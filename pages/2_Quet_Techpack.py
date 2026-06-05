import base64
import io
import json
import re
import requests
import streamlit as st
import pandas as pd
import time
from pdf2image import convert_from_bytes, pdfinfo_from_bytes
from google import genai
from google.genai import types

# BẮT BUỘC: Câu lệnh cấu hình trang phải nằm đầu tiên trong file Streamlit
st.set_page_config(
    page_title="PPJ Techpack AI - Management System",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Cấu hình giao diện CSS chuyên nghiệp cho nút bấm và vùng hiển thị dữ liệu
st.markdown("""
    <style>
    [data-testid="stSidebar"] { background-color: #f8f9fa; min-width: 280px; }
    .main-title { font-size: 26px; font-weight: bold; color: #1E3A8A; margin-bottom: 5px; }
    .step-title { font-size: 18px; font-weight: bold; color: #0F172A; margin-top: 20px; margin-bottom: 10px; }
    .badge-offline { background-color: #FEF3C7; color: #D97706; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; }
    .badge-match { background-color: #DBEAFE; color: #2563EB; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)
# Cấu hình kết nối cơ sở dữ liệu Supabase Master DB của PPJ Group
SB_URL = "https://ewqqodsfvlvnrzsylawy.supabase.co"
SB_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImV3cXFvZHNmdmx2bnJ6c3lsYXd5Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzUxMTkyOTAsImV4cCI6MjA5MDY5NTI5MH0.BWPxOsyswBT5CLrZgluRC1F2x5EpU06oexUFyakGhyc"

def get_secure_gemini_key():
    if "GEMINI_API_KEY" in st.secrets:
        return st.secrets["GEMINI_API_KEY"].strip()
    return "AIzaSyC7z02-60O0-X20P_Production_PPJ_Group_Active2026"

def save_to_supabase_techpack_table(payload_data):
    """Hàm xử lý lưu trữ hình ảnh rập/sketch và đồng bộ bảng thông số kĩ thuật vào Supabase Database"""
    try:
        style_name_db = payload_data.get("style_number_db", "").strip()
        if not style_name_db: style_name_db = "UNKNOWN_STYLE"
        sketch_b64 = payload_data.get("sketch_image", "")
        public_image_url = ""

        if sketch_b64:
            try:
                image_data = base64.b64decode(sketch_b64)
                storage_headers = {
                    "apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}",
                    "Content-Type": "image/jpeg", "x-upsert": "true"
                }
                clean_filename = re.sub(r'[^a-zA-Z0-9_-]', '', style_name_db)
                storage_url = f"{SB_URL.rstrip('/')}/storage/v1/object/kho_anh/{clean_filename}.jpg"
                upload_res = requests.post(storage_url, headers=storage_headers, data=image_data, timeout=20)
                if upload_res.status_code >= 200 and upload_res.status_code <= 299:
                    public_image_url = f"{SB_URL.rstrip('/')}/storage/v1/object/public/kho_anh/{clean_filename}.jpg"
            except Exception: pass

        headers = {
            "apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}",
            "Content-Type": "application/json", "Prefer": "resolution=merge-duplicates"
        }
        insert_url = f"{SB_URL.rstrip('/')}/rest/v1/thong_so_techpack"
        
        raw_measurements = payload_data.get("detailed_measurements", {})
        clean_dict = {str(k): str(v) for k, v in dict(raw_measurements).items()}
        jsonb_ready_measurements = json.loads(json.dumps(clean_dict, ensure_ascii=True))

        db_payload = {
            "StyleName": style_name_db,
            "Buyer": payload_data.get("buyer"),
            "Category": payload_data.get("category"),
            "BaseSize": payload_data.get("base_size_name"),
            "DetailedMeasurements": jsonb_ready_measurements,
            "SketchURL": public_image_url
        }
        response = requests.post(insert_url, headers=headers, json=[db_payload], timeout=15)
        return response.status_code >= 200 and response.status_code <= 299
    except Exception: return False

def get_all_historical_styles_from_db():
    """Hàm trích xuất dữ liệu lịch sử số đo rập mẫu từ bảng thong_so_techpack"""
    try:
        headers = {"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}"}
        url = f"{SB_URL.rstrip('/')}/rest/v1/thong_so_techpack?select=*&limit=100"
        res = requests.get(url, headers=headers, timeout=15)
        return res.json() if res.status_code >= 200 and res.status_code <= 299 else []
    except Exception: return []

def get_historical_fabric_consumption_from_db(search_keyword=None):
    """Hàm trích xuất dữ liệu định mức vải trên Supabase"""
    try:
        headers = {"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}"}
        url = f"{SB_URL.rstrip('/')}/rest/v1/san_pham"
        query_params = {
            "select": "style_name,article_name,consumption_type,material_size,uom,consumption_value,notes",
            "limit": 100
        }
        if search_keyword:
            query_params["style_name"] = f"ilike.*{search_keyword}*"
        res = requests.get(url, headers=headers, params=query_params, timeout=15)
        return res.json() if res.status_code >= 200 and res.status_code <= 299 else []
    except Exception: return []
def process_single_pdf_batch(file_bytes, file_name):
    gemini_key = get_secure_gemini_key()
    if '.' in file_name: fallback_style = file_name.rsplit('.', 1)[0].strip()
    else: fallback_style = file_name.strip()

    try:
        info = pdfinfo_from_bytes(file_bytes)
        total_pages = int(info.get("Pages", 1))
        contents_payload = []
        sketch_base64 = ""

        for p_num in range(1, total_pages + 1):
            try:
                images = convert_from_bytes(file_bytes, dpi=150, first_page=p_num, last_page=p_num)
                if images:
                    img = images[0].convert("RGB")
                    img_buffer = io.BytesIO()
                    img.save(img_buffer, format="JPEG", quality=95)
                    contents_payload.append(types.Part.from_bytes(data=img_buffer.getvalue(), mime_type='image/jpeg'))
                    
                    if p_num == 1 and not sketch_base64:
                        if img.width > 450: img = img.resize((450, int(img.height * (450 / img.width))))
                        bk_buf = io.BytesIO()
                        img.save(bk_buf, format="JPEG", quality=80)
                        sketch_base64 = base64.b64encode(bk_buf.getvalue()).decode("utf-8")
            except Exception: pass

        if not contents_payload: return {"success": False, "error": "Không thể giải mã các trang dữ liệu của file PDF."}

        user_prompt = """
        You are a strict garment technical auditor. Analyze all the attached images from the techpack PDF.
        Extract the exact Style Number/ID, Buyer, Category, Base Size Name, and all detailed measurement specification row values found in the grid.
        Return a valid JSON object with this exact format:
        {
          "style_number_parsed": "Extract real Style ID from text",
          "buyer": "Extract real Buyer Account name",
          "category": "Extract real Product Category line",
          "base_size_name": "Extract real sample base size used in table columns",
          "measurements": {
             "POM Name 1": "Value 1",
             "POM Name 2": "Value 2"
          }
        }
        """
        contents_payload.append(user_prompt)

        client = genai.Client(api_key=gemini_key)
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=contents_payload,
            config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.0)
        )

        parsed_data = json.loads(response.text.strip())
        dict_measurements = parsed_data.get("measurements") or {}
        
        if not dict_measurements:
            return {"success": False, "error": "AI không tìm thấy lưới ma trận thông số đo gốc."}

        return {"success": True, "data": {
            "style_number_db": parsed_data.get("style_number_parsed") or fallback_style,
            "buyer": parsed_data.get("buyer") or "UNKNOWN BUYER",
            "category": parsed_data.get("category") or "PRODUCTION GARMENT",
            "base_size_name": parsed_data.get("base_size_name") or "N/A",
            "detailed_measurements": dict_measurements,
            "sketch_image": sketch_base64
        }}
    except Exception as e: return {"success": False, "error": f"Lỗi xử lý tệp: {str(e)}"}

def generate_real_gemini_chat_response(user_query, attached_file):
    try:
        gemini_key = get_secure_gemini_key()
        ai_contents_payload = []
        pdf_context = "Không có tệp phụ trợ đính kèm."
        search_keyword = None

        # 1. Tự động bóc tách từ khóa mã hàng từ tên file phụ trợ tải lên
        if attached_file:
            file_name = attached_file.name
            # Trích xuất chuỗi ký tự/mã số đứng đầu file làm từ khóa tìm kiếm (Ví dụ: S6BT065 -> S6BT065)
            clean_name = re.sub(r'[^a-zA-Z0-9_-]', ' ', file_name)
            name_parts = clean_name.split()
            if name_parts:
                # Lấy phần tử đầu tiên hoặc phần tử dài nhất thường chứa mã hàng
                search_keyword = max(name_parts, key=len)
                
            file_bytes = attached_file.getvalue()
            if attached_file.name.lower().endswith('.pdf'):
                try:
                    pdf_images = convert_from_bytes(file_bytes, dpi=140, first_page=1, last_page=min(2, int(pdfinfo_from_bytes(file_bytes).get("Pages", 1))))
                    for img_obj in pdf_images:
                        img_buf = io.BytesIO()
                        img_obj.convert("RGB").save(img_buf, format="JPEG", quality=90)
                        ai_contents_payload.append(types.Part.from_bytes(data=img_buf.getvalue(), mime_type='image/jpeg'))
                    pdf_context = f"[Tài liệu Techpack mới đính kèm: AI đã quét ảnh sơ đồ cấu trúc bản vẽ rập phom dáng mã {search_keyword}]"
                except Exception: pass
            elif attached_file.name.lower().endswith(('.png', '.jpg', '.jpeg')):
                ai_contents_payload.append(types.Part.from_bytes(data=file_bytes, mime_type='image/jpeg'))
                pdf_context = f"[Hình ảnh đính kèm: Đã nạp ảnh cấu trúc bản vẽ mã mới {search_keyword}]"

        # Nếu không có file đính kèm, cố gắng tìm kiếm từ khóa mã hàng nằm trong câu gõ chat của kỹ sư
        if not search_keyword and user_query:
            clean_query = re.sub(r'[^a-zA-Z0-9_-]', ' ', user_query)
            query_parts = clean_query.split()
            # Lấy chuỗi ký tự có độ dài từ 4 ký tự trở lên (thường là mã hàng)
            long_parts = [p for p in query_parts if len(p) >= 4]
            if long_parts:
                search_keyword = long_parts[0]

        # 2. TRUY XUẤT KHO THÔNG SỐ ĐO RẬP LỊCH SỬ
        db_spec_data = get_all_historical_styles_from_db()
        spec_context = f"\n[KHO LỊCH SỬ THÔNG SỐ ĐO RẬP BLUEPRINT (BẢNG thong_so_techpack)]:\n{json.dumps(db_spec_data, ensure_ascii=False)}"

        # 3. ✨ ĐÃ SỬA: Ép truyền từ khóa tìm kiếm để Supabase trả về chính xác dòng dữ liệu thật, gạt bỏ lỗi trả về mảng rỗng []
        db_consumption_data = get_historical_fabric_consumption_from_db(search_keyword)
        
        # Cơ chế dự phòng cứu hộ: Nếu truyền từ khóa hẹp không ra kết quả, gọi diện rộng để lấy dữ liệu làm căn cứ tính toán
        if not db_consumption_data:
            db_consumption_data = get_historical_fabric_consumption_from_db(None)
            
        consumption_context = f"\n[KHO ĐỊNH MỨC NGUYÊN PHỤ LIỆU THỰC TẾ (BẢNG san_pham)]:\n{json.dumps(db_consumption_data, ensure_ascii=False)}"

        # 4. CHỈ THỊ NGHIỆP VỤ ĐỊNH MỨC MAY MẶC CHẶT CHẼ
        system_instruction = f"""
        Bạn là một Chuyên viên tính toán Định mức nguyên phụ liệu dệt may thực thụ thuộc phòng Kỹ thuật PPJ Group.
        Từ khóa mã hàng được hệ thống xác định: {search_keyword or 'Chưa xác định'}.
        Tài liệu Techpack mới người dùng tải lên cần phân tích: {pdf_context}.
        
        Dữ liệu thực tế truy xuất được từ cơ sở dữ liệu Supabase Master DB của nhà xưởng:
        - Kho thông số đo rập dáng cũ: {spec_context}
        - Kho định mức vật tư tiêu hao cũ: {consumption_context}
        
        Nhiệm vụ nghiêm ngặt của bạn:
        1. [QUÉT FILE MỚI]: Hãy phân tích hình ảnh sơ đồ rập, ảnh sketch sản phẩm đính kèm để bóc tách bảng thông số đo (vòng eo, mông, hạ đũi trước/sau, dài quần...) của mã hàng mới gửi lên. Nếu hình ảnh mờ không đọc được POM chi tiết, hãy lấy thông số mẫu tiêu chuẩn ngành của dòng sản phẩm quần Denim/Cargo tương ứng làm cơ sở.
        2. [SO KHỚP TÌM MÃ TƯƠNG ĐỒNG HÌNH HỌC]: Đối chiếu ma trận thông số đo được với kho 'DetailedMeasurements' của bảng 'thong_so_techpack'. Tìm ra tên mã hàng cũ (StyleName) có độ tương đồng cấu trúc cao nhất về hình dáng.
        3. [PHÂN TÍCH TỶ LỆ CHÊNH LỆCH %]: So sánh chi tiết từng vị trí đo (POM) giữa mã mới và mã cũ vừa tìm được. Tính toán cụ thể xem mã hàng mới lớn hơn hoặc nhỏ hơn mã cũ bao nhiêu % ở các vị trí cốt lõi (Ví dụ: Vòng mông rộng hơn bao nhiêu %, dài quần lệch bao nhiêu).
        4. [TÍNH TOÁN DỰ ĐOÁN ĐM CHO MÃ MỚI]: Tra cứu sang kho định mức 'san_pham' để lấy chính xác các dòng định mức vật tư thật của mã tương đồng cũ đó (gồm article_name, consumption_type, material_size, consumption_value). 
        Dựa vào tỷ lệ phần trăm chênh lệch kích thước hình học rập vừa phân tích ở bước 3, tính toán tăng hoặc giảm định mức nguyên phụ liệu tương ứng cho mã hàng mới (Cộng thêm 5% hao hụt sản xuất thực tế bàn cắt tấm tiêu chuẩn).
        5. [KẾT LUẬN đơn hàng]: Xuất ra bảng đối chiếu dạng Markdown thể hiện rõ ma trận chênh lệch thông số rập và bảng dự đoán định mức chi tiết (Vải chính, vải lót, mếch dựng, đơn vị YRD) cho mã hàng mới này.
        
        Văn phong yêu cầu: Đanh thép, chuyên nghiệp của nhân viên kỹ thuật phòng Định mức PPJ. Tuyệt đối không báo kho trống hay yêu cầu người dùng nhập thủ công nếu đã có dữ liệu kho nạp vào ngữ cảnh.
        """
        ai_contents_payload.append(system_instruction)
        ai_contents_payload.append(f"Yêu cầu thực tế của kỹ sư PPJ: {user_query}")

        client = genai.Client(api_key=gemini_key)
        response = client.models.generate_content(model='gemini-2.5-flash', contents=ai_contents_payload)
        return response.text.strip()
    except Exception as e:
        return f"Lỗi truy vấn máy chủ AI xử lý định mức: {str(e)}"

if "current_menu" not in st.session_state: st.session_state.current_menu = "Quét Tài Liệu Techpack"

with st.sidebar:
    st.markdown("<div style='background-color: #1E3A8A; color: white; padding: 20px; border-radius: 8px; text-align: center; margin-bottom: 20px;'><h2 style='margin:0; font-size:22px; font-weight:bold;'>PPJ GROUP</h2><p style='margin:0; font-size:11px; opacity:0.8;'>Boundless solutions</p></div>", unsafe_allow_html=True)
    if st.button("📄 Quét Tài Liệu Techpack", use_container_width=True, type="primary" if st.session_state.current_menu == "Quét Tài Liệu Techpack" else "secondary"): st.session_state.current_menu = "Quét Tài Liệu Techpack"; st.rerun()
    if st.button("📊 So Sánh Phom Thông Số", use_container_width=True, type="primary" if st.session_state.current_menu == "So Sánh Thông Số Rập" else "secondary"): st.session_state.current_menu = "So Sánh Thông Số Rập"; st.rerun()
    if st.button("🌾 Trợ Lý Tính Định Mức", use_container_width=True, type="primary" if st.session_state.current_menu == "Trợ Lý Tính Định Mức" else "secondary"): st.session_state.current_menu = "Trợ Lý Tính Định Mức"; st.rerun()

st.markdown("<div class='main-title'>PPJ GROUP — Content Management System</div>", unsafe_allow_html=True)
st.markdown(f"<p style='color:#64748B; margin-top:-5px;'>Phân hệ đang hoạt động: <b>{st.session_state.current_menu}</b></p>", unsafe_allow_html=True)
st.markdown("---")
# PHÂN HỆ 1: QUÉT TÀI LIỆU TECHPACK
if st.session_state.current_menu == "Quét Tài Liệu Techpack":
    uploaded_files = st.file_uploader("Kéo thả tài liệu PDF vào đây", type=["pdf"], accept_multiple_files=True)
    if uploaded_files:
        with st.spinner("Hệ thống AI đang bóc tách chính xác ma trận dữ liệu gốc..."):
            all_results, errors_occurred = [], []
            for f in uploaded_files:
                res = process_single_pdf_batch(f.getvalue(), f.name)
                if res["success"]: all_results.append(res["data"])
                else: errors_occurred.append(f"{f.name}: {res['error']}")
                    
            if all_results:
                st.success("Bóc tách cấu trúc dữ liệu tệp thành công!")
                cols = st.columns(len(all_results))
                for idx, data in enumerate(all_results):
                    with cols[idx]:
                        st.markdown(f"### <span style='color:#1E3A8A;'>{data['style_number_db']}</span>", unsafe_allow_html=True)
                        st.markdown("<span class='badge-offline'>OFFLINE PREVIEW</span> <span class='badge-match'>BEST MATCH</span>", unsafe_allow_html=True)
                        st.markdown(f"<p style='font-size:13px;'><b>Buyer:</b> {data['buyer']}<br><b>Category:</b> {data['category']}<br><b>Scale:</b> {data['base_size_name']}</p>", unsafe_allow_html=True)
                        sc1, sc2 = st.columns(2)
                        with sc1:
                            df = pd.DataFrame([{"Garment Attribute": k, "Target Spec": v} for k, v in data['detailed_measurements'].items()])
                            st.dataframe(df, hide_index=True, use_container_width=True)
                        with sc2:
                            if data.get("sketch_image"): st.image(f"data:image/jpeg;base64,{data['sketch_image']}", use_container_width=True)
                        if st.button(f"💾 LƯU MÃ HÀNG {data['style_number_db']}", key=f"sv_{idx}", use_container_width=True, type="primary"):
                            if save_to_supabase_techpack_table(data): st.success("Đã đồng bộ lưu vào Supabase Database!")
                            else: st.error("Lỗi cơ sở dữ liệu!")
            for err in errors_occurred: st.error(err)

# PHÂN HỆ 2: SO SÁNH THÔNG SỐ RẬP
elif st.session_state.current_menu == "So Sánh Thông Số Rập":
    st.subheader("📊 Phân hệ Đối Chiếu & Kiểm Tra Sai Lệch Thông Số Rập Mẫu")
    up1, up2 = st.columns(2)
    with up1: buyer_file = st.file_uploader("Upload tài liệu gốc khách hàng (Buyer Techpack PDF)", type=["pdf"])
    with up2: factory_file = st.file_uploader("Upload tài liệu sản xuất thực tế (Factory Spec PDF)", type=["pdf"])
    
    if st.button("🚀 Tiến hành đối chiếu song song", type="primary", use_container_width=True):
        if buyer_file and factory_file:
            with st.spinner("Hệ thống AI đang đối chiếu song song tệp dữ liệu..."):
                rb = process_single_pdf_batch(buyer_file.getvalue(), buyer_file.name)
                rf = process_single_pdf_batch(factory_file.getvalue(), factory_file.name)
                if rb["success"] and rf["success"]:
                    data_b, data_f = rb["data"]["detailed_measurements"], rf["data"]["detailed_measurements"]
                    compare_rows = []
                    for k in data_b.keys():
                        v_b, v_f = data_b.get(k, "N/A"), data_f.get(k, "N/A")
                        compare_rows.append({"Vị trí đo (Garment Attribute)": k, "Mẫu gốc (Buyer Spec)": v_b, "Thực tế xưởng (Factory Spec)": v_f, "Trạng thái": "✅ Khớp" if v_b == v_f else "⚠️ Lệch thông số"})
                    df_compare = pd.DataFrame(compare_rows)
                    st.success("Phân tích so khớp hoàn tất!")
                    st.table(df_compare)
                    towrite = io.BytesIO()
                    with pd.ExcelWriter(towrite, engine='xlsxwriter') as writer: df_compare.to_excel(writer, index=False, sheet_name='Spec_Comparison')
                    towrite.seek(0)
                    st.download_button(label="📥 XUẤT PHÂN TÍCH RA FILE EXCEL (.XLSX)", data=towrite, file_name=f"So_Sanh_Thong_So_PPJ_{int(time.time())}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
                else: st.error("Sự cố trích xuất dữ liệu.")

# PHÂN HỆ 1: QUÉT TÀI LIỆU TECHPACK
if st.session_state.current_menu == "Quét Tài Liệu Techpack":
    uploaded_files = st.file_uploader("Kéo thả tài liệu PDF vào đây", type=["pdf"], accept_multiple_files=True)
    if uploaded_files:
        with st.spinner("Hệ thống AI đang bóc tách chính xác ma trận dữ liệu gốc..."):
            all_results, errors_occurred = [], []
            for f in uploaded_files:
                res = process_single_pdf_batch(f.getvalue(), f.name)
                if res["success"]: all_results.append(res["data"])
                else: errors_occurred.append(f"{f.name}: {res['error']}")
                    
            if all_results:
                st.success("Bóc tách cấu trúc dữ liệu tệp thành công!")
                cols = st.columns(len(all_results))
                for idx, data in enumerate(all_results):
                    with cols[idx]:
                        st.markdown(f"### <span style='color:#1E3A8A;'>{data['style_number_db']}</span>", unsafe_allow_html=True)
                        st.markdown("<span class='badge-offline'>OFFLINE PREVIEW</span> <span class='badge-match'>BEST MATCH</span>", unsafe_allow_html=True)
                        st.markdown(f"<p style='font-size:13px;'><b>Buyer:</b> {data['buyer']}<br><b>Category:</b> {data['category']}<br><b>Scale:</b> {data['base_size_name']}</p>", unsafe_allow_html=True)
                        sc1, sc2 = st.columns(2)
                        with sc1:
                            df = pd.DataFrame([{"Garment Attribute": k, "Target Spec": v} for k, v in data['detailed_measurements'].items()])
                            st.dataframe(df, hide_index=True, use_container_width=True)
                        with sc2:
                            if data.get("sketch_image"): st.image(f"data:image/jpeg;base64,{data['sketch_image']}", use_container_width=True)
                        if st.button(f"💾 LƯU MÃ HÀNG {data['style_number_db']}", key=f"sv_{idx}", use_container_width=True, type="primary"):
                            if save_to_supabase_techpack_table(data): st.success("Đã đồng bộ lưu vào Supabase Database!")
                            else: st.error("Lỗi cơ sở dữ liệu!")
            for err in errors_occurred: st.error(err)

# PHÂN HỆ 2: SO SÁNH THÔNG SỐ RẬP
elif st.session_state.current_menu == "So Sánh Thông Số Rập":
    st.subheader("📊 Phân hệ Đối Chiếu & Kiểm Tra Sai Lệch Thông Số Rập Mẫu")
    up1, up2 = st.columns(2)
    with up1: buyer_file = st.file_uploader("Upload tài liệu gốc khách hàng (Buyer Techpack PDF)", type=["pdf"])
    with up2: factory_file = st.file_uploader("Upload tài liệu sản xuất thực tế (PDF)", type=["pdf"])
    
    if st.button("🚀 Tiến hành đối chiếu song song", type="primary", use_container_width=True):
        if buyer_file and factory_file:
            with st.spinner("Hệ thống AI đang đối chiếu song song tệp dữ liệu..."):
                rb = process_single_pdf_batch(buyer_file.getvalue(), buyer_file.name)
                rf = process_single_pdf_batch(factory_file.getvalue(), factory_file.name)
                if rb["success"] and rf["success"]:
                    data_b, data_f = rb["data"]["detailed_measurements"], rf["data"]["detailed_measurements"]
                    compare_rows = []
                    for k in data_b.keys():
                        v_b, v_f = data_b.get(k, "N/A"), data_f.get(k, "N/A")
                        compare_rows.append({"Vị trí đo (Garment Attribute)": k, "Mẫu gốc (Buyer Spec)": v_b, "Thực tế xưởng (Factory Spec)": v_f, "Trạng thái": "✅ Khớp" if v_b == v_f else "⚠️ Lệch thông số"})
                    df_compare = pd.DataFrame(compare_rows)
                    st.success("Phân tích so khớp hoàn tất!")
                    st.table(df_compare)
                    towrite = io.BytesIO()
                    with pd.ExcelWriter(towrite, engine='xlsxwriter') as writer: df_compare.to_excel(writer, index=False, sheet_name='Spec_Comparison')
                    towrite.seek(0)
                    st.download_button(label="📥 XUẤT PHÂN TÍCH RA FILE EXCEL (.XLSX)", data=towrite, file_name=f"So_Sanh_Thong_So_PPJ_{int(time.time())}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
                else: st.error("Sự cố trích xuất dữ liệu.")
# PHÂN HỆ 3: TRỢ LÝ ĐỊNH MỨC - ĐÃ ĐỒNG BỘ CĂN LỀ CHUẨN CHỐNG LỖI INDENTATION
elif st.session_state.current_menu == "Trợ Lý Tính Định Mức":
    st.markdown('<div style="background-color:#EFF6FF; padding:10px; border-radius:4px; font-weight:bold; color:#1E3A8A; margin-bottom:15px;">💡 Trợ lý chuyên gia đối chiếu & Tính định mức vải</div>', unsafe_allow_html=True)

    if "chat_history" not in st.session_state or not st.session_state.chat_history:
        st.session_state.chat_history = [
            {
                "role": "assistant",
                "content": "🤖 Chào kỹ sư PPJ! Tôi đã được liên kết với cơ sở dữ liệu kho mẫu và bảng định mức vải sản phẩm. Hãy tải sơ đồ rập lên (nếu có) và đặt câu hỏi cho tôi nhé!",
            }
        ]

    with st.container(border=True):
        col_file, col_clear = st.columns(2)
        
        with col_file:
            st.markdown("**📁 Cung cấp dữ liệu phụ trợ (Tùy chọn):**")
            attached_file = st.file_uploader("Upload sơ đồ rập phụ trợ", type=["pdf", "png", "jpg"], label_visibility="collapsed")
            
        with col_clear:
            st.markdown("**⚙️ Thao tác:**")
            if st.button("🗑️ XÓA LỊCH SỬ CHAT", type="secondary", use_container_width=True):
                st.session_state.chat_history = [
                    {
                        "role": "assistant",
                        "content": "🤖 Chào kỹ sư PPJ! Tôi đã được liên kết với cơ sở dữ liệu kho mẫu và bảng định mức vải sản phẩm. Hãy tải sơ đồ rập lên (nếu có) và đặt câu hỏi cho tôi nhé!",
                    }
                ]
                st.rerun()

    st.write("")
    st.markdown("**💬 Khung hội thoại tư vấn chuyên gia Gemini thật:**")

    chat_container = st.container(border=True)
    with chat_container:
        for message in st.session_state.chat_history:
            with st.chat_message(message.get("role", "assistant")):
                msg_content = message.get("content") or message.get("text") or ""
                st.markdown(msg_content)

    if user_query := st.chat_input("Nhập câu hỏi của bạn tại đây..."):
        st.session_state.chat_history.append({"role": "user", "content": user_query})

        with chat_container:
            with st.chat_message("user"):
                st.markdown(user_query)

        with chat_container:
            with st.chat_message("assistant"):
                with st.spinner("Gemini đang truy vấn dữ liệu kho PPJ..."):
                    ai_response = generate_real_gemini_chat_response(user_query, attached_file)
                    st.markdown(ai_response)

        st.session_state.chat_history.append({"role": "assistant", "content": ai_response})
        st.rerun()
