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
st.markdown("""
    <style>
    /* Tổng thể nền và Sidebar màu tối chuyên nghiệp */
    .stApp { background-color: #F8FAFC; }
    [data-testid="stSidebar"] { background-color: #0F172A; color: #FFFFFF; min-width: 300px; }
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p { color: #E2E8F0; }
    
    /* Thương hiệu PPJ Group ở Sidebar */
    .sidebar-brand-container {
        background: linear-gradient(135deg, #1E3A8A 0%, #3B82F6 100%);
        padding: 20px; border-radius: 12px; text-align: center; margin-bottom: 25px;
        box-shadow: 0 4px 12px rgba(37, 99, 235, 0.2);
    }
    .sidebar-brand-title { font-size: 22px; font-weight: 800; color: #FFFFFF; margin: 0; letter-spacing: 1px; }
    .sidebar-brand-subtitle { font-size: 11px; color: #93C5FD; margin-top: 4px; font-weight: 500; }
    
    /* Thiết kế Khung Container chính (Card hoành tráng) */
    .tech-card {
        background-color: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 16px;
        padding: 24px; margin-bottom: 24px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
    }
    .tech-header { font-size: 18px; font-weight: 700; color: #1E293B; border-bottom: 2px solid #F1F5F9; padding-bottom: 12px; margin-bottom: 20px; }
    
    /* Khung kết quả chi tiết từng sản phẩm (Matrix Node) */
    .matrix-node { background: #FFFFFF; border: 1px solid #CBD5E1; border-top: 4px solid #2563EB; border-radius: 12px; padding: 20px; margin-bottom: 20px; }
    .matrix-title { font-size: 16px; font-weight: 700; color: #1E3A8A; margin-bottom: 12px; }
    
    .badge-container { display: flex; gap: 8px; margin-bottom: 15px; }
    .badge-custom { padding: 4px 10px; border-radius: 6px; font-size: 11px; font-weight: 700; text-transform: uppercase; }
    .badge-offline { background-color: #FEF3C7; color: #D97706; border: 1px solid #FCD34D; }
    .badge-match { background-color: #DBEAFE; color: #2563EB; border: 1px solid #BFDBFE; }
    
    /* Định dạng bảng dữ liệu kỹ thuật */
    .tech-table { width: 100%; border-collapse: collapse; margin-top: 10px; }
    .tech-table th { background-color: #F8FAFC; color: #64748B; font-weight: 600; text-align: left; padding: 10px; border-bottom: 2px solid #E2E8F0; font-size: 13px; }
    .tech-table td { padding: 10px; border-bottom: 1px solid #F1F5F9; color: #334155; font-size: 13px; }
    </style>
""", unsafe_allow_html=True)
# Cấu hình kết nối cơ sở dữ liệu Supabase Master DB của PPJ Group
SB_URL = "https://ewqqodsfvlvnrzsylawy.supabase.co"
SB_KEY = st.secrets.get("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImV3cXFvZHNmdmx2bnJ6c3lsYXd5Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzUxMTkyOTAsImV4cCI6MjA5MDY5NTI5MH0.BWPxOsyswBT5CLrZgluRC1F2x5EpU06oexUFyakGhyc")

def get_secure_gemini_key():
    if "GEMINI_API_KEY" in st.secrets:
        return st.secrets["GEMINI_API_KEY"].strip()
    return None

def save_to_supabase_techpack_table(payload_data):
    """Hàm xử lý lưu trữ hình ảnh rập/sketch và đồng bộ bảng thông số kĩ thuật vào Supabase Database"""
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
            except Exception: pass

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
    except Exception: return False

def get_historical_fabric_consumption_from_db(search_keyword=None):
    """Hàm trích xuất dữ liệu định mức vải trên Supabase theo mã hàng tìm kiếm tương đồng"""
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
    except Exception: return []
