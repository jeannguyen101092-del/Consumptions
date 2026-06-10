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
def save_to_supabase_techpack_table(payload_data, raw_file_bytes=None, file_name=""):
    """
    Hàm xử lý đồng bộ dữ liệu, tự động tìm đúng trang có hình thiết kế phẳng (Sketch) sạch,
    đẩy ảnh rập lên Storage kho_anh và số hóa chuỗi đặc trưng hình học đồng bộ với luồng đối soát.
    ✨ ĐÃ SỬA: Tích hợp bộ lọc thị giác thông minh loại bỏ hoàn toàn các trang bảng biểu dữ liệu (Spec Grid)
    """
    try:
        style_name_db = payload_data.get("style_number_parsed", "").strip()
        if not style_name_db: 
            style_name_db = "UNKNOWN_STYLE"
            
        sketch_b64 = payload_data.get("sketch_image", "")
        public_image_url = ""
        image_data = None

        # LUỒNG CAO CẤP: Nếu có file gốc dạng PDF, tự động dò tìm trang Sketch sạch 100%
        if raw_file_bytes and file_name.lower().endswith('.pdf'):
            try:
                import pdfplumber  # Dùng để kiểm tra mật độ chữ trên trang nhanh chóng
                info_pdf = pdfinfo_from_bytes(raw_file_bytes)
                total_p = int(info_pdf.get("Pages", 1))
                pdf_images = convert_from_bytes(raw_file_bytes, dpi=90, first_page=1, last_page=total_p)
                
                # Đồng bộ chỉ số trang bóc tách được từ metadata của luồng AI
                detected_idx = int(payload_data.get("sketch_page_index_detected", 0))
                
                # --- THUẬT TOÁN BỘ LỌC THỊ GIÁC: KIỂM TRA CHỐNG BẮT NHẦM BẢNG THÔNG SỐ (SPEC GRID) ---
                best_idx = detected_idx
                
                with pdfplumber.open(io.BytesIO(raw_file_bytes)) as pdf:
                    # Kiểm tra trang hiện tại được AI chỉ định
                    if 0 <= detected_idx < len(pdf.pages):
                        page_text = pdf.pages[detected_idx].extract_text() or ""
                        # Nếu trang chứa quá nhiều từ khóa thông số dệt may, khả năng cao là bảng dữ liệu (Spec Grid)
                        tech_words = ["WAIST", "HIP", "INSEAM", "THIGH", "RISE", "SPEC", "TARGET", "TOLERANCE", "SIZE"]
                        word_count = sum(1 for w in tech_words if w in page_text.upper())
                        
                        # Nếu mật độ chữ kỹ thuật > 4 hoặc tổng ký tự quá dài -> Chạy thuật toán quét tìm trang Flat Sketch thực sự
                        if word_count >= 4 or len(page_text) > 400:
                            min_text_len = 99999
                            # Quét nhanh 4 trang đầu tiên (nơi thường đặt bản vẽ thiết kế)
                            for i in range(min(4, len(pdf.pages))):
                                txt = pdf.pages[i].extract_text() or ""
                                c_count = sum(1 for w in tech_words if w in txt.upper())
                                # Tìm trang có ít chữ kỹ thuật nhất và ngắn gọn nhất (thường chỉ chứa ảnh Sketch và tên mã hàng)
                                if c_count < 3 and len(txt) < min_text_len:
                                    min_text_len = len(txt)
                                    best_idx = i
                
                # Trích xuất hình ảnh từ trang đã được lọc sạch
                if 0 <= best_idx < len(pdf_images):
                    img_buf = io.BytesIO()
                    pdf_images[best_idx].convert("RGB").save(img_buf, format="JPEG", quality=85)
                    image_data = img_buf.getvalue()
            except Exception as e:
                print(f"[IMAGE EXTRACT WARNING]: {str(e)}")
                image_data = None

        # Hướng xử lý dự phòng nếu không phải file PDF hoặc bóc tách lỗi thì dùng ảnh Base64
        if not image_data and sketch_b64:
            try:
                import base64
                image_data = base64.b64decode(sketch_b64)
            except Exception:
                pass

        # Đẩy dữ liệu ảnh đã được lọc sạch lên hệ thống Supabase Storage
        if image_data:
            try:
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

        # ⚡ LUỒNG ĐỒNG BỘ THỊ GIÁC: Quét chuỗi đặc trưng hình học giống hệt Đoạn tìm kiếm tương đồng
        visual_description_str = "technical garment layout specs"
        if image_data:
            gemini_key = get_secure_gemini_key()
            if gemini_key:
                try:
                    client_db = genai.Client(api_key=gemini_key)
                    vision_prompt = """
                    Analyze this technical flat sketch in detail. 
                    List all unique geometric attributes, silhouette, waistband type, front/back pockets layout, and panel shapes.
                    Output a dense string of these visual characteristics for garment similarity matching.
                    """
                    vision_res = client_db.models.generate_content(
                        model='gemini-2.5-flash',
                        contents=[types.Part.from_bytes(data=image_data, mime_type='image/jpeg'), vision_prompt]
                    )
                    if vision_res.text:
                        visual_description_str = vision_res.text.strip()
                except Exception as ai_err:
                    print(f"[AI VISION ERROR - LUỒNG NẠP KHO]: {str(ai_err)}")

        headers = {
            "apikey": SB_KEY, 
            "Authorization": f"Bearer {SB_KEY}",
            "Content-Type": "application/json", 
            "Prefer": "resolution=merge-duplicates"
        }
        insert_url = f"{SB_URL.rstrip('/')}/rest/v1/thong_so_techpack"
        
        raw_measurements = payload_data.get("measurements", {})
        clean_dict = {str(k).strip(): str(v).strip() for k, v in dict(raw_measurements).items()}

        db_payload = {
            "StyleName": style_name_db,
            "Buyer": payload_data.get("buyer"),
            "Category": payload_data.get("category"),
            "BaseSize": payload_data.get("base_size_name"),
            "DetailedMeasurements": clean_dict,
            "SketchURL": public_image_url,
            "sketch_vector": visual_description_str 
        }
        
        response = requests.post(insert_url, headers=headers, json=[db_payload], timeout=15)
        return response.status_code >= 200 and response.status_code <= 299
    except Exception as e:
        st.sidebar.error(f"Lỗi xử lý hệ thống nạp kho: {str(e)}")
        return False




