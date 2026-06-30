import streamlit as st
import pandas as pd
import json
import google.generativeai as genai
from google.generativeai import types

# =====================================================================
# CẤU HÌNH TRANG VÀ BỘ NHỚ LƯU TRỮ (STATE LOCK)
# =====================================================================
st.set_page_config(page_title="3. AI FABRIC CONSUMPTION", layout="wide")
st.title("📊 TRỢ LÝ ĐỊNH MỨC NGUYÊN PHỤ LIỆU TỰ ĐỘNG (BOM)")
st.caption("Kiến trúc AI Estimated Engine - Tự động ước tính định mức trực tiếp từ cấu trúc tài liệu PDF")
st.markdown("---")

if "gemini_parsed_bom_data" not in st.session_state: st.session_state.gemini_parsed_bom_data = None
if "saved_pdf_bytes" not in st.session_state: st.session_state.saved_pdf_bytes = None
if "saved_pdf_name" not in st.session_state: st.session_state.saved_pdf_name = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = [{"role": "assistant", "content": "Xin chào! Vui lòng tải file PDF Techpack lên, AI sẽ tiến hành quét BOM và ước tính định mức Yards."}]

# =====================================================================
# LÕI ENGINE 1: BỘ LỌC AN TOÀN - CHỈ LỌC BỎ CHỈ MAY VÀ PHỤ LIỆU ĐẾM CÁI
# =====================================================================
def python_consumption_sanity_check(bom_data: dict) -> dict:
    """
    Bộ lọc an toàn xưởng:
    1. Giữ nguyên 100% con số ước tính toán học động từ AI.
    2. Chỉ quét và loại bỏ các phụ liệu đếm bằng cái/cuộn không dùng đơn vị Yards (như Chỉ may, nhãn mác).
    """
    if "bom_rows" not in bom_data: return bom_data
    
    filtered_rows = []
    for row in bom_data["bom_rows"]:
        comp_type = str(row.get("component_type", "")).upper()
        
        # Loại bỏ hoàn toàn chỉ may và các phụ liệu không dùng đơn vị yards
        if any(keyword in comp_type for keyword in ["CHỈ", "THREAD", "LABEL", "BUTTON", "ZIPPER", "MÁC", "NÚT"]):
            continue
            
        filtered_rows.append(row)
        
    bom_data["bom_rows"] = filtered_rows
    return bom_data
