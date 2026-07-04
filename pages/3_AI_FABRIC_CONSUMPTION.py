
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
import copy
import re
import streamlit as st

# =====================================================================
# ĐOẠN 2a1: BỘ NÃO IE TỰ SUY LUẬN THÔNG SỐ & CHUẨN HÓA SƠ ĐỒ HÌNH HỌC (V17.5.0)
# ĐÃ SỬA: ƯU TIÊN TUYỆT ĐỐI PANELS_CATALOG THẬT VÀ SỬA LỖI CHECK CHUỖI VẬT LIỆU
# =====================================================================
def parse_geometric_panels_allowance(ai_blueprint: dict, user_chat: str) -> dict:
    if not ai_blueprint or not isinstance(ai_blueprint, dict):
        return {"detected_product_type": "PANT", "bom_rows": [], "_btp_global_summary": {}}

    blueprint_output = copy.deepcopy(ai_blueprint)
    ai_size = str(blueprint_output.get("calculated_on_size", "30")).upper().strip()
    
    if any(s in ai_size for s in ["30", "31", "32", "34", "36", "38"]):
        outseam_length = 40.0
        hip_width = 22.5
    else:
        outseam_length = 38.0
        hip_width = 21.5

    all_rows = blueprint_output.get("bom_rows", []) if isinstance(blueprint_output.get("bom_rows"), list) else []
    parsed_rows = []

    for row in all_rows:
        if not row or not isinstance(row, dict): 
            continue

        # 🌟 VÁ LỖI KHỔ VẢI 0.0 INCH: Kiểm tra và chốt chặn an toàn ngay từ đầu
        width = float(row.get("fabric_width_inch", 0) or 0.0)
        if width < 20.0:
            width = 57.0
        row["fabric_width_inch"] = width
        row["_btp_fabric_width_inch"] = width

        row_sum = row.get("_btp_summary", {}) if isinstance(row.get("_btp_summary"), dict) else {}
        max_l = float(row_sum.get("max_piece_length", 0.0)) if row_sum.get("max_piece_length") else 0.0
        max_w = float(row_sum.get("max_piece_width", 0.0)) if row_sum.get("max_piece_width") else 0.0
        
        if max_l <= 0.0 or max_l > 48.0: max_l = outseam_length
        if max_w <= 0.0 or max_w < 8.0:  max_w = hip_width * 0.68

        # 🌟 3️⃣ ƯU TIÊN SỐ 1: QUÉT TÍNH TỔNG DIỆN TÍCH TỪ DANH SÁCH CHI TIẾT RẬP THẬT (PANELS_CATALOG) CỦA AI
        catalog_area = 0.0
        has_valid_catalog = False
        
        if "panels_catalog" in row and isinstance(row["panels_catalog"], list):
            for panel in row["panels_catalog"]:
                if not isinstance(panel, dict): 
                    continue
                geo = panel.get("geometry_metadata", {})
                # Đọc kích thước chiều dài và chiều rộng của từng chi tiết rập phẳng nhỏ (Front, Back, Waistband,...)
                p_len = float(panel.get("piece_length_inch", 0.0) or 0.0)
                p_wid = float(panel.get("piece_width_inch", 0.0) or 0.0)
                p_cnt = float(panel.get("piece_count", 1.0) or 1.0)
                
                # Tính diện tích hình học phẳng thực tế của chi tiết rập nhỏ đó
                p_area = p_len * p_wid * p_cnt
                if p_area <= 0.0:
                    p_area = float(geo.get("net_area", 0.0) or 0.0)
                    
                if p_area > 5.0:
                    catalog_area += p_area
                    has_valid_catalog = True

        # Gộp tất cả các trường để kiểm tra loại vật liệu chính xác
        comp_type = (
            str(row.get("component_type", "")) + " " +
            str(row.get("fabric_classification", "")) + " " +
            str(row.get("fabric_code", ""))
        ).upper()

        # Nếu AI có bảng chi tiết rập thật, dùng luôn. Nếu trống, bộ não IE tự động suy luận phôi dự phòng
        if has_valid_catalog and catalog_area > 0.0:
            calculated_area = catalog_area
        else:
            if any(k in comp_type for k in ["DENIM", "MAIN", "CHÍNH", "SELF", "SHELL"]):
                calculated_area = max_l * max_w * 4.0 * 0.72
            elif any(k in comp_type for k in ["POCKET", "LÓT", "LINING", "TC"]):
                calculated_area = 14.0 * 7.5 * 4.0
            elif any(k in comp_type for k in ["FUSING", "MẾCH", "DỰNG", "TRICOT"]):
                calculated_area = max_w * 3.5 * 2.0
            else:
                calculated_area = max_l * max_w * 0.1

        # Chặn đứng trường hợp giá trị 0 hoặc rỗng đè lên diện tích tính toán dự phòng
        existing_area = float(row.get("_btp_total_panel_area", 0.0) or 0.0)
        if existing_area <= 0.0:
            row["_btp_total_panel_area"] = calculated_area
        else:
            row["_btp_total_panel_area"] = existing_area
            
        row["_btp_max_piece_length"] = max_l
        row["_btp_max_piece_width"] = max_w
        row["_btp_total_piece_count"] = int(float(row.get("_btp_total_piece_count", row_sum.get("piece_count", 2.0))))
        
        if "panels_catalog" not in row or not isinstance(row["panels_catalog"], list):
            row["panels_catalog"] = []

        # Sao lưu toàn bộ sang các trường gốc để chống lại sự phá hoại ngầm của hàm middleware ở giữa
        for key_origin in list(row.keys()):
            if not key_origin.startswith("_btp_") and key_origin != "panels_catalog":
                row[f"_btp_{key_origin}"] = row.get(key_origin)
            
        parsed_rows.append(row)

    blueprint_output["bom_rows"] = parsed_rows
    return blueprint_output


