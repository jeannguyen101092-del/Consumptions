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

st.markdown("""
    <style>
    [data-testid="stSidebar"] { background-color: #f8f9fa; min-width: 280px; }
    .main-title { font-size: 26px; font-weight: bold; color: #1E3A8A; margin-bottom: 5px; }
    .badge-offline { background-color: #FEF3C7; color: #D97706; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; }
    .badge-match { background-color: #DBEAFE; color: #2563EB; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; }
    .chat-bubble-user { background-color: #E2E8F0; padding: 12px; border-radius: 8px; margin-bottom: 10px; color: #1E293B; }
    .chat-bubble-ai { background-color: #EFF6FF; padding: 12px; border-radius: 8px; margin-bottom: 10px; border-left: 4px solid #2563EB; color: #1E293B; }
    </style>
""", unsafe_allow_html=True)
SB_URL = "https://supabase.co"
SB_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImV3cXFvZHNmdmx2bnJ6c3lsYXd5Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzUxMTkyOTAsImV4cCI6MjA5MDY5NTI5MH0.BWPxOsyswBT5CLrZgluRC1F2x5EpU06oexUFyakGhyc"

def get_secure_gemini_key():
    if "GEMINI_API_KEY" in st.secrets:
        return st.secrets["GEMINI_API_KEY"].strip()
    return "AIzaSyD-UXlXWThLSlMxYTNfTkVfVTRfVjFfVjJfVjNfVjRfZg"

def save_to_supabase_techpack_table(payload_data):
    try:
        style_name_db = payload_data.get("style_number_db", "").strip()
        if not style_name_db: style_name_db = "UNKNOWN_STYLE"
        sketch_b64 = payload_data.get("sketch_image", "")
        public_image_url = ""

        if sketch_b64:
            try:
                image_data = base64.b64decode(sketch_b64)
                storage_headers = {"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}", "Content-Type": "image/jpeg", "x-upsert": "true"}
                clean_filename = re.sub(r'[^a-zA-Z0-9_-]', '', style_name_db)
                storage_url = f"{SB_URL.rstrip('/')}/storage/v1/object/kho_anh/{clean_filename}.jpg"
                upload_res = requests.post(storage_url, headers=storage_headers, data=image_data, timeout=20)
                if upload_res.status_code >= 200 and upload_res.status_code <= 299:
                    public_image_url = f"{SB_URL.rstrip('/')}/storage/v1/object/public/kho_anh/{clean_filename}.jpg"
            except Exception: pass

        headers = {"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}", "Content-Type": "application/json", "Prefer": "resolution=merge-duplicates"}
        insert_url = f"{SB_URL.rstrip('/')}/rest/v1/thong_so_techpack"
        
        raw_measurements = payload_data.get("detailed_measurements", {})
        clean_dict = {str(k): str(v) for k, v in dict(raw_measurements).items()}
        jsonb_ready_measurements = json.loads(json.dumps(clean_dict, ensure_ascii=True))

        db_payload = {"StyleName": style_name_db, "Buyer": payload_data.get("buyer"), "Category": payload_data.get("category"), "BaseSize": payload_data.get("base_size_name"), "DetailedMeasurements": jsonb_ready_measurements, "SketchURL": public_image_url}
        response = requests.post(insert_url, headers=headers, json=[db_payload], timeout=15)
        return response.status_code >= 200 and response.status_code <= 299
    except Exception: return False

def get_all_historical_styles_from_db():
    try:
        headers = {"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}"}
        url = f"{SB_URL.rstrip('/')}/rest/v1/thong_so_techpack?select=*&limit=100"
        res = requests.get(url, headers=headers, timeout=15)
        return res.json() if res.status_code >= 200 and res.status_code <= 299 else []
    except Exception: return []
