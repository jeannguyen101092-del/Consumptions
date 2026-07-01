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
    và lưu trữ cấu hình thô vào registry trước khi phân bổ chi tiết.
    """
    all_rows = ai_blueprint.get("bom_rows", [])
    fabric_registry = {}

    w_chat, s_l_chat, s_w_chat = None, None, None
    chat_clean = str(user_chat).lower().strip()
    match_w = re.search(r'(?:khổ|kho)\s*(\d+)', chat_clean)
    if match_w: w_chat = float(match_w.group(1))
    match_range = re.search(r'(?:co\s*rút|co\s*rut|co)\s*(\d+)\s*(?:-|–|ngang|\s+)\s*(\d+)', chat_clean)
    if match_range: 
        s_l_chat = float(match_range.group(1))
        s_w_chat = float(match_range.group(2))

    for row in all_rows:
        if "_computed_net_area_sq_in" not in row: continue

        f_class_raw = row.get("fabric_classification", "MAIN_FABRIC")
        f_class_norm = normalize_fabric_class(f_class_raw)
        f_code = str(row.get("fabric_code", "MAIN")).upper().strip().replace(" ", "_")
        f_color = str(row.get("fabric_color", "COLOR")).upper().strip().replace(" ", "_")
        grain_rule = str(row.get("fabric_grain_rule", "TWO_WAY")).upper().strip().replace(" ", "_")
        fab_repeat = safe_float(row.get("fabric_repeat_inch"), 0.0)
        
        tmp_id = f"{f_code}_{f_color}_{grain_rule}_{int(fab_repeat)}"
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

            # 📌 CHỐT ĐỒNG BỘ: Chuyển đổi hiệu suất (ví dụ 89.0 -> 0.89) ngay tại đây
            eff_factor = max(0.50, min(raw_eff / 100.0 if raw_eff > 1.0 else raw_eff, 0.95))

            fabric_registry[tmp_id] = {
                "accumulated_area_sq_in": 0.0,
                "cutable_w": max(40.0, w_b - 1.5), 
                "eff": eff_factor, # Trở thành số thực thập phân an toàn
                "shrink_warp_f": 1.0 + (s_warp / 100.0),
                "shrink_weft_f": 1.0 + (s_weft / 100.0),
                "wastage_f": 1.03, 
                "consumption_mode": consumption_mode,
                "rows_to_update": [],
                "w_saved": w_b, "s_l_saved": s_warp, "s_w_saved": s_weft, "f_class": f_class_norm
            }
        
        fabric_registry[tmp_id]["accumulated_area_sq_in"] += row["_computed_net_area_sq_in"]
        fabric_registry[tmp_id]["rows_to_update"].append(row)

    # Lưu tạm cấu trúc registry vào object để Đoạn 2b đọc tiếp nối luồng dữ liệu
    ai_blueprint["_fabric_registry_cache"] = fabric_registry
    return ai_blueprint



def allocate_fabric_consumption_and_quality_gate(ai_blueprint: dict) -> dict:
    """
    Phân đoạn 2b: Trích xuất bộ đệm, tính toán định mức Yards thực tế chuẩn xác,
    và áp dụng bộ gác cổng kiểm soát biên độ tiêu chuẩn PLM.
    """
    product_type = str(ai_blueprint.get("detected_product_type", "DEFAULT")).upper().strip()
    fabric_registry = ai_blueprint.pop("_fabric_registry_cache", {})
    processed_bom_blueprint = []
    
    # Nạp trả phụ liệu phần cứng từ bước trước
    all_rows = ai_blueprint.get("bom_rows", [])
    for row in all_rows:
        if "_computed_net_area_sq_in" not in row:
            processed_bom_blueprint.append(row)

    for f_id, data in fabric_registry.items():
        if data["f_class"] != "MAIN_FABRIC":
            for r in data["rows_to_update"]:
                f_yds = 0.15 if product_type in ["PANT", "JORT", "CAPRI_PANT", "CARGO_PANT"] else 0.65
                r["calculated_gross_consumption_yds"] = f_yds
                r["marker_efficiency_pct"] = f"{round(data['eff'] * 100, 1)}%"
                r["status"] = "PASS"
                r["consumption_note"] = "Trim/Fusing Fixed"
                r["panel_debug_summary"] = r.get("_panel_debug_logs", [])
                r.pop("_computed_net_area_sq_in", None)
                r.pop("_panel_debug_logs", None)
                processed_bom_blueprint.append(r)
            continue
            
        total_area = data["accumulated_area_sq_in"]
        cutable_w = data["cutable_w"]
        eff = data["eff"] # Nhận giá trị số thực thập phân an toàn (Ví dụ: 0.88)
        
        # 📌 SỬA LỖI CỐT LÕI: Công thức loại bỏ toán tử chia 100 bị lặp lại
        base_cons = (total_area / (cutable_w * 36.0)) / eff
        total_yds_with_self = base_cons * data["shrink_warp_f"] * data["shrink_weft_f"] * data["wastage_f"]
        total_yds_with_self = round(total_yds_with_self, 4)

        row_status = "PASS"
        cfg = LIMITS.get(product_type, LIMITS["DEFAULT"])
        min_allow, max_allow = cfg["range"]
        high_ceiling = max_allow 
        
        if total_yds_with_self > high_ceiling:
            row_status = "CRITICAL_HIGH_CONSUMPTION"
            exceed_val = round(total_yds_with_self - high_ceiling, 2)
            log_output = f"{int(data['w_saved'])}\"/{round(eff*100,1)}%/{int(data['s_l_saved'])}x{int(data['s_w_saved'])} | Rập {f_id}: {round(total_area,1)} sq_in. 🔴 VƯỢT TRẦN TIÊU CHUẨN (+{exceed_val} yds)"
        elif total_yds_with_self < min_allow:
            row_status = "LOW_CONSUMPTION_WARNING"
            log_output = f"{int(data['w_saved'])}\"/{round(eff*100,1)}%/{int(data['s_l_saved'])}x{int(data['s_w_saved'])} | Rập {f_id}: {round(total_area,1)} sq_in. 🔵 ĐỊNH MỨC THẤP DƯỚI BIÊN ĐỘ"
        elif total_yds_with_self > cfg["warn_thresh"]:
            row_status = "HIGH_CONSUMPTION_WARNING"
            log_output = f"{int(data['w_saved'])}\"/{round(eff*100,1)}%/{int(data['s_l_saved'])}x{int(data['s_w_saved'])} | Rập {f_id}: {round(total_area,1)} sq_in. 🟡 CẢNH BÁO PLM"
        else:
            log_output = f"{int(data['w_saved'])}\"/{round(eff*100,1)}%/{int(data['s_l_saved'])}x{int(data['s_w_saved'])} | Rập {f_id}: {round(total_area,1)} sq_in. 🟢 ĐẠT TIÊU CHUẨN MAY"

        for row in data["rows_to_update"]:
            row["calculated_gross_consumption_yds"] = total_yds_with_self
            row["marker_efficiency_pct"] = f"{round(eff * 100, 1)}%"
            row["status"] = row_status
            row["consumption_note"] = f"Mode: AREA | CutWidth: {cutable_w}\" | Check: {row_status}"
            row["reason_or_logs"] = log_output
            row["panel_debug_summary"] = row.get("_panel_debug_logs", [])
            
            row.pop("_computed_net_area_sq_in", None)
            row.pop("_panel_debug_logs", None)
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
    st.markdown('<div class="cad-card" style="min-height: 450px;">', unsafe_allow_html=True)
    st.markdown('<div class="cad-header">🚀 EXECUTION WORKSPACE</div>', unsafe_allow_html=True)
    st.markdown("<p style='color:#475569;'>Ready to process vector coordinate tables and apply structural seam/pleat adjustments.</p>", unsafe_allow_html=True)
    
    # KIỂM TRA TRẠNG THÁI FILE TRONG BỘ ĐỆM
    if "pdf_bytes" not in st.session_state:
        st.caption("⚪ SYSTEM STATE: Directory unmounted. Upload a techpack file to activate.")
    else:
        st.success(f"📎 BUFFERED OBJECT: `{st.session_state.pdf_name}` loaded successfully.")

    # TỰ ĐỘNG KÍCH HOẠT LÕI TÍNH TOÁN KHI PHÁT HIỆN CÓ LỆNH CHAT MỚI VÀ ĐÃ UPLOAD FILE
    if user_prompt and "pdf_bytes" in st.session_state:
        if st.session_state.get("api_error_status") == 429:
            st.error("❌ Không thể chạy do API Google Gemini đang hết hạn ngạch (Lỗi 429).")
        else:
            with st.spinner("⏳ Khởi động Engine: Tự động tính toán theo lệnh phòng cắt..."):
                try:
                    # Lưu tin nhắn của user vào lịch sử hội thoại trước
                    st.session_state.chat_history.append({"role": "user", "content": user_prompt})
                    
                    # 1. Khởi tạo dữ liệu thô giả lập (Thay bằng hàm gọi API thực tế nếu có)
                    if "raw_blueprint" not in st.session_state:
                        st.session_state.raw_blueprint = {
                            "detected_product_type": "PANT",
                            "bom_rows": [
                                {
                                    "component_type": "MAIN FABRIC", "placement": "FRONT PANEL",
                                    "fabric_classification": "MAIN_FABRIC", "fabric_code": "DENIM_01", "fabric_color": "INDIGO",
                                    "panels_catalog": [{"panel_name": "THÂN TRƯỚC", "piece_count": 2, "piece_length_inch": 40.0, "piece_width_inch": 12.0}]
                                }
                            ]
                        }
                    
                    # Sao chép dữ liệu tránh xung đột vùng nhớ
                    import copy
                    working_blueprint = copy.deepcopy(st.session_state.raw_blueprint)
                    
                    # 2. CHẠY TUẦN TỰ THEO 3 PHÂN ĐOẠN ĐỘC LẬP THEO THÔNG TIN CHAT CỦA USER
                    step_2a1 = parse_geometric_panels_allowance(working_blueprint, user_prompt)
                    step_2a2 = execute_marker_yardage_and_quality_gate(step_2a1, user_prompt)
                    blueprint_final = allocate_fabric_consumption_and_quality_gate(step_2a2)
                    
                    # 3. Lưu kết quả cuối cùng để render bảng dữ liệu bên dưới màn hình
                    st.session_state.bom_data = blueprint_final
                    
                    # 4. Ghi nhận nhật ký thành công vào Live Log Console
                    st.session_state.chat_history.append({
                        "role": "assistant", 
                        "content": f"[SUCCESS]: Đã cập nhật tính toán định mức dựa trên lệnh: \"{user_prompt}\""
                    })
                    
                    # Tải lại trang để cập nhật giao diện
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"💥 Lỗi tiến trình nội bộ: {str(e)}")
                    st.session_state.chat_history.append({"role": "assistant", "content": f"[CRASH]: {str(e)}"})
                    st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)






# --- KHU VỰC HIỂN THỊ KẾT QUẢ VÀ XUẤT FILE EXCEL PHÍA DƯỚI GIAO DIỆN MÀN HÌNH ---
# Điều kiện: Chỉ hiển thị khi st.session_state.bom_data chứa dữ liệu đã được xử lý từ Đoạn 2a2
if st.session_state.bom_data and "bom_rows" in st.session_state.bom_data:
    st.markdown('<div class="cad-card">', unsafe_allow_html=True)
    st.markdown('<div class="cad-header">📊 CALCULATED FABRIC CONSUMPTION MATRIX (BOM RESULT)</div>', unsafe_allow_html=True)
    
    # 1. Chuyển đổi dữ liệu BOM thô sang DataFrame để hiển thị và xuất file
    raw_rows = st.session_state.bom_data["bom_rows"]
    
    # Làm sạch các cột hiển thị ra màn hình cho chuyên nghiệp
    display_data = []
    for r in raw_rows:
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
    
    # 2. XỬ LÝ ĐÓNG GÓI EXCEL CHUẨN ĐƠN VỊ VÀ ĐĂNG KÝ NÚT BẤM DOWNLOAD
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
        df_bom.to_excel(writer, index=False, sheet_name='Fabric_Consumption_BOM')
        # Tự động căn chỉnh độ rộng cột Excel
        worksheet = writer.sheets['Fabric_Consumption_BOM']
        for idx, col in enumerate(df_bom.columns):
            max_len = max(df_bom[col].astype(str).map(len).max(), len(col)) + 3
            worksheet.set_column(idx, idx, max_len)
            
    excel_data = buffer.getvalue()

    # Layout nút xuất Excel nằm ngay phía trên bảng số liệu
    col_table_hdr, col_btn_export = st.columns([3, 1])
    with col_table_hdr:
        st.write("Bản xem trước dữ liệu định mức tính toán tự động dựa trên sơ đồ rập:")
    with col_btn_export:
        # Nút bấm chính thức tải file Excel về hệ thống
        st.download_button(
            label="🟢 EXPORT TO EXCEL (.XLSX)",
            data=excel_data,
            file_name=f"AI_CAD_Fabric_BOM_{st.session_state.bom_data.get('style_code', 'GUEST')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
        
    # Render bảng dữ liệu tương tác lên Streamlit màn hình sáng
    st.dataframe(df_bom, use_container_width=True, hide_index=True)
    st.markdown('</div>', unsafe_allow_html=True)
# =====================================================================
# ĐOẠN 4: ENGINE XUẤT EXCEL THEO FORM MẪU BÁO CÁO PHONG PHÚ (V15.9)
# =====================================================================
import streamlit as st
import pandas as pd
import io

def export_to_phong_phu_excel(bom_data, pdf_name):
    """
    Hàm đóng gói dữ liệu và tự động căn chỉnh format, font chữ, kẻ viền
    để xuất ra file Excel giống hệt biểu mẫu Phong Phú thực tế.
    """
    buffer = io.BytesIO()
    
    # Khởi tạo workbook với engine xlsxwriter để can thiệp sâu vào format định dạng
    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
        workbook  = writer.book
        
        # 1. THIẾT LẬP MA TRẬN PHÔNG CHỮ VÀ MÀU SẮC CHUYÊN NGÀNH (FONTS & FORMATS)
        font_name = 'Segoe UI' # Font chữ phẳng hiện đại, sạch sẽ
        
        # Format cho Tiêu đề Công ty (Dòng 1, 2)
        company_format = workbook.add_format({
            'font_name': font_name, 'font_size': 11, 'bold': True, 'color': '#1e3a8a'
        })
        dept_format = workbook.add_format({
            'font_name': font_name, 'font_size': 10, 'italic': True, 'color': '#475569'
        })
        
        # Format cho Tiêu đề Bảng Chính (Dòng 4)
        title_format = workbook.add_format({
            'font_name': font_name, 'font_size': 16, 'bold': True, 
            'align': 'center', 'valign': 'vcenter', 'color': '#0f172a'
        })
        
        # Format cho Cụm Thông tin Mã hàng (Style, Season, Customer...)
        info_label_format = workbook.add_format({
            'font_name': font_name, 'font_size': 10, 'bold': True, 'color': '#334155'
        })
        info_val_format = workbook.add_format({
            'font_name': font_name, 'font_size': 10, 'color': '#0f172a'
        })
        
        # Format cho Tiêu đề các Cột của Bảng Lưới (Header Grid) - Phối màu xanh dương nhạt
        header_format = workbook.add_format({
            'font_name': font_name, 'font_size': 10, 'bold': True,
            'align': 'center', 'valign': 'vcenter',
            'bg_color': '#e0f2fe', 'color': '#0369a1',
            'border': 1, 'border_color': '#cbd5e1'
        })
        
        # Format dữ liệu nền chung trong bảng
        cell_center = workbook.add_format({'font_name': font_name, 'font_size': 10, 'align': 'center', 'border': 1, 'border_color': '#cbd5e1'})
        cell_left   = workbook.add_format({'font_name': font_name, 'font_size': 10, 'align': 'left', 'border': 1, 'border_color': '#cbd5e1'})
        cell_right  = workbook.add_format({'font_name': font_name, 'font_size': 10, 'align': 'right', 'border': 1, 'border_color': '#cbd5e1', 'num_format': '#,##0.000'})
        
        # Format màu cảnh báo rủi ro Quality Gate cho cột trạng thái
        pass_format = workbook.add_format({'font_name': font_name, 'font_size': 10, 'align': 'center', 'bg_color': '#dcfce7', 'color': '#15803d', 'border': 1, 'border_color': '#cbd5e1', 'bold': True})
        warn_format = workbook.add_format({'font_name': font_name, 'font_size': 10, 'align': 'center', 'bg_color': '#fef9c3', 'color': '#a16207', 'border': 1, 'border_color': '#cbd5e1', 'bold': True})
        crit_format = workbook.add_format({'font_name': font_name, 'font_size': 10, 'align': 'center', 'bg_color': '#fee2e2', 'color': '#b91c1c', 'border': 1, 'border_color': '#cbd5e1', 'bold': True})

        # Format khu vực chữ ký góc dưới (Ký duyệt)
        sign_title_format = workbook.add_format({'font_name': font_name, 'font_size': 10, 'bold': True, 'align': 'center'})

        # 2. KHỞI TẠO SHEET VÀ ĐỔ DỮ LIỆU ĐỊNH VỊ
        worksheet = workbook.add_worksheet('BẢNG ĐỊNH MỨC KỸ THUẬT')
        worksheet.hide_gridlines(2) # Ẩn lưới mặc định của Excel, chỉ hiện khung kẻ tùy biến để bảng trông sạch sẽ
        
        # A. Ghi thông tin tiêu đề doanh nghiệp (Dòng 1, 2)
        worksheet.write('A1', 'CTY CỔ PHẦN QUỐC TẾ PHONG PHÚ', company_format)
        worksheet.write('A2', '⚙️ Phòng Kỹ Thuật May - IE Engine Core', dept_format)
        
        # B. Ghi tiêu đề báo cáo lớn (Dòng 4)
        worksheet.merge_range('A4:I4', 'BẢNG ĐỊNH MỨC KỸ THUẬT (APPROVED CONSUMPTION)', title_format)
        
        # C. Thiết lập khối meta thông tin mã hàng (Dòng 6 -> Dòng 9)
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

        # D. XÂY DỰNG KHUNG BẢNG LƯỚI ĐỊNH MỨC CHI TIẾT (Dòng 12 trở đi)
        headers = [
            "STT", "Phân loại vật tư (Fabric type)", "Mã vải (Code)", 
            "Khổ (Cuttable)", "Định mức (Cons)", "Co rút dọc (% Warp)", 
            "Co rút ngang (% Weft)", "Hiệu suất sơ đồ", "Trạng thái PLM"
        ]
        
        header_row = 11
        for col_idx, text in enumerate(headers):
            worksheet.write(header_row, col_idx, text, header_format)
            
        # Duyệt mảng cấu trúc bom_rows nạp vào bảng lưới
        current_data_row = 12
        for idx, r in enumerate(bom_data.get("bom_rows", [])):
            worksheet.write(current_data_row, 0, idx + 1, cell_center)
            worksheet.write(current_data_row, 1, r.get("fabric_classification", "MAIN_FABRIC"), cell_left)
            worksheet.write(current_data_row, 2, r.get("fabric_code", "NONE"), cell_center)
            
            # Đọc các giá trị số và áp định dạng đơn vị chuẩn xác
            w_inch = safe_float(r.get("fabric_width_inch"), 58.0)
            cons_yds = safe_float(r.get("calculated_gross_consumption_yds"), 1.25)
            s_warp = safe_float(r.get("shrinkage_warp_pct"), 5.0)
            s_weft = safe_float(r.get("shrinkage_weft_pct"), 10.0)
            
            worksheet.write(current_data_row, 3, w_inch, cell_center)
            worksheet.write(current_data_row, 4, cons_yds, cell_right)
            worksheet.write(current_data_row, 5, f"{s_warp}%", cell_center)
            worksheet.write(current_data_row, 6, f"{s_weft}%", cell_center)
            worksheet.write(current_data_row, 7, r.get("marker_efficiency_pct", "85%"), cell_center)
            
            # Tự động chọn màu cảnh báo theo trạng thái của cổng Quality Gate
            gate_status = r.get("status", "PASS")
            if gate_status == "PASS":
                worksheet.write(current_data_row, 8, "PASS", pass_format)
            elif "HIGH" in gate_status:
                worksheet.write(current_data_row, 8, "WARNING", warn_format)
            else:
                worksheet.write(current_data_row, 8, "CRITICAL", crit_format)
                
            current_data_row += 1
            
        # E. BỔ SUNG KHỐI KÝ TÊN BẢO CHỨNG (Góc dưới bảng tính)
        sign_row = current_data_row + 2
        worksheet.write(sign_row, 1, "Approved", sign_title_format)
        worksheet.write(sign_row, 6, "Issued By Consumption", sign_title_format)
        
        # Tự động co giãn độ rộng thông minh cho toàn bộ các cột chính
        col_widths = [6, 32, 14, 15, 15, 20, 20, 16, 18]
        for i, w in enumerate(col_widths):
            worksheet.set_column(i, i, w)
            
    return buffer.getvalue()


# --- ĐOẠN GRID HIỂN THỊ LÊN MÀN HÌNH CHÍNH CỦA STREAMLIT ---
if st.session_state.bom_data and "bom_rows" in st.session_state.bom_data:
    st.markdown('<div class="cad-card">', unsafe_allow_html=True)
    st.markdown('<div class="cad-header">📊 ĐỊNH MỨC VẬT TƯ THÀNH PHẨM (MẪU BÁO CÁO PHONG PHÚ)</div>', unsafe_allow_html=True)
    
    # Sinh file tệp Excel định dạng chuẩn từ hàm xử lý xlsxwriter phía trên
    excel_file_bytes = export_to_phong_phu_excel(st.session_state.bom_data, st.session_state.get('pdf_name', 'Techpack'))
    
    col_text, col_export = st.columns([7, 3])
    with col_text:
        st.write("Dữ liệu định mức kỹ thuật đã sẵn sàng xuất bản ra file Excel theo form hệ thống:")
    with col_export:
        # Nút nhấn tải file Excel thành phẩm
        st.download_button(
            label="📥 TẢI MẪU BÁO CÁO PHONG PHÚ (.XLSX)",
            data=excel_file_bytes,
            file_name=f"BOM_Approved_Report_{st.session_state.bom_data.get('style_code', 'Output')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
        
    # Render bảng phụ để xem trước trên trình duyệt web
    st.dataframe(pd.DataFrame(st.session_state.bom_data["bom_rows"]), use_container_width=True, hide_index=True)
    st.markdown('</div>', unsafe_allow_html=True)
