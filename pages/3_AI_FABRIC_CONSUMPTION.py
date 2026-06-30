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
st.caption("Kiến trúc Costing Validation Engine - Hệ thống giám sát 3 cấp độ (🟢 PASS | 🟡 WARNING | 🔴 CRITICAL)")
st.markdown("---")

if "gemini_parsed_bom_data" not in st.session_state: st.session_state.gemini_parsed_bom_data = None
if "saved_pdf_bytes" not in st.session_state: st.session_state.saved_pdf_bytes = None
if "saved_pdf_name" not in st.session_state: st.session_state.saved_pdf_name = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = [{"role": "assistant", "content": "Xin chào! Vui lòng nạp file PDF Techpack lên, tôi sẽ tự động phân tích và kích hoạt hệ thống kiểm soát 3 cấp độ cho xưởng."}]

# =====================================================================
# LÕI ENGINE 1: PHÂN LOẠI BẬC CAO VÀ KIỂM SOÁT 3 CẤP ĐỘ (VALIDATION MATRIX)
# =====================================================================
def get_dynamic_marker_efficiency(description: str, style_code: str):
    """Ưu tiên nhận diện phom dáng đặc thù trước chủng loại vải. Không khớp trả về None."""
    desc_upper = str(description).upper() + " " + str(style_code).upper()
    if any(x in desc_upper for x in ["BAGGY", "FLARE", "WIDE LEG"]):
        return 87.0
    elif any(x in desc_upper for x in ["JEAN", "DENIM", "5 POCKET", "5-POCKET"]):
        return 88.0
    elif any(x in desc_upper for x in ["JACKET", "COAT", "VEST"]):
        return 84.0
    elif any(x in desc_upper for x in ["KNIT", "TEE", "T-SHIRT", "THUN"]):
        return 90.0
    return None

def python_consumption_sanity_check(bom_data: dict) -> dict:
    """
    HỆ THỐNG GIÁM SÁT SẢN XUẤT 3 CẤP ĐỘ:
    Sửa lỗi cú pháp Python, áp dụng dải định mức thực tế của quần Jean 
    và phân loại trạng thái trực quan: PASS, WARNING, CRITICAL.
    """
    if "bom_rows" not in bom_data: return bom_data
    
    filtered_rows = []
    for row in bom_data["bom_rows"]:
        comp_type = str(row.get("component_type", "")).upper()
        current_val = float(row.get("net_consumption_yds_pc", 0))
        
        # Lọc bỏ phụ liệu đếm mác nhãn/chỉ may
        if any(keyword in comp_type for keyword in ["CHỈ", "THREAD", "LABEL", "BUTTON", "ZIPPER", "MÁC", "NÚT"]):
            continue
            
        # Thiết lập trạng thái an toàn mặc định ban đầu
        row["validation_status"] = "PASS"
        
        # 1. KIỂM TRA ĐỊNH MỨC VẢI CHÍNH (DENIM / SHELL / MAIN FABRIC)
        if any(keyword in comp_type for keyword in ["SHELL", "DENIM", "VẢI CHÍNH", "MAIN"]):
            if current_val > 2.3:
                row["validation_status"] = "CRITICAL"
                row["notes"] = f"🔴 [CRITICAL] Shell Consumption ({current_val:.3f} yds) exceeds limit! " + row.get("notes", "")
            elif current_val > 2.0:
                row["validation_status"] = "WARNING"
                row["notes"] = f"🟡 [WARNING] Check Shell Consumption ({current_val:.3f} yds). " + row.get("notes", "")
                
        # 2. KIỂM TRA VẢI LÓT TÚI (POCKETING / LINING)
        elif any(keyword in comp_type for keyword in ["POCKETING", "LINING", "LÓT", "TÚI"]):
            if current_val > 0.35:
                row["validation_status"] = "WARNING"
                row["notes"] = f"🟡 [WARNING] Check Pocketing Consumption ({current_val:.3f} yds). " + row.get("notes", "")
                
        # 3. KIỂM TRA KEO / DỰNG / MEX (FUSING / INTERLINING)
        elif any(keyword in comp_type for keyword in ["FUSING", "KEO", "INTERLINING", "MEX", "MẾCH"]):
            if current_val > 0.20:
                row["validation_status"] = "WARNING"
                row["notes"] = f"🟡 [WARNING] Check Fusing Consumption ({current_val:.3f} yds). " + row.get("notes", "")
                
        # 4. KIỂM TRA DÂY BĂNG / TAPE
        elif "TAPE" in comp_type:
            if current_val > 0.30:
                row["validation_status"] = "WARNING"
                row["notes"] = f"🟡 [WARNING] Check Tape Consumption ({current_val:.3f} yds). " + row.get("notes", "")
                
        filtered_rows.append(row)
        
    bom_data["bom_rows"] = filtered_rows
    return bom_data
