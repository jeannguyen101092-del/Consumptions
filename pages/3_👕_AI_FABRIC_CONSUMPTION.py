import streamlit as st
import re
import json
import copy
import streamlit as st
import pandas as pd  # <--- Bắt buộc phải có dòng này
import threading

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





import io
import re
import hashlib
import numpy as np
import pandas as pd
import streamlit as st

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter


# =====================================================================
# 🟩 MASTER CHAT WORKSPACE & PARAMS SYNC
# VERSION V30.0
#
# FLOW:
#
# USER CHAT
#    ↓
# last_submitted_query
#    ↓
# PARAMETER EXTRACTION
#    ↓
# MASTER SESSION STATE
#    ↓
# BOM DATA
#    ↓
# IE CALCULATION ENGINE
#
# ĐOẠN NÀY LÀ ĐOẠN DUY NHẤT XỬ LÝ CHAT + PARAMETER SYNC
# =====================================================================


# =====================================================================
# 1. SESSION STATE SAFETY
# =====================================================================

if "chat_history" not in st.session_state:
    st.session_state["chat_history"] = []

if "ai_processing" not in st.session_state:
    st.session_state["ai_processing"] = False

if "last_submitted_query" not in st.session_state:
    st.session_state["last_submitted_query"] = ""

if (
    "bom_data" not in st.session_state
    or not isinstance(st.session_state.get("bom_data"), dict)
):
    st.session_state["bom_data"] = {}

ctx = st.session_state["bom_data"]


# =====================================================================
# 2. SAFE NUMBER EXTRACTOR
# =====================================================================

def extract_number(pattern, text):
    """
    Trả về số được tìm thấy.
    Không tìm thấy -> None.
    """

    if not text:
        return None

    match = re.search(
        pattern,
        text,
        re.IGNORECASE
    )

    if not match:
        return None

    try:
        return float(match.group(1))
    except (TypeError, ValueError):
        return None


# =====================================================================
# 3. CHAT HISTORY DISPLAY
# =====================================================================

chat_history_container = st.container()

with chat_history_container:

    st.markdown(
        '<br>'
        '<div class="cad-card">'
        '<div class="cad-header">'
        '💬 CHATGPT IE COLLABORATION WORKSPACE'
        '</div>'
        '</div>',
        unsafe_allow_html=True
    )

    if st.session_state.get("chat_history"):

        for msg in st.session_state["chat_history"]:

            if not isinstance(msg, dict):
                continue

            user_msg = str(msg.get("user", "") or "")
            ai_msg = str(msg.get("ai", "") or "")

            if user_msg:

                with st.chat_message("user"):
                    st.write(user_msg)

            if ai_msg:

                with st.chat_message("assistant"):
                    st.write(ai_msg)


# =====================================================================
# 4. CHAT INPUT
# =====================================================================

safe_user_prompt = st.chat_input(
    "Gõ lệnh tính toán "
    "(Ví dụ: tính định mức cỡ 32 khổ 56 co rút dọc 3 ngang 14)...",
    key="ie_workspace_fixed_dynamic_chat_final_patch_v30_0"
)


# =====================================================================
# 5. KHI USER NHẬP LỆNH
# =====================================================================

if safe_user_prompt:

    query_text = str(
        safe_user_prompt
    ).strip()

    if not query_text:
        st.stop()

    query_lower = query_text.lower()

    st.session_state["last_submitted_query"] = query_text
    st.session_state["ai_processing"] = True


    # ================================================================
    # A. FABRIC WIDTH
    #
    # Hỗ trợ:
    #   khổ 56
    #   khổ vải 56
    #   khổ chính 56
    #   width 56
    # ================================================================

    width_from_chat = extract_number(
        r'\b(?:khổ\s*vải|khổ\s*chính|khổ|kho|width)'
        r'\s*[:=-]?\s*(\d+(?:\.\d+)?)\b',
        query_lower
    )

    if (
        width_from_chat is not None
        and width_from_chat > 0
    ):

        detected_width = width_from_chat

    else:

        detected_width = float(
            st.session_state.get(
                "current_active_width",
                st.session_state.get(
                    "fabric_width_inch",
                    ctx.get(
                        "fabric_width_inch",
                        58.0
                    )
                )
            )
        )

        if detected_width <= 0:
            detected_width = 58.0


    # MASTER FABRIC WIDTH
    st.session_state["current_active_width"] = detected_width
    st.session_state["fabric_width_inch"] = detected_width

    ctx["fabric_width_inch"] = detected_width


    # ================================================================
    # B. FUSING WIDTH
    # ================================================================

    fusing_from_chat = extract_number(
        r'\b(?:khổ\s*keo|keo\s*khổ|khổ\s*dựng)'
        r'\s*[:=-]?\s*(\d+(?:\.\d+)?)\b',
        query_lower
    )

    if (
        fusing_from_chat is not None
        and fusing_from_chat > 0
    ):

        fusing_width = fusing_from_chat

    else:

        fusing_width = float(
            st.session_state.get(
                "fusing_width_inch",
                ctx.get(
                    "fusing_width_inch",
                    59.0
                )
            )
        )

        if fusing_width <= 0:
            fusing_width = 59.0


    st.session_state["fusing_width_inch"] = fusing_width
    ctx["fusing_width_inch"] = fusing_width


    # ================================================================
    # C. LINING WIDTH
    # ================================================================

    lining_from_chat = extract_number(
        r'\b(?:khổ\s*lót|lót\s*khổ|vải\s*lót\s*khổ)'
        r'\s*[:=-]?\s*(\d+(?:\.\d+)?)\b',
        query_lower
    )

    if (
        lining_from_chat is not None
        and lining_from_chat > 0
    ):

        lining_width = lining_from_chat

    else:

        lining_width = float(
            st.session_state.get(
                "lining_width_inch",
                ctx.get(
                    "lining_width_inch",
                    57.0
                )
            )
        )

        if lining_width <= 0:
            lining_width = 57.0


    st.session_state["lining_width_inch"] = lining_width
    ctx["lining_width_inch"] = lining_width


    # ================================================================
    # D. SIZE
    #
    # Hỗ trợ:
    #   cỡ 32
    #   size 32
    #   kích cỡ 32
    # ================================================================

    size_match = re.search(
        r'\b(?:cỡ|size|kích\s*cỡ)'
        r'\s*[:=-]?\s*([a-zA-Z0-9]+)\b',
        query_lower,
        re.IGNORECASE
    )

    if size_match:

        detected_size_code = (
            str(size_match.group(1))
            .upper()
            .strip()
        )

    else:

        size_candidates = [
            st.session_state.get("current_active_size"),
            st.session_state.get("target_size"),
            ctx.get("detected_base_size"),
            ctx.get("base_size"),
            ctx.get("calculated_on_size"),
            "32"
        ]

        detected_size_code = "32"

        for candidate in size_candidates:

            if candidate is None:
                continue

            candidate_text = (
                str(candidate)
                .strip()
            )

            if candidate_text:

                detected_size_code = (
                    candidate_text
                    .upper()
                    .strip()
                )

                break


    # ================================================================
    # SIZE COMPLEX
    #
    # 32X33 -> 32
    # 32 x 33 -> 32
    # ================================================================

    detected_size_code = re.split(
        r'\s*[xX×]\s*',
        detected_size_code
    )[0].strip()


    # MASTER SIZE
    st.session_state["current_active_size"] = detected_size_code
    st.session_state["target_size"] = detected_size_code
    st.session_state["detected_base_size"] = detected_size_code

    ctx["calculated_on_size"] = detected_size_code
    ctx["detected_base_size"] = detected_size_code


    # ================================================================
    # E. WARP / VERTICAL SHRINKAGE
    #
    # Hỗ trợ:
    #   co rút dọc 3
    #   co dọc 3
    #   dọc 3
    #   vertical 3
    # ================================================================

    warp_from_chat = extract_number(
        r'\b(?:co\s*rút\s*dọc|co\s*dọc|dọc|shrink_v|vertical)'
        r'\s*[:=-]?\s*(-?\d+(?:\.\d+)?)\s*%?\b',
        query_lower
    )

    if warp_from_chat is not None:

        warp_shrink = warp_from_chat

    else:

        # KHÔNG RESET VỀ 0
        warp_shrink = float(
            st.session_state.get(
                "warp_shrinkage",
                st.session_state.get(
                    "current_warp_shrinkage",
                    st.session_state.get(
                        "shrinkage_vertical",
                        0.0
                    )
                )
            )
        )


    # ================================================================
    # F. WEFT / HORIZONTAL SHRINKAGE
    # ================================================================

    weft_from_chat = extract_number(
        r'\b(?:co\s*rút\s*ngang|co\s*ngang|ngang|shrink_h|horizontal)'
        r'\s*[:=-]?\s*(-?\d+(?:\.\d+)?)\s*%?\b',
        query_lower
    )

    if weft_from_chat is not None:

        weft_shrink = weft_from_chat

    else:

        # KHÔNG RESET VỀ 0
        weft_shrink = float(
            st.session_state.get(
                "weft_shrinkage",
                st.session_state.get(
                    "current_weft_shrinkage",
                    st.session_state.get(
                        "shrinkage_horizontal",
                        0.0
                    )
                )
            )
        )


    # ================================================================
    # G. ĐỒNG BỘ TOÀN BỘ TÊN BIẾN SHRINKAGE
    # ================================================================

    # Vertical / Warp
    st.session_state["warp_shrinkage"] = warp_shrink
    st.session_state["current_warp_shrinkage"] = warp_shrink
    st.session_state["shrinkage_vertical"] = warp_shrink

    # Horizontal / Weft
    st.session_state["weft_shrinkage"] = weft_shrink
    st.session_state["current_weft_shrinkage"] = weft_shrink
    st.session_state["shrinkage_horizontal"] = weft_shrink


    # ================================================================
    # H. MASTER SNAPSHOT
    # ================================================================

    st.session_state["ie_master_params"] = {

        "size": detected_size_code,

        "fabric_width": detected_width,

        "fusing_width": fusing_width,

        "lining_width": lining_width,

        "warp_shrinkage": warp_shrink,

        "weft_shrinkage": weft_shrink,
    }


    # ================================================================
    # I. ĐỒNG BỘ BOM DATA
    # ================================================================

    ctx["fabric_width_inch"] = detected_width
    ctx["fusing_width_inch"] = fusing_width
    ctx["lining_width_inch"] = lining_width

    ctx["calculated_on_size"] = detected_size_code
    ctx["detected_base_size"] = detected_size_code

    ctx["warp_shrinkage"] = warp_shrink
    ctx["weft_shrinkage"] = weft_shrink

    st.session_state["bom_data"] = ctx


    # ================================================================
    # J. TẠO THÔNG BÁO AUDIT
    # ================================================================

    parameter_summary = (
        f"Size = {detected_size_code} | "
        f"Khổ = {detected_width:g}\" | "
        f"Co dọc = {warp_shrink:g}% | "
        f"Co ngang = {weft_shrink:g}%"
    )

    st.session_state["chat_history"].append({
        "user": query_text,
        "ai": (
            "⚙️ IE Engine đã nhận và đồng bộ:\n\n"
            f"{parameter_summary}\n\n"
            "🔄 Đang kích hoạt tái tính định mức."
        )
    })


    # ================================================================
    # K. RESET PIPELINE
    # ================================================================

    st.session_state["pipeline_auto_run_executed"] = False

    st.session_state["ie_parameter_sync_complete"] = True


    # ================================================================
    # L. RERUN
    # ================================================================

    st.rerun()




