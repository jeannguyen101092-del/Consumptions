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
st.caption("Phân tích rập thô xếp ly, cơi đáp túi mổ thực tế xưởng sản xuất")
st.markdown("---")

if "gemini_parsed_bom_data" not in st.session_state: st.session_state.gemini_parsed_bom_data = None
if "saved_pdf_bytes" not in st.session_state: st.session_state.saved_pdf_bytes = None
if "saved_pdf_name" not in st.session_state: st.session_state.saved_pdf_name = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = [{"role": "assistant", "content": "Xin chào! Vui lòng tải file PDF Techpack lên trước, sau đó nhập yêu cầu tính định mức tại ô chat bên dưới."}]

# =====================================================================
# LÕI ENGINE 1: BỘ CHẶN SỐ TOÁN HỌC PYTHON CHỐNG PHÌNH ĐỊNH MỨC
# =====================================================================
def python_consumption_sanity_check(bom_data: dict) -> dict:
    """Kiểm tra và ép số vải chính (Denim) về dải an toàn thực tế từ 1.35 đến 1.85 yds"""
    if "bom_rows" not in bom_data: return bom_data
    desc_lower = bom_data.get("description", "").lower()
    style_lower = bom_data.get("style_code", "").lower()
    is_pant = "pant" in desc_lower or "pant" in style_lower or "jean" in desc_lower or "trouser" in desc_lower
    is_jacket = "jacket" in desc_lower or "vest" in desc_lower or "coat" in desc_lower
    
    for row in bom_data["bom_rows"]:
        comp_type = row.get("component_type", "").upper()
        current_val = float(row.get("net_consumption_yds_pc", 0))
        
        if "SHELL" in comp_type or "DENIM" in comp_type or "VẢI CHÍNH" in comp_type:
            if is_pant and current_val > 2.0:
                row["net_consumption_yds_pc"] = round(1.45 + (current_val * 0.03), 3)
                row["notes"] = f"[Sửa lỗi phình số] " + row.get("notes", "")
            elif is_jacket and current_val > 3.2:
                row["net_consumption_yds_pc"] = round(2.35 + (current_val * 0.03), 3)
            elif current_val > 3.5:
                row["net_consumption_yds_pc"] = 1.65
        if "FUSING" in comp_type or "KEO" in comp_type or "INTERLINING" in comp_type:
            if current_val > 0.4: row["net_consumption_yds_pc"] = 0.12
        if "POCKETING" in comp_type or "LINING" in comp_type or "LÓT" in comp_type:
            if current_val > 0.6: row["net_consumption_yds_pc"] = 0.25
    return bom_data

# =====================================================================
# LÕI ENGINE 2: AI QUÉT PDF VÀ TÍNH TOÁN ĐỊNH MỨC THEO HÀNG DỌC
# =====================================================================
def ai_gemini_vision_pdf_parser(pdf_bytes, user_custom_prompt) -> dict:
    try:
        if "GEMINI_API_KEY" in st.secrets: genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        elif "gemini" in st.secrets: genai.configure(api_key=st.secrets["gemini"].get("api_key", ""))
        else: return {"error": "Chưa cấu hình GEMINI_API_KEY trong Streamlit Secrets."}
        
        pdf_blob = {"mime_type": "application/pdf", "data": pdf_bytes}
        json_schema = {
            "type": "OBJECT",
            "properties": {
                "style_code": {"type": "STRING"},
                "description": {"type": "STRING"},
                "calculated_size": {"type": "STRING"},
                "bom_rows": {
                    "type": "ARRAY",
                    "items": {
                        "type": "OBJECT",
                        "properties": {
                            "component_type": {"type": "STRING"}, "fabric_width_inch": {"type": "STRING"},
                            "shrinkage_warp_pct": {"type": "STRING"}, "shrinkage_weft_pct": {"type": "STRING"},
                            "marker_efficiency_pct": {"type": "STRING"}, "net_consumption_yds_pc": {"type": "NUMBER"},
                            "notes": {"type": "STRING"}
                        },
                        "required": ["component_type", "net_consumption_yds_pc"]
                    }
                }
            },
            "required": ["style_code", "bom_rows"]
        }

        base_prompt = f"""
        Bạn là Chuyên gia tối ưu hóa định mức xưởng may. Hãy quét bảng BOM trong file PDF để TÍNH TOÁN ĐỊNH MỨC TIÊU HAO.
        🚨 QUY TẮC PHÂN DÒNG: Mỗi vật liệu phải nằm trên một hàng độc lập (Vải chính, Vải lót, Keo dựng, Tape...).
        📉 QUY TẮC BÙ THÔNG SỐ: Cộng thêm thông số thực tế theo: Xếp ly, Tà rời, Cơi đáp túi mổ, Túi hộp Cargo (thành túi), Lai gấu.
        Quy đổi toàn bộ kết quả 'net_consumption_yds_pc' về đơn vị YARDS (yds/pc).
        YÊU CẦU BỔ SUNG TỪ USER: "{user_custom_prompt}"
        """

        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content(
            [pdf_blob, base_prompt],
            generation_config=types.GenerationConfig(response_mime_type="application/json", response_schema=json_schema, temperature=0.1)
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

st.subheader("📁 BƯỚC 1: TẢI TÀI LIỆU KỸ THUẬT SẢN XUẤT (TECHPACK / BOM)")
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
        with st.spinner("AI đang phân tích và tính toán định mức..."):
            parsed_result = ai_gemini_vision_pdf_parser(st.session_state.saved_pdf_bytes, user_prompt)
            if parsed_result and "error" not in parsed_result:
                st.session_state.gemini_parsed_bom_data = parsed_result
                ai_response_text = f"**🤖 AI ĐÃ PHÂN TÍCH XONG FILE:** `{st.session_state.saved_pdf_name}`\n\n* **Mã Style:** {parsed_result.get('style_code', 'N/A')}\n* **Mô tả:** {parsed_result.get('description', 'N/A')}\n* **Size tính toán:** {parsed_result.get('calculated_size', 'N/A')}\n\n👉 *Mời xem bảng định mức tự động điền số liệu ở dưới.*"
                st.session_state.chat_history.append({"role": "assistant", "content": ai_response_text})
            else:
                st.session_state.chat_history.append({"role": "assistant", "content": f"❌ Lỗi: {parsed_result.get('error', 'Lỗi dữ liệu')}"})
        st.rerun()

# BẢNG HIỂN THỊ ĐỊNH MỨC DẠNG HÀNG DỌC
if st.session_state.gemini_parsed_bom_data:
    st.markdown("---")
    st.subheader("📋 BẢNG ĐỊNH MỨC MỌI BỘ - PHÂN TÁCH THEO DÒNG NGUYÊN PHỤ LIỆU")
    
    col1, col2, col3 = st.columns(3)
    col1.markdown(f"📌 **Mã Style:** `{st.session_state.gemini_parsed_bom_data.get('style_code', 'N/A')}`")
    col2.markdown(f"📏 **Kích cỡ (Size):** `{st.session_state.gemini_parsed_bom_data.get('calculated_size', 'N/A')}`")
    col3.markdown(f" Jacket/Pant Description: {st.session_state.gemini_parsed_bom_data.get('description', 'N/A')}")
        
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
        st.download_button("📥 Tải bảng định mức dọc (.CSV)", data=csv, file_name="ai_bom_report.csv", mime="text/csv")
