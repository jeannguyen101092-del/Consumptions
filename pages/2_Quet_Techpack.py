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

# CẤU HÌNH DATABASE
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
                storage_headers = {"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}", "Content-Type": "image/jpeg", "x-upsert": "true"}
                clean_filename = re.sub(r'[^a-zA-Z0-9_-]', '', style_name_db)
                storage_url = f"{SB_URL.rstrip('/')}/storage/v1/object/kho_anh/{clean_filename}.jpg"
                upload_res = requests.post(storage_url, headers=storage_headers, data=image_data, timeout=20)
                if 200 <= upload_res.status_code <= 299: public_image_url = f"{SB_URL.rstrip('/')}/storage/v1/object/public/kho_anh/{clean_filename}.jpg"
            except Exception: pass
        headers = {"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}", "Content-Type": "application/json", "Prefer": "resolution=merge-duplicates"}
        insert_url = f"{SB_URL.rstrip('/')}/rest/v1/thong_so_techpack"
        clean_dict = {str(k): str(v) for k, v in dict(payload_data.get("measurements", {})).items()}
        db_payload = {"StyleName": style_name_db, "Buyer": payload_data.get("buyer"), "Category": payload_data.get("category"), "BaseSize": payload_data.get("base_size_name"), "DetailedMeasurements": clean_dict, "SketchURL": public_image_url}
        response = requests.post(insert_url, headers=headers, json=[db_payload], timeout=15)
        return 200 <= response.status_code <= 299
    except Exception: return False

def process_single_pdf_batch(file_bytes, file_name):
    gemini_key = get_secure_gemini_key()
    if not gemini_key: return {"success": False, "error": "Missing Gemini Key."}
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
            images = convert_from_bytes(file_bytes, dpi=160, first_page=p_num, last_page=p_num)
            if images:
                img = images[0].convert("RGB")
                img_buffer = io.BytesIO()
                img.save(img_buffer, format="JPEG", quality=95)
                contents_payload.append(types.Part.from_bytes(data=img_buffer.getvalue(), mime_type='image/jpeg'))
                if p_num == 1 and not sketch_base64:
                    if img.width > 450: img = img.resize((450, int(img.height * (450 / img.width))))
                    bk_buf = io.BytesIO()
                    img.save(bk_buf, format="JPEG", quality=85)
                    sketch_base64 = base64.b64encode(bk_buf.getvalue()).decode("utf-8")
        user_prompt = "Extract technical specs chart grid row by row. Return a valid JSON object matching this schema: {'style_number_parsed': 'Style ID', 'buyer': 'Buyer', 'category': 'Product Line', 'base_size_name': 'Base Size', 'measurements': {'POM 1': 'Value 1'}}"
        contents_payload.append(user_prompt)
        client = genai.Client(api_key=gemini_key)
        response = client.models.generate_content(model='gemini-2.5-flash', contents=contents_payload, config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.0))
        parsed_data = json.loads(response.text.strip())
        parsed_data["sketch_image"] = sketch_base64
        if not parsed_data.get("style_number_parsed"): parsed_data["style_number_parsed"] = fallback_style
        return {"success": True, "data": parsed_data}
    except Exception as e: return {"success": False, "error": str(e)}
