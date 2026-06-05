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
    /* Tổng thể nền và Sidebar */
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
    
    # ✨ ĐÃ SỬA LỖI: Lấy chính xác phần tử đầu tiên [0] của List sau khi rsplit trước khi gọi .strip()
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
                    img = images[0].convert("RGB") # ĐÃ SỬA LỖI: Lấy phần tử ảnh đầu tiên của danh sách các trang
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

if "processed_styles" not in st.session_state:
    st.session_state["processed_styles"] = {}

# TAB 1: QUÉT LƯU THÔNG SỐ VÀ HÌNH ẢNH SKETCH
if menu_selection == "📊 Quét Techpack Document":
    st.markdown("""<div class="tech-card"><div class="tech-header">📥 STEP 1: GARMENT TECHPACK DATA INGESTION</div></div>""", unsafe_allow_html=True)
    uploaded_files = st.file_uploader("Upload PDF", type=["pdf"], accept_multiple_files=True, label_visibility="collapsed")
    st.markdown("""<div class="tech-card"><div class="tech-header">🔍 STEP 2: METRIC EXTRACTION & VISUAL RENDERING MATRIX</div></div>""", unsafe_allow_html=True)
    
    if uploaded_files:
        cols = st.columns(2)
        for idx, file in enumerate(uploaded_files):
            col_target = cols[idx % 2]
            with col_target:
                if file.name not in st.session_state["processed_styles"]:
                    with st.spinner(f"AI đang bóc tách file {file.name}..."):
                        res = process_single_pdf_batch(file.getvalue(), file.name)
                        if res["success"]: st.session_state["processed_styles"][file.name] = res["data"]
                        else: st.error(res["error"]); continue
                
                data = st.session_state["processed_styles"][file.name]
                st.markdown(f"""<div class="matrix-node"><div class="matrix-title">{data.get('style_number_parsed')}</div>
                    <p style="margin:2px 0; font-size:13px;"><b>Buyer:</b> {data.get('buyer')}</p>
                    <p style="margin:2px 0; font-size:13px;"><b>Product Line:</b> {data.get('category')}</p></div>""", unsafe_allow_html=True)
                
                sub_col1, sub_col2 = st.columns([1.2, 0.8])
                with sub_col1:
                    st.markdown("<p style='font-weight:700; font-size:13px;'>📋 SPECIFICATION MATRIX</p>", unsafe_allow_html=True)
                    table_html = '<table class="tech-table"><tr><th>Garment Attribute</th><th>Target Spec</th></tr>'
                    for k, v in data.get("measurements", {}).items():
                        table_html += f"<tr><td>{k}</td><td>{v}</td></tr>"
                    st.markdown(table_html + "</table>", unsafe_allow_html=True)
                with sub_col2:
                    st.markdown("<p style='font-weight:700; font-size:13px;'>🤖 GARMENT REPLICAS</p>", unsafe_allow_html=True)
                    if data.get("sketch_image"): st.image(base64.b64decode(data["sketch_image"]), use_column_width=True)
                
                if st.button(f"💾 LƯU MÃ {data.get('style_number_parsed')} VÀO MASTER DB", key=f"btn_save_{file.name}", use_container_width=True):
                    if save_to_supabase_techpack_table(data): st.success("🎉 Đã lưu trữ thành công!")
                    else: st.error("❌ Lỗi lưu dữ liệu.")

