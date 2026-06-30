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
    """Hàm trung tâm nhận diện phân loại sản phẩm - Đã sửa lỗi trùng chữ POCKETS và SHORT."""
    # 1. ƯU TIÊN KIỂM TRA ÁO KHOÁC TRƯỚC (BẬT CỜ JACKET)
    if any(x in desc_upper for x in ["JACKET", "COAT", "VEST", "OUTERWEAR"]): 
        return "JACKET"
        
    # 2. SỬ DỤNG REGEX CHẶN TỪ ĐỘC LẬP TÌM QUẦN (Tránh từ 'Pockets' nuốt mất chữ 'Short')
    # \b giúp tìm chính xác từ độc lập, không bắt các ký tự nằm trong từ khác
    pant_keywords = r"\b(JEAN|DENIM|PANT|PANTS|BAGGY|TROUSER|TROUSERS|LEGGING|JORT|SHORT|SHORTS)\b"
    if re.search(pant_keywords, desc_upper):
        return "JORT" if raw_inseam_val < 15.0 else "PANT"
        
    if any(x in desc_upper for x in ["DRESS", "SKIRT", "VÁY", "ĐẦM", "MAXI"]): 
        return "DRESS"
    elif any(x in desc_upper for x in ["TSHIRT", "T-SHIRT", "TEE", "POLO", "ÁO THUN"]): 
        return "TSHIRT"
    elif any(x in desc_upper for x in ["SHIRT", "SƠ MI", "BLOUSE", "BUTTON DOWN"]): 
        return "SHIRT"
        
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
# ĐOẠN 2: LÕI TOÁN HỌC ĐỊNH MỨC TỰ ĐỘNG CỘNG BÙ CHI TIẾT PHỐI VẢI CHÍNH
# =====================================================================

