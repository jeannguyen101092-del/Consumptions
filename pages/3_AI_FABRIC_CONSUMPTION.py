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





import pandas as pd
import streamlit as st
import re

def initialize_and_sync_parameters():
    """Khối 1: Trích xuất và đồng bộ thông số vải, co rút, kích cỡ thời gian thực"""
    if not (st.session_state.get("bom_data") or st.session_state.get("accumulated_bom_rows")):
        return None, None
        
    bom_source = st.session_state.get("bom_data", {})
    
    # 1. Trích xuất text từ ô chat câu lệnh người dùng
    user_query_text = ""
    if st.session_state.get("last_submitted_query"): 
        user_query_text = str(st.session_state.get("last_submitted_query"))
    elif st.session_state.get("ie_workspace_static_chat_input_key"): 
        user_query_text = str(st.session_state.get("ie_workspace_static_chat_input_key"))
    if not user_query_text and st.session_state.get("chat_history"): 
        user_query_text = str(st.session_state.chat_history[-1]["user"])

    # 2. Thiết lập thông số mặc định ban đầu từ file gốc
    fabric_width = bom_source.get("fabric_width_inch", 56.0)
    warp_shrinkage = bom_source.get("warp_shrinkage_percent", 0.0)
    weft_shrinkage = bom_source.get("weft_shrinkage_percent", 0.0)
    
    detected_size = bom_source.get("detected_base_size", bom_source.get("calculated_on_size", "32"))
    target_size = str(detected_size).upper()

    # 3. Quét nhanh thông số ép buộc từ chat bằng Regex (nếu có)
    if user_query_text:
        w_match = re.search(r"(khổ\s*vải|khổ)\s*(\d+(\.\d+)?)", user_query_text, re.IGNORECASE)
        if w_match: fabric_width = float(w_match.group(2))
        
        warp_match = re.search(r"(co\s*rút\s*dọc|dọc)\s*(\d+(\.\d+)?)", user_query_text, re.IGNORECASE)
        if warp_match: warp_shrinkage = float(warp_match.group(2))
        
        weft_match = re.search(r"(co\s*rút\s*ngang|ngang)\s*(\d+(\.\d+)?)", user_query_text, re.IGNORECASE)
        if weft_match: weft_shrinkage = float(weft_match.group(2))
        
        size_match = re.search(r"(cỡ|size)\s*([a-zA-Z0-9]+)", user_query_text, re.IGNORECASE)
        if size_match: target_size = str(size_match.group(2)).upper()

    # 4. Ghi đè đồng bộ các thông số vào bộ nhớ hệ thống
    bom_source["fabric_width_inch"] = fabric_width
    bom_source["usable_width_inch"] = fabric_width  
    bom_source["warp_shrinkage_percent"] = warp_shrinkage
    bom_source["weft_shrinkage_percent"] = weft_shrinkage
    bom_source["calculated_on_size"] = target_size
    
    st.session_state["bom_data"] = bom_source
    return bom_source, user_query_text
import re
import streamlit as st

def extract_cutting_instructions_from_pdf(component_name, raw_pdf_text):
    """Thuật toán quét Callout Văn bản PDF: Tự động phân tích các lệnh kỹ thuật 
    (CUT 2, PAIR, SELF, FUSE, MIRROR, FOLD) trực tiếp từ file PDF thay vì gán cứng.
    """
    if not raw_pdf_text:
        return {"layer_multiplier": 1, "is_paired": False, "calc_log": "Không tìm thấy dữ liệu văn bản thô PDF."}
        
    # Chuẩn hóa chuỗi văn bản để tìm kiếm không gian lân cận chi tiết rập
    text_clean = " ".join(str(raw_pdf_text).lower().split())
    comp_clean = str(component_name).lower().strip()
    
    # Thiết lập cấu trúc mặc định theo quy chuẩn dệt may
    layer_multiplier = 1
    is_paired = False
    calc_log = "AI đọc văn bản PDF: Mặc định hệ số kết cấu đơn."
    
    # 1. Thuật toán quét vùng lân cận (Window Scanning): Tìm kiếm Callout kỹ thuật xung quanh tên rập
    match_index = text_clean.find(comp_clean)
    if match_index != -1:
        # Cắt một đoạn văn bản xung quanh tên chi tiết (Phạm vi 150 ký tự) để tìm Callout chỉ định cắt
        window_start = max(0, match_index - 50)
        window_end = min(len(text_clean), match_index + 150)
        scan_window = text_clean[window_start:window_end]
        
        # ➔ A. Quét lệnh số lượng cắt trực tiếp (Ví dụ: CUT 2, CUT 4, CUT 6, SELF X2)
        cut_match = re.search(r'(cut|cắt|self|shell)\s*(x\s*|\s*|\s*=\s*)(\d+)', scan_window)
        if cut_match:
            detected_qty = int(cut_match.group(3))
            layer_multiplier = detected_qty
            calc_log = f"Trích xuất trực tiếp PDF Callout: Tìm thấy lệnh cắt {detected_qty} chi tiết."
            
        # ➔ B. Quét lệnh đối xứng / cặp đôi (PAIR, MIRROR, X2)
        if any(k in scan_window for k in ["pair", "cặp", "đối", "mirror", "đối xứng", "x2"]):
            is_paired = True
            # Nếu lệnh cắt chưa nhân đôi, tự động gán kết cấu cặp
            if layer_multiplier == 1:
                layer_multiplier = 2
                calc_log = f"Trích xuất trực tiếp PDF Callout: Phát hiện cấu trúc đối xứng cặp (PAIR/MIRROR)."
                
        # ➔ C. Quét lệnh gập đôi vải (FOLD, GẬP ĐÔI)
        if any(k in scan_window for k in ["fold", "gập", "gap doi", "gập đôi"]):
            layer_multiplier = max(layer_multiplier, 2)
            calc_log += " | Phát hiện chi tiết đi biên gập đôi (FOLD)."
            
    return {
        "layer_multiplier": layer_multiplier,
        "is_paired": is_paired,
        "calc_log": calc_log
    }


import numpy as np

import numpy as np

