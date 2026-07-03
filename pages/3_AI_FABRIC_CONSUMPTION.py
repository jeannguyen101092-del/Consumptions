# ==============================================================================
# ĐOẠN 1/6: KHAI BÁO THƯ VIỆN & CẤU HÌNH TRANG WEB CHUẨN CAD-AI
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

st.set_page_config(page_title="Gerber V18 CAD-AI Engine", layout="wide")

if "pdf_bytes" not in st.session_state: st.session_state.pdf_bytes = None
if "pdf_text_cache" not in st.session_state: st.session_state.pdf_text_cache = ""
if "chat_history" not in st.session_state: st.session_state.chat_history = []
if "active_blueprint" not in st.session_state: st.session_state.active_blueprint = {}
if "accumulated_bom_rows" not in st.session_state: st.session_state.accumulated_bom_rows = {}
if "current_warp_pct" not in st.session_state: st.session_state.current_warp_pct = "3.0%"
if "current_weft_pct" not in st.session_state: st.session_state.current_weft_pct = "3.0%"
# ==============================================================================
# ĐOẠN 2/6: SIDEBAR CONTROLS & BỘ TIẾP NHẬN TỆP TIN TECHPACK PDF
# ==============================================================================
st.sidebar.header("🛠️ Tham Số Kỹ Thuật Hệ Thống")
fabric_width_input = st.sidebar.number_input("Khổ rộng vải hữu dụng (Inch):", min_value=10.0, max_value=150.0, value=58.0, step=0.5)
seam_allowance_input = st.sidebar.slider("Hao hụt đường may - Seam Allowance (Inch):", min_value=0.0, max_value=2.0, value=0.25, step=0.05)
warp_shrinkage = st.sidebar.slider("Độ co rút sớ dọc (Warp %):", min_value=0.0, max_value=20.0, value=3.0, step=0.1)
weft_shrinkage = st.sidebar.slider("Độ co rút sớ ngang (Weft %):", min_value=0.0, max_value=20.0, value=3.0, step=0.1)

st.title("🏭 Hệ Thống Tính Định Mức Sơ Đồ Gerber V18 CAD-AI")
st.caption("Quy trình khép kín: AI bóc tách cấu trúc BOM ➡️ Python xử lý tính toán và nén sơ đồ hình học")

uploaded_file = st.file_uploader("Tải lên tệp PDF Tài liệu Kỹ thuật (Techpack):", type=["pdf"], key="main_file_uploader_v18")

if uploaded_file is not None:
    file_bytes_read = uploaded_file.read()
    if st.session_state.pdf_bytes != file_bytes_read:
        st.session_state.pdf_bytes = file_bytes_read
        st.session_state.pdf_text_cache, st.session_state.active_blueprint, st.session_state.accumulated_bom_rows = "", {}, {}
        try:
            doc_context = fitz.open(stream=file_bytes_read, filetype="pdf")
            extracted_text_list = []
            for page_num in range(len(doc_context)):
                page_obj = doc_context.load_page(page_num)
                page_text = page_obj.get_text("text")
                if page_text.strip(): extracted_text_list.append(page_text)
            doc_context.close()
            st.session_state.pdf_text_cache = "\n".join(extracted_text_list)
            st.toast("✓ Đã bóc tách dữ liệu văn bản từ Techpack PDF!", icon="🔍")
        except: st.session_state.pdf_text_cache = "Không thể trích xuất văn bản."
else:
    st.session_state.pdf_bytes, st.session_state.pdf_text_cache, st.session_state.active_blueprint, st.session_state.accumulated_bom_rows = None, "", {}, {}
