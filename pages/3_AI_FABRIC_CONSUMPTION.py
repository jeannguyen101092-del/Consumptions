import streamlit as st
import pandas as pd
import json
import re
import google.generativeai as genai
from google.generativeai import types

# =====================================================================
# ĐOẠN 1: GLOBAL CONFIG REGISTRY & LÕI TRÍCH XUẤT SỐ HỌC NỀN
# =====================================================================

# --- 1. KHỐI QUẢN LÝ BIÊN ĐỘ GIỚI HẠN TẬP TRUNG CHỐNG HARDCODE ---
LIMITS = {
    "JACKET": {"range": (1.65, 2.65), "warn_thresh": 2.5},
    "PANT":   {"range": (1.15, 1.75), "warn_thresh": 1.8},
    "JORT":   {"range": (1.05, 1.35), "warn_thresh": 1.25},
    "DRESS":  {"range": (1.45, 3.25), "warn_thresh": 3.0},
    "TSHIRT": {"range": (0.65, 1.35), "warn_thresh": 1.4},
    "SHIRT":  {"range": (1.15, 1.95), "warn_thresh": 2.0},
    "DEFAULT":{"range": (1.15, 2.20), "warn_thresh": 2.2}
}

# MA TRẬN TỪ KHÓA ĐỘC LẬP - KHÔNG CHỨA CHỮ "SELF" ĐƠN LẺ TRÁNH BẮT NHẦM DÂY PHỐI
MAIN_KEYS = ("MAIN FABRIC", "MAIN", "BODY", "SHELL", "SELF FABRIC", "SELFFABRIC", "SELF-FABRIC", "FACE", "OUTER", "PRIMARY", "FABRIC", "MAIN FABRIC", "THÂN", "VẢI CHÍNH", "DENIM", "COTTON")
THREAD_KEYS = ("CHỈ", "THREAD", "ZIPPER", "DÂY KÉO", "BUTTON", "NÚT", "SHANK", "RIVET", "LABEL", "MÁC", "TAG", "EYELETS")
POCKET_KEYS = ("POCKETING", "POCKET BAG", "POCKET", "TÚI", "TC POCKETING")
FUSING_KEYS = ("INTERLINING", "FUSING", "LINING", "MECK", "MEX", "KEO", "LÓT", "DỰNG")
DRAWSTRING_KEYS = ("DRAWSTRING", "DRAW CORD", "DRAWCORD", "DÂY RÚT", "DÂY LUỒN")

# --- 2. BỘ HÀM BỔ TRỢ HÌNH HỌC RẬP CƠ SỞ ---
def safe_float(val, default=0.0) -> float:
    """Ép kiểu dữ liệu chuỗi bất kỳ từ PDF về số thực an toàn."""
    if val is None: return default
    val_clean = str(val).replace("%", "").replace('"', '').strip().lower()
    if val_clean in ["null", "none", "unknown", "na", "n/a", ""]: return default
    try: return float(val_clean)
    except (ValueError, TypeError): return default

def calculate_cad_area(length: float, width: float, cutable_w: float, row_eff: float) -> float:
    """Tính toán diện tích yards hình học phẳng tiêu chuẩn phần mềm CAD."""
    return ((length * width) / (cutable_w * 36.0)) / (row_eff / 100.0)

def detect_product_type(desc_upper: str, raw_inseam_val: float) -> str:
    """Hàm trung tâm nhận diện phân loại sản phẩm dựa trên từ khóa Techpack."""
    if any(x in desc_upper for x in ["JACKET", "COAT", "VEST", "OUTERWEAR"]): return "JACKET"
    elif any(x in desc_upper for x in ["JEAN", "DENIM", "PANT", "BAGGY", "TROUSER", "LEGGING", "JORT", "CAPRI"]):
        return "JORT" if raw_inseam_val < 15.0 else "PANT"
    elif any(x in desc_upper for x in ["DRESS", "SKIRT", "VÁY", "ĐẦM", "MAXI"]): return "DRESS"
    elif any(x in desc_upper for x in ["TSHIRT", "T-SHIRT", "TEE", "POLO", "ÁO THUN"]): return "TSHIRT"
    elif any(x in desc_upper for x in ["SHIRT", "SƠ MI", "BLOUSE", "BUTTON DOWN"]): return "SHIRT"
    return "DEFAULT"
