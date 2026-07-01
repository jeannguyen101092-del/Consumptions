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
FUSING_KEYS = ("INTERLINING", "FUSING", "MEX", "MECK", "KEO", "DỰNG") 
DRAWSTRING_KEYS = ("DRAWSTRING", "DRAW CORD", "DRAWCORD", "DÂY RÚT", "DÂY LUỒN")

# HẰNG SỐ BẮT BUỘC LOẠI TRỪ KHÔNG TÍNH ĐỊNH MỨC (ÉP VỀ 0 YDS)
EXCLUDE_HARDWARE_KEYS = (
    "CHỈ", "THREAD", "ZIPPER", "DÂY KÉO", "BUTTON", "NÚT", "SHANK", "RIVET", 
    "LABEL", "MÁC", "TAG", "EYELETS", "SNAP", "VELCRO", "HOOK", "LOOP", 
    "STOPPER", "TOGGLE", "BUCKLE", "GROMMET", "STICKER", "CARE WHITE", 
    "HEAT STAMP", "HANGTAG", "POLYBAG", "BAO BÌ"
)

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

def parse_geometric_panels_allowance(ai_blueprint: dict, user_chat: str) -> dict:
    """
    Phân đoạn 2a1: Đọc dữ liệu thô, quét từ khóa thông minh
    để tính toán diện tích tịnh và cộng bù sai lệch hình học (Seam, Hem, Pleat).
    """
    product_type = str(ai_blueprint.get("detected_product_type", "DEFAULT")).upper().strip()
    
    body_length = safe_float(ai_blueprint.get("extracted_body_length"), 28.0)
    chest_width = safe_float(ai_blueprint.get("extracted_chest_width"), 20.0)
    outseam_length = safe_float(ai_blueprint.get("extracted_outseam_length"), 14.5 if product_type == "JORT" else 40.0)
    hip_width = safe_float(ai_blueprint.get("extracted_hip_width"), 21.0)

    FACTORY_SEAM_INCH = 0.5       
    FACTORY_HEM_INCH = 1.5        
    FACTORY_WAISTBAND_INCH = 2.5  
    FACTORY_PLEAT_INCH = 3.0      

    all_rows = ai_blueprint.get("bom_rows", [])
    parsed_rows = []

    for row in all_rows:
        c_type = str(row.get("component_type", "")).upper()
        placement = str(row.get("placement", "")).upper()
        body_type = str(row.get("body_type", "")).upper()
        
        if any(k in c_type or k in placement or k in body_type for k in THREAD_KEYS):
            row["calculated_gross_consumption_yds"] = 0.0
            row["reason_or_logs"] = "Hardware Trim Bypass"
            row["status"] = "PASS"
            row["consumption_note"] = "Bypass"
            parsed_rows.append(row)
            continue

        panels = row.get("panels_catalog", [])
        row_total_net_area_sq_in = 0.0
        panel_debug_logs = []

        if panels:
            for panel in panels:
                p_count = safe_float(panel.get("piece_count"), 1.0)
                polygon_points = panel.get("polygon_points", [])
                scale_factor = max(0.001, min(safe_float(panel.get("coordinate_scale"), 1.0), 100.0))
                
                if polygon_points and isinstance(polygon_points, list) and len(polygon_points) >= 3:
                    base_area = calculate_shoelace_polygon_area(polygon_points) * (scale_factor ** 2)
                else:
                    p_len = safe_float(panel.get("piece_length_inch"), 0.0)
                    p_wid = safe_float(panel.get("piece_width_inch"), 0.0)
                    base_area = p_len * p_wid * 0.88 if (p_len > 0 and p_wid > 0) else 0.0
                
                if base_area == 0.0:
                    eval_len_fb = outseam_length if product_type in ["PANT", "CARGO_PANT", "CAPRI_PANT", "JORT"] else body_length
                    eval_wid_fb = hip_width if product_type in ["PANT", "CARGO_PANT", "CAPRI_PANT", "JORT"] else chest_width
                    base_area = (eval_len_fb * eval_wid_fb * 0.25)
                
                net_panel_area = base_area * p_count
                polygon_include_seam = panel.get("include_seam", False) or str(panel.get("include_seam")).lower() == "true"
                polygon_include_hem = panel.get("include_hem", False) or str(panel.get("include_hem")).lower() == "true"
                
                p_name = str(panel.get("panel_name", "")).upper().strip()
                p_type_code = str(panel.get("panel_type", "")).upper().strip()
                has_seam = panel.get("seam_allowance", False) if str(panel.get("seam_allowance")).lower() == "false" else True

                hem_val = safe_float(panel.get("hem"), 0.0)
                if hem_val == 0.0 and not polygon_include_hem:
                    if any(k in p_name or k in p_type_code for k in ["LAI", "GAU", "HEM", "BOTTOM", "CUFF", "ONG_QUAN", "CHAN_VAY"]):
                        hem_val = 1.0

                pleat_val = safe_float(panel.get("pleat"), 0.0)
                if pleat_val == 0.0:
                    if any(k in p_name or k in p_type_code for k in ["PLEAT", "XEP_LY", "LY_HOP", "CARGO", "POCKET", "TUI_DAT", "TUI_HOP"]):
                        pleat_val = 1.0

                eval_len = safe_float(panel.get("piece_length_inch"), outseam_length if product_type in ["PANT", "CARGO_PANT", "CAPRI_PANT", "JORT"] else body_length)
                eval_wid = safe_float(panel.get("piece_width_inch"), hip_width if product_type in ["PANT", "CARGO_PANT", "CAPRI_PANT", "JORT"] else chest_width)

                if has_seam and not polygon_include_seam:
                    seam_length_map = panel.get("seam_length_map", {})
                    if seam_length_map and isinstance(seam_length_map, dict):
                        actual_seam_length = sum(safe_float(v) for v in seam_length_map.values()) * p_count
                        seam_unit = str(panel.get("seam_unit", "INCH")).upper().strip()
                        if seam_unit == "MM": actual_seam_length /= 25.4
                        elif seam_unit == "CM": actual_seam_length /= 2.54
                        seam_area_addition = actual_seam_length * FACTORY_SEAM_INCH
                    else:
                        default_perimeter = ((eval_len * 2) + (eval_wid * 2)) * p_count
                        seam_perimeter = safe_float(panel.get("seam_perimeter_inch"), default_perimeter)
                        seam_area_addition = (seam_perimeter * 0.85) * FACTORY_SEAM_INCH
                    net_panel_area += seam_area_addition

                if hem_val > 0 and not polygon_include_hem:
                    current_hem = FACTORY_HEM_INCH
                    if any(k in p_name or k in p_type_code for k in ["SLEEVE", "TAY"]): current_hem = 1.0
                    net_panel_area += (eval_wid * current_hem) * p_count

                if pleat_val > 0:
                    pleat_width = safe_float(panel.get("pleat_width"), 1.0)
                    pleat_count = safe_float(panel.get("pleat_count"), 1.0)
                    net_panel_area += (eval_len * pleat_width * pleat_count) * p_count

                row_total_net_area_sq_in += net_panel_area
                panel_debug_logs.append({
                    "panel_name": p_name, "piece_count": p_count, "computed_area_sq_in": round(net_panel_area, 3)
                })

        row["_computed_net_area_sq_in"] = row_total_net_area_sq_in
        row["_panel_debug_logs"] = panel_debug_logs
        parsed_rows.append(row)

    ai_blueprint["bom_rows"] = parsed_rows
    return ai_blueprint

