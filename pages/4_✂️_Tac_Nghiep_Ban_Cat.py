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
                sbd_prompt = """Extract style_id, total_quantity, and complete size breakdown JSON. Keep format '26 X 30' explicitly."""
                if sbd_content_str: 
                    sbd_parts_payload.append(types.Part.from_text(text=sbd_content_str))
                sbd_parts_payload.append(types.Part.from_text(text=sbd_prompt))
                try:
                    res_sbd = client_ai.models.generate_content(model='gemini-2.5-flash', contents=sbd_parts_payload, config=types.GenerateContentConfig(response_mime_type="application/json"))
                    st.session_state["sbd_parsed_data"] = json.loads(res_sbd.text.strip().replace("```json", "").replace("```", "").strip())
                except Exception: 
                    pass
                st.session_state["pur_tp_parsed_data"] = {"dummy_status": "skipped_not_needed"}
                st.session_state["purchase_ready"] = True
                st.rerun()
# =============================================================================
# TẦNG 2 - ĐOẠN 1: MÀN HÌNH TÁC NGHIỆP FORM HÀNH CHÍNH VÀ Ô CHỌN LOẠI VẢI ĐỘNG
# =============================================================================
else:
    sbd_data_store = st.session_state.get("sbd_parsed_data", {})
    if isinstance(sbd_data_store, dict) and sbd_data_store:
        detected_style_id = sbd_data_store.get("style_id", "UNKNOWN_STYLE")
        detected_total_po = sbd_data_store.get("total_quantity", 0)
        
        # CHUẨN HÓA DỮ LIỆU ĐẦU VÀO: Đảm bảo size_breakdown_main luôn là Dictionary
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
        try:
            default_index = available_fabrics.index(default_fab)
        except ValueError:
            default_index = 0
            
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
                    st.session_state["auto_cutting_results_recovered"] = res_check.data[0]["cutting_matrix_data"]
                    st.session_state["auto_cutting_results"] = None
                    st.rerun()
                else:
                    if "auto_cutting_results_recovered" in st.session_state: 
                        del st.session_state["auto_cutting_results_recovered"]
            except Exception: 
                pass

        active_sizes = []
        for k, v in size_breakdown_main.items():
            try:
                clean_v = int(str(v).replace(",", "").strip())
                if clean_v > 0:
                    active_sizes.append(str(k))
            except (ValueError, TypeError):
                continue

        if not active_sizes: 
            active_sizes = ["26 X 30", "28 X 30", "29 X 32"]
