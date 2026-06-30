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
st.caption("Kiến trúc Toán học Nhất quán - Giải quyết triệt để lỗi nhảy số ngược của AI")
st.markdown("---")

if "gemini_parsed_bom_data" not in st.session_state: st.session_state.gemini_parsed_bom_data = None
if "saved_pdf_bytes" not in st.session_state: st.session_state.saved_pdf_bytes = None
if "saved_pdf_name" not in st.session_state: st.session_state.saved_pdf_name = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = [{"role": "assistant", "content": "Xin chào! Vui lòng nạp file PDF Techpack lên để hệ thống tự động bóc tách và tính toán định mức Yards chuẩn xưởng."}]

# =====================================================================
# LÕI ENGINE 1: THUẬT TOÁN TOÁN HỌC SƠ ĐỒ CHUẨN (PYTHON EXECUTION)
# =====================================================================
def get_dynamic_marker_efficiency(description: str, style_code: str) -> float:
    """Bộ lọc nhận diện phom dáng đặc thù để áp hiệu suất sơ đồ chuẩn mục tiêu của xưởng"""
    desc_upper = str(description).upper() + " " + str(style_code).upper()
    if any(x in desc_upper for x in ["BAGGY", "FLARE", "WIDE LEG"]):
        return 87.0
    elif any(x in desc_upper for x in ["JEAN", "DENIM", "5 POCKET", "5-POCKET"]):
        return 88.0
    elif any(x in desc_upper for x in ["JACKET", "COAT", "VEST"]):
        return 84.0
    elif any(x in desc_upper for x in ["KNIT", "TEE", "T-SHIRT", "THUN"]):
        return 90.0
    return 86.0

def python_consumption_sanity_check(bom_data: dict) -> dict:
    """
    LÕI TOÁN HỌC ĐỊNH MỨC QUYẾT ĐỊNH 100%:
    AI chỉ bóc tách chiều dài thô (raw_length_inch), Python thực hiện phép toán sơ đồ.
    Khi Hiệu suất (Efficiency) tăng -> Định mức Yards BẮT BUỘC phải giảm xuống.
    """
    if "bom_rows" not in bom_data: return bom_data
    
    desc_upper = str(bom_data.get("description", "")).upper()
    style_upper = str(bom_data.get("style_code", "").upper())
    
    # Lấy hiệu suất mặc định theo loại hàng từ bộ lọc Python
    default_eff = get_dynamic_marker_efficiency(desc_upper, style_upper)
    
    filtered_rows = []
    for row in bom_data["bom_rows"]:
        comp_type = str(row.get("component_type", "")).upper()
        row["validation_status"] = "PASS"
        
        # 1. Đồng bộ và làm sạch dữ liệu Khổ vải đầu vào
        width_text = str(row.get("fabric_width_inch", "58")).replace('"', '').strip()
        try: width = float(width_text)
        except: width = 58.0
        
        # 2. Đồng bộ hiệu suất sơ đồ (Ưu tiên số đọc từ PDF, không có dùng default_eff)
        raw_eff = row.get("marker_efficiency_pct", "")
        if not raw_eff or "UNKNOWN" in str(raw_eff).upper() or "NONE" in str(raw_eff).upper():
            row["marker_efficiency_pct"] = f"{int(default_eff)}%"
            eff_val = default_eff
        else:
            try: eff_val = float(str(raw_eff).replace("%", "").strip())
            except:
                row["marker_efficiency_pct"] = f"{int(default_eff)}%"
                eff_val = default_eff
                
        # 3. Xử lý phần trăm độ co rút dọc L
        shrink_l_text = str(row.get("shrinkage_warp_pct", "0")).replace("%", "").strip()
        try: shrink_l = float(shrink_l_text) / 100.0
        except: shrink_l = 0.0

        # Lấy chiều dài thô do AI trích xuất từ tài liệu PDF (Mặc định quần dài khoảng 40 inch nếu PDF trống)
        raw_length = float(row.get("raw_length_inch", 40.0)) if row.get("raw_length_inch") else 40.0

        # --- THỰC THI PHÉP TOÁN SƠ ĐỒ ĐỊNH MỨC THỰC TẾ ---
        if any(keyword in comp_type for keyword in ["SHELL", "DENIM", "VẢI CHÍNH", "MAIN"]):
            # Quy trình rập thô: Chiều dài cắt = Chiều dài quần + 1.5" (may lai) + 1.5" (bo cạp/đường may)
            gross_pattern_length = raw_length + 3.0
            
            # Công thức tính Yards công nghiệp: ĐM = (Chiều dài rập / 36 inch) / (Hiệu suất % * (1 - Độ co dọc))
            # Với công thức này: Mẫu số chứa eff_val -> Khi eff_val tăng, ĐM chắc chắn phải giảm xuống!
            calculated_yds = (gross_pattern_length / 36.0) / ((eff_val / 100.0) * (1.0 - shrink_l))
            
            # Cộng 2% hao hụt đầu cây biên vải thực tế xưởng cắt
            row["net_consumption_yds_pc"] = round(calculated_yards := calculated_yds * 1.02, 3)
            
            # Đánh giá cảnh báo 3 cấp độ
            if calculated_yards > 2.2: row["validation_status"] = "CRITICAL"
            elif calculated_yards > 1.8: row["validation_status"] = "WARNING"

        # --- TÍNH TOÁN CHO KEO / DỰNG (TRICOT FUSING) ---
        elif any(keyword in comp_type for keyword in ["FUSING", "KEO", "INTERLINING", "MEX"]):
            # Định mức keo dựa trên diện tích bản cạp lưng quần (bản dọc 4.5 inch * vòng eo 36 inch)
            row["net_consumption_yds_pc"] = round((4.5 * 36.0) / (width * 36.0 * 0.90), 3) # Kết quả luôn ổn định ~ 0.105 yds
            if row["net_consumption_yds_pc"] > 0.20: row["validation_status"] = "WARNING"

        # --- TÍNH TOÁN CHO VẢI LÓT TÚI (POCKETING / LINING) ---
        elif any(keyword in comp_type for keyword in ["POCKETING", "LINING", "LÓT", "TÚI"]):
            # Định mức lót túi cho 2 cụm lót túi trước tiêu chuẩn quần jean
            row["net_consumption_yds_pc"] = round((22.0 * 14.0 * 2) / (width * 36.0 * 0.85), 3) # Kết quả luôn ổn định ~ 0.243 yds
            if row["net_consumption_yds_pc"] > 0.35: row["validation_status"] = "WARNING"
            
        filtered_rows.append(row)
        
    bom_data["bom_rows"] = filtered_rows
    return bom_data