def execute_marker_yardage_and_quality_gate(ai_blueprint: dict, user_chat: str) -> dict:
    """
    Phân đoạn 2a2: Gom nhóm diện tích dệt, đồng bộ hóa hệ số hiệu suất sơ đồ (Marker)
    Cải tiến: Bóc tách thông minh chuỗi co rút dạng '5-15', '5x15' hoặc 'dọc 5 ngang 15'.
    """
    all_rows = ai_blueprint.get("bom_rows", [])
    fabric_registry = {}

    w_chat, s_l_chat, s_w_chat = None, None, None
    chat_clean = str(user_chat).lower().strip()
    
    # 1. Bóc tách thông số Khổ vải (Ví dụ: "khổ 58", "kho 58")
    match_w = re.search(r'(?:khổ|kho)\s*([\d\.]+)', chat_clean)
    if match_w: w_chat = float(match_w.group(1))
    
    # 2. Bóc tách linh hoạt biên độ co rút dạng: "5-15", "5x15", "5 15", "dọc 5 ngang 15"
    match_range = re.search(r'(?:co\s*rút|co\s*rut|co)\s*([\d\.]+)\s*(?:-|–|x|ngang|\s+)\s*([\d\.]+)', chat_clean)
    if match_range: 
        s_l_chat = float(match_range.group(1))
        s_w_chat = float(match_range.group(2))
    else:
        # Tìm kiếm riêng lẻ nếu user gõ tách rời "dọc 5" và "ngang 15"
        match_doc = re.search(r'(?:dọc|doc)\s*([\d\.]+)', chat_clean)
        match_ngang = re.search(r'(?:ngang)\s*([\d\.]+)', chat_clean)
        if match_doc: s_l_chat = float(match_doc.group(1))
        if match_ngang: s_w_chat = float(match_ngang.group(2))

    for row in all_rows:
        if "_computed_net_area_sq_in" not in row: continue

        f_class_raw = row.get("fabric_classification", "MAIN_FABRIC")
        f_class_norm = normalize_fabric_class(f_class_raw)
        f_code = str(row.get("fabric_code", "MAIN")).upper().strip().replace(" ", "_")
        f_color = str(row.get("fabric_color", "COLOR")).upper().strip().replace(" ", "_")
        grain_rule = str(row.get("fabric_grain_rule", "TWO_WAY")).upper().strip().replace(" ", "_")
        fab_repeat = safe_float(row.get("fabric_repeat_inch"), 0.0)
        
        tmp_id = f"{f_code}_{f_color}_{grain_rule}_{int(fab_repeat)}"
        
        # Áp dụng thông số từ ô chat, nếu không có mới dùng giá trị mặc định của file
        w_b = w_chat if w_chat is not None else safe_float(row.get("fabric_width_inch"), 56.0)
        s_warp = s_l_chat if s_l_chat is not None else safe_float(row.get("shrinkage_warp_pct"), 5.0)
        s_weft = s_w_chat if s_w_chat is not None else safe_float(row.get("shrinkage_weft_pct"), 10.0)
        
        if tmp_id not in fabric_registry:
            if f_class_norm == "RIB":
                raw_eff = 95.0
                consumption_mode = "LINEAR"
            elif f_class_norm == "LINING":
                raw_eff = 88.0
                consumption_mode = "AREA"
            else:
                raw_eff = simulate_marker_efficiency_v14(row.get("panels_catalog", []), f_class_norm, grain_rule, w_b, fab_repeat)
                consumption_mode = "AREA"

            eff_factor = max(0.50, min(raw_eff / 100.0 if raw_eff > 1.0 else raw_eff, 0.95))

            fabric_registry[tmp_id] = {
                "accumulated_area_sq_in": 0.0,
                "cutable_w": max(40.0, w_b - 1.5), 
                "eff": eff_factor, 
                "shrink_warp_f": 1.0 + (s_warp / 100.0),
                "shrink_weft_f": 1.0 + (s_weft / 100.0),
                "wastage_f": 1.03, 
                "consumption_mode": consumption_mode,
                "rows_to_update": [],
                "w_saved": w_b, "s_l_saved": s_warp, "s_w_saved": s_weft, "f_class": f_class_norm
            }
        
        fabric_registry[tmp_id]["accumulated_area_sq_in"] += row["_computed_net_area_sq_in"]
        fabric_registry[tmp_id]["rows_to_update"].append(row)

    ai_blueprint["_fabric_registry_cache"] = fabric_registry
    return ai_blueprint




