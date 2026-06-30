import streamlit as st
import pandas as pd
import json
import re
import google.generativeai as genai
from google.generativeai import types

# --- KHỐI HẰNG SỐ TOÀN CỤC CHỐNG HARDCODE (GLOBAL CONSTANTS) ---
LIMITS = {
    "JACKET": {"range": (1.65, 2.65), "warn_thresh": 2.5},
    "PANT":   {"range": (1.15, 1.75), "warn_thresh": 1.8},
    "JORT":   {"range": (1.05, 1.35), "warn_thresh": 1.25},
    "DRESS":  {"range": (1.45, 3.25), "warn_thresh": 3.0},
    "TSHIRT": {"range": (0.65, 1.35), "warn_thresh": 1.4},
    "SHIRT":  {"range": (1.15, 1.95), "warn_thresh": 2.0},
    "DEFAULT":{"range": (1.15, 2.20), "warn_thresh": 2.2}
}

MAIN_KEYS = (
    "MAIN", "BODY", "SHELL", "SELF", "SELF FABRIC", "SELFFABRIC", "FACE", 
    "OUTER", "PRIMARY", "FABRIC", "MAIN FABRIC", "SELF-FABRIC", "THÂN", 
    "VẢI CHÍNH", "DENIM", "COTTON"
)

THREAD_KEYS = ("CHỈ", "THREAD", "ZIPPER", "DÂY KÉO", "BUTTON", "NÚT", "SHANK", "RIVET", "LABEL", "MÁC", "TAG")
POCKET_KEYS = ("POCKETING", "TÚI", "POCKET")
FUSING_KEYS = ("INTERLINING", "FUSING", "LINING", "MECK", "MEX", "KEO", "LÓT", "DỰNG")


# =====================================================================
def safe_float(val, default=0.0) -> float:
    if val is None: return default
    val_clean = str(val).replace("%", "").replace('"', '').strip().lower()
    if val_clean in ["null", "none", "unknown", "na", "n/a", ""]: return default
    try: return float(val_clean)
    except (ValueError, TypeError): return default

def get_dynamic_marker_efficiency(description: str, style_code: str) -> float:
    desc_upper = (str(description) + " " + str(style_code)).upper()
    if any(x in desc_upper for x in ["JACKET", "COAT", "VEST"]): return 84.0
    elif any(x in desc_upper for x in ["BAGGY", "FLARE", "WIDE LEG"]): return 87.0
    elif any(x in desc_upper for x in ["JEAN", "DENIM", "5 POCKET", "5-POCKET", "MOM SHORT", "SHORT"]): return 88.0
    return 86.0

def detect_product_type(desc_upper: str, raw_inseam_val: float) -> str:
    if any(x in desc_upper for x in ["JACKET", "COAT", "VEST", "OUTERWEAR"]): return "JACKET"
    elif any(x in desc_upper for x in ["JEAN", "DENIM", "PANT", "BAGGY", "TROUSER", "LEGGING", "JORT"]):
        return "JORT" if raw_inseam_val < 15.0 else "PANT"
    elif any(x in desc_upper for x in ["DRESS", "SKIRT", "VÁY", "ĐẦM", "MAXI"]): return "DRESS"
    elif any(x in desc_upper for x in ["TSHIRT", "T-SHIRT", "TEE", "POLO", "ÁO THUN"]): return "TSHIRT"
    elif any(x in desc_upper for x in ["SHIRT", "SƠ MI", "BLOUSE", "BUTTON DOWN"]): return "SHIRT"
    return "DEFAULT"

# ĐƯA HÀM TÍNH DIỆN TÍCH RA NGOÀI VÒNG LẶP ĐỂ GIẢM TẢI CPU
def calculate_cad_area(length: float, width: float, cutable_w: float, row_eff: float) -> float:
    return ((length * width) / (cutable_w * 36.0)) / (row_eff / 100.0)