# GIAO DIỆN HỆ THỐNG (CYBER LIGHT PREMIUM)
st.markdown("""<style>
    .stApp { background-color: #F8FAFC !important; }
    .component-title-box { background: linear-gradient(90deg, #1E3A8A 0%, #2563EB 100%); color: #FFFFFF !important; font-size: 16px; font-weight: 700; padding: 14px 20px; border-radius: 10px; margin-bottom: 25px; text-transform: uppercase; }
    .card-container { background-color: #FFFFFF !important; border: 1px solid #E2E8F0 !important; border-radius: 14px !important; padding: 24px; margin-bottom: 25px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.03) !important; }
    .tech-card-header { font-size: 18px; font-weight: 800; color: #0F172A; margin-bottom: 15px; }
    .metric-grid-box { display: flex; gap: 25px; background: #F8FAFC; padding: 14px 20px; border-radius: 10px; border: 1px solid #E2E8F0; margin-bottom: 20px; }
    .metric-label { font-size: 11px; font-weight: 700; color: #64748B; margin: 0; text-transform: uppercase; }
    .metric-value { font-size: 14px; font-weight: 700; color: #1E3A8A; margin: 3px 0 0 0; }
    .data-table-container { max-height: 420px; overflow-y: auto; border: 1px solid #CBD5E1; border-radius: 10px; margin-top: 12px; background: white; }
    .industrial-table { width: 100%; border-collapse: collapse; text-align: left; }
    .industrial-table th { background-color: #F1F5F9 !important; color: #1E3A8A !important; font-weight: 700 !important; padding: 12px 16px; font-size: 13px; position: sticky; top: 0; z-index: 5; border-bottom: 2px solid #CBD5E1 !important; }
    .industrial-table td { padding: 11px 16px; border-bottom: 1px solid #E2E8F0; color: #334155 !important; font-size: 13px; }
    .idle-alert-box { background-color: #FFFBEB; border-left: 5px solid #F59E0B; padding: 16px 20px; border-radius: 4px 12px 12px 4px; color: #B45309; font-size: 13.5px; font-weight: 600; }
</style>""", unsafe_allow_html=True)

st.markdown('<div class="component-title-box">📊 MULTI-BATCH GARMENT SPECIFICATION MATRIX</div>', unsafe_allow_html=True)

if "processed_styles" not in st.session_state: st.session_state["processed_styles"] = {}

st.markdown("""<div class="card-container"><div class="card-section-header" style="font-weight:700; color:#1E3A8A; border-left:4px solid #2563EB; padding-left:10px; text-transform:uppercase; font-size:14px; margin-bottom:12px;">📥 INGESTION ENGINE</div>
<p style="color: #64748B; font-size:13px; margin:0;">Tải tệp Techpack PDF gốc để hệ thống tự động bóc tách và đồng bộ kho hàng loạt.</p></div>""", unsafe_allow_html=True)

uploaded_files = st.file_uploader("Upload Techpack PDF", type=["pdf"], accept_multiple_files=True, label_visibility="collapsed")
if uploaded_files:
    files_to_render = []
    for file in uploaded_files:
        if file.name not in st.session_state["processed_styles"]:
            with st.spinner(f"Core AI đang bóc tách mô hình {file.name}..."):
                res = process_single_pdf_batch(file.getvalue(), file.name)
                if res["success"]: st.session_state["processed_styles"][file.name] = res["data"]
                else: st.error(f"FAIL ENGINE [{file.name}]: {res['error']}")
        if file.name in st.session_state["processed_styles"]: files_to_render.append(file.name)

    if files_to_render:
        if st.button("💾 SAVE ALL PROCESSED MATRIX TO SUPABASE MASTER DB", key="bulk_save_all_btn", type="primary", use_container_width=True):
            success_count = 0
            with st.spinner("Đang đồng bộ dữ liệu hàng loạt lên Supabase Cloud..."):
                for f_name in files_to_render:
                    if save_to_supabase_techpack_table(st.session_state["processed_styles"][f_name]): success_count += 1
            st.success(f"🎉 Đã đồng bộ thành công {success_count}/{len(files_to_render)} mã hàng vào Database!")
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
                    for k, v in data.get("measurements", {}).items(): table_html += f"<tr><td>{k}</td><td>{v}</td></tr>"
                    st.markdown(table_html + "</tbody></table></div>", unsafe_allow_html=True)
                with sub_col2:
                    st.markdown("<p style='font-weight:700; font-size:12px; color:#1E293B;'>📐 GARMENT FLAT SKETCH</p>", unsafe_allow_html=True)
                    if data.get("sketch_image"): st.image(base64.b64decode(data["sketch_image"]), use_column_width=True)
                st.markdown("<br><hr style='border-color:#E2E8F0;'><br>", unsafe_allow_html=True)
else:
    st.markdown('<div class="idle-alert-box">⚠️ INITIALIZATION SYSTEM IDLE: Hiện tại chưa có tệp dữ liệu Techpack nào được nạp vào hệ thống để AI khởi chạy mô hình.</div>', unsafe_allow_html=True)
import io
import re
import streamlit as st
import pandas as pd

