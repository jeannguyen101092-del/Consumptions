import base64
import io
import json
import re
import requests
import streamlit as st
import pandas as pd
import time
from pdf2image import convert_from_bytes, pdfinfo_from_bytes
from google import genai
from google.genai import types

# BẮT BUỘC: Cấu hình trang phải đặt đầu tiên
st.set_page_config(
    page_title="PPJ Core AI - Techpack R&D System",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# SIÊU CẤU HÌNH GIAO DIỆN KIẾN TRÚC CYBER SLATE
st.markdown("""
    <style>
    /* Đồng bộ màu nền toàn hệ thống sang màu tối công nghiệp - Slate Dark */
    .stApp, [data-testid="stAppViewContainer"] {
        background-color: #0B0F19 !important;
        font-family: 'JetBrains Mono', 'Segoe UI', monospace !important;
    }
    
    /* Giao diện Sidebar đồng khối gắn liền với Dashboard */
    [data-testid="stSidebar"] {
        background-color: #0F172A !important;
        border-right: 1px solid #1E293B !important;
        min-width: 290px;
    }
    
    /* Khung định danh thương hiệu PPJ Tech */
    .ppj-brand-card {
        background: linear-gradient(135deg, #1E3A8A 0%, #0284C7 100%);
        padding: 18px;
        border-radius: 8px;
        text-align: center;
        margin-bottom: 20px;
        border: 1px solid #38BDF8;
        box-shadow: 0 0 15px rgba(2, 132, 199, 0.4);
    }
    .ppj-brand-main { font-size: 20px; font-weight: 800; color: #FFFFFF; letter-spacing: 2px; margin: 0; }
    .ppj-brand-sub { font-size: 10px; color: #38BDF8; font-weight: 600; text-transform: uppercase; margin-top: 4px; }

    /* Thiết kế Khung Kỹ thuật Đóng Khung Hoành Tráng (Unified Industrial Card) */
    .tech-panel {
        background-color: #111827 !important;
        border: 1px solid #1F2937 !important;
        border-top: 3px solid #0284C7 !important;
        border-radius: 8px;
        padding: 20px;
        margin-bottom: 20px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }
    .tech-panel-title {
        font-size: 14px; font-weight: 700; color: #38BDF8; 
        text-transform: uppercase; letter-spacing: 1px; margin-bottom: 12px;
        display: flex; align-items: center; gap: 8px;
    }
    
    /* Ma trận bảng số đo Cyber Matrix Table */
    .matrix-wrapper {
        max-height: 400px; overflow-y: auto; 
        border: 1px solid #1F2937; border-radius: 6px; margin-top: 10px;
    }
    .matrix-table { width: 100%; border-collapse: collapse; text-align: left; }
    .matrix-table th {
        background-color: #1F2937; color: #9CA3AF; font-weight: 600; 
        padding: 10px 14px; font-size: 12px; text-transform: uppercase;
        position: sticky; top: 0; z-index: 5; border-bottom: 2px solid #374151;
    }
    .matrix-table td { 
        padding: 10px 14px; border-bottom: 1px solid #1F2937; 
        color: #E5E7EB; font-size: 13px; font-weight: 500;
    }
    .matrix-table tr:hover { background-color: #111827; }
    
    /* Định dạng nhãn màu chỉ số Delta Spec chênh lệch */
    .delta-up { background-color: rgba(22, 101, 52, 0.2); color: #4ADE80; font-weight: 700; padding: 2px 6px; border-radius: 4px; font-size: 12px; border: 1px solid #22C55E; }
    .delta-down { background-color: rgba(153, 27, 27, 0.2); color: #F87171; font-weight: 700; padding: 2px 6px; border-radius: 4px; font-size: 12px; border: 1px solid #EF4444; }
    .delta-steady { color: #9CA3AF; font-size: 12px; }

    /* Tinh chỉnh các dòng Text hiển thị thông tin sản xuất */
    .spec-label { font-size: 13px; color: #9CA3AF; margin-bottom: 4px; }
    .spec-value { font-size: 14px; color: #F3F4F6; font-weight: 600; margin-bottom: 12px; }
    
    /* Thanh hiển thị trạng thái hệ thống */
    .sys-status-bar {
        background-color: #111827; border: 1px solid #1F2937;
        padding: 8px 12px; border-radius: 6px; font-size: 11px; color: #9CA3AF;
    }
    </style>
""", unsafe_allow_html=True)
SB_URL = "https://supabase.co"
SB_KEY = st.secrets.get("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImV3cXFvZHNmdmx2bnJ6c3lsYXd5Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzUxMTkyOTAsImV4cCI6MjA5MDY5NTI5MH0.BWPxOsyswBT5CLrZgluRC1F2x5EpU06oexUFyakGhyc")

def get_secure_gemini_key():
    if "GEMINI_API_KEY" in st.secrets:
        return st.secrets["GEMINI_API_KEY"].strip()
    return None

def save_to_supabase_techpack_table(payload_data):
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
        clean_dict = {str(k): str(v) for k, v in dict(payload_data.get("measurements", {})).items()}

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
    try:
        headers = {"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}"}
        url = f"{SB_URL.rstrip('/')}/rest/v1/san_pham"
        query_params = {"select": "style_name,article_name,consumption_type,material_size,uom,consumption_value,notes", "limit": 10}
        if search_keyword:
            clean_kw = str(search_keyword).strip()
            query_params["style_name"] = f"ilike.*{clean_kw.split('-')[-1].strip()}*" if '-' in clean_kw else f"ilike.*{clean_kw}*"
        res = requests.get(url, headers=headers, params=query_params, timeout=15)
        return res.json() if 200 <= res.status_code <= 299 else []
    except Exception: return []

def process_single_pdf_batch(file_bytes, file_name):
    gemini_key = get_secure_gemini_key()
    if not gemini_key: return {"success": False, "error": "Chưa cấu hình khóa Secrets GEMINI_API_KEY."}
    fallback_style = file_name.rsplit('.', 1)[0].strip() if '.' in file_name else file_name.strip()
    try:
        info = pdfinfo_from_bytes(file_bytes)
        total_pages = int(info.get("Pages", 1))
        contents_payload = []
        sketch_base64 = ""

        for p_num in range(1, total_pages + 1):
            try:
                images = convert_from_bytes(file_bytes, dpi=150, first_page=p_num, last_page=p_num)
                if images:
                    img = images[0].convert("RGB")
                    img_buffer = io.BytesIO()
                    img.save(img_buffer, format="JPEG", quality=90)
                    contents_payload.append(types.Part.from_bytes(data=img_buffer.getvalue(), mime_type='image/jpeg'))
                    
                    if p_num == 1 and not sketch_base64:
                        if img.width > 450: img = img.resize((450, int(img.height * (450 / img.width))))
                        bk_buf = io.BytesIO()
                        img.save(bk_buf, format="JPEG", quality=80)
                        sketch_base64 = base64.b64encode(bk_buf.getvalue()).decode("utf-8")
            except Exception: pass

        user_prompt = """
        You are a strict garment technical auditor. Analyze the techpack PDF images row-by-row.
        Extract EVERY SINGLE measurement specification row found in the grid for the base sample size. Do not skip or summarize.
        Return a valid JSON object with this exact schema:
        {
          "style_number_parsed": "Extract real Style ID",
          "buyer": "Extract real Buyer Account name",
          "category": "Extract real Product Category line",
          "base_size_name": "Extract Sample Base Size",
          "measurements": { "POM Name": "Value" }
        }
        """
        contents_payload.append(user_prompt)
        client = genai.Client(api_key=gemini_key)
        response = client.models.generate_content(model='gemini-2.5-flash', contents=contents_payload, config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.0))
        parsed_data = json.loads(response.text.strip())
        parsed_data["sketch_image"] = sketch_base64
        if not parsed_data.get("style_number_parsed"): parsed_data["style_number_parsed"] = fallback_style
        return {"success": True, "data": parsed_data}
    except Exception as e: return {"success": False, "error": f"Lỗi AI: {str(e)}"}