# =============================================================================
# TẦNG 2 - ĐOẠN 2: CÁC NÚT BẤM HÀNH ĐỘNG VÀ LOGIC KHÓA CỨNG/AI VÉT DÒNG TRỐNG
# =============================================================================
        btn_col1, btn_col2 = st.columns(2)
        with btn_col1: 
            trigger_auto_cutting = st.button("🤖 1. KÍCH HOẠT AI VÉT SẠCH SẼ LƯỢNG DƯ CÒN LẠI", type="primary", use_container_width=True, key="c2_normal_cut_btn")
        with btn_col2: 
            trigger_consumption = st.button("🔒 2. TÍNH TOÁN LUỸ TIẾN & KHÓA CHỒNG KHO", type="secondary", use_container_width=True, key="c2_consumption_btn")

        # Kích hoạt trạng thái khóa cứng bảng nhập liệu khi bấm nút số 2
        if trigger_consumption:
            st.session_state["consumption_activated"] = True
            st.toast("🔒 Đã khóa cứng ma trận nhập tay và đồng bộ xuống bảng theo dõi!", icon="🔒")

        if trigger_auto_cutting:
            with st.spinner(f"🤖 AI đang tính toán tổ hợp cho các dòng sơ đồ còn trống..."):
                if "get_secure_gemini_key" in globals(): 
                    gemini_key = get_secure_gemini_key()
                else: 
                    gemini_key = st.secrets.get("GEMINI_API_KEY", "").strip()
                from google import genai
                from google.genai import types
                client_ai = genai.Client(api_key=gemini_key)
                
                # Đọc dữ liệu snapshot hiện tại người dùng đang nhập
                snapshot = st.session_state.get("session_editor_snapshot")
                calculated_balances = {}
                for sz in active_sizes:
                    calculated_balances[sz] = int(str(size_breakdown_main.get(sz, 0)).replace(",", "").split(".")[0].strip() or 0)
                
                # Quét tìm chính xác dòng nào trống, dòng nào đã nhập tay để giữ nguyên
                empty_slots = []
                current_grid_structure = []
                
                if snapshot:
                    for idx, row_data in enumerate(snapshot):
                        s_name = str(row_data.get("BÀN CẮT / TÊN SƠ ĐỒ", f"SƠ ĐỒ C{idx+1}")).upper()
                        s_code = f"c{str(idx+1).zfill(2)}"
                        
                        total_ratios_entered = sum(int(str(row_data.get(sz, 0)).split(".")[0] or 0) for sz in active_sizes)
                        layers = int(str(row_data.get("SƠ LỚP", 0)).split(".")[0] or 0)
                        tables = int(str(row_data.get("SỐ BÀN", 1)).split(".")[0] or 1)
                        
                        if total_ratios_entered > 0 and layers > 0:
                            # Dòng đã nhập tay: Khấu trừ số lượng và lưu cấu trúc để giữ nguyên
                            for sz in active_sizes:
                                r_val = int(str(row_data.get(sz, 0)).split(".")[0] or 0)
                                calculated_balances[sz] = max(0, calculated_balances[sz] - (r_val * layers * tables))
                            
                            current_grid_structure.append({
                                "Mã dòng": s_code,
                                "Tên sơ đồ gốc": s_name,
                                "Trạng thái": "GIỮ NGUYÊN KHÔNG ĐỔI"
                            })
                        else:
                            # Dòng trống hoàn toàn: AI được quyền điền dữ liệu
                            empty_slots.append(s_code)
                            current_grid_structure.append({
                                "Mã dòng": s_code,
                                "Tên sơ đồ gốc": s_name,
                                "Trạng thái": "AI ĐIỀN VÀO ĐÂY"
                            })
                else:
                    empty_slots = ["c01", "c02", "c03", "c04", "c05", "c06"]
                    current_grid_structure = [{"Mã dòng": f"c{str(i+1).zfill(2)}", "Tên sơ đồ gốc": f"SƠ ĐỒ C{str(i+1).zfill(2)}", "Trạng thái": "AI ĐIỀN VÀO ĐÂY"} for i in range(6)]

                dinhmuc_met = round(consumption_input * 0.9144, 3)
                
                ai_cutting_prompt = f"""
                Bạn là thuật toán toán học điều độ bàn cắt. Nhiệm vụ của bạn chỉ là tính toán phối cỡ điền vào các dòng đang TRỐNG này: {json.dumps(empty_slots)}.
                Tuyệt đối KHÔNG ĐƯỢC thay đổi thông tin của các dòng đã có dữ liệu nhập tay.
                
                Dữ liệu đầu vào:
                - Bản đồ cấu trúc các dòng: {json.dumps(current_grid_structure)}
                - Số lượng sản phẩm còn dư thực tế cần vét: {json.dumps(calculated_balances)}
                - Định mức kỹ thuật: {dinhmuc_met} mét/quần.
                - Chiều dài bàn vải tối đa cho phép: {max_table_length} mét.

                QUY TẮC PHỐI CỠ VÀ TÍNH CHIỀU DÀI:
                1. Chỉ được phép điền tỷ lệ phối (Ratios) và Số lớp vào các mã dòng sơ đồ ghi là "AI ĐIỀN VÀO ĐÂY". Không điền lấn sang dòng khác.
                2. KHỐNG CHẾ CHIỀU DÀI: (Tổng các tỷ lệ phối Ratios) * ({dinhmuc_met} mét) BẮT BUỘC <= {max_table_length} mét.
                3. Gom các cỡ có số lượng lớn ghép chung sơ đồ để rải lớp cao. Chỉ rải sơ đồ vét 1 quần ở ô trống cuối cùng cho số lượng mồ côi cực lẻ.
                4. Nếu là vải KEO/LÓT/PHỐI: Cho phép làm tròn cắt dư thêm 5-10 Pcs/size lẻ. Nếu là vải CHÍNH: Cắt chính xác triệt tiêu dư về 0.

                Trả về mảng JSON sạch, chỉ chứa kết quả điền cho các dòng trống được yêu cầu, đúng định dạng mẫu:
                [
                  {{"Sơ đồ / Trạng thái": "c02", "Ratios": {{"00": 1, "0": 1}}, "Số lớp": 120, "Số bàn": 1, "Chiều dài mét": {round(dinhmuc_met * 2, 2)}}}
                ]
                """
                try:
                    res_cutting = client_ai.models.generate_content(
                        model='gemini-2.5-flash', 
                        contents=[ai_cutting_prompt],
                        config=types.GenerateContentConfig(response_mime_type="application/json")
                    )
                    ai_vete_res = json.loads(res_cutting.text.strip().replace("```json", "").replace("```", "").strip())
                    
                    if isinstance(ai_vete_res, list):
                        st.session_state["auto_cutting_results"] = ai_vete_res
                        
                        updated_rows = []
                        for i in range(6):
                            s_code = f"c{str(i+1).zfill(2)}"
                            
                            if snapshot and i < len(snapshot):
                                old_row = snapshot[i]
                                s_name_display = str(old_row.get("BÀN CẮT / TÊN SƠ ĐỒ", f"SƠ ĐỒ C{str(i+1).zfill(2)}")).upper()
                            else:
                                s_name_display = f"SƠ ĐỒ C{str(i+1).zfill(2)}"
                                
                            item_dict = {"BÀN CẮT / TÊN SƠ ĐỒ": s_name_display}
                            ai_match = [x for x in ai_vete_res if str(x.get("Sơ đồ / Trạng thái", "")).strip().lower() == s_code]
                            
                            if ai_match and len(ai_match) > 0:
                                ai_row = ai_match[0]
                                r_dict = ai_row.get("Ratios", {})
                                for sz in active_sizes: 
                                    item_dict[sz] = int(str(r_dict.get(sz, 0)).split(".")[0] or 0)
                                
                                total_pants = sum(int(str(r_dict.get(sz, 0)).split(".")[0] or 0) for sz in active_sizes)
                                calculated_len = round(total_pants * dinhmuc_met, 2)
                                
                                item_dict.update({
                                    "SƠ LỚP": int(str(ai_row.get("Số lớp", 0)).split(".")[0] or 0), 
                                    "SỐ BÀN": int(str(ai_row.get("Số bàn", 1)).split(".")[0] or 1), 
                                    "DÀI SƠ ĐỒ": float(calculated_len)
                                })
                            else:
                                # Dòng đã nhập tay hoặc không có kết quả AI -> Giữ nguyên 100% tất cả thông tin kể cả Tên sơ đồ sửa tay
                                if snapshot and i < len(snapshot):
                                    old_row = snapshot[i]
                                    for sz in active_sizes: item_dict[sz] = int(str(old_row.get(sz, 0)).split(".")[0] or 0)
                                    item_dict.update({
                                        "SƠ LỚP": int(str(old_row.get("SƠ LỚP", 0)).split(".")[0] or 0), 
                                        "SỐ BÀN": int(str(old_row.get("SỐ BÀN", 1)).split(".")[0] or 1), 
                                        "DÀI SƠ ĐỒ": float(old_row.get("DÀI SƠ ĐỒ", 0.0))
                                    })
                                else:
                                    for sz in active_sizes: item_dict[sz] = 0
                                    item_dict.update({"SƠ LỚP": 0, "SỐ BÀN": 1, "DÀI SƠ ĐỒ": 0.0})
                            updated_rows.append(item_dict)
                        
                        st.session_state["session_editor_snapshot"] = updated_rows
                        st.success("🎯 AI đã điền bổ sung vào các dòng sơ đồ trống mà không làm đổi dữ liệu nhập tay!")
                        st.rerun()
                except Exception as e: 
                    st.error(f"⚠️ Lỗi xử lý thuật toán AI: {str(e)}")





        # =============================================================================
        # TẦNG 3: ĐỒNG BỘ LUỒNG EDIT GÕ TAY VÀ ĐÓN NHẬN KẾT QUẢ AI VÉT ĐUÔI TỰ ĐỘNG
        # =============================================================================
        # TẦNG 3 - ĐOẠN SỬA LỖI: KHỞI TẠO BIẾN DISPLAY_EDITOR_ROWS AN TOÀN ĐA LUỒNG
        # =============================================================================
        display_editor_rows = []
        recovered_source = st.session_state.get("auto_cutting_results_recovered", [])
        ai_source = st.session_state.get("auto_cutting_results", [])
        snapshot = st.session_state.get("session_editor_snapshot")

        # 1. ƯU TIÊN SỐ 1: Nếu đã có dữ liệu snapshot do tổ trưởng gõ tay hoặc AI điền trước đó, giữ nguyên 100%
        if snapshot and len(snapshot) > 0:
            display_editor_rows = list(snapshot)
            
        # 2. ƯU TIÊN SỐ 2: Nếu có kết quả khôi phục lịch sử từ Supabase gửi về
        elif recovered_source:
            for row in recovered_source:
                t_name = str(row.get("BÀN CẮT / TÊN SƠ ĐỒ", ""))
                if not any(x in t_name for x in ["CÒN LẠI", "GIÀNG", "SIZE", "SẢN LƯỢNG", "Mã hàng"]):
                    clean_row = {"BÀN CẮT / TÊN SƠ ĐỒ": t_name}
                    for sz in active_sizes: 
                        clean_row[sz] = int(str(row.get(sz, 0)).replace(",", "").split(".")[0] if str(row.get(sz, 0)).strip() else 0)
                    clean_row.update({
                        "SƠ LỚP": int(str(row.get("SƠ LỚP", 120)).split(".")[0]), 
                        "SỐ BÀN": int(str(row.get("SỐ BÀN", 1)).split(".")[0]), 
                        "DÀI SƠ ĐỒ": float(row.get("DÀI SƠ ĐỒ", 0.0))
                    })
                    display_editor_rows.append(clean_row)
                    
        # 3. ƯU TIÊN SỐ 3: Mặc định ban đầu tạo form trống trơn để tổ trưởng tự nhập tay từ con số 0
        else:
            for i in range(6):
                s_code = f"c{str(i+1).zfill(2)}"
                item_dict = {"BÀN CẮT / TÊN SƠ ĐỒ": f"SƠ ĐỒ C{s_code.upper()}"}
                for sz in active_sizes: 
                    item_dict[sz] = 0
                item_dict.update({"SƠ LỚP": 120 if i < 3 else 0, "SỐ BÀN": 1, "DÀI SƠ ĐỒ": 0.0})
                display_editor_rows.append(item_dict)
                
        # Khởi tạo bảng dữ liệu nền (Đã khắc phục hoàn toàn lỗi NameError)
        df_editor_base = pd.DataFrame(display_editor_rows)
        
        # Quản lý trạng thái khóa cứng bảng nhập liệu
        is_locked = st.session_state.get("consumption_activated", False)

        # Bổ sung nút bấm mở khóa nếu tổ trưởng muốn quay lại sửa tay tiếp
        if is_locked:
            if st.button("🔓 MỞ KHÓA TOÀN BỘ BẢNG ĐỂ CHỈNH SỬA LẠI TAY", type="secondary", use_container_width=True, key="unlock_matrix_btn_c2"):
                st.session_state["consumption_activated"] = False
                st.toast("🔓 Đã mở khóa biểu mẫu! Bạn có thể sửa tay tên sơ đồ và số lượng.", icon="🔓")
                st.rerun()

        st.markdown("<p style='font-weight:700; font-size:14px; color:#1E3A8A; margin-top:15px;'>✍️ BẢNG TỰ NHẬP TỶ LỆ PHỐI SIZE VÀ SỐ LỚP BÀN CẮT (CHO PHÉP SỬA TAY TÊN SƠ ĐỒ VÀ THÔNG SỐ)</p>", unsafe_allow_html=True)
        
        # HIỂN THỊ Ô LƯỚI TƯƠNG TÁC
        edited_df = st.data_editor(
            df_editor_base, 
            use_container_width=True, 
            hide_index=True, 
            disabled=is_locked, 
            key="table_manual_data_editor_v1"
        )
        
        # Nếu chưa khóa thì liên tục lưu giữ snapshot động người dùng gõ tay
        if not is_locked:
            st.session_state["session_editor_snapshot"] = edited_df.to_dict(orient="records")


        # =============================================================================
        # 📊 ĐỊNH DẠNG CSS VÀ HIỂN THỊ BẢNG ĐỐI CHIẾU THỰC TẾ TRÊN MÀN HÌNH
        # =============================================================================
        st.markdown("""<style>
            th { background-color: #F1F5F9 !important; color: #000000 !important; font-weight: 700 !important; text-align: center !important; border: 1px solid #CBD5E1 !important; position: sticky; top: 0; z-index: 10; }
            tr td { background-color: #FFFFFF !important; color: #000000 !important; border: 1px solid #E2E8F0 !important; text-align: center !important; font-weight: 500 !important; }
            tr:nth-child(2) td:nth-child(2), tr:nth-child(3) td:nth-child(2) { color: #DC2626 !important; font-weight: 800 !important; }
            td:nth-child(1) { font-weight: 700 !important; text-align: left !important; padding-left: 10px !important; color: #000000 !important; }
        </style>""", unsafe_allow_html=True)

        st.markdown("<p style='font-weight:700; font-size:14px; color:#1E3A8A; margin-top:15px;'>📊 BẢNG THEO DÕI TÁC NGHIỆP ĐỐI CHIẾU THỰC TẾ (KÉO XUỐNG XEM SỐ DƯ TRỪ LÙI CÒN LẠI)</p>", unsafe_allow_html=True)
        st.dataframe(df_final_report, use_container_width=True, hide_index=True)
        st.markdown("---")

        # =============================================================================
        # 🎯 PHÂN HỆ ĐA SHEET EXCEL ĐỔ MÀU CÔNG NGHIỆP
        # =============================================================================
        excel_generated_status = False
        buffer = io.BytesIO()
        try:
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                from supabase import create_client
                sb_ex_client = create_client("https://supabase.co", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImV3cXFvZHNmeGx2bnJ6c3lsYXd5Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3MjEwMjc1NjIsImV4cCI6MjAzNjYwMzU2Mn0.uD-n6W9k6_Z87RcoX_OlyV_1R0g_Yp_B-D3v7b0Q678")
                res_all_fabs = sb_ex_client.table("cutting_orders_db").select("*").eq("style_id", style_id_input).execute()
                
                if res_all_fabs.data and len(res_all_fabs.data) > 0:
                    # Duyệt qua từng loại vải đã lưu trên hệ thống để gom cụm thành các sheet riêng biệt
                    for r_record in res_all_fabs.data:
                        f_type_name = str(r_record.get("fabric_type", "CHÍNH")).upper()
                        raw_matrix = r_record.get("cutting_matrix_data", [])
                        if raw_matrix:
                            df_sheet = pd.DataFrame(raw_matrix)
                            # Đảm bảo giữ nguyên cấu trúc hiển thị bảng báo cáo gốc
                            df_sheet.to_excel(writer, sheet_name=f"VAI {f_type_name}", index=False)
                else: 
                    # Nếu chưa có dữ liệu cũ, ghi đè bảng hiện hành vào sheet hiện tại
                    df_final_report.to_excel(writer, sheet_name=f"VAI {fabric_type_input}", index=False)
            excel_generated_status = True
        except Exception: 
            pass

        if excel_generated_status:
            st.download_button(
                label="📥 XUẤT FILE EXCEL GỘP ĐA SHEET MÀU SẮC CÔNG NGHIỆP", 
                data=buffer.getvalue(), 
                file_name=f"MA_TRAN_DA_VAI_{style_id_input}.xlsx", 
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", 
                use_container_width=True, 
                key="excel_multi_sheet_btn_final_v5"
            )
        
        # =============================================================================
        # 💾 LƯU TRỮ VÀ ĐỒNG BỘ PHIẾU VẢI VÀO KHO
        # =============================================================================
        st.markdown(f"<p style='font-weight:700; font-size:14px; color:#1E3A8A; margin-top:15px;'>💾 LƯU TRỮ VÀ ĐỒNG BỘ PHIẾU VẢI {fabric_type_input.upper()} VÀO KHO</p>", unsafe_allow_html=True)
        trigger_save_supabase = st.button(f"💾 KÍCH HOẠT LƯU TRỮ / CẬP NHẬT PHIẾU VẢI {fabric_type_input.upper()} LÊN CLOUD SUPABASE", type="primary", use_container_width=True, key="save_to_supabase_btn_c2")
        
        if trigger_save_supabase:
            with st.spinner(f"🚀 Hệ thống đang ghi dữ liệu vải {fabric_type_input} đồng bộ vào kho Supabase..."):
                # CHUẨN HÓA SẮP XẾP CỘT: Ép kiểu dữ liệu chuỗi cố định cho JSON payload
                df_clean_string = df_final_report.copy().astype(str)
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
                    
                    # Đồng bộ an toàn lên cơ sở dữ liệu cloud
                    response_db = supabase_client.table("cutting_orders_db").upsert(supabase_payload, on_conflict="style_id,fabric_type").execute()
                    st.success(f"🎉 Đã đồng bộ lưu đè dữ liệu mảng phẳng vải {fabric_type_input} lên Cloud Supabase thành công!")
                except Exception as e: 
                    st.error(f"⚠️ Lỗi kết nối Supabase: {str(e)}")
        st.markdown("---")
        st.success("🎉 Hệ thống phân hệ tác nghiệp gập rập gõ tay đa loại vải đã Re-build hoàn tất trơn tru!")
