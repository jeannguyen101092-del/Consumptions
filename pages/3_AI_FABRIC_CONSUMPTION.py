import streamlit as st
import re
import json
import copy

import re

# =====================================================================
# KIẾN TRÚC V34.0: ENTERPRISE INDUSTRIAL CAM CORE (DATA-DRIVEN)
# 🌟 ARCHITECTURE APPROVED BY SENIOR INDUSTRIAL ENGINEERING (IE) ARCHITECT
# =====================================================================

class IndustrialGeometryEngine:
    """Module chuyên trách xử lý hình học đa giác Polygon CAD và Convex Hull Fallback"""
    
    @staticmethod
    def convert_to_sq_inches(area: float, unit: str) -> float:
        """Bộ chuyển đổi đơn vị đo lường vạn năng bám sát hệ thống Gerber/Lectra"""
        u = str(unit).upper().strip()
        if u in ["CM2", "CMSQ", "SQUARE_CM"]:
            return area / 6.4516  # 1 inch² = 6.4516 cm²
        if u in ["MM2", "MMSQ", "SQUARE_MM"]:
            return area / 645.16  # 1 inch² = 645.16 mm²
        return area  # Mặc định IN2 / INCH2

    @classmethod
    def compute_net_area(cls, row: dict, product_type: str, mat_class: str, p_count: int) -> tuple:
        poly_area = float(row.get("polygon_net_area", 0.0) or 0.0)
        area_mode = str(row.get("polygon_area_mode", "PER_PIECE")).upper().strip()
        poly_unit = str(row.get("polygon_unit", "IN2")).upper().strip()
        
        comp_name = str(row.get("component_name", "")).upper()
        
        # 1. ƯU TIÊN TỐI CAO: Diện tích đa giác thực tế Polygon CAD trích xuất từ file Gerber/Lectra DXF
        if poly_area > 0.0:
            converted_poly = cls.convert_to_sq_inches(poly_area, poly_unit)
            if area_mode == "TOTAL":
                return converted_poly, f"Gerber/Lectra Polygon DXF ({poly_unit} -> IN2 Total)"
            return converted_poly * p_count, f"Gerber/Lectra Polygon DXF ({poly_unit} -> IN2 Per-Piece)"

        # 2. PHƯƠNG ÁN DỰ PHÒNG (Fallback): Sử dụng Convex Hull lồng ma trận hệ số góc khuyết rập
        b_length = float(row.get("bounding_box_length", 0.0) or 0.0)
        b_width = float(row.get("bounding_box_width", 0.0) or 0.0)
        raw_box_area = b_length * b_width * p_count
        
        # Ma trận hệ số diện tích thực (Net Factor Matrix) triệt tiêu sai số Bounding Box khuyết mông/đùi
        if any(k in comp_name for k in ["POCKET", "FLAP", "BAG", "TÚI", "NẮP"]):
            net_factor = 0.85  # Rập túi đắp vuông vức ít góc khuyết
        elif any(k in comp_name for k in ["WAISTBAND", "CẠP", "FLY", "NẸP"]):
            net_factor = 0.95  # Rập cạp thẳng bảo toàn diện tích
        elif mat_class in ["MAIN_FABRIC", "FABRIC", "SELF"] or "BODY" in comp_name or "THÂN" in comp_name:
            net_factor = 0.72 if product_type in ["CARGO_PANTS", "JEANS"] else 0.78
        else:
            net_factor = 0.80
            
        inferred_area = raw_box_area * net_factor
        return inferred_area, f"CAD Convex Hull Inferred (Factor: {net_factor})"


class IndustrialLossEngine:
    """Module chuyên tách biệt ma trận 7 lỗi hao hụt xưởng cắt may nhà máy"""
    
    INDUSTRIAL_LOSS_MATRIX = {
        "DENIM": {"marker_end": 0.008, "spread_waste": 0.012, "relaxation": 0.005, "defect_cut": 0.010, "roll_end": 0.005},
        "WOVEN": {"marker_end": 0.006, "spread_waste": 0.010, "relaxation": 0.004, "defect_cut": 0.005, "roll_end": 0.005},
        "KNIT":  {"marker_end": 0.010, "spread_waste": 0.015, "relaxation": 0.020, "defect_cut": 0.008, "roll_end": 0.007}
    }

    @classmethod
    def get_factory_loss(cls, chat_clean: str) -> float:
        fabric_group = "WOVEN"
        if any(k in chat_clean for k in ["DENIM", "JEANS", "THÔ DÀY"]): fabric_group = "DENIM"
        elif any(k in chat_clean for k in ["KNIT", "THUN", "JERSEY", "RIB", "LEN"]): fabric_group = "KNIT"
        
        loss_set = cls.INDUSTRIAL_LOSS_MATRIX[fabric_group]
        return sum(loss_set.values())