with st.sidebar:
    st.markdown("""
        <div class="sidebar-brand-container">
            <div class="sidebar-brand-title">PPJ GROUP</div>
            <div class="sidebar-brand-subtitle">TECHPACK MANAGEMENT CORE AI</div>
        </div>
    """, unsafe_allow_html=True)
    
    st.markdown("<p style='font-size:11px; font-weight:700; color:#64748B; margin: 15px 0 5px 5px; letter-spacing:0.5px;'>🏭 AUTOMATION FACTORY</p>", unsafe_allow_html=True)
    menu_selection = st.sidebar.radio(
        label="Chức năng hệ thống",
        options=["📊 Quét Techpack Document", "🔄 Pattern Spec Comparison", "🧵 Fabric Consumption Assistant (Cons)"],
        label_visibility="collapsed"
    )
    st.markdown("---")
    st.success("DATABASE ACCESS: SECURED")
    st.info("ANALYTICS ENGINE: COMPLY")

if "processed_styles" not in st.session_state:
    st.session_state["processed_styles"] = {}

# -----------------------------------------------------------------------------
# CHỨC NĂNG 1: QUÉT TỰ ĐỘNG BẰNG AI VÀ LƯU HÀNG LOẠT (BULK SAVE MULTI-BATCH)
# -----------------------------------------------------------------------------
if menu_selection == "📊 Quét Techpack Document":
    st.markdown('<div class="component-title-box">📊 MULTI-BATCH GARMENT SPECIFICATION MATRIX</div>', unsafe_allow_html=True)
    
    st.markdown("""<div class="card-container"><div class="card-section-header">📥 INGESTION ENGINE</div>
    <p style="color: #94A3B8; font-size:13px; margin:0 0 15px 0;">Hệ thống tự động cắt trang, khử nhiễu đồ họa phẳng và gọi API mạng nơ-ron tích hợp để bóc tách thông số hàng loạt.</p></div>""", unsafe_allow_html=True)
    uploaded_files = st.file_uploader("Upload Techpack PDF", type=["pdf"], accept_multiple_files=True, label_visibility="collapsed")
    
    if uploaded_files:
        files_to_render = []
        for file in uploaded_files:
            if file.name not in st.session_state["processed_styles"]:
                with st.spinner(f"Core AI đang bóc tách mô hình {file.name}..."):
                    res = process_single_pdf_batch(file.getvalue(), file.name)
                    if res["success"]: st.session_state["processed_styles"][file.name] = res["data"]
                    else: st.error(f"FAIL ENGINE [{file.name}]: {res['error']}")
            if file.name in st.session_state["processed_styles"]:
                files_to_render.append(file.name)

        if files_to_render:
            if st.button("💾 SAVE ALL PROCESSED MATRIX TO SUPABASE MASTER DB", key="bulk_save_all_btn", type="primary", use_container_width=True):
                success_count = 0
                with st.spinner("Đang đồng bộ cổng dữ liệu nhị phân hàng loạt lên Supabase Cloud..."):
                    for f_name in files_to_render:
                        style_data = st.session_state["processed_styles"][f_name]
                        if save_to_supabase_techpack_table(style_data): success_count += 1
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
                        st.markdown("<p style='font-weight:700; font-size:12px; color:#F8FAFC; letter-spacing:0.5px;'>📋 SPECIFICATION DATA GRID</p>", unsafe_allow_html=True)
                        table_html = '<div class="data-table-container"><table class="industrial-table"><thead><tr><th>Point of Measurement</th><th>Target Spec</th></tr></thead><tbody>'
                        for k, v in data.get("measurements", {}).items():
                            table_html += f"<tr><td>{k}</td><td>{v}</td></tr>"
                        st.markdown(table_html + "</tbody></table></div>", unsafe_allow_html=True)
                    with sub_col2:
                        st.markdown("<p style='font-weight:700; font-size:12px; color:#F8FAFC; letter-spacing:0.5px;'>📐 GARMENT FLAT SKETCH</p>", unsafe_allow_html=True)
                        if data.get("sketch_image"): 
                            st.image(base64.b64decode(data["sketch_image"]), use_column_width=True)
                    st.markdown("<br><hr style='border-color:#334155;'><br>", unsafe_allow_html=True)
    else:
        st.markdown("""<div style="background-color: #1E293B; border-left: 4px solid #F59E0B; padding: 15px; border-radius: 6px; color: #FBBF24; font-size: 13.5px; font-weight: 500;">
        ⚠️ INITIALIZATION SYSTEM IDLE: Hiện tại chưa có tệp dữ liệu Techpack nào được nạp vào hệ thống để AI khởi chạy mô hình.</div>""", unsafe_allow_html=True)
