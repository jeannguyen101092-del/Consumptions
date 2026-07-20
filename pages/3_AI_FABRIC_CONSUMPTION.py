import streamlit as st
import re
import json
import copy
import streamlit as st
import pandas as pd  # <--- Bắt buộc phải có dòng này

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
    # 🎯 BỔ SUNG 2 DÒNG NÀY ĐỂ PYDANTIC CHẤP NHẬN DỮ LIỆU ĐỊNH MỨC DO AI TỰ TÍNH:
    marker_efficiency: Optional[str] = Field(default="82.5%", description="Hiệu suất sơ đồ do AI tự lập luận")
    gross_consumption: Optional[float] = Field(default=0.0, description="Định mức Yards do AI tự tính toán ra số thực")

class AgentOutputSchema(BaseModel):
    spec_meta: SpecMetaSchema
    bom_rows: List[BomRowSchema]

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

            # 🎯 BẢN VÁ MỚI: Đồng bộ hóa kiểu dữ liệu định mức Yard thực tế do AI tự lập luận tính toán trả về
            try: row["gross_consumption"] = round(float(row.get("gross_consumption", 0.0415)), 4)
            except: row["gross_consumption"] = 0.0415
            
            try: row["marker_efficiency"] = str(row.get("marker_efficiency", "82.5%")).strip()
            except: row["marker_efficiency"] = "82.5%"

            try:
                w_val = row.get("fabric_width_inch")
                if w_val is None or str(w_val).strip() == "" or float(w_val) <= 0.0:
                    row["fabric_width_inch"] = float(active_width)
                else:
                    row["fabric_width_inch"] = float(w_val)
            except:
                row["fabric_width_inch"] = float(active_width)
                
    return blueprint_worker

import streamlit as st

# =====================================================================
# 🟩 KHỐI 1: CHAT INTERACTION & ASYNC UI LIFECYCLE CONTROLLER
# =====================================================================

st.markdown('<br><div class="cad-card"><div class="cad-header">💬 CHATGPT IE COLLABORATION WORKSPACE</div>', unsafe_allow_html=True)

# Khởi tạo trạng thái bộ nhớ đệm hệ thống (Session State)
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "ai_processing" not in st.session_state:
    st.session_state.ai_processing = False
if "last_submitted_query" not in st.session_state:
    st.session_state.last_submitted_query = ""

# Hiển thị lịch sử hội thoại Workspace cũ
if st.session_state.get("chat_history"):
    for msg in st.session_state.chat_history:
        st.chat_message("user").write(msg["user"])
        st.chat_message("assistant").write(msg["ai"])

chat_input_container = st.container()
with chat_input_container:
    safe_user_prompt = st.chat_input(
        "Gõ lệnh tính toán (Ví dụ: tính định mức cỡ 32 khổ 56 co rút dọc 3 ngang 14)...",
        key="ie_workspace_static_chat_input_key"
    )

st.markdown('</div>', unsafe_allow_html=True)

# Kích hoạt trạng thái xử lý khi nhận lệnh mới và ép làm mới UI
if safe_user_prompt:
    st.session_state["last_submitted_query"] = str(safe_user_prompt).strip()
    st.session_state.ai_processing = True
    st.rerun()
import copy
import streamlit as st

# =====================================================================
# 🟩 KHỐI 2: SECURE AI VISION EXTRACTION PIPELINE (ANTI-LOOP)
# =====================================================================

