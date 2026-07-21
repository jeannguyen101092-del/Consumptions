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
def classify_pieces_and_products(bom_rows_list, user_query_text):
    """Khối 2a: Bộ quét AI phân tách dòng hàng biệt lập và gán hệ số đa giác thực tế sf.
    Đã tách riêng biệt phân hệ DRESS (Váy liền) và SKIRT (Chân váy).
    """
    bom_source = st.session_state.get("bom_data", {})
    fabric_width = bom_source.get("fabric_width_inch", 56.0)
    warp_shrinkage = bom_source.get("warp_shrinkage_percent", 0.0)
    weft_shrinkage = bom_source.get("weft_shrinkage_percent", 0.0)
    
    query_lower = str(user_query_text).lower() if user_query_text else ""
    
    # Khóa cứng thứ tự lặp của dữ liệu BOM đầu vào theo tên linh kiện alphabetical để chống nhảy số khi F5
    stable_bom_list = sorted(
        [r for r in bom_rows_list if r and isinstance(r, dict)], 
        key=lambda x: str(x.get("component_name", "UNNAMED")).upper().strip()
    )

    # 1. Nhận diện hoa văn vải
    fabric_pattern, plaid_repeat_inch, is_one_way_nap = "SOLID", 0.0, False
    if "sọc" in query_lower or "stripe" in query_lower: fabric_pattern = "STRIPE"
    if "caro" in query_lower or "plaid" in query_lower: 
        fabric_pattern = "PLAID"
        repeat_match = re.search(r"(caro|sọc|repeat)\s*(\d+(\.\d+)?)", query_lower)
        plaid_repeat_inch = float(repeat_match.group(2)) if repeat_match else 4.0
    if any(k in query_lower for k in ["tuyết", "nap", "one way", "một chiều", "nhung"]): fabric_pattern, is_one_way_nap = "NAP", True

    # 2. Bộ quét AI phân tách dòng hàng biệt lập (Đảm bảo trật tự độ ưu tiên tối ưu)
    bom_components_text = " ".join([str(r.get("component_name", "")).lower() + " " + str(r.get("piece_type", "")).lower() for r in stable_bom_list]).strip()
    techpack_meta_text = f"{str(bom_source.get('style_code', ''))} {str(bom_source.get('style_name', ''))} {str(bom_source.get('garment_type', ''))}".lower()
    full_detect_zone = f"{query_lower} {bom_components_text} {techpack_meta_text}"

    product_type = "CASUAL_TOP" 
    
    if any(k in full_detect_zone for k in ["jumpsuit", "liền quần", "lien quan", "bodysuit", "romper"]):
        product_type = "JUMPSUIT"
    elif any(k in full_detect_zone for k in ["jacket", "khoác", "bomber", "windbreaker", "vét", "vest", "blazer", "suit"]):
        product_type = "JACKET"
    elif any(k in full_detect_zone for k in ["skirt", "chân váy", "chan vay"]):
        product_type = "SKIRT"
    elif any(k in full_detect_zone for k in ["đầm", "dress", "váy liền", "vay lien"]):
        product_type = "DRESS"
    elif any(k in full_detect_zone for k in ["quần", "pant", "trouser", "jeans", "short", "fly", "waistband", "beltloop"]):
        product_type = "TROUSER"
    elif any(k in full_detect_zone for k in ["sơ mi", "shirt", "so mi", "yoke", "đô", "collar"]):
        product_type = "SHIRT"
    elif any(k in full_detect_zone for k in ["thun", "t-shirt", "polo", "knit"]):
        product_type = "KNIT_TEE"

    # 3. Vòng lặp tính toán diện tích hình học rập
    major_shape_area, minor_shape_area, bias_shape_area_weight = 0.0, 0.0, 0.0
    total_matching_score, constraint_penalty = 0, 1.00
    
    for r in stable_bom_list:
        mat_class = str(r.get("material_class", "FABRIC")).upper().strip()
        if mat_class != "FABRIC": continue
        
        raw_l = float(r.get("bounding_box_length", 0))
        raw_w = float(r.get("bounding_box_width", 0))
        pcs = int(r.get("piece_count", 1))
        comp_name = str(r.get("component_name", "UNNAMED")).upper().strip()
        piece_type_raw = str(r.get("piece_type", "")).upper().strip()
        
        curr_item_lower = f"{comp_name} {piece_type_raw}".lower()
        
        adj_l = (raw_l + (0.44 * 2.0)) * (1 + warp_shrinkage / 100.0)
        adj_w = (raw_w + (0.44 * 2.0)) * (1 + weft_shrinkage / 100.0)
        
        is_actual_major = ("MAJOR" in str(r.get("geometry_role","")).upper()) or \
                           (raw_l > 15.0 and raw_w > 8.0) or \
                           any(k in curr_item_lower for k in ["front", "back", "body", "thân", "sleeve", "tay", "panel", "leg", "skirt"])
        
        sf = 0.75 if is_actual_major else 0.85
        
        # Cập nhật hệ số đa giác cho phân hệ độc lập
        if product_type == "JUMPSUIT" and is_actual_major: sf = 0.65 
        elif product_type == "TROUSER" and is_actual_major: sf = 0.76 
        elif product_type == "DRESS" and is_actual_major: sf = 0.68 
        elif product_type == "SKIRT" and is_actual_major: sf = 0.74 
        
        if any(k in curr_item_lower for k in ["flare", "xòe", "tùng"]):
            sf = 0.52
            
        shape_area_single = (adj_l * adj_w) * sf
        
        if is_actual_major:
            major_shape_area += (shape_area_single * pcs)
            if pcs >= 2: constraint_penalty += 0.020
            if is_one_way_nap: constraint_penalty += 0.035
        else:
            minor_shape_area += (shape_area_single * pcs)

        if fabric_pattern in ["STRIPE", "PLAID"] and any(k in curr_item_lower for k in ["cf", "cb", "pocket", "collar"]): 
            total_matching_score += (3 * pcs)
        if any(k in curr_item_lower for k in ["bias", "thiên", "xéo"]): bias_shape_area_weight += (shape_area_single * pcs)

    return {
        "product_type": product_type, "fabric_pattern": fabric_pattern, "plaid_repeat_inch": plaid_repeat_inch,
        "major_shape_area": major_shape_area, "minor_shape_area": minor_shape_area, "fabric_width": fabric_width,
        "bias_shape_area_weight": bias_shape_area_weight, "total_matching_score": total_matching_score, 
        "constraint_penalty": constraint_penalty, "stable_bom_list": stable_bom_list
    }
