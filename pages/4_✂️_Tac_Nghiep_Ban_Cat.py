import streamlit as st
import pandas as pd
import json
import io
import re

st.set_page_config(layout="wide")

# =============================================================================
# TẦNG 1: SỐ HÓA FILE SBD HOẶC GỌI TRỰC TIẾP PHIẾU CŨ TỪ CLOUD SUPABASE MÀN HÌNH CHÍNH
# =============================================================================
if not st.session_state.get("purchase_ready"):
    st.markdown("""<div class="card-container"><div class="card-section-header">📋 PHÂN HỆ TÁC NGHIỆP BÀN CẮT ĐA GIÀNG NÂNG CAO</div>
    <p style="color: #64748B; font-size:13px; margin:0;">Tải lên File SBD (Excel/PDF) để tính toán tác nghiệp mới, HOẶC chọn tra cứu nhanh phiếu cũ bên dưới.</p></div>""", unsafe_allow_html=True)
    
    from supabase import create_client
    url_direct = "https://supabase.co"
    key_direct = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImV3cXFvZHNmeGx2bnJ6c3lsYXd5Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3MjEwMjc1NjIsImV4cCI6MjAzNjYwMzU2Mn0.uD-n6W9k6_Z87RcoX_OlyV_1R0g_Yp_B-D3v7b0Q678"
    sb_load_client = create_client(url_direct, key_direct)
    
    history_styles = ["-- Chọn mã hàng cũ đã lưu trên Supabase --"]
    try:
        res_history = sb_load_client.table("cutting_orders_db").select("style_id", "fabric_type").execute()
        if res_history.data:
            for item in res_history.data:
                label = f"{item['style_id']} - VẢI: {item['fabric_type']}"
                if label not in history_styles: history_styles.append(label)
    except Exception: pass
    
    selected_old_record = st.selectbox("📂 Xem lại phiếu tác nghiệp cũ từ Supabase (Không cần up file):", history_styles, key="sb_outside_history_select")
    
    if selected_old_record != "-- Chọn mã hàng cũ đã lưu trên Supabase --":
        try:
            parts_str = selected_old_record.split(" - VẢI: ")
            st_id_search = str(parts_str[0]).strip()
            fb_tp_search = str(parts_str[1]).strip()
            
            res_detail = sb_load_client.table("cutting_orders_db").select("*").eq("style_id", st_id_search).eq("fabric_type", fb_tp_search).limit(1).execute()
            if res_detail.data and len(res_detail.data) > 0:
                old_data = res_detail.data[0]
                
                # 🎯 THUẬT TOÁN TỰ DỰNG LẠI MA TRẬN KÍCH CỠ TỪ FILE JSON LƯU TRỮ ĐỂ PHỤC VỤ VẼ BẢNG [INDEX]
                recovered_matrix = old_data.get("cutting_matrix_data", [])
                built_sizes_dict = {}
                
                if recovered_matrix and len(recovered_matrix) >= 6:
                    # Dòng số 5 chứa dữ liệu SIZE gốc và Dòng số 6 chứa dữ liệu SẢN LƯỢNG PO gốc [INDEX]
                    size_row_data = recovered_matrix[4]
                    qty_row_data = recovered_matrix[5]
                    
                    # Quét dọc qua từng cột kích cỡ để bốc ngược dữ liệu vào bộ nhớ đệm [INDEX]
                    for k_key, v_size in size_row_data.items():
                        if k_key != "BÀN CẮT / TÊN SƠ ĐỒ" and not any(x in k_key for x in ["SƠ LỚP", "SỐ BÀN", "DÀI SƠ ĐỒ", "SỐ SP/SĐ", "Đ.MỨC SĐ", "VẢI CẦN"]):
                            if v_size and str(v_size).strip() != "":
                                # Đọc con số sản lượng PO tương ứng đi kèm [INDEX]
                                raw_qty_str = str(qty_row_data.get(k_key, "0")).replace(",", "")
                                try: built_sizes_dict[str(v_size).strip()] = int(raw_qty_str)
                                except ValueError: built_sizes_dict[str(v_size).strip()] = 1
                
                # Nếu không tự bẻ được, nạp mảng dự phòng tránh treo ứng dụng [INDEX]
                if not built_sizes_dict:
                    built_sizes_dict = {"26 X 30": 100, "28 X 30": 100}
                
                st.session_state["sbd_parsed_data"] = {
                    "style_id": old_data.get("style_id"),
                    "total_quantity": old_data.get("total_po_qty"),
                    "size_breakdown": built_sizes_dict # Đồng bộ bộ nhớ đệm kích cỡ sạch [INDEX]
                }
                
                if recovered_matrix:
                    st.session_state["auto_cutting_results_recovered"] = recovered_matrix
                    st.session_state["fabric_type_recovered"] = old_data.get("fabric_type", "CHÍNH")
                    
                st.session_state["pur_tp_parsed_data"] = {"dummy_status": "skipped_not_needed"}
                st.session_state["purchase_ready"] = True
                st.rerun()
        except Exception: pass
        
    st.markdown("<br><p style='font-size:13px; font-weight:700; color:#475569;'>HOẶC LẬP PHIẾU TÁC NGHIỆP MỚI BẰNG FILE SBD:</p>", unsafe_allow_html=True)
    file_sbd_c2 = st.file_uploader("📋 Chọn File SBD Số Lượng Đơn Hàng (Excel/PDF)", type=["xlsx", "xls", "pdf"], key="purchase_sbd_c2_unique")

    if file_sbd_c2:
        trigger_btn_c2 = st.button("⚡ SỐ HÓA MA TRẬN SẢN LƯỢNG ĐƠN HÀNG TÁC NGHIỆP", type="primary", use_container_width=True, key="activate_sbd_only_ingest_c2")
        if trigger_btn_c2:
            with st.spinner("🚀 Hệ thống đang phân tích mảng phân bổ size phẳng từ file SBD..."):
                if "get_secure_gemini_key" in globals(): gemini_key = get_secure_gemini_key()
                else: gemini_key = st.secrets.get("GEMINI_API_KEY", "").strip()
                
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
                    
                sbd_prompt = """Bạn là một chuyên gia số hóa tài liệu ngành dệt may. Hãy phân tích bảng 'Quantity Details' trong tài liệu được cung cấp. Trả về JSON gốc sạch: {"style_id": "string", "total_quantity": integer, "size_breakdown": {"Size X Giang": integer}}"""
                if sbd_content_str: sbd_parts_payload.append(types.Part.from_text(text=sbd_content_str))
                sbd_parts_payload.append(types.Part.from_text(text=sbd_prompt))
                
                try:
                    res_sbd = client_ai.models.generate_content(model='gemini-2.5-flash', contents=sbd_parts_payload, config=types.GenerateContentConfig(response_mime_type="application/json"))
                    st.session_state["sbd_parsed_data"] = json.loads(res_sbd.text.strip().replace("```json", "").replace("```", "").strip())
                except Exception: pass
                st.session_state["pur_tp_parsed_data"] = {"dummy_status": "skipped_not_needed"}
                st.session_state["purchase_ready"] = True
                st.rerun()
