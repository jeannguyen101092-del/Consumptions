import streamlit as st
import numpy as np
import copy

# 1. CẤU HÌNH TRANG & CSS TÙY BIẾN (MATCH GIAO DIỆN MẪU)
st.set_page_config(layout="wide", page_title="AI Fabric Consumption Platform")

# Inject CSS để ép giao diện có tông màu và bo góc giống hệt ảnh mẫu
st.markdown("""
    <style>
    .main-header {
        background-color: #0b72b9;
        color: white;
        padding: 15px;
        border-radius: 5px;
        font-size: 22px;
        font-weight: bold;
        margin-bottom: 20px;
    }
    .sub-header {
        font-size: 13px;
        font-weight: normal;
        color: #e0e0e0;
    }
    .metric-box {
        padding: 15px;
        border-radius: 5px;
        text-align: center;
        color: white;
        font-weight: bold;
        height: 100px;
    }
    .metric-title { font-size: 11px; text-transform: uppercase; opacity: 0.9; margin-bottom: 5px;}
    .metric-value { font-size: 20px; font-weight: 900; }
    
    /* Màu sắc các khối kịch bản */
    .bg-navy { background-color: #2b3e50; }
    .bg-teal { background-color: #008b8b; }
    .bg-orange { background-color: #d35400; }
    .bg-green { background-color: #27ae60; }
    </style>
""", unsafe_allow_html=True)

# 2. THANH SIDEBAR (ĐIỀU HƯỚNG & ENGINE CONTROLS)
with st.sidebar:
    st.caption("app")
    st.markdown("**HISTORICAL CONSUMPTION DB**")
    st.markdown("**BOM CONSUMPTION MATRIX**")
    st.markdown("<span style='color:#0b72b9; font-weight:bold;'>AI FABRIC CONSUMPTION</span>", unsafe_allow_html=True)
    
    st.write("---")
    st.markdown("⚙️ **ENGINE CONTROLS**")
    if st.button("🗑️ CLEAR SYSTEM MEMORY", use_container_width=True):
        st.session_state.clear()
        st.success("Đã xóa bộ nhớ đệm hệ thống!")

# 3. TIÊU ĐỀ CHÍNH (MAIN HEADER CONTAINER)
st.markdown("""
    <div class="main-header">
        📊 INTELLIGENT FABRIC CONSUMPTION PLATFORM
        <div class="sub-header">Hệ thống phân tích rập hình học và tự động tính toán định mức kỹ thuật dệt may bằng AI CORE</div>
    </div>
""", unsafe_allow_html=True)

# 4. KHỐI METRIC ĐỒNG HỒ ĐO (TOP KANBAN METRICS)
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown('<div class="metric-box bg-navy"><div class="metric-title">Mã hàng đang xử lý</div><div class="metric-value">N/A</div></div>', unsafe_allow_html=True)
with col2:
    st.markdown('<div class="metric-box bg-teal"><div class="metric-title">Tổng số vật tư kết xuất</div><div class="metric-value">0 Item(s)</div></div>', unsafe_allow_html=True)
with col3:
    st.markdown('<div class="metric-box bg-orange"><div class="metric-title">Định mức vải chính dự kiến</div><div class="metric-value">0.000</div></div>', unsafe_allow_html=True)
with col4:
    st.markdown('<div class="metric-box bg-green"><div class="metric-title">Cơ chế tính định mức</div><div class="metric-value">AUTOMATIC</div></div>', unsafe_allow_html=True)

st.write("") # Tạo khoảng cách dòng

# 5. KHU VỰC TẢI TECHPACK & HIỂN THỊ SKETCH (HAI CỘT CHÍNH)
left_panel, right_panel = st.columns(2)

with left_panel:
    st.markdown("📂 **TECHPACK UPLOADER & PROFILE SUMMARY**")
    uploaded_file = st.file_uploader(
        "Kéo thả hoặc chọn file PDF Techpack vào đây...", 
        type=["pdf"], 
        label_visibility="collapsed"
    )
    
    if uploaded_file is not None:
        st.info(f"📁 Đã nhận file: **{uploaded_file.name}** ({round(uploaded_file.size/1024, 1)} KB)")
        # Giả lập khu vực bóc tách dữ liệu bảng thông số (Spec sheet dataframe) sau khi up file
        st.write("---")
        st.caption("Bảng tóm tắt thông số sản phẩm sẽ tự động hiển thị tại đây sau khi nạp file PDF.")
    else:
        st.info("Bảng tóm tắt thông số sản phẩm sẽ tự động hiển thị tại đây sau khi nạp file PDF.")

with right_panel:
    st.markdown("🎨 **TECHPACK SKETCH VISUALIZER**")
    # Khung giả lập chứa ảnh vẽ kĩ thuật (Sketch) trích xuất từ trang bìa PDF
    st.markdown(
        """
        <div style="border: 1px dashed #ccc; padding: 40px; text-align: center; border-radius: 5px; background-color: #fafafa; color: #777; min-height: 150px;">
            Hình vẽ phác họa phẳng (Sketch) trích xuất từ trang bìa PDF sẽ tự động hiển thị tại đây.
        </div>
        """, 
        unsafe_allow_html=True
    )

st.write("") 

# 6. KHÔNG GIAN LÀM VIỆC CHATGPT IE COLLABORATION (DƯỚI CÙNG)
st.markdown("💬 **CHATGPT IE COLLABORATION WORKSPACE**")
user_prompt = st.text_input(
    "Gõ lệnh điều chỉnh thông số tại đây...", 
    placeholder="Ví dụ: 'Ép hiệu suất sơ đồ lên 88%' hoặc 'Thay đổi độ co rút vải dọc thành 5%'...",
    label_visibility="collapsed"
)

if user_prompt:
    st.chat_message("user").write(user_prompt)
    with st.spinner("AI Engine đang tính toán lại sơ đồ hình học..."):
        # Phản hồi giả lập từ lõi IE dựa trên prompt tinh chỉnh của kỹ sư
        st.chat_message("assistant").write(f"Đã ghi nhận yêu cầu: '{user_prompt}'. Hệ thống đang tiến hành điều chỉnh ma trận xếp rập thích ứng.")