# =====================================================================
# ĐOẠN 2: LÕI PYTHON CAD ENGINE (RULE ENGINE + MATH ENGINE CỘNG DỒN)
# =====================================================================

def execute_numerical_consumption(ai_blueprint: dict, user_chat: str) -> dict:
    # A. Phân tách và ép số nhanh từ ô chat của người dùng (Ưu tiên cao nhất)
    w_chat, s_l_chat, s_w_chat = None, None, None
    chat_clean = str(user_chat).lower().strip()
    match_w = re.search(r'(?:khổ|kho)\s*(\d+)', chat_clean)
    if match_w: w_chat = float(match_w.group(1))
    match_range = re.search(r'(?:co\s*rút|co\s*rut|co)\s*(\d+)\s*(?:-|–|ngang|\s+)\s*(\d+)', chat_clean)
    if match_range: 
        s_l_chat = float(match_range.group(1))
        s_w_chat = float(match_range.group(2))

    # B. Thu thập thông số kích thước hình học rập nền do AI bóc tách từ Spec PDF
    body_length = safe_float(ai_blueprint.get("extracted_body_length"), 28.0)
    sleeve_length = safe_float(ai_blueprint.get("extracted_sleeve_length"), 24.0)
    chest_width = safe_float(ai_blueprint.get("extracted_chest_width"), 20.0)
    outseam_length = safe_float(ai_blueprint.get("extracted_outseam_length"), 40.0)
    hip_width = safe_float(ai_blueprint.get("extracted_hip_width"), 21.0)
    skirt_hem = safe_float(ai_blueprint.get("extracted_skirt_hem_width"), 35.0)
    
    # Xác định loại sản phẩm bằng hàm tập trung của Đoạn 1
    product_type = ai_blueprint.get("detected_product_type", "DEFAULT")

    # Tính toán diện tích bề mặt rập hình học cơ sở cho Thân chính lớn (Square Inches)
    if product_type == "JACKET": base_area_sq_in = ((body_length * 2) + sleeve_length + 4.0) * ((chest_width * 2) + 5.0)
    elif product_type == "PANT": base_area_sq_in = (outseam_length + 3.0) * ((hip_width * 2) + 6.0)
    elif product_type == "JORT": base_area_sq_in = (outseam_length + 4.0) * ((hip_width * 2) + 16.0)
    elif product_type == "DRESS": base_area_sq_in = (body_length + 6.0) * ((skirt_hem * 2) + 4.0)
    elif product_type == "TSHIRT": base_area_sq_in = ((body_length * 2) + 3.0) * ((chest_width * 2) + 3.0)
    elif product_type == "SHIRT": base_area_sq_in = ((body_length * 2) + sleeve_length + 3.5) * ((chest_width * 2) + 4.5)
    else: base_area_sq_in = 30.0 * 50.0

    processed_bom_blueprint = []
    accumulated_self_consumption = 0.0  # Bộ nhớ lưu trữ tổng Yards chi tiết phối cắt từ vải chính
    main_fabric_row_index = None        # Đánh dấu chỉ số dòng vải thân chính lớn đầu tiên

    for idx, row in enumerate(ai_blueprint.get("bom_rows", [])):
        c_type = str(row.get("component_type", "")).upper()
        placement = str(row.get("placement", "")).upper()
        body_type = str(row.get("body_type", "")).upper()
        
        # Loại bỏ phụ liệu cứng đếm chiếc khỏi bàn tính phẳng
        if any(k in c_type or k in placement for k in THREAD_KEYS): continue

        # --- PYTHON LOOKUP RULE MATRIX: MA TRẬN PHÂN LOẠI ĐỊNH LÝ TỰ ĐỘNG CHUẨN PLM ---
        is_shell = any(k in body_type for k in MAIN_KEYS) or any(k in c_type for k in MAIN_KEYS) or any(k in placement for k in MAIN_KEYS)
        is_self_word = ("SELF" in c_type or "SELF" in placement or "SELF" in body_type)
        
        is_pocket = any(k in body_type for k in POCKET_KEYS) or any(k in c_type for k in POCKET_KEYS) or any(k in placement for k in POCKET_KEYS)
        is_fusing = any(k in body_type for k in FUSING_KEYS) or any(k in c_type for k in FUSING_KEYS) or any(k in placement for k in FUSING_KEYS)
        is_drawstring = any(k in body_type for k in DRAWSTRING_KEYS) or any(k in c_type for k in DRAWSTRING_KEYS) or any(k in placement for k in DRAWSTRING_KEYS)

        # Trích xuất dữ liệu rập chi tiết từ AI để phục vụ công thức CAD Dynamic (Tuyệt đối không dùng số cứng)
        piece_count = safe_float(row.get("piece_count"), 2.0 if is_pocket else 1.0)
        piece_length = safe_float(row.get("piece_length_inch"), 12.0 if is_pocket else 43.0)
        piece_width = safe_float(row.get("piece_width_inch"), 10.0 if is_pocket else 0.375)

        # Định lý hóa cơ chế gán phương pháp tính toán
        if is_fusing: method = "INTERLINING_AREA"
        elif is_pocket and (is_shell or is_self_word): method = "MERGE_MAIN_POCKET"
        elif is_pocket and not (is_shell or is_self_word): method = "POCKETING_FABRIC_ISOLATED"
        elif is_drawstring and (is_shell or is_self_word): method = "LENGTH_TRIM"
        elif is_shell:
            row_w_check = safe_float(row.get("fabric_width_inch"), 0.0)
            # Nếu tên là SELF đơn thuần nhưng khổ vải bằng 0 hoặc rỗng -> Xác định là dây viền rác phối
            if (c_type == "SELF" or placement == "SELF") and row_w_check <= 0:
                method = "LENGTH_TRIM"
            else:
                method = "MAIN_BODY_AREA"
                if main_fabric_row_index is None: main_fabric_row_index = idx
        else: method = "BYPASS"

        # Khóa cấu hình thông số vải vật lý
        w_bom = w_chat if w_chat is not None else safe_float(row.get("fabric_width_inch"), 58.0)
        s_l = s_l_chat if s_l_chat is not None else safe_float(row.get("shrinkage_warp_pct"), 3.0)
        s_w = s_w_chat if s_w_chat is not None else safe_float(row.get("shrinkage_weft_pct"), 3.0)
        eff = max(80.0, min(safe_float(row.get("marker_efficiency_pct"), 86.0), 95.0))
        
        cutable_w = max(40.0, w_bom - 1.5)
        shrink_warp_f, shrink_weft_f = 1.0 + (s_l / 100.0), 1.0 + (s_w / 100.0)
        wastage_f = 1.04

        final_yds, log_txt, row_status = 0.0, f"Method: {method}", "PASS"

        # --- KHỐI ENGINE TOÁN HỌC SỐ HỌC DYNAMIC (PYTHON MATH ENGINE) ---
        if method == "MAIN_BODY_AREA":
            base_cons = (base_area_sq_in / (cutable_w * 36.0)) / (eff / 100.0)
            raw_total = base_cons * shrink_warp_f * shrink_weft_f * wastage_f
            
            # Đánh giá Warning/Critical dựa trên dữ liệu thô trước khi Clamp biên an toàn
            cfg = LIMITS.get(product_type, LIMITS["DEFAULT"])
            if raw_total > cfg["warn_thresh"]: row_status = "WARNING"
            if raw_total > 3.3: row_status = "CRITICAL"
            
            low, high = cfg["range"]
            final_gross_yards = round(max(low, min(raw_total, high)), 2)
            final_yds = final_gross_yards
            log_txt = f"{int(w_bom)}\"/{int(eff)}%/{int(s_l)}x{int(s_w)} | Thân chính"
            
        elif method == "MERGE_MAIN_POCKET":
            # TỰ ĐỘNG TÍNH DIỆN TÍCH RẬP TÚI DYNAMIC THEO LƯỢNG CHI TIẾT
            pocket_area_sq_in = piece_length * piece_width * piece_count
            calculated_pocket_yds = (pocket_area_sq_in / (cutable_w * 36.0)) / (eff / 100.0) * shrink_warp_f * shrink_weft_f * wastage_f
            accumulated_self_consumption += calculated_pocket_yds  # Đẩy vào bộ cộng dồn tích lũy
            final_yds = 0.0
            log_txt = f"Rập túi vải chính ({int(piece_length)}x{int(piece_width)}\" x{int(piece_count)}) -> Đã cộng dồn vào Vải chính"
            row["notes_display"] = "Included in Main Fabric"
            
        elif method == "LENGTH_TRIM":
            # TỰ ĐỘNG TÍNH ĐỊNH MỨC DÂY THEO CHIỀU DÀI THỰC TẾ CM/INCH TRÊN SƠ ĐỒ CẮT
            trim_area_sq_in = piece_length * piece_width * piece_count
            calculated_trim_yds = (trim_area_sq_in / (cutable_w * 36.0)) / (eff / 100.0) * shrink_warp_f * wastage_f
            accumulated_self_consumption += calculated_trim_yds  # Đẩy vào bộ cộng dồn tích lũy
            final_yds = 0.0
            log_txt = f"Dây luồn vải chính (Dài {round(piece_length,1)}\" x Rộng {piece_width}\") -> Đã cộng dồn vào Vải chính"
            row["notes_display"] = "Included in Main Fabric"
            
        elif method == "POCKETING_FABRIC_ISOLATED":
            final_yds = 0.15 if product_type == "JORT" else 0.25
            log_txt = "Vải lót túi chuyên dụng độc lập (Tính riêng biệt)"
            
        elif method == "INTERLINING_AREA":
            final_yds = 0.10 if product_type in ["PANT", "JORT"] else 0.65
            log_txt = "Diện tích dựng mếch keo phối chi tiết"

        row["calculated_gross_consumption_yds"] = final_yds
        row["reason_or_logs"] = log_txt
        row["status"] = row_status
        row["marker_efficiency_pct"] = f"{int(eff)}%" if method in ["MAIN_BODY_AREA", "MERGE_MAIN_POCKET", "LENGTH_TRIM"] else "N/A"
        processed_bom_blueprint.append(row)

    # --- HỆ THỐNG CỘNG DỒN LUỸ TIẾN CUỐI CÙNG (FINAL OVERLAY MATRIX) ---
    if main_fabric_row_index is not None and accumulated_self_consumption > 0:
        main_row = processed_bom_blueprint[main_fabric_row_index]
        main_row["calculated_gross_consumption_yds"] = round(main_row["calculated_gross_consumption_yds"] + accumulated_self_consumption, 2)
        main_row["reason_or_logs"] += f" [Cộng bù rập chi tiết phối +{round(accumulated_self_consumption, 2)}yds]"

    ai_blueprint["bom_rows"] = processed_bom_blueprint
    return ai_blueprint
