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
st.caption("Kiến trúc Toán học CAD Engine - Đồng bộ hóa chỉ mục dòng cố định chống lỗi nhảy số")
st.markdown("---")

if "gemini_parsed_bom_data" not in st.session_state: st.session_state.gemini_parsed_bom_data = None
if "saved_pdf_bytes" not in st.session_state: st.session_state.saved_pdf_bytes = None
if "saved_pdf_name" not in st.session_state: st.session_state.saved_pdf_name = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = [{"role": "assistant", "content": "Xin chào! Vui lòng nạp file PDF Techpack lên để hệ thống thực hiện thuật toán bù diện tích rập."}]

# =====================================================================
# LÕI ENGINE 1: THUẬT TOÁN ĐỊNH MỨC CAD THEO CHỈ MỤC DÒNG CỐ ĐỊNH (INDEX-BASED)
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
    THUẬT TOÁN ĐỊNH VỊ CHỈ MỤC DÒNG (INDEX-BASED CAD ENGINE):
    Loại bỏ việc tìm từ khóa chuỗi dễ lỗi. Định vị chính xác thuật toán tính toán 
    theo đúng số thứ tự dòng xuất hiện trong bảng dữ liệu rập.
    """
    if "bom_rows" not in bom_data: return bom_data
    
    desc_upper = str(bom_data.get("description", "")).upper()
    style_upper = str(bom_data.get("style_code", "")).upper()
    
    default_eff = get_dynamic_marker_efficiency(desc_upper, style_upper)
    
    filtered_rows = []
    # Duyệt qua các dòng kèm theo chỉ số index (0, 1, 2) để gán thuật toán chính xác tuyệt đối
    for idx, row in enumerate(bom_data["bom_rows"]):
        row["validation_status"] = "PASS"
        
        # 1. Đồng bộ khổ vải vật lý đầu vào
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
                
        # 3. Đồng bộ độ co rút dọc L (Warp)
        shrink_l_text = str(row.get("shrinkage_warp_pct", "0")).replace("%", "").strip()
        try: shrink_l = float(shrink_l_text) / 100.0
        except: shrink_l = 0.0

        # Lấy thông số dài quần thô do AI bóc (Mặc định quần dài Flare Leg/Baggy là 40.5 inch)
        raw_length = float(row.get("raw_length_inch", 40.5)) if row.get("raw_length_inch") else 40.5

        # --- ÁP DỤNG THUẬT TOÁN ĐỊNH MỨC THEO SỐ THỨ TỰ DÒNG CỐ ĐỊNH ---
        
        if idx == 0:
            # 📌 DÒNG 0: ĐỊNH MỨC VẢI CHÍNH (MAIN FABRIC / DENIM)
            row["component_type"] = "Vải Chính (Main Fabric)"
            gross_length_inch = raw_length + 3.0
            
            # Hệ số nhân diện tích bề ngang rập thô thực tế cho quần dáng loe/baggy rộng
            if any(x in desc_upper for x in ["BAGGY", "FLARE", "WIDE LEG"]):
                width_multiplier = 2.45
            else:
                width_multiplier = 2.32
                
            total_garment_area_sq_inch = gross_length_inch * width_multiplier * 2.0
            usable_area_per_yard = width * 36.0 * (eff_val / 100.0)
            net_consumption = total_garment_area_sq_inch / usable_area_per_yard
            
            final_yards = (net_consumption / (1.0 - shrink_l)) * 1.02
            row["net_consumption_yds_pc"] = round(final_yards, 3)
            
            if final_yards > 2.2: row["validation_status"] = "CRITICAL"
            elif final_yards > 1.8: row["validation_status"] = "WARNING"

        elif idx == 1:
            # 📌 DÒNG 1: ĐỊNH MỨC KEO / DỰNG (INTERLINING / FUSING)
            row["component_type"] = "Keo Dựng (Interlining)"
            row["shrinkage_warp_pct"] = "0%"
            row["shrinkage_weft_pct"] = "0%"
            
            # Tính chính xác dựa trên bản cạp quần thực tế chia khổ keo người dùng chỉ định
            calculated_fusing = (4.5 * 38.0) / (width * 36.0 * 0.90)
            row["net_consumption_yds_pc"] = round(calculated_fusing, 3)
            
            if calculated_fusing > 0.20: row["validation_status"] = "WARNING"

        elif idx == 2:
            # 📌 DÒNG 2: ĐỊNH MỨC VẢI LÓT TÚI (LINING FABRIC / POCKETING)
            row["component_type"] = "Vải Lót (Lining Fabric)"
            row["shrinkage_warp_pct"] = "0%"
            row["shrinkage_weft_pct"] = "0%"
            
            # Tính chính xác diện tích cho 2 cụm lót túi trước quần jean chia khổ lót người dùng chỉ định
            calculated_lining = (22.0 * 14.0 * 2) / (width * 36.0 * 0.85)
            row["net_consumption_yds_pc"] = round(calculated_lining, 3)
            
            if calculated_lining > 0.35: row["validation_status"] = "WARNING"
            
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

        🚨 QUY TẮC BẮT BUỘC VỀ CẤU TRÚC ĐẦU RA (MẢNG CỐ ĐỊNH 3 DÒNG):
        Mảng `bom_rows` của bạn chỉ được phép trả về đúng 3 đối tượng (Object) xếp chồng theo đúng thứ tự sau đây:
        - Đối tượng 1 (Dòng 0): Vải chính (Gom thông tin vải Denim/Vải chính). Đọc chiều dài thành phẩm của quần dài từ bảng POM và điền vào trường `raw_length_inch` dạng số (Ví dụ: 40.5).
        - Đối tượng 2 (Dòng 1): Keo dựng (Gom thông tin mếch/mex/keo dựng).
        - Đối tượng 3 (Dòng 2): Vải lót (Gom thông tin vải lót túi/pocketing).

        🚨 LUỒNG ĐỒNG BỘ THÔNG TIN TỪ Ô CHAT CỦA USER:
        - Nếu ở câu lệnh người dùng gõ có chỉ định khổ vải riêng biệt, bạn phải điền chính xác vào trường `fabric_width_inch` tương ứng của từng dòng (Ví dụ câu lệnh: "vai chính khổ 58, vải lót khổ 57, keo khổ 59" thì dòng 0 điền "58", dòng 1 điền "59", dòng 2 điền "57").
        - Tuyệt đối không tự ý tính toán hay điền số định mức Yards, việc tính toán đã bàn giao hoàn toàn cho Python xử lý [INDEX].

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
        with st.spinner("Hệ thống Python Index Engine đang giải quyết toán học sơ đồ Yards..."):
            parsed_result = ai_gemini_vision_pdf_parser(st.session_state.saved_pdf_bytes, user_prompt)
            if parsed_result and "error" not in parsed_result:
                st.session_state.gemini_parsed_bom_data = parsed_result
                ai_response_text = f"**🤖 HỆ THỐNG ĐÃ XỬ LÝ XONG FILE:** `{st.session_state.saved_pdf_name}`\n\n* **Mã Style:** {parsed_result.get('style_code', 'N/A')}\n* **Mô tả:** {parsed_result.get('description', 'N/A')}\n\n👉 *Mời xem bảng định mức hàng dọc được cố định chỉ mục toán học ở phía dưới.*"
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
    col2.markdown(f"📐 **Cơ chế tính:** `PYTHON_INDEX_BASED_ENGINE`")
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
