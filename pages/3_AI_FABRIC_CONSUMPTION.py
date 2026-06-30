import streamlit as st
import pandas as pd
import re
import json
import io
import google.generativeai as genai

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

# Khởi tạo các bộ định tuyến lưu trữ RAM (Session State) chống đơ và mất file
if "width_inch_override" not in st.session_state: st.session_state.width_inch_override = None
if "shrinkage_override" not in st.session_state: st.session_state.shrinkage_override = None
if "is_calculated" not in st.session_state: st.session_state.is_calculated = False
if "gemini_parsed_bom_data" not in st.session_state: st.session_state.gemini_parsed_bom_data = None
if "saved_pdf_bytes" not in st.session_state: st.session_state.saved_pdf_bytes = None
if "saved_pdf_name" not in st.session_state: st.session_state.saved_pdf_name = None

# Khởi tạo cấu trúc lịch sử chat nằm ở khung chính
if "chat_history" not in st.session_state:
    st.session_state.chat_history = [
        {"role": "assistant", "content": "Xin chào! Vui lòng tải file PDF Techpack lên trước, sau đó nhập yêu cầu tính định mức hoặc thông số bổ sung tại ô chat bên dưới."}
    ]

def update_config_from_text(text: str):
    """NLP Parser công nghiệp: Tự động trích xuất thông số từ nội dung chat"""
    if not text: return
    text_lower = text.lower()
    
    # 1. Quét tìm khổ vải vật lý
    width_match = re.search(r'(?:khổ|width|vải|đm|mức|cắt)\s*(\d+)', text_lower)
    if width_match: 
        st.session_state.width_inch_override = float(width_match.group(1))
        st.session_state.is_calculated = True

    # 2. Quét tìm độ co rút dọc L
    co_l_match = re.search(r'(?:co dọc|dọc|l|warp)\s*(\d+)', text_lower)
    if co_l_match: 
        st.session_state.shrinkage_override = float(co_l_match.group(1))
    else:
        generic_co = re.search(r'(?:co rút|độ co|co)\s*(\d+)', text_lower)
        if generic_co: st.session_state.shrinkage_override = float(generic_co.group(1))

    # 3. Quét tìm độ co rút ngang W
    co_w_match = re.search(r'(?:co ngang|ngang|w|weft)\s*(\d+)', text_lower)
    if co_w_match:
        if "gemini_parsed_bom_data" in st.session_state and st.session_state.gemini_parsed_bom_data:
            materials = st.session_state.gemini_parsed_bom_data.get("materials_bom", [])
            if isinstance(materials, list):
                for mat in materials:
                    if isinstance(mat, dict) and mat.get("placement") == "SHELL":
                        mat["shrinkage_weft"] = float(co_w_match.group(1))

def safe_float(val, default=0.0) -> float:
    if val is None: return default
    try: return float(val)
    except (ValueError, TypeError): return default