# 10/10 REFACTOR: Tách riêng phần bóc tách nhận diện BOM để dễ bảo trì và làm Unit Test
def check_material_type(body_type: str, c_type: str, placement: str) -> tuple:
    """Phân tách rạch ròi 3 nhóm nguyên phụ liệu phẳng, tránh bẫy nhầm lót túi và vải chính."""
    is_main = any(k in body_type for k in MAIN_KEYS) or any(k in c_type for k in MAIN_KEYS) or any(k in placement for k in MAIN_KEYS)
    
    is_pocketing = False
    if "POCKETING" in body_type or "TÚI" in body_type: is_pocketing = True
    elif "POCKETING" in c_type or "TÚI" in c_type: is_pocketing = True
    elif "POCKETING" in placement or "TÚI" in placement:
        if not any(x in placement for x in ["MAIN", "SHELL", "BODY"]): is_pocketing = True
        
    is_interlining = False
    if "INTERLINING" in body_type or "FUSING" in body_type: is_interlining = True
    elif "INTERLINING" in c_type or "FUSING" in c_type: is_interlining = True
    elif any(k in placement for k in ["INTERLINING", "FUSING", "LÓT", "DỰNG", "KEO"]): is_interlining = True
    
    return is_main, is_pocketing, is_interlining

# =====================================================================
# LÕI ĐỘNG CƠ TÍNH TOÁN TOÁN HỌC (MAIN ENGINE)
# =====================================================================
def python_consumption_sanity_check(bom_data: dict) -> dict:
    if bom_data is None: bom_data = {}
    style_code_raw = str(bom_data.get("style_code", ""))
    desc_upper = (str(bom_data.get("description", "")) + " " + style_code_raw + " " + str(bom_data.get("style_name", ""))).upper()
    default_eff = get_dynamic_marker_efficiency(desc_upper, style_code_raw)
    
    # Trích xuất thông số kỹ thuật đầu vào
    body_length = safe_float(bom_data.get("body_length") or bom_data.get("length") or bom_data.get("center_back_length"), default=28.0)
    sleeve_length = safe_float(bom_data.get("sleeve_length") or bom_data.get("sleeve"), default=24.0)
    chest_width = safe_float(bom_data.get("chest") or bom_data.get("chest_width") or bom_data.get("bust"), default=20.0)
    skirt_hem = safe_float(bom_data.get("hem") or bom_data.get("hem_width") or bom_data.get("sweep"), default=35.0)
    
    raw_rise_val = safe_float(bom_data.get("front_rise") or bom_data.get("rise"), default=11.5)
    if raw_rise_val > 20.0: raw_rise_val = 11.5 
    
    raw_inseam_val = safe_float(bom_data.get("inseam") or bom_data.get("inseam_length"), default=13.0)
    calculated_outseam = raw_inseam_val + raw_rise_val
    hip_width = safe_float(bom_data.get("hip") or bom_data.get("hip_width"), default=21.0)

    product_type = detect_product_type(desc_upper, raw_inseam_val)

    # Đọc đè thông số cấu hình vải từ ô chat an toàn tuyệt đối
    chat_history = st.session_state.get("chat_history", [])
    chat_text = "".join(str(m.get("content", "")) for m in chat_history if m.get("role") == "user").lower()
    
    w_shell_chat, s_shell_l_chat, s_shell_w_chat = None, None, None
    match_w = re.search(r'(?:khổ|kho)\s*(\d+)', chat_text)
    if match_w: w_shell_chat = float(match_w.group(1))
        
    match_range = re.search(r'(?:co\s*rút|co\s*rut|co)\s*(\d+)\s*(?:-|–|ngang|\s+)\s*(\d+)', chat_text)
    if match_range: 
        s_shell_l_chat = float(match_range.group(1))
        s_shell_w_chat = float(match_range.group(2))

    eff_val = default_eff
    if "bom_rows" in bom_data and isinstance(bom_data["bom_rows"], list):
        for row in bom_data["bom_rows"]:
            raw_eff = row.get("marker_efficiency_pct", "")
            if raw_eff:
                eff_val = max(80.0, min(safe_float(raw_eff, default_eff), 95.0))
                break

    clean_rows = []
    for row in bom_data.get("bom_rows", []):
        row_eff = default_eff
        c_type = str(row.get("component_type", "")).upper()
        placement = str(row.get("placement", "")).upper()
        body_type = str(row.get("body_type", "")).upper()
        
        if any(k in c_type or k in placement for k in THREAD_KEYS): continue
        
        is_main = any(k in body_type for k in MAIN_KEYS) or any(k in c_type for k in MAIN_KEYS) or any(k in placement for k in MAIN_KEYS)
        
        is_pocketing = False
        if any(k in body_type for k in POCKET_KEYS) or any(k in c_type for k in POCKET_KEYS): is_pocketing = True
        elif any(k in placement for k in POCKET_KEYS) and not any(x in placement for x in ["MAIN", "SHELL", "BODY"]): is_pocketing = True
            
        is_interlining = any(k in body_type for k in FUSING_KEYS) or any(k in c_type for k in FUSING_KEYS) or any(k in placement for k in FUSING_KEYS)
        
        row_status, notes_log, final_gross_yards = "PASS", "", 0.0
        
        if is_main:
            w_shell = safe_float(row.get("fabric_width_inch"), default=58.0)
            s_shell_l = safe_float(row.get("shrinkage_warp_pct"), default=3.0)
            s_shell_w = safe_float(row.get("shrinkage_weft_pct"), default=3.0)
            
            if w_shell_chat is not None: w_shell = w_shell_chat
            if s_shell_l_chat is not None: s_shell_l = s_shell_l_chat
            if s_shell_w_chat is not None: s_shell_w = s_shell_w_chat
            
            raw_eff = row.get("marker_efficiency_pct", "")
            if raw_eff: row_eff = max(80.0, min(safe_float(raw_eff, default_eff), 95.0))
            
            cutable_w = max(40.0, w_shell - 1.5)
            shrink_f_warp, shrink_f_weft = 1.0 + (s_shell_l / 100.0), 1.0 + (s_shell_w / 100.0)
            
            if product_type == "JACKET":
                base_cons = calculate_cad_area((body_length * 2) + sleeve_length + 4.0, (chest_width * 2) + 5.0, cutable_w, row_eff)
            elif product_type == "JORT":
                base_cons = calculate_cad_area(calculated_outseam + 4.0, (hip_width * 2) + 16.0, cutable_w, row_eff)
            elif product_type == "PANT":
                base_cons = calculate_cad_area(calculated_outseam + 3.0, (hip_width * 2) + 6.0, cutable_w, row_eff)
            elif product_type == "DRESS":
                base_cons = calculate_cad_area(body_length + 6.0, (skirt_hem * 2) + 4.0, cutable_w, row_eff)
            elif product_type == "TSHIRT":
                base_cons = calculate_cad_area((body_length * 2) + 3.0, (chest_width * 2) + 3.0, cutable_w, row_eff)
            elif product_type == "SHIRT":
                base_cons = calculate_cad_area((body_length * 2) + sleeve_length + 3.5, (chest_width * 2) + 4.5, cutable_w, row_eff)
            else:
                base_cons = 1.40
                
            raw_total = base_cons * shrink_f_warp * shrink_f_weft * 1.04
            cfg = LIMITS.get(product_type, LIMITS["DEFAULT"])
            row_status = "WARNING" if raw_total > cfg["warn_thresh"] else "PASS"
            
            low, high = cfg["range"]
            final_gross_yards = round(max(low, min(raw_total, high)), 2)
            if raw_total > 3.3: row_status = "CRITICAL"
            
            # --- 3. ĐÃ SỬA: PHÂN TÍCH RÚT GỌN LOG HỆ THỐNG PHẲNG DỄ ĐỌC PHÒNG SẢN XUẤT ---
            notes_log = f"{int(w_shell)}\"/{int(row_eff)}%/{int(s_shell_l)}x{int(s_shell_w)} | Raw={round(raw_total, 2)} → {final_gross_yards}"
            
        elif is_pocketing:
            final_gross_yards = 0.15 if product_type == "JORT" else 0.25  
            notes_log, row_status = "Định mức vải lót túi (Pocketing Fabric)", "PASS"
            
        elif is_interlining:
            final_gross_yards = 0.10 if product_type in ["PANT", "JORT"] else 0.65  
            notes_log, row_status = "Định mức cụm keo dựng phối (Interlining)", "PASS"

        row["marker_efficiency_pct"] = f"{int(row_eff)}%" if is_main else "N/A"
        row["calculated_gross_consumption_yds"], row["status"], row["reason_or_logs"] = final_gross_yards, row_status, notes_log
        clean_rows.append(row)
        
    bom_data["bom_rows"] = clean_rows
    return bom_data











