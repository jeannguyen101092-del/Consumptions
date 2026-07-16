import streamlit as st
import pandas as pd
import json
import io
import re
from supabase import create_client

# Cấu hình trang luôn luôn đặt ở dòng đầu tiên của ứng dụng
st.set_page_config(layout="wide")

# =============================================================================
# TẦNG 1: SỐ HÓA FILE SBD HOẶC GỌI TRỰC TIẾP PHIẾU CŨ TỪ CLOUD SUPABASE
# =============================================================================

# Khởi tạo kết nối Supabase bảo mật tuyệt đối qua Streamlit Secrets
# (Vui lòng cấu hình SUPABASE_URL và SUPABASE_KEY trong file .streamlit/secrets.toml)
try:
    url_direct = st.secrets["SUPABASE_URL"]
    key_direct = st.secrets["SUPABASE_KEY"]
except Exception:
    # Cơ chế dự phòng an toàn nếu chạy local chưa thiết lập secrets
    url_direct = "https://supabase.co"
    key_direct = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." # Thay bằng chuỗi Key thực tế của bạn nếu chạy nội bộ

sb_load_client = create_client(url_direct, key_direct)

# Kiểm tra nếu hệ thống chưa nạp dữ liệu hoàn chỉnh thì hiển thị màn hình Ingest
if not st.session_state.get("purchase_ready", False):
    st.markdown("""
        <div class="card-container">
            <div class="card-section-header">📋 PHÂN HỆ TÁC NGHIỆP BÀN CẮT ĐA GIÀNG NÂNG CAO</div>
            <p style="color: #64748B; font-size:13px; margin:0;">
                Tải lên File SBD (Excel/PDF) để tính toán tác nghiệp mới, HOẶC chọn tra cứu nhanh phiếu cũ bên dưới.
            </p>
        </div>
    """, unsafe_allow_html=True)
    
    # Tải danh sách các mã hàng cũ đã lưu trên hệ thống đám mây
    history_styles = ["-- Chọn mã hàng cũ đã lưu trên Supabase --"]
    try:
        res_history = sb_load_client.table("cutting_orders_db").select("style_id", "fabric_type").execute()
        if res_history.data:
            for item in res_history.data:
                label = f"{item['style_id']} - VẢI: {item['fabric_type']}"
                if label not in history_styles: 
                    history_styles.append(label)
    except Exception as e: 
        st.error(f"⚠️ Không thể tải danh sách lịch sử tác nghiệp: {str(e)}")

    selected_old_record = st.selectbox(
        "📂 Xem lại phiếu tác nghiệp cũ từ Supabase (Không cần up file):", 
        history_styles, 
        key="sb_outside_history_select"
    )
    
    # Xử lý khôi phục cấu trúc ma trận cũ nếu người dùng chọn từ danh sách lịch sử
    if selected_old_record != "-- Chọn mã hàng cũ đã lưu trên Supabase --":
        try:
            parts_str = selected_old_record.split(" - VẢI: ")
            st_id_search = str(parts_str[0]).strip()
            fb_tp_search = str(parts_str[1]).strip()
            
            # Đã sửa lỗi: Phương thức lọc .eq() và .limit() phải nằm TRƯỚC .execute()
            res_detail = (
                sb_load_client.table("cutting_orders_db")
                .select("*")
                .eq("style_id", st_id_search)
                .eq("fabric_type", fb_tp_search)
                .limit(1)
                .execute()
            )
            
            if res_detail.data and len(res_detail.data) > 0:
                old_data = res_detail.data[0]
                recovered_matrix = old_data.get("cutting_matrix_data", [])
                built_sizes_dict = {}
                
                # Trích xuất và bóc tách lại bảng size breakdown từ ma trận cũ
                if recovered_matrix and len(recovered_matrix) >= 6:
                    # Giả định hàng index 4 và 5 chứa thông số Size và Sản lượng
                    size_row_data = recovered_matrix[4] if len(recovered_matrix) > 4 else {}
                    qty_row_data = recovered_matrix[5] if len(recovered_matrix) > 5 else {}
                    
                    exclude_keywords = ["SƠ LỚP", "SỐ BÀN", "DÀI SƠ ĐỒ", "SỐ SP/SĐ", "Đ.MỨC SĐ", "VẢI CẦN"]
                    
                    for k_key, v_size in size_row_data.items():
                        if k_key != "BÀN CẮT / TÊN SƠ ĐỒ" and not any(x in k_key for x in exclude_keywords):
                            if v_size and str(v_size).strip() != "":
                                try:
                                    clean_qty = str(qty_row_data.get(k_key, "0")).replace(",", "")
                                    built_sizes_dict[str(v_size).strip()] = int(float(clean_qty))
                                except Exception:
                                    built_sizes_dict[str(v_size).strip()] = 0
                                    
                if not built_sizes_dict: 
                    built_sizes_dict = {"26 X 30": 100, "28 X 30": 100}
                    
                # Ghi dữ liệu khôi phục vào Session State
                st.session_state["sbd_parsed_data"] = {
                    "style_id": old_data.get("style_id"), 
                    "total_quantity": old_data.get("total_po_qty"), 
                    "size_breakdown": built_sizes_dict
                }
                
                if recovered_matrix:
                    st.session_state["auto_cutting_results_recovered"] = recovered_matrix
                    st.session_state["fabric_type_recovered"] = old_data.get("fabric_type", "CHÍNH")
                    
                st.session_state["pur_tp_parsed_data"] = {"dummy_status": "skipped_not_needed"}
                st.session_state["purchase_ready"] = True
                st.success("🔄 Đang đồng bộ cấu trúc dữ liệu cũ lên màn hình tác nghiệp...")
                st.rerun()
            else:
                st.warning("⚠️ Không tìm thấy dữ liệu chi tiết cho bản ghi này trên Supabase.")
        except Exception as e: 
            st.error(f"❌ Lỗi trong quá trình khôi phục dữ liệu: {str(e)}")
        
    st.markdown("<br><p style='font-size:13px; font-weight:700; color:#475569;'>HOẶC LẬP PHIẾU TÁC NGHIỆP MỚI BẰNG FILE SBD:</p>", unsafe_allow_html=True)
    file_sbd_c2 = st.file_uploader("📋 Chọn File SBD Số Lượng Đơn Hàng (Excel/PDF)", type=["xlsx", "xls", "pdf"], key="purchase_sbd_c2_unique")
import streamlit as st
import pandas as pd
import json
import io
from pydantic import BaseModel, Field
from typing import Dict
from google import genai
from google.genai import types

# Định nghĩa cấu trúc Schema cứng bằng Pydantic để ép Gemini trả về cấu trúc JSON sạch 100%
class SizeBreakdownModel(BaseModel):
    style_id: str = Field(description="The unique identification code of the garment style.")
    total_quantity: int = Field(description="The sum of all ordering or cutting quantities across all sizes.")
    size_breakdown: Dict[str, int] = Field(description="A dictionary where keys are size names and values are their corresponding quantities as pure integers.")

# =============================================================================
# TẦNG 1 - ĐOẠN 2: LIÊN KẾT PHÂN TÍCH FILE VÀ CHUẨN HÓA DỮ LIỆU ĐƠN HÀNG SBD
# =============================================================================

# CƠ CHẾ PHÒNG VỆ KHÓA CHẶN KHI BẤM NÚT XÓA TỪ TẦNG DƯỚI
if st.session_state.get("planning_cleared", False):
    st.session_state["purchase_ready"] = False
    st.session_state["sbd_parsed_data"] = None
    st.session_state["pur_tp_parsed_data"] = None

# 🎯 SỬA LỖI NAMERROR TRIỆT ĐỂ: 
# Lấy file trực tiếp từ session_state thông qua key duy nhất đã khai báo ở file_uploader trước đó.
# Nếu widget file_uploader chưa được tạo hoặc chưa có file, biến sẽ trả về None một cách an toàn.
uploaded_file_sbd = st.session_state.get("purchase_sbd_c2_unique", None)