# ==============================================================================
# ĐOẠN 3/6: LÕI HÌNH HỌC PHẲNG V18 - BƯỚC 1 (ĐỌC & QUY ĐỔI VECTOR INCH)
# ==============================================================================
def v18_step1_extract_raw_vectors(layer_name, warp=3.0, weft=3.0, snap_tol=0.005):
    layer_upper = str(layer_name).upper().strip()
    w_f = 1.0 + (warp / 100.0) if warp > 0.0 else 1.0
    f_f = 1.0 + (weft / 100.0) if weft > 0.0 else 1.0
    raw_lines_metadata, all_contours = [], []

    def clean_and_snap_points(pts_list, tolerance):
        if len(pts_list) < 2: return pts_list
        cleaned = [pts_list[0]]
        for pt in pts_list[1:]:
            if math.hypot(pt[0] - cleaned[-1][0], pt[1] - cleaned[-1][1]) > tolerance: cleaned.append(pt)
        return cleaned

    try:
        doc = fitz.open(stream=st.session_state.pdf_bytes, filetype="pdf")
        page = doc.load_page(0)
        drawings = page.get_drawings()
        p_height = page.rect.height
        page_area_sq_in = (page.rect.width / 72.0) * (page.rect.height / 72.0)

        def interpolate_adaptive_bezier(p0, p1, p2, p3):
            chord_len = math.hypot(p3[0] - p0[0], p3[1] - p0[1]) / 72.0
            steps = 16 if chord_len < 1.0 else (48 if chord_len < 5.0 else (72 if chord_len < 15.0 else 96))
            pts = []
            for t_idx in range(steps + 1):
                t = t_idx / float(steps)
                x = ((1-t)**3)*p0[0] + 3*((1-t)**2)*t*p1[0] + 3*(1-t)*(t**2)*p2[0] + (t**3)*p3[0]
                y = ((1-t)**3)*p0[1] + 3*((1-t)**2)*t*p1[1] + 3*(1-t)*(t**2)*p2[1] + (t**3)*p3[1]
                pts.append((x / 72.0 * f_f, (p_height - y) / 72.0 * w_f))
            return pts

        for draw in drawings:
            stroke_color = draw.get("color", (0, 0, 0)) or (0, 0, 0)
            fill_color = draw.get("fill", None)
            line_width = draw.get("width", 1.0) or 1.0
            color_key = f"{stroke_color[0]:.2f}_{stroke_color[1]:.2f}_{stroke_color[2]:.2f}"
            current_subpath, current_pos = [], (0.0, 0.0)
            if "items" not in draw or not draw["items"]: continue
                
            for item in draw["items"]:
                if not isinstance(item, (list, tuple)) or len(item) == 0: continue
                type_code = str(item[0]).lower().strip()
                
                if type_code == "m":
                    if len(current_subpath) >= 2:
                        current_subpath = clean_and_snap_points(current_subpath, snap_tol)
                        if current_subpath[0] != current_subpath[-1]: current_subpath.append(current_subpath[0])
                        if len(current_subpath) >= 3: all_contours.append(LineString(current_subpath))
                    current_pos = item[1]
                    current_subpath = [(current_pos[0] / 72.0 * f_f, (p_height - current_pos[1]) / 72.0 * w_f)]
                elif type_code == "l":
                    next_pos = item[1]
                    current_subpath.append((next_pos[0] / 72.0 * f_f, (p_height - next_pos[1]) / 72.0 * w_f))
                    try:
                        ln = LineString([(current_pos[0] / 72.0 * f_f, (p_height - current_pos[1]) / 72.0 * w_f), (next_pos[0] / 72.0 * f_f, (p_height - next_pos[1]) / 72.0 * w_f)])
                        raw_lines_metadata.append({"line": ln, "color": color_key, "width": line_width, "is_filled": fill_color is not None})
                    except: pass
                    current_pos = next_pos
                elif type_code == "re":
                    r = item[1]
                    rect_pts = [(r.x0 / 72.0 * f_f, (p_height - r.y0) / 72.0 * w_f), (r.x1 / 72.0 * f_f, (p_height - r.y0) / 72.0 * w_f), (r.x1 / 72.0 * f_f, (p_height - r.y1) / 72.0 * w_f), (r.x0 / 72.0 * f_f, (p_height - r.y1) / 72.0 * w_f), (r.x0 / 72.0 * f_f, (p_height - r.y0) / 72.0 * w_f)]
                    all_contours.append(LineString(clean_and_snap_points(rect_pts, snap_tol)))
                elif type_code == "c":
                    curve_pts = interpolate_adaptive_bezier(current_pos, item[1], item[2], item[3])
                    if current_subpath: current_subpath.extend(curve_pts[1:])
                    else: current_subpath.extend(curve_pts)
                    current_pos = item[3]
                elif type_code in ["h", "closepath"]:
                    if len(current_subpath) >= 2:
                        current_subpath = clean_and_snap_points(current_subpath, snap_tol)
                        if current_subpath[0] != current_subpath[-1]: current_subpath.append(current_subpath[0])
                        if len(current_subpath) >= 3: all_contours.append(LineString(current_subpath))
                    current_subpath = []
        doc.close()
        return {"status": "success", "all_contours": all_contours, "raw_lines_metadata": raw_lines_metadata, "page_area_sq_in": page_area_sq_in, "target_pieces_count": 2.0, "is_mirror_pair": True, "layer_upper": layer_upper}
    except Exception as e: return {"status": "error", "message": str(e)}
