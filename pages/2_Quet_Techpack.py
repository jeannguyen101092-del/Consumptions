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

# Khởi tạo giao diện CSS chuyên nghiệp
st.markdown("""
    <style>
    [data-testid="stSidebar"] { background-color: #f8f9fa; min-width: 280px; }
    .main-title { font-size: 26px; font-weight: bold; color: #1E3A8A; margin-bottom: 5px; }
    .step-title { font-size: 18px; font-weight: bold; color: #0F172A; margin-top: 20px; margin-bottom: 10px; }
    .badge-offline { background-color: #FEF3C7; color: #D97706; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; }
    .badge-match { background-color: #DBEAFE; color: #2563EB; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; }
    .chat-bubble-user { background-color: #E2E8F0; padding: 12px; border-radius: 8px; margin-bottom: 10px; color: #1E293B; }
    .chat-bubble-ai { background-color: #EFF6FF; padding: 12px; border-radius: 8px; margin-bottom: 10px; border-left: 4px solid #2563EB; color: #1E293B; }
    </style>
""", unsafe_allow_html=True)
# Thông tin kết nối Supabase Master DB của PPJ Group
SB_URL = "https://supabase.co"
SB_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImV3cXFvZHNmdmx2bnJ6c3lsYXd5Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzUxMTkyOTAsImV4cCI6MjA5MDY5NTI5MH0.BWPxOsyswBT5CLrZgluRC1F2x5EpU06oexUFyakGhyc"