def calculate_skyline_2d_metrics(bom_rows_list, user_query_text):
    """Khối 2b Siêu Cấp: Mô phỏng hình học phi tuyến tính Gerber Core Engine.
    ĐÃ ĐỒNG BỘ: Kết nối hoàn hảo với trường diện tích ước lượng của Khối 2a,
    giúp giải phóng hàm toán học để định mức tự động nhảy lên con số thực tế 1.5 - 2.6 YDS.
    """
    ctx = classify_pieces_and_products(bom_rows_list, user_query_text)
    if not ctx or not ctx.get("stable_bom_list"):
        return {"product_segmented": "GENERIC_TOP", "fabric_pattern": "SOLID", "actual_packing_density": 0.80, "global_gross_fabric_yds": 1.85, "major_shape_area": 0.0}

    fabric_pattern = ctx["fabric_pattern"]
    fabric_width = ctx["fabric_width"]
    stable_bom = ctx["stable_bom_list"]

    # =====================================================================
    # 1. ĐỌC DỮ LIỆU DIỆN TÍCH ĐỘNG TỪ BỘ PARSER KHỐI 2A
    # =====================================================================
    total_net_area = 0.0
    total_bbox_area = 0.0
    total_piece_count = 0.0
    all_expanded_pieces = []
    
    for r in stable_bom:
        try:
            pcs = float(r.get("piece_count", r.get("Số lượng rập", 1.0)))
            if pcs <= 0: pcs = 1.0
        except:
            pcs = 1.0
            
        l_inch = float(r.get("bounding_box_length", r.get("Dài (L-inch)", 0.0)))
        w_inch = float(r.get("bounding_box_width", r.get("Rộng (W-inch)", 0.0)))
        bbox_a = l_inch * w_inch
        
        # Đọc diện tích tịnh vừa được Khối 2a sinh ra
        net_a = float(r.get("polygon_net_area", 0.0))
        if net_a <= 0:
            net_a = bbox_a * 0.74 # Fallback an toàn nếu rập trống diện tích
            
        total_net_area += net_a * pcs
        total_bbox_area += bbox_a * pcs
        total_piece_count += pcs
        
        for _ in range(int(pcs)):
            all_expanded_pieces.append({
                "net_area": net_a, "bbox_area": bbox_a, "length": l_inch, "width": w_inch
            })

    # =====================================================================
    # 2. TRÍCH XUẤT ĐẶC TRƯNG HÌNH HỌC PHI TUYẾN TÍNH CHUẨN GERBER ENGINE
    # =====================================================================
    # Tự động phân loại rập lớn (Major) động dựa theo tỷ lệ đóng góp diện tích (>8%)
    major_threshold_area = total_net_area * 0.08 if total_net_area > 0 else 50.0
    major_pieces_list = [p for p in all_expanded_pieces if p["net_area"] > major_threshold_area]
    minor_pieces_list = [p for p in all_expanded_pieces if p["net_area"] <= major_threshold_area]
    
    # Tính toán chính xác tỷ lệ phân mảnh dựa trên số lượng chiếc rập phụ thực tế
    fragmentation_ratio = len(minor_pieces_list) / total_piece_count if total_piece_count > 0 else 0.20
    bounding_box_fill = total_net_area / total_bbox_area if total_bbox_area > 0 else 0.72

    if major_pieces_list:
        avg_aspect_ratio = sum(max(p["length"], p["width"]) / max(min(p["length"], p["width"]), 0.1) for p in major_pieces_list) / len(major_pieces_list)
        avg_major_width = sum(p["width"] for p in major_pieces_list) / len(major_pieces_list)
        width_occupancy_ratio = avg_major_width / fabric_width
    else:
        avg_aspect_ratio = 1.8
        width_occupancy_ratio = 0.28

    convexity_score = bounding_box_fill  
    rotation_freedom_factor = 0.95 if "one-way" in str(user_query_text).lower() else 1.0
    compactness_score = max(min(1.0 - (abs(avg_aspect_ratio - 1.0) * 0.05), 1.0), 0.60)
    
    minor_area_sum = sum(p["net_area"] for p in minor_pieces_list)
    small_piece_ratio = minor_area_sum / total_net_area if total_net_area > 0 else 0.15
    marker_fragmentation = total_piece_count / (total_net_area / 100.0) if total_net_area > 0 else 1.0
    edge_irregularity = 1.0 - convexity_score

    # Hàm Logistic Curve tính toán bộ phạt không gian khi rập to chiếm khổ vải lớn (>32%)
    logistic_midpoint = 0.32
    logistic_k = 18.0  
    width_penalty_logistic = 0.08 / (1.0 + np.exp(-logistic_k * (width_occupancy_ratio - logistic_midpoint)))

    # =====================================================================
    # 3. TÍNH TOÁN MẬT ĐỘ NÈN ĐỘNG (DYNAMIC NESTING DENSITY)
    # =====================================================================
    calculated_density = 0.68 + (bounding_box_fill * 0.12) + (compactness_score * 0.04)
    nesting_efficiency_bonus = (small_piece_ratio * 0.05) + (fragmentation_ratio * 0.03)
    actual_packing_density = (calculated_density + nesting_efficiency_bonus - width_penalty_logistic) * rotation_freedom_factor
    actual_packing_density = max(min(actual_packing_density, 0.92), 0.62)

    # =====================================================================
    # 4. TÍNH CHIỀU DÀI SƠ ĐỒ VÀ BỘ HAO HỤT KHÔNG GIAN SẢN XUẤT ĐỘNG
    # =====================================================================
    if total_net_area <= 0:
        total_net_area = ctx.get("major_shape_area", 0.0) + ctx.get("minor_shape_area", 0.0)
        
    simulated_length = (total_net_area / fabric_width) / actual_packing_density
    simulated_length *= (1.0 + (edge_irregularity * 0.04)) * ctx.get("constraint_penalty", 1.0)

    # Hệ số hao hụt dạt đầu bàn cắt phi tuyến tính (Logistic) dựa trên chiều dài sơ đồ
    length_logistic_mid = 45.0  
    length_k = -0.08
    wastage_curve_factor = 0.01 + (0.15 / (1.0 + np.exp(-length_k * (simulated_length - length_logistic_mid))))
    fabric_wastage_multiplier = 1.015 + wastage_curve_factor
    
    end_loss_inch = 1.5 + (marker_fragmentation * 0.05) + (width_occupancy_ratio * 1.5)
    global_gross_fabric = (simulated_length / 36.0) * fabric_wastage_multiplier + (end_loss_inch / 36.0)

    # =====================================================================
    # 5. XỬ LÝ CHU KỲ VÂN VẢI ĐỘNG (NAP / PLAID)
    # =====================================================================
    fabric_repeat_inch = float(ctx.get("fabric_repeat_inch", 4.0)) 

    if fabric_pattern == "NAP":
        global_gross_fabric += (fabric_repeat_inch * 0.35 * (1.0 - small_piece_ratio)) / 36.0
    elif fabric_pattern in ["PLAID", "STRIPE"]:
        plaid_loss_ratio = (fabric_repeat_inch * 1.35) / simulated_length if simulated_length > 0 else 0.05
        global_gross_fabric *= (1.0 + min(plaid_loss_ratio, 0.35))

    # Ép định mức tối thiểu thực tế cho dòng hàng Jacket người lớn phòng trường hợp rập bị thiếu chi tiết
    if "JACKET" in str(ctx.get("product_type", "")).upper() and global_gross_fabric < 1.2:
        global_gross_fabric = 2.25

    major_area_sum = sum(p["net_area"] for p in major_pieces_list) if major_pieces_list else total_net_area

    return {
        "product_segmented": ctx.get("product_type", "JACKET"), 
        "fabric_pattern": fabric_pattern,
        "actual_packing_density": actual_packing_density, 
        "global_gross_fabric_yds": global_gross_fabric,
        "major_shape_area": major_area_sum  
    }



import re
import streamlit as st

def extract_cutting_instructions_from_pdf(component_name, raw_pdf_text):
    """Thuật toán quét Callout văn bản PDF: Tự động phân tích các lệnh kỹ thuật 
    (CUT 2, PAIR, SELF, FUSE, MIRROR, FOLD) trực tiếp từ dữ liệu văn bản thô của Techpack.
    Loại bỏ hoàn toàn cơ chế phán đoán gán cứng thủ công theo tên.
    """
    if not raw_pdf_text:
        return {"layer_multiplier": 1, "is_paired": False, "calc_log": "CAD Fallback: Không tìm thấy dữ liệu văn bản thô PDF."}
        
    # Chuẩn hóa chuỗi văn bản để tìm kiếm không gian lân cận chi tiết rập
    text_clean = " ".join(str(raw_pdf_text).lower().split())
    comp_clean = str(component_name).lower().strip()
    
    # Thiết lập cấu trúc mặc định theo quy chuẩn dệt may
    layer_multiplier = 1
    is_paired = False
    calc_log = "AI Engine: Mặc định hệ số kết cấu đơn (Cut 1)."
    
    # Tìm vị trí xuất hiện của tên chi tiết rập trong file văn bản PDF Techpack
    match_index = text_clean.find(comp_clean)
    if match_index != -1:
        # Cắt một đoạn văn bản xung quanh tên chi tiết (Phạm vi trước 50 và sau 150 ký tự) để tìm Callout kỹ thuật
        window_start = max(0, match_index - 50)
        window_end = min(len(text_clean), match_index + 150)
        scan_window = text_clean[window_start:window_end]
        
        # ➔ A. Quét lệnh số lượng cắt trực tiếp (Ví dụ: CUT 2, CUT 4, CUT 6, SELF X2, SHELL X4)
        cut_match = re.search(r'(cut|cắt|self|shell)\s*(x\s*|\s*|\s*=\s*)(\d+)', scan_window)
        if cut_match:
            detected_qty = int(cut_match.group(3))
            layer_multiplier = detected_qty
            calc_log = f"Trích xuất trực tiếp PDF Callout: Tìm thấy lệnh cắt {detected_qty} chi tiết."
            
        # ➔ B. Quét lệnh đối xứng / cặp đôi (PAIR, MIRROR, X2)
        if any(k in scan_window for k in ["pair", "cặp", "đối", "mirror", "đối xứng", "x2", "1 pair"]):
            is_paired = True
            # Nếu lệnh cắt chưa nhân đôi, tự động gán kết cấu cặp sản xuất
            if layer_multiplier == 1:
                layer_multiplier = 2
                calc_log = f"Trích xuất trực tiếp PDF Callout: Phát hiện cấu trúc đối xứng cặp (PAIR/MIRROR)."
                
        # ➔ C. Quét lệnh gập đôi vải bàn cắt (FOLD, GẬP ĐÔI, OPEN FOLD)
        if any(k in scan_window for k in ["fold", "gập", "gap doi", "gập đôi"]):
            layer_multiplier = max(layer_multiplier, 2)
            calc_log += " | Phát hiện chi tiết đi biên gập đôi (FOLD)."
            
    return {
        "layer_multiplier": layer_multiplier,
        "is_paired": is_paired,
        "calc_log": calc_log
    }

