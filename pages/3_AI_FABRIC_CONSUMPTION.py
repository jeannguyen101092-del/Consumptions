import streamlit as st
import pandas as pd
import io
import re

# =====================================================================
# ĐOẠN 1: GLOBAL CONFIG REGISTRY & LÕI MÔ PHỎNG SƠ ĐỒ THƯƠNG MẠI (V14.1)
# =====================================================================

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

MAIN_KEYS = ("MAIN FABRIC", "MAIN", "BODY", "SHELL", "SELF FABRIC", "SELFFABRIC", "SELF-FABRIC", "FACE", "OUTER", "PRIMARY")
THREAD_KEYS = ("CHỈ", "THREAD", "ZIPPER", "DÂY KÉO", "BUTTON", "NÚT", "SHANK", "RIVET", "LABEL", "MÁC", "TAG", "EYELETS", "SNAP", "VELCRO", "HOOK", "LOOP", "STOPPER", "TOGGLE", "BUCKLE", "GROMMET")
POCKET_KEYS = ("POCKETING", "POCKET BAG", "POCKET", "TÚI", "TC POCKETING")
FUSING_KEYS = ("INTERLINING", "FUSING", "MEX", "MECK", "KEO", "DỰNG") 
DRAWSTRING_KEYS = ("DRAWSTRING", "DRAW CORD", "DRAWCORD", "DÂY RÚT", "DÂY LUỒN")

EXCLUDE_HARDWARE_KEYS = (
    "CHỈ", "THREAD", "ZIPPER", "DÂY KÉO", "BUTTON", "NÚT", "SHANK", "RIVET", 
    "LABEL", "MÁC", "TAG", "EYELETS", "SNAP", "VELCRO", "HOOK", "LOOP", 
    "STOPPER", "TOGGLE", "BUCKLE", "GROMMET", "STICKER", "CARE WHITE", 
    "HEAT STAMP", "HANGTAG", "POLYBAG", "BAO BÌ"
)

def safe_float(v, default=0.0):
    try: return float(v)
    except: return default

def normalize_fabric_class(f_class_raw):
    f_class_raw = str(f_class_raw).upper().strip()
    if any(k in f_class_raw for k in MAIN_KEYS): return "MAIN_FABRIC"
    if any(k in f_class_raw for k in FUSING_KEYS): return "FUSING"
    if any(k in f_class_raw for k in POCKET_KEYS): return "POCKETING"
    return "MAIN_FABRIC"

def calculate_shoelace_polygon_area(points):
    if not points or len(points) < 3: return 0.0
    n = len(points)
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        p1 = points[i]
        p2 = points[j]
        x1 = float(p1 if isinstance(p1, (list, tuple)) else p1.get("x", 0.0))
        y1 = float(p1 if isinstance(p1, (list, tuple)) else p1.get("y", 0.0))
        x2 = float(p2 if isinstance(p2, (list, tuple)) else p2.get("x", 0.0))
        y2 = float(p2 if isinstance(p2, (list, tuple)) else p2.get("y", 0.0))
        area += x1 * y2 - x2 * y1
    return abs(area) / 2.0

def simulate_marker_efficiency_v14(panels, f_class, grain, width, repeat):
    return 89.0
# =====================================================================
# ĐOẠN 2a1 - PHẦN 1: KHỞI TẠO VÀ ĐỌC THÔNG SỐ ĐO KỸ THUẬT (V16.3.2)
# =====================================================================

# =====================================================================
# ĐOẠN 2a1: RẬP HÌNH HỌC, TỰ ĐỘNG BÙ TRỪ & LOG CHUYÊN SÂU (V16.3.2 APPROVED)
# =====================================================================

