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
# ĐOẠN 2a1: RẬP HÌNH HỌC, TỰ ĐỘNG BÙ TRỪ & LOG CHUYÊN SÂU (V16.3 CHUẨN)
# =====================================================================

def parse_geometric_panels_allowance(ai_blueprint: dict, user_chat: str) -> dict:
    if not ai_blueprint or not isinstance(ai_blueprint, dict):
        return {"detected_product_type": "PANT", "bom_rows": []}

    product_type = str(ai_blueprint.get("detected_product_type", "DEFAULT")).upper().strip()
    body_length = safe_float(ai_blueprint.get("extracted_body_length"), 28.0)
    chest_width = safe_float(ai_blueprint.get("extracted_chest_width"), 20.0)
    outseam_length = safe_float(ai_blueprint.get("extracted_outseam_length"), 14.5 if product_type == "JORT" else 40.0)
    hip_width = safe_float(ai_blueprint.get("extracted_hip_width"), 21.0)

    FACTORY_SEAM_INCH = 0.5       
    FACTORY_HEM_INCH = 1.5        
    FACTORY_WAISTBAND_INCH = 2.5  
    FACTORY_PLEAT_INCH = 3.0      

    SHAPE_FACTORS = {
        "FRONT": 0.54,      
        "BACK": 0.59,       
        "WAISTBAND": 0.94,  
        "POCKET": 0.78,     
        "SLEEVE": 0.64,     
        "DEFAULT": 0.62     
    }

    all_rows = ai_blueprint.get("bom_rows", [])
    if not all_rows or not isinstance(all_rows, list): all_rows = []
    parsed_rows = []

    for row in all_rows:
        if not row or not isinstance(row, dict): continue
        c_type = str(row.get("component_type", "")).upper()
        placement = str(row.get("placement", "")).upper()
        f_class_raw = str(row.get("fabric_classification", "")).upper()
        f_code = str(row.get("fabric_code", "")).upper()
        
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

        if panels and isinstance(panels, list):
            for panel in panels:
                if not panel or not isinstance(panel, dict): continue
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
                if polygon_points and isinstance(polygon_points, list) and len(polygon_points) >= 3:
                    base_area = calculate_shoelace_polygon_area(polygon_points) * (scale_factor ** 2)
                    p_len_nodes = len(polygon_points)
                    total_dist = 0.0
                    for i in range(p_len_nodes):
                        j = (i + 1) % p_len_nodes
                        pt1, pt2 = polygon_points[i], polygon_points[j]
                        if not pt1 or not pt2: continue
                        x1 = float(pt1 if isinstance(pt1, (list, tuple)) else pt1.get("x", 0.0))
                        y1 = float(pt1 if isinstance(pt1, (list, tuple)) else pt1.get("y", 0.0))
                        x2 = float(pt2 if isinstance(pt2, (list, tuple)) else pt2.get("x", 0.0))
                        y2 = float(pt2 if isinstance(pt2, (list, tuple)) else pt2.get("y", 0.0))
                        total_dist += ((x2 - x1)**2 + (y2 - y1)**2)**0.5
                    actual_perimeter_inch = total_dist * scale_factor * p_count
                else:
                    p_len = safe_float(panel.get("piece_length_inch"), 0.0)
                    p_wid = safe_float(panel.get("piece_width_inch"), 0.0)
                    base_area = p_len * p_wid * s_factor if (p_len > 0 and p_wid > 0) else 0.0
                    perimeter_factor = 0.88 if s_factor in [0.54, 0.59] else 0.96 
                    actual_perimeter_inch = ((p_len * 2) + (p_wid * 2)) * perimeter_factor * p_count
                
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

                pleat_area_addition = 0.0
                pleat_val = safe_float(panel.get("pleat"), 0.0)
                if pleat_val == 0.0:
                    if any(k in p_name or k in p_type_code for k in ["PLEAT", "XEP_LY", "LY_HOP", "CARGO", "POCKET", "TUI_DAT", "TUI_HOP"]):
                        pleat_val = 1.0
                if pleat_val > 0:
                    pleat_width = safe_float(panel.get("pleat_width"), 1.0)
                    pleat_count = safe_float(panel.get("pleat_count"), 1.0)
                    pleat_area_addition = (eval_len * pleat_width * pleat_count) * p_count

                final_panel_area = raw_panel_area_total + seam_area_addition + hem_area_addition + pleat_area_addition
                row_total_net_area_sq_in += final_panel_area
                
                panel_debug_logs.append({
                    "panel_name": p_name, "piece_count": p_count,
                    "base_area_sq_in": round(raw_panel_area_total, 2),
                    "seam_add_sq_in": round(seam_area_addition, 2),
                    "hem_add_sq_in": round(hem_area_addition, 2),
                    "pleat_add_sq_in": round(pleat_area_addition, 2),
                    "total_area_sq_in": round(final_panel_area, 2),
                    "perimeter_inch": round(actual_perimeter_inch, 2)
                })

        row["_computed_net_area_sq_in"] = row_total_net_area_sq_in
        row["_panel_debug_logs"] = panel_debug_logs
        parsed_rows.append(row)

    ai_blueprint["bom_rows"] = parsed_rows
    return ai_blueprint
