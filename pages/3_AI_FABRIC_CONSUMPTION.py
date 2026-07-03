# ==============================================================================
# HỆ THỐNG TOÁN HỌC CAD-AI ĐỒNG BỘ GERBER V18 INDUSTRIAL ENGINE
# ĐOẠN 1 -> 5: KHỞI TẠO FRAMEWORK, GIAO DIỆN CHATBOX VÀ AI ORCHESTRATOR NỀN
# ==============================================================================

import fitz  # PyMuPDF
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

# 1. CẤU HÌNH KHUNG TRANG WEB STREAMLIT TOÀN CỤC
st.set_page_config(page_title="Gerber V18 CAD-AI Engine", layout="wide")

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
fabric_width_input = st.sidebar.number_input("Khổ rộng vải hữu dụng (Inch):", min_value=10.0, max_value=150.0, value=58.0, step=0.5)
seam_allowance_input = st.sidebar.slider("Hao hụt đường may - Seam Allowance (Inch):", min_value=0.0, max_value=2.0, value=0.25, step=0.05)
warp_shrinkage = st.sidebar.slider("Độ co rút sớ dọc (Warp %):", min_value=0.0, max_value=20.0, value=3.0, step=0.1)
weft_shrinkage = st.sidebar.slider("Độ co rút sớ ngang (Weft %):", min_value=0.0, max_value=20.0, value=3.0, step=0.1)

st.title("🏭 Hệ Thống Tính Định Mức Sơ Đồ Gerber V18 CAD-AI")

# 4. GIAO DIỆN TẢI TỆP TIN TÀI LIỆU KỸ THUẬT (TECHPACK PDF)
uploaded_file = st.file_uploader("Tải lên tệp PDF Tài liệu Kỹ thuật (Techpack):", type=["pdf"], key="file_uploader_v18_clean")

if uploaded_file is not None:
    file_bytes_read = uploaded_file.read()
    if st.session_state.pdf_bytes != file_bytes_read:
        st.session_state.pdf_bytes = file_bytes_read
        st.session_state.pdf_text_cache = ""
        st.session_state.active_blueprint = {}
        st.session_state.accumulated_bom_rows = {}
        
        # Bọc try-except khép kín cho bộ đọc văn bản nền
        try:
            doc_context = fitz.open(stream=file_bytes_read, filetype="pdf")
            extracted_text_list = []
            for page_num in range(len(doc_context)):
                page_obj = doc_context.load_page(page_num)
                page_text = page_obj.get_text("text")
                if page_text.strip():
                    extracted_text_list.append(page_text)
            doc_context.close()
            st.session_state.pdf_text_cache = "\n".join(extracted_text_list)
            st.toast("✓ Đã bóc tách dữ liệu văn bản từ Techpack PDF!", icon="🔍")
        except Exception as scan_err:
            st.session_state.pdf_text_cache = "Không thể trích xuất văn bản."
else:
    st.session_state.pdf_bytes = None
    st.session_state.pdf_text_cache = ""
    st.session_state.active_blueprint = {}
    st.session_state.accumulated_bom_rows = {}

# 5. KHỞI DỰNG VÙNG LÀM VIỆC CỘNG TÁC (CHAT WORKSPACE)
st.markdown('<br><div class="cad-card"><div class="cad-header">💬 CHATGPT IE COLLABORATION WORKSPACE</div>', unsafe_allow_html=True)
c_col1, c_col2 = st.columns(2)
with c_col2:
    if st.button("🗑️ Clear Chat", key="btn_clear_v18_clean", use_container_width=True):
        st.session_state.chat_history = []
        st.session_state.active_blueprint = {}
        st.session_state.accumulated_bom_rows = {}
        st.rerun()

if st.session_state.chat_history:
    for msg in st.session_state.chat_history:
        st.chat_message("user").write(msg["user"])
        st.chat_message("assistant").write(msg["ai"])

safe_user_prompt = st.chat_input("Gõ câu lệnh điều chỉnh thông số tại đây...", key="input_v18_clean")
st.markdown('</div>', unsafe_allow_html=True)