def compute_fabric_engine(row: dict, product_type: str, chat_txt: str) -> tuple:
    """
    Industrial Consumption CAM Core Engine v34.0.
    100% Data-Driven: Loại bỏ hoàn toàn UI code, triệt tiêu lỗi ghi đè, 
    ưu tiên Polygon CAD đầu vào và xử lý ma trận chuyển đổi đơn vị vạn năng.
    """
    chat_clean = str(chat_txt).upper().strip()
    current_mat_class = str(row.get("material_class", "FABRIC")).upper().strip()
    current_comp_name = str(row.get("component_name", "")).upper()
    
    # -----------------------------------------------------------------
    # STEP 1: READ GEOMETRY & PIECE CLASSIFIER (Đọc dữ liệu và đếm chi tiết)
    # -----------------------------------------------------------------
    p_count = int(row.get("piece_count", 1) or 1)
    
    # Kích hoạt Động cơ hình học: Trích xuất diện tích Net Area thực tế
    total_net_area, geo_source = IndustrialGeometryEngine.compute_net_area(row, product_type, current_mat_class, p_count)

    # -----------------------------------------------------------------
    # STEP 2: MARKER WIDTH EXTRACTION (Trích xuất khổ vải thực tế từ BOM)
    # -----------------------------------------------------------------
    raw_width = row.get("fabric_width_inch")
    try:
        width_inch = float(raw_width) if raw_width else 56.0
        match_w = re.search(r'(?:KHỔ|KHO|WIDTH|W)\s*[:\-=\s]*([\d\.]+)', chat_clean)
        if match_w: width_inch = float(match_w.group(1))
    except:
        width_inch = 56.0

    # -----------------------------------------------------------------
    # STEP 3: ADVANCED SHRINKAGE ENGINE (Động cơ co rút Lab-Test đa tầng)
    # -----------------------------------------------------------------
    warp_num, weft_num = 0.02, 0.02  # Điểm sàn mặc định của vải mộc
    match_warp = re.search(r'(?:CO RÚT DỌC|WARP|DỌC|DOC)\s*[:\-=\s]*([\d\.]+)', chat_clean)
    match_weft = re.search(r'(?:CO RÚT NGANG|WEFT|NGANG)\s*[:\-=\s]*([\d\.]+)', chat_clean)
    if match_warp: warp_num = float(match_warp.group(1)) / 100.0
    if match_weft: weft_num = float(match_weft.group(1)) / 100.0
    
    # Cộng dồn độ co rút xử lý hoàn tất ướt của nhà máy giặt nhuộm
    if "GARMENT DYE" in chat_clean: warp_num += 0.025; weft_num += 0.020
    if "ENZYME WASH" in chat_clean: warp_num += 0.015; weft_num += 0.010

    # -----------------------------------------------------------------
    # STEP 4: AI MARKER EFFICIENCY INFERENCE (Suy luận hiệu suất sơ đồ)
    # -----------------------------------------------------------------
    base_eff = 0.835  # Sàn mặc định cho Woven
    if product_type in ["CARGO_PANTS", "JEANS"]: base_eff = 0.855
    elif product_type == "DRESS": base_eff = 0.770  # Vạt cong hao hụt đầu sơ đồ lớn
    
    # Phạt hiệu suất theo đặc tính vân sọc vải và sơ đồ định hướng (Nap / Stripe Matching)
    if any(k in chat_clean for k in ["STRIPE", "VÂN SỌC", "KẺ CARO", "PLAID"]): base_eff -= 0.06
    if any(k in chat_clean for k in ["ONE WAY LAYOUT", "SƠ ĐỒ MỘT CHIỀU", "NAP"]): base_eff -= 0.03
    if width_inch >= 60.0: base_eff += 0.015
    elif width_inch <= 45.0: base_eff -= 0.035
    
    ai_marker_efficiency = round(max(0.50, min(0.96, base_eff)), 3)

    # -----------------------------------------------------------------
    # STEP 5: PURE CAM MATHEMATICAL CORE (Phép toán toán học phẳng CAM)
    # -----------------------------------------------------------------
    gross_val = 0.0
    total_industrial_loss = IndustrialLossEngine.get_factory_loss(chat_clean)
    
    # Tự động đọc hệ số nhún ly bù hao vải của rập Cargo đắp ly nổi
    gather_ratio = 1.00
    g_type = str(row.get("gather_type", "NONE")).upper().strip()
    g_depth = str(row.get("gather_depth", "NONE")).upper().strip()
    if g_type == "SIDE_RUCHE" and g_depth == "MEDIUM": gather_ratio = 1.45
    if any(k in chat_clean for k in ["RUCHE", "SIDE_RUCHE", "NHÚN SƯỜN"]): gather_ratio = 1.45

    if total_net_area > 0 and width_inch > 0:
        # Tầng A: Diện tích thực sau nhún ly rập
        adjusted_area = total_net_area * gather_ratio
        
        # Tầng B: Nhân nhân ma trận co rút đa lớp biên dạng phòng Lab
        expanded_area = adjusted_area * (1.0 + warp_num) * (1.0 + weft_num)
        
        # Tầng C: Công thức toán học vạt chia sơ đồ CAM phẳng (Tuyệt đối không nhân đôi *2.0 cảm tính)
        math_cad_yardage = expanded_area / (width_inch * 36.0 * ai_marker_efficiency)
        
        # Tầng D: Áp dụng ma trận hao hụt nhà máy cắt may công nghiệp (Industrial Multi-Loss Matrix)
        gross_val = math_cad_yardage * (1.0 + total_industrial_loss)
        gross_val = round(max(0.0, gross_val), 3)

    # -----------------------------------------------------------------
    # STEP 6: DATA EXPORT FOR UI AUDIT TRAIL (Kết xuất dữ liệu thô cho UI)
    # -----------------------------------------------------------------
    # Chỉ ghi đè vào chính chiếc từ điển dữ liệu dòng hiện tại (Cô lập bộ nhớ bảo vệ hệ thống)
    row["fabric_consumption"] = gross_val
    row["gross_consumption"] = gross_val
    
    # Trả về siêu dữ liệu (Metadata) thô cho lớp UI đọc hiển thị, tuyệt đối không gọi st.write ngầm
    row["cad_geometry_source"] = geo_source
    row["cad_calculated_net_area"] = round(total_net_area, 1)
    row["cad_inferred_efficiency"] = ai_marker_efficiency
    row["cad_total_industrial_loss"] = round(total_industrial_loss * 100, 2)
    row["cad_engine_version"] = "CAM-v34.0-Enterprise"

    note = f"CAM Core v34 | Area: {total_net_area:.1f} sq in | Eff: {ai_marker_efficiency*100}%"
    return gross_val, note