# =====================================================================
# ĐOẠN 2a2: ĐỊNH MỨC SƠ ĐỒ VÀ GOM NHÓM VẬT TƯ CHỐNG TRÙNG LẶP (V15.4)
# =====================================================================

def execute_marker_yardage_and_quality_gate(ai_blueprint: dict, user_chat: str) -> dict:
    all_rows = ai_blueprint.get("bom_rows", [])
    fabric_registry = {}
    chat_clean = " " + str(user_chat).lower().strip() + " "

    def parse_specs_safe(chat_text):
        width, warp, weft = None, None, None
        words = chat_text.split()
        for idx, word in enumerate(words):
            if word in ["khổ", "kho"] and idx + 1 < len(words):
                try: width = float(words[idx+1].replace('"', '').replace('inch', ''))
                except ValueError: pass
        for idx, word in enumerate(words):
            if word in ["dọc", "doc"] and idx + 1 < len(words):
                try: warp = float(words[idx+1].replace("%", ""))
                except ValueError: pass
            elif word in ["co", "rút", "rut"] and idx + 1 < len(words) and warp is None:
                try: warp = float(words[idx+1].replace("%", ""))
                except ValueError: pass
        for idx, word in enumerate(words):
            if word in ["ngang"] and idx + 1 < len(words):
                try: weft = float(words[idx+1].replace("%", ""))
                except ValueError: pass
        if warp is None or weft is None:
            for word in words:
                if "-" in word:
                    parts = word.split("-")
                    if len(parts) == 2:
                        try:
                            warp = float(parts.replace("%", ""))
                            weft = float(parts.replace("%", ""))
                        except ValueError: pass
        return width, warp, weft

    w_main, s_l_main, s_w_main = parse_specs_safe(chat_clean)

    for row in all_rows:
        if not row or not isinstance(row, dict) or "_computed_net_area_sq_in" not in row: continue
        f_class_raw = row.get("fabric_classification", "MAIN_FABRIC")
        f_class_norm = normalize_fabric_class(f_class_raw)
        f_code = str(row.get("fabric_code", "MAIN")).upper().strip().replace(" ", "_")
        f_color = str(row.get("fabric_color", "COLOR")).upper().strip().replace(" ", "_")
        grain_rule = str(row.get("fabric_grain_rule", "TWO_WAY")).upper().strip().replace(" ", "_")
        fab_repeat = safe_float(row.get("fabric_repeat_inch"), 0.0)
        
        tmp_id = f"{f_code}_{f_color}_{grain_rule}_{int(fab_repeat)}"
        w_b = w_main if w_main is not None else safe_float(row.get("fabric_width_inch"), 58.0)
        s_warp = s_l_main if s_l_main is not None else safe_float(row.get("shrinkage_warp_pct"), 5.0)
        s_weft = s_w_main if s_w_main is not None else safe_float(row.get("shrinkage_weft_pct"), 15.0)
        
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
                "cutable_w": w_b, 
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
# =====================================================================
# ĐOẠN 2b: PHÂN BỔ ĐỊNH MỨC THEO FABRIC ID & KIỂM SOÁT THỰC TẾ (V16.5)
# =====================================================================

