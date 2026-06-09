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
                info_pdf = pdfinfo_from_bytes(raw_file_bytes)
                total_p = int(info_pdf.get("Pages", 1))
                pdf_images = convert_from_bytes(raw_file_bytes, dpi=90, first_page=1, last_page=total_p)
                
                # Đồng bộ chỉ số trang bóc tách được từ metadata của luồng Đoạn 2
                detected_idx = int(payload_data.get("sketch_page_index_detected", 0))
                if 0 <= detected_idx < len(pdf_images):
                    img_buf = io.BytesIO()
                    pdf_images[detected_idx].convert("RGB").save(img_buf, format="JPEG", quality=85)
                    image_data = img_buf.getvalue()
            except Exception:
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
                    # Sử dụng chính xác 100% Vision Prompt của luồng Tìm Kiếm Tương Đồng
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
        
        # SỬA LỖI ĐỐI SOÁT ÍT DÒNG: Đóng gói chuỗi JSON hợp lệ để đẩy lên Supabase không bị dính chuỗi thô văn bản
        json_measurements_string = json.dumps(clean_dict, ensure_ascii=False)

        # SỬA LỖI GHI ĐÈ VECTOR MẤT TƯƠNG ĐỒNG: Đổ chuỗi mô tả vào DetailedMeasurements để đồng bộ thuật toán so khớp chéo
        db_payload = {
            "StyleName": style_name_db,
            "Buyer": payload_data.get("buyer"),
            "Category": payload_data.get("category"),
            "BaseSize": payload_data.get("base_size_name"),
            "DetailedMeasurements": json_measurements_string, # Lưu chuỗi JSON sạch
            "SketchURL": public_image_url,
            "sketch_vector": visual_description_str # Giữ cấu trúc trường dự phòng
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
    ✨ ĐÃ ĐỒNG BỘ TOÀN DIỆN TRẢ VỀ: Ép AI đọc đúng cột kích cỡ mẫu rập cơ sở 32/32,
    đồng thời đóng gói trọn vẹn mảng thông số đo thực tế và ảnh rập phẳng sạch về luồng hiển thị.
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
            
        # PROMPT NÂNG CAO ÉP QUY TẮC NGÀNH MAY: Khóa chặt trục số Waist/Inseam mẫu chuẩn đầu chuyền
        industrial_extraction_prompt = (
            "You are an expert Garment Specification Auditor. Analyze all sheets page by page. "
            "1. Identify the core 'Base Size' / 'Sample Size' (e.g., written as 32/32, 34/32, or Size M). "
            "2. CRITICAL SPECIFICATION SELECTION RULE: If the sheet displays a grading matrix table with multiple length options (e.g., columns for Inseam 30, 32, 34), "
            "you MUST extract the target point of measurement (POM) specs that strictly belong to the specified Base/Sample length column. "
            "If the label is 32/32, the Waist is 32 and the Inseam MUST be extracted from the 32 Length column (which is 32\"). "
            "NEVER extract the Inseam value from the 30\" column blindly. Avoid any row/column shifting errors. "
            "3. Extract all available Points of Measurement (POM) for this single base size only. Provide at least 15-20 fields if present. "
            "4. Extract the 'Style ID' / 'Style Number', 'Category', 'Buyer' name, and fabric details. "
            "5. Detect the exact PAGE INDEX (0-based) containing the pure black and white line art TECHNICAL FLAT SKETCH. "
            "DO NOT pick pages showing summary costing grids, fabric swatch data sheets, or trim lists. "
            "Return a completely valid raw JSON string matching this schema (no markdown blocks): "
            "{\"style_number_parsed\": \"string\", \"buyer\": \"string\", \"category\": \"string\", \"base_size_name\": \"string\", \"measurements\": {}, \"sketch_page_index_detected\": 0}"
        )
        
        pdf_parts_payload.append(industrial_extraction_prompt)
        response = client.models.generate_content(model='gemini-2.5-flash', contents=pdf_parts_payload)
        
        clean_json = response.text.strip().replace("```json", "").replace("```", "").strip()
        parsed_data = json.loads(clean_json)
        
        # Trích xuất ảnh vẽ phẳng sạch dựa trên chỉ số trang AI tìm thấy
        extracted_sketch_bytes = None
        detected_idx = int(parsed_data.get("sketch_page_index_detected", 0))
        if 0 <= detected_idx < len(chat_images):
            b_buf = io.BytesIO()
            chat_images[detected_idx].convert("RGB").save(b_buf, format="JPEG")
            extracted_sketch_bytes = b_buf.getvalue()
            
        # Thực hiện gọi hàm đồng bộ đẩy dữ liệu sạch lên Supabase ngay lập tức
        success_db = save_to_supabase_techpack_table(parsed_data, raw_file_bytes=file_bytes, file_name=file_name)
        
        # 🔥 ĐỒNG BỘ ĐẦU RA CHÍNH XÁC: Đóng gói cả measurements và sketch_bytes trả ngược ra cho luồng hiển thị
        return {
            "success": success_db,
            "style_id": parsed_data.get("style_number_parsed", "UNKNOWN"),
            "size": parsed_data.get("base_size_name", "32"),
            "measurements": parsed_data.get("measurements", {}), # Truyền dữ liệu ma trận thông số đo thực tế
            "sketch_bytes": extracted_sketch_bytes, # Truyền nhị phân ảnh vẽ phẳng rập sạch
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
                            "size": res.get("size", "32"),
                            "measurements": res.get("measurements", {}), # Đóng gói thông số trực tiếp từ lõi PDF
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
                # 🛠️ ĐỒNG BỘ CHUẨN XÁC KHÓA BIẾN: Sửa từ sketch_image sang sketch_bytes để bốc đúng dữ liệu nhị phân ảnh của luồng core
                                mock_data = {
                                    "style_number_parsed": task_res.get("style_id"),
                                    "buyer": "Vineyard Vines", 
                                    "category": "Denim Pants",
                                    "base_size_name": task_res.get("size"),
                                    "measurements": task_res.get("measurements", {}), 
                                    "sketch_image": base64.b64encode(task_res["sketch_bytes"]).decode("utf-8") if task_res.get("sketch_bytes") else "", 
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
                        if data.get("sketch_image"): 
                            try:
                                st.image(base64.b64decode(data["sketch_image"]), use_container_width=True)
                            except Exception:
                                st.info("Không thể dựng bản xem trước hình ảnh.")
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
            extraction_prompt = (
                "Analyze all attached sheets page by page. "
                "1. Locate the core 'Base Size' / 'Sample Size' (e.g., size 32 or size 34 or M). "
                "2. Extract ALL points of measurement (POM) and their corresponding target specs for THIS BASE SIZE ONLY. Extract at least 15-20 measurements if available. "
                "3. Find 'Style ID' / 'Style Number' (e.g., 1P001369) and 'Category'. "
                "4. CRITICAL VISION TASK FOR SKETCH DETECTION: Find the exact 'PAGE INDEX' (starting from 0) that contains the TECHNICAL BLACK AND WHITE FLAT SKETCH / DRAWING. "
                "STRICTLY FORBIDDEN: DO NOT select summary pages containing a large grid table of BOM (Bill of Materials), fabrics itemization, trim sheets, or costing data grids. "
                "Only pick the pure big line art design layout drawing page. "
                "Return a valid raw JSON string with this exact schema (no markdown block): "
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
        # LẤY DỮ LIỆU TỪ BỘ NHỚ KHÓA ĐỂ HIỂN THỊ LÊN MÀN HÌNH
    matched_techpack = st.session_state["matched_techpack"]
    bom_records = st.session_state["bom_records"]

    if matched_techpack:
        target_style_name = matched_techpack.get("StyleName")
        st.success(f"🎯 MỤC ĐÍCH 2: ĐÃ TÌM THẤY MÃ HÀNG TƯƠNG ĐỒNG: **{target_style_name}**")
        
        col1, col2 = st.columns(2)
        with col1: st.image(target_new_sketch_bytes, caption="Bản vẽ phẳng mẫu mới (AI quét sạch)", use_container_width=True)
        with col2: 
            if matched_techpack.get("SketchURL"): st.image(matched_techpack["SketchURL"], caption=f"Ảnh Sketch gốc lưu trong kho: {target_style_name}", use_container_width=True)

        st.subheader("📦 Chi Tiết Định Mức Nguyên Phụ Liệu Gốc trong kho (BOM)")
        if bom_records:
            formatted_bom = []
            for r in bom_records:
                formatted_bom.append({
                    "Mã hàng (Style)": r.get("style_name") if r.get("style_name") else r.get("style_id"),
                    "Tên vật tư": r.get("article_name"),
                    "Chủng loại tiêu hao": r.get("consumption_type"),
                    "Khổ nguyên liệu": r.get("material_size"),
                    "Đơn vị tính": r.get("uom"),
                    "Định mức cơ sở (Kho)": str(r.get("consumption_value")) if r.get("consumption_value") is not None else "EMPTY",
                    "Ghi chú phân xưởng": r.get("notes") if r.get("notes") else "EMPTY"
                })
            st.table(formatted_bom)
            main_fabrics = list(set([r.get("article_name") for r in bom_records if "MAIN" in str(r.get("consumption_type", "")).upper() if r.get("article_name")]))
            if main_fabrics: st.info(f"🧵 Mã vải chính của mã hàng gốc: **{', '.join(main_fabrics)}**")
        else:
            st.warning(f"⚠️ Không tìm thấy dữ liệu phụ liệu cho biến thể mã hàng gốc `{dynamic_keyword}` trong bảng san_pham.")

        # HÀM AI ĐỐI SOÁT TỰ ĐỘNG KHÔNG DÙNG TỪ ĐIỂN CỨNG THỦ CÔNG
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
            with st.spinner("🧠 Trợ lý AI đang tự động quét lập bản đồ đối soát vị trí đo đa chủng loại..."):
                try:
                    mapping_prompt = f"""
                    You are a professional garment pattern grader. Your task is to align and map points of measurement (POM) between an old style spec sheet and a newly scanned spec sheet.
                    The items could be Pants, Shirts, Jackets, Blazers, or Dresses. Avoid cross-aligning circumferences with positions/lengths.
                    OLD SPEC KEYS: {list(specs_old.keys())}
                    NEW SPEC KEYS: {list(specs_new.keys())}
                    Return clean raw JSON with this schema: {{"old_key": "new_key"}}
                    """
                    mapping_res = client.models.generate_content(model='gemini-2.5-flash', contents=mapping_prompt)
                    clean_mapping_json = mapping_res.text.strip().replace("```json", "").replace("```", "").strip()
                    ai_pom_map = json.loads(clean_mapping_json)
                except Exception: ai_pom_map = {}

            comparison_table = []
            deviation_length_pct = 0.0
            deviation_width_pct = 0.0
            has_len = False
            has_wid = False
            
            for original_old_key, old_val in specs_old.items():
                if original_old_key in ai_pom_map:
                    corresponding_new_key = ai_pom_map[original_old_key]
                    new_val_str = specs_new.get(corresponding_new_key, "0")
                    v_old = parse_fraction(old_val)
                    v_new = parse_fraction(new_val_str)
                    if v_old > 0 and v_new > 0:
                        diff = v_new - v_old
                        pct_diff = (diff / v_old) * 100
                        k_upper = original_old_key.upper()
                        
                        if any(word in k_upper for word in ["INSEAM", "OUTSEAM", "LENGTH", "CB", "CF", "DÀI"]):
                            if pct_diff != 0: deviation_length_pct = pct_diff; has_len = True
                        if any(word in k_upper for word in ["HIP", "CHEST", "BUST", "THIGH", "WAIST", "NGỰC", "EO", "MÔNG", "WIDTH"]):
                            if pct_diff != 0: deviation_width_pct = pct_diff; has_wid = True
                                
                        comparison_table.append({"Vị trí đo (POM)": original_old_key, "Thông số gốc (Kho)": f"{old_val}\"", "Thông số mới (Quét)": f"{new_val_str}\"", "Chênh lệch": f"{diff:+.3f}\"", "Tỷ lệ biến động": f"{pct_diff:+.1f}%"})
            
            # 🚀 N N CẤP THỊ THỊ HÀNG NGANG CHIA THÀNH 3 CỘT ĐỘC LẬP ĐỂ HIỂN THỊ ĐẦY ĐỦ THÔNG SỐ TRONG KHO
            ui_col1, ui_col2, ui_col3 = st.columns([1.0, 0.5, 0.5])
            with ui_col1:
                st.subheader("📊 Bảng Đối Soát Sai Lệch Hình Học")
                if comparison_table: st.table(comparison_table)
            with ui_col2:
                # 🎯 THÀNH QUẢ YÊU CẦU 2: Bung ra toàn bộ tất cả thông số hiện có trong kho dữ liệu Supabase của mã tương đồng
                st.subheader("🏛️ Dữ liệu gốc lưu trong Kho")
                st.table([{"Vị trí đo (Gốc)": k, "Thông số kho": v} for k, v in specs_old.items()])
            with ui_col3:
                st.subheader("📋 Thông số mẫu mới quét được")
                st.table([{"Vị trí đo (Quét sạch)": k, "Thông số quét": v} for k, v in specs_new.items()])
                
            if has_len or has_wid:
                factor_len = 1.0 + (deviation_length_pct / 100.0)
                factor_wid = 1.0 + (deviation_width_pct / 100.0)
                total_area_deviation_pct = (factor_len * factor_wid - 1.0) * 100
                st.markdown(f"💡 **Phân tích hình học rập mẫu tự động bởi AI:**")
                st.write(f"- Biến động chiều dài thân rập chủ đạo: **{deviation_length_pct:+.1f}%**")
                st.write(f"- Biến động chiều rộng thân rập chủ đạo: **{deviation_width_pct:+.1f}%**")
                st.markdown(f"🎯 **Tỷ lệ biến động diện tích khối sơ đồ vải thực tế (Marker Area Deviation): {total_area_deviation_pct:+.1f}%**")
                new_style_base_size = f"{new_style_base_size} (Marker Area Delta: {total_area_deviation_pct:+.2f}%)"
    elif has_file:
        st.warning("⚠️ MỤC ĐÍCH 3: MÃ HÀNG HOÀN TOÀN MỚI - KHÔNG TÌM THẤY MÃ TƯƠNG ĐỒNG TRONG KHO!")
        st.info("💡 AI đã tự động kích hoạt tính năng Hình học không gian (Geometric Surface Area Estimation). Vui lòng ra lệnh ở ô chat bên dưới để tính định mức sơ đồ ban đầu.")
        st.subheader("📋 Trọn bộ thông số mẫu mới quét được")
        st.table([{"Vị trí đo (Quét sạch)": k, "Thông số quét": v} for k, v in new_style_measurements_dict.items()])

    # GIAO DIỆN KHUNG CHAT PHÂN TÍCH LIÊN KẾT CHATGPT STYLE
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