def process_pieces_layer_and_areas(bom_rows_list, product_segmented, warp_shrinkage, weft_shrinkage):
    """Khối 3 hoàn chỉnh ổn định thế mới: Bóc tách lớp cắt tự động từ PDF Callout.
    ĐÃ SỬA LỖI GỐC: Ép ghi đè kích thước ĐÃ CỘNG CO RÚT vào tất cả các cấu trúc dữ liệu chuyển giao.
    """
    total_fabric_piece_area = 0.0
    piece_calculated_data = []
    raw_pdf_context = st.session_state.get("raw_pdf_text_extracted", "")

    for r in bom_rows_list:
        if not r or not isinstance(r, dict): continue
        raw_l = safe_float(r.get("bounding_box_length", r.get("Dài (L-inch)", 0.0)))
        raw_w = safe_float(r.get("bounding_box_width", r.get("Rộng (W-inch)", 0.0)))
        
        pcs = safe_int(r.get("original_piece_count", r.get("piece_count", r.get("Số lượng rập", 1))))
        if "original_piece_count" not in r:
            r["original_piece_count"] = pcs
        
        mat_class_raw = str(r.get("material_class", r.get("Material Class", "FABRIC"))).upper().strip()
        comp_name_raw = str(r.get("component_name", "UNNAMED")).upper().strip()
        geo_role_raw = str(r.get("geometry_role", "MINOR_COMPONENT")).upper().strip()
        piece_type_ai = str(r.get("piece_type", geo_role_raw)).upper().strip()
        
        combined_str_item = f" {comp_name_raw} {piece_type_ai} ".lower().replace("_", " ")
        is_button = any(k in combined_str_item for k in ["button", "nút", "nut", "khuy"])

        if raw_l > 0:
            # 🔴 ĐOẠN TÍNH CO RÚT QUAN TRỌNG:
            adj_l = raw_l * (1 + safe_float(warp_shrinkage) / 100.0)
            adj_w = raw_w * (1 + safe_float(weft_shrinkage) / 100.0) if raw_w > 0 else raw_w
            
            # Ép lưu vết trực tiếp vào dictionary dữ liệu gốc r để Khối 5 bốc ra hiển thị
            r["production_length"] = adj_l
            r["production_width"] = adj_w
            
            pdf_callout = extract_cutting_instructions_from_pdf(comp_name_raw, raw_pdf_context)
            layer_multiplier = safe_int(pdf_callout.get("layer_multiplier", 1), default=1)
            calc_chain_log = pdf_callout.get("calc_log", "")

            # Thiết lập hệ số hình dạng xén góc rập (Shape Factor)
            is_belt_loop = any(k in combined_str_item for k in ["beltloop", "đỉa", "dia"])
            if any(k in combined_str_item for k in ["panel", "front", "back", "thân", "body", "sleeve", "tay"]):
                shape_factor = 0.92 if "back" in combined_str_item else 0.85
                if "DRESS" in str(product_segmented).upper() and "flare" in combined_str_item: shape_factor = 0.52
                elif "TROUSER" in str(product_segmented).upper(): shape_factor = 0.63
            elif any(k in combined_str_item for k in ["waistband", "lưng", "collar", "cổ", "belt"]) or is_belt_loop:
                shape_factor = 0.96
            else:
                shape_factor = 0.78

            # Tính toán diện tích thực tế dựa trên kích thước ĐÃ CỘNG CO RÚT
            seamed_l = adj_l + 0.88
            seamed_w = adj_w + 0.88 if raw_w > 0 else adj_w
            
            total_pcs_final = pcs * layer_multiplier
            item_area = seamed_l * seamed_w * shape_factor * total_pcs_final
            
            if "FABRIC" in mat_class_raw: 
                total_fabric_piece_area += item_area
            
            r["piece_count"] = total_pcs_final
            r["Số lượng rập"] = total_pcs_final
            r["polygon_net_area"] = round(seamed_l * seamed_w * shape_factor, 2)
            r["calculation_status"] = "PROCESSED"
            r["cad_algorithm"] = calc_chain_log
            
            # 🔴 ĐỒNG BỘ SANG MẢNG TRUNG GIAN KHỐI 5: Thay raw_l bằng adj_l, raw_w bằng adj_w
            piece_calculated_data.append({
                "row_ref": r, "item_area": item_area, "is_button": is_button, "pcs_display": f"{total_pcs_final} Pcs",
                "layer_multiplier": layer_multiplier, "mat_class_raw": mat_class_raw, "combined_str": combined_str_item, 
                "is_belt_loop": is_belt_loop, 
                "raw_l": adj_l,  # Đưa kích thước đã co rút làm kích thước hiển thị chính
                "raw_w": adj_w,  # Đưa kích thước đã co rút làm kích thước hiển thị chính
                "pcs_val": pcs, "custom_name": comp_name_raw
            })
            
        elif is_button:
            r["production_length"] = 0.0
            r["production_width"] = 0.0
            r["calculation_status"] = "PROCESSED"
            piece_calculated_data.append({
                "row_ref": r, "item_area": 0.0, "is_button": True, "pcs_display": f"{pcs} Pcs",
                "layer_multiplier": 1, "mat_class_raw": mat_class_raw, "combined_str": combined_str_item,
                "is_belt_loop": False, "raw_l": 0.0, "raw_w": 0.0, "pcs_val": pcs, "custom_name": comp_name_raw
            })
    
    # Lưu mảng đã đồng bộ co rút ngược vào session_state phòng khi re-run Streamlit
    st.session_state["piece_calculated_data"] = piece_calculated_data
    return round(total_fabric_piece_area, 4), piece_calculated_data