def allocate_fabric_consumption_and_quality_gate(ai_blueprint: dict) -> dict:
    if not ai_blueprint or not isinstance(ai_blueprint, dict):
        return {"detected_product_type": "PANT", "bom_rows": []}

    product_type = str(ai_blueprint.get("detected_product_type", "DEFAULT")).upper().strip()
    fabric_registry = ai_blueprint.pop("_fabric_registry_cache", {})
    if not fabric_registry: fabric_registry = {}
    processed_bom_blueprint = []
    
    all_rows = ai_blueprint.get("bom_rows", [])
    if not all_rows or not isinstance(all_rows, list): all_rows = []
    
    for row in all_rows:
        if not row or not isinstance(row, dict): continue
        comp_type = str(row.get("component_type", "")).upper()
        placement = str(row.get("placement", "")).upper()
        f_class_raw = str(row.get("fabric_classification", "")).upper()
        f_code = str(row.get("fabric_code", "")).upper()

        if any(k in comp_type or k in placement or k in f_class_raw or k in f_code for k in EXCLUDE_HARDWARE_KEYS):
            row["calculated_gross_consumption_yds"] = 0.0
            row["marker_efficiency_pct"] = "N/A"
            row["status"] = "PASS"
            row["consumption_note"] = "Hardware Trim Bypass"
            row["reason_or_logs"] = "Bypass hoàn toàn theo yêu cầu"
            if row not in processed_bom_blueprint: processed_bom_blueprint.append(row)

    for f_id, data in fabric_registry.items():
        if not data or not isinstance(data, dict): continue
        total_area = data.get("accumulated_area_sq_in", 0.0)
        cutable_w = data.get("cutable_w", 58.0)
        eff = data.get("eff", 0.85)
        f_class_norm = data.get("f_class", "MAIN_FABRIC")
        rows_to_update = data.get("rows_to_update", [])
        if not rows_to_update or not isinstance(rows_to_update, list): rows_to_update = []

        for row in rows_to_update:
            if not row or not isinstance(row, dict): continue
            comp_type = str(row.get("component_type", "")).upper()
            placement = str(row.get("placement", "")).upper()
            f_code = str(row.get("fabric_code", "")).upper()

            if any(k in comp_type or k in placement or k in f_code for k in EXCLUDE_HARDWARE_KEYS):
                row["calculated_gross_consumption_yds"] = 0.0
                row["marker_efficiency_pct"] = "N/A"
                row["status"] = "PASS"
                row["consumption_note"] = "Hardware Trim Bypass"
                if row not in processed_bom_blueprint: processed_bom_blueprint.append(row)
                continue

            if f_class_norm in ["MAIN_FABRIC", "RIB"]:
                if f_class_norm == "MAIN_FABRIC": nesting_factor = 0.45  
                else: nesting_factor = 0.85  
                if product_type not in ["PANT", "CARGO_PANT", "CAPRI_PANT", "JORT"]: nesting_factor = 1.0 
                
                optimized_area = total_area * nesting_factor
                base_cons = (optimized_area / (cutable_w * 36.0)) / eff
                total_yds = base_cons * data.get("shrink_warp_f", 1.05) * data.get("wastage_f", 1.03)
                total_yds = round(total_yds, 4)
                
                row_status = "PASS"
                cfg = LIMITS.get(product_type, LIMITS["DEFAULT"])
                min_allow, max_allow = cfg["range"]
                if f_class_norm == "MAIN_FABRIC":
                    if total_yds > max_allow: row_status = "CRITICAL_HIGH_CONSUMPTION"
                    elif total_yds < min_allow: row_status = "LOW_CONSUMPTION_WARNING"
                    elif total_yds > cfg["warn_thresh"]: row_status = "HIGH_CONSUMPTION_WARNING"
                
                w_original = data.get("w_saved", 58.0)
                s_l_saved = (data.get("shrink_warp_f", 1.0) - 1.0) * 100.0
                s_w_saved = (data.get("shrink_weft_f", 1.0) - 1.0) * 100.0
                log_output = f"{round(w_original,1)}\"/{round(eff*100,1)}%/{round(s_l_saved,1)}x{round(s_w_saved,1)} | Rập {f_id}: {round(total_area,1)} sq_in."
                
                row["calculated_gross_consumption_yds"] = total_yds
                row["status"] = row_status
                row["consumption_note"] = f"Khổ vải: {w_original}\" | Sơ đồ: {cutable_w}\" | Check: {row_status}"
                row["reason_or_logs"] = log_output
            else:
                if f_class_norm in ["FUSING", "INTERLINING"] or "KEO" in comp_type or "MEX" in comp_type: f_yds = 0.15  
                elif f_class_norm in ["LINING", "POCKETING"] or "POCKET" in comp_type or "TÚI" in comp_type: f_yds = 0.20  
                elif any(x in comp_type for x in ["TAPE", "THUN", "PIPING"]): f_yds = 0.15  
                else: f_yds = 0.0
                
                row["calculated_gross_consumption_yds"] = f_yds
                row["status"] = "PASS"
                row["consumption_note"] = "Component Fixed Allocation"
                row["reason_or_logs"] = "FIXED"

            row["marker_efficiency_pct"] = f"{round(eff * 100, 1)}%"
            row["panel_debug_summary"] = row.get("_panel_debug_logs", [])
            if row not in processed_bom_blueprint: processed_bom_blueprint.append(row)

    ai_blueprint["bom_rows"] = processed_bom_blueprint
    return ai_blueprint
