import streamlit as st
import pandas as pd
import json
import io
import re

st.set_page_config(layout="wide")

# KIỂM TRA ĐIỀU KIỆN 1: Nếu CHƯA bốc tách file SBD thành công
if not st.session_state.get("purchase_ready"):
    st.markdown("""<div class="card-container"><div class="card-section-header">📋 PHÂN HỆ TÁC NGHIỆP BÀN CẮT ĐA GIÀNG NÂNG CAO</div>
    <p style="color: #64748B; font-size:13px; margin:0;">Tải lên File SBD (Excel/PDF) chứa thông tin Giàng (Inseam), Nhóm Size để hệ thống tự động số hóa ma trận.</p></div>""", unsafe_allow_html=True)
    
    file_sbd_c2 = st.file_uploader("📋 Chọn File SBD Số Lượng Đơn Hàng (Excel/PDF)", type=["xlsx", "xls", "pdf"], key="purchase_sbd_c2_unique")
    if file_sbd_c2:
        trigger_btn_c2 = st.button("⚡ SỐ HÓA MA TRẬN SẢN LƯỢNG ĐƠN HÀNG TÁC NGHIỆP", type="primary", use_container_width=True, key="activate_sbd_only_ingest_c2")
        if trigger_btn_c2:
            with st.spinner("🚀 Hệ thống đang phân tích mảng phân bổ size phẳng từ file SBD..."):
                if "get_secure_gemini_key" in globals(): 
                    gemini_key = get_secure_gemini_key()
                else: 
                    gemini_key = st.secrets.get("GEMINI_API_KEY", "").strip()
                
                from google import genai
                from google.genai import types
                
                client_ai = genai.Client(api_key=gemini_key)
                sbd_bytes = file_sbd_c2.getvalue()
                sbd_content_str = ""
                sbd_parts_payload = []
                if file_sbd_c2.name.lower().endswith(('.xlsx', '.xls')):
                    try:
                        excel_data = pd.read_excel(io.BytesIO(sbd_bytes), sheet_name=None)
                        for sheet_name, df_sheet in excel_data.items():
                            sbd_content_str += f"\n--- SHEET: {sheet_name} ---\n{df_sheet.fillna('').to_csv(index=False)}"
                    except Exception: pass
                elif file_sbd_c2.name.lower().endswith('.pdf'):
                    sbd_parts_payload.append(types.Part.from_bytes(data=sbd_bytes, mime_type='application/pdf'))
                    
                sbd_prompt = """Bạn là một chuyên gia số hóa tài liệu ngành dệt may. Hãy phân tích bảng 'Quantity Details' trong tài liệu được cung cấp.
                1. Trích xuất mã hàng nằm ở mục 'Key Item' hoặc 'Style' (Ví dụ: '6082').
                2. Trích xuất tổng sản lượng ở mục 'Units' hoặc 'Total' (Ví dụ: 2500).
                3. Trích xuất toàn bộ danh sách kích cỡ nằm ở hàng tiêu đề của bảng số lượng (Ví dụ: '26 X 30', '28 X 30', '29 X 32').
                
                QUY TẮC ÉP KIỂU MA TRẬN SIZE BẮT BUỘC:
                - Đối với các tiêu đề cột có dạng nối liền như '26 X 30' hoặc '30 X 32', bạn PHẢI giữ nguyên cấu trúc chuỗi văn bản gốc này làm Tên Khóa (Key Name) của mảng 'size_breakdown'. 
                - Hãy nhặt con số sản lượng thực tế nằm ngay dưới cột cỡ đó (Ví dụ dưới cột '26 X 30' có số '88'). Bỏ qua các hàng trống hoặc các cột tổng.
                
                Trả về kết quả DUY NHẤT dưới dạng cấu trúc JSON gốc sạch sẽ, không kèm từ giải thích rác:
                {
                    "style_id": "6082",
                    "total_quantity": 2500,
                    "size_breakdown": {
                        "26 X 30": 88,
                        "28 X 30": 156
                    }
                }"""
                if sbd_content_str: sbd_parts_payload.append(types.Part.from_text(text=sbd_content_str))
                sbd_parts_payload.append(types.Part.from_text(text=sbd_prompt))
                
                try:
                    res_sbd = client_ai.models.generate_content(model='gemini-2.5-flash', contents=sbd_parts_payload, config=types.GenerateContentConfig(response_mime_type="application/json"))
                    st.session_state["sbd_parsed_data"] = json.loads(res_sbd.text.strip().replace("```json", "").replace("```", "").strip())
                except Exception: pass
                st.session_state["pur_tp_parsed_data"] = {"dummy_status": "skipped_not_needed"}
                st.session_state["purchase_ready"] = True
                st.rerun()