# =====================================================================
# 🟩 ĐOẠN 2 (PHIÊN BẢN V27 - CHUẨN ĐỒNG BỘ ĐA TẦNG TUYỆT ĐỐI)
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
                
                🚨 CRITICAL SINGLE PIECE BLOCK RULE (LUẬT RẬP ĐƠN CAD):
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

                # 3. GỌI HÀM QUÉT AI VÀ BỔ SUNG ĐẦY ĐỦ THAM SỐ PROMPT_AGENT_2 
                bom_data = execute_final_gerber_pure_scan(
                    pdf_bytes=active_pdf, 
                    current_query=current_query,
                    active_width=dynamic_width, 
                    target_size_cmd=target_size,
                    raw_json_schema=raw_json_schema,
                    prompt_agent_2=prompt_agent_2  # ✅ ĐÃ SỬA: Thêm tham số chỉ thị AI bị thiếu để phá vỡ lỗi đỏ positional argument
                )
                
                # =====================================================================
                # 🔥 BỘ KHÓA CHẶT THÔNG SỐ CHAT ĐẦU RA (ANTI-OVERRIDE LAYER)
                # =====================================================================
                if bom_data and isinstance(bom_data, dict):
                    # Cưỡng bức đè giá trị từ chat vào cấu hình AI trả về, triệt tiêu số 58 cũ của file
                    bom_data["fabric_width_inch"] = float(dynamic_width)
                    bom_data["usable_width_inch"] = float(dynamic_width)
                    bom_data["calculated_on_size"] = str(target_size)
                    
                    if "ai_expert_decision" in bom_data and isinstance(bom_data["ai_expert_decision"], dict):
                        bom_data["ai_expert_decision"]["detected_base_size"] = str(target_size)
                        bom_data["ai_expert_decision"]["fabric_width"] = float(dynamic_width)

                # Đồng bộ tối thượng vào bộ nhớ RAM hệ thống liên tầng cho Đoạn 4, 5, 7 thừa kế
                st.session_state["bom_data"] = bom_data
                st.session_state["current_active_width"] = float(dynamic_width)
                st.session_state["current_active_size"] = str(target_size)
                
                # Tắt cờ xử lý khi hoàn thành chu kỳ thành công và làm mới giao diện
                st.session_state.ai_processing = False
                st.rerun()

          


            except Exception as e:
                # Vạch trần lỗi ẩn lên màn hình nếu có xung đột cấu trúc dữ liệu
                st.error(f"❌ Lỗi xử lý luồng AI Execute (Đoạn 2): {str(e)}")
                st.session_state.ai_processing = False

                st.rerun()



def initialize_and_sync_parameters():
    """Khối 1 (PHIÊN BẢN V22 - MASTER CONTROLLER): Đồng bộ thông số, bảo vệ an toàn số mảnh rập"""
    if not (st.session_state.get("bom_data") or st.session_state.get("accumulated_bom_rows")):
        return None, None
        
    bom_source = st.session_state.get("bom_data", {})
    if not isinstance(bom_source, dict): bom_source = {}
    
    # 🚨 BẢO VỆ TUYỆT ĐỐI: Trích xuất giữ lại bộ não số lượng rập và lớp ảo trước khi ghi đè
    ai_expert_decision = bom_source.get("ai_expert_decision", {})
    if not isinstance(ai_expert_decision, dict): ai_expert_decision = {}
    
    virtual_pieces_layer = ai_expert_decision.get("virtual_pieces_layer", {})
    if not isinstance(virtual_pieces_layer, dict): virtual_pieces_layer = {}
    
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
        import re
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
    
    # 🔥 KHÔI PHỤC VÀ KHÓA CHẶT BỘ NÃO LỚP ẢO (Ngăn chặn hoàn toàn việc xóa số lượng rập đối xứng)
    ai_expert_decision["virtual_pieces_layer"] = virtual_pieces_layer
    bom_source["ai_expert_decision"] = ai_expert_decision
    
    st.session_state["bom_data"] = bom_source
    return bom_source, user_query_text






import re
import streamlit as st