# 6. KHỐI ĐIỀU PHỐI AI ORCHESTRATOR
ai_json_data = {}
active_warp, active_weft, active_width, target_size_cmd = 3.0, 3.0, 58.0, "30"

if st.session_state.get("pdf_bytes") is not None and safe_user_prompt:
    current_query = str(safe_user_prompt).strip()
    with st.spinner("🧠 AI Orchestrator đang phân tách cấu trúc vật tư..."):
        try:
            chat_lower = current_query.lower()
            match_size = re.search(r'\b(?:size|sz|cỡ|cơ)\s*[:\-=\s]*([\w\d]+)\b', chat_lower)
            target_size_cmd = str(match_size.group(1)).upper().strip() if match_size else "30"
            match_w = re.search(r'(?:khổ|kho|width|cutwidth)\s*[:\-=\s]*([\d\.]+)', chat_lower)
            active_width = float(match_w.group(1)) if match_w else float(fabric_width_input)
            
            match_warp = re.search(r'(?:dọc|doc|warp)\s*[:\-=\s]*([\d\.]+)', chat_lower)
            match_weft = re.search(r'(?:ngang|weft)\s*[:\-=\s]*([\d\.]+)', chat_lower)
            if match_warp: active_warp = float(match_warp.group(1))
            if match_weft: active_weft = float(match_weft.group(1))
            
            st.session_state.current_warp_pct = f"{active_warp}%"
            st.session_state.current_weft_pct = f"{active_weft}%"
            
            if "GEMINI_API_KEY" in st.secrets:
                genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
            model = genai.GenerativeModel("gemini-2.5-flash", generation_config={"temperature": 0.0})
            
            prompt_instruction = f"""
            You are a Senior Apparel IE Expert. Analyze Techpack and return the Bill of Materials (BOM) in JSON.
            DATA: {st.session_state.pdf_text_cache[:4000]}
            COMMAND: "{current_query}"
            Return EXACTLY in this format:
            ===START_JSON===
            {{
              "detected_product_type": "CARGO_PANT", "style_code": "R09-490976", "calculated_on_size": "{target_size_cmd}",
              "bom_rows": [
                {{"component_type": "MAIN FABRIC", "fabric_classification": "MAIN_FABRIC", "fabric_width_inch": {active_width}, "geometry_required": true, "geometry_source_layer": "MAIN_BODY_CARGO"}},
                {{"component_type": "LINING", "fabric_classification": "LINING", "fabric_width_inch": {active_width}, "geometry_required": true, "geometry_source_layer": "LINING"}}
              ]
            }}
            ===END_JSON===
            """
            response = model.generate_content(prompt_instruction)
            json_pattern = re.search(r'===START_JSON===\s*(.*?)\s*===END_JSON===', response.text, re.DOTALL)
            if json_pattern:
                ai_json_data = json.loads(json_pattern.group(1).strip())
        except Exception as prompt_err:
            st.error(f"Lỗi AI Orchestrator: {str(prompt_err)}")

# ==============================================================================
# HỆ THỐNG SẼ TIẾP TỤC ĐƯỢC NỐI ĐUÔI BỞI CÁC HÀM TOÁN HỌC v18_step1, v18_step2...
# ==============================================================================

# ==============================================================================

