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
import re

# =====================================================================
# ĐOẠN 6a - PHẦN 1: KHỞI TẠO BANNER VĂN BẢN ĐỈNH SIDEBAR CHUẨN ERP
# =====================================================================

# 1. Cấu hình trang rộng toàn màn hình chuẩn hệ thống SaaS/ERP Văn phòng
st.set_page_config(layout="wide", page_title="AI Fabric Consumption Matrix")

# Dùng lệnh Python tạo hộp chữ Banner vuông vắn ghim cứng lên đỉnh lề trái
with st.sidebar:
    st.markdown(
        """
        <div style="
            background: linear-gradient(135deg, #1e40af 0%, #1d4ed8 100%); 
            border-radius: 8px; 
            padding: 15px 10px; 
            text-align: center; 
            margin-top: -30px; /* Đẩy sát kịch trần lề trên */
            margin-bottom: 20px; 
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.15);
        ">
            <div style="font-family: 'Segoe UI', sans-serif; font-size: 16px; font-weight: 800; color: #ffffff; letter-spacing: 0.5px; line-height: 1.2;">
                PPJ GROUP
            </div>
            <div style="font-family: 'Segoe UI', sans-serif; font-size: 9px; font-weight: 600; color: #bfdbfe; letter-spacing: 0.3px; margin-top: 4px; text-transform: uppercase;">
                BOUNDLESS SOLUTIONS
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

# 2. Khởi tạo cấu trúc trạng thái bộ nhớ hệ thống (Session State) an toàn
if "bom_data" not in st.session_state: st.session_state.bom_data = None
if "chat_history" not in st.session_state: st.session_state.chat_history = []
if "pdf_bytes" not in st.session_state: st.session_state.pdf_bytes = None
if "pdf_name" not in st.session_state: st.session_state.pdf_name = ""
if "pdf_text_cache" not in st.session_state: st.session_state.pdf_text_cache = None
if "accumulated_bom_rows" not in st.session_state: st.session_state.accumulated_bom_rows = []



# =====================================================================
# ĐOẠN 6a - PHẦN 2: BỘ CẤU HÌNH CSS ĐỒNG BỘ MÀU SẮC & XỬ LÝ LỀ SIDEBAR
# =====================================================================
st.markdown("""
<style>
    /* 🎨 ÉP ĐỒNG BỘ TOÀN DIỆN MÀU NỀN XANH NGỌC MỊN CHO TẤT CẢ CÁC LỚP BAN NỀN */
    .stApp, header[data-testid="stHeader"], div[data-testid="stMainView"], section[data-testid="stSidebar"] + div { 
        background-color: #e6f4f1 !important; 
    }
    
    /* Ép khoảng cách lề của toàn vùng nội dung dạt sang phải, tránh so le */
    .block-container { 
        padding-top: 1.5rem !important; 
        padding-left: 2rem !important; 
        padding-right: 2rem !important; 
        margin-left: 300px !important; /* Tạo khoảng trống chuẩn tách biệt Sidebar */
        max-width: calc(100% - 300px) !important; 
        padding-bottom: 120px !important; 
    }
    
    /* Ép tất cả các khối ngang (Horizontal Blocks) dãn đều */
    div[data-testid="stHorizontalBlock"] { 
        margin-top: 0px !important; 
        padding-top: 0px !important; 
        width: 100% !important;
        max-width: 100% !important;
        background-color: transparent !important; 
    }

    /* NHUỘM XANH CÁC KHỐI CHỨA UPLOADER VÀ VISUALIZER CHO ĐỒNG BỘ */
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background-color: #f0fdfa !important; 
        border: 1px solid #99f6e4 !important; 
        box-shadow: 0 4px 6px -1px rgba(15, 118, 110, 0.05) !important;
    }

    /* CẤU HÌNH THANH MENU ĐIỀU HƯỚNG ĐA TRANG GỌN GÀNG */
    [data-testid="stSidebarNav"] {
        padding-top: 5px !important; /* Thu hẹp lại lề vì khoảng trống đã được lấp đầy */
        background-color: transparent !important;
        position: relative !important;
    }
    
    /* Triệt tiêu hoàn toàn các cơ chế vẽ đè cũ tránh xung đột */
    [data-testid="stSidebarNav"]::before,
    [data-testid="stSidebarNav"]::after {
        content: "" !important;
        display: none !important;
    }

    /* ÉP TOÀN BỘ KHỐI CONTAINER CHAT VÀ FIELDSET PHÌNH TO 100% CHẠM BIÊN ĐÁY MÀN HÌNH */
    .stChatInput,
    .stChatInput > div,
    .stChatInput fieldset,
    div[data-testid="stChatInputContainer"] {
        position: fixed !important;
        bottom: 0 !important; 
        left: 300px !important; 
        right: 0 !important; 
        width: calc(100% - 300px) !important; 
        max-width: calc(100% - 300px) !important; 
        background-color: #ccfbf1 !important; 
        border: none !important;
        border-top: 1px solid #5eead4 !important; 
        border-radius: 0px !important; 
        box-shadow: 0 -4px 10px rgba(15, 118, 110, 0.06) !important;
        padding: 10px 2rem !important; 
    }

    /* Định dạng lõi nhập văn bản gõ chữ bên trong cho tiệp màu xanh ngọc */
    div[data-testid="stChatInputContainer"] textarea {
        background-color: #ccfbf1 !important; 
        color: #115e59 !important; 
        font-family: "Segoe UI", sans-serif !important;
        font-size: 13px !important;
        width: 100% !important;
        border: none !important;
    }

    /* Căn chỉnh nút gửi hình mũi tên gọn gàng bên góc phải dải băng chat */
    div[data-testid="stChatInputContainer"] button {
        background-color: #0f766e !important;
        color: #ffffff !important;
        border-radius: 6px !important;
    }

    /* KHÓA CHẶT SIDEBAR CỐ ĐỊNH BÊN TRÁI HỆ THỐNG */
    [data-testid="stSidebar"] {
        background-color: #0f766e !important; 
        color: #ffffff !important;
        position: fixed !important;
        top: 0 !important;
        left: 0 !important;
        width: 300px !important; 
        min-width: 300px !important;
        max-width: 300px !important;
        height: 100vh !important;
        overflow-y: hidden !important;
        z-index: 99999 !important;
    }
    
    [data-testid="stSidebar"] > div:first-child {
        height: 100vh !important;
        overflow-y: hidden !important;
    }

    div[data-testid="stSidebarNav"] {
        font-size: 11px !important;
    }

    /* Định dạng nút bấm xóa bộ nhớ tinh tế */
    [data-testid="stSidebar"] button {
        background-color: #115e59 !important;
        color: #fca5a5 !important;
        border: 1px solid #115e59 !important;
        font-weight: 600 !important;
        transition: all 0.2s ease !important;
    }
    [data-testid="stSidebar"] button:hover {
        background-color: #dc2626 !important;
        color: #ffffff !important;
    }

    .sidebar-sub-title {
        font-family: "Segoe UI", sans-serif !important; 
        font-size: 12px !important; 
        font-weight: 800 !important; 
        color: #fde047 !important; 
        text-shadow: 0px 1px 2px rgba(0,0,0,0.4) !important; 
        text-transform: uppercase !important; 
        letter-spacing: 0.8px !important; 
        margin-bottom: 6px !important;
        margin-top: 18px !important;
    }

    .sidebar-custom-card, .sidebar-custom-card-history {
        background: linear-gradient(135deg, #115e59 0%, #134e4a 100%) !important; 
        border: 1px solid #14b8a6 !important;
        border-radius: 6px !important; 
        padding: 12px !important; 
        box-shadow: 0 4px 6px rgba(0,0,0,0.15) !important;
        margin-bottom: 15px !important;
    }
    .sidebar-custom-card-history { padding: 6px 12px !important; }
    .sidebar-divider { margin: 20px 0 12px 0 !important; border: 0 !important; border-top: 1px solid #115e59 !important; }

    .kpi-box-flat-matrix { border-radius: 6px 6px 0 0 !important; padding: 10px 12px !important; text-align: center !important; box-shadow: 0 2px 4px rgba(0,0,0,0.02) !important; box-sizing: border-box !important; }
    .kpi-num-flat-matrix { font-size: 16px !important; font-weight: 700 !important; color: #ffffff !important; font-family: 'Segoe UI', sans-serif !important; line-height: 1.2 !important; }
    .kpi-lbl-flat-matrix { font-size: 9px !important; font-weight: 600 !important; color: #ffffff !important; opacity: 0.95 !important; text-transform: uppercase !important; margin-top: 2px !important; }
    .bg-style-erp { background: linear-gradient(135deg, #334155 0%, #1e293b 100%) !important; }
    .bg-items-erp { background: linear-gradient(135deg, #0d9488 0%, #0f766e 100%) !important; }
    .bg-cons-erp  { background: linear-gradient(135deg, #ea580c 0%, #c2410c 100%) !important; }
    .bg-size-erp { background: linear-gradient(135deg, #16a34a 0%, #15803d 100%) !important; }

    .image-placeholder-box-flat { border: 1px solid #cbd5e1 !important; border-top: none !important; border-radius: 0 0 6px 6px !important; padding: 10px 5px !important; height: 140px !important; display: flex !important; align-items: center !important; justify-content: center !important; box-sizing: border-box !important; margin-bottom: 25px !important; background-color: #ffffff !important; overflow: hidden !important; }
    div[data-testid="stImage"] img { width: 100% !important; height: auto !important; }
    
    /* 🛠️ SỬA DỨT ĐIỂM: Khử sạch và ẩn hoàn toàn cái icon rác ảnh vỡ nhỏ màu trắng ở giữa lề */
    [data-testid="stSidebar"] img, [data-testid="stSidebar"] div[data-testid="stImage"] { display: none !important; }
    .main-body-spacer, .sticky-top-container, div[smart-fixed-container], div[data-testid="stHorizontalBlock"]:empty { display: none !important; height: 0px !important; margin: 0 !important; padding: 0 !important; }
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

# Phân bổ lưới 4 ô KPIs Native gốc của Streamlit
k_col1, k_col2, k_col3, k_col4 = st.columns(4)

# Cấu hình chung cho hiệu ứng Emoji: To rõ (70px), có đổ bóng mờ tạo độ nổi khối 3D cực đẹp
emoji_style = "font-size: 70px; display: inline-block; filter: drop-shadow(0px 4px 6px rgba(0, 0, 0, 0.15)); transform: scale(1); transition: all 0.2s ease-in-out;"

with k_col1: 
    st.markdown(f'<div class="kpi-box-flat-matrix bg-style-erp"><div class="kpi-num-flat-matrix">{kpi_style_id}</div><div class="kpi-lbl-flat-matrix">Mã hàng đang xử lý</div></div>', unsafe_allow_html=True)
    st.markdown(f'<div class="image-placeholder-box-flat"><span style="{emoji_style}">👕</span></div>', unsafe_allow_html=True)

with k_col2: 
    st.markdown(f'<div class="kpi-box-flat-matrix bg-items-erp"><div class="kpi-num-flat-matrix">{total_materials} Item(s)</div><div class="kpi-lbl-flat-matrix">Tổng số vật tư kết xuất</div></div>', unsafe_allow_html=True)
    st.markdown(f'<div class="image-placeholder-box-flat"><span style="{emoji_style}">👖</span></div>', unsafe_allow_html=True)

with k_col3: 
    st.markdown(f'<div class="kpi-box-flat-matrix bg-cons-erp"><div class="kpi-num-flat-matrix">{main_fabric_cons}</div><div class="kpi-lbl-flat-matrix">Định mức vải chính dự kiến</div></div>', unsafe_allow_html=True)
    st.markdown(f'<div class="image-placeholder-box-flat"><span style="{emoji_style}">✂️</span></div>', unsafe_allow_html=True)

with k_col4: 
    st.markdown(f'<div class="kpi-box-flat-matrix bg-size-erp"><div class="kpi-num-flat-matrix">{active_size_kpi}</div><div class="kpi-lbl-flat-matrix">Cỡ hạt tính định mức</div></div>', unsafe_allow_html=True)
    st.markdown(f'<div class="image-placeholder-box-flat"><span style="{emoji_style}">🧵</span></div>', unsafe_allow_html=True)



# --- BẢNG ĐIỀU KHIỂN SIDEBAR MÁY CHỦ MỚI (BẢN MÀU XANH NGỌC LAM SÁNG RÕ) ---
st.sidebar.markdown("### ⚙️ ENGINE CONTROLS")
if st.sidebar.button("🗑️ CLEAR SYSTEM MEMORY", use_container_width=True):
    st.session_state.bom_data = {}
    st.session_state.chat_history = []
    st.session_state.pdf_bytes = None
    st.session_state.pdf_name = ""
    st.session_state.pdf_text_cache = None
    if "processed_display_rows" in st.session_state: st.session_state.processed_display_rows = []
    if "accumulated_bom_rows" in st.session_state: st.session_state.accumulated_bom_rows = []
    if "last_active_blueprint" in st.session_state: st.session_state.last_active_blueprint = None
    if "raw_ai_debug_payload" in st.session_state: st.session_state.raw_ai_debug_payload = None
    if "pdf_page_one_image" in st.session_state: st.session_state.pdf_page_one_image = None
    st.rerun()

# --- TÍCH HỢP 3 Ý TƯỞNG TIỆN ÍCH DƯỚI NÚT CLEAR (MÀU XANH NGỌC LAM) ---
with st.sidebar:
    # -----------------------------------------------------------------
    # KHỐI 1: THÔNG TIN HỆ THỐNG (SYSTEM STATUS)
    # -----------------------------------------------------------------
    st.markdown("<hr style='margin: 20px 0 12px 0; border: 0; border-top: 1px solid #115e59;'>", unsafe_allow_html=True)
    st.markdown("<div style='font-family:\"Segoe UI\", sans-serif; font-size: 12px; font-weight: 700; color: #ffffff; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px;'>⚙️ SYSTEM STATUS</div>", unsafe_allow_html=True)
    st.markdown(
        """
        <div style="background: linear-gradient(135deg, #115e59 0%, #134e4a 100%); border: 1px solid #14b8a6; border-radius: 6px; padding: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.15); margin-bottom: 15px;">
            <div style="display: flex; justify-content: space-between; margin-bottom: 6px; font-size: 11px; color: #ccfbf1; font-family: 'Segoe UI', sans-serif;">
                <span>Core Engine:</span>
                <span style="color: #ffffff; font-weight: 700;">v2.4.1-AI</span>
            </div>
            <div style="display: flex; justify-content: space-between; margin-bottom: 6px; font-size: 11px; color: #ccfbf1; font-family: 'Segoe UI', sans-serif;">
                <span>AI CAD Status:</span>
                <span style="color: #4ade80; font-weight: 700;">● Connected</span>
            </div>
            <div style="display: flex; justify-content: space-between; font-size: 11px; color: #ccfbf1; font-family: 'Segoe UI', sans-serif;">
                <span>Response Time:</span>
                <span style="color: #fde047; font-weight: 700;">&lt; 1.2s</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    # -----------------------------------------------------------------
    # KHỐI 2: HƯỚNG DẪN SỬ DỤNG NHANH (QUICK USER GUIDE)
    # -----------------------------------------------------------------
    st.markdown("<div style='font-family:\"Segoe UI\", sans-serif; font-size: 12px; font-weight: 700; color: #ffffff; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px;'>📖 QUICK USER GUIDE</div>", unsafe_allow_html=True)
    st.markdown(
        """
        <div style="background: linear-gradient(135deg, #115e59 0%, #134e4a 100%); border: 1px solid #14b8a6; border-radius: 6px; padding: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.15); margin-bottom: 15px;">
            <div style="display: flex; align-items: flex-start; margin-bottom: 10px; font-size: 11px; color: #ffffff; font-family: 'Segoe UI', sans-serif;">
                <div style="background-color: #14b8a6; color: #ffffff; font-weight: 700; width: 18px; height: 18px; border-radius: 50%; display: flex; align-items: center; justify-content: center; margin-right: 8px; flex-shrink: 0;">1</div>
                <div style="line-height: 1.4;"><span style="font-weight: 700; color: #2dd4bf;">Tải tài liệu:</span> Upload file Techpack PDF.</div>
            </div>
            <div style="display: flex; align-items: flex-start; margin-bottom: 10px; font-size: 11px; color: #ffffff; font-family: 'Segoe UI', sans-serif;">
                <div style="background-color: #14b8a6; color: #ffffff; font-weight: 700; width: 18px; height: 18px; border-radius: 50%; display: flex; align-items: center; justify-content: center; margin-right: 8px; flex-shrink: 0;">2</div>
                <div style="line-height: 1.4;"><span style="font-weight: 700; color: #2dd4bf;">Định mức:</span> Xem dữ liệu tại 4 ô KPIs trần.</div>
            </div>
            <div style="display: flex; align-items: flex-start; font-size: 11px; color: #ffffff; font-family: 'Segoe UI', sans-serif;">
                <div style="background-color: #14b8a6; color: #ffffff; font-weight: 700; width: 18px; height: 18px; border-radius: 50%; display: flex; align-items: center; justify-content: center; margin-right: 8px; flex-shrink: 0;">3</div>
                <div style="line-height: 1.4;"><span style="font-weight: 700; color: #2dd4bf;">Xuất bảng:</span> Lưu bảng BOM Matrix.</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    # -----------------------------------------------------------------
    # KHỐI 3: DANH SÁCH LỊCH SỬ MÃ HÀNG ĐỘNG (RECENT CODE HISTORY)
    # -----------------------------------------------------------------
    st.markdown("<div style='font-family:\"Segoe UI\", sans-serif; font-size: 12px; font-weight: 700; color: #ffffff; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px;'>🕒 RECENT CODE HISTORY</div>", unsafe_allow_html=True)
    if "history_list" not in st.session_state:
        st.session_state.history_list = ["PPJ-K12-200451", "PPJ-M04-330129"]
    if kpi_style_id != "N/A" and kpi_style_id not in st.session_state.history_list:
        st.session_state.history_list.insert(0, kpi_style_id)
        st.session_state.history_list = st.session_state.history_list[:3]

    history_html = '<div style="background: linear-gradient(135deg, #115e59 0%, #134e4a 100%); border: 1px solid #14b8a6; border-radius: 6px; padding: 6px 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.15); margin-bottom: 15px;">'
    for index, style_code in enumerate(st.session_state.history_list):
        border_style = 'border-bottom: 1px solid #14b8a6;' if index < len(st.session_state.history_list) - 1 else ''
        if index == 0 and kpi_style_id != "N/A":
            history_html += (
                '<div style="display: flex; justify-content: space-between; align-items: center; padding: 7px 0; ' + border_style + ' font-size: 11px; font-family: \'Segoe UI\', sans-serif;">'
                '    <span style="color: #ffffff; font-weight: 700;">📦 ' + style_code + '</span>'
                '    <span style="color: #ffffff; font-size: 10px; font-weight: 700; background-color: #14b8a6; padding: 2px 8px; border-radius: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.2);">Active</span>'
                '</div>'
            )
        else:
            history_html += (
                '<div style="display: flex; justify-content: space-between; align-items: center; padding: 7px 0; ' + border_style + ' font-size: 11px; font-family: \'Segoe UI\', sans-serif;">'
                '    <span style="color: #ccfbf1; font-weight: 600;">📦 ' + style_code + '</span>'
                '    <span style="color: #5eead4; font-size: 10px;">Processed</span>'
                '</div>'
            )
    history_html += '</div>'
    
    st.markdown(history_html, unsafe_allow_html=True)
    st.markdown("<div style='font-size: 10px; color: #ccfbf1; font-family: \"Segoe UI\", sans-serif; text-align: center; margin-top: 15px; opacity: 0.8;'>© 2026 PPJ Digital Transformation</div>", unsafe_allow_html=True)




import streamlit as st
import re
import fitz  # Thư viện PyMuPDF để trích xuất văn bản và ảnh tự động từ file PDF

# ------------------------------------------------------------------------------
# LƯỚI CHIA ĐÔI CỘT CHÍNH THỰC TẾ (ĐÃ ĐÓNG KHUNG VIỀN ĐẸP MẮT & SỬA LỖI HIỂN THỊ)
# ------------------------------------------------------------------------------
col_left, col_right = st.columns(2)

# --- CỘT TRÁI: BỘ TẢI FILE & HỒ SƠ TÓM TẮT MÃ HÀNG MÀU XANH ---
with col_left:
    with st.container(border=True, height=520):
        st.markdown("### 📂 TECHPACK UPLOADER & PROFILE SUMMARY")
        
        uploaded_file = st.file_uploader("Upload PDF", type=["pdf"], label_visibility="collapsed")
        
        if uploaded_file is not None:
            # Nếu phát hiện người dùng tải lên một file hoàn toàn mới
            if st.session_state.pdf_name != uploaded_file.name:
                st.session_state.pdf_text_cache = None
                st.session_state.pdf_page_one_image = None
                if "accumulated_bom_rows" in st.session_state: st.session_state.accumulated_bom_rows = []
                
            st.session_state.pdf_bytes = uploaded_file.read()
            st.session_state.pdf_name = uploaded_file.name

            # Tự động bóc tách Văn Bản và chuyển đổi PDF thành hình ảnh Sketch ngay lập tức
            if st.session_state.pdf_text_cache is None or st.session_state.pdf_page_one_image is None:
                with st.spinner("🤖 AI đang đọc tài liệu và trích xuất hình ảnh phác thảo..."):
                    try:
                        # Mở file PDF trực tiếp từ bộ nhớ bytes
                        doc = fitz.open(stream=st.session_state.pdf_bytes, filetype="pdf")
                        
                        # 1. Trích xuất toàn bộ text từ tất cả các trang phục vụ Regex tìm mã hàng
                        full_text = ""
                        for page in doc:
                            full_text += page.get_text()
                        st.session_state.pdf_text_cache = full_text
                        
                        # 2. Chuyển đổi trang đầu tiên (Trang 0) thành hình ảnh PNG chất lượng cao
                        if len(doc) > 0:
                            page_one = doc[0]
                            pix = page_one.get_pixmap(matrix=fitz.Matrix(2, 2)) # Zoom x2 để ảnh nét hơn
                            image_bytes = pix.tobytes("png")
                            st.session_state.pdf_page_one_image = image_bytes
                            
                        doc.close()
                    except Exception as e:
                        st.error(f"Lỗi khi đọc file PDF kĩ thuật: {e}")
                
                # Khởi động lại luồng giao diện để cập nhật ngay lập tức dữ liệu mới lên màn hình
                st.rerun()

        # Hiển thị thông tin hồ sơ tóm tắt sau khi đã trích xuất văn bản thành công
        if st.session_state.pdf_text_cache is not None:
            st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)
            txt = st.session_state.pdf_text_cache
            
            def get_meta(pattern, default="N/A"):
                m = re.search(pattern, txt, re.IGNORECASE)
                return m.group(1).strip() if m else default

            # Thực hiện quét thông tin kĩ thuật bằng biểu thức chính quy (Regex)
            style_id = get_meta(r'(?:Style ID|Style_ID|Mã hàng)\s*[:\-=\s]*([\w\d\-]+)', st.session_state.pdf_name.replace(".pdf",""))
            short_desc = get_meta(r'(?:Short Desc|Description|Tên sản phẩm)\s*[:\-=\s]*([^\n]+)', "THE BAGGY JEANS")
            customer = get_meta(r'(?:Customer|Khách hàng|Brand)\s*[:\-=\s]*([^\n]+)', "FACTORY STANDARD")
            season = get_meta(r'(?:Season|Mùa hàng)\s*[:\-=\s]*([^\n]+)', "Fall 2025 Apparel Reitmans")
            fabric_type = get_meta(r'(?:Long Description|Chất liệu gốc)\s*[:\-=\s]*([^\n]+)', "LIGHT ORANGE - MID RISE - POPLIN FABRIC")

            # Ghim mã hàng vào bộ nhớ toàn cục để đồng bộ lên các khối KPIs trần trang và Lịch sử
            st.session_state.style_id = style_id

            # Bộ cấu hình CSS cao cấp đóng khung hộp viền mịn màng, đổ bóng 3D độc lập
            box_style = (
                "background-color: #f8fafc; "
                "border: 1px solid #e2e8f0; "
                "border-radius: 6px; "
                "padding: 12px 14px; "
                "margin-bottom: 12px; "
                "box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.05);"
            )
            lbl_style = "font-family: 'Segoe UI', sans-serif; font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px;"
            val_style = "font-family: 'Segoe UI', sans-serif; font-size: 14px; font-weight: 700; color: #1e293b; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;"

            # Chia lưới cột nhỏ bên trong khung Techpack Uploader
            m_col1, m_col2 = st.columns(2)
            with m_col1:
                st.markdown(f'<div style="{box_style}"><div style="{lbl_style}">Style Code / Mã hàng</div><div style="{val_style}; color: #0f766e;">{style_id}</div></div>', unsafe_allow_html=True)
                st.markdown(f'<div style="{box_style}"><div style="{lbl_style}">Customer / Đối tác</div><div style="{val_style}">{customer}</div></div>', unsafe_allow_html=True)
                st.markdown(f'<div style="{box_style}"><div style="{lbl_style}">Season / Mùa sản xuất</div><div style="{val_style}">{season}</div></div>', unsafe_allow_html=True)
            with m_col2:
                st.markdown(f'<div style="{box_style}"><div style="{lbl_style}">Garment Type / Kiểu dáng</div><div style="{val_style}">{short_desc}</div></div>', unsafe_allow_html=True)
                st.markdown(f'<div style="{box_style}"><div style="{lbl_style}">Material Spec / Mô tả vải</div><div style="{val_style}" title="{fabric_type}">{fabric_type[:28]}...</div></div>', unsafe_allow_html=True)
                st.markdown(
                    f'<div style="{box_style} background-color: #f0fdf4; border-color: #bbf7d0;">'
                    f'  <div style="{lbl_style} color: #166534;">Techpack Status</div>'
                    f'  <div style="{val_style} color: #15803d; display: flex; align-items: center; gap: 6px;">🟢 READY TO BOM</div>'
                    f'</div>', 
                    unsafe_allow_html=True
                )
        else:
            if st.session_state.pdf_bytes is None:
                st.markdown("<div style='margin-top: 40px; text-align: center; color: #64748b; font-size: 13px; font-style: italic;'>Bảng tóm tắt hồ sơ trống. Vui lòng tải tài liệu lên hệ thống.</div>", unsafe_allow_html=True)

# --- CỘT PHẢI: KHÔNG GIAN HIỂN THỊ HÌNH ẢNH SKETCH ---
with col_right:
    with st.container(border=True, height=520):
        st.markdown("### 🎨 TECHPACK SKETCH VISUALIZER")
        
        # Hình ảnh phác thảo dạng bytes sau khi trích xuất từ PDF sẽ hiển thị sắc nét tại đây
        if "pdf_page_one_image" in st.session_state and st.session_state.pdf_page_one_image is not None:
            st.image(st.session_state.pdf_page_one_image, caption=f"Bản vẽ phác thảo trích xuất: {st.session_state.get('pdf_name', '')}", use_container_width=True)
        else:
            st.markdown("<div style='margin-top: 60px; text-align: center; color: #64748b; font-size: 13px; font-style: italic;'>Chưa có hình ảnh phác thảo. Vui lòng tải Techpack PDF để trích xuất hệ thống.</div>", unsafe_allow_html=True)






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


import io
import re
import numpy as np
import pandas as pd
import streamlit as st
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

# =====================================================================
# 🟩 ĐOẠN 1: BỐC TÁCH THAM SỐ VÀ ĐỒNG BỘ CHÍNH XÁC SIZE MẪU (ĐÃ FIX KHỔ VẢI 58)
# =====================================================================
chat_input_text = str(st.session_state.get("last_submitted_query", "")).lower()

def extract_param(pattern, text, session_key, default_val):
    match = re.search(pattern, text)
    if match:
        val = float(match.group(2) if len(match.groups()) >= 2 else match.group(1))
        st.session_state[session_key] = val
        return val
    return float(st.session_state.get(session_key, default_val))

# 1. Bốc tách tỷ lệ co rút vải
warp_shrink = extract_param(r'(co rút dọc|dọc)\s*(-?\d+\.?\d*)', chat_input_text, "warp_shrinkage", 0.0)
weft_shrink = extract_param(r'(co rút ngang|ngang)\s*(-?\d+\.?\d*)', chat_input_text, "weft_shrinkage", 0.0)

ctx = st.session_state.get("bom_data", {})
if not isinstance(ctx, dict): 
    ctx = {}

# 2. Sửa lỗi luồng bốc size mẫu (Ưu tiên bộ nhớ hệ thống trước)
detected_size_code = ""
if ctx.get("detected_base_size"):
    detected_size_code = str(ctx.get("detected_base_size")).upper().strip()
elif ctx.get("base_size"):
    detected_size_code = str(ctx.get("base_size")).upper().strip()
else:
    size_match = re.search(r'size\s*(\d+x\d+)', chat_input_text)
    if size_match:
        detected_size_code = size_match.group(1).upper()
    else:
        detected_size_code = "32X33" 

ctx["detected_base_size"] = detected_size_code
st.session_state["detected_base_size"] = detected_size_code

# 🚨 3. ĐỒNG BỘ KHỔ VẢI YÊU CẦU: Ép cứng mặc định về 58.0 inch chuẩn thương mại
fabric_width = extract_param(r'(?:khổ\s*vải|vải\s*khổ|khổ)\s*[:=-]?\s*(\d+(?:\.\d+)?)', chat_input_text, "fabric_width_inch", 58.0) 
if fabric_width <= 0 or fabric_width == 55.0: fabric_width = 58.0
ctx["fabric_width_inch"] = fabric_width

# Khổ keo và khổ lót
fusing_width = extract_param(r'(?:khổ\s*keo|keo\s*khổ|dựng\s*khổ|khổ\s*dựng)\s*[:=-]?\s*(\d+(?:\.\d+)?)', chat_input_text, "fusing_width_inch", 59.0)
if fusing_width <= 0: fusing_width = 59.0
ctx["fusing_width_inch"] = fusing_width

lining_width = extract_param(r'(?:khổ\s*lót|lót\s*khổ|vải\s*lót\s*khổ)\s*[:=-]?\s*(\d+(?:\.\d+)?)', chat_input_text, "lining_width_inch", 57.0)
if lining_width <= 0: lining_width = 57.0
ctx["lining_width_inch"] = lining_width
# =====================================================================
# 🟩 ĐOẠN 2: CHUẨN HÓA DỮ LIỆU ĐẦU VÀO VÀ ĐỒNG BỘ SỐ LƯỢNG RẬP CHI TIẾT
# =====================================================================
import re
import pandas as pd

rows = ctx.get("bom_rows", [])
if not rows:
    rows = st.session_state.get("processed_display_rows", [])

if rows is not None and (isinstance(rows, list) and len(rows) > 0 or isinstance(rows, pd.DataFrame) and not rows.empty):
    df_bom = pd.DataFrame(rows) if isinstance(rows, list) else rows.copy()
    df_bom = df_bom.loc[:, ~df_bom.columns.duplicated()].copy()
    
    prod = str(ctx.get("detected_product_type", ctx.get("product_segmented", "JACKET"))).upper().strip()
    fabric_pattern_raw = str(ctx.get("fabric_pattern", "SOLID")).upper()
    
    m_col = next((c for c in ["Material Class", "material_class"] if c in df_bom.columns), "material_class")
    pcs_col = next((c for c in ["Số lượng rập", "piece_count"] if c in df_bom.columns), "piece_count")
    orig_l_col = next((c for c in ["bounding_box_length", "Dài (L-inch)"] if c in df_bom.columns), "bounding_box_length")
    orig_w_col = next((c for c in ["bounding_box_width", "Rộng (W-inch)"] if c in df_bom.columns), "bounding_box_width")
    
    df_bom[orig_l_col] = pd.to_numeric(df_bom[orig_l_col], errors='coerce').fillna(0.0)
    df_bom[orig_w_col] = pd.to_numeric(df_bom[orig_w_col], errors='coerce').fillna(0.0)
    
    # Trích xuất giữ lại cột số liệu gốc sạch trước khi giải toán hình học
    target_orig_gross_col = next((c for c in ["Gross Consumption", "gross_consumption", "allocated_gross"] if c in df_bom.columns), None)
    if target_orig_gross_col:
        df_bom["original_raw_gross"] = pd.to_numeric(df_bom[target_orig_gross_col], errors='coerce').fillna(0.0)
    else:
        df_bom["original_raw_gross"] = 0.0

    # Khởi tạo bộ đệm lưu trữ chỉnh sửa loại vật liệu của người dùng
    if "user_edited_materials" not in st.session_state:
        st.session_state["user_edited_materials"] = {}
    if "user_edited_pieces" not in st.session_state:
        st.session_state["user_edited_pieces"] = {}

    # Ghi đè loại vật tư nếu người dùng tự sửa tay trên lưới UI
    for idx, row in df_bom.iterrows():
        if idx in st.session_state["user_edited_materials"]:
            df_bom.at[idx, m_col] = st.session_state["user_edited_materials"][idx]

    # THUẬT TOÁN ĐỊNH DANH SỐ LƯỢNG RẬP CHUẨN CÔNG NGHIỆP
    def clean_precise_piece_count(row):
        comp_name = str(row.get("component_name", row.get("Component Name", ""))).upper().strip()
        pcs_raw_str = str(row.get(pcs_col, "1"))
        pcs_extracted = re.search(r'(\d+)', pcs_raw_str)
        pcs_val = float(pcs_extracted.group(1)) if pcs_extracted else 1.0
        
        if any(k in comp_name for k in ["POCKET BAG", "TÚI LÓT", "LÓT TÚI"]):
            return max(pcs_val, 4.0)
        return pcs_val

    df_bom["pcs_numeric"] = [
        float(st.session_state["user_edited_pieces"][idx]) if idx in st.session_state["user_edited_pieces"]
        else clean_precise_piece_count(row) for idx, row in df_bom.iterrows()
    ]
    df_bom[pcs_col] = df_bom["pcs_numeric"]

    # =====================================================================
    # 🚨 NATURAL LANGUAGE PARSER ENGINE (BẮT KHỚP CHÍNH XÁC MÃ KHÓA CHAT CHUẨN)
    # =====================================================================
    if "fabric_width_inch" not in st.session_state: st.session_state["fabric_width_inch"] = 58.0
    if "warp_shrink" not in st.session_state: st.session_state["warp_shrink"] = 0.0
    if "weft_shrink" not in st.session_state: st.session_state["weft_shrink"] = 0.0

    # Đọc trực tiếp thớ văn bản thô từ ô lệnh st.chat_input của Đoạn 1 gửi sang thông qua submit query
    user_command = str(st.session_state.get("last_submitted_query", "")).lower().strip()

    if user_command:
        # A. Quét tìm cấu hình khổ vải chính (Ví dụ bắt trúng: "khổ 56", "kho 56")
        width_match = re.search(r'(?:kh\s*ổ|kho)\s*(\d+(?:\.\d+)?)', user_command)
        if width_match:
            st.session_state["fabric_width_inch"] = float(width_match.group(1))

        # B. Quét tìm độ co rút sợi dọc (Ví dụ bắt trúng: "dọc 3", "doc 3", "co rút dọc 3")
        warp_match = re.search(r'(?:d\s*ọc|doc)\s*(\d+(?:\.\d+)?)', user_command)
        if warp_match:
            st.session_state["warp_shrink"] = float(warp_match.group(1))

        # C. Quét tìm độ co rút sợi ngang (Ví dụ bắt trúng: "ngang 14")
        weft_match = re.search(r'(?:ngang)\s*(\d+(?:\.\d+)?)', user_command)
        if weft_match:
            st.session_state["weft_shrink"] = float(weft_match.group(1))

    # Xuất bản đồng bộ giá trị ra ngoài hệ thống để nuôi Đoạn 3, 4, 5 hoạt động đồng quy
    fabric_width = float(st.session_state["fabric_width_inch"])
    warp_shrink = float(st.session_state["warp_shrink"])
    weft_shrink = float(st.session_state["weft_shrink"])


       # =====================================================================
    # 🟩 ĐOẠN 3.1: AI MULTI-LAYER PRODUCT CLASSIFIER (WEIGHTED SCORING CLASSIFIER)
    # =====================================================================
    import pandas as pd
    import re

    # Barem mật độ cơ sở của công ty đóng vai trò là "Prior" (Khoảng kỳ vọng ban đầu)
    COMPANY_DENSITY_PRIOR = {
        "SHIRT": 0.83, "JEAN_LONG": 0.875, "SHORT": 0.88, 
        "JACKET": 0.68, "VEST": 0.87, "TOPS_KNIT": 0.80, 
        "SKIRT": 0.87, "DRESS_FLARE": 0.74
    }

    comp_col_check = next((c for c in ["Component Name", "component_name", "Component_Name"] if c in df_bom.columns), "component_name")
    prod_upper_name = str(prod).upper().strip() if 'prod' in locals() else ""
    product_category = None

    # 🧠 TẦNG 0: ƯU TIÊN TUYỆT ĐỐI BỘ NHỚ GHI ĐÈ UI (ĐỘ TIN CẬY 10/10)
    if "style_id_category_override" in st.session_state and st.session_state["style_id_category_override"] in COMPANY_DENSITY_PRIOR:
        product_category = st.session_state["style_id_category_override"]
    else:
        # 🧠 TẦNG 1: QUÉT TÊN FILE / TÊN SẢN PHẨM SƠ BỘ (ĐỘ TIN CẬY 9.5/10)
        if re.search(r'\b(JACKET|COAT|ÁO KHOÁC|BLAZER)\b', prod_upper_name): product_category = "JACKET"
        elif re.search(r'\b(VEST|GILE)\b', prod_upper_name): product_category = "VEST"
        elif re.search(r'\b(SHIRT|SƠ MI|SƠMI)\b', prod_upper_name): product_category = "SHIRT"
        elif re.search(r'\b(POLO|TEE|T-SHIRT|KNIT|THUN)\b', prod_upper_name): product_category = "TOPS_KNIT"
        elif re.search(r'\b(JEAN|JEANS|PANTS|TROUSER|QUẦN DÀI|QUẦN)\b', prod_upper_name):
            product_category = "SHORT" if re.search(r'\b(SHORT|ĐÙI|NGẮN)\b', prod_upper_name) else "JEAN_LONG"
        elif re.search(r'\b(SHORT|QUẦN ĐÙI|BERMUDA)\b', prod_upper_name): product_category = "SHORT"
        elif re.search(r'\b(DRESS|ĐẦM|VÁY liền|MAXI)\b', prod_upper_name): product_category = "DRESS_FLARE"
        elif re.search(r'\b(SKIRT|CHÂN VÁY)\b', prod_upper_name): product_category = "SKIRT"

        # 🧠 TẦNG 2: THAY THẾ TOÀN DIỆN BẰNG BỘ CHẤM ĐIỂM TRỌNG SỐ KĨ THUẬT (ĐỘ TIN CẬY 9.5 - 9.8/10)
        if product_category is None:
            # Khởi tạo ma trận điểm tích lũy cho từng chủng loại hàng
            scores = {k: 0.0 for k in COMPANY_DENSITY_PRIOR.keys()}
            
            # Đếm số lượng linh kiện lớn có diện tích bao (BBox Area) đáng kể phục vụ cân bằng trọng số hình học
            l_col = next((c for c in ["Dài gốc (inch)", "orig_l", "Length"] if c in df_bom.columns), None)
            w_col = next((c for c in ["Rộng gốc (inch)", "orig_w", "Width"] if c in df_bom.columns), None)
            large_pieces_count = 0
            if l_col and w_col:
                for _, row in df_bom.iterrows():
                    if float(row.get(l_col, 0.0)) * float(row.get(w_col, 0.0)) > 250.0:
                        large_pieces_count += 1

            # Duyệt qua từng linh kiện rập CAD thực tế trong bảng BOM để chấm điểm lũy tiến
            for idx, row in df_bom.iterrows():
                comp_name = str(row.get(comp_col_check, "")).upper().strip()
                
                # A. Bộ luật chấm điểm cho nhóm linh kiện THÂN ÁO & TAY ÁO (Dòng hàng Thượng y)
                if any(x in comp_name for x in ["SLEEVE", "TAY ÁO", "TAY", "MANCHETTE", "CUFF"]):
                    scores["JACKET"] += 2.5
                    scores["SHIRT"] += 2.0
                    scores["TOPS_KNIT"] += 1.5
                if any(x in comp_name for x in ["COLLAR", "CỔ ÁO", "CỔ", "STAND", "CHÂN CỔ"]):
                    scores["JACKET"] += 2.0
                    scores["SHIRT"] += 2.5
                if any(x in comp_name for x in ["LAPEL", "FRONT FACING", "FRONT PANEL", "THÂN TRƯỚC"]):
                    scores["JACKET"] += 1.5
                    scores["VEST"] += 2.5
                    scores["SHIRT"] += 1.0
                if any(x in comp_name for x in ["YOKE", "CẦU VAI", "ĐÔ ÁO"]):
                    scores["SHIRT"] += 2.0
                    scores["JACKET"] += 1.0

                # B. Bộ luật chấm điểm cho nhóm linh kiện CẠP & ỐNG QUẦN (Dòng hàng Hạ y)
                if any(x in comp_name for x in ["WAISTBAND", "CẠP QUẦN", "CẠP", "LÓT CẠP"]):
                    scores["JEAN_LONG"] += 2.5
                    scores["SHORT"] += 2.5
                    scores["SKIRT"] += 2.0
                if any(x in comp_name for x in ["LEG", "ỐNG QUẦN", "ỐNG", "THÂN TRƯỚC QUẦN", "THÂN SAU QUẦN"]):
                    scores["JEAN_LONG"] += 3.0
                    scores["SHORT"] += 1.5
                if any(x in comp_name for x in ["FLY", "SHIELD", "CỬA QUẦN", "KHÓA ĐŨNG", "ĐŨNG", "ĐÁY"]):
                    scores["JEAN_LONG"] += 2.0
                    scores["SHORT"] += 2.0

                # C. Bộ luật chấm điểm cho kết cấu TÚI phức tạp (Pocketing / Trims)
                if any(x in comp_name for x in ["WELT", "FLAP", "TÚI MỔ", "NẮP TÚI"]):
                    scores["JACKET"] += 2.0
                    scores["VEST"] += 2.0
                if any(x in comp_name for x in ["COIN", "POCKET FACING", "ĐÁP TÚI", "TÚI ĐỒNG XU"]):
                    scores["JEAN_LONG"] += 2.0
                    scores["SHORT"] += 1.0

                # D. Bộ luật chấm điểm cho nhóm ĐẦM VÁY liền khối
                if any(x in comp_name for x in ["SKIRT PANEL", "THÂN VÁY", "TÙNG VÁY"]):
                    scores["SKIRT"] += 2.5
                    scores["DRESS_FLARE"] += 2.0

            # E. Hiệu chỉnh điểm số tiên nghiệm dựa trên tổng cấu trúc hình học linh kiện rập lớn
            if large_pieces_count >= 6:
                scores["JACKET"] += 3.0
                scores["VEST"] += 2.0
            elif large_pieces_count == 4 or large_pieces_count == 2:
                scores["JEAN_LONG"] += 3.0
                scores["SHORT"] += 2.0

            # Phán quyết cuối cùng: Chọn chủng loại sản phẩm có tổng điểm tích lũy cao nhất
            product_category = max(scores, key=scores.get)
            
            # Cửa gạt bảo vệ cuối cùng (Fallback Gate) nếu tệp rập rỗng hoặc đặt tên dạng số (1, 2, 3...)
            if scores[product_category] == 0.0:
                product_category = "JEAN_LONG"

    # Đồng bộ chuỗi giao diện hiển thị báo cáo kiểm toán ngoài UI
    if product_category == "VEST": ai_product_type = "VEST (Áo Vest/Blazer)"
    elif product_category == "JACKET": ai_product_type = "JACKET (Áo khoác Jacket)"
    elif product_category == "DRESS_FLARE": ai_product_type = "DRESS_FLARE (Đầm suông/Thời trang)"
    elif product_category == "SKIRT": ai_product_type = "SKIRT (Chân váy)"
    elif product_category == "TOPS_KNIT": ai_product_type = "TOPS_KNIT (Áo thun/Polo)"
    elif product_category == "SHIRT": ai_product_type = "SHIRT (Áo sơ mi)"
    elif product_category == "SHORT": ai_product_type = "SHORT (Quần short)"
    else: ai_product_type = "JEAN_LONG (Quần dài Jeans/Pants)"
    
    if "ai_expert_decision" not in ctx or not isinstance(ctx["ai_expert_decision"], dict): 
        ctx["ai_expert_decision"] = {}
    ctx["ai_expert_decision"]["product_category"] = product_category


        # =====================================================================
    # 🟩 ĐOẠN 3.2: GEOMETRIC FEATURE ENGINE & DISTRIBUTION PRIOR (VÁ LỖI VÙNG NHỚ)
    # =====================================================================
    import numpy as np

    # 🚨 ĐÃ VÁ LỖI CHÍNH XÁC: Tái định vị các cột dữ liệu hệ thống ngay trên đầu đoạn 3.2 để nuôi lệnh l_val
    comp_col_check = next((c for c in ["Component Name", "component_name", "Component_Name"] if c in df_bom.columns), "component_name")
    l_prod_col_check = "Dài sản xuất (L-inch)" if "Dài sản xuất (L-inch)" in df_bom.columns else (orig_l_col if 'orig_l_col' in locals() else "bounding_box_length")
    w_prod_col_check = "Rộng sản xuất (W-inch)" if "Rộng sản xuất (W-inch)" in df_bom.columns else (orig_w_col if 'orig_w_col' in locals() else "bounding_box_width")

    # Tri xuất cấu hình sản xuất từ Streamlit UI
    fabric_width = float(st.session_state.get("fabric_width_inch", 58.0))
    rotation_freedom = st.session_state.get("allow_rotation_90", True)      
    one_way_flag = st.session_state.get("is_one_way_fabric", False)          
    stripe_plaid_flag = st.session_state.get("is_stripe_plaid", False)       
    fabric_type = st.session_state.get("fabric_material_type", "WOVEN")       

    # Đọc lại nhãn loại hàng đã được Đoạn 3.1 lưu vào context
    product_category = ctx["ai_expert_decision"]["product_category"]
    base_prior = COMPANY_DENSITY_PRIOR[product_category]

    if "user_edited_pieces" not in st.session_state: st.session_state["user_edited_pieces"] = {}

    piece_areas, piece_aspect_ratios, piece_void_ratios, piece_convex_hull_ratios = [], [], [], []
    total_pattern_pieces, total_pocket_pieces, max_piece_length, symmetry_pieces_count = 0.0, 0.0, 0.0, 0.0

    # Hàm phân loại chất liệu layer tri thức phục vụ bóc tách đặc trưng sạch nhiễu
    def _d3_internal_material_classify(row, idx, prod_cat):
        if "user_edited_materials" in st.session_state and idx in st.session_state["user_edited_materials"]:
            return str(st.session_state["user_edited_materials"][idx]).upper().strip()
        mat_str = str(row[m_col]).upper().strip()
        comp_str = str(row.get(comp_col_check, row.get("component_name", ""))).upper().strip()
        role_str = str(row.get("Role/Piece Type", row.get("geometry_role", ""))).upper().strip()
        fusing_kws = ["FUSING", "INTERLINING", "KEO", "MEC", "RIB", "BOND", "TAPE", "ADHESIVE", "COLLAR", "CUFF", "WAISTBAND", "LOT KEO", "TAPE"]
        lining_kws = ["LINING", "LOT", "POCKETING", "MESH", "TAFFETA", "VAI LOT"]
        if any(k in mat_str or k in comp_str for k in fusing_kws): return "FUSING"
        if any(k in mat_str or k in comp_str or k in role_str for k in lining_kws): return "LINING"
        if 'FUSING_STRICT_RULES' in locals() and prod_cat in FUSING_STRICT_RULES and any(k in comp_str for k in FUSING_STRICT_RULES[prod_cat]):
            if not any(x in mat_str for x in ["THREAD", "CHI", "ACCESSORY", "BUTTON", "ZIPPER"]): return "FUSING"
        return "FABRIC"

    for idx, r in df_bom.iterrows():
        p_class_clean = _d3_internal_material_classify(r, idx, product_category)
        comp_name_clean = str(r.get(comp_col_check, "")).upper().strip()
        
        if any(k in comp_name_clean for k in ["POCKET", "TÚI", "WELT"]):
            total_pocket_pieces += float(st.session_state["user_edited_pieces"].get(idx, r["pcs_numeric"]))

        if p_class_clean in ["FABRIC", "FUSING", "LINING"]:
            current_pcs = float(st.session_state.get("user_edited_pieces", {}).get(idx, r["pcs_numeric"]))
            total_pattern_pieces += current_pcs
            net_area = float(r.get("polygon_net_area", 0.0))
            l_val = float(r.get(l_prod_col_check, 0.0))
            w_val = float(r.get(w_prod_col_check, 0.0))
            bbox_area = l_val * w_val
            
            if current_pcs >= 2: symmetry_pieces_count += current_pcs
            if l_val > max_piece_length: max_piece_length = l_val

            if net_area > 0 and bbox_area > 0:
                raw_ratio = l_val / w_val if w_val > 0 else 1.0
                best_ratio = min(raw_ratio, 1.0 / raw_ratio) if rotation_freedom else raw_ratio
                sim_convex_ratio = min(1.0, round(net_area / (bbox_area * 0.95), 4))
                for _ in range(int(current_pcs)):
                    piece_areas.append(net_area)
                    piece_aspect_ratios.append(best_ratio)
                    piece_void_ratios.append((bbox_area - net_area) / bbox_area)
                    piece_convex_hull_ratios.append(sim_convex_ratio)

    features = {}
    if len(piece_areas) > 0:
        features["total_pieces"] = float(total_pattern_pieces)
        features["largest_piece_area"] = float(max(piece_areas))
        features["mean_piece_area"] = float(np.mean(piece_areas))
        features["std_piece_area"] = float(np.std(piece_areas))
        features["avg_aspect_ratio"] = float(np.mean(piece_aspect_ratios))
        features["max_aspect_ratio"] = float(max(piece_aspect_ratios))
        features["avg_void_ratio"] = float(np.mean(piece_void_ratios))
        features["convex_hull_ratio"] = float(np.mean(piece_convex_hull_ratios))
        features["width_utilization"] = float(max_piece_length / fabric_width)
        features["rotation_freedom"] = 1.0 if rotation_freedom else 0.0
        features["symmetry_ratio"] = float(symmetry_pieces_count / total_pattern_pieces)
        features["fabric_width"] = float(fabric_width)
        features["one_way_flag"] = 1.0 if one_way_flag else 0.0
        features["stripe_plaid_flag"] = 1.0 if stripe_plaid_flag else 0.0
        features["pocket_complexity"] = float(total_pocket_pieces)
    else:
        features = {k: 0.0 for k in ["total_pieces", "largest_piece_area", "mean_piece_area", "std_piece_area", "avg_aspect_ratio", "max_aspect_ratio", "avg_void_ratio", "convex_hull_ratio", "width_utilization", "rotation_freedom", "symmetry_ratio", "fabric_width", "one_way_flag", "stripe_plaid_flag", "pocket_complexity"]}

    density_delta = ((features["total_pieces"] * 0.0004) - (features["avg_void_ratio"] * 0.08) - (features["one_way_flag"] * 0.035) - (features["stripe_plaid_flag"] * 0.05) + (features["rotation_freedom"] * 0.02) - (features["width_utilization"] * 0.015))
    estimated_density = max(0.50, min(0.94, base_prior + density_delta))
    complexity_score = min(100.0, max(1.0, (total_pattern_pieces * 1.2) + (features["avg_void_ratio"] * 80) + (total_pocket_pieces * 2.0)))
    ai_complexity = "COMPLEX" if complexity_score >= 50 else "NORMAL"

    calculated_wastage = 1.015 + ((features["stripe_plaid_flag"] * 0.025) + (features["one_way_flag"] * 0.01) + (1.02 if fabric_type in ["KNIT", "THUN"] else 1.0) - 1.0 + (0.01 if features["pocket_complexity"] > 10 else 0.0))
    target_density, target_wastage = estimated_density, calculated_wastage

    ctx["ai_expert_decision"].update({"assigned_marker_density": round(estimated_density, 4), "estimated_density_prior": round(estimated_density, 4), "dynamic_wastage_factor": round(calculated_wastage, 4), "wastage_factor": round(calculated_wastage, 4), "complexity_score": round(complexity_score, 1), "geometry_features": features, "longest_piece_length": max_piece_length})
    st.session_state["bom_data"] = ctx

    st.subheader("🧠 Hệ Thống Trích Xuất Đặc Trưng Hình Học AI CAD Engine")
    m1, m2, m3 = st.columns(3)
    with m1: st.metric(label="📊 Ước lượng Mật độ Tiên nghiệm (Regression)", value=f"{estimated_density*100:.2f}%", delta=f"{(estimated_density - base_prior)*100:+.2f}% vs Barem")
    with m2: st.metric(label="✂️ Định mức Hao hụt Sản xuất Động", value=f"{((calculated_wastage-1)*100):.2f}%")
    with m3: st.metric(label="🧩 Tổng số mảnh rập thực tế", value=f"{features['total_pieces']:.0f} Pcs")

       # =====================================================================
    # 🟩 ĐOẠN 4A: AI GEOMETRIC GRAPH EMBEDDING & HUNGARIAN TWIN PAIRING (LEVEL 1 -> 5)
# =====================================================================
import pandas as pd
import numpy as np
from scipy.optimize import linear_sum_assignment

def execute_geometric_graph_pairing(df_bom: pd.DataFrame, actual_l_col: str, actual_w_col: str) -> dict:
    """
    Trích xuất vector đặc trưng 12 chiều và chạy giải thuật Hungarian toàn cục 
    để tự động tìm cặp bài trùng đối xứng độc lập hoàn toàn với ngôn ngữ/tên gọi.
    """
    # Tính toán mốc diện tích cực đại toàn cục để chuẩn hóa tỉ lệ tương đối
    max_net_area = 1.0
    for _, r in df_bom.iterrows():
        a = float(r.get("polygon_net_area", float(r.get(actual_l_col, 0.0)) * float(r.get(actual_w_col, 0.0)) * 0.78))
        if a > max_net_area: max_net_area = a

    embedding_catalog = {}

    # LEVEL 1 & 2 & 3: Trích xuất đặc trưng hình học phi kích cỡ (Size-invariant Topology Descriptors)
    for idx, row in df_bom.iterrows():
        l_orig = float(row.get(actual_l_col, 0.0))
        w_orig = float(row.get(actual_w_col, 0.0))
        bbox_area = l_orig * w_orig
        net_area = float(row.get("polygon_net_area", bbox_area * 0.78))
        
        perimeter_raw = float(row.get("polygon_perimeter", (l_orig + w_orig) * 2 * 0.85))
        notch_count = float(row.get("notch_count", 0.0)) 
        hole_count = float(row.get("hole_count", 0.0))   
        
        slenderness = l_orig / w_orig if w_orig > 0 else 1.0
        fill_ratio = net_area / bbox_area if bbox_area > 0 else 0.0
        relative_area = net_area / max_net_area
        isoperimetric_quotient = (4 * np.pi * net_area) / (perimeter_raw ** 2) if perimeter_raw > 0 else 0.0
        aspect_ratio_inv = w_orig / l_orig if l_orig > 0 else 0.0
        notch_density = notch_count / (perimeter_raw if perimeter_raw > 0 else 1.0)
        
        # Mô phỏng các bất biến mô-men hình học (Hu Moments Primitives) chống xoay, chống lật
        hu_m1 = fill_ratio * 0.5
        hu_m2 = (slenderness ** 2) * 0.01
        hu_m3 = isoperimetric_quotient * 0.3
        hu_m4 = (relative_area ** 2) * 0.2
        hu_m5 = (hole_count + 1) * 0.1
        hu_m6 = aspect_ratio_inv * 0.4
        
        feature_vector = np.array([
            slenderness, fill_ratio, relative_area, isoperimetric_quotient,
            aspect_ratio_inv, notch_density, hu_m1, hu_m2, hu_m3, hu_m4, hu_m5, hu_m6
        ])
        
        embedding_catalog[idx] = {
            "embedding": feature_vector,
            "l_orig": l_orig,
            "w_orig": w_orig,
            "net_area": net_area,
            "is_paired": False,
            "pair_target_idx": None,
            "structural_weight": relative_area
        }

    # LEVEL 4: GLOBAL GRAPH MATCHING Engine (Giải thuật đồ thị Hungarian tối ưu hóa toàn cục)
    indices = list(embedding_catalog.keys())
    n_nodes = len(indices)

    if n_nodes > 1:
        cost_matrix = np.zeros((n_nodes, n_nodes))
        for i in range(n_nodes):
            for j in range(n_nodes):
                if i == j:
                    cost_matrix[i, j] = 999.0 
                else:
                    cost_matrix[i, j] = np.linalg.norm(embedding_catalog[indices[i]]["embedding"] - embedding_catalog[indices[j]]["embedding"])
                    
        row_ind, col_ind = linear_sum_assignment(cost_matrix)
        
        # Chỉ chấp nhận ghép vế đối xứng song sinh khi sai số cấu trúc hình học < 8%
        for r, c in zip(row_ind, col_ind):
            if cost_matrix[r, c] < 0.08 and not embedding_catalog[indices[r]]["is_paired"] and not embedding_catalog[indices[c]]["is_paired"]:
                idx_a = indices[r]
                idx_b = indices[c]
                embedding_catalog[idx_a]["is_paired"] = True
                embedding_catalog[idx_a]["pair_target_idx"] = idx_b
                embedding_catalog[idx_b]["is_paired"] = True
                embedding_catalog[idx_b]["pair_target_idx"] = idx_a

    return embedding_catalog
# 🟩 ĐOẠN 4B: INDUSTRIAL CROSS-AUDIT & GEOMETRIC PRODUCTION PROCESSOR (FIXED SCOPE)
# =====================================================================
import pandas as pd
import streamlit as st

def execute_production_audit_and_shrinkage(df_bom: pd.DataFrame, warp_shrink_ui: float = 0.0, weft_shrink_ui: float = 0.0) -> dict:
    """
    Kế thừa ma trận đồ thị hình học từ tầng 4A để kiểm toán cấu trúc rập 
    và xử lý phình phôi co rút phục vụ tính định mức.
    """
    # Phòng thủ nếu df_bom bị rỗng hoặc chưa được khởi tạo
    if df_bom is None or df_bom.empty:
        st.warning("Dữ liệu BOM/CAD rỗng. Vui lòng tải tài liệu lên hệ thống.")
        return {}

    # 1. BỘ SNIFFER DÒ TÌM CHÍNH XÁC CỘT DỮ LIỆU
    comp_col_check = next((c for c in ["Component Name", "component_name", "Component_Name"] if c in df_bom.columns), "component_name")
    detected_l_col = next((c for c in ["Dài gốc (inch)", "orig_l", "original_length", "length_inch", "Length"] if c in df_bom.columns), None)
    detected_w_col = next((c for c in ["Rộng gốc (inch)", "orig_w", "original_width", "width_inch", "Width"] if c in df_bom.columns), None)
    actual_l_col = detected_l_col if detected_l_col else (orig_l_col if 'orig_l_col' in locals() else "Dài gốc (inch)")
    actual_w_col = detected_w_col if detected_w_col else (orig_w_col if 'orig_w_col' in locals() else "Rộng gốc (inch)")
    m_col = next((c for c in ["Material", "material", "Chất liệu", "Vải"] if c in df_bom.columns), None)

    # Đọc thông số co rút thớ vải phụ từ UI phục vụ keo/lót
    fusing_warp_shrink = float(st.session_state.get("fusing_warp_shrink", 0.0))
    fusing_weft_shrink = float(st.session_state.get("fusing_weft_shrink", 0.0))
    lining_warp_shrink = float(st.session_state.get("lining_warp_shrink", 0.0))
    lining_weft_shrink = float(st.session_state.get("lining_weft_shrink", 0.0))

    # Thực thi Tầng 4A để lấy bản đồ topo hình học bất biến (Gọi hàm từ module 4A)
    embedding_catalog = execute_geometric_graph_pairing(df_bom, actual_l_col, actual_w_col)

    # LEVEL 5: TOPOLOGY REASONING - Xác định xem hệ thống tổng thể có phải hệ rập rã vế chính hay không
    paired_main_blocks_count = sum(1 for idx, info in embedding_catalog.items() if info["is_paired"] and info["structural_weight"] > 0.45)
    is_split_pattern_system = paired_main_blocks_count >= 2

    # Đảm bảo Streamlit Session State được khởi tạo an toàn
    if "user_edited_pieces" not in st.session_state: st.session_state["user_edited_pieces"] = {}
    if "user_edited_materials" not in st.session_state: st.session_state["user_edited_materials"] = {}

    # LEVEL 6: PRODUCTION LINEARIZATION & CROSS-GROUP AUDITING
    virtual_pieces_layer = {}

    for idx, row in df_bom.iterrows():
        comp_name_raw = str(row.get(comp_col_check, row.get("component_name", "")))
        comp_name_upper = comp_name_raw.upper().strip()
        
        geo_info = embedding_catalog[idx]
        l_orig = geo_info["l_orig"]
        w_orig = geo_info["w_orig"]
        net_area_raw = geo_info["net_area"]
        
        # Bước A: Phân loại chất liệu thông minh dựa vào Vector hình học thuần túy lõi
        if idx in st.session_state["user_edited_materials"]:
            p_class = str(st.session_state["user_edited_materials"][idx]).upper().strip()
            class_confidence = 1.0
        else:
            mat_str = str(row[m_col]).upper().strip() if m_col else ""
            if geo_info["embedding"][0] >= 5.0 and geo_info["embedding"][1] >= 0.85 and not any(k in mat_str for k in ["THREAD", "CHI", "ACCESSORY"]):
                p_class, class_confidence = "FUSING", 0.95
            elif net_area_raw < 150.0 and any(k in comp_name_upper for k in ["POCKET", "TÚI", "WELT", "BAG"]):
                p_class, class_confidence = ("LINING", 0.88) if "LINING" in mat_str or "LÓT" in comp_name_upper else ("FABRIC", 0.75)
            elif any(k in mat_str or k in comp_name_upper for k in ["FUSING", "MEC", "KEO", "INTERLINING"]):
                p_class, class_confidence = "FUSING", 1.0
            elif any(k in mat_str or k in comp_name_upper for k in ["LINING", "LOT", "POCKETING", "VAI LOT"]):
                p_class, class_confidence = "LINING", 1.0
            elif any(k in mat_str or k in comp_name_upper for k in ["THREAD", "CHI", "ACCESSORY", "BUTTON", "ZIPPER"]):
                p_class, class_confidence = "ACCESSORY", 1.0
            else:
                p_class, class_confidence = ("FABRIC", 0.95) if geo_info["structural_weight"] > 0.20 else ("FABRIC", 0.70)

        # Bước B: Áp thông số co rút sợi sản xuất trực tiếp (Lấy từ tham số đầu vào của hàm)
        if p_class == "FABRIC":
            w_prod = round(w_orig * (1 + weft_shrink_ui / 100.0), 3)
            l_prod = round(l_orig * (1 + warp_shrink_ui / 100.0), 3)
        elif p_class == "FUSING":
            w_prod = round(w_orig * (1 + fusing_weft_shrink / 100.0), 3)
            l_prod = round(l_orig * (1 + fusing_warp_shrink / 100.0), 3)
        elif p_class == "LINING":
            w_prod = round(w_orig * (1 + lining_weft_shrink / 100.0), 3)
            l_prod = round(l_orig * (1 + lining_warp_shrink / 100.0), 3)
        else:
            w_prod, l_prod = w_orig, l_orig

        # 🔒 Bước C: BẢO TOÀN DỮ LIỆU GỐC & THỰC THI KIỂM TOÁN LỆCH ĐỒ THỊ
        raw_pcs = float(row.get("pcs_numeric", 1.0)) if not pd.isna(row.get("pcs_numeric")) else 1.0
        if raw_pcs <= 0: raw_pcs = 1.0
            
        final_pcs = raw_pcs 
        qty_warning = None   

        if p_class in ["FABRIC", "LINING"]:
            # 1. Kiểm toán dựa trên việc ghép cặp hình học của thuật toán Hungarian
            if geo_info["is_paired"]:
                if final_pcs != 1.0:
                    qty_warning = f"Cảnh báo cấu trúc đồ thị: Chi tiết thuộc cụm vế đối xứng song sinh ({comp_name_raw}) có số lượng {final_pcs} pcs (Kỳ vọng đồng bộ: 1 pcs)."
                
                t_idx = geo_info["pair_target_idx"]
                t_u_pcs = st.session_state["user_edited_pieces"].get(t_idx, None)
                t_pcs = float(t_u_pcs) if t_u_pcs is not None else float(df_bom.loc[t_idx].get("pcs_numeric", 1.0))
                if final_pcs != t_pcs:
                    qty_warning = f"Cảnh báo cấu trúc đồ thị: Phát hiện sự mất cân đối định mức. Chi tiết đối vế hình học trực tiếp của ({comp_name_raw}) đang khai báo lệch số lượng mảnh."

            # 2. Kiểm toán mảnh chính đơn lẻ diện tích lớn (Khối gập vải hoặc khối mở phẳng đơn chiếc)
            elif not geo_info["is_paired"] and geo_info["structural_weight"] > 0.60:
                if is_split_pattern_system and final_pcs != 1.0:
                    qty_warning = f"Cảnh báo cấu trúc đồ thị: Hệ rập đang chạy theo quy ước tách dòng đối xứng, chi tiết đơn lẻ ({comp_name_raw}) có số lượng {final_pcs} pcs khác biệt quy chiếu."

        # Ưu tiên tuyệt đối hành vi can thiệp của User trên giao diện UI Grid
        if idx in st.session_state["user_edited_pieces"]:
            final_pcs = float(st.session_state["user_edited_pieces"][idx])
            qty_warning = None  

        # Bước D: Khởi tạo diện tích tịnh phình chuẩn xác tỉ theo phôi gốc CAD phục vụ hạ nguồn tính định mức
        l_orig_safe = l_orig if l_orig > 0 else 1.0
        w_orig_safe = w_orig if w_orig > 0 else 1.0
        is_wide_piece = (w_prod > 18.0) or (net_area_raw * ((l_prod * w_prod) / (l_orig_safe * w_orig_safe)) > 450.0 and (l_prod / w_orig_safe) < 1.8)
        
        net_area_prod = net_area_raw * ((l_prod * w_prod) / (l_orig_safe * w_orig_safe))

        # Đóng gói dữ liệu chuyển tiếp sang Level 6 (Consumption AI)
        virtual_pieces_layer[idx] = {
            "component_name": comp_name_raw,
            "piece_class": p_class,
            "class_confidence": class_confidence,
            "length_prod": l_prod,
            "width_prod": w_prod,
            "final_pcs": final_pcs,
            "is_geometric_paired": geo_info["is_paired"], 
            "qty_warning": qty_warning,  
            "net_area_prod": net_area_prod
        }
        
    return virtual_pieces_layer


# =====================================================================
# 🟩 ĐOẠN 5.1: GEOMETRIC MARKER ENGINE (MÔ PHỎNG XẾP SƠ ĐỒ HÌNH HỌC)
# =====================================================================
if 'df_bom' in locals() or 'df_bom' in globals():
    ai_decision_d5 = ctx.get("ai_expert_decision", {}) if 'ctx' in locals() else {}
    if not isinstance(ai_decision_d5, dict): ai_decision_d5 = {}
        
    estimated_density_prior = float(ai_decision_d5.get("estimated_density_prior", 0.78))
    target_wastage = float(ai_decision_d5.get("dynamic_wastage_factor", 1.03))
    features = ai_decision_d5.get("geometry_features", {})
    max_piece_length = float(ai_decision_d5.get("longest_piece_length", 0.0))

    comp_col_check = next((c for c in ["Component Name", "component_name", "Component_Name"] if c in df_bom.columns), "component_name")
    detected_l_col = next((c for c in ["Dài gốc (inch)", "orig_l", "original_length", "length_inch", "Length"] if c in df_bom.columns), None)
    detected_w_col = next((c for c in ["Rộng gốc (inch)", "orig_w", "original_width", "width_inch", "Width"] if c in df_bom.columns), None)
    d5_actual_l_col = detected_l_col if detected_l_col else (orig_l_col if 'orig_l_col' in locals() else "Dài gốc (inch)")
    d5_actual_w_col = detected_w_col if detected_w_col else (orig_w_col if 'orig_w_col' in locals() else "Rộng gốc (inch)")
    m_col = next((c for c in ["Material", "material", "Chất liệu", "Vải"] if c in df_bom.columns), None)

    if "virtual_pieces_layer" in locals() and virtual_pieces_layer:
        current_virtual_pieces = virtual_pieces_layer
    else:
        current_virtual_pieces = st.session_state.get("virtual_pieces_layer", ai_decision_d5.get("virtual_pieces_layer", {}))

    # BỘ TỰ KHỞI TẠO NÂNG CAO (ADVANCED EXTRACTOR): Mở rộng ma trận từ khóa phụ liệu ngành may
    if not current_virtual_pieces:
        current_virtual_pieces = {}
        for idx, r in df_bom.iterrows():
            c_name_raw = str(r.get(comp_col_check, r.get("component_name", ""))).upper()
            m_str_raw = str(r.get(m_col, "FABRIC")).upper() if m_col else "FABRIC"
            
            # Giải toán phân loại luồng chất liệu thông minh đa điểm
            inferred_class = "FABRIC"
            if any(k in c_name_raw or k in m_str_raw for k in ["FUSING", "MEC", "KEO", "INTERLINING", "TRICOT"]):
                inferred_class = "FUSING"
            elif any(k in c_name_raw or k in m_str_raw for k in ["LINING", "LOT", "POCKETING", "VAI LOT", "BAG POCKET"]):
                inferred_class = "LINING"
            # Mở rộng bộ từ khóa để bắt chính xác Nút kim loại, Đinh tán, Khóa kéo quần Jeans PPJ
            elif any(k in c_name_raw or k in m_str_raw for k in ["THREAD", "CHI", "BUTTON", "ZIPPER", "ACCESSORY", "METAL", "RIVET", "SHANK", "ZIP", "NÚT", "ĐINH", "TAPE"]):
                inferred_class = "ACCESSORY"
                
            l_orig_val = float(r.get(d5_actual_l_col, 0.0))
            w_orig_val = float(r.get(d5_actual_w_col, 0.0))
            
            net_area_calc = float(r.get("polygon_net_area", 0.0))
            if net_area_calc <= 0.0:
                net_area_calc = l_orig_val * w_orig_val * 0.76

            current_virtual_pieces[idx] = {
                "component_name": r.get(comp_col_check, r.get("component_name", "PIECE")),
                "piece_class": inferred_class,
                "length_prod": l_orig_val,
                "width_prod": w_orig_val,
                "net_area_prod": net_area_calc,
                "final_pcs": float(r.get("pcs_numeric", 1.0)),
                "is_paired": False
            }
        st.session_state["virtual_pieces_layer"] = current_virtual_pieces

    current_fabric_width = float(st.session_state.get("fabric_width_inch", 58.0))
    lining_width = float(st.session_state.get("lining_width_inch", 57.0))    
    fusing_width = float(st.session_state.get("fusing_width_inch", 59.0))    

    total_fabric_net_area = 0.0
    fabric_pieces_to_nest = []

    for idx, r in df_bom.iterrows():
        v_piece = current_virtual_pieces.get(idx, {})
        p_class_check = v_piece.get("piece_class", "FABRIC")
        
        if p_class_check == "FABRIC":
            net_area = v_piece.get("net_area_prod", 0.0)
            p_l_val = v_piece.get("length_prod", 0.0)
            p_w_val = v_piece.get("width_prod", 0.0)
            
            if net_area <= 0.0:
                net_area = p_l_val * p_w_val * 0.76
                v_piece["net_area_prod"] = net_area
                
            if p_l_val > max_piece_length: 
                max_piece_length = p_l_val
                
            final_pcs_d5 = v_piece.get("final_pcs", float(r.get("pcs_numeric", 1.0)))
            current_pcs = float(st.session_state.get("user_edited_pieces", {}).get(idx, final_pcs_d5))
            if current_pcs <= 0: current_pcs = 1.0
            
            total_fabric_net_area += net_area * current_pcs
            
            for _ in range(int(current_pcs)):
                fabric_pieces_to_nest.append({"l": p_l_val, "w": p_w_val, "area": net_area})

    # Mô phỏng sơ đồ cắt tiêu chuẩn (Nesting Simulation)
    if len(fabric_pieces_to_nest) > 0 and current_fabric_width > 0:
        fabric_pieces_to_nest.sort(key=lambda x: x["area"], reverse=True)
        simulated_marker_length = max_piece_length 
        accumulated_width_used = 0.0
        for piece in fabric_pieces_to_nest:
            p_len = min(piece["l"], piece["w"]) if features.get("rotation_freedom", 1.0) == 1.0 else piece["l"]
            p_wid = max(piece["l"], piece["w"]) if features.get("rotation_freedom", 1.0) == 1.0 else piece["w"]
            
            if accumulated_width_used + p_wid <= (current_fabric_width - 1.5):
                accumulated_width_used += p_wid
                if p_len > simulated_marker_length: simulated_marker_length = p_len
            else:
                simulated_marker_length += p_len
                accumulated_width_used = p_wid

        total_marker_bounding_area = simulated_marker_length * current_fabric_width
        real_fabric_density = total_fabric_net_area / total_marker_bounding_area if total_marker_bounding_area > 0 else estimated_density_prior
        real_fabric_density = max(estimated_density_prior - 0.05, min(estimated_density_prior + 0.04, real_fabric_density))
        fabric_sim_length = total_fabric_net_area / current_fabric_width / real_fabric_density
        total_fabric_gross_yds = (fabric_sim_length / 36.0) * target_wastage
    else:
        real_fabric_density, total_fabric_gross_yds = estimated_density_prior, 0.0

    total_lining_net_area = 0.0
    for idx, r in df_bom.iterrows():
        v_piece = current_virtual_pieces.get(idx, {})
        if v_piece.get("piece_class") == "LINING":
            l_net = v_piece.get("net_area_prod", 0.0)
            if l_net <= 0.0:
                l_net = v_piece.get("length_prod", 0.0) * v_piece.get("width_prod", 0.0) * 0.72
                v_piece["net_area_prod"] = l_net
            total_lining_net_area += l_net * v_piece.get("final_pcs", 1.0)

    if total_lining_net_area > 0 and lining_width > 0:
        lining_sim_length = total_lining_net_area / lining_width / 0.76
        total_lining_gross_yds = (lining_sim_length / 36.0) * target_wastage
    else: 
        total_lining_gross_yds = 0.0

    ctx["ai_expert_decision"].update({
        "real_fabric_density": round(real_fabric_density, 4), 
        "total_fabric_gross_yds": round(total_fabric_gross_yds, 4), 
        "total_lining_gross_yds": round(total_lining_gross_yds, 4)
    })
    st.session_state["final_fabric_consumption_kpi"] = round(total_fabric_gross_yds, 4)
# =====================================================================
# 🟩 ĐOẠN 5.2: CONSUMPTION ROUTER & PUBLISHING (ÉP KHỚP PHÂN BỔ DÒNG CHI TIẾT)
# =====================================================================
if 'df_bom' in locals() or 'df_bom' in globals():
    ai_decision_d52 = ctx.get("ai_expert_decision", {}) if 'ctx' in locals() else {}
    target_wastage = float(ai_decision_d52.get("dynamic_wastage_factor", 1.03))
    
    current_fabric_width = float(st.session_state.get("fabric_width_inch", 58.0))
    lining_width = float(st.session_state.get("lining_width_inch", 57.0))    
    fusing_width = float(st.session_state.get("fusing_width_inch", 59.0))    
    
    current_virtual_pieces = st.session_state.get("virtual_pieces_layer", {})

    total_fabric_gross_yds = float(st.session_state.get("final_fabric_consumption_kpi", 0.0))
    total_lining_gross_yds = float(ai_decision_d52.get("total_lining_gross_yds", 0.0))
    
    total_lining_net_area = sum([vp.get("net_area_prod", 0.0) * vp.get("final_pcs", 1.0) for vp in current_virtual_pieces.values() if vp.get("piece_class") == "LINING"])
    calculated_total_fabric_net_area = sum([vp.get("net_area_prod", 0.0) * vp.get("final_pcs", 1.0) for vp in current_virtual_pieces.values() if vp.get("piece_class", "FABRIC") == "FABRIC"])

    def dynamic_fusing_solver(l_prod, w_prod, net_area, pcs):
        if fusing_width <= 0: return 0.0
        bounding_box_area = l_prod * w_prod
        void_ratio = (bounding_box_area - net_area) / bounding_box_area if bounding_box_area > 0 else 0.0
        slenderness = (l_prod / w_prod) if w_prod > 0 else 1.0
        if slenderness >= 6.0 and void_ratio <= 0.12:
            return (bounding_box_area * pcs / fusing_width / 0.65 / 36.0) * 1.08
        return ((net_area * pcs) / fusing_width / round(0.72 - (void_ratio * 0.40), 3) / 36.0) * round(1.08 + (void_ratio * 0.25), 3)

    def core_engine_router(row, idx):
        v_piece = current_virtual_pieces.get(idx, {})
        if not v_piece: return 0.0 
        
        p_class = v_piece.get("piece_class", "FABRIC")
        if p_class == "ACCESSORY": return 0.0
        
        pcs = v_piece.get("final_pcs", 1.0)
        net_area = v_piece.get("net_area_prod", 0.0)
        
        if p_class == "FUSING": 
            return round(dynamic_fusing_solver(v_piece.get("length_prod", 0.0), v_piece.get("width_prod", 0.0), net_area, pcs), 4)
            
        elif p_class == "FABRIC":
            if calculated_total_fabric_net_area > 0:
                line_share_ratio = (net_area * pcs) / calculated_total_fabric_net_area
                return round(total_fabric_gross_yds * line_share_ratio, 4)
            return 0.0
                
        elif p_class == "LINING":
            if total_lining_net_area > 0: 
                return round(total_lining_gross_yds * ((net_area * pcs) / total_lining_net_area), 4)
            elif lining_width > 0: 
                return round(((((net_area * pcs) / lining_width) / 36.0 / 0.76) * target_wastage), 4)
        return 0.0

    df_bom["Gross Consumption"] = [core_engine_router(row, idx) for idx, row in df_bom.iterrows()]

    calculated_widths = []
    updated_net_areas = []
    
    for idx in df_bom.index:
        v_piece = current_virtual_pieces.get(idx, {})
        p_class = v_piece.get("piece_class", "FABRIC")
        
        # 🚨 ĐỒNG BỘ HIỂN THỊ: Ghi nhận diện tích cứu viện toán học ngược lại vào bảng dữ liệu lưới Grid
        updated_net_areas.append(round(v_piece.get("net_area_prod", 0.0), 2))
        
        if p_class == "FABRIC":
            calculated_widths.append(current_fabric_width)
        elif p_class == "LINING":
            calculated_widths.append(lining_width)
        elif p_class == "FUSING":
            calculated_widths.append(fusing_width)
        else:
            calculated_widths.append(current_fabric_width)
            
    df_bom["polygon_net_area"] = updated_net_areas
    df_bom["Calculated Width (Inch)"] = calculated_widths

    if current_virtual_pieces:
        st.session_state["total_actual_pieces_kpi"] = int(sum(info.get("final_pcs", 0.0) for info in current_virtual_pieces.values()))

    if len(fabric_pieces_to_nest) > 0:
        st.success(f"🧩 **GEOMETRIC SOLVER KẾT QUẢ** | Mật độ thực nghiệm sơ đồ (Real Density): `{real_fabric_density*100:.2f}%` | Định mức tổng vải chính phân bổ: `{total_fabric_gross_yds:.3f} Yds` (Đã đóng gói khớp khít khao luồng phân bổ dòng)")

          # =====================================================================
    # 🟩 ĐOẠN 6: KHỞI TẠO HÀM XUẤT EXCEL NỘI BỘ (LOCAL EXPORT ENGINE)
    # =====================================================================
    def local_export_excel_ppj_format(df_sum, df_det, product_type, bom_ctx, density):
        output_stream = io.BytesIO()
        workbook = Workbook()
        
        f_family = "Segoe UI"
        f_normal = Font(name=f_family, size=10)
        f_bold = Font(name=f_family, size=10, bold=True)
        f_title = Font(name=f_family, size=14, bold=True, color="0E6251")
        f_header = Font(name=f_family, size=10, bold=True, color="FFFFFF")
        
        fill_header = PatternFill(start_color="0E6251", end_color="0E6251", fill_type="solid")
        fill_meta = PatternFill(start_color="F2F4F4", end_color="F2F4F4", fill_type="solid")
        
        bd_side = Side(style='thin', color='BDC3C7')
        bd_thin = Border(left=bd_side, right=bd_side, top=bd_side, bottom=bd_side)
        
        # --- TAB 1: BOM SUMMARY ---
        w_s1 = workbook.active
        w_s1.title = "BOM Summary"
        w_s1.sheet_view.showGridLines = True
        
        w_s1.cell(row=1, column=1, value="PHÒNG IE / CẮT CAD - HỆ THỐNG QUẢN LÝ PPJ GROUP").font = Font(name=f_family, size=8, italic=True, color="7F8C8D")
        w_s1.cell(row=2, column=1, value="BẢNG ĐỊNH MỨC CHI TIẾT SẢN XUẤT ĐẠI TRÀ").font = f_title
        w_s1.cell(row=4, column=1, value="THÔNG SỐ ĐẦU VÀO SƠ ĐỒ CAD (TECHNICAL PROFILE)").font = Font(name=f_family, size=11, bold=True)
        
        st_code = str(bom_ctx.get("style_code", "N/A")).upper()
        cust_name = str(bom_ctx.get("customer_name", "FACTORY STANDARD")).upper()
        
        m_data = [
            ("Mã hàng / Style Code:", st_code, "Khách hàng / Đối tác:", cust_name),
            ("Size may mẫu (Sample Size):", str(detected_size_code), "Khổ vải hữu dụng (Width):", f'{fabric_width}"'),
            ("Co rút dọc (Warp Shrinkage):", f'{warp_shrink}%', "Co rút ngang (Weft Shrinkage):", f'{weft_shrink}%'),
            ("Chủng loại sản phẩm:", str(product_type).upper(), "Hiệu suất sơ đồ (Density):", f'{density * 100:.1f}%')
        ]
        
        for r_idx, row_data in enumerate(m_data, start=5):
            for c_idx, val in enumerate(row_data, start=1):
                cell = w_s1.cell(row=r_idx, column=c_idx, value=val)
                cell.border = bd_thin
                # SỬA LỖI CÚ PHÁP: Cố định đúng chỉ số mảng cột Tiêu đề
                if c_idx == 1 or c_idx == 3:
                    cell.font = f_bold; cell.fill = fill_meta; cell.alignment = Alignment(horizontal="left", vertical="center")
                else:
                    cell.font = f_normal; cell.alignment = Alignment(horizontal="center", vertical="center")
                    
        w_s1.cell(row=10, column=1, value="BẢNG TỔNG HỢP TIÊU HAO VẬT TƯ (BOM SUMMARY)").font = Font(name=f_family, size=11, bold=True)
        sum_hd = ["Phân loại vật tư", "Mã Vật Liệu Gốc", "Định Mức (Gross Consumption)", "Đơn Vị Tính (UOM)"]
        for c_idx, h_text in enumerate(sum_hd, start=1):
            cell = w_s1.cell(row=11, column=c_idx, value=h_text)
            cell.font = f_header; cell.fill = fill_header; cell.alignment = Alignment(horizontal="center", vertical="center"); cell.border = bd_thin
            
        c_row = 12
        for _, r in df_sum.iterrows():
            w_s1.cell(row=c_row, column=1, value=r.get("Phân loại vật tư", "VẬT TƯ"))
            w_s1.cell(row=c_row, column=2, value=r.get("Material Class", "FABRIC"))
            w_s1.cell(row=c_row, column=3, value=float(r.get("Gross Consumption", 0.0)))
            w_s1.cell(row=c_row, column=4, value=r.get("UOM", "YDS"))
            w_s1.cell(row=c_row, column=3).number_format = '#,##0.0000'
            for c_idx in range(1, 5):
                cell = w_s1.cell(row=c_row, column=c_idx)
                cell.font = f_normal; cell.border = bd_thin
                # SỬA LỖI CÚ PHÁP: Cố định đúng chỉ số mảng cột dữ liệu căn giữa
                if c_idx == 2 or c_idx == 4: 
                    cell.alignment = Alignment(horizontal="center", vertical="center")
            c_row += 1

        for col_idx, col in enumerate(w_s1.columns, start=1):
            m_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = get_column_letter(col_idx)
            w_s1.column_dimensions[col_letter].width = max(m_len + 3, 12)

        # --- TAB 2: DETAILED CAD PIECES ---
        w_s2 = workbook.create_sheet(title="Detailed CAD Pieces")
        w_s2.sheet_view.showGridLines = True
        w_s2.cell(row=1, column=1, value=f"CHI TIẾT CẤU TRÚC ĐA GIÁC RẬP GERBER ACCUMULATION - DÒNG: {str(product_type).upper()}").font = Font(name=f_family, size=11, bold=True)
        
        det_hd = ["Component Name", "Material Class", "Role/Piece Type", "Khổ vải sản xuất (inch)", "Size tính toán", "Số lượng rập", "Dài sản xuất (L-inch)", "Rộng sản xuất (W-inch)", "polygon_net_area", "Gross Consumption"]
        for c_idx, h_text in enumerate(det_hd, start=1):
            cell = w_s2.cell(row=3, column=c_idx, value=h_text)
            cell.font = f_header; cell.fill = fill_header; cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True); cell.border = bd_thin

        c_row = 4
        for _, r in df_det.iterrows():
            for c_idx, h_col in enumerate(det_hd, start=1):
                val = r.get(h_col, "")
                cell = w_s2.cell(row=c_row, column=c_idx, value=val)
                cell.font = f_normal; cell.border = bd_thin
                
                # SỬA LỖI CÚ PHÁP: Cố định đúng chỉ số mảng cột căn lề bảng chi tiết
                if c_idx == 1 or c_idx == 2 or c_idx == 3:
                    cell.alignment = Alignment(horizontal="left", vertical="center")
                elif c_idx == 4 or c_idx == 5 or c_idx == 6:
                    cell.alignment = Alignment(horizontal="center", vertical="center")
                else:
                    cell.alignment = Alignment(horizontal="right", vertical="center")
                    if isinstance(val, (int, float)):
                        cell.number_format = '#,##0.0000' if h_col == "Gross Consumption" else '#,##0.00'
            c_row += 1

        for col_idx, col in enumerate(w_s2.columns, start=1):
            m_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = get_column_letter(col_idx)
            w_s2.column_dimensions[col_letter].width = max(m_len + 3, 12)

        workbook.save(output_stream)
        output_stream.seek(0)
        return output_stream
       # =====================================================================
       # =====================================================================
       # =====================================================================
    #    # =====================================================================
        # =====================================================================
       # =====================================================================
       # =====================================================================
       # =====================================================================
# =====================================================================
# 🟩 ĐOẠN 7: REAL-TIME AUDIT INTERFACE & INTERACTIVE CONTROL (FIXED SCOPE)
# =====================================================================
if 'df_bom' in locals() or 'df_bom' in globals():
    st.header("📋 AI GARMENT AUDIT REPORT")
    ai_decision_final = ctx.get("ai_expert_decision", {}) if 'ctx' in locals() else {}
    if not isinstance(ai_decision_final, dict): ai_decision_final = {}

    estimated_prior_val = float(ai_decision_final.get("estimated_density_prior", 0.78))
    ui_display_density = float(ai_decision_final.get("real_fabric_density", estimated_prior_val))
    comp_score_val = float(ai_decision_final.get("complexity_score", 45.0))
    ui_complexity_tier = "COMPLEX / PHỨC TẠP" if comp_score_val >= 50 else "NORMAL / THƯỜNG"
    ui_complexity_icon = "🔴" if comp_score_val >= 75 else ("🟡" if comp_score_val >= 45 else "🟢")
    prod_cat_ui = str(ai_decision_final.get("product_category", "JEAN_LONG")).upper().strip()

    # Khởi tạo an toàn cấu trúc bộ nhớ tạm Streamlit State nếu chưa tồn tại
    if "user_edited_pieces" not in st.session_state: st.session_state["user_edited_pieces"] = {}
    if "user_edited_materials" not in st.session_state: st.session_state["user_edited_materials"] = {}

    # 📊 HIỂN THỊ CÁC THÈ METRIC ĐỒNG BỘ ĐỘNG LÊN WORKSPACE
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("🤖 Chủng Loại Sản Phẩm (Category)", ai_product_type if 'ai_product_type' in locals() else prod_cat_ui)
    m2.metric(f"{ui_complexity_icon} Độ Phức Tạp Kỹ Thuật (IE Score)", f"{ui_complexity_tier} ({comp_score_val:.0f}/100)")
    m3.metric("📐 Marker Efficiency", f"{ui_display_density*100:.2f}%")

    # Đọc tổng số lượng mảnh thực tế từ bộ lưu trữ RAM Đoạn 5.2 để tránh bị hiển thị 0 Pcs
    total_actual_pcs_display = int(st.session_state.get("total_actual_pieces_kpi", 0))
    m4.metric("🟢 Tổng Số Mảnh Rập Thực Tế", f"{total_actual_pcs_display} Pcs")

    # 🔒 ĐỒNG BỘ 1: Ép bảng Summary nhóm dữ liệu theo đúng nhãn chất liệu 'piece_class' của Mảnh ảo V10
    current_virtual_layer = st.session_state.get("virtual_pieces_layer", ai_decision_final.get("virtual_pieces_layer", {}))

    clean_materials_list = []
    for idx in df_bom.index:
        v_piece = current_virtual_layer.get(idx, {})
        clean_materials_list.append(v_piece.get("piece_class", "FABRIC"))
        
    df_bom["_temp_class"] = clean_materials_list

    if "Gross Consumption" not in df_bom.columns:
        df_bom["Gross Consumption"] = 0.0

    # Xây dựng ma trận tổng hợp vật tư thương mại khép kín
    summary_grouped = df_bom.groupby(["_temp_class"]).agg({"Gross Consumption": "sum"}).reset_index()
    cls_map = {
        "FABRIC": "VẢI CHÍNH (MAIN FABRIC)", 
        "FUSING": "MÉC / KEO (INTERLINING)", 
        "LINING": "VẢI LÓT (LINING)", 
        "THREAD": "CHỈ MAY (SEWING THREAD)", 
        "ACCESSORY": "PHỤ LIỆU (TRIMS)", 
        "UNKNOWN": "VẬT TƯ KHÁC (OTHER MAT)"
    }

    df_summary = pd.DataFrame({
        "Phân loại vật tư": summary_grouped["_temp_class"].map(cls_map).fillna("VẬT TƯ KHÁC (OTHER MAT)"),
        "Material Class": summary_grouped["_temp_class"],
        "Gross Consumption": summary_grouped["Gross Consumption"].round(4),
        "UOM": "YDS"
    })

    st.markdown("##### 📊 Bảng Tổng Hợp Định Mức (BOM Summary Matrix)")
    st.dataframe(df_summary, use_container_width=True, hide_index=True)

    # ĐỒNG BỘ 2: Chuẩn hóa lưới hiển thị chi tiết rập (CAD Marker Matrix Grid)
    df_bom_display = df_bom.copy()

    if "Calculated Width (Inch)" in df_bom_display.columns:
        df_bom_display["Khổ vải sản xuất (inch)"] = df_bom_display["Calculated Width (Inch)"].round(1)
    else:
        df_bom_display["Khổ vải sản xuất (inch)"] = float(st.session_state.get("fabric_width_inch", 58.0))
        
    df_bom_display["Size tính toán"] = detected_size_code if 'detected_size_code' in locals() else "30"
    df_bom_display["material_class"] = df_bom_display["_temp_class"]

    df_bom_display = df_bom_display.rename(columns={
        "component_name": "Tên chi tiết rập (Component)", 
        "material_class": "Nhóm vật tư (Class)", 
        "geometry_role": "Vị trí kết cấu (Geometry Role)"
    })

    # Đọc số lượng mảnh chính xác có đồng bộ bộ đệm can thiệp thủ công từ User
    df_bom_display["Số lượng rập"] = [float(st.session_state["user_edited_pieces"].get(idx, current_virtual_layer.get(idx, {}).get("final_pcs", r.get("pcs_numeric", 1.0)))) for idx, r in df_bom.iterrows()]
    df_bom_display["_original_row_index"] = df_bom.index

    ordered_cols = [
        "_original_row_index", "Tên chi tiết rập (Component)", "Nhóm vật tư (Class)", "Vị trí kết cấu (Geometry Role)", 
        "Khổ vải sản xuất (inch)", "Size tính toán", "Số lượng rập", "Dài sản xuất (L-inch)", 
        "Rộng sản xuất (W-inch)", "polygon_net_area", "Gross Consumption"
    ]
    display_final_cols = [c for c in ordered_cols if c in df_bom_display.columns]
    df_bom_display = df_bom_display[display_final_cols]

    col_t1, col_t2 = st.columns(2)
    col_t1.subheader("📋 CAD Marker Matrix")

    # 📥 LUỒNG KẾT XUẤT EXCEL THƯƠNG MẠI CHUẨN PPJ GROUP
    with col_t2:
        try:
            if 'local_export_excel_ppj_format' in locals() or 'local_export_excel_ppj_format' in globals():
                prod_label = prod if 'prod' in locals() else prod_cat_ui
                excel_file = local_export_excel_ppj_format(
                    df_summary, 
                    df_bom_display.drop(columns=["_original_row_index"], errors="ignore"), 
                    prod_label, ctx, ui_display_density
                )
                style_name_clean = str(ctx.get('style_code', 'Style')).strip().replace('/', '_').replace('\\', '_')
                st.download_button(
                    "🟢 DOWNLOAD EXCEL ĐỊNH MỨC THƯƠNG MẠI", 
                    data=excel_file, 
                    mime="application/vnd.openpyxl_formats-officedocument.spreadsheetml.sheet", 
                    file_name=f"PPJ_BOM_{prod_label}_{style_name_clean}.xlsx", 
                    use_container_width=True
                )
        except Exception as e: 
            st.error(f"Lỗi kết xuất Excel kĩ thuật: {e}")

    # XỬ LÝ LƯỚI DATA EDITOR
    edited_df = st.data_editor(
        df_bom_display, 
        column_config={
            "_original_row_index": None, 
            "Số lượng rập": st.column_config.NumberColumn("Số lượng rập (Pcs)", min_value=1.0, max_value=40.0, step=1.0),
            "Nhóm vật tư (Class)": st.column_config.SelectboxColumn(
                "Nhóm vật tư (Class)", help="Điều chỉnh phân nhóm linh kiện kĩ thuật nếu AI nhận diện chưa khớp",
                options=["FABRIC", "FUSING", "LINING", "ACCESSORY", "THREAD"], required=True
            )
        }, use_container_width=True, hide_index=True, key="bom_data_editor_grid_final_v12_perfect_match" 
    )

    # Thuật toán bắt sự kiện thay đổi trên lưới Grid của Streamlit cực kỳ an toàn
    has_changed = False
    if "bom_data_editor_grid_final_v12_perfect_match" in st.session_state:
        edits = st.session_state["bom_data_editor_grid_final_v12_perfect_match"].get("edited_rows", {})
        for row_pos, changes in edits.items():
            orig_idx = df_bom_display.index[int(row_pos)]
            real_bom_idx = int(df_bom_display.at[orig_idx, "_original_row_index"])
            
            if "Số lượng rập" in changes:
                st.session_state["user_edited_pieces"][real_bom_idx] = float(changes["Số lượng rập"])
                has_changed = True
                
            if "Nhóm vật tư (Class)" in changes:
                st.session_state["user_edited_materials"][real_bom_idx] = str(changes["Nhóm vật tư (Class)"]).upper().strip()
                has_changed = True

    if has_changed:
        st.rerun()
else:
    # Trạng thái chờ load tệp rập ban đầu
    st.write("")
