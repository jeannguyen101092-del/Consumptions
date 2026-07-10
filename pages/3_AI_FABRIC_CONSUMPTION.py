import streamlit as st
import re
import json
import copy

from typing import List, Optional
from pydantic import BaseModel, Field

class SpecMetaSchema(BaseModel):
    warp_shrink: float = Field(default=3.0, description="Độ co rút dọc (%) trích xuất từ Techpack")
    weft_shrink: float = Field(default=3.0, description="Độ co rút ngang (%) trích xuất từ Techpack")
    gather_ratio: float = Field(default=1.0, description="Tỷ lệ nhún vải (Ví dụ: 1.45 nếu có nhún sườn)")
    has_stripe: bool = Field(default=False, description="True nếu vải có vân sọc, kẻ caro, plaid")
    fabric_group: str = Field(default="WOVEN", description="Nhóm vải chính: DENIM, WOVEN, hoặc KNIT")

class BomRowSchema(BaseModel):
    component_name: str = Field(description="Tên chi tiết rập (Ví dụ: FRONT PANEL, POCKET...)")
    material_class: str = Field(description="Phân loại nguyên liệu: FABRIC, LINING, FUSING, ELASTIC, THREAD")
    piece_count: int = Field(default=1, description="Tổng số lượng chi tiết thực tế khi sản xuất")
    polygon_net_area: Optional[float] = Field(default=0.0, description="Diện tích đa giác từ Gerber/Lectra nếu có")
    polygon_area_mode: Optional[str] = Field(default="PER_PIECE", description="TOTAL hoặc PER_PIECE")
    polygon_unit: Optional[str] = Field(default="IN2", description="CM2 hoặc IN2")
    bounding_box_length: Optional[float] = Field(default=0.0, description="Chiều dài hộp bao khối rập thô")
    bounding_box_width: Optional[float] = Field(default=0.0, description="Chiều rộng hộp bao khối rập thô")
    fabric_width_inch: Optional[float] = Field(default=None, description="Khổ rộng thực tế của vật tư từ BOM")

class AgentOutputSchema(BaseModel):
    spec_meta: SpecMetaSchema
    bom_rows: List[BomRowSchema]
import streamlit as st

# Danh sách từ khóa tĩnh để tự động loại trừ phụ liệu đếm chiếc khỏi vải cuộn
EXCLUDE_HARDWARE_KEYS = (
    "CHỈ", "THREAD", "ZIPPER", "DÂY KÉO", "BUTTON", "NÚT", "SHANK", "RIVET", 
    "LABEL", "MÁC", "TAG", "EYELETS", "SNAP", "VELCRO", "HOOK", "LOOP", 
    "STOPPER", "TOGGLE", "BUCKLE", "GROMMET", "STICKER", "CARE WHITE", 
    "HEAT STAMP", "HANGTAG", "POLYBAG", "BAO BÌ"
)

def convert_to_sq_inches(area: float, unit: str) -> float:
    """Bộ chuyển đổi đơn vị đo lường vạn năng bám sát hệ thống Gerber/Lectra"""
    u = str(unit).upper().strip()
    if u in ["CM2", "CMSQ", "SQUARE_CM"]:
        return area / 6.4516
    if u in ["MM2", "MMSQ", "SQUARE_MM"]:
        return area / 645.16
    return area

def compute_fabric_engine(row: dict, product_type: str, spec_meta: dict) -> tuple:
    """
    Industrial Consumption CAM Core Engine v54.6 - FIXED DENIM FORMULA.
    🌟 SỬA TRIỆT ĐỂ: Sửa lại công thức Gerber CAD gốc, đưa định mức về đúng thực tế sản xuất.
    Khóa cứng hiệu suất sơ đồ hàng Jeans tối đa 87% - 88%.
    """
    current_mat_class = str(row.get("material_class", "FABRIC")).upper().strip()
    current_comp_name = str(row.get("component_name", "")).upper().strip()
    
    # Ma trận hệ số diện tích rập tịnh phẳng hình học CAD cho hàng Jeans Denim
    PRODUCT_NET_AREA_MATRIX = {
        "JEANS": {"MAIN_FABRIC": 0.82, "LINING": 0.78, "FUSING": 0.15, "DEFAULT": 0.80},
        "DEFAULT": {"MAIN_FABRIC": 0.80, "LINING": 0.75, "FUSING": 0.20, "DEFAULT": 0.80}
    }
    active_product = "JEANS"

    is_main_fabric = False
    is_pocket_fabric = False
    
    if current_mat_class in ["MAIN_FABRIC", "FABRIC", "SELF", "SHELL", "OUTER"] or "MAIN" in current_mat_class or "BODY" in current_comp_name:
        if not any(k in current_comp_name for k in ["POCKET", "POCKETING", "LÓT"]):
            is_main_fabric = True
            
    if any(k in current_comp_name for k in ["POCKET", "POCKETING", "LÓT"]) or current_mat_class in ["LINING", "POCKETING"]:
        is_pocket_fabric = True

    # 1. ÉP KIỂU DỮ LIỆU SỐ THỰC HÌNH HỌC RẬP
    try: p_count = int(float(row.get("piece_count", 1) or 1))
    except: p_count = 1
        
    try: poly_area = float(row.get("polygon_net_area", 0.0) or 0.0)
    except: poly_area = 0.0
    
    area_mode = str(row.get("polygon_area_mode", "PER_PIECE")).upper().strip()
    poly_unit = str(row.get("polygon_unit", "IN2")).upper().strip()
    
    try: b_length = float(row.get("bounding_box_length", 0.0) or 0.0)
    except: b_length = 0.0
        
    try: b_width = float(row.get("bounding_box_width", 0.0) or 0.0)
    except: b_width = 0.0
    
    # Bộ lọc nhận diện chi tiết lớn hay chi tiết nhỏ lọt khe sơ đồ
    MAJOR_KEYWORDS = ["FRONT", "BACK", "THÂN", "PANEL", "CARGO", "TÚI HỘP"]
    is_major = any(kw in current_comp_name for kw in MAJOR_KEYWORDS)
    if b_width < 4.5 or b_length < 6.5:
        is_major = False

    # 2. PHÉP TOÁN NHÂN DIỆN TÍCH NET AREA TỰ ĐỘNG HIỆU CHUẨN
    if poly_area > 0.0:
        u_unit = poly_unit.upper().strip()
        if u_unit in ["CM2", "CMSQ", "SQUARE_CM"]:
            converted_poly = poly_area / 6.4516
        elif u_unit in ["MM2", "MMSQ", "SQUARE_MM"]:
            converted_poly = poly_area / 645.16
        else:
            converted_poly = poly_area
        total_net_area = converted_poly if area_mode == "TOTAL" else converted_poly * p_count
        geo_source = "Gerber/Lectra Polygon DXF"
    else:
        # SỬA LỖI TẠI ĐÂY: Tính diện tích hình chữ nhật bao thô chuẩn (Dài x Rộng x Số lượng)
        raw_box_area = b_length * b_width * p_count
        prod_map = PRODUCT_NET_AREA_MATRIX.get(active_product, PRODUCT_NET_AREA_MATRIX["DEFAULT"])
        
        if is_pocket_fabric:
            net_factor = prod_map.get("LINING", 0.78)
        elif any(k in current_comp_name for k in ["WAISTBAND", "CẠP", "FLY", "NẸP"]):
            net_factor = 0.90  
        elif is_main_fabric:
            net_factor = prod_map.get("MAIN_FABRIC", 0.82)
        else:
            net_factor = 0.80
            
        total_net_area = raw_box_area * net_factor
        geo_source = "CAD Convex Hull Inferred"

    # 3. XỬ LÝ KHỔ VẢI THỰC TẾ (SƠ ĐỒ BÁO KHỔ ĐANG LÀ 57 INCH)
    try: width_inch = float(row.get("fabric_width_inch", 0.0) or 0.0)
    except: width_inch = 0.0
    if width_inch <= 0.0:
        width_inch = 57.0

    # 4. ĐỘ CO RÚT VÀ HIỆU SUẤT GIÁC SƠ ĐỒ CHUẨN ĐỒ DENIM
    try:
        warp_num = float(spec_meta.get("warp_shrink", 3.0)) / 100.0
        weft_num = float(spec_meta.get("weft_shrink", 3.0)) / 100.0
    except:
        warp_num, weft_num = 0.03, 0.03

    # Đồng bộ hiệu suất sơ đồ chuẩn hàng Jeans Denim theo đúng yêu cầu
    if is_major:
        base_eff = 0.87  # Thân lớn cố định 87%
    else:
        base_eff = 0.88  # Chi tiết nhỏ xếp xen kẽ đạt 88%

    ai_marker_efficiency = round(base_eff, 3)
    row["marker_efficiency"] = ai_marker_efficiency

    # 5. MA TRẬN HAO HỤT CÔNG NGHIỆP TĨNH DENIM (~4.3%)
    INDUSTRIAL_LOSS_MATRIX = {
        "DENIM": {"marker_end": 0.008, "spread_waste": 0.012, "relaxation": 0.005, "defect_cut": 0.010, "roll_end": 0.008}
    }
    total_industrial_loss = sum(INDUSTRIAL_LOSS_MATRIX["DENIM"].values())
    
    try: gather_ratio = float(spec_meta.get("gather_ratio", 1.00))
    except: gather_ratio = 1.00

    # 6. 🛠️ SỬA LẠI CÔNG THỨC TOÁN HỌC GERBER CAD TIÊU CHUẨN ĐỔ RA YARDS ĐÚNG THỰC TẾ
    gross_consumption_yards = 0.0
    if total_net_area > 0.0 and width_inch > 0.0:
        # Tính toán diện tích đã cộng độ co rút dọc và ngang
        area_with_shrinkage = total_net_area * (1.0 + warp_num) * (1.0 + weft_num) * gather_ratio
        
        # Áp dụng chiết khấu 25% diện tích vải thô cho các linh kiện nhỏ vì đi lọt lách vào háng/đáy quần bò
        if not is_major and not is_pocket_fabric:
            area_with_shrinkage = area_with_shrinkage * 0.75 
            
        # Công thức chuẩn: Diện tích / (Khổ vải inch * 36 inch để đổi ra Yards * Hiệu suất sơ đồ)
        raw_yards = area_with_shrinkage / (width_inch * 36.0 * ai_marker_efficiency)
        gross_consumption_yards = raw_yards * (1.0 + total_industrial_loss)

    # Khối phòng vệ dự phòng tính toán thô chuẩn nhà máy (nếu công thức trên dính lỗi chia)
    if gross_consumption_yards <= 0.005 and (b_length > 0 and b_width > 0):
        # Tính toán ước lượng thực tế tiến trình sơ đồ dệt
        approx_yards = (b_length * p_count) / 36.0
        if not is_major:
            approx_yards = approx_yards * 0.50 # Chi tiết phụ giảm một nửa chiều dài đóng góp sơ đồ
        gross_consumption_yards = (approx_yards / ai_marker_efficiency) * (1.0 + total_industrial_loss)

    gross_consumption_meters = gross_consumption_yards * 0.9144
    
    return round(gross_consumption_yards, 4), round(gross_consumption_meters, 4), geo_source