# Chỉ tiến hành xử lý khi đã có file được upload và trạng thái hệ thống chưa sẵn sàng
if uploaded_file_sbd is not None and not st.session_state.get("purchase_ready", False):
    
    trigger_btn_c2 = st.button(
        "⚡ SỐ HÓA MA TRẬN SẢN LƯỢNG ĐƠN HÀNG TÁC NGHIỆP", 
        type="primary", 
        use_container_width=True, 
        key="activate_sbd_only_ingest_c2"
    )
    
    if trigger_btn_c2:
        with st.spinner("🚀 Hệ thống đang phân tích mảng phân bổ size phẳng từ file SBD..."):
            if "get_secure_gemini_key" in globals(): 
                gemini_key = get_secure_gemini_key()
            else: 
                gemini_key = st.secrets.get("GEMINI_API_KEY", "").strip()
            
            if not gemini_key:
                st.error("❌ Hệ thống chưa được cấu hình GEMINI_API_KEY trong file secrets.toml.")
                st.stop()
                
            try:
                client_ai = genai.Client(api_key=gemini_key)
                sbd_bytes = uploaded_file_sbd.getvalue()
                sbd_content_str = ""
                sbd_parts_payload = []
                
                # Phân tích cú pháp File Excel
                if uploaded_file_sbd.name.lower().endswith(('.xlsx', '.xls')):
                    try:
                        excel_data = pd.read_excel(io.BytesIO(sbd_bytes), sheet_name=None)
                        for sheet_name, df_sheet in excel_data.items(): 
                            sbd_content_str += f"\n--- SHEET: {sheet_name} ---\n{df_sheet.fillna('').to_csv(index=False)}"
                    except Exception as e:
                        st.warning(f"⚠️ Trình đọc dữ liệu Excel dạng bảng gặp lỗi nhỏ: {str(e)}")
                        
                # Phân tích cú pháp File PDF        
                elif uploaded_file_sbd.name.lower().endswith('.pdf'): 
                    sbd_parts_payload.append(types.Part.from_bytes(data=sbd_bytes, mime_type='application/pdf'))
                
                sbd_prompt = """
                Analyze the uploaded garment production file. Extract style_id, total_quantity, and the complete size breakdown numbers.
                
                CRITICAL INSTRUCTIONS FOR QUANTITIES:
                1. Identify the rows containing the actual ordering or cutting quantities distributed under each size column.
                2. Extract the numbers as pure integers. If numbers contain commas (e.g., 1,250), strip the comma and save as 1250.
                3. Map everything into the requested JSON schema perfectly.
                """
                
                if sbd_content_str: 
                    sbd_parts_payload.append(types.Part.from_text(text=sbd_content_str))
                sbd_parts_payload.append(types.Part.from_text(text=sbd_prompt))
                
                # Gọi API Gemini 2.5 với cấu trúc JSON định hình sẵn
                res_sbd = client_ai.models.generate_content(
                    model='gemini-2.5-flash', 
                    contents=sbd_parts_payload, 
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=SizeBreakdownModel,
                        temperature=0.1
                    )
                )
                
                parsed_json_data = json.loads(res_sbd.text.strip())
                
                # Chuẩn hóa lại kiểu dữ liệu của số lượng (ép kiểu Integer)
                if "size_breakdown" in parsed_json_data and isinstance(parsed_json_data["size_breakdown"], dict):
                    clean_dict = {}
                    for k, v in parsed_json_data["size_breakdown"].items():
                        try:
                            clean_key = str(k).strip().upper()
                            clean_dict[clean_key] = int(float(str(v).replace(",", "").strip() or 0))
                        except Exception:
                            clean_dict[str(k).strip().upper()] = 0
                    parsed_json_data["size_breakdown"] = clean_dict
                    
                # Cập nhật trạng thái ứng dụng
                st.session_state["sbd_parsed_data"] = parsed_json_data
                
                keys_to_clear_cache = [
                    "session_editor_snapshot", 
                    "auto_cutting_results", 
                    "auto_cutting_results_recovered", 
                    "fabric_type_recovered"
                ]
                for cache_key in keys_to_clear_cache:
                    if cache_key in st.session_state:
                        st.session_state[cache_key] = None
                        
                st.session_state["pur_tp_parsed_data"] = {"dummy_status": "skipped_not_needed"}
                st.session_state["purchase_ready"] = True
                st.session_state["planning_cleared"] = False
                
                st.success("✅ Hệ thống đã số hóa dữ liệu đơn hàng thành công!")
                st.rerun()
                
            except Exception as e: 
                st.error(f"❌ Lỗi nghiêm trọng khi giải cấu trúc tài liệu bằng AI: {str(e)}")



import streamlit as st
import pandas as pd
import json
import re
from supabase import create_client

# Cấu hình kết nối bảo mật sử dụng chung cấu trúc Secrets của Đoạn 1
try:
    url_direct = st.secrets["SUPABASE_URL"]
    key_direct = st.secrets["SUPABASE_KEY"]
except Exception:
    # 🎯 FIX LỖI 404: Đổi URL trang chủ thành chuỗi rỗng để chặn gọi nhầm khi thiếu Secrets
    url_direct = ""
    key_direct = ""

# Hàm callback xử lý tự động tra cứu dữ liệu cũ từ Supabase khi người dùng đổi loại vải
def handle_fabric_change():
    # Lấy giá trị mới nhất trực tiếp từ key của selectbox
    current_fabric = st.session_state.get("fabric_selectbox_key")
    st.session_state["last_checked_fabric"] = current_fabric
    
    if url_direct and key_direct:
        try:
            sb_client_check = create_client(url_direct, key_direct)
            # Lấy style_id trực tiếp từ session state hoặc widget key để đảm bảo dữ liệu mới nhất
            current_style = st.session_state.get("style_id_input_key", "").strip().upper()
            
            res_check = (
                sb_client_check.table("cutting_orders_db")
                .select("*")
                .eq("style_id", current_style)
                .eq("fabric_type", current_fabric)
                .limit(1)
                .execute()
            )
            
            if res_check.data and len(res_check.data) > 0:
                # Trích xuất phần tử đầu tiên an toàn
                st.session_state["auto_cutting_results_recovered"] = res_check.data[0].get("cutting_matrix_data", [])
                st.session_state["auto_cutting_results"] = None
            else:
                if "auto_cutting_results_recovered" in st.session_state: 
                    del st.session_state["auto_cutting_results_recovered"]
        except Exception as e: 
            st.error(f"⚠️ Trục trặc khi kiểm tra bộ nhớ đám mây: {str(e)}")
    else:
        st.warning("⚠️ Chưa cấu hình thông tin Supabase Secrets đầy đủ để tra cứu dữ liệu lịch sử.")

# Khối xử lý hiển thị chính nằm trong nhánh điều kiện True của "purchase_ready"
if st.session_state.get("purchase_ready", False):
    sbd_data_store = st.session_state.get("sbd_parsed_data", {})
    
    if isinstance(sbd_data_store, dict) and sbd_data_store:
        detected_style_id = sbd_data_store.get("style_id", "UNKNOWN_STYLE")
        detected_total_po = sbd_data_store.get("total_quantity", 0)
        
        # CHUẨN HÓA DỮ LIỆU ĐẦU VÀO: Đảm bảo bộ dữ liệu size luôn là một Dictionary phẳng
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
        
        # Thiết lập hàng nhập liệu số 1
        input_col1, input_col2, input_col3, input_col_color = st.columns(4)
        with input_col1: 
            style_id_input = st.text_input(
                "🏷️ Tên mã hàng (Style ID):", 
                value=str(detected_style_id).strip().upper(),
                key="style_id_input_key" # Gán key để lưu trạng thái phục vụ callback
            )
        with input_col2: 
            po_qty_input = st.number_input("📦 Số lượng đơn hàng (PO Pcs):", value=int(detected_total_po), step=100)
        with input_col3: 
            consumption_input = st.number_input("🎯 Định mức tài liệu đề xuất (Yds/Pcs):", value=1.140, step=0.001, format="%.3f")
        with input_col_color: 
            color_input = st.text_input("🎨 Tự gõ Màu vải:", value="BLACK")

        # Thiết lập hàng nhập liệu số 2
        input_col4, input_col5, input_col6 = st.columns(3)
        with input_col4: 
            max_table_length = st.number_input("📏 Chiều dài tối đa bàn vải (Meters):", value=12.00, step=1.0)
            
        default_fab = st.session_state.get("fabric_type_recovered", "CHÍNH")
        available_fabrics = ["CHÍNH", "LÓT", "KEO", "PHỐI"]
        try: 
            default_index = available_fabrics.index(default_fab)
        except ValueError: 
            default_index = 0
            
        with input_col5:
            # 🎯 FIX LỖI INFINITE LOOP: Sử dụng callback on_change thay vì kiểm tra if-else thủ công sau widget
            fabric_type_input = st.selectbox(
                "🧵 Loại vải đang tác nghiệp:", 
                available_fabrics, 
                index=default_index,
                key="fabric_selectbox_key",
                on_change=handle_fabric_change
            )
            
        with input_col6: 
            cuttable_width_inch = st.number_input("📐 KHỔ CẮT (Khổ vải đi sơ đồ - Inches):", value=56.00, step=0.50, format="%.2f")
        
        cad_paste_zone = st.text_area(
            "Sau khi xem cấu trúc phối size phía dưới, hãy đi sơ đồ trên máy CAD rồi copy dán kết quả [Tên sơ đồ + Chiều dài mét] vào đây:", 
            placeholder="Ví dụ:\n5844-c01 1.05\n5844-c02 10", 
            height=90, 
            key="cad_bulk_paste_c2"
        )

        # 🛠️ KHỬ TRIỆT ĐỂ CHUỖI MẢNG VÀ PHẲNG HÓA SIZE: Dọn sạch đuôi cột phát sinh từ Pandas (_1, _2)
        clean_size_breakdown = {}
        for k, v in size_breakdown_main.items():
            try:
                clean_key = re.sub(r'_\d+$', '', str(k)).strip().upper()
                
                # Bảo vệ mảng: Ép chuỗi cấu trúc mảng vô tình sinh ra từ file văn bản thành text may mặc tiêu chuẩn
                if clean_key.startswith("[") and clean_key.endswith("]"):
                    clean_key = clean_key.replace("[", "").replace("]", "").replace("'", "").replace('"', "").replace(",", "X").replace(" ", "")
                
                clean_v = int(float(str(v).replace(",", "").strip() or 0))
                if clean_v > 0:
                    clean_size_breakdown[clean_key] = clean_size_breakdown.get(clean_key, 0) + clean_v
            except Exception:
                continue
        
        size_breakdown_main = clean_size_breakdown

        # Thuật toán tối ưu sắp xếp danh sách kích cỡ bám hình học bàn vải (Inseam tăng dần -> Eo tăng dần)
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
                try: 
                    return (0, int(float(s_clean)))
                except ValueError: 
                    char_hash_code = sum(ord(c) for c in s_clean)
                    return (0, 1000 + char_hash_code)

        # Trích xuất mảng danh sách size sạch phẳng
        active_sizes = sorted(list(size_breakdown_main.keys()), key=key_sort_by_inseam_then_waist)
        if not active_sizes: 
            active_sizes = ["26X30", "28X30", "29X32"]

