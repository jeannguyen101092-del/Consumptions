import streamlit as st
import pandas as pd
import json
import re
import google.generativeai as genai
from google.generativeai import types

# =====================================================================
# ĐOẠN 1: GLOBAL CONFIG REGISTRY & LÕI MÔ PHỎNG SƠ ĐỒ THƯƠNG MẠI (V14.1)
# =====================================================================

# KHỐI CỦA BẢNG CẤU HÌNH BIÊN ĐỘ GIỚI HẠN TẬP TRUNG KIỂM SOÁT CHẤT LƯỢNG PLM
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

# CHUẨN HÓA TỪ KHÓA - LOẠI BỎ CÁC TỪ DỄ TRÙNG CHUỖI NHƯ "FABRIC", "COTTON", "DENIM"
MAIN_KEYS = ("MAIN FABRIC", "MAIN", "BODY", "SHELL", "SELF FABRIC", "SELFFABRIC", "SELF-FABRIC", "FACE", "OUTER", "PRIMARY")
THREAD_KEYS = ("CHỈ", "THREAD", "ZIPPER", "DÂY KÉO", "BUTTON", "NÚT", "SHANK", "RIVET", "LABEL", "MÁC", "TAG", "EYELETS", "SNAP", "VELCRO", "HOOK", "LOOP", "STOPPER", "TOGGLE", "BUCKLE", "GROMMET")
POCKET_KEYS = ("POCKETING", "POCKET BAG", "POCKET", "TÚI", "TC POCKETING")
FUSING_KEYS = ("INTERLINING", "FUSING", "MEX", "MECK", "KEO", "DỰNG") # Đã tách biệt hoàn toàn LINING độc lập
DRAWSTRING_KEYS = ("DRAWSTRING", "DRAW CORD", "DRAWCORD", "DÂY RÚT", "DÂY LUỒN")

def safe_float(val, default=0.0) -> float:
    if val is None: return default
    val_clean = str(val).replace("%", "").replace('"', '').strip().lower()
    if val_clean in ["null", "none", "unknown", "na", "n/a", ""]: return default
    try: return float(val_clean)
    except (ValueError, TypeError): return default

def normalize_fabric_class(raw_class: str) -> str:
    """Chuẩn hóa dữ liệu đầu vào của Gemini về đúng 6 nhóm nguyên vật liệu tối cao [INDEX]"""
    c_upper = str(raw_class).upper().strip()
    if any(k in c_upper for k in ["MAIN", "SHELL", "BODY", "SELF FABRIC"]): return "MAIN_FABRIC"
    if any(k in c_upper for k in ["POCKETING", "POCKET"]): return "POCKETING"
    if any(k in c_upper for k in ["INTERLINING", "FUSING", "MEX", "MECK", "KEO", "DỰNG"]): return "FUSING"
    if any(k in c_upper for k in ["LINING", "LÓT", "MESH", "TAFFETA"]): return "LINING"
    if c_upper.startswith("SELF_") or "COMPONENT" in c_upper: return "SELF_COMPONENT"
    return "TRIM"

def calculate_shoelace_polygon_area(points: list) -> float:
    """True Polygon CAD Core: Tính toán diện tích đa giác khép kín bằng công thức Shoelace [INDEX]"""
    if not points or len(points) < 3: return 0.0
    try:
        n = len(points)
        area = 0.0
        for i in range(n):
            j = (i + 1) % n
            p1, p2 = points[i], points[j]
            x1 = float(p1 if isinstance(p1, (list, tuple)) else p1.get("x", 0.0))
            y1 = float(p1 if isinstance(p1, (list, tuple)) else p1.get("y", 0.0))
            x2 = float(p2 if isinstance(p2, (list, tuple)) else p2.get("x", 0.0))
            y2 = float(p2 if isinstance(p2, (list, tuple)) else p2.get("y", 0.0))
            area += (x1 * y2) - (x2 * y1)
        return abs(area) / 2.0
    except Exception: return 0.0