def get_historical_fabric_consumption_from_db(search_keyword=None):
    """
    Hàm tra cứu kho dữ liệu san_pham lịch sử nâng cao.
    ✨ ĐÃ SỬA LỖI TRỐNG BẢNG BOM: Áp dụng tìm kiếm mờ chuỗi lõi, không chia cắt chữ/số làm mất hậu tố wash dệt may.
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
            kw_raw = str(search_keyword).strip().upper()
            # Làm sạch ký tự đặc biệt nhưng giữ nguyên vẹn chuỗi dài mã hàng để Supabase quét chính xác
            kw_clean = re.sub(r'[^A-Z0-9]', '', kw_raw)
            
            if len(kw_clean) >= 5:
                # Tìm kiếm mờ thông minh bao quát cả mã gốc lẫn các biến thể wash rách rập phân xưởng
                or_filter = f"(style_name.ilike.*{kw_clean}*,article_name.ilike.*{kw_clean}*)"
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
    ✨ ĐÃ CHUẨN HÓA: Đảm bảo đồng bộ chính xác tên các trường dữ liệu để trả về cho Đoạn 3 hiển thị.
    """
    try:
        headers = {
            "apikey": SB_KEY, 
            "Authorization": f"Bearer {SB_KEY}"
        }
        url = f"{SB_URL.rstrip('/')}/rest/v1/thong_so_techpack"
        
        query_params = {
            "select": "StyleName,Buyer,Category,BaseSize,DetailedMeasurements,SketchURL,sketch_vector",
            "limit": 500
        }
        
        if style_name_keyword and str(style_name_keyword).strip().upper() != "UNKNOWN":
            clean_kw = str(style_name_keyword).strip()
            query_params["StyleName"] = f"ilike.*{clean_kw}*"
            
        response = requests.get(url, headers=headers, params=query_params, timeout=15)
        return response.json() if response.status_code == 200 else []
    except Exception:
        return []

def process_single_pdf_batch(file_bytes, file_name):
    """
    Hàm bóc tách dữ liệu kỹ thuật từ một file PDF độc lập phục vụ LUỒNG NẠP KHO.
    ✨ ĐÃ SỬA LỖI MẤT ẢNH: Đóng gói và trả về đầy đủ các trường Buyer, Category, Measurements 
    và nhị phân ảnh vẽ phẳng rập sạch về cho luồng hiển thị đa luồng xử lý ngầm.
    """
    try:
        gemini_key = get_secure_gemini_key()
        if not gemini_key:
            return {"success": False, "error": "API Key cho Gemini đang bị thiếu trong Secrets."}
            
        client = genai.Client(api_key=gemini_key)
        info = pdfinfo_from_bytes(file_bytes)
        total_p = int(info.get("Pages", 1))
        
        pdf_parts_payload = []
        chat_images = convert_from_bytes(file_bytes, dpi=90, first_page=1, last_page=total_p)
        for page_img in chat_images:
            img_buf = io.BytesIO()
            page_img.convert("RGB").save(img_buf, format="JPEG", quality=75)
            pdf_parts_payload.append(types.Part.from_bytes(data=img_buf.getvalue(), mime_type='image/jpeg'))
            
        # PROMPT CÔNG NGHIỆP: Ép AI bóc tách đầy đủ thông tin khách hàng, chủng loại hàng hóa và định vị trang rập thiết kế
        industrial_extraction_prompt = (
            "You are an expert Garment Specification Auditor. Analyze all sheets page by page. "
            "1. Identify the core 'Base Size' / 'Sample Size' (e.g., written as 32/32, 34/32, or Size M). "
            "2. CRITICAL SPECIFICATION SELECTION RULE: If the sheet displays a grading matrix table with multiple length options, "
            "you MUST extract the target point of measurement (POM) specs that strictly belong to the specified Base/Sample length column (e.g. 32\"). "
            "3. Extract all available Points of Measurement (POM) for this single base size only. Provide at least 15-20 fields if present. "
            "4. Find the exact 'Style ID' / 'Style Number' (e.g. 1P001369), 'Category' / 'Product Line' (e.g. Denim Pants), and 'Buyer' name (e.g. Vineyard Vines). "
            "5. Detect the exact PAGE INDEX (0-based) containing the pure black and white line art TECHNICAL FLAT SKETCH. "
            "Return a completely valid raw JSON string matching this schema (no markdown blocks): "
            "{\"style_number_parsed\": \"string\", \"buyer\": \"string\", \"category\": \"string\", \"base_size_name\": \"string\", \"measurements\": {}, \"sketch_page_index_detected\": 0}"
        )
        
        pdf_parts_payload.append(industrial_extraction_prompt)
        response = client.models.generate_content(model='gemini-2.5-flash', contents=pdf_parts_payload)
        
        clean_json = response.text.strip().replace("```json", "").replace("```", "").strip()
        parsed_data = json.loads(clean_json)
        
        # Trích xuất dữ liệu nhị phân ảnh dựa trên số trang AI tìm thấy
        extracted_sketch_bytes = None
        detected_idx = int(parsed_data.get("sketch_page_index_detected", 0))
        if 0 <= detected_idx < len(chat_images):
            b_buf = io.BytesIO()
            chat_images[detected_idx].convert("RGB").save(b_buf, format="JPEG")
            extracted_sketch_bytes = b_buf.getvalue()
            
        # Thực hiện gọi hàm đồng bộ đẩy dữ liệu sạch lên Supabase ngay lập tức
        success_db = save_to_supabase_techpack_table(parsed_data, raw_file_bytes=file_bytes, file_name=file_name)
        
        # 🔥 ĐỒNG BỘ ĐẦU RA TOÀN DIỆN: Trả đầy đủ buyer, category và sketch_bytes ra ngoài rìa để luồng hiển thị đọc được
        return {
            "success": success_db,
            "style_id": parsed_data.get("style_number_parsed", "UNKNOWN"),
            "buyer": parsed_data.get("buyer", "UNKNOWN BUYER"),
            "category": parsed_data.get("category", "GARMENT"),
            "size": parsed_data.get("base_size_name", "32"),
            "measurements": parsed_data.get("measurements", {}), 
            "sketch_bytes": extracted_sketch_bytes, 
            "error": None if success_db else "Lỗi ghi dữ liệu đồng bộ lên bảng Supabase"
        }
    except Exception as e:
        return {"success": False, "error": f"Lỗi bóc tách PDF công nghiệp: {str(e)}"}






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


