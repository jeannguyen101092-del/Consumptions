import streamlit as st
import pandas as pd
import io
import re
import copy

# =====================================================================
# ĐOẠN 1: GLOBAL CONFIG REGISTRY & BỘ HẰNG SỐ KỸ THUẬT IE ENGINE (V17.1.0.0 APPROVED)
# =====================================================================

# 1. BỘ CẤU HÌNH HẰNG SỐ KỸ THUẬT CẤP MODULE (CHỐT SỐ KIẾN TRÚC SẠCH)
IE_CONSTANTS = {
    "DEFAULT_WIDTH_MAIN": 57.0,
    "DEFAULT_WIDTH_FUSING": 59.0,
    "DEFAULT_WIDTH_LINING": 57.0,
    "DEFAULT_WIDTH_ELASTIC": 1.5,
    "BASE_MARKER_EFF": 0.83,
    "FIXED_EFF_TRIMS": 0.85,
    "MIN_SAFETY_EFF": 0.75,       # Chặn dưới hiệu suất người dùng nhập (75%)
    "MAX_ALLOWED_EFF": 0.92,      # Chặn trên hiệu suất người dùng nhập (92%)
    "WASTAGE_FACTOR": 1.01,
    "DUNG_SAI_BIEN_CARGO": 1.03,
    "FALLBACK_MAIN_CONS": 1.5450,
    "FALLBACK_FUSING_CONS": 0.1650,
    "FALLBACK_LINING_CONS": 0.4450,
    "FALLBACK_ELASTIC_CONS": 0.8500,
    "WARN_PANT_THRESHOLD": 1.6200,      # Ngưỡng Quality Gate cảnh báo màu vàng
    "CRITICAL_PANT_THRESHOLD": 1.8000,  # Ngưỡng Quality Gate cảnh báo màu đỏ
    "SEAM_ALLOWANCE_FUSING_L": 1.0,
    "SEAM_ALLOWANCE_FUSING_W": 0.5,
    "SEAM_ALLOWANCE_LINING_L": 0.75,
    "SEAM_ALLOWANCE_LINING_W": 0.5
}

# 2. TỪ ĐIỂN PHÂN LOẠI VẬT TƯ VÀ GIỚI HẠN KIỂM SOÁT KIỂM PLM/ERP
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

# Mảng hằng số loại trừ linh kiện cứng an toàn độc lập (Không gọi qua globals)
EXCLUDE_HARDWARE_KEYS = (
    "CHỈ", "THREAD", "ZIPPER", "DÂY KÉO", "BUTTON", "NÚT", "SHANK", "RIVET", 
    "LABEL", "MÁC", "TAG", "EYELETS", "SNAP", "VELCRO", "HOOK", "LOOP", 
    "STOPPER", "TOGGLE", "BUCKLE", "GROMMET", "STICKER", "CARE WHITE", 
    "HEAT STAMP", "HANGTAG", "POLYBAG", "BAO BÌ"
)

# 3. HÀM TIỆN ÍCH PHÒNG VỆ VÀ THUẬT TOÁN HÌNH HỌC NỀN
def safe_float(v, default=0.0):
    """Hàm an toàn cũ giữ tính tương thích ngược hệ thống"""
    try: return float(v)
    except: return default

def ie_safe_float(val, default=0.0):
    """Hàm an toàn mới loại bỏ triệt để text rác nhiễu từ phản hồi AI"""
    if val is None: 
        return default
    if isinstance(val, (int, float)): 
        return float(val)
    try:
        cleaned = re.sub(r'[^\d\.]', '', str(val))
        return float(cleaned) if cleaned else default
    except Exception:
        return default

def normalize_fabric_class(f_class_raw):
    """Đồng bộ hóa tên phân loại chất liệu theo hệ thống nhà máy"""
    f_class_raw = str(f_class_raw).upper().strip()
    if any(k in f_class_raw for k in MAIN_KEYS): return "MAIN_FABRIC"
    if any(k in f_class_raw for k in FUSING_KEYS): return "FUSING"
    if any(k in f_class_raw for k in POCKET_KEYS): return "POCKETING"
    return "MAIN_FABRIC"

def calculate_shoelace_polygon_area(points):
    """Thuật toán Shoelace tính diện tích rập đa giác phi rect phẳng"""
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
    """Hàm giả lập hiệu suất sơ đồ mặc định tương thích ngược"""
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
# ĐOẠN 2b1: BỘ PHÂN RÃ REGEX LỆNH CHAT & TRÍCH XUẤT THÔNG SỐ RẬP BTP (V17.0.2.0)
# =====================================================================

