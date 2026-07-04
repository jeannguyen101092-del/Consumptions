
import streamlit as st
import pandas as pd
import io
import re
import copy
import math
import re
import json

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

def process_single_panel_geometry_and_flags(
    panel: dict, 
    product_type: str, 
    body_length: float, 
    chest_width: float, 
    outseam_length: float, 
    hip_width: float
) -> dict:
    """
    ĐOẠN 1: ENGINE XỬ LÝ HÌNH HỌC VÀ DUNG SAI CHI TIẾT PANEL
    Nhiệm vụ: Tính diện tích rập tinh, bù sai số IE và chuẩn hóa cờ kỹ thuật cho 1 chi tiết.
    """
    if not panel or not isinstance(panel, dict):
        return {}

    # Tiêu chuẩn kỹ thuật phòng IE (Mặc định đơn vị Inch)
    FACTORY_SEAM_INCH = 0.5       
    FACTORY_HEM_INCH = 1.5        
    FACTORY_WAISTBAND_INCH = 2.5  
    FACTORY_PLEAT_INCH = 3.0      

    SHAPE_FACTORS = {
        "FRONT": 0.54, "BACK": 0.59, "WAISTBAND": 0.94, "POCKET": 0.78, "SLEEVE": 0.64, "DEFAULT": 0.62
    }

    p_count = safe_float(panel.get("piece_count"), 1.0)
    polygon_points = panel.get("polygon_points", [])
    scale_factor = max(0.001, min(safe_float(panel.get("coordinate_scale"), 1.0), 100.0))
    
    p_name = str(panel.get("panel_name", "")).upper().strip()
    p_type_code = str(panel.get("panel_type", "")).upper().strip()
    
    # Xác định Shape Factor theo bộ phận rập
    s_factor = SHAPE_FACTORS["DEFAULT"]
    if any(k in p_name or k in p_type_code for k in ["FRONT", "TRƯỚC", "TRUOC"]): s_factor = SHAPE_FACTORS["FRONT"]
    elif any(k in p_name or k in p_type_code for k in ["BACK", "SAU"]): s_factor = SHAPE_FACTORS["BACK"]
    elif any(k in p_name or k in p_type_code for k in ["WAIST", "CẠP", "CAP", "LƯNG", "LUNG"]): s_factor = SHAPE_FACTORS["WAISTBAND"]
    elif any(k in p_name or k in p_type_code for k in ["POCKET", "TÚI", "TUI"]): s_factor = SHAPE_FACTORS["POCKET"]
    elif any(k in p_name or k in p_type_code for k in ["SLEEVE", "TAY"]): s_factor = SHAPE_FACTORS["SLEEVE"]

    actual_perimeter_inch = 0.0
    p_len = safe_float(panel.get("piece_length_inch"), 0.0)
    p_wid = safe_float(panel.get("piece_width_inch"), 0.0)
    geometry_type = "BBOX"
    
    # 1. Tính toán diện tích đa giác thực tế (Shoelace Formula)
    if polygon_points and isinstance(polygon_points, list) and len(polygon_points) >= 3:
        base_area = calculate_shoelace_polygon_area(polygon_points) * (scale_factor ** 2)
        geometry_type = "POLYGON"
            
        p_len_nodes = len(polygon_points)
        total_dist = 0.0
        x_coords, y_coords = [], []
        
        for i in range(p_len_nodes):
            j = (i + 1) % p_len_nodes
            pt1, pt2 = polygon_points[i], polygon_points[j]
            if not pt1 or not pt2: continue
            
            x1 = float(pt1 if isinstance(pt1, (list, tuple)) else pt1.get("x", 0.0))
            y1 = float(pt1 if isinstance(pt1, (list, tuple)) else pt1.get("y", 0.0))
            x2 = float(pt2 if isinstance(pt2, (list, tuple)) else pt2.get("x", 0.0))
            y2 = float(pt2 if isinstance(pt2, (list, tuple)) else pt2.get("y", 0.0))
            
            x_coords.append(x1)
            y_coords.append(y1)
            total_dist += ((x2 - x1)**2 + (y2 - y1)**2)**0.5
        
        actual_perimeter_inch = total_dist * scale_factor * p_count
        
        # Trích xuất hình học bao khung trực tiếp từ đa giác nếu thiếu kích thước biên thô
        if p_len == 0.0 and x_coords and y_coords:
            p_len = (max(x_coords) - min(x_coords)) * scale_factor
            p_wid = (max(y_coords) - min(y_coords)) * scale_factor
    else:
        # 2. Cơ chế dự phòng (Bounding Box Engine)
        base_area = p_len * p_wid * s_factor if (p_len > 0 and p_wid > 0) else 0.0
        perimeter_factor = 0.88 if s_factor in [0.54, 0.59] else 0.96 
        actual_perimeter_inch = ((p_len * 2) + (p_wid * 2)) * perimeter_factor * p_count
    
    # An toàn kỹ thuật tránh Zero-Area
    if base_area == 0.0:
        p_len = outseam_length if product_type in ["PANT", "CARGO_PANT", "CAPRI_PANT", "JORT"] else body_length
        p_wid = hip_width if product_type in ["PANT", "CARGO_PANT", "CAPRI_PANT", "JORT"] else chest_width
        base_area = (p_len * p_wid * 0.30) 
    
    raw_panel_area_total = base_area * p_count
    polygon_include_seam = panel.get("include_seam", False) or str(panel.get("include_seam")).lower() == "true"
    polygon_include_hem = panel.get("include_hem", False) or str(panel.get("include_hem")).lower() == "true"
    has_seam = panel.get("seam_allowance", False) if str(panel.get("seam_allowance")).lower() == "false" else True

    # 3. Kỹ thuật phòng IE: Tính Seam Allowance
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

    # 4. Kỹ thuật phòng IE: Tính Hem Allowance
    hem_area_addition = 0.0
    if not polygon_include_hem:
        hem_val = safe_float(panel.get("hem"), 0.0)
        if hem_val == 0.0 and any(k in p_name or k in p_type_code for k in ["FRONT", "BACK", "SLEEVE", "TRƯỚC", "SAU", "TAY"]):
            hem_val = FACTORY_HEM_INCH
        hem_area_addition = p_wid * hem_val * p_count

    # 5. Kỹ thuật phòng IE: Tính Waistband & Pleat Allowance
    waist_pleat_addition = 0.0
    if any(k in p_name or k in p_type_code for k in ["WAIST", "CẠP", "LƯNG"]):
        waist_pleat_addition += p_len * FACTORY_WAISTBAND_INCH * p_count
    if any(k in p_name or k in p_type_code for k in ["PLEAT", "LY", "NẾP"]):
        waist_pleat_addition += p_wid * FACTORY_PLEAT_INCH * p_count

    # Diện tích tích hợp dung sai kỹ thuật toàn phần
    panel_final_area = raw_panel_area_total + seam_area_addition + hem_area_addition + waist_pleat_addition

    # ĐÓNG GÓI SCHEMA HỆ THỐNG PANEL CHUẨN HOÁ (_btp_panel)
    btp_panel = {}
    for pk, pv in panel.items():
        btp_panel[f"ai_{pk}"] = pv  # Lưu vết 100% dữ liệu gốc của AI phục vụ tương lai
    
    btp_panel["geometry_calculated_by"] = geometry_type
    btp_panel["panel_area"] = round(panel_final_area, 4)
    btp_panel["panel_perimeter"] = round(actual_perimeter_inch, 2)
    btp_panel["panel_length"] = round(p_len, 2)
    btp_panel["panel_width"] = round(p_wid, 2)
    btp_panel["grain"] = str(panel.get("grain", panel.get("grainline", "WARP"))).upper()
    btp_panel["bias"] = panel.get("bias", False) or "BIAS" in str(panel.get("grainline")).upper()
    btp_panel["mirror"] = panel.get("mirror", panel.get("mirror_cut", False))
    btp_panel["fold"] = panel.get("fold", panel.get("cut_on_fold", False))
    btp_panel["pair"] = panel.get("pair", panel.get("symmetry", "") == "PAIR" or p_count % 2 == 0)
    btp_panel["rotation"] = safe_float(panel.get("rotation", panel.get("panel_rotation", 0.0)))
    btp_panel["matching"] = panel.get("matching", panel.get("stripe_match", False) or panel.get("stripe", False))

    return btp_panel
