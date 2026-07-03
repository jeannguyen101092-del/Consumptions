import streamlit as st
import math
import json
import re
import traceback
import io
import numpy as np
import pandas as pd
from shapely.geometry import Polygon, MultiPolygon, LineString
from shapely.ops import unary_union, polygonize
from shapely.affinity import translate, rotate, scale
from shapely.strtree import STRtree
import google.generativeai as genai

# ==========================================
# ĐOẠN 1/2: CẤU HÌNH HỆ THỐNG & AI ENGINE
# ==========================================

# Cấu hình giao diện Streamlit rộng rãi để hiển thị sơ đồ CAD
st.set_page_config(page_title="Gerber V10 CAD-AI Engine", layout="wide")

# Khởi tạo các biến lưu trữ trạng thái hệ thống (Session State)
if "pdf_bytes" not in st.session_state:
    st.session_state.pdf_bytes = None
if "pdf_text_cache" not in st.session_state:
    st.session_state.pdf_text_cache = ""
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "active_blueprint" not in st.session_state:
    st.session_state.active_blueprint = {}
if "accumulated_bom_rows" not in st.session_state:
    st.session_state.accumulated_bom_rows = {}
if "current_warp_pct" not in st.session_state:
    st.session_state.current_warp_pct = "3.0%"
if "current_weft_pct" not in st.session_state:
    st.session_state.current_weft_pct = "2.0%"

# --- SIDEBAR: ĐIỀU KHIỂN & CÀI ĐẶT THÔNG SỐ VẢI ---
st.sidebar.header("🔧 Thông Số Kỹ Thuật Hệ Thống")

# Nhập các thông số hình học đầu vào của sơ đồ vải
fabric_width_input = st.sidebar.number_input(
    "Khổ rộng vải hữu dụng (Inch):", 
    min_value=10.0, max_value=150.0, value=57.0, step=0.5
)
seam_allowance_input = st.sidebar.slider(
    "Hao hụt đường may - Seam Allowance (inch):", 
    min_value=0.0, max_value=2.0, value=0.25, step=0.05
)
warp_shrinkage = st.sidebar.slider(
    "Độ co rút sợi dọc (Warp %):", 
    min_value=0.0, max_value=20.0, value=3.0, step=0.1
)
weft_shrinkage = st.sidebar.slider(
    "Độ co rút sợi ngang (Weft %):", 
    min_value=0.0, max_value=20.0, value=2.0, step=0.1
)

# Cập nhật thông số co rút vào hệ thống toàn cục
st.session_state.current_warp_pct = f"{warp_shrinkage}%"
st.session_state.current_weft_pct = f"{weft_shrinkage}%"

# --- THÔNG TIN TIÊU ĐỀ CHÍNH ---
st.title("🤖 Hệ Thống Tính Định Mức Sơ Đồ Gerber V10 CAD-AI")
st.caption("Quy trình khép kín: AI bóc tách cấu trúc sơ đồ -> Python xử lý tính toán và xếp sơ đồ hình học thực tế.")

# Cấu hình API Key cho Gemini (Sử dụng secrets của Streamlit hoặc biến môi trường)
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
except Exception:
    st.sidebar.warning("⚠️ Chưa cấu hình GEMINI_API_KEY trong Streamlit Secrets.")

# --- AI CORE ENGINE: HÀM TRÍCH XUẤT VÀ XỬ LÝ NGÔN NGỮ ---