def parse_and_prepare_ie_panels(all_rows: list, product_type: str, user_prompt: str = "") -> tuple:
    """
    Phân đoạn 2b1: Bóc tách số hiệu suất chỉ định và tính diện tích rập bán thành phẩm (BTP).
    Trả về: danh sách dòng đã xử lý hình học và giá trị hiệu suất sơ đồ ép cứng (nếu có).
    """
    import re
    import streamlit as st

    # Phân tích từ khóa hiệu suất mở rộng đa dạng từ ô chat người dùng
    chat_lower = str(user_prompt if user_prompt else "").lower().strip()
    user_requested_eff = None
    
    pattern_eff = r'(?:hiệu\s*suất|hieu\s*suat|eff|efficiency|marker|sơ\s*đồ)\s*[:\-=\s]*([\d\.]+)'
    match_eff = re.search(pattern_eff, chat_lower)
    
    if match_eff:
        try:
            val_eff = float(match_eff.group(1))
            raw_eff = val_eff / 100.0 if val_eff > 1.0 else val_eff
            # Giới hạn biên Eff an toàn, chặn lỗi nhập nhầm số quá lớn hoặc quá nhỏ
            user_requested_eff = min(max(raw_eff, IE_CONSTANTS["MIN_SAFETY_EFF"]), IE_CONSTANTS["MAX_ALLOWED_EFF"])
        except ValueError:
            pass

    prepared_rows = []
    
    for row in all_rows:
        if not row or not isinstance(row, dict): 
            continue
            
        comp_type = str(row.get("component_type", "")).upper().strip()
        placement = str(row.get("placement", "")).upper().strip()
        f_class_raw = str(row.get("fabric_classification", "")).upper().strip()
        f_code = str(row.get("fabric_code", "")).upper().strip()

        # Kiểm tra nhanh phân loại linh kiện
        f_class_norm = normalize_fabric_class(f_class_raw if f_class_raw else comp_type)
        is_fusing = (f_class_norm == "FUSING" or any(x in comp_type or x in placement for x in ["KEO", "MEX", "MẾCH", "INTERLINING"]))
        is_lining = (f_class_norm == "POCKETING" or any(x in comp_type or x in placement for x in ["LINING", "POCKET", "TÚI", "LÓT"]))
        is_elastic_or_tape = any(x in comp_type or x in placement for x in ["ELASTIC", "TAPE", "THUN", "CHUN", "DÂY"])

        # Trích xuất và bóc tách kích thước tấm rập hình học BTP
        panels = row.get("panels_catalog", [])
        max_piece_length = 0.0
        total_panel_area = 0.0
        total_piece_count = 0
        
        if panels and isinstance(panels, list):
            valid_panels = [p for p in panels if isinstance(p, dict)]
            for p in valid_panels:
                l_val = ie_safe_float(p.get("piece_length_inch"), 0.0)
                w_val = ie_safe_float(p.get("piece_width_inch"), 0.0)
                c_val = ie_safe_float(p.get("piece_count"), 1.0)
                
                # Cộng biên đường may bán thành phẩm BTP từ bộ cấu hình hằng số
                if is_fusing:
                    l_val += IE_CONSTANTS["SEAM_ALLOWANCE_FUSING_L"]
                    w_val += IE_CONSTANTS["SEAM_ALLOWANCE_FUSING_W"]
                elif is_lining:
                    l_val += IE_CONSTANTS["SEAM_ALLOWANCE_LINING_L"]
                    w_val += IE_CONSTANTS["SEAM_ALLOWANCE_LINING_W"]
                
                total_panel_area += (l_val * w_val * c_val)
                total_piece_count += c_val
                
                # Xác định chiều dài rập mẫu lớn nhất của cụm thân quần chính phục vụ sơ đồ LINEAR
                if any(x in str(p.get("panel_name", "")).upper() for x in ["PANEL", "BODY", "FRONT", "BACK"]):
                    if l_val > max_piece_length:
                        max_piece_length = l_val

        if max_piece_length == 0.0 and len(panels) > 0:
            max_piece_length = max([ie_safe_float(p.get("piece_length_inch"), 0.0) for p in panels if isinstance(p, dict)] or [42.0])
            if max_piece_length > 50.0: max_piece_length = 42.0

        # Ghi nhận các biến hình học BTP vừa bóc tách vào cấu trúc dòng dữ liệu tạm
        row["_btp_max_piece_length"] = max_piece_length
        row["_btp_total_panel_area"] = total_panel_area
        row["_btp_total_piece_count"] = total_piece_count
        row["_is_fusing"] = is_fusing
        row["_is_lining"] = is_lining
        row["_is_elastic_or_tape"] = is_elastic_or_tape
        
        prepared_rows.append(row)
        
    return prepared_rows, user_requested_eff
# =====================================================================
# ĐOẠN 2b2: LÕI TOÁN HỌC PHÂN BỔ ĐỊNH MỨC & SỬA LỖI ĐỘNG KÍCH SỐ CARGO (V17.0.2.2 APPROVED)
# =====================================================================
# =====================================================================
# ĐOẠN 2b2 - PHẦN A: KHỞI TẠO MA TRẬN ĐỘNG & NHẬN DIỆN CHỦNG LOẠI HÀNG
# =====================================================================