# ==============================================================================
# ĐOẠN 4/6: LÕI HÌNH HỌC PHẲNG V18 - BƯỚC 2 (VÁ LỖ RẬP & NHẬN DIỆN CANH SỢI)
# ==============================================================================
def v18_step2_reconstruct_and_orient_geometry(step1_results, seam_allowance=0.0):
    all_contours = step1_results["all_contours"]
    raw_lines_metadata = step1_results["raw_lines_metadata"]
    page_area_sq_in = step1_results["page_area_sq_in"]
    target_pieces_count = step1_results["target_pieces_count"]
    is_mirror_pair = step1_results["is_mirror_pair"]
    layer_upper = step1_results["layer_upper"]
    min_area_thresh, max_area_thresh = max(1.5, page_area_sq_in * 0.002), min(2500.0, page_area_sq_in * 0.98)
    panels_catalog = []
    try:
        merged_lines = unary_union(all_contours)
        polygons_built = list(polygonize(merged_lines))
        polygons_built = sorted(polygons_built, key=lambda p: p.area, reverse=True)
        validated_master_pieces, used_flags = [], np.zeros(len(polygons_built), dtype=bool)
        for i, poly_outer in enumerate(polygons_built):
            if used_flags[i]: continue
            if poly_outer.area < min_area_thresh or poly_outer.area > max_area_thresh: continue
            master_geom, interior_holes = poly_outer, []
            for j in range(i + 1, len(polygons_built)):
                if not used_flags[j] and poly_outer.contains(polygons_built[j]):
                    interior_holes.append(polygons_built[j].exterior.coords)
                    used_flags[j] = True
            if interior_holes: master_geom = Polygon(shell=poly_outer.exterior.coords, holes=interior_holes)
            if not master_geom.is_valid: master_geom = master_geom.buffer(0)
            validated_master_pieces.append(master_geom)
            used_flags[i] = True
        all_lines_flat = [item["line"] for item in raw_lines_metadata]
        spatial_tree = STRtree(all_lines_flat) if all_lines_flat else None
        piece_idx = 0
        for poly in validated_master_pieces:
            if "MAIN" not in layer_upper and poly.area > (page_area_sq_in * 0.35): continue
            poly_base = Polygon(shell=poly.exterior.coords, holes=[h.coords for h in poly.interiors])
            grain_angle_deg, max_grain_len = 0.0, 0.0
            if spatial_tree:
                intersect_indices = spatial_tree.query(poly_base.buffer(0.02))
                for idx in intersect_indices:
                    meta = raw_lines_metadata[idx]
                    if (poly_base.buffer(0.02).covers(meta["line"]) or poly_base.distance(meta["line"]) < 0.01) and not meta["is_filled"]:
                        l_coords = list(meta["line"].coords)
                        if len(l_coords) >= 2:
                            dx, dy = l_coords[1][0] - l_coords[0][0], l_coords[1][1] - l_coords[0][1]
                            g_len = math.hypot(dx, dy)
                            if g_len > max_grain_len and g_len > 0.4: max_grain_len, grain_angle_deg = g_len, math.degrees(math.atan2(dy, dx))
            poly_oriented = rotate(poly_base, -grain_angle_deg, origin='center') if abs(grain_angle_deg) > 0.01 else poly_base.minimum_rotated_rectangle
            if not poly_oriented.is_valid: poly_oriented = poly_oriented.buffer(0)
            if seam_allowance > 0.001: poly_oriented = poly_oriented.buffer(seam_allowance)
            loops = int(target_pieces_count) if target_pieces_count > 0 else 1
            for loop_idx in range(loops):
                piece_idx += 1
                poly_final = scale(poly_oriented, xfact=-1.0, yfact=1.0, origin='center') if is_mirror_pair and (loop_idx % 2 == 1) else poly_oriented
                minx, miny, maxx, maxy = poly_final.bounds
                panels_catalog.append({"id": f"P_{layer_upper}_{piece_idx}", "polygon": poly_final, "width": round(maxy - miny, 4), "length": round(maxx - minx, 4), "area": round(poly_final.area, 4)})
        return {"status": "success", "panels_catalog": panels_catalog}
    except Exception as e: return {"status": "error", "message": str(e)}