# =====================================================================
# LÕI ENGINE 2: AI QUÉT PDF VÀ TỰ ĐỘNG ƯỚC TÍNH ĐỊNH MỨC YARDS (ESTIMATED)
# =====================================================================
def ai_gemini_vision_pdf_parser(pdf_bytes, user_custom_prompt) -> dict:
    try:
        if "GEMINI_API_KEY" in st.secrets: genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        elif "gemini" in st.secrets: genai.configure(api_key=st.secrets["gemini"].get("api_key", ""))
        else: return {"error": "Chưa cấu hình GEMINI_API_KEY trong Streamlit Secrets."}
        
        pdf_blob = {"mime_type": "application/pdf", "data": pdf_bytes}
        
        # Đã thêm lại net_consumption_yds_pc và trường trạng thái bóc tách theo yêu cầu của bạn
        json_schema = {
            "type": "OBJECT",
            "properties": {
                "style_code": {"type": "STRING"},
                "description": {"type": "STRING"},
                "calculated_size": {"type": "STRING"},
                "consumption_type": {"type": "STRING"}, # Trả về "ESTIMATED_FROM_PDF"
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
                            "net_consumption_yds_pc": {"type": "NUMBER"}, # Định mức AI tự ước tính toán học
                            "notes": {"type": "STRING"}
                        },
                        "required": ["component_type", "net_consumption_yds_pc"]
                    }
                }
            },
            "required": ["style_code", "bom_rows"]
        }

        base_prompt = f"""
        Bạn là Chuyên gia tối ưu hóa định mức xưởng may và Trưởng phòng kỹ thuật rập CAD (Pattern & Costing Master).
        Hãy quét bảng BOM (Bill of Materials) và bảng thông số POM trong file PDF để bóc tách dữ liệu và ước tính định mức tiêu hao.

        🚨 QUY TẮC PHÂN DÒNG HÀNG NGANG XUỐNG DÒNG (BẮT BUỘC):
        Mỗi loại nguyên phụ liệu / vật liệu bóc tách được từ BOM phải nằm trên một hàng độc lập (Vải chính, Vải lót, Keo dựng, Twill tape...).

        📐 THUẬT TOÁN ƯỚC TÍNH TOÁN HỌC (ESTIMATED CONSUMPTION):
        - Chỉ khi không có tệp hình học DXF, bạn được phép dựa vào bảng thông số POM (Chiều dài quần/áo thành phẩm), khổ vải vật lý (Fabric Width), độ co rút dọc/ngang (Shrinkage), và hiệu suất sơ đồ (Marker Efficiency) để tính toán định mức ước tính [INDEX].
        - Đối với vải chính (Denim/Shell): Hãy tính toán dựa trên chiều dài quần thực tế + thông số may lai gấu + bo cạp rồi bù co rút dọc. Định mức quần dài dáng Baggy/Flare Leg thông thường chỉ dao động quanh mức 1.35 yds đến 1.75 yds/pc trên khổ vải 56-58 inch. Tuyệt đối không được tính vọt lên quá cao trên 2.2 yds. Hãy kiểm soát chặt trần số liệu này.
        - Đối với Keo dựng (Tricot Fusing) và Vải lót túi (TC Pocketing): Ước tính dựa trên diện tích vùng ép keo cạp quần và diện tích 2 túi trước (thường keo từ 0.08 - 0.15 yds, lót túi từ 0.18 - 0.30 yds). Không để bằng 0 hoặc None.
        - Quy đổi toàn bộ kết quả 'net_consumption_yds_pc' về đơn vị YARDS (yds/pc) [INDEX].

        🚨 TRẠNG THÁI HỆ THỐNG:
        - Bắt buộc điền giá trị "ESTIMATED_FROM_PDF" vào trường dữ liệu `consumption_type` [INDEX].

        YÊU CẦU BỔ SUNG TỪ USER: "{user_custom_prompt}"
        """

        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content(
            [pdf_blob, base_prompt],
            generation_config=types.GenerationConfig(
                response_mime_type="application/json",
                response_schema=json_schema,
                temperature=0.1 # Giảm độ sáng tạo để số liệu bám sát toán học thực tế
            )
        )
        return python_consumption_sanity_check(json.loads(response.text.strip()))
    except Exception as e:
        return {"error": f"Lỗi xử lý AI: {str(e)}"}
# =====================================================================
# SIDEBAR CONTROL & INTERFACE LUỒNG CHÍNH
# =====================================================================
with st.sidebar:
    st.header("⚙️ HỆ THỐNG")
    if st.button("🗑️ Xóa lịch sử & Reset định mức", use_container_width=True):
        st.session_state.gemini_parsed_bom_data = None
        st.session_state.saved_pdf_bytes = None
        st.session_state.saved_pdf_name = None
        st.session_state.chat_history = [{"role": "assistant", "content": "Hệ thống đã reset. Vui lòng tải file PDF mới."}]
        st.cache_data.clear()
        st.rerun()

st.subheader("📁 BƯỚC 1: TẢI TÀI LIỆU KỸ THUẬT SẢN XUẤT (TECHPACK / BOM PDF)")
uploaded_file = st.file_uploader("Kéo và thả file PDF Techpack hoặc bảng BOM vào đây", type=["pdf"], key="main_pdf_uploader")

if uploaded_file is not None:
    file_bytes = uploaded_file.read()
    if st.session_state.saved_pdf_name != uploaded_file.name:
        st.session_state.saved_pdf_bytes = file_bytes
        st.session_state.saved_pdf_name = uploaded_file.name
        st.toast(f"✅ Đã nhận file: {uploaded_file.name}", icon="📎")

