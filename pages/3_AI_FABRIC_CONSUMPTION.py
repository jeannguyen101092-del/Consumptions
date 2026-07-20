import streamlit as st
import re
import json
import copy
import streamlit as st
import pandas as pd  # <--- Bắt buộc phải có dòng này
import threading

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











import hashlib
import json
import re
import fitz
import google.generativeai as genai
import streamlit as st


# =====================================================================
# 🧠 ĐOẠN A (NÂNG CẤP QUET TOÀN DIỆN BOM): KHỐI HÀM CACHE AI
# =====================================================================
@st.cache_data(
    show_spinner=False,
    ttl=60,
    hash_funcs={bytes: lambda b: hashlib.sha256(b).hexdigest()},
)
def execute_cached_gemini_scan(
    pdf_bytes,
    current_query,
    active_width,
    target_size_cmd,
    raw_json_schema,
    prompt_agent_2,
):
    """Hàm gọi AI quét TOÀN BỘ các trang trong file Techpack để bóc tách trọn

    vẹn cấu trúc Vải chính, Vải lót và Keo lót (Fusing).
    """
    import copy
    import hashlib

    if hasattr(pdf_bytes, "getvalue"):
        pdf_bytes = pdf_bytes.getvalue()

    if not isinstance(pdf_bytes, bytes):
        raise TypeError("Dữ liệu PDF đầu vào không đúng định dạng bytes hợp lệ!")

    full_pdf_raw_text = ""
    image_payloads = []

    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc_recovery:
        total_pages = len(doc_recovery)

        # 🚨 ĐÃ SỬA: Quét toàn bộ số trang của file Techpack để tìm sạch linh kiện keo/phụ liệu ở trang sau
        for idx in range(total_pages):
            page_text = doc_recovery[idx].get_text("text")
            full_pdf_raw_text += f"\n--- PAGE {idx + 1} ---\n{page_text}"

            # Chỉ render ảnh cho 5 trang đầu hoặc trang chứa hình vẽ rập để tối ưu hóa dung lượng gửi đi
            if len(image_payloads) < 5:
                try:
                    pix = doc_recovery[idx].get_pixmap(
                        dpi=72, colorspace=fitz.csRGB
                    )
                    image_payloads.append(
                        {
                            "mime_type": "image/jpeg",
                            "data": pix.tobytes("jpeg"),
                        }
                    )
                except Exception:
                    continue

    gemini_inputs = copy.deepcopy(image_payloads)
    gemini_inputs.insert(
        0,
        f"=== USER CHAT COMMAND ===\n{current_query}\n\n=== TECHPACK TEXT ===\n{full_pdf_raw_text}\n",
    )

    # 🚨 ĐÃ CẬP NHẬT PROMPT ÉP ĐẦU RA TOÀN DIỆN NGUYÊN PHỤ LIỆU
    extended_prompt = (
        prompt_agent_2
        + """
    CRITICAL MULTI-MATERIAL EXTRACTION RULES:
    - You MUST extract EVERY SINGLE component listed in the document, not just FABRIC.
    - Carefully scan for pocket linings, waist linings, and fusing/interfacing descriptors.
    - If a component name contains "FUSING", "INTERLINING", "MEX", "DỰNG", "KEO LOT", classify its material_class strictly as "FUSING".
    - If a component name contains "LINING", "POCKET BAG", "LOT TUI", classify its material_class strictly as "LINING".
    - Do not omit any minor panels or components from the final JSON structure.
    """
    )
    gemini_inputs.append(extended_prompt)

    model = genai.GenerativeModel("gemini-2.5-flash")
    response = model.generate_content(
        gemini_inputs,
        generation_config={
            "response_mime_type": "application/json",
            "response_schema": raw_json_schema,
            "temperature": 0.0,
        },
        request_options={"timeout": 60.0},
    )

    if not response or not response.text:
        raise RuntimeError("Mô hình Gemini trả về kết quả rỗng!")

    txt = response.text.strip()
    if txt.startswith("```"):
        txt = re.sub(r"^```json\s*", "", txt)
        txt = re.sub(r"^```\s*", "", txt)
        txt = re.sub(r"\s*```$", "", txt)
    txt = txt.strip()

    try:
        blueprint_worker = json.loads(txt)
    except json.JSONDecodeError as json_err:
        raise RuntimeError(
            f"Mô hình Gemini trả về cấu trúc chuỗi JSON không hợp lệ:\n\n{txt}"
        ) from json_err

    if blueprint_worker and "bom_rows" in blueprint_worker:
        blueprint_worker["calculated_on_size"] = target_size_cmd
        for row in blueprint_worker.get("bom_rows", []):
            if "component_name" in row:
                row["component_name"] = " ".join(
                    str(row["component_name"]).upper().split()
                )
            try:
                row["bounding_box_length"] = round(
                    float(row.get("bounding_box_length", 0.0)), 2
                )
            except Exception:
                row["bounding_box_length"] = 0.0
            try:
                row["bounding_box_width"] = round(
                    float(row.get("bounding_box_width", 0.0)), 2
                )
            except Exception:
                row["bounding_box_width"] = 0.0
            try:
                row["polygon_net_area"] = float(row.get("polygon_net_area", 0.0))
            except Exception:
                row["polygon_net_area"] = 0.0
            try:
                row["piece_count"] = int(float(row.get("piece_count", 1)))
            except Exception:
                row["piece_count"] = 1
            try:
                row["gross_consumption"] = round(
                    float(row.get("gross_consumption", 0.0415)), 4
                )
            except Exception:
                row["gross_consumption"] = 0.0415
            try:
                row["marker_efficiency"] = str(
                    row.get("marker_efficiency", "82.5%")
                ).strip()
            except Exception:
                row["marker_efficiency"] = "82.5%"
            try:
                w_val = row.get("fabric_width_inch")
                if (
                    w_val is None
                    or str(w_val).strip() == ""
                    or float(w_val) <= 0.0
                ):
                    row["fabric_width_inch"] = float(active_width)
                else:
                    row["fabric_width_inch"] = float(w_val)
            except Exception:
                row["fabric_width_inch"] = float(active_width)

    return blueprint_worker





