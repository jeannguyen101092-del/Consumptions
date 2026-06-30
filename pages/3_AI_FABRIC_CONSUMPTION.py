import streamlit as st
import pandas as pd
import json
import re
import google.generativeai as genai
from google.generativeai import types

# =====================================================================
# ĐOẠN 1: GLOBAL CONFIG REGISTRY & LÕI TRÍCH XUẤT SỐ HỌC NỀN (V11)
# =====================================================================

# KHỐI QUẢN LÝ BIÊN ĐỘ GIỚI HẠN CHUẨN ĐỊNH MỨC XƯỞNG
LIMITS = {
    "JACKET":     {"range": (1.65, 2.65), "warn_thresh": 2.5},
    "PANT":       {"range": (1.15, 1.75), "warn_thresh": 1.6},  
    "CAPRI_PANT": {"range": (1.15, 2.45), "warn_thresh": 2.2},  
    "CARGO_PANT": {"range": (1.45, 2.85), "warn_thresh": 2.4},  
    "JORT":       {"range": (1.05, 1.35), "warn_thresh": 1.25},
    "DRESS":      {"range": (1.45, 3.25), "warn_thresh": 3.0},
    "TSHIRT":     {"range": (0.65, 1.35), "warn_thresh": 1.4},
    "SHIRT":      {"range": (1.15, 1.95), "warn_thresh": 2.0},
    "DEFAULT":    {"range": (1.15, 2.20), "warn_thresh": 2.2}
}

MAIN_KEYS = ("MAIN FABRIC", "MAIN", "BODY", "SHELL", "SELF FABRIC", "SELFFABRIC", "SELF-FABRIC", "FACE", "OUTER", "PRIMARY", "FABRIC", "MAIN FABRIC", "THÂN", "VẢI CHÍNH", "DENIM", "COTTON")
THREAD_KEYS = ("CHỈ", "THREAD", "ZIPPER", "DÂY KÉO", "BUTTON", "NÚT", "SHANK", "RIVET", "LABEL", "MÁC", "TAG", "EYELETS")
POCKET_KEYS = ("POCKETING", "POCKET BAG", "POCKET", "TÚI", "TC POCKETING")
FUSING_KEYS = ("INTERLINING", "FUSING", "LINING", "MECK", "MEX", "KEO", "LÓT", "DỰNG")
DRAWSTRING_KEYS = ("DRAWSTRING", "DRAW CORD", "DRAWCORD", "DÂY RÚT", "DÂY LUỒN")

def safe_float(val, default=0.0) -> float:
    if val is None: return default
    val_clean = str(val).replace("%", "").replace('"', '').strip().lower()
    if val_clean in ["null", "none", "unknown", "na", "n/a", ""]: return default
    try: return float(val_clean)
    except (ValueError, TypeError): return default

def calculate_cad_area(length: float, width: float, cutable_w: float, row_eff: float) -> float:
    return ((length * width) / (cutable_w * 36.0)) / (row_eff / 100.0)

def detect_product_type(desc_upper: str, raw_inseam_val: float) -> str:
    """Hàm phân loại sản phẩm nâng cao - Đã chuẩn hóa 100% thụt lề thụt dòng."""
    if any(x in desc_upper for x in ["JACKET", "COAT", "VEST", "OUTERWEAR"]):
        return "JACKET"
        
    elif any(x in desc_upper for x in ["JEAN", "DENIM", "PANT", "PANTS", "BAGGY", "TROUSER", "LEGGING", "JORT", "CAPRI", "CARGO"]):
        if any(k in desc_upper for k in ["CARGO", "UTILITY", "CARPENTER", "DOUBLE KNEE"]):
            return "CARGO_PANT"
        if any(k in desc_upper for k in ["CAPRI", "CROP PANT", "CROPPED", "CROP", "ANKLE PANT"]):
            return "CAPRI_PANT"
        return "JORT" if raw_inseam_val < 15.0 else "PANT"
        
    elif any(x in desc_upper for x in ["DRESS", "SKIRT", "VÁY", "ĐẦM", "MAXI"]):
        return "DRESS"
    elif any(x in desc_upper for x in ["TSHIRT", "T-SHIRT", "TEE", "POLO", "ÁO THUN"]):
        return "TSHIRT"
    elif any(x in desc_upper for x in ["SHIRT", "SƠ MI", "BLOUSE", "BUTTON DOWN"]):
        return "SHIRT"
        
    return "DEFAULT"