def simulate_marker_efficiency_v14(panels: list, fabric_class: str, grain_rule: str, width: float, fabric_repeat_inch: float = 0.0) -> float:
    """Marker Nesting Simulator: Áp phạt penalty cho cấu kiện vải một chiều, sọc kẻ, và cặp đối xứng [INDEX]"""
    base_efficiency = 89.0
    panel_count = len(panels) if panels else 4
    if grain_rule == "ONE_WAY" or fabric_class in ["VELVET", "NHUNG", "TUYẾT"]: base_efficiency -= 4.0
    elif grain_rule in ["STRIPE_MATCH", "GRID_MATCH"] or fabric_repeat_inch > 0: base_efficiency -= 6.5
    if panel_count > 12: base_efficiency += 2.0
    elif panel_count < 5: base_efficiency -= 3.5
    if width < 45.0: base_efficiency -= 3.0
    return max(60.0, min(base_efficiency, 94.0))

def detect_product_type(desc_upper: str, raw_inseam_val: float) -> str:
    """Quy trình nhận diện thứ tự phân tầng ưu tiên: CARGO -> CAPRI -> JORT -> PANT [INDEX]"""
    if any(x in desc_upper for x in ["JACKET", "COAT", "VEST", "OUTERWEAR"]): return "JACKET"
    elif any(x in desc_upper for x in ["JEAN", "DENIM", "PANT", "PANTS", "BAGGY", "TROUSER", "LEGGING", "JORT", "CAPRI", "CARGO"]):
        if any(k in desc_upper for k in ["CARGO", "UTILITY", "CARPENTER", "DOUBLE KNEE"]): return "CARGO_PANT"
        if any(k in desc_upper for k in ["CAPRI", "CROP PANT", "CROPPED", "CROP", "ANKLE PANT"]): return "CAPRI_PANT"
        return "JORT" if raw_inseam_val < 15.0 else "PANT"
    elif any(x in desc_upper for x in ["DRESS", "SKIRT", "VÁY", "ĐẦM", "MAXI"]): return "DRESS"
    elif any(x in desc_upper for x in ["TSHIRT", "T-SHIRT", "TEE", "POLO", "ÁO THUN"]): return "TSHIRT"
    elif any(x in desc_upper for x in ["SHIRT", "SƠ MI", "BLOUSE", "BUTTON DOWN"]): return "SHIRT"
    return "DEFAULT"

# =====================================================================
# ĐOẠN 2a: PYTHON CAD ENGINE - PHÂN RÃ HÌNH HỌC ĐA GIÁC CHI TIẾT
# =====================================================================