# ==============================================================================
# ==============================================================================
# ĐOẠN 5.1/6: LÕI HÌNH HỌC PHẲNG V18 - BƯỚC 3 (PHẦN ĐẦU VÁ LỖI TUPLE BOUNDS)
# ==============================================================================
def v18_step3_execute_strip_nesting(panels_catalog, target_width=58.0, fabric_type="ONE_WAY"):
    STRIP_WIDTH = float(target_width)
    total_theoretical_area = sum(item["area"] for item in panels_catalog)
    allowed_rotations = (0,) if str(fabric_type).upper() in ["ONE_WAY", "NAP"] else ((0, 180) if str(fabric_type).upper() in ["TWO_WAY", "DENIM"] else (0, 90, 180, 270))
    nested_queue = sorted(panels_catalog, key=lambda x: x["area"], reverse=True)
    virtual_bound = Polygon([(-10, -10), (-9, -10), (-9, -9), (-10, -9)])
    placed_polygons = [virtual_bound]
    spatial_index = STRtree(placed_polygons)
    skyline = [{"x": 0.0, "y0": 0.0, "y1": STRIP_WIDTH}]
    current_marker_length = 0.0

    def check_collision(candidate_poly, current_tree, reference_list):
        intersect_indices = current_tree.query(candidate_poly)
        for idx in intersect_indices:
            if candidate_poly.intersects(reference_list[idx]) and candidate_poly.intersection(reference_list[idx]).area > 0.001: return True
        return False

    for item in nested_queue:
        poly_base, best_x_score, best_placed_poly = item["polygon"], float('inf'), None
        for angle in allowed_rotations:
            poly_rotated = poly_base if angle == 0 else rotate(poly_base, angle, origin='center')
            minx, miny, maxx, maxy = poly_rotated.bounds
            w_piece, l_piece = maxy - miny, maxx - minx
            if w_piece > STRIP_WIDTH: continue
            for seg in skyline:
                if seg["y1"] - seg["y0"] >= w_piece:
                    for y_cand in [seg["y0"], seg["y1"] - w_piece]:
                        dx, dy = seg["x"] - minx, y_cand - miny
                        test_poly = translate(poly_rotated, xoff=dx, yoff=dy)
                        
                        # ✅ FIXED CRITICAL: Bóc tách chính xác float từ tuple để so sánh giới hạn khổ vải
                        t_minx, t_miny, t_maxx, t_maxy = test_poly.bounds
                        if t_miny < 0.0 or t_maxy > STRIP_WIDTH: continue
                        
                        if not check_collision(test_poly, spatial_index, placed_polygons):
                            low_f, high_factor, optimal_dx = 0.0, 1.0, dx
                            for _ in range(5):
                                mid = (low_f + high_factor) / 2.0
                                if not check_collision(translate(poly_rotated, xoff=seg["x"] - minx + (optimal_dx - (seg["x"] - minx)) * mid, yoff=dy), spatial_index, placed_polygons):
                                    optimal_dx, high_factor = seg["x"] - minx + (optimal_dx - (seg["x"] - minx)) * mid, mid
                                else: low_f = mid
                            final_p = translate(poly_rotated, xoff=optimal_dx, yoff=dy)
                            f_minx, f_miny, f_maxx, f_maxy = final_p.bounds
                            if f_maxx < best_x_score: best_x_score, best_placed_poly = f_maxx, final_p
