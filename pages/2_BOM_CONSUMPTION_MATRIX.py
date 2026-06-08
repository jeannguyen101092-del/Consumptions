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
SB_KEY = st.secrets.get("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImV3cXFvZHNmdmx2bnJ6c3lsYXd5Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzUxMTkyOTAsImV4cCI6MjA5MDY5NTI5MH0.BWPxOsyswBT5CLrZgluRC1F2x5EpU06oexUFyakGhyc")

def get_secure_gemini_key():
    """Hàm bảo mật trích xuất Token API chìa khóa phân tích từ bộ Secrets"""
    if "GEMINI_API_KEY" in st.secrets:
        return st.secrets["GEMINI_API_KEY"].strip()
    return None

def save_to_supabase_techpack_table(payload_data):
    """
    Hàm xử lý đồng bộ và nạp Master DB bảng thong_so_techpack kết hợp đẩy ảnh lên Storage kho_anh.
    ✨ ĐA VÁ LỖI: Đồng bộ hóa chính xác 100% tên cột dữ liệu dệt may (StyleName, Buyer, Category, BaseSize).
    """
    try:
        style_name_db = payload_data.get("style_number_parsed", "").strip()
        if not style_name_db: 
            style_name_db = "UNKNOWN_STYLE"
            
        sketch_b64 = payload_data.get("sketch_image", "")
        public_image_url = ""

        # Xử lý đẩy hình ảnh rập/thiết kế phẳng lên Storage
        if sketch_b64:
            try:
                image_data = base64.b64decode(sketch_b64)
                storage_headers = {
                    "apikey": SB_KEY, 
                    "Authorization": f"Bearer {SB_KEY}",
                    "Content-Type": "image/jpeg", 
                    "x-upsert": "true"
                }
                clean_filename = re.sub(r'[^a-zA-Z0-9_-]', '', style_name_db)
                storage_url = f"{SB_URL.rstrip('/')}/storage/v1/object/kho_anh/{clean_filename}.jpg"
                upload_res = requests.post(storage_url, headers=storage_headers, data=image_data, timeout=20)
                if 200 <= upload_res.status_code <= 299:
                    public_image_url = f"{SB_URL.rstrip('/')}/storage/v1/object/public/kho_anh/{clean_filename}.jpg"
            except Exception: 
                pass

        # Cấu hình Headers kết nối database REST API quyền service_role cao cấp
        headers = {
            "apikey": SB_KEY, 
            "Authorization": f"Bearer {SB_KEY}",
            "Content-Type": "application/json", 
            "Prefer": "resolution=merge-duplicates"
        }
        insert_url = f"{SB_URL.rstrip('/')}/rest/v1/thong_so_techpack"
        
        # Đồng bộ hóa cấu trúc dữ liệu cặp Key-Value bảng thông số POM dệt may
        raw_measurements = payload_data.get("measurements", {})
        clean_dict = {str(k): str(v) for k, v in dict(raw_measurements).items()}

        # Khớp chính xác tên cột phân biệt chữ HOA - thường trên bảng Supabase của bạn
        db_payload = {
            "StyleName": style_name_db,
            "Buyer": payload_data.get("buyer"),
            "Category": payload_data.get("category"),
            "BaseSize": payload_data.get("base_size_name"),
            "DetailedMeasurements": clean_dict,  # Gửi dưới dạng Dict nguyên bản để REST tự định dạng JSON
            "SketchURL": public_image_url
        }
        
        response = requests.post(insert_url, headers=headers, json=[db_payload], timeout=15)
        
        # Nếu Supabase báo lỗi cấu trúc, ghi nhận nhật ký lỗi ra màn hình terminal để xử lý
        if response.status_code < 200 or response.status_code > 299:
            st.sidebar.error(f"Lỗi Supabase ({response.status_code}): {response.text}")
            return False
            
        return True
    except Exception as e: 
        st.sidebar.error(f"Lỗi hệ thống: {str(e)}")
        return False


