import streamlit as st
import pandas as pd
import re
import json
import io
import google.generativeai as genai

# =====================================================================
# CẤU HÌNH TRANG VÀ KHÓA BỘ NHỚ FILE VĨNH VIỄN (STATE LOCK)
# =====================================================================
st.set_page_config(
    page_title="3. AI FABRIC CONSUMPTION", 
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("📊 TRỢ LÝ ĐỊNH MỨC NGUYÊN PHỤ LIỆU TỰ ĐỘNG (BOM)")
st.caption("Cấu trúc lõi 13-Engine VECTOR CAD/AI - Phân tích rập thô xếp ly, cơi đáp túi mổ thực tế xưởng sản xuất")
st.markdown("---")

if "width_inch_override" not in st.session_state: st.session_state.width_inch_override = None
if "shrinkage_override" not in st.session_state: st.session_state.shrinkage_override = None
if "is_calculated" not in st.session_state: st.session_state.is_calculated = False
if "gemini_parsed_bom_data" not in st.session_state: st.session_state.gemini_parsed_bom_data = None
if "saved_pdf_bytes" not in st.session_state: st.session_state.saved_pdf_bytes = None
if "saved_pdf_name" not in st.session_state: st.session_state.saved_pdf_name = None

if "sidebar_chat_history" not in st.session_state:
    st.session_state.sidebar_chat_history = [
        {"role": "assistant", "content": "Xin chào! Hệ thống đã được nâng cấp lên Lõi Phân Tích Rập Thô Công Nghiệp. AI sẽ tự động phân tích xếp ly, cấu trúc túi mổ (cơi, đáp) và túi hộp để tính toán diện tích vải trước khi may."}
    ]

def update_config_from_text(text: str):
    """NLP Parser công nghiệp: Tự động trích xuất thông số từ nội dung chat"""
    if not text: return
    text_lower = text.lower()
    
    # 1. Quét tìm khổ vải vật lý
    width_match = re.search(r'(?:khổ|width|vải|đm|mức|cắt)\s*(\d+)', text_lower)
    if width_match: 
        st.session_state.width_inch_override = float(width_match.group(1))
        st.session_state.is_calculated = True

    # 2. Quét tìm độ co rút dọc L
    co_l_match = re.search(r'(?:co dọc|dọc|l|warp)\s*(\d+)', text_lower)
    if co_l_match: 
        st.session_state.shrinkage_override = float(co_l_match.group(1))
    else:
        generic_co = re.search(r'(?:co rút|độ co|co)\s*(\d+)', text_lower)
        if generic_co: st.session_state.shrinkage_override = float(generic_co.group(1))

    # 3. Quét tìm độ co rút ngang W
    co_w_match = re.search(r'(?:co ngang|ngang|w|weft)\s*(\d+)', text_lower)
    if co_w_match:
        if "gemini_parsed_bom_data" in st.session_state and st.session_state.gemini_parsed_bom_data:
            materials = st.session_state.gemini_parsed_bom_data.get("materials_bom", [])
            if isinstance(materials, list):
                for mat in materials:
                    if isinstance(mat, dict) and mat.get("placement") == "SHELL":
                        mat["shrinkage_weft"] = float(co_w_match.group(1))

def safe_float(val, default=0.0) -> float:
    if val is None: return default
    try: return float(val)
    except (ValueError, TypeError): return default

# =====================================================================
# AI GEMINI VISION PARSER QUÉT CẤU TRÚC MAY RẬP THÔ THỰC TẾ
# =====================================================================
def ai_gemini_vision_pdf_parser(pdf_file_name, pdf_bytes) -> dict:
    """Ép buộc AI đóng vai trò Pattern Maker bóc tách rập thô dựa trên kỹ thuật may ráp"""
    try:
        if "GEMINI_API_KEY" in st.secrets: genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        elif "gemini" in st.secrets: genai.configure(api_key=st.secrets["gemini"].get("api_key", ""))
        
        pdf_blob = {"mime_type": "application/pdf", "data": pdf_bytes}
        prompt = """
        Bạn là một Trưởng phòng kỹ thuật rập CAD (Pattern Master). Hãy phân tích toàn bộ tài liệu kỹ thuật PDF này (Bản vẽ Sketch, Bảng thông số, Mô tả quy cách may).
        Nhiệm vụ bắt buộc là phải bóc tách đầy đủ các chi tiết rập thô (Gross Pattern Pieces) trước khi may ráp, cụ thể:
        1. KIỂM TRA XẾP LY (Pleats/Tucks): Xem thân áo/quần hay túi hộp có xếp ly không. Nếu có, kích thước rập thô bắt buộc phải CỘNG THÊM độ sâu của ly (Ví dụ: ly lật cộng thêm 1.5 inch đến 3 inch tùy quy cách ly).
        2. KIỂM TRA CẤU TRÚC TÚI MỔ (Welt/Piping Pocket): Nếu có túi mổ, bắt buộc phải bóc tách thêm chi tiết vải chính gồm: Cơi túi (Welt), Đáp cơi túi (Facing), và các miếng Lót túi (Pocket Bag) bằng vải lót phối.
        3. KIỂM TRA TÚI HỘP (Cargo Pocket): Xác định xem túi có thành túi (Pocket Wall/Bellow) và xếp ly không. Kích thước rập thô của túi phải bằng: Ngang thành phẩm + (Độ sâu ly * số lượng) + (Chiều cao thành túi * 2) + Đường may.
        4. Tuyệt đối liệt kê đủ tất cả chi tiết vải chính (SHELL) cấu thành nên sản phẩm thật trên bàn cắt.

        Trả về chuỗi JSON duy nhất theo cấu trúc chính xác dưới đây:
        {
            "style_code": "Mã style hàng",
            "description": "Mô tả sản phẩm",
            "category": "pant hoặc jacket hoặc shirt",
            "sewing_spec": {
                "hem_allowance_inch": Chiều rộng đường may lai gấu (dạng số, ví dụ gấu cuộn 1.5 inch thì ghi 1.5)"
            },
            "materials_bom": [
                {"placement": "SHELL", "width_inch": 58.0, "shrinkage_warp": 5.0, "shrinkage_weft": 15.0, "material_name": "Vải chính"}
            ],
            "garment_panels": [
                {
                    "panel_name": "Tên chi tiết rập thô (Ví dụ: Thân Trước, Thân Sau, Lưng/Cạp, Cơi Túi Mổ, Đáp Túi Mổ, Túi Hộp Cargo, Nắp Túi, Đỉa...)",
                    "quantity_per_garment": Số lượng chi tiết này cần cắt trên 1 sản phẩm dạng số,
                    "length_inch": "Kích thước chiều dài thành phẩm đo từ bảng (chuỗi hoặc số)",
                    "width_inch": "Kích thước chiều rộng thành phẩm đo từ bảng (chuỗi hoặc số)",
                    "measurement_type": "half hoặc full",
                    "added_allowance_for_pleats_or_walls": "Ghi chú kỹ thuật số inch đã cộng thêm cho xếp ly/thành túi/đáp cơi (Ví dụ: '+3.0 inch cho ly hộp và thành túi', hoặc '0' nếu không có)"
                }
            ]
        }
        """
        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content([pdf_blob, prompt])
        clean_text = response.text.strip().replace("```json", "").replace("```", "")
        return json.loads(clean_text)
    except Exception as e:
        st.error(f"Lỗi phân tích AI: {str(e)}")
        return None
# =====================================================================
# SIDEBAR CONTROL (KHÔI PHỤC HOÀN TOÀN Ô CHAT VÀ LỊCH SỬ TƯƠNG TÁC)
# =====================================================================
with st.sidebar:
    st.header("💬 TRỢ LÝ SẢN XUẤT AI")
    if st.button("🗑️ Xóa lịch sử & Reset định mức", use_container_width=True):
        st.session_state.width_inch_override = None
        st.session_state.shrinkage_override = None
        st.session_state.is_calculated = False
        st.session_state.gemini_parsed_bom_data = None
        st.session_state.saved_pdf_bytes = None
        st.session_state.saved_pdf_name = None
        st.session_state.sidebar_chat_history = [
            {"role": "assistant", "content": "Hệ thống đã reset. Vui lòng tải file PDF Techpack mới để bắt đầu quy trình."}
        ]
        st.cache_data.clear()
        st.rerun()
        
    st.write("Nhập bổ sung thông tin vải, độ co rút sau khi tải PDF.")
    st.markdown("---")
    
    for chat in st.session_state.sidebar_chat_history:
        with st.chat_message(chat["role"]): st.markdown(chat["content"])
            
    user_prompt = st.chat_input("Gửi thông số cho AI...", key="garment_chat_input_unique")

if user_prompt:
    st.session_state.sidebar_chat_history.append({"role": "user", "content": user_prompt})
    update_config_from_text(user_prompt)
    st.session_state.sidebar_chat_history.append({
        "role": "assistant", 
        "content": f"⚙️ Đã nhận diện thông số: '{user_prompt}'. Tiến hành giải mã phân số bảng POM và đẩy định mức mới cập nhật vào bảng BOM ngay lập tức..."
    })
    st.rerun()

# =====================================================================
# ENGINE QUY ĐỔI PHÂN SỐ NGÀNH MAY 
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