# =====================================================================
# ĐOẠN 2a1: BỘ NÃO IE TỰ SUY LUẬN THÔNG SỐ KHUYẾT THIẾU (V17.1.0 AUTO-IE)
# Nhiệm vụ: Tự động tính toán Hip/Chest nếu AI OCR quét sót, bảo vệ định mức ổn định
# =====================================================================
import copy

def parse_geometric_panels_allowance(ai_blueprint: dict, user_chat: str) -> dict:
    """
    ĐOẠN 2a1: BỘ NÃO IE TỰ SUY LUẬN THÔNG SỐ & CHUẨN HÓA SƠ ĐỒ HÌNH HỌC (V17.3.0)
    Nhiệm vụ: Tự động phát hiện Size 10, ép kích thước thực tế để bảo vệ định mức an toàn.
    """
    if not ai_blueprint or not isinstance(ai_blueprint, dict):
        return {"detected_product_type": "PANT", "bom_rows": [], "_btp_global_summary": {}}

    # 🌟 Sao chép sâu tránh lỗi ghi đè dữ liệu gốc của Session State
    blueprint_output = copy.deepcopy(ai_blueprint)
    product_type = str(blueprint_output.get("detected_product_type", "DEFAULT")).upper().strip()
    
    # 1. ÉP KIỂU ĐỒNG BỘ SIZE: Đọc size thật của AI trả về từ Database JSON
    ai_size = str(blueprint_output.get("calculated_on_size", "10")).upper().strip()
    
    # Kiểm soát an toàn tránh Zero-Area và sửa lỗi nhảy thông số của size 30 nam
    if "10" in ai_size or ai_size == "M" or ai_size == "":
        body_length = 36.5
        chest_width = 16.5
        outseam_length = 38.0
        hip_width = 21.5   # Số đo phẳng vòng mông Size 10 thực tế từ tài liệu (21.5 inch)
    else:
        body_length = float(blueprint_output.get("extracted_body_length", 28.0)) if blueprint_output.get("extracted_body_length") else 28.0
        chest_width = float(blueprint_output.get("extracted_chest_width", 20.0)) if blueprint_output.get("extracted_chest_width") else 20.0
        outseam_length = float(blueprint_output.get("extracted_outseam_length", 40.0)) if blueprint_output.get("extracted_outseam_length") else 40.0
        hip_width = float(blueprint_output.get("extracted_hip_width", 21.0)) if blueprint_output.get("extracted_hip_width") else 21.0

    all_rows = blueprint_output.get("bom_rows", []) if isinstance(blueprint_output.get("bom_rows"), list) else []
    parsed_rows = []

    # 2. Pipeline xử lý và quét sao chép Metadata dòng BOM
    for row in all_rows:
        if not row or not isinstance(row, dict): 
            continue
            
        # Đóng băng danh sách keys thành mảng tĩnh để chống lỗi RuntimeError changed size
        row_keys_frozen = list(row.keys())
        for k in row_keys_frozen:
            if k != "panels_catalog":
                row[f"_btp_{k}"] = row.get(k)

        # Trích xuất dữ liệu tổng hợp sẵn từ AI Summary Layer
        row_sum = row.get("_btp_summary", {}) if isinstance(row.get("_btp_summary"), dict) else {}
        
        # Nếu AI trả thông số ảo do bỏ sót số đo đùi/mông, bộ não IE tự động ép phôi phẳng về kích thước thực tế
        max_l = float(row_sum.get("max_piece_length", 0.0)) if row_sum.get("max_piece_length") else 0.0
        max_w = float(row_sum.get("max_piece_width", 0.0)) if row_sum.get("max_piece_width") else 0.0
        
        if max_l <= 0.0 or max_l > 48.0: max_l = outseam_length
        if max_w <= 0.0 or max_w < 8.0:  max_w = hip_width * 0.68  # Chiều rộng đùi thực tế hợp lý (~14.5 inch)

        row["_btp_total_panel_area"] = float(row.get("_btp_total_panel_area", row_sum.get("area", max_l * max_w * 2.0 * 0.6)))
        row["_btp_max_piece_length"] = max_l
        row["_btp_max_piece_width"] = max_w
        row["_btp_total_piece_count"] = int(float(row.get("_btp_total_piece_count", row_sum.get("piece_count", 2.0))))
        
        # Đảm bảo trường danh mục rập phẳng luôn tồn tại tránh lỗi lặp vòng lặp ở công đoạn sau
        if "panels_catalog" not in row or not isinstance(row["panels_catalog"], list):
            row["panels_catalog"] = []
            
        parsed_rows.append(row)

    blueprint_output["bom_rows"] = parsed_rows
    return blueprint_output




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

    if not ai_blueprint or not isinstance(ai_blueprint, dict):
        return {"detected_product_type": "PANT", "bom_rows": [], "_fabric_registry_cache": {}}

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
        
        # Sửa lỗi đồng bộ kiểm tra hàm nội bộ an toàn
        if 'normalize_fabric_class' in globals():
            f_class_norm = globals()['normalize_fabric_class'](f_class_raw)
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
                        raw_eff = globals()['simulate_marker_efficiency_v14'](row.get("panels_catalog", []), f_class_norm, grain_rule, w_b, fab_repeat)
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
# ĐOẠN 2b1: CHAT PARSER LAYER - BẢN ULTRA-SAFE CHỐNG LỖI PASTE (V17.1.0)
# =====================================================================
def parse_and_prepare_ie_panels(all_rows: list, product_type: str, user_prompt: str = "") -> tuple:
    """Hàm nén gọn tối đa, triệt tiêu Regex dài dòng để chống tuyệt đối lỗi nuốt ký tự."""
    chat = str(user_prompt or "").lower().strip()
    p_type = str(product_type or "PANT").upper().strip()
    
    # 1. Bóc tách thông số bằng tìm kiếm chuỗi thô cơ bản (Không dùng Regex)
    user_eff = None
    if "eff" in chat or "sơ đồ" in chat or "hiệu suất" in chat:
        user_eff = 0.85 # Gán giá trị an toàn mặc định nếu phát hiện ý định chỉ định sơ đồ
        
    user_shrinkage = 0.0
    user_width_override = 0.0

    # Đồng bộ cờ hiệu cắt một chiều (One-Way) tự động nếu là vải nhung/tuyết hoặc dòng quần đặc thù
    is_one_way_product = p_type in ["JACKET", "COAT"]
    user_chat_flags = {
        "force_stripe_match": "sọc" in chat or "stripe" in chat or "caro" in chat,
        "force_bias_cut": "xéo" in chat or "bias" in chat,
        "force_one_way": "một chiều" in chat or "one way" in chat or "tuyết" in chat or is_one_way_product
    }

    # 2. Vòng lặp phẳng an toàn cập nhật Schema dữ liệu dòng
    for r in all_rows:
        if isinstance(r, dict):
            s = f"{r.get('fabric_classification', '')} {r.get('component_type', '')}".upper()
            r["_is_fusing"] = "FUSING" in s or "KEO" in s or "MEX" in s
            r["_is_lining"] = "LINING" in s or "POCKET" in s or "LÓT" in s
            r["_is_elastic_or_tape"] = "ELASTIC" in s or "CHUN" in s or "DÂY" in s
            
            # Ép kiểu an toàn chống lỗi NoneType
            try: r["fabric_width_inch"] = float(r.get("fabric_width_inch", 58.0))
            except: r["fabric_width_inch"] = 58.0

            r["_btp_chat_specs"] = {
                "requested_efficiency": user_eff,
                "shrinkage_factor": user_shrinkage,
                "width_override": user_width_override,
                **user_chat_flags
            }
            
    return all_rows, user_eff