# =====================================================================
# ĐOẠN 5: ENGINE XUẤT EXCEL THEO FORM MẪU BÁO CÁO PHONG PHÚ (V15.9 APPROVED)
# =====================================================================

def export_to_phong_phu_excel(bom_data, pdf_name):
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
        for col_num, header_title in enumerate(headers): worksheet.write(10, col_num, header_title, header_format)
            
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
            
            if gross_yds == 0.0 or "Bypass" in sys_notes: cut_width, warp_str, weft_str = "N/A", "N/A", "N/A"
            else:
                match_w = re.search(r'Khổ vải:\s*([\d\.]+)', sys_notes)
                if match_w: cut_width = f"{float(match_w.group(1))} inch"
                else:
                    match_w_alt = re.search(r'CutWidth:\s*([\d\.]+)', sys_notes)
                    cut_width = f"{float(match_w_alt.group(1))} inch" if match_w_alt else "58.0 inch"
                match_sh = re.search(r'([\d\.]+)x([\d\.]+)', reason_logs)
                if match_sh: warp_str, weft_str = f"{float(match_sh.group(1))}%", f"{float(match_sh.group(2))}%"
                else: warp_str, weft_str = "5.0%", "15.0%"
            
            worksheet.write(current_data_row, 0, stt, cell_center)
            worksheet.write(current_data_row, 1, comp_type, cell_left)
            worksheet.write(current_data_row, 2, full_code, cell_left)
            worksheet.write(current_data_row, 3, cut_width, cell_center)
            worksheet.write(current_data_row, 4, gross_yds, cell_right)
            worksheet.write(current_data_row, 5, warp_str, cell_center)  
            worksheet.write(current_data_row, 6, weft_str, cell_center) 
            worksheet.write(current_data_row, 7, marker_eff, cell_center)
            
            if "CRITICAL" in q_status: worksheet.write(current_data_row, 8, "🔴 VƯỢT TRẦN", crit_format)
            elif "WARN" in q_status: worksheet.write(current_data_row, 8, "🟡 CẢNH BÁO", warn_format)
            else: worksheet.write(current_data_row, 8, "🟢 ĐẠT TIÊU CHUẨN", pass_format)
            current_data_row += 1
            stt += 1
            
        worksheet.write(current_data_row + 3, 1, "NGƯỜI LẬP BIỂU\n(Phòng IE May)", sign_title_format)
        worksheet.write(current_data_row + 3, 4, "TRƯỞNG PHÒNG IE\n(Ký duyệt)", sign_title_format)
        worksheet.write(current_data_row + 3, 7, "GIÁM ĐỐC SẢN XUẤT\n(Phê duyệt)", sign_title_format)
        
        widths = [6, 30, 25, 15, 15, 18, 18, 18, 22]
        for col_idx, w in enumerate(widths): worksheet.set_column(col_idx, col_idx, w)
    return buffer.getvalue()