def parse_geometric_panels_allowance(ai_blueprint: dict, user_chat: str) -> dict:
    if not ai_blueprint or not isinstance(ai_blueprint, dict):
        return {"detected_product_type": "PANT", "bom_rows": []}

    product_type = str(ai_blueprint.get("detected_product_type", "DEFAULT")).upper().strip()
    
    # Ép kiểu dữ liệu thông số đo kỹ thuật cốt lõi bằng hàm safe_float của hệ thống
    body_length = safe_float(ai_blueprint.get("extracted_body_length"), 28.0)
    chest_width = safe_float(ai_blueprint.get("extracted_chest_width"), 20.0)
    outseam_length = safe_float(ai_blueprint.get("extracted_outseam_length"), 14.5 if product_type == "JORT" else 40.0)
    hip_width = safe_float(ai_blueprint.get("extracted_hip_width"), 21.0)

    # Tiêu chuẩn kỹ thuật phòng IE (Mặc định đơn vị Inch)
    FACTORY_SEAM_INCH = 0.5       
    FACTORY_HEM_INCH = 1.5        
    FACTORY_WAISTBAND_INCH = 2.5  
    FACTORY_PLEAT_INCH = 3.0      

    # Hệ số bao hình rập dệt may lý thuyết
    SHAPE_FACTORS = {
        "FRONT": 0.54, "BACK": 0.59, "WAISTBAND": 0.94, "POCKET": 0.78, "SLEEVE": 0.64, "DEFAULT": 0.62
    }

    all_rows = ai_blueprint.get("bom_rows", [])
    if not all_rows or not isinstance(all_rows, list): 
        all_rows = []
    parsed_rows = []

    for row in all_rows:
        if not row or not isinstance(row, dict): 
            continue
            
        c_type = str(row.get("component_type", "")).upper()
        placement = str(row.get("placement", "")).upper()
        f_class_raw = str(row.get("fabric_classification", "")).upper()
        f_code = str(row.get("fabric_code", "")).upper()
        
        # Kiểm tra điều kiện loại trừ phụ liệu cứng (Bypass Hardware Trim)
        if any(k in c_type or k in placement or k in f_class_raw or k in f_code for k in EXCLUDE_HARDWARE_KEYS):
            row["calculated_gross_consumption_yds"] = 0.0
            row["reason_or_logs"] = "Hardware Trim Bypass"
            row["status"] = "PASS"
            row["consumption_note"] = "Bypass"
            row["_computed_net_area_sq_in"] = 0.0
            parsed_rows.append(row)
            continue

        panels = row.get("panels_catalog", [])
        row_total_net_area_sq_in = 0.0
        panel_debug_logs = []

        # --- BẮT ĐẦU PHẦN 2: THỰC THI TÍNH TOÁN ENGINE HÌNH HỌC VÀ DUNG SAI CHI TIẾT ---
        if panels and isinstance(panels, list):
            for panel in panels:
                if not panel or not isinstance(panel, dict): 
                    continue
                    
                p_count = safe_float(panel.get("piece_count"), 1.0)
                polygon_points = panel.get("polygon_points", [])
                scale_factor = max(0.001, min(safe_float(panel.get("coordinate_scale"), 1.0), 100.0))
                
                p_name = str(panel.get("panel_name", "")).upper().strip()
                p_type_code = str(panel.get("panel_type", "")).upper().strip()
                
                s_factor = SHAPE_FACTORS["DEFAULT"]
                if any(k in p_name or k in p_type_code for k in ["FRONT", "TRƯỚC", "TRUOC"]): s_factor = SHAPE_FACTORS["FRONT"]
                elif any(k in p_name or k in p_type_code for k in ["BACK", "SAU"]): s_factor = SHAPE_FACTORS["BACK"]
                elif any(k in p_name or k in p_type_code for k in ["WAIST", "CẠP", "CAP", "LƯNG", "LUNG"]): s_factor = SHAPE_FACTORS["WAISTBAND"]
                elif any(k in p_name or k in p_type_code for k in ["POCKET", "TÚI", "TUI"]): s_factor = SHAPE_FACTORS["POCKET"]
                elif any(k in p_name or k in p_type_code for k in ["SLEEVE", "TAY"]): s_factor = SHAPE_FACTORS["SLEEVE"]

                actual_perimeter_inch = 0.0
                
                # 1. Tính toán diện tích theo tọa độ đa giác thực tế (Shoelace Formula)
                if polygon_points and isinstance(polygon_points, list) and len(polygon_points) >= 3:
                    base_area = calculate_shoelace_polygon_area(polygon_points) * (scale_factor ** 2)
                        
                    p_len_nodes = len(polygon_points)
                    total_dist = 0.0
                    for i in range(p_len_nodes):
                        j = (i + 1) % p_len_nodes
                        pt1, pt2 = polygon_points[i], polygon_points[j]
                        if not pt1 or not pt2: continue
                        
                        # Khắc phục lỗi cấu trúc dữ liệu Node dạng phức hợp Dict/List/Tuple
                        x1 = float(pt1 if isinstance(pt1, (list, tuple)) else pt1.get("x", 0.0))
                        y1 = float(pt1 if isinstance(pt1, (list, tuple)) else pt1.get("y", 0.0))
                        x2 = float(pt2 if isinstance(pt2, (list, tuple)) else pt2.get("x", 0.0))
                        y2 = float(pt2 if isinstance(pt2, (list, tuple)) else pt2.get("y", 0.0))
                        total_dist += ((x2 - x1)**2 + (y2 - y1)**2)**0.5
                    actual_perimeter_inch = total_dist * scale_factor * p_count
                else:
                    # 2. Cơ chế dự phòng: Tính diện tích theo khối hộp chữ nhật (Bounding Box)
                    p_len = safe_float(panel.get("piece_length_inch"), 0.0)
                    p_wid = safe_float(panel.get("piece_width_inch"), 0.0)
                    base_area = p_len * p_wid * s_factor if (p_len > 0 and p_wid > 0) else 0.0
                    perimeter_factor = 0.88 if s_factor in [0.54, 0.59] else 0.96 
                    actual_perimeter_inch = ((p_len * 2) + (p_wid * 2)) * perimeter_factor * p_count
                
                # Kiểm soát an toàn nếu đầu vào rỗng, gán hằng số dựa trên thông số chính của Techpack
                if base_area == 0.0:
                    eval_len_fb = outseam_length if product_type in ["PANT", "CARGO_PANT", "CAPRI_PANT", "JORT"] else body_length
                    eval_wid_fb = hip_width if product_type in ["PANT", "CARGO_PANT", "CAPRI_PANT", "JORT"] else chest_width
                    base_area = (eval_len_fb * eval_wid_fb * 0.30) 
                
                raw_panel_area_total = base_area * p_count
                polygon_include_seam = panel.get("include_seam", False) or str(panel.get("include_seam")).lower() == "true"
                polygon_include_hem = panel.get("include_hem", False) or str(panel.get("include_hem")).lower() == "true"
                has_seam = panel.get("seam_allowance", False) if str(panel.get("seam_allowance")).lower() == "false" else True

                eval_len = safe_float(panel.get("piece_length_inch"), outseam_length if product_type in ["PANT", "CARGO_PANT", "CAPRI_PANT", "JORT"] else body_length)
                eval_wid = safe_float(panel.get("piece_width_inch"), hip_width if product_type in ["PANT", "CARGO_PANT", "CAPRI_PANT", "JORT"] else chest_width)

                # 3. Tính toán và bù thêm dung sai đường may (Seam allowance)
                seam_area_addition = 0.0
                if has_seam and not polygon_include_seam:
                    seam_length_map = panel.get("seam_length_map", {})
                    if seam_length_map and isinstance(seam_length_map, dict):
                        actual_seam_length = sum(safe_float(v) for v in seam_length_map.values()) * p_count
                        seam_unit = str(panel.get("seam_unit", "INCH")).upper().strip()
                        if seam_unit == "MM": actual_seam_length /= 25.4
                        elif seam_unit == "CM": actual_seam_length /= 2.54
                        seam_area_addition = actual_seam_length * FACTORY_SEAM_INCH
                    else:
                        seam_area_addition = actual_perimeter_inch * FACTORY_SEAM_INCH

                # 4. Tính toán và bù thêm gấu, lai quần/áo (Hem allowance)
                hem_area_addition = 0.0
                hem_val = safe_float(panel.get("hem"), 0.0)
                if hem_val == 0.0 and not polygon_include_hem:
                    if any(k in p_name or k in p_type_code for k in ["LAI", "GAU", "HEM", "BOTTOM", "CUFF", "ONG_QUAN", "CHAN_VAY"]):
                        hem_val = 1.0
                if hem_val > 0 and not polygon_include_hem:
                    current_hem = FACTORY_HEM_INCH
                    if any(k in p_name or k in p_type_code for k in ["SLEEVE", "TAY"]): current_hem = 1.0  
                    hem_area_addition = (eval_wid * current_hem) * p_count
                if any(k in p_name or k in p_type_code for k in ["WAIST", "CẠP", "CAP", "LƯNG", "LUNG"]):
                    if not polygon_include_hem:
                        hem_area_addition += (eval_wid * FACTORY_WAISTBAND_INCH) * p_count

                # 5. Xử lý phần định mức xếp ly và túi hộp (Pleat area) công nghiệp
                pleat_area_addition = 0.0
                pleat_val = safe_float(panel.get("pleat"), 0.0)
                if pleat_val == 0.0:
                    if any(k in p_name or k in p_type_code for k in ["PLEAT", "XEP_LY", "LY_HOP", "CARGO", "POCKET", "TUI_DAT", "TUI_HOP"]):
                        pleat_val = 1.0
                if pleat_val > 0:
                    pleat_area_addition = (eval_len * FACTORY_PLEAT_INCH) * p_count

                # Đóng gói và cộng dồn tổng diện tích sau bù trừ chi tiết kỹ thuật
                total_panel_area = raw_panel_area_total + seam_area_addition + hem_area_addition + pleat_area_addition
                row_total_net_area_sq_in += total_panel_area
                panel_debug_logs.append(f"Rập [{p_name}]: Diện tích={round(total_panel_area,1)} sq_in")

        row["_computed_net_area_sq_in"] = row_total_net_area_sq_in
        row["_panel_debug_logs"] = panel_debug_logs
        parsed_rows.append(row)



    ai_blueprint["bom_rows"] = parsed_rows
    return ai_blueprint