def allocate_fabric_consumption_and_quality_gate(ai_blueprint: dict) -> dict:
    """
    Phân đoạn 2b: Tính toán định mức Yards thực tế và ép định mức = 0 cho nhóm phụ liệu phần cứng,
    chỉ tính toán định mức cho Vải chính, Keo (Fusing), Lót (Lining/Pocketing), Phối, Rib, Tape, Thun, Piping.
    """
    product_type = str(ai_blueprint.get("detected_product_type", "DEFAULT")).upper().strip()
    fabric_registry = ai_blueprint.pop("_fabric_registry_cache", {})
    processed_bom_blueprint = []
    
    # 1. Quét trước toàn bộ bom_rows để xử lý lọc các dòng phụ liệu độc lập
    all_rows = ai_blueprint.get("bom_rows", [])
    
    for row in all_rows:
        comp_type = str(row.get("component_type", "")).upper()
        placement = str(row.get("placement", "")).upper()
        f_class_raw = str(row.get("fabric_classification", "")).upper()
        f_code = str(row.get("fabric_code", "")).upper()

        # Kiểm tra dính từ khóa loại trừ (chỉ, nhãn, nút, khóa, sticker...) -> Ép định mức về bằng 0 ngay
        if any(k in comp_type or k in placement or k in f_class_raw or k in f_code for k in EXCLUDE_HARDWARE_KEYS):
            row["calculated_gross_consumption_yds"] = 0.0
            row["marker_efficiency_pct"] = "N/A"
            row["status"] = "PASS"
            row["consumption_note"] = "Hardware Trim Bypass"
            row["reason_or_logs"] = "Bypass hoàn toàn theo yêu cầu phòng cắt"
            if row not in processed_bom_blueprint:
                processed_bom_blueprint.append(row)

    # 2. Tính toán định mức phân phối cho các nhóm dệt/phối/phụ liệu may mặc
    for f_id, data in fabric_registry.items():
        total_area = data["accumulated_area_sq_in"]
        cutable_w = data["cutable_w"]
        eff = data["eff"]
        f_class_norm = data["f_class"]

        for row in data["rows_to_update"]:
            comp_type = str(row.get("component_type", "")).upper()
            placement = str(row.get("placement", "")).upper()
            f_code = str(row.get("fabric_code", "")).upper()

            # Chặn rò rỉ nếu dòng vật tư phụ nằm lẫn lộn trong nhóm fabric id
            if any(k in comp_type or k in placement or k in f_code for k in EXCLUDE_HARDWARE_KEYS):
                row["calculated_gross_consumption_yds"] = 0.0
                row["marker_efficiency_pct"] = "N/A"
                row["status"] = "PASS"
                row["consumption_note"] = "Hardware Trim Bypass"
                if row not in processed_bom_blueprint:
                    processed_bom_blueprint.append(row)
                continue

            # Thực hiện tính toán định mức Yards dựa trên phân tầng nguyên vật liệu
            if f_class_norm == "MAIN_FABRIC":
                # Vải chính: Tính toán dựa trên diện tích hình học rập thật từ CAD
                base_cons = (total_area / (cutable_w * 36.0)) / eff
                total_yds = base_cons * data["shrink_warp_f"] * data["shrink_weft_f"] * data["wastage_f"]
                total_yds = round(total_yds, 4)
                row_status = "PASS"
                
                # Cổng kiểm duyệt chất lượng PLM
                cfg = LIMITS.get(product_type, LIMITS["DEFAULT"])
                min_allow, max_allow = cfg["range"]
                
                if total_yds > max_allow: row_status = "CRITICAL_HIGH_CONSUMPTION"
                elif total_yds < min_allow: row_status = "LOW_CONSUMPTION_WARNING"
                elif total_yds > cfg["warn_thresh"]: row_status = "HIGH_CONSUMPTION_WARNING"
                
                row["calculated_gross_consumption_yds"] = total_yds
                row["status"] = row_status
                row["consumption_note"] = f"Mode: AREA | CutWidth: {cutable_w}\" | Check: {row_status}"
                
            else:
                # Định mức kỹ thuật cố định áp cho nhóm Keo lót / Rib / Tape / Thun / Piping
                if f_class_norm in ["FUSING", "LINING", "POCKETING"] or any(x in comp_type for x in ["TAPE", "RIB", "THUN", "PIPING", "PHỐI"]):
                    f_yds = 0.15 if product_type in ["PANT", "JORT", "CAPRI_PANT", "CARGO_PANT"] else 0.65
                else:
                    f_yds = 0.0
                
                row["calculated_gross_consumption_yds"] = f_yds
                row["status"] = "PASS"
                row["consumption_note"] = "Component Fixed Allocation"

            row["marker_efficiency_pct"] = f"{round(eff * 100, 1)}%"
            row["panel_debug_summary"] = row.get("_panel_debug_logs", [])
            row.pop("_computed_net_area_sq_in", None)
            row.pop("_panel_debug_logs", None)
            
            if row not in processed_bom_blueprint:
                processed_bom_blueprint.append(row)

    ai_blueprint["bom_rows"] = processed_bom_blueprint
    return ai_blueprint