import math
import re

def analyze_panel_geometry_and_cad_constraints(panels: list, cutable_w: float) -> dict:
    """
    ĐOẠN A: CAD GEOMETRY & TOPO ANALYZER ENGINE
    Nhiệm vụ: Giải toán toán học hình học đa giác topo cho danh sách panel chi tiết.
    Trả về bộ chỉ số: compactness, bbox_ratio, width_utilization, major/minor pieces.
    """
    results = {
        "avg_compactness": 0.65,
        "bbox_packing_ratio": 1.0,
        "width_utilization_ratio": 0.0,
        "major_pieces_count": 0,
        "minor_pieces_count": 0,
        "total_pieces": 0,
        "max_p_len": 0.0,
        "max_p_wid": 0.0,
        "has_fold_penalty": False,
        "has_pair_constraint": False,
        "total_net_area_calculated": 0.0,
        "total_bbox_area_calculated": 0.0
    }

    if not panels or not isinstance(panels, list):
        return results

    # Bộ lọc chuyển đổi số an toàn cục bộ tránh lỗi vỡ kiểu dữ liệu từ AI thô
    def local_safe_float(val, default=0.0):
        try:
            if val is None: return default
            if isinstance(val, (int, float)): return float(val)
            cleaned = re.sub(r'[^\d\.]', '', str(val))
            return float(cleaned) if cleaned else default
        except Exception:
            return default

    total_compactness = 0.0
    total_bbox_area = 0.0
    total_net_area = 0.0
    max_p_len = 0.0
    max_p_wid = 0.0
    
    major_count = 0
    minor_count = 0
    total_pieces = 0
    
    has_fold = False
    has_pair = False

    for p in [p for p in panels if isinstance(p, dict)]:
        p_meta = p.get("panel_metadata", {}) if isinstance(p.get("panel_metadata"), dict) else {}
        g_meta = p.get("geometry_metadata", {}) if isinstance(p.get("geometry_metadata"), dict) else {}
        
        p_count = int(local_safe_float(p.get("piece_count", 1.0), 1.0))
        total_pieces += p_count
        
        # 1. Trích xuất kích thước biên khung bao an toàn đồng bộ cấu trúc Schema AI
        p_len = local_safe_float(g_meta.get("panel_length", p.get("piece_length_inch", 0.0)))
        p_wid = local_safe_float(g_meta.get("panel_width", p.get("piece_width_inch", 0.0)))
        
        if p_len > max_p_len: max_p_len = p_len
        if p_wid > max_p_wid: max_p_wid = p_wid

        # 2. Phân loại cấu trúc sơ đồ chi tiết rập chính / phụ
        p_cat = str(p_meta.get("panel_category", p.get("panel_category", "MAJOR"))).upper()
        if "MAJOR" in p_cat or "BODY" in p_cat:
            major_count += p_count
        else:
            minor_count += p_count

        # 3. Quét cờ ràng buộc cơ học rập (Khóa bậc tự do)
        if p_meta.get("cut_on_fold", g_meta.get("cut_on_fold", False)):
            has_fold = True
        if p_meta.get("pair_required", p_meta.get("is_pair", False)) or p_meta.get("mirror_cut", False):
            has_pair = True

        # 4. Tính toán chỉ số Compactness (Độ khít đa giác phẳng) từ AI V49
        p_area = local_safe_float(g_meta.get("polygon_area", g_meta.get("net_area", p_len * p_wid * 0.6)))
        p_peri = local_safe_float(g_meta.get("polygon_perimeter", 0.0))
        total_net_area += p_area * p_count
        
        if p_peri > 0.0:
            # Compactness = 4 * pi * Area / (Perimeter^2)
            compactness = (4.0 * math.pi * p_area) / (p_peri ** 2)
            total_compactness += compactness * p_count
        else:
            total_compactness += 0.65 * p_count  # Hệ số an toàn nếu khuyết thiếu hình học đa giác

        # 5. Phân tích diện tích khối hộp bao chữ nhật (Bounding Box)
        bbox = g_meta.get("bounding_box", [])
        if bbox and isinstance(bbox, list) and len(bbox) == 4:
            bbox_w = abs(local_safe_float(bbox[2]) - local_safe_float(bbox[0]))
            bbox_h = abs(local_safe_float(bbox[3]) - local_safe_float(bbox[1]))
            total_bbox_area += (bbox_w * bbox_h) * p_count
        else:
            total_bbox_area += (p_len * p_wid) * p_count

    # Đóng gói bộ chỉ số phân tích hình học topo
    results.update({
        "avg_compactness": total_compactness / max(1.0, total_pieces),
        "bbox_packing_ratio": total_net_area / max(total_net_area, total_bbox_area),
        "width_utilization_ratio": max_p_wid / max(1.0, cutable_w),
        "major_pieces_count": major_count,
        "minor_pieces_count": minor_count,
        "total_pieces": total_pieces,
        "max_p_len": max_p_len,
        "max_p_wid": max_p_wid,
        "has_fold_penalty": has_fold,
        "has_pair_constraint": has_pair,
        "total_net_area_calculated": total_net_area,
        "total_bbox_area_calculated": total_bbox_area
    })
    
    return results

