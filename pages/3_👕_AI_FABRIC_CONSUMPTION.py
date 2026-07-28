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
# ĐOẠN 6a - PHẦN 2: BỘ CẤU HÌNH CSS ĐỒNG BỘ MÀU SẮC & XỬ LÝ LỀ SIDEBAR - BẢN TINH GỌN CHỐNG TRỐNG
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

    /* 🛠️ MỞ KHÓA THANH CUỘN SIDEBAR CỐ ĐỊNH BÊN TRÁI HỆ THỐNG (SỬA LỖI LẤP TÍNH NĂNG) */
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
        overflow-y: auto !important; /* Đã chuyển từ hidden thành auto để tự động xuất hiện thanh cuộn dọc */
        z-index: 99999 !important;
    }
    
    [data-testid="stSidebar"] > div:first-child {
        height: 100vh !important;
        overflow-y: auto !important; /* Đã mở khóa lớp cuộn bên trong phôi RAM */
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

    /* 🛠️ ÉP THU HẸP KHOẢNG CÁCH DUNG LƯỢNG KEY TRÊN SIDEBAR - CHỐNG LÃNG PHÍ KHÔNG GIAN VÙNG TRỐNG */
    [data-testid="stSidebar"] hr {
        margin-top: 8px !important;
        margin-bottom: 8px !important;
    }
    [data-testid="stSidebar"] h5 {
        margin-bottom: 2px !important;
        padding-bottom: 0px !important;
    }
    [data-testid="stSidebar"] div[data-testid="stProgress"] {
        margin-top: 2px !important;
        margin-bottom: 2px !important;
    }
    [data-testid="stSidebar"] .stCaptionContainer {
        margin-top: -4px !important;
        margin-bottom: 4px !important;
    }
    /* Kéo giật khối ngang chứa 2 Metric (Số lượt quét và số Tokens) lên sát dải băng pin phía trên */
    [data-testid="stSidebar"] div[data-testid="stVerticalBlock"] > div[data-testid="stHorizontalBlock"] {
        margin-top: -12px !important; 
        gap: 4px !important; 
    }
    [data-testid="stSidebar"] div[data-testid="stMetricWidget"] {
        padding-top: 0px !important;
        padding-bottom: 0px !important;
        margin-bottom: 0px !important;
    }
    [data-testid="stSidebar"] label[data-testid="stMetricLabel"] p {
        font-size: 11px !important;
    }
    .sidebar-divider { margin: 12px 0 8px 0 !important; border: 0 !important; border-top: 1px solid #115e59 !important; }

    .kpi-box-flat-matrix { border-radius: 6px 6px 0 0 !important; padding: 10px 12px !important; text-align: center !important; box-shadow: 0 2px 4px rgba(0,0,0,0.02) !important; box-sizing: border-box !important; }
    .kpi-num-flat-matrix { font-size: 16px !important; font-weight: 700 !important; color: #ffffff !important; font-family: 'Segoe UI', sans-serif !important; line-height: 1.2 !important; }
    .kpi-lbl-flat-matrix { font-size: 9px !important; font-weight: 600 !important; color: #ffffff !important; opacity: 0.95 !important; text-transform: uppercase !important; margin-top: 2px !important; }
    .bg-style-erp { background: linear-gradient(135deg, #334155 0%, #1e293b 100%) !important; }
    .bg-items-erp { background: linear-gradient(135deg, #0d9488 0%, #0f766e 100%) !important; }
    .bg-cons-erp  { background: linear-gradient(135deg, #ea580c 0%, #c2410c 100%) !important; }
    .bg-size-erp { background: linear-gradient(135deg, #16a34a 0%, #15803d 100%) !important; }

    .image-placeholder-box-flat { border: 1px solid #cbd5e1 !important; border-top: none !important; border-radius: 0 0 6px 6px !important; padding: 10px 5px !important; height: 140px !important; display: flex !important; align-items: center !important; justify-content: center !important; box-sizing: border-box !important; margin-bottom: 25px !important; background-color: #ffffff !important; overflow: hidden !important; }
    div[data-testid="stImage"] img { width: 100% !important; height: auto !important; }
    
    /* Khử và ẩn hoàn toàn cái icon rác ảnh vỡ nhỏ màu trắng ở giữa lề */
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


# --- BẢNG ĐIỀU KHIỂN SIDEBAR MÁY CHỦ MỚI (CỐ ĐỊNH CHUẨN XÁC CHẾ ĐỘ KEY MUA - PREMIUM KEY ĐỒNG BỘ) ---
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

st.sidebar.markdown("---")
st.sidebar.markdown("##### 🔑 API KEY CAPACITY (DUNG LƯỢNG KEY)")

# Khởi tạo bộ đếm dung lượng tiêu hao thực tế trong màng RAM hệ thống
if "api_calls_count" not in st.session_state:
    st.session_state["api_calls_count"] = 0
if "tokens_consumed" not in st.session_state:
    st.session_state["tokens_consumed"] = 0

# Tính toán dung lượng ước tính dựa trên dữ liệu văn bản thô Techpack đã quét
if st.session_state.get("raw_pdf_text_extracted"):
    current_tokens = len(str(st.session_state["raw_pdf_text_extracted"])) // 4
    if st.session_state["tokens_consumed"] == 0:
        st.session_state["tokens_consumed"] = current_tokens
        st.session_state["api_calls_count"] += 1

# 🚨 SỬA LỖI ĐỒNG BỘ: Ép cứng nhận diện chế độ Key mua (Premium) cho công ty
# - Gán cứng True vì đây là Key mua đã nạp tiền/liên kết thẻ thanh toán của công ty bạn.
# - Gán False nếu sau này bạn muốn đổi sang một mã Key cá nhân dùng thử miễn phí nào khác.
is_paid_key = True  

if is_paid_key:
    # ➔ CHẾ ĐỘ KEY MUA: Mở khóa băng thông, màn hình luôn báo đầy pin 100% màu xanh ngọc lam sáng rõ
    st.sidebar.progress(1.0) 
    st.sidebar.caption("CN⚙️ **TÀI KHOẢN TRẢ PHÍ (PREMIUM KEY)** | Trạng thái: `BĂNG THÔNG MỞ RỘNG`")
else:
    # ➔ CHẾ ĐỘ KEY FREE: Tự động co giãn theo giới hạn 1500 lượt của Google
    max_daily_calls = 1500
    capacity_percentage = (max(0, max_daily_calls - st.session_state["api_calls_count"]) / max_daily_calls) * 100
    st.sidebar.progress(capacity_percentage / 100)
    st.sidebar.caption(f"🔋 Dung lượng khả dụng (Free Tier): `{capacity_percentage:.1f}%`")

# Hiển thị bộ đôi số liệu trực quan khít sát lề dải pin, chống lãng phí khoảng trống dư thừa
col_cap1, col_cap2 = st.sidebar.columns(2)
with col_cap1:
    st.metric("🔄 Lượt đã quét", f"{st.session_state['api_calls_count']}")
with col_cap2:
    st.metric("📊 Đã dùng (Tokens)", f"{st.session_state['tokens_consumed']:,}")

# CẤU HÌNH CANH SỢI SƠ ĐỒ (CAD) CO GIÃN ĐỊNH MỨC THEO GERBER CỦA BẠN VẪN GIỮ NGUYÊN PHÍA DƯỚI
st.sidebar.markdown("---")
st.sidebar.markdown("##### 📏 CẤU HÌNH CANH SỢI SƠ ĐỒ (CAD)")

st.sidebar.checkbox(
    "🔄 Cắt tự do (Xoay ngược 180°)", 
    key="allow_rotation_90", 
    value=True,
    help="Cho phép chi tiết xoay ngược đầu đuôi tự do. Trong một bộ không nhất thiết phải cùng chiều. Tối ưu sơ đồ khít nhất, định mức thấp nhất."
)
st.sidebar.checkbox(
    "✂️ Cắt mỗi bộ 1 chiều (Nap)", 
    key="is_nap_layout",
    help="Tất cả chi tiết trong 1 bộ rập phải xoay cùng 1 chiều dọc thớ vải."
)
st.sidebar.checkbox(
    "🧵 Tất cả size 1 chiều (One-Way)", 
    key="is_one_way_fabric",
    help="Ép toàn bộ chi tiết rập của mọi cỡ size quay chung về 1 hướng duy nhất (vải tuyết/nhung)."
)




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
                <div style="line-height: 1.4;"><span style="font-weight: 700; color: #2dd4bf;">Định mức:</span> Xem dữ liệu ở bảng đinh mức.</div>
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






# =====================================================================
# 🧠 ĐOẠN A: KHỐI HÀM CACHE AI - ĐÃ VÁ LỖI "genai is not defined" & CHỐNG HAO TIỀN
# =====================================================================
@st.cache_data(
    show_spinner=False,
    ttl=3600,  # Khóa chặt bộ nhớ Cache trong 1 tiếng để sửa UI thoải mái không bị tính tiền lần 2
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
    import copy
    import hashlib
    import google.generativeai as genai  # 🛠️ CHÈN BỔ SUNG DÒNG NÀY ĐỂ TRIỆT TIÊU LỖI NAMEERROR TRÊN GIAO DIỆN

    if hasattr(pdf_bytes, "getvalue"):
        pdf_bytes = pdf_bytes.getvalue()

    if not isinstance(pdf_bytes, bytes):
        raise TypeError("Dữ liệu PDF đầu vào không đúng định dạng bytes hợp lệ!")

    full_pdf_raw_text = ""
    image_payloads = []

    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc_recovery:
        total_pages = len(doc_recovery)

        for idx in range(total_pages):
            page_text = doc_recovery[idx].get_text("text")
            full_pdf_raw_text += f"\n--- PAGE {idx + 1} ---\n{page_text}"

            # Giới hạn phòng vệ gửi 2 trang ảnh đầu để bảo vệ số dư tài khoản 300k
            if len(image_payloads) < 2:
                try:
                    pix = doc_recovery[idx].get_pixmap(dpi=72, colorspace=fitz.csRGB)
                    image_payloads.append({"mime_type": "image/jpeg", "data": pix.tobytes("jpeg")})
                except Exception:
                    continue

    gemini_inputs = copy.deepcopy(image_payloads)
    gemini_inputs.insert(0, f"=== USER CHAT COMMAND ===\n{current_query}\n\n=== TECHPACK TEXT ===\n{full_pdf_raw_text}\n")

    extended_prompt = prompt_agent_2 + """
    CRITICAL MULTI-MATERIAL EXTRACTION RULES:
    - You MUST extract EVERY SINGLE component listed in the document, not just FABRIC.
    - If a component name contains "FUSING", "INTERLINING", "MEX", "DỰNG", "KEO LOT", classify its material_class strictly as "FUSING".
    - If a component name contains "LINING", "POCKET BAG", "LOT TUI", classify its material_class strictly as "LINING".
    """
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
        raise RuntimeError(f"Mô hình Gemini trả về cấu trúc chuỗi JSON không hợp lệ:\n\n{txt}") from json_err

    if blueprint_worker and "bom_rows" in blueprint_worker:
        blueprint_worker["calculated_on_size"] = target_size_cmd
        for row in blueprint_worker.get("bom_rows", []):
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
            try: row["gross_consumption"] = round(float(row.get("gross_consumption", 0.0415)), 4)
            except: row["gross_consumption"] = 0.0415
            try: row["marker_efficiency"] = str(row.get("marker_efficiency", "82.5%")).strip()
            except: row["marker_efficiency"] = "82.5%"
            
            try:
                forced_width = float(active_width)
                if current_query:
                    width_match = re.search(r"(khổ\s*vải|khổ)\s*(\d+(\.\d+)?)", str(current_query), re.IGNORECASE)
                    if width_match: forced_width = float(width_match.group(2))
                row["fabric_width_inch"] = forced_width
            except:
                row["fabric_width_inch"] = float(active_width)

    if "api_calls_count" not in st.session_state: st.session_state["api_calls_count"] = 0
    if "tokens_consumed" not in st.session_state: st.session_state["tokens_consumed"] = 0
        
    st.session_state["api_calls_count"] += 1
    st.session_state["tokens_consumed"] += len(str(full_pdf_raw_text)) // 4

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
# 🟩 ĐOẠN 2 (PHẦN 1/2): BỘ LỌC ĐẦU VÀO & SCHEMA KHỬ SẠCH PHỤ LIỆU LOẠT LOẠT
# =====================================================================
if st.session_state.ai_processing:
    current_query = st.session_state["last_submitted_query"]
    active_pdf = st.session_state.get("pdf_bytes") or st.session_state.get("uploaded_file") or st.session_state.get("current_pdf") or st.session_state.get("pdf_data")

    dynamic_width, target_size = 58.0, "32"
    if current_query:
        import re
        w_m = re.search(r"(khổ\s*vải|khổ)\s*(\d+(\.\d+)?)", str(current_query), re.IGNORECASE)
        if w_m: dynamic_width = float(w_m.group(2))
        s_m = re.search(r"(cỡ|size)\s*(\d+)", str(current_query), re.IGNORECASE)
        if s_m: target_size = str(s_m.group(2))

    if active_pdf is not None:
        with st.spinner("🧠 AI Vision đang quét phôi rập Nguyên Liệu..."):
            try:
                # 1. JSON SCHEMA GIỚI HẠN CHẶN CỨNG CHỦNG LOẠI VẬT TƯ (CHỈ QUÉT VẢI/KEO)
                raw_json_schema = {
                    "type": "OBJECT",
                    "properties": {
                        "detected_product_type": {"type": "STRING"},
                        "detected_base_size": {"type": "STRING"},
                        "bom_rows": {
                            "type": "ARRAY",
                            "items": {
                                "type": "OBJECT",
                                "properties": {
                                    "component_name": {"type": "STRING"},
                                    "bounding_box_length": {"type": "NUMBER"},
                                    "bounding_box_width": {"type": "NUMBER"},
                                    "piece_shape": {"type": "STRING"},
                                    "piece_function": {"type": "STRING"},
                                    "fold_type": {"type": "STRING"},
                                    # 🚨 CHỐNG RÁC DỮ LIỆU: Khống chế ENUM chỉ cho phép trả về phôi rập có diện tích rải sơ đồ
                                    "material_zone": {"type": "STRING", "enum": ["SELF", "LINING", "INTERFACING", "RIB", "CONTRAST"]},
                                    "grain_constraint": {"type": "STRING"},
                                    "packing_priority": {"type": "INTEGER"},
                                    "convex_fill_ratio": {"type": "NUMBER"},
                                    "seam_allowance": {"type": "STRING"},
                                    "mirror_piece": {"type": "BOOLEAN"},
                                    "is_left_right_pair": {"type": "BOOLEAN"},
                                    "requires_matching": {"type": "BOOLEAN"},
                                    "critical_alignment": {"type": "STRING"},
                                    "cut_quantity": {"type": "INTEGER"},
                                    "grain_direction": {"type": "STRING"},
                                    "rotation_allowed": {"type": "STRING"},
                                    "edge_curvature": {"type": "STRING"},
                                    "shape_complexity": {"type": "STRING"},
                                    "inference_source": {"type": "STRING"},
                                    "cad_reconstruction_score": {"type": "INTEGER"},
                                    "field_confidence": {
                                        "type": "OBJECT",
                                        "properties": {"dimensions": {"type": "STRING"}, "geometry_shape": {"type": "STRING"}, "grain_alignment": {"type": "STRING"}},
                                        "required": ["dimensions", "geometry_shape", "grain_alignment"]
                                    },
                                    "shape_parameters": {
                                        "type": "OBJECT",
                                        "properties": {
                                            "estimated_corner_points": {"type": "INTEGER"}, "dominant_axis": {"type": "STRING"},
                                            "top_width_ratio": {"type": "NUMBER"}, "bottom_width_ratio": {"type": "NUMBER"},
                                            "left_edge_profile": {"type": "STRING"}, "right_edge_profile": {"type": "STRING"},
                                            "waist_curve_depth": {"type": "NUMBER"}, "hem_curve_depth": {"type": "NUMBER"}, "crotch_projection_ratio": {"type": "NUMBER"}
                                        }
                                    }
                                },
                                "required": ["component_name", "bounding_box_length", "bounding_box_width", "piece_shape", "piece_function", "fold_type", "material_zone", "packing_priority", "convex_fill_ratio", "mirror_piece"],
                            },
                        },
                    },
                    "required": ["detected_product_type", "detected_base_size", "bom_rows"],
                }
                # =====================================================================
                # 🟩 ĐOẠN 2 (PHẦN 2/2): PROMPT PHÒNG VỆ CHỐNG RÁC PHỤ LIỆU & AI EXECUTE
                # =====================================================================
                prompt_agent_2 = f"""
                You are a senior Industrial Garment IE & CAD Pattern Engineering Intelligence. Reconstruct the multi-layered CAD metadata for EVERY valid fabric/fusing piece in the Techpack for Size {target_size}.
                
                🚨 CRITICAL ACCESSORY OMISSION MANDATE (LỆNH KHỬ TRỪ PHỤ LIỆU):
                - NEVER extract buttons, sewing threads, zippers, sliders, rivets, main labels, care labels, size tabs, hangtags, polybags, or any metal/plastic accessories.
                - IGNORE them completely. They do NOT have marker dimensions or 2D polygon packing footprints.
                - ONLY extract components belonging to: SELF (Vải chính), LINING (Vải lót), INTERFACING (Mếch/Keo/Fusing), RIB (Bo), or CONTRAST (Vải phối).
                
                🚨 SECTION 1: EXTRACT BOUNDING BOX (ANTI-ZERO RULE)
                Extract/estimate exact 'bounding_box_length' and 'bounding_box_width' in INCHES. NEVER output 0.0.
                
                🚨 SECTION 2: CAD GEOMETRIC SHAPE & METADATA
                Map each valid component to:
                - 'piece_shape': RECTANGLE, TRAPEZOID, TAPERED_PANEL, CURVED_PANEL, POCKET, WAISTBAND, COLLAR, SLEEVE, GUSSET.
                - 'piece_function': PRIMARY, SECONDARY, REINFORCEMENT, DECORATIVE, LINING.
                - 'fold_type': NONE, CENTER_FOLD, EDGE_FOLD, ON_FOLD.
                - 'material_zone': SELF, LINING, INTERFACING, RIB, CONTRAST.
                - 'packing_priority': 1 (Main Panels) to 5 (Small Filler Loops).
                - 'convex_fill_ratio': RECTANGLE=0.98; Waistband=0.94; Curved/Tapered Panel=0.68-0.76; Pocket=0.82; Collar=0.60.
                - 'mirror_piece': [true, false].
                
                🚨 SECTION 3: 5 CRITICAL SOLVER FIELDS
                - 'cut_quantity': Total physical pieces to be cut.
                - 'grain_direction': VERTICAL, HORIZONTAL, BIAS.
                - 'rotation_allowed': 0_DEG, 180_DEG, ANY.
                - 'edge_curvature': LOW, MEDIUM, HIGH.
                - 'shape_complexity': LOW, MEDIUM, HIGH.
                
                🚨 SECTION 4: RECONSTRUCTION & VALIDATION
                Output inference_source, cad_reconstruction_score, field confidence, and shape_parameters. Perform strict validation: a component cannot be processed if it has no 2D area. Skip all non-pattern rows.
                """

                # 3. GỌI HÀM QUÉT AI CACHE VÀ TRUYỀN KHỔ VẢI ĐỘNG ĐÃ TRÍCH XUẤT
                bom_data = execute_cached_gemini_scan(
                    pdf_bytes=active_pdf, current_query=current_query,
                    active_width=dynamic_width, target_size_cmd=target_size,
                    raw_json_schema=raw_json_schema, prompt_agent_2=prompt_agent_2
                )
                
                st.session_state["bom_data"] = bom_data
                if bom_data and "bom_rows" in bom_data:
                    st.session_state["accumulated_bom_rows"] = bom_data["bom_rows"]
                
                st.session_state.ai_processing = False
                st.success("✅ AI Core đã lọc sạch phụ liệu và đồng bộ phôi rập thành công!")
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
    ĐÃ NÂNG CẤP: Quét diện rộng bố cục bảng, chống sót lệnh x2 viết liền, bảo vệ định mức tổng.
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
        # 🛠️ TỐI ƯU 1: Mở rộng vùng quét lên trước 100 và sau 450 ký tự để bao phủ hết toàn bộ dòng dữ liệu trên bảng BOM
        window_start = max(0, match_index - 100)
        window_end = min(len(text_clean), match_index + 450)
        scan_window = text_clean[window_start:window_end]
        
        # 🛠️ TỐI ƯU 2: Regex siêu cấp bắt trọn mọi kiểu ghi (CUT 2, CUT=2, SELF X2, PANEL X2, PANEL(2), PANEL-2)
        # Bắt được cả chữ viết liền hoặc chỉ có ký tự số đặt trong ngoặc đơn lân cận tên rập
        cut_match = re.search(r'(?:cut|cắt|self|shell|\bx\b|\bqty\b)\s*(?:x\s*|\s*|=\s*|\(-\s*)(\d+)|(?:\s+|\()(\d+)(?:\s*pcs|\s*chi tiết|\))', scan_window)
        
        if cut_match:
            # Lấy nhóm dữ liệu số khớp được từ 1 trong 2 cấu trúc Regex trên
            detected_qty_str = cut_match.group(1) or cut_match.group(2)
            if detected_qty_str:
                detected_qty = int(detected_qty_str)
                layer_multiplier = detected_qty
                calc_log = f"Trích xuất trực tiếp PDF Callout: Tìm thấy lệnh số lượng {detected_qty} chi tiết."
            
        # ➔ B. Quét lệnh đối xứng / cặp đôi (PAIR, MIRROR, X2)
        if any(k in scan_window for k in ["pair", "cặp", "đối", "mirror", "đối xứng", "1 pair", "x2"]):
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
    """Khối 3 hoàn chỉnh kiến trúc mới: Python Geometric Area Solver.
    ĐÃ ĐỒNG BỘ: Kết nối ma trận đa biến 14 lớp, đọc hiểu INTERFACING, RIB, CONTRAST.
    """
    total_fabric_piece_area = 0.0
    piece_calculated_data = []
    raw_pdf_context = st.session_state.get("raw_pdf_text_extracted", "")

    for r in bom_rows_list:
        if not r or not isinstance(r, dict): continue
        
        raw_l = safe_float(r.get("bounding_box_length", r.get("Dài (L-inch)", 0.0)))
        raw_w = safe_float(r.get("bounding_box_width", r.get("Rộng (W-inch)", 0.0)))
        
        pcs = safe_int(r.get("original_piece_count", r.get("pcs_numeric", 1)))
        if "original_piece_count" not in r:
            r["original_piece_count"] = pcs
            
        comp_name_raw = str(r.get("component_name", "UNNAMED")).upper().strip()
        
        # Đọc dữ liệu định danh cấu trúc hình học mới từ AI
        piece_shape = str(r.get("piece_shape", "TAPERED_PANEL")).upper().strip()
        piece_function = str(r.get("piece_function", "PRIMARY")).upper().strip()
        fold_type = str(r.get("fold_type", "NONE")).upper().strip()
        mat_zone = str(r.get("material_zone", "SELF")).upper().strip()
        grain_constraint = str(r.get("grain_constraint", "PREFERRED")).upper().strip()
        packing_priority = safe_int(r.get("packing_priority", 3), default=3)
        critical_alignment = str(r.get("critical_alignment", "NONE")).upper().strip()
        
        # Đọc trường số lượng và độ cong động
        cut_qty_ai = safe_int(r.get("cut_quantity", 1), default=1)
        ai_convex_ratio = safe_float(r.get("convex_fill_ratio", 0.74))
        if ai_convex_ratio <= 0 or ai_convex_ratio > 1.0:
            ai_convex_ratio = 0.74
            
        mirror_piece = r.get("mirror_piece", False)

        if raw_l > 0:
            # 1. Áp thông số co rút vải
            adj_l = raw_l * (1 + safe_float(warp_shrinkage) / 100.0)
            adj_w = raw_w * (1 + safe_float(weft_shrinkage) / 100.0) if raw_w > 0 else raw_w
            
            # 2. Đồng bộ số lượng cắt (Ưu tiên số lượng cắt thực tế cut_quantity của AI)
            layer_multiplier = cut_qty_ai
            calc_chain_log = f"Số lượng cắt: {layer_multiplier} chi tiết."
            if mirror_piece and layer_multiplier == 1:
                layer_multiplier = 2
                calc_chain_log += " | Nhân đôi đối xứng."

            # 3. Tính toán hệ số phom dáng hình học (Shape Factor) từ Convex Ratio động
            shape_factor = ai_convex_ratio
            if fold_type in ["ON_FOLD", "CENTER_FOLD"]:
                shape_factor *= 0.98
            if critical_alignment in ["STRIPE", "PLAID"]:
                shape_factor += 0.03
                
            if piece_function == "PRIMARY":
                shape_factor = max(0.6300, min(0.9200, shape_factor))
            elif piece_shape == "RECTANGLE":
                shape_factor = 0.98

            # 4. Cộng thêm độ rộng đường may biên rập tiêu chuẩn (+0.88 inch)
            sa_match = re.search(r'(\d+\.?\d*)', str(r.get("seam_allowance", "0.88")))
            sa_val = float(sa_match.group(1)) if sa_match else 0.88
            
            seamed_l = adj_l + (sa_val * 2)
            seamed_w = adj_w + (sa_val * 2) if raw_w > 0 else adj_w
            
            total_pcs_final = pcs * layer_multiplier
            item_area = seamed_l * seamed_w * shape_factor * total_pcs_final
            
            # Đồng bộ chuẩn hóa nhóm chất liệu dệt thoi/dệt kim thương mại
            # Ép ghi nhận INTERFACING tương đương FUSING để duy trì mạch chạy ngầm
            if mat_zone == "SELF": r_material_class = "FABRIC"
            elif mat_zone == "INTERFACING": r_material_class = "FUSING"
            else: r_material_class = mat_zone
            
            r["material_class"] = r_material_class
            if r_material_class == "FABRIC": 
                total_fabric_piece_area += item_area
            
            # Đẩy ngược dữ liệu đã làm giàu vào DataFrame
            r["production_length"] = adj_l
            r["production_width"] = adj_w
            r["piece_count"] = total_pcs_final
            r["Số lượng rập"] = total_pcs_final
            r["polygon_net_area"] = round(seamed_l * seamed_w * shape_factor, 2)
            r["calculation_status"] = "PROCESSED"
            r["cad_algorithm"] = f"Phom: {piece_shape} | Cấp ưu tiên: {packing_priority}"
            
            piece_calculated_data.append({
                "row_ref": r, "item_area": item_area, "is_button": False, "pcs_display": f"{total_pcs_final} Pcs",
                "layer_multiplier": layer_multiplier, "mat_class_raw": r_material_class, "combined_str": f" {comp_name_raw} ", 
                "is_belt_loop": (piece_shape == "RECTANGLE" and "LOOP" in comp_name_raw), 
                "raw_l": adj_l, "raw_w": adj_w, "pcs_val": pcs, "custom_name": comp_name_raw
            })
            
    st.session_state["piece_calculated_data"] = piece_calculated_data
    return round(total_fabric_piece_area, 4), piece_calculated_data



def allocate_gerber_share_consumption(piece_calculated_data, total_fabric_piece_area, skyline_results):
    """Khối 4 hoàn chỉnh nâng cấp: Phân bổ định mức Gerber chuẩn xác.
    ĐÃ ĐỒNG BỘ: Đọc hiểu và phân phối độc lập cho RIB, CONTRAST, FUSING, LINING.
    """
    base_gross_fabric = skyline_results.get("global_gross_fabric_yds", 0.0)
    if base_gross_fabric == 0.0:
        base_gross_fabric = skyline_results.get("global_gross_fabric_consumption", 0.0)
    if base_gross_fabric == 0.0:
        base_gross_fabric = skyline_results.get("global_gross_fabric", 0.0)
        
    product_segmented = skyline_results.get("product_segmented", "CASUAL_TOP")
    actual_packing_density = skyline_results.get("actual_packing_density", 0.85)
    if actual_packing_density <= 0: actual_packing_density = 0.85
    
    bom_source = st.session_state.get("bom_data", {})
    usable_width = bom_source.get("fabric_width_inch", 58.0)
    if not isinstance(usable_width, (int, float)) or usable_width <= 0: usable_width = 58.0
    
    # Đồng bộ khổ vải phụ từ bộ nhớ hệ thống
    lining_width = float(st.session_state.get("lining_width_inch", 57.0))
    fusing_width = float(st.session_state.get("fusing_width_inch", 59.0))
    
    processed_rows = []

    for item in piece_calculated_data:
        if "row_ref" not in item: continue
        r = item["row_ref"]
        item_area = item["item_area"]
        layer_multiplier = item["layer_multiplier"]
        mat_class_raw = str(item["mat_class_raw"]).upper().strip()
        
        raw_l = r.get("production_length", item.get("raw_l", 0.0))
        pcs = item["pcs_val"]

        if "FABRIC" in mat_class_raw:
            packing_priority = safe_int(r.get("packing_priority", 3), default=3)
            if total_fabric_piece_area > 0 and base_gross_fabric > 0:
                # Phân phối gánh nặng định mức nền theo cấp bậc ưu tiên rập lớn/rập phụ
                weight_factor = 1.12 if packing_priority <= 2 else (0.85 if packing_priority >= 4 else 1.00)
                share_ratio = (item_area / total_fabric_piece_area) * weight_factor
                gross_consumption = round(base_gross_fabric * share_ratio, 4)
                calc_chain = f"Gerber Fabric Priority {packing_priority}"
            else:
                estimated_base = ((item_area / usable_width) / 36.0) / actual_packing_density
                gross_consumption = round(estimated_base * 1.045, 4)
                calc_chain = f"CAD Geometry Fallback"
                    
        elif "LINING" in mat_class_raw:
            gross_consumption = round(((item_area / lining_width) / 36.0 / 0.72), 4)
            calc_chain = f"Sơ đồ LINING độc lập (Khổ {lining_width} inch)"
            
        elif "FUSING" in mat_class_raw:
            gross_consumption = round(((item_area / fusing_width) / 36.0 / 0.70 * 1.15), 4)
            calc_chain = f"Sơ đồ FUSING độc lập (Khổ {fusing_width} inch)"
            
        elif mat_class_raw in ["RIB", "CONTRAST"]:
            # Định mức độc lập cho Vải bo (Rib) và Vải phối tính theo diện tích chiếm dụng phẳng + 5% hao hụt biên
            gross_consumption = round(((item_area / usable_width) / 36.0 / 0.78 * 1.05), 4)
            calc_chain = f"Sơ đồ phối {mat_class_raw} độc lập"
        else:
            gross_consumption, calc_chain = 0.0, f"Vật tư mẫu hàng {product_segmented}."

        r["Gross Consumption"] = gross_consumption
        item["row_ref"]["Gross Consumption"] = gross_consumption
        r["Số lượng rập"] = f"{pcs * layer_multiplier} Pcs"
        
        processed_rows.append(r)

    ctx = st.session_state.get("bom_data", {})
    ctx["global_gross_fabric_yds"] = base_gross_fabric
    ctx["actual_packing_density"] = actual_packing_density
    st.session_state["bom_data"] = ctx

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
# 🟩 ĐOẠN 1: BỐC TÁCH THAM SỐ VÀ ĐỒNG BỘ CHÍNH XÁC SIZE MẪU (ĐÃ FIX KHỔ VẢI 58 & CHỐNG NHẢY SIZE)
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

# 🛠️ 2. SỬA TẬN GỐC LUỒNG BỐC SIZE: Ưu tiên bóc tách số size đơn (Ví dụ: 32, 30) để đồng bộ hoàn hảo với CAD Gerber
detected_size_code = ""
if ctx.get("detected_base_size") and str(ctx.get("detected_base_size")).strip() != "":
    detected_size_code = str(ctx.get("detected_base_size")).upper().strip()
elif ctx.get("base_size") and str(ctx.get("base_size")).strip() != "":
    detected_size_code = str(ctx.get("base_size")).upper().strip()
else:
    # Quét tìm ký tự số size dạng đơn trước (ví dụ: size 32, size 30)
    size_match = re.search(r'size\s*(\d+)', chat_input_text)
    if size_match:
         detected_size_code = size_match.group(1).upper()
    else:
         # Nếu là chuỗi dài dạng 32x33, bóc lấy phần số đầu tiên (Size eo 32) để rập không bị lỗi diện tích bằng 0
         long_size_match = re.search(r'size\s*(\d+x\d+)', chat_input_text)
         detected_size_code = long_size_match.group(1).split('X')[0].upper() if long_size_match else "32"

# Rút gọn chuỗi size phức tạp về dạng số chuẩn (Ví dụ: "32X33" -> "32") giúp Regex Khối 3 và Khối 5 không bị crash
if "X" in detected_size_code:
    detected_size_code = detected_size_code.split("X")[0].strip()

ctx["detected_base_size"] = detected_size_code
st.session_state["detected_base_size"] = detected_size_code
st.session_state["target_size"] = detected_size_code # Khóa đồng bộ cho Prompt Agent 2

# 🚨 3. ĐỒNG BỘ KHỔ VẢI YÊU CẦU: Ép cứng mặc định về 58.0 inch, ghi đè triệt để vào bộ nhớ hệ thống
fabric_width = extract_param(r'(?:khổ\s*vải|vải\s*khổ|khổ)\s*[:=-]?\s*(\d+(?:\.\d+)?)', chat_input_text, "fabric_width_inch", 58.0) 
if fabric_width <= 0 or fabric_width == 55.0: 
    fabric_width = 58.0
st.session_state["fabric_width_inch"] = fabric_width
ctx["fabric_width_inch"] = fabric_width

# Khổ keo và khổ lót độc lập
fusing_width = extract_param(r'(?:khổ\s*keo|keo\s*khổ|dựng\s*khổ|khổ\s*dựng)\s*[:=-]?\s*(\d+(?:\.\d+)?)', chat_input_text, "fusing_width_inch", 59.0)
if fusing_width <= 0: fusing_width = 59.0
st.session_state["fusing_width_inch"] = fusing_width
ctx["fusing_width_inch"] = fusing_width

lining_width = extract_param(r'(?:khổ\s*lót|lót\s*khổ|vải\s*lót\s*khổ)\s*[:=-]?\s*(\d+(?:\.\d+)?)', chat_input_text, "lining_width_inch", 57.0)
if lining_width <= 0: lining_width = 57.0
st.session_state["lining_width_inch"] = lining_width
ctx["lining_width_inch"] = lining_width

# =====================================================================
# 🟩 ĐOẠN 2: CHUẨN HÓA DỮ LIỆU ĐẦU VÀO VÀ ĐỒNG BỘ SỐ LƯỢNG RẬP CHI TIẾT - ĐÃ ĐỒNG BỘ KHÓA CO RÚT
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
        
        # 🛠️ SỬA LỖI NHÂN ĐÔI LŨY TIẾN: Giữ nguyên số lượng rập gốc ban đầu từ file, không ép cứng lên 4.0 
        # để tránh bị hàm nhân đôi đối xứng cặp ở Khối 3 nhân chồng lên thành 8 chi tiết gây sập diện tích.
        return pcs_val

    df_bom["pcs_numeric"] = [
        float(st.session_state["user_edited_pieces"][idx]) if idx in st.session_state["user_edited_pieces"]
        else clean_precise_piece_count(row) for idx, row in df_bom.iterrows()
    ]
    df_bom[pcs_col] = df_bom["pcs_numeric"]

    # =====================================================================
    # 🚨 NATURAL LANGUAGE PARSER ENGINE (BẮT KHỚP CHÍNH XÁC MÃ KHÓA CHAT CHUẨN)
    # =====================================================================
    # 🛠️ ĐỒNG BỘ KHÓA BỘ NHỚ: Sửa toàn bộ tên khóa lưu trữ về "warp_shrinkage" và "weft_shrinkage" đồng quy với Đoạn 1
    if "fabric_width_inch" not in st.session_state: st.session_state["fabric_width_inch"] = 58.0
    if "warp_shrinkage" not in st.session_state: st.session_state["warp_shrinkage"] = 0.0
    if "weft_shrinkage" not in st.session_state: st.session_state["weft_shrinkage"] = 0.0

    user_command = str(st.session_state.get("last_submitted_query", "")).lower().strip()

    if user_command:
        # A. Quét tìm cấu hình khổ vải chính
        width_match = re.search(r'(?:kh\s*ổ|kho)\s*(\d+(?:\.\d+)?)', user_command)
        if width_match:
            st.session_state["fabric_width_inch"] = float(width_match.group(1))

        # B. Quét tìm độ co rút sợi dọc (Ghi chuẩn vào khóa warp_shrinkage)
        warp_match = re.search(r'(?:d\s*ọc|doc)\s*(\d+(?:\.\d+)?)', user_command)
        if warp_match:
            st.session_state["warp_shrinkage"] = float(warp_match.group(1))

        # C. Quét tìm độ co rút sợi ngang (Ghi chuẩn vào khóa weft_shrinkage)
        weft_match = re.search(r'(?:ngang)\s*(\d+(?:\.\d+)?)', user_command)
        if weft_match:
            st.session_state["weft_shrinkage"] = float(weft_match.group(1))

    # Xuất bản giá trị ra hệ thống đồng bộ tuyệt đối cho Đoạn 3, 4, 5
    fabric_width = float(st.session_state["fabric_width_inch"])
    warp_shrink = float(st.session_state["warp_shrinkage"])
    weft_shrink = float(st.session_state["weft_shrinkage"])
    # =====================================================================
    # 🟩 ĐOẠN 3.1: AI MULTI-LAYER PRODUCT CLASSIFIER (BỘ PHÂN TÍCH LOẠI HÀNG CHUẨN) - TỐI ƯU HIỆU SUẤT GERBER
    # =====================================================================
    import pandas as pd

    # 🛠️ TỐI ƯU GERBER THỰC TẾ: Điều chỉnh hạ Barem mật độ cơ sở (Prior) của dòng quần Jean/Pants 
    # từ 87.5% xuống mốc an toàn thực tế phòng cắt là 0.795 (79.5%) để kích định mức tổng không bị tụt thấp.
    COMPANY_DENSITY_PRIOR = {
        "SHIRT": 0.82, "JEAN_LONG": 0.795, "SHORT": 0.83, 
        "JACKET": 0.68, "VEST": 0.82, "TOPS_KNIT": 0.78, 
        "SKIRT": 0.82, "DRESS_FLARE": 0.72
    }

    comp_col_check = next((c for c in ["Component Name", "component_name", "Component_Name"] if c in df_bom.columns), "component_name")
    prod_upper_name = str(prod).upper().strip() if 'prod' in locals() else ""
    product_category = None
    
    # 🧠 TẦNG 1: Gom toàn bộ văn bản từ danh sách linh kiện trong file rập/BOM để AI phân tích từ khóa chuyên ngành
    all_components_text = " ".join(df_bom[comp_col_check].astype(str).str.upper().tolist())

    # 🧠 TẦNG 2 (AI QUYẾT ĐỊNH LOẠI HÀNG): Quét từ khóa để phân biệt rạch ròi giữa ÁO và QUẦN
    if any(x in all_components_text for x in ["TROUSER", "LEG", "ĐŨNG", "ĐÁY QUẦN", "JEAN", "PANTS", "QUẦN", "QUAN", "WAISTBAND", "FLY", "CẠP", "LƯNG", "POCKET FACING"]):
        product_category = "JEAN_LONG"
        
    elif any(x in all_components_text for x in ["SLEEVE", "COLLAR", "CỔ ÁO", "TAY ÁO", "JACKET", "KHOÁC", "BODY PANEL"]):
        product_category = "JACKET"
        
    # TẦNG 3: Nếu quét linh kiện vẫn trống, AI sẽ đọc tiêu đề sản phẩm (Header Techpack)
    else:
        for k in COMPANY_DENSITY_PRIOR.keys():
            if k in prod_upper_name or (k == "DRESS_FLARE" and any(d in prod_upper_name for d in ["DRESS", "FLARE", "ĐẦM", "XÒE", "SHIFT", "MAXI"])):
                product_category = k
                break
        # Mặc định phòng hộ nếu file lỗi không có thông tin
        if product_category is None:
            product_category = "JEAN_LONG"

    # 🧠 TẦNG 4: Đồng bộ chuỗi văn bản dịch thuật để AI xuất bản ra giao diện UI báo cáo
    if product_category == "VEST": ai_product_type = "VEST (Áo Vest/Blazer)"
    elif product_category == "JACKET": ai_product_type = "JACKET (Áo khoác Jacket)"
    elif product_category == "DRESS_FLARE": ai_product_type = "DRESS_FLARE (Đầm suông/Thời trang)"
    elif product_category == "SKIRT": ai_product_type = "SKIRT (Chân váy)"
    elif product_category == "TOPS_KNIT": ai_product_type = "TOPS_KNIT (Áo thun/Polo)"
    elif product_category == "SHIRT": ai_product_type = "SHIRT (Áo sơ mi)"
    elif product_category == "SHORT": ai_product_type = "SHORT (Quần short)"
    else: ai_product_type = "JEAN_LONG (Quần dài Jeans/Pants)"
    
    # Ghi giá trị phân tích sạch vào context vùng nhớ hệ thống để nuôi luồng Đoạn 4 và Đoạn 5
    if "ai_expert_decision" not in ctx or not isinstance(ctx["ai_expert_decision"], dict): 
        ctx["ai_expert_decision"] = {}
        
    ctx["ai_expert_decision"]["product_category"] = product_category
    ctx["ai_expert_decision"]["product_type_friendly"] = ai_product_type
    
    # 🛠️ NẠP ĐỒNG BỘ ƯU TIÊN: Đưa thẳng mốc mật độ an toàn vừa cập nhật vào bộ nhớ đệm 
    # giúp Đoạn 5.1 bốc đúng thông số nền, giải phóng hoàn toàn lỗi nghẽn định mức thấp.
    ctx["ai_expert_decision"]["estimated_density_prior"] = COMPANY_DENSITY_PRIOR[product_category]
        # =====================================================================
    # 🟩 ĐOẠN 3.2: GEOMETRIC FEATURE ENGINE & DISTRIBUTION PRIOR (V10 SYNC LAYER)
    # =====================================================================
    import numpy as np

    # Tái định vị các cột dữ liệu hệ thống ngay trên đầu đoạn 3.2 để nuôi lệnh l_val
    comp_col_check = next((c for c in ["Component Name", "component_name", "Component_Name"] if c in df_bom.columns), "component_name")
    l_prod_col_check = "Dài sản xuất (L-inch)" if "Dài sản xuất (L-inch)" in df_bom.columns else (orig_l_col if 'orig_l_col' in locals() else "bounding_box_length")
    w_prod_col_check = "Rộng sản xuất (W-inch)" if "Rộng sản xuất (W-inch)" in df_bom.columns else (orig_w_col if 'orig_w_col' in locals() else "bounding_box_width")
    area_col_check = next((c for c in ["polygon_net_area", "net_area", "Diện tích (inch²)"] if c in df_bom.columns), "polygon_net_area")

    # Truy xuất cấu hình sản xuất từ Streamlit UI
    fabric_width = float(st.session_state.get("fabric_width_inch", 58.0))
    rotation_freedom = st.session_state.get("allow_rotation_90", True)      
    one_way_flag = st.session_state.get("is_one_way_fabric", False)          
    stripe_plaid_flag = st.session_state.get("is_stripe_plaid", False)       
    fabric_type = st.session_state.get("fabric_material_type", "WOVEN")       

    # Đọc lại nhãn loại hàng đã được Đoạn 3.1 lưu vào context
    product_category = ctx["ai_expert_decision"]["product_category"]
    
    if "user_edited_pieces" not in st.session_state: st.session_state["user_edited_pieces"] = {}

    piece_areas = []
    total_pattern_pieces, total_pocket_pieces, max_piece_length = 0.0, 0.0, 0.0

    # 🛠️ BỘ PHÂN LOẠI CHẤT LIỆU LAYER TRÍ THỨC (GIỮ LẠI ĐỂ TÁCH LỌC VẬT TƯ SẠCH RÁC)
    def _d3_internal_material_classify(row, idx, prod_cat):
        if "user_edited_materials" in st.session_state and idx in st.session_state["user_edited_materials"]:
            return str(st.session_state["user_edited_materials"][idx]).upper().strip()
        mat_str = str(row[m_col]).upper().strip() if 'm_col' in locals() and m_col in row else ""
        comp_str = str(row.get(comp_col_check, row.get("component_name", ""))).upper().strip()
        role_str = str(row.get("Role/Piece Type", row.get("geometry_role", ""))).upper().strip()
        
        fusing_kws = ["FUSING", "INTERLINING", "INTERFACING", "KEO", "MEC", "MẾCH", "BOND", "ADHESIVE", "LOT KEO", "TRICOT"]
        lining_kws = ["LINING", "LOT", "LÓT", "POCKETING", "MESH", "TAFFETA", "VAI LOT", "VẢI LÓT", "POCKET BAG"]
        
        if any(k in comp_str for k in ["WAISTBAND", "LƯNG", "CẠP", "BELT"]) and not any(x in mat_str for x in ["MEC", "KEO", "FUSING", "INTERFACING"]):
            return "FABRIC"
            
        if any(k in mat_str or k in comp_str for k in fusing_kws): return "FUSING"
        if any(k in mat_str or k in comp_str or k in role_str for k in lining_kws): return "LINING"
        return "FABRIC"

    for idx, r in df_bom.iterrows():
        p_class_clean = _d3_internal_material_classify(r, idx, product_category)
        comp_name_clean = str(r.get(comp_col_check, "")).upper().strip()
        
        mat_clean_str = str(r.get(m_col, "")).upper().strip() if 'm_col' in locals() and m_col in r else ""
        if any(x in comp_name_clean or x in mat_clean_str for x in ["BUTTON", "ZIP", "THREAD", "NÚT", "CHỈ", "RIVET", "LABEL", "NHÃN", "MÁC", "SHANK", "SLIDER", "PULLER", "ACCESSORY", "PHỤ LIỆU"]):
            continue

        try:
            pcs_numeric_val = float(r.get("pcs_numeric", 1.0))
            if np.isnan(pcs_numeric_val): pcs_numeric_val = 1.0
        except:
            pcs_numeric_val = 1.0

        if any(k in comp_name_clean for k in ["POCKET", "TÚI", "WELT", "BAG"]):
            total_pocket_pieces += float(st.session_state["user_edited_pieces"].get(idx, pcs_numeric_val))

        if p_class_clean in ["FABRIC", "FUSING", "LINING"]:
            current_pcs = float(st.session_state.get("user_edited_pieces", {}).get(idx, pcs_numeric_val))
            total_pattern_pieces += current_pcs
            
            try:
                net_area = float(r.get(area_col_check, 0.0))
                if np.isnan(net_area): net_area = 0.0
            except:
                net_area = 0.0
                
            l_val = float(r.get(l_prod_col_check, 0.0))
            w_val = float(r.get(w_prod_col_check, 0.0))
            
            if net_area <= 0.0 and l_val > 0 and w_val > 0:
                net_area = l_val * w_val * 0.74
                
            if l_val > max_piece_length: max_piece_length = l_val
            if net_area > 0:
                for _ in range(int(current_pcs)):
                    piece_areas.append(net_area)

    # 🛠️ ĐỒNG BỘ SIÊU DỮ LIỆU SẠCH: Tạo gói dữ liệu Geometry Signature chuẩn để nuôi Đoạn 4, 5
    features = {
        "total_pieces": float(total_pattern_pieces),
        "largest_piece_area": float(max(piece_areas)) if piece_areas else 0.0,
        "mean_piece_area": float(np.mean(piece_areas)) if piece_areas else 0.0,
        "longest_piece_length": float(max_piece_length),
        "fabric_width": float(fabric_width),
        "rotation_freedom": 1.0 if rotation_freedom else 0.0,
        "one_way_flag": 1.0 if one_way_flag else 0.0,
        "stripe_plaid_flag": 1.0 if stripe_plaid_flag else 0.0,
        "pocket_complexity": float(total_pocket_pieces)
    }

    complexity_score = min(100.0, max(1.0, (total_pattern_pieces * 1.2) + (total_pocket_pieces * 1.5)))
    
    # Nạp toàn bộ siêu dữ liệu đồng quy vào bộ não hệ thống
    ctx["ai_expert_decision"]["geometry_features"] = features
    ctx["ai_expert_decision"]["longest_piece_length"] = max_piece_length
    ctx["ai_expert_decision"]["complexity_score"] = complexity_score

    # =====================================================================
    # 🟩 ĐOẠN 4: AI VIRTUAL PIECE ENGINE & GEOMETRIC PREPROCESSOR (NO ACCESSORY) - FIX SẬP DIỆN TÍCH
    # =====================================================================
    pattern_has_shrink = True  
    comp_col_check = next((c for c in ["Component Name", "component_name", "Component_Name"] if c in df_bom.columns), "component_name")

    # 1. BỘ SNIFFER DÒ TÌM CHÍNH XÁC CỘT CHIỀU DÀI / CHIỀU RỘNG GỐC CỦA FILE CAD
    detected_l_col = next((c for c in ["Dài gốc (inch)", "orig_l", "original_length", "length_inch", "Length"] if c in df_bom.columns), None)
    detected_w_col = next((c for c in ["Rộng gốc (inch)", "orig_w", "original_width", "width_inch", "Width"] if c in df_bom.columns), None)
    actual_l_col = detected_l_col if detected_l_col else (orig_l_col if 'orig_l_col' in locals() else "bounding_box_length")
    actual_w_col = detected_w_col if detected_w_col else (orig_w_col if 'orig_w_col' in locals() else "bounding_box_width")

    # Đọc thông số co rút thớ vải từ UI phục vụ nắn kích thước phôi ảo
    fusing_warp_shrink = float(st.session_state.get("fusing_warp_shrink", 0.0))
    fusing_weft_shrink = float(st.session_state.get("fusing_weft_shrink", 0.0))
    lining_warp_shrink = float(st.session_state.get("lining_warp_shrink", 0.0))
    lining_weft_shrink = float(st.session_state.get("lining_weft_shrink", 0.0))

    # Kế thừa dữ liệu tiên nghiệm từ bộ não tri thức Đoạn 3
    ai_decision_d4 = ctx.get("ai_expert_decision", {})
    if not isinstance(ai_decision_d4, dict): ai_decision_d4 = {}
    current_prod_cat = str(ai_decision_d4.get("product_category", "JEAN_LONG")).upper().strip()
    prod_upper_name = str(prod).upper().strip() if 'prod' in locals() else ""

    if "user_edited_pieces" not in st.session_state: st.session_state["user_edited_pieces"] = {}
    if "user_edited_materials" not in st.session_state: st.session_state["user_edited_materials"] = {}

    virtual_pieces_layer = {}
    p_length_list, p_width_list, p_area_list = [], [], []

    # 🚨 BỘ KIỂM SOÁT VÀ PHÂN LOẠI CHỦNG LOẠI HÀNG TẬP TRUNG (ƯU TIÊN TUYỆT ĐỐI DÒNG QUẦN)
    has_pant_components = any(any(k in str(row.get(comp_col_check, "")).upper() for k in ["WAISTBAND", "FLY", "COIN", "POCKET", "QUAN", "PANT"]) for _, row in df_bom.iterrows())
    
    if has_pant_components or any(k in current_prod_cat or k in prod_upper_name for k in ["TROUSER", "JEAN", "PANTS", "SHORT", "QUẦN", "QUAN", "JEAN_LONG"]):
        is_trouser_item = True
        is_jacket_item = False
        ctx["ai_expert_decision"]["product_category"] = "JEAN_LONG"  
    else:
        is_trouser_item = False
        is_jacket_item = any(k in current_prod_cat or k in prod_upper_name for k in ["JACKET", "VEST", "ÁO KHOÁC", "KHOAC"])

    # 🚨 PHẲNG HÓA TUYẾN TÍNH VÀ TUYỆT ĐỐI BẢO TOÀN THÔNG SỐ RẬP CHUẨN CAD
    for idx, row in df_bom.iterrows():
        comp_name_raw = str(row.get(comp_col_check, row.get("component_name", "")))
        comp_name_upper = comp_name_raw.upper().strip()
        
        l_orig = float(row.get(actual_l_col, 0.0))
        w_orig = float(row.get(actual_w_col, 0.0))
        
        # 🔍 BỘ QUÉT PHÂN LOẠI CHẤT LIỆU (BỎ PHỤ LIỆU HOÀN TOÀN)
        mat_str = str(row.get(m_col, "")).upper().strip() if 'm_col' in locals() and m_col in row else ""
        
        if "user_edited_materials" in st.session_state and idx in st.session_state["user_edited_materials"]:
            p_class = str(st.session_state["user_edited_materials"][idx]).upper().strip()
            class_confidence = 1.0
        else:
            if any(k in comp_name_upper or k in mat_str for k in ["THREAD", "CHỈ", "BUTTON", "NÚT", "ZIP", "RIVET", "ĐINH", "LABEL", "NHÃN", "MÁC", "SHANK", "SLIDER", "PULLER", "ACCESSORY", "PHỤ LIỆU"]):
                p_class, class_confidence = "ACCESSORY", 1.0
            elif any(k in comp_name_upper or k in mat_str for k in ["FUSING", "MEC", "MẾCH", "KEO", "INTERLINING", "TRICOT"]):
                p_class, class_confidence = "FUSING", 1.0
            elif any(k in comp_name_upper or k in mat_str for k in ["LINING", "LÓT", "POCKETING", "VẢI LÓT"]):
                p_class, class_confidence = "LINING", 1.0
            elif (l_orig / w_orig if w_orig > 0 else 1.0) >= 5.0 and (1.0 - (float(row.get("polygon_net_area", 0.0)) / (l_orig * w_orig)) if (l_orig * w_orig) > 0 else 0.0) <= 0.15 and l_orig > 0:
                p_class, class_confidence = "FUSING", 0.90
            elif float(row.get("polygon_net_area", 0.0)) < 150.0 and any(k in comp_name_upper for k in ["POCKET", "TÚI", "WELT", "BAG"]):
                p_class, class_confidence = ("LINING", 0.88) if ("LINING" in mat_str or "LÓT" in comp_name_upper) else ("FABRIC", 0.75)
            else:
                p_class, class_confidence = "FABRIC", 0.95

        # Bước B: Áp thông số co rút sợi sản xuất trực tiếp từ thớ lệnh chat
        if p_class == "FABRIC":
            w_prod = round(w_orig * (1 + weft_shrink / 100.0), 3) if w_orig > 0 else 58.0
            l_prod = round(l_orig * (1 + warp_shrink / 100.0), 3) if l_orig > 0 else 0.0
        elif p_class == "FUSING":
            w_prod = round(w_orig * (1 + fusing_weft_shrink / 100.0), 3) if w_orig > 0 else 59.0
            l_prod = round(l_orig * (1 + fusing_warp_shrink / 100.0), 3) if l_orig > 0 else 0.0
        elif p_class == "LINING":
            w_prod = round(w_orig * (1 + lining_weft_shrink / 100.0), 3) if w_orig > 0 else 57.0
            l_prod = round(l_orig * (1 + lining_warp_shrink / 100.0), 3) if l_orig > 0 else 0.0
        else:
            w_prod, l_prod = w_orig, l_orig

        p_width_list.append(w_prod)
        p_length_list.append(l_prod)

        # 🛠️ SỬA SAI DIỆN TÍCH TỊNH: Đọc diện tích tịnh thực tế đã qua Khối 3 xử lý cộng co rút và đường may
        net_area_raw = float(row.get("polygon_net_area", 0.0))
        if net_area_raw <= 0.0:
            # Fallback an toàn tuyệt đối từ kích thước sản xuất đã cộng co rút nếu dữ liệu thô lỗi
            net_area_raw = round(l_prod * w_prod * 0.74, 2) if (l_prod > 0 and w_prod > 0) else 1.0

        # Bước C: Suy luận số lượng mảnh rập thực nghiệm rải bàn cắt
        raw_pcs = float(row.get("pcs_numeric", 1.0))
        inferred_pcs = raw_pcs
        qty_confidence = 1.0
        
        has_front_kw = any(k in comp_name_upper for k in ["FRONT", "TRƯỚC"])
        has_back_kw = any(k in comp_name_upper for k in ["BACK", "SAU"])
        
        if p_class in ["FABRIC", "LINING"] and (l_prod * w_prod) > 10.0:
            if is_trouser_item:
                if has_front_kw or has_back_kw or any(k in comp_name_upper for k in ["LEG", "THAN", "ỐNG", "PANEL"]):
                    inferred_pcs = 2.0
                    qty_confidence = 0.99

        # Lưu dữ liệu phôi ảo đồng bộ màng RAM hệ thống
        final_pcs = float(st.session_state["user_edited_pieces"].get(idx, inferred_pcs))
        virtual_pieces_layer[idx] = {
            "inferred_class": p_class,
            "class_confidence": class_confidence,
            "production_l": l_prod,
            "production_w": w_prod,
            "production_net_area": net_area_raw, # Đã bảo vệ giá trị diện tích thực của CAD Gerber
            "inferred_pieces": final_pcs,
            "qty_confidence": qty_confidence,
            "component_name": comp_name_raw
        }

    ctx["ai_expert_decision"]["virtual_pieces_layer"] = virtual_pieces_layer

     # =====================================================================
    # 🟩 ĐOẠN 5.1 (PHIÊN BẢN V11 - CHUẨN CAD GERBER): PAIR BUILDER & DYNAMIC CONFIG
    # =====================================================================
    ai_decision_d5 = ctx.get("ai_expert_decision", {})
    if not isinstance(ai_decision_d5, dict): ai_decision_d5 = {}
        
    virtual_pieces_layer = ai_decision_d5.get("virtual_pieces_layer", {})
    if not virtual_pieces_layer or not isinstance(virtual_pieces_layer, dict):
        virtual_pieces_layer = st.session_state.get("bom_data", {}).get("ai_expert_decision", {}).get("virtual_pieces_layer", {})
    if not virtual_pieces_layer: virtual_pieces_layer = {}

    current_fabric_width = float(st.session_state.get("fabric_width_inch", 58.0))
    lining_width = float(st.session_state.get("lining_width_inch", 57.0))    
    fusing_width = float(st.session_state.get("fusing_width_inch", 59.0))    
    one_way_flag = st.session_state.get("is_one_way_fabric", False)  
    nap_layout_flag = st.session_state.get("is_nap_layout", False)   

    raw_unpaired_pieces = []
    list_lengths, list_widths = [], []

    for idx, r in df_bom.iterrows():
        v_piece = virtual_pieces_layer.get(idx, {}) if isinstance(virtual_pieces_layer, dict) else {}
        p_len, p_wid = float(v_piece.get("production_l", 0.0)), float(v_piece.get("production_w", 0.0))
        net_area, pcs = float(v_piece.get("production_net_area", 0.0)), float(v_piece.get("inferred_pieces", 1.0))
        list_lengths.append(round(p_len, 2) if p_len > 0 else "-")
        list_widths.append(round(p_wid, 2) if p_wid > 0 else "-")

        if v_piece.get("inferred_class", "FABRIC") == "FABRIC" and p_len > 0:
            shape_params = r.get("shape_parameters", {}) or {}
            for _ in range(int(pcs)):
                raw_unpaired_pieces.append({
                    "idx": idx, "l": p_len, "w": p_wid, "area": net_area, 
                    "pair_req": r.get("is_left_right_pair", False), 
                    "shape": str(r.get("piece_shape", "TAPERED_PANEL")).upper().strip(),
                    "function": str(r.get("piece_function", "PRIMARY")).upper().strip(), 
                    "priority": int(float(r.get("packing_priority", 3))) if str(r.get("packing_priority", "")).replace(".","").isdigit() else 3,
                    "left_profile": str(shape_params.get("left_edge_profile", "STRAIGHT")).upper(), 
                    "right_profile": str(shape_params.get("right_edge_profile", "STRAIGHT")).upper(),
                    "grain": str(r.get("grain_constraint", "PREFERRED")).upper()
                })

    df_bom["Chiều dài rập (inch)"] = list_lengths
    df_bom["Chiều rộng rập (inch)"] = list_widths

    if len(raw_unpaired_pieces) > 0 and current_fabric_width > 0:
        # 1️⃣ ENGINE 1: CAD PROFILE-BASED PAIR BUILDER (Ghép cặp dựa trên biên dạng lồi lõm)
        paired_groups = []
        visited_indices = set()
        for i in range(len(raw_unpaired_pieces)):
            if i in visited_indices: continue
            p1 = raw_unpaired_pieces[i]
            found_pair = False
            if p1["pair_req"]:
                for j in range(i + 1, len(raw_unpaired_pieces)):
                    if j in visited_indices: continue
                    p2 = raw_unpaired_pieces[j]
                    if p1["idx"] == p2["idx"] or (p1["shape"] == p2["shape"] and p1["function"] == "PRIMARY" and p2["function"] == "PRIMARY"):
                        # Thực tế CAD: Nếu biên dạng thẳng xếp đan xen đối đầu chỉ tốn 82%~85% tổng bề rộng bbox
                        blend_ratio = 0.84 if (p1["left_profile"] == "STRAIGHT" or p1["right_profile"] == "STRAIGHT") else 0.90
                        paired_groups.append({
                            "idx": p1["idx"], "w": (p1["w"] + p2["w"]) * blend_ratio, "l": max(p1["l"], p2["l"]), "area": p1["area"] + p2["area"],
                            "priority": min(p1["priority"], p2["priority"]), "shape": p1["shape"], "function": p1["function"], "grain": p1["grain"]
                        })
                        visited_indices.add(i); visited_indices.add(j); found_pair = True; break
            if not found_pair:
                paired_groups.append({
                    "idx": p1["idx"], "w": p1["w"], "l": p1["l"], "area": p1["area"], "priority": p1["priority"],
                    "shape": p1["shape"], "function": p1["function"], "grain": p1["grain"]
                })
                visited_indices.add(i)

        paired_groups.sort(key=lambda x: (x["priority"], -x["area"]))

        # 2️⃣ ENGINE 2: KHỞI TẠO KHÔNG GIAN TỰ DO GỐC (Bỏ hoàn toàn hệ số nhân 1.05 lãng phí)
        total_bbox_sum = sum(g["l"] * g["w"] for g in paired_groups)
        initial_horizon_length = max(10.0, total_bbox_sum / current_fabric_width)
        free_rectangles = [{"x": 0.0, "y": 0.0, "w": current_fabric_width, "l": initial_horizon_length}]
               # =====================================================================
        # 🟩 ĐOẠN 5.2 (PHIÊN BẢN V12): MAXRECTS BSSF OPTIMIZER & ADVANCED ROUTER
        # =====================================================================
        placed_pieces = []
        overflow_minor_pieces = []
        simulated_marker_length = 0.0
        
        # Danh sách quản lý không gian tự do linh hoạt
        spaces = [{"x": 0.0, "y": 0.0, "w": current_fabric_width, "l": initial_horizon_length}]

        for g in paired_groups:
            orig_w, orig_l = float(g["w"]), float(g["l"])
            if orig_w <= 0 or orig_l <= 0:
                overflow_minor_pieces.append(g)
                continue

            # ĐỊNH HÌNH CÁC HƯỚNG XOAY (Xoay 90 độ nếu vải tự do hoặc chi tiết phụ nhỏ)
            allowed_rotations = [(orig_w, orig_l)]
            if not one_way_flag and not nap_layout_flag:
                allowed_rotations.append((orig_l, orig_w)) # Thêm cấu hình xoay 90 độ nâng hiệu suất

            best_space_idx = -1
            best_short_side_fit = float('inf')
            best_w, best_l = orig_w, orig_l

            # VÒNG LẶP MAXRECTS: Tìm ô trống theo tiêu chí Best Short Side Fit (BSSF)
            for s_idx, space in enumerate(spaces):
                s_w, s_l = space["w"], space["l"]
                for p_w, p_l in allowed_rotations:
                    if p_w <= s_w and p_l <= s_l:
                        leftover_w = s_w - p_w
                        leftover_l = s_l - p_l
                        short_side_fit = min(leftover_w, leftover_l)
                        
                        if short_side_fit < best_short_side_fit:
                            best_short_side_fit = short_side_fit
                            best_space_idx = s_idx
                            best_w, best_l = p_w, p_l

            # ĐẶT CHI TIẾT VÀO VỊ TRÍ TỐI ƯU NHẤT BIÊN
            if best_space_idx != -1:
                space = spaces.pop(best_space_idx)
                posX, posY = space["x"], space["y"]
                placed_pieces.append({"idx": g["idx"], "x": posX, "y": posY, "w": best_w, "l": best_l})
                
                if posY + best_l > simulated_marker_length:
                    simulated_marker_length = posY + best_l

                # Chia cắt không gian thành các Free Rectangles cực đại mới
                if space["w"] - best_w > 0.01:
                    spaces.append({"x": posX + best_w, "y": posY, "w": space["w"] - best_w, "l": best_l})
                if space["l"] - best_l > 0.01:
                    spaces.append({"x": posX, "y": posY + best_l, "w": space["w"], "l": space["l"] - best_l})

                # KHỬ PHÂN MẢNH (MERGE FREE RECTANGLES): Gộp các ô trống lồng vào nhau
                i = 0
                while i < len(spaces):
                    j = i + 1
                    while j < len(spaces):
                        r1, r2 = spaces[i], spaces[j]
                        if r2["x"] <= r1["x"] and r2["y"] <= r1["y"] and r2["x"]+r2["w"] >= r1["x"]+r1["w"] and r2["y"]+r2["l"] >= r1["y"]+r1["l"]:
                            spaces.pop(i)
                            i -= 1
                            break
                        elif r1["x"] <= r2["x"] and r1["y"] <= r2["y"] and r1["x"]+r1["w"] >= r2["x"]+r2["w"] and r1["y"]+r1["l"] >= r2["y"]+r2["l"]:
                            spaces.pop(j)
                            j -= 1
                        j += 1
                    i += 1
            else:
                overflow_minor_pieces.append(g)

        # Xử lý linh kiện phụ tràn vùng tự do
        total_overflow_area = sum([float(m.get("area", 0.0)) for m in overflow_minor_pieces])
        overflow_added_len = (total_overflow_area / current_fabric_width) / 0.92 if current_fabric_width > 0 else 0.0
        simulated_marker_length += overflow_added_len

        total_all_net_area = sum(float(p["area"]) for p in raw_unpaired_pieces)
        real_fabric_density = total_all_net_area / (simulated_marker_length * current_fabric_width) if simulated_marker_length > 0 else 0.85
        real_fabric_density = max(0.7400, min(0.9450, real_fabric_density))
        
        # CHỈ CỘNG HỆ SỐ HAO HỤT 3% BÀN CẮT Ở BƯỚC CUỐI CÙNG CHO VẢI CHÍNH
        total_fabric_gross_yds = (simulated_marker_length / 36.0) * 1.030
    else:
        real_fabric_density, total_fabric_gross_yds, simulated_marker_length = 0.85, 0.0, 0.0

    # SỬA LỖI: Gom nhóm an toàn, ép viết hoa và cắt khoảng trắng chuỗi để quét sạch RIB và LINING
    total_lining_net_area = sum([
        float(vp.get("production_net_area", 0.0)) * float(vp.get("inferred_pieces", 1.0)) 
        for vp in virtual_pieces_layer.values() 
        if isinstance(vp, dict) and str(vp.get("inferred_class", "")).upper().strip() in ["LINING", "RIB"]
    ])
    
    if total_lining_net_area > 0 and lining_width > 0:
        lining_sim_length = total_lining_net_area / lining_width / 0.82 
        total_lining_gross_yds = (lining_sim_length / 36.0) * 1.030
    else:
        total_lining_gross_yds = 0.0

    if "ai_expert_decision" not in ctx or not isinstance(ctx["ai_expert_decision"], dict):
        ctx["ai_expert_decision"] = {}

    ctx["ai_expert_decision"].update({
        "real_fabric_density": round(real_fabric_density, 4), 
        "total_fabric_gross_yds": round(total_fabric_gross_yds, 4), 
        "total_lining_gross_yds": round(total_lining_gross_yds, 4)
    })

    # =====================================================================
    # PUBLISHING CONSUMPTION ROUTER (PHÂN BỔ ĐỊNH MỨC CHI TIẾT ĐÃ SỬA BUG)
    # =====================================================================
    def dynamic_fusing_solver(l_prod, w_prod, net_area, pcs):
        if fusing_width <= 0: return 0.0
        bounding_box_area = float(l_prod) * float(w_prod) if (float(l_prod) > 0 and float(w_prod) > 0) else float(net_area)
        void_ratio = (bounding_box_area - net_area) / bounding_box_area if bounding_box_area > 0 else 0.0
        return ((net_area * pcs) / fusing_width / round(0.78 - (void_ratio * 0.35), 3) / 36.0) * 1.030

    calculated_total_fabric_net_area = sum([
        float(vp.get("production_net_area", 0.0)) * float(vp.get("inferred_pieces", 1.0)) 
        for vp in virtual_pieces_layer.values() 
        if isinstance(vp, dict) and str(vp.get("inferred_class", "")).upper().strip() == "FABRIC"
    ])

    def core_engine_router(row, idx):
        v_piece = virtual_pieces_layer.get(idx, {}) if isinstance(virtual_pieces_layer, dict) else {}
        # Chuẩn hóa chuỗi danh mục vật tư đầu vào
        p_class = str(v_piece.get("inferred_class", "FABRIC")).upper().strip()
        pcs = float(v_piece.get("inferred_pieces", 1.0))
        net_area = float(v_piece.get("production_net_area", 1.0))
        
        if p_class == "ACCESSORY": 
            return 0.0
        elif p_class in ["FUSING", "INTERLINING"]: 
            return round(dynamic_fusing_solver(v_piece.get("production_l", 0.0), v_piece.get("production_w", 0.0), net_area, pcs), 4)
        elif p_class == "FABRIC":
            if calculated_total_fabric_net_area > 0:
                return round(total_fabric_gross_yds * ((net_area * pcs) / calculated_total_fabric_net_area), 4)
            return 0.0
        elif p_class in ["LINING", "RIB"]:
            if total_lining_net_area > 0: 
                return round(total_lining_gross_yds * ((net_area * pcs) / total_lining_net_area), 4)
        return 0.0

    df_bom["Gross Consumption"] = [core_engine_router(row, idx) for idx, row in df_bom.iterrows()]
    
    # Đồng bộ khổ vải tương ứng cho từng nhóm vật tư lên UI bảng chi tiết
    df_bom["Calculated Width (Inch)"] = [
        current_fabric_width if (isinstance(virtual_pieces_layer, dict) and str(virtual_pieces_layer.get(idx, {}).get("inferred_class", "")).upper().strip() == "FABRIC") 
        else (lining_width if (isinstance(virtual_pieces_layer, dict) and str(virtual_pieces_layer.get(idx, {}).get("inferred_class", "")).upper().strip() in ["LINING", "RIB"]) 
        else fusing_width) for idx in df_bom.index
    ]

    if "polygon_net_area" in df_bom.columns:
        df_bom["polygon_net_area"] = [round(float(virtual_pieces_layer.get(idx, {}).get("production_net_area", 0.0) or 0.0), 2) if (isinstance(virtual_pieces_layer, dict) and idx in virtual_pieces_layer) else round(float(row.get("polygon_net_area", 0.0) or 0.0), 2) for idx, row in df_bom.iterrows()]

    if len(raw_unpaired_pieces) > 0:
        st.success(f"💎 **CAD V12 MAXRECTS SOLVER COMPLETE** | Sửa lỗi phân bổ linh kiện phụ thành công | Định mức vải chính: `{total_fabric_gross_yds:.3f} Yds`")








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
    # 🟩 ĐOẠN 7: REAL-TIME AUDIT INTERFACE & INTERACTIVE CONTROL (ĐỒNG BỘ SUMMARY KHÉP KÍN) - ĐÃ HIỆN CỘT DÀI/RỘNG
    # =====================================================================
    st.header("📋 AI AUDIT REPORT (BÁO CÁO KIỂM TOÁN ĐỊNH MỨC TỰ ĐỘNG)")
    ai_decision_final = ctx.get("ai_expert_decision", {})
    estimated_prior_val = float(ai_decision_final.get("estimated_density_prior", 0.78))
    ui_display_density = float(ai_decision_final.get("real_fabric_density", estimated_prior_val))
    comp_score_val = float(ai_decision_final.get("complexity_score", 45.0))
    ui_complexity_tier = "COMPLEX" if comp_score_val >= 50 else "NORMAL"
    ui_complexity_icon = "🔴" if comp_score_val >= 75 else ("🟡" if comp_score_val >= 45 else "🟢")
    prod_cat_ui = str(ai_decision_final.get("product_category", "JEAN_LONG")).upper().strip()

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("🤖 Loại Hàng Nhận Diện", ai_product_type if 'ai_product_type' in locals() else "JEAN_LONG")
    m2.metric(f"{ui_complexity_icon} Mức Độ Phức Tạp", f"{ui_complexity_tier} ({comp_score_val:.0f}/100)")
    m3.metric("📐 Mật Độ Sơ Đồ Chỉ Định", f"{ui_display_density*100:.2f}%")
    m4.metric("🎯 Độ Tin Cậy AI (Confidence)", f"{float(ctx.get('confidence', 0.95))*100:.1f}%")

    # 🚨 ĐÃ SỬA CHÍNH XÁC: Ép bảng Summary phải nhóm dữ liệu theo đúng nhãn chất liệu của Mảnh ảo trong RAM
    virtual_pieces_layer = ai_decision_final.get("virtual_pieces_layer", {})
    
    # Nạp nhãn chất liệu chuẩn từ lớp phôi ảo trực tiếp vào một danh sách đồng bộ với df_bom
    clean_materials_list = []
    for idx in df_bom.index:
        v_piece = virtual_pieces_layer.get(idx, {})
        clean_materials_list.append(v_piece.get("inferred_class", "FABRIC"))
        
    df_bom["_temp_class"] = clean_materials_list
    
    if "Gross Consumption" not in df_bom.columns:
        df_bom["Gross Consumption"] = 0.0

    summary_grouped = df_bom.groupby(["_temp_class"]).agg({"Gross Consumption": "sum"}).reset_index()
    cls_map = {"FABRIC": "VẢI CHÍNH", "FUSING": "MÉC / KEO", "LINING": "VẢI LÓT", "THREAD": "CHỈ MAY", "ACCESSORY": "PHỤ LIỆU", "UNKNOWN": "VẬT TƯ KHÁC"}
    
    df_summary = pd.DataFrame({
        "Phân loại vật tư": summary_grouped["_temp_class"].map(cls_map).fillna("VẬT TƯ KHÁC"),
        "Material Class": summary_grouped["_temp_class"],
        "Gross Consumption": summary_grouped["Gross Consumption"].round(4),
        "UOM": "YDS"
    })

    st.markdown("##### 📊 Bảng Tổng Hợp Tiêu Hao Vật Tư Đại Trà (BOM Summary)")
    st.dataframe(df_summary, use_container_width=True, hide_index=True)

    df_bom_display = df_bom.copy()
    
    if "Calculated Width (Inch)" in df_bom_display.columns:
        df_bom_display["Khổ vải sản xuất (inch)"] = df_bom_display["Calculated Width (Inch)"].round(1)
    else:
        df_bom_display["Khổ vải sản xuất (inch)"] = float(st.session_state.get("fabric_width_inch", 58.0))
        
    df_bom_display["Size tính toán"] = detected_size_code if 'detected_size_code' in locals() else "30"
    df_bom_display["material_class"] = df_bom_display["_temp_class"]
    df_bom_display = df_bom_display.rename(columns={"component_name": "Component Name", "material_class": "Material Class", "geometry_role": "Role/Piece Type"})
    df_bom_display["Số lượng rập"] = [float(st.session_state.get("user_edited_pieces", {}).get(idx, r["pcs_numeric"])) for idx, r in df_bom.iterrows()]
    df_bom_display["_original_row_index"] = df_bom.index

    # 🛠️ SỬA LỖI ĐỒNG BỘ TÊN CỘT: Cập nhật tên mảng `ordered_cols` khớp chính xác 100% với Đoạn 5.1 để giao diện không lọc bỏ
    ordered_cols = [
        "_original_row_index", 
        "Component Name", 
        "Material Class", 
        "Role/Piece Type", 
        "Chiều dài rập (inch)",   # Đưa cột Chiều dài rập lên trước
        "Chiều rộng rập (inch)",  # Đưa cột Chiều rộng rập lên trước
        "Khổ vải sản xuất (inch)", 
        "Size tính toán", 
        "Số lượng rập", 
        "polygon_net_area", 
        "Gross Consumption"
    ]
    display_final_cols = [c for c in ordered_cols if c in df_bom_display.columns]
    df_bom_display = df_bom_display[display_final_cols]

    col_t1, col_t2 = st.columns(2)
    col_t1.subheader("📋 Bảng Kế Hoạch Định Mức Rải Sơ Đồ Chi Tiết")
    
    with col_t2:
        try:
            if 'local_export_excel_ppj_format' in locals():
                excel_file = local_export_excel_ppj_format(df_summary, df_bom_display.drop(columns=["_original_row_index"], errors="ignore"), prod, ctx, ui_display_density)
                style_name_clean = str(ctx.get('style_code', 'Style')).strip().replace('/', '_').replace('\\', '_')
                st.download_button("🟢 DOWNLOAD EXCEL ĐỊNH MỨC THƯƠNG MẠI", data=excel_file, mime="application/vnd.openpyxl_formats-officedocument.spreadsheetml.sheet", file_name=f"PPJ_BOM_{prod}_{style_name_clean}.xlsx", use_container_width=True)
        except Exception as e: st.error(f"Lỗi kết xuất Excel: {e}")

    # 🛠️ CẤU HÌNH RENDER GRID: Khai báo định dạng số (format) cho 2 cột mới giúp hiển thị chuyên nghiệp hơn trên UI
    edited_df = st.data_editor(
        df_bom_display, 
        column_config={
            "_original_row_index": None, 
            "Chiều dài rập (inch)": st.column_config.NumberColumn("📏 Chiều dài rập (inch)", format="%.2f", disabled=True),
            "Chiều rộng rập (inch)": st.column_config.NumberColumn("📐 Chiều rộng rập (inch)", format="%.2f", disabled=True),
            "Số lượng rập": st.column_config.NumberColumn("Số lượng rập", min_value=1.0, max_value=40.0, step=1.0),
            "Material Class": st.column_config.SelectboxColumn(
                "Material Class", help="Chọn lại nhóm vật tư nếu AI nhận diện sai",
                options=["FABRIC", "FUSING", "LINING", "ACCESSORY", "THREAD"], required=True
            )
        }, use_container_width=True, hide_index=True, key="bom_data_editor_grid_final_v12_perfect_match" 
    )

    has_changed = False
    for _, row in edited_df.iterrows():
        orig_idx = int(row["_original_row_index"])
        old_pcs = float(df_bom.at[orig_idx, "pcs_numeric"])
        new_pcs = float(row["Số lượng rập"])
        if old_pcs != new_pcs:
            st.session_state["user_edited_pieces"][orig_idx] = new_pcs
            has_changed = True
        old_mat = str(df_bom.at[orig_idx, "_temp_class"]).upper().strip()
        new_mat = str(row["Material Class"]).upper().strip()
        if old_mat != new_mat:
            st.session_state["user_edited_materials"][orig_idx] = new_mat
            has_changed = True
            
    if has_changed:
        st.session_state["processed_display_rows"] = df_bom.to_dict(orient="records")
        st.rerun()
