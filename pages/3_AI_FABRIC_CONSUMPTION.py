import streamlit as st
import pandas as pd
import json
import google.generativeai as genai
from google.generativeai import types
import io
import re

# =====================================================================
# CẤU HÌNH TRANG VÀ BỘ NHỚ LƯU TRỮ (STATE LOCK)
# =====================================================================
st.set_page_config(page_title="3. AI FABRIC CONSUMPTION", layout="wide")
st.title("📊 TRỢ LÝ ĐỊNH MỨC NGUYÊN PHỤ LIỆU TỰ ĐỘNG (BOM)")
st.caption("Kiến trúc Techpack Engine - Bản vá dứt điểm lỗi bóc tách văn bản ô chat")
st.markdown("---")

if "gemini_parsed_bom_data" not in st.session_state: st.session_state.gemini_parsed_bom_data = None
if "saved_pdf_bytes" not in st.session_state: st.session_state.saved_pdf_bytes = None
if "saved_pdf_name" not in st.session_state: st.session_state.saved_pdf_name = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = [{"role": "assistant", "content": "Xin chào! Vui lòng nạp file PDF Techpack lên, hệ thống sẽ thực hiện toán học sơ đồ dài tích hợp co rút hai chiều."}]

# =====================================================================
# LÕI ENGINE 1: THUẬT TOÁN ĐỊNH MỨC TÍCH HỢP CO RÚT HAI CHIỀU (WARP & WEFT)
# =====================================================================
def safe_float(val, default=0.0) -> float:
    """Chuyển đổi hoàn chỉnh các chuỗi 'null', 'unknown', None về số thực float an toàn."""
    if val is None: return default
    val_clean = str(val).replace("%", "").replace('"', '').strip().lower()
    if val_clean in ["null", "none", "unknown", "na", "n/a", ""]: return default
    try: return float(val_clean)
    except (ValueError, TypeError): return default

def get_dynamic_marker_efficiency(description: str, style_code: str) -> float:
    """Bộ lọc nhận diện phom dáng đặc thù dựa trên mô tả và mã để áp hiệu suất sơ đồ mục tiêu"""
    desc_upper = (str(description) + " " + str(style_code)).upper()
    if any(x in desc_upper for x in ["JACKET", "COAT", "VEST"]): return 84.0
    elif any(x in desc_upper for x in ["BAGGY", "FLARE", "WIDE LEG"]): return 87.0
    elif any(x in desc_upper for x in ["JEAN", "DENIM", "5 POCKET", "5-POCKET", "MOM SHORT", "SHORT"]): return 88.0
    return 86.0