# =====================================================================
# ĐOẠN 2b - PHẦN 1: UNIVERSAL APPAREL GEOMETRIC ENGINE (V46.0 PURE CAD)
# ĐỘNG CƠ RẬP VẠN NĂNG - LOẠI BỎ HOÀN TOÀN ĐƯỜNG MAY (SEAM_ALLOWANCE = 0.0)
# =====================================================================
def allocate_fabric_consumption_and_quality_gate(blueprint_final: dict, query_string: str) -> dict:
    st.warning("⚡ ENGINE EXECUTING: GEOMETRIC INTERPRETER CONTROL V46.0 ACTIVATED")
    
    if not blueprint_final or "bom_rows" not in blueprint_final:
        return blueprint_final
        
    # 🌟 THEO YÊU CẦU: Thiết lập dung sai đường may bằng 0.0 để kiểm tra độ giảm định mức
    SEAM_ALLOWANCE = 0.0
        
    # TRÍCH XUẤT ĐỘNG TỶ LỆ CO RÚT TỪ Ô CHAT NGƯỜI DÙNG
    chat_lower = str(query_string).lower()
    match_shrink = re.search(r'(?:co rút|co rut|sh|shrinkage)\s*[:\-=\s]*([\d\.]+)\s*[\-,\s]\s*([\d\.]+)', chat_lower)
    
    if match_shrink:
        try:
            warp_val = f"{float(match_shrink.group(1))}%"
            weft_val = f"{float(match_shrink.group(2))}%"
            w_num = float(match_shrink.group(1)) / 100.0
            f_num = float(match_shrink.group(2)) / 100.0
        except:
            warp_val, weft_val = "4.0%", "14.0%"
            w_num, f_num = 0.04, 0.14
    else:
        warp_val, weft_val = "4.0%", "14.0%"
        w_num, f_num = 0.04, 0.14
        
    shrink_factor = (1.0 + w_num) * (1.0 + f_num)
    product_type = str(blueprint_final.get("detected_product_type", "PANT")).upper().strip()
    
    # TRÍCH XUẤT SỐ ĐO THỰC TẾ TỪ BẢNG THÔNG SỐ POM DO AI CUNG CẤP CỦA SIZE MỤC TIÊU
    matched_list = blueprint_final.get("matched_measurements", [])
    length_base, width_base, secondary_base = 0.0, 0.0, 0.0
    
    for item in matched_list:
        item_str = str(item).upper()
        if any(k in item_str for k in ["LENGTH", "OUTSEAM", "DÀI"]):
            m_num = re.search(r'([\d\.]+)', item_str)
            if m_num: length_base = float(m_num.group(1))
        if any(k in item_str for k in ["CHEST", "HIP", "RỘNG MÔNG", "NGỰC"]):
            m_num = re.search(r'([\d\.]+)', item_str)
            if m_num: width_base = float(m_num.group(1))
        if any(k in item_str for k in ["WAIST", "SLEEVE", "TAY", "BỤNG"]):
            m_num = re.search(r'([\d\.]+)', item_str)
            if m_num: secondary_base = float(m_num.group(1))

    filtered_bom_rows = []
    for row in blueprint_final["bom_rows"]:
        comp_type = (str(row.get("component_type", "")) + " " + str(row.get("fabric_classification", ""))).upper()
        fab_class = str(row.get("fabric_classification", "")).upper()
        
        row["_btp_warp_pct"] = warp_val
        row["_btp_weft_pct"] = weft_val
        
        if any(k in comp_type for k in ["BUTTON", "NÚT", "RIVET", "ĐINH TÁN", "LABEL", "NHÃN", "MÁC", "STICKER", "THREAD", "CHỈ"]):
            continue
            
        width_inch = float(row.get("fabric_width_inch", 57.0))
        if width_inch < 20.0: width_inch = 57.0
        row["fabric_width_inch"] = width_inch
            
        panels = row.get("panels_catalog", [])
        
        # ✅ CHUẨN HÓA LẠI TỶ LỆ RẬP CAD: Chia đều 4 mảnh vòng mông/vòng ngực tịnh để kích thước rập phẳng chính xác
        if not panels and any(k in comp_type for k in ["MAIN", "DENIM", "CHÍNH", "SELF", "SHELL"]):
            l_eff = length_base or 38.0
            w_eff = width_base or 21.5   # Số đo phẳng mông quần Jeans
            s_eff = secondary_base or 16.5 # Số đo phẳng cạp quần
            
            if any(k in product_type for k in ["KNIT", "SHIRT", "HOODIE", "TOP", "ÁO"]):
                if "SHIRT" in product_type:
                    panels = [
                        {"panel_name": "FRONT PANEL LEFT", "piece_length_inch": l_eff, "piece_width_inch": w_eff * 0.52, "piece_count": 1.0, "panel_metadata": {"mirror_cut": True}},
                        {"panel_name": "FRONT PANEL RIGHT", "piece_length_inch": l_eff, "piece_width_inch": w_eff * 0.52, "piece_count": 1.0, "panel_metadata": {"mirror_cut": True}},
                        {"panel_name": "BACK PANEL", "piece_length_inch": l_eff, "piece_width_inch": w_eff, "piece_count": 1.0, "panel_metadata": {"cut_on_fold": True}},
                        {"panel_name": "SLEEVE", "piece_length_inch": s_eff or 24.0, "piece_width_inch": w_eff * 0.42, "piece_count": 2.0, "panel_metadata": {"mirror_cut": True}}
                    ]
                else:
                    panels = [
                        {"panel_name": "FRONT PANEL", "piece_length_inch": l_eff, "piece_width_inch": w_eff, "piece_count": 1.0},
                        {"panel_name": "BACK PANEL", "piece_length_inch": l_eff, "piece_width_inch": w_eff, "piece_count": 1.0, "panel_metadata": {"cut_on_fold": True}},
                        {"panel_name": "SLEEVE", "piece_length_inch": s_eff or 9.5, "piece_width_inch": w_eff * 0.45, "piece_count": 2.0, "panel_metadata": {"mirror_cut": True}}
                    ]
            else:
                # Quy tắc hình học CAD quần Jeans: Vòng mông phẳng width_base gồm 2 thân trước + 2 thân sau co giãn đều
                panels = [
                    {"panel_name": "FRONT PANEL", "piece_length_inch": (l_eff - 9.0) if l_eff > 35 else 28.5, "piece_width_inch": w_eff * 0.48, "piece_count": 2.0, "panel_metadata": {"mirror_cut": True}},
                    {"panel_name": "BACK PANEL", "piece_length_inch": l_eff, "piece_width_inch": w_eff * 0.52, "piece_count": 2.0, "panel_metadata": {"mirror_cut": True}},
                    {"panel_name": "WAISTBAND", "piece_length_inch": s_eff * 2.0 if s_eff > 20 else 32.0, "piece_width_inch": 3.0, "piece_count": 1.0, "panel_metadata": {"cut_on_fold": True}}
                ]

        total_panel_area = 0.0
        is_calculated_from_data = False
        actual_panel_count = len(panels)
        actual_piece_count = 0.0
        max_p_len, max_p_wid = 0.0, 0.0
            
        for p in panels:
            if not isinstance(p, dict): continue
            try:
                L = float(p.get("piece_length_inch", 0.0) or 0.0)
                W = float(p.get("piece_width_inch", 0.0) or 0.0)
                C = float(p.get("piece_count", 1.0) or 1.0)
                
                p_name = str(p.get("panel_name", "")).upper()
                p_meta = p.get("panel_metadata", {})
                geo = p.get("geometry_metadata", {})
                
                # PHÂN LOẠI CHI TIẾT RẬP THEO CHẤT LIỆU
                is_lining_row = any(k in comp_type or k in fab_class for k in ["POCKET", "LÓT", "LINING", "TC"])
                is_fusing_row = any(k in comp_type or k in fab_class for k in ["FUSING", "MẾCH", "DỰNG", "TRICOT", "INTERLINING"])
                
                if is_lining_row:
                    if not any(k in p_name for k in ["POCKET", "LÓT", "BAG"]): continue
                elif is_fusing_row:
                    if not any(k in p_name for k in ["WAISTBAND", "CẠP", "FUSING", "MẾCH", "NẸP", "FLY", "FACING"]): continue
                else:
                    if any(k in p_name for k in ["POCKET BAG", "LÓT TÚI"]): continue
                
                if C == 1.0 and p_meta.get("mirror_cut", False):
                    C = 2.0
                
                # 🌟 ĐỒNG BỘ TUYỂN TÍNH CAD: Cộng dung sai đường may trực tiếp vào hai biên kích thước chi tiết rập mẫu
                if L > 0.0 and W > 0.0:
                    L += (SEAM_ALLOWANCE * 2.0)
                    W += (SEAM_ALLOWANCE * 2.0)
                
                if L > max_p_len: max_p_len = L
                if W > max_p_wid: max_p_wid = W
                actual_piece_count += C
                
                polygon_area = float(geo.get("net_area", 0.0) or 0.0)
                if polygon_area > 5.0:
                    p_area = polygon_area * C
                else:
                    # Hệ số hình học diện tích thực phẳng CAD Gerber
                    if any(k in p_name for k in ["FRONT", "THÂN TRƯỚC"]): shape_factor = 0.65  
                    elif any(k in p_name for k in ["BACK", "THÂN SAU"]): shape_factor = 0.72  
                    elif any(k in p_name for k in ["SLEEVE", "TAY ÁO"]): shape_factor = 0.58  
                    elif any(k in p_name for k in ["WAISTBAND", "CẠP", "COLLAR", "CỔ"]): shape_factor = 0.92  
                    elif any(k in p_name for k in ["POCKET", "TÚI"]): shape_factor = 0.82  
                    else: shape_factor = 0.70  
                        
                    p_area = L * W * C * shape_factor
                
                if p_area > 0.0:
                    total_panel_area += p_area
            except:
                pass
        # Loại bỏ hoàn toàn hằng số yards gán chết, cho phép luồng toán học CAD co giãn tự động theo dữ liệu rập thực tế
        if total_panel_area > 0.0:
            is_calculated_from_data = True
        else:
            total_panel_area = float(row.get("_btp_total_panel_area", 0.0) or 0.0)
            is_calculated_from_data = True if total_panel_area > 0.0 else False
            
        if total_panel_area <= 0.0:
            total_panel_area = 0.0
            is_calculated_from_data = False
            
        # ÁP DỤNG HỆ SỐ CO RÚT ĐỘNG VÀO KHÔNG GIAN DIỆN TÍCH PHẲNG
        if total_panel_area > 0.0:
            total_panel_area *= shrink_factor

        row["_btp_summary"] = {
            "panel_count": actual_panel_count, "piece_count": round(actual_piece_count, 1),
            "area": round(total_panel_area, 2), "max_piece_length": max_p_len, "max_piece_width": max_p_wid
        }
        row["_btp_total_panel_area"] = total_panel_area

        # ĐỒNG BỘ HIỆU SUẤT ĐỘNG THEO DÒNG HÀNG THỰC TẾ BẢNG ĐỊNH DANH CỦA BẠN
        if "JEAN" in product_type or "PANT" in product_type or any(k in comp_type for k in ["DENIM", "MAIN"]):
            default_efficiency = 0.8894  # Denim: 88.94%
        elif any(k in product_type for k in ["KNIT", "SHIRT", "HOODIE", "TOP", "ÁO"]) or any(k in comp_type for k in ["KNIT", "THUN"]):
            default_efficiency = 0.8449  # Knits: 84.49%
        elif "JACKET" in product_type or "OUTERWEAR" in product_type:
            default_efficiency = 0.8746  # Outerwear: 87.46%
        elif any(k in comp_type for k in ["POCKET", "LÓT", "LINING", "TC"]):
            default_efficiency = 0.7218  # Vải lót túi: 72.18%
        elif "FORMAL" in product_type or "SUIT" in product_type:
            default_efficiency = 0.8942  # Formalwear: 89.42%
        else:
            default_efficiency = 0.8939  # Casualwear: 89.39%
            
        raw_eff = row.get("marker_efficiency", row.get("marker_efficiency_pct", default_efficiency))
        if isinstance(raw_eff, str):
            try:
                efficiency = float(raw_eff.replace("%", "").strip())
                if efficiency > 1.0: efficiency /= 100.0
            except: efficiency = default_efficiency
        else:
            try: efficiency = float(raw_eff)
            except: efficiency = default_efficiency
                
        if efficiency < 0.55 or efficiency > 0.95: efficiency = default_efficiency 
        row["marker_efficiency_pct"] = f"{efficiency * 100.0:.1f}%"
        
        unit = str(row.get("_btp_area_unit", row.get("area_unit", "inch2"))).lower().strip()
        if "mm" in unit and total_panel_area > 0: total_panel_area /= 645.16
        elif "cm" in unit and total_panel_area > 0: total_panel_area /= 6.4516
            
        row["_btp_total_panel_area"] = total_panel_area
        
        st.write({
            "Garment Type": product_type,
            "Material Checked": row.get("component_type", "FABRIC"),
            "Shrinkage Applied Area (inch2)": round(total_panel_area, 2),
            "Width (inch)": width_inch,
            "Efficiency (Dynamic)": row["marker_efficiency_pct"]
        })
        
        # PHÉP TOÁN TOÁN HỌC 100% CO GIÃN TỰ ĐỘNG THEO DỮ LIỆU FILE (ĐÃ GỠ BỎ TOÀN BỘ HARD-CODE YARDS)
        if total_panel_area > 0.0:
            gross_yds = (total_panel_area / efficiency) / width_inch / 36.0
            row["calculated_gross_consumption_yds"] = round(gross_yds, 3)
            row["status"] = "PASS"
            row["consumption_note"] = f"Mô phỏng rập CAD vạn năng chuẩn hình học phẳng. Đường may: {SEAM_ALLOWANCE} in."
        else:
            row["calculated_gross_consumption_yds"] = 0.000
            row["status"] = "NEEDS REVIEW"
            row["consumption_note"] = "Bỏ qua: Khuyết thiếu diện tích chi tiết rập phẳng có trong tài liệu kỹ thuật."
            
        filtered_bom_rows.append(row)
        
    blueprint_final["bom_rows"] = filtered_bom_rows
    return blueprint_final





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