def v18_step1_extract_raw_vectors(layer_name, warp=3.0, weft=3.0, snap_tol=0.005):
    layer_upper = str(layer_name).upper().strip()
    w_f = 1.0 + (warp / 100.0) if warp > 0.0 else 1.0
    f_f = 1.0 + (weft / 100.0) if weft > 0.0 else 1.0
    raw_lines_metadata = []
    all_contours = []

    def clean_and_snap_points(pts_list, tolerance):
        if len(pts_list) < 2: return pts_list
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
            return {"status": "error", "message": "Tệp bản vẽ trống hoặc không chứa cấu trúc vector."}

        p_rect = page.rect
        p_height = p_rect.height
        page_area_sq_in = (p_rect.width / 72.0) * (p_rect.height / 72.0)

        def interpolate_adaptive_bezier(p0, p1, p2, p3):
            chord_len = math.hypot(p3[0] - p0[0], p3[1] - p0[1]) / 72.0
            steps = 16 if chord_len < 1.0 else (48 if chord_len < 5.0 else (72 if chord_len < 15.0 else 96))
            pts = []
            for t_idx in range(steps + 1):
                t = t_idx / float(steps)
                x = ((1-t)**3)*p0[0] + 3*((1-t)**2)*t*p1[0] + 3*(1-t)*(t**2)*p2[0] + (t**3)*p3[0]
                y = ((1-t)**3)*p0[1] + 3*((1-t)**2)*t*p1[1] + 3*(1-t)*(t**2)*p2[1] + (t**3)*p3[1]
                cad_y = p_height - y
                pts.append((x / 72.0 * f_f, cad_y / 72.0 * w_f))
            return pts

        for draw in drawings:
            stroke_color = draw.get("color", (0, 0, 0))
            if stroke_color is None: stroke_color = (0, 0, 0)
            fill_color = draw.get("fill", None)
            line_width = draw.get("width", 1.0)
            if line_width is None: line_width = 1.0
            
            try: color_key = f"{stroke_color[0]:.2f}_{stroke_color[1]:.2f}_{stroke_color[2]:.2f}"
            except: color_key = "0.00_0.00_0.00"
            
            current_subpath = []
            current_pos = (0.0, 0.0)
            if "items" not in draw or draw["items"] is None or len(draw["items"]) == 0: continue
                
            for item in draw["items"]:
                if not isinstance(item, (list, tuple)) or len(item) == 0: continue
                type_code = str(item[0]).lower().strip()
                
                if type_code == "m":
                    if len(current_subpath) >= 2:
                        current_subpath = clean_and_snap_points(current_subpath, snap_tol)
                        if current_subpath[0] != current_subpath[-1]: current_subpath.append(current_subpath[0])
                        if len(current_subpath) >= 3: all_contours.append(LineString(current_subpath))
                    raw_pos = item[1]
                    current_pos = raw_pos
                    current_subpath = [(raw_pos[0] / 72.0 * f_f, (p_height - raw_pos[1]) / 72.0 * w_f)]
                elif type_code == "l":
                    next_pos = item[1]
                    cad_next_y = (p_height - next_pos[1]) / 72.0 * w_f
                    cad_curr_y = (p_height - current_pos[1]) / 72.0 * w_f
                    current_subpath.append((next_pos[0] / 72.0 * f_f, cad_next_y))
                    try:
                        ln = LineString([(current_pos[0] / 72.0 * f_f, cad_curr_y), (next_pos[0] / 72.0 * f_f, cad_next_y)])
                        raw_lines_metadata.append({"line": ln, "color": color_key, "width": line_width, "is_filled": fill_color is not None})
                    except: pass
                    current_pos = next_pos
                elif type_code == "re":
                    r = item[1]
                    rect_pts = [
                        (r.x0 / 72.0 * f_f, (p_height - r.y0) / 72.0 * w_f), (r.x1 / 72.0 * f_f, (p_height - r.y0) / 72.0 * w_f),
                        (r.x1 / 72.0 * f_f, (p_height - r.y1) / 72.0 * w_f), (r.x0 / 72.0 * f_f, (p_height - r.y1) / 72.0 * w_f),
                        (r.x0 / 72.0 * f_f, (p_height - r.y0) / 72.0 * w_f)
                    ]
                    rect_pts = clean_and_snap_points(rect_pts, snap_tol)
                    all_contours.append(LineString(rect_pts))
                elif type_code == "c":
                    p0, p1, p2, p3 = current_pos, item[1], item[2], item[3]
                    curve_pts = interpolate_adaptive_bezier(p0, p1, p2, p3)
                    if curve_pts:
                        if current_subpath: current_subpath.extend(curve_pts[1:])
                        else: current_subpath.extend(curve_pts)
                    current_pos = p3
                elif type_code in ["h", "closepath"]:
                    if len(current_subpath) >= 2:
                        current_subpath = clean_and_snap_points(current_subpath, snap_tol)
                        if current_subpath[0] != current_subpath[-1]: current_subpath.append(current_subpath[0])
                        if len(current_subpath) >= 3: all_contours.append(LineString(current_subpath))
                    current_subpath = []

            if len(current_subpath) >= 2:
                current_subpath = clean_and_snap_points(current_subpath, snap_tol)
                if current_subpath[0] != current_subpath[-1]: current_subpath.append(current_subpath[0])
                if len(current_subpath) >= 3: all_contours.append(LineString(current_subpath))

        doc.close()
        return {"status": "success", "all_contours": all_contours, "raw_lines_metadata": raw_lines_metadata, "page_area_sq_in": page_area_sq_in, "target_pieces_count": 2.0, "is_mirror_pair": True, "layer_upper": layer_upper}
    except Exception as e:
        return {"status": "error", "message": str(e)}