def get_historical_fabric_consumption_from_db(search_keyword=None):
    """
    Hàm tra cứu kho dữ liệu san_pham lịch sử nâng cao.
    ✨ ĐÃ SỬA: Tìm kiếm mờ thông minh, tự động quét cả dạng viết liền, dấu cách và dấu gạch ngang!
    """
    try:
        headers = {
            "apikey": SB_KEY, 
            "Authorization": f"Bearer {SB_KEY}"
        }
        url = f"{SB_URL.rstrip('/')}/rest/v1/san_pham"
        
        query_params = {
            "select": "style_name,article_name,consumption_type,material_size,uom,consumption_value,notes",
            "limit": 1000
        }
        
        if search_keyword:
            # Làm sạch từ khóa thô ban đầu
            kw_raw = str(search_keyword).strip().upper()
            # Tự động tạo ra các biến thể tìm kiếm khác nhau để đối soát chéo
            kw_clean = kw_raw.replace("-", "").replace(" ", "") # Dạng viết liền: NP430, SJ8902
            
            # Trích xuất phần chữ và số để tạo dạng gạch ngang và khoảng trắng dự phòng
            letters = "".join(re.findall(r'[A-Z]+', kw_clean))
            digits = "".join(re.findall(r'\d+', kw_clean))
            
            # Xây dựng màng lọc ma trận or của Supabase PostgREST
            if letters and digits:
                or_filter = f"(style_name.ilike.*{letters}*{digits}*,article_name.ilike.*{letters}*{digits}*)"
            else:
                or_filter = f"(style_name.ilike.*{kw_raw}*,article_name.ilike.*{kw_raw}*)"
                
            query_params["or"] = or_filter
        
        response = requests.get(url, headers=headers, params=query_params, timeout=15)
        return response.json() if response.status_code == 200 else []
    except Exception: 
        return []


def get_techpack_spec_from_db(style_name_keyword=None):
    """
    Hàm cho phép AI tự động tra cứu thông số từ bảng thong_so_techpack.
    ✨ ĐÃ SỬA LỖI ĐÚNG TOÁN TỬ: Chuyển đổi bộ lọc về định dạng PostgREST chính thống (StyleName=ilike.*keyword*)
    """
    try:
        headers = {
            "apikey": SB_KEY, 
            "Authorization": f"Bearer {SB_KEY}"
        }
        url = f"{SB_URL.rstrip('/')}/rest/v1/thong_so_techpack"
        
        # Cấu hình trường select chính xác (giữ nguyên SketchURL viết hoa)
        query_params = {
            "select": "StyleName,Buyer,Category,BaseSize,DetailedMeasurements,SketchURL",
            "limit": 500
        }
        
        # SỬA TẠI ĐÂY: Thay vì gán trực tiếp tên cột, PostgREST yêu cầu định dạng lọc thông qua giá trị tham số
        if style_name_keyword:
            clean_kw = str(style_name_keyword).strip()
            # Cú pháp chuẩn: tên_cột=toán_tử.giá_trị
            query_params["StyleName"] = f"ilike.*{clean_kw}*"
            
        response = requests.get(url, headers=headers, params=query_params, timeout=15)
        return response.json() if response.status_code == 200 else []
    except Exception:
        return []