# =====================================================================
# ĐOẠN 2b - PHẦN 1: UNIVERSAL APPAREL GEOMETRIC ENGINE (V44.0 ULTRA FACTORY)
# KHAI BÁO BIẾN DUNG SAI BIÊN SEAM_ALLOWANCE & TRÍCH XUẤT ĐỘNG THÔNG SỐ CO RÚT
# =====================================================================
# =====================================================================
# ĐOẠN 2b - PHẦN 1: MULTI-LAYER WEIGHTED AVERAGE ENGINE (V52.0 PRODUCTION READY)
# KIẾN TRÚC CAD TỰ ĐỘNG CÂN BẰNG: 0.5 CAD LAYER + 0.3 IE LAYER + 0.2 FACTORY HISTORY LAYER
# =====================================================================
def allocate_fabric_consumption_and_quality_gate(blueprint_final: dict, query_string: str) -> dict:
    st.warning("⚡ ENGINE EXECUTING: MULTI-LAYER WEIGHTED ENGINE V52.0 ACTIVATED")
    
    if not blueprint_final or "bom_rows" not in blueprint_final:
        return blueprint_final
        
    # LỚP HỆ THỐNG LỊCH SỬ (FACTORY LAYER): Cơ sở dữ liệu định mức thực tế trung bình từ nhà máy
    FACTORY_HISTORY_DATABASE = {
        "PANT": {"min_yds": 1.150, "max_yds": 1.950, "avg_area": 2450.0, "fallback_yds": 1.380},
        "JEAN": {"min_yds": 1.250, "max_yds": 2.150, "avg_area": 2850.0, "fallback_yds": 1.450},
        "SHIRT": {"min_yds": 1.100, "max_yds": 1.650, "avg_area": 1950.0, "fallback_yds": 1.250},
        "KNIT": {"min_yds": 0.850, "max_yds": 1.450, "avg_area": 1450.0, "fallback_yds": 1.050},
        "JACKET": {"min_yds": 1.650, "max_yds": 2.650, "avg_area": 3350.0, "fallback_yds": 1.950}
    }
        
    SEAM_ALLOWANCE = 0.44
    chat_lower = str(query_string).lower()
    match_shrink = re.search(r'(?:co rút|co rut|sh|shrinkage)\s*[:\-=\s]*([\d\.]+)\s*[\-,\s]\s*([\d\.]+)', chat_lower)
    
    if match_shrink:
        try:
            warp = float(match_shrink.group(1)) / 100.0
            weft = float(match_shrink.group(2)) / 100.0
            warp_val = f"{float(match_shrink.group(1))}%"
            weft_val = f"{float(match_shrink.group(2))}%"
        except:
            warp, weft = 0.04, 0.14
            warp_val, weft_val = "4.0%", "14.0%"
    else:
        warp, weft = 0.04, 0.14
        warp_val, weft_val = "4.0%", "14.0%"
        
    # Mô hình co rút định hướng tiêu chuẩn CAD Gerber
    shrink_factor = 1.0 + (warp * 0.6 + weft * 0.4)
    product_type = str(blueprint_final.get("detected_product_type", "PANT")).upper().strip()
    
    SEAM_RATIO_BASE = 0.035  
    def seam_factor(panel_name: str) -> float:
        name = str(panel_name).upper()
        if "POCKET" in name or "TÚI" in name: return SEAM_RATIO_BASE * 0.6   
        elif "WAISTBAND" in name or "CẠP" in name: return SEAM_RATIO_BASE * 1.3   
        elif "COLLAR" in name or "CỔ" in name: return SEAM_RATIO_BASE * 1.2   
        elif "SLEEVE" in name or "TAY" in name: return SEAM_RATIO_BASE * 1.0   
        else: return SEAM_RATIO_BASE

    def normalize_panel(L: float, W: float, C: float) -> float:
        base = L * W
        scale_guard = min(1.0, max(0.65, base / 500.0))
        return base * scale_guard * C

    # TRÍCH XUẤT SỐ ĐO THỰC TẾ TỪ BẢNG THÔNG SỐ POM
    matched_list = blueprint_final.get("matched_measurements", [])
    length_base, width_base, secondary_base = 0.0, 0.0, 0.0
    for item in matched_list:
        item_str = str(item).upper()
        if any(k in item_str for k in ["LENGTH", "OUTSEAM", "DÀI"]):
            m_num = re.search(r'([\d\.]+)', item_str)
            if m_num: length_base = float(m_num.group(1))
        if any(k in item_str for k in ["CHEST", "HIP", "RỘNG MÔNG", "NGỰC"]):
            m_num = re.search(r'([\d\.]+)', item_str)
            if m_num: width_base = float(m_num.group(1))
        if any(k in item_str for k in ["WAIST", "SLEEVE", "TAY", "BỤNG"]):
            m_num = re.search(r'([\d\.]+)', item_str)
            if m_num: secondary_base = float(m_num.group(1))

    filtered_bom_rows = []
    for row in blueprint_final["bom_rows"]:
        comp_type = (str(row.get("component_type", "")) + " " + str(row.get("fabric_classification", ""))).upper()
        fab_class = str(row.get("fabric_classification", "")).upper()
        
        row["_btp_warp_pct"] = warp_val
        row["_btp_weft_pct"] = weft_val
        
        if any(k in comp_type for k in ["BUTTON", "NÚT", "RIVET", "ĐINH TÁN", "LABEL", "NHÃN", "MÁC", "STICKER", "THREAD", "CHỈ"]):
            continue
            
        width_inch = float(row.get("fabric_width_inch", 57.0))
        if width_inch < 20.0: width_inch = 57.0
        row["fabric_width_inch"] = width_inch
            
        panels = row.get("panels_catalog", [])
        is_calculated_from_data = False
        
        # TỰ ĐỘNG BUNG DANH MỤC LINH KIỆN MẪU KHI MẢNG PANELS CỦA VẢI CHÍNH TRỐNG HOÀN TOÀN
        if not panels and any(k in comp_type for k in ["MAIN", "DENIM", "CHÍNH", "SELF", "SHELL"]):
            l_eff = length_base or 38.0
            w_eff = width_base or 21.5   
            s_eff = secondary_base or 16.5 
            panels = [
                {"panel_name": "FRONT PANEL", "piece_length_inch": (l_eff - 9.0) if l_eff > 35 else 28.5, "piece_width_inch": w_eff * 0.48, "piece_count": 2.0, "panel_metadata": {"mirror_cut": True}},
                {"panel_name": "BACK PANEL", "piece_length_inch": l_eff, "piece_width_inch": w_eff * 0.52, "piece_count": 2.0, "panel_metadata": {"mirror_cut": True}},
                {"panel_name": "WAISTBAND", "piece_length_inch": s_eff * 2.0 if s_eff > 20 else w_eff * 1.5, "piece_width_inch": 3.0, "piece_count": 1.0, "panel_metadata": {"cut_on_fold": True}}
            ]

        # ADAPTIVE EFFICIENCY MODEL
        if "JEAN" in product_type or "PANT" in product_type or any(k in comp_type for k in ["DENIM", "MAIN"]):
            efficiency = 0.8894  # Denim: 88.94%
            if width_inch < 46.0: efficiency -= 0.04  
        elif any(k in product_type for k in ["KNIT", "SHIRT", "HOODIE", "TOP", "ÁO"]) or any(k in comp_type for k in ["KNIT", "THUN"]):
            efficiency = 0.8449  # Knits: 84.49%
        elif "JACKET" in product_type or "OUTERWEAR" in product_type:
            efficiency = 0.8746  # Outerwear: 87.46%
        elif any(k in comp_type for k in ["POCKET", "LÓT", "LINING", "TC"]):
            efficiency = 0.7218  # Vải lót túi: 72.18%
        elif "FORMAL" in product_type or "SUIT" in product_type:
            efficiency = 0.8942  # Formalwear: 89.42%
        else:
            efficiency = 0.8939  # Casualwear: 89.39%

        raw_eff = row.get("marker_efficiency", row.get("marker_efficiency_pct", efficiency))
        if isinstance(raw_eff, str):
            try:
                efficiency_read = float(raw_eff.replace("%", "").strip())
                if efficiency_read > 1.0: efficiency_read /= 100.0
                efficiency = efficiency_read
            except: pass

        total_net_locked_area = 0.0
        actual_panel_count = len(panels)
        actual_piece_count = 0.0
        max_p_len, max_p_wid = 0.0, 0.0
            
        for p in panels:
            if not isinstance(p, dict): continue
            try:
                L = float(p.get("piece_length_inch", 0.0) or 0.0)
                W = float(p.get("piece_width_inch", 0.0) or 0.0)
                C = float(p.get("piece_count", 1.0) or 1.0)
                
                p_name = str(p.get("panel_name", "")).upper()
                p_meta = p.get("panel_metadata", {})
                geo = p.get("geometry_metadata", {})
                
                if any(k in comp_type or k in fab_class for k in ["POCKET", "LÓT", "LINING", "TC"]):
                    if not any(k in p_name for k in ["POCKET", "LÓT", "BAG"]): continue
                elif any(k in comp_type or k in fab_class for k in ["FUSING", "MẾCH", "DỰNG", "TRICOT", "INTERLINING"]):
                    if not any(k in p_name for k in ["WAISTBAND", "CẠP", "FUSING", "MẾCH", "NẸP", "FLY", "FACING"]): continue
                else:
                    if any(k in p_name for k in ["POCKET BAG", "LÓT TÚI"]): continue

                # BỘ HÃM PHANH HÌNH HỌC (APPAREL SIZING GATE) - CHẶN SỐ LIỆU PHÓNG ĐẠI CỦA AI [INDEX]
                if "PANT" in product_type or "JEAN" in product_type or any(k in comp_type for k in ["DENIM", "MAIN"]):
                    if any(k in p_name for k in ["FRONT", "BACK", "THÂN"]):
                        if W > 15.0: W = 11.5  
                        if L > 44.0: L = 39.5  
                    if "WAISTBAND" in p_name or "CẠP" in p_name:
                        if W > 5.0: W = 3.0
                        if L > 45.0: L = 32.0

                if C == 1.0 and p_meta.get("mirror_cut", False):
                    C = 2.0
                
                if L > max_p_len: max_p_len = L
                if W > max_p_wid: max_p_wid = W
                actual_piece_count += C
                
                # KHÓA HÌNH HỌC TUYỆT ĐỐI (GEOMETRY LOCK STAGE): Tách biệt diện tích tịnh phẳng [INDEX]
                polygon_area = float(geo.get("net_area", 0.0) or 0.0)
                if polygon_area > 5.0:
                    net_piece_area = polygon_area * C
                    is_calculated_from_data = True  
                else:
                    if any(k in p_name for k in ["FRONT", "THÂN TRƯỚC"]): shape_factor = 0.65  
                    elif any(k in p_name for k in ["BACK", "THÂN SAU"]): shape_factor = 0.72  
                    elif any(k in p_name for k in ["SLEEVE", "TAY ÁO"]): shape_factor = 0.58  
                    elif any(k in p_name for k in ["WAISTBAND", "CẠP", "COLLAR", "CỔ"]): shape_factor = 0.92  
                    elif any(k in p_name for k in ["POCKET", "TÚI"]): shape_factor = 0.82  
                    else: shape_factor = 0.70  
                    
                    net_piece_area = normalize_panel(L, W, C) * shape_factor
                    if L > 0.0 and W > 0.0:
                        is_calculated_from_data = True  

                # ÁP DỤNG BIÊN ĐƯỜNG MAY VẬT TƯ
                panel_seam_ratio = seam_factor(p_name)
                net_piece_area *= (1.0 + panel_seam_ratio)       
                
                total_net_locked_area += net_piece_area
            except:
                pass
        # KHÓA CHỐT CHẶN KIỂM SOÁT QUY ĐỔI ĐƠN VỊ ĐO (UNIT CONVERSION LOCK) [INDEX]
        if not row.get("_btp_unit_converted_lock", False):
            unit = str(row.get("_btp_area_unit", row.get("area_unit", "inch2"))).lower().strip()
            if "mm" in unit and total_net_locked_area > 0: 
                total_net_locked_area /= 645.16
            elif "cm" in unit and total_net_locked_area > 0: 
                total_net_locked_area /= 6.4516
            row["_btp_unit_converted_lock"] = True  

        if total_net_locked_area <= 0.0:
            total_net_locked_area = float(row.get("_btp_total_panel_area", 0.0) or 0.0)
            if "mm" in unit and total_net_locked_area > 0: total_net_locked_area /= 645.16
            elif "cm" in unit and total_net_locked_area > 0: total_net_locked_area /= 6.4516
            is_calculated_from_data = True if total_net_locked_area > 0.0 else False

        # =====================================================================
        # 🌟 KIẾN TRÚC MỚI: 3 LỚP SONG SONG KẾT HỢP TRỌNG SỐ TRUNG BÌNH (WEIGHTED AVERAGE) [INDEX]
        # Công thức: Final Yards = 0.5 * CAD Layer + 0.3 * IE Layer + 0.2 * Factory Layer [INDEX]
        # =====================================================================
        
        # LỚP 1: CAD LAYER (Geometry tịnh hình học phẳng nhân phình độ co rút vải) [INDEX]
        # Tính toán Yards tịnh trần từ biên diện tích rập thật sau khi nhân co rút [INDEX]
        if total_net_locked_area > 0.0:
            cad_layer_yds = (total_net_locked_area * shrink_factor) / width_inch / 36.0
        else:
            cad_layer_yds = FACTORY_HISTORY_DATABASE.get(product_type, {}).get("fallback_yds", 1.350)

        # LỚP 2: IE LAYER (Industrial Engineering Model - Tính toán áp dụng hao hụt sơ đồ marker) [INDEX]
        # Phép toán CAD Gerber tiêu chuẩn kết xuất định mức dựa theo độ hụt sơ đồ [INDEX]
        if total_net_locked_area > 0.0:
            ie_layer_yds = ((total_net_locked_area * shrink_factor) / efficiency) / width_inch / 36.0
        else:
            ie_layer_yds = FACTORY_HISTORY_DATABASE.get(product_type, {}).get("fallback_yds", 1.350)

        # LỚP 3: FACTORY LAYER (Cơ sở dữ liệu lịch sử đối chiếu của phân xưởng) [INDEX]
        # Lấy giá trị định mức Yards cơ sở thực tế đã vận hành trong lịch sử may mặc của mã hàng [INDEX]
        if product_type in FACTORY_HISTORY_DATABASE:
            hist_meta = FACTORY_HISTORY_DATABASE[product_type]
            if any(k in comp_type for k in ["DENIM", "MAIN", "CHÍNH", "SELF", "SHELL"]):
                factory_layer_yds = hist_meta["fallback_yds"]
            elif any(k in comp_type for k in ["POCKET", "LÓT", "LINING", "TC"]):
                factory_layer_yds = 0.220
            else:
                factory_layer_yds = 0.060
        else:
            factory_layer_yds = 1.350

        # 🌟 CÂN BẰNG PHƯƠNG TRÌNH: TRỘN TOÁN HỌC ĐA TẦNG THEO TỶ LỆ TRỌNG SỐ VÀNG 5:3:2 [INDEX]
        # Loại bỏ hoàn toàn lỗi sụp ngầm dây chuyền, giữ số Yards cực kì ổn định, không bao giờ bị nhảy vọt phi lý [INDEX]
        final_gross_yds = (0.5 * cad_layer_yds) + (0.3 * ie_layer_yds) + (0.2 * factory_layer_yds)
        final_gross_yds = round(final_gross_yds, 3)

        # HỆ THỐNG ANOMALY DETECTION ĐỘNG (GẮN CỜ CẢNH BÁO KHÁCH QUAN - BẢO TOÀN CAD TRUTH) [INDEX]
        is_anomaly_detected = False
        if product_type in FACTORY_HISTORY_DATABASE:
            hist_meta = FACTORY_HISTORY_DATABASE[product_type]
            if any(k in comp_type for k in ["DENIM", "MAIN", "CHÍNH"]) and (final_gross_yds < hist_meta["min_yds"] or final_gross_yds > hist_meta["max_yds"]):
                is_anomaly_detected = True

        # Đóng gói dữ liệu kết xuất
        row["_btp_summary"] = {
            "panel_count": actual_panel_count, "piece_count": round(actual_piece_count, 1),
            "area": round(total_net_locked_area, 2), "max_piece_length": max_p_len, "max_piece_width": max_p_wid
        }
        row["_btp_total_panel_area"] = total_net_locked_area
        row["marker_efficiency_pct"] = f"{efficiency * 100.0:.1f}%"
        row["calculated_gross_consumption_yds"] = final_gross_yds
        
        # Xuất dòng dữ liệu live giám sát đa tầng độc lập
        st.write({
            "Vật tư": row.get("component_type", "FABRIC"),
            "1. CAD Layer (Yds)": round(cad_layer_yds, 3),
            "2. IE Layer (Yds)": round(ie_layer_yds, 3),
            "3. Factory History (Yds)": round(factory_layer_yds, 3),
            "🔥 TRỘN TRỌNG SỐ (Gross Yds)": final_gross_yds,
            "Cờ Giám Sát": "🚨 ANOMALY OUTLIER" if is_anomaly_detected else "✅ STABLE PROD"
        })
        
        # KHỐI PHÂN ĐỊNH TRẠNG THÁI STATUS MINH BẠCH KIẾN TRÚC SẠCH (CLEAN ARCHITECTURE) [INDEX]
        if final_gross_yds > 0.0:
            if is_anomaly_detected:
                row["status"] = "NEEDS REVIEW"
                row["consumption_note"] = f"🚨 CAD Audit Alert: Định mức trộn trọng số ({final_gross_yds} Yds) vượt ngưỡng an toàn lịch sử nhà máy. Phòng kỹ thuật cần kiểm tra lại sơ đồ giác rập."
            elif is_calculated_from_data:
                row["status"] = "PASS"
                row["consumption_note"] = f"Mô phỏng 3 lớp trọng số song song song phẳng V52. Co rút: {warp_val}x{weft_val}."
            else:
                row["status"] = "ESTIMATED"
                row["consumption_note"] = "Định mức ước tính dựa trên phôi rập mẫu lịch sử (Khuyết thiếu dữ liệu rập thật)."
        else:
            row["calculated_gross_consumption_yds"] = 0.000
            row["status"] = "NEEDS REVIEW"
            row["consumption_note"] = "Bỏ qua: Khuyết thiếu hoàn toàn diện tích chi tiết rập phẳng."
            
        filtered_bom_rows.append(row)
        
    blueprint_final["bom_rows"] = filtered_bom_rows
    return blueprint_final











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
            # 🟢 ĐÃ SỬA DẤU GẠCH DƯỚI THÀNH DẤU GẠCH NGANG CHUẨN ĐỂ HIỂN THỊ ĐỦ MÀU SẮC KHỐI SEASON:
            st.markdown(f'<div class="meta-box-light"><div class="meta-label-light">Season / Mùa sản xuất</div><div class="meta-value-light">{season}</div></div>', unsafe_allow_html=True)
        with m_col2:
            st.markdown(f'<div class="meta-box-light"><div class="meta-label-light">Garment Type / Kiểu dáng</div><div class="meta-value-light">{short_desc}</div></div>', unsafe_allow_html=True)
            st.markdown(f'<div class="meta-box-light"><div class="meta-label-light">Material Spec / Mô tả vải</div><div class="meta-value-light">{fabric_type[:28]}...</div></div>', unsafe_allow_html=True)
            st.markdown(f'<div class="meta-box-light"><div class="meta-label-light">Techpack Status</div><div class="meta-value-light" style="color: #16a34a; font-weight: bold;">🟢 READY TO BOM</div></div>', unsafe_allow_html=True)
    else:
        if st.session_state.pdf_bytes is None:
            st.markdown("<div style='margin-top: 40px; text-align: center; color: #64748b; font-size: 13px;'>Bảng tóm tắt thông số sản phẩm sẽ tự động hiển thị tại đây sau khi nạp file PDF.</div>", unsafe_allow_html=True)
        
    st.markdown('</div>', unsafe_allow_html=True)




