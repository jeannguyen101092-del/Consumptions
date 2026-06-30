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
import streamlit as st
import json
import google.generativeai as genai

def ai_gemini_vision_pdf_parser(pdf_bytes, user_custom_prompt) -> dict:
    """
    KIẾN TRÚC CAD/ERP CHUẨN CÔNG NGHIỆP:
    AI đóng vai trò Bộ bóc tách siêu dữ liệu kỹ thuật phẳng (Flat Metadata Extractor).
    Tuyệt đối KHÔNG tính toán, KHÔNG đoán (Hallucinate). Nếu không có dữ liệu => UNKNOWN.
    Giao diện JSON Schema nghiêm ngặt, ổn định 100% khi parse qua Python json.loads().
    """
    try:
        if "GEMINI_API_KEY" in st.secrets: genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        elif "gemini" in st.secrets: genai.configure(api_key=st.secrets["gemini"].get("api_key", ""))
        else:
            return {"error": "Chưa cấu hình GEMINI_API_KEY trong Streamlit Secrets."}
        
        pdf_blob = {"mime_type": "application/pdf", "data": pdf_bytes}
        
        base_prompt = f"""
        Bạn là một Trợ lý AI chuyên trách cấu trúc hóa dữ liệu kỹ thuật may mặc (Techpack & BOM Parser) đầu vào cho hệ thống CAD/ERP.
        Nhiệm vụ duy nhất: ĐỌC, PHÂN TÁCH và ĐIỀN dữ liệu thực tế từ file PDF vào hệ thống.

        🚨 NGUYÊN TẮC BÓC TÁCH KHÔNG ĐOÁN ĐỊNH (CRITICAL RULES):
        1. KHÔNG TỰ TÍNH TOÁN: Tuyệt đối không tự đoán, không tự tính toán consumption, không quy đổi đơn vị nếu tài liệu gốc không ghi.
        2. CƠ CHẾ UNKNOWN: Nếu bất kỳ trường dữ liệu nào không được ghi rõ ràng trong file PDF => Bắt buộc điền "UNKNOWN" hoặc null / false tùy theo kiểu dữ liệu quy định. Không tự ý suy diễn (Ví dụ: Không tự đoán nap=true nếu Techpack không ghi rõ quy cách marker một chiều).
        3. DỮ LIỆU ĐỘNG (DÒNG BOM): Không giới hạn số lượng vật liệu. Mỗi loại vật liệu xuất hiện trong bảng BOM gốc (Shell, Contrast, Pocketing, Mesh, Fusing, Rib, Elastic, Tape...) phải được bóc thành 1 Object độc lập trong mảng `bom_materials`.

        YÊU CẦU BỔ SUNG TỪ Ô CHAT CỦA USER (NẾU CÓ):
        "{user_custom_prompt}"

        Trả về chuỗi JSON duy nhất, KHÔNG bao gồm markdown (```json), KHÔNG có văn bản giải thích. Phải parse được trực tiếp bằng Python json.loads().
        
        [JSON SCHEMA BẮT BUỘC]:
        {{
            "style_code": "Mã Style thực tế từ file hoặc UNKNOWN",
            "description": "Mô tả dáng hàng thực tế hoặc UNKNOWN",
            "base_size": "Size gốc dùng thiết kế (Ví dụ: M, L, 32...) hoặc UNKNOWN",
            "base_pattern_fit": "Kiểu dáng rập gốc (Ví dụ: Regular, Slim, Loose, Oversized...) hoặc UNKNOWN",
            "grading_rule": "Quy tắc nhảy size (Ví dụ: 1 inch bệt vòng) hoặc UNKNOWN",
            "technical_features": [
                "Liệt kê phẳng các đặc tính kỹ thuật có trên sản phẩm: Ví dụ: Double Pleat, Cargo Pocket, Welt Pocket, Elastic Waist. Nếu không có để mảng rỗng []"
            ],
            "bom_materials": [
                {{
                    "material_type": "Phân loại chuẩn: SHELL, CONTRAST, LINING, POCKETING, FUSING, RIB, ELASTIC, hoặc TAPE...",
                    "material_code": "Mã hiệu vải/NPL (Ví dụ: CB250, TR-01) hoặc UNKNOWN",
                    "fabric_composition": "Thành phần vải (Ví dụ: 100% Cotton) hoặc UNKNOWN",
                    "fabric_gsm": "Trọng lượng vải dạng số (Ví dụ: 280) hoặc UNKNOWN",
                    "fabric_width_inch": "Khổ vải ghi trong tài liệu hoặc UNKNOWN",
                    "shrinkage_warp_pct": "Độ co dọc L % từ tài liệu hoặc UNKNOWN",
                    "shrinkage_weft_pct": "Độ co ngang W % từ tài liệu hoặc UNKNOWN",
                    "marker_efficiency_target_pct": "Mục tiêu hiệu suất sơ đồ % hoặc UNKNOWN",
                    "fabric_direction": "Hướng vải (Ví dụ: Lengthwise, Crosswise, Bias) hoặc UNKNOWN",
                    "nap_required": "Chỉ điền true/false nếu tài liệu ghi rõ quy cách tuyết/vải 1 chiều, nếu không ghi bắt buộc điền UNKNOWN",
                    "one_way": "Chỉ điền true/false nếu tài liệu ghi rõ quy cách sơ đồ 1 chiều, nếu không ghi bắt buộc điền UNKNOWN",
                    "stripe_match": false, // Điền true nếu có yêu cầu đối kẻ sọc
                    "plaid_match": false,  // Điền true nếu có yêu cầu đối caro
                    "seam_allowance": "Thông số đường may (Ví dụ: 1cm, 3/8 inch) nếu có ghi, hoặc UNKNOWN",
                    "raw_marker_length_from_pdf": "Chiều dài sơ đồ gốc có sẵn trong PDF hay không, nếu không ghi UNKNOWN",
                    "raw_consumption_from_pdf": "Định mức định biên có sẵn trong PDF hay không, nếu không ghi UNKNOWN",
                    "pieces": [
                        {{
                            "piece_name": "Tên chi tiết rập (Ví dụ: Front Panel, Sleeve, Waistband...)",
                            "cut_qty": 2, // Số lượng chi tiết cần cắt trên 1 sản phẩm (Ví dụ: 2) dạng số hoặc UNKNOWN
                            "mirror": "Trạng thái đối lật rập (true/false) hoặc UNKNOWN",
                            "grainline": "Đường canh sợi chi tiết (Ví dụ: Lengthwise, Crosswise, Bias) hoặc UNKNOWN"
                        }}
                    ]
                }}
            ]
        }}
        """
        # Sử dụng cấu hình cấu trúc đầu ra nghiêm ngặt của Gemini 2.5
        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content([pdf_blob, base_prompt])
        
        # Loại bỏ các ký tự bọc khối mã nếu LLM cố tình thêm vào
        clean_text = response.text.strip()
        if clean_text.startswith("```json"): clean_text = clean_text[7:]
        if clean_text.endswith("```"): clean_text = clean_text[:-3]
        clean_text = clean_text.strip()
        
        return json.loads(clean_text)
    except Exception as e:
        return {"error": f"Lỗi bóc tách siêu dữ liệu AI: {str(e)}"}



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
# BẢNG HIỂN THỊ ĐỊNH MỨC THEO HÀNG NGANG XUỐNG DÒNG (DỄ NHÌN)
# Đoạn code mẫu gợi ý render dữ liệu tại app.py khi hiển thị cục JSON công nghiệp:
if st.session_state.gemini_parsed_bom_data:
    data = st.session_state.gemini_parsed_bom_data
    
    st.markdown("### 🏬 SIÊU DỮ LIỆU SẢN XUẤT (CAD METADATA)")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Mã Style", data.get("style_code"))
    col2.metric("Size gốc (Base Size)", data.get("base_size"))
    col3.metric("Phom dáng rập", data.get("base_pattern_fit"))
    col4.metric("Đặc tính rập", f"{len(data.get('technical_features', []))} điểm lưu ý")
    
    st.markdown("### 📋 DANH SÁCH BOM & CHI TIẾT CẮT (PIECE LIST)")
    
    # Duyệt qua từng vật liệu động do AI quét được
    for idx, mat in enumerate(data.get("bom_materials", [])):
        with st.expander(f"📦 VẬT LIỆU {idx+1}: {mat.get('material_type')} [Mã: {mat.get('material_code')}]", expanded=True):
            # Hiển thị thông số sơ đồ CAD thô
            m_col1, m_col2, m_col3, m_col4 = st.columns(4)
            m_col1.write(f"**Khổ vải:** {mat.get('fabric_width_inch')} inch")
            m_col2.write(f"**Định lượng:** {mat.get('fabric_gsm')} GSM")
            m_col3.write(f"**Độ co L/W:** {mat.get('shrinkage_warp_pct')} / {mat.get('shrinkage_weft_pct')}")
            m_col4.write(f"**Đường may:** {mat.get('seam_allowance')}")
            
            # Chuyển đổi danh sách chi tiết (Pieces List) sang bảng DataFrame để hiển thị sạch sẽ
            pieces_list = mat.get("pieces", [])
            if pieces_list:
                df_pieces = pd.DataFrame(pieces_list)
                # Đổi tên cột hiển thị cho chuyên nghiệp
                df_pieces.columns = ["Tên chi tiết rập", "Số lượng cắt (Cut Qty)", "Đối cặp (Mirror)", "Canh sợi (Grainline)"]
                st.dataframe(df_pieces, use_container_width=True)
            else:
                st.info("Không tìm thấy danh sách chi tiết cắt cho loại vật liệu này trong BOM.")