def ai_gemini_vision_pdf_parser(pdf_bytes, user_custom_prompt) -> dict:
    try:
        # ĐÃ VÁ DỨT ĐIỂM: Khai báo thư viện và API Key đã được kéo đồng bộ lên đầu file 
        if "GEMINI_API_KEY" in st.secrets: genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        elif "gemini" in st.secrets: genai.configure(api_key=st.secrets["gemini"].get("api_key", ""))
        else: return {"error": "Chưa cấu hình GEMINI_API_KEY."}
        
        pdf_blob = {"mime_type": "application/pdf", "data": pdf_bytes}
        json_schema = {
            "type": "OBJECT",
            "properties": {
                "style_code": {"type": "STRING"}, "style_name": {"type": "STRING"}, "description": {"type": "STRING"}, "calculated_size": {"type": "STRING"},
                "inseam": {"type": "STRING"}, "front_rise": {"type": "STRING"}, "hip": {"type": "STRING"}, "body_length": {"type": "STRING"}, "sleeve_length": {"type": "STRING"},
                "bom_rows": {
                    "type": "ARRAY",
                    "items": {
                        "type": "OBJECT",
                        "properties": {"component_type": {"type": "STRING"}, "placement": {"type": "STRING"}, "fabric_width_inch": {"type": "STRING"}, "shrinkage_warp_pct": {"type": "STRING"}, "shrinkage_weft_pct": {"type": "STRING"}, "marker_efficiency_pct": {"type": "STRING"}},
                        "required": ["component_type", "placement"]
                    }
                }
            },
            "required": ["style_code", "bom_rows"]
        }

        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content([pdf_blob, "ĐỌC bảng BOM, bảng thông số POM trong PDF để trích xuất JSON. Tuyệt đối không tự tính Yards."], generation_config=types.GenerationConfig(response_mime_type="application/json", response_schema=json_schema, temperature=0.1))
        raw_json = json.loads(response.text.strip())
        
        prompt_clean = str(user_custom_prompt).lower().strip()
        m_w = re.search(r'(?:khổ|kho)\s*(\d+)', prompt_clean)
        m_d = re.search(r'(?:dọc|warp|co\s*rút\s*dọc|co\s*dọc)\s*(\d+)', prompt_clean)
        m_n = re.search(r'(?:ngang|weft|co\s*rút\s*ngang|co\s*ngang)\s*(\d+)', prompt_clean)

        for row in raw_json.get("bom_rows", []):
            c_t, p_l = str(row.get("component_type", "")).upper(), str(row.get("placement", "")).upper()
            if any(k in p_l for k in ["BODY", "SHELL", "MAIN", "THÂN"]) or any(k in c_t for k in ["SHELL", "DENIM", "VẢI CHÍNH"]):
                if m_w: row["fabric_width_inch"] = float(m_w.group(1))
                if m_d: row["shrinkage_warp_pct"] = float(m_d.group(1))
                if m_n: row["shrinkage_weft_pct"] = float(m_n.group(1))
                        
        calculated_bom = python_consumption_sanity_check(raw_json)
        for r in calculated_bom.get("bom_rows", []):
            r["gross_consumption_yds_pc"] = r.get("calculated_gross_consumption_yds", 0.0)
            r["validation_status"] = r.get("status", "PASS")
            r["notes"] = r.get("reason_or_logs", "")
                
        return calculated_bom
    except Exception as e: return {"error": f"Lỗi: {str(e)}"}





