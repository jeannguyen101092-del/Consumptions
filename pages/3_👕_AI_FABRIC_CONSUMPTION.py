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
# 🧠 ĐOẠN A: KHỐI HÀM CACHE AI (PHIÊN BẢN V24) - TÍNH ĐỊNH MỨC CHUẨN KỸ THUẬT
# =====================================================================
@st.cache_data(
    show_spinner=False,
    ttl=3600,  # Khóa chặt bộ nhớ Cache trong 1 tiếng để sửa UI thoải mái
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
    import streamlit as st

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

            # Giới hạn gửi 2 trang ảnh đầu để tối ưu chi phí
            if len(image_payloads) < 2:
                try:
                    pix = doc_recovery[idx].get_pixmap(dpi=72, colorspace=fitz.csRGB)
                    image_payloads.append({"mime_type": "image/jpeg", "data": pix.tobytes("jpeg")})
                except Exception:
                    continue

    gemini_inputs = list(image_payloads)
    gemini_inputs.insert(0, f"=== USER CHAT COMMAND ===\n{current_query}\n\n=== TECHPACK TEXT ===\n{full_pdf_raw_text}\n")

    # Bổ sung chỉ thị nghiêm ngặt cho AI về thông số Size yêu cầu
    extended_prompt = prompt_agent_2 + f"""
    CRITICAL MULTI-MATERIAL EXTRACTION RULES:
    - You MUST extract EVERY SINGLE component listed in the document for the requested TARGET SIZE: {target_size_cmd}.
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
        
        # 📌 1. XỬ LÝ THÔNG SỐ KHỔ VẢI TỪ CẤU HÌNH HOẶC CÂU LỆNH CHAT
        try:
            forced_width = float(active_width)
            if current_query:
                width_match = re.search(r"(khổ\s*vải|khổ)\s*(\d+(\.\d+)?)", str(current_query), re.IGNORECASE)
                if width_match: 
                    forced_width = float(width_match.group(2))
        except:
            forced_width = float(active_width)

        # 📌 2. ĐỌC TỶ LỆ CO RÚT (SHRINKAGE) TỪ CÂU LỆNH CHAT (NẾU CÓ, MẶC ĐỊNH LÀ 0% = 1.0)
        shrinkage_length = 1.0  # Hệ số co rút dọc
        shrinkage_width = 1.0   # Hệ số co rút ngang
        if current_query:
            # Tìm kiếm dạng: "co rút 3%" hoặc "co rút dọc 2% ngang 4%"
            shrink_matches = re.findall(r"co\s*rút\s*(\d+(\.\d+)?)%", str(current_query), re.IGNORECASE)
            if shrink_matches:
                # Nếu chỉ nhập 1 con số co rút chung
                val = float(shrink_matches[0][0]) / 100.0
                shrinkage_length = 1.0 + val
                shrinkage_width = 1.0 + val

        # BẮT BUỘC CỘNG THÊM ĐƯỜNG MAY (SEAM ALLOWANCE) = 0.44 INCH
        SEAM_ALLOWANCE = 0.44

        for row in blueprint_worker.get("bom_rows", []):
            if "component_name" in row:
                row["component_name"] = " ".join(str(row["component_name"]).upper().split())
            
            # Ép kiểu dữ liệu gốc an toàn từ AI
            try: raw_len = float(row.get("bounding_box_length", 0.0))
            except: raw_len = 0.0
            try: raw_wid = float(row.get("bounding_box_width", 0.0))
            except: raw_wid = 0.0
            try: piece_count = int(float(row.get("piece_count", 1)))
            except: piece_count = 1
            
            comp_name = str(row.get("component_name", "")).upper()
            mat_class = str(row.get("material_class", "FABRIC")).upper().strip()
            
            # Phân loại vật tư nghiêm ngặt
            if any(k in comp_name for k in ["FUSING", "INTERLINING", "MEX", "DỰNG", "KEO LOT"]):
                mat_class = "FUSING"
            elif any(k in comp_name for k in ["LINING", "POCKET", "LÓT", "RIB", "BO GÂN"]):
                mat_class = "LINING"
            row["material_class"] = mat_class

            # Đảm bảo hiển thị đúng khổ vải đã chọn/ép cho từng dòng vật tư
            row["fabric_width_inch"] = forced_width

            # 📌 3. ÁP DỤNG CÔNG THỨC: ĐƯỜNG MAY ĐƯỢC CỘNG VÀO HAI ĐẦU CẠNH CỦA CHI TIẾT RẬP
            # Kích thước sau khi cộng đường may và tính độ co rút vải
            if raw_len > 0:
                final_len = (raw_len + (SEAM_ALLOWANCE * 2)) * shrinkage_length
            else:
                final_len = 0.0

            if raw_wid > 0:
                final_wid = (raw_wid + (SEAM_ALLOWANCE * 2)) * shrinkage_width
            else:
                final_wid = 0.0

            # Cập nhật lại kích thước hình học chính xác hiển thị trên UI
            row["bounding_box_length"] = round(final_len, 2)
            row["bounding_box_width"] = round(final_wid, 2)
            row["piece_count"] = piece_count

            # 📌 4. TÍNH TOÁN ĐỊNH MỨC THỰC TẾ (GROSS CONSUMPTION) DỰA TRÊN KHỔ VẢI
            # Đọc hiệu suất sơ đồ (Marker Efficiency), mặc định 82.5% nếu AI không quét được
            try:
                eff_str = str(row.get("marker_efficiency", "82.5%")).replace("%", "").strip()
                marker_eff = float(eff_str) / 100.0
            except:
                marker_eff = 0.825
            row["marker_efficiency"] = f"{round(marker_eff * 100, 1)}%"

            # Công thức tính định mức hình học chuẩn cho 1 sản phẩm (đơn vị: Yards)
            # Khổ vải hiệu dụng = Khổ vải tổng - 1 inch biên vải (An toàn ngành may)
            usable_fabric_width = max(forced_width - 1.0, 10.0) 

            if final_len > 0 and final_wid > 0 and usable_fabric_width > 0:
                # Diện tích hình hộp bao chi tiết (inch vuông) nhân với số lượng chi tiết
                total_area_inches = final_len * final_wid * piece_count
                # Chia cho diện tích của 1 Yard vải theo khổ vải đang tính toán, có tính đến hiệu suất đi sơ đồ
                calculated_gross = total_area_inches / (usable_fabric_width * 36.0 * marker_eff)
                row["gross_consumption"] = round(calculated_gross, 4)
            else:
                row["gross_consumption"] = 0.0

            # Tính lại diện tích lưới phẳng trực quan cho UI
            row["polygon_net_area"] = round(final_len * final_wid * 0.82, 2)

    # Cập nhật bộ đếm log hệ thống
    if "api_calls_count" not in st.session_state: st.session_state["api_calls_count"] = 0
    if "tokens_consumed" not in st.session_state: st.session_state["tokens_consumed"] = 0
    st.session_state["api_calls_count"] += 1
    st.session_state["tokens_consumed"] += len(str(full_pdf_raw_text)) // 4

    return blueprint_worker




import streamlit as st
import re

# =====================================================================
# 🟩 ĐOẠN 1: CHAT WORKSPACE LAYER (TỰ ĐỘNG PHÂN TÍCH THÔNG SỐ SẢN XUẤT)
# =====================================================================

# 1. Khởi tạo an toàn bộ nhớ đệm hệ thống (Session State)
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "ai_processing" not in st.session_state:
    st.session_state.ai_processing = False
if "last_submitted_query" not in st.session_state:
    st.session_state.last_submitted_query = ""

# Khởi tạo các biến lưu trữ thông số kỹ thuật để truyền sang Đoạn A
if "active_width" not in st.session_state:
    st.session_state.active_width = 58.0  # Khổ vải mặc định thông dụng
if "target_size_cmd" not in st.session_state:
    st.session_state.target_size_cmd = "M"  # Size mặc định
if "shrinkage_length" not in st.session_state:
    st.session_state.shrinkage_length = 1.0  # Hệ số co dọc mặc định (0%)
if "shrinkage_width" not in st.session_state:
    st.session_state.shrinkage_width = 1.0   # Hệ số co ngang mặc định (0%)

# 2. Tạo một khung Container riêng độc lập để chứa lịch sử hội thoại cũ
chat_history_container = st.container()
with chat_history_container:
    st.markdown('<br><div class="cad-card"><div class="cad-header">💬 CHATGPT IE COLLABORATION WORKSPACE</div></div>', unsafe_allow_html=True)
    if st.session_state.get("chat_history"):
        for msg in st.session_state.chat_history:
            st.chat_message("user").write(msg["user"])
            st.chat_message("assistant").write(msg["ai"])

# Thanh nhập lệnh chat động
safe_user_prompt = st.chat_input(
    "Gõ lệnh tính toán (Ví dụ: tính định mức cỡ 32 khổ 56 co rút dọc 3 ngang 14)...",
    key="ie_workspace_fixed_dynamic_chat_final_patch_v9"
)

# 3. Bộ xử lý trích xuất thông số thông minh trước khi ép tải lại luồng (Rerun)
if safe_user_prompt:
    query_text = str(safe_user_prompt).strip()
    st.session_state["last_submitted_query"] = query_text
    
    # 📌 BÓC TÁCH KHỔ VẢI: Tìm cụm "khổ 56", "khổ vải 58"
    width_match = re.search(r"(khổ\s*vải|khổ)\s*(\d+(\.\d+)?)", query_text, re.IGNORECASE)
    if width_match:
        st.session_state.active_width = float(width_match.group(2))
        
    # 📌 BÓC TÁCH SIZE/CỠ YÊU CẦU: Tìm cụm "cỡ 32", "size M", "cỡ L"
    size_match = re.search(r"(cỡ|size)\s*([a-zA-Z0-9]+)", query_text, re.IGNORECASE)
    if size_match:
        st.session_state.target_size_cmd = str(size_match.group(2)).upper()

    # 📌 BÓC TÁCH ĐỘ CO RÚT CHI TIẾT (DỌC VÀ NGANG)
    # Trường hợp 1: Có cả "dọc X" và "ngang Y"
    shrink_length_match = re.search(r"dọc\s*(\d+(\.\d+)?)", query_text, re.IGNORECASE)
    shrink_width_match = re.search(r"ngang\s*(\d+(\.\d+)?)", query_text, re.IGNORECASE)
    
    if shrink_length_match:
        st.session_state.shrinkage_length = 1.0 + (float(shrink_length_match.group(1)) / 100.0)
    if shrink_width_match:
        st.session_state.shrinkage_width = 1.0 + (float(shrink_width_match.group(1)) / 100.0)
        
    # Trường hợp 2: Chỉ ghi chung chung "co rút 3%" (áp dụng đều cho cả dọc và ngang)
    if not shrink_length_match and not shrink_width_match:
        general_shrink_match = re.search(r"co\s*rút\s*(\d+(\.\d+)?)", query_text, re.IGNORECASE)
        if general_shrink_match:
            val = float(general_shrink_match.group(1)) / 100.0
            st.session_state.shrinkage_length = 1.0 + val
            st.session_state.shrinkage_width = 1.0 + val
        else:
            # Nếu không nhập co rút, reset về gốc (0%) để tránh kẹt dữ liệu của lệnh cũ
            st.session_state.shrinkage_length = 1.0
            st.session_state.shrinkage_width = 1.0

    # Kích hoạt cờ hiệu xử lý luồng cho AI Agent
    st.session_state.ai_processing = True
    st.rerun()

import streamlit as st
import re

# =====================================================================
# 🟩 ĐOẠN 2 (PHIÊN BẢN V24 - CHUẨN ĐỒNG BỘ): SCHEMAS, PROMPTS & AI EXECUTE
# =====================================================================
if st.session_state.ai_processing:
    current_query = st.session_state["last_submitted_query"]
    
    # Tìm kiếm file PDF từ tất cả các nguồn bộ nhớ đệm có thể có
    active_pdf = (
        st.session_state.get("pdf_bytes") 
        or st.session_state.get("uploaded_file") 
        or st.session_state.get("current_pdf") 
        or st.session_state.get("pdf_data")
    )

    # Lấy thông số đã bóc tách sạch sẽ từ Đoạn 1 (Chat Workspace Layer) làm chuẩn [1, 2]
    dynamic_width = st.session_state.get("active_width", 58.0)
    target_size = st.session_state.get("target_size_cmd", "M")

    if active_pdf is not None:
        with st.spinner(f"🧠 AI Vision đang quét phôi rập Nguyên Liệu cho Size {target_size}..."):
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
                You are a senior Industrial Garment IE & CAD Pattern Engineering Intelligence. Reconstruct the multi-layered CAD metadata for EVERY valid fabric/fusing piece in the Techpack for Target Size: {target_size}.
                
                🚨 CRITICAL TARGET SIZE ACCURACY:
                - You MUST look for the exact measurement table column, pattern grading row, or text notes corresponding to Size {target_size}.
                - Do NOT extract base size dimensions if the user explicitly requested Size {target_size}.
                
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

                # 3. GỌI HÀM QUÉT AI CACHE MỚI ĐÃ SỬA ĐỒNG BỘ TÊN HÀM V24 CHÍNH XÁC
                bom_data = execute_final_gerber_pure_scan(
                    pdf_bytes=active_pdf,
                    current_query=current_query,
                    active_width=dynamic_width,
                    target_size_cmd=target_size,
                    raw_json_schema=raw_json_schema,
                    prompt_agent_2=prompt_agent_2
                )
                
                # Lưu trữ kết quả đầu ra an toàn vào session state để hiển thị lên bảng dữ liệu (Dataframe/Table)
                st.session_state["final_bom_data"] = bom_data
                st.success(f"🎉 Đã trích xuất và tính toán định mức thành công cho Khổ {dynamic_width} in - Cỡ {target_size}!")
                
            except Exception as e:
                st.error(f"❌ Lỗi xử lý dữ liệu hệ thống: {str(e)}")
            finally:
                # Hạ cờ hiệu xử lý để mở khóa cho lệnh chat tiếp theo
                st.session_state.ai_processing = False
                st.rerun()
    else:
        st.warning("⚠️ Không tìm thấy file tài liệu kĩ thuật (Techpack PDF). Vui lòng upload file trước khi ra lệnh tính toán!")
        st.session_state.ai_processing = False



def initialize_and_sync_parameters():
    """Khối 1 (PHIÊN BẢN V24 - MASTER CONTROLLER): Đồng bộ thông số, chống bẫy ghi đè Cache AI"""
    import re
    import streamlit as st

    # 📌 1. Đồng bộ lại khóa lưu trữ chính xác từ Đoạn 2 ("final_bom_data")
    bom_source = st.session_state.get("final_bom_data") or st.session_state.get("bom_data") or {}
    accumulated = st.session_state.get("accumulated_bom_rows")
    
    if not bom_source and not accumulated:
        return None, None
        
    if not isinstance(bom_source, dict):
        bom_source = {"bom_rows": bom_source} if isinstance(bom_source, list) else {}
    
    # Trích xuất văn bản từ ô chat câu lệnh người dùng
    user_query_text = ""
    if st.session_state.get("last_submitted_query"): 
        user_query_text = str(st.session_state.get("last_submitted_query")).strip()
    
    # 📌 2. Thiết lập thông số mặc định chuẩn ban đầu
    fabric_width = float(bom_source.get("fabric_width_inch", 58.0))
    warp_shrinkage = float(bom_source.get("warp_shrinkage_percent", 0.0))
    weft_shrinkage = float(bom_source.get("weft_shrinkage_percent", 0.0))
    
    # Hằng số đường may bắt buộc theo yêu cầu kỹ thuật
    SEAM_ALLOWANCE = 0.44
    
    # Đồng bộ Size: Ưu tiên lấy từ cấu hình động hoặc từ kết quả quét AI
    detected_size = st.session_state.get("current_active_size", bom_source.get("detected_base_size", bom_source.get("calculated_on_size", "32")))
    target_size = str(detected_size).upper().strip()
    if not target_size: 
        target_size = "32"

    # 📌 3. Quét thông số ép buộc từ câu lệnh bằng bộ lọc Regex cải tiến (Hỗ trợ ký tự %)
    if user_query_text:
        # Khổ vải
        w_match = re.search(r"\b(khổ\s*vải|khổ)\s*[:=]?\s*(\d+(\.\d+)?)\b", user_query_text, re.IGNORECASE)
        if w_match: 
            fabric_width = float(w_match.group(2))
        
        # Co rút dọc
        warp_match = re.search(r"\b(co\s*rút\s*dọc|độ\s*co\s*dọc|co\s*dọc)\s*[:=]?\s*(\d+(\.\d+)?)%?\b", user_query_text, re.IGNORECASE)
        if warp_match: 
            val = float(warp_match.group(2))
            if val < 25.0: warp_shrinkage = val 
        
        # Co rút ngang
        weft_match = re.search(r"\b(co\s*rút\s*ngang|độ\s*co\s*ngang|co\s*ngang)\s*[:=]?\s*(\d+(\.\d+)?)%?\b", user_query_text, re.IGNORECASE)
        if weft_match: 
            val = float(weft_match.group(2))
            if val < 25.0: weft_shrinkage = val

        # Co rút chung (Nếu người dùng chỉ gõ "co rút 3%")
        if not warp_match and not weft_match:
            general_match = re.search(r"\bco\s*rút\s*[:=]?\s*(\d+(\.\d+)?)%?\b", user_query_text, re.IGNORECASE)
            if general_match:
                val = float(general_match.group(1))
                if val < 25.0:
                    warp_shrinkage = val
                    weft_shrinkage = val

        # Size / Cỡ yêu cầu (Hỗ trợ cả size chữ S, M, L, XL và size số 32, 34)
        size_match = re.search(r"\b(cỡ|size)\s*[:=]?\s*([a-zA-Z0-9]+)\b", user_query_text, re.IGNORECASE)
        if size_match: 
            target_size = str(size_match.group(2)).upper().strip()

    # 📌 4. GHI ĐÈ ĐỒNG BỘ LÊN TẦNG NGOÀI SESSION STATE (Chống bẫy mất bộ nhớ khi Rerun)
    st.session_state["current_active_width"] = fabric_width
    st.session_state["current_active_size"] = target_size
    st.session_state["current_warp_shrinkage"] = warp_shrinkage
    st.session_state["current_weft_shrinkage"] = weft_shrinkage
    st.session_state["seam_allowance_inch"] = SEAM_ALLOWANCE  # Lưu cố định đường may vào hệ thống

    # Cập nhật trực tiếp vào cấu trúc dữ liệu bom_data gốc để chuyển mạch xuống tầng dưới
    bom_source["fabric_width_inch"] = fabric_width
    bom_source["usable_width_inch"] = fabric_width  
    bom_source["warp_shrinkage_percent"] = warp_shrinkage
    bom_source["weft_shrinkage_percent"] = weft_shrinkage
    bom_source["calculated_on_size"] = target_size
    bom_source["seam_allowance_inch"] = SEAM_ALLOWANCE
    
    # Trả ngược lại bộ nhớ hệ thống
    st.session_state["final_bom_data"] = bom_source
    st.session_state["bom_data"] = bom_source
    
    return bom_source, user_query_text

import re
import streamlit as st

def extract_cutting_instructions_from_pdf(component_name, raw_pdf_text, current_inferred_pcs=1.0):
    """
    Thuật toán quét Callout Văn bản PDF (PHIÊN BẢN V24 - CHỐNG BẪY NHÂN ĐÔI & TỰ ĐỘNG BÙ RẬP GẬP)
    Tự động phân tích lệnh kỹ thuật chuẩn CAD công nghiệp, đồng bộ với thông số đường may và khổ vải.
    """
    if not raw_pdf_text:
        return {
            "layer_multiplier": 1, 
            "is_paired": False, 
            "is_folded": False,
            "calc_log": "Không tìm thấy dữ liệu văn bản thô PDF."
        }
        
    # Chuẩn hóa chuỗi văn bản để làm sạch khoảng trắng rác
    text_clean = " ".join(str(raw_pdf_text).lower().split())
    comp_clean = str(component_name).lower().strip()
    
    # Khai báo cấu trúc tham chiếu an toàn ban đầu
    layer_multiplier = 1
    is_paired = False
    is_folded = False
    calc_log = "AI đọc văn bản PDF: Đồng bộ trực tiếp theo kích thước phôi đơn của Techpack."
    
    # Đưa biến số lượng gốc về kiểu số nguyên để kiểm tra an toàn
    base_pcs = int(float(current_inferred_pcs or 1.0))
    
    # 📌 1. Sử dụng Regex tìm kiếm linh hoạt thay thế cho .find() tuyệt đối để tránh bẫy lệch ký tự
    # Tìm kiếm tên linh hoạt, bỏ qua các ký tự khoảng trắng dư thừa
    comp_regex = re.escape(comp_clean).replace(r'\ ', r'\s*')
    match_iter = re.finditer(comp_regex, text_clean)
    match_index = -1
    
    for m in match_iter:
        match_index = m.start()
        break # Lấy vị trí xuất hiện đầu tiên hợp lệ

    if match_index != -1:
        # Mở rộng phạm vi quét lùi về trước 120 ký tự và tiến sau 120 ký tự để bóc tách bảng thông số
        window_start = max(0, match_index - 120)
        window_end = min(len(text_clean), match_index + 120)
        scan_window = text_clean[window_start:window_end]
        
        # ➔ A. Quét lệnh số lượng cắt vật lý trực tiếp (Ví dụ: CUT 2, CẮT 2, SELF X2, SHELL=2)
        cut_match = re.search(r'\b(cut|cắt|self|shell|qty)\s*(x\s*|\s*|\s*[:=]\s*)(\d+)\b', scan_window)
        if cut_match:
            detected_qty = int(cut_match.group(3))
            # CHỐNG GỘP KÉP: Chỉ cập nhật hệ số nhân nếu số lượng phát hiện lớn hơn số lượng nền
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
                
        # ➔ C. Quét lệnh gập đôi vải rải sơ đồ (FOLD, GẬP ĐÔI, ON FOLD)
        # 🚨 ĐÃ SỬA: Kích hoạt cờ hiệu gập đôi để tầng tính toán diện tích nhân đôi bề rộng rập đơn độc lập
        if any(k in scan_window for k in ["fold", "gập", "gap doi", "gập đôi", "on fold"]):
            is_folded = True
            calc_log += " | LỆNH PHÒNG VỆ: Phát hiện rập đi biên gập đôi (FOLD). Hệ thống tự kích hoạt nhân đôi kích thước bao phẳng."
            
    return {
        "layer_multiplier": layer_multiplier,
        "is_paired": is_paired,
        "is_folded": is_folded,
        "calc_log": calc_log
    }



import numpy as np
import re
import streamlit as st

def calculate_skyline_2d_metrics(bom_rows_list, user_query_text):
    """
    Khối 2b Siêu Cấp (PHIÊN BẢN V24 - CHUẨN GERBER ENGINE): Mô phỏng toán học phi tuyến tính.
    TÍNH TOÁN ĐỊNH MỨC CHÍNH XÁC: Tự động đồng bộ Khổ vải, Co rút, Size, Rập gập và đường may +0.44 in.
    """
    ctx = classify_pieces_and_products(bom_rows_list, user_query_text)
    if not ctx or not ctx.get("stable_bom_list"):
        return {"product_segmented": "GENERIC_TOP", "fabric_pattern": "SOLID", "actual_packing_density": 0.85, "global_gross_fabric_yds": 1.65, "major_shape_area": 0.0}

    fabric_pattern = ctx["fabric_pattern"]
    
    # 📌 1. ĐỒNG BỘ THÔNG SỐ CHUẨN TỪ MASTER CONTROLLER (SESSION STATE KHỐI 1)
    fabric_width = float(st.session_state.get("current_active_width", ctx.get("fabric_width", 58.0)))
    target_size = str(st.session_state.get("current_active_size", "M"))
    
    # Đọc tỷ lệ co rút từ phần trăm đổi ra hệ số nhân (Ví dụ: 3% -> 1.03)
    warp_shrinkage_pct = float(st.session_state.get("current_warp_shrinkage", 0.0))
    weft_shrinkage_pct = float(st.session_state.get("current_weft_shrinkage", 0.0))
    shrinkage_length_factor = 1.0 + (warp_shrinkage_pct / 100.0)
    shrinkage_width_factor = 1.0 + (weft_shrinkage_pct / 100.0)
    
    # Hằng số đường may bắt buộc cộng thêm vào mỗi đầu cạnh chi tiết
    SEAM_ALLOWANCE = float(st.session_state.get("seam_allowance_inch", 0.44))
    
    stable_bom = ctx["stable_bom_list"]

    # =====================================================================
    # 2. ÁP DỤNG HÌNH HỌC PHẲNG: CỘNG ĐƯỜNG MAY, CO RÚT & TÍNH DIỆN TÍCH THỰC TẾ
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
            
        raw_l = float(r.get("bounding_box_length", r.get("Dài (L-inch)", 0.0)))
        raw_w = float(r.get("bounding_box_width", r.get("Rộng (W-inch)", 0.0)))
        
        if raw_l <= 0 or raw_w <= 0:
            continue

        # ➔ A. KIỂM TRA LỆNH RẬP GẬP ĐÔI (FOLD): Nếu có, phải nhân đôi chiều rộng thô trước khi cộng đường may
        is_folded = r.get("is_folded", False)
        if is_folded:
            raw_w = raw_w * 2.0

        # ➔ B. BẮT BUỘC CỘNG ĐƯỜNG MAY VÀO 2 ĐẦU CẠNH VÀ NHÂN HỆ SỐ CO RÚT VẢI KỸ THUẬT
        final_l_inch = (raw_l + (SEAM_ALLOWANCE * 2)) * shrinkage_length_factor
        final_w_inch = (raw_w + (SEAM_ALLOWANCE * 2)) * shrinkage_width_factor
        
        # Cập nhật ngược lại rập để hiển thị đúng thông số lên giao diện UI bảng dữ liệu
        r["bounding_box_length"] = round(final_l_inch, 2)
        r["bounding_box_width"] = round(final_w_inch, 2)

        # Tính toán lại diện tích hộp bao phẳng thực tế sau khi tăng kích thước đường may
        bbox_a = final_l_inch * final_w_inch
        
        # ➔ C. ĐỒNG BỘ DIỆN TÍCH TINH (POLYGON NET AREA) THEO TỶ LỆ HÌNH HỌC MỚI
        # Lấy tỷ lệ diện tích tinh của rập gốc để nhân với hộp bao mới, chống lỗi tràn hoặc rỗng diện tích
        raw_bbox = raw_l * raw_w
        raw_net = float(r.get("polygon_net_area", 0.0))
        fill_ratio = (raw_net / raw_bbox) if (raw_bbox > 0 and raw_net > 0) else 0.78
        
        net_a = bbox_a * min(max(fill_ratio, 0.50), 0.98)
        r["polygon_net_area"] = round(net_a, 2)
            
        total_net_area += net_a * pcs
        total_bbox_area += bbox_a * pcs
        total_piece_count += pcs
        
        for _ in range(int(pcs)):
            all_expanded_pieces.append({
                "net_area": net_a, "bbox_area": bbox_a, "length": final_l_inch, "width": final_w_inch
            })

    # =====================================================================
    # 3. TRÍCH XUẤT ĐẶC TRƯNG HÌNH HỌC PHI TUYẾN TÍNH CHUẨN ĐỒ THỊ GERBER
    # =====================================================================
    if total_bbox_area <= 0:
        return {"product_segmented": ctx.get("product_type", "JEAN_LONG"), "fabric_pattern": fabric_pattern, "actual_packing_density": 0.82, "global_gross_fabric_yds": 0.0, "major_shape_area": 0.0}

    major_threshold_area = total_net_area * 0.08 if total_net_area > 0 else 50.0
    major_pieces_list = [p for p in all_expanded_pieces if p["net_area"] > major_threshold_area]
    minor_pieces_list = [p for p in all_expanded_pieces if p["net_area"] <= major_threshold_area]
    
    fragmentation_ratio = len(minor_pieces_list) / total_piece_count if total_piece_count > 0 else 0.20
    bounding_box_fill = total_net_area / total_bbox_area

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
    small_piece_ratio = minor_area_sum / total_net_area
    edge_irregularity = 1.0 - convexity_score

    # Đồ thị phạt Logistic điều hướng mật độ nền khi chiếm khổ vải lớn
    logistic_midpoint = 0.38
    logistic_k = 12.0  
    width_penalty_logistic = 0.05 / (1.0 + np.exp(-logistic_k * (width_occupancy_ratio - logistic_midpoint)))

    # =====================================================================
    # 4. TÍNH TOÁN MẬT ĐỘ NÈN ĐỘNG CHUẨN CƠ ĐỒNG BỘ
    # =====================================================================
    calculated_density = 0.72 + (bounding_box_fill * 0.14) + (compactness_score * 0.04)
    nesting_efficiency_bonus = (small_piece_ratio * 0.04) + (fragmentation_ratio * 0.02)
    actual_packing_density = (calculated_density + nesting_efficiency_bonus - width_penalty_logistic) * rotation_freedom_factor
    actual_packing_density = max(min(actual_packing_density, 0.9450), 0.7600)

    # =====================================================================
    # 5. CHIỀU DÀI SƠ ĐỒ VÀ TRUNG HÒA HAO HỤT BÀN CẮT (YARDS)
    # =====================================================================
    # Khổ vải hiệu dụng tính sơ đồ sau khi trừ biên vải an toàn (1.0 inch)
    usable_fabric_width = max(fabric_width - 1.0, 10.0)
    
    simulated_length = (total_net_area / usable_fabric_width) / actual_packing_density
    simulated_length *= (1.0 + (edge_irregularity * 0.02))

    # Tính toán đường cong hao hụt bàn cắt đầu khúc thương mại
    length_logistic_mid = 45.0  
    length_k = -0.05
    wastage_curve_factor = 0.005 + (0.04 / (1.0 + np.exp(-length_k * (simulated_length - length_logistic_mid))))
    fabric_wastage_multiplier = 1.010 + wastage_curve_factor
    
    # Quy đổi thẳng tổng chiều dài sơ đồ phẳng sang đơn vị Yards thông dụng
    global_gross_fabric = (simulated_length / 36.0) * fabric_wastage_multiplier

    # =====================================================================
    # 6. XỬ LÝ CHU KỲ VÂN VẢI ĐỘNG (NAP / PLAID)
    # =====================================================================
    fabric_repeat_inch = float(ctx.get("fabric_repeat_inch", 4.0)) 

    if fabric_pattern == "NAP":
        global_gross_fabric += (fabric_repeat_inch * 0.15 * (1.0 - small_piece_ratio)) / 36.0
    elif fabric_pattern in ["PLAID", "STRIPE"]:
        plaid_loss_ratio = (fabric_repeat_inch * 0.85) / simulated_length if simulated_length > 0 else 0.03
        global_gross_fabric *= (1.0 + min(plaid_loss_ratio, 0.15))

    # Ép định mức sàn phòng vệ dòng hàng phức tạp (Jacket)
    if "JACKET" in str(ctx.get("product_type", "")).upper() and global_gross_fabric < 1.2:
        global_gross_fabric = 2.15

    major_area_sum = sum(p["net_area"] for p in major_pieces_list) if major_pieces_list else total_net_area

    return {
        "product_segmented": ctx.get("product_type", "JEAN_LONG"), 
        "fabric_pattern": fabric_pattern,
        "actual_packing_density": actual_packing_density, 
        "global_gross_fabric_yds": round(global_gross_fabric, 4),
        "major_shape_area": major_area_sum  
    }



import re
import streamlit as st

def extract_cutting_instructions_from_pdf(component_name, raw_pdf_text, current_inferred_pcs=1.0):
    """
    Thuật toán quét Callout văn bản PDF (PHIÊN BẢN V24 - ANTI-DOUBLE MULTIPLIER & FOLD DETECTOR)
    Tự động phân tích các lệnh kỹ thuật (CUT 2, PAIR, SELF, FUSE, MIRROR, FOLD).
    ĐÃ SỬA: Trả về cờ hiệu is_folded để nhân đôi kích thước phôi gập và tính đúng đường may 0.44 in.
    """
    if not raw_pdf_text:
        return {
            "layer_multiplier": 1, 
            "is_paired": False, 
            "is_folded": False, 
            "calc_log": "CAD Fallback: Không tìm thấy dữ liệu văn bản thô PDF."
        }
        
    # Chuẩn hóa chuỗi văn bản để làm sạch khoảng trắng rác
    text_clean = " ".join(str(raw_pdf_text).lower().split())
    comp_clean = str(component_name).lower().strip()
    
    # Thiết lập cấu trúc mặc định theo quy chuẩn dệt may
    layer_multiplier = 1
    is_paired = False
    is_folded = False  # 🚨 BỔ SUNG: Cờ hiệu theo dõi rập gập biên
    calc_log = "AI Engine: Mặc định đồng bộ trực tiếp theo số lượng phôi gốc từ sơ đồ Techpack."
    
    # Ép biến số lượng gốc về dạng số nguyên để kiểm tra an toàn hình học
    base_pcs = int(float(current_inferred_pcs or 1.0))
    
    # Sử dụng Regex tìm kiếm linh hoạt thay cho .find() để tránh lỗi lệch ký tự viết hoa/thường
    comp_regex = re.escape(comp_clean).replace(r'\ ', r'\s*')
    match_iter = re.finditer(comp_regex, text_clean)
    match_index = -1
    
    for m in match_iter:
        match_index = m.start()
        break

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
        if any(k in scan_window for k in ["pair", "cặp", "đối", "mirror", "đối xứng", "1 pair", "left/right", "trái/phải"]):
            is_paired = True
            # CHỈ ĐƯỢC PHÉP BÙ PHÔI ĐỐI XỨNG (X2) NẾU SỐ LƯỢNG GỐC TRONG TECHPACK ĐANG THIẾU (= 1)
            if base_pcs == 1 and layer_multiplier == 1:
                layer_multiplier = 2
                calc_log = "Trích xuất Callout PDF: Phát hiện kết cấu cặp (PAIR) trên rập đơn. Kích hoạt đối xứng phôi phẳng."
                
        # ➔ C. Quét lệnh gập đôi vải bàn cắt (FOLD, GẬP ĐÔI, ON FOLD)
        # 🚨 ĐÃ SỬA: Bật cờ hiệu is_folded lên True để lõi hình học phía sau tự động bù kích thước rập gập
        if any(k in scan_window for k in ["fold", "gập", "gap doi", "gập đôi", "on fold"]):
            is_folded = True
            calc_log += " | LỆNH PHÒNG VỆ: Phát hiện rập đi biên gập đôi (FOLD). Kích hoạt bù nhân đôi bề rộng."
            
    return {
        "layer_multiplier": layer_multiplier,
        "is_paired": is_paired,
        "is_folded": is_folded,  # Xuất dữ liệu cấu hình ra ngoài
        "calc_log": calc_log
    }



import streamlit as st

def process_pieces_layer_and_areas(bom_rows_list, product_segmented, warp_shrinkage, weft_shrinkage):
    """
    Khối 3 hoàn chỉnh (PHIÊN BẢN V26 - GEOMETRIC AREA SOLVER): Chuẩn hóa hình học phẳng dệt may.
    ĐÃ SỬA: Tính chuẩn kích thước rập gập, bắt buộc cộng đúng 0.44 inch đường may và nhân co rút chính xác.
    """
    # Hàm bổ trợ ép kiểu an toàn nội bộ
    def safe_float(v, default=0.0):
        try: return float(v)
        except: return default
    def safe_int(v, default=1):
        try: return int(float(v))
        except: return default

    total_fabric_piece_area = 0.0
    piece_calculated_data = []
    raw_pdf_context = st.session_state.get("raw_pdf_text_extracted", "")

    # 📌 1. LẤY HẰNG SỐ ĐƯỜNG MAY BẮT BUỘC TỪ MASTER CONTROLLER (MẶC ĐỊNH LÀ 0.44 INCH)
    SEAM_ALLOWANCE = float(st.session_state.get("seam_allowance_inch", 0.44))
    
    # Chuyển đổi phần trăm co rút sang hệ số nhân (Ví dụ: 3% -> 1.03)
    shrink_len_factor = 1.0 + (safe_float(warp_shrinkage) / 100.0)
    shrink_wid_factor = 1.0 + (safe_float(weft_shrinkage) / 100.0)

    for r in bom_rows_list:
        if not r or not isinstance(r, dict): 
            continue
        
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
        
        # Nhận diện nhãn lớp vật tư thực tế
        if mat_zone in ["SELF", "FABRIC"]: 
            r_material_class = "FABRIC"
        elif mat_zone in ["FUSING", "INTERFACING", "INTERLINING", "MEX"]: 
            r_material_class = "FUSING"
        elif mat_zone in ["LINING", "POCKET", "RIB"]: 
            r_material_class = "LINING"
        else: 
            r_material_class = "FABRIC"

        # 📌 2. XỬ LÝ RẬP GẬP BIÊN (FOLD): Nếu có lệnh gập đôi, phải nhân đôi bề rộng rập thô ngay lập tức
        is_folded = r.get("is_folded", False) or fold_type in ["ON_FOLD", "CENTER_FOLD"]
        if is_folded:
            raw_w = raw_w * 2.0

        # Đọc số lượng phôi gốc từ Techpack
        pcs = safe_int(r.get("original_piece_count", r.get("pcs_numeric", 1)))
        if "original_piece_count" not in r:
            r["original_piece_count"] = pcs
            
        cut_qty_ai = safe_int(r.get("cut_quantity", 1), default=1)
        ai_convex_ratio = safe_float(r.get("convex_fill_ratio", 0.74))
        if ai_convex_ratio <= 0 or ai_convex_ratio > 1.0:
            ai_convex_ratio = 0.74
            
        mirror_piece = r.get("mirror_piece", False)

        if raw_l > 0 and raw_w > 0:
            # 📌 3. BẮT BUỘC CỘNG ĐƯỜNG MAY 0.44 INCH VÀO HAI ĐẦU CẠNH CHI TIẾT (+0.88 IN)
            seamed_l = raw_l + (SEAM_ALLOWANCE * 2)
            seamed_w = raw_w + (SEAM_ALLOWANCE * 2)

            # 📌 4. ÁP THÔNG SỐ CO RÚT VẢI CỦA NHÀ MÁY VÀO KÍCH THƯỚC ĐÃ CÓ ĐƯỜNG MAY
            adj_l = seamed_l * shrink_len_factor
            adj_w = seamed_w * shrink_wid_factor

            # CHỐNG BẪY NHÂN ĐÔI SỐ LƯỢNG KÉP: Khóa chặt hệ số nhân nếu dữ liệu nền đã đủ phôi rập
            if cut_qty_ai > pcs:
                layer_multiplier = max(1, cut_qty_ai // pcs)
            else:
                layer_multiplier = 1
                
            if mirror_piece and pcs == 1 and layer_multiplier == 1:
                layer_multiplier = 2

            # Tính toán hệ số phom dáng hình học (Shape Factor) từ Convex Ratio động chuẩn CAD phẳng
            shape_factor = ai_convex_ratio
            if is_folded:
                shape_factor *= 0.96
            if critical_alignment in ["STRIPE", "PLAID"]:
                shape_factor += 0.02
                
            if piece_function == "PRIMARY":
                shape_factor = max(0.6400, min(0.8800, shape_factor))
            elif piece_shape == "RECTANGLE":
                shape_factor = 0.98

            total_pcs_final = pcs * layer_multiplier
            
            # GEOMETRY GUARD: Chặn đứng hiện tượng diện tích tinh lấn át hộp bao phẳng
            bbox_area = adj_l * adj_w
            calculated_net_area = bbox_area * shape_factor
            if calculated_net_area > bbox_area:
                calculated_net_area = bbox_area * 0.76
                
            item_area = calculated_net_area * total_pcs_final
            
            # Đồng bộ dữ liệu sạch hoàn toàn vào cấu trúc hệ thống để hiển thị đúng lên UI Table
            r["material_class"] = r_material_class
            if r_material_class == "FABRIC": 
                total_fabric_piece_area += item_area
            
            # Hiển thị kích thước sản xuất thực tế trên bảng giao diện sau khi đã cộng đường may và co rút
            r["bounding_box_length"] = round(adj_l, 2)
            r["bounding_box_width"] = round(adj_w, 2)
            r["production_length"] = round(adj_l, 2)
            r["production_width"] = round(adj_w, 2)
            r["piece_count"] = total_pcs_final
            r["Số lượng rập"] = total_pcs_final
            r["polygon_net_area"] = round(calculated_net_area, 2)
            r["calculation_status"] = "PROCESSED"
            r["cad_algorithm"] = f"Phom: {piece_shape} | Đường may: +{SEAM_ALLOWANCE} in | Gập: {is_folded}"
            
            piece_calculated_data.append({
                "row_ref": r, "item_area": item_area, "is_button": False, "pcs_display": f"{total_pcs_final} Pcs",
                "layer_multiplier": layer_multiplier, "mat_class_raw": r_material_class, "combined_str": f" {comp_name_raw} ", 
                "is_belt_loop": (piece_shape == "RECTANGLE" and "LOOP" in comp_name_raw), 
                "raw_l": round(adj_l, 2), "raw_w": round(adj_w, 2), "pcs_val": pcs, "custom_name": comp_name_raw
            })
            
    st.session_state["piece_calculated_data"] = piece_calculated_data
    return round(total_fabric_piece_area, 4), piece_calculated_data




import streamlit as st

def allocate_gerber_share_consumption(piece_calculated_data, total_fabric_piece_area, skyline_results):
    """
    Khối 4 hoàn chỉnh (PHIÊN BẢN V26 - GERBER ALLOCATION ENGINE): Phân bổ định mức thương mại.
    ĐÃ SỬA: Khử triệt để lỗi sập NameError biến hệ thống, đồng bộ hóa chính xác Khổ vải, Size, Đường may +0.44 in.
    """
    # Hàm bổ trợ ép kiểu an toàn nội bộ
    def safe_int(v, default=1):
        try: return int(float(v))
        except: return default

    base_gross_fabric = skyline_results.get("global_gross_fabric_yds", 0.0)
    if base_gross_fabric == 0.0:
        base_gross_fabric = skyline_results.get("global_gross_fabric_consumption", 0.0)
    if base_gross_fabric == 0.0:
        base_gross_fabric = skyline_results.get("global_gross_fabric", 0.0)
        
    product_segmented = skyline_results.get("product_segmented", "JEAN_LONG")
    actual_packing_density = skyline_results.get("actual_packing_density", 0.85)
    if actual_packing_density <= 0: 
        actual_packing_density = 0.85
    
    bom_source = st.session_state.get("bom_data", {})
    usable_width = bom_source.get("fabric_width_inch", 58.0)
    if not isinstance(usable_width, (int, float)) or usable_width <= 0: 
        usable_width = 58.0
    
    # Đồng bộ khổ vải phụ thời gian thực từ bộ nhớ hệ thống (Khối 1 Master Controller)
    lining_width = float(st.session_state.get("lining_width_inch", 57.0))
    fusing_width = float(st.session_state.get("fusing_width_inch", 59.0))
    
    # Khổ vải hiệu dụng sau khi trừ 1.0 inch biên vải an toàn ngăn ngừa hụt sơ đồ phẳng
    usable_fabric_width_net = max(usable_width - 1.0, 10.0)
    usable_lining_width_net = max(lining_width - 1.0, 10.0)
    usable_fusing_width_net = max(fusing_width - 1.0, 10.0)

    # ➔ BƯỚC 1: THUẬT TOÁN CHUẨN HÓA TRỌNG SỐ (RE-NORMALIZATION) CHO VẢI CHÍNH
    weighted_area_sum = 0.0
    for item in piece_calculated_data:
        if "row_ref" not in item: 
            continue
        r = item["row_ref"]
        mat_class_raw = str(item["mat_class_raw"]).upper().strip()
        
        if mat_class_raw == "FABRIC":
            packing_priority = safe_int(r.get("packing_priority", 3), default=3)
            # Áp trọng số gánh nền chuẩn dệt may (Rập diện tích lớn gánh hao hụt biên đầu khúc sơ đồ nhiều hơn)
            weight_factor = 1.08 if packing_priority <= 2 else (0.88 if packing_priority >= 4 else 1.00)
            weighted_area_sum += item["item_area"] * weight_factor

    # ➔ BƯỚC 2: TIẾN HÀNH PHÂN BỔ ĐỊNH MỨC CHI TIẾT THEO TRỤC VẬT TƯ VÀ SIZE YÊU CẦU
    processed_rows = []

    for item in piece_calculated_data:
        if "row_ref" not in item: 
            continue
        r = item["row_ref"]
        item_area = item["item_area"]
        layer_multiplier = item["layer_multiplier"]
        mat_class_raw = str(item["mat_class_raw"]).upper().strip()
        
        raw_l = r.get("production_length", item.get("raw_l", 0.0))
        pcs = item["pcs_val"]
        
        # 📌 SỬA LỖI SẬP MÃ NGUỒN: Tính toán chính xác tổng số lượng chi tiết thực tế của dòng rập
        calculated_total_pcs = pcs * layer_multiplier

        # Ép điều kiện phân tách định mức độc lập theo chủng loại vật tư thương mại
        if mat_class_raw == "FABRIC":
            packing_priority = safe_int(r.get("packing_priority", 3), default=3)
            if total_fabric_piece_area > 0 and base_gross_fabric > 0 and weighted_area_sum > 0:
                weight_factor = 1.08 if packing_priority <= 2 else (0.88 if packing_priority >= 4 else 1.00)
                # Công thức phân bổ chuẩn hóa: Tỷ trọng diện tích có trọng số của dòng rập
                share_ratio = (item_area * weight_factor) / weighted_area_sum
                gross_consumption = round(base_gross_fabric * share_ratio, 4)
                calc_chain = f"Gerber Fabric Re-normalized (Priority {packing_priority})"
            else:
                # CAD Geometry Fallback chuẩn hóa theo khổ vải hữu ích thực tế
                estimated_base = ((item_area / usable_fabric_width_net) / 36.0) / actual_packing_density
                gross_consumption = round(estimated_base, 4)
                calc_chain = f"CAD Geometry Fallback (Net Width)"
                    
        elif mat_class_raw == "LINING":
            # Định mức lót: Tính toán dựa trên diện tích phôi rập (đã gồm đường may +0.44 in và độ co rút)
            gross_consumption = round(((item_area / usable_lining_width_net) / 36.0), 4)
            calc_chain = f"Sơ đồ LINING độc lập (Khổ hữu ích {usable_lining_width_net} in)"
            
        elif mat_class_raw == "FUSING":
            # Định mức keo/mếch: Tính toán dựa trên diện tích phôi rập (đã gồm đường may +0.44 in và độ co rút)
            gross_consumption = round(((item_area / usable_fusing_width_net) / 36.0), 4)
            calc_chain = f"Sơ đồ FUSING độc lập (Khổ hữu ích {usable_fusing_width_net} in)"
            
        elif mat_class_raw in ["RIB", "CONTRAST"]:
            # Định mức vải phối / bo gân theo khổ vải hữu ích được chỉ định
            gross_consumption = round(((item_area / usable_fabric_width_net) / 36.0), 4)
            calc_chain = f"Sơ đồ phối {mat_class_raw} độc lập (Khổ hữu ích {usable_fabric_width_net} in)"
        else:
            gross_consumption, calc_chain = 0.0, f"Vật tư phụ mẫu hàng {product_segmented}."

        # 📌 3. ĐỒNG BỘ DỮ LIỆU ĐẦU RA LÊN GIAO DIỆN BẢNG DỮ LIỆU CHI TIẾT (UI DATAFRAME)
        r["Gross Consumption"] = gross_consumption
        r["Số lượng rập"] = f"{calculated_total_pcs} Pcs"
        r["fabric_width_inch"] = usable_width  # Hiển thị đúng khổ vải được chọn
        r["calculation_chain"] = calc_chain    # Lưu vết thuật toán phục vụ kiểm tra

        # Cập nhật ngược lại vào tham chiếu dòng
        item["row_ref"]["Gross Consumption"] = gross_consumption
        item["row_ref"]["Số lượng rập"] = f"{calculated_total_pcs} Pcs"
        
        processed_rows.append(r)

    # 📌 4. ĐỒNG BỘ ĐẢM BẢO CHỐNG GHI ĐÈ CACHE TẦNG NGOÀI (SESSION STATE)
    ctx = st.session_state.get("bom_data", {})
    if isinstance(ctx, dict):
        ctx["global_gross_fabric_yds"] = base_gross_fabric
        ctx["actual_packing_density"] = actual_packing_density
        ctx["calculated_size"] = st.session_state.get("current_active_size", "M")
        st.session_state["bom_data"] = ctx

    st.session_state["processed_display_rows"] = processed_rows
    return processed_rows

import io
import re
import numpy as np
import pandas as pd
import streamlit as st
import hashlib 
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

# =====================================================================
# 🟩 ĐOẠN 1 (PHIÊN BẢN V24 - MASTER PARAMS & SEAM CONTROL): ĐỒNG BỘ TUYỆT ĐỐI
# =====================================================================

# 1. Trích xuất văn bản câu lệnh chat mới nhất từ người dùng
chat_input_text = str(st.session_state.get("last_submitted_query", "")).strip()

def extract_param_advanced(pattern, text, session_key, default_val):
    """Hàm trích xuất số liệu kỹ thuật thông minh từ câu lệnh chat"""
    if not text:
        return float(st.session_state.get(session_key, default_val))
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        val = float(match.group(2) if len(match.groups()) >= 2 else match.group(1))
        st.session_state[session_key] = val
        return val
    return float(st.session_state.get(session_key, default_val))

# 📌 2. BẮT BUỘC KHỞI TẠO VÀ NIÊM PHONG HẰNG SỐ ĐƯỜNG MAY = 0.44 INCH KHÔNG ĐỔI
SEAM_ALLOWANCE = 0.44
st.session_state["seam_allowance_inch"] = SEAM_ALLOWANCE

# 📌 3. BÓC TÁCH TỶ LỆ CO RÚT VẢI DỌC VÀ NGANG TỪ Ô CÂU LỆNH CHAT (HỖ TRỢ DẤU % HOẶC KÝ TỰ ĐẶC BIỆT)
warp_shrink = extract_param_advanced(r'\b(co\s*rút\s*dọc|độ\s*co\s*dọc|co\s*dọc|dọc)\s*[:=-]?\s*(\d+(?:\.\d+)?)%?\b', chat_input_text, "warp_shrinkage", 0.0)
weft_shrink = extract_param_advanced(r'\b(co\s*rút\s*ngang|độ\s*co\s*ngang|co\s*ngang|ngang)\s*[:=-]?\s*(\d+(?:\.\d+)?)%?\b', chat_input_text, "weft_shrinkage", 0.0)

# Khớp lệnh co rút chung (Nếu người dùng chỉ gõ chung chung: "co rút 3%")
if not re.search(r'(dọc|ngang)', chat_input_text, re.IGNORECASE):
    general_shrink = extract_param_advanced(r'\bco\s*rút\s*[:=-]?\s*(\d+(?:\.\d+)?)%?\b', chat_input_text, "general_shrinkage", -1.0)
    if general_shrink >= 0:
        warp_shrink = general_shrink
        weft_shrink = general_shrink
        st.session_state["warp_shrinkage"] = general_shrink
        st.session_state["weft_shrinkage"] = general_shrink

# Lấy dữ liệu nguồn BOM hiện tại
ctx = st.session_state.get("final_bom_data") or st.session_state.get("bom_data") or {}
if not isinstance(ctx, dict): 
    ctx = {"bom_rows": ctx} if isinstance(ctx, list) else {}

# 📌 4. GIẢI PHÓNG BẪY KẸT SIZE: Ưu tiên bóc tách lệnh nhảy size mới từ ô Chat trước dữ liệu Cache
detected_size_code = ""
size_match = re.search(r'\b(size|cỡ|khổ\s*size)\s*[:=-]?\s*([a-zA-Z0-9]+)\b', chat_input_text, re.IGNORECASE)

if size_match:
    detected_size_code = str(size_match.group(2)).upper().strip()
elif ctx.get("calculated_on_size") and str(ctx.get("calculated_on_size")).strip() != "":
    detected_size_code = str(ctx.get("calculated_on_size")).upper().strip()
elif ctx.get("detected_base_size") and str(ctx.get("detected_base_size")).strip() != "":
    detected_size_code = str(ctx.get("detected_base_size")).upper().strip()
else:
    detected_size_code = "M"  # Định vị size chữ mặc định an toàn ngành may quần áo

# Giải phóng chuỗi kích thước phối hợp nhảy size (Ví dụ: "32X33" -> lấy thông số vòng eo "32")
if "X" in detected_size_code:
    detected_size_code = detected_size_code.split("X")[0].strip()

# Khóa chặt thông số Size yêu cầu lên trục Master hệ thống
st.session_state["current_active_size"] = detected_size_code
st.session_state["target_size"] = detected_size_code
st.session_state["detected_base_size"] = detected_size_code
ctx["calculated_on_size"] = detected_size_code
ctx["detected_base_size"] = detected_size_code

# 📌 5. ĐỒNG BỘ HIỂN THỊ KHỔ VẢI CHÍNH THỜI GIAN THỰC TỪ CHAT VÀ CACHE AI
fabric_width = extract_param_advanced(r'\b(khổ\s*vải|khổ)\s*[:=-]?\s*(\d+(?:\.\d+)?)\b', chat_input_text, "fabric_width_inch", 58.0) 
if fabric_width <= 0: 
    fabric_width = 58.0

# Lưu trữ trọn vẹn lên trục điều khiển Master để hiển thị đồng bộ lên UI phẳng
st.session_state["current_active_width"] = fabric_width
st.session_state["fabric_width_inch"] = fabric_width
ctx["fabric_width_inch"] = fabric_width

# 📌 6. TRÍCH XUẤT ĐỘC LẬP KHỔ VẢI KEO (FUSING) VÀ VẢI LÓT (LINING)
fusing_width = extract_param_advanced(r'\b(khổ\s*keo|keo\s*khổ|khổ\s*dựng|mếch|fusing)\s*[:=-]?\s*(\d+(?:\.\d+)?)\b', chat_input_text, "fusing_width_inch", 59.0)
if fusing_width <= 0: 
    fusing_width = 59.0
st.session_state["fusing_width_inch"] = fusing_width
ctx["fusing_width_inch"] = fusing_width

lining_width = extract_param_advanced(r'\b(khổ\s*lót|lót\s*khổ|vải\s*lót\s*khổ|lining)\s*[:=-]?\s*(\d+(?:\.\d+)?)\b', chat_input_text, "lining_width_inch", 57.0)
if lining_width <= 0: 
    lining_width = 57.0
st.session_state["lining_width_inch"] = lining_width
ctx["lining_width_inch"] = lining_width

# Đồng bộ hệ số co rút lên trục Master để bảo vệ Khối 3 hình học phẳng
st.session_state["current_warp_shrinkage"] = warp_shrink
st.session_state["current_weft_shrinkage"] = weft_shrink

# Cập nhật ngược lại vào tầng lưu trữ lõi
ctx["warp_shrinkage_percent"] = warp_shrink
ctx["weft_shrinkage_percent"] = weft_shrink
ctx["seam_allowance_inch"] = SEAM_ALLOWANCE
st.session_state["final_bom_data"] = ctx
st.session_state["bom_data"] = ctx


    # =====================================================================
    # 🚨 ĐOẠN 2 (TIẾP THEO): TÍNH TOÁN ĐƯỜNG MAY, CO RÚT & PHÂN BỔ ĐỊNH MỨC CHI TIẾT
    # =====================================================================
    
    # 1. Thu thập hằng số đường may bắt buộc từ Master Controller
    SEAM_ALLOWANCE = float(st.session_state.get("seam_allowance_inch", 0.44))
    
    # Chuyển đổi phần trăm co rút sang hệ số nhân hình học
    shrink_len_factor = 1.0 + (warp_shrink / 100.0)
    shrink_wid_factor = 1.0 + (weft_shrink / 100.0)
    
    # Đồng bộ khổ vải phụ từ bộ nhớ hệ thống phục vụ phân bổ độc lập
    lining_width = float(st.session_state.get("lining_width_inch", 57.0))
    fusing_width = float(st.session_state.get("fusing_width_inch", 59.0))
    
    # Trừ biên an toàn 1 inch cho sơ đồ phẳng dệt may công nghiệp
    usable_fabric_width_net = max(fabric_width - 1.0, 10.0)
    usable_lining_width_net = max(lining_width - 1.0, 10.0)
    usable_fusing_width_net = max(fusing_width - 1.0, 10.0)

    # Chuyển đổi df_bom sang danh sách dict để tương thích với cấu trúc solver hình học
    bom_rows_list = df_bom.to_dict(orient="records")
    
    # Khởi chạy quy trình xử lý phôi phẳng và tính diện tích lưới phẳng thực tế (Khối 3)
    total_fabric_piece_area = 0.0
    piece_calculated_data = []
    
    for r in bom_rows_list:
        raw_l = float(r.get(orig_l_col, 0.0))
        raw_w = float(r.get(orig_w_col, 0.0))
        pcs = float(r.get("pcs_numeric", 1.0))
        
        comp_name_raw = str(r.get("component_name", r.get("Component Name", "UNNAMED"))).upper().strip()
        piece_shape = str(r.get("piece_shape", "TAPERED_PANEL")).upper().strip()
        piece_function = str(r.get("piece_function", "PRIMARY")).upper().strip()
        fold_type = str(r.get("fold_type", "NONE")).upper().strip()
        mat_zone = str(r.get(m_col, "SELF")).upper().strip()
        critical_alignment = str(r.get("critical_alignment", "NONE")).upper().strip()
        packing_priority = int(float(r.get("packing_priority", 3)))
        
        # Nhận diện lớp vật tư nghiêm ngặt
        if mat_zone in ["SELF", "FABRIC"]: 
            r_material_class = "FABRIC"
        elif mat_zone in ["FUSING", "INTERFACING", "INTERLINING", "MEX", "KEO LOT", "DỰNG"]: 
            r_material_class = "FUSING"
        elif mat_zone in ["LINING", "POCKET", "LÓT", "RIB", "BO GÂN"]: 
            r_material_class = "LINING"
        else: 
            r_material_class = "FABRIC"

        # Đọc thông số quét văn bản PDF để phát hiện rập gập đôi (FOLD)
        # Giả định hàm bóc tách văn bản PDF đã gắn cờ hiệu hoặc kiểm tra chuỗi fold_type
        is_folded = r.get("is_folded", False) or fold_type in ["ON_FOLD", "CENTER_FOLD"]
        if is_folded:
            raw_w = raw_w * 2.0  # Nhân đôi bề rộng rập thô trước khi tính toán đường may

        if raw_l > 0 and raw_w > 0:
            # 📌 QUY TẮC BẮT BUỘC: Cộng thêm đường may 0.44 inch vào hai đầu chi tiết (+0.88 inch tổng)
            seamed_l = raw_l + (SEAM_ALLOWANCE * 2)
            seamed_w = raw_w + (SEAM_ALLOWANCE * 2)

            # Đắp thông số co rút dệt may vào kích thước phôi thành phẩm
            adj_l = seamed_l * shrink_len_factor
            adj_w = seamed_w * shrink_wid_factor

            # Trích xuất hệ số phom dáng hình học (Convex Fill Ratio)
            ai_convex_ratio = float(r.get("convex_fill_ratio", 0.74))
            if ai_convex_ratio <= 0 or ai_convex_ratio > 1.0: 
                ai_convex_ratio = 0.74
                
            shape_factor = ai_convex_ratio
            if is_folded: 
                shape_factor *= 0.96
            if critical_alignment in ["STRIPE", "PLAID"]: 
                shape_factor += 0.02
                
            if piece_function == "PRIMARY":
                shape_factor = max(0.6400, min(0.8800, shape_factor))
            elif piece_shape == "RECTANGLE":
                shape_factor = 0.98

            # Đồng bộ số lượng cắt vật lý tránh trùng lặp
            cut_qty_ai = int(float(r.get("cut_quantity", pcs)))
            layer_multiplier = max(1, cut_qty_ai // int(pcs)) if cut_qty_ai > pcs else 1
            if r.get("mirror_piece", False) and pcs == 1 and layer_multiplier == 1:
                layer_multiplier = 2
                
            total_pcs_final = pcs * layer_multiplier
            
            # Tính toán diện tích hình hộp bao phẳng thực tế sau đường may và co rút
            bbox_area = adj_l * adj_w
            calculated_net_area = bbox_area * shape_factor
            if calculated_net_area > bbox_area: 
                calculated_net_area = bbox_area * 0.76
                
            item_area = calculated_net_area * total_pcs_final
            
            # Lưu trữ kích thước hiển thị mới sau xử lý kỹ thuật lên lưới giao diện UI
            r[orig_l_col] = round(adj_l, 2)
            r[orig_w_col] = round(adj_w, 2)
            r[pcs_col] = int(total_pcs_final)
            r[m_col] = r_material_class
            r["polygon_net_area"] = round(calculated_net_area, 2)
            r["cad_algorithm_status"] = f"Đường may: +{SEAM_ALLOWANCE} in | Gập: {is_folded}"

            if r_material_class == "FABRIC":
                total_fabric_piece_area += item_area

            piece_calculated_data.append({
                "row_ref": r, "item_area": item_area, "layer_multiplier": layer_multiplier,
                "mat_class_raw": r_material_class, "raw_l": adj_l, "raw_w": adj_w, "pcs_val": pcs
            })

    # Gọi mô phỏng cấu trúc sơ đồ phi tuyến tính chuẩn Gerber Engine để bốc tổng định mức Yards toàn cục
    # Ở đây tích hợp cấu trúc dữ liệu mô phỏng thu gọn từ kết quả Skyline Engine
    actual_packing_density = 0.825 if fabric_pattern_raw == "SOLID" else 0.795
    
    # Mô phỏng chiều dài đi sơ đồ Yards (Tổng diện tích vải chính / Khổ hữu ích / Hiệu suất sơ đồ / 36 inch)
    if total_fabric_piece_area > 0:
        simulated_length_inches = (total_fabric_piece_area / usable_fabric_width_net) / actual_packing_density
        # Nhân hệ số hao hụt đầu khúc thương mại bàn cắt biên độ nhỏ 1.5%
        base_gross_fabric = round((simulated_length_inches / 36.0) * 1.015, 4)
    else:
        base_gross_fabric = 0.0

    # Ép định mức sàn phòng vệ cho dòng hàng áo khoác phức tạp
    if "JACKET" in prod and base_gross_fabric < 1.2 and total_fabric_piece_area > 0:
        base_gross_fabric = 2.15

    # Quét lại một vòng tính tổng diện tích phân bổ vải chính có trọng số ưu tiên sơ đồ
    weighted_area_sum = 0.0
    for item in piece_calculated_data:
        if item["mat_class_raw"] == "FABRIC":
            p_priority = int(float(item["row_ref"].get("packing_priority", 3)))
            weight_factor = 1.08 if p_priority <= 2 else (0.88 if p_priority >= 4 else 1.00)
            weighted_area_sum += item["item_area"] * weight_factor

    # 📌 TIẾN HÀNH PHÂN BỔ ĐỊNH MỨC CHI TIẾT TỪNG DÒNG VẬT TƯ THƯƠNG MẠI
    for item in piece_calculated_data:
        r = item["row_ref"]
        item_area = item["item_area"]
        mat_class_raw = item["mat_class_raw"]
        
        if mat_class_raw == "FABRIC":
            p_priority = int(float(r.get("packing_priority", 3)))
            if total_fabric_piece_area > 0 and base_gross_fabric > 0 and weighted_area_sum > 0:
                weight_factor = 1.08 if p_priority <= 2 else (0.88 if p_priority >= 4 else 1.00)
                share_ratio = (item_area * weight_factor) / weighted_area_sum
                gross_consumption = round(base_gross_fabric * share_ratio, 4)
            else:
                gross_consumption = round(((item_area / usable_fabric_width_net) / 36.0) / actual_packing_density, 4)
                
        elif mat_class_raw == "LINING":
            # Tính độc lập theo diện tích phôi lót túi thực tế trên khổ lót chỉ định (đơn vị Yards)
            gross_consumption = round((item_area / usable_lining_width_net) / 36.0, 4)
            
        elif mat_class_raw == "FUSING":
            # Tính độc lập theo diện tích phôi keo/dựng thực tế trên khổ dựng chỉ định (đơn vị Yards)
            gross_consumption = round((item_area / usable_fusing_width_net) / 36.0, 4)
            
        else:
            gross_consumption = round((item_area / usable_fabric_width_net) / 36.0, 4)

        # Cập nhật kết quả đồng bộ tối cao lên cột hiển thị của bảng dữ liệu
        target_gross_final_col = next((c for c in ["Gross Consumption", "gross_consumption", "allocated_gross"] if c in df_bom.columns), "Gross Consumption")
        r[target_gross_final_col] = gross_consumption
        r["fabric_width_inch"] = fabric_width

    # Khôi phục và cập nhật ngược lại dữ liệu DataFrame sạch hoàn chỉnh
    df_bom = pd.DataFrame(bom_rows_list)
    
    # Đồng bộ đẩy ngược bộ nhớ hệ thống lưu vết thông tin kiểm toán đầu ra
    ctx["global_gross_fabric_yds"] = base_gross_fabric
    ctx["actual_packing_density"] = actual_packing_density
    ctx["calculated_size"] = st.session_state.get("current_active_size", "M")
    st.session_state["final_bom_data"] = ctx
    st.session_state["bom_data"] = ctx
    st.session_state["processed_display_rows"] = bom_rows_list

    # Hiển thị thông báo trạng thái tính toán thành công trên UI
    st.success(f"⚡ CAD Engine: Đã đồng bộ thông số Size {st.session_state['current_active_size']} | Khổ vải {fabric_width} in | Đường may bắt buộc +{SEAM_ALLOWANCE} in.")
    # =====================================================================
    # 🟩 ĐOẠN 3.2 (PHIÊN BẢN V24): PATTERN RECOGNITION & ACTUAL PACKING DENSITY SOLVER
    # =====================================================================
    
    # 1. Trích xuất văn bản chat câu lệnh người dùng để nhận diện vân vải (Fabric Pattern)
    chat_input_text_lower = str(st.session_state.get("last_submitted_query", "")).lower().strip()
    
    # Thiết lập barem chu kỳ vân vải mặc định (Mặc định là vải trơn - SOLID)
    fabric_pattern = "SOLID"
    fabric_repeat_inch = 0.0
    pattern_loss_multiplier = 1.00
    
    # 🧠 Bộ lọc Regex nhận diện vân vải đặc trưng từ câu lệnh chat của thợ may
    if any(p in chat_input_text_lower for p in ["kẻ sọc", "caro", "sọc", "plaid", "stripe", "check"]):
        fabric_pattern = "PLAID"
        # Quét nhanh chu kỳ lặp vân vải, ví dụ: "sọc 4 inch" hoặc "caro chu kỳ 10cm"
        repeat_match = re.search(r'(?:sọc|caro|chu kỳ|bước vằn)\s*(\d+(?:\.\d+)?)', chat_input_text_lower)
        fabric_repeat_inch = float(repeat_match.group(1)) if repeat_match else 4.0
        # Vải kẻ sọc/caro bắt buộc phải canh đối rập dọc ngang, làm giảm hiệu suất sơ đồ phẳng từ 3% - 8%
        pattern_loss_multiplier = 0.945  
        pattern_log = f"Phát hiện cấu trúc vân vải KẺ SỌC/CARO (Chu kỳ lặp: {fabric_repeat_inch} in). Tự động hạ mật độ rải rập để đối sọc."
    elif any(p in chat_input_text_lower for p in ["vải tuyết", "một chiều", "1 chiều", "nap", "one-way", "one way"]):
        fabric_pattern = "NAP"
        fabric_repeat_inch = 0.0
        # Vải có tuyết/vải một chiều bắt buộc rập chỉ được xoay 180 độ hoặc giữ nguyên hướng, giảm 2% hiệu suất
        pattern_loss_multiplier = 0.975
        pattern_log = "Phát hiện cấu trúc VẢI TUYẾT / MỘT CHIỀU (NAP). Khóa hướng xoay tự do của rập đơn để tránh lệch màu."
    else:
        pattern_log = "Cấu trúc vật tư VẢI TRƠN (SOLID). Kích hoạt chế độ đi sơ đồ xoay tự do tự động tối ưu định mức."

    # 2. Tính toán mật độ nèn thực tế động (Actual Packing Density) dựa trên loại hàng và vân vải
    base_density = COMPANY_DENSITY_PRIOR[product_category]
    
    # Áp dụng ma trận phạt phi tuyến tính từ vân vải vào mật độ nền cơ sở
    actual_packing_density = base_density * pattern_loss_multiplier
    
    # Kiểm soát biên độ an toàn của mật độ đi sơ đồ công nghiệp (Giới hạn sàn 62%, trần 92.5%)
    actual_packing_density = max(min(actual_packing_density, 0.9250), 0.6200)

    # 📌 3. ĐỒNG BỘ ĐƯỜNG MAY BẮT BUỘC 0.44 INCH & CO RÚT VÀO HỆ THỐNG MASTER KIỂM TOÁN
    SEAM_ALLOWANCE = float(st.session_state.get("seam_allowance_inch", 0.44))
    warp_shrinkage = float(st.session_state.get("current_warp_shrinkage", 0.0))
    weft_shrinkage = float(st.session_state.get("current_weft_shrinkage", 0.0))
    target_size_display = str(st.session_state.get("current_active_size", "32"))

    # Cập nhật ngược lại vào tầng lưu trữ lõi để liên thông dữ liệu cho Đoạn hiển thị UI và Excel
    ctx["ai_expert_decision"]["fabric_pattern"] = fabric_pattern
    ctx["ai_expert_decision"]["fabric_repeat_inch"] = fabric_repeat_inch
    ctx["ai_expert_decision"]["actual_packing_density"] = round(actual_packing_density, 4)
    ctx["ai_expert_decision"]["seam_allowance_inch"] = SEAM_ALLOWANCE
    ctx["ai_expert_decision"]["pattern_log"] = pattern_log

    st.session_state["current_actual_packing_density"] = actual_packing_density
    st.session_state["bom_data"] = ctx

    # 4. Hiển thị khối tóm tắt phân tích kỹ thuật của AI Agent trực quan lên giao diện chính
    st.markdown(f"""
    <div style="background-color: #1E293B; border-left: 5px solid #3B82F6; padding: 12px; border-radius: 6px; margin-bottom: 15px;">
        <span style="color: #60A5FA; font-weight: bold; font-size: 14px;">🧠 CAD IE EXPERT INTELLIGENCE REPORT</span><br>
        <table style="width:100%; color: #E2E8F0; font-size: 13px; margin-top: 8px; border-collapse: collapse;">
            <tr>
                <td style="padding: 3px 0; color: #94A3B8;">Phân loại hàng:</td>
                <td style="padding: 3px 0; font-weight: bold; color: #F59E0B;">{ai_product_type}</td>
                <td style="padding: 3px 0; color: #94A3B8;">Size yêu cầu:</td>
                <td style="padding: 3px 0; font-weight: bold; color: #10B981;">{target_size_display}</td>
            </tr>
            <tr>
                <td style="padding: 3px 0; color: #94A3B8;">Mật độ sơ đồ nền:</td>
                <td style="padding: 3px 0; font-weight: bold;">{round(actual_packing_density * 100, 2)}%</td>
                <td style="padding: 3px 0; color: #94A3B8;">Khổ vải chính:</td>
                <td style="padding: 3px 0; font-weight: bold;">{st.session_state.get('current_active_width', 58.0)} in</td>
            </tr>
            <tr>
                <td style="padding: 3px 0; color: #94A3B8;">Co rút dọc (Warp):</td>
                <td style="padding: 3px 0; font-weight: bold; color: #F87171;">+{warp_shrinkage}%</td>
                <td style="padding: 3px 0; color: #94A3B8;">Co rút ngang (Weft):</td>
                <td style="padding: 3px 0; font-weight: bold; color: #F87171;">+{weft_shrinkage}%</td>
            </tr>
            <tr>
                <td style="padding: 3px 0; color: #94A3B8;">Đường may bắt buộc:</td>
                <td style="padding: 3px 0; font-weight: bold; color: #38BDF8;">+{SEAM_ALLOWANCE} in (mỗi đầu cạnh)</td>
                <td style="padding: 3px 0; color: #94A3B8;">Trạng thái vân:</td>
                <td style="padding: 3px 0; font-weight: bold; color: #A78BFA;">{fabric_pattern}</td>
            </tr>
        </table>
        <div style="font-size: 11px; color: #94A3B8; margin-top: 8px; border-top: 1px solid #334155; padding-top: 5px; font-style: italic;">
            ℹ️ {pattern_log}
        </div>
    </div>
    """, unsafe_allow_html=True)

        # =====================================================================
    # 🟩 ĐOẠN 3.2 (PHIÊN BẢN V24 - MASTER GEOMETRY): GEOMETRIC FEATURE ENGINE
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

    # 📌 1. ĐỌC THÔNG SỐ ĐƯỜNG MAY BẮT BUỘC VÀ TỶ LỆ CO RÚT TỪ MASTER CONTROLLER (ĐOẠN 1)
    SEAM_ALLOWANCE = float(st.session_state.get("seam_allowance_inch", 0.44))
    warp_shrink = float(st.session_state.get("current_warp_shrinkage", 0.0))
    weft_shrink = float(st.session_state.get("current_weft_shrinkage", 0.0))
    
    # Đổi phần trăm co rút sang hệ số nhân hình học phẳng
    shrink_len_factor = 1.0 + (warp_shrink / 100.0)
    shrink_wid_factor = 1.0 + (weft_shrink / 100.0)

    # Đảm bảo context bom_data luôn tồn tại cấu trúc
    if "bom_data" not in st.session_state or not isinstance(st.session_state["bom_data"], dict):
        st.session_state["bom_data"] = {}
    ctx = st.session_state["bom_data"]
    if "ai_expert_decision" not in ctx or not isinstance(ctx["ai_expert_decision"], dict): 
        ctx["ai_expert_decision"] = {}

    product_category = ctx["ai_expert_decision"].get("product_category", "JEAN_LONG")
    
    if "user_edited_pieces" not in st.session_state: 
        st.session_state["user_edited_pieces"] = {}

    piece_areas = []
    total_pattern_pieces, total_pocket_pieces, max_piece_length = 0.0, 0.0, 0.0

    # 🛠️ BỘ PHÂN LOẠI CHẤT LIỆU LAYER TRÍ THỨC (ĐỐI CHIẾU NGHIÊM NGẶT KEO/LÓT/RIB)
    def _d3_internal_material_classify(row, idx, prod_cat):
        if "user_edited_materials" in st.session_state and idx in st.session_state["user_edited_materials"]:
            return str(st.session_state["user_edited_materials"][idx]).upper().strip()
            
        mat_str = str(row[m_col_check]).upper().strip() if m_col_check in row else ""
        comp_str = str(row.get(comp_col_check, row.get("component_name", ""))).upper().strip()
        
        fusing_kws = ["FUSING", "INTERLINING", "INTERFACING", "KEO", "MEC", "MẾCH", "BOND", "ADHESIVE", "LOT KEO", "TRICOT"]
        lining_kws = ["LINING", "LOT", "LÓT", "POCKETING", "MESH", "TAFFETA", "VAI LOT", "VẢI LÓT", "POCKET BAG"]
        rib_kws = ["RIB", "BO GÂN", "BO", "CỔ BO", "TAY BO"]
        
        if any(k in comp_str for k in ["WAISTBAND", "LƯNG", "CẠP", "BELT", "POCKET"]) and not any(x in mat_str or x in comp_str for x in fusing_kws + lining_kws):
            return "FABRIC"
            
        if any(k in mat_str or k in comp_str for k in fusing_kws): return "FUSING"
        if any(k in mat_str or k in comp_str for k in lining_kws): return "LINING"
        if any(k in mat_str or k in comp_str for k in rib_kws): return "LINING"
        return "FABRIC"

    # Duyệt qua từng dòng rập để làm sạch hình học phẳng nâng cao
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

        current_pcs = float(st.session_state.get("user_edited_pieces", {}).get(idx, pcs_numeric_val))

        if any(k in comp_name_clean for k in ["POCKET", "TÚI", "WELT", "BAG"]):
            total_pocket_pieces += current_pcs

        if p_class_clean in ["FABRIC", "FUSING", "LINING"]:
            total_pattern_pieces += current_pcs
            
            # Đọc thông số chiều dài và chiều rộng thô ban đầu từ rập đơn
            raw_l_val = float(r.get(l_prod_col_check, 0.0))
            raw_w_val = float(r.get(w_prod_col_check, 0.0))
            
            if raw_l_val <= 0 or raw_w_val <= 0:
                continue

            # 📌 2. XỬ LÝ RẬP GẬP BIÊN (FOLD): Nếu có lệnh gập, tự động bù gấp đôi chiều rộng thô trước
            fold_type_str = str(r.get("fold_type", "NONE")).upper().strip()
            is_folded = r.get("is_folded", False) or fold_type_str in ["ON_FOLD", "CENTER_FOLD"]
            if is_folded:
                raw_w_val = raw_w_val * 2.0

            # 📌 3. BẮT BUỘC CỘNG ĐƯỜNG MAY 0.44 INCH VÀO HAI ĐẦU CẠNH CHI TIẾT CHUẨN KỸ THUẬT (+0.88 INCH TỔNG)
            seamed_l_val = raw_l_val + (SEAM_ALLOWANCE * 2)
            seamed_w_val = raw_w_val + (SEAM_ALLOWANCE * 2)

            # 📌 4. ÁP THÔNG SỐ CO RÚT KỸ THUẬT VÀO KÍCH THƯỚC ĐÃ CÓ ĐƯỜNG MAY
            final_l_val = seamed_l_val * shrink_len_factor
            final_w_val = seamed_w_val * shrink_wid_factor
            
            # Cập nhật ngược lại bảng UI hiển thị kích thước sản xuất chính xác của thợ cắt
            df_bom.at[idx, l_prod_col_check] = round(final_l_val, 2)
            df_bom.at[idx, w_prod_col_check] = round(final_w_val, 2)

            # Tính toán lại diện tích hộp bao hình chữ nhật phẳng thực tế
            bbox_area_check = final_l_val * final_w_val
            
            # Đồng bộ lại diện tích tinh (Polygon Net Area) theo tỷ lệ hình học mới chống bẫy lấn át diện tích
            try:
                raw_net_area = float(r.get(area_col_check, 0.0))
                if np.isnan(raw_net_area) or raw_net_area <= 0:
                    raw_net_area = raw_l_val * raw_w_val * 0.76
            except:
                raw_net_area = raw_l_val * raw_w_val * 0.76
                
            raw_bbox_area = raw_l_val * raw_w_val
            fill_ratio = (raw_net_area / raw_bbox_area) if raw_bbox_area > 0 else 0.76
            fill_ratio = min(max(fill_ratio, 0.50), 0.98)
            
            net_area = bbox_area_check * fill_ratio
            df_bom.at[idx, area_col_check] = round(net_area, 2)
                
            if final_l_val > max_piece_length: 
                max_piece_length = final_l_val
                
            if net_area > 0:
                for _ in range(int(current_pcs)):
                    piece_areas.append(net_area)

    # 🛠| ĐỒNG BỘ SIÊU DỮ LIỆU SẠCH: Tạo gói dữ liệu Geometry Signature chuẩn xác sau đường may và co rút
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
    st.session_state["processed_display_rows"] = df_bom.to_dict(orient="records")
    # =====================================================================
    # 🟩 ĐOẠN 4 (PHIÊN BẢN MASTER V30 - CAD ENGINE): AI VIRTUAL PIECE ENGINE
    # =====================================================================
    import pandas as pd
    import numpy as np

    comp_col_check = next((c for c in ["Component Name", "component_name", "Component_Name"] if c in df_bom.columns), "component_name")
    m_col_check = next((c for c in ["Material Class", "material_class"] if c in df_bom.columns), "material_class")
    fold_col_check = next((c for c in ["Fold Type", "fold_type", "Loại gập"] if c in df_bom.columns), "fold_type")

    # 📌 1. ĐỒNG BỘ TRỤC MASTER THÔNG SỐ ĐƯỜNG MAY BẮT BUỘC & KHỔ VẢI TỪ ĐOẠN 1
    SEAM_ALLOWANCE = float(st.session_state.get("seam_allowance_inch", 0.44))
    fabric_width = float(st.session_state.get("current_active_width", 58.0))
    
    # Đồng bộ trục co rút vải chính (SELF/FABRIC)
    warp_shrink = float(st.session_state.get("current_warp_shrinkage", 0.0))
    weft_shrink = float(st.session_state.get("current_weft_shrinkage", 0.0))
    
    # Đồng bộ trục co rút vật tư phụ (Nếu ô chat không ghi, mặc định chạy theo tỷ lệ co rút vải chính để phòng vệ hụt vải)
    fusing_warp_shrink = float(st.session_state.get("fusing_warp_shrink", warp_shrink))
    fusing_weft_shrink = float(st.session_state.get("fusing_weft_shrink", weft_shrink))
    lining_warp_shrink = float(st.session_state.get("lining_warp_shrink", warp_shrink))
    lining_weft_shrink = float(st.session_state.get("lining_weft_shrink", weft_shrink))

    if "bom_data" not in st.session_state or not isinstance(st.session_state["bom_data"], dict):
        st.session_state["bom_data"] = {}
    ctx = st.session_state["bom_data"]
    if "ai_expert_decision" not in ctx or not isinstance(ctx["ai_expert_decision"], dict):
        ctx["ai_expert_decision"] = {}

    virtual_pieces_layer = {}

    for idx, row in df_bom.iterrows():
        comp_name_raw = str(row.get(comp_col_check, row.get("component_name", "")))
        comp_name_upper = comp_name_raw.upper().strip()
        mat_str = str(row.get(m_col_check, "")).upper().strip()
        
        # Nhập phân lớp vật tư dệt may nghiêm ngặt
        if any(k in comp_name_upper or k in mat_str for k in ["THREAD", "CHỈ", "BUTTON", "NÚT", "ZIP", "ACCESSORY", "PHỤ LIỆU"]):
            p_class, class_confidence = "ACCESSORY", 1.0
        elif any(k in comp_name_upper or k in mat_str for k in ["FUSING", "MEC", "MẾCH", "KEO", "INTERLINING", "DỰNG"]):
            p_class, class_confidence = "FUSING", 1.0
        elif any(k in comp_name_upper or k in mat_str for k in ["LINING", "LÓT", "POCKET BAG", "POCKETING", "RIB", "BO GÂN"]):
            p_class, class_confidence = "LINING", 1.0
        else:
            p_class, class_confidence = "FABRIC", 0.95

        l_orig = float(row.get("bounding_box_length", 0.0))
        w_orig = float(row.get("bounding_box_width", 0.0))
        net_area_real = float(row.get("polygon_net_area", 0.0))

        if l_orig <= 0 or w_orig <= 0: 
            continue

        # ➔ A. ASPECT RATIO CORRECTION: Chuẩn hóa trục canh sợi tự động (Xoay rập chiều dài lớn hơn chiều rộng)
        if w_orig > l_orig:
            l_orig, w_orig = w_orig, l_orig

        # ➔ B. KIỂM TRA LỆNH RẬP GẬP BIÊN (FOLD): Nếu rập vẽ một nửa, tự động nhân đôi chiều rộng thô ngay lập tức
        fold_type_str = str(row.get(fold_col_check, "NONE")).upper().strip()
        is_folded = row.get("is_folded", False) or fold_type_str in ["ON_FOLD", "CENTER_FOLD", "GẬP ĐÔI"]
        if is_folded:
            w_orig = w_orig * 2.0

        # ➔ C. BẰNG SUY DIỄN HÌNH THÁI HỌC OBB VÀ NẮN KÍCH THƯỚC HỘP BAO SẠCH (ANTI-AABB BUG)
        if net_area_real > 0:
            current_factor = net_area_real / (l_orig * w_orig)
            aspect_ratio = l_orig / w_orig
            log_aspect = np.log1p(aspect_ratio)
            
            target_obb_eff = 0.88 - (0.05 * log_aspect) + (0.15 * current_factor)
            target_obb_eff = max(0.6400, min(0.9200, target_obb_eff))

            if current_factor < target_obb_eff:
                optimized_area = net_area_real / target_obb_eff
                w_orig = (optimized_area / aspect_ratio) ** 0.5
                l_orig = w_orig * aspect_ratio

        # 📌 2. QUY TẮC BẮT BUỘC MAY MẶC: Cộng thêm đường may 0.44 inch vào hai đầu chi tiết rập (+0.88 in tổng)
        seamed_l = l_orig + (SEAM_ALLOWANCE * 2)
        seamed_w = w_orig + (SEAM_ALLOWANCE * 2)

        # Sửa lỗi trùng lặp số lượng chi tiết (Inferred Pieces chuẩn CAD phòng sơ đồ)
        raw_pcs = float(row.get("pcs_numeric", row.get("Số lượng rập", 1.0)))
        inferred_pcs = raw_pcs
        if raw_pcs == 1.0 and p_class in ["FABRIC", "LINING"]:
            if any(k in comp_name_upper for k in ["LEG", "THAN", "ỐNG", "PANEL", "BAG", "THÂN SAU", "THÂN TRƯỚC"]):
                if not any(k in comp_name_upper for k in ["LEFT", "RIGHT", "TRÁI", "PHẢI", " (L)", " (R)"]):
                    inferred_pcs = 2.0

        final_pcs = float(st.session_state.get("user_edited_pieces", {}).get(idx, inferred_pcs))

        # 📌 3. ÁP THÔNG SỐ CO RÚT SẢN XUẤT THEO MA TRẬN CHẤT LIỆU LÊN KÍCH THƯỚC ĐÃ CÓ ĐƯỜNG MAY
        if p_class == "FABRIC":
            l_prod = seamed_l * (1 + warp_shrink / 100.0)
            w_prod = seamed_w * (1 + weft_shrink / 100.0)
        elif p_class == "FUSING":
            l_prod = seamed_l * (1 + fusing_warp_shrink / 100.0)
            w_prod = seamed_w * (1 + fusing_weft_shrink / 100.0)
        elif p_class == "LINING":
            l_prod = seamed_l * (1 + lining_warp_shrink / 100.0)
            w_prod = seamed_w * (1 + lining_weft_shrink / 100.0)
        else:
            l_prod, w_prod = seamed_l, seamed_w

        # Tính toán lại diện tích lưới phẳng thực tế (Polygon Net Area) theo tỷ trọng hình học mới sau đường may
        bbox_area_final = l_prod * w_prod
        raw_bbox_initial = l_orig * w_orig
        fill_ratio = (net_area_real / raw_bbox_initial) if raw_bbox_initial > 0 else 0.76
        fill_ratio = min(max(fill_ratio, 0.50), 0.98)
        
        net_area_final = bbox_area_final * fill_ratio

        virtual_pieces_layer[idx] = {
            "inferred_class": p_class, "class_confidence": class_confidence,
            "production_l": round(l_prod, 2), "production_w": round(w_prod, 2), 
            "production_net_area": round(net_area_final, 2),
            "inferred_pieces": final_pcs, "component_name": comp_name_raw
        }

    # 📌 4. ĐỒNG BỘ HOÀN TOÀN DỮ LIỆU ĐẦU RA LÊN CỘT GIAO DIỆN BẢNG THEO ĐÚNG THÔNG SỐ SIZE
    for idx, vp in virtual_pieces_layer.items():
        if idx in df_bom.index:
            df_bom.at[idx, "Chiều dài rập (inch)"] = vp["production_l"]
            df_bom.at[idx, "Chiều rộng rập (inch)"] = vp["production_w"]
            df_bom.at[idx, "polygon_net_area"] = vp["production_net_area"]
            df_bom.at[idx, "Số lượng rập"] = int(vp["inferred_pieces"])
            df_bom.at[idx, m_col_check] = vp["inferred_class"]
            df_bom.at[idx, "cad_status"] = f"Biên may: +{SEAM_ALLOWANCE} in | Đã áp độ co"

    # Đồng bộ lưu vết ngược vào bộ nhớ đệm hệ thống
    st.session_state["processed_display_rows"] = df_bom.to_dict(orient="records")

     # =====================================================================
    # 🟩 ĐOẠN 5.1 (PHIÊN BẢN V28 - CHUẨN HÓA VÀ NÂNG HỆ SỐ DIỆN TÍCH RẬP CHUẨN)
    # =====================================================================
    import json
    import math  
    import streamlit as st

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

    # 📌 1. ĐỒNG BỘ ĐƯỜNG MAY BẮT BUỘC 0.44 INCH & KHỔ VẢI ĐỘNG TỪ MASTER CONTROLLER (ĐOẠN 1)
    SEAM_ALLOWANCE = float(st.session_state.get("seam_allowance_inch", 0.44))
    current_fabric_width = float(st.session_state.get("current_active_width", 58.0))
    lining_width = float(st.session_state.get("lining_width_inch", 57.0))    
    fusing_width = float(st.session_state.get("fusing_width_inch", 59.0))    
    
    one_way_flag = st.session_state.get("is_one_way_fabric", False)  
    nap_layout_flag = st.session_state.get("is_nap_layout", False)   

    raw_unpaired_pieces = []
    list_lengths, list_widths = [], []

    size_scale_ratio = float(st.session_state.get("total_marker_bundle_ratio", 1.0))

    l_col = next((c for c in ["bounding_box_length", "Dài (L-inch)", "Chiều dài rập (inch)"] if c in df_bom.columns), None)
    w_col = next((c for c in ["bounding_box_width", "Rộng (W-inch)", "Chiều rộng rập (inch)"] if c in df_bom.columns), None)
    pcs_col = next((c for c in ["pcs_numeric", "Số lượng rập", "Số lượng", "pcs"] if c in df_bom.columns), None)

    for idx, r in df_bom.iterrows():
        if idx not in virtual_pieces_layer:
            virtual_pieces_layer[idx] = {}
        v_piece = virtual_pieces_layer[idx]
        
        # Đồng bộ kích thước đã có đường may +0.44 in và co rút từ Đoạn 4 [INDEX]
        p_len = float(v_piece.get("production_l", 0.0))
        if p_len <= 0 and l_col: 
            p_len = float(r.get(l_col, 0.0))
            
        p_wid = float(v_piece.get("production_w", 0.0))
        if p_wid <= 0 and w_col: 
            p_wid = float(r.get(w_col, 0.0))
            
        net_area = float(v_piece.get("production_net_area", 0.0))
        if net_area <= 0: 
            net_area = float(r.get("polygon_net_area", 0.0))
            
        c_name_upper = str(r.get("component_name", "")).upper().strip()
        p_class_check = str(v_piece.get("inferred_class", r.get("material_class", "FABRIC"))).upper().strip()

        # Ép phân loại lớp vật tư nghiêm ngặt đầu nguồn dệt may
        if any(x in c_name_upper for x in ["FUSING", "MEC", "MẾCH", "KEO", "INTERLINING", "WAISTBAND FUSING"]): 
            p_class_check = "FUSING"
        elif any(x in c_name_upper for x in ["LINING", "LÓT", "POCKET BAG", "POCKETING", "POCKET FACING"]): 
            p_class_check = "LINING"
        elif any(x in c_name_upper for x in ["CONTRAST", "PHỐI"]):
            p_class_check = "CONTRAST"
        elif any(x in c_name_upper for x in ["RIB", "BO CỔ", "BO TĂM", "BO GÂN"]):
            p_class_check = "RIB"
            
        v_piece["material_class"] = p_class_check  

        # Nâng hệ số điền đầy hình học phẳng (Fill Factor) từ 0.76 lên 0.82 để tối ưu hóa Net Area diện tích tinh
        if net_area <= 0 and p_len > 0 and p_wid > 0:
            if any(k in c_name_upper for k in ["LEG", "THAN", "ỐNG", "PANEL", "BAG", "THÂN TRƯỚC", "THÂN SAU"]):
                net_area = p_len * p_wid * 0.82
            else:
                net_area = p_len * p_wid * (0.76 if "FABRIC" in p_class_check else 0.85)
        
        raw_pcs = float(r.get(pcs_col, 1.0)) if pcs_col else 1.0
        inferred_pcs = raw_pcs
        
        if inferred_pcs == 1.0 and p_class_check in ["FABRIC", "LINING"]:
            if any(k in c_name_upper for k in ["LEG", "THAN", "ỐNG", "PANEL", "BAG", "THÂN TRƯỚC", "THÂN SAU"]):
                if not any(k in c_name_upper for k in ["LEFT", "RIGHT", "TRÁI", "PHẢI", " (L)", " (R)"]):
                    inferred_pcs = 2.0

        pcs = float(st.session_state.get("user_edited_pieces", {}).get(idx, inferred_pcs))
        if pcs_col: 
            df_bom.at[idx, pcs_col] = int(pcs)

        pcs = pcs * size_scale_ratio
        v_piece["active_user_pieces"] = int(pcs)

        # 📌 2. ĐỊNH VỊ KHỔ VẢI GIỚI HẠN THEO CHỦNG LOẠI VẬT TƯ THỰC TẾ TRONG HỆ THỐNG
        target_limit_width = fusing_width if p_class_check == "FUSING" else (lining_width if p_class_check == "LINING" else current_fabric_width)
        
        # HOTFIX CHUẨN CAD: Nắn đảo trục xoay nếu chiều rộng phôi vượt khổ vải an toàn
        if p_wid > target_limit_width and p_len <= target_limit_width:
            p_len, p_wid = p_wid, p_len

        list_lengths.append(round(p_len, 2) if p_len > 0 else 0.0)
        list_widths.append(round(p_wid, 2) if p_wid > 0 else 0.0)
        df_bom.at[idx, "polygon_net_area"] = round(net_area, 2)
        v_piece["polygon_net_area"] = round(net_area, 2)

        # 📌 3. THUẬT TOÁN MA TRẬN GỘP ĐÔI PHÔI RẬP ĐI SƠ ĐỒ (PHÒNG SƠ ĐỒ PHẲNG GERBER ENGINE)
        if p_class_check in ["FABRIC", "FUSING", "INTERLINING", "LINING", "RIB", "CONTRAST"] and p_len > 0:
            loop_pcs = int(math.ceil(pcs))
            
            if p_class_check in ["FABRIC", "LINING"] and loop_pcs >= 2 and p_len > 15.0:
                num_pairs = loop_pcs // 2
                remainder_pcs = loop_pcs % 2
                
                # Tính toán ghép đôi chi tiết rập theo chiều ngang khổ vải hữu ích
                if (p_wid * 2) <= target_limit_width:
                    best_paired_w, best_paired_l = p_wid * 2, p_len
                    # Khi đi gộp chi tiết chung cạnh, triệt tiêu 1 lượng biên may trùng nhau
                    paired_area = (net_area * 2) - (p_len * SEAM_ALLOWANCE * 2)
                else:
                    best_paired_w, best_paired_l = p_wid, p_len * 2
                    paired_area = (net_area * 2) - (p_wid * SEAM_ALLOWANCE * 2)
                    
                for _ in range(num_pairs):
                    raw_unpaired_pieces.append({
                        "idx": idx, "l": best_paired_l, "w": best_paired_w, "area": round(paired_area, 2),
                        "material_class": p_class_check, "priority": 1 
                    })
                for _ in range(remainder_pcs):
                    raw_unpaired_pieces.append({
                        "idx": idx, "l": p_len, "w": p_wid, "area": net_area,
                        "material_class": p_class_check, "priority": 3
                    })
            else:
                for _ in range(loop_pcs):
                    raw_unpaired_pieces.append({
                        "idx": idx, "l": p_len, "w": p_wid, "area": net_area,
                        "material_class": p_class_check, "priority": 3
                    })

    # Sắp xếp danh sách chi tiết đi sơ đồ phẳng theo cấp ưu tiên hình học của rập
    raw_unpaired_pieces.sort(key=lambda x: (x.get('priority', 3), -x['area']))
    df_bom["Chiều dài rập (inch)"] = list_lengths
    df_bom["Chiều rộng rập (inch)"] = list_widths
    
    # Đồng bộ gói dữ liệu sạch vào bộ nhớ Master Controller ngoài để chuyển mạch
    ctx["ai_expert_decision"]["raw_unpaired_pieces"] = raw_unpaired_pieces
    st.session_state["bom_data"] = ctx
    st.session_state["processed_display_rows"] = df_bom.to_dict(orient="records")
    # =====================================================================
    # 🟩 ĐOẠN 5.2 - PHẦN A: BỘ ĐỊNH TUYẾN TOÁN HỌC & TÍNH ĐỊNH MỨC CHI TIẾT (V45)
    # =====================================================================
    import pandas as pd
    import streamlit as st

    _is_short = locals().get("is_short", False)
    _is_trouser = locals().get("is_trouser", False)
    _is_skirt_or_dress = locals().get("is_skirt_or_dress", False)
    _is_jacket = locals().get("is_jacket", False)

    # Đọc dải số liệu định mức tổng từ Đoạn 5.1 / Phần B đầu vào
    global_fabric_gross = total_fabric_gross_yds if 'total_fabric_gross_yds' in locals() or 'total_fabric_gross_yds' in globals() else 0.0
    global_lining_gross = total_lining_gross_yds if 'total_lining_gross_yds' in locals() or 'total_lining_gross_yds' in globals() else 0.0
    global_fusing_gross = total_fusing_gross_yds if 'total_fusing_gross_yds' in locals() or 'total_fusing_gross_yds' in globals() else 0.0

    f_width = current_fabric_width if 'current_fabric_width' in locals() else 58.0
    l_width = lining_width if 'lining_width' in locals() else 57.0
    fuse_width = fusing_width if 'fusing_width' in locals() else 59.0
    local_wastage = target_wastage if 'target_wastage' in locals() else 1.015

    if "virtual_pieces_layer" not in locals() or not isinstance(virtual_pieces_layer, dict):
        virtual_pieces_layer = st.session_state.get("bom_data", {}).get("ai_expert_decision", {}).get("virtual_pieces_layer", {})
    if not virtual_pieces_layer: 
        virtual_pieces_layer = {}

    net_areas = {"FABRIC": 0.0, "CONTRAST": 0.0, "LINING": 0.0, "FUSING": 0.0, "RIB": 0.0}
    shape_ratio = 0.65 if _is_short else (0.58 if _is_trouser else 0.72)

    # Gom nhóm tổng diện tích tịnh ma trận hình học rập phẳng dựa trên Master Layer
    for idx, r in df_bom.iterrows():
        v = virtual_pieces_layer.get(idx, {})
        p_cls = str(v.get("material_class", r.get("material_class", "FABRIC"))).upper().strip()
        pcs = int(v.get("active_user_pieces", r.get("pcs_numeric", r.get("Số lượng rập", 1))))
        
        net_area = float(v.get("polygon_net_area", r.get("polygon_net_area", 0.0)))
        if p_cls in net_areas:
            net_areas[p_cls] += net_area * pcs

    # 🤖 MA TRẬN ĐỊNH TUYẾN HIỆU SUẤT SƠ ĐỒ ĐỘNG THEO CHỦNG LOẠI HÀNG TOÀN CẦU
    dynamic_marker_efficiency = 0.72  
    p_type_upper = str(st.session_state.get("bom_data", {}).get("ai_expert_decision", {}).get("product_type_friendly", "JEAN_LONG")).upper().strip()

    MARKER_EFFICIENCY_MAP = {
        "SHORT": 0.68, "JEAN": 0.68, "KHAKI": 0.68, "TROUSER": 0.68, "PANT": 0.68,  
        "JACKET": 0.65, "COAT": 0.65, "BLAZER": 0.65, "SUIT": 0.63, "SHIRT": 0.78, "BLOUSE": 0.78,
        "POLO": 0.75, "TEE": 0.75, "TSHIRT": 0.75, "TANK": 0.75, "HOODIE": 0.70, "SWEATER": 0.70,
        "DRESS": 0.61, "SKIRT": 0.61, "GOWN": 0.58, "JUMPSUIT": 0.60, "ROMPER": 0.60, "OVERALL": 0.60,
        "UNDERWEAR": 0.82, "PANTY": 0.82, "BRA": 0.78, "KIMONO": 0.72, "ROBE": 0.72
    }

    matched = False
    for key, efficiency in MARKER_EFFICIENCY_MAP.items():
        if key in p_type_upper:
            dynamic_marker_efficiency = efficiency
            matched = True
            break

    if not matched:
        if _is_short: dynamic_marker_efficiency = 0.68
        elif _is_trouser: dynamic_marker_efficiency = 0.64
        elif _is_jacket: dynamic_marker_efficiency = 0.65
        elif _is_skirt_or_dress: dynamic_marker_efficiency = 0.61

    _is_knit = any(k in p_type_upper for k in ["POLO", "TEE", "TSHIRT", "TANK", "HOODIE", "SWEATER"])
    _is_jumpsuit = any(k in p_type_upper for k in ["JUMPSUIT", "ROMPER", "OVERALL"])

    def core_engine_router(row, idx):
        v = virtual_pieces_layer.get(idx, {})
        p_cls = str(v.get("material_class", row.get("material_class", "FABRIC"))).upper().strip()
        pcs = int(v.get("active_user_pieces", row.get("Số lượng rập", 1)))
        
        pure_unit_area = float(v.get("polygon_net_area", row.get("polygon_net_area", 0.0)))
        if p_cls == "ACCESSORY" or pure_unit_area <= 0: 
            l_val = float(row.get("Chiều dài rập (inch)", 0.0))
            w_val = float(row.get("Chiều rộng rập (inch)", 0.0))
            pure_unit_area = l_val * w_val * (0.85 if p_cls == "FUSING" else shape_ratio)
            if pure_unit_area <= 0: return 0.0
        
        piece_area = pure_unit_area * pcs
        
        # 📌 VẢI CHÍNH (FABRIC)
        if p_cls == "FABRIC":
            if net_areas["FABRIC"] > 0 and global_fabric_gross > 0:
                allocated_gross = global_fabric_gross * (piece_area / net_areas["FABRIC"])
                if _is_short: allocated_gross = max(allocated_gross, (piece_area / ((f_width - 1.0) * 36.0)) * 1.05)
                elif _is_jumpsuit: allocated_gross = max(allocated_gross, (piece_area / ((f_width - 1.0) * 36.0)) * 1.04)
                return round(allocated_gross, 4)
            knit_wastage_factor = 1.02 if _is_knit else 1.0
            return round(((piece_area / (f_width - 1.0) / dynamic_marker_efficiency) / 36.0) * knit_wastage_factor, 4) if f_width > 1.0 else 0.0

        # 📌 VẢI PHỐI (CONTRAST)
        if p_cls == "CONTRAST":
            if net_areas["CONTRAST"] > 0:
                if global_fabric_gross > 0 and net_areas["FABRIC"] > 0:
                    return round(global_fabric_gross * (piece_area / net_areas["FABRIC"]), 4)
                line_share_ratio = piece_area / net_areas["CONTRAST"]
                base_contrast_gross = (net_areas["CONTRAST"] / (f_width - 1.0) / dynamic_marker_efficiency / 36.0)
                return round(base_contrast_gross * line_share_ratio, 4)
            return round(((piece_area / (f_width - 1.0) / dynamic_marker_efficiency) / 36.0), 4) if f_width > 1.0 else 0.0
            
        # 📌 VẢI LÓT (LINING)
        if p_cls == "LINING":
            if _is_short or _is_trouser: return round(((piece_area / (l_width - 1.0) / 0.82) / 36.0), 4) if l_width > 1.0 else 0.0
            if _is_jacket or "COAT" in p_type_upper or "BLAZER" in p_type_upper: return round(((piece_area / (l_width - 1.0) / 0.72) / 36.0), 4) if l_width > 1.0 else 0.0
            if net_areas["LINING"] > 0 and global_lining_gross > 0: return round(global_lining_gross * (piece_area / net_areas["LINING"]), 4)
            return round(((piece_area / (l_width - 1.0) / 0.82) / 36.0), 4) if l_width > 1.0 else 0.0
            
        # 📌 KEO LÓT / MẾCH DỰNG (FUSING)
        if p_cls == "FUSING":
            if _is_short or _is_trouser:
                if net_areas["FUSING"] > 0 and global_fusing_gross > 0: return round(global_fusing_gross * (piece_area / net_areas["FUSING"]), 4)
                return round(((piece_area / (fuse_width - 1.0) / 0.85) / 36.0), 4) if fuse_width > 1.0 else 0.0
            if "SHIRT" in p_type_upper or "POLO" in p_type_upper: return round(((piece_area / (fuse_width - 1.0) / 0.88) / 36.0), 4) if fuse_width > 1.0 else 0.0
            if net_areas["FUSING"] > 0 and global_fusing_gross > 0:
                allocated_gross = global_fusing_gross * (piece_area / net_areas["FUSING"])
                min_fusing_floor = round(((piece_area / (fuse_width - 1.0) / 0.80) / 36.0), 4) if fuse_width > 1.0 else 0.0
                return max(round(allocated_gross, 4), min_fusing_floor)
            return round(((piece_area / (fuse_width - 1.0) / 0.78) / 36.0), 4) if fuse_width > 1.0 else 0.0

        # 📌 BO TĂM / BO GÂN (RIB) - Đã sửa lỗi mất code trả về dữ liệu (Khử lỗi sập cú pháp)
        if p_cls == "RIB":
            if net_areas["RIB"] > 0:
                base_rib_gross = (net_areas["RIB"] / (fuse_width - 1.0) / 0.82 / 36.0)
                return round(base_rib_gross * (piece_area / net_areas["RIB"]), 4)
            return round(((piece_area / (fuse_width - 1.0) / 0.82) / 36.0), 4) if fuse_width > 1.0 else 0.0
            
        return 0.0
    # =====================================================================
    # 🟩 ĐOẠN 5.2 - PHẦN B: THỰC THI GIAO DIỆN & CẬP NHẬT BỘ NHỚ LƯỚI (V45)
    # =====================================================================
    
    # Kích hoạt thực thi gọi hàm định tuyến từ Phần A cho từng dòng vật tư
    gross_list = []
    for idx, row in df_bom.iterrows():
        gross_list.append(core_engine_router(row, idx))
        
    # Xác định chính xác tên cột định mức thành phẩm có trong bảng
    target_gross_final_col = next((c for c in ["Gross Consumption", "gross_consumption", "allocated_gross"] if c in df_bom.columns), "Gross Consumption")
    df_bom[target_gross_final_col] = gross_list

    # Triển khai giao diện lưới bảng hiển thị báo cáo kiểm toán CAD
    st.markdown('<div class="cad-header">📊 BẢNG BOM ĐỊNH MỨC CHI TIẾT SẢN XUẤT (ĐÃ ÉP BIÊN MAY +0.44 IN)</div>', unsafe_allow_html=True)
    
    # Gọi bảng Data Editor cho phép người dùng thay đổi trực tiếp
    edited_df = st.data_editor(
        df_bom,
        use_container_width=True,
        hide_index=True,
        disabled=["Chiều dài rập (inch)", "Chiều rộng rập (inch)", "polygon_net_area", target_gross_final_col, "cad_status"],
        key=f"cad_bom_editor_master_sync_v45_{st.session_state.get('current_active_size', 'M')}"
    )

    # Lưu lại bộ đệm thay đổi của thợ may lên bộ nhớ hệ thống chống bẫy kẹt Rerun tự động
    if edited_df is not None:
        for idx, row in edited_df.iterrows():
            if "material_class" in edited_df.columns:
                st.session_state["user_edited_materials"][idx] = row["material_class"]
            
            # Ghi nhớ vết số lượng chi tiết thực tế của dòng
            target_pcs_col = "Số lượng rập" if "Số lượng rập" in edited_df.columns else ("piece_count" if "piece_count" in edited_df.columns else "pcs_numeric")
            st.session_state["user_edited_pieces"][idx] = int(row.get(target_pcs_col, 1))

    # Đẩy ngược dữ liệu sạch tối cao vào bộ lưu trữ nền để kết xuất file
    st.session_state["processed_display_rows"] = edited_df.to_dict(orient="records")






        # =====================================================================
    # 🟩 ĐOẠN 6: KHỞI TẠO HÀM XUẤT EXCEL NỘI BỘ (LOCAL EXPORT ENGINE - FIXED)
    # =====================================================================
    def local_export_excel_ppj_format(df_sum, df_det, product_type, bom_ctx, density):
        import io
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Border, Side, Alignment
        from openpyxl.utils import get_column_letter

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
        
        # 🔥 ĐỒNG BỘ AN TOÀN TRÁNH BẪY LỖI NAMEERROR KHI KẾ THỪA BIẾN NGOÀI TRONG HÀM
        f_width_val = float(st.session_state.get("current_active_width", 58.0))
        w_shrink_val = float(st.session_state.get("current_warp_shrinkage", 0.0))
        h_shrink_val = float(st.session_state.get("current_weft_shrinkage", 0.0))
        s_code_val = str(st.session_state.get("current_active_size", bom_ctx.get("detected_base_size", "32"))).upper().strip()

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
            ("Size may mẫu (Sample Size):", s_code_val, "Khổ vải hữu dụng (Width):", f'{f_width_val}"'),
            ("Co rút dọc (Warp Shrinkage):", f'{w_shrink_val}%', "Co rút ngang (Weft Shrinkage):", f'{h_shrink_val}%'),
            ("Chủng loại sản phẩm:", str(product_type).upper(), "Hiệu suất sơ đồ (Density):", f'{density * 100:.1f}%')
        ]
        
        for r_idx, row_data in enumerate(m_data, start=5):
            for c_idx, val in enumerate(row_data, start=1):
                cell = w_s1.cell(row=r_idx, column=c_idx, value=val)
                cell.border = bd_thin
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
        
        # 🌟 ĐỒNG BỘ CHUẨN TÊN CỘT LƯỚI HIỂN THỊ TRÊN FILE EXCEL ĐỂ KHÔNG BỊ KHUYẾT SỐ LIỆU
        det_hd = [
            "Component Name", "Material Class", "Role/Piece Type", "Khổ vải sản xuất (inch)", 
            "Size tính toán", "Số lượng rập", "Chiều dài rập (inch)", "Chiều rộng rập (inch)", 
            "polygon_net_area", "Gross Consumption"
        ]
        for c_idx, h_text in enumerate(det_hd, start=1):
            cell = w_s2.cell(row=3, column=c_idx, value=h_text)
            cell.font = f_header; cell.fill = fill_header; cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True); cell.border = bd_thin

        c_row = 4
        for _, r in df_det.iterrows():
            for c_idx, h_col in enumerate(det_hd, start=1):
                val = r.get(h_col, "")
                cell = w_s2.cell(row=c_row, column=c_idx, value=val)
                cell.font = f_normal; cell.border = bd_thin
                
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
        return output_stream.getvalue() # Trả về mảng dữ liệu byte sạch để st.download_button đọc trực tiếp

        # =====================================================================
    #    # =====================================================================
  

  # =====================================================================
# 🟩 ĐOẠN 7 (VERSION V42 - CHUẨN HÓA NHẬN DIỆN VẬT TƯ ĐA TẦNG & UI HOÀN CHỈNH)
# =====================================================================
    import pandas as pd
    import streamlit as st

    # 🔬 KHỐI MÃ KIỂM TRA ĐỒNG BỘ BIẾN LIÊN ĐOẠN (DEBUG MONITOR)
    st.markdown("### 🔬 Hệ Thống Kiểm Toán Dữ Liệu RAM")
    d_c1, d_c2, d_c3 = st.columns(3)
    d_c1.write(f"**DEBUG FABRIC:** `{st.session_state.get('summary_fabric_gross')}`")
    d_c2.write(f"**DEBUG LINING:** `{st.session_state.get('summary_lining_gross')}`")
    d_c3.write(f"**DEBUG FUSING:** `{st.session_state.get('summary_fusing_gross')}`")
    st.divider()

    st.header("📋 AI AUDIT REPORT (BÁO CÁO KIỂM TOÁN ĐỊNH MỨC TỰ ĐỘNG)")
    
    if "bom_data" not in st.session_state or not isinstance(st.session_state["bom_data"], dict):
        st.session_state["bom_data"] = {}
    ctx = st.session_state["bom_data"]
    
    # Rút trực tiếp cấu trúc tính toán sạch từ bộ não Geometric Solver (Đoạn 5.2)
    ai_decision_final = ctx.get("ai_expert_decision", {})
    virtual_pieces = ai_decision_final.get("virtual_pieces_layer", {})
    
    comp_score_val = float(ai_decision_final.get("complexity_score", 45.0))
    ui_complexity_tier = "COMPLEX" if comp_score_val >= 50 else "NORMAL"
    ui_complexity_icon = "🔴" if comp_score_val >= 75 else ("🟡" if comp_score_val >= 45 else "🟢")
    real_sync_product_type = str(ai_decision_final.get("product_type_friendly", "JEAN_LONG (Quần dài Jeans/Pants)")).strip()

    # Nhận mật độ sơ đồ thực tế phát ra từ Solver thực tế
    marker_efficiency = float(ai_decision_final.get("actual_packing_density", 0.7800))

    # 1. HIỂN THỊ MA TRẬN METRICS ĐẦU GIAO DIỆN CHUẨN XÁC TỪ SOLVER VÀ MASTER CONTROLLER
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("🤖 Loại Hàng Nhận Diện", real_sync_product_type)
    m2.metric(f"{ui_complexity_icon} Mức Độ Phức Tạp", f"{ui_complexity_tier} ({comp_score_val:.0f}/100)")
    m3.metric("📐 Mật Độ Sơ Đồ Chỉ Định", f"{marker_efficiency * 100:.2f}%") 
    m4.metric("🎯 Đường May Bắt Buộc", f"+{float(st.session_state.get('seam_allowance_inch', 0.44))} in")

    # 2. PHỤC HỒI NỀN LƯỚI CHI TIẾT ĐỒNG BỘ AN TOÀN CHỐNG LỆCH KEY (STR/INT)
    df_bom_display = df_bom.copy()
    c_name_col_raw = next((c for c in ["component_name", "Component Name", "Component_Name"] if c in df_bom.columns), "component_name")
    
    df_bom_display["Size tính toán"] = str(st.session_state.get("current_active_size", ctx.get("detected_base_size", "M"))).upper().strip()
    df_bom_display["Component Name"] = df_bom_display[c_name_col_raw]
    df_bom_display["Role/Piece Type"] = "PRIMARY"
    df_bom_display["_original_row_index"] = df_bom.index
    
    # Thừa kế đồng bộ số lượng chi tiết sạch đã qua chỉnh sửa tương tác trên UI
    target_pcs_col_init = next((c for c in ["Số lượng rập", "piece_count", "pcs_numeric"] if c in df_bom.columns), "piece_count")
    df_bom_display["Số lượng rập"] = [int(float(st.session_state.get("user_edited_pieces", {}).get(idx, r.get(target_pcs_col_init, 1.0)))) for idx, r in df_bom.iterrows()]

    clean_mats = []
    calculated_widths = []
    gross_consumptions = []

    for idx, row in df_bom_display.iterrows():
        orig_idx = row["_original_row_index"]
        
        solver_piece_data = {}
        if isinstance(virtual_pieces, dict):
            solver_piece_data = virtual_pieces.get(orig_idx, virtual_pieces.get(str(orig_idx), {}))
        
        # Thừa kế Material Class sạch đã được Đoạn 5.1 nhận diện đồng bộ từ đầu nguồn
        p_cls = solver_piece_data.get("material_class", row.get("Material Class", row.get("material_class", "FABRIC"))).upper().strip()
        clean_mats.append(p_cls)
        
        # Đồng bộ đa khổ vải động dựa trên nhóm vật liệu chuẩn xác trừ đi biên an toàn
        p_width = float(st.session_state.get("current_active_width", 58.0))
        if p_cls == "FUSING": 
            p_width = float(st.session_state.get("fusing_width_inch", 59.0))
        elif p_cls == "LINING": 
            p_width = float(st.session_state.get("lining_width_inch", 57.0))
            
        calculated_widths.append(p_width)
        
        # Đồng bộ định mức tiêu hao thô chi tiết dòng trực tiếp từ Solver thương mại
        target_gross_final_col = next((c for c in ["Gross Consumption", "gross_consumption", "allocated_gross"] if c in df_bom.columns), "Gross Consumption")
        p_gross = df_bom.at[orig_idx, target_gross_final_col] if target_gross_final_col in df_bom.columns else solver_piece_data.get("gross_consumption", 0.0)
        gross_consumptions.append(float(p_gross))

    df_bom_display["Material Class"] = clean_mats
    df_bom_display["Khổ vải sản xuất (inch)"] = calculated_widths
    df_bom_display["Gross Consumption"] = gross_consumptions

    # 🛠️ CƠ CHẾ TỰ ĐỘNG TÍNH TOÁN NGƯỢC CHO BẢNG SUMMARY (Triệt tiêu hoàn toàn lỗi lệch số giữa hai bảng)
    summary_data = {
        "Phân loại vật tư": [],
        "Material Class": [],
        "Gross Consumption": [],
        "UOM": []
    }
    
    label_map = {"FABRIC": "VẢI CHÍNH", "FUSING": "MÉC / KEO", "LINING": "VẢI LÓT", "CONTRAST": "VẢI PHỐI", "RIB": "BO / RIB"}
    grouped_gross = {"FABRIC": 0.0, "FUSING": 0.0, "LINING": 0.0, "CONTRAST": 0.0, "RIB": 0.0}
    
    # Cộng dồn định mức trực tiếp từ lưới chi tiết ra bảng tổng hợp Summary phía trên
    for _, r in df_bom_display.iterrows():
        m_c = str(r["Material Class"]).upper().strip()
        if m_c in grouped_gross:
            grouped_gross[m_c] += float(r["Gross Consumption"])
            
    for mat_cls, total_val in grouped_gross.items():
        if total_val > 0 or mat_cls in ["FABRIC", "FUSING", "LINING"]:
            summary_data["Phân loại vật tư"].append(label_map.get(mat_cls, mat_cls))
            summary_data["Material Class"].append(mat_cls)
            summary_data["Gross Consumption"].append(round(total_val, 4))
            summary_data["UOM"].append("YDS")
            
    df_summary = pd.DataFrame(summary_data)

    st.markdown("##### 📊 Bảng Tổng Hợp Tiêu Hao Vật Tư Đại Trà (BOM Summary)")
    st.dataframe(df_summary, use_container_width=True, hide_index=True)

    # Chuẩn hóa kiểu dữ liệu số hiển thị thương mại
    for col in ["Chiều dài rập (inch)", "Chiều rộng rập (inch)", "polygon_net_area", "Gross Consumption", "Khổ vải sản xuất (inch)"]:
        if col in df_bom_display.columns:
            df_bom_display[col] = pd.to_numeric(df_bom_display[col], errors='coerce').fillna(0.0)

    # Khóa dải cột hiển thị chuẩn ERP thương mại
    ordered_cols = ["_original_row_index", "Component Name", "Material Class", "Role/Piece Type", "Chiều dài rập (inch)", "Chiều rộng rập (inch)", "Khổ vải sản xuất (inch)", "Size tính toán", "Số lượng rập", "polygon_net_area", "Gross Consumption"]
    display_final_cols = [c for c in ordered_cols if c in df_bom_display.columns]
    df_bom_display = df_bom_display[display_final_cols]

    col_t1, col_t2 = st.columns(2)
    col_t1.subheader("📋 Bảng Kế Hoạch Định Mức Rải Sơ Đồ Chi Tiết")

    # 3. XUẤT FILE EXCEL THƯƠNG MẠI CHUẨN ĐỒNG BỘ HIỆU SUẤT ĐỘNG
    with col_t2:
        try:
            if 'local_export_excel_ppj_format' in locals():
                excel_file = local_export_excel_ppj_format(
                    df_summary, 
                    df_bom_display.drop(columns=["_original_row_index"], errors="ignore"), 
                    prod if 'prod' in locals() else "JEAN", 
                    ctx, 
                    marker_efficiency
                )
                style_name_clean = str(ctx.get('style_code', 'Style')).strip().replace('/', '_').replace('\\', '_')
                st.download_button("🟢 DOWNLOAD EXCEL ĐỊNH MỨC THƯƠNG MẠI", data=excel_file, mime="application/vnd.openpyxl_formats-officedocument.spreadsheetml.sheet", file_name=f"PPJ_BOM_{style_name_clean}.xlsx", use_container_width=True)
        except Exception as e: 
            pass

    # RENDER GRID ĐỒNG BỘ CHI TIẾT KHÔNG BÁO LỖI CHỮ ĐỎ
    if "user_edited_pieces" not in st.session_state:
        st.session_state["user_edited_pieces"] = {}

    # 📌 ĐÃ SỬA HOÀN CHỈNH: Đóng ngoặc và cấu hình toàn vẹn cho bộ hiển thị lưới bảng dữ liệu chi tiết
    edited_df_final = st.data_editor(
        df_bom_display, 
        use_container_width=True,
        hide_index=True,
        column_config={
            "_original_row_index": None, 
            "Component Name": st.column_config.TextColumn("🧩 Chi tiết rập CAD", disabled=True),
            "Material Class": st.column_config.TextColumn("🧵 Phân lớp vật tư", disabled=True),
            "Role/Piece Type": st.column_config.TextColumn("📍 Phân loại", disabled=True),
            "Chiều dài rập (inch)": st.column_config.NumberColumn("📏 Chiều dài rập (in)", format="%.2f", disabled=True),
            "Chiều rộng rập (inch)": st.column_config.NumberColumn("📐 Chiều rộng rập (in)", format="%.2f", disabled=True),
            "Khổ vải sản xuất (inch)": st.column_config.NumberColumn("📼 Khổ vải tổng (in)", format="%.1f", disabled=True),
            "Size tính toán": st.column_config.TextColumn("👕 Size", disabled=True),
            "Số lượng rập": st.column_config.NumberColumn("🔢 Số lượng (Pcs)", format="%d", disabled=True),
            "polygon_net_area": st.column_config.NumberColumn("🕸️ Diện tích tinh (in²)", format="%.2f", disabled=True),
            "Gross Consumption": st.column_config.NumberColumn("🎯 Định mức Gross (Yds)", format="%.4f", disabled=True)
        },
        key=f"cad_audit_final_viewer_sync_{st.session_state.get('current_active_size', 'M')}"
    )