# =====================================================================
# ĐOẠN 3 & 4: RENDER BẢNG ĐỊNH MỨC VÀ TÍCH HỢP XUẤT FILE EXCEL V15.8
# =====================================================================
import streamlit as st
import pandas as pd
import io
import json
import re

st.set_page_config(page_title="AI CAD Fabric Consumption Engine", layout="wide")

# CSS Đồng bộ màu xám sáng công nghiệp cao cấp
st.markdown("""
    <style>
    .stApp { background-color: #f4f6f9; color: #2d3748; }
    [data-testid="stSidebar"] { background-color: #e2e8f0; border-right: 1px solid #cbd5e1; }
    
    .cad-card {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 20px;
        margin-bottom: 16px;
        box-shadow: 0 4px 10px rgba(0, 0, 0, 0.05);
    }
    
    .cad-header {
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        color: #1e40af;
        font-weight: 700;
        border-bottom: 2px solid #3b82f6;
        padding-bottom: 8px;
        margin-bottom: 16px;
        text-transform: uppercase;
        font-size: 14px;
    }
    
    .chat-box {
        background-color: #f8fafc;
        border-radius: 6px;
        padding: 14px;
        height: 280px;
        overflow-y: auto;
        font-family: 'Courier New', Courier, monospace;
        font-size: 13px;
        border: 1px solid #cbd5e1;
        white-space: pre-wrap;       
        word-wrap: break-word;       
    }
    </style>
""", unsafe_allow_html=True)

if "bom_data" not in st.session_state: st.session_state.bom_data = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = [{"role": "assistant", "content": "[SYSTEM READY] V15.8 Light Core active."}]