def python_consumption_sanity_check(bom_data: dict) -> dict:
    """
    TECHPACK PDF CONSUMPTION ESTIMATION ENGINE - BẢN TỐI ƯU HÓA HOÀN CHỈNH:
    - Sửa lỗi bắt trùng từ khóa áo thun (T-shirt) và sơ mi (Shirt) bằng logic loại trừ.
    - Chuẩn hóa tên biến tiếng Anh kỹ thuật ngành may (Warp / Weft).
    - Tăng độ dài bọc rập cho Đầm/Váy (Dress) lên +6.0 inch để bao quát phom Maxi/thân trên.
    - Tích hợp bộ phân tầng trạng thái Validation tự động dựa trên dải định mức (PASS, WARNING, CRITICAL).
    """
    if bom_data is None: bom_data = {}
    
    style_code_raw = str(bom_data.get("style_code", ""))
    desc_upper = (
        str(bom_data.get("description", "")) + " " + 
        str(bom_data.get("style_code", "")) + " " + 
        str(bom_data.get("style_name", ""))
    ).upper()
    
    default_eff = get_dynamic_marker_efficiency(desc_upper, style_code_raw)
    
    # --- PHÂN LOẠI SẢN PHẨM TỰ ĐỘNG (ĐÃ VÁ LỖI TRÙNG TỪ KHÓA) ---
    is_jacket = any(x in desc_upper for x in ["JACKET", "COAT", "VEST", "OUTERWEAR"])
    is_pant = any(x in desc_upper for x in ["JEAN", "DENIM", "PANT", "BAGGY", "SHORT", "TROUSER", "LEGGING"])
    is_dress = any(x in desc_upper for x in ["DRESS", "SKIRT", "VÁY", "ĐẦM", "MAXI"])
    is_tshirt = any(x in desc_upper for x in ["TSHIRT", "T-SHIRT", "TEE", "POLO", "ÁO THUN"])
    
    # Loại trừ T-Shirt để tránh bắt nhầm áo thun thành sơ mi
    is_shirt = (
        any(x in desc_upper for x in ["SHIRT", "SƠ MI", "BLOUSE", "BUTTON DOWN"])
    ) and not is_tshirt
    
    extracted_size = str(bom_data.get("calculated_size") or bom_data.get("size") or bom_data.get("base_size") or "N/A").strip().upper()
    bom_data["calculated_size"] = extracted_size
    
    # --- THU THẬP THÔNG SỐ SPEC ---
    body_length = safe_float(bom_data.get("body_length") or bom_data.get("length") or bom_data.get("center_back_length"), default=28.0)
    sleeve_length = safe_float(bom_data.get("sleeve_length") or bom_data.get("sleeve"), default=24.0)
    chest_width = safe_float(bom_data.get("chest") or bom_data.get("chest_width") or bom_data.get("bust") or bom_data.get("half_chest"), default=20.0)
    
    skirt_hem = safe_float(bom_data.get("hem") or bom_data.get("hem_width") or bom_data.get("sweep"), default=35.0)
    raw_inseam = safe_float(bom_data.get("inseam") or bom_data.get("inseam_length"), default=30.0)
    raw_rise = safe_float(bom_data.get("front_rise") or bom_data.get("rise"), default=11.0)
    calculated_outseam = raw_inseam + raw_rise
    hip_width = safe_float(bom_data.get("hip") or bom_data.get("hip_width"), default=21.0)

    # --- ĐỒNG BỘ THÔNG SỐ VẢI ---
    w_shell = 58.0  
    s_shell_l, s_shell_w = 3.0, 3.0 
    eff_val = default_eff
    
    chat_text = ""
    if "chat_history" in st.session_state and len(st.session_state.chat_history) > 1:
        user_messages = [msg["content"] for msg in st.session_state.chat_history if msg["role"] == "user"]
        if user_messages: chat_text = str(user_messages[-1]).lower()

    width_match = re.search(r'(?:khổ|kho)\s*(\d+)', chat_text)
    if width_match: w_shell = float(width_match.group(1))
        
    shrink_2d_match = re.search(r'(?:co rút|co rut)\s*(\d+)\s*[-–]\s*(\d+)', chat_text)
    if shrink_2d_match:
        s_shell_l = float(shrink_2d_match.group(1))
        s_shell_w = float(shrink_2d_match.group(2))

    if "bom_rows" in bom_data and isinstance(bom_data["bom_rows"], list):
        for row in bom_data["bom_rows"]:
            c_type = str(row.get("component_type", "")).upper()
            placement = str(row.get("placement", "")).upper()
            if any(k in placement for k in ["BODY", "SHELL", "MAIN", "THÂN", "FABRIC"]) or any(k in c_type for k in ["SHELL", "DENIM", "VẢI CHÍNH", "MAIN"]):
                if not width_match:
                    width_parsed = safe_float(row.get("fabric_width_inch"), default=0.0)
                    if width_parsed > 0: w_shell = width_parsed
                if not shrink_2d_match:
                    s_shell_l = safe_float(row.get("shrinkage_warp_pct"), default=3.0)
                    s_shell_w = safe_float(row.get("shrinkage_weft_pct"), default=3.0)

    clean_rows = []
    if "bom_rows" in bom_data and isinstance(bom_data["bom_rows"], list):
        for idx, row in enumerate(bom_data["bom_rows"], start=1):
            c_type = str(row.get("component_type", "")).upper()
            placement = str(row.get("placement", "")).upper()
            
            if any(k in c_type or k in placement for k in [
                "CHỈ", "THREAD", "ZIPPER", "DÂY KÉO", "BUTTON", "NÚT", "LABEL", "MÁC", "TAG", "CORD", "CHUN"
            ]):
                continue
                
            row_status = "PASS"
            notes_log = ""
            final_gross_yards = 0.0
            
            if any(k in placement for k in ["BODY", "SHELL", "MAIN", "THÂN", "FABRIC"]) or any(k in c_type for k in ["SHELL", "DENIM", "VẢI CHÍNH", "MAIN"]):
                
                eff_val = max(82.0, min(eff_val, 92.0))
                cutable_w = w_shell - 1.5
                
                # CHUẨN HÓA TIẾNG ANH BIẾN CO RÚT (WARP/WEFT)
                shrink_factor_warp = 1.0 + (s_shell_l / 100.0)
                shrink_factor_weft = 1.0 + (s_shell_w / 100.0)
                wastage_factor = 1.04 
                
                # --- TOÁN HỌC DIỆN TÍCH THEO PHÂN LOẠI SẢN PHẨM ---
                if is_jacket:
                    total_length_inch = (body_length * 2) + sleeve_length + 4.0
                    width_factor_inch = (chest_width * 2) + 5.0
                    total_area_sq_in = total_length_inch * width_factor_inch
                    base_consumption_yds = (total_area_sq_in / (cutable_w * 36.0)) / (eff_val / 100.0)
                    final_gross_yards = base_consumption_yds * shrink_factor_warp * shrink_factor_weft * wastage_factor
                    final_gross_yards = max(1.65, min(final_gross_yards, 2.65))
                    
                elif is_pant:
                    total_length_inch = calculated_outseam + 3.0
                    width_factor_inch = (hip_width * 2) + 6.0
                    total_area_sq_in = total_length_inch * width_factor_inch
                    base_consumption_yds = (total_area_sq_in / (cutable_w * 36.0)) / (eff_val / 100.0)
                    final_gross_yards = base_consumption_yds * shrink_factor_warp * shrink_factor_weft * wastage_factor
                    final_gross_yards = max(1.15, min(final_gross_yards, 1.75))
                    
                elif is_dress:
                    # ĐẦM VÁY: Tăng bọc dư rập lên +6.0 inch để phủ đủ chiều dài Maxi và cụm thân trên
                    total_length_inch = body_length + 6.0  
                    width_factor_inch = (skirt_hem * 2) + 4.0 
                    total_area_sq_in = total_length_inch * width_factor_inch
                    base_consumption_yds = (total_area_sq_in / (cutable_w * 36.0)) / (eff_val / 100.0)
                    final_gross_yards = base_consumption_yds * shrink_factor_warp * shrink_factor_weft * wastage_factor
                    final_gross_yards = max(1.45, min(final_gross_yards, 3.25))
                    
                elif is_tshirt:
                    total_length_inch = (body_length * 2) + 3.0
                    width_factor_inch = (chest_width * 2) + 3.0
                    total_area_sq_in = total_length_inch * width_factor_inch
                    base_consumption_yds = (total_area_sq_in / (cutable_w * 36.0)) / (eff_val / 100.0)
                    final_gross_yards = base_consumption_yds * shrink_factor_warp * shrink_factor_weft * wastage_factor
                    final_gross_yards = max(0.65, min(final_gross_yards, 1.35))
                    
                elif is_shirt:
                    total_length_inch = (body_length * 2) + sleeve_length + 3.5
                    width_factor_inch = (chest_width * 2) + 4.5
                    total_area_sq_in = total_length_inch * width_factor_inch
                    base_consumption_yds = (total_area_sq_in / (cutable_w * 36.0)) / (eff_val / 100.0)
                    final_gross_yards = base_consumption_yds * shrink_factor_warp * shrink_factor_weft * wastage_factor
                    final_gross_yards = max(1.15, min(final_gross_yards, 1.95))
                    
                else:
                    final_gross_yards = 1.40
                
                final_gross_yards = round(final_gross_yards, 3)
                notes_log = f"Đã quy đổi hình học, bù co rút Warp x Weft, hao hụt xưởng 4%"
                
                # --- PHÂN TẦNG VALIDATION CẢNH BÁO ĐỊNH MỨC ---
                if final_gross_yards > 2.8:
                    row_status = "CRITICAL"
                elif final_gross_yards > 2.2:
                    row_status = "WARNING"
                else:
                    row_status = "PASS"
            
            elif any(k in placement for k in ["LINING", "FUSING", "POCKETING", "LÓT", "DỰNG", "KEO"]):
                if is_jacket or is_dress: final_gross_yards = 0.65
                elif is_pant or is_shirt: final_gross_yards = 0.25
                else: final_gross_yards = 0.15
                notes_log = "Định mức cụm keo dựng dựng phối"

            row["calculated_gross_consumption_yds"] = final_gross_yards
            row["status"] = row_status
            row["reason_or_logs"] = notes_log
            clean_rows.append(row)
            
    bom_data["bom_rows"] = clean_rows
    return bom_data