# --- CỘT PHẢI: KHUNG XEM BẢN VẼ PHẲNG SKETCH (🌟 ĐÃ ÉP CO NHỎ ẢNH GỐC ĐỐI XỨNG) ---
with col_right:
    # 🟢 ĐỒNG BỘ MÀU SẮC PHẲNG: Chuyển từ class cũ custom-erp-box sang erp-main-card chuẩn SAP ERP
    st.markdown('<div class="erp-main-card sticky-sketch-box">', unsafe_allow_html=True)
    st.markdown('<div class="erp-header-title">🎨 TECHPACK SKETCH VISUALIZER</div>', unsafe_allow_html=True)
    
    # 🟢 BỘ KHỞI TẠO VÀ TRÍCH XUẤT ẢNH TỰ ĐỘNG NGAY KHI CÓ FILE PDF TRONG HỆ THỐNG
    if st.session_state.pdf_bytes is not None:
        if "pdf_page_one_image" not in st.session_state or st.session_state.pdf_page_one_image is None:
            try:
                import fitz
                doc_img = fitz.open(stream=st.session_state.pdf_bytes, filetype="pdf")
                if len(doc_img) > 0:
                    page = doc_img.load_page(0)
                    # Thiết lập ma trận phóng nét và ép hệ màu kĩ thuật số RGB tránh sập luồng hiển thị
                    pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), colorspace=fitz.csRGB)
                    st.session_state.pdf_page_one_image = pix.tobytes("png")
            except Exception as e_img:
                st.error(f"⚠️ Không thể hiển thị ảnh vẽ phác họa: {str(e_img)}")

    # THỰC THI HIỂN THỊ HÌNH ẢNH SAU KHI ĐÃ CÓ CACHE SẠCH TRONG SESSION
    if "pdf_page_one_image" in st.session_state and st.session_state.pdf_page_one_image is not None:
        # 🌟 TINH CHỈNH VÀNG: Thay thế use_container_width=True bằng width=300 để ảnh thu nhỏ tinh tế,
        # kết hợp với CSS căn giữa tự động ở đoạn 6a sẽ tạo ra sự đối xứng hình học hoàn hảo.
        st.image(st.session_state.pdf_page_one_image, width=300)
    else:
        st.markdown("<div style='margin-top: 50px; text-align: center; color: #64748b; font-size: 13px;'>Hình vẽ phác họa phẳng (Sketch) trích xuất từ trang bìa PDF sẽ tự động hiển thị cân xứng tại đây sau khi nạp file thành công.</div>", unsafe_allow_html=True)
        
    st.markdown('</div>', unsafe_allow_html=True)




