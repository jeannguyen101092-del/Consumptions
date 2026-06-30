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
# ĐOẠN 2a1: RẬP HÌNH HỌC & TỰ ĐỘNG BÙ TRỪ CHI TIẾT (V15.4)
# =====================================================================
import re

def parse_geometric_panels_allowance(ai_blueprint: dict, user_chat: str) -> dict:
    """
    Phân đoạn 2a1: Đọc dữ liệu thô từ DXF/Gerber, quét từ khóa thông minh (AI Auto-Dispatcher)
    để tính toán diện tích tịnh và cộng bù sai lệch hình học (Seam, Hem, Pleat) cho từng panel.
    """
    product_type = str(ai_blueprint.get("detected_product_type", "DEFAULT")).upper().strip()
    
    # Kích thước bao rập cơ sở phục vụ dải chu vi phẳng khi không có dữ liệu map
    body_length = safe_float(ai_blueprint.get("extracted_body_length"), 28.0)
    chest_width = safe_float(ai_blueprint.get("extracted_chest_width"), 20.0)
    outseam_length = safe_float(ai_blueprint.get("extracted_outseam_length"), 14.5 if product_type == "JORT" else 40.0)
    hip_width = safe_float(ai_blueprint.get("extracted_hip_width"), 21.0)

    # MA TRẬN HẰNG SỐ BÙ KỸ THUẬT PHÒNG IE MAY PHONG PHÚ
    FACTORY_SEAM_INCH = 0.5       # Biên may chuẩn (chưa nhân đôi sườn)
    FACTORY_HEM_INCH = 1.5        # Cuốn gấu lai sạch (Double-fold hem)
    FACTORY_WAISTBAND_INCH = 2.5  # Chun lưng quần
    FACTORY_PLEAT_INCH = 3.0      # Hệ số bù ly túi hộp

    all_rows = ai_blueprint.get("bom_rows", [])
    parsed_rows = []

    for row in all_rows:
        # Kiểm tra lọc bỏ các nguyên phụ liệu phần cứng (Bypass Hardware/Trim)
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
                
                # 1. Tính toán diện tích hình học gốc bằng Shoelace hoặc công thức bao
                if polygon_points and isinstance(polygon_points, list) and len(polygon_points) >= 3:
                    base_area = calculate_shoelace_polygon_area(polygon_points) * (scale_factor ** 2)
                else:
                    p_len = safe_float(panel.get("piece_length_inch"), 0.0)
                    p_wid = safe_float(panel.get("piece_width_inch"), 0.0)
                    base_area = p_len * p_wid * 0.88
                
                net_panel_area = base_area * p_count
                
                # 2. Thuộc tính chống cộng trùng lặp (Double-Count Protection Flags)
                polygon_include_seam = panel.get("include_seam", False) or str(panel.get("include_seam")).lower() == "true"
                polygon_include_hem = panel.get("include_hem", False) or str(panel.get("include_hem")).lower() == "true"
                
                # 3. Trích xuất nhãn cấu trúc chữ để AI tự phân bổ lệnh cộng thêm
                p_name = str(panel.get("panel_name", "")).upper().strip()
                p_type_code = str(panel.get("panel_type", "")).upper().strip()
                
                has_seam = panel.get("seam_allowance", False) if str(panel.get("seam_allowance")).lower() == "false" else True

                # AI Auto-Dispatcher: Quét định vị đoạn Lai / Gấu / Ong quần
                hem_val = safe_float(panel.get("hem"), 0.0)
                if hem_val == 0.0 and not polygon_include_hem:
                    if any(k in p_name or k in p_type_code for k in ["LAI", "GAU", "HEM", "BOTTOM", "CUFF", "ONG_QUAN", "CHAN_VAY"]):
                        hem_val = 1.0

                # AI Auto-Dispatcher: Quét định vị cụm Xếp Ly / Túi hộp Cargo
                pleat_val = safe_float(panel.get("pleat"), 0.0)
                if pleat_val == 0.0:
                    if any(k in p_name or k in p_type_code for k in ["PLEAT", "XEP_LY", "LY_HOP", "CARGO", "POCKET", "TUI_DAT", "TUI_HOP"]):
                        pleat_val = 1.0

                # Đồng bộ chiều dài/rộng bao mặc định theo sản phẩm may mặc
                eval_len = safe_float(panel.get("piece_length_inch"), outseam_length if product_type in ["PANT", "CARGO_PANT", "CAPRI_PANT", "JORT"] else body_length)
                eval_wid = safe_float(panel.get("piece_width_inch"), hip_width if product_type in ["PANT", "CARGO_PANT", "CAPRI_PANT", "JORT"] else chest_width)

                # --- ĐOẠN SỬA LỖI VẬT LÝ V15.4 ---
                # A. Xử lý bản đồ đường may (Seam Length Map) chính xác từ CAD
                seam_area_addition = 0.0
                if has_seam and not polygon_include_seam:
                    seam_length_map = panel.get("seam_length_map", {})
                    if seam_length_map and isinstance(seam_length_map, dict):
                        # Nhân tổng độ dài các cạnh có may với p_count để chống thiếu hụt
                        actual_seam_length = sum(safe_float(v) for v in seam_length_map.values()) * p_count
                        
                        # Chuyển đổi đơn vị đo lường linh hoạt tránh sai lệch phần mềm CAD ngoại quốc
                        seam_unit = str(panel.get("seam_unit", "INCH")).upper().strip()
                        if seam_unit == "MM":
                            actual_seam_length /= 25.4
                        elif seam_unit == "CM":
                            actual_seam_length /= 2.54
                            
                        seam_area_addition = actual_seam_length * FACTORY_SEAM_INCH
                    else:
                        # Phương án dự phòng (Fallback) chu vi an toàn
                        default_perimeter = ((eval_len * 2) + (eval_wid * 2)) * p_count
                        seam_perimeter = safe_float(panel.get("seam_perimeter_inch"), default_perimeter)
                        seam_area_addition = (seam_perimeter * 0.85) * FACTORY_SEAM_INCH
                        
                net_panel_area += seam_area_addition

                # B. Xử lý tính toán gấu lai áo / lai quần
                if hem_val > 0 and not polygon_include_hem:
                    current_hem = FACTORY_HEM_INCH
                    if any(k in p_name or k in p_type_code for k in ["SLEEVE", "TAY"]):
                        current_hem = 1.0  # Tay áo cuốn nhỏ gọn
                    net_panel_area += (eval_wid * current_hem) * p_count

                # C. Xử lý độ mở xếp ly thực tế (Pleat Logic chuẩn vật lý)
                if pleat_val > 0:
                    pleat_width = safe_float(panel.get("pleat_width"), 1.0)
                    pleat_count = safe_float(panel.get("pleat_count"), 1.0)
                    net_panel_area += (eval_len * pleat_width * pleat_count) * p_count

                row_total_net_area_sq_in += net_panel_area
                panel_debug_logs.append({
                    "panel_name": p_name,
                    "piece_count": p_count,
                    "computed_area_sq_in": round(net_panel_area, 3)
                })

        row["_computed_net_area_sq_in"] = row_total_net_area_sq_in
        row["_panel_debug_logs"] = panel_debug_logs
        parsed_rows.append(row)

    ai_blueprint["bom_rows"] = parsed_rows
    return ai_blueprint