def allocate_fabric_consumption_and_quality_gate(ai_blueprint: dict, user_prompt: str = "") -> dict:
    """
    Phân đoạn 2b2: Bộ phân bổ định mức kỹ thuật đa chủng loại thích ứng động (Adaptive IE Engine).
    Nâng cấp V17.6: Tích hợp ma trận hiệu suất sơ đồ động (Dynamic Marker Efficiency Matrix).
    """
    import streamlit as st
    import re
    import copy

    # 1. KHỞI TẠO MA TRẬN HIỆU SUẤT SƠ ĐỒ ĐỘNG THEO CHỦNG LOẠI HÀNG (MARKER EFF CONFIG)
    MARKER_EFF_CONFIG = {
        "TSHIRT":      {"base": 0.88, "max": 0.92, "edge": 1.02, "warn": 1.4, "crit": 1.8},
        "POLO":        {"base": 0.87, "max": 0.91, "edge": 1.02, "warn": 1.4, "crit": 1.8},
        "SHIRT":       {"base": 0.85, "max": 0.90, "edge": 1.02, "warn": 1.4, "crit": 1.8},
        "PANT":        {"base": 0.85, "max": 0.90, "edge": 1.03, "warn": 1.6, "crit": 1.8},
        "CARGO_PANT":  {"base": 0.84, "max": 0.89, "edge": 1.03, "warn": 1.7, "crit": 1.9},
        "SHORT":       {"base": 0.88, "max": 0.92, "edge": 1.02, "warn": 1.2, "crit": 1.45},
        "JACKET":      {"base": 0.82, "max": 0.88, "edge": 1.05, "warn": 2.4, "crit": 2.8},
        "HOODIE":      {"base": 0.84, "max": 0.89, "edge": 1.04, "warn": 2.2, "crit": 2.6},
        "DRESS":       {"base": 0.83, "max": 0.88, "edge": 1.04, "warn": 2.8, "crit": 3.3},
        "JEAN":        {"base": 0.84, "max": 0.89, "edge": 1.03, "warn": 1.8, "crit": 2.1},
        "CHILDREN":    {"base": 0.91, "max": 0.95, "edge": 1.01, "warn": 0.8, "crit": 1.2},
        "DEFAULT":     {"base": 0.85, "max": 0.90, "edge": 1.03, "warn": 1.62, "crit": 1.80}
    }

    global IE_CONSTANTS, EXCLUDE_HARDWARE_KEYS
    if "IE_CONSTANTS" not in globals():
        IE_CONSTANTS = {
            "DEFAULT_WIDTH_MAIN": 58.0, "DEFAULT_WIDTH_FUSING": 44.0, 
            "DEFAULT_WIDTH_LINING": 56.0, "DEFAULT_WIDTH_ELASTIC": 2.0,
            "FIXED_EFF_TRIMS": 0.85, "WASTAGE_FACTOR": 1.05
        }
    if "EXCLUDE_HARDWARE_KEYS" not in globals():
        EXCLUDE_HARDWARE_KEYS = ["ZIPPER", "BUTTON", "RIVET", "BUCKLE", "SNAP", "HOOK"]

    def ie_safe_float(val, fallback=0.0):
        try: return float(val) if val is not None else fallback
        except: return fallback

    if not ai_blueprint or not isinstance(ai_blueprint, dict):
        return {"detected_product_type": "CARGO_PANT", "bom_rows": []}

    # 2. NHẬN DIỆN CHỦNG LOẠI SẢN PHẨM & TRÍCH XUẤT THÔNG SỐ ĐỘNG
    product_type = str(ai_blueprint.get("detected_product_type", "DEFAULT")).upper().strip()
    
    # Định tuyến tìm cấu hình phù hợp trong ma trận MARKER_EFF_CONFIG
    matched_cfg = MARKER_EFF_CONFIG["DEFAULT"]
    for key, cfg in MARKER_EFF_CONFIG.items():
        if key in product_type:
            matched_cfg = cfg
            break

    # Gán biến điều khiển toán học từ cấu hình tra cứu được
    base_eff = matched_cfg["base"]
    max_allowed_eff = matched_cfg["max"]
    edge_allowance = matched_cfg["edge"]
    warn_thresh = matched_cfg["warn"]
    critical_thresh = matched_cfg["crit"]

    # Thiết lập dải dập biên an toàn (min_len, max_len) theo từng dòng sản phẩm
    if "JACKET" in product_type: min_len, max_len, fallback_len = 24.0, 38.0, 30.0
    elif "DRESS" in product_type: min_len, max_len, fallback_len = 35.0, 65.0, 48.0
    elif "SHORT" in product_type: min_len, max_len, fallback_len = 12.0, 26.0, 18.0
    else: min_len, max_len, fallback_len = 24.0, 52.0, 41.5

    fabric_registry = ai_blueprint.get("_fabric_registry_cache", {}) or {}
    all_rows = ai_blueprint.get("bom_rows", []) or []

    if "parse_and_prepare_ie_panels" in globals():
        prepared_rows, user_requested_eff = parse_and_prepare_ie_panels(all_rows, product_type, user_prompt)
    else:
        prepared_rows = copy.deepcopy(all_rows)
        user_requested_eff = None

    if "accumulated_bom_rows" not in st.session_state:
        st.session_state.accumulated_bom_rows = {}
    # 3. VÒNG LẶP PHÂN BỔ ĐỊNH MỨC VÀ KIỂM SOÁT QUALITY GATE (TIẾP THEO)
    processed_bom_rows = []

    for row in prepared_rows:
        comp_type = str(row.get("component_type", "")).upper().strip()
        placement = str(row.get("placement", "")).upper().strip()
        f_class_raw = str(row.get("fabric_classification", "")).upper().strip()
        f_code = str(row.get("fabric_code", "")).upper().strip()
        f_color = str(row.get("fabric_color", "")).upper().strip()

        # Loại bỏ phụ liệu cứng dệt thoi (Bypass Hardware Trim)
        if any(k in comp_type or k in placement or k in f_class_raw or k in f_code for k in EXCLUDE_HARDWARE_KEYS if k):
            row["calculated_gross_consumption_yds"] = 0.0
            row["marker_efficiency_pct"] = "N/A"
            row["consumption_note"] = "Hardware Trim Bypass"
            row["reason_or_logs"] = "Bypass"
            st.session_state.accumulated_bom_rows[f"HARDWARE_{f_code}"] = row
            processed_bom_rows.append(row)
            continue

        is_fusing = row.get("_is_fusing", False)
        is_lining = row.get("_is_lining", False)
        is_elastic_or_tape = row.get("_is_elastic_or_tape", False)
        total_panel_area = ie_safe_float(row.get("_btp_total_panel_area", 0.0))
        total_piece_count = ie_safe_float(row.get("_btp_total_piece_count", 0.0))

        # Trích xuất chiều dài rập động lớn nhất của mã hàng
        max_piece_length = 0.0
        panels = row.get("panels_catalog", [])
        if panels and isinstance(panels, list):
            lengths = [ie_safe_float(p.get("piece_length_inch"), 0.0) for p in panels if isinstance(p, dict)]
            if lengths:
                valid_lengths = [l for l in lengths if min_len <= l <= max_len]
                max_piece_length = max(valid_lengths) if valid_lengths else (max(lengths) if max(lengths) < 100.0 else fallback_len)

        # Áp khổ vải mặc định theo phân loại cấu trúc phụ liệu mềm
        if is_fusing: default_width = IE_CONSTANTS["DEFAULT_WIDTH_FUSING"]
        elif is_lining: default_width = IE_CONSTANTS["DEFAULT_WIDTH_LINING"]
        elif is_elastic_or_tape: default_width = IE_CONSTANTS["DEFAULT_WIDTH_ELASTIC"]
        else: default_width = IE_CONSTANTS["DEFAULT_WIDTH_MAIN"]

        row["fabric_width_inch"] = row.get("fabric_width_inch", default_width) if ie_safe_float(row.get("fabric_width_inch", 0)) > 0 else default_width
        current_width_val = row["fabric_width_inch"]

        # Tra cứu tỷ lệ co rút dệt phẳng (Shrinkage Lookup)
        matched_cache_data = fabric_registry.get(f"{f_code}_{f_color}_TWO_WAY_0") or next((c_data for f_id, c_data in fabric_registry.items() if f_code in f_id or f_class_raw in f_id), None)
        shrink_warp = matched_cache_data.get("shrink_warp_f", 1.03) if matched_cache_data else 1.03
        shrink_weft = matched_cache_data.get("shrink_weft_f", 1.03) if matched_cache_data else 1.03

        # Khóa Unique Key an toàn tuyệt đối chống gộp nhầm chất liệu phối dệt
        shrink_id_str = f"S{int(shrink_warp*100)}X{int(shrink_weft*100)}"
        if is_fusing: row_unique_key = f"FUSING_TOTAL_{f_code}_W{int(current_width_val)}_{shrink_id_str}"
        elif is_lining: row_unique_key = f"LINING_TOTAL_{f_code}_W{int(current_width_val)}_{shrink_id_str}"
        elif is_elastic_or_tape: row_unique_key = f"ELASTIC_TOTAL_{f_code}_W{int(current_width_val)}"
        else: row_unique_key = f"MAIN_FABRIC_{f_code}_{f_color}_W{int(current_width_val)}_{shrink_id_str}"

        if total_panel_area > 5.0:
            # Đồng bộ hóa hiệu suất sơ đồ thích ứng
            if user_requested_eff is not None:
                eff = max(0.75, min(user_requested_eff, max_allowed_eff))
            else:
                if not is_fusing and not is_lining and not is_elastic_or_tape:
                    # Thuật toán tăng Eff tuyến tính dựa trên mật độ chi tiết dập (Piece-count yield bonus)
                    bonus_eff = min(0.08, (total_piece_count - 4) * 0.008) if total_piece_count > 4 else 0.0
                    eff = min(max_allowed_eff, base_eff + bonus_eff)
                else:
                    eff = IE_CONSTANTS["FIXED_EFF_TRIMS"]
                    
            row["marker_efficiency_pct"] = f"{round(eff * 100, 1)}%"
            
            # Tiến hành chạy công thức toán học phân bổ định mức công nghiệp
            if max_piece_length >= min_len and not is_fusing and not is_lining and not is_elastic_or_tape:
                total_yds = (max_piece_length / 36.0) * shrink_warp * IE_CONSTANTS["WASTAGE_FACTOR"] / eff
                total_yds *= edge_allowance
                row["consumption_note"] = f"Calculated by Max Piece Length (Adaptive Matrix for {product_type})"
            else:
                denom = (current_width_val * 36.0 * eff)
                total_yds = (total_panel_area / denom) * shrink_warp * shrink_weft * IE_CONSTANTS["WASTAGE_FACTOR"] if denom > 0 else 0.0
                row["consumption_note"] = "Calculated by Surface Area Yield"

            total_yds = round(total_yds, 4)
            row["calculated_gross_consumption_yds"] = total_yds

            # Áp dụng bộ lọc Quality Gate theo dải động
            if total_yds >= critical_thresh:
                row["quality_gate_status"] = "CRITICAL"
                row["reason_or_logs"] = f"Yield {total_yds} Yds exceeds critical limit ({critical_thresh}) for {product_type}."
            elif total_yds >= warn_thresh:
                row["quality_gate_status"] = "WARNING"
                row["reason_or_logs"] = f"Yield {total_yds} Yds exceeds tolerance ({warn_thresh}) for {product_type}."
            else:
                row["quality_gate_status"] = "PASSED"
                row["reason_or_logs"] = "Passed internal mathematical constraints validation."

            # Thực hiện tích lũy và cộng dồn định mức theo nhóm Key đồng nhất
            if row_unique_key in st.session_state.accumulated_bom_rows:
                existing_row = st.session_state.accumulated_bom_rows[row_unique_key]
                existing_row["calculated_gross_consumption_yds"] = round(existing_row["calculated_gross_consumption_yds"] + total_yds, 4)
                row = existing_row
            else:
                st.session_state.accumulated_bom_rows[row_unique_key] = row
        else:
            row["calculated_gross_consumption_yds"] = 0.0
            row["marker_efficiency_pct"] = "N/A"
            row["quality_gate_status"] = "SKIPPED"
            row["reason_or_logs"] = "Component area too trivial."

        processed_bom_rows.append(row)

    ai_blueprint["bom_rows"] = processed_bom_rows
    return ai_blueprint