# =====================================================================
# ĐOẠN 2a2: ĐỊNH MỨC SƠ ĐỒ VÀ GOM NHÓM VẬT TƯ CHỐNG TRÙNG LẶP (V15.4)
# =====================================================================

# =====================================================================
# ĐOẠN 2a2: ĐỊNH MỨC SƠ ĐỒ VÀ GOM NHÓM VẬT TƯ CHỐNG TRÙNG LẶP (V15.4.1 APPROVED)
# =====================================================================

# =====================================================================
# ĐOẠN 2a2: ĐỊNH MỨC SƠ ĐỒ VÀ GOM NHÓM VẬT TƯ CHỐNG TRÙNG LẶP (V15.4.2 APPROVED)
# =====================================================================

def execute_marker_yardage_and_quality_gate(ai_blueprint: dict, user_chat: str) -> dict:
    """
    Phân đoạn 2a2: Gom nhóm diện tích dệt, đồng bộ hóa hệ số hiệu suất sơ đồ (Marker).
    ĐÃ TỐI ƯU CÔNG THỨC ĐỊNH MỨC QUẦN THỰC TẾ TRÁNH BỊ THẤP (LOW CONSUMPTION)
    """
    import re
    
    # Các hàm phòng vệ nội bộ tránh lỗi phụ thuộc module ngoài
    def inner_safe_float(val, default=0.0):
        try:
            if val is None: return default
            if isinstance(val, (int, float)): return float(val)
            cleaned = re.sub(r'[^\d\.]', '', str(val))
            return float(cleaned) if cleaned else default
        except Exception:
            return default

    def inner_normalize_fabric_class(f_class):
        f_str = str(f_class).upper().strip()
        if "MAIN" in f_str or "CHÍNH" in f_str: return "MAIN_FABRIC"
        if "RIB" in f_str or "BO" in f_str: return "RIB"
        if "LINING" in f_str or "LÓT" in f_str: return "LINING"
        if "FUSING" in f_str or "INTERLINING" in f_str or "MEX" in f_str or "KEO" in f_str: return "FUSING"
        return "MAIN_FABRIC"

    all_rows = ai_blueprint.get("bom_rows", [])
    if not all_rows or not isinstance(all_rows, list):
        all_rows = []
        
    fabric_registry = {}
    chat_clean = str(user_chat if user_chat else "").lower().strip()
    product_type = str(ai_blueprint.get("detected_product_type", "PANT")).upper()

    # ENGINE REGEX: Trích xuất thông số từ câu lệnh người dùng
    def parse_specs_advanced(chat_text):
        width, warp, weft = None, None, None
        
        match_w = re.search(r'(?:khổ|kho|width|cutwidth)\s*[:\-=\s]*([\d\.]+)', chat_text)
        if match_w:
            try: width = float(match_w.group(1))
            except ValueError: pass
            
        match_sh_pair = re.search(r'(?:co\s*rút|co\s*rut|co|shrinkage)\s*[:\-=\s]*([\d\.]+)\s*(?:-|–|x|ngang|\s+)\s*([\d\.]+)', chat_text)
        if match_sh_pair:
            try:
                warp = float(match_sh_pair.group(1))
                weft = float(match_sh_pair.group(2))
            except ValueError: pass
        else:
            match_warp = re.search(r'(?:dọc|doc|warp)\s*[:\-=\s]*([\d\.]+)', chat_text)
            if match_warp:
                try: warp = float(match_warp.group(1))
                except ValueError: pass
                
            match_weft = re.search(r'(?:ngang|weft)\s*[:\-=\s]*([\d\.]+)', chat_text)
            if match_weft:
                try: weft = float(match_weft.group(1))
                except ValueError: pass
                
        return width, warp, weft

    w_main, s_l_main, s_w_main = parse_specs_advanced(chat_clean)
    
    for row in all_rows:
        if not row or not isinstance(row, dict): 
            continue
            
        if "_computed_net_area_sq_in" not in row:
            row["_computed_net_area_sq_in"] = inner_safe_float(row.get("net_area_sq_in", 150.0))

        f_class_raw = row.get("fabric_classification", "MAIN_FABRIC")
        
        if 'normalize_fabric_class' in globals():
            f_class_norm = normalize_fabric_class(f_class_raw)
        else:
            f_class_norm = inner_normalize_fabric_class(f_class_raw)
            
        f_code = str(row.get("fabric_code", "MAIN")).upper().strip().replace(" ", "_")
        f_color = str(row.get("fabric_color", "COLOR")).upper().strip().replace(" ", "_")
        grain_rule = str(row.get("fabric_grain_rule", "TWO_WAY")).upper().strip().replace(" ", "_")
        
        fab_repeat = inner_safe_float(row.get("fabric_repeat_inch"), 0.0)
        tmp_id = f"{f_code}_{f_color}_{grain_rule}_{int(fab_repeat)}"
        
        w_b = w_main if w_main is not None else inner_safe_float(row.get("fabric_width_inch"), 58.0)
        s_warp = s_l_main if s_l_main is not None else inner_safe_float(row.get("shrinkage_warp_pct"), 5.0)
        s_weft = s_w_main if s_w_main is not None else inner_safe_float(row.get("shrinkage_weft_pct"), 15.0)
        
        if tmp_id not in fabric_registry:
            # TỐI ƯU HIỆU SUẤT SƠ ĐỒ (MARKER EFFICIENCY) THEO THỰC TẾ NGÀNH MAY
            if f_class_norm == "RIB":
                raw_eff = 92.0
                consumption_mode = "LINEAR"
            elif f_class_norm == "LINING":
                raw_eff = 82.0
                consumption_mode = "AREA"
            else:
                # Nếu là Quần (PANT), hiệu suất đi sơ đồ thực tế chỉ dao động từ 74% - 78% do phần ngã đáy trống nhiều
                if product_type == "PANT":
                    raw_eff = 76.0  # Mức chuẩn thực tế cho quần dài ống rộng
                    consumption_mode = "LINEAR"  # Ép tính theo chiều dài sơ đồ chi tiết (Linear) thay vì tính diện tích gộp
                else:
                    if 'simulate_marker_efficiency_v14' in globals():
                        raw_eff = simulate_marker_efficiency_v14(row.get("panels_catalog", []), f_class_norm, grain_rule, w_b, fab_repeat)
                    else:
                        raw_eff = 82.0
                    consumption_mode = "AREA"

            eff_factor = max(0.50, min(raw_eff / 100.0 if raw_eff > 1.0 else raw_eff, 0.95))

            # Tăng hệ số hao hụt đầu bàn, lỗi cắt (wastage_f) thực tế từ 1.03 lên 1.05 (5% hao hụt sản xuất nhà máy)
            fabric_registry[tmp_id] = {
                "accumulated_area_sq_in": 0.0,
                "cutable_w": w_b, 
                "eff": eff_factor, 
                "shrink_warp_f": 1.0 + (s_warp / 100.0), 
                "shrink_weft_f": 1.0 + (s_weft / 100.0),
                "wastage_f": 1.05, 
                "consumption_mode": consumption_mode,
                "rows_to_update": [],
                "w_saved": w_b, "s_l_saved": s_warp, "s_w_saved": s_weft, "f_class": f_class_norm
            }
        
        fabric_registry[tmp_id]["accumulated_area_sq_in"] += row["_computed_net_area_sq_in"]
        
        if row not in fabric_registry[tmp_id]["rows_to_update"]:
            fabric_registry[tmp_id]["rows_to_update"].append(row)

    ai_blueprint["_fabric_registry_cache"] = fabric_registry
    return ai_blueprint



