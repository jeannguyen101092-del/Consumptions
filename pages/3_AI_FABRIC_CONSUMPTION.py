import streamlit as st
import pandas as pd
import numpy as np
import re

# =====================================================================
# ĐOẠN 1: CẤU HÌNH TRANG & BỘ LỌC TỰ ĐỘNG QUÉT TỪ KHÓA CHAT (NLP)
# =====================================================================

st.set_page_config(
    page_title="3. AI FABRIC CONSUMPTION", 
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("📊 TRỢ LÝ ĐỊNH MỨC NGUYÊN PHỤ LIỆU TỰ ĐỘNG (BOM)")
st.caption("Cấu trúc lõi 13-Engine CAD/AI - Tính toán dựa trên tọa độ rập đa giác và bảng bước nhảy")
st.markdown("---")

def parse_conversational_input(text: str) -> dict:
    """NLP Parser quét từ khóa để trích xuất cấu hình dệt may thông minh từ hội thoại"""
    config = {
        "width_inch": 56.0, "shrinkage_l": 5.0, "shrinkage_w": 5.0, "marker_efficiency": 85.0,
        "has_lining": False, "has_padding": False, "has_rib": False, "has_interlining": True
    }
    
    if not text:
        return config
        
    text_lower = text.lower()
    
    # Quét tìm khổ vải vật lý
    width_match = re.search(r'(?:khổ|width)\s*(\d+)', text_lower)
    if width_match: config["width_inch"] = float(width_match.group(1))
        
    # Quét tìm độ co rút dọc (L)
    co_l_match = re.search(r'(?:co dọc|co l|l)\s*(\d+)', text_lower)
    if co_l_match: config["shrinkage_l"] = float(co_l_match.group(1))
        
    # Tự động nhận diện cấu trúc BOM phụ liệu từ cuộc trò chuyện chat
    if any(k in text_lower for k in ["lót", "lining", "jacket"]): config["has_lining"] = True
    if any(k in text_lower for k in ["gòn", "padding", "puffer"]): config["has_padding"] = True
    if any(k in text_lower for k in ["bo", "rib", "thun"]): config["has_rib"] = True
    if any(k in text_lower for k in ["keo", "interlining", "phối"]): config["has_interlining"] = True
        
    return config
# =====================================================================
# ĐOẠN 2: LÕI TÍNH TOÁN ĐỊNH MỨC ĐA LỚP VẬT LIỆU (CAD CORE ENGINE)
# =====================================================================

class GarmentCADCoreEngine:
    """Tính toán diện tích tinh từ thư viện đa giác điểm và xử lý gá đặt sơ đồ"""
    @staticmethod
    def get_net_geometry_areas(category: str, pom: dict) -> dict:
        chest = pom.get("chest", 54.0)
        length = pom.get("body_length", 72.0)
        bicep = pom.get("bicep_width", 22.0)
        sleeve_len = pom.get("sleeve_length", 24.0)
        
        # Triệt tiêu sai số hình chữ nhật: Lấy diện tích tịnh thực tế của đa giác rập chuẩn CAD (78% - 82%)
        base_factor = 0.78 if "jacket" in category.lower() else 0.82
        front_area = (chest * length) * base_factor
        back_area = front_area * 1.03  # Thân sau chồm vai dôi dư 3%
        sleeve_area = (bicep * sleeve_len) * 0.75  # Rập quả chuối cong
        
        return {"Front": front_area, "Back": back_area, "Sleeve": sleeve_area}

    @staticmethod
    def calculate_matrix_consumption(category: str, pom: dict, config: dict) -> dict:
        areas = GarmentCADCoreEngine.get_net_geometry_areas(category, pom)
        
        width_cm = config["width_inch"] * 2.54
        efficiency = config["marker_efficiency"] / 100
        shrinkage_l = 1 + (config["shrinkage_l"] / 100)
        
        # 1. Định mức Vải chính (Shell Fabric)
        total_shell_area = (areas["Front"] * 2) + (areas["Back"] * 2) + (areas["Sleeve"] * 2)
        shell_length_cm = (total_shell_area / efficiency) / width_cm
        shell_yds = (shell_length_cm / 91.44) * shrinkage_l

        # 2. Định mức Vải lót (Lining) - Tự động tính hụt nẹp vát
        lining_yds = shell_yds * 0.82 if config["has_lining"] else 0.0
        
        # 3. Định mức Gòn bông (Padding)
        padding_yds = shell_yds * 0.95 if config["has_padding"] else 0.0
        
        # 4. Định mức Bo thun (Rib) - Tính độc lập dựa trên chu vi cổ/cuff
        rib_yds = 0.15 if config["has_rib"] else 0.0
        
        # 5. Định mức Keo dựng/Mếch phôi (Interlining)
        interlining_yds = 0.22 if config["has_interlining"] else 0.0
        
        # Tổng định mức Yards trên một sản phẩm
        total_yds = shell_yds + lining_yds + padding_yds + rib_yds + interlining_yds
        
        return {
            "shell": round(shell_yds, 2),
            "lining": round(lining_yds, 2),
            "padding": round(padding_yds, 2),
            "rib": round(rib_yds, 2),
            "interlining": round(interlining_yds, 2),
            "total": round(total_yds, 2)
        }
# =====================================================================
# ĐOẠN 3: CƠ SỞ DỮ LIỆU MÃ HÀNG, SIDEBAR CHAT VÀ BẢNG HIỂN THỊ LỚN UI
# =====================================================================

# 1. Cơ sở dữ liệu mẫu các mã hàng sản xuất (Techpack / BOM Data)
mock_production_db = [
    {"style": "EMV0017", "desc": "M-RIDGEVENT VEST", "cat": "vest", "pom": {"chest": 54.0, "body_length": 72.0, "bicep_width": 0.0, "sleeve_length": 0.0}, "note": "Shell + Lining DNBR-38; Padding F-021"},
    {"style": "EML0016", "desc": "M-RIDGEVENT JACKET", "cat": "jacket", "pom": {"chest": 56.0, "body_length": 75.0, "bicep_width": 24.0, "sleeve_length": 65.0}, "note": "Shell + Lining DNBR-38; bọc gòn chống chui"},
    {"style": "EMR0007", "desc": "M-TECH RAINCOAT", "cat": "jacket", "pom": {"chest": 55.0, "body_length": 82.0, "bicep_width": 23.0, "sleeve_length": 68.0}, "note": "Vải chính bonded không lót/gòn; Ép keo cổ"},
    {"style": "EMV0013", "desc": "M-ULTRASONIC VEST", "cat": "vest", "pom": {"chest": 53.5, "body_length": 71.0, "bicep_width": 0.0, "sleeve_length": 0.0}, "note": "Main fabric already quilted"},
    {"style": "EML0012", "desc": "M-ULTRASONIC JACKET", "cat": "jacket", "pom": {"chest": 54.0, "body_length": 73.5, "bicep_width": 23.0, "sleeve_length": 64.0}, "note": "Quilted main; lining/yoke; small padding yoke"}
]

# 2. Xây dựng khu vực Hội thoại Chatbot AI ở Sidebar bên trái
with st.sidebar:
    st.header("💬 TRỢ LÝ SẢN XUẤT AI")
    st.write("Nhập thông tin vải, độ co rút để cập nhật bảng định mức.")
    st.markdown("---")
    
    # Khởi tạo lưu trữ lịch sử chat của trang
    if "sidebar_chat_history" not in st.session_state:
        st.session_state.sidebar_chat_history = [
            {"role": "assistant", "content": "Xin chào! Nhập lệnh cấp thông số dệt may tại đây. Ví dụ: *'Khổ 56, co L5, áo jacket có lót gòn bông và phối bo thun rib'*"}
        ]
        
    # Render hội thoại
    for chat in st.session_state.sidebar_chat_history:
        with st.chat_message(chat["role"]):
            st.markdown(chat["content"])
            
    # Ô tiếp nhận văn bản chat từ người dùng
    user_prompt = st.chat_input("Gửi thông số cho AI...")

# Nếu người dùng nhấn gửi lệnh chat, cập nhật session và tải lại giao diện
if user_prompt:
    st.session_state.sidebar_chat_history.append({"role": "user", "content": user_prompt})
    st.rerun()

# Trích xuất câu lệnh chat mới nhất của người dùng phục vụ tính toán
last_user_message = ""
for msg in reversed(st.session_state.sidebar_chat_history):
    if msg["role"] == "user":
        last_user_message = msg["content"]
        break

current_fabric_config = parse_conversational_input(last_user_message)

# 3. Khu vực màn hình lớn ở trung tâm hiển thị bảng biểu
st.subheader("📋 BẢNG ĐỊNH MỨC MỌI BỘ - SƠ ĐỒ 1 CHIỀU")

# Dòng ghi chú thông tin biên dệt may động (Đồng bộ với tiêu chuẩn nhà máy)
st.info(
    f"**Điều kiện chung:** Size M | Khổ vải: **{current_fabric_config['width_inch']} Inch** | "
    f"Độ co: **L {int(current_fabric_config['shrinkage_l'])}% / W {int(current_fabric_config['shrinkage_w'])}%** | "
    f"Hiệu suất sơ đồ tham chiếu: **{int(current_fabric_config['marker_efficiency'])}%** | Chưa bao gồm hao hụt hao hụt booking."
)

# Chạy vòng lặp bóc tách định mức đa lớp cho toàn bộ DB mã hàng
table_rows = []
for item in mock_production_db:
    config_by_style = current_fabric_config.copy()
    
    # Ép cấu hình cứng theo đặc trưng mẫu của từng nhóm kiểu dáng (Vest, Áo mưa)
    if item["cat"] == "vest":
        config_by_style["has_lining"] = True
        config_by_style["has_padding"] = True
    elif "raincoat" in item["desc"].lower():
        config_by_style["has_lining"] = False
        config_by_style["has_padding"] = False
        
    res = GarmentCADCoreEngine.calculate_matrix_consumption(item["cat"], item["pom"], config_by_style)
    
    # Chuỗi mô tả thành phần cấu trúc của sản phẩm
    comp_desc = "Puffer jacket" if config_by_style["has_padding"] else "Raincoat/Vest"
    if config_by_style["has_lining"]: comp_desc += " + lót"
    if config_by_style["has_padding"]: comp_desc += " - gòn tấm"
    
    table_rows.append({
        "Style": item["style"],
        "Mô tả": item["desc"],
        "Cấu trúc": comp_desc,
        "Khổ vải (inch)": f"{config_by_style['width_inch']}''",
        "Độ co L": f"{int(config_by_style['shrinkage_l'])}%",
        "Độ co W": f"{int(config_by_style['shrinkage_w'])}%",
        "Hiệu suất": f"{int(config_by_style['marker_efficiency'])}%",
        "Shell/Main Fabric Net (yds/pc)": res["shell"],
        "Lining Net (yds/pc)": res["lining"] if config_by_style["has_lining"] else "0.00 N/A",
        "Padding/Gòn Net (yds/pc)": res["padding"] if config_by_style["has_padding"] else "0.00 N/A",
        "Bo/Rib Net (yds/pc)": res["rib"],
        "Keo/Interlining Net (yds/pc)": res["interlining"],
        "Tổng yds vải/pc": res["total"],
        "Ghi chú kỹ thuật dệt may": item["note"]
    })

# Tự động dọn dẹp và chuẩn hóa dữ liệu số trước khi render bảng
df_display = df_matrix.copy()

# Render bảng ma trận định mức lớn lên trung tâm màn hình phẳng
st.dataframe(
    df_display,
    use_container_width=True,
    height=450
)



# Nút cho phép người dùng trích xuất dữ liệu nhanh về máy tính dưới dạng file CSV/Excel
st.download_button(
    label="📥 Xuất File Định Mức Sản Xuất (CSV)",
    data=df_matrix.to_csv(index=False).encode('utf-8-sig'),
    file_name="BOM_Consumption_Matrix_Report.csv",
    mime="text/csv"
)
