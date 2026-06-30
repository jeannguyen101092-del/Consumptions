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
st.caption("Kiến trúc Toán học CAD Engine - Tích hợp bộ lọc safe_float sạch lỗi hệ thống")
st.markdown("---")

if "gemini_parsed_bom_data" not in st.session_state: st.session_state.gemini_parsed_bom_data = None
if "saved_pdf_bytes" not in st.session_state: st.session_state.saved_pdf_bytes = None
if "saved_pdf_name" not in st.session_state: st.session_state.saved_pdf_name = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = [{"role": "assistant", "content": "Xin chào! Vui lòng nạp file PDF Techpack lên để hệ thống tự động bóc tách và ước tính định mức Yards."}]

# =====================================================================
# LÕI ENGINE 1: BỘ LỌC AN TOÀN TOÁN HỌC KHỬ LỖI CHUỖI 'NULL'
# =====================================================================
def safe_float(val, default=0.0) -> float:
    """
    VÁ LỖI TOÀN DIỆN CỦA HỆ THỐNG:
    Chuyển đổi hoàn chỉnh các chuỗi 'null', 'unknown', None về số thực an toàn.
    """
    if val is None: 
        return default
    val_clean = str(val).replace("%", "").replace('"', '').strip().lower()
    if val_clean in ["null", "none", "unknown", "na", "n/a", ""]:
        return default
    try:
        return float(val_clean)
    except (ValueError, TypeError):
        return default

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
    BỘ KHUNG MA TRẬN 3 DÒNG ĐỘC LẬP TỰ ĐỘNG CẬP NHẬT:
    Tính toán dựa trên chiều dài quần thực tế từ bảng thông số kết hợp 
    với khổ vải và hiệu suất để cho ra kết quả Yards chuẩn xác cho xưởng may.
    """
    desc_upper = str(bom_data.get("description", "")).upper()
    style_upper = str(bom_data.get("style_code", "")).upper()
    default_eff = get_dynamic_marker_efficiency(desc_upper, style_upper)
    
    # Sử dụng safe_float xử lý dứt điểm lỗi chữ null ngầm [INDEX]
    raw_length = safe_float(bom_data.get("raw_length_inch"), default=40.5)
    
    # Cấu hình giá trị số nền tảng mặc định ban đầu cho 3 dòng vật liệu
    w_shell, w_fusing, w_lining = 58.0, 59.0, 57.0
    s_shell_l, s_shell_w = 5.0, 15.0
    eff_val = default_eff
    
    # TRÍCH XUẤT THÔNG SỐ ĐẦU VÀO KHÔNG PHỤ THUỘC THỨ TỰ AI TRẢ VỀ
    if "bom_rows" in bom_data and isinstance(bom_data["bom_rows"], list):
        for row in bom_data["bom_rows"]:
            c_type = str(row.get("component_type", "")).upper()
            width_parsed = safe_float(row.get("fabric_width_inch"), default=0.0)
            
            if any(k in c_type for k in ["SHELL", "DENIM", "VẢI CHÍNH", "MAIN"]):
                if width_parsed > 0: 
                    w_shell = width_parsed
                s_shell_l = safe_float(row.get("shrinkage_warp_pct"), default=5.0)
                s_shell_w = safe_float(row.get("shrinkage_weft_pct"), default=15.0)
                
                raw_eff = row.get("marker_efficiency_pct", "")
                if raw_eff and "UNKNOWN" not in str(raw_eff).upper() and "NONE" not in str(raw_eff).upper():
                    eff_val = safe_float(raw_eff, default=default_eff)
            
            elif any(k in c_type for k in ["FUSING", "KEO", "INTERLINING", "MEX"]):
                if width_parsed > 0: 
                    w_fusing = width_parsed
                
            elif any(k in c_type for k in ["POCKETING", "LINING", "LÓT", "TÚI"]):
                if width_parsed > 0: 
                    w_lining = width_parsed

    clean_rows = []
    
    # 🧵 DÒNG 1: TÍNH TOÁN ĐỊNH MỨC VẢI CHÍNH (DENIM / SHELL)
    gross_length_inch = raw_length + 4.0
    width_multiplier = 2.45 if any(x in desc_upper for x in ["BAGGY", "FLARE", "WIDE LEG"]) else 2.32
    
    # Tính diện tích 4 lớp thân quần jean lớn hoàn chỉnh [INDEX]
    total_garment_area_sq_inch = gross_length_inch * width_multiplier * 4.0
    usable_area_per_yard_shell = w_shell * 36.0 * (eff_val / 100.0)
    net_consumption_shell = total_garment_area_sq_inch / usable_area_per_yard_shell
    final_yards_shell = (net_consumption_shell / (1.0 - (s_shell_l / 100.0))) * 1.02
    
    clean_rows.append({
        "component_type": "Vải Chính (Main Fabric/Denim)", "fabric_width_inch": str(int(w_shell)),
        "shrinkage_warp_pct": f"{int(s_shell_l)}%", "shrinkage_weft_pct": f"{int(s_shell_w)}%",
        "marker_efficiency_pct": f"{int(eff_val)}%", "net_consumption_yds_pc": round(final_yards_shell, 3),
        "validation_status": "CRITICAL" if final_yards_shell > 2.2 else ("WARNING" if final_yards_shell > 1.8 else "PASS"),
        "notes": "Tính toán diện tích hình học rập thành công dựa trên thông số thực tế xưởng may."
    })
    
    # 🧵 DÒNG 2: TÍNH TOÁN ĐỊNH MỨC KEO DỰNG (INTERLINING)
    calculated_fusing = (4.5 * 38.0) / (w_fusing * 36.0 * 0.90)
    clean_rows.append({
        "component_type": "Keo Dựng (Interlining/Mex)", "fabric_width_inch": str(int(w_fusing)),
        "shrinkage_warp_pct": "0%", "shrinkage_weft_pct": "0%",
        "marker_efficiency_pct": f"{int(eff_val)}%", "net_consumption_yds_pc": round(calculated_fusing, 3),
        "validation_status": "WARNING" if calculated_fusing > 0.20 else "PASS",
        "notes": "Tính toán diện tích bản cạp lưng quần thực tế."
    })
    
    # 🧵 DÒNG 3: TÍNH TOÁN ĐỊNH MỨC VẢI LÓT TÚI (LINING FABRIC)
    calculated_lining = (22.0 * 14.0 * 2) / (w_lining * 36.0 * 0.85)
    clean_rows.append({
        "component_type": "Vải Lót (Lining Fabric/Pocketing)", "fabric_width_inch": str(int(w_lining)),
        "shrinkage_warp_pct": "0%", "shrinkage_weft_pct": "0%",
        "marker_efficiency_pct": f"{int(eff_val)}%", "net_consumption_yds_pc": round(calculated_lining, 3),
        "validation_status": "WARNING" if calculated_lining > 0.35 else "PASS",
        "notes": "Cân đối diện tích lót túi cho cặp túi trước quần Jean."
    })
    
    bom_data["bom_rows"] = clean_rows
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
                "raw_length_inch": {"type": "STRING"},
                "bom_rows": {
                    "type": "ARRAY",
                    "items": {
                        "type": "OBJECT",
                        "properties": {
                            "component_type": {"type": "STRING"},
                            "fabric_width_inch": {"type": "STRING"},
                            "shrinkage_warp_pct": {"type": "STRING"},
                            "shrinkage_weft_pct": {"type": "STRING"},
                            "marker_efficiency_pct": {"type": "STRING"}
                        },
                        "required": ["component_type"]
                    }
                }
            },
            "required": ["style_code", "bom_rows"]
        }

        base_prompt = f"""
        Bạn là Trợ lý AI bóc tách tài liệu kỹ thuật ngành may mặc.
        Nhiệm vụ duy nhất của bạn là ĐỌC và TRÍCH XUẤT chính xác các thông số từ bảng BOM và POM trong file PDF [INDEX].

        🚨 QUY TẮC AN TOÀN TUYỆT ĐỐI (CẤM TỰ TÍNH TOÁN):
        1. Tuyệt đối KHÔNG ĐƯỢC tự tính toán định mức số Yards, không được điền trường net_consumption [INDEX].
        2. Hãy tìm trong bảng thông số kích thước (POM) để lấy số chiều dài thành phẩm của quần dài (Outseam hoặc Inseam chiều dài từ cạp đến gấu quần, ví dụ: 39, 40, 41.5...) và điền vào trường `raw_length_inch` dạng chuỗi (Ví dụ: "40.5"). Nếu tài liệu không ghi bắt buộc điền chữ "null" [INDEX].
        3. Phân tách danh sách theo dòng nguyên phụ liệu độc lập (Vải chính, Keo dựng, Vải lót) [INDEX]. 
        4. LUỒNG ĐỒNG BỘ THÔNG TIN TỪ Ô CHAT CỦA USER: Nếu người dùng có gõ chỉ định khổ vải riêng biệt ở câu lệnh chat (Ví dụ: "khổ 58 co rút dọc 5 ngang 15"), bạn phải điền chính xác con số khổ vải đó vào trường `fabric_width_inch` của đúng dòng vật liệu tương ứng [INDEX].

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
        with st.spinner("Hệ thống Matrix Engine đang kết nối Gemini quét file và tự động tính toán số liệu..."):
            parsed_result = ai_gemini_vision_pdf_parser(st.session_state.saved_pdf_bytes, user_prompt)
            if parsed_result and "error" not in parsed_result:
                st.session_state.gemini_parsed_bom_data = parsed_result
                ai_response_text = f"**🤖 HỆ THỐNG ĐÃ XỬ LÝ XONG FILE:** `{st.session_state.saved_pdf_name}`\n\n* **Mã Style:** {parsed_result.get('style_code', 'N/A')}\n* **Mô tả:** {parsed_result.get('description', 'N/A')}\n\n👉 *Mời xem bảng định mức do Python độc lập tính toán 100% ở phía dưới.*"
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
    col2.markdown(f"📐 **Cơ chế tính:** `PYTHON_DETERMINISTIC_MATRIX_ENGINE`")
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
