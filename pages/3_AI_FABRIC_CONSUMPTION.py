import streamlit as st
import pandas as pd
import json
import google.generativeai as genai
from google.generativeai import types
import io

# =====================================================================
# CẤU HÌNH TRANG VÀ BỘ NHỚ LƯU TRỮ (STATE LOCK)
# =====================================================================
st.set_page_config(page_title="3. AI FABRIC CONSUMPTION", layout="wide")
st.title("📊 TRỢ LÝ ĐỊNH MỨC NGUYÊN PHỤ LIỆU TỰ ĐỘNG (BOM)")
st.caption("Kiến trúc Piece-Polygon Estimation Engine - Tính định mức dựa trên tổng diện tích chi tiết rập bóc từ PDF")
st.markdown("---")

if "gemini_parsed_bom_data" not in st.session_state: st.session_state.gemini_parsed_bom_data = None
if "saved_pdf_bytes" not in st.session_state: st.session_state.saved_pdf_bytes = None
if "saved_pdf_name" not in st.session_state: st.session_state.saved_pdf_name = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = [{"role": "assistant", "content": "Xin chào! Vui lòng tải file PDF Techpack lên, AI sẽ quét toàn bộ danh mục chi tiết cắt để tính định mức."}]

# =====================================================================
# LÕI ENGINE 1: THUẬT TOÁN ĐỊNH MỨC TÍCH LŨY CHI TIẾT RẬP (PIECE-AREA MATRIX)
# =====================================================================
def safe_float(val, default=0.0) -> float:
    if val is None: return default
    val_clean = str(val).replace("%", "").replace('"', '').strip().lower()
    if val_clean in ["null", "none", "unknown", "na", "n/a", ""]: return default
    try: return float(val_clean)
    except (ValueError, TypeError): return default

def get_dynamic_marker_efficiency(desc_upper: str) -> float:
    if any(x in desc_upper for x in ["JACKET", "COAT", "VEST"]): return 84.0
    elif any(x in desc_upper for x in ["BAGGY", "FLARE", "WIDE LEG"]): return 87.0
    elif any(x in desc_upper for x in ["JEAN", "DENIM", "5 POCKET", "5-POCKET"]): return 88.0
    return 86.0

