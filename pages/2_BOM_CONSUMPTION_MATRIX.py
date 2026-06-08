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
    ✨ ĐÃ SỬA: Sửa cấu trúc bóc tách mảng Embedding của Google GenAI SDK mới và chuẩn hóa cấu trúc mảng Vector.
    """
    try:
        style_name_db = payload_data.get("style_number_parsed", "").strip()
        if not style_name_db: 
            style_name_db = "UNKNOWN_STYLE"
            
        sketch_b64 = payload_data.get("sketch_image", "")
        public_image_url = ""
        image_data = None

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
            except Exception as e: 
                print(f"[STORAGE UPLOAD ERROR]: {str(e)}")

        # ⚡ TỰ ĐỘNG SỐ HÓA SKETCH THÀNH MẢNG SỐ THỰC CHUẨN ĐỂ ĐỐI SOÁT
        new_sketch_vector_str = None
        if image_data:
            gemini_key = get_secure_gemini_key()
            if gemini_key:
                try:
                    client = genai.Client(api_key=gemini_key)
                    embedding_res = client.models.embed_content(
                        model='multimodal-embedding-001',
                        contents=types.Part.from_bytes(data=image_data, mime_type='image/jpeg')
                    )
                    
                    # SỬA LỖI TẠI ĐÂY: Trích xuất chính xác cấu trúc dữ liệu .embeddings từ SDK mới
                    if hasattr(embedding_res, 'embeddings') and embedding_res.embeddings:
                        # Lấy phần tử mảng đầu tiên và bóc tách danh sách tọa độ vector (.values)
                        vector_values = embedding_res.embeddings[0].values
                        
                        # CHUẨN HÓA ĐẦU RA: Định dạng thành chuỗi mảng Postgres Vector chuẩn format [x,y,z...] 
                        # giúp Supabase hiểu được dù cột lưu trữ cấu hình ở dạng TEXT hay mảng VECTOR chuyên dụng.
                        new_sketch_vector_str = "[" + ",".join(str(float(v)) for v in vector_values) + "]"
                except Exception as ai_err:
                    print(f"[AI EMBEDDING ERROR]: {str(ai_err)}")
                    new_sketch_vector_str = None

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

        # Khớp chính xác tên cột và bổ sung cột 'sketch_vector' lưu chuỗi số đối soát
        db_payload = {
            "StyleName": style_name_db,
            "Buyer": payload_data.get("buyer"),
            "Category": payload_data.get("category"),
            "BaseSize": payload_data.get("base_size_name"),
            "DetailedMeasurements": clean_dict,
            "SketchURL": public_image_url,
            "sketch_vector": new_sketch_vector_str
        }
        
        response = requests.post(insert_url, headers=headers, json=[db_payload], timeout=15)
        
        if response.status_code < 200 or response.status_code > 299:
            st.sidebar.error(f"Lỗi Supabase ({response.status_code}): {response.text}")
            return False
            
        return True
    except Exception as e:
        st.sidebar.error(f"Lỗi xử lý hệ thống: {str(e)}")
        return False


def get_historical_fabric_consumption_from_db(search_keyword=None):
    """
    Hàm tra cứu kho dữ liệu san_pham lịch sử nâng cao.
    ✨ ĐÃ BẢO TRÌ: Giữ nguyên cơ chế lọc đa chiều PostgREST bằng ký tự dại diện (*).
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
        
        if search_keyword and str(search_keyword).strip().upper() != "UNKNOWN":
            kw_raw = str(search_keyword).strip().upper()
            kw_clean = kw_raw.replace("-", "").replace(" ", "") 
            
            or_filter = (
                f"style_name.ilike.*{kw_raw}*,"
                f"style_name.ilike.*{kw_clean}*,"
                f"article_name.ilike.*{kw_raw}*,"
                f"article_name.ilike.*{kw_clean}*"
            )
            query_params["or"] = f"({or_filter})"
        
        response = requests.get(url, headers=headers, params=query_params, timeout=15)
        return response.json() if response.status_code == 200 else []
    except Exception: 
        return []


