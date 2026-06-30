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
st.caption("Kiến trúc TECHPACK PDF CONSUMPTION ESTIMATION ENGINE - Thuật toán cộng dồn hình học (Inseam + Front Rise)")
st.markdown("---")

if "gemini_parsed_bom_data" not in st.session_state: st.session_state.gemini_parsed_bom_data = None
if "saved_pdf_bytes" not in st.session_state: st.session_state.saved_pdf_bytes = None
if "saved_pdf_name" not in st.session_state: st.session_state.saved_pdf_name = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = [{"role": "assistant", "content": "Xin chào! Vui lòng nạp file PDF Techpack lên, hệ thống sẽ tự động bóc tách Inseam + Rise để tính định mức Yards."}]

# =====================================================================
# LÕI ENGINE 1: BỘ LỌC AN TOÀN TOÁN HỌC KHỬ LỖI CHUỖI 'NULL'
# =====================================================================
def safe_float(val, default=0.0) -> float:
    """Chuyển đổi hoàn chỉnh các chuỗi 'null', 'unknown', None về số thực float an toàn."""
    if val is None: return default
    val_clean = str(val).replace("%", "").replace('"', '').strip().lower()
    if val_clean in ["null", "none", "unknown", "na", "n/a", ""]:
        return default
    try:
        return float(val_clean)
    except (ValueError, TypeError):
        return default

def get_dynamic_marker_efficiency(desc_upper: str) -> float:
    """Bộ lọc nhận diện phom dáng đặc thù dựa trên chuỗi thông tin gộp để áp hiệu suất sơ đồ mục tiêu"""
    if any(x in desc_upper for x in ["BAGGY", "FLARE", "WIDE LEG"]):
        return 87.0
    elif any(x in desc_upper for x in ["JEAN", "DENIM", "5 POCKET", "5-E-POCKET", "5POCKET"]):
        return 88.0
    elif any(x in desc_upper for x in ["JACKET", "COAT", "VEST"]):
        return 84.0
    elif any(x in desc_upper for x in ["KNIT", "TEE", "T-SHIRT", "THUN"]):
        return 90.0
    return 86.0

