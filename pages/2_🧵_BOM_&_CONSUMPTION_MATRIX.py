import base64
import io
import json
import re
import requests
import streamlit as st
import pandas as pd
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

# ĐỒ HỌA HIGH-CONTRAST INDUSTRIAL LIGHT THEME (XÓA BỎ BÓNG TỐI, CỐ ĐỊNH CHỮ RÕ NÉT)
st.markdown("""
    <style>
    /* Ép toàn bộ nền ứng dụng về màu xám trắng phòng thí nghiệm sạch sẽ */
    .stApp { background-color: #F8FAFC !important; }
    
    /* Thiết kế thanh điều hướng Sidebar màu trắng tinh, chữ xanh đen tương phản */
    [data-testid="stSidebar"] { 
        background-color: #FFFFFF !important; 
        border-right: 1px solid #CBD5E1 !important;
        min-width: 320px; 
    }
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p { 
        color: #1E293B !important; font-weight: 600; font-size: 13.5px;
    }
    
    /* Khung thương hiệu PPJ Group hiệu ứng Gradient cao cấp */
    .sidebar-brand-container {
        background: linear-gradient(135deg, #1E3A8A 0%, #3B82F6 100%);
        padding: 22px; border-radius: 14px; text-align: center; margin-bottom: 30px;
        box-shadow: 0 4px 14px rgba(37, 99, 235, 0.2);
    }
    .sidebar-brand-title { font-size: 24px; font-weight: 800; color: #FFFFFF; margin: 0; letter-spacing: 1px; }
    .sidebar-brand-subtitle { font-size: 11px; color: #BFDBFE; margin-top: 5px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; }
    
    /* Thiết kế tiêu đề phân hệ lớn dạng dải màu Gradient hoành tráng */
    .component-title-box {
        background: linear-gradient(90deg, #1E3A8A 0%, #2563EB 100%);
        color: #FFFFFF !important; font-size: 16px; font-weight: 700; padding: 14px 20px;
        border-radius: 10px; margin-bottom: 25px; letter-spacing: 0.5px; text-transform: uppercase;
        box-shadow: 0 4px 12px rgba(30, 58, 138, 0.1);
    }
    
    /* Thiết kế Khung Container (Card hoành tráng, có đổ bóng tách biệt không gian) */
    .card-container {
        background-color: #FFFFFF !important; border: 1px solid #E2E8F0 !important; border-radius: 14px !important;
        padding: 24px; margin-bottom: 25px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.03) !important;
    }
    
    /* Lưới thông tin Metadata bọc khung xám nhẹ */
    .metric-grid-box {
        display: flex; gap: 25px; background: #F8FAFC; padding: 14px 20px; border-radius: 10px; border: 1px solid #E2E8F0; margin-bottom: 20px;
    }
    .metric-label { font-size: 11px; font-weight: 700; color: #64748B; margin: 0; text-transform: uppercase; letter-spacing: 0.5px; }
    .metric-value { font-size: 14px; font-weight: 700; color: #1E3A8A; margin: 3px 0 0 0; }
    
    /* Bộ khung chứa bảng thông số kỹ thuật mượt mà */
    .data-table-container {
        max-height: 420px; overflow-y: auto; border: 1px solid #CBD5E1; border-radius: 10px; margin-top: 12px; background: white;
    }
    
    /* Định dạng bảng dữ liệu dệt may công nghiệp */
    .industrial-table { width: 100%; border-collapse: collapse; text-align: left; }
    .industrial-table th {
        background-color: #F1F5F9 !important; color: #1E3A8A !important; font-weight: 700 !important; padding: 12px 16px; font-size: 13px; position: sticky; top: 0; z-index: 5; border-bottom: 2px solid #CBD5E1 !important;
    }
    .industrial-table td { padding: 11px 16px; border-bottom: 1px solid #E2E8F0; color: #334155 !important; font-size: 13px; }
    .industrial-table tr:hover { background-color: #F8FAFC !important; }
    
    /* Khung thông báo trạng thái rỗng (Hệ thống IDLE) */
    .idle-alert-box {
        background-color: #FFFBEB; border-left: 5px solid #F59E0B; padding: 16px 20px; border-radius: 4px 12px 12px 4px; color: #B45309; font-size: 13.5px; font-weight: 600;
    }
    
    /* Ép toàn bộ màu chữ của bong bóng Chatbot về màu xám đậm trên nền trắng để nhìn rõ 100% */
    [data-testid="stChatMessage"] { background-color: #FFFFFF !important; border: 1px solid #CBD5E1 !important; border-radius: 12px !important; box-shadow: 0 2px 5px rgba(0,0,0,0.02) !important; }
    [data-testid="stChatMessage"] p { color: #0F172A !important; font-size: 14px !important; font-weight: 500 !important; line-height: 1.6 !important; }
    
    /* Đồng bộ màu chữ cho văn bản Streamlit tiêu chuẩn */
    [data-testid="stMarkdownContainer"] p, [data-testid="stMarkdownContainer"] h5 { color: #1E293B !important; }
    </style>
""", unsafe_allow_html=True)
# Cấu hình cổng kết nối Master DB của Tập đoàn PPJ Group
SB_URL = "https://ewqqodsfvlvnrzsylawy.supabase.co"
SB_KEY = st.secrets.get("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInRefI6ImV3cXFvZHNmdmx2bnJ6c3lsYXd5Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzUxMTkyOTAsImV4cCI6MjA5MDY5NTI5MH0.BWPxOsyswBT5CLrZgluRC1F2x5EpU06oexUFyakGhyc")