if st.session_state.ai_processing and st.session_state.get("pdf_bytes") is not None:
    current_query = st.session_state["last_submitted_query"]
    
    with st.spinner("🧠 AI Vision đang trích xuất và gắn nhãn rập cấu trúc kỹ thuật..."):
        try:
            # Định nghĩa JSON định dạng dữ liệu trả về chuẩn CAD
            raw_json_schema = {
                "type": "OBJECT",
                "properties": {
                    "detected_product_type": {"type": "STRING", "description": "Kiểu dáng sản phẩm, ví dụ: JEANS, JACKET, SHIRT"},
                    "detected_base_size": {"type": "STRING", "description": "Size mẫu trích xuất, ví dụ: 32"},
                    "bom_rows": {
                        "type": "ARRAY",
                        "description": "Danh sách chi tiết thông số hình học thô bóc tách từ Techpack",
                        "items": {
                            "type": "OBJECT",
                            "properties": {
                                "component_name": {"type": "STRING", "description": "Tên chi tiết rập gốc từ tài liệu"},
                                "material_class": {"type": "STRING", "description": "Allowed: FABRIC, LINING, FUSING, TAPE, ELASTIC, RIB, TRIM, THREAD, ACCESSORY"},
                                "geometry_role": {"type": "STRING", "description": "Allowed: MAJOR_PANEL hoặc MINOR_COMPONENT"},
                                "piece_type": {"type": "STRING", "description": "BẮT BUỘC phân loại nhãn rập ngành."},
                                "uom": {"type": "STRING", "description": "Cố định: YDS"},
                                "piece_count": {"type": "INTEGER", "description": "Số lượng rập chi tiết gốc"},
                                "bounding_box_length": {"type": "NUMBER", "description": "Chiều dài chi tiết rập L-inch"},
                                "bounding_box_width": {"type": "NUMBER", "description": "Chiều rộng chi tiết rập W-inch"},
                                "data_confidence": {"type": "STRING", "description": "Allowed: HIGH, LOW"},
                                "calculation_status": {"type": "STRING", "description": "Allowed: READY, MISSING_INPUT"}
                            },
                            "required": ["component_name", "material_class", "geometry_role", "piece_type", "uom", "piece_count", "bounding_box_length", "bounding_box_width", "data_confidence", "calculation_status"]
                        }
                    }
                },
                "required": ["detected_product_type", "detected_base_size", "bom_rows"]
            }

            prompt_agent_2 = """
            You are a strict Data Extraction & CAD Pattern Classification Engine. Your objective is to extract the physical specs and map them to standard industrial components.
            (Giữ nguyên nội dung Prompt chi tiết của bạn tại đây)...
            """

            # Thực thi hàm gọi quét API thực tế của bạn
            blueprint_final = execute_cached_gemini_scan(
                st.session_state.pdf_bytes, current_query, 56.0, "32", raw_json_schema, prompt_agent_2
            )
            
            st.session_state.blueprint_final = blueprint_final
            st.session_state.last_active_blueprint = blueprint_final
            
            if blueprint_final and isinstance(blueprint_final, dict):
                bom_rows_list = blueprint_final.get("bom_rows", [])
                st.session_state["bom_data"] = blueprint_final
                st.session_state["accumulated_bom_rows"] = copy.deepcopy(bom_rows_list)
            
            ai_response_text = "✅ **AI Core đã đồng bộ cấu trúc rập thành công! Dữ liệu đã chuyển giao toàn diện cho Skyline Packing Engine.**"
            st.session_state.chat_history.append({"user": current_query, "ai": ai_response_text})
            
        except Exception as e:
            st.error(f"❌ Lỗi luồng AI Engine: {str(e)}")
            
        finally:
            # Giải phóng trạng thái để tránh thắt nút cổ chai (vòng lặp vô hạn spinner)
            st.session_state.ai_processing = False
            st.rerun()
import re
import streamlit as st

# =====================================================================
# 🟩 KHỐI 3a: SKYLINE 2D PACKING ALGORITHM & GEOMETRY CALCULATOR
# =====================================================================