import streamlit as st
import pandas as pd
import json
import re

# =============================================================================
# TẦNG 2 - ĐOẠN 2a: CÁC NÚT BẤM HÀNH ĐỘNG VÀ KHẮC PHỤC HOÀN TOÀN LỖI EMPTY_SLOTS
# =============================================================================

# Khởi tạo cục bộ an toàn các thông số kỹ thuật được kế thừa từ Đoạn 3 hoặc widget keys
current_fabric_type = st.session_state.get("fabric_selectbox_key", "CHÍNH")
current_consumption = consumption_input if 'consumption_input' in locals() else 1.140

# Hàm helper tối ưu tốc độ ép số nguyên sạch cho dữ liệu ngành may
def safe_int(value, default=0):
    if value is None:
        return default
    try:
        clean_val = str(value).replace(",", "").strip()
        if not clean_val or clean_val.lower() == "none":
            return default
        return int(float(clean_val))
    except (ValueError, TypeError):
        return default

# Tạo Layout bảng điều khiển với 3 nút bấm phân hệ chính
btn_col1, btn_col2, btn_col_clear = st.columns([1.5, 1.5, 1])

with btn_col1: 
    trigger_auto_cutting = st.button("🤖 1. KÍCH HOẠT AI VÉT SẠCH SẼ LƯỢNG DƯ CÒN LẠI", type="primary", use_container_width=True, key="c2_normal_cut_btn")
with btn_col2: 
    trigger_consumption = st.button("🔒 2. TÍNH TOÁN LUỸ TIẾN & KHÓA CHỒNG KHO", type="secondary", use_container_width=True, key="c2_consumption_btn")
with btn_col_clear:
    trigger_clear_data = st.button("🧹 XÓA ĐỂ TÍNH LẠI", type="secondary", use_container_width=True, key="c2_clear_all_data_btn")

# 🎯 Xử lý Nút 3: Giải phóng bộ nhớ đệm và hạ cờ kích hoạt của bảng dưới
if trigger_clear_data:
    keys_to_reset = ["session_editor_snapshot", "auto_cutting_results", "consumption_activated"]
    for k in keys_to_reset:
        st.session_state[k] = None
        
    # Kích hoạt cờ xóa kế hoạch để bảo bộ máy Python toán học ở dưới ngừng xuất dữ liệu cũ
    st.session_state["planning_cleared"] = True
    
    st.toast("🧹 Đã làm sạch toàn bộ ô lưới tác nghiệp và phiếu báo cáo dưới!", icon="🧹")
    st.rerun()

# Xử lý Nút 2: Khóa cứng ma trận và tắt cờ xóa để kích hoạt rải số liệu xuống bảng dưới
if trigger_consumption:
    st.session_state["consumption_activated"] = True
    st.session_state["planning_cleared"] = False # Tắt cờ xóa để cấp quyền tính toán
    st.toast("🔒 Đã khóa cứng ma trận nhập tay và đồng bộ xuống bảng theo dõi!", icon="🔒")
    st.rerun() 

# Xử lý Nút 1: Kích hoạt thuật toán chuẩn bị cấu trúc gửi sang Gemini AI giải toán điều độ
if trigger_auto_cutting:
    st.session_state["planning_cleared"] = False # Tắt cờ xóa khi gọi AI
    
    # 🎯 FIX LỖI NAMERROR: Phục hồi mảng kích cỡ an toàn từ session_state gốc của file SBD
    sbd_store = st.session_state.get("sbd_parsed_data", {})
    local_size_breakdown = sbd_store.get("size_breakdown", {}) if isinstance(sbd_store, dict) else {}
    
    # Sử lại thuật toán sắp xếp cục bộ độc lập để phòng vệ NameError khi Rerun
    def local_sort_key(size_str):
        s_clean = str(size_str).upper().replace(" ", "").strip()
        parts = re.split(r'[X_-]', s_clean)
        if len(parts) >= 2:
            try: return (int(float(parts[1])), int(float(parts[0])))
            except ValueError: return (999, 999)
        try: return (0, int(float(s_clean)))
        except ValueError: return (0, 1000 + sum(ord(c) for c in s_clean))
        
    local_active_sizes = sorted(list(local_size_breakdown.keys()), key=local_sort_key)
    if not local_active_sizes:
        local_active_sizes = ["26X30", "28X30", "29X32"]

    with st.spinner("🤖 AI đang quét dữ liệu và giải ma trận phối cỡ cho các sơ đồ trống..."):
        if "get_secure_gemini_key" in globals(): 
            gemini_key = get_secure_gemini_key()
        else: 
            gemini_key = st.secrets.get("GEMINI_API_KEY", "").strip()
            
        if not gemini_key:
            st.error("❌ Ứng dụng chưa được cấu hình GEMINI_API_KEY trong file secrets.toml.")
            st.stop()
            
        from google import genai
        from google.genai import types
        client_ai = genai.Client(api_key=gemini_key)
        
        calculated_balances = {}
        for sz in local_active_sizes:
            calculated_balances[sz] = safe_int(local_size_breakdown.get(sz, 0))
        
        empty_slots = []
        current_grid_structure = []
        
        snapshot = st.session_state.get("session_editor_snapshot")

        if snapshot and isinstance(snapshot, list) and len(snapshot) > 0:
            for idx, row_data in enumerate(snapshot):
                s_name = str(row_data.get("BÀN CẮT / TÊN SƠ ĐỒ", f"SƠ ĐỒ C{idx+1}")).upper().strip()
                s_code = f"c{str(idx+1).zfill(2)}"
                
                total_ratios_entered = 0
                row_ratios = {}
                
                for sz in local_active_sizes:
                    # 🎯 FIX LỖI INDEX TOÁN HỌC: Kiểm tra key trực tiếp chuỗi kích cỡ tĩnh trước
                    r_val = safe_int(row_data.get(sz))
                    if r_val == 0:
                        # Cơ chế dự phòng tìm theo số thứ tự cột CỠ
                        try:
                            idx_pos = local_active_sizes.index(sz) + 1
                            r_val = safe_int(row_data.get(f"CỠ {idx_pos}"))
                        except ValueError:
                            r_val = 0
                            
                    row_ratios[sz] = r_val
                    total_ratios_entered += r_val
                
                layers = safe_int(row_data.get("SƠ LỚP", 0))
                tables = safe_int(row_data.get("SỐ BÀN", 1))

                if total_ratios_entered > 0 and layers > 0:
                    for sz in local_active_sizes:
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
            empty_slots = ["c01", "c02", "c03", "c04", "c05", "c06"]
            
            fab_letter_c2 = "C"
            fab_upper_c2 = str(current_fabric_type).upper().strip()
            if fab_upper_c2 == "LÓT": fab_letter_c2 = "L"
            elif fab_upper_c2 == "KEO": fab_letter_c2 = "K"
            elif fab_upper_c2 == "PHỐI": fab_letter_c2 = "P"
            
            current_grid_structure = [
                {
                    "Mã dòng": f"c{str(i+1).zfill(2)}", "Tên sơ đồ gốc": f"{fab_upper_c2} {fab_letter_c2}{str(i+1).zfill(2)}", "Trạng thái": "AI ĐIỀN VÀO ĐÂY"
                } for i in range(6)
            ]

        is_sub_fabric = str(current_fabric_type).upper() in ["LÓT", "KEO", "PHỐI"]
        fabric_rule_text = ""
        if is_sub_fabric:
            fabric_rule_text = "- ĐẶC BIỆT: Đây là vải phụ (KEO/LÓT/PHỐI). Được phép cắt dư nhẹ 5-10 Pcs mỗi size lẻ để tăng tốc gộp sơ đồ lớn, hạn chế sinh sơ đồ quá mỏng."
        else:
            fabric_rule_text = "- ĐẶC BIỆT: Đây là vải CHÍNH. Tuyệt đối không cắt dư quá quy định, tính toán phối cỡ và số lớp sao cho sản lượng PO triệt tiêu chuẩn xác về 0 hoặc tiệm cận nhất."

        dinhmuc_met_c2 = round(current_consumption * 0.9144, 3)
        
        # Gợi ý xử lý tiếp theo: Đoạn mã của bạn ở đây sẽ sẵn sàng truyền `calculated_balances` và `empty_slots` vào payload gửi tới Gemini Client...