def extract_cutting_instructions_from_pdf(component_name, raw_pdf_text, current_inferred_pcs=1.0):
    """
    Thuật toán quét Callout văn bản PDF (PHIÊN BẢN V25 - ĐỒNG BỘ SỐ MẢNH THỰC TẾ LÊN LƯỚI UI)
    Tự động phân tích các lệnh kỹ thuật và xuất ra số lượng rập vật lý chuẩn để triệt tiêu lỗi ĐM ảo.
    """
    if not raw_pdf_text:
        return {
            "layer_multiplier": 1, 
            "final_validated_pcs": int(float(current_inferred_pcs or 1.0)), 
            "is_paired": False, 
            "calc_log": "CAD Fallback: Không tìm thấy dữ liệu văn bản thô PDF."
        }
        
    # Chuẩn hóa chuỗi văn bản để làm sạch khoảng trắng rác
    text_clean = " ".join(str(raw_pdf_text).lower().split())
    comp_clean = str(component_name).lower().strip()
    
    # Thiết lập cấu trúc mặc định theo quy chuẩn dệt may
    layer_multiplier = 1
    is_paired = False
    calc_log = "AI Engine: Mặc định đồng bộ trực tiếp theo số lượng phôi gốc từ sơ đồ Techpack."
    
    # Ép biến số lượng gốc về dạng số nguyên để kiểm tra an toàn hình học
    base_pcs = int(float(current_inferred_pcs or 1.0))
    base_pcs = max(base_pcs, 1)
    
    # Tạo biến lưu trữ số lượng rập cuối cùng để đồng bộ hiển thị lên giao diện UI
    final_validated_pcs = base_pcs
    
    # Tìm vị trí xuất hiện của tên chi tiết rập trong file văn bản PDF Techpack
    match_index = text_clean.find(comp_clean)
    if match_index != -1:
        # Gom màng quét về trước 80 và sau 120 ký tự để ép chỉ quét trọn vẹn trong một dòng bảng BOM
        window_start = max(0, match_index - 80)
        window_end = min(len(text_clean), match_index + 120)
        scan_window = text_clean[window_start:window_end]
        
        # Regex bắt trọn cấu trúc ghi (CUT 2, CUT=2, SELF X2, PANEL X2, QTY: 2)
        cut_match = re.search(r'(?:cut|cắt|self|shell|\bx\b|\bqty\b)\s*(?:x\s*|\s*|=\s*|[:\s]*|\(-\s*)(\d+)|(?:\s+|\()(\d+)(?:\s*pcs|\s*chi tiết|\))', scan_window)
        
        if cut_match:
            detected_qty_str = cut_match.group(1) or cut_match.group(2)
            if detected_qty_str:
                detected_qty = int(detected_qty_str)
                if detected_qty > 0:
                    # Ghi nhận số lượng mảnh vật lý thật từ file PDF Techpack
                    final_validated_pcs = detected_qty
                    layer_multiplier = 1 # Khóa chặn hệ số nhân về 1 để dập tắt lỗi nhân chồng chéo định mức ở Đoạn 7.1
                    calc_log = f"Trích xuất Callout PDF: Tìm thấy lệnh cắt tổng {detected_qty} chi tiết (Đã đồng bộ lưới)."
            
        # ➔ B. Quét lệnh đối xứng / cặp đôi (PAIR, MIRROR, X2)
        if any(k in scan_window for k in ["pair", "cặp", "đối", "mirror", "đối xứng", "1 pair"]):
            is_paired = True
            # CHỈ ĐƯỢC PHÉP BÙ PHÔI ĐỐI XỨNG (X2) NẾU SỐ LƯỢNG KHI QUÉT ĐANG BỊ THIẾU (= 1)
            if final_validated_pcs == 1:
                final_validated_pcs = 2
                calc_log = "Trích xuất Callout PDF: Phát hiện kết cấu cặp (PAIR) trên rập đơn. Kích hoạt khôi phục 2 mảnh đối xứng."
                
        # ➔ C. Quét lệnh gập đôi vải bàn cắt (FOLD, GẬP ĐÔI)
        if any(k in scan_window for k in ["fold", "gập", "gap doi", "gập đôi"]):
            calc_log += " | Ghi nhận chi tiết đi biên gập đôi (FOLD)."
            
    # 🚨 BỘ PHÒNG VỆ THƯƠNG MẠI: Nếu là chi tiết thân chính đối xứng nhưng quét bị sót lỗi ra số 1 -> Ép khôi phục về số 2 mảnh
    if final_validated_pcs == 1:
        if any(x in comp_clean for x in ["panel", "front", "back", "than truoc", "than sau", "sleeve", "tay", "pocket bag", "lot tui", "pocket facing"]):
            final_validated_pcs = 2
            calc_log += " | [Auto-Fix] Khôi phục 2 mảnh đối xứng chuẩn kỹ thuật may cho chi tiết thân chính."

    return {
        "layer_multiplier": layer_multiplier,
        "final_validated_pcs": final_validated_pcs, # Đổ số lượng thực tế chuẩn ra bên ngoài cho hệ thống dùng chung
        "is_paired": is_paired,
        "calc_log": calc_log
    }







# =====================================================================
# 🟩 ĐOẠN 2 (PHIÊN BẢN V26 - CHUẨN CAD - NO INDENT): DATA CLEANING & PARAMETER SYNC
# =====================================================================
import re
import pandas as pd

rows = ctx.get("bom_rows", [])
if not rows:
    rows = st.session_state.get("processed_display_rows", [])

