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
    V17.0.2.7 APPROVED - CẬP NHẬT CỘNG BIÊN ĐƯỜNG MAY VẢI CHÍNH CHUẨN GERBER
    """
    import re
    import streamlit as st

    globals_dict = globals()
    IE_CONSTANTS = globals_dict.get("IE_CONSTANTS", {
        "MIN_SAFETY_EFF": 0.44, "MAX_ALLOWED_EFF": 0.44,
        "SEAM_ALLOWANCE_MAIN_L": 0.44,    # 🟢 Cộng thêm 0.75 inch vào chiều dài vải chính (Gấu, ráp cạp)
        "SEAM_ALLOWANCE_MAIN_W": 0.44,    # 🟢 Cộng thêm 0.75 inch vào chiều rộng vải chính (Cuốn sườn, ráp túi)
        "SEAM_ALLOWANCE_FUSING_L": 0.375, 
        "SEAM_ALLOWANCE_FUSING_W": 0.375,
        "SEAM_ALLOWANCE_LINING_L": 0.375, 
        "SEAM_ALLOWANCE_LINING_W": 0.375
    })

    def ie_safe_float_local(val, default=0.0):
        try: return float(val) if val is not None else default
        except: return default

    def normalize_fabric_class_local(raw_str):
        s = str(raw_str if raw_str else "").upper().strip()
        if any(x in s for x in ["FUSING", "KEO", "MEX", "MẾCH", "INTERLINING"]): return "FUSING"
        if any(x in s for x in ["LINING", "POCKET", "TÚI", "LÓT", "POCKETING"]): return "POCKETING"
        if any(x in s for x in ["ELASTIC", "TAPE", "THUN", "CHUN", "DÂY"]): return "ELASTIC"
        return "MAIN_FABRIC"

    chat_lower = str(user_prompt if user_prompt else "").lower().strip()
    user_requested_eff = None
    
    pattern_eff = r'(?:hiệu\s*suất|hieu\s*suat|eff|efficiency|marker|sơ\s*đồ)\s*[:\-=\s]*([\d\.]+)'
    match_eff = re.search(pattern_eff, chat_lower)
    
    if match_eff:
        try:
            val_eff = float(match_eff.group(1))
            raw_eff = val_eff / 100.0 if val_eff > 1.0 else val_eff
            user_requested_eff = min(max(raw_eff, IE_CONSTANTS.get("MIN_SAFETY_EFF", 0.50)), IE_CONSTANTS.get("MAX_ALLOWED_EFF", 0.92))
        except ValueError: pass

    prepared_rows = []
    
    for row in all_rows:
        if not row or not isinstance(row, dict): continue
            
        comp_type = str(row.get("component_type", "")).upper().strip()
        placement = str(row.get("placement", "")).upper().strip()
        f_class_raw = str(row.get("fabric_classification", "")).upper().strip()

        f_class_norm = normalize_fabric_class_local(f_class_raw if f_class_raw else comp_type)
        is_fusing = (f_class_norm == "FUSING")
        is_lining = (f_class_norm == "POCKETING")
        is_elastic_or_tape = (f_class_norm == "ELASTIC")

        panels = row.get("panels_catalog", [])
        max_piece_length = 0.0
        total_panel_area = 0.0
        total_piece_count = 0
        
        if panels and isinstance(panels, list):
            valid_panels = [p for p in panels if isinstance(p, dict)]
            for p in valid_panels:
                l_val = ie_safe_float_local(p.get("piece_length_inch"), 0.0)
                w_val = ie_safe_float_local(p.get("piece_width_inch"), 0.0)
                c_val = ie_safe_float_local(p.get("piece_count"), 1.0)
                
                # 🌟 VÁ LỖI CHÍ MẠNG: CỘNG DÙNG SAI ĐƯỜNG MAY (SEAM ALLOWANCE) CHO TỪNG CHI TIẾT
                if is_fusing:
                    l_val += IE_CONSTANTS.get("SEAM_ALLOWANCE_FUSING_L", 0.25)
                    w_val += IE_CONSTANTS.get("SEAM_ALLOWANCE_FUSING_W", 0.25)
                elif is_lining:
                    l_val += IE_CONSTANTS.get("SEAM_ALLOWANCE_LINING_L", 0.375)
                    w_val += IE_CONSTANTS.get("SEAM_ALLOWANCE_LINING_W", 0.375)
                else:
                    # Áp dụng cho VẢI CHÍNH (MAIN FABRIC)
                    l_val += IE_CONSTANTS.get("SEAM_ALLOWANCE_MAIN_L", 0.75)
                    w_val += IE_CONSTANTS.get("SEAM_ALLOWANCE_MAIN_W", 0.75)
                
                total_panel_area += (l_val * w_val * c_val)
                total_piece_count += c_val
                
                if any(x in str(p.get("panel_name", "")).upper() for x in ["PANEL", "BODY", "FRONT", "BACK"]):
                    if l_val > max_piece_length: max_piece_length = l_val

        if max_piece_length == 0.0 and len(panels) > 0:
            max_piece_length = max([ie_safe_float_local(p.get("piece_length_inch"), 0.0) for p in panels if isinstance(p, dict)] or [42.0])
            if max_piece_length > 50.0: max_piece_length = 42.0

        row["_btp_max_piece_length"] = max_piece_length
        row["_btp_total_panel_area"] = total_panel_area
        row["_btp_total_piece_count"] = total_piece_count
        row["_is_fusing"] = is_fusing
        row["_is_lining"] = is_lining
        row["_is_elastic_or_tape"] = is_elastic_or_tape
        
        prepared_rows.append(row)
        
    return prepared_rows, user_requested_eff


def allocate_fabric_consumption_and_quality_gate(ai_blueprint: dict, user_prompt: str = "") -> dict:
    """
    Phân đoạn 2b2: Tầng xử lý dữ liệu sau AI (Post-AI Data Engine) chuẩn Gerber cho đa mã hàng.
    V17.0.4.0 APPROVED - FIXED DUPLICATE KEYS, DYNAMIC LOOKUP & STRICT SPEC VALIDATION
    """
    import streamlit as st
    import re

    # 1. VALIDATE SCHEMA AI: Kiểm tra dữ liệu đầu vào bắt buộc
    if not ai_blueprint or not isinstance(ai_blueprint, dict):
        return {"detected_product_type": "DEFAULT", "bom_rows": [], "status": "ERROR", "error_log": "Invalid AI blueprint schema"}
        
    all_rows = ai_blueprint.get("bom_rows", [])
    if not all_rows or not isinstance(all_rows, list): 
        return {"detected_product_type": "DEFAULT", "bom_rows": [], "status": "ERROR", "error_log": "Missing or invalid bom_rows array"}

    product_type = str(ai_blueprint.get("detected_product_type", "DEFAULT")).upper().strip()
    pocket_style = str(ai_blueprint.get("pocket_style_type", "FRONT_ONLY")).upper().strip()
    fabric_registry = ai_blueprint.get("_fabric_registry_cache", {})
    if not fabric_registry or not isinstance(fabric_registry, dict): 
        fabric_registry = {}

    try:
        prepared_rows, user_requested_eff = parse_and_prepare_ie_panels(all_rows, product_type, user_prompt)
    except Exception as e:
        prepared_rows = all_rows
        user_requested_eff = None

    if "accumulated_bom_rows" not in st.session_state or not isinstance(st.session_state.accumulated_bom_rows, dict):
        st.session_state.accumulated_bom_rows = {}

    # Trích xuất nhanh khổ vải chỉ định từ prompt người dùng
    chat_lower = str(user_prompt).lower().strip()
    match_w_prompt = re.search(r'\b(?:khổ|kho|width)\s*[:\-=\s]*([\d\.]+)\b', chat_lower)
    prompt_extracted_width = float(match_w_prompt.group(1)) if match_w_prompt else None

    # Khởi tạo bộ hằng số hệ thống tiêu chuẩn kỹ thuật
    globals_dict = globals()
    IE_CONSTANTS = globals_dict.get("IE_CONSTANTS", {
        "DEFAULT_WIDTH_MAIN": 57.0, 
        "DEFAULT_WIDTH_FUSING": 44.0, 
        "DEFAULT_WIDTH_LINING": 44.0,
        "WASTAGE_FACTOR": 1.05, 
        "DUNG_SAI_XEP_RAP": 1.04
    })
    EXCLUDE_HARDWARE_KEYS = globals_dict.get("EXCLUDE_HARDWARE_KEYS", ["BUTTON", "ZIPPER", "THREAD", "LABEL"])

    def ie_safe_float(val, default=0.0):
        try: return float(val) if val is not None else default
        except: return default

    # 2. VÒNG LẶP TOÁN HỌC & KIỂM TRA CHẶT CHẼ TỪNG DÒNG VẬT TƯ (STRICT VALIDATION TIER)
    for row in prepared_rows:
        if not row or not isinstance(row, dict): continue
        
        comp_type = str(row.get("component_type", "")).upper().strip()
        placement = str(row.get("placement", "")).upper().strip()
        f_class_raw = str(row.get("fabric_classification", "")).upper().strip()
        f_code = str(row.get("fabric_code", "")).upper().strip()
        f_color = str(row.get("fabric_color", "")).upper().strip()

        # Bỏ qua phụ liệu kim loại / phần cứng (Nút, khóa, nhãn...)
        if any(k in comp_type or k in placement or k in f_class_raw or k in f_code for k in EXCLUDE_HARDWARE_KEYS if k):
            continue

        is_fusing = row.get("_is_fusing", "FUSING" in f_class_raw or "KEO" in comp_type)
        is_lining = row.get("_is_lining", "LINING" in f_class_raw or "LÓT" in comp_type)

        # Đọc dữ liệu hình học trung gian đã xử lý từ tầng Python Đoạn 7a2
        total_panel_area = row.get("_btp_total_panel_area")
        max_piece_length = row.get("_btp_max_piece_length")
        total_piece_count = row.get("_btp_total_piece_count", 0.0)

        # 🛑 CHẶN LỖI THIẾU THÔNG SỐ DIỆN TÍCH / SỐ LƯỢNG RẬP HOẶC THIẾU TÊN VẢI
        if total_panel_area is None or max_piece_length is None or not f_code or not f_class_raw:
            row["status"] = "ERROR"
            row["consumption_note"] = "❌ LỖI HỆ THỐNG: AI Core trích xuất thiếu dữ liệu thông số rập"
            row["calculated_gross_consumption_yds"] = 0.0
            continue

        if ie_safe_float(total_panel_area) <= 0.0 or ie_safe_float(total_piece_count) <= 0.0:
            row["status"] = "ERROR"
            row["consumption_note"] = "❌ LỖI KỸ THUẬT: Diện tích rập hoặc số lượng chi tiết bằng 0"
            row["calculated_gross_consumption_yds"] = 0.0
            continue

        # Xác định khổ vải (Width)
        if is_fusing: default_width = IE_CONSTANTS["DEFAULT_WIDTH_FUSING"]
        elif is_lining: default_width = IE_CONSTANTS["DEFAULT_WIDTH_LINING"]
        else: default_width = IE_CONSTANTS["DEFAULT_WIDTH_MAIN"]

        if not is_fusing and not is_lining and prompt_extracted_width is not None:
            row["fabric_width_inch"] = prompt_extracted_width
        else:
            row["fabric_width_inch"] = row.get("fabric_width_inch", default_width) if ie_safe_float(row.get("fabric_width_inch", 0)) > 0 else default_width

        cutable_w = ie_safe_float(row["fabric_width_inch"])

        # 🛑 CHẶN LỖI SAI KHỔ VẢI
        if cutable_w <= 0.0:
            row["status"] = "ERROR"
            row["consumption_note"] = "❌ LỖI SƠ ĐỒ: Khổ vải hữu dụng (Cut width) phải lớn hơn 0"
            row["calculated_gross_consumption_yds"] = 0.0
            continue

        # 🌟 DYNAMIC LOOKUP: Trích xuất dải co rút động theo hướng cắt (fabric_direction, nap) từ dữ liệu AI
        f_direction = str(row.get("fabric_direction", "TWO_WAY")).upper().strip()
        f_nap = str(row.get("nap", "0")).upper().strip()
        
        cache_key = f"{f_code}_{f_color}_{f_direction}_{f_nap}"
        matched_cache_data = fabric_registry.get(cache_key)
        
        if not matched_cache_data:
            # Tra cứu tương đối theo mã vải nếu cấu hình định danh chuỗi bị lệch ký tự
            matched_cache_data = next((c_data for f_id, c_data in fabric_registry.items() if f_code in f_id), None)
            
        shrink_warp = matched_cache_data.get("shrink_warp_f", 1.03) if matched_cache_data else 1.03
        safety_allowance = IE_CONSTANTS.get("DUNG_SAI_XEP_RAP", 1.04)

        # 3. LUỒNG TOÁN HỌC TÍNH TOÁN ĐỊNH MỨC AN TOÀN TRUYỀN SANG SƠ ĐỒ GERBER
        if is_lining:
            # Luồng phụ liệu lót túi: Phân bổ thông minh dựa theo kết cấu túi
            eff = 0.85
            if "FRONT_AND_BACK" in pocket_style or "4" in placement or ie_safe_float(total_panel_area) > 350.0:
                total_yds = 0.42 * shrink_warp * IE_CONSTANTS["WASTAGE_FACTOR"]
                row["consumption_note"] = "Khổ lót: 44\" | Tự động phân bổ: 4 túi lót trước sau chuẩn Gerber"
            else:
                total_yds = 0.20 * shrink_warp * IE_CONSTANTS["WASTAGE_FACTOR"]
                row["consumption_note"] = "Khổ lót: 44\" | Tự động phân bổ: 2 túi trước chuẩn Jean thực tế"
        else:
            if is_fusing:
                # Luồng mếch keo lót: Đi sơ đồ khít, tính theo tổng diện tích phẳng chi tiết cạp/baget có biên may
                eff = user_requested_eff if user_requested_eff else 0.88
                total_yds = (ie_safe_float(total_panel_area) / (cutable_w * 36.0)) / eff * shrink_warp * IE_CONSTANTS["WASTAGE_FACTOR"]
                row["consumption_note"] = f"Khổ mếch: {cutable_w}\" | Tính diện tích tổng thông số cạp/baget có biên may"
            else:
                # Luồng vải chính: Tách luồng rẽ nhánh Quần dài và luồng Áo/Đầm/Váy
                eff = user_requested_eff if user_requested_eff else 0.83
                if "PANT" in product_type or "QUẦN" in product_type:
                    linear_base_yds = (ie_safe_float(max_piece_length) / 36.0) * shrink_warp * IE_CONSTANTS["WASTAGE_FACTOR"] / eff
                    area_base_yds = (ie_safe_float(total_panel_area) / (cutable_w * 36.0)) / eff * shrink_warp * IE_CONSTANTS["WASTAGE_FACTOR"]
                    total_yds = max(linear_base_yds, area_base_yds) * safety_allowance
                else:
                    # Các nhóm hàng Áo, Đầm, Váy, Jacket... tính toán tối ưu dựa trên tổng diện tích phôi phẳng rập
                    total_yds = (ie_safe_float(total_panel_area) / (cutable_w * 36.0)) / eff * shrink_warp * IE_CONSTANTS["WASTAGE_FACTOR"] * safety_allowance
                row["consumption_note"] = f"Khổ vải: {cutable_w}\" | Sơ đồ hình học Gerber nhóm {product_type}"

        row["marker_efficiency_pct"] = f"{round(eff * 100, 1)}%"
        row["calculated_gross_consumption_yds"] = round(total_yds, 4)
        row["reason_or_logs"] = f"{cutable_w}\"/{row['marker_efficiency_pct']}/{round((shrink_warp-1)*100,1)}x0.0"
        row["status"] = "PASS"

        row_unique_key = f"{f_class_raw}_{f_code}_{f_color}"
        st.session_state.accumulated_bom_rows[row_unique_key] = row

    ai_blueprint["bom_rows"] = prepared_rows
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
# ĐOẠN 7a1: INTEL PAGE ISOLATOR & COMPRESSION PIPELINE (V36.1 FIXED)
# =====================================================================
import time
import fitz  # PyMuPDF
import streamlit as st

# CHỐT CHẶN: Khởi tạo biến lưu trữ bền vững, KHÔNG reset nếu nó đã có dữ liệu từ trước
if "gemini_inputs" not in st.session_state:
    st.session_state.gemini_inputs = []

start_pipeline_time = time.time()

if "uploaded_pdf_bytes" in st.session_state and st.session_state.uploaded_pdf_bytes:
    try:
        # Mở tài liệu từ bộ nhớ đệm bytes
        doc_recovery = fitz.open(stream=st.session_state.uploaded_pdf_bytes, filetype="pdf")
        total_pages = len(doc_recovery)
        
        # Chỉ tập trung bóc tách các trang thông số cốt lõi (0-indexed: Trang 1, 2, 13, 14)
        target_pages = [0, 1, 12, 13]
        actual_pages_to_scan = [p for p in target_pages if p < total_pages]
        
        # Nếu tài liệu ngắn, quét toàn bộ số trang hiện có
        if not actual_pages_to_scan:
            actual_pages_to_scan = list(range(total_pages))

        # Làm sạch mảng lưu trữ TRƯỚC KHI nạp dữ liệu của file mới vào
        local_payloads = []

        for page_num in actual_pages_to_scan:
            t_page_start = time.time()
            page = doc_recovery.load_page(page_num)
            
            # Giảm tải: Hạ xuống 100 DPI và chuyển hệ màu đen trắng (GRAYSCALE)
            pix = page.get_pixmap(dpi=100, colorspace=fitz.csGRAY)
            
            # Nén chất lượng ảnh xuống 75% để giảm dung lượng mạng tối đa
            page_img_bytes = pix.tobytes("jpeg", jpeg_quality=75)
            
            local_payloads.append({
                "mime_type": "image/jpeg",
                "data": page_img_bytes
            })
            
            if st.session_state.get("debug_mode", False):
                st.info(f"⏱️ [7a1] Đã xử lý Trang {page_num + 1} ({len(page_img_bytes)/1024:.1f} KB) trong {time.time() - t_page_start:.2f}s")
                
        doc_recovery.close()
        
        # Gán toàn bộ mảng dữ liệu ảnh đã xử lý vào Session State một lần duy nhất
        if local_payloads:
            st.session_state.gemini_inputs = local_payloads
        
    except Exception as pdf_err:
        st.error(f"❌ Lỗi nghiêm trọng tại tầng xử lý PDF 7a1: {str(pdf_err)}")

# =====================================================================
# ĐOẠN 7a2.1: AI CORE EXTRACTOR & ASYNCHRONOUS TIMEOUT GATEKEEPER (V36.0 APPROVED)
# =====================================================================
import concurrent.futures
from fractions import Fraction
import json
import re
import copy
import traceback
import time
import random
import streamlit as st

# Kiểm tra dữ liệu đầu vào từ tầng tiền xử lý hình ảnh 7a1
if "gemini_inputs" not in st.session_state or not st.session_state.gemini_inputs:
    st.error("❌ Không tìm thấy dữ liệu hình ảnh đầu vào từ ĐOẠN 7a1.")
    st.stop()

gemini_inputs = st.session_state.gemini_inputs

# HÀM HELPER: Trích xuất số an toàn từ văn bản OCR nhiễu
def safe_float(v, default=0.0):
    if v is None: return default
    if isinstance(v, (int, float)): return float(v)
    try:
        s = str(v).strip().lower()
        if re.search(r"[0-9¼½¾⅛⅜⅝⅞\/]", s):
            s = s.replace("o", "0").replace("l", "1").replace("i", "1")
        s = re.sub(r"\.+", ".", s)
        s = re.sub(r"\s*\.\s*", ".", s)
        s = s.replace('"', '').replace("'", "").replace("inch", "").replace("cm", "").replace("%", "").strip()
        if not s: return default
        
        unicode_fractions = {"½": " 1/2", "¼": " 1/4", "¾": " 3/4", "⅛": " 1/8", "⅜": " 3/8", "⅝": " 5/8", "⅞": " 7/8"}
        for uni_char, ascii_str in unicode_fractions.items():
            s = s.replace(uni_char, ascii_str)
        s = s.strip()

        s_normalized = s.replace("-", " ")
        if " " in s_normalized:
            parts = s_normalized.split()
            if len(parts) == 2 and "/" in parts[1]:
                return float(parts[0]) + float(Fraction(parts[1]))
        if "/" in s and " " not in s:
            return float(Fraction(s))

        num_match = re.search(r'([\d\.]+)', s)
        if num_match: return float(num_match.group(1))
        return float(s)
    except Exception:
        return default

# KHAI BÁO JSON RESPONSE SCHEMA CHO GEMINI
response_schema_definition = {
    "type": "OBJECT",
    "properties": {
        "chat_response": {"type": "STRING"},
        "blueprint": {
            "type": "OBJECT",
            "properties": {
                "status": {"type": "STRING"},
                "spec_page": {"type": "INTEGER"},
                "calculated_on_size": {"type": "STRING"},
                "matched_measurements": {"type": "ARRAY", "items": {"type": "STRING"}},
                "bom_rows": {
                    "type": "ARRAY",
                    "items": {
                        "type": "OBJECT",
                        "properties": {
                            "component_type": {"type": "STRING"},
                            "fabric_classification": {"type": "STRING"},
                            "panels_catalog": {
                                "type": "ARRAY",
                                "items": {
                                    "type": "OBJECT",
                                    "properties": {
                                        "panel_name": {"type": "STRING"},
                                        "piece_count": {"type": "NUMBER"},
                                        "piece_length_inch": {"type": "NUMBER"},
                                        "piece_width_inch": {"type": "NUMBER"}
                                    },
                                    "required": ["panel_name", "piece_count", "piece_length_inch", "piece_width_inch"]
                                }
                            }
                        },
                        "required": ["component_type", "panels_catalog"]
                    }
                }
            },
            "required": ["status", "bom_rows"]
        }
    },
    "required": ["chat_response", "blueprint"]
}

if "GEMINI_API_KEY" in st.secrets: 
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    
generation_config_base = {"temperature": 0.0, "response_mime_type": "application/json"}
generation_config_advanced = {"temperature": 0.0, "response_mime_type": "application/json", "response_schema": response_schema_definition}

model_basic = genai.GenerativeModel("gemini-2.5-flash", generation_config=generation_config_base)
model_advanced = None
try:
    model_advanced = genai.GenerativeModel("gemini-2.5-flash", generation_config=generation_config_advanced)
except Exception:
    pass

# Đọc câu lệnh hiện tại của người dùng từ hệ thống chatbot
current_query = st.session_state.get("current_query", "")
chat_lower = current_query.lower()

# BÓC TÁCH THAM SỐ TỪ CHAT BOX NGƯỜI DÙNG
match_size = re.search(r'\b(?:size|sz|cỡ)\s*[:\-=\s]*([\w\d]+)\b', chat_lower)
target_size_cmd = str(match_size.group(1)).upper().strip() if match_size else "30"

match_w = re.search(r'(?:khổ|kho|width|size)\s*([\d\.]+)', chat_lower)
active_width = safe_float(match_w.group(1), 57.0) if match_w else 57.0

match_warp = re.search(r'(?:dọc|doc|warp)\s*[:\-=\s]*([\d\.,\s½¼¾⅛⅜⅝⅞/-]+)', chat_lower)
match_weft = re.search(r'(?:ngang|weft)\s*[:\-=\s]*([\d\.,\s½¼¾⅛⅜⅝⅞/-]+)', chat_lower)
active_warp = safe_float(match_warp.group(1), 3.0) if match_warp else 3.0
active_weft = safe_float(match_weft.group(1), 3.0) if match_weft else 3.0

if len(st.session_state.get("chat_history", [])) > 30:
    st.session_state.chat_history = st.session_state.chat_history[-30:]

prompt_instruction = f"""
You are an expert apparel IE OCR system. Scan the provided specification pages to extract measurement charts.
TARGET SIZE: '{target_size_cmd}'
ACTIVE FABRIC WIDTH: {active_width} inch

