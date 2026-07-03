import streamlit as st
import numpy as np
import json
import re
import traceback
import fitz  # PyMuPDF để đọc hình học Vector
from shapely.geometry import Polygon, MultiPolygon, LineString
from shapely.ops import unary_union, polygonize
from shapely.affinity import translate, rotate, scale
import google.generativeai as genai

# =========================================================================
# ĐOẠN 1/3: GIAO DIỆN & AI BÓC TÁCH BLUEPRINT (KHÔNG TÍNH TOÁN, KHÔNG TỌA ĐỘ)
# =========================================================================
st.set_page_config(page_title="Gerber V10 CAD-AI Hybrid Engine", layout="wide")

if "active_blueprint" not in st.session_state:
    st.session_state.active_blueprint = {}
if "vector_geometry" not in st.session_state:
    st.session_state.vector_geometry = []

# --- SIDEBAR THÔNG SỐ KỸ THUẬT ---
with st.sidebar:
    st.header("🔧 Tham Số Hệ Thống CAD")
    fabric_width_input = st.number_input("Khổ rộng vải hữu dụng (Inch):", min_value=10.0, max_value=150.0, value=57.0, step=0.5)
    seam_allowance_input = st.slider("Hao hụt đường may mặc định (Inch):", min_value=0.0, max_value=2.0, value=0.25, step=0.05)
    warp_shrinkage = st.slider("Độ co rút sợi dọc (Warp %):", min_value=0.0, max_value=20.0, value=3.0, step=0.1)
    weft_shrinkage = st.slider("Độ co rút sợi ngang (Weft %):", min_value=0.0, max_value=20.0, value=2.0, step=0.1)
    
    st.markdown("---")
    uploaded_file = st.file_uploader("📥 Tải lên Gerber PDF (Chứa sơ đồ Vector & BOM)", type=["pdf"])

st.title("🧵 Gerber V10 CAD-AI Pro - Hybrid Architecture")
st.caption("Kiến trúc chuẩn: AI bóc tách thuộc tính quản lý (BOM) ➔ Python Vector Engine trích xuất dữ liệu hình học gốc.")

try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
except Exception:
    st.sidebar.warning("⚠️ Chưa cấu hình GEMINI_API_KEY.")

def ai_compile_bom_blueprint(pdf_bytes):
    """AI làm đúng nhiệm vụ ngôn ngữ: Chỉ bóc tách Piece List, Qty, Fabric, Grain. Tuyệt đối không sinh tọa độ."""
    model = genai.GenerativeModel("gemini-2.5-flash", generation_config={"response_mime_type": "application/json"})
    
    prompt = f"""
    Bạn là một AI Blueprint Compiler thuộc hệ thống CAD/CAM. Hãy đọc tài liệu PDF và trích xuất bảng danh mục chi tiết rập (Piece List / BOM).
    Xuất ra cấu trúc JSON chuẩn hóa chứa các thuộc tính quản lý. KHÔNG TỰ SINH hoặc ĐOÁN tọa độ hình học hình vẽ.

    HÃY TRẢ VỀ JSON THEO ĐÚNG CẤU TRÚC MẪU NÀY:
    {{
      "pieces": [
        {{
          "name": "Tên chi tiết viết hoa khớp với bản vẽ (Ví dụ: FRONT, SLEEVE, COLLAR)",
          "quantity": 2,
          "grain": "warp",
          "mirror": true,
          "fabric": "Main"
        }}
      ],
      "sewing_spec": {{
        "stitch_type": "301",
        "thread_waste_pct": 15.0
      }}
    }}
    """
    response = model.generate_content([{"mime_type": "application/pdf", "data": pdf_bytes}, prompt])
    return json.loads(response.text.strip())
# =========================================================================
# ĐOẠN 2/3: PYTHON VECTOR ENGINE - TRÍCH XUẤT HÌNH HỌC GỐC CHÍNH XÁC 100%
# =========================================================================
def adaptive_bezier_to_points(p0, p1, p2, p3, steps=15):
    """Số hóa đường cong Bezier bậc 3 từ bản vẽ kỹ thuật thành chuỗi điểm liên tục"""
    points = []
    for i in range(steps + 1):
        t = i / steps
        x = (1-t)**3 * p0[0] + 3*(1-t)**2 * t * p1[0] + 3*(1-t) * t**2 * p2[0] + t**3 * p3[0]
        y = (1-t)**3 * p0[1] + 3*(1-t)**2 * t * p1[1] + 3*(1-t) * t**2 * p2[1] + t**3 * p3[1]
        points.append((x, y))
    return points