# =====================================================================
# AI GEMINI VISION PARSER QUÉT CẤU TRÚC MAY RẬP THÔ THỰC TẾ
# =====================================================================
def ai_gemini_vision_pdf_parser(pdf_bytes, user_custom_prompt) -> dict:
    """Quét bảng BOM từ PDF và trả về định mức dạng hàng dọc xuống (mỗi NPL một dòng).
    Kiểm soát chặt chẽ để định mức thực tế không bị quá thấp."""
    try:
        if "GEMINI_API_KEY" in st.secrets: genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        elif "gemini" in st.secrets: genai.configure(api_key=st.secrets["gemini"].get("api_key", ""))
        else:
            return {"error": "Chưa cấu hình GEMINI_API_KEY trong Streamlit Secrets."}
        
        pdf_blob = {"mime_type": "application/pdf", "data": pdf_bytes}
        
        base_prompt = f"""
        Bạn là Chuyên gia tối ưu hóa định mức xưởng may (Garment Costing Master).
        Hãy quét bảng BOM trong file PDF để trích xuất dữ liệu rập và tính định mức tiêu hao (Consumption).

        🚨 QUY TẮC PHÂN DÒNG NGUYÊN PHỤ LIỆU (BẮT BUỘC):
        Hãy trả về kết quả theo dạng danh sách các dòng (Mỗi loại nguyên phụ liệu chiếm 1 dòng riêng biệt):
        - Dòng 1: VÀI CHÍNH (SHELL) -> Gom tất cả chi tiết vải chính (thân, tay, nắp túi, cơi, đáp...) thành 1 dòng tổng.
        - Dòng 2: VẢI LÓT (LINING) -> Nếu sản phẩm có lót.
        - Dòng 3: KEO / DỰNG (INTERLINING) -> Nếu có keo ép mex.
        - Dòng 4: RIB / CHỈ / GÒN... -> Các nguyên phụ liệu khác nếu bảng BOM yêu cầu.

        📉 QUY TẮC TÍNH TOÁN ĐỊNH MỨC CHUẨN XƯỞNG (CHỐNG QUÁ THẤP HOẶC QUÁ CAO):
        - Kiểm tra kỹ độ co rút và hao hụt cắt thực tế. Định mức không được quá thấp dưới mức an toàn của bàn cắt.
        - Đối với Quần (Pants) dáng dài/Flare Leg: Định mức Vải chính (Shell) thông thường phải nằm trong khoảng từ 1.20 yds đến 1.70 yds/pc tùy vào khổ vải và size. Nếu AI tính ra dưới 1.10 yds cho quần dài là QUÁ THẤP, hãy tính toán lại dựa trên chiều dài rập thô thực tế + đường may gấu + độ co,thông số phải cộng thêm xếp ly nếu có xếp ly,tà áo rời cũng phai công thêm,túi mổ phai có cơi túi đáp túi,túi cargo phải cần xem là loại túi gì có xêp ly không có thành túi không để cộng thêm thông số xếp ly vào,lai áo ,lai quần cần kiểm tra quy cách may đê lấy thông sô cho hợp lý.
        - Đơn vị tính bắt buộc: Quy đổi toàn bộ về YARDS (yds/pc).

        YÊU CẦU BỔ SUNG TỪ Ô CHAT CỦA USER:
        "{user_custom_prompt}"

        Trả về chuỗi JSON duy nhất theo cấu trúc chính xác sau (Tuyệt đối không viết thêm chữ giải thích bên ngoài):
        {{
            "style_code": "Mã Style",
            "description": "Mô tả dáng hàng (Ví dụ: LIGHT ORANGE MID-RISE FLARE LEG PANT)",
            "structure": "Cấu trúc sản phẩm",
            "bom_rows": [
                {{
                    "component_type": "VẢI CHÍNH (SHELL)",
                    "fabric_width_inch": "58",
                    "shrinkage_warp_pct": "5%",
                    "shrinkage_weft_pct": "15%",
                    "marker_efficiency_pct": "88%",
                    "net_consumption_yds_pc": 1.47,
                    "notes": "Gom tổng tất cả các chi tiết vải chính bao gồm cả thân, túi, bo cạp"
                }},
                {{
                    "component_type": "VẢI LÓT (LINING)",
                    "fabric_width_inch": "57",
                    "shrinkage_warp_pct": "0%",
                    "shrinkage_weft_pct": "0%",
                    "marker_efficiency_pct": "85%",
                    "net_consumption_yds_pc": 0.25,
                    "notes": "Lót túi, lót đáp"
                }},
                {{
                    "component_type": "KEO / DỰNG",
                    "fabric_width_inch": "59",
                    "shrinkage_warp_pct": "0%",
                    "shrinkage_weft_pct": "0%",
                    "marker_efficiency_pct": "90%",
                    "net_consumption_yds_pc": 0.08,
                    "notes": "Keo ép cạp quần, nắp túi"
                }}
            ]
        }}
        """
        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content([pdf_blob, base_prompt])
        clean_text = response.text.strip().replace("```json", "").replace("```", "")
        return json.loads(clean_text)
    except Exception as e:
        return {"error": f"Lỗi phân tích AI: {str(e)}"}


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
            {"role": "assistant", "content": "Hệ thống đã reset. Vui lòng tải file PDF Techpack mới để bắt đầu quy trình."}
        ]
        st.cache_data.clear()
        st.rerun()
# =====================================================================
# MAIN PAGE INTERFACE: LUỒNG GIAO DIỆN CHÍNH (NỐI TIẾP ĐOẠN 1)
# =====================================================================

# --- BƯỚC 1: TẢI TÀI LIỆU (MAIN PAGE) ---
st.subheader("📁 BƯỚC 1: TẢI TÀI LIỆU KỸ THUẬT SẢN XUẤT (TECHPACK / BOM)")
uploaded_file = st.file_uploader(
    "Kéo và thả file PDF Techpack hoặc bảng BOM của bạn vào đây", 
    type=["pdf"],
    key="main_pdf_uploader"
)

# Nếu người dùng chọn file mới, cập nhật vào Session State chặn đứng tình trạng mất data khi rerun
if uploaded_file is not None:
    file_bytes = uploaded_file.read()
    if st.session_state.saved_pdf_name != uploaded_file.name:
        st.session_state.saved_pdf_bytes = file_bytes
        st.session_state.saved_pdf_name = uploaded_file.name
        st.toast(f"✅ Đã tải file: {uploaded_file.name}", icon="📎")

# --- BƯỚC 2: CHAT AI NẰM NGAY DƯỚI UPLOAD FILE ---
st.markdown("---")
st.subheader("💬 TRỢ LÝ SẢN XUẤT AI")

# Khung hiển thị nội dung hội thoại chat ngay tại dòng chảy chính với chiều cao cố định
chat_container = st.container(height=300)
with chat_container:
    for chat in st.session_state.chat_history:
        with st.chat_message(chat["role"]): 
            st.markdown(chat["content"])