import streamlit as st
import pandas as pd
import json
import re

# =============================================================================
# TẦNG 2 - ĐOẠN 2b (PHẦN 1): KHÔI PHỤC TRẠNG THÁI VÀ DỰNG PROMPT TOÁN HỌC
# =============================================================================

# Khôi phục danh sách size sạch phẳng an toàn từ session_state gốc của file SBD
sbd_store = st.session_state.get("sbd_parsed_data", {})
local_size_breakdown = sbd_store.get("size_breakdown", {}) if isinstance(sbd_store, dict) else {}

def local_sort_key(size_str):
    s_clean = str(size_str).upper().replace(" ", "").strip()
    parts = re.split(r'[X_-]', s_clean)
    if len(parts) >= 2:
        try: return (int(float(parts[0])), int(float(parts[1])))
        except ValueError: return (999, 999)
    try: return (0, int(float(s_clean)))
    except ValueError: return (0, 1000 + sum(ord(c) for c in s_clean))
    
active_sizes = sorted(list(local_size_breakdown.keys()), key=local_sort_key)
if not active_sizes:
    active_sizes = ["26X30", "28X30", "29X32"]

# Định nghĩa JSON Schema loại bỏ ký tự đặc biệt có dấu gạch chéo (/) để AI không nhận diện sai
gemini_raw_json_schema = {
    "type": "OBJECT",
    "properties": {
        "cutting_plan": {
            "type": "ARRAY",
            "description": "Danh sách các sơ đồ bàn cắt đã được tối ưu hóa phối cỡ.",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "line_code": {
                        "type": "STRING",
                        "description": "Mã dòng cần điền dữ liệu, ví dụ: 'c01', 'c02', 'c03'..."
                    },
                    "Ratios": {
                        "type": "OBJECT",
                        "description": "Tỷ lệ phối cỡ, key bắt buộc là 'CỠ 1', 'CỠ 2'...",
                        "properties": {
                            f"CỠ {i+1}": {"type": "INTEGER"} for i in range(len(active_sizes))
                        }
                    },
                    "layers": {
                        "type": "INTEGER",
                        "description": "Số lớp vải cần trải cho sơ đồ này."
                    },
                    "tables": {
                        "type": "INTEGER",
                        "description": "Số bàn cắt áp dụng, mặc định là 1."
                    },
                    "marker_length_meters": {
                        "type": "NUMBER",
                        "description": "Chiều dài sơ đồ tính toán bằng mét."
                    }
                },
                "required": ["line_code", "Ratios", "layers", "tables", "marker_length_meters"]
            }
        }
    },
    "required": ["cutting_plan"]
}

# Kiểm tra trạng thái kích hoạt nút bấm thông qua key đã cấu hình ở Đoạn 2a
if st.session_state.get("c2_normal_cut_btn", False):
    snapshot = st.session_state.get("session_editor_snapshot", [])
    
    # Chuẩn bị ma trận tính toán tồn dư thực tế dựa trên ô lưới hiện tại
    calculated_balances = {sz: int(float(str(v).replace(",", ""))) for sz, v in local_size_breakdown.items()}
    empty_slots = []
    current_grid_structure = []
    
    if snapshot and isinstance(snapshot, list) and len(snapshot) > 0:
        for idx, row_data in enumerate(snapshot):
            s_name = str(row_data.get("BÀN CẮT / TÊN SƠ ĐỒ", f"SƠ ĐỒ C{idx+1}")).upper().strip()
            s_code = f"c{str(idx+1).zfill(2)}"
            total_ratios_entered = 0
            
            for sz in active_sizes:
                r_val = 0
                try:
                    r_val = int(float(str(row_data.get(sz, row_data.get(f"CỠ {active_sizes.index(sz)+1}", 0))).replace(",", "")))
                except Exception: pass
                total_ratios_entered += r_val
            
            layers = max(0, int(float(str(row_data.get("SƠ LỚP", 0)).replace(",", ""))))
            tables = max(1, int(float(str(row_data.get("SỐ BÀN", 1)).replace(",", ""))))
            
            if total_ratios_entered > 0 and layers > 0:
                current_grid_structure.append({"Mã dòng": s_code, "Tên sơ đồ gốc": s_name, "Trạng thái": "GIỮ NGUYÊN KHÔNG ĐỔI"})
            else:
                empty_slots.append(s_code)
                current_grid_structure.append({"Mã dòng": s_code, "Tên sơ đồ gốc": s_name, "Trạng thái": "AI ĐIỀN VÀO ĐÂY"})
    else:
        empty_slots = ["c01", "c02", "c03", "c04", "c05", "c06"]
        current_fabric_type = st.session_state.get("fabric_selectbox_key", "CHÍNH")
        fab_letter_c2 = "L" if str(current_fabric_type).upper() == "LÓT" else ("K" if str(current_fabric_type).upper() == "KEO" else ("P" if str(current_fabric_type).upper() == "PHỐI" else "C"))
        current_grid_structure = [{"Mã dòng": f"c{str(i+1).zfill(2)}", "Tên sơ đồ gốc": f"{str(current_fabric_type).upper()} {fab_letter_c2}{str(i+1).zfill(2)}", "Trạng thái": "AI ĐIỀN VÀO ĐÂY"} for i in range(6)]

    current_consumption = consumption_input if 'consumption_input' in locals() else 1.140
    dinhmuc_met_c2 = round(current_consumption * 0.9144, 3)
    max_table_len_val = max_table_length if 'max_table_length' in locals() else 12.0
    size_mapping_for_ai = [f"CỠ {i+1}: {sz}" for i, sz in enumerate(active_sizes)]

    ai_cutting_prompt = f"""
    Bạn là một thuật toán tối ưu hóa điều độ bàn cắt may mặc chuyên nghiệp.
    Hãy tính toán tỷ lệ phối cỡ (Ratios) và số lớp (layers) điền vào các dòng đang TRỐNG này: {json.dumps(empty_slots)}.
    Tuyệt đối KHÔNG ĐƯỢC tự ý bỏ dòng hoặc thay đổi thông tin các dòng có trạng thái "GIỮ NGUYÊN KHÔNG ĐỔI".
    
    Thông số kỹ thuật đầu vào:
    - Bản đồ cấu trúc dòng hiện tại: {json.dumps(current_grid_structure)}
    - Số lượng sản phẩm còn dư thực tế cần vét (Phải triệt tiêu về 0): {json.dumps(calculated_balances)}
    - Định mức tài liệu kỹ thuật: {dinhmuc_met_c2} mét/sản phẩm.
    - Chiều dài bàn vải tối đa cho phép: {max_table_len_val} mét.

    QUY TẮC PHỐI CỠ BẮT BUỘC:
    1. Chỉ điền Ratios và Số lớp vào dòng ghi "AI ĐIỀN VÀO ĐÂY". Điền tuần tự từ trên xuống dưới.
    2. Chiều dài sơ đồ thực tế = (Tổng số sản phẩm trên sơ đồ) * ({dinhmuc_met_c2} mét) phải <= Chiều dài bàn vải tối đa ({max_table_len_val} mét).
    3. Key trong mảng Ratios bắt buộc đặt tên chuẩn xác theo thứ tự cột là "CỠ 1", "CỠ 2", "CỠ 3"... dựa theo danh sách: {json.dumps(size_mapping_for_ai)}.
    """
    # =============================================================================
    # TẦNG 2 - ĐOẠN 2b (PHẦN 2): GỌI API GEMINI VÀ ĐỒNG BỘ DỮ LIỆU Ô LƯỚI
    # =============================================================================
    try:
        from google import genai
        from google.genai import types
        
        gemini_key = st.secrets.get("GEMINI_API_KEY", "").strip()
        client_ai = genai.Client(api_key=gemini_key)
        
        res_cutting = client_ai.models.generate_content(
            model='gemini-2.5-flash', 
            contents=[ai_cutting_prompt],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=gemini_raw_json_schema,
                temperature=0.1
            )
        )
        
        raw_response_data = json.loads(res_cutting.text.strip())
        ai_vete_res = raw_response_data.get("cutting_plan", [])
        
        if isinstance(ai_vete_res, list) and len(ai_vete_res) > 0:
            st.session_state["auto_cutting_results"] = ai_vete_res
            
            updated_rows = []
            current_fabric_type = st.session_state.get("fabric_selectbox_key", "CHÍNH")
            fab_letter_c2 = "L" if str(current_fabric_type).upper() == "LÓT" else ("K" if str(current_fabric_type).upper() == "KEO" else ("P" if str(current_fabric_type).upper() == "PHỐI" else "C"))
            fab_upper_c2 = str(current_fabric_type).upper().strip()

            for i in range(6):
                s_code = f"c{str(i+1).zfill(2)}"
                
                if snapshot and i < len(snapshot):
                    old_row_data = snapshot[i]
                    s_name_display = str(old_row_data.get("BÀN CẮT / TÊN SƠ ĐỒ", f"{fab_upper_c2} {fab_letter_c2}{str(i+1).zfill(2)}")).upper().strip()
                else:
                    s_name_display = f"{fab_upper_c2} {fab_letter_c2}{str(i+1).zfill(2)}"
                    
                item_dict = {"BÀN CẮT / TÊN SƠ ĐỒ": s_name_display}
                ai_match = [x for x in ai_vete_res if str(x.get("line_code", "")).strip().lower() == s_code]
                
                if ai_match:
                    ai_row = ai_match[0]
                    r_dict = ai_row.get("Ratios", {})
                    total_pants_in_marker = 0
                    
                    # Ánh xạ chuẩn hai loại key (Key ảo 'CỠ X' và Key tên size thật) cho giao diện nhận dạng song song
                    for idx_sz, sz in enumerate(active_sizes):
                        ai_key_look = f"CỠ {idx_sz+1}"
                        val_ai = r_dict.get(ai_key_look, r_dict.get(sz, 0))
                        
                        try: val_int = int(float(str(val_ai).strip() or 0))
                        except Exception: val_int = 0
                        
                        item_dict[ai_key_look] = val_int
                        item_dict[sz] = val_int
                        total_pants_in_marker += val_int
                    
                    try: item_dict["SƠ LỚP"] = int(float(str(ai_row.get("layers", 0)).strip()))
                    except Exception: item_dict["SƠ LỚP"] = 0
                    try: item_dict["SỐ BÀN"] = int(float(str(ai_row.get("tables", 1)).strip() or 1))
                    except Exception: item_dict["SỐ BÀN"] = 1
                    try: item_dict["DÀI SƠ ĐỒ"] = float(str(ai_row.get("marker_length_meters", 0.0)).strip())
                    except Exception: item_dict["DÀI SƠ ĐỒ"] = 0.0
                    
                    item_dict["SỐ SP/SĐ"] = total_pants_in_marker
                    
                    # Phòng vệ lỗi toán học: Chỉ thực hiện phép chia khi tổng sản phẩm lớn hơn 0
                    if total_pants_in_marker > 0:
                        item_dict["Đ.MỨC SĐ"] = round(item_dict["DÀI SƠ ĐỒ"] / total_pants_in_marker, 3)
                        item_dict["VẢI CẦN"] = round(item_dict["DÀI SƠ ĐỒ"] * item_dict["SƠ LỚP"] * item_dict["SỐ BÀN"], 2)
                    else:
                        item_dict["Đ.MỨC SĐ"] = 0.0
                        item_dict["VẢI CẦN"] = 0.0
                else:
                    # Nếu dòng đã gõ tay từ trước (GIỮ NGUYÊN KHÔNG ĐỔI), sao chép nguyên vẹn dữ liệu cũ tránh mất thông tin
                    if snapshot and i < len(snapshot):
                        item_dict = snapshot[i]
                    else:
                        for idx_sz, sz in enumerate(active_sizes):
                            item_dict[f"CỠ {idx_sz+1}"] = 0
                            item_dict[sz] = 0
                        item_dict["SƠ LỚP"] = 0
                        item_dict["SỐ BÀN"] = 1
                        item_dict["DÀI SƠ ĐỒ"] = 0.0
                        item_dict["SỐ SP/SĐ"] = 0
                        item_dict["Đ.MỨC SĐ"] = 0.0
                        item_dict["VẢI CẦN"] = 0.0
                
                updated_rows.append(item_dict)
            
            # Đẩy ngược mảng dữ liệu hoàn chỉnh vào snapshot để cập nhật giao diện ngay lập tức
            st.session_state["session_editor_snapshot"] = updated_rows
            st.success("🤖 AI đã hoàn tất điền cấu trúc và giải toán ma trận bàn cắt!")
            st.rerun()
            
    except Exception as e:
        st.error(f"❌ Lỗi nghiêm trọng khi giải ma trận bàn cắt bằng AI: {str(e)}")