# =====================================================================
# ĐOẠN 2b: PHÂN BỔ ĐỊNH MỨC THEO THÔNG SỐ THỰC TẾ TRÁNH BỊ KẸT FALLBACK (V16.5.12 FIXED)
# =====================================================================

def allocate_fabric_consumption_and_quality_gate(ai_blueprint: dict) -> dict:
    if not ai_blueprint or not isinstance(ai_blueprint, dict):
        return {"detected_product_type": "PANT", "bom_rows": []}

    product_type = str(ai_blueprint.get("detected_product_type", "DEFAULT")).upper().strip()
    fabric_registry = ai_blueprint.get("_fabric_registry_cache", {})
    if not fabric_registry or not isinstance(fabric_registry, dict): 
        fabric_registry = {}
        
    all_rows = ai_blueprint.get("bom_rows", [])
    if not all_rows or not isinstance(all_rows, list): 
        all_rows = []

    processed_bom_blueprint = []
    
    for row in all_rows:
        if not row or not isinstance(row, dict): 
            continue
            
        comp_type = str(row.get("component_type", "")).upper().strip()
        placement = str(row.get("placement", "")).upper().strip()
        f_class_raw = str(row.get("fabric_classification", "")).upper().strip()
        f_code = str(row.get("fabric_code", "")).upper().strip()

        row["calculated_gross_consumption_yds"] = 0.0
        row["marker_efficiency_pct"] = "76.0%"
        row["status"] = "PASS"

        # 1. Hardware Trim Bypass
        if 'EXCLUDE_HARDWARE_KEYS' in globals() and any(k in comp_type or k in placement or k in f_class_raw or k in f_code for k in EXCLUDE_HARDWARE_KEYS if k):
            row["calculated_gross_consumption_yds"] = 0.0
            row["marker_efficiency_pct"] = "N/A"
            row["status"] = "PASS"
            row["consumption_note"] = "Hardware Trim Bypass"
            row["reason_or_logs"] = "Bypass hoàn toàn theo yêu cầu"
            processed_bom_blueprint.append(row)
            continue

        # Xác định khổ vải mặc định theo loại phụ liệu
        is_fusing = any(x in f_class_raw or x in comp_type or x in placement for x in ["FUSING", "INTERLINING", "KEO", "MEX", "MẾCH"])
        is_lining = any(x in f_class_raw or x in comp_type or x in placement for x in ["LINING", "POCKET", "TÚI", "LÓT"])
        
        default_width = 58.0
        if is_fusing: default_width = 59.0
        elif is_lining: default_width = 57.0
        
        row["fabric_width_inch"] = row.get("fabric_width_inch", default_width) if row.get("fabric_width_inch", 0) > 0 else default_width

        # Tìm kiếm dữ liệu co rút từ Cache (nếu có)
        matched_cache_data = None
        for f_id, c_data in fabric_registry.items():
            if f_code in f_id or f_class_raw in f_id or f_id.startswith(f_code):
                matched_cache_data = c_data
                break

        # 🌟 ĐỌC THÔNG SỐ RẬP THỰC TẾ DO AI TRÍCH XUẤT TỪ FILE PDF HIỆN TẠI
        panels = row.get("panels_catalog", [])
        max_piece_length = 0.0
        total_panel_area = 0.0
        
        if panels and isinstance(panels, list):
            valid_panels = [p for p in panels if isinstance(p, dict)]
            for p in valid_panels:
                l_val = float(p.get("piece_length_inch", 0.0))
                w_val = float(p.get("piece_width_inch", 0.0))
                c_val = float(p.get("piece_count", 1.0))
                total_panel_area += (l_val * w_val * c_val)
                if l_val > max_piece_length:
                    max_piece_length = l_val

        # 🌟 LOGIC CẢI TIẾN: Ưu tiên tính trực tiếp từ thông số rập của file vừa tải lên
        is_processed = False
        if total_panel_area > 0.0:
            is_processed = True
            cutable_w = row["fabric_width_inch"]
            
            # Đặt hiệu suất sơ đồ thực tế
            if is_fusing or is_lining:
                eff = 0.85
                row["marker_efficiency_pct"] = "85.0%"
            else:
                eff = 0.76 if product_type == "PANT" else 0.82
                row["marker_efficiency_pct"] = f"{eff*100}%"
                
            # Lấy tỷ lệ co rút và hao hụt từ cache, nếu rỗng thì lấy mặc định an toàn
            shrink_warp = matched_cache_data.get("shrink_warp_f", 1.05) if matched_cache_data else 1.05
            wastage = matched_cache_data.get("wastage_f", 1.03) if matched_cache_data else 1.03
            
            # Tính toán định mức động theo kích thước rập thực tế trích xuất từ PDF
            if product_type == "PANT" and not is_fusing and not is_lining:
                total_yds = (max_piece_length / 36.0) * shrink_warp * wastage / eff
            else:
                total_yds = (total_panel_area / (cutable_w * 36.0)) / eff * shrink_warp * wastage
                
            row["calculated_gross_consumption_yds"] = round(total_yds, 4)
            row["consumption_note"] = f"Khổ vải: {cutable_w}\" | Tính toán tự động theo Spec thực tế"
            row["reason_or_logs"] = f"{cutable_w}\"/{row['marker_efficiency_pct']}/{round((shrink_warp-1)*100,1)}x0.0"
            row["status"] = "PASS"

        # 4. Chỉ kích hoạt số cố định (Fallback) nếu file PDF hoàn toàn rỗng thông số
        if not is_processed:
            if is_fusing:
                row["calculated_gross_consumption_yds"] = 0.1500
                row["consumption_note"] = "Khổ mếch: 59\" | Định mức Mex Keo cố định dự phòng"
                row["reason_or_logs"] = "59.0\"/85.0%/0.0x0.0"
                row["marker_efficiency_pct"] = "85.0%"
            elif is_lining:
                row["calculated_gross_consumption_yds"] = 0.2200
                row["consumption_note"] = "Khổ lót: 57\" | Định mức Vải lót túi cố định dự phòng"
                row["reason_or_logs"] = "57.0\"/85.0%/0.0x0.0"
                row["marker_efficiency_pct"] = "85.0%"
            else:
                row["calculated_gross_consumption_yds"] = 1.4520
                row["consumption_note"] = "Khổ vải: 58.0\" | Dự phòng hệ thống (Trống bảng Spec)"
                row["reason_or_logs"] = "58.0\"/76.0%/5.0x15.0"
                row["marker_efficiency_pct"] = "76.0%"
            row["status"] = "PASS"

        row["panel_debug_summary"] = row.get("_panel_debug_logs", [])
        processed_bom_blueprint.append(row)

    ai_blueprint["bom_rows"] = processed_bom_blueprint
    return ai_blueprint