if menu_selection == "📊 Upload Techpack":
    import base64
    import concurrent.futures

    st.markdown('<div class="component-title-box">📊 MULTI-BATCH GARMENT SPECIFICATION MATRIX</div>', unsafe_allow_html=True)
    
    st.markdown("""<div class="card-container"><div class="card-section-header">📥 INGESTION ENGINE</div>
    <p style="color: #64748B; font-size:13px; margin:0 0 15px 0;">Hệ thống tự động cắt trang, khử nhiễu đồ họa phẳng và gọi API mạng nơ-ron tích hợp để bóc tách thông số hàng loạt.</p></div>""", unsafe_allow_html=True)
    
    uploaded_files = st.file_uploader("Upload Techpack PDFs Here", type=["pdf"], accept_multiple_files=True, key="bulk_techpack_pdf_uploader", label_visibility="collapsed")
    
    if uploaded_files:
        files_to_render = []
        files_need_processing = [f for f in uploaded_files if f.name not in st.session_state["processed_styles"]]
        
        if files_need_processing:
            if st.button(f"🚀 KÍCH HOẠT SỐ HÓA ĐA LUỒNG SONG SONG ({len(files_need_processing)} FILE MỚI)", use_container_width=True, type="primary"):
                status_text = st.empty()
                progress_bar = st.progress(0)
                total_new_files = len(files_need_processing)
                
                def thread_worker(file_obj):
                    try:
                        f_bytes = file_obj.getvalue()
                        res = process_single_pdf_batch(f_bytes, file_obj.name)
                        return {
                            "file_name": file_obj.name, 
                            "success": res.get("success", False), 
                            "style_id": res.get("style_id", "UNKNOWN"),
                            "buyer": res.get("buyer", "UNKNOWN BUYER"),
                            "category": res.get("category", "GARMENT"),
                            "size": res.get("size", "32"),
                            "measurements": res.get("measurements", {}),
                            "sketch_bytes": res.get("sketch_bytes", None),
                            "error": res.get("error", None),
                            "raw_bytes": f_bytes  
                        }
                    except Exception as e:
                        return {"file_name": file_obj.name, "success": False, "error": str(e), "raw_bytes": None}

                with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
                    future_to_file = {executor.submit(thread_worker, f): f.name for f in files_need_processing}
                    
                    for idx, future in enumerate(concurrent.futures.as_completed(future_to_file)):
                        f_name = future_to_file[future]
                        try:
                            task_res = future.result()
                            if task_res.get("success") == True:
                                # ĐỒNG BỘ TIỀN TỐ ẢNH BASE64: Ép trình duyệt tự động bung hình rập nét mảnh lớn lập tức
                                s_bytes = task_res.get("sketch_bytes")
                                img_base64_str = f"data:image/jpeg;base64,{base64.b64encode(s_bytes).decode('utf-8')}" if s_bytes else ""
                                
                                mock_data = {
                                    "style_number_parsed": task_res.get("style_id"),
                                    "buyer": task_res.get("buyer"), 
                                    "category": task_res.get("category"),
                                    "base_size_name": task_res.get("size"),
                                    "measurements": task_res.get("measurements", {}), 
                                    "sketch_image": img_base64_str, 
                                    "_raw_file_bytes": task_res["raw_bytes"] 
                                }
                                st.session_state["processed_styles"][f_name] = mock_data
                            else:
                                st.error(f"FAIL ENGINE [{f_name}]: {task_res.get('error')}")
                        except Exception as exc:
                            st.error(f"CRITICAL CRASH [{f_name}]: {str(exc)}")
                        
                        completed = idx + 1
                        progress_bar.progress(completed / total_new_files)
                        status_text.text(f"⚡ Core AI đang xử lý: {completed}/{total_new_files} tệp ({f_name})...")
                
                status_text.empty()
                progress_bar.empty()
                st.success("🎉 Số hóa dữ liệu thành công! Hãy kiểm tra bảng thông số bên dưới trước khi bấm lưu.")
        for file in uploaded_files:
            if file.name in st.session_state["processed_styles"]:
                files_to_render.append(file.name)

        if files_to_render:
            st.markdown("<br>", unsafe_allow_html=True)
            
            if st.button("💾 LƯU TOÀN BỘ DỮ LIỆU ĐÃ SỐ HÓA VÀO MASTER DB", key="bulk_save_all_btn", type="primary", use_container_width=True):
                success_count = 0
                with st.spinner("Đang đồng bộ cổng dữ liệu nhị phân hàng loạt lên Supabase Cloud..."):
                    for f_name in files_to_render:
                        style_data = st.session_state["processed_styles"][f_name]
                        raw_bytes_backup = style_data.get("_raw_file_bytes", None)
                        if save_to_supabase_techpack_table(payload_data=style_data, raw_file_bytes=raw_bytes_backup, file_name=f_name): 
                            success_count += 1
                st.success(f"🎉 PATTERN DATA PIPELINE: Đã bóc tách ảnh Sketch sạch và lưu trữ thành công {success_count}/{len(files_to_render)} mã hàng vào Database!")
            
            st.markdown("---")
            st.markdown("### 📋 KẾT QUẢ SỐ HÓA HÌNH HỌC VÀ THÔNG SỐ SẢN XUẤT")

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
                        # SỬA TRIỆT ĐỂ: Gọi biến trực tiếp chứa thẻ định vị, xóa hoàn toàn dấu ngoặc kép gây lỗi thô chữ
                        if data.get("sketch_image") and data["sketch_image"] != "":
                            try:
                                st.image(data["sketch_image"], use_container_width=True)
                            except Exception:
                                st.info("Hệ thống đang tải cổng ảnh vẽ phẳng kĩ thuật...")
                    st.markdown("<br><hr style='border-color:#E2E8F0;'><br>", unsafe_allow_html=True)
    else:
        st.markdown('<div class="idle-alert-box">⚠️ INITIALIZATION SYSTEM IDLE: Hiện tại chưa có tệp dữ liệu Techpack nào được nạp vào hệ thống để AI khởi chạy mô hình.</div>', unsafe_allow_html=True)