# =====================================================================
# LÕI ENGINE 2: AI VISION PARSER KẾT HỢP BỘ LỌC REGEX ĐÈ SỐ Ô CHAT REALS
# =====================================================================
import re  # Gọi thư viện quét chuỗi văn bản hệ thống [INDEX]

def ai_gemini_vision_pdf_parser(pdf_bytes, user_custom_prompt) -> dict:
    try:
        if "GEMINI_API_KEY" in st.secrets: genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        elif "gemini" in st.secrets: genai.configure(api_key=st.secrets["gemini"].get("api_key", ""))
        else: return {"error": "Chưa cấu hình GEMINI_API_KEY trong Streamlit Secrets."}
        
        pdf_blob = {"mime_type": "application/pdf", "data": pdf_bytes}
        
        json_schema = {
            "type": "OBJECT",
            "properties": {
                "style_code": {"type": "STRING"}, "style_name": {"type": "STRING"}, "description": {"type": "STRING"}, "calculated_size": {"type": "STRING"},
                "inseam": {"type": "STRING"}, "front_rise": {"type": "STRING"}, "hip": {"type": "STRING"},
                "body_length": {"type": "STRING"}, "sleeve_length": {"type": "STRING"},
                "consumption_type": {"type": "STRING"},
                "bom_rows": {
                    "type": "ARRAY",
                    "items": {
                        "type": "OBJECT",
                        "properties": {
                            "component_type": {"type": "STRING"}, "placement": {"type": "STRING"},
                            "fabric_width_inch": {"type": "STRING"}, "shrinkage_warp_pct": {"type": "STRING"}, "marker_efficiency_pct": {"type": "STRING"}
                        },
                        "required": ["component_type", "placement"]
                    }
                }
            },
            "required": ["style_code", "bom_rows"]
        }

        base_prompt = f"""
        Bạn là Trợ lý AI bóc tách tài liệu kỹ thuật ngành may mặc chuyên nghiệp (Techpack & BOM Parser).
        Nhiệm vụ: ĐỌC bảng BOM, bảng thông số kích thước POM trong file PDF để trích xuất siêu dữ liệu, tuyệt đối không tự tính Yards.
        Gạt bỏ hoàn toàn chỉ may và dây kéo zipper khỏi mảng đầu ra.
        """

        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content(
            [pdf_blob, base_prompt],
            generation_config=types.GenerationConfig(response_mime_type="application/json", response_schema=json_schema, temperature=0.1)
        )
        raw_json = json.loads(response.text.strip())
        
        # 🚨 BỘ LỌC CỨNG PYTHON (TEXT REGEX PARSER) - ĐÈ SỐ LIỆU Ô CHAT: [INDEX]
        # Nếu phát hiện người dùng chỉ định thông số ở ô chat, Python tự động bắt số gán đè trực tiếp [INDEX]
        prompt_clean = str(user_custom_prompt).lower().replace(" ", "")
        
        # Quét tìm con số đi sau chữ "khổ"
        match_width = re.search(r'khổ(\d+)', prompt_clean)
        # Quét tìm con số co dọc đi sau chữ "co" hoặc "rút"
        match_warp = re.search(r'(?:co|rút|dọc)(\d+)', prompt_clean)
        # Quét tìm con số co ngang đi sau chữ "ngang"
        match_weft = re.search(r'ngang(\d+)', prompt_clean)
        
        # Nếu trong mảng bom_rows có dữ liệu vải chính, cưỡng ép gán số ô chat vào [INDEX]
        if "bom_rows" in raw_json and isinstance(raw_json["bom_rows"], list):
            for row in raw_json["bom_rows"]:
                c_t = str(row.get("component_type", "")).upper()
                p_l = str(row.get("placement", "")).upper()
                
                # Định vị dòng vải chính để đè số [INDEX]
                if any(k in p_l for k in ["BODY", "SHELL", "MAIN", "THÂN"]) or any(k in c_t for k in ["SHELL", "DENIM", "VẢI CHÍNH", "POLY"]):
                    if match_width: 
                        row["fabric_width_inch"] = str(match_width.group(1))
                    if match_warp: 
                        row["shrinkage_warp_pct"] = str(match_warp.group(1)) + "%"
                    if match_weft: 
                        row["shrinkage_weft_pct"] = str(match_weft.group(1)) + "%"
                        
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
                
                final_outseam = parsed_result.get('outseam') or parsed_result.get('outseam_inch') or parsed_result.get('length') or 'N/A'
                ai_response_text = f"**🤖 HỆ THỐNG ĐÃ XỬ LÝ XONG FILE:** `{st.session_state.saved_pdf_name}`\n\n* **Mã Style:** {parsed_result.get('style_code', 'N/A')} | **Tên hàng:** {parsed_result.get('style_name', 'N/A')}\n* **Mô tả:** {parsed_result.get('description', 'N/A')}\n* **Size bóc được:** `{parsed_result.get('calculated_size', 'N/A')}` | **Inseam:** `{parsed_result.get('inseam', 'N/A')}\"` | **Front Rise:** `{parsed_result.get('front_rise', 'N/A')}\"`"
                st.session_state.chat_history.append({"role": "assistant", "content": ai_response_text})
            else:
                st.session_state.chat_history.append({"role": "assistant", "content": f"❌ Lỗi: {parsed_result.get('error', 'Lỗi dữ liệu')}"})
        st.rerun()