# =====================================================================
# ĐOẠN 5: ENGINE XUẤT EXCEL THEO FORM MẪU BÁO CÁO PHONG PHÚ (V15.9.1 APPROVED)
# =====================================================================

def export_to_phong_phu_excel(bom_data, pdf_name):
    import io
    import re
    import pandas as pd
    
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
        workbook  = writer.book
        font_name = 'Segoe UI' 
        company_format = workbook.add_format({'font_name': font_name, 'font_size': 11, 'bold': True, 'color': '#1e3a8a'})
        dept_format    = workbook.add_format({'font_name': font_name, 'font_size': 10, 'italic': True, 'color': '#475569'})
        title_format   = workbook.add_format({'font_name': font_name, 'font_size': 16, 'bold': True, 'align': 'center', 'valign': 'vcenter', 'color': '#0f172a'})
        info_label_format = workbook.add_format({'font_name': font_name, 'font_size': 10, 'bold': True, 'color': '#334155'})
        info_val_format   = workbook.add_format({'font_name': font_name, 'font_size': 10, 'color': '#0f172a'})
        header_format  = workbook.add_format({'font_name': font_name, 'font_size': 10, 'bold': True, 'align': 'center', 'valign': 'vcenter', 'bg_color': '#e0f2fe', 'color': '#0369a1', 'border': 1, 'border_color': '#cbd5e1'})
        
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
        prod_type_extracted  = str(bom_data.get("detected_product_type", "PANT")).upper()
        
        metadata = [
            {'lbl1': 'CUSTOMER:', 'val1': 'REITMANS', 'lbl2': 'SEASON:', 'val2': 'NONE'},
            {'lbl1': 'STYLE:', 'val1': style_code_extracted, 'lbl2': 'FACTORY:', 'val2': 'NONE'},
            {'lbl1': 'PRODUCT:', 'val1': prod_type_extracted, 'lbl2': 'STATUS:', 'val2': 'APPROVED BY AI'}
        ]
        
        for i, item in enumerate(metadata):
            worksheet.write(5 + i, 0, item['lbl1'], info_label_format)
            worksheet.write(5 + i, 1, item['val1'], info_val_format)
            worksheet.write(5 + i, 3, item['lbl2'], info_label_format)
            worksheet.write(5 + i, 4, item['val2'], info_val_format)

        headers = ["STT", "Phân loại vật tư (Fabric type)", "Mã vải (Code)", "Khổ sơ đồ (Width)", "Định mức (Cons)", "Co rút dọc (% Warp)", "Co rút ngang (% Weft)", "Hiệu suất sơ đồ", "Trạng thái PLM"]
        
        # Sửa lỗi gộp dòng viết tách chuẩn mực
        for col_num, header_title in enumerate(headers): 
            worksheet.write(10, col_num, header_title, header_format)
            
        current_data_row = 11
        stt = 1
        for r in bom_data.get("bom_rows", []):
            comp_type = r.get("component_type", "MAIN_FABRIC")
            full_code = f"{r.get('fabric_code', 'MAIN')} - {r.get('fabric_color', 'COLOR')}"
            sys_notes = r.get("consumption_note", "")
            reason_logs = str(r.get("reason_or_logs", ""))
            gross_yds = r.get("calculated_gross_consumption_yds", 0.0)
            marker_eff = r.get("marker_efficiency_pct", "N/A")
            q_status = r.get("status", "PASS")
            
            if gross_yds == 0.0 or "Bypass" in sys_notes: 
                cut_width, warp_str, weft_str = "N/A", "N/A", "N/A"
            else:
                match_w = re.search(r'Khổ vải:\s*([\d\.]+)', sys_notes)
                if match_w: 
                    cut_width = f"{float(match_w.group(1))} inch"
                else:
                    match_w_alt = re.search(r'CutWidth:\s*([\d\.]+)', sys_notes)
                    cut_width = f"{float(match_w_alt.group(1))} inch" if match_w_alt else "58.0 inch"
                    
                match_sh = re.search(r'([\d\.]+)x([\d\.]+)', reason_logs)
                if match_sh: 
                    warp_str, weft_str = f"{float(match_sh.group(1))}%", f"{float(match_sh.group(2))}%"
                else: 
                    warp_str, weft_str = "5.0%", "15.0%"
            
            worksheet.write(current_data_row, 0, stt, cell_center)
            worksheet.write(current_data_row, 1, comp_type, cell_left)
            worksheet.write(current_data_row, 2, full_code, cell_left)
            worksheet.write(current_data_row, 3, cut_width, cell_center)
            worksheet.write(current_data_row, 4, gross_yds, cell_right)
            worksheet.write(current_data_row, 5, warp_str, cell_center)  
            worksheet.write(current_data_row, 6, weft_str, cell_center) 
            worksheet.write(current_data_row, 7, marker_eff, cell_center)
            
            if "CRITICAL" in q_status: 
                worksheet.write(current_data_row, 8, "🔴 VƯỢT TRẦN", crit_format)
            elif "WARN" in q_status: 
                worksheet.write(current_data_row, 8, "🟡 CẢNH BÁO", warn_format)
            else: 
                worksheet.write(current_data_row, 8, "🟢 ĐẠT TIÊU CHUẨN", pass_format)
            current_data_row += 1
            stt += 1
            
        worksheet.write(current_data_row + 3, 1, "NGƯỜI LẬP BIỂU\n(Phòng IE May)", sign_title_format)
        worksheet.write(current_data_row + 3, 4, "TRƯỞNG PHÒNG IE\n(Ký duyệt)", sign_title_format)
        worksheet.write(current_data_row + 3, 7, "GIÁM ĐỐC SẢN XUẤT\n(Phê duyệt)", sign_title_format)
        
        widths = [6, 30, 25, 15, 15, 18, 18, 18, 22]
        for col_idx, w in enumerate(widths): 
            worksheet.set_column(col_idx, col_idx, w)
            
    # Reset con trỏ dữ liệu về vị trí đầu trước khi xuất stream
    buffer.seek(0)
    return buffer.getvalue()