# =====================================================================
# ĐOẠN 6: GIAO DIỆN CHÍNH THỰC THI CHUẨN LAYOUT GỐC (APP FRAMEWORK)
# =====================================================================
st.set_page_config(layout="wide", page_title="AI Fabric Consumption Matrix")

st.markdown("""
<style>
    .cad-card {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 20px;
        margin-top: 20px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
    }
    .cad-header {
        font-family: 'Segoe UI', sans-serif;
        font-size: 14px;
        font-weight: 700;
        color: #0369a1;
        letter-spacing: 0.05em;
        margin-bottom: 15px;
        padding-bottom: 8px;
        border-bottom: 2px solid #cbd5e1;
    }
</style>
""", unsafe_allow_html=True)

if "bom_data" not in st.session_state: st.session_state.bom_data = None
if "chat_history" not in st.session_state: st.session_state.chat_history = []
if "pdf_bytes" not in st.session_state: st.session_state.pdf_bytes = None
if "pdf_name" not in st.session_state: st.session_state.pdf_name = ""

col_left, col_right = st.columns(2)

with col_left:
    st.markdown('<h1 style="color:#1e3a8a; font-family:Segoe UI;">💬 CAD LIVE LOG CONSOLE</h1>', unsafe_allow_html=True)
    st.sidebar.markdown("### ⚙️ ENGINE CONTROLS")
    st.sidebar.markdown('<div style="background-color:#dcfce7; color:#15803d; padding:10px; border-radius:6px; font-weight:600; font-size:13px; margin-bottom:15px;">🟢 API STATUS: Hệ thống đang hoạt động trong hạn ngạch cho phép.</div>', unsafe_allow_html=True)
    
    if st.sidebar.button("🗑️ CLEAR SYSTEM MEMORY", use_container_width=True):
        st.session_state.bom_data = None
        st.session_state.chat_history = []
        st.session_state.pdf_bytes = None
        st.session_state.pdf_name = ""
        st.rerun()

    uploaded_file = st.file_uploader("📂 Tải lên tệp tài liệu kỹ thuật Techpack / BOM (PDF)", type=["pdf"])
    if uploaded_file is not None:
        st.session_state.pdf_bytes = uploaded_file.read()
        st.session_state.pdf_name = uploaded_file.name

    user_prompt = st.chat_input("Input override commands...")
with col_right:
    st.markdown('<div style="height:45px;"></div>', unsafe_allow_html=True)
    if st.session_state.pdf_bytes is not None:
        try:
            import fitz  
            doc = fitz.open(stream=st.session_state.pdf_bytes, filetype="pdf")
            st.image(doc.load_page(0).get_pixmap(dpi=150).tobytes("png"), caption="🎨 Sketch Layout", use_container_width=True)
            st.success(f"📎 BUFFERED OBJECT: {st.session_state.pdf_name} loaded successfully.")
        except: pass
    else:
        st.caption("ℹ️ Hệ thống sẵn sàng kết xuất hình ảnh phác thảo sơ đồ rập phẳng sau khi tải file.")

    if user_prompt and st.session_state.pdf_bytes is not None:
        with st.spinner("🧠 AI đang bóc tách sơ đồ BOM thực tế..."):
            try:
                import google.generativeai as genai
                import json, copy, traceback
                if "GEMINI_API_KEY" in st.secrets: genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
                
                model = genai.GenerativeModel("gemini-2.5-flash", generation_config={"response_mime_type": "application/json"})
                prompt_instruction = f"Extract apparel BOM rows into structured JSON format with panels_catalog detail. User overrides: {user_prompt}"
                
                response = model.generate_content([{"mime_type": "application/pdf", "data": st.session_state.pdf_bytes}, prompt_instruction])
                raw_blueprint = json.loads(response.text)
                
                step_2a1 = parse_geometric_panels_allowance(raw_blueprint, user_prompt)
                step_2a2 = execute_marker_yardage_and_quality_gate(step_2a1, user_prompt)
                blueprint_final = allocate_fabric_consumption_and_quality_gate(step_2a2)
                
                st.session_state.bom_data = blueprint_final
                st.rerun()
            except Exception:
                st.error("💥 Lỗi xử lý tiến trình:")
                st.code(traceback.format_exc())

