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
                if file_sbd_c2.name.lower().endswith(('.xlsx', '.xls')):
                    try:
                        excel_data = pd.read_excel(io.BytesIO(sbd_bytes), sheet_name=None)
                        for sheet_name, df_sheet in excel_data.items():
                            sbd_content_str += f"\n--- SHEET: {sheet_name} ---\n{df_sheet.fillna('').to_csv(index=False)}"
                    except Exception: 
                        pass
                elif file_sbd_c2.name.lower().endswith('.pdf'):
                    sbd_parts_payload.append(types.Part.from_bytes(data=sbd_bytes, mime_type='application/pdf'))
                    
                # NÂNG CẤP PROMPT ÉP AI SỐ HÓA MA TRẬN PHỐI GIÀNG CHỨA KÝ TỰ 'X' CỦA BIỂU MẪU ĐƠN HÀNG
                sbd_prompt = """
                Bạn là một chuyên gia số hóa tài liệu ngành dệt may. Hãy phân tích bảng 'Quantity Details' trong tài liệu được cung cấp.
                1. Trích xuất mã hàng nằm ở mục 'Key Item' hoặc 'Style' (Ví dụ: '6082').
                2. Trích xuất tổng sản lượng ở mục 'Units' hoặc 'Total' (Ví dụ: 2500).
                3. Trích xuất toàn bộ danh sách kích cỡ nằm ở hàng tiêu đề của bảng số lượng (Ví dụ: '26 X 30', '28 X 30', '29 X 32').
                
                QUY TẮC ÉP KIỂU MA TRẬN SIZE BẮT BUỘC:
                - Đối với các tiêu đề cột có dạng nối liền như '26 X 30' hoặc '30 X 32', bạn PHẢI giữ nguyên cấu trúc chuỗi văn bản gốc này làm Tên Khóa (Key Name) của mảng 'size_breakdown'. 
                - Hãy nhặt con số sản lượng thực tế nằm ngay dưới cột cỡ đó (Ví dụ dưới cột '26 X 30' có số '88', dưới cột '28 X 30' có số '156') để điền giá trị. Bỏ qua các hàng trống hoặc các cột tổng.
                
                Trả về kết quả DUY NHẤT dưới dạng cấu trúc JSON gốc sạch sẽ, không kèm từ giải thích rác:
                {
                    "style_id": "6082",
                    "total_quantity": 2500,
                    "size_breakdown": {
                        "26 X 30": 88,
                        "28 X 30": 156,
                        "29 X 30": 150,
                        "29 X 32": 122
                    }
                }
                """
                if sbd_content_str: 
                    sbd_parts_payload.append(types.Part.from_text(text=sbd_content_str))
                sbd_parts_payload.append(types.Part.from_text(text=sbd_prompt))
                
                try:
                    res_sbd = client_ai.models.generate_content(
                        model='gemini-2.5-flash', 
                        contents=sbd_parts_payload, 
                        config=types.GenerateContentConfig(response_mime_type="application/json")
                    )
                    st.session_state["sbd_parsed_data"] = json.loads(res_sbd.text.strip().replace("```json", "").replace("```", "").strip())
                except Exception: 
                    pass
                
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
            with st.spinner("🤖 AI đang phân tích dữ liệu SBD gốc, dồn cụm ma trận theo cấu trúc Kim tự tháp ngược..."):
                if "get_secure_gemini_key" in globals(): 
                    gemini_key = get_secure_gemini_key()
                else: 
                    gemini_key = st.secrets.get("GEMINI_API_KEY", "").strip()
                
                from google import genai
                from google.genai import types
                
                client_ai = genai.Client(api_key=gemini_key)
                
                # NÂNG CẤP PROMPT ÉP BUỘC ĐỒNG BỘ KHÓA KEY SIZE GỐC VÀ DỒN CỤM TỶ LỆ LỚN
                ai_cutting_prompt = f"""
                Bạn là chuyên gia lập kế hoạch bàn cắt công nghiệp dệt may đại tài. 
                Hãy tính toán tổ hợp sơ đồ phối size dồn cụm cho đơn hàng này theo đúng nguyên lý sản xuất thực tế.

                DANH SÁCH KHÓA SIZE GỐC BẮT BUỘC SỬ DỤNG: {json.dumps(list(size_breakdown_main.keys()))}
                MA TRẬN SẢN LƯỢNG PO THỰC TẾ: {json.dumps(size_breakdown_main)}
                THÔNG SỐ GIỚI HẠN XƯỞNG:
                - Chiều dài gia tối đa bàn vải cho phép: {max_table_length} Mét
                - Định mức tài liệu đề xuất: {consumption_input} Yds/Pcs
                - Khổ vải đi sơ đồ: {cuttable_width_inch} Inches
                - Loại vải tác nghiệp: {fabric_type_input}

                QUY TẮC PHỐI TỶ LỆ ÉP BUỘC (CẤU TRÚC KIM TỰ THÁP NGƯỢC):
                1. ĐỒNG BỘ KHÓA KEY: Khi viết mảng "Ratios", bạn PHẢI sử dụng chính xác 100% nguyên văn chuỗi ký tự nằm trong danh sách khóa size gốc được cung cấp ở trên (Ví dụ nếu khóa gốc là "['26']" hoặc "SIZE: 26" thì phải viết nguyên văn như vậy, TUYỆT ĐỐI không được tự ý làm sạch thành "26").
                2. DỒN CỤM TỶ LỆ LỚN (BÀN ĐẦU): Gom các size sát cạnh nhau có sản lượng lớn lại đi chung sơ đồ gộp có tổng tỷ lệ lớn (Ví dụ tỉ lệ: 2, 3, 4 quần/size) sao cho chiều dài đạt sát trần {max_table_length}m nhằm giải quyết nhanh PO.
                3. SƠ ĐỒ VÉT VUỐT ĐUÔI (BÀN CUỐI): Trừ lùi sản lượng lũy tiến. Ở các bàn cuối cùng, bẻ nhỏ sơ đồ lại thành sơ đồ vét chỉ chứa tỷ lệ 1 quần cho các cỡ nhỏ hoặc cỡ biên mồ côi còn sót lại để triệt tiêu số lượng 'CÒN LẠI' về đúng số 0.

                Trả về duy nhất mảng JSON gốc sạch sẽ, không giải thích văn bản rác:
                [
                    {{"Sơ đồ / Trạng thái": "c01", "Ratios": {{ "Điền_Đúng_Khóa_Size_Gốc_1": 2, "Điền_Đúng_Khóa_Size_Gốc_2": 3 }}, "Số lớp": 120, "Số bàn": 1, "Số sp/SĐ": 5}}
                ]
                """
                try:
                    res_cutting = client_ai.models.generate_content(
                        model='gemini-2.5-flash', 
                        contents=[ai_cutting_prompt]
                    )
                    st.session_state["auto_cutting_results"] = json.loads(res_cutting.text.strip().replace("```json", "").replace("```", "").strip())
                    st.success("🎯 AI đã đồng bộ khóa mã size và tối ưu tổ hợp Kim tự tháp ngược thành công!")
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

            t_header_ma_hang = ["Mã hàng:", f" {style_id_input.strip().upper()}"]
            t_header_mau = ["Màu:", f" {color_input.strip().upper()}"]
            t_header_loai_vai = ["Loại vải:", f" {fabric_type_input.strip().upper()}"]

            t1_giang_row, t2_size_row, t3_sl_row = ["GIÀNG"], ["SIZE"], ["SẢN LƯỢNG"]
            po_qty_matrix = []
            for col_name in active_sizes:
                col_str = str(col_name).strip().replace("'", "").replace('"', '').replace("(", "").replace(")", "")
                giang_val, size_val = "None", col_str
                parts = re.split(r'[\sXx\-\/:]+', col_str)
                parts_clean = [p.strip() for p in parts if p.strip()]
                if len(parts_clean) >= 2: giang_val, size_val = parts_clean, parts_clean
                elif len(parts_clean) == 1: size_val = parts_clean
                po_val = int(size_breakdown_main.get(col_name, 0))
                po_qty_matrix.append(po_val)
                t1_giang_row.append(f"{giang_val}" if giang_val != "None" else "None")
                t2_size_row.append(f"{size_val}")
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
                layers = int(item.get("Số lớp", 50))
                tables = int(item.get("Số bàn", 1))
                sp_sd = int(item.get("Số sp/SĐ", 1))
                
                m_len = cad_lengths_map.get(s_name.lower().strip(), 0.0) if st.session_state.get("consumption_activated") else 0.0
                vail_can_m = m_len * layers * tables
                total_ratios_sum = sum(item["Ratios"].values())
                pcs_cut_marker = total_ratios_sum * layers * tables
                dm_sd = (vail_can_m * 1.09361) / pcs_cut_marker if pcs_cut_marker > 0 else 0.0
                
                # 🎯 BẺ CHUỖI TÊN BÀN CẮT THƯƠNG MẠI
                marker_num_match = re.search(r'\d+', s_name)
                marker_num_str = str(int(marker_num_match.group(0))) if marker_num_match else "1"
                fabric_prefix = f"{fabric_type_input.strip().upper()}{marker_num_str}:"
                
                active_ratio_parts = []
                for sz in active_sizes:
                    sz_clean = str(sz).strip().replace("'", "").replace('"', '').replace("SIZE:", "").strip()
                    r_val = int(item["Ratios"].get(sz, 0))
                    if r_val > 0: active_ratio_parts.append(f"{sz_clean}/{r_val}")
                ratio_row_title = f"{fabric_prefix} " + " ".join(active_ratio_parts) if active_ratio_parts else f"{fabric_prefix} TRỐNG"

                ratio_row = [ratio_row_title] + [int(item["Ratios"].get(sz, 0)) for sz in active_sizes] + [layers, tables, m_len, sp_sd, round(dm_sd, 3), round(vail_can_m, 1)]
                matrix_body_rows.append(ratio_row)
                
                # B. DÒNG CÒN LẠI LŨY TIẾN TRỪ LÙI SẢN LƯỢNG
                remaining_row = ["CÒN LẠI"]
                for idx, sz in enumerate(active_sizes):
                    current_ratio = int(item["Ratios"].get(sz, 0))
                    allocated_pcs = current_ratio * layers * tables
                    remaining_balances[idx] = max(0, remaining_balances[idx] - allocated_pcs)
                    remaining_row.append(remaining_balances[idx])
                remaining_row.extend(["", "", "", "", "", ""])
                matrix_body_rows.append(remaining_row)

            clean_headers = ["BÀN CẮT / TÊN SƠ ĐỒ"] + [f"CỠ {i+1}" for i in range(len(active_sizes))] + ["SƠ LỚP", "SỐ BÀN", "DÀI SƠ ĐỒ", "SỐ SP/SĐ", "Đ.MỨC SĐ", "VẢI CẦN (M)"]
            final_table_rows = [t_header_ma_hang, t_header_mau, t_header_loai_vai, t1_giang_row, t2_size_row, t3_sl_row] + matrix_body_rows
            df_final_report = pd.DataFrame(final_table_rows, columns=clean_headers)
            # 🎯 THUẬT TOÁN ĐỔI MÀU: Nền vàng chanh chữ đen đậm nổi bật cho ô tỷ lệ nhảy số [INDEX]
            # 🎯 THUẬT TOÁN ĐỔI MÀU: Nền vàng chanh chữ đen đậm nổi bật cho ô tỷ lệ nhảy số [INDEX]
            def highlight_ratios(x):
                color_df = pd.DataFrame('', index=x.index, columns=x.columns)
                num_size_cols = len(active_sizes)
                
                for r in range(len(x)):
                    if r < 6: continue
                    if str(x.iloc[r, 0]).strip().upper() == "CÒN LẠI": continue
                    
                    for c in range(1, len(x.columns)):
                        if c <= num_size_cols:
                            val = x.iloc[r, c]
                            try:
                                # SỬA LỖI TẠI ĐÂY: Ép kiểu sang số thực để nhận diện chính xác giá trị tỉ lệ > 0 [INDEX]
                                if pd.notna(val) and float(val) > 0:
                                    color_df.iloc[r, c] = 'background-color: #FDE047 !important; color: #000000 !important; font-weight: 800 !important; border: 1px solid #EAB308 !important; text-align: center !important;'
                            except (ValueError, TypeError): pass
                return color_df

            styled_report_df = df_final_report.style.apply(highlight_ratios, axis=None)

            # --- KHỐI KẾT XUẤT FILE EXCEL ĐÓNG KHUNG CHUẨN THƯƠNG MẠI IN ẤN ---
            try:
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                    df_final_report.to_excel(writer, sheet_name="TacNghiepBanCat", index=False)
                    
                    workbook  = writer.book
                    worksheet = writer.sheets["TacNghiepBanCat"]
                    
                    # Thiết lập các định dạng ô lưới chuẩn xưởng
                    fmt_header = workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter', 'fg_color': '#D1FAE5', 'font_color': '#065F46', 'border': 1})
                    fmt_giang = workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter', 'fg_color': '#CBD5E1', 'border': 1})
                    fmt_size = workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter', 'fg_color': '#FDE047', 'border': 1})
                    fmt_sl = workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter', 'fg_color': '#E2E8F0', 'border': 1})
                    fmt_ratio_active = workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter', 'fg_color': '#FEF08A', 'font_color': '#991B1B', 'border': 1})
                    fmt_normal = workbook.add_format({'align': 'center', 'valign': 'vcenter', 'border': 1})
                    fmt_con_lai = workbook.add_format({'align': 'center', 'valign': 'vcenter', 'fg_color': '#EFF6FF', 'font_color': '#1E40AF', 'border': 1})
                    
                    # Khóa độ rộng cột tự động
                    worksheet.set_column(0, 0, 35)
                    worksheet.set_column(1, len(clean_headers)-1, 12)
                    
                    # Đóng khung tô màu định dạng từng hàng dữ liệu trong Excel
                    for r_idx in range(len(df_final_report)):
                        row_title = str(df_final_report.iloc[r_idx, 0]).strip().upper()
                        for c_idx in range(len(df_final_report.columns)):
                            val = df_final_report.iloc[r_idx, c_idx]
                            
                            if r_idx == 0: worksheet.write(r_idx + 1, c_idx, val, fmt_giang)
                            elif r_idx == 1: worksheet.write(r_idx + 1, c_idx, val, fmt_size)
                            elif r_idx == 2: worksheet.write(r_idx + 1, c_idx, val, fmt_sl)
                            elif "CÒN LẠI" in row_title: worksheet.write(r_idx + 1, c_idx, val, fmt_con_lai)
                            else:
                                if c_idx > 0 and c_idx <= len(active_sizes) and pd.notna(val) and str(val).replace('.','',1).isdigit() and float(val) > 0:
                                    worksheet.write(r_idx + 1, c_idx, val, fmt_ratio_active)
                                else:
                                    worksheet.write(r_idx + 1, c_idx, val, fmt_normal)
                                    
                st.download_button(
                    label="📥 IN FILE EXCEL TÁC NGHIỆP SẢN XUẤT ĐÓNG KHUNG CHUẨN",
                    data=buffer.getvalue(),
                    file_name=f"PHIEU_TAC_NGHIEP_BAN_CAT_{style_id_input}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                    key="excel_download_btn_final_v109"
                )
            except Exception: pass

            # --- KHÓA CHẶT CSS ĐƯỜNG BIÊN EXCEL SẠCH SẼ KHÔNG CHE KHUẤT CHỮ ---
            st.markdown("""<style>
                th { background-color: #D1FAE5 !important; color: #065F46 !important; font-weight: 700 !important; text-align: center !important; border: 1px solid #A7F3D0 !important; position: sticky; top: 0; z-index: 10; }
                
                tr:nth-child(1) td { position: sticky; top: 25px; z-index: 9; background-color: #F1F5F9 !important; font-weight: 700 !important; }
                tr:nth-child(2) td { position: sticky; top: 55px; z-index: 9; background-color: #F1F5F9 !important; font-weight: 700 !important; }
                tr:nth-child(3) td { position: sticky; top: 85px; z-index: 9; background-color: #F1F5F9 !important; font-weight: 700 !important; }
                tr:nth-child(4) td { position: sticky; top: 115px; z-index: 9; background-color: #CBD5E1 !important; color: #000000 !important; font-weight: 800 !important; text-align: center !important; border: 1px solid #94A3B8 !important; }
                tr:nth-child(5) td { position: sticky; top: 145px; z-index: 9; background-color: #FEF08A !important; color: #991B1B !important; font-weight: 800 !important; text-align: center !important; border: 1px solid #FDE047 !important; }
                tr:nth-child(6) td { position: sticky; top: 150px; z-index: 9; background-color: #F1F5F9 !important; color: #1E293B !important; font-weight: 700 !important; text-align: center !important; border: 1px solid #CBD5E1 !important; }
                
                tr:nth-child(1) td, tr:nth-child(2) td, tr:nth-child(3) td { text-align: left !important; border: 1px solid #E2E8F0 !important; color: #000000 !important; }
                tr:nth-child(2) td:nth-child(2), tr:nth-child(3) td:nth-child(2) { color: #DC2626 !important; font-weight: 800 !important; font-size: 14px !important; }
                
                /* Hàng CÒN LẠI nhuộm màu nền xanh lam nhạt, chữ xanh đậm rõ nét */
                tr:nth-child(even):nth-child(n+7) td { background-color: #EFF6FF !important; color: #1E40AF !important; font-weight: 600 !important; border: 1px solid #BFDBFE !important; text-align: center !important; }
                
                /* Định dạng các ô tỷ lệ bằng 0 hoặc trống ở hàng thường giữ màu nền trắng chữ xám nhẹ */
                tr:nth-child(odd):nth-child(n+7) td { background-color: #FFFFFF !important; color: #475569 !important; text-align: center !important; border: 1px solid #E2E8F0 !important; }
                
                td:nth-child(1) { font-weight: 700 !important; text-align: left !important; padding-left: 10px !important; color: #000000 !important; }
                tr:nth-child(even):nth-child(n+7) td:nth-child(1) { text-align: center !important; padding-left: 0px !important; }
            </style>""", unsafe_allow_html=True)

            st.markdown("<p style='font-weight:700; font-size:14px; color:#1E3A8A; margin-top:15px;'>📊 BẢNG THEO DÕI TÁC NGHIỆP BAN CẮT MULTI-INSEAM CHUẨN EXCEL DNA</p>", unsafe_allow_html=True)
            st.dataframe(styled_report_df, use_container_width=True, hide_index=True)
            st.markdown("---")
            st.success("🎉 Giao diện ma trận màu vàng rực rỡ và nút bấm xuất file Excel đóng khung in ấn đã sẵn sàng!")
        else:
            st.info("💡 Quy trình: Bấm nút 1 để tính tác nghiệp sơ đồ -> Điền độ dài CAD -> Bấm nút 2 để kích hoạt nhảy số định mức.")