def python_consumption_sanity_check(bom_data: dict) -> dict:
    """
    TECHPACK PDF CONSUMPTION ESTIMATION ENGINE:
    Thuật toán cộng dồn hình học rập Jean: Total Length = Inseam + Front Rise + Seam Allowances.
    """
    desc_upper = (
        str(bom_data.get("description", "")) + " " +
        str(bom_data.get("style_code", "")) + " " +
        str(bom_data.get("style_name", ""))
    ).upper()
    
    default_eff = get_dynamic_marker_efficiency(desc_upper)
    
    # 📐 ĐIỂM CẢI TIẾN LÕI: Trích xuất và cộng dồn Inseam + Front Rise thực tế từ Techpack
    raw_inseam = safe_float(bom_data.get("inseam") or bom_data.get("inseam_length"), default=30.0)
    raw_rise = safe_float(bom_data.get("front_rise") or bom_data.get("rise"), default=10.5)
    
    # Tổng chiều dài quần thực tế dọc trục hông = Inseam + Front Rise
    calculated_outseam = raw_inseam + raw_rise
    
    w_shell, w_fusing, w_lining = 58.0, 59.0, 57.0
    s_shell_l, s_shell_w = 5.0, 15.0
    eff_val = default_eff
    
    if "bom_rows" in bom_data and isinstance(bom_data["bom_rows"], list):
        for row in bom_data["bom_rows"]:
            c_type = str(row.get("component_type", "")).upper()
            width_parsed = safe_float(row.get("fabric_width_inch"), default=0.0)
            
            if any(k in c_type for k in ["SHELL", "DENIM", "VẢI CHÍNH", "MAIN"]):
                if width_parsed > 0: w_shell = width_parsed
                s_shell_l = safe_float(row.get("shrinkage_warp_pct"), default=5.0)
                s_shell_w = safe_float(row.get("shrinkage_weft_pct"), default=15.0)
                
                raw_eff = row.get("marker_efficiency_pct", "")
                if raw_eff and "UNKNOWN" not in str(raw_eff).upper() and "NONE" not in str(raw_eff).upper():
                    try: eff_val = float(str(raw_eff).replace("%", "").strip())
                    except: eff_val = default_eff
            
            elif any(k in c_type for k in ["FUSING", "KEO", "INTERLINING", "MEX"]):
                if width_parsed > 0: w_fusing = width_parsed
                
            elif any(k in c_type for k in ["POCKETING", "LINING", "LÓT", "TÚI"]):
                if width_parsed > 0: w_lining = width_parsed

    clean_rows = []
    
    # 🧵 DÒNG 1: THUẬT TOÁN ƯỚC TÍNH VẢI CHÍNH (DENIM PANTS ENGINE)
    # Chiều dài quần rập cắt thô = Tổng chiều dài tính toán + 1.5 inch (may lai gấu + hao hụt đường ráp cạp)
    pant_length = calculated_outseam + 1.5
    
    if any(x in desc_upper for x in ["BAGGY", "FLARE", "WIDE LEG"]):
        body_width_factor = 23.5  # Phom rộng loe
    elif "STRAIGHT" in desc_upper:
        body_width_factor = 21.0  # Phom đứng
    else:
        body_width_factor = 19.5  # Phom ôm skinny

    total_garment_area_sq_inch = pant_length * body_width_factor * 2.0
    total_garment_area_sq_inch *= 1.12  # Cộng 12% chi tiết phụ (túi sau, đáp đô, lưng cạp)
    
    usable_area_per_yard_shell = w_shell * 36.0 * (eff_val / 100.0)
    net_consumption_shell = total_garment_area_sq_inch / usable_area_per_yard_shell
    
    shrink_factor = max(0.85, 1.0 - (s_shell_l / 100.0))
    final_gross_yards_shell = (net_consumption_shell / shrink_factor) * 1.02
    
    validation_status = (
        "CRITICAL" if final_gross_yards_shell > 2.2 
        else ("WARNING" if final_gross_yards_shell > 1.8 else "PASS")
    )
    
    clean_rows.append({
        "component_type": "Vải Chính (Main Fabric/Denim)", "fabric_width_inch": str(int(w_shell)),
        "shrinkage_warp_pct": f"{int(s_shell_l)}%", "shrinkage_weft_pct": f"{int(s_shell_w)}%",
        "marker_efficiency_pct": f"{int(eff_val)}%", "gross_consumption_yds_pc": round(final_gross_yards_shell, 3),
        "validation_status": validation_status,
        "notes": f"Tính toán từ Inseam ({raw_inseam} in) + Front Rise ({raw_rise} in). Tổng Dài Quần: {calculated_outseam} in."
    })
    
    # 🧵 DÒNG 2: ƯỚC TÍNH KEO DỰNG (INTERLINING)
    calculated_fusing = (4.5 * 38.0) / (w_fusing * 36.0 * 0.90)
    clean_rows.append({
        "component_type": "Keo Dựng (Interlining/Mex)", "fabric_width_inch": str(int(w_fusing)),
        "shrinkage_warp_pct": "0%", "shrinkage_weft_pct": "0%",
        "marker_efficiency_pct": f"{int(eff_val)}%", "gross_consumption_yds_pc": round(calculated_fusing, 3),
        "validation_status": "WARNING" if calculated_fusing > 0.20 else "PASS",
        "notes": "Ước tính bản cạp lưng quần thực tế."
    })
    
    # 🧵 DÒNG 3: ƯỚC TÍNH VẢI LÓT TÚI (LINING FABRIC)
    calculated_lining = (22.0 * 14.0 * 2) / (w_lining * 36.0 * 0.85)
    clean_rows.append({
        "component_type": "Vải Lót (Lining Fabric/Pocketing)", "fabric_width_inch": str(int(w_lining)),
        "shrinkage_warp_pct": "0%", "shrinkage_weft_pct": "0%",
        "marker_efficiency_pct": f"{int(eff_val)}%", "gross_consumption_yds_pc": round(calculated_lining, 3),
        "validation_status": "WARNING" if calculated_lining > 0.35 else "PASS",
        "notes": "Cân đối diện tích cặp túi trước quần Jean."
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
        
        # Cấu hình schema ép AI tìm kiếm chính xác trường inseam và front_rise từ bảng POM
        json_schema = {
            "type": "OBJECT",
            "properties": {
                "style_code": {"type": "STRING"},
                "style_name": {"type": "STRING"},
                "description": {"type": "STRING"},
                "calculated_size": {"type": "STRING"},
                "inseam": {"type": "STRING"},           # Trích xuất chiều dài dọc ống trong (Inseam) [INDEX]
                "front_rise": {"type": "STRING"},       # Trích xuất hạ đáy thân trước (Front Rise) [INDEX]
                "hip": {"type": "STRING"},              
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
                            "marker_efficiency_pct": {"type": "STRING"}
                        },
                        "required": ["component_type"]
                    }
                }
            },
            "required": ["style_code", "bom_rows"]
        }

        base_prompt = f"""
        Bạn là Trợ lý AI bóc tách tài liệu kỹ thuật ngành may mặc chuyên nghiệp (Techpack & BOM Parser).
        Nhiệm vụ duy nhất của bạn là ĐỌC và TRÍCH XUẤT chính xác các siêu dữ liệu từ bảng BOM và bảng kích thước POM trong file PDF.

        🚨 QUY TẮC TRÍCH XUẤT THÔNG SỐ (POM INSEAM EXTRACTION):
        1. Tuyệt đối KHÔNG ĐƯỢC tự tính toán định mức số Yards, giữ các trường tính toán trống.
        2. Hãy quét kỹ bảng thông số kích cỡ (POM) để trích xuất:
           - Ký hiệu kích cỡ làm gốc tính toán đưa vào trường `calculated_size` (Ví dụ: 30, 32...).
           - Tìm thông số chiều dài dọc ống bên trong (INSEAM hoặc CROTCH LENGTH) đưa vào trường `inseam` dạng chuỗi (Ví dụ: "30" hoặc "31").
           - Tìm thông số hạ đáy / vòng đáy thân trước (FRONT RISE hoặc CROTCH RISE) đưa vào trường `front_rise` dạng chuỗi (Ví dụ: "10.5" hoặc "11").
           - Tìm thông số vòng mông (HIP) đưa vào trường `hip` dạng chuỗi (Ví dụ: "44").
        3. Phân tách danh sách mảng bom_rows theo dòng nguyên phụ liệu độc lập (Vải chính, Keo dựng, Vải lót). Đồng bộ chỉ số khổ vải do người dùng gõ chỉ định ở ô chat nếu có yêu cầu.
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
        with st.spinner("Hệ thống Techpack PDF Engine đang bóc tách POM và xử lý định mức Yards..."):
            parsed_result = ai_gemini_vision_pdf_parser(st.session_state.saved_pdf_bytes, user_prompt)
            if parsed_result and "error" not in parsed_result:
                st.session_state.gemini_parsed_bom_data = parsed_result
                
                ai_response_text = f"**🤖 HỆ THỐNG ĐÃ XỬ LÝ XONG FILE:** `{st.session_state.saved_pdf_name}`\n\n* **Mã Style:** {parsed_result.get('style_code', 'N/A')} | **Tên hàng:** {parsed_result.get('style_name', 'N/A')}\n* **Mô tả:** {parsed_result.get('description', 'N/A')}\n* **Size bóc được:** `{parsed_result.get('calculated_size', 'N/A')}` | **Inseam:** `{parsed_result.get('inseam', 'N/A')}\"` | **Front Rise:** `{parsed_result.get('front_rise', 'N/A')}\"`"
                st.session_state.chat_history.append({"role": "assistant", "content": ai_response_text})
            else:
                st.session_state.chat_history.append({"role": "assistant", "content": f"❌ Lỗi: {parsed_result.get('error', 'Lỗi dữ liệu')}"})
        st.rerun()

# BẢNG HIỂN THỊ ĐỊNH MỨC DẠNG HÀNG DỌC XẾP CHỒNG THEO TIÊU CHUẨN ĐỊNH MỨC GROSS
if st.session_state.gemini_parsed_bom_data:
    st.markdown("---")
    st.subheader("📋 BẢNG ĐỊNH MỨC MỌI BỘ - HỆ THỐNG GIÁM SÁT PLM")
    
    col1, col2, col3 = st.columns(3)
    col1.markdown(f"📌 **Mã Style:** `{st.session_state.gemini_parsed_bom_data.get('style_code', 'N/A')}`")
    col2.markdown(f"📐 **Cơ chế tính:** `TECHPACK_PDF_CONSUMPTION_ESTIMATION_ENGINE`")
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
                "Định mức Gross (yds/pc)": row.get("gross_consumption_yds_pc"),
                "Ghi chú Hệ thống / Nhật ký Cảnh báo": row.get("notes")
            })
            
        df_rows = pd.DataFrame(flat_table_data)
        st.dataframe(df_rows, use_container_width=True)
        
        csv = df_rows.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 Tải bảng định mức kiểm chuẩn (.CSV)", data=csv, file_name="validated_bom_report.csv", mime="text/csv")