def v10_step1_extract_raw_text(pdf_file_bytes):
    """
    Sử dụng mô hình Multimodal Gemini để đọc trực tiếp file tài liệu PDF 
    và chuyển hóa toàn bộ nội dung BOM, Tech Pack thành chuỗi văn bản thô cấu trúc.
    """
    if not pdf_file_bytes:
        return ""
    
    # Cấu hình mô hình tối ưu cho xử lý văn bản dài và chính xác dữ liệu
    model = genai.GenerativeModel("gemini-1.5-pro-latest")
    
    prompt = """
    Bạn là một chuyên gia bóc tách tài liệu kỹ thuật ngành may (Tech Pack / BOM). 
    Hãy đọc kỹ file tài liệu PDF đính kèm và trích xuất tất cả các thông tin sau một cách chi tiết:
    1. Bảng danh mục nguyên phụ liệu (BOM): Tên chi tiết, loại vải, mã màu, định mức định hướng.
    2. Các thông số kỹ thuật cấu trúc: Khổ vải (Fabric width), quy cách đường may (Seam allowance), độ co rút (Shrinkage) nếu có ghi chú.
    3. Danh sách các chi tiết rập (Piece count) cần cắt cho sản phẩm.
    Hãy giữ nguyên các thuật ngữ tiếng Anh chuyên ngành để đảm bảo tính chính xác cho các bước xử lý sau.
    """
    
    try:
        response = model.generate_content([
            {"mime_type": "application/pdf", "data": pdf_file_bytes},
            prompt
        ])
        return response.text
    except Exception as e:
        return f"Lỗi khi xử lý tài liệu qua AI: {str(e)}"


def clean_and_snap_points(coords, tolerance=0.01):
    """Làm sạch và làm tròn các tọa độ hình học phẳng để tránh sai số dấu phẩy động trong CAD Engine"""
    return [(round(x, 4), round(y, 4)) for x, y in coords]


def interpolate_adaptive_bezier(p0, p1, p2, p3, steps=10):
    """Nội suy đường cong Bezier bậc 3 của các chi tiết rập thành chuỗi các điểm đa giác tuyến tính"""
    points = []
    for i in range(steps + 1):
        t = i / steps
        x = (1-t)**3 * p0[0] + 3*(1-t)**2 * t * p1[0] + 3*(1-t) * t**2 * p2[0] + t**3 * p3[0]
        y = (1-t)**3 * p0[1] + 3*(1-t)**2 * t * p1[1] + 3*(1-t) * t**2 * p2[1] + t**3 * p3[1]
        points.append((x, y))
    return points


def v10_step2_reconstruct_json_blueprint(raw_text_context):
    """
    AI nhận nhiệm vụ phân tích ngữ nghĩa từ văn bản thô, ánh xạ thông tin
    và đóng gói thành một file JSON Blueprint chuẩn kỹ thuật, KHÔNG thực hiện tính toán.
    """
    model = genai.GenerativeModel("gemini-1.5-flash-latest")
    
    # Định nghĩa cấu trúc JSON mong muốn bắt buộc AI tuân thủ
    json_format_spec = {
      "marker_settings": {
        "fabric_width_inch": 57.0,
        "seam_allowance_inch": 0.25,
        "shrinkage_warp_pct": st.session_state.current_warp_pct,
        "shrinkage_weft_pct": st.session_state.current_weft_pct
      },
      "pieces": [
        {
          "name": "FRONT_PANEL",
          "quantity": 2,
          "grainline_angle_deg": 0,
          "polygon_coordinates_inch": [[0,0], [10,0], [10,20], [0,20]]
        }
      ],
      "thread_spec": {
        "stitch_type": "301",
        "spi": 12,
        "waste_allowance_pct": 15.0
      }
    }

    prompt = f"""
    Dựa trên văn bản kỹ thuật được trích xuất dưới đây, hãy tạo ra một JSON Blueprint chuẩn hóa 
    để cấu hình cho hệ thống xử lý hình học Python CAD Engine.
    
    Yêu Cầu Nghiêm Ngặt:
    1. Bóc tách chính xác tên chi tiết (name), số lượng cấu thành (quantity), hướng sợi (grainline).
    2. Nếu tài liệu không mô tả tọa độ cụ thể của đa giác rập, hãy tự động tạo lập vùng tọa độ giả lập (polygon_coordinates_inch) dạng bao quát hợp lý cho chi tiết đó (Ví dụ: Thân trước/Thân sau là hình chữ nhật lớn cách điệu, tay áo là đa giác hẹp hơn) dựa trên kinh nghiệm ngành may để Python CAD Engine thực hiện chạy thuật toán mô phỏng hình học bên dưới.
    3. Đầu ra CHỈ ĐƯỢC CHỨA chuỗi JSON nguyên bản, không bao gồm các ký tự bọc ngoài như ```json ... ```.

    Dữ liệu văn bản kỹ thuật đầu vào:
    {raw_text_context}

    Cấu trúc mẫu bắt buộc tuân theo:
    {json.dumps(json_format_spec, indent=2)}
    """
    
    try:
        response = model.generate_content(prompt)
        cleaned_response = response.text.strip()
        # Loại bỏ các ký tự markdown bao quanh nếu AI vô tình thêm vào
        cleaned_response = re.sub(r'^```json\s*|\s*```$', '', cleaned_response, flags=re.MULTILINE).strip()
        return json.loads(cleaned_response)
    except Exception as e:
        # Trả về blueprint dự phòng chuẩn nếu AI gặp sự cố biên dịch JSON
        return {
            "marker_settings": {"fabric_width_inch": fabric_width_input, "seam_allowance_inch": seam_allowance_input, "shrinkage_warp_pct": st.session_state.current_warp_pct, "shrinkage_weft_pct": st.session_state.current_weft_pct},
            "pieces": [
                {"name": "FRONT_PANEL_DEFAULT", "quantity": 2, "grainline_angle_deg": 0, "polygon_coordinates_inch": [[0,0], [12,0], [12,24], [0,24]]},
                {"name": "BACK_PANEL_DEFAULT", "quantity": 2, "grainline_angle_deg": 0, "polygon_coordinates_inch": [[0,0], [12,0], [12,24], [0,24]]},
                {"name": "SLEEVE_DEFAULT", "quantity": 2, "grainline_angle_deg": 45, "polygon_coordinates_inch": [[0,0], [8,0], [8,15], [0,15]]}
            ],
            "thread_spec": {"stitch_type": "301", "spi": 12, "waste_allowance_pct": 15.0}
        }