# --- SIDEBAR CONTROL PANEL ---
with st.sidebar:
    st.markdown('<div class="cad-header">⚙️ ENGINE CONTROLS</div>', unsafe_allow_html=True)
    
    # 1. KIỂM TRA TRẠNG THÁI LỖI QUOTA TRONG SESSION STATE ĐỂ HIỂN THỊ TỰ ĐỘNG
    if st.session_state.get("api_error_status") == 429:
        st.error("🚨 **HỆ THỐNG HẾT DUNG LƯỢNG:** Hạn ngạch API hiện tại đã bị vượt quá (Error 429). Vui lòng nâng cấp tài khoản hoặc thử lại sau.")
    else:
        st.success("🟢 **API STATUS:** Hệ thống đang hoạt động trong hạn ngạch cho phép.")
    
    if st.button("🗑️ CLEAR SYSTEM MEMORY", use_container_width=True, type="secondary"):
        st.session_state.bom_data = None
        st.session_state.pdf_bytes = None
        st.session_state.pdf_name = None
        st.session_state.api_error_status = None  # Xóa trạng thái lỗi khi reset hệ thống
        st.session_state.chat_history = [{"role": "assistant", "content": "[SYSTEM] Session cache purged."}]
        st.rerun()


# --- MAIN DASHBOARD INTERFACE ---
st.title("🏭 AI CAD Fabric Consumption Engine")
st.caption("PLM-Integrated Pattern Discovery & Marker Analytics • Version 15.8")

# Cấu trúc lưới hai cột đối xứng sạch sẽ
col_left, col_right = st.columns(2)

with col_left:
    st.markdown('<div class="cad-card">', unsafe_allow_html=True)
    st.markdown('<div class="cad-header">📥 FILE INGESTION (PDF/TECHPACK)</div>', unsafe_allow_html=True)
    uploaded_file = st.file_uploader("Upload Spec", type=["pdf"], key="v158_uploader", label_visibility="collapsed")
    if uploaded_file is not None:
        st.session_state.pdf_bytes = uploaded_file.read()
        st.session_state.pdf_name = uploaded_file.name
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="cad-card">', unsafe_allow_html=True)
    st.markdown('<div class="cad-header">💻 CAD LIVE LOG CONSOLE</div>', unsafe_allow_html=True)
    chat_html = '<div class="chat-box">'
    for chat in st.session_state.get("chat_history", []):
        color = '#1e3a8a' if chat["role"] == "assistant" else '#b45309'
        prefix = "🤖 [CAD]: " if chat["role"] == "assistant" else "👤 [USER]: "
        chat_html += f"<div style='margin-bottom:8px; color: {color}'>{prefix}{chat['content']}</div>"
    chat_html += '</div>'
    st.markdown(chat_html, unsafe_allow_html=True)
    user_prompt = st.chat_input("Input override commands...")
    st.markdown('</div>', unsafe_allow_html=True)