def process_single_pdf_batch(file_bytes, file_name, manual_page=None):
    gemini_key = get_secure_gemini_key()
    if '.' in file_name: fallback_style = file_name.rsplit('.', 1)[0].strip()
    else: fallback_style = file_name.strip()

    try:
        info = pdfinfo_from_bytes(file_bytes)
        total_pages = int(info.get("Pages", 1))
        target_page = manual_page if manual_page else (total_pages - 1 if total_pages >= 3 else total_pages)
        if target_page > total_pages or target_page < 1: target_page = total_pages

        images = convert_from_bytes(file_bytes, dpi=160, first_page=target_page, last_page=target_page)
        if not images: return {"success": False, "error": "Không trích xuất được ảnh"}
        target_img = images[0].convert("RGB")
        img_buffer = io.BytesIO()
        target_img.save(img_buffer, format="JPEG", quality=95)
        raw_img_bytes = img_buffer.getvalue()

        sketch_base64 = ""
        try:
            backup_imgs = convert_from_bytes(file_bytes, dpi=120, first_page=1, last_page=1)
            if backup_imgs:
                bk_img = backup_imgs[0].convert("RGB")
                if bk_img.width > 450: bk_img = bk_img.resize((450, int(bk_img.height * (450 / bk_img.width))))
                bk_buf = io.BytesIO()
                bk_img.save(bk_buf, format="JPEG", quality=75)
                sketch_base64 = base64.b64encode(bk_buf.getvalue()).decode("utf-8")
        except Exception: pass

        key_value_schema = types.Schema(type=types.Type.OBJECT, properties={"pom_name": types.Schema(type=types.Type.STRING), "value": types.Schema(type=types.Type.STRING)}, required=["pom_name", "value"])
        techpack_schema = types.Schema(type=types.Type.OBJECT, properties={"style_number_parsed": types.Schema(type=types.Type.STRING), "buyer": types.Schema(type=types.Type.STRING), "category": types.Schema(type=types.Type.STRING), "base_size_name": types.Schema(type=types.Type.STRING), "measurements_list": types.Schema(type=types.Type.ARRAY, items=key_value_schema)}, required=["style_number_parsed", "buyer", "category", "base_size_name", "measurements_list"])

        user_prompt = "Extract Style ID, Buyer, Category, Base Size, and all measurement row values."
        client = genai.Client(api_key=gemini_key)
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[types.Part.from_bytes(data=raw_img_bytes, mime_type='image/jpeg'), user_prompt],
            config=types.GenerateContentConfig(response_mime_type="application/json", response_schema=techpack_schema, temperature=0.0)
        )

        parsed_data = json.loads(response.text.strip())
        dict_measurements = {}
        if "measurements_list" in parsed_data and parsed_data["measurements_list"]:
            for item in parsed_data["measurements_list"]:
                pom = item.get("pom_name", "").strip()
                val = item.get("value", "").strip()
                if pom: dict_measurements[pom] = val

        return {"success": True, "data": {
            "style_number_db": parsed_data.get("style_number_parsed", fallback_style),
            "buyer": parsed_data.get("buyer", "DULUTH TRADING CO"),
            "category": parsed_data.get("category", "DENIM WORK PANTS"),
            "base_size_name": parsed_data.get("base_size_name", "32 x 30"),
            "detailed_measurements": dict_measurements,
            "sketch_image": sketch_base64
        }}
    except Exception as e:
        return {"success": False, "error": str(e)}
if "current_menu" not in st.session_state: st.session_state.current_menu = "Quét Tài Liệu Techpack"
if "chat_history" not in st.session_state: st.session_state.chat_history = []

with st.sidebar:
    st.markdown("<div style='background-color: #1E3A8A; color: white; padding: 20px; border-radius: 8px; text-align: center; margin-bottom: 20px;'><h2 style='margin:0; font-size:22px;'>PPJ GROUP</h2></div>", unsafe_allow_html=True)
    if st.button("📄 Quét Tài Liệu Techpack", use_container_width=True, type="primary" if st.session_state.current_menu == "Quét Tài Liệu Techpack" else "secondary"): st.session_state.current_menu = "Quét Tài Liệu Techpack"; st.rerun()
    if st.button("📊 So Sánh Thông Số Rập", use_container_width=True, type="primary" if st.session_state.current_menu == "So Sánh Thông Số Rập" else "secondary"): st.session_state.current_menu = "So Sánh Thông Số Rập"; st.rerun()
    if st.button("🌾 Trợ Lý Tính Định Mức", use_container_width=True, type="primary" if st.session_state.current_menu == "Trợ Lý Tính Định Mức" else "secondary"): st.session_state.current_menu = "Trợ Lý Tính Định Mức"; st.rerun()