def process_single_pdf_batch(file_bytes, file_name):
    """
    Hàm bóc tách dữ liệu kỹ thuật từ một file PDF độc lập sử dụng Gemini Vision API.
    ✨ ĐÃ SỬA LỖI TRÍCH XUẤT ẢNH TRANG ĐẦU TIÊN [0] CHỐNG LỖI CÚ PHÁP LIST INDEX
    """
    try:
        gemini_key = get_secure_gemini_key()
        if not gemini_key:
            return {"success": False, "error": "API Key cho Gemini đang bị thiếu trong Secrets."}
            
        client = genai.Client(api_key=gemini_key)
        
        # Chuyển đổi PDF sang hình ảnh JPEG để mô hình Vision quét dữ liệu
        info = pdfinfo_from_bytes(file_bytes)
        total_pages = int(info.get("Pages", 1))
        images = convert_from_bytes(file_bytes, dpi=140, first_page=1, last_page=total_pages)
        
        contents_payload = []
        for img in images:
            img_buf = io.BytesIO()
            img.convert("RGB").save(img_buf, format="JPEG")
            contents_payload.append(types.Part.from_bytes(data=img_buf.getvalue(), mime_type='image/jpeg'))
            
        # Prompt cấu trúc ép AI trả về định dạng JSON chuẩn dệt may
        prompt = """
        You are an expert garment technical auditor. Analyze this Techpack image page by page.
        1. Extract the genuine 'Style ID' / 'Style Number'.
        2. Identify the 'Buyer' or Brand name.
        3. Identify the Product Line 'Category' (e.g., Blouses, Jacket, Pants).
        4. Detect the 'Base Size' utilized.
        5. Extract all points of measurement (POM) and their target specifications into a flat key-value dictionary.
        
        Return a strict JSON format with this exact schema:
        {
          "style_number_parsed": "Mã hàng",
          "buyer": "Tên khách hàng",
          "category": "Phân loại sản phẩm",
          "base_size_name": "Size gốc",
          "measurements": {"Vị trí đo 1": "Thông số 1", "Vị trí đo 2": "Thông số 2"},
          "sketch_image": ""
        }
        """
        contents_payload.append(prompt)
        
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=contents_payload,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.0
            )
        )
        
        parsed_data = json.loads(response.text.strip())
        
        # ✨ ĐÃ SỬA LỖI: Trích xuất phần tử index [0] của danh sách để lấy ảnh trang đầu tiên
        if images:
            thumb_buf = io.BytesIO()
            images[0].convert("RGB").save(thumb_buf, format="JPEG")
            parsed_data["sketch_image"] = base64.b64encode(thumb_buf.getvalue()).decode("utf-8")
            
        return {"success": True, "data": parsed_data}
    except Exception as e:
        return {"success": False, "error": str(e)}


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
    
    # ĐÃ ĐỒNG BỘ: Đảm bảo khớp hoàn toàn các nhãn chức năng
    menu_selection = st.radio(
        label="Chức năng hệ thống",
        options=["📊 Upload Techpack", "🔄 Pattern Spec Comparison", "🧵 BOM & Consumption Matrix"],
        label_visibility="collapsed"
    )
    st.markdown("---")
    st.success("DATABASE ACCESS: SECURED")
    st.info("ANALYTICS ENGINE: COMPLY")

if "processed_styles" not in st.session_state:
    st.session_state["processed_styles"] = {}