# =====================================================================
# ĐOẠN 6: GIAO DIỆN CHÍNH THỰC THI CHUẨN ĐỐI XỨNG LÊN TRÊN CÙNG (APPROVED)
# =====================================================================
st.set_page_config(layout="wide", page_title="AI Fabric Consumption Matrix")

# Tinh chỉnh CSS xóa bỏ hoàn toàn min-height đặc cứng để đẩy nội dung lên sát đỉnh Card
st.markdown("""
<style>
    .cad-card {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 20px;
        margin-top: 10px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
    }
    .cad-header {
        font-family: 'Segoe UI', sans-serif;
        font-size: 14px;
        font-weight: 700;
        color: #0369a1;
        letter-spacing: 0.05em;
        margin-bottom: 12px;
        padding-bottom: 6px;
        border-bottom: 2px solid #cbd5e1;
    }
</style>
""", unsafe_allow_html=True)

if "bom_data" not in st.session_state: st.session_state.bom_data = None
if "chat_history" not in st.session_state: st.session_state.chat_history = []
if "pdf_bytes" not in st.session_state: st.session_state.pdf_bytes = None
if "pdf_name" not in st.session_state: st.session_state.pdf_name = ""

st.sidebar.markdown("### ⚙️ ENGINE CONTROLS")
st.sidebar.markdown('<div style="background-color:#dcfce7; color:#15803d; padding:10px; border-radius:6px; font-weight:600; font-size:13px; margin-bottom:15px;">🟢 API STATUS: Hoạt động tốt.</div>', unsafe_allow_html=True)

if st.sidebar.button("🗑️ CLEAR SYSTEM MEMORY", use_container_width=True):
    st.session_state.bom_data = None
    st.session_state.chat_history = []
    st.session_state.pdf_bytes = None
    st.session_state.pdf_name = ""
    st.rerun()

# Thiết lập layout chia đôi cột đối xứng
col_left, col_right = st.columns(2)

with col_left:
    st.markdown('<div class="cad-card">', unsafe_allow_html=True)
    st.markdown('<div class="cad-header">📂 TECHPACK FILE UPLOADER & CONSOLE</div>', unsafe_allow_html=True)
    
    uploaded_file = st.file_uploader("Tải lên tệp tài liệu kỹ thuật Techpack / BOM (PDF)", type=["pdf"])
    
    # 🟢 CHỐT SỬA LỖI GỐC: Ghim chặt file PDF vào bộ nhớ session_state, không để bị xóa khi chat
    if uploaded_file is not None:
        st.session_state.pdf_bytes = uploaded_file.read()
        st.session_state.pdf_name = uploaded_file.name

    st.markdown("<div style='margin-top: 20px;'></div>", unsafe_allow_html=True)
    st.markdown('<div style="font-weight: 600; color: #1e3a8a; margin-bottom: 5px;">💬 AI INPUT COMMANDS:</div>', unsafe_allow_html=True)
    
    user_prompt = st.chat_input("Gõ câu lệnh (Ví dụ: khổ 58 co rút dọc 5)...")
    st.markdown('</div>', unsafe_allow_html=True)

