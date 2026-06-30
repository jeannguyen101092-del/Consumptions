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
    """Ép buộc AI đóng vai trò Pattern Maker bóc tách rập thô dựa trên kỹ thuật may ráp và yêu cầu riêng biệt từ ô chat"""
    try:
        if "GEMINI_API_KEY" in st.secrets: genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        elif "gemini" in st.secrets: genai.configure(api_key=st.secrets["gemini"].get("api_key", ""))
        else:
            return {"error": "Chưa cấu hình GEMINI_API_KEY trong Streamlit Secrets."}
        
        pdf_blob = {"mime_type": "application/pdf", "data": pdf_bytes}
        
        base_prompt = f"""
        Bạn là một Trưởng phòng kỹ thuật rập CAD (Pattern Master). Hãy phân tích toàn bộ tài liệu kỹ thuật PDF này (Bản vẽ Sketch, Bảng thông số, Mô tả quy cách may).
        Nhiệm vụ bắt buộc là phải bóc tách đầy đủ các chi tiết rập thô (Gross Pattern Pieces) trước khi may ráp, cụ thể:
        1. KIỂM TRA XẾP LY (Pleats/Tucks): Xem thân áo/quần hay túi hộp có xếp ly không. Nếu có, kích thước rập thô bắt buộc phải CỘNG THÊM độ sâu của ly.
        2. KIỂM TRA CẤU TRÚC TÚI MỔ (Welt/Piping Pocket): Nếu có túi mổ, bắt buộc phải bóc tách thêm chi tiết vải chính gồm: Cơi túi (Welt), Đáp cơi túi (Facing), và các miếng Lót túi (Pocket Bag).
        3. KIỂM TRA TÚI HỘP (Cargo Pocket): Xác định xem túi có thành túi (Pocket Wall/Bellow) và xếp ly không.
        4. Tuyệt đối liệt kê đủ tất cả chi tiết vải chính (SHELL) cấu thành nên sản phẩm thật trên bàn cắt.

        YÊU CẦU ĐẶC BIỆT TỪ NGƯỜI DÙNG TẠI Ô CHAT (Ưu tiên xử lý và tính định mức theo yêu cầu này):
        "{user_custom_prompt}"

        Trả về chuỗi JSON duy nhất theo cấu trúc chính xác dưới đây (Không viết thêm chữ gì ngoài JSON):
        {{
            "style_code": "Mã style hàng",
            "description": "Mô tả sản phẩm",
            "category": "pant hoặc jacket hoặc shirt",
            "sewing_spec": {{
                "hem_allowance_inch": 1.5
            }},
            "materials_bom": [
                {{"placement": "SHELL", "width_inch": 58.0, "shrinkage_warp": 5.0, "shrinkage_weft": 15.0, "material_name": "Vải chính"}}
            ],
            "garment_panels": [
                {{
                    "panel_name": "Tên chi tiết rập thô",
                    "quantity_per_garment": 2,
                    "length_inch": 40.0,
                    "width_inch": 12.0,
                    "measurement_type": "half",
                    "added_allowance_for_pleats_or_walls": "0"
                }}
            ],
            "ai_analysis_notes": "Ghi chú phân tích thông số và kết quả tính toán định mức theo yêu cầu chat của người dùng"
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
# BẢNG HIỂN THỊ KẾT QUẢ ĐẦU RA CỦA RẬP THÔ
# =====================================================================
if st.session_state.gemini_parsed_bom_data:
    st.markdown("---")
    st.subheader("📋 Bảng chi tiết rập thô bóc tách từ PDF")
    
    # Thử nghiệm trích xuất danh sách chi tiết rập ra DataFrame để hiển thị dạng bảng trực quan
    panels = st.session_state.gemini_parsed_bom_data.get("garment_panels", [])
    if panels and isinstance(panels, list):
        df_panels = pd.DataFrame(panels)
        st.dataframe(df_panels, use_container_width=True)
    else:
        st.json(st.session_state.gemini_parsed_bom_data)
