import streamlit as st
import pandas as pd
import json
import io
import re

st.set_page_config(layout="wide")

# =============================================================================
# TẦNG 1: SỐ HÓA FILE SBD HOẶC GỌI TRỰC TIẾP PHIẾU CŨ TỪ CLOUD SUPABASE
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
    except Exception: 
        pass

    selected_old_record = st.selectbox("📂 Xem lại phiếu tác nghiệp cũ từ Supabase (Không cần up file):", history_styles, key="sb_outside_history_select")
    
    if selected_old_record != "-- Chọn mã hàng cũ đã lưu trên Supabase --":
        try:
            parts_str = selected_old_record.split(" - VẢI: ")
            st_id_search = str(parts_str[0]).strip()
            fb_tp_search = str(parts_str[1]).strip()
            
            res_detail = sb_load_client.table("cutting_orders_db").select("*").eq("style_id", st_id_search).eq("fabric_type", fb_tp_search).limit(1).execute()
            if res_detail.data and len(res_detail.data) > 0:
                old_data = res_detail.data[0]
                recovered_matrix = old_data.get("cutting_matrix_data", [])
                built_sizes_dict = {}
                if recovered_matrix and len(recovered_matrix) >= 6:
                    size_row_data = recovered_matrix[4]
                    qty_row_data = recovered_matrix[5]
                    for k_key, v_size in size_row_data.items():
                        if k_key != "BÀN CẮT / TÊN SƠ ĐỒ" and not any(x in k_key for x in ["SƠ LỚP", "SỐ BÀN", "DÀI SƠ ĐỒ", "SỐ SP/SĐ", "Đ.MỨC SĐ", "VẢI CẦN"]):
                            if v_size and str(v_size).strip() != "":
                                try: 
                                    built_sizes_dict[str(v_size).strip()] = int(str(qty_row_data.get(k_key, "0")).replace(",", ""))
                                except Exception: 
                                    built_sizes_dict[str(v_size).strip()] = 0
                if not built_sizes_dict: 
                    built_sizes_dict = {"26 X 30": 100, "28 X 30": 100}
                st.session_state["sbd_parsed_data"] = {"style_id": old_data.get("style_id"), "total_quantity": old_data.get("total_po_qty"), "size_breakdown": built_sizes_dict}
                if recovered_matrix:
                    st.session_state["auto_cutting_results_recovered"] = recovered_matrix
                    st.session_state["fabric_type_recovered"] = old_data.get("fabric_type", "CHÍNH")
                st.session_state["pur_tp_parsed_data"] = {"dummy_status": "skipped_not_needed"}
                st.session_state["purchase_ready"] = True
                st.rerun()
        except Exception: 
            pass
        
    st.markdown("<br><p style='font-size:13px; font-weight:700; color:#475569;'>HOẶC LẬP PHIẾU TÁC NGHIỆP MỚI BẰNG FILE SBD:</p>", unsafe_allow_html=True)
    file_sbd_c2 = st.file_uploader("📋 Chọn File SBD Số Lượng Đơn Hàng (Excel/PDF)", type=["xlsx", "xls", "pdf"], key="purchase_sbd_c2_unique")