# Ô nhập liệu chat nằm ngay dưới lịch sử chat ở main page
user_prompt = st.chat_input("Nhập bổ sung thông tin vải, độ co rút hoặc yêu cầu tính định mức thực tế...", key="main_chat_input_unique")

# XỬ LÝ LỆNH CHAT VÀ GỬI THẲNG FILE QUA GEMINI
if user_prompt:
    st.session_state.chat_history.append({"role": "user", "content": user_prompt})
    
    # 1. Chạy NLP trích xuất nhanh thông số nếu có viết dạng text (ví dụ: "khổ 58 co dọc 5")
    update_config_from_text(user_prompt)
    
    # 2. Kiểm tra điều kiện file PDF đã được upload chưa
    if not st.session_state.saved_pdf_bytes:
        st.session_state.chat_history.append({
            "role": "assistant", 
            "content": "⚠️ Bạn chưa tải lên file PDF nào ở Bước 1. Vui lòng chọn file PDF để tôi có thông số phân tích định mức nhé!"
        })
        st.rerun()
    else:
        # Tiến hành gọi Gemini quét file PDF kèm Prompt từ ô chat
        with st.spinner("AI đang quét PDF độc lập và tính toán định mức theo yêu cầu..."):
            parsed_result = ai_gemini_vision_pdf_parser(
                st.session_state.saved_pdf_bytes, 
                user_prompt
            )
            
            if parsed_result and "error" not in parsed_result:
                # Lưu data bóc tách vào State để các phần vẽ bảng dữ liệu phía sau sử dụng
                st.session_state.gemini_parsed_bom_data = parsed_result
                st.session_state.is_calculated = True
                
                # Tạo nội dung phản hồi hiển thị lên chat
                ai_response_text = f"""
**🤖 AI ĐÃ PHÂN TÍCH XONG FILE:** `{st.session_state.saved_pdf_name}`

* **Mã Style:** {parsed_result.get('style_code', 'N/A')}
* **Mô tả:** {parsed_result.get('description', 'N/A')}
* **Phân loại sản phẩm:** {parsed_result.get('category', 'N/A')}

📝 **Kết quả tính định mức & Ghi chú kỹ thuật:**
{parsed_result.get('ai_analysis_notes', 'Đã bóc tách thành công cấu trúc chi tiết, mời xem bảng dữ liệu rập phía dưới.')}
"""
                st.session_state.chat_history.append({"role": "assistant", "content": ai_response_text})
            else:
                error_msg = parsed_result.get("error", "Lỗi cấu trúc dữ liệu trả về từ AI.") if parsed_result else "Không nhận được phản hồi từ AI."
                st.session_state.chat_history.append({
                    "role": "assistant", 
                    "content": f"❌ Thất bại: {error_msg}"
                })
        st.rerun()

# =====================================================================
# BẢNG HIỂN THỊ KẾT QUẢ ĐẦU RA THEO PHONG CÁCH BẢNG ĐỊNH MỨC MỌI BỘ
# =====================================================================
if st.session_state.gemini_parsed_bom_data:
    st.markdown("---")
    st.subheader("📊 BẢNG ĐỊNH MỨC MỌI BỘ - PHÂN TÁCH CHUẨN XƯỞNG")
    
    bom_data = st.session_state.gemini_parsed_bom_data.get("bom_table", [])
    
    if bom_data and isinstance(bom_data, list):
        df_bom = pd.DataFrame(bom_data)
        
        # Định nghĩa map tên cột mới bám sát yêu cầu tách biệt NPL của bạn
        column_mapping = {
            "style_code": "Style",
            "description": "Mô tả",
            "structure": "Cấu trúc",
            "fabric_width_inch": "Khổ vải (inch)",
            "shrinkage_warp_pct": "Độ co L",
            "shrinkage_weft_pct": "Độ co W",
            "marker_efficiency_pct": "Hiệu suất",
            "shell_main_fabric_net_yds_pc": "Shell (Vải chính Tổng) (yds/pc)",
            "lining_net_yds_pc": "Lining (Vải lót) (yds/pc)",
            "interlining_keo_net_yds_pc": "Keo / Dựng (yds/pc)",
            "rib_net_yds_pc": "Rib (Bo) (yds/pc)",
            "padding_gon_net_yds_pc": "Padding (Gòn) (yds/pc)",
            "total_yds_pc": "Tổng yds/pc",
            "notes": "Ghi chú"
        }
        
        # Đổi tên hiển thị cho bảng
        df_bom = df_bom.rename(columns={k: v for k, v in column_mapping.items() if k in df_bom.columns})
        st.dataframe(df_bom, use_container_width=True)
        
        # Nút tải file
        csv = df_bom.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 Tải bảng định mức sạch (.CSV)", data=csv, file_name="ai_clean_bom_report.csv", mime="text/csv")