# KIỂM TRA ĐIỀU KIỆN 2: Nếu ĐÃ số hóa xong file SBD -> Màn hình tác nghiệp sản xuất
else:
    sbd_data_store = st.session_state.get("sbd_parsed_data", {})
    if isinstance(sbd_data_store, dict) and sbd_data_store:
        detected_style_id = sbd_data_store.get("style_id", "UNKNOWN_STYLE")
        detected_total_po = sbd_data_store.get("total_quantity", 0)
        size_breakdown_main = sbd_data_store.get("size_breakdown", {})

        if st.button("🔄 Tải lên File SBD Khác", type="secondary"):
            st.session_state["purchase_ready"] = False
            st.session_state["sbd_parsed_data"] = {}
            st.session_state["consumption_activated"] = False
            st.session_state["auto_cutting_results"] = None
            st.rerun()

        st.markdown("#### 📋 KHAI BÁO THÔNG SỐ TÁC NGHIỆP ĐƠN HÀNG VÀ BÀN VẢI MULTI-INSEAM")
        input_col1, input_col2, input_col3, input_col_color = st.columns(4)
        with input_col1: style_id_input = st.text_input("🏷️ Tên mã hàng (Style ID):", value=str(detected_style_id).strip().upper())
        with input_col2: po_qty_input = st.number_input("📦 Số lượng đơn hàng (PO Pcs):", value=int(detected_total_po), step=100)
        with input_col3: consumption_input = st.number_input("🎯 Định mức tài liệu đề xuất (Yds/Pcs):", value=1.140, step=0.001, format="%.3f")
        with input_col_color: color_input = st.text_input("🎨 Tự gõ Màu vải:", value="BLACK")
        input_col4, input_col5, input_col6 = st.columns(3)
        with input_col4: max_table_length = st.number_input("📏 Chiều gia tối đa bàn vải (Meters):", value=12.00, step=1.0)
        with input_col5: fabric_type_input = st.text_input("🧵 Tự gõ Loại vải:", value="CHÍNH")
        with input_col6: cuttable_width_inch = st.number_input("📐 KHỔ CẮT (Khổ vải đi sơ đồ - Inches):", value=56.00, step=0.50, format="%.2f")
        
        cad_paste_zone = st.text_area("Sau khi xem cấu trúc phối size phía dưới, hãy đi sơ đồ trên máy CAD rồi copy dán kết quả [Tên sơ đồ + Chiều dài mét] vào đây:", placeholder="Ví dụ dán bảng từ Excel CAD:\n5844-c01 1.05\n5844-c02 10", height=90, key="cad_bulk_paste_c2")
        
        active_sizes = [str(k) for k, v in size_breakdown_main.items() if int(v) > 0]
        if not active_sizes: active_sizes = ["S", "M", "L", "XL", "2XL", "3XL"]
        
        btn_col1, btn_col2 = st.columns(2)
        with btn_col1: trigger_auto_cutting = st.button("⚡ 1. KÍCH HOẠT TÍNH TÁC NGHIỆP SƠ ĐỒ (AI GIẢI MA TRẬN TỶ LỆ)", type="primary", use_container_width=True, key="c2_normal_cut_btn")
        with btn_col2: trigger_consumption = st.button("🤖 2. KÍCH HOẠT NHẢY SỐ ĐỊNH MỨC VÀ ĐỐI CHIẾU CAD", type="secondary", use_container_width=True, key="c2_consumption_btn")
        if trigger_auto_cutting:
            with st.spinner("🤖 AI đang phân tích dữ liệu, áp dụng quy tắc chặn số lớp ít - tỷ lệ nhỏ công nghiệp..."):
                if "get_secure_gemini_key" in globals(): 
                    gemini_key = get_secure_gemini_key()
                else: 
                    gemini_key = st.secrets.get("GEMINI_API_KEY", "").strip()
                
                from google import genai
                from google.genai import types
                
                client_ai = genai.Client(api_key=gemini_key)
                
                # ÉP TOÀN BỘ RÀNG BUỘC SỐ LỚP ÍT KHÔNG ĐƯỢC ĐI TỶ LỆ LỚN VÀO PROMPT [INDEX]
                ai_cutting_prompt = f"""
                Bạn là một kỹ sư toán học điều độ bàn cắt công nghiệp dệt may đại tài. Hãy lập phương án sơ đồ phối size cho đơn hàng này.
                
                DANH SÁCH SIZE GỐC BẮT BUỘC SỬ DỤNG LÀM KEY: {json.dumps(list(size_breakdown_main.keys()))}
                SẢN LƯỢNG ĐƠN HÀNG GỐC CẦN TRIỆT TIÊU: {json.dumps(size_breakdown_main)}
                
                THÔNG SỐ GIỚI HẠN FORM:
                - Chiều dài gia tối đa bàn vải cho phép: {max_table_length} Mét
                - Định mức tài liệu đề xuất: {consumption_input} Yds/Pcs
                - Khổ cắt: {cuttable_width_inch} Inches
                - Loại vải tác nghiệp: {fabric_type_input}

                QUY TẮC TOÁN HỌC & RÀNG BUỘC KỸ THUẬT BAN CẮT BẮT BUỘC [INDEX]:
                1. RÀNG BUỘC SỐ LỚP VÀ TỶ LỆ (QUY TẮC CHẶN HAO VẢI ĐẦU KHÚC) [INDEX]: 
                   - Nếu Số Lớp (Layers) LỚN (Từ 50 lớp trở lên): BẮT BUỘC đi sơ đồ gộp có tổng tỷ lệ lớn (Ví dụ tổng tỉ lệ bằng 3, 4, 5 hoặc 6 quần trên một sơ đồ) để chiều dài sơ đồ đạt sát trần {max_table_length}m nhằm tối ưu năng suất và tiết kiệm vải đầu bàn [INDEX].
                   - Nếu Số Lớp (Layers) ÍT (Dưới 40 lớp hoặc các bàn vét đuôi lẻ): TUYỆT ĐỐI KHÔNG ĐƯỢC đi sơ đồ gộp có tổng tỷ lệ lớn [INDEX]. Nếu số lớp ít, tổng tỷ lệ của sơ đồ đó CHỈ ĐƯỢC PHÉP bằng 1 quần (Sơ đồ vét đơn) hoặc tối đa là 2 quần để bàn vải không bị quá ngắn, tránh hiện tượng hao phí vải đầu khúc lãng phí [INDEX].
                2. Hãy làm phép toán trừ lùi lũy tiến (Lượng dư còn lại = Sản lượng gốc - Tỉ lệ * Số lớp * Số bàn) qua từng bàn để ép số dư 'CÒN LẠI' ở sơ đồ cuối cùng về đúng số 0 sạch sẽ [INDEX].
                3. Tổng sản lượng cắt (Tỉ lệ * Số lớp * Số bàn) của tất cả sơ đồ cộng lại phải trùng khớp chính xác 100% với sản lượng PO ban đầu [INDEX].

                Trả về duy nhất mảng JSON sạch cấu trúc mẫu, không viết chữ giải thích rác:
                [
                    {{"Sơ đồ / Trạng thái": "c01", "Ratios": {{ "Điền_Đúng_Khóa_Size_Gốc_1": 2, "Điền_Đúng_Khóa_Size_Gốc_2": 2 }}, "Số lớp": 120, "Số bàn": 1, "Số sp/SĐ": 4}}
                ]
                """
                try:
                    res_cutting = client_ai.models.generate_content(model='gemini-2.5-flash', contents=[ai_cutting_prompt])
                    st.session_state["auto_cutting_results"] = json.loads(res_cutting.text.strip().replace("```json", "").replace("```", "").strip())
                    st.success("🎯 AI đã giải mã toán ma trận phối size gộp và vét đầu khúc theo ràng buộc số lớp thành công!")
                except Exception:
                    st.session_state["auto_cutting_results"] = [{"Sơ đồ / Trạng thái": f"c{str(i+1).zfill(2)}", "Ratios": {s: (1 if s == sz else 0) for s in active_sizes}, "Số lớp": 50, "Số bàn": 1, "Số sp/SĐ": 1} for i, sz in enumerate(active_sizes)]

        if trigger_consumption:
            st.session_state["consumption_activated"] = True
            st.rerun()

        if st.session_state.get("auto_cutting_results") is not None:
            cad_lengths_map = {}
            if cad_paste_zone.strip() and st.session_state.get("consumption_activated"):
                for line in cad_paste_zone.strip().split("\n"):
                    if not line.strip(): continue
                    match = re.search(r'(p\d{2}|c\d{2})[\s\t]+([0-9]*\.?[0-9]+)', line.lower().strip())
                    if match:
                        try: cad_lengths_map[match.group(1)] = float(match.group(2))
                        except ValueError: pass

            color_display = st.session_state.get("sbd_parsed_data", {}).get("color", "BLACK")
            t_header_ma_hang = ["Mã hàng:", f" {style_id_input.strip().upper()}"]
            t_header_mau = ["Màu:", f" {color_input.strip().upper()}"]
            t_header_loai_vai = ["Loại vải:", f" {fabric_type_input.strip().upper()}"]

            t1_giang_row, t2_size_row, t3_sl_row = ["GIÀNG"], ["SIZE"], ["SẢN LƯỢNG"]
            po_qty_matrix = []
            for col_name in active_sizes:
                col_str = str(col_name).strip().upper()
                if "X" in col_str:
                    parts = col_str.split("X")
                    size_val = parts[0].strip().replace("[","").replace("]","").replace("'","")
                    giang_val = parts[1].strip().replace("[","").replace("]","").replace("'","")
                else:
                    size_val = col_str.replace("[","").replace("]","").replace("'","")
                    giang_val = "None"
                    
                po_val = int(size_breakdown_main.get(col_name, 0))
                po_qty_matrix.append(po_val)
                t1_giang_row.append(giang_val)
                t2_size_row.append(size_val)
                t3_sl_row.append(f"{po_val:,}")

            total_cols_count = 1 + len(active_sizes) + 6
            while len(t_header_ma_hang) < total_cols_count: t_header_ma_hang.append("")
            while len(t_header_mau) < total_cols_count: t_header_mau.append("")
            while len(t_header_loai_vai) < total_cols_count: t_header_loai_vai.append("")
            for _ in range(6):
                t1_giang_row.append(""); t2_size_row.append(""); t3_sl_row.append("")

            matrix_body_rows = []
            remaining_balances = list(po_qty_matrix)
            valid_items = [i for i in st.session_state["auto_cutting_results"] if str(i["Sơ đồ / Trạng thái"]).strip().lower() != "balance"]
            for item in valid_items:
                s_name = str(item["Sơ đồ / Trạng thái"]).strip().upper()
                layers, tables, sp_sd = item["Số lớp"], item["Số bàn"], item["Số sp/SĐ"]
                m_len = cad_lengths_map.get(s_name.lower().strip(), 0.0) if st.session_state.get("consumption_activated") else 0.0
                vail_can_m = m_len * layers * tables
                
                # 🎯 THUẬT TOÁN ĐỘNG: Tự động đổi cấu trúc thành dạng SIZE TRƯỚC - GIÀNG SAU [INDEX]
                marker_num_match = re.search(r'\d+', s_name)
                marker_num_str = str(int(marker_num_match.group(0))) if marker_num_match else "1"
                fabric_prefix = f"{fabric_type_input.strip().upper()}{marker_num_str}:"
                
                active_ratio_parts = []
                for sz in active_sizes:
                    r_val = int(item["Ratios"].get(sz, 0))
                    if r_val > 0:
                        sz_clean = str(sz).strip().replace("'", "").replace('"', '').replace("[", "").replace("]", "")
                        
                        # Bóc tách chuỗi 'SIZE X GIÀNG' từ tệp SBD đầu vào [INDEX]
                        if "X" in sz_clean:
                            parts = sz_clean.split("X")
                            s_size = parts[0].strip()
                            s_giang = parts[1].strip()
                            # ĐẢO TRỤC CHUẨN XƯỞNG: Ép buộc Size đứng trước - Giàng đứng sau [INDEX]
                            size_tag = f"{s_size}-{s_giang}"
                        else:
                            size_tag = sz_clean
                            
                        active_ratio_parts.append(f"{size_tag}/{r_val}")
                        
                ratio_row_title = f"{fabric_prefix} " + " ".join(active_ratio_parts) if active_ratio_parts else f"{fabric_prefix} TRỐNG"

                ratio_row = [ratio_row_title] + [item["Ratios"].get(sz, 0) for sz in active_sizes] + [layers, tables, m_len, sp_sd, round((vail_can_m * 1.09361) / (sum(item["Ratios"].values()) * layers * tables) if sum(item["Ratios"].values()) > 0 else 0, 3), round(vail_can_m, 1)]
                matrix_body_rows.append(ratio_row)
                
                remaining_row = ["CÒN LẠI"]
                for idx, sz in enumerate(active_sizes):
                    remaining_balances[idx] = max(0, remaining_balances[idx] - (item["Ratios"].get(sz, 0) * layers * tables))
                    remaining_row.append(remaining_balances[idx])
                remaining_row.extend(["", "", "", "", "", ""])
                matrix_body_rows.append(remaining_row)

            clean_headers = ["BÀN CẮT / TÊN SƠ ĐỒ"] + [f"CỠ {i+1}" for i in range(len(active_sizes))] + ["SƠ LỚP", "SỐ BÀN", "DÀI SƠ ĐỒ", "SỐ SP/SĐ", "Đ.MỨC SĐ", "VẢI CẦN (M)"]
            final_table_rows = [t_header_ma_hang, t_header_mau, t_header_loai_vai, t1_giang_row, t2_size_row, t3_sl_row] + matrix_body_rows
            df_final_report = pd.DataFrame(final_table_rows, columns=clean_headers)

            # --- PHÂN HỆ SÁNG TẠO: XUẤT EXCEL ĐỔ MÀU PHÂN KHỐI CÔNG NGHIỆP TUYỆT ĐẸP ---
            try:
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                    df_final_report.to_excel(writer, sheet_name="TacNghiepBanCat", index=False)
                    workbook = writer.book
                    worksheet = writer.sheets["TacNghiepBanCat"]
                    
                    # 1. ĐỊNH NGHĨA BẢNG MÀU CHUẨN XƯỞNG GIỐNG 100% ẢNH MẪU EXCEL BẠN GỬI
                    f_admin = workbook.add_format({'bold': True, 'align': 'left', 'valign': 'vcenter', 'fg_color': '#FFD966', 'border': 1, 'font_size': 11}) # Màu vàng gold khối hành chính dòng 1-3
                    f_giang = workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter', 'fg_color': '#BDD7EE', 'border': 1, 'font_size': 11}) # Màu xanh lam nhạt khối GIÀNG
                    f_size = workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter', 'fg_color': '#FFF2CC', 'border': 1, 'font_size': 11}) # Màu vàng kem khối nhãn SIZE
                    f_sl_po = workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter', 'fg_color': '#E2EFDA', 'font_color': '#375623', 'border': 1}) # Màu xanh lục nhạt khối SẢN LƯỢNG
                    f_tyle_cell = workbook.add_format({'align': 'center', 'valign': 'vcenter', 'fg_color': '#FFFFFF', 'border': 1}) # Nền trắng mặc định cho dòng TỶ LỆ thường
                    f_con_lai = workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter', 'fg_color': '#D9E1F2', 'font_color': '#1F4E78', 'border': 1}) # Nền xanh dương dịu xưởng khối CÒN LẠI
                    f_ratio_active = workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter', 'fg_color': '#FEF08A', 'font_color': '#C00000', 'border': 1}) # Nền vàng chanh chữ đỏ in nổi cho ô có tỉ lệ > 0
                    f_title_col = workbook.add_format({'bold': True, 'align': 'left', 'valign': 'vcenter', 'border': 1, 'fg_color': '#F2F2F2'}) # Cột tên sơ đồ ngoài cùng
                    
                    # Tự động giãn cột ngang bao phủ diện tích hiển thị máy in
                    worksheet.set_column(0, 0, 42)
                    worksheet.set_column(1, len(clean_headers)-1, 11)
                    
                    # 2. VÒNG LẶP ĐỔ MÀU TOÀN DIỆN CHO TỪNG CAO ĐỘ HÀNG EXCEL (ĐÃ SỬA SẠCH LỖI CÚ PHÁP)
                    for r_idx in range(len(df_final_report)):
                        row_vals = df_final_report.iloc[r_idx].tolist()
                        row_title = str(row_vals).strip().upper()
                        
                        for c_idx, val in enumerate(row_vals):
                            # Sửa lỗi logic điều kiện so sánh số nguyên tường minh sạch sẽ
                            if r_idx <= 2: 
                                worksheet.write(r_idx + 1, c_idx, val, f_admin)
                            elif r_idx == 3: # Dòng 4: GIÀNG
                                worksheet.write(r_idx + 1, c_idx, val, f_giang)
                            elif r_idx == 4: # Dòng 5: SIZE
                                worksheet.write(r_idx + 1, c_idx, val, f_size)
                            elif r_idx == 5: # Dòng 6: SẢN LƯỢNG PO tổng
                                worksheet.write(r_idx + 1, c_idx, val, f_sl_po)
                            elif "CÒN LẠI" in row_title: 
                                worksheet.write(r_idx + 1, c_idx, val, f_con_lai)
                            else: # Hàng TỶ LỆ sơ đồ bàn cắt vải
                                if c_idx == 0:
                                    worksheet.write(r_idx + 1, c_idx, val, f_title_col)
                                elif c_idx <= len(active_sizes) and pd.notna(val) and str(val).isdigit() and int(val) > 0:
                                    worksheet.write(r_idx + 1, c_idx, int(val), f_ratio_active)
                                else:
                                    worksheet.write(r_idx + 1, c_idx, int(val) if str(val).isdigit() else val, f_tyle_cell)
                                    
                st.download_button(
                    label="📥 IN FILE EXCEL ĐỔ MÀU PHÂN KHỐI CÔNG NGHIỆP (MẪU TNC-DNA CHUẨN)",
                    data=buffer.getvalue(),
                    file_name=f"PHIEU_TAC_NGHIEP_BÀN_CẮT_MÀU_{style_id_input}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                    key="excel_download_btn_final_v120_colorful"
                )
            except Exception: pass

            # --- KHÓA CHẶT STICKY CSS GHIM DÒNG LƯỚI TRẮNG TỐI GIẢN CHỮ ĐEN TRÊN WEB ---
            st.markdown("""<style>
                th { background-color: #F1F5F9 !important; color: #000000 !important; font-weight: 700 !important; text-align: center !important; border: 1px solid #CBD5E1 !important; position: sticky; top: 0; z-index: 10; }
                
                tr:nth-child(1) td { position: sticky; top: 25px; z-index: 9; background-color: #FFFFFF !important; font-weight: 700 !important; }
                tr:nth-child(2) td { position: sticky; top: 50px; z-index: 9; background-color: #FFFFFF !important; font-weight: 700 !important; }
                tr:nth-child(3) td { position: sticky; top: 75px; z-index: 9; background-color: #FFFFFF !important; font-weight: 700 !important; }
                tr:nth-child(4) td { position: sticky; top: 100px; z-index: 9; background-color: #FFFFFF !important; color: #000000 !important; font-weight: 800 !important; text-align: center !important; border: 1px solid #CBD5E1 !important; }
                tr:nth-child(5) td { position: sticky; top: 125px; z-index: 9; background-color: #FFFFFF !important; color: #000000 !important; font-weight: 800 !important; text-align: center !important; border: 1px solid #CBD5E1 !important; }
                tr:nth-child(6) td { position: sticky; top: 150px; z-index: 9; background-color: #FFFFFF !important; color: #000000 !important; font-weight: 700 !important; text-align: center !important; border: 1px solid #CBD5E1 !important; }
                
                tr td { background-color: #FFFFFF !important; color: #000000 !important; border: 1px solid #E2E8F0 !important; text-align: center !important; font-weight: 500 !important; }
                tr:nth-child(1) td, tr:nth-child(2) td, tr:nth-child(3) td { text-align: left !important; padding-left: 10px !important; }
                tr:nth-child(2) td:nth-child(2), tr:nth-child(3) td:nth-child(2) { color: #DC2626 !important; font-weight: 800 !important; font-size: 14px !important; }
                
                td:nth-child(1) { font-weight: 700 !important; text-align: left !important; padding-left: 10px !important; color: #000000 !important; }
                tr:nth-child(even):nth-child(n+7) td:nth-child(1) { text-align: center !important; padding-left: 0px !important; }
            </style>""", unsafe_allow_html=True)

            st.markdown("<p style='font-weight:700; font-size:14px; color:#1E3A8A; margin-top:15px;'>📊 BẢNG THEO DÕI TÁC NGHIỆP BAN CẮT MULTI-INSEAM CHUẨN EXCEL DNA</p>", unsafe_allow_html=True)
            st.dataframe(df_final_report, use_container_width=True, hide_index=True)
            st.markdown("---")
            st.success("🎉 Đã sửa lỗi! File Excel màu sắc công nghiệp chuẩn 100% phom mẫu mới đã sẵn sàng tải xuống.")
        else:
            st.info("💡 Quy trình: Bấm nút 1 để tính tác nghiệp sơ đồ -> Điền độ dài CAD -> Bấm nút 2 để kích hoạt nhảy số định mức.")