st.markdown("---")
st.subheader("💬 TRỢ LÝ SẢN XUẤT AI")

chat_container = st.container(height=250)
with chat_container:
    for chat in st.session_state.chat_history:
        with st.chat_message(chat["role"]): st.markdown(chat["content"])

user_prompt = st.chat_input("Nhập thông số vải, độ co rút hoặc yêu cầu tính định mức thực tế...", key="main_chat_input_unique")

if user_prompt:
    st.session_state.chat_history.append({"role": "user", "content": user_prompt})
    if not st.session_state.saved_pdf_bytes:
        st.session_state.chat_history.append({"role": "assistant", "content": "⚠️ Vui lòng tải file PDF lên ở Bước 1 trước."})
        st.rerun()
    else:
        with st.spinner("AI đang tiến hành phân tích sâu tài liệu kĩ thuật và ước tính bảng định mức..."):
            parsed_result = ai_gemini_vision_pdf_parser(st.session_state.saved_pdf_bytes, user_prompt)
            if parsed_result and "error" not in parsed_result:
                st.session_state.gemini_parsed_bom_data = parsed_result
                ai_response_text = f"**🤖 AI ĐÃ PHÂN TÍCH XONG FILE:** `{st.session_state.saved_pdf_name}`\n\n* **Mã Style:** {parsed_result.get('style_code', 'N/A')}\n* **Mô tả:** {parsed_result.get('description', 'N/A')}\n* **Phương thức xử lý:** `{parsed_result.get('consumption_type', 'N/A')}`\n\n👉 *Mời xem bảng định mức tự động điền số liệu dạng Yards ở dưới.*"
                st.session_state.chat_history.append({"role": "assistant", "content": ai_response_text})
            else:
                st.session_state.chat_history.append({"role": "assistant", "content": f"❌ Lỗi: {parsed_result.get('error', 'Lỗi dữ liệu')}"})
        st.rerun()

# BẢNG HIỂN THỊ ĐỊNH MỨC DẠNG HÀNG DỌC XẾP CHỒNG THEO DÒNG VẬT LIỆU
if st.session_state.gemini_parsed_bom_data:
    st.markdown("---")
    st.subheader("📋 BẢNG ĐỊNH MỨC MỌI BỘ - PHÂN TÁCH THEO DÒNG NGUYÊN PHỤ LIỆU")
    
    col1, col2, col3 = st.columns(3)
    col1.markdown(f"📌 **Mã Style:** `{st.session_state.gemini_parsed_bom_data.get('style_code', 'N/A')}`")
    col2.markdown(f"📐 **Cơ chế tính:** `{st.session_state.gemini_parsed_bom_data.get('consumption_type', 'N/A')}`")
    col3.markdown(f"🧥 **Mô tả dáng:** {st.session_state.gemini_parsed_bom_data.get('description', 'N/A')}")
        
    bom_rows = st.session_state.gemini_parsed_bom_data.get("bom_rows", [])
    if bom_rows and isinstance(bom_rows, list):
        df_rows = pd.DataFrame(bom_rows)
        column_mapping = {
            "component_type": "Loại Nguyên Phụ Liệu", "fabric_width_inch": "Khổ vải (inch)",
            "shrinkage_warp_pct": "Độ co L (Dọc)", "shrinkage_weft_pct": "Độ co W (Ngang)",
            "marker_efficiency_pct": "Hiệu suất sơ đồ", "net_consumption_yds_pc": "Định mức Net (yds/pc)",
            "notes": "Chi tiết / Ghi chú bóc tách từ BOM"
        }
        df_rows = df_rows.rename(columns={k: v for k, v in column_mapping.items() if k in df_rows.columns})
        st.dataframe(df_rows, use_container_width=True)
        
        csv = df_rows.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 Tải bảng định mức dọc (.CSV)", data=csv, file_name="ai_estimated_bom_report.csv", mime="text/csv")