def get_techpack_spec_from_db(style_name_keyword=None):
    """
    Hàm cho phép AI tự động tra cứu thông số từ bảng thong_so_techpack.
    ✨ ĐÃ SỬA: Ép kiểu dữ liệu tham số 'limit' về định dạng số nguyên nguyên bản tránh lỗi PostgREST.
    """
    try:
        headers = {
            "apikey": SB_KEY, 
            "Authorization": f"Bearer {SB_KEY}"
        }
        url = f"{SB_URL.rstrip('/')}/rest/v1/thong_so_techpack"
        
        query_params = {
            "select": "StyleName,Buyer,Category,BaseSize,DetailedMeasurements,SketchURL,sketch_vector",
            "limit": 500  # SỬA LỖI: Chuyển đổi từ chuỗi "500" sang số nguyên 500 chuẩn API
        }
        
        if style_name_keyword and str(style_name_keyword).strip().upper() != "UNKNOWN":
            clean_kw = str(style_name_keyword).strip().upper()
            query_params["StyleName"] = f"ilike.*{clean_kw}*"
            
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
import re
import io
import json
import requests
import streamlit as st
import concurrent.futures
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
                            chat_images = convert_from_bytes(file_bytes, dpi=110, first_page=1, last_page=total_chat_pages)
                            for idx, page_img in enumerate(chat_images):
                                img_buf = io.BytesIO()
                                page_img.convert("RGB").save(img_buf, format="JPEG", quality=85)
                                img_payload.append(types.Part.from_bytes(data=img_buf.getvalue(), mime_type='image/jpeg'))
                        else:
                            img_payload.append(types.Part.from_bytes(data=file_bytes, mime_type='image/jpeg'))
                        
                        extraction_prompt = """
                        Analyze ALL the attached technical pack images page by page.
                        1. Locate the genuine 'Style ID' / 'Style Number' / 'Mã hàng'. Clean it.
                        2. Identify the Product Line 'Category' (e.g., Pants, Jeans, Jacket).
                        3. Extract all points of measurement (POM) into a strict key-value flat dictionary.
                        4. CRITICAL VISION TASK: Find the exact 'PAGE INDEX' (starting from 0) that contains the TECHNICAL BLACK AND WHITE FLAT SKETCH / DRAWING. 
                           DO NOT select pages containing real product photographs, fabrics, or 'Labeled Images' wash denim sheets. Only pick the pure line art design drawing page.
                        
                        Return a valid JSON with this exact schema:
                        {"detected_style_id": "Pure code only", "category": "Pants or Jacket", "fabric_code": "Pure fabric code", "measurements": {"Vị trí đo": "Thông số"}, "sketch_page_index_detected": 0}
                        """
                        extraction_payload = list(img_payload)
                        extraction_payload.append(extraction_prompt)
                        
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
                        except Exception:
                            pass
                    
                    clean_text_upper = str(user_query).strip().upper()
                    is_searching_fabric = any(word in clean_text_upper for word in ["CODE VẢI", "CODE VAI", "MÃ VẢI", "MA VAI", "LOẠI VẢI", "LOAI VAI", "TÌM VẢI", "TIM VAI"])
                    
                    codes_found = re.findall(r'\b[A-Z]*\d+[A-Z0-9]*\b|\b[A-Z0-9]+-\d+[A-Z0-9-]*\b', clean_text_upper)
                    
                    if codes_found:
                        clean_query = codes_found[0] if isinstance(codes_found, list) else codes_found
                    else:
                        pattern_remove = r"\b(TÌM|TIM|KIỂM TRA|KIEM TRA|XEM|CHECK|CHO TOI|XIN|MÃ HÀNG|MA HANG|MÃ|MA|VẢI|VAI|ĐỊNH MỨC|DINH MUC|CODE|TRÍCH XUẤT|TRICH XUAT|HÌNH ẢNH|HINH ANH|HÌNH|HINH|ẢNH|ANH|TÍNH|TINH|THÔNG TIN|THONG TIN|NÀY|NAY|TƯƠNG ĐỒNG|TUONG DONG|VỚI|KHO|KIẾM|VOI|TRONG)\b"
                        clean_query = re.sub(pattern_remove, "", clean_text_upper).strip()
                    
                    if has_file:
                        if is_searching_fabric and new_style_fabric_detected != "UNKNOWN_FABRIC":
                            dynamic_keyword = str(new_style_fabric_detected).strip()
                        elif clean_query and len(clean_query) >= 3 and not any(w in clean_query for w in ["VỚI", "KHO", "TRONG"]):
                            dynamic_keyword = clean_query
                        else:
                            dynamic_keyword = str(new_style_id_detected).strip()
                    else:
                        dynamic_keyword = clean_query if clean_query else "UNKNOWN"

                    dynamic_keyword = re.sub(r"[\[\]'\"*?%#&]", "", dynamic_keyword).strip()
                    
                    # CƠ CHẾ DỰ PHÒNG: Tự bóc tách mã hàng từ tên file nếu câu lệnh của bạn quá ngắn (ví dụ chỉ nhập chữ "tìm mã hàng tương đồng")
                    if has_file and (not dynamic_keyword or len(dynamic_keyword) < 3 or dynamic_keyword == "UNKNOWN_STYLE" or dynamic_keyword == "UNKNOWN"):
                        file_name_upper = chat_file.name.upper()
                        file_code_match = re.search(r'\b[A-Z0-9]{4,12}\b', file_name_upper)
                        if file_code_match:
                            dynamic_keyword = file_code_match.group(0)
                            if new_style_id_detected == "UNKNOWN_STYLE":
                                new_style_id_detected = dynamic_keyword

                    db_results = get_techpack_spec_from_db(style_name_keyword=dynamic_keyword)
                    backup_res = get_historical_fabric_consumption_from_db(search_keyword=dynamic_keyword)

                    if has_file and target_new_sketch_bytes:
                        st.image(target_new_sketch_bytes, caption=f"🖼️ Bản vẽ phẳng công nghệ trích xuất từ FILE MỚI UPLOAD ({new_style_id_detected})", use_container_width=True)


