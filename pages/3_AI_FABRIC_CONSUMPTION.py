import streamlit as st
import json
import google.generativeai as genai
from google.generativeai import types

# =====================================================================
# LÕI ENGINE: HÀM GỌI API GEMINI TÍNH TOÁN ĐỊNH MỨC THEO HÀNG DỌC
# =====================================================================
def ai_gemini_vision_pdf_parser(pdf_bytes, user_custom_prompt) -> dict:
    """
    AI tự động quét bảng BOM từ file PDF và tính toán định mức Yards thực tế,
    áp dụng các luật bù trừ thông số may rập (ly, tà rời, cơi đáp túi mổ, túi cargo, lai gấu)
    và xuất kết quả theo dạng hàng dọc (mỗi vật liệu một dòng).
    """
    try:
        if "GEMINI_API_KEY" in st.secrets: 
            genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        elif "gemini" in st.secrets: 
            genai.configure(api_key=st.secrets["gemini"].get("api_key", ""))
        else:
            return {"error": "Chưa cấu hình GEMINI_API_KEY trong Streamlit Secrets."}
        
        pdf_blob = {"mime_type": "application/pdf", "data": pdf_bytes}

        json_schema = {
            "type": "OBJECT",
            "properties": {
                "style_code": {"type": "STRING"},
                "description": {"type": "STRING"},
                "calculated_size": {"type": "STRING"},
                "structure": {"type": "STRING"},
                "bom_rows": {
                    "type": "ARRAY",
                    "items": {
                        "type": "OBJECT",
                        "properties": {
                            "component_type": {"type": "STRING"},
                            "fabric_width_inch": {"type": "STRING"},
                            "shrinkage_warp_pct": {"type": "STRING"},
                            "shrinkage_weft_pct": {"type": "STRING"},
                            "marker_efficiency_pct": {"type": "STRING"},
                            "net_consumption_yds_pc": {"type": "NUMBER"},
                            "notes": {"type": "STRING"}
                        },
                        "required": ["component_type", "net_consumption_yds_pc"]
                    }
                }
            },
            "required": ["style_code", "bom_rows"]
        }

        base_prompt = f"""
        Bạn là Chuyên gia tối ưu hóa định mức xưởng may và Trưởng phòng kỹ thuật rập CAD (Pattern & Garment Costing Master).
        Hãy quét bảng BOM (Bill of Materials) trong file PDF để bóc tách dữ liệu rập và TÍNH TOÁN ĐỊNH MỨC TIÊU HAO THỰC TẾ.

        🚨 QUY TẮC HIỂN THỊ DẠNG HÀNG DỌC (BẮT BUỘC):
        Hãy phân tách kết quả theo dạng danh sách các dòng độc lập, mỗi loại vật liệu chiếm 1 dòng riêng biệt:
        - VẢI CHÍNH (SHELL): Gom tổng tất cả chi tiết cấu thành từ vải chính (thân, túi, bo cạp...) thành 1 dòng tổng duy nhất.
        - VẢI LÓT (LINING): Tính toán riêng nếu sản phẩm có chi tiết lót.
        - KEO / DỰNG (INTERLINING): Tính toán riêng nếu có keo ép mếch/mex.
        - RIB / TAPE / POCKETING...: Phân dòng riêng cho từng vật liệu phối khác xuất hiện trong bảng BOM gốc.

        📉 QUY TẮC TÍNH TOÁN VÀ BÙ THÔNG SỐ (CHỐNG ĐỊNH MỨC BỊ THẤP SAI THỰC TẾ):
        Hãy dựa vào hình vẽ sơ đồ rập và quy cách may trong PDF để cộng thêm thông số vào phép tính định mức:
        1. XẾP LY (Pleats/Tucks): Nếu sản phẩm có xếp ly, bắt buộc phải CỘNG THÊM độ sâu của các nếp gấp ly vào thông số tính vải.
        2. TÀ ÁO RỜI: Nếu có thiết kế tà rời, phải tính toán cộng thêm phần vải hao hụt của tà rời vào dòng vải chính.
        3. TÚI MỔ (Welt Pocket): Bắt buộc định mức vải chính phải bao gồm cả diện tích của Cơi túi và Đáp túi mổ.
        4. TÚI CARGO (Túi hộp): Kiểm tra xem có xếp ly hộp hoặc có thành túi (Pocket Wall) không để cộng thêm vào diện tích vải cắt.
        5. LAI GẤU (Lai áo/Lai quần): Kiểm tra quy cách may lai để lấy thông số chiều dài rập thô hợp lý, an toàn cho xưởng cắt.
        6. KIỂM TRA LOGIC KEO VÀ LÓT: Không để định mức Lót và Keo bị quá thấp (Ví dụ như mức 0.03 yds là lỗi), lót túi phải đủ diện tích cho 2 túi trước (thường từ 0.18 - 0.30 yds), keo cạp quần phải đủ chiều dài vòng eo (thường từ 0.08 - 0.15 yds).

        🚨 LƯU Ý QUY ĐỔI ĐƠN VỊ:
        - Tất cả kết quả tính toán định mức cuối cùng ở trường `net_consumption_yds_pc` phải được quy đổi về đơn vị YARDS TRÊN MỖI SẢN PHẨM (yds/pc).

        YÊU CẦU BỔ SUNG TỪ Ô CHAT CỦA USER:
        "{user_custom_prompt}"
        """

        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content(
            [pdf_blob, base_prompt],
            generation_config=types.GenerationConfig(
                response_mime_type="application/json",
                response_schema=json_schema,
                temperature=0.2
            )
        )
        return json.loads(response.text.strip())
    except Exception as e:
        return {"error": f"Lỗi bóc tách và tính toán AI: {str(e)}"}
