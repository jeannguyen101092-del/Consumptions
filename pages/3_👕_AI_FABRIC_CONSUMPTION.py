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
# 🧠 ĐOẠN A - AI PURE SCAN
# VERSION V24.6
# MASTER GEOMETRY SAFE + PIECE QTY SAFE
# MASTER WIDTH / SHRINK USER COMMAND LOCK
# =====================================================================

import copy
import hashlib
import json
import re
import fitz
import google.generativeai as genai
import streamlit as st


# =====================================================================
# 🔒 MASTER PARAMETER PARSER
# ƯU TIÊN TUYỆT ĐỐI GIÁ TRỊ TỪ USER COMMAND
# =====================================================================

def parse_master_user_parameters(
    current_query,
    active_width,
    target_size_cmd,
):

    query = str(
        current_query or ""
    ).strip()

    # -----------------------------------------------------------------
    # DEFAULT SAFE VALUES
    # -----------------------------------------------------------------

    resolved_width = None
    resolved_warp_shrink = None
    resolved_weft_shrink = None
    resolved_size = target_size_cmd

    # -----------------------------------------------------------------
    # TEXT NORMALIZATION
    # -----------------------------------------------------------------

    normalized_query = (
        query
        .replace(",", ".")
        .replace("％", "%")
        .replace("”", '"')
        .replace("″", '"')
    )

    # =================================================================
    # 1. SIZE
    # =================================================================

    size_patterns = [
        r"\bsize\s*[:=]?\s*(\d+(?:\.\d+)?)\b",
        r"\bsize\s*(\d+(?:\.\d+)?)\b",
        r"\bSZ\s*[:=]?\s*(\d+(?:\.\d+)?)\b",
        r"\bSZ\s*(\d+(?:\.\d+)?)\b",
    ]

    for pattern in size_patterns:

        match = re.search(
            pattern,
            normalized_query,
            re.IGNORECASE
        )

        if match:

            resolved_size = (
                match.group(1).strip()
            )

            break

    # =================================================================
    # 2. KHỔ VẢI
    #
    # Hỗ trợ:
    #   khổ 58
    #   khổ vải 58
    #   kho 58
    #   width 58
    #   fabric width 58
    #   khổ = 58
    # =================================================================

    width_patterns = [

        r"(?:khổ\s*vải|khổ|kho)\s*[:=]?\s*"
        r"(\d+(?:\.\d+)?)\s*(?:[\"']|inch|in)?",

        r"(?:fabric\s*width|width)\s*[:=]?\s*"
        r"(\d+(?:\.\d+)?)\s*(?:[\"']|inch|in)?",
    ]

    for pattern in width_patterns:

        match = re.search(
            pattern,
            normalized_query,
            re.IGNORECASE
        )

        if match:

            try:

                resolved_width = float(
                    match.group(1)
                )

            except Exception:

                resolved_width = None

            break

    # =================================================================
    # 3. CO DỌC
    #
    # Hỗ trợ:
    #   dọc 3
    #   doc 3
    #   co doc 3
    #   co dọc 3%
    #   warp 3
    #   warp shrink 3%
    # =================================================================

    warp_patterns = [

        r"(?:co\s*)?(?:dọc|doc)\s*[:=]?\s*"
        r"(\d+(?:\.\d+)?)\s*%?",

        r"(?:warp|warp\s*shrink|warp\s*shrinkage)"
        r"\s*[:=]?\s*(\d+(?:\.\d+)?)\s*%?",
    ]

    for pattern in warp_patterns:

        match = re.search(
            pattern,
            normalized_query,
            re.IGNORECASE
        )

        if match:

            try:

                resolved_warp_shrink = float(
                    match.group(1)
                )

            except Exception:

                resolved_warp_shrink = None

            break

    # =================================================================
    # 4. CO NGANG
    #
    # Hỗ trợ:
    #   ngang 15
    #   ngang 15%
    #   co ngang 15
    #   weft 15
    #   weft shrink 15%
    # =================================================================

    weft_patterns = [

        r"(?:co\s*)?(?:ngang)\s*[:=]?\s*"
        r"(\d+(?:\.\d+)?)\s*%?",

        r"(?:weft|weft\s*shrink|weft\s*shrinkage)"
        r"\s*[:=]?\s*(\d+(?:\.\d+)?)\s*%?",
    ]

    for pattern in weft_patterns:

        match = re.search(
            pattern,
            normalized_query,
            re.IGNORECASE
        )

        if match:

            try:

                resolved_weft_shrink = float(
                    match.group(1)
                )

            except Exception:

                resolved_weft_shrink = None

            break

    # =================================================================
    # 5. FALLBACK WIDTH
    #
    # CHỈ dùng active_width nếu USER KHÔNG nhập khổ.
    # =================================================================

    if resolved_width is None:

        try:

            resolved_width = float(
                active_width
            )

        except Exception:

            resolved_width = 56.0

    # =================================================================
    # 6. FALLBACK SHRINK
    #
    # Không dùng 4% cứng.
    # Nếu user không nhập thì giữ None để tầng IE xử lý.
    # =================================================================

    if resolved_warp_shrink is not None:

        resolved_warp_shrink = float(
            resolved_warp_shrink
        )

    if resolved_weft_shrink is not None:

        resolved_weft_shrink = float(
            resolved_weft_shrink
        )

    # =================================================================
    # 7. RETURN MASTER PARAMETERS
    # =================================================================

    return {
        "target_size": resolved_size,
        "fabric_width": float(
            resolved_width
        ),
        "warp_shrink_percent": (
            resolved_warp_shrink
        ),
        "weft_shrink_percent": (
            resolved_weft_shrink
        ),
    }


# =====================================================================
# 🧠 AI PURE SCAN
# =====================================================================