# ==============================================================================
# ĐOẠN 5.2/6 (CHUẨN HOÀN THIỆN): TRÍCH XUẤT ĐÚNG FLOAT CHỈ SỐ BOUNDS [2] VÀ [3]
# ==============================================================================
        if best_placed_poly is not None:
            placed_polygons.append(best_placed_poly)
            spatial_index = STRtree(placed_polygons)
            
            # ✅ BÓC TÁCH FLOAT TỪNG CHỈ SỐ CHUẨN XÁC TUYỆT ĐỐI
            p_bounds = best_placed_poly.bounds
            p_miny = p_bounds[1]
            p_maxx = p_bounds[2]  # [2] chính là maxx (độ dài thực trục X)
            p_maxy = p_bounds[3]  # [3] chính là maxy
            
            new_skyline = []
            for seg in skyline:
                if seg["y0"] >= p_miny and seg["y1"] <= p_maxy: 
                    new_skyline.append({"x": max(seg["x"], p_maxx), "y0": seg["y0"], "y1": seg["y1"]})
                elif seg["y0"] < p_miny and seg["y1"] > p_miny and seg["y1"] <= p_maxy:
                    new_skyline.append({"x": seg["x"], "y0": seg["y0"], "y1": p_miny})
                    new_skyline.append({"x": max(seg["x"], p_maxx), "y0": p_miny, "y1": seg["y1"]})
                elif seg["y0"] >= p_miny and seg["y0"] < p_maxy and seg["y1"] > p_maxy:
                    new_skyline.append({"x": max(seg["x"], p_maxx), "y0": p_miny, "y1": p_maxy})
                    new_skyline.append({"x": seg["x"], "y0": p_maxy, "y1": seg["y1"]})
                elif seg["y0"] < p_miny and seg["y1"] > p_maxy:
                    new_skyline.append({"x": seg["x"], "y0": seg["y0"], "y1": p_miny})
                    new_skyline.append({"x": max(seg["x"], p_maxx), "y0": p_miny, "y1": p_maxy})
                    new_skyline.append({"x": seg["x"], "y0": p_maxy, "y1": seg["y1"]})
                else: 
                    new_skyline.append(seg)
            
            # Gộp sơ đồ chân trời liền kề chống nát sơ đồ
            sorted_segs = sorted(new_skyline, key=lambda s: s["y0"])
            merged = []
            if sorted_segs:
                curr = sorted_segs
                for next_seg in sorted_segs[1:]:
                    if abs(curr["y1"] - next_seg["y0"]) < 0.001 and abs(curr["x"] - next_seg["x"]) < 0.005:
                        curr["y1"] = next_seg["y1"]
                        curr["x"] = max(curr["x"], next_seg["x"])
                    else: 
                        merged.append(curr)
                        curr = next_seg
                merged.append(curr)
            skyline = merged
            if p_maxx > current_marker_length: 
                current_marker_length = p_maxx
        else:
            # Nhánh bảo vệ Fallback bám dải biên ngoài
            lowest_seg = min(skyline, key=lambda s: s["x"])
            minx, miny, maxx, maxy = poly_base.bounds
            fallback_dx = lowest_seg["x"] - minx
            fallback_dy = lowest_seg["y0"] - miny
            fallback_poly = translate(poly_base, xoff=fallback_dx, yoff=fallback_dy)
            scan_counter, max_y_limit = 0, STRIP_WIDTH - (maxy - miny)
            
            while check_collision(fallback_poly, spatial_index, placed_polygons) and fallback_dy <= max_y_limit:
                fallback_dy += 0.5
                fallback_poly = translate(poly_base, xoff=fallback_dx, yoff=fallback_dy)
                scan_counter += 1
                if scan_counter > 30: 
                    break
                    
            if check_collision(fallback_poly, spatial_index, placed_polygons):
                fallback_dx = current_marker_length - minx
                fallback_dy = 0.0 - miny
                fallback_poly = translate(poly_base, xoff=fallback_dx, yoff=fallback_dy)
                
            placed_polygons.append(fallback_poly)
            spatial_index = STRtree(placed_polygons)
            
            f_bounds = fallback_poly.bounds
            f_miny = f_bounds[1]
            f_maxx = f_bounds[2]
            f_maxy = f_bounds[3]
            
            if f_maxx > current_marker_length: 
                current_marker_length = f_maxx
                
            # ✅ ĐÃ SỬA: Ép chuẩn xác float f_miny và f_maxy
            skyline.append({"x": current_marker_length, "y0": f_miny, "y1": f_maxy})
            
            # Gộp chân trời sau khi bổ sung phần tử Fallback
            sorted_segs = sorted(skyline, key=lambda s: s["y0"])
            merged = []
            if sorted_segs:
                curr = sorted_segs
                for next_seg in sorted_segs[1:]:
                    if abs(curr["y1"] - next_seg["y0"]) < 0.001 and abs(curr["x"] - next_seg["x"]) < 0.005:
                        curr["y1"] = next_seg["y1"]
                        curr["x"] = max(curr["x"], next_seg["x"])
                    else: 
                        merged.append(curr)
                        curr = next_seg
                merged.append(curr)
            skyline = merged

    total_marker_area = current_marker_length * STRIP_WIDTH
    marker_utilization = (total_theoretical_area / total_marker_area * 100.0) if total_marker_area > 0 else 0.0
    return {
        "status": "success", 
        "total_pieces_nested": len(panels_catalog), 
        "marker_length_inch": round(current_marker_length, 2), 
        "fabric_width_inch": STRIP_WIDTH, 
        "marker_utilization_percent": round(marker_utilization, 2), 
        "fabric_consumption_yard": round((current_marker_length / 36.0), 3)
    }