# TAB 2: ĐỐI CHIẾU SO SÁNH HAI MÃ RẬP KHÁC NHAU
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
            def clean_val(v_str):
                try: return float(re.findall(r"[-+]?\d*\.\d+|\d+", str(v_str)))
                except: return 0.0
            all_poms = set(list(d1["measurements"].keys()) + list(d2["measurements"].keys()))
            compare_rows = []
            for pom in all_poms:
                val1 = d1["measurements"].get(pom, "N/A"); val2 = d2["measurements"].get(pom, "N/A")
                delta = round(clean_val(val2) - clean_val(val1), 3) if val1 != "N/A" and val2 != "N/A" else 0.0
                compare_rows.append({"Vị trí đo (POM)": pom, f"Mẫu A ({d1['style_number_parsed']})": val1, f"Mẫu B ({d2['style_number_parsed']})": val2, "Sai lệch (Delta)": delta})
            df_compare = pd.DataFrame(compare_rows)
            st.dataframe(df_compare, use_container_width=True, hide_index=True)
            towrite = io.BytesIO()
            with pd.ExcelWriter(towrite, engine='xlsxwriter') as writer: df_compare.to_excel(writer, index=False, sheet_name='Report')
            towrite.seek(0)
            st.download_button(label="📥 XUẤT BÁO CÁO ĐỐI CHIẾU THÔNG SỐ (EXCEL)", data=towrite, file_name="PPJ_Spec_Comparison.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
elif menu_selection == "🧵 Fabric Consumption Assistant (Cons)":
    st.markdown("""<div class="tech-card"><div class="tech-header">🧵 PPJ INTELLIGENT FABRIC CONSUMPTION ASSISTANT</div>
    <p style="color: #64748B; font-size:14px; margin:0;">Hỏi đáp và tải lên tài liệu mới để AI tự động trích xuất thông số, đồng thời truy tìm các mã hàng có định mức tương đồng trong kho dữ liệu lịch sử Supabase.</p></div>""", unsafe_allow_html=True)
    
    # Khu vực tải lên tài liệu mới trực tiếp ngay trong chức năng Chat AI Assistant
    st.markdown("##### 📁 TẢI LÊN FILE SƠ ĐỒ HOẶC TECHPACK MỚI ĐỂ ĐỐI CHIẾU ĐỊNH MỨC KHO")
    chat_file = st.file_uploader("Upload tài liệu vật tư phụ trợ tại đây", type=["pdf", "jpg", "jpeg", "png"], key="chat_uploader")
    
    if chat_file:
        st.success(f"📎 Đã tiếp nhận thành công tài liệu phụ trợ: {chat_file.name}")
    
    st.markdown("---")
    
    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = [
            {"role": "assistant", "content": "Xin chào! Tôi là Trợ lý Vật tư AI của PPJ Group. Hãy nhập mã hàng hoặc tải lên bản vẽ, tôi sẽ giúp bạn trích xuất thông số định mức vật tư và đối chiếu mã hàng tương đồng trong kho!"}
        ]
        
    for msg in st.session_state["chat_history"]:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])
            
    if user_query := st.chat_input("Nhập yêu cầu hỏi đáp hoặc tra cứu mã hàng tại đây..."):
        st.session_state["chat_history"].append({"role": "user", "content": user_query})
        with st.chat_message("user"):
            st.write(user_query)
            
        with st.chat_message("assistant"):
            with st.spinner("AI đang giải mã thông tin văn bản và thực hiện quét kho dữ liệu lịch sử Supabase..."):
                gemini_key = get_secure_gemini_key()
                if not gemini_key:
                    ans = "Hệ thống chưa được cấu hình khóa bảo mật GEMINI_API_KEY."
                else:
                    try:
                        # BƯỚC 1: Tìm kiếm dữ liệu mã hàng tương đồng thực tế từ Database Supabase dựa trên từ khóa người dùng nhập
                        extracted_keywords = re.findall(r'[A-Za-z0-9]+[-–][A-Za-z0-9]+|[A-Za-z0-9]{4,}', user_query)
                        search_key = extracted_keywords[0] if extracted_keywords else user_query
                        
                        db_results = get_historical_fabric_consumption_from_db(search_keyword=search_key)
                        
                        db_context = ""
                        if db_results:
                            db_context = "\n\n[DỮ LIỆU THỰC TẾ TRONG KHO SUPABASE PHÙ HỢP TÌM THẤY]:\n"
                            for item in db_results:
                                db_context += f"- Mã hàng: {item.get('style_name')}, Nguyên liệu: {item.get('article_name')}, Định mức thực tế: {item.get('consumption_value')} {item.get('uom')}, Ghi chú kỹ thuật: {item.get('notes')}\n"
                        else:
                            db_context = "\n\n[DỮ LIỆU KHO]: Không tìm thấy mã hàng nào khớp hoàn toàn trong danh sách lịch sử hiện tại. Cần tính toán định mức mới dựa trên tài liệu đính kèm."

                        # BƯỚC 2: Gọi AI xử lý kết hợp tài liệu đính kèm (nếu có) và dữ liệu lịch sử từ Database để trả lời
                        client = genai.Client(api_key=gemini_key)
                        
                        contents_payload = []
                        if chat_file:
                            file_bytes = chat_file.getvalue()
                            if chat_file.name.lower().endswith('.pdf'):
                                # Nếu là file pdf mới tải lên, chuyển đổi trang đầu làm dữ liệu đầu vào cho Chat AI bóc tách thông số hình ảnh
                                images = convert_from_bytes(file_bytes, dpi=130, first_page=1, last_page=1)
                                if images:
                                    img_buf = io.BytesIO()
                                    images[0].convert("RGB").save(img_buf, format="JPEG")
                                    contents_payload.append(types.Part.from_bytes(data=img_buf.getvalue(), mime_type='image/jpeg'))
                            else:
                                contents_payload.append(types.Part.from_bytes(data=file_bytes, mime_type='image/jpeg'))
                        
                        system_instruction = (
                            "You are an elite garment technical auditor and fabric consumption expert at PPJ Group. "
                            "Analyze the engineer prompt and use the provided database history records to perform calculations, "
                            "compare consumption values (Cons), or find highly similar garments. Answer professionally in Vietnamese.\n"
                        )
                        
                        full_prompt = system_instruction + f"Câu hỏi của kỹ sư: {user_query}" + db_context
                        contents_payload.append(full_prompt)
                        
                        response = client.models.generate_content(
                            model='gemini-2.5-flash',
                            contents=contents_payload
                        )
                        ans = response.text
                    except Exception as e:
                        ans = f"Có lỗi xảy ra trong quá trình tính toán hoặc đối chiếu dữ liệu: {str(e)}"
                        
                st.write(ans)
                st.session_state["chat_history"].append({"role": "assistant", "content": ans})