# =====================================================================
# LÕI ENGINE 2: AI QUÉT PDF VÀ PHÂN TÁCH SIÊU DỮ LIỆU SẠCH (CẤM TỰ TÍNH TOÁN)
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
                            "raw_length_inch": {"type": "NUMBER", "nullable": True}, # AI bóc tách thông số dài quần thô từ POM vào đây
                            "notes": {"type": "STRING"}
                        },
                        "required": ["component_type"]
                    }
                }
            },
            "required": ["style_code", "bom_rows"]
        }

        base_prompt = f"""
        Bạn là Trợ lý AI bóc tách tài liệu kỹ thuật ngành may mặc.
        Nhiệm vụ duy nhất của bạn là ĐỌC và TRÍCH XUẤT chính xác các thông số từ bảng BOM và POM trong file PDF.

        🚨 QUY TẮC AN TOÀN TUYỆT ĐỐI (CẤM TỰ TÍNH TOÁN):
        1. Tuyệt đối KHÔNG ĐƯỢC tự tính toán định mức số Yards, không được điền trường net_consumption. Trọng trách tính toán số lượng đã được chuyển giao cho Engine Python phía sau đảm nhiệm.
        2. Hãy tìm trong bảng thông số kích thước (POM) để lấy số chiều dài thành phẩm của quần dài (Outseam hoặc Inseam chiều dài từ cạp đến gấu quần, ví dụ: 39, 40, 41.5...) và điền vào trường `raw_length_inch` dạng số. Nếu tài liệu không ghi để null.
        3. Phân tách danh sách theo dòng nguyên phụ liệu độc lập (Vải chính, Keo dựng, Vải lót). Hãy điền khổ vải vật lý do người dùng yêu cầu ở ô chat nếu có chỉ định.

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
        
        # Đẩy dữ liệu cấu trúc sạch qua Python tự tính toán định mức
        raw_json = json.loads(response.text.strip())
        return python_consumption_sanity_check(raw_json)
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
        with st.spinner("Hệ thống Python đang thực hiện thuật toán sơ đồ tính toán Yards..."):
            parsed_result = ai_gemini_vision_pdf_parser(st.session_state.saved_pdf_bytes, user_prompt)
            if parsed_result and "error" not in parsed_result:
                st.session_state.gemini_parsed_bom_data = parsed_result
                ai_response_text = f"**🤖 HỆ THỐNG ĐÃ XỬ LÝ XONG FILE:** `{st.session_state.saved_pdf_name}`\n\n* **Mã Style:** {parsed_result.get('style_code', 'N/A')}\n* **Mô tả:** {parsed_result.get('description', 'N/A')}\n\n👉 *Mời xem bảng định mức do Python tự động tính toán đồng bộ ở phía dưới.*"
                st.session_state.chat_history.append({"role": "assistant", "content": ai_response_text})
            else:
                st.session_state.chat_history.append({"role": "assistant", "content": f"❌ Lỗi: {parsed_result.get('error', 'Lỗi dữ liệu')}"})
        st.rerun()

# BẢNG HIỂN THỊ ĐỊNH MỨC DẠNG HÀNG DỌC XẾP CHỒNG THEO DÒNG VẬT LIỆU
if st.session_state.gemini_parsed_bom_data:
    st.markdown("---")
    st.subheader("📋 BẢNG ĐỊNH MỨC MỌI BỘ - HỆ THỐNG GIÁM SÁT PLM")
    
    col1, col2, col3 = st.columns(3)
    col1.markdown(f"📌 **Mã Style:** `{st.session_state.gemini_parsed_bom_data.get('style_code', 'N/A')}`")
    col2.markdown(f"📐 **Cơ chế tính:** `PYTHON_DETERMINISTIC_ENGINE`")
    col3.markdown(f"🧥 **Mô tả dáng:** {st.session_state.gemini_parsed_bom_data.get('description', 'N/A')}")
        
    bom_rows = st.session_state.gemini_parsed_bom_data.get("bom_rows", [])
    if bom_rows and isinstance(bom_rows, list):
        flat_table_data = []
        for row in bom_rows:
            status_raw = row.get("validation_status", "PASS")
            if status_raw == "CRITICAL": status_display = "🔴 CRITICAL"
            elif status_raw == "WARNING": status_display = "🟡 WARNING"
            else: status_display = "🟢 PASS"
                
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
        st.download_button("📥 Tải bảng định mức kiểm chuẩn (.CSV)", data=csv, file_name="validated_bom_report.csv", mime="text/csv")