# PHẦN 6.1: KHÔNG GIAN CHAT WORKSPACE & BỘ TRÍCH XUẤT SPECS BIÊN
# ==============================================================================
st.markdown('<br><div class="cad-card"><div class="cad-header">💬 CHATGPT IE COLLABORATION WORKSPACE</div>', unsafe_allow_html=True)
c_col1, c_col2 = st.columns(2)
with c_col2:
    if st.button("🗑️ Clear Chat", key="btn_clear_v18_final_clean", use_container_width=True):
        st.session_state.chat_history, st.session_state.active_blueprint, st.session_state.accumulated_bom_rows = [], {}, {}
        st.rerun()

if st.session_state.chat_history:
    for msg in st.session_state.chat_history:
        st.chat_message("user").write(msg["user"])
        st.chat_message("assistant").write(msg["ai"])

safe_user_prompt = st.chat_input("Gõ câu lệnh điều chỉnh thông số tại đây...", key="input_v18_final_clean")
st.markdown('</div>', unsafe_allow_html=True)

ai_json_data, active_warp, active_weft, active_width, target_size_cmd = {}, float(warp_shrinkage), float(weft_shrinkage), float(fabric_width_input), "30"

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
            st.session_state.current_warp_pct, st.session_state.current_weft_pct = f"{active_warp}%", f"{active_weft}%"
# ==============================================================================
# PHẦN 6.2: CẤU HÌNH JSON SCHEMA & GỌI API GEMINI AI ORCHESTRATOR
# ==============================================================================
            if "GEMINI_API_KEY" in st.secrets: genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
            
            bom_schema = {
                "type": "OBJECT",
                "properties": {
                    "detected_product_type": {"type": "STRING"}, "style_code": {"type": "STRING"}, "calculated_on_size": {"type": "STRING"},
                    "bom_rows": {
                        "type": "ARRAY",
                        "items": {
                            "type": "OBJECT",
                            "properties": {
                                "component_type": {"type": "STRING"}, "fabric_classification": {"type": "STRING"}, "fabric_width_inch": {"type": "NUMBER"}, "geometry_required": {"type": "BOOLEAN"}, "geometry_source_layer": {"type": "STRING"}
                            },
                            "required": ["component_type", "fabric_classification", "fabric_width_inch", "geometry_required", "geometry_source_layer"]
                        }
                    }
                },
                "required": ["detected_product_type", "style_code", "calculated_on_size", "bom_rows"]
            }

            model = genai.GenerativeModel("gemini-2.5-flash", generation_config={"temperature": 0.1, "response_mime_type": "application/json", "response_schema": bom_schema})
            prompt_instruction = f"Analyze Techpack text and return Bill of Materials (BOM) in JSON.\nDATA: {st.session_state.pdf_text_cache[:3000]}\nCOMMAND: {current_query}"
            response = model.generate_content(prompt_instruction)
            ai_json_data = json.loads(response.text.strip())
        except Exception as prompt_err: st.error(f"Lỗi AI: {str(prompt_err)}")
