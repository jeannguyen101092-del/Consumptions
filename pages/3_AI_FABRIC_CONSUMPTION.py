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
st.caption("Kiến trúc Toán học CAD Engine - Vá lỗi cú pháp biên dịch hệ thống")
st.markdown("---")

if "gemini_parsed_bom_data" not in st.session_state: st.session_state.gemini_parsed_bom_data = None
if "saved_pdf_bytes" not in st.session_state: st.session_state.saved_pdf_bytes = None
if "saved_pdf_name" not in st.session_state: st.session_state.saved_pdf_name = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = [{"role": "assistant", "content": "Xin chào! Vui lòng nạp file PDF Techpack lên để hệ thống thực hiện thuật toán bù diện tích rập."}]

# =====================================================================
# LÕI ENGINE 1: THUẬT TOÁN ĐỊNH MỨC CAD BÙ DIỆN TÍCH BỀ NGANG RẬP THÔ
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
    THUẬT TOÁN CAD BÙ DIỆN TÍCH BỀ NGANG THỰC TẾ:
    Đã sửa dứt điểm lỗi SyntaxError gán trùng toán tử. Tính toán diện tích 
    hình học rập phẳng quần Jean độc lập dựa trên khổ vải và hiệu suất thực tế.
    """
    if "bom_rows" not in bom_data: return bom_data
    
    desc_upper = str(bom_data.get("description", "")).upper()
    style_upper = str(bom_data.get("style_code", "")).upper()
    
    default_eff = get_dynamic_marker_efficiency(desc_upper, style_upper)
    
    filtered_rows = []
    for row in bom_data["bom_rows"]:
        comp_type = str(row.get("component_type", "")).upper()
        row["validation_status"] = "PASS"
        
        # 1. Đồng bộ khổ vải đầu vào
        width_text = str(row.get("fabric_width_inch", "58")).replace('"', '').strip()
        try: width = float(width_text)
        except: width = 58.0
        
        # 2. Đồng bộ hiệu suất sơ đồ mục tiêu
        raw_eff = row.get("marker_efficiency_pct", "")
        if not raw_eff or "UNKNOWN" in str(raw_eff).upper() or "NONE" in str(raw_eff).upper():
            row["marker_efficiency_pct"] = f"{int(default_eff)}%"
            eff_val = default_eff
        else:
            try: eff_val = float(str(raw_eff).replace("%", "").strip())
            except:
                row["marker_efficiency_pct"] = f"{int(default_eff)}%"
                eff_val = default_eff
                
        # 3. Đồng bộ độ co rút dọc L
        shrink_l_text = str(row.get("shrinkage_warp_pct", "0")).replace("%", "").strip()
        try: shrink_l = float(shrink_l_text) / 100.0
        except: shrink_l = 0.0

        # Lấy thông số dài quần thô do AI bóc (Mặc định quần dài 40.5 inch nếu Techpack trống)
        raw_length = float(row.get("raw_length_inch", 40.5)) if row.get("raw_length_inch") else 40.5

        # --- TÍNH TOÁN VẢI CHÍNH (DENIM / SHELL) ÁP DỤNG HỆ SỐ DIỆN TÍCH BỀ NGANG ---
        if any(keyword in comp_type for keyword in ["SHELL", "DENIM", "VẢI CHÍNH", "MAIN"]):
            # Quy cách dài quần cắt rập thô (bao gồm lai gấu và bo cạp)
            gross_length_inch = raw_length + 3.0
            
            # Hệ số nhân diện tích bề ngang rập thô thực tế (Width Multiplier) cho quần dáng loe/rộng
            if any(x in desc_upper for x in ["BAGGY", "FLARE", "WIDE LEG"]):
                width_multiplier = 2.42
            else:
                width_multiplier = 2.30
                
            # Tính tổng diện tích hình học rập phẳng cho quần (Thân trước + Thân sau đối xứng)
            total_garment_area_sq_inch = gross_length_inch * width_multiplier * 2.0
            
            # Diện tích hữu ích thực tế trên mỗi Yard của khổ vải tương ứng
            usable_area_per_yard = width * 36.0 * (eff_val / 100.0)
            
            # Thực hiện phép toán chia diện tích thô (Đã vá dứt điểm lỗi SyntaxError gán trùng)
            net_consumption = total_garment_area_sq_inch / usable_area_per_yard
            
            # Nhân hệ số bù trừ độ co rút dọc bàn cắt và cộng hao hụt đầu cây 2%
            final_yards = (net_consumption / (1.0 - shrink_l)) * 1.02
            row["net_consumption_yds_pc"] = round(final_yards, 3)
            
            # Nhật ký giám sát 3 cấp độ
            if final_yards > 2.2: row["validation_status"] = "CRITICAL"
            elif final_yards > 1.8: row["validation_status"] = "WARNING"

        # --- TÍNH TOÁN KEO DỰNG (ĐẢM BẢO CHUẨN XƯỞNG) ---
        elif any(keyword in comp_type for keyword in ["FUSING", "KEO", "INTERLINING", "MEX"]):
            row["net_consumption_yds_pc"] = round((4.5 * 38.0) / (width * 36.0 * 0.90), 3)
            if row["net_consumption_yds_pc"] > 0.20: row["validation_status"] = "WARNING"

        # --- TÍNH TOÁN VẢI LÓT TÚI (ĐẢM BẢO CHUẨN XƯỞNG) ---
        elif any(keyword in comp_type for keyword in ["POCKETING", "LINING", "LÓT", "TÚI"]):
            row["net_consumption_yds_pc"] = round((22.0 * 14.0 * 2) / (width * 36.0 * 0.85), 3)
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
                            "raw_length_inch": {"type": "NUMBER", "nullable": True},
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
        1. Tuyệt đối KHÔNG ĐƯỢC tự tính toán định mức số Yards, không được điền trường net_consumption. Trọng trách tính toán số lượng đã được chuyển giao cho Engine Python phía sau đảm nhiệm [INDEX].
        2. Hãy tìm trong bảng thông số kích thước (POM) để lấy số chiều dài thành phẩm của quần dài (Outseam hoặc Inseam chiều dài từ cạp đến gấu quần, ví dụ: 39, 40, 41.5...) và điền vào trường `raw_length_inch` dạng số. Nếu tài liệu không ghi để null [INDEX].
        3. Phân tách danh sách theo dòng nguyên phụ liệu độc lập (Vải chính, Keo dựng, Vải lót) [INDEX]. Hãy điền khổ vải vật lý do người dùng yêu cầu ở ô chat nếu có chỉ định.

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
        with st.spinner("Hệ thống Python đang thực hiện thuật toán sơ đồ tính toán Yards..."):
            parsed_result = ai_gemini_vision_pdf_parser(st.session_state.saved_pdf_bytes, user_prompt)
            if parsed_result and "error" not in parsed_result:
                st.session_state.gemini_parsed_bom_data = parsed_result
                ai_response_text = f"**🤖 HỆ THỐNG ĐÃ XỬ LÝ XONG FILE:** `{st.session_state.saved_pdf_name}`\n\n* **Mã Style:** {parsed_result.get('style_code', 'N/A')}\n* **Mô tả:** {parsed_result.get('description', 'N/A')}\n\n👉 *Mời xem bảng định mức do Python tự động tính toán hình học rập thực tế ở phía dưới.*"
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
    col2.markdown(f"📐 **Cơ chế tính:** `PYTHON_GEOMETRIC_CAD_ENGINE`")
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