def get_secure_gemini_key():
    if "GEMINI_API_KEY" in st.secrets:
        return st.secrets["GEMINI_API_KEY"].strip()
    return "AIzaSyD-UXlXWThLSlMxYTNfTkVfVTRfVjFfVjJfVjNfVjRfZg"

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
    """Hàm trích xuất dữ liệu định mức vải tự động lọc ilike chuẩn xác cột trên bảng san_pham"""
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

        # Duyệt qua toàn bộ các trang của file PDF để bóc tách triệt để không sót bảng biểu
        for p_num in range(1, total_pages + 1):
            try:
                images = convert_from_bytes(file_bytes, dpi=150, first_page=p_num, last_page=p_num)
                if images:
                    img = images[0].convert("RGB")
                    img_buffer = io.BytesIO()
                    img.save(img_buffer, format="JPEG", quality=95)
                    img_bytes = img_buffer.getvalue()
                    contents_payload.append(types.Part.from_bytes(data=img_bytes, mime_type='image/jpeg'))
                    
                    # Lấy hình ảnh trang đầu tiên làm bản vẽ Sketch kỹ thuật mặt trước
                    if p_num == 1 and not sketch_base64:
                        if img.width > 450:
                            img = img.resize((450, int(img.height * (450 / img.width))))
                        bk_buf = io.BytesIO()
                        img.save(bk_buf, format="JPEG", quality=85)
                        sketch_base64 = base64.b64encode(bk_buf.getvalue()).decode("utf-8")
            except Exception: pass

        if not contents_payload:
            return {"success": False, "error": "Không thể giải mã các trang dữ liệu của file PDF."}

        # Prompt kiểm toán nghiêm ngặt: Ép AI trả ra dữ liệu thật, không có là báo lỗi không tự bịa thông số
        user_prompt = """
        You are a strict garment technical auditor. Analyze all the attached images from the techpack PDF.
        1. Locate the specification grid/table containing Point of Measurements (POM) and their target spec values.
        2. Extract EVERY SINGLE measurement row exactly as written in the document. Do not miss any rows.
        3. Do not invent, fake, hallucinate, or use default fallback numbers. If no measurement table is found, return the measurements dictionary empty.
        
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
            return {"success": False, "error": "AI không tìm thấy hoặc tài liệu quá mờ để đọc chính xác lưới ma trận thông số đo gốc."}

        return {"success": True, "data": {
            "style_number_db": parsed_data.get("style_number_parsed") or fallback_style,
            "buyer": parsed_data.get("buyer") or "UNKNOWN BUYER",
            "category": parsed_data.get("category") or "PRODUCTION GARMENT",
            "base_size_name": parsed_data.get("base_size_name") or "N/A",
            "detailed_measurements": dict_measurements,
            "sketch_image": sketch_base64
        }}
    except Exception as e:
        return {"success": False, "error": f"Lỗi xử lý tệp: {str(e)}"}
if "current_menu" not in st.session_state: st.session_state.current_menu = "Quét Tài Liệu Techpack"
if "chat_history" not in st.session_state: st.session_state.chat_history = []

with st.sidebar:
    st.markdown("<div style='background-color: #1E3A8A; color: white; padding: 20px; border-radius: 8px; text-align: center; margin-bottom: 20px;'><h2 style='margin:0; font-size:22px; font-weight:bold;'>PPJ GROUP</h2><p style='margin:0; font-size:11px; opacity:0.8;'>Boundless solutions</p></div>", unsafe_allow_html=True)
    if st.button("📄 Quét Tài Liệu Techpack", use_container_width=True, type="primary" if st.session_state.current_menu == "Quét Tài Liệu Techpack" else "secondary"): st.session_state.current_menu = "Quét Tài Liệu Techpack"; st.rerun()
    if st.button("📊 So Sánh Thông Số Rập", use_container_width=True, type="primary" if st.session_state.current_menu == "So Sánh Thông Số Rập" else "secondary"): st.session_state.current_menu = "So Sánh Thông Số Rập"; st.rerun()
    if st.button("🌾 Trợ Lý Tính Định Mức", use_container_width=True, type="primary" if st.session_state.current_menu == "Trợ Lý Tính Định Mức" else "secondary"): st.session_state.current_menu = "Trợ Lý Tính Định Mức"; st.rerun()

st.markdown("<div class='main-title'>PPJ GROUP — Content Management System</div>", unsafe_allow_html=True)
st.markdown(f"<p style='color:#64748B; margin-top:-5px;'>Phân hệ đang hoạt động: <b>{st.session_state.current_menu}</b></p>", unsafe_allow_html=True)
st.markdown("---")
# PHÂN HỆ 1: QUÉT TÀI LIỆU TECHPACK
if st.session_state.current_menu == "Quét Tài Liệu Techpack":
    uploaded_files = st.file_uploader("Kéo thả tài liệu PDF vào đây", type=["pdf"], accept_multiple_files=True)
    if uploaded_files:
        with st.spinner("Hệ thống AI đang bóc tách chính xác ma trận dữ liệu gốc..."):
            all_results = []
            errors_occurred = []
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
                        st.markdown(f"<p style='font-size:13px;'><b>Buyer Account:</b> {data['buyer']}<br><b>Product Line:</b> {data['category']}<br><b>Sample Scale:</b> {data['base_size_name']}</p>", unsafe_allow_html=True)
                        
                        sub_col1, sub_col2 = st.columns(2)
                        with sub_col1:
                            st.markdown("📋 **SPECIFICATION MATRIX**")
                            df = pd.DataFrame([{"Garment Attribute": k, "Target Spec": v} for k, v in data['detailed_measurements'].items()])
                            st.dataframe(df, hide_index=True, use_container_width=True)
                        with sub_col2:
                            st.markdown("🗺️ **GARMENT REPLICAS**")
                            if data.get("sketch_image"): st.image(f"data:image/jpeg;base64,{data['sketch_image']}", use_container_width=True)
                            else: st.warning("Không có hình ảnh bản vẽ.")
                        
                        if st.button(f"💾 LƯU MÃ HÀNG {data['style_number_db']}", key=f"sv_{idx}", use_container_width=True, type="primary"):
                            with st.spinner("Đang đồng bộ dữ liệu..."):
                                if save_to_supabase_techpack_table(data): st.success(f"Đã lưu mã {data['style_number_db']} vào Supabase!")
                                else: st.error("Lỗi đồng bộ cơ sở dữ liệu bảng!")
            for err in errors_occurred: st.error(err)

# PHÂN HỆ 2: SO SÁNH THÔNG SỐ RẬP (ĐỐI CHIẾU THỰC TẾ FILE THEO ĐÚNG HÀM AI)
elif st.session_state.current_menu == "So Sánh Thông Số Rập":
    st.subheader("📊 Phân hệ Đối Chiếu & Kiểm Tra Sai Lệch Thông Số Rập Mẫu")
    st.markdown("##### 📥 Tải lên 2 tệp tài liệu để tiến hành kiểm tra so sánh đối chiếu song song:")
    up1, up2 = st.columns(2)
    with up1: buyer_file = st.file_uploader("Upload tài liệu gốc khách hàng (Buyer Techpack PDF)", type=["pdf"])
    with up2: factory_file = st.file_uploader("Upload tài liệu sản xuất thực tế (Factory Spec PDF)", type=["pdf"])
    
    if st.button("🚀 Tiến hành đối chiếu song song", type="primary", use_container_width=True):
        if buyer_file and factory_file:
            with st.spinner("Hệ thống AI đang đọc đồng thời cả 2 tệp dữ liệu thật..."):
                rb = process_single_pdf_batch(buyer_file.getvalue(), buyer_file.name)
                rf = process_single_pdf_batch(factory_file.getvalue(), factory_file.name)
                if rb["success"] and rf["success"]:
                    data_b = rb["data"]["detailed_measurements"]
                    data_f = rf["data"]["detailed_measurements"]
                    compare_rows = []
                    for k in data_b.keys():
                        v_b = data_b.get(k, "N/A")
                        v_f = data_f.get(k, "N/A")
                        compare_rows.append({"Vị trí đo (Garment Attribute)": k, "Mẫu gốc (Buyer Spec)": v_b, "Thực tế xưởng (Factory Spec)": v_f, "Trạng thái đánh giá": "✅ Khớp" if v_b == v_f else "⚠️ Lệch thông số"})
                    st.success("Bảng ma trận đối chiếu sai lệch thông số thực tế:")
                    st.table(pd.DataFrame(compare_rows))
                else: st.error(f"Sự cố trích xuất so sánh: {rb.get('error') or rf.get('error')}")
        else: st.warning("Vui lòng tải lên đầy đủ cả 2 file tài liệu để hệ thống đối chiếu.")

# PHÂN HỆ 3: TRỢ LÝ ĐỊNH MỨC (CHAT VỚI AI VÀ TRA CỨU KHO DỮ LIỆU THẬT SUPABASE)
elif st.session_state.current_menu == "Trợ Lý Tính Định Mức":
    st.subheader("🌾 Trợ Lý Chat AI Tính Toán Định Mức Nguyên Phụ Liệu Tự Động")
    chat_file = st.file_uploader("Upload ảnh cấu trúc hoặc tài liệu định mức nguyên phụ liêu", type=["pdf", "png", "jpg"])
    
    for chat in st.session_state.chat_history:
        if chat.get("role") == "user": st.markdown(f"<div class='chat-bubble-user'><b>Bạn:</b> {chat.get('text')}</div>", unsafe_allow_html=True)
        else: st.markdown(f"<div class='chat-bubble-ai'><b>AI PPJ Assistant:</b> {chat.get('text')}</div>", unsafe_allow_html=True)
            
    u_msg = st.chat_input("Nhập câu hỏi tra cứu định mức hoặc từ khóa mã hàng cần tìm kiếm...")
    if u_msg:
        st.session_state.chat_history.append({"role": "user", "text": u_msg})
        with st.spinner("Đang truy vấn kho dữ liệu dệt may..."):
            try:
                # Tự động quét tìm kiếm tương đồng trên bảng san_pham của Supabase DB bằng từ khóa chat của bạn
                db_results = get_historical_fabric_consumption_from_db(u_msg)
                context_db = ""
                if db_results: context_db = f"\nDữ liệu định mức vải thật tìm thấy trong Supabase DB cho từ khóa này: {json.dumps(db_results, ensure_ascii=False)}"
                
                client = genai.Client(api_key=get_secure_gemini_key())
                response = client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=[f"Bạn là trợ lý kỹ thuật nhà xưởng PPJ Group. Hãy phân tích câu hỏi người dùng dựa trên dữ liệu thật của kho phụ liệu nếu có. Câu hỏi: {u_msg}. {context_db}"]
                )
                ai_reply = response.text.strip()
            except Exception as e: ai_reply = f"Lỗi kết nối AI xử lý: {str(e)}"
        st.session_state.chat_history.append({"role": "ai", "text": ai_reply})
        st.rerun()