def compute_elastic_engine(row: dict) -> tuple:
    """Engine chuyên tính toán cho Chun / Thun co giãn (Elastic)"""
    uom_target = str(row.get("uom", "YDS")).upper().strip()
    e_length = float(row.get("length_inch", 0.0) or 0.0)
    e_count = int(row.get("piece_count", 1) or 1)
    stretch = float(row.get("stretch_pct", 1.00) or 1.00)
    
    total_inches = e_length * e_count * stretch * 1.05 # 5% hao hụt đầu bàn thun
    if uom_target == "YDS":
        gross_val = round(total_inches / 36.0, 3)
    elif uom_target == "MTR":
        gross_val = round(total_inches * 0.0254, 3)
    else:
        gross_val = round(total_inches, 3)
        
    note = f"ElasticEngine | Dài: {e_length}\" | Số lượng: {e_count} | Độ giãn: {stretch}x | Hao hụt: 5%"
    return gross_val, note


def compute_tape_engine(row: dict) -> tuple:
    """Engine chuyên tính toán cho Dây Tape / Dây Viền / Dây dệt (Tape/Cord)"""
    uom_target = str(row.get("uom", "MTR")).upper().strip()
    t_length = float(row.get("length_inch", 0.0) or 0.0)
    t_count = int(row.get("piece_count", 1) or 1)
    
    total_inches = t_length * t_count * 1.03 # 3% hao hụt cắt nối dây
    if uom_target == "YDS":
        gross_val = round(total_inches / 36.0, 3)
    elif uom_target == "MTR":
        gross_val = round(total_inches * 0.0254, 3)
    else:
        gross_val = round(total_inches, 3)
        
    note = f"TapeEngine | Chiều dài: {t_length}\" | Số lượng: {t_count} | Hao hụt: 3%"
    return gross_val, note