with col_right:
    # =====================================================================
    # 🎨 VỊ TRÍ DUY NHẤT: HIỂN THỊ HÌNH ẢNH SKETCH LÊN TRÊN CÙNG
    # =====================================================================
    if "pdf_bytes" in st.session_state:
        try:
            import fitz  
            doc = fitz.open(stream=st.session_state.pdf_bytes, filetype="pdf")
            page = doc.load_page(0)  
            pix = page.get_pixmap(dpi=150)
            img_data = pix.tobytes("png")
            
            st.image(
                img_data, 
                caption=f"🎨 Bản Vẽ Kỹ Thuật Trích Xuất Từ Tệp: {st.session_state.pdf_name}", 
                use_container_width=True
            )
        except Exception:
            pass
    else:
        st.caption("ℹ️ Hệ thống sẵn sàng kết xuất hình ảnh phác thảo sau khi tải file.")

    if "pdf_bytes" in st.session_state:
        st.success(f"📎 BUFFERED OBJECT: `{st.session_state.pdf_name}` loaded successfully.")

    # TỰ ĐỘNG KÍCH HOẠT KHI USER NHẬP CÂU LỆNH CHAT VÀ ĐÃ CÓ FILE
    if user_prompt and "pdf_bytes" in st.session_state:
        with st.spinner("🧠 AI đang bóc tách cấu trúc hình học sơ đồ BOM thực tế..."):
            try:
                import google.generativeai as genai
                import google.api_core.exceptions
                import json
                import copy
                
                # 🟢 TỰ ĐỘNG NẠP KEY TỪ SECRETS MÀ KHÔNG CẦN CHÈN TRỰC TIẾP VÀO CODE
                if "GEMINI_API_KEY" in st.secrets:
                    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
                elif "google" in st.secrets and "api_key" in st.secrets["google"]:
                    genai.configure(api_key=st.secrets["google"]["api_key"])
                
                st.session_state.chat_history.append({"role": "user", "content": user_prompt})
                model = genai.GenerativeModel("gemini-2.5-flash", generation_config={"response_mime_type": "application/json"})
                
                prompt_instruction = f"""
                You are an expert apparel CAD data extractor and PLM analyzer. Analyze the attached Techpack/PDF document.
                Your goal is to extract the ACTUAL Bill of Materials (BOM) and technical measurement data from the file.
                
                CRITICAL FILTRATION RULES FOR BOM EXTRACTION:
                1. ONLY extract: Main Fabric (Vải chính), Lining/Pocketing (Vải lót túi), Fusing/Interlining (Keo dựng), Rib/Tape/Piping (Bo/Dây dệt/Viền), Elastic (Thun).
                2. STRICTLY EXCLUDE: Thread, Labels/Tags, Buttons/Snaps, Zippers, Packaging. Do not include these in 'bom_rows'.

                DATA EXTRACTION REQUIREMENTS:
                - Scan the document for garment measurement charts or CAD pattern panel specifications.
                - For each fabric/component row, look at the measurement sheet to estimate or extract the 'panels_catalog'.
                - If exact panel sizes are written (e.g., Waist, Hips, Inseam, Front Rise, Back Rise), use them to generate realistic 'piece_length_inch' and 'piece_width_inch' for the panels (such as Front Panel, Back Panel, Waistband, Pocket Bag) so that the calculated area is NOT zero.
                - Ensure 'piece_count' is correctly extracted (e.g., Front Panel count: 2, Back Panel count: 2).

                Return a JSON matching this exact structure:
                {{
                    "detected_product_type": "PANT",
                    "extracted_body_length": 40.0,
                    "bom_rows": [
                        {{
                            "component_type": "MAIN FABRIC",
                            "placement": "SELF BODY",
                            "fabric_classification": "MAIN_FABRIC",
                            "fabric_code": "Extract from document",
                            "fabric_color": "Extract from document",
                            "fabric_width_inch": 58.0,
                            "panels_catalog": [
                                {{
                                    "panel_name": "FRONT PANEL", 
                                    "piece_count": 2, 
                                    "piece_length_inch": 38.0, 
                                    "piece_width_inch": 14.0
                                }},
                                {{
                                    "panel_name": "BACK PANEL", 
                                    "piece_count": 2, 
                                    "piece_length_inch": 39.0, 
                                    "piece_width_inch": 16.0
                                }}
                            ]
                        }}
                    ]
                }}
                User prompt overrides for parsing parameters: {user_prompt}
                """
                
                pdf_part = {"mime_type": "application/pdf", "data": st.session_state.pdf_bytes}
                response = model.generate_content([pdf_part, prompt_instruction])
                
                raw_blueprint = json.loads(response.text)
                st.session_state.raw_blueprint = raw_blueprint
                
                # 🟢 XÓA TRẠNG THÁI LỖI 429 CŨ NGAY KHI GỌI THÀNH CÔNG VỚI KEY MỚI
                st.session_state.api_error_status = None
                
                working_blueprint = copy.deepcopy(st.session_state.raw_blueprint)
                
                step_2a1 = parse_geometric_panels_allowance(working_blueprint, user_prompt)
                step_2a2 = execute_marker_yardage_and_quality_gate(step_2a1, user_prompt)
                blueprint_final = allocate_fabric_consumption_and_quality_gate(step_2a2)
                
                st.session_state.bom_data = blueprint_final
                
                st.session_state.chat_history.append({
                    "role": "assistant", 
                    "content": f"[SUCCESS]: Đã trích xuất cấu trúc vải thực tế và áp dụng thông số: \"{user_prompt}\""
                })
                st.rerun()
                
            except google.api_core.exceptions.ResourceExhausted:
                # Nếu key mới cũng hết dung lượng hoặc tần suất enter quá nhanh
                st.session_state.api_error_status = 429
                st.session_state.chat_history.append({"role": "assistant", "content": "[🚨 API ERROR 429]: Hết hạn ngạch. Vui lòng thử lại sau ít phút."})
                st.rerun()
            except Exception as e:
                st.error(f"💥 Lỗi phân tích: {str(e)}")
                st.session_state.chat_history.append({"role": "assistant", "content": f"[CRASH]: {str(e)}"})
                st.rerun()






# =====================================================================
# ĐOẠN 4: ENGINE XUẤT EXCEL THEO FORM MẪU BÁO CÁO PHONG PHÚ (V15.9)
# =====================================================================
import streamlit as st
import pandas as pd
import io
import re