import streamlit as st

# =====================================================================
# 🟩 ĐOẠN 1: CHAT WORKSPACE LAYER (CHỐNG KẸT LUỒNG & PHÁT LỆNH)
# =====================================================================

# 1. Khởi tạo an toàn bộ nhớ đệm hệ thống (Session State)
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "ai_processing" not in st.session_state:
    st.session_state.ai_processing = False
if "last_submitted_query" not in st.session_state:
    st.session_state.last_submitted_query = ""

# 2. Tạo một khung Container riêng độc lập để chứa lịch sử hội thoại cũ
chat_history_container = st.container()
with chat_history_container:
    st.markdown('<br><div class="cad-card"><div class="cad-header">💬 CHATGPT IE COLLABORATION WORKSPACE</div></div>', unsafe_allow_html=True)
    if st.session_state.get("chat_history"):
        for msg in st.session_state.chat_history:
            st.chat_message("user").write(msg["user"])
            st.chat_message("assistant").write(msg["ai"])

# 🚨 ĐÃ SỬA: Đặt sát lề trái ngoài cùng, đổi key sang _v8 mới tinh để giải phóng hoàn toàn bộ nhớ đệm kẹt cũ
safe_user_prompt = st.chat_input(
    "Gõ lệnh tính toán (Ví dụ: tính định mức cỡ 32 khổ 56 co rút dọc 3 ngang 14)...",
    key="ie_workspace_fixed_dynamic_chat_final_patch_v8"
)

# 3. Kích hoạt cờ hiệu xử lý và ép tải lại luồng chính khi người dùng gửi thành công
if safe_user_prompt:
    st.session_state["last_submitted_query"] = str(safe_user_prompt).strip()
    st.session_state.ai_processing = True
    st.rerun()

import copy
import traceback
import streamlit as st

# =====================================================================
# 🟩 ĐOẠN 2 (BẢN UPDATE PROMPT CAD HÌNH HỌC): AI CORE ENGINE
# =====================================================================