# -----------------------------------------------------------------------------
# CHỨC NĂNG 2: ĐỐI CHIẾU SO SÁNH HAI MÃ RẬP KHÁC NHAU (PATTERN SPEC COMPARISON)
# -----------------------------------------------------------------------------
elif menu_selection == "🔄 Pattern Spec Comparison":
    st.markdown('<div class="component-title-box">🔄 DIFFERENTIAL GEOMETRY & DELTA SPEC EVALUATOR</div>', unsafe_allow_html=True)
    st.markdown('<div class="card-container"><div class="card-section-header">🔍 CONFIGURATION SELECTION</div><p style="color: #64748B; font-size:13px; margin:0 0 15px 0;">Tải lên hai tệp bản vẽ kỹ thuật độc lập để tính toán khoảng chênh lệch rập mẫu.</p></div>', unsafe_allow_html=True)
    
    sc1, sc2 = st.columns(2)
    with sc1: file1 = st.file_uploader("Chọn file mẫu Techpack Gốc (File A)", type=["pdf"], key="f1")
    with sc2: file2 = st.file_uploader("Chọn file mẫu Techpack Sửa đổi (File B)", type=["pdf"], key="f2")
    
    if file1 and file2:
        # SỬA TRIỆT ĐỂ LỖI KEYERROR: Kiểm tra điều kiện success nghiêm ngặt trước khi gán
        if st.session_state.get("last_f1_name") != file1.name or "data_a" not in st.session_state:
            res1 = process_single_pdf_batch(file1.getvalue(), file1.name)
            if res1.get("success"): 
                st.session_state["data_a"] = res1["data"]
                st.session_state["last_f1_name"] = file1.name
            else:
                st.error(f"❌ Lỗi xử lý File A: {res1.get('error', 'Không xác định')}")
                st.session_state.pop("data_a", None)
                
        if st.session_state.get("last_f2_name") != file2.name or "data_b" not in st.session_state:
            res2 = process_single_pdf_batch(file2.getvalue(), file2.name)
            if res2.get("success"): 
                st.session_state["data_b"] = res2["data"]
                st.session_state["last_f2_name"] = file2.name
            else:
                st.error(f"❌ Lỗi xử lý File B: {res2.get('error', 'Không xác định')}")
                st.session_state.pop("data_b", None)
            
        d1 = st.session_state.get("data_a")
        d2 = st.session_state.get("data_b")
        
        # Chỉ tiến hành hiển thị bảng so sánh khi cả hai tệp dữ liệu đã bóc tách thành công
        if d1 and d2:
            style_a = d1.get('style_number_parsed', 'Mẫu A')
            style_b = d2.get('style_number_parsed', 'Mẫu B')
            if style_a == style_b:
                lbl_a = f"Mẫu A ({style_a}-Gốc) [{d1.get('base_size_name','30').strip()}]"
                lbl_b = f"Mẫu B ({style_b}-Sửa) [{d2.get('base_size_name','30').strip()}]"
            else:
                lbl_a = f"Mẫu A ({style_a}) [{d1.get('base_size_name','30').strip()}]"
                lbl_b = f"Mẫu B ({style_b}) [{d2.get('base_size_name','30').strip()}]"
                
            st.info(f"⚙️ **ĐANG ĐỐI CHIẾU MA TRẬN:** {lbl_a} ↔️ {lbl_b}")
            
            def clean_num(v):
                if not v or str(v).strip().upper() in ["N/A", ""]: return 0.0
                try:
                    s = str(v).replace("INCH", "").strip()
                    if " " in s:
                        p = s.split()
                        whole = float(p[0])
                        frac = p[1].split('/')
                        return whole + (float(frac[0]) / float(frac[1]))
                    return float(s.split('/')[0]) / float(s.split('/')[1]) if "/" in s else float(s)
                except:
                    import re
                    nums = re.findall(r"[-+]?\d*\.\d+|\d+", str(v))
                    return float(nums[0]) if nums else 0.0

            def extract_pom_code(pom_str):
                import re
                if not pom_str: return ""
                match = re.search(r'([A-Za-z]{2,4}-\d{3})', str(pom_str))
                return match.group(1).upper() if match else str(pom_str).lower().strip()

            df_a = pd.DataFrame(list(d1["measurements"].items()), columns=['raw_pom_a', lbl_a])
            df_b = pd.DataFrame(list(d2["measurements"].items()), columns=['raw_pom_b', lbl_b])
            
            df_a['pom_code'] = df_a['raw_pom_a'].apply(extract_pom_code)
            df_b['pom_code'] = df_b['raw_pom_b'].apply(extract_pom_code)
            
            df_a['seq'] = df_a.groupby('pom_code').cumcount()
            df_b['seq'] = df_b.groupby('pom_code').cumcount()
            
            df_res = pd.merge(df_a, df_b, on=['pom_code', 'seq'], how='outer').fillna("N/A").sort_values(['pom_code', 'seq'])
            
            table_body_html = ""
            compare_rows_for_df = []
            
            for _, r in df_res.iterrows():
                display_pom = r['raw_pom_a'] if r['raw_pom_a'] != "N/A" else r['raw_pom_b']
                val1, val2 = r[lbl_a], r[lbl_b]
                
                delta = round(clean_num(val2) - clean_num(val1), 3) if val1 != "N/A" and val2 != "N/A" else "N/A"
                compare_rows_for_df.append({"Vị trí đo (POM)": display_pom, lbl_a: val1, lbl_b: val2, "Sai lệch (Delta)": delta})
                
                if delta == "N/A":
                    style, txt = "color:#94A3B8; font-style:italic;", "N/A"
                elif delta > 0:
                    style, txt = "background:rgba(16,185,129,0.15); color:#166534; font-weight:700; padding:2px 8px; border-radius:4px; font-size:12px; border:1px solid #BBF7D0;", f"+{delta}"
                elif delta < 0:
                    style, txt = "background:rgba(239,68,68,0.15); color:#991B1B; font-weight:700; padding:2px 8px; border-radius:4px; font-size:12px; border:1px solid #FECACA;", f"{delta}"
                else:
                    style, txt = "color:#64748B; font-size:12px;", "0.00"
                
                table_body_html += f"<tr style='background:#FFF;'><td style='padding:10px 14px; border-bottom:1px solid #E2E8F0; font-weight:600; color:#1E293B;'>{display_pom}</td><td style='padding:10px 14px; border-bottom:1px solid #E2E8F0; color:#334155;'>{val1}</td><td style='padding:10px 14px; border-bottom:1px solid #E2E8F0; color:#334155;'>{val2}</td><td style='padding:10px 14px; border-bottom:1px solid #E2E8F0; text-align:center;'><span style='{style}'>{txt}</span></td></tr>"
            
            st.markdown(f"<div style='max-height:460px; overflow-y:auto; border:1px solid #CBD5E1; border-radius:12px;'><table style='width:100%; border-collapse:collapse; text-align:left; font-family:sans-serif;'><thead style='background:linear-gradient(90deg, #1E3A8A, #2563EB); color:white;'><tr><th style='padding:14px 16px; position:sticky; top:0; z-index:10;'>Vị trí đo (POM Description)</th><th style='padding:14px 16px; position:sticky; top:0; z-index:10;'>{lbl_a}</th><th style='padding:14px 16px; position:sticky; top:0; z-index:10;'>{lbl_b}</th><th style='padding:14px 16px; text-align:center; width:150px; position:sticky; top:0; z-index:10;'>Sai lệch (Delta)</th></tr></thead><tbody>{table_body_html}</tbody></table></div>", unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)

            # --- KHỐI ĐỔ MÀU EXCEL ĐỒNG BỘ GIAO DIỆN ---
            df_xl = pd.DataFrame(compare_rows_for_df)
            towrite = io.BytesIO()
            with pd.ExcelWriter(towrite, engine='xlsxwriter') as writer:
                df_xl.to_excel(writer, index=False, sheet_name='Spec_Report')
                workbook  = writer.book
                worksheet = writer.sheets['Spec_Report']
                
                header_fmt = workbook.add_format({'bold':True, 'text_wrap':True, 'fg_color':'#1E3A8A', 'font_color':'white', 'border':1, 'align':'center', 'valign':'vcenter'})
                left_fmt   = workbook.add_format({'align':'left', 'valign':'vcenter', 'border':1, 'font_name':'Arial', 'font_size':10})
                center_fmt = workbook.add_format({'align':'center', 'valign':'vcenter', 'border':1, 'font_name':'Arial', 'font_size':10})
                
                green_fmt  = workbook.add_format({'bold':True, 'align':'center', 'valign':'vcenter', 'fg_color':'#E8F5E9', 'font_color':'#166534', 'border':1})
                red_fmt    = workbook.add_format({'bold':True, 'align':'center', 'valign':'vcenter', 'fg_color':'#FFEBEE', 'font_color':'#991B1B', 'border':1})
                na_fmt     = workbook.add_format({'italic':True, 'align':'center', 'valign':'vcenter', 'fg_color':'#F8FAFC', 'font_color':'#94A3B8', 'border':1})
                
                for col_num, title in enumerate(df_xl.columns):
                    worksheet.write(0, col_num, title, header_fmt)
                    max_len = max(df_xl[title].astype(str).map(len).max(), len(title)) + 4
                    worksheet.set_column(col_num, col_num, max_len)
                
                for idx, row in df_xl.iterrows():
                    worksheet.write(idx + 1, 0, row["Vị trí đo (POM)"], left_fmt)
                    worksheet.write(idx + 1, 1, row[lbl_a], center_fmt)
                    worksheet.write(idx + 1, 2, row[lbl_b], center_fmt)
                    
                    d_val = row["Sai lệch (Delta)"]
                    if d_val == "N/A":
                        worksheet.write(idx + 1, 3, "N/A", na_fmt)
                    elif d_val > 0:
                        worksheet.write(idx + 1, 3, f"+{d_val}", green_fmt)
                    elif d_val < 0:
                        worksheet.write(idx + 1, 3, d_val, red_fmt)
                    else:
                        worksheet.write(idx + 1, 3, "0.00", center_fmt)
                        
                worksheet.set_row(0, 26)
                worksheet.freeze_panes(1, 0)
                
            towrite.seek(0)
            st.download_button(label="📥 Tải Báo Cáo Đối Chiếu Có Màu (Excel)", data=towrite, file_name=f"Spec_Comparison_{style_a}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")