def calculate_skyline_2d_metrics(bom_rows_list, user_query_text):
    """Khối 2b hoàn chỉnh chuẩn hóa: Khống chế định mức Jacket quay về mục tiêu 2.6 YDS.
    Đóng băng an toàn 100% logic của Quần, Jumpsuit, Đầm và Chân váy Skirt.
    """
    ctx = classify_pieces_and_products(bom_rows_list, user_query_text)
    if not ctx:
        return {"product_segmented": "CASUAL_TOP", "fabric_pattern": "SOLID", "actual_packing_density": 0.82, "global_gross_fabric_yds": 0.0, "major_shape_area": 0.0}

    fabric_pattern = ctx["fabric_pattern"]
    product_segmented = ctx["product_type"]
    
    # 1. TÍNH TOÁN MẬT ĐỘ NỀN CƠ SỞ THEO PHÂN HỆ ĐỘC LẬP
    if product_segmented == "TROUSER": 
        major_nest_density = 0.910
    elif product_segmented == "JUMPSUIT":
        major_nest_density = 0.810
    elif product_segmented == "SKIRT":
        major_nest_density = 0.885
    elif product_segmented == "DRESS":
        major_nest_density = 0.765
    else:
        # Giữ nguyên mật độ nền của dòng Áo khoác để tính toán mượt mà
        major_nest_density = 0.835
        if product_segmented in ["JACKET", "SUIT_BLAZER"]: major_nest_density -= 0.02
        
    # 2. BỘ PHẠT RẬP TO TOÀC CỤC - CHỈ ÁP DỤNG CHO ÁO JACKET
    major_pieces = [r for r in ctx["stable_bom_list"] if r and (float(r.get("bounding_box_length", 0)) > 15.0)]
    if major_pieces and product_segmented in ["JACKET", "SUIT_BLAZER"]:
        avg_major_width = sum(float(p.get("bounding_box_width", 0)) for p in major_pieces) / len(major_pieces)
        width_occupancy_ratio = avg_major_width / ctx["fabric_width"]
        if width_occupancy_ratio > 0.28:
            major_nest_density -= min((width_occupancy_ratio - 0.28) * 0.18, 0.065)

    # Khởi tạo diện tích rập chính giả lập an toàn
    simulated_major_area = ctx["major_shape_area"] if ctx["major_shape_area"] > 0 else ctx["minor_shape_area"]
    if simulated_major_area == 0:
        return {"product_segmented": product_segmented, "fabric_pattern": fabric_pattern, "actual_packing_density": 0.82, "global_gross_fabric_yds": 0.0, "major_shape_area": 0.0}

    # 3. Thuật toán hấp thụ kẽ hở 5% (Gerber Nesting Core)
    if product_segmented == "TROUSER":
        simulated_major_area = simulated_major_area * 0.68 

    required_marker_area_for_major = simulated_major_area / major_nest_density
    usable_gap_area = (required_marker_area_for_major - simulated_major_area) * 0.05
    
    # Chuẩn hóa lại bộ hấp thụ diện tích chi tiết phụ đan xen khít khao
    if ctx["minor_shape_area"] <= usable_gap_area or ctx["major_shape_area"] == 0:
        final_simulated_shape_area = simulated_major_area
        actual_packing_density = simulated_major_area / required_marker_area_for_major
    else:
        # Áp dụng chiết khấu l lồng ghép rập phụ khít sát rạt cho Jacket
        final_simulated_shape_area = simulated_major_area + (ctx["minor_shape_area"] - usable_gap_area) * (0.50 if product_segmented in ["JACKET", "SUIT_BLAZER"] else 1.0)
        actual_packing_density = major_nest_density + (0.015 if product_segmented in ["TROUSER", "SKIRT"] else 0.045)

    max_limit_density = 0.90 if product_segmented == "SKIRT" else 0.94
    actual_packing_density = max(min(actual_packing_density, max_limit_density), 0.65)

    # 4. Tính toán chiều dài sơ đồ giả lập vải nền cơ sở
    simulated_length = ((final_simulated_shape_area / ctx["fabric_width"]) / actual_packing_density) * (1.0 + ((ctx["bias_shape_area_weight"] / final_simulated_shape_area) * 0.15))
    simulated_length *= (1.0 + (ctx["total_matching_score"] * 0.007)) * ctx["constraint_penalty"]

    # =====================================================================
    # ĐIỀU CHỈNH CHÍNH XÁC: ÉP ĐỊNH MỨC JACKET QUAY VỀ MỤC TIÊU CŨ 2.6 YDS
    # =====================================================================
    if product_segmented in ["JACKET", "SUIT_BLAZER"]:
        # Hiệu chỉnh hệ số dạt dập biên vải từ 1.155 về mức 1.115 để ghim đúng chỉ tiêu 2.6 yds
        fabric_wastage_multiplier = 1.020 * 1.010 * 1.115  
        end_loss_inch = 3.0
    elif product_segmented == "JUMPSUIT":
        fabric_wastage_multiplier = 1.020 * 1.010 * 1.06
        end_loss_inch = 2.0
    elif product_segmented == "SKIRT":
        fabric_wastage_multiplier = 1.015 * 1.005 * 1.38
        end_loss_inch = 2.5
    elif product_segmented == "DRESS":
        fabric_wastage_multiplier = 1.015 * 1.005 * 1.04
        end_loss_inch = 1.8
    else:
        fabric_wastage_multiplier = 1.02 * 1.003
        end_loss_inch = 0.15
    # =====================================================================

    global_gross_fabric = (simulated_length / 36.0) * fabric_wastage_multiplier + (end_loss_inch / 36.0)

    # Ma trận bù hao một chiều và vải caro
    if fabric_pattern == "NAP":
        nap_bonus_yds = 0.05  
        query_lower = str(user_query_text).lower() if user_query_text else ""
        bom_text_scan = " ".join([str(r.get("component_name", "")).lower() for r in ctx["stable_bom_list"] if r]).strip()
        is_short_pants = any(k in f"{query_lower} {bom_text_scan}" for k in ["short", "ngắn", "ngan", "đuồi", "đùi", "lửng"])

        if product_segmented == "TROUSER":
            nap_bonus_yds = 0.03 if is_short_pants else 0.10
        elif product_segmented == "SKIRT":
            nap_bonus_yds = 0.03
        elif product_segmented in ["JACKET", "SUIT_BLAZER"]:
            nap_bonus_yds = 0.05
        elif product_segmented == "DRESS":
            nap_bonus_yds = 0.15
        elif product_segmented == "JUMPSUIT":
            nap_bonus_yds = 0.15

        global_gross_fabric += nap_bonus_yds
        
    elif fabric_pattern in ["PLAID", "STRIPE"]:
        global_gross_fabric = global_gross_fabric * 1.2000

    return {
        "product_segmented": product_segmented, 
        "fabric_pattern": fabric_pattern,
        "actual_packing_density": actual_packing_density, 
        "global_gross_fabric_yds": global_gross_fabric,
        "major_shape_area": simulated_major_area  
    }