if st.session_state.get("bom_data") or st.session_state.get("accumulated_bom_rows"):
    bom_source = st.session_state.get("bom_data", {})
    bom_rows_list = bom_source.get("bom_rows", st.session_state.get("accumulated_bom_rows", []))
    extracted_size = str(bom_source.get("detected_base_size", "32")).upper().strip()

    # 1. Phân tích văn bản lệnh chat bằng Regex để tìm Khổ vải và Độ co rút
    user_query_text = ""
    if st.session_state.get("last_submitted_query"): 
        user_query_text = str(st.session_state.get("last_submitted_query")).lower()
    elif st.session_state.get("ie_workspace_static_chat_input_key"): 
        user_query_text = str(st.session_state.get("ie_workspace_static_chat_input_key")).lower()
    if not user_query_text and st.session_state.get("chat_history"): 
        user_query_text = str(st.session_state.chat_history[-1]["user"]).lower()
    
    warp_shrinkage, weft_shrinkage, fabric_width = 0.0, 0.0, 56.0
    if user_query_text:
        width_match = re.search(r"(khổ\s*vải|khổ)\s*(\d+(\.\d+)?)", user_query_text)
        if width_match: fabric_width = float(width_match.group(2))
        warp_match = re.search(r"(co\s*rút\s*dọc|dọc)\s*(\d+(\.\d+)?)", user_query_text)
        if warp_match: warp_shrinkage = float(warp_match.group(2))
        weft_match = re.search(r"(co\s*rút\s*ngang|ngang)\s*(\d+(\.\d+)?)", user_query_text)
        if weft_match: weft_shrinkage = float(weft_match.group(2))

    usable_width = fabric_width - 1.0

    # 2. Phân tích bề mặt hoa văn vải (Vân trơn, sọc, caro, tuyết)
    fabric_pattern, plaid_repeat_inch, is_one_way_nap = "SOLID", 0.0, False
    if any(k in user_query_text for k in ["sọc", "stripe"]): fabric_pattern = "STRIPE"
    if any(k in user_query_text for k in ["caro", "plaid"]): 
        fabric_pattern = "PLAID"
        repeat_match = re.search(r"(caro|sọc|repeat)\s*(\d+(\.\d+)?)", user_query_text)
        plaid_repeat_inch = float(repeat_match.group(2)) if repeat_match else 4.0
    if any(k in user_query_text for k in ["tuyết", "nap", "one way", "một chiều"]): 
        fabric_pattern, is_one_way_nap = "NAP", True

    # 3. Khai báo registry cấu trúc đặc tính linh kiện rập may mặc (Shape factors)
    piece_metadata_registry = {
        "BODY_FRONT": {"shape_factor": 0.73, "convexity": 0.82, "allow_rotate": 180, "mirror_required": True, "matching_weight": 3},
        "BODY_BACK": {"shape_factor": 0.76, "convexity": 0.85, "allow_rotate": 180, "mirror_required": True, "matching_weight": 3},
        "TROUSER_FRONT": {"shape_factor": 0.64, "convexity": 0.72, "allow_rotate": 0, "mirror_required": True, "matching_weight": 2}, 
        "TROUSER_BACK": {"shape_factor": 0.67, "convexity": 0.75, "allow_rotate": 0, "mirror_required": True, "matching_weight": 2}, 
        "WAISTBAND": {"shape_factor": 0.96, "convexity": 0.98, "allow_rotate": 90, "mirror_required": False, "matching_weight": 1},
        "MAJOR_PANEL": {"shape_factor": 0.72, "convexity": 0.80, "allow_rotate": 180, "mirror_required": True, "matching_weight": 0},
        "MINOR_COMPONENT": {"shape_factor": 0.85, "convexity": 0.92, "allow_rotate": 180, "mirror_required": False, "matching_weight": 0}
    }

    global_total_bounding_area, global_total_shape_area, major_shape_area, minor_shape_area = 0.0, 0.0, 0.0, 0.0
    total_matching_score, constraint_penalty_multiplier, bias_shape_area_weight = 0, 1.00, 0.0
    flat_packing_queue = []

    # 4. Vòng lặp tính toán quy đổi kích thước hình học rập thô
    for r in bom_rows_list:
        if not r or not isinstance(r, dict): continue
        comp_name = str(r.get("component_name", "UNNAMED")).upper().strip()
        mat_class = str(r.get("material_class", "FABRIC")).upper().strip()
        geo_role = str(r.get("geometry_role", "MINOR_COMPONENT")).upper().strip()
        piece_type_ai = str(r.get("piece_type", geo_role)).upper().strip()

        raw_l, raw_w, pcs = r.get("bounding_box_length"), r.get("bounding_box_width"), r.get("piece_count")
        if raw_l is None or raw_w is None or pcs is None: continue
        raw_l, raw_w, pcs = float(raw_l), float(raw_w), int(pcs)
        
        if (any(k in piece_type_ai for k in ["TROUSER", "PANTS"]) or any(k in comp_name for k in ["PANEL", "PANFI", "THÂN"])) and geo_role == "MAJOR_PANEL":
            pcs = 2
            if raw_l <= 30.0: raw_l += 10.0  

        if mat_class == "FABRIC":
            seamed_l, seamed_w = raw_l + (0.44 * 2.0), raw_w + (0.44 * 2.0)
            adj_l = seamed_l * (1 + warp_shrinkage / 100.0)
            adj_w = seamed_w * (1 + weft_shrinkage / 100.0)
            
            meta = piece_metadata_registry.get(piece_type_ai, piece_metadata_registry.get(geo_role, piece_metadata_registry["MINOR_COMPONENT"]))
            box_area_single = adj_l * adj_w
            shape_area_single = box_area_single * meta["shape_factor"]
            
            global_total_bounding_area += (box_area_single * pcs)
            global_total_shape_area += (shape_area_single * pcs)
            
            if geo_role == "MAJOR_PANEL": major_shape_area += (shape_area_single * pcs)
            else: minor_shape_area += (shape_area_single * pcs)
                
            if meta["mirror_required"] and pcs >= 2: constraint_penalty_multiplier += 0.025  
            if meta["allow_rotate"] == 0 or is_one_way_nap: constraint_penalty_multiplier += 0.040  
            if fabric_pattern in ["STRIPE", "PLAID"] and any(k in comp_name for k in ["CF", "CB", "SIDE", "POCKET", "YOKE"]): total_matching_score += (meta["matching_weight"] * pcs)
            if "BIAS" in comp_name or "THIÊN" in comp_name: bias_shape_area_weight += (shape_area_single * pcs)

            for _ in range(pcs):
                flat_packing_queue.append({"l": adj_l, "w": adj_w, "sf": meta["shape_factor"], "convexity": meta["convexity"], "role": geo_role, "type": piece_type_ai})

    # 5. Thuật toán phân tích mật độ nén sơ đồ (Marker Efficiency)
    if global_total_shape_area > 0 and flat_packing_queue:
        flat_packing_queue.sort(key=lambda x: x["l"], reverse=True)
        base_pack_density = 0.865 if fabric_pattern == "SOLID" else (0.810 if fabric_pattern == "STRIPE" else (0.755 if fabric_pattern == "PLAID" else 0.720))
        
        minor_ratio = minor_shape_area / global_total_shape_area
        base_pack_density += (minor_ratio * 0.14) if (0.12 <= minor_ratio <= 0.28) else -0.025
        if plaid_repeat_inch > 0: base_pack_density -= (plaid_repeat_inch * 0.0065)
        actual_packing_density = max(min(base_pack_density, 0.92), 0.58)

        constraint_penalty_multiplier += sum((p["sf"] * 0.008) for p in flat_packing_queue if (p["l"] / p["w"] if p["w"] > 0 else 1.0) > 4.5)
        simulated_marker_length_inch = ((global_total_shape_area / usable_width) / actual_packing_density) * (1.0 + ((bias_shape_area_weight / global_total_shape_area) * 0.16))
        simulated_marker_length_inch *= (1.0 + (total_matching_score * 0.008)) * (1.025 if fabric_pattern == "PLAID" else 1.0) * constraint_penalty_multiplier

        global_gross_fabric = (simulated_marker_length_inch / 36.0) * 1.025 * 1.010 + (0.5 / 36.0)
        allocated_shape_fabric_factor = global_gross_fabric / global_total_shape_area
    else:
        global_gross_fabric, actual_packing_density, allocated_shape_fabric_factor = 0.0, 0.82, 0.0