def preprocess_bom_and_execute(agent_output_json: dict, product_type: str) -> list:
    """
    Pipeline Wrapper v40.0: 100% Data-Driven.
    Loại bỏ hoàn toàn Regex. Bóc tách trực tiếp đối tượng JSON có cấu trúc từ AI.
    """
    # Trích xuất dữ liệu sạch từ JSON của Agent đầu ra
    ai_meta = agent_output_json.get("spec_meta", {})
    bom_rows = agent_output_json.get("bom_rows", [])
    
    # Ép kiểu dữ liệu an toàn đảm bảo tính toàn vẹn hệ thống toán học
    spec_meta = {
        "warp_shrink": float(ai_meta.get("warp_shrink", 3.0)),
        "weft_shrink": float(ai_meta.get("weft_shrink", 3.0)),
        "gather_ratio": float(ai_meta.get("gather_ratio", 1.00)),
        "has_stripe": bool(ai_meta.get("has_stripe", False)),
        "fabric_group": str(ai_meta.get("fabric_group", "WOVEN")).upper().strip(),
        "cargo_pocket_accumulated_area": 0.0
    }

    # TÍNH TRƯỚC TỔNG DIỆN TÍCH TÚI CARGO (CHẠY 1 VÒNG LẶP DUY NHẤT CHO CẢ BẢNG BOM)
    prod_type_upper = str(product_type).upper()
    if "CARGO" in prod_type_upper or spec_meta["fabric_group"] == "DENIM":
        total_cargo_area = 0.0
        for b_row in bom_rows:
            if not b_row or not isinstance(b_row, dict): 
                continue
            c_name = str(b_row.get("component_name", "")).upper()
            
            if any(k in c_name for k in ["CARGO", "PATCH POCKET", "TÚI HỘP", "FLAP", "NẮP TÚI"]):
                p_len = float(b_row.get("bounding_box_length", 0.0) or 0.0)
                p_wid = float(b_row.get("bounding_box_width", 0.0) or 0.0)
                p_cnt = int(b_row.get("piece_count", 1) or 1)
                p_poly = float(b_row.get("polygon_net_area", 0.0) or 0.0)
                
                pocket_area = p_poly if p_poly > 0.0 else (p_len * p_wid * 0.85)
                if pocket_area <= 0.0 and any(f in c_name for f in ["CARGO", "TÚI HỘP"]):
                    pocket_area = 9.0 * 8.0 * 0.85  # Thông số mặc định khung hộp túi Cargo
                    
                total_cargo_area += (pocket_area * p_cnt)
        
        spec_meta["cargo_pocket_accumulated_area"] = total_cargo_area

    # CHẠY VÒNG LẶP CHÍNH ĐỂ ĐẨY VÀO LÕI MÁY TÍNH TOÁN
    updated_bom_results = []
    for row in bom_rows:
        if not row or not isinstance(row, dict): 
            continue
            
        comp_name = str(row.get("component_name", "")).upper()
        mat_class = str(row.get("material_class", "")).upper()
        
        # Sàng lọc loại bỏ phụ liệu cứng bằng code Python
        if any(k in comp_name or k in mat_class for k in EXCLUDE_HARDWARE_KEYS):
            continue
            
        # Kích hoạt lõi Gerber CAM Core tính toán định mức cuộn tĩnh
        yards, meters, source = compute_fabric_engine(row, product_type, spec_meta)
        
        row["calculated_consumption_yards"] = yards
        row["calculated_consumption_meters"] = meters
        row["geometry_source_audit"] = source
        
        updated_bom_results.append(row)
        
    return updated_bom_results





import copy
import streamlit as st

# 🌟 CẢI TIẾN: Thu hẹp danh sách chặn, tuyệt đối loại bỏ các từ "CHỈ", "CHI TIẾT" 
# Chỉ chặn các linh kiện phần cứng đếm chiếc độc lập
HARDWARE_WORDS = {
    "ZIPPER", "BUTTON", "NÚT", "SHANK", "RIVET", "TAG", 
    "EYELETS", "SNAP", "VELCRO", "HOOK", "LOOP", "STOPPER", "TOGGLE", 
    "BUCKLE", "GROMMET", "STICKER", "POLYBAG", "BAO BÌ"
}

def is_hardware_component(component_name: str, material_class: str) -> bool:
    """Bộ kiểm tra an toàn: Tuyệt đối không chặn nhầm Keo, Lót, Thun, Chỉ cuộn"""
    c_text = f" {str(component_name).upper().strip()} "
    m_text = f" {str(material_class).upper().strip()} "
    
    # Cho phép các từ khóa liên quan đến keo lót đi qua ngay lập tức, không xét bộ lọc chặn
    if any(k in c_text or k in m_text for k in ["KEO", "DỰNG", "FUSING", "INTERLINING", "MEX", "LÓT"]):
        return False
        
    # Loại bỏ nhãn mác đếm chiếc (nếu thuộc nhóm COUNT)
    if "COUNT" in m_text and any(k in c_text for k in ["LABEL", "MÁC", "TAG", "HANGTAG"]):
        return True
        
    # So khớp chính xác tách từ cho phụ liệu cứng
    for word in HARDWARE_WORDS:
        if f" {word} " in c_text or f" {word} " in m_text:
            return True
            
    return False
# =====================================================================
# LÕI TÍNH TOÁN PHỤ TRỢ TĨNH CHUẨN IE FACTORY MATRIX - VERSION 56.0
# 🌟 TUYỆT ĐỐI KHÔNG GỌI AI: 100% Xử lý toán học bằng CPU Python tĩnh
# =====================================================================

def compute_elastic_engine(row: dict) -> tuple:
    """Engine chuyên tính toán cho Chun / Thun cạp co giãn bằng toán học phẳng"""
    try: e_length = float(row.get("length_inch", 0.0) or row.get("bounding_box_length", 0.0) or 0.0)
    except: e_length = 0.0
        
    try: e_count = int(float(row.get("piece_count", 1) or 1))
    except: e_count = 1
        
    try: stretch = float(row.get("stretch_pct", 1.00) or 1.00)
    except: stretch = 1.00
    
    # Công thức: Chiều dài x Số lượng x Độ co giãn thun x 5% hao hụt biên cắt đầu chun
    total_inches = e_length * e_count * stretch * 1.05
    gross_yards = round(total_inches / 36.0, 4)
    gross_meters = round(gross_yards * 0.9144, 4)
    
    note = f"CAM ElasticCore v56.0 | L:{e_length}\" | Qty:{e_count} | Stretch:{stretch}x | Loss:5%"
    return gross_yards, gross_meters, note


def compute_tape_engine(row: dict) -> tuple:
    """Engine chuyên tính toán cho Dây Tape / Dây Viền / Dây dệt bằng toán học phẳng"""
    try: t_length = float(row.get("length_inch", 0.0) or row.get("bounding_box_length", 0.0) or 0.0)
    except: t_length = 0.0
        
    try: t_count = int(float(row.get("piece_count", 1) or 1))
    except: t_count = 1
    
    # Công thức: Chiều dài dây x Số lượng x 3% hao hụt nối đầu cây viền
    total_inches = t_length * t_count * 1.03
    gross_yards = round(total_inches / 36.0, 4)
    gross_meters = round(gross_yards * 0.9144, 4)
    
    note = f"CAM TapeCore v56.0 | Length:{t_length}\" | Qty:{t_count} | Industrial Loss:3%"
    return gross_yards, gross_meters, note


def compute_thread_engine() -> tuple:
    """Engine tính định mức Chỉ may công nghiệp theo ma trận tiêu chuẩn nhà máy tĩnh"""
    gross_yards = 18.5000
    gross_meters = round(gross_yards * 0.9144, 4)
    note = f"CAM ThreadCore v56.0 | IE Factory Sew-in Target Matrix Standard"
    return gross_yards, gross_meters, note


import copy
import re
import math

