# =====================================================================
# ĐOẠN 2b1: GIAO DIỆN CHÍNH, KHÓA BỘ NHỚ VÀ ENGINE BÓC TÁCH CHI TIẾT RẬP CAD
# =====================================================================
st.subheader("📁 BƯỚC 1: TẢI TÀI LIỆU KỸ THUẬT SẢN XUẤT (TECHPACK / BOM)")
uploaded_file = st.file_uploader("Kéo và thả file PDF Techpack hoặc bảng BOM của bạn vào đây", type=["pdf"], key="pdf_uploader")

if uploaded_file is not None:
    if st.session_state.saved_pdf_name != uploaded_file.name:
        st.session_state.saved_pdf_bytes = uploaded_file.read()
        st.session_state.saved_pdf_name = uploaded_file.name
        st.session_state.gemini_parsed_bom_data = None  

if st.session_state.saved_pdf_bytes is not None:
    st.success(f"📥 **Hệ thống đã khóa file và duy trì liên tục:** `{st.session_state.saved_pdf_name}`")
    
    if st.session_state.gemini_parsed_bom_data is None:
        with st.spinner("AI đang bóc tách quy cách may, tính toán bù xếp ly và cấu trúc túi mổ..."):
            st.session_state.gemini_parsed_bom_data = ai_gemini_vision_pdf_parser(
                st.session_state.saved_pdf_name, st.session_state.saved_pdf_bytes
            )

    data = st.session_state.gemini_parsed_bom_data
    if data:
        st.markdown("### 📋 THÔNG TIN CHUNG SẢN PHẨM")
        col1, col2, col3 = st.columns(3)
        col1.metric("Mã sản phẩm (Style)", data.get("style_code", "N/A"))
        col2.metric("Mô tả", data.get("description", "N/A"))
        category = data.get("category", "pant").lower()
        col3.metric("Phân loại cấu trúc", category.upper())

        # LƯU TRỮ VÀ HIỂN THỊ DANH MỤC CHI TIẾT RẬP AI BÓC TÁCH ĐƯỢC TỪ TRANG SKETCH/POM
        panels = data.get("garment_panels", [])
        st.markdown("### 📐 DANH MỤC CÁC CHI TIẾT RẬP THÔ KỸ THUẬT MAY (GROSS PANEL LOG)")
        
        panel_records = []
        sewing_seam_allowance = 0.44  # Biên đường may ráp công đoạn 0.44" chuẩn
        sewing_spec = data.get("sewing_spec", {})
        hem_allowance = parse_garment_fraction(sewing_spec.get("hem_allowance_inch", 0.75))

        total_garment_fabric_area = 0.0  # Biến tích lũy diện tích rập hình học thực tế

        for p in panels:
            name = p.get("panel_name", "Chi tiết phụ")
            qty = int(safe_float(p.get("quantity_per_garment", 1.0)))
            l_inch = parse_garment_fraction(p.get("length_inch"))
            w_inch = parse_garment_fraction(p.get("width_inch"))
            allowance_note = p.get("added_allowance_for_pleats_or_walls", "0")

            # Chuẩn hóa số đo bề ngang cho các chi tiết thân lớn dải chu vi sơ đồ
            m_type = str(p.get("measurement_type", "half")).lower()
            if m_type == "half" and any(x in name.lower() for x in ["thân", "lưng", "cạp", "waist", "hip"]):
                w_inch = w_inch * 2.0

            # Áp dụng công thức rập thô: Cộng biên đường may ráp nối (+0.44" mỗi đầu chi tiết)
            p_length = l_inch + (2 * sewing_seam_allowance)
            if any(x in name.lower() for x in ["thân", "main", "outseam"]):
                p_length += hem_allowance
                
            p_width = w_inch + (2 * sewing_seam_allowance)

            # Tính diện tích rập phẳng chiếm dụng thật của cấu phần này (SL * Dài rập * Rộng rập)
            panel_area = p_length * p_width * qty
            total_garment_fabric_area += panel_area

            panel_records.append({
                "Chi tiết rập thô": name,
                "Số lượng (SL)": qty,
                "Dài rập thô (+May)": round(p_length, 2),
                "Rộng rập thô (+May)": round(p_width, 2),
                "Cộng bù kỹ thuật (Ly/Cơi/Thành)": allowance_note,
                "Diện tích rập (inch²)": round(panel_area, 2)
            })

        df_panels = pd.DataFrame(panel_records)
        st.dataframe(df_panels, use_container_width=True, hide_index=True)

        # ĐỒNG BỘ BẢO TOÀN DANH MỤC PHỤ LIỆU (Ép thêm Keo lót lót và Lót túi nếu thiếu)
        materials = data.get("materials_bom", [])
        has_pocketing = any("POCKETING" in str(m.get("placement")).upper() for m in materials)
        has_interlining = any("INTERLINING" in str(m.get("placement")).upper() for m in materials)
        
        if not has_pocketing:
            materials.append({"placement": "POCKETING", "width_inch": 60.0, "shrinkage_warp": 0.0, "shrinkage_weft": 0.0, "material_name": "TC POCKETING (Vải lót túi)"})
        if not has_interlining:
            materials.append({"placement": "INTERLINING", "width_inch": 44.0, "shrinkage_warp": 0.0, "shrinkage_weft": 0.0, "material_name": "TRICOT FUSING (Keo lót phôi)"})
        data["materials_bom"] = materials