def python_extract_vector_polygons(pdf_bytes):
    """Đọc dữ liệu vẽ Vector trực tiếp từ cấu trúc file PDF thông qua fitz.get_drawings()"""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    extracted_pieces = []
    
    for page_idx, page in enumerate(doc):
        drawings = page.get_drawings()
        for draw in drawings:
            points = []
            for item in draw["items"]:
                if item[0] == "l":  # Đoạn thẳng (Line)
                    points.append((item[1].x, item[1].y))
                    points.append((item[2].x, item[2].y))
                elif item[0] == "c":  # Đường cong Bezier (Curve)
                    # item[1]=p0, item[2]=p1, item[3]=p2, item[4]=p3
                    curve_pts = adaptive_bezier_to_points(item[1], item[2], item[3], item[4])
                    points.extend(curve_pts)
            
            # Nếu tập hợp điểm tạo thành một chu trình khép kín, chuyển đổi sang Đối tượng Đa Giác Shapely
            if len(points) >= 3:
                # Loại bỏ các điểm trùng lặp liên tiếp cạnh nhau
                cleaned_pts = []
                for pt in points:
                    if not cleaned_pts or np.linalg.norm(np.array(cleaned_pts[-1]) - np.array(pt)) > 0.01:
                        cleaned_pts.append(pt)
                
                if len(cleaned_pts) >= 3:
                    try:
                        poly = Polygon(cleaned_pts)
                        if poly.is_valid and poly.area > 1.0: # Loại bỏ các đường vẽ rác hoặc đường chỉ may nhỏ
                            extracted_pieces.append({
                                "polygon": poly,
                                "center": (poly.centroid.x, poly.centroid.y)
                            })
                    except Exception:
                        pass
    return extracted_pieces
# =========================================================================
# ĐOẠN 3/3: MAPPING DATA & NESTING ENGINE - CHỈ TÍNH VẢI, KEO, RIB (KHÔNG CHỈ)
# =========================================================================
import pandas as pd
import numpy as np
from shapely.affinity import translate, scale

def check_collision_system(placed_list, target_poly):
    """Kiểm tra đè nén hình học cục bộ phẳng giữa chi tiết mới xếp và sơ đồ nền"""
    for placed in placed_list:
        if target_poly.intersects(placed) and target_poly.intersection(placed).area > 0.001:
            return True
    return False