def process_single_pdf_batch(file_bytes, file_name):
    """Xử lý cắt trang PDF thành ảnh và dùng Gemini AI bóc tách TOÀN BỘ ma trận thông số cấu trúc thực tế"""
    gemini_key = get_secure_gemini_key()
    if not gemini_key: 
        return {"success": False, "error": "Chưa cấu hình khóa Secrets GEMINI_API_KEY trên Streamlit."}
    
    # ✨ ĐÃ SỬA TRIỆT ĐỂ LỖI: Lấy chính xác phần tử đầu tiên của List [0] trước khi dùng .strip()
    if '.' in file_name:
        fallback_style = file_name.rsplit('.', 1)[0].strip()
    else:
        fallback_style = file_name.strip()

    try:
        info = pdfinfo_from_bytes(file_bytes)
        total_pages = int(info.get("Pages", 1))
        contents_payload = []
        sketch_base64 = ""

        for p_num in range(1, total_pages + 1):
            try:
                images = convert_from_bytes(file_bytes, dpi=160, first_page=p_num, last_page=p_num)
                if images:
                    img = images[0].convert("RGB") # ĐÃ SỬA LỖI: Lấy phần tử ảnh đầu tiên của danh sách
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
            return {"success": False, "error": "Không thể giải mã hình ảnh từ file PDF."}

        user_prompt = """
        You are a strict garment technical auditor. Analyze all the attached images from the techpack PDF.
        
        CRITICAL INSTRUCTIONS:
        1. Identify the main specification grid/table containing Point of Measurements (POM Description / Vị trí đo) and their target spec values for the sample base size.
        2. Read the grid ROW-BY-ROW. You MUST extract EVERY SINGLE measurement row found in the document. Do not truncate, do not skip, and do not summarize.
        3. For the "measurements" object, map each detected POM name directly to its target measurement value. Extract all available rows.

        Return a valid JSON object with this exact schema:
        {
          "style_number_parsed": "Extract real Style ID from text",
          "buyer": "Extract real Buyer Account name",
          "category": "Extract real Product Category line",
          "base_size_name": "Extract Sample Base Size",
          "measurements": {
             "Detected POM Name 1": "Value 1",
             "Detected POM Name 2": "Value 2"
          }
        }
        """
        contents_payload.append(user_prompt)

        client = genai.Client(api_key=gemini_key)
        response = client.models.generate_content(
            model='gemini-2.5-flash', 
            contents=contents_payload, 
            config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.0)
        )
        
        parsed_data = json.loads(response.text.strip())
        parsed_data["sketch_image"] = sketch_base64
        if not parsed_data.get("style_number_parsed"):
            parsed_data["style_number_parsed"] = fallback_style
            
        return {"success": True, "data": parsed_data}
    except Exception as e: 
        return {"success": False, "error": f"Lỗi hệ thống khi gọi AI: {str(e)}"}
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
    st.success("Database Status: ONLINE")
    st.info("Core Engine: Gemini-2.5-Flash")

# Nhúng bổ sung CSS nâng cấp giao diện bảng dữ liệu Cyber chuyên sâu
st.markdown("""
    <style>
    /* Bo mạch lưới bảng dữ liệu may mặc cao cấp */
    .cyber-table-wrapper {
        max-height: 480px; overflow-y: auto; border: 1px solid #CBD5E1; 
        border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.03); margin-top: 15px;
    }
    .cyber-table { width: 100%; border-collapse: collapse; text-align: left; font-family: sans-serif; }
    .cyber-table th {
        background: linear-gradient(90deg, #1E3A8A 0%, #2563EB 100%);
        color: #FFFFFF; font-weight: 600; padding: 12px 16px; 
        font-size: 13px; letter-spacing: 0.5px; position: sticky; top: 0; z-index: 10;
    }
    .cyber-table td { padding: 12px 16px; border-bottom: 1px solid #E2E8F0; color: #334155; font-size: 13.5px; font-weight: 500; }
    .cyber-table tr:hover { background-color: #F8FAFC; }
    
    /* Hệ thống mã màu nhận diện sai lệch Delta tự động */
    .delta-positive { background-color: #DCFCE7 !important; color: #166534 !important; font-weight: 700 !important; border-radius: 4px; padding: 2px 6px; }
    .delta-negative { background-color: #FEE2E2 !important; color: #991B1B !important; font-weight: 700 !important; border-radius: 4px; padding: 2px 6px; }
    .delta-zero { color: #64748B; font-weight: 400; }
    
    /* Tiêu đề vùng đối chiếu kiểu dáng đặc thù */
    .comp-header-box {
        background-color: #FFFFFF; border-left: 5px solid #3B82F6; 
        padding: 12px 20px; border-radius: 4px 12px 12px 4px; margin-bottom: 20px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.02);
    }
    </style>
""", unsafe_allow_html=True)