# -----------------------------------------------------------------------------
# CHỨC NĂNG 2: ĐỐI CHIẾU SO SÁNH HAI MÃ RẬP KHÁC NHAU (PATTERN SPEC COMPARISON)
# -----------------------------------------------------------------------------
elif menu_selection == "🔄 Pattern Spec Comparison":
    st.markdown('<div class="component-title-box">🔄 DIFFERENTIAL GEOMETRY & DELTA SPEC EVALUATOR</div>', unsafe_allow_html=True)
    
    st.markdown("""<div class="card-container"><div class="card-section-header">🔍 CONFIGURATION SELECTION</div>
    <p style="color: #94A3B8; font-size:13px; margin:0 0 15px 0;">Tải lên hai tệp bản vẽ kỹ thuật dệt may độc lập để tiến hành lập luận so sánh và tính toán toán học các khoảng chênh lệch rập mẫu.</p></div>""", unsafe_allow_html=True)
    
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
                    delta_style = "background-color:rgba(16,185,129,0.15); color:#34D399; font-weight:700; padding:2px 8px; border-radius:4px; font-size:12px; border:1px solid rgba(16,185,129,0.3);"
                    delta_text = f"+{delta}"
                elif delta < 0:
                    delta_style = "background-color:rgba(239,68,68,0.15); color:#F87171; font-weight:700; padding:2px 8px; border-radius:4px; font-size:12px; border:1px solid rgba(239,68,68,0.3);"
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
            
            df_compare = pd.DataFrame(compare_rows_for_df)
            towrite = io.BytesIO()
            with pd.ExcelWriter(towrite, engine='xlsxwriter') as writer: 
                df_compare.to_excel(writer, index=False, sheet_name='Spec_Report')
                workbook  = writer.book
                worksheet = writer.sheets['Spec_Report']
                # ✨ ĐÃ SỬA LỖI CÚ PHÁP: Bổ sung dấu phẩy ngăn cách giữa các thuộc tính định dạng xlsxwriter
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
                label="📥 EXPORT PRODUCTION DELTA SHEET (EXCEL)", 
                data=towrite, 
                file_name=f"PPJ_Delta_Spec_Comparison.xlsx", 
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
# -----------------------------------------------------------------------------
# CHỨC NĂNG 3: TRỢ LÝ ĐỊNH MỨC VẢI (ISOLATED DATA PIPELINE & RETRY LAB - ĐOẠN 6A)
# -----------------------------------------------------------------------------
elif menu_selection == "🧵 Fabric Consumption Assistant (Cons)":
    st.markdown('<div class="component-title-box">🧵 INTELLIGENT FABRIC CONSUMPTION ASSISTANT (R&D CORES)</div>', unsafe_allow_html=True)
    
    control_col1, control_col2 = st.columns([3.3, 0.7])
    with control_col1:
        st.markdown("<p style='font-weight:700; font-size:12px; color:#F8FAFC;'>📁 INGEST NEW STYLE REPRINTS</p>", unsafe_allow_html=True)
        chat_file = st.file_uploader("Upload Techpack file", type=["pdf", "jpg", "jpeg", "png"], key="chat_uploader", label_visibility="collapsed")
        if chat_file: st.success(f"📎 DATASTREAM PIPELINE BOUND: Tiếp nhận thành công file {chat_file.name}")
            
    with control_col2:
        st.markdown("<p style='font-weight:700; font-size:12px; color:#F8FAFC;'>🧹 RESET CORE</p>", unsafe_allow_html=True)
        if st.button("🗑️ PURGE CHAT CACHE", use_container_width=True, type="secondary"):
            import time
            if "chat_history" in st.session_state: del st.session_state["chat_history"]
            st.success("🔄 MEMORY CLEARED")
            time.sleep(0.5)
            st.rerun()

    st.markdown("---")
    
    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = [
            {"role": "assistant", "content": "Welcome to PPJ Textile R&D Engine. Hãy tải lên sơ đồ rập mã mới, hệ thống sẽ bóc tách biệt lập, tự động đối soát kho Master DB và lập luận toán học để kết xuất định mức vải chính xác."}
        ]
        
    for msg in st.session_state["chat_history"]:
        with st.chat_message(msg["role"]): st.write(msg["content"])
    # LUỒNG PHÂN TÍCH ĐÓNG BĂNG DỮ LIỆU CHỐNG LẪN LỘN MÃ HÀNG (ĐOẠN 6B)
    if user_query := st.chat_input("Nhập yêu cầu phân tích định mức vải và đối soát sai lệch..."):
        st.session_state["chat_history"].append({"role": "user", "content": user_query})
        with st.chat_message("user"): st.write(user_query)
            
        with st.chat_message("assistant"):
            with st.spinner("AI R&D Engine đang thiết lập ma trận đối soát và tính toán toán học..."):
                gemini_key = get_secure_gemini_key()
                if not gemini_key: 
                    ans = "CRITICAL SERVER BREAKDOWN: AI API Token is missing."
                else:
                    try:
                        client = genai.Client(api_key=gemini_key)
                        contents_payload = []
                        new_style_id_detected = "UNKNOWN_STYLE"
                        new_style_raw_text = ""
                        
                        if chat_file:
                            file_bytes = chat_file.getvalue()
                            img_payload = []
                            if chat_file.name.lower().endswith('.pdf'):
                                images = convert_from_bytes(file_bytes, dpi=140, first_page=1, last_page=1)
                                if images:
                                    img_buf = io.BytesIO()
                                    images[0].convert("RGB").save(img_buf, format="JPEG")
                                    img_payload.append(types.Part.from_bytes(data=img_buf.getvalue(), mime_type='image/jpeg'))
                            else:
                                img_payload.append(types.Part.from_bytes(data=file_bytes, mime_type='image/jpeg'))
                            
                            extraction_prompt = """
                            Analyze this technical sheet image. Extract the genuine 'Style ID' / 'Mã hàng'.
                            Return a valid JSON with this exact schema:
                            {"detected_style_id": "Text of Style ID", "all_specs_text": "Specs list as plain text"}
                            """
                            img_payload.append(extraction_prompt)
                            
                            for ext_attempt in range(3):
                                try:
                                    extraction_res = client.models.generate_content(model='gemini-2.5-flash', contents=img_payload, config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.0))
                                    parsed_meta = json.loads(extraction_res.text.strip())
                                    new_style_id_detected = parsed_meta.get("detected_style_id", "UNKNOWN_STYLE").strip()
                                    new_style_raw_text = parsed_meta.get("all_specs_text", "")
                                    break
                                except Exception:
                                    import time
                                    time.sleep(2 * (ext_attempt + 1))
                            
                            if chat_file.name.lower().endswith('.pdf') and images:
                                img_buf = io.BytesIO()
                                images[0].convert("RGB").save(img_buf, format="JPEG")
                                contents_payload.append(types.Part.from_bytes(data=img_buf.getvalue(), mime_type='image/jpeg'))
                            elif not chat_file.name.lower().endswith('.pdf'):
                                contents_payload.append(types.Part.from_bytes(data=file_bytes, mime_type='image/jpeg'))
                        
                        if new_style_id_detected == "UNKNOWN_STYLE" or not chat_file:
                            found_keywords = re.findall(r'[A-Za-z0-9]+[-–][A-Za-z0-9]+|[A-Za-z0-9]{4,}', user_query)
                            if found_keywords: new_style_id_detected = found_keywords[0]

                        db_results = get_historical_fabric_consumption_from_db(search_keyword=new_style_id_detected)
                        
                        db_context = f"\n\n[SUPABASE DB ISOLATED RECORDS FOR STYLE: {new_style_id_detected}]:\n"
                        if db_results:
                            for item in db_results:
                                db_context += f"- Mã gốc: {item.get('style_name')}\n  + Vải: {item.get('article_name')}\n  + Định mức (Cons): {item.get('consumption_value')} {item.get('uom')}\n  + Ghi chú: {item.get('notes')}\n"
                        else:
                            fallback_key = new_style_id_detected.split('-')[-1] if '-' in new_style_id_detected else new_style_id_detected[:4]
                            backup_results = get_historical_fabric_consumption_from_db(search_keyword=fallback_key)
                            if backup_results:
                                db_context += f"⚠️ Không có định mức trực tiếp cho mã {new_style_id_detected}. Dưới đây là các mã cơ sở cùng dòng rập gốc để đối sánh:\n"
                                for item in backup_results[:4]:
                                    db_context += f"- Mã hàng nhóm: {item.get('style_name')}, Vải: {item.get('article_name')}, Định mức gốc: {item.get('consumption_value')} {item.get('uom')}, Cấu trúc: {item.get('notes')}\n"
                            else:
                                db_context += "❌ Không tìm thấy mã hàng dệt may khả nghi tương thích trong Master DB."

                        system_instruction = (
                            "You are the Lead R&D Expert and Garment Technical Auditor at PPJ Group.\n"
                            "CRITICAL DATA INTEGRITY RULE:\n"
                            "You must ONLY compare the newly uploaded garment style with the historical database records provided inside the context below. Do NOT mix data from different styles.\n\n"
                            "REQUIRED 3-STEP REPORT FORMAT:\n"
                            f"1. PHÂN TÍCH MÃ MỚI ĐÃ BÓC TÁCH: Xác nhận rõ mã số ID vừa đọc được từ file là '{new_style_id_detected}' và liệt kê tóm tắt ma trận thông số kích thước của nó.\n"
                            f"2. ĐỐI CHIẾU MÃ KHO TƯƠNG ĐỒNG: Chỉ được chọn mã hàng xuất hiện trong danh sách đối chiếu kho của mã '{new_style_id_detected}' bên dưới. Chỉ rõ mã cũ tương đồng đó có định mức tiêuthu gốc là bao nhiêu.\n"
                            "3. LẬP LUẬN TOÁN HỌC TÍNH ĐỊNH MỨC THEO DELTA SPEC: Đo lường sự chênh lệch kích cỡ số đo (Delta Spec) giữa mã hàng mới và mã cũ tương đồng vừa chọn. Dựa trên độ lệch đó để cộng thêm hoặc giảm trừ vật tư, đưa ra kết quả định mức tiêu thụ vải dự kiến cuối cùng cho mã mới.\n\n"
                            "Trình bày chuyên nghiệp bằng tiếng Việt kỹ thuật dệt may."
                        )
                        
                        full_prompt = f"{system_instruction}\n\nYêu cầu kỹ sư: {user_query}\n\n[Thông số file mới]:\n{new_style_raw_text if new_style_raw_text else 'Không đính kèm file'}\n{db_context}"
                        contents_payload.append(full_prompt)
                        
                        ans = ""
                        for attempt in range(5):
                            try:
                                response = client.models.generate_content(model='gemini-2.5-flash', contents=contents_payload)
                                ans = response.text
                                break
                            except Exception as e:
                                if "503" in str(e) or "UNAVAILABLE" in str(e):
                                    if attempt < 4:
                                        import time
                                        time.sleep(2 * (attempt + 1))
                                        continue
                                raise e
                                
                    except Exception as e: 
                        ans = f"Hệ thống đang điều phối hàng đợi mạng nơ-ron quốc tế. Hãy gửi lại sau vài giây! Chi tiết: {str(e)}"
                        
                st.write(ans)
                st.session_state["chat_history"].append({"role": "assistant", "content": ans})