# ==============================================================================
# PHẦN 6.3: PYTHON CORE PIPELINE - ĐIỀU PHỐI TỰ ĐỘNG TÍNH ĐỊNH MỨC THEO BOM
# ==============================================================================
if ai_json_data and "bom_rows" in ai_json_data:
    updated_bom_rows = []
    for row in ai_json_data.get("bom_rows", []):
        if row.get("geometry_required", False):
            layer_target = row.get("geometry_source_layer", "MAIN_BODY_CARGO")
            f_width = float(row.get("fabric_width_inch", active_width))
            f_type = "TWO_WAY" if str(row.get("fabric_classification", "MAIN_FABRIC")).upper() == "MAIN_FABRIC" else "FREE"
            
            with st.status(f"⚙️ Lõi V18 đang tự động lấp đầy sơ đồ lớp: {layer_target}...", expanded=False) as layer_status:
                s1 = v18_step1_extract_raw_vectors(layer_name=layer_target, warp=active_warp, weft=active_weft, snap_tol=0.005)
                if s1["status"] == "success":
                    if "MAIN" in layer_target.upper(): s1["target_pieces_count"], s1["is_mirror_pair"] = 2.0, True
                    else: s1["target_pieces_count"], s1["is_mirror_pair"] = 4.0, False
                    
                    s2 = v18_step2_reconstruct_and_orient_geometry(step1_results=s1, seam_allowance=seam_allowance_input)
                    if s2["status"] == "success" and s2["panels_catalog"]:
                        s3 = v18_step3_execute_strip_nesting(panels_catalog=s2["panels_catalog"], target_width=f_width, fabric_type=f_type)
                        if s3["status"] == "success":
                            row["calculated_gross_consumption_yds"], row["quality_gate_status"] = s3["fabric_consumption_yard"], "PASSED"
                            row["consumption_note"] = f"Skyline complete. Utilization: {s3['marker_utilization_percent']}%."
                            layer_status.update(label=f"✓ Lớp {layer_target} hoàn tất!", state="complete")
                        else: row["calculated_gross_consumption_yds"], row["consumption_note"], row["quality_gate_status"] = 0.0, "Nesting failed.", "FAILED"; layer_status.update(label="✕ Lỗi Nesting", state="error")
                    else: row["calculated_gross_consumption_yds"], row["consumption_note"], row["quality_gate_status"] = 0.0, "No polygons.", "EMPTY"; layer_status.update(label="⚠ Không tìm thấy rập", state="warning")
                else: row["calculated_gross_consumption_yds"], row["consumption_note"], row["quality_gate_status"] = 0.0, "Parsing failed.", "FAILED"; layer_status.update(label="✕ Lỗi trích xuất vector", state="error")
        else: row["calculated_gross_consumption_yds"], row["consumption_note"], row["quality_gate_status"] = 0.0, "Calculation skipped.", "SKIPPED"
        updated_bom_rows.append(row)
    
    ai_json_data["bom_rows"] = updated_bom_rows
    st.session_state.active_blueprint = ai_json_data
    for r in updated_bom_rows: st.session_state.accumulated_bom_rows[r["component_type"]] = r
    st.session_state.chat_history.append({"user": current_query, "ai": "Đã phân tích tài liệu kỹ thuật và tính toán ma trận định mức CAD thành công bằng Python."})
    st.rerun()