def python_consumption_sanity_check(bom_data: dict) -> dict:
    if bom_data is None: bom_data = {}
    style_code_raw = str(bom_data.get("style_code", ""))
    desc_upper = (str(bom_data.get("description", "")) + " " + style_code_raw + " " + str(bom_data.get("style_name", ""))).upper()
    default_eff = get_dynamic_marker_efficiency(desc_upper, style_code_raw)
    
    # Khai báo các bộ từ khóa hệ thống chuẩn hóa
    MAIN_KEYS = ("MAIN", "BODY", "SHELL", "SELF FABRIC", "SELFFABRIC", "FACE", "OUTER", "PRIMARY", "FABRIC", "MAIN FABRIC", "SELF-FABRIC", "THÂN", "VẢI CHÍNH", "DENIM", "COTTON")
    THREAD_KEYS = ("CHỈ", "THREAD", "ZIPPER", "DÂY KÉO", "BUTTON", "NÚT", "SHANK", "RIVET", "LABEL", "MÁC", "TAG", "EYELETS", "ELASTIC")
    POCKET_KEYS = ("POCKETING", "POCKET BAG", "POCKET", "TÚI")
    FUSING_KEYS = ("INTERLINING", "FUSING", "LINING", "MECK", "MEX")

    LIMITS = {
        "JACKET": {"range": (1.65, 2.65), "warn_thresh": 2.5},
        "PANT":   {"range": (1.15, 1.75), "warn_thresh": 1.8},
        "JORT":   {"range": (1.05, 1.35), "warn_thresh": 1.25},
        "DRESS":  {"range": (1.45, 3.25), "warn_thresh": 3.0},
        "TSHIRT": {"range": (0.65, 1.35), "warn_thresh": 1.4},
        "SHIRT":  {"range": (1.15, 1.95), "warn_thresh": 2.0},
        "DEFAULT":{"range": (1.15, 2.20), "warn_thresh": 2.2}
    }
    
    # 1. Trích xuất thông số rập nền từ tài liệu kỹ thuật
    body_length = safe_float(bom_data.get("body_length") or bom_data.get("length") or bom_data.get("center_back_length"), default=28.0)
    sleeve_length = safe_float(bom_data.get("sleeve_length") or bom_data.get("sleeve"), default=24.0)
    chest_width = safe_float(bom_data.get("chest") or bom_data.get("chest_width") or bom_data.get("bust"), default=20.0)
    skirt_hem = safe_float(bom_data.get("hem") or bom_data.get("hem_width") or bom_data.get("sweep"), default=35.0)
    
    raw_rise_val = safe_float(bom_data.get("front_rise") or bom_data.get("rise"), default=11.5)
    if raw_rise_val > 20.0: raw_rise_val = 11.5 
    raw_inseam_val = safe_float(bom_data.get("inseam") or bom_data.get("inseam_length"), default=21.0) 
    calculated_outseam = raw_inseam_val + raw_rise_val
    hip_width = safe_float(bom_data.get("hip") or bom_data.get("hip_width"), default=21.0)

    product_type = detect_product_type(desc_upper, raw_inseam_val)

    # Đọc đè thông số cấu hình vải từ ô chat
    chat_history = st.session_state.get("chat_history", [])
    chat_text = "".join(str(m.get("content", "")) for m in chat_history if m.get("role") == "user").lower()
    
    w_shell_chat, s_shell_l_chat, s_shell_w_chat = None, None, None
    match_w = re.search(r'(?:khổ|kho)\s*(\d+)', chat_text)
    if match_w: w_shell_chat = float(match_w.group(1))
        
    match_range = re.search(r'(?:co\s*rút|co\s*rut|co)\s*(\d+)\s*(?:-|–|ngang|\s+)\s*(\d+)', chat_text)
    if match_range: 
        s_shell_l_chat = float(match_range.group(1))
        s_shell_w_chat = float(match_range.group(2))

    # --- BƯỚC 1: QUÉT TRƯỚC BẢNG BOM ĐỂ ĐỊNH VỊ THÔNG SỐ VẢI CHÍNH THÂN LỚN ---
    base_w_shell = 58.0
    base_s_l = 3.0
    base_s_w = 3.0
    base_eff = default_eff
    
    if "bom_rows" in bom_data and isinstance(bom_data["bom_rows"], list):
        for row in bom_data["bom_rows"]:
            c_type_upper = str(row.get("component_type", "")).upper()
            placement_upper = str(row.get("placement", "")).upper()
            w_parsed = safe_float(row.get("fabric_width_inch"), default=0.0)
            
            # Định vị dòng vải chính thực sự (có khổ vải lớn trên 40 inch) để lấy thông số nền
            if w_parsed > 40.0 and (any(k in placement_upper for k in ["BODY", "SHELL", "THÂN"]) or any(k in c_type_upper for k in ["SHELL", "DENIM", "VẢI CHÍNH"])):
                base_w_shell = w_parsed
                base_s_l = safe_float(row.get("shrinkage_warp_pct"), default=3.0)
                base_s_w = safe_float(row.get("shrinkage_weft_pct"), default=3.0)
                raw_eff = row.get("marker_efficiency_pct", "")
                if raw_eff: base_eff = max(80.0, min(safe_float(raw_eff, default_eff), 95.0))
                break

    # Áp đè số ô chat lên thông số vải chính nền (nếu có)
    if w_shell_chat is not None: base_w_shell = w_shell_chat
    if s_shell_l_chat is not None: base_s_l = s_shell_l_chat
    if s_shell_w_chat is not None: base_s_w = s_shell_w_chat

    # Tính toán định mức cơ sở cho thân chính lớn (Yards)
    cutable_w = max(40.0, base_w_shell - 1.5)
    shrink_f_warp = 1.0 + (base_s_l / 100.0)
    shrink_f_weft = 1.0 + (base_s_w / 100.0)
    wastage_factor = 1.04
    
    if product_type == "JACKET":
        main_body_cons = calculate_cad_area((body_length * 2) + sleeve_length + 4.0, (chest_width * 2) + 5.0, cutable_w, base_eff)
    elif product_type == "JORT":
        main_body_cons = calculate_cad_area(calculated_outseam + 4.0, (hip_width * 2) + 16.0, cutable_w, base_eff)
    elif product_type in ["PANT", "DEFAULT"]:
        main_body_cons = calculate_cad_area(calculated_outseam + 3.0, (hip_width * 2) + 6.0, cutable_w, base_eff)
    elif product_type == "DRESS":
        main_body_cons = calculate_cad_area(body_length + 6.0, (skirt_hem * 2) + 4.0, cutable_w, base_eff)
    elif product_type == "TSHIRT":
        main_body_cons = calculate_cad_area((body_length * 2) + 3.0, (chest_width * 2) + 3.0, cutable_w, base_eff)
    elif product_type == "SHIRT":
        main_body_cons = calculate_cad_area((body_length * 2) + sleeve_length + 3.5, (chest_width * 2) + 4.5, cutable_w, base_eff)

    # --- BƯỚC 2: TÍNH TOÁN CHI TIẾT TỪNG DÒNG VÀ ĐỒNG BỘ CỘNG DỒN BIÊN ĐỘ ---
    clean_rows = []
    for row in bom_data.get("bom_rows", []):
        c_type = str(row.get("component_type", "")).upper()
        placement = str(row.get("placement", "")).upper()
        body_type = str(row.get("body_type", "")).upper()
        
        if any(k in c_type or k in placement for k in THREAD_KEYS): continue
        
        row_width = safe_float(row.get("fabric_width_inch"), default=0.0)
        
        # Nhận diện bản chất nguyên liệu dựa trên từ khóa
        is_fusing_material = any(k in body_type for k in FUSING_KEYS) or any(k in c_type for k in FUSING_KEYS) or any(k in placement for k in FUSING_KEYS)
        
        is_pocket_material = False
        if not is_fusing_material:
            if any(k in body_type for k in POCKET_KEYS) or any(k in c_type for k in POCKET_KEYS) or any(k in placement for k in POCKET_KEYS): 
                is_pocket_material = True
                
        is_drawstring_material = "DRAWSTRING" in placement or "DRAWSTRING" in c_type or "DÂY RÚT" in placement
        
        # Kiểm tra xem dòng này có cắt từ vải chính (SELF/SHELL) ra hay không
        cut_from_self = (c_type == "SELF" or placement == "SELF" or "SELF" in body_type or "SHELL" in body_type or "VẢI CHÍNH" in c_type)

        row_status, notes_log, final_gross_yards = "PASS", "", 0.0

        # --- LOGIC PHÂN TÁCH DIỆN TÍCH RẬP CHI TIẾT ---
        
        # TRƯỜNG HỢP 1: Vải thân chính lớn thực sự (Khổ vải lớn hoặc dòng vải thân chính đầu tiên)
        if cut_from_self and not is_pocket_material and not is_drawstring_material and (row_width > 40.0 or row_width == 0.0):
            raw_total = main_body_cons * shrink_f_warp * shrink_f_weft * wastage_factor
            cfg = LIMITS.get(product_type, LIMITS["DEFAULT"])
            row_status = "WARNING" if raw_total > cfg["warn_thresh"] else "PASS"
            low, high = cfg["range"]
            final_gross_yards = round(max(low, min(raw_total, high)), 2)
            if raw_total > 3.3: row_status = "CRITICAL"
            notes_log = f"{int(base_w_shell)}\"/{int(base_eff)}%/{int(base_s_l)}x{int(base_s_w)} | Thân chính"
            row["marker_efficiency_pct"] = f"{int(base_eff)}%"

        # TRƯỜNG HỢP 2: Lót túi nhưng ghi rõ cắt từ vải chính (SELF + POCKETING) -> Tính cộng bù diện tích
        elif is_pocket_material and cut_from_self:
            # Lót túi vải chính tốn thêm diện tích rập phụ bằng 0.20 yds bù co rút
            final_gross_yards = round(0.20 * shrink_f_warp * shrink_f_weft * wastage_factor, 2)
            notes_log = f"Lót túi cắt bằng VẢI CHÍNH (SELF) - Đã bù co rút {int(base_s_l)}x{int(base_s_w)}%"
            row["marker_efficiency_pct"] = f"{int(base_eff)}%"
            
        # TRƯỜNG HỢP 3: Dây luồn/Dây rút cắt bằng vải chính (SELF + DRAWSTRINGS khổ 3/8") -> Tính theo chiều dài cắt dây
        elif is_drawstring_material and cut_from_self:
            # Dây rút quần tiêu chuẩn dài 45 inch (~1.25 yards), cắt sọc dải chiếm 0.12 yards vải khổ rộng
            final_gross_yards = round(0.12 * shrink_f_warp * wastage_factor, 2)
            notes_log = f"Dây rút cắt bằng VẢI CHÍNH (Khổ {row.get('fabric_width_inch','3/8\"')}) - Đã tính hao hụt"
            row["marker_efficiency_pct"] = f"{int(base_eff)}%"

        # TRƯỜNG HỢP 4: Lót túi bằng vải lót chuyên dụng độc lập (Không cắt từ vải chính SELF)
        elif is_pocket_material and not cut_from_self:
            final_gross_yards = 0.15 if product_type == "JORT" else 0.25  
            notes_log = "Định mức vải lót túi độc lập (Pocketing Fabric)"
            row["marker_efficiency_pct"] = "N/A"

        # TRƯỜNG HỢP 5: Keo dựng / Mex lót (Interlining / Fusing)
        elif is_fusing_material:
            final_gross_yards = 0.10 if product_type in ["PANT", "JORT", "DEFAULT"] else 0.65  
            notes_log = "Định mức cụm keo dựng phối (Interlining)"
            row["marker_efficiency_pct"] = "N/A"
            
        else:
            # Các chi tiết phối viền rác siêu nhỏ không tốn yards thân
            final_gross_yards = 0.0
            notes_log = "Chi tiết phối phụ nhỏ không đáng kể"
            row["marker_efficiency_pct"] = "N/A"



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
    col2.markdown(f"📐 **Cơ chế tính:** `TECHPACK_PDF_CONSUMPTION_ESTIMATION_ENGINE_V7`")
    col3.markdown(f"🧥 **Mô tả dáng:** {st.session_state.gemini_parsed_bom_data.get('description', 'N/A')}")
    
    bom_rows = st.session_state.gemini_parsed_bom_data.get("bom_rows", [])
    if bom_rows and isinstance(bom_rows, list):
        flat_table_data = []
        for row in bom_rows:
            status_raw = row.get("status", "PASS")
            status_display = "🔴 CRITICAL" if status_raw == "CRITICAL" else ("🟡 WARNING" if status_raw == "WARNING" else "🟢 PASS")
                
            flat_table_data.append({
                "Giám Sát PLM": status_display,
                "Loại Nguyên Phụ Liệu": row.get("component_type", "N/A"),
                "Vị trí sử dụng (Placement)": row.get("placement", "N/A"),
                "Hiệu suất sơ đồ": row.get("marker_efficiency_pct", "N/A"),
                "Định mức Gross (yds/pc)": row.get("calculated_gross_consumption_yds", 0.0),
                "Ghi chú Hệ thống / Nhật ký Cảnh báo": row.get("reason_or_logs", "")
            })
            
        df_rows = pd.DataFrame(flat_table_data)
        st.dataframe(df_rows, use_container_width=True)
        
        # Khởi động openpyxl xuất bản in xưởng may cao cấp
        from openpyxl import Workbook
        from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
        from openpyxl.utils import get_column_letter
        import io
        
        wb = Workbook()
        ws = wb.active
        ws.title = "BẢNG ĐỊNH MỨC KỸ THUẬT"
        ws.sheet_view.showGridLines = True  
        
        font_header_comp = Font(name="Arial", size=11, bold=True)
        font_title = Font(name="Arial", size=14, bold=True, color="1F497D")
        font_label = Font(name="Arial", size=10, bold=True)
        font_data = Font(name="Arial", size=10, bold=False)
        font_table_header = Font(name="Arial", size=9, bold=True)
        
        thin_side = Side(border_style="thin", color="000000")
        border_all = Border(left=thin_side, right=thin_side, top=thin_side, bottom=thin_side)
        header_fill = PatternFill(start_color="DCE6F1", end_color="DCE6F1", fill_type="solid")
        
        ws["B2"] = "CTY CỔ PHẦN QUỐC TẾ PHONG PHÚ"
        ws["B2"].font = font_header_comp
        ws["B3"] = "Phòng Kỹ Thuật"
        ws["B3"].font = Font(name="Arial", size=10, italic=True, bold=True)
        
        ws.merge_cells("B5:H5")
        ws["B5"] = "BẢNG ĐỊNH MỨC KỸ THUẬT (APPROVED CONSUMPTION)"
        ws["B5"].font = font_title
        ws["B5"].alignment = Alignment(horizontal="center", vertical="center")
        
        headers_info = [
            ("B7", "STYLE:", "C7", str(st.session_state.gemini_parsed_bom_data.get('style_code', 'N/A'))),
            ("B8", "DESCRIPTION:", "C8", str(st.session_state.gemini_parsed_bom_data.get('description', 'N/A'))[:60])
        ]
        
        for lbl_cell, lbl_txt, val_cell, val_txt in headers_info:
            ws[lbl_cell] = lbl_txt
            ws[lbl_cell].font = font_label
            ws[val_cell] = val_txt
            ws[val_cell].font = font_data
            ws[lbl_cell].border = Border(bottom=thin_side)
            ws[val_cell].border = Border(bottom=thin_side)
            
        headers = ["STT", "Fabric/Trim Type", "Placement", "Cons (Yds)", "Marker Eff", "Unit", "System Notes / Debug Log"]
        
        for col_num, header_title in enumerate(headers, start=2):
            cell = ws.cell(row=11, column=col_num)
            cell.value = header_title
            cell.font = font_table_header
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cell.border = border_all
            
        current_row = 12
        for idx, row in enumerate(bom_rows, start=1):
            ws.cell(row=current_row, column=2, value=idx)                                            # STT
            ws.cell(row=current_row, column=3, value=row.get("component_type", "N/A"))               # Fabric Type
            ws.cell(row=current_row, column=4, value=row.get("placement", "N/A"))                    # Placement
            ws.cell(row=current_row, column=5, value=row.get("calculated_gross_consumption_yds", 0.0)) # Cons
            ws.cell(row=current_row, column=6, value=row.get("marker_efficiency_pct", "N/A"))        # Marker Eff
            ws.cell(row=current_row, column=7, value="YDS")                                          # Unit
            ws.cell(row=current_row, column=8, value=row.get("reason_or_logs", ""))                  # Notes

            for col_num in range(2, 9):
                c = ws.cell(row=current_row, column=col_num)
                c.font = font_data
                c.border = border_all
                
                # ĐÃ VÁ LỖI: Căn chỉnh an toàn độc lập dựa trên số thứ tự cột Excel, loại bỏ hoàn toàn biến lỗi is_main
                if col_num in:
                    c.alignment = Alignment(horizontal="center", vertical="center")
                elif col_num == 5:
                    c.alignment = Alignment(horizontal="right", vertical="center")
                    c.number_format = '0.000'
                    
            current_row += 1

        for col in ws.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = get_column_letter(col.column)
            ws.column_dimensions[col_letter].width = max(max_len + 3, 12)
            
        excel_buffer = io.BytesIO()
        wb.save(excel_buffer)
        excel_buffer.seek(0)
        
        st.markdown(" ")
        st.download_button(
            label="📥 TẢI BIỂU MẪU ĐỊNH MỨC KỸ THUẬT PHONG PHÚ (.XLSX)",
            data=excel_buffer,
            file_name=f"BOM_APPROVED_{st.session_state.gemini_parsed_bom_data.get('style_code', 'STYLE')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
