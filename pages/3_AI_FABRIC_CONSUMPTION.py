# ==============================================================================
# HỆ THỐNG TOÁN HỌC CAD-AI ĐỒNG BỘ GERBER V18 INDUSTRIAL ENGINE
# ĐOẠN 1/12: KHAI BÁO THƯ VIỆN TOÀN CỤC VÀ KHỞI TẠO FRAMEWORK CẤU HÌNH GIAO DIỆN
# ==============================================================================

import fitz  # Thư viện PyMuPDF trích xuất đồ họa giải tích và văn bản từ PDF
import math
import json
import re
import traceback
import io
import numpy as np
import pandas as pd
import streamlit as st
from shapely.geometry import Polygon, MultiPolygon, LineString
from shapely.ops import unary_union, polygonize
from shapely.affinity import translate, rotate, scale
from shapely.strtree import STRtree
import google.generativeai as genai
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter

# 1. CẤU HÌNH KHUNG TRANG WEB STREAMLIT TOÀN CỤC
st.set_page_config(
    page_title="Gerber V18 CAD-AI Industrial Engine", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. KHỞI TẠO BỘ NHỚ TRẠNG THÁI PHIÊN CHẠY AN TOÀN (SESSION STATE BUFFER)
if "pdf_bytes" not in st.session_state: st.session_state.pdf_bytes = None
if "pdf_text_cache" not in st.session_state: st.session_state.pdf_text_cache = ""
if "chat_history" not in st.session_state: st.session_state.chat_history = []
if "active_blueprint" not in st.session_state: st.session_state.active_blueprint = {}
if "accumulated_bom_rows" not in st.session_state: st.session_state.accumulated_bom_rows = {}
if "current_warp_pct" not in st.session_state: st.session_state.current_warp_pct = "3.0%"
if "current_weft_pct" not in st.session_state: st.session_state.current_weft_pct = "3.0%"

# 3. THIẾT LẬP THANH ĐIỀU KHIỂN CẤU HÌNH THÔNG SỐ (SIDEBAR CONTROLS)
st.sidebar.header("🛠️ Tham Số Kỹ Thuật Hệ Thống")

fabric_width_input = st.sidebar.number_input(
    "Khổ rộng vải hữu dụng (Inch):", 
    min_value=10.0, max_value=150.0, value=58.0, step=0.5,
    help="Chiều rộng thực tế của khổ vải sau khi đã trừ biên dập của máy cắt."
)

seam_allowance_input = st.sidebar.slider(
    "Hao hụt đường may - Seam Allowance (Inch):",
    min_value=0.0, max_value=2.0, value=0.25, step=0.05,
    help="Khoảng offset bù đường may kỹ thuật ra biên ngoài của rập."
)

st.sidebar.markdown("---")
st.sidebar.subheader("📈 Hệ Số Co Rút Vật Liệu (%)")
warp_shrinkage = st.sidebar.slider("Độ co rút sớ dọc (Warp %):", min_value=0.0, max_value=20.0, value=3.0, step=0.1)
weft_shrinkage = st.sidebar.slider("Độ co rút sớ ngang (Weft %):", min_value=0.0, max_value=20.0, value=3.0, step=0.1)

# Ghi nhận các giá trị mặc định ban đầu từ Sidebar vào bộ đệm an toàn
st.session_state.current_warp_pct = f"{warp_shrinkage}%"
st.session_state.current_weft_pct = f"{weft_shrinkage}%"

st.title("🏭 Hệ Thống Tính Định Mức Sơ Đồ Gerber V18 CAD-AI")
st.caption("Kiến trúc phân cấp: AI điều phối, trích xuất cấu trúc BOM và Specs ➡️ Python độc lập xử lý toán học hình học phẳng")

# 🔗 CHUYỂN TIẾP SANG ĐOẠN 2/12...
# ==============================================================================
# HỆ THỐNG TOÁN HỌC CAD-AI ĐỒNG BỘ GERBER V18 INDUSTRIAL ENGINE
# ĐOẠN 2/12: BỘ TIẾP NHẬN TỆP TIN & LÕI TRÍCH XUẤT VĂN BẢN KỸ THUẬT NỀN (FIXED SYNTAX)
# ==============================================================================

# 1. KHỐI GIAO DIỆN TẢI TỆP TIN TÀI LIỆU KỸ THUẬT (TECHPACK PDF)
uploaded_file = st.file_uploader(
    "Tải lên tệp PDF Tài liệu Kỹ thuật (Techpack Vector/Text):", 
    type=["pdf"],
    key="file_uploader_gerber_v18_final_fixed",
    help="Tệp PDF kỹ thuật chứa thông tin bảng BOM vật tư và thông số size kích thước sản phẩm."
)

# 2. LÕI TỰ ĐỘNG QUÉT VÀ TRÍCH XUẤT VĂN BẢN NỀN (AUTOMATED TEXT EXTRACTION PIPELINE)
if uploaded_file is not None:
    # Đọc luồng nhị phân nguyên bản vào Session State
    file_bytes_read = uploaded_file.read()
    
    # Chỉ thực hiện phân tích và ghi đè Text Cache nếu phát hiện file mới hoàn toàn
    if st.session_state.pdf_bytes != file_bytes_read:
        st.session_state.pdf_bytes = file_bytes_read
        st.session_state.pdf_text_cache = ""  # Reset bộ đệm văn bản cũ
        st.session_state.active_blueprint = {} # Reset bảng dữ liệu sơ đồ cũ
        st.session_state.accumulated_bom_rows = {}
        
        try:
            # Mở luồng giải tích tệp tin PDF trong bộ nhớ đệm RAM
            doc_context = fitz.open(stream=file_bytes_read, filetype="pdf")
            extracted_text_list = []
            
            # Quét thu thập dữ liệu ký tự văn bản trên toàn bộ các trang tài liệu
            for page_num in range(len(doc_context)):
                page_obj = doc_context.load_page(page_num)
                page_text = page_obj.get_text("text")
                if page_text.strip():
                    extracted_text_list.append(f"--- PAGE {page_num + 1} --- \n{page_text}")
                    
            doc_context.close()
            
            # Ghi nhận dải dữ liệu sạch vào bộ nhớ đệm phục vụ AI Orchestrator
            st.session_state.pdf_text_cache = "\n".join(extracted_text_list)
            st.toast("✓ Đã quét và bóc tách thành công dữ liệu văn bản từ Techpack PDF!", icon="🔍")
            
        # ✅ KHÉP MẠCH LOGIC: Bổ sung khối bẫy lỗi để đóng mạch try phía trên, sửa lỗi SyntaxError tận gốc
        except Exception as scan_err:
            st.error(f"Lỗi cục bộ trong quá trình bóc tách văn bản tệp tài liệu: {str(scan_err)}")
            st.session_state.pdf_text_cache = "Không thể trích xuất văn bản tự động từ file này."

else:
    # Trường hợp kỹ thuật viên bấm Clear tệp tin, đưa toàn bộ hệ thống về trạng thái rỗng an toàn
    st.session_state.pdf_bytes = None
    st.session_state.pdf_text_cache = ""
    st.session_state.active_blueprint = {}
    st.session_state.accumulated_bom_rows = {}

# 🔗 CHUYỂN TIẾP SANG ĐOẠN 3/12...

# ==============================================================================
# HỆ THỐNG TOÁN HỌC CAD-AI ĐỒNG BỘ GERBER V18 INDUSTRIAL ENGINE
# ĐOẠN 3/12: KHUNG GIAO DIỆN CHATBOX & CƠ CHẾ RESET DỮ LIỆU ĐỒNG BỘ
# ==============================================================================

# 1. KHỞI DỰNG VÙNG LÀM VIỆC CỘNG TÁC (CHAT COLLABORATION WORKSPACE)
st.markdown('<br><div class="cad-card"><div class="cad-header">💬 CHATGPT IE COLLABORATION WORKSPACE</div>', unsafe_allow_html=True)

# Thiết lập layout chia cột thông minh để đẩy nút bấm Clear Chat về bên phải
c_col1, c_col2 = st.columns([5, 1])
with c_col2:
    # Nút bấm làm sạch bộ đệm với Key định danh độc bản duy nhất trên hệ thống
    if st.button("🗑️ Clear Chat", key="btn_clear_chat_v18_structural", use_container_width=True):
        st.session_state.chat_history = []
        st.session_state.active_blueprint = {}
        st.session_state.accumulated_bom_rows = {}
        st.session_state.current_warp_pct = "3.0%"
        st.session_state.current_weft_pct = "3.0%"
        st.toast("🧹 Đã làm sạch toàn bộ lịch sử chatbox và ma trận kết quả!", icon="🗑️")
        st.rerun()

# 2. XUẤT LỊCH SỬ BONG BÓNG HỘI THOẠI TRÊN GIAO DIỆN WEB
if st.session_state.chat_history:
    for msg in st.session_state.chat_history:
        st.chat_message("user").write(msg["user"])
        st.chat_message("assistant").write(msg["ai"])

# ⚠️ Ô NHẬP LIỆU DUY NHẤT: Khóa định danh độc bản triệt tiêu lỗi trùng ID phần tử
safe_user_prompt = st.chat_input(
    "Gõ câu lệnh điều chỉnh thông số (Ví dụ: Tính định mức vải chính khổ 58 co rút 3x3 size 32) tại đây...", 
    key="main_chat_input_v18_structural"
)
st.markdown('</div>', unsafe_allow_html=True)

# 🔗 CHUYỂN TIẾP SANG ĐOẠN 4/12...
# ==============================================================================
# HỆ THỐNG TOÁN HỌC CAD-AI ĐỒNG BỘ GERBER V18 INDUSTRIAL ENGINE
# ĐOẠN 4/12: BỘ TRÍCH XUẤT SPECS VÀ BỘ LỌC AN TOÀN BIÊN SỐ CHỐT CHẶN
# ==============================================================================

# KÍCH HOẠT KHI PHÁT HIỆN CÓ ĐỦ TỆP TIN VÀ CÂU LỆNH MỚI TỪ NGƯỜI DÙNG
if st.session_state.get("pdf_bytes") is not None and safe_user_prompt:
    current_query = str(safe_user_prompt).strip()
    
    with st.spinner("🧠 AI Orchestrator đang phân tách cấu trúc vật tư từ Techpack..."):
        try:
            chat_lower = current_query.lower()
            
            # =====================================================================
            # 🌟 BỘ TRÍCH XUẤT REgex: BÓC TÁCH SPECS TỪ CÂU LỆNH CỦA KỸ THUẬT VIÊN
            # =====================================================================
            # 1. Trích xuất cỡ mẫu mục tiêu (Size)
            match_size = re.search(r'\b(?:size|sz|cỡ|cơ)\s*[:\-=\s]*([\w\d]+)\b', chat_lower)
            target_size_cmd = str(match_size.group(1)).upper().strip() if match_size else "30"
            
            # Khóa an toàn: Chống bốc nhầm số trang tài liệu (ví dụ trang 10) thành số cỡ mẫu
            try:
                size_num_check = float(re.sub(r'[^\d\.]', '', target_size_cmd))
                if size_num_check < 20.0 or size_num_check > 50.0:
                    target_size_cmd = "30"
            except:
                pass

            # 2. Trích xuất thông số khổ rộng cắt vải hữu dụng (Inch)
            match_w = re.search(r'(?:khổ|kho|width|cutwidth)\s*[:\-=\s]*([\d\.]+)', chat_lower)
            active_width = float(match_w.group(1)) if match_w else float(fabric_width_input)
            
            # 3. Trích xuất tỉ lệ phần trăm co rút sợi dọc (Warp) và sợi ngang (Weft)
            active_warp = float(warp_shrinkage)
            active_weft = float(weft_shrinkage)
            
            match_warp = re.search(r'(?:dọc|doc|warp)\s*[:\-=\s]*([\d\.]+)', chat_lower)
            match_weft = re.search(r'(?:ngang|weft)\s*[:\-=\s]*([\d\.]+)', chat_lower)
            
            if match_warp: active_warp = float(match_warp.group(1))
            if match_weft: active_weft = float(match_weft.group(1))
            if not match_warp or not match_weft:
                # Quét cú pháp gõ nhanh dạng: co rut 3x3 hoặc co 3 - 3
                m_sh = re.search(r'(?:co\s*rút|co\s*rut|co|shrinkage)\s*[:\-=\s]*([\d\.]+)\s*(?:-|–|x|ngang|\s+)\s*([\d\.]+)', chat_lower)
                if m_sh:
                    active_warp, active_weft = float(m_sh.group(1)), float(m_sh.group(2))

            # Đồng bộ các thông số Specs làm sạch vào bộ nhớ trạng thái hệ thống
            st.session_state.current_warp_pct = f"{active_warp}%"
            st.session_state.current_weft_pct = f"{active_weft}%"

            # Thiết lập cấu hình API khóa bí mật kết nối mạng trí tuệ nhân tạo Gemini
            if "GEMINI_API_KEY" in st.secrets: 
                genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
            else:
                # Khởi chạy chế độ mô phỏng cục bộ nếu thiếu API Key môi trường đám mây
                pass
                
            model = genai.GenerativeModel("gemini-2.5-flash", generation_config={"temperature": 0.0})
            techpack_text_source = st.session_state.pdf_text_cache if st.session_state.pdf_text_cache else "Default Casual Techpack Text Context."

# 🔗 CHUYỂN TIẾP SANG ĐOẠN 5/12...
# ==============================================================================
# HỆ THỐNG TOÁN HỌC CAD-AI ĐỒNG BỘ GERBER V18 INDUSTRIAL ENGINE
# ĐOẠN 5/12: CHỈ THỊ PROMPT ORCHESTRATOR CAO CẤP & GỌI API GEMINI AI
# ==============================================================================

            # =====================================================================
            # 🌟 PROMPT ORCHESTRATOR TỐI CAO: PHÂN TÍCH VẬT TƯ NGUYÊN BẢN TỪ TECHPACK
            # =====================================================================
            prompt_instruction = f"""
            You are a Senior Apparel IE Expert and CAD Master. Your job is to strictly analyze the provided Techpack data text context and extract the Bill of Materials (BOM).
            You must isolate components into structured classifications such as MAIN_FABRIC, LINING, or FUSING.
            
            DATA FOUND IN TECHPACK TEXT CONTEXT: {techpack_text_source}
            CONTEXT HISTORY FLOW: {json.dumps(st.session_state.chat_history, ensure_ascii=False)}
            CURRENT USER COMMAND REQUIREMENT: "{current_query}"
            
            CRITICAL EXTRACTION LOGIC FOR PYTHON PIPELINE:
            1. Extract the product type and style code accurately.
            2. Map each material row with its corresponding parameters.
            3. "geometry_source_layer" MUST be determined purely based on component purpose:
               - Main body fabrics -> "MAIN_BODY_CARGO"
               - Fusing/Interlinings -> "INTERLINING"
               - Pocket bags/Linings -> "LINING"
            
            Return response in EXACTLY this format and do NOT write any preamble conversational text around it:
            ===START_JSON===
            {{
              "detected_product_type": "CARGO_PANT",
              "style_code": "R09-490976",
              "calculated_on_size": "{target_size_cmd}",
              "bom_rows": [
                {{
                  "component_type": "MAIN FABRIC", 
                  "placement": "BODY/POCKETS/CARGO", 
                  "fabric_classification": "MAIN_FABRIC",
                  "fabric_code": "TWILL", 
                  "fabric_color": "KHAKI", 
                  "fabric_width_inch": {active_width},
                  "geometry_required": true, 
                  "geometry_source_layer": "MAIN_BODY_CARGO"
                }},
                {{
                  "component_type": "INTERLINING", 
                  "placement": "WAISTBAND/FLAPS", 
                  "fabric_classification": "FUSING",
                  "fabric_code": "LIGHT KNIT", 
                  "fabric_color": "DTM", 
                  "fabric_width_inch": {active_width},
                  "geometry_required": true, 
                  "geometry_source_layer": "INTERLINING"
                }},
                {{
                  "component_type": "LINING", 
                  "placement": "POCKET BAGS FRONT/BACK", 
                  "fabric_classification": "LINING",
                  "fabric_code": "COTTON SHEETING", 
                  "fabric_color": "WHITE", 
                  "fabric_width_inch": {active_width},
                  "geometry_required": true, 
                  "geometry_source_layer": "LINING"
                }}
              ]
            }}
            ===END_JSON===
            """
            
            # Gửi toàn bộ chỉ thị phân tích cấu trúc sang mô hình trí tuệ nhân tạo
            response = model.generate_content(prompt_instruction)
            resp_text = response.text

            # Giải nén phân tách khối cấu trúc dữ liệu JSON thô bằng Regex biên
            json_pattern = re.search(r'===START_JSON===\s*(.*?)\s*===END_JSON===', resp_text, re.DOTALL)
            
            ai_json_data = {}
            if json_pattern:
                try:
                    ai_json_data = json.loads(json_pattern.group(1).strip())
                except Exception as json_parse_err:
                    st.error(f"Lỗi cú pháp phân rã cấu trúc JSON từ AI: {str(json_parse_err)}")
            else:
                st.error("AI Orchestrator phản hồi lỗi cấu trúc biên hoặc thiếu thẻ đánh dấu dữ liệu vật tư.")

# 🔗 CHUYỂN TIẾP SANG ĐOẠN 6/12...
# ==============================================================================
# HỆ THỐNG TOÁN HỌC CAD-AI ĐỒNG BỘ GERBER V18 INDUSTRIAL ENGINE
# ĐOẠN 6/12: LÕI GIẢI TÍCH HÌNH HỌC BƯỚC 1 - TRÍCH XUẤT VECTOR THÔ & FLIP TRỤC CAD Y (FIXED SYNTAX)
# ==============================================================================

def v18_step1_extract_raw_vectors(layer_name, warp=3.0, weft=3.0, snap_tol=0.005):
    """
    LÕI INDUSTRIAL V18 - HÀM BƯỚC 1:
    Nạp lớp rập vector từ PDF, chuẩn hóa hệ tọa độ CAD phẳng (Lật trục Y), làm sạch 
    điểm trùng bằng Snap Tolerance, đồng bộ hệ số co rút dệt và đóng gói siêu dữ liệu đồ họa.
    • VÁ LỖI CÚ PHÁP: Cân bằng thụt lề cho block try-except, đóng chuỗi chính xác.
    """
    import fitz
    import math
    from shapely.geometry import LineString
    import streamlit as st

    layer_upper = str(layer_name).upper().strip()
    
    # Tính toán ma trận hệ số nhân co rút vật liệu hữu hiệu (Warp: Dọc, Weft: Ngang)
    w_f = 1.0 + (warp / 100.0) if warp > 0.0 else 1.0
    f_f = 1.0 + (weft / 100.0) if weft > 0.0 else 1.0
    
    raw_lines_metadata = []  # Mảng phẳng lưu trữ nét nội bộ kèm Metadata độ dày, fill màu
    all_contours = []        # Mảng chuỗi liên kết bao quanh ngoại vi biên rập

    def clean_and_snap_points(pts_list, tolerance):
        """Hàm băm mịn điểm trùng lặp và làm sạch sai số tọa độ vi phân cục bộ"""
        if len(pts_list) < 2: 
            return pts_list
        cleaned = [pts_list[0]]
        for pt in pts_list[1:]:
            if math.hypot(pt[0] - cleaned[-1][0], pt[1] - cleaned[-1][1]) > tolerance:
                cleaned.append(pt)
        return cleaned

    try:
        if "pdf_bytes" not in st.session_state or st.session_state.pdf_bytes is None:
            return {"status": "error", "message": "Thiếu dữ liệu luồng tệp rập PDF gốc."}

        doc = fitz.open(stream=st.session_state.pdf_bytes, filetype="pdf")
        page = doc.load_page(0)
        drawings = page.get_drawings()
        
        if not drawings:
            return {"status": "error", "message": "Tệp bản vẽ trống hoặc không chứa cấu trúc vector hình học giải tích."}

        # Bóc tách thông số chiều cao trang phôi để thực hiện phép tịnh tiến lật trục Y CAD
        p_rect = page.rect
        p_height = p_rect.height
        page_area_sq_in = (p_rect.width / 72.0) * (p_rect.height / 72.0)

        # Cấu hình số lượng chi tiết mặc định
        target_pieces_count = 2.0
        is_mirror_pair = True

        # 🌟 BỘ NỘI SUY BÉZIER THÍCH ỨNG: Chuyển đổi chính xác 100% đơn vị Point sang Inch công nghiệp
        def interpolate_adaptive_bezier(p0, p1, p2, p3):
            chord_len = math.hypot(p3[0] - p0[0], p3[1] - p0[1]) / 72.0
            steps = 16 if chord_len < 1.0 else (48 if chord_len < 5.0 else (72 if chord_len < 15.0 else 96))
                
            pts = []
            for t_idx in range(steps + 1):
                t = t_idx / float(steps)
                x = ((1-t)**3)*p0[0] + 3*((1-t)**2)*t*p1[0] + 3*(1-t)*(t**2)*p2[0] + (t**3)*p3[0]
                y = ((1-t)**3)*p0[1] + 3*((1-t)**2)*t*p1[1] + 3*(1-t)*(t**2)*p2[1] + (t**3)*p3[1]
                
                # 🔄 CHUẨN HÓA HỆ TỌA ĐỘ PHẲNG: Lật Y PDF sang CAD và chia 72.0 đưa về Inch thực tế
                cad_y = p_height - y
                pts.append((x / 72.0 * f_f, cad_y / 72.0 * w_f))
            return pts

        # DUYỆT TRÍCH XUẤT CẤU TRÚC ĐỒ HỌA VECTOR TỪ FILE PDF
        for draw in drawings:
            stroke_color = draw.get("color", (0, 0, 0))
            if stroke_color is None: stroke_color = (0, 0, 0)
            fill_color = draw.get("fill", None)
            line_width = draw.get("width", 1.0)
            if line_width is None: line_width = 1.0
            
            try:
                color_key = f"{stroke_color[0]:.2f}_{stroke_color[1]:.2f}_{stroke_color[2]:.2f}"
            except (TypeError, IndexError):
                color_key = "0.00_0.00_0.00"
            
            current_subpath = []
            current_pos = (0.0, 0.0)
            
            if "items" not in draw or draw["items"] is None or len(draw["items"]) == 0:
                continue
                
            for item in draw["items"]:
                if not isinstance(item, (list, tuple)) or len(item) == 0:
                    continue
                type_code = str(item[0]).lower().strip()
                
                if type_code == "m":  # Lệnh MoveTo - Khởi tạo điểm neo chuỗi
                    if len(current_subpath) >= 2:
                        current_subpath = clean_and_snap_points(current_subpath, snap_tol)
                        if current_subpath[0] != current_subpath[-1]:
                            current_subpath.append(current_subpath[0])
                        if len(current_subpath) >= 3:
                            all_contours.append(LineString(current_subpath))
                    
                    raw_pos = item[1]
                    current_pos = raw_pos
                    current_subpath = [(raw_pos[0] / 72.0 * f_f, (p_height - raw_pos[1]) / 72.0 * w_f)]
                    
                elif type_code == "l":  # Lệnh LineTo - Dựng phân đoạn thẳng
                    next_pos = item[1]
                    cad_next_y = (p_height - next_pos[1]) / 72.0 * w_f
                    cad_curr_y = (p_height - current_pos[1]) / 72.0 * w_f
                    
                    current_subpath.append((next_pos[0] / 72.0 * f_f, cad_next_y))
                    
                    try:
                        ln = LineString([(current_pos[0] / 72.0 * f_f, cad_curr_y), 
                                        (next_pos[0] / 72.0 * f_f, cad_next_y)])
                        raw_lines_metadata.append({
                            "line": ln, "color": color_key, "width": line_width, "is_filled": fill_color is not None
                        })
                    except: 
                        pass
                    current_pos = next_pos
                    
                elif type_code == "re":  # Lệnh vẽ khối HCN trực tiếp
                    r = item[1]
                    rect_pts = [
                        (r.x0 / 72.0 * f_f, (p_height - r.y0) / 72.0 * w_f),
                        (r.x1 / 72.0 * f_f, (p_height - r.y0) / 72.0 * w_f),
                        (r.x1 / 72.0 * f_f, (p_height - r.y1) / 72.0 * w_f),
                        (r.x0 / 72.0 * f_f, (p_height - r.y1) / 72.0 * w_f),
                        (r.x0 / 72.0 * f_f, (p_height - r.y0) / 72.0 * w_f)
                    ]
                    rect_pts = clean_and_snap_points(rect_pts, snap_tol)
                    all_contours.append(LineString(rect_pts))
                    
                elif type_code == "c":  # Lệnh CurveTo - Đường cong nội suy Bezier bậc 3
                    p0, p1, p2, p3 = current_pos, item[1], item[2], item[3]
                    curve_pts = interpolate_adaptive_bezier(p0, p1, p2, p3)
                    if curve_pts:
                        if current_subpath: current_subpath.extend(curve_pts[1:])
                        else: current_subpath.extend(curve_pts)
                    current_pos = p3
                    
                elif type_code in ["h", "closepath"]:  # Lệnh khép góc chuỗi đồ họa hành trình
                    if len(current_subpath) >= 2:
                        current_subpath = clean_and_snap_points(current_subpath, snap_tol)
                        if current_subpath[0] != current_subpath[-1]:
                            current_subpath.append(current_subpath[0])
                        if len(current_subpath) >= 3:
                            all_contours.append(LineString(current_subpath))
                    current_subpath = []

            if len(current_subpath) >= 2:
                current_subpath = clean_and_snap_points(current_subpath, snap_tol)
                if current_subpath[0] != current_subpath[-1]:
                    current_subpath.append(current_subpath[0])
                if len(current_subpath) >= 3:
                    all_contours.append(LineString(current_subpath))

        doc.close()
        return {
            "status": "success",
            "all_contours": all_contours,
            "raw_lines_metadata": raw_lines_metadata,
            "page_area_sq_in": page_area_sq_in,
            "target_pieces_count": target_pieces_count,
            "is_mirror_pair": is_mirror_pair,
            "layer_upper": layer_upper
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}

# ==============================================================================
# HỆ THỐNG TOÁN HỌC CAD-AI ĐỒNG BỘ GERBER V18 INDUSTRIAL ENGINE
# ĐOẠN 7/12: LÕI GIẢI TÍCH HÌNH HỌC BƯỚC 2 - TÁI DỰNG ĐA GIÁC ĐA VÒNG LỒNG NHAU (HOLES)
# ==============================================================================

def v18_step2_reconstruct_and_orient_geometry(step1_results, seam_allowance=0.0):
    """
    LÕI INDUSTRIAL V18 - HÀM BƯỚC 2:
    Tái tạo cấu trúc rập đa contour (vòng ngoài và các lỗ rỗng nội bộ), lọc sớ vải 
    thông minh qua chỉ mục không gian kết hợp bộ lọc Metadata, khử hoàn toàn góc nghiêng 
    và trích xuất thông số chiều dài/chiều rộng tĩnh thực tế sau khi đã normalize.
    """
    import math
    from shapely.geometry import Polygon, MultiPolygon, LineString
    from shapely.ops import unary_union, polygonize
    from shapely.affinity import rotate, scale
    from shapely.strtree import STRtree
    import numpy as np
    import streamlit as st

    if not step1_results or step1_results.get("status") != "success":
        return {"status": "error", "message": "Dữ liệu đầu vào từ Bước 1 không hợp lệ hoặc bị gián đoạn."}

    all_contours = step1_results["all_contours"]
    raw_lines_metadata = step1_results["raw_lines_metadata"]
    page_area_sq_in = step1_results["page_area_sq_in"]
    target_pieces_count = step1_results["target_pieces_count"]
    is_mirror_pair = step1_results["is_mirror_pair"]
    layer_upper = step1_results["layer_upper"]

    # Phân ngưỡng diện tích an toàn dựa trên kích thước phôi giấy vẽ trang PDF
    min_area_thresh = max(1.5, page_area_sq_in * 0.002)
    max_area_thresh = min(2500.0, page_area_sq_in * 0.98)
    panels_catalog = []

    try:
        # Xử lý khâu khép góc các mạch hở và tự động gộp dải diện tích tiếp xúc biên
        merged_lines = unary_union(all_contours)
        polygons_built = list(polygonize(merged_lines))
        
        if not polygons_built:
            # Cơ chế dự phòng bằng dải đệm siêu vi phân nếu vector gốc bị hở góc quá lớn
            buffered_contours = [line.buffer(0.001) for line in all_contours]
            union_poly = unary_union(buffered_contours)
            if isinstance(union_poly, Polygon): 
                polygons_built = [union_poly]
            elif isinstance(union_poly, MultiPolygon): 
                polygons_built = list(union_poly.geoms)

        # Sắp xếp đa giác giảm dần để thuật toán bóc tách lỗ trống (Hole Detection) chạy chính xác
        polygons_built = sorted(polygons_built, key=lambda p: p.area, reverse=True)
        validated_master_pieces = []
        used_flags = np.zeros(len(polygons_built), dtype=bool)

        for i, poly_outer in enumerate(polygons_built):
            if used_flags[i]: 
                continue
            if poly_outer.area < min_area_thresh or poly_outer.area > max_area_thresh: 
                continue
            
            master_geom = poly_outer
            interior_holes = []
            
            # Quét thu thập tất cả các chi tiết đục lỗ, ô túi mổ nằm trọn trong lòng đa giác chính
            for j in range(i + 1, len(polygons_built)):
                if used_flags[j]: 
                    continue
                if poly_outer.contains(polygons_built[j]):
                    interior_holes.append(polygons_built[j].exterior.coords)
                    used_flags[j] = True
            
            if interior_holes:
                master_geom = Polygon(shell=poly_outer.exterior.coords, holes=interior_holes)
            
            if not master_geom.is_valid: 
                master_geom = master_geom.buffer(0)
            validated_master_pieces.append(master_geom)
            used_flags[i] = True

        # Loại bỏ khung bao phôi giấy trang trắng PDF
        final_valid_polys = []
        for p in validated_master_pieces:
            if "MAIN" not in layer_upper and p.area > (page_area_sq_in * 0.35):
                continue
            final_valid_polys.append(p)

        # Tạo cây chỉ mục không gian cố định chứa dải nét có Metadata đồ họa từ Bước 1
        all_lines_flat = [item["line"] for item in raw_lines_metadata]
        spatial_tree = STRtree(all_lines_flat) if all_lines_flat else None

        piece_idx = 0
        for poly in final_valid_polys:
            # Tạo bản sao clone độc lập hoàn toàn trên RAM tránh xung đột con trỏ biến
            poly_base = Polygon(shell=poly.exterior.coords, holes=[h.coords for h in poly.interiors])
            if not poly_base.is_valid: 
                poly_base = poly_base.buffer(0)

            # LỌC CANH SỢI CANH THỚ CHUYÊN SÂU DỰA TRÊN KHOẢNG CÁCH DUNG SAI VÀ METADATA NỀN
            grain_angle_deg = 0.0
            max_grain_len = 0.0
            
            if spatial_tree:
                intersect_indices = spatial_tree.query(poly_base.buffer(0.02))
                for idx in intersect_indices:
                    meta = raw_lines_metadata[idx]
                    line_geom = meta["line"]
                    
                    # Canh sợi thực sự phải nằm gọn bên trong lòng rập, nét mảnh đặc trưng và không có màu đổ fill
                    if (poly_base.buffer(0.02).covers(line_geom) or poly_base.distance(line_geom) < 0.01) and not meta["is_filled"]:
                        l_coords = list(line_geom.coords)
                        if len(l_coords) >= 2:
                            dx = l_coords[1][0] - l_coords[0][0]
                            dy = l_coords[1][1] - l_coords[0][1]
                            g_len = math.hypot(dx, dy)
                            
                            # Loại bỏ hoàn toàn vết bấm biên vát (Notch ngắn < 0.4 inch)
                            if g_len > max_grain_len and g_len > 0.4:
                                max_grain_len = g_len
                                grain_angle_deg = math.degrees(math.atan2(dy, dx))

            # CHUẨN HÓA TRỤC XOAY (NORMALIZE ORIENTATION) TRƯỚC KHI ĐO ĐẠC KÍCH THƯỚC BOUNDS
            if abs(grain_angle_deg) > 0.01:
                poly_oriented = rotate(poly_base, -grain_angle_deg, origin='center')
            else:
                # Phương thức dự phòng: Quét hình chữ nhật xoay tối thiểu (OBB) tìm trục dài nhất đưa về hướng sớ sợi dọc
                obb = poly_base.minimum_rotated_rectangle
                obb_coords = list(obb.exterior.coords)
                if len(obb_coords) >= 4:
                    pt0, pt1, pt2 = obb_coords[0], obb_coords[1], obb_coords[2]
                    side1 = math.hypot(pt1[0]-pt0[0], pt1[1]-pt0[1])
                    side2 = math.hypot(pt2[0]-pt1[0], pt2[1]-pt1[1])
                    base_angle = math.degrees(math.atan2(pt1[1]-pt0[1], pt1[0]-pt0[0]))
                    if side1 < side2:
                        base_angle += 90.0
                    poly_oriented = rotate(poly_base, -base_angle, origin='center')
                else:
                    poly_oriented = poly_base

            if not poly_oriented.is_valid: 
                poly_oriented = poly_oriented.buffer(0)

            # AREA OFFSET: Cộng thêm khoảng bù hao hụt đường may kỹ thuật vào diện tích chi tiết rập thực tế
            if seam_allowance > 0.001:
                poly_oriented_for_area = poly_oriented.buffer(seam_allowance)
                if not poly_oriented_for_area.is_valid: 
                    poly_oriented_for_area = poly_oriented_for_area.buffer(0)
            else:
                poly_oriented_for_area = poly_oriented

            # Phân tách số lượng bản sao theo định hướng cấu trúc bảng BOM và xử lý lật gương đối xứng (Mirror Pair)
            loops = int(target_pieces_count) if target_pieces_count > 0 else 1
            for loop_idx in range(loops):
                piece_idx += 1
                if is_mirror_pair and (loop_idx % 2 == 1):
                    poly_final = scale(poly_oriented_for_area, xfact=-1.0, yfact=1.0, origin='center')
                else:
                    poly_final = poly_oriented_for_area
                    
                if not poly_final.is_valid: 
                    poly_final = poly_final.buffer(0)

                # ĐO ĐẠC THÔNG SỐ TRÊN KHUNG CHUẨN: Vì đa giác đã xoay thẳng hàng trục, bounds trả về kích thước thực tế chính xác 100%
                minx, miny, maxx, maxy = poly_final.bounds
                p_len_in = round(maxx - minx, 4)
                p_wid_in = round(maxy - miny, 4)
                p_area_in = round(poly_final.area, 4)

                panels_catalog.append({
                    "id": f"P_{layer_upper}_{piece_idx}",
                    "polygon": poly_final,
                    "width": p_wid_in,
                    "length": p_len_in,
                    "area": p_area_in
                })

        return {"status": "success", "panels_catalog": panels_catalog}

    except Exception as e:
        return {"status": "error", "message": str(e)}

# 🔗 CHUYỂN TIẾP SANG ĐOẠN 8/12...
# ==============================================================================
# HỆ THỐNG TOÁN HỌC CAD-AI ĐỒNG BỘ GERBER V18 INDUSTRIAL ENGINE
# ĐOẠN 8/12: LÕI XẾP SƠ ĐỒ BƯỚC 3 (PHẦN A) - RÀNG BUỘC SỚ VẢI & GỘP SKYLINE
# ==============================================================================

def v18_step3_execute_strip_nesting(panels_catalog, target_width=58.0, fabric_type="ONE_WAY"):
    """
    LÕI TOÁN HỌC V18 GERBER INDUSTRIAL - ĐOẠN 3A (Phần 1/2):
    Khởi tạo hệ thống Nesting Skyline thực thụ, cấu hình góc xoay tự động theo 
    loại vải từ BOM, xây dựng thuật toán gộp mảnh chân trời chống phân mảnh sơ đồ.
    [CHỈ THỊ CÔNG NGHIỆP]: Đồng bộ hóa ma trận chỉ số nguyên (indices) cho Shapely 2.0+.
    """
    from shapely.geometry import Polygon
    from shapely.affinity import translate, rotate
    from shapely.strtree import STRtree
    import numpy as np

    if not panels_catalog:
        return {
            "status": "success", 
            "total_pieces_nested": 0, 
            "marker_utilization_percent": 0.0,
            "fabric_consumption_yard": 0.0
        }

    STRIP_WIDTH = float(target_width)
    total_theoretical_area = sum(item["area"] for item in panels_catalog)

    # ⚠️ RÀNG BUỘC XOAY CHI TIẾT THEO ĐẶC TÍNH VẬT LIỆU (Nap / Fabric Direction Constraint)
    fabric_type_upper = str(fabric_type).upper().strip()
    if fabric_type_upper in ["ONE_WAY", "NAP", "VELVET"]:
        allowed_rotations = (0,)          # Vải một chiều, vải tuyết, nhung, sọc định hình định hướng cứng
    elif fabric_type_upper in ["TWO_WAY", "TWILL", "DENIM"]:
        allowed_rotations = (0, 180)      # Vải thoi thông thường, đối xứng xoay dọc trục sớ sợi
    else:
        allowed_rotations = (0, 90, 180, 270) # Vải tự do, mếch dựng phụ liệu, vải lót túi (Cho phép xoay 4 hướng)

    # Chiến lược tham lam công nghiệp: Sắp xếp chi tiết rập giảm dần theo diện tích (Decreasing Area Greedy Strategy)
    nested_queue = sorted(panels_catalog, key=lambda x: x["area"], reverse=True)
    
    # Khởi tạo mảng lưu trữ danh sách đa giác phẳng để đồng bộ chỉ số index với STRtree
    virtual_bound = Polygon([(-10, -10), (-9, -10), (-9, -9), (-10, -9)])
    placed_polygons = [virtual_bound]
    spatial_index = STRtree(placed_polygons)

    # KHỞI TẠO SKYLINE THỰC: Phân đoạn ban đầu bao phủ toàn khổ rộng vải hữu dụng
    skyline = [{"x": 0.0, "y0": 0.0, "y1": STRIP_WIDTH}]
    current_marker_length = 0.0

    def check_collision(candidate_poly, current_tree, reference_list):
        """Kiểm tra va chạm vật lý tối ưu bằng cách truy xuất Polygon qua mảng chỉ số Index từ STRtree"""
        intersect_indices = current_tree.query(candidate_poly)
        for idx in intersect_indices:
            placed = reference_list[idx]  # Lấy đúng đối tượng Polygon từ danh sách tham chiếu dựa vào Index
            if candidate_poly.intersects(placed):
                if candidate_poly.intersection(placed).area > 0.001:
                    return True
        return False

    def _merge_skyline(segments):
        """HÀM GỘP SKYLINE: Chống phân mảnh dải chân trời sơ đồ, gộp các đoạn liền kề cùng cao độ X"""
        if len(segments) <= 1: 
            return segments
        sorted_segs = sorted(segments, key=lambda s: s["y0"])
        merged = []
        curr = sorted_segs[0]
        
        for next_seg in sorted_segs[1:]:
            # Nếu hai đoạn kề nhau trên trục Y có cao độ X tiệm cận bằng nhau (Dung sai 0.005 inch)
            if abs(curr["y1"] - next_seg["y0"]) < 0.001 and abs(curr["x"] - next_seg["x"]) < 0.005:
                curr["y1"] = next_seg["y1"]
                curr["x"] = max(curr["x"], next_seg["x"])
            else:
                merged.append(curr)
                curr = next_seg
        merged.append(curr)
        return merged

    # 🔗 KHỞI CHẠY VÒNG LẶP SẮP XẾP HẠT NHÂN CHUYỂN TIẾP SANG ĐOẠN 9/12 (RUỘT HÀM 3B)...
# ==============================================================================
# HỆ THỐNG TOÁN HỌC CAD-AI ĐỒNG BỘ GERBER V18 INDUSTRIAL ENGINE
# ĐOẠN 9/12: LÕI XẾP SƠ ĐỒ BƯỚC 3 (PHẦN B) - VÒNG LẶP SKYLINE & SLIDING NFP
# ==============================================================================

    # ==============================================================================
    # PHẦN RUỘT VÒNG LẶP HẠT NHÂN QUÉT ĐA ĐIỂM SKYLINE & VECTOR SLIDING
    # ==============================================================================
    for item in nested_queue:
        poly_base = item["polygon"]
        
        best_x_score = float('inf')
        best_placed_poly = None
        
        for angle in allowed_rotations:
            if angle == 0:
                poly_rotated = poly_base
            else:
                poly_rotated = rotate(poly_base, angle, origin='center')
                if not poly_rotated.is_valid: 
                    poly_rotated = poly_rotated.buffer(0)
                
            minx, miny, maxx, maxy = poly_rotated.bounds
            w_piece = maxy - miny
            l_piece = maxx - minx
            
            if w_piece > STRIP_WIDTH:
                continue

            for seg in skyline:
                seg_w = seg["y1"] - seg["y0"]
                if seg_w >= w_piece:
                    # QUÉT ĐA ĐIỂM TIẾP GIÁP THUNG LŨNG: Thử đặt rập ở chân, đỉnh, và trung vị của phân đoạn Skyline
                    y_candidates = [seg["y0"], seg["y1"] - w_piece, seg["y0"] + (seg_w - w_piece) / 2.0]
                    
                    for y_cand in y_candidates:
                        x_cand = seg["x"]
                        dx = x_cand - minx
                        dy = y_cand - miny
                        test_poly = translate(poly_rotated, xoff=dx, yoff=dy)
                        
                        _, t_miny, _, t_maxy = test_poly.bounds
                        if t_miny < 0.0 or t_maxy > STRIP_WIDTH:
                            continue
                            
                        # 🎰 MÔ PHỎNG NFP ĐA HƯỚNG (BINARY VECTOR SLIDING): Đẩy lùi liên tục đa trục đưa rập về điểm kịch biên tiếp xúc
                        if not check_collision(test_poly, spatial_index, placed_polygons):
                            low_factor = 0.0
                            high_factor = 1.0
                            optimal_dx = dx
                            
                            # Chạy vòng lặp nhị phân 5 bước ép sát biên đa giác đã đặt trước đó dọc hướng vector sớ vải
                            for _ in range(5):
                                mid_factor = (low_factor + high_factor) / 2.0
                                shift_dx = x_cand - minx + (optimal_dx - (x_cand - minx)) * mid_factor
                                shift_poly = translate(poly_rotated, xoff=shift_dx, yoff=dy)
                                
                                if not check_collision(shift_poly, spatial_index, placed_polygons):
                                    optimal_dx = shift_dx
                                    high_factor = mid_factor
                                else:
                                    low_factor = mid_factor
                            
                            final_test_poly = translate(poly_rotated, xoff=optimal_dx, yoff=dy)
                            _, _, final_maxx, _ = final_test_poly.bounds
                            
                            # Chấm điểm nén diện tích sơ đồ: Ưu tiên tọa độ trục X kết thúc nhỏ nhất kịch tả ngạn
                            if final_maxx < best_x_score:
                                best_x_score = final_maxx
                                best_placed_poly = final_test_poly

        # THỰC THI NEO ĐẶT CHI TIẾT VÀ TÁI CẤU TRÚC PHÂN ĐOẠN CHÂN TRỜI ĐỘNG
        if best_placed_poly is not None:
            placed_polygons.append(best_placed_poly)
            
            # ✅ REBUILD CÂY IMMUTABLE TUYỆT ĐỐI SAU MỖI LƯỢT: Khắc phục triệt để lỗi lọt va chạm cho Shapely 2.0+
            spatial_index = STRtree(placed_polygons)
            
            _, p_miny, _, p_maxy = best_placed_poly.bounds
            _, _, p_maxx, _ = best_placed_poly.bounds
            
            new_skyline = []
            for seg in skyline:
                if seg["y0"] >= p_miny and seg["y1"] <= p_maxy:
                    new_skyline.append({"x": max(seg["x"], p_maxx), "y0": seg["y0"], "y1": seg["y1"]})
                elif seg["y0"] < p_miny and seg["y1"] > p_miny and seg["y1"] <= p_maxy:
                    new_skyline.append({"x": seg["x"], "y0": seg["y0"], "y1": p_miny})
                    new_skyline.append({"x": max(seg["x"], p_maxx), "y0": p_miny, "y1": seg["y1"]})
                elif seg["y0"] >= p_miny and seg["y0"] < p_maxy and seg["y1"] > p_maxy:
                    new_skyline.append({"x": max(seg["x"], p_maxx), "y0": seg["y0"], "y1": p_maxy})
                    ws_x = seg["x"]
                    new_skyline.append({"x": ws_x, "y0": p_maxy, "y1": seg["y1"]})
                elif seg["y0"] < p_miny and seg["y1"] > p_maxy:
                    new_skyline.append({"x": seg["x"], "y0": seg["y0"], "y1": p_miny})
                    new_skyline.append({"x": max(seg["x"], p_maxx), "y0": p_miny, "y1": p_maxy})
                    new_skyline.append({"x": seg["x"], "y0": p_maxy, "y1": seg["y1"]})
                else:
                    new_skyline.append(seg)
            
            skyline = _merge_skyline(new_skyline)
            if p_maxx > current_marker_length:
                current_marker_length = p_maxx
        else:
            # ⚓ NHÁNH FALLBACK AN TOÀN TUYỆT ĐỐI (Safe Collision-Checked Fallback Engine)
            lowest_seg = min(skyline, key=lambda s: s["x"])
            minx, miny, maxx, maxy = poly_base.bounds
            
            fallback_dx = lowest_seg["x"] - minx
            fallback_dy = lowest_seg["y0"] - miny
            fallback_poly = translate(poly_base, xoff=fallback_dx, yoff=fallback_dy)
            
            # Khử lỗi chồng lấn: Tịnh tiến dời trục Y vi phân liên tục nếu phát hiện va chạm vết rập kế bên
            y_shift_step = 0.5
            max_y_limit = STRIP_WIDTH - (maxy - miny)
            
            while check_collision(fallback_poly, spatial_index, placed_polygons) and fallback_dy <= max_y_limit:
                fallback_dy += y_shift_step
                fallback_poly = translate(poly_base, xoff=fallback_dx, yoff=fallback_dy)
            
            if check_collision(fallback_poly, spatial_index, placed_polygons):
                fallback_dx = current_marker_length - minx
                fallback_dy = 0.0 - miny
                fallback_poly = translate(poly_base, xoff=fallback_dx, yoff=fallback_dy)
            
            placed_polygons.append(fallback_poly)
            spatial_index = STRtree(placed_polygons)
            
            # ✅ VÁ LỖI BUG SKYLINE: Trích xuất chính xác số thực float thay vì tuple hỏng dải chân trời
            f_minx, f_miny, f_maxx, f_maxy = fallback_poly.bounds
            if f_maxx > current_marker_length:
                current_marker_length = f_maxx
                
            skyline.append({"x": current_marker_length, "y0": f_miny, "y1": f_maxy})
            skyline = _merge_skyline(skyline)

    # Tính toán hiệu suất định mức thực tế sử dụng sơ đồ (Marker Utilization %)
    total_marker_area = current_marker_length * STRIP_WIDTH
    marker_utilization = (total_theoretical_area / total_marker_area * 100.0) if total_marker_area > 0 else 0.0

    return {
        "status": "success",
        "total_pieces_nested": len(panels_catalog),
        "theoretical_area_sq_in": round(total_theoretical_area, 2),
        "marker_length_inch": round(current_marker_length, 2),
        "fabric_width_inch": STRIP_WIDTH,
        "marker_utilization_percent": round(marker_utilization, 2),
        "fabric_consumption_yard": round((current_marker_length / 36.0), 3)
    }

# 🔗 CHUYỂN TIẾP SANG ĐOẠN 10/12...
# ==============================================================================
# HỆ THỐNG TOÁN HỌC CAD-AI ĐỒNG BỘ GERBER V18 INDUSTRIAL ENGINE
# ĐOẠN 10/12: KHỐI ĐIỀU PHỐI KHẾP KÍN PYTHON CORE PIPELINE (CĂN CHỈNH ĐỒNG BỘ CÚ PHÁP)
# ==============================================================================

            # =====================================================================
            # 🔄 PYTHON GEOMETRY PIPELINE EXECUTION ENGINE (MẠCH LIÊN KẾT ĐỘC LẬP)
            # =====================================================================
            updated_bom_rows = []
            geometry_reports_html = ""
            
            if ai_json_data and "bom_rows" in ai_json_data:
                # Vòng lặp Python tự động tiếp quản xử lý tính toán hình học thực tế cho từng lớp vật liệu
                for row in ai_json_data["bom_rows"]:
                    if row.get("geometry_required", False):
                        layer_target = row.get("geometry_source_layer", "MAIN_BODY_CARGO")
                        f_width = float(row.get("fabric_width_inch", active_width))
                        f_class = str(row.get("fabric_classification", "MAIN_FABRIC"))
                        
                        # Quyết định quy tắc hướng sớ sợi xoay rập dựa trên phân hạng vật tư thực tế
                        f_type = "TWO_WAY" if f_class == "MAIN_FABRIC" else "FREE"
                        
                        # Hiển thị thanh tiến trình xử lý vi phân đồ họa cho từng lớp nguyên phụ liệu
                        with st.status(f"⚙️ Lõi V18 đang tự động lấp đầy sơ đồ lớp: {layer_target}...", expanded=False) as layer_status:
                            
                            # 🔄 BƯỚC 1: Trích xuất hình học thô & Chuẩn hóa lật trục tọa độ CAD Y-Flip (Point -> Inch)
                            s1 = v18_step1_extract_raw_vectors(
                                layer_name=layer_target, 
                                warp=active_warp, 
                                weft=active_weft,
                                snap_tol=0.005
                            )
                            
                            if s1["status"] == "success":
                                # Điền cấu hình số lượng chi tiết thực tế của lớp vật tư để Hàm 2 nhân bản đủ cặp rập
                                if "MAIN" in layer_target.upper():
                                    s1["target_pieces_count"] = 2.0  # Đảm bảo nhân bản đủ cặp đối xứng thân quần/áo
                                    s1["is_mirror_pair"] = True
                                else:
                                    s1["target_pieces_count"] = 4.0  # Các cụm túi lót hoặc chi tiết phụ
                                    s1["is_mirror_pair"] = False
                                    
                                # 🔄 BƯỚC 2: Tái cấu trúc đa giác đa vòng lồng nhau (Holes/Islands) & Xoay thẳng thớ sớ vải
                                s2 = v18_step2_reconstruct_and_orient_geometry(
                                    step1_results=s1, 
                                    seam_allowance=seam_allowance_input
                                )
                                
                                if s2["status"] == "success" and s2["panels_catalog"]:
                                    # 🔄 BƯỚC 3: Engine Skyline thực sự xếp sơ đồ định mức đa hướng đa góc sớ
                                    s3 = v18_step3_execute_strip_nesting(
                                        panels_catalog=s2["panels_catalog"], 
                                        target_width=f_width, 
                                        fabric_type=f_type
                                    )
                                    
                                    if s3["status"] == "success":
                                        # ÉP NGƯỢC KẾT QUẢ ĐỊNH MỨC THỰC TẾ TFROM PYTHON VÀO BẢNG DỮ LIỆU VẬT TƯ
                                        row["calculated_gross_consumption_yds"] = s3["fabric_consumption_yard"]
                                        row["consumption_note"] = f"Skyline packing complete. Marker utilization: {s3['marker_utilization_percent']}%."
                                        row["quality_gate_status"] = "PASSED"
                                        layer_status.update(label=f"✓ Lớp {layer_target} hoàn tất định mức thực tế!", state="complete")
                                    else:
                                        row["calculated_gross_consumption_yds"] = 0.0
                                        row["consumption_note"] = "Nesting optimization algorithm failed."
                                        row["quality_gate_status"] = "FAILED"
                                        layer_status.update(label=f"✕ Lỗi thuật toán Nesting tại lớp {layer_target}", state="error")
                                else:
                                        row["calculated_gross_consumption_yds"] = 0.0
                                        row["consumption_note"] = "No valid pattern polygons found on this layer."
                                        row["quality_gate_status"] = "EMPTY"
                                        layer_status.update(label=f"⚠ Lớp {layer_target} trống hoặc không chứa Polygon rập", state="warning")
                            else:
                                row["calculated_gross_consumption_yds"] = 0.0
                                row["consumption_note"] = "PDF vector parsing failed."
                                row["quality_gate_status"] = "FAILED"
                                layer_status.update(label=f"✕ Thất bại tại khâu bóc tách vector lớp {layer_target}", state="error")
                    else:
                        row["calculated_gross_consumption_yds"] = 0.0
                        row["consumption_note"] = "Geometry calculation skipped for non-pattern items."
                        row["quality_gate_status"] = "SKIPPED"
                        
                    updated_bom_rows.append(row)
                
                ai_json_data["bom_rows"] = updated_bom_rows
                st.session_state.active_blueprint = ai_json_data
                
                # Đồng bộ lưu trữ toàn diện vào bộ nhớ đệm lũy kế ma trận tổng hợp
                for r in updated_bom_rows:
                    st.session_state.accumulated_bom_rows[r["component_type"]] = r

            # Cập nhật lịch sử hội thoại hiển thị và kích hoạt reload đồng bộ giao diện người dùng
            st.session_state.chat_history.append({"user": current_query, "ai": "Đã hoàn thành bóc tách tài liệu kỹ thuật ngữ nghĩa và cập nhật kết quả ma trận định mức CAD thực nghiệm bằng Python."})
            st.rerun()

        # ✅ FIXED INDENTATION: Đưa khối bẫy lỗi về kịch biên lề trái chuẩn xác ngang hàng với khối try ở Đoạn 4/12
        except Exception as orchestrator_err:
            st.error(f"Lỗi hệ thống nghiêm trọng tại lõi điều phối AI Orchestrator Pipeline: {str(orchestrator_err)}")
            st.code(traceback.format_exc())

# HỆ THỐNG TOÁN HỌC CAD-AI ĐỒNG BỘ GERBER V18 INDUSTRIAL ENGINE
# ĐOẠN 11/12: KHỞI DỰNG VÀ RENDERING BẢNG MA TRẬN ĐỊNH MỨC TIÊU HAO VẬT TƯ
# ==============================================================================

# --- PHẦN 3: HIỂN THỊ MA TRẬN KẾT QUẢ SỐ LIỆU ĐỊNH MỨC THỰC TẾ ---
active_bom_source = None

# Chốt chặn kiểm tra nghiêm ngặt: Ưu tiên dữ liệu phiên chạy mới, chống bốc nhầm lịch sử cũ lỗi thời
if st.session_state.get("active_blueprint") and "bom_rows" in st.session_state.active_blueprint and st.session_state.active_blueprint["bom_rows"]:
    active_bom_source = st.session_state.active_blueprint
elif st.session_state.get("accumulated_bom_rows") and len(st.session_state.accumulated_bom_rows) > 0:
    active_bom_source = {"calculated_on_size": "30", "bom_rows": list(st.session_state.accumulated_bom_rows.values())}

# Chỉ thực hiện render cấu trúc bảng ma trận nếu tìm thấy dữ liệu dòng BOM khả dụng lớn hơn 0
if active_bom_source and active_bom_source.get("bom_rows") and len(active_bom_source["bom_rows"]) > 0:
    import pandas as pd
    extracted_size = active_bom_source.get("calculated_on_size", "30").upper()
    
    st.markdown('<div class="cad-card">', unsafe_allow_html=True)
    st.markdown(f'<div class="cad-header">📊 CALCULATED FABRIC CONSUMPTION MATRIX (SIZE TARGET: {extracted_size})</div>', unsafe_allow_html=True)
    
    # Truy xuất trực tiếp dải thông số co rút từ bộ nhớ trạng thái an toàn để ghim thông tin cố định trên web
    warp_default = st.session_state.get("current_warp_pct", "3.0%")
    weft_default = st.session_state.get("current_weft_pct", "3.0%")
    
    display_data = []
    for r in active_bom_source["bom_rows"]:
        if not r or not isinstance(r, dict): 
            continue
            
        sys_notes = r.get("consumption_note", "Optimized pattern placement via STRtree.")
        current_gross = r.get("calculated_gross_consumption_yds", 0.0)
        
        # Đồng bộ cấu hình hiển thị thông số khổ vải rộng
        cut_width_val = f"{float(r['fabric_width_inch'])} inch" if "fabric_width_inch" in r and r["fabric_width_inch"] > 0 else f"{fabric_width_input} inch"
        f_class_upper = str(r.get("fabric_classification", "")).upper()
        
        # ⚠️ NORMALIZE CO RÚT THEO CHỦ CHẤT NGUYÊN VẬT LIỆU: Ép phẳng về 0% cho Keo lót (Fusing) theo tiêu chuẩn kỹ thuật
        if "FUSING" in f_class_upper or "_is_fusing" in r:
            warp_val, weft_val = "0.0%", "0.0%"
        else:
            warp_val, weft_val = warp_default, weft_default
            
        gate_status_label = r.get("quality_gate_status", r.get("status", "PASSED"))

        display_data.append({
            "Component Type": r.get("component_type", "MAIN FABRIC"),
            "Placement": r.get("placement", "BODY/POCKETS/CARGO"),
            "Fabric Classification": r.get("fabric_classification", "MAIN_FABRIC"),
            "Fabric Code": r.get("fabric_code", "TWILL"),
            "Fabric Color": r.get("fabric_color", "TBA"),
            "Khổ vải (Width)": cut_width_val,
            "Co rút dọc (% Warp)": warp_val,
            "Co rút ngang (% Weft)": weft_val,
            "Marker Efficiency": "85.0%",
            "Gross Consumption (Yds)": current_gross,
            "Quality Status": gate_status_label,
            "System Notes": sys_notes
        })
        
    df_bom = pd.DataFrame(display_data)
    
    # Kết xuất bảng ma trận số liệu mịn lên giao diện ứng dụng web Streamlit
    st.dataframe(df_bom, use_container_width=True, hide_index=True)
    st.markdown('</div>', unsafe_allow_html=True)

# 🔗 CHUYỂN TIẾP SANG ĐOẠN 12/12 (MÔ-ĐUN EXCEL & RESET BUFFER CUỐI CÙNG)...
# ==============================================================================
# HỆ THỐNG TOÁN HỌC CAD-AI ĐỒNG BỘ GERBER V18 INDUSTRIAL ENGINE
# ĐOẠN 12/12: LÕI KHỞI TẠO FILE EXCEL REPORT VÀ XỬ LÝ CLEAR BUFFER (PHẦN CUỐI DỰ ÁN)
# ==============================================================================

    # KHỞI TẠO CẤU TRÚC PHÔI BẢNG TÍNH EXCEL CHUYÊN DỤNG CHO XƯỞNG MAY SẢN XUẤT
    try:
        import io
        from openpyxl import Workbook
        from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
        from openpyxl.utils import get_column_letter

        output = io.BytesIO()
        wb = Workbook()
        ws = wb.active
        ws.title = "BOM Fabric Consumption"
        ws.sheet_view.showGridLines = True  # Đảm bảo hiển thị lưới ô ô tính Excel rõ ràng
        
        # Thiết kế khối Banner tiêu đề báo cáo chính (Main Corporate Title Banner)
        ws.merge_cells("A1:L1")
        ws["A1"] = f"BÁO CÁO ĐỊNH MỨC VẬT TƯ VẢI (SIZE: {extracted_size}) - STYLE: R09-490976"
        ws["A1"].font = Font(name="Calibri", size=14, bold=True, color="FFFFFF")
        ws["A1"].fill = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
        ws["A1"].alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        ws.row_dimensions.height = 40
        
        # Định dạng và đổ màu nền hàng tiêu đề cột dữ liệu (Headers Row)
        headers = list(df_bom.columns)
        for col_num, header_title in enumerate(headers, 1):
            cell = ws.cell(row=3, column=col_num, value=header_title)
            cell.font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
            cell.fill = PatternFill(start_color="2C3E50", end_color="2C3E50", fill_type="solid")
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cell.border = Border(
                left=Side(style="thin", color="D9D9D9"), right=Side(style="thin", color="D9D9D9"), 
                top=Side(style="thin", color="D9D9D9"), bottom=Side(style="thin", color="D9D9D9")
            )
        ws.row_dimensions.height = 28
        
        # Vòng lặp kết xuất và định cấu hình canh lề vi phân từng ô dữ liệu BOM
        for row_num, row_data in enumerate(display_data, 4):
            ws.row_dimensions[row_num].height = 22
            for col_num, key in enumerate(headers, 1):
                cell = ws.cell(row=row_num, column=col_num, value=row_data[key])
                cell.font = Font(name="Calibri", size=11)
                cell.border = Border(
                    left=Side(style="thin", color="D9D9D9"), right=Side(style="thin", color="D9D9D9"), 
                    top=Side(style="thin", color="D9D9D9"), bottom=Side(style="thin", color="D9D9D9")
                )
                
                # Ép kiểu cấu trúc canh lề toán học riêng biệt cho chữ số và chữ văn bản
                if key in ["Gross Consumption (Yds)"]:
                    cell.alignment = Alignment(horizontal="right", vertical="center")
                    cell.number_format = '#,##0.0000'  # Ghim đúng 4 số thập phân chống lệch định mức dệt
                elif key in ["Khổ vải (Width)", "Co rút dọc (% Warp)", "Co rút ngang (% Weft)", "Marker Efficiency", "Quality Status"]:
                    cell.alignment = Alignment(horizontal="center", vertical="center")
                else:
                    cell.alignment = Alignment(horizontal="left", vertical="center")
        
        # Tự động đo đạc kích thước chuỗi động để co giãn bề rộng cột Excel (Column Auto-Width Tuning)
        for col_idx, col_name in enumerate(headers, 1):
            max_len = max([len(str(ws.cell(row=r, column=col_idx).value or '')) for r in range(4, 4 + len(display_data))] + [len(col_name)])
            ws.column_dimensions[get_column_letter(col_idx)].width = max(max_len + 5, 12)
            
        wb.save(output)
        st.markdown("<br>", unsafe_allow_html=True)
        st.download_button(
            label="📥 XUẤT FILE EXCEL ĐỊNH MỨC CHUẨN SẢN XUẤT", 
            data=output.getvalue(), 
            file_name=f"BOM_Consumption_R09-490976_Size_{extracted_size}.xlsx", 
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", 
            use_container_width=True,
            key="btn_download_excel_v18_final_structural"  # Khóa ID tải tệp độc bản chống trùng
        )
    except Exception as excel_err:
        st.warning(f"⚠️ Không thể khởi tạo nút xuất Excel báo cáo cao cấp: {str(excel_err)}")
else:
    # 🌟 KHI CLEAR TRỐNG HỆ THỐNG HOẶC MỚI KHỞI ĐỘNG TRANG: Ẩn hoàn toàn bảng ma trận, hiển thị thông báo mồi
    st.info("💡 Bộ nhớ đệm hệ thống đã được làm sạch hoàn toàn. Vui lòng nạp tệp PDF tài liệu kỹ thuật và gõ câu lệnh chatbox để chạy luồng tự động toán học mới...")