def execute_cad_polygon_consumption(ai_blueprint: dict, user_chat: str) -> dict:
    processed_bom_blueprint = []
    fabric_registry = {}
    accumulated_self_consumption_map = {} 

    w_chat, s_l_chat, s_w_chat = None, None, None
    chat_clean = str(user_chat).lower().strip()
    match_w = re.search(r'(?:khổ|kho)\s*(\d+)', chat_clean)
    if match_w: w_chat = float(match_w.group(1))
    match_range = re.search(r'(?:co\s*rút|co\s*rut|co)\s*(\d+)\s*(?:-|–|ngang|\s+)\s*(\d+)', chat_clean)
    if match_range: 
        s_l_chat = float(match_range.group(1))
        s_w_chat = float(match_range.group(2))

    product_type = ai_blueprint.get("detected_product_type", "DEFAULT")
    body_length = safe_float(ai_blueprint.get("extracted_body_length"), 28.0)
    sleeve_length = safe_float(ai_blueprint.get("extracted_sleeve_length"), 24.0)
    chest_width = safe_float(ai_blueprint.get("extracted_chest_width"), 20.0)
    outseam_length = safe_float(ai_blueprint.get("extracted_outseam_length"), 30.5 if product_type == "CAPRI_PANT" else 40.0)
    hip_width = safe_float(ai_blueprint.get("extracted_hip_width"), 21.0)
    skirt_hem = safe_float(ai_blueprint.get("extracted_skirt_hem_width"), 35.0)

    if product_type == "JACKET": fallback_base_area = ((body_length * 2) + sleeve_length + 4.0) * ((chest_width * 2) + 5.0)
    elif product_type in ["PANT", "CAPRI_PANT", "CARGO_PANT"]: fallback_base_area = (outseam_length + 4.0) * ((hip_width * 2) + 12.0)
    elif product_type == "JORT": fallback_base_area = (outseam_length + 4.0) * ((hip_width * 2) + 16.0)
    else: fallback_base_area = 30.0 * 50.0

    all_rows = ai_blueprint.get("bom_rows", [])
    
    # Đăng ký trước tất cả các mã khóa sơ bộ của vải chính để bảo vệ target SELF
    for row in all_rows:
        f_class_raw = row.get("fabric_classification", "MAIN_FABRIC")
        f_class_norm = normalize_fabric_class(f_class_raw)
        f_code = str(row.get("fabric_code", "MAIN")).upper().strip().replace(" ", "_")
        f_color = str(row.get("fabric_color", "COLOR")).upper().strip().replace(" ", "_")
        grain_rule = row.get("fabric_grain_rule", "TWO_WAY")
        fab_repeat = safe_float(row.get("fabric_repeat_inch"), 0.0)
        
        tmp_id = f"{f_code}_{f_color}_{grain_rule}_{int(fab_repeat)}"
        w_b = w_chat if w_chat is not None else safe_float(row.get("fabric_width_inch"), 56.0)
        s_warp = s_l_chat if s_l_chat is not None else safe_float(row.get("shrinkage_warp_pct"), 5.0)
        s_weft = s_l_chat if s_l_chat is not None else safe_float(row.get("shrinkage_weft_pct"), 10.0)
        
        if f_class_norm == "MAIN_FABRIC" and tmp_id not in fabric_registry:
            fabric_registry[tmp_id] = {
                "accumulated_area_sq_in": 0.0, "cutable_w": max(40.0, w_b - 1.5), 
                "eff": simulate_marker_efficiency_v14(row.get("panels_catalog", []), f_class_norm, grain_rule, w_b, fab_repeat),
                "shrink_warp_f": 1.0 + (s_warp / 100.0), "shrink_weft_f": 1.0 + (s_weft / 100.0), "wastage_f": 1.03,
                "rows_to_update": [], "w_saved": w_b, "s_l_saved": s_warp, "s_w_saved": s_weft, "f_class": f_class_norm
            }

    for row in all_rows:
        c_type = str(row.get("component_type", "")).upper()
        placement = str(row.get("placement", "")).upper()
        body_type = str(row.get("body_type", "")).upper()
        
        if any(k in c_type or k in placement or k in body_type for k in THREAD_KEYS):
            row["calculated_gross_consumption_yds"] = 0.0
            row["reason_or_logs"] = "Hardware Trim Bypass"
            row["status"] = "PASS"
            row["marker_efficiency_pct"] = "N/A"
            row["consumption_note"] = "Bypass"
            processed_bom_blueprint.append(row)
            continue

        f_class_raw = row.get("fabric_classification", "MAIN_FABRIC")
        f_class = normalize_fabric_class(f_class_raw)
        
        f_code = str(row.get("fabric_code", "MAIN")).upper().strip().replace(" ", "_")
        f_color = str(row.get("fabric_color", "COLOR")).upper().strip().replace(" ", "_")
        grain_rule = row.get("fabric_grain_rule", "TWO_WAY")
        fab_repeat = safe_float(row.get("fabric_repeat_inch"), 0.0)
        
        fabric_id = f"{f_code}_{f_color}_{grain_rule}_{int(fab_repeat)}"
        consume_target_id = str(row.get("consume_to_fabric_id", "")).upper().strip().replace(" ", "_")

        w_bom = w_chat if w_chat is not None else safe_float(row.get("fabric_width_inch"), 56.0)
        s_l = s_l_chat if s_l_chat is not None else safe_float(row.get("shrinkage_warp_pct"), 5.0)
        s_w = s_w_chat if s_w_chat is not None else safe_float(row.get("shrinkage_weft_pct"), 10.0)
        
        panels = row.get("panels_catalog", [])
        eff = simulate_marker_efficiency_v14(panels, f_class, grain_rule, w_bom, fab_repeat)
        
        cutable_w = max(40.0, w_bom - 1.5)
        shrink_warp_f, shrink_weft_f = 1.0 + (s_l / 100.0), 1.0 + (s_w / 100.0)
        wastage_f = 1.03

        if fabric_id not in fabric_registry:
            fabric_registry[fabric_id] = {
                "accumulated_area_sq_in": 0.0, "cutable_w": cutable_w, "eff": eff,
                "shrink_warp_f": shrink_warp_f, "shrink_weft_f": shrink_weft_f, "wastage_f": wastage_f,
                "rows_to_update": [], "w_saved": w_bom, "s_l_saved": s_l, "s_w_saved": s_w, "f_class": f_class
            }
        if fabric_id not in accumulated_self_consumption_map:
            accumulated_self_consumption_map[fabric_id] = 0.0

        row_area_sq_in = 0.0
        is_main_shell = (f_class == "MAIN_FABRIC")
        
        if panels:
            for panel in panels:
                p_count = safe_float(panel.get("piece_count"), 1.0)
                polygon_points = panel.get("polygon_points", [])
                
                scale_factor = safe_float(panel.get("coordinate_scale"), 1.0)
                scale_factor = max(0.001, min(scale_factor, 100.0))
                
                if polygon_points and isinstance(polygon_points, list) and len(polygon_points) >= 3:
                    panel_area = calculate_shoelace_polygon_area(polygon_points) * p_count
                    panel_area *= (scale_factor ** 2) 
                else:
                    p_len = safe_float(panel.get("piece_length_inch"), 0.0)
                    p_wid = safe_float(panel.get("piece_width_inch"), 0.0)
                    s_factor = safe_float(panel.get("shape_factor"), 0.88)
                    panel_area = p_len * p_wid * p_count * s_factor
                row_area_sq_in += panel_area
        else:
            row_area_sq_in = fallback_base_area if is_main_shell else 150.0

        if is_main_shell and not panels: row_area_sq_in = fallback_base_area

        if f_class.startswith("SELF_") or consume_target_id != "":
            sub_cons = (row_area_sq_in / (cutable_w * 36.0)) / (eff / 100.0)
            sub_yds = sub_cons * shrink_warp_f * shrink_weft_f * wastage_f
            
            final_target = consume_target_id if consume_target_id else fabric_id.replace("SELF_", "MAIN_FABRIC_")
            
            if final_target not in accumulated_self_consumption_map:
                accumulated_self_consumption_map[final_target] = 0.0
            accumulated_self_consumption_map[final_target] += sub_yds
            
            row["calculated_gross_consumption_yds"] = 0.0
            row["consumption_note"] = f"Included in {final_target}"
            row["reason_or_logs"] = f"Mảnh phối rập SELF [Diện tích: {round(row_area_sq_in,1)} sq_in] -> Đã kết chuyển thô +{round(sub_yds, 2)}yds"
        else:
            fabric_registry[fabric_id]["accumulated_area_sq_in"] += row_area_sq_in
            row["calculated_gross_consumption_yds"] = 0.0
            row["consumption_note"] = "Calculated"
            row["reason_or_logs"] = f"Mảnh rập chính [Diện tích: {round(row_area_sq_in, 1)} sq_in]"
            
        row["status"] = "PASS"
        row["marker_efficiency_pct"] = f"{int(eff)}%" if f_class != "FUSING" else "N/A"
        fabric_registry[fabric_id]["rows_to_update"].append(row)
        processed_bom_blueprint.append(row)