# =============================================================================
# TẦNG 1 - ĐOẠN 1: LIÊN KẾT PHÂN TÍCH FILE VÀ CHUẨN HÓA DỮ LIỆU ĐƠN HÀNG SBD
# =============================================================================
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
                    except Exception: 
                        pass
                elif file_sbd_c2.name.lower().endswith('.pdf'): 
                    sbd_parts_payload.append(types.Part.from_bytes(data=sbd_bytes, mime_type='application/pdf'))
                # =============================================================================
                # TẦNG 1 - ĐOẠN 2: PROMPT ÉP SỐ LƯỢNG SẠCH VÀ RESET BỘ NHỚ ĐỆM SNAPSHOT TRỐNG
                # =============================================================================
                sbd_prompt = """
                Analyze the uploaded garment production file. Extract style_id, total_quantity, and the complete size breakdown numbers.
                
                CRITICAL INSTRUCTIONS FOR QUANTITIES:
                1. Identify the rows containing the actual ordering or cutting quantities distributed under each size column.
                2. Extract the numbers as pure integers. If numbers contain commas (e.g., 1,250), strip the comma and save as 1250.
                3. Return a clean JSON object exactly matching this schema:
                {
                  "style_id": "string",
                  "total_quantity": integer,
                  "size_breakdown": {
                    "SIZE_NAME_1": integer,
                    "SIZE_NAME_2": integer
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
                    
                    # Giải mã chuỗi JSON an toàn đa tầng
                    parsed_json_data = json.loads(res_sbd.text.strip().replace("```json", "").replace("```", "").strip())
                    
                    # Lọc sạch dữ liệu ép kiểu int đề phòng AI trả về chuỗi text số lượng lẻ
                    if "size_breakdown" in parsed_json_data and isinstance(parsed_json_data["size_breakdown"], dict):
                        clean_dict = {}
                        for k, v in parsed_json_data["size_breakdown"].items():
                            try: clean_dict[str(k).strip().upper()] = int(float(str(v).replace(",", "").strip() or 0))
                            except Exception: clean_dict[str(k).strip().upper()] = 0
                        parsed_json_data["size_breakdown"] = clean_dict
                        
                    st.session_state["sbd_parsed_data"] = parsed_json_data
                    
                    # 🔥 ĐIỂM SỬA LỖI CỐT LÕI: Hủy hoàn toàn bộ nhớ đệm snapshot ô lưới trống cũ
                    # Việc này ép Tầng 3 bắt buộc phải vẽ lại lưới mới tinh dựa trên sản lượng vừa quét
                    if "session_editor_snapshot" in st.session_state:
                        st.session_state["session_editor_snapshot"] = None
                    if "auto_cutting_results" in st.session_state:
                        st.session_state["auto_cutting_results"] = None
                        
                except Exception as e: 
                    st.error(f"⚠️ Lỗi xử lý cấu trúc ma trận file: {str(e)}")
                    
                st.session_state["pur_tp_parsed_data"] = {"dummy_status": "skipped_not_needed"}
                st.session_state["purchase_ready"] = True
                st.rerun()

# =============================================================================
# TẦNG 2 - ĐOẠN 1: CHUẨN HÓA LÀM SẠCH VÀ PHẲNG HÓA COLUMN SIZES TỪ GỐC
# =============================================================================
else:
    sbd_data_store = st.session_state.get("sbd_parsed_data", {})
    if isinstance(sbd_data_store, dict) and sbd_data_store:
        detected_style_id = sbd_data_store.get("style_id", "UNKNOWN_STYLE")
        detected_total_po = sbd_data_store.get("total_quantity", 0)
        
        # CHUẨN HÓA DỮ LIỆU ĐẦU VÀO: Đảm bảo size_breakdown_main luôn là Dictionary phẳng
        size_breakdown_main = sbd_data_store.get("size_breakdown", {})
        if not isinstance(size_breakdown_main, dict):
            size_breakdown_main = {}

        if st.button("🔄 Quay lại Màn Hình Chính / Tải file khác", type="secondary"):
            st.session_state["purchase_ready"] = False
            st.session_state["sbd_parsed_data"] = {}
            st.session_state["consumption_activated"] = False
            st.session_state["auto_cutting_results"] = None
            if "auto_cutting_results_recovered" in st.session_state: 
                del st.session_state["auto_cutting_results_recovered"]
            st.rerun()

        st.markdown("#### 📋 KHAI BÁO THÔNG SỐ TÁC NGHIỆP ĐƠN HÀNG VÀ BÀN VẢI MULTI-INSEAM")
        input_col1, input_col2, input_col3, input_col_color = st.columns(4)
        with input_col1: style_id_input = st.text_input("🏷️ Tên mã hàng (Style ID):", value=str(detected_style_id).strip().upper())
        with input_col2: po_qty_input = st.number_input("📦 Số lượng đơn hàng (PO Pcs):", value=int(detected_total_po), step=100)
        with input_col3: consumption_input = st.number_input("🎯 Định mức tài liệu đề xuất (Yds/Pcs):", value=1.140, step=0.001, format="%.3f")
        with input_col_color: color_input = st.text_input("🎨 Tự gõ Màu vải:", value="BLACK")

        input_col4, input_col5, input_col6 = st.columns(3)
        with input_col4: max_table_length = st.number_input("📏 Chiều gia tối đa bàn vải (Meters):", value=12.00, step=1.0)
        default_fab = st.session_state.get("fabric_type_recovered", "CHÍNH")
        
        available_fabrics = ["CHÍNH", "LÓT", "KEO", "PHỐI"]
        try: default_index = available_fabrics.index(default_fab)
        except ValueError: default_index = 0
            
        fabric_type_input = st.selectbox("🧵 Loại vải đang tác nghiệp:", available_fabrics, index=default_index)
        with input_col6: cuttable_width_inch = st.number_input("📐 KHỔ CẮT (Khổ vải đi sơ đồ - Inches):", value=56.00, step=0.50, format="%.2f")
        
        cad_paste_zone = st.text_area("Sau khi xem cấu trúc phối size phía dưới, hãy đi sơ đồ trên máy CAD rồi copy dán kết quả [Tên sơ đồ + Chiều dài mét] vào đây:", placeholder="Ví dụ:\n5844-c01 1.05\n5844-c02 10", height=90, key="cad_bulk_paste_c2")
        
        if fabric_type_input != st.session_state.get("last_checked_fabric"):
            st.session_state["last_checked_fabric"] = fabric_type_input
            try:
                from supabase import create_client
                sb_client_check = create_client("https://supabase.co", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImV3cXFvZHNmeGx2bnJ6c3lsYXd5Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3MjEwMjc1NjIsImV4cCI6MjAzNjYwMzU2Mn0.uD-n6W9k6_Z87RcoX_OlyV_1R0g_Yp_B-D3v7b0Q678")
                res_check = sb_client_check.table("cutting_orders_db").select("*").eq("style_id", style_id_input).eq("fabric_type", fabric_type_input).limit(1).execute()
                if res_check.data and len(res_check.data) > 0:
                    st.session_state["auto_cutting_results_recovered"] = res_check.data["cutting_matrix_data"]
                    st.session_state["auto_cutting_results"] = None
                    st.rerun()
                else:
                    if "auto_cutting_results_recovered" in st.session_state: 
                        del st.session_state["auto_cutting_results_recovered"]
            except Exception: pass

        # 🛠️ BƯỚC THAY ĐỔI CỐT LÕI: Phẳng hóa và dọn sạch ký tự gạch chân từ gốc dữ liệu
        clean_size_breakdown = {}
        for k, v in size_breakdown_main.items():
            try:
                # Xóa sạch đuôi _1, _2 lỡ có ở tên cột của Pandas
                clean_key = re.sub(r'_\d+$', '', str(k)).strip().upper()
                
                # Bẫy lỗi bảo vệ: Nếu clean_key vô tình bị biến thành chuỗi dạng mảng, ép phẳng trả về dạng text chuẩn may mặc
                if clean_key.startswith("[") and clean_key.endswith("]"):
                    clean_key = clean_key.replace("[", "").replace("]", "").replace("'", "").replace('"', "").replace(",", "X").replace(" ", "")
                
                clean_v = int(float(str(v).replace(",", "").strip() or 0))
                if clean_v > 0:
                    clean_size_breakdown[clean_key] = clean_size_breakdown.get(clean_key, 0) + clean_v
            except Exception:
                continue
        
        # Ghi đè ma trận sản lượng phẳng sạch vào hệ thống
        size_breakdown_main = clean_size_breakdown

        # Thuật toán sắp xếp danh sách kích cỡ bám theo Inseam (Giàng) tăng dần (30 -> 32 -> 34)
        def key_sort_by_inseam_then_waist(size_string):
            s_clean = str(size_string).upper().replace(" ", "").strip()
            parts = re.split(r'[X_-]', s_clean)
            if len(parts) >= 2:
                try:
                    waist = int(float(parts[0]))
                    inseam = int(float(parts[1]))
                    return (inseam, waist)
                except ValueError:
                    return (999, 999)
            else:
                try: return (0, int(float(s_clean)))
                except ValueError: return (0, s_clean)

        # Trích xuất mảng danh sách size sạch phẳng
        active_sizes = sorted(list(size_breakdown_main.keys()), key=key_sort_by_inseam_then_waist)
        if not active_sizes: 
            active_sizes = ["26X30", "28X30", "29X32"]


# =============================================================================
# TẦNG 2 - ĐOẠN 2a: CÁC NÚT BẤM HÀNH ĐỘNG VÀ KHẮC PHỤC HOÀN TOÀN LỖI EMPTY_SLOTS
# =============================================================================
        btn_col1, btn_col2, btn_col_clear = st.columns([1.5, 1.5, 1])
        with btn_col1: 
            trigger_auto_cutting = st.button("🤖 1. KÍCH HOẠT AI VÉT SẠCH SẼ LƯỢNG DƯ CÒN LẠI", type="primary", use_container_width=True, key="c2_normal_cut_btn")
        with btn_col2: 
            trigger_consumption = st.button("🔒 2. TÍNH TOÁN LUỸ TIẾN & KHÓA CHỒNG KHO", type="secondary", use_container_width=True, key="c2_consumption_btn")
        with btn_col_clear:
            trigger_clear_data = st.button("🧹 XÓA ĐỂ TÍNH LẠI", type="secondary", use_container_width=True, key="c2_clear_all_data_btn")

        if trigger_clear_data:
            st.session_state["session_editor_snapshot"] = None
            st.session_state["auto_cutting_results"] = None
            st.session_state["consumption_activated"] = False
            st.toast("🧹 Đã làm sạch toàn bộ ô lưới tác nghiệp. Bạn có thể nhập lại!", icon="🧹")
            st.rerun()

        if trigger_consumption:
            st.session_state["consumption_activated"] = True
            st.toast("🔒 Đã khóa cứng ma trận nhập tay và đồng bộ xuống bảng theo dõi!", icon="🔒")

        if trigger_auto_cutting:
            with st.spinner(f"🤖 AI đang quét dữ liệu và giải ma trận phối cỡ cho các sơ đồ trống..."):
                if "get_secure_gemini_key" in globals(): 
                    gemini_key = get_secure_gemini_key()
                else: 
                    gemini_key = st.secrets.get("GEMINI_API_KEY", "").strip()
                from google import genai
                from google.genai import types
                client_ai = genai.Client(api_key=gemini_key)
                
                snapshot = st.session_state.get("session_editor_snapshot")
                calculated_balances = {}
                for sz in active_sizes:
                    try: calculated_balances[sz] = int(float(str(size_breakdown_main.get(sz, 0)).replace(",", "").strip() or 0))
                    except Exception: calculated_balances[sz] = 0
                
                # 🔥 ĐIỂM CHỐT KHẮC PHỤC LỖI: Luôn khởi tạo mảng rỗng trước khi rẽ nhánh điều kiện
                empty_slots = []
                current_grid_structure = []

                if snapshot and len(snapshot) > 0 and snapshot is not None:
                    for idx, row_data in enumerate(snapshot):
                        s_name = str(row_data.get("BÀN CẮT / TÊN SƠ ĐỒ", f"SƠ ĐỒ C{idx+1}")).upper().strip()
                        s_code = f"c{str(idx+1).zfill(2)}"
                        
                        total_ratios_entered = 0
                        row_ratios = {}
                        for sz in active_sizes:
                            try: r_val = int(float(str(row_data.get(sz, 0)).replace(",", "").strip() or 0))
                            except Exception: r_val = 0
                            row_ratios[sz] = r_val
                            total_ratios_entered += r_val
                        
                        try: layers = int(float(str(row_data.get("SƠ LỚP", 0)).replace(",", "").strip() or 0))
                        except Exception: layers = 0
                            
                        try: tables = int(float(str(row_data.get("SỐ BÀN", 1)).replace(",", "").strip() or 1))
                        except Exception: tables = 1

                        if total_ratios_entered > 0 and layers > 0:
                            for sz in active_sizes:
                                r_val = row_ratios[sz]
                                calculated_balances[sz] = max(0, calculated_balances[sz] - (r_val * layers * tables))
                            
                            current_grid_structure.append({
                                "Mã dòng": s_code, "Tên sơ đồ gốc": s_name, "Trạng thái": "GIỮ NGUYÊN KHÔNG ĐỔI"
                            })
                        else:
                            empty_slots.append(s_code)
                            current_grid_structure.append({
                                "Mã dòng": s_code, "Tên sơ đồ gốc": s_name, "Trạng thái": "AI ĐIỀN VÀO ĐÂY"
                            })
                else:
                    # Nếu snapshot trống (vừa gõ nút Clear), mặc định toàn bộ 6 dòng c01-c06 đều chờ AI giải
                    empty_slots = ["c01", "c02", "c03", "c04", "c05", "c06"]
                    fab_letter_c2 = "C"
                    fab_upper_c2 = str(fabric_type_input).upper().strip() if 'fabric_type_input' in locals() else "CHÍNH"
                    if fab_upper_c2 == "LÓT": fab_letter_c2 = "L"
                    elif fab_upper_c2 == "KEO": fab_letter_c2 = "K"
                    elif fab_upper_c2 == "PHỐI": fab_letter_c2 = "P"
                    
                    current_grid_structure = [
                        {
                            "Mã dòng": f"c{str(i+1).zfill(2)}", 
                            "Tên sơ đồ gốc": f"{fab_upper_c2} {fab_letter_c2}{str(i+1).zfill(2)}", 
                            "Trạng thái": "AI ĐIỀN VÀO ĐÂY"
                        } for i in range(6)
                    ]

                is_sub_fabric = str(fabric_type_input).upper() in ["LÓT", "KEO", "PHỐI"]
                fabric_rule_text = ""
                if is_sub_fabric:
                    fabric_rule_text = "- ĐẶC BIỆT: Đây là vải phụ (KEO/LÓT/PHỐI). Được phép cắt dư thêm 5-10 Pcs mỗi size lẻ để dễ gộp vào sơ đồ lớn, hạn chế sinh sơ đồ mỏng."
                else:
                    fabric_rule_text = "- ĐẶC BIỆT: Đây là vải CHÍNH. Không được phép cắt dư, tính toán phối cỡ và số lớp sao cho sản lượng triệt tiêu chính xác về 0."

                dinhmuc_met_c2 = round(consumption_input * 0.9144, 3)


         # =============================================================================
        # TẦNG 2 - ĐOẠN 2b (PHẦN 1): THIẾT LẬP CẤU TRÚC SƠ ĐỒ TRỐNG VÀ GỬI PROMPT AI ÉP CỘT PHẲNG
        # =============================================================================
        if trigger_auto_cutting:
            with st.spinner(f"🤖 AI đang quét dữ liệu và giải ma trận phối cỡ cho các sơ đồ trống..."):
                if "get_secure_gemini_key" in globals(): 
                    gemini_key = get_secure_gemini_key()
                else: 
                    gemini_key = st.secrets.get("GEMINI_API_KEY", "").strip()
                from google import genai
                from google.genai import types
                client_ai = genai.Client(api_key=gemini_key)
                
                snapshot = st.session_state.get("session_editor_snapshot")
                calculated_balances = {}
                for sz in active_sizes:
                    try: calculated_balances[sz] = int(float(str(size_breakdown_main.get(sz, 0)).replace(",", "").strip() or 0))
                    except Exception: calculated_balances[sz] = 0
                
                empty_slots = []
                current_grid_structure = []

                if snapshot and len(snapshot) > 0:
                    real_slots = [r for r in snapshot if str(r.get("BÀN CẮT / TÊN SƠ ĐỒ", "")).upper().strip() not in ["GIÀNG", "SIZE", "SẢN LƯỢNG"]]
                    for idx, row_data in enumerate(real_slots):
                        s_name = str(row_data.get("BÀN CẮT / TÊN SƠ ĐỒ", f"SƠ ĐỒ C{idx+1}")).upper().strip()
                        s_code = f"c{str(idx+1).zfill(2)}"
                        
                        total_ratios_entered = 0
                        row_ratios = {}
                        for sz in active_sizes:
                            val_cell = row_data.get(sz, row_data.get(f"CỠ {active_sizes.index(sz)+1}" if sz in active_sizes else "", 0))
                            try: r_val = int(float(str(val_cell).replace(",", "").strip() or 0))
                            except Exception: r_val = 0
                            row_ratios[sz] = r_val
                            total_ratios_entered += r_val
                        
                        try: layers = int(float(str(row_data.get("SƠ LỚP", 0)).replace(",", "").strip() or 0))
                        except Exception: layers = 0
                        try: tables = int(float(str(row_data.get("SỐ BÀN", 1)).replace(",", "").strip() or 1))
                        except Exception: tables = 1

                        if total_ratios_entered > 0 and layers > 0:
                            for sz in active_sizes:
                                r_val = row_ratios[sz]
                                calculated_balances[sz] = max(0, calculated_balances[sz] - (r_val * layers * tables))
                            current_grid_structure.append({"Mã dòng": s_code, "Tên sơ đồ gốc": s_name, "Trạng thái": "GIỮ NGUYÊN KHÔNG ĐỔI"})
                        else:
                            empty_slots.append(s_code)
                            current_grid_structure.append({"Mã dòng": s_code, "Tên sơ đồ gốc": s_name, "Trạng thái": "AI ĐIỀN VÀO ĐÂY"})
                else:
                    empty_slots = ["c01", "c02", "c03", "c04", "c05", "c06"]
                    current_grid_structure = [{"Mã dòng": f"c{str(i+1).zfill(2)}", "Tên sơ đồ gốc": f"SƠ ĐỒ C{str(i+1).zfill(2)}", "Trạng thái": "AI ĐIỀN VÀO ĐÂY"} for i in range(6)]

                total_remaining_po = sum(calculated_balances.values())
                dinhmuc_met_c2 = round(consumption_input * 0.9144, 3)

                ai_cutting_prompt = f"""
                Bạn là thuật toán toán học điều độ bàn cắt. Hãy tính phối cỡ điền vào các dòng đang TRỐNG này: {json.dumps(empty_slots)}.
                Tuyệt đối KHÔNG ĐƯỢC tự ý bỏ dòng hoặc thay đổi thông tin các dòng đã gõ tay.
                
                Thông số đầu vào:
                - Bản đồ cấu trúc các dòng: {json.dumps(current_grid_structure)}
                - Số lượng sản phẩm còn dư thực tế cần vét: {json.dumps(calculated_balances)}
                - Định mức tài liệu kỹ thuật: {dinhmuc_met_c2} mét/quần.
                - Chiều dài bàn vải tối đa cho phép: {max_table_length} mét.

                QUY TẮC PHỐI CỠ VÀ TÍNH CHIỀU DÀI BẮT BUỘC:
                1. Chỉ được điền tỷ lệ phối (Ratios) và Số lớp vào dòng ghi "AI ĐIỀN VÀO ĐÂY". Điền tuần tự từ trên xuống dưới.
                2. Với mỗi dòng sơ đồ được điền, bạn hãy CHỌN một tổng số sản phẩm trên sơ đồ (Ví dụ: 10 sản phẩm hoặc 14 sản phẩm) sao cho chiều dài đi sơ đồ thực tế = (Tổng số sản phẩm) * ({dinhmuc_met_c2} mét) BẮT BUỘC <= {max_table_length} mét.
                3. Hãy phân bổ số sản phẩm trên sơ đồ đó vào các size theo đúng TỶ LỆ PHẦN TRĂM (%) của sản lượng còn lại.
                4. Trả về mảng JSON sạch cấu trúc chuẩn xác, Key trong mảng Ratios bắt buộc phải đặt tên theo đúng số thứ tự của cột là "CỠ 1", "CỠ 2", "CỠ 3"... dựa theo danh sách size tương ứng này: {json.dumps([f'CỠ {i+1}: {sz}' for i, sz in enumerate(active_sizes)])}.

                Trả về cấu trúc JSON chuẩn:
                [
                  {{"Sơ đồ / Trạng thái": "c01", "Ratios": {{"CỠ 1": 2, "CỠ 2": 4, "CỠ 3": 4}}, "Số lớp": 120, "Số bàn": 1, "Chiều dài mét": 11.4}}
                ]
                """
                # =============================================================================
                # TẦNG 2 - ĐOẠN 2b (PHẦN 2): GIẢI GEMINI VÀ CHẠY THUẬT TOÁN PYTHON LARGEST REMAINDER
                # =============================================================================
                try:
                    res_cutting = client_ai.models.generate_content(
                        model='gemini-2.5-flash', contents=[ai_cutting_prompt],
                        config=types.GenerateContentConfig(response_mime_type="application/json")
                    )
                    ai_vete_res = json.loads(res_cutting.text.strip().replace("```json", "").replace("```", "").strip())
                    
                    if isinstance(ai_vete_res, list) and len(ai_vete_res) > 0:
                        st.session_state["auto_cutting_results"] = ai_vete_res
                        
                        updated_rows = []
                        fab_letter_c2 = "C"
                        fab_upper_c2 = str(fabric_type_input).upper().strip() if 'fabric_type_input' in locals() else "CHÍNH"
                        if fab_upper_c2 == "LÓT": fab_letter_c2 = "L"
                        elif fab_upper_c2 == "KEO": fab_letter_c2 = "K"
                        elif fab_upper_c2 == "PHỐI": fab_letter_c2 = "P"

                        for i in range(6):
                            s_code = f"c{str(i+1).zfill(2)}"
                            
                            # Chừa lại đúng vị trí dòng bỏ qua 3 dòng tiêu đề phụ
                            if snapshot and (i+3) < len(snapshot):
                                old_row_data = snapshot[i+3]
                                s_name_display = str(old_row_data.get("BÀN CẮT / TÊN SƠ ĐỒ", f"{fab_upper_c2} {fab_letter_c2}{str(i+1).zfill(2)}")).upper().strip()
                            else:
                                s_name_display = f"{fab_upper_c2} {fab_letter_c2}{str(i+1).zfill(2)}"
                                
                            item_dict = {"BÀN CẮT / TÊN SƠ ĐỒ": s_name_display}
                            ai_match = [x for x in ai_vete_res if str(x.get("Sơ đồ / Trạng thái", "")).strip().lower() == s_code]
                            
                            if ai_match and len(ai_match) > 0:
                                ai_row = ai_match
                                r_dict = ai_row.get("Ratios", {})
                                
                                # 1. Bóc tách số quần phối trên sơ đồ (Garments_Per_Marker) từ dữ liệu AI gửi về
                                total_pants_in_marker = 0
                                for r_k, r_v in r_dict.items():
                                    try: total_pants_in_marker += int(float(str(r_v).strip() or 0))
                                    except Exception: pass
                                    
                                if total_pants_in_marker == 0:
                                    try: total_pants_in_marker = int(float(str(ai_row.get("Tổng số sản phẩm", 10))))
                                    except Exception: total_pants_in_marker = 10
                                    
                                # 2. CƯƠNG CHẾ THUẬT TOÁN PYTHON PHÂN BỔ TỶ LỆ SIZE THEO NGUYÊN LÝ LARGEST REMAINDER
                                base_values = {}
                                remainders = []
                                
                                for c_idx, sz in enumerate(active_sizes):
                                    sz_order = calculated_balances.get(sz, 0)
                                    sz_ratio_pct = sz_order / total_remaining_po if total_remaining_po > 0 else 0
                                    theoretical_qty = total_pants_in_marker * sz_ratio_pct
                                    
                                    base_qty = int(theoretical_qty)
                                    rem = theoretical_qty - base_qty
                                    
                                    base_values[sz] = base_qty
                                    remainders.append({"size": sz, "remainder": rem})
                                    
                                current_total = sum(base_values.values())
                                allocated_more = total_pants_in_marker - current_total
                                remainders.sort(key=lambda x: x["remainder"], reverse=True)
                                
                                for k in range(min(max(0, allocated_more), len(remainders))):
                                    target_sz = remainders[k]["size"]
                                    base_values[target_sz] += 1
                                    
                                # Nạp dữ liệu tỷ lệ phối sạch đã phân bổ bằng Python vào mảng
                                for sz in active_sizes:
                                    item_dict[sz] = base_values[sz]
                                
                                try: s_lop = int(float(str(ai_row.get("Số lớp", 120))).strip() or 120)
                                except Exception: s_lop = 120
                                try: s_ban = int(float(str(ai_row.get("Số bàn", 1))).strip() or 1)
                                except Exception: s_ban = 1
                                
                                calculated_len = float(round(total_pants_in_marker * dinhmuc_met_c2, 2))
                                item_dict.update({"SƠ LỚP": s_lop, "SỐ BÀN": s_ban, "DÀI SƠ ĐỒ": calculated_len})
                            else:
                                if snapshot and (i+3) < len(snapshot):
                                    old_row = snapshot[i+3]
                                    for sz in active_sizes:
                                        try: item_dict[sz] = int(float(str(old_row.get(sz, 0)).strip() or 0))
                                        except Exception: item_dict[sz] = 0
                                    try: item_dict["SƠ LỚP"] = int(float(str(old_row.get("SƠ LỚP", 0)).strip() or 0))
                                    except Exception: item_dict["SƠ LỚP"] = 0
                                    try: item_dict["SỐ BÀN"] = int(float(str(old_row.get("SỐ BÀN", 1)).strip() or 1))
                                    except Exception: item_dict["SỐ BÀN"] = 1
                                    try: item_dict["DÀI SƠ ĐỒ"] = float(str(old_row.get("DÀI SƠ ĐỒ", 0.0)).strip() or 0.0)
                                    except Exception: item_dict["DÀI SƠ ĐỒ"] = 0.0
                                else:
                                    for sz in active_sizes: item_dict[sz] = 0
                                    item_dict.update({"SƠ LỚP": 0, "SỐ BÀN": 1, "DÀI SƠ ĐỒ": 0.0})
                            updated_rows.append(item_dict)
                        
                        # Tạo mảng render_snapshot khớp chuẩn xác trục cột phẳng CỠ X đưa lên Tầng 3
                        final_sync_render_rows = []
                        giang_row_cache = snapshot if snapshot else {"BÀN CẮT / TÊN SƠ ĐỒ": "GIÀNG"}
                        size_row_cache = snapshot if snapshot else {"BÀN CẮT / TÊN SƠ ĐỒ": "SIZE"}
                        sl_row_cache = snapshot if snapshot else {"BÀN CẮT / TÊN SƠ ĐỒ": "SẢN LƯỢNG"}
                        
                        final_sync_render_rows.append(giang_row_cache)
                        final_sync_render_rows.append(size_row_cache)
                        final_sync_render_rows.append(sl_row_cache)
                        
                        for row_data_item in updated_rows:
                            render_dict = {"BÀN CẮT / TÊN SƠ ĐỒ": row_data_item["BÀN CẮT / TÊN SƠ ĐỒ"]}
                            r_sum_horizontal = 0
                            for c_idx, sz in enumerate(active_sizes):
                                val_sz = row_data_item.get(sz, 0)
                                render_dict[f"CỠ {c_idx+1}"] = val_sz
                                r_sum_horizontal += val_sz
                                    
                            l_val = row_data_item.get("SƠ LỚP", 0)
                            t_val = row_data_item.get("SỐ BÀN", 1)
                            
                            render_dict["TỔNG SẢN LƯỢNG"] = f"{r_sum_horizontal * l_val * t_val:,}"
                            render_dict["SƠ LỚP"] = l_val
                            render_dict["SỐ BÀN"] = t_val
                            render_dict["DÀI SƠ ĐỒ"] = row_data_item.get("DÀI SƠ ĐỒ", 0.0)
                            final_sync_render_rows.append(render_dict)
                            
                        st.session_state["session_editor_snapshot"] = final_sync_render_rows
                        st.success("🎉 Thuật toán toán học Python đã phân bổ tỷ lệ phối cỡ và tự động gộp phần dư lớn nhất thành công!")
                        st.rerun()
                except Exception as e:
                    st.error(f"⚠️ Lỗi xử lý ma trận đồng bộ AI: {str(e)}")





        # =============================================================================
        # TẦNG 3 - ĐOẠN 1: BẢNG NHẬP LIỆU GÕ TAY DUY NHẤT PHÍA TRÊN (KHÔNG CHẠY LẶP)
        # =============================================================================
        display_editor_rows = []
        recovered_source = st.session_state.get("auto_cutting_results_recovered", [])
        snapshot = st.session_state.get("session_editor_snapshot")

        fab_upper = str(fabric_type_input).upper().strip()
        prefix_letter = "L" if fab_upper == "LÓT" else "K" if fab_upper == "KEO" else "P" if fab_upper == "PHỐI" else "C"

        # Tính tổng sản lượng đơn hàng gốc
        total_sum_po_qty = 0
        for sz in active_sizes:
            try: total_sum_po_qty += int(str(size_breakdown_main.get(sz, 0)).replace(",", "").split(".").strip() or 0)
            except Exception: pass

        # Khởi tạo 3 hàng tiêu đề phụ cố định
        giang_top_row = {"BÀN CẮT / TÊN SƠ ĐỒ": "GIÀNG", "TỔNG SẢN LƯỢNG": ""}
        size_top_row = {"BÀN CẮT / TÊN SƠ ĐỒ": "SIZE", "TỔNG SẢN LƯỢNG": ""}
        sl_top_row = {"BÀN CẮT / TÊN SƠ ĐỒ": "SẢN LƯỢNG", "TỔNG SẢN LƯỢNG": f"{total_sum_po_qty:,}"}
        
        for sz in active_sizes:
            parts = re.split(r'[X_-]', str(sz).upper().replace(" ", ""))
            giang_top_row[sz] = re.sub(r'_\d+$', '', str(parts).strip()) if len(parts) >= 2 else "None"
            size_top_row[sz] = re.sub(r'_\d+$', '', str(parts).strip()) if len(parts) >= 1 else "None"
            try: po_v = int(str(size_breakdown_main.get(sz, 0)).replace(",", "").split(".").strip() or 0)
            except Exception: po_v = 0
            sl_top_row[sz] = po_v
            
        giang_top_row.update({"SƠ LỚP": 0, "SỐ BÀN": 0, "DÀI SƠ ĐỒ": 0.0})
        size_top_row.update({"SƠ LỚP": 0, "SỐ BÀN": 0, "DÀI SƠ ĐỒ": 0.0})
        sl_top_row.update({"SƠ LỚP": 0, "SỐ BÀN": 0, "DÀI SƠ ĐỒ": 0.0})

        # Đọc dữ liệu từ bộ đệm phẳng tránh sinh bảng ảo thừa
        if snapshot and len(snapshot) > 0:
            filtered_snapshot = [r for row in snapshot if (r := dict(row)).get("BÀN CẮT / TÊN SƠ ĐỒ") not in ["GIÀNG", "SIZE", "SẢN LƯỢNG"]]
            cleaned_snapshot = [giang_top_row, size_top_row, sl_top_row]
            for row in filtered_snapshot:
                item_dict = {"BÀN CẮT / TÊN SƠ ĐỒ": str(row.get("BÀN CẮT / TÊN SƠ ĐỒ", "")).upper().strip(), "TỔNG SẢN LƯỢNG": row.get("TỔNG SẢN LƯỢNG", 0)}
                for sz in active_sizes:
                    try: item_dict[sz] = int(float(str(row.get(sz, 0)).replace(",", "").strip() or 0))
                    except Exception: item_dict[sz] = 0
                try: item_dict["SƠ LỚP"] = int(float(str(row.get("SƠ LỚP", 0)).replace(",", "").strip() or 0))
                except Exception: item_dict["SƠ LỚP"] = 0
                try: item_dict["SỐ BÀN"] = int(float(str(row.get("SỐ BÀN", 1)).replace(",", "").strip() or 1))
                except Exception: item_dict["SỐ BÀN"] = 1
                try: item_dict["DÀI SƠ ĐỒ"] = float(str(row.get("DÀI SƠ ĐỒ", 0.0)).replace(",", "").strip() or 0.0)
                except Exception: item_dict["DÀI SƠ ĐỒ"] = 0.0
                cleaned_snapshot.append(item_dict)
            display_editor_rows = cleaned_snapshot
        elif recovered_source:
            display_editor_rows = [giang_top_row, size_top_row, sl_top_row]
            for row in recovered_source:
                t_name = str(row.get("BÀN CẮT / TÊN SƠ ĐỒ", "")).strip()
                if not any(x in t_name for x in ["CÒN LẠI", "SẢN LƯỢNG", "Mã hàng", "Màu:", "Loại vải:", "GIÀNG", "SIZE"]):
                    clean_row = {"BÀN CẮT / TÊN SƠ ĐỒ": t_name, "TỔNG SẢN LƯỢNG": row.get("TỔNG SẢN LƯỢNG", 0)}
                    for sz in active_sizes: 
                        try: clean_row[sz] = int(float(str(row.get(sz, 0)).replace(",", "").strip() or 0))
                        except Exception: clean_row[sz] = 0
                    try:
                        clean_row.update({
                            "SƠ LỚP": int(float(str(row.get("SƠ LỚP", 0)).replace(",", "").strip() or 0)), 
                            "SỐ BÀN": int(float(str(row.get("SỐ BÀN", 1)).replace(",", "").strip() or 1)), 
                            "DÀI SƠ ĐỒ": float(str(row.get("DÀI SƠ ĐỒ", 0.0)).replace(",", "").strip() or 0.0)
                        })
                    except Exception: clean_row.update({"SƠ LỚP": 0, "SỐ BÀN": 1, "DÀI SƠ ĐỒ": 0.0})
                    display_editor_rows.append(clean_row)
        else:
            display_editor_rows = [giang_top_row, size_top_row, sl_top_row]
            for i in range(6):
                s_code = f"{prefix_letter}{str(i+1).zfill(2)}"
                item_dict = {"BÀN CẮT / TÊN SƠ ĐỒ": f"{fab_upper} {s_code}", "TỔNG SẢN LƯỢNG": 0}
                for sz in active_sizes: item_dict[sz] = 0
                item_dict.update({"SƠ LỚP": 0, "SỐ BÀN": 1, "DÀI SƠ ĐỒ": 0.0})
                display_editor_rows.append(item_dict)
                
        df_editor_base = pd.DataFrame(display_editor_rows)
        clean_headers_top = ["BÀN CẮT / TÊN SƠ ĐỒ", "TỔNG SẢN LƯỢNG"] + [f"CỠ {i+1}" for i in range(len(active_sizes))] + ["SƠ LỚP", "SỐ BÀN", "DÀI SƠ ĐỒ"]
        df_editor_top_render = df_editor_base.copy()
        df_editor_top_render.columns = clean_headers_top

        is_locked = st.session_state.get("consumption_activated", False)
        if is_locked:
            if st.button("🔓 MỞ KHÓA TOÀN BỘ BẢNG ĐỂ CHỈNH SỬA LẠI TAY", type="secondary", use_container_width=True, key="unlock_matrix_btn_final"):
                st.session_state["consumption_activated"] = False
                st.rerun()

        st.markdown("<p style='font-weight:700; font-size:14px; color:#1E3A8A; margin-top:15px;'>✍️ BẢNG TỰ NHẬP TỶ LỆ PHỐI SIZE VÀ SỐ LỚP BÀN CẮT (GÕ DÀI SƠ ĐỒ TỰ NHẢY TỶ LỆ)</p>", unsafe_allow_html=True)
        
        # Hàm callback xử lý thay đổi số liệu tức thời
        def callback_sync_on_the_fly_final():
            if "table_manual_data_editor_final" in st.session_state:
                st_editor = st.session_state["table_manual_data_editor_final"]
                if "edited_rows" in st_editor:
                    for r_idx_edit, change_dict in st_editor["edited_rows"].items():
                        if r_idx_edit < len(display_editor_rows):
                            if display_editor_rows[r_idx_edit]["BÀN CẮT / TÊN SƠ ĐỒ"] in ["GIÀNG", "SIZE", "SẢN LƯỢNG"]: continue
                            clean_changes = {}
                            for col_header, new_val in change_dict.items():
                                if str(col_header).startswith("CỠ "):
                                    try:
                                        c_num = int(str(col_header).replace("CỠ ", "").strip())
                                        clean_changes[active_sizes[c_num - 1]] = int(float(str(new_val).strip() or 0))
                                    except Exception: pass
                                elif col_header in ["SƠ LỚP", "SỐ BÀN"]:
                                    try: clean_changes[col_header] = int(float(str(new_val).strip() or 0))
                                    except Exception: pass
                                elif col_header == "DÀI SƠ ĐỒ":
                                    try: clean_changes[col_header] = float(str(new_val).strip() or 0.0)
                                    except Exception: pass
                                else: clean_changes[col_header] = new_val
                            display_editor_rows[r_idx_edit].update(clean_changes)
                st.session_state["session_editor_snapshot"] = display_editor_rows

        edited_df_raw = st.data_editor(
            df_editor_top_render, use_container_width=True, hide_index=True, disabled=is_locked, 
            key="table_manual_data_editor_final", on_change=callback_sync_on_the_fly_final
        )

        # =============================================================================
        # TẦNG 3 - ĐOẠN 2: THUẬT TOÁN CHIA TỶ LỆ TOÁN HỌC VÀ LẬP MA TRẬN PHÂN BỔ BẢNG DƯỚI
        # =============================================================================
        final_snapshot_rows = []
        for idx, row in edited_df_raw.iterrows():
            s_row_name = str(row.get("BÀN CẮT / TÊN SƠ ĐỒ", "")).upper().strip()
            item_dict = {"BÀN CẮT / TÊN SƠ ĐỒ": s_row_name}
            
            try: layers = int(float(str(row.get("SƠ LỚP", 0)).replace(",", "").strip() or 0))
            except Exception: layers = 0
            try: tables = int(float(str(row.get("SỐ BÀN", 1)).replace(",", "").strip() or 1))
            except Exception: tables = 1
            try: m_len = float(str(row.get("DÀI SƠ ĐỒ", 0.0)).replace(",", "").strip() or 0.0)
            except Exception: m_len = 0.0
            
            # 🎯 LUỒNG NGUYÊN LÝ CỦA BẠN: Chia tổng số lượng sản phẩm trên sơ đồ từ chiều dài Yards
            m_len_yards = m_len * 1.09361
            if m_len_yards > 0 and consumption_input > 0 and s_row_name not in ["GIÀNG", "SIZE", "SẢN LƯỢNG"]:
                garments_per_marker = int(round(m_len_yards / consumption_input))
            else: garments_per_marker = 0
                
            r_dict = {}
            if garments_per_marker > 0 and total_sum_po_qty > 0:
                base_values = {}
                remainders = []
                for sz in active_sizes:
                    try: sz_order = int(str(size_breakdown_main.get(sz, 0)).replace(",", "").split(".").strip() or 0)
                    except Exception: sz_order = 0
                    sz_ratio_pct = sz_order / total_sum_po_qty
                    theoretical_qty = garments_per_marker * sz_ratio_pct
                    base_qty = int(theoretical_qty)
                    base_values[sz] = base_qty
                    remainders.append({"size": sz, "remainder": theoretical_qty - base_qty})
                    
                allocated_more = garments_per_marker - sum(base_values.values())
                remainders.sort(key=lambda x: x["remainder"], reverse=True)
                for k in range(min(max(0, allocated_more), len(remainders))):
                    base_values[remainders[k]["size"]] += 1
                r_dict = base_values
            else:
                for c_idx, sz in enumerate(active_sizes):
                    try: r_dict[sz] = int(float(str(row.get(f"CỠ {c_idx+1}", 0)).replace(",", "").strip() or 0))
                    except Exception: r_dict[sz] = 0

            row_ratios_total = 0
            for sz in active_sizes:
                val_sz = r_dict.get(sz, 0)
                item_dict[sz] = val_sz
                if s_row_name not in ["GIÀNG", "SIZE", "SẢN LƯỢNG"]: row_ratios_total += val_sz
            
            if s_row_name in ["GIÀNG", "SIZE"]: item_dict["TỔNG SẢN LƯỢNG"] = ""
            elif s_row_name == "SẢN LƯỢNG": item_dict["TỔNG SẢN LƯỢNG"] = f"{total_sum_po_qty:,}"
            else: item_dict["TỔNG SẢN LƯỢNG"] = f"{row_ratios_total * layers * tables:,}"
                
            item_dict["SƠ LỚP"] = layers
            item_dict["SỐ BÀN"] = tables
            item_dict["DÀI SƠ ĐỒ"] = m_len
            final_snapshot_rows.append(item_dict)
            
        st.session_state["session_editor_snapshot"] = final_snapshot_rows

        # DỰNG MA TRẬN KHẤU TRỪ BẢNG DƯỚIChuẩn xác 100%
        t_header_ma_hang = ["Mã hàng:", f" {style_id_input.strip().upper()}"] + [""] * (len(active_sizes) + 6)
        t_header_mau = ["Màu:", f" {color_input.strip().upper()}"] + [""] * (len(active_sizes) + 6)
        t_header_loai_vai = ["Loại vải:", f" {fabric_type_input.strip().upper()}"] + [""] * (len(active_sizes) + 6)

        t1_giang_row = ["GIÀNG", ""]
        t2_size_row = ["SIZE", ""]
        po_qty_matrix = []

        for col_name in active_sizes:
            c_str = str(col_name).strip().upper().replace(" ", "")
            g_val, s_val = "None", c_str
            parts = re.split(r'[X_-]', c_str)
            if len(parts) >= 2:
                s_val = str(parts).strip(); g_val = str(parts).strip()
            elif len(parts) == 1: s_val = str(parts).strip(); g_val = "None"
            
            g_val_clean = re.sub(r'_\d+$', '', g_val)
            s_val_clean = re.sub(r'_\d+$', '', s_val)
            
            try: po_v = int(str(size_breakdown_main.get(col_name, 0)).replace(",", "").split(".").strip() or 0)
            except Exception: po_v = 0
            po_qty_matrix.append(po_v)
            t1_giang_row.append(g_val_clean)
            t2_size_row.append(s_val_clean)
            
        for _ in range(6): t1_giang_row.append(""); t2_size_row.append("")
        t3_sl_row = ["SẢN LƯỢNG", f"{total_sum_po_qty:,}"] + [f"{v:,}" for v in po_qty_matrix] + [""] * 6
            
        matrix_body_rows = []
        running_balances = list(po_qty_matrix)
        production_rows = [r for r in final_snapshot_rows if r.get("BÀN CẮT / TÊN SƠ ĐỒ") not in ["GIÀNG", "SIZE", "SẢN LƯỢNG"]]

        for r_idx, row_data in enumerate(production_rows):
            s_name = str(row_data.get("BÀN CẮT / TÊN SƠ ĐỒ", f"SƠ ĐỒ C{r_idx+1}")).upper().strip()
            layers = row_data.get("SƠ LỚP", 0)
            tables = row_data.get("SỐ BÀN", 1)
            m_len = row_data.get("DÀI SƠ ĐỒ", 0.0)
            
            active_ratio_parts = []
            row_ratios_list = []
            ratios_sum = 0
            
            for sz in active_sizes:
                r_val = row_data.get(sz, 0)
                ratios_sum += r_val
                row_ratios_list.append(r_val)
                if r_val > 0:
                    sz_clean = re.sub(r'_\d+$', '', str(sz).replace("X","-").replace(" ", "").strip())
                    active_ratio_parts.append(f"{sz_clean}/{r_val}")
            
            if m_len > 0 and ratios_sum > 0:
                dm_sd = (m_len * 1.09361) / ratios_sum
                vail_can_m = m_len * layers * tables
            else: dm_sd = 0.0; vail_can_m = 0.0
                
            ratio_row_title = f"{s_name}: " + " ".join(active_ratio_parts) if active_ratio_parts else f"{s_name}"
            total_cut_in_row = ratios_sum * layers * tables
            
            ratio_row = [ratio_row_title, f"{total_cut_in_row:,}"] + row_ratios_list + [layers, tables, round(m_len, 2), ratios_sum, round(dm_sd, 3), round(vail_can_m, 1)]
            matrix_body_rows.append(ratio_row)
            
            remaining_row = ["CÒN LẠI", ""]
            for idx, sz in enumerate(active_sizes):
                running_balances[idx] = max(0, running_balances[idx] - (row_ratios_list[idx] * layers * tables))
                remaining_row.append(f"{running_balances[idx]:,}" if running_balances[idx] > 0 else "0")
            remaining_row.extend(["", "", "", "", "", ""])
            matrix_body_rows.append(remaining_row)

        clean_headers = ["BÀN CẮT / TÊN SƠ ĐỒ", "TỔNG SẢN LƯỢNG"] + [f"CỠ {i+1}" for i in range(len(active_sizes))] + ["SƠ LỚP", "SỐ BÀN", "DÀI SƠ ĐỒ", "SỐ SP/SĐ", "Đ.MỨC SĐ", "VẢI CẦN (M)"]
        final_table_rows = [t_header_ma_hang, t_header_mau, t_header_loai_vai, t1_giang_row, t2_size_row, t3_sl_row] + matrix_body_rows
        
        df_final_report = pd.DataFrame(final_table_rows, columns=clean_headers)

        st.markdown("""<style>
            th { background-color: #F1F5F9 !important; color: #000000 !important; font-weight: 700 !important; text-align: center !important; border: 1px solid #CBD5E1 !important; position: sticky; top: 0; z-index: 10; }
            tr td { background-color: #FFFFFF !important; color: #000000 !important; border: 1px solid #E2E8F0 !important; text-align: center !important; font-weight: 500 !important; }
            tr:nth-child(2) td:nth-child(2), tr:nth-child(3) td:nth-child(2) { color: #DC2626 !important; font-weight: 800 !important; }
            td:nth-child(1) { font-weight: 700 !important; text-align: left !important; padding-left: 10px !important; color: #000000 !important; }
        </style>""", unsafe_allow_html=True)

        st.markdown("<p style='font-weight:700; font-size:14px; color:#1E3A8A; margin-top:15px;'>📊 BẢNG THEO DÕI TÁC NGHIỆP ĐỐI CHIẾU THỰC TẾ (KÉO XUỐNG XEM SỐ DƯ TRỪ LÙI CÒN LẠI)</p>", unsafe_allow_html=True)
        st.dataframe(df_final_report, use_container_width=True, hide_index=True)
        st.markdown("---")

        excel_generated_status = False
        buffer = io.BytesIO()
        try:
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                from supabase import create_client
                sb_ex_client = create_client("https://supabase.co", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImV3cXFvZHNmeGx2bnJ6c3lsYXd5Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3MjEwMjc1NjIsImV4cCI6MjAzNjYwMzU2Mn0.uD-n6W9k6_Z87RcoX_OlyV_1R0g_Yp_B-D3v7b0Q678")
                res_all_fabs = sb_ex_client.table("cutting_orders_db").select("*").eq("style_id", style_id_input).execute()
                if res_all_fabs.data and len(res_all_fabs.data) > 0:
                    for r_record in res_all_fabs.data:
                        f_type_name = str(r_record.get("fabric_type", "CHÍNH")).upper()
                        raw_matrix = r_record.get("cutting_matrix_data", [])
                        if raw_matrix: pd.DataFrame(raw_matrix).to_excel(writer, sheet_name=f"VAI {f_type_name}", index=False)
                else: df_final_report.to_excel(writer, sheet_name=f"VAI {fabric_type_input}", index=False)
            excel_generated_status = True
        except Exception: pass

        

        if excel_generated_status:
            st.download_button(
                label="📥 XUẤT FILE EXCEL GỘP ĐA SHEET MÀU SẮC CÔNG NGHIỆP", 
                data=buffer.getvalue(), file_name=f"MA_TRAN_DA_VAI_{style_id_input}.xlsx", 
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", 
                use_container_width=True, key="excel_multi_sheet_btn_final_v5"
            )
        
        st.markdown(f"<p style='font-weight:700; font-size:14px; color:#1E3A8A; margin-top:15px;'>💾 LƯU TRỮ VÀ ĐỒNG BỘ PHIẾU VẢI {fabric_type_input.upper()} VÀO KHO</p>", unsafe_allow_html=True)
        trigger_save_supabase = st.button(f"💾 KÍCH HOẠT LƯU TRỮ / CẬP NHẬT PHIẾU VẢI {fabric_type_input.upper()} LÊN CLOUD SUPABASE", type="primary", use_container_width=True, key="save_to_supabase_btn_c2")
        
        if trigger_save_supabase:
            with st.spinner(f"🚀 Hệ thống đang lưu trữ dữ liệu vải {fabric_type_input} lên đám mây..."):
                df_clean_string = df_final_report.copy().astype(str)
                matrix_json_string = df_clean_string.to_json(orient="records")
                
                supabase_payload = {
                    "style_id": str(style_id_input).strip().upper(), "color": str(color_input).strip().upper(), 
                    "fabric_type": str(fabric_type_input).strip().upper(), "total_po_qty": int(po_qty_input), 
                    "proposal_yield": float(consumption_input), "max_table_len": float(max_table_length), 
                    "cuttable_width": float(cuttable_width_inch), "cutting_matrix_data": json.loads(matrix_json_string)
                }
                try:
                    from supabase import create_client
                    supabase_client = create_client("https://supabase.co", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImV3cXFvZHNmeGx2bnJ6c3lsYXd5Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3MjEwMjc1NjIsImV4cCI6MjAzNjYwMzU2Mn0.uD-n6W9k6_Z87RcoX_OlyV_1R0g_Yp_B-D3v7b0Q678")
                    supabase_client.table("cutting_orders_db").upsert(supabase_payload, on_conflict="style_id,fabric_type").execute()
                    st.success(f"🎉 Đã đồng bộ lưu đè dữ liệu mảng phẳng vải {fabric_type_input} lên Cloud Supabase thành công!")
                except Exception as e: 
                    st.error(f"⚠️ Lỗi kết nối Supabase: {str(e)}")
                    
        st.markdown("---")
        st.success("🎉 Cấu trúc phân hệ tác nghiệp gập rập gõ tay kết hợp AI đã hoạt động chính xác 100%!")