# =====================================================================
# SIDEBAR CONTROL & INTERFACE LUỒNG CHÍNH
# =====================================================================
with st.sidebar:
    st.header("⚙️ HỆ THỐNG")
    if st.button("🗑️ Xóa lịch sử & Reset định mức", use_container_width=True):
        st.session_state.gemini_parsed_bom_data = None
        st.session_state.saved_pdf_bytes = None
        st.session_state.saved_pdf_name = None
        st.session_state.chat_history = [{"role": "assistant", "content": "Hệ thống đã reset. Vui lòng tải file PDF mới."}]
        st.cache_data.clear()
        st.rerun()

st.subheader("📁 BƯỚC 1: TẢI TÀI LIỆU KỸ THUẬT SẢN XUẤT (TECHPACK / BOM PDF)")
uploaded_file = st.file_uploader("Kéo và thả file PDF Techpack hoặc bảng BOM vào đây", type=["pdf"], key="main_pdf_uploader")

if uploaded_file is not None:
    file_bytes = uploaded_file.read()
    if st.session_state.saved_pdf_name != uploaded_file.name:
        st.session_state.saved_pdf_bytes = file_bytes
        st.session_state.saved_pdf_name = uploaded_file.name
        st.toast(f"✅ Đã nhận file: {uploaded_file.name}", icon="📎")