# =====================================================================
# ĐOẠN 2: LÕI PYTHON CAD ENGINE (SỬA DỨT ĐIỂM BUG CỘNG TRÙNG PHỤ LIỆU CỨNG)
# =====================================================================

def execute_numerical_consumption(ai_blueprint: dict, user_chat: str) -> dict:
    w_chat, s_l_chat, s_w_chat = None, None, None
    chat_clean = str(user_chat).lower().strip()
    match_w = re.search(r'(?:khổ|kho)\s*(\d+)', chat_clean)
    if match_w: w_chat = float(match_w.group(1))
    match_range = re.search(r'(?:co\s*rút|co\s*rut|co)\s*(\d+)\s*(?:-|–|ngang|\s+)\s*(\d+)', chat_clean)
    if match_range: 
        s_l_chat = float(match_range.group(1))
        s_w_chat = float(match_range.group(2))

    body_length = safe_float(ai_blueprint.get("extracted_body_length"), 28.0)
    sleeve_length = safe_float(ai_blueprint.get("extracted_sleeve_length"), 24.0)
    chest_width = safe_float(ai_blueprint.get("extracted_chest_width"), 20.0)
    
    product_type = ai_blueprint.get("detected_product_type", "DEFAULT")
    default_outseam = 31.0 if product_type == "CAPRI_PANT" else (14.0 if product_type == "JORT" else 40.0)
    outseam_length = safe_float(ai_blueprint.get("extracted_outseam_length"), default_outseam)
    hip_width = safe_float(ai_blueprint.get("extracted_hip_width"), 21.0)
    skirt_hem = safe_float(ai_blueprint.get("extracted_skirt_hem_width"), 35.0)

    if product_type == "JACKET": base_area_sq_in = ((body_length * 2) + sleeve_length + 4.0) * ((chest_width * 2) + 5.0)
    elif product_type in ["PANT", "CAPRI_PANT"]: base_area_sq_in = (outseam_length + 4.0) * ((hip_width * 2) + 12.0)
    elif product_type == "JORT": base_area_sq_in = (outseam_length + 4.0) * ((hip_width * 2) + 16.0)
    elif product_type == "DRESS": base_area_sq_in = (body_length + 6.0) * ((skirt_hem * 2) + 4.0)
    elif product_type == "TSHIRT": base_area_sq_in = ((body_length * 2) + 3.0) * ((chest_width * 2) + 3.0)
    elif product_type == "SHIRT": base_area_sq_in = ((body_length * 2) + sleeve_length + 3.5) * ((chest_width * 2) + 4.5)
    else: base_area_sq_in = 30.0 * 50.0

    processed_bom_blueprint = []
    accumulated_self_consumption = 0.0  
    main_fabric_row_index = None        

    for idx, row in enumerate(ai_blueprint.get("bom_rows", [])):
        c_type = str(row.get("component_type", "")).upper()
        placement = str(row.get("placement", "")).upper()
        body_type = str(row.get("body_type", "")).upper()
        
        # --- BỘ LỌC ƯU TIÊN SỐ 1: Bọc chặt, gạt bỏ 100% rác kim loại cứng ra khỏi khối tính diện tích ---
        if any(k in c_type or k in placement or k in body_type for k in [
            "CHỈ", "THREAD", "ZIPPER", "DÂY KÉO", "BUTTON", "NÚT", "SHANK", "RIVET", "LABEL", "MÁC", "TAG", 
            "EYELETS", "ELASTIC", "CHUN", "D-RING", "RING", "MÓC", "SẮT", "KIM LOẠI"
        ]):
            row["calculated_gross_consumption_yds"] = 0.0
            row["reason_or_logs"] = "Bỏ qua toán học phẳng (Phụ liệu phần cứng/Trims)"
            row["status"] = "PASS"
            row["marker_efficiency_pct"] = "N/A"
            processed_bom_blueprint.append(row)
            continue

        is_shell = any(k in body_type for k in MAIN_KEYS) or any(k in c_type for k in MAIN_KEYS) or any(k in placement for k in MAIN_KEYS)
        is_self_word = ("SELF" in c_type or "SELF" in placement or "SELF" in body_type)
        
        is_pocket = any(k in body_type for k in POCKET_KEYS) or any(k in c_type for k in POCKET_KEYS) or any(k in placement for k in POCKET_KEYS)
        is_fusing = any(k in body_type for k in FUSING_KEYS) or any(k in c_type for k in FUSING_KEYS) or any(k in placement for k in FUSING_KEYS)
        is_drawstring = any(k in body_type for k in DRAWSTRING_KEYS) or any(k in c_type for k in DRAWSTRING_KEYS) or any(k in placement for k in DRAWSTRING_KEYS)

        piece_count = safe_float(row.get("piece_count"), 2.0 if is_pocket else 1.0)
        piece_length = safe_float(row.get("piece_length_inch"), 12.0 if is_pocket else 43.0)
        piece_width = safe_float(row.get("piece_width_inch"), 10.0 if is_pocket else 0.375)

        if is_fusing: method = "INTERLINING_AREA"
        elif is_pocket: method = "MERGE_MAIN_POCKET"
        elif is_drawstring: method = "LENGTH_TRIM"
        elif is_shell or is_self_word:
            method = "MAIN_BODY_AREA"
            if main_fabric_row_index is None: main_fabric_row_index = idx
        else: method = "BYPASS"

        w_bom = w_chat if w_chat is not None else safe_float(row.get("fabric_width_inch"), 56.0)
        s_l = s_l_chat if s_l_chat is not None else safe_float(row.get("shrinkage_warp_pct"), 5.0)
        s_w = s_w_chat if s_w_chat is not None else safe_float(row.get("shrinkage_weft_pct"), 10.0)
        eff = max(80.0, min(safe_float(row.get("marker_efficiency_pct"), 88.0), 95.0))
        
        cutable_w = max(40.0, w_bom - 1.5)
        shrink_warp_f, shrink_weft_f = 1.0 + (s_l / 100.0), 1.0 + (s_w / 100.0)
        wastage_f = 1.03

        final_yds, log_txt, row_status = 0.0, f"Method: {method}", "PASS"

        if method == "MAIN_BODY_AREA":
            base_cons = (base_area_sq_in / (cutable_w * 36.0)) / (eff / 100.0)
            row["raw_main_body_consumption_yds"] = base_cons * shrink_warp_f * shrink_weft_f * wastage_f
            
        elif method == "MERGE_MAIN_POCKET":
            pocket_area_sq_in = piece_length * piece_width * piece_count
            calculated_pocket_yds = (pocket_area_sq_in / (cutable_w * 36.0)) / (eff / 100.0) * shrink_warp_f * shrink_weft_f * wastage_f
            # Khóa trần rập túi hợp lý sản xuất (0.28 yds)
            calculated_pocket_yds = min(calculated_pocket_yds, 0.28)
            accumulated_self_consumption += calculated_pocket_yds  
            final_yds = 0.0
            log_txt = "Included in Main Fabric"
            row["notes_display"] = "Included in Main Fabric"
            
        elif method == "LENGTH_TRIM":
            trim_area_sq_in = piece_length * piece_width * piece_count
            calculated_trim_yds = (trim_area_sq_in / (cutable_w * 36.0)) / (eff / 100.0) * shrink_warp_f * wastage_f
            calculated_trim_yds = min(calculated_trim_yds, 0.12)
            accumulated_self_consumption += calculated_trim_yds  
            final_yds = 0.0
            log_txt = "Included in Main Fabric"
            row["notes_display"] = "Included in Main Fabric"
            
        elif method == "POCKETING_FABRIC_ISOLATED":
            final_yds = 0.15 if product_type == "JORT" else 0.25
            log_txt = "Vải lót túi lót chuyên dụng độc lập"
            
        elif method == "INTERLINING_AREA":
            final_yds = 0.10 if product_type in ["PANT", "JORT", "CAPRI_PANT", "CARGO_PANT"] else 0.65
            log_txt = "Diện tích dựng mếch keo phối chi tiết lưng"
            
        else:
            final_yds = 0.0
            log_txt = "Bỏ qua tính toán số học"

        row["calculated_gross_consumption_yds"] = final_yds
        row["reason_or_logs"] = log_txt
        row["status"] = row_status
        row["marker_efficiency_pct"] = f"{int(eff)}%" if method in ["MAIN_BODY_AREA", "MERGE_MAIN_POCKET", "LENGTH_TRIM"] else "N/A"
        row["w_bom_saved"], row["eff_saved"], row["s_l_saved"], row["s_w_saved"] = w_bom, eff, s_l, s_w
        processed_bom_blueprint.append(row)

    if main_fabric_row_index is not None:
        main_row = processed_bom_blueprint[main_fabric_row_index]
        raw_main_body = main_row.get("raw_main_body_consumption_yds", 1.10)
        
        # PHÉP TOÁN XÁC ĐỊNH CHUẨN: Thân quần Capri lửng thô (~1.25) + 1 cụm túi thô (~0.28) + 1 cụm dây luồn thô (~0.12) = ~1.65 Yds thô
        raw_total_with_self = raw_main_body + accumulated_self_consumption
        
        cfg = LIMITS.get(product_type, LIMITS["DEFAULT"])
        if raw_total_with_self > cfg["warn_thresh"]: main_row["status"] = "WARNING"
        if raw_total_with_self > 3.3: main_row["status"] = "CRITICAL"
        
        low, high = cfg["range"]
        final_yds_clamped = round(max(low, min(raw_total_with_self, high)), 2)
        
        main_row["calculated_gross_consumption_yds"] = final_yds_clamped
        main_row["reason_or_logs"] = f"{int(main_row['w_bom_saved'])}\"/{int(main_row['eff_saved'])}%/{int(main_row['s_l_saved'])}x{int(main_row['s_w_saved'])} | Raw={round(raw_total_with_self,2)} → {final_yds_clamped} [Đã sửa lỗi loại trừ phụ liệu kim loại]"

    ai_blueprint["bom_rows"] = processed_bom_blueprint
    return ai_blueprint