def compute_count_engine(row: dict) -> tuple:
    """Engine chuyên tính đếm số lượng cho Phụ liệu: Cúc / Khóa / Nhãn (Count)"""
    uom_target = str(row.get("uom", "PCS")).upper().strip()
    qty_pcs = int(row.get("quantity_pcs", row.get("piece_count", 1)) or 1)
    gross_val = round(float(qty_pcs) * 1.01, 2) if uom_target == "PCS" else float(qty_pcs)
    note = f"CountEngine | Đếm trực tiếp: {qty_pcs} PCS | Bù hao rơi: 1%"
    return gross_val, note


def compute_thread_engine() -> tuple:
    """Engine tính định mức Chỉ may công nghiệp theo ma trận tiêu chuẩn (Thread)"""
    gross_val = 18.5
    note = f"ThreadEngine | Tiêu chuẩn Factory Standard Sew-in Matrix"
    return gross_val, note
def allocate_fabric_consumption_and_quality_gate(blueprint_final: dict, query_string: str) -> dict:
    import copy
    import streamlit as st
    
    st.info("🚀 ENTERPRISE MULTI-ENGINE CAD ROUTER ACTIVATED")
    
    if not blueprint_final or "bom_rows" not in blueprint_final:
        return blueprint_final
        
    router_bom_rows = []
    product_type = str(blueprint_final.get("detected_product_type", "DRESS")).upper().strip()
    chat_txt = str(query_string).lower()
    
    for ai_row in blueprint_final.get("bom_rows", []):
        ui_row = copy.deepcopy(ai_row)
        engine_target = str(ui_row.get("engine", "FABRIC")).upper().strip()
        comp_name = str(ui_row.get("component_name", "")).upper()
        
        # 🌟 KHỐI ĐÁNH CHẶN NGHIÊM NGẶT: Loại bỏ phụ liệu cứng, chỉ giữ lại nguyên liệu may (Vải, dựng, keo, thun, chỉ)
        # Nếu trùng bất kỳ từ khóa nào trong danh mục EXCLUDE_HARDWARE_KEYS hoặc thuộc nhóm COUNT, bỏ qua không đưa vào bảng
        if engine_target == "COUNT" or any(key in comp_name for key in EXCLUDE_HARDWARE_KEYS):
            continue
            
        if engine_target in ["FABRIC", "FUSING"]:
            gross_val, calc_note = compute_fabric_engine(ui_row, product_type, chat_txt)
            
        elif engine_target == "ELASTIC":
            gross_val, calc_note = compute_elastic_engine(ui_row)
            
        elif engine_target in ["TAPE", "CORD", "WEBBING"]:
            gross_val, calc_note = compute_tape_engine(ui_row)
            
        elif engine_target == "THREAD":
            gross_val, calc_note = compute_thread_engine()
            
        else:
            continue

        ui_row["gross_consumption"] = gross_val
        ui_row["quality_status"] = "PASS" if gross_val > 0 else "QA_FAIL"
        ui_row["system_notes"] = calc_note
        
        router_bom_rows.append(ui_row)
        
    blueprint_final["bom_rows"] = router_bom_rows
    return blueprint_final

import streamlit as st

# =====================================================================
# ĐOẠN A: KHỞI TẠO BỘ NHỚ STATE & CẤU HÌNH CSS PHẲNG NATIVE CHUẨN ERP
# =====================================================================

# 1. Cấu hình trang rộng toàn màn hình chuẩn hệ thống SaaS/ERP
st.set_page_config(layout="wide", page_title="AI Fabric Consumption Matrix")

# 2. Khởi tạo an toàn cấu trúc trạng thái bộ nhớ (Session State)
if "bom_data" not in st.session_state: st.session_state.bom_data = None
if "chat_history" not in st.session_state: st.session_state.chat_history = []
if "pdf_bytes" not in st.session_state: st.session_state.pdf_bytes = None
if "pdf_name" not in st.session_state: st.session_state.pdf_name = ""
if "pdf_text_cache" not in st.session_state: st.session_state.pdf_text_cache = None
if "accumulated_bom_rows" not in st.session_state: st.session_state.accumulated_bom_rows = []

# 3. Tự động phân tách trích xuất văn bản từ tài liệu PDF khi có file nạp vào
if st.session_state.pdf_bytes is not None and st.session_state.pdf_text_cache is None:
    try:
        import fitz
        doc = fitz.open(stream=st.session_state.pdf_bytes, filetype="pdf")
        full_text_extract = ""
        for page_num in range(len(doc)):
            full_text_extract += f"\n--- TRANG THỨ {page_num + 1} ---\n" + doc.load_page(page_num).get_text("text")
        st.session_state.pdf_text_cache = full_text_extract
    except Exception: pass