def export_to_phong_phu_excel(bom_data, pdf_name):
    """
    Hàm đóng gói dữ liệu và tự động căn chỉnh format, font chữ, kẻ viền
    để xuất ra file Excel giống hệt biểu mẫu Phong Phú thực tế.
    """
    buffer = io.BytesIO()
    
    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
        workbook  = writer.book
        font_name = 'Segoe UI' 
        
        company_format = workbook.add_format({
            'font_name': font_name, 'font_size': 11, 'bold': True, 'color': '#1e3a8a'
        })
        dept_format = workbook.add_format({
            'font_name': font_name, 'font_size': 10, 'italic': True, 'color': '#475569'
        })
        title_format = workbook.add_format({
            'font_name': font_name, 'font_size': 16, 'bold': True, 
            'align': 'center', 'valign': 'vcenter', 'color': '#0f172a'
        })
        info_label_format = workbook.add_format({
            'font_name': font_name, 'font_size': 10, 'bold': True, 'color': '#334155'
        })
        info_val_format = workbook.add_format({
            'font_name': font_name, 'font_size': 10, 'color': '#0f172a'
        })
        header_format = workbook.add_format({
            'font_name': font_name, 'font_size': 10, 'bold': True,
            'align': 'center', 'valign': 'vcenter',
            'bg_color': '#e0f2fe', 'color': '#0369a1',
            'border': 1, 'border_color': '#cbd5e1'
        })
        
        cell_center = workbook.add_format({'font_name': font_name, 'font_size': 10, 'align': 'center', 'border': 1, 'border_color': '#cbd5e1'})
        cell_left   = workbook.add_format({'font_name': font_name, 'font_size': 10, 'align': 'left', 'border': 1, 'border_color': '#cbd5e1'})
        cell_right  = workbook.add_format({'font_name': font_name, 'font_size': 10, 'align': 'right', 'border': 1, 'border_color': '#cbd5e1', 'num_format': '#,##0.000'})
        
        pass_format = workbook.add_format({'font_name': font_name, 'font_size': 10, 'align': 'center', 'bg_color': '#dcfce7', 'color': '#15803d', 'border': 1, 'border_color': '#cbd5e1', 'bold': True})
        warn_format = workbook.add_format({'font_name': font_name, 'font_size': 10, 'align': 'center', 'bg_color': '#fef9c3', 'color': '#a16207', 'border': 1, 'border_color': '#cbd5e1', 'bold': True})
        crit_format = workbook.add_format({'font_name': font_name, 'font_size': 10, 'align': 'center', 'bg_color': '#fee2e2', 'color': '#b91c1c', 'border': 1, 'border_color': '#cbd5e1', 'bold': True})
        sign_title_format = workbook.add_format({'font_name': font_name, 'font_size': 10, 'bold': True, 'align': 'center'})

        worksheet = workbook.add_worksheet('BẢNG ĐỊNH MỨC KỸ THUẬT')
        worksheet.hide_gridlines(2) 
        
        worksheet.write('A1', 'CTY CỔ PHẦN QUỐC TẾ PHONG PHÚ', company_format)
        worksheet.write('A2', '⚙️ Phòng Kỹ Thuật May - IE Engine Core', dept_format)
        worksheet.merge_range('A4:I4', 'BẢNG ĐỊNH MỨC KỸ THUẬT (APPROVED CONSUMPTION)', title_format)
        
        style_code_extracted = str(bom_data.get("style_code", "R09-450416")).upper()
        prod_type_extracted = str(bom_data.get("detected_product_type", "PANT")).upper()
        
        metadata = [
            ('CUSTOMER:', 'REITMANS', 'SEASON:', 'NONE'),
            ('STYLE:', style_code_extracted, 'FACTORY:', 'NONE'),
            ('PRODUCT:', prod_type_extracted, 'STATUS:', 'APPROVED BY AI')
        ]
        
        start_row = 5
        for i, data_row in enumerate(metadata):
            worksheet.write(start_row + i, 0, data_row[0], info_label_format)
            worksheet.write(start_row + i, 1, data_row[1], info_val_format)
            worksheet.write(start_row + i, 3, data_row[2], info_label_format)
            worksheet.write(start_row + i, 4, data_row[3], info_val_format)

        headers = [
            "STT", "Phân loại vật tư (Fabric type)", "Mã vải (Code)", 
            "Khổ (Cuttable)", "Định mức (Cons)", "Co rút dọc (% Warp)", 
            "Co rút ngang (% Weft)", "Hiệu suất sơ đồ", "Trạng thái PLM"
        ]
        
        header_row = 10
        for col_num, header_title in enumerate(headers):
            worksheet.write(header_row, col_num, header_title, header_format)
            
        raw_rows = bom_data.get("bom_rows", [])
        current_data_row = header_row + 1
        stt = 1
        
        for r in raw_rows:
            comp_type = r.get("component_type", "MAIN_FABRIC")
            fabric_code = r.get("fabric_code", "MAIN")
            fabric_color = r.get("fabric_color", "COLOR")
            full_code = f"{fabric_code} - {fabric_color}"
            sys_notes = r.get("consumption_note", "")
            
            match_w = re.search(r'CutWidth:\s*([\d\.]+)', sys_notes)
            cut_width = f"{float(match_w.group(1))} inch" if match_w else "56.0 inch"
            
            gross_yds = r.get("calculated_gross_consumption_yds", 0.0)
            marker_eff = r.get("marker_efficiency_pct", "N/A")
            q_status = r.get("status", "PASS")
            
            worksheet.write(current_data_row, 0, stt, cell_center)
            worksheet.write(current_data_row, 1, comp_type, cell_left)
            worksheet.write(current_data_row, 2, full_code, cell_left)
            worksheet.write(current_data_row, 3, cut_width, cell_center)
            worksheet.write(current_data_row, 4, gross_yds, cell_right)
            worksheet.write(current_data_row, 5, "5.0%", cell_center)  
            worksheet.write(current_data_row, 6, "10.0%", cell_center) 
            worksheet.write(current_data_row, 7, marker_eff, cell_center)
            
            if "CRITICAL" in q_status:
                worksheet.write(current_data_row, 8, "🔴 VƯỢT TRẦN", crit_format)
            elif "WARN" in q_status:
                worksheet.write(current_data_row, 8, "🟡 CẢNH BÁO", warn_format)
            else:
                worksheet.write(current_data_row, 8, "🟢 ĐẠT TIÊU CHUẨN", pass_format)
                
            current_data_row += 1
            stt += 1
            
        sign_row = current_data_row + 3
        worksheet.write(sign_row, 1, "NGƯỜI LẬP BIỂU\n(Phòng IE May)", sign_title_format)
        worksheet.write(sign_row, 4, "TRƯỞNG PHÒNG IE\n(Ký duyệt)", sign_title_format)
        worksheet.write(sign_row, 7, "GIÁM ĐỐC SẢN XUẤT\n(Phê duyệt)", sign_title_format)
        
        worksheet.set_column(0, 0, 6)   
        worksheet.set_column(1, 1, 30)  
        worksheet.set_column(2, 2, 25)  
        worksheet.set_column(3, 3, 15)  
        worksheet.set_column(4, 4, 15)  
        worksheet.set_column(5, 7, 18)  
        worksheet.set_column(8, 8, 22)  

    return buffer.getvalue()