def allocate_fabric_consumption_and_quality_gate(blueprint_final: dict, current_query: str = "", *args, **kwargs) -> dict:
    """
    Enterprise Multi-Engine CAD Router v75.0 - RULE-DRIVEN INDUSTRIAL MATRIX.
    🌟 PHẦN 1: Khởi tạo Rule Engine động, bóc tách cấu trúc Grading Size và cô lập dữ liệu.
    """
    if not blueprint_final or "bom_rows" not in blueprint_final:
        return blueprint_final
        
    router_bom_rows = []
    
    # 1. ĐỌC THÔNG SỐ CO RÚT VÀ HAO HỤT CÔNG NGHIỆP TỪ SPEC_META
    ai_meta = blueprint_final.get("spec_meta", {})
    try: warp_shrink = float(ai_meta.get("warp_shrink", 3.0))
    except: warp_shrink = 3.0
    warp_shrink_factor = 1.0 + (warp_shrink / 100.0)

    try: weft_shrink = float(ai_meta.get("weft_shrink", 3.0))
    except: weft_shrink = 3.0
    weft_shrink_factor = 1.0 + (weft_shrink / 100.0)

    # Đọc hao hụt đầu sào/hao hụt cắt từ Meta (mặc định 4.3% nếu trống)
    industrial_loss = float(ai_meta.get("industrial_loss_rate", 0.043))

    # Danh sách lọc sạch phụ liệu cứng và chỉ thêu trực tiếp
    EXCLUDE_HARDWARE_AND_THREAD = {
        "ZIPPER", "BUTTON", "NÚT", "SHANK", "RIVET", "TAG", "LABEL", "MÁC", "HANGTAG",
        "EYELETS", "SNAP", "VELCRO", "HOOK", "LOOP", "STOPPER", "TOGGLE", "THREAD", "CHỈ",
        "STEPESTITCH", "TOPSTITCH", "SEWING", "ASTRA", "COATS", "TWILL TAPE"
    }

    # BÓC TÁCH KHỔ VẬT TƯ ĐỘNG TỪ LỆNH CHAT BẰNG REGEX
    query_lower = str(current_query).lower()
    parsed_main_width = float(ai_meta.get("default_fabric_width", 57.0))
    
    match_main = re.search(r'(?:khổ|kho)\s*[:\-=\s]*([\d\.]+)', query_lower)
    if match_main: parsed_main_width = float(match_main.group(1))

    # =====================================================================
    # 📑 CHUYỂN ĐỔI THÀNH RULE ENGINE: MA TRẬN BÙ BIÊN ĐƯỜNG MAY CHUẨN IE (SA)
    # =====================================================================
    SEAM_RULE_MATRIX = {
        "JACKET": {
            "BODY": [0.88, 1.44], "SLEEVE": [0.88, 1.25], "COLLAR": [0.50, 0.50],
            "CUFF": [0.50, 0.50], "POCKET": [0.88, 1.50], "PLACKET": [0.50, 0.88], "DEFAULT": [0.88, 0.88]
        },
        "PANTS": {
            "BODY": [1.00, 1.75], "POCKET": [0.88, 1.25], "WAISTBAND": [0.50, 0.88], "DEFAULT": [0.75, 0.75]
        },
        "DRESS": {
            "BODY": [0.88, 0.88], "TIER": [0.88, 1.50], "DEFAULT": [0.88, 0.88]
        },
        "DEFAULT": {
            "DEFAULT": [0.75, 0.75]
        }
    }

    # =====================================================================
    # 🧠 CHUYỂN ĐỔI THÀNH RULE ENGINE: MA TRẬN HIỆU SUẤT SƠ ĐỒ ĐỘNG (MARKER EFF)
    # =====================================================================
    NESTING_EFF_MATRIX = {
        "JACKET": {"BODY": 0.85, "SLEEVE": 0.82, "POCKET": 0.78, "DEFAULT": 0.82},
        "PANTS": {"BODY": 0.87, "POCKET": 0.85, "DEFAULT": 0.85},
        "DRESS": {"BODY": 0.82, "TIER": 0.78, "DEFAULT": 0.80},
        "DEFAULT": {"DEFAULT": 0.82}
    }
    
    # =====================================================================
    # 🔍 BỘ NHẬN DIỆN MÃ HÀNG ĐỘNG (PRODUCT TYPE CLASS ENGINE)
    # =====================================================================
    product_type = "DEFAULT"
    for r in blueprint_final.get("bom_rows", []):
        if not r: continue
        name_check = str(r.get("Component Name", r.get("component_name", ""))).upper().strip()
        
        if any(kw in name_check for kw in ["DRESS", "VÁY", "BODICE", "TIER", "SKIRT"]):
            product_type = "DRESS"
            break
        elif any(kw in name_check for kw in ["JACKET", "COAT", "ÁO", "SLEEVE", "COLLAR", "CUFF"]):
            product_type = "JACKET"
            break
        elif any(kw in name_check for kw in ["JEAN", "PANTS", "QUẦN", "CARGO", "TROUSER", "SHORT"]):
            product_type = "PANTS"
            break

         # 🔥 ĐOẠN 2.1: BỘ LỌC KHỬ TRÙNG & SỬA LỖI ĐỊNH TUYẾN CHUỖI TỪ KHÓA TÚI QUẦN
    # =====================================================================
    seen_pieces = set()
    unique_bom_rows = []
    
    raw_bom_source = blueprint_final.get("bom_rows", []) if isinstance(blueprint_final, dict) else (blueprint_final if isinstance(blueprint_final, list) else [])
    
    for row in raw_bom_source:
        if not row: continue
        r_name = " ".join(str(row.get("Component Name", row.get("component_name", ""))).upper().split())
        r_mat = " ".join(str(row.get("Material Class", row.get("material_class", ""))).upper().split())
        r_len = str(row.get("Dài sản xuất (L-inch)", row.get("bounding_box_length", "0")))
        r_wid = str(row.get("Rộng sản xuất (W-inch)", row.get("bounding_box_width", "0")))
        
        absolute_key = (r_name, r_mat, r_len, r_wid)
        if absolute_key in seen_pieces:
            continue  
        seen_pieces.add(absolute_key)
        unique_bom_rows.append(row)

    # 2. Thu thập kích thước Thân tổng dự phòng phục vụ vá lỗi Techpack gom dòng
    main_body_len = 0.0
    main_body_wid = 0.0
    for r in unique_bom_rows:
        r_name = str(r.get("Component Name", r.get("component_name", ""))).upper()
        if "ALLOVER" in r_name or "BODY" in r_name or "PANEL" in r_name:
            try:
                main_body_len = float(r.get("bounding_box_length", r.get("Dài sản xuất (L-inch)", 0.0)))
                main_body_wid = float(r.get("bounding_box_width", r.get("Rộng sản xuất (W-inch)", 0.0)))
                if main_body_len > 0: break
            except: pass

    has_waistband_fusing = any(
        "FUSING" in str(r.get("Component Name", r.get("component_name", ""))).upper() and "WAISTBAND" in str(r.get("Component Name", r.get("component_name", ""))).upper()
        for r in unique_bom_rows
    )
    is_waistband_elastic = False
    has_welt_pocket = False
    for r in unique_bom_rows:
        r_name = str(r.get("Component Name", r.get("component_name", ""))).upper()
        r_mat = str(r.get("Material Class", r.get("material_class", ""))).upper()
        if "ELASTIC" in r_name or "CHUN" in r_name or "THUN" in r_name or "ELASTIC" in r_mat:
            if "WAIST" in r_name or "LƯNG" in r_name or "CẠP" in r_name: is_waistband_elastic = True
        if any(kw in r_name for kw in ["WELT", "CƠI", "MỔ", "FACING"]): has_welt_pocket = True

    generated_fusing_rows = []
    router_bom_rows = []

    # 4. Tiến hành lặp duyệt trên danh sách rập ĐÃ ĐƯỢC LỌC SẠCH TRÙNG LẶP
    for ai_row in unique_bom_rows:
        ui_row = copy.deepcopy(ai_row)
        
        comp_name = str(ui_row.get("Component Name", ui_row.get("component_name", ""))).upper().strip()
        mat_class = str(ui_row.get("Material Class", ui_row.get("material_class", ui_row.get("engine", "FABRIC")))).upper().strip()
        uom_target = str(ui_row.get("UOM", ui_row.get("uom", "YDS"))).upper().strip()
        
        if any(key in comp_name or key in mat_class for key in ["ZIPPER", "BUTTON", "NÚT", "KHÓA", "THREAD", "CHỈ", "SHANK", "RIVET", "TRIM", "LABEL", "TAG"]):
            continue 
            
        # 🌟 SỬA BẪY TỪ KHÓA TẠI ĐÂY: Nhận diện chính xác cụm lót túi bất kể có chữ MAIN FABRIC đứng trước hay không
        is_pocket_component = any(k in comp_name for k in ["POCKET BAG", "LOT TUI", "LÓT TÚI", "POCKETING"]) or ("POCKET" in comp_name and "FLAP" not in comp_name and "BACK POCKET" not in comp_name)
        
        if any(k in comp_name or k in mat_class for k in ["KEO", "DỰNG", "FUSING", "INTERLINING", "MEX"]):
            engine_target = "FUSING"
        elif is_pocket_component:
            # Ép chi tiết lót túi văng ra khỏi vải chính, chuyển hẳn sang phân hệ LINING
            engine_target = "LINING"
            ui_row["Material Class"] = "LINING"
        elif "THUN" in comp_name or "CHUN" in comp_name or "ELASTIC" in mat_class:
            engine_target = "ELASTIC"
        else:
            engine_target = "FABRIC"

        raw_len = float(ai_row.get("bounding_box_length", 0.0))
        raw_wid = float(ai_row.get("bounding_box_width", 0.0))
        if raw_len <= 0: raw_len = float(ai_row.get("Dài sản xuất (L-inch)", 0.0))
        if raw_wid <= 0: raw_wid = float(ai_row.get("Rộng sản xuất (W-inch)", 0.0))
        
        try: p_count = int(float(ui_row.get("Số lượng rập (Pcs)", ui_row.get("piece_count", 1))))
        except: p_count = 1
        width_inch = parsed_main_width

        # Đồng bộ hóa cấu phần phụ trợ (bỏ qua tiền tố để nhận diện đúng sub_component)
        sub_component = "DEFAULT"
        if any(kw in comp_name for kw in ["FRONT PANEL", "BACK PANEL", "BODY", "THÂN CHÍNH"]): sub_component = "BODY"
        elif "SLEEVE" in comp_name or "TAY" in comp_name: sub_component = "SLEEVE"
        elif "COLLAR" in comp_name or "CỔ" in comp_name: sub_component = "COLLAR"
        elif "CUFF" in comp_name or "MANS" in comp_name or "BO TAY" in comp_name: sub_component = "CUFF"
        elif "PLACKET" in comp_name or "NẸP" in comp_name or "BAGET" in comp_name: sub_component = "PLACKET"
        elif "TIER" in comp_name or "TẦNG" in comp_name: sub_component = "TIER"
        elif "POCKET" in comp_name or "TÚI" in comp_name: sub_component = "POCKET"
        elif "WAISTBAND" in comp_name or "CẠP" in comp_name or "LƯNG" in comp_name: sub_component = "WAISTBAND"

        if engine_target == "FUSING" and raw_len <= 0.0:
            if main_body_len > 0:
                raw_len = main_body_len
                raw_wid = main_body_wid * 0.15 
            else:
                raw_len = 34.0
                raw_wid = 3.5

        prod_rules = SEAM_RULE_MATRIX.get(product_type, SEAM_RULE_MATRIX["DEFAULT"])
        seam_allowance = prod_rules.get(sub_component, prod_rules["DEFAULT"])
        
        if isinstance(seam_allowance, (list, tuple)):
            sa_w = float(seam_allowance) if len(seam_allowance) > 0 else 0.5
            sa_l = float(seam_allowance) if len(seam_allowance) > 1 else sa_w
        else:
            sa_w = float(seam_allowance)
            sa_l = float(seam_allowance)

        if engine_target != "FUSING" and engine_target != "ELASTIC":
            raw_wid_with_sa = raw_wid + sa_w
            raw_len_with_sa = raw_len + sa_l
            calc_note = f"📌 {product_type}-{sub_component} | Biên may W+{sa_w}\" L+{sa_l}\" | "
        else:
            raw_wid_with_sa = raw_wid
            raw_len_with_sa = raw_len
            calc_note = f"📌 {product_type}-{sub_component} | Fusing cắt sát rập thành phẩm | "

        if raw_len_with_sa <= 0.0 or raw_wid_with_sa <= 0.0:
            ui_row["Gross Consumption"] = 0.0
            router_bom_rows.append(ui_row)
            continue


               # 🔥 ĐOẠN 3.1: MULTI-ENGINE CAD ROUTER (BẢN ÉP CHIỀU DÀI THEO THÂN CHÍNH CHỐNG PHÌNH DM)
        # =====================================================================
        gross_yds = 0.0
        try:
            shrunk_len = raw_len_with_sa * warp_shrink_factor
            shrunk_wid = raw_wid_with_sa * weft_shrink_factor
            active_wid = float(width_inch) if float(width_inch) > 0 else 56.0
            active_count = int(p_count)

            eff_rules = NESTING_EFF_MATRIX.get(product_type, NESTING_EFF_MATRIX["DEFAULT"])
            nesting_data = eff_rules.get(sub_component, eff_rules["DEFAULT"])
            marker_efficiency = float(nesting_data) if isinstance(nesting_data, list) else float(nesting_data)

            LAYOUT_FACTOR_MATRIX = {
                "KNIT": 1.01, "SHIRT": 1.02, "PANTS": 1.00, "DRESS": 1.03, "JACKET": 1.03, "DEFAULT": 1.01
            }
            material_group = ai_meta.get("fabric_group", "WOVEN").upper().strip()
            current_layout_factor = LAYOUT_FACTOR_MATRIX.get(product_type, LAYOUT_FACTOR_MATRIX.get(material_group, LAYOUT_FACTOR_MATRIX["DEFAULT"]))

            if engine_target == "FABRIC":
                total_fabric_net_area = 0.0
                max_primary_len = 0.0
                
                # 🌟 THAY ĐỔI CỐT LÕI: Chỉ tính diện tích của THÂN CHÍNH (FRONT/BACK/BODY) để dựng khung sơ đồ
                for r_scan in unique_bom_rows:
                    if not r_scan: continue
                    scan_comp = str(r_scan.get("Component Name", r_scan.get("component_name", ""))).upper().strip()
                    scan_mat = str(r_scan.get("Material Class", r_scan.get("material_class", "FABRIC"))).upper().strip()
                    
                    is_scan_fusing = any(k in scan_comp or k in scan_mat for k in ["KEO", "DỰNG", "FUSING", "INTERLINING", "MEX"])
                    is_scan_lining = any(k in scan_comp for k in ["LÓT", "LINING", "POCKETING", "BAG", "POCKET BAG", "LOT TUI"])
                    is_scan_elastic = "THUN" in scan_comp or "CHUN" in scan_comp or "ELASTIC" in scan_mat
                    is_scan_trim = any(k in scan_comp or k in scan_mat for k in ["ZIPPER", "BUTTON", "NÚT", "KHÓA", "THREAD", "CHỈ"])

                    if not (is_scan_fusing or is_scan_lining or is_scan_elastic or is_scan_trim):
                        # Lọc chuẩn: Chỉ cộng dồn diện tích nếu là Thân trước hoặc Thân sau lớn
                        is_main_body = any(kw in scan_comp for kw in ["FRONT PANEL", "BACK PANEL", "BODY", "THÂN CHÍNH"])
                        try:
                            l_s = float(r_scan.get("bounding_box_length", r_scan.get("Dài sản xuất (L-inch)", 0.0)))
                            if l_s <= 0: l_s = float(r_scan.get("Dài sản xuất (L-Inch)", 0.0))
                            l_s = l_s * warp_shrink_factor
                            
                            w_s = float(r_scan.get("bounding_box_width", r_scan.get("Rộng sản xuất (W-inch)", 0.0)))
                            if w_s <= 0: w_s = float(r_scan.get("Rộng sản xuất (W-Inch)", 0.0))
                            w_s = w_s * weft_shrink_factor
                            
                            c_s = int(float(r_scan.get("piece_count", r_scan.get("Số lượng rập (Pcs)", 1))))
                            
                            if is_main_body:
                                total_fabric_net_area += (l_s * w_s * c_s)
                            if l_s > max_primary_len and is_main_body: 
                                max_primary_len = l_s
                        except: pass

                usable_fabric_width = active_wid - 1.2
                if usable_fabric_width <= 0: usable_fabric_width = 54.8
                theoretical_marker_len_inch = total_fabric_net_area / (usable_fabric_width * marker_efficiency) if total_fabric_net_area > 0 else 0
                
                if theoretical_marker_len_inch < max_primary_len:
                    total_marker_length_inch = max_primary_len * 1.01
                else:
                    total_marker_length_inch = theoretical_marker_len_inch

                # Tổng định mức dài bàn cắt thực tế của cụm thân chính
                total_marker_gross_yds = (total_marker_length_inch / 36.0) * current_layout_factor * (1.0 + industrial_loss)
                current_piece_net_area = shrunk_len * shrunk_wid * float(active_count)
                
                # 🌟 NẮN LOGIC PHÂN BỔ: 
                # Nếu là chi tiết lớn (Thân), ăn theo tỷ lệ sơ đồ tổng.
                # Nếu là chi tiết nhỏ (Đỉa, túi, đáp...), tính lách độc lập quy đổi ra diện tích cực nhỏ chứ không kéo dài sơ đồ.
                is_current_main = any(kw in comp_name for kw in ["FRONT PANEL", "BACK PANEL", "BODY", "THÂN CHÍNH"])
                
                if total_fabric_net_area > 0 and is_current_main:
                    area_contribution_ratio = current_piece_net_area / total_fabric_net_area
                    gross_yds = total_marker_gross_yds * area_contribution_ratio
                    calc_note += f"📊 [MARKER BASED] Phân bổ theo thân chính | "
                else:
                    # Công thức lách rập cho chi tiết nhỏ: Hiệu suất lách rập cực cao (95%) vì nhét vào khe hở
                    gross_yds = (current_piece_net_area / (active_wid * 36.0 * 0.95)) * (1.0 + industrial_loss)
                    calc_note += f"✂️ [NESTED PIECE] Tính lách vào khoảng trống sơ đồ | "

            elif engine_target == "LINING":
                eff_lining = 0.82
                pieces_per_row = max(1, int(active_wid / (shrunk_wid + 0.1)))
                required_vertical_rows = math.ceil(active_count / float(pieces_per_row))
                allocated_lining_len_inch = shrunk_len * required_vertical_rows
                
                gross_yds = (allocated_lining_len_inch / 36.0) * (1.0 + industrial_loss)
                marker_efficiency = eff_lining
                calc_note += f"✂️ Xếp lót ({pieces_per_row} pcs/hàng) | "

            elif engine_target == "FUSING":
                eff_fusing = 0.92
                fusing_shrink_l = 1.01
                fusing_shrink_w = 1.01
                
                if any(kw in comp_name or kw in sub_component for kw in ["WELT", "CƠI", "MỔ", "FACING"]):
                    shrunk_len = 7.0 * fusing_shrink_l
                    shrunk_wid = 4.0 * fusing_shrink_w
                    calc_note += "✂️ Ép kích thước keo cơi túi mặc định 7\" x 4\" | "
                else:
                    shrunk_len = raw_len_with_sa * fusing_shrink_l
                    shrunk_wid = raw_wid_with_sa * fusing_shrink_w
                
                raw_fusing_area = shrunk_len * shrunk_wid * float(active_count)
                gross_yds = (raw_fusing_area / (active_wid * 36.0 * eff_fusing)) * (1.0 + industrial_loss)
                
                max_allowable_yds = ((shrunk_len * float(active_count)) / 36.0) * (1.0 + industrial_loss)
                if gross_yds > max_allowable_yds: gross_yds = max_allowable_yds
                marker_efficiency = eff_fusing
                calc_note += "⚡ Diện tích keo chuẩn | "

            elif engine_target == "ELASTIC":
                gross_yds = ((shrunk_len * active_count) / 36.0) * 1.05
                marker_efficiency = 1.0
                calc_note += "Tính theo trục dọc chun | "

            gross_val = gross_yds * 0.9144 if uom_target == "MTR" else gross_yds
            final_rounded_value = max(0.0001, round(gross_val, 4))

            ui_row["Dài sản xuất (L-inch)"] = round(raw_len_with_sa, 2)
            ui_row["Rộng sản xuất (W-inch)"] = round(raw_wid_with_sa, 2)
            ui_row["Gross Consumption"] = final_rounded_value
            ui_row["gross_consumption"] = final_rounded_value
            ui_row["calculated_consumption"] = final_rounded_value
            ui_row["Marker Efficiency"] = marker_efficiency
            ui_row["Notes"] = calc_note
            
            router_bom_rows.append(ui_row)

            # 🌟 TỰ ĐỘNG SINH MẾCH KEO CHO CÁC CHI TIẾT NHỎ CỦA QUẦN JEANS / CARGO
            if engine_target == "FABRIC" and product_type == "PANTS":
                if sub_component == "WAISTBAND" and not is_waistband_elastic:
                    f_row = copy.deepcopy(ui_row)
                    f_row["Component Name"] = f"{comp_name} INTERLINING KEO (AUTO JEANS)"
                    f_row["Material Class"] = "FUSING"
                    f_row["Notes"] = "⚡ Quy tắc IE: Ép keo lưng cứng Baget cho quần Jean"
                    f_row["bounding_box_length"] = raw_len
                    f_row["bounding_box_width"] = raw_wid
                    generated_fusing_rows.append(f_row)
                    
                if sub_component == "POCKET" or any(k in comp_name for k in ["FLAP", "WELT", "CƠI", "NẮP"]):
                    f_row = copy.deepcopy(ui_row)
                    f_row["Component Name"] = f"{comp_name} INTERLINING KEO (AUTO POCKET)"
                    f_row["Material Class"] = "FUSING"
                    f_row["Notes"] = "⚡ Quy tắc IE: Tự động ép keo mếch cho chi tiết túi"
                    f_row["bounding_box_length"] = raw_len
                    f_row["bounding_box_width"] = raw_wid
                    generated_fusing_rows.append(f_row)

                if any(k in comp_name for k in ["FLY", "FACING", "SHIELD", "ĐÁP", "BAGET"]):
                    f_row = copy.deepcopy(ui_row)
                    f_row["Component Name"] = f"{comp_name} INTERLINING KEO (AUTO FLY)"
                    f_row["Material Class"] = "FUSING"
                    f_row["Notes"] = "⚡ Quy tắc IE: Tự động ép keo cửa quần (Fly)"
                    f_row["bounding_box_length"] = raw_len
                    f_row["bounding_box_width"] = raw_wid
                    generated_fusing_rows.append(f_row)
        except Exception as e:
            pass

    if generated_fusing_rows:
        router_bom_rows.extend(generated_fusing_rows)



   


    # 🌟 CHỐT CHẶN TRIỆT TIÊU LỖI PHƯƠNG THỨC: Thay thế hoàn toàn cơ chế .get lỗi của hệ thống gốc
    # =====================================================================
    bom_rows_source = []
    if 'blueprint_final' in locals() and blueprint_final:
        if isinstance(blueprint_final, dict):
            bom_rows_source = blueprint_final.get("bom_rows", [])
        elif isinstance(blueprint_final, list):
            bom_rows_source = blueprint_final

    # Kiểm tra biến cục bộ và ép đồng bộ trạng thái lưu trữ Streamlit
    if 'router_bom_rows' in locals() and router_bom_rows:
        st.session_state["accumulated_bom_rows"] = copy.deepcopy(router_bom_rows)
        # Ép đè trực tiếp lên blueprint_processed/accumulated_bom_rows gốc để ngăn chặn dòng mã lỗi chạy tiếp
        if 'blueprint_processed' in locals() and isinstance(blueprint_processed, dict):
            blueprint_processed["bom_rows"] = copy.deepcopy(router_bom_rows)
    else:
        st.session_state["accumulated_bom_rows"] = copy.deepcopy(bom_rows_source)
    # =====================================================================


   