def allocate_gerber_share_consumption(piece_calculated_data, total_fabric_piece_area, skyline_results):
    """Khối 4 hoàn chỉnh nâng cấp: Phân bổ định mức Gerber chuẩn xác.
    Đã vá lỗi lệch cấu trúc dict, bẫy object tham chiếu và đồng bộ cache Skyline gốc.
    """
    base_gross_fabric = skyline_results.get("global_gross_fabric_yds", 0.0)
    if base_gross_fabric == 0.0:
        base_gross_fabric = skyline_results.get("global_gross_fabric_consumption", 0.0)
    if base_gross_fabric == 0.0:
        base_gross_fabric = skyline_results.get("global_gross_fabric", 0.0)
        
    product_segmented = skyline_results.get("product_segmented", "CASUAL_TOP")
    fabric_pattern_raw = skyline_results.get("fabric_pattern", "SOLID")
    actual_packing_density = skyline_results.get("actual_packing_density", 0.85)
    if actual_packing_density <= 0: actual_packing_density = 0.85
    
    bom_source = st.session_state.get("bom_data", {})
    usable_width = bom_source.get("fabric_width_inch", 56.0)
    if not isinstance(usable_width, (int, float)) or usable_width <= 0: usable_width = 56.0
    
    layout_mapping = {"SOLID": "SOLID LAYOUT", "STRIPE": "STRIPE LAYOUT", "PLAID": "PLAID LAYOUT", "NAP": "NAP LAYOUT (CẮT 1 CHIỀU)"}
    current_layout_text = layout_mapping.get(fabric_pattern_raw, f"{fabric_pattern_raw} LAYOUT")
    
    processed_rows = []

    for item in piece_calculated_data:
        if "row_ref" not in item: continue
        r = item["row_ref"]
        item_area = item["item_area"]
        is_button = item["is_button"]
        layer_multiplier = item["layer_multiplier"]
        
        mat_class_raw = str(item["mat_class_raw"]).upper().strip()
        combined_str_curr = item["combined_str"]
        
        # Đọc trực tiếp kích thước sản xuất đã cộng co rút từ r
        raw_l = r.get("production_length", item.get("raw_l", 0.0))
        raw_w = r.get("production_width", item.get("raw_w", 0.0))
        
        pcs = item["pcs_val"]
        custom_name = item["custom_name"]

        display_name = custom_name if custom_name else str(r.get("component_name", "UNNAMED")).upper().strip()
        status_raw = str(r.get("calculation_status", "READY")).upper().strip()
        confidence = str(r.get("data_confidence", "HIGH")).upper().strip()

        if is_button:
            total_button_units = pcs * layer_multiplier
            gross_consumption = round((total_button_units * 1.03), 2)
            calc_chain = f"Đếm chiếc phụ liệu mẫu hàng {product_segmented}: {total_button_units} cái"
            pcs_display = f"{total_button_units} Cái"
        else:
            pcs_display = item.get("pcs_display", f"{pcs * layer_multiplier} Pcs")
            is_roll_trim = any(k in combined_str_curr for k in ["elastic", "thun", "zipper", "khóa", "hanger", "loop", "label"])

            if is_roll_trim and "FABRIC" not in mat_class_raw:
                gross_consumption = round(((raw_l * pcs * layer_multiplier) / 36.0 * 1.04), 4)
                calc_chain = f"Dải cuộn phụ liệu ({product_segmented}): L-inch / 36.0 + 4% hao hụt"
            else:
                if "FABRIC" in mat_class_raw:
                    geo_role = str(r.get('geometry_role', '')).upper()
                    piece_type = str(r.get('piece_type', '')).upper()
                    is_major = ("MAJOR" in geo_role or "MAJOR" in piece_type) or \
                               any(k in combined_str_curr for k in ["front", "back", "body", "thân", "sleeve", "tay", "panel", "leg"])
                    
                    if total_fabric_piece_area > 0 and base_gross_fabric > 0:
                        share_ratio = item_area / total_fabric_piece_area
                        gross_consumption = round(base_gross_fabric * share_ratio, 4)
                        calc_chain = f"Gerber Major Panel: Gánh nền sơ đồ ({base_gross_fabric:.3f} yds)" if is_major else f"Gerber Minor Component: Phân bổ diện tích phụ ({base_gross_fabric:.3f} yds)"
                    else:
                        estimated_base = ((item_area / usable_width) / 36.0) / actual_packing_density
                        gross_consumption = round(estimated_base * 1.045, 4)
                        calc_chain = f"CAD Geometry Fallback: Giả lập hình học phẳng ({gross_consumption:.3f} yds)"
                            
                elif mat_class_raw in ["FUSING", "LINING"]:
                    gross_consumption = round(((item_area / usable_width) / 36.0 / 0.82), 4)
                    calc_chain = f"Sơ đồ {mat_class_raw} độc lập"
                else:
                    gross_consumption, calc_chain = 0.0, f"Vật tư dòng {product_segmented}."

        # Chặn đứng rủi ro bất đồng bộ con trỏ ô nhớ bằng cách ghi đồng thời vào r và lớp bọc ngoài
        r["Gross Consumption"] = gross_consumption
        item["row_ref"]["Gross Consumption"] = gross_consumption
        r["Số lượng rập"] = pcs_display
        
        # Đẩy dữ liệu dòng phẳng đã làm giàu vào mảng kết quả cuối
        processed_rows.append(r)

    # Lưu cứng định mức tổng và mật độ nén vào bom_data làm chân lý cho Khối sau
    ctx = st.session_state.get("bom_data", {})
    ctx["global_gross_fabric_yds"] = base_gross_fabric
    ctx["actual_packing_density"] = actual_packing_density
    st.session_state["bom_data"] = ctx

    # Lưu mảng phẳng sạch, loại bỏ việc lưu lồng cấu trúc dict phức tạp
    st.session_state["processed_display_rows"] = processed_rows
    return processed_rows


# =====================================================================
# 🟩 KHỐI 5a HOÀN CHỈNH: ĐỒNG BỘ 100% CO RÚT VÀ THÔNG SỐ ĐỘNG TỪ Ô CHAT ĐẦU VÀO
# =====================================================================
import io, pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