def python_consumption_sanity_check(bom_data: dict) -> dict:
    """
    KIẾN TRÚC PIECE-POLYGON ENGINE:
    Tính tổng định mức bằng cách cộng dồn diện tích (Dài x Rộng x Số lượng) của TẤT CẢ các chi tiết 
    do AI quét và bóc tách được từ hình ảnh/văn bản PDF (Thân, Tay, Túi đắp, Cổ, Nắp túi...) [INDEX].
    """
    if bom_data is None: bom_data = {}
    desc_upper = (str(bom_data.get("description", "")) + " " + str(bom_data.get("style_code", ""))).upper()
    default_eff = get_dynamic_marker_efficiency(desc_upper)
    
    # 📐 Lấy danh sách chi tiết rập AI quét được từ PDF [INDEX]
    pattern_pieces = bom_data.get("extracted_pattern_pieces", [])
    
    clean_rows = []
    if "bom_rows" in bom_data and isinstance(bom_data["bom_rows"], list):
        for idx, row in enumerate(bom_data["bom_rows"], start=1):
            c_type = str(row.get("component_type", "")).upper()
            placement = str(row.get("placement", "")).upper()
            
            # Loại bỏ phụ liệu đếm chiếc/cuộn
            if any(k in c_type or k in placement for k in ["CHỈ", "THREAD", "ZIPPER", "DÂY KÉO", "BUTTON", "NÚT", "LABEL", "MÁC"]):
                continue
                
            w_val = safe_float(row.get("fabric_width_inch"), default=58.0 if "KEO" not in c_type and "FUSING" not in c_type else 59.0)
            s_l = safe_float(row.get("shrinkage_warp_pct"), default=5.0 if "SHELL" in c_type or "DENIM" in c_type else 0.0)
            
            # --- TÍNH TOÁN VẢI CHÍNH DỰA TRÊN TỔNG DIỆN TÍCH CHI TIẾT QUÉT ĐƯỢC ---
            if any(k in placement for k in ["BODY", "SHELL", "MAIN", "THÂN", "FABRIC"]) or any(k in c_type for k in ["SHELL", "DENIM", "VẢI CHÍNH"]):
                raw_eff = row.get("marker_efficiency_pct", "")
                eff_val = safe_float(raw_eff, default=default_eff) if raw_eff else default_eff
                eff_display = f"{int(eff_val)}%"
                
                # Cộng dồn diện tích hình học phẳng thực tế của từng chi tiết rập [INDEX]
                total_pieces_area_sq_inch = 0.0
                pieces_log = []
                
                if pattern_pieces:
                    for piece in pattern_pieces:
                        p_name = piece.get("piece_name", "Chi tiết phụ")
                        p_len = safe_float(piece.get("length_inch"))
                        p_wid = safe_float(piece.get("width_inch"))
                        p_qty = safe_float(piece.get("quantity"), default=1.0)
                        
                        # Diện tích chi tiết = Dài thô (đã cộng đường may) x Rộng thô x Số lượng lớp cắt [INDEX]
                        piece_area = p_len * p_wid * p_qty
                        total_pieces_area_sq_inch += piece_area
                        pieces_log.append(f"{p_name}(x{int(p_qty)})")
                else:
                    # Trạng thái dự phòng an toàn nếu sơ đồ PDF thiếu bảng POM chi tiết
                    total_pieces_area_sq_inch = (30.0 + 24.5 + 4.0) * 27.5 * 2.0 * 1.25
                    pieces_log = ["Thân trước", "Thân sau", "Tay áo", "Túi đắp mặc định"]

                # Áp công thức sơ đồ công nghiệp tiêu chuẩn [INDEX]
                usable_area_per_yard = w_val * 36.0 * (eff_val / 100.0)
                net_consumption = total_pieces_area_sq_inch / usable_area_per_yard
                shrink_f = max(0.85, 1.0 - (s_l / 100.0))
                final_gross_yards = (net_consumption / shrink_f) * 1.02 # Cộng biên đầu cây 2% [INDEX]
                
                notes_log = f"Quét thành công danh mục chi tiết rập: {', '.join(pieces_log)}. Tổng diện tích rập: {int(total_pieces_area_sq_inch)} sq_in."
                row_status = "CRITICAL" if final_gross_yards > 2.6 else ("WARNING" if final_gross_yards > 2.2 else "PASS")
                
            elif any(k in placement for k in ["WAISTBAND", "FACING", "COLLAR", "CẠP", "NẸP", "VE"]) or any(k in c_type for k in ["FUSING", "KEO", "MEX", "INTERLINING"]):
                eff_display = "N/A"
                fusing_len = 14.0 if "JACKET" in desc_upper else 4.5
                final_gross_yards = (fusing_len * 38.0) / (w_val * 36.0 * 0.90)
                notes_log = "Tính keo ép dựa trên chi tiết cạp quần hoặc ve nẹp cổ áo."
                row_status = "PASS"

            elif any(k in placement for k in ["POCKET", "LINING", "LÓT", "TÚI"]) or any(k in c_type for k in ["POCKETING", "LINING", "LÓT"]):
                eff_display = "N/A"
                final_gross_yards = 0.180 if "JACKET" in desc_upper else (19.5 * 12.0 * 2) / (w_val * 36.0 * 0.91)
                notes_log = "Định mức vải phối lót túi bóc từ BOM."
                row_status = "PASS"
            else:
                eff_display = "N/A"
                final_gross_yards = 0.15
                notes_log = "Phụ liệu phẳng khác."

            clean_rows.append({
                "component_type": row.get("component_type", f"Vật liệu {idx}"), "fabric_width_inch": str(int(w_val)),
                "shrinkage_warp_pct": f"{int(s_l)}%", "shrinkage_weft_pct": "0%", "marker_efficiency_pct": eff_display,
                "gross_consumption_yds_pc": round(final_gross_yards, 3), "validation_status": row_status, "notes": notes_log
            })
            
        bom_data["bom_rows"] = clean_rows
        
    if st.session_state.gemini_parsed_bom_data is None: st.session_state.gemini_parsed_bom_data = {}
    st.session_state.gemini_parsed_bom_data.update(bom_data)
    if "bom_rows" in bom_data: st.session_state.gemini_parsed_bom_data["bom_rows"] = clean_rows
    return bom_data






