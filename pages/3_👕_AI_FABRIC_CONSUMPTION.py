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
# 🧠 ĐOẠN A: KHỐI HÀM CACHE AI (PHIÊN BẢN V23) - ĐÃ PHÁ VỠ BẪY CACHE CŨ HOÀN TOÀN
# =====================================================================
@st.cache_data(
    show_spinner=False,
    ttl=3600,  # Khóa chặt bộ nhớ Cache trong 1 tiếng để sửa UI thoải mái không bị tính tiền lần 2
    hash_funcs={bytes: lambda b: hashlib.sha256(b).hexdigest()},
)
def execute_final_gerber_pure_scan(
    pdf_bytes,
    current_query,
    active_width,
    target_size_cmd,
    raw_json_schema,
    prompt_agent_2,
):
    import copy
    import hashlib
    import json
    import re
    import fitz  # PyMuPDF xử lý văn bản và hình ảnh PDF
    import google.generativeai as genai

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

    gemini_inputs = list(image_payloads)
    gemini_inputs.insert(0, f"=== USER CHAT COMMAND ===\n{current_query}\n\n=== TECHPACK TEXT ===\n{full_pdf_raw_text}\n")

    extended_prompt = prompt_agent_2 + """
    CRITICAL MULTI-MATERIAL EXTRACTION RULES:
    - You MUST extract EVERY SINGLE component listed in the document, not just FABRIC.
    - If a component name contains "FUSING", "INTERLINING", "MEX", "DỰNG", "KEO LOT", classify its material_class strictly as "FUSING".
    - If a component name contains "LINING", "POCKET BAG", "LOT TUI", "RIB", "BO GÂN", classify its material_class strictly as "LINING".
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
            
            # Ép kiểu dữ liệu an toàn ban đầu
            try: row["bounding_box_length"] = round(float(row.get("bounding_box_length", 0.0)), 2)
            except: row["bounding_box_length"] = 0.0
            try: row["bounding_box_width"] = round(float(row.get("bounding_box_width", 0.0)), 2)
            except: row["bounding_box_width"] = 0.0
            try: row["polygon_net_area"] = float(row.get("polygon_net_area", 0.0))
            except: row["polygon_net_area"] = 0.0
            try: row["piece_count"] = int(float(row.get("piece_count", 1)))
            except: row["piece_count"] = 1
            
            comp_name = str(row.get("component_name", "")).upper()
            mat_class = str(row.get("material_class", "FABRIC")).upper().strip()
            
            # Sửa lỗi phân loại vật tư nghiêm ngặt cho Keo/Lót/Rib
            if any(k in comp_name for k in ["FUSING", "INTERLINING", "MEX", "DỰNG", "KEO LOT"]):
                mat_class = "FUSING"
            elif any(k in comp_name for k in ["LINING", "POCKET", "LÓT", "RIB", "BO GÂN"]):
                mat_class = "LINING"
            row["material_class"] = mat_class

            # CHUẨN HÓA HÌNH HỌC PHẲNG: Gỡ hoàn toàn bẫy nhân đôi bề rộng của rập vải chính
            if mat_class == "FABRIC" and row["bounding_box_width"] > 16.0:
                row["bounding_box_width"] = round(row["bounding_box_width"] / 2.0, 2)
                row["polygon_net_area"] = row["polygon_net_area"] / 2.0
                row["piece_count"] = int(row["piece_count"] * 2)

            # GEOMETRY GUARD: Khống chế diện tích tinh không cho lấn át diện tích hộp bao phẳng
            bbox_area = row["bounding_box_length"] * row["bounding_box_width"]
            if row["polygon_net_area"] > bbox_area and bbox_area > 0:
                row["polygon_net_area"] = bbox_area * (0.76 if mat_class == "FABRIC" else 0.85)

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
# 🟩 ĐOẠN 2 (PHIÊN BẢN V23 - CHUẨN ĐỒNG BỘ): SCHEMAS, PROMPTS & AI EXECUTE
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
                # 1. JSON SCHEMA GIỚI HẠN CHẶN CỨNG CHỦNG LOẠI VẬT TƯ ĐÃ ĐỒNG BỘ THUẬT NGỮ
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
                                    "material_zone": {"type": "STRING", "enum": ["SELF", "LINING", "FUSING", "RIB", "CONTRAST"]},
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
                
                # 2. PROMPT CHỈ THỊ CHẶN LỖI PHÌNH TO BỀ RỘNG RẬP ĐƠN VÀ LỌC PHỤ LIỆU
                prompt_agent_2 = f"""
                You are a senior Industrial Garment IE & CAD Pattern Engineering Intelligence. Reconstruct the multi-layered CAD metadata for EVERY valid fabric/fusing piece in the Techpack for Size {target_size}.
                
                🚨 CRITICAL ACCESSORY OMISSION MANDATE (LỆNH KHỬ TRỪ PHỤ LIỆU):
                - NEVER extract buttons, sewing threads, zippers, sliders, rivets, main labels, care labels, size tabs, hangtags, polybags, or any metal/plastic accessories.
                - IGNORE them completely. They do NOT have marker dimensions or 2D polygon packing footprints.
                - ONLY extract components belonging to: SELF (Vải chính), LINING (Vải lót), FUSING (Mếch/Keo/Fusing), RIB (Bo), or CONTRAST (Vải phối).
                
                🚨 CRITICAL SINGLE PIECE DIMENSION RULE (LUẬT RẬP ĐƠN CAD):
                - 'bounding_box_width' MUST represent the width of ONE SINGLE physical piece (e.g., around 11-14 inches for a single front/back panel of long pants).
                - NEVER combine or double the width of left and right symmetric panels into a single row width (Never output 25+ inches for a single panel width).
                
                🚨 SECTION 1: EXTRACT BOUNDING BOX (ANTI-ZERO RULE)
                Extract/estimate exact 'bounding_box_length' and 'bounding_box_width' in INCHES. NEVER output 0.0.
                
                🚨 SECTION 2: CAD GEOMETRIC SHAPE & METADATA
                Map each valid component to:
                - 'piece_shape': RECTANGLE, TRAPEZOID, TAPERED_PANEL, CURVED_PANEL, POCKET, WAISTBAND, COLLAR, SLEEVE, GUSSET.
                - 'piece_function': PRIMARY, SECONDARY, REINFORCEMENT, DECORATIVE, LINING.
                - 'fold_type': NONE, CENTER_FOLD, EDGE_FOLD, ON_FOLD.
                - 'material_zone': SELF, LINING, FUSING, RIB, CONTRAST.
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

                # 3. GỌI HÀM QUÉT AI CACHE MỚI ĐÃ SỬA ĐỒNG BỘ TÊN HÀM V23
                bom_data = execute_final_gerber_pure_scan(
                    pdf_bytes=active_pdf, current_query=current_query,
                    active_width=dynamic_width, target_size_cmd=target_size,
                    raw_json_schema=raw_json_schema, prompt_agent_2=prompt_agent_2
                )
                
                st.session_state["bom_data"] = bom_data
                st.session_state.ai_processing = False 
                
            except Exception as e:
                st.error(f"❌ Lỗi xử lý trích xuất dữ liệu rập từ Gemini: {str(e)}")
                st.session_state.ai_processing = False




def initialize_and_sync_parameters():
    """Khối 1 (PHIÊN BẢN V21 - MASTER CONTROLLER): Đồng bộ thông số, chống bẫy ghi đè Cache AI"""
    if not (st.session_state.get("bom_data") or st.session_state.get("accumulated_bom_rows")):
        return None, None
        
    bom_source = st.session_state.get("bom_data", {})
    
    # 1. Trích xuất văn bản từ ô chat câu lệnh người dùng
    user_query_text = ""
    if st.session_state.get("last_submitted_query"): 
        user_query_text = str(st.session_state.get("last_submitted_query")).strip()
    
    # 2. Thiết lập thông số mặc định chuẩn từ tầng nhớ gốc
    fabric_width = float(bom_source.get("fabric_width_inch", 58.0))
    warp_shrinkage = float(bom_source.get("warp_shrinkage_percent", 0.0))
    weft_shrinkage = float(bom_source.get("weft_shrinkage_percent", 0.0))
    
    # Đồng bộ Size: Ưu tiên lấy từ cấu hình động tầng ngoài để tránh bị Cache AI đè
    detected_size = st.session_state.get("current_active_size", bom_source.get("detected_base_size", bom_source.get("calculated_on_size", "32")))
    target_size = str(detected_size).upper().strip()
    if not target_size: 
        target_size = "32"

    # 3. Quét thông số ép buộc từ chat bằng Regex nghiêm ngặt
    if user_query_text:
        w_match = re.search(r"\b(khổ\s*vải|khổ)\s*[:=]?\s*(\d+(\.\d+)?)\b", user_query_text, re.IGNORECASE)
        if w_match: 
            fabric_width = float(w_match.group(2))
        
        warp_match = re.search(r"\b(co\s*rút\s*dọc|độ\s*co\s*dọc)\s*[:=]?\s*(\d+(\.\d+)?)\b", user_query_text, re.IGNORECASE)
        if warp_match: 
            val = float(warp_match.group(2))
            if val < 15.0: warp_shrinkage = val 
        
        weft_match = re.search(r"\b(co\s*rút\s*ngang|độ\s*co\s*ngang)\s*[:=]?\s*(\d+(\.\d+)?)\b", user_query_text, re.IGNORECASE)
        if weft_match: 
            val = float(weft_match.group(2))
            if val < 15.0: weft_shrinkage = val

        size_match = re.search(r"\b(cỡ|size)\s*[:=]?\s*([a-zA-Z0-9]+)\b", user_query_text, re.IGNORECASE)
        if size_match: 
            target_size = str(size_match.group(2)).upper().strip()

    # 4. GHI ĐÈ ĐỒNG BỘ LÊN TẦNG NGOÀI (Bảo vệ tham số không bị bộ nhớ đệm AI xóa mất)
    st.session_state["current_active_width"] = fabric_width
    st.session_state["current_active_size"] = target_size
    st.session_state["current_warp_shrinkage"] = warp_shrinkage
    st.session_state["current_weft_shrinkage"] = weft_shrinkage

    # Duy trì cấu trúc dữ liệu cũ bên trong bom_data để đảm bảo không gãy logic các hàm phụ
    bom_source["fabric_width_inch"] = fabric_width
    bom_source["usable_width_inch"] = fabric_width  
    bom_source["warp_shrinkage_percent"] = warp_shrinkage
    bom_source["weft_shrinkage_percent"] = weft_shrinkage
    bom_source["calculated_on_size"] = target_size
    
    st.session_state["bom_data"] = bom_source
    return bom_source, user_query_text

import re
import streamlit as st