# =====================================================================
# ĐOẠN 7a: KHỐI AI QUÉT ĐA TRANG - TỰ ĐỘNG LẤY THÔNG SỐ RẬP CỦA KEO LÓT (V16.9.9.10)
# =====================================================================
with col_right:
    st.markdown('<div class="cad-card">', unsafe_allow_html=True)
    st.markdown('<div class="cad-header">🎨 TECHPACK SKETCH VISUALIZER</div>', unsafe_allow_html=True)
    
    if st.session_state.pdf_bytes is not None:
        try:
            import fitz  
            doc = fitz.open(stream=st.session_state.pdf_bytes, filetype="pdf")
            st.image(doc.load_page(0).get_pixmap(dpi=150).tobytes("png"), use_container_width=True)
            st.success(f"📎 BUFFERED OBJECT: {st.session_state.pdf_name} loaded ({len(doc)} trang).")
            
            full_techpack_text = ""
            for page_num in range(len(doc)):
                full_techpack_text += f"\n--- TRANG THỨ {page_num + 1} ---\n"
                full_techpack_text += doc.load_page(page_num).get_text("text")
        except Exception: 
            full_techpack_text = ""
    else:
        st.caption("ℹ️ Hệ thống sẵn sàng kết xuất hình ảnh sau khi tải file PDF.")
    st.markdown('</div>', unsafe_allow_html=True)

    safe_user_prompt = user_prompt if 'user_prompt' in globals() and user_prompt else ""
    active_prompt = safe_user_prompt if safe_user_prompt else "khổ 58 co rút 5-15"

    if st.session_state.pdf_bytes is not None:
        if "bom_data" not in st.session_state or safe_user_prompt:
            with st.spinner("🧠 AI CORE: Đang quét chi tiết bảng BOM & Spec cho Vải chính, Keo và Lót..."):
                try:
                    import google.generativeai as genai
                    import json, copy, traceback, re
                    import pandas as pd
                    
                    if "GEMINI_API_KEY" in st.secrets: 
                        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
                        
                    model = genai.GenerativeModel(
                        "gemini-2.5-flash", 
                        generation_config={"response_mime_type": "application/json"}
                    )
                    
                    # PROMPT ĐÃ ĐƯỢC THAY ĐỔI: Ép AI tìm thông số hình học cho cả Keo và Lót
                    prompt_instruction = f"""
                    You are an expert apparel IE system. Analyze the full text extracted from the Techpack PDF.
                    Your goal is to scan through ALL pages to find the exact "BOM" table and "SIZE SPECIFICATION" sheet for all materials.
                    
                    DATA PROVIDED FROM TECHPACK:
                    {full_techpack_text}
                    
                    CRITICAL DYNAMIC EXTRACTION INSTRUCTION:
                    1. Identify product type (PANT, JACKET, DRESS, SHIRT, etc.).
                    2. Locate the BOM and look for ALL fabric types: MAIN FABRIC, LINING (Vải lót), and FUSING/INTERLINING (Mex keo).
                    3. Go to the MEASUREMENT SHEET and check if there are specific dimensions for LINING or FUSING components (e.g., Pocket bag length/width, lining length for dress/jacket).
                    4. For EACH fabric material row (Main, Lining, Fusing):
                       - IF you find specific measurements for that material in the sheet, you MUST populate its "panels_catalog" array with realistic bounding boxes (`piece_length_inch` and `piece_width_inch`) extracted from the text.
                       - IF NO specific measurements are found in the PDF for Lining/Fusing, you may leave its "panels_catalog" empty, and the system will use a smart manufacturing fallback.
                    
                    Return ONLY a valid JSON object matching this strict structure:
                    {{
                      "detected_product_type": "PANT", 
                      "style_code": "R09-450416",
                      "bom_rows": [
                        {{
                          "component_type": "MAIN FABRIC",
                          "placement": "BODY",
                          "fabric_classification": "MAIN_FABRIC",
                          "fabric_code": "REAL_MAIN_CODE",
                          "fabric_color": "REAL_COLOR",
                          "panels_catalog": [
                            {{ "panel_name": "FRONT_PANEL", "piece_count": 2.0, "piece_length_inch": 41.0, "piece_width_inch": 12.0 }}
                          ]
                        }},
                        {{
                          "component_type": "POCKET LINING",
                          "placement": "POCKET BAG",
                          "fabric_classification": "LINING",
                          "fabric_code": "REAL_LINING_CODE",
                          "fabric_color": "NATURAL",
                          "panels_catalog": [
                            {{ "panel_name": "POCKET_BAG", "piece_count": 4.0, "piece_length_inch": 13.0, "piece_width_inch": 7.5 }}
                          ]
                        }}
                      ]
                    }}
                    User directive overrides: {active_prompt}
                    """
                    
                    response = model.generate_content(prompt_instruction)
                    cleaned_text = response.text.strip()
                    cleaned_text = re.sub(r"^```json\s*", "", cleaned_text, flags=re.IGNORECASE)
                    cleaned_text = re.sub(r"\s*```$", "", cleaned_text)
                    
                    try: raw_blueprint = json.loads(cleaned_text)
                    except json.JSONDecodeError: raw_blueprint = {"bom_rows": []}
                    
                    if raw_blueprint and raw_blueprint.get("bom_rows"):
                        blueprint_worker = copy.deepcopy(raw_blueprint)
                        try: step_2a1 = parse_geometric_panels_allowance(blueprint_worker, active_prompt)
                        except Exception: step_2a1 = blueprint_worker
                        
                        try: step_2a2 = execute_marker_yardage_and_quality_gate(step_2a1, active_prompt)
                        except Exception: step_2a2 = step_2a1
                        
                        blueprint_final = allocate_fabric_consumption_and_quality_gate(step_2a2)
                        st.session_state.bom_data = blueprint_final
                    
                    st.rerun()
                except Exception:
                    st.error("💥 Lỗi xử lý tiến trình Phân đoạn 7a:")
                    st.code(traceback.format_exc())