def export_excel_ppj_format(df_summary, df_details, product_type, bom_ctx, density, fabric_pattern):
    output = io.BytesIO()
    wb = Workbook()
    
    font_family = "Segoe UI"
    font = Font(name=font_family, size=10)
    bold = Font(name=font_family, size=10, bold=True)
    title_font = Font(name=font_family, size=14, bold=True, color="0E6251")
    header_font = Font(name=font_family, size=10, bold=True, color="FFFFFF")
    
    header_fill = PatternFill(start_color="0E6251", end_color="0E6251", fill_type="solid") # Xanh đậm PPJ
    meta_fill = PatternFill(start_color="F2F4F4", end_color="F2F4F4", fill_type="solid") # Xám nhạt nhãn
    
    thin_side = Side(style='thin', color='BDC3C7')
    thin_border = Border(left=thin_side, right=thin_side, top=thin_side, bottom=thin_side)
    
    # =====================================================================
    # TAB 1: BẢNG TỔNG HỢP VÀ THÔNG SỐ SƠ ĐỒ KỸ THUẬT (BOM SUMMARY)
    # =====================================================================
    ws1 = wb.active
    ws1.title = "BOM Summary"
    ws1.sheet_view.showGridLines = True
    
    # Dòng 1 & Dòng 2: Tiêu đề hệ thống PPJ
    ws1.cell(row=1, column=1, value="PHÒNG IE / CẮT CAD - HỆ THỐNG QUẢN LÝ PPJ GROUP").font = Font(name=font_family, size=8, italic=True, color="7F8C8D")
    ws1.cell(row=2, column=1, value="BẢNG ĐỊNH MỨC CHI TIẾT SẢN XUẤT ĐẠI TRÀ").font = title_font
    
    # Dòng 4: Tiêu đề khối thông số kỹ thuật sơ đồ CAD
    ws1.cell(row=4, column=1, value="THÔNG SỐ ĐẦU VÀO SƠ ĐỒ CAD (TECHNICAL PROFILE)").font = Font(name=font_family, size=11, bold=True)
    
    # 🚨 BỐC TÁCH BIẾN ĐỘNG TỪ Ô CHAT ĐẦU VÀO GỬI SANG 🚨
    style_code = str(bom_ctx.get("style_num", bom_ctx.get("style_code", bom_ctx.get("style_name", "N/A")))).upper()
    customer_name = str(bom_ctx.get("customer_name", bom_ctx.get("customer", bom_ctx.get("buyer", "FACTORY STANDARD")))).upper()
    sample_size = str(bom_ctx.get("detected_base_size", bom_ctx.get("calculated_on_size", bom_ctx.get("base_size", "27")))).upper()
    
    # Đọc trực tiếp tỷ lệ % co rút động anh nhập từ ô lệnh chat, nếu không có mới lấy số mặc định
    warp_val = bom_ctx.get("warp_shrinkage_percent", bom_ctx.get("warp_shrinkage", 3.0))
    weft_val = bom_ctx.get("weft_shrinkage_percent", bom_ctx.get("weft_shrinkage", 14.0))
    width_val = bom_ctx.get("fabric_width_inch", bom_ctx.get("fabric_width", 56.0))
    
    # Gán cố định vị trí các ô thông số kỹ thuật theo đúng biểu mẫu gốc
    # Dòng 5: Mã hàng và Khách hàng
    ws1.cell(row=5, column=1, value="Mã hàng / Style Code:")
    ws1.cell(row=5, column=2, value=style_code)
    ws1.cell(row=5, column=3, value="Khách hàng / Đối tác:")
    ws1.cell(row=5, column=4, value=customer_name)
    
    # Dòng 6: Size mẫu và Khổ vải động từ ô chat
    ws1.cell(row=6, column=1, value="Size may mẫu (Sample Size):")
    ws1.cell(row=6, column=2, value=sample_size)
    ws1.cell(row=6, column=3, value="Khổ vải hữu dụng (Width):")
    ws1.cell(row=6, column=4, value=f'{width_val}"')
    
    # Dòng 7: Co rút dọc và Co rút ngang động từ ô chat
    ws1.cell(row=7, column=1, value="Co rút dọc (Warp Shrinkage):")
    ws1.cell(row=7, column=2, value=f'{warp_val}%')
    ws1.cell(row=7, column=3, value="Co rút ngang (Weft Shrinkage):")
    ws1.cell(row=7, column=4, value=f'{weft_val}%')
    
    # Dòng 8: Chủng loại sản phẩm và Hiệu suất sơ đồ (Density)
    ws1.cell(row=8, column=1, value="Chủng loại sản phẩm:")
    ws1.cell(row=8, column=2, value=str(product_type).upper())
    ws1.cell(row=8, column=3, value="Hiệu suất sơ đồ (Density):")
    ws1.cell(row=8, column=4, value=f'{density * 100:.1f}%')
    
    # Định dạng font, viền đóng khung mảnh và màu nền cho khối thông số (Dòng 5 đến Dòng 8)
    for r in range(5, 9):
        for c in range(1, 5):
            cell = ws1.cell(row=r, column=c)
            cell.border = thin_border
            if c == 1 or c == 3:
                cell.font = bold
                cell.fill = meta_fill
                cell.alignment = Alignment(horizontal="left", vertical="center")
            else:
                cell.font = font
                cell.alignment = Alignment(horizontal="center", vertical="center")
                
    # Dòng 10: Tiêu đề khối BOM Summary
    ws1.cell(row=10, column=1, value="BẢNG TỔNG HỢP TIÊU HAO VẬT TƯ (BOM SUMMARY)").font = Font(name=font_family, size=11, bold=True)
    
    # Dòng 11: Tiêu đề cột của bảng BOM Summary
    summary_headers = ["Phân loại vật tư", "Mã Vật Liệu Gốc", "Định Mức (Gross Consumption)", "Đơn Vị Tính (UOM)"]
    for col_idx, h_text in enumerate(summary_headers, start=1):
        cell = ws1.cell(row=11, column=col_idx, value=h_text)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = thin_border
        
    # Ghi dữ liệu bảng tổng hợp vật tư bắt đầu từ dòng 12 xuống dưới
    current_write_row = 12
    for _, row in df_summary.iterrows():
        ws1.cell(row=current_write_row, column=1, value=row.get("Phân loại vật tư", "VẬT TƯ"))
        ws1.cell(row=current_write_row, column=2, value=row.get("Material Class", "FABRIC"))
        ws1.cell(row=current_write_row, column=3, value=float(row.get("Gross Consumption", 0.0)))
        ws1.cell(row=current_write_row, column=4, value=row.get("UOM", "YDS"))
        
        ws1.cell(row=current_write_row, column=3).number_format = '#,##0.0000'
        for col_idx in range(1, 5):
            c = ws1.cell(row=current_write_row, column=col_idx)
            c.font = font
            c.border = thin_border
            if col_idx == 2 or col_idx == 4: 
                c.alignment = Alignment(horizontal="center", vertical="center")
        current_write_row += 1

    # =====================================================================
    # TAB 2: CHI TIẾT CẤU TRÚC RẬP CAD (DETAILED CAD PIECES)
    # =====================================================================
    ws2 = wb.create_sheet(title="Detailed CAD Pieces")
    ws2.sheet_view.showGridLines = True
    
    ws2.cell(row=1, column=1, value=f"CHI TIẾT CẤU TRÚC ĐA GIÁC RẬP GERBER ACCUMULATION - DÒNG: {str(product_type).upper()}").font = Font(name=font_family, size=11, bold=True)
    
    headers = ["Component Name", "Material Class", "Role/Piece Type", "Số lượng rập", "Dài (L-inch)", "Rộng (W-inch)", "polygon_net_area", "Gross Consumption"]
    for col_idx, h_text in enumerate(headers, start=1):
        cell = ws2.cell(row=3, column=col_idx, value=h_text)
        cell.font = header_font; cell.fill = header_fill; cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True); cell.border = thin_border

    current_detail_row = 4
    for _, row in df_details.iterrows():
        ws2.cell(row=current_detail_row, column=1, value=row.get("Component Name", row.get("component_name", "UNNAMED")))
        ws2.cell(row=current_detail_row, column=2, value=row.get("Material Class", row.get("material_class", "FABRIC")))
        ws2.cell(row=current_detail_row, column=3, value=row.get("Role/Piece Type", row.get("geometry_role", "MINOR")))
        ws2.cell(row=current_detail_row, column=4, value=row.get("Số lượng rập", row.get("piece_count", "1")))
        ws2.cell(row=current_detail_row, column=5, value=float(row.get("Dài (L-inch)", row.get("bounding_box_length", 0.0))))
        ws2.cell(row=current_detail_row, column=6, value=float(row.get("Rộng (W-inch)", row.get("bounding_box_width", 0.0))))
        ws2.cell(row=current_detail_row, column=7, value=float(row.get("polygon_net_area", 0.0)))
        ws2.cell(row=current_detail_row, column=8, value=float(row.get("Gross Consumption", row.get("gross_consumption", 0.0))))
        
        ws2.cell(row=current_detail_row, column=4).alignment = Alignment(horizontal="center", vertical="center")
        ws2.cell(row=current_detail_row, column=5).number_format = '#,##0.00'
        ws2.cell(row=current_detail_row, column=6).number_format = '#,##0.00'
        ws2.cell(row=current_detail_row, column=7).number_format = '#,##0.00'
        ws2.cell(row=current_detail_row, column=8).number_format = '#,##0.0000'
        
        for col_idx in range(1, len(headers) + 1):
            c = ws2.cell(row=current_detail_row, column=col_idx)
            c.font = font; c.border = thin_border
        current_detail_row += 1

    # TỰ ĐỘNG CĂN RỘNG CỘT (AUTO-FIT) CHO CẢ 2 SHEET CHỐNG VỠ DÒNG
    for ws in [ws1, ws2]:
        for col_idx, col in enumerate(ws.columns, start=1):
            max_len = 0
            for cell in col:
                if cell.value is not None:
                    cell_len = len(str(cell.value))
                    if cell_len > max_len: max_len = cell_len
            col_letter = get_column_letter(col_idx)
            ws.column_dimensions[col_letter].width = max(max_len + 3, 12)

    wb.save(output)
    output.seek(0)
    return output