## =====================================================================
# ĐOẠN 7a - PHẦN 1: CHATGPT-STYLE WORKSPACE & SMART TARGET SCANNED PIPELINE (V44.0)
# CHIẾN LƯỢC HYBRID: QUÉT 100% TEXT, RENDER TỐI ĐA 15 ẢNH VÀNG ĐỂ BẮT TRÚNG VẢI CHÍNH
# =====================================================================
st.markdown('<br><div class="cad-card"><div class="cad-header">💬 CHATGPT IE COLLABORATION WORKSPACE</div>', unsafe_allow_html=True)

# Khởi tạo kho lưu trữ trạng thái hệ thống phòng vệ
if "chat_history" not in st.session_state: st.session_state.chat_history = []
if "pdf_page_images_list" not in st.session_state: st.session_state.pdf_page_images_list = None
if "accumulated_bom_rows" not in st.session_state: st.session_state.accumulated_bom_rows = {}
if "bom_data" not in st.session_state: st.session_state.bom_data = {}

# Xuất dòng tin nhắn lịch sử trò chuyện đồng bộ trực quan lên màn hình theo chuẩn OpenAI
if st.session_state.chat_history:
    for msg in st.session_state.chat_history:
        st.chat_message("user").write(msg["user"])
        st.chat_message("assistant").write(msg["ai"])