# =====================================================================
# ĐOẠN 2a2: ĐỊNH MỨC SƠ ĐỒ VÀ KIỂM SOÁT CHẤT LƯỢNG PLM (V15.4)
# =====================================================================

def execute_marker_yardage_and_quality_gate(ai_blueprint: dict, user_chat: str) -> dict:
    """
    Phân đoạn 2a2: Gom diện tích, tích hợp hệ số hao hụt, co rút, hiệu suất cắt (Marker)
    để quy đổi ra Yards chiều dài; chạy kiểm tra rủi ro tự động (PLM Limits Quality Gate).
    """
    processed_bom_blueprint = []
    fabric_registry = {}

    # BẢNG MA TRẬN BIÊN ĐỘ GIỚI HẠN TẬP TRUNG KIỂM SOÁT CHẤT LƯỢNG PLM (V15.4 Cập nhật)
    PLM_LIMITS = {
        "JACKET": {"range": (1.65, 2.65), "warn_thresh": 2.5},
        "PANT": {"range": (1.15, 1.75), "warn_thresh": 1.6},
        "CAPRI_PANT": {"range": (1.15, 2.45), "warn_thresh": 2.2},
        "CARGO_PANT": {"range": (1.55, 2.65), "warn_thresh": 2.4}, # Hạ biên độ an toàn theo xưởng wash
        "JORT": {"range": (1.05, 1.35), "warn_thresh": 1.25},
        "DRESS": {"range": (1.45, 3.25), "warn_thresh": 3.0},
        "TSHIRT": {"range": (0.65, 1.35), "warn_thresh": 1.4},
        "SHIRT": {"range": (1.15, 1.95), "warn_thresh": 2.0},
        "DEFAULT": {"range": (1.15, 2.20), "warn_thresh": 2.2}
    }

    # Bóc tách lệnh thay đổi thủ công từ hội thoại phòng cắt
    w_chat, s_l_chat, s_w_chat = None, None, None
    chat_clean = str(user_chat).lower().strip()
    match_w = re.search(r'(?:khổ|kho)\s*(\d+)', chat_clean)
    if match_w: w_chat = float(match_w.group(1))
    match_range = re.search(r'(?:co\s*rút|co\s*rut|co)\s*(\d+)\s*(?:-|–|ngang|\s+)\s*(\d+)', chat_clean)
    if match_range: 
        s_l_chat = float(match_range.group(1))
        s_w_chat = float(match_range.group(2))

    product_type = str(ai_blueprint.get("detected_product_type", "DEFAULT")).upper().strip()
    all_rows = ai_blueprint.get("bom_rows", [])

    # VÒNG 1: Gom nhóm cấu trúc dệt và đồng bộ nhãn đồng nhất (Normalizing Grid)
    for row in all_rows:
        if "_computed_net_area_sq_in" not in row:
            continue  # Bỏ qua phụ liệu phần cứng đã lọc ở Đoạn 2a1

        f_class_raw = row.get("fabric_classification", "MAIN_FABRIC")
        f_class_norm = normalize_fabric_class(f_class_raw)
        
        f_code = str(row.get("fabric_code", "MAIN")).upper().strip().replace(" ", "_")
        f_color = str(row.get("fabric_color", "COLOR")).upper().strip().replace(" ", "_")
        
        # Sửa lỗi đồng bộ chuỗi khoảng trống của V15.2
        grain_rule = str(row.get("fabric_grain_rule", "TWO_WAY")).upper().strip().replace(" ", "_")
        fab_repeat = safe_float(row.get("fabric_repeat_inch"), 0.0)
        
        tmp_id = f"{f_code}_{f_color}_{grain_rule}_{int(fab_repeat)}"
        w_b = w_chat if w_chat is not None else safe_float(row.get("fabric_width_inch"), 56.0)
        s_warp = s_l_chat if s_l_chat is not None else safe_float(row.get("shrinkage_warp_pct"), 5.0)
        s_weft = s_w_chat if s_w_chat is not None else safe_float(row.get("shrinkage_weft_pct"), 10.0)
        
        if tmp_id not in fabric_registry:
            # Phân tách logic xử lý Bo Gân (RIB) và các nhóm vải lót (LINING) đặc thù
            if f_class_norm == "RIB":
                eff_val = 0.95        # RIB chạy sơ đồ ghép dài, hao hụt sơ đồ cực thấp
                consumption_mode = "LINEAR"
            elif f_class_norm == "LINING":
                eff_val = 0.88        # Vải lót túi dễ đi sơ đồ xen kẽ
                consumption_mode = "AREA"
            else:
                eff_val = simulate_marker_efficiency_v14(row.get("panels_catalog", []), f_class_norm, grain_rule, w_b, fab_repeat)
                consumption_mode = "AREA"

            eff_val = max(0.50, min(eff_val, 0.95)) # Giới hạn chốt lỗi chia cho 0 hoặc cao ảo vô lý

            fabric_registry[tmp_id] = {
                "accumulated_area_sq_in": 0.0,
                "cutable_w": max(40.0, w_b - 1.5), 
                "eff": eff_val,
                "shrink_warp_f": 1.0 + (s_warp / 100.0),
                "shrink_weft_f": 1.0 + (s_weft / 100.0),
                "wastage_f": 1.03, # Hao hụt đầu cây, bàn cắt dính cứng 3%
                "consumption_mode": consumption_mode,
                "rows_to_update": [],
                "w_saved": w_b, "s_l_saved": s_warp, "s_w_saved": s_weft, "f_class": f_class_norm
            }
        
        fabric_registry[tmp_id]["accumulated_area_sq_in"] += row["_computed_net_area_sq_in"]
        fabric_registry[tmp_id]["rows_to_update"].append(row)

    # VÒNG 2: Đẩy kết quả quy đổi ra Yards và kích hoạt cổng Quality Gate đối chiếu PLM
    for f_id, fab in fabric_registry.items():
        total_area = fab["accumulated_area_sq_in"]
        cutable_w = fab["cutable_w"]
        eff = fab["eff"]
        
        # Công thức tính định mức tổng thể (Gross Consumption Yardage Engine)
        gross_yds = (total_area / (cutable_w * 36.0)) / eff * fab["shrink_warp_f"] * fab["shrink_weft_f"] * fab["wastage_f"]
        gross_yds = round(gross_yds, 4)

        # Trích xuất cấu hình ma trận giới hạn PLM để kiểm duyệt tự động
        limit_cfg = PLM_LIMITS.get(product_type, PLM_LIMITS["DEFAULT"])
        min_allow, max_allow = limit_cfg["range"]
        warn_th = limit_cfg["warn_thresh"]

        # Cơ chế gác cổng (Quality Gate Dispatcher) dựa trên vải chính (MAIN_FABRIC)
        status_gate = "PASS"
        if fab["f_class"] == "MAIN_FABRIC":
            if gross_yds < min_allow:
                status_gate = "LOW_CONSUMPTION_WARNING"
            elif gross_yds > max_allow:
                status_gate = "CRITICAL_HIGH_CONSUMPTION"
            elif gross_yds >= warn_th:
                status_gate = "HIGH_CONSUMPTION_WARNING"

        # Cập nhật ngược lại từng dòng vật tư trong tập cấu trúc BOM
        for row in fab["rows_to_update"]:
            row["calculated_gross_consumption_yds"] = gross_yds
            row["marker_efficiency_pct"] = f"{round(eff * 100, 2)}%"
            row["status"] = status_gate
            row["consumption_note"] = f"Mode: {fab['consumption_mode']} | CutWidth: {cutable_w}\" | Check: {status_gate}"
            
            # Giữ lại nhật ký gỡ lỗi rập để hiển thị ngoài giao diện
            row["panel_debug_summary"] = row.get("_panel_debug_logs", [])
            
            # Thu dọn sạch các trường đệm vùng nhớ nội bộ
            row.pop("_computed_net_area_sq_in", None)
            row.pop("_panel_debug_logs", None)
            
            processed_bom_blueprint.append(row)

    # Nạp trả lại các dòng vật tư phụ (Hardware/Trim) để tránh làm thiếu hụt cấu trúc file BOM gốc
    for row in all_rows:
        if "calculated_gross_consumption_yds" in row and row not in processed_bom_blueprint:
            processed_bom_blueprint.append(row)

    ai_blueprint["bom_rows"] = processed_bom_blueprint
    return ai_blueprint



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
            log_output = f"{int(data['w_saved'])}\"/{int(data['eff'])}%/{int(data['s_l_saved'])}x{int(data['s_w_saved'])} | Diện tích rập {f_id}: {round(total_area,1)} sq_in. 🔴 VƯỢT TRẦN TIÊU CHUẨN (+{exceed_val} yds)"
        elif total_yds_with_self > cfg["warn_thresh"]:
            row_status = "WARNING"
            log_output = f"{int(data['w_saved'])}\"/{int(data['eff'])}%/{int(data['s_l_saved'])}x{int(data['s_w_saved'])} | Diện tích rập {f_id}: {round(total_area,1)} sq_in. 🟡 CẢNH BÁO PLM"
        else:
            log_output = f"{int(data['w_saved'])}\"/{int(data['eff'])}%/{int(data['s_l_saved'])}x{int(data['s_w_saved'])} | Diện tích rập {f_id}: {round(total_area,1)} sq_in. 🟢 ĐẠT TIÊU CHUẨN MAY"

        rows = data["rows_to_update"]
        if rows:
            # FIX DỨT ĐIỂM TYPEERROR: Trỏ đích danh dòng đầu tiên của nhóm vải Fabric ID nhận tổng số Yards [INDEX]
            main_row = rows[0]
            main_row["calculated_gross_consumption_yds"] = total_yds_with_self
            main_row["status"] = row_status
            main_row["consumption_note"] = "Final Real Gross"
            main_row["reason_or_logs"] = log_output

    ai_blueprint["bom_rows"] = processed_bom_blueprint
    return ai_blueprint