# CHỨC NĂNG 1: QUÉT TỰ ĐỘNG BẰNG AI VÀ LƯU HÀNG LOẠT (BULK SAVE MULTI-BATCH)
# -----------------------------------------------------------------------------
if menu_selection == "📊 Upload Techpack":
    st.markdown('<div class="component-title-box">📊 MULTI-BATCH GARMENT SPECIFICATION MATRIX</div>', unsafe_allow_html=True)
    
    st.markdown("""<div class="card-container"><div class="card-section-header">📥 INGESTION ENGINE</div>
    <p style="color: #64748B; font-size:13px; margin:0 0 15px 0;">Hệ thống tự động cắt trang, khử nhiễu đồ họa phẳng và gọi API mạng nơ-ron tích hợp để bóc tách thông số hàng loạt.</p></div>""", unsafe_allow_html=True)
    
    uploaded_files = st.file_uploader("Upload Techpack PDFs Here", type=["pdf"], accept_multiple_files=True, label_visibility="collapsed")
    
    if uploaded_files:
        files_to_render = []
        for file in uploaded_files:
            if file.name not in st.session_state["processed_styles"]:
                with st.spinner(f"Core AI đang bóc tách mô hình {file.name}..."):
                    # LƯU Ý: Đảm bảo hàm process_single_pdf_batch đã được định nghĩa trong file code của bạn
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
                        table_html += "</tbody></table></div>"
                        st.markdown(table_html, unsafe_allow_html=True)
                    with sub_col2:
                        st.markdown("<p style='font-weight:700; font-size:12px; color:#1E293B;'>📐 GARMENT FLAT SKETCH</p>", unsafe_allow_html=True)
                        if data.get("sketch_image"): 
                            st.image(base64.b64decode(data["sketch_image"]), use_container_width=True)
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
            
            # ĐÃ VÁ LỖI CỤT: Hoàn thiện logic định dạng cột và sinh tệp Excel tự động
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
                    max_len = max(df_compare[col].astype(str).map(len).max(), len(col)) + 3
                    if col == "Vị trí đo (POM)":
                        worksheet.set_column(i, i, max_len, left_format)
                    else:
                        worksheet.set_column(i, i, max_len, center_format)
                        
            st.download_button(
                label="📥 DOWNLOAD COMPARISON EXCEL REPORT",
                data=towrite.getvalue(),
                file_name=f"Spec_Comparison_{d1['style_number_parsed']}_vs_{d2['style_number_parsed']}.xlsx",
                mime="application/vnd.ms-excel",
                use_container_width=True
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
def thuc_thi_pipeline_rd(user_query, chat_file, SB_URL, SB_KEY, client, types, json, requests, pdfinfo_from_bytes, convert_from_bytes, io, re, st):
    try:
        contents_payload = []
        new_style_id_detected = "UNKNOWN_STYLE"
        new_style_raw_text = ""
        if chat_file:
            file_bytes = chat_file.getvalue()
            img_payload = []
            if chat_file.name.lower().endswith('.pdf'):
                try:
                    info_chat = pdfinfo_from_bytes(file_bytes)
                    total_chat_pages = int(info_chat.get("Pages", 1))
                    max_pages_to_scan = min(total_chat_pages, 3)
                    chat_images = convert_from_bytes(file_bytes, dpi=100, first_page=1, last_page=max_pages_to_scan)
                    for page_img in chat_images:
                        img_buf = io.BytesIO()
                        page_img.convert("RGB").save(img_buf, format="JPEG", quality=85)
                        img_payload.append(types.Part.from_bytes(data=img_buf.getvalue(), mime_type='image/jpeg'))
                except Exception:
                    st.warning("Không thể tự động phân tách trang PDF. Đang quét text...")
            else:
                img_payload.append(types.Part.from_bytes(data=file_bytes, mime_type='image/jpeg'))
            if img_payload:
                extraction_prompt = "Analyze the techpack. Return JSON: {\"detected_style_id\": \"Pure code\", \"all_specs_text\": \"BOM details\"}"
                extraction_payload = list(img_payload)
                extraction_payload.append(extraction_prompt)
                for ext_attempt in range(2):
                    try:
                        extraction_res = client.models.generate_content(model='gemini-2.5-flash', contents=extraction_payload, config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.0))
                        parsed_meta = json.loads(extraction_res.text.strip())
                        new_style_id_detected = parsed_meta.get("detected_style_id", "UNKNOWN_STYLE").strip()
                        new_style_raw_text = parsed_meta.get("all_specs_text", "")
                        break
                    except Exception:
                        import time
                        time.sleep(1)
        clean_text_upper = str(user_query).strip().upper()
        stop_words = ["TÌM", "CODE", "VẢI", "MÃ", "HÀNG", "ĐỊNH MỨC", "CHO", "KIỂM TRA", "XEM", "THÔNG", "SỐ"]
        query_words = clean_text_upper.split()
        filtered_words = [w for w in query_words if w not in stop_words]
        raw_keyword = " ".join(filtered_words) if filtered_words else clean_text_upper
        if chat_file and new_style_id_detected != "UNKNOWN_STYLE" and not filtered_words:
            dynamic_keyword = str(new_style_id_detected).strip()
        else:
            dynamic_keyword = raw_keyword
        dynamic_keyword = re.sub(r"[\[\]'\"*?%#&]", "", dynamic_keyword).strip()
        if not dynamic_keyword:
            dynamic_keyword = "UNKNOWN"
        headers = {"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}"}
        url_san_pham = f"{SB_URL.rstrip('/')}/rest/v1/san_pham?or=(style_name.ilike.*{dynamic_keyword}*,article_name.ilike.*{dynamic_keyword}*,notes.ilike.*{dynamic_keyword}*)&select=style_name,article_name,consumption_type,material_size,uom,consumption_value,notes&limit=1000"
        res_sp = requests.get(url_san_pham, headers=headers, timeout=5)
        backup_res = res_sp.json() if 200 <= res_sp.status_code <= 299 else []
        tp_search_keyword = dynamic_keyword
        if backup_res and not chat_file:
            for b_item in backup_res:
                if b_item.get('style_name'):
                    tp_search_keyword = str(b_item.get('style_name')).strip()
                    break
        url_techpack = f"{SB_URL.rstrip('/')}/rest/v1/thong_so_techpack?StyleName=ilike.*{tp_search_keyword}*&select=StyleName,Buyer,Category,BaseSize,DetailedMeasurements,SketchURL&limit=3"
        res_tp = requests.get(url_techpack, headers=headers, timeout=5)
        db_results = res_tp.json() if 200 <= res_tp.status_code <= 299 else []
        db_context = f"\n\n[ KHO DỮ LIỆU MASTER DB PHÒNG R&D ]: \n"
        detected_image_url_to_render = ""
        detected_style_title_to_render = ""
        if db_results:
            target_item = db_results if isinstance(db_results, list) and len(db_results) > 0 else db_results
            if isinstance(target_item, dict):
                detected_style_title_to_render = target_item.get("StyleName", tp_search_keyword)
                if target_item.get("SketchURL"):
                    detected_image_url_to_render = target_item.get("SketchURL")
                db_context += f"- Hồ sơ rập tìm thấy: {target_item.get('StyleName')} | Khách hàng: {target_item.get('Buyer')} | Số đo: {json.dumps(target_item.get('DetailedMeasurements', {}), ensure_ascii=False)}\n"
        else:
            db_context += f"- Không tìm thấy thông số trực tiếp cho từ khóa '{tp_search_keyword}' trong thong_so_techpack.\n"
        if backup_res:
            exact_matched_items = []
            for b_item in backup_res:
                s_n = str(b_item.get('style_name', '')).strip().upper()
                a_n = str(b_item.get('article_name', '')).strip().upper()
                n_s = str(b_item.get('notes', '')).strip().upper()
                if dynamic_keyword in s_n or dynamic_keyword in a_n or dynamic_keyword in n_s:
                    exact_matched_items.append(b_item)
            if exact_matched_items:
                db_context += f"\n- KẾT QUẢ TRA CỨU ĐỊNH MỨC CHO TỪ KHÓA '{dynamic_keyword}':\n"
                values = [float(i.get('consumption_value')) for i in exact_matched_items if i.get('consumption_value') is not None]
                for item in exact_matched_items:
                    db_context += f"  + Mã hàng: {item.get('style_name')} | Mã vật tư: {item.get('article_name')} | Định mức: {item.get('consumption_value')} {item.get('uom')}\n"
                if values:
                    avg_c = sum(values) / len(values)
                    db_context += f"  => Định mức trung bình thực tế (Avg Cons): {avg_c:.3f} (Gồm 5% hao hụt sản xuất đề xuất: {avg_c * 1.05:.3f})\n"
        if new_style_raw_text:
            db_context += f"\n- DỮ LIỆU THÔ TỪ FILE TECHPACK:\n{new_style_raw_text}\n"
        if not detected_image_url_to_render and tp_search_keyword and tp_search_keyword != "UNKNOWN":
            detected_style_title_to_render = tp_search_keyword
            detected_image_url_to_render = f"{SB_URL.rstrip('/')}/storage/v1/object/public/kho_anh/{tp_search_keyword}.jpg"
        final_prompt = f"Bạn là trợ lý R&D dệt may. Hãy trả lời TRỰC DIỆN, NGẮN GỌN vào câu hỏi: '{user_query}'. Quy tắc: 1. Hỏi gì đáp nấy, không chào hỏi dong dài. 2. Nếu tra thông số mã hàng (Ví dụ: MR1705), hiển thị bảng DetailedMeasurements thành định dạng Markdown, kèm định mức lịch sử. 3. Nếu tra mã vải (Ví dụ: SJ-8902), chỉ hiển thị thông tin vải và định mức tiêu thụ liên quan của mã vải đó. Kho dữ liệu: {db_context}"
        final_res = client.models.generate_content(model='gemini-2.5-flash', contents=[final_prompt])
        st.markdown(final_res.text)
        if detected_image_url_to_render:
            st.image(detected_image_url_to_render, caption=f"Hình ảnh Sketch: {detected_style_title_to_render}", use_container_width=True)
    except Exception as e:
        st.error(f"Lỗi hệ thống: {str(e)}")
        # VẼ LẠI TOÀN BỘ KHUNG HIỂN THỊ LỊCH SỬ CHAT TRÊN GIAO DIỆN
    for msg in st.session_state["chat_history"]:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])
            if msg.get("type") == "visual" and msg.get("image_url"):
                st.image(msg["image_url"], caption="Hình vẽ Thiết kế kỹ thuật", width=220)

    # KHỞI CHẠY LẠI Ô CHAT INPUT VÀ LUỒNG XỬ LÝ ĐỘC LẬP
   
        st.session_state["chat_history"].append({"role": "user", "type": "text", "content": user_query})
        with st.chat_message("user"): 
            st.write(user_query)
            
        with st.chat_message("assistant"):
            with st.spinner("Hệ thống AI R&D Engine đang kết nối kho tri thức nền dệt may..."):
                gemini_key = get_secure_gemini_key()
                if not gemini_key: 
                    st.error("CRITICAL SERVER BREAKDOWN: AI API Token is missing.")
                else:
                    client_gen = genai.Client(api_key=gemini_key)
                    # Triệu gọi hàm xử lý R&D độc lập để phản hồi "Hỏi gì đáp nấy"
                    thuc_thi_pipeline_rd(user_query, chat_file, SB_URL, SB_KEY, client_gen, types, json, requests, pdfinfo_from_bytes, convert_from_bytes, io, re, st)