if st.session_state.get("bom_data") and "bom_rows" in st.session_state.bom_data:
    st.markdown('<div class="cad-card">', unsafe_allow_html=True)
    st.markdown('<div class="cad-header">📊 CALCULATED FABRIC CONSUMPTION MATRIX (BOM RESULT)</div>', unsafe_allow_html=True)
    
    chat_txt = str(user_prompt if user_prompt else "").lower()
    m_c = re.search(r'(?:co\s*rút|co\s*rut|co)\s*([\d\.]+)\s*(?:-|–|x|ngang|\s+)\s*([\d\.]+)', chat_txt)
    warp_default, weft_default = (f"{float(m_c.group(1))}%", f"{float(m_c.group(2))}%") if m_c else ("5.0%", "15.0%")
    
    display_data = []
    for r in st.session_state.bom_data["bom_rows"]:
        sys_notes = r.get("consumption_note", "")
        current_gross = r.get("calculated_gross_consumption_yds", 0.0)
        reason_logs = str(r.get("reason_or_logs", ""))
        
        match_w = re.search(r'Khổ vải:\s*([\d\.]+)', sys_notes)
        if match_w: cut_width_val = f"{float(match_w.group(1))} inch"
        else:
            match_w_alt = re.search(r'CutWidth:\s*([\d\.]+)', sys_notes)
            cut_width_val = f"{float(match_w_alt.group(1))} inch" if match_w_alt else "58.0 inch"
        
        match_sh = re.search(r'([\d\.]+)x([\d\.]+)', reason_logs)
        warp_val, weft_val = (f"{float(match_sh.group(1))}%", f"{float(match_sh.group(2))}%") if match_sh else (warp_default, weft_default)
        
        if current_gross == 0.0 or "Bypass" in sys_notes: cut_width_val, warp_val, weft_val = "N/A", "N/A", "N/A"
            
        display_data.append({
            "Component Type": r.get("component_type", "N/A"), "Placement": r.get("placement", "N/A"),
            "Fabric Classification": r.get("fabric_classification", "MAIN_FABRIC"), "Fabric Code": r.get("fabric_code", "MAIN"),
            "Fabric Color": r.get("fabric_color", "COLOR"), "Khổ vải (Width)": cut_width_val,
            "Co rút dọc (% Warp)": warp_val, "Co rút ngang (% Weft)": weft_val,
            "Marker Efficiency": r.get("marker_efficiency_pct", "N/A"), "Gross Consumption (Yds)": current_gross,
            "Quality Status": r.get("status", "PASS"), "System Notes": sys_notes
        })
        
    df_bom = pd.DataFrame(display_data)
    phong_phu_excel_bytes = export_to_phong_phu_excel(st.session_state.bom_data, st.session_state.get("pdf_name", "file.pdf"))
    
    col_label_pp, col_btn_pp = st.columns(2)
    with col_label_pp: st.write("Dữ liệu định mức kỹ thuật đã sẵn sàng xuất bản ra file Excel theo form hệ thống:")
    with col_btn_pp:
        st.download_button(
            label="📥 TẢI MẪU BÁO CÁO PHONG PHÚ (.XLSX)", data=phong_phu_excel_bytes,
            file_name=f"Bao_Cao_Dinh_Muc_Phong_Phu_{st.session_state.get('pdf_name', 'file').replace('.pdf', '')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True
        )
    st.dataframe(df_bom, use_container_width=True, hide_index=True)
    st.markdown('</div>', unsafe_allow_html=True)