@st.cache_data(
    show_spinner=False,
    ttl=3600,
    hash_funcs={
        bytes: lambda b: hashlib.sha256(
            b
        ).hexdigest()
    },
)
def execute_final_gerber_pure_scan(
    pdf_bytes,
    current_query,
    active_width,
    target_size_cmd,
    raw_json_schema,
    prompt_agent_2,
):

    # =================================================================
    # 0. MASTER USER PARAMETER RESOLUTION
    # =================================================================

    master_params = parse_master_user_parameters(
        current_query=current_query,
        active_width=active_width,
        target_size_cmd=target_size_cmd,
    )

    resolved_size = master_params[
        "target_size"
    ]

    resolved_width = master_params[
        "fabric_width"
    ]

    resolved_warp_shrink = master_params[
        "warp_shrink_percent"
    ]

    resolved_weft_shrink = master_params[
        "weft_shrink_percent"
    ]

    # =================================================================
    # 1. ĐỌC PDF BYTES
    # =================================================================

    if hasattr(
        pdf_bytes,
        "getvalue"
    ):

        pdf_bytes = pdf_bytes.getvalue()

    if not isinstance(
        pdf_bytes,
        bytes
    ):

        raise TypeError(
            "Dữ liệu PDF đầu vào không đúng định dạng bytes hợp lệ!"
        )

    # =================================================================
    # 2. ĐỌC TOÀN BỘ TEXT + ẢNH TECHPACK
    # =================================================================

    full_pdf_raw_text = ""

    image_payloads = []

    with fitz.open(
        stream=pdf_bytes,
        filetype="pdf"
    ) as doc_recovery:

        total_pages = len(
            doc_recovery
        )

        for page_idx in range(
            total_pages
        ):

            page_text = (
                doc_recovery[
                    page_idx
                ].get_text("text")
            )

            full_pdf_raw_text += (
                f"\n--- PAGE {page_idx + 1} ---\n"
                f"{page_text}"
            )

            # ---------------------------------------------------------
            # CHỈ LẤY TỐI ĐA 2 TRANG ẢNH
            # ---------------------------------------------------------

            if len(
                image_payloads
            ) < 2:

                try:

                    pix = (
                        doc_recovery[
                            page_idx
                        ].get_pixmap(
                            dpi=72,
                            colorspace=fitz.csRGB
                        )
                    )

                    image_payloads.append(
                        {
                            "mime_type": "image/jpeg",
                            "data": pix.tobytes(
                                "jpeg"
                            ),
                        }
                    )

                except Exception:

                    continue

    # =================================================================
    # 3. MASTER PARAMETERS TEXT
    # =================================================================

    warp_text = (
        f"{resolved_warp_shrink:g}%"
        if resolved_warp_shrink is not None
        else "NOT SPECIFIED"
    )

    weft_text = (
        f"{resolved_weft_shrink:g}%"
        if resolved_weft_shrink is not None
        else "NOT SPECIFIED"
    )

    master_parameter_text = f"""
===============================================================
🔒 MASTER USER PARAMETERS - LOCKED
===============================================================

TARGET SIZE:
{resolved_size}

FABRIC WIDTH:
{resolved_width:g} INCH

WARP / VERTICAL SHRINKAGE:
{warp_text}

WEFT / HORIZONTAL SHRINKAGE:
{weft_text}

===============================================================
🚨 PRIORITY RULE
===============================================================

USER COMMAND HAS HIGHER PRIORITY THAN OLD CACHE,
DEFAULT VALUE, FALLBACK VALUE OR PREVIOUS SESSION VALUE.

If USER COMMAND explicitly contains:

KHỔ / WIDTH:
use that exact width.

DỌC / WARP:
use that exact vertical shrinkage.

NGANG / WEFT:
use that exact horizontal shrinkage.

SIZE:
use that exact size.

NEVER replace a user-provided value with:

56"
4%
previous session value
old BOM value
old cache value

===============================================================
"""

    # =================================================================
    # 4. INPUT CHO GEMINI
    # =================================================================

    gemini_inputs = list(
        image_payloads
    )

    gemini_inputs.insert(
        0,
        f"""
=== USER CHAT COMMAND ===
{current_query}

=== TECHPACK TEXT ===
{full_pdf_raw_text}

{master_parameter_text}

=== MASTER PARAMETERS SENT TO AI ===
TARGET SIZE = {resolved_size}
FABRIC WIDTH = {resolved_width:g} INCH
WARP SHRINK = {warp_text}
WEFT SHRINK = {weft_text}
"""
    )

    # =================================================================
    # 5. PROMPT MASTER
    # =================================================================

    extended_prompt = (
        prompt_agent_2
        + """

===============================================================
🚨 MASTER GEOMETRY SAFETY RULE
===============================================================

1. 'bounding_box_width' MUST represent ONE SINGLE physical CAD piece.

2. NEVER combine left/right pieces into one width.

3. NEVER divide a piece merely because its width is greater than
   16 inches.

4. A real garment panel is allowed to be wider than 16 inches.

5. NEVER automatically double 'piece_count' merely because a piece
   is wide.

6. 'cut_quantity' and 'piece_count' must follow the actual Techpack
   cutting instruction whenever such information is available.

7. If Techpack explicitly says CUT 2 / QTY 2 / PAIR:
   return 2.

8. If Techpack explicitly says CUT 1:
   return 1.

9. If Techpack says ONE PIECE:
   return 1.

10. If no explicit quantity exists, infer quantity from the actual
    garment construction, not merely from the word PANEL.

===============================================================
🚨 MASTER GEOMETRY AREA RULE
===============================================================

'polygon_net_area' must represent the estimated physical area of
ONE SINGLE pattern piece.

Do NOT inflate polygon_net_area to the full bounding rectangle.

For curved garment panels:

    polygon_net_area < bounding_box_length × bounding_box_width

The more curved/tapered the pattern is, the lower the fill ratio.

Typical guidance:

MAIN BODY PANEL:
0.70 - 0.86

JACKET BODY:
0.68 - 0.82

SLEEVE:
0.62 - 0.78

POCKET:
0.70 - 0.88

COLLAR:
0.55 - 0.75

WAISTBAND:
0.80 - 0.95

RECTANGULAR STRAIGHT PIECE:
0.90 - 0.98

Do NOT automatically use 0.92 for every piece.

===============================================================
🚨 PRODUCT TYPE
===============================================================

Determine the real garment type from:

1. Techpack sketch
2. garment description
3. construction
4. pattern/component structure
5. product name

Do NOT default to JEAN_LONG.

A short pant must be SHORT.

A jacket must be JACKET.

A long jean must be JEAN_LONG.

===============================================================
🚨 WIDTH / SHRINK PARAMETER LOCK
===============================================================

The following values have already been resolved from the USER
COMMAND by the MASTER PARAMETER PARSER.

TARGET SIZE:
{resolved_size}

FABRIC WIDTH:
{resolved_width:g} INCH

WARP SHRINK:
{warp_text}

WEFT SHRINK:
{weft_text}

Do NOT invent or replace these values.

If these values appear in the Techpack and conflict with the
explicit USER COMMAND, the USER COMMAND has priority for the
current IE calculation.

===============================================================
"""
    )

    gemini_inputs.append(
        extended_prompt
    )

    # =================================================================
    # 6. GEMINI
    # =================================================================

    model = genai.GenerativeModel(
        "gemini-2.5-flash"
    )

    response = model.generate_content(
        gemini_inputs,
        generation_config={
            "response_mime_type": "application/json",
            "response_schema": raw_json_schema,
            "temperature": 0.0,
        },
        request_options={
            "timeout": 120.0
        },
    )

    if (
        not response
        or not response.text
    ):

        raise RuntimeError(
            "Mô hình Gemini trả về kết quả rỗng!"
        )

    txt = response.text.strip()

    # =================================================================
    # 7. CLEAN MARKDOWN JSON
    # =================================================================

    if txt.startswith("```"):

        txt = re.sub(
            r"^```json\s*",
            "",
            txt
        )

        txt = re.sub(
            r"^```\s*",
            "",
            txt
        )

        txt = re.sub(
            r"\s*```$",
            "",
            txt
        )

    txt = txt.strip()

    # =================================================================
    # 8. PARSE JSON
    # =================================================================

    try:

        blueprint_worker = json.loads(
            txt
        )

    except json.JSONDecodeError as json_err:

        raise RuntimeError(
            "Mô hình Gemini trả về JSON không hợp lệ:\n\n"
            + txt
        ) from json_err

    # =================================================================
    # 9. NORMALIZE BOM
    # =================================================================

    if (
        blueprint_worker
        and "bom_rows"
        in blueprint_worker
    ):

        # -------------------------------------------------------------
        # LOCK CALCULATED SIZE
        # -------------------------------------------------------------

        blueprint_worker[
            "calculated_on_size"
        ] = resolved_size

        # -------------------------------------------------------------
        # 🔒 MASTER IE PARAMETERS
        # -------------------------------------------------------------

        blueprint_worker[
            "master_fabric_width_inch"
        ] = round(
            float(
                resolved_width
            ),
            2
        )

        blueprint_worker[
            "master_warp_shrink_percent"
        ] = (
            round(
                float(
                    resolved_warp_shrink
                ),
                4
            )
            if resolved_warp_shrink is not None
            else None
        )

        blueprint_worker[
            "master_weft_shrink_percent"
        ] = (
            round(
                float(
                    resolved_weft_shrink
                ),
                4
            )
            if resolved_weft_shrink is not None
            else None
        )

        # -------------------------------------------------------------
        # PRODUCT TYPE
        # -------------------------------------------------------------

        detected_type = str(
            blueprint_worker.get(
                "detected_product_type",
                "JEAN_LONG"
            )
        ).upper().strip()

        blueprint_worker[
            "detected_product_type"
        ] = detected_type

        # -------------------------------------------------------------
        # COMPONENT LOOP
        # -------------------------------------------------------------

        for row in blueprint_worker.get(
            "bom_rows",
            []
        ):

            # =========================================================
            # COMPONENT NAME
            # =========================================================

            if "component_name" in row:

                row["component_name"] = (
                    " ".join(
                        str(
                            row[
                                "component_name"
                            ]
                        ).upper().split()
                    )
                )

            comp_name = str(
                row.get(
                    "component_name",
                    ""
                )
            ).upper().strip()

            # =========================================================
            # DIMENSIONS
            # =========================================================

            try:

                row[
                    "bounding_box_length"
                ] = round(
                    float(
                        row.get(
                            "bounding_box_length",
                            0.0
                        )
                    ),
                    2
                )

            except Exception:

                row[
                    "bounding_box_length"
                ] = 0.0

            try:

                row[
                    "bounding_box_width"
                ] = round(
                    float(
                        row.get(
                            "bounding_box_width",
                            0.0
                        )
                    ),
                    2
                )

            except Exception:

                row[
                    "bounding_box_width"
                ] = 0.0

            # =========================================================
            # MATERIAL
            # =========================================================

            mat_class = str(
                row.get(
                    "material_class",
                    "FABRIC"
                )
            ).upper().strip()

            if any(
                k in comp_name
                for k in [
                    "FUSING",
                    "INTERLINING",
                    "MEX",
                    "DỰNG",
                    "KEO"
                ]
            ):

                mat_class = "FUSING"

            elif any(
                k in comp_name
                for k in [
                    "LINING",
                    "POCKET BAG",
                    "LOT TUI",
                    "LÓT"
                ]
            ):

                mat_class = "LINING"

            elif any(
                k in comp_name
                for k in [
                    "RIB",
                    "BO GÂN",
                    "BO"
                ]
            ):

                mat_class = "RIB"

            row[
                "material_class"
            ] = mat_class

            # =========================================================
            # PIECE COUNT
            # =========================================================

            try:

                raw_qty = row.get(
                    "piece_count",
                    row.get(
                        "cut_quantity",
                        1
                    )
                )

                row[
                    "piece_count"
                ] = max(
                    1,
                    int(
                        float(
                            raw_qty
                        )
                    )
                )

            except Exception:

                row[
                    "piece_count"
                ] = 1

            try:

                row[
                    "cut_quantity"
                ] = max(
                    1,
                    int(
                        float(
                            row.get(
                                "cut_quantity",
                                row[
                                    "piece_count"
                                ]
                            )
                        )
                    )
                )

            except Exception:

                row[
                    "cut_quantity"
                ] = row[
                    "piece_count"
                ]

            # =========================================================
            # 🚫 KHÔNG CHIA PIECE > 16"
            # =========================================================

            # Không được:
            #
            # if fabric and width > 16:
            #     width /= 2
            #     area /= 2
            #     piece_count *= 2
            #
            # Jacket Back / Front có thể rộng >16".

            # =========================================================
            # POLYGON AREA
            # =========================================================

            try:

                polygon_area = float(
                    row.get(
                        "polygon_net_area",
                        0.0
                    )
                )

            except Exception:

                polygon_area = 0.0

            bbox_area = (
                row[
                    "bounding_box_length"
                ]
                *
                row[
                    "bounding_box_width"
                ]
            )

            # ---------------------------------------------------------
            # AI KHÔNG TRẢ AREA
            # ---------------------------------------------------------

            if (
                polygon_area <= 0.0
                and bbox_area > 0.0
            ):

                polygon_area = (
                    bbox_area
                    *
                    0.75
                )

            # ---------------------------------------------------------
            # AREA KHÔNG ĐƯỢC VƯỢT BBOX
            # ---------------------------------------------------------

            if (
                bbox_area > 0.0
                and polygon_area > bbox_area
            ):

                polygon_area = (
                    bbox_area
                    *
                    0.76
                )

            # ---------------------------------------------------------
            # KHÔNG AREA ÂM
            # ---------------------------------------------------------

            polygon_area = max(
                0.0,
                polygon_area
            )

            row[
                "polygon_net_area"
            ] = round(
                polygon_area,
                2
            )

            # =========================================================
            # OTHER SAFE FIELDS
            # =========================================================

            try:

                row[
                    "gross_consumption"
                ] = round(
                    float(
                        row.get(
                            "gross_consumption",
                            0.0
                        )
                    ),
                    4
                )

            except Exception:

                row[
                    "gross_consumption"
                ] = 0.0

            try:

                row[
                    "marker_efficiency"
                ] = str(
                    row.get(
                        "marker_efficiency",
                        "78.0%"
                    )
                ).strip()

            except Exception:

                row[
                    "marker_efficiency"
                ] = "78.0%"

            # =========================================================
            # 🔒 WIDTH MASTER
            #
            # USER COMMAND > active_width > fallback
            # =========================================================

            row[
                "fabric_width_inch"
            ] = round(
                float(
                    resolved_width
                ),
                2
            )

            # =========================================================
            # 🔒 SHRINK MASTER TRÊN TỪNG BOM ROW
            # =========================================================

            row[
                "warp_shrink_percent"
            ] = (
                round(
                    float(
                        resolved_warp_shrink
                    ),
                    4
                )
                if resolved_warp_shrink is not None
                else None
            )

            row[
                "weft_shrink_percent"
            ] = (
                round(
                    float(
                        resolved_weft_shrink
                    ),
                    4
                )
                if resolved_weft_shrink is not None
                else None
            )

    # =================================================================
    # 10. API COUNTER
    # =================================================================

    if (
        "api_calls_count"
        not in st.session_state
    ):

        st.session_state[
            "api_calls_count"
        ] = 0

    if (
        "tokens_consumed"
        not in st.session_state
    ):

        st.session_state[
            "tokens_consumed"
        ] = 0

    st.session_state[
        "api_calls_count"
    ] += 1

    st.session_state[
        "tokens_consumed"
    ] += (
        len(
            str(
                full_pdf_raw_text
            )
        )
        // 4
    )

    # =================================================================
    # 11. DEBUG MASTER PARAMETERS
    # =================================================================

    blueprint_worker[
        "_master_parameters"
    ] = {
        "size": resolved_size,
        "fabric_width_inch": round(
            float(
                resolved_width
            ),
            2
        ),
        "warp_shrink_percent": (
            round(
                float(
                    resolved_warp_shrink
                ),
                4
            )
            if resolved_warp_shrink is not None
            else None
        ),
        "weft_shrink_percent": (
            round(
                float(
                    resolved_weft_shrink
                ),
                4
            )
            if resolved_weft_shrink is not None
            else None
        ),
        "source": "USER_COMMAND_PRIORITY",
    }

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
    # 🟩 ĐOẠN 2 - VERSION V28.9
    # MASTER AI SCAN + PRODUCT TYPE + WIDTH/SHRINK + MATERIAL LOCK
    # =====================================================================

    if st.session_state.get("ai_processing", False):

        import re
        import pandas as pd
        import streamlit as st

        # =================================================================
        # 1. CURRENT QUERY - MASTER USER COMMAND
        # =================================================================

        current_query = str(
            st.session_state.get(
                "current_query",
                st.session_state.get(
                    "last_submitted_query",
                    st.session_state.get(
                        "user_query",
                        ""
                    )
                )
            )
        ).strip()

        # =================================================================
        # 2. ACTIVE PDF RECOVERY
        # =================================================================

        active_pdf = (
            st.session_state.get("pdf_bytes")
            or st.session_state.get("uploaded_file")
            or st.session_state.get("current_pdf")
            or st.session_state.get("pdf_data")
        )

        # =================================================================
        # 3. MASTER PARAMETER INITIALIZATION
        # =================================================================

        dynamic_width = 58.0
        target_size = "32"
        warp_shrinkage = 0.0
        weft_shrinkage = 0.0

        query_clean = (
            str(current_query)
            .replace(",", ".")
            .replace("％", "%")
            .replace("”", '"')
            .replace("″", '"')
            .lower()
        )

        query_clean = " ".join(
            query_clean.split()
        )

        # =================================================================
        # 4. WIDTH PARSER
        # =================================================================

        width_patterns = [

            r"\bkhổ\s*vải\s*[:=]?\s*"
            r"(\d+(?:\.\d+)?)",

            r"\bkhổ\s*[:=]?\s*"
            r"(\d+(?:\.\d+)?)",

            r"\bkhô\s*[:=]?\s*"
            r"(\d+(?:\.\d+)?)",

            r"\bkho\s*[:=]?\s*"
            r"(\d+(?:\.\d+)?)",

            r"\bfabric\s*width\s*[:=]?\s*"
            r"(\d+(?:\.\d+)?)",

            r"\bwidth\s*[:=]?\s*"
            r"(\d+(?:\.\d+)?)",
        ]

        for pattern in width_patterns:

            w_match = re.search(
                pattern,
                query_clean,
                re.IGNORECASE
            )

            if w_match:

                try:

                    parsed_width = float(
                        w_match.group(1)
                    )

                    if (
                        20.0
                        <= parsed_width
                        <= 100.0
                    ):

                        dynamic_width = (
                            parsed_width
                        )

                        break

                except Exception:
                    pass

        # =================================================================
        # 5. SIZE PARSER
        # =================================================================

        size_patterns = [

            r"\bsize\s*[:=]?\s*"
            r"([a-zA-Z0-9._-]+)",

            r"\bcỡ\s*[:=]?\s*"
            r"([a-zA-Z0-9._-]+)",

            r"\bco\s*size\s*[:=]?\s*"
            r"([a-zA-Z0-9._-]+)",
        ]

        for pattern in size_patterns:

            s_match = re.search(
                pattern,
                query_clean,
                re.IGNORECASE
            )

            if s_match:

                target_size = str(
                    s_match.group(1)
                ).upper().strip()

                if target_size:
                    break

        # =================================================================
        # 6. WARP SHRINKAGE
        # =================================================================

        warp_patterns = [

            r"\bco\s*dọc\s*[:=]?\s*"
            r"(\d+(?:\.\d+)?)\s*%?",

            r"\bco\s*rút\s*dọc\s*[:=]?\s*"
            r"(\d+(?:\.\d+)?)\s*%?",

            r"\bđộ\s*co\s*dọc\s*[:=]?\s*"
            r"(\d+(?:\.\d+)?)\s*%?",

            r"\bwarp\s*shrinkage\s*[:=]?\s*"
            r"(\d+(?:\.\d+)?)\s*%?",

            r"\bwarp\s*shrink\s*[:=]?\s*"
            r"(\d+(?:\.\d+)?)\s*%?",
        ]

        for pattern in warp_patterns:

            m = re.search(
                pattern,
                query_clean,
                re.IGNORECASE
            )

            if m:

                try:

                    value = float(
                        m.group(1)
                    )

                    if (
                        0.0
                        <= value
                        <= 15.0
                    ):

                        warp_shrinkage = (
                            value
                        )

                        break

                except Exception:
                    pass

        # =================================================================
        # 7. WEFT SHRINKAGE
        # =================================================================

        weft_patterns = [

            r"\bco\s*ngang\s*[:=]?\s*"
            r"(\d+(?:\.\d+)?)\s*%?",

            r"\bco\s*rút\s*ngang\s*[:=]?\s*"
            r"(\d+(?:\.\d+)?)\s*%?",

            r"\bđộ\s*co\s*ngang\s*[:=]?\s*"
            r"(\d+(?:\.\d+)?)\s*%?",

            r"\bweft\s*shrinkage\s*[:=]?\s*"
            r"(\d+(?:\.\d+)?)\s*%?",

            r"\bweft\s*shrink\s*[:=]?\s*"
            r"(\d+(?:\.\d+)?)\s*%?",
        ]

        for pattern in weft_patterns:

            m = re.search(
                pattern,
                query_clean,
                re.IGNORECASE
            )

            if m:

                try:

                    value = float(
                        m.group(1)
                    )

                    if (
                        0.0
                        <= value
                        <= 15.0
                    ):

                        weft_shrinkage = (
                            value
                        )

                        break

                except Exception:
                    pass

        # =================================================================
        # 8. MASTER SESSION COMMIT
        # =================================================================

        st.session_state[
            "current_active_width"
        ] = float(
            dynamic_width
        )

        st.session_state[
            "current_active_size"
        ] = str(
            target_size
        )

        st.session_state[
            "current_warp_shrinkage"
        ] = float(
            warp_shrinkage
        )

        st.session_state[
            "current_weft_shrinkage"
        ] = float(
            weft_shrinkage
        )

        # =================================================================
        # 9. DEBUG
        # =================================================================

        print(
            "[ĐOẠN 2 MASTER]"
            f" Query={current_query}"
            f" | Size={target_size}"
            f" | Width={dynamic_width}\""
            f" | Warp={warp_shrinkage}%"
            f" | Weft={weft_shrinkage}%"
        )

        # =================================================================
        # 10. ONLY CONTINUE WHEN PDF EXISTS
        # =================================================================

        if active_pdf is not None:

            with st.spinner(
                "🧠 AI Vision đang quét phôi rập Nguyên Liệu..."
            ):

                try:

                    # =====================================================
                    # 11. JSON SCHEMA
                    # =====================================================

                    raw_json_schema = {

                        "type": "OBJECT",

                        "properties": {

                            "detected_product_type": {
                                "type": "STRING"
                            },

                            "detected_base_size": {
                                "type": "STRING"
                            },

                            "product_type_confidence": {
                                "type": "NUMBER"
                            },

                            "bom_rows": {

                                "type": "ARRAY",

                                "items": {

                                    "type": "OBJECT",

                                    "properties": {

                                        "component_name": {
                                            "type": "STRING"
                                        },

                                        "material_class": {
                                            "type": "STRING",
                                            "enum": [
                                                "FABRIC",
                                                "LINING",
                                                "FUSING",
                                                "RIB",
                                                "CONTRAST",
                                                "PADDING"
                                            ]
                                        },

                                        "bounding_box_length": {
                                            "type": "NUMBER"
                                        },

                                        "bounding_box_width": {
                                            "type": "NUMBER"
                                        },

                                        "piece_shape": {
                                            "type": "STRING"
                                        },

                                        "piece_function": {
                                            "type": "STRING"
                                        },

                                        "fold_type": {
                                            "type": "STRING"
                                        },

                                        "material_zone": {
                                            "type": "STRING",
                                            "enum": [
                                                "SELF",
                                                "LINING",
                                                "FUSING",
                                                "RIB",
                                                "CONTRAST"
                                            ]
                                        },

                                        "grain_constraint": {
                                            "type": "STRING"
                                        },

                                        "packing_priority": {
                                            "type": "INTEGER"
                                        },

                                        "convex_fill_ratio": {
                                            "type": "NUMBER"
                                        },

                                        "seam_allowance": {
                                            "type": "STRING"
                                        },

                                        "mirror_piece": {
                                            "type": "BOOLEAN"
                                        },

                                        "is_left_right_pair": {
                                            "type": "BOOLEAN"
                                        },

                                        "requires_matching": {
                                            "type": "BOOLEAN"
                                        },

                                        "critical_alignment": {
                                            "type": "STRING"
                                        },

                                        "cut_quantity": {
                                            "type": "INTEGER"
                                        },

                                        "grain_direction": {
                                            "type": "STRING"
                                        },

                                        "rotation_allowed": {
                                            "type": "STRING"
                                        },

                                        "edge_curvature": {
                                            "type": "STRING"
                                        },

                                        "shape_complexity": {
                                            "type": "STRING"
                                        },

                                        "inference_source": {
                                            "type": "STRING"
                                        },

                                        "cad_reconstruction_score": {
                                            "type": "INTEGER"
                                        },

                                        "field_confidence": {

                                            "type": "OBJECT",

                                            "properties": {

                                                "dimensions": {
                                                    "type": "STRING"
                                                },

                                                "geometry_shape": {
                                                    "type": "STRING"
                                                },

                                                "grain_alignment": {
                                                    "type": "STRING"
                                                }
                                            },

                                            "required": [
                                                "dimensions",
                                                "geometry_shape",
                                                "grain_alignment"
                                            ]
                                        },

                                        "shape_parameters": {

                                            "type": "OBJECT",

                                            "properties": {

                                                "estimated_corner_points": {
                                                    "type": "INTEGER"
                                                },

                                                "dominant_axis": {
                                                    "type": "STRING"
                                                },

                                                "top_width_ratio": {
                                                    "type": "NUMBER"
                                                },

                                                "bottom_width_ratio": {
                                                    "type": "NUMBER"
                                                },

                                                "left_edge_profile": {
                                                    "type": "STRING"
                                                },

                                                "right_edge_profile": {
                                                    "type": "STRING"
                                                },

                                                "waist_curve_depth": {
                                                    "type": "NUMBER"
                                                },

                                                "hem_curve_depth": {
                                                    "type": "NUMBER"
                                                },

                                                "crotch_projection_ratio": {
                                                    "type": "NUMBER"
                                                }
                                            }
                                        }
                                    },

                                    "required": [
                                        "component_name",
                                        "material_class",
                                        "bounding_box_length",
                                        "bounding_box_width",
                                        "piece_shape",
                                        "piece_function",
                                        "fold_type",
                                        "material_zone",
                                        "packing_priority",
                                        "convex_fill_ratio",
                                        "mirror_piece",
                                        "cut_quantity"
                                    ]
                                }
                            }
                        },

                        "required": [
                            "detected_product_type",
                            "detected_base_size",
                            "bom_rows"
                        ]
                    }

                    # =====================================================
                    # 12. AI MASTER PROMPT
                    # =====================================================

                    prompt_agent_2 = f"""

You are a senior Industrial Garment IE,
CAD Pattern Engineering and Commercial Fabric
Consumption Intelligence.

Analyze the entire Techpack/PDF.

TARGET SIZE:
{target_size}

USER FABRIC WIDTH:
{dynamic_width:.2f} inches

USER WARP SHRINKAGE:
{warp_shrinkage:.2f}%

USER WEFT SHRINKAGE:
{weft_shrinkage:.2f}%


=========================================================
SECTION A - PRODUCT TYPE
=========================================================

Identify the ACTUAL garment product from the PDF.

Allowed:

JEAN_LONG
PANT_LONG
SHORT
JACKET
SHIRT
TSHIRT
POLO
DRESS
SKIRT
HOODIE
OTHER

Do NOT automatically classify every bottom as JEAN_LONG.

SHORT only when evidence shows shorts or short pants.

JEAN_LONG / PANT_LONG only for long pants,
jeans or full-length trousers.

JACKET when the PDF clearly shows jacket/outerwear
construction.


=========================================================
SECTION B - ACCESSORY EXCLUSION
=========================================================

NEVER create BOM pieces for:

BUTTON
ZIPPER
SLIDER
RIVET
THREAD
LABEL
CARE LABEL
SIZE LABEL
HANGTAG
POLYBAG
HARDWARE
PLASTIC ACCESSORY
METAL ACCESSORY
DRAW CORD
CORD END


=========================================================
SECTION C - MATERIAL CLASS
=========================================================

Allowed:

FABRIC
LINING
FUSING
RIB
CONTRAST
PADDING


=========================================================
ABSOLUTE RIB RULE
=========================================================

RIB is allowed ONLY when explicit evidence exists.

Examples:

RIB
RIB KNIT
RIB FABRIC
RIB COLLAR
RIB CUFF
RIB WAISTBAND
BO GÂN
BO RIB
KNIT RIB

A normal collar is FABRIC.

A normal cuff is FABRIC.

A normal waistband is FABRIC.

A normal shoulder is FABRIC.

A normal facing is FABRIC.

Do NOT invent RIB.


=========================================================
LINING RULE
=========================================================

LINING only when explicitly supported by the Techpack.

Examples:

LINING
BODY LINING
SLEEVE LINING
POCKET BAG
POCKET LINING
LINING PANEL


=========================================================
FUSING RULE
=========================================================

FUSING only when explicitly supported.

Examples:

FUSING
INTERLINING
INTERFACING
MEX
DỰNG
KEO


=========================================================
SINGLE PIECE GEOMETRY
=========================================================

bounding_box_width MUST represent ONE SINGLE
physical pattern piece.

NEVER combine left and right pieces.

NEVER output double-width for paired panels.


=========================================================
CUT QUANTITY
=========================================================

cut_quantity MUST represent actual physical quantity.

1 physical piece = 1

left + right pair = 2

front pair = 2

sleeve pair = 2

Do NOT multiply again because mirror_piece is true.


=========================================================
JACKET FABRIC RULE
=========================================================

For JACKET:

FRONT BODY
BACK BODY
SLEEVE
COLLAR
CUFF
FRONT FACING
BACK FACING
POCKET
POCKET FLAP
HOOD

remain FABRIC unless Techpack explicitly proves
another material.


=========================================================
GEOMETRY
=========================================================

Extract:

bounding_box_length
bounding_box_width
piece_shape
piece_function
fold_type
grain_direction
rotation_allowed
edge_curvature
shape_complexity

Never output zero dimensions for valid pattern pieces.


=========================================================
FINAL VALIDATION
=========================================================

Before returning JSON:

1. Confirm product type from PDF.
2. Confirm material class from PDF.
3. Confirm RIB has explicit evidence.
4. Confirm cut_quantity.
5. Confirm width is for ONE physical piece.
6. Exclude accessories.
7. Do not invent RIB.
8. Do not invent LINING.
9. Do not invent FUSING.
10. Do not default product type to JEAN_LONG.

Return ONLY valid BOM pattern pieces.
"""

                    # =====================================================
                    # 13. EXECUTE AI ENGINE
                    # =====================================================

                    bom_data = execute_final_gerber_pure_scan(

                        pdf_bytes=active_pdf,

                        current_query=current_query,

                        active_width=dynamic_width,

                        target_size_cmd=target_size,

                        raw_json_schema=raw_json_schema,

                        prompt_agent_2=prompt_agent_2
                    )

                    # =====================================================
                    # 14. VALIDATE AI RESULT
                    # =====================================================

                    if (
                        bom_data
                        and isinstance(
                            bom_data,
                            dict
                        )
                    ):

                        if not isinstance(
                            bom_data.get(
                                "bom_rows"
                            ),
                            list
                        ):

                            bom_data[
                                "bom_rows"
                            ] = []

                        # =================================================
                        # MASTER PARAMETERS
                        # =================================================

                        bom_data[
                            "fabric_width_inch"
                        ] = float(
                            dynamic_width
                        )

                        bom_data[
                            "usable_width_inch"
                        ] = float(
                            dynamic_width
                        )

                        bom_data[
                            "warp_shrinkage_percent"
                        ] = float(
                            warp_shrinkage
                        )

                        bom_data[
                            "weft_shrinkage_percent"
                        ] = float(
                            weft_shrinkage
                        )

                        bom_data[
                            "calculated_on_size"
                        ] = str(
                            target_size
                        )

                        bom_data[
                            "detected_base_size"
                        ] = str(
                            target_size
                        )

                        # =================================================
                        # 15. READ PDF TEXT FOR MATERIAL VALIDATION
                        # =================================================

                        raw_pdf_text_for_validation = ""

                        try:

                            import fitz

                            pdf_check = (
                                active_pdf.getvalue()
                                if hasattr(
                                    active_pdf,
                                    "getvalue"
                                )
                                else active_pdf
                            )

                            with fitz.open(
                                stream=pdf_check,
                                filetype="pdf"
                            ) as validation_doc:

                                for pg in validation_doc:

                                    raw_pdf_text_for_validation += (
                                        " "
                                        + pg.get_text(
                                            "text"
                                        )
                                    ).lower()

                        except Exception as pdf_error:

                            print(
                                "[ĐOẠN 2 PDF TEXT WARNING]",
                                pdf_error
                            )

                            raw_pdf_text_for_validation = ""

                        # =================================================
                        # 16. REAL RIB KEYWORDS
                        # =================================================

                        explicit_rib_keywords = [

                            "rib knit",
                            "rib fabric",
                            "rib collar",
                            "rib cuff",
                            "rib waistband",
                            "rib",
                            "bo gân",
                            "bo gan",
                            "bo rib"
                        ]

                        pdf_has_real_rib = any(
                            keyword
                            in raw_pdf_text_for_validation
                            for keyword
                            in explicit_rib_keywords
                        )

                        # =================================================
                        # 17. MATERIAL LOCK
                        # =================================================

                        accessory_words = [

                            "BUTTON",
                            "ZIPPER",
                            "SLIDER",
                            "RIVET",
                            "THREAD",
                            "LABEL",
                            "CARE LABEL",
                            "SIZE LABEL",
                            "HANGTAG",
                            "POLYBAG",
                            "HARDWARE",
                            "DRAW CORD",
                            "CORD END"
                        ]

                        fusing_words = [

                            "FUSING",
                            "INTERLINING",
                            "INTERFACING",
                            "MEX",
                            "DỰNG",
                            "DUNG",
                            "KEO"
                        ]

                        lining_words = [

                            "LINING",
                            "POCKET BAG",
                            "POCKET LINING",
                            "LOT TUI",
                            "LÓT TÚI",
                            "SLEEVE LINING",
                            "BODY LINING"
                        ]

                        for row in bom_data[
                            "bom_rows"
                        ]:

                            if not isinstance(
                                row,
                                dict
                            ):
                                continue

                            comp_name = str(
                                row.get(
                                    "component_name",
                                    ""
                                )
                            ).strip()

                            comp_upper = (
                                comp_name.upper()
                            )

                            comp_lower = (
                                comp_name.lower()
                            )

                            current_material = str(
                                row.get(
                                    "material_class",
                                    "FABRIC"
                                )
                            ).upper().strip()

                            # =============================================
                            # ACCESSORY
                            # =============================================

                            if any(
                                word in comp_upper
                                for word in accessory_words
                            ):

                                row[
                                    "_ignore_for_bom"
                                ] = True

                                continue

                            # =============================================
                            # RIB
                            # =============================================

                            explicit_component_rib = any(
                                key in comp_lower
                                for key in [
                                    "rib",
                                    "bo gân",
                                    "bo gan",
                                    "rib knit"
                                ]
                            )

                            if (
                                current_material
                                == "RIB"
                            ):

                                if not (
                                    pdf_has_real_rib
                                    and explicit_component_rib
                                ):

                                    current_material = (
                                        "FABRIC"
                                    )

                            # =============================================
                            # FUSING
                            # =============================================

                            if any(
                                key in comp_upper
                                for key in fusing_words
                            ):

                                current_material = (
                                    "FUSING"
                                )

                            # =============================================
                            # LINING
                            # =============================================

                            if any(
                                key in comp_upper
                                for key in lining_words
                            ):

                                current_material = (
                                    "LINING"
                                )

                            # =============================================
                            # EXPLICIT RIB
                            # =============================================

                            if (
                                explicit_component_rib
                                and pdf_has_real_rib
                            ):

                                current_material = (
                                    "RIB"
                                )

                            # =============================================
                            # VALID MATERIAL
                            # =============================================

                            if current_material not in [
                                "FABRIC",
                                "LINING",
                                "FUSING",
                                "RIB",
                                "CONTRAST",
                                "PADDING"
                            ]:

                                current_material = (
                                    "FABRIC"
                                )

                            row[
                                "material_class"
                            ] = current_material

                            # =============================================
                            # MATERIAL ZONE
                            # =============================================

                            if current_material == "FABRIC":

                                row[
                                    "material_zone"
                                ] = "SELF"

                            elif current_material == "LINING":

                                row[
                                    "material_zone"
                                ] = "LINING"

                            elif current_material == "FUSING":

                                row[
                                    "material_zone"
                                ] = "FUSING"

                            elif current_material == "RIB":

                                row[
                                    "material_zone"
                                ] = "RIB"

                            elif current_material == "CONTRAST":

                                row[
                                    "material_zone"
                                ] = "CONTRAST"

                            elif current_material == "PADDING":

                                row[
                                    "material_zone"
                                ] = "SELF"

                            # =============================================
                            # CUT QUANTITY
                            # =============================================

                            try:

                                row[
                                    "cut_quantity"
                                ] = max(
                                    1,
                                    int(
                                        float(
                                            row.get(
                                                "cut_quantity",
                                                1
                                            )
                                        )
                                    )
                                )

                            except Exception:

                                row[
                                    "cut_quantity"
                                ] = 1

                            # =============================================
                            # LENGTH
                            # =============================================

                            try:

                                row[
                                    "bounding_box_length"
                                ] = round(
                                    float(
                                        row.get(
                                            "bounding_box_length",
                                            0
                                        )
                                    ),
                                    2
                                )

                            except Exception:

                                row[
                                    "bounding_box_length"
                                ] = 0.0

                            # =============================================
                            # WIDTH
                            # =============================================

                            try:

                                row[
                                    "bounding_box_width"
                                ] = round(
                                    float(
                                        row.get(
                                            "bounding_box_width",
                                            0
                                        )
                                    ),
                                    2
                                )

                            except Exception:

                                row[
                                    "bounding_box_width"
                                ] = 0.0

                            # =============================================
                            # MASTER WIDTH
                            # =============================================

                            row[
                                "fabric_width_inch"
                            ] = float(
                                dynamic_width
                            )

                        # =================================================
                        # 18. ENSURE BOM DATA IS SAVED
                        # =================================================

                        st.session_state[
                            "bom_data"
                        ] = bom_data

                        # =================================================
                        # 19. MASTER SESSION
                        # =================================================

                        st.session_state[
                            "current_active_width"
                        ] = float(
                            dynamic_width
                        )

                        st.session_state[
                            "current_active_size"
                        ] = str(
                            target_size
                        )

                        st.session_state[
                            "current_warp_shrinkage"
                        ] = float(
                            warp_shrinkage
                        )

                        st.session_state[
                            "current_weft_shrinkage"
                        ] = float(
                            weft_shrinkage
                        )

                        # =================================================
                        # 20. IMPORTANT
                        #
                        # KHÔNG TẠO active_calculated_df_bom Ở ĐOẠN 2
                        #
                        # ĐỂ 5.2B1 → 5.2B2 → 5.2C
                        # TIẾP TỤC TÍNH DM
                        # =================================================

                        st.session_state.pop(
                            "active_calculated_df_bom",
                            None
                        )

                        # =================================================
                        # 21. CHO PHÉP ĐOẠN 5.2C CHẠY
                        # =================================================

                        st.session_state[
                            "pipeline_auto_run_executed"
                        ] = False

                        # =================================================
                        # 22. STOP AI SCAN
                        # =================================================

                        st.session_state[
                            "ai_processing"
                        ] = False

                        # =================================================
                        # 23. RERUN
                        # =================================================

                        st.rerun()

                    else:

                        st.error(
                            "❌ AI không trả về bom_data hợp lệ."
                        )

                        st.session_state[
                            "ai_processing"
                        ] = False

                        st.session_state[
                            "pipeline_auto_run_executed"
                        ] = False

                # =========================================================
                # ERROR HANDLER
                # =========================================================

                except Exception as e:

                    st.error(
                        "❌ Lỗi xử lý luồng AI Execute "
                        f"(Đoạn 2): {str(e)}"
                    )

                    print(
                        "[ĐOẠN 2 ERROR]",
                        repr(e)
                    )

                    st.session_state[
                        "ai_processing"
                    ] = False

                    st.session_state[
                        "pipeline_auto_run_executed"
                    ] = False