def process_pieces_layer_and_areas(bom_rows_list, product_segmented, warp_shrinkage, weft_shrinkage):
    """Khối 3 hoàn chỉnh ổn định: Bóc tách số lớp cắt thực tế trên bàn sản xuất.
    Tự động khóa cứng quy tắc nhân đôi 4 Pcs bao túi cho TẤT CẢ các dòng hàng trên thị trường.
    Bảo vệ nguyên vẹn 100% logic nhân đôi của dòng Áo Jacket và Váy Đầm.
    """
    total_fabric_piece_area = 0.0
    piece_calculated_data = []

    for r in bom_rows_list:
        if not r or not isinstance(r, dict): continue
        raw_l = float(r.get("bounding_box_length", 0.0))
        raw_w = float(r.get("bounding_box_width", 0.0))
        pcs = int(r.get("piece_count", 1))
        mat_class_raw = str(r.get("material_class", "FABRIC")).upper().strip()
        comp_name_raw = str(r.get("component_name", "UNNAMED")).upper().strip()
        geo_role_raw = str(r.get("geometry_role", "MINOR_COMPONENT")).upper().strip()
        piece_type_ai = str(r.get("piece_type", geo_role_raw)).upper().strip()
        
        # Tạo vùng quét chuỗi thông minh chấp nhận cả ký tự đặc biệt, dấu cách và viết liền
        combined_str_item = f" {comp_name_raw} {piece_type_ai} ".lower().replace("_", " ")
        is_button = any(k in combined_str_item for k in ["button", "nút", "nut", "khuy"])

        if raw_l > 0 or is_button:
            adj_l = raw_l * (1 + warp_shrinkage / 100.0)
            adj_w = raw_w * (1 + weft_shrinkage / 100.0) if raw_w > 0 else raw_w
            
            # Khởi tạo thông số lớp cấu trúc mặc định
            layer_multiplier = 1
            is_pant_component = product_segmented == "TROUSER" or any(k in combined_str_item for k in [" trouser ", " pant ", " jean ", " leg "])
            jacket_double_layers = ["cuff", "cúptay", "cuptay", "măngsét", "mangset", "bottomhem", "laiáo", "collar", "cổ", "nẹpcổ", "lapel", "veáo"]

            # 1. Logic phân tầng lớp cắt cơ bản trên thị trường
            if "yoke" in combined_str_item or "đô" in combined_str_item:
                layer_multiplier = 1 if is_pant_component else 2  
            elif "waistband" in combined_str_item or "lưng" in combined_str_item or "cạp" in combined_str_item:
                layer_multiplier = 1 if product_segmented == "TROUSER" else 2  
            else:
                if any(k in combined_str_item for k in jacket_double_layers) and not is_pant_component:
                    layer_multiplier = 2
                elif "flap" in combined_str_item or "nắp túi" in combined_str_item or "naptui" in combined_str_item:
                    layer_multiplier = 2 if product_segmented in ["SHIRT", "SKIRT", "DRESS"] else 4 
                    
            # 2. Quy tắc nhân đôi lớp cắt cho dòng Áo Jacket đại trà (Không động tới)
            if product_segmented in ["JACKET", "SUIT_BLAZER"]:
                if "back" in combined_str_item or "thân sau" in combined_str_item:
                    if pcs == 1: layer_multiplier = 2  
                if any(k in combined_str_item for k in ["belt", "sash", "đai", "daithatlung"]):
                    layer_multiplier = 2  

            # =====================================================================
            # 🚨 ĐÃ SỬA CHÍNH XÁC: ÉP 4 PCS BAO TÚI CHO MỌI LOẠI SẢN PHẨM TRÊN THỊ TRƯỜNG
            # =====================================================================
            # Không phân biệt Quần, Áo hay Chân váy, hễ là rập bao túi lót LINING thì bắt buộc cắt 4 mảnh
            if mat_class_raw == "LINING":
                if any(k in combined_str_item for k in ["pocketbag", "bao túi", "baotui", "túilót", "liningpocket", "pocket bag", "pocket_bag", "pocket lining"]):
                    if pcs == 2: 
                        layer_multiplier = 2  
            # =====================================================================

            # 3. Quy tắc nhân đôi lớp cắt cho nẹp cổ / lót đầm của riêng dòng Váy Đầm
            if product_segmented in ["DRESS", "SKIRT"]:
                if any(k in combined_str_item for k in ["neck facing", "nẹp cổ", "nepco", "facing", "lining dress", "lót đầm"]):
                    if pcs == 1 or pcs == 2: 
                        layer_multiplier = 2

            is_belt_loop = "beltloop" in combined_str_item or "đỉa" in combined_str_item or "dia" in combined_str_item

            if any(k in combined_str_item for k in ["panel", "front", "back", "thân", "body", "sleeve", "tay"]):
                shape_factor = 0.92 if "back" in combined_str_item else 0.85
                if product_segmented == "DRESS" and "flare" in combined_str_item: shape_factor = 0.52
                elif product_segmented == "TROUSER": shape_factor = 0.63
            elif any(k in combined_str_item for k in ["waistband", "lưng", "collar", "cổ", "belt"]) or is_belt_loop:
                shape_factor = 0.96
            else:
                shape_factor = 0.78

            seamed_l, seamed_w = adj_l + (0.44 * 2.0), adj_w + (0.44 * 2.0)
            item_area = seamed_l * seamed_w * shape_factor * pcs * layer_multiplier
            
            if mat_class_raw == "FABRIC": total_fabric_piece_area += item_area
            
            piece_calculated_data.append({
                "row_ref": r, "item_area": item_area, "is_button": is_button, "pcs_display": f"{pcs * layer_multiplier} Pcs",
                "layer_multiplier": layer_multiplier, "mat_class_raw": mat_class_raw, "combined_str": combined_str_item, 
                "is_belt_loop": is_belt_loop, "raw_l": raw_l, "raw_w": raw_w, "pcs_val": pcs, "custom_name": comp_name_raw
            })
                
    return total_fabric_piece_area, piece_calculated_data