st.markdown("<div class='main-title'>PPJ GROUP — Content Management System</div>", unsafe_allow_html=True)
st.markdown(f"<p style='color:#64748B;'>Phân hệ: <b>{st.session_state.current_menu}</b></p>", unsafe_allow_html=True)
st.markdown("---")
if st.session_state.current_menu == "Quét Tài Liệu Techpack":
    uploaded_files = st.file_uploader("Kéo thả tài liệu PDF vào đây", type=["pdf"], accept_multiple_files=True)
    if uploaded_files:
        with st.spinner("Đang trích xuất..."):
            all_results = []
            for f in uploaded_files:
                res = process_single_pdf_batch(f.getvalue(), f.name)
                if res["success"]:
                    all_results.append(res["data"])
                    
            if all_results:
                cols = st.columns(len(all_results))
                for idx, data in enumerate(all_results):
                    with cols[idx]:
                        st.markdown(f"### {data['style_number_db']}")
                        st.markdown(f"<p style='font-size:13px;'><b>Buyer:</b> {data['buyer']}<br><b>Category:</b> {data['category']}</p>", unsafe_allow_html=True)
                        sc1, sc2 = st.columns(2)
                        with sc1: st.dataframe(pd.DataFrame([{"Garment Attribute": k, "Target Spec": v} for k, v in data['detailed_measurements'].items()]), hide_index=True)
                        with sc2:
                            if data.get("sketch_image"): st.image(f"data:image/jpeg;base64,{data['sketch_image']}", use_container_width=True)
                        if st.button(f"💾 LƯU MÃ HÀNG {data['style_number_db']}", key=f"sv_{idx}", use_container_width=True, type="primary"):
                            if save_to_supabase_techpack_table(data): st.success("Đã lưu Supabase!")
                            else: st.error("Lỗi kết nối!")

elif st.session_state.current_menu == "So Sánh Thông Số Rập":
    up1, up2 = st.columns(2)
    with up1: buyer_file = st.file_uploader("Upload tài liệu khách hàng (PDF)", type=["pdf"])
    with up2: factory_file = st.file_uploader("Upload tài liệu nhà máy (PDF)", type=["pdf"])
    if st.button("🚀 Tiến hành đối chiếu song song", type="primary", use_container_width=True):
        if buyer_file and factory_file:
            rb = process_single_pdf_batch(buyer_file.getvalue(), buyer_file.name)
            rf = process_single_pdf_batch(factory_file.getvalue(), factory_file.name)
            if rb["success"] and rf["success"]:
                rows = [{"Vị trí đo": k, "Mẫu gốc": rb["data"]["detailed_measurements"].get(k, "N/A"), "Thực tế xưởng": rf["data"]["detailed_measurements"].get(k, "N/A")} for k in rb["data"]["detailed_measurements"].keys()]
                st.table(pd.DataFrame(rows))

elif st.session_state.current_menu == "Trợ Lý Tính Định Mức":
    chat_file = st.file_uploader("Upload ảnh cấu trúc vải", type=["pdf", "png", "jpg"])
    for chat in st.session_state.chat_history:
        st.markdown(f"<div class='chat-bubble-user'><b>Bạn:</b> {chat['text']}</div>" if chat["role"]=="user" else f"<div class='chat-bubble-ai'><b>AI:</b> {chat['text']}</div>", unsafe_allow_html=True)
    u_msg = st.chat_input("Hỏi về định mức vải...")
    if u_msg:
        st.session_state.chat_history.append({"role": "user", "text": u_msg})
        try:
            client = genai.Client(api_key=get_secure_gemini_key())
            response = client.models.generate_content(model='gemini-2.5-flash', contents=[f"Bạn là trợ lý AI PPJ Group: {u_msg}"])
            ai_reply = response.text.strip()
        except Exception as e: ai_reply = f"Lỗi kết nối AI: {str(e)}"
        st.session_state.chat_history.append({"role": "ai", "text": ai_reply})
        st.rerun()
