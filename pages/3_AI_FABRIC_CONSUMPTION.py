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
def parse_geometric_panels_allowance(ai_blueprint: dict, user_chat: str) -> dict:
    """
    ĐOẠN 2: TRUNG TÂM TỔNG HỢP VÀ ĐÓNG GÓI SCHEMA TOÀN DIỆN (_btp_)
    Nhiệm vụ: Chạy vòng lặp dòng BOM, tích hợp Đoạn 1, quét sạch metadata và thống kê toàn cục.
    """
    if not ai_blueprint or not isinstance(ai_blueprint, dict):
        return {"detected_product_type": "PANT", "bom_rows": [], "_btp_global_summary": {}}

    # 1. Thu thập thông tin định dạng sản phẩm nền từ AI
    product_type = str(ai_blueprint.get("detected_product_type", "DEFAULT")).upper().strip()
    body_length = safe_float(ai_blueprint.get("extracted_body_length"), 28.0)
    chest_width = safe_float(ai_blueprint.get("extracted_chest_width"), 20.0)
    outseam_length = safe_float(ai_blueprint.get("extracted_outseam_length"), 14.5 if product_type == "JORT" else 40.0)
    hip_width = safe_float(ai_blueprint.get("extracted_hip_width"), 21.0)

    # Khởi tạo các thùng chứa dữ liệu thống kê toàn cục
    g_total_area = 0.0
    g_total_pieces = 0
    g_total_panels = 0
    g_largest_panel_area = 0.0
    g_largest_len = 0.0
    g_largest_wid = 0.0
    g_polygon_count = 0
    g_bbox_count = 0

    fabric_groups, lining_groups, fusing_groups, hardware_groups = set(), set(), set(), set()
    
    g_flags = {
        "need_stripe_match": False, "need_bias": False, "need_one_way": False, 
        "need_pair": False, "need_fold": False, "has_polygon": False, "has_bbox": False
    }

    all_rows = ai_blueprint.get("bom_rows", [])
    if not all_rows or not isinstance(all_rows, list): 
        all_rows = []
    
    parsed_rows = []

    # 2. Pipeline xử lý chi tiết từng dòng vật tư BOM
    for row in all_rows:
        if not row or not isinstance(row, dict): 
            continue
            
        c_type = str(row.get("component_type", "")).upper()
        placement = str(row.get("placement", "")).upper()
        f_class = str(row.get("fabric_classification", "")).upper()
        f_code = str(row.get("fabric_code", "")).upper()
        
        # Gom nhóm phân loại vật tư lên mức hệ thống toàn cục
        if "FABRIC" in f_class or "MAIN" in f_class: fabric_groups.add(f_code)
        elif "LINING" in f_class: lining_groups.add(f_code)
        elif "FUSING" in f_class or "INTERLINING" in f_class: fusing_groups.add(f_code)
        elif "HARDWARE" in f_class or "TRIM" in f_class: hardware_groups.add(f_code)

        # Sao chép động tất cả metadata dòng AI sang tiền tố hệ thống _btp_ (Row future-proof)
        for k, v in row.items():
            if k != "panels_catalog":
                row[f"_btp_{k}"] = v

        row_summary = {
            "total_panel": 0, "total_piece": 0, "area": 0.0, 
            "largest_piece_area": 0.0, "longest_piece": 0.0, "widest_piece": 0.0,
            "polygon_exist": False, "bbox_exist": False
        }

        # Bypass bảo vệ đối với phụ liệu cứng (Hardware/Trims)
        if any(k in c_type or k in placement or k in f_class or k in f_code for k in EXCLUDE_HARDWARE_KEYS):
            row["calculated_gross_consumption_yds"] = 0.0
            row["_btp_summary"] = row_summary
            row["_btp_total_panel_area"] = 0.0
            row["status"] = "PASS"
            parsed_rows.append(row)
            continue

        panels = row.get("panels_catalog", [])
        panel_debug_logs = []
        parsed_panels_catalog = []

        if panels and isinstance(panels, list):
            for panel in panels:
                if not panel or not isinstance(panel, dict): 
                    continue
                
                # Gọi ĐOẠN 1: Xử lý đóng gói hình học đa giác & dung sai của Panel
                btp_panel = process_single_panel_geometry_and_flags(
                    panel, product_type, body_length, chest_width, outseam_length, hip_width
                )
                
                # Đếm bộ đếm thống kê
                g_total_panels += 1
                row_summary["total_panel"] += 1
                p_count = safe_float(panel.get("piece_count"), 1.0)
                g_total_pieces += int(p_count)
                row_summary["total_piece"] += int(p_count)

                # Ghi nhận trạng thái hình học để thống kê
                if btp_panel["geometry_calculated_by"] == "POLYGON":
                    g_polygon_count += 1
                    row_summary["polygon_exist"] = True
                    g_flags["has_polygon"] = True
                else:
                    g_bbox_count += 1
                    row_summary["bbox_exist"] = True
                    g_flags["has_bbox"] = True

                # Đánh giá cực đại kích thước hình học bao khung
                p_len, p_wid = btp_panel["panel_length"], btp_panel["panel_width"]
                if p_len > row_summary["longest_piece"]: row_summary["longest_piece"] = p_len
                if p_wid > row_summary["widest_piece"]: row_summary["widest_piece"] = p_wid
                if p_len > g_largest_len: g_largest_len = p_len
                if p_wid > g_largest_wid: g_largest_wid = p_wid

                # Tính tổng tích lũy diện tích sau dung sai
                p_area = btp_panel["panel_area"]
                row_summary["area"] += p_area
                g_total_area += p_area
                
                if p_area > row_summary["largest_piece_area"]: row_summary["largest_piece_area"] = p_area
                if p_area > g_largest_panel_area: g_largest_panel_area = p_area

                # Đẩy trạng thái cờ may mặc từ panel chi tiết lên cờ Toàn Cục
                if btp_panel["matching"]: g_flags["need_stripe_match"] = True
                if btp_panel["bias"]: g_flags["need_bias"] = True
                if btp_panel["mirror"] or btp_panel["pair"]: g_flags["need_pair"] = True
                if btp_panel["fold"]: g_flags["need_fold"] = True

                # Tiêm schema chuẩn hóa hệ thống vào cấu trúc panel
                panel["_btp_panel"] = btp_panel
                parsed_panels_catalog.append(panel)
                panel_debug_logs.append(f"[{panel.get('panel_name','')}]: Area={p_area:.1f}")

        # Đồng bộ dữ liệu thống kê cấp Dòng BOM vào Schema _btp_ cho Engine V25 đọc trực tiếp
        row["panels_catalog"] = parsed_panels_catalog
        row["_btp_total_panel_area"] = round(row_summary["area"], 4)
        row["_btp_max_piece_length"] = round(row_summary["longest_piece"], 2)
        row["_btp_max_piece_width"] = round(row_summary["widest_piece"], 2)
        row["_btp_total_piece_count"] = int(row_summary["total_piece"])
        
        row["_btp_summary"] = {
            "total_panel": row_summary["total_panel"],
            "total_piece": row_summary["total_piece"],
            "area": round(row_summary["area"], 4),
            "largest_piece": round(row_summary["largest_piece_area"], 4),
            "longest_piece": round(row_summary["longest_piece"], 2),
            "widest_piece": round(row_summary["widest_piece"], 2),
            "polygon_exist": row_summary["polygon_exist"],
            "bbox_exist": row_summary["bbox_exist"]
        }
        
        row["_computed_net_area_sq_in"] = row["_btp_total_panel_area"]
        row["reason_or_logs"] = " | ".join(panel_debug_logs) if panel_debug_logs else "No panels found"
        row["status"] = "SUCCESS"
        parsed_rows.append(row)

    ai_blueprint["bom_rows"] = parsed_rows

    # 3. Thu hoạch Metadata AI mức toàn cục (Bắt bẫy hướng tuyết vải nếu có)
    fabric_direction_raw = str(ai_blueprint.get("fabric_direction", "")).upper()
    if "ONE" in fabric_direction_raw or "NAP" in fabric_direction_raw or ai_blueprint.get("nap") is True:
        g_flags["need_one_way"] = True

    # Khởi tạo Schema _btp_global_summary
    g_summary = {
        "total_area": round(g_total_area, 4),
        "total_piece": int(g_total_pieces),
        "total_panels": int(g_total_panels),
        "largest_panel": round(g_largest_panel_area, 4),
        "largest_length": round(g_largest_len, 2),
        "largest_width": round(g_largest_wid, 2),
        "average_piece_area": round(g_total_area / max(1, g_total_pieces), 4),
        "fabric_groups": list(fabric_groups),
        "lining_groups": list(lining_groups),
        "fusing_groups": list(fusing_groups),
        "hardware_groups": list(hardware_groups),
        "total_polygon": int(g_polygon_count),
        "total_bbox": int(g_bbox_count),
        "has_polygon": g_flags["has_polygon"],
        "has_bbox": g_flags["has_bbox"],
        "need_stripe_match": g_flags["need_stripe_match"] or ai_blueprint.get("matching_required") is True or ai_blueprint.get("stripe_match") is True,
        "need_bias": g_flags["need_bias"],
        "need_one_way": g_flags["need_one_way"],
        "need_pair": g_flags["need_pair"],
        "need_fold": g_flags["need_fold"],
        "system_pipeline_version": "V17.0.0-DECOUPLED-AGGREGATOR"
    }

    # BỘ THU GOM METADATA AI TOÀN CỤC CHỦ ĐỘNG (_btp_ai_metadata) - 100% TRƯỜNG DỮ LIỆU ĐƯỢC GIỮ LẠI
    ai_metadata_schema = {}
    for key, value in ai_blueprint.items():
        if key.startswith("_btp_") or key == "bom_rows":
            continue
        ai_metadata_schema[key] = value

    ai_blueprint["_btp_ai_metadata"] = ai_metadata_schema
    ai_blueprint["_btp_global_summary"] = g_summary

    return ai_blueprint



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
# ĐOẠN 2b1: CHAT PARSER LAYER - BẢN ULTRA-SAFE CHỐNG LỖI PASTE (V17.1.0)
# =====================================================================
def parse_and_prepare_ie_panels(all_rows: list, product_type: str, user_prompt: str = "") -> tuple:
    """Hàm nén gọn tối đa, triệt tiêu Regex dài dòng để chống tuyệt đối lỗi nuốt ký tự."""
    chat = str(user_prompt or "").lower().strip()
    
    # 1. Bóc tách thông số bằng tìm kiếm chuỗi thô cơ bản (Không dùng Regex)
    user_eff = None
    if "eff" in chat or "sơ đồ" in chat or "hiệu suất" in chat:
        user_eff = 0.85 # Gán giá trị an toàn mặc định nếu phát hiện ý định chỉ định sơ đồ
        
    user_shrinkage = 0.0
    user_width_override = 0.0

    user_chat_flags = {
        "force_stripe_match": "sọc" in chat or "stripe" in chat or "caro" in chat,
        "force_bias_cut": "xéo" in chat or "bias" in chat,
        "force_one_way": "một chiều" in chat or "one way" in chat or "tuyết" in chat
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
        p_meta = p.get("panel_metadata", {})
        g_meta = p.get("geometry_metadata", {})
        p_count = float(p.get("piece_count", 1.0))
        total_pieces += int(p_count)
        
        # 1. Trích xuất kích thước biên khung bao của chi tiết
        p_len = float(g_meta.get("panel_length", p.get("piece_length_inch", 0.0)))
        p_wid = float(g_meta.get("panel_width", p.get("piece_width_inch", 0.0)))
        
        if p_len > max_p_len: max_p_len = p_len
        if p_wid > max_p_wid: max_p_wid = p_wid

        # 2. Phân loại cấu trúc sơ đồ chi tiết rập chính / phụ
        p_cat = str(p_meta.get("panel_category", p.get("panel_category", "MAJOR"))).upper()
        if "MAJOR" in p_cat or "BODY" in p_cat:
            major_count += int(p_count)
        else:
            minor_count += int(p_count)

        # 3. Quét cờ ràng buộc cơ học rập (Khóa bậc tự do)
        if p_meta.get("cut_on_fold", g_meta.get("cut_on_fold", False)):
            has_fold = True
        if p_meta.get("pair_required", p_meta.get("is_pair", False)):
            has_pair = True

        # 4. Tính toán chỉ số Compactness (Độ khít đa giác phẳng) từ AI V49
        p_area = float(g_meta.get("polygon_area", g_meta.get("net_area", p_len * p_wid * 0.6)))
        p_peri = float(g_meta.get("polygon_perimeter", 0.0))
        total_net_area += p_area * p_count
        
        if p_peri > 0:
            # Compactness = 4 * pi * Area / (Perimeter^2)
            compactness = (4.0 * math.pi * p_area) / (p_peri ** 2)
            total_compactness += compactness * p_count
        else:
            total_compactness += 0.65 * p_count  # Hệ số an toàn nếu khuyết thiếu hình học đa giác

        # 5. Phân tích diện tích khối hộp bao chữ nhật (Bounding Box)
        bbox = g_meta.get("bounding_box", [])
        if bbox and len(bbox) == 4:
            bbox_w = abs(float(bbox[2]) - float(bbox[0]))
            bbox_h = abs(float(bbox[3]) - float(bbox[1]))
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
        chat_shrink_warp = 1.0 + (float(match_warp.group(1)) / 100.0)

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

        fc = row.get("fabric_constraints", {})
        row_sum = row.get("_btp_summary", {})
        panels = row.get("panels_catalog", [])

        # Kiểm tra diện tích phẳng phẳng dồn khả dụng
        row_net_area = float(row.get("_btp_total_panel_area", row_sum.get("area", 0.0)))
        if row_net_area <= 0.0 and panels:
            row_net_area = sum(float(p.get("piece_length_inch", 0)) * float(p.get("piece_width_inch", 0)) * float(p.get("piece_count", 1)) * 0.6 for p in panels)

        if row_net_area <= 0.0:
            row["status"] = "ERROR"
            row["calculated_gross_consumption_yds"] = 0.0
            row["consumption_note"] = "Bỏ qua: Khuyết thiếu diện tích hình học rập."
            continue

        # Xác định khổ vải hữu dụng sau trừ biên cắt (Cuttable Width)
        cutable_w = float(row.get("fabric_width_inch", fc.get("fabric_width_inch", 58.0)))
        if cutable_w <= 0: 
            cutable_w = 58.0

        is_fusing = row.get("_is_fusing", "FUSING" in f_class or "KEO" in comp_type)
        is_lining = row.get("_is_lining", "LINING" in f_class or "LÓT" in comp_type)

        # 🚀 TÍNH TOÁN ĐOẠN A: Gọi Engine phân tích topo đa giác chi tiết
        topo = analyze_panel_geometry_and_cad_constraints(panels, cutable_w)

        # =====================================================================
        # 📊 THUẬT TOÁN ĐIỀU CHỈNH HIỆU SUẤT MÔ PHỎNG SƠ ĐỒ (CAD LOGIC MATRIX)
        # =====================================================================
        # Khống chế hiệu suất nền theo tỷ lệ chiếm khổ biên cực đại (Width Utilization)
        w_util = topo["width_utilization_ratio"]
        if w_util > 0.90:   
            base_eff = 0.77  # Rập quá to chắn ngang khổ vải: không còn không gian lồng rập nhỏ
        elif w_util > 0.70: 
            base_eff = 0.81
        else:               
            base_eff = 0.85  # Khổ rập vừa vặn lý tưởng cho bài toán xếp hình phẳng 2D

        # Thưởng hiệu suất lồng rập (Nesting Bonus): Càng nhiều chi tiết nhỏ (minor) càng dễ nhét khoảng trống
        total_p_pieces = float(topo["total_pieces"])
        minor_ratio = float(topo["minor_pieces_count"]) / max(1.0, total_p_pieces)
        nesting_bonus = min(0.045, minor_ratio * 0.08)

        # Phạt hiệu suất dựa trên hình học rập lồi lõm (Compactness) và hộp bao hình (BBox)
        shape_penalty = max(0.0, (0.85 - topo["avg_compactness"]) * 0.1) + max(0.0, (0.85 - topo["bbox_packing_ratio"]) * 0.08)

        # Phạt ràng buộc dệt may từ Fabric Constraints của AI V49
        is_one_way = fc.get("one_way", False) or str(fc.get("fabric_grain_rule")).upper() == "ONE_WAY"
        is_stripe = fc.get("nap_sensitive", False) or float(fc.get("stripe_repeat_inch", 0.0)) > 0 or float(fc.get("plaid_repeat_inch", 0.0)) > 0
        
        fabric_penalty = 0.0
        if is_one_way:                    fabric_penalty += 0.035  # Khóa chiều sợi vải
        if is_stripe:                     fabric_penalty += 0.060  # Hao hụt khoảng cách đối kẻ sọc
        if topo["has_fold_penalty"]:      fabric_penalty += 0.025  # Khóa chi tiết sát biên gập (`cut_on_fold`)
        if topo["has_pair_constraint"]:   fabric_penalty += 0.015  # Ép rập đi theo cặp đối xứng (`pair_required`)

        # Thiết lập hiệu suất mô phỏng cuối cùng (Simulated Efficiency)
        simulated_eff = base_eff - shape_penalty - fabric_penalty + nesting_bonus
        
        if is_fusing:    simulated_eff = max(0.82, min(0.92, simulated_eff + 0.05))
        elif is_lining:  simulated_eff = max(0.80, min(0.90, simulated_eff + 0.03))
        else:            simulated_eff = max(0.62, min(0.93, simulated_eff))

        # =====================================================================
        # 📐 THUẬT TOÁN TOÁN HỌC TÍNH CHIỀU DÀI SƠ ĐỒ VÀ YARDS (GERBER CAD CONVERSION)
        # =====================================================================
        # Chiều dài sơ đồ mô phỏng CAD thực tế = Diện tích rập phẳng / (Khổ hữu dụng * Hiệu suất mô phỏng)
        simulated_marker_length_inch = row_net_area / (cutable_w * simulated_eff)
        
        # Điểm chặn vật lý biên cứng: Chiều dài sơ đồ không được nhỏ hơn chiều dài chi tiết dài nhất
        if simulated_marker_length_inch < topo["max_p_len"]:
            simulated_marker_length_inch = topo["max_p_len"] * 1.04

        # Áp dụng tỷ lệ co rút dọc (Shrinkage)
        shrink_warp_pct = float(fc.get("shrinkage_warp_pct", 0.0))
        shrink_factor = chat_shrink_warp if chat_shrink_warp is not None else (1.0 + (shrink_warp_pct / 100.0) if shrink_warp_pct > 0 else 1.03)

        # Xác định Lay Planning Factor (Tỷ lệ hao hụt đầu khúc/đầu bàn cắt của phân xưởng)
        wastage_factor = 1.04  # Tiêu chuẩn vải dệt thoi (Woven)
        if "KNIT" in str(fc.get("fabric_grain_rule")).upper() or any(x in str(row).upper() for x in ["THUN", "KNIT"]):
            wastage_factor = 1.065 # Vải thun dệt kim co kéo đầu bàn 6.5%
        if is_stripe:
            wastage_factor += 0.025 # Hao hụt đầu bàn căn kẻ hoa văn sọc caro

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
# ĐOẠN 7a1: INTERFACE WORKSPACE & HIGH-RES JPEG IMAGE PIPELINE (V29.0 CHUẨN CONTAINER ID)
# =====================================================================
st.markdown('<br><div class="cad-card"><div class="cad-header">💬 CHATGPT IE COLLABORATION WORKSPACE</div>', unsafe_allow_html=True)

# Khởi tạo kho lưu trữ trạng thái hệ thống phòng vệ tránh lỗi mất Session State khi tương tác
if "chat_history" not in st.session_state: st.session_state.chat_history = []
if "pdf_page_images_list" not in st.session_state: st.session_state.pdf_page_images_list = None
if "accumulated_bom_rows" not in st.session_state: st.session_state.accumulated_bom_rows = {}
if "bom_data" not in st.session_state: st.session_state.bom_data = {}

# Xuất dòng tin nhắn lịch sử trò chuyện đồng bộ trực quan lên màn hình
if st.session_state.chat_history:
    for msg in st.session_state.chat_history:
        st.chat_message("user").write(msg["user"])
        st.chat_message("assistant").write(msg["ai"])

# 🌟 FIX CHIẾN LƯỢC HẠ TẦNG ID: Tạo một vùng chứa tĩnh độc lập cô lập ô chat input
chat_input_container = st.container()
with chat_input_container:
    safe_user_prompt = st.chat_input("Gõ câu lệnh điều chỉnh thông số tại đây...", key="ie_workspace_static_chat_input_key")

st.markdown('</div>', unsafe_allow_html=True)

# Kích hoạt luồng trích xuất dữ liệu khi có tệp tài liệu và lệnh từ ô chat
if st.session_state.pdf_bytes is not None and safe_user_prompt:
    current_query = str(safe_user_prompt).strip()
    
    with st.spinner("🧠 AI Platform đang trích xuất dải ảnh kỹ thuật JPEG và xử lý rập phẳng..."):
        try:
            import google.generativeai as genai
            import json, copy, traceback, re
            import fitz 
            
            doc_recovery = fitz.open(stream=st.session_state.pdf_bytes, filetype="pdf")
            total_pages = len(doc_recovery)
            
            # Ép chuyển đổi sang định dạng hình ảnh JPEG (RGB) để triệt tiêu lỗi byte ảnh nhiễu
            image_payloads = []
            target_dpi = 180 if total_pages <= 5 else 130
            max_scan_pages = min(total_pages, 16)
            
            for page_num in range(max_scan_pages):
                page = doc_recovery.load_page(page_num)
                pix = page.get_pixmap(dpi=target_dpi, colorspace=fitz.csRGB)
                page_img_bytes = pix.tobytes("jpeg")
                
                image_payloads.append({"mime_type": "image/jpeg", "data": page_img_bytes})
            
            gemini_inputs = copy.deepcopy(image_payloads)
# =====================================================================
# ĐOẠN 7a2.1: AI COGNITIVE EXTRACTOR - CAD INDUSTRIAL STANDARDIZATION (V49.0 ULTIMATE)
# =====================================================================
            if "GEMINI_API_KEY" in st.secrets: 
                genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
                
            model = genai.GenerativeModel("gemini-2.5-flash", generation_config={"temperature": 0.0})
            chat_lower = current_query.lower()
            
            # Bẫy kiểm tra NoneType an toàn phòng vệ hệ thống ban đầu
            bom_state_data = st.session_state.get("bom_data")
            doc_product_type_raw = str(bom_state_data.get("detected_product_type", "DEFAULT")).upper() if isinstance(bom_state_data, dict) else "DEFAULT"
            
            inferred_is_upper = any(x in chat_lower or x in doc_product_type_raw for x in ["DRESS", "VÁY", "ĐẦM", "SHIRT", "SƠ MI", "TSHIRT", "JACKET", "HOODIE", "TOP", "ÁO"])
            
            # Bộ bóc tách thông minh bắt trọn dải Size chữ lẫn Size số từ ô chat
            match_size = re.search(r'\b(?:size|sz|cỡ)\s*[:\-=\s]*([\w\d/]+)\b', chat_lower)
            target_size_cmd = str(match_size.group(1)).upper().strip() if match_size else ("M" if inferred_is_upper else "30")
            
            # Ép kiểu an toàn nghiêm ngặt cho khổ vải đầu vào từ ô chat, tránh văng lỗi float()
            match_w = re.search(r'(?:khổ|kho|width|vải chính khổ)\s*([\d\.]+)', chat_lower)
            try:
                active_width = float(match_w.group(1)) if match_w else 56.0
            except (ValueError, TypeError):
                active_width = 56.0

            if len(st.session_state.chat_history) > 30:
                st.session_state.chat_history = st.session_state.chat_history[-30:]

            # 🌟 PROMPT REVOLUTION V49.0: TWO-TIER DATA SYSTEM & CAD MARKER CONSTRAINT INJECTION
            prompt_instruction = f"""
            You are an expert apparel Industrial Engineering (IE) OCR and CAD Optimization system. Scan all provided techpack pages to analyze both the Sizing Charts and the Bill of Materials (BOM) / Material Fabric Specification tables.
            
            STRICT REAL-WORLD PRODUCTION RULES (TARGET SIZE: {target_size_cmd}):
            1. Target size is '{target_size_cmd}'. Convert fractional measurements to clean decimals.
            2. 🌟 ABSOLUTE BOM FIDELITY RULE (NO FABRIC FABRICATION):
               - Look closely at the fabric specifications and material descriptions in the document.
               - DO NOT invent, assume, or output any material rows if they are NOT explicitly listed in the techpack's BOM tables.
            3. 🌟 PROACTIVE DIMENSION INFERENCE RULE:
               - If panel dimensions are not explicitly given but can be logically inferred or estimated from the sizing chart (e.g., Body Length for panel length, Bust/Chest or Hip for panel width), you MUST estimate them intelligently.
               - NEVER default to 0.0 or 0 for length and width unless it is absolutely impossible to determine or guess. Defaulting to 0.0 will crash the marker engine and yield false fabric consumption.
            
            4. 🌟 STRICT CRITICAL COMPLIANCE VALIDATION MANDATE:
               Before generating the final JSON output, perform an internal validation sweep to ensure:
               - Every single numeric field is a valid JSON number (integer or float). Never output null, "", "N/A", or "unknown".
               - Every boolean field must strictly be true or false. Never null or omitted.
               - All arrays and objects must exist. No missing schema keys are allowed.
            
            Output strictly in the specified TWO-TIER CAD-standard JSON structure below based on REAL and inferred data:
            ===START_JSON===
            {{
              "status": "PASS",
              "spec_sheet_found": true,
              "spec_page": 13,
              "detected_product_type": "DRESS",
              "style_code": "EV-1436B",
              "calculated_on_size": "{target_size_cmd}",
              "matched_measurements": [
                 "A-11: FRONT LENGTH = 36.000 inch",
                 "E-01: BUST/CHEST = 16.500 inch"
              ],
              "_btp_global_summary": {{
                "total_bom_rows": 1,
                "total_panels": 2,
                "total_pieces": 2,
                "largest_piece_length": 36.0,
                "largest_piece_width": 16.5,
                "polygon_count": 0,
                "bbox_count": 2,
                "has_polygon": false,
                "has_bbox": true,
                "need_stripe_match": false,
                "need_bias": false,
                "need_one_way": true,
                "need_fold": false
              }},
              "bom_rows": [
                {{
                  "component_type": "MAIN FABRIC", 
                  "placement": "BODY", 
                  "fabric_classification": "MAIN_FABRIC",
                  "fabric_code": "CASUAL_TWILL", 
                  "fabric_color": "SOLID BLACK", 
                  "fabric_width_inch": {active_width},
                  "_btp_summary": {{
                     "panel_count": 2,
                     "piece_count": 2,
                     "largest_piece_area": 594.0,
                     "max_piece_length": 36.0,
                     "max_piece_width": 16.5
                  }},
                  "fabric_constraints": {{
                     "fabric_grain_rule": "ONE_WAY",
                     "marker_type": "OPEN_WIDTH",
                     "shrinkage_warp_pct": 3.0,
                     "shrinkage_weft_pct": 2.0,
                     "nap_direction": "DOWN",
                     "fabric_face": "FACE_TO_FACE",
                     "fabric_splice_allowed": true,
                     "face_up": true,
                     "one_way": true,
                     "two_way": false,
                     "mirror_allowed": true,
                     "pair_required": true,
                     "stripe_repeat_inch": 0.0,
                     "plaid_repeat_inch": 0.0,
                     "nap_sensitive": true
                  }},
                  "panels_catalog": [
                    {{ 
                      "panel_name": "FRONT_BODY", 
                      "panel_type": "BODY",
                      "piece_count": 1.0, 
                      "piece_length_inch": 36.0, 
                      "piece_width_inch": 16.5,
                      "geometry_metadata": {{
                         "polygon_points": [],
                         "coordinate_scale": 1.0,
                         "bounding_box": [0.0, 0.0, 16.5, 36.0],
                         "polygon_area": 0.0,
                         "polygon_perimeter": 0.0,
                         "net_area": 594.0,
                         "gross_area": 594.0,
                         "include_seam": false,
                         "include_hem": false,
                         "seam_allowance": true,
                         "seam_length_map": {{}},
                         "hem": 1.5
                      }},
                      "panel_metadata": {{
                         "grainline": "WARP",
                         "stripe_match": false,
                         "bias": false,
                         "bias_degree": 0.0,
                         "mirror_cut": false,
                         "cut_on_fold": false,
                         "panel_rotation": 0.0,
                         "is_major_panel": true,
                         "is_pair": false,
                         "left_right": "NONE",
                         "can_rotate": true,
                         "rotation_limit": 180.0,
                         "nest_group": "A",
                         "symmetry_axis": "Y",
                         "match_group": "NONE",
                         "panel_category": "MAJOR",
                         "nest_priority": 1
                      }}
                    }}
                  ]
                }}
              ]
            }}
            ===END_JSON===
            
            Populated data must reflect the specific techpack analyzed. Verify that NO string descriptions or nulls leak into numerical fields. Execute the validation sweep before delivering the text block.
            
            ===START_CHAT===
            [Confirm in Vietnamese which pages you scanned and summarize the exact clean verified dimensions and materials found for size {target_size_cmd}.]
            ===END_CHAT===
            """
            
            gemini_inputs.append(prompt_instruction)
            response = model.generate_content(gemini_inputs)





            # =====================================================================
            # ĐOẠN 7a2.2: PIPELINE HỢP NHẤT HÌNH HỌC CAD VÀ TÍNH ĐỊNH MỨC (V17.0.7 FIXED)
            # =====================================================================
            ai_chat_response = "Hệ thống đang xử lý dữ liệu..."
            response_text = ""
            
            if response:
                try:
                    response_text = response.text.strip()
                except Exception as e_text:
                    response_text = ""
                    st.error(f"⚠️ Không thể đọc thuộc tính text phản hồi từ AI: {str(e_text)}")
            
            if response_text:
                json_match = re.search(r'(?:===START_JSON===\s*|```json\s*)(.*?)(?:\s*===END_JSON===|\s*```)', response_text, re.DOTALL)
                chat_match = re.search(r'(?:===START_CHAT===\s*|```markdown\s*|(?:\n|^)\s*\*\s*)(.*?)(?:\s*===END_CHAT===|\s*```|$)', response_text, re.DOTALL)
                raw_json_str = json_match.group(1).strip() if json_match else ""
                
                if raw_json_str:
                    try:
                        raw_blueprint = json.loads(raw_json_str)
                        if "bom_rows" in raw_blueprint:
                            # Thực thi chuỗi 3 bước xử lý hình học & định mức Gerber CAD phẳng
                            b1 = parse_geometric_panels_allowance(raw_blueprint, current_query)
                            b2_rows, _ = parse_and_prepare_ie_panels(b1.get("bom_rows", []), b1.get("detected_product_type"), current_query)
                            b1["bom_rows"] = b2_rows
                            blueprint_final = allocate_fabric_consumption_and_quality_gate(b1, current_query)
                            
                            st.session_state.bom_data = blueprint_final
                            st.session_state.accumulated_bom_rows = blueprint_final.get("bom_rows", [])
                            ai_chat_response = chat_match.group(1).strip() if chat_match else "✅ Gerber CAD Simulation thành công!"
                            st.session_state.chat_history.append({"user": current_query, "ai": ai_chat_response})
                            st.rerun()
                    except Exception as e_pipeline:
                        st.error(f"💥 Lỗi luồng thực thi toán học định mức: {str(e_pipeline)}")
                else:
                    st.warning("⚠️ Không tìm thấy khối START_JSON hợp lệ từ Gemini.")
            else:
                st.warning("⚠️ Gemini phản hồi nội dung trống.")



                







# =====================================================================
# ĐOẠN 7b: HIỂN THỊ KẾT QUẢ ĐỊNH MỨC & BẢNG ĐỐI CHỨNG ĐA CỘT ĐỒNG BỘ SIZE (V46.0 APPROVED)
# =====================================================================
if st.session_state.get("bom_data") and "bom_rows" in st.session_state.bom_data and st.session_state.bom_data["bom_rows"]:
    
    # 🌟 NÂNG CẤP ĐỒNG BỘ: Giải phóng cache kẹt số 30 thô
    chat_txt = ""
    if 'safe_user_prompt' in locals() and safe_user_prompt:
        chat_txt = str(safe_user_prompt).lower()
    elif st.session_state.chat_history:
        chat_txt = str(st.session_state.chat_history[-1]["user"]).lower()
        
    # Bóc tách trực tiếp size người dùng gõ ở ô chat để in lên tiêu đề hiển thị
    match_active_size = re.search(r'\b(?:size|sz|cỡ)\s*[:\-=\s]*([\w\d/]+)\b', chat_txt)
    if match_active_size:
        extracted_size = str(match_active_size.group(1)).upper().strip()
    else:
        # Nếu không gõ size, đọc trực tiếp số size thật do AI phản hồi trong database JSON
        extracted_size = str(st.session_state.bom_data.get("calculated_on_size", "M")).upper().strip()
    
    st.markdown('<div class="cad-card">', unsafe_allow_html=True)
    st.markdown(f'<div class="cad-header">📊 CALCULATED FABRIC CONSUMPTION MATRIX (SIZE TARGET: {extracted_size})</div>', unsafe_allow_html=True)
    
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
            cut_width_val = f"{float(match_w.group(1))} inch" if match_w else "56.0 inch"
        
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
            "Fabric Code": r.get("fabric_code", "CASUAL_FABRIC"),
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
    
    # TRỰC QUAN HÓA BẢNG ĐỐI CHỨNG ĐA CỘT PHÂN TÁCH SIÊU ĐẸP
    raw_evidence_list = st.session_state.bom_data.get("matched_measurements", [])
    if raw_evidence_list:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<div class="cad-card">', unsafe_allow_html=True)
        st.markdown(f'<div class="cad-header" style="background-color: #2C3E50;">🔍 BẰNG CHỨNG SỐ ĐO GỐC TỪ TECHPACK (SIZE: {extracted_size})</div>', unsafe_allow_html=True)
        
        parsed_evidence_rows = []
        for idx, item in enumerate(raw_evidence_list):
            raw_str = str(item).strip()
            pom_code = "POM"
            description = raw_str
            measurement_val = "-"
            
            if ":" in raw_str:
                parts = raw_str.split(":", 1)
                pom_code = parts[0].strip()
                remainder = parts[1].strip()
                if "=" in remainder:
                    sub_parts = remainder.split("=", 1)
                    description = sub_parts[0].strip()
                    measurement_val = sub_parts[1].strip()
                else:
                    description = remainder
            elif "=" in raw_str:
                parts = raw_str.split("=", 1)
                description = parts[0].strip()
                measurement_val = parts[1].strip()
                
            parsed_evidence_rows.append({
                "STT": idx + 1,
                "Mã POM": pom_code,
                "Mô tả Thông số Kỹ thuật": description,
                "Kích thước Đo thực tế (Inches)": measurement_val
            })
            
        df_evidence = pd.DataFrame(parsed_evidence_rows)
        st.dataframe(df_evidence, use_container_width=True, hide_index=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # KHỐI LOGIC XUẤT EXCEL CHUẨN ĐƯỢC VÁ SẠCH LỖI
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