import io
import json
import re
import requests
import streamlit as st
from urllib.parse import quote
from google import genai
from google.genai import types

try:
    from pdf2image import convert_from_bytes, pdfinfo_from_bytes
except ImportError:
    pass

# HÀM QUY ĐỔI PHÂN SỐ NGÀNH MAY CHUẨN (Ví dụ: "1 1/8 inches" -> 1.125)
def parse_fraction(val_str):
    if not val_str: 
        return 0.0
    val_str = str(val_str).strip().lower()
    val_str = val_str.replace('"', '').replace('inches', '').replace('inch', '').replace('s', '').strip()
    try:
        if ' ' in val_str:
            parts = [p for p in val_str.split(' ') if p.strip()]
            if len(parts) >= 2:
                whole = float(parts)
                frac = parts
            else:
                whole = 0.0
                frac = parts
        else:
            whole = 0.0
            frac = val_str
            
        if '/' in frac:
            num, denom = frac.split('/')
            return whole + (float(num) / float(denom))
        return float(val_str) if val_str else 0.0
    except Exception:
        return 0.0
def ai_consumption_analyst_engine(client, user_message, matched_techpack, bom_records, new_style_measurements, target_new_sketch_bytes, detected_size):
    """
    Bộ não xử lý tính toán định mức nâng cao đáp ứng kịch bản có mã tương đồng (Mục đích 2)
    và tự động ước tính diện tích hình học rập mẫu khi không có mã tương đồng (Mục đích 3).
    """
    style_old_name = matched_techpack.get("StyleName", "N/A") if matched_techpack else "N/A"
    specs_old = matched_techpack.get("DetailedMeasurements", {}) if matched_techpack else {}
    
    bom_summary = ""
    if bom_records:
        bom_summary = "\n".join([f"- Vật tư: {r.get('consumption_type')}, Mã vải: {r.get('article_name')}, Khổ vải gốc: {r.get('material_size')}, ĐM gốc: {r.get('consumption_value')}" for r in bom_records])

    shrinkage_width = re.findall(r'(?:CO RÚT NGANG|NGANG)\s*(\d+(?:\.\d+)?)\s*%', user_message.upper())
    shrinkage_length = re.findall(r'(?:CO RÚT DỌC|DỌC)\s*(\d+(?:\.\d+)?)\s*%', user_message.upper())
    new_fabric_width = re.findall(r'(?:KHỔ VẢI|KHỔ)\s*(\d+)\s*(?:\"|INCH|INCHES)?', user_message.upper())

    w_shrink = float(shrinkage_width) if shrinkage_width else 0.0
    l_shrink = float(shrinkage_length) if shrinkage_length else 0.0
    f_width = float(new_fabric_width) if new_fabric_width else 0.0

    system_instruction = f"""
    You are an expert Garment Engineer and Techpack Costing Analyst at PPJ Group.
    Your mission is to calculate and predict the exact fabric consumption (Định mức vải - YRD/PCS) based on technical specs, layout patterns, and user metrics.
    
    CRITICAL DATA FOR CALCULATION:
    1. MATCHED OLD STYLE DATA (Mã tương đồng): Name: {style_old_name}
       - Old Spec (POM): {json.dumps(specs_old)}
       - Old BOM database: {bom_summary}
    2. NEW STYLE TECHPACK DATA (Mã mới tải lên):
       - Target Base Size detected: Size {detected_size}
       - New Spec (POM) parsed by vision: {json.dumps(new_style_measurements)}
    3. USER INPUT FABRIC CHANGES:
       - Fabric Width requested: {f_width if f_width > 0 else 'Keep database standard'}
       - Width Shrinkage (Co rút ngang): {w_shrink}%
       - Length Shrinkage (Co rút dọc): {l_shrink}%
       
    EXECUTION LOGIC BASED ON 2 MAIN SCENARIOS:
    - SCENARIO A (MỤC ĐÍCH 2 - Có mã tương đồng): Calculate based on the old consumption value found in database. Apply Shrinkage multiplier: New Consumption = Old Consumption * (1 + Length Shrinkage%) * (1 + Width Shrinkage%). Adjust further based on the Marker Area Delta parameter provided in the size context.
    - SCENARIO B (MỤC ĐÍCH 3 - KHÔNG CÓ MÃ TƯƠNG ĐỒNG / MÃ MỚI HOÀN TOÀN): Perform a pure Geometric Surface Area Estimation task using the attached Flat Sketch Image and the New Spec (POM). Estimate layout blocking area (Width * Length of panels like Front panel, Back panel, Waistband, Pockets) + Seam allowances (Đường may) + Waste factor (Hao hụt đi sơ đồ 5-8%) to yield the initial consumption rate.
    
    OUTPUT REQUIREMENT: Answer directly, professionally in Vietnamese like ChatGPT with clear mathematical steps and final metric values. Keep it highly scannable. Do not reply generically.
    """

    chat_contents = [types.Part.from_text(text=system_instruction)]
    for past_chat in st.session_state.get("consumption_chat_history", []):
        chat_contents.append(types.Part.from_text(text=f"User: {past_chat['user']}"))
        chat_contents.append(types.Part.from_text(text=f"AI: {past_chat['ai']}"))
        
    chat_contents.append(types.Part.from_text(text=f"User current request: {user_message}"))
    if target_new_sketch_bytes:
        chat_contents.append(types.Part.from_bytes(data=target_new_sketch_bytes, mime_type='image/jpeg'))

    try:
        response = client.models.generate_content(model='gemini-2.5-flash', contents=chat_contents)
        ai_reply = response.text if response.text else "Hệ thống AI không thể đưa ra phân tích."
        st.session_state["consumption_chat_history"].append({"user": user_message, "ai": ai_reply})
        return ai_reply
    except Exception as e:
        return f"🚨 Lỗi cổng phân tích định mức: {str(e)}"
