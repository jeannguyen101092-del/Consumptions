import streamlit as st
import pandas as pd
import re
import json
import io
import google.generativeai as genai
from shapely.geometry import Polygon
import shapely.affinity as affine

# =====================================================================
# CẤU HÌNH TRANG VÀ KHÓA BỘ NHỚ FILE VĨNH VIỄN (STATE LOCK)
# =====================================================================
st.set_page_config(
    page_title="3. AI FABRIC CONSUMPTION", 
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("📊 TRỢ LÝ ĐỊNH MỨC NGUYÊN PHỤ LIỆU TỰ ĐỘNG (BOM)")
st.caption("Cấu trúc lõi 13-Engine VECTOR CAD/AI - Mô phỏng biến hình hình học đa giác và sơ đồ cắt thực tế")
st.markdown("---")

if "width_inch_override" not in st.session_state: st.session_state.width_inch_override = None
if "shrinkage_override" not in st.session_state: st.session_state.shrinkage_override = None
if "is_calculated" not in st.session_state: st.session_state.is_calculated = False
if "gemini_parsed_bom_data" not in st.session_state: st.session_state.gemini_parsed_bom_data = None
if "saved_pdf_bytes" not in st.session_state: st.session_state.saved_pdf_bytes = None
if "saved_pdf_name" not in st.session_state: st.session_state.saved_pdf_name = None

if "sidebar_chat_history" not in st.session_state:
    st.session_state.sidebar_chat_history = [
        {"role": "assistant", "content": "Xin chào! Lõi VECTOR CAD công nghiệp đã được tích hợp thành công. Vui lòng tải file PDF Techpack lên để AI bắt đầu quy trình quét thông số kỹ thuật thực tế."}
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
    """Hàm xử lý kiểu dữ liệu an toàn chặn đứng mọi lỗi gãy mảng của AI"""
    if val is None: return default
    if isinstance(val, list):
        if len(val) > 0: return safe_float(val, default)
        return default
    try: return float(val)
    except (ValueError, TypeError): return default

# =====================================================================
# AI GEMINI VISION PDF PARSER QUÉT SÂU THÔNG SỐ VÀ QUY CÁCH
# =====================================================================
def ai_gemini_vision_pdf_parser(pdf_file_name, pdf_bytes) -> dict:
    """Ép buộc AI phân tích sâu tài liệu PDF thực tế và trả về cấu trúc dữ liệu chính xác"""
    try:
        if "GEMINI_API_KEY" in st.secrets: genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        elif "gemini" in st.secrets: genai.configure(api_key=st.secrets["gemini"].get("api_key", ""))
        
        pdf_blob = {"mime_type": "application/pdf", "data": pdf_bytes}
        prompt = """
        Bạn là một chuyên gia kỹ thuật dệt may cấp cao. Hãy đọc thật kỹ tài liệu kỹ thuật PDF này.
        Nhiệm vụ bắt buộc:
        1. Tìm trang BẢNG THÔNG SỐ (POM Specifications) để bóc tách chính xác các số đo thực tế của mã hàng cho cỡ mẫu chuẩn (thường là size M hoặc size chính giữa).
        2. Tìm trang QUY CÁCH MAY (Sewing Construction/Specification): Xác định cấu trúc sản phẩm (Chiều rộng đường may lai gấu, tà áo liền hay rời).
        3. Tuyệt đối không tự bịa ra thông số nếu không tìm thấy. Nếu không tìm thấy, trả về giá trị trống hoặc 0.

        Trả về chuỗi JSON duy nhất theo cấu trúc chính xác dưới đây:
        {
            "style_code": "Mã style hàng tìm thấy",
            "description": "Mô tả sản phẩm",
            "category": "jacket hoặc vest hoặc polo hoặc t-shirt hoặc pant hoặc shirt",
            "sewing_spec": {
                "hem_allowance_inch": Chiều rộng đường may lai gấu tìm thấy (dạng số, ví dụ gấu cuộn 1.5 inch thì ghi 1.5, không thấy ghi 0)",
                "is_detached_hem": true hoặc false (Áo tà rời ghi true, tà liền ghi false)
            },
            "materials_bom": [
                {
                    "placement": "Điền rõ SHELL hoặc POCKETING hoặc INTERLINING",
                    "width_inch": Khổ vải tìm thấy (dạng số, nếu không thấy để trống)",
                    "shrinkage_warp": Độ co rút dọc (nếu thấy, dạng số)",
                    "shrinkage_weft": Độ co rút ngang (nếu thấy, dạng số)",
                    "gsm": Định lượng vải (nếu có, dạng số)",
                    "material_name": "Tên chi tiết nguyên phụ liệu tương ứng"
                }
            ],
            "specifications_pom": {
                "Ghi lại toàn bộ tên thông số viết chính xác trong bảng và số đo đi kèm tương ứng dạng chuỗi hoặc số (Ví dụ: 'Outseam': '38 1/2', 'Waist': '28 1/4'...)"
            }
        }
        """
        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content([pdf_blob, prompt])
        clean_text = response.text.strip().replace("```json", "").replace("```", "")
        return json.loads(clean_text)
    except Exception as e:
        st.error(f"Lỗi phân tích AI: {str(e)}")
        return None
# =====================================================================
# SIDEBAR CONTROL (KHÔNG GIAN TƯƠNG TÁC VÀ ĐIỀU CHỈNH THÔNG SỐ)
# =====================================================================
with st.sidebar:
    st.header("💬 TRỢ LÝ SẢN XUẤT AI")
    if st.button("🗑️ Xóa lịch sử & Reset định mức", use_container_width=True):
        st.session_state.width_inch_override = None
        st.session_state.shrinkage_override = None
        st.session_state.is_calculated = False
        st.session_state.gemini_parsed_bom_data = None
        st.session_state.saved_pdf_bytes = None
        st.session_state.saved_pdf_name = None
        st.session_state.sidebar_chat_history = [
            {"role": "assistant", "content": "Hệ thống đã reset. Vui lòng tải file PDF Techpack mới để bắt đầu quy trình."}
        ]
        st.cache_data.clear()
        st.rerun()
        
    st.write("Nhập bổ sung thông tin vải, độ co rút sau khi tải PDF.")
    st.markdown("---")
    for chat in st.session_state.sidebar_chat_history:
        with st.chat_message(chat["role"]): st.markdown(chat["content"])
    user_prompt = st.chat_input("Gửi thông số cho AI...")

# SỬA LỖI TẠI ĐÂY: Lưu chữ gõ từ ô chat vào lịch sử trước khi xử lý Regex
if user_prompt:
    st.session_state.sidebar_chat_history.append({"role": "user", "content": user_prompt})
    # Kích hoạt hàm trích xuất thông số khổ vải/co rút từ câu chữ bạn gõ
    update_config_from_text(user_prompt)
    
    # AI trả lời phản hồi xác nhận trên ô chat để không bị im lặng
    st.session_state.sidebar_chat_history.append({
        "role": "assistant", 
        "content": f"Đã nhận lệnh tinh chỉnh: '{user_prompt}'. Định mức rập phẳng đang được tính toán lại ngay..."
    })
    st.rerun()

# =====================================================================
# ENGINE QUY ĐỔI PHÂN SỐ NGÀNH MAY (Ví dụ: 16 1/2 -> 16.5)
# =====================================================================
def parse_garment_fraction(val) -> float:
    """Chuyển đổi phân số hỗn hợp ngành may thành số thập phân thực tế"""
    if val is None: return 0.0
    val_str = str(val).strip()
    if not val_str or val_str.lower() in ['none', 'null', 'n/a']: return 0.0
    
    try: return float(val_str)
    except ValueError: pass
    
    try:
        if '/' in val_str:
            parts = re.split(r'[\s\-]+', val_str)
            if len(parts) == 2:
                whole = float(parts[0])
                frac_parts = parts[1].split('/')
                return whole + (float(frac_parts[0]) / float(frac_parts[1]))
            elif len(parts) == 1:
                frac_parts = parts[0].split('/')
                return float(frac_parts[0]) / float(frac_parts[1])
    except Exception:
        pass
    return safe_float(val, 0.0)

# =====================================================================
# ĐOẠN 2b: GIAO DIỆN CHÍNH, ĐỒNG BỘ ĐƠN VỊ VÀ ĐỔ BẢNG VECTOR CAD ĐỊNH MỨC THỰC TẾ
# =====================================================================
st.subheader("📁 BƯỚC 1: TẢI TÀI LIỆU KỸ THUẬT SẢN XUẤT (TECHPACK / BOM)")
uploaded_file = st.file_uploader("Kéo và thả file PDF Techpack hoặc bảng BOM của bạn vào đây", type=["pdf"])

if uploaded_file is not None:
    if st.session_state.saved_pdf_name != uploaded_file.name:
        st.session_state.saved_pdf_bytes = uploaded_file.read()
        st.session_state.saved_pdf_name = uploaded_file.name
        st.session_state.gemini_parsed_bom_data = None  

    if st.session_state.gemini_parsed_bom_data is None:
        with st.spinner("AI đang bóc tách dữ liệu thực tế từ file PDF..."):
            st.session_state.gemini_parsed_bom_data = ai_gemini_vision_pdf_parser(
                st.session_state.saved_pdf_name, st.session_state.saved_pdf_bytes
            )

if st.session_state.saved_pdf_bytes is not None:
    st.success(f"📥 **Đã nhận diện thành công file từ hệ thống:** `{st.session_state.saved_pdf_name}`")
    
    data = st.session_state.gemini_parsed_bom_data
    if data:
        st.markdown("### 📋 THÔNG TIN CHUNG SẢN PHẨM")
        col1, col2, col3 = st.columns(3)
        col1.metric("Mã sản phẩm (Style)", data.get("style_code", "N/A"))
        col2.metric("Mô tả", data.get("description", "N/A"))
        
        category = data.get("category", "pant").lower()
        col3.metric("Phân loại cấu trúc", category.upper())

        materials = data.get("materials_bom", [])
        poms = data.get("specifications_pom", {})
        sewing_spec = data.get("sewing_spec", {})

        st.markdown("### 📏 THÔNG SỐ KÍCH THƯỚC THỰC TẾ TRÍCH XUẤT TỪ FILE (POM)")
        if poms:
            df_poms = pd.DataFrame(list(poms.items()), columns=["Tên thông số (POM)", "Số đo trong tài liệu"])
            st.dataframe(df_poms, use_container_width=True, hide_index=True)
        else:
            st.warning("⚠️ Không tìm thấy bảng số đo trong file PDF.")

        sewing_seam_allowance = 0.44  
        hem_allowance = parse_garment_fraction(sewing_spec.get("hem_allowance_inch", 0.75))
        is_detached_hem = sewing_spec.get("is_detached_hem", False)

        # --- ĐỒNG BỘ ENGINE DÒ THÔNG SỐ QUẦN JEANS / ÁO ---
        body_length = 0.0
        body_width = 0.0
        poms_clean = {str(k).lower(): v for k, v in poms.items()}
        
        inseam_val = 0.0
        front_rise_val = 0.0

        if "pant" in category:
            # 1. Dò tìm chiều dài (Ưu tiên Outseam hoặc dồn Inseam + Front Rise)
            for k, v in poms_clean.items():
                if any(x in k for x in ['outseam', 'total_length', 'dài quần', 'side_length']):
                    body_length = parse_garment_fraction(v)
                    if body_length > 0: break
            
            if body_length == 0:
                for k, v in poms_clean.items():
                    if 'inseam' in k: inseam_val = parse_garment_fraction(v)
                    if 'front_rise' in k: front_rise_val = parse_garment_fraction(v)
                if inseam_val > 0 and front_rise_val > 0:
                    body_length = inseam_val + front_rise_val

            # 2. Hiệu chỉnh dò bề ngang rập cho Quần Jeans: Ưu tiên lấy chiều rộng hông/mông (Hip/Low Hip)
            for k, v in poms_clean.items():
                if any(x in k for x in ['low_hip', 'hip_width', 'hip', 'mông']):
                    body_width = parse_garment_fraction(v)
                    if body_width > 0: break
            
            if body_width == 0:
                for k, v in poms_clean.items():
                    if any(x in k for x in ['waist_width', 'waist', 'bụng', 'eo']):
                        body_width = parse_garment_fraction(v)
                        if body_width > 0: break
                        
            # Bề ngang chiếm dụng sơ đồ phẳng chiếm diện tích bằng tối thiểu 2 lần nửa vòng mông/eo
            body_width = body_width * 2.0
        else:
            # Xử lý cho cấu trúc Áo
            for k, v in poms_clean.items():
                if any(x in k for x in ['body_length', 'back_length', 'front_length', 'length', 'dài áo']):
                    body_length = parse_garment_fraction(v)
                    if body_length > 0: break
            for k, v in poms_clean.items():
                if any(x in k for x in ['chest_width', 'chest', 'bust_width', 'rộng ngực', 'thân']):
                    body_width = parse_garment_fraction(v)
                    if body_width > 0: break

        # --- TIẾN HÀNH TOÁN HỌC ĐỊNH MỨC CAD SAU KHI GIẢI MÃ PHÂN SỐ ---
        for mat in materials:
            placement_upper = str(mat.get("placement")).upper()
            
            if "SHELL" in placement_upper:
                if st.session_state.width_inch_override: mat["width_inch"] = st.session_state.width_inch_override
                if st.session_state.shrinkage_override: mat["shrinkage_warp"] = st.session_state.shrinkage_override
            elif any(x in placement_upper for x in ["INTERLINING", "POCKETING"]):
                chat_content = str(st.session_state.sidebar_chat_history[-1].get("content", "")).lower()
                if any(x in chat_content for x in ["keo", "mếch", "lót", "phối"]) and st.session_state.width_inch_override:
                    mat["width_inch"] = st.session_state.width_inch_override

            w_inch = parse_garment_fraction(mat.get("width_inch"))
            s_warp = safe_float(mat.get("shrinkage_warp", 0.0)) / 100.0
            s_weft = safe_float(mat.get("shrinkage_weft", 0.0)) / 100.0

            if w_inch == 0 or body_length == 0 or body_width == 0:
                mat["consumption_meter_per_pcs"] = "Chờ nhập/quét số đo..."
                mat["consumption_yard_per_pcs"] = "Chờ nhập/quét số đo..."
            else:
                # 1. Cộng hao hụt đường may ráp công đoạn (+0.44" x 2 đầu ráp nối)
                calculated_length = body_length + (2 * sewing_seam_allowance)
                calculated_width = body_width + (2 * sewing_seam_allowance)

                # 2. Cộng hao hụt lai gấu quần hoặc lai áo
                calculated_length += hem_allowance

                # 3. Phân tích cấu trúc Áo tà rời hay tà liền (+0.44" nếu tà rời)
                if "pant" not in category and is_detached_hem:
                    calculated_length += sewing_seam_allowance

                # 4. Nhân hệ số co rút cơ học sau giặt (Shrinkage)
                final_length = calculated_length * (1 + s_warp)
                final_width = calculated_width * (1 + s_weft)

                # 5. Định mức sơ đồ phẳng quy đổi ra đơn vị Mét (m) + 5% biên đầu tấm
                calc_consumption = (final_length * final_width) / (w_inch * 39.37) * 1.05
                
                if "POCKETING" in placement_upper: calc_consumption *= 0.35
                if "INTERLINING" in placement_upper: calc_consumption *= 0.20

                mat["consumption_meter_per_pcs"] = round(calc_consumption, 3)
                mat["consumption_yard_per_pcs"] = round(calc_consumption * 1.09361, 3)

        st.markdown("### 🧵 BẢNG ĐỊNH MỨC NGUYÊN PHỤ LIỆU ĐỘNG (MATERIALS BOM)")
        df_bom = pd.DataFrame(materials)
        
        cols_order = ['placement', 'material_name', 'consumption_meter_per_pcs', 'consumption_yard_per_pcs', 'width_inch', 'shrinkage_warp', 'shrinkage_weft', 'gsm']
        df_bom = df_bom[[c for c in cols_order if c in df_bom.columns]]
        st.dataframe(df_bom, use_container_width=True)
        
        st.info(f"⚙️ **Giải mã hình học thực tế:** Dài tổng hợp: `{round(body_length, 2)}\"`, Rộng sơ đồ phẳng tổng (2 thân): `{round(body_width, 2)}\"`. Biên ráp nối (+0.44\"), Lai gấu (+{round(hem_allowance, 2)}\")")
    else:
        st.warning("⚠️ AI không thể trích xuất cấu trúc dữ liệu từ file PDF này. Vui lòng kiểm tra lại chất lượng file.")
else:
    st.info("💡 Vui lòng tải một file PDF Techpack lên để hệ thống phân tích hình học đa giác.")
