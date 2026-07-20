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
    # 🚨 ĐÃ SỬA: Chuyển về dict trống thay vì None để tránh lỗi crash hệ thống
    st.session_state.bom_data = {}
    st.session_state.chat_history = []
    st.session_state.pdf_bytes = None
    st.session_state.pdf_name = ""
    st.session_state.pdf_text_cache = None
    
    # 🚨 ĐÃ THÊM: Xóa sạch dữ liệu bảng chi tiết CAD và tổng hợp định mức
    if "processed_display_rows" in st.session_state: 
        st.session_state.processed_display_rows = []
    if "accumulated_bom_rows" in st.session_state: 
        st.session_state.accumulated_bom_rows = []
        
    if "last_active_blueprint" in st.session_state: st.session_state.last_active_blueprint = None
    if "raw_ai_debug_payload" in st.session_state: st.session_state.raw_ai_debug_payload = None
    if "pdf_page_one_image" in st.session_state: st.session_state.pdf_page_one_image = None
    
    # Ép hệ thống render lại giao diện trống sạch sẽ ngay lập tức
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
# 🧠 ĐOẠN A (NÂNG CẤP QUET TOÀN DIỆN BOM): KHỐI HÀM CACHE AI (ĐÃ SỬA LỖI KHỔ VẢI)
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
        request_options={"timeout": 120.0},
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
            
            # 🛠️ ĐÃ SỬA: ÉP ĐÈ KHỔ VẢI THEO Ô CHAT VÀO TỪNG DÒNG RẬP CHỐNG KẸT CACHE 56 CŨ
            try:
                forced_width = float(active_width)
                if current_query:
                    width_match = re.search(r"(khổ\s*vải|khổ)\s*(\d+(\.\d+)?)", str(current_query), re.IGNORECASE)
                    if width_match:
                        forced_width = float(width_match.group(2))
                
                # Gán thẳng khổ vải vừa quét động được vào dữ liệu chi tiết rập
                row["fabric_width_inch"] = forced_width
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

    # 🛠️ TRÍCH XUẤT KHỔ VẢI ĐỘNG TỪ Ô CHAT ĐỂ BẺ GÃY SỐ 56 CỐ ĐỊNH
    dynamic_width = 56.0  # Giá trị mặc định phòng hờ
    target_size = "32"    # Cỡ mẫu mặc định
    
    if current_query:
        import re
        width_match = re.search(r"(khổ\s*vải|khổ)\s*(\d+(\.\d+)?)", str(current_query), re.IGNORECASE)
        if width_match:
            dynamic_width = float(width_match.group(2))
            
        size_match = re.search(r"(cỡ|size)\s*(\d+)", str(current_query), re.IGNORECASE)
        if size_match:
            target_size = str(size_match.group(2))

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

                # 3. GỌI HÀM QUÉT AI CACHE VÀ TRUYỀN KHỔ VẢI ĐỘNG ĐÃ TRÍCH XUẤT
                bom_data = execute_cached_gemini_scan(
                    pdf_bytes=active_pdf,
                    current_query=current_query,
                    active_width=dynamic_width,  # ✅ ĐÃ SỬA: Thay số 56.0 cố định cũ bằng biến động dynamic_width
                    target_size_cmd=target_size,
                    raw_json_schema=raw_json_schema,
                    prompt_agent_2=prompt_agent_2
                )
                
                # Lưu kết quả bóc tách vào session_state
                st.session_state["bom_data"] = bom_data
                if bom_data and "bom_rows" in bom_data:
                    st.session_state["accumulated_bom_rows"] = bom_data["bom_rows"]
                
                st.session_state.ai_processing = False
                st.success("✅ AI Core đã đồng bộ cấu trúc rập thành công!")
                st.rerun()

            except Exception as e:
                st.session_state.ai_processing = False
                st.error(f"❌ Lỗi xử lý AI Core Engine: {str(e)}")
                import traceback
                st.text(traceback.format_exc())