st.markdown("""<style>
    .stApp { background-color: #F8FAFC !important; }
    .component-title-box { background: linear-gradient(90deg, #1E3A8A 0%, #2563EB 100%); color: #FFFFFF !important; font-size: 16px; font-weight: 700; padding: 14px 20px; border-radius: 10px; margin-bottom: 25px; text-transform: uppercase; }
    .card-container { background-color: #FFFFFF !important; border: 1px solid #E2E8F0 !important; border-radius: 14px !important; padding: 24px; margin-bottom: 25px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.03) !important; }
</style>""", unsafe_allow_html=True)

st.markdown('<div class="component-title-box">🔄 DIFFERENTIAL GEOMETRY & DELTA SPEC EVALUATOR</div>', unsafe_allow_html=True)

if "processed_styles" not in st.session_state: st.session_state["processed_styles"] = {}

st.markdown("""<div class="card-container"><div style="font-size:14px; font-weight:700; color:#1E3A8A; border-left:4px solid #2563EB; padding-left:10px; text-transform:uppercase; margin-bottom:12px;">🔍 CONFIGURATION SELECTION</div>
<p style="color: #64748B; font-size:13px; margin:0;">Tải lên hai tệp bản vẽ kỹ thuật dệt may độc lập từ bộ nhớ đệm đã quét ở Trang 1 để tiến hành lập luận so sánh.</p></div>""", unsafe_allow_html=True)