# =====================================================================
# ĐOẠN 3: AI BLUEPRINT OBJECT PARSER VÀ RENDERING GIAO DIỆN PHẲNG V11
# =====================================================================

with st.sidebar:
    st.header("⚙️ HỆ THỐNG")
    if st.button("🗑️ Xóa lịch sử & Reset định mức", use_container_width=True):
        st.session_state.bom_data = None
        st.session_state.pdf_bytes = None
        st.session_state.pdf_name = None
        st.session_state.chat_history = [{"role": "assistant", "content": "Hệ thống đã reset sạch cache dữ liệu. Vui lòng tải file PDF mới."}]
        st.rerun()

st.subheader("📁 BƯỚC 1: TẢI BIỂU MẪU SẢN XUẤT TECHPACK PDF")
uploaded_file = st.file_uploader("Kéo và thả file PDF Techpack vào đây", type=["pdf"], key="final_v11_uploader")
if uploaded_file is not None:
    st.session_state.pdf_bytes = uploaded_file.read()
    st.session_state.pdf_name = uploaded_file.name

chat_container = st.container(height=150)
with chat_container:
    for chat in st.session_state.get("chat_history", []):
        with st.chat_message(chat["role"]): st.markdown(chat["content"])

user_prompt = st.chat_input("Nhập thông số cấu hình...")
trigger_calc = st.button("🚀 KÍCH HOẠT AI BÓC TÁCH CẤU TRÚC RẬP", use_container_width=True, type="primary")