import streamlit as st

# =====================================================================
# ĐOẠN 6a: KHỞI TẠO BỘ NHỚ STATE & CẤU HÌNH CSS PHẲNG NATIVE CHUẨN ERP
# =====================================================================

# 1. Cấu hình trang rộng toàn màn hình chuẩn hệ thống SaaS/ERP Văn phòng
st.set_page_config(layout="wide", page_title="AI Fabric Consumption Matrix")

# 2. Khởi tạo an toàn cấu trúc trạng thái bộ nhớ hệ thống (Session State)
if "bom_data" not in st.session_state: st.session_state.bom_data = None
if "chat_history" not in st.session_state: st.session_state.chat_history = []
if "pdf_bytes" not in st.session_state: st.session_state.pdf_bytes = None
if "pdf_name" not in st.session_state: st.session_state.pdf_name = ""
if "pdf_text_cache" not in st.session_state: st.session_state.pdf_text_cache = None
if "accumulated_bom_rows" not in st.session_state: st.session_state.accumulated_bom_rows = []

# 3. Tự động phân tách trích xuất văn bản và hình ảnh trang đầu từ tài liệu PDF
if st.session_state.pdf_bytes is not None and (st.session_state.pdf_text_cache is None or st.session_state.get("pdf_page_one_image") is None):
    try:
        import fitz
        doc = fitz.open(stream=st.session_state.pdf_bytes, filetype="pdf")
        
        # Trích xuất văn bản chữ
        if st.session_state.pdf_text_cache is None:
            full_text_extract = ""
            for page_num in range(len(doc)):
                full_text_extract += f"\n--- TRANG THỨ {page_num + 1} ---\n" + doc.load_page(page_num).get_text("text")
            st.session_state.pdf_text_cache = full_text_extract
            
        # Trích xuất hình ảnh trang đầu tiên làm Sketch bản vẽ
        if "pdf_page_one_image" not in st.session_state or st.session_state.pdf_page_one_image is None:
            if len(doc) > 0:
                page = doc.load_page(0)
                pix = page.get_pixmap(dpi=150)
                st.session_state.pdf_page_one_image = pix.tobytes("png")
    except Exception: 
        pass

