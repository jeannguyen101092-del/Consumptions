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
    query_text = str(safe_user_prompt).strip()
    st.session_state["last_submitted_query"] = query_text
    st.session_state.ai_processing = True
    
    # =====================================================================
    # ⚙️ BỘ TRÍ TUỆ NHÂN DIỆN LỆNH CHAT ĐỘNG (ROUTING PARSER LAYER)
    # =====================================================================
    import re
    query_lower = query_text.lower()
    
    # A. BÓC TÁCH KHỔ VẢI SẢN XUẤT (Ví dụ: "khổ 56", "khổ vải 54.5", "khổ sản xuất 58")
    width_match = re.search(r'(?:khổ|kho|width|khổ vải|khổ sản xuất)\s*([0-9]+(?:\.[0-9]+)?)', query_lower)
    if width_match:
        detected_width = float(width_match.group(1))
        # Khóa chặt giá trị vào vùng nhớ liên tầng
        st.session_state["current_active_width"] = detected_width
        
    # B. BÓC TÁCH CỠ/SIZE SẢN XUẤT (Mở rộng thêm - Ví dụ: "cỡ 32", "size 34", "cỡ l")
    size_match = re.search(r'(?:cỡ|size|coer)\s*([a-z0-9]+)', query_lower)
    if size_match:
        detected_size = str(size_match.group(1)).upper().strip()
        st.session_state["current_active_size"] = detected_size

    # C. BÓC TÁCH TỶ LỆ CO RÚT (Mở rộng thêm nếu bạn cần dùng cho cấu hình sơ đồ)
    # Tìm "co rút dọc 3" -> 3%
    shrink_v_match = re.search(r'(?:dọc|doc)\s*([0-9]+(?:\.[0-9]+)?)', query_lower)
    if shrink_v_match:
        st.session_state["shrinkage_vertical"] = float(shrink_v_match.group(1))
    # Tìm "ngang 14" -> 14%    
    shrink_h_match = re.search(r'(?:ngang)\s*([0-9]+(?:\.[0-9]+)?)', query_lower)
    if shrink_h_match:
        st.session_state["shrinkage_horizontal"] = float(shrink_h_match.group(1))

    # Thực hiện làm sạch luồng và rerun để cập nhật toàn bộ hệ thống
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
    Thuật toán quét Callout Văn bản PDF (PHIÊN BẢN V23 - CHUẨN HÓA SỐ MẢNH THƯƠNG MẠI SẢN XUẤT)
    Tự động đồng bộ số lượng rập đối xứng trái phải lên lưới UI và cân bằng lại định mức.
    """
    if not raw_pdf_text:
        return {"layer_multiplier": 1, "final_validated_pcs": int(float(current_inferred_pcs or 1.0)), "is_paired": False, "calc_log": "Không tìm thấy dữ liệu văn bản thô PDF."}
        
    # Chuẩn hóa chuỗi văn bản để làm sạch khoảng trắng rác
    text_clean = " ".join(str(raw_pdf_text).lower().split())
    comp_clean = str(component_name).lower().strip()
    
    # Khai báo cấu trúc tham chiếu an toàn ban đầu
    layer_multiplier = 1
    is_paired = False
    calc_log = "AI đọc văn bản PDF: Đồng bộ trực tiếp theo kích thước phôi đơn của Techpack."
    
    # Đưa biến số lượng gốc về kiểu số nguyên để kiểm tra an toàn
    base_pcs = int(float(current_inferred_pcs or 1.0))
    base_pcs = max(base_pcs, 1)
    
    # Biến lưu trữ số lượng rập cuối cùng sau chuẩn hóa để ép lên giao diện UI
    final_validated_pcs = base_pcs
    
    # 1. Thuật toán quét vùng lân cận mở rộng (Quét phạm vi lùi về trước 120 ký tự để bắt trọn Callout cột trước)
    match_index = text_clean.find(comp_clean)
    if match_index != -1:
        window_start = max(0, match_index - 120)
        window_end = min(len(text_clean), match_index + 120)
        scan_window = text_clean[window_start:window_end]
        
        # ➔ A. Quét lệnh số lượng cắt vật lý trực tiếp (Ví dụ: CUT 2, CẮT 2, SELF X2, SHELL=2)
        cut_match = re.search(r'\b(cut|cắt|self|shell|qty)\s*(x\s*|\s*|\s*[:=]\s*)(\d+)\b', scan_window)
        if cut_match:
            detected_qty = int(cut_match.group(3))
            if detected_qty > 0:
                final_validated_pcs = detected_qty
                layer_multiplier = 1 # Đặt hệ số nhân về 1 để chống bẫy nhân đôi định mức chéo ở tầng hiển thị
                calc_log = f"Trích xuất Callout PDF: Phát hiện lệnh cắt tổng {detected_qty} chi tiết (Đã khóa đồng bộ lưới)."
            
        # ➔ B. Quét lệnh đối xứng / cặp đôi (PAIR, MIRROR, X2, TRÁI PHẢI)
        if any(k in scan_window for k in ["pair", "cặp", "đối", "mirror", "đối xứng", "left/right", "trái/phải", "1l+1r"]):
            is_paired = True
            # CHỈ KHÔI PHỤC SỐ MẢNH ĐỐI XỨNG NẾU SỐ LƯỢNG NHẬN DIỆN BAN ĐẦU BỊ THIẾU (BẰNG 1)
            if final_validated_pcs == 1:
                final_validated_pcs = 2
                calc_log = "Trích xuất Callout PDF: Phát hiện kết cấu cặp (PAIR). Kích hoạt khôi phục 2 mảnh đối xứng chuẩn ngành may."
                
        # ➔ C. Quét lệnh gập đôi vải rải sơ đồ (FOLD, GẬP ĐÔI)
        if any(k in scan_window for k in ["fold", "gập", "gap doi", "gập đôi", "on fold"]):
            calc_log += " | Ghi nhận chi tiết đi biên gập đôi (FOLD)."
            
    # 🚨 BỘ SỬA LỖI ÉP SỐ LƯỢNG THƯƠNG MẠI: Nếu tên chi tiết chứa từ khóa thân chính nhưng vẫn bị bằng 1 -> Ép khôi phục về số 2
    if final_validated_pcs == 1:
        if any(x in comp_clean for x in ["panel", "front", "back", "than truoc", "than sau", "sleeve", "tay", "pocket bag", "lot tui", "pocket facing", "dap tui"]):
            final_validated_pcs = 2
            calc_log += " | [Sửa lỗi tự động] Ép số lượng mảnh rập về 2 cho chi tiết đối xứng thân chính."

    return {
        "layer_multiplier": layer_multiplier,
        "final_validated_pcs": final_validated_pcs, # Trả số lượng thực tế đã đồng bộ ra cho DataFrame sử dụng
        "is_paired": is_paired,
        "calc_log": calc_log
    }




import numpy as np
import re
import streamlit as st

def calculate_skyline_2d_metrics(bom_rows_list, user_query_text):
    """
    Khối 2b Siêu Cấp (PHIÊN BẢN V24 - CHUẨN GERBER ENGINE): Mô phỏng toán học phi tuyến tính.
    Đ-Á SỬA: Đồng bộ chuẩn trường dữ liệu pcs_numeric và vá lỗi chính tả biến hình học chữ nhật.
    """
    ctx = classify_pieces_and_products(bom_rows_list, user_query_text)
    if not ctx or not ctx.get("stable_bom_list"):
        return {"product_segmented": "GENERIC_TOP", "fabric_pattern": "SOLID", "actual_packing_density": 0.85, "global_gross_fabric_yds": 1.45, "major_shape_area": 0.0}

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
    
    # Đồng bộ bộ não ghi nhớ chỉnh sửa rập thủ công từ UI nếu có
    user_edited = st.session_state.get("user_edited_pieces", {})
    
    for idx, r in enumerate(stable_bom):
        try:
            # ✅ ĐÃ SỬA: Đọc chính xác trường dữ liệu gốc pcs_numeric và Số lượng rập liên tầng
            if idx in user_edited:
                pcs = float(user_edited[idx])
            else:
                pcs = float(r.get("pcs_numeric", r.get("Số lượng rập", r.get("piece_count", 2.0))))
            
            # Khôi phục số lượng rập đối xứng tự động cho các thân chính nếu bị kẹt số 1 trái ngành
            c_name_lower = str(r.get("component_name", "")).lower().strip()
            if pcs <= 1:
                if any(x in c_name_lower for x in ["panel", "front", "back", "than truoc", "than sau", "sleeve", "tay"]):
                    pcs = 2.0
            
            if pcs <= 0: pcs = 1.0
        except:
            pcs = 2.0  # Mặc định an toàn cho phôi rập may mặc công nghiệp là rập cặp (Pair)
            
        l_inch = float(r.get("bounding_box_length", r.get("Dài (L-inch)", r.get("Chiều dài rập (inch)", 0.0))))
        w_inch = float(r.get("bounding_box_width", r.get("Rộng (W-inch)", r.get("Chiều rộng rập (inch)", 0.0))))
        
        # HOTFIX HÌNH HỌC PHẲNG: Nếu rập bị phình to >16" do dữ liệu thô, tự động đưa về kích thước đơn
        p_c_check = str(r.get("material_class", "FABRIC")).upper().strip()
        if p_c_check == "FABRIC" and w_inch > 16.0:
            w_inch = w_inch / 2.0
            pcs = pcs * 2.0

        bbox_a = l_inch * w_inch
        net_a = float(r.get("polygon_net_area", 0.0))
        
        # ✅ ĐÃ SỬA CHÍNH TẢ: Thay bbox_area thành biến đúng bbox_a chống sập Exception ngầm
        if net_a > bbox_a and bbox_a > 0:
            net_a = bbox_a * 0.76
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
    edge_irregularity = 1.0 - convexity_score

    logistic_midpoint = 0.38
    logistic_k = 12.0  
    width_penalty_logistic = 0.05 / (1.0 + np.exp(-logistic_k * (width_occupancy_ratio - logistic_midpoint)))

    # =====================================================================
    # 3. TÍNH TOÁN MẬT ĐỘ NÈN ĐỘNG CHUẨN CƠ ĐỒNG BỘ
    # =====================================================================
    calculated_density = 0.72 + (bounding_box_fill * 0.14) + (compactness_score * 0.04)
    nesting_efficiency_bonus = (small_piece_ratio * 0.04) + (fragmentation_ratio * 0.02)
    actual_packing_density = (calculated_density + nesting_efficiency_bonus - width_penalty_logistic) * rotation_freedom_factor
    actual_packing_density = max(min(actual_packing_density, 0.9450), 0.7600)

    # =====================================================================
    # 4. CHIỀU DÀI SƠ ĐỒ VÀ TRUNG HÒA HAO HỤT BÀN CẮT (LOẠI BỎ PHẠT TRÙNG)
    # =====================================================================
    if total_net_area <= 0:
        total_net_area = ctx.get("major_shape_area", 0.0) + ctx.get("minor_shape_area", 0.0)
        
    simulated_length = (total_net_area / fabric_width) / actual_packing_density
    simulated_length *= (1.0 + (edge_irregularity * 0.02))

    length_logistic_mid = 45.0  
    length_k = -0.05
    wastage_curve_factor = 0.005 + (0.04 / (1.0 + np.exp(-length_k * (simulated_length - length_logistic_mid))))
    fabric_wastage_multiplier = 1.010 + wastage_curve_factor
    
    # Quy đổi chiều dài sơ đồ ra Yards chuẩn hệ thống thương mại thương bản
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



def process_pieces_layer_and_areas(bom_rows_list, product_segmented, warp_shrinkage, weft_shrinkage):
    """
    Khối 3 hoàn chỉnh (PHIÊN BẢN V26 - GEOMETRIC AREA SOLVER): Chuẩn hóa hình học phẳng dệt may.
    Đ-Á SỬA: Khôi phục chuẩn số lượng rập đối xứng trái phải và vá lỗi biến hình học phẳng bbox_a.
    """
    total_fabric_piece_area = 0.0
    piece_calculated_data = []
    raw_pdf_context = st.session_state.get("raw_pdf_text_extracted", "")

    for r in bom_rows_list:
        if not r or not isinstance(r, dict): continue
        
        raw_l = safe_float(r.get("bounding_box_length", r.get("Dài (L-inch)", r.get("Chiều dài rập (inch)", 0.0))))
        raw_w = safe_float(r.get("bounding_box_width", r.get("Rộng (W-inch)", r.get("Chiều rộng rập (inch)", 0.0))))
        
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

        # Đọc số lượng phôi gốc từ Techpack (Đồng bộ chuẩn hóa các trường khóa liên tầng)
        pcs = safe_int(r.get("pcs_numeric", r.get("Số lượng rập", r.get("original_piece_count", 1))))
        
        # 🧠 BỘ LỌC TỰ ĐỘNG KHÔI PHỤC SỐ MẢNH RẬP ĐỐI XỨNG THEO TIÊU CHUẨN KỸ THUẬT MAY IE
        c_name_lower = comp_name_raw.lower()
        if pcs <= 1:
            if any(x in c_name_lower for x in ["panel", "front", "back", "than truoc", "than sau", "sleeve", "tay", "pocket bag", "lot tui", "pocket facing", "dap tui"]):
                pcs = 2  # Các chi tiết đối xứng trái/phải bắt buộc phải có ít nhất 2 mảnh dập hình

        if "original_piece_count" not in r:
            r["original_piece_count"] = pcs
            
        cut_qty_ai = safe_int(r.get("cut_quantity", pcs), default=pcs)
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

            # 4. CHUẨN HÓA ĐƯỜNG MAY BIÊN RẬP (Chỉ bù hao hụt biên cắt cực nhỏ 0.15 inch chu vi)
            seamed_l = adj_l + 0.15
            seamed_w = adj_w + 0.15 if raw_w > 0 else adj_w
            
            # Kiểm tra xem người dùng có can thiệp sửa số lượng mảnh trên UI không
            if "user_edited_pieces" in st.session_state and idx in st.session_state["user_edited_pieces"]:
                total_pcs_final = int(st.session_state["user_edited_pieces"][idx])
            else:
                total_pcs_final = pcs * layer_multiplier
                
            total_pcs_final = max(total_pcs_final, 1)
            
            # GEOMETRY GUARD: ✅ ĐÃ SỬA: Thay thế bbox_area bằng biến đúng bbox_a chống sập logic ngầm
            bbox_a = seamed_l * seamed_w
            calculated_net_area = bbox_a * shape_factor
            if calculated_net_area > bbox_a:
                calculated_net_area = bbox_a * 0.76
                
            item_area = calculated_net_area * total_pcs_final
            
            # Đồng bộ dữ liệu sạch hoàn toàn vào DataFrame của hệ thống
            r["material_class"] = r_material_class
            if r_material_class == "FABRIC": 
                total_fabric_piece_area += item_area
            
            r["production_length"] = adj_l
            r["production_width"] = adj_w
            r["piece_count"] = total_pcs_final
            r["Số lượng rập"] = total_pcs_final
            r["pcs_numeric"] = total_pcs_final
            r["polygon_net_area"] = round(calculated_net_area, 2)
            r["calculation_status"] = "PROCESSED"
            r["cad_algorithm"] = f"Phom: {piece_shape} | Cấp ưu tiên: {packing_priority}"
            
            piece_calculated_data.append({
                "row_ref": r, "item_area": item_area, "is_button": False, "pcs_display": f"{total_pcs_final} Pcs",
                "layer_multiplier": layer_multiplier, "mat_class_raw": r_material_class, "combined_str": f" {comp_name_raw} ", 
                "is_belt_loop": (piece_shape == "RECTANGLE" and "LOOP" in comp_name_raw), 
                "raw_l": adj_l, "raw_w": adj_w, "pcs_val": total_pcs_final, "custom_name": comp_name_raw
            })
            
    st.session_state["piece_calculated_data"] = piece_calculated_data
    return round(total_fabric_piece_area, 4), piece_calculated_data





def allocate_gerber_share_consumption(piece_calculated_data, total_fabric_piece_area, skyline_results):
    """
    Khối 4 hoàn chỉnh (PHIÊN BẢN V27 - GERBER ALLOCATION ENGINE): Phân bổ định mức thương mại.
    Đ-Á SỬA: Trả cột số lượng rập về kiểu số nguyên sạch (int) chống kẹt hiển thị và đồng bộ khổ chat.
    """
    base_gross_fabric = skyline_results.get("global_gross_fabric_yds", 0.0)
    if base_gross_fabric == 0.0:
        base_gross_fabric = skyline_results.get("global_gross_fabric_consumption", 0.0)
    if base_gross_fabric == 0.0:
        base_gross_fabric = skyline_results.get("global_gross_fabric", 0.0)
        
    product_segmented = skyline_results.get("product_segmented", "JEAN_LONG")
    actual_packing_density = skyline_results.get("actual_packing_density", 0.85)
    if actual_packing_density <= 0: actual_packing_density = 0.85
    
    # ✅ Đ-Á SỬA: Đồng bộ khổ vải sản xuất chuẩn theo câu lệnh phiên chat hoạt động, loại bỏ găm cứng 58.0 của file cũ
    usable_width = float(st.session_state.get("current_active_width", 56.0))
    if usable_width <= 0: usable_width = 56.0
    
    # Đồng bộ khổ vải phụ thời gian thực từ bộ nhớ hệ thống
    lining_width = float(st.session_state.get("lining_width_inch", 57.0))
    fusing_width = float(st.session_state.get("fusing_width_inch", 59.0))
    
    # ➔ BƯỚC 1: THUẬT TOÁN CHUẨN HÓA TRỌNG SỐ (RE-NORMALIZATION) CHO VẢI CHÍNH
    weighted_area_sum = 0.0
    for item in piece_calculated_data:
        if "row_ref" not in item: continue
        r = item["row_ref"]
        mat_class_raw = str(item["mat_class_raw"]).upper().strip()
        
        if mat_class_raw == "FABRIC":
            packing_priority = safe_int(r.get("packing_priority", 3), default=3)
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

        if mat_class_raw == "FABRIC":
            packing_priority = safe_int(r.get("packing_priority", 3), default=3)
            if total_fabric_piece_area > 0 and base_gross_fabric > 0 and weighted_area_sum > 0:
                weight_factor = 1.08 if packing_priority <= 2 else (0.88 if packing_priority >= 4 else 1.00)
                share_ratio = (item_area * weight_factor) / weighted_area_sum
                gross_consumption = round(base_gross_fabric * share_ratio, 4)
                calc_chain = f"Gerber Fabric Re-normalized (Priority {packing_priority})"
            else:
                estimated_base = ((item_area / usable_width) / 36.0) / actual_packing_density
                gross_consumption = round(estimated_base * 1.030, 4)
                calc_chain = f"CAD Geometry Fallback"
                    
        elif mat_class_raw == "LINING":
            gross_consumption = round(((item_area / lining_width) / 36.0) * 1.030, 4)
            calc_chain = f"Sơ đồ LINING độc lập (Khổ {lining_width} inch)"
            
        elif mat_class_raw == "FUSING":
            gross_consumption = round(((item_area / fusing_width) / 36.0) * 1.030, 4)
            calc_chain = f"Sơ đồ FUSING độc lập (Khổ {fusing_width} inch)"
            
        elif mat_class_raw in ["RIB", "CONTRAST"]:
            gross_consumption = round(((item_area / usable_width) / 36.0) * 1.030, 4)
            calc_chain = f"Sơ đồ phối {mat_class_raw} độc lập"
        else:
            gross_consumption, calc_chain = 0.0, f"Vật tư phụ mẫu hàng {product_segmented}."

        # Cập nhật kết quả đồng bộ lên DataFrame để đẩy ra bảng UI chi tiết
        r["Gross Consumption"] = gross_consumption
        item["row_ref"]["Gross Consumption"] = gross_consumption
        
        # ✅ Đ-Á SỬA CHÍ MẠNG: Ép giá trị nguyên tinh khiết (int) tuyệt đối, bỏ chuỗi chữ " Pcs" để giải phóng grid hiển thị
        final_pieces_numeric = int(total_pcs_final) if 'total_pcs_final' in locals() else int(pcs * layer_multiplier)
        r["Số lượng rập"] = final_pieces_numeric
        item["row_ref"]["Số lượng rập"] = final_pieces_numeric
        
        # Đồng bộ luôn cột khổ vải sản xuất ngay tại đầu ra dữ liệu chi tiết chi dòng
        if mat_class_raw == "FUSING":
            r["Khổ vải sản xuất (inch)"] = float(fusing_width)
        elif mat_class_raw == "LINING":
            r["Khổ vải sản xuất (inch)"] = float(lining_width)
        else:
            r["Khổ vải sản xuất (inch)"] = float(usable_width)
            
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
    # 🟩 ĐOẠN 3.2 (PHIÊN BẢN V27 - MASTER GEOMETRY - INDENTED): GEOMETRIC FEATURE ENGINE
    # =====================================================================
    import numpy as np
    import pandas as pd

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

    # 🛠️ BỘ PHÂN LOẠI CHẤT LIỆU LAYER TRÍ THỨC (FIXED LỖI PHÂN LOẠI)
    def _d3_internal_material_classify(row, idx, prod_cat):
        if "user_edited_materials" in st.session_state and idx in st.session_state["user_edited_materials"]:
            return str(st.session_state["user_edited_materials"][idx]).upper().strip()
            
        mat_str = str(row[m_col_check]).upper().strip() if m_col_check in row else ""
        comp_str = str(row.get(comp_col_check, row.get("component_name", ""))).upper().strip()
        
        fusing_kws = ["FUSING", "INTERLINING", "INTERFACING", "KEO", "MEC", "MẾCH", "BOND", "ADHESIVE", "LOT KEO", "TRICOT"]
        lining_kws = ["LINING", "LOT", "LÓT", "POCKETING", "MESH", "TAFFETA", "VAI LOT", "VẢI LÓT", "POCKET BAG"]
        rib_kws = ["RIB", "BO GÂN", "BO", "CỔ BO", "TAY BO", "BO CO", "BO TAY", "BO LAI", "BO LUNG"]
        contrast_kws = ["CONTRAST", "PHOI", "VẢI PHOI", "VAI PHOI", "COMBO", "MATCHING"]
        padding_kws = ["PADDING", "GÒN", "GON", "WADDING", "BÔNG LÓT", "BONG LOT", "QUILTING"]
        
        if any(k in comp_str for k in ["WAISTBAND", "LƯNG", "CẠP", "BELT", "POCKET"]) and not any(x in mat_str or x in comp_str for x in fusing_kws + lining_kws + rib_kws + contrast_kws + padding_kws):
            return "FABRIC"
            
        if any(k in mat_str or k in comp_str for k in fusing_kws): return "FUSING"
        if any(k in mat_str or k in comp_str for k in lining_kws): return "LINING"
        if any(k in mat_str or k in comp_str for k in rib_kws): return "RIB"        # Đã tách RIB độc lập
        if any(k in mat_str or k in comp_str for k in contrast_kws): return "CONTRAST" # Nhận diện vải phối
        if any(k in mat_str or k in comp_str for k in padding_kws): return "PADDING"   # Nhận diện gòn lót
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

        # Khôi phục số lượng mảnh đối xứng trái/phải mở rộng bảo vệ tà đầm/váy không bị thiếu
        c_name_lower = comp_name_clean.lower()
        if pcs_numeric_val <= 1.0:
            if any(x in c_name_lower for x in ["panel", "front", "back", "than truoc", "than sau", "sleeve", "tay", "pocket bag", "lot tui", "than vay", "than dam", "skirt panel", "side front", "side back"]):
                pcs_numeric_val = 2.0

        if any(k in comp_name_clean for k in ["POCKET", "TÚI", "WELT", "BAG"]):
            total_pocket_pieces += float(st.session_state["user_edited_pieces"].get(idx, pcs_numeric_val))

        if p_class_clean in ["FABRIC", "FUSING", "LINING", "CONTRAST", "RIB", "PADDING"]:
            current_pcs = float(st.session_state.get("user_edited_pieces", {}).get(idx, pcs_numeric_val))
            total_pattern_pieces += current_pcs
            
            try:
                net_area = float(r.get(area_col_check, 0.0))
                if np.isnan(net_area): net_area = 0.0
            except:
                net_area = 0.0
                
            l_val = float(r.get(l_prod_col_check, 0.0))
            w_val = float(r.get(w_prod_col_check, 0.0))
            
            # Không tự động chia đôi chiều rộng đối với rập tà váy rộng xòe của đồ nữ thời trang
            if p_class_clean == "FABRIC" and w_val > 16.0 and "SKIRT" not in product_category and "DRESS" not in product_category:
                w_val = w_val / 2.0
                if net_area > 0: net_area = net_area / 2.0
            
            bbox_area_check = l_val * w_val
            if net_area > bbox_area_check and bbox_area_check > 0:
                net_area = bbox_area_check * (0.76 if p_class_clean == "FABRIC" else 0.85)
            
            if net_area <= 0.0 and l_val > 0 and w_val > 0:
                net_area = l_val * w_val * (0.76 if p_class_clean == "FABRIC" else 0.85)
                
            if l_val > max_piece_length: max_piece_length = l_val
            if net_area > 0:
                for _ in range(int(current_pcs)):
                    piece_areas.append(net_area)

    # 🛠️ ĐỒNG BỘ SIÊU DỮ LIỆU SẠCH
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
    
    # Kế thừa an toàn lớp ảo tránh bị ghi đè rỗng
    virtual_pieces_layer_backup = ctx.get("ai_expert_decision", {}).get("virtual_pieces_layer", {})

    # Xuất bản dữ liệu kiểm toán sạch ra trục ngoài
    ctx["ai_expert_decision"]["geometry_features"] = features
    ctx["ai_expert_decision"]["longest_piece_length"] = max_piece_length
    ctx["ai_expert_decision"]["complexity_score"] = complexity_score
    ctx["ai_expert_decision"]["virtual_pieces_layer"] = virtual_pieces_layer_backup
    
    st.session_state["current_longest_piece_length"] = max_piece_length
    st.session_state["bom_data"] = ctx


        # =====================================================================
        # =====================================================================
       # =====================================================================
    # 🟩 ĐOẠN 4 (PHIÊN BẢN MASTER V33 - ĐỒNG BỘ ĐA TẦNG TUYỆT ĐỐI)
    # =====================================================================
    import pandas as pd
    import numpy as np

    comp_col_check = next((c for c in ["Component Name", "component_name", "Component_Name"] if c in df_bom.columns), "component_name")
    m_col_check = next((c for c in ["Material Class", "material_class"] if c in df_bom.columns), "material_class")

    # Đọc khổ vải động an toàn từ phiên chat (Ưu tiên RAM hệ thống)
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

    virtual_pieces_layer = {}

    for idx, row in df_bom.iterrows():
        comp_name_raw = str(row.get(comp_col_check, row.get("component_name", "")))
        comp_name_upper = comp_name_raw.upper().strip()
        mat_str = str(row.get(m_col_check, "")).upper().strip()
        
        if any(k in comp_name_upper or k in mat_str for k in ["THREAD", "CHỈ", "BUTTON", "NÚT", "ZIP", "ACCESSORY"]):
            p_class, class_confidence = "ACCESSORY", 1.0
        elif any(k in comp_name_upper or k in mat_str for k in ["FUSING", "MEC", "MẾCH", "KEO", "INTERLINING"]):
            p_class, class_confidence = "FUSING", 1.0
        elif any(k in comp_name_upper or k in mat_str for k in ["LINING", "LÓT", "POCKET BAG", "POCKETING", "RIB"]):
            p_class, class_confidence = "LINING", 1.0
        else:
            p_class, class_confidence = "FABRIC", 0.95

        l_orig = float(row.get("bounding_box_length", 0.0))
        w_orig = float(row.get("bounding_box_width", 0.0))
        net_area_real = float(row.get("polygon_net_area", 0.0))

        if l_orig <= 0 or w_orig <= 0: continue

        # 1. Aspect Ratio Correction (Sửa đảo trục canh sợi tự động)
        if w_orig > l_orig:
            l_orig, w_orig = w_orig, l_orig

        # 2. Adaptive OBB Efficiency Inference (Suy diễn hình thái học động phi tuyến tính)
        if net_area_real > 0:
            current_factor = net_area_real / (l_orig * w_orig)
            aspect_ratio = l_orig / w_orig
            log_aspect = np.log1p(aspect_ratio)
            
            target_obb_eff = max(0.6400, min(0.9200, 0.88 - (0.05 * log_aspect) + (0.15 * current_factor)))
            if current_factor < target_obb_eff:
                optimized_area = net_area_real / target_obb_eff
                w_orig = (optimized_area / aspect_ratio) ** 0.5
                l_orig = w_orig * aspect_ratio

        # 4. PCS MASTER - KHÔNG SUY LUẬN NHÂN ĐÔI THEO TÊN
        raw_pcs = float(row.get("pcs_numeric", row.get("Số lượng rập", 1.0)))
        raw_pcs = max(raw_pcs, 1.0)

        if idx in st.session_state.get("user_edited_pieces", {}):
            final_pcs = float(st.session_state["user_edited_pieces"][idx])
        else:
            final_pcs = raw_pcs
        final_pcs = max(final_pcs, 1.0)

        # 5. Shrinkage Matrix Application
        if p_class == "FABRIC":
            w_prod = round(w_orig * (1 + weft_shrink / 100.0), 3) if w_orig > 0 else fabric_width
            l_prod = round(l_orig * (1 + warp_shrink / 100.0), 3) if l_orig > 0 else 0.0
            
            # 🔥 ĐÃ SỬA: Ép cứng giá trị khổ vải từ ô chat vào dataframe gốc tại tầng lõi xử lý hình thái học
            df_bom.at[idx, "Khổ vải sản xuất (inch)"] = float(fabric_width)
            
        elif p_class == "FUSING":
            w_prod = round(w_orig * (1 + fusing_weft_shrink / 100.0), 3) if w_orig > 0 else 59.0
            l_prod = round(l_orig * (1 + fusing_warp_shrink / 100.0), 3) if l_orig > 0 else 0.0
            df_bom.at[idx, "Khổ vải sản xuất (inch)"] = 59.0
            
        elif p_class == "LINING":
            w_prod = round(w_orig * (1 + lining_weft_shrink / 100.0), 3) if w_orig > 0 else 57.0
            l_prod = round(l_orig * (1 + lining_warp_shrink / 100.0), 3) if l_orig > 0 else 0.0
            df_bom.at[idx, "Khổ vải sản xuất (inch)"] = 57.0
            
        else:
            w_prod, l_prod = w_orig, l_orig

        # 6. DIỆN TÍCH MASTER
        prod_bbox_area = w_prod * l_prod
        if net_area_real <= 0:
            net_area_real = prod_bbox_area * 0.74
        elif net_area_real > prod_bbox_area:
            net_area_real = prod_bbox_area * 0.85

        virtual_pieces_layer[idx] = {
            "material_class": p_class,                      
            "production_l": round(l_prod, 2), 
            "production_w": round(w_prod, 2), 
            "production_net_area": round(net_area_real, 2),
            "polygon_net_area": round(net_area_real, 2),    
            "active_user_pieces": final_pcs,                
            "component_name": comp_name_raw
        }

    for idx, vp in virtual_pieces_layer.items():
        if idx in df_bom.index:
            df_bom.at[idx, "Chiều dài rập (inch)"] = vp["production_l"]
            df_bom.at[idx, "Chiều rộng rập (inch)"] = vp["production_w"]
            df_bom.at[idx, "polygon_net_area"] = vp["production_net_area"]
            df_bom.at[idx, "Material Class"] = vp["material_class"]

    st.session_state["bom_data"]["ai_expert_decision"]["virtual_pieces_layer"] = virtual_pieces_layer


       # =====================================================================
    # 🟩 ĐOẠN 5.1 (PHIÊN BẢN V59 - CHUẨN HÓA VÀ ĐỒNG BỘ LIÊN TẦNG ERP)
    # =====================================================================
    import json
    import math  
    import re

    # 🛒 SINGLE SOURCE OF TRUTH - BỘ TRÍCH XUẤT KHỔ VẢI TỪ ĐOẠN CHAT THỜI GIAN THỰC
    user_query_text = str(st.session_state.get("last_submitted_query", "")).lower().strip()
    if user_query_text:
        chat_width_match = re.search(r"(khổ\s*vải|khổ|width)\s*(\d+(\.\d+)?)", user_query_text)
        if chat_width_match:
            # Ép biến toàn cục nhận số khổ vải mới nhất từ đoạn chat
            st.session_state["current_active_width"] = float(chat_width_match.group(2))

    if "bom_data" not in st.session_state or not isinstance(st.session_state["bom_data"], dict):
        st.session_state["bom_data"] = {}
    ctx = st.session_state["bom_data"]
    
    ai_decision_d5 = ctx.get("ai_expert_decision", {})
    if not isinstance(ai_decision_d5, dict): ai_decision_d5 = {}
        
    # Kế thừa lớp ảo sạch an toàn từ Đoạn 4 lưu trong State
    virtual_pieces_layer = ai_decision_d5.get("virtual_pieces_layer", {})
    if not virtual_pieces_layer or not isinstance(virtual_pieces_layer, dict):
        virtual_pieces_layer = st.session_state.get("bom_data", {}).get("ai_expert_decision", {}).get("virtual_pieces_layer", {})
    if not virtual_pieces_layer: virtual_pieces_layer = {}

    # ĐỒNG BỘ BIẾN KHỔ VẢI ĐỘNG CHUẨN THEO ĐOẠN CHAT YÊU CẦU
    current_fabric_width = float(st.session_state.get("current_active_width", 56.0))
    lining_width = float(st.session_state.get("lining_width", st.session_state.get("lining_width_inch", 57.0)))    
    fusing_width = float(st.session_state.get("fusing_width", st.session_state.get("fusing_width_inch", 59.0)))    
    
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
        
        p_len = float(v_piece.get("production_l", 0.0))
        if p_len <= 0 and l_col: p_len = float(r.get(l_col, 0.0))
            
        p_wid = float(v_piece.get("production_w", 0.0))
        if p_wid <= 0 and w_col: p_wid = float(r.get(w_col, 0.0))
            
        net_area = float(v_piece.get("polygon_net_area", 0.0))
        if net_area <= 0: net_area = float(r.get("polygon_net_area", 0.0))
            
        c_name_upper = str(r.get("component_name", "")).upper().strip()
        
        # SỬA LỖI NAME ERROR: Đổi row.get thành r.get cho đồng bộ vòng lặp iterrows
        p_class_check = str(v_piece.get("material_class", r.get("Material Class", "FABRIC"))).upper().strip()
        if any(x in c_name_upper for x in ["FUSING", "MEC", "MẾCH", "KEO", "INTERLINING", "WAISTBAND FUSING"]): 
            p_class_check = "FUSING"
        elif any(x in c_name_upper for x in ["LINING", "LÓT", "POCKET BAG", "POCKETING", "POCKET FACING"]): 
            p_class_check = "LINING"
        elif any(x in c_name_upper for x in ["CONTRAST", "PHỐI"]):
            p_class_check = "CONTRAST"
        elif any(x in c_name_upper for x in ["RIB", "BO CỔ", "BO TĂM"]):
            p_class_check = "RIB"
            
        v_piece["material_class"] = p_class_check  

        # Giữ nguyên bản diện tích tịnh đơn mảnh của rập CAD
        if net_area <= 0 and p_len > 0 and p_wid > 0:
            if any(k in c_name_upper for k in ["LEG", "THAN", "ỐNG", "PANEL", "BAG"]):
                net_area = p_len * p_wid * 0.82
            else:
                net_area = p_len * p_wid * (0.76 if "FABRIC" in p_class_check else 0.85)
        
        # ✅ SỬA LỖI 1: KHÓA CHẶT LOGIC TỰ ĐỘNG SUY DIỄN NHÂN ĐÔI PCS SAI LỆCH THEO TÊN
        raw_pcs = float(v_piece.get("inferred_pieces", r.get(pcs_col, 1.0)))
        raw_pcs = max(raw_pcs, 1.0)

        # Ưu tiên số lượng rập do người dùng biên tập tĩnh trên giao diện
        pcs = float(st.session_state.get("user_edited_pieces", {}).get(idx, raw_pcs))
        if pcs_col: df_bom.at[idx, pcs_col] = int(pcs)

        pcs = pcs * size_scale_ratio
        v_piece["active_user_pieces"] = int(pcs)

        # KHỬ LỖI RẬP VƯỢT KHỔ VẢI SẢN XUẤT ĐẦU VÀO
        target_limit_width = fusing_width if p_class_check == "FUSING" else (lining_width if p_class_check == "LINING" else current_fabric_width)
        if p_len > target_limit_width and p_len > 35.0:
            p_len = p_len / 2.0
            net_area = net_area / 2.0
            pcs = pcs * 2.0
            v_piece["active_user_pieces"] = int(pcs)

        list_lengths.append(round(p_len, 2) if p_len > 0 else 0.0)
        list_widths.append(round(p_wid, 2) if p_wid > 0 else 0.0)
        df_bom.at[idx, "polygon_net_area"] = round(net_area, 2)
        v_piece["polygon_net_area"] = round(net_area, 2)

        # ✅ SỬA LỖI 2: LOẠI BỎ TOÀN BỘ BỘ GHÉP CẶP ẢO LÀM SAI TỶ TRỌNG DIỆN TÍCH DÒNG
        if p_class_check in ["FABRIC", "FUSING", "INTERLINING", "LINING", "RIB", "CONTRAST"] and p_len > 0:
            loop_pcs = int(math.ceil(pcs))
            for _ in range(loop_pcs):
                raw_unpaired_pieces.append({
                    "idx": idx, "l": p_len, "w": p_wid, "area": net_area,
                    "material_class": p_class_check, "priority": 3
                })

    raw_unpaired_pieces.sort(key=lambda x: (x.get('priority', 3), -x['area']))
    df_bom["Chiều dài rập (inch)"] = list_lengths
    df_bom["Chiều rộng rập (inch)"] = list_widths
    
    # Cập nhật ngược lại bộ não State phục vụ liên tầng độc lập cho Đoạn 5.2 và Đoạn 7
    st.session_state["bom_data"]["ai_expert_decision"]["virtual_pieces_layer"] = virtual_pieces_layer

    import pandas as pd
    import streamlit as st

    # =====================================================================
    # 🟩 ĐOẠN 5.2 - PHẦN A: CONFIGURATION & MARKER EFFICIENCY ROUTER (V72.1)
    # =====================================================================
    _is_short = locals().get("is_short", False)
    _is_trouser = locals().get("is_trouser", False)
    _is_skirt_or_dress = locals().get("is_skirt_or_dress", False)
    _is_jacket = locals().get("is_jacket", False)

    style_code_upper = str(st.session_state.get("bom_data", {}).get("ai_expert_decision", {}).get("style_code", "")).upper().strip()
    material_spec_upper = str(st.session_state.get("bom_data", {}).get("ai_expert_decision", {}).get("material_spec", "")).upper().strip()
    p_type_friendly = str(st.session_state.get("bom_data", {}).get("ai_expert_decision", {}).get("product_type_friendly", "JEAN_LONG")).upper().strip()

    combined_search_text = f"{style_code_upper} | {material_spec_upper} | {p_type_friendly}"

    # 🤖 1. MA TRẬN HIỆU SUẤT SƠ ĐỒ CƠ SỞ CHUẨN CÔNG NGHIỆP IE
    MARKER_EFFICIENCY_MAP = {
        "DRESS": 0.66, "SKIRT": 0.66, "SHORT": 0.68,
        "JEAN": 0.68, "KHAKI": 0.74, "TROUSER": 0.69, "PANT": 0.7,
        "JACKET": 0.65, "COAT": 0.65, "BLAZER": 0.65, "SUIT": 0.65,
        "SHIRT": 0.78, "BLOUSE": 0.78,
        "POLO": 0.76, "TEE": 0.76, "TSHIRT": 0.76, "TANK": 0.74
    }

    dynamic_marker_efficiency = None
    detected_type_label = None

    for key, efficiency in MARKER_EFFICIENCY_MAP.items():
        if key in combined_search_text:
            dynamic_marker_efficiency = efficiency
            detected_type_label = key
            break

    if dynamic_marker_efficiency is None:
        if _is_skirt_or_dress:
            dynamic_marker_efficiency = 0.66
            detected_type_label = "DRESS/SKIRT"
        elif _is_short or "SHORT" in combined_search_text:
            dynamic_marker_efficiency = 0.68
            detected_type_label = "SHORT"
        elif _is_jacket:
            dynamic_marker_efficiency = 0.65
            detected_type_label = "JACKET"
        else:
            dynamic_marker_efficiency = 0.74
            detected_type_label = "JEAN_LONG"

    # 🔥 DYNAMIC CAD PENALTY: ĐỌC TRẠNG THÁI CHECKBOX TỪ GIAO DIỆN (UI CONTROLS)
    is_nap_mode = st.session_state.get("is_nap_fabric", False)          # Checkbox: Cắt mỗi bộ 1 chiều (Nap)
    is_one_way_mode = st.session_state.get("is_one_way_fabric", False)  # Checkbox: Tất cả size 1 chiều (One-Way)

    if is_one_way_mode:
        dynamic_marker_efficiency -= 0.05  # Trừ 5% hiệu suất cho vải tuyết/nhung
    elif is_nap_mode:
        dynamic_marker_efficiency -= 0.03  # Trừ 3% hiệu suất cho sơ đồ Nap

    dynamic_marker_efficiency = max(0.52, dynamic_marker_efficiency)

    # Đồng bộ dữ liệu chủng loại hàng vào hệ thống
    if "bom_data" not in st.session_state: st.session_state["bom_data"] = {}
    if "ai_expert_decision" not in st.session_state["bom_data"]: st.session_state["bom_data"]["ai_expert_decision"] = {}

    if detected_type_label and "DRESS" in detected_type_label:
        st.session_state["bom_data"]["ai_expert_decision"]["product_type_friendly"] = "DRESS (Đầm xòe/suông)"
    elif detected_type_label and "SKIRT" in detected_type_label:
        st.session_state["bom_data"]["ai_expert_decision"]["product_type_friendly"] = "SKIRT (Chân váy)"
    elif detected_type_label and "SHORT" in detected_type_label:
        st.session_state["bom_data"]["ai_expert_decision"]["product_type_friendly"] = "SHORT (Quần short)"

    # Đẩy thông số hiệu suất sơ đồ tính toán được vào bộ não tổng để Đoạn 7 lấy dùng hiển thị
    st.session_state["bom_data"]["ai_expert_decision"]["marker_efficiency"] = dynamic_marker_efficiency
      # =====================================================================
    # 🟩 ĐOẠN 5.2 - PHẦN B: IE COMMERCIAL CONSUMPTION CALCULATOR (V75 - RE-ARCH PIECES)
    # =====================================================================

    stored_virtual_pieces = st.session_state.get("bom_data", {}).get("ai_expert_decision", {}).get("virtual_pieces_layer", {})
    if not isinstance(stored_virtual_pieces, dict): 
        stored_virtual_pieces = {}

    calculated_gross_list = []
    summary_grouped_gross = {"FABRIC": 0.0, "FUSING": 0.0, "LINING": 0.0, "CONTRAST": 0.0, "RIB": 0.0, "PADDING": 0.0}

    # Khởi tạo sẵn các cột Master trên DataFrame gốc
    if "Số lượng rập" not in df_bom.columns: df_bom["Số lượng rập"] = None
    if "Gross Consumption" not in df_bom.columns: df_bom["Gross Consumption"] = 0.0
    if "Khổ vải sản xuất (inch)" not in df_bom.columns: df_bom["Khổ vải sản xuất (inch)"] = 56.0

    # Trích xuất tỷ lệ co rút từ bộ nhớ đệm đoạn chat (Chia 100 để ra tỷ lệ phần thập phân)
    shrink_v = float(st.session_state.get("shrinkage_vertical", 0.0)) / 100.0   # Co dọc (VD: 3% -> 0.03)
    shrink_h = float(st.session_state.get("shrinkage_horizontal", 0.0)) / 100.0 # Co ngang (VD: 14% -> 0.14)

    # Hệ số hao hụt vận hành bàn cắt thực tế xưởng may (Giữ ở mức 6% để bù đầu cây, vải lỗi)
    wastage_allowance = 1.06

    # 🔥 ENGINE CÂN BẰNG ĐỊNH MỨC THƯƠNG MẠI CHUẨN XƯỞNG MAY
    for idx, r in df_bom.iterrows():
        v = stored_virtual_pieces.get(idx, stored_virtual_pieces.get(str(idx), {}))
        if not isinstance(v, dict): 
            v = {}
        
        c_name_lower = str(r.get("component_name", v.get("component_name", ""))).lower().strip()

        # Phân loại nhóm vật tư động
        p_cls = None
        for field in ["Material Class", "material_class", "inferred_class"]:
            if field in r and pd.notna(r[field]): p_cls = str(r[field]).upper().strip()
            elif field in v and pd.notna(v[field]): p_cls = str(v[field]).upper().strip()
            if p_cls in summary_grouped_gross: break

        if not p_cls or p_cls not in summary_grouped_gross or p_cls == "FABRIC":
            if any(x in c_name_lower for x in ["rib", "bo co", "bo tay", "bo lai", "bo lung"]): p_cls = "RIB"
            elif any(x in c_name_lower for x in ["contrast", "phoi", "vai phoi", "combo", "matching"]): p_cls = "CONTRAST"
            elif any(x in c_name_lower for x in ["padding", "gon", "wadding", "bong lot", "quilting"]): p_cls = "PADDING"
            elif any(x in c_name_lower for x in ["lining", "vai lot", "lot than", "lot tui"]): p_cls = "LINING"
            elif any(x in c_name_lower for x in ["fusing", "keo", "interlining", "mex", "mec", "dung"]): p_cls = "FUSING"
            else: p_cls = "FABRIC"

        # Đọc thông số kích thước hình học rập để thẩm định diện tích thực
        piece_length = float(v.get("length", r.get("length", r.get("Chiều dài rập (inch)", 0.0))))
        piece_width = float(v.get("width", r.get("width", r.get("Chiều rộng rập (inch)", 0.0))))
        bbox_area = piece_length * piece_width

        # =====================================================================
        # 🚨 ĐÃ SỬA: THUẬT TOÁN ĐẾM MẢNH RẬP PHÂN CẶP ĐỐI XỨNG (ANTI-MISCOUNT)
        # Bỏ hoàn toàn điều kiện giới hạn diện tích < 450.0 vô lý gây hụt ống quần
        # =====================================================================
        if any(x in c_name_lower for x in ["back body", "collar top", "collar band", "belt loop", "diat"]):
            pcs_default = 1
        elif any(x in c_name_lower for x in ["leg", "panel", "front", "back", "than truoc", "than sau", "sleeve", "tay", "pocket bag", "lot tui", "pocket facing", "dap tui", "fly", "shield", "facing"]):
            pcs_default = 2  # Ép buộc nhân 2 mảnh đối xứng (Trái + Phải) cho các chi tiết cấu thành ống quần/túi quần
        else:
            pcs_default = 1  

        if "user_edited_pieces" in st.session_state and idx in st.session_state["user_edited_pieces"]:
            pcs = int(st.session_state["user_edited_pieces"][idx])
        elif pd.notna(r.get("Số lượng rập")) and int(r["Số lượng rập"]) >= 2:
            pcs = int(r["Số lượng rập"])
        elif "active_user_pieces" in v and int(v["active_user_pieces"]) >= 1:
            pcs = int(v["active_user_pieces"])
        else:
            pcs = pcs_default

        pcs = max(pcs, 1)
        df_bom.at[idx, "Số lượng rập"] = int(pcs)
        if idx not in stored_virtual_pieces: stored_virtual_pieces[idx] = {}
        stored_virtual_pieces[idx]["active_user_pieces"] = pcs

        pure_unit_area = float(v.get("polygon_net_area", r.get("polygon_net_area", 0.0)))

        # Thẩm định và khôi phục diện tích rập nếu file rập CAD bị lỗi trả về diện tích tịnh rỗng
        min_coverage = 0.76 if (detected_type_label and ("DRESS" in detected_type_label or "SKIRT" in detected_type_label)) else 0.72
        if pure_unit_area <= 0.0 or (any(x in c_name_lower for x in ["panel", "front", "back", "than", "sleeve", "tay"]) and pure_unit_area < bbox_area * min_coverage):
            # Điền khuyết diện tích sơ đồ bao hình thực tế
            pure_unit_area = bbox_area * (0.83 if p_cls == "FUSING" else 0.78)
        
        # Bù thêm 6% diện tích an toàn cho chu vi đường viền may (Seam Allowance) quanh rập đơn chiếc
        seam_modifier = 1.06 if p_cls in ["FABRIC", "CONTRAST"] else 1.0
        total_piece_area = pure_unit_area * pcs * seam_modifier
        
        # Xác định khổ vải thực tế đầu vào
        if p_cls == "FUSING": current_w = float(st.session_state.get("fusing_width", 59.0))
        elif p_cls == "LINING": current_w = float(st.session_state.get("lining_width", 57.0))
        elif p_cls == "RIB": current_w = float(st.session_state.get("rib_width", 40.0))
        elif p_cls == "PADDING": current_w = float(st.session_state.get("padding_width", 60.0))
        else: current_w = float(st.session_state.get("current_active_width", 56.0))
            
        if current_w <= 0: current_w = 56.0 

        # Hiệu suất sơ đồ đơn thực tế ngoài bàn cắt (64%)
        row_efficiency = dynamic_marker_efficiency
        if row_efficiency > 0.66 and p_cls in ["FABRIC", "CONTRAST"]:
            row_efficiency = 0.64
            
        if p_cls == "RIB": row_efficiency = 0.82
        elif p_cls == "PADDING": row_efficiency = 0.85

        # =====================================================================
        # ⚙️ TOÁN TỬ TÍNH ĐỊNH MỨC THEO CHUẨN CO RÚT LẬP TRÌNH MAY ERP
        # =====================================================================
        if p_cls in ["FABRIC", "CONTRAST"]:
            effective_width = current_w * (1.0 - shrink_h)
        else:
            effective_width = current_w

        if effective_width <= 0: effective_width = 56.0

        pure_length_inch = total_piece_area / (effective_width * row_efficiency)

        if p_cls in ["FABRIC", "CONTRAST"]:
            length_inch_with_shrink = pure_length_inch * (1.0 + shrink_v)
        else:
            length_inch_with_shrink = pure_length_inch

        gross_yds = (length_inch_with_shrink / 36.0) * wastage_allowance
        gross_yds = round(gross_yds, 4)

        # =====================================================================
        # 🔗 KHÓA CHẶT ĐỒNG BỘ: GHI NGƯỢC GIÁ TRỊ MỚI VÀO DATAFRAME MASTER
        # =====================================================================
        df_bom.at[idx, "Gross Consumption"] = float(gross_yds)
        df_bom.at[idx, "Khổ vải sản xuất (inch)"] = float(current_w)
        
        calculated_gross_list.append(gross_yds)
        summary_grouped_gross[p_cls] += gross_yds

    # Tích lũy tổng định mức nhóm vật tư lên Session State để đồng bộ bảng Summary Đoạn 7.1
    st.session_state["summary_fabric_gross"] = round(summary_grouped_gross["FABRIC"], 4)
    st.session_state["summary_fusing_gross"] = round(summary_grouped_gross["FUSING"], 4)
    st.session_state["summary_lining_gross"] = round(summary_grouped_gross["LINING"], 4)
    st.session_state["summary_contrast_gross"] = round(summary_grouped_gross["CONTRAST"], 4)
    st.session_state["summary_rib_gross"] = round(summary_grouped_gross["RIB"], 4)
    st.session_state["summary_padding_gross"] = round(summary_grouped_gross["PADDING"], 4)


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
    import re
    import pandas as pd

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

    ai_decision_final = ctx.get("ai_expert_decision", {})
    virtual_pieces = ai_decision_final.get("virtual_pieces_layer", {})

    comp_score_val = float(ai_decision_final.get("complexity_score", 45.0))
    ui_complexity_tier = "COMPLEX" if comp_score_val >= 50 else "NORMAL"
    ui_complexity_icon = "🔴" if comp_score_val >= 75 else ("🟡" if comp_score_val >= 45 else "🟢")
    real_sync_product_type = str(ai_decision_final.get("product_type_friendly", "JEAN_LONG (Quần dài Jeans/Pants)")).strip()

    # Rút đúng hiệu suất động từ Đoạn 5.2 truyền xuống
    marker_efficiency = float(ai_decision_final.get("marker_efficiency", 0.7400))

    # Đọc khổ vải sản xuất động từ Session State
    chat_width_override = st.session_state.get("current_active_width", 56.0)
    st.caption(f"🔗 **Khổ vải sản xuất đang ép sử dụng từ đoạn Chat:** `{chat_width_override:.1f}\" inch`")

    # 1. HIỂN THỊ MA TRẬN METRICS ĐỒNG BỘ
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("🤖 Loại Hàng Nhận Diện", real_sync_product_type)
    m2.metric(f"{ui_complexity_icon} Mức Độ Phức Tạp", f"{ui_complexity_tier} ({comp_score_val:.0f}/100)")
    m3.metric("📐 Mật Độ Sơ Đồ Chỉ Định", f"{marker_efficiency * 100:.2f}%") 
    m4.metric("🎯 Độ Tin Cậy AI (Confidence)", f"{float(ctx.get('confidence', 0.95))*100:.1f}%")

    # 2. PHỤC HỒI NỀN LƯỚI CHI TIẾT SẠCH THỪA HƯỞNG TỪ LÕI MASTER ĐOẠN 5.2
    df_bom_display = df_bom.copy()
    c_name_col_raw = next((c for c in ["component_name", "Component Name", "Component_Name"] if c in df_bom.columns), "component_name")

    df_bom_display["Size tính toán"] = str(st.session_state.get("current_active_size", ctx.get("detected_base_size", "32"))).upper().strip()
    df_bom_display["Component Name"] = df_bom_display[c_name_col_raw]
    df_bom_display["Role/Piece Type"] = "PRIMARY"
    df_bom_display["_original_row_index"] = df_bom.index

    # Đồng bộ tuyệt đối dữ liệu định mức và số lượng rập từ DataFrame Master
    if "Gross Consumption" in df_bom.columns:
        df_bom_display["Gross Consumption"] = df_bom["Gross Consumption"]
    else:
        df_bom_display["Gross Consumption"] = 0.0

    if "Số lượng rập" in df_bom.columns:
        df_bom_display["Số lượng rập"] = df_bom["Số lượng rập"]
    else:
        df_bom_display["Số lượng rập"] = 1

    # Đồng bộ chất liệu sạch lên bảng hiển thị
    clean_mats = []
    for idx, row in df_bom_display.iterrows():
        solver_piece_data = virtual_pieces.get(idx, virtual_pieces.get(str(idx), {})) if isinstance(virtual_pieces, dict) else {}
        p_cls = st.session_state.get("user_edited_mats", {}).get(idx, solver_piece_data.get("material_class", row.get("Material Class", "FABRIC"))).upper().strip()
        clean_mats.append(p_cls)
    df_bom_display["Material Class"] = clean_mats

    # 3. 📊 RENDER BẢNG TỔNG HỢP BOM SUMMARY ĐỒNG BỘ 100% THEO LÕI STATE
    total_fabric = st.session_state.get("summary_fabric_gross", 0.0)
    total_fusing = st.session_state.get("summary_fusing_gross", 0.0)
    total_lining = st.session_state.get("summary_lining_gross", 0.0)
    total_contrast = st.session_state.get("summary_contrast_gross", 0.0)
    total_rib = st.session_state.get("summary_rib_gross", 0.0)
    total_padding = st.session_state.get("summary_padding_gross", 0.0)

    summary_data = {"Phân loại vật tư": [], "Material Class": [], "Gross Consumption": [], "UOM": []}

    if total_fabric > 0 or (total_fabric == 0.0 and total_fusing == 0.0):
        summary_data["Phân loại vật tư"].append("VẢI CHÍNH")
        summary_data["Material Class"].append("FABRIC")
        summary_data["Gross Consumption"].append(round(total_fabric, 4))
        summary_data["UOM"].append("Yds")
    if total_contrast > 0:
        summary_data["Phân loại vật tư"].append("VẢI PHỐI")
        summary_data["Material Class"].append("CONTRAST")
        summary_data["Gross Consumption"].append(round(total_contrast, 4))
        summary_data["UOM"].append("Yds")
    if total_fusing > 0:
        summary_data["Phân loại vật tư"].append("MÉC / KEO")
        summary_data["Material Class"].append("FUSING")
        summary_data["Gross Consumption"].append(round(total_fusing, 4))
        summary_data["UOM"].append("Yds")
    if total_lining > 0:
        summary_data["Phân loại vật tư"].append("VẢI LÓT")
        summary_data["Material Class"].append("LINING")
        summary_data["Gross Consumption"].append(round(total_lining, 4))
        summary_data["UOM"].append("Yds")
    if total_rib > 0:
        summary_data["Phân loại vật tư"].append("BO / RIB")
        summary_data["Material Class"].append("RIB")
        summary_data["Gross Consumption"].append(round(total_rib, 4))
        summary_data["UOM"].append("Yds")
    if total_padding > 0:
        summary_data["Phân loại vật tư"].append("GÒN LÓT THÂN")
        summary_data["Material Class"].append("PADDING")
        summary_data["Gross Consumption"].append(round(total_padding, 4))
        summary_data["UOM"].append("Yds")

    df_summary = pd.DataFrame(summary_data)
    st.subheader("📊 BẢNG TỔNG HỢP BOM SUMMARY (YARDS)")
    st.dataframe(df_summary, use_container_width=True, hide_index=True)
    # =====================================================================
    # 🟩 ĐOẠN 7.2: RENDER BẢNG CHI TIẾT & BỘ LẮNG NGHE SỰ KIỆN BIÊN TẬP VẬT TƯ - V62 ĐỒNG BỘ HOÀN TOÀN TRỰC TIẾP
    # =====================================================================

    # 🔥 BẢO VỆ CHỐNG CRASH HỆ THỐNG KHI CHƯA CÓ FILE ĐẦU VÀO
    if 'df_bom_display' in locals() and df_bom_display is not None:

        # 🔄 ĐÃ SỬA: Đọc trực tiếp khổ vải thực tế dùng để tính toán từ Đoạn 5.2 bàn giao sang
        if "Khổ vải sản xuất (inch)" in df_bom.columns:
            df_bom_display["Khổ vải sản xuất (inch)"] = df_bom["Khổ vải sản xuất (inch)"]
        else:
            # Phòng hộ nếu cột chưa kịp khởi tạo
            df_bom_display["Khổ vải sản xuất (inch)"] = float(st.session_state.get("current_active_width", 56.0))

        # Chuẩn hóa kiểu dữ liệu số hiển thị ERP thương mại
        for col in ["Chiều dài rập (inch)", "Chiều rộng rập (inch)", "polygon_net_area", "Gross Consumption", "Khổ vải sản xuất (inch)"]:
            if col in df_bom_display.columns:
                df_bom_display[col] = pd.to_numeric(df_bom_display[col], errors='coerce').fillna(0.0)

        # Sắp xếp thứ tự các cột hiển thị đẹp mắt và loại bỏ bảng thô thừa
        ordered_cols = ["_original_row_index", "Component Name", "Material Class", "Role/Piece Type", "Chiều dài rập (inch)", "Chiều rộng rập (inch)", "Khổ vải sản xuất (inch)", "Size tính toán", "Số lượng rập", "polygon_net_area", "Gross Consumption"]
        display_final_cols = [c for c in ordered_cols if c in df_bom_display.columns]
        df_bom_display = df_bom_display[display_final_cols]

        col_t1, col_t2 = st.columns(2)
        col_t1.subheader("🔍 LƯỚI CHI TIẾT ĐỊNH MỨC TOÀN BỘ CHI TIẾT (BOM DETAILS)")

        # XUẤT FILE EXCEL ĐỒNG BỘ THEO ĐỊNH MỨC GỐC
        with col_t2:
            try:
                if 'local_export_excel_ppj_format' in locals():
                    excel_file = local_export_excel_ppj_format(
                        df_summary if 'df_summary' in locals() else None, 
                        df_bom_display.drop(columns=["_original_row_index"], errors="ignore"), 
                        prod if 'prod' in locals() else "JEAN", 
                        ctx if 'ctx' in locals() else {}, 
                        marker_efficiency if 'marker_efficiency' in locals() else 0.74
                    )
                    style_name_clean = str(ctx.get('style_code', 'Style')).strip().replace('/', '_').replace('\\', '_') if 'ctx' in locals() else 'Style'
                    st.download_button("🟢 DOWNLOAD EXCEL ĐỊNH MỨC THƯƠNG MẠI", data=excel_file, mime="application/vnd.openpyxl_formats-officedocument.spreadsheetml.sheet", file_name=f"PPJ_BOM_{style_name_clean}.xlsx", use_container_width=True)
            except Exception as e: 
                pass

        # Đảm bảo khởi tạo vùng nhớ State lưu trữ chỉnh sửa thủ công
        if "user_edited_pieces" not in st.session_state: st.session_state["user_edited_pieces"] = {}
        if "user_edited_mats" not in st.session_state: st.session_state["user_edited_mats"] = {}

        # DUY NHẤT 1 BẢNG CHỈNH SỬA DỮ LIỆU ĐỘNG FIXED V11
        edited_df = st.data_editor(
            df_bom_display, 
            key="bom_data_editor_matrix_fixed_v9",
            use_container_width=True,
            column_config={
                "_original_row_index": None, 
                "Component Name": st.column_config.TextColumn("📋 Component Name", disabled=True),
                "Material Class": st.column_config.SelectboxColumn(
                    "🧵 Material Class", 
                    options=["FABRIC", "LINING", "FUSING", "CONTRAST", "RIB"],
                    required=True,
                    disabled=False
                ),
                "Role/Piece Type": st.column_config.TextColumn("Role/Piece Type", disabled=True),
                "Chiều dài rập (inch)": st.column_config.NumberColumn("📏 Chiều dài rập (inch)", format="%.2f", disabled=True),
                "Chiều rộng rập (inch)": st.column_config.NumberColumn("📐 Chiều rộng rập (inch)", format="%.2f", disabled=True),
                "Khổ vải sản xuất (inch)": st.column_config.NumberColumn("Khổ vải sản xuất (inch)", format="%.1f", disabled=True),
                "Size tính toán": st.column_config.TextColumn("Size tính toán", disabled=True),
                "Số lượng rập": st.column_config.NumberColumn("🔢 Số lượng rập", format="%d", min_value=1, disabled=False),
                "polygon_net_area": st.column_config.NumberColumn("polygon_net_area", format="%.2f", disabled=True),
                "Gross Consumption": st.column_config.NumberColumn("Gross Consumption", format="%.4f", disabled=True)
            }
        )

        # BỘ LẮNG NGHE SỰ KIỆN: Chỉ kích hoạt rerun khi có tương tác thủ công từ người dùng
        if edited_df is not None and "bom_data_editor_matrix_fixed_v9" in st.session_state:
            editor_state = st.session_state["bom_data_editor_matrix_fixed_v9"]
            
            if "edited_rows" in editor_state and len(editor_state["edited_rows"]) > 0:
                changes = editor_state["edited_rows"]
                has_updates = False
                
                for row_idx_str, updated_cols in changes.items():
                    row_idx = int(row_idx_str)
                    orig_idx = df_bom_display.iloc[row_idx]["_original_row_index"]
                    
                    if "Số lượng rập" in updated_cols:
                        st.session_state["user_edited_pieces"][orig_idx] = int(updated_cols["Số lượng rập"])
                        has_updates = True
                        
                    if "Material Class" in updated_cols:
                        st.session_state["user_edited_mats"][orig_idx] = str(updated_cols["Material Class"]).upper().strip()
                        has_updates = True
                        
                if has_updates:
                    st.rerun()
    else:
        st.info("💡 Vui lòng chờ hệ thống xử lý hoặc tải lên tệp phôi rập để hiển thị bảng định mức chi tiết.")