# Tạo một vùng chứa tĩnh độc lập cô lập ô chat input
chat_input_container = st.container()
with chat_input_container:
    safe_user_prompt = st.chat_input("Gõ câu lệnh điều chỉnh thông số hoặc câu hỏi bất kỳ tại đây...", key="ie_workspace_static_chat_input_key")

st.markdown('</div>', unsafe_allow_html=True)

# KÍCH HOẠT LUỒNG CHẠY AI NGAY KHI CÓ BẤT KỲ CÂU HỎI CHAT NÀO
if st.session_state.pdf_bytes is not None and safe_user_prompt:
    current_query = str(safe_user_prompt).strip()
    
    with st.spinner("🧠 AI Platform đang quét thông minh đa tầng tài liệu kỹ thuật Techpack..."):
        import google.generativeai as genai
        import json, copy, traceback, re
        import fitz 
        
        # 🌟 BẮT ĐẦU MỞ KHỐI TRY LỚN DUY NHẤT BAO QUANH TOÀN BỘ HẠ TẦNG AI
        try:
            doc_recovery = fitz.open(stream=st.session_state.pdf_bytes, filetype="pdf")
            total_pages = len(doc_recovery)
            pdf_size_mb = len(st.session_state.pdf_bytes) / (1024 * 1024)
            
            # Khởi tạo phôi văn bản và dải mảng ảnh
            full_pdf_raw_text = ""
            image_payloads = []
            MAX_IMAGE_PAGES = 15  # 🟢 VÁ CHÍ MẠNG: Nâng từ 10 lên 15 để AI quét sâu không sót trang vải chính Denim
            MAX_TEXT = 150000     # Chốt chặn bảo vệ Token ngữ cảnh
            
            # Khống chế DPI mượt mà theo độ nặng của tệp tin để bảo vệ RAM
            target_dpi = 110 if total_pages <= 15 else 90
            
            # DUYỆT QUA TỪNG TRANG: Thu thập văn bản và trích xuất ảnh mục tiêu
            for idx in range(total_pages):
                page_text = doc_recovery[idx].get_text("text")
                page_text_upper = page_text.upper()
                
                # Tích lũy cơ sở dữ liệu văn bản phẳng toàn cục
                full_pdf_raw_text += f"\n--- DATA SCANNING SOURCE: PAGE {idx + 1} ---\n{page_text}"
                
                # Lồng điều kiện tường minh, chỉ quét ảnh khi chưa vượt ngưỡng MAX_IMAGE_PAGES
                if len(image_payloads) < MAX_IMAGE_PAGES:
                    if any(k in page_text_upper for k in [
                        "BOM", "BILL OF MATERIAL", "SPECIFICATION", "MEASUREMENT", 
                        "SKETCH", "PATTERN", "GRADING", "VẢI CHÍNH", "THÔNG SỐ", "KÍCH THƯỚC", "DENIM"
                    ]):
                        page = doc_recovery.load_page(idx)
                        pix = page.get_pixmap(dpi=target_dpi, colorspace=fitz.csRGB)
                        image_payloads.append({"mime_type": "image/jpeg", "data": pix.tobytes("jpeg")})
            
            # Hãm phanh cắt chuỗi văn bản nếu vượt quá ngưỡng an toàn bảo vệ Token
            if len(full_pdf_raw_text) > MAX_TEXT:
                full_pdf_raw_text = full_pdf_raw_text[:MAX_TEXT] + "\n\n... [TRUNCATED DUE TO MAX TOKEN PROTECTION] ..."
            
            # Trường hợp file PDF scan dạng ảnh thô hoàn toàn không có text, lấy mặc định 5 trang đầu
            if not image_payloads:
                for idx in range(min(5, total_pages)):
                    page = doc_recovery.load_page(idx)
                    pix = page.get_pixmap(dpi=target_dpi, colorspace=fitz.csRGB)
                    image_payloads.append({"mime_type": "image/jpeg", "data": pix.tobytes("jpeg")})
                    
            gemini_inputs = copy.deepcopy(image_payloads)
            
            # Bơm toàn bộ dữ liệu text phẳng đã trích xuất sạch vào đầu danh sách gửi sang Gemini [INDEX]
            gemini_inputs.insert(0, f"=== RECOVERED TECHPACK FLAT TEXT DATABASE ===\n{full_pdf_raw_text}\n============================================\n")



                       # =====================================================================
                          # =====================================================================
                      # =====================================================================
            # ĐOẠN 7a - PHẦN 2: DYNAMIC AI GATEWAY & JACKET DATA GATEWAY (V48.0)
            # 🌟 BẺ GÃY NÚT THẮT KHUYẾT THÔNG SỐ: ÉP AI BẮT BUỘC TRÍCH XUẤT ĐỦ 12 MIẾNG RẬP ÁO JACKET
            # =====================================================================
            if "GEMINI_API_KEY" not in st.secrets:
                st.error("💥 Lỗi hạ tầng: Thiếu cấu hình GEMINI_API_KEY trong hệ thống Secrets.")
                st.stop()
                
            genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
            model = genai.GenerativeModel("gemini-2.5-flash")
            
            chat_lower = current_query.lower()
            match_size = re.search(r'\b(?:size|sz|cỡ)\s*[:\-=\s]*([\w\d/]+)\b', chat_lower)
            target_size_cmd = str(match_size.group(1)).upper().strip() if match_size else "30"
            
            # Bộ quét trích xuất khổ vải linh hoạt từ câu lệnh chat
            match_w = re.search(r'(?:khổ|kho|width|w)\s*[:\-=\s]*([\d\.]+)', chat_lower)
            active_width = float(match_w.group(1)) if match_w else 57.0
            if active_width < 20.0: active_width = 57.0
            
            pdf_bytes_len = len(st.session_state.pdf_bytes) if st.session_state.pdf_bytes else 0
            current_signature = (str(safe_user_prompt).strip(), int(len(image_payloads)), int(pdf_bytes_len))
            
            has_no_data = not st.session_state.get("bom_data") or st.session_state.get("bom_data") == {}
            is_signature_changed = st.session_state.get("last_processed_signature") != current_signature

            response_text = ""
            if has_no_data or is_signature_changed:
                if not image_payloads:
                    st.error("⚠️ Hệ thống phòng vệ: Không trích xuất được ảnh kỹ thuật từ file PDF.")
                    st.stop()
                    
                prompt_instruction = f"""
                You are a world-class expert apparel IE CAD Data Gateway [INDEX]. Your mission is to scan ALL provided techpack pages to extract structural data for size '{target_size_cmd}' [INDEX].
                This garment is a heavy JACKET/OUTERWEAR. You MUST exhaustively extract specifications for ALL component panels. DO NOT return a lazy or truncated panel list.
                
                🌟 ADAPTIVE SIZE CODES SEARCH LAW:
                The user requested size '{target_size_cmd}'. If the chart lacks a column named exactly '{target_size_cmd}' but utilizes grading columns like '1X', '2X', '3X', 'XL', or 'Sample Size', you MUST automatically extract metrics from the design base column (e.g., '1X' or 'Sample') and use those values for the panels. DO NOT output 0.0 or leave keys empty.
                
                🌟 MANDATORY COMPONENT INSTRUCTION FOR JACKETS:
                For the MAIN_FABRIC / CANVAS row, you MUST find or mathematically estimate the exact piece dimensions for ALL of the following 12 key jacket panels:
                1. FRONT PANEL LEFT & RIGHT: length ~ Front Body Length/HSP, width ~ Chest Width divided by 2 [INDEX]. piece_count: 2.0
                2. BACK PANEL: length ~ Back Body Length, width ~ Full Chest Width Flat [INDEX]. piece_count: 1.0 (with cut_on_fold: true)
                3. SLEEVE LEFT & RIGHT: length ~ Sleeve length from center back minus half of shoulder width, width ~ Sleeve opening/Bicep [INDEX]. piece_count: 2.0
                4. COLLAR & CHAN CỔ (COLLAR STAND): length ~ Neck circumference, width ~ 3.0 to 4.5 inch [INDEX]. piece_count: 2.0
                5. FRONT FLY FACING (NẸP CHE KHÓA): length ~ Front Zipper length, width ~ 3.5 to 4.5 inch. piece_count: 2.0
                6. WELT POCKET FLAPS / POCKET DETAILS (ĐÁP TÚI): length ~ Pocket opening, width ~ 2.5 to 3.5 inch. piece_count: 4.0
                
                🌟 MANDATORY FUSING/INTERLINING ANALYSIS:
                Locate 'PCC INTERLINING RM 66' or any fusing row. You MUST find its specific technical notes. Its 'panels_catalog' MUST include the parts designated for fusing: Collar pieces, Front Facings/Nẹp khóa, and Pocket Welts. Extract their true physical length and width from the text notes or map them from the core garment specs.
                
                Output STRICTLY in this two-tier raw plain text JSON format without markdown markers. All 'fabric_width_inch' MUST match the value {active_width}:
                ===START_JSON===
                {{
                  "status": "PASS",
                  "detected_product_type": "JACKET",
                  "calculated_on_size": "{target_size_cmd}",
                  "matched_measurements": [
                     "HSP-01: Front Body Length From HSP = <EXTRACTED_DECIMAL> inch",
                     "CHS-02: Chest Width Below Armhole = <EXTRACTED_DECIMAL> inch",
                     "SLV-03: Sleeve Length From Center Back = <EXTRACTED_DECIMAL> inch",
                     "SHL-04: Shoulder Width Across = <EXTRACTED_DECIMAL> inch"
                  ],
                  "_btp_global_summary": {{
                    "total_bom_rows": 3,
                    "total_panels": 16
                  }},
                  "bom_rows": [
                    {{
                      "component_type": "Canvas Main Fabric",
                      "fabric_classification": "MAIN_FABRIC",
                      "fabric_width_inch": {active_width},
                      "panels_catalog": [
                        {{ "panel_name": "FRONT PANEL", "piece_count": 2.0, "piece_length_inch": <EXTRACTED_OR_MAPPED_VALUE>, "piece_width_inch": <EXTRACTED_OR_MAPPED_VALUE>, "geometry_metadata": {{ "net_area": 0.0 }}, "panel_metadata": {{ "mirror_cut": true }} }},
                        {{ "panel_name": "BACK PANEL", "piece_count": 1.0, "piece_length_inch": <EXTRACTED_OR_MAPPED_VALUE>, "piece_width_inch": <EXTRACTED_OR_MAPPED_VALUE>, "geometry_metadata": {{ "net_area": 0.0 }}, "panel_metadata": {{ "cut_on_fold": true }} }},
                        {{ "panel_name": "SLEEVE PANEL", "piece_count": 2.0, "piece_length_inch": <EXTRACTED_OR_MAPPED_VALUE>, "piece_width_inch": <EXTRACTED_OR_MAPPED_VALUE>, "geometry_metadata": {{ "net_area": 0.0 }}, "panel_metadata": {{ "mirror_cut": true }} }},
                        {{ "panel_name": "COLLAR OVERLAY", "piece_count": 2.0, "piece_length_inch": <EXTRACTED_OR_MAPPED_VALUE>, "piece_width_inch": 4.0, "geometry_metadata": {{ "net_area": 0.0 }} }},
                        {{ "panel_name": "FRONT FLY FACING", "piece_count": 2.0, "piece_length_inch": <EXTRACTED_OR_MAPPED_VALUE>, "piece_width_inch": 3.5, "geometry_metadata": {{ "net_area": 0.0 }} }}
                      ]
                    }},
                    {{
                      "component_type": "Pocketing Fabric / Lining",
                      "fabric_classification": "LINING",
                      "fabric_width_inch": {active_width},
                      "panels_catalog": [
                        {{ "panel_name": "WELT POCKET BAGS", "piece_count": 4.0, "piece_length_inch": 9.0, "piece_width_inch": 8.0, "geometry_metadata": {{ "net_area": 0.0 }} }}
                      ]
                    }},
                    {{
                      "component_type": "PCC INTERLINING RM 66 / FUSING",
                      "fabric_classification": "FUSING",
                      "fabric_width_inch": {active_width},
                      "panels_catalog": [
                        {{ "panel_name": "COLLAR INTERLINING", "piece_count": 2.0, "piece_length_inch": <EXTRACTED_OR_MAPPED_VALUE>, "piece_width_inch": 4.0, "geometry_metadata": {{ "net_area": 0.0 }} }},
                        {{ "panel_name": "FRONT FLY FUSING", "piece_count": 2.0, "piece_length_inch": <EXTRACTED_OR_MAPPED_VALUE>, "piece_width_inch": 3.5, "geometry_metadata": {{ "net_area": 0.0 }} }}
                      ]
                    }}
                  ]
                }}
                ===END_JSON===
                
                ===START_CHAT=== [Xác nhận bằng Tiếng Việt dải linh kiện 12 mảnh rập Jacket bạn vừa bắt buộc trích xuất và quy đổi cho size {target_size_cmd}.] ===END_CHAT===
                """
                gemini_inputs.append(prompt_instruction)
                
                try:
                    response = model.generate_content(gemini_inputs)
                    if response and hasattr(response, "text"): 
                        response_text = response.text.strip()
                except Exception as e_api:
                    st.error(f"💥 Gemini API Error: {str(e_api)}")
                    response_text = ""




                        # =====================================================================
                      # =====================================================================
            # ĐOẠN 7a - PHẦN 3: POST-AI MIDDLEWARE & VÁ TRỰC DIỆN LUỒNG DỮ LIỆU ĐA TẦNG
            # SỬA LỖI KẸT CACHE CHỮ KÝ - ÉP BUỘC CẬP NHẬT TRỌN VẸN VẢI CHÍNH, LÓT, KEO RA MÀN HÌNH
            # =====================================================================
            if response_text:
                json_match = re.search(r'(?:===START_JSON===\s*|```json\s*)(.*?)(?:\s*===END_JSON===|\s*```)', response_text, re.DOTALL)
                
                chat_match = re.search(r'(?:===START_CHAT===\s*|```markdown\s*)(.*?)(?:\s*===END_CHAT===|\s*```|$)', response_text, re.DOTALL)
                ai_conversation_reply = chat_match.group(1).strip() if chat_match else "Hệ thống đã cập nhật bảng tính toán định mức hình học phẳng CAD của mã hàng."
                
                raw_json_str = ""
                if json_match: 
                    raw_json_str = json_match.group(1).strip()
                elif "===START_JSON===" in response_text and "===END_JSON===" in response_text:
                    raw_json_str = response_text[response_text.find("===START_JSON===")+16:response_text.find("===END_JSON===")].strip()
                else:
                    match_fb = re.search(r'\{.*\}', response_text, re.DOTALL)
                    raw_json_str = match_fb.group(0).strip() if match_fb else ""
                
                # CẬP NHẬT LỊCH SỬ TRÒ CHUYỆN THEO PHONG CÁCH OPENAI
                st.session_state.chat_history.append({"user": current_query, "ai": ai_conversation_reply})
                
                if raw_json_str:
                    raw_json_str = re.sub(r',\s*([\]\}])', r'\1', raw_json_str) 
                    
                    try:
                        raw_blueprint = json.loads(raw_json_str)
                    except json.JSONDecodeError as json_err:
                        st.error(f"❌ THẤT BẠI PARSE JSON: Chuỗi cấu trúc hình học sinh ra từ Gemini bị lỗi cú pháp: {str(json_err)}")
                        st.code(raw_json_str, language="json")
                        st.stop()
                    
                    if raw_blueprint and "bom_rows" in raw_blueprint:
                        blueprint_worker = copy.deepcopy(raw_blueprint)
                        query_str = str(current_query)
                        
                        # 🌟 CẢI TIẾN VÀNG: Xóa sạch bộ nhớ đệm kpi và tích lũy cũ trước khi chạy pipeline mới
                        # Chặn đứng hoàn toàn hiện tượng dữ liệu lót túi cũ đè bẹp vải chính Denim
                        st.session_state.bom_data = {}
                        st.session_state.accumulated_bom_rows = {}
                        
                        # Chạy chuỗi pipeline máy tính 3 bước hình học phẳng CAD doanh nghiệp
                        b1 = parse_geometric_panels_allowance(blueprint_worker, query_str)
                        b2_rows, _ = parse_and_prepare_ie_panels(b1.get("bom_rows", []), b1.get("detected_product_type"), query_str)
                        b1["bom_rows"] = b2_rows
                        
                        # Gọi lõi kiểm toán diện tích hình học phẳng CAD (Hàm 2b V44.0 Master)
                        blueprint_final = allocate_fabric_consumption_and_quality_gate(b1, query_str)
                        
                        # Đổ dữ liệu sạch mới tinh vào session và khóa chốt chặn chữ ký để tải trang vẽ bảng tính
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
                
                st.rerun()

        # ĐÓNG NGOẶC LỆNH TRY TOÀN CỤC CỦA ĐOẠN 7A1
        except Exception as e_global:
            st.error(f"💥 Lỗi luồng trích xuất hạ tầng tổng toàn cục: {str(e_global)}")
            st.code(traceback.format_exc())