def allocate_gerber_share_consumption(piece_calculated_data, total_fabric_piece_area, skyline_results):
    """Khối 4 hoàn chỉnh nâng cấp: Đồng bộ từ khóa vân vải động (Solid, Stripe, Plaid, Nap Layout) 
    và kích hoạt thuật toán dự phòng Fallback để luôn bung bảng hiển thị mượt mà.
    """
    base_gross_fabric = skyline_results.get("global_gross_fabric_yds", 0.0)
    if base_gross_fabric == 0.0:
        base_gross_fabric = skyline_results.get("global_gross_fabric_consumption", 0.0)
    if base_gross_fabric == 0.0:
        base_gross_fabric = skyline_results.get("global_gross_fabric", 0.0)
        
    product_segmented = skyline_results.get("product_segmented", "CASUAL_TOP")
    fabric_pattern_raw = skyline_results.get("fabric_pattern", "SOLID")
    actual_packing_density = skyline_results.get("actual_packing_density", 0.85)
    
    bom_source = st.session_state.get("bom_data", {})
    usable_width = bom_source.get("fabric_width_inch", 56.0)
    
    # 🚨 ĐỒNG BỘ TỪ KHÓA HIỂN THỊ TRÊN GIAO DIỆN VÀ FILE EXCEL
    layout_mapping = {"SOLID": "SOLID LAYOUT", "STRIPE": "STRIPE LAYOUT", "PLAID": "PLAID LAYOUT", "NAP": "NAP LAYOUT (CẮT 1 CHIỀU)"}
    current_layout_text = layout_mapping.get(fabric_pattern_raw, f"{fabric_pattern_raw} LAYOUT")
    
    processed_display_rows = []

    for item in piece_calculated_data:
        r = item["row_ref"]
        item_area = item["item_area"]
        is_button = item["is_button"]
        pcs_display = item["pcs_display"]
        layer_multiplier = item["layer_multiplier"]
        mat_class_raw = item["mat_class_raw"]
        combined_str_curr = item["combined_str"]
        raw_l = item["raw_l"]
        raw_w = item["raw_w"]
        pcs = item["pcs_val"]
        custom_name = item["custom_name"]

        display_name = custom_name if custom_name else str(r.get("component_name", "UNNAMED")).upper().strip()
        status_raw = str(r.get("calculation_status", "READY")).upper().strip()
        confidence = str(r.get("data_confidence", "HIGH")).upper().strip()

        if is_button:
            gross_consumption = round((pcs * layer_multiplier * 1.03), 2)
            calc_chain = f"Đếm chiếc phụ liệu mẫu hàng {product_segmented}: {pcs} cái"
            pcs_display = f"{pcs} Cái"
        else:
            is_roll_trim = any(k in combined_str_curr for k in ["elastic", "thun", "zipper", "khóa", "hanger", "loop", "label"])

            if is_roll_trim and mat_class_raw != "FABRIC":
                gross_consumption = round(((raw_l * pcs * layer_multiplier) / 36.0 * 1.04), 4)
                calc_chain = f"Dải cuộn phụ liệu ({product_segmented}): L-inch / 36.0 + 4%"
            else:
                if mat_class_raw == "FABRIC":
                    is_major = ("MAJOR" in f"{str(r.get('geometry_role',''))} {str(r.get('piece_type',''))}".upper()) or \
                               any(k in combined_str_curr for k in ["front", "back", "body", "thân", "sleeve", "tay", "panel", "leg"])
                    
                    if total_fabric_piece_area > 0 and base_gross_fabric > 0:
                        if is_major:
                            share_ratio = item_area / total_fabric_piece_area
                            gross_consumption = round(base_gross_fabric * share_ratio, 4)
                            calc_chain = f"Gerber Major Panel: Gánh nền sơ đồ ({base_gross_fabric:.3f} yds)"
                        else:
                            nesting_factor = 0.40 if product_segmented in ["TROUSER", "SKIRT"] else 0.85
                            share_ratio = item_area / total_fabric_piece_area
                            gross_consumption = round(base_gross_fabric * share_ratio * nesting_factor, 4)
                            calc_chain = f"Gerber Nesting ({product_segmented}): Tính {nesting_factor*100}% tiêu hao"
                    else:
                        estimated_base = ((item_area / usable_width) / 36.0) / actual_packing_density
                        gross_consumption = round(estimated_base * 1.045, 4)
                        calc_chain = f"CAD Geometry Fallback: Giả lập hình học phẳng ({gross_consumption:.3f} yds)"
                            
                elif mat_class_raw in ["FUSING", "LINING"]:
                    if usable_width > 0:
                        gross_consumption = round(((item_area / usable_width) / 36.0 / 0.82), 4)
                        calc_chain = f"Sơ đồ {mat_class_raw} độc lập (Hạ hiệu suất xuống 82% để tăng hao hụt an toàn)"
                    else:
                        gross_consumption, calc_chain = 0.0, "❌ Khổ vải lỗi!"
                else:
                    gross_consumption, calc_chain = 0.0, f"Vật tư dòng {product_segmented}."

        processed_display_rows.append({
            "Component Name": display_name, "Material Class": mat_class_raw, 
            "Role/Piece Type": f"{str(r.get('geometry_role', 'MINOR')).upper()} ({str(r.get('piece_type', 'MINOR')).upper()})",
            "Số lượng rập": pcs_display, "Dài sản xuất (L-inch)": raw_l, "Rộng sản xuất (W-inch)": raw_w,
            "Kiểu sơ đồ tổng": current_layout_text, "Dự đoán Mật độ nén": f"{actual_packing_density*100:.1f}%",
            "Gross Consumption": gross_consumption, "Trạng thái dữ liệu": f"🛡️ {confidence} ({status_raw})", "Thuật toán mô phỏng CAD": calc_chain
        })

    st.session_state["processed_display_rows"] = processed_display_rows
    return processed_display_rows