# =====================================================================
# ĐOẠN 2b: PHÂN BỔ ĐỊNH MỨC THEO FABRIC ID & KIỂM SOÁT THỰC TẾ (V14.1)
# =====================================================================

    for f_id, data in fabric_registry.items():
        if data["f_class"] != "MAIN_FABRIC":
            # Gán thông số mếch keo lót độc lập không chạy dồn thân chính
            for r in data["rows_to_update"]:
                if r["consumption_note"] == "Calculated":
                    f_yds = 0.10 if product_type in ["PANT", "JORT", "CAPRI_PANT", "CARGO_PANT"] else 0.65
                    r["calculated_gross_consumption_yds"] = f_yds
            continue
            
        total_area = data["accumulated_area_sq_in"]
        base_cons = (total_area / (data["cutable_w"] * 36.0)) / (data["eff"] / 100.0)
        final_raw_yds = base_cons * data["shrink_warp_f"] * data["shrink_weft_f"] * data["wastage_f"]
        
        self_add = accumulated_self_consumption_map.get(f_id, 0.0)
        total_yds_with_self = round(final_raw_yds + self_add, 2)

        row_status = "PASS"
        cfg = LIMITS.get(product_type, LIMITS["DEFAULT"])
        high_ceiling = cfg["range"][1] # Lấy trần tối đa chặn rủi ro dữ liệu đầu vào [INDEX]
        
        # CHÈN BỘ KIỂM SOÁT IE CHẤT LƯỢNG - GIỮ NGUYÊN SỐ THỰC THÔ KHÔNG CLAMP [INDEX]
        if total_yds_with_self > high_ceiling:
            row_status = "CRITICAL"
            exceed_val = round(total_yds_with_self - high_ceiling, 2)
            log_output = f"{int(data['w_saved'])}\"/{int(data['eff'])}%/{int(data['s_l_saved'])}x{int(data['s_w_saved'])} | Diện tích rập {f_id}: {round(total_area,1)} sq_in. 🔴 VƯỢT TRẦN TIÊU CHUẨN (+{exceed_val} yds)" [INDEX]
        elif total_yds_with_self > cfg["warn_thresh"]:
            row_status = "WARNING"
            log_output = f"{int(data['w_saved'])}\"/{int(data['eff'])}%/{int(data['s_l_saved'])}x{int(data['s_w_saved'])} | Diện tích rập {f_id}: {round(total_area,1)} sq_in. 🟡 CẢNH BÁO PLM"
        else:
            log_output = f"{int(data['w_saved'])}\"/{int(data['eff'])}%/{int(data['s_l_saved'])}x{int(data['s_w_saved'])} | Diện tích rập {f_id}: {round(total_area,1)} sq_in. 🟢 ĐẠT TIÊU CHUẨN MAY"

        rows = data["rows_to_update"]
        if rows:
            # FIX DỨT ĐIỂM TYPEERROR: Trỏ đích danh dòng đầu tiên của nhóm vải Fabric ID nhận tổng số Yards [INDEX]
            main_row = rows[0] [INDEX]
            main_row["calculated_gross_consumption_yds"] = total_yds_with_self [INDEX]
            main_row["status"] = row_status
            main_row["consumption_note"] = "Final Real Gross"
            main_row["reason_or_logs"] = log_output

    ai_blueprint["bom_rows"] = processed_bom_blueprint
    return ai_blueprint


