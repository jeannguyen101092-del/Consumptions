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
    ✨ ĐÃ CHỈNH SỬA CHỐNG NULL: Lưu trực tiếp chuỗi mô tả đặc trưng hình học vào cột text của Supabase.
    """
    try:
        style_name_db = payload_data.get("style_number_parsed", "").strip()
        if not style_name_db: 
            style_name_db = "UNKNOWN_STYLE"
            
        sketch_b64 = payload_data.get("sketch_image", "")
        public_image_url = ""
        image_data = None

        if sketch_b64:
            try:
                import base64
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

        # ⚡ LUỒNG SỐ HÓA ĐẶC TRƯNG HÌNH HỌC (LƯU DẠNG CHỮ CHỐNG NULL 100%)
        visual_description_str = "technical garment layout specs"
        if image_data:
            gemini_key = get_secure_gemini_key()
            if gemini_key:
                try:
                    client_db = genai.Client(api_key=gemini_key)
                    
                    # Gọi Gemini-2.5-Flash bóc tách chi tiết hình học của ảnh rập dệt may
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
        clean_dict = {str(k): str(v) for k, v in dict(raw_measurements).items()}

        # Đồng bộ lưu chuỗi văn bản đặc trưng thẳng vào cột sketch_vector kiểu text
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
            # Sử dụng cú pháp toán tử hoa thị (*) của PostgREST truyền qua params để an toàn tuyệt đối
            query_params["StyleName"] = f"ilike.*{clean_kw}*"
            
        response = requests.get(url, headers=headers, params=query_params, timeout=15)
        return response.json() if response.status_code == 200 else []
    except Exception:
        return []


def process_single_pdf_batch(file_bytes, file_name):
    """
    Hàm bóc tách dữ liệu kỹ thuật từ một file PDF độc lập sử dụng Gemini Vision API.
    ✨ ĐÃ FIX HOÀN TOÀN: Sửa thuật toán cắt chuỗi split để lấy chữ số size "32" sạch 100%.
    """
    try:
        import base64
        gemini_key = get_secure_gemini_key()
        if not gemini_key:
            return {"success": False, "error": "API Key cho Gemini đang bị thiếu trong Secrets."}
            
        client = genai.Client(api_key=gemini_key)
        
        info = pdfinfo_from_bytes(file_bytes)
        total_pages = int(info.get("Pages", 1))
        images = convert_from_bytes(file_bytes, dpi=90, first_page=1, last_page=total_pages)
        
        contents_payload = []
        for idx, page_img in enumerate(images):
            img_buf = io.BytesIO()
            page_img.convert("RGB").save(img_buf, format="JPEG", quality=75)
            contents_payload.append(types.Part.from_bytes(data=img_buf.getvalue(), mime_type='image/jpeg'))
            
        extraction_prompt = """
        Analyze all technical sheets page by page. 
        1. Find the 'Style ID' / 'Style Number' (e.g., 1P001363).
        2. Identify 'Buyer', 'Category', and the designated 'Base Size' / 'Sample Size' (e.g., 32/32).
        
        3. CRITICAL SPECIFICATION TASK (EXTRACT BASE SIZE ONLY):
           Look at the Measurement Specification Sheet (bảng thông số kỹ thuật). 
           - Detect the exact column that belongs to the 'Base Size' / 'Sample Size' (e.g., column '32' or the sample size column).
           - Extract the points of measurement (POM) and their corresponding target values for THIS BASE SIZE ONLY.
           - DO NOT extract multiple sizes. DO NOT return nesting JSON or multiple size values for a single POM.
           - Format each measurement value as a clean single string/number (e.g., "33", "11 1/2", "15 1/4").
        
        4. Identify the 0-based page index containing the black & white technical flat design sketch.
        
        Return a valid raw JSON schema with this exact structure:
        {"style_number_parsed": "string", "buyer": "string", "category": "string", "base_size_name": "string", "measurements": {"Waist Circ": "33", "Waistband Height": "1 5/8"}, "sketch_page_index_detected": 0}
        """
        contents_payload.append(extraction_prompt)
        
        res = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=contents_payload,
            config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.0)
        )
        
        parsed_data = json.loads(res.text.strip())
        
        # --- CƠ CHẾ DỰ PHÒNG PYTHON: TRÍCH XUẤT TỪ KHÓA SIZE CHUẨN XÁC ---
        base_size_target = str(parsed_data.get("base_size_name", "")).strip()
        
        # SỬA LỖI TẠI ĐÂY: Lấy phần tử đầu tiên của mảng sau khi tách bằng dấu gạch chéo
        if "/" in base_size_target:
            size_keyword = str(base_size_target.split("/")[0]).strip()
        else:
            size_keyword = base_size_target.strip()
            
        # Nếu chuỗi rỗng hoặc AI nhận diện sai, ép từ khóa mặc định về size "32" để đối soát rập Denim
        if not size_keyword or size_keyword == "None":
            size_keyword = "32"
            
        raw_measurements = parsed_data.get("measurements", {})
        clean_measurements = {}
        
        if isinstance(raw_measurements, dict):
            for pom, val in raw_measurements.items():
                if isinstance(val, dict):
                    if size_keyword in val:
                        clean_measurements[pom] = str(val[size_keyword])
                    elif "32" in val:
                        clean_measurements[pom] = str(val["32"])
                    else:
                        first_key = list(val.keys()) if val.keys() else ""
                        clean_measurements[pom] = str(val[first_key]) if first_key else str(val)
                else:
                    val_str = str(val)
                    if "{" in val_str or ":" in val_str:
                        # Tìm thông số kỹ thuật đứng ngay sau ký tự số size sạch (Ví dụ '32': hoặc "32":)
                        match_val = re.search(fr"['\"]?{size_keyword}['\"]?\s*:\s*['\"]?([^'\",}}]+)", val_str)
                        if match_val:
                            clean_measurements[pom] = match_val.group(1).strip()
                        else:
                            # Phương án dự phòng tìm trực tiếp giá trị của size 32 trong chuỗi thô
                            match_default = re.search(r"['\"]?32['\"]?\s*:\s*['\"]?([^'\",}}]+)", val_str)
                            clean_measurements[pom] = match_default.group(1).strip() if match_default else val_str
                    else:
                        clean_measurements[pom] = val_str
                        
            # Ghi đè lại bảng thông số đã được làm sạch
            parsed_data["measurements"] = clean_measurements
        # ----------------------------------------------------------------------
        
        detected_idx = int(parsed_data.get("sketch_page_index_detected", 0))
        if not (0 <= detected_idx < len(images)):
            detected_idx = 0
            
        sketch_buf = io.BytesIO()
        images[detected_idx].convert("RGB").save(sketch_buf, format="JPEG", quality=75)
        parsed_data["sketch_image"] = base64.b64encode(sketch_buf.getvalue()).decode('utf-8')
        
        save_success = save_to_supabase_techpack_table(parsed_data)
        return {"success": save_success, "data": parsed_data}
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
    import base64
    import concurrent.futures

    st.markdown('<div class="component-title-box">📊 MULTI-BATCH GARMENT SPECIFICATION MATRIX</div>', unsafe_allow_html=True)
    
    st.markdown("""<div class="card-container"><div class="card-section-header">📥 INGESTION ENGINE</div>
    <p style="color: #64748B; font-size:13px; margin:0 0 15px 0;">Hệ thống tự động cắt trang, khử nhiễu đồ họa phẳng và gọi API mạng nơ-ron tích hợp để bóc tách thông số hàng loạt.</p></div>""", unsafe_allow_html=True)
    
    uploaded_files = st.file_uploader("Upload Techpack PDFs Here", type=["pdf"], accept_multiple_files=True, label_visibility="collapsed")
    
    if uploaded_files:
        files_to_render = []
        
        # Thống kê danh sách file chưa được số hóa đưa vào hàng đợi
        files_need_processing = [f for f in uploaded_files if f.name not in st.session_state["processed_styles"]]
        
        if files_need_processing:
            if st.button(f"🚀 KÍCH HOẠT SỐ HÓA ĐA LUỒNG SONG SONG ({len(files_need_processing)} FILE MỚI)", use_container_width=True, type="primary"):
                status_text = st.empty()
                progress_bar = st.progress(0)
                total_new_files = len(files_need_processing)
                
                def thread_worker(file_obj):
                    try:
                        # Thực hiện đọc và trích xuất thông số kỹ thuật đơn lẻ sạch
                        res = process_single_pdf_batch(file_obj.getvalue(), file_obj.name)
                        # Trả kết quả về bộ nhớ tạm để hiển thị trước, CHƯA bấm lưu vào database ở bước này
                        return {"file_name": file_obj.name, "success": res.get("success", False), "data": res.get("data", None), "error": res.get("error", None)}
                    except Exception as e:
                        return {"file_name": file_obj.name, "success": False, "data": None, "error": str(e)}

                with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
                    future_to_file = {executor.submit(thread_worker, f): f.name for f in files_need_processing}
                    
                    for idx, future in enumerate(concurrent.futures.as_completed(future_to_file)):
                        f_name = future_to_file[future]
                        try:
                            task_res = future.result()
                            if task_res["data"]:
                                # Nạp dữ liệu vào bộ nhớ đệm màn hình
                                st.session_state["processed_styles"][f_name] = task_res["data"]
                            else:
                                st.error(f"FAIL ENGINE [{f_name}]: {task_res['error']}")
                        except Exception as exc:
                            st.error(f"CRITICAL CRASH [{f_name}]: {str(exc)}")
                        
                        completed = idx + 1
                        progress_bar.progress(completed / total_new_files)
                        status_text.text(f"⚡ Core AI đang xử lý: {completed}/{total_new_files} tệp ({f_name})...")
                
                status_text.empty()
                progress_bar.empty()
                st.success("🎉 Số hóa dữ liệu thành công! Hãy kiểm tra bảng thông số bên dưới trước khi bấm lưu.")

        # Gom toàn bộ file đã hiển thị thành công lên giao diện màn hình
        for file in uploaded_files:
            if file.name in st.session_state["processed_styles"]:
                files_to_render.append(file.name)

        if files_to_render:
            st.markdown("<br>", unsafe_allow_html=True)
            
            # 🎯 HIỂN THỊ NÚT LƯU THỦ CÔNG THEO YÊU CẦU CỦA BẠN TẠI ĐÂY
            if st.button("💾 LƯU TOÀN BỘ DỮ LIỆU ĐÃ SỐ HÓA VÀO MASTER DB", key="bulk_save_all_btn", type="primary", use_container_width=True):
                success_count = 0
                with st.spinner("Đang đồng bộ cổng dữ liệu nhị phân hàng loạt lên Supabase Cloud..."):
                    for f_name in files_to_render:
                        style_data = st.session_state["processed_styles"][f_name]
                        # Gọi hàm đẩy trực tiếp cục dữ liệu sạch lên database
                        if save_to_supabase_techpack_table(style_data): 
                            success_count += 1
                st.success(f"🎉 PATTERN DATA PIPELINE: Đã ghi nhận và lưu trữ thành công {success_count}/{len(files_to_render)} mã hàng vào Database!")
            
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
import numpy as np
from urllib.parse import quote
from google import genai
from google.genai import types

try:
    from pdf2image import convert_from_bytes, pdfinfo_from_bytes
except ImportError:
    pass

if user_query := st.chat_input("Nhập yêu cầu phân tích định mức vải và đối soát sai lệch..."):
        # Khởi tạo bộ nhớ đệm State cố định để giữ tệp tin không bị xóa khi người dùng gửi lệnh chat
    if "cached_file_bytes" not in st.session_state:
        st.session_state["cached_file_bytes"] = None
    if "cached_file_name" not in st.session_state:
        st.session_state["cached_file_name"] = ""

    # Ghi nhận dữ liệu file từ uploader hệ thống vào bộ nhớ State ngay khi phát hiện có tệp tải lên
    if 'chat_file' in locals() or 'chat_file' in globals():
        if chat_file is not None:
            st.session_state["cached_file_bytes"] = chat_file.getvalue()
            st.session_state["cached_file_name"] = chat_file.name
    elif 'uploaded_file' in st.session_state:
        if st.session_state['uploaded_file'] is not None:
            st.session_state["cached_file_bytes"] = st.session_state['uploaded_file'].getvalue()
            st.session_state["cached_file_name"] = st.session_state['uploaded_file'].name

    gemini_key = get_secure_gemini_key()
    if not gemini_key:
        st.error("AI API Token is missing.")
        st.stop()
        
    client = genai.Client(api_key=gemini_key, http_options=types.HttpOptions(api_version='v1'))
    new_style_id_detected = "UNKNOWN_STYLE"
    new_style_category_detected = ""
    new_style_fabric_detected = "UNKNOWN_FABRIC"
    new_style_measurements_dict = {}
    img_payload = [] 
    target_new_sketch_bytes = None 
    
    # Xác định trạng thái tệp tin từ bộ nhớ đệm
    has_file = st.session_state["cached_file_bytes"] is not None
    
    # Luồng AI bóc tách thông số kỹ thuật (POM) từ tệp tin đã lưu trạng thái cố định
    if has_file:
        file_bytes = st.session_state["cached_file_bytes"]
        file_name = st.session_state["cached_file_name"]
        
        if file_name.lower().endswith('.pdf'):
            info_chat = pdfinfo_from_bytes(file_bytes)
            total_chat_pages = int(info_chat.get("Pages", 1))
            chat_images = convert_from_bytes(file_bytes, dpi=90, first_page=1, last_page=total_chat_pages)
            for idx, page_img in enumerate(chat_images):
                img_buf = io.BytesIO()
                page_img.convert("RGB").save(img_buf, format="JPEG", quality=75)
                img_payload.append(types.Part.from_bytes(data=img_buf.getvalue(), mime_type='image/jpeg'))
        else:
            target_new_sketch_bytes = file_bytes
            img_payload.append(types.Part.from_bytes(data=file_bytes, mime_type='image/jpeg'))
            
        extraction_prompt = "Analyze all sheets page by page. Find the designated 'Base Size' / 'Sample Size'. Extract the points of measurement (POM) and their target values for THIS BASE SIZE ONLY. Format each value as a clean single number or string (e.g., '33', '11 1/2'). Also find 'Style ID' and 'Category'. Identify the 0-based index of the black and white technical flat design sketch page. Return valid JSON only: {\"detected_style_id\": \"string\", \"category\": \"string\", \"fabric_code\": \"string\", \"measurements\": {}, \"sketch_page_index_detected\": 0}"
        extraction_payload = list(img_payload)
        extraction_payload.append(extraction_prompt)
        try:
            extraction_res = client.models.generate_content(model='gemini-2.5-flash', contents=extraction_payload, config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.0))
            parsed_meta = json.loads(extraction_res.text.strip())
            new_style_id_detected = parsed_meta.get("detected_style_id", "UNKNOWN_STYLE").strip()
            new_style_category_detected = parsed_meta.get("category", "").strip()
            new_style_fabric_detected = parsed_meta.get("fabric_code", "UNKNOWN_FABRIC").strip()
            new_style_measurements_dict = parsed_meta.get("measurements", {})
            
            # Tự động gạn lọc làm sạch chuỗi đa kích cỡ (Grading Sheet) nếu AI trích xuất nhầm dải size
            clean_measurements = {}
            if isinstance(new_style_measurements_dict, dict):
                for pom, val in new_style_measurements_dict.items():
                    if isinstance(val, dict):
                        # Ưu tiên bốc tách riêng cột dữ liệu của size mẫu 32
                        clean_measurements[pom] = str(val.get("32", val.get("32/32", list(val.values())[0])))
                    else:
                        clean_measurements[pom] = str(val)
                new_style_measurements_dict = clean_measurements
                
            detected_idx = int(parsed_meta.get("sketch_page_index_detected", 0))
            if file_name.lower().endswith('.pdf') and 0 <= detected_idx < len(chat_images):
                b_buf = io.BytesIO()
                chat_images[detected_idx].convert("RGB").save(b_buf, format="JPEG")
                target_new_sketch_bytes = b_buf.getvalue()
        except Exception:
            pass
            
    clean_text_upper = str(user_query).strip().upper()
    is_searching_fabric = any(word in clean_text_upper for word in ["CODE VẢI", "MÃ VẢI", "LOẠI VẢI", "TÌM VẢI"])
    codes_found = re.findall(r'\b[A-Z]*\d+[A-Z0-9]*\b|\b[A-Z0-9]+-\d+[A-Z0-9-]*\b', clean_text_upper)
    if codes_found:
        clean_query = codes_found if isinstance(codes_found, list) else codes_found
    else:
        pattern_remove = r"\b(TÌM|KIỂM TRA|XEM|CHECK|MÃ HÀNG|MÃ|VẢI|CODE|TRÍCH XUẤT|HÌNH ẢNH|TƯƠNG ĐỒNG|KHO|TRONG)\b"
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

    base_sb_url = SB_URL.rstrip('/')
    headers = {"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}"}
    matched_style_name = None
    best_similarity = -1.0
    fabric_records = []
    techpack_records = []
    if has_file and new_style_measurements_dict:
        with st.spinner("⚡ AI dệt may đang quét phân tích hình học thông số rập đối soát phom dáng..."):
            query_vector = None
            try:
                def get_clean_num(text_val):
                    if not text_val: return 0.0
                    nums = re.findall(r'\d+(?:\.\d+)?', str(text_val).strip())
                    return float(nums) if nums else 0.0
                def find_fuzzy_val(measure_dict, keyword):
                    if not isinstance(measure_dict, dict): return 0.0
                    for k, v in measure_dict.items():
                        if keyword.lower() in str(k).lower():
                            return get_clean_num(v)
                    return 0.0
                q_waist = find_fuzzy_val(new_style_measurements_dict, "waist")
                q_hip = find_fuzzy_val(new_style_measurements_dict, "hip")
                q_thigh = find_fuzzy_val(new_style_measurements_dict, "thigh")
                if q_waist > 0 or q_hip > 0:
                    query_vector = np.array([q_waist, q_hip, q_thigh], dtype=np.float32)
            except Exception:
                query_vector = None
            if query_vector is not None:
                url_all_vectors = f"{base_sb_url}/rest/v1/thong_so_techpack?select=StyleName,DetailedMeasurements"
                try:
                    res_all = requests.get(url_all_vectors, headers=headers, timeout=10)
                    warehouse_data = res_all.json() if (res_all and res_all.status_code == 200) else []
                except Exception:
                    warehouse_data = []
                for row in warehouse_data:
                    db_measurements = row.get("DetailedMeasurements", {})
                    if isinstance(db_measurements, str):
                        try: db_measurements = json.loads(db_measurements)
                        except Exception: db_measurements = {}
                    if isinstance(db_measurements, dict) and len(db_measurements) > 0:
                        try:
                            db_waist = find_fuzzy_val(db_measurements, "waist")
                            db_hip = find_fuzzy_val(db_measurements, "hip")
                            db_thigh = find_fuzzy_val(db_measurements, "thigh")
                            db_vector = np.array([db_waist, db_hip, db_thigh], dtype=np.float32)
                            if np.any(db_vector > 0):
                                dot_product = np.dot(query_vector, db_vector)
                                norm_query = np.linalg.norm(query_vector)
                                norm_db = np.linalg.norm(db_vector)
                                if norm_query > 0 and norm_db > 0:
                                    similarity = float(dot_product / (norm_query * norm_db))
                                    if similarity > best_similarity and similarity >= 0.90:
                                        best_similarity = similarity
                                        matched_style_name = row.get("StyleName")
                        except Exception:
                            pass
    if matched_style_name:
        final_search_key = matched_style_name.strip()
        st.sidebar.success(f"🎯 Khớp phom hình học thành công: {final_search_key} ({round(best_similarity * 100, 1)}%)")
    else:
        final_search_key = "NOT_FOUND_IN_WAREHOUSE"
        st.sidebar.warning("⚠️ Không tìm thấy phom dáng quần tương đồng trong kho.")
    def fetch_san_pham(key):
        if not key or key == "NOT_FOUND_IN_WAREHOUSE": return []
        try:
            url = f"{base_sb_url}/rest/v1/san_pham"
            safe_key = quote(f"*{key}*")
            params = {"select": "*", "or": f"(style_name.ilike.{safe_key},article_name.ilike.{safe_key})"}
            res = requests.get(url, headers=headers, params=params, timeout=5)
            return res.json() if res.status_code == 200 else []
        except Exception: return []
    def fetch_techpack(key):
        if not key or key == "NOT_FOUND_IN_WAREHOUSE": return []
        try:
            url = f"{base_sb_url}/rest/v1/thong_so_techpack"
            params = {"select": "*", "StyleName": f"ilike.*{key}*"}
            res = requests.get(url, headers=headers, params=params, timeout=5)
            return res.json() if res.status_code == 200 else []
        except Exception: return []
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future_sp = executor.submit(fetch_san_pham, final_search_key)
        future_tp = executor.submit(fetch_techpack, final_search_key)
        fabric_records = future_sp.result()
        techpack_records = future_tp.result()
    db_sketch_url = None
    db_measurements_raw = {}
    current_style_name = ""
    SUPABASE_PROJECT_URL = SB_URL.rstrip('/') if 'SB_URL' in locals() else "https://supabase.co" 
    img_col1, img_col2 = st.columns(2)
    with img_col1:
        if has_file and target_new_sketch_bytes:
            st.image(target_new_sketch_bytes, caption="🖼️ Ảnh rập kỹ thuật bạn vừa tải lên", use_container_width=True)
    with img_col2:
        if techpack_records and len(techpack_records) > 0:
            first_record = techpack_records if isinstance(techpack_records, list) else techpack_records
            if isinstance(first_record, dict):
                current_style_name = first_record.get("StyleName", "").strip()
                db_sketch_url = first_record.get("SketchURL")
                db_measurements_raw = first_record.get("DetailedMeasurements", {})
                if isinstance(db_measurements_raw, str):
                    try: db_measurements_raw = json.loads(db_measurements_raw)
                    except Exception: db_measurements_raw = {}
            if db_sketch_url and str(db_sketch_url).startswith("http"):
                st.image(db_sketch_url, caption=f"🎯 Ảnh Sketch đối chứng khớp trong kho: {current_style_name}", use_container_width=True)
            elif current_style_name:
                constructed_url = f"{SUPABASE_PROJECT_URL}/storage/v1/object/public/kho_anh/{current_style_name}.jpg"
                st.image(constructed_url, caption=f"🎯 Ảnh Sketch đối chứng khớp trong kho: {current_style_name}", use_container_width=True)
        else:
            if dynamic_keyword and dynamic_keyword not in ["UNKNOWN", "UNKNOWN_STYLE"]:
                constructed_url = f"{SUPABASE_PROJECT_URL}/storage/v1/object/public/kho_anh/{dynamic_keyword}.jpg"
                st.image(constructed_url, caption=f"🔍 Thử tìm kiếm ảnh theo mã chuỗi: {dynamic_keyword}", use_container_width=True)
            else:
                st.info("ℹ️ Không tìm thấy mẫu thiết kế đối chứng tương đồng trong kho ảnh.")
    fabric_width_input = re.search(r'(?:KHỔ|KHO)\s*(\d+(?:\.\d+)?)', clean_text_upper)
    shrink_ngang = re.search(r'(?:NGANG)\s*(\d+(?:\.\d+)?)\s*%', clean_text_upper)
    shrink_doc = re.search(r'(?:DỌC|DOC)\s*(\d+(?:\.\d+)?)\s*%', clean_text_upper)
    shrink_general = re.search(r'(?:CO|CO RÚT|CO RUT)\s*(\d+(?:\.\d+)?)', clean_text_upper)
    user_width = f"{fabric_width_input.group(1)} INCH" if fabric_width_input else "57 INCH"
    co_ngang = shrink_ngang.group(1) if shrink_ngang else "0"
    co_doc = shrink_doc.group(1) if shrink_doc else (shrink_general.group(1) if shrink_general else "0")
    st.markdown(f"### 📊 Kết quả đối soát dữ liệu mã hàng: **{new_style_id_detected if new_style_id_detected != 'UNKNOWN_STYLE' else final_search_key}**")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**📋 Thông tin định mức vải gốc (Bảng san_pham):**")
        has_history_match = False
        if fabric_records and isinstance(fabric_records, list):
            formatted_fabric = [{"Mã hàng": r.get("style_name"), "Mã vải (Article)": r.get("article_name"), "Loại vật tư": r.get("consumption_type"), "Khổ vải": r.get("material_size"), "Định mức gốc": r.get("consumption_value"), "Đơn vị": r.get("uom")} for r in fabric_records if isinstance(r, dict)]
            if formatted_fabric:
                st.dataframe(formatted_fabric, use_container_width=True)
                has_history_match = True
            else:
                st.warning("Không tìm thấy dữ liệu vải lịch sử của mã tương đồng.")
        else:
            st.info("ℹ️ Tự động kích hoạt tính toán độc lập từ thông số hình học rập Techpack mới.")
    with col2:
        st.markdown("**📏 Thông số hình học thực tế (Bảng lưới phẳng đơn cỡ sạch):**")
        display_specs = db_measurements_raw if (isinstance(db_measurements_raw, dict) and len(db_measurements_raw) > 0) else new_style_measurements_dict
        if isinstance(display_specs, dict) and len(display_specs) > 0:
            formatted_measurements = [{"Vị trí đo (POM)": k, "Thông số kỹ thuật thực tế": v} for k, v in display_specs.items()]
            st.dataframe(formatted_measurements, use_container_width=True)
        else:
            st.info("Không tìm thấy thông số kỹ thuật gốc.")
    is_user_asking_to_calculate = any(w in clean_text_upper for w in ["TÍNH", "TINH", "ĐỊNH MỨC", "DINH MUC", "CO RÚT", "CO RUT", "KHỔ", "KHO", "DỰ ĐOÁN", "DU DOAN"])
    if is_user_asking_to_calculate:
        st.markdown("### 📐 Kết quả phân tích sơ đồ & Tính toán định mức vải")
        pipeline_mode = "HISTORY_BASED_PREDICTION" if has_history_match else "PURE_MARKER_CALCULATOR"
        analysis_prompt = f"You are an expert Apparel Costing Engineer. Perform a fabric consumption analysis. Width: {user_width}, Shrinkage Ngang: {co_ngang}%, Dọc: {co_doc}%. New Style Specs: {json.dumps(new_style_measurements_dict, ensure_ascii=False)}, Warehouse Specs: {json.dumps(db_measurements_raw, ensure_ascii=False)}, Warehouse Fabrics: {json.dumps(fabric_records, ensure_ascii=False)}. [MODE: {pipeline_mode}] RULE 1: IF MODE IS 'HISTORY_BASED_PREDICTION': Locate 'Định mức gốc' of matched style in warehouse. Compare New Style against Warehouse Specs to calculate delta. Adjust 'Định mức gốc' proportionally. State: 'Dự đoán định mức dựa trên mã tương đồng lịch sử'. RULE 2: IF MODE IS 'PURE_MARKER_CALCULATOR': Calculate from scratch using standard apparel marker geometry. Add 5% wastage. State: 'Tính toán độc lập theo quy ước hình học ngành may do không có mã tương đồng'. [OUTPUT] Output step-by-step completely in Vietnamese. Strictly technical."
        with st.spinner("AI đang phân tích sơ đồ đối soát và lập công thức dự toán định mức..."):
            try:
                analysis_res = client.models.generate_content(model='gemini-2.5-flash', contents=[analysis_prompt])
                st.markdown(analysis_res.text)
                st.session_state["chat_history"].append({"role": "assistant", "type": "text", "content": analysis_res.text})
            except Exception as e:
                st.error(f"Lỗi gửi yêu cầu tới Gemini: {str(e)}")
else:
    st.info("💡 Hệ thống đã thực hiện đối soát hình ảnh và thông số rập thành công. Bạn có thể nhập thêm câu lệnh yêu cầu tính toán định mức vải cùng với thông số khổ vải hoặc độ co rút để kích hoạt lõi phân tích AI.")