# =====================================================================
# LÕI ENGINE 2: AI QUÉT PDF VÀ ƯỚC TÍNH ĐỊNH MỨC THEO TARGET EFFICIENCY
# =====================================================================
def ai_gemini_vision_pdf_parser(pdf_bytes, user_custom_prompt) -> dict:
    try:
        if "GEMINI_API_KEY" in st.secrets: genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        elif "gemini" in st.secrets: genai.configure(api_key=st.secrets["gemini"].get("api_key", ""))
        else: return {"error": "Chưa cấu hình GEMINI_API_KEY trong Streamlit Secrets."}
        
        pdf_blob = {"mime_type": "application/pdf", "data": pdf_bytes}
        
        # --- BƯỚC PRE-SCAN METADATA ---
        meta_prompt = "Hãy trích xuất từ tài liệu PDF này và trả về chuỗi JSON phẳng gồm duy nhất 2 trường sau: {'style_code': 'Mã style', 'description': 'Mô tả sản phẩm'}. Không ghi thêm chữ giải thích bên ngoài."
        model_meta = genai.GenerativeModel('gemini-2.5-flash')
        meta_res = model_meta.generate_content([pdf_blob, meta_prompt], generation_config=types.GenerationConfig(response_mime_type="application/json"))
        
        try:
            meta_json = json.loads(meta_res.text.strip())
            desc_text = meta_json.get("description", "")
            style_text = meta_json.get("style_code", "")
        except:
            desc_text, style_text = "", ""

        # --- BẢNG TRA CỨU EFFICIENCY BẬC CAO QUA PYTHON ---
        default_eff = get_dynamic_marker_efficiency(desc_text, style_text)
        if default_eff is not None:
            eff_instruction = f"Nếu tài liệu kỹ thuật PDF không ghi rõ chỉ số hiệu suất sơ đồ, bạn BẮT BUỘC phải sử dụng mức hiệu suất mặc định của xưởng chúng tôi cho chủng loại hàng này là: {int(default_eff)}% làm căn cứ gốc để tính toán."
        else:
            eff_instruction = "Nếu tài liệu kỹ thuật PDF không ghi rõ chỉ số hiệu suất sơ đồ, hãy tự phân tích và đưa ra mức hiệu suất an toàn toán học từ 85% đến 88% dựa trên cấu trúc phom dáng sản phẩm."

        json_schema = {
            "type": "OBJECT",
            "properties": {
                "style_code": {"type": "STRING"},
                "description": {"type": "STRING"},
                "calculated_size": {"type": "STRING"},
                "consumption_type": {"type": "STRING"},
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

        # --- PROMPT CHÍNH GỬI AI ---
        base_prompt = f"""
        Bạn là Chuyên gia tối ưu hóa định mức xưởng may và Trưởng phòng kỹ thuật rập CAD.
        Hãy quét bảng BOM và bảng thông số trong file PDF để bóc tách dữ liệu và ước tính định mức tiêu hao Yards.

        🚨 QUY TẮC PHÂN DÒNG (BẮT BUỘC):
        Mỗi loại nguyên phụ liệu / vật liệu bóc tách được phải nằm trên một hàng dọc độc lập (Vải chính, Vải lót, Keo dựng...).

        📉 QUY TẮC ƯỚC TÍNH SỐ LIỆU ĐỊNH MỨC GỐC (ESTIMATED):
        - Hãy đọc kỹ trường dữ liệu hiệu suất sơ đồ 'marker_efficiency_pct' ghi trong PDF trước. Nếu tài liệu có sẵn chỉ số, hãy sử dụng con số đó để tính.
        - {eff_instruction}
        - Tiến hành tính toán định mức tiêu hao Net Yards dựa trên: Chiều dài thành phẩm, khổ vải, thông số may lai gấu, bo cạp, độ co rút dọc/ngang và biến số hiệu suất sơ đồ mục tiêu nêu trên. Phép tính phải đảm bảo tính nhất quán dữ liệu công nghiệp.
        - Quy đổi toàn bộ kết quả cuối cùng ở trường 'net_consumption_yds_pc' về đơn vị YARDS (yds/pc).

        🚨 TRẠNG THÁI HỆ THỐNG:
        - Điền giá trị "ESTIMATED_FROM_PDF" vào trường dữ liệu `consumption_type`.

        YÊU CẦU BỔ SUNG TỪ USER: "{user_custom_prompt}"
        """

        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content(
            [pdf_blob, base_prompt],
            generation_config=types.GenerationConfig(
                response_mime_type="application/json",
                response_schema=json_schema,
                temperature=0.1
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
                ai_response_text = f"**🤖 AI ĐÃ PHÂN TÍCH XONG FILE:** `{st.session_state.saved_pdf_name}`\n\n* **Mã Style:** {parsed_result.get('style_code', 'N/A')}\n* **Mô tả:** {parsed_result.get('description', 'N/A')}\n* **Phương thức xử lý:** `{parsed_result.get('consumption_type', 'N/A')}`\n\n👉 *Mời xem bảng định mức có gắn nhãn giám sát 3 cấp độ ở phía dưới.*"
                st.session_state.chat_history.append({"role": "assistant", "content": ai_response_text})
            else:
                st.session_state.chat_history.append({"role": "assistant", "content": f"❌ Lỗi: {parsed_result.get('error', 'Lỗi dữ liệu')}"})
        st.rerun()

# BẢNG HIỂN THỊ ĐỊNH MỨC DẠNG HÀNG DỌC PHÂN MÀU TRẠNG THÁI CHUYÊN NGHIỆP
if st.session_state.gemini_parsed_bom_data:
    st.markdown("---")
    st.subheader("📋 BẢNG ĐỊNH MỨC MỌI BỘ - HỆ THỐNG GIÁM SÁT PLM")
    
    col1, col2, col3 = st.columns(3)
    col1.markdown(f"📌 **Mã Style:** `{st.session_state.gemini_parsed_bom_data.get('style_code', 'N/A')}`")
    col2.markdown(f"📐 **Cơ chế tính:** `{st.session_state.gemini_parsed_bom_data.get('consumption_type', 'N/A')}`")
    col3.markdown(f"🧥 **Mô tả dáng:** {st.session_state.gemini_parsed_bom_data.get('description', 'N/A')}")
        
    bom_rows = st.session_state.gemini_parsed_bom_data.get("bom_rows", [])
    if bom_rows and isinstance(bom_rows, list):
        flat_table_data = []
        for row in bom_rows:
            # Quy đổi trạng thái chuỗi ký tự sang Icon màu sắc trực quan trên giao diện
            status_raw = row.get("validation_status", "PASS")
            if status_raw == "CRITICAL":
                status_display = "🔴 CRITICAL"
            elif status_raw == "WARNING":
                status_display = "🟡 WARNING"
            else:
                status_display = "🟢 PASS"
                
            flat_table_data.append({
                "Giám Sát PLM": status_display,
                "Loại Nguyên Phụ Liệu": row.get("component_type"),
                "Khổ vải (inch)": row.get("fabric_width_inch"),
                "Độ co L (Dọc)": row.get("shrinkage_warp_pct"),
                "Độ co W (Ngang)": row.get("shrinkage_weft_pct"),
                "Hiệu suất sơ đồ": row.get("marker_efficiency_pct"),
                "Định mức Net (yds/pc)": row.get("net_consumption_yds_pc"),
                "Ghi chú Hệ thống / Nhật ký Cảnh báo": row.get("notes")
            })
            
        df_rows = pd.DataFrame(flat_table_data)
        st.dataframe(df_rows, use_container_width=True)
        
        csv = df_rows.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 Tải bảng định mức kiểm chuẩn (.CSV)", data=csv, file_name="ai_validated_bom_report.csv", mime="text/csv")