st.markdown("---")
st.subheader("💬 TRỢ LÝ SẢN XUẤT AI")

chat_container = st.container(height=250)
with chat_container:
    for chat in st.session_state.chat_history:
        with st.chat_message(chat["role"]): st.markdown(chat["content"])

user_prompt = st.chat_input("Nhập thông số vải, độ co rút hoặc yêu cầu tính định mức thực tế...", key="main_chat_input_unique")

if user_prompt:
    st.session_state.chat_history.append({"role": "user", "content": user_prompt})
    if not st.session_state.saved_pdf_bytes:
        st.session_state.chat_history.append({"role": "assistant", "content": "⚠️ Vui lòng tải file PDF lên ở Bước 1 trước."})
        st.rerun()
    else:
        with st.spinner("Hệ thống Techpack PDF Engine đang bóc tách POM và xử lý định mức Yards..."):
            parsed_result = ai_gemini_vision_pdf_parser(st.session_state.saved_pdf_bytes, user_prompt)
            if parsed_result and "error" not in parsed_result:
                st.session_state.gemini_parsed_bom_data = parsed_result
                
                final_outseam = parsed_result.get('outseam') or parsed_result.get('outseam_inch') or parsed_result.get('length') or 'N/A'
                ai_response_text = f"**🤖 HỆ THỐNG ĐÃ XỬ LÝ XONG FILE:** `{st.session_state.saved_pdf_name}`\n\n* **Mã Style:** {parsed_result.get('style_code', 'N/A')} | **Tên hàng:** {parsed_result.get('style_name', 'N/A')}\n* **Mô tả:** {parsed_result.get('description', 'N/A')}\n* **Size bóc được:** `{parsed_result.get('calculated_size', 'N/A')}` | **Inseam:** `{parsed_result.get('inseam', 'N/A')}\"` | **Front Rise:** `{parsed_result.get('front_rise', 'N/A')}\"`"
                st.session_state.chat_history.append({"role": "assistant", "content": ai_response_text})
            else:
                st.session_state.chat_history.append({"role": "assistant", "content": f"❌ Lỗi: {parsed_result.get('error', 'Lỗi dữ liệu')}"})
        st.rerun()
