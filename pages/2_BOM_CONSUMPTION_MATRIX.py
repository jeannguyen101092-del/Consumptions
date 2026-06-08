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
    ✨ SỬA LỖI TOÁN TỬ GỐC: Đổi từ toán tử dạng Regex (.*) sang toán tử chuẩn PostgREST (%) 
    để bắt trúng mã 1P001451 trong kho lưu trữ của bạn.
    """
    try:
        headers = {
            "apikey": SB_KEY, 
            "Authorization": f"Bearer {SB_KEY}"
        }
        url = f"{SB_URL.rstrip('/')}/rest/v1/thong_so_techpack"
        
        query_params = {
            "select": "StyleName,Buyer,Category,BaseSize,DetailedMeasurements,SketchURL",
            "limit": "500"
        }
        
        if style_name_keyword:
            clean_kw = str(style_name_keyword).strip()
            # Đổi từ ilike.*{clean_kw}* sang ilike.%{clean_kw}% chuẩn cú pháp Supabase PostgREST
            query_params["StyleName"] = f"ilike.%{clean_kw}%"
            
        response = requests.get(url, headers=headers, params=query_params, timeout=15)
        return response.json() if response.status_code == 200 else []
    except Exception:
        return []




def process_single_pdf_batch(file_bytes, file_name):
    """
    Hàm bóc tách dữ liệu kỹ thuật từ một file PDF độc lập sử dụng Gemini Vision API.
    ✨ ĐÃ ĐỒNG BỘ MỤC 3: Ép AI tự dò tìm trang chứa hình vẽ thiết kế sơ đồ phẳng (Sketch) 
    để lưu kho chuẩn xác, giúp mắt thần AI ở Mục 3 đối chiếu hình ảnh chính xác 100%.
    """
    try:
        gemini_key = get_secure_gemini_key()
        if not gemini_key:
            return {"success": False, "error": "API Key cho Gemini đang bị thiếu trong Secrets."}
            
        client = genai.Client(api_key=gemini_key)
        
        # Chuyển đổi PDF sang hình ảnh JPEG để mô hình Vision quét dữ liệu diện rộng
        info = pdfinfo_from_bytes(file_bytes)
        total_pages = int(info.get("Pages", 1))
        images = convert_from_bytes(file_bytes, dpi=140, first_page=1, last_page=total_pages)
        
        contents_payload = []
        # Duyệt và đóng gói toàn bộ các trang ảnh kèm số thứ tự index để AI tự đếm trang
        for idx, img in enumerate(images):
            img_buf = io.BytesIO()
            img.convert("RGB").save(img_buf, format="JPEG")
            # Đính kèm ảnh kèm nhãn trang để AI chỉ định chính xác trang chứa hình vẽ
            contents_payload.append(f"--- IMAGE OF PAGE INDEX {idx} ---")
            contents_payload.append(types.Part.from_bytes(data=img_buf.getvalue(), mime_type='image/jpeg'))
            
        # PROMPT CẢI TIẾN: Ép AI chỉ định số trang chứa hình vẽ phác thảo (Technical Sketch)
        prompt = """
        You are an expert garment technical auditor. Analyze this Techpack image page by page.
        1. Extract the genuine 'Style ID' / 'Style Number'.
        2. Identify the 'Buyer' or Brand name.
        3. Identify the Product Line 'Category' (e.g., Blouses, Jacket, Pants).
        4. Detect the 'Base Size' utilized.
        5. Extract all points of measurement (POM) and their target specifications into a flat key-value dictionary.
        6. CRITICAL VISION TASK: Look at all pages and identify the exact 'PAGE INDEX' that contains the main technical sketch drawing (hình vẽ phẳng mô tả kết cấu quần/áo, chi tiết túi hộp, cạp). Ignore text-only layout pages or cover pages.
        
        Return a strict JSON format with this exact schema:
        {
          "style_number_parsed": "Mã hàng",
          "buyer": "Tên khách hàng",
          "category": "Phân loại sản phẩm",
          "base_size_name": "Size gốc",
          "measurements": {"Vị trí đo 1": "Thông số 1", "Vị trí đo 2": "Thông số 2"},
          "sketch_page_index_detected": 0
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
        
        # ✨ THUẬT TOÁN ĐỒNG BỘ THỊ GIÁC MỚI: Bốc đúng trang chứa ảnh Sketch do AI chỉ định
        sketch_index = int(parsed_data.get("sketch_page_index_detected", 0))
        
        # Kiểm tra an toàn chỉ mục trang để tránh lỗi crash List Index Out Of Range
        if sketch_index >= len(images) or sketch_index < 0:
            sketch_index = 0 # Trả về trang đầu làm dự phòng nếu AI nhận diện vượt ngưỡng
            
        if images:
            thumb_buf = io.BytesIO()
            # Trích xuất chính xác trang chứa sơ đồ phẳng công nghệ thực tế
            images[sketch_index].convert("RGB").save(thumb_buf, format="JPEG")
            # Ghi đè chuỗi Base64 sạch để đẩy thẳng vào trường dữ liệu lưu kho
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
# =============================================================================
# ĐOẠN 1: TỰ ĐỘNG BÓC TÁCH FILE MỚI UPLOAD VÀ TRUY VẤN MASTER DB THEO SỐ ĐO THẬT
# =============================================================================
import re
import io
import json
import requests
import streamlit as st
from urllib.parse import quote
from google import genai
from google.genai import types
try:
    from pdf2image import convert_from_bytes, pdfinfo_from_bytes
except ImportError:
    pass

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
                try:
                    client = genai.Client(api_key=gemini_key)
                    new_style_id_detected = "UNKNOWN_STYLE"
                    new_style_raw_text = ""
                    new_style_category_detected = ""
                    new_style_fabric_detected = "UNKNOWN_FABRIC"
                    new_style_measurements_dict = {}
                    img_payload = [] 
                    target_new_sketch_bytes = None 
                    
                    if 'chat_file' in locals() or 'chat_file' in globals():
                        has_file = chat_file is not None
                    elif 'uploaded_file' in st.session_state:
                        chat_file = st.session_state['uploaded_file']
                        has_file = chat_file is not None
                    else:
                        has_file = False
                        
                    if has_file:
                        file_bytes = chat_file.getvalue()
                        if chat_file.name.lower().endswith('.pdf'):
                            info_chat = pdfinfo_from_bytes(file_bytes)
                            total_chat_pages = int(info_chat.get("Pages", 1))
                            chat_images = convert_from_bytes(file_bytes, dpi=140, first_page=1, last_page=total_chat_pages)
                            for idx, page_img in enumerate(chat_images):
                                img_buf = io.BytesIO()
                                page_img.convert("RGB").save(img_buf, format="JPEG")
                                img_payload.append(types.Part.from_bytes(data=img_buf.getvalue(), mime_type='image/jpeg'))
                        else:
                            img_payload.append(types.Part.from_bytes(data=file_bytes, mime_type='image/jpeg'))
                        
                        extraction_prompt = """
                        Analyze ALL the attached technical pack images page by page.
                        Return a valid JSON with this exact schema:
                        {"detected_style_id": "Pure code only", "category": "Pants or Jacket", "fabric_code": "Pure fabric code", "measurements": {"Vị trí đo": "Thông số"}, "sketch_page_index_detected": 0}
                        """
                        extraction_payload = list(img_payload)
                        extraction_payload.append(extraction_prompt)
                        
                        for ext_attempt in range(3):
                            try:
                                extraction_res = client.models.generate_content(
                                    model='gemini-2.5-flash', 
                                    contents=extraction_payload, 
                                    config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.0)
                                )
                                parsed_meta = json.loads(extraction_res.text.strip())
                                new_style_id_detected = parsed_meta.get("detected_style_id", "UNKNOWN_STYLE").strip()
                                new_style_category_detected = parsed_meta.get("category", "").strip()
                                new_style_fabric_detected = parsed_meta.get("fabric_code", "UNKNOWN_FABRIC").strip()
                                new_style_measurements_dict = parsed_meta.get("measurements", {})
                                new_style_raw_text = json.dumps(new_style_measurements_dict, ensure_ascii=False)
                                
                                detected_idx = int(parsed_meta.get("sketch_page_index_detected", 0))
                                if chat_file.name.lower().endswith('.pdf') and 0 <= detected_idx < len(chat_images):
                                    b_buf = io.BytesIO()
                                    chat_images[detected_idx].convert("RGB").save(b_buf, format="JPEG")
                                    target_new_sketch_bytes = b_buf.getvalue()
                                else:
                                    target_new_sketch_bytes = file_bytes
                                break
                            except Exception:
                                import time
                                time.sleep(2 * (ext_attempt + 1))
                    
                    clean_text_upper = str(user_query).strip().upper()
                    is_searching_fabric = any(word in clean_text_upper for word in ["CODE VẢI", "CODE VAI", "MÃ VẢI", "MA VAI", "LOẠI VẢI", "LOAI VAI", "TÌM VẢI", "TIM VAI"])
                    
                    # BẢO LƯU CẤU TRÚC CŨ: Quét tìm đích danh mã chữ viết liền (Ví dụ: MR1705, CR2045)
                    codes_found = re.findall(r'\b[A-Z]*\d+[A-Z0-9]*\b|\b[A-Z0-9]+-\d+[A-Z0-9-]*\b', clean_text_upper)
                    
                    if codes_found:
                        clean_query = codes_found[0] # Lấy mã chữ chuẩn đầu tiên được tìm thấy
                    else:
                        pattern_remove = r"\b(TÌM|TIM|KIỂM TRA|KIEM TRA|XEM|CHECK|CHO TOI|XIN|MÃ HÀNG|MA HANG|MÃ|MA|VẢI|VAI|ĐỊNH MỨC|DINH MUC|CODE|TRÍCH XUẤT|TRICH XUAT|HÌNH ẢNH|HINH ANH|HÌNH|HINH|ẢNH|ANH|TÍNH|TINH|THÔNG TIN|THONG TIN|NÀY|NAY|TƯƠNG ĐỒNG|TUONG DONG)\b"
                        clean_query = re.sub(pattern_remove, "", clean_text_upper).strip()
                    
                    if has_file:
                        if is_searching_fabric and new_style_fabric_detected != "UNKNOWN_FABRIC":
                            dynamic_keyword = str(new_style_fabric_detected).strip()
                        elif new_style_id_detected != "UNKNOWN_STYLE" and not clean_query:
                            dynamic_keyword = str(new_style_id_detected).strip()
                        else:
                            dynamic_keyword = clean_query if clean_query else str(new_style_id_detected).strip()
                    else:
                        dynamic_keyword = clean_query

                    dynamic_keyword = re.sub(r"[\[\]'\"*?%#&]", "", dynamic_keyword).strip()
                    if not dynamic_keyword:
                        dynamic_keyword = "UNKNOWN"

                    db_results = get_techpack_spec_from_db(style_name_keyword=dynamic_keyword)
                    backup_res = get_historical_fabric_consumption_from_db(search_keyword=dynamic_keyword)

                    if has_file and target_new_sketch_bytes:
                        st.image(target_new_sketch_bytes, caption=f"🖼️ Bản vẽ phẳng công nghệ trích xuất từ FILE MỚI UPLOAD ({new_style_id_detected})", use_container_width=True)