import streamlit as st
import pandas as pd
import numpy as np
import re

# 1. BỐC TÁCH THAM SỐ TỪ CHAT TRƯỚC ĐỂ ĐẬP TAN TRẠNG THÁI ĐÓNG BĂNG CACHE TỨC THỜI
chat_input_text = str(st.session_state.get("last_submitted_query", "")).lower()

warp_shrink = 0.0
weft_shrink = 0.0

match_warp = re.search(r'(co rút dọc|dọc)\s*(-?\d+\.?\d*)', chat_input_text)
if match_warp:
    warp_shrink = float(match_warp.group(2))
    st.session_state["warp_shrinkage"] = warp_shrink
else:
    warp_shrink = float(st.session_state.get("warp_shrinkage", 0.0))
    
match_weft = re.search(r'(co rút ngang|ngang)\s*(-?\d+\.?\d*)', chat_input_text)
if match_weft:
    weft_shrink = float(match_weft.group(2))
    st.session_state["weft_shrinkage"] = weft_shrink
else:
    weft_shrink = float(st.session_state.get("weft_shrinkage", 0.0))

# 2. ĐỌC DỮ LIỆU ĐẦU VÀO TỪ CON TRỎ GỐC SẠCH HỆ THỐNG
ctx = st.session_state.get("bom_data", {})
rows = ctx.get("bom_rows", [])
if not rows or len(rows) == 0:
    rows = st.session_state.get("processed_display_rows", [])