# =====================================================================
# ĐOẠN 6a: BANNER, KPIs GHIM ĐỈNH & CÂN BẰNG CHIỀU CAO 1:1 ĐỐI XỨNG (V18.3.4.0 APPROVED)
# =====================================================================
st.set_page_config(layout="wide", page_title="AI Fabric Consumption Matrix")

# 🌟 BỘ STYLING CSS CẤP CAO: KHỐNG CHẾ MAX-HEIGHT CÂN XỨNG VÀ TẠO KHUNG CUỘN ĐỘC LẬP
st.markdown("""
<style>
    /* Trả nền ứng dụng về màu xám trắng dịu mắt chuẩn văn phòng ERP */
    .stApp {
        background-color: #f8fafc !important;
    }
    
    /* Can thiệp xóa bỏ hoàn toàn thanh Header mặc định của Streamlit để dải ghim không bị đè khuất */
    header[data-testid="stHeader"] {
        background-color: #f8fafc !important;
        z-index: 999990 !important;
    }
    
    /* CONTAINER GHIM ĐỈNH TUYỆT ĐỐI: Nổi lên tầng cao nhất, hiện chữ số rõ ràng */
    .sticky-top-container {
        position: fixed;
        top: 0; 
        left: 0;
        right: 0;
        padding: 10px 4rem 15px 4rem; 
        background-color: #f8fafc !important; 
        z-index: 999999 !important; 
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        width: 100%;
    }

    /* Khung Banner chính trên đỉnh chuyển sắc xanh Coban công nghệ */
    .top-banner {
        background: linear-gradient(135deg, #1e3a8a 0%, #0284c7 100%);
        padding: 12px 20px;
        border-radius: 8px;
        color: #ffffff;
        margin-bottom: 10px;
    }
    .top-title {
        font-family: 'Segoe UI', sans-serif;
        font-size: 18px;
        font-weight: 700;
        letter-spacing: 0.02em;
    }
    .top-subtitle {
        font-size: 11px;
        color: #e0f2fe;
        opacity: 0.85;
        margin-top: 1px;
    }
    
    /* Thẻ chỉ số KPIs sắc màu rực rỡ chữ trắng hiển thị rõ nét vĩnh viễn */
    .kpi-card-colored {
        border-radius: 6px;
        padding: 10px 12px;
        text-align: center;
        box-shadow: 0 2px 4px rgba(0,0,0,0.02);
    }
    .kpi-num-light {
        font-size: 18px;
        font-weight: 700;
        color: #ffffff !important; 
        font-family: 'Segoe UI', sans-serif;
    }
    .kpi-lbl-light {
        font-size: 10px;
        font-weight: 600;
        color: #ffffff !important;
        opacity: 0.9;
        text-transform: uppercase;
        margin-top: 2px;
    }
    
    .bg-style { background: linear-gradient(135deg, #334155 0%, #1e293b 100%); }
    .bg-items { background: linear-gradient(135deg, #0d9488 0%, #0f766e 100%); }
    .bg-cons  { background: linear-gradient(135deg, #ea580c 0%, #c2410c 100%); }
    .bg-size  { background: linear-gradient(135deg, #16a34a 0%, #15803d 100%); }

    /* Khung đệm spacer đẩy nội dung dưới sụp xuống hợp lý, chống lỗi đè mất chữ uploader */
    .main-body-spacer {
        margin-top: 175px; 
    }

    /* 🌟 BƯỚC ĐỘT PHÁ CÂN BẰNG TỶ LỆ: Khống chế chặt chẽ chiều cao tối đa của 2 khối hộp, */
    /* Tạo thanh cuộn trượt độc lập (overflow-y) để ảnh dài không đẩy vỡ bố cục */
    .custom-erp-box {
        background-color: #ffffff !important;
        border: 1px solid #cbd5e1 !important;
        border-radius: 8px;
        padding: 20px;
        margin-bottom: 15px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.03);
        
        max-height: 380px !important; /* 🟢 Ép chiều cao tối đa bằng khít nhau */
        overflow-y: auto !important;   /* 🟢 Tự động bật thanh cuộn nếu ảnh hoặc chữ quá dài */
    }
    
    .cad-header-text {
        font-family: 'Segoe UI', sans-serif;
        font-size: 14px;
        font-weight: 700;
        color: #0369a1; 
        margin-bottom: 15px;
        padding-bottom: 6px;
        border-bottom: 2px solid #e2e8f0;
    }

    /* Thẻ hồ sơ tóm tắt mã hàng ngăn nắp */
    .meta-box-light {
        background-color: #f8fafc; 
        border-left: 4px solid #0284c7;
        padding: 8px 12px;
        margin-bottom: 8px;
        border-radius: 0 6px 6px 0;
    }
    .meta-label-light { font-size: 11px; font-weight: 700; color: #64748b; text-transform: uppercase; }
    .meta-value-light { font-size: 13px; font-weight: 600; color: #0f172a; margin-top: 1px; }
</style>
""", unsafe_allow_html=True)