# =====================================================================
# 🟩 KHỐI 3a: HÀM TÍNH TOÁN HÌNH HỌC SƠ ĐỒ 2D (SKYLINE ENGINE) - ĐÃ SỬA LỖI KHỔ VẢI
# =====================================================================
def calculate_skyline_2d_metrics(bom_rows_list, user_query_text):
    # Khởi tạo tham số mặc định
    warp_shrinkage, weft_shrinkage, fabric_width = 0.0, 0.0, 56.0
    
    # SỬA LỖI: Thêm re.IGNORECASE để nhận diện chính xác chữ "khổ" hoặc "khổ vải" từ ô chat
    if user_query_text:
        width_match = re.search(r"(khổ\s*vải|khổ)\s*(\d+(\.\d+)?)", user_query_text, re.IGNORECASE)
        if width_match: fabric_width = float(width_match.group(2))
        warp_match = re.search(r"(co\s*rút\s*dọc|dọc)\s*(\d+(\.\d+)?)", user_query_text, re.IGNORECASE)
        if warp_match: warp_shrinkage = float(warp_match.group(2))
        weft_match = re.search(r"(co\s*rút\s*ngang|ngang)\s*(\d+(\.\d+)?)", user_query_text, re.IGNORECASE)
        if weft_match: weft_shrinkage = float(weft_match.group(2))

    # THAY ĐỔI: Khổ vải hữu dụng bằng đúng khổ vải thực tế, không trừ đi 1 inch
    usable_width = fabric_width

    # Nhận diện mẫu vân hoa vải
    fabric_pattern, plaid_repeat_inch, is_one_way_nap = "SOLID", 0.0, False
    if any(k in str(user_query_text).lower() for k in ["sọc", "stripe"]): fabric_pattern = "STRIPE"
    if any(k in str(user_query_text).lower() for k in ["caro", "plaid"]): 
        fabric_pattern = "PLAID"
        repeat_match = re.search(r"(caro|sọc|repeat)\s*(\d+(\.\d+)?)", user_query_text, re.IGNORECASE)
        plaid_repeat_inch = float(repeat_match.group(2)) if repeat_match else 4.0
    if any(k in str(user_query_text).lower() for k in ["tuyết", "nap", "one way", "một chiều"]): fabric_pattern, is_one_way_nap = "NAP", True

    # Ma trận đăng ký thông số Shape Factor
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

    return {
        "fabric_width": fabric_width, "usable_width": usable_width, "warp_shrinkage": warp_shrinkage, "weft_shrinkage": weft_shrinkage,
        "fabric_pattern": fabric_pattern, "actual_packing_density": actual_packing_density, "allocated_shape_fabric_factor": allocated_shape_fabric_factor,
        "constraint_penalty_multiplier": constraint_penalty_multiplier, "piece_metadata_registry": piece_metadata_registry
    }

import pandas as pd
import streamlit as st
import re

# Khởi tạo danh sách chứa dữ liệu sau xử lý hình học CAD
processed_display_rows = []