def extract_cutting_instructions_from_pdf(component_name, raw_pdf_text, current_inferred_pcs=1.0):
    """
    Thuật toán quét Callout Văn bản PDF (PHIÊN BẢN V22 - CHỐNG BẪY NHÂN ĐÔI ĐỊNH MỨC CHI TIẾT)
    Tự động phân tích lệnh kỹ thuật chuẩn CAD công nghiệp, đồng bộ với số lượng gốc của hệ thống.
    """
    if not raw_pdf_text:
        return {"layer_multiplier": 1, "is_paired": False, "calc_log": "Không tìm thấy dữ liệu văn bản thô PDF."}
        
    # Chuẩn hóa chuỗi văn bản để làm sạch khoảng trắng rác
    text_clean = " ".join(str(raw_pdf_text).lower().split())
    comp_clean = str(component_name).lower().strip()
    
    # Khai báo cấu trúc tham chiếu an toàn ban đầu
    layer_multiplier = 1
    is_paired = False
    calc_log = "AI đọc văn bản PDF: Đồng bộ trực tiếp theo kích thước phôi đơn của Techpack."
    
    # Đưa biến số lượng gốc về kiểu số nguyên để kiểm tra an toàn
    base_pcs = int(float(current_inferred_pcs or 1.0))
    
    # 1. Thuật toán quét vùng lân cận mở rộng (Mở rộng phạm vi lùi về trước 120 ký tự để bắt trọn Callout cột trước)
    match_index = text_clean.find(comp_clean)
    if match_index != -1:
        window_start = max(0, match_index - 120)
        window_end = min(len(text_clean), match_index + 120)
        scan_window = text_clean[window_start:window_end]
        
        # ➔ A. Quét lệnh số lượng cắt vật lý trực tiếp (Ví dụ: CUT 2, CẮT 2, SELF X2, SHELL=2)
        cut_match = re.search(r'\b(cut|cắt|self|shell|qty)\s*(x\s*|\s*|\s*[:=]\s*)(\d+)\b', scan_window)
        if cut_match:
            detected_qty = int(cut_match.group(3))
            # CHỐNG GỘP KÉP: Chỉ cập nhật nếu số lượng nhận diện được lớn hơn dữ liệu nền hiện tại
            if detected_qty > base_pcs:
                layer_multiplier = max(1, detected_qty // base_pcs)
                calc_log = f"Trích xuất Callout PDF: Phát hiện lệnh cắt tổng {detected_qty} chi tiết (Đã chuẩn hóa)."
            else:
                layer_multiplier = 1
                calc_log = f"Trích xuất Callout PDF: Khớp lệnh cắt gốc {detected_qty} chi tiết. Khóa hệ số chống nhân đôi định mức ảo."
            
        # ➔ B. Quét lệnh đối xứng / cặp đôi (PAIR, MIRROR, X2, TRÁI PHẢI)
        if any(k in scan_window for k in ["pair", "cặp", "đối", "mirror", "đối xứng", "left/right", "trái/phải", "1l+1r"]):
            is_paired = True
            # CHỈ NHÂN ĐÔI NẾU SỐ LƯỢNG GỐC TRONG TECHPACK BỊ THIẾU (BẰNG 1)
            if base_pcs == 1 and layer_multiplier == 1:
                layer_multiplier = 2
                calc_log = "Trích xuất Callout PDF: Phát hiện kết cấu cặp (PAIR). Kích hoạt bù phôi đối xứng đối với rập đơn."
                
        # ➔ C. Quét lệnh gập đôi vải rải sơ đồ (FOLD, GẬP ĐÔI)
        if any(k in scan_window for k in ["fold", "gập", "gap doi", "gập đôi", "on fold"]):
            # Bản chất gập đôi biên đối với sơ đồ phẳng là gộp chung đường cắt, giữ nguyên multiplier
            calc_log += " | Ghi nhận chi tiết đi biên gập đôi (FOLD)."
            
    return {
        "layer_multiplier": layer_multiplier,
        "is_paired": is_paired,
        "calc_log": calc_log
    }



import numpy as np
import re
import streamlit as st

def calculate_skyline_2d_metrics(bom_rows_list, user_query_text):
    """
    Khối 2b Siêu Cấp (PHIÊN BẢN V23 - CHUẨN GERBER ENGINE): Mô phỏng toán học phi tuyến tính.
    ĐÃ SỬA: Đảo ngược đồ thị hàm phạt Logistic và trung hòa hệ số hao hụt kép để ép định mức về đúng thực tế.
    """
    ctx = classify_pieces_and_products(bom_rows_list, user_query_text)
    if not ctx or not ctx.get("stable_bom_list"):
        return {"product_segmented": "GENERIC_TOP", "fabric_pattern": "SOLID", "actual_packing_density": 0.85, "global_gross_fabric_yds": 1.65, "major_shape_area": 0.0}

    fabric_pattern = ctx["fabric_pattern"]
    fabric_width = ctx["fabric_width"]
    stable_bom = ctx["stable_bom_list"]

    # =====================================================================
    # 1. ĐỌC DỮ LIỆU VÀ LÀM SẠCH KÍCH THƯỚC ĐƠN CHỐNG PHÌNH RẬP
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
        
        # HOTFIX HÌNH HỌC PHẲNG: Nếu rập bị phình to >16" do dữ liệu thô, tự động đưa về kích thước đơn
        p_c_check = str(r.get("material_class", "FABRIC")).upper().strip()
        if p_c_check == "FABRIC" and w_inch > 16.0:
            w_inch = w_inch / 2.0
            pcs = pcs * 2.0

        bbox_a = l_inch * w_inch
        net_a = float(r.get("polygon_net_area", 0.0))
        
        # Geometry Guard chống lỗi diện tích tinh lấn át hộp bao hình chữ nhật
        if net_a > bbox_a and bbox_a > 0:
            net_a = bbox_area * 0.76
        if net_a <= 0:
            net_a = bbox_a * 0.74 
            
        total_net_area += net_a * pcs
        total_bbox_area += bbox_a * pcs
        total_piece_count += pcs
        
        for _ in range(int(pcs)):
            all_expanded_pieces.append({
                "net_area": net_a, "bbox_area": bbox_a, "length": l_inch, "width": w_inch
            })

    # =====================================================================
    # 2. TRÍCH XUẤT ĐẶC TRƯNG HÌNH HỌC PHI TUYẾN TÍNH CHUẨN ĐỒ THỊ GERBER
    # =====================================================================
    major_threshold_area = total_net_area * 0.08 if total_net_area > 0 else 50.0
    major_pieces_list = [p for p in all_expanded_pieces if p["net_area"] > major_threshold_area]
    minor_pieces_list = [p for p in all_expanded_pieces if p["net_area"] <= major_threshold_area]
    
    fragmentation_ratio = len(minor_pieces_list) / total_piece_count if total_piece_count > 0 else 0.20
    bounding_box_fill = total_net_area / total_bbox_area if total_bbox_area > 0 else 0.72

    if major_pieces_list:
        avg_aspect_ratio = sum(max(p["length"], p["width"]) / max(min(p["length"], p["width"]), 0.1) for p in major_pieces_list) / len(major_pieces_list)
        avg_major_width = sum(p["width"] for p in major_pieces_list) / len(major_pieces_list)
        width_occupancy_ratio = avg_major_width / fabric_width
    else:
        avg_aspect_ratio = 1.8
        width_occupancy_ratio = 0.25

    convexity_score = bounding_box_fill  
    rotation_freedom_factor = 0.97 if "one-way" in str(user_query_text).lower() else 1.0
    compactness_score = max(min(1.0 - (abs(avg_aspect_ratio - 1.0) * 0.03), 1.0), 0.70)
    
    minor_area_sum = sum(p["net_area"] for p in minor_pieces_list)
    small_piece_ratio = minor_area_sum / total_net_area if total_net_area > 0 else 0.15
    marker_fragmentation = total_piece_count / (total_net_area / 100.0) if total_net_area > 0 else 1.0
    edge_irregularity = 1.0 - convexity_score

    # ĐÃ SỬA ĐỒ THỊ LOGISTIC CHUẨN: Chi tiết chiếm khổ vải nhỏ (<28%) được thưởng mật độ, chi tiết quá to (>40%) mới bị phạt
    logistic_midpoint = 0.38
    logistic_k = 12.0  
    # Đổi dấu phạt thành hàm điều hướng tăng trưởng mật độ nền tự nhiên
    width_penalty_logistic = 0.05 / (1.0 + np.exp(-logistic_k * (width_occupancy_ratio - logistic_midpoint)))

    # =====================================================================
    # 3. TÍNH TOÁN MẬT ĐỘ NÈN ĐỘNG CHUẨN CƠ ĐỒNG BỘ
    # =====================================================================
    calculated_density = 0.72 + (bounding_box_fill * 0.14) + (compactness_score * 0.04)
    nesting_efficiency_bonus = (small_piece_ratio * 0.04) + (fragmentation_ratio * 0.02)
    actual_packing_density = (calculated_density + nesting_efficiency_bonus - width_penalty_logistic) * rotation_freedom_factor
    actual_packing_density = max(min(actual_packing_density, 0.9450), 0.7600) # Nâng giới hạn sàn hiệu suất mô phỏng lên 76%

    # =====================================================================
    # 4. CHIỀU DÀI SƠ ĐỒ VÀ TRUNG HÒA HAO HỤT BÀN CẮT (LOẠI BỎ PHẠT TRÙNG)
    # =====================================================================
    if total_net_area <= 0:
        total_net_area = ctx.get("major_shape_area", 0.0) + ctx.get("minor_shape_area", 0.0)
        
    simulated_length = (total_net_area / fabric_width) / actual_packing_density
    simulated_length *= (1.0 + (edge_irregularity * 0.02))

    # Tối ưu lại đường cong hao hụt, khống chế biên độ dạt đầu khúc thương mại
    length_logistic_mid = 45.0  
    length_k = -0.05
    wastage_curve_factor = 0.005 + (0.04 / (1.0 + np.exp(-length_k * (simulated_length - length_logistic_mid))))
    fabric_wastage_multiplier = 1.010 + wastage_curve_factor
    
    # Quy đổi chiều dài sơ đồ ra Yards (Bỏ bớt dạt khúc inch lặp hai lần để tránh bug tăng định mức)
    global_gross_fabric = (simulated_length / 36.0) * fabric_wastage_multiplier

    # =====================================================================
    # 5. XỬ LÝ CHU KỲ VÂN VẢI ĐỘNG (NAP / PLAID)
    # =====================================================================
    fabric_repeat_inch = float(ctx.get("fabric_repeat_inch", 4.0)) 

    if fabric_pattern == "NAP":
        global_gross_fabric += (fabric_repeat_inch * 0.15 * (1.0 - small_piece_ratio)) / 36.0
    elif fabric_pattern in ["PLAID", "STRIPE"]:
        plaid_loss_ratio = (fabric_repeat_inch * 0.85) / simulated_length if simulated_length > 0 else 0.03
        global_gross_fabric *= (1.0 + min(plaid_loss_ratio, 0.15))

    # Ép định mức sàn thực tế cho dòng hàng Jacket phòng vệ rập trống chi tiết
    if "JACKET" in str(ctx.get("product_type", "")).upper() and global_gross_fabric < 1.2:
        global_gross_fabric = 2.15

    major_area_sum = sum(p["net_area"] for p in major_pieces_list) if major_pieces_list else total_net_area

    return {
        "product_segmented": ctx.get("product_type", "JEAN_LONG"), 
        "fabric_pattern": fabric_pattern,
        "actual_packing_density": actual_packing_density, 
        "global_gross_fabric_yds": global_gross_fabric,
        "major_shape_area": major_area_sum  
    }



import re
import streamlit as st

def extract_cutting_instructions_from_pdf(component_name, raw_pdf_text, current_inferred_pcs=1.0):
    """
    Thuật toán quét Callout văn bản PDF (PHIÊN BẢN V24 - ANTI-DOUBLE MULTIPLIER)
    Tự động phân tích các lệnh kỹ thuật (CUT 2, PAIR, SELF, FUSE, MIRROR, FOLD).
    ĐÃ SỬA: Thu hẹp màng quét để cô lập dòng, khóa chặt bộ nhân đôi nếu số lượng gốc đã đủ để tránh lỗi tăng ĐM ảo.
    """
    if not raw_pdf_text:
        return {"layer_multiplier": 1, "is_paired": False, "calc_log": "CAD Fallback: Không tìm thấy dữ liệu văn bản thô PDF."}
        
    # Chuẩn hóa chuỗi văn bản để làm sạch khoảng trắng rác
    text_clean = " ".join(str(raw_pdf_text).lower().split())
    comp_clean = str(component_name).lower().strip()
    
    # Thiết lập cấu trúc mặc định theo quy chuẩn dệt may
    layer_multiplier = 1
    is_paired = False
    calc_log = "AI Engine: Mặc định đồng bộ trực tiếp theo số lượng phôi gốc từ sơ đồ Techpack."
    
    # Ép biến số lượng gốc về dạng số nguyên để kiểm tra an toàn hình học
    base_pcs = int(float(current_inferred_pcs or 1.0))
    
    # Tìm vị trí xuất hiện của tên chi tiết rập trong file văn bản PDF Techpack
    match_index = text_clean.find(comp_clean)
    if match_index != -1:
        # SỬA LỖI GÔM RÁC: Gom màng quét về trước 80 và sau 120 ký tự để ép chỉ quét trọn vẹn trong một dòng bảng BOM
        window_start = max(0, match_index - 80)
        window_end = min(len(text_clean), match_index + 120)
        scan_window = text_clean[window_start:window_end]
        
        # Regex bắt trọn cấu trúc ghi (CUT 2, CUT=2, SELF X2, PANEL X2, QTY: 2)
        cut_match = re.search(r'(?:cut|cắt|self|shell|\bx\b|\bqty\b)\s*(?:x\s*|\s*|=\s*|[:\s]*|\(-\s*)(\d+)|(?:\s+|\()(\d+)(?:\s*pcs|\s*chi tiết|\))', scan_window)
        
        if cut_match:
            detected_qty_str = cut_match.group(1) or cut_match.group(2)
            if detected_qty_str:
                detected_qty = int(detected_qty_str)
                
                # CHỐNG LỖI NHÂN CHỒNG CHÉO: Chỉ nhân thêm hệ số nếu số lượng phát hiện được lớn hơn số lượng nền
                if detected_qty > base_pcs:
                    layer_multiplier = max(1, detected_qty // base_pcs)
                    calc_log = f"Trích xuất Callout PDF: Tìm thấy lệnh cắt tổng {detected_qty} chi tiết (Đã chuẩn hóa hệ số)."
                else:
                    layer_multiplier = 1
                    calc_log = f"Trích xuất Callout PDF: Lệnh cắt {detected_qty} chi tiết trùng khớp dữ liệu nền. Khóa chống nhân đôi."
            
        # ➔ B. Quét lệnh đối xứng / cặp đôi (PAIR, MIRROR, X2)
        if any(k in scan_window for k in ["pair", "cặp", "đối", "mirror", "đối xứng", "1 pair"]):
            is_paired = True
            # CHỈ ĐƯỢC PHÉP BÙ PHÔI ĐỐI XỨNG (X2) NẾU SỐ LƯỢNG GỐC TRONG TECHPACK ĐANG THIẾU (= 1)
            if base_pcs == 1 and layer_multiplier == 1:
                layer_multiplier = 2
                calc_log = "Trích xuất Callout PDF: Phát hiện kết cấu cặp (PAIR) trên rập đơn. Kích hoạt đối xứng phôi phẳng."
                
        # ➔ C. Quét lệnh gập đôi vải bàn cắt (FOLD, GẬP ĐÔI)
        if any(k in scan_window for k in ["fold", "gập", "gap doi", "gập đôi"]):
            # Sơ đồ phẳng dệt may giữ nguyên số lượng phôi, biên gập đôi chỉ thay đổi đường cắt của Gerber
            calc_log += " | Ghi nhận chi tiết đi biên gập đôi (FOLD)."
            
    return {
        "layer_multiplier": layer_multiplier,
        "is_paired": is_paired,
        "calc_log": calc_log
    }



def process_pieces_layer_and_areas(bom_rows_list, product_segmented, warp_shrinkage, weft_shrinkage):
    """
    Khối 3 hoàn chỉnh (PHIÊN BẢN V25 - GEOMETRIC AREA SOLVER): Chuẩn hóa hình học phẳng dệt may.
    ĐÃ SỬA: Triệt tiêu bẫy cộng biên rập ảo, khóa chống nhân đôi số lượng và đồng bộ nhãn vật tư thương mại.
    """
    total_fabric_piece_area = 0.0
    piece_calculated_data = []
    raw_pdf_context = st.session_state.get("raw_pdf_text_extracted", "")

    for r in bom_rows_list:
        if not r or not isinstance(r, dict): continue
        
        raw_l = safe_float(r.get("bounding_box_length", r.get("Dài (L-inch)", 0.0)))
        raw_w = safe_float(r.get("bounding_box_width", r.get("Rộng (W-inch)", 0.0)))
        
        # Nhận diện chính xác tên chi tiết để phục vụ bộ lọc
        comp_name_raw = str(r.get("component_name", "UNNAMED")).upper().strip()
        piece_shape = str(r.get("piece_shape", "TAPERED_PANEL")).upper().strip()
        piece_function = str(r.get("piece_function", "PRIMARY")).upper().strip()
        fold_type = str(r.get("fold_type", "NONE")).upper().strip()
        mat_zone = str(r.get("material_zone", "SELF")).upper().strip()
        critical_alignment = str(r.get("critical_alignment", "NONE")).upper().strip()
        packing_priority = safe_int(r.get("packing_priority", 3), default=3)
        
        # Nhận diện nhãn lớp vật tư thực tế đổ về từ Schema V20
        if mat_zone in ["SELF", "FABRIC"]: r_material_class = "FABRIC"
        elif mat_zone in ["FUSING", "INTERFACING", "INTERLINING", "MEX"]: r_material_class = "FUSING"
        elif mat_zone in ["LINING", "POCKET", "RIB"]: r_material_class = "LINING"
        else: r_material_class = "FABRIC"

        # HOTFIX KÍCH THƯỚC BỀ RỘNG RẬP ĐƠN CHUẨN CAD
        if r_material_class == "FABRIC" and raw_w > 16.0:
            raw_w = raw_w / 2.0

        # Đọc số lượng phôi gốc từ Techpack
        pcs = safe_int(r.get("original_piece_count", r.get("pcs_numeric", 1)))
        if "original_piece_count" not in r:
            r["original_piece_count"] = pcs
            
        cut_qty_ai = safe_int(r.get("cut_quantity", 1), default=1)
        ai_convex_ratio = safe_float(r.get("convex_fill_ratio", 0.74))
        if ai_convex_ratio <= 0 or ai_convex_ratio > 1.0:
            ai_convex_ratio = 0.74
            
        mirror_piece = r.get("mirror_piece", False)

        if raw_l > 0:
            # 1. Áp thông số co rút dọc và ngang của cây vải nhà máy
            adj_l = raw_l * (1 + safe_float(warp_shrinkage) / 100.0)
            adj_w = raw_w * (1 + safe_float(weft_shrinkage) / 100.0) if raw_w > 0 else raw_w
            
            # HOTFIX KHỐNG CHẾ CHIỀU DÀI RẬP THÂN (Nếu bị kéo giãn lố >46" do lỗi bóc tách cũ)
            if r_material_class == "FABRIC" and adj_l > 46.0 and "PANEL" in comp_name_raw:
                adj_l = adj_l * 0.82

            # 2. CHỐNG BẪY NHÂN ĐÔI SỐ LƯỢNG KÉP: Khóa chặt hệ số nhân nếu dữ liệu nền đã đủ phôi rập
            if cut_qty_ai > pcs:
                layer_multiplier = max(1, cut_qty_ai // pcs)
            else:
                layer_multiplier = 1
                
            if mirror_piece and pcs == 1 and layer_multiplier == 1:
                layer_multiplier = 2

            # 3. Tính toán hệ số phom dáng hình học (Shape Factor) từ Convex Ratio động chuẩn CAD phẳng
            shape_factor = ai_convex_ratio
            if fold_type in ["ON_FOLD", "CENTER_FOLD"]:
                shape_factor *= 0.96
            if critical_alignment in ["STRIPE", "PLAID"]:
                shape_factor += 0.02
                
            if piece_function == "PRIMARY":
                shape_factor = max(0.6400, min(0.8800, shape_factor))
            elif piece_shape == "RECTANGLE":
                shape_factor = 0.98

            # 4. CHUẨN HÓA ĐƯỜNG MAY BIÊN RẬP (Bỏ hẳn mốc cộng khống 1.76" lãng phí cho các chi tiết đã ra rập thành phẩm)
            # Chỉ bù hao hụt biên cắt cực nhỏ 0.15 inch chu vi nếu cần thiết
            seamed_l = adj_l + 0.15
            seamed_w = adj_w + 0.15 if raw_w > 0 else adj_w
            
            total_pcs_final = pcs * layer_multiplier
            
            # GEOMETRY GUARD: Chặn đứng hiện tượng diện tích tinh lấn át hộp bao phẳng
            bbox_area = seamed_l * seamed_w
            calculated_net_area = bbox_area * shape_factor
            if calculated_net_area > bbox_area:
                calculated_net_area = bbox_area * 0.76
                
            item_area = calculated_net_area * total_pcs_final
            
            # Đồng bộ dữ liệu sạch hoàn toàn vào DataFrame của hệ thống
            r["material_class"] = r_material_class
            if r_material_class == "FABRIC": 
                total_fabric_piece_area += item_area
            
            r["production_length"] = adj_l
            r["production_width"] = adj_w
            r["piece_count"] = total_pcs_final
            r["Số lượng rập"] = total_pcs_final
            r["polygon_net_area"] = round(calculated_net_area, 2)
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
    """
    Khối 4 hoàn chỉnh (PHIÊN BẢN V26 - GERBER ALLOCATION ENGINE): Phân bổ định mức thương mại.
    ĐÃ SỬA: Chuẩn hóa ma trận trọng số (Re-normalization) chống lọt ĐM và đồng bộ hóa độc lập Keo/Lót/Rib.
    """
    base_gross_fabric = skyline_results.get("global_gross_fabric_yds", 0.0)
    if base_gross_fabric == 0.0:
        base_gross_fabric = skyline_results.get("global_gross_fabric_consumption", 0.0)
    if base_gross_fabric == 0.0:
        base_gross_fabric = skyline_results.get("global_gross_fabric", 0.0)
        
    product_segmented = skyline_results.get("product_segmented", "JEAN_LONG")
    actual_packing_density = skyline_results.get("actual_packing_density", 0.85)
    if actual_packing_density <= 0: actual_packing_density = 0.85
    
    bom_source = st.session_state.get("bom_data", {})
    usable_width = bom_source.get("fabric_width_inch", 58.0)
    if not isinstance(usable_width, (int, float)) or usable_width <= 0: usable_width = 58.0
    
    # Đồng bộ khổ vải phụ thời gian thực từ bộ nhớ hệ thống
    lining_width = float(st.session_state.get("lining_width_inch", 57.0))
    fusing_width = float(st.session_state.get("fusing_width_inch", 59.0))
    
    # ➔ BƯỚC 1: THUẬT TOÁN CHUẨN HÓA TRỌNG SỐ (RE-NORMALIZATION) CHO VẢI CHÍNH
    # Quét trước một vòng để tính tổng diện tích sau khi nhân hệ số trọng số ưu tiên
    weighted_area_sum = 0.0
    for item in piece_calculated_data:
        if "row_ref" not in item: continue
        r = item["row_ref"]
        mat_class_raw = str(item["mat_class_raw"]).upper().strip()
        
        if mat_class_raw == "FABRIC":
            packing_priority = safe_int(r.get("packing_priority", 3), default=3)
            # Áp trọng số gánh nền chuẩn dệt may (Rập to gánh nhiều hao hụt biên sơ đồ hơn)
            weight_factor = 1.08 if packing_priority <= 2 else (0.88 if packing_priority >= 4 else 1.00)
            weighted_area_sum += item["item_area"] * weight_factor

    # ➔ BƯỚC 2: TIẾN HÀNH PHÂN BỔ ĐỊNH MỨC CHI TIẾT THEO TRỤC VẬT TƯ
    processed_rows = []

    for item in piece_calculated_data:
        if "row_ref" not in item: continue
        r = item["row_ref"]
        item_area = item["item_area"]
        layer_multiplier = item["layer_multiplier"]
        mat_class_raw = str(item["mat_class_raw"]).upper().strip()
        
        raw_l = r.get("production_length", item.get("raw_l", 0.0))
        pcs = item["pcs_val"]

        # Ép điều kiện so sánh chữ nghiêm ngặt (==) chống lỗi nhận diện nhầm dòng
        if mat_class_raw == "FABRIC":
            packing_priority = safe_int(r.get("packing_priority", 3), default=3)
            if total_fabric_piece_area > 0 and base_gross_fabric > 0 and weighted_area_sum > 0:
                weight_factor = 1.08 if packing_priority <= 2 else (0.88 if packing_priority >= 4 else 1.00)
                # Công thức chuẩn hóa: Trọng số của dòng chia cho Tổng trọng số toàn hệ thống
                share_ratio = (item_area * weight_factor) / weighted_area_sum
                gross_consumption = round(base_gross_fabric * share_ratio, 4)
                calc_chain = f"Gerber Fabric Re-normalized (Priority {packing_priority})"
            else:
                estimated_base = ((item_area / usable_width) / 36.0) / actual_packing_density
                gross_consumption = round(estimated_base * 1.030, 4) # Chỉ cộng hao hụt bàn cắt 3% chuẩn
                calc_chain = f"CAD Geometry Fallback"
                    
        elif mat_class_raw == "LINING":
            # Định mức Lót túi tinh: Tính trực tiếp trên khổ vải lót thực tế + 3% hao hụt dạt khúc công ty
            gross_consumption = round(((item_area / lining_width) / 36.0) * 1.030, 4)
            calc_chain = f"Sơ đồ LINING độc lập (Khổ {lining_width} inch)"
            
        elif mat_class_raw == "FUSING":
            # Định mức Méc keo tinh: Tính trực tiếp trên khổ vải keo thực tế + 3% hao hụt bàn cắt công ty
            gross_consumption = round(((item_area / fusing_width) / 36.0) * 1.030, 4)
            calc_chain = f"Sơ đồ FUSING độc lập (Khổ {fusing_width} inch)"
            
        elif mat_class_raw in ["RIB", "CONTRAST"]:
            # Định mức Vải phối / Phôi bo gân tính theo khổ vải chính chỉ định + 3% hao hụt
            gross_consumption = round(((item_area / usable_width) / 36.0) * 1.030, 4)
            calc_chain = f"Sơ đồ phối {mat_class_raw} độc lập"
        else:
            gross_consumption, calc_chain = 0.0, f"Vật tư phụ mẫu hàng {product_segmented}."

        # Cập nhật kết quả đồng bộ lên DataFrame để đẩy ra bảng UI chi tiết
        r["Gross Consumption"] = gross_consumption
        item["row_ref"]["Gross Consumption"] = gross_consumption
        r["Số lượng rập"] = f"{total_pcs_final if 'total_pcs_final' in locals() else (pcs * layer_multiplier)} Pcs"
        
        processed_rows.append(r)

    # Đồng bộ dữ liệu kiểm toán hệ thống ngược vào session_state để khóa chặt bộ nhớ màn hình hiển thị
    ctx = st.session_state.get("bom_data", {})
    if isinstance(ctx, dict):
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
import hashlib # Bổ sung thư viện băm mã hóa để tránh lỗi NameError hệ thống cache
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

# =====================================================================
# 🟩 ĐOẠN 1 (PHIÊN BẢN V21 - ĐỒNG BỘ TUYỆT ĐỐI MASTER): PARAMS & SIZE SYNC
# =====================================================================
chat_input_text = str(st.session_state.get("last_submitted_query", "")).lower().strip()

def extract_param(pattern, text, session_key, default_val):
    match = re.search(pattern, text)
    if match:
        val = float(match.group(2) if len(match.groups()) >= 2 else match.group(1))
        st.session_state[session_key] = val
        return val
    return float(st.session_state.get(session_key, default_val))

# 1. Bóc tách tỷ lệ co rút vải dọc và ngang từ ô câu lệnh chat
warp_shrink = extract_param(r'(co rút dọc|dọc)\s*[:=-]?\s*(-?\d+\.?\d*)', chat_input_text, "warp_shrinkage", 0.0)
weft_shrink = extract_param(r'(co rút ngang|ngang)\s*[:=-]?\s*(-?\d+\.?\d*)', chat_input_text, "weft_shrinkage", 0.0)

ctx = st.session_state.get("bom_data", {})
if not isinstance(ctx, dict): 
    ctx = {}

# 🛠️ 2. SỬA TẬN GỐC LUỒNG BỐC SIZE: Bóc tách đơn nguyên để gỡ bẫy kẹt size 32
detected_size_code = ""
if ctx.get("detected_base_size") and str(ctx.get("detected_base_size")).strip() != "":
    detected_size_code = str(ctx.get("detected_base_size")).upper().strip()
elif ctx.get("base_size") and str(ctx.get("base_size")).strip() != "":
    detected_size_code = str(ctx.get("base_size")).upper().strip()
elif ctx.get("calculated_on_size") and str(ctx.get("calculated_on_size")).strip() != "":
    detected_size_code = str(ctx.get("calculated_on_size")).upper().strip()
else:
    # Quét nhanh lệnh đổi size từ chat (Ví dụ: "size 29" hoặc "cỡ 30")
    size_match = re.search(r'\b(size|cỡ)\s*([a-zA-Z0-9]+)\b', chat_input_text)
    if size_match:
         detected_size_code = size_match.group(2).upper().strip()
    else:
         detected_size_code = "32" # Sàn dự phòng cuối cùng

# Giải phóng chuỗi kích thước nhảy size phức tạp (Ví dụ: "32X33" -> lấy eo "32")
if "X" in detected_size_code:
    detected_size_code = detected_size_code.split("X")[0].strip()

# ĐỒNG BỘ LÊN TRỤC BIẾN MASTER NGOÀI VÀ TRONG ĐỂ KHÓA CHẶT BẢNG SIZE ĐOẠN 5.2
st.session_state["current_active_size"] = detected_size_code
st.session_state["target_size"] = detected_size_code
st.session_state["detected_base_size"] = detected_size_code
ctx["calculated_on_size"] = detected_size_code
ctx["detected_base_size"] = detected_size_code

# 🚨 3. ĐỒNG BỘ KHỔ VẢI CHÍNH THỜI GIAN THỰC (Giải phóng lệnh chặn ép khổ vải 55)
fabric_width = extract_param(r'\b(khổ\s*vải|khổ)\s*[:=-]?\s*(\d+(?:\.\d+)?)\b', chat_input_text, "fabric_width_inch", 58.0) 
if fabric_width <= 0: 
    fabric_width = 58.0

# Lưu trữ trọn vẹn lên trục điều khiển Master ngoài để Đoạn 5.1 bóc tách khổ vải động linh hoạt
st.session_state["current_active_width"] = fabric_width
st.session_state["fabric_width_inch"] = fabric_width
ctx["fabric_width_inch"] = fabric_width

# 4. Trích xuất khổ vải Keo và khổ Vải lót độc lập
fusing_width = extract_param(r'\b(khổ\s*keo|keo\s*khổ|khổ\s*dựng)\s*[:=-]?\s*(\d+(?:\.\d+)?)\b', chat_input_text, "fusing_width_inch", 59.0)
if fusing_width <= 0: fusing_width = 59.0
st.session_state["fusing_width_inch"] = fusing_width
ctx["fusing_width_inch"] = fusing_width

lining_width = extract_param(r'\b(khổ\s*lót|lót\s*khổ|vải\s*lót\s*khổ)\s*[:=-]?\s*(\d+(?:\.\d+)?)\b', chat_input_text, "lining_width_inch", 57.0)
if lining_width <= 0: lining_width = 57.0
st.session_state["lining_width_inch"] = lining_width
ctx["lining_width_inch"] = lining_width

# Đồng bộ hệ số co rút lên trục Master để bảo vệ Khối 3
st.session_state["current_warp_shrinkage"] = warp_shrink
st.session_state["current_weft_shrinkage"] = weft_shrink


# =====================================================================
# 🟩 ĐOẠN 2 (PHIÊN BẢN V21 - CHUẨN CAD): DATA CLEANING & PARAMETER SYNC
# =====================================================================
import re
import pandas as pd

rows = ctx.get("bom_rows", [])
if not rows:
    rows = st.session_state.get("processed_display_rows", [])

if rows is not None and (isinstance(rows, list) and len(rows) > 0 or isinstance(rows, pd.DataFrame) and not rows.empty):
    df_bom = pd.DataFrame(rows) if isinstance(rows, list) else rows.copy()
    df_bom = df_bom.loc[:, ~df_bom.columns.duplicated()].copy()
    
    prod = str(ctx.get("detected_product_type", ctx.get("product_segmented", "JEAN_LONG"))).upper().strip()
    fabric_pattern_raw = str(ctx.get("fabric_pattern", "SOLID")).upper()
    
    m_col = next((c for c in ["Material Class", "material_class"] if c in df_bom.columns), "material_class")
    pcs_col = next((c for c in ["Số lượng rập", "piece_count"] if c in df_bom.columns), "piece_count")
    orig_l_col = next((c for c in ["bounding_box_length", "Dài (L-inch)"] if c in df_bom.columns), "bounding_box_length")
    orig_w_col = next((c for c in ["bounding_box_width", "Rộng (W-inch)"] if c in df_bom.columns), "bounding_box_width")
    
    df_bom[orig_l_col] = pd.to_numeric(df_bom[orig_l_col], errors='coerce').fillna(0.0)
    df_bom[orig_w_col] = pd.to_numeric(df_bom[orig_w_col], errors='coerce').fillna(0.0)
    
    # Trích xuất giữ lại cột số liệu gốc sạch trước khi giải toán hình học phẳng
    target_orig_gross_col = next((c for c in ["Gross Consumption", "gross_consumption", "allocated_gross"] if c in df_bom.columns), None)
    if target_orig_gross_col:
        df_bom["original_raw_gross"] = pd.to_numeric(df_bom[target_orig_gross_col], errors='coerce').fillna(0.0)
    else:
        df_bom["original_raw_gross"] = 0.0

    # Khởi tạo bộ đệm lưu trữ chỉnh sửa loại vật liệu và số lượng của người dùng trên lưới UI
    if "user_edited_materials" not in st.session_state:
        st.session_state["user_edited_materials"] = {}
    if "user_edited_pieces" not in st.session_state:
        st.session_state["user_edited_pieces"] = {}

    # Ghi đè loại vật tư nếu người dùng tự thay đổi trên giao diện lưới
    for idx, row in df_bom.iterrows():
        if idx in st.session_state["user_edited_materials"]:
            df_bom.at[idx, m_col] = st.session_state["user_edited_materials"][idx]

    # THUẬT TOÁN ĐỊNH DANH SỐ LƯỢNG RẬP CHUẨN CAD
    def clean_precise_piece_count(row):
        comp_name = str(row.get("component_name", row.get("Component Name", ""))).upper().strip()
        pcs_raw_str = str(row.get(pcs_col, "1"))
        pcs_extracted = re.search(r'(\d+)', pcs_raw_str)
        pcs_val = float(pcs_extracted.group(1)) if pcs_extracted else 1.0
        
        # 🛠️ CHỐNG LỖI NHÂN ĐÔI LŨY TIẾN: Giữ nguyên số lượng rập gốc nguyên bản từ file thô đầu vào
        return pcs_val

    df_bom["pcs_numeric"] = [
        float(st.session_state["user_edited_pieces"][idx]) if idx in st.session_state["user_edited_pieces"]
        else clean_precise_piece_count(row) for idx, row in df_bom.iterrows()
    ]
    df_bom[pcs_col] = df_bom["pcs_numeric"]

    # =====================================================================
    # 🚨 ĐỒNG BỘ TUYỆT ĐỐI THEO TRỤC BIẾN MASTER CỦA ĐOẠN 1 (CHỐNG PHẠT SAI LỆCH)
    # =====================================================================
    # Loại bỏ hoàn toàn Regex quét lại lỏng lẻo ở Đoạn 2 để triệt tiêu lỗi bắt nhầm số rác làm phóng đại rập dài 50"
    
    # Đọc đồng bộ thời gian thực từ các khóa Master an toàn đã được Đoạn 1 xử lý sạch sẽ
    fabric_width = float(st.session_state.get("current_active_width", 58.0))
    warp_shrink = float(st.session_state.get("current_warp_shrinkage", 0.0))
    weft_shrink = float(st.session_state.get("current_weft_shrinkage", 0.0))

    # Khóa chặt lưu trữ đồng nhất trên toàn bộ hệ thống
    st.session_state["fabric_width_inch"] = fabric_width
    st.session_state["warp_shrinkage"] = warp_shrink
    st.session_state["weft_shrinkage"] = weft_shrink
    
    ctx["fabric_width_inch"] = fabric_width
    ctx["warp_shrinkage_percent"] = warp_shrink
    ctx["weft_shrinkage_percent"] = weft_shrink
    # =====================================================================
    # 🟩 ĐOẠN 3.1 (PHIÊN BẢN V21 - CHUẨN ĐỊNH DANH CAD): AI PRODUCT CLASSIFIER
    # =====================================================================
    import pandas as pd

    # 🛠️ TỐI ƯU GERBER THỰC TẾ: Barem mật độ cơ sở an toàn chuẩn phòng sơ đồ dệt thoi/dệt kim
    COMPANY_DENSITY_PRIOR = {
        "SHIRT": 0.82, "JEAN_LONG": 0.795, "SHORT": 0.83, 
        "JACKET": 0.68, "VEST": 0.82, "TOPS_KNIT": 0.78, 
        "SKIRT": 0.82, "DRESS_FLARE": 0.72
    }

    comp_col_check = next((c for c in ["Component Name", "component_name", "Component_Name"] if c in df_bom.columns), "component_name")
    prod_upper_name = str(prod).upper().strip() if 'prod' in locals() else ""
    product_category = None
    
    # 🧠 TẦNG 1: Gom toàn bộ văn bản danh sách linh kiện, loại bỏ ký tự rác để phân tích
    all_components_text = " ".join(df_bom[comp_col_check].astype(str).str.upper().tolist())

    # 🧠 TẦNG 2 (AI QUYẾT ĐỊNH LOẠI HÀNG): Quét từ khóa đặc trưng hình học độc lập
    # Ưu tiên nhận diện dòng quần dài/quần short trước để tránh bẫy overlap từ khóa thân áo
    if any(x in all_components_text for x in ["TROUSER", "LEG", "ĐŨNG", "ĐÁY QUẦN", "JEAN", "PANTS", "QUẦN", "QUAN", "WAISTBAND", "FLY", "CẠP", "LƯNG", "POCKET FACING"]):
        # Kiểm tra thêm từ khóa để phân biệt quần short và quần dài Jeans
        if "SHORT" in prod_upper_name or "SHORT" in all_components_text:
            product_category = "SHORT"
        else:
            product_category = "JEAN_LONG"
        
    elif any(x in all_components_text for x in ["SLEEVE", "COLLAR", "CỔ ÁO", "TAY ÁO", "JACKET", "KHOÁC"]):
        # ĐÃ SỬA: Loại bỏ "BODY PANEL" ra khỏi bộ lọc JACKET để tránh bắt nhầm BODY FRONT/BACK PANEL của quần Jean
        product_category = "JACKET"
        
    # TẦNG 3: Nếu quét linh kiện rập trống, đọc tiêu đề sản phẩm trên Header Techpack
    else:
        for k in COMPANY_DENSITY_PRIOR.keys():
            if k in prod_upper_name or (k == "DRESS_FLARE" and any(d in prod_upper_name for d in ["DRESS", "FLARE", "ĐẦM", "XÒE", "SHIFT", "MAXI"])):
                product_category = k
                break
        
        # Mặc định phòng hộ an toàn cho dòng quần dài đại trà của công ty PPJ Group
        if product_category is None:
            product_category = "JEAN_LONG"

    # 🧠 TẦNG 4: Chuẩn hóa chuỗi hiển thị thân thiện lên giao diện UI báo cáo kiểm toán
    if product_category == "VEST": ai_product_type = "VEST (Áo Vest/Blazer)"
    elif product_category == "JACKET": ai_product_type = "JACKET (Áo khoác Jacket)"
    elif product_category == "DRESS_FLARE": ai_product_type = "DRESS_FLARE (Đầm suông/Thời trang)"
    elif product_category == "SKIRT": ai_product_type = "SKIRT (Chân váy)"
    elif product_category == "TOPS_KNIT": ai_product_type = "TOPS_KNIT (Áo thun/Polo)"
    elif product_category == "SHIRT": ai_product_type = "SHIRT (Áo sơ mi)"
    elif product_category == "SHORT": ai_product_type = "SHORT (Quần short)"
    else: ai_product_type = "JEAN_LONG (Quần dài Jeans/Pants)"
    
    # 🚨 ĐỒNG BỘ TUYỆT ĐỐI VÀO BỘ NHỚ HỆ THỐNG MASTER (CHỐNG LỖI CONTEXT BREAKDOWN)
    if "bom_data" not in st.session_state or not isinstance(st.session_state["bom_data"], dict):
        st.session_state["bom_data"] = {}
        
    ctx = st.session_state["bom_data"]
    if "ai_expert_decision" not in ctx or not isinstance(ctx["ai_expert_decision"], dict): 
        ctx["ai_expert_decision"] = {}
        
    ctx["ai_expert_decision"]["product_category"] = product_category
    ctx["ai_expert_decision"]["product_type_friendly"] = ai_product_type
    ctx["ai_expert_decision"]["estimated_density_prior"] = COMPANY_DENSITY_PRIOR[product_category]
    
    # Đẩy lên trục biến tầng ngoài bảo vệ tham số nền cho Đoạn 5.1 gỡ nghẽn
    st.session_state["current_estimated_density_prior"] = COMPANY_DENSITY_PRIOR[product_category]
    st.session_state["bom_data"] = ctx
    # =====================================================================
    # 🟩 ĐOẠN 3.2 (PHIÊN BẢN V21 - MASTER GEOMETRY Chống Lỗi Kích Thước): GEOMETRIC FEATURE ENGINE
    # =====================================================================
    import numpy as np

    # ĐỒNG BỘ CHUẨN XÁC: Định vị trực tiếp về cột dữ liệu gốc sạch đã được Đoạn 2 chuẩn hóa
    comp_col_check = next((c for c in ["Component Name", "component_name", "Component_Name"] if c in df_bom.columns), "component_name")
    l_prod_col_check = next((c for c in ["bounding_box_length", "Dài (L-inch)"] if c in df_bom.columns), "bounding_box_length")
    w_prod_col_check = next((c for c in ["bounding_box_width", "Rộng (W-inch)"] if c in df_bom.columns), "bounding_box_width")
    area_col_check = next((c for c in ["polygon_net_area", "net_area", "Diện tích (inch²)"] if c in df_bom.columns), "polygon_net_area")
    m_col_check = next((c for c in ["Material Class", "material_class"] if c in df_bom.columns), "material_class")

    # Đọc đồng bộ thời gian thực từ các trục biến Master của Đoạn 1 để chống bẫy kẹt thông số cũ
    fabric_width = float(st.session_state.get("current_active_width", 58.0))
    rotation_freedom = st.session_state.get("allow_rotation_90", True)      
    one_way_flag = st.session_state.get("is_one_way_fabric", False)          
    stripe_plaid_flag = st.session_state.get("is_stripe_plaid", False)       
    fabric_type = st.session_state.get("fabric_material_type", "WOVEN")       

    # Đảm bảo context bom_data luôn tồn tại cấu trúc
    if "bom_data" not in st.session_state or not isinstance(st.session_state["bom_data"], dict):
        st.session_state["bom_data"] = {}
    ctx = st.session_state["bom_data"]
    if "ai_expert_decision" not in ctx or not isinstance(ctx["ai_expert_decision"], dict): 
        ctx["ai_expert_decision"] = {}

    product_category = ctx["ai_expert_decision"].get("product_category", "JEAN_LONG")
    
    if "user_edited_pieces" not in st.session_state: st.session_state["user_edited_pieces"] = {}

    piece_areas = []
    total_pattern_pieces, total_pocket_pieces, max_piece_length = 0.0, 0.0, 0.0

    # 🛠️ BỘ PHÂN LOẠI CHẤT LIỆU LAYER TRÍ THỨC (ĐÃ SỬA: ĐỒNG BỘ CHO CẢ KEO, LÓT VÀ RIB)
    def _d3_internal_material_classify(row, idx, prod_cat):
        if "user_edited_materials" in st.session_state and idx in st.session_state["user_edited_materials"]:
            return str(st.session_state["user_edited_materials"][idx]).upper().strip()
            
        mat_str = str(row[m_col_check]).upper().strip() if m_col_check in row else ""
        comp_str = str(row.get(comp_col_check, row.get("component_name", ""))).upper().strip()
        
        fusing_kws = ["FUSING", "INTERLINING", "INTERFACING", "KEO", "MEC", "MẾCH", "BOND", "ADHESIVE", "LOT KEO", "TRICOT"]
        lining_kws = ["LINING", "LOT", "LÓT", "POCKETING", "MESH", "TAFFETA", "VAI LOT", "VẢI LÓT", "POCKET BAG"]
        rib_kws = ["RIB", "BO GÂN", "BO", "CỔ BO", "TAY BO"]
        
        # Nếu là các chi tiết cạp quần, lưng quần, túi chính -> Ép về Vải chính (SELF) trừ khi có chữ FUSING rõ ràng
        if any(k in comp_str for k in ["WAISTBAND", "LƯNG", "CẠP", "BELT", "POCKET"]) and not any(x in mat_str or x in comp_str for x in fusing_kws + lining_kws):
            return "FABRIC"
            
        if any(k in mat_str or k in comp_str for k in fusing_kws): return "FUSING"
        if any(k in mat_str or k in comp_str for k in lining_kws): return "LINING"
        if any(k in mat_str or k in comp_str for k in rib_kws): return "LINING" # Luồng MaxRects phụ gộp RIB và LINING
        return "FABRIC"

    for idx, r in df_bom.iterrows():
        p_class_clean = _d3_internal_material_classify(r, idx, product_category)
        comp_name_clean = str(r.get(comp_col_check, "")).upper().strip()
        
        mat_clean_str = str(r.get(m_col_check, "")).upper().strip() if m_col_check in r else ""
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
            
            # Khống chế kích thước rập đơn vải chính bị phình to bề rộng
            if p_class_clean == "FABRIC" and w_val > 16.0:
                w_val = w_val / 2.0
                if net_area > 0: net_area = net_area / 2.0
            
            # Hình học Guard: Chống lỗi diện tích tinh lấn át hộp bao hình chữ nhật phẳng
            bbox_area_check = l_val * w_val
            if net_area > bbox_area_check and bbox_area_check > 0:
                net_area = bbox_area_check * (0.76 if p_class_clean == "FABRIC" else 0.85)
            
            if net_area <= 0.0 and l_val > 0 and w_val > 0:
                net_area = l_val * w_val * (0.76 if p_class_clean == "FABRIC" else 0.85)
                
            if l_val > max_piece_length: max_piece_length = l_val
            if net_area > 0:
                for _ in range(int(current_pcs)):
                    piece_areas.append(net_area)

    # 🛠️ ĐỒNG BỘ SIÊU DỮ LIỆU SẠCH: Tạo gói dữ liệu Geometry Signature chuẩn xác
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
    
    # Xuất bản và nạp toàn bộ siêu dữ liệu đồng quy vào bộ não hệ thống Master ngoài
    ctx["ai_expert_decision"]["geometry_features"] = features
    ctx["ai_expert_decision"]["longest_piece_length"] = max_piece_length
    ctx["ai_expert_decision"]["complexity_score"] = complexity_score
    
    st.session_state["current_longest_piece_length"] = max_piece_length
    st.session_state["bom_data"] = ctx
        # =====================================================================
      # =====================================================================
    # 🟩 ĐOẠN 4 (PHIÊN BẢN V24 - KHÓA TỪ KHÓA NGHIÊM NGẶT CHỐNG LỆCH THÔNG SỐ): AI VIRTUAL PIECE ENGINE
    # =====================================================================
    pattern_has_shrink = True  
    comp_col_check = next((c for c in ["Component Name", "component_name", "Component_Name"] if c in df_bom.columns), "component_name")
    m_col_check = next((c for c in ["Material Class", "material_class"] if c in df_bom.columns), "material_class")

    actual_l_col = next((c for c in ["bounding_box_length", "Dài (L-inch)"] if c in df_bom.columns), "bounding_box_length")
    actual_w_col = next((c for c in ["bounding_box_width", "Rộng (W-inch)"] if c in df_bom.columns), "bounding_box_width")

    fabric_width = float(st.session_state.get("current_active_width", 58.0))
    warp_shrink = float(st.session_state.get("current_warp_shrinkage", 0.0))
    weft_shrink = float(st.session_state.get("current_weft_shrinkage", 0.0))

    fusing_warp_shrink = float(st.session_state.get("fusing_warp_shrink", 0.0))
    fusing_weft_shrink = float(st.session_state.get("fusing_weft_shrink", 0.0))
    lining_warp_shrink = float(st.session_state.get("lining_warp_shrink", 0.0))
    lining_weft_shrink = float(st.session_state.get("lining_weft_shrink", 0.0))

    if "bom_data" not in st.session_state or not isinstance(st.session_state["bom_data"], dict):
        st.session_state["bom_data"] = {}
    ctx = st.session_state["bom_data"]
    if "ai_expert_decision" not in ctx or not isinstance(ctx["ai_expert_decision"], dict):
        ctx["ai_expert_decision"] = {}
        
    ai_decision_d4 = ctx["ai_expert_decision"]
    current_prod_cat = str(ai_decision_d4.get("product_category", "JEAN_LONG")).upper().strip()
    prod_upper_name = str(prod).upper().strip() if 'prod' in locals() else ""

    if "user_edited_pieces" not in st.session_state: st.session_state["user_edited_pieces"] = {}
    if "user_edited_materials" not in st.session_state: st.session_state["user_edited_materials"] = {}

    virtual_pieces_layer = {}
    is_trouser_item = (current_prod_cat in ["JEAN_LONG", "SHORT"])

    # Mảng lưu trữ kích thước thực tế của rập chính để nắn cấu trúc
    master_panel_lengths = {"FRONT": 0.0, "BACK": 0.0}

    # 🚨 VÒNG LẶP TIỀN XỬ LÝ VÀ PHÂN LOẠI VẬT TƯ AN TOÀN CHỐNG NHẦM LẪN
    for idx, row in df_bom.iterrows():
        comp_name_raw = str(row.get(comp_col_check, row.get("component_name", "")))
        comp_name_upper = comp_name_raw.upper().strip()
        
        l_orig = float(row.get(actual_l_col, 0.0))
        w_orig = float(row.get(actual_w_col, 0.0))
        net_area_raw = float(row.get("polygon_net_area", 0.0))
        
        mat_str = str(row.get(m_col_check, "")).upper().strip()
        
        if idx in st.session_state["user_edited_materials"]:
            p_class = str(st.session_state["user_edited_materials"][idx]).upper().strip()
            class_confidence = 1.0
        else:
            if any(k in comp_name_upper or k in mat_str for k in ["THREAD", "CHỈ", "BUTTON", "NÚT", "ZIP", "RIVET", "LABEL", "MÁC", "ACCESSORY"]):
                p_class, class_confidence = "ACCESSORY", 1.0
            elif any(k in comp_name_upper or k in mat_str for k in ["FUSING", "MEC", "MẾCH", "KEO", "INTERLINING", "INTERFACING"]):
                p_class, class_confidence = "FUSING", 1.0
            elif any(k in comp_name_upper or k in mat_str for k in ["LINING", "LÓT", "POCKETING", "RIB", "BO GÂN"]):
                p_class, class_confidence = "LINING", 1.0
            else:
                p_class, class_confidence = "FABRIC", 0.95

        # ĐĂC TRỊ LỖI PHÌNH ĐÔ SAU (YOKE) VÀ ĐÁP TÚI (FACING)
        # Khống chế kích thước đô sau (Yoke) và đáp lưng nếu AI đọc nhầm dòng cột làm phình chiều dài
        if "YOKE" in comp_name_upper or "ĐÔ" in comp_name_upper or "ĐÔ SAU" in comp_name_upper:
            if l_orig > 25.0: 
                # Hoán đổi ngược lại kích thước chuẩn của miếng đô quần jean hình thang (~18" x 4.5")
                swap_temp = l_orig
                l_orig = w_orig if w_orig > 0 else 4.5
                w_orig = swap_temp / 4.0 if swap_temp > 0 else 10.26

        # HOTFIX 1: Triệt hạ lỗi phình chiều rộng rập vải chính đơn > 16 inch
        if p_class == "FABRIC" and w_orig > 16.0:
            w_orig = w_orig / 2.0
            if net_area_raw > 0: net_area_raw = net_area_raw / 2.0

        # HOTFIX 2: Khống chế chiều dài trần rập thân quần dài đại trà (Tránh lỗi kéo giãn lố)
        if p_class == "FABRIC" and is_trouser_item and l_orig > 45.0 and "LEG" in comp_name_upper:
            l_orig = 39.5

        # Áp thông số co rút thớ sợi sản xuất trực tiếp từ trục Master
        if p_class == "FABRIC":
            w_prod = round(w_orig * (1 + weft_shrink / 100.0), 3) if w_orig > 0 else fabric_width
            l_prod = round(l_orig * (1 + warp_shrink / 100.0), 3) if l_orig > 0 else 0.0
        elif p_class == "FUSING":
            w_prod = round(w_orig * (1 + fusing_weft_shrink / 100.0), 3) if w_orig > 0 else 59.0
            l_prod = round(l_orig * (1 + fusing_warp_shrink / 100.0), 3) if l_orig > 0 else 0.0
        elif p_class == "LINING":
            w_prod = round(w_orig * (1 + lining_weft_shrink / 100.0), 3) if w_orig > 0 else 57.0
            l_prod = round(l_orig * (1 + lining_warp_shrink / 100.0), 3) if l_orig > 0 else 0.0
        else:
            w_prod, l_prod = w_orig, l_orig

        # 🚨 NGHIÊM NGẶT KHÓA CHẶT TỪ KHÓA THÂN QUẦN CHÍNH XÁC (Chỉ nhận LEG PANEL để tránh lọt rác rập phụ)
        if p_class == "FABRIC" and is_trouser_item and "LEG" in comp_name_upper:
            if "FRONT" in comp_name_upper or "TRƯỚC" in comp_name_upper: 
                master_panel_lengths["FRONT"] = l_prod if l_prod > 20.0 else 38.5
            if "BACK" in comp_name_upper or "SAU" in comp_name_upper: 
                master_panel_lengths["BACK"] = l_prod if l_prod > 20.0 else 40.5

        bbox_area_check = l_prod * w_prod
        if net_area_raw > bbox_area_check and bbox_area_check > 0:
            net_area_raw = bbox_area_check * (0.76 if p_class == "FABRIC" else 0.85)

        if net_area_raw <= 0.0 and l_prod > 0 and w_prod > 0:
            net_area_raw = round(l_prod * w_prod * (0.76 if p_class == "FABRIC" else 0.85), 2)

        raw_pcs = float(row.get("pcs_numeric", 1.0))
        inferred_pcs = raw_pcs
        
        if p_class in ["FABRIC", "LINING"] and (l_prod * w_prod) > 10.0 and is_trouser_item:
            if any(k in comp_name_upper for k in ["LEG", "THAN", "ỐNG", "PANEL"]):
                if raw_pcs == 1.0: inferred_pcs = 2.0

        final_pcs = float(st.session_state["user_edited_pieces"].get(idx, inferred_pcs))
        virtual_pieces_layer[idx] = {
            "inferred_class": p_class, "class_confidence": class_confidence,
            "production_l": l_prod, "production_w": w_prod, "production_net_area": net_area_raw,
            "inferred_pieces": final_pcs, "component_name": comp_name_raw
        }

    # ➔ CAD STRUCTURE V24: Ép khống chế đồng bộ chiều dài thân quần Jeans thực tế thương mại
    # Sửa triệt để lỗi đảo ngược thông số: Thân sau (Back) bắt buộc phải dài hơn Thân trước (Front) từ 1.5 - 2.0"
    if is_trouser_item:
        f_len = master_panel_lengths.get("FRONT", 0.0)
        b_len = master_panel_lengths.get("BACK", 0.0)
        
        # Nếu dữ liệu thô bị gãy làm mất dấu hoặc hoán đổi sai lệch chiều dài thân trước chân không
        if f_len < 20.0 or b_len < 20.0 or f_len >= b_len:
            f_len = 38.8  # Đưa về barem rập chuẩn sản xuất quần jean size 32 mẫu
            b_len = 40.6
            
        for idx, vp in virtual_pieces_layer.items():
            c_name = str(vp.get("component_name", "")).upper()
            if "FABRIC" in vp.get("inferred_class", "") and "LEG" in c_name:
                if "FRONT" in c_name or "TRƯỚC" in c_name:
                    vp["production_l"] = round(f_len, 2)
                    vp["production_net_area"] = round(vp["production_l"] * vp["production_w"] * 0.74, 2)
                if "BACK" in c_name or "SAU" in c_name:
                    vp["production_l"] = round(b_len, 2)
                    vp["production_net_area"] = round(vp["production_l"] * vp["production_w"] * 0.76, 2)

    ctx["ai_expert_decision"]["virtual_pieces_layer"] = virtual_pieces_layer
    st.session_state["bom_data"] = ctx
    # =====================================================================
    # 🟩 ĐOẠN 5.1 (PHIÊN BẢN V28 - ĐỒNG BỘ TỪ KHÓA DIỆN TÍCH TINH): MULTI-MARKER PREPARATION
    # =====================================================================
    import json

    # Kiểm tra ngữ cảnh vùng nhớ an toàn tầng ngoài
    if "bom_data" not in st.session_state or not isinstance(st.session_state["bom_data"], dict):
        st.session_state["bom_data"] = {}
    ctx = st.session_state["bom_data"]
    
    ai_decision_d5 = ctx.get("ai_expert_decision", {})
    if not isinstance(ai_decision_d5, dict): 
        ai_decision_d5 = {}
        
    virtual_pieces_layer = ai_decision_d5.get("virtual_pieces_layer", {})
    if not virtual_pieces_layer or not isinstance(virtual_pieces_layer, dict):
        virtual_pieces_layer = st.session_state.get("bom_data", {}).get("ai_expert_decision", {}).get("virtual_pieces_layer", {})
    if not virtual_pieces_layer: 
        virtual_pieces_layer = {}

    # Đọc tham số Master điều khiển thời gian thực
    current_fabric_width = float(st.session_state.get("current_active_width", 58.0))
    lining_width = float(st.session_state.get("lining_width_inch", 57.0))    
    fusing_width = float(st.session_state.get("fusing_width_inch", 59.0))    
    
    one_way_flag = st.session_state.get("is_one_way_fabric", False)  
    nap_layout_flag = st.session_state.get("is_nap_layout", False)   
    size_scale_ratio = float(st.session_state.get("total_marker_bundle_ratio", 1.0))

    # Khởi tạo 3 hành lang phân rã vật tư độc lập tuyệt đối
    fabric_unpaired_pieces = []
    fusing_unpaired_pieces = []
    lining_unpaired_pieces = []

    list_lengths, list_widths = [], []

    for idx, r in df_bom.iterrows():
        v_piece = virtual_pieces_layer.get(idx, {}) if isinstance(virtual_pieces_layer, dict) else {}
        
        p_len = float(v_piece.get("production_l", 0.0))
        p_wid = float(v_piece.get("production_w", 0.0))
        
        # SỬA LỖI NAME DISCONNECT: Bóc đúng nhãn diện tích tinh của phôi ảo từ RAM Đoạn 4 đổ sang
        net_area = float(v_piece.get("production_net_area", 0.0))
        
        # Nhận số lượng chiếc rập thời gian thực được đồng bộ từ lưới chỉnh sửa UI
        pcs = float(st.session_state.get("user_edited_pieces", {}).get(idx, v_piece.get("inferred_pieces", 1.0)))
        pcs = pcs * size_scale_ratio

        p_class_check = str(v_piece.get("inferred_class", "")).upper().strip()
        if not p_class_check: 
            p_class_check = str(r.get("material_class", "FABRIC")).upper().strip()

        # Bộ lọc bảo vệ phom dáng rập quần Jean đơn nguyên bản chuẩn CAD phẳng
        if p_class_check == "FABRIC" and p_wid > 16.0:
            p_wid = p_wid / 2.0
            net_area = net_area / 2.0
            pcs = pcs * 2.0

        if p_class_check == "FABRIC" and p_len > 46.0 and "PANEL" in str(r.get("component_name", "")).upper():
            p_len = p_len * 0.82
            net_area = net_area * 0.82

        bbox_area = p_len * p_wid
        if net_area <= 0.0 and bbox_area > 0:
            net_area = bbox_area * 0.76

        list_lengths.append(round(p_len, 2) if p_len > 0 else "-")
        list_widths.append(round(p_wid, 2) if p_wid > 0 else "-")

        # Đẩy phôi đơn độc lập vào đúng mảng sơ đồ chỉ định
        if p_len > 0:
            piece_data = {"idx": idx, "l": p_len, "w": p_wid, "area": net_area, "material_class": p_class_check}
            
            if p_class_check == "FABRIC":
                for _ in range(int(pcs)): fabric_unpaired_pieces.append(piece_data)
            elif p_class_check in ["FUSING", "INTERLINING"]:
                for _ in range(int(pcs)): fusing_unpaired_pieces.append(piece_data)
            elif p_class_check in ["LINING", "RIB"]:
                for _ in range(int(pcs)): lining_unpaired_pieces.append(piece_data)

    df_bom["Chiều dài rập (inch)"] = list_lengths
    df_bom["Chiều rộng rập (inch)"] = list_widths
        # =====================================================================
        # 🟩 ĐOẠN 5.2 (PHIÊN BẢN V28 - TÍNH ĐỊNH MỨC ĐỘC LẬP TỪ MẢNG SẠCH)
        # =====================================================================
        total_fabric_gross_yds = 0.0
        total_fusing_gross_yds = 0.0
        total_lining_gross_yds = 0.0
        real_fabric_density = 0.85

        # ➔ ĐỘNG CƠ SƠ ĐỒ 1: Đi sơ đồ độc lập cho VẢI CHÍNH (MaxRects BSSF)
        if len(fabric_unpaired_pieces) > 0 and current_fabric_width > 0:
            f_net_sum = sum(p["l"] * p["w"] for p in fabric_unpaired_pieces)
            f_init_hor = max(20.0, f_net_sum / current_fabric_width)
            f_spaces = [{"x": 0.0, "y": 0.0, "w": current_fabric_width, "l": f_init_hor}]
            f_marker_len = 0.0
            f_placed = 0
            f_sorted = sorted(fabric_unpaired_pieces, key=lambda x: (-x["area"], -x["l"]))

            for g in f_sorted:
                o_w, o_l = float(g["w"]), float(g["l"])
                rotations = [(o_w, o_l)]
                if not one_way_flag and not nap_layout_flag: rotations.append((o_l, o_w))
                b_idx, b_fit = -1, float('inf')
                b_w_f, b_l_f = o_w, o_l

                for s_idx, sp in enumerate(f_spaces):
                    for p_w, p_l in rotations:
                        if p_w <= sp["w"] and p_l <= sp["l"]:
                            fit = min(sp["w"] - p_w, sp["l"] - p_l)
                            if fit < b_fit: b_fit, b_idx, b_w_f, b_l_f = fit, s_idx, p_w, p_l

                if b_idx != -1:
                    space = f_spaces.pop(b_idx)
                    if space["y"] + b_l_f > f_marker_len: f_marker_len = space["y"] + b_l_f
                    if space["w"] - b_w_f > 0.01: f_spaces.append({"x": space["x"] + b_w_f, "y": space["y"], "w": space["w"] - b_w_f, "l": b_l_f})
                    if space["l"] - b_l_f > 0.01: f_spaces.append({"x": space["x"], "y": space["y"] + b_l_f, "w": space["w"], "l": space["l"] - b_l_f})
                    f_placed += 1

            if f_placed < len(f_sorted):
                f_marker_len += (sum(p["area"] for p in f_sorted[f_placed:]) / current_fabric_width) / 0.92
            total_fabric_gross_yds = (f_marker_len / 36.0) * 1.030
            
            f_net_total = sum(p["area"] for p in fabric_unpaired_pieces)
            real_fabric_density = f_net_total / (f_marker_len * current_fabric_width) if f_marker_len > 0 else 0.85
            real_fabric_density = max(0.7800, min(0.9550, real_fabric_density))

        # ➔ ĐỘNG CƠ SƠ ĐỒ 2: Đi sơ đồ độc lập cho MÉC / KEO (MaxRects BSSF)
        if len(fusing_unpaired_pieces) > 0 and fusing_width > 0:
            fu_net_sum = sum(p["l"] * p["w"] for p in fusing_unpaired_pieces)
            fu_init_hor = max(20.0, fu_net_sum / fusing_width)
            fu_spaces = [{"x": 0.0, "y": 0.0, "w": fusing_width, "l": fu_init_hor}]
            fu_marker_len = 0.0
            fu_placed = 0
            fu_sorted = sorted(fusing_unpaired_pieces, key=lambda x: (-x["area"], -x["l"]))

            for g in fu_sorted:
                o_w, o_l = float(g["w"]), float(g["l"])
                rotations = [(o_w, o_l)]
                if not one_way_flag and not nap_layout_flag: rotations.append((o_l, o_w))
                b_idx, b_fit = -1, float('inf')
                b_w_f, b_l_f = o_w, o_l

                for s_idx, sp in enumerate(fu_spaces):
                    for p_w, p_l in rotations:
                        if p_w <= sp["w"] and p_l <= sp["l"]:
                            fit = min(sp["w"] - p_w, sp["l"] - p_l)
                            if fit < b_fit: b_fit, b_idx, b_w_f, b_l_f = fit, s_idx, p_w, p_l

                if b_idx != -1:
                    space = fu_spaces.pop(b_idx)
                    if space["y"] + b_l_f > fu_marker_len: fu_marker_len = space["y"] + b_l_f
                    if space["w"] - b_w_f > 0.01: fu_spaces.append({"x": space["x"] + b_w_f, "y": space["y"], "w": space["w"] - b_w_f, "l": b_w_f})
                    if space["l"] - b_l_f > 0.01: fu_spaces.append({"x": space["x"], "y": space["y"] + b_l_f, "w": space["w"], "l": space["l"] - b_l_f})
                    fu_placed += 1

            if fu_placed < len(fu_sorted):
                fu_marker_len += (sum(p["area"] for p in fu_sorted[fu_placed:]) / fusing_width) / 0.92
            total_fusing_gross_yds = (fu_marker_len / 36.0) * 1.030

        # ➔ ĐỘNG CƠ SƠ ĐỒ 3: Đi sơ đồ độc lập cho VẢI LÓT TÚI (MaxRects BSSF)
        if len(lining_unpaired_pieces) > 0 and lining_width > 0:
            li_net_sum = sum(p["l"] * p["w"] for p in lining_unpaired_pieces)
            li_init_hor = max(20.0, li_net_sum / lining_width)
            li_spaces = [{"x": 0.0, "y": 0.0, "w": lining_width, "l": li_init_hor}]
            li_marker_len = 0.0
            li_placed = 0
            li_sorted = sorted(lining_unpaired_pieces, key=lambda x: (-x["area"], -x["l"]))

            for g in li_sorted:
                o_w, o_l = float(g["w"]), float(g["l"])
                rotations = [(o_w, o_l)]
                if not one_way_flag and not nap_layout_flag: rotations.append((o_l, o_w))
                b_idx, b_fit = -1, float('inf')
                b_w_f, b_l_f = o_w, o_l

                for s_idx, sp in enumerate(li_spaces):
                    for p_w, p_l in rotations:
                        if p_w <= sp["w"] and p_l <= sp["l"]:
                            fit = min(sp["w"] - p_w, sp["l"] - p_l)
                            if fit < b_fit: b_fit, b_idx, b_w_f, b_l_f = fit, s_idx, p_w, p_l

                if b_idx != -1:
                    space = li_spaces.pop(b_idx)
                    if space["y"] + b_l_f > li_marker_len: li_marker_len = space["y"] + b_l_f
                    if space["w"] - b_w_f > 0.01: li_spaces.append({"x": space["x"] + b_w_f, "y": space["y"], "w": space["w"] - b_w_f, "l": b_w_f})
                    if space["l"] - b_l_f > 0.01: li_spaces.append({"x": space["x"], "y": space["y"] + b_l_f, "w": space["w"], "l": space["l"] - b_l_f})
                    li_placed += 1

            if li_placed < len(li_sorted):
                li_marker_len += (sum(p["area"] for p in li_sorted[li_placed:]) / lining_width) / 0.92
            total_lining_gross_yds = (li_marker_len / 36.0) * 1.030

        # Xuất bản dữ liệu kiểm toán lên context hệ thống
        if "ai_expert_decision" not in ctx or not isinstance(ctx["ai_expert_decision"], dict): 
            ctx["ai_expert_decision"] = {}
        ctx["ai_expert_decision"].update({
            "real_fabric_density": round(real_fabric_density, 4), 
            "total_fabric_gross_yds": round(total_fabric_gross_yds, 4), 
            "total_lining_gross_yds": round(total_lining_gross_yds, 4)
        })

        # =====================================================================
        # PUBLISHING CONSUMPTION ROUTER (PHÂN BỔ CHI TIẾT ĐỊNH MỨC BIỆT LẬP CÔ LẬP)
        # =====================================================================
        # Ép đồng bộ lại trường polygon_net_area hiển thị trên bảng UI theo mảng RAM sạch để gỡ nút thắt số 0
        clean_area_display = []
        for idx in df_bom.index:
            v_p = virtual_pieces_layer.get(idx, {})
            clean_area_display.append(float(v_p.get("production_net_area", 0.0)))
        df_bom["polygon_net_area"] = clean_area_display

        total_fabric_net_sum = sum(float(p["area"]) for p in fabric_unpaired_pieces)
        total_fusing_net_sum = sum(p["area"] for p in fusing_unpaired_pieces)
        total_lining_net_sum = sum(p["area"] for p in lining_unpaired_pieces)

        def core_engine_router(idx):
            v_piece = virtual_pieces_layer.get(idx, {}) if isinstance(virtual_pieces_layer, dict) else {}
            p_class = str(v_piece.get("inferred_class", "FABRIC")).upper().strip()
            
            final_pcs_sync = float(st.session_state.get("user_edited_pieces", {}).get(idx, v_piece.get("inferred_pieces", 1.0))) * size_scale_ratio
            if p_class == "FABRIC" and float(v_piece.get("production_w", 0.0)) > 16.0:
                final_pcs_sync = final_pcs_sync * 2.0 
                
            net_area = float(df_bom.at[idx, "polygon_net_area"] if idx in df_bom.index else 0.0)
            
            if p_class == "ACCESSORY": 
                return 0.0
            elif p_class in ["FUSING", "INTERLINING"]:
                if total_fusing_net_sum > 0: 
                    return round(total_fusing_gross_yds * ((net_area * final_pcs_sync) / total_fusing_net_sum), 4)
                return 0.0
            elif p_class == "FABRIC":
                # HÀNH LANG CÔ LẬP TUYỆT ĐỐI: Mẫu số gánh độc lập, đứng im hoàn toàn khi sửa vải lót túi
                if total_fabric_net_sum > 0: 
                    return round(total_fabric_gross_yds * ((net_area * final_pcs_sync) / total_fabric_net_sum), 4)
                return 0.0
            elif p_class in ["LINING", "RIB"]:
                if total_lining_net_sum > 0: 
                    return round(total_lining_gross_yds * ((net_area * final_pcs_sync) / total_lining_net_sum), 4)
            return 0.0

        df_bom["Gross Consumption"] = [core_engine_router(idx) for idx in df_bom.index]
        df_bom["Calculated Width (Inch)"] = [current_fabric_width if (isinstance(virtual_pieces_layer, dict) and str(virtual_pieces_layer.get(idx, {}).get("inferred_class", "")).upper().strip() == "FABRIC") else (lining_width if (isinstance(virtual_pieces_layer, dict) and str(virtual_pieces_layer.get(idx, {}).get("inferred_class", "")).upper().strip() in ["LINING", "RIB"]) else fusing_width) for idx in df_bom.index]

        # Khóa đồng bộ size tính toán hiển thị bảng chi tiết
        real_sync_size = str(st.session_state.get("current_active_size", "32")).upper().strip()
        df_bom["Size tính toán"] = [real_sync_size for _ in df_bom.index]
        st.success(f"💎 **CAD V27 TRIPLE MAXRECTS ENGINES COMPLETE** | Phẳng hóa cấu trúc lề: `THÀNH CÔNG` | Định mức vải chính tối ưu biệt lập: `{total_fabric_gross_yds:.3f} Yds`")







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
    # 🟩 ĐOẠN 7 (PHIÊN BẢN V21 - GIẢI PHÓNG KẸT SIZE & KHỔ VẢI UI): REAL-TIME AUDIT INTERFACE
    # =====================================================================
    st.header("📋 AI AUDIT REPORT (BÁO CÁO KIỂM TOÁN ĐỊNH MỨC TỰ ĐỘNG)")
    
    # Thiết lập và kế thừa đồng bộ từ bộ não hệ thống Master ngoài
    if "bom_data" not in st.session_state or not isinstance(st.session_state["bom_data"], dict):
        st.session_state["bom_data"] = {}
    ctx = st.session_state["bom_data"]
    
    ai_decision_final = ctx.get("ai_expert_decision", {})
    estimated_prior_val = float(ai_decision_final.get("estimated_density_prior", 0.795))
    ui_display_density = float(ai_decision_final.get("real_fabric_density", estimated_prior_val))
    comp_score_val = float(ai_decision_final.get("complexity_score", 45.0))
    
    ui_complexity_tier = "COMPLEX" if comp_score_val >= 50 else "NORMAL"
    ui_complexity_icon = "🔴" if comp_score_val >= 75 else ("🟡" if comp_score_val >= 45 else "🟢")
    prod_cat_ui = str(ai_decision_final.get("product_category", "JEAN_LONG")).upper().strip()

    # ĐỒNG BỘ MASTER NGOÀI: Đọc nhãn loại hàng thân thiện trực tiếp từ RAM Master ngoài đã qua Đoạn 3.1 làm sạch
    real_sync_product_type = str(ai_decision_final.get("product_type_friendly", "JEAN_LONG (Quần dài Jeans/Pants)")).strip()

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("🤖 Loại Hàng Nhận Diện", real_sync_product_type)
    m2.metric(f"{ui_complexity_icon} Mức Độ Phức Tạp", f"{ui_complexity_tier} ({comp_score_val:.0f}/100)")
    m3.metric("📐 Mật Độ Sơ Đồ Chỉ Định", f"{ui_display_density*100:.2f}%")
    m4.metric("🎯 Độ Tin Cậy AI (Confidence)", f"{float(ctx.get('confidence', 0.95))*100:.1f}%")

    # Ép bảng Summary phải nhóm dữ liệu theo đúng nhãn chất liệu của Mảnh ảo trong RAM
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
    
    # ĐỒNG BỘ MASTER KHỔ VẢI THỜI GIAN THỰC LÊN LƯỚI UI CHI TIẾT
    real_sync_width = float(st.session_state.get("current_active_width", 58.0))
    if "Calculated Width (Inch)" in df_bom_display.columns:
        df_bom_display["Khổ vải sản xuất (inch)"] = df_bom_display["Calculated Width (Inch)"].round(1)
    else:
        df_bom_display["Khổ vải sản xuất (inch)"] = real_sync_width
        
    # ĐỒNG BỘ MASTER SIZE MỤC TIÊU THỜI GIAN THỰC LÊN LƯỚI UI CHI TIẾT (Giải phóng hoàn toàn bẫy kẹt size cứng số 30/32 cũ)
    real_sync_size_code = str(st.session_state.get("current_active_size", ctx.get("detected_base_size", "32"))).upper().strip()
    df_bom_display["Size tính toán"] = real_sync_size_code
    
    df_bom_display["material_class"] = df_bom_display["_temp_class"]
    df_bom_display = df_bom_display.rename(columns={"component_name": "Component Name", "material_class": "Material Class", "geometry_role": "Role/Piece Type"})
    df_bom_display["Số lượng rập"] = [float(st.session_state.get("user_edited_pieces", {}).get(idx, r["pcs_numeric"])) for idx, r in df_bom.iterrows()]
    df_bom_display["_original_row_index"] = df_bom.index

    # Sắp xếp cấu trúc cột hiển thị đồng bộ chuẩn xác cao cấp
    ordered_cols = [
        "_original_row_index", 
        "Component Name", 
        "Material Class", 
        "Role/Piece Type", 
        "Chiều dài rập (inch)",   
        "Chiều rộng rập (inch)",  
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
                excel_file = local_export_excel_ppj_format(df_summary, df_bom_display.drop(columns=["_original_row_index"], errors="ignore"), prod if 'prod' in locals() else "JEAN", ctx, ui_display_density)
                style_name_clean = str(ctx.get('style_code', 'Style')).strip().replace('/', '_').replace('\\', '_')
                st.download_button("🟢 DOWNLOAD EXCEL ĐỊNH MỨC THƯƠNG MẠI", data=excel_file, mime="application/vnd.openpyxl_formats-officedocument.spreadsheetml.sheet", file_name=f"PPJ_BOM_{style_name_clean}.xlsx", use_container_width=True)
        except Exception as e: 
            st.error(f"Lỗi kết xuất Excel thương mại: {e}")

    # RENDER GRID ĐỒNG BỘ: Cập nhật định dạng lưới thông minh số thực số thập phân chuyên nghiệp
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
        }, use_container_width=True, hide_index=True, key="bom_data_editor_grid_final_v21_master_match" 
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