import streamlit as st
import pandas as pd
import json
import re

# =============================================================================
# TẦNG 3 - ĐOẠN 6 (PHẦN 1): KHỞI TẠO CẤU TRÚC LƯỚI VÀ CALLBACK ĐỒNG BỘ HAI CHIỀU
# =============================================================================

# --- 0. HÀM BỔ TRỢ ÉP KIỂU SỐ NGUYÊN AN TOÀN TRÁNH LỖI NAMERROR ---
def safe_int_final(value, default=0):
    if value is None: return default
    try:
        clean_val = str(value).replace(",", "").strip()
        if not clean_val or clean_val.lower() == "none": return default
        if "." in clean_val: clean_val = clean_val.split(".")[0]
        return int(clean_val)
    except (ValueError, TypeError):
        return default

# --- PHÒNG VỆ DỮ LIỆU ĐẦU VÀO TỪ FILE SBD NẾU THIẾU ---
if 'size_breakdown_main' not in locals() and 'size_breakdown_main' not in globals():
    sbd_store = st.session_state.get("sbd_parsed_data", {})
    size_breakdown_main = sbd_store.get("size_breakdown", {}) if isinstance(sbd_store, dict) else {}
if 'active_sizes' not in locals() and 'active_sizes' not in globals():
    active_sizes = []

fab_upper = str(st.session_state.get("fabric_selectbox_key", "CHÍNH")).upper().strip()
prefix_letter = "L" if fab_upper == "LÓT" else "K" if fab_upper == "KEO" else "P" if fab_upper == "PHỐI" else "C"

# 1. Làm sạch và phẳng hóa mảng kích cỡ động từ gốc file SBD
flattened_active_sizes = []
flattened_size_breakdown = {}

for original_key, original_val in size_breakdown_main.items():
    k_str = str(original_key).strip().upper()
    if k_str.startswith("[") or "['" in k_str or '["' in k_str:
        cleaned_parts = re.findall(r"['\"](.*?)['\"]", k_str)
        if len(cleaned_parts) >= 2: k_str = f"{cleaned_parts[0]}X{cleaned_parts[1]}"
        else: k_str = k_str.replace("[","").replace("]","").replace("'","").replace('"',"").replace(" ","").replace(",", "X")
    k_str = re.sub(r'_\d+$', '', k_str).replace(" ", "")
    
    v_num = safe_int_final(original_val)
    if v_num > 0 and k_str != "":
        flattened_size_breakdown[k_str] = flattened_size_breakdown.get(k_str, 0) + v_num
        if k_str not in flattened_active_sizes: flattened_active_sizes.append(k_str)

active_sizes = flattened_active_sizes
size_breakdown_main = flattened_size_breakdown
total_sum_po_qty = sum(size_breakdown_main.values())

# Tiêu đề cột chuẩn hóa thống nhất đồng bộ dạng ảo CỠ X để Streamlit nhận diện lưu trữ
clean_headers_top = ["BÀN CẮT / TÊN SƠ ĐỒ", "TỔNG SẢN LƯỢNG"] + [f"CỠ {i+1}" for i in range(len(active_sizes))] + ["SƠ LỚP", "SỐ BÀN", "DÀI SƠ ĐỒ"]

# 2. Tạo cấu trúc khuôn mẫu 3 hàng tiêu đề phụ cố định
giang_top_row = {"BÀN CẮT / TÊN SƠ ĐỒ": "GIÀNG", "TỔNG SẢN LƯỢNG": 0}
size_top_row = {"BÀN CẮT / TÊN SƠ ĐỒ": "SIZE", "TỔNG SẢN LƯỢNG": 0}
sl_top_row = {"BÀN CẮT / TÊN SƠ ĐỒ": "SẢN LƯỢNG", "TỔNG SẢN LƯỢNG": total_sum_po_qty}

for i, sz in enumerate(active_sizes):
    c_str = str(sz).replace(" ", "").upper()
    g_val, s_val = "None", c_str
    parts = re.split(r'[X_x-]', c_str)
    if len(parts) >= 2:
        s_val = str(parts[0]).strip()
        g_val = str(parts[1]).strip()
    elif len(parts) == 1:
        s_val = str(parts[0]).strip()
        g_val = "None"
    
    giang_top_row[f"CỠ {i+1}"] = re.sub(r'_\d+$', '', g_val)
    size_top_row[f"CỠ {i+1}"] = re.sub(r'_\d+$', '', s_val)
    sl_top_row[f"CỠ {i+1}"] = size_breakdown_main.get(sz, 0)

giang_top_row.update({"SƠ LỚP": 0, "SỐ BÀN": 0, "DÀI SƠ ĐỒ": 0.0})
size_top_row.update({"SƠ LỚP": 0, "SỐ BÀN": 0, "DÀI SƠ ĐỒ": 0.0})
sl_top_row.update({"SƠ LỚP": 0, "SỐ BÀN": 0, "DÀI SƠ ĐỒ": 0.0})