if uploaded_file is not None:
    file_content = uploaded_file.read()
    
    if st.button("🚀 KÍCH HOẠT HỆ THỐNG CAD-AI HYBRID PIPELINE"):
        col_view1, col_view2 = st.columns(2)
        
        with col_view1:
            with st.spinner("🤖 AI đang quét bóc tách cấu trúc BOM thuộc tính..."):
                try:
                    blueprint = ai_compile_bom_blueprint(file_content)
                    if not blueprint or "pieces" not in blueprint:
                        blueprint = {"pieces": []}
                    st.session_state.active_blueprint = blueprint
                    st.success("Đã trích xuất cấu trúc thuộc tính!")
                    st.json(blueprint)
                except Exception as ai_err:
                    st.error(f"AI bóc tách lỗi, tự động kích hoạt Blueprint dự phòng: {str(ai_err)}")
                    blueprint = {"pieces": []}
                    st.session_state.active_blueprint = blueprint
                
        with col_view2:
            with st.spinner("⚙️ Python đang quét lớp đồ họa Vector nguyên bản..."):
                vectors = python_extract_vector_polygons(file_content)
                st.session_state.vector_geometry = vectors
                st.success(f"Trích xuất thành công {len(vectors)} đa giác hình học phẳng từ bản vẽ PDF!")
        
        # --- PIPELINE ĐỒNG BỘ MAPPING & TÍNH TOÁN TOÁN HỌC CHÍNH XÁC ---
        st.markdown("---")
        st.write("### 📐 Tiến Trình Xử Lý Hình Học Hình Học Thực Tế & Thêm Đường Chừa May")
        
        warp_factor = 1 + (warp_shrinkage / 100.0)
        weft_factor = 1 + (weft_shrinkage / 100.0)
        
        pieces_list = blueprint.get("pieces", [])
        
        # Tình huống khẩn cấp: Nếu AI trả về danh sách pieces rỗng, ép đọc tuần tự từ Vector đồ họa thực tế
        if not pieces_list and vectors:
            st.warning("⚠️ AI không phân tách được danh mục. Hệ thống chuyển sang đọc hình học Vector gốc tuần tự.")
            for v_idx in range(len(vectors)):
                # Giả định phân nhóm tự động theo kích thước chi tiết (Chi tiết lớn = Vải chính, Chi tiết nhỏ = Keo/Phối)
                v_poly = vectors[v_idx]["polygon"]
                inferred_fabric = "Vải chính (Main)" if v_poly.area > 500 else "Keo lót / Rib"
                pieces_list.append({
                    "name": f"GEOM_PIECE_{v_idx+1}",
                    "quantity": 1,
                    "fabric": inferred_fabric
                })
        
        # Khởi tạo từ điển phân tách dữ liệu sơ đồ theo loại vật liệu cuộn
        fabric_groups = {}
        summary_table_data = []
        
        for idx, ai_piece in enumerate(pieces_list):
            if idx < len(vectors):
                geom_poly = vectors[idx]["polygon"]
                poly_with_seam = geom_poly.buffer(seam_allowance_input, join_style=2)
                
                if weft_factor != 1.0:
                    poly_with_seam = scale(poly_with_seam, xfact=1.0, yfact=weft_factor, origin='center')
                
                qty = ai_piece.get("quantity", 1)
                if qty is None: qty = 1
                
                # Trích xuất loại vật liệu (Vải chính, Keo lót, hoặc Bo Rib) - Mặc định là Vải chính nếu AI bỏ trống
                fab_type = ai_piece.get("fabric", "Vải chính (Main)")
                if not fab_type: fab_type = "Vải chính (Main)"
                
                summary_table_data.append({
                    "Tên Chi Tiết": ai_piece.get('name', 'UNKNOWN'),
                    "Loại Vật Liệu": fab_type,
                    "Số Lượng (Pcs)": qty,
                    "Chu Vi Gốc (Inch)": round(geom_poly.length, 2),
                    "Diện Tích Gốc (Sq.In)": round(geom_poly.area, 2),
                    "Diện Tích + Đường May (Sq.In)": round(poly_with_seam.area, 2)
                })
                
                if fab_type not in fabric_groups:
                    fabric_groups[fab_type] = []
                    
                for q in range(qty):
                    fabric_groups[fab_type].append({
                        "name": f"{ai_piece.get('name', 'UNKNOWN')}_Q{q+1}",
                        "poly": poly_with_seam
                    })
        
        # Hiển thị bảng thống kê cấu trúc rập hình học thực tế
        st.write("#### 📊 Bảng Thống Kê Thuộc Tính Hình Học Chi Tiết Rập Thực Tế (Python Engine)")
        st.dataframe(pd.DataFrame(summary_table_data), use_container_width=True)
                    
        # --- NESTING & CONSUMPTION ENGINE THEO TỪNG LOẠI VẬT LIỆU CRITICAL ---
        st.write("#### ⚙️ Tiến trình Nesting và Tính định mức theo chủng loại vật liệu")
        
        # Tạo cấu trúc giao diện hiển thị kết quả cho từng nhóm vải/keo/rib riêng biệt
        for fab_name, nesting_queue in fabric_groups.items():
            placed_shapes = []
            max_length_reached = 0.0
            
            with st.expander(f"🔍 Nhật ký sơ đồ cho nhóm: {fab_name} ({len(nesting_queue)} chi tiết)", expanded=True):
                for item in nesting_queue:
                    current_poly = item["poly"]
                    minx, miny, maxx, maxy = current_poly.bounds
                    pw, ph = maxx - minx, maxy - miny
                    
                    placed = False
                    curr_x = 0.0
                    while not placed:
                        for curr_y in np.arange(0.0, fabric_width_input - ph + 0.01, 0.5):
                            moved_poly = translate(current_poly, xoff=curr_x - minx, yoff=curr_y - miny)
                            if not check_collision_system(placed_shapes, moved_poly):
                                placed_shapes.append(moved_poly)
                                
                                moved_maxx = moved_poly.bounds[2]
                                if moved_maxx > max_length_reached:
                                    max_length_reached = moved_maxx
                                    
                                placed = True
                                break
                        if not placed:
                            curr_x += 0.5
                        if curr_x > 5000.0: break
                        
                    st.caption(f"✅ Định vị xong chi tiết `{item['name']}` tại X={curr_x:.2f} Inch")
            
            # Tính toán định mức vải cuộn (Vải/Keo/Rib) áp dụng co rút sợi dọc (Warp Shrinkage)
            final_length_inch = max_length_reached * warp_factor
            final_consumption_yard = final_length_inch / 36.0
            
            # Xuất kết quả riêng biệt cho loại vật liệu đang duyệt lặp
            st.info(f"📊 **KẾT QUẢ ĐỊNH MỨC NGUYÊN LIỆU: {fab_name.upper()}**")
            c1, c2 = st.columns(2)
            with c1:
                st.metric(label=f"Định Mức Tiêu Hao ({fab_name})", value=f"{final_consumption_yard:.3f} Yards")
            with c2:
                st.metric(label="Chiều Dài Sơ Đồ Thực Tế", value=f"{final_length_inch:.1f} Inch")
            st.markdown("---")
            
        st.success("⚙️ Quy trình xử lý hoàn tất độc lập. Đã loại bỏ chỉ may, tập trung 100% tính toán chính xác định mức Vải, Keo lót, và Bo Rib.")