if (trigger_calc and "pdf_bytes" in st.session_state) or (user_prompt and "pdf_bytes" in st.session_state):
    current_prompt = user_prompt if user_prompt else "Hãy tự động bóc tách và phân loại bảng dữ liệu rập cho file này."
    if user_prompt: st.session_state.chat_history.append({"role": "user", "content": user_prompt})
    
    # SCHEMA V11: MỞ RỘNG ENUM SẢN PHẨM GỒM CAPRI_PANT VÀ CARGO_PANT CHUẨN CAD
    json_schema = {
        "type": "OBJECT",
        "properties": {
            "style_code": {"type": "STRING"},
            "detected_product_type": {"type": "STRING", "enum": ["JACKET", "PANT", "CAPRI_PANT", "CARGO_PANT", "JORT", "DRESS", "TSHIRT", "SHIRT", "DEFAULT"]},
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
                        "component_type": {"type": "STRING"}, "placement": {"type": "STRING"}, "body_type": {"type": "STRING"},
                        "material_classification": {"type": "STRING", "enum": ["MAIN_FABRIC", "SELF_POCKET", "SELF_DRAWSTRING", "POCKETING_FABRIC", "INTERLINING_FUSING", "HARDWARE_TRIM"]},
                        "fabric_width_inch": {"type": "STRING"}, "marker_efficiency_pct": {"type": "STRING"}, "shrinkage_warp_pct": {"type": "STRING"}, "shrinkage_weft_pct": {"type": "STRING"},
                        "piece_count": {"type": "STRING"}, "piece_length_inch": {"type": "STRING"}, "piece_width_inch": {"type": "STRING"}
                    },
                    "required": ["component_type", "placement", "material_classification"]
                }
            }
        },
        "required": ["detected_product_type", "bom_rows"]
    }

    ocr_master_prompt = f"""
    Bạn là Senior Garment Data Engineer chuyên bóc tách hồ sơ PLM/CAD rập phẳng. Nhiệm vụ của bạn: Đọc file PDF Techpack và trích xuất dữ liệu thô.
    ⚠️ QUY TẮC CỐT LÕI: TUYỆT ĐỐI KHÔNG ĐƯỢC TỰ TÍNH TOÁN HOẶC ĐƯA RA CON SỐ ĐỊNH MỨC YARDS CUỐI CÙNG.
    
    HƯỚNG DẪN TRÍCH XUẤT NGỮ CẢNH:
    1. ĐỌC BẢNG POM: Tìm thông số Spec nền hình học thô (Length, Chest, Outseam...) của Base Size. 
    2. PHÂN LOẠI SẢN PHẨM: 
       - Nếu tài liệu mô tả là quần lửng, quần ngố nữ, Capri, Ankle, Crop hoặc Cropped Pant: Gán detected_product_type='CAPRI_PANT'.
       - Nếu có túi hộp side pocket, carpenter, utility pocket hoặc double knee: Gán detected_product_type='CARGO_PANT'.
    3. QUÉT BẢNG BOM: Tìm kích thước rập phụ của Túi (Pocket), Dây rút (Drawstring/Drawcord), Dây viền (Binding). Nếu tài liệu ghi kích thước (Ví dụ: 3/8" Width, Length 110cm hoặc 13 inch), quy đổi sang đơn vị Inch thô dán vào piece_length_inch, piece_width_inch và piece_count.
    
    Yêu cầu bổ sung: {current_prompt}
    """

    with st.spinner("AI đang thực thi OCR bóc tách và phân rã cấu trúc rập chi tiết..."):
        try:
            pdf_blob = {"mime_type": "application/pdf", "data": st.session_state.pdf_bytes}
            model = genai.GenerativeModel('gemini-2.5-flash')
            response = model.generate_content([pdf_blob, ocr_master_prompt], generation_config=types.GenerationConfig(response_mime_type="application/json", response_schema=json_schema, temperature=0.1))
            ai_blueprint = json.loads(response.text.strip())
            
            # Khởi động máy toán học số học xác định Đoạn 2
            st.session_state.bom_data = execute_numerical_consumption(ai_blueprint, user_prompt)
            st.session_state.chat_history.append({"role": "assistant", "content": "🤖 Đồng bộ thành công V11: Đã phân loại độ phức tạp kết hợp bộ cộng dồn thô."})
        except Exception as e:
            st.session_state.chat_history.append({"role": "assistant", "content": f"❌ Lỗi: {str(e)}. Hãy đợi 1 phút rồi bấm lại nút🚀."})
    st.rerun()

# KHỐI HIỂN THỊ BẢNG ĐỊNH MỨC CAO CẤP V11
if st.session_state.get("bom_data"):
    st.markdown(f"### 📋 BẢNG ĐỊNH MỨC PLM DETECT ENGINE (Phom dáng rập: `{st.session_state.bom_data.get('detected_product_type')}` )")
    flat_rows = []
    for r in st.session_state.bom_data["bom_rows"]:
        display_yds = r.get("calculated_gross_consumption_yds")
        if r.get("notes_display") == "Included in Main Fabric": display_yds = "Included in Main"
        
        flat_rows.append({
            "Giám Sát PLM": "🟢 PASS" if r.get("status") == "PASS" else ("🟡 WARNING" if r.get("status") == "WARNING" else "🔴 CRITICAL"),
            "Nguyên phụ liệu": r.get("component_type"), 
            "Vị trí sử dụng": r.get("placement"),
            "Hiệu suất sơ đồ": r.get("marker_efficiency_pct"), 
            "Định mức Gross (Yds/Pc)": display_yds,
            "Nhật ký Telemetry / Phân tích số học": r.get("reason_or_logs")
        })
    st.dataframe(pd.DataFrame(flat_rows), use_container_width=True)