else:
    sbd_data_store = st.session_state.get("sbd_parsed_data", {})
    if isinstance(sbd_data_store, dict) and sbd_data_store:
        detected_style_id = sbd_data_store.get("style_id", "UNKNOWN_STYLE")
        detected_total_po = sbd_data_store.get("total_quantity", 0)
        size_breakdown_main = sbd_data_store.get("size_breakdown", {})

        if st.button("🔄 Quay lại Màn Hình Chính / Tải file khác", type="secondary"):
            st.session_state["purchase_ready"] = False
            st.session_state["sbd_parsed_data"] = {}
            st.session_state["consumption_activated"] = False
            st.session_state["auto_cutting_results"] = None
            if "auto_cutting_results_recovered" in st.session_state: del st.session_state["auto_cutting_results_recovered"]
            st.rerun()

        st.markdown("#### 📋 KHAI BÁO THÔNG SỐ TÁC NGHIỆP ĐƠN HÀNG VÀ BÀN VẢI MULTI-INSEAM")
        input_col1, input_col2, input_col3, input_col_color = st.columns(4)
        with input_col1: style_id_input = st.text_input("🏷️ Tên mã hàng (Style ID):", value=str(detected_style_id).strip().upper())
        with input_col2: po_qty_input = st.number_input("📦 Số lượng đơn hàng (PO Pcs):", value=int(detected_total_po), step=100)
        with input_col3: consumption_input = st.number_input("🎯 Định mức tài liệu đề xuất (Yds/Pcs):", value=1.140, step=0.001, format="%.3f")
        with input_col_color: color_input = st.text_input("🎨 Tự gõ Màu vải:", value="BLACK")

        input_col4, input_col5, input_col6 = st.columns(3)
        with input_col4: max_table_length = st.number_input("📏 Chiều gia tối đa bàn vải (Meters):", value=12.00, step=1.0)
        
        # 🎯 ĐỘNG HÓA Ô CHỌN LOẠI VẢI: Cho phép chuyển đổi nhanh Chính/Lót/Keo để xem/sửa
        default_fab = st.session_state.get("fabric_type_recovered", "CHÍNH")
        fabric_type_input = st.selectbox("🧵 Loại vải đang tác nghiệp:", ["CHÍNH", "LÓT", "KEO", "PHỐI"], index=["CHÍNH", "LÓT", "KEO", "PHỐI"].index(default_fab))
        
        with input_col6: cuttable_width_inch = st.number_input("📐 KHỔ CẮT (Khổ vải đi sơ đồ - Inches):", value=56.00, step=0.50, format="%.2f")
        cad_paste_zone = st.text_area("Sau khi xem cấu trúc phối size phía dưới, hãy đi sơ đồ trên máy CAD rồi copy dán kết quả [Tên sơ đồ + Chiều dài mét] vào đây:", placeholder="Ví dụ dán bảng từ Excel CAD:\n5844-c01 1.05\n5844-c02 10", height=90, key="cad_bulk_paste_c2")
        
        # 🎯 KỸ THUẬT AUTO-QUERY: Nếu người dùng đổi loại vải, tự động check nhanh trên Supabase có dữ liệu cũ chưa
        if fabric_type_input != st.session_state.get("last_checked_fabric"):
            st.session_state["last_checked_fabric"] = fabric_type_input
            try:
                from supabase import create_client
                url_direct = "https://ewqqodsfvlvnrzsylawy.supabase.co"
                key_direct = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImV3cXFvZHNmdmx2bnJ6c3lsYXd5Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzUxMTkyOTAsImV4cCI6MjA5MDY5NTI5MH0.BWPxOsyswBT5CLrZgluRC1F2x5EpU06oexUFyakGhyc"
                sb_client_check = create_client(url_direct, key_direct)
                res_check = sb_client_check.table("cutting_orders_db").select("*").eq("style_id", style_id_input).eq("fabric_type", fabric_type_input).limit(1).execute()
                if res_check.data:
                    st.session_state["auto_cutting_results_recovered"] = res_check.data[0]["cutting_matrix_data"]
                    st.session_state["auto_cutting_results"] = None
                    st.rerun()
                else:
                    if "auto_cutting_results_recovered" in st.session_state: del st.session_state["auto_cutting_results_recovered"]
            except Exception: pass

        active_sizes = [str(k) for k, v in size_breakdown_main.items() if int(v) > 0]
        if not active_sizes: active_sizes = ["S", "M", "L", "XL", "2XL", "3XL"]
        
        btn_col1, btn_col2 = st.columns(2)
        with btn_col1: trigger_auto_cutting = st.button("⚡ 1. KÍCH HOẠT TÍNH TÁC NGHIỆP SƠ ĐỒ (AI GIẢI MA TRẬN TỶ LỆ)", type="primary", use_container_width=True, key="c2_normal_cut_btn")
        with btn_col2: trigger_consumption = st.button("🤖 2. KÍCH HOẠT NHẢY SỐ ĐỊNH MỨC VÀ ĐỐI CHIẾU CAD", type="secondary", use_container_width=True, key="c2_consumption_btn")
        if trigger_auto_cutting:
            with st.spinner("🤖 AI đang tối ưu: Nâng số lớp sơ đồ chính, dồn cụm tỉ lệ lớn và vét đuôi khúc..."):
                if "get_secure_gemini_key" in globals(): gemini_key = get_secure_gemini_key()
                else: gemini_key = st.secrets.get("GEMINI_API_KEY", "").strip()
                
                from google import genai
                from google.genai import types
                client_ai = genai.Client(api_key=gemini_key)
                
                ai_cutting_prompt = f"""Bạn là chuyên gia lập kế hoạch bàn cắt công nghiệp dệt may đại tài. Hãy tính toán phân bổ sơ đồ cho đơn hàng này.
                DANH SÁCH SIZE GỐC BẮT BUỘC SỬ DỤNG LÀM KEY: {json.dumps(list(size_breakdown_main.keys()))}
                SẢN LƯỢNG ĐƠN HÀNG GỐC CẦN TRIỆT TIÊU: {json.dumps(size_breakdown_main)}
                THÔNG SỐ FORM: Max Length {max_table_length}m, DM {consumption_input}yd, Width {cuttable_width_inch}inch, Fabric {fabric_type_input}
                QUY TẮC PHỐI LẬP SƠ ĐỒ: Bàn đầu tự động đẩy Số Lớp lên mức cao (100-150 lớp) đi kèm sơ đồ gộp có tổng tỷ lệ lớn (Tỉ lệ 2,3,4 quần) sao cho chiều dài đạt sát trần {max_table_length}m. Sơ đồ cuối cùng bẻ về tỉ lệ 1 quần số lớp ít để vét sạch lượng dư CÒN LẠI về 0. Trả về kết quả DUY NHẤT dưới dạng mảng JSON gốc sạch: 
                [ {{"Sơ đồ / Trạng thái": "c01", "Ratios": {{ "Key_Gốc": 2 }}, "Số lớp": 120, "Số bàn": 1, "Số sp/SĐ": 2}} ]"""
                
                try:
                    res_cutting = client_ai.models.generate_content(model='gemini-2.5-flash', contents=[ai_cutting_prompt])
                    st.session_state["auto_cutting_results"] = json.loads(res_cutting.text.strip().replace("```json", "").replace("```", "").strip())
                    if "auto_cutting_results_recovered" in st.session_state: del st.session_state["auto_cutting_results_recovered"]
                    st.success("🎯 AI đã nâng số lớp và tối ưu tổ hợp tỷ lệ gộp lớn thành công!")
                except Exception:
                    st.session_state["auto_cutting_results"] = [{"Sơ đồ / Trạng thái": f"c{str(i+1).zfill(2)}", "Ratios": {s: (1 if s == sz else 0) for s in active_sizes}, "Số lớp": 50, "Số bàn": 1, "Số sp/SĐ": 1} for i, sz in enumerate(active_sizes)]

        if trigger_consumption:
            st.session_state["consumption_activated"] = True
            st.rerun()
        cutting_source_data = None
        if "auto_cutting_results_recovered" in st.session_state and st.session_state["auto_cutting_results_recovered"]:
            cutting_source_data = st.session_state["auto_cutting_results_recovered"]
        elif st.session_state.get("auto_cutting_results") is not None:
            cutting_source_data = st.session_state["auto_cutting_results"]

        if cutting_source_data is not None:
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
            valid_items = [i for i in cutting_source_data if str(i.get("Sơ đồ / Trạng thái", "")).strip().lower() != "balance"] if isinstance(cutting_source_data, list) else []

            for item in valid_items:
                s_name = str(item.get("Sơ đồ / Trạng thái", "")).strip().upper()
                layers, tables, sp_sd = int(item.get("Số lớp", 50)), int(item.get("Số bàn", 1)), int(item.get("Số sp/SĐ", 1))
                m_len = cad_lengths_map.get(s_name.lower().strip(), 0.0) if st.session_state.get("consumption_activated") else 0.0
                vail_can_m = m_len * layers * tables
                
                marker_num_match = re.search(r'\d+', s_name)
                marker_num_str = str(int(marker_num_match.group(0))) if marker_num_match else "1"
                fabric_prefix = f"{fabric_type_input.strip().upper()}{marker_num_str}:"
                
                active_ratio_parts = []
                ratios_dict = item.get("Ratios", {})
                for sz in active_sizes:
                    r_val = int(ratios_dict.get(sz, 0))
                    if r_val > 0:
                        sz_clean = str(sz).strip().replace("'", "").replace('"', '').replace("[", "").replace("]", "")
                        if "X" in sz_clean:
                            parts = sz_clean.split("X")
                            size_tag = f"{parts[0].strip()}-{parts[1].strip()}"
                        else: size_tag = sz_clean
                        active_ratio_parts.append(f"{size_tag}/{r_val}")
                        
                ratio_row_title = f"{fabric_prefix} " + " ".join(active_ratio_parts) if active_ratio_parts else f"{fabric_prefix} TRỐNG"
                ratio_row = [ratio_row_title] + [int(ratios_dict.get(sz, 0)) for sz in active_sizes] + [layers, tables, m_len, sp_sd, round((vail_can_m * 1.09361) / (sum(ratios_dict.values()) * layers * tables) if sum(ratios_dict.values()) > 0 else 0, 3), round(vail_can_m, 1)]
                matrix_body_rows.append(ratio_row)
                
                remaining_row = ["CÒN LẠI"]
                for idx, sz in enumerate(active_sizes):
                    remaining_balances[idx] = max(0, remaining_balances[idx] - (int(ratios_dict.get(sz, 0)) * layers * tables))
                    remaining_row.append(remaining_balances[idx])
                remaining_row.extend(["", "", "", "", "", ""])
                matrix_body_rows.append(remaining_row)

            clean_headers = ["BÀN CẮT / TÊN SƠ ĐỒ"] + [f"CỠ {i+1}" for i in range(len(active_sizes))] + ["SƠ LỚP", "SỐ BÀN", "DÀI SƠ ĐỒ", "SỐ SP/SĐ", "Đ.MỨC SĐ", "VẢI CẦN (M)"]
            final_table_rows = [t_header_ma_hang, t_header_mau, t_header_loai_vai, t1_giang_row, t2_size_row, t3_sl_row] + matrix_body_rows
            df_final_report = pd.DataFrame(final_table_rows, columns=clean_headers)
            # --- 🎯 PHÂN HỆ ĐA SHEET EXCEL ĐẸP MẮT THEO ĐÚNG TIÊU CHUẨN ĐIỀU KIỆN ---
            excel_generated_status = False
            buffer = io.BytesIO()
            
            # CHỈ CHO PHÉP XUẤT EXCEL KHI ĐÃ NHẢY SỐ ĐỊNH MỨC CAD (NÚT 2) HOẶC ĐANG GỌI MÃ CŨ TỪ KHO
            if st.session_state.get("consumption_activated") or ("auto_cutting_results_recovered" in st.session_state):
                try:
                    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                        from supabase import create_client
                        sb_ex_client = create_client("https://supabase.co", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImV3cXFvZHNmeGx2bnJ6c3lsYXd5Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3MjEwMjc1NjIsImV4cCI6MjAzNjYwMzU2Mn0.uD-n6W9k6_Z87RcoX_OlyV_1R0g_Yp_B-D3v7b0Q678")
                        res_all_fabs = sb_ex_client.table("cutting_orders_db").select("*").eq("style_id", style_id_input).execute()
                        
                        if res_all_fabs.data and len(res_all_fabs.data) > 0:
                            for r_record in res_all_fabs.data:
                                f_type_name = str(r_record.get("fabric_type", "CHÍNH")).upper()
                                raw_matrix = r_record.get("cutting_matrix_data", [])
                                if raw_matrix:
                                    df_sheet_temp = pd.DataFrame(raw_matrix)
                                    df_sheet_temp.to_excel(writer, sheet_name=f"VAI {f_type_name}", index=False)
                                    workbook = writer.book; worksheet = writer.sheets[f"VAI {f_type_name}"]
                                    
                                    f_admin = workbook.add_format({'bold': True, 'align': 'left', 'valign': 'vcenter', 'fg_color': '#FFD966', 'border': 1, 'font_size': 11})
                                    f_giang = workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter', 'fg_color': '#BDD7EE', 'border': 1, 'font_size': 11})
                                    f_size = workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter', 'fg_color': '#FFF2CC', 'border': 1, 'font_size': 11})
                                    f_sl_po = workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter', 'fg_color': '#E2EFDA', 'font_color': '#375623', 'border': 1})
                                    f_tyle_cell = workbook.add_format({'align': 'center', 'valign': 'vcenter', 'fg_color': '#FFFFFF', 'border': 1})
                                    f_con_lai = workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter', 'fg_color': '#D9E1F2', 'font_color': '#1F4E78', 'border': 1})
                                    f_ratio_active = workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter', 'fg_color': '#FEF08A', 'font_color': '#C00000', 'border': 1})
                                    f_title_col = workbook.add_format({'bold': True, 'align': 'left', 'valign': 'vcenter', 'border': 1, 'fg_color': '#F2F2F2'})
                                    
                                    worksheet.set_column(0, 0, 42)
                                    worksheet.set_column(1, 25, 11)
                                    
                                    for r_i in range(len(df_sheet_temp)):
                                        r_vals = df_sheet_temp.iloc[r_i].tolist()
                                        r_title = str(r_vals).strip().upper()
                                        for c_i, v_val in enumerate(r_vals):
                                            if str(v_val) == "None" or pd.isna(v_val): v_val = ""
                                            if r_i <= 2: worksheet.write(r_i + 1, c_i, v_val, f_admin)
                                            elif r_i == 3: worksheet.write(r_i + 1, c_i, v_val, f_giang)
                                            elif r_i == 4: worksheet.write(r_i + 1, c_i, v_val, f_size)
                                            elif r_i == 5: worksheet.write(r_i + 1, c_i, v_val, f_sl_po)
                                            elif "CÒN LẠI" in r_title: worksheet.write(r_i + 1, c_i, v_val, f_con_lai)
                                            else:
                                                if c_i == 0: worksheet.write(r_i + 1, c_i, v_val, f_title_col)
                                                elif c_i <= len(active_sizes) and str(v_val).replace('.','',1).isdigit() and int(float(v_val)) > 0:
                                                    worksheet.write(r_i + 1, c_i, int(float(v_val)), f_ratio_active)
                                                else: worksheet.write(r_i + 1, c_i, int(float(v_val)) if str(v_val).replace('.','',1).isdigit() else v_val, f_tyle_cell)
                            excel_generated_status = True
                        else:
                            df_final_report.to_excel(writer, sheet_name=f"VAI {fabric_type_input}", index=False)
                            excel_generated_status = True
                except Exception: pass

            if excel_generated_status:
                st.download_button(
                    label="📥 XUẤT 1 FILE EXCEL ĐỒNG BỘ ĐỦ TẤT CẢ CÁC SHEET LOẠI VẢI (CHÍNH-LÓT-KEO)",
                    data=buffer.getvalue(),
                    file_name=f"PHIEU_TAC_NGHIEP_TONG_HOP_{style_id_input}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                    key="excel_multi_sheet_btn_final_v5"
                )
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
            </style>""", unsafe_allow_html=True)

            st.markdown("<p style='font-weight:700; font-size:14px; color:#1E3A8A; margin-top:15px;'>📊 BẢNG THEO DÕI TÁC NGHIỆP BAN CẮT MULTI-INSEAM CHUẨN EXCEL DNA</p>", unsafe_allow_html=True)
            st.dataframe(df_final_report, use_container_width=True, hide_index=True)
            
            # 🎯 KỸ THUẬT CHẶT QUY TRÌNH: CHỈ HIỆN NÚT LƯU KHI ĐÃ QUA BƯỚC CAD HOẶC ĐANG TRUY VẤN MÃ CŨ ĐỂ CHỈNH SỬA
            if st.session_state.get("consumption_activated") or ("auto_cutting_results_recovered" in st.session_state):
                st.markdown("---")
                st.markdown(f"<p style='font-weight:700; font-size:14px; color:#1E3A8A;'>💾 LƯU TRỮ VÀ CẬP NHẬT TÁC NGHIỆP VẢI {fabric_type_input.upper()}</p>", unsafe_allow_html=True)
                trigger_save_supabase = st.button(f"💾 KÍCH HOẠT LƯU/CẬP NHẬT PHIẾU VẢI {fabric_type_input.upper()} VÀO KHO CLOUD", type="primary", use_container_width=True, key="save_to_supabase_btn_c2")
                
                if trigger_save_supabase:
                    with st.spinner(f"🚀 Hệ thống đang đồng bộ ghi đè vải {fabric_type_input} lên kho dữ liệu Supabase..."):
                        df_clean_string = df_final_report.astype(str)
                        matrix_json_string = df_clean_string.to_json(orient="records")
                        
                        supabase_payload = {
                            "style_id": str(style_id_input).strip().upper(),
                            "color": str(color_input).strip().upper(),
                            "fabric_type": str(fabric_type_input).strip().upper(),
                            "total_po_qty": int(po_qty_input),
                            "proposal_yield": float(consumption_input),
                            "max_table_len": float(max_table_length),
                            "cuttable_width": float(cuttable_width_inch),
                            "cutting_matrix_data": json.loads(matrix_json_string)
                        }
                        try:
                            from supabase import create_client
                            supabase_client = create_client("https://supabase.co", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImV3cXFvZHNmeGx2bnJ6c3lsYXd5Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3MjEwMjc1NjIsImV4cCI6MjAzNjYwMzU2Mn0.uD-n6W9k6_Z87RcoX_OlyV_1R0g_Yp_B-D3v7b0Q678")
                            
                            # Dùng lệnh upsert để tự động ghi đè bản sửa đổi mới lên kho dữ liệu cũ của mã hàng
                            response_db = supabase_client.table("cutting_orders_db").upsert(supabase_payload, on_conflict="style_id,fabric_type").execute()
                            st.success(f"🎉 Đã lưu và cập nhật thành công dữ liệu mảng phẳng vải {fabric_type_input} của mã hàng {style_id_input} vào kho lưu trữ!")
                        except Exception as e: 
                            st.error(f"⚠️ Lỗi kết nối Supabase: {str(e)}")
            st.markdown("---")
            st.success("🎉 Quy trình điều độ ban cắt thông minh đa loại vải ghim trần đã đồng bộ hoàn tất!")
        else:
            st.info("💡 Quy trình: Lập tác nghiệp từng loại vải ➡️ Ấn Lưu ➡️ Chuyển loại vải khác làm tiếp ➡️ Ấn Xuất Excel gộp chung.")