if "processed_styles" not in st.session_state:
    st.session_state["processed_styles"] = {}

# -----------------------------------------------------------------------------
# CHỨC NĂNG 1: QUÉT TỰ ĐỘNG BẰNG AI VÀ LƯU HÀNG LOẠT (BULK SAVE)
# -----------------------------------------------------------------------------
if menu_selection == "📊 Quét Techpack Document":
    st.markdown("""<div class="tech-card"><div class="tech-header">📥 STEP 1: GARMENT TECHPACK DATA INGESTION</div></div>""", unsafe_allow_html=True)
    uploaded_files = st.file_uploader("Upload PDF", type=["pdf"], accept_multiple_files=True, label_visibility="collapsed")
    st.markdown("""<div class="tech-card"><div class="tech-header">🔍 STEP 2: METRIC EXTRACTION & VISUAL RENDERING MATRIX</div></div>""", unsafe_allow_html=True)
    
    if uploaded_files:
        files_to_render = []
        for file in uploaded_files:
            if file.name not in st.session_state["processed_styles"]:
                with st.spinner(f"AI đang bóc tách file {file.name}..."):
                    res = process_single_pdf_batch(file.getvalue(), file.name)
                    if res["success"]: st.session_state["processed_styles"][file.name] = res["data"]
                    else: st.error(f"Lỗi file {file.name}: {res['error']}")
            if file.name in st.session_state["processed_styles"]: files_to_render.append(file.name)

        if files_to_render:
            st.markdown("### 📊 THAO TÁC HỆ THỐNG HÀNG LOẠT")
            if st.button("💾 LƯU TẤT CẢ CÁC MÃ HÀNG ĐÃ QUÉT VÀO MASTER DB", key="bulk_save_all_btn", type="primary", use_container_width=True):
                success_count = 0
                with st.spinner("Đang đồng bộ dữ liệu hàng loạt lên máy chủ Supabase..."):
                    for f_name in files_to_render:
                        style_data = st.session_state["processed_styles"][f_name]
                        if save_to_supabase_techpack_table(style_data): success_count += 1
                st.success(f"🎉 Đồng bộ thành công {success_count}/{len(files_to_render)} mã hàng vào Database!")
            st.markdown("---")

            cols = st.columns(2)
            for idx, f_name in enumerate(files_to_render):
                col_target = cols[idx % 2]
                data = st.session_state["processed_styles"][f_name]
                with col_target:
                    st.markdown(f"""<div class="matrix-node"><div class="matrix-title">{data.get('style_number_parsed')}</div>
                        <p style="margin:2px 0; font-size:13px;"><b>Buyer:</b> {data.get('buyer')}</p>
                        <p style="margin:2px 0; font-size:13px;"><b>Product Line:</b> {data.get('category')}</p></div>""", unsafe_allow_html=True)
                    
                    sub_col1, sub_col2 = st.columns([1.2, 0.8])
                    with sub_col1:
                        st.markdown("<p style='font-weight:700; font-size:13px;'>📋 SPECIFICATION MATRIX</p>", unsafe_allow_html=True)
                        table_html = '<div class="cyber-table-wrapper"><table class="cyber-table"><tr><th>Garment Attribute</th><th>Target Spec</th></tr>'
                        for k, v in data.get("measurements", {}).items():
                            table_html += f"<tr><td>{k}</td><td>{v}</td></tr>"
                        st.markdown(table_html + "</table></div>", unsafe_allow_html=True)
                    with sub_col2:
                        st.markdown("<p style='font-weight:700; font-size:13px;'>🤖 GARMENT REPLICAS</p>", unsafe_allow_html=True)
                        if data.get("sketch_image"): st.image(base64.b64decode(data["sketch_image"]), use_column_width=True)
                    st.markdown("<br><hr style='border-color:#E2E8F0;'><br>", unsafe_allow_html=True)
    else: st.warning("⚠️ Hiện tại chưa có tệp dữ liệu Techpack nào được đưa vào hệ thống xử lý.")