# 3. Nạp bộ nhớ đệm snapshot hoặc khởi tạo lưới mặc định ban đầu
snapshot = st.session_state.get("session_editor_snapshot")
if snapshot and len(snapshot) > 0:
    cleaned_snapshot = [giang_top_row, size_top_row, sl_top_row]
    filtered_snapshot = [r for r in snapshot if isinstance(r, dict) and r.get("BÀN CẮT / TÊN SƠ ĐỒ") not in ["GIÀNG", "SIZE", "SẢN LƯỢNG"]]
    
    for row in filtered_snapshot:
        item_name = str(row.get("BÀN CẮT / TÊN SƠ ĐỒ", "")).upper().strip()
        if not item_name:
            item_name = f"{fab_upper} {prefix_letter}{str(len(cleaned_snapshot)-3).zfill(2)}"
            
        item_dict = {"BÀN CẮT / TÊN SƠ ĐỒ": item_name, "TỔNG SẢN LƯỢNG": 0}
        for c_idx, sz in enumerate(active_sizes):
            val_cell = row.get(f"CỠ {c_idx+1}", row.get(sz, 0))
            item_dict[f"CỠ {c_idx+1}"] = safe_int_final(val_cell)
            item_dict[sz] = safe_int_final(val_cell)
            
        item_dict["SƠ LỚP"] = safe_int_final(row.get("SƠ LỚP", 0))
        item_dict["SỐ BÀN"] = max(1, safe_int_final(row.get("SỐ BÀN", 1)))
        try: item_dict["DÀI SƠ ĐỒ"] = float(str(row.get("DÀI SƠ ĐỒ", 0.0)).replace(",", "") or 0.0)
        except: item_dict["DÀI SƠ ĐỒ"] = 0.0
        
        cleaned_snapshot.append(item_dict)
    display_editor_rows = cleaned_snapshot
else:
    display_editor_rows = [giang_top_row, size_top_row, sl_top_row]
    item_pilot = {"BÀN CẮT / TÊN SƠ ĐỒ": "PILOT", "TỔNG SẢN LƯỢNG": 0}
    for i in range(len(active_sizes)): 
        item_pilot[f"CỠ {i+1}"] = 0
        item_pilot[active_sizes[i]] = 0
    item_pilot.update({"SƠ LỚP": 0, "SỐ BÀN": 1, "DÀI SƠ ĐỒ": 0.0})
    display_editor_rows.append(item_pilot)
    
    for i in range(5):
        item_dict = {"BÀN CẮT / TÊN SƠ ĐỒ": f"{fab_upper} {prefix_letter}{str(i+1).zfill(2)}", "TỔNG SẢN LƯỢNG": 0}
        for c_i in range(len(active_sizes)): 
            item_dict[f"CỠ {c_i+1}"] = 0
            item_dict[active_sizes[c_i]] = 0
        item_dict.update({"SƠ LỚP": 0, "SỐ BÀN": 1, "DÀI SƠ ĐỒ": 0.0})
        display_editor_rows.append(item_dict)

if st.session_state.get("session_editor_snapshot") is None:
    st.session_state["session_editor_snapshot"] = display_editor_rows

# 🎯 FIX KHỐI CODE DỞ: Hàm callback bắt sự kiện chỉnh sửa ô lưới và đồng bộ ngược lên bộ nhớ
def callback_sync_on_the_fly_final():
    if "table_manual_data_editor_final" in st.session_state:
        st_editor = st.session_state["table_manual_data_editor_final"]
        if "edited_rows" in st_editor and st_editor["edited_rows"]:
            raw_snapshot = st.session_state.get("session_editor_snapshot", display_editor_rows)
            current_snapshot = json.loads(json.dumps(raw_snapshot))
            
            for r_idx_edit, change_dict in st_editor["edited_rows"].items():
                r_idx_int = int(r_idx_edit)
                if current_snapshot and r_idx_int < len(current_snapshot):
                    # Khóa chặn bảo vệ không cho sửa nội dung 3 dòng thông số cố định
                    if current_snapshot[r_idx_int]["BÀN CẮT / TÊN SƠ ĐỒ"] in ["GIÀNG", "SIZE", "SẢN LƯỢNG"]: continue
                    
                    for col_header, new_val in change_dict.items():
                        if str(col_header).startswith("CỠ "):
                            try:
                                c_num = int(str(col_header).replace("CỠ ", "").strip())
                                target_size_key = active_sizes[c_num - 1]
                                val_clean = safe_int_final(new_val)
                                current_snapshot[r_idx_int][f"CỠ {c_num}"] = val_clean
                                current_snapshot[r_idx_int][target_size_key] = val_clean # Gán key đôi đồng bộ sạch lỗi hình học
                            except Exception: pass
                        elif col_header in ["SƠ LỚP", "SỐ BÀN"]:
                            current_snapshot[r_idx_int][col_header] = safe_int_final(new_val)
                        elif col_header == "DÀI SƠ ĐỒ":
                            try: current_snapshot[r_idx_int][col_header] = float(str(new_val).strip() or 0.0)
                            except: current_snapshot[r_idx_int][col_header] = 0.0
            
            st.session_state["session_editor_snapshot"] = current_snapshot
# =============================================================================
# TẦNG 3 - ĐOẠN 6 (PHẦN 2): CẤU HÌNH CỘT VÀ HIỂN THỊ Ô LƯỚI DATA EDITOR
# =============================================================================

# Luôn luôn ưu tiên nạp dữ liệu từ bộ nhớ snapshot mới nhất đã được đồng bộ
current_display_data = st.session_state.get("session_editor_snapshot", display_editor_rows)

df_editor_top_render = pd.DataFrame(current_display_data).reindex(columns=clean_headers_top).fillna(0)

# Ép kiểu dữ liệu hiển thị an toàn tuyệt đối cho DataFrame render
for col in clean_headers_top:
    if col.startswith("CỠ ") or col in ["SƠ LỚP", "SỐ BÀN"]:
        df_editor_top_render[col] = pd.to_numeric(df_editor_top_render[col], errors='coerce').fillna(0).astype(int)
    elif col == "DÀI SƠ ĐỒ":
        df_editor_top_render[col] = pd.to_numeric(df_editor_top_render[col], errors='coerce').fillna(0).astype(float)

# Thiết lập cấu hình render nâng cao cho từng loại cột trong xưởng may
config_cot = {
    "BÀN CẮT / TÊN SƠ ĐỒ": st.column_config.TextColumn("📋 Tên Sơ Đồ", disabled=True, width="medium"), 
    "TỔNG SẢN LƯỢNG": st.column_config.NumberColumn("📊 Tổng SL", disabled=True),
    "SƠ LỚP": st.column_config.NumberColumn("🥞 Sơ Lớp", disabled=False, min_value=0, step=1, format="%d"),
    "SỐ BÀN": st.column_config.NumberColumn("🗂️ Số Bàn", disabled=False, min_value=1, step=1, format="%d"),
    "DÀI SƠ ĐỒ": st.column_config.NumberColumn("📏 Dài Sơ Đồ (m)", disabled=False, min_value=0.0, step=0.05, format="%.2f")
}

# Tự động ánh xạ nhãn cột thông minh dạng "CỠ X (Size thực tế)" để tổ trưởng tổ cắt dễ xem
for i, sz in enumerate(active_sizes):
    config_cot[f"CỠ {i+1}"] = st.column_config.NumberColumn(
        f"🔍 CỠ {i+1} ({sz})", 
        disabled=False, 
        min_value=0, 
        step=1, 
        format="%d"
    )

# Gọi kết xuất ô lưới ma trận đồng bộ 2 chiều ra màn hình
st.data_editor(
    df_editor_top_render,
    column_config=config_cot,
    use_container_width=True,
    hide_index=True,
    key="table_manual_data_editor_final",
    on_change=callback_sync_on_the_fly_final # Kích hoạt callback lưu giữ dữ liệu tức thì
)

import math
import streamlit as st
import pandas as pd

# =============================================================================
# TẦNG 3 - ĐOẠN 7a (PHẦN 1): KHÔI PHỤC VÀ KHẤU TRỪ SẢN LƯỢNG SƠ ĐỒ MẪU (PILOT)
# =============================================================================

final_snapshot_rows = []

# --- 0. KHÔI PHỤC DỮ LIỆU ĐẦU VÀO AN TOÀN TỪ STREAMLIT SESSION STATE ---
sbd_store = st.session_state.get("sbd_parsed_data", {})
local_size_breakdown = sbd_store.get("size_breakdown", {}) if isinstance(sbd_store, dict) else {}

# Phục hồi danh sách kích cỡ động tránh lỗi NameError
if 'active_sizes' not in locals() or not active_sizes:
    active_sizes = sorted(list(local_size_breakdown.keys()))
if not active_sizes:
    active_sizes = ["26X30", "28X30", "29X32"]

# Gán biến an toàn cho bộ dữ liệu ô lưới từ data_editor
snapshot_current = st.session_state.get("session_editor_snapshot", [])
edited_df_raw = pd.DataFrame(snapshot_current) if snapshot_current else pd.DataFrame()

# Tính tổng sản lượng đơn hàng PO đầu vào
total_sum_po_qty = sum(safe_int_final(local_size_breakdown.get(sz, 0)) for sz in active_sizes)

# --- 1. KHỞI TẠO MẢNG SẢN LƯỢNG ĐƠN HÀNG THỰC TẾ (PO BALANCES) ---
current_order_balances = {}
for sz in active_sizes:
    current_order_balances[sz] = safe_int_final(local_size_breakdown.get(sz, 0))

consumption_in_yards = consumption_input if 'consumption_input' in locals() else 1.140