# =====================================================================
# 🧠 MASTER PARAMETER CONTROLLER V27.5
# 🔒 CHAT COMMAND = NGUỒN SỰ THẬT TUYỆT ĐỐI
# 🔒 KHỔ VẢI / SIZE / CO DỌC / CO NGANG KHÔNG ĐƯỢC CACHE AI GHI ĐÈ
# =====================================================================

import re
import streamlit as st


def initialize_and_sync_parameters():
    """
    MASTER CONTROLLER

    Ưu tiên tuyệt đối:
        CHAT COMMAND
            ↓
        current_active_width
        current_active_size
        current_warp_shrinkage
        current_weft_shrinkage
            ↓
        bom_data
            ↓
        IE ENGINE 5.2B1/B2

    Không cho giá trị cũ 58" từ bom_data/cache AI ghi đè
    giá trị mới người dùng nhập trong Chat.
    """

    # ================================================================
    # 0. KIỂM TRA NGUỒN BOM
    # ================================================================
    if not (
        st.session_state.get("bom_data")
        or st.session_state.get("accumulated_bom_rows")
    ):
        return None, None

    bom_source = st.session_state.get("bom_data", {})

    if not isinstance(bom_source, dict):
        bom_source = {}

    # ================================================================
    # 1. GIỮ NGUYÊN BỘ NÃO VIRTUAL PIECES
    # ================================================================
    ai_expert_decision = bom_source.get(
        "ai_expert_decision",
        {}
    )

    if not isinstance(ai_expert_decision, dict):
        ai_expert_decision = {}

    virtual_pieces_layer = ai_expert_decision.get(
        "virtual_pieces_layer",
        {}
    )

    if not isinstance(virtual_pieces_layer, dict):
        virtual_pieces_layer = {}

    # ================================================================
    # 2. LẤY CHAT COMMAND
    # ================================================================
    user_query_text = str(
        st.session_state.get(
            "last_submitted_query",
            ""
        )
    ).strip()

    # ================================================================
    # 3. LẤY GIÁ TRỊ HIỆN TẠI
    #    CHỈ DÙNG LÀM FALLBACK
    # ================================================================
    try:
        fabric_width = float(
            st.session_state.get(
                "current_active_width",
                bom_source.get(
                    "fabric_width_inch",
                    58.0
                )
            )
        )
    except:
        fabric_width = 58.0

    try:
        warp_shrinkage = float(
            st.session_state.get(
                "current_warp_shrinkage",
                bom_source.get(
                    "warp_shrinkage_percent",
                    0.0
                )
            )
        )
    except:
        warp_shrinkage = 0.0

    try:
        weft_shrinkage = float(
            st.session_state.get(
                "current_weft_shrinkage",
                bom_source.get(
                    "weft_shrinkage_percent",
                    0.0
                )
            )
        )
    except:
        weft_shrinkage = 0.0

    detected_size = st.session_state.get(
        "current_active_size",
        bom_source.get(
            "detected_base_size",
            bom_source.get(
                "calculated_on_size",
                "32"
            )
        )
    )

    target_size = str(
        detected_size
    ).strip().upper()

    if not target_size:
        target_size = "32"

    # ================================================================
    # 4. CHAT PARSER - MASTER
    #
    # Hỗ trợ:
    #   khổ 62
    #   khổ vải 62
    #   khổ=62
    #   khổ vải=62
    #   khổ 56
    #
    # Và tránh bắt nhầm số của co rút / size.
    # ================================================================
    if user_query_text:

        query = " ".join(
            user_query_text.lower().split()
        )

        # ------------------------------------------------------------
        # KHỔ VẢI
        # ------------------------------------------------------------
        width_match = re.search(
            r"\bkhổ(?:\s+vải)?\s*[:=]?\s*(\d+(?:\.\d+)?)\b",
            query,
            re.IGNORECASE
        )

        if width_match:

            parsed_width = float(
                width_match.group(1)
            )

            # Khổ vải kỹ thuật hợp lệ
            if 20.0 <= parsed_width <= 100.0:

                fabric_width = parsed_width

                print(
                    f"[MASTER CHAT SYNC] "
                    f"KHỔ CHAT = {fabric_width:.2f}\""
                )

        # ------------------------------------------------------------
        # CO DỌC
        # ------------------------------------------------------------
        warp_match = re.search(
            r"\b(?:co\s*rút\s*dọc|co\s*dọc|độ\s*co\s*dọc)"
            r"\s*[:=]?\s*(\d+(?:\.\d+)?)",
            query,
            re.IGNORECASE
        )

        if warp_match:

            parsed_warp = float(
                warp_match.group(1)
            )

            if 0.0 <= parsed_warp <= 15.0:
                warp_shrinkage = parsed_warp

        # ------------------------------------------------------------
        # CO NGANG
        # ------------------------------------------------------------
        weft_match = re.search(
            r"\b(?:co\s*rút\s*ngang|co\s*ngang|độ\s*co\s*ngang)"
            r"\s*[:=]?\s*(\d+(?:\.\d+)?)",
            query,
            re.IGNORECASE
        )

        if weft_match:

            parsed_weft = float(
                weft_match.group(1)
            )

            if 0.0 <= parsed_weft <= 15.0:
                weft_shrinkage = parsed_weft

        # ------------------------------------------------------------
        # SIZE
        # Hỗ trợ:
        # size 30
        # size M
        # cỡ 32
        # cỡ XL
        # ------------------------------------------------------------
        size_match = re.search(
            r"\b(?:size|cỡ)\s*[:=]?\s*([a-zA-Z0-9]+)\b",
            query,
            re.IGNORECASE
        )

        if size_match:

            target_size = str(
                size_match.group(1)
            ).strip().upper()

    # ================================================================
    # 5. 🔒 MASTER COMMIT VÀO SESSION STATE
    # ================================================================
    st.session_state[
        "current_active_width"
    ] = float(fabric_width)

    st.session_state[
        "current_active_size"
    ] = str(target_size)

    st.session_state[
        "current_warp_shrinkage"
    ] = float(warp_shrinkage)

    st.session_state[
        "current_weft_shrinkage"
    ] = float(weft_shrinkage)

    # ================================================================
    # 6. 🔒 MASTER COMMIT VÀO BOM DATA
    # ================================================================
    bom_source[
        "fabric_width_inch"
    ] = float(fabric_width)

    bom_source[
        "usable_width_inch"
    ] = float(fabric_width)

    bom_source[
        "warp_shrinkage_percent"
    ] = float(warp_shrinkage)

    bom_source[
        "weft_shrinkage_percent"
    ] = float(weft_shrinkage)

    bom_source[
        "calculated_on_size"
    ] = str(target_size)

    bom_source[
        "detected_base_size"
    ] = str(target_size)

    # ================================================================
    # 7. KHÓA LỚP AI KHÔNG ĐƯỢC GHI ĐÈ THÔNG SỐ CHAT
    # ================================================================
    ai_expert_decision[
        "virtual_pieces_layer"
    ] = virtual_pieces_layer

    ai_expert_decision[
        "detected_base_size"
    ] = str(target_size)

    ai_expert_decision[
        "fabric_width"
    ] = float(fabric_width)

    ai_expert_decision[
        "fabric_width_inch"
    ] = float(fabric_width)

    ai_expert_decision[
        "warp_shrinkage_percent"
    ] = float(warp_shrinkage)

    ai_expert_decision[
        "weft_shrinkage_percent"
    ] = float(weft_shrinkage)

    bom_source[
        "ai_expert_decision"
    ] = ai_expert_decision

    # ================================================================
    # 8. GHI BOM DATA CUỐI CÙNG
    # ================================================================
    st.session_state[
        "bom_data"
    ] = bom_source

    # ================================================================
    # 9. DEBUG MASTER
    # ================================================================
    print(
        "\n"
        "============================================================\n"
        "[MASTER PARAMETER SYNC]\n"
        f"CHAT        = {user_query_text}\n"
        f"SIZE        = {target_size}\n"
        f"WIDTH       = {fabric_width:.2f}\"\n"
        f"WARP SHRINK  = {warp_shrinkage:.2f}%\n"
        f"WEFT SHRINK  = {weft_shrinkage:.2f}%\n"
        "============================================================\n"
    )

    return bom_source, user_query_text
# =====================================================================
# 🧠 CUTTING INSTRUCTION ENGINE (VERSION V26.0)
# 🔒 STRICT PIECE QUANTITY RECOVERY
# =====================================================================
import re
import streamlit as st


def extract_cutting_instructions_from_pdf(
    component_name,
    raw_pdf_text,
    current_inferred_pcs=1.0
):
    """
    Quét Callout kỹ thuật trong PDF để xác định số lượng mảnh cắt thực tế.

    NGUYÊN TẮC:
    1. Giữ nguyên số lượng AI đã xác định nếu PDF không có Callout rõ ràng.
    2. Nếu PDF có CUT / QTY / PCS / X2 / PAIR thì dùng dữ liệu PDF.
    3. Không tự động ép mọi PANEL / FRONT / BACK / SLEEVE thành 2.
    4. Không nhân layer_multiplier lần nữa ở các tầng sau.
    5. final_validated_pcs là số lượng mảnh vật lý cuối cùng.
    """

    # =================================================================
    # 1. SAFE BASE QUANTITY
    # =================================================================
    try:
        base_pcs = int(float(current_inferred_pcs))
    except (TypeError, ValueError):
        base_pcs = 1

    base_pcs = max(base_pcs, 1)

    final_validated_pcs = base_pcs

    layer_multiplier = 1
    is_paired = False

    calc_log = (
        f"AI Base Quantity: giữ nguyên {base_pcs} mảnh "
        f"nếu PDF không có Callout xác nhận khác."
    )

    # =================================================================
    # 2. KHÔNG CÓ PDF TEXT → GIỮ NGUYÊN AI QUANTITY
    # =================================================================
    if not raw_pdf_text:
        return {
            "layer_multiplier": 1,
            "final_validated_pcs": final_validated_pcs,
            "is_paired": False,
            "calc_log": (
                "CAD Fallback: Không có PDF text. "
                f"Giữ nguyên AI quantity = {final_validated_pcs}."
            )
        }

    # =================================================================
    # 3. CHUẨN HÓA TEXT
    # =================================================================
    text_clean = " ".join(
        str(raw_pdf_text).lower().split()
    )

    comp_clean = " ".join(
        str(component_name).lower().split()
    ).strip()

    if not comp_clean:
        return {
            "layer_multiplier": 1,
            "final_validated_pcs": final_validated_pcs,
            "is_paired": False,
            "calc_log": (
                "Không có Component Name. "
                f"Giữ AI quantity = {final_validated_pcs}."
            )
        }

    # =================================================================
    # 4. TÌM COMPONENT TRONG PDF
    # =================================================================
    match_positions = [
        m.start()
        for m in re.finditer(
            re.escape(comp_clean),
            text_clean,
            re.IGNORECASE
        )
    ]

    if not match_positions:
        return {
            "layer_multiplier": 1,
            "final_validated_pcs": final_validated_pcs,
            "is_paired": False,
            "calc_log": (
                f"Không tìm thấy Callout cho [{component_name}]. "
                f"Giữ AI quantity = {final_validated_pcs}."
            )
        }

    # =================================================================
    # 5. QUÉT TỪNG VÙNG QUANH COMPONENT
    # =================================================================
    best_detected_qty = None
    best_priority = 999
    best_window = ""

    for match_index in match_positions:

        window_start = max(
            0,
            match_index - 100
        )

        window_end = min(
            len(text_clean),
            match_index + 180
        )

        scan_window = text_clean[
            window_start:window_end
        ]

        # =============================================================
        # PRIORITY 1
        # Explicit CUT / QTY / PCS
        # =============================================================
        explicit_patterns = [
            r"\bcut\s*(?:qty\s*)?(?:x\s*)?[:=]?\s*(\d+)\b",
            r"\bqty\s*[:=]?\s*(\d+)\b",
            r"\bquantity\s*[:=]?\s*(\d+)\b",
            r"\b(\d+)\s*pcs\b",
            r"\b(\d+)\s*pieces\b",
            r"\bcut\s+(\d+)\b",
            r"\bcắt\s+(\d+)\b",
            r"\bsố\s*lượng\s*[:=]?\s*(\d+)\b",
            r"\bsl\s*[:=]?\s*(\d+)\b",
        ]

        detected_qty = None
        detected_priority = 999

        for pattern in explicit_patterns:

            m = re.search(
                pattern,
                scan_window,
                re.IGNORECASE
            )

            if m:

                try:
                    qty = int(m.group(1))
                except (TypeError, ValueError):
                    continue

                if qty >= 1:

                    detected_qty = qty
                    detected_priority = 1
                    break

        # =============================================================
        # PRIORITY 2
        # X2 / X3 / X4
        # =============================================================
        if detected_qty is None:

            x_match = re.search(
                r"(?:\bx\s*|\*\s*)([2-9])\b",
                scan_window,
                re.IGNORECASE
            )

            if x_match:

                try:
                    qty = int(x_match.group(1))
                except (TypeError, ValueError):
                    qty = None

                if qty and qty >= 2:

                    detected_qty = qty
                    detected_priority = 2

        # =============================================================
        # PRIORITY 3
        # PAIR / 1 PAIR / DOUBLE
        # =============================================================
        pair_detected = bool(
            re.search(
                r"\b(pair|1\s*pair|double|mirror|"
                r"đối\s*xứng|cặp|đôi)\b",
                scan_window,
                re.IGNORECASE
            )
        )

        if pair_detected:

            is_paired = True

            if detected_qty is None:

                # Chỉ suy ra 2 khi PDF thực sự nói PAIR.
                detected_qty = 2
                detected_priority = 3

        # =============================================================
        # CHỌN KẾT QUẢ CÓ ĐỘ ƯU TIÊN CAO NHẤT
        # =============================================================
        if (
            detected_qty is not None
            and detected_priority < best_priority
        ):
            best_detected_qty = detected_qty
            best_priority = detected_priority
            best_window = scan_window

    # =================================================================
    # 6. COMMIT QUANTITY TỪ PDF
    # =================================================================
    if best_detected_qty is not None:

        final_validated_pcs = max(
            int(best_detected_qty),
            1
        )

        if best_priority == 1:

            calc_log = (
                f"PDF Callout xác nhận CUT/QTY = "
                f"{final_validated_pcs} mảnh. "
                f"AI Base = {base_pcs}."
            )

        elif best_priority == 2:

            calc_log = (
                f"PDF Callout xác nhận X{final_validated_pcs}. "
                f"AI Base = {base_pcs}."
            )

        else:

            calc_log = (
                "PDF Callout xác nhận PAIR/MIRROR. "
                f"Khôi phục = {final_validated_pcs} mảnh."
            )

    else:

        # =============================================================
        # KHÔNG CÓ CALLOUT → TUYỆT ĐỐI KHÔNG ÉP VỀ 2
        # =============================================================
        final_validated_pcs = base_pcs

        calc_log = (
            f"Không có Callout quantity rõ ràng. "
            f"Giữ nguyên AI Base = {base_pcs}."
        )

    # =================================================================
    # 7. 🔒 MASTER GUARD
    # =================================================================
    final_validated_pcs = max(
        int(final_validated_pcs),
        1
    )

    # Không cho layer multiplier nhân lại quantity.
    layer_multiplier = 1

    # =================================================================
    # 8. RETURN MASTER QUANTITY
    # =================================================================
    return {
        "layer_multiplier": 1,

        # SỐ LƯỢNG MẢNH VẬT LÝ CUỐI CÙNG
        "final_validated_pcs": int(
            final_validated_pcs
        ),

        "is_paired": bool(is_paired),

        "calc_log": calc_log,

        # Debug để các tầng sau biết nguồn quantity
        "base_pcs": int(base_pcs),

        "quantity_source": (
            "PDF_CALLOUT"
            if best_detected_qty is not None
            else "AI_BASE"
        ),

        "detected_pdf_quantity": (
            int(best_detected_qty)
            if best_detected_qty is not None
            else None
        )
    }



