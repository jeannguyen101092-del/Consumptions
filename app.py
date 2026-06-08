import streamlit as st

# Thiết lập cấu hình trang nền sáng High-Contrast cao cấp từ đầu nguồn
st.set_page_config(
    page_title="PPJ Techpack AI - Management System",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ✨ BẢN SỬA LỖI ĐỒ HỌA: Ép trình duyệt hiển thị rõ chữ MAIN DASHBOARD không bị che khuất
st.markdown("""
    <style>
    /* Ép nền ứng dụng màu xám sáng phòng Lab sạch sẽ */
    .stApp { background-color: #F8FAFC !important; }
    
    /* Thiết kế Khung Welcome giữa màn hình */
    .main-box { background: white; padding: 40px; border-radius: 14px; border: 1px solid #E2E8F0; box-shadow: 0 4px 12px rgba(0,0,0,0.02); text-align: center; margin-top: 50px; }
    
    /* 🛠️ BỘ KHÓA ÉP HIỂN THỊ CHỮ: Sửa thuộc tính block để chữ không bị ẩn mất trên Streamlit Cloud */
    [data-testid="stSidebarNav"] ul li:first-child a span {
        visibility: hidden !important;
        position: relative !important;
        display: inline-block !important;
        min-width: 180px !important;
    }
    [data-testid="stSidebarNav"] ul li:first-child a span::after {
        content: "MAIN DASHBOARD" !important;
        visibility: visible !important;
        position: absolute !important;
        left: 0 !important;
        top: 0 !important;
        font-weight: 700 !important;
        color: #1E293B !important;
        letter-spacing: 0.5px !important;
    }
    </style>
""", unsafe_allow_html=True)

# Khung trạng thái hệ thống hiển thị ở Sidebar mặc định
with st.sidebar:
    st.markdown("""
        <div style="background: linear-gradient(135deg, #1E3A8A 0%, #3B82F6 100%); padding: 22px; border-radius: 14px; text-align: center; margin-bottom: 30px; box-shadow: 0 4px 14px rgba(37, 99, 235, 0.2);">
            <div style="font-size: 24px; font-weight: 800; color: #FFFFFF; margin: 0; letter-spacing: 1px;">PPJ GROUP</div>
            <div style="font-size: 11px; color: #BFDBFE; margin-top: 5px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px;">TECHPACK MANAGEMENT CORE AI</div>
        </div>
    """, unsafe_allow_html=True)
    st.success("DATABASE ACCESS: SECURED")
    st.info("ANALYTICS ENGINE: COMPLY")

# Giao diện chào mừng tại trang chủ chính
st.markdown("""
    <div class="main-box">
        <h1 style="color: #1E3A8A !important; font-weight: 800; font-size: 28px;">🏭 PPJ GROUP - TECHPACK CORE AI PLATFORM</h1>
        <p style="color: #64748B; font-size: 15px; margin-top: 10px;">Nền tảng tự động hóa R&D và quản lý hồ sơ kỹ thuật số thông minh tích hợp trí tuệ nhân tạo cấp tập đoàn.</p>
        <div style="background-color: #EFF6FF; border-left: 4px solid #3B82F6; padding: 12px; border-radius: 4px; margin-top: 25px; text-align: left;">
            <p style="font-weight: 600; color: #1E40AF !important; margin: 0;">📋 HƯỚNG DẪN ĐIỀU HÀNH FACTORY:</p>
            <p style="color: #1E3A8A !important; font-size:13.5px; margin: 4px 0 0 0;">Vui lòng lựa chọn các phân hệ tính năng độc lập (SPECIFICATION MATRIX hoặc BOM & CONSUMPTION MATRIX) tại thanh menu Sidebar tự động ở bên trái để bắt đầu làm việc.</p>
        </div>
    </div>
""", unsafe_allow_html=True)
# =============================================================================
# LOGIC KÍCH HOẠT CHẠY FILE DONG_BO_KHO.PY QUA SIDEBAR (ĐÃ VÁ LỖI CĂN LỀ)
# =============================================================================
import dong_bo_kho

st.sidebar.markdown("---")
st.sidebar.subheader("⚙️ Phân hệ Quản trị")

if st.sidebar.button("⚡ Đồng bộ hóa Vector Kho mẫu"):
    # Ép lấy Token bảo mật trực tiếp bên trong khối lệnh nút bấm
    token_chinh_xac = st.secrets.get("GEMINI_API_KEY", "").strip()
    if not token_chinh_xac:
        token_chinh_xac = st.secrets.get("GEMINI_KEY", "").strip()
        
    if token_chinh_xac:
        with st.sidebar.spinner("Đang xử lý số hóa hình ảnh toàn bộ mã cũ..."):
            # THỤT LỀ CHUẨN: Lệnh này chỉ chạy khi nút được bấm thành công
            msg = dong_bo_kho.run_sync(token_chinh_xac, SB_URL, SB_KEY)
            st.sidebar.success(msg)
    else:
        st.sidebar.error("Không tìm thấy cấu hình GEMINI_API_KEY trong bộ Secrets.")