# =============================================================================
# KHÔI PHỤC THANH CHAT INPUT GỐC - ĐƯA RA SÁT LỀ TRÁI NGOÀI CÙNG
# =============================================================================
if "chat_history" not in st.session_state:
    st.session_state["chat_history"] = []

for msg in st.session_state["chat_history"]:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])
        if msg.get("type") == "visual" and msg.get("image_url"):
            st.image(msg["image_url"], caption="Hình vẽ kỹ thuật", width=220)

if user_query := st.chat_input("Nhập yêu cầu phân tích định mức vải và đối soát sai lệch..."):
    st.session_state["chat_history"].append({"role": "user", "type": "text", "content": user_query})
    with st.chat_message("user"): 
        st.write(user_query)
        
    with st.chat_message("assistant"):
        with st.spinner("Hệ thống AI R&D Engine đang kết nối kho tri thức nền dệt may..."):
            gemini_key = get_secure_gemini_key()
            if not gemini_key: 
                st.error("CRITICAL SERVER BREAKDOWN: AI API Token is missing.")
            else:
                client_gen = genai.Client(api_key=gemini_key)
                thuc_thi_pipeline_rd(user_query, chat_file, SB_URL, SB_KEY, client_gen, types, json, requests, pdfinfo_from_bytes, convert_from_bytes, io, re, st)