# Khởi tạo an toàn cấu trúc trạng thái hệ thống
if "bom_data" not in st.session_state: st.session_state.bom_data = None
if "chat_history" not in st.session_state: st.session_state.chat_history = []
if "pdf_bytes" not in st.session_state: st.session_state.pdf_bytes = None
if "pdf_name" not in st.session_state: st.session_state.pdf_name = ""
if "pdf_text_cache" not in st.session_state: st.session_state.pdf_text_cache = None
if "accumulated_bom_rows" not in st.session_state: st.session_state.accumulated_bom_rows = {}

# Khối tự động trích xuất chữ khi nạp file PDF
if st.session_state.pdf_bytes is not None and st.session_state.pdf_text_cache is None:
    try:
        import fitz
        doc = fitz.open(stream=st.session_state.pdf_bytes, filetype="pdf")
        full_text_extract = ""
        for page_num in range(len(doc)):
            full_text_extract += f"\n--- TRANG THỨ {page_num + 1} ---\n" + doc.load_page(page_num).get_text("text")
        st.session_state.pdf_text_cache = full_text_extract
    except Exception: pass

# ĐỒNG BỘ DỮ LIỆU KPIs BIẾN THIÊN THEO THỜI GIAN THỰC
kpi_style_id = "N/A"
total_materials = len(st.session_state.accumulated_bom_rows) if st.session_state.accumulated_bom_rows else 0
main_fabric_cons = "0.000"
active_size_kpi = "AUTOMATIC"

if st.session_state.get("bom_data") and "bom_rows" in st.session_state.bom_data:
    kpi_style_id = str(st.session_state.bom_data.get("style_code", "R09-450416")).upper()
    active_size_kpi = str(st.session_state.bom_data.get("calculated_on_size", "MEDIAN")).upper()
    if total_materials == 0: total_materials = len(st.session_state.bom_data["bom_rows"])
    for row in st.session_state.bom_data["bom_rows"]:
        if not row: continue
        if "MAIN" in str(row.get("fabric_classification", "")).upper() or "MAIN" in str(row.get("component_type", "")).upper():
            val_gross = row.get("calculated_gross_consumption_yds", 0.0)
            if val_gross > 0.0:
                main_fabric_cons = f"{val_gross:.3f} Yds"
                break

# VẼ KHỐI CỐ ĐỊNH GHIM LÊN ĐỈNH MÀN HÌNH (LUÔN NỔI LÊN TRÊN CÙNG)
st.markdown('<div class="sticky-top-container">', unsafe_allow_html=True)
st.markdown("""
<div class="top-banner">
    <div class="top-title">📊 INTELLIGENT FABRIC CONSUMPTION PLATFORM</div>
    <div class="top-subtitle">Hệ thống phân tích rập hình học và tự động tính toán định mức kỹ thuật dệt may bằng AI CORE</div>
</div>
""", unsafe_allow_html=True)

k_col1, k_col2, k_col3, k_col4 = st.columns(4)
with k_col1: st.markdown(f'<div class="kpi-card-colored bg-style"><div class="kpi-num-light">{kpi_style_id}</div><div class="kpi-lbl-light">Mã hàng đang xử lý</div></div>', unsafe_allow_html=True)
with k_col2: st.markdown(f'<div class="kpi-card-colored bg-items"><div class="kpi-num-light">{total_materials} Item(s)</div><div class="kpi-lbl-light">Tổng số vật tư kết xuất</div></div>', unsafe_allow_html=True)
with k_col3: st.markdown(f'<div class="kpi-card-colored bg-cons"><div class="kpi-num-light" style="font-size:22px;">{main_fabric_cons}</div><div class="kpi-lbl-light">Định mức vải chính dự kiến</div></div>', unsafe_allow_html=True)
with k_col4: st.markdown(f'<div class="kpi-card-colored bg-size"><div class="kpi-num-light">{active_size_kpi}</div><div class="kpi-lbl-light">Cỡ hạt tính định mức</div></div>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="main-body-spacer"></div>', unsafe_allow_html=True)



# =====================================================================
# ĐOẠN 6b: KHỐI CHIA CỘT ĐỐI XỨNG - KHỐNG CHẾ TRỰC TIẾP CHIỀU CAO ẢNH (V18.3.5.0 APPROVED)
# =====================================================================

# 🌟 BỘ CSS PHÒNG VỆ: Ép trực tiếp mọi thẻ ảnh (img) nằm trong khung Sketch phải co nhỏ lại vừa vặn
st.markdown("""
<style>
    /* Ép tất cả các hình ảnh nằm trong cột bên phải khống chế chiều cao tối đa, */
    /* tự động giữ nguyên tỷ lệ rập phẳng mà không bị kéo giãn to đùng */
    .sticky-sketch-box img {
        max-height: 290px !important;
        width: auto !important;
        object-fit: contain !important;
        margin: 0 auto !important;
        display: block !important;
    }
</style>
""", unsafe_allow_html=True)

# --- SIDEBAR ENGINE CONTROLS CONTROL PANEL ---
st.sidebar.markdown("### ⚙️ ENGINE CONTROLS")
if st.sidebar.button("🗑️ CLEAR SYSTEM MEMORY", use_container_width=True):
    st.session_state.bom_data = None
    st.session_state.chat_history = []
    st.session_state.pdf_bytes = None
    st.session_state.pdf_name = ""
    st.session_state.pdf_text_cache = None
    if "pdf_page_one_image" in st.session_state: st.session_state.pdf_page_one_image = None
    if "accumulated_bom_rows" in st.session_state: del st.session_state["accumulated_bom_rows"]
    st.rerun()

# LƯỚI CHIA ĐÔI CỘT ĐỐI XỨNG CÂN BẰNG THỊ GIÁC ĐỀU NHAU
col_left, col_right = st.columns(2)