# --- 2. BƯỚC 1: ĐẨY 3 HÀNG TIÊU ĐỀ PHỤ CỐ ĐỊNH XUỐNG BẢNG THEO DÕI LŨY TIẾN ---
if not edited_df_raw.empty:
    for idx, row in edited_df_raw.iterrows():
        s_row_name = str(row.get("BÀN CẮT / TÊN SƠ ĐỒ", "")).upper().strip()
        if s_row_name in ["GIÀNG", "SIZE", "SẢN LƯỢNG"]:
            item_dict = {
                "BÀN CẮT / TÊN SƠ ĐỒ": s_row_name, "SƠ LỚP": 0, "SỐ BÀN": 0, 
                "DÀI SƠ ĐỒ": 0.0, "TỔNG SẢN LƯỢNG": total_sum_po_qty if s_row_name == "SẢN LƯỢNG" else 0
            }
            for c_idx, sz in enumerate(active_sizes):
                item_dict[sz] = safe_int_final(row.get(f"CỠ {c_idx+1}", row.get(sz, 0)))
            final_snapshot_rows.append(item_dict)

    # --- 3. BƯỚC 2: KHẤU TRỪ SẢN LƯỢNG TỪ CÁC DÒNG SƠ ĐỒ CẮT MẪU (PILOT) ĐƯỢC NHẬP TAY ---
    for idx, row in edited_df_raw.iterrows():
        s_row_name = str(row.get("BÀN CẮT / TÊN SƠ ĐỒ", "")).upper().strip()
        if s_row_name not in ["GIÀNG", "SIZE", "SẢN LƯỢNG"] and ("PILOT" in s_row_name or "SS" in s_row_name):
            layers = safe_int_final(row.get("SƠ LỚP", 0))
            tables = safe_int_final(row.get("SỐ BÀN", 1))
            try: m_len = float(str(row.get("DÀI SƠ ĐỒ", 0.0)).replace(",", "").strip() or 0.0)
            except: m_len = 0.0
            
            r_dict = {}
            for c_idx, sz in enumerate(active_sizes):
                r_dict[sz] = safe_int_final(row.get(f"CỠ {c_idx+1}", row.get(sz, 0)))
                
            row_ratios_total = sum(r_dict.values())
            
            if row_ratios_total > 0 and layers > 0:
                for sz in active_sizes:
                    allocated_pcs = r_dict.get(sz, 0) * layers * tables
                    current_order_balances[sz] = max(0, current_order_balances[sz] - allocated_pcs)
                    
            item_pilot = {"BÀN CẮT / TÊN SƠ ĐỒ": s_row_name, "SƠ LỚP": layers, "SỐ BÀN": tables, "DÀI SƠ ĐỒ": m_len, "TỔNG SẢN LƯỢNG": row_ratios_total * layers * tables}
            item_pilot.update(r_dict)
            item_pilot["REMAINING_SNAPSHOT_AFTER"] = dict(current_order_balances)
            final_snapshot_rows.append(item_pilot)
# =============================================================================
# TẦNG 3 - ĐOẠN 7a (PHẦN 2): TOÁN HỌC CUỐN CHIẾU LIÊN HOÀN VÀ VÉT SẠCH SỐ LẺ
# =============================================================================

# --- 4. BƯỚC 3: ĐỌC CẤU HÌNH RẢI SƠ ĐỒ CHÍNH TỪ DÒNG ĐẦU CẦN ĐIỀU ĐỘ CHÍNH ---
max_target_length = 11.46
max_target_layers = 60

if not edited_df_raw.empty:
    chinh_rows_input = edited_df_raw[edited_df_raw["BÀN CẮT / TÊN SƠ ĐỒ"].str.contains("CHÍNH|C01", na=False, case=False)]
    if not chinh_rows_input.empty:
        first_chinh = chinh_rows_input.iloc[0]
        try: 
            max_target_length = float(str(first_chinh["DÀI SƠ ĐỒ"]).replace(",", "").strip() or 11.46)
        except: 
            max_target_length = 11.46
        
        user_layers = safe_int_final(first_chinh["SƠ LỚP"])
        max_target_layers = user_layers if user_layers > 1 else 60

if max_target_length <= 0: max_target_length = 11.46

# --- 5. BƯỚC 4: THUẬT TOÁN ĐIỀU PHỐI ĐỘNG CUỐN CHIẾU PHÒNG VỆ CHẶN TREO SERVER ---
marker_counter, max_safety_loops = 1, 30
while sum(current_order_balances.values()) > 0 and marker_counter <= max_safety_loops:
    s_marker_name = f"CHÍNH C{str(marker_counter).zfill(2)}"
    total_remaining_po_at_row = sum(current_order_balances.values())
    
    garments_per_marker = math.floor(max_target_length / consumption_in_yards) if (max_target_length > 0 and consumption_in_yards > 0) else 0
    if garments_per_marker <= 0 or total_remaining_po_at_row <= 0: break
        
    base_values, remainders = {}, []
    for sz in active_sizes:
        if current_order_balances.get(sz, 0) <= 0:
            base_values[sz] = 0
            remainders.append({"size": sz, "remainder": 0.0})
            continue
        sz_remaining_qty = current_order_balances.get(sz, 0)
        sz_ratio_pct = sz_remaining_qty / total_remaining_po_at_row if total_remaining_po_at_row > 0 else 0
        theoretical_qty = garments_per_marker * sz_ratio_pct
        base_qty = int(theoretical_qty)
        base_values[sz] = base_qty
        remainders.append({"size": sz, "remainder": theoretical_qty - base_qty})
        
    allocated_more = garments_per_marker - sum(base_values.values())
    remainders.sort(key=lambda x: x["remainder"], reverse=True)
    for k in range(min(max(0, allocated_more), len(remainders))):
        if current_order_balances.get(remainders[k]["size"], 0) > 0:
            base_values[remainders[k]["size"]] += 1
            
    r_dict = base_values
    row_ratios_total = sum(r_dict.values())
    
    # Tính số lớp vải trải cuốn chiếu tối đa theo từng size đơn hàng lẻ
    possible_layers_dynamic = []
    for sz in active_sizes:
        if r_dict.get(sz, 0) > 0:
            max_layers_allowed_for_sz = math.floor(current_order_balances.get(sz, 0) / r_dict.get(sz, 0))
            possible_layers_dynamic.append(max_layers_allowed_for_sz if max_layers_allowed_for_sz > 0 else 1)
                
    calculated_layers = min(possible_layers_dynamic) if possible_layers_dynamic else 1
    row_layers = min(max_target_layers, calculated_layers)
    
    # 🎯 FIX LỖI CHÍ MẠNG CHẶN VÒNG LẶP VÔ HẠN: Nếu thuật toán không thể tính thêm số lớp, bẻ gãy vòng lặp lập tức
    if row_layers <= 0 or row_ratios_total <= 0: 
        break
        
    for sz in active_sizes:
        current_order_balances[sz] = max(0, current_order_balances[sz] - (r_dict.get(sz, 0) * row_layers))
        
    item_auto = {
        "BÀN CẮT / TÊN SƠ ĐỒ": s_marker_name, "SƠ LỚP": row_layers, "SỐ BÀN": 1,
        "DÀI SƠ ĐỒ": round(row_ratios_total * consumption_in_yards, 2),
        "TỔNG SẢN LƯỢNG": row_ratios_total * row_layers
    }
    item_auto.update(r_dict)
    item_auto["REMAINING_SNAPSHOT_AFTER"] = dict(current_order_balances)
    final_snapshot_rows.append(item_auto)
    
    marker_counter += 1

# --- 6. BƯỚC 5: KIỂM TRA DƯ THIẾU CUỐI ĐƠN - TỰ ĐỘNG CHÈN DÒNG VÉT SẠCH VẢI VỤN (DÒNG CUỐI) ---
leftover_sum = sum(current_order_balances.values())
if leftover_sum > 0:
    s_marker_name = f"CHÍNH C{str(marker_counter).zfill(2)} (VÉT SẠCH ĐƠN HÀNG)"
    vet_ratios = {}
    total_vet_pants = 0
    
    for sz in active_sizes:
        qty_left = current_order_balances.get(sz, 0)
        vet_ratios[sz] = qty_left
        total_vet_pants += qty_left
        current_order_balances[sz] = 0
        
    item_vet = {
        "BÀN CẮT / TÊN SƠ ĐỒ": s_marker_name, "SƠ LỚP": 1, "SỐ BÀN": 1,
        "DÀI SƠ ĐỒ": round(total_vet_pants * consumption_in_yards, 2),
        "TỔNG SẢN LƯỢNG": total_vet_pants
    }
    item_vet.update(vet_ratios)
    item_vet["REMAINING_SNAPSHOT_AFTER"] = dict(current_order_balances)
    final_snapshot_rows.append(item_vet)






import streamlit as st
import pandas as pd
import io
import re

# =============================================================================
# TẦNG 3 - ĐOẠN 2b (PHẦN 1): TÁI CẤU TRÚC PHIẾU BÁO CÁO MA TRẬN LŨY TIẾN
# =============================================================================

# Khai báo lại hàm helper để tránh lỗi NameError khi chạy độc lập
def safe_int_final(value, default=0):
    if value is None: return default
    try:
        clean_val = str(value).replace(",", "").strip()
        if not clean_val or clean_val.lower() == "none": return default
        if "." in clean_val: clean_val = clean_val.split(".")[0]
        return int(clean_val)
    except (ValueError, TypeError):
        return default