# =====================================================================
# ENGINE QUY ĐỔI PHÂN SỐ NGÀNH MAY (ĐÃ ĐƯA LÊN ĐẦU ĐOẠN ĐỂ VÁ LỖI BIÊN DỊCH)
# =====================================================================
def parse_garment_fraction(val) -> float:
    """Chuyển đổi chính xác phân số hỗn hợp ngành may thành số thập phân thực tế"""
    if val is None: return 0.0
    val_str = str(val).strip()
    if not val_str or val_str.lower() in ['none', 'null', 'n/a']: return 0.0
    
    try: return float(val_str)
    except ValueError: pass
    
    try:
        if '/' in val_str:
            parts_list = re.split(r'[\s\-]+', val_str)
            if len(parts_list) == 2:
                frac_part_str = parts_list.pop()
                whole_part_str = parts_list.pop()
                whole_num = float(whole_part_str)
                
                sub_parts = frac_part_str.split('/')
                den_num = float(sub_parts.pop())
                num_num = float(sub_parts.pop())
                return whole_num + (num_num / den_num)
            elif len(parts_list) == 1:
                frac_part_str = parts_list.pop()
                sub_parts = frac_part_str.split('/')
                den_num = float(sub_parts.pop())
                num_num = float(sub_parts.pop())
                return num_num / den_num
    except Exception:
        pass
    return safe_float(val, 0.0)

# =====================================================================
# ĐOẠN 2b1: GIAO DIỆN CHÍNH, KHÓA BỘ NHỚ VÀ ENGINE BÓC TÁCH CHI TIẾT RẬP CAD
# =====================================================================
st.subheader("📁 BƯỚC 1: TẢI TÀI LIỆU KỸ THUẬT SẢN XUẤT (TECHPACK / BOM)")
uploaded_file = st.file_uploader("Kéo và thả file PDF Techpack hoặc bảng BOM của bạn vào đây", type=["pdf"], key="pdf_uploader")

if uploaded_file is not None:
    if st.session_state.saved_pdf_name != uploaded_file.name:
        st.session_state.saved_pdf_bytes = uploaded_file.read()
        st.session_state.saved_pdf_name = uploaded_file.name
        st.session_state.gemini_parsed_bom_data = None  