if st.session_state.get("bom_data") or st.session_state.get("accumulated_bom_rows"):
    # Đọc nguồn dữ liệu gốc từ session_state
    bom_source = st.session_state.get("bom_data", {})
    
    # 1. Trích xuất thông số động thời gian thực trực tiếp từ câu lệnh chat
    user_query_text = ""
    if st.session_state.get("last_submitted_query"): 
        user_query_text = str(st.session_state.get("last_submitted_query"))
    elif st.session_state.get("ie_workspace_static_chat_input_key"): 
        user_query_text = str(st.session_state.get("ie_workspace_static_chat_input_key"))
    if not user_query_text and st.session_state.get("chat_history"): 
        user_query_text = str(st.session_state.chat_history[-1]["user"])

    # Thiết lập thông số mặc định ban đầu phòng hờ từ file gốc
    fabric_width = bom_source.get("fabric_width_inch", 56.0)
    warp_shrinkage = bom_source.get("warp_shrinkage_percent", 0.0)
    weft_shrinkage = bom_source.get("weft_shrinkage_percent", 0.0)
    
    # 🚨 ĐÃ SỬA: Ưu tiên quét size mẫu (Base Size/Sample Size) từ file gốc, không để cứng 32 mặc định
    detected_size = bom_source.get("detected_base_size", bom_source.get("calculated_on_size", "32"))
    target_size = str(detected_size).upper()

    # Quét nhanh thông số từ câu lệnh chat bằng Regex (Chỉ ghi đè nếu người dùng ép thông số khác trong chat)
    if user_query_text:
        w_match = re.search(r"(khổ\s*vải|khổ)\s*(\d+(\.\d+)?)", user_query_text, re.IGNORECASE)
        if w_match: fabric_width = float(w_match.group(2))
        
        warp_match = re.search(r"(co\s*rút\s*dọc|dọc)\s*(\d+(\.\d+)?)", user_query_text, re.IGNORECASE)
        if warp_match: warp_shrinkage = float(warp_match.group(2))
        
        weft_match = re.search(r"(co\s*rút\s*ngang|ngang)\s*(\d+(\.\d+)?)", user_query_text, re.IGNORECASE)
        if weft_match: weft_shrinkage = float(weft_match.group(2))
        
        size_match = re.search(r"(cỡ|size)\s*([a-zA-Z0-9]+)", user_query_text, re.IGNORECASE)
        if size_match: target_size = str(size_match.group(2)).upper()

    # Ghi đè đồng bộ các thông số mới thẳng vào ROOT của bom_source để bộ nhớ hệ thống luôn nhất quán
    bom_source["fabric_width_inch"] = fabric_width
    bom_source["usable_width_inch"] = fabric_width  
    bom_source["warp_shrinkage_percent"] = warp_shrinkage
    bom_source["weft_shrinkage_percent"] = weft_shrinkage
    bom_source["calculated_on_size"] = target_size
    
    st.session_state["bom_data"] = bom_source
    # 🚨 ĐÃ THÊM: Định nghĩa lại các biến số an toàn từ gốc Root đã đồng bộ ở Đoạn 1a
       # Giải nén lại các biến số an toàn từ gốc Root đã đồng bộ ở Đoạn 1a
    usable_width = bom_source.get("fabric_width_inch", 56.0)
    fabric_pattern = bom_source.get("fabric_pattern", "SOLID")
    actual_packing_density = bom_source.get("global_packing_density", 0.85)
    
    bom_rows_list = bom_source.get("bom_rows", st.session_state.get("accumulated_bom_rows", []))

    # Vòng lặp tính toán định mức từng cấu kiện chi tiết rập
    for r in bom_rows_list:
        if not r or not isinstance(r, dict): continue
        
        raw_l = float(r.get("bounding_box_length", 0.0))
        raw_w = float(r.get("bounding_box_width", 0.0))
        pcs = int(r.get("piece_count", 1))
        mat_class_raw = str(r.get("material_class", "FABRIC")).upper().strip()
        
        comp_name_raw = str(r.get("component_name", "UNNAMED")).upper().strip()
        geo_role_raw = str(r.get("geometry_role", "MINOR_COMPONENT")).upper().strip()
        piece_type_ai = str(r.get("piece_type", geo_role_raw)).upper().strip()
        combined_str = f" {comp_name_raw} {piece_type_ai} "  # Thêm khoảng trắng để quét chính xác từ khóa
        
        status_raw = str(r.get("calculation_status", "READY")).upper().strip()
        confidence = str(r.get("data_confidence", "HIGH")).upper().strip()

        # Quy tắc 1: Kiểm tra chi tiết có phải là Nút áo/quần hay không
        is_button = any(k in combined_str for k in [" BUTTON ", " NÚT ", " NUT ", " KHUY "])

        # Quy tắc 2: SỬA LỖI MẤT LAI ÁO - Nếu là lai/gấu áo bị thiếu kích thước, tự bù thông số tiêu chuẩn sản xuất
        if raw_l == 0.0 or raw_w == 0.0:
            if any(k in combined_str for k in [" BOTTOM HEM ", " LAI ÁO ", " LAI AO ", " GẤU ÁO "]):
                raw_l = 38.0 if raw_l == 0.0 else raw_l  
                raw_w = 1.75 if raw_w == 0.0 else raw_w  
                r["bounding_box_length"] = raw_l
                r["bounding_box_width"] = raw_w

        # Điều kiện chạy tính toán hình học: Có chiều dài rập HOẶC là chi tiết Nút tính chiếc
        if raw_l > 0 or is_button:
            # Nhân tỉ lệ co rút động đã đồng bộ vào kích thước rập sản xuất
            adj_l = raw_l * (1 + warp_shrinkage / 100.0)
            adj_w = raw_w * (1 + weft_shrinkage / 100.0) if raw_w > 0 else raw_w
            
            # --- KHỐI LỌC AI: PHÂN TÁCH LỚP CHUẨN ĐÃ KHỬ LỖI QUẦN JEAN ---
            layer_multiplier = 1
            is_two_layers = False
            is_four_layers = False
            pocket_note = ""
            
            is_pant_component = any(k in combined_str for k in ["TROUSER", "PANT", "JEAN", "DENIM", "SLIDER", "FLY", "LEG", "WAISTBAND", "YOKE"])

            # Khử hoàn toàn lỗi nhân đôi lớp cho Đô quần (YOKE) và Lưng quần (WAISTBAND)
            if "YOKE" in combined_str or "ĐÔ" in combined_str:
                layer_multiplier = 1  
                is_two_layers = False
            elif "WAISTBAND" in combined_str or "LƯNG" in combined_str or "CẠP" in combined_str:
                layer_multiplier = 1  
                is_two_layers = False
            else:
                double_layer_jacket_keywords = [" CUFF ", " CÚP TAY ", " CUP TAY ", " MĂNG SÉT ", " BOTTOM HEM ", " LAI ÁO "]
                if any(k in combined_str for k in double_layer_jacket_keywords) and not is_pant_component:
                    layer_multiplier = 2
                    is_two_layers = True
                elif any(k in combined_str for k in [" FLAP ", " NẮP TÚI ", " NAP TUI "]):
                    layer_multiplier = 4
                    is_four_layers = True

            # Xử lý Bao túi mổ quần
            is_pocket_bag = any(k in combined_str for k in ["POCKET BAG", "BAO TÚI", "BAO TUI", "LINING POCKET"])
            is_welt_pocket = any(k in combined_str for k in ["WELT", "TÚI MỔ", "TUI MO"])
            
            if is_pocket_bag or is_welt_pocket:
                pocket_note = f" [Túi mổ - Dùng {mat_class_raw} theo BOM]"
                if is_pocket_bag:
                    layer_multiplier = 2
                    is_two_layers = True

            if is_four_layers:
                pcs_display = f"{pcs} Pcs (x4 lớp)"
            elif is_two_layers:
                pcs_display = f"{pcs} Pcs (x2 lớp)"
            else:
                pcs_display = f"{pcs} Pcs"

            # Kiểm tra đỉa quần (PASSAN)
            is_belt_loop = any(k in combined_str for k in ["BELT LOOP", "BELT_LOOP", "ĐỈA", "DIA ", "PASSAN"])

            # 📏 THUẬT TOÁN ĐỊNH MỨC THEO PHÂN LOẠI VẬT TƯ
            if is_button:
                mat_class_raw = "ACCESSORY" if mat_class_raw in ["FABRIC", "TRIM"] else mat_class_raw
                gross_consumption = round((pcs * layer_multiplier * 1.03), 2)
                calc_chain = f"Đếm chiếc phụ liệu: {pcs} cái * Hao hụt"
                pcs_display = f"{pcs} Cái"
                
            else:
                is_binding_fabric = ("BINDING" in combined_str or "VIỀN" in combined_str) and (mat_class_raw == "FABRIC")
                
                # 🚨 ĐÃ SỬA: Loại bỏ hoàn toàn BELT_LOOP khỏi nhóm dải cuộn dọc mua ngoài (is_roll_trim = False)
                # Hệ thống ép Passan vải chính phải tính theo sơ đồ diện tích hình học mảng lớn Layout chung
                is_roll_trim = any(k in combined_str for k in [
                    "ELASTIC", "THUN", "ZIPPER", "KHÓA", "KHOA", "HANGER", "LOOP", "LABEL", "TAG"
                ]) or (("BINDING" in combined_str or "VIỀN" in combined_str) and mat_class_raw != "FABRIC")

                if is_roll_trim and not is_binding_fabric and not is_belt_loop:
                    # Công thức tính phụ liệu dải dọc cuộn mua sẵn bên ngoài
                    gross_consumption = round(((adj_l * pcs * layer_multiplier) / 36.0 * 1.04), 4)
                    calc_chain = f"Dải cuộn dọc: L-inch / 36.0"
                else:
                    # 🗺️ THUẬT TOÁN ĐỒNG BỘ: TÍNH THEO SƠ ĐỒ LAYOUT ĐA GIÁC (Dành cho Vải chính, Bao túi và cả Passan)
                    if any(k in combined_str for k in ["PANEL", "FRONT", "BACK", "THÂN"]):
                        # 🚨 ĐÃ SỬA: Nâng hệ số đa giác hình học rập thân quần lên mức chuẩn cao để tránh định mức thấp
                        shape_factor = 0.88 if "BACK" in combined_str else 0.84
                    elif "BINDING" in combined_str or "VIỀN" in combined_str or is_belt_loop:
                        shape_factor = 0.96  # Băng đỉa, băng viền đi thẳng khít, hệ số nén sơ đồ tuyệt đối
                    else:
                        shape_factor = 0.76
                        
                    if any(k in combined_str for k in ["WAISTBAND", "LƯNG", "COLLAR", "CỔ", "BO"]):
                        shape_factor = 0.94

                    # Phép toán nhân diện tích sơ đồ bàn cắt chuẩn công nghiệp
                    seamed_l = adj_l + (0.44 * 2.0)
                    seamed_w = adj_w + (0.44 * 2.0)
                    piece_area = seamed_l * seamed_w * shape_factor * pcs * layer_multiplier
                    
                    if usable_width > 0:
                        efficiency_factor = actual_packing_density if actual_packing_density > 0 else 0.85
                        gross_consumption = round(((piece_area / usable_width) / 36.0 / efficiency_factor), 4)
                        layer_note = " nhân lớp" if (is_two_layers or is_four_layers) else ""
                        
                        if is_belt_loop:
                            calc_chain = f"Sơ đồ Layout diện tích Passan: Eff {efficiency_factor*100:.1f}%"
                        else:
                            calc_chain = f"Sơ đồ {mat_class_raw} Layout: Eff {efficiency_factor*100:.1f}% / Khổ {usable_width}\"{layer_note}"
                    else:
                        gross_consumption = 0.0
                        calc_chain = "❌ Lỗi: Khổ vải dụng bằng 0!"
        else:
            gross_consumption = 0.0
            pcs_display = f"{pcs} Pcs"
            calc_chain = "❌ Bỏ qua: Thiếu kích thước rập đầu vào!"

        processed_display_rows.append({
            "Component Name": comp_name_raw, "Material Class": mat_class_raw, "Role/Piece Type": f"{geo_role_raw} ({piece_type_ai})",
            "Số lượng rập": pcs_display, "Dài sản xuất (L-inch)": raw_l, "Rộng sản xuất (W-inch)": raw_w,
            "Kiểu sơ đồ tổng": f"{fabric_pattern} LAYOUT", "Dự đoán Mật độ nén": f"{actual_packing_density*100:.1f}%",
            "Gross Consumption": gross_consumption, "Trạng thái dữ liệu": f"🛡️ {confidence} ({status_raw})", "Thuật toán mô phỏng CAD": calc_chain
        })

    st.session_state["processed_display_rows"] = processed_display_rows