if st.session_state.ai_processing:
    current_query = st.session_state["last_submitted_query"]

    # Bộ quét tự động tìm file PDF dự phòng từ bộ nhớ đệm dùng chung khi chuyển tab
    active_pdf = st.session_state.get("pdf_bytes")
    if active_pdf is None:
        active_pdf = (
            st.session_state.get("uploaded_file")
            or st.session_state.get("current_pdf")
            or st.session_state.get("pdf_data")
        )

    if active_pdf is not None:
        with st.spinner(
            "🧠 AI Vision đang trích xuất và gắn nhãn rập cấu trúc kỹ thuật..."
        ):
            try:
                # 1. JSON SCHEMA MỞ RỘNG MÁ TRẬN ĐA GIÁC CAD
                raw_json_schema = {
                    "type": "OBJECT",
                    "properties": {
                        "detected_product_type": {
                            "type": "STRING",
                            "description": "Kiểu dáng sản phẩm, ví dụ: JEANS, JACKET, SHIRT",
                        },
                        "detected_base_size": {
                            "type": "STRING",
                            "description": "Size mẫu trích xuất, ví dụ: 32",
                        },
                        "bom_rows": {
                            "type": "ARRAY",
                            "description": "Danh sách chi tiết thông số hình học thô bóc tách từ Techpack",
                            "items": {
                                "type": "OBJECT",
                                "properties": {
                                    "component_name": {
                                        "type": "STRING",
                                        "description": "Tên chi tiết rập gốc từ tài liệu",
                                    },
                                    "material_class": {
                                        "type": "STRING",
                                        "description": "Allowed: FABRIC, LINING, FUSING, TAPE, ELASTIC, RIB, TRIM, THREAD, ACCESSORY",
                                    },
                                    "geometry_role": {
                                        "type": "STRING",
                                        "description": "Allowed: MAJOR_PANEL hoặc MINOR_COMPONENT",
                                    },
                                    "piece_type": {
                                        "type": "STRING",
                                        "description": "BẮT BUỘC phân loại nhãn rập chuẩn ngành.",
                                    },
                                    "uom": {
                                        "type": "STRING",
                                        "description": "Cố định: YDS",
                                    },
                                    "piece_count": {
                                        "type": "INTEGER",
                                        "description": "Số lượng rập chi tiết gốc (Pcs).",
                                    },
                                    "bounding_box_length": {
                                        "type": "NUMBER",
                                        "description": "Chiều dài chi tiết rập L-inch.",
                                    },
                                    "bounding_box_width": {
                                        "type": "NUMBER",
                                        "description": "Chiều rộng chi tiết rập W-inch.",
                                    },
                                    "data_confidence": {
                                        "type": "STRING",
                                        "description": "Allowed: HIGH, LOW",
                                    },
                                    "calculation_status": {
                                        "type": "STRING",
                                        "description": "Allowed: READY, MISSING_INPUT",
                                    },
                                },
                                "required": [
                                    "component_name",
                                    "material_class",
                                    "geometry_role",
                                    "piece_type",
                                    "uom",
                                    "piece_count",
                                    "bounding_box_length",
                                    "bounding_box_width",
                                    "data_confidence",
                                    "calculation_status",
                                ],
                            },
                        },
                    },
                    "required": [
                        "detected_product_type",
                        "detected_base_size",
                        "bom_rows",
                    ],
                }

                # 2. PROMPT CHUYÊN GIA CAD TRÍCH XUẤT & SUY LUẬN KHÔNG GIAN RẬP
                prompt_agent_2 = """
                You are a senior Industrial Garment IE & CAD Pattern Engineering Intelligence. Your absolute priority is to extract or intelligently estimate the physical dimensions (Length and Width in INCHES) for EVERY garment component found in the Techpack.
                
                🚨 CRITICAL DIMENSION RETRIEVAL & ESTIMATION DIRECTIVES (ANTI-ZERO RULE):
                1. PRIMARY SOURCE (TABLES): Search all pages for spec tables, graded measurement sheets, or marker detail blocks. Extract the exact 'bounding_box_length' and 'bounding_box_width' for the base size (Size 32).
                
                2. SECONDARY SOURCE (PATTERN SKETCH ESTIMATION): If numerical dimensions are NOT explicitly written in a structured table, you MUST estimate the bounding rectangle directly from the technical flat sketches, drawings, or pattern diagrams.
                   - Use the overall garment proportions and drawing scale to approximate the bounding box.
                   - NEVER output 0.0 or null for 'bounding_box_width' or 'bounding_box_length' if the component physically exists in the design sketch. A pant leg or waistband CANNOT have a width of 0.
                
                3. INDUSTRIAL GARMENT HEURISTIC BOUNDS (GUARDRAILS FOR JEANS/PANTS):
                   If you cannot find exact metrics and must estimate from the sketch, apply these standard apparel industry geometric boundaries to prevent mathematically impossible zeros:
                   - TROUSER_FRONT / TROUSER_BACK (Main Leg Panels): Length typically ranges between 35.0 to 45.0 inches. Width MUST be estimated based on the leg opening/thigh ratio, typically between 10.0 to 16.0 inches. NEVER leave width as 0.
                   - WAISTBAND / LƯNG QUẦN: Length is tied to waist size (e.g., Size 32 approx 32.0-35.0 inches if flat/curved). Width is standard waistband height, typically 1.5 to 2.5 inches.
                   - POCKET BAG / LÓT TÚI: Length typically 10.0 to 13.0 inches, Width typically 6.0 to 8.0 inches.
                   - COIN POCKET / FLAP / MINOR PIECES: Length 3.0 to 5.0 inches, Width 3.0 to 5.0 inches.
                
                4. DATA CONFIDENCE & STATUS LOGIC:
                   - Set data_confidence = "HIGH" and calculation_status = "READY" ONLY if the numbers are explicitly extracted from text/tables.
                   - Set data_confidence = "LOW" and calculation_status = "READY" if the dimensions are mathematically estimated/reconstructed from the pattern sketch or garment guardrails.
                   - ONLY set calculation_status = "MISSING_INPUT" if the component name is mentioned but there is absolutely zero visual representation or context to infer size.
                
                Ensure your output strictly adheres to the requested JSON structure. Every valid component must have non-zero geometric properties to allow proper 2D packing area calculation.
                """

                # 3. GỌI THỰC THI HÀM LÕI TRÊN LUỒNG CHÍNH AN TOÀN
                blueprint_final = execute_cached_gemini_scan(
                    active_pdf,
                    current_query,
                    56.0,
                    "32",
                    raw_json_schema,
                    prompt_agent_2,
                )

                st.session_state.blueprint_final = blueprint_final
                st.session_state.last_active_blueprint = blueprint_final

                if blueprint_final and isinstance(blueprint_final, dict):
                    bom_rows_list = blueprint_final.get("bom_rows", [])
                    st.session_state["bom_data"] = blueprint_final
                    st.session_state["accumulated_bom_rows"] = copy.deepcopy(
                        bom_rows_list
                    )

                ai_response_text = "✅ **AI Core đã đồng bộ cấu trúc rập thành công! Dữ liệu đã chuyển giao toàn diện cho Skyline Packing Engine.**"
                st.session_state.chat_history.append(
                    {"user": current_query, "ai": ai_response_text}
                )

            except Exception as e:
                # Bẫy lỗi và đóng băng giao diện để bảo lưu vết mã nguồn kĩ thuật thô màu đen khi xảy ra sự cố
                st.error("🚨 Chi tiết lỗi hệ thống từ API Core:")
                st.exception(e)
                st.code(traceback.format_exc(), language="python")
                st.session_state.ai_processing = False
                st.stop()

            finally:
                if st.session_state.ai_processing:
                    st.session_state.ai_processing = False
                    st.rerun()
   
    else:
        st.error(
            "⚠️ **Hệ thống chưa nhận được dữ liệu file PDF!** Vui lòng quay lại trang chính (Uploader), tải lại file Techpack để đồng bộ bộ nhớ đệm (Session State), sau đó quay lại đây gõ lệnh chat."
        )
        st.session_state.ai_processing = False