# =====================================================================
# KHỐI HIỂN THỊ VÀ KHỞI TẠO BIỂU MẪU ĐỒ HỌA EXCEL PHONG PHÚ (.XLSX)
# =====================================================================
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
            status_display = "🔴 CRITICAL" if status_raw == "CRITICAL" else ("🟡 WARNING" if status_raw == "WARNING" else "🟢 PASS")
                
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
        
        # Gọi thư viện openpyxl dựng form xuất xưởng Phong Phú cao cấp
        from openpyxl import Workbook
        from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
        from openpyxl.utils import get_column_letter
        import io
        
        wb = Workbook()
        ws = wb.active
        ws.title = "BẢNG ĐỊNH MỨC KỸ THUẬT"
        
        # VÁ LỖI QUAN TRỌNG: Sửa lại cách mở ô lưới Excel phẳng, xóa bỏ hoàn toàn dấu ngoặc vuông [0] lỗi list
        ws.sheet_view.showGridLines = True  # [INDEX]
        
        # Cấu hình thiết kế đồ họa bảng tính
        font_header_comp = Font(name="Arial", size=11, bold=True)
        font_title = Font(name="Arial", size=14, bold=True, color="1F497D")
        font_label = Font(name="Arial", size=10, bold=True)
        font_data = Font(name="Arial", size=10, bold=False)
        font_table_header = Font(name="Arial", size=9, bold=True)
        
        thin_side = Side(border_style="thin", color="000000")
        border_all = Border(left=thin_side, right=thin_side, top=thin_side, bottom=thin_side)
        header_fill = PatternFill(start_color="DCE6F1", end_color="DCE6F1", fill_type="solid") # Màu xanh dương nhạt thương hiệu
        
        # Ghi khối tiêu đề biên bản góc trái trên cùng
        ws["B2"] = "CTY CỔ PHẦN QUỐC TẾ PHONG PHÚ"
        ws["B2"].font = font_header_comp
        ws["B3"] = "Phòng Kỹ Thuật"
        ws["B3"].font = Font(name="Arial", size=10, italic=True, bold=True)
        
        # Merge ô căn giữa chữ hoa lớn tiêu đề chính
        ws.merge_cells("B5:L5")
        ws["B5"] = "BẢNG ĐỊNH MỨC KỸ THUẬT (APPROVED CONSUMPTION)"
        ws["B5"].font = font_title
        ws["B5"].alignment = Alignment(horizontal="center", vertical="center")
        
        # Đổ thông số quản trị hệ thống
        headers_info = [
            ("B7", "CUSTOMER:", "C7", "REITMANS"),
            ("B8", "STYLE:", "C8", str(st.session_state.gemini_parsed_bom_data.get('style_code', 'N/A'))),
            ("B9", "BOCK PATTERN:", "C9", "NONE"),
            ("B10", "SEASON:", "C10", "NONE"),
            ("B11", "FACTORY:", "C11", "NONE")
        ]
        
        for lbl_cell, lbl_txt, val_cell, val_txt in headers_info:
            ws[lbl_cell] = lbl_txt
            ws[lbl_cell].font = font_label
            ws[val_cell] = val_txt
            ws[val_cell].font = font_data
            ws[lbl_cell].border = Border(bottom=thin_side)
            ws[val_cell].border = Border(bottom=thin_side)
            
        # Tiêu đề lưới cột dữ liệu Phong Phú gán ở dòng 13
        headers = [
            "STT", "Fabric type", "Fabric code", "Fabric Depictions Fabric", 
            "Cuttable", "Cons", "Shrinkage (% RẬP dọc)", "Shrinkage (% RẬP ngang)", 
            "Hiệu suất sơ đồ", "Unit", "Noted"
        ]
        
        for col_num, header_title in enumerate(headers, start=2):
            cell = ws.cell(row=13, column=col_num)
            cell.value = header_title
            cell.font = font_table_header
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cell.border = border_all
            
        # Ghi các dòng định mức đã qua giải thuật Python
        current_row = 14
        for idx, row in enumerate(bom_rows, start=1):
            ws.cell(row=current_row, column=2, value=idx).alignment = Alignment(horizontal="center")
            ws.cell(row=current_row, column=3, value=row.get("component_type", "N/A"))
            ws.cell(row=current_row, column=4, value="NONE")
            ws.cell(row=current_row, column=5, value=str(st.session_state.gemini_parsed_bom_data.get('description', 'NONE')))
            ws.cell(row=current_row, column=6, value=safe_float(row.get("fabric_width_inch"), 58.0)).alignment = Alignment(horizontal="center")
            ws.cell(row=current_row, column=7, value=safe_float(row.get("gross_consumption_yds_pc"), 0.0)).alignment = Alignment(horizontal="right")
            ws.cell(row=current_row, column=8, value=str(row.get("shrinkage_warp_pct", "0%"))).alignment = Alignment(horizontal="center")
            ws.cell(row=current_row, column=9, value=str(row.get("shrinkage_weft_pct", "0%"))).alignment = Alignment(horizontal="center")
            ws.cell(row=current_row, column=10, value=str(row.get("marker_efficiency_pct", "88%"))).alignment = Alignment(horizontal="center")
            ws.cell(row=current_row, column=11, value="YDS/PC").alignment = Alignment(horizontal="center")
            ws.cell(row=current_row, column=12, value=row.get("notes", ""))
            
            # Format kẻ khung lưới và bôi màu alert cảnh báo trực tiếp lên ô tính
            for col_idx in range(2, 13):
                c = ws.cell(row=current_row, column=col_idx)
                c.font = font_data
                c.border = border_all
                if row.get("validation_status") == "WARNING":
                    c.fill = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid")
                elif row.get("validation_status") == "CRITICAL":
                    c.fill = PatternFill(start_color="FCE4D6", end_color="FCE4D6", fill_type="solid")
            current_row += 1
            
        # Duyệt cột theo dải số thứ tự chuẩn openpyxl từ cột B (2) đến L (12)
        for col_idx in range(2, 13):
            max_len = 0
            col_letter = get_column_letter(col_idx)
            for row_idx in range(13, current_row):
                cell_val = ws.cell(row=row_idx, column=col_idx).value
                if cell_val:
                    max_len = max(max_len, len(str(cell_val)))
            ws.column_dimensions[col_letter].width = max(max_len + 3, 11)
            
        # Vẽ cụm ký tên biên bản đóng chân
        ws.cell(row=current_row+2, column=4, value="Approved").font = font_label
        ws.cell(row=current_row+2, column=9, value="Issued By Consumption").font = font_label
        
        # Biên dịch luồng dữ liệu nhị phân xuất nút bấm tải file màu sắc chuẩn form hãng
        excel_data = io.BytesIO()
        wb.save(excel_data)
        excel_data.seek(0)
        
        st.download_button(
            label="📥 TẢI BIỂU MẪU ĐỊNH MỨC KỸ THUẬT PHONG PHÚ (.XLSX)",
            data=excel_data,
            file_name=f"BOM_Approved_Report_{st.session_state.gemini_parsed_bom_data.get('style_code', 'Style')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