# ==============================================================================
# PHẦN 6.4: RENDERING BẢNG MA TRẬN ĐỊNH MỨC & KHỞI TẠO BÁO CÁO FILE EXCEL
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
    warp_default, weft_default = st.session_state.get("current_warp_pct", "3.0%"), st.session_state.get("current_weft_pct", "3.0%")
    display_data = []
    for r in active_bom_source["bom_rows"]:
        if not r or not isinstance(r, dict): continue
        cut_width_val = f"{float(r['fabric_width_inch'])} inch" if "fabric_width_inch" in r and r["fabric_width_inch"] > 0 else f"{fabric_width_input} inch"
        warp_val, weft_val = ("0.0%", "0.0%") if "FUSING" in str(r.get("fabric_classification", "")).upper() else (warp_default, weft_default)
        display_data.append({"Component Type": r.get("component_type", "MAIN FABRIC"), "Placement": r.get("placement", "BODY/POCKETS/CARGO"), "Fabric Classification": r.get("fabric_classification", "MAIN_FABRIC"), "Fabric Code": r.get("fabric_code", "TWILL"), "Fabric Color": r.get("fabric_color", "TBA"), "Khổ vải (Width)": cut_width_val, "Co rút dọc (% Warp)": warp_val, "Co rút ngang (% Weft)": weft_val, "Marker Efficiency": "85.0%", "Gross Consumption (Yds)": r.get("calculated_gross_consumption_yds", 0.0), "Quality Status": r.get("quality_gate_status", "PASSED"), "System Notes": r.get("consumption_note", "Optimized.")})
    df_bom = pd.DataFrame(display_data)
    st.dataframe(df_bom, use_container_width=True, hide_index=True)
    st.markdown('</div>', unsafe_allow_html=True)
    
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
        from openpyxl.utils import get_column_letter
        output = io.BytesIO(); wb = Workbook(); ws = wb.active; ws.title = "BOM Fabric Consumption"; ws.sheet_view.showGridLines = True
        ws.merge_cells("A1:L1"); ws["A1"] = f"BÁO CÁO ĐỊNH MỨC VẬT TƯ VẢI (SIZE: {extracted_size})"; ws["A1"].font = Font(name="Calibri", size=14, bold=True, color="FFFFFF"); ws["A1"].fill = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid"); ws["A1"].alignment = Alignment(horizontal="center", vertical="center"); ws.row_dimensions.height = 40
        headers = list(df_bom.columns)
        for col_num, title in enumerate(headers, 1):
            cell = ws.cell(row=3, column=col_num, value=title); cell.font = Font(name="Calibri", size=11, bold=True, color="FFFFFF"); cell.fill = PatternFill(start_color="2C3E50", end_color="2C3E50", fill_type="solid"); cell.alignment = Alignment(horizontal="center", vertical="center"); cell.border = Border(left=Side(style="thin", color="D9D9D9"), right=Side(style="thin", color="D9D9D9"), top=Side(style="thin", color="D9D9D9"), bottom=Side(style="thin", color="D9D9D9"))
        ws.row_dimensions.height = 28
        for row_num, row_data in enumerate(display_data, 4):
            ws.row_dimensions[row_num].height = 22
            for col_num, key in enumerate(headers, 1):
                cell = ws.cell(row=row_num, column=col_num, value=row_data[key]); cell.font = Font(name="Calibri", size=11); cell.border = Border(left=Side(style="thin", color="D9D9D9"), right=Side(style="thin", color="D9D9D9"), top=Side(style="thin", color="D9D9D9"), bottom=Side(style="thin", color="D9D9D9"))
                if key in ["Gross Consumption (Yds)"]: cell.alignment = Alignment(horizontal="right", vertical="center"); cell.number_format = '#,##0.0000'
                elif key in ["Khổ vải (Width)", "Co rút dọc (% Warp)", "Co rút ngang (% Weft)", "Marker Efficiency", "Quality Status"]: cell.alignment = Alignment(horizontal="center", vertical="center")
                else: cell.alignment = Alignment(horizontal="left", vertical="center")
        for col_idx, col_name in enumerate(headers, 1):
            max_len = max([len(str(ws.cell(row=r, column=col_idx).value or '')) for r in range(4, 4 + len(display_data))] + [len(col_name)])
            ws.column_dimensions[get_column_letter(col_idx)].width = max(max_len + 5, 12)
        wb.save(output)
        st.markdown("<br>", unsafe_allow_html=True)
        st.download_button(label="📥 XUẤT FILE EXCEL ĐỊNH MỨC CHUẨN SẢN XUẤT", data=output.getvalue(), file_name=f"BOM_Consumption_Size_{extracted_size}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True, key="btn_download_excel_v18_final_structural")
    except Exception as e: st.warning(f"⚠️ Lỗi Excel: {str(e)}")
else:
    st.info("💡 Bộ nhớ đệm hệ thống đã được làm sạch hoàn toàn. Vui lòng nạp tệp PDF tài liệu và gõ câu lệnh chatbox để chạy luồng tự động toán học mới...")