import re

def prepare_bom_and_geometry(bom_rows_list, user_query_text, blueprint_final=None):
    """
    Đoạn 1: Xử lý văn bản chat, chuẩn hóa kích thước BOM và bóc tách dữ liệu rập.
    """
    # 1. Trích xuất thông số vải từ văn bản chat bằng Regex
    warp_shrinkage, weft_shrinkage, fabric_width = 0.0, 0.0, 56.0
    user_query_text = str(user_query_text or "").lower()
    
    if user_query_text:
        width_match = re.search(r"(khổ\s*vải|khổ)\s*(\d+(\.\d+)?)", user_query_text)
        if width_match: fabric_width = float(width_match.group(2))
        warp_match = re.search(r"(co\s*rút\s*dọc|dọc)\s*(\d+(\.\d+)?)", user_query_text)
        if warp_match: warp_shrinkage = float(warp_match.group(2))
        weft_match = re.search(r"(co\s*rút\s*ngang|ngang)\s*(\d+(\.\d+)?)", user_query_text)
        if weft_match: weft_shrinkage = float(weft_match.group(2))

    usable_width = max(1.0, fabric_width - 1.0) 

    # 2. Xác định kiểu hoa văn và loại sản phẩm (Khớp dữ liệu AI)
    fabric_pattern, plaid_repeat_inch, is_one_way_nap = "SOLID", 0.0, False
    if any(k in user_query_text for k in ["sọc", "stripe"]): fabric_pattern = "STRIPE"
    if any(k in user_query_text for k in ["caro", "plaid"]): 
        fabric_pattern = "PLAID"
        repeat_match = re.search(r"(caro|sọc|repeat)\s*(\d+(\.\d+)?)", user_query_text)
        plaid_repeat_inch = float(repeat_match.group(2)) if repeat_match else 4.0
    if any(k in user_query_text for k in ["tuyết", "nap", "one way", "một chiều"]): fabric_pattern, is_one_way_nap = "NAP", True

    product_category = "JACKET_COAT"
    if blueprint_final and isinstance(blueprint_final, dict):
        product_category = blueprint_final.get("detected_product_type", "JACKET_COAT").upper()
    else:
        if any(k in user_query_text for k in ["shirt", "sơ mi", "polo", "t-shirt"]): product_category = "SHIRT_TOP"
        elif any(k in user_query_text for k in ["trouser", "pants", "quần", "jeans"]): product_category = "TROUSER_PANTS"

    # 3. Bảng ma trận tỷ lệ rập và cấu hình chặn dưới (Min length)
    piece_metadata_registry = {
        "BODY_FRONT": {"shape_factor": 0.73, "allow_rotate": 180, "mirror_required": True, "avg_aspect_ratio": 1.35, "min_len": 24.0},
        "BODY_BACK": {"shape_factor": 0.76, "allow_rotate": 180, "mirror_required": True, "avg_aspect_ratio": 1.40, "min_len": 25.0},
        "TROUSER_FRONT": {"shape_factor": 0.64, "allow_rotate": 0, "mirror_required": True, "avg_aspect_ratio": 3.20, "min_len": 38.0}, 
        "TROUSER_BACK": {"shape_factor": 0.67, "allow_rotate": 0, "mirror_required": True, "avg_aspect_ratio": 3.00, "min_len": 39.0}, 
        "WAISTBAND": {"shape_factor": 0.96, "allow_rotate": 90, "mirror_required": False, "avg_aspect_ratio": 6.00, "min_len": 18.0},
        "MAJOR_PANEL": {"shape_factor": 0.72, "allow_rotate": 180, "mirror_required": True, "avg_aspect_ratio": 1.50, "min_len": 20.0},
        "MINOR_COMPONENT": {"shape_factor": 0.85, "allow_rotate": 180, "mirror_required": False, "avg_aspect_ratio": 1.20, "min_len": 4.0}
    }

    flat_packing_queue = []
    total_net_shape_area, total_bounding_box_area = 0.0, 0.0
    minor_pieces_count, stripe_matching_penalty_score = 0, 0.0
    has_mirror_restriction = False

    if not bom_rows_list:
        return {}

    for r in bom_rows_list:
        if not r or not isinstance(r, dict): continue
        comp_name = str(r.get("component_name", "UNNAMED")).upper().strip()
        mat_class = str(r.get("material_class", "FABRIC")).upper().strip()
        geo_role = str(r.get("geometry_role", "MINOR_COMPONENT")).upper().strip()
        piece_type_ai = str(r.get("piece_type", geo_role)).upper().strip()
        
        pcs = r.get("piece_count")
        if pcs is None: continue
        try:
            pcs = int(pcs)
            if pcs <= 0: continue
        except ValueError: continue

        meta = piece_metadata_registry.get(piece_type_ai, piece_metadata_registry.get(geo_role, piece_metadata_registry["MINOR_COMPONENT"]))

        # Ước lượng kích thước thiếu theo Tỷ lệ hình học phẳng
        raw_l, raw_w = r.get("bounding_box_length"), r.get("bounding_box_width")
        if raw_l is None and raw_w is not None:
            raw_l = float(raw_w) * meta["avg_aspect_ratio"]
        elif raw_w is None and raw_l is not None:
            raw_w = float(raw_l) / meta["avg_aspect_ratio"]
        elif raw_l is None and raw_w is None:
            continue
            
        try:
            raw_l, raw_w = float(raw_l), float(raw_w)
            if raw_l <= 0 or raw_w <= 0: continue
        except ValueError: continue

        # Ngưỡng chặn kích thước rập tối thiểu (Min Length Bound)
        if (any(k in piece_type_ai for k in ["TROUSER", "PANTS"]) or any(k in comp_name for k in ["PANEL", "PANFI", "THÂN"])) and geo_role == "MAJOR_PANEL":
            pcs = max(pcs, 2)
            raw_l = max(raw_l, meta["min_len"])

        if mat_class == "FABRIC":
            # Cộng đường may (0.44" mỗi biên) và độ co rút vải
            seamed_l, seamed_w = raw_l + (0.44 * 2.0), raw_w + (0.44 * 2.0)
            adj_l = seamed_l * (1.0 + max(0.0, warp_shrinkage) / 100.0)
            adj_w = seamed_w * (1.0 + max(0.0, weft_shrinkage) / 100.0)
            
            box_area_single = adj_l * adj_w
            total_bounding_box_area += (box_area_single * pcs)
            total_net_shape_area += (box_area_single * meta["shape_factor"] * pcs)

            if geo_role == "MINOR_COMPONENT": minor_pieces_count += pcs
            if fabric_pattern in ["STRIPE", "PLAID"] and any(k in comp_name for k in ["CF", "CB", "SIDE", "POCKET", "YOKE"]):
                stripe_matching_penalty_score += 0.015 * pcs

            if meta["mirror_required"] and is_one_way_nap and meta["allow_rotate"] == 0 and pcs >= 2:
                has_mirror_restriction = True

            if len(flat_packing_queue) < 3000:
                for _ in range(pcs):
                    flat_packing_queue.append({
                        "l": adj_l, "w": adj_w, 
                        "allow_rotate": meta["allow_rotate"], "shape_factor": meta["shape_factor"]
                    })

    return {
        "fabric_width": fabric_width, "usable_width": usable_width, "warp_shrinkage": warp_shrinkage, "weft_shrinkage": weft_shrinkage,
        "fabric_pattern": fabric_pattern, "plaid_repeat_inch": plaid_repeat_inch, "is_one_way_nap": is_one_way_nap,
        "flat_packing_queue": flat_packing_queue, "total_bounding_box_area": total_bounding_box_area, "total_net_shape_area": total_net_shape_area,
        "minor_pieces_count": minor_pieces_count, "stripe_matching_penalty_score": stripe_matching_penalty_score, "has_mirror_restriction": has_mirror_restriction
    }