if rows is not None and (isinstance(rows, list) and len(rows) > 0 or isinstance(rows, pd.DataFrame) and not rows.empty):
    df_bom = pd.DataFrame(rows) if isinstance(rows, list) else rows.copy()
    df_bom = df_bom.loc[:, ~df_bom.columns.duplicated()].copy()
    
    # 🚨 ĐỒNG BỘ ÉP NHẬN DIỆN CHỦNG LOẠI THỰC TẾ (CHỐNG AI BẮT NHẦM JEAN_LONG)
    style_code_upper = str(st.session_state.get("bom_data", {}).get("ai_expert_decision", {}).get("style_code", "")).upper().strip()
    material_spec_upper = str(st.session_state.get("bom_data", {}).get("ai_expert_decision", {}).get("material_spec", "")).upper().strip()
    p_type_friendly = str(st.session_state.get("bom_data", {}).get("ai_expert_decision", {}).get("product_type_friendly", "JEAN_LONG")).upper().strip()
    
    # Chuỗi tổng hợp phục vụ quét từ khóa chủng loại
    combined_search_text = f"{style_code_upper} | {material_spec_upper} | {p_type_friendly}"
    
    # Mặc định ban đầu lấy từ context
    prod = str(ctx.get("detected_product_type", ctx.get("product_segmented", "JEAN_LONG"))).upper().strip()
    
    # Ép từ khóa ưu tiên cao từ mã hàng thực tế lên biến Master của hệ thống
    if "DRESS" in combined_search_text:
        prod = "DRESS"
    elif "SKIRT" in combined_search_text:
        prod = "SKIRT"
    elif "SHORT" in combined_search_text:
        prod = "SHORT"
    elif "JACKET" in combined_search_text or "COAT" in combined_search_text:
        prod = "JACKET"
    elif "SHIRT" in combined_search_text:
        prod = "SHIRT"

    # Lưu ngược vào ctx và session để các công cụ hạ nguồn đồng bộ chính xác
    ctx["detected_product_type"] = prod
    ctx["product_segmented"] = prod
    
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
        return pcs_val

    df_bom["pcs_numeric"] = [
        float(st.session_state["user_edited_pieces"][idx]) if idx in st.session_state["user_edited_pieces"]
        else clean_precise_piece_count(row) for idx, row in df_bom.iterrows()
    ]
    df_bom[pcs_col] = df_bom["pcs_numeric"]

    # =====================================================================
    # 🚨 ĐỒNG BỘ TUYỆT ĐỐI THEO TRỤC BIẾN MASTER CỦA ĐOẠN 1 (FIXED TRÙM CACHE 58.0)
    # =====================================================================
    # Ép đọc real-time trực tiếp từ ô UI giao diện, mặc định sàn là 56.0 nếu trống
    fabric_width = float(st.session_state.get("current_active_width", 56.0))
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
    # 🟩 ĐOẠN 3.1 (PHIÊN BẢN V27 - CHUẨN ĐỊNH DANH CAD): AI PRODUCT CLASSIFIER
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

    # Gom toàn bộ văn bản danh sách linh kiện, loại bỏ ký tự rác để phân tích
    all_components_text = " ".join(df_bom[comp_col_check].astype(str).str.upper().tolist())

    # Đọc thêm thông tin mã hàng/mô tả từ session để tăng độ chính xác khi quét chủng loại đồ nữ/áo
    style_code_upper = str(st.session_state.get("bom_data", {}).get("ai_expert_decision", {}).get("style_code", "")).upper().strip()
    material_spec_upper = str(st.session_state.get("bom_data", {}).get("ai_expert_decision", {}).get("material_spec", "")).upper().strip()
    combined_context_text = f"{style_code_upper} {material_spec_upper} {prod_upper_name} {all_components_text}"

    # 🧠 TẦNG 2 (AI QUYẾT ĐỊNH LOẠI HÀNG): ĐÃ FIX BẪY TỪ KHÓA ÉP SHIRT LÊN TRÊN JACKET
    # 👗 👔 Ưu tiên 1: Ép nhận diện các nhóm Áo sơ mi, Đầm, Váy trước để không bị Sleeve/Collar bẫy sang Áo khoác
    if any(x in combined_context_text for x in ["SHIRT", "SƠ MI", "SO MI", "BLOUSE"]):
        product_category = "SHIRT"
    elif any(x in combined_context_text for x in ["SKIRT", "VÁY", "CHÂN VÁY", "CHAN VAY"]):
        product_category = "SKIRT"
    elif any(x in combined_context_text for x in ["DRESS", "ĐẦM", "DAM", "FLARE", "SHIFT", "MAXI"]):
        product_category = "DRESS_FLARE"
    elif any(x in combined_context_text for x in ["JACKET", "KHOÁC", "COAT", "BLAZER"]):
        product_category = "JACKET"
    elif "SHORT" in combined_context_text or "QUẦN SHORT" in combined_context_text:
        product_category = "SHORT"

    # 👖 Ưu tiên 2: Nếu không dính sơ mi/đồ nữ/áo khoác rõ ràng, mới quét sang cấu trúc linh kiện Quần dài
    elif any(x in all_components_text for x in ["TROUSER", "LEG", "ĐŨNG", "ĐÁY QUẦN", "JEAN", "PANTS", "QUẦN", "QUAN", "WAISTBAND", "FLY", "CẠP", "LƯNG", "POCKET FACING"]):
        product_category = "JEAN_LONG"
        
    elif any(x in all_components_text for x in ["SLEEVE", "COLLAR", "CỔ ÁO", "TAY ÁO"]):
        product_category = "JACKET"
        
    else:
        for k in COMPANY_DENSITY_PRIOR.keys():
            if k in prod_upper_name:
                product_category = k
                break
        
        if product_category is None:
            product_category = "JEAN_LONG"

    # Chuẩn hóa chuỗi hiển thị thân thiện lên giao diện UI báo cáo kiểm toán
    if product_category == "VEST": ai_product_type = "VEST (Áo Vest/Blazer)"
    elif product_category == "JACKET": ai_product_type = "JACKET (Áo khoác Jacket)"
    elif product_category == "DRESS_FLARE": ai_product_type = "DRESS_FLARE (Đầm suông/Thời trang)"
    elif product_category == "SKIRT": ai_product_type = "SKIRT (Chân váy)"
    elif product_category == "TOPS_KNIT": ai_product_type = "TOPS_KNIT (Áo thun/Polo)"
    elif product_category == "SHIRT": ai_product_type = "SHIRT (Áo sơ mi)"
    elif product_category == "SHORT": ai_product_type = "SHORT (Quần short)"
    else: ai_product_type = "JEAN_LONG (Quần dài Jeans/Pants)"

    # ĐỒNG BỘ TUYỆT ĐỐI VÀO BỘ NHỚ HỆ THỐNG MASTER (CHỐNG LỖI CONTEXT BREAKDOWN)
    if "bom_data" not in st.session_state or not isinstance(st.session_state["bom_data"], dict):
        st.session_state["bom_data"] = {}
        
    ctx = st.session_state["bom_data"]
    if "ai_expert_decision" not in ctx or not isinstance(ctx["ai_expert_decision"], dict): 
        ctx["ai_expert_decision"] = {}
        
    # 🔥 BẢO VỆ SỐ LƯỢNG MẢNH ẢO: Trích xuất giữ lại bộ não số lượng rập đối xứng cũ của AI trước khi gán đè
    virtual_pieces_layer_backup = ctx["ai_expert_decision"].get("virtual_pieces_layer", {})

    ctx["ai_expert_decision"]["product_category"] = product_category
    ctx["ai_expert_decision"]["product_type_friendly"] = ai_product_type
    ctx["ai_expert_decision"]["estimated_density_prior"] = COMPANY_DENSITY_PRIOR[product_category]
    ctx["ai_expert_decision"]["virtual_pieces_layer"] = virtual_pieces_layer_backup

    # Đẩy lên trục biến tầng ngoài bảo vệ tham số nền cho Đoạn 5.1 gỡ nghẽn
    st.session_state["current_estimated_density_prior"] = COMPANY_DENSITY_PRIOR[product_category]
    st.session_state["bom_data"] = ctx
       # =====================================================================
    # 🟩 ĐOẠN 4 (VERSION V28.0): MASTER GEOMETRY & STRICT MATERIAL CLASSIFIER
    # =====================================================================
    import pandas as pd
    import numpy as np
    import streamlit as st

    comp_col_check = next((c for c in ["Component Name", "component_name", "Component_Name"] if c in df_bom.columns), "component_name")
    m_col_check = next((c for c in ["Material Class", "material_class"] if c in df_bom.columns), "material_class")

    if "bom_data" not in st.session_state or not isinstance(st.session_state["bom_data"], dict):
        st.session_state["bom_data"] = {}
    ctx = st.session_state["bom_data"]

    if "ai_expert_decision" not in ctx or not isinstance(ctx["ai_expert_decision"], dict):
        ctx["ai_expert_decision"] = {}

    virtual_pieces_layer = {}
    user_edited_materials = st.session_state.get("user_edited_materials", {})

    for idx, row in df_bom.iterrows():
        # 🔒 LOCK KIẾN TRÚC INDEX: Ép khóa định danh dòng về dạng Chuỗi (str) đồng bộ toàn bộ pipeline
        idx_str = str(idx).strip()
        
        comp_name_raw = str(row.get(comp_col_check, row.get("component_name", "")))
        comp_name_upper = comp_name_raw.upper().strip()
        mat_str = str(row.get(m_col_check, "")).upper().strip()
        
        # 🧵 CHẶNG 4.1: MULTI-LAYER MATERIAL CLASSIFIER (QUÉT SÂU KHÔNG LỌT LƯỚI)
        # Ưu tiên tuyệt đối quyết định chỉnh sửa chất liệu thủ công của User từ lưới UI
        if idx in user_edited_materials:
            p_class = user_edited_materials[idx]
        elif idx_str in user_edited_materials:
            p_class = user_edited_materials[idx_str]
            
        # Nếu User chưa sửa, tiến hành quét biểu thức chính quy chính xác cao
        elif any(k in comp_name_upper or k in mat_str for k in ["THREAD", "CHỈ", "BUTTON", "NÚT", "ZIP", "ACCESSORY"]):
            p_class = "ACCESSORY"
        elif any(k in comp_name_upper or k in mat_str for k in ["FUSING", "MEC", "MẾCH", "KEO", "INTERLINING", "DỰNG", "WAISTBAND FUSING"]):
            p_class = "FUSING"
        elif any(k in comp_name_upper or k in mat_str for k in ["RIB", "BO GÂN", "BO CO", "BO TAY", "BO LAI", "BO LUNG", "BO TĂM"]):
            p_class = "RIB"
        elif any(k in comp_name_upper or k in mat_str for k in ["LINING", "LÓT", "POCKET BAG", "POCKETING", "VẢI LÓT", "POCKET FACING", "POCKETING FABRIC", "POCKET"]):
            p_class = "LINING"
        elif any(k in comp_name_upper or k in mat_str for k in ["CONTRAST", "PHỐI", "VẢI PHỐI", "MATCHING"]):
            p_class = "CONTRAST"
        elif any(k in comp_name_upper or k in mat_str for k in ["PADDING", "GÒN", "WADDING", "BÔNG LOT"]):
            p_class = "PADDING"
        else:
            p_class = "FABRIC"

        # COLUMN RESOLVER ĐA TẦNG ĐỌC ĐÚNG CHIỀU DÀI/RỘNG RẬP GỐC CAD/AI
        l_orig = float(pd.to_numeric(row.get("bounding_box_length", row.get("Dài (L-inch)", row.get("Chiều dài rập (inch)", 0.0))), errors="coerce") or 0.0)
        w_orig = float(pd.to_numeric(row.get("bounding_box_width", row.get("Rộng (W-inch)", row.get("Chiều rộng rập (inch)", 0.0))), errors="coerce") or 0.0)
        net_area_real = float(pd.to_numeric(row.get("polygon_net_area", 0.0), errors="coerce") or 0.0)

        if l_orig <= 0.0 or w_orig <= 0.0: 
            continue

        # Aspect Ratio Correction (Dài luôn >= Rộng)
        if w_orig > l_orig:
            l_orig, w_orig = w_orig, l_orig

        # Adaptive OBB Efficiency Inference (Tối ưu hình học phẳng)
        if net_area_real > 0:
            current_factor = net_area_real / (l_orig * w_orig)
            aspect_ratio = l_orig / w_orig
            log_aspect = np.log1p(aspect_ratio)
            
            target_obb_eff = max(0.6400, min(0.9200, 0.88 - (0.05 * log_aspect) + (0.15 * current_factor)))
            if current_factor < target_obb_eff:
                optimized_area = net_area_real / target_obb_eff
                w_orig = (optimized_area / aspect_ratio) ** 0.5
                l_orig = w_orig * aspect_ratio

        # Tiếp nhận số lượng mảnh cơ sở từ Đoạn 2
        raw_pcs = float(row.get("pcs_numeric", row.get("Số lượng rập", 1.0)))
        raw_pcs = max(raw_pcs, 1.0)

        user_pieces_dict = st.session_state.get("user_edited_pieces", {})
        if idx in user_pieces_dict:
            final_pcs = float(user_pieces_dict[idx])
        elif idx_str in user_pieces_dict:
            final_pcs = float(user_pieces_dict[idx_str])
        else:
            final_pcs = raw_pcs
        final_pcs = max(final_pcs, 1.0)

        # GEOMETRY CONTROL: Khống chế diện tích tinh hình học
        bbox_area_control = l_orig * w_orig
        if net_area_real <= 0.0:
            net_area_real = bbox_area_control * 0.74
        elif net_area_real > bbox_area_control:
            net_area_real = bbox_area_control * 0.85

        # Đóng gói dữ liệu gốc sạch vào lớp rập ảo bằng Khóa Chuỗi bảo vệ liên tầng
        virtual_pieces_layer[idx_str] = {
            "material_class": p_class,                      
            "production_l": round(l_orig, 2), 
            "production_w": round(w_orig, 2), 
            "production_net_area": round(net_area_real, 2),
            "polygon_net_area": round(net_area_real, 2),    
            "active_user_pieces": int(final_pcs),                
            "component_name": comp_name_raw
        }

    # Phản hồi dữ liệu hình học phẳng ngược về DataFrame Master phục vụ pipeline
    for idx, vp in virtual_pieces_layer.items():
        target_loc = int(idx) if idx.isdigit() and int(idx) in df_bom.index else (idx if idx in df_bom.index else None)
        if target_loc is not None:
            df_bom.at[target_loc, "Chiều dài rập (inch)"] = vp["production_l"]
            df_bom.at[target_loc, "Chiều rộng rập (inch)"] = vp["production_w"]
            df_bom.at[target_loc, "polygon_net_area"] = vp["production_net_area"]
            df_bom.at[target_loc, "Material Class"] = vp["material_class"]

    ctx["ai_expert_decision"]["virtual_pieces_layer"] = virtual_pieces_layer
    st.session_state["bom_data"] = ctx
    # =====================================================================
    # 🟩 ĐOẠN 5.1 (VERSION V28.5): PIECE NORMALIZE PIPELINE (STRICT USER SYNC)
    # =====================================================================
    import pandas as pd
    import streamlit as st

    current_fabric_width = float(st.session_state.get("current_active_width", 58.0))
    fusing_width = float(st.session_state.get("fusing_width", 59.0))    
    lining_width = float(st.session_state.get("lining_width", 57.0))    

    raw_unpaired_pieces = []
    list_lengths, list_widths = [], []

    l_col = next((c for c in ["Chiều dài rập (inch)", "bounding_box_length"] if c in df_bom.columns), None)
    w_col = next((c for c in ["Chiều rộng rập (inch)", "bounding_box_width"] if c in df_bom.columns), None)
    pcs_col = next((c for c in ["pcs_numeric", "Số lượng rập"] if c in df_bom.columns), "Số lượng rập")

    user_edited_materials = st.session_state.get("user_edited_materials", {})

    for idx, r in df_bom.iterrows():
        idx_str = str(idx).strip()
        
        v_piece = virtual_pieces_layer.get(idx_str, {})
        if not v_piece:
            virtual_pieces_layer[idx_str] = {}
            v_piece = virtual_pieces_layer[idx_str]
        
        p_len = float(v_piece.get("production_l", r.get(l_col, 0.0) if l_col else 0.0))
        p_wid = float(v_piece.get("production_w", r.get(w_col, 0.0) if w_col else 0.0))
        net_area = float(v_piece.get("polygon_net_area", r.get("polygon_net_area", 0.0)))
        
        # 🛠️ FIXED: Ưu tiên tuyệt đối quyết định chỉnh sửa chất liệu của User từ UI truyền xuống
        if idx in user_edited_materials:
            p_class_check = user_edited_materials[idx]
        elif idx_str in user_edited_materials:
            p_class_check = user_edited_materials[idx_str]
        else:
            p_class_check = str(v_piece.get("material_class", r.get("Material Class", "FABRIC"))).upper().strip()
            
        v_piece["material_class"] = p_class_check  

        if net_area <= 0.0 and p_len > 0.0 and p_wid > 0.0:
            net_area = p_len * p_wid

        raw_pcs = float(v_piece.get("active_user_pieces", r.get(pcs_col, 1.0) if pcs_col else 1.0))
        raw_pcs = max(raw_pcs, 1.0)

        user_pieces_dict = st.session_state.get("user_edited_pieces", {})
        if idx in user_pieces_dict: pcs = float(user_pieces_dict[idx])
        elif idx_str in user_pieces_dict: pcs = float(user_pieces_dict[idx_str])
        else: pcs = raw_pcs

        pcs = max(pcs, 1.0)
        df_bom.at[idx, pcs_col] = int(pcs)
        v_piece["active_user_pieces"] = int(pcs)

        list_lengths.append(round(p_len, 2) if p_len > 0 else 0.0)
        list_widths.append(round(p_wid, 2) if p_wid > 0 else 0.0)
        
        df_bom.at[idx, "polygon_net_area"] = round(net_area, 2)
        v_piece["polygon_net_area"] = round(net_area, 2)

        if p_class_check in ["FABRIC", "FUSING", "LINING", "RIB", "CONTRAST", "PADDING"] and p_len > 0.0:
            # 🛠️ FIXED CRITICAL: Thay thế hoàn toàn math.ceil bằng phép chia sàn số âm thuần túy an toàn dứt điểm lỗi NameError
            loop_pcs = int(-(-pcs // 1))
            for _ in range(loop_pcs):
                raw_unpaired_pieces.append({
                    "idx": idx_str, "l": p_len, "w": p_wid, "area": net_area,
                    "material_class": p_class_check, "priority": 3
                })

    raw_unpaired_pieces.sort(key=lambda x: (x.get('priority', 3), -x['area']))
    df_bom["Chiều dài rập (inch)"] = list_lengths
    df_bom["Chiều rộng rập (inch)"] = list_widths

    ctx["ai_expert_decision"]["virtual_pieces_layer"] = virtual_pieces_layer
    st.session_state["bom_data"] = ctx


   
    # =====================================================================
    # 🟩 ĐOẠN 5.2 - PHẦN A (VERSION V25): MARKER EFFICIENCY ROUTER PIPELINE
    # =====================================================================
    import pandas as pd
    import streamlit as st

    if "bom_data" not in st.session_state or not isinstance(st.session_state["bom_data"], dict):
        st.session_state["bom_data"] = {}
    ctx = st.session_state["bom_data"]
    ai_decision = ctx.get("ai_expert_decision", {})

    CONFIG_MATRIX = {
        "OVERALL":  [0.71, "OVERALLS (Quần yếm/Quần bảo hộ)"], "COVERALL": [0.71, "OVERALLS (Quần yếm/Quần bảo hộ)"],
        "BIB":      [0.71, "OVERALLS (Quần yếm/Quần bảo hộ)"], "JUMPSUIT": [0.70, "OVERALLS (Quần yếm/Quần bảo hộ)"],
        "DUNGAREE": [0.71, "OVERALLS (Quần yếm/Quần bảo hộ)"], "DRESS":    [0.75, "DRESS (Đầm xòe/suông)"],
        "SKIRT":    [0.66, "SKIRT (Chân váy)"],             "SHORT":    [0.68, "SHORT (Quần short)"],
        "JEAN":     [0.75, "JEAN (Vải Denim/Jean)"],         "KHAKI":    [0.60, "KHAKI (Quần Khaki)"],
        "TROUSER":  [0.71, "TROUSER (Quần tây công sở)"],    "PANT":     [0.72, "PANT (Quần dài dáng suông)"],
        "JACKET":   [0.60, "JACKET (Áo khoác gió/Jeans)"],   "COAT":     [0.60, "COAT (Áo măng tô/Áo choàng)"],
        "BLAZER":   [0.65, "BLAZER (Áo Vest mỏng/Blazer)"],  "SUIT":     [0.65, "SUIT (Bộ Comple/Suit)"],
        "SHIRT":    [0.78, "SHIRT (Áo sơ mi vải dệt)"],      "BLOUSE":   [0.78, "BLOUSE (Áo kiểu/Blouse)"],
        "POLO":     [0.76, "POLO (Áo thun cổ bẻ)"],          "TEE":      [0.76, "TEE/TSHIRT (Áo thun cổ tròn)"],
        "TSHIRT":   [0.76, "TEE/TSHIRT (Áo thun cổ tròn)"],  "TANK":     [0.74, "TANK (Áo ba lỗ/Sát nách)"],
        "JEAN_LONG":[0.82, "JEAN_LONG (Quần Jeans dài chuẩn)"]
    }

    # 🔒 Kế thừa trực tiếp nhãn chủng loại thô vững chắc từ Đoạn 3.1
    inherited_raw_type = ai_decision.get("ai_product_type_raw", "JEAN_LONG").upper().strip()
    ie_detected_type = inherited_raw_type if inherited_raw_type in CONFIG_MATRIX else "JEAN_LONG"
    dynamic_marker_efficiency = CONFIG_MATRIX[ie_detected_type][0]

    # Phạt sơ đồ từ UI Controls
    is_nap_mode = st.session_state.get("is_nap_fabric", False)          
    is_one_way_mode = st.session_state.get("is_one_way_fabric", False)  
    if is_one_way_mode: dynamic_marker_efficiency -= 0.05  
    elif is_nap_mode: dynamic_marker_efficiency -= 0.03  

    dynamic_marker_efficiency = max(0.52, round(dynamic_marker_efficiency, 4))

    ctx["ie_detected_type"] = ie_detected_type
    ctx["ie_product_type_friendly"] = CONFIG_MATRIX[ie_detected_type][1]
    
    st.session_state["active_marker_efficiency_value"] = float(dynamic_marker_efficiency)
    ctx["ai_expert_decision"]["marker_efficiency"] = dynamic_marker_efficiency
    st.session_state["bom_data"] = ctx
       # =====================================================================
    # 🟩 ĐOẠN 5.2 - PHẦN B1 (VERSION V26.9): INITIALIZATION & DATA RECOVERY
    # =====================================================================
    import pandas as pd
    import streamlit as st

    # 1. ĐỒNG BỘ VÀ KẾ THỪA LỚP RẬP ẢO TỪ BỘ NHỚ RAM HỆ THỐNG
    if "bom_data" not in st.session_state: 
        st.session_state["bom_data"] = {}
    ctx = st.session_state["bom_data"]
    
    if "ai_expert_decision" not in ctx: 
        ctx["ai_expert_decision"] = {}
    
    stored_virtual_pieces = ctx["ai_expert_decision"].get("virtual_pieces_layer", {})
    if not isinstance(stored_virtual_pieces, dict): 
        stored_virtual_pieces = {}

    # Khởi tạo ma trận tổng tích lũy định mức thương mại sạch sẽ
    summary_grouped_gross = {"FABRIC": 0.0, "FUSING": 0.0, "LINING": 0.0, "CONTRAST": 0.0, "RIB": 0.0, "PADDING": 0.0}

    # Kế thừa trực tiếp khổ vải chính an toàn đã qua kiểm toán tại Đoạn 1
    raw_chat_width = st.session_state.get("current_active_width", 58.0)
    try:
        parsed_width = float(raw_chat_width) if raw_chat_width not in [None, ""] else 58.0
    except:
        parsed_width = 58.0

    if parsed_width <= 0.0:
        parsed_width = 58.0

    # 🔒 MỒI MẠCH RECOVERY: Nếu df_bom bị biến mất do refresh trang, tự động dựng lại từ mảng dữ liệu gốc
    if 'df_bom' not in locals() or df_bom is None or (isinstance(df_bom, pd.DataFrame) and df_bom.empty):
        rows_backup = ctx.get("bom_rows", st.session_state.get("processed_display_rows", []))
        if rows_backup:
            df_bom = pd.DataFrame(rows_backup)
        else:
            df_bom = pd.DataFrame()

    # Cấu hình sẵn các cột cấu trúc Master trên DataFrame
    if 'df_bom' in locals() and df_bom is not None and not df_bom.empty:
        for col, default_val in [("Số lượng rập", None), ("Gross Consumption", 0.0), ("Khổ vải sản xuất (inch)", parsed_width)]:
            if col not in df_bom.columns: 
                df_bom[col] = default_val

    # Kế thừa tỷ lệ co rút từ RAM Đoạn 1 (Phần thập phân)
    shrink_v = float(st.session_state.get("shrinkage_vertical", 0.0)) / 100.0   
    shrink_h = float(st.session_state.get("shrinkage_horizontal", 0.0)) / 100.0 
    wastage_allowance = 1.05

    # Nhận và khống chế hiệu suất chặt chẽ trong khoảng kỹ thuật (52% - 95%)
    try:
        base_efficiency = float(st.session_state.get("active_marker_efficiency_value", 0.74))
    except (TypeError, ValueError):
        base_efficiency = 0.74
    base_efficiency = max(0.52, min(base_efficiency, 0.95))


    # =====================================================================
    # 🟩 ĐOẠN 5.2 - PHẦN B2 (VERSION V26.9): COMMERCIAL CONSUMPTION ENGINE
    # =====================================================================
    if 'df_bom' in locals() and df_bom is not None and not df_bom.empty:
        for idx, r in df_bom.iterrows():
            v = stored_virtual_pieces.get(idx, stored_virtual_pieces.get(str(idx), {}))
            if not isinstance(v, dict): 
                v = {}
            
            c_name_lower = str(r.get("component_name", v.get("component_name", ""))).lower().strip()

            # [BƯỚC 1]: THỪA HƯỞNG PHÂN LOẠI NHÓM VẬT TƯ ĐỒNG BỘ LIÊN TẦNG
            p_cls = str(v.get("material_class", r.get("Material Class", "FABRIC"))).upper().strip()
            if p_cls not in summary_grouped_gross:
                p_cls = "FABRIC"

            p_length_fallback = float(v.get("production_l", r.get("Chiều dài rập (inch)", r.get("bounding_box_length", 0.0))))
            p_width_fallback = float(v.get("production_w", r.get("Chiều rộng rập (inch)", r.get("bounding_box_width", 0.0))))

            # [BƯỚC 2]: GEOMETRY GUARD - CHỐNG DIỆN TÍCH BẰNG 0
            pure_unit_area = float(v.get("polygon_net_area", r.get("polygon_net_area", 0.0)))
            if pure_unit_area <= 0.0:
                pure_unit_area = p_length_fallback * p_width_fallback
            if pure_unit_area <= 0.0:
                pure_unit_area = 10.0 

            # [BƯỚC 3]: SỐ LƯỢNG CHI TIẾT VÀ USER OVERRIDE
            user_pieces_dict = st.session_state.get("user_edited_pieces", {})
            user_override_exists = (idx in user_pieces_dict or str(idx) in user_pieces_dict)
            
            if idx in user_pieces_dict: pcs = int(user_pieces_dict[idx])
            elif str(idx) in user_pieces_dict: pcs = int(user_pieces_dict[str(idx)])
            elif "active_user_pieces" in v and int(v["active_user_pieces"]) >= 1: pcs = int(v["active_user_pieces"])
            elif pd.notna(r.get("Số lượng rập")) and int(r["Số lượng rập"]) >= 1: pcs = int(r["Số lượng rập"])
            else: pcs = 2 if any(x in c_name_lower for x in ["leg", "panel", "front", "back", "than", "sleeve", "tay"]) else 1

            if not user_override_exists:
                if pcs == 1 and any(x in c_name_lower for x in ["leg", "panel", "front leg", "back leg", "than truoc", "than sau", "ong quan"]):
                    pcs = 2

            pcs = max(pcs, 1)
            df_bom.at[idx, "Số lượng rập"] = int(pcs)
            
            if idx not in stored_virtual_pieces: stored_virtual_pieces[idx] = {}
            stored_virtual_pieces[idx]["active_user_pieces"] = pcs

            # [BƯỚC 4]: BIÊN MAY
            area_includes_seam = bool(v.get("area_includes_seam", False) or r.get("area_includes_seam", False))
            seam_modifier = 1.06 if (p_cls in ["FABRIC", "CONTRAST"] and not area_includes_seam) else 1.0
            total_piece_area = pure_unit_area * pcs * seam_modifier
            
            # [BƯỚC 5]: XÁC ĐỊNH KHỔ VẢI THỰC TẾ TRÊN TỪNG NHÓM PHÂN LỚP VẬT TƯ
            if p_cls == "FUSING": current_w = float(st.session_state.get("fusing_width", 59.0))
            elif p_cls == "LINING": current_w = float(st.session_state.get("lining_width", 57.0))
            elif p_cls == "RIB": current_w = float(st.session_state.get("rib_width", 40.0))
            elif p_cls == "PADDING": current_w = float(st.session_state.get("padding_width", 60.0))
            else: current_w = parsed_width  
                
            if current_w <= 0.0: 
                current_w = 58.0
            df_bom.at[idx, "Khổ vải sản xuất (inch)"] = current_w

            # [BƯỚC 6]: PHÂN PHỐI HIỆU SUẤT SƠ ĐỒ
            row_efficiency = base_efficiency
            if p_cls in ["FUSING", "LINING"]: row_efficiency = 0.60  
            elif p_cls == "RIB": row_efficiency = 0.82  
            elif p_cls == "PADDING": row_efficiency = 0.85  

            # =====================================================================
            # ⚙️ TOÁN TỬ TÍNH ĐỊNH MỨC THƯƠNG MẠI CHUẨN XƯỞNG MAY ERP
            # =====================================================================
            gross_area_sq_inches = total_piece_area / row_efficiency
            shrinkage_multiplier = (1.0 + shrink_v) * (1.0 + shrink_h)
            gross_area_post_shrink = gross_area_sq_inches * shrinkage_multiplier
            
            linear_inches_needed = gross_area_post_shrink / current_w
            actual_wastage = 1.03 if area_includes_seam else wastage_allowance
            total_inches_with_wastage = linear_inches_needed * actual_wastage
            
            gross_consumption_yards = total_inches_with_wastage / 36.0
            gross_consumption_yards = round(max(0.0, gross_consumption_yards), 4)
            
            df_bom.at[idx, "Gross Consumption"] = gross_consumption_yards
            summary_grouped_gross[p_cls] += gross_consumption_yards

            print(f"[DM ENGINE] idx={idx} | comp={c_name_lower} | gross={gross_consumption_yards:.4f} Yds")

        # Đóng gói dữ liệu tổng định biên sau vòng lặp
        for k in summary_grouped_gross:
            summary_grouped_gross[k] = round(summary_grouped_gross[k], 3)
            
        st.session_state["summary_grouped_gross"] = summary_grouped_gross
        ctx["ai_expert_decision"]["virtual_pieces_layer"] = stored_virtual_pieces

        # =====================================================================
        # 🔒 FINAL MASTER COMMIT - ÉP LƯU DỮ LIỆU ĐỔ THẲNG XUỐNG ĐOẠN 7 (NO RERUN)
        # =====================================================================
        df_bom["Gross Consumption"] = pd.to_numeric(df_bom["Gross Consumption"], errors="coerce").fillna(0.0).round(4)
        st.session_state["active_calculated_df_bom"] = df_bom.copy()
        
        print(f"[DM ENGINE FINAL COMMIT] Rows={len(df_bom)} | Total DM={df_bom['Gross Consumption'].sum():.4f} Yds")

            # =====================================================================
    # 🟩 ĐOẠN 5.2C (VERSION V26.7): AUTOMATED CORES IGNITION (INDENTED)
    # =====================================================================
    if "bom_data" not in st.session_state:
        st.session_state["bom_data"] = {}
    ctx = st.session_state["bom_data"]

    # 🔒 BỘ PHÁ BĂNG TỰ ĐỘNG THỤT LỀ (ANTI-FREEZE TRIGGER)
    # Nếu phát hiện AI Scan đã có dữ liệu thô nhưng mạch kết quả Yards chưa được commit lên RAM
    if ("bom_rows" in ctx and len(ctx["bom_rows"]) > 0) or ("ai_expert_decision" in ctx and ctx["ai_expert_decision"].get("virtual_pieces_layer")):
        
        # Kiểm tra nếu cờ chạy tự động đang bị khóa (bị lì), chủ động bẻ khóa để kích luồng chạy ngay
        if not st.session_state.get("pipeline_auto_run_executed", False) or "active_calculated_df_bom" not in st.session_state:
            
            with st.spinner("⚙️ Hệ thống IE Engine đang tự động tính toán định mức kỹ thuật thương mại..."):
                try:
                    # Ép trạng thái ghi nhận mạch chạy tự động bắt đầu kích hoạt
                    st.session_state["pipeline_auto_run_executed"] = True
                    
                    # 🔄 THỰC THI CHUỖI LIÊN HOÀN (Mồi mạch cho DataFrame chạy xuyên suốt)
                    if 'df_bom' not in locals() or df_bom is None or (isinstance(df_bom, pd.DataFrame) and df_bom.empty):
                        rows_raw = ctx.get("bom_rows", st.session_state.get("processed_display_rows", []))
                        if rows_raw:
                            df_bom = pd.DataFrame(rows_raw)
                    
                    # Sau khi nạp mạch mồi, ép Streamlit rerun 1 lần duy nhất để giải phóng bộ nhớ đệm
                    st.rerun()
                    
                except Exception as e:
                    st.session_state["pipeline_auto_run_executed"] = False




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
      # =====================================================================
       # =====================================================================
    # 🟩 ĐOẠN 7.1 (VERSION V26.0): DISPLAY LAYER (SUMMARY ONLY)
    # =====================================================================
    import re
    import pandas as pd
    import streamlit as st

    if "bom_data" not in st.session_state or not isinstance(st.session_state["bom_data"], dict):
        st.session_state["bom_data"] = {}
    ctx = st.session_state["bom_data"]
    ai_decision_final = ctx.get("ai_expert_decision", {})
    if not isinstance(ai_decision_final, dict): ai_decision_final = {}

    grouped_gross = st.session_state.get("summary_grouped_gross", {"FABRIC": 0.0, "FUSING": 0.0, "LINING": 0.0, "CONTRAST": 0.0, "RIB": 0.0, "PADDING": 0.0})
    
    st.markdown("### 🔬 Hệ Thống Kiểm Toán Dữ Liệu RAM")
    d_c1, d_c2, d_c3 = st.columns(3)
    d_c1.write(f"**DEBUG FABRIC:** `{grouped_gross.get('FABRIC', 0.0)}`")
    d_c2.write(f"**DEBUG LINING:** `{grouped_gross.get('LINING', 0.0)}`")
    d_c3.write(f"**DEBUG FUSING:** `{grouped_gross.get('FUSING', 0.0)}`")
    st.divider()

    st.header("📋 AI AUDIT REPORT (BÁO CÁO KIỂM TOÁN ĐỊNH MỨC TỰ ĐỘNG)")
    virtual_pieces = ai_decision_final.get("virtual_pieces_layer", {})

    comp_score_val = float(ai_decision_final.get("complexity_score", 45.0))
    ui_complexity_tier = "COMPLEX" if comp_score_val >= 50 else "NORMAL"
    ui_complexity_icon = "🔴" if comp_score_val >= 75 else ("🟡" if comp_score_val >= 45 else "🟢")
    
    real_sync_product_type = str(ctx.get("ie_product_type_friendly", ai_decision_final.get("product_type_friendly", "JEAN_LONG (Quần dài Jeans/Pants)"))).strip()
    marker_efficiency = float(st.session_state.get("active_marker_efficiency_value", ai_decision_final.get("marker_efficiency", 0.7400)))
    chat_width_override = float(st.session_state.get("current_active_width", 58.0))

    fusing_w_audit = float(st.session_state.get("fusing_width", 59.0))
    lining_w_audit = float(st.session_state.get("lining_width", 57.0))
    rib_w_audit = float(st.session_state.get("rib_width", 40.0))
    padding_w_audit = float(st.session_state.get("padding_width", 60.0))

    st.caption(
        f"🔗 **Bảng tra cứu khổ vải kỹ thuật đang áp dụng:** "
        f"Chính (Chat): `{chat_width_override:.1f}\"` | "
        f"Keo (Fusing): `{fusing_w_audit:.1f}\"` | "
        f"Lót (Lining): `{lining_w_audit:.1f}\"` | "
        f"Bo (Rib): `{rib_w_audit:.1f}\"` | "
        f"Gòn (Padding): `{padding_w_audit:.1f}\"`"
    )

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("🤖 Chủng Loại Nhận Diện (IE)", real_sync_product_type)
    m2.metric(f"{ui_complexity_icon} Mức Độ Phức Tạp", f"{ui_complexity_tier} ({comp_score_val:.0f}/100)")
    m3.metric("📐 Mật Độ Sơ Đồ Chỉ Định", f"{marker_efficiency * 100:.2f}%") 
    m4.metric("🎯 Độ Tin Cậy AI (Confidence)", f"{float(ctx.get('confidence', 0.95))*100:.1f}%")

    if "active_calculated_df_bom" in st.session_state:
        df_bom_display = st.session_state["active_calculated_df_bom"].copy()
    else:
        df_bom_display = df_bom.copy()

    _debug_total_dm = float(df_bom_display["Gross Consumption"].sum())
    st.caption(f"🔒 MASTER ENGINE DATA: {len(df_bom_display)} pieces | Total Gross DM = **{_debug_total_dm:.4f} Yds**")

    # Bảng tổng hợp Summary Yards gốc
    total_fabric = grouped_gross.get("FABRIC", 0.0)
    total_fusing = grouped_gross.get("FUSING", 0.0)
    total_lining = grouped_gross.get("LINING", 0.0)
    total_contrast = grouped_gross.get("CONTRAST", 0.0)
    total_rib = grouped_gross.get("RIB", 0.0)
    total_padding = grouped_gross.get("PADDING", 0.0)

    summary_data = {"Phân loại vật tư": ["VẢI CHÍNH"], "Material Class": ["FABRIC"], "Gross Consumption": [round(total_fabric, 4)], "UOM": ["Yds"]}
    for k, v in [("VẢI PHỐI", "CONTRAST"), ("MÉC / KEO", "FUSING"), ("VẢI LÓT", "LINING"), ("BO / RIB", "RIB"), ("GÒN LÓT THÂN", "PADDING")]:
        if grouped_gross.get(v, 0.0) > 0:
            summary_data["Phân loại vật tư"].append(k)
            summary_data["Material Class"].append(v)
            summary_data["Gross Consumption"].append(round(grouped_gross[v], 4))
            summary_data["UOM"].append("Yds")
            
    df_summary = pd.DataFrame(summary_data)
    st.subheader("📊 BẢNG TỔNG HỢP BOM SUMMARY (YARDS)")
    st.dataframe(df_summary, use_container_width=True, hide_index=True)

       # =====================================================================
    # 🟩 ĐOẠN 7.2 (VERSION V27.2): BOM EDITOR PIPELINE (STRICT INDEX RESILIENT)
    # =====================================================================
    import pandas as pd
    import streamlit as st

    if "active_calculated_df_bom" in st.session_state:
        df_bom_display_final = st.session_state["active_calculated_df_bom"].copy()

        # Ép kiểu dữ liệu số thực an toàn toàn diện bảo vệ lưới đồ họa
        for col in ["Chiều dài rập (inch)", "Chiều rộng rập (inch)", "polygon_net_area", "Gross Consumption", "Khổ vải sản xuất (inch)"]:
            if col in df_bom_display_final.columns:
                df_bom_display_final[col] = pd.to_numeric(df_bom_display_final[col], errors='coerce').fillna(0.0)

        # Chuẩn hóa tên cột Component Name hiển thị trên giao diện
        c_name_master = next((c for c in ["component_name", "Component Name", "Component_Name"] if c in df_bom_display_final.columns), None)
        if c_name_master:
            df_bom_display_final["Component Name"] = df_bom_display_final[c_name_master].astype(str).str.upper().str.strip()
        else:
            df_bom_display_final["Component Name"] = "CHI TIẾT RẬP THÔ"

        df_bom_display_final["Size tính toán"] = str(st.session_state.get("current_active_size", "32")).upper().strip()

        # Khôi phục chính xác Material Class đồng bộ từ bộ lắng nghe sự kiện
        clean_mats = []
        user_edited_materials = st.session_state.get("user_edited_materials", {})
        for idx, row in df_bom_display_final.iterrows():
            if idx in user_edited_materials: p_cls = user_edited_materials[idx]
            elif str(idx) in user_edited_materials: p_cls = user_edited_materials[str(idx)]
            else: p_cls = row.get("Material Class", row.get("material_class", "FABRIC"))
            clean_mats.append(str(p_cls).upper().strip())
        df_bom_display_final["Material Class"] = clean_mats

        # 🛠️ FIXED: Tạo khóa định danh bằng chuỗi Index vật lý hiện tại của DataFrame
        df_bom_display_final["Mã Chi Tiết"] = df_bom_display_final.index.astype(str)

        # Trật tự cột hoàn chỉnh, hiện Component Name ở vị trí đầu tiên
        ordered_cols = ["Mã Chi Tiết", "Component Name", "Material Class", "Chiều dài rập (inch)", "Chiều rộng rập (inch)", "Khổ vải sản xuất (inch)", "Size tính toán", "Số lượng rập", "polygon_net_area", "Gross Consumption"]
        display_final_cols = [c for c in ordered_cols if c in df_bom_display_final.columns]
        df_bom_display_final = df_bom_display_final[display_final_cols]

        st.subheader("📐 ĐỊNH MỨC CHI TIẾT TỪNG RẬP VÀ ĐIỀU CHỈNH VẬT TƯ (BOM EDITOR)")

        col_t1, col_t2 = st.columns(2)
        with col_t1:
            st.caption("🟢 **Hướng dẫn:** Anh click trực tiếp vào ô chữ **FABRIC** của chi tiết túi để đổi sang **LINING** hoặc **FUSING**.")

        # Khôi phục nút Download Excel đồng bộ nằm bên tay phải tiêu đề
        with col_t2:
            try:
                if 'local_export_excel_ppj_format' in locals():
                    excel_file = local_export_excel_ppj_format(
                        df_summary if 'df_summary' in locals() else pd.DataFrame(), 
                        df_bom_display_final.drop(columns=["Mã Chi Tiết"], errors="ignore"), 
                        "JEAN", ctx, float(st.session_state.get("active_marker_efficiency_value", 0.74))
                    )
                    style_name_clean = str(ctx.get('style_code', 'Style')).strip().replace('/', '_').replace('\\', '_')
                    st.download_button("🟢 DOWNLOAD EXCEL ĐỊNH MỨC THƯƠNG MẠI", data=excel_file, mime="application/vnd.openpyxl_formats-officedocument.spreadsheetml.sheet", file_name=f"PPJ_BOM_{style_name_clean}.xlsx", use_container_width=True)
            except Exception as excel_err: 
                pass

        if "user_edited_pieces" not in st.session_state: st.session_state["user_edited_pieces"] = {}
        if "user_edited_materials" not in st.session_state: st.session_state["user_edited_materials"] = {}

        # LƯỚI DATA EDITOR DUY NHẤT CHO PHÉP CLICK CHỌN ĐỔI CHẤT LIỆU
        edited_df = st.data_editor(
            df_bom_display_final, 
            key="bom_data_editor_matrix_fixed_v27_2",
            use_container_width=True,
            hide_index=True,
            column_config={
                "Mã Chi Tiết": None, # Ẩn cột khóa khỏi mắt người dùng để tối ưu giao diện
                "Component Name": st.column_config.TextColumn("📋 Component Name (Tên Chi Tiết)", disabled=True, width="large"),
                "Material Class": st.column_config.SelectboxColumn(
                    "🧵 Material Class (Click Chọn Sửa)", 
                    options=["FABRIC", "LINING", "FUSING", "CONTRAST", "RIB", "PADDING"],
                    required=True, disabled=False, width="medium"
                ),
                "Chiều dài rập (inch)": st.column_config.NumberColumn("📏 Chiều dài (inch)", format="%.2f", disabled=True),
                "Chiều rộng rập (inch)": st.column_config.NumberColumn("📐 Chiều rộng (inch)", format="%.2f", disabled=True),
                "Khổ vải sản xuất (inch)": st.column_config.NumberColumn("Khổ vải (inch)", format="%.1f", disabled=True),
                "Size tính toán": st.column_config.TextColumn("Size", disabled=True),
                "Số lượng rập": st.column_config.NumberColumn("🔢 Số lượng", format="%d", min_value=1, disabled=False),
                "polygon_net_area": st.column_config.NumberColumn("polygon_net_area", format="%.2f", disabled=True),
                "Gross Consumption": st.column_config.NumberColumn("Gross Consumption (Yds)", format="%.4f", disabled=True)
            }
        )

        # 🎯 BỘ LẮNG NGHE SỰ KIỆN: Vá dứt điểm lỗi bẫy Index vật lý khi người dùng tương tác Sort lưới
        if edited_df is not None and "bom_data_editor_matrix_fixed_v27_2" in st.session_state:
            editor_state = st.session_state["bom_data_editor_matrix_fixed_v27_2"]
            if "edited_rows" in editor_state and len(editor_state["edited_rows"]) > 0:
                changes = editor_state["edited_rows"]
                has_updates = False
                
                for row_key_str, updated_cols in changes.items():
                    df_row_index = int(row_key_str)
                    
                    # 🛠️ FIXED CRITICAL: Truy vết nhãn Index gốc vững chắc từ mảng đích DataFrame hiển thị
                    orig_idx = df_bom_display_final.index[df_row_index]
                    master_target_idx = df_bom_display_final.at[orig_idx, "Mã Chi Tiết"]
                    
                    # Hỗ trợ đồng bộ đa kiểu dữ liệu Index (chuỗi/số nguyên) của pandas
                    target_key = int(master_target_idx) if str(master_target_idx).isdigit() else master_target_idx
                    
                    if "Số lượng rập" in updated_cols:
                        st.session_state["user_edited_pieces"][target_key] = int(updated_cols["Số lượng rập"])
                        has_updates = True
                    if "Material Class" in updated_cols:
                        # GHI NHẬN RAM MASTER LUỒNG ĐỘNG ĐỂ ENGINE 5.2B2 THỰC THI KHẤU TRỪ VẬT TƯ
                        st.session_state["user_edited_materials"][target_key] = str(updated_cols["Material Class"]).upper().strip()
                        has_updates = True
                        
                if has_updates:
                    st.session_state["pipeline_auto_run_executed"] = False
                    st.rerun()