# =============================================================================
# ĐOẠN 2 - PHẦN A: ĐỐI SOÁT VECTOR EMBEDDINGS HOÀN TOÀN BẰNG PYTHON BẮT TRÚNG MÃ
# =============================================================================
                    import numpy as np
                    
                    base_sb_url = SB_URL.rstrip('/')
                    headers = {"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}"}

                    is_similarity_requested = True
                    fabric_records = []
                    techpack_records = []
                    matched_style_name = None

                    if is_similarity_requested:
                        short_keyword = dynamic_keyword.strip().upper()
                        
                        check_url = f"{base_sb_url}/rest/v1/thong_so_techpack?StyleName=ilike.%{quote(short_keyword)}%&select=StyleName"
                        has_in_techpack = False
                        try:
                            res_check = requests.get(check_url, headers=headers, timeout=3)
                            if res_check.status_code == 200:
                                res_json = res_check.json()
                                if len(res_json) > 0:
                                    has_in_techpack = True
                                    # Lấy chính xác StyleName từ bản ghi đầu tiên trả về của database
                                    matched_style_name = res_json[0].get("StyleName") if isinstance(res_json, list) else res_json.get("StyleName")
                        except Exception:
                            has_in_techpack = False

                        if has_in_techpack:
                            matched_style_name = short_keyword
                        elif has_file and target_new_sketch_bytes:
                            with st.spinner("⚡ AI đang số hóa hình học phẳng và chạy thuật toán so khớp thị giác Vector..."):
                                query_vector = None
                                try:
                                    # SỬA LỖI TẠI ĐÂY: text-embedding-004 không nhận định dạng ảnh nhị phân trực tiếp. 
                                    # Sử dụng Gemini tạo chuỗi text mô tả thiết kế phẳng trước khi bóc tách vector.
                                    vision_prompt = "Analyze this technical flat sketch. Describe its silhouette, geometry, and key tailoring features in 3 concise sentences."
                                    vision_res = client.models.generate_content(
                                        model='gemini-2.5-flash',
                                        contents=[types.Part.from_bytes(data=target_new_sketch_bytes, mime_type='image/jpeg'), vision_prompt]
                                    )
                                    visual_description = vision_res.text.strip() if vision_res.text else "unknown denim pattern geometry"

                                    embedding_res = client.models.embed_content(
                                        model='text-embedding-004',
                                        contents=visual_description
                                    )
                                    # SỬA LỖI TẠI ĐÂY: Trích xuất mảng số thực thông qua thuộc tính chuẩn .embeddings của SDK mới
                                    query_vector = np.array(embedding_res.embeddings.values if hasattr(embedding_res.embeddings, 'values') else embedding_res.embeddings[0].values)
                                except Exception:
                                    query_vector = None

                                if query_vector is not None:
                                    url_all_vectors = f"{base_sb_url}/rest/v1/thong_so_techpack?select=StyleName,sketch_vector"
                                    try:
                                        res_all = requests.get(url_all_vectors, headers=headers, timeout=5)
                                        warehouse_data = res_all.json() if res_all.status_code == 200 else []
                                    except Exception:
                                        warehouse_data = []

                                    best_similarity = -1.0
                                    for row in warehouse_data:
                                        v_str = row.get("sketch_vector")
                                        if v_str:
                                            try:
                                                # Giải mã mảng số được lưu trữ dưới dạng chuỗi toán học từ Database
                                                if str(v_str).startswith("["):
                                                    db_vector = np.array(json.loads(v_str))
                                                else:
                                                    db_vector = np.array(json.loads(v_str))
                                                    
                                                dot_product = np.dot(query_vector, db_vector)
                                                norm_query = np.linalg.norm(query_vector)
                                                norm_db = np.linalg.norm(db_vector)
                                                similarity = dot_product / (norm_query * norm_db)
                                                
                                                if similarity > best_similarity and similarity >= 0.70:
                                                    best_similarity = similarity
                                                    matched_style_name = row.get("StyleName")
                                            except Exception:
                                                pass

                        final_search_key = matched_style_name if (matched_style_name and matched_style_name != "null") else short_keyword

                        # ĐỒNG BỘ TỪ KHÓA: Sử dụng final_search_key đồng bộ cho cả hai bảng để bắt trúng dữ liệu liên đới
                        url_san_pham = f"{base_sb_url}/rest/v1/san_pham?or=(style_name.ilike.%{quote(final_search_key)}%,article_name.ilike.%{quote(final_search_key)}%)&select=*"
                        url_techpack = f"{base_sb_url}/rest/v1/thong_so_techpack?StyleName=ilike.%{quote(final_search_key)}%&select=*"

                        def fetch_url(url):
                            try:
                                res = requests.get(url, headers=headers, timeout=5)
                                return res.json() if res.status_code == 200 else []
                            except Exception:
                                return []

                        with concurrent.futures.ThreadPoolExecutor() as executor:
                            future_sp = executor.submit(fetch_url, url_san_pham)
                            future_tp = executor.submit(fetch_url, url_techpack)
                            
                            fabric_records = future_sp.result()
                            techpack_records = future_tp.result()