def get_secure_gemini_key():
    """Hàm bảo mật trích xuất Token API chìa khóa phân tích từ bộ Secrets"""
    if "GEMINI_API_KEY" in st.secrets:
        return st.secrets["GEMINI_API_KEY"].strip()
    return None

def save_to_supabase_techpack_table(payload_data):
    """Hàm xử lý đồng bộ và nạp Master DB bảng thong_so_techpack kết hợp đẩy ảnh lên Storage kho_anh"""
    try:
        style_name_db = payload_data.get("style_number_parsed", "").strip()
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
            except Exception: 
                pass

        headers = {
            "apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}",
            "Content-Type": "application/json", "Prefer": "resolution=merge-duplicates"
        }
        insert_url = f"{SB_URL.rstrip('/')}/rest/v1/thong_so_techpack"
        
        raw_measurements = payload_data.get("measurements", {})
        clean_dict = {str(k): str(v) for k, v in dict(raw_measurements).items()}

        db_payload = {
            "StyleName": style_name_db,
            "Buyer": payload_data.get("buyer"),
            "Category": payload_data.get("category"),
            "BaseSize": payload_data.get("base_size_name"),
            "DetailedMeasurements": clean_dict,
            "SketchURL": public_image_url
        }
        response = requests.post(insert_url, headers=headers, json=[db_payload], timeout=15)
        return 200 <= response.status_code <= 299
    except Exception: 
        return False

def get_historical_fabric_consumption_from_db(search_keyword=None):
    """Hàm tra cứu kho dữ liệu san_pham lịch sử phục vụ lập luận toán học Delta Cons phụ trợ"""
    try:
        headers = {"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}"}
        url = f"{SB_URL.rstrip('/')}/rest/v1/san_pham"
        query_params = {
            "select": "style_name,article_name,consumption_type,material_size,uom,consumption_value,notes",
            "limit": 10
        }
        if search_keyword:
            clean_kw = str(search_keyword).strip()
            if '-' in clean_kw:
                query_params["style_name"] = f"ilike.*{clean_kw.split('-')[-1].strip()}*"
            else:
                query_params["style_name"] = f"ilike.*{clean_kw}*"
                
        res = requests.get(url, headers=headers, params=query_params, timeout=15)
        return res.json() if 200 <= res.status_code <= 299 else []
    except Exception: 
        return []