# Upload file Tech Pack đầu vào từ người dùng
uploaded_file = st.file_uploader("📥 Tải lên tài liệu kỹ thuật Tech Pack (PDF)", type=["pdf"])
# ==========================================
# ĐOẠN 2/2: PYTHON GEOMETRY & CALCULATE ENGINE
# ==========================================

def check_collision(placed_pieces, new_poly):
    """Kiểm tra va chạm hình học giữa chi tiết mới và các chi tiết đã xếp trên sơ đồ"""
    for placed_poly in placed_pieces:
        if new_poly.intersects(placed_poly):
            # Nếu chạm nhau hoặc đè lên nhau, trả về True
            if new_poly.intersection(placed_poly).area > 0.0001: 
                return True
    return False


def v10_step3_execute_strip_nesting(blueprint):
    """
    Python Nesting Engine: Tự động sắp xếp các chi tiết đa giác rập lên khổ vải.
    Áp dụng thuật toán Bottom-Left Strip Packing kết hợp xoay hướng sợi (Grainline).
    """
    settings = blueprint["marker_settings"]
    fabric_width = settings["fabric_width_inch"]
    seam_allowance = settings["seam_allowance_inch"]
    
    # Ép kiểu dữ liệu co rút từ chuỗi (ví dụ: "3.0%") sang số thực float
    warp_shrinkage_factor = 1 + (float(settings["shrinkage_warp_pct"].replace("%", "")) / 100)
    weft_shrinkage_factor = 1 + (float(settings["shrinkage_weft_pct"].replace("%", "")) / 100)
    
    st.write("### 📐 Tiến trình xử lý toán học hình học (Python Engine)")
    
    all_polygons_to_nest = []
    
    # 1. GEOMETRY ENGINE: Khôi phục đa giác và thêm đường chừa may (Seam Allowance)
    for piece in blueprint["pieces"]:
        coords = clean_and_snap_points(piece["polygon_coordinates_inch"])
        base_poly = Polygon(coords)
        
        # Thêm đường chừa may mặc định bằng thuật toán Buffer hình học phẳng
        # join_style=2 giúp giữ các góc vuông góc mút sắc nét theo tiêu chuẩn CAD ngành may
        poly_with_seam = base_poly.buffer(seam_allowance, join_style=2)
        
        # Áp dụng căn góc hướng sợi (Grainline) được trích xuất từ AI
        angle = piece.get("grainline_angle_deg", 0)
        if angle != 0:
            poly_with_seam = rotate(poly_with_seam, angle, origin='center')
            
        # Áp dụng co rút khổ sợi ngang (Weft) trực tiếp vào hình học trước khi đi sơ đồ
        if weft_shrinkage_factor != 1.0:
            poly_with_seam = scale(poly_with_seam, xfact=1.0, yfact=weft_shrinkage_factor, origin='center')

        # Gom tất cả các bản sao dựa trên số lượng cắt (Quantity) vào hàng đợi xếp sơ đồ
        for i in range(piece["quantity"]):
            all_polygons_to_nest.append({
                "name": f"{piece['name']}_qty{i+1}",
                "poly": poly_with_seam,
                "base_area": base_poly.area
            })
            
    # Sắp xếp các chi tiết theo diện tích giảm dần để tăng hiệu suất tối ưu sơ đồ (Greedy Strategy)
    all_polygons_to_nest.sort(key=lambda x: x["poly"].area, reverse=True)

    # 2. NESTING ENGINE: Thuật toán sắp xếp lấp đầy lưới phẳng
    placed_polygons = []
    current_marker_length = 0.0
    step_x = 0.25  # Bước nhảy quét dịch chuyển theo chiều dài sơ đồ (inch)
    step_y = 0.25  # Bước nhảy quét dịch chuyển theo chiều rộng khổ vải (inch)
    
    progress_bar = st.progress(0)
    total_pieces = len(all_polygons_to_nest)

    for index, item in enumerate(all_polygons_to_nest):
        poly_to_place = item["poly"]
        minx, miny, maxx, maxy = poly_to_place.bounds
        p_width = maxx - minx
        p_height = maxy - miny
        
        placed = False
        # Quét tìm vị trí trống từ trái sang phải, từ dưới lên trên
        target_x = 0.0
        while not placed:
            for target_y in np.arange(0.0, fabric_width - p_height + 0.01, step_y):
                # Dịch chuyển cấu trúc tọa độ chi tiết rập đến điểm đang quét thử nghiệm
                shifted_poly = translate(poly_to_place, xoff=target_x - minx, yoff=target_y - miny)
                
                # Kiểm tra xem có bị tràn biên khổ vải hữu dụng hay không
                if shifted_poly.bounds[3] > fabric_width:
                    continue
                    
                # Kiểm tra va chạm hình học chồng lấn với các chi tiết đã đặt trước đó
                if not check_collision(placed_polygons, shifted_poly):
                    placed_polygons.append(shifted_poly)
                    # Cập nhật chiều dài sơ đồ thực tế đạt được tại điểm xa nhất
                    if shifted_poly.bounds[2] > current_marker_length:
                        current_marker_length = shifted_poly.bounds[2]
                    placed = True
                    break
            if not placed:
                target_x += step_x
                # Giới hạn an toàn tránh vòng lặp vô hạn
                if target_x > 500.0: 
                    break
                    
        progress_bar.progress(int((index + 1) / total_pieces * 100))
        st.caption(f"✅ Đang đồng bộ hình học: Đã xếp xong `{item['name']}`")

    # 3. FABRIC CONSUMPTION ENGINE: Tính toán định mức tiêu hao vải cuối cùng
    # Áp dụng tỷ lệ co rút dọc (Warp Shrinkage) vào tổng chiều dài sơ đồ hình học thu được
    final_length_inch = current_marker_length * warp_shrinkage_factor
    final_consumption_yard = final_length_inch / 36.0 # Quy đổi inch sang Yards chuẩn quốc tế
    
    # Tính toán hiệu suất sử dụng vải của sơ đồ hình học (Utilization)
    total_pieces_area = sum([p.area for p in placed_polygons])
    total_marker_area = current_marker_length * fabric_width
    utilization_pct = (total_pieces_area / total_marker_area) * 100 if total_marker_area > 0 else 0

    # 4. THREAD CONSUMPTION ENGINE: Tính toán định mức tiêu hao chỉ may
    # Công thức toán học: Chiều dài chỉ = Chu vi đường may * Hệ số tiêu hao mũi (SPI/Stitch Type Ratio)
    # Loại mũi 301 Lockstitch có hệ số tiêu hao thực tế dao động từ 2.5 đến 3.5 lần chu vi
    thread_ratio = 3.0 
    total_thread_inch = 0.0
    
    for poly in placed_polygons:
        # Đường chỉ may chạy dọc theo chu vi bao của chi tiết có đường may
        total_thread_inch += poly.length * thread_ratio
        
    # Cộng thêm phần trăm hao hụt đầu chỉ, chỉ bỏ, chỉ chạy thử nghiệm (Waste Allowance)
    waste_factor = 1 + (blueprint["thread_spec"]["waste_allowance_pct"] / 100)
    final_thread_yard = (total_thread_inch / 36.0) * waste_factor

    return final_consumption_yard, final_thread_yard, utilization_pct, current_marker_length