def execute_skyline_placement(geometry_data):
    """
    Đoạn 2: Lõi thuật toán Skyline Corner với cơ chế Thử hướng xoay và Lấp khoảng trống (Gap Filling).
    Sửa lỗi gộp sai phân đoạn đứt gãy trên trục X.
    """
    if not geometry_data or not geometry_data.get("flat_packing_queue"):
        return {"fabric_width": 56.0, "usable_width": 55.0, "actual_packing_density": 0.82, "global_gross_fabric_consumption": 0.0}

    usable_width = geometry_data["usable_width"]
    flat_packing_queue = geometry_data["flat_packing_queue"]
    fabric_pattern = geometry_data["fabric_pattern"]
    plaid_repeat_inch = geometry_data["plaid_repeat_inch"]
    is_one_way_nap = geometry_data["is_one_way_nap"]

    # 1. PHÂN TÁCH HÀNG ĐỢI THEO VAI TRÒ HÌNH HỌC (GỐI ĐẦU CHO GAP FILLING)
    major_queue = [p for p in flat_packing_queue if p["role"] == "MAJOR_PANEL"]
    minor_queue = [p for p in flat_packing_queue if p["role"] != "MAJOR_PANEL"]

    # Xếp thứ tự ưu tiên chi tiết lớn nhất lên trước
    major_queue.sort(key=lambda x: max(x["l"], x["w"]), reverse=True)
    minor_queue.sort(key=lambda x: max(x["l"], x["w"]), reverse=True)

    # Khởi tạo ma trận đường chân trời: [x_start, width, y_level]
    skyline = [[0.0, usable_width, 0.0]]
    simulated_marker_length_inch = 0.0

    def place_piece_into_skyline(piece, current_skyline):
        """Hàm Heuristic tìm kiếm vị trí đặt và xoay rập tối ưu nhất trên lưới Skyline"""
        best_idx = -1
        best_num_spanned = 1
        best_y = float('inf')
        best_l, best_w = piece["l"], piece["w"]
        
        # Thử nghiệm các hướng xoay được cấu hình cho phép
        allowed_orientations = [(piece["l"], piece["w"])]
        if piece["allow_rotate"] == 90:
            allowed_orientations.append((piece["w"], piece["l"]))
        elif piece["allow_rotate"] == 180:
            allowed_orientations.append((piece["w"], piece["l"])) # Thử cả hai thế nằm đứng/ngang

        for test_l, test_w in allowed_orientations:
            if test_w > usable_width: continue # Bỏ qua nếu rập rộng vượt khổ vải
            
            # Quét tìm vùng phẳng liên kết trên trục X
            for i in range(len(current_skyline)):
                accumulated_w = 0.0
                max_y_in_range = 0.0
                segments_count = 0
                
                for j in range(i, len(current_skyline)):
                    _, seg_w, seg_y = current_skyline[j]
                    accumulated_w += seg_w
                    max_y_in_range = max(max_y_in_range, seg_y)
                    segments_count += 1
                    
                    if accumulated_w >= test_w:
                        # Chọn hướng xoay và vị trí tạo ra điểm nhô Y thấp nhất (Khớp Gerber Heuristic)
                        if max_y_in_range < best_y:
                            best_y = max_y_in_range
                            best_idx = i
                            best_num_spanned = segments_count
                            best_l, best_w = test_l, test_w
                        break
        return best_idx, best_num_spanned, best_y, best_l, best_w

    # =====================================================================
    # b1. ĐẶT TOÀN BỘ CHI TIẾT LỚN (MAJOR PANELS) ĐỂ ĐỊNH HÌNH KHUNG SƠ ĐỒ
    # =====================================================================
    for piece in major_queue:
        best_idx, num_spanned, min_y_found, p_l, p_w = place_piece_into_skyline(piece, skyline)
        
        if best_idx == -1:
            best_idx = 0
            num_spanned = len(skyline)
            min_y_found = max(seg[2] for seg in skyline)
            p_l, p_w = min(piece["l"], piece["w"]), max(piece["l"], piece["w"])

        seg_x = skyline[best_idx][0]
        placed_y_top = min_y_found + p_l
        total_spanned_w = sum(skyline[j][1] for j in range(best_idx, best_idx + num_spanned))
        
        new_segments = [[seg_x, p_w, placed_y_top]]
        if total_spanned_w > p_w:
            new_segments.append([seg_x + p_w, total_spanned_w - p_w, min_y_found])
            
        skyline[best_idx : best_idx + num_spanned] = new_segments

        # 🚨 SỬA LỖI GỘP PHÂN ĐOẠN: Kiểm tra cả độ cao Y và tính liền kề trục X
        merged_skyline = []
        for seg in skyline:
            if (merged_skyline 
                and abs(merged_skyline[-1][2] - seg[2]) < 0.001 
                and abs(merged_skyline[-1][0] + merged_skyline[-1][1] - seg[0]) < 0.001):
                merged_skyline[-1][1] += seg[1] # Hợp nhất chiều rộng nếu liền kề khít nhau
            else:
                merged_skyline.append(seg)
        skyline = merged_skyline
        simulated_marker_length_inch = max(simulated_marker_length_inch, placed_y_top)

    # =====================================================================
    # b2. THUẬT TOÁN GAP FILLING: QUAY LẠI TÌM HỐC TRỐNG LẤP CHI TIẾT NHỎ
    # =====================================================================
    for piece in minor_queue:
        best_idx, num_spanned, min_y_found, p_l, p_w = place_piece_into_skyline(piece, skyline)
        
        if best_idx != -1:
            seg_x = skyline[best_idx][0]
            placed_y_top = min_y_found + p_l
            total_spanned_w = sum(skyline[j][1] for j in range(best_idx, best_idx + num_spanned))
            
            new_segments = [[seg_x, p_w, placed_y_top]]
            if total_spanned_w > p_w:
                new_segments.append([seg_x + p_w, total_spanned_w - p_w, min_y_found])
                
            skyline[best_idx : best_idx + num_spanned] = new_segments

            # Làm sạch lưới liên kết trục X hậu Gap Filling
            merged_skyline = []
            for seg in skyline:
                if (merged_skyline 
                    and abs(merged_skyline[-1][2] - seg[2]) < 0.001 
                    and abs(merged_skyline[-1][0] + merged_skyline[-1][1] - seg[0]) < 0.001):
                    merged_skyline[-1][1] += seg[1]
                else:
                    merged_skyline.append(seg)
            skyline = merged_skyline
            simulated_marker_length_inch = max(simulated_marker_length_inch, placed_y_top)

    # 4. ÁP DỤNG BIÊN HAO HỤT VÀ CHU KỲ KẺ CARO THEO VẬT LÝ THỰC TẾ
    if fabric_pattern == "PLAID" and plaid_repeat_inch > 0:
        remainder = simulated_marker_length_inch % plaid_repeat_inch
        if remainder > 0: simulated_marker_length_inch += (plaid_repeat_inch - remainder)

    # Loại bỏ hoàn toàn các hệ số phạt ép định mức cũ. Chỉ giữ hao hụt đầu cây vật lý (0.5 inch)
    global_gross_fabric_consumption_yard = (simulated_marker_length_inch / 36.0) + (0.5 / 36.0)
    
    total_bounding_box_area = geometry_data["total_bounding_box_area"]
    actual_packing_density = total_bounding_box_area / (simulated_marker_length_inch * usable_width) if simulated_marker_length_inch > 0 else 0.82
    actual_packing_density = max(min(actual_packing_density, 0.94), 0.65)

    allocated_shape_fabric_factor = global_gross_fabric_consumption_yard / geometry_data["total_net_shape_area"] if geometry_data["total_net_shape_area"] > 0 else 0.0

    return {
        "fabric_width": geometry_data["fabric_width"], "usable_width": usable_width,
        "fabric_pattern": fabric_pattern, "actual_packing_density": actual_packing_density,
        "allocated_shape_fabric_factor": allocated_shape_fabric_factor,
        "simulated_marker_length_yard": simulated_marker_length_inch / 36.0,
        "global_gross_fabric_consumption": global_gross_fabric_consumption_yard
    }