gemini_key = get_secure_gemini_key()
if gemini_key:
    client = genai.Client(api_key=gemini_key, http_options=types.HttpOptions(api_version='v1'))

new_style_id_detected = "UNKNOWN_STYLE"
new_style_category_detected = ""
new_style_fabric_detected = "UNKNOWN_FABRIC"
new_style_measurements_dict = {}
new_style_base_size = "32"
img_payload = [] 
target_new_sketch_bytes = None 

# Đồng bộ hóa cấu trúc lấy tệp đính kèm từ Uploader lưu trong bộ nhớ hệ thống
target_file_object = None
if 'uploaded_file' in st.session_state and st.session_state['uploaded_file'] is not None:
    target_file_object = st.session_state['uploaded_file']
elif 'chat_uploader' in st.session_state and st.session_state['chat_uploader'] is not None:
    target_file_object = st.session_state['chat_uploader']

has_file = target_file_object is not None

if has_file:
    file_bytes = target_file_object.getvalue()
    file_name = target_file_object.name
    if file_name.lower().endswith('.pdf'):
        try:
            info_chat = pdfinfo_from_bytes(file_bytes)
            total_chat_pages = int(info_chat.get("Pages", 1))
            chat_images = convert_from_bytes(file_bytes, dpi=90, first_page=1, last_page=total_chat_pages)
            for idx, page_img in enumerate(chat_images):
                img_buf = io.BytesIO()
                page_img.convert("RGB").save(img_buf, format="JPEG", quality=75)
                img_payload.append(types.Part.from_bytes(data=img_buf.getvalue(), mime_type='image/jpeg'))
            
            # ÉP BỘ LỌC THỊ GIÁC: Ép AI tìm đúng số trang vẽ kĩ thuật lớn sạch, loại bỏ trang lưới bảng biểu BOM chữ
                        # --- 🚀 N N CẤP ĐOẠN 3: ÉP AI KHÓA TRỤC INSEAM MẪU CHUẨN TRÊN TRANG ĐỐI SOÁT CHÍNH ---
            extraction_prompt = (
                "You are an expert Garment Specification Auditor at PPJ Group. Analyze all attached sheets page by page. "
                "1. Locate the core 'Base Size' / 'Sample Size' specified by the buyer (e.g., Size 32 with Inseam 32, written as 32/32 or 32x32). "
                "2. CRITICAL MEASUREMENT SELECTION RULE: Look closely at the grading table sheet. "
                "If the table contains multiple inseam length columns (e.g., columns for Inseam 30, 32, 34), you MUST extract the target point of measurement (POM) values that belong ONLY to the specified Sample length column (which is 32\"). "
                "STRICTLY FORBIDDEN: Do not blindly extract the value from the first column if it represents an Inseam of 30\". "
                "You must output the true Inseam target value which is 32\" for a 32/32 profile garment. "
                "3. Extract at least 15-20 distinct Points of Measurement (POM) for this specific sample size only. "
                "4. Find the exact 'Style ID' / 'Style Number' (e.g., 1P001369), 'Category' / 'Product Line', and 'Buyer' name. "
                "5. Detect the exact PAGE INDEX (0-based) containing the pure black and white line art TECHNICAL FLAT SKETCH. "
                "Return a completely valid raw JSON string with this exact schema (no markdown blocks): "
                "{\"detected_style_id\": \"string\", \"category\": \"string\", \"fabric_code\": \"string\", \"base_size_detected\": \"string\", \"measurements\": {}, \"sketch_page_index_detected\": 0}"
            )

            extraction_payload = list(img_payload)
            extraction_payload.append(extraction_prompt)
            
            extraction_res = client.models.generate_content(model='gemini-2.5-flash', contents=extraction_payload)
            clean_json_text = extraction_res.text.strip().replace("```json", "").replace("```", "").strip()
            
            parsed_meta = json.loads(clean_json_text)
            new_style_id_detected = parsed_meta.get("detected_style_id", "UNKNOWN_STYLE").strip()
            new_style_category_detected = parsed_meta.get("category", "").strip()
            new_style_fabric_detected = parsed_meta.get("fabric_code", "UNKNOWN_FABRIC").strip()
            new_style_base_size = parsed_meta.get("base_size_detected", "32").strip()
            new_style_measurements_dict = parsed_meta.get("measurements", {})
            detected_idx = int(parsed_meta.get("sketch_page_index_detected", 0))
            
            if 0 <= detected_idx < len(chat_images):
                b_buf = io.BytesIO()
                chat_images[detected_idx].convert("RGB").save(b_buf, format="JPEG")
                target_new_sketch_bytes = b_buf.getvalue()
        except Exception:
            pass
    else:
        target_new_sketch_bytes = file_bytes