def process_single_pdf_batch(file_bytes, file_name):
    """
    Hệ thống bóc tách tự động đa tầng: Chuyển đổi mã nhị phân PDF sang mô hình 
    đồ họa mặt phẳng (Sketch) và cấu trúc lại toàn bộ ma trận số đo Spec Grid.
    """
    gemini_key = get_secure_gemini_key()
    if not gemini_key: 
        return {
            "success": False, 
            "error": "CRITICAL CONFIGURATION ERROR: GEMINI_API_KEY environment variable is uninitialized."
        }
    
    # ✨ ĐÃ SỬA TRIỆT ĐỂ LỖI CHỈ MỤC: Lấy phần tử index 0 của mảng rsplit trước khi ép hàm .strip()
    if '.' in file_name:
        fallback_style = file_name.rsplit('.', 1)[0].strip()
    else:
        fallback_style = file_name.strip()

    try:
        # Trích xuất dữ liệu cấu trúc trang để định vị không gian tài liệu
        info = pdfinfo_from_bytes(file_bytes)
        total_pages = int(info.get("Pages", 1))
        contents_payload = []
        sketch_base64 = ""

        # Chu trình quét cắt trang tự động (Rasterization)
        for p_num in range(1, total_pages + 1):
            try:
                images = convert_from_bytes(file_bytes, dpi=160, first_page=p_num, last_page=p_num)
                if images:
                    # ✨ ĐÃ SỬA LỖI LIST OBJECT: Trích xuất phần tử ảnh đầu tiên [0] từ thư viện pdf2image
                    img = images[0].convert("RGB") 
                    img_buffer = io.BytesIO()
                    img.save(img_buffer, format="JPEG", quality=95)
                    contents_payload.append(types.Part.from_bytes(data=img_buffer.getvalue(), mime_type='image/jpeg'))
                    
                    # Trích xuất trang đầu tiên làm sơ đồ thiết kế cơ sở (Technical Sketch)
                    if p_num == 1 and not sketch_base64:
                        if img.width > 450: 
                            img = img.resize((450, int(img.height * (450 / img.width))))
                        bk_buf = io.BytesIO()
                        img.save(bk_buf, format="JPEG", quality=85)
                        sketch_base64 = base64.b64encode(bk_buf.getvalue()).decode("utf-8")
            except Exception: 
                pass

        if not contents_payload: 
            return {
                "success": False, 
                "error": "DATA CORRUPTION DETECTED: Unable to extract image buffers from target PDF matrix."
            }

        # Hệ thống chỉ thị AI chuyên ngành dệt may toàn cầu (Strict Garment Spec Prompt)
        user_prompt = """
        You are an elite Garment Technical Auditor and QA/QC Data Engineer at PPJ Group.
        Your task is to analyze the attached images from the technical pack (Techpack) PDF and extract data with absolute precision.
        
        CRITICAL OPERATIONAL INSTRUCTIONS:
        1. Identify the primary specification chart/grid containing the Point of Measurements (POM Description) and target values.
        2. Scan the document ROW-BY-ROW from top to bottom. You MUST extract EVERY SINGLE measurement position. Do not drop, truncate, or group any rows.
        3. Isolate the exact data column assigned for the sample 'Base Size' (e.g., Sample Size, M, or the baseline dimensions stated in the chart header).
        
        You must return a valid JSON object strictly conforming to this exact schema (no additional text, markdown, or wrapping):
        {
          "style_number_parsed": "The official product Style ID or Code",
          "buyer": "The official Client/Buyer account name",
          "category": "The specific garment product line or category",
          "base_size_name": "The extracted sample base size used for values",
          "measurements": {
             "Exact POM Name 1": "Value 1 with UOM",
             "Exact POM Name 2": "Value 2 with UOM"
          }
        }
        """
        contents_payload.append(user_prompt)

        # Kích hoạt Core Engine xử lý đa phương thức với tham số chính xác cơ khí
        client = genai.Client(api_key=gemini_key)
        response = client.models.generate_content(
            model='gemini-2.5-flash', 
            contents=contents_payload, 
            config=types.GenerateContentConfig(
                response_mime_type="application/json", 
                temperature=0.0
            )
        )
        
        # Đồng bộ hóa cấu trúc dữ liệu JSON phản hồi
        parsed_data = json.loads(response.text.strip())
        parsed_data["sketch_image"] = sketch_base64
        
        if not parsed_data.get("style_number_parsed"):
            parsed_data["style_number_parsed"] = fallback_style
            
        return {"success": True, "data": parsed_data}
        
    except Exception as e: 
        return {
            "success": False, 
            "error": f"SYSTEM EXECUTION EXCEPTION: Critical pipeline breakdown during AI processing. Details: {str(e)}"
        }
# =============================================================================
# PHASE 5: USER INTERFACE STRUCTURE & AUTOMATION FACTORY 
# =============================================================================
with st.sidebar:
    st.markdown("""
        <div class="sidebar-brand-container">
            <div class="sidebar-brand-title">PPJ GROUP</div>
            <div class="sidebar-brand-subtitle">TECHPACK MANAGEMENT CORE AI</div>
        </div>
    """, unsafe_allow_html=True)
    
    st.markdown("<p style='font-size:11px; font-weight:700; color:#64748B; margin: 15px 0 5px 5px; letter-spacing:0.5px;'>🏭 AUTOMATION FACTORY</p>", unsafe_allow_html=True)
    menu_selection = st.radio(
        label="Chức năng hệ thống",
        options=["📊 upload Techpack ", "🔄 Pattern Spec Comparison", "🧵 BOM & Consumption Matrix"],
        label_visibility="collapsed"
    )
    st.markdown("---")
    st.success("DATABASE ACCESS: SECURED")
    st.info("ANALYTICS ENGINE: COMPLY")

if "processed_styles" not in st.session_state:
    st.session_state["processed_styles"] = {}