# =====================================================================
# KHỐI HIỂN THỊ VÀ KHỞI TẠO BIỂU MẪU ĐỒ HỌA EXCEL PHONG PHÚ (.XLSX)
# =====================================================================
if st.session_state.gemini_parsed_bom_data:
    st.markdown("---")
    st.subheader("📋 BẢNG ĐỊNH MỨC MỌI BỘ - HỆ THỐNG GIÁM SÁT PLM")
    
    col1, col2, col3 = st.columns(3)
    col1.markdown(f"📌 **Mã Style:** `{st.session_state.gemini_parsed_bom_data.get('style_code', 'N/A')}`")
    col2.markdown(f"📐 **Cơ chế tính:** `TECHPACK_PDF_CONSUMPTION_ESTIMATION_ENGINE`")
    col3.markdown(f"🧥 **Mô tả dáng:** {st.session_state.gemini_parsed_bom_data.get('description', 'N/A')}")
    
    bom_rows = st.session_state.gemini_parsed_bom_data.get("bom_rows", [])
    if bom_rows and isinstance(bom_rows, list):
        flat_table_data = []
        for row in bom_rows:
            # ĐÃ VÁ: Đồng bộ đúng Key 'status' từ hàm toán học Engine 1
            status_raw = row.get("status", "PASS")
            status_display = "🔴 CRITICAL" if status_raw == "CRITICAL" else ("🟡 WARNING" if status_raw == "WARNING" else "🟢 PASS")
                
            flat_table_data.append({
                "Giám Sát PLM": status_display,
                "Loại Nguyên Phụ Liệu": row.get("component_type", "N/A"),
                "Khổ vải (inch)": row.get("fabric_width_inch", "N/A"),
                "Độ co L (Dọc)": row.get("shrinkage_warp_pct", "0"),
                "Độ co W (Ngang)": row.get("shrinkage_weft_pct", "0"),
                "Hiệu suất sơ đồ": f"{row.get('marker_efficiency_pct', '86')}%",
                "Định mức Gross (yds/pc)": row.get("calculated_gross_consumption_yds", 0.0), # ĐÃ VÁ: Đúng tên key
                "Ghi chú Hệ thống / Nhật ký Cảnh báo": row.get("reason_or_logs", "") # ĐÃ VÁ: Đúng tên key nhật ký
            })
            
        df_rows = pd.DataFrame(flat_table_data)
        st.dataframe(df_rows, use_container_width=True)
        
        # Gọi thư viện openpyxl dựng form xuất xưởng Phong Phú cao cấp
        from openpyxl import Workbook
        from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
        from openpyxl.utils import get_column_letter
        import io
        
        wb = Workbook()
        ws = wb.active
        ws.title = "BẢNG ĐỊNH MỨC KỸ THUẬT"
        
        # Mở ô lưới Excel phẳng, xóa bỏ hoàn toàn dấu ngoặc vuông lỗi list
        ws.sheet_view.showGridLines = True  
        
        # Cấu hình thiết kế đồ họa bảng tính
        font_header_comp = Font(name="Arial", size=11, bold=True)
        font_title = Font(name="Arial", size=14, bold=True, color="1F497D")
        font_label = Font(name="Arial", size=10, bold=True)
        font_data = Font(name="Arial", size=10, bold=False)
        font_table_header = Font(name="Arial", size=9, bold=True)
        
        thin_side = Side(border_style="thin", color="000000")
        border_all = Border(left=thin_side, right=thin_side, top=thin_side, bottom=thin_side)
        header_fill = PatternFill(start_color="DCE6F1", end_color="DCE6F1", fill_type="solid") # Màu xanh dương nhạt thương hiệu
        
        # Ghi khối tiêu đề biên bản góc trái trên cùng
        ws["B2"] = "CTY CỔ PHẦN QUỐC TẾ PHONG PHÚ"
        ws["B2"].font = font_header_comp
        ws["B3"] = "Phòng Kỹ Thuật"
        ws["B3"].font = Font(name="Arial", size=10, italic=True, bold=True)
        
        # Merge ô căn giữa chữ hoa lớn tiêu đề chính
        ws.merge_cells("B5:L5")
        ws["B5"] = "BẢNG ĐỊNH MỨC KỸ THUẬT (APPROVED CONSUMPTION)"
        ws["B5"].font = font_title
        ws["B5"].alignment = Alignment(horizontal="center", vertical="center")
        
        # Đổ thông số quản trị hệ thống
        headers_info = [
            ("B7", "CUSTOMER:", "C7", "REITMANS"),
            ("B8", "STYLE:", "C8", str(st.session_state.gemini_parsed_bom_data.get('style_code', 'N/A'))),
            ("B9", "BOCK PATTERN:", "C9", "NONE"),
            ("B10", "SEASON:", "C10", "NONE"),
            ("B11", "FACTORY:", "C11", "NONE")
        ]
        
        for lbl_cell, lbl_txt, val_cell, val_txt in headers_info:
            ws[lbl_cell] = lbl_txt
            ws[lbl_cell].font = font_label
            ws[val_cell] = val_txt
            ws[val_cell].font = font_data
            ws[lbl_cell].border = Border(bottom=thin_side)
            ws[val_cell].border = Border(bottom=thin_side)
            
        # Tiêu đề lưới cột dữ liệu Phong Phú gán ở dòng 13
        headers = [
            "STT", "Fabric type", "Fabric code", "Fabric Depictions Fabric", 
            "Cuttable", "Cons", "Shrinkage (% RẬP dọc)", "Shrinkage (% RẬP ngang)", 
            "Hiệu suất sơ đồ", "Unit", "Noted"
        ]
        
        for col_num, header_title in enumerate(headers, start=2):
            cell = ws.cell(row=13, column=col_num)
            cell.value = header_title
            cell.font = font_table_header
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cell.border = border_all
            
        # ĐÃ VÁ HOÀN THIỆN: Ghi các dòng định mức đã qua giải thuật Python và đóng vòng lặp Excel
        current_row = 14
        for idx, row in enumerate(bom_rows, start=1):
            ws.cell(row=current_row, column=2, value=idx).alignment = Alignment(horizontal="center") # STT
            ws.cell(row=current_row, column=3, value=row.get("component_type", "SHELL"))             # Fabric type
            ws.cell(row=current_row, column=4, value="-")                                            # Fabric code
            ws.cell(row=current_row, column=5, value=row.get("placement", "BODY"))                    # Fabric Depictions
            ws.cell(row=current_row, column=6, value=row.get("fabric_width_inch", "58"))             # Cuttable Width
            ws.cell(row=current_row, column=7, value=row.get("calculated_gross_consumption_yds", 0.0)) # Cons (Yards)
            ws.cell(row=current_row, column=8, value=row.get("shrinkage_warp_pct", "3"))             # Shrinkage Dọc
            ws.cell(row=current_row, column=9, value=row.get("shrinkage_weft_pct", "3"))             # Shrinkage Ngang
            ws.cell(row=current_row, column=10, value=f"{row.get('marker_efficiency_pct', '86')}%") # Hiệu suất sơ đồ
            ws.cell(row=current_row, column=11, value="YDS").alignment = Alignment(horizontal="center") # Unit
            ws.cell(row=current_row, column=12, value=row.get("reason_or_logs", ""))                 # Noted / Nhật ký

                     # GÁN FONT VÀ BORDER CHO TOÀN BỘ CÁC Ô DỮ LIỆU VỪA TẠO
            for col_num in range(2, 13):
                c = ws.cell(row=current_row, column=col_num)
                c.font = font_data
                c.border = border_all
                
                # SỬA TRIỆT ĐỂ: Dùng toán tử so sánh tường minh để tránh lỗi cú pháp biên dịch
                is_center_col = (col_num == 2 or col_num == 6 or col_num == 8 or col_num == 9 or col_num == 10 or col_num == 11)
                
                if is_center_col:
                    c.alignment = Alignment(horizontal="center", vertical="center")
                elif col_num == 7:
                    # Căn phải và cố định 3 chữ số thập phân cho cột định mức kỹ thuật
                    c.alignment = Alignment(horizontal="right", vertical="center")
                    c.number_format = '0.000'
                    
            current_row += 1



        # Tự động căn rộng kích thước chiều ngang các cột tương thích nội dung Excel
        for col in ws.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = get_column_letter(col[0].column)
            ws.column_dimensions[col_letter].width = max(max_len + 3, 12)
            
        # Xuất file Excel ra bộ nhớ tạm (Stream Byte IO)
        excel_buffer = io.BytesIO()
        wb.save(excel_buffer)
        excel_buffer.seek(0)
        
        # Tạo nút bấm tải biểu mẫu chất lượng cao ngay trên Streamlit
        st.markdown(" ")
        st.download_button(
            label="📥 TẢI BIỂU MẪU ĐỊNH MỨC KỸ THUẬT PHONG PHÚ (.XLSX)",
            data=excel_buffer,
            file_name=f"BOM_APPROVED_{st.session_state.gemini_parsed_bom_data.get('style_code', 'STYLE')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