# =====================================================================
# 🟩 ĐOẠN 2 - DATA CLEANING & MASTER PARAMETER READ
# VERSION V27.0 - MASTER LOCK / NO OVERRIDE
# =====================================================================

import re
import pandas as pd


# =====================================================================
# 1. LẤY BOM ROWS
# =====================================================================

rows = ctx.get("bom_rows", [])

if not rows:
    rows = st.session_state.get("processed_display_rows", [])


# =====================================================================
# 2. KIỂM TRA DỮ LIỆU BOM
# =====================================================================

_has_rows = (
    isinstance(rows, list) and len(rows) > 0
) or (
    isinstance(rows, pd.DataFrame) and not rows.empty
)


if _has_rows:

    # =================================================================
    # 3. TẠO DATAFRAME SẠCH
    # =================================================================

    df_bom = (
        pd.DataFrame(rows)
        if isinstance(rows, list)
        else rows.copy()
    )

    # Loại bỏ column trùng tên
    df_bom = df_bom.loc[
        :,
        ~df_bom.columns.duplicated()
    ].copy()


    # =================================================================
    # 4. NHẬN DIỆN PRODUCT TYPE THỰC TẾ
    #    CHỐNG AI BẮT NHẦM JEAN_LONG
    # =================================================================

    ai_decision = st.session_state.get(
        "bom_data",
        {}
    ).get(
        "ai_expert_decision",
        {}
    )

    if not isinstance(ai_decision, dict):
        ai_decision = {}


    style_code_upper = str(
        ai_decision.get(
            "style_code",
            ""
        )
    ).upper().strip()


    material_spec_upper = str(
        ai_decision.get(
            "material_spec",
            ""
        )
    ).upper().strip()


    p_type_friendly = str(
        ai_decision.get(
            "product_type_friendly",
            "JEAN_LONG"
        )
    ).upper().strip()


    # =================================================================
    # 5. CHUỖI TỔNG HỢP PHỤC VỤ QUÉT PRODUCT TYPE
    # =================================================================

    combined_search_text = (
        f"{style_code_upper} | "
        f"{material_spec_upper} | "
        f"{p_type_friendly}"
    )


    # =================================================================
    # 6. LẤY PRODUCT TYPE TỪ CONTEXT
    # =================================================================

    prod = str(
        ctx.get(
            "detected_product_type",
            ctx.get(
                "product_segmented",
                "JEAN_LONG"
            )
        )
    ).upper().strip()


    # =================================================================
    # 7. ƯU TIÊN NHẬN DIỆN PRODUCT TYPE
    # =================================================================

    if "DRESS" in combined_search_text:

        prod = "DRESS"

    elif "SKIRT" in combined_search_text:

        prod = "SKIRT"

    elif "SHORT" in combined_search_text:

        prod = "SHORT"

    elif (
        "JACKET" in combined_search_text
        or "COAT" in combined_search_text
    ):

        prod = "JACKET"

    elif "SHIRT" in combined_search_text:

        prod = "SHIRT"


    # =================================================================
    # 8. ĐỒNG BỘ PRODUCT TYPE
    # =================================================================

    ctx["detected_product_type"] = prod
    ctx["product_segmented"] = prod


    # =================================================================
    # 9. FABRIC PATTERN
    # =================================================================

    fabric_pattern_raw = str(
        ctx.get(
            "fabric_pattern",
            "SOLID"
        )
    ).upper()


    # =================================================================
    # 10. XÁC ĐỊNH CỘT MATERIAL
    # =================================================================

    m_col = next(
        (
            c
            for c in [
                "Material Class",
                "material_class"
            ]
            if c in df_bom.columns
        ),
        "material_class"
    )


    # Nếu column chưa tồn tại thì tạo
    if m_col not in df_bom.columns:
        df_bom[m_col] = ""


    # =================================================================
    # 11. XÁC ĐỊNH CỘT PIECE COUNT
    # =================================================================

    pcs_col = next(
        (
            c
            for c in [
                "Số lượng rập",
                "piece_count"
            ]
            if c in df_bom.columns
        ),
        "piece_count"
    )


    # Nếu column chưa tồn tại thì tạo
    if pcs_col not in df_bom.columns:
        df_bom[pcs_col] = 1


    # =================================================================
    # 12. XÁC ĐỊNH BOUNDING BOX LENGTH
    # =================================================================

    orig_l_col = next(
        (
            c
            for c in [
                "bounding_box_length",
                "Dài (L-inch)"
            ]
            if c in df_bom.columns
        ),
        "bounding_box_length"
    )


    if orig_l_col not in df_bom.columns:
        df_bom[orig_l_col] = 0.0


    # =================================================================
    # 13. XÁC ĐỊNH BOUNDING BOX WIDTH
    # =================================================================

    orig_w_col = next(
        (
            c
            for c in [
                "bounding_box_width",
                "Rộng (W-inch)"
            ]
            if c in df_bom.columns
        ),
        "bounding_box_width"
    )


    if orig_w_col not in df_bom.columns:
        df_bom[orig_w_col] = 0.0


    # =================================================================
    # 14. CLEAN GEOMETRY DIMENSIONS
    # =================================================================

    df_bom[orig_l_col] = pd.to_numeric(
        df_bom[orig_l_col],
        errors="coerce"
    ).fillna(0.0)


    df_bom[orig_w_col] = pd.to_numeric(
        df_bom[orig_w_col],
        errors="coerce"
    ).fillna(0.0)


    # =================================================================
    # 15. GIỮ LẠI GROSS CONSUMPTION GỐC
    # =================================================================

    target_orig_gross_col = next(
        (
            c
            for c in [
                "Gross Consumption",
                "gross_consumption",
                "allocated_gross"
            ]
            if c in df_bom.columns
        ),
        None
    )


    if target_orig_gross_col:

        df_bom["original_raw_gross"] = pd.to_numeric(
            df_bom[target_orig_gross_col],
            errors="coerce"
        ).fillna(0.0)

    else:

        df_bom["original_raw_gross"] = 0.0


    # =================================================================
    # 16. USER EDIT BUFFER
    # =================================================================

    if "user_edited_materials" not in st.session_state:
        st.session_state["user_edited_materials"] = {}


    if "user_edited_pieces" not in st.session_state:
        st.session_state["user_edited_pieces"] = {}


    # =================================================================
    # 17. APPLY USER MATERIAL EDIT
    # =================================================================

    for idx, row in df_bom.iterrows():

        if idx in st.session_state["user_edited_materials"]:

            df_bom.at[
                idx,
                m_col
            ] = st.session_state[
                "user_edited_materials"
            ][idx]


    # =================================================================
    # 18. CLEAN PIECE COUNT
    # =================================================================

    def clean_precise_piece_count(row):

        comp_name = str(
            row.get(
                "component_name",
                row.get(
                    "Component Name",
                    ""
                )
            )
        ).upper().strip()


        pcs_raw_str = str(
            row.get(
                pcs_col,
                "1"
            )
        )


        pcs_extracted = re.search(
            r"(\d+(?:\.\d+)?)",
            pcs_raw_str
        )


        if pcs_extracted:

            try:
                pcs_val = float(
                    pcs_extracted.group(1)
                )

            except (TypeError, ValueError):

                pcs_val = 1.0

        else:

            pcs_val = 1.0


        if pcs_val <= 0:
            pcs_val = 1.0


        return pcs_val


    # =================================================================
    # 19. CREATE NUMERIC PIECE COUNT
    # =================================================================

    clean_piece_values = []

    for idx, row in df_bom.iterrows():

        if idx in st.session_state[
            "user_edited_pieces"
        ]:

            try:

                edited_value = float(
                    st.session_state[
                        "user_edited_pieces"
                    ][idx]
                )

                if edited_value > 0:
                    clean_piece_values.append(
                        edited_value
                    )
                else:
                    clean_piece_values.append(1.0)

            except (TypeError, ValueError):

                clean_piece_values.append(
                    clean_precise_piece_count(row)
                )

        else:

            clean_piece_values.append(
                clean_precise_piece_count(row)
            )


    df_bom["pcs_numeric"] = clean_piece_values


    df_bom[pcs_col] = pd.to_numeric(
        df_bom["pcs_numeric"],
        errors="coerce"
    ).fillna(1.0)


    # =====================================================================
    # 🚨 20. MASTER PARAMETER READ
    #
    # ĐOẠN 2 KHÔNG TỰ TÍNH PARAMETER.
    # ĐOẠN 1 LÀ MASTER DUY NHẤT.
    # =====================================================================

    master_params = st.session_state.get(
        "ie_master_params",
        {}
    )


    if not isinstance(master_params, dict):
        master_params = {}


    # =================================================================
    # 21. FABRIC WIDTH
    # =================================================================

    fabric_width = master_params.get(
        "fabric_width",
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


    try:

        fabric_width = float(
            fabric_width
        )

    except (TypeError, ValueError):

        fabric_width = 58.0


    if fabric_width <= 0:
        fabric_width = 58.0


    # =================================================================
    # 22. WARP / VERTICAL SHRINKAGE
    # =================================================================

    warp_shrink = master_params.get(
        "warp_shrinkage",
        st.session_state.get(
            "current_warp_shrinkage",
            st.session_state.get(
                "warp_shrinkage",
                st.session_state.get(
                    "shrinkage_vertical",
                    ctx.get(
                        "warp_shrinkage",
                        0.0
                    )
                )
            )
        )
    )


    try:

        warp_shrink = float(
            warp_shrink
        )

    except (TypeError, ValueError):

        warp_shrink = 0.0


    # =================================================================
    # 23. WEFT / HORIZONTAL SHRINKAGE
    # =================================================================

    weft_shrink = master_params.get(
        "weft_shrinkage",
        st.session_state.get(
            "current_weft_shrinkage",
            st.session_state.get(
                "weft_shrinkage",
                st.session_state.get(
                    "shrinkage_horizontal",
                    ctx.get(
                        "weft_shrinkage",
                        0.0
                    )
                )
            )
        )
    )


    try:

        weft_shrink = float(
            weft_shrink
        )

    except (TypeError, ValueError):

        weft_shrink = 0.0


    # =================================================================
    # 24. ĐỒNG BỘ MASTER → SESSION ALIAS
    #
    # Các tầng cũ vẫn có thể đọc các tên biến cũ.
    # =================================================================

    st.session_state[
        "fabric_width_inch"
    ] = fabric_width


    st.session_state[
        "current_active_width"
    ] = fabric_width


    st.session_state[
        "warp_shrinkage"
    ] = warp_shrink


    st.session_state[
        "weft_shrinkage"
    ] = weft_shrink


    st.session_state[
        "current_warp_shrinkage"
    ] = warp_shrink


    st.session_state[
        "current_weft_shrinkage"
    ] = weft_shrink


    st.session_state[
        "shrinkage_vertical"
    ] = warp_shrink


    st.session_state[
        "shrinkage_horizontal"
    ] = weft_shrink


    # =================================================================
    # 25. MASTER → BOM CONTEXT
    # =================================================================

    ctx[
        "fabric_width_inch"
    ] = fabric_width


    ctx[
        "warp_shrinkage_percent"
    ] = warp_shrink


    ctx[
        "weft_shrinkage_percent"
    ] = weft_shrink


    ctx[
        "warp_shrinkage"
    ] = warp_shrink


    ctx[
        "weft_shrinkage"
    ] = weft_shrink


    # =================================================================
    # 26. LƯU MASTER PARAMETER SNAPSHOT VÀO BOM
    # =================================================================

    ctx[
        "ie_master_params"
    ] = {
        "size": master_params.get(
            "size",
            st.session_state.get(
                "current_active_size",
                ctx.get(
                    "calculated_on_size",
                    "32"
                )
            )
        ),
        "fabric_width": fabric_width,
        "fusing_width": master_params.get(
            "fusing_width",
            st.session_state.get(
                "fusing_width_inch",
                ctx.get(
                    "fusing_width_inch",
                    59.0
                )
            )
        ),
        "lining_width": master_params.get(
            "lining_width",
            st.session_state.get(
                "lining_width_inch",
                ctx.get(
                    "lining_width_inch",
                    57.0
                )
            )
        ),
        "warp_shrinkage": warp_shrink,
        "weft_shrinkage": weft_shrink,
    }


    # =================================================================
    # 27. LƯU BOM DATA CUỐI CÙNG
    # =================================================================

    st.session_state[
        "bom_data"
    ] = ctx


    # =================================================================
    # 28. MASTER SYNC STATUS
    # =================================================================

    st.session_state[
        "ie_parameter_sync_complete"
    ] = True

    # =====================================================================
    # 🟩 ĐOẠN 3.1 - AI PRODUCT CLASSIFIER
    # VERSION V28.1 - COMPACT / CAD SAFE
    # =====================================================================

    import re

    COMPANY_DENSITY_PRIOR = {
        "SHIRT": 0.82,
        "JEAN_LONG": 0.795,
        "SHORT": 0.83,
        "JACKET": 0.68,
        "VEST": 0.82,
        "TOPS_KNIT": 0.78,
        "SKIRT": 0.82,
        "DRESS_FLARE": 0.72,
    }

    if not isinstance(st.session_state.get("bom_data"), dict):
        st.session_state["bom_data"] = {}

    ctx = st.session_state["bom_data"]

    if not isinstance(ctx.get("ai_expert_decision"), dict):
        ctx["ai_expert_decision"] = {}

    ai_decision = ctx["ai_expert_decision"]

    comp_col = next(
        (
            c for c in [
                "Component Name",
                "component_name",
                "Component_Name"
            ]
            if c in df_bom.columns
        ),
        None
    )

    all_components_text = (
        " ".join(
            df_bom[comp_col]
            .fillna("")
            .astype(str)
            .str.upper()
        )
        if comp_col
        else ""
    )

    style_code = str(
        ai_decision.get("style_code", "")
    ).upper().strip()

    material_spec = str(
        ai_decision.get("material_spec", "")
    ).upper().strip()

    prod_master = str(
        ctx.get(
            "detected_product_type",
            ctx.get(
                "product_segmented",
                prod if "prod" in locals() else ""
            )
        )
    ).upper().strip()

    combined_text = (
        f"{style_code} "
        f"{material_spec} "
        f"{prod_master} "
        f"{all_components_text}"
    ).upper()

    product_category = None

    if re.search(
        r"\b(SHIRT|SƠ MI|SO MI|BLOUSE)\b",
        combined_text
    ):
        product_category = "SHIRT"

    elif re.search(
        r"\b(SKIRT|CHÂN VÁY|CHAN VAY)\b",
        combined_text
    ):
        product_category = "SKIRT"

    elif re.search(
        r"\b(DRESS|ĐẦM|DAM|FLARE DRESS|SHIFT DRESS|MAXI DRESS)\b",
        combined_text
    ):
        product_category = "DRESS_FLARE"

    elif re.search(
        r"\b(JACKET|COAT|BLAZER|ÁO KHOÁC|AO KHOAC|BOMBER|PARKA)\b",
        combined_text
    ):
        product_category = "JACKET"

    elif re.search(
        r"\b(SHORT|SHORTS|QUẦN SHORT|QUAN SHORT)\b",
        combined_text
    ):
        product_category = "SHORT"

    elif re.search(
        r"\b(TROUSER|TROUSERS|PANTS|PANT|JEAN|JEANS|QUẦN|QUAN|WAISTBAND|FLY|CẠP|CAP|POCKET FACING)\b",
        all_components_text
    ):
        product_category = "JEAN_LONG"

    elif re.search(
        r"\b(VEST|WAISTCOAT)\b",
        combined_text
    ):
        product_category = "VEST"

    elif re.search(
        r"\b(POLO|T-SHIRT|TSHIRT|TEE|KNIT TOP|HOODIE|SWEATSHIRT)\b",
        combined_text
    ):
        product_category = "TOPS_KNIT"

    if product_category is None:

        master_map = {
            "SHIRT": "SHIRT",
            "SKIRT": "SKIRT",
            "SHORT": "SHORT",
            "JACKET": "JACKET",
            "COAT": "JACKET",
            "VEST": "VEST",
            "TOPS_KNIT": "TOPS_KNIT",
            "POLO": "TOPS_KNIT",
            "T-SHIRT": "TOPS_KNIT",
            "TSHIRT": "TOPS_KNIT",
            "DRESS": "DRESS_FLARE",
            "DRESS_FLARE": "DRESS_FLARE",
            "JEAN": "JEAN_LONG",
            "JEANS": "JEAN_LONG",
            "PANT": "JEAN_LONG",
            "PANTS": "JEAN_LONG",
            "TROUSER": "JEAN_LONG",
            "JEAN_LONG": "JEAN_LONG",
        }

        product_category = master_map.get(
            prod_master,
            "JEAN_LONG"
        )

    density_prior = COMPANY_DENSITY_PRIOR.get(
        product_category,
        COMPANY_DENSITY_PRIOR["JEAN_LONG"]
    )

    friendly_map = {
        "SHIRT": "SHIRT (Áo sơ mi)",
        "SKIRT": "SKIRT (Chân váy)",
        "SHORT": "SHORT (Quần short)",
        "JACKET": "JACKET (Áo khoác Jacket)",
        "VEST": "VEST (Áo Vest/Blazer)",
        "TOPS_KNIT": "TOPS_KNIT (Áo thun/Polo)",
        "DRESS_FLARE": "DRESS_FLARE (Đầm)",
        "JEAN_LONG": "JEAN_LONG (Quần dài Jeans/Pants)",
    }

    ai_product_type = friendly_map.get(
        product_category,
        friendly_map["JEAN_LONG"]
    )

    virtual_pieces = ai_decision.get(
        "virtual_pieces_layer",
        {}
    )

    if not isinstance(virtual_pieces, dict):
        virtual_pieces = {}

    ai_decision["product_category"] = product_category
    ai_decision["product_type_friendly"] = ai_product_type
    ai_decision["estimated_density_prior"] = density_prior
    ai_decision["virtual_pieces_layer"] = virtual_pieces

    ctx["detected_product_type"] = product_category
    ctx["product_segmented"] = product_category
    ctx["estimated_density_prior"] = density_prior

    st.session_state["current_product_category"] = product_category
    st.session_state["current_product_type_friendly"] = ai_product_type
    st.session_state["current_estimated_density_prior"] = density_prior

    st.session_state["bom_data"] = ctx
         # =====================================================================
    # 🟩 ĐOẠN 4 - MASTER GEOMETRY & STRICT MATERIAL CLASSIFIER
    # VERSION V28.1 - COMPACT / CAD SAFE
    # =====================================================================

    import pandas as pd
    import numpy as np

    # ---------------------------------------------------------------------
    # 1. MASTER CONTEXT
    # ---------------------------------------------------------------------

    if not isinstance(st.session_state.get("bom_data"), dict):
        st.session_state["bom_data"] = {}

    ctx = st.session_state["bom_data"]

    if not isinstance(ctx.get("ai_expert_decision"), dict):
        ctx["ai_expert_decision"] = {}

    comp_col_check = next(
        (
            c for c in [
                "Component Name",
                "component_name",
                "Component_Name"
            ]
            if c in df_bom.columns
        ),
        "component_name"
    )

    m_col_check = next(
        (
            c for c in [
                "Material Class",
                "material_class"
            ]
            if c in df_bom.columns
        ),
        "material_class"
    )

    user_edited_materials = st.session_state.get(
        "user_edited_materials",
        {}
    )

    user_edited_pieces = st.session_state.get(
        "user_edited_pieces",
        {}
    )

    virtual_pieces_layer = {}


    # ---------------------------------------------------------------------
    # 2. SAFE NUMBER CONVERTER
    # ---------------------------------------------------------------------

    def safe_float(value, default=0.0):
        try:
            value = pd.to_numeric(value, errors="coerce")
            return default if pd.isna(value) else float(value)
        except Exception:
            return default


    # ---------------------------------------------------------------------
    # 3. MATERIAL CLASSIFIER + GEOMETRY
    # ---------------------------------------------------------------------

    for idx, row in df_bom.iterrows():

        idx_str = str(idx).strip()

        comp_name_raw = str(
            row.get(
                comp_col_check,
                row.get("component_name", "")
            )
        ).strip()

        comp_name_upper = comp_name_raw.upper()

        mat_str = str(
            row.get(m_col_check, "")
        ).upper().strip()


        # ---------------------------------------------------------------
        # MATERIAL CLASS
        # ---------------------------------------------------------------

        if idx in user_edited_materials:
            p_class = str(
                user_edited_materials[idx]
            ).upper().strip()

        elif idx_str in user_edited_materials:
            p_class = str(
                user_edited_materials[idx_str]
            ).upper().strip()

        elif any(
            k in comp_name_upper or k in mat_str
            for k in [
                "THREAD",
                "CHỈ",
                "BUTTON",
                "NÚT",
                "ZIP",
                "ZIPPER",
                "ACCESSORY"
            ]
        ):
            p_class = "ACCESSORY"

        elif any(
            k in comp_name_upper or k in mat_str
            for k in [
                "FUSING",
                "MEC",
                "MẾCH",
                "KEO",
                "INTERLINING",
                "DỰNG",
                "WAISTBAND FUSING"
            ]
        ):
            p_class = "FUSING"

        elif any(
            k in comp_name_upper or k in mat_str
            for k in [
                "RIB",
                "BO GÂN",
                "BO CO",
                "BO TAY",
                "BO LAI",
                "BO LƯNG",
                "BO LUNG",
                "BO TĂM"
            ]
        ):
            p_class = "RIB"

        elif any(
            k in comp_name_upper or k in mat_str
            for k in [
                "LINING",
                "LÓT",
                "POCKET BAG",
                "POCKETING",
                "VẢI LÓT",
                "POCKET FACING",
                "POCKETING FABRIC"
            ]
        ):
            p_class = "LINING"

        elif any(
            k in comp_name_upper or k in mat_str
            for k in [
                "CONTRAST",
                "PHỐI",
                "VẢI PHỐI",
                "MATCHING"
            ]
        ):
            p_class = "CONTRAST"

        elif any(
            k in comp_name_upper or k in mat_str
            for k in [
                "PADDING",
                "GÒN",
                "WADDING",
                "BÔNG LOT"
            ]
        ):
            p_class = "PADDING"

        else:
            p_class = "FABRIC"


        # ---------------------------------------------------------------
        # GEOMETRY INPUT
        # ---------------------------------------------------------------

        l_orig = safe_float(
            row.get(
                "bounding_box_length",
                row.get(
                    "Dài (L-inch)",
                    row.get(
                        "Chiều dài rập (inch)",
                        0.0
                    )
                )
            )
        )

        w_orig = safe_float(
            row.get(
                "bounding_box_width",
                row.get(
                    "Rộng (W-inch)",
                    row.get(
                        "Chiều rộng rập (inch)",
                        0.0
                    )
                )
            )
        )

        net_area_real = safe_float(
            row.get(
                "polygon_net_area",
                0.0
            )
        )

        if l_orig <= 0 or w_orig <= 0:
            continue


        # ---------------------------------------------------------------
        # NORMALIZE L / W
        # ---------------------------------------------------------------

        if w_orig > l_orig:
            l_orig, w_orig = w_orig, l_orig

        bbox_area = l_orig * w_orig


        # ---------------------------------------------------------------
        # NET AREA CONTROL
        # ---------------------------------------------------------------

        if net_area_real <= 0:
            net_area_real = bbox_area * 0.74

        elif net_area_real > bbox_area:
            net_area_real = bbox_area * 0.85


        # ---------------------------------------------------------------
        # CAD OBB EFFICIENCY CONTROL
        # ---------------------------------------------------------------

        if net_area_real > 0 and bbox_area > 0:

            current_factor = (
                net_area_real / bbox_area
            )

            aspect_ratio = (
                l_orig / max(w_orig, 0.001)
            )

            log_aspect = np.log1p(
                aspect_ratio
            )

            target_obb_eff = max(
                0.6400,
                min(
                    0.9200,
                    0.88
                    - (0.05 * log_aspect)
                    + (0.15 * current_factor)
                )
            )

            if (
                current_factor < target_obb_eff
                and target_obb_eff > 0
            ):

                optimized_area = (
                    net_area_real /
                    target_obb_eff
                )

                w_new = np.sqrt(
                    optimized_area /
                    max(aspect_ratio, 0.001)
                )

                l_new = (
                    w_new *
                    aspect_ratio
                )

                # Chỉ cập nhật nếu geometry hợp lệ
                if l_new > 0 and w_new > 0:
                    l_orig = l_new
                    w_orig = w_new


        # ---------------------------------------------------------------
        # PIECE COUNT
        # ---------------------------------------------------------------

        raw_pcs = safe_float(
            row.get(
                "pcs_numeric",
                row.get(
                    "Số lượng rập",
                    1.0
                )
            ),
            1.0
        )

        raw_pcs = max(
            raw_pcs,
            1.0
        )

        if idx in user_edited_pieces:
            final_pcs = safe_float(
                user_edited_pieces[idx],
                raw_pcs
            )

        elif idx_str in user_edited_pieces:
            final_pcs = safe_float(
                user_edited_pieces[idx_str],
                raw_pcs
            )

        else:
            final_pcs = raw_pcs

        final_pcs = max(
            final_pcs,
            1.0
        )


        # ---------------------------------------------------------------
        # SAVE VIRTUAL CAD PIECE
        # ---------------------------------------------------------------

        virtual_pieces_layer[idx_str] = {
            "material_class": p_class,
            "production_l": round(l_orig, 2),
            "production_w": round(w_orig, 2),
            "production_net_area": round(
                net_area_real,
                2
            ),
            "polygon_net_area": round(
                net_area_real,
                2
            ),
            "active_user_pieces": int(
                final_pcs
            ),
            "component_name": comp_name_raw
        }


    # ---------------------------------------------------------------------
    # 4. WRITE BACK TO MASTER DATAFRAME
    # ---------------------------------------------------------------------

    for idx_str, vp in virtual_pieces_layer.items():

        target_idx = None

        if idx_str in df_bom.index:
            target_idx = idx_str

        else:
            try:
                idx_int = int(idx_str)

                if idx_int in df_bom.index:
                    target_idx = idx_int

            except Exception:
                pass

        if target_idx is None:
            continue

        df_bom.at[
            target_idx,
            "Chiều dài rập (inch)"
        ] = vp["production_l"]

        df_bom.at[
            target_idx,
            "Chiều rộng rập (inch)"
        ] = vp["production_w"]

        df_bom.at[
            target_idx,
            "polygon_net_area"
        ] = vp["production_net_area"]

        df_bom.at[
            target_idx,
            "Material Class"
        ] = vp["material_class"]


    # ---------------------------------------------------------------------
    # 5. MASTER OUTPUT
    # ---------------------------------------------------------------------

    ctx["ai_expert_decision"][
        "virtual_pieces_layer"
    ] = virtual_pieces_layer

    st.session_state["bom_data"] = ctx
        # =====================================================================
    # 🟩 ĐOẠN 5.1 - PIECE NORMALIZE PIPELINE
    # VERSION V28.6 - STRICT USER SYNC / CAD SAFE
    # =====================================================================

    import pandas as pd

    # ---------------------------------------------------------------------
    # 1. MASTER WIDTH PARAMETERS
    # ---------------------------------------------------------------------

    current_fabric_width = float(
        st.session_state.get(
            "current_active_width",
            st.session_state.get(
                "fabric_width_inch",
                58.0
            )
        )
    )

    fusing_width = float(
        st.session_state.get(
            "fusing_width_inch",
            st.session_state.get(
                "fusing_width",
                59.0
            )
        )
    )

    lining_width = float(
        st.session_state.get(
            "lining_width_inch",
            st.session_state.get(
                "lining_width",
                57.0
            )
        )
    )


    # ---------------------------------------------------------------------
    # 2. COLUMN RESOLVER
    # ---------------------------------------------------------------------

    l_col = next(
        (
            c for c in [
                "Chiều dài rập (inch)",
                "bounding_box_length"
            ]
            if c in df_bom.columns
        ),
        None
    )

    w_col = next(
        (
            c for c in [
                "Chiều rộng rập (inch)",
                "bounding_box_width"
            ]
            if c in df_bom.columns
        ),
        None
    )

    pcs_col = next(
        (
            c for c in [
                "pcs_numeric",
                "Số lượng rập"
            ]
            if c in df_bom.columns
        ),
        "Số lượng rập"
    )


    # ---------------------------------------------------------------------
    # 3. USER EDIT BUFFER
    # ---------------------------------------------------------------------

    user_edited_materials = st.session_state.get(
        "user_edited_materials",
        {}
    )

    user_edited_pieces = st.session_state.get(
        "user_edited_pieces",
        {}
    )

    raw_unpaired_pieces = []
    list_lengths = []
    list_widths = []


    # ---------------------------------------------------------------------
    # 4. SAFE NUMBER CONVERTER
    # ---------------------------------------------------------------------

    def safe_piece_float(value, default=0.0):

        try:
            value = pd.to_numeric(
                value,
                errors="coerce"
            )

            if pd.isna(value):
                return default

            return float(value)

        except Exception:
            return default


    # ---------------------------------------------------------------------
    # 5. NORMALIZE EVERY CAD PIECE
    # ---------------------------------------------------------------------

    for idx, r in df_bom.iterrows():

        idx_str = str(idx).strip()

        # ---------------------------------------------------------------
        # VIRTUAL PIECE
        # ---------------------------------------------------------------

        v_piece = virtual_pieces_layer.get(
            idx_str,
            {}
        )

        if not isinstance(v_piece, dict):
            v_piece = {}

        virtual_pieces_layer[idx_str] = v_piece


        # ---------------------------------------------------------------
        # GEOMETRY
        # ---------------------------------------------------------------

        p_len = safe_piece_float(
            v_piece.get(
                "production_l",
                r.get(
                    l_col,
                    0.0
                ) if l_col else 0.0
            )
        )

        p_wid = safe_piece_float(
            v_piece.get(
                "production_w",
                r.get(
                    w_col,
                    0.0
                ) if w_col else 0.0
            )
        )

        net_area = safe_piece_float(
            v_piece.get(
                "polygon_net_area",
                r.get(
                    "polygon_net_area",
                    0.0
                )
            )
        )


        # ---------------------------------------------------------------
        # MATERIAL CLASS - USER OVERRIDE FIRST
        # ---------------------------------------------------------------

        if idx in user_edited_materials:

            p_class_check = str(
                user_edited_materials[idx]
            ).upper().strip()

        elif idx_str in user_edited_materials:

            p_class_check = str(
                user_edited_materials[idx_str]
            ).upper().strip()

        else:

            p_class_check = str(
                v_piece.get(
                    "material_class",
                    r.get(
                        "Material Class",
                        "FABRIC"
                    )
                )
            ).upper().strip()

        if not p_class_check:
            p_class_check = "FABRIC"

        v_piece["material_class"] = p_class_check


        # ---------------------------------------------------------------
        # NET AREA FALLBACK
        # ---------------------------------------------------------------

        if (
            net_area <= 0.0
            and p_len > 0.0
            and p_wid > 0.0
        ):
            net_area = p_len * p_wid


        # ---------------------------------------------------------------
        # PIECE COUNT
        # ---------------------------------------------------------------

        raw_pcs = safe_piece_float(
            v_piece.get(
                "active_user_pieces",
                r.get(
                    pcs_col,
                    1.0
                ) if pcs_col else 1.0
            ),
            1.0
        )

        raw_pcs = max(
            raw_pcs,
            1.0
        )


        # ---------------------------------------------------------------
        # USER PIECE OVERRIDE
        # ---------------------------------------------------------------

        if idx in user_edited_pieces:

            pcs = safe_piece_float(
                user_edited_pieces[idx],
                raw_pcs
            )

        elif idx_str in user_edited_pieces:

            pcs = safe_piece_float(
                user_edited_pieces[idx_str],
                raw_pcs
            )

        else:

            pcs = raw_pcs

        pcs = max(
            pcs,
            1.0
        )


        # ---------------------------------------------------------------
        # WRITE PIECE COUNT BACK
        # ---------------------------------------------------------------

        df_bom.at[
            idx,
            pcs_col
        ] = int(round(pcs))

        v_piece["active_user_pieces"] = int(
            round(pcs)
        )


        # ---------------------------------------------------------------
        # WRITE GEOMETRY
        # ---------------------------------------------------------------

        list_lengths.append(
            round(p_len, 2)
            if p_len > 0
            else 0.0
        )

        list_widths.append(
            round(p_wid, 2)
            if p_wid > 0
            else 0.0
        )

        df_bom.at[
            idx,
            "polygon_net_area"
        ] = round(
            net_area,
            2
        )

        v_piece["polygon_net_area"] = round(
            net_area,
            2
        )


        # ---------------------------------------------------------------
        # CREATE UNPAIRED PIECES FOR NESTING
        # ---------------------------------------------------------------

        if (
            p_class_check in [
                "FABRIC",
                "FUSING",
                "LINING",
                "RIB",
                "CONTRAST",
                "PADDING"
            ]
            and p_len > 0.0
            and p_wid > 0.0
        ):

            loop_pcs = max(
                1,
                int(round(pcs))
            )

            for _ in range(loop_pcs):

                raw_unpaired_pieces.append({
                    "idx": idx_str,
                    "l": p_len,
                    "w": p_wid,
                    "area": net_area,
                    "material_class": p_class_check,
                    "priority": 3
                })


    # ---------------------------------------------------------------------
    # 6. SORT PIECES FOR NESTING
    # ---------------------------------------------------------------------

    raw_unpaired_pieces.sort(
        key=lambda x: (
            x.get(
                "priority",
                3
            ),
            -x.get(
                "area",
                0.0
            )
        )
    )


    # ---------------------------------------------------------------------
    # 7. WRITE NORMALIZED GEOMETRY BACK
    # ---------------------------------------------------------------------

    df_bom[
        "Chiều dài rập (inch)"
    ] = list_lengths

    df_bom[
        "Chiều rộng rập (inch)"
    ] = list_widths


    # ---------------------------------------------------------------------
    # 8. MASTER SYNC
    # ---------------------------------------------------------------------

    ctx[
        "ai_expert_decision"
    ][
        "virtual_pieces_layer"
    ] = virtual_pieces_layer

    ctx[
        "raw_unpaired_pieces"
    ] = raw_unpaired_pieces

    ctx[
        "fabric_width_inch"
    ] = current_fabric_width

    ctx[
        "fusing_width_inch"
    ] = fusing_width

    ctx[
        "lining_width_inch"
    ] = lining_width

    st.session_state[
        "bom_data"
    ] = ctx


   
# =====================================================================
# 🟩 ĐOẠN 5.2A
# VERSION V28.9 - MASTER PRODUCT TYPE / MARKER EFFICIENCY ROUTER
# 🔒 KHÔNG FALLBACK UNKNOWN -> JEAN_LONG
# 🔒 ĐỒNG BỘ TRỰC TIẾP AI PRODUCT TYPE TỪ ĐOẠN 2
# =====================================================================

import re
import pandas as pd
import streamlit as st


# =====================================================================
# 1. KHỞI TẠO BOM DATA
# =====================================================================

if "bom_data" not in st.session_state or not isinstance(
    st.session_state["bom_data"],
    dict
):
    st.session_state["bom_data"] = {}

ctx = st.session_state["bom_data"]

if not isinstance(ctx, dict):
    ctx = {}
    st.session_state["bom_data"] = ctx


# =====================================================================
# 2. LẤY AI EXPERT DECISION
# =====================================================================

ai_decision = ctx.get(
    "ai_expert_decision",
    {}
)

if not isinstance(ai_decision, dict):
    ai_decision = {}


# =====================================================================
# 3. MASTER CONFIG MATRIX
# =====================================================================

CONFIG_MATRIX = {

    "OVERALL": [
        0.71,
        "OVERALLS (Quần yếm/Quần bảo hộ)"
    ],

    "COVERALL": [
        0.71,
        "OVERALLS (Quần yếm/Quần bảo hộ)"
    ],

    "BIB": [
        0.71,
        "OVERALLS (Quần yếm/Quần bảo hộ)"
    ],

    "JUMPSUIT": [
        0.70,
        "JUMPSUIT (Đồ liền thân)"
    ],

    "DUNGAREE": [
        0.71,
        "DUNGAREE (Quần yếm)"
    ],

    "DRESS": [
        0.75,
        "DRESS (Đầm)"
    ],

    "SKIRT": [
        0.66,
        "SKIRT (Chân váy)"
    ],

    "SHORT": [
        0.68,
        "SHORT (Quần short)"
    ],

    "JEAN": [
        0.75,
        "JEAN (Quần Jeans/Denim)"
    ],

    "JEAN_LONG": [
        0.78,
        "JEAN_LONG (Quần Jeans dài chuẩn)"
    ],

    "KHAKI": [
        0.60,
        "KHAKI (Quần Khaki)"
    ],

    "TROUSER": [
        0.71,
        "TROUSER (Quần tây công sở)"
    ],

    "PANT": [
        0.72,
        "PANT (Quần dài)"
    ],

    "JACKET": [
        0.60,
        "JACKET (Áo khoác)"
    ],

    "COAT": [
        0.60,
        "COAT (Áo măng tô/Áo choàng)"
    ],

    "BLAZER": [
        0.65,
        "BLAZER (Áo Vest/Blazer)"
    ],

    "SUIT": [
        0.65,
        "SUIT (Bộ Comple/Suit)"
    ],

    "SHIRT": [
        0.78,
        "SHIRT (Áo sơ mi)"
    ],

    "BLOUSE": [
        0.78,
        "BLOUSE (Áo kiểu)"
    ],

    "POLO": [
        0.76,
        "POLO (Áo thun cổ bẻ)"
    ],

    "TEE": [
        0.76,
        "TEE/TSHIRT (Áo thun)"
    ],

    "TSHIRT": [
        0.76,
        "TEE/TSHIRT (Áo thun)"
    ],

    "TANK": [
        0.74,
        "TANK (Áo ba lỗ)"
    ],

    # -------------------------------------------------------------
    # UNKNOWN KHÔNG ĐƯỢC ÉP THÀNH JEAN_LONG
    # -------------------------------------------------------------

    "UNKNOWN": [
        0.74,
        "UNKNOWN (Chưa xác định chắc chắn)"
    ]
}


# =====================================================================
# 4. HÀM NORMALIZE PRODUCT TYPE
# =====================================================================

def normalize_router_product_type(raw_type):

    s = str(raw_type or "").upper().strip()

    s = re.sub(r"[_\-]+", " ", s)

    s = re.sub(r"\s+", " ", s)

    # -------------------------------------------------------------
    # SHORT
    # -------------------------------------------------------------

    if any(k in s for k in [
        "SHORT",
        "SHORTS",
        "BERMUDA"
    ]):
        return "SHORT"

    # -------------------------------------------------------------
    # JUMPSUIT / OVERALL
    # -------------------------------------------------------------

    if "JUMPSUIT" in s:
        return "JUMPSUIT"

    if "DUNGAREE" in s:
        return "DUNGAREE"

    if "COVERALL" in s:
        return "COVERALL"

    if "OVERALL" in s:
        return "OVERALL"

    if "BIB" in s:
        return "BIB"

    # -------------------------------------------------------------
    # DRESS / SKIRT
    # -------------------------------------------------------------

    if "DRESS" in s:
        return "DRESS"

    if "SKIRT" in s:
        return "SKIRT"

    # -------------------------------------------------------------
    # SHIRT
    # -------------------------------------------------------------

    if any(k in s for k in [
        "SHIRT",
        "DENIM SHIRT",
        "WORK SHIRT",
        "BUTTON SHIRT",
        "BUTTON DOWN"
    ]):
        return "SHIRT"

    if "BLOUSE" in s:
        return "BLOUSE"

    if "POLO" in s:
        return "POLO"

    if any(k in s for k in [
        "TSHIRT",
        "T SHIRT",
        "TEE"
    ]):
        return "TSHIRT"

    if "TANK" in s:
        return "TANK"

    # -------------------------------------------------------------
    # JACKET
    # -------------------------------------------------------------

    if any(k in s for k in [
        "JACKET",
        "TRUCKER",
        "DENIM JACKET"
    ]):
        return "JACKET"

    if "COAT" in s:
        return "COAT"

    if "BLAZER" in s:
        return "BLAZER"

    if "SUIT" in s:
        return "SUIT"

    # -------------------------------------------------------------
    # JEAN LONG
    # -------------------------------------------------------------

    if any(k in s for k in [
        "JEAN LONG",
        "LONG JEAN",
        "LONG JEANS",
        "JEANS LONG",
        "FULL LENGTH JEANS"
    ]):
        return "JEAN_LONG"

    # -------------------------------------------------------------
    # JEAN
    # -------------------------------------------------------------

    if any(k in s for k in [
        "JEAN PANT",
        "JEANS PANT",
        "DENIM PANT",
        "DENIM JEAN"
    ]):
        return "JEAN"

    # -------------------------------------------------------------
    # TROUSER
    # -------------------------------------------------------------

    if any(k in s for k in [
        "TROUSER",
        "TROUSERS",
        "DRESS PANT",
        "DRESS PANTS"
    ]):
        return "TROUSER"

    # -------------------------------------------------------------
    # KHAKI
    # -------------------------------------------------------------

    if "KHAKI" in s:
        return "KHAKI"

    # -------------------------------------------------------------
    # PANT
    # -------------------------------------------------------------

    if any(k in s for k in [
        "PANT",
        "PANTS",
        "LONG PANT",
        "LONG PANTS"
    ]):
        return "PANT"

    # -------------------------------------------------------------
    # UNKNOWN
    # -------------------------------------------------------------

    return "UNKNOWN"


# =====================================================================
# 5. LẤY PRODUCT TYPE TỪ AI
# =====================================================================

raw_ai_type = ai_decision.get(
    "ai_product_type_raw",
    ctx.get(
        "ai_product_type_raw",
        ctx.get(
            "detected_product_type",
            ""
        )
    )
)


# =====================================================================
# 6. NORMALIZE
# =====================================================================

ie_detected_type = normalize_router_product_type(
    raw_ai_type
)


# =====================================================================
# 7. 🚨 MASTER GUARD
# =====================================================================
# Nếu AI đã nhận diện SHIRT thì tuyệt đối không được biến thành
# JEAN_LONG chỉ vì material là DENIM.
# =====================================================================

if ie_detected_type == "UNKNOWN":

    # Thử lấy product type thứ hai nếu có
    secondary_type = normalize_router_product_type(
        ai_decision.get(
            "detected_product_type",
            ""
        )
    )

    if secondary_type != "UNKNOWN":
        ie_detected_type = secondary_type


# =====================================================================
# 8. KHÓA KHÔNG CHO JEAN / DENIM MATERIAL ĐÈ PRODUCT TYPE
# =====================================================================

material_hint = str(
    ctx.get(
        "material_spec",
        ctx.get(
            "fabric_description",
            ""
        )
    )
).upper()


if ie_detected_type in [
    "SHIRT",
    "BLOUSE",
    "POLO",
    "TSHIRT",
    "TANK",
    "JACKET",
    "COAT",
    "BLAZER"
]:

    # Giữ nguyên loại áo.
    # Không được chuyển thành JEAN_LONG chỉ vì material có DENIM/JEAN.

    pass


# =====================================================================
# 9. LẤY MARKER EFFICIENCY
# =====================================================================

if ie_detected_type not in CONFIG_MATRIX:

    ie_detected_type = "UNKNOWN"


dynamic_marker_efficiency = float(
    CONFIG_MATRIX[ie_detected_type][0]
)


friendly_product_type = CONFIG_MATRIX[
    ie_detected_type
][1]


# =====================================================================
# 10. NAP / ONE-WAY
# =====================================================================

is_nap_mode = bool(
    st.session_state.get(
        "is_nap_fabric",
        False
    )
)

is_one_way_mode = bool(
    st.session_state.get(
        "is_one_way_fabric",
        False
    )
)


# ONE-WAY ưu tiên cao hơn NAP
if is_one_way_mode:

    dynamic_marker_efficiency -= 0.05

elif is_nap_mode:

    dynamic_marker_efficiency -= 0.03


# =====================================================================
# 11. GIỚI HẠN KỸ THUẬT
# =====================================================================

dynamic_marker_efficiency = max(
    0.52,
    min(
        dynamic_marker_efficiency,
        0.95
    )
)

dynamic_marker_efficiency = round(
    dynamic_marker_efficiency,
    4
)


# =====================================================================
# 12. MASTER COMMIT
# =====================================================================

ctx["ie_detected_type"] = ie_detected_type

ctx["ie_product_type_friendly"] = friendly_product_type

ctx["ai_product_type_raw"] = str(
    raw_ai_type
)

ctx["ai_expert_decision"] = ai_decision

ctx["ai_expert_decision"][
    "ai_product_type_raw"
] = ie_detected_type

ctx["ai_expert_decision"][
    "detected_product_type"
] = ie_detected_type

ctx["ai_expert_decision"][
    "marker_efficiency"
] = dynamic_marker_efficiency


st.session_state[
    "active_marker_efficiency_value"
] = float(
    dynamic_marker_efficiency
)


st.session_state[
    "bom_data"
] = ctx


# =====================================================================
# 13. DEBUG LOG
# =====================================================================

print(
    "[MARKER ROUTER MASTER]"
    f" RAW_AI={raw_ai_type}"
    f" | NORMALIZED={ie_detected_type}"
    f" | FRIENDLY={friendly_product_type}"
    f" | MARKER={dynamic_marker_efficiency:.4f}"
    f" | NAP={is_nap_mode}"
    f" | ONE_WAY={is_one_way_mode}"
)
# =====================================================================
# 🟩 ĐOẠN 5.2 - B1 + B2
# VERSION V29.0
# MASTER COMMERCIAL CONSUMPTION ENGINE
#
# 🔒 USER COMMAND > AI MASTER > SESSION > CTX > DEFAULT
#
# MASTER:
# WIDTH + SHRINKAGE + PIECE QTY + GEOMETRY CONTROL
#
# 🔒 V29.0 FIX:
# 1. REMOVE PRODUCT GEOMETRY FACTOR 0.72 / 0.78...
# 2. NEVER ARTIFICIALLY REDUCE JACKET AREA
# 3. PROTECT AGAINST BBOX AREA INFLATION
# 4. FIX SIZE PRIORITY
# 5. FIX INVALID AI VALUE FALLBACK
# 6. SYNC USABLE WIDTH
# 7. PRESERVE SINGLE-PIECE GEOMETRY RULE
# =====================================================================

import re
import pandas as pd
import streamlit as st


# =====================================================================
# 🔒 MASTER USER PARAMETER PARSER
# =====================================================================

def _parse_ie_master_parameters(
    current_query=None,
    ai_decision=None,
    ctx=None,
):

    current_query = str(
        current_query or ""
    ).strip()

    if not isinstance(
        ai_decision,
        dict
    ):
        ai_decision = {}

    if not isinstance(
        ctx,
        dict
    ):
        ctx = {}

    # =================================================================
    # NORMALIZE USER COMMAND
    # =================================================================

    q = (
        current_query
        .replace(",", ".")
        .replace("％", "%")
        .replace("”", '"')
        .replace("″", '"')
    )

    # =================================================================
    # WIDTH - USER COMMAND
    # =================================================================

    user_width = None

    width_patterns = [

        r"(?:khổ|khô|kho)\s*(?:vải)?\s*[:=]?\s*"
        r"(\d+(?:\.\d+)?)\s*(?:[\"']|inch|in)?",

        r"(?:fabric\s*width|width)\s*[:=]?\s*"
        r"(\d+(?:\.\d+)?)\s*(?:[\"']|inch|in)?",
    ]

    for pattern in width_patterns:

        m = re.search(
            pattern,
            q,
            re.IGNORECASE
        )

        if m:

            try:
                value = float(
                    m.group(1)
                )

                if value > 0:
                    user_width = value

            except Exception:
                user_width = None

            if user_width is not None:
                break

    # =================================================================
    # WARP / DỌC
    # =================================================================

    user_warp = None

    warp_patterns = [

        r"(?:co\s*)?(?:dọc|doc)\s*[:=]?\s*"
        r"(\d+(?:\.\d+)?)\s*%?",

        r"(?:warp|warp\s*shrink|warp\s*shrinkage)"
        r"\s*[:=]?\s*"
        r"(\d+(?:\.\d+)?)\s*%?",
    ]

    for pattern in warp_patterns:

        m = re.search(
            pattern,
            q,
            re.IGNORECASE
        )

        if m:

            try:
                value = float(
                    m.group(1)
                )

                if value >= 0:
                    user_warp = value

            except Exception:
                user_warp = None

            if user_warp is not None:
                break

    # =================================================================
    # WEFT / NGANG
    # =================================================================

    user_weft = None

    weft_patterns = [

        r"(?:co\s*)?ngang\s*[:=]?\s*"
        r"(\d+(?:\.\d+)?)\s*%?",

        r"(?:weft|weft\s*shrink|weft\s*shrinkage)"
        r"\s*[:=]?\s*"
        r"(\d+(?:\.\d+)?)\s*%?",
    ]

    for pattern in weft_patterns:

        m = re.search(
            pattern,
            q,
            re.IGNORECASE
        )

        if m:

            try:
                value = float(
                    m.group(1)
                )

                if value >= 0:
                    user_weft = value

            except Exception:
                user_weft = None

            if user_weft is not None:
                break

    # =================================================================
    # AI MASTER PARAMETERS
    # =================================================================

    ai_master = ai_decision.get(
        "_master_parameters",
        {}
    )

    if not isinstance(
        ai_master,
        dict
    ):
        ai_master = {}

    # =================================================================
    # WIDTH RESOLUTION
    #
    # PRIORITY:
    # USER COMMAND
    # > AI MASTER
    # > SESSION
    # > CTX
    # > DEFAULT
    # =================================================================

    resolved_width = None
    width_source = "DEFAULT"

    if user_width is not None:

        resolved_width = user_width
        width_source = "USER_COMMAND"

    else:

        try:

            ai_width = ai_master.get(
                "fabric_width_inch",
                None
            )

            if (
                ai_width is not None
                and float(ai_width) > 0
            ):

                resolved_width = float(
                    ai_width
                )

                width_source = "AI_MASTER"

        except Exception:

            resolved_width = None

    if resolved_width is None:

        try:

            session_width = st.session_state.get(
                "current_active_width",
                None
            )

            if (
                session_width is not None
                and float(session_width) > 0
            ):

                resolved_width = float(
                    session_width
                )

                width_source = "SESSION"

        except Exception:

            resolved_width = None

    if resolved_width is None:

        try:

            ctx_width = ctx.get(
                "fabric_width_inch",
                None
            )

            if (
                ctx_width is not None
                and float(ctx_width) > 0
            ):

                resolved_width = float(
                    ctx_width
                )

                width_source = "CTX"

        except Exception:

            resolved_width = None

    if resolved_width is None:

        resolved_width = 58.0
        width_source = "DEFAULT"

    # =================================================================
    # WARP RESOLUTION
    # =================================================================

    resolved_warp = None
    warp_source = "DEFAULT"

    if user_warp is not None:

        resolved_warp = user_warp
        warp_source = "USER_COMMAND"

    else:

        try:

            ai_warp = ai_master.get(
                "warp_shrink_percent",
                None
            )

            if (
                ai_warp is not None
                and float(ai_warp) >= 0
            ):

                resolved_warp = float(
                    ai_warp
                )

                warp_source = "AI_MASTER"

        except Exception:

            resolved_warp = None

    if resolved_warp is None:

        try:

            session_warp = st.session_state.get(
                "current_warp_shrinkage",
                None
            )

            if (
                session_warp is not None
                and float(session_warp) >= 0
            ):

                resolved_warp = float(
                    session_warp
                )

                warp_source = "SESSION"

        except Exception:

            resolved_warp = None

    if resolved_warp is None:

        try:

            ctx_warp = ctx.get(
                "warp_shrinkage_percent",
                None
            )

            if (
                ctx_warp is not None
                and float(ctx_warp) >= 0
            ):

                resolved_warp = float(
                    ctx_warp
                )

                warp_source = "CTX"

        except Exception:

            resolved_warp = None

    if resolved_warp is None:

        resolved_warp = 0.0
        warp_source = "DEFAULT"

    # =================================================================
    # WEFT RESOLUTION
    # =================================================================

    resolved_weft = None
    weft_source = "DEFAULT"

    if user_weft is not None:

        resolved_weft = user_weft
        weft_source = "USER_COMMAND"

    else:

        try:

            ai_weft = ai_master.get(
                "weft_shrink_percent",
                None
            )

            if (
                ai_weft is not None
                and float(ai_weft) >= 0
            ):

                resolved_weft = float(
                    ai_weft
                )

                weft_source = "AI_MASTER"

        except Exception:

            resolved_weft = None

    if resolved_weft is None:

        try:

            session_weft = st.session_state.get(
                "current_weft_shrinkage",
                None
            )

            if (
                session_weft is not None
                and float(session_weft) >= 0
            ):

                resolved_weft = float(
                    session_weft
                )

                weft_source = "SESSION"

        except Exception:

            resolved_weft = None

    if resolved_weft is None:

        try:

            ctx_weft = ctx.get(
                "weft_shrinkage_percent",
                None
            )

            if (
                ctx_weft is not None
                and float(ctx_weft) >= 0
            ):

                resolved_weft = float(
                    ctx_weft
                )

                weft_source = "CTX"

        except Exception:

            resolved_weft = None

    if resolved_weft is None:

        resolved_weft = 0.0
        weft_source = "DEFAULT"

    # =================================================================
    # SIZE
    #
    # FIX:
    # USER > AI > SESSION > CTX > DEFAULT
    # =================================================================

    size_match = re.search(
        r"\bsize\s*[:=]?\s*([A-Za-z0-9._-]+)",
        q,
        re.IGNORECASE
    )

    if size_match:

        resolved_size = str(
            size_match.group(1)
        ).strip()

        size_source = "USER_COMMAND"

    elif ai_master.get("size") is not None:

        resolved_size = str(
            ai_master.get("size")
        ).strip()

        size_source = "AI_MASTER"

    else:

        session_size = st.session_state.get(
            "current_active_size",
            None
        )

        if (
            session_size is not None
            and str(session_size).strip()
        ):

            resolved_size = str(
                session_size
            ).strip()

            size_source = "SESSION"

        else:

            ctx_size = ctx.get(
                "calculated_on_size",
                None
            )

            if (
                ctx_size is not None
                and str(ctx_size).strip()
            ):

                resolved_size = str(
                    ctx_size
                ).strip()

                size_source = "CTX"

            else:

                target_size = st.session_state.get(
                    "target_size",
                    ""
                )

                if str(target_size).strip():

                    resolved_size = str(
                        target_size
                    ).strip()

                    size_source = "SESSION"

                else:

                    resolved_size = "32"
                    size_source = "DEFAULT"

    # =================================================================
    # RETURN MASTER
    # =================================================================

    return {

        "width": float(
            resolved_width
        ),

        "warp_shrink_percent": float(
            resolved_warp
        ),

        "weft_shrink_percent": float(
            resolved_weft
        ),

        "size": resolved_size,

        "width_source": width_source,
        "warp_source": warp_source,
        "weft_source": weft_source,
        "size_source": size_source,
    }


# =====================================================================
# B1 - INITIALIZATION & DATA RECOVERY
# =====================================================================

if "bom_data" not in st.session_state:

    st.session_state[
        "bom_data"
    ] = {}


ctx = st.session_state[
    "bom_data"
]


if not isinstance(
    ctx,
    dict
):

    ctx = {}

    st.session_state[
        "bom_data"
    ] = ctx


# =====================================================================
# AI EXPERT DECISION
# =====================================================================

if "ai_expert_decision" not in ctx:

    ctx[
        "ai_expert_decision"
    ] = {}


ai_decision = ctx[
    "ai_expert_decision"
]


if not isinstance(
    ai_decision,
    dict
):

    ai_decision = {}

    ctx[
        "ai_expert_decision"
    ] = ai_decision


# =====================================================================
# 🔒 CURRENT USER COMMAND
# =====================================================================

current_query = str(
    st.session_state.get(
        "current_query",
        st.session_state.get(
            "user_query",
            ""
        )
    )
)


# =====================================================================
# 🔒 MASTER PARAMETERS
# =====================================================================

ie_master = _parse_ie_master_parameters(
    current_query=current_query,
    ai_decision=ai_decision,
    ctx=ctx,
)


parsed_width = ie_master[
    "width"
]

shrink_v_percent = ie_master[
    "warp_shrink_percent"
]

shrink_h_percent = ie_master[
    "weft_shrink_percent"
]

shrink_v = (
    shrink_v_percent / 100.0
)

shrink_h = (
    shrink_h_percent / 100.0
)


# =====================================================================
# 🔒 MASTER SESSION COMMIT
# =====================================================================

st.session_state[
    "current_active_width"
] = parsed_width

st.session_state[
    "current_warp_shrinkage"
] = shrink_v_percent

st.session_state[
    "current_weft_shrinkage"
] = shrink_h_percent

st.session_state[
    "current_active_size"
] = ie_master[
    "size"
]


# =====================================================================
# 🔒 MASTER CTX COMMIT
# =====================================================================

ctx[
    "fabric_width_inch"
] = parsed_width

ctx[
    "usable_width_inch"
] = parsed_width

ctx[
    "warp_shrinkage_percent"
] = shrink_v_percent

ctx[
    "weft_shrinkage_percent"
] = shrink_h_percent

ctx[
    "calculated_on_size"
] = ie_master[
    "size"
]


# =====================================================================
# 🔒 MASTER AUDIT
# =====================================================================

ctx[
    "_ie_master_parameters"
] = {

    "width": parsed_width,

    "usable_width": parsed_width,

    "warp_shrink_percent": (
        shrink_v_percent
    ),

    "weft_shrink_percent": (
        shrink_h_percent
    ),

    "size": ie_master[
        "size"
    ],

    "width_source": ie_master[
        "width_source"
    ],

    "warp_source": ie_master[
        "warp_source"
    ],

    "weft_source": ie_master[
        "weft_source"
    ],

    "size_source": ie_master[
        "size_source"
    ],

    "priority": (
        "USER_COMMAND > AI_MASTER > "
        "SESSION > CTX > DEFAULT"
    ),
}


# =====================================================================
# VIRTUAL PIECES
# =====================================================================

stored_virtual_pieces = ai_decision.get(
    "virtual_pieces_layer",
    {}
)


if not isinstance(
    stored_virtual_pieces,
    dict
):

    stored_virtual_pieces = {}


# =====================================================================
# SUMMARY
# =====================================================================

summary_grouped_gross = {

    "FABRIC": 0.0,
    "FUSING": 0.0,
    "LINING": 0.0,
    "CONTRAST": 0.0,
    "RIB": 0.0,
    "PADDING": 0.0,
}


# =====================================================================
# WASTAGE
# =====================================================================

wastage_allowance = 1.05


# =====================================================================
# MARKER EFFICIENCY
# =====================================================================

try:

    base_efficiency = float(
        st.session_state.get(
            "active_marker_efficiency_value",
            0.78
        )
    )

except Exception:

    base_efficiency = 0.78


base_efficiency = max(
    0.52,
    min(
        base_efficiency,
        0.95
    )
)


# =====================================================================
# PRODUCT TYPE MASTER
# =====================================================================

product_type = str(
    ctx.get(
        "ie_detected_type",
        ai_decision.get(
            "ai_product_type_raw",
            "JEAN_LONG"
        )
    )
).upper().strip()


# =====================================================================
# 🔒 V29.0 GEOMETRY POLICY
#
# KHÔNG dùng PRODUCT GEOMETRY FACTOR để ép DM cao/thấp.
#
# Diện tích phải đến từ:
#   1. polygon_net_area
#   2. geometry thật
#   3. bounding box chỉ là fallback cuối
#
# Jacket / Jean / Pant đều = 1.00
#
# Không được:
#   JACKET = 0.72
#   BLAZER = 0.78
#   DRESS = 0.92
#
# vì các hệ số này làm sai bản chất diện tích rập.
# =====================================================================

geometry_factor = 1.00


# =====================================================================
# B2 - COMMERCIAL CONSUMPTION ENGINE
# =====================================================================

if (
    "df_bom" in locals()
    and df_bom is not None
    and isinstance(df_bom, pd.DataFrame)
    and not df_bom.empty
):

    for idx, r in df_bom.iterrows():

        # =============================================================
        # VIRTUAL PIECE RECOVERY
        # =============================================================

        v = stored_virtual_pieces.get(
            idx,
            stored_virtual_pieces.get(
                str(idx),
                {}
            )
        )

        if not isinstance(
            v,
            dict
        ):

            v = {}


        # =============================================================
        # COMPONENT
        # =============================================================

        c_name = str(
            r.get(
                "component_name",
                v.get(
                    "component_name",
                    ""
                )
            )
        ).strip()


        c_name_lower = (
            c_name.lower()
        )


        # =============================================================
        # MATERIAL CLASS
        # =============================================================

        p_cls = str(
            v.get(
                "material_class",
                r.get(
                    "Material Class",
                    "FABRIC"
                )
            )
        ).upper().strip()


        if p_cls not in summary_grouped_gross:

            p_cls = "FABRIC"


        # =============================================================
        # GEOMETRY - LENGTH
        # =============================================================

        try:

            p_length = float(
                v.get(
                    "production_l",
                    r.get(
                        "Chiều dài rập (inch)",
                        r.get(
                            "bounding_box_length",
                            0.0
                        )
                    )
                )
            )

        except Exception:

            p_length = 0.0


        # =============================================================
        # GEOMETRY - WIDTH
        # =============================================================

        try:

            p_width = float(
                v.get(
                    "production_w",
                    r.get(
                        "Chiều rộng rập (inch)",
                        r.get(
                            "bounding_box_width",
                            0.0
                        )
                    )
                )
            )

        except Exception:

            p_width = 0.0


        # =============================================================
        # PURE UNIT AREA
        #
        # 🔒 ƯU TIÊN POLYGON AREA
        # 🔒 KHÔNG NHÂN PRODUCT GEOMETRY FACTOR
        # =============================================================

        try:

            pure_unit_area = float(
                v.get(
                    "polygon_net_area",
                    r.get(
                        "polygon_net_area",
                        0.0
                    )
                )
            )

        except Exception:

            pure_unit_area = 0.0


        # =============================================================
        # FALLBACK AREA
        #
        # Chỉ dùng BBOX nếu polygon area không tồn tại.
        # =============================================================

        area_source = "POLYGON"

        if pure_unit_area <= 0:

            pure_unit_area = (
                p_length
                *
                p_width
            )

            area_source = "BBOX_FALLBACK"


        # =============================================================
        # ABSOLUTE SAFETY
        # =============================================================

        if pure_unit_area <= 0:

            pure_unit_area = 10.0

            area_source = "MINIMUM_FALLBACK"


        # =============================================================
        # 🔒 GEOMETRY CORRECTION
        #
        # V29:
        # KHÔNG GIẢM AREA THEO PRODUCT TYPE.
        # =============================================================

        corrected_unit_area = (
            pure_unit_area
            *
            geometry_factor
        )


        # =============================================================
        # USER PIECE OVERRIDE
        # =============================================================

        user_pieces_dict = (
            st.session_state.get(
                "user_edited_pieces",
                {}
            )
        )


        if not isinstance(
            user_pieces_dict,
            dict
        ):

            user_pieces_dict = {}


        user_override_exists = (
            idx in user_pieces_dict
            or
            str(idx) in user_pieces_dict
        )


        if idx in user_pieces_dict:

            try:

                pcs = int(
                    user_pieces_dict[idx]
                )

            except Exception:

                pcs = 1

        elif str(idx) in user_pieces_dict:

            try:

                pcs = int(
                    user_pieces_dict[str(idx)]
                )

            except Exception:

                pcs = 1

        elif (
            "active_user_pieces" in v
            and
            pd.notna(
                v.get(
                    "active_user_pieces"
                )
            )
            and
            int(
                v.get(
                    "active_user_pieces"
                )
            ) >= 1
        ):

            pcs = int(
                v.get(
                    "active_user_pieces"
                )
            )

        else:

            raw_pcs = r.get(
                "Số lượng rập",
                None
            )

            try:

                if (
                    raw_pcs is not None
                    and
                    pd.notna(raw_pcs)
                    and
                    int(raw_pcs) >= 1
                ):

                    pcs = int(
                        raw_pcs
                    )

                else:

                    pcs = 1

            except Exception:

                pcs = 1


        # =============================================================
        # FALLBACK PIECE QTY
        #
        # Chỉ áp dụng khi thực sự không có thông tin qty.
        # =============================================================

        if (
            not user_override_exists
            and
            pcs == 1
        ):

            raw_pcs = r.get(
                "Số lượng rập",
                None
            )

            has_valid_qty = False

            try:

                has_valid_qty = (
                    raw_pcs is not None
                    and
                    pd.notna(raw_pcs)
                    and
                    int(raw_pcs) >= 1
                )

            except Exception:

                has_valid_qty = False


            if (
                not has_valid_qty
                and
                not v.get(
                    "active_user_pieces"
                )
            ):

                if any(
                    x in c_name_lower
                    for x in [
                        "front leg",
                        "back leg",
                        "than truoc",
                        "than sau",
                        "ong quan",
                        "sleeve pair"
                    ]
                ):

                    pcs = 2


        pcs = max(
            int(pcs),
            1
        )


        # =============================================================
        # MASTER PIECE QTY COMMIT
        # =============================================================

        df_bom.at[
            idx,
            "Số lượng rập"
        ] = pcs


        if idx not in stored_virtual_pieces:

            stored_virtual_pieces[
                idx
            ] = {}


        stored_virtual_pieces[
            idx
        ][
            "active_user_pieces"
        ] = pcs


        stored_virtual_pieces[
            idx
        ][
            "polygon_net_area_corrected"
        ] = corrected_unit_area


        stored_virtual_pieces[
            idx
        ][
            "area_source"
        ] = area_source


        # =============================================================
        # SEAM ALLOWANCE
        # =============================================================

        area_includes_seam = bool(
            v.get(
                "area_includes_seam",
                False
            )
            or
            r.get(
                "area_includes_seam",
                False
            )
        )


        if (
            p_cls in [
                "FABRIC",
                "CONTRAST"
            ]
            and
            not area_includes_seam
        ):

            seam_modifier = 1.06

        else:

            seam_modifier = 1.00


        total_piece_area = (
            corrected_unit_area
            *
            pcs
            *
            seam_modifier
        )


        # =============================================================
        # WIDTH BY MATERIAL
        # =============================================================

        if p_cls == "FUSING":

            current_w = float(
                st.session_state.get(
                    "fusing_width",
                    59.0
                )
            )

        elif p_cls == "LINING":

            current_w = float(
                st.session_state.get(
                    "lining_width",
                    57.0
                )
            )

        elif p_cls == "RIB":

            current_w = float(
                st.session_state.get(
                    "rib_width",
                    40.0
                )
            )

        elif p_cls == "PADDING":

            current_w = float(
                st.session_state.get(
                    "padding_width",
                    60.0
                )
            )

        else:

            current_w = parsed_width


        if current_w <= 0:

            current_w = 58.0


        # =============================================================
        # 🔒 MASTER WIDTH COMMIT
        # =============================================================

        df_bom.at[
            idx,
            "Khổ vải sản xuất (inch)"
        ] = current_w


        # =============================================================
        # MARKER EFFICIENCY
        # =============================================================

        row_efficiency = (
            base_efficiency
        )


        if p_cls in [
            "FUSING",
            "LINING"
        ]:

            row_efficiency = 0.60

        elif p_cls == "RIB":

            row_efficiency = 0.82

        elif p_cls == "PADDING":

            row_efficiency = 0.85


        row_efficiency = max(
            0.52,
            min(
                row_efficiency,
                0.95
            )
        )


        # =============================================================
        # SHRINKAGE
        #
        # 🔒 CHỈ DÙNG MASTER RESOLVED VALUES
        # =============================================================

        shrinkage_multiplier = (
            (1.0 + shrink_v)
            *
            (1.0 + shrink_h)
        )


        # =============================================================
        # GROSS AREA
        # =============================================================

        gross_area_sq_inches = (
            total_piece_area
            /
            row_efficiency
        )


        # =============================================================
        # POST SHRINKAGE
        # =============================================================

        gross_area_post_shrink = (
            gross_area_sq_inches
            *
            shrinkage_multiplier
        )


        # =============================================================
        # LINEAR INCHES
        # =============================================================

        linear_inches_needed = (
            gross_area_post_shrink
            /
            current_w
        )


        # =============================================================
        # WASTAGE
        # =============================================================

        if area_includes_seam:

            actual_wastage = 1.03

        else:

            actual_wastage = (
                wastage_allowance
            )


        total_inches_with_wastage = (
            linear_inches_needed
            *
            actual_wastage
        )


        # =============================================================
        # YARDS
        # =============================================================

        gross_consumption_yards = (
            total_inches_with_wastage
            /
            36.0
        )


        gross_consumption_yards = round(
            max(
                0.0,
                gross_consumption_yards
            ),
            4
        )


        # =============================================================
        # COMMIT GROSS CONSUMPTION
        # =============================================================

        df_bom.at[
            idx,
            "Gross Consumption"
        ] = gross_consumption_yards


        summary_grouped_gross[
            p_cls
        ] += gross_consumption_yards


        # =============================================================
        # 🔒 ROW MASTER AUDIT
        # =============================================================

        df_bom.at[
            idx,
            "_master_width"
        ] = current_w

        df_bom.at[
            idx,
            "_master_warp_shrink"
        ] = shrink_v_percent

        df_bom.at[
            idx,
            "_master_weft_shrink"
        ] = shrink_h_percent

        df_bom.at[
            idx,
            "_area_source"
        ] = area_source

        df_bom.at[
            idx,
            "_geometry_factor"
        ] = geometry_factor

        df_bom.at[
            idx,
            "_efficiency"
        ] = row_efficiency

        df_bom.at[
            idx,
            "_seam_modifier"
        ] = seam_modifier

        df_bom.at[
            idx,
            "_wastage"
        ] = actual_wastage


        # =============================================================
        # DEBUG
        # =============================================================

        print(
            "[DM ENGINE]"
            f" idx={idx}"
            f" | product={product_type}"
            f" | comp={c_name}"
            f" | class={p_cls}"
            f" | pcs={pcs}"
            f" | area_source={area_source}"
            f" | raw_area={pure_unit_area:.2f}"
            f" | geometry_factor={geometry_factor:.2f}"
            f" | corrected_area={corrected_unit_area:.2f}"
            f" | width={current_w:.2f}"
            f" | shrink_v={shrink_v_percent:.2f}%"
            f" | shrink_h={shrink_h_percent:.2f}%"
            f" | efficiency={row_efficiency:.4f}"
            f" | seam={seam_modifier:.4f}"
            f" | wastage={actual_wastage:.4f}"
            f" | gross={gross_consumption_yards:.4f} Yds"
        )


    # =================================================================
    # SUMMARY COMMIT
    # =================================================================

    for k in summary_grouped_gross:

        summary_grouped_gross[k] = round(
            summary_grouped_gross[k],
            4
        )


    st.session_state[
        "summary_grouped_gross"
    ] = summary_grouped_gross


    # =================================================================
    # VIRTUAL PIECES COMMIT
    # =================================================================

    ai_decision[
        "virtual_pieces_layer"
    ] = stored_virtual_pieces


    ctx[
        "ai_expert_decision"
    ] = ai_decision


    # =================================================================
    # FINAL NUMERIC NORMALIZATION
    # =================================================================

    if "Gross Consumption" in df_bom.columns:

        df_bom[
            "Gross Consumption"
        ] = pd.to_numeric(
            df_bom[
                "Gross Consumption"
            ],
            errors="coerce"
        ).fillna(
            0.0
        ).round(4)


    # =================================================================
    # FINAL MASTER COMMIT
    # =================================================================

    st.session_state[
        "active_calculated_df_bom"
    ] = df_bom.copy()


    st.session_state[
        "bom_data"
    ] = ctx


    # =================================================================
    # 🔒 FINAL MASTER AUDIT
    # =================================================================

    total_dm = float(
        df_bom[
            "Gross Consumption"
        ].sum()
    )


    print(
        "[DM ENGINE FINAL]"
        f" Product={product_type}"
        f" | Size={ie_master['size']}"
        f" | Width={parsed_width:.2f}\""
        f" | Warp Shrink={shrink_v_percent:.2f}%"
        f" | Weft Shrink={shrink_h_percent:.2f}%"
        f" | Width Source={ie_master['width_source']}"
        f" | Warp Source={ie_master['warp_source']}"
        f" | Weft Source={ie_master['weft_source']}"
        f" | Size Source={ie_master['size_source']}"
        f" | Geometry Factor={geometry_factor:.2f}"
        f" | Rows={len(df_bom)}"
        f" | Total DM={total_dm:.4f} Yds"
    )
    # =====================================================================
    # 🟩 ĐOẠN 5.2C
    # VERSION V29.1
    # MASTER COMMERCIAL ENGINE CONTROL
    #
    # 🔒 5.2C = CONTROL / RECOVERY LAYER
    #
    # KHÔNG TÍNH DM
    # KHÔNG TẠO WIDTH MỚI
    # KHÔNG TẠO SHRINKAGE MỚI
    # KHÔNG TẠO SIZE MỚI
    #
    # NHIỆM VỤ:
    # 1. RECOVER BOM
    # 2. GIỮ MASTER TỪ B1
    # 3. ĐẢM BẢO B2 CÓ df_bom ĐỂ CHẠY
    # 4. KHÔNG RERUN VÒNG LẶP
    # =====================================================================

    import pandas as pd
    import streamlit as st


    # =====================================================================
    # BẢO ĐẢM BOM DATA
    # =====================================================================

    if "bom_data" not in st.session_state:

        st.session_state[
            "bom_data"
        ] = {}


    ctx = st.session_state[
        "bom_data"
    ]


    if not isinstance(
        ctx,
        dict
    ):

        ctx = {}

        st.session_state[
            "bom_data"
        ] = ctx


    # =====================================================================
    # AI DECISION
    # =====================================================================

    ai_decision = ctx.get(
        "ai_expert_decision",
        {}
    )


    if not isinstance(
        ai_decision,
        dict
    ):

        ai_decision = {}

        ctx[
            "ai_expert_decision"
        ] = ai_decision


    # =====================================================================
    # 🔥 RECOVER df_bom
    # =====================================================================

    if (
        "df_bom" not in locals()
        or df_bom is None
        or not isinstance(
            df_bom,
            pd.DataFrame
        )
        or df_bom.empty
    ):

        rows_raw = ctx.get(
            "bom_rows",
            []
        )


        if (
            not isinstance(
                rows_raw,
                list
            )
            or
            len(rows_raw) == 0
        ):

            rows_raw = st.session_state.get(
                "processed_display_rows",
                []
            )


        if (
            isinstance(
                rows_raw,
                list
            )
            and
            len(rows_raw) > 0
        ):

            try:

                df_bom = pd.DataFrame(
                    rows_raw
                )

                print(
                    "[5.2C RECOVERY]"
                    f" | df_bom restored"
                    f" | rows={len(df_bom)}"
                )

            except Exception as e:

                print(
                    f"[5.2C RECOVERY ERROR] {e}"
                )

                df_bom = None


    # =====================================================================
    # 🔒 MASTER PARAMETERS
    #
    # CHỈ ĐỌC MASTER ĐÃ ĐƯỢC B1 RESOLVE
    # =====================================================================

    master = ctx.get(
        "_ie_master_parameters",
        {}
    )


    if not isinstance(
        master,
        dict
    ):

        master = {}


    # =====================================================================
    # 🔒 MASTER SYNC
    # =====================================================================

    if master:

        try:

            master_width = float(
                master.get(
                    "width"
                )
            )

            master_usable_width = float(
                master.get(
                    "usable_width",
                    master_width
                )
            )

            master_warp = float(
                master.get(
                    "warp_shrink_percent",
                    0.0
                )
            )

            master_weft = float(
                master.get(
                    "weft_shrink_percent",
                    0.0
                )
            )

            master_size = str(
                master.get(
                    "size",
                    ""
                )
            ).strip()


            # =============================================================
            # SESSION SYNC
            # =============================================================

            st.session_state[
                "current_active_width"
            ] = master_width

            st.session_state[
                "current_active_size"
            ] = master_size

            st.session_state[
                "current_warp_shrinkage"
            ] = master_warp

            st.session_state[
                "current_weft_shrinkage"
            ] = master_weft


            # =============================================================
            # CTX SYNC
            # =============================================================

            ctx[
                "fabric_width_inch"
            ] = master_width

            ctx[
                "usable_width_inch"
            ] = master_usable_width

            ctx[
                "calculated_on_size"
            ] = master_size

            ctx[
                "warp_shrinkage_percent"
            ] = master_warp

            ctx[
                "weft_shrinkage_percent"
            ] = master_weft


            print(
                "[5.2C MASTER]"
                f" | Width={master_width:.2f}\""
                f" | Usable={master_usable_width:.2f}\""
                f" | Size={master_size}"
                f" | Warp={master_warp:.2f}%"
                f" | Weft={master_weft:.2f}%"
            )


        except Exception as e:

            print(
                f"[5.2C MASTER ERROR] {e}"
            )


    # =====================================================================
    # 🔥 VIRTUAL PIECES
    # =====================================================================

    virtual_pieces = ai_decision.get(
        "virtual_pieces_layer",
        {}
    )


    if not isinstance(
        virtual_pieces,
        dict
    ):

        virtual_pieces = {}


    # =====================================================================
    # 🔥 CHECK RAW BOM
    # =====================================================================

    has_raw_bom = (

        isinstance(
            ctx.get(
                "bom_rows"
            ),
            list
        )

        and

        len(
            ctx.get(
                "bom_rows",
                []
            )
        ) > 0
    )


    # =====================================================================
    # 🔥 CHECK VIRTUAL PIECES
    # =====================================================================

    has_virtual_pieces = (

        isinstance(
            virtual_pieces,
            dict
        )

        and

        len(
            virtual_pieces
        ) > 0
    )


    # =====================================================================
    # 🔥 CHECK CALCULATED BOM
    # =====================================================================

    has_calculated_bom = (

        "active_calculated_df_bom"
        in
        st.session_state

        and

        isinstance(
            st.session_state.get(
                "active_calculated_df_bom"
            ),
            pd.DataFrame
        )

        and

        not st.session_state[
            "active_calculated_df_bom"
        ].empty
    )


    # =====================================================================
    # 🔥 FINAL DF CHECK
    # =====================================================================

    has_working_df_bom = (

        "df_bom" in locals()

        and

        df_bom is not None

        and

        isinstance(
            df_bom,
            pd.DataFrame
        )

        and

        not df_bom.empty
    )


    # =====================================================================
    # 🔒 SAVE RECOVERED BOM
    # =====================================================================

    if has_working_df_bom:

        try:

            ctx[
                "bom_rows"
            ] = df_bom.to_dict(
                orient="records"
            )

        except Exception as e:

            print(
                f"[5.2C BOM SAVE ERROR] {e}"
            )


    # =====================================================================
    # 🔥 DO NOT FORCE RERUN
    #
    # B2 sẽ chạy tiếp trong cùng execution.
    # =====================================================================

    if (
        has_working_df_bom
        and
        not has_calculated_bom
    ):

        print(
            "[5.2C]"
            " | B2 READY"
            f" | rows={len(df_bom)}"
            " | ACTION=CONTINUE_TO_B2"
        )


    elif has_calculated_bom:

        print(
            "[5.2C]"
            " | CALCULATED BOM EXISTS"
            " | ACTION=SKIP"
        )


    elif (
        has_raw_bom
        or
        has_virtual_pieces
    ):

        print(
            "[5.2C]"
            " | BOM DATA EXISTS"
            " | df_bom NOT AVAILABLE"
            " | WAITING RECOVERY"
        )


    else:

        print(
            "[5.2C]"
            " | NO BOM DATA"
            " | ACTION=WAIT"
        )


    # =====================================================================
    # 🔒 FINAL CTX COMMIT
    # =====================================================================

    st.session_state[
        "bom_data"
    ] = ctx


    # =====================================================================
    # DEBUG
    # =====================================================================

    print(
        "[5.2C FINAL]"
        f" | raw_bom={has_raw_bom}"
        f" | virtual={has_virtual_pieces}"
        f" | df_bom={has_working_df_bom}"
        f" | calculated={has_calculated_bom}"
        " | STATUS=READY"
    )
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
    # 🟩 ĐOẠN 7.1 (VERSION V27.0): DISPLAY LAYER - SUMMARY ONLY
    # =====================================================================
    import re
    import pandas as pd
    import streamlit as st

    # ---------------------------------------------------------------------
    # 1. MASTER CONTEXT RECOVERY
    # ---------------------------------------------------------------------
    if "bom_data" not in st.session_state or not isinstance(st.session_state["bom_data"], dict):
        st.session_state["bom_data"] = {}

    ctx = st.session_state["bom_data"]

    if "ai_expert_decision" not in ctx or not isinstance(ctx["ai_expert_decision"], dict):
        ctx["ai_expert_decision"] = {}

    ai_decision_final = ctx["ai_expert_decision"]

    # ---------------------------------------------------------------------
    # 2. SUMMARY GROSS RECOVERY
    # ---------------------------------------------------------------------
    grouped_gross = st.session_state.get(
        "summary_grouped_gross",
        {
            "FABRIC": 0.0,
            "FUSING": 0.0,
            "LINING": 0.0,
            "CONTRAST": 0.0,
            "RIB": 0.0,
            "PADDING": 0.0
        }
    )

    if not isinstance(grouped_gross, dict):
        grouped_gross = {
            "FABRIC": 0.0,
            "FUSING": 0.0,
            "LINING": 0.0,
            "CONTRAST": 0.0,
            "RIB": 0.0,
            "PADDING": 0.0
        }

    # ---------------------------------------------------------------------
    # 3. DEBUG MASTER RAM
    # ---------------------------------------------------------------------
    st.markdown("### 🔬 Hệ Thống Kiểm Toán Dữ Liệu RAM")

    d_c1, d_c2, d_c3 = st.columns(3)

    d_c1.write(
        f"**DEBUG FABRIC:** "
        f"`{float(grouped_gross.get('FABRIC', 0.0)):.4f} Yds`"
    )

    d_c2.write(
        f"**DEBUG LINING:** "
        f"`{float(grouped_gross.get('LINING', 0.0)):.4f} Yds`"
    )

    d_c3.write(
        f"**DEBUG FUSING:** "
        f"`{float(grouped_gross.get('FUSING', 0.0)):.4f} Yds`"
    )

    st.divider()

    # ---------------------------------------------------------------------
    # 4. AI AUDIT REPORT
    # ---------------------------------------------------------------------
    st.header(
        "📋 AI AUDIT REPORT "
        "(BÁO CÁO KIỂM TOÁN ĐỊNH MỨC TỰ ĐỘNG)"
    )

    virtual_pieces = ai_decision_final.get(
        "virtual_pieces_layer",
        {}
    )

    if not isinstance(virtual_pieces, dict):
        virtual_pieces = {}

    # ---------------------------------------------------------------------
    # 5. COMPLEXITY
    # ---------------------------------------------------------------------
    try:
        comp_score_val = float(
            ai_decision_final.get("complexity_score", 45.0)
        )
    except (TypeError, ValueError):
        comp_score_val = 45.0

    comp_score_val = max(
        0.0,
        min(comp_score_val, 100.0)
    )

    ui_complexity_tier = (
        "COMPLEX"
        if comp_score_val >= 50
        else "NORMAL"
    )

    ui_complexity_icon = (
        "🔴"
        if comp_score_val >= 75
        else (
            "🟡"
            if comp_score_val >= 45
            else "🟢"
        )
    )

    # ---------------------------------------------------------------------
    # 6. PRODUCT TYPE
    # ---------------------------------------------------------------------
    real_sync_product_type = str(
        ctx.get(
            "ie_product_type_friendly",
            ai_decision_final.get(
                "product_type_friendly",
                "JEAN_LONG (Quần dài Jeans/Pants)"
            )
        )
    ).strip()

    # ---------------------------------------------------------------------
    # 7. MARKER EFFICIENCY
    # ---------------------------------------------------------------------
    try:
        marker_efficiency = float(
            st.session_state.get(
                "active_marker_efficiency_value",
                ai_decision_final.get(
                    "marker_efficiency",
                    0.7400
                )
            )
        )
    except (TypeError, ValueError):
        marker_efficiency = 0.7400

    marker_efficiency = max(
        0.0,
        min(marker_efficiency, 1.0)
    )

    # ---------------------------------------------------------------------
    # 8. FABRIC WIDTH MASTER
    # ---------------------------------------------------------------------
    try:
        chat_width_override = float(
            st.session_state.get(
                "current_active_width",
                st.session_state.get(
                    "fabric_width_inch",
                    ctx.get("fabric_width_inch", 58.0)
                )
            )
        )
    except (TypeError, ValueError):
        chat_width_override = 58.0

    if chat_width_override <= 0:
        chat_width_override = 58.0

    # ---------------------------------------------------------------------
    # 9. MATERIAL WIDTH MASTER
    # ---------------------------------------------------------------------
    def get_width_value(session_keys, default_value):
        for key in session_keys:
            value = st.session_state.get(key)

            try:
                value = float(value)
                if value > 0:
                    return value
            except (TypeError, ValueError):
                pass

        return float(default_value)

    fusing_w_audit = get_width_value(
        ["fusing_width_inch", "fusing_width"],
        59.0
    )

    lining_w_audit = get_width_value(
        ["lining_width_inch", "lining_width"],
        57.0
    )

    rib_w_audit = get_width_value(
        ["rib_width_inch", "rib_width"],
        40.0
    )

    padding_w_audit = get_width_value(
        ["padding_width_inch", "padding_width"],
        60.0
    )

    # ---------------------------------------------------------------------
    # 10. TECHNICAL WIDTH AUDIT
    # ---------------------------------------------------------------------
    st.caption(
        f"🔗 **Bảng tra cứu khổ vải kỹ thuật đang áp dụng:** "
        f"Chính (Chat): `{chat_width_override:.1f}\"` | "
        f"Keo (Fusing): `{fusing_w_audit:.1f}\"` | "
        f"Lót (Lining): `{lining_w_audit:.1f}\"` | "
        f"Bo (Rib): `{rib_w_audit:.1f}\"` | "
        f"Gòn (Padding): `{padding_w_audit:.1f}\"`"
    )

    # ---------------------------------------------------------------------
    # 11. MASTER KPI
    # ---------------------------------------------------------------------
    try:
        confidence_value = float(
            ctx.get("confidence", 0.95)
        )
    except (TypeError, ValueError):
        confidence_value = 0.95

    # Hỗ trợ cả trường hợp AI trả 95 thay vì 0.95
    if confidence_value > 1.0:
        confidence_value = confidence_value / 100.0

    confidence_value = max(
        0.0,
        min(confidence_value, 1.0)
    )

    m1, m2, m3, m4 = st.columns(4)

    m1.metric(
        "🤖 Chủng Loại Nhận Diện (IE)",
        real_sync_product_type
    )

    m2.metric(
        f"{ui_complexity_icon} Mức Độ Phức Tạp",
        f"{ui_complexity_tier} ({comp_score_val:.0f}/100)"
    )

    m3.metric(
        "📐 Mật Độ Sơ Đồ Chỉ Định",
        f"{marker_efficiency * 100:.2f}%"
    )

    m4.metric(
        "🎯 Độ Tin Cậy AI (Confidence)",
        f"{confidence_value * 100:.1f}%"
    )

    # ---------------------------------------------------------------------
    # 12. LẤY DATAFRAME MASTER ĐÃ TÍNH
    # ---------------------------------------------------------------------
    if (
        "active_calculated_df_bom" in st.session_state
        and isinstance(
            st.session_state["active_calculated_df_bom"],
            pd.DataFrame
        )
    ):
        df_bom_display = (
            st.session_state["active_calculated_df_bom"].copy()
        )

    elif (
        "df_bom" in locals()
        and isinstance(df_bom, pd.DataFrame)
    ):
        df_bom_display = df_bom.copy()

    else:
        df_bom_display = pd.DataFrame()

    # ---------------------------------------------------------------------
    # 13. MASTER TOTAL GROSS DM
    # ---------------------------------------------------------------------
    if "Gross Consumption" not in df_bom_display.columns:
        df_bom_display["Gross Consumption"] = 0.0

    df_bom_display["Gross Consumption"] = pd.to_numeric(
        df_bom_display["Gross Consumption"],
        errors="coerce"
    ).fillna(0.0)

    _debug_total_dm = float(
        df_bom_display["Gross Consumption"].sum()
    )

    st.caption(
        f"🔒 **MASTER ENGINE DATA:** "
        f"{len(df_bom_display)} pieces | "
        f"Total Gross DM = **{_debug_total_dm:.4f} Yds**"
    )

    # ---------------------------------------------------------------------
    # 14. SUMMARY GROSS BY MATERIAL CLASS
    # ---------------------------------------------------------------------
    total_fabric = float(
        grouped_gross.get("FABRIC", 0.0)
    )

    total_fusing = float(
        grouped_gross.get("FUSING", 0.0)
    )

    total_lining = float(
        grouped_gross.get("LINING", 0.0)
    )

    total_contrast = float(
        grouped_gross.get("CONTRAST", 0.0)
    )

    total_rib = float(
        grouped_gross.get("RIB", 0.0)
    )

    total_padding = float(
        grouped_gross.get("PADDING", 0.0)
    )

    # ---------------------------------------------------------------------
    # 15. BUILD SUMMARY TABLE
    # ---------------------------------------------------------------------
    summary_data = {
        "Phân loại vật tư": ["VẢI CHÍNH"],
        "Material Class": ["FABRIC"],
        "Gross Consumption": [
            round(total_fabric, 4)
        ],
        "UOM": ["Yds"]
    }

    material_summary_map = [
        ("VẢI PHỐI", "CONTRAST", total_contrast),
        ("MÉC / KEO", "FUSING", total_fusing),
        ("VẢI LÓT", "LINING", total_lining),
        ("BO / RIB", "RIB", total_rib),
        ("GÒN LÓT THÂN", "PADDING", total_padding)
    ]

    for display_name, material_class, value in material_summary_map:

        if value > 0.0:

            summary_data["Phân loại vật tư"].append(
                display_name
            )

            summary_data["Material Class"].append(
                material_class
            )

            summary_data["Gross Consumption"].append(
                round(value, 4)
            )

            summary_data["UOM"].append(
                "Yds"
            )

    # ---------------------------------------------------------------------
    # 16. FINAL SUMMARY UI
    # ---------------------------------------------------------------------
    df_summary = pd.DataFrame(summary_data)

    st.subheader(
        "📊 BẢNG TỔNG HỢP BOM SUMMARY (YARDS)"
    )

    st.dataframe(
        df_summary,
        use_container_width=True,
        hide_index=True
    )
       # =====================================================================
       # =====================================================================
    # 🟩 ĐOẠN 7.2 (VERSION V28.0): BOM EDITOR PIPELINE
    # =====================================================================
    import pandas as pd
    import streamlit as st

    # ---------------------------------------------------------------------
    # 1. RECOVER MASTER DATAFRAME
    # ---------------------------------------------------------------------
    if (
        "active_calculated_df_bom" in st.session_state
        and isinstance(
            st.session_state["active_calculated_df_bom"],
            pd.DataFrame
        )
    ):
        df_bom_display_final = (
            st.session_state["active_calculated_df_bom"].copy()
        )

        # -------------------------------------------------------------
        # 2. SAFE NUMERIC NORMALIZATION
        # -------------------------------------------------------------
        numeric_columns = [
            "Chiều dài rập (inch)",
            "Chiều rộng rập (inch)",
            "polygon_net_area",
            "Gross Consumption",
            "Khổ vải sản xuất (inch)",
            "Số lượng rập"
        ]

        for col in numeric_columns:
            if col in df_bom_display_final.columns:
                df_bom_display_final[col] = pd.to_numeric(
                    df_bom_display_final[col],
                    errors="coerce"
                ).fillna(0.0)

        # -------------------------------------------------------------
        # 3. COMPONENT NAME MASTER
        # -------------------------------------------------------------
        c_name_master = next(
            (
                c
                for c in [
                    "component_name",
                    "Component Name",
                    "Component_Name"
                ]
                if c in df_bom_display_final.columns
            ),
            None
        )

        if c_name_master:
            df_bom_display_final["Component Name"] = (
                df_bom_display_final[c_name_master]
                .astype(str)
                .str.upper()
                .str.strip()
            )
        else:
            df_bom_display_final["Component Name"] = (
                "CHI TIẾT RẬP THÔ"
            )

        # -------------------------------------------------------------
        # 4. SIZE MASTER
        # -------------------------------------------------------------
        current_size = str(
            st.session_state.get(
                "current_active_size",
                st.session_state.get(
                    "target_size",
                    "32"
                )
            )
        ).upper().strip()

        df_bom_display_final["Size tính toán"] = current_size

        # -------------------------------------------------------------
        # 5. MATERIAL CLASS MASTER
        # -------------------------------------------------------------
        if "user_edited_materials" not in st.session_state:
            st.session_state["user_edited_materials"] = {}

        user_edited_materials = st.session_state[
            "user_edited_materials"
        ]

        clean_mats = []

        for idx, row in df_bom_display_final.iterrows():

            idx_str = str(idx).strip()

            if idx in user_edited_materials:
                p_cls = user_edited_materials[idx]

            elif idx_str in user_edited_materials:
                p_cls = user_edited_materials[idx_str]

            else:
                p_cls = row.get(
                    "Material Class",
                    row.get(
                        "material_class",
                        "FABRIC"
                    )
                )

            p_cls = str(
                p_cls
            ).upper().strip()

            if p_cls not in [
                "FABRIC",
                "LINING",
                "FUSING",
                "CONTRAST",
                "RIB",
                "PADDING"
            ]:
                p_cls = "FABRIC"

            clean_mats.append(p_cls)

        df_bom_display_final["Material Class"] = clean_mats

        # -------------------------------------------------------------
        # 6. PHYSICAL MASTER INDEX
        # -------------------------------------------------------------
        df_bom_display_final["Mã Chi Tiết"] = (
            df_bom_display_final.index.astype(str)
        )

        # -------------------------------------------------------------
        # 7. ORDER DISPLAY COLUMNS
        # -------------------------------------------------------------
        ordered_cols = [
            "Mã Chi Tiết",
            "Component Name",
            "Material Class",
            "Chiều dài rập (inch)",
            "Chiều rộng rập (inch)",
            "Khổ vải sản xuất (inch)",
            "Size tính toán",
            "Số lượng rập",
            "polygon_net_area",
            "Gross Consumption"
        ]

        display_final_cols = [
            c
            for c in ordered_cols
            if c in df_bom_display_final.columns
        ]

        df_bom_display_final = (
            df_bom_display_final[display_final_cols]
        )

        # -------------------------------------------------------------
        # 8. BOM EDITOR HEADER
        # -------------------------------------------------------------
        st.subheader(
            "📐 ĐỊNH MỨC CHI TIẾT TỪNG RẬP "
            "VÀ ĐIỀU CHỈNH VẬT TƯ (BOM EDITOR)"
        )

        col_t1, col_t2 = st.columns(2)

        with col_t1:
            st.caption(
                "🟢 **Hướng dẫn:** "
                "Click trực tiếp vào ô **FABRIC** của chi tiết "
                "để đổi sang **LINING**, **FUSING**, **CONTRAST**, "
                "**RIB** hoặc **PADDING**."
            )

        # -------------------------------------------------------------
        # 9. EXCEL EXPORT
        # -------------------------------------------------------------
        with col_t2:

            try:

                if "local_export_excel_ppj_format" in locals():

                    excel_file = local_export_excel_ppj_format(
                        df_summary
                        if "df_summary" in locals()
                        else pd.DataFrame(),

                        df_bom_display_final.drop(
                            columns=["Mã Chi Tiết"],
                            errors="ignore"
                        ),

                        str(
                            ctx.get(
                                "product_category",
                                ctx.get(
                                    "ie_detected_type",
                                    "JEAN"
                                )
                            )
                        ),

                        ctx,

                        float(
                            st.session_state.get(
                                "active_marker_efficiency_value",
                                0.74
                            )
                        )
                    )

                    style_name_clean = str(
                        ctx.get(
                            "style_code",
                            ai_decision_final.get(
                                "style_code",
                                "Style"
                            )
                        )
                    ).strip()

                    style_name_clean = (
                        style_name_clean
                        .replace("/", "_")
                        .replace("\\", "_")
                        .replace(" ", "_")
                    )

                    st.download_button(
                        "🟢 DOWNLOAD EXCEL ĐỊNH MỨC THƯƠNG MẠI",
                        data=excel_file,
                        mime=(
                            "application/vnd.openxmlformats-"
                            "officedocument.spreadsheetml.sheet"
                        ),
                        file_name=(
                            f"PPJ_BOM_{style_name_clean}.xlsx"
                        ),
                        use_container_width=True
                    )

            except Exception:
                pass

        # -------------------------------------------------------------
        # 10. USER EDIT MEMORY
        # -------------------------------------------------------------
        if "user_edited_pieces" not in st.session_state:
            st.session_state["user_edited_pieces"] = {}

        if "user_edited_materials" not in st.session_state:
            st.session_state["user_edited_materials"] = {}

        # -------------------------------------------------------------
        # 11. DATA EDITOR
        # -------------------------------------------------------------
        edited_df = st.data_editor(
            df_bom_display_final,

            key="bom_data_editor_matrix_fixed_v28_0",

            use_container_width=True,

            hide_index=True,

            column_config={

                "Mã Chi Tiết": None,

                "Component Name":
                    st.column_config.TextColumn(
                        "📋 Component Name (Tên Chi Tiết)",
                        disabled=True,
                        width="large"
                    ),

                "Material Class":
                    st.column_config.SelectboxColumn(
                        "🧵 Material Class (Click Chọn Sửa)",

                        options=[
                            "FABRIC",
                            "LINING",
                            "FUSING",
                            "CONTRAST",
                            "RIB",
                            "PADDING"
                        ],

                        required=True,
                        disabled=False,
                        width="medium"
                    ),

                "Chiều dài rập (inch)":
                    st.column_config.NumberColumn(
                        "📏 Chiều dài (inch)",
                        format="%.2f",
                        disabled=True
                    ),

                "Chiều rộng rập (inch)":
                    st.column_config.NumberColumn(
                        "📐 Chiều rộng (inch)",
                        format="%.2f",
                        disabled=True
                    ),

                "Khổ vải sản xuất (inch)":
                    st.column_config.NumberColumn(
                        "Khổ vải (inch)",
                        format="%.1f",
                        disabled=True
                    ),

                "Size tính toán":
                    st.column_config.TextColumn(
                        "Size",
                        disabled=True
                    ),

                "Số lượng rập":
                    st.column_config.NumberColumn(
                        "🔢 Số lượng",
                        format="%d",
                        min_value=1,
                        disabled=False
                    ),

                "polygon_net_area":
                    st.column_config.NumberColumn(
                        "polygon_net_area",
                        format="%.2f",
                        disabled=True
                    ),

                "Gross Consumption":
                    st.column_config.NumberColumn(
                        "Gross Consumption (Yds)",
                        format="%.4f",
                        disabled=True
                    )
            }
        )

        # -------------------------------------------------------------
        # 12. EDIT EVENT LISTENER
        # -------------------------------------------------------------
        editor_key = "bom_data_editor_matrix_fixed_v28_0"

        if (
            edited_df is not None
            and editor_key in st.session_state
        ):

            editor_state = st.session_state[
                editor_key
            ]

            changes = editor_state.get(
                "edited_rows",
                {}
            )

            if changes:

                has_updates = False

                for row_key_str, updated_cols in changes.items():

                    # -------------------------------------------------
                    # SAFETY CHECK: edited_rows dùng POSITIONAL INDEX
                    # -------------------------------------------------
                    try:
                        display_row_position = int(
                            row_key_str
                        )
                    except (
                        TypeError,
                        ValueError
                    ):
                        continue

                    if (
                        display_row_position < 0
                        or display_row_position >= len(
                            df_bom_display_final
                        )
                    ):
                        continue

                    # -------------------------------------------------
                    # TRUY NGƯỢC INDEX GỐC
                    # -------------------------------------------------
                    orig_idx = (
                        df_bom_display_final.index[
                            display_row_position
                        ]
                    )

                    master_target_idx = (
                        df_bom_display_final.at[
                            orig_idx,
                            "Mã Chi Tiết"
                        ]
                    )

                    target_key = str(
                        master_target_idx
                    ).strip()

                    # Nếu index gốc là số nguyên thì giữ integer
                    if target_key.isdigit():
                        target_key = int(target_key)

                    # -------------------------------------------------
                    # USER EDIT PIECE COUNT
                    # -------------------------------------------------
                    if "Số lượng rập" in updated_cols:

                        try:
                            new_pcs = int(
                                float(
                                    updated_cols[
                                        "Số lượng rập"
                                    ]
                                )
                            )

                            new_pcs = max(
                                1,
                                new_pcs
                            )

                            st.session_state[
                                "user_edited_pieces"
                            ][target_key] = new_pcs

                            has_updates = True

                        except (
                            TypeError,
                            ValueError
                        ):
                            pass

                    # -------------------------------------------------
                    # USER EDIT MATERIAL CLASS
                    # -------------------------------------------------
                    if "Material Class" in updated_cols:

                        new_material = str(
                            updated_cols[
                                "Material Class"
                            ]
                        ).upper().strip()

                        allowed_materials = [
                            "FABRIC",
                            "LINING",
                            "FUSING",
                            "CONTRAST",
                            "RIB",
                            "PADDING"
                        ]

                        if new_material in allowed_materials:

                            st.session_state[
                                "user_edited_materials"
                            ][target_key] = (
                                new_material
                            )

                            has_updates = True

                # -----------------------------------------------------
                # 13. RE-TRIGGER MASTER ENGINE
                # -----------------------------------------------------
                if has_updates:

                    st.session_state[
                        "pipeline_auto_run_executed"
                    ] = False

                    st.session_state[
                        "active_calculated_df_bom"
                    ] = edited_df.copy()

                    st.rerun()
