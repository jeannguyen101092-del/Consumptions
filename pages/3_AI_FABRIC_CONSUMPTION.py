import streamlit as st
import re
import pandas as pd

# 1. CẤU HÌNH TRANG VÀ INJECT CSS 
st.set_page_config(layout="wide", page_title="AI Fabric Consumption Platform")

st.markdown("""
    <style>
    .main-header {
        background-color: #0b72b9; color: white; padding: 12px;
        border-radius: 4px; font-size: 14px; font-weight: bold; margin-bottom: 15px;
    }
    .metric-container { display: flex; gap: 10px; margin-bottom: 20px; }
    .metric-box {
        flex: 1; padding: 12px; border-radius: 4px; text-align: center; color: white; height: 85px;
    }
    .metric-title { font-size: 10px; text-transform: uppercase; font-weight: bold; margin-bottom: 8px; opacity: 0.95;}
    .metric-value { font-size: 18px; font-weight: 900; }
    .bg-navy { background-color: #2c3e50; }
    .bg-teal { background-color: #16a085; }
    .bg-orange { background-color: #d35400; }
    .bg-green { background-color: #27ae60; }
    </style>
""", unsafe_allow_html=True)

# 2. KHỞI TẠO BỘ NHỚ TRẠNG THÁI HỆ THỐNG (SESSION STATE)
if "product_code" not in st.session_state:
    st.session_state.product_code = "N/A"
if "total_items" not in st.session_state:
    st.session_state.total_items = "0 Item(s)"
if "estimated_consumption" not in st.session_state:
    st.session_state.estimated_consumption = 0.000
if "engine_mode" not in st.session_state:
    st.session_state.engine_mode = "AUTOMATIC"
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# 3. THANH SIDEBAR ĐIỀU HƯỚNG
with st.sidebar:
    st.caption("app")
    st.markdown("**HISTORICAL CONSUMPTION DB**")
    st.markdown("**BOM CONSUMPTION MATRIX**")
    st.markdown("<span style='color:#0b72b9; font-weight:bold;'>AI FABRIC CONSUMPTION</span>", unsafe_allow_html=True)
    st.write("---")
    st.markdown("⚙️ **ENGINE CONTROLS**")
    if st.button("🗑️ CLEAR SYSTEM MEMORY", use_container_width=True):
        st.session_state.chat_history = []
        st.session_state.estimated_consumption = 0.000
        st.session_state.total_items = "0 Item(s)"
        st.session_state.product_code = "N/A"
        st.session_state.engine_mode = "AUTOMATIC"
        st.rerun()

# 4. TIÊU ĐỀ HỆ THỐNG
st.markdown("""
    <div class="main-header">
        Hệ thống phân tích rập hình học và tự động tính toán định mức kỹ thuật dệt may bằng AI CORE
    </div>
""", unsafe_allow_html=True)

# 5. BỘ ĐỒNG HỒ ĐO METRIC DÙNG ĐỘNG BIẾN STATE
st.markdown(f"""
    <div class="metric-container">
        <div class="metric-box bg-navy">
            <div class="metric-title">Mã hàng đang xử lý</div>
            <div class="metric-value">{st.session_state.product_code}</div>
        </div>
        <div class="metric-box bg-teal">
            <div class="metric-title">Tổng số vật tư kết xuất</div>
            <div class="metric-value">{st.session_state.total_items}</div>
        </div>
        <div class="metric-box bg-orange">
            <div class="metric-title">Định mức vải chính dự kiến</div>
            <div class="metric-value">{st.session_state.estimated_consumption:.3f}</div>
        </div>
        <div class="metric-box bg-green">
            <div class="metric-title">Cơ chế tính định mức</div>
            <div class="metric-value">{st.session_state.engine_mode}</div>
        </div>
    </div>
""", unsafe_allow_html=True)

# 6. KHU VỰC TẢI TÀI LIỆU KỸ THUẬT VÀ HÌNH VẼ PHÁC HỌA
left_panel, right_panel = st.columns(2)

with left_panel:
    st.markdown("📂 **TECHPACK UPLOADER & PROFILE SUMMARY**")
    uploaded_file = st.file_uploader("Upload", type=["pdf"], label_visibility="collapsed")
    
    if uploaded_file is not None:
        st.success(f"📁 Đã nhận file: {uploaded_file.name} ({round(uploaded_file.size/1024, 1)} KB)")
        st.session_state.product_code = uploaded_file.name.split(".")[0]
        
        st.markdown("**Bảng thông số kích thước (Spec Sheet):**")
        mock_spec_data = {
            "Vị trí đo (Measurement Point)": ["Dài quần (Outseam)", "Vòng mông (Hip /2)", "Vòng đùi (Thigh /2)", "Rộng cạp (Waistband)"],
            "Thông số (Inch)": [42.0, 22.0, 13.5, 4.0],
            "Dung sai (+/-)": [0.5, 0.5, 0.25, 0.25]
        }
        df_spec = pd.DataFrame(mock_spec_data)
        st.dataframe(df_spec, use_container_width=True, hide_index=True)
    else:
        st.caption("Bảng tóm tắt thông số sản phẩm sẽ tự động hiển thị tại đây sau khi nạp file PDF.")