# =============================================================================
# ĐOẠN 3: KẾT XUẤT HÌNH ẢNH SKETCH, BẢNG THÔNG SỐ VÀ TỰ TÍNH ĐỊNH MỨC ĐỘ CO ĐA CHIỀU
# =============================================================================
                    db_sketch_url = None
                    db_measurements_raw = {}
                    current_style_name = ""
                    SUPABASE_PROJECT_URL = SB_URL.rstrip('/') if 'SB_URL' in locals() else "https://supabase.co" 
                    
                    if techpack_records and len(techpack_records) > 0:
                        # SỬA LỖI LOGIC: Bóc tách chính xác phần tử đầu tiên từ mảng danh sách bản ghi trả về
                        first_record = techpack_records[0] if isinstance(techpack_records, list) else techpack_records
                        if isinstance(first_record, dict):
                            current_style_name = first_record.get("StyleName", "")
                            db_sketch_url = first_record.get("SketchURL")
                            db_measurements_raw = first_record.get("DetailedMeasurements", {})
                            if isinstance(db_measurements_raw, str):
                                try: db_measurements_raw = json.loads(db_measurements_raw)
                                except Exception: pass
                        
                        if db_sketch_url and str(db_sketch_url).startswith("http"):
                            st.image(db_sketch_url, caption=f"🖼️ Ảnh Sketch đối chứng mã hàng trong kho: {current_style_name}", use_container_width=True)
                        elif current_style_name:
                            constructed_url = f"{SUPABASE_PROJECT_URL}/storage/v1/object/public/kho_anh/{current_style_name}.jpg"
                            st.image(constructed_url, caption=f"🖼️ Ảnh Sketch đối chứng mã hàng trong kho: {current_style_name}", use_container_width=True)
                    else:
                        if dynamic_keyword and dynamic_keyword != "UNKNOWN":
                            constructed_url = f"{SUPABASE_PROJECT_URL}/storage/v1/object/public/kho_anh/{dynamic_keyword}.jpg"
                            st.image(constructed_url, caption=f"🖼️ Ảnh Sketch tìm theo mã: {dynamic_keyword}", use_container_width=True)

                    fabric_width_input = re.search(r'(?:KHỔ|KHO)\s*(\d+(?:\.\d+)?)', clean_text_upper)
                    shrink_ngang = re.search(r'(?:NGANG)\s*(\d+(?:\.\d+)?)\s*%', clean_text_upper)
                    shrink_doc = re.search(r'(?:DỌC|DOC)\s*(\d+(?:\.\d+)?)\s*%', clean_text_upper)
                    shrink_general = re.search(r'(?:CO|CO RÚT|CO RUT)\s*(\d+(?:\.\d+)?)\s*%', clean_text_upper)

                    user_width = f"{fabric_width_input.group(1)} INCH" if fabric_width_input else "57 INCH"
                    co_ngang = shrink_ngang.group(1) if shrink_ngang else "0"
                    co_doc = shrink_doc.group(1) if shrink_doc else (shrink_general.group(1) if shrink_general else "0")

                    st.markdown(f"### 📊 Kết quả đối soát dữ liệu mã hàng: **{new_style_id_detected if new_style_id_detected != 'UNKNOWN_STYLE' else final_search_key}**")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown("**📋 Thông tin định mức vải gốc (Bảng san_pham):**")
                        if fabric_records and isinstance(fabric_records, list):
                            formatted_fabric = [{"Mã hàng": r.get("style_name"), "Mã vải (Article)": r.get("article_name"), "Loại vật tư": r.get("consumption_type"), "Khổ vải": r.get("material_size"), "Đơn vị": r.get("uom")} for r in fabric_records if isinstance(r, dict)]
                            st.dataframe(formatted_fabric, use_container_width=True)
                        else:
                            st.info("ℹ️ Không tìm thấy mã tương đồng. Hệ thống tự động kích hoạt tính toán độc lập từ thông số rập Techpack mới.")
                            
                    with col2:
                        st.markdown("**📏 Thông số hình học thực tế (Bảng lưới phẳng chuyên nghiệp):**")
                        display_specs = db_measurements_raw if (db_measurements_raw and len(db_measurements_raw) > 0) else new_style_measurements_dict
                        if display_specs and isinstance(display_specs, dict):
                            formatted_measurements = [{"Vị trí đo (POM)": key, "Thông số kỹ thuật thực tế": value} for key, value in display_specs.items()]
                            st.dataframe(formatted_measurements, use_container_width=True)
                        else:
                            st.info("Không tìm thấy thông số kỹ thuật gốc.")

                    # BÁO CÁO PHÂN TÍCH ĐỊNH MỨC THEO QUY CHUẨN NGÀNH MAY (ĐỘ CO ĐA CHIỀU & KHỔ VẢI)
                    st.markdown("### 📐 Kết quả phân tích sơ đồ & Tính toán định mức vải")
                    
                    analysis_prompt = f"""
                    You are an expert Apparel Costing & Marker Planning Engineer. Perform a strict fabric consumption calculation.
                    
                    [PRODUCTION VARIABLES]
                    - Usable Fabric Width: {user_width}
                    - Fabric Shrinkage Weft (Ngang): {co_ngang}%
                    - Fabric Shrinkage Warp (Dọc): {co_doc}%
                    
                    [SPECS DATA]
                    - Current Style Measurements: {json.dumps(display_specs, ensure_ascii=False)}
                    - Reference Records: {json.dumps(fabric_records, ensure_ascii=False)}
                    
                    [RULES]
                    1. If history match is found, modify fabric consumption proportionally.
                    2. If no history match is found, calculate fabric net consumption per unit using standard garment marker math based on length points found in POM.
                    3. Warp shrinkage ({co_doc}%) must expand required length. Weft shrinkage ({co_ngang}%) impacts pattern layout efficiency inside width ({user_width}). Add 5% cutting wastage.
                    4. Output step-by-step completely in Vietnamese. Make it technical, professional and concise without verbose chat.
                    """
                    
                    with st.spinner("AI đang tính toán sơ đồ định mức và áp công thức co rút dệt may..."):
                        final_payload = list(img_payload) if has_file else []
                        final_payload.append(analysis_prompt)
                        
                        analysis_res = client.models.generate_content(
                            model='gemini-2.5-flash', 
                            contents=final_payload,
                        )
                        st.markdown(analysis_res.text)
                        st.session_state["chat_history"].append({"role": "assistant", "type": "text", "content": analysis_res.text})
                        
                except Exception as master_err:
                    st.error(f"Hệ thống lõi gặp lỗi trong quá trình xử lý: {str(master_err)}")