# Lấy trực tiếp dữ liệu bền vững từ st.session_state gán ở Đoạn 1b
display_rows_source = st.session_state.get("processed_display_rows", [])

if display_rows_source:
    df_bom = pd.DataFrame(display_rows_source)
    
    st.markdown('<div class="cad-card">', unsafe_allow_html=True)
    st.markdown(
        '<div class="cad-header" style="background-color: #0E6251; color: white; padding: 10px; font-weight: bold; border-radius: 4px 4px 0 0;">'
        '📦 ADVANCED INDUSTRIAL SUMMARY (THUẬT TOÁN ĐỒNG BỘ GERBER ACCUMULATION)'
        '</div>', 
        unsafe_allow_html=True
    )
    
    # 1. XỬ LÝ BẢNG TỔNG HỢP ĐỊNH MỨC (SUMMARY)
    df_summary = df_bom.groupby(["Material Class"], as_index=False).agg({"Gross Consumption": "sum"})
    df_summary["Gross Consumption"] = df_summary["Gross Consumption"].round(4)
    df_summary["UOM"] = "YDS"
    
    class_mapping = {
        "FABRIC": "VẢI CHÍNH (MAIN FABRIC)",
        "FUSING": "KEO/DỰNG (FUSING)",
        "LINING": "VẢI LÓT/BAO TÚI (LINING)",
        "ACCESSORY": "PHỤ LIỆU ĐẾM CHIẾC (ACCESSORY)"
    }
    df_summary["Phân loại vật tư"] = df_summary["Material Class"].map(lambda x: class_mapping.get(x, f"PHỤ LIỆU KHÁC ({x})"))
    
    # Hiển thị bảng tổng hợp lên giao diện
    st.subheader("Bảng tổng hợp định mức (BOM Summary)")
    st.dataframe(df_summary[["Phân loại vật tư", "Gross Consumption", "UOM"]], use_container_width=True)
    
    # 2. HIỂN THỊ BẢNG CHI TIẾT TỪNG CHI TIẾT RẬP (DETAILED CAD)
    st.subheader("Bảng chi tiết cấu trúc rập (Bộ lọc thông minh Bao túi mổ)")
    st.dataframe(df_bom, use_container_width=True)
    
    # 3. HIỂN THỊ THÔNG BÁO THÔNG SỐ ĐỘNG TỪ AI (Đọc chuẩn size mẫu từ file)
    bom_source = st.session_state.get("bom_data", {})
    if not isinstance(bom_source, dict): 
        bom_source = {}
        
    current_size = bom_source.get("calculated_on_size", "Mẫu")
    current_warp = bom_source.get("warp_shrinkage_percent", 0.0)
    current_weft = bom_source.get("weft_shrinkage_percent", 0.0)
    current_width = bom_source.get("fabric_width_inch", 56.0)
    
    st.markdown(
        f'<p style="color: #7F8C8D; font-size: 0.85rem; margin-top: 10px; font-style: italic;">'
        f'🤖 AI ghi nhận lệnh tính toán: Tính định mức dựa trên <b>Size may mẫu: {current_size}</b> quét từ Techpack | Khổ vải: <b>{current_width}"</b> | '
        f'Co rút dọc: <b>{current_warp}%</b> | Co rút ngang: <b>{current_weft}%</b>.'
        f'</p>', 
        unsafe_allow_html=True
    )
    
    st.markdown('</div>', unsafe_allow_html=True)
else:
    # Khi bấm Clear Memory hoặc chưa nạp file, hệ thống hiển thị dòng này một cách an toàn tránh lỗi sập giao diện
    st.info("🔄 Bộ nhớ hệ thống đã được làm sạch. Vui lòng nạp file Techpack hoặc nhập câu lệnh mới để tính toán.")