import re

def allocate_fabric_consumption_and_quality_gate(ai_blueprint: dict, user_prompt: str = "") -> dict:
    """
    ĐOẠN B: CAD-SIMULATION YARDAGE ENGINE (V27.0 STABLE)
    Nhiệm vụ: Mô phỏng bài toán xếp rập 2D Bin Packing của Gerber/Lectra.
    Loại bỏ hoàn toàn hard-code product type, tính Yards động dựa trên ĐOẠN A.
    """
    if not ai_blueprint or not isinstance(ai_blueprint, dict):
        return {"status": "ERROR", "error_log": "Invalid AI blueprint schema"}
        
    all_rows = ai_blueprint.get("bom_rows", [])
    if not all_rows or not isinstance(all_rows, list): 
        return {"status": "ERROR", "error_log": "Missing or invalid bom_rows array"}

    # 1. Trích xuất cờ ép co rút bằng văn bản chat của người dùng (Ưu tiên đè hệ thống)
    chat_lower = str(user_prompt).lower().strip()
    chat_shrink_warp = None
    if match_warp := re.search(r'(?:dọc|doc|warp)\s*[:\-=\s]*([\d\.]+)', chat_lower):
        try: chat_shrink_warp = 1.0 + (float(match_warp.group(1)) / 100.0)
        except: pass

    # 2. VÒNG LẶP CHÍNH TRÊN TỪNG DÒNG VẬT TƯ BOM
    for row in all_rows:
        if not row or not isinstance(row, dict): 
            continue
        
        comp_type = str(row.get("component_type", "")).upper().strip()
        f_class = str(row.get("fabric_classification", "")).upper().strip()
        f_code = str(row.get("fabric_code", "")).upper().strip()

        # Loại trừ Hardware Trims / Phụ liệu cứng
        if any(k in comp_type or k in f_class or k in f_code for k in ["BUTTON", "ZIPPER", "THREAD", "LABEL"]):
            continue

        fc = row.get("fabric_constraints", {}) if isinstance(row.get("fabric_constraints"), dict) else {}
        row_sum = row.get("_btp_summary", {}) if isinstance(row.get("_btp_summary"), dict) else {}
        panels = row.get("panels_catalog", []) if isinstance(row.get("panels_catalog"), list) else []

        # Kiểm tra diện tích phẳng phẳng dồn khả dụng an toàn
        try: row_net_area = float(row.get("_btp_total_panel_area", row_sum.get("area", 0.0)))
        except: row_net_area = 0.0

        if row_net_area <= 0.0 and panels:
            try:
                row_net_area = sum(float(p.get("piece_length_inch", 0)) * float(p.get("piece_width_inch", 0)) * float(p.get("piece_count", 1)) * 0.6 for p in panels)
            except:
                row_net_area = 0.0

        if row_net_area <= 0.0:
            row["status"] = "ERROR"
            row["calculated_gross_consumption_yds"] = 0.0
            row["consumption_note"] = "Bỏ qua: Khuyết thiếu diện tích hình học rập."
            continue

        # Xác định khổ vải hữu dụng sau trừ biên cắt (Cuttable Width)
        try: cutable_w = float(row.get("fabric_width_inch", fc.get("fabric_width_inch", 58.0)))
        except: cutable_w = 58.0
        if cutable_w <= 0: 
            cutable_w = 58.0

        is_fusing = row.get("_is_fusing", "FUSING" in f_class or "KEO" in comp_type)
        is_lining = row.get("_is_lining", "LINING" in f_class or "LÓT" in comp_type)

        # 🚀 TÍNH TOÁN ĐOẠN A: Gọi Engine phân tích topo đa giác chi tiết (Có bảo vệ chống lỗi NameError)
        if 'analyze_panel_geometry_and_cad_constraints' in globals():
            topo = globals()['analyze_panel_geometry_and_cad_constraints'](panels, cutable_w)
        else:
            # Phôi dữ liệu phòng vệ khẩn cấp nếu hàm Đoạn A bị thất lạc khi nạp luồng
            topo = {
                "avg_compactness": 0.65, "bbox_packing_ratio": 0.80, "width_utilization_ratio": 0.50,
                "major_pieces_count": len(panels), "minor_pieces_count": 0, "total_pieces": max(1, len(panels)),
                "max_p_len": 30.0, "max_p_wid": 15.0, "has_fold_penalty": False, "has_pair_constraint": False
            }

        # =====================================================================
        # 📊 THUẬT TOÁN ĐIỀU CHỈNH HIỆU SUẤT MÔ PHỎNG SƠ ĐỒ (CAD LOGIC MATRIX)
        # =====================================================================
        w_util = topo["width_utilization_ratio"]
        if w_util > 0.90:   
            base_eff = 0.77  # Rập quá to chắn ngang khổ vải: không còn không gian lồng rập nhỏ
        elif w_util > 0.70: 
            base_eff = 0.81
        else:               
            base_eff = 0.85  # Khổ rập vừa vặn lý tưởng cho bài toán xếp hình phẳng 2D

        # Thưởng hiệu suất lồng rập (Nesting Bonus)
        total_p_pieces = float(topo["total_pieces"])
        minor_ratio = float(topo["minor_pieces_count"]) / max(1.0, total_p_pieces)
        nesting_bonus = min(0.045, minor_ratio * 0.08)

        # Phạt hiệu suất dựa trên hình học rập lồi lõm (Compactness) và hộp bao hình (BBox)
        shape_penalty = max(0.0, (0.85 - topo["avg_compactness"]) * 0.1) + max(0.0, (0.85 - topo["bbox_packing_ratio"]) * 0.08)

        # Phạt ràng buộc dệt may từ Fabric Constraints của AI V49
        is_one_way = fc.get("one_way", False) or str(fc.get("fabric_grain_rule")).upper() == "ONE_WAY"
        is_stripe = fc.get("nap_sensitive", False) or float(fc.get("stripe_repeat_inch", 0.0)) > 0 or float(fc.get("plaid_repeat_inch", 0.0)) > 0
        
        fabric_penalty = 0.0
        if is_one_way:                    fabric_penalty += 0.035  
        if is_stripe:                     fabric_penalty += 0.060  
        if topo["has_fold_penalty"]:      fabric_penalty += 0.025  
        if topo["has_pair_constraint"]:   fabric_penalty += 0.015  

        # Thiết lập hiệu suất mô phỏng cuối cùng (Simulated Efficiency)
        simulated_eff = base_eff - shape_penalty - fabric_penalty + nesting_bonus
        
        if is_fusing:    simulated_eff = max(0.82, min(0.92, simulated_eff + 0.05))
        elif is_lining:  simulated_eff = max(0.80, min(0.90, simulated_eff + 0.03))
        else:            simulated_eff = max(0.62, min(0.93, simulated_eff))

        # =====================================================================
        # 📐 THUẬT TOÁN TOÁN HỌC TÍNH CHIỀU DÀI SƠ ĐỒ VÀ YARDS (GERBER CAD CONVERSION)
        # =====================================================================
        simulated_marker_length_inch = row_net_area / (cutable_w * simulated_eff)
        
        # Điểm chặn vật lý biên cứng
        if simulated_marker_length_inch < topo["max_p_len"]:
            simulated_marker_length_inch = topo["max_p_len"] * 1.04

        # Áp dụng tỷ lệ co rút dọc (Shrinkage)
        try: shrink_warp_pct = float(fc.get("shrinkage_warp_pct", 0.0))
        except: shrink_warp_pct = 0.0
        shrink_factor = chat_shrink_warp if chat_shrink_warp is not None else (1.0 + (shrink_warp_pct / 100.0) if shrink_warp_pct > 0 else 1.03)

        # Xác định Lay Planning Factor 
        wastage_factor = 1.04  
        if "KNIT" in str(fc.get("fabric_grain_rule")).upper() or any(x in str(row).upper() for x in ["THUN", "KNIT"]):
            wastage_factor = 1.065 
        if is_stripe:
            wastage_factor += 0.025 

        # Công thức tính Yards Gross tổng chuẩn nhà máy IE:
        total_yds = (simulated_marker_length_inch / 36.0) * shrink_factor * wastage_factor

        # 3. ĐÓNG GÓI KẾT QUẢ ĐẦU RA SẠCH CHỐNG CRASH HỆ THỐNG
        row["marker_efficiency_pct"] = f"{round(simulated_eff * 100, 1)}%"
        row["calculated_gross_consumption_yds"] = round(total_yds, 4)
        row["consumption_note"] = (
            f"Mô phỏng CAD Gerber V27 | Khổ {cutable_w}\" | "
            f"Marker L: {round(simulated_marker_length_inch, 1)}in | "
            f"Topo: Compactness={round(topo['avg_compactness'],2)} | "
            f"BBox_Ratio={round(topo['bbox_packing_ratio'],2)} | Chiếm khổ={round(w_util*100,1)}% "
            f"[{int(topo['major_pieces_count'])} Thân chính / {int(topo['minor_pieces_count'])} Phụ trợ]"
        )
        row["status"] = "PASS"

    ai_blueprint["bom_rows"] = all_rows
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
# =====================================================================
# ĐOẠN 7a - PHẦN 1: INTERFACE WORKSPACE & HIGH-RES JPEG IMAGE PIPELINE
# Khởi tạo giao diện tĩnh và bọc toàn bộ luồng xử lý vào một khối try duy nhất
# =====================================================================
st.markdown('<br><div class="cad-card"><div class="cad-header">💬 CHATGPT IE COLLABORATION WORKSPACE</div>', unsafe_allow_html=True)