# --- KHU VỰC HIỂN THỊ KẾT QUẢ VÀ XUẤT FILE EXCEL PHÍA DƯỚI GIAO DIỆN MÀN HÌNH ---
if st.session_state.get("bom_data") and "bom_rows" in st.session_state.bom_data:
    st.markdown('<div class="cad-card">', unsafe_allow_html=True)
    st.markdown('<div class="cad-header">📊 CALCULATED FABRIC CONSUMPTION MATRIX (BOM RESULT)</div>', unsafe_allow_html=True)
    
    raw_rows_display = st.session_state.bom_data["bom_rows"]
    display_data = []
    for r in raw_rows_display:
        display_data.append({
            "Component Type": r.get("component_type", "N/A"),
            "Placement": r.get("placement", "N/A"),
            "Fabric Classification": r.get("fabric_classification", "MAIN_FABRIC"),
            "Fabric Code": r.get("fabric_code", "MAIN"),
            "Fabric Color": r.get("fabric_color", "COLOR"),
            "Marker Efficiency": r.get("marker_efficiency_pct", "N/A"),
            "Gross Consumption (Yds)": r.get("calculated_gross_consumption_yds", 0.0),
            "Quality Status": r.get("status", "PASS"),
            "System Notes": r.get("consumption_note", "")
        })
    df_bom = pd.DataFrame(display_data)

    # Khởi tạo buffer tải file Excel Phong Phú
    pdf_name_clean = st.session_state.get("pdf_name", "F25R09-490416.pdf")
    phong_phu_excel_bytes = export_to_phong_phu_excel(st.session_state.bom_data, pdf_name_clean)
    
    col_label_pp, col_btn_pp = st.columns([3, 1])
    with col_label_pp:
        st.write("Dữ liệu định mức kỹ thuật đã sẵn sàng xuất bản ra file Excel theo form hệ thống:")
    with col_btn_pp:
        st.download_button(
            label="📥 TẢI MẪU BÁO CÁO PHONG PHÚ (.XLSX)",
            data=phong_phu_excel_bytes,
            file_name=f"Bao_Cao_Dinh_Muc_Phong_Phu_{pdf_name_clean.replace('.pdf', '')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
        
    st.dataframe(df_bom, use_container_width=True, hide_index=True)
    st.markdown('</div>', unsafe_allow_html=True)