# --- CỘT TRÁI: BỘ TẢI FILE & HỒ SƠ TÓM TẮT MÃ HÀNG ---
with col_left:
    st.markdown('<div class="custom-erp-box">', unsafe_allow_html=True)
    st.markdown('<div class="cad-header-text">📂 TECHPACK UPLOADER & PROFILE SUMMARY</div>', unsafe_allow_html=True)
    
    uploaded_file = st.file_uploader("Upload PDF", type=["pdf"], label_visibility="collapsed")
    
    if uploaded_file is not None:
        if st.session_state.pdf_name != uploaded_file.name:
            st.session_state.pdf_text_cache = None
            if "pdf_page_one_image" in st.session_state: st.session_state.pdf_page_one_image = None
            if "accumulated_bom_rows" in st.session_state: del st.session_state["accumulated_bom_rows"]
        st.session_state.pdf_bytes = uploaded_file.read()
        st.session_state.pdf_name = uploaded_file.name

    if st.session_state.pdf_text_cache is not None:
        st.markdown("<div style='margin-top: 10px;'></div>", unsafe_allow_html=True)
        txt = st.session_state.pdf_text_cache
        
        import re
        def get_meta(pattern, default="N/A"):
            m = re.search(pattern, txt, re.IGNORECASE)
            return m.group(1).strip() if m else default

        style_id = get_meta(r'(?:Style ID|Style_ID|Mã hàng)\s*[:\-=\s]*([\w\d\-]+)', st.session_state.pdf_name.replace(".pdf",""))
        short_desc = get_meta(r'(?:Short Desc|Description|Tên sản phẩm)\s*[:\-=\s]*([^\n]+)', "THE TWILL CARGO PANTS")
        customer = get_meta(r'(?:Customer|Khách hàng|Brand)\s*[:\-=\s]*([^\n]+)', "REITMANS")
        season = get_meta(r'(?:Season|Mùa hàng)\s*[:\-=\s]*([^\n]+)', "Spring 2027")
        fabric_type = get_meta(r'(?:Long Description|Chất liệu gốc)\s*[:\-=\s]*([^\n]+)', "CASUAL TWILL PANTS - SP27")

        m_col1, m_col2 = st.columns(2)
        with m_col1:
            st.markdown(f'<div class="meta-box-light"><div class="meta-label-light">Style Code / Mã hàng</div><div class="meta-value-light"><b>{style_id}</b></div></div>', unsafe_allow_html=True)
            st.markdown(f'<div class="meta-box-light"><div class="meta-label-light">Customer / Đối tác</div><div class="meta-value-light">{customer}</div></div>', unsafe_allow_html=True)
            st.markdown(f'<div class="meta-box_light"><div class="meta-label-light">Season / Mùa sản xuất</div><div class="meta-value-light">{season}</div></div>', unsafe_allow_html=True)
        with m_col2:
            st.markdown(f'<div class="meta-box-light"><div class="meta-label-light">Garment Type / Kiểu dáng</div><div class="meta-value-light">{short_desc}</div></div>', unsafe_allow_html=True)
            st.markdown(f'<div class="meta-box-light"><div class="meta-label-light">Material Spec / Mô tả vải</div><div class="meta-value-light">{fabric_type[:28]}...</div></div>', unsafe_allow_html=True)
            st.markdown(f'<div class="meta-box-light"><div class="meta-label-light">Techpack Status</div><div class="meta-value-light" style="color: #16a34a;">🟢 READY TO BOM</div></div>', unsafe_allow_html=True)
    else:
        if st.session_state.pdf_bytes is None:
            st.markdown("<div style='margin-top: 40px; text-align: center; color: #64748b; font-size: 13px;'>Bảng tóm tắt thông số sản phẩm sẽ tự động hiển thị tại đây sau khi nạp file PDF.</div>", unsafe_allow_html=True)
        
    st.markdown('</div>', unsafe_allow_html=True)


# --- CỘT PHẢI: KHUNG XEM BẢN VẼ PHẲNG SKETCH (🌟 ĐÃ ÉP CO NHỎ ẢNH GỐC) ---
with col_right:
    # Bọc thêm một class định danh riêng sticky-sketch-box phục vụ ép co ảnh
    st.markdown('<div class="custom-erp-box sticky-sketch-box">', unsafe_allow_html=True)
    st.markdown('<div class="cad-header-text">🎨 TECHPACK SKETCH VISUALIZER</div>', unsafe_allow_html=True)
    
    if "pdf_page_one_image" in st.session_state and st.session_state.pdf_page_one_image is not None:
        st.image(st.session_state.pdf_page_one_image, use_container_width=True)
    else:
        st.markdown("<div style='margin-top: 50px; text-align: center; color: #64748b; font-size: 13px;'>Hình vẽ phác họa phẳng (Sketch) trích xuất từ trang bìa PDF sẽ tự động hiển thị cân xứng tại đây.</div>", unsafe_allow_html=True)
        
    st.markdown('</div>', unsafe_allow_html=True)









# =====================================================================
# ĐOẠN 7a - PHẦN 1: KHUNG HỘI THOẠI & LỊCH SỬ WORKSPACE (UI CHAT)
# =====================================================================
st.markdown('<br><div class="cad-card"><div class="cad-header">💬 CHATGPT IE COLLABORATION WORKSPACE</div>', unsafe_allow_html=True)

if "chat_history" not in st.session_state: st.session_state.chat_history = []
if "pdf_page_one_image" not in st.session_state: st.session_state.pdf_page_one_image = None
if "accumulated_bom_rows" not in st.session_state: st.session_state.accumulated_bom_rows = {}
if "current_warp_pct" not in st.session_state: st.session_state.current_warp_pct = "3.0%"
if "current_weft_pct" not in st.session_state: st.session_state.current_weft_pct = "3.0%"

if st.session_state.chat_history:
    for msg in st.session_state.chat_history:
        st.chat_message("user").write(msg["user"])
        st.chat_message("assistant").write(msg["ai"])

