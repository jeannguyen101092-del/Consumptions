import streamlit as st

# BẮT BUỘC: Cấu hình trang phải nằm đầu tiên trong file app.py ngoài cùng
st.set_page_config(
    page_title="PPJ Techpack AI - Management System",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Nhúng cấu hình giao diện Sáng chuyên nghiệp, tương phản cao toàn hệ thống
st.markdown("""
    <style>
    /* Ép toàn bộ nền ứng dụng về màu xám trắng phòng thí nghiệm sạch sẽ */
    .stApp { background-color: #F8FAFC !important; }
    
    /* Thiết kế thanh điều hướng Sidebar màu trắng tinh, có đường chia rõ ràng */
    [data-testid="stSidebar"] { 
        background-color: #FFFFFF !important; 
        border-right: 1px solid #CBD5E1 !important;
        min-width: 320px; 
    }
    
    /* Khung thương hiệu PPJ Group hiệu ứng Gradient cao cấp */
    .sidebar-brand-container {
        background: linear-gradient(135deg, #1E3A8A 0%, #3B82F6 100%);
        padding: 22px; border-radius: 14px; text-align: center; margin-bottom: 30px;
        box-shadow: 0 4px 14px rgba(37, 99, 235, 0.2);
    }
    .sidebar-brand-title { font-size: 24px; font-weight: 800; color: #FFFFFF; margin: 0; letter-spacing: 1px; }
    .sidebar-brand-subtitle { font-size: 11px; color: #BFDBFE; margin-top: 5px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; }
    
    /* Thiết kế Container giới thiệu */
    .main-box { background: white; padding: 40px; border-radius: 14px; border: 1px solid #E2E8F0; box-shadow: 0 4px 6px rgba(0,0,0,0.02); text-align: center; margin-top: 50px; }
    h1 { color: #1E3A8A !important; font-weight: 800; }
    p { color: #64748B !important; font-size: 15px; }
    </style>
""", unsafe_allow_html=True)

# Khung nhận diện Logo cố định trên thanh Menu Sidebar của tất cả các trang
with st.sidebar:
    st.markdown("""
        <div class="sidebar-brand-container">
            <div class="sidebar-brand-title">PPJ GROUP</div>
            <div class="sidebar-brand-subtitle">TECHPACK ENGINE CORE AI</div>
        </div>
    """, unsafe_allow_html=True)
    st.success("DATABASE ACCESS: SECURED")
    st.info("ANALYTICS ENGINE: COMPLY")

# Nội dung hiển thị vùng trung tâm trang chủ
st.markdown("""
    <div class="main-box">
        <h1>🏭 PPJ GROUP - TECHPACK CORE AI SYSTEMS</h1>
        <p>Hệ thống tự động hóa R&D, đối chiếu hình học rập mẫu và bóc tách cấu trúc BOM dệt may tích hợp mạng nơ-ron đa tầng.</p>
        <p style="font-weight: 600; color: #2563EB !important; margin-top: 20px;">👈 Vui lòng chọn các phân hệ kỹ thuật chuyên ngành ở thanh điều hướng Sidebar bên trái để làm việc.</p>
    </div>
""", unsafe_allow_html=True)
