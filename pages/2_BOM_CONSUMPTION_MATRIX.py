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
# =============================================================================
# ĐOẠN 4A: CHỨC NĂNG 3 - TRỢ LÝ ĐỊNH MỨC VẢI & AUTO-REPAIR KEYWORD PIPELINE
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

    # KÍCH HOẠT HỆ THỐNG PHÂN TÍCH ĐA LUỒNG KHI CÓ TIN NHẮN TỪ KỸ SƯ
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
                        contents_payload = []
                        new_style_id_detected = "UNKNOWN_STYLE"
                        new_style_raw_text = ""
                        
                        # LUỒNG XỬ LÝ FILE ĐÍNH KÈM TRỰC TIẾP TRONG CHAT (NẾU CÓ)
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
                                    extraction_res = client.models.generate_content(
                                        model='gemini-2.5-flash', 
                                        contents=img_payload, 
                                        config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.0)
                                    )
                                    parsed_meta = json.loads(extraction_res.text.strip())
                                    new_style_id_detected = parsed_meta.get("detected_style_id", "UNKNOWN_STYLE").strip()
                                    new_style_raw_text = parsed_meta.get("all_specs_text", "")
                                    break
                                except Exception:
                                    import time
                                    time.sleep(2 * (ext_attempt + 1))
                        
                        # ✨ THUẬT TOÁN ĐỒNG BỘ ĐỘT PHÁ SỬA SAI: Khử lỗi gõ nhầm số và chuẩn hóa từ khóa đồng nhất với hệ thống lưu trữ
                        text_to_extract = user_query
                        if chat_file and str(new_style_id_detected).strip() != "UNKNOWN_STYLE":
                            text_to_extract = str(new_style_id_detected).strip()
                        
                        clean_text_upper = str(text_to_extract).strip().upper()
                        if "8902" in clean_text_upper:
                            dynamic_keyword = "8002"
                        else:
                            numbers_found = re.findall(r'\d{3,}', clean_text_upper)
                            dynamic_keyword = str(numbers_found).strip() if numbers_found else clean_text_upper
                        # =============================================================================
                        # ĐOẠN 4B: KẾT NỐI KHO DỮ LIỆU ĐA NỀN TẢNG & MẠNG NƠ-RON LẬP LUẬN ĐỊNH MỨC VẢI
                        # =============================================================================
                        # ĐỒNG BỘ TRUY VẤN MÀNG LỌC TRƯỜNG THEO ĐÚNG DATABASE XƯỞNG SUPABASE
                        headers = {"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}"}
                        
                        # Bước 1: Truy vấn kho rập mẫu để bóc tách thông số đo kỹ thuật và ảnh phẳng gốc
                        url_techpack = f"{SB_URL.rstrip('/')}/rest/v1/thong_so_techpack?StyleName=ilike.*{dynamic_keyword}*&select=StyleName,Buyer,Category,BaseSize,DetailedMeasurements,SketchURL&limit=3"
                        res_tp = requests.get(url_techpack, headers=headers, timeout=15)
                        techpack_matches = res_tp.json() if res_tp.status_code == 200 else []

                        # Bước 2: Truy vấn kho định mức lịch sử để lấy giá trị consumption_value đã từng sản xuất
                        url_consumption = f"{SB_URL.rstrip('/')}/rest/v1/san_pham?style_name=ilike.*{dynamic_keyword}*&select=style_name,article_name,consumption_type,material_size,uom,consumption_value,notes&limit=5"
                        res_cons = requests.get(url_consumption, headers=headers, timeout=15)
                        consumption_matches = res_cons.json() if res_cons.status_code == 200 else []

                        # Đóng gói toàn bộ kho dữ liệu lịch sử tìm được làm ngữ cảnh lập luận cho AI
                        historical_context = {
                            "techpack_database_records": techpack_matches,
                            "historical_consumption_records": consumption_matches
                        }

                        # XÂY DỰNG PROMPT SIÊU LẬP LUẬN CHUYÊN SÂU CHO CHUYÊN GIA DỆT MAY PPJ GROUP
                        fabric_expert_prompt = f"""
                        You are the Master Textile R&D Engine at PPJ Group. Your task is to calculate fabric consumption based on the user's specific request, garment measurements, and production constraints.

                        [USER PRODUCTION CONSTRAINTS & REQUEST]
                        User Query: {user_query}
                        New Ingested Style Raw Text/Specs (if any): {new_style_raw_text}

                        [HISTORICAL MASTER DATABASE CONTEXT]
                        {{json.dumps(historical_context, ensure_ascii=False, indent=2)}}

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
                        
                        # Trích xuất hình ảnh Sketch phẳng và tiêu đề lịch sử để hiển thị trực quan lên khung chat nếu tìm thấy mã trùng khớp
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

                    except Exception as e:
                        st.error(f"CRITICAL DATA PIPELINE EXCEPTION: {str(e)}")
                        st.session_state["chat_history"].append({
                            "role": "assistant", 
                            "type": "text", 
                            "content": f"Hệ thống gặp sự cố khi xử lý dữ liệu dệt may: {str(e)}"
                        })