# Kiểm tra phòng vệ an toàn cho các biến môi trường đầu vào từ Tầng trước
style_id_clean = style_id_input.strip().upper() if 'style_id_input' in locals() else "UNKNOWN"
color_clean = color_input.strip().upper() if 'color_input' in locals() else "BLACK"
fab_type_clean = fabric_type_input.strip().upper() if 'fabric_type_input' in locals() else "CHÍNH"

if 'active_sizes' not in locals() and 'active_sizes' not in globals():
    active_sizes = []
if 'size_breakdown_main' not in locals() and 'size_breakdown_main' not in globals():
    size_breakdown_main = {}
if 'total_sum_po_qty' not in locals() and 'total_sum_po_qty' not in globals():
    total_sum_po_qty = 0
if 'final_snapshot_rows' not in locals() and 'final_snapshot_rows' not in globals():
    final_snapshot_rows = []

# Tạo 3 hàng tiêu đề thông tin tổng quát của phiếu đơn hàng dệt may
t_header_ma_hang = ["Mã hàng:", f" {style_id_clean}"] + [""] * (len(active_sizes) + 6)
t_header_mau = ["Màu:", f" {color_clean}"] + [""] * (len(active_sizes) + 6)
t_header_loai_vai = ["Loại vải:", f" {fab_type_clean}"] + [""] * (len(active_sizes) + 6)

t1_giang_row = ["GIÀNG", ""]
t2_size_row = ["SIZE", ""]
po_qty_matrix = []

# Quét danh sách kích cỡ phân tách thông số Eo (Size) và Giàng (Inseam)
for col_name in active_sizes:
    c_str = str(col_name).strip().upper().replace(" ", "")
    g_val, s_val = "None", c_str
    parts = re.split(r'[X_x-]', c_str)
    
    if len(parts) >= 2:
        s_val = str(parts[0]).strip()  # Thông số Eo (Size)
        g_val = str(parts[1]).strip()  # Thông số Giàng (Inseam)
    elif len(parts) == 1:
        s_val = str(parts[0]).strip()
        g_val = "None"
        
    po_v = safe_int_final(size_breakdown_main.get(col_name, 0))
    po_qty_matrix.append(po_v)
    
    t1_giang_row.append(re.sub(r'_\d+$', '', g_val))
    t2_size_row.append(re.sub(r'_\d+$', '', s_val))
    
# Thêm khoảng trống đệm cho các cột kỹ thuật bổ trợ ở phía sau
for _ in range(6): 
    t1_giang_row.append("")
    t2_size_row.append("")
    
t3_sl_row = ["SẢN LƯỢNG", f"{total_sum_po_qty:,}"] + [f"{v:,}" for v in po_qty_matrix] + [""] * 6
    
matrix_body_rows = []
production_rows = [r for r in final_snapshot_rows if isinstance(r, dict) and r.get("BÀN CẮT / TÊN SƠ ĐỒ") not in ["GIÀNG", "SIZE", "SẢN LƯỢNG"]]

for r_idx, row_data in enumerate(production_rows):
    s_name = str(row_data.get("BÀN CẮT / TÊN SƠ ĐỒ", f"SƠ ĐỒ C{r_idx+1}")).upper().strip()
    layers = safe_int_final(row_data.get("SƠ LỚP", 0))
    tables = max(1, safe_int_final(row_data.get("SỐ BÀN", 1)))
    try: m_len = float(str(row_data.get("DÀI SƠ ĐỒ", 0.0)).replace(",", "") or 0.0)
    except: m_len = 0.0
    
    row_ratios_list = []
    ratios_sum = 0
    
    for c_idx, sz in enumerate(active_sizes):
        r_val = safe_int_final(row_data.get(sz, row_data.get(f"CỠ {c_idx+1}", 0)))
        ratios_sum += r_val
        row_ratios_list.append(r_val)
    
    dm_sd = (m_len * 1.09361) / ratios_sum if (m_len > 0 and ratios_sum > 0) else 0.0
    vail_can_m = m_len * layers * tables
    total_cut_in_row = ratios_sum * layers * tables
    
    # 1. Thêm dòng thông số tỷ lệ và định mức sơ đồ bàn vải
    ratio_row = [s_name, f"{total_cut_in_row:,}"] + [f"{v:,}" if isinstance(v, int) else v for v in row_ratios_list] + [layers, tables, round(m_len, 2), ratios_sum, round(dm_sd, 3), round(vail_can_m, 1)]
    matrix_body_rows.append(ratio_row)
    
    # 2. Chèn dòng trạng thái "CÒN LẠI" khấu trừ lũy tiến cuốn chiếu xuống dưới
    row_remaining_snapshot = row_data.get("REMAINING_SNAPSHOT_AFTER", {})
    remaining_row = ["CÒN LẠI", ""]
    for sz in active_sizes:
        rem_sz_val = safe_int_final(row_remaining_snapshot.get(sz, 0))
        remaining_row.append(f"{rem_sz_val:,}" if rem_sz_val > 0 else "0")
    remaining_row.extend(["", "", "", "", "", ""])
    matrix_body_rows.append(remaining_row)

clean_headers = ["BÀN CẮT / TÊN SƠ ĐỒ", "TỔNG SẢN LƯỢNG"] + [f"CỠ {i+1}" for i in range(len(active_sizes))] + ["SƠ LỚP", "SỐ BÀN", "DÀI SƠ ĐỒ", "SỐ SP/SĐ", "Đ.MỨC SĐ", "VẢI CẦN (M)"]
final_table_rows = [t_header_ma_hang, t_header_mau, t_header_loai_vai, t1_giang_row, t2_size_row, t3_sl_row] + matrix_body_rows

df_final_report = pd.DataFrame(final_table_rows, columns=clean_headers)
from supabase import create_client

# =============================================================================
# TẦNG 3 - ĐOẠN 2b (PHẦN 2): RENDERING GIAO DIỆN VÀ ĐỒNG BỘ CLOUD SUPABASE
# =============================================================================

# Bộ định dạng giao diện hiển thị bảng may mặc chuyên nghiệp bằng CSS
st.markdown("""<style>
    .report-table th { background-color: #F1F5F9 !important; color: #1E293B !important; font-weight: 700 !important; text-align: center !important; border: 1px solid #CBD5E1 !important; }
    .report-table td { background-color: #FFFFFF !important; color: #0F172A !important; border: 1px solid #E2E8F0 !important; text-align: center !important; font-weight: 500 !important; }
</style>""", unsafe_allow_html=True)

st.markdown("### 📊 PHIẾU TÁC NGHIỆP LIÊN KẾT BÀN CẮT CHÍNH THỨC")
st.dataframe(df_final_report, use_container_width=True, hide_index=True)

st.markdown("---")
action_col1, action_col2 = st.columns(2)

# NÚT BẤM 1: Xuất tệp tin Excel (.xlsx) tải về máy cá nhân
with action_col1:
    output_excel = io.BytesIO()
    with pd.ExcelWriter(output_excel, engine='xlsxwriter') as writer:
        df_final_report.to_excel(writer, sheet_name='TAC_NGHIEP_BAN_CAT', index=False)
    processed_data = output_excel.getvalue()
    st.download_button(
        label="📥 TẢI PHIẾU TÁC NGHIỆP EXCEL (.XLSX)", data=processed_data,
        file_name=f"Phieu_Tac_Nghiep_{style_id_clean}_{fab_type_clean}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", 
        use_container_width=True, 
        type="primary"
    )

# NÚT BẤM 2: Gói Payload và Upsert trực tiếp lên kho cơ sở dữ liệu trung tâm Cloud Supabase
with action_col2:
    if st.button("💾 ĐẨY PHIẾU LÊN HỆ THỐNG TRUNG TÂM CLOUD SUPABASE", use_container_width=True):
        try:
            url_direct_push = st.secrets.get("SUPABASE_URL", "")
            key_direct_push = st.secrets.get("SUPABASE_KEY", "")
            
            if not url_direct_push or not key_direct_push: 
                st.error("❌ Hệ thống chưa được cấu hình đầy đủ biến môi trường SUPABASE_URL hoặc SUPABASE_KEY trong Secrets.")
            else:
                sb_client_push = create_client(url_direct_push, key_direct_push)
                payload_save = {
                    "style_id": str(style_id_clean), 
                    "fabric_type": str(fab_type_clean),
                    "total_po_qty": int(total_sum_po_qty), 
                    "cutting_matrix_data": final_snapshot_rows, 
                    "color_name": str(color_clean)
                }
                # Sử dụng cơ chế upsert ràng buộc theo cặp khóa (style_id, fabric_type) chống ghi trùng lặp dữ liệu
                res_push = sb_client_push.table("cutting_orders_db").upsert(payload_save, on_conflict="style_id,fabric_type").execute()
                st.success("🎉 Hệ thống đã đồng bộ phiếu tác nghiệp lên Cloud Supabase thành công!")
        except Exception as e: 
            st.error(f"❌ Trục trặc khi gửi gói tin lên Supabase: {str(e)}")