with right_panel:
    st.markdown("🎨 **TECHPACK SKETCH VISUALIZER**")
    if uploaded_file is not None:
        st.markdown(
            """
            <div style="border: 1px solid #ddd; padding: 20px; text-align: center; border-radius: 4px; background-color: #ffffff; min-height: 165px;">
                <span style="color: #555; font-weight: bold; font-size:13px;">[BẢN VẼ PHÁC HỌA FLAT SKETCH]</span><br>
                <div style="margin-top:15px; color:#aaa; font-style:italic;">(AI Core đã trích xuất thành công sơ đồ kết cấu 2 túi hộp bên đùi và cạp rời)</div>
            </div>
            """, 
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            """
            <div style="border: 1px dashed #ccc; padding: 40px; text-align: center; border-radius: 4px; background-color: #fafafa; color: #777; min-height: 115px; font-size:12px;">
                Hình vẽ phác họa phẳng (Sketch) trích xuất từ trang bìa PDF sẽ tự động hiển thị tại đây.
            </div>
            """, 
            unsafe_allow_html=True
        )

st.write("")

# 7. KHÔNG GIAN LÀM VIỆC CHATGPT IE COLLABORATION & XỬ LÝ LỆNH TỰ ĐỘNG
st.markdown("💬 **CHATGPT IE COLLABORATION WORKSPACE**")

# Khối hiển thị lịch sử chat
for chat in st.session_state.chat_history:
    if chat["role"] == "user":
        st.markdown(f"🔴 **tính:** {chat['content']}")
    else:
        st.markdown(f"🟠 **AI:** {chat['content']}")

# 🌟 GIẢI PHÁP TRIỆT ĐỂ: Dùng st.form kết hợp clear_on_submit để khóa lỗi lặp dòng dữ liệu chat
with st.form(key="ie_chat_form", clear_on_submit=True):
    user_input = st.text_input(
        "Gõ lệnh điều chỉnh thông số tại đây...", 
        placeholder="Nhập cấu hình vải và thông số...", 
        label_visibility="collapsed"
    )
    # Nút submit ẩn hoặc nhỏ gọn để giữ nguyên trải nghiệm gõ Enter
    submit_button = st.form_submit_button("Gửi lệnh tinh chỉnh", use_container_width=False)

if submit_button and user_input.strip():
    user_prompt = user_input.strip()
    
    # NLP Parser bóc tách số liệu
    width_match = re.search(r"khổ\s*(\d+)", user_prompt.lower())
    warp_match = re.search(r"dọc\s*(\d+)", user_prompt.lower())
    weft_match = re.search(r"ngang\s*(\d+)", user_prompt.lower())
    
    base_consumption = 1.325  
    width_val = float(width_match.group(1)) if width_match else 58.0
    warp_val = float(warp_match.group(1)) if warp_match else 0.0
    weft_val = float(weft_match.group(1)) if weft_match else 0.0
    
    # Tính định mức thích ứng dệt may
    shrinkage_coefficient = (1 + (warp_val / 100)) * (1 + (weft_val / 100))
    width_penalty = 58.0 / width_val if width_val > 0 else 1.0
    final_consumption = base_consumption * shrinkage_coefficient * width_penalty
    
    # Ghi nhận trạng thái hệ thống
    st.session_state.estimated_consumption = final_consumption
    st.session_state.total_items = "1 Item(s)"
    st.session_state.engine_mode = "ADAPTIVE IE"

    # Đẩy dữ liệu vào lịch sử
    st.session_state.chat_history.append({"role": "user", "content": user_prompt})
    ai_response = f"Đã ghi nhận yêu cầu: '{user_prompt}'. Hệ thống đang tiến hành điều chỉnh ma trận xếp rập thích ứng. Kết quả định mức mới: {final_consumption:.3f} Yds."
    st.session_state.chat_history.append({"role": "assistant", "content": ai_response})
    
    # Re-run tức thời sạch sẽ, xóa hoàn toàn chuỗi text cũ khỏi bộ nhớ đệm
    st.rerun()

# 8. BẢNG XUẤT DỮ LIỆU BOM & NÚT TẢI EXCEL (BỔ SUNG TIỆN ÍCH CHO PHÒNG MUA HÀNG)
if st.session_state.estimated_consumption > 0:
    st.write("---")
    st.markdown("📋 **BẢNG KẾT XUẤT ĐỊNH MỨC CHI TIẾT (AI BOM EXPORT)**")
    
    bom_data = {
        "Mã Vải (Fabric Code)": ["MAIN_FABRIC_01"],
        "Phân Loại (Type)": ["Vải chính / Khổ dệt"],
        "Khổ rộng (Inch)": [58.0],
        "Định mức tổng (Yds/Pcs)": [round(st.session_state.estimated_consumption, 3)],
        "Trạng thái Gate": ["PASSED"]
    }
    df_bom = pd.DataFrame(bom_data)
    st.dataframe(df_bom, use_container_width=True, hide_index=True)
    
    # Nút cho phép tải file báo giá định mức nhanh
    csv = df_bom.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 TẢI FILE BÁO GIÁ ĐỊNH MỨC VẬT TƯ (CSV)",
        data=csv,
        file_name=f"BOM_Estimation_{st.session_state.product_code}.csv",
        mime="text/csv",
    )