all_processed_keys = list(st.session_state["processed_styles"].keys())
if len(all_processed_keys) >= 2:
    sc1, sc2 = st.columns(2)
    with sc1: file1_name = st.selectbox("Chọn file mẫu Techpack Gốc (File A)", options=all_processed_keys, index=0)
    with sc2: file2_name = st.selectbox("Chọn file mẫu Techpack Sửa đổi (File B)", options=all_processed_keys, index=1)
    
    d1 = st.session_state["processed_styles"].get(file1_name)
    d2 = st.session_state["processed_styles"].get(file2_name)
    
    if d1 and d2:
        st.markdown(f"""<div style="background-color: #FFFFFF; border-left: 5px solid #3B82F6; padding: 12px 20px; border-radius: 4px 12px 12px 4px; margin-bottom: 20px; box-shadow: 0 2px 5px rgba(0,0,0,0.02);"><h5 style="margin:0; color:#1E3A8A; font-weight:700; font-size:16px;">⚙️ ĐANG ĐỐI CHIẾU MA TRẬN PHÁT TRIỂN MẪU</h5><p style="margin:4px 0 0 0; font-size:13px; color:#64748B;"><b>Mẫu Gốc A:</b> {d1['style_number_parsed']} [Size: {d1.get('base_size_name','N/A')}] &nbsp;|&nbsp; <b>Mẫu Sửa B:</b> {d2['style_number_parsed']} [Size: {d2.get('base_size_name','N/A')}]</p></div>""", unsafe_allow_html=True)
        
        def clean_garment_fraction(v_str):
            if not v_str or str(v_str).strip().upper() in ["N/A", "N/A INCH", ""]: return 0.0
            try:
                s = str(v_str).replace("INCH", "").strip()
                if " " in s:
                    parts = s.split()
                    return float(parts[0]) + (float(parts[1].split('/')[0]) / float(parts[1].split('/')[1]))
                elif "/" in s:
                    return float(s.split('/')[0]) / float(s.split('/')[1])
                return float(s)
            except:
                nums = re.findall(r"[-+]?\d*\.\d+|\d+", str(v_str))
                return float(nums[0]) if nums else 0.0

        col_title_a = f"Mẫu A ({d1['style_number_parsed']}) [{d1.get('base_size_name','BASE')}]"
        col_title_b = f"Mẫu B ({d2['style_number_parsed']}) [{d2.get('base_size_name','BASE')}]"
        all_poms = set(list(d1["measurements"].keys()) + list(d2["measurements"].keys()))
        
        table_body_html = ""
        compare_rows_for_df = []
        for pom in sorted(all_poms):
            val1 = d1["measurements"].get(pom, "N/A")
            val2 = d2["measurements"].get(pom, "N/A")
            delta = round(clean_garment_fraction(val2) - clean_garment_fraction(val1), 3) if val1 != "N/A" and val2 != "N/A" else 0.0
            compare_rows_for_df.append({"Vị trí đo (POM)": pom, col_title_a: val1, col_title_b: val2, "Sai lệch (Delta)": delta})
            
            if delta > 0: delta_td = f'<td style="padding:10px 14px;border-bottom:1px solid #E2E8F0;text-align:center;"><span style="background-color:#DCFCE7;color:#166534;font-weight:700;padding:2px 6px;border-radius:4px;font-size:12px;">+{delta}</span></td>'
            elif delta < 0: delta_td = f'<td style="padding:10px 14px;border-bottom:1px solid #E2E8F0;text-align:center;"><span style="background-color:#FEE2E2;color:#991B1B;font-weight:700;padding:2px 6px;border-radius:4px;font-size:12px;">{delta}</span></td>'
            else: delta_td = f'<td style="padding:10px 14px;border-bottom:1px solid #E2E8F0;text-align:center;color:#94A3B8;font-size:12px;">0.0</td>'
            table_body_html += f'<tr style="background-color: #FFFFFF;"><td style="padding: 10px 14px; border-bottom: 1px solid #E2E8F0; font-weight: 600; color: #1E293B; font-size: 13px;">{pom}</td><td style="padding: 10px 14px; border-bottom: 1px solid #E2E8F0; color: #334155; font-size: 13px;">{val1}</td><td style="padding: 10px 14px; border-bottom: 1px solid #E2E8F0; color: #334155; font-size: 13px;">{val2}</td>{delta_td}</tr>'
        
        full_table_render = f'<div style="max-height:460px;overflow-y:auto;border:1px solid #CBD5E1;border-radius:12px;margin-top:15px;"><table style="width:100%;border-collapse:collapse;text-align:left;font-family:sans-serif;"><thead><tr style="background:linear-gradient(90deg,#1E3A8A 0%,#2563EB 100%);"><th style="color:#FFFFFF;font-weight:600;padding:14px 16px;font-size:13px;position:sticky;top:0;z-index:10;">Vị trí đo (POM Description)</th><th style="color:#FFFFFF;font-weight:600;padding:14px 16px;font-size:13px;position:sticky;top:0;z-index:10;">{col_title_a}</th><th style="color:#FFFFFF;font-weight:600;padding:14px 16px;font-size:13px;position:sticky;top:0;z-index:10;">{col_title_b}</th><th style="color:#FFFFFF;font-weight:600;padding:14px 16px;font-size:13px;text-align:center;width:150px;position:sticky;top:0;z-index:10;">Sai lệch (Delta)</th></tr></thead><tbody>{table_body_html}</tbody></table></div>'
        st.markdown(full_table_render, unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        
        df_compare = pd.DataFrame(compare_rows_for_df)
        towrite = io.BytesIO()
        with pd.ExcelWriter(towrite, engine='xlsxwriter') as writer:
            df_compare.to_excel(writer, index=False, sheet_name='Spec_Report')
            workbook = writer.book; worksheet = writer.sheets['Spec_Report']
            header_format = workbook.add_format({'bold':True,'text_wrap':True,'fg_color':'#1E3A8A','font_color':'white','border':1,'align':'center','valign':'vcenter'})
            center_format = workbook.add_format({'align':'center','valign':'vcenter','border':1}); left_format = workbook.add_format({'align':'left','valign':'vcenter','border':1})
            for col_num, column_title in enumerate(df_compare.columns): worksheet.write(0, col_num, column_title, header_format)
            for i, col in enumerate(df_compare.columns):
                max_len = max(df_compare[col].astype(str).map(len).max(), len(col)) + 4
                if i == 0: worksheet.set_column(i, i, max_len, left_format)
                else: worksheet.set_column(i, i, max_len, center_format)
        towrite.seek(0)
        st.download_button(label="📥 XUẤT BÁO CÁO ĐỐI CHIẾU THÔNG SỐ (EXCEL PRODUCTION)", data=towrite, file_name="PPJ_Spec_Comparison_Premium.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
else:
    st.warning("⚠️ Hiện tại bộ nhớ đệm trống. Bạn vui lòng quay lại Trang số 1 quét ít nhất 2 file PDF để kích hoạt ma trận đối chiếu.")
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

# 1. CẤU HÌNH THƯ VIỆN & DATABASE MATRIX
SB_URL = "https://supabase.co"
SB_KEY = st.secrets.get("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImV3cXFvZHNmdmx2bnJ6c3lsYXd5Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzUxMTkyOTAsImV4cCI6MjA5MDY5NTI5MH0.BWPxOsyswBT5CLrZgluRC1F2x5EpU06oexUFyakGhyc")

def get_secure_gemini_key():
    if "GEMINI_API_KEY" in st.secrets: 
        return st.secrets["GEMINI_API_KEY"].strip()
    return None

def get_historical_fabric_consumption_from_db(search_keyword=None):
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
    except Exception:
        return []

# 2. ĐỒ HỌA CYBER LIGHT HIGH-CONTRAST (CHỐNG TỐI ĐEN & MỜ CHỮ)
st.markdown("""
    <style>
    .stApp { background-color: #F8FAFC !important; }
    [data-testid="stChatMessage"] { background-color: #FFFFFF !important; border: 1px solid #CBD5E1 !important; border-radius: 12px !important; box-shadow: 0 2px 5px rgba(0,0,0,0.02) !important; }
    [data-testid="stChatMessage"] p { color: #0F172A !important; font-size: 14px !important; font-weight: 500 !important; line-height: 1.6 !important; }
    [data-testid="stMarkdownContainer"] p, [data-testid="stMarkdownContainer"] h1, [data-testid="stMarkdownContainer"] h5 { color: #0F172A !important; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<div style="background: linear-gradient(90deg, #1E3A8A 0%, #2563EB 100%); padding: 16px 20px; border-radius: 12px; font-size: 18px; font-weight: 700; color: #FFFFFF; box-shadow: 0 4px 12px rgba(30,58,138,0.15); margin-bottom: 24px;">🧵 PPJ INTELLIGENT BOM & CONSUMPTION MATRIX ENGINE</div>', unsafe_allow_html=True)

with st.sidebar:
    st.success("DATABASE ACCESS: SECURED")
    st.info("ANALYTICS ENGINE: COMPLY")

# KHU VỰC ĐIỀU KHIỂN INPUT HỆ THỐNG
control_col1, control_col2 = st.columns([3.2, 0.8])
with control_col1:
    st.markdown("<p style='font-weight:700; font-size:13px; color:#1E293B;'>📁 INGEST NEW TECHPACK BATCH (PDF/IMAGE)</p>", unsafe_allow_html=True)
    chat_file = st.file_uploader("Upload Techpack file", type=["pdf", "jpg", "jpeg", "png"], key="chat_uploader", label_visibility="collapsed")
    if chat_file: 
        st.success(f"🎉 DATASTREAM PIPELINE BOUND: Tiếp nhận thành công file {chat_file.name}")
        
with control_col2:
    st.markdown("<p style='font-weight:700; font-size:13px; color:#1E293B;'>🧹 PURGE LAB MEMORY</p>", unsafe_allow_html=True)
    if st.button("🗑️ XÓA LỊCH SỬ CHAT", use_container_width=True, type="secondary"):
        import time
        if "chat_history" in st.session_state: 
            del st.session_state["chat_history"]
        st.success("🔄 MEMORY PURGED")
        time.sleep(0.5)
        st.rerun()

st.markdown("<hr style='border-color:#E2E8F0; margin: 20px 0;'>", unsafe_allow_html=True)

# KHỞI TẠO VÀ IN LỊCH SỬ HỘI THOẠI (CHỐNG TRÙNG LẶP TIN NHẮN)
if "chat_history" not in st.session_state:
    st.session_state["chat_history"] = [
        {"role": "assistant", "type": "text", "content": "Welcome to PPJ Textile Visual R&D Engine. Hãy tải lên sơ đồ rập/Techpack mã mới, hệ thống sẽ bóc tách biệt lập, tự động đối soát kho Master DB và lập luận toán học để kết xuất định mức vải cùng bảng phụ liệu BOM chính xác."}
    ]
    
for msg in st.session_state["chat_history"]:
    with st.chat_message(msg["role"]): 
        st.write(msg["content"])
        if msg.get("type") == "visual" and msg.get("image_url"):
            st.image(msg["image_url"], caption=f"Bản vẽ Sketch lịch sử đối chiếu mã {msg.get('style_title')}", width=220)
# 3. LÕI BACKEND XỬ LÝ AI - LUỒNG DỮ LIỆU ĐÓNG BĂNG ĐỘC LẬP CHỐNG LẪN MÃ (ĐOẠN A)
if user_query := st.chat_input("Nhập yêu cầu phân tích định mức vải và đối soát sai lệch..."):
    st.session_state["chat_history"].append({"role": "user", "type": "text", "content": user_query})
    with st.chat_message("user"): 
        st.write(user_query)
        
    with st.chat_message("assistant"):
        with st.spinner("Hệ thống AI R&D Engine đang thiết lập ma trận đối soát và phân tích cấu trúc BOM..."):
            gemini_key = get_secure_gemini_key()
            if not gemini_key: 
                ans = "CRITICAL SERVER BREAKDOWN: AI API Token is missing."
            else:
                try:
                    client = genai.Client(api_key=gemini_key)
                    contents_payload = []
                    new_style_id_detected = "UNKNOWN_STYLE"
                    new_style_raw_text = ""
                    
                    # BƯỚC A: BÓC TÁCH KHÉP KÍN TOÀN BỘ CÁC TRANG CỦA TỆP FILE MỚI
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
                        2. Locate the Specification table and extract ALL measurement positions and target values.
                        3. Locate the Bill of Materials (BOM) section. Extract EVERY SINGLE trim, thread, zipper, button, label, elastic or accessory along with its specific description and target consumption/yield.
                        Return a valid JSON with this exact schema:
                        {"detected_style_id": "Text of Style ID", "all_specs_text": "Specs list and complete raw BOM text from all pages"}
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
                    
                    if new_style_id_detected == "UNKNOWN_STYLE" or not chat_file:
                        found_keywords = re.findall(r'[A-Za-z0-9]+[-–][A-Za-z0-9]+|[A-Za-z0-9]{4,}', user_query)
                        if found_keywords: new_style_id_detected = found_keywords

                    # BƯỚC B: TRUY VẤN ĐỐI SOÁT CHÍNH XÁC KHO THỊ GIÁC TỪ DATABASE
                    headers = {"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}"}
                    url = f"{SB_URL.rstrip('/')}/rest/v1/thong_so_techpack?StyleName=ilike.*{new_style_id_detected}*&select=StyleName,Buyer,Category,BaseSize,DetailedMeasurements,SketchURL&limit=3"
                    res = requests.get(url, headers=headers, timeout=15)
                    db_results = res.json() if 200 <= res.status_code <= 299 else []
                    
                    db_context = f"\n\n[ KHO DỮ LIỆU THỊ GIÁC VÀ THÔNG SỐ LỊCH SỬ CHO MÃ HÀNG: {new_style_id_detected} ]:\n"
                    detected_image_url_to_render = ""
                    detected_style_title_to_render = ""
                    
                    if db_results:
                        for item in db_results:
                            if item.get("SketchURL") and not detected_image_url_to_render:
                                detected_image_url_to_render = item.get("SketchURL")
                                detected_style_title_to_render = item.get("StyleName")
                            db_context += f"- Mã hàng lịch sử đối chiếu: {item.get('StyleName')}\n  + Khách hàng (Buyer): {item.get('Buyer')}\n  + Cấu trúc ma trận số đo cũ: {json.dumps(item.get('DetailedMeasurements', {}), ensure_ascii=False)}\n  + Đường dẫn hình ảnh Sketch lưu kho: {item.get('SketchURL', 'Không có ảnh')}\n"
                    else:
                        fallback_key = new_style_id_detected.split('-')[-1] if '-' in str(new_style_id_detected) else str(new_style_id_detected)[:4]
                        backup_res = get_historical_fabric_consumption_from_db(search_keyword=fallback_key)
                        if backup_res:
                            db_context += f"⚠️ Không có dữ liệu cấu trúc rập trực tiếp cho mã {new_style_id_detected}. Dưới đây là dữ liệu định mức phụ trợ gốc của các mã hàng anh em trong kho để so sánh mẫu:\n"
                            for b_item in backup_res[:4]:
                                db_context += f"- Mã gốc: {b_item.get('style_name')}, Nguyên liệu: {b_item.get('article_name')}, Định mức gốc: {b_item.get('consumption_value')} {b_item.get('uom')}, Ghi chú: {b_item.get('notes')}\n"
                        else:
                            db_context += "❌ HỆ THỐNG PHÁT HIỆN: Mã hàng này hoàn toàn mới, chưa từng tồn tại dữ liệu trùng khớp hoặc hình ảnh phác thảo tương đồng trong kho dữ liệu Master DB.\n"
                    # BƯỚC C: RÀNG BUỘC PHÂN TÍCH R&D ĐỌC HIỂU CẠN KIỆT BOM CHI TIẾT (ĐOẠN B)
                    system_instruction = (
                        "You are the Lead Technical Director and Senior R&D Data Auditor at PPJ Group.\n"
                        "Your objective is to conduct a complete analysis of the newly uploaded Techpack, covering BOTH Fabric Specifications and the Bill of Materials (BOM).\n\n"
                        "MANDATORY 4-STEP TECHNICAL WORKFLOW:\n"
                        "1. PHÂN TÍCH THÔNG TIN SƠ BỘ: Xác nhận Style ID, khách hàng, dải kích cỡ và tóm tắt nhanh ma trận số đo rập mẫu.\n"
                        "2. ĐỐI CHIẾU DỮ LIỆU LỊCH SỬ DB: Đối soát mã với bộ dữ liệu kho được cung cấp để rút ra mã hàng tương đồng.\n"
                        "3. LẬP LUẬN TÍNH ĐỊNH MỨC VẢI CHÍNH (MAIN FABRIC): So sánh chi tiết sai lệch kích thước hình học (Delta Spec) giữa mã mới và mã tương đồng. Điều chỉnh tăng/giảm định mức vải tiêu thụ cuối cùng kèm hệ số hao hụt cắt xưởng 15%, đưa ra kết quả Cons Value cụ thể (YARDS/UNIT).\n"
                        "4. BẢNG BÓC TÁCH ĐỊNH MỨC NGUYÊN PHỤ LIỆU CHI TIẾT (COMPLETE BOM BREAKDOWN): Quét toàn bộ dữ liệu phụ liệu tìm thấy từ Techpack mới. Bạn phải lập bảng trích xuất cạn kiệt từng hạng mục phụ liệu: Chỉ may, Nhãn mác, Cúc, Khóa, Chun... Mỗi hạng mục phải ghi rõ: Tên phụ liệu, Mô tả chi tiết, Định mức chỉ định gốc và Định mức dự kiến thực tế sau khi cộng hệ số hao hụt xưởng. Nếu Techpack không có bảng BOM, bạn phải dựa vào kết cấu kiểu dáng của sản phẩm để chủ động lập một bảng BOM kỹ thuật khuyến nghị chuẩn.\n\n"
                        "Yêu cầu kết xuất báo cáo sắc bén, khoa học, trình bày bằng tiếng Việt chuyên ngành dệt may cao cấp."
                    )
                    
                    full_prompt = f"{system_instruction}\n\nYêu cầu kỹ sư: {user_query}\n\n[Thông số và dữ liệu thô từ toàn bộ trang Techpack mới]:\n{new_style_raw_text if new_style_raw_text else 'Không đính kèm file'}\n{db_context}"
                    contents_payload.append(full_prompt)
                    
                    # Bộ bẫy lỗi lũy tiến Backoff 5 lần tránh sập mạng
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
                    
                    if detected_image_url_to_render:
                        st.image(detected_image_url_to_render, caption=f"Bản vẽ Sketch lịch sử đối chiếu của Mã hàng {detected_style_title_to_render}", width=220)
                        st.session_state["chat_history"].append({"role": "assistant", "type": "visual", "content": f"[Hệ thống đã kết xuất hình ảnh tham chiếu]", "image_url": detected_image_url_to_render, "style_title": detected_style_title_to_render})
                            
                except Exception as e: 
                    ans = f"⚠️ Máy chủ AI bận hoặc đạt giới hạn (15 lần/phút) khi xử lý ma trận BOM lớn. Vui lòng bấm thử lại sau 15-30 giây! Chi tiết: {str(e)}"
                    st.write(ans)
                    st.session_state["chat_history"].append({"role": "assistant", "type": "text", "content": ans})