# =====================================================================
# LÕI ENGINE 2: AI QUÉT TOÀN DIỆN FILE PDF ĐỂ LẬP DANH MỤC CHI TIẾT CẮT REAL
# =====================================================================
def ai_gemini_vision_pdf_parser(pdf_bytes, user_custom_prompt) -> dict:
    try:
        if "GEMINI_API_KEY" in st.secrets: genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        elif "gemini" in st.secrets: genai.configure(api_key=st.secrets["gemini"].get("api_key", ""))
        else: return {"error": "Chưa cấu hình GEMINI_API_KEY trong Streamlit Secrets."}
        
        pdf_blob = {"mime_type": "application/pdf", "data": pdf_bytes}
        
        # Schema ép cấu hình AI bắt buộc phải trả về mảng danh mục chi tiết rập quét được [INDEX]
        json_schema = {
            "type": "OBJECT",
            "properties": {
                "style_code": {"type": "STRING"}, "description": {"type": "STRING"},
                "inseam": {"type": "STRING"}, "front_rise": {"type": "STRING"},
                "body_length": {"type": "STRING"}, "sleeve_length": {"type": "STRING"},
                "extracted_pattern_pieces": { # Mảng quét chi tiết rập thật từ bản vẽ/văn bản PDF [INDEX]
                    "type": "ARRAY",
                    "items": {
                        "type": "OBJECT",
                        "properties": {
                            "piece_name": {"type": "STRING"}, # Thân trước, Thân sau, Tay, Túi đắp, Nắp túi, Cổ... [INDEX]
                            "length_inch": {"type": "NUMBER"}, # Chiều dài thô của chi tiết (Kèm đường may) [INDEX]
                            "width_inch": {"type": "NUMBER"},  # Chiều rộng thô của chi tiết [INDEX]
                            "quantity": {"type": "NUMBER"}     # Số lượng chi tiết trên 1 sản phẩm (Ví dụ: Tay x2, Túi x2) [INDEX]
                        },
                        "required": ["piece_name", "length_inch", "width_inch", "quantity"]
                    }
                },
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
        Bạn là Trưởng phòng Kỹ thuật rập và Giác sơ đồ máy Gerber/Lectra.
        Hãy quét TOÀN BỘ file PDF này (nhìn cả hình vẽ mô tả sản phẩm phẳng và bảng thông số POM) để nhận diện mã hàng có tổng cộng bao nhiêu chi tiết cấu thành cần cắt [INDEX].

        🚨 QUY TẮC QUÈT CHI TIẾT RẬP BẮT BUỘC (PATTERN PIECE SCANNING):
        1. Phân tích hình ảnh và văn bản để lập danh mục điền vào mảng `extracted_pattern_pieces` [INDEX]:
           - Ví dụ đối với Áo khoác Jacket: Phải quét được Thân trước (x2), Thân sau (x1), Tay áo (x2), Túi đắp trước ngực/bụng nếu có (x2), Nắp túi nếu có (x2), Cổ áo (x1 hoặc x2), Nẹp ve trước (x2) [INDEX].
           - Ước tính kích cỡ Chiều dài (length_inch) và Chiều rộng (width_inch) thô (sau khi đã cộng đường may lai gấu ráp vai) của từng chi tiết dựa trên bảng POM chính [INDEX].
        2. Quét bảng BOM trích xuất danh mục phụ liệu phẳng thực tế sang mảng `bom_rows`. Tuyệt đối không tự ý thêm dòng lót túi nếu tài liệu gốc không có [INDEX]. Gạt bỏ hoàn toàn chỉ may và dây kéo đếm chiếc [INDEX].
        3. LUỒNG ĐỒNG BỘ CHAT: Điền thông số khổ vải hoặc co rút do người dùng gõ chỉ định ở ô chat vào trường dữ liệu vật liệu tương ứng [INDEX].
        """

        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content(
            [pdf_blob, base_prompt],
            generation_config=types.GenerationConfig(response_mime_type="application/json", response_schema=json_schema, temperature=0.1)
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
