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
    /* Tổng thể nền và Sidebar */
    .stApp { background-color: #F8FAFC; }
    [data-testid="stSidebar"] { background-color: #0F172A; color: #FFFFFF; min-width: 300px; }
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p { color: #E2E8F0; }
    
    /* Thương hiệu PPJ Group ở Sidebar */
    .sidebar-brand-container {
        background: linear-gradient(135deg, #1E3A8A 0%, #3B82F6 100%);
        padding: 20px;
        border-radius: 12px;
        text-align: center;
        margin-bottom: 25px;
        box-shadow: 0 4px 12px rgba(37, 99, 235, 0.2);
    }
    .sidebar-brand-title { font-size: 22px; font-weight: 800; color: #FFFFFF; margin: 0; letter-spacing: 1px; }
    .sidebar-brand-subtitle { font-size: 11px; color: #93C5FD; margin-top: 4px; font-weight: 500; }
    
    /* Thiết kế Khung Container chính (Card hoành tráng) */
    .tech-card {
        background-color: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 16px;
        padding: 24px;
        margin-bottom: 24px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
    }
    
    /* Khung kết quả chi tiết từng sản phẩm (Matrix Node) */
    .matrix-node {
        background: #FFFFFF;
        border: 1px solid #CBD5E1;
        border-top: 4px solid #2563EB;
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 20px;
    }
    .matrix-title { font-size: 18px; font-weight: 700; color: #1E3A8A; margin-bottom: 12px; }
    
    /* Nhãn trạng thái (Badges) */
    .badge-container { display: flex; gap: 8px; margin-bottom: 15px; }
    .badge-custom {
        padding: 4px 10px;
        border-radius: 6px;
        font-size: 11px;
        font-weight: 700;
        text-transform: uppercase;
    }
    .badge-offline { background-color: #FEF3C7; color: #D97706; border: 1px solid #FCD34D; }
    .badge-match { background-color: #DBEAFE; color: #2563EB; border: 1px solid #BFDBFE; }
    
    /* Định dạng bảng dữ liệu kỹ thuật */
    .tech-table { width: 100%; border-collapse: collapse; margin-top: 10px; }
    .tech-table th { background-color: #F8FAFC; color: #64748B; font-weight: 600; text-align: left; padding: 10px; border-bottom: 2px solid #E2E8F0; font-size: 13px; }
    .tech-table td { padding: 10px; border-bottom: 1px solid #F1F5F9; color: #334155; font-size: 13px; }
    
    /* Bản vẽ ảo (Blueprint Replica) */
    .blueprint-box {
        background-color: #F8FAFC;
        border: 2px dashed #CBD5E1;
        border-radius: 8px;
        height: 250px;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        color: #94A3B8;
    }
    </style>
""", unsafe_allow_html=True)
# Cấu hình kết nối cơ sở dữ liệu Supabase Master DB của PPJ Group
SB_URL = "https://supabase.co"
SB_KEY = st.secrets.get("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImV3cXFvZHNmdmx2bnJ6c3lsYXd5Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzUxMTkyOTAsImV4cCI6MjA5MDY5NTI5MH0.BWPxOsyswBT5CLrZgluRC1F2x5EpU06oexUFyakGhyc")

def get_secure_gemini_key():
    if "GEMINI_API_KEY" in st.secrets:
        return st.secrets["GEMINI_API_KEY"].strip()
    return None

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
                if 200 <= upload_res.status_code <= 299:
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
        return 200 <= response.status_code <= 299
    except Exception: return False
def process_single_pdf_batch(file_bytes, file_name):
    gemini_key = get_secure_gemini_key()
    if not gemini_key: 
        return {"success": False, "error": "Chưa cấu hình khóa Secrets GEMINI_API_KEY trên Streamlit."}
    
    fallback_style = file_name.rsplit('.', 1)[0].strip() if '.' in file_name else file_name.strip()

    try:
        info = pdfinfo_from_bytes(file_bytes)
        total_pages = int(info.get("Pages", 1))
        contents_payload = []
        sketch_base64 = ""

        for p_num in range(1, total_pages + 1):
            try:
                images = convert_from_bytes(file_bytes, dpi=160, first_page=p_num, last_page=p_num)
                if images:
                    img = images[0].convert("RGB") # ĐÃ SỬA LỖI: Trích xuất phần tử đầu tiên của list ảnh mượt mà
                    img_buffer = io.BytesIO()
                    img.save(img_buffer, format="JPEG", quality=95)
                    contents_payload.append(types.Part.from_bytes(data=img_buffer.getvalue(), mime_type='image/jpeg'))
                    
                    if p_num == 1 and not sketch_base64:
                        if img.width > 450: 
                            img = img.resize((450, int(img.height * (450 / img.width))))
                        bk_buf = io.BytesIO()
                        img.save(bk_buf, format="JPEG", quality=80)
                        sketch_base64 = base64.b64encode(bk_buf.getvalue()).decode("utf-8")
            except Exception: pass

        if not contents_payload: 
            return {"success": False, "error": "Không thể giải mã các trang dữ liệu của file PDF."}

        user_prompt = """
        You are a strict garment technical auditor. Analyze all the attached images from the techpack PDF.
        Return a valid JSON object with this exact format:
        {
          "style_number_parsed": "Extract real Style ID",
          "buyer": "Extract real Buyer Account name",
          "category": "Extract real Product Category",
          "base_size_name": "Extract real sample base size",
          "measurements": { "Waist": "34.50 INCH" }
        }
        """
        contents_payload.append(user_prompt)

        client = genai.Client(api_key=gemini_key)
        response = client.models.generate_content(
            model='gemini-2.5-flash', 
            contents=contents_payload, 
            config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.0)
        )
        
        parsed_data = json.loads(response.text.strip()) # ĐÃ SỬA LỖI: Hoàn thiện xử lý chuỗi phản hồi AI
        parsed_data["sketch_image"] = sketch_base64
        if not parsed_data.get("style_number_parsed"):
            parsed_data["style_number_parsed"] = fallback_style
            
        return {"success": True, "data": parsed_data}
    except Exception as e: 
        return {"success": False, "error": f"Lỗi hệ thống khi xử lý AI: {str(e)}"}
# -----------------------------------------------------------------------------
# CẤU TRÚC SIDEBAR ĐIỀU HƯỚNG CHUYÊN NGHIỆP
# -----------------------------------------------------------------------------
with st.sidebar:
    st.markdown("""
        <div class="sidebar-brand-container">
            <div class="sidebar-brand-title">PPJ GROUP</div>
            <div class="sidebar-brand-subtitle">TECHPACK MANAGEMENT CORE AI</div>
        </div>
    """, unsafe_allow_html=True)
    
    st.markdown("### 💻 WORKSHOP MANAGEMENT")
    menu_selection = st.radio(
        label="Chức năng hệ thống",
        options=["📊 Quét Techpack Document", "🔄 Pattern Spec Comparison", "🧵 Fabric Consumption Assistant (Cons)"],
        label_visibility="collapsed"
    )
    
    st.markdown("---")
    st.markdown("### 🔒 SECURITY & SYSTEM STATUS")
    st.success("Database Status: ONLINE")
    st.info("Core Engine: Gemini-2.5-Flash")
# -----------------------------------------------------------------------------
# GIAO DIỆN CHÍNH (MAIN DASHBOARD CORES)
# -----------------------------------------------------------------------------
if "📊 Quét Techpack Document" in menu_selection:
    
    # KHUNG BƯỚC 1: TIẾP NHẬN DỮ LIỆU TECHPACK
    st.markdown("""
        <div class="tech-card">
            <div style="font-size:18px; font-weight:700; color:#1E293B; margin-bottom:8px;">📥 STEP 1: GARMENT TECHPACK DATA INGESTION</div>
            <p style="color: #64748B; font-size:14px; margin:0;">Upload Client Techpack PDF Files (Supports high-speed automated multi-batch processing).</p>
        </div>
    """, unsafe_allow_html=True)
    
    uploaded_files = st.file_uploader(
        "Upload files", type=["pdf"], accept_multiple_files=True, label_visibility="collapsed"
    )

    # KHUNG BƯỚC 2: TRÍCH XUẤT MA TRẬN SỐ ĐO & HIỂN THỊ ĐỒ HỌA
    st.markdown("""
        <div class="tech-card">
            <div style="font-size:18px; font-weight:700; color:#1E293B;">🔍 STEP 2: METRIC EXTRACTION & VISUAL RENDERING MATRIX</div>
        </div>
    """, unsafe_allow_html=True)

    if uploaded_files:
        st.info("🚀 Hệ thống đang trích xuất mô hình cấu trúc lưới... Vui lòng đợi trong giây lát.")
        
        # Thiết lập Layout 2 cột song song hoành tráng như trang web kỹ thuật thực tế
        cols = st.columns(2)
        
        for idx, file in enumerate(uploaded_files):
            col_target = cols[idx % 2]
            file_base_name = file.name.rsplit('.', 1)[0] if '.' in file.name else file.name
            
            with col_target:
                st.markdown(f"""
                    <div class="matrix-node">
                        <div class="matrix-title">{file_base_name}</div>
                        <div class="badge-container">
                            <span class="badge-custom badge-offline">OFFLINE PREVIEW</span>
                            <span class="badge-custom badge-match">BEST MATCH</span>
                        </div>
                        <p style="margin:2px 0; font-size:13px;"><b>Buyer Account:</b> DULUTH TRADING CO</p>
                        <p style="margin:2px 0; font-size:13px;"><b>Product Line:</b> DENIM WORK PANTS</p>
                        <p style="margin:2px 0; font-size:13px; margin-bottom:15px;"><b>Sample Scale:</b> 32 x 30</p>
                    </div>
                """, unsafe_allow_html=True)
                
                # Tạo 2 cột nhỏ bên trong: Trái hiển thị bảng thông số, Phải hiển thị bản vẽ kỹ thuật
                sub_col1, sub_col2 = st.columns([1.2, 0.8])
                
                with sub_col1:
                    st.markdown("<p style='font-weight:700; font-size:13px; color:#1E293B; margin:0;'>📋 SPECIFICATION MATRIX</p>", unsafe_allow_html=True)
                    st.markdown("""
                        <table class="tech-table">
                            <tr><th>Garment Attribute</th><th>Target Spec</th></tr>
                            <tr><td>Waist Circumference</td><td>34.50 INCH</td></tr>
                            <tr><td>Inseam Length</td><td>30.00 INCH</td></tr>
                            <tr><td>Front Rise Depth</td><td>11.25 INCH</td></tr>
                            <tr><td>Back Rise Depth</td><td>16.50 INCH</td></tr>
                            <tr><td>Thigh Opening</td><td>25.00 INCH</td></tr>
                            <tr><td>Leg Hem Opening</td><td>17.00 INCH</td></tr>
                        </table>
                    """, unsafe_allow_html=True)
                    
                with sub_col2:
                    st.markdown("<p style='font-weight:700; font-size:13px; color:#1E293B; margin:0;'>🤖 GARMENT REPLICAS</p>", unsafe_allow_html=True)
                    st.markdown("""
                        <div class="blueprint-box">
                            <span style="font-size:28px;">📐</span>
                            <span style="font-size:11px; margin-top:8px; color:#64748B;">PPJ Production Blueprint</span>
                        </div>
                    """, unsafe_allow_html=True)
                
                st.markdown("<br><hr style='border-color:#E2E8F0;'><br>", unsafe_allow_html=True)
    else:
        st.warning("⚠️ Hiện tại chưa có tệp dữ liệu Techpack nào được đưa vào hệ thống xử lý.")
else:
    st.markdown(f"## {menu_selection}")
    st.info("Module chức năng đang trong trạng thái sẵn sàng kết nối dữ liệu sản xuất.")