# -----------------------------------------------------------------------------
# CHỨC NĂNG 2 (TIẾP THEO): ĐỐI CHIẾU SO SÁNH HAI MÃ RẬP KHÁC NHAU (FIX LỖI HIỂN THỊ TUYỆT ĐỐI)
# -----------------------------------------------------------------------------
elif menu_selection == "🔄 Pattern Spec Comparison":
    st.markdown("""<div class="tech-card"><div class="tech-header">🔄 CHỨC NĂNG ĐỐI CHIẾU SỐ ĐO & PHÂN TÍCH SAI LỆCH (DELTA SPEC)</div></div>""", unsafe_allow_html=True)
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
            st.markdown(f"""<div style="background-color: #FFFFFF; border-left: 5px solid #3B82F6; padding: 12px 20px; border-radius: 4px 12px 12px 4px; margin-bottom: 20px; box-shadow: 0 2px 5px rgba(0,0,0,0.02);"><h5 style="margin:0; color:#1E3A8A; font-weight:700; font-size:16px;">⚙️ ĐANG ĐỐI CHIẾU MA TRẬN PHÁT TRIỂN MẪU</h5><p style="margin:4px 0 0 0; font-size:13px; color:#64748B;"><b>Mẫu Gốc A:</b> {d1['style_number_parsed']} [Size: {d1.get('base_size_name','N/A')}] &nbsp;|&nbsp; <b>Mẫu Sửa B:</b> {d2['style_number_parsed']} [Size: {d2.get('base_size_name','N/A')}]</p></div>""", unsafe_allow_html=True)
            
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

            size_a = d1.get("base_size_name", "BASE SIZE").strip()
            size_b = d2.get("base_size_name", "BASE SIZE").strip()
            col_title_a = f"Mẫu A ({d1['style_number_parsed']}) [Size: {size_a}]"
            col_title_b = f"Mẫu B ({d2['style_number_parsed']}) [Size: {size_b}]"

            all_poms = set(list(d1["measurements"].keys()) + list(d2["measurements"].keys()))
            
            # ✨ BIẾN ĐỔI QUAN TRỌNG: Nối chuỗi liên tục trên một dòng, triệt tiêu toàn bộ ký tự xuống dòng chắp vá
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
                    delta_td = f'<td style="padding:10px 14px;border-bottom:1px solid #E2E8F0;text-align:center;"><span style="background-color:#DCFCE7;color:#166534;font-weight:700;padding:2px 6px;border-radius:4px;font-size:12px;">+{delta}</span></td>'
                elif delta < 0:
                    delta_td = f'<td style="padding:10px 14px;border-bottom:1px solid #E2E8F0;text-align:center;"><span style="background-color:#FEE2E2;color:#991B1B;font-weight:700;padding:2px 6px;border-radius:4px;font-size:12px;">{delta}</span></td>'
                else:
                    delta_td = f'<td style="padding:10px 14px;border-bottom:1px solid #E2E8F0;text-align:center;color:#94A3B8;font-size:12px;">0</td>'
                
                # Gom gọn dòng TR thành một chuỗi văn bản không xuống hàng
                table_body_html += f'<tr style="background-color:#FFFFFF;"><td style="padding:10px 14px;border-bottom:1px solid #E2E8F0;font-weight:600;color:#1E293B;font-size:13px;">{pom}</td><td style="padding:10px 14px;border-bottom:1px solid #E2E8F0;color:#334155;font-size:13px;">{val1}</td><td style="padding:10px 14px;border-bottom:1px solid #E2E8F0;color:#334155;font-size:13px;">{val2}</td>{delta_td}</tr>'
            
            # Đóng gói toàn bộ cấu trúc Table trên một dòng lệnh duy nhất để Streamlit không chèn thẻ code lỗi
            full_table_render = f'<div style="max-height:450px;overflow-y:auto;border:1px solid #CBD5E1;border-radius:12px;margin-top:15px;"><table style="width:100%;border-collapse:collapse;text-align:left;font-family:sans-serif;"><thead><tr style="background:linear-gradient(90deg,#1E3A8A 0%,#2563EB 100%);"><th style="color:#FFFFFF;font-weight:600;padding:12px 14px;font-size:13px;position:sticky;top:0;z-index:10;">Vị trí đo (POM Description)</th><th style="color:#FFFFFF;font-weight:600;padding:12px 14px;font-size:13px;position:sticky;top:0;z-index:10;">{col_title_a}</th><th style="color:#FFFFFF;font-weight:600;padding:12px 14px;font-size:13px;position:sticky;top:0;z-index:10;">{col_title_b}</th><th style="color:#FFFFFF;font-weight:600;padding:12px 14px;font-size:13px;text-align:center;width:140px;position:sticky;top:0;z-index:10;">Sai lệch (Delta)</th></tr></thead><tbody>{table_body_html}</tbody></table></div>'
            
            # Thực thi ép buộc render giao diện
            st.markdown(full_table_render, unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)
            
            # Luồng xuất file Excel kỹ thuật giữ nguyên
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
                label="📥 XUẤT BÁO CÁO ĐỐI CHIẾU THÔNG SỐ (EXCEL PRODUCTION)", 
                data=towrite, 
                file_name=f"PPJ_Spec_Comparison_Premium.xlsx", 
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )



# CHỨC NĂNG 3: TRỢ LÝ ĐỊNH MỨC VẢI THÔNG MINH (BÓC TÁCH MÃ MỚI -> QUÉT KHO TƯƠNG ĐỒNG -> TỰ ĐỘNG TÍNH ĐỊNH MỨC THEO DELTA SPEC)
elif menu_selection == "🧵 Fabric Consumption Assistant (Cons)":
    st.markdown("""<div class="tech-card"><div class="tech-header">🧵 PPJ INTELLIGENT FABRIC CONSUMPTION ASSISTANT (R&D ENGINE)</div>
    <p style="color: #64748B; font-size:14px; margin:0;">Tải lên tài liệu Techpack mới, AI sẽ tự động bóc tách hình ảnh/thông số, truy vấn mã hàng tương đồng trong kho Supabase và lập luận toán học để tự động tính định mức vải mới.</p></div>""", unsafe_allow_html=True)
    
    # ✨ ĐÃ SỬA LỖI: Chia cột theo tỷ lệ rõ ràng [3.2, 0.8] (Cột 1 rộng 80% chứa file, Cột 2 rộng 20% chứa nút xóa)
    control_col1, control_col2 = st.columns([3.2, 0.8])
    
    with control_col1:
        st.markdown("##### 📁 TẢI LÊN FILE TECHPACK MỚI ĐỂ AI PHÂN TÍCH & TÍNH TOÁN ĐỊNH MỨC VẢI")
        chat_file = st.file_uploader("Upload tài liệu vật tư kỹ thuật tại đây", type=["pdf", "jpg", "jpeg", "png"], key="chat_uploader", label_visibility="collapsed")
        if chat_file: 
            st.success(f"📎 Hệ thống tiếp nhận thành công tài liệu: {chat_file.name}")
            
    with control_col2:
        st.markdown("##### 🧹 LÀM LÀM MỚI")
        if st.button("🗑️ XÓA LỊCH SỬ CHAT", use_container_width=True, type="secondary"):
            import time
            if "chat_history" in st.session_state:
                del st.session_state["chat_history"]
            st.success("🔄 Đã xóa lịch sử! Sẵn sàng làm việc với mã hàng mới.")
            time.sleep(1)
            st.rerun()

    st.markdown("---")
    
    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = [
            {"role": "assistant", "content": "Xin chào! Tôi là Trợ lý Nghiên cứu & Phát triển Vật tư (R&D AI) của PPJ Group. Hãy tải sơ đồ rập/Techpack mã mới lên và ra lệnh cho tôi, tôi sẽ bóc tách dữ liệu, đối chiếu kho để tự động tính toán định mức vải chính xác cho bạn!"}
        ]
        
    for msg in st.session_state["chat_history"]:
        with st.chat_message(msg["role"]): st.write(msg["content"])
        if user_query := st.chat_input("Nhập yêu cầu (Ví dụ: Hãy tìm mã tương đồng và tính định mức cho mã mới này)..."):
        st.session_state["chat_history"].append({"role": "user", "content": user_query})
        with st.chat_message("user"): 
            st.write(user_query)
            
        with st.chat_message("assistant"):
            with st.spinner("Hệ thống R&D Core AI đang chạy chu trình phân tích, đối chiếu kho và lập ma trận toán học..."):
                gemini_key = get_secure_gemini_key()
                if not gemini_key: 
                    ans = "Hệ thống chưa được cấu hình khóa bảo mật GEMINI_API_KEY."
                else:
                    try:
                        client = genai.Client(api_key=gemini_key)
                        contents_payload = []
                        new_style_info = {}
                        
                        # BƯỚC 1: Xử lý bóc tách File mã hàng mới đính kèm bằng AI (Nếu người dùng có upload file)
                        if chat_file:
                            file_bytes = chat_file.getvalue()
                            img_payload = []
                            if chat_file.name.lower().endswith('.pdf'):
                                images = convert_from_bytes(file_bytes, dpi=140, first_page=1, last_page=1)
                                if images:
                                    img_buf = io.BytesIO()
                                    # ✨ ĐÃ SỬA LỖI: Thêm [0] để lấy chính xác trang ảnh đầu tiên từ danh sách trang PDF
                                    images[0].convert("RGB").save(img_buf, format="JPEG")
                                    img_payload.append(types.Part.from_bytes(data=img_buf.getvalue(), mime_type='image/jpeg'))
                            else:
                                img_payload.append(types.Part.from_bytes(data=file_bytes, mime_type='image/jpeg'))
                            
                            extraction_prompt = "Extract the Style ID, Buyer, Category, Base Size and EVERY measurement specification. Return raw text."
                            img_payload.append(extraction_prompt)
                            extraction_res = client.models.generate_content(model='gemini-2.5-flash', contents=img_payload)
                            new_style_info["raw_text"] = extraction_res.text
                            
                            if chat_file.name.lower().endswith('.pdf') and images:
                                img_buf = io.BytesIO()
                                # ✨ ĐÃ SỬA LỖI: Thêm [0] để lấy ảnh đính kèm vào luồng phản hồi cuối cùng hiển thị trực quan
                                images[0].convert("RGB").save(img_buf, format="JPEG")
                                contents_payload.append(types.Part.from_bytes(data=img_buf.getvalue(), mime_type='image/jpeg'))
                            elif not chat_file.name.lower().endswith('.pdf'):
                                contents_payload.append(types.Part.from_bytes(data=file_bytes, mime_type='image/jpeg'))
                        
                        # BƯỚC 2: Tự động trích xuất từ khóa từ file mới hoặc câu lệnh để truy vấn kho Supabase
                        search_keyword = ""
                        if chat_file:
                            found_keywords = re.findall(r'[A-Za-z0-9]+[-–][A-Za-z0-9]+|[A-Za-z0-9]{4,}', chat_file.name)
                            if found_keywords: search_keyword = found_keywords
                        if not search_keyword:
                            found_keywords = re.findall(r'[A-Za-z0-9]+[-–][A-Za-z0-9]+|[A-Za-z0-9]{4,}', user_query)
                            if found_keywords: search_keyword = found_keywords
                            
                        db_results = get_historical_fabric_consumption_from_db(search_keyword=search_keyword if search_keyword else None)
                        
                        db_context = ""
                        if db_results:
                            db_context = "\n\n[KHO DỮ LIỆU LỊCH SỬ SUPABASE PHÙ HỢP ĐỂ ĐỐI CHIẾU VÀ TÍNH TOÁN]:\n"
                            for item in db_results:
                                db_context += (
                                    f"- Mã hàng lịch sử: {item.get('style_name')}\n"
                                    f"  + Loại nguyên liệu/Vải: {item.get('article_name')}\n"
                                    f"  + Định mức tiêu thụ (Cons) gốc trong kho: {item.get('consumption_value')} {item.get('uom')}\n"
                                    f"  + Ghi chú cấu trúc: {item.get('notes')}\n"
                                )
                        else:
                            backup_results = get_historical_fabric_consumption_from_db(search_keyword=None)
                            db_context = "\n\n[KHO DỮ LIỆU LỊCH SỬ THAM KHẢO]:\n"
                            for item in backup_results[:5]:
                                db_context += f"- Mã hàng: {item.get('style_name')}, Vải: {item.get('article_name')}, Định mức gốc: {item.get('consumption_value')} {item.get('uom')}, Cấu trúc: {item.get('notes')}\n"

                        # BƯỚC 3: Thiết lập Prompt kỹ thuật cao, chỉ thị AI thực hiện quy trình nghiệp vụ R&D 3 bước
                        system_instruction = (
                            "You are the Lead R&D Expert and Garment Technical Auditor at PPJ Group.\n"
                            "Your job is to calculate the fabric consumption (Cons) for a NEW garment style by comparing it with SIMILAR historical styles in the database.\n\n"
                            "EXECUTE THIS STRICT 3-STEP WORKFLOW IN YOUR RESPONSE:\n"
                            "1. TRÍCH XUẤT MÃ MỚI: Liệt kê rõ Style ID, Buyer, hình dáng bản vẽ (Sketch) và toàn bộ bảng thông số kích cỡ cơ bản trích xuất được từ tài liệu mới tải lên.\n"
                            "2. ĐỐI CHIẾU MÃ TƯƠNG ĐỒNG: Chọn ra mã hàng tương đồng nhất từ danh sách Kho dữ liệu Supabase được cung cấp bên dưới. Chỉ rõ mã cũ đó có kiểu dáng, chất liệu vải và định mức tiêu thụ gốc là bao nhiêu.\n"
                            "3. PHÂN TÍCH DELTA SPEC & TÍNH ĐỊNH MỨC MỚI: So sánh chi tiết thông số kích thước giữa Mã mới và Mã tương đồng vừa chọn (ví dụ: Waist, Hip, Inseam, Thigh opening lệch bao nhiêu inch/cm). "
                            "Dựa trên các độ lệch kích thước này (Delta Spec), áp dụng lập luận kỹ thuật ngành may để tăng hoặc giảm định mức tiêu thụ vải từ định mức gốc của mã cũ, "
                            "đưa ra con số định mức tiêu thụ vải dự kiến cuối cùng (Cons value) cho mã hàng mới một cách chính xác.\n\n"
                            "Trình bày báo cáo rõ ràng, chuyên nghiệp bằng tiếng Việt kỹ thuật."
                        )
                        
                        full_prompt = (
                            f"{system_instruction}\n\n"
                            f"Yêu cầu của kỹ sư: {user_query}\n\n"
                            f"[Dữ liệu bóc tách thô của mã mới]: {new_style_info.get('raw_text', 'Không có file đính kèm')}\n"
                            f"{db_context}"
                        )
                        contents_payload.append(full_prompt)
                        
                        ans = ""
                        for attempt in range(3):
                            try:
                                response = client.models.generate_content(model='gemini-2.5-flash', contents=contents_payload)
                                ans = response.text
                                break
                            except Exception as e:
                                if "503" in str(e) or "UNAVAILABLE" in str(e):
                                    if attempt < 2:
                                        import time
                                        time.sleep(2)
                                        continue
                                raise e
                                
                    except Exception as e: 
                        ans = f"Máy chủ AI hiện đang bận do xử lý ma trận tính toán lớn. Vui lòng bấm gửi lại câu hỏi sau vài giây nhé! Chi tiết: {str(e)}"
                        
                st.write(ans)
                st.session_state["chat_history"].append({"role": "assistant", "content": ans})
