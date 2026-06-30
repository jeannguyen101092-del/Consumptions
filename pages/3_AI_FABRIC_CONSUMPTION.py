import streamlit as st
import pandas as pd
import json
import re
import google.generativeai as genai
from google.generativeai import types

# --- 1. CONFIG REGISTRY TOÀN CỤC (GLOBAL RULES & LIMITS CHUẨN XƯỞNG PHONG PHÚ) ---
LIMITS = {
    "JACKET": {"range": (1.65, 2.65), "warn_thresh": 2.5},
    "PANT":   {"range": (1.15, 1.75), "warn_thresh": 1.8},
    "JORT":   {"range": (1.05, 1.35), "warn_thresh": 1.25},
    "DRESS":  {"range": (1.45, 3.25), "warn_thresh": 3.0},
    "TSHIRT": {"range": (0.65, 1.35), "warn_thresh": 1.4},
    "SHIRT":  {"range": (1.15, 1.95), "warn_thresh": 2.0},
    "DEFAULT":{"range": (1.15, 2.20), "warn_thresh": 2.2}
}

# --- 2. BỘ HÀM BỔ TRỢ HÌNH HỌC PHẲNG ---
def safe_float(val, default=0.0) -> float:
    if val is None: return default
    val_clean = str(val).replace("%", "").replace('"', '').strip().lower()
    if val_clean in ["null", "none", "unknown", "na", "n/a", ""]: return default
    try: return float(val_clean)
    except (ValueError, TypeError): return default

def calculate_cad_area(length: float, width: float, cutable_w: float, row_eff: float) -> float:
    return ((length * width) / (cutable_w * 36.0)) / (row_eff / 100.0)