# =====================================================================
# ĐOẠN 3: AI BLUEGRAPH OBJECT PARSER VÀ RENDERING GIAO DIỆN PHẲNG V12
# =====================================================================

# KHỞI TẠO BỘ NHỚ STATE CHỐNG SẬP ỨNG DỤNG KHÔNG ĐÁNG CÓ
if "bom_data" not in st.session_state: st.session_state.bom_data = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = [{"role": "assistant", "content": "Hệ thống CAD V12 đã sẵn sàng. Tải tệp PDF lên để AI phân rã đa giác rập chi tiết phẳng."}]

with st.sidebar:
    st.header("⚙️ HỆ THỐNG")
    if st.button("🗑️ Xóa lịch sử & Reset định mức", use_container_width=True):
        st.session_state.bom_data = None
        st.session_state.pdf_bytes = None
        st.session_state.pdf_name = None
        st.session_state.chat_history = [{"role": "assistant", "content": "Hệ thống đã reset sạch cache. Vui lòng tải file PDF mới."}]
        st.rerun()

st.subheader("📁 BƯỚC 1: TẢI BIỂU MẪU SẢN XUẤT TECHPACK PDF")
uploaded_file = st.file_uploader("Kéo và thả file PDF Techpack vào đây", type=["pdf"], key="final_v12_uploader")
if uploaded_file is not None:
    st.session_state.pdf_bytes = uploaded_file.read()
    st.session_state.pdf_name = uploaded_file.name

chat_container = st.container(height=150)
with chat_container:
    for chat in st.session_state.get("chat_history", []):
        with st.chat_message(chat["role"]): st.markdown(chat["content"])