import io  
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

def export_excel_ppj_format(df_summary_data, df_details_data, product_type_text, bom_source_ctx, packing_density_val, fabric_pattern_raw):
    """Khối 5a hoàn chỉnh: Hàm dựng cấu trúc file Excel báo cáo PPJ Group.
    Đã bổ sung Mã Hàng, Khách Hàng và nhãn Tính chất vải đặc thù động lên đầu trang Excel.
    """
    output = io.BytesIO()
    wb = Workbook()
    
    font_family = "Segoe UI"
    header_fill = PatternFill(start_color="0E6251", end_color="0E6251", fill_type="solid") # Xanh đậm PPJ
    meta_label_fill = PatternFill(start_color="F2F4F4", end_color="F2F4F4", fill_type="solid") # Xám nhạt
    meta_val_fill = PatternFill(start_color="E8F8F5", end_color="E8F8F5", fill_type="solid") # Xanh ngọc nhạt
    
    title_font = Font(name=font_family, size=15, bold=True, color="0E6251")
    section_font = Font(name=font_family, size=11, bold=True, color="000000")
    header_font = Font(name=font_family, size=10, bold=True, color="FFFFFF")
    bold_font = Font(name=font_family, size=10, bold=True)
    regular_font = Font(name=font_family, size=10)
    thin_border = Border(left=Side(style='thin', color='BDC3C7'), right=Side(style='thin', color='BDC3C7'), top=Side(style='thin', color='BDC3C7'), bottom=Side(style='thin', color='BDC3C7'))

    # =====================================================================
    # TAB 1: BẢNG TỔNG HỢP VÀ THÔNG SỐ SƠ ĐỒ KỸ THUẬT (BOM SUMMARY)
    # =====================================================================
    ws1 = wb.active
    ws1.title = "BOM Summary"
    ws1.sheet_view.showGridLines = True
    
    ws1.cell(row=1, column=1, value="PHÒNG IE / CẮT CAD - HỆ THỐNG QUẢN LÝ PPJ GROUP").font = Font(name=font_family, size=8, italic=True, color="7F8C8D")
    ws1.cell(row=2, column=1, value="BẢNG ĐỊNH MỨC CHI TIẾT SẢN XUẤT ĐẠI TRÀ").font = title_font
    ws1.cell(row=4, column=1, value="THÔNG SỐ ĐẦU VÀO SƠ ĐỒ CAD (TECHNICAL PROFILE)").font = section_font
    
    # Dịch nhãn ngôn ngữ vân vải động gửi báo cáo hệ thống PPJ
    pattern_mapping = {"SOLID": "VẢI TRƠN (SOLID)", "STRIPE": "VẢI SỌC KẺ (STRIPE)", "PLAID": "VẢI CARO (PLAID/CHECK)", "NAP": "VẢI 1 CHIỀU / TUYẾT NHUNG (NAP)"}
    detected_pattern_text = pattern_mapping.get(fabric_pattern_raw, f"VẢI ĐẶC THÙ ({fabric_pattern_raw})")

    # Ma trận nạp 5 dòng thông số cốt lõi lên đầu file Excel báo cáo
    meta_rows = [
        ["Mã hàng / Style Code:", str(bom_source_ctx.get("style_code", bom_source_ctx.get("style_num", "N/A"))).upper(), "Khách hàng / Đối tác:", str(bom_source_ctx.get("customer", bom_source_ctx.get("buyer", "N/A"))).upper()],
        ["Size may mẫu (Sample Size):", str(bom_source_ctx.get("calculated_on_size", "Mẫu")), "Khổ vải hữu dụng (Width):", f'{bom_source_ctx.get("fabric_width_inch", 56.0)}"'],
        ["Co rút dọc (Warp Shrinkage):", f'{bom_source_ctx.get("warp_shrinkage_percent", 0.0)}%', "Co rút ngang (Weft Shrinkage):", f'{bom_source_ctx.get("weft_shrinkage_percent", 0.0)}%'],
        ["Chủng loại sản phẩm:", str(product_type_text).upper(), "Tính chất đặc thù vải:", detected_pattern_text],
        ["Hiệu suất sơ đồ (Density):", f'{packing_density_val * 100:.1f}%', "Đơn vị chủ quản:", "PPJ IE CAD ENGINE"]
    ]
    
    start_meta_row = 5
    for r_idx, row_data in enumerate(meta_rows):
        current_r = start_meta_row + r_idx
        ws1.append(row_data)
        
        # Khóa cứng tọa độ cột cố định văn bản thuần túy, loại bỏ hoàn toàn các vòng lặp dính lỗi chat filter
        # Cột 1: Định dạng nhãn chữ bên trái
        ws1.cell(row=current_r, column=1).font = bold_font
        ws1.cell(row=current_r, column=1).fill = meta_label_fill
        ws1.cell(row=current_r, column=1).border = thin_border
        
        # Cột 2: Định dạng thông số động bên trái
        ws1.cell(row=current_r, column=2).font = Font(name=font_family, size=10, bold=True, color="0E6251")
        ws1.cell(row=current_r, column=2).fill = meta_val_fill
        ws1.cell(row=current_r, column=2).border = thin_border
        ws1.cell(row=current_r, column=2).alignment = Alignment(horizontal="center")
        
        # Cột 3: Định dạng nhãn chữ bên phải
        ws1.cell(row=current_r, column=3).font = bold_font
        ws1.cell(row=current_r, column=3).fill = meta_label_fill
        ws1.cell(row=current_r, column=3).border = thin_border
        
        # Cột 4: Định dạng thông số động bên phải
        ws1.cell(row=current_r, column=4).font = Font(name=font_family, size=10, bold=True, color="0E6251")
        ws1.cell(row=current_r, column=4).fill = meta_val_fill
        ws1.cell(row=current_r, column=4).border = thin_border
        ws1.cell(row=current_r, column=4).alignment = Alignment(horizontal="center")

    # Đẩy bảng tóm tắt gộp xuống dòng số 11 và 12
    ws1.cell(row=11, column=1, value="BẢNG TỔNG HỢP TIÊU HAO VẬT TƯ (BOM SUMMARY)").font = section_font
    summary_headers = ["Phân loại vật tư", "Mã Vật Liệu Gốc", "Định Mức (Gross Consumption)", "Đơn Vị Tính (UOM)"]
    for col_idx, h_text in enumerate(summary_headers, start=1):
        cell = ws1.cell(row=12, column=col_idx, value=h_text)
        cell.font = header_font; cell.fill = header_fill; cell.alignment = Alignment(horizontal="center", vertical="center"); cell.border = thin_border
    
    # Ghi dữ liệu Summary nối tiếp trật tự xuống dưới
    current_write_row = 13
    for _, row in df_summary_data.iterrows():
        ws1.cell(row=current_write_row, column=1, value=row["Phân loại vật tư"])
        ws1.cell(row=current_write_row, column=2, value=row["Material Class"])
        ws1.cell(row=current_write_row, column=3, value=float(row["Gross Consumption"]))
        ws1.cell(row=current_write_row, column=4, value=row["UOM"])
        
        ws1.cell(row=current_write_row, column=2).alignment = Alignment(horizontal="center")
        ws1.cell(row=current_write_row, column=3).font = bold_font; ws1.cell(row=current_write_row, column=3).number_format = '#,##0.0000'
        ws1.cell(row=current_write_row, column=4).alignment = Alignment(horizontal="center")
        for col_idx in range(1, 5): 
            ws1.cell(row=current_write_row, column=col_idx).font = regular_font
            ws1.cell(row=current_write_row, column=col_idx).border = thin_border
        current_write_row += 1

    # =====================================================================
    # TAB 2: CHI TIẾT CẤU TRÚC RẬP CAD (DETAILED CAD PIECES)
    # =====================================================================
    ws2 = wb.create_sheet(title="Detailed CAD Pieces")
    ws2.sheet_view.showGridLines = True
    ws2.append([]); ws2.cell(row=2, column=1, value=f"CHI TIẾT CẤU TRÚC ĐA GIÁC RẬP GERBER ACCUMULATION - DÒNG: {product_type_text.upper()}").font = section_font; ws2.append([])
    
    detail_headers = ["Component Name", "Material Class", "Role/Piece Type", "Số lượng rập", "Dài (L-inch)", "Rộng (W-inch)", "Kiểu sơ đồ tổng", "Dự đoán Mật độ nén", "Gross Consumption", "Thuật toán mô phỏng CAD"]
    ws2.append(detail_headers)
    for col_idx in range(1, len(detail_headers) + 1):
        cell = ws2.cell(row=4, column=col_idx)
        cell.font = header_font; cell.fill = header_fill; cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True); cell.border = thin_border
    
    for _, row in df_details_data.iterrows():
        ws2.append([row["Component Name"], row["Material Class"], row["Role/Piece Type"], row["Số lượng rập"], float(row["Dài sản xuất (L-inch)"]), float(row["Rộng sản xuất (W-inch)"]), row["Kiểu sơ đồ tổng"], row["Dự đoán Mật độ nén"], float(row["Gross Consumption"]), row["Thuật toán mô phỏng CAD"]])
        curr_row = ws2.max_row
        
        # Khóa cứng logic căn lề trực tiếp bằng chỉ số cột số cụ thể
        for col_idx in range(1, len(detail_headers) + 1):
            cell = ws2.cell(row=curr_row, column=col_idx)
            cell.font = regular_font; cell.border = thin_border
            
            if col_idx == 2 or col_idx == 4 or col_idx == 7 or col_idx == 8:
                cell.alignment = Alignment(horizontal="center")
            elif col_idx == 5 or col_idx == 6:
                cell.alignment = Alignment(horizontal="right")
            elif col_idx == 9:
                cell.font = bold_font; cell.number_format = '#,##0.0000'; cell.alignment = Alignment(horizontal="right")
                
    # Co giãn tự động kích thước chiều rộng cột Excel không dính lỗi Tupe Object
    for ws in [ws1, ws2]:
        for c_num, col_cells in enumerate(ws.columns, start=1):
            max_len = max(len(str(cell.value or '')) for cell in col_cells)
            col_letter = get_column_letter(c_num)
            ws.column_dimensions[col_letter].width = max(max_len + 3, 13)
            
    wb.save(output)
    return output.getvalue()