# 4. Engine đồng bộ dữ liệu KPIs động biến thiên theo thời gian thực trên đỉnh trần
kpi_style_id = "N/A"
total_materials = len(st.session_state.accumulated_bom_rows) if st.session_state.accumulated_bom_rows else 0
main_fabric_cons = "0.000 Yds"
active_size_kpi = "AUTOMATIC"

if st.session_state.get("bom_data") and "bom_rows" in st.session_state.bom_data:
    kpi_style_id = str(st.session_state.bom_data.get("style_code", "R09-500778")).upper()
    active_size_kpi = str(st.session_state.bom_data.get("calculated_on_size", "MEDIAN")).upper()
    if total_materials == 0: total_materials = len(st.session_state.bom_data["bom_rows"])
    for row in st.session_state.bom_data["bom_rows"]:
        if not row: continue
        if "MAIN" in str(row.get("material_class", "")).upper() or "FABRIC" in str(row.get("material_class", "")).upper():
            val_gross = row.get("gross_consumption", 0.0)
            if val_gross > 0.0:
                main_fabric_cons = f"{val_gross:.3f} Yds"
                break


# 5. Bộ cấu hình định dạng CSS phẳng triệt tiêu vĩnh viễn mọi ô trống khổng lồ
st.markdown("""
<style>
    /* Trả màu nền ứng dụng về màu xám trắng dịu mắt chuẩn văn phòng */
    .stApp {
        background-color: #f8fafc !important;
    }
    header[data-testid="stHeader"] {
        background-color: #f8fafc !important;
    }
    
    /* Ép khoảng đệm trần Streamlit về mặc định, triệt tiêu vĩnh viễn khoảng hở */
    .block-container {
        padding-top: 1.5rem !important; 
        margin-top: 0px !important;
        max-width: 100% !important;
    }
    
    /* Ép tất cả các hàng chia cột mặc định phải co khít sát lên trên cùng */
    div[data-testid="stHorizontalBlock"] {
        margin-top: 0px !important;
        padding-top: 0px !important;
    }

    /* Thẻ chỉ số KPIs sắc màu rực rỡ chữ trắng hiển thị rõ nét vĩnh viễn */
    .kpi-box-flat-matrix {
        border-radius: 6px 6px 0 0 !important;
        padding: 10px 12px !important;
        text-align: center !important;
        box-shadow: 0 2px 4px rgba(0,0,0,0.02) !important;
        box-sizing: border-box !important;
    }
    .kpi-num-flat-matrix {
        font-size: 16px !important;
        font-weight: 700 !important;
        color: #ffffff !important; 
        font-family: 'Segoe UI', sans-serif !important;
        line-height: 1.2 !important;
    }
    .kpi-lbl-flat-matrix {
        font-size: 9px !important;
        font-weight: 600 !important;
        color: #ffffff !important;
        opacity: 0.95 !important;
        text-transform: uppercase !important;
        margin-top: 2px !important;
    }

    /* Đóng gói dải màu phân hệ động sắc nét */
    .bg-style-erp { background: linear-gradient(135deg, #334155 0%, #1e293b 100%) !important; }
    .bg-items-erp { background: linear-gradient(135deg, #0d9488 0%, #0f766e 100%) !important; }
    .bg-cons-erp  { background: linear-gradient(135deg, #ea580c 0%, #c2410c 100%) !important; }
    .bg-size-erp  { background: linear-gradient(135deg, #16a34a 0%, #15803d 100%) !important; }

    /* Hộp trắng bao bọc hình vẽ rập vector hình học gọn gàng 140px */
    .image-placeholder-box-flat {
        border: 1px solid #cbd5e1 !important;
        border-top: none !important; 
        border-radius: 0 0 6px 6px !important;
        padding: 10px 5px !important;
        height: 140px !important; 
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        box-sizing: border-box !important;
        margin-bottom: 25px !important;
        background-color: #ffffff !important;
    }
    .image-placeholder-box-flat img {
        max-height: 110px !important;
        width: auto !important;
        object-fit: contain !important;
        display: block !important;
        margin: auto !important;
    }

    /* 🌟 FIX TRIỆT ĐỂ: SỬA LỖI ẨN ẢNH VÀ TRẢ LẠI HIỂN THỊ TỰ ĐỘNG CHO SKETCH 🌟 */
    div[data-testid="stImage"] img {
        width: 100% !important;
        height: auto !important;
    }
    
    .cad-header-text-flat {
        font-family: 'Segoe UI', sans-serif !important;
        font-size: 14px !important;
        font-weight: 700 !important;
        color: #0369a1 !important; 
        margin-bottom: 15px !important;
        padding-bottom: 6px !important;
        border-bottom: 2px solid #e2e8f0 !important;
    }

    .meta-box-light-flat {
        background-color: #f8fafc !important; 
        border-left: 4px solid #0284c7 !important;
        padding: 8px 12px !important;
        margin-bottom: 8px !important;
        border-radius: 0 6px 6px 0 !important;
    }
    .meta-label-flat { font-size: 11px !important; font-weight: 700 !important; color: #64748b !important; text-transform: uppercase !important; }
    .meta-value-flat { font-size: 13px !important; font-weight: 600 !important; color: #0f172a !important; margin-top: 1px !important; }

    /* Khóa chết và ép ẩn toàn diện mọi class ghim đỉnh hoặc hàng rỗng cũ bị dính đệm */
    .main-body-spacer, 
    .sticky-top-container, 
    div[smart-fixed-container], 
    div[data-testid="stHorizontalBlock"]:empty {
        display: none !important;
        height: 0px !important;
        margin: 0 !important;
        padding: 0 !important;
    }
</style>
""", unsafe_allow_html=True)





import streamlit as st
import re

# =====================================================================
# KHỞI TẠO DỮ LIỆU ĐỂ TRÁNH LỖI BIẾN CHƯA ĐỊNH NGHĨA (NAMEERROR)
# =====================================================================
kpi_style_id = st.session_state.get("style_id", "N/A")
total_materials = 0
main_fabric_cons = "0.00"
active_size_kpi = "M"

# Khởi tạo các giá trị session state mặc định nếu chưa có
if "pdf_name" not in st.session_state: st.session_state.pdf_name = ""
if "pdf_bytes" not in st.session_state: st.session_state.pdf_bytes = None
if "pdf_text_cache" not in st.session_state: st.session_state.pdf_text_cache = None

# =====================================================================
# ĐOẠN B: GIAO DIỆN HIỂN THỊ KPIs MÀU SẮC ĐỘNG & GRID THÂN TRANG HỢP NHẤT
# =====================================================================

# 🌟 TIÊU ĐỀ ĐÃ ĐỔI SANG MÀU XANH THEME ERP SANG TRỌNG 🌟
st.markdown(
    """
    <div style="background: linear-gradient(135deg, #0f766e 0%, #115e59 100%); border-radius: 6px; padding: 14px 20px; margin-bottom: 20px; box-shadow: 0 4px 6px -1px rgba(15, 118, 110, 0.1), 0 2px 4px -1px rgba(15, 118, 110, 0.06); text-align: center;">
        <h2 style="font-family: 'Segoe UI', sans-serif; font-size: 16px; font-weight: 700; color: #ffffff; margin: 0; text-transform: uppercase; letter-spacing: 0.8px;">
            🚀 AUTOMATED CAD CONSUMPTION & INDUSTRIAL COSTING ENGINE
        </h2>
    </div>
    """, 
    unsafe_allow_html=True
)