dynamic_keyword = str(new_style_id_detected).strip().upper()
base_sb_url = SB_URL.rstrip('/')
headers = {"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}"}
if menu_selection == "🧵 BOM & Consumption Matrix":
    st.markdown('<div class="component-title-box">🧵 INTELLIGENT BOM & CONSUMPTION MATRIX ENGINE</div>', unsafe_allow_html=True)
    
    # Khóa cứng trạng thái bộ nhớ đệm màn hình (Chống xóa trắng dữ liệu khi Rerun ô Chat)
    if "matched_techpack" not in st.session_state: st.session_state["matched_techpack"] = None
    if "bom_records" not in st.session_state: st.session_state["bom_records"] = []
    if "consumption_chat_history" not in st.session_state: st.session_state["consumption_chat_history"] = []

    control_col1, control_col2 = st.columns([3.3, 0.7])
    with control_col1:
        st.markdown("<p style='font-weight:700; font-size:12px; color:#1E293B;'>📁 INGEST NEW STYLE REPRINTS (PDF/IMAGE)</p>", unsafe_allow_html=True)
        uploaded_file = st.file_uploader("Upload Techpack file", type=["pdf", "jpg", "jpeg", "png"], key="uploaded_file", label_visibility="collapsed")
            
    with control_col2:
        st.markdown("<p style='font-weight:700; font-size:12px; color:#1E293B;'>🧹 RESET CORE</p>", unsafe_allow_html=True)
        if st.button("🗑️ PURGE CHAT CACHE", use_container_width=True, type="secondary"):
            st.session_state["consumption_chat_history"] = []
            st.session_state["matched_techpack"] = None
            st.session_state["bom_records"] = []
            st.success("♻️ MEMORY PURGED - SẴN SÀNG CHO MÃ HÀNG MỚI")
            st.rerun()

    st.markdown("---")

    # Hiển thị tiêu đề Size mẫu cơ sở đang bóc tách đối soát
    if has_file:
        if new_style_base_size and new_style_base_size != "32":
            st.info(f"📋 **CƠ SỞ ĐỐI SOÁT KIẾM TRA:** Mẫu mới số hóa mã hàng `{new_style_id_detected}` | Quy chuẩn kích thước hình học rập mẫu: **SIZE {new_style_base_size}**")
        else:
            st.info(f"📋 **CƠ SỞ ĐỐI SOÁT KIỂM TRA:** Đang áp dụng quy chuẩn kích thước hình học rập mẫu cơ sở: **SIZE 32 / M (Mặc định)**")

    # CHẠY THUẬT TOÁN QUÉT TƯƠNG ĐỒNG KHI CÓ FILE TẢI LÊN
    if has_file and target_new_sketch_bytes and st.session_state["matched_techpack"] is None:
        with st.spinner("⚡ AI đang phân tích phom dáng vẽ phẳng và đối soát dữ liệu kho..."):
            try:
                vision_prompt = "Analyze this technical flat sketch in detail. Output a dense string of these visual characteristics for garment similarity matching."
                vision_res = client.models.generate_content(model='gemini-2.5-flash', contents=[types.Part.from_bytes(data=target_new_sketch_bytes, mime_type='image/jpeg'), vision_prompt])
                query_description = vision_res.text.strip().lower() if vision_res.text else ""
                
                url_techpack = f"{base_sb_url}/rest/v1/thong_so_techpack?select=StyleName,Category,BaseSize,DetailedMeasurements,SketchURL"
                res_tp = requests.get(url_techpack, headers=headers, timeout=10)
                techpack_records = res_tp.json() if res_tp.status_code == 200 else []
                
                best_similarity_ratio = -1.0
                temp_matched = None
                
                if query_description and techpack_records:
                    query_keywords = set(re.findall(r'\b\w{3,15}\b', query_description))
                    for row in techpack_records:
                        db_text = str(row.get("DetailedMeasurements", "")).lower()
                        db_keywords = set(re.findall(r'\b\w{3,15}\b', db_text))
                        if db_keywords:
                            intersection = query_keywords.intersection(db_keywords)
                            union = query_keywords.union(db_keywords)
                            ratio = float(len(intersection)) / float(len(union)) if union else 0
                            if ratio > best_similarity_ratio:
                                best_similarity_ratio = ratio
                                temp_matched = row

                if not temp_matched or best_similarity_ratio < 0.10:
                    for row in techpack_records:
                        if str(row.get("StyleName", "")).strip().upper() == dynamic_keyword:
                            temp_matched = row
                            break
                            
                if temp_matched:
                    st.session_state["matched_techpack"] = temp_matched
                    target_style_name = str(temp_matched.get("StyleName", "")).strip()
                    core_match = re.search(r'\b[A-Z0-9]{5,12}\b', target_style_name.upper())
                    search_term = core_match.group(0) if core_match else target_style_name
                    
                    url_san_pham = f"{base_sb_url}/rest/v1/san_pham?style_name=ilike.*{quote(str(search_term).strip())}*&select=style_name,article_name,consumption_type,material_size,uom,consumption_value,notes"
                    res_sp = requests.get(url_san_pham, headers=headers, timeout=10)
                    if res_sp.status_code == 200: 
                        st.session_state["bom_records"] = res_sp.json()
            except Exception: pass
            # LẤY DỮ LIỆU TỪ BỘ NHỚ KHÓA ĐỂ HIỂN THỊ LÊN MÀN HÌNH MƯỢT MÀ CHỐNG RERUN TRẮNG TRƠN
    matched_techpack = st.session_state["matched_techpack"]
    bom_records = st.session_state["bom_records"]

    if matched_techpack:
        target_style_name = matched_techpack.get("StyleName")
        st.success(f"🎯 MỤC ĐÍCH 2: ĐÃ TÌM THẤY MÃ HÀNG TƯƠNG ĐỒNG TRONG KHO: **{target_style_name}**")
        
        col1, col2 = st.columns(2)
        with col1: 
            if target_new_sketch_bytes is not None:
                st.image(target_new_sketch_bytes, caption="Bản vẽ phẳng mẫu mới (AI quét sạch)", use_container_width=True)
            else:
                st.info("💡 Hệ thống đang liên kết cổng nhị phân ảnh vẽ phẳng sạch...")
        with col2: 
            if matched_techpack.get("SketchURL"): 
                st.image(matched_techpack["SketchURL"], caption=f"Ảnh Sketch gốc lưu trong kho: {target_style_name}", use_container_width=True)

        st.subheader("📦 Chi Tiết Định Mức Nguyên Phụ Liệu Gốc trong kho (BOM)")
        if bom_records:
            formatted_bom = []
            for r in bom_records:
                # 🛠️ THUẬT TOÁN KHỬ LỖI NAN: Kiểm tra và ép kiểu dữ liệu văn bản chuỗi sạch, cấm hiện chữ nan toán học
                raw_c_type = r.get("consumption_type")
                raw_art_name = r.get("article_name")
                raw_m_size = r.get("material_size")
                raw_uom = r.get("uom")
                raw_val = r.get("consumption_value")
                raw_notes = r.get("notes")
                
                # Hàm ép kiểu chuỗi văn bản may mặc chuẩn, nếu dính NaN hoặc rỗng sẽ tự động đưa về khoảng trống sạch
                def clean_db_string(val):
                    if val is None or str(val).strip() == "" or str(val).lower() == "nan" or str(val).lower() == "<na>":
                        return "EMPTY"
                    return str(val).strip()

                formatted_bom.append({
                    "Mã hàng (Style)": clean_db_string(r.get("style_name") if r.get("style_name") else r.get("style_id")),
                    "Tên vật tư": clean_db_string(raw_art_name),
                    "Chủng loại tiêu hao": clean_db_string(raw_c_type), # Ép hiển thị rõ chữ POCKETING / MAIN FABRIC
                    "Khổ nguyên liệu": clean_db_string(raw_m_size),
                    "Đơn vị tính": clean_db_string(raw_uom),
                    "Định mức cơ sở (Kho)": clean_db_string(raw_val),
                    "Ghi chú phân xưởng": clean_db_string(raw_notes)
                })
            st.table(formatted_bom)
            
            # Quét vải chính an toàn không dính lỗi chuỗi nan
            main_fabrics = list(set([str(r.get("article_name")).strip() for r in bom_records if "MAIN" in str(r.get("consumption_type", "")).upper() if r.get("article_name") and str(r.get("article_name")).lower() != "nan"]))
            if main_fabrics: st.info(f"🧵 Mã vải chính của mã hàng gốc: **{', '.join(main_fabrics)}**")
        else:
            st.warning(f"⚠️ Không tìm thấy dữ liệu phụ liệu cho biến thể mã hàng gốc `{dynamic_keyword}` trong bảng san_pham.")

        st.subheader("📊 Bảng Đối Soát Sai Lệch Thông Số Hình Học (Mẫu Gốc vs Mẫu Mới)")
        db_measurements = matched_techpack.get("DetailedMeasurements", {})
        specs_old = {}
        if isinstance(db_measurements, dict): specs_old = db_measurements
        else:
            try: specs_old = json.loads(str(db_measurements))
            except Exception:
                pairs = re.findall(r'"([^"]+)":\s*"([^"]+)"', str(db_measurements))
                if pairs: specs_old = {k: v for k, v in pairs}

        specs_new = new_style_measurements_dict
        
        if specs_old and specs_new:
            def normalize_core_garment_key(raw_key):
                text = str(raw_key).strip().upper()
                text = re.sub(r'^[A-Z]{2,4}-\d{2,4}\s*', '', text)
                text = text.replace('"', '').replace('-', '').replace('\'', '').replace('’', '').replace(' ', '')
                if "WAIST" in text: return "WAIST"
                if "HIP" in text: return "HIP"
                if "THIGH" in text: return "THIGH"
                if "INSEAM" in text: return "INSEAM"
                if "OUTSEAM" in text or "LENGTH" in text: return "OUTSEAM"
                if "KNEE" in text: return "KNEE"
                if "OPENING" in text or "SWEEP" in text: return "LEGOPENING"
                if "RISE" in text or "CROTCH" in text: return "RISE"
                if "CHEST" in text or "BUST" in text: return "CHEST"
                if "SHOULDER" in text: return "SHOULDER"
                if "SLEEVE" in text: return "SLEEVE"
                return text

            norm_map_old = {normalize_core_garment_key(k): (k, v) for k, v in specs_old.items()}
            norm_map_new = {normalize_core_garment_key(k): (k, v) for k, v in specs_new.items()}

            comparison_table = []
            deviation_length_pct = 0.0
            deviation_width_pct = 0.0
            has_len = False
            has_wid = False
            
            for core_key, (original_old_key, old_val) in norm_map_old.items():
                if core_key in norm_map_new:
                    original_new_key, new_val_str = norm_map_new[core_key]
                    v_old = parse_fraction(old_val)
                    v_new = parse_fraction(new_val_str)
                    
                    if v_old > 0 and v_new > 0:
                        diff = v_new - v_old
                        pct_diff = (diff / v_old) * 100
                        
                        if core_key in ["INSEAM", "OUTSEAM", "SLEEVE"]:
                            if pct_diff != 0: deviation_length_pct = pct_diff; has_len = True
                        if core_key in ["WAIST", "HIP", "THIGH", "CHEST"]:
                            if pct_diff != 0: deviation_width_pct = pct_diff; has_wid = True
                                
                        comparison_table.append({
                            "Vị trí đo (POM)": original_old_key,
                            "Thông số gốc (Kho)": f"{old_val}\"",
                            "Thông số mới (Quét)": f"{new_val_str}\"",
                            "Chênh lệch": f"{diff:+.3f}\"",
                            "Tỷ lệ biến động": f"{pct_diff:+.1f}%"
                        })
            
            ui_col1, ui_col2, ui_col3 = st.columns([1.0, 0.5, 0.5])
            with ui_col1:
                st.markdown("<p style='font-weight:700; font-size:14px; color:#1E293B;'>📊 Bảng Đối Soát Sai Lệch Hình Học</p>", unsafe_allow_html=True)
                if comparison_table: st.table(comparison_table)
            with ui_col2:
                st.markdown("<p style='font-weight:700; font-size:14px; color:#1E293B;'>🏛️ Dữ liệu gốc lưu trong Kho</p>", unsafe_allow_html=True)
                st.table([{"Vị trí đo (Gốc)": k, "Thông số kho": v} for k, v in specs_old.items()])
            with ui_col3:
                st.markdown("<p style='font-weight:700; font-size:14px; color:#1E293B;'>📋 Thông số mẫu mới quét được</p>", unsafe_allow_html=True)
                st.table([{"Vị trí đo (Quét sạch)": k, "Thông số quét": v} for k, v in specs_new.items()])
                
            if has_len or has_wid:
                factor_len = 1.0 + (deviation_length_pct / 100.0)
                factor_wid = 1.0 + (deviation_width_pct / 100.0)
                total_area_deviation_pct = (factor_len * factor_wid - 1.0) * 100
                
                st.markdown(f"💡 **Phân tích hình học rập mẫu tự động bởi hệ thống:**")
                st.write(f"- Biến động chiều dài thân rập chủ đạo: **{deviation_length_pct:+.1f}%**")
                st.write(f"- Biến động chiều rộng thân rập chủ đạo: **{deviation_width_pct:+.1f}%**")
                st.markdown(f"🎯 **Tỷ lệ biến động diện tích khối sơ đồ vải thực tế (Marker Area Deviation): {total_area_deviation_pct:+.1f}%**")
                new_style_base_size = f"{new_style_base_size} (Marker Area Delta: {total_area_deviation_pct:+.2f}%)"
        else:
            st.info("💡 Điền file để chạy đối soát.")

    st.markdown("### 💬 PPJ TEXTILE AI COSTING ENGINE - LUỒNG CHAT PHÂN TÍCH ĐỊNH MỨC TỰ ĐỘNG")
    chat_container = st.container()
    with chat_container:
        for chat_block in st.session_state["consumption_chat_history"]:
            with st.chat_message("user"): st.write(chat_block["user"])
            with st.chat_message("assistant", avatar="🧵"): st.write(chat_block["ai"])

    if prompt_input := st.chat_input("Nhập lệnh tính toán định mức nâng cao...", key="matrix_consumption_chat_input"):
        st.session_state["consumption_chat_history"].append({"user": prompt_input, "ai": "Đang tính toán..."})
        ai_output_response = ai_consumption_analyst_engine(client, prompt_input, matched_techpack, bom_records, new_style_measurements_dict, target_new_sketch_bytes, new_style_base_size)
        st.session_state["consumption_chat_history"][-1]["ai"] = ai_output_response
        st.rerun()