# =====================================================================
# ĐOẠN 3: GEMINI CAD OBJECT PARSER & GIAO DIỆN STREAMLIT LUỒNG CHÍNH
# =====================================================================

st.subheader("📁 BẢNG ĐỊNH MỨC CAD COMPONENT ENGINE (V9)")
uploaded_file = st.file_uploader("Kéo và thả file PDF Techpack hoặc bảng BOM vào đây", type=["pdf"], key="plm_pdf_uploader")

if uploaded_file is not None:
    st.session_state.pdf_bytes = uploaded_file.read()
    st.session_state.pdf_name = uploaded_file.name

chat_container = st.container(height=200)
with chat_container:
    for chat in st.session_state.get("chat_history", []):
        with st.chat_message(chat["role"]): st.markdown(chat["content"])

user_prompt = st.chat_input("Nhập thông số cấu hình vải (Ví dụ: Khổ 56 co rút 3 - 12)...")

if user_prompt and "pdf_bytes" in st.session_state:
    st.session_state.chat_history.append({"role": "user", "content": user_prompt})
    
    # SYSTEM JSON SCHEMA CAO CẤP - ÉP AI TRÍCH XUẤT ĐỐI TƯỢNG HÌNH HỌC RẬP THÔ
    json_schema = {
        "type": "OBJECT",
        "properties": {
            "style_code": {"type": "STRING"},
            "detected_product_type": {"type": "STRING", "enum": ["JACKET", "PANT", "JORT", "DRESS", "TSHIRT", "SHIRT", "DEFAULT"]},
            "extracted_body_length": {"type": "STRING"}, 
            "extracted_sleeve_length": {"type": "STRING"}, 
            "extracted_chest_width": {"type": "STRING"},
            "extracted_outseam_length": {"type": "STRING"}, 
            "extracted_hip_width": {"type": "STRING"}, 
            "extracted_skirt_hem_width": {"type": "STRING"},
            "bom_rows": {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "component_type": {"type": "STRING"}, 
                        "placement": {"type": "STRING"}, 
                        "body_type": {"type": "STRING"},
                        "fabric_width_inch": {"type": "STRING"}, 
                        "marker_efficiency_pct": {"type": "STRING"},
                        "shrinkage_warp_pct": {"type": "STRING"},
                        "shrinkage_weft_pct": {"type": "STRING"},
                        "piece_count": {"type": "STRING"},       # Số lượng cấu kiện chi tiết rập
                        "piece_length_inch": {"type": "STRING"}, # Chiều dài cấu kiện rập thô bóc từ CAD/PDF
                        "piece_width_inch": {"type": "STRING"}   # Chiều rộng cấu kiện rập thô bóc từ CAD/PDF
                    },
                    "required": ["component_type", "placement"]
                }
            }
        },
        "required": ["detected_product_type", "bom_rows"]
    }

    reasoning_prompt = """
    Bạn là Senior CAD Object Specialist hệ thống PLM quốc tế. Nhiệm vụ: Đọc file PDF Techpack để bóc tách thông số.
    QUY TẮC BÓC TÁCH NGỮ CẢNH KHÔNG SAI LỆCH:
    1. Trích xuất thông số Spec nền hình học thô (Length, Chest, Hip, Outseam) của trang phục từ bảng POM.
    2. Quét mảng BOM: Tìm các chi tiết rập phụ như Túi (Pocket), Dây rút (Drawstring/Drawcord), Dây viền (Binding/Tape). Nếu tài liệu có ghi kích thước (Ví dụ: 3/8" Width, Length 110cm hoặc 13 inch), hãy quy đổi sang đơn vị Inch thô và gán chính xác vào các trường piece_length_inch, piece_width_inch và piece_count. Tuyệt đối không tự tính toán Yards tổng.
    """

    with st.spinner("AI Reasoning Engine đang phân rã cấu trúc rập chi tiết..."):
        try:
            pdf_blob = {"mime_type": "application/pdf", "data": st.session_state.pdf_bytes}
            model = genai.GenerativeModel('gemini-2.5-flash')
            response = model.generate_content([pdf_blob, reasoning_prompt], generation_config=types.GenerationConfig(response_mime_type="application/json", response_schema=json_schema, temperature=0.1))
            ai_blueprint = json.loads(response.text.strip())
            
            # Khởi động máy toán học Số học Python Rule Engine (Đoạn 2)
            st.session_state.bom_data = execute_numerical_consumption(ai_blueprint, user_prompt)
            st.session_state.chat_history.append({"role": "assistant", "content": "🤖 Đồng bộ thành công: AI phân rã chi tiết rập, Python Rule Engine làm toán định lý."})
        except Exception as e: 
            st.session_state.chat_history.append({"role": "assistant", "content": f"❌ Lỗi xử lý hệ thống: {str(e)}"})
    st.rerun()