# Chuỗi mã hóa hình ảnh vector đồ họa gốc của 4 ô trang phục
encoded_ao = "data:image/svg+xml;utf8,%3Csvg%20xmlns%3D%27http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%27%20width%3D%27100%27%20height%3D%27100%27%20viewBox%3D%270%200%2024%2024%27%20fill%3D%27none%27%20stroke%3D%27%23334155%27%20stroke-width%3D%271.25%27%20stroke-linecap%3D%27round%27%20stroke-linejoin%3D%27round%27%3E%3Cpath%20d%3D%27M20.38%203.46L16%202a4%204%200%200%200-8%200l-4.38%201.46a2%202%200%200%200-1.37%202l.35%2011.23a2%202%200%200%200%202%201.94h14.8a2%202%200%200%200%202-1.94l.35-11.23a2%202%200%200%200-1.37-2z%27%2F%3E%3Cpath%20d%3D%27M12%205v16%27%2F%3E%3Cpath%20d%3D%27M4%2010h16%27%2F%3E%3C%2Fsvg%3E"
encoded_quan = "data:image/svg+xml;utf8,%3Csvg%20xmlns%3D%27http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%27%20width%3D%27100%27%20height%3D%27100%27%20viewBox%3D%270%200%2024%2024%27%20fill%3D%27none%27%20stroke%3D%27%230f766e%27%20stroke-width%3D%271.25%27%20stroke-linecap%3D%27round%27%20stroke-linejoin%3D%27round%27%3E%3Cpath%20d%3D%27M4%202h16l-2%2020H6L4%202z%27%2F%3E%3Cpath%20d%3D%27M12%202v20%27%2F%3E%3Cpath%20d%3D%27M5%208h14%27%2F%3E%3C%2Fsvg%3E"
encoded_vest = "data:image/svg+xml;utf8,%3Csvg%20xmlns%3D%27http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%27%20width%3D%27100%27%20height%3D%27100%27%20viewBox%3D%270%200%2024%2024%27%20fill%3D%27none%27%20stroke%3D%27%23c2410c%27%20stroke-width%3D%271.25%27%20stroke-linecap%3D%27round%27%20stroke-linejoin%3D%27round%27%3E%3Cpath%20d%3D%27M4%202v20l8-4%208%204V2l-8%204-8-4z%27%2F%3E%3Cpath%20d%3D%27M12%206v12%27%2F%3E%3Cpath%20d%3D%27M4%208h16%27%2F%3E%3C%2Fsvg%3E"
encoded_vay = "data:image/svg+xml;utf8,%3Csvg%20xmlns%3D%27http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%27%20width%3D%27100%27%20height%3D%27100%27%20viewBox%3D%270%200%2024%2024%27%20fill%3D%27none%27%20stroke%3D%27%2315803d%27%20stroke-width%3D%271.25%27%20stroke-linecap%3D%27round%27%20stroke-linejoin%3D%27round%27%3E%3Cpath%20d%3D%27M6%202h12l3%207-9%2013-9-7%203-7z%27%2F%3E%3Cpath%20d%3D%27M6%209h12%27%2F%3E%3Cpath%20d%3D%27M12%202v7%27%2F%3E%3C%2Fsvg%3E"

# Phân bổ lưới 4 ô KPIs Native gốc của Streamlit
k_col1, k_col2, k_col3, k_col4 = st.columns(4)

with k_col1: 
    st.markdown(f'<div class="kpi-box-flat-matrix bg-style-erp"><div class="kpi-num-flat-matrix">{kpi_style_id}</div><div class="kpi-lbl-flat-matrix">Mã hàng đang xử lý</div></div>', unsafe_allow_html=True)
    st.markdown(f'<div class="image-placeholder-box-flat"><img src="{encoded_ao}" alt="Ao"></div>', unsafe_allow_html=True)

with k_col2: 
    st.markdown(f'<div class="kpi-box-flat-matrix bg-items-erp"><div class="kpi-num-flat-matrix">{total_materials} Item(s)</div><div class="kpi-lbl-flat-matrix">Tổng số vật tư kết xuất</div></div>', unsafe_allow_html=True)
    st.markdown(f'<div class="image-placeholder-box-flat"><img src="{encoded_quan}" alt="Quan"></div>', unsafe_allow_html=True)

with k_col3: 
    st.markdown(f'<div class="kpi-box-flat-matrix bg-cons-erp"><div class="kpi-num-flat-matrix">{main_fabric_cons}</div><div class="kpi-lbl-flat-matrix">Định mức vải chính dự kiến</div></div>', unsafe_allow_html=True)
    st.markdown(f'<div class="image-placeholder-box-flat"><img src="{encoded_vest}" alt="Vest"></div>', unsafe_allow_html=True)

with k_col4: 
    st.markdown(f'<div class="kpi-box-flat-matrix bg-size-erp"><div class="kpi-num-flat-matrix">{active_size_kpi}</div><div class="kpi-lbl-flat-matrix">Cỡ hạt tính định mức</div></div>', unsafe_allow_html=True)
    st.markdown(f'<div class="image-placeholder-box-flat"><img src="{encoded_vay}" alt="Vay"></div>', unsafe_allow_html=True)

# --- BẢNG ĐIỀU KHIỂN SIDEBAR MÁY CHỦ ---
st.sidebar.markdown("### ⚙️ ENGINE CONTROLS")
if st.sidebar.button("🗑️ CLEAR SYSTEM MEMORY", use_container_width=True):
    st.session_state.bom_data = None
    st.session_state.chat_history = []
    st.session_state.pdf_bytes = None
    st.session_state.pdf_name = ""
    st.session_state.pdf_text_cache = None
    
    if "last_active_blueprint" in st.session_state: st.session_state.last_active_blueprint = None
    if "raw_ai_debug_payload" in st.session_state: st.session_state.raw_ai_debug_payload = None
    if "pdf_page_one_image" in st.session_state: st.session_state.pdf_page_one_image = None
    if "accumulated_bom_rows" in st.session_state: st.session_state.accumulated_bom_rows = []
    st.rerun()


# ------------------------------------------------------------------------------
# LƯỚI CHIA ĐÔI CỘT CHÍNH THỰC TẾ (SỬ DỤNG HEIGHT NATIVE CỦA STREAMLIT)
# ------------------------------------------------------------------------------
col_left, col_right = st.columns(2)

# --- CỘT TRÁI: BỘ TẢI FILE & HỒ SƠ TÓM TẮT MÃ HÀNG MÀU XANH ---
with col_left:
    # Ép chiều cao native bằng tham số height, tự động sinh thanh cuộn nếu tràn nội dung
    with st.container(border=True, height=520):
        st.markdown("### 📂 TECHPACK UPLOADER & PROFILE SUMMARY")
        
        uploaded_file = st.file_uploader("Upload PDF", type=["pdf"], label_visibility="collapsed")
        
        if uploaded_file is not None:
            if st.session_state.pdf_name != uploaded_file.name:
                st.session_state.pdf_text_cache = None
                if "pdf_page_one_image" in st.session_state: st.session_state.pdf_page_one_image = None
                if "accumulated_bom_rows" in st.session_state: st.session_state.accumulated_bom_rows = []
            st.session_state.pdf_bytes = uploaded_file.read()
            st.session_state.pdf_name = uploaded_file.name

        if st.session_state.pdf_text_cache is not None:
            st.markdown("<div style='margin-top: 5px;'></div>", unsafe_allow_html=True)
            txt = st.session_state.pdf_text_cache
            
            def get_meta(pattern, default="N/A"):
                m = re.search(pattern, txt, re.IGNORECASE)
                return m.group(1).strip() if m else default

            style_id = get_meta(r'(?:Style ID|Style_ID|Mã hàng)\s*[:\-=\s]*([\w\d\-]+)', st.session_state.pdf_name.replace(".pdf",""))
            short_desc = get_meta(r'(?:Short Desc|Description|Tên sản phẩm)\s*[:\-=\s]*([^\n]+)', "THE RUCHED MINI DRESS")
            customer = get_meta(r'(?:Customer|Khách hàng|Brand)\s*[:\-=\s]*([^\n]+)', "FACTORY STANDARD")
            season = get_meta(r'(?:Season|Mùa hàng)\s*[:\-=\s]*([^\n]+)', "FALL Winter 2026")
            fabric_type = get_meta(r'(?:Long Description|Chất liệu gốc)\s*[:\-=\s]*([^\n]+)', "POPLIN FABRIC COTTON - SP26")

            m_col1, m_col2 = st.columns(2)
            with m_col1:
                st.markdown(f'<div class="meta-box-light-flat"><div class="meta-label-flat">Style Code / Mã hàng</div><div class="meta-value-flat"><b>{style_id}</b></div></div>', unsafe_allow_html=True)
                st.markdown(f'<div class="meta-box-light-flat"><div class="meta-label-flat">Customer / Đối tác</div><div class="meta-value-flat">{customer}</div></div>', unsafe_allow_html=True)
                st.markdown(f'<div class="meta-box-light-flat"><div class="meta-label-flat">Season / Mùa sản xuất</div><div class="meta-value-flat">{season}</div></div>', unsafe_allow_html=True)
            with m_col2:
                st.markdown(f'<div class="meta-box-light-flat"><div class="meta-label-flat">Garment Type / Kiểu dáng</div><div class="meta-value-flat">{short_desc}</div></div>', unsafe_allow_html=True)
                st.markdown(f'<div class="meta-box-light-flat"><div class="meta-label-flat">Material Spec / Mô tả vải</div><div class="meta-value-flat">{fabric_type[:25]}...</div></div>', unsafe_allow_html=True)
                st.markdown(f'<div class="meta-box-light-flat"><div class="meta-label-flat">Techpack Status</div><div class="meta-value-light" style="color: #16a34a; font-weight: bold;">🟢 READY TO BOM</div></div>', unsafe_allow_html=True)
        else:
            if st.session_state.pdf_bytes is None:
                st.markdown("<div style='margin-top: 20px; text-align: center; color: #64748b; font-size: 13px;'>Bảng tóm tắt hồ sơ trống. Vui lòng tải tài liệu lên hệ thống.</div>", unsafe_allow_html=True)

# --- CỘT PHẢI: KHÔNG GIAN HIỂN THỊ THÔNG TIN HÌNH ẢNH SKETCH ---
with col_right:
    with st.container(border=True, height=520):
        st.markdown("### 🎨 TECHPACK SKETCH VISUALIZER")
        
        # Hiển thị hình vẽ phác thảo nguyên bản mượt mà
        if "pdf_page_one_image" in st.session_state and st.session_state.pdf_page_one_image is not None:
            st.image(st.session_state.pdf_page_one_image, use_container_width=True)
        else:
            st.markdown("<div style='margin-top: 60px; text-align: center; color: #64748b; font-size: 13px;'>Chưa có hình ảnh phác thảo. Vui lòng tải Techpack PDF để trích xuất hệ thống.</div>", unsafe_allow_html=True)











# =====================================================================
# 🧠 KHỐI CHỨA HÀM CACHE AI CỐ ĐỊNH THÔNG SỐ RẬP (ĐẶT PHÍA TRÊN ĐOẠN 7a)
# =====================================================================
import streamlit as st
import google.generativeai as genai
import json, copy, re, fitz, traceback