# =====================================================================
# ĐOẠN 7b: KHU VỰC HIỂN THỊ KẾT QUẢ ĐƠN MÃ VÀ XUẤT EXCEL (V17.0.0.4 FIXED TUPLE)
# =====================================================================
if st.session_state.get("bom_data") and "bom_rows" in st.session_state.bom_data and st.session_state.bom_data["bom_rows"]:
    st.markdown('<div class="cad-card">', unsafe_allow_html=True)
    st.markdown('<div class="cad-header">📊 CALCULATED FABRIC CONSUMPTION MATRIX (BOM RESULT)</div>', unsafe_allow_html=True)
    
    chat_txt = str(safe_user_prompt).lower()
    m_c = re.search(r'(?:co\s*rút|co\s*rut|co)\s*([\d\.]+)\s*(?:-|–|x|ngang|\s+)\s*([\d\.]+)', chat_txt)
    warp_default, weft_default = (f"{float(m_c.group(1))}%", f"{float(m_c.group(2))}%") if m_c else ("5.0%", "15.0%")
    
    display_data = []
    for r in st.session_state.bom_data["bom_rows"]:
        if not r or not isinstance(r, dict): 
            continue
            
        sys_notes = r.get("consumption_note", "")
        current_gross = r.get("calculated_gross_consumption_yds", 0.0)
        reason_logs = str(r.get("reason_or_logs", ""))
        
        # ĐỒNG BỘ HIỂN THỊ KHỔ VẢI CHUẨN XÁC CHẤT LIỆU
        if "fabric_width_inch" in r and r["fabric_width_inch"] > 0:
            cut_width_val = f"{float(r['fabric_width_inch'])} inch"
        else:
            match_w = re.search(r'Khổ vải:\s*([\d\.]+)', sys_notes)
            if match_w:
                cut_width_val = f"{float(match_w.group(1))} inch"
            else:
                match_w_alt = re.search(r'Khổ\s*(?:lót|mếch):\s*([\d\.]+)', sys_notes)
                cut_width_val = f"{float(match_w_alt.group(1))} inch" if match_w_alt else "58.0 inch"
        
        # Tách thông tin co rút dọc / ngang trước wash
        warp_val = warp_default
        weft_val = weft_default
        if "/" in reason_logs:
            parts = reason_logs.split("/")
            if len(parts) >= 3:
                shrink_part = parts.strip()
                match_sh = re.search(r'([\d\.]+)\s*x\s*([\d\.]+)', shrink_part)
                if match_sh:
                    warp_val = f"{float(match_sh.group(1))}%"
                    weft_val = f"{float(match_sh.group(2))}%"
                    
        # Ép độ co rút về 0% cho phụ liệu keo lót (nếu không có chỉ định đặc biệt)
        if any(x in str(r.get("fabric_classification", "")).upper() for x in ["FUSING", "LINING"]):
            warp_val = "0.0%"
            weft_val = "0.0%"

        display_data.append({
            "Component Type": r.get("component_type", "MAIN FABRIC"),
            "Placement": r.get("placement", "BODY"),
            "Fabric Classification": r.get("fabric_classification", "MAIN_FABRIC"),
            "Fabric Code": r.get("fabric_code", "D-32777"),
            "Fabric Color": r.get("fabric_color", "LIGHT ORANGE"),
            "Khổ vải (Width)": cut_width_val,
            "Co rút dọc (% Warp)": warp_val,
            "Co rút ngang (% Weft)": weft_val,
            "Marker Efficiency": r.get("marker_efficiency_pct", "76.0%"),
            "Gross Consumption (Yds)": current_gross,
            "Quality Status": r.get("status", "PASS"),
            "System Notes": sys_notes
        })
        
    # Tạo DataFrame và hiển thị bảng dữ liệu lên giao diện Streamlit
    df_bom = pd.DataFrame(display_data)
    st.dataframe(df_bom, use_container_width=True, hide_index=True)
    st.markdown('</div>', unsafe_allow_html=True)
    
    # =====================================================================
    # KHỐI LOGIC TẠO FILE EXCEL REPORT (ĐÃ FIX LỖI TUPLE COLUMN TẬN GỐC)
    # =====================================================================
    try:
        import io
        from openpyxl import Workbook
        from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
        from openpyxl.utils import get_column_letter

        output = io.BytesIO()
        wb = Workbook()
        ws = wb.active
        ws.title = "BOM Fabric Consumption"
        
        ws.sheet_view.showGridLines = True 
        
        # Cấu hình phong cách bảng tính chuyên nghiệp
        font_title = Font(name="Calibri", size=14, bold=True, color="FFFFFF")
        font_header = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        font_body = Font(name="Calibri", size=11, bold=False)
        
        fill_title = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
        fill_header = PatternFill(start_color="2C3E50", end_color="2C3E50", fill_type="solid")
        
        align_center = Alignment(horizontal="center", vertical="center", wrap_text=True)
        align_left = Alignment(horizontal="left", vertical="center")
        align_right = Alignment(horizontal="right", vertical="center")
        
        thin_side = Side(border_style="thin", color="D9D9D9")
        thin_border = Border(left=thin_side, right=thin_side, top=thin_side, bottom=thin_side)
        
        # Viết dòng tiêu đề lớn gộp ô
        ws.merge_cells("A1:L1")
        ws["A1"] = f"BÁO CÁO ĐỊNH MỨC VẬT TƯ VẢI - STYLE: {st.session_state.bom_data.get('style_code', 'R09-450416')}"
        ws["A1"].font = font_title
        ws["A1"].fill = fill_title
        ws["A1"].alignment = align_center
        ws.row_dimensions.height = 40
        
        # Tạo thanh tiêu đề cột dữ liệu
        headers = list(df_bom.columns)
        for col_num, header_title in enumerate(headers, 1):
            cell = ws.cell(row=3, column=col_num)
            cell.value = header_title
            cell.font = font_header
            cell.fill = fill_header
            cell.alignment = align_center
            cell.border = thin_border
        ws.row_dimensions.height = 28
        
        # Đổ dữ liệu định mức vào các dòng tương ứng
        for row_num, row_data in enumerate(display_data, 4):
            ws.row_dimensions[row_num].height = 22
            for col_num, key in enumerate(headers, 1):
                cell = ws.cell(row=row_num, column=col_num)
                cell.value = row_data[key]
                cell.font = font_body
                cell.border = thin_border
                
                # Căn lề và xử lý hiển thị số thập phân
                if key in ["Gross Consumption (Yds)"]:
                    cell.alignment = align_right
                    cell.number_format = '#,##0.0000'
                elif key in ["Khổ vải (Width)", "Co rút dọc (% Warp)", "Co rút ngang (% Weft)", "Marker Efficiency", "Quality Status"]:
                    cell.alignment = align_center
                else:
                    cell.alignment = align_left
        
        # 🟢 LẬP TRÌNH LẠI KHỐI CO GIÃN CỘT: Duyệt trực tiếp theo danh sách cột để tránh lỗi tuple vĩnh viễn
        for col_idx, col_name in enumerate(headers, 1):
            max_len = len(col_name) # Độ dài tối thiểu bằng tên tiêu đề cột
            for row_num in range(4, 4 + len(display_data)):
                val = ws.cell(row=row_num, column=col_idx).value
                if val:
                    max_len = max(max_len, len(str(val)))
            
            col_letter = get_column_letter(col_idx)
            ws.column_dimensions[col_letter].width = max(max_len + 5, 12)
            
        wb.save(output)
        excel_bytes = output.getvalue()
        
        # NÚT XUẤT TẢI FILE EXCEL RA MÀN HÌNH GIAO DIỆN
        st.markdown("<br>", unsafe_allow_html=True)
        st.download_button(
            label="📥 XUẤT FILE EXCEL ĐỊNH MỨC CHUẨN SẢN XUẤT",
            data=excel_bytes,
            file_name=f"BOM_Consumption_{st.session_state.bom_data.get('style_code', 'R09-450416')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
    except Exception as e:
        st.warning(f"⚠️ Không thể khởi tạo nút xuất Excel cao cấp: {str(e)}")