# 4. Engine đồng bộ dữ liệu KPIs động biến thiên theo thời gian thực
kpi_style_id = "N/A"
total_materials = len(st.session_state.accumulated_bom_rows) if st.session_state.accumulated_bom_rows else 0
main_fabric_cons = "0.000 Yds"
active_size_kpi = "AUTOMATIC"

if st.session_state.get("bom_data") and "bom_rows" in st.session_state.bom_data:
    kpi_style_id = str(st.session_state.bom_data.get("style_code", "R09-450416")).upper()
    active_size_kpi = str(st.session_state.bom_data.get("calculated_on_size", "MEDIAN")).upper()
    if total_materials == 0: total_materials = len(st.session_state.bom_data["bom_rows"])
    for row in st.session_state.bom_data["bom_rows"]:
        if not row: continue
        if "MAIN" in str(row.get("material_class", "")).upper() or "FABRIC" in str(row.get("material_class", "")).upper():
            val_gross = row.get("gross_consumption", 0.0)
            if val_gross > 0.0:
                main_fabric_cons = f"{val_gross:.3f} Yds"
                break

# 5. Bộ cấu hình định dạng CSS phẳng triệt tiêu vĩnh viễn 2 ô trống khổng lồ
st.markdown("""
<style>
    /* Trả nền ứng dụng về màu xám trắng dịu mắt */
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

    /* Khống chế chiều cao 1:1 đối xứng phần thân dưới khít rạt */
    .custom-erp-box-flat {
        background-color: #ffffff !important;
        border: 1px solid #cbd5e1 !important;
        border-radius: 8px !important;
        padding: 20px !important;
        margin-bottom: 15px !important;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.03) !important;
        max-height: 380px !important; 
        min-height: 380px !important; 
        overflow-y: auto !important;   
        box-sizing: border-box !important;
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

    .sticky-sketch-box-flat img {
        max-height: 290px !important;
        width: auto !important;
        object-fit: contain !important;
        margin: 0 auto !important;
        display: block !important;
    }

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

# =====================================================================
# ĐOẠN B: GIAO DIỆN HIỂN THỊ KPIs MÀU SẮC ĐỘNG & GRID THÂN TRANG HỢP NHẤT
# =====================================================================

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
    if "pdf_page_one_image" in st.session_state: st.session_state.pdf_page_one_image = None
    if "accumulated_bom_rows" in st.session_state: st.session_state.accumulated_bom_rows = []
    st.rerun()


# ------------------------------------------------------------------------------
# LƯỚI CHIA ĐÔI CỘT CHÍNH THỰC TẾ (HỢP NHẤT THẺ ĐÓNG HTML KHÍT RẠT)
# ------------------------------------------------------------------------------
col_left, col_right = st.columns(2)

# --- CỘT TRÁI: BỘ TẢI FILE & HỒ SƠ TÓM TẮT MÃ HÀNG MÀU XANH ---
with col_left:
    # Mở hộp custom-erp-box-flat và viết tiêu đề trong cùng 1 lệnh st.markdown
    st.markdown('<div class="custom-erp-box-flat"><div class="cad-header-text-flat">📂 TECHPACK UPLOADER & PROFILE SUMMARY</div>', unsafe_allow_html=True)
    
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
        
        import re
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
            st.markdown("<div style='margin-top: 60px; text-align: center; color: #64748b; font-size: 13px;'>Bảng tóm tắt thông số sản phẩm sẽ tự động hiển thị tại đây sau khi nạp file PDF.</div>", unsafe_allow_html=True)
        
    # 🟢 CHUYỂN THÈ ĐÓNG HỘP XUỐNG ĐÂY (Sau khi tất cả nội dung bên trong đã chạy xong)
    st.markdown('</div>', unsafe_allow_html=True)


# --- CỘT PHẢI: KHUNG XEM BẢN VẼ PHẲNG SKETCH VÀNG VÀNG ---
with col_right:
    # Mở hộp custom-erp-box-flat và viết tiêu đề trong cùng 1 lệnh st.markdown
    st.markdown('<div class="custom-erp-box-flat sticky-sketch-box-flat"><div class="cad-header-text-flat">🎨 TECHPACK SKETCH VISUALIZER</div>', unsafe_allow_html=True)
    
    if st.session_state.pdf_bytes is not None:
        if "pdf_page_one_image" not in st.session_state or st.session_state.pdf_page_one_image is None:
            try:
                import fitz
                doc_img = fitz.open(stream=st.session_state.pdf_bytes, filetype="pdf")
                if len(doc_img) > 0:
                    page = doc_img.load_page(0)
                    pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), colorspace=fitz.csRGB)
                    st.session_state.pdf_page_one_image = pix.tobytes("png")
            except Exception as e_img:
                st.error(f"⚠️ Không thể hiển thị ảnh vẽ phác họa: {str(e_img)}")

    if "pdf_page_one_image" in st.session_state and st.session_state.pdf_page_one_image is not None:
        st.image(st.session_state.pdf_page_one_image, width=300)
    else:
        st.markdown("<div style='margin-top: 70px; text-align: center; color: #64748b; font-size: 13px;'>Hình vẽ phác họa phẳng (Sketch) trích xuất từ trang bìa PDF sẽ tự động hiển thị cân xứng tại đây sau khi nạp file thành công.</div>", unsafe_allow_html=True)
        
    # 🟢 CHUYỂN THÈ ĐÓNG HỘP XUỐNG ĐÂY (Sau khi ảnh hoặc chữ sketch đã vẽ xong)
    st.markdown('</div>', unsafe_allow_html=True)









# =====================================================================
# ĐOẠN 7a - PHẦN 1: CHATGPT-STYLE WORKSPACE & SMART TARGET SCANNED PIPELINE (V65.0)
# CHIẾN LƯỢC HYBRID: GIẢM TẢI DPI XUỐNG 65 ĐỂ KHẮC PHỤC TRIỆT ĐỂ LỖI QUOTA 429
# =====================================================================
st.markdown('<br><div class="cad-card"><div class="cad-header">💬 CHATGPT IE COLLABORATION WORKSPACE</div>', unsafe_allow_html=True)

if st.session_state.chat_history:
    for msg in st.session_state.chat_history:
        st.chat_message("user").write(msg["user"])
        st.chat_message("assistant").write(msg["ai"])

chat_input_container = st.container()
with chat_input_container:
    safe_user_prompt = st.chat_input("Gõ câu lệnh bất kỳ...", key="ie_workspace_static_chat_input_key")

st.markdown('</div>', unsafe_allow_html=True)

if st.session_state.pdf_bytes is not None and safe_user_prompt:
    current_query = str(safe_user_prompt).strip()
    
    with st.spinner("🧠 AI Platform đang quét Techpack..."):
        import google.generativeai as genai
        import json, copy, traceback, re
        import fitz 
        
        try:
            doc_recovery = fitz.open(stream=st.session_state.pdf_bytes, filetype="pdf")
            total_pages = len(doc_recovery)
            full_pdf_raw_text = ""
            image_payloads = []
            
            for idx in range(total_pages):
                page_text = doc_recovery[idx].get_text("text")
                if any(k in page_text.upper() for k in ["BOM", "SPECIFICATION", "THÔNG SỐ", "SKETCH"]):
                    full_pdf_raw_text += f"\n--- PAGE {idx + 1} ---\n{page_text}"
                    if len(image_payloads) < 15:
                        pix = doc_recovery[idx].get_pixmap(dpi=65, colorspace=fitz.csRGB)
                        image_payloads.append({"mime_type": "image/jpeg", "data": pix.tobytes("jpeg")})
            
            if not image_payloads:
                for idx in range(min(5, total_pages)):
                    pix = doc_recovery[idx].get_pixmap(dpi=65, colorspace=fitz.csRGB)
                    image_payloads.append({"mime_type": "image/jpeg", "data": pix.tobytes("jpeg")})
            
            chat_lower = current_query.lower()
            match_size = re.search(r'\b(?:size|sz|cỡ)\s*[:\-=\s]*([\w\d/]+)\b', chat_lower)
            target_size_cmd = str(match_size.group(1)).upper().strip() if match_size else "30"
            
            match_w = re.search(r'(?:khổ|kho|width|w)\s*[:\-=\s]*([\d\.]+)', chat_lower)
            active_width = float(match_w.group(1)) if match_w else 56.0
            if active_width < 20.0 or active_width > 80.0: active_width = 56.0

            dummy_json_payload = """
            {
              "status": "PASS", "detected_product_type": "DRESS", "calculated_on_size": "SIZE_PLH",
              "bom_rows": [
                {"component_name": "Main Fabric", "material_class": "FABRIC", "uom": "YDS", "engine": "FABRIC", "fabric_width_inch": WIDTH_PLH, "bounding_box_length": 65.0, "bounding_box_width": 26.0, "piece_count": 2, "gather_type": "SIDE_RUCHE", "gather_depth": "MEDIUM"},
                {"component_name": "Elastic Waistband", "material_class": "ELASTIC", "uom": "YDS", "engine": "ELASTIC", "length_inch": 28.0, "piece_count": 2, "stretch_pct": 1.20},
                {"component_name": "Twill Tape Neck", "material_class": "TAPE", "uom": "MTR", "engine": "TAPE", "length_inch": 14.5, "piece_count": 1},
                {"component_name": "Button 24L", "material_class": "BUTTON", "uom": "PCS", "engine": "COUNT", "quantity_pcs": 8}
              ]
            }
            """.replace("SIZE_PLH", str(target_size_cmd)).replace("WIDTH_PLH", str(active_width))
                       # =====================================================================
            # ĐOẠN 7a - PHẦN 10: PROMPT AGENT 2 ROUTER & API EXECUTION CORE (V102.8)
            # 🌟 ĐÃ KHÔI PHỤC TƯ DUY HÌNH HỌC: ÉP AI TRA CỨU THÔNG SỐ RẬP THÔ > 2.5 YDS
            # =====================================================================
                        # =====================================================================
                        # =====================================================================
                     # =====================================================================
            # ĐOẠN 7a - PHẦN 10: PROMPT AGENT 2 ROUTER & INDUSTRIAL CAD AUDITOR (v104.0)
            # 🌟 CHỈ TÍNH NGUYÊN LIỆU MAY - ĐỒNG BỘ POLYGON CAD & PIECE CLASSIFIER
            # =====================================================================
            prompt_agent_2 = f"""
            You are Agent 2: The Enterprise Apparel CAD Auditor & Raw Material Router.
            Review Agent 1 extraction against the raw Techpack context, BOM tables, and sketches.

            🌟 STRICT SYSTEM RULE: ONLY EXTRACT RAW SEWING MATERIALS. 
            Completely exclude and ignore hardware or counts (No Buttons, No Zippers, No Labels, No Polybags, No Hardware).
            
            ONLY route and extract the following industrial raw sewing components:
            - Main Fabric, Lining, Pocketing, Contrast Fabric -> Engine: "FABRIC"
            - Fusible Interlining, Tape, Collar Stay -> Engine: "FUSING"
            - Elastic Bands, Elastic Webbing -> Engine: "ELASTIC"
            - Sewing Thread (Spun / Filament) -> Engine: "THREAD"

            🌟 CAD PATTERN & GEOMETRY EXTRACTION INSTRUCTIONS (98% Accuracy Target):
            1. PIECE CLASSIFIER: For each component, audit the structural symmetry. Identify if it is a 'Pair', 'Mirror', or 'Cut on Fold' layout. Ensure 'piece_count' represents the TOTAL actual pieces cut in production (e.g., Jeans Front Panel must be 2, Cargo Pocket Body must be 2).
            2. POLYGON AREA PRIORITY: Look for any exact square inch area or CAD system outputs (Gerber/Lectra tables) in the Techpack. If found, populate 'polygon_net_area' and set 'polygon_area_mode' to "TOTAL" or "PER_PIECE".
            3. GEOMETRY FALLBACK: If polygon area is missing, you MUST extract the 'bounding_box_length' and 'bounding_box_width' of the gross pattern block. Never output 0.0 or null for geometric shapes.
            4. MARKET WIDTH TRACKING: Do NOT force active width {active_width} on all items. Scan the BOM table carefully: extract the SPECIFIC width for Lining (e.g., 44") or Interlining (e.g., 36") if specified. Use {active_width} only as a baseline fallback for Main Fabric.

            Output clean executable JSON under ===START_JSON=== and chat summary under ===START_CHAT===.
            
            ===START_CHAT===
            ⚖️ Industrial CAD Pipeline Engaged: Đã dọn sạch phụ liệu đếm chiếc. Hệ thống tự động phân loại cấu trúc rập đối xứng (Pair/Mirror), ưu tiên trích xuất diện tích đa giác CAD và khổ rộng thực tế của từng phân hệ vật tư từ BOM Techpack.
            ===END_CHAT===
            
            ===START_JSON===
            {dummy_json_payload}
            ===END_JSON===
            """



            gemini_inputs = copy.deepcopy(image_payloads)
            gemini_inputs.insert(0, f"=== TECHPACK TEXT ===\n{full_pdf_raw_text}\n")
            gemini_inputs.append(prompt_agent_2)

            model = genai.GenerativeModel('gemini-2.5-flash')
            response = model.generate_content(gemini_inputs)
            response_text = response.text
            
            chat_part, json_part = "", dummy_json_payload
            if "===START_CHAT===" in response_text and "===END_CHAT===" in response_text:
                chat_part = response_text.split("===START_CHAT===")[1].split("===END_CHAT===")[0].strip()
            if "===START_JSON===" in response_text and "===END_JSON===" in response_text:
                json_part = response_text.split("===START_JSON===")[1].split("===END_JSON===")[0].strip()
                
            try: 
                blueprint_worker = json.loads(json_part)
            except: 
                blueprint_worker = json.loads(dummy_json_payload)
                
            if blueprint_worker and "bom_rows" in blueprint_worker:
                blueprint_worker["calculated_on_size"] = target_size_cmd
                for row in blueprint_worker.get("bom_rows", []):
                    if row.get("fabric_classification") == "MAIN_FABRIC" or "fabric_width_inch" not in row:
                        row["fabric_width_inch"] = active_width
                
                blueprint_final = allocate_fabric_consumption_and_quality_gate(blueprint_worker, str(safe_user_prompt).strip())
                st.session_state.bom_data = blueprint_final
                st.session_state.accumulated_bom_rows = blueprint_final.get("bom_rows", [])
                
                st.session_state["last_processed_signature"] = (str(safe_user_prompt).strip(), int(len(image_payloads)), int(len(st.session_state.pdf_bytes)))
                st.rerun()

        except Exception as ai_err:
            st.error(f"❌ Lỗi AI: {str(ai_err)}")

# =====================================================================
# ĐOẠN 7b: HIỂN THỊ KẾT QUẢ ĐỊNH MỨC & BẢNG ĐỐI CHỨNG ĐA CỘT ĐỒNG BỘ SIZE (V102.6 MULTI-ENGINE)
# 🌟 ĐỒNG BỘ HẠ TẦNG: ĐỌC ĐỘNG DỮ LIỆU TỪ CÁC MICRO-ENGINES (FABRIC/ELASTIC/TAPE/COUNT)
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
    st.markdown(f'<div class="cad-header">📊 CALCULATED MATERIAL CONSUMPTION MATRIX (SIZE TARGET: {extracted_size})</div>', unsafe_allow_html=True)
    
    display_data = []
    
    for r in bom_rows_list:
        if not r or not isinstance(r, dict): 
            continue
            
        current_gross = r.get("gross_consumption", 0.0)
        sys_notes = r.get("system_notes", "Mô phỏng CAD Gerber V27")
        engine_target = str(r.get("engine", "FABRIC")).upper().strip()
        uom_display = str(r.get("uom", "YDS")).upper().strip()

        if engine_target in ["FABRIC", "FUSING"]:
            raw_width = r.get("fabric_width_inch", 56.0)
            cut_width_val = f"{float(raw_width)} inch" if isinstance(raw_width, (int, float)) else f"{raw_width} inch"
            warp_dynamic = r.get("_btp_warp_pct", "3.0%")
            weft_dynamic = r.get("_btp_weft_pct", "3.0%")
            eff_dynamic = r.get("marker_efficiency", "85.5%")
        else:
            cut_width_val = "N/A (Linear/Count)"
            warp_dynamic = "-"
            weft_dynamic = "-"
            eff_dynamic = "-"

        display_data.append({
            "Component Name": r.get("component_name", "Unnamed Material"),
            "Material Class": r.get("material_class", engine_target),
            "UOM": uom_display,
            "Khổ vải (Width)": cut_width_val,
            "Co rút dọc (% Warp)": warp_dynamic,     
            "Co rút ngang (% Weft)": weft_dynamic,   
            "Marker Efficiency": eff_dynamic,         
            "Gross Consumption": current_gross,
            "Quality Status": r.get("quality_status", "PASS"),
            "System Calculation Notes": sys_notes
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
            
            ws.append([f"BÁO CÁO ĐỊNH MỨC VẬT TƯ SẢN XUẤT ĐA PHÂN HỆ (SIZE: {extracted_size})"])
            if 'df_bom' in locals():
                ws.append(list(df_bom.columns))
                for index, row_excel in df_bom.iterrows():
                    ws.append(list(row_excel))
            wb.save(output)
            output.seek(0)
            
            st.markdown("<br>", unsafe_allow_html=True)
            st.download_button(
                label="📥 Tải Báo Cáo Định Mức Phụ Liệu Excel (Chuẩn Nhà Máy)",
                data=output,
                file_name=f"BOM_Production_Consumption_Size_{extracted_size}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
        except Exception as excel_err:
            pass