user_prompt = st.chat_input("Nhập thông số cấu hình...")
trigger_calc = st.button("🚀 KÍCH HOẠT AI PHÂN RÃ CHI TIẾT RẬP VÀ MÔ PHỎNG", use_container_width=True, type="primary")

if (trigger_calc and "pdf_bytes" in st.session_state) or (user_prompt and "pdf_bytes" in st.session_state):
    current_prompt = user_prompt if user_prompt else "Hãy tự động phân rã đa giác rập chi tiết cho file này."
    if user_prompt: st.session_state.chat_history.append({"role": "user", "content": user_prompt})
    
    # SYSTEM JSON SCHEMA MÔ PHỎNG PHẦN MỀM CAD LECTRA/GERBER TIÊU CHUẨN
    json_schema = {
        "type": "OBJECT",
        "properties": {
            "style_code": {"type": "STRING"},
            "detected_product_type": {"type": "STRING", "enum": ["JACKET", "PANT", "CAPRI_PANT", "CARGO_PANT", "JORT", "DRESS", "TSHIRT", "SHIRT", "DEFAULT"]},
            "extracted_body_length": {"type": "STRING"}, "extracted_sleeve_length": {"type": "STRING"}, "extracted_chest_width": {"type": "STRING"},
            "extracted_outseam_length": {"type": "STRING"}, "extracted_hip_width": {"type": "STRING"}, "extracted_skirt_hem_width": {"type": "STRING"},
            "bom_rows": {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "component_type": {"type": "STRING"}, "placement": {"type": "STRING"}, "body_type": {"type": "STRING"},
                        "fabric_id": {"type": "STRING"}, # Mã nhóm định danh vải phẳng (V dụ: SHELL_A, LINING_B)
                        "fabric_classification": {"type": "STRING", "enum": ["MAIN_FABRIC", "CONTRAST_FABRIC", "LINING_FABRIC", "POCKETING_FABRIC", "INTERLINING_FUSING"]},
                        "fabric_grain_rule": {"type": "STRING", "enum": ["ONE_WAY", "TWO_WAY", "STRIPE_MATCH", "GRID_MATCH"]},
                        "fabric_width_inch": {"type": "STRING"}, "marker_efficiency_pct": {"type": "STRING"}, "shrinkage_warp_pct": {"type": "STRING"}, "shrinkage_weft_pct": {"type": "STRING"},
                        # KHỐI DANH MỤC MẢNH RẬP PHÂN RÃ HÌNH HỌC (PANEL CATALOG)
                        "panels_catalog": {
                            "type": "ARRAY",
                            "items": {
                                "type": "OBJECT",
                                "properties": {
                                    "panel_name": {"type": "STRING"},       # Tên mảnh rập thô (Ví dụ: Thân trước, Thân sau, Cổ áo)
                                    "piece_count": {"type": "STRING"},      # Số lượng cấu kiện rập chi tiết cho 1 sản phẩm
                                    "piece_length_inch": {"type": "STRING"},# Chiều dài bao rập thô của chi tiết
                                    "piece_width_inch": {"type": "STRING"}, # Chiều rộng bao rập thô của chi tiết
                                    "shape_factor": {"type": "STRING"}     # Hệ số rã hình đa giác phẳng (Ví dụ: 0.78 cho rập hình vát góc đũng)
                                },
                                "required": ["panel_name", "piece_count", "piece_length_inch", "piece_width_inch"]
                            }
                        }
                    },
                    "required": ["component_type", "placement", "fabric_id", "fabric_classification"]
                }
            }
        },
        "required": ["detected_product_type", "bom_rows"]
    }

    ocr_master_prompt = f"""
    Bạn là Senior CAD Pattern & Data Engineer chuyên số hóa rập và bóc tách hồ sơ PLM.
    Nhiệm vụ của bạn: Đọc file PDF Techpack kết hợp Sketch hình ảnh để lập Bản thiết kế đa giác rập chi tiết (Panel Catalog Blueprint).
    
    ⚠️ QUY TẮC CỐT LÕI: TUYỆT ĐỐI KHÔNG ĐƯỢC TỰ TÍNH TOÁN HOẶC ĐƯA RA CON SỐ ĐỊNH MỨC YARDS CUỐI CÙNG [INDEX].
    
    HƯỚNG DẪN TRÍCH XUẤT VÀ PHÂN RÃ CHI TIẾT RẬP:
    1. ĐỌC BẢNG POM: Trích xuất thông số Spec nền hình học thô (Length, Ngực, Mông, Outseam...) điền ngoài Schema. Nhận diện kiểu đồ để gán loại trang phục chuẩn xác.
    2. GOM NHÓM THEO FABRIC ID: Hãy đọc kỹ bảng BOM. Phân nhóm tất cả các dòng phụ liệu dùng chung một loại vải vào cùng 1 mã fabric_id (Ví dụ: Vải chính thân, túi cắt từ vải chính, dây luồn lưng cắt từ vải chính đều gán fabric_id='MAIN_FABRIC_SHELL').
    3. PHÂN RÃ MẢNH RẬP ẢO (panels_catalog): Nhìn vào Sketch và bản vẽ kết cấu để phân rã nguyên liệu đó thành danh mục các mảnh rập chi tiết cấu kiện (Ví dụ: Dòng Vải chính gồm Front Panel x2, Back Panel x2, Pocket Flap x2...; Dòng dây rút gồm Waist Drawstring x1). Tìm hoặc tự suy luận thông số dài/rộng/số lượng mảnh của từng miếng rập phụ thuộc vào bảng Spec POM để điền vào Schema. Nếu chi tiết rập vát hình thang, lượn đũng cong tốn vải thì áp shape_factor trong dải từ 0.75 - 0.90 tùy độ phức tạp của chi tiết rập phẳng.
    
    Yêu cầu bổ sung: {current_prompt}
    """

    with st.spinner("AI đang bóc tách kết cấu và phân rã mảnh rập cấu kiện..."):
        try:
            pdf_blob = {"mime_type": "application/pdf", "data": st.session_state.pdf_bytes}
            model = genai.GenerativeModel('gemini-2.5-flash')
            response = model.generate_content([pdf_blob, ocr_master_prompt], generation_config=types.GenerationConfig(response_mime_type="application/json", response_schema=json_schema, temperature=0.1))
            ai_blueprint = json.loads(response.text.strip())
            
            # Gửi mảng chi tiết rập ảo qua bộ xử lý số học toán CAD phẳng ở Đoạn 2
            st.session_state.bom_data = execute_cad_polygon_consumption(ai_blueprint, user_prompt)
            st.session_state.chat_history.append({"role": "assistant", "content": "🤖 Thành công V12: AI đã rã mảnh rập ảo dựa trên Sketch, Python Engine đã mô phỏng sơ đồ cắt phẳng dứt điểm ổn định."})
        except Exception as e:
            st.session_state.chat_history.append({"role": "assistant", "content": f"❌ Lỗi: {str(e)}. Hãy chờ 1 phút rồi nhấn chạy lại nút 🚀."})
    st.rerun()

# KHỐI HIỂN THỊ BẢNG ĐỊNH MỨC CAO CẤP V12 THƯƠNG MẠI
if st.session_state.get("bom_data"):
    st.markdown(f"### 📋 BẢNG ĐỊNH MỨC CAD COMPONENT ENGINE - PHOM RẬP: `{st.session_state.bom_data.get('detected_product_type')}`")
    flat_rows = []
    for r in st.session_state.bom_data["bom_rows"]:
        flat_rows.append({
            "Giám Sát PLM": "🟢 PASS" if r.get("status") == "PASS" else ("🟡 WARNING" if r.get("status") == "WARNING" else "🔴 CRITICAL"),
            "Nguyên phụ liệu": r.get("component_type"), 
            "Vị trí sử dụng": r.get("placement"),
            "Hiệu suất sơ đồ": r.get("marker_efficiency_pct"), 
            "Định mức Gross (Yds/Pc)": r.get("calculated_gross_consumption_yds"),
            "Nhật ký Telemetry / Bản thiết kế sơ đồ CAD": r.get("reason_or_logs")
        })
    st.dataframe(pd.DataFrame(flat_rows), use_container_width=True)