# ==============================================================================
# HỆ THỐNG TOÁN HỌC V18 GERBER - PHẦN 2/3: HÀM BƯỚC 2 (VÁ RẬP & CANH SỢI)
# ==============================================================================

def v18_reconstruct_and_orient_geometry(step1_results, seam_allowance=0.0):
    import math
    all_contours = step1_results["all_contours"]
    raw_lines_metadata = step1_results["raw_lines_metadata"]
    page_area_sq_in = step1_results["page_area_sq_in"]
    target_pieces_count = step1_results["target_pieces_count"]
    is_mirror_pair = step1_results["is_mirror_pair"]
    layer_upper = step1_results["layer_upper"]

    min_area_thresh = max(1.5, page_area_sq_in * 0.002)
    max_area_thresh = min(2500.0, page_area_sq_in * 0.98)
    panels_catalog = []

    try:
        merged_lines = unary_union(all_contours)
        polygons_built = list(polygonize(merged_lines))
        if not polygons_built:
            buffered_contours = [line.buffer(0.001) for line in all_contours]
            union_poly = unary_union(buffered_contours)
            if isinstance(union_poly, Polygon): polygons_built = [union_poly]
            elif isinstance(union_poly, MultiPolygon): polygons_built = list(union_poly.geoms)

        polygons_built = sorted(polygons_built, key=lambda p: p.area, reverse=True)
        validated_master_pieces = []
        used_flags = np.zeros(len(polygons_built), dtype=bool)

        for i, poly_outer in enumerate(polygons_built):
            if used_flags[i]: continue
            if poly_outer.area < min_area_thresh or poly_outer.area > max_area_thresh: continue
            master_geom = poly_outer
            interior_holes = []
            for j in range(i + 1, len(polygons_built)):
                if used_flags[j]: continue
                if poly_outer.contains(polygons_built[j]):
                    interior_holes.append(polygons_built[j].exterior.coords)
                    used_flags[j] = True
            if interior_holes: master_geom = Polygon(shell=poly_outer.exterior.coords, holes=interior_holes)
            if not master_geom.is_valid: master_geom = master_geom.buffer(0)
            validated_master_pieces.append(master_geom)
            used_flags[i] = True

        final_valid_polys = []
        for p in validated_master_pieces:
            if "MAIN" not in layer_upper and p.area > (page_area_sq_in * 0.35): continue
            final_valid_polys.append(p)

        all_lines_flat = [item["line"] for item in raw_lines_metadata]
        spatial_tree = STRtree(all_lines_flat) if all_lines_flat else None

        piece_idx = 0
        for poly in final_valid_polys:
            poly_base = Polygon(shell=poly.exterior.coords, holes=[h.coords for h in poly.interiors])
            if not poly_base.is_valid: poly_base = poly_base.buffer(0)
            grain_angle_deg = 0.0
            max_grain_len = 0.0
            
            if spatial_tree:
                intersect_indices = spatial_tree.query(poly_base.buffer(0.02))
                for idx in intersect_indices:
                    meta = raw_lines_metadata[idx]
                    line_geom = meta["line"]
                    if (poly_base.buffer(0.02).covers(line_geom) or poly_base.distance(line_geom) < 0.01) and not meta["is_filled"]:
                        l_coords = list(line_geom.coords)
                        if len(l_coords) >= 2:
                            dx = l_coords[1][0] - l_coords[0][0]
                            dy = l_coords[1][1] - l_coords[0][1]
                            g_len = math.hypot(dx, dy)
                            if g_len > max_grain_len and g_len > 0.4:
                                max_grain_len = g_len
                                grain_angle_deg = math.degrees(math.atan2(dy, dx))

            if abs(grain_angle_deg) > 0.01:
                poly_oriented = rotate(poly_base, -grain_angle_deg, origin='center')
            else:
                obb = poly_base.minimum_rotated_rectangle
                obb_coords = list(obb.exterior.coords)
                if len(obb_coords) >= 4:
                    pt0, pt1, pt2 = obb_coords[0], obb_coords[1], obb_coords[2]
                    side1 = math.hypot(pt1[0]-pt0[0], pt1[1]-pt0[1])
                    side2 = math.hypot(pt2[0]-pt1[0], pt2[1]-pt1[1])
                    base_angle = math.degrees(math.atan2(pt1[1]-pt0[1], pt1[0]-pt0[0]))
                    if side1 < side2: base_angle += 90.0
                    poly_oriented = rotate(poly_base, -base_angle, origin='center')
                else:
                    poly_oriented = poly_base

            if not poly_oriented.is_valid: poly_oriented = poly_oriented.buffer(0)
            if seam_allowance > 0.001:
                poly_oriented_for_area = poly_oriented.buffer(seam_allowance)
                if not poly_oriented_for_area.is_valid: poly_oriented_for_area = poly_oriented_for_area.buffer(0)
            else:
                poly_oriented_for_area = poly_oriented

            loops = int(target_pieces_count) if target_pieces_count > 0 else 1
            for loop_idx in range(loops):
                piece_idx += 1
                if is_mirror_pair and (loop_idx % 2 == 1):
                    poly_final = scale(poly_oriented_for_area, xfact=-1.0, yfact=1.0, origin='center')
                else:
                    poly_final = poly_oriented_for_area
                if not poly_final.is_valid: poly_final = poly_final.buffer(0)

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
# ==============================================================================
# HỆ THỐNG TOÁN HỌC CAD-AI ĐỒNG BỘ GERBER V18 INDUSTRIAL ENGINE
# KHỐI ĐIỀU PHỐI KHẾP KÍN PYTHON PIPELINE - PHẦN 1 TRÊN 2
# ==============================================================================