# -----------------------------------------------------------------------------
# CHỨC NĂNG 1: QUÉT TỰ ĐỘNG BẰNG AI VÀ LƯU HÀNG LOẠT (BULK SAVE MULTI-BATCH)
# -----------------------------------------------------------------------------
if menu_selection == "📊 Quét Techpack Document":
    st.markdown('<div class="component-title-box">📊 MULTI-BATCH GARMENT SPECIFICATION MATRIX</div>', unsafe_allow_html=True)
    
    st.markdown("""<div class="card-container"><div class="card-section-header">📥 INGESTION ENGINE</div>
    <p style="color: #64748B; font-size:13px; margin:0 0 15px 0;">Hệ thống tự động cắt trang, khử nhiễu đồ họa phẳng và gọi API mạng nơ-ron tích hợp để bóc tách thông số hàng loạt.</p></div>""", unsafe_allow_html=True)
    uploaded_files = st.file_uploader("Upload Techpack PDF", type=["pdf"], accept_multiple_files=True, label_visibility="collapsed")
    
    if uploaded_files:
        files_to_render = []
        for file in uploaded_files:
            if file.name not in st.session_state["processed_styles"]:
                with st.spinner(f"Core AI đang bóc tách mô hình {file.name}..."):
                    res = process_single_pdf_batch(file.getvalue(), file.name)
                    if res["success"]: 
                        st.session_state["processed_styles"][file.name] = res["data"]
                    else: 
                        st.error(f"FAIL ENGINE [{file.name}]: {res['error']}")
            if file.name in st.session_state["processed_styles"]:
                files_to_render.append(file.name)

        if files_to_render:
            if st.button("💾 SAVE ALL PROCESSED MATRIX TO SUPABASE MASTER DB", key="bulk_save_all_btn", type="primary", use_container_width=True):
                success_count = 0
                with st.spinner("Đang đồng bộ cổng dữ liệu nhị phân hàng loạt lên Supabase Cloud..."):
                    for f_name in files_to_render:
                        style_data = st.session_state["processed_styles"][f_name]
                        if save_to_supabase_techpack_table(style_data): 
                            success_count += 1
                st.success(f"🎉 PATTERN DATA PIPELINE: Đã ghi nhận và lưu trữ thành công {success_count}/{len(files_to_render)} mã hàng vào Database!")
            st.markdown("---")

            cols = st.columns(2)
            for idx, f_name in enumerate(files_to_render):
                col_target = cols[idx % 2]
                data = st.session_state["processed_styles"][f_name]
                with col_target:
                    st.markdown(f"""<div class="card-container"><div class="tech-card-header">{data.get('style_number_parsed')}</div>
                        <div class="metric-grid-box"><div><p class="metric-label">BUYER</p><p class="metric-value">{data.get('buyer')}</p></div>
                        <div><p class="metric-label">PRODUCT LINE</p><p class="metric-value">{data.get('category')}</p></div>
                        <div><p class="metric-label">BASE SIZE</p><p class="metric-value">{data.get('base_size_name')}</p></div></div></div>""", unsafe_allow_html=True)
                    
                    sub_col1, sub_col2 = st.columns([1.2, 0.8])
                    with sub_col1:
                        st.markdown("<p style='font-weight:700; font-size:12px; color:#1E293B;'>📋 SPECIFICATION DATA GRID</p>", unsafe_allow_html=True)
                        table_html = '<div class="data-table-container"><table class="industrial-table"><thead><tr><th>Point of Measurement</th><th>Target Spec</th></tr></thead><tbody>'
                        for k, v in data.get("measurements", {}).items():
                            table_html += f"<tr><td>{k}</td><td>{v}</td></tr>"
                        st.markdown(table_html + "</tbody></table></div>", unsafe_allow_html=True)
                    with sub_col2:
                        st.markdown("<p style='font-weight:700; font-size:12px; color:#1E293B;'>📐 GARMENT FLAT SKETCH</p>", unsafe_allow_html=True)
                        if data.get("sketch_image"): 
                            st.image(base64.b64decode(data["sketch_image"]), use_column_width=True)
                    st.markdown("<br><hr style='border-color:#E2E8F0;'><br>", unsafe_allow_html=True)
    else:
        st.markdown('<div class="idle-alert-box">⚠️ INITIALIZATION SYSTEM IDLE: Hiện tại chưa có tệp dữ liệu Techpack nào được nạp vào hệ thống để AI khởi chạy mô hình.</div>', unsafe_allow_html=True)