safe_user_prompt = st.chat_input("Gõ câu lệnh điều chỉnh thông số tại đây...")
st.markdown('</div>', unsafe_allow_html=True)
# =====================================================================
# ĐOẠN 7a - PHẦN 2: CORE AI ENGINE & BỘ TRÍCH XUẤT THÔNG SỐ CO RÚT ĐỘNG
# =====================================================================
if st.session_state.pdf_bytes is not None and safe_user_prompt:
    current_query = str(safe_user_prompt).strip()
    
    with st.spinner("🧠 AI Core đang bóc tách rập ảnh Sketch phẳng và đối chiếu bảng BOM đa trang..."):
        try:
            import google.generativeai as genai
            import json, copy, traceback, re
            import fitz 
            
            if st.session_state.pdf_page_one_image is None:
                doc_recovery = fitz.open(stream=st.session_state.pdf_bytes, filetype="pdf")
                st.session_state.pdf_page_one_image = doc_recovery.load_page(0).get_pixmap(dpi=150).tobytes("png")
            
            if "GEMINI_API_KEY" in st.secrets: 
                genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
                
            model = genai.GenerativeModel("gemini-2.5-flash", generation_config={"temperature": 0.2})
            chat_lower = current_query.lower()
            
            # Bộ trích xuất thông số kỹ thuật động thông minh
            match_size = re.search(r'\b(?:size|sz|cỡ)\s*[:\-=\s]*([\w\d]+)\b', chat_lower)
            target_size_cmd = str(match_size.group(1)).upper().strip() if match_size else "30"
            
            match_w = re.search(r'\b(?:khổ|kho|width)\s*[:\-=\s]*([\d\.]+)\b', chat_lower)
            active_width = float(match_w.group(1)) if match_w else 58.0
            
            # 🌟 VÁ LỖI HỆ SỐ CO RÚT ĐỘNG CHUẨN HOÁ % THEO YÊU CẦU NGƯỜI DÙNG
            active_warp = 3.0
            active_weft = 3.0
            
            match_warp = re.search(r'(?:dọc|doc|warp)\s*[:\-=\s]*([\d\.]+)', chat_lower)
            match_weft = re.search(r'(?:ngang|weft)\s*[:\-=\s]*([\d\.]+)', chat_lower)
            
            if match_warp:
                try: active_warp = float(match_warp.group(1))
                except Exception: pass
            if match_weft:
                try: active_weft = float(match_weft.group(1))
                except Exception: pass
                
            if not match_warp or not match_weft:
                match_sh_pair = re.search(r'(?:co\s*rút|co\s*rut|co|shrinkage)\s*[:\-=\s]*([\d\.]+)\s*(?:-|–|x|ngang|dọc|\s+)\s*([\d\.]+)', chat_lower)
                if match_sh_pair:
                    try:
                        active_warp = float(match_sh_pair.group(1))
                        active_weft = float(match_sh_pair.group(2))
                    except Exception: pass

            # Lưu trực tiếp vào session_state để khóa thông số hiển thị cố định ở Đoạn 7b
            st.session_state.current_warp_pct = f"{active_warp}%"
            st.session_state.current_weft_pct = f"{active_weft}%"

            # Chuẩn hóa hệ số toán học phần trăm cho Fabric Registry Cache trước khi đẩy vào IE Engine
            factory_warp_factor = 1.0 + (active_warp / 100.0) if active_warp > 1.0 else 1.03
            factory_weft_factor = 1.0 + (active_weft / 100.0) if active_weft > 1.0 else 1.03

            if "_fabric_registry_cache" not in st.session_state:
                st.session_state._fabric_registry_cache = {}
            
            st.session_state._fabric_registry_cache["DENIM_SOLID COLOR_TWO_WAY_0"] = {
                "shrink_warp_f": factory_warp_factor, "shrink_weft_f": factory_weft_factor
            }

            if len(st.session_state.chat_history) > 30:
                st.session_state.chat_history = st.session_state.chat_history[-30:]

            prompt_instruction = f"""
            You are a senior apparel IE system. Analyze BOTH the visual sketch image and the techpack text data.
            DATA FOUND IN TECHPACK TEXT (BOM SHEET): {st.session_state.pdf_text_cache}
            CONTEXT HISTORY: {json.dumps(st.session_state.chat_history, ensure_ascii=False)}
            CURRENT USER COMMAND: "{current_query}"
            
            STRICT COMPONENT RULES:
            1. Front/Back bodies, Waistband, side cargo pockets, and pocket flaps must be allocated under "MAIN FABRIC".
            2. Piped/Welt back pockets require pocket bags made of LINING fabric. Put this item under "POCKET LINING / LÓT TÚI".
            3. Waistband fusing requires fusible interlining. Put this item under "INTERLINING / KEO LÓT".
            4. You MUST structure the output JSON to include exactly THREE rows in the "bom_rows" array. Do NOT drop or omit rows.
            
            Target size: '{target_size_cmd}', Cut Width: {active_width} inches, Warp: {active_warp}%, Weft: {active_weft}%.
            
            Return response in exact format:
            ===START_JSON===
            {{
              "detected_product_type": "CARGO_PANT", "style_code": "R09-500778", "calculated_on_size": "{target_size_cmd}",
              "_fabric_registry_cache": {{ "DENIM_SOLID COLOR_TWO_WAY_0": {{ "shrink_warp_f": {factory_warp_factor}, "shrink_weft_f": {factory_weft_factor} }} }},
              "bom_rows": [
                {{
                  "component_type": "MAIN FABRIC", "placement": "BODY/POCKETS", "fabric_classification": "MAIN_FABRIC",
                  "fabric_code": "DENIM", "fabric_color": "SOLID COLOR", "fabric_width_inch": {active_width},
                  "_btp_total_panel_area": 2520.0, "_btp_total_piece_count": 14.0,
                  "panels_catalog": [
                    {{ "panel_name": "FRONT_PANEL", "piece_count": 2.0, "piece_length_inch": 41.5, "piece_width_inch": 13.0 }},
                    {{ "panel_name": "BACK_PANEL", "piece_count": 2.0, "piece_length_inch": 42.0, "piece_width_inch": 15.5 }},
                    {{ "panel_name": "SIDE_CARGO_POCKET", "piece_count": 2.0, "piece_length_inch": 9.5, "piece_width_inch": 8.5 }},
                    {{ "panel_name": "CARGO_POCKET_FLAP", "piece_count": 4.0, "piece_length_inch": 3.5, "piece_width_inch": 8.5 }},
                    {{ "panel_name": "WAISTBAND", "piece_count": 2.0, "piece_length_inch": 34.0, "piece_width_inch": 3.5 }},
                    {{ "panel_name": "BACK_POCKET", "piece_count": 2.0, "piece_length_inch": 6.5, "piece_width_inch": 6.0 }}
                  ]
                }},
                {{
                  "component_type": "INTERLINING / KEO LÓT", "placement": "WAISTBAND", "fabric_classification": "FUSING",
                  "fabric_code": "TRICOT FUSING", "fabric_color": "WHITE", "fabric_width_inch": {active_width},
                  "_is_fusing": true, "_btp_total_panel_area": 238.0, "_btp_total_piece_count": 2.0, "panels_catalog": []
                }},
                {{
                  "component_type": "POCKET LINING / LÓT TÚI", "placement": "POCKET BAGS", "fabric_classification": "LINING",
                  "fabric_code": "TC POCKETING", "fabric_color": "NATURAL", "fabric_width_inch": {active_width},
                  "_is_lining": true, "_btp_total_panel_area": 312.0, "_btp_total_piece_count": 4.0, "panels_catalog": []
                }}
              ]
            }}
            ===END_JSON===
            ===START_CHAT===
            Tôi đã đồng bộ tính toán định mức chuẩn xác cho khổ vải {active_width} inch với độ co rút dọc {active_warp}% và ngang {active_weft}% dựa trên cấu trúc rập phân bổ thực tế.
            ===END_CHAT===
            """
            
            image_payload = {"mime_type": "image/png", "data": st.session_state.pdf_page_one_image}
            response = model.generate_content([image_payload, prompt_instruction])
            
            if response and response.text:
                response_text = response.text.strip()
                json_match = re.search(r'===START_JSON===\s*(.*?)\s*===END_JSON===', response_text, re.DOTALL)
                chat_match = re.search(r'===START_CHAT===\s*(.*?)\s*===END_CHAT===', response_text, re.DOTALL)
                
                if json_match:
                    raw_json_str = json_match.group(1).strip()
                    raw_json_str = re.sub(r"^```json\s*|\s*```$", "", raw_json_str, flags=re.IGNORECASE)
                    
                    raw_blueprint = json.loads(raw_json_str)
                    if raw_blueprint and raw_blueprint.get("bom_rows"):
                        blueprint_worker = copy.deepcopy(raw_blueprint)
                        blueprint_worker["_fabric_registry_cache"] = st.session_state._fabric_registry_cache
                        blueprint_final = allocate_fabric_consumption_and_quality_gate(blueprint_worker, current_query)
                        
                        st.session_state.active_blueprint = blueprint_final
                        ai_chat_response = chat_match.group(1).strip() if chat_match else "Tôi đã đồng bộ tính toán định mức."
                        st.session_state.chat_history.append({"user": current_query, "ai": ai_chat_response})
                        st.rerun()
                else:
                    st.error("⚠️ AI Engine không xuất được cấu trúc JSON hợp lệ. Vui lòng thử lại câu lệnh.")
        except Exception as ce:
            st.error(f"❌ Lỗi xử lý Core AI Engine: {str(ce)}")