import pandas as pd
import streamlit as st

# =====================================================================
# 🟩 KHỐI 3b: RENDERING INTERFACE LAYER (ĐỒNG BỘ ĐỊNH MỨC THEO SƠ ĐỒ)
# =====================================================================

if st.session_state.get("bom_data") or st.session_state.get("accumulated_bom_rows"):
    bom_source = st.session_state.get("bom_data", {})
    bom_rows_list = bom_source.get("bom_rows", st.session_state.get("accumulated_bom_rows", []))

    # 1. Thu thập văn bản chat từ session state
    user_query_text = ""
    if st.session_state.get("last_submitted_query"): 
        user_query_text = str(st.session_state.get("last_submitted_query")).lower()
    elif st.session_state.get("ie_workspace_static_chat_input_key"): 
        user_query_text = str(st.session_state.get("ie_workspace_static_chat_input_key")).lower()
    if not user_query_text and st.session_state.get("chat_history"): 
        user_query_text = str(st.session_state.chat_history[-1]["user"]).lower()

    blueprint_final = st.session_state.get("blueprint_final", None)

    # 🚨 Gọi Đoạn 1 & Đoạn 2 của Skyline Engine Pro
    geometry_data = prepare_bom_and_geometry(bom_rows_list, user_query_text, blueprint_final)
    metrics = execute_skyline_placement(geometry_data)
    
    fabric_width = metrics.get("fabric_width", 56.0)
    usable_width = metrics.get("usable_width", 55.0)
    fabric_pattern = metrics.get("fabric_pattern", "SOLID")
    actual_packing_density = metrics.get("actual_packing_density", 0.82)
    allocated_shape_fabric_factor = metrics.get("allocated_shape_fabric_factor", 0.0)
    
    # 🚨 ĐÂY LÀ GIÁ TRỊ ĐỊNH MỨC THỰC TẾ ĐÚNG CỦA SƠ ĐỒ (Ví dụ: ~1.35 YDS)
    global_gross_fabric_consumption = metrics.get("global_gross_fabric_consumption", 0.0)

    warp_shrinkage = geometry_data.get("warp_shrinkage", 0.0)
    weft_shrinkage = geometry_data.get("weft_shrinkage", 0.0)

    piece_metadata_registry = {
        "BODY_FRONT": {"shape_factor": 0.73, "avg_aspect_ratio": 1.35, "min_len": 24.0},
        "BODY_BACK": {"shape_factor": 0.76, "avg_aspect_ratio": 1.40, "min_len": 25.0},
        "TROUSER_FRONT": {"shape_factor": 0.64, "avg_aspect_ratio": 3.20, "min_len": 38.0}, 
        "TROUSER_BACK": {"shape_factor": 0.67, "avg_aspect_ratio": 3.00, "min_len": 39.0}, 
        "WAISTBAND": {"shape_factor": 0.96, "avg_aspect_ratio": 6.00, "min_len": 18.0},
        "MAJOR_PANEL": {"shape_factor": 0.72, "avg_aspect_ratio": 1.50, "min_len": 20.0},
        "MINOR_COMPONENT": {"shape_factor": 0.85, "avg_aspect_ratio": 1.20, "min_len": 4.0}
    }

    display_data = []
    total_fabric_weight_points = 0.0
    
    # VÒNG LẶP 1: Tính toán trọng số diện tích trước để phân bổ chuẩn xác tỷ lệ đóng góp của từng chi tiết
    temp_rows = []
    for r in bom_rows_list:
        if not r or not isinstance(r, dict): continue
        comp_name_raw = str(r.get("component_name", "UNNAMED")).upper().strip()
        mat_class_raw = str(r.get("material_class", "FABRIC")).upper().strip()
        geo_role_raw = str(r.get("geometry_role", "MINOR_COMPONENT")).upper().strip()
        piece_type_ai = str(r.get("piece_type", geo_role_raw)).upper().strip()
        
        pcs_raw = r.get("piece_count")
        raw_l = r.get("bounding_box_length")
        raw_w = r.get("bounding_box_width")
        
        if pcs_raw is None: continue
        pcs = int(pcs_raw)
        meta_item = piece_metadata_registry.get(piece_type_ai, piece_metadata_registry.get(geo_role_raw, piece_metadata_registry["MINOR_COMPONENT"]))
        
        if raw_l is None and raw_w is not None: raw_l = float(raw_w) * meta_item["avg_aspect_ratio"]
        elif raw_w is None and raw_l is not None: raw_w = float(raw_l) / meta_item["avg_aspect_ratio"]
        
        if raw_l is not None and raw_w is not None:
            raw_l, raw_w = float(raw_l), float(raw_w)
            if (any(k in piece_type_ai for k in ["TROUSER", "PANTS"]) or any(k in comp_name_raw for k in ["PANEL", "PANFI", "THÂN"])) and geo_role_raw == "MAJOR_PANEL":
                pcs = max(pcs, 2)
                raw_l = max(raw_l, meta_item["min_len"])
                
            seamed_l, seamed_w = raw_l + (0.44 * 2.0), raw_w + (0.44 * 2.0)
            adj_l = seamed_l * (1.0 + max(0.0, warp_shrinkage) / 100.0)
            adj_w = seamed_w * (1.0 + max(0.0, weft_shrinkage) / 100.0)
            
            box_area_total = adj_l * adj_w * pcs
            if mat_class_raw == "FABRIC":
                total_fabric_weight_points += box_area_total
            
            temp_rows.append((r, comp_name_raw, mat_class_raw, geo_role_raw, piece_type_ai, pcs, raw_l, raw_w, box_area_total, adj_l, adj_w))

    # VÒNG LẶP 2: Khởi tạo dữ liệu hiển thị dòng chi tiết rập
    for row_data in temp_rows:
        r, comp_name_raw, mat_class_raw, geo_role_raw, piece_type_ai, pcs, raw_l, raw_w, box_area_total, adj_l, adj_w = row_data
        status_raw = str(r.get("calculation_status", "READY")).upper().strip()
        confidence = str(r.get("data_confidence", "HIGH")).upper().strip()

        if mat_class_raw == "FABRIC":
            # 🚨 SỬA LỖI PHÂN BỔ: Định mức chi tiết = Định mức tổng sơ đồ * (Diện tích chi tiết / Tổng diện tích vải)
            share_ratio = (box_area_total / total_fabric_weight_points) if total_fabric_weight_points > 0 else 0.0
            gross_consumption = round(global_gross_fabric_consumption * share_ratio, 4)
            calc_chain = f"Skyline Share: Chiếm {share_ratio*100:.1f}% diện tích sơ đồ x Tổng định mức ({global_gross_fabric_consumption:.4f} YDS)"
        elif mat_class_raw in ["FUSING", "LINING"]:
            gross_consumption = round(((box_area_total / usable_width) / 36.0 / 0.78 * 1.04), 4)
            calc_chain = f"Mini-Sơ đồ phụ liệu: Diện tích bao {box_area_total:.1f} in² / Khổ dụng {usable_width} / Eff 78%"
        else:
            gross_consumption, calc_chain = 0.0, f"Phụ liệu {mat_class_raw} bóc tách độc lập."

        display_data.append({
            "Component Name": comp_name_raw, "Material Class": mat_class_raw, "Role/Piece Type": f"{geo_role_raw} ({piece_type_ai})",
            "Số lượng rập (Pcs)": pcs, "Dài sản xuất (L-inch)": round(raw_l, 2), "Rộng sản xuất (W-inch)": round(raw_w, 2),
            "Kiểu sơ đồ tổng": f"{fabric_pattern} LAYOUT", "Dự đoán Mật độ nén": f"{actual_packing_density*100:.1f}%",
            "Gross Consumption": gross_consumption, "Trạng thái dữ liệu": f"🛡️ {confidence} ({status_raw})", "Thuật toán mô phỏng CAD": calc_chain
        })

    # Render bảng biểu lên giao diện Streamlit
    if display_data:
        df_bom = pd.DataFrame(display_data)
        st.markdown('<div class="cad-card">', unsafe_allow_html=True)
        st.markdown('<div class="cad-header" style="background-color: #0E6251;">📦 ADVANCED INDUSTRIAL SUMMARY (THUẬT TOÁN 2D SKYLINE)</div>', unsafe_allow_html=True)
        
        # Nhóm tổng hợp định mức
        df_summary = df_bom.groupby(["Material Class"], as_index=False).agg({"Gross Consumption": "sum"})
        
        # 🚨 KHÓA CHẶT DỮ LIỆU BẢNG TỔNG: Ép giá trị tổng Vải chính phải bằng đúng kết quả thực tế của lõi Skyline
        for idx, row in df_summary.iterrows():
            if row["Material Class"] == "FABRIC":
                df_summary.at[idx, "Gross Consumption"] = global_gross_fabric_consumption
                
        df_summary["Gross Consumption"] = df_summary["Gross Consumption"].round(4)
        df_summary["UOM"] = "YDS"
        
        class_mapping = {"FABRIC": "VẢI CHÍNH (MAIN FABRIC)", "LINING": "VẢI LÓT TÚI (POCKETING LINING)", "FUSING": "KEO LÓT / DỰNG (INTERLINING)"}
        df_summary["Material Class"] = df_summary["Material Class"].map(lambda x: class_mapping.get(x, x))
        st.dataframe(df_summary, use_container_width=True, hide_index=True)
        
        # Thẻ thông tin Insights kỹ thuật từ CAD
        st.info(f"🚀 **FashionINSTA CAD Insights:** Khổ vải: **{fabric_width} in** | Khổ hữu dụng: **{usable_width:.2f} in** | Co rút: Dọc {warp_shrinkage}% / Ngang {weft_shrinkage}% | Mật độ đi sơ đồ: **{actual_packing_density*100:.1f}%** | **TỔNG ĐỊNH MỨC VẢI CHÍNH THỰC TẾ: {global_gross_fabric_consumption:.4f} YDS**")
        st.markdown('</div><br>', unsafe_allow_html=True)
        
        # Thẻ thông tin chi tiết từng rập bán thành phẩm
        st.markdown('<div class="cad-card"><div class="cad-header">📐 DETAILED HYBRID CAD ENGINE (PLACEMENT-BASED)</div>', unsafe_allow_html=True)
        st.dataframe(df_bom, use_container_width=True, hide_index=True, column_config={"Gross Consumption": st.column_config.NumberColumn(format="%.4f")})
        st.markdown('</div>', unsafe_allow_html=True)