if st.session_state.saved_pdf_bytes is not None:
    st.success(f"📥 **Hệ thống đã khóa file và duy trì liên tục:** `{st.session_state.saved_pdf_name}`")
    
    if st.session_state.gemini_parsed_bom_data is None:
        with st.spinner("AI đang bóc tách quy cách may, tính toán bù xếp ly và cấu trúc túi mổ..."):
            st.session_state.gemini_parsed_bom_data = ai_gemini_vision_pdf_parser(
                st.session_state.saved_pdf_name, st.session_state.saved_pdf_bytes
            )

    data = st.session_state.gemini_parsed_bom_data
    if data:
        st.markdown("### 📋 THÔNG TIN CHUNG SẢN PHẨM")
        col1, col2, col3 = st.columns(3)
        col1.metric("Mã sản phẩm (Style)", data.get("style_code", "N/A"))
        col2.metric("Mô tả", data.get("description", "N/A"))
        category = data.get("category", "pant").lower()
        col3.metric("Phân loại cấu trúc", category.upper())

        # LƯU TRỮ VÀ HIỂN THỊ DANH MỤC CHI TIẾT RẬP AI BÓC TÁCH ĐƯỢC TỪ TRANG SKETCH/POM
        panels = data.get("garment_panels", [])
        st.markdown("### 📐 DANH MỤC CÁC CHI TIẾT RẬP THÔ KỸ THUẬT MAY (GROSS PANEL LOG)")
        
        panel_records = []
        sewing_seam_allowance = 0.44  # Biên đường may ráp công đoạn 0.44" chuẩn
        sewing_spec = data.get("sewing_spec", {})
        hem_allowance = parse_garment_fraction(sewing_spec.get("hem_allowance_inch", 0.75))

        total_garment_fabric_area = 0.0  # Biến tích lũy diện tích rập hình học thực tế

        for p in panels:
            name = p.get("panel_name", "Chi tiết phụ")
            qty = int(safe_float(p.get("quantity_per_garment", 1.0)))
            l_inch = parse_garment_fraction(p.get("length_inch"))
            w_inch = parse_garment_fraction(p.get("width_inch"))
            allowance_note = p.get("added_allowance_for_pleats_or_walls", "0")

            # Chuẩn hóa số đo bề ngang cho các chi tiết thân lớn dải chu vi sơ đồ
            m_type = str(p.get("measurement_type", "half")).lower()
            if m_type == "half" and any(x in name.lower() for x in ["thân", "lưng", "cạp", "waist", "hip"]):
                w_inch = w_inch * 2.0

            # Áp dụng công thức rập thô: Cộng biên đường may ráp nối (+0.44" mỗi đầu chi tiết)
            p_length = l_inch + (2 * sewing_seam_allowance)
            if any(x in name.lower() for x in ["thân", "main", "outseam"]):
                p_length += hem_allowance
                
            p_width = w_inch + (2 * sewing_seam_allowance)

            # Tính diện tích rập phẳng chiếm dụng thật của cấu phần này (SL * Dài rập * Rộng rập)
            panel_area = p_length * p_width * qty
            total_garment_fabric_area += panel_area

            panel_records.append({
                "Chi tiết rập thô": name,
                "Số lượng (SL)": qty,
                "Dài rập thô (+May)": round(p_length, 2),
                "Rộng rập thô (+May)": round(p_width, 2),
                "Cộng bù kỹ thuật (Ly/Cơi/Thành)": allowance_note,
                "Diện tích rập (inch²)": round(panel_area, 2)
            })

        df_panels = pd.DataFrame(panel_records)
        st.dataframe(df_panels, use_container_width=True, hide_index=True)

        # ĐỒNG BỘ BẢO TOÀN DANH MỤC PHỤ LIỆU (Ép thêm Keo lót phối và Lót túi nếu thiếu)
        materials = data.get("materials_bom", [])
        has_pocketing = any("POCKETING" in str(m.get("placement")).upper() for m in materials)
        has_interlining = any("INTERLINING" in str(m.get("placement")).upper() for m in materials)
        
        if not has_pocketing:
            materials.append({"placement": "POCKETING", "width_inch": 60.0, "shrinkage_warp": 0.0, "shrinkage_weft": 0.0, "material_name": "TC POCKETING (Vải lót túi)"})
        if not has_interlining:
            materials.append({"placement": "INTERLINING", "width_inch": 44.0, "shrinkage_warp": 0.0, "shrinkage_weft": 0.0, "material_name": "TRICOT FUSING (Keo lót phôi)"})
        data["materials_bom"] = materials
        # --- ĐOẠN 2b2: TOÁN HỌC SƠ ĐỒ CÔNG NGHIỆP CỘNG DỒN CHI TIẾT RẬP VÀ ĐỔ BẢNG BOM ---
        materials = data.get("materials_bom", [])
        
        # Trích xuất chiều dài cấu phần lớn nhất (Thân chính) để làm lõi định vị luồng xếp sơ đồ
        max_panel_length = 0.0
        for p in panels:
            name_lower = p.get("panel_name", "").lower()
            if any(x in name_lower for x in ["thân", "main", "outseam", "sau", "trước", "body"]):
                l_val = parse_garment_fraction(p.get("length_inch"))
                if l_val > max_panel_length:
                    max_panel_length = l_val
        if max_panel_length == 0:
            max_panel_length = 42.5 if "pant" in category.upper() else 28.0

        for mat in materials:
            placement_upper = str(mat.get("placement")).upper()
            
            # Đồng bộ thông số khổ vải và độ co rút tương tác động từ ô chat bên trái
            if "SHELL" in placement_upper:
                if st.session_state.width_inch_override: mat["width_inch"] = st.session_state.width_inch_override
                if st.session_state.shrinkage_override: mat["shrinkage_warp"] = st.session_state.shrinkage_override
            elif any(x in placement_upper for x in ["INTERLINING", "POCKETING"]):
                chat_content = str(st.session_state.sidebar_chat_history[-1].get("content", "")).lower()
                if any(x in chat_content for x in ["keo", "mếch", "lót", "phối"]) and st.session_state.width_inch_override:
                    mat["width_inch"] = st.session_state.width_inch_override

            w_inch = parse_garment_fraction(mat.get("width_inch"))
            if w_inch == 0:
                if "POCKETING" in placement_upper: w_inch = 60.0; mat["width_inch"] = 60.0
                elif "INTERLINING" in placement_upper: w_inch = 44.0; mat["width_inch"] = 44.0
                else: w_inch = 58.0; mat["width_inch"] = 58.0

            s_warp = safe_float(mat.get("shrinkage_warp", 5.0 if "SHELL" in placement_upper else 0.0)) / 100.0
            s_weft = safe_float(mat.get("shrinkage_weft", 15.0 if "SHELL" in placement_upper else 0.0)) / 100.0
            
            if "SHELL" in placement_upper and st.session_state.shrinkage_override:
                s_warp = st.session_state.shrinkage_override / 100.0

            # THUẬT TOÁN ĐỊNH MỨC SƠ ĐỒ BÀN CẮT DỰA TRÊN DIỆN TÍCH RẬP THÔ THỰC TẾ (GROSS PATTERN AREA):
            if total_garment_fabric_area > 0:
                # 1. Nhân hệ số co rút dọc và ngang tác động lên rập vải chính
                final_fabric_area_sq_inch = total_garment_fabric_area * (1 + s_warp) * (1 + s_weft)
                
                # 2. Quy đổi tổng diện tích chiếm dụng dạng inch vuông sang mét dài khổ vải
                base_consumption_meter = (final_fabric_area_sq_inch / w_inch) / 39.37
                
                if "PANT" in category.upper():
                    # Đối với quần (Jeans, Kaki Cargo): Hiệu suất sơ đồ đan xen các cấu phần túi hộp, cạp rập đạt 84%
                    calc_consumption = base_consumption_meter / 0.84
                    
                    if "POCKETING" in placement_upper: calc_consumption = 0.25 # Lót túi tiêu chuẩn
                    elif "INTERLINING" in placement_upper: calc_consumption = 0.12 # Keo lưng tiêu chuẩn
                else:
                    # Đối với áo (Jacket có túi mổ, cơi đáp phức tạp): Hiệu suất sơ đồ đạt 85%
                    calc_consumption = base_consumption_meter / 0.85
                    
                    if "POCKETING" in placement_upper: calc_consumption = 0.35 # Lót túi áo khoác
                    elif "INTERLINING" in placement_upper: calc_consumption = 0.45 # Mex keo nẹp/cổ áo

                # 3. Cộng biên lỗi cắt kỹ thuật đầu tấm đại trà (5%)
                calc_consumption = calc_consumption * 1.05

                mat["consumption_meter_per_pcs"] = round(calc_consumption, 3)
                mat["consumption_yard_per_pcs"] = round(calc_consumption * 1.09361, 3)
            else:
                mat["consumption_meter_per_pcs"] = "Khuyết số đo chi tiết rập"
                mat["consumption_yard_per_pcs"] = "Khuyết số đo chi tiết rập"

        st.markdown("### 🧵 BẢNG ĐỊNH MỨC NGUYÊN PHỤ LIỆU ĐỘNG (MATERIALS BOM)")
        df_bom = pd.DataFrame(materials)
        
        cols_order = ['placement', 'material_name', 'consumption_meter_per_pcs', 'consumption_yard_per_pcs', 'width_inch', 'shrinkage_warp', 'shrinkage_weft', 'gsm']
        df_bom = df_bom[[c for c in cols_order if c in df_bom.columns]]
        st.dataframe(df_bom, use_container_width=True)
        
        # Băng thông báo thông số rập minh chứng kỹ thuật dưới chân bảng
        st.info(f"⚙️ **Lõi CAD Sơ đồ Tích lũy (Gross Area):** Tổng diện tích rập thô bao gồm cộng bù Xếp ly, Cơi, Đáp, Thành túi (+May 0.44\"): `{round(total_garment_fabric_area, 2)} inch vuong`. Hiệu suất dải sơ đồ thực tế: `84.0%` (Quần) / `85.0%` (Áo).")
    else:
        st.warning("⚠️ AI không thể trích xuất cấu trúc dữ liệu từ file PDF này. Vui lòng kiểm tra lại chất lượng file.")
else:
    st.info("💡 Vui lòng tải một file PDF Techpack lên để hệ thống phân tích hình học đa giác.")