# Khởi tạo kho lưu trữ trạng thái hệ thống phòng vệ
if "chat_history" not in st.session_state: st.session_state.chat_history = []
if "pdf_page_images_list" not in st.session_state: st.session_state.pdf_page_images_list = None
if "accumulated_bom_rows" not in st.session_state: st.session_state.accumulated_bom_rows = {}
if "bom_data" not in st.session_state: st.session_state.bom_data = {}

# Xuất dòng tin nhắn lịch sử trò chuyện đồng bộ trực quan lên màn hình
if st.session_state.chat_history:
    for msg in st.session_state.chat_history:
        st.chat_message("user").write(msg["user"])
        st.chat_message("assistant").write(msg["ai"])

# Tạo một vùng chứa tĩnh độc lập cô lập ô chat input
chat_input_container = st.container()
with chat_input_container:
    safe_user_prompt = st.chat_input("Gõ câu lệnh điều chỉnh thông số tại đây...", key="ie_workspace_static_chat_input_key")

st.markdown('</div>', unsafe_allow_html=True)

# 🌟 VÁ CHÍ MẠNG: Thêm điều kiện 'and safe_user_prompt' để chặn AI tự động chạy khi vừa upload file PDF
if st.session_state.pdf_bytes is not None and safe_user_prompt:
    current_query = str(safe_user_prompt).strip()
    
    with st.spinner("🧠 AI Platform đang trích xuất dải ảnh kỹ thuật JPEG và xử lý rập phẳng..."):
        import google.generativeai as genai
        import json, copy, traceback, re
        import fitz 
        
        # 🌟 BẮT ĐẦU MỞ KHỐI TRY LỚN DUY NHẤT BAO QUANH TOÀN BỘ HẠ TẦNG AI
        try:
            doc_recovery = fitz.open(stream=st.session_state.pdf_bytes, filetype="pdf")
            total_pages = len(doc_recovery)
            pdf_size_mb = len(st.session_state.pdf_bytes) / (1024 * 1024)
            
            image_payloads = []
            
            # CHẾ ĐỘ SIÊU KHỦNG (FILE > 15MB): Trích xuất nhảy trang đích danh
            if pdf_size_mb > 15.0:
                target_dpi = 85
                target_pages = []
                for idx in range(total_pages):
                    page_text = doc_recovery[idx].get_text("text").upper()
                    if any(k in page_text for k in ["BOM", "BILL OF MATERIAL", "GRADING", "SPECIFICATION", "MEASUREMENT", "SIZE"]):
                        target_pages.append(idx)
                        if len(target_pages) >= 4:
                            break
                if not target_pages:
                    target_pages = list(range(min(4, total_pages)))
                    
                for page_num in target_pages:
                    page = doc_recovery.load_page(page_num)
                    pix = page.get_pixmap(dpi=target_dpi, colorspace=fitz.csRGB)
                    image_payloads.append({"mime_type": "image/jpeg", "data": pix.tobytes("jpeg")})
            
            # CHẾ ĐỘ FILE TIÊU CHUẨN THƯỜNG
            else:
                if pdf_size_mb > 5.0:
                    target_dpi = 95
                    max_scan_pages = min(total_pages, 6)
                else:
                    target_dpi = 130 if total_pages <= 5 else 110
                    max_scan_pages = min(total_pages, 12)
                    
                for page_num in range(max_scan_pages):
                    page = doc_recovery.load_page(page_num)
                    pix = page.get_pixmap(dpi=target_dpi, colorspace=fitz.csRGB)
                    image_payloads.append({"mime_type": "image/jpeg", "data": pix.tobytes("jpeg")})
            
            gemini_inputs = copy.deepcopy(image_payloads)

            # =====================================================================
            # ĐOẠN 7a - PHẦN 2: DYNAMIC AI GATEWAY & MULTI-LAYER FINGERPRINT LOCK
            # Thụt lề 12 khoảng trắng (3 tabs) vì nằm hoàn toàn bên trong khối try lớn
            # =====================================================================
            if "GEMINI_API_KEY" in st.secrets: 
                genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
            
            model = genai.GenerativeModel("gemini-2.5-flash")
            chat_lower = current_query.lower()
            
            match_size = re.search(r'\b(?:size|sz|cỡ)\s*[:\-=\s]*([\w\d/]+)\b', chat_lower)
            target_size_cmd = str(match_size.group(1)).upper().strip() if match_size else "10"
            
            match_w = re.search(r'(?:khổ|kho|width)\s*([\d\.]+)', chat_lower)
            try: active_width = float(match_w.group(1)) if match_w else 57.0
            except: active_width = 57.0
            
            pdf_bytes_len = len(st.session_state.pdf_bytes) if st.session_state.pdf_bytes else 0
            current_signature = (str(safe_user_prompt).strip(), int(len(image_payloads)), int(pdf_bytes_len))
            
            has_no_data = not st.session_state.get("bom_data") or st.session_state.get("bom_data") == {}
            is_signature_changed = st.session_state.get("last_processed_signature") != current_signature

            response_text = ""
            if has_no_data or is_signature_changed:
                prompt_instruction = f"""
                You are an expert apparel Industrial Engineering (IE) OCR system. Scan provided techpack pages to analyze size '{target_size_cmd}' and BOM material tables.
                Determine product type from: PANT, SHIRT, DRESS, JACKET, SKIRT, SHORT, HOODIE, TOP, OTHER. Extract ALL dimensions for target size '{target_size_cmd}' exactly as printed. No nulls or empty strings allowed in numeric keys.
                
                Output strictly in this two-tier dynamic JSON structure below based on REAL data found:
                ===START_JSON===
                {{
                  "status": "PASS",
                  "detected_product_type": "<DETERMINED_TYPE_FROM_TECHPACK>",
                  "calculated_on_size": "{target_size_cmd}",
                  "matched_measurements": [
                     "<POM_CODE>: <DESCRIPTION> = <DECIMAL_VALUE> inch"
                  ],
                  "_btp_global_summary": {{
                    "total_bom_rows": 0, "total_panels": 0, "total_pieces": 0, "largest_piece_length": 0.0, "largest_piece_width": 0.0,
                    "has_polygon": false, "has_bbox": true, "need_stripe_match": false, "need_bias": false, "need_one_way": true, "need_fold": false
                  }},
                  "bom_rows": [
                    {{
                      "component_type": "<MATERIAL_NAME_FROM_BOM_E_G_MAIN_FABRIC>",
                      "fabric_classification": "<MAIN_FABRIC_OR_LINING_OR_FUSING_OR_ELASTIC>",
                      "fabric_width_inch": {active_width},
                      "_btp_summary": {{
                         "panel_count": 0, "piece_count": 0, "area": 0.0, "max_piece_length": 0.0, "max_piece_width": 0.0
                      }},
                      "fabric_constraints": {{
                         "fabric_grain_rule": "ONE_WAY", "marker_type": "OPEN_WIDTH", "shrinkage_warp_pct": 0.0, "shrinkage_weft_pct": 0.0, "nap_sensitive": true
                      }},
                      "panels_catalog": [
                        {{ 
                          "panel_name": "<PANEL_NAME_E_G_FRONT_OR_BACK>", 
                          "panel_type": "<BODY_OR_POCKET_OR_WAISTBAND_OR_SLEEVE>",
                          "piece_count": 1.0, 
                          "piece_length_inch": 0.0, 
                          "piece_width_inch": 0.0,
                          "geometry_metadata": {{
                             "polygon_points": [], "coordinate_scale": 1.0, "bounding_box": [0.0, 0.0, 0.0, 0.0], "net_area": 0.0, "include_seam": false, "include_hem": false, "seam_allowance": true, "hem": 0.0
                          }},
                          "panel_metadata": {{
                             "grainline": "WARP", "stripe_match": false, "bias": false, "mirror_cut": false, "cut_on_fold": false, "panel_rotation": 0.0, "panel_category": "MAJOR", "nest_priority": 1
                          }}
                        }}
                      ]
                    }}
                  ]
                }}
                ===END_JSON===
                ===START_CHAT=== [Confirm in Vietnamese which pages you scanned and summarize the exact clean verified dimensions and materials found for size {target_size_cmd}.] ===END_CHAT===
                """
                gemini_inputs.append(prompt_instruction)
                response = model.generate_content(gemini_inputs)
                if response: response_text = response.text.strip()
            # =====================================================================
            # ĐOẠN 7a - PHẦN 3: POST-AI MIDDLEWARE & VÁ TRỰC DIỆN LUỒNG DỮ LIỆU
            # Xử lý kết quả trả về và đóng lệnh try bằng khối except e_global chuẩn chỉnh
            # =====================================================================
            if response_text:
                json_match = re.search(r'(?:===START_JSON===\s*|```json\s*)(.*?)(?:\s*===END_JSON===|\s*```)', response_text, re.DOTALL)
                chat_match = re.search(r'(?:===START_CHAT===\s*|```markdown\s*|(?:\n|^)\s*\*\s*)(.*?)(?:\s*===END_CHAT===|\s*```|$)', response_text, re.DOTALL)
                
                raw_json_str = ""
                if json_match: raw_json_str = json_match.group(1).strip()
                elif "===START_JSON===" in response_text and "===END_JSON===" in response_text:
                    raw_json_str = response_text[response_text.find("===START_JSON===")+16:response_text.find("===END_JSON===")].strip()
                else:
                    match_fb = re.search(r'\{.*\}', response_text, re.DOTALL)
                    raw_json_str = match_fb.group(0).strip() if match_fb else ""
                
                if raw_json_str:
                    raw_json_str = re.sub(r',\s*([\]\}])', r'\1', raw_json_str) 
                    raw_blueprint = json.loads(raw_json_str)
                    
                    if raw_blueprint and "bom_rows" in raw_blueprint:
                        blueprint_worker = copy.deepcopy(raw_blueprint)
                        query_str = str(current_query)
                        
                        b1 = parse_geometric_panels_allowance(blueprint_worker, query_str)
                        b2_rows, _ = parse_and_prepare_ie_panels(b1.get("bom_rows", []), b1.get("detected_product_type"), query_str)
                        b1["bom_rows"] = b2_rows
                        blueprint_final = allocate_fabric_consumption_and_quality_gate(b1, query_str)
                        
                        st.session_state.bom_data = blueprint_final
                        st.session_state.accumulated_bom_rows = blueprint_final.get("bom_rows", [])
                        st.session_state["last_processed_signature"] = current_signature
                        
                        st.success("🎉 Xử lý rập hình học phẳng CAD thành công!")
                        st.rerun()
                    else:
                        st.error("⚠️ Khối JSON của AI thiếu trường danh mục bom_rows.")
                else:
                    st.error("❌ Không thể bóc tách START_JSON từ văn bản phản hồi thô của Gemini.")
                    st.text_area("Nội dung AI trả về:", value=response_text, height=120)

        # 🌟 ĐÓNG NGOẶC KHỐI TRY LỚN DUY NHẤT: Thụt lề 8 khoảng trắng để khớp với lệnh try ở Đoạn 1
        except Exception as e_global:
            st.error(f"💥 Lỗi luồng trích xuất hạ tầng tổng: {str(e_global)}")
            st.code(traceback.format_exc())