@st.cache_data(show_spinner=False)
def execute_cached_gemini_scan(pdf_bytes, current_query, active_width, target_size_cmd, raw_json_schema, prompt_agent_2):
    """
    Hàm gọi AI quét PDF có sử dụng cơ chế Cache dữ liệu của Streamlit.
    Giúp cố định thông số 100% không đổi giữa các lần gõ chat hoặc tương tác nút bấm.
    """
    doc_recovery = fitz.open(stream=pdf_bytes, filetype="pdf")
    total_pages = len(doc_recovery)
    full_pdf_raw_text = ""
    image_payloads = []
    
    for idx in range(total_pages):
        page_text = doc_recovery[idx].get_text("text")
        full_pdf_raw_text += f"\n--- PAGE {idx + 1} ---\n{page_text}"
        
        if len(image_payloads) < 12:
            pix = doc_recovery[idx].get_pixmap(dpi=50, colorspace=fitz.csRGB)
            image_payloads.append({"mime_type": "image/jpeg", "data": pix.tobytes("jpeg")})
            
    gemini_inputs = copy.deepcopy(image_payloads)
    gemini_inputs.insert(0, f"=== USER CHAT COMMAND ===\n{current_query}\n\n=== TECHPACK TEXT ===\n{full_pdf_raw_text}\n")
    gemini_inputs.append(prompt_agent_2)

    model = genai.GenerativeModel('gemini-2.5-flash')
    response = model.generate_content(
        gemini_inputs,
        generation_config={
            "response_mime_type": "application/json",
            "response_schema": raw_json_schema,
            "temperature": 0.0  # 🌟 KHÓA CHẶT: Ép về 0.0 để triệt tiêu tính ngẫu nhiên, số liệu luôn đồng nhất
        }
    )
    
    blueprint_worker = json.loads(response.text)
    
    if blueprint_worker and "bom_rows" in blueprint_worker:
        blueprint_worker["calculated_on_size"] = target_size_cmd
        
        for row in blueprint_worker.get("bom_rows", []):
            # Chuẩn hóa chuỗi văn bản đầu vào để tránh lỗi khoảng trắng làm áp sai quy tắc IE
            if "component_name" in row:
                row["component_name"] = " ".join(str(row["component_name"]).upper().split())
                
            try: row["bounding_box_length"] = round(float(row.get("bounding_box_length", 0.0)), 2)
            except: row["bounding_box_length"] = 0.0
            
            try: row["bounding_box_width"] = round(float(row.get("bounding_box_width", 0.0)), 2)
            except: row["bounding_box_width"] = 0.0
            
            try: row["polygon_net_area"] = float(row.get("polygon_net_area", 0.0))
            except: row["polygon_net_area"] = 0.0
            
            try: row["piece_count"] = int(float(row.get("piece_count", 1)))
            except: row["piece_count"] = 1

            try:
                w_val = row.get("fabric_width_inch")
                if w_val is None or str(w_val).strip() == "" or float(w_val) <= 0.0:
                    row["fabric_width_inch"] = float(active_width)
                else:
                    row["fabric_width_inch"] = float(w_val)
            except:
                row["fabric_width_inch"] = float(active_width)
                
    return blueprint_worker
# =====================================================================
# ĐOẠN 7a - PHẦN 1 & 10: SINGLE-CALL PIPELINE CHỐNG TRÀO REQUEST (V125.0)
# 🌟 ĐỒNG BỘ TUYỆT ĐỐI VỚI THUẬT TOÁN SƠ ĐỒ TỔNG GERBER / LECTRA
# =====================================================================
st.markdown('<br><div class="cad-card"><div class="cad-header">💬 CHATGPT IE COLLABORATION WORKSPACE</div>', unsafe_allow_html=True)

if st.session_state.chat_history:
    for msg in st.session_state.chat_history:
        st.chat_message("user").write(msg["user"])
        st.chat_message("assistant").write(msg["ai"])

chat_input_container = st.container()
with chat_input_container:
    safe_user_prompt = st.chat_input("Gõ câu lệnh bất kỳ (Ví dụ: tính định mức cỡ 32)...", key="ie_workspace_static_chat_input_key")

st.markdown('</div>', unsafe_allow_html=True)

# BIỆN PHÁP CHẶN ĐỨNG VÒNG LẶP RERUN: Chỉ gọi AI khi có prompt thực sự phát sinh
if st.session_state.pdf_bytes is not None and safe_user_prompt:
    current_query = str(safe_user_prompt).strip()
    
    with st.spinner("🧠 AI Platform đang quét toàn bộ Techpack..."):
        try:
            chat_lower = current_query.lower()
            match_size = re.search(r'\b(?:size|sz|cỡ|co|cl)\s*[:\-=\s]*([\w\d/]+)\b', chat_lower)
            target_size_cmd = str(match_size.group(1)).upper().strip() if match_size else "32"
            
            match_w = re.search(r'(?:khổ|kho|width|w)\s*[:\-=\s]*([\d\.]+)', chat_lower)
            active_width = float(match_w.group(1)) if match_w else 56.0
            if active_width < 20.0 or active_width > 80.0: active_width = 56.0

            raw_json_schema = {
                "type": "OBJECT",
                "properties": {
                    "detected_product_type": {"type": "STRING", "description": "Kiểu dáng sản phẩm, ví dụ: CARGO_PANTS, JEANS"},
                    "detected_base_size": {"type": "STRING", "description": "Size mẫu/Size chuẩn trích xuất từ tài liệu"},
                    "spec_meta": {
                        "type": "OBJECT",
                        "properties": {
                            "warp_shrink": {"type": "NUMBER", "description": "Độ co rút dọc (%)"},
                            "weft_shrink": {"type": "NUMBER", "description": "Độ co rút ngang (%)"},
                            "gather_ratio": {"type": "NUMBER", "description": "Tỷ lệ nhún vải"},
                            "has_stripe": {"type": "BOOLEAN", "description": "True nếu vải có vân sọc, kẻ caro"},
                            "fabric_group": {"type": "STRING", "description": "Nhóm vải chính: DENIM, WOVEN, hoặc KNIT"}
                        },
                        "required": ["warp_shrink", "weft_shrink", "gather_ratio", "has_stripe", "fabric_group"]
                    },
                    "bom_rows": {
                        "type": "ARRAY",
                        "description": "Danh sách chi tiết rập trích xuất từ bảng BOM hoặc hình ảnh Sketch",
                        "items": {
                            "type": "OBJECT",
                            "properties": {
                                "component_name": {"type": "STRING", "description": "Tên chi tiết rập (FRONT PANEL, POCKET...)"},
                                "material_class": {"type": "STRING", "description": "Phân loại bắt buộc: FABRIC, LINING, FUSING, ELASTIC, THREAD"},
                                "uom": {"type": "STRING", "description": "Đơn vị tính từ bảng BOM: YDS, MTR, PCS"},
                                "piece_count": {"type": "INTEGER", "description": "Tổng số lượng chi tiết thực tế khi cắt sản xuất"},
                                "bounding_box_length": {"type": "NUMBER", "description": "Chiều dài rập thô chi tiết (L)"},
                                "bounding_box_width": {"type": "NUMBER", "description": "Chiều rộng rập thô chi tiết (W)"},
                                "fabric_width_inch": {"type": "NUMBER", "description": "Khổ rộng vật tư tương ứng trích xuất từ bảng BOM"}
                            },
                            "required": ["component_name", "material_class", "uom", "piece_count"]
                        }
                    }
                },
                "required": ["detected_product_type", "detected_base_size", "spec_meta", "bom_rows"]
            }

            prompt_agent_2 = f"""
            You are an Enterprise Apparel CAD Auditor.
            Task: Audit and extract ALL components from the Techpack context, drawings, BOM tables, and sketches.

            🌟 USER CHAT COMMAND CONTEXT (CRITICAL):
            You MUST extract numbers belonging to Size '{target_size_cmd}'. Update 'warp_shrink' and 'weft_shrink' exactly as requested here:
            "{current_query}"

            STRICT AUDIT & VISION RULES:
            - Scan all pages to extract valid numeric values for 'bounding_box_length' and 'bounding_box_width' for front/back panels. Do not leave them as 0.
            - For fabric_width_inch, extract specific values from BOM; if not specified, fallback to {active_width}.
            """

            # Gọi hàm bọc st.cache_data phía trên để lấy dữ liệu rập thô cố định từ tài liệu
            blueprint_worker = execute_cached_gemini_scan(
                st.session_state.pdf_bytes, 
                current_query, 
                active_width, 
                target_size_cmd, 
                raw_json_schema, 
                prompt_agent_2
            )
                
            if blueprint_worker and "bom_rows" in blueprint_worker:
                blueprint_worker["calculated_on_size"] = target_size_cmd
                
                # 🌟 ĐÃ SỬA CHÍ MẠNG: Chuẩn hóa sạch dữ liệu thô ngay trước khi đẩy vào bộ não sơ đồ tổng
                # Ép kiểu an toàn, tuyệt đối không chạy thuật toán nhân nhân/cộng dồn bừa bãi tại đây
                for row in blueprint_worker.get("bom_rows", []):
                    if "component_name" in row:
                        row["component_name"] = " ".join(str(row["component_name"]).upper().split())
                    try: row["bounding_box_length"] = float(row.get("bounding_box_length", 0.0))
                    except: row["bounding_box_length"] = 0.0
                    try: row["bounding_box_width"] = float(row.get("bounding_box_width", 0.0))
                    except: row["bounding_box_width"] = 0.0
                    try: row["piece_count"] = int(float(row.get("piece_count", 1)))
                    except: row["piece_count"] = 1
                    row["fabric_width_inch"] = float(active_width)
                
                # 🔥 ĐỒNG BỘ: Chuyển tiếp thẳng dữ liệu thô vào bộ não sơ đồ tổng gộp Gerber/Lectra
                if "allocate_fabric_consumption_and_quality_gate" in globals():
                    blueprint_final = allocate_fabric_consumption_and_quality_gate(
                        blueprint_worker, 
                        current_query=current_query
                    )
                else:
                    blueprint_final = blueprint_worker
                
                # Khóa chặt trạng thái vào session_state để Streamlit UI hiển thị lên màn hình
                st.session_state.blueprint_final = blueprint_final
                st.session_state.last_active_blueprint = blueprint_final
                
                # Ghi nhận phản hồi thành công vào lịch sử Chat
                total_extracted_pieces = len(blueprint_final.get("bom_rows", []))
                ai_response_text = (
                    f"✅ **Hệ thống Sơ đồ Tổng (Marker-Based) đã xử lý thành công!**\n\n"
                    f"📊 Đã gộp và phân bổ tỷ lệ diện tích phẳng cho **{total_extracted_pieces} chi tiết rập**.\n"
                    f"- Mã hàng: Định mức tính theo chiều dài dọc cây khung nền chuẩn.\n"
                    f"- Cỡ (Size): **{target_size_cmd}** | Khổ hữu dụng: **{active_width}\"**."
                )
                st.session_state.chat_history.append({"user": current_query, "ai": ai_response_text})
                
                # Ép làm mới giao diện ngay lập tức để giải phóng RAM và vẽ lại bảng số liệu tối ưu
                st.rerun()
                
        except Exception as e:
            st.error(f"❌ Pipeline Lỗi: {str(e)}")
            st.code(traceback.format_exc())