# --- 3. LÕI PYTHON DETERMINISTIC CAD CALCULATOR ---
def execute_deterministic_cad_calc(ai_blueprint: dict, user_chat: str) -> dict:
    """
    PYTHON DETECT & MATH ENGINE: 
    Nhận dữ liệu Blueprint thô từ Gemini. Tự động map loại nguyên liệu, 
    tự tính hình học phẳng và tự thực thi cộng dồn lũy tiến.
    """
    # Khai thác ép thông số từ ô chat của User (Ưu tiên số 1)
    w_chat, s_l_chat, s_w_chat = None, None, None
    chat_clean = str(user_chat).lower().strip()
    match_w = re.search(r'(?:khổ|kho)\s*(\d+)', chat_clean)
    if match_w: w_chat = float(match_w.group(1))
    match_range = re.search(r'(?:co\s*rút|co\s*rut|co)\s*(\d+)\s*(?:-|–|ngang|\s+)\s*(\d+)', chat_clean)
    if match_range: 
        s_l_chat = float(match_range.group(1))
        s_w_chat = float(match_range.group(2))

    # Đọc Spec thô do AI bóc tách từ PDF
    product_type = ai_blueprint.get("detected_product_type", "DEFAULT")
    body_length = safe_float(ai_blueprint.get("extracted_body_length"), 28.0)
    sleeve_length = safe_float(ai_blueprint.get("extracted_sleeve_length"), 24.0)
    chest_width = safe_float(ai_blueprint.get("extracted_chest_width"), 20.0)
    
    # Đồng bộ thông số Quần ngố Capri phẳng thực tế của xưởng
    outseam_length = safe_float(ai_blueprint.get("extracted_outseam_length"), 30.5 if product_type in ["PANT", "DEFAULT"] else 40.0)
    hip_width = safe_float(ai_blueprint.get("extracted_hip_width"), 21.0)
    skirt_hem = safe_float(ai_blueprint.get("extracted_skirt_hem_width"), 35.0)

    # Tính diện tích rập thân lớn hình học phẳng cơ sở (Square Inches)
    if product_type == "JACKET": base_area_sq_in = ((body_length * 2) + sleeve_length + 4.0) * ((chest_width * 2) + 5.0)
    elif product_type == "PANT": base_area_sq_in = (outseam_length + 3.0) * ((hip_width * 2) + 5.5)
    elif product_type == "JORT": base_area_sq_in = (outseam_length + 4.0) * ((hip_width * 2) + 16.0)
    elif product_type == "DRESS": base_area_sq_in = (body_length + 6.0) * ((skirt_hem * 2) + 4.0)
    elif product_type == "TSHIRT": base_area_sq_in = ((body_length * 2) + 3.0) * ((chest_width * 2) + 3.0)
    elif product_type == "SHIRT": base_area_sq_in = ((body_length * 2) + sleeve_length + 3.5) * ((chest_width * 2) + 4.5)
    else: base_area_sq_in = 30.0 * 50.0

    processed_bom_rows = []
    accumulated_self_consumption = 0.0  # Cộng dồn tích lũy chi tiết phối (SELF) vào vải chính
    main_fabric_row_index = None

    for idx, row in enumerate(ai_blueprint.get("bom_rows", [])):
        material_classification = row.get("material_classification", "BYPASS")
        
        # Đồng bộ cấu hình vải vật lý phẳng
        w_bom = w_chat if w_chat is not None else safe_float(row.get("fabric_width_inch"), 56.0)
        s_l = s_l_chat if s_l_chat is not None else safe_float(row.get("shrinkage_warp_pct"), 5.0)
        s_w = s_w_chat if s_w_chat is not None else safe_float(row.get("shrinkage_weft_pct"), 10.0)
        
        # Mặc định hiệu suất rập chặt 88% cho phom Jeans/Denim của xưởng Phong Phú
        eff = max(80.0, min(safe_float(row.get("marker_efficiency_pct"), 88.0), 95.0))
        
        cutable_w = max(40.0, w_bom - 1.5)
        shrink_warp_f, shrink_weft_f = 1.0 + (s_l / 100.0), 1.0 + (s_w / 100.0)
        wastage_f = 1.03 # 3% hao hụt bàn cắt

        final_yds = 0.0
        log_txt = f"Method: {material_classification}"
        row_status = "PASS"

        # ĐA PHÂN TÁCH: Thực thi toán học phẳng hoàn toàn dựa trên lệnh kiểm soát của Python
        if material_classification == "MAIN_FABRIC":
            base_cons = (base_area_sq_in / (cutable_w * 36.0)) / (eff / 100.0)
            raw_total = base_cons * shrink_warp_f * shrink_weft_f * wastage_f
            
            # Kiểm soát giới hạn (Clamp) và Warning rủi ro
            eval_type = "PANT" if product_type == "DEFAULT" else product_type
            cfg = LIMITS.get(eval_type, LIMITS["PANT"])
            
            if raw_total > cfg["warn_thresh"]: row_status = "WARNING"
            if raw_total > 3.3: row_status = "CRITICAL"
            
            low, high = cfg["range"]
            final_gross_yards = round(max(low, min(raw_total, high)), 2)
            final_yds = final_gross_yards
            log_txt = f"{int(w_bom)}\"/{int(eff)}%/{int(s_l)}x{int(s_w)} | Diện tích thân chính"
            if main_fabric_row_index is None: main_fabric_row_index = idx

        elif material_classification == "SELF_POCKET":
            # Chi tiết rập túi nhỏ cắt từ vải chính
            piece_count = safe_float(row.get("piece_count"), 2.0)
            piece_len = safe_float(row.get("piece_length_inch"), 12.0)
            piece_wid = safe_float(row.get("piece_width_inch"), 10.0)
            
            pocket_area = piece_len * piece_wid * piece_count
            calculated_pocket_yds = (pocket_area / (cutable_w * 36.0)) / (eff / 100.0) * shrink_warp_f * shrink_weft_f * wastage_f
            calculated_pocket_yds = min(calculated_pocket_yds, 0.15) # Khóa trần túi phụ phối
            
            accumulated_self_consumption += calculated_pocket_yds
            final_yds = 0.0
            log_txt = f"Included in Main Fabric (Túi SELF rập phụ)"
            row["notes_display"] = "Included in Main Fabric"

        elif material_classification == "SELF_DRAWSTRING":
            # Dây rút/Dây luồn cắt từ vải chính
            piece_len = safe_float(row.get("piece_length_inch"), 43.0)
            piece_wid = safe_float(row.get("piece_width_inch"), 0.375)
            
            trim_area = piece_len * piece_wid * 1.0
            calculated_trim_yds = (trim_area / (cutable_w * 36.0)) / (eff / 100.0) * shrink_warp_f * wastage_f
            calculated_trim_yds = min(calculated_trim_yds, 0.08)
            
            accumulated_self_consumption += calculated_trim_yds
            final_yds = 0.0
            log_txt = f"Included in Main Fabric (Dây rút SELF)"
            row["notes_display"] = "Included in Main Fabric"

        elif material_classification == "POCKETING_FABRIC":
            final_yds = 0.15 if product_type == "JORT" else 0.25
            log_txt = "Vải lót túi lót chuyên dụng độc lập"
            
        elif material_classification == "INTERLINING_FUSING":
            final_yds = 0.10
            log_txt = "Diện tích dựng mếch keo phối chi tiết lưng"
            
        else:
            final_yds = 0.0
            log_txt = "Bỏ qua toán học phẳng (Hardware Trim)"

        row["calculated_gross_consumption_yds"] = final_yds
        row["reason_or_logs"] = log_txt
        row["status"] = row_status
        row["marker_efficiency_pct"] = f"{int(eff)}%" if material_classification in ["MAIN_FABRIC", "SELF_POCKET", "SELF_DRAWSTRING"] else "N/A"
        processed_bom_rows.append(row)

    # THỰC THI CỘNG DỒN LUỸ TIẾN CUỐI CÙNG VÀO DÒNG VẢI THÂN CHÍNH
    if main_fabric_row_index is not None and accumulated_self_consumption > 0:
        main_row = processed_bom_rows[main_fabric_row_index]
        main_row["calculated_gross_consumption_yds"] = round(main_row["calculated_gross_consumption_yds"] + accumulated_self_consumption, 2)
        main_row["reason_or_logs"] += f" [Cộng dồn rập chi tiết phối +{round(accumulated_self_consumption, 2)}yds]"

    ai_blueprint["bom_rows"] = processed_bom_rows
    return ai_blueprint