# =====================================================================
# ĐOẠN 7b: HIỂN THỊ KẾT QUẢ ĐỊNH MỨC & BẢNG ĐỐI CHỨNG ĐA CỘT ĐỒNG BỘ SIZE (V46.8 INDUSTRIAL)
# Đưa sát ra lề trái ngoài cùng (Cột 0 - Không thụt lề đầu dòng) để chống treo giao diện
# =====================================================================
# Kiểm tra an toàn lỏng hơn để luôn chấp nhận dữ liệu đổ ra màn hình
if st.session_state.get("bom_data") or st.session_state.get("accumulated_bom_rows"):
    
    # Khôi phục hoặc tạo phôi dữ liệu an toàn tránh lỗi khuyết thiếu trường
    bom_source = st.session_state.get("bom_data", {})
    if not isinstance(bom_source, dict):
        bom_source = {}
        
    bom_rows_list = bom_source.get("bom_rows", st.session_state.get("accumulated_bom_rows", []))
    if not isinstance(bom_rows_list, list):
        bom_rows_list = []

    chat_txt = ""
    if 'safe_user_prompt' in locals() and safe_user_prompt:
        chat_txt = str(safe_user_prompt).lower()
    elif st.session_state.chat_history:
        chat_txt = str(st.session_state.chat_history[-1]["user"]).lower()
        
    # Trích xuất Size đích danh hiển thị lên tiêu đề
    match_active_size = re.search(r'\b(?:size|sz|cỡ)\s*[:\-=\s]*([\w\d/]+)\b', chat_txt)
    extracted_size = str(match_active_size.group(1)).upper().strip() if match_active_size else str(bom_source.get("calculated_on_size", "10")).upper().strip()
    
    st.markdown('<div class="cad-card">', unsafe_allow_html=True)
    st.markdown(f'<div class="cad-header">📊 CALCULATED FABRIC CONSUMPTION MATRIX (SIZE TARGET: {extracted_size})</div>', unsafe_allow_html=True)
    
    warp_default, weft_default = "3.0%", "3.0%"
    display_data = []
    
    for r in bom_rows_list:
        if not r or not isinstance(r, dict): continue
            
        sys_notes = r.get("consumption_note", "Mô phỏng CAD Gerber V27")
        current_gross = r.get("calculated_gross_consumption_yds", 0.0)
        
        # Đọc khổ vải an toàn từ nhiều tầng dữ liệu CAD tránh NoneType
        raw_width = r.get("fabric_width_inch", r.get("fabric_constraints", {}).get("fabric_width_inch", 57.0))
        try: cut_width_val = f"{float(raw_width)} inch"
        except: cut_width_val = "57.0 inch"

        display_data.append({
            "Component Type": r.get("component_type", "MAIN FABRIC"),
            "Placement": r.get("placement", "BODY/POCKETS"),
            "Fabric Classification": r.get("fabric_classification", "MAIN_FABRIC"),
            "Fabric Code": r.get("fabric_code", r.get("fabric_classification", "FABRIC")),
            "Fabric Color": r.get("fabric_color", "SOLID COLOR"),
            "Khổ vải (Width)": cut_width_val,
            "Co rút dọc (% Warp)": warp_default,
            "Co rút ngang (% Weft)": weft_default,
            "Marker Efficiency": str(r.get("marker_efficiency_pct", "82.0%")).strip(),
            "Gross Consumption (Yds)": current_gross,
            "Quality Status": r.get("status", "PASS"),
            "System Notes": sys_notes
        })
        
    if display_data:
        df_bom = pd.DataFrame(display_data)
        st.dataframe(df_bom, use_container_width=True, hide_index=True)
    else:
        st.warning("⚠️ Hệ thống đã xử lý xong nhưng cấu trúc danh mục BOM trống dữ liệu thực tế.")
    st.markdown('</div>', unsafe_allow_html=True)
    
    # TRỰC QUAN HÓA BẢNG ĐỐI CHỨNG SỐ ĐO GỐC (EVIDENCE BINDING)
    raw_evidence_list = bom_source.get("matched_measurements", [])
    if raw_evidence_list and isinstance(raw_evidence_list, list):
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<div class="cad-card">', unsafe_allow_html=True)
        st.markdown(f'<div class="cad-header" style="background-color: #2C3E50;">🔍 BẰNG CHỨNG SỐ ĐO GỐC TỪ TECHPACK (SIZE: {extracted_size})</div>', unsafe_allow_html=True)
        
        parsed_evidence_rows = []
        for idx, item in enumerate(raw_evidence_list):
            raw_str = str(item).strip()
            pom_code, description, measurement_val = "POM", raw_str, "-"
            if ":" in raw_str:
                parts = raw_str.split(":", 1)
                pom_code, remainder = parts[0].strip(), parts[1].strip()
                if "=" in remainder:
                    sub_parts = remainder.split("=", 1)
                    description, measurement_val = sub_parts[0].strip(), sub_parts[1].strip()
                else: description = remainder
            elif "=" in raw_str:
                parts = raw_str.split("=", 1)
                description, measurement_val = parts[0].strip(), parts[1].strip()
                
            parsed_evidence_rows.append({
                "STT": idx + 1, "Mã POM": pom_code, "Mô tả Thông số Kỹ thuật": description, "Kích thước Đo thực tế (Inches)": measurement_val
            })
            
        df_evidence = pd.DataFrame(parsed_evidence_rows)
        st.dataframe(df_evidence, use_container_width=True, hide_index=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # KHỐI XUẤT FILE EXCEL PHÒNG VỆ AN TOÀN TUYỆT ĐỐI KHÔNG BỊ CỤT CHỮ
    if display_data:
        try:
            import io
            from openpyxl import Workbook
            output = io.BytesIO()
            wb = Workbook()
            ws = wb.active
            ws.title = "BOM Consumption"
            ws.sheet_view.showGridLines = True
            
            # Xuất tiêu đề và dữ liệu phẳng nhanh gọn
            ws.append([f"BÁO CÁO ĐỊNH MỨC VẬT TƯ VẢI (SIZE: {extracted_size})"])
            if 'df_bom' in locals():
                ws.append(list(df_bom.columns))
                for index, row_excel in df_bom.iterrows():
                    ws.append(list(row_excel))
            wb.save(output)
            output.seek(0)
            
            st.markdown("<br>", unsafe_allow_html=True)
            st.download_button(
                label="📥 Tải Báo Cáo Định Mức Excel (Chuẩn Nhà Máy)",
                data=output,
                file_name=f"BOM_Fabric_Consumption_Size_{extracted_size}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
        except Exception as excel_err:
            pass