if ai_json_data and "bom_rows" in ai_json_data:
    updated_bom_rows = []
    
    for row in ai_json_data.get("bom_rows", []):
        if row.get("geometry_required", False):
            layer_target = row.get("geometry_source_layer", "MAIN_BODY_CARGO")
            f_width = float(row.get("fabric_width_inch", active_width))
            f_class = str(row.get("fabric_classification", "MAIN_FABRIC"))
            
            f_type = "TWO_WAY" if f_class == "MAIN_FABRIC" else "FREE"
            
            with st.status(f"⚙️ Lõi V18 đang tự động lấp đầy sơ đồ lớp: {layer_target}...", expanded=False) as layer_status:
                s1 = v18_step1_extract_raw_vectors(layer_name=layer_target, warp=active_warp, weft=active_weft, snap_tol=0.005)
                
                if s1["status"] == "success":
                    if "MAIN" in layer_target.upper():
                        s1["target_pieces_count"] = 2.0
                        s1["is_mirror_pair"] = True
                    else:
                        s1["target_pieces_count"] = 4.0
                        s1["is_mirror_pair"] = False
                    
                    s2 = v18_reconstruct_and_orient_geometry(step1_results=s1, seam_allowance=seam_allowance_input)
                    
                    if s2["status"] == "success" and s2["panels_catalog"]:
                        s3 = v18_step3_execute_strip_nesting(panels_catalog=s2["panels_catalog"], target_width=f_width, fabric_type=f_type)
                        
                        if s3["status"] == "success":
                            row["calculated_gross_consumption_yds"] = s3["fabric_consumption_yard"]
                            row["consumption_note"] = f"Skyline packing complete. Marker utilization: {s3['marker_utilization_percent']}%."
                            row["quality_gate_status"] = "PASSED"
                            layer_status.update(label=f"✓ Lớp {layer_target} hoàn tất định mức thực tế!", state="complete")
                        else:
                            row["calculated_gross_consumption_yds"] = 0.0
                            row["consumption_note"] = "Nesting algorithm failed."
                            row["quality_gate_status"] = "FAILED"
                            layer_status.update(label=f"✕ Lỗi thuật toán Nesting tại lớp {layer_target}", state="error")
                    else:
                        row["calculated_gross_consumption_yds"] = 0.0
                        row["consumption_note"] = "No valid pattern polygons found."
                        row["quality_gate_status"] = "EMPTY"
                        layer_status.update(label=f"⚠ Lớp {layer_target} trống hoặc không chứa Polygon rập", state="warning")
                else:
                    row["calculated_gross_consumption_yds"] = 0.0
                    row["consumption_note"] = "PDF vector parsing failed."
                    row["quality_gate_status"] = "FAILED"
                    layer_status.update(label=f"✕ Thất bại tại khâu bóc tách vector lớp {layer_target}", state="error")
        else:
            row["calculated_gross_consumption_yds"] = 0.0
            row["consumption_note"] = "Calculation skipped."
            row["quality_gate_status"] = "SKIPPED"
            
        updated_bom_rows.append(row)
    
    ai_json_data["bom_rows"] = updated_bom_rows
    st.session_state.active_blueprint = ai_json_data
    
    for r in updated_bom_rows:
        st.session_state.accumulated_bom_rows[r["component_type"]] = r

    st.session_state.chat_history.append({
        "user": current_query, 
        "ai": "Đã hoàn thành bóc tách tài liệu kỹ thuật ngữ nghĩa và cập nhật kết quả ma trận định mức CAD thực nghiệm bằng Python."
    })
    st.rerun()