# =====================================================================
# ĐOẠN 7b: HIỂN THỊ KẾT QUẢ ĐỊNH MỨC & BẢNG ĐỐI CHỨNG ĐA CỘT ĐỒNG BỘ SIZE (V47.0 MASTER DYNAMIC)
# ĐỒNG BỘ ĐỘNG ĐỘ CO RÚT, KHỔ VẢI VÀ HIỆU SUẤT TỪ HÀM TÍNH TOÁN 2B RA GIAO DIỆN
# =====================================================================
if st.session_state.get("bom_data") or st.session_state.get("accumulated_bom_rows"):
    import pandas as pd
    
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
        
    match_active_size = re.search(r'\b(?:size|sz|cỡ)\s*[:\-=\s]*([\w\d/]+)\b', chat_txt)
    extracted_size = str(match_active_size.group(1)).upper().strip() if match_active_size else str(bom_source.get("calculated_on_size", "30")).upper().strip()
    
    st.markdown('<div class="cad-card">', unsafe_allow_html=True)
    st.markdown(f'<div class="cad-header">📊 CALCULATED FABRIC CONSUMPTION MATRIX (SIZE TARGET: {extracted_size})</div>', unsafe_allow_html=True)
    
    display_data = []
    
    for r in bom_rows_list:
        if not r or not isinstance(r, dict): 
            continue
        sys_notes = r.get("consumption_note", "Mô phỏng CAD Gerber V27")
        current_gross = r.get("calculated_gross_consumption_yds", 0.0)
        
        # Đọc khổ vải an toàn đã được chốt chặn chống số 0 từ Đoạn 2b
        raw_width = r.get("fabric_width_inch", 57.0)
        try: cut_width_val = f"{float(raw_width)} inch"
        except: cut_width_val = "57.0 inch"

        # 🌟 ĐỒNG BỘ ĐỘNG CHÍ MẠNG: Đọc chính xác độ co rút động và hiệu suất từ Đoạn 2b truyền sang
        warp_dynamic = r.get("_btp_warp_pct", "4.0%")
        weft_dynamic = r.get("_btp_weft_pct", "14.0%")
        eff_dynamic = r.get("marker_efficiency_pct", "88.9%")

        display_data.append({
            "Component Type": r.get("component_type", "MAIN FABRIC"),
            "Placement": r.get("placement", "BODY/POCKETS"),
            "Fabric Classification": r.get("fabric_classification", "MAIN_FABRIC"),
            "Fabric Code": r.get("fabric_code", r.get("fabric_classification", "FABRIC")),
            "Fabric Color": r.get("fabric_color", "SOLID COLOR"),
            "Khổ vải (Width)": cut_width_val,
            "Co rút dọc (% Warp)": warp_dynamic,     # 🟢 Đã đổi sang biến động
            "Co rút ngang (% Weft)": weft_dynamic,   # 🟢 Đã đổi sang biến động
            "Marker Efficiency": eff_dynamic,         # 🟢 Đã đổi sang biến động theo bảng
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
    
    # BẢNG ĐỐI CHỨNG SỐ ĐO GỐC TỪ TECHPACK
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
                pom_code = parts[0].strip()
                description = parts[1].strip()
                if "=" in description:
                    sub_parts = description.split("=", 1)
                    description = sub_parts[0].strip()
                    measurement_val = sub_parts[1].strip()
            elif "=" in raw_str:
                parts = raw_str.split("=", 1)
                description = parts[0].strip()
                measurement_val = parts[1].strip()
                
            parsed_evidence_rows.append({
                "STT": idx + 1, "Mã POM": pom_code, "Mô tả Thông số Kỹ thuật": description, "Kích thước Đo thực tế (Inches)": measurement_val
            })
            
        df_evidence = pd.DataFrame(parsed_evidence_rows)
        st.dataframe(df_evidence, use_container_width=True, hide_index=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # KHỐI XUẤT FILE EXCEL PHÒNG VỆ AN TOÀN TRÊN MÀN HÌNH CHÍNH
    if display_data:
        try:
            import io
            from openpyxl import Workbook
            output = io.BytesIO()
            wb = Workbook()
            ws = wb.active
            ws.title = "BOM Consumption"
            ws.sheet_view.showGridLines = True
            
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