# =====================================================================
# CẤU HÌNH GIAO DIỆN VÀ NÚT ĐIỀU KHIỂN SIDEBAR CHỐNG KẸT LOOP
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
uploaded_file = st.file_uploader("Kéo và thả file PDF Techpack vào đây", type=["pdf"])
if uploaded_file is not None:
    st.session_state.pdf_bytes = uploaded_file.read()
    st.session_state.pdf_name = uploaded_file.name

chat_container = st.container(height=150)
with chat_container:
    for chat in st.session_state.get("chat_history", []):
        with st.chat_message(chat["role"]): st.markdown(chat["content"])

user_prompt = st.chat_input("Nhập thông số cấu hình...")

# Nút bấm thủ công kiểm soát luồng Quota API Google an toàn tuyệt đối
trigger_calc = st.button("🚀 KÍCH HOẠT AI BÓC TÁCH CẤU TRÚC RẬP", use_container_width=True, type="primary")

if (trigger_calc and "pdf_bytes" in st.session_state) or (user_prompt and "pdf_bytes" in st.session_state):
    current_prompt = user_prompt if user_prompt else "Hãy tự động bóc tách và phân loại bảng dữ liệu rập cho file này."
    if user_prompt: st.session_state.chat_history.append({"role": "user", "content": user_prompt})
    
    # SCHEMA PHẲNG TRÍCH XUẤT THÔNG SỐ ĐẦU VÀO CHO PYTHON
    json_schema = {
        "type": "OBJECT",
        "properties": {
            "style_code": {"type": "STRING"},
            "detected_product_type": {"type": "STRING", "enum": ["JACKET", "PANT", "JORT", "DRESS", "TSHIRT", "SHIRT", "DEFAULT"]},
            "extracted_body_length": {"type": "STRING"}, "extracted_sleeve_length": {"type": "STRING"}, "extracted_chest_width": {"type": "STRING"},
            "extracted_outseam_length": {"type": "STRING"}, "extracted_hip_width": {"type": "STRING"}, "extracted_skirt_hem_width": {"type": "STRING"},
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

    # BỘ LỆNH CẤM AI LÀM TOÁN - CHỈ ĐƯỢC PHÉP PHÂN LOẠI NGỮ CẢNH TRÍCH DỮ LIỆU
    ocr_master_prompt = f"""
    Bạn là Senior Garment Data Engineer chuyên bóc tách hồ sơ PLM/CAD rập phẳng.
    Nhiệm vụ của bạn: Đọc file PDF Techpack, trích xuất dữ liệu thô và phân loại cấu trúc rập của từng dòng BOM.
    
    ⚠️ QUY TẮC CỐT LÕI: TUYỆT ĐỐI KHÔNG ĐƯỢC TỰ TÍNH TOÁN HOẶC ĐƯA RA CON SỐ ĐỊNH MỨC YARDS CUỐI CÙNG [INDEX]. 
    
    HƯỚNG DẪN TRÍCH XUẤT VÀ PHÂN LOẠI (BLUEPRINT MATRIX):
    1. ĐỌC BẢNG POM: Tìm thông số Spec nền hình học thô (Length, Chest, Outseam...) của Base Size điền vào các trường tương ứng ngoài Schema.
    2. NHẬN DIỆN PHOM DÁNG: Tự phân biệt kiểu đồ (Quần ngố Cargo/Capri/Denim ghi nhận là 'PANT'; áo khoác là 'JACKET').
    3. PHÂN LOẠI DÒNG BOM (material_classification):
       - Nếu dòng đó là vải thân chính lớn (Main Fabric, Shell, Outer, Denim): Gán 'MAIN_FABRIC'.
       - Nếu dòng đó là túi nhỏ ghi cắt từ vải chính hoặc vải SELF (SELF + POCKET/POCKETING): Gán 'SELF_POCKET'. Tìm kích thước rập túi thô (Ví dụ: 12x10 inch) trong tài liệu để điền vào piece_length_inch/piece_width_inch.
       - Nếu dòng đó là dây rút/dây luồn lưng cắt từ vải chính (SELF + DRAWSTRING): Gán 'SELF_DRAWSTRING'. Tìm độ dài dây (Ví dụ: 3/8" Width, Length 110cm) đổi sang Inch điền vào piece_length_inch/piece_width_inch.
       - Nếu dòng đó là vải lót túi độc lập (TC Pocketing Fabric): Gán 'POCKETING_FABRIC'.
       - Nếu dòng đó là mếch, keo, dựng, lót ép phom (Interlining, Fusing, Lining, Mex): Gán 'INTERLINING_FUSING'.
       - Nếu là phụ liệu kim loại đếm chiếc (Chỉ Thread, Nút Button, Đinh tán): Gán 'HARDWARE_TRIM'.
       
    Yêu cầu bổ sung: {current_prompt}
    """

    with st.spinner("AI đang thực thi OCR bóc tách và phân rã cấu trúc rập chi tiết..."):
        try:
            pdf_blob = {"mime_type": "application/pdf", "data": st.session_state.pdf_bytes}
            model = genai.GenerativeModel('gemini-2.5-flash')
            response = model.generate_content([pdf_blob, ocr_master_prompt], generation_config=types.GenerationConfig(response_mime_type="application/json", response_schema=json_schema, temperature=0.1))
            ai_blueprint = json.loads(response.text.strip())
            
            # CHUYỂN GIAO TOÀN BỘ DỮ LIỆU ĐỂ PYTHON ENGINE LÀM TOÁN XÁC ĐỊNH
            st.session_state.bom_data = execute_deterministic_cad_calc(ai_blueprint, user_prompt)
            st.session_state.chat_history.append({"role": "assistant", "content": "🤖 Thành công: AI đã bóc tách Spec rập phẳng, Python Rule Engine đã thực thi toán học xác định định mức ổn định 100%."})
        except Exception as e:
            st.session_state.chat_history.append({"role": "assistant", "content": f"❌ Lỗi giới hạn gọi hàm Google (Quota): {str(e)}. Hãy đợi 1 phút rồi bấm lại nút🚀."})
    st.rerun()

# HIỂN THỊ BẢNG SẢN XUẤT PHẲNG ỔN ĐỊNH
if st.session_state.get("bom_data"):
    st.markdown(f"### 📋 BẢNG ĐỊNH MỨC PLM DETECT ENGINE (Phom dáng rập: `{st.session_state.bom_data.get('detected_product_type')}` )")
    flat_rows = []
    for r in st.session_state.bom_data["bom_rows"]:
        display_yds = r.get("calculated_gross_consumption_yds")
        if r.get("notes_display") == "Included in Main Fabric": display_yds = "Included in Main"
        
        flat_rows.append({
            "Giám Sát PLM": "🟢 PASS" if r.get("status") == "PASS" else ("🟡 WARNING" if r.get("status") == "WARNING" else "🔴 CRITICAL"),
            "Nguyên phụ liệu": r.get("component_type"), "Vị trí sử dụng": r.get("placement"),
            "Hiệu suất sơ đồ": r.get("marker_efficiency_pct"), "Định mức Gross (Yds/Pc)": display_yds,
            "Nhật ký Telemetry / Phân tích số học": r.get("reason_or_logs")
        })
    st.dataframe(pd.DataFrame(flat_rows), use_container_width=True)