# =====================================================================
# ĐOẠN 3: ĐỔI PHONG CÁCH GIAO DIỆN XÁM SÁNG CÔNG NGHIỆP PLM V15.7
# =====================================================================
import streamlit as st
import json
import re

st.set_page_config(page_title="AI CAD Fabric Consumption Engine", layout="wide")

# CSS Thay đổi màu sắc chủ đạo: Nền sáng xám nhạt, Chữ tối, Thẻ trắng tinh tế
st.markdown("""
    <style>
    /* Nền ứng dụng xám sáng, chữ tối màu rõ nét */
    .stApp { background-color: #f4f6f9; color: #2d3748; }
    
    /* Thanh biên màu xám xanh nhã nhặn */
    [data-testid="stSidebar"] { background-color: #e2e8f0; border-right: 1px solid #cbd5e1; }
    [data-testid="stSidebar"] .stMarkdown { color: #334155; }
    
    /* Thẻ Card màu trắng bo góc, đổ bóng nhẹ kiểu giao diện ERP cao cấp */
    .cad-card {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 20px;
        margin-bottom: 16px;
        box-shadow: 0 4px 10px rgba(0, 0, 0, 0.05);
    }
    
    /* Tiêu đề cụm chức năng màu Xanh Dương Kỹ Thuật */
    .cad-header {
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        color: #1e40af;
        font-weight: 700;
        border-bottom: 2px solid #3b82f6;
        padding-bottom: 8px;
        margin-bottom: 16px;
        text-transform: uppercase;
        font-size: 14px;
        letter-spacing: 0.5px;
    }
    
    /* Khung Terminal mô phỏng console sáng sủa, bẻ dòng chống tràn */
    .chat-box {
        background-color: #f8fafc;
        border-radius: 6px;
        padding: 14px;
        height: 280px;
        overflow-y: auto;
        font-family: 'Courier New', Courier, monospace;
        font-size: 13px;
        font-weight: 600;
        border: 1px solid #cbd5e1;
        white-space: pre-wrap;       
        word-wrap: break-word;       
        word-break: break-all;
    }
    </style>
""", unsafe_allow_html=True)