# =====================================================================
# ĐOẠN 7b: KHU VỰC HIỂN THỊ KẾT QUẢ ĐƠN MÃ VÀ XUẤT EXCEL CHUẨN ĐỒNG BỘ CO RÚT ĐỘNG
# =====================================================================
active_bom_source = None
if st.session_state.get("active_blueprint") and "bom_rows" in st.session_state.active_blueprint:
    active_bom_source = st.session_state.active_blueprint
elif st.session_state.get("accumulated_bom_rows"):
    active_bom_source = {"calculated_on_size": "30", "bom_rows": list(st.session_state.accumulated_bom_rows.values())}

if active_bom_source and active_bom_source.get("bom_rows"):
    import pandas as pd
    extracted_size = active_bom_source.get("calculated_on_size", "30").upper()
    
    st.markdown('<div class="cad-card">', unsafe_allow_html=True)
    st.markdown(f'<div class="cad-header">📊 CALCULATED FABRIC CONSUMPTION MATRIX (SIZE TARGET: {extracted_size})</div>', unsafe_allow_html=True)
    
    warp_default = st.session_state.get("current_warp_pct", "3.0%")
    weft_default = st.session_state.get("current_weft_pct", "3.0%")
    
    display_data = []
    for r in active_bom_source["bom_rows"]:
        if not r or not isinstance(r, dict): continue
        sys_notes = r.get("consumption_note", "")
        current_gross = r.get("calculated_gross_consumption_yds", 0.0)
        
        cut_width_val = f"{float(r['fabric_width_inch'])} inch" if "fabric_width_inch" in r and r["fabric_width_inch"] > 0 else "58.0 inch"
        warp_val = "0.0%" if any(x in str(r.get("fabric_classification", "")).upper() for x in ["FUSING", "LINING"]) else warp_default
        weft_val = "0.0%" if any(x in str(r.get("fabric_classification", "")).upper() for x in ["FUSING", "LINING"]) else weft_default

        raw_eff_value = r.get("marker_efficiency_pct")
        raw_eff_value = f"{raw_eff_value}%" if isinstance(raw_eff_value, (int, float)) else ("85.0%" if any(x in str(r.get("fabric_classification", "")).upper() for x in ["FUSING", "LINING"]) else "87.0%")
        gate_status_label = "PASSED" if r.get("quality_gate_status") == "PASSED_MIN" else r.get("quality_gate_status", r.get("status", "PASSED"))

        display_data.append({
            "Component Type": r.get("component_type", "MAIN FABRIC"), "Placement": r.get("placement", "BODY/POCKETS"),
            "Fabric Classification": r.get("fabric_classification", "MAIN_FABRIC"), "Fabric Code": r.get("fabric_code", "DENIM"),
            "Fabric Color": r.get("fabric_color", "SOLID COLOR"), "Khổ vải (Width)": cut_width_val,
            "Co rút dọc (% Warp)": warp_val, "Co rút ngang (% Weft)": weft_val, "Marker Efficiency": str(raw_eff_value).strip(),
            "Gross Consumption (Yds)": current_gross, "Quality Status": gate_status_label, "System Notes": sys_notes
        })
        
    df_bom = pd.DataFrame(display_data)
    st.dataframe(df_bom, use_container_width=True, hide_index=True)
    st.markdown('</div>', unsafe_allow_html=True)
    
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
        
        ws.merge_cells("A1:L1")
        ws["A1"] = f"BÁO CÁO ĐỊNH MỨC VẬT TƯ VẢI (SIZE: {extracted_size}) - STYLE: R09-500778"
        ws["A1"].font = Font(name="Calibri", size=14, bold=True, color="FFFFFF")
        ws["A1"].fill = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
        ws["A1"].alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        ws.row_dimensions.height = 40
        
        headers = list(df_bom.columns)
        for col_num, header_title in enumerate(headers, 1):
            cell = ws.cell(row=3, column=col_num, value=header_title)
            cell.font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
            cell.fill = PatternFill(start_color="2C3E50", end_color="2C3E50", fill_type="solid")
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cell.border = Border(left=Side(style="thin", color="D9D9D9"), right=Side(style="thin", color="D9D9D9"), top=Side(style="thin", color="D9D9D9"), bottom=Side(style="thin", color="D9D9D9"))
        ws.row_dimensions.height = 28
        
        for row_num, row_data in enumerate(display_data, 4):
            ws.row_dimensions[row_num].height = 22
            for col_num, key in enumerate(headers, 1):
                cell = ws.cell(row=row_num, column=col_num, value=row_data[key])
                cell.font = Font(name="Calibri", size=11)
                cell.border = Border(left=Side(style="thin", color="D9D9D9"), right=Side(style="thin", color="D9D9D9"), top=Side(style="thin", color="D9D9D9"), bottom=Side(style="thin", color="D9D9D9"))
                if key in ["Gross Consumption (Yds)"]:
                    cell.alignment = Alignment(horizontal="right", vertical="center")
                    cell.number_format = '#,##0.0000'
                elif key in ["Khổ vải (Width)", "Co rút dọc (% Warp)", "Co rút ngang (% Weft)", "Marker Efficiency", "Quality Status"]:
                    cell.alignment = Alignment(horizontal="center", vertical="center")
                else:
                    cell.alignment = Alignment(horizontal="left", vertical="center")
        
        for col_idx, col_name in enumerate(headers, 1):
            max_len = max([len(str(ws.cell(row=r, column=col_idx).value or '')) for r in range(4, 4 + len(display_data))] + [len(col_name)])
            ws.column_dimensions[get_column_letter(col_idx)].width = max(max_len + 5, 12)
            
        wb.save(output)
        st.markdown("<br>", unsafe_allow_html=True)
        st.download_button(label="📥 XUẤT FILE EXCEL ĐỊNH MỨC CHUẨN SẢN XUẤT", data=output.getvalue(), file_name=f"BOM_Consumption_R09-500778_Size_{extracted_size}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
    except Exception as e:
        st.warning(f"⚠️ Không thể khởi tạo nút xuất Excel cao cấp: {str(e)}")
else:
    st.info("💡 Hệ thống đang chờ câu lệnh phân bổ dữ liệu rập hoặc BOM gốc...")