# RENDER BẢNG HIỂN THỊ PHẲNG TRÊN GIAO DIỆN STREAMLIT
if st.session_state.bom_data:
    st.markdown(f"### 📋 BẢNG ĐỊNH MỨC CAD ENGINE V9 (Kiểu dáng: `{st.session_state.bom_data.get('detected_product_type')}` )")
    
    flat_rows = []
    for r in st.session_state.bom_data["bom_rows"]:
        # Chuyển đổi hiển thị Yards cho các dòng chi tiết phối đã được tích hợp cộng dồn vào vải chính
        display_yds = r.get("calculated_gross_consumption_yds")
        status_display = r.get("status", "PASS")
        
        if r.get("notes_display") == "Included in Main Fabric":
            display_yds = "Included in Main"
            status_display = "PASS"
            
        flat_rows.append({
            "Giám Sát PLM": "🟢 PASS" if status_display == "PASS" else ("🟡 WARNING" if status_display == "WARNING" else "🔴 CRITICAL"),
            "Nguyên phụ liệu": r.get("component_type"), 
            "Vị trí sử dụng": r.get("placement"),
            "Khổ vải (inch)": r.get("fabric_width_inch", "N/A"),
            "Hiệu suất sơ đồ": r.get("marker_efficiency_pct", "N/A"),
            "Định mức Gross (Yds/Pc)": display_yds,
            "Nhật ký Telemetry Hệ Thống May": r.get("reason_or_logs")
        })
    st.dataframe(pd.DataFrame(flat_rows), use_container_width=True)