# =============================================================================
# ĐOẠN 2 - PHẦN A: BẢN THÔNG MẠCH TUYỆT ĐỐI KHÔNG PHÂN BIỆT HOA THƯỜNG CHO KHO
# =============================================================================
                    base_sb_url = SB_URL.rstrip('/')
                    headers = {"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}"}
                    SUPABASE_PROJECT_URL = "https://supabase.co"

                    is_similarity_requested = True
                    fabric_records = []
                    techpack_records = []
                    matched_style_name = None

                    if is_similarity_requested:
                        short_keyword = dynamic_keyword.strip().upper()
                        
                        # BƯỚC 1: LUÔN ƯU TIÊN SỬ DỤNG CODE CHỮ NẾU NGƯỜI DÙNG CÓ NHẬP HOẶC AI BÓC ĐƯỢC TỪ FILE
                        if short_keyword and short_keyword != "UNKNOWN":
                            matched_style_name = short_keyword
                        
                        # BƯỚC 2: RẼ NHÁNH DỰ PHÒNG - NẾU KHÔNG CÓ CODE CHỮ MÀ CÓ FILE TẢI LÊN -> KÍCH HOẠT QUÉT ẢNH KHO
                        elif has_file and target_new_sketch_bytes:
                            with st.spinner("Đang chạy đối chiếu thị giác ảnh Sketch với kho Storage..."):
                                # Danh sách các mã ảnh có sẵn trong hệ thống kho của bạn để đối so sánh
                                known_sketches = ["1P001451", "MR1705", "P01-495544", "P08-492175", "P09-488051", "R06-494148", "R09-491542"]
                                
                                vision_payload = [
                                    types.Part.from_bytes(data=target_new_sketch_bytes, mime_type='image/jpeg'),
                                    f"Identify which Style Code from this list is the most visually similar to the attached sketch: {json.dumps(known_sketches)}. Return JSON: {{\"most_similar_style\": \"Code or null\"}}"
                                ]
                                try:
                                    v_res = client.models.generate_content(
                                        model='gemini-2.5-flash', contents=vision_payload,
                                        config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.0)
                                    )
                                    matched_style_name = json.loads(v_res.text.strip()).get("most_similar_style")
                                except Exception:
                                    matched_style_name = None

                        # 3. TIẾN HÀNH GỌI DATABASE THEO MÃ ĐÃ XÁC ĐỊNH ĐƯỢC (TỪ CODE CHỮ HOẶC TỪ ẢNH)
                        if matched_style_name and matched_style_name != "null":
                            if is_searching_fabric:
                                url_san_pham = f"{base_sb_url}/rest/v1/san_pham?article_name=ilike.*{quote(matched_style_name)}*&select=*"
                            else:
                                url_san_pham = f"{base_sb_url}/rest/v1/san_pham?style_name=ilike.*{quote(matched_style_name)}*&select=*"
                            
                            url_techpack = f"{base_sb_url}/rest/v1/thong_so_techpack?StyleName=ilike.*{quote(matched_style_name)}*&select=*"

                            try:
                                res_sp = requests.get(url_san_pham, headers=headers)
                                if res_sp.status_code == 200:
                                    fabric_records = res_sp.json()
                            except Exception as e:
                                st.warning(f"Lỗi kết nối bảng san_pham: {e}")

                            try:
                                res_tp = requests.get(url_techpack, headers=headers)
                                if res_tp.status_code == 200:
                                    techpack_records = res_tp.json()
                            except Exception as e:
                                st.warning(f"Lỗi kết nối bảng thong_so_techpack: {e}")





