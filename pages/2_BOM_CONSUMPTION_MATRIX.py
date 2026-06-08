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
    .card-section-header { font-size: 14px; font-weight: 700; color: #1E3A8A; margin-bottom: 8px; text-transform: uppercase; }
    .tech-card-header { font-size: 16px; font-weight: 800; color: #1E3A8A; margin-bottom: 12px; border-bottom: 2px solid #3B82F6; padding-bottom: 4px; }
    
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
SB_URL = "https://supabase.co"
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
            kw_raw = str(search_keyword).strip().upper()
            kw_clean = kw_raw.replace("-", "").replace(" ", "")
            
            letters = "".join(re.findall(r'[A-Z]+', kw_clean))
            digits = "".join(re.findall(r'\d+', kw_clean))
            
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
    """
    try:
        headers = {
            "apikey": SB_KEY, 
            "Authorization": f"Bearer {SB_KEY}"
        }
        url = f"{SB_URL.rstrip('/')}/rest/v1/thong_so_techpack"
        
        query_params = {
            "select": "StyleName,Buyer,Category,BaseSize,DetailedMeasurements,SketchURL",
            "limit": 500
        }
        
        if style_name_keyword:
            clean_kw = str(style_name_keyword).strip()
            query_params["StyleName"] = f"ilike.*{clean_kw}*"
            
        response = requests.get(url, headers=headers, params=query_params, timeout=15)
        return response.json() if response.status_code == 200 else []
    except Exception:
        return []


def process_single_pdf_batch(file_bytes, file_name):
    """
    Hàm bóc tách dữ liệu kỹ thuật từ một file PDF độc lập sử dụng Gemini Vision API.
    ✨ ĐỒNG BỘ: Định dạng Prompt đầu ra trùng khớp 100% với cấu trúc trường của Trợ lý Định mức.
    """
    try:
        gemini_key = get_secure_gemini_key()
        if not gemini_key:
            return {"success": False, "error": "API Key cho Gemini đang bị thiếu trong Secrets."}
            
        client = genai.Client(api_key=gemini_key)
        
        info = pdfinfo_from_bytes(file_bytes)
        total_pages = int(info.get("Pages", 1))
        images = convert_from_bytes(file_bytes, dpi=140, first_page=1, last_page=total_pages)
        
        contents_payload = []
        for img in images:
            img_buf = io.BytesIO()
            img.convert("RGB").save(img_buf, format="JPEG")
            contents_payload.append(types.Part.from_bytes(data=img_buf.getvalue(), mime_type='image/jpeg'))
            
        prompt = """
        You are an expert garment technical auditor. Analyze this Techpack image page by page.
        1. Extract the genuine 'Style ID' / 'Style Number' / 'Mã hàng'.
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
        
        if images:
            thumb_buf = io.BytesIO()
            images[0].convert("RGB").save(thumb_buf, format="JPEG")
            parsed_data["sketch_image"] = base64.b64encode(thumb_buf.getvalue()).decode("utf-8")
            
        return {"success": True, "data": parsed_data}
    except Exception as e:
        return {"success": False, "error": str(e)}
# PHASE 5: USER INTERFACE STRUCTURE & AUTOMATION FACTORY 
# =============================================================================
def execute_consumption_ai_logic(client, user_query, new_style_raw_text, historical_context, contents_payload, techpack_matches):
    """Hàm độc lập xử lý chuỗi Prompt dệt may và gọi API Gemini để tránh lỗi thụt lề khi chia đoạn"""
    fabric_expert_prompt = f"""
    You are the Master Textile R&D Engine at PPJ Group. Your task is to calculate fabric consumption based on the user's specific request, garment measurements, and production constraints.

    [USER PRODUCTION CONSTRAINTS & REQUEST]
    User Query: {user_query}
    New Ingested Style Raw Text/Specs (if any): {new_style_raw_text}

    [HISTORICAL MASTER DATABASE CONTEXT]
    {json.dumps(historical_context, ensure_ascii=False, indent=2)}

    [CRITICAL INFERENCE LOGIC RULES]
    1. CLONE IDENTITY DETECTION: Check 'techpack_database_records' and 'historical_consumption_records'. If they contain data, a historical match IS FOUND.
    2. IF HISTORICAL REFERENCE MATCH IS FOUND:
       - Compare the specs of the new style with the historical style specs.
       - Extract the historical 'consumption_value'.
       - Apply math conversion scaling based on: Target Fabric Width (Khổ vải, e.g., 56 inch) and Target Fabric Shrinkage (Độ co, e.g., ngang 5% dọc 5%).
       - Calculate mathematically: New Consumption = Historical Consumption * (1 + Shrinkage_Vertical/100) * (Historical_Width / Target_Width).
    3. IF NO REFERENCE MATCH IS FOUND: You must calculate from scratch using industrial marker geometry formulas:
       - For Tops/Jackets: Consumption = [((Garment Length + Sleeve Length + Allowances) * (1/2 Chest Width + Seam)) / Target Useable Width] * 2 * (1 + Shrinkage_Vertical/100) * 1.05 (Waste).
       - For Bottoms/Pants: Consumption = [((Pants Outseam Length + Allowances) * (1/4 Hip Width + Seam)) / Target Useable Width] * 4 * (1 + Shrinkage_Vertical/100) * 1.05 (Waste).
       - Provide the formula steps step-by-step. Do not state you lack data.

    [OUTPUT FORMAT SPECIFICATION]
    - Clearly state if a historical matching style was found or calculated from standard garment formulas.
    - List out the reference StyleName, Buyer and historical consumption if found.
    - Print the step-by-step calculation breakdown for the new predicted consumption value and UOM.
    - Answer strictly and directly in Vietnamese. No chatty preamble or unnecessary greetings.
    """
    
    ai_payload = []
    if contents_payload:
        ai_payload.append(contents_payload)
    ai_payload.append(fabric_expert_prompt)

    ai_response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=ai_payload
    )
    
    ans = ai_response.text.strip()
    
    detected_sketch_url = ""
    detected_title = ""
    if techpack_matches and isinstance(techpack_matches, list) and len(techpack_matches) > 0:
        first_match = techpack_matches[0]
        detected_sketch_url = first_match.get("SketchURL", "")
        detected_title = first_match.get("StyleName", "Historical Reference")

    if detected_sketch_url:
        st.session_state["chat_history"].append({
            "role": "assistant", 
            "type": "visual", 
            "content": ans, 
            "image_url": detected_sketch_url,
            "style_title": detected_title
        })
    else:
        st.session_state["chat_history"].append({
            "role": "assistant", 
            "type": "text", 
            "content": ans
        })
    st.rerun()

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
            # =============================================================================
            # ĐOẠN 3B: THUẬT TOÁN ĐỐI SOÁT PHÂN SỐ DỆT MAY & KẾT XUẤT DELTA MATRIX
            # =============================================================================
            def clean_garment_fraction(v_str):
                """
                Chuyển đổi phân số dệt may (1/2, 3/4, 11 1/2) hoặc số thập phân về dạng float.
                Đảm bảo tính chính xác tuyệt đối cho các khoảng delta chênh lệch rập.
                """
                if not v_str:
                    return 0.0
                val_clean = str(v_str).strip().lower()
                # Loại bỏ các ký tự đơn vị inch hoặc khoảng trắng thừa
                val_clean = re.sub(r'(in|inch|""|u0022|cm|mm)', '', val_clean).strip()
                
                try:
                    # Xử lý trường hợp hỗn số dệt may (Ví dụ: "11 1/2" hoặc "11-1/2")
                    if ' ' in val_clean or '-' in val_clean:
                        parts = re.split(r'[\s-]+', val_clean)
                        if len(parts) == 2 and '/' in parts[1]:
                            whole = float(parts[0])
                            num, denom = parts[1].split('/')
                            return whole + (float(num) / float(denom))
                    
                    # Xử lý trường hợp chỉ có phân số đơn thuần (Ví dụ: "3/4")
                    if '/' in val_clean:
                        num, denom = val_clean.split('/')
                        return float(num) / float(denom)
                        
                    # Trường hợp số thực hoặc số nguyên tiêu chuẩn
                    return float(val_clean)
                except ValueError:
                    # Trích xuất ký tự số đầu tiên bằng Regex nếu chuỗi chứa ký tự lạ
                    nums = re.findall(r'\d+\.\d+|\d+', val_clean)
                    if nums:
                        return float(nums[0])
                    return 0.0

            # Lập ma trận so sánh POM (Gộp chung key từ cả 2 mẫu rập để đối soát chéo)
            m1 = d1.get("measurements", {})
            m2 = d2.get("measurements", {})
            all_poms = sorted(list(set(list(m1.keys()) + list(m2.keys()))))
            
            st.markdown("<p style='font-weight:700; font-size:14px; color:#1E293B; margin-top:15px;'>📐 BẢNG SAI LỆCH HÌNH HỌC PHÁT TRIỂN (DELTA MATRIX)</p>", unsafe_allow_html=True)
            
            # Khởi tạo khung hiển thị dữ liệu dệt may công nghiệp
            table_compare_html = """
            <div class="data-table-container">
                <table class="industrial-table">
                    <thead>
                        <tr>
                            <th>Điểm đo kỹ thuật (POM)</th>
                            <th>Thông số gốc A</th>
                            <th>Thông số sửa đổi B</th>
                            <th>Sai lệch (Delta)</th>
                        </tr>
                    </thead>
                    <tbody>
            """
            
            for pom in all_poms:
                val_a_raw = m1.get(pom, "-")
                val_b_raw = m2.get(pom, "-")
                
                num_a = clean_garment_fraction(val_a_raw) if val_a_raw != "-" else 0.0
                num_b = clean_garment_fraction(val_b_raw) if val_b_raw != "-" else 0.0
                
                delta = num_b - num_a
                
                # Định dạng màu sắc trực quan cho các khoảng Delta tăng (Xanh)/giảm (Đỏ)
                if delta > 0:
                    delta_str = f"<span style='color:#10B981; font-weight:700;'>+{delta:g}</span>"
                elif delta < 0:
                    delta_str = f"<span style='color:#EF4444; font-weight:700;'>{delta:g}</span>"
                else:
                    delta_str = "<span style='color:#64748B;'>0</span>" if val_a_raw != "-" and val_b_raw != "-" else "<span style='color:#CBD5E1;'>-</span>"
                
                table_compare_html += f"""
                    <tr>
                        <td style="font-weight:600;">{pom}</td>
                        <td>{val_a_raw}</td>
                        <td>{val_b_raw}</td>
                        <td>{delta_str}</td>
                    </tr>
                """
                
            table_compare_html += "</tbody></table></div>"
            st.markdown(table_compare_html, unsafe_allow_html=True)
            
            # Kết xuất trực quan hóa thiết kế phẳng hai bên đối xứng để kỹ sư đối chiếu hình ảnh
            st.markdown("<br>", unsafe_allow_html=True)
            img_col1, img_col2 = st.columns(2)
            with img_col1:
                st.markdown(f"<p class='metric-label' style='text-align:center;'>SKETCH FILE A: {d1['style_number_parsed']}</p>", unsafe_allow_html=True)
                if d1.get("sketch_image"):
                    st.image(base64.b64decode(d1["sketch_image"]), use_container_width=True)
            with img_col2:
                st.markdown(f"<p class='metric-label' style='text-align:center;'>SKETCH FILE B: {d2['style_number_parsed']}</p>", unsafe_allow_html=True)
                if d2.get("sketch_image"):
                    st.image(base64.b64decode(d2["sketch_image"]), use_container_width=True)
    else:
        st.markdown('<div class="idle-alert-box">⚠️ SELECTION IDLE: Vui lòng tải lên đồng thời cả 2 tệp PDF Techpack (Gốc và Sửa đổi) để kích hoạt ma trận đối chiếu.</div>', unsafe_allow_html=True)
# PHASE 6B - PART 2: DYNAMIC R&D GEOMETRIC ENGINE (STRICT INDUSTRIAL LOGIC)
                        # =============================================================================
                        # CHỈ THỊ THUẬT TOÁN TƯ VẤN TỐI CAO - KHÔI PHỤC BỘ NÃO TÍNH TOÁN ĐỘC LẬP CHO AI
                        system_instruction = (
                            "You are the elite Chief R&D Fashion Technical Director at PPJ Group.\n"
                            "Your core objective is to calculate fabric consumption, look up material databases, and analyze techpacks with 100% industrial precision. Hỏi gì đáp nấy.\n\n"
                            "STRICT OPERATIONAL INSTRUCTIONS FOR MULTI-INTENT PROCESSING:\n"
                            "1. LUỒNG TRA CỨU THUẦN TÚY (KHI KHÔNG CÓ FILE TẢI LÊN): Nếu người dùng chỉ gõ văn bản để hỏi tìm thông tin vải hoặc mã hàng cũ mà không đính kèm file, "
                            "bạn KHÔNG ĐƯỢC báo lỗi thiếu tài liệu. Hãy lập tức quét cạn kiệt phần dữ liệu 'KẾT QUẢ TRA CỨU DỮ LIỆU ĐỊNH MỨC VÀ NGUYÊN LIỆU PHÙ HỢP' thu được từ database ở trên. "
                            "Liệt kê rõ ràng tất cả các mã hàng lịch sử, định mức vải chính thực tế (Cons Value) thu được từ kho, và các ghi chú sản xuất liên quan đến từ khóa đó một cách ngắn gọn, minh bạch.\n"
                            "2. TUYỆT ĐỐI CẤM TỰ Ý ĐƯA CON SỐ GIẢ ĐỊNH CỐ ĐỊNH HOẶC HAO HỤT 15% VÀO LẬP LUẬN: Mỗi mã hàng có phom dáng và định mức hoàn toàn khác nhau. "
                            "Bạn tuyệt đối không được phép khóa cứng kết quả vào một con số cố định (như 2.05) hay tự bịa ra tỷ lệ phần trăm hao hụt cắt xưởng nếu dữ liệu kho thực tế không yêu cầu. Mọi lập luận phải biến thiên linh hoạt theo thông số rập thực tế.\n"
                            "3. THUẬT TOÁN TÍNH ĐỊNH MỨC KHI CÓ FILE VÀ KHO CÓ DỮ LIỆU ĐỐI CHIẾU: Khi có file tải lên và tìm thấy mã cũ tương đồng trong DB, "
                            "bạn phải lấy trực tiếp giá trị định mức gốc ('consumption_value') của mã cũ đó trong DB làm chuẩn. "
                            "Tiến hành so sánh ma trận số đo kích thước chênh lệch (Delta Spec) giữa mã mới tải lên và mã cũ đó để lập luận tăng hoặc giảm vật tư một cách logic (Ví dụ: Nếu mã mới dài hơn hoặc rộng hơn, điều chỉnh tăng định mức thêm một lượng yard tương ứng dựa trên chênh lệch inch của rập mẫu).\n"
                            "4. THUẬT TOÁN TÍNH TOÁN HÌNH HỌC TỰ ĐỘNG KHI KHO TRỐNG (ĐỘT PHÁ TƯ DUY AI): Trong trường hợp tải file lên nhưng kho dữ liệu trống hoặc không tìm thấy mã hàng tương đồng, "
                            "bạn bắt buộc phải vận dụng ngay thuật toán AI tự động tính toán diện tích hình học rập cắt thô tiêu chuẩn ngành may mặc. "
                            "Dựa vào ma trận thông số kích thước chi tiết bóc tách được từ file mới tải lên (Dài đáy, Rộng ống, Rộng đùi, Rộng hông, Rộng cạp, Dài thân trước/sau...), "
                            "áp dụng công thức toán học tính diện tích bề mặt vải cắt thô của các chi tiết quần (Thân trước x2, thân sau x2, cạp, lót túi, túi sau), "
                            "kết hợp với Khổ vải chỉ định (Ví dụ: Khổ 57 inch) để tự tính toán và đưa ra một con số kết luận định mức vải dự kiến (Cons Value) độc lập, biến thiên chuẩn xác cụ thể (YARDS/UNIT) cho riêng mã hàng này, kèm theo lập luận giải thích công thức rõ ràng cho kỹ sư phân xưởng.\n"
                            "5. ĐÁP ỨNG ĐÚNG TRỌNG TÂM CÂU HỎI: Hỏi gì đáp nấy, tập trung thẳng vào số liệu kỹ thuật, trình bày khoa học bằng tiếng Việt chuyên ngành dệt may kỹ thuật."
                        )
                        
                        full_prompt = f"{system_instruction}\n\nYêu cầu của kỹ sư: {user_query}\n\n[Thông số ma trận file mới tải lên]:\n{new_style_raw_text if new_style_raw_text else 'Không đính kèm file (Kỹ sư tra cứu thuần văn bản)'}\n{db_context}"
                        contents_payload.append(full_prompt)
                        
                        # Bộ bẫy lỗi lũy tiến Backoff 5 lần tránh sập mạng
                                                # =============================================================================
                        # PHASE 6B - PART 2: DYNAMIC STORAGE IMAGE LINKING ENGINE & RETRY PIPELINE
                        # =============================================================================
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
                        
                        # ✨ ĐỘT PHÁ TỰ ĐỘNG GỌI KHO ẢNH CHUYÊN NGHIỆP:
                        # Nếu database thong_so_techpack không trả về URL, hệ thống sẽ tự động lấy từ khóa sạch 'dynamic_keyword' (ví dụ: R09-490416)
                        # Để tự cấu trúc chính xác đường link public dẫn thẳng đến file ảnh .jpg trong bucket kho_anh của bạn!
                        final_render_url = ""
                        final_caption_title = ""
                        
                        if detected_image_url_to_render:
                            final_render_url = detected_image_url_to_render
                            final_caption_title = detected_style_title_to_render
                        elif dynamic_keyword and str(dynamic_keyword).strip() != "":
                            clean_style_id = str(dynamic_keyword).strip()
                            # Tự động ghép nối đường dẫn URL công khai dẫn thẳng tới file ảnh lưu trữ thực tế trong kho của bạn
                            final_render_url = f"{SB_URL.rstrip('/')}/storage/v1/object/public/kho_anh/{clean_style_id}.jpg"
                            final_caption_title = clean_style_id

                        # Kích hoạt hiển thị trực quan sơ đồ phác thảo phẳng (Garment Flat Sketch) lên khung chat
                        if final_render_url:
                            st.markdown("<br>", unsafe_allow_html=True)
                            # Hiển thị ảnh dạng Card thu nhỏ chuyên nghiệp, tránh tràn khung hình
                            st.image(final_render_url, caption=f"📐 Bản vẽ Sketch thiết kế đối chiếu của Mã hàng: {final_caption_title}", width=240)
                            
                            # Lưu hình ảnh này vào lịch sử trò chuyện để không bị biến mất khi trang web làm mới (Rerun)
                            st.session_state["chat_history"].append({
                                "role": "assistant", 
                                "type": "visual", 
                                "content": f"[Hệ thống đã xuất hình ảnh tham chiếu công khai của mã {final_caption_title} từ kho lưu trữ lên màn hình]",
                                "image_url": final_render_url,
                                "style_title": final_caption_title
                            })
                            
                    except Exception as e: 
                        ans = f"⚠️ Máy chủ AI đang xử lý tác vụ tra cứu kho lớn. Vui lòng thử lại sau vài giây! Chi tiết: {str(e)}"
                        st.write(ans)
                        st.session_state["chat_history"].append({"role": "assistant", "type": "text", "content": ans})
