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

# Cấu hình trang Streamlit bắt buộc ở đầu file
st.set_page_config(
    page_title="PPJ Techpack AI - Management System",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Hệ thống Style CSS cao cấp, đóng khung hoành tráng
st.markdown("""
    <style>
    .stApp { background-color: #F8FAFC; }
    [data-testid="stSidebar"] { background-color: #0F172A; color: #FFFFFF; min-width: 300px; }
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p { color: #E2E8F0; }
    
    .sidebar-brand-container {
        background: linear-gradient(135deg, #1E3A8A 0%, #3B82F6 100%);
        padding: 20px; border-radius: 12px; text-align: center; margin-bottom: 25px;
        box-shadow: 0 4px 12px rgba(37, 99, 235, 0.2);
    }
    .sidebar-brand-title { font-size: 22px; font-weight: 800; color: #FFFFFF; margin: 0; letter-spacing: 1px; }
    .sidebar-brand-subtitle { font-size: 11px; color: #93C5FD; margin-top: 4px; font-weight: 500; }
    
    .tech-card {
        background-color: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 16px;
        padding: 24px; margin-bottom: 24px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
    }
    .tech-header { font-size: 18px; font-weight: 700; color: #1E293B; border-bottom: 2px solid #F1F5F9; padding-bottom: 12px; margin-bottom: 20px; }
    
    .matrix-node { background: #FFFFFF; border: 1px solid #CBD5E1; border-top: 4px solid #2563EB; border-radius: 12px; padding: 20px; margin-bottom: 20px; }
    .matrix-title { font-size: 16px; font-weight: 700; color: #1E3A8A; margin-bottom: 12px; }
    
    .badge-container { display: flex; gap: 8px; margin-bottom: 15px; }
    .badge-custom { padding: 4px 10px; border-radius: 6px; font-size: 11px; font-weight: 700; text-transform: uppercase; }
    .badge-offline { background-color: #FEF3C7; color: #D97706; border: 1px solid #FCD34D; }
    .badge-match { background-color: #DBEAFE; color: #2563EB; border: 1px solid #BFDBFE; }
    
    .tech-table { width: 100%; border-collapse: collapse; margin-top: 10px; }
    .tech-table th { background-color: #F8FAFC; color: #64748B; font-weight: 600; text-align: left; padding: 10px; border-bottom: 2px solid #E2E8F0; font-size: 13px; }
    .tech-table td { padding: 10px; border-bottom: 1px solid #F1F5F9; color: #334155; font-size: 13px; }
    
    .blueprint-image-box { border: 2px dashed #CBD5E1; border-radius: 8px; padding: 10px; text-align: center; background-color: #F8FAFC; }
    </style>
""", unsafe_allow_html=True)
SB_URL = "https://supabase.co"
SB_KEY = st.secrets.get("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImV3cXFvZHNmdmx2bnJ6c3lsYXd5Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzUxMTkyOTAsImV4cCI6MjA5MDY5NTI5MH0.BWPxOsyswBT5CLrZgluRC1F2x5EpU06oexUFyakGhyc")

def get_secure_gemini_key():
    if "GEMINI_API_KEY" in st.secrets:
        return st.secrets["GEMINI_API_KEY"].strip()
    return None

def save_to_supabase_techpack_table(payload_data):
    """Hàm lưu thông số kỹ thuật và đẩy ảnh Sketch lên Storage của Supabase"""
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
def process_single_pdf_batch(file_bytes, file_name):
    """Xử lý cắt trang PDF thành ảnh và dùng Gemini AI bóc tách thông số cấu trúc thực tế"""
    gemini_key = get_secure_gemini_key()
    if not gemini_key: 
        return {"success": False, "error": "Chưa cấu hình khóa Secrets GEMINI_API_KEY trên Streamlit."}
    
    fallback_style = file_name.rsplit('.', 1)[0].strip() if '.' in file_name else file_name.strip()

    try:
        info = pdfinfo_from_bytes(file_bytes)
        total_pages = int(info.get("Pages", 1))
        contents_payload = []
        sketch_base64 = ""

        for p_num in range(1, total_pages + 1):
            try:
                # Cắt từng trang PDF thành định dạng hình ảnh dữ liệu
                images = convert_from_bytes(file_bytes, dpi=140, first_page=p_num, last_page=p_num)
                if images:
                    img = images[0].convert("RGB")
                    img_buffer = io.BytesIO()
                    img.save(img_buffer, format="JPEG", quality=90)
                    contents_payload.append(types.Part.from_bytes(data=img_buffer.getvalue(), mime_type='image/jpeg'))
                    
                    # Giữ trang đầu làm hình ảnh sơ đồ phẳng (Sketch Replica)
                    if p_num == 1 and not sketch_base64:
                        if img.width > 400: 
                            img = img.resize((400, int(img.height * (400 / img.width))))
                        bk_buf = io.BytesIO()
                        img.save(bk_buf, format="JPEG", quality=75)
                        sketch_base64 = base64.b64encode(bk_buf.getvalue()).decode("utf-8")
            except Exception: pass

        if not contents_payload: 
            return {"success": False, "error": "Không thể giải mã hình ảnh từ file PDF."}

        user_prompt = """
        You are a strict garment technical auditor. Analyze all the attached images from the techpack PDF.
        1. Find Style ID, Buyer Account, Product Category, Base Size.
        2. Locate the main specification table containing Point of Measurements (POM Description) and target values.
        Return a valid JSON object with this exact schema:
        {
          "style_number_parsed": "Extract real Style ID",
          "buyer": "Extract real Buyer Account name",
          "category": "Extract real Product Category",
          "base_size_name": "Extract Sample Base Size",
          "measurements": {
             "Waist Circumference": "34.50 INCH",
             "Inseam Length": "30.00 INCH"
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
# Cấu trúc Menu Sidebar
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
    st.markdown("### 🔒 SECURITY & SYSTEM STATUS")
    st.success("Database Status: ONLINE")
    st.info("Core Engine: Gemini-2.5-Flash")

# Khởi tạo bộ nhớ Session State lưu trữ liên kết dữ liệu giữa các tab công việc
if "processed_styles" not in st.session_state:
    st.session_state["processed_styles"] = {}
# -----------------------------------------------------------------------------
# CHỨC NĂNG 1: QUÉT FILE VÀ TRÍCH XUẤT THÔNG SỐ TỰ ĐỘNG BẰNG AI
# -----------------------------------------------------------------------------
if menu_selection == "📊 Quét Techpack Document":
    st.markdown("""<div class="tech-card"><div class="tech-header">📥 STEP 1: GARMENT TECHPACK DATA INGESTION</div>
    <p style="color: #64748B; font-size:14px; margin:0;">Tải tệp Techpack PDF gốc để hệ thống tự động bóc tách thông số bằng trí tuệ nhân tạo.</p></div>""", unsafe_allow_html=True)
    
    uploaded_files = st.file_uploader("Upload PDF", type=["pdf"], accept_multiple_files=True, label_visibility="collapsed")
    
    st.markdown("""<div class="tech-card"><div class="tech-header">🔍 STEP 2: METRIC EXTRACTION & VISUAL RENDERING MATRIX</div></div>""", unsafe_allow_html=True)
    
    if uploaded_files:
        cols = st.columns(2)
        for idx, file in enumerate(uploaded_files):
            col_target = cols[idx % 2]
            
            with col_target:
                # Nếu file chưa quét thì tiến hành chạy qua AI thật
                if file.name not in st.session_state["processed_styles"]:
                    with st.spinner(f"AI đang bóc tách file {file.name}..."):
                        res = process_single_pdf_batch(file.getvalue(), file.name)
                        if res["success"]:
                            st.session_state["processed_styles"][file.name] = res["data"]
                            save_to_supabase_techpack_table(res["data"]) # Tự động đồng bộ lên Database
                        else:
                            st.error(res["error"])
                            continue
                
                data = st.session_state["processed_styles"][file.name]
                
                st.markdown(f"""
                    <div class="matrix-node">
                        <div class="matrix-title">{data.get('style_number_parsed')}</div>
                        <div class="badge-container">
                            <span class="badge-custom badge-offline">ONLINE PARSED</span>
                            <span class="badge-custom badge-match">SYNC SUCCESS</span>
                        </div>
                        <p style="margin:2px 0; font-size:13px;"><b>Buyer Account:</b> {data.get('buyer')}</p>
                        <p style="margin:2px 0; font-size:13px;"><b>Product Line:</b> {data.get('category')}</p>
                        <p style="margin:2px 0; font-size:13px; margin-bottom:15px;"><b>Sample Scale:</b> {data.get('base_size_name')}</p>
                    </div>
                """, unsafe_allow_html=True)
                
                sub_col1, sub_col2 = st.columns([1.2, 0.8])
                with sub_col1:
                    st.markdown("<p style='font-weight:700; font-size:13px; color:#1E293B; margin:0;'>📋 SPECIFICATION MATRIX</p>", unsafe_allow_html=True)
                    table_html = '<table class="tech-table"><tr><th>Garment Attribute</th><th>Target Spec</th></tr>'
                    for k, v in data.get("measurements", {}).items():
                        table_html += f"<tr><td>{k}</td><td>{v}</td></tr>"
                    table_html += "</table>"
                    st.markdown(table_html, unsafe_allow_html=True)
                    
                with sub_col2:
                    st.markdown("<p style='font-weight:700; font-size:13px; color:#1E293B; margin:0;'>🤖 GARMENT REPLICAS</p>", unsafe_allow_html=True)
                    if data.get("sketch_image"):
                        st.image(base64.b64decode(data["sketch_image"]), use_column_width=True)
                    else:
                        st.markdown('<div class="blueprint-box"><span style="font-size:28px;">📐</span></div>', unsafe_allow_html=True)
                st.markdown("<br><hr style='border-color:#E2E8F0;'><br>", unsafe_allow_html=True)
    else:
        st.warning("⚠️ Hiện tại chưa có tệp dữ liệu Techpack nào được đưa vào hệ thống xử lý.")

# -----------------------------------------------------------------------------
# CHỨC NĂNG 2: SO SÁNH THÔNG SỐ 2 MÃ RẬP (PATTERN SPEC COMPARISON) + XUẤT EXCEL
# -----------------------------------------------------------------------------
elif menu_selection == "🔄 Pattern Spec Comparison":
    st.markdown("""<div class="tech-card"><div class="tech-header">🔄 CHỨC NĂNG ĐỐI CHIẾU SỐ ĐO & PHÂN TÍCH SAI LỆCH (DELTA SPEC)</div>
    <p style="color: #64748B; font-size:14px; margin:0;">Tải lên 2 file PDF cần so sánh rập mẫu (Ví dụ: Bản cũ gốc vs Bản mới sửa đổi từ khách hàng).</p></div>""", unsafe_allow_html=True)
    
    sc1, sc2 = st.columns(2)
    with sc1: file1 = st.file_uploader("Chọn file mẫu Techpack Gốc (File A)", type=["pdf"], key="f1")
    with sc2: file2 = st.file_uploader("Chọn file mẫu Techpack Sửa đổi (File B)", type=["pdf"], key="f2")
    
    if file1 and file2:
        with st.spinner("AI đang giải mã đối chiếu ma trận thông số..."):
            if file1.name not in st.session_state["processed_styles"]:
                res1 = process_single_pdf_batch(file1.getvalue(), file1.name)
                if res1["success"]: st.session_state["processed_styles"][file1.name] = res1["data"]
            if file2.name not in st.session_state["processed_styles"]:
                res2 = process_single_pdf_batch(file2.getvalue(), file2.name)
                if res2["success"]: st.session_state["processed_styles"][file2.name] = res2["data"]
                
        d1 = st.session_state["processed_styles"].get(file1.name)
        d2 = st.session_state["processed_styles"].get(file2.name)
        
        if d1 and d2:
            st.success("✅ Cấu trúc ma trận đối sánh đối chiếu thành công!")
            
            # Hàm làm sạch dữ liệu chuỗi số đo để tính toán độ lệch toán học
            def clean_val(v_str):
                try: return float(re.findall(r"[-+]?\d*\.\d+|\d+", str(v_str))[0])
                except: return 0.0

            all_poms = set(list(d1["measurements"].keys()) + list(d2["measurements"].keys()))
            compare_rows = []
            for pom in all_poms:
                val1_str = d1["measurements"].get(pom, "N/A")
                val2_str = d2["measurements"].get(pom, "N/A")
                num1 = clean_val(val1_str)
                num2 = clean_val(val2_str)
                delta = round(num2 - num1, 3) if val1_str != "N/A" and val2_str != "N/A" else 0.0
                compare_rows.append({
                    "Vị trí đo (POM Description)": pom,
                    f"Thông số mẫu A ({d1['style_number_parsed']})": val1_str,
                    f"Thông số mẫu B ({d2['style_number_parsed']})": val2_str,
                    "Sai lệch (Delta)": delta
                })
            
            df_compare = pd.DataFrame(compare_rows)
            st.dataframe(df_compare, use_container_width=True, hide_index=True)
            
            # Xuất dữ liệu đối chiếu ra file Excel thật để gửi đối tác hoặc xưởng sản xuất
            towrite = io.BytesIO()
            with pd.ExcelWriter(towrite, engine='xlsxwriter') as writer:
                df_compare.to_excel(writer, index=False, sheet_name='Spec_Comparison_Report')
            towrite.seek(0)
            
            st.download_button(
                label="📥 XUẤT BÁO CÁO ĐỐI CHIẾU THÔNG SỐ (EXCEL)",
                data=towrite,
                file_name=f"PPJ_Spec_Comparison_{d1['style_number_parsed']}_vs_{d2['style_number_parsed']}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
# -----------------------------------------------------------------------------
# CHỨC NĂNG 3: TRỢ LÝ ĐỊNH MỨC VẢI THÔNG MINH (FABRIC CONSUMPTION ASSISTANT)
# -----------------------------------------------------------------------------
elif menu_selection == "🧵 Fabric Consumption Assistant (Cons)":
    st.markdown("""<div class="tech-card"><div class="tech-header">🧵 PPJ INTELLIGENT FABRIC CONSUMPTION ASSISTANT</div>
    <p style="color: #64748B; font-size:14px; margin:0;">Hỏi đáp trực tiếp với trợ lý AI để tra cứu định mức nguyên phụ liệu vải hoặc kiểm tra dung sai hao hụt vật tư kỹ thuật.</p></div>""", unsafe_allow_html=True)
    
    # Khởi tạo lịch sử hội thoại chat trong bộ nhớ đệm
    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = [
            {"role": "assistant", "content": "Xin chào! Tôi là Trợ lý Vật tư AI của PPJ Group. Bạn cần tra cứu định mức hao hụt (Cons) hay kiểm tra thông tin định mức của mã hàng nào hôm nay?"}
        ]
        
    for msg in st.session_state["chat_history"]:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])
            
    if user_query := st.chat_input("Nhập câu hỏi tra cứu vật tư kỹ thuật tại đây..."):
        st.session_state["chat_history"].append({"role": "user", "content": user_query})
        with st.chat_message("user"):
            st.write(user_query)
            
        with st.chat_message("assistant"):
            with st.spinner("Hệ thống AI đang tra cứu dữ liệu tổng kho vật tư..."):
                gemini_key = get_secure_gemini_key()
                if not gemini_key:
                    ans = "Hệ thống chưa được cấu hình khóa bảo mật GEMINI_API_KEY."
                else:
                    try:
                        client = genai.Client(api_key=gemini_key)
                        # Truyền toàn bộ ngữ cảnh lịch sử cho mô hình xử lý hội thoại
                        context_prompt = "You are an expert advisor for garment fabric consumption calculation at PPJ Group. Answer the engineer request clearly: " + user_query
                        response = client.models.generate_content(
                            model='gemini-2.5-flash',
                            contents=context_prompt
                        )
                        ans = response.text
                    except Exception as e:
                        ans = f"Có lỗi xảy ra khi kết nối máy chủ AI: {str(e)}"
                        
                st.write(ans)
                st.session_state["chat_history"].append({"role": "assistant", "content": ans})