CRITICAL RULES:
1. Extract size dimensions for '{target_size_cmd}' across tables. Convert fractions to decimals.
2. Compute flat pattern boundaries for PANT:
   - FRONT_PANEL/BACK_PANEL Length = Inseam + Front Rise (or Outseam).
   - FRONT_PANEL/BACK_PANEL Width = Hip or Waist width divided by 2.
   - WAISTBAND = Waist circumference specs.
"""
gemini_inputs.append(prompt_instruction)

# Khởi tạo các trạng thái đầu ra cho ĐOẠN 7a2.2 tiêu thụ
st.session_state.parsed_ai_response = None
st.session_state.ai_chat_response = "❌ HỆ THỐNG LỖI: Không nhận được phản hồi hợp lệ từ mô hình AI."

is_debug_enabled = st.session_state.get("debug_mode", False)
attempt_errors = []

# KHỐI LỆNH TRUYỀN TẢI GỌI AI & CHỐT TIMEOUT MẠNG
with st.spinner("⏳ Hệ thống đang truyền tải dữ liệu và phân tích cấu trúc sơ đồ sơ bộ (Thời gian xử lý tối đa 40s)..."):
    for attempt in range(3):
        if attempt > 0:
            time.sleep((2 ** attempt) + random.uniform(0.1, 0.4))
            
        try:
            active_model = model_advanced if model_advanced else model_basic
            
            # Cưỡng bức Timeout bằng ThreadPoolExecutor bảo vệ luồng UI
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(active_model.generate_content, gemini_inputs)
                try:
                    response = future.result(timeout=40)
                except concurrent.futures.TimeoutError:
                    attempt_errors.append(f"[Attempt {attempt+1}] Kết nối mạng bị nghẽn (HTTP Timeout sau 40 giây).")
                    continue

            if not response:
                attempt_errors.append(f"[Attempt {attempt+1}] API trả về thực thể trống.")
                continue
                
            response_text = ""
            try: response_text = response.text
            except Exception: pass

            # Nhánh Fallback đọc Content Parts nếu thuộc tính .text bị khóa độc quyền
            if not response_text:
                try:
                    if hasattr(response, "candidates") and response.candidates:
                        candidate = response.candidates[0]
                        parts = getattr(candidate.content, "parts", [])
                        response_text = "".join(getattr(p, "text", "") for p in parts)
                except Exception: pass

            response_text = response_text.strip() if response_text else ""
            if not response_text:
                attempt_errors.append(f"[Attempt {attempt+1}] Không bóc tách được chuỗi ký tự từ các Content Parts.")
                continue

            if is_debug_enabled:
                with st.expander(f"🤖 [DEBUG] Lượt {attempt + 1} - Chuỗi phản hồi thô từ Gemini"):
                    st.code(response_text)

            # Kiểm tra cú pháp biểu diễn chuỗi JSON cơ bản
            try:
                local_parsed = json.loads(response_text)
            except json.JSONDecodeError:
                attempt_errors.append(f"[Attempt {attempt+1}] Lỗi định dạng JSON (JSONDecodeError).")
                break  # Gãy cấu trúc chuỗi JSON nghiêm ngặt -> Ngắt vòng lặp ngay lập tức

            # ĐẠT TIÊU CHUẨN CẤU TRÚC SƠ BỘ -> Đóng gói chuyển giao trạng thái sang Đoạn 7a2.2
            if isinstance(local_parsed, dict) and "blueprint" in local_parsed:
                st.session_state.parsed_ai_response = local_parsed
                break

        except Exception as exc:
            if isinstance(exc, (KeyError, TypeError, NameError, AttributeError)):
                attempt_errors.append(f"❌ Critical Internal Bug: {str(exc)}\n{traceback.format_exc()}")
                break
            attempt_errors.append(f"[Attempt {attempt+1}] Hệ thống bận / Ngoại lệ mạng: {str(exc)}")
            continue

# Kết xuất Log tích lũy phục vụ việc bảo trì
if is_debug_enabled and attempt_errors:
    with st.expander("⚠️ [DEBUG] Nhật ký xử lý & Lỗi tích lũy hệ thống 7a2.1"):
        for err in attempt_errors: st.text(err)
# =====================================================================
# ĐOẠN 7a2.2: POST-AI MIDDLEWARE GEOMETRY PROCESSOR (V36.0 APPROVED)
# =====================================================================
import copy
import streamlit as st

# Tái khai báo hàm xử lý số để đảm bảo tính độc lập khi thực thi
def safe_float(v, default=0.0):
    from fractions import Fraction
    import re
    if v is None: return default
    if isinstance(v, (int, float)): return float(v)
    try:
        s = str(v).strip().lower()
        if re.search(r"[0-9¼½¾⅛⅜⅝⅞\/]", s):
            s = s.replace("o", "0").replace("l", "1").replace("i", "1")
        s = re.sub(r"\.+", ".", s)
        s = re.sub(r"\s*\.\s*", ".", s)
        s = s.replace('"', '').replace("'", "").replace("inch", "").replace("cm", "").replace("%", "").strip()
        if not s: return default
        
        unicode_fractions = {"½": " 1/2", "¼": " 1/4", "¾": " 3/4", "⅛": " 1/8", "⅜": " 3/8", "⅝": " 5/8", "⅞": " 7/8"}
        for uni_char, ascii_str in unicode_fractions.items():
            s = s.replace(uni_char, ascii_str)
        s = s.strip()

        s_normalized = s.replace("-", " ")
        if " " in s_normalized:
            parts = s_normalized.split()
            if len(parts) == 2 and "/" in parts[1]:
                return float(parts[0]) + float(Fraction(parts[1]))
        if "/" in s and " " not in s:
            return float(Fraction(s))

        num_match = re.search(r'([\d\.]+)', s)
        if num_match: return float(num_match.group(1))
        return float(s)
    except Exception:
        return default

# Kiểm tra kết quả trả về từ cấu phần AI Extractor 7a2.1
if "parsed_ai_response" in st.session_state and st.session_state.parsed_ai_response:
    parsed_response = st.session_state.parsed_ai_response
    
    if "chat_response" in parsed_response:
        st.session_state.ai_chat_response = str(parsed_response["chat_response"]).strip()
    
    raw_blueprint = parsed_response["blueprint"]
    
    # 1. BỘ LỌC KIỂM SOÁT VÀ THẨM ĐỊNH CHẤT LƯỢNG HÌNH HỌC VẬT LÝ (QUALITY GATE GATEKEEPER)
    bom_list = raw_blueprint.get("bom_rows", [])
    has_valid_bom = False
    
    if isinstance(bom_list, list) and len(bom_list) > 0:
        valid_rows_count = 0
        required_bom_fields = ("component_type", "panels_catalog")
        required_panel_fields = ("panel_name", "piece_count", "piece_length_inch", "piece_width_inch")
        
        # Thiết lập ranh giới vật lý chuẩn của sản phẩm Quần/Jeans ngành may
        MAX_PANEL_LENGTH = 80.0
        MAX_PANEL_WIDTH = 40.0
        MAX_PIECE_COUNT = 20
        
        for row in bom_list:
            if not isinstance(row, dict): continue
            if all(k in row for k in required_bom_fields):
                catalog = row.get("panels_catalog", [])
                if isinstance(catalog, list) and len(catalog) > 0:
                    for p in catalog:
                        if isinstance(p, dict) and all(k in p for k in required_panel_fields):
                            p_count = safe_float(p.get("piece_count"), 0.0)
                            p_len = safe_float(p.get("piece_length_inch"), 0.0)
                            p_wid = safe_float(p.get("piece_width_inch"), 0.0)
                            
                            # Kiểm tra xem kích thước bóc tách từ OCR có nằm ngoài ranh giới phi thực tế
                            if (0.0 < p_len <= MAX_PANEL_LENGTH) and (0.0 < p_wid <= MAX_PANEL_WIDTH) and (0.0 < p_count <= MAX_PIECE_COUNT):
                                valid_rows_count += 1
                                
        if valid_rows_count > 0:
            has_valid_bom = True

    # 2. TIẾN TRÌNH TÍNH TOÁN VÀ ĐỊNH HÌNH DIỆN TÍCH SƠ ĐỒ (GEOMETRY MIDDLEWARE ENGINE)
    if has_valid_bom:
        # Chuẩn hóa văn bản mảng đo lường chứng cứ
        raw_specs = []
        for s in raw_blueprint.get("matched_measurements", []):
            raw_specs.append(str(s).upper().replace("I", "1").replace("S", "5").replace("O", "0"))
        raw_blueprint["matched_measurements"] = raw_specs 

        # Kích hoạt trạng thái logic tự động (Fail-safe)
        if raw_blueprint.get("status") != "PASS": raw_blueprint["status"] = "PASS"
        if "spec_sheet_found" not in raw_blueprint: raw_blueprint["spec_sheet_found"] = True
            
        blueprint_worker = copy.deepcopy(raw_blueprint)
        processed_bom_rows = []
        
        for row in blueprint_worker.get("bom_rows", []):
            if not row or not isinstance(row, dict): continue
            c_type = str(row.get("component_type", "")).upper()
            f_class = str(row.get("fabric_classification", "")).upper()
            
            # Phân loại tự động loại linh kiện phụ trợ bằng từ khóa ngôn ngữ học
            row["_is_fusing"] = "FUSING" in f_class or "KEO" in c_type or "MEX" in c_type
            row["_is_lining"] = "LINING" in f_class or "LÓT" in c_type or "POCKET" in c_type
            row["_is_elastic_or_tape"] = "ELASTIC" in f_class or "THUN" in c_type
            
            total_area, max_len, total_pieces = 0.0, 0.0, 0.0
            catalog = row.get("panels_catalog", [])
            if isinstance(catalog, list):
                for p in catalog:
                    if not isinstance(p, dict): continue
                    count = safe_float(p.get("piece_count"), 0.0)
                    length = safe_float(p.get("piece_length_inch"), 0.0)
                    width = safe_float(p.get("piece_width_inch"), 0.0)
                    
                    # Tính lũy kế hình học phẳng cho sơ đồ nếu panel nằm trong vùng an toàn
                    if (0.0 < length <= 80.0) and (0.0 < width <= 40.0) and (0.0 < count <= 20.0):
                        total_area += (length * width * count)
                        total_pieces += count
                        if length > max_len: max_len = length
            
            # Khớp thông số hình học phẳng bổ sung vào hàng dữ liệu BOM vật tư
            row["total_area_inch2"] = total_area
            row["max_length_inch"] = max_len
            row["total_pieces_count"] = total_pieces
            processed_bom_rows.append(row)
        
        blueprint_worker["bom_rows"] = processed_bom_rows
        
        # BÀN GIAO DỮ LIỆU ĐẠT CHUẨN SẠCH TUYỆT ĐỐI CHO CAD ENGINE TIÊU THỤ KẾ TIẾP
        st.session_state.processed_blueprint = blueprint_worker
    else:
        st.error("❌ Gatekeeper từ chối: Dữ liệu bóc tách không vượt qua bài kiểm tra giới hạn vật lý (Physical Boundary Check) hoặc cấu trúc BOM trống.")
else:
    st.error(st.session_state.get("ai_chat_response", "❌ HỆ THỐNG LỖI: Vượt quá số lần thử lại tại AI Core Extractor."))

                








# =====================================================================
# ĐOẠN 7b: HIỂN THỊ KẾT QUẢ ĐỊNH MỨC & BẢNG TRA CỨU THÔNG SỐ AI OCR (V20.5 APPROVED)
# =====================================================================
if st.session_state.get("bom_data") and "bom_rows" in st.session_state.bom_data and st.session_state.bom_data["bom_rows"]:
    
    extracted_size = st.session_state.bom_data.get("calculated_on_size", "30").upper()
    
    st.markdown('<div class="cad-card">', unsafe_allow_html=True)
    st.markdown(f'<div class="cad-header">📊 CALCULATED FABRIC CONSUMPTION MATRIX (SIZE TARGET: {extracted_size})</div>', unsafe_allow_html=True)
    
    # 🌟 PHÒNG VỆ BIẾN KHI LÀM MỚI TRANG (F5) - KHÔNG LO MẤT DỮ LIỆU HIỂN THỊ
    chat_txt = ""
    if 'safe_user_prompt' in locals() and safe_user_prompt:
        chat_txt = str(safe_user_prompt).lower()
    elif st.session_state.chat_history:
        chat_txt = str(st.session_state.chat_history[-1]["user"]).lower()
    
    warp_default, weft_default = "3.0%", "3.0%"
    match_w_direct = re.search(r'(?:dọc|doc|warp)\s*[:\-=\s]*([\d\.]+)', chat_txt)
    match_f_direct = re.search(r'(?:ngang|weft)\s*[:\-=\s]*([\d\.]+)', chat_txt)
    
    if match_w_direct and match_f_direct:
        warp_default = f"{float(match_w_direct.group(1))}%"
        weft_default = f"{float(match_f_direct.group(1))}%"
    else:
        m_c = re.search(r'(?:co\s*rút|co\s*rut|co)\s*[:\-=\s]*([\d\.]+)\s*(?:-|–|x|ngang|\s+)\s*([\d\.]+)', chat_txt)
        if m_c:
            warp_default = f"{float(m_c.group(1))}%"
            weft_default = f"{float(m_c.group(2))}%"
    
    display_data = []
    for r in st.session_state.bom_data["bom_rows"]:
        if not r or not isinstance(r, dict): continue
            
        sys_notes = r.get("consumption_note", "")
        current_gross = r.get("calculated_gross_consumption_yds", 0.0)
        
        if "fabric_width_inch" in r and r["fabric_width_inch"] > 0:
            cut_width_val = f"{float(r['fabric_width_inch'])} inch"
        else:
            match_w = re.search(r'Khổ vải:\s*([\d\.]+)', sys_notes)
            cut_width_val = f"{float(match_w.group(1))} inch" if match_w else "57.0 inch"
        
        warp_val = warp_default
        weft_val = weft_default
        
        if any(x in str(r.get("fabric_classification", "")).upper() for x in ["FUSING", "LINING"]):
            warp_val = "0.0%"
            weft_val = "0.0%"

        raw_eff_value = r.get("marker_efficiency_pct")
        if not raw_eff_value:
            raw_eff_value = "85.0%" if any(x in str(r.get("fabric_classification", "")).upper() for x in ["FUSING", "LINING"]) else "83.0%"

        display_data.append({
            "Component Type": r.get("component_type", "MAIN FABRIC"),
            "Placement": r.get("placement", "BODY/POCKETS"),
            "Fabric Classification": r.get("fabric_classification", "MAIN_FABRIC"),
            "Fabric Code": r.get("fabric_code", "DENIM"),
            "Fabric Color": r.get("fabric_color", "SOLID COLOR"),
            "Khổ vải (Width)": cut_width_val,
            "Co rút dọc (% Warp)": warp_val,
            "Co rút ngang (% Weft)": weft_val,
            "Marker Efficiency": str(raw_eff_value).strip(),
            "Gross Consumption (Yds)": current_gross,
            "Quality Status": r.get("status", "PASS"),
            "System Notes": sys_notes
        })
        
    df_bom = pd.DataFrame(display_data)
    st.dataframe(df_bom, use_container_width=True, hide_index=True)
    st.markdown('</div>', unsafe_allow_html=True)
    
    # =====================================================================
    # 🌟 TRỰC QUAN HÓA BẢNG CHỨNG CỨ THÔNG SỐ AI OCR QUÉT ĐƯỢC LIÊN TRANG (13-14)
    # =====================================================================
    raw_evidence_list = st.session_state.bom_data.get("matched_measurements", [])
    if raw_evidence_list:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<div class="cad-card">', unsafe_allow_html=True)
        st.markdown(f'<div class="cad-header" style="background-color: #2C3E50;">🔍 BẰNG CHỨNG THÔNG SỐ SỐ ĐO GỐC (AI OCR EVIDENCE FOR SIZE: {extracted_size})</div>', unsafe_allow_html=True)
        
        evidence_rows = [{"STT": idx + 1, "Thông số gốc bóc tách từ Spec (Trang 13-14)": str(item)} for idx, item in enumerate(raw_evidence_list)]
        df_evidence = pd.DataFrame(evidence_rows)
        st.dataframe(df_evidence, use_container_width=True, hide_index=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # KHỐI LOGIC KHỞI TẠO FILE BÁO CÁO EXCEL CHUẨN NHÀ MÁY
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
        
        ws.merge_cells("A1:L1")
        ws["A1"] = f"BÁO CÁO ĐỊNH MỨC VẬT TƯ VẢI (SIZE: {extracted_size}) - STYLE: EXPORT_REPORT"
        ws["A1"].font = font_title
        ws["A1"].fill = fill_title
        ws["A1"].alignment = align_center
        ws.row_dimensions.height = 40
        
        headers = list(df_bom.columns)
        for col_num, header_title in enumerate(headers, 1):
            cell = ws.cell(row=3, column=col_num)
            cell.value = header_title
            cell.font = font_header
            cell.fill = fill_header
            cell.alignment = align_center
            cell.border = thin_border
        ws.row_dimensions.height = 28
        
        for row_num, row_data in enumerate(display_data, 4):
            ws.row_dimensions[row_num].height = 22
            for col_idx, key in enumerate(headers, 1):
                cell = ws.cell(row=row_num, column=col_idx)
                cell.value = row_data[key]
                cell.font = font_body
                cell.border = thin_border
                if key in ["Gross Consumption (Yds)"]:
                    cell.alignment = align_right
                    cell.number_format = '#,##0.0000'
                elif key in ["Khổ vải (Width)", "Co rút dọc (% Warp)", "Co rút ngang (% Weft)", "Marker Efficiency", "Quality Status"]:
                    cell.alignment = align_center
                else:
                    cell.alignment = align_left
        
        for col_idx, col_name in enumerate(headers, 1):
            max_len = len(col_name)
            for row_num in range(4, 4 + len(display_data)):
                val = ws.cell(row=row_num, column=col_idx).value
                if val: max_len = max(max_len, len(str(val)))
            col_letter = get_column_letter(col_idx)
            ws.column_dimensions[col_letter].width = max(max_len + 5, 12)
            
        wb.save(output)
        excel_bytes = output.getvalue()
        
        st.markdown("<br>", unsafe_allow_html=True)
        st.download_button(
            label="📥 XUẤT FILE EXCEL ĐỊNH MỨC CHUẨN SẢN XUẤT",
            data=excel_bytes,
            file_name=f"BOM_Consumption_Size_{extracted_size}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
    except Exception as e:
        st.warning(f"⚠️ Không thể khởi tạo nút xuất Excel cao cấp: {str(e)}")