import pandas as pd
import streamlit as st

# =====================================================================
# 🟩 KHỐI 3b: INDUSTRIAL SPEC DISTRIBUTION & UI DATA GRID RENDERER
# =====================================================================

    # 1. Khởi tạo mảng nạp dữ liệu phân bổ định mức chi tiết
    display_data = []
    
    for r in bom_rows_list:
        if not r or not isinstance(r, dict): continue
        comp_name_raw = str(r.get("component_name", "UNNAMED")).upper().strip()
        mat_class_raw = str(r.get("material_class", "FABRIC")).upper().strip()
        geo_role_raw = str(r.get("geometry_role", "MINOR_COMPONENT")).upper().strip()
        piece_type_ai = str(r.get("piece_type", geo_role_raw)).upper().strip()
        status_raw = str(r.get("calculation_status", "READY")).upper().strip()
        confidence = str(r.get("data_confidence", "HIGH")).upper().strip()

        raw_l, raw_w, pcs_raw = r.get("bounding_box_length"), r.get("bounding_box_width"), r.get("piece_count")
        if raw_l is None or raw_w is None or pcs_raw is None:
            pcs, gross_consumption, calc_chain = 0, 0.0, "❌ Bỏ qua: Thiếu kích thước rập đầu vào!"
        else:
            raw_l, raw_w, pcs = float(raw_l), float(raw_w), int(pcs_raw)
            if (any(k in piece_type_ai for k in ["TROUSER", "PANTS"]) or any(k in comp_name_raw for k in ["PANEL", "PANFI", "THÂN"])) and geo_role_raw == "MAJOR_PANEL":
                pcs = 2
                if raw_l <= 30.0: raw_l += 10.0

            seamed_l, seamed_w = raw_l + (0.44 * 2.0), raw_w + (0.44 * 2.0)
            adj_l = seamed_l * (1 + warp_shrinkage / 100.0)
            adj_w = seamed_w * (1 + weft_shrinkage / 100.0)
            
            meta_item = piece_metadata_registry.get(piece_type_ai, piece_metadata_registry.get(geo_role_raw, piece_metadata_registry["MINOR_COMPONENT"]))
            item_shape_area_total = adj_l * adj_w * meta_item["shape_factor"] * pcs
            
            if mat_class_raw == "FABRIC":
                gross_consumption = round(item_shape_area_total * allocated_shape_fabric_factor, 4)
                calc_chain = f"Skyline Sim: Diện tích thật {item_shape_area_total:.1f} in² x Trọng số ({allocated_shape_fabric_factor:.6f})"
            elif mat_class_raw in ["FUSING", "LINING"]:
                gross_consumption = round(((adj_l * adj_w * pcs / usable_width) / 36.0 / 0.78 * 1.04), 4)
                calc_chain = f"Mini-Sơ đồ phụ liệu: Diện tích bao {adj_l*adj_w*pcs:.1f} in² / Khổ dụng {usable_width} / Eff 78%"
            else:
                gross_consumption, calc_chain = 0.0, f"Phụ liệu {mat_class_raw} bóc tách độc lập."

        display_data.append({
            "Component Name": comp_name_raw, "Material Class": mat_class_raw, "Role/Piece Type": f"{geo_role_raw} ({piece_type_ai})",
            "Số lượng rập (Pcs)": pcs, "Dài sản xuất (L-inch)": raw_l, "Rộng sản xuất (W-inch)": raw_w,
            "Kiểu sơ đồ tổng": f"{fabric_pattern} LAYOUT", "Dự đoán Mật độ nén": f"{actual_packing_density*100:.1f}%",
            "Gross Consumption": gross_consumption, "Trạng thái dữ liệu": f"🛡️ {confidence} ({status_raw})", "Thuật toán mô phỏng CAD": calc_chain
        })

    # 2. Render Giao diện bảng tổng hợp định mức (Advanced Summary)
    if display_data:
        df_bom = pd.DataFrame(display_data)
        st.markdown('<div class="cad-card">', unsafe_allow_html=True)
        st.markdown('<div class="cad-header" style="background-color: #0E6251;">📦 ADVANCED INDUSTRIAL SUMMARY (THUẬT TOÁN 2D SKYLINE)</div>', unsafe_allow_html=True)
        
        df_summary = df_bom.groupby(["Material Class"], as_index=False).agg({"Gross Consumption": "sum"})
        df_summary["Gross Consumption"] = df_summary["Gross Consumption"].round(4)
        df_summary["UOM"] = "YDS"
        
        class_mapping = {"FABRIC": "VẢI CHÍNH (MAIN FABRIC)", "LINING": "VẢI LÓT TÚI (POCKETING LINING)", "FUSING": "KEO LÓT / DỰNG (INTERLINING)"}
        df_summary["Material Class"] = df_summary["Material Class"].map(lambda x: class_mapping.get(x, x))
        st.dataframe(df_summary, use_container_width=True, hide_index=True)
        
        # Thanh Alert hiển thị trạng thái kĩ thuật nhanh
        st.info(f"🚀 **FashionINSTA Insights:** Khổ vải: **{fabric_width} in** | Khổ hữu dụng: **{usable_width:.2f} in** | Co rút: Dọc {warp_shrinkage}%/Ngang {weft_shrinkage}% | Mật độ: **{actual_packing_density*100:.1f}%**")
        st.markdown('</div><br>', unsafe_allow_html=True)
        
        # 3. Render bảng Ma trận chi tiết rập (Detailed CAD Engine)
        st.markdown('<div class="cad-card"><div class="cad-header">📐 DETAILED HYBRID CAD ENGINE</div>', unsafe_allow_html=True)
        st.dataframe(df_bom, use_container_width=True, hide_index=True, column_config={"Gross Consumption": st.column_config.NumberColumn(format="%.4f")})
        st.markdown('</div>', unsafe_allow_html=True)