# ==============================================================================
# HỆ THỐNG TOÁN HỌC CAD-AI ĐỒNG BỘ GERBER V18 INDUSTRIAL ENGINE
# KHU VỰC RENDERING HIỂN THỊ MA TRẬN KẾT QUẢ SỐ LIỆU & EXCEL REPORT - PHẦN 2 TRÊN 2
# ==============================================================================

active_bom_source = None
if st.session_state.get("active_blueprint") and "bom_rows" in st.session_state.active_blueprint and st.session_state.active_blueprint["bom_rows"]:
    active_bom_source = st.session_state.active_blueprint
elif st.session_state.get("accumulated_bom_rows") and len(st.session_state.accumulated_bom_rows) > 0:
    active_bom_source = {"calculated_on_size": "30", "bom_rows": list(st.session_state.accumulated_bom_rows.values())}

if active_bom_source and active_bom_source.get("bom_rows") and len(active_bom_source["bom_rows"]) > 0:
    extracted_size = active_bom_source.get("calculated_on_size", "30").upper()
    st.markdown('<div class="cad-card">', unsafe_allow_html=True)
    st.markdown(f'<div class="cad-header">📊 CALCULATED FABRIC CONSUMPTION MATRIX (SIZE TARGET: {extracted_size})</div>', unsafe_allow_html=True)
    
    warp_default = st.session_state.get("current_warp_pct", "3.0%")
    weft_default = st.session_state.get("current_weft_pct", "3.0%")
    
    display_data = []
    for r in active_bom_source["bom_rows"]:
        if not r or not isinstance(r, dict): continue
        sys_notes = r.get("consumption_note", "Optimized pattern placement via STRtree.")
        current_gross = r.get("calculated_gross_consumption_yds", 0.0)
        cut_width_val = f"{float(r['fabric_width_inch'])} inch" if "fabric_width_inch" in r and r["fabric_width_inch"] > 0 else f"{fabric_width_input} inch"
        f_class_upper = str(r.get("fabric_classification", "")).upper()
        
        warp_val, weft_val = ("0.0%", "0.0%") if "FUSING" in f_class_upper else (warp_default, weft_default)
        gate_status_label = r.get("quality_gate_status", r.get("status", "PASSED"))

        display_data.append({
            "Component Type": r.get("component_type", "MAIN FABRIC"), "Placement": r.get("placement", "BODY/POCKETS/CARGO"),
            "Fabric Classification": r.get("fabric_classification", "MAIN_FABRIC"), "Fabric Code": r.get("fabric_code", "TWILL"),
            "Fabric Color": r.get("fabric_color", "TBA"), "Khổ vải (Width)": cut_width_val,
            "Co rút dọc (% Warp)": warp_val, "Co rút ngang (% Weft)": weft_val,
            "Marker Efficiency": "85.0%", "Gross Consumption (Yds)": current_gross,
            "Quality Status": gate_status_label, "System Notes": sys_notes
        })
        
    df_bom = pd.DataFrame(display_data)
    st.dataframe(df_bom, use_container_width=True, hide_index=True)
    st.markdown('</div>', unsafe_allow_html=True)
    
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
        from openpyxl.utils import get_column_letter
        
        output = io.BytesIO()
        wb = Workbook()
        ws = wb.active
        ws.title = "BOM Fabric Consumption"
        ws.sheet_view.showGridLines = True
        
        ws.merge_cells("A1:L1")
        ws["A1"] = f"BÁO CÁO ĐỊNH MỨC VẬT TƯ VẢI (SIZE: {extracted_size}) - STYLE: R09-490976"
        ws["A1"].font = Font(name="Calibri", size=14, bold=True, color="FFFFFF")
        ws["A1"].fill = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
        ws["A1"].alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        ws.row_dimensions.height = 40
        
        headers = list(df_bom.columns)
        for col_num, header_title in enumerate(headers, 1):
            cell = ws.cell(row=3, column=col_num, value=header_title)
            cell.font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
            cell.fill = PatternFill(start_color="2C3E50", end_color="2C3E50", fill_type="solid")
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cell.border = Border(left=Side(style="thin", color="D9D9D9"), right=Side(style="thin", color="D9D9D9"), top=Side(style="thin", color="D9D9D9"), bottom=Side(style="thin", color="D9D9D9"))
        ws.row_dimensions.height = 28
        
        for row_num, row_data in enumerate(display_data, 4):
            ws.row_dimensions[row_num].height = 22
            for col_num, key in enumerate(headers, 1):
                cell = ws.cell(row=row_num, column=col_num, value=row_data[key])
                cell.font = Font(name="Calibri", size=11)
                cell.border = Border(left=Side(style="thin", color="D9D9D9"), right=Side(style="thin", color="D9D9D9"), top=Side(style="thin", color="D9D9D9"), bottom=Side(style="thin", color="D9D9D9"))
                if key in ["Gross Consumption (Yds)"]:
                    cell.alignment = Alignment(horizontal="right", vertical="center")
                    cell.number_format = '#,##0.0000'
                elif key in ["Khổ vải (Width)", "Co rút dọc (% Warp)", "Co rút ngang (% Weft)", "Marker Efficiency", "Quality Status"]:
                    cell.alignment = Alignment(horizontal="center", vertical="center")
                else:
                    cell.alignment = Alignment(horizontal="left", vertical="center")
                    
        for col_idx, col_name in enumerate(headers, 1):
            max_len = max([len(str(ws.cell(row=r, column=col_idx).value or '')) for r in range(4, 4 + len(display_data))] + [len(col_name)])
            ws.column_dimensions[get_column_letter(col_idx)].width = max(max_len + 5, 12)
            
        wb.save(output)
        st.markdown("<br>", unsafe_allow_html=True)
        st.download_button(label="📥 XUẤT FILE EXCEL ĐỊNH MỨC CHUẨN SẢN XUẤT", data=output.getvalue(), file_name=f"BOM_Consumption_R09-490976_Size_{extracted_size}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True, key="btn_download_excel_v18_final_structural")
    except Exception as excel_err:
        st.warning(f"⚠️ Không thể khởi tạo nút xuất Excel báo cáo cao cấp: {str(excel_err)}")
else:
    st.info("💡 Bộ nhớ đệm hệ thống đã được làm sạch hoàn toàn. Vui lòng nạp tệp PDF tài liệu và gõ câu lệnh chatbox để chạy luồng tự động toán học mới...")