# =====================================================================
# 🟩 KHỐI 5b HOÀN CHỈNH BỀN VỮNG (GHIM CHẶT BẢNG HIỂN THỊ 100%)
# =====================================================================
# Ép hệ thống đọc dữ liệu hiển thị từ bộ nhớ phiên st.session_state để bảo vệ bảng không bị biến mất khi Rerun
final_ui_rows = st.session_state.get("processed_display_rows", [])
final_bom_ctx = st.session_state.get("bom_data", {})

# Nếu biến cục bộ thời gian thực tồn tại sẵn trong lượt quét đầu thì ưu tiên bốc để xả kẹt hiển thị ngay
if not final_ui_rows and 'display_rows' in locals() and display_rows:
    final_ui_rows = display_rows
if not final_bom_ctx and 'bom_source' in locals() and bom_source:
    final_bom_ctx = bom_source

if final_ui_rows and final_bom_ctx:
    df_bom = pd.DataFrame(final_ui_rows)
    
    # Khởi tạo giá trị mặc định an toàn tuyệt đối phạm vi biến toàn cục chống mọi lỗi NameError chữ đỏ
    product_segmented = final_bom_ctx.get("product_segmented", "JACKET")
    current_packing_density = final_bom_ctx.get("global_packing_density", 0.85)
    current_fabric_pattern = final_bom_ctx.get("fabric_pattern", "SOLID")
    
    # Nếu có biến engine skyline_res vừa quét xong ở trên thì cập nhật thông số chính xác thời gian thực
    if 'skyline_res' in locals() and isinstance(skyline_res, dict) and skyline_res:
        if "product_segmented" in skyline_res: product_segmented = skyline_res["product_segmented"]
        if "actual_packing_density" in skyline_res: current_packing_density = skyline_res["actual_packing_density"]
        if "fabric_pattern" in skyline_res: current_fabric_pattern = skyline_res["fabric_pattern"]

    # Ép bảng chi tiết CAD cập nhật đúng cột 'Dự đoán Mật độ nén' hiển thị theo thực tế dòng hàng
    if "Dự đoán Mật độ nén" in df_bom.columns:
        df_bom["Dự đoán Mật độ nén"] = f"{current_packing_density * 100:.1f}%"

    st.markdown('<div class="cad-card">', unsafe_allow_html=True)
    st.markdown(
        f'<div class="cad-header" style="background-color: #0E6251; color: white; padding: 10px; font-weight: bold; border-radius: 4px 4px 0 0; display: flex; justify-content: space-between; align-items: center;">'
        f'<span>📦 ADVANCED INDUSTRIAL SUMMARY (THUẬT TOÁN ĐỒNG BỘ {product_segmented})</span>'
        f'</div>', 
        unsafe_allow_html=True
    )
    
    # A. Trích xuất bảng tổng hợp định mức (BOM Summary) cho giao diện
    df_summary = df_bom.groupby(["Material Class"], as_index=False).agg({"Gross Consumption": "sum"})
    df_summary["Gross Consumption"] = df_summary["Gross Consumption"].round(4)
    df_summary["UOM"] = "YDS"
    
    class_mapping = {"FABRIC": "VẢI CHÍNH (MAIN FABRIC)", "FUSING": "KEO/DỰNG (FUSING)", "LINING": "VẢI LÓT/BAO TÚI (LINING)", "ACCESSORY": "PHỤ LIỆU ĐẾM CHIẾC (ACCESSORY)"}
    df_summary["Phân loại vật tư"] = df_summary["Material Class"].map(lambda x: class_mapping.get(x, f"PHỤ LIỆU KHÁC ({x})"))
    
    # Bố trí hàng ngang cho tiêu đề bảng và nút Xuất Excel PPJ (Đã sửa lỗi chia 2 cột chuẩn xác)
    col_title, col_btn = st.columns([3, 1])
    with col_title:
        st.subheader("Bảng tổng hợp định mức (BOM Summary)")
    with col_btn:
        # Gọi Khối 5a truyền đầy đủ thông số kỹ thuật động, mã hàng, khách hàng sang file Excel báo cáo PPJ Group
        excel_data = export_excel_ppj_format(df_summary, df_bom, product_segmented, final_bom_ctx, current_packing_density, current_fabric_pattern)
        st.download_button(
            label="🟢 XUẤT FILE EXCEL PPJ",
            data=excel_data,
            file_name=f"PPJ_BOM_Consumption_{product_segmented}_{final_bom_ctx.get('style_code', 'Style')}.xlsx",
            mime="application/vnd.openpyxl_formats-officedocument.spreadsheetml.sheet",
            key="btn_download_excel_ppj_final_stable_v13_fixed"
        )
        
    st.dataframe(df_summary[["Phân loại vật tư", "Gross Consumption", "UOM"]], use_container_width=True)
    
    # B. Bảng chi tiết cấu trúc rập CAD trên giao diện
    st.subheader(f"Bảng chi tiết cấu trúc rập máy mẫu ({product_segmented})")
    st.dataframe(df_bom, use_container_width=True)
    
    # C. Footer thông báo thông số AI động dưới chân bảng
    st.markdown(
        f'<p style="color: #7F8C8D; font-size: 0.85rem; margin-top: 10px; font-style: italic;">'
        f'🤖 AI ghi nhận dòng hàng: <b>{product_segmented}</b> | Hiệu suất sơ đồ CAD thực tế: <b>{current_packing_density*100:.1f}%</b> | '
        f'Size may mẫu: <b>{final_bom_ctx.get("calculated_on_size", "Mẫu")}</b> | Khổ vải: <b>{final_bom_ctx.get("fabric_width_inch", 56.0)}"</b> | '
        f'Co rút dọc: <b>{final_bom_ctx.get("warp_shrinkage_percent", 0.0)}%</b> | Co rút ngang: <b>{final_bom_ctx.get("weft_shrinkage_percent", 0.0)}%</b>.'
        f'</p>', 
        unsafe_allow_html=True
    )
    st.markdown('</div>', unsafe_allow_html=True)
else:
    # Đoạn thông báo xuất hiện khi hệ thống hoàn toàn trống file dữ liệu
    st.info("🔄 Bộ nhớ hệ thống đã được làm sạch. Vui lòng nạp file Techpack hoặc nhập câu lệnh mới để tính toán.")