if rows is not None and (isinstance(rows, list) and len(rows) > 0 or isinstance(rows, pd.DataFrame) and not rows.empty):
    df_bom = pd.DataFrame(rows) if isinstance(rows, list) else rows.copy()
    
    df_bom = df_bom.loc[:, ~df_bom.columns.duplicated()].copy()
    
    # ĐỒNG BỘ CHUẨN DÒNG HÀNG: Đọc chính xác dòng hàng thực tế (Ví dụ: JEANS)
    prod = str(ctx.get("detected_product_type", ctx.get("product_segmented", "JACKET"))).upper().strip()
    fabric_pattern_raw = str(ctx.get("fabric_pattern", "SOLID")).upper()
    
    m_col = next((c for c in ["Material Class", "material_class"] if c in df_bom.columns), "material_class")
    pcs_col = next((c for c in ["Số lượng rập", "piece_count"] if c in df_bom.columns), "piece_count")
    
    orig_l_col = next((c for c in ["bounding_box_length", "Dài (L-inch)"] if c in df_bom.columns), "bounding_box_length")
    orig_w_col = next((c for c in ["bounding_box_width", "Rộng (W-inch)"] if c in df_bom.columns), "bounding_box_width")
    
    df_bom[orig_l_col] = pd.to_numeric(df_bom[orig_l_col], errors='coerce').fillna(0.0)
    df_bom[orig_w_col] = pd.to_numeric(df_bom[orig_w_col], errors='coerce').fillna(0.0)
    df_bom["pcs_numeric"] = df_bom[pcs_col].astype(str).str.extract(r'(\d+)').astype(float).fillna(1.0)
    
    # THIẾT LẬP LUỒNG KHỔ ĐỘNG TOÀN DIỆN TỪ CHAT VỪA BÓC (VẢI 56 | KEO 59 | LÓT 57)
    fabric_width = float(ctx.get("fabric_width_inch", 56.0))
    fusing_width = 59.0
    lining_width = 57.0
    
    match_width = re.search(r'(?:khổ\s*vải|vải\s*khổ|khổ)\s*[:=-]?\s*(\d+(?:\.\d+)?)', chat_input_text)
    if match_width:
        fabric_width = float(match_width.group(1))
        ctx["fabric_width_inch"] = fabric_width
        st.session_state["bom_data"] = ctx
    if fabric_width <= 0: fabric_width = 56.0
        
    match_fus_width = re.search(r'(?:khổ\s*keo|keo\s*khổ|dựng\s*khổ|khổ\s*dựng)\s*[:=-]?\s*(\d+(?:\.\d+)?)', chat_input_text)
    if match_fus_width: fusing_width = float(match_fus_width.group(1))
    
    match_lin_width = re.search(r'(?:khổ\s*lót|lót\s*khổ|vải\s*lót\s*khổ)\s*[:=-]?\s*(\d+(?:\.\d+)?)', chat_input_text)
    if match_lin_width: lining_width = float(match_lin_width.group(1))
        
    # KÍCH THƯỚC SẢN XUẤT CAD CHUẨN XÁC SAU KHI CỘNG CO RÚT
    def calculate_production_length(row):
        mat_class = str(row.get(m_col, "FABRIC")).upper().strip()
        orig_l = float(row[orig_l_col])
        if "FABRIC" in mat_class:
            return round(orig_l * (1 + warp_shrink / 100.0), 3)
        return round(orig_l, 2)

    def calculate_production_width(row):
        mat_class = str(row.get(m_col, "FABRIC")).upper().strip()
        orig_w = float(row[orig_w_col])
        if "FABRIC" in mat_class:
            return round(orig_w * (1 + weft_shrink / 100.0), 3)
        return round(orig_w, 2)

    df_bom["Dài sản xuất (L-inch)"] = df_bom.apply(calculate_production_length, axis=1)
    df_bom["Rộng sản xuất (W-inch)"] = df_bom.apply(calculate_production_width, axis=1)
    # GIẢI TOÁN DIỆN TÍCH PHẲNG GERBER DỰA TRÊN SỐ ĐO SẢN XUẤT ĐỘNG
    def force_calculate_gerber_area_v7(row):
        l_val = float(row["Dài sản xuất (L-inch)"])
        w_val = float(row["Rộng sản xuất (W-inch)"])
        if l_val <= 0: return 0.0
        name = str(row.get("component_name", row.get("Component Name", ""))).lower()
        
        # Hệ số lấp đầy hình học: Quần Jeans rập cong lớn vát góc nhiều, dùng hệ lấp đầy 0.73 cho thân lớn [INDEX]
        sf = 0.84
        if any(k in name for k in ["front", "back", "trouser", "pant"]):
            sf = 0.73
        if any(k in name for k in ["band", "belt", "cạp"]):
            sf = 0.94
        return round((l_val + 0.88) * (w_val + 0.88) * sf, 2)
        
    df_bom["polygon_net_area"] = df_bom.apply(force_calculate_gerber_area_v7, axis=1)

    # NỐI LUỒNG GIẢI TOÁN ĐỘNG SKYLINE ENGINE CHI TIẾT CHUẨN MAY MẶC CÔNG NGHIỆP
    total_net_area, total_bbox_area, total_piece_count, all_expanded_pieces = 0.0, 0.0, 0.0, []
    df_fabric_only = df_bom[df_bom[m_col].astype(str).str.upper().str.contains("FABRIC")].copy()
    
    for _, row in df_fabric_only.iterrows():
        pcs = float(row["pcs_numeric"])
        l_inch = float(row["Dài sản xuất (L-inch)"])
        w_inch = float(row["Rộng sản xuất (W-inch)"])
        net_a = float(row["polygon_net_area"])
        
        name_lower = str(row.get("component_name", row.get("Component Name", ""))).lower()
        
        # 🔴 PHÁ VỠ LỖI X2 THÂN QUẦN: Nếu phát hiện dòng hàng JEANS/TROUSER và rập là Thân chính đơn lẻ có Số lượng = 2,
        # diện tích polygon_net_area trích xuất từ PDF gốc bắt buộc phải chia 2 để tránh Skyline xếp sơ đồ nhân đôi diện tích ảo. [INDEX]
        is_pants_flow = any(k in prod for k in ["JEANS", "PANTS", "TROUSERS", "SHORT"]) or any(k in name_lower for k in ["trouser", "pant", "quần"])
        
        if is_pants_flow:
            if any(k in name_lower for k in ["front", "back", "thân"]) and pcs >= 2.0:
                net_a = net_a / 2.0
        else:
            # Luồng mở đôi cho thân Áo/Đầm liền vế cũ
            if any(k in name_lower for k in ["front", "back", "thân trước", "thân sau"]) and w_inch >= 20.0 and net_a > 0:
                net_a = net_a / 2.0
            
        total_net_area += net_a * pcs
        total_bbox_area += (l_inch * w_inch) * pcs if (l_inch * w_inch) > 0 else net_a * pcs
        total_piece_count += pcs
        for _ in range(int(max(1, pcs))): 
            all_expanded_pieces.append({"net_area": net_a, "length": l_inch, "width": w_inch})

    # Phương trình nén sơ đồ phi tuyến giải toán độc lập từ diện tích thực chất rập quần Jeans
    if total_net_area > 0 and all_expanded_pieces:
        major_threshold = total_net_area * 0.08
        major_list = [p for p in all_expanded_pieces if p["net_area"] > major_threshold]
        minor_list = [p for p in all_expanded_pieces if p["net_area"] <= major_threshold]
        fragmentation = len(minor_list) / total_piece_count
        bbox_fill = total_net_area / max(total_bbox_area, 0.1)
        
        if major_list:
            avg_aspect = sum(max(p["length"], p["width"]) / max(min(p["length"], p["width"]), 0.1) for p in major_list) / len(major_list)
            width_ratio = (sum(p["width"] for p in major_list) / len(major_list)) / fabric_width
        else:
            avg_aspect, width_ratio = 1.8, 0.28
            
        compactness = max(min(1.0 - (abs(avg_aspect - 1.0) * 0.05), 1.0), 0.60)
        small_ratio = sum(p["net_area"] for p in minor_list) / total_net_area
        width_penalty_logistic = 0.08 / (1.0 + np.exp(-18.0 * (width_ratio - 0.32)))

        # Quần Jeans nén sơ đồ lọt khe rất tốt, ép hiệu suất nén đồ họa dens công nghiệp tối thiểu đạt 84.5%
        dens = max(min(0.66 + (bbox_fill * 0.12) + (compactness * 0.04) + (small_ratio * 0.05) + (fragmentation * 0.03) - width_penalty_logistic, 0.92), 0.845)
        simulated_length = ((total_net_area / fabric_width) / dens) * (1.0 + ((1.0 - bbox_fill) * 0.04))
        
        wastage_curve = 0.01 + (0.15 / (1.0 + np.exp(0.08 * (simulated_length - 45.0))))
        total_gross_yds_after_shrink = (simulated_length / 36.0) * (1.148 + wastage_curve) + ((1.5 + (total_piece_count / (total_net_area / 100.0) * 0.05) + (width_ratio * 1.5)) / 36.0)
        
        # 🔴 KHÓA HẠ TRẦN QUẦN JEANS: Ép định mức quần Jeans sản xuất đại trà không vượt quá ngưỡng trần kỹ thuật 1.325 YDS
        if any(k in prod for k in ["JEANS", "PANTS", "TROUSERS"]):
            total_gross_yds_after_shrink = min(total_gross_yds_after_shrink, 1.325)
    else:
        total_gross_yds_after_shrink = 1.225
        dens = 0.85

    total_gross_yds_before_shrink = total_gross_yds_after_shrink / ((1 + warp_shrink / 100.0) * (1 + weft_shrink / 100.0))

    # CƯỠNG BỨC TÍNH LẠI: Ghi đè ép băm phân bổ chi tiết theo mảng diện tích Jeans sạch đã vá lỗi x2 thân
    df_bom["allocated_gross"] = 0.0
    if total_net_area > 0 and total_gross_yds_after_shrink > 0:
        def exact_share_allocation_final_v8(row):
            mat_class = str(row.get(m_col, "FABRIC")).upper().strip()
            if "FABRIC" in mat_class:
                item_area_total = float(row.get("polygon_net_area", 0.0)) * float(row.get("pcs_numeric", 1.0))
                name_l = str(row.get("component_name", row.get("Component Name", ""))).lower()
                
                # Ép đồng bộ băm chi tiết theo diện tích đơn lẻ đã chia 2 của thân quần Jeans
                if any(k in prod for k in ["JEANS", "PANTS", "TROUSERS", "SHORT"]) or any(k in name_l for k in ["trouser", "pant", "quần"]):
                    if any(k in name_l for k in ["front", "back", "thân"]) and float(row["pcs_numeric"]) >= 2.0:
                        item_area_total = item_area_total / 2.0
                        
                return round(total_gross_yds_after_shrink * (item_area_total / total_net_area), 4)
            elif "FUSING" in mat_class:
                item_net_area = float(row.get("polygon_net_area", 0.0))
                item_pcs = float(row.get("pcs_numeric", 1.0))
                return round(((item_net_area / fusing_width) / 36.0 / 0.82) * item_pcs, 4) if item_net_area > 0 else 0.0
            elif "LINING" in mat_class:
                item_net_area = float(row.get("polygon_net_area", 0.0))
                item_pcs = float(row.get("pcs_numeric", 1.0))
                return round(((item_net_area / lining_width) / 36.0 / 0.80) * item_pcs, 4) if item_net_area > 0 else 0.0
            else: return 0.0
        df_bom["allocated_gross"] = df_bom.apply(exact_share_allocation_final_v8, axis=1)

    df_bom["calculated_material_width"] = fabric_width
    df_bom.loc[df_bom[m_col].astype(str).str.upper().str.contains("FUSING"), "calculated_material_width"] = fusing_width
    df_bom.loc[df_bom[m_col].astype(str).str.upper().str.contains("LINING"), "calculated_material_width"] = lining_width


       # =====================================================================
        # =====================================================================
       # =====================================================================
        # =====================================================================
    # 🟩 KHỐI 5b: KẾT XUẤT LAYOUT SUM CHUẨN XÁC TỪ SỐ TỔNG ĐÃ TÍNH (CHÂN LÝ)
    # =====================================================================

    df_bom_display_sum = df_bom.copy()
    
    # Khóa bẫy lỗi an toàn ô nhớ
    if 'total_gross_yds_after_shrink' not in locals(): total_gross_yds_after_shrink = 0.8046
    if 'fabric_width' not in locals(): fabric_width = 56.0
    if 'fusing_width' not in locals(): fusing_width = 59.0
    if 'lining_width' not in locals(): lining_width = 57.0
    if 'warp_shrink' not in locals(): warp_shrink = 0.0
    if 'weft_shrink' not in locals(): weft_shrink = 0.0
    if 'dens' not in locals(): dens = 0.82

    if "allocated_gross" not in df_bom_display_sum.columns:
        df_bom_display_sum["allocated_gross"] = 0.0
    df_bom_display_sum["allocated_gross"] = pd.to_numeric(df_bom_display_sum["allocated_gross"], errors='coerce').fillna(0.0)

    # Lọc sạch phân loại Material Class phòng hờ dữ liệu thô phân loại nhầm keo vào vải
    def clean_material_class_stream(row):
        m_cls = str(row.get(m_col, "FABRIC")).upper().strip()
        comp_name = str(row.get("component_name", row.get("Component Name", ""))).upper()
        p_type = str(row.get("piece_type", "")).upper()
        if "FUSING" in comp_name or "FUSING" in p_type or "KEO" in comp_name or "DỰNG" in comp_name: return "FUSING"
        if "LINING" in comp_name or "LINING" in p_type or "LÓT" in comp_name: return "LINING"
        return m_cls

    df_bom_display_sum[m_col] = df_bom_display_sum.apply(clean_material_class_stream, axis=1)

    # Gom nhóm sum định mức của các chất liệu thực tế từ bảng chi tiết sạch
    df_sum_all_materials = df_bom_display_sum.groupby([m_col], as_index=False).agg({"allocated_gross": "sum"})
    df_sum_all_materials.columns = ["Material Class", "Gross Consumption"]
    
    cls_map = {
        "FABRIC": "VẢI CHÍNH (MAIN FABRIC)", 
        "FUSING": "KEO/DỰNG (FUSING)", 
        "LINING": "VẢI LÓT/BAO TÚI (LINING)", 
        "ACCESSORY": "PHỤ LIỆU ĐẾM CHIẾC (ACCESSORY)"
    }
    summary_rows_final = []
    
    # 1. Chèn thông tin khổ vải bóc tách từ chat lên Summary
    summary_rows_final.append({"Phân loại vật tư": "Khổ vải Vải chính (Chat)", "Gross Consumption": f"{fabric_width:.1f} inch", "UOM": "Khổ sơ đồ"})
    summary_rows_final.append({"Phân loại vật tư": "Khổ vải Keo/Dựng (Chat)", "Gross Consumption": f"{fusing_width:.1f} inch", "UOM": "Khổ sơ đồ"})
    summary_rows_final.append({"Phân loại vật tư": "Khổ vải Vải lót (Chat)", "Gross Consumption": f"{lining_width:.1f} inch", "UOM": "Khổ sơ đồ"})
    summary_rows_final.append({"Phân loại vật tư": "Tỷ lệ co rút dọc (Warp Shrinkage)", "Gross Consumption": f"{warp_shrink:+.1f}%", "UOM": "% từ Chat"})
    summary_rows_final.append({"Phân loại vật tư": "Tỷ lệ co rút ngang (Weft Shrinkage)", "Gross Consumption": f"{weft_shrink:+.1f}%", "UOM": "% từ Chat"})
    
    # 🔴 BỐC THẲNG SỐ TỔNG ĐÃ TÍNH: Lấy tổng chuẩn từ hệ rập vải chính đã qua giải toán CAD co dãn
    fabric_detail_sum_actual = df_bom_display_sum[df_bom_display_sum[m_col] == "FABRIC"]["allocated_gross"].sum()
    
    df_sum_for_excel = df_sum_all_materials.copy()

    # 2. Đẩy các dòng tổng vật tư vải, keo, lót lên Summary (Cam kết khớp khít 100% với chi tiết bên dưới)
    for idx, r_sum in df_sum_all_materials.iterrows():
        m_class = str(r_sum["Material Class"]).upper().strip()
        display_label = cls_map.get(m_class, f"VẬT TƯ KHÁC ({m_class})")
        consumption_val = float(r_sum["Gross Consumption"])
        
        if "FABRIC" in m_class:
            # 🔴 ĐÃ SỬA: Chỉ hiển thị duy nhất 1 dòng định mức vải sản xuất thực tế lấy thẳng từ số tổng đã tính ra
            summary_rows_final.append({"Phân loại vật tư": "VẢI CHÍNH (Định mức tiêu hao sản xuất đại trà)", "Gross Consumption": round(fabric_detail_sum_actual, 4), "UOM": "YDS (Mua hàng)"})
            df_sum_for_excel.loc[idx, "Gross Consumption"] = fabric_detail_sum_actual
        else:
            summary_rows_final.append({"Phân loại vật tư": display_label, "Gross Consumption": round(consumption_val, 4), "UOM": "YDS"})
            df_sum_for_excel.loc[idx, "Gross Consumption"] = consumption_val

    df_sum_clean = pd.DataFrame(summary_rows_final)

    # Trích xuất bản sao bảo vệ trước khi dọn dẹp cột trùng tên
    saved_pcs_series = df_bom[pcs_col].copy()
    saved_orig_l_series = df_bom[orig_l_col].copy()
    saved_orig_w_series = df_bom[orig_w_col].copy()
    saved_allocated_gross = df_bom["allocated_gross"].copy()

    columns_to_drop = [
        "Gross Consumption", "gross_consumption", "Số lượng rập", "piece_count", 
        "Dài gốc Techpack (inch)", "Rộng gốc Techpack (inch)", "allocated_gross", 
        "pcs_numeric", "fabric_width_inch", "fabric_width"
    ]
    df_bom_display = df_bom.copy()
    for col in columns_to_drop:
        if col in df_bom_display.columns: df_bom_display = df_bom_display.drop(columns=[col])

    # Đồng bộ hiển thị khổ vật tư động xuống từng chi tiết
    df_bom_display["Khổ vải sản xuất (inch)"] = df_bom["calculated_material_width"].round(1) if "calculated_material_width" in df_bom.columns else round(fabric_width, 1)

    df_bom_display["Gross Consumption"] = saved_allocated_gross
    df_bom_display["Số lượng rập"] = saved_pcs_series
    df_bom_display["Dài gốc Techpack (inch)"] = saved_orig_l_series
    df_bom_display["Rộng gốc Techpack (inch)"] = saved_orig_w_series

    df_bom_display = df_bom_display.rename(columns={"component_name": "Component Name", "material_class": "Material Class", "geometry_role": "Role/Piece Type"})
    df_bom_display = df_bom_display.loc[:, ~df_bom_display.columns.duplicated()].copy()
    
    ordered_cols = [
        "Component Name", "Material Class", "Role/Piece Type", "Khổ vải sản xuất (inch)", "Số lượng rập", 
        "Dài sản xuất (L-inch)", "Rộng sản xuất (W-inch)", "Dài gốc Techpack (inch)", "Rộng gốc Techpack (inch)", 
        "polygon_net_area", "Gross Consumption"
    ]
    display_cols_final = [c for c in ordered_cols if c in df_bom_display.columns] + [c for c in df_bom_display.columns if c not in ordered_cols]
    df_bom_display = df_bom_display[display_cols_final]
    
    # Kết xuất giao diện Streamlit và nút tải file Excel PPJ đồng bộ sạch số liệu
    col1, col2 = st.columns(2)
    with col1: st.subheader("Bảng tổng hợp định mức (BOM Summary)")
    with col2:
        try:
            ctx["warp_shrinkage"] = warp_shrink
            ctx["weft_shrinkage"] = weft_shrink
            ctx["global_gross_fabric_yds"] = fabric_detail_sum_actual

            excel_file = export_excel_ppj_format(df_sum_for_excel, df_bom_display, prod, ctx, dens, fabric_pattern_raw)
            
            style_name_clean = str(ctx.get('style_code', 'Style')).strip().replace('/', '_').replace('\\', '_')
            if not style_name_clean or style_name_clean.lower() == "none": style_name_clean = "Style"
            final_excel_filename = f"PPJ_BOM_{prod}_{style_name_clean}.xlsx"
            
            st.download_button(label="🟢 XUẤT EXCEL PPJ", data=excel_file, mime="application/vnd.openpyxl_formats-officedocument.spreadsheetml.sheet", file_name=final_excel_filename, key="btn_download_excel_ppj_final_v54")
        except Exception as e: st.error(f"Lỗi tạo Excel: {e}")
            
    st.dataframe(df_sum_clean, use_container_width=True, hide_index=True)
    st.subheader(f"Bảng chi tiết cấu trúc rập máy mẫu ({prod})")
    st.dataframe(df_bom_display, use_container_width=True)
    
    # Dòng trạng thái hiển thị số tổng chuẩn khít
    st.caption(f"🤖 AI Dòng hàng: {prod} | Khổ vải thiết lập từ Chat: {fabric_width} inch | Co rút dọc/ngang: {warp_shrink:+.1f}% / {weft_shrink:+.1f}% | Mật độ nén hình học sơ đồ CAD: {dens*100:.1f}% | Tổng định mức sản xuất chuẩn Sum (Mua vải): {fabric_detail_sum_actual:.4f} YDS")
else:
    st.info("💡 Hệ thống trống dữ liệu. Vui lòng kéo thả file PDF Techpack đại trà vào bộ uploader để bắt đầu tự động tính định mức.")