# =====================================================================
# ĐOẠN 7b - PHẦN 1: ĐỒNG BỘ DỮ LIỆU PIPELINE & BẢNG TỔNG HỢP SUMMARY
# =====================================================================
import pandas as pd
import re
import io
import copy
import streamlit as st
from openpyxl import Workbook

# 🌟 VÁ LỖI DÒNG 1264: Chốt chặn an toàn cho biến blueprint_final trước khi xử lý hiển thị
# =====================================================================
if 'blueprint_final' in locals() and blueprint_final is not None:
    if isinstance(blueprint_final, dict):
        total_extracted_pieces = len(blueprint_final.get("bom_rows", []))
    elif isinstance(blueprint_final, list):
        total_extracted_pieces = len(blueprint_final)
    else:
        total_extracted_pieces = 0
else:
    total_extracted_pieces = 0

# 1. ĐỒNG BỘ NGUỒN DỮ LIỆU TỪ PIPELINE SANG BỘ HIỂN THỊ GIAO DIỆN
# =====================================================================
# ĐOẠN 7b - MỤC 1: SỬA TRIỆT ĐỂ LỖI TRỒI SỤT - LÀM SẠCH BỘ NHỚ TẠM
# =====================================================================
if "last_active_blueprint" in st.session_state and st.session_state.last_active_blueprint:
    # 🔒 KHÓA BẢO VỆ: Luôn tạo một bản sao độc lập (Deepcopy) từ dữ liệu gốc của Techpack
    blueprint_worker = copy.deepcopy(st.session_state.last_active_blueprint)
    
    # Trích xuất văn bản câu lệnh chat mới nhất để lấy thông số khổ vải động
    chat_txt = ""
    if 'safe_user_prompt' in locals() and safe_user_prompt:
        chat_txt = str(safe_user_prompt).lower()
    elif "chat_history" in st.session_state and st.session_state.chat_history:
        chat_txt = str(st.session_state.chat_history[-1]["user"]).lower()
        
    match_active_size = re.search(r'\b(?:size|sz|cỡ)\s*[:\-=\s]*([\w\d/]+)\b', chat_txt)
    extracted_size = str(match_active_size.group(1)).upper().strip() if match_active_size else str(blueprint_worker.get("calculated_on_size", "30")).upper().strip()
    
    # Kích hoạt hàm Router để tính toán ma trận đường may từ rập gốc sạch
    if 'allocate_fabric_consumption_and_quality_gate' in globals():
        blueprint_processed = allocate_fabric_consumption_and_quality_gate(blueprint_worker, current_query=chat_txt)
    else:
        blueprint_processed = blueprint_worker

    # 🌟 CHỐT CHẶN VÁ LỖI AN TOÀN TUYỆT ĐỐI KHỬ ATTRIBUTEERROR KHI PIPELINE TRẢ VỀ NONE
    if blueprint_processed is None:
        blueprint_processed = {"bom_rows": [], "calculated_on_size": "30", "spec_meta": {}}

    # 🧹 BỘ LỌC LÀM SẠCH: Xóa bỏ hoàn toàn mảng cũ, ép bộ nhớ tạm ghi nhận dữ liệu mới tinh
    st.session_state["bom_data"] = blueprint_processed
    
    if isinstance(blueprint_processed, dict):
        st.session_state["accumulated_bom_rows"] = copy.deepcopy(blueprint_processed.get("bom_rows", []))
    elif isinstance(blueprint_processed, list):
        st.session_state["accumulated_bom_rows"] = copy.deepcopy(blueprint_processed)
    else:
        st.session_state["accumulated_bom_rows"] = []


# 2. KHỐI DEBUG MONITOR GIÁM SÁT PAYLOAD THÔ TỪ GEMINI
if "raw_ai_debug_payload" in st.session_state and st.session_state["raw_ai_debug_payload"]:
    with st.expander("🔍 [DEBUG MONITOR] XEM DỮ LIỆU THÔ CHƯA QUA TÍNH TOÁN DO AI (GEMINI) TRẢ VỀ"):
        st.json(st.session_state["raw_ai_debug_payload"])


# 3. KHỐI CHUYỂN ĐỔI SANG PANDAS DATAFRAME & HIỂN THỊ BẢNG GỘP MỦA HÀNG
if st.session_state.get("bom_data") or st.session_state.get("accumulated_bom_rows"):
    bom_source = st.session_state.get("bom_data", {})
    if not isinstance(bom_source, dict): bom_source = {}
    
    bom_rows_list = bom_source.get("bom_rows", st.session_state.get("accumulated_bom_rows", []))

    ai_meta_data = bom_source.get("spec_meta", {})
    if not isinstance(ai_meta_data, dict): ai_meta_data = {}
    
    current_warp_shrink = f"{ai_meta_data.get('warp_shrink', 3.0)}%"
    current_weft_shrink = f"{ai_meta_data.get('weft_shrink', 3.0)}%"
    
    if 'extracted_size' not in locals():
        extracted_size = str(bom_source.get("calculated_on_size", "30")).upper().strip()

    display_data = []
    
    for r in bom_rows_list:
        if not r or not isinstance(r, dict): continue
            
        current_gross = r.get("gross_consumption", r.get("Gross Consumption", 0.0))
        sys_notes = r.get("system_notes", r.get("Notes", "Mô phỏng CAD Gerber V27"))
        engine_target = str(r.get("engine", r.get("Material Class", "FABRIC"))).upper().strip()
        uom_display = str(r.get("uom", r.get("UOM", "YDS"))).upper().strip()

        b_len_val = r.get("bounding_box_length", r.get("Dài sản xuất (L-inch)", r.get("Dài sản xuất (L-Inch)", 0.0)))
        b_wid_val = r.get("bounding_box_width", r.get("Rộng sản xuất (W-inch)", r.get("Rộng sản xuất (W-Inch)", 0.0)))
        p_count_val = r.get("piece_count", r.get("Số lượng rập (Pcs)", 1))

        if engine_target in ["FABRIC", "LINING", "FUSING"]:
            raw_width = r.get("fabric_width_inch", r.get("Khổ vải (Width)", 57.0))
            cut_width_val = f"{float(raw_width)} inch" if isinstance(raw_width, (int, float)) else f"{raw_width} inch"
            warp_dynamic = current_warp_shrink
            weft_dynamic = current_weft_shrink
            eff_dynamic = r.get('marker_efficiency', r.get('Marker Efficiency', 0.87))
            if isinstance(eff_dynamic, (int, float)): 
                eff_dynamic = f"{round(eff_dynamic * 100, 1)}%" if eff_dynamic <= 1.0 else f"{eff_dynamic}%"
            else:
                eff_dynamic = f"{eff_dynamic}"
        else:
            cut_width_val = "N/A (Linear/Count)"
            warp_dynamic = "-"
            weft_dynamic = "-"
            eff_dynamic = "-"

        display_data.append({
            "Component Name": r.get("component_name", r.get("Component Name", "Unnamed Material")),
            "Material Class": r.get("material_class", engine_target).upper().strip(),
            "UOM": uom_display,
            "Số lượng rập (Pcs)": p_count_val,
            "Dài sản xuất (L-Inch)": b_len_val,
            "Rộng sản xuất (W-Inch)": b_wid_val,
            "Khổ vải (Width)": cut_width_val,
            "Co rút dọc (% Warp)": warp_dynamic,     
            "Co rút ngang (% Weft)": weft_dynamic,   
            "Marker Efficiency": eff_dynamic,         
            "Gross Consumption": float(current_gross),
            "Quality Status": r.get("quality_status", r.get("Quality Status", "PASS")),
            "System Calculation Notes": sys_notes
        })
        
    if display_data:
        df_bom = pd.DataFrame(display_data)
        
        # GIAO DIỆN BẢNG GỘP TỔNG ĐỊNH MỨC NGUYÊN LIỆU MUA HÀNG (SUMMARIZED BOM)
        st.markdown('<div class="cad-card">', unsafe_allow_html=True)
        st.markdown(f'<div class="cad-header" style="background-color: #27AE60;">📦 SUMMARY: TỔNG HỢP ĐỊNH MỨC NGUYÊN LIỆU PHẲNG (SIZE: {extracted_size})</div>', unsafe_allow_html=True)
        
        df_bom_fix_uom = df_bom.copy()
        df_bom_fix_uom.loc[df_bom_fix_uom["Material Class"].isin(["FABRIC", "LINING", "FUSING"]), "UOM"] = "YDS"
        
        df_summary = df_bom_fix_uom.groupby(["Material Class", "UOM"], as_index=False).agg({
            "Gross Consumption": "sum"
        })
        df_summary["Gross Consumption"] = df_summary["Gross Consumption"].round(4)
        df_summary["Trạng thái"] = "READY TO BUY"
        
        class_mapping = {
            "FABRIC": "VẢI CHÍNH (MAIN FABRIC)", 
            "LINING": "VẢI LÓT TÚI (POCKETING LINING)", 
            "FUSING": "KEO LÓT / DỰNG (INTERLINING)"
        }
        df_summary["Material Class"] = df_summary["Material Class"].map(lambda x: class_mapping.get(x, x))
        
        st.dataframe(df_summary, use_container_width=True, hide_index=True)
        st.markdown('</div><br>', unsafe_allow_html=True)
        
        # GIAO DIỆN BẢNG CHI TIẾT ĐỐI CHIẾU RẬP CAD (DETAILED CAD PIECES MATRIX)
        st.markdown('<div class="cad-card">', unsafe_allow_html=True)
        st.markdown(f'<div class="cad-header">📐 DETAILED CAD PIECES MATRIX (SƠ ĐỒ CHI TIẾT RẬP ĐÃ BÙ LAI & ĐƯỜNG MAY)</div>', unsafe_allow_html=True)
        st.dataframe(df_bom, use_container_width=True, hide_index=True)
        st.markdown('</div>', unsafe_allow_html=True)
        
    else:
        st.warning("⚠️ Hệ thống đã xử lý xong nhưng cấu trúc danh mục BOM trống dữ liệu thực tế.")

    # 6. KHỐI BẰNG CHỨNG SỐ ĐO GỐC TRÍCH XUẤT TỪ TECHPACK (VÁ CÚ PHÁP HOÀN CHỈNH)
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
                "Mã POM": pom_code,
                "Mô tả vị trí kiểm tra": description,
                "Thông số gốc": measurement_val
            })
        if parsed_evidence_rows:

            st.dataframe(pd.DataFrame(parsed_evidence_rows), use_container_width=True, hide_index=True)
        st.markdown('</div>', unsafe_allow_html=True)
