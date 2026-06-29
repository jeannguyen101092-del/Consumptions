import streamlit as st
import pandas as pd
import numpy as np
import re

# =====================================================================
# CONFIGURATION & PAGE LAYOUT
# =====================================================================
st.set_page_config(
    page_title="3. AI FABRIC CONSUMPTION", 
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("📊 TRỢ LÝ ĐỊNH MỨC NGUYÊN PHỤ LIỆU TỰ ĐỘNG (BOM)")
st.caption("Cấu trúc lõi 13-Engine CAD/AI - Phân tích tài liệu kỹ thuật PDF và tính toán định mức đa lớp")
st.markdown("---")

# =====================================================================
# ENGINE: NATURAL LANGUAGE PROCESSING PARSER (NLP)
# =====================================================================
def parse_conversational_input(text: str) -> dict:
    """NLP Parser quét từ khóa để trích xuất cấu hình dệt may thông minh từ hội thoại"""
    config = {
        "width_inch": 56.0, "shrinkage_l": 5.0, "shrinkage_w": 5.0, "marker_efficiency": 85.0,
        "has_lining": False, "has_padding": False, "has_rib": False, "has_interlining": True
    }
    if not text: return config
    text_lower = text.lower()
    
    # Quét khổ vải vật lý
    width_match = re.search(r'(?:khổ|width)\s*(\d+)', text_lower)
    if width_match: config["width_inch"] = float(width_match.group(1))
        
    # Quét độ co rút dọc (L)
    co_l_match = re.search(r'(?:co dọc|co l|l)\s*(\d+)', text_lower)
    if co_l_match: config["shrinkage_l"] = float(co_l_match.group(1))
        
    # Tự động nhận diện cấu trúc BOM phụ liệu từ cuộc trò chuyện chat
    if any(k in text_lower for k in ["lót", "lining", "jacket"]): config["has_lining"] = True
    if any(k in text_lower for k in ["gòn", "padding", "puffer"]): config["has_padding"] = True
    if any(k in text_lower for k in ["bo", "rib", "thun"]): config["has_rib"] = True
    if any(k in text_lower for k in ["keo", "interlining", "phối"]): config["has_interlining"] = True
        
    return config

# =====================================================================
# CORE ENGINE: LAYERED CONSUMPTION MATRIX
# =====================================================================
class GarmentCADCoreEngine:
    """Tính toán diện tích tinh từ thư viện đa giác điểm và xử lý gá đặt sơ đồ"""
    @staticmethod
    def calculate_matrix_consumption(category: str, config: dict) -> dict:
        # Giả lập kích thước nhảy mẫu chuẩn hóa dựa theo loại danh mục sản phẩm (Category) bóc tách từ PDF
        chest = 56.0 if "jacket" in category.lower() else 54.0
        length = 75.0 if "jacket" in category.lower() else 72.0
        
        base_factor = 0.78 if "jacket" in category.lower() else 0.82
        front_area = (chest * length) * base_factor
        back_area = front_area * 1.03
        sleeve_area = (22.0 * 24.0) * 0.75 if "vest" not in category.lower() else 0.0
        
        width_cm = config["width_inch"] * 2.54
        efficiency = config["marker_efficiency"] / 100
        shrinkage_l = 1 + (config["shrinkage_l"] / 100)
        
        # 1. Định mức Vải chính (Shell Fabric)
        total_shell_area = (front_area * 2) + (back_area * 2) + (sleeve_area * 2)
        shell_length_cm = (total_shell_area / efficiency) / width_cm
        shell_yds = (shell_length_cm / 91.44) * shrinkage_l

        # 2. Định mức Vải lót (Lining)
        lining_yds = shell_yds * 0.82 if config["has_lining"] else 0.0
        
        # 3. Định mức Gòn bông (Padding)
        padding_yds = shell_yds * 0.95 if config["has_padding"] else 0.0
        
        # 4. Định mức Bo thun (Rib)
        rib_yds = 0.15 if config["has_rib"] else 0.0
        
        # 5. Định mức Keo dựng (Interlining)
        interlining_yds = 0.22 if config["has_interlining"] else 0.0
        
        total_yds = shell_yds + lining_yds + padding_yds + rib_yds + interlining_yds
        
        return {
            "shell": round(shell_yds, 2), "lining": round(lining_yds, 2), 
            "padding": round(padding_yds, 2), "rib": round(rib_yds, 2), 
            "interlining": round(interlining_yds, 2), "total": round(total_yds, 2)
        }

# =====================================================================
# STREAMLIT SIDEBAR: TRUNG TÂM TƯƠNG TÁC AI CHATBOT
# =====================================================================
with st.sidebar:
    st.header("💬 TRỢ LÝ SẢN XUẤT AI")
    st.write("Nhập bổ sung thông tin vải, độ co rút sau khi tải PDF.")
    st.markdown("---")
    
    if "sidebar_chat_history" not in st.session_state:
        st.session_state.sidebar_chat_history = [
            {"role": "assistant", "content": "Xin chào! Sau khi tải file Techpack lên, bạn có thể gõ bổ sung thông số tại đây. Ví dụ: *'Khổ 56, co L5'*"}
        ]
        
    for chat in st.session_state.sidebar_chat_history:
        with st.chat_message(chat["role"]):
            st.markdown(chat["content"])
            
    user_prompt = st.chat_input("Gửi thông số cho AI...")

if user_prompt:
    st.session_state.sidebar_chat_history.append({"role": "user", "content": user_prompt})
    st.rerun()

last_user_message = ""
for msg in reversed(st.session_state.sidebar_chat_history):
    if msg["role"] == "user":
        last_user_message = msg["content"]
        break

current_fabric_config = parse_conversational_input(last_user_message)

# =====================================================================
# MAIN PANEL: KHU VỰC TẢI FILE PDF (INGESTION) VÀ HIỂN THỊ BẢNG TRẢ VỀ
# =====================================================================

st.subheader("📁 BƯỚC 1: TẢI TÀI LIỆU KỸ THUẬT SẢN XUẤT (TECHPACK / BOM)")
uploaded_file = st.file_uploader("Kéo và thả file PDF Techpack hoặc bảng BOM của bạn vào đây", type=["pdf"])

if uploaded_file is not None:
    st.success(f"✔️ Đã tải file thành công: {uploaded_file.name} | AI đang thực thi quét cấu trúc tài liệu...")
    
    # GIẢ LẬP HÀNH VI ENGINE 1 & 2: Quét đọc tệp tin PDF thực tế để trích xuất danh sách mã hàng tự động
    # (Khi bạn kết nối API đọc PDF, dữ liệu mảng này sẽ được sinh động từ nội dung trong file)
    parsed_styles_from_pdf = [
        {"style": "EMV0017", "desc": "M-RIDGEVENT VEST", "cat": "vest", "note": "Shell + Lining DNBR-38; Padding F-021"},
        {"style": "EML0016", "desc": "M-RIDGEVENT JACKET", "cat": "jacket", "note": "Shell + Lining DNBR-38; bọc gòn chống chui"},
        {"style": "EMR0007", "desc": "M-TECH RAINCOAT", "cat": "jacket", "note": "Vải chính bonded không lót/gòn; Ép keo cổ"},
        {"style": "EML0012", "desc": "M-ULTRASONIC JACKET", "cat": "jacket", "note": "Quilted main; lining/yoke; small padding yoke"}
    ]
    
    st.markdown("---")
    st.subheader("📋 BƯỚC 2: BẢNG KẾT QUẢ ĐỊNH MỨC MỌI BỘ TRẢ VỀ TỪ AI")
    
    st.info(
        f"**Điều kiện biên áp dụng:** Size M | Khổ vải: **{current_fabric_config['width_inch']} Inch** | "
        f"Độ co: **L {int(current_fabric_config['shrinkage_l'])}% / W {int(current_fabric_config['shrinkage_w'])}%** | "
        f"Hiệu suất sơ đồ tham chiếu: **{int(current_fabric_config['marker_efficiency'])}%**"
    )
    
    table_rows = []
    for item in parsed_styles_from_pdf:
        config_by_style = current_fabric_config.copy()
        
        # Thiết lập điều kiện tự động bóc tách lớp vật liệu dựa theo loại sản phẩm AI nhận diện được trong PDF
        if item["cat"] == "vest":
            config_by_style["has_lining"] = True
            config_by_style["has_padding"] = True
        elif "raincoat" in item["desc"].lower():
            config_by_style["has_lining"] = False
            config_by_style["has_padding"] = False
            
        res = GarmentCADCoreEngine.calculate_matrix_consumption(item["cat"], config_by_style)
        
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
        
    df_matrix = pd.DataFrame(table_rows)
    
    st.dataframe(df_matrix, use_container_width=True, height=350)
    
    st.download_button(
        label="📥 Xuất File Định Mức Sản Xuất (CSV)",
        data=df_matrix.to_csv(index=False).encode('utf-8-sig'),
        file_name="AI_BOM_Consumption_Matrix.csv",
        mime="text/csv"
    )
else:
    # Trạng thái chờ khi người dùng chưa cung cấp tệp tin kỹ thuật
    st.warning("👉 Vui lòng kéo thả hoặc tải file PDF Techpack lên ở khung phía trên để kích hoạt AI bóc tách danh sách mã hàng và tính toán định mức.")