# =============================================================================
# ĐOẠN 3: HIỂN THỊ TRỰC TIẾP HÌNH ẢNH SKETCH ĐỐI CHỨNG VÀ AI TÍNH TOÁN ĐỊNH MỨC
# =============================================================================
                    db_sketch_url = None
                    db_measurements_raw = {}
                    current_style_name = ""
                    
                    if techpack_records and len(techpack_records) > 0:
                        first_record = techpack_records if isinstance(techpack_records, list) else techpack_records
                        if isinstance(first_record, dict):
                            current_style_name = first_record.get("StyleName", "")
                            db_sketch_url = first_record.get("SketchURL")
                            db_measurements_raw = first_record.get("DetailedMeasurements", {})
                        
                        if db_sketch_url and str(db_sketch_url).startswith("http"):
                            st.image(db_sketch_url, caption=f"🖼️ Ảnh Sketch đối chứng mã hàng trong kho: {current_style_name}", use_container_width=True)
                        elif current_style_name:
                            constructed_url = f"{SUPABASE_PROJECT_URL}/storage/v1/object/public/kho_anh/{current_style_name}.jpg"
                            st.image(constructed_url, caption=f"🖼️ Ảnh Sketch đối chứng mã hàng trong kho: {current_style_name}", use_container_width=True)
                    else:
                        if dynamic_keyword and dynamic_keyword != "UNKNOWN":
                            constructed_url = f"{SUPABASE_PROJECT_URL}/storage/v1/object/public/kho_anh/{dynamic_keyword}.jpg"
                            st.image(constructed_url, caption=f"🖼️ Ảnh Sketch tìm theo mã: {dynamic_keyword}", use_container_width=True)

                    # Bóc tách thông số Khổ vải và Độ co từ ô chat người dùng
                    fabric_width_input = re.search(r'(?:KHỔ|KHO)\s*(\d+(?:\.\d+)?)', clean_text_upper)
                    shrinkage_input = re.search(r'(?:CO|CO RÚT|CO RUT)\s*(\d+(?:\.\d+)?)\s*%', clean_text_upper)
                    
                    user_width = fabric_width_input.group(1) if fabric_width_input else "1.5m (Standard)"
                    user_shrinkage = shrinkage_input.group(1) if shrinkage_input else "0%"

                    # Hiển thị trực quan dữ liệu thô dạng bảng
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown("**📋 Thông tin định mức vải (Bảng san_pham):**")
                        if fabric_records:
                            formatted_fabric = [{
                                "Mã hàng": r.get("style_name"),
                                "Mã vải (Article)": r.get("article_name"),
                                "Loại vật tư": r.get("consumption_type"),
                                "Khổ vải": r.get("material_size"),
                                "Đơn vị": r.get("uom")
                            } for r in fabric_records]
                            st.dataframe(formatted_fabric, use_container_width=True)
                        else:
                            st.info("Không có dữ liệu định mức lịch sử trùng khớp.")
                            
                    with col2:
                        st.markdown("**📏 Thông số hình học gốc (Bảng thong_so_techpack):**")
                        if db_measurements_raw and isinstance(db_measurements_raw, dict):
                            formatted_measurements = [
                                {"Vị trí đo (POM)": key, "Thông số kỹ thuật": value} 
                                for key, value in db_measurements_raw.items()
                            ]
                            st.dataframe(formatted_measurements, use_container_width=True)
                        else:
                            st.info("Không tìm thấy thông số kỹ thuật tương ứng.")

                    # BƯỚC AI PHÂN TÍCH TÍNH TOÁN ĐỊNH MỨC VẢI THEO CÁC BIẾN SỐ
                    st.markdown("### 📊 Kết quả phân tích và tính toán Định mức Vải")
                    
                    calculation_prompt = f"""
                    You are an expert Apparel Costing Engineer. 
                    - Specified Width: {user_width}
                    - Specified Shrinkage: {user_shrinkage}%
                    - Uploaded Techpack Specs: {new_style_raw_text}
                    - Matched Style from Search: {matched_style_name}
                    - Historical Matched Fabric Yield: {json.dumps(fabric_records, ensure_ascii=False)}
                    - Historical Matched Measurements: {json.dumps(db_measurements_raw, ensure_ascii=False)}
                    
                    Tasks:
                    1. If a matched style exists, compare specs, pull historical consumption as baseline, and calculate final consumption incorporating the specified width and shrinkage.
                    2. If no matched style exists, perform direct independent geometric calculations based entirely on the current style's POM to determine consumption.
                    3. Output step-by-step completely in Vietnamese with zero fluff text.
                    """
                    
                    with st.spinner("AI đang tính toán sơ đồ định mức vải dệt may..."):
                        final_payload = list(img_payload) if has_file else []
                        final_payload.append(calculation_prompt)
                        
                        analysis_res = client.models.generate_content(
                            model='gemini-2.5-flash', 
                            contents=final_payload,
                        )
                        st.markdown(analysis_res.text)
                        st.session_state["chat_history"].append({"role": "assistant", "type": "text", "content": analysis_res.text})
                        
                except Exception as master_err:
                    st.error(f"Hệ thống lõi gặp lỗi trong quá trình xử lý: {str(master_err)}")