if "bom_data" not in st.session_state: st.session_state.bom_data = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = [{"role": "assistant", "content": "[SYSTEM READY] V15.7 Engine initialized in Industrial Light Mode."}]

# --- SIDEBAR CONTROL PANEL ---
with st.sidebar:
    st.markdown('<div class="cad-header">⚙️ ENGINE CONTROLS</div>', unsafe_allow_html=True)
    st.info("💡 **Hạn ngạch Google:** Để tránh vấp lỗi gián đoạn 429 Quota Exceeded khi phân rã rập liên tục, hãy cân nhắc nâng cấp tài khoản hoặc sử dụng API Key có định mức cao hơn.")
    
    if st.button("🗑️ CLEAR SYSTEM MEMORY", use_container_width=True, type="secondary"):
        st.session_state.bom_data = None
        st.session_state.pdf_bytes = None
        st.session_state.pdf_name = None
        st.session_state.chat_history = [{"role": "assistant", "content": "[SYSTEM] Session cache purged."}]
        st.rerun()

# --- MAIN DASHBOARD INTERFACE ---
st.title("🏭 AI CAD Fabric Consumption Engine")
st.caption("PLM-Integrated Pattern Discovery & Marker Analytics • Version 15.7")

# Cấu trúc lưới hai cột đối xứng sạch sẽ
col_left, col_right = st.columns(2)