# -----------------------------------------------------------------------------
# CHỨC NĂNG 2: ĐỐI CHIẾU SO SÁNH HAI MÃ RẬP KHÁC NHAU (PATTERN SPEC COMPARISON)
# -----------------------------------------------------------------------------
elif menu_selection == "🔄 Pattern Spec Comparison":
    st.markdown('<div class="component-title-box">🔄 DIFFERENTIAL GEOMETRY & DELTA SPEC EVALUATOR</div>', unsafe_allow_html=True)
    
    st.markdown("""<div class="card-container"><div class="card-section-header">🔍 CONFIGURATION SELECTION</div>
    <p style="color: #64748B; font-size:13px; margin:0 0 15px 0;">Tải lên hai tệp bản vẽ kỹ thuật dệt may độc lập để tiến hành lập luận so sánh và tính toán toán học các khoảng chênh lệch rập mẫu.</p></div>""", unsafe_allow_html=True)
    
    sc1, sc2 = st.columns(2)
    with sc1: file1 = st.file_uploader("Chọn file mẫu Techpack Gốc (File A)", type=["pdf"], key="f1")
    with sc2: file2 = st.file_uploader("Chọn file mẫu Techpack Sửa đổi (File B)", type=["pdf"], key="f2")
    
    if file1 and file2:
        if file1.name not in st.session_state["processed_styles"]:
            res1 = process_single_pdf_batch(file1.getvalue(), file1.name)
            if res1["success"]: st.session_state["processed_styles"][file1.name] = res1["data"]
        if file2.name not in st.session_state["processed_styles"]:
            res2 = process_single_pdf_batch(file2.getvalue(), file2.name)
            if res2["success"]: st.session_state["processed_styles"][file2.name] = res2["data"]
            
        d1 = st.session_state["processed_styles"].get(file1.name)
        d2 = st.session_state["processed_styles"].get(file2.name)
        
        if d1 and d2:
            st.markdown(f"""
                <div style="background-color: #FFFFFF; border-left: 5px solid #3B82F6; padding: 12px 20px; border-radius: 4px 12px 12px 4px; margin-bottom: 20px; box-shadow: 0 2px 5px rgba(0,0,0,0.02);">
                    <h5 style="margin:0; color:#1E3A8A; font-weight:700; font-size:16px;">⚙️ ĐANG ĐỐI CHIẾU MA TRẬN PHÁT TRIỂN MẪU</h5>
                    <p style="margin:4px 0 0 0; font-size:13px; color:#64748B;">
                        <b>Mẫu Gốc A:</b> {d1['style_number_parsed']} [Size: {d1.get('base_size_name','N/A')}] 
                        &nbsp;|&nbsp; 
                        <b>Mẫu Sửa B:</b> {d2['style_number_parsed']} [Size: {d2.get('base_size_name','N/A')}]
                    </p>
                </div>
            """, unsafe_allow_html=True)
            
            def clean_garment_fraction(v_str):
                if not v_str or str(v_str).strip().upper() in ["N/A", "N/A INCH", ""]: return 0.0
                try:
                    s = str(v_str).replace("INCH", "").strip()
                    if " " in s:
                        parts = s.split()
                        whole = float(parts[0])
                        frac = parts[1].split('/')
                        return whole + (float(frac[0]) / float(frac[1]))
                    elif "/" in s:
                        frac = s.split('/')
                        return float(frac[0]) / float(frac[1])
                    return float(s)
                except:
                    nums = re.findall(r"[-+]?\d*\.\d+|\d+", str(v_str))
                    return float(nums[0]) if nums else 0.0

            size_a = d1.get("base_size_name", "BASE").strip()
            size_b = d2.get("base_size_name", "BASE").strip()
            col_title_a = f"Mẫu A ({d1['style_number_parsed']}) [{size_a}]"
            col_title_b = f"Mẫu B ({d2['style_number_parsed']}) [{size_b}]"
            all_poms = set(list(d1["measurements"].keys()) + list(d2["measurements"].keys()))
            
            table_body_html = ""
            compare_rows_for_df = []
            
            for pom in sorted(all_poms):
                val1 = d1["measurements"].get(pom, "N/A")
                val2 = d2["measurements"].get(pom, "N/A")
                num1 = clean_garment_fraction(val1)
                num2 = clean_garment_fraction(val2)
                
                delta = round(num2 - num1, 3) if val1 != "N/A" and val2 != "N/A" else 0.0
                compare_rows_for_df.append({"Vị trí đo (POM)": pom, col_title_a: val1, col_title_b: val2, "Sai lệch (Delta)": delta})
                
                if delta > 0:
                    delta_style = "background-color:rgba(16,185,129,0.15); color:#166534; font-weight:700; padding:2px 8px; border-radius:4px; font-size:12px; border:1px solid #BBF7D0;"
                    delta_text = f"+{delta}"
                elif delta < 0:
                    delta_style = "background-color:rgba(239,68,68,0.15); color:#991B1B; font-weight:700; padding:2px 8px; border-radius:4px; font-size:12px; border:1px solid #FECACA;"
                    delta_text = f"{delta}"
                else:
                    delta_style = "color:#64748B; font-size:12px;"
                    delta_text = "0.00"
                
                table_body_html += f"""<tr style="background-color: #FFFFFF;">
                    <td style="padding: 10px 14px; border-bottom: 1px solid #E2E8F0; font-weight: 600; color: #1E293B; font-size: 13px;">{pom}</td>
                    <td style="padding: 10px 14px; border-bottom: 1px solid #E2E8F0; color: #334155; font-size: 13px;">{val1}</td>
                    <td style="padding: 10px 14px; border-bottom: 1px solid #E2E8F0; color: #334155; font-size: 13px;">{val2}</td>
                    <td style="padding: 10px 14px; border-bottom: 1px solid #E2E8F0; text-align: center;"><span style="{delta_style}">{delta_text}</span></td>
                </tr>"""
            
            full_table_render = f"""
            <div style="max-height: 460px; overflow-y: auto; border: 1px solid #CBD5E1; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.02); margin-top: 15px;">
                <table style="width: 100%; border-collapse: collapse; text-align: left; font-family: sans-serif;">
                    <thead>
                        <tr style="background: linear-gradient(90deg, #1E3A8A 0%, #2563EB 100%);">
                            <th style="color: #FFFFFF; font-weight: 600; padding: 14px 16px; font-size: 13px; position: sticky; top: 0; z-index: 10;">Vị trí đo (POM Description)</th>
                            <th style="color: #FFFFFF; font-weight: 600; padding: 14px 16px; font-size: 13px; position: sticky; top: 0; z-index: 10;">{col_title_a}</th>
                            <th style="color: #FFFFFF; font-weight: 600; padding: 14px 16px; font-size: 13px; position: sticky; top: 0; z-index: 10;">{col_title_b}</th>
                            <th style="color: #FFFFFF; font-weight: 600; padding: 14px 16px; font-size: 13px; text-align: center; width: 150px; position: sticky; top: 0; z-index: 10;">Sai lệch (Delta)</th>
                        </tr>
                    </thead>
                    <tbody>
                        {table_body_html}
                    </tbody>
                </table>
            </div>
            """
            st.markdown(full_table_render, unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)
            
            df_compare = pd.DataFrame(compare_rows_for_df)
            towrite = io.BytesIO()
            with pd.ExcelWriter(towrite, engine='xlsxwriter') as writer: 
                df_compare.to_excel(writer, index=False, sheet_name='Spec_Report')
                workbook  = writer.book
                worksheet = writer.sheets['Spec_Report']
                header_format = workbook.add_format({'bold':True,'text_wrap':True,'fg_color':'#1E3A8A','font_color':'white','border':1,'align':'center','valign':'vcenter'})
                center_format = workbook.add_format({'align':'center','valign':'vcenter','border':1})
                left_format = workbook.add_format({'align':'left','valign':'vcenter','border':1})
                
                for col_num, column_title in enumerate(df_compare.columns):
                    worksheet.write(0, col_num, column_title, header_format)
                for i, col in enumerate(df_compare.columns):
                    max_len = max(df_compare[col].astype(str).map(len).max(), len(col)) + 4
                    if i == 0: worksheet.set_column(i, i, max_len, left_format)
                    else: worksheet.set_column(i, i, max_len, center_format)
            towrite.seek(0)
            
            st.download_button(
                label="📥 EXPORT PRODUCTION DELTA SHEET (EXCEL)", 
                data=towrite, 
                file_name=f"PPJ_Delta_Spec_Comparison.xlsx", 
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
# =============================================================================
# CHỨC NĂNG 3: TRỢ LÝ ĐỊNH MỨC VẢI (ISOLATED DATA PIPELINE & INTENT LAB - PHẦN 6A)
# =============================================================================
elif menu_selection == "🧵 BOM & Consumption Matrix":
    st.markdown('<div class="component-title-box">🧵 INTELLIGENT BOM & CONSUMPTION MATRIX ENGINE</div>', unsafe_allow_html=True)
    
    # Thiết lập giao diện điều khiển hàng ngang cố định chống tràn trang
    control_col1, control_col2 = st.columns([3.3, 0.7])
    with control_col1:
        st.markdown("<p style='font-weight:700; font-size:12px; color:#1E293B;'>📁 INGEST NEW STYLE REPRINTS (PDF/IMAGE)</p>", unsafe_allow_html=True)
        chat_file = st.file_uploader("Upload Techpack file", type=["pdf", "jpg", "jpeg", "png"], key="chat_uploader", label_visibility="collapsed")
        if chat_file: 
            st.success(f"📎 DATASTREAM PIPELINE BOUND: Tiếp nhận thành công file {chat_file.name}")
            
    with control_col2:
        st.markdown("<p style='font-weight:700; font-size:12px; color:#1E293B;'>🧹 RESET CORE</p>", unsafe_allow_html=True)
        if st.button("🗑️ PURGE CHAT CACHE", use_container_width=True, type="secondary"):
            import time
            if "chat_history" in st.session_state: 
                del st.session_state["chat_history"]
            st.success("🔄 MEMORY CLEARED")
            time.sleep(0.5)
            st.rerun()

    st.markdown("---")
    
    # Khởi tạo mảng lưu lịch sử hội thoại chuẩn hóa
    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = [
            {"role": "assistant", "type": "text", "content": "Welcome to PPJ Textile Visual R&D Engine. Hãy tải lên sơ đồ rập/Techpack mã mới và ra lệnh. Tôi sẽ tìm chính xác mã tương đồng, xuất ảnh Sketch và tính định mức vải/phụ liệu theo đúng yêu cầu, không trả lời lan man."}
        ]
        
    for msg in st.session_state["chat_history"]:
        with st.chat_message(msg["role"]): 
            st.write(msg["content"])
            if msg.get("type") == "visual" and msg.get("image_url"):
                st.image(msg["image_url"], caption=f"Bản vẽ Sketch lịch sử đối chiếu mã {msg.get('style_title')}", width=220)
    # LUỒNG XỬ LÝ ĐÓNG BĂNG DỮ LIỆU CHỐNG LẪN LỘN MÃ HÀNG GIAO TIẾP ĐỘNG (PHẦN 6B - PHẦN 1)
    if user_query := st.chat_input("Nhập yêu cầu phân tích định mức vải và đối soát sai lệch..."):
        st.session_state["chat_history"].append({"role": "user", "type": "text", "content": user_query})
        with st.chat_message("user"): 
            st.write(user_query)
            
        with st.chat_message("assistant"):
            with st.spinner("Hệ thống AI R&D Engine đang đối soát tri thức nền xưởng may..."):
                gemini_key = get_secure_gemini_key()
                if not gemini_key: 
                    ans = "CRITICAL SERVER BREAKDOWN: AI API Token is missing."
                else:
                    try:
                        client = genai.Client(api_key=gemini_key)
                        contents_payload = []
                        new_style_id_detected = "UNKNOWN_STYLE"
                        new_style_raw_text = ""
                        
                        if chat_file:
                            file_bytes = chat_file.getvalue()
                            img_payload = []
                            if chat_file.name.lower().endswith('.pdf'):
                                info_chat = pdfinfo_from_bytes(file_bytes)
                                total_chat_pages = int(info_chat.get("Pages", 1))
                                chat_images = convert_from_bytes(file_bytes, dpi=140, first_page=1, last_page=total_chat_pages)
                                for page_img in chat_images:
                                    img_buf = io.BytesIO()
                                    page_img.convert("RGB").save(img_buf, format="JPEG")
                                    img_payload.append(types.Part.from_bytes(data=img_buf.getvalue(), mime_type='image/jpeg'))
                                    if not contents_payload:
                                        contents_payload.append(types.Part.from_bytes(data=img_buf.getvalue(), mime_type='image/jpeg'))
                            else:
                                img_payload.append(types.Part.from_bytes(data=file_bytes, mime_type='image/jpeg'))
                                contents_payload.append(types.Part.from_bytes(data=file_bytes, mime_type='image/jpeg'))
                            
                            extraction_prompt = """
                            Analyze ALL the attached technical pack images page by page.
                            1. Locate and extract the genuine 'Style ID' / 'Style Number' / 'Mã hàng'.
                            2. Extract ALL specification charts and raw Bill of Materials (BOM) fields.
                            Return a valid JSON with this exact schema:
                            {"detected_style_id": "Text of Style ID", "all_specs_text": "Complete specifications and raw BOM data text from all pages"}
                            """
                            img_payload.append(extraction_prompt)
                            
                            for ext_attempt in range(3):
                                try:
                                    extraction_res = client.models.generate_content(model='gemini-2.5-flash', contents=img_payload, config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.0))
                                    parsed_meta = json.loads(extraction_res.text.strip())
                                    new_style_id_detected = parsed_meta.get("detected_style_id", "UNKNOWN_STYLE").strip()
                                    new_style_raw_text = parsed_meta.get("all_specs_text", "")
                                    break
                                except Exception:
                                    import time
                                    time.sleep(2 * (ext_attempt + 1))
                        
                        if new_style_id_detected == "UNKNOWN_STYLE" or not chat_file:
                            found_keywords = re.findall(r'[A-Za-z0-9]+[-–][A-Za-z0-9]+|[A-Za-z0-9]{4,}', user_query)
                            if found_keywords: new_style_id_detected = found_keywords

                        # TRUY VẤN ĐỐI SOÁT CHÍNH XÁC KHO THỊ GIÁC TỪ DATABASE
                        headers = {"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}"}
                        url = f"{SB_URL.rstrip('/')}/rest/v1/thong_so_techpack?StyleName=ilike.*{new_style_id_detected}*&select=StyleName,Buyer,Category,BaseSize,DetailedMeasurements,SketchURL&limit=3"
                        res = requests.get(url, headers=headers, timeout=15)
                        db_results = res.json() if 200 <= res.status_code <= 299 else []
                        
                        db_context = f"\n\n[ DỮ LIỆU THỰC TẾ TRONG HỆ THỐNG KHO CHO MÃ HÀNG: {new_style_id_detected} ]:\n"
                        detected_image_url_to_render = ""
                        detected_style_title_to_render = ""
                        
                        if db_results:
                            for item in db_results:
                                if item.get("SketchURL") and not detected_image_url_to_render:
                                    detected_image_url_to_render = item.get("SketchURL")
                                    detected_style_title_to_render = item.get("StyleName")
                                db_context += f"- Mã gốc đối chiếu tìm thấy: {item.get('StyleName')}\n  + Khách hàng: {item.get('Buyer')}\n  + Ma trận thông số kích thước kích cỡ: {json.dumps(item.get('DetailedMeasurements', {}), ensure_ascii=False)}\n  + Liên kết ảnh vẽ phác thảo phẳng (SketchURL): {item.get('SketchURL', '')}\n"
                        else:
                            fallback_key = new_style_id_detected.split('-')[-1] if '-' in str(new_style_id_detected) else str(new_style_id_detected)[:4]
                            backup_res = get_historical_fabric_consumption_from_db(search_keyword=fallback_key)
                            if backup_res:
                                db_context += f"⚠️ Không có dữ liệu rập trực tiếp cho mã {new_style_id_detected}. Dưới đây là định mức vải thực tế của các mã hàng anh em trong kho sản xuất:\n"
                                for b_item in backup_res[:4]:
                                    db_context += f"- Mã sản xuất: {b_item.get('style_name')}\n  + Loại vải: {b_item.get('article_name')}\n  + Định mức tiêu thụ vải thực tế trong kho: {b_item.get('consumption_value')} {b_item.get('uom')}\n  + Ghi chú hao hụt rập: {b_item.get('notes')}\n"
                            else:
                                db_context += "❌ HỆ THỐNG PHÁT HIỆN: Mã hàng này hoàn toàn mới, chưa từng tồn tại dữ liệu hay hình ảnh phác thảo tương đồng trong Master DB.\n"
                        # CHỈ THỊ NGHIÊM NGẶT: HỎI GÌ ĐÁP NẤY - TUYỆT ĐỐI KHÔNG TRẢ LỜI LAN MAN TRÀN LAN (PHẦN 6B - PHẦN 2)
                        system_instruction = (
                            "You are the Lead R&D Expert and Garment Auditor at PPJ Group.\n"
                            "STRICT OPERATIONAL FOCUS (HỎI GÌ ĐÁP NẤY):\n"
                            "1. Nếu người dùng yêu cầu 'Tìm mã tương đồng' hoặc đối chiếu số đo: Bạn chỉ được liệt kê mã cũ tương đồng nhất từ dữ liệu kho bên dưới, "
                            "so sánh sai lệch kích thước hình học (Delta Spec). TUYỆT ĐỐI KHÔNG xuất bảng nguyên phụ liệu BOM, không lan man sang chủ đề khác.\n"
                            "2. Nếu người dùng gõ từ khóa liên quan đến 'BOM', 'Phụ liệu', 'Phụ kiện': Lúc này bạn mới được quyền lập bảng bóc tách chi tiết nguyên phụ liệu.\n"
                            "3. BẢO TOÀN SỐ LIỆU ĐỊNH MỨC VẢI: Khi phân tích định mức vải tiêu thụ, bạn phải căn cứ 100% vào cột số liệu định mức gốc ('consumption_value') và ghi chú rập thực tế từ dữ liệu kho được cung cấp. "
                            "TUYỆT ĐỐI KHÔNG tự ý giả định hay đưa con số 'hao hụt cắt xưởng 15%' vô lý vào báo cáo nếu dữ liệu gốc không yêu cầu.\n\n"
                            "Trình bày ngắn gọn, tập trung thẳng vào câu hỏi, dùng tiếng Việt chuyên ngành dệt may kỹ thuật."
                        )
                        
                        full_prompt = f"{system_instruction}\n\nYêu cầu của kỹ sư: {user_query}\n\n[Thông số file mới tải lên]:\n{new_style_raw_text if new_style_raw_text else 'Không đính kèm file'}\n{db_context}"
                        contents_payload.append(full_prompt)
                        
                        ans = ""
                        for attempt in range(5):
                            try:
                                response = client.models.generate_content(model='gemini-2.5-flash', contents=contents_payload)
                                ans = response.text
                                break
                            except Exception as e:
                                if "503" in str(e) or "UNAVAILABLE" in str(e) or "429" in str(e) or "EXHAUSTED" in str(e):
                                    if attempt < 4:
                                        import time
                                        time.sleep(3 * (attempt + 1))
                                        continue
                                raise e
                                
                        st.write(ans)
                        st.session_state["chat_history"].append({"role": "assistant", "type": "text", "content": ans})
                        
                        # Chỉ tự động bắn ảnh ra màn hình khi tìm thấy ảnh lưu trữ thực tế trong kho Supabase
                        if detected_image_url_to_render:
                            st.image(detected_image_url_to_render, caption=f"Bản vẽ Sketch lịch sử đối chiếu của Mã hàng {detected_style_title_to_render}", width=220)
                            st.session_state["chat_history"].append({"role": "assistant", "type": "visual", "content": f"[Hệ thống đã kết xuất hình ảnh tham chiếu mã {detected_style_title_to_render}]", "image_url": detected_image_url_to_render, "style_title": detected_style_title_to_render})
                            
                    except Exception as e: 
                        ans = f"⚠️ Máy chủ AI đang xử lý ma trận số liệu lớn. Vui lòng thử lại sau vài giây! Chi tiết: {str(e)}"
                        st.write(ans)
                        st.session_state["chat_history"].append({"role": "assistant", "type": "text", "content": ans})