import streamlit as st
import pandas as pd
# Gọi trực tiếp bộ xử lý lõi từ file ai_engine.py nằm cùng thư mục
from ai_engine import ai_gemini_vision_pdf_parser

# =====================================================================
# CẤU HÌNH TRANG VÀ KHÓA BỘ NHỚ FILE VĨNH VIỄN (STATE LOCK)
# =====================================================================
st.set_page_config(
    page_title="3. AI FABRIC CONSUMPTION", 
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("📊 TRỢ LÝ ĐỊNH MỨC NGUYÊN PHỤ LIỆU TỰ ĐỘNG (BOM)")
st.caption("Cấu trúc lõi 13-Engine VECTOR CAD/AI - Phân tích rập thô xếp ly, cơi đáp túi mổ thực tế xưởng sản xuất")
st.markdown("---")

# Khởi tạo các trạng thái RAM ảo chống mất file hoặc trắng trang khi click chuột
if "width_inch_override" not in st.session_state: st.session_state.width_inch_override = None
if "shrinkage_override" not in st.session_state: st.session_state.shrinkage_override = None
if "is_calculated" not in st.session_state: st.session_state.is_calculated = False
if "gemini_parsed_bom_data" not in st.session_state: st.session_state.gemini_parsed_bom_data = None
if "saved_pdf_bytes" not in st.session_state: st.session_state.saved_pdf_bytes = None
if "saved_pdf_name" not in st.session_state: st.session_state.saved_pdf_name = None

if "chat_history" not in st.session_state:
    st.session_state.chat_history = [
        {"role": "assistant", "content": "Xin chào! Vui lòng tải file PDF Techpack lên trước, sau đó nhập yêu cầu tính định mức hoặc thông số bổ sung tại ô chat bên dưới."}
    ]

# =====================================================================
# SIDEBAR CONTROL: NÚT RESET HỆ THỐNG
# =====================================================================
with st.sidebar:
    st.header("⚙️ HỆ THỐNG")
    if st.button("🗑️ Xóa lịch sử & Reset định mức", use_container_width=True):
        st.session_state.width_inch_override = None
        st.session_state.shrinkage_override = None
        st.session_state.is_calculated = False
        st.session_state.gemini_parsed_bom_data = None
        st.session_state.saved_pdf_bytes = None
        st.session_state.saved_pdf_name = None
        st.session_state.chat_history = [
            {"role": "assistant", "content": "Hệ thống đã reset. Vui lòng tải file PDF Techpack mới để bắt đầu."}
        ]
        st.cache_data.clear()
        st.rerun()

# =====================================================================
# MAIN PAGE INTERFACE: LUỒNG GIAO DIỆN CHÍNH NẰM TRÊN MỘT FILE DUY NHẤT
# =====================================================================

# --- BƯỚC 1: TẢI TÀI LIỆU ---
st.subheader("📁 BƯỚC 1: TẢI TÀI LIỆU KỸ THUẬT SẢN XUẤT (TECHPACK / BOM)")
uploaded_file = st.file_uploader(
    "Kéo và thả file PDF Techpack hoặc bảng BOM của bạn vào đây", 
    type=["pdf"],
    key="main_pdf_uploader"
)

# Khóa cứng nhị phân file (bytes) chống mất dữ liệu khi nhấn chat hoặc rerun
if uploaded_file is not None:
    file_bytes = uploaded_file.read()
    if st.session_state.saved_pdf_name != uploaded_file.name:
        st.session_state.saved_pdf_bytes = file_bytes
        st.session_state.saved_pdf_name = uploaded_file.name
        st.toast(f"✅ Đã nhận file dữ liệu: {uploaded_file.name}", icon="📎")

# --- BƯỚC 2: CHAT AI NẰM NGAY DƯỚI KHU VỰC UPLOAD ---
st.markdown("---")
st.subheader("💬 TRỢ LÝ SẢN XUẤT AI")

# Khung hiển thị tin nhắn chat độc lập ở trang chính
chat_container = st.container(height=280)
with chat_container:
    for chat in st.session_state.chat_history:
        with st.chat_message(chat["role"]): 
            st.markdown(chat["content"])

# Ô nhập dữ liệu chat nằm ngay phía dưới dòng chảy trang chính
user_prompt = st.chat_input("Nhập bổ sung thông tin vải, độ co rút hoặc yêu cầu tính định mức thực tế...", key="main_chat_input_unique")

# XỬ LÝ SỰ KIỆN GỬI CHAT VÀ GỌI ENGINE TỰ ĐỘNG TÍNH TOÁN
if user_prompt:
    st.session_state.chat_history.append({"role": "user", "content": user_prompt})
    
    if not st.session_state.saved_pdf_bytes:
        st.session_state.chat_history.append({
            "role": "assistant", 
            "content": "⚠️ Hệ thống chưa nhận được file PDF từ Bước 1. Vui lòng tải file lên trước khi ra lệnh phân tích."
        })
        st.rerun()
    else:
        with st.spinner("AI đang tiến hành phân tích sâu tài liệu kĩ thuật và tính toán bảng định mức..."):
            parsed_result = ai_gemini_vision_pdf_parser(
                st.session_state.saved_pdf_bytes, 
                user_prompt
            )
            
            if parsed_result and "error" not in parsed_result:
                st.session_state.gemini_parsed_bom_data = parsed_result
                st.session_state.is_calculated = True
                
                ai_response_text = f"""
**🤖 AI ĐÃ PHÂN TÍCH XONG FILE:** `{st.session_state.saved_pdf_name}`

* **Mã Style:** {parsed_result.get('style_code', 'N/A')}
* **Mô tả:** {parsed_result.get('description', 'N/A')}
* **Kích cỡ tính toán (Size):** {parsed_result.get('calculated_size', 'N/A')}

👉 *Mời xem bảng phân tách định mức theo hàng dọc đã được tự động điền số liệu ở phía dưới.*
"""
                st.session_state.chat_history.append({"role": "assistant", "content": ai_response_text})
            else:
                error_msg = parsed_result.get("error", "Lỗi dữ liệu hệ thống.") if parsed_result else "Không có phản hồi."
                st.session_state.chat_history.append({
                    "role": "assistant", 
                    "content": f"❌ Lỗi xử lý: {error_msg}"
                })
        st.rerun()

# =====================================================================
# BẢNG HIỂN THỊ ĐỊNH MỨC HÀNG DỌC (XẾP CHỒNG THEO NPL)
# =====================================================================
if st.session_state.gemini_parsed_bom_data:
    st.markdown("---")
    st.subheader("📋 BẢNG ĐỊNH MỨC MỌI BỘ - PHÂN TÁCH THEO DÒNG NGUYÊN PHỤ LIỆU")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f"📌 **Mã Style:** `{st.session_state.gemini_parsed_bom_data.get('style_code', 'N/A')}`")
    with col2:
        st.markdown(f"📏 **Kích cỡ (Size):** `{st.session_state.gemini_parsed_bom_data.get('calculated_size', 'N/A')}`")
    with col3:
        st.markdown(f"🧥 **Mô tả:** {st.session_state.gemini_parsed_bom_data.get('description', 'N/A')}")
        
    bom_rows = st.session_state.gemini_parsed_bom_data.get("bom_rows", [])
    
    if bom_rows and isinstance(bom_rows, list):
        df_rows = pd.DataFrame(bom_rows)
        
        column_mapping = {
            "component_type": "Loại Nguyên Phụ Liệu",
            "fabric_width_inch": "Khổ vải (inch)",
            "shrinkage_warp_pct": "Độ co L (Dọc)",
            "shrinkage_weft_pct": "Độ co W (Ngang)",
            "marker_efficiency_pct": "Hiệu suất sơ đồ",
            "net_consumption_yds_pc": "Định mức Net (yds/pc)",
            "notes": "Chi tiết / Ghi chú bóc tách từ BOM"
        }
        
        df_rows = df_rows.rename(columns={k: v for k, v in column_mapping.items() if k in df_rows.columns})
        st.dataframe(df_rows, use_container_width=True)
        
        csv = df_rows.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            label="📥 Tải bảng định mức dọc (.CSV)", 
            data=csv, 
            file_name=f"dinh_muc_{st.session_state.saved_pdf_name}.csv", 
            mime="text/csv"
        )
    else:
        st.error("Cấu trúc phản hồi không phù hợp để tạo bảng dòng dọc.")
        st.json(st.session_state.gemini_parsed_bom_data)