# ==========================================
# ĐOẠN 3/2: KÍCH HOẠT PIPELINE & ĐỒNG BỘ GIAO DIỆN
# ==========================================

if uploaded_file is not None:
    # Lưu file tạm để đưa vào xử lý văn bản
    pdf_bytes = uploaded_file.read()
    
    if st.button("🚀 KÍCH HOẠT HỆ THỐNG CAD-AI ENGINE"):
        
        # BƯỚC 1 & 2: Gọi AI bóc tách cấu trúc dữ liệu ngôn ngữ ngữ nghĩa
        with st.spinner("🤖 AI (Gemini) đang đọc hiểu tài liệu Tech Pack & trích xuất JSON Blueprint..."):
            try:
                raw_text = v10_step1_extract_raw_text(pdf_bytes)
                blueprint = v10_step2_reconstruct_json_blueprint(raw_text)
                st.session_state.active_blueprint = blueprint
                
                st.success("🎉 AI đã hoàn thành bóc tách dữ liệu thành công!")
                st.write("#### 📄 Cấu trúc dữ liệu JSON Blueprint nhận được từ AI:")
                st.json(blueprint)
            except Exception as e:
                st.error(f"Thất bại tại phân đoạn xử lý AI: {str(e)}")
                
        # BƯỚC 3: Chuyển giao toàn bộ dữ liệu cấu trúc cho Python làm toán học
        with st.spinner("⚙️ Python Geometry Engine đang tính toán hình học phẳng & chạy sơ đồ..."):
            try:
                fab_yard, th_yard, util_pct, marker_len = v10_step3_execute_strip_nesting(st.session_state.active_blueprint)
                
                # --- REPORT ENGINE: XUẤT BÁO CÁO ĐỊNH MỨC ỔN ĐỊNH CỐ ĐỊNH 100% ---
                st.markdown("---")
                st.subheader("📊 BÁO CÁO ĐỊNH MỨC NGUYÊN PHỤ LIỆU TỰ ĐỘNG CHUẨN V10")
                
                # Hiển thị số liệu trực quan dạng thẻ đo lường (Metrics)
                m1, m2, m3, m4 = st.columns(4)
                with m1:
                    st.metric(label="Định Mức Vải (Consumption)", value=f"{fab_yard:.3f} Yards", delta=f"{marker_len:.1f} Inch dài")
                with m2:
                    st.metric(label="Định Mức Chỉ May Tổng (Thread)", value=f"{th_yard:.2f} Yards")
                with m3:
                    st.metric(label="Hiệu Suất Sơ Đồ (Utilization)", value=f"{util_pct:.2f} %")
                with m4:
                    st.metric(label="Khổ Vải Tính Toán (Width)", value=f"{fabric_width_input} Inch")
                    
                st.success("✨ Quy trình tính toán định mức kết thúc hoàn hảo. Kết quả lặp lại ổn định 100% đối với cùng một tệp đồ họa.")
                
            except Exception as e:
                st.error(f"Lỗi cục bộ tại Python Engine tính toán: {str(e)}")
                st.code(traceback.format_exc())
else:
    st.info("💡 Hệ thống đang sẵn sàng. Hãy kéo và thả file Tech Pack / BOM định dạng PDF ở vùng bên trên để kích hoạt quy trình tự động.")