with col_left:
    # KHỐI 1: UPLOAD FILE TECHPACK
    st.markdown('<div class="cad-card">', unsafe_allow_html=True)
    st.markdown('<div class="cad-header">📥 FILE INGESTION (PDF/TECHPACK)</div>', unsafe_allow_html=True)
    uploaded_file = st.file_uploader("Upload Spec", type=["pdf"], key="v157_uploader", label_visibility="collapsed")
    if uploaded_file is not None:
        st.session_state.pdf_bytes = uploaded_file.read()
        st.session_state.pdf_name = uploaded_file.name
    st.markdown('</div>', unsafe_allow_html=True)

    # KHỐI 2: TERMINAL NHẬT KÝ HỆ THỐNG
    st.markdown('<div class="cad-card">', unsafe_allow_html=True)
    st.markdown('<div class="cad-header">💻 CAD LIVE LOG CONSOLE</div>', unsafe_allow_html=True)
    
    chat_html = '<div class="chat-box">'
    for chat in st.session_state.get("chat_history", []):
        # Đổi màu chữ tối tương phản tốt trên nền xám nhạt
        color = '#1e3a8a' if chat["role"] == "assistant" else '#b45309'
        prefix = "🤖 [CAD]: " if chat["role"] == "assistant" else "👤 [USER]: "
        chat_html += f"<div style='margin-bottom:8px; color: {color}'>{prefix}{chat['content']}</div>"
    chat_html += '</div>'
    st.markdown(chat_html, unsafe_allow_html=True)
    
    user_prompt = st.chat_input("Input override commands (e.g., Khổ vải 57 inch)...")
    st.markdown('</div>', unsafe_allow_html=True)

with col_right:
    # KHỐI 3: KHU VỰC ĐIỀU KHIỂN CHẠY MÔ HÌNH
    st.markdown('<div class="cad-card" style="min-height: 450px;">', unsafe_allow_html=True)
    st.markdown('<div class="cad-header">🚀 EXECUTION WORKSPACE</div>', unsafe_allow_html=True)
    
    st.markdown("<p style='color:#475569;'>Ready to process vector coordinate tables and apply structural seam/pleat adjustments.</p>", unsafe_allow_html=True)
    trigger_calc = st.button("RUN GEOMETRIC CALCULATION ENGINE", use_container_width=True, type="primary")
    
    if "pdf_bytes" not in st.session_state:
        st.caption("⚪ SYSTEM STATUS: Directory unmounted. Upload a techpack file to activate.")
    else:
        st.success(f"📎 BUFFERED OBJECT: `{st.session_state.pdf_name}` loaded successfully.")
    st.markdown('</div>', unsafe_allow_html=True)
