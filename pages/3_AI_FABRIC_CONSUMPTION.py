
# =====================================================================
# HỆ THỐNG TOÁN HỌC V18 GERBER INDUSTRIAL MARKER ENGINE
# ĐOẠN 7 - PHẦN 1/6: KHỞI TẠO KHUNG WORKSPACE CHAT & CƠ CHẾ RESET (ĐÃ SỬA LỖI ĐƠN VỊ ĐM)
# =====================================================================

# --- PHẦN 1: KHUNG HỘI THOẠI & LỊCH SỬ WORKSPACE (UI CHAT) ---
st.markdown('<br><div class="cad-card"><div class="cad-header">💬 CHATGPT IE COLLABORATION WORKSPACE</div>', unsafe_allow_html=True)

if "chat_history" not in st.session_state: st.session_state.chat_history = []
if "pdf_page_one_image" not in st.session_state: st.session_state.pdf_page_one_image = None
if "accumulated_bom_rows" not in st.session_state: st.session_state.accumulated_bom_rows = {}
if "current_warp_pct" not in st.session_state: st.session_state.current_warp_pct = "3.0%"
if "current_weft_pct" not in st.session_state: st.session_state.current_weft_pct = "3.0%"
if "active_blueprint" not in st.session_state: st.session_state.active_blueprint = {}

c_col1, c_col2 = st.columns(2)
with c_col2:
    if st.button("🗑️ Clear Chat", key="btn_clear_chat_v18_final", use_container_width=True):
        st.session_state.chat_history = []
        st.session_state.active_blueprint = {}
        st.session_state.accumulated_bom_rows = {}
        st.session_state.current_warp_pct = "3.0%"
        st.session_state.current_weft_pct = "3.0%"
        st.toast("🧹 Đã dọn sạch lịch sử hội thoại và ma trận định mức!", icon="🗑️")
        st.rerun()

if st.session_state.chat_history:
    for msg in st.session_state.chat_history:
        st.chat_message("user").write(msg["user"])
        st.chat_message("assistant").write(msg["ai"])

safe_user_prompt = st.chat_input("Gõ câu lệnh điều chỉnh thông số tại đây...", key="main_chat_input_v18_final")
st.markdown('</div>', unsafe_allow_html=True)

# --- PHẦN 2: CORE AI ENGINE ĐIỀU PHỐI VÀ TRÍCH XUẤT THÔNG SỐ SPECS ---
if st.session_state.get("pdf_bytes") is not None and safe_user_prompt:
    current_query = str(safe_user_prompt).strip()
    
    with st.spinner("🧠 AI đang phân tách cấu trúc vật tư, song song kích hoạt Lõi Hình Học V18..."):
        try:
            import google.generativeai as genai
            import json, copy, traceback, re
            import fitz 
            
            if st.session_state.pdf_page_one_image is None:
                doc_recovery = fitz.open(stream=st.session_state.pdf_bytes, filetype="pdf")
                st.session_state.pdf_page_one_image = doc_recovery.load_page(0).get_pixmap(dpi=150).tobytes("png")
            
            if "GEMINI_API_KEY" in st.secrets: 
                genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
                
            model = genai.GenerativeModel("gemini-2.5-flash", generation_config={"temperature": 0.0})
            chat_lower = current_query.lower()
            
            match_size = re.search(r'\b(?:size|sz|cỡ|cơ)\s*[:\-=\s]*([\w\d]+)\b', chat_lower)
            target_size_cmd = str(match_size.group(1)).upper().strip() if match_size else "30"
            
            try:
                size_num_check = float(re.sub(r'[^\d\.]', '', target_size_cmd))
                if size_num_check < 20.0 or size_num_check > 50.0:
                    target_size_cmd = "30"
            except:
                pass

            match_w = re.search(r'(?:khổ|kho|width|cutwidth)\s*[:\-=\s]*([\d\.]+)', chat_lower)
            active_width = float(match_w.group(1)) if match_w else 58.0
            
            active_warp, active_weft = 3.0, 3.0
            match_warp = re.search(r'(?:dọc|doc|warp)\s*[:\-=\s]*([\d\.]+)', chat_lower)
            match_weft = re.search(r'(?:ngang|weft)\s*[:\-=\s]*([\d\.]+)', chat_lower)
            
            if match_warp: active_warp = float(match_warp.group(1))
            if match_weft: active_weft = float(match_weft.group(1))
            if not match_warp or not match_weft:
                m_sh = re.search(r'(?:co\s*rút|co\s*rut|co|shrinkage)\s*[:\-=\s]*([\d\.]+)\s*(?:-|–|x|ngang|\s+)\s*([\d\.]+)', chat_lower)
                if m_sh:
                    active_warp, active_weft = float(m_sh.group(1)), float(m_sh.group(2))

            st.session_state.current_warp_pct = f"{active_warp}%"
            st.session_state.current_weft_pct = f"{active_weft}%"

            techpack_text = st.session_state.get("pdf_text_cache", "Casual Twill Cargo Pants with multiple pockets.")

def v18_step2_reconstruct_and_orient_geometry(step1_results, seam_allowance=0.0):
    """
    LÕI INDUSTRIAL V18 - ĐOẠN 2 (Phần A2):
    Xây dựng Polygon đa vòng (Holes/Islands), lọc sớ vải thông minh qua Metadata (độ dày/chiều dài),
    khử góc nghiêng sai lệch và trích xuất thông số hình học (Length/Width) chuẩn xác.
    """
    import math
    from shapely.geometry import Polygon, MultiPolygon, LineString
    from shapely.ops import unary_union, polygonize
    from shapely.affinity import rotate, scale
    from shapely.strtree import STRtree
    import numpy as np
    import streamlit as st

    if not step1_results or step1_results.get("status") != "success":
        return {"status": "error", "message": "Dữ liệu đầu vào từ Đoạn 1 không hợp lệ hoặc bị gián đoạn."}

    all_contours = step1_results["all_contours"]
    raw_lines_metadata = step1_results["raw_lines_metadata"]
    page_area_sq_in = step1_results["page_area_sq_in"]
    target_pieces_count = step1_results["target_pieces_count"]
    is_mirror_pair = step1_results["is_mirror_pair"]
    layer_upper = step1_results["layer_upper"]

    # Phân ngưỡng diện tích thực nghiệm nhằm triệt tiêu các vết xước nhỏ hay khung bao viền PDF quảng cáo
    min_area_thresh = max(1.5, page_area_sq_in * 0.002)
    max_area_thresh = min(2500.0, page_area_sq_in * 0.98)
    panels_catalog = []

    try:
        # 6, 9, 10, 11. POLYGONIZE CHUYÊN SÂU: Gộp tổ hợp đường và khâu các mạch hở cục bộ
        merged_lines = unary_union(all_contours)
        polygons_built = list(polygonize(merged_lines))
        
        if not polygons_built:
            # Cơ chế dự phòng khẩn cấp nếu chuỗi vector gốc hở góc quá lớn (Dùng đệm buffer siêu vi phân)
            buffered_contours = [line.buffer(0.001) for line in all_contours]
            union_poly = unary_union(buffered_contours)
            if isinstance(union_poly, Polygon): 
                polygons_built = [union_poly]
            elif isinstance(union_poly, MultiPolygon): 
                polygons_built = list(union_poly.geoms)

        # Sắp xếp các hình đa giác kín giảm dần theo diện tích để đảm bảo Hole Detection lồng lỗ chạy chính xác tuyệt đối
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
            
            # 10 & 11. HOLE & ISLAND DETECTION: Quét tìm tất cả các chi tiết đục lỗ khuy, túi mổ nằm trọn bên trong rập chính
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

        # Bộ lọc cách ly tầng rập chính (Main Layer) chống bóc nhầm khung bao phôi trang PDF gốc
        final_valid_polys = []
        for p in validated_master_pieces:
            if "MAIN" not in layer_upper and p.area > (page_area_sq_in * 0.35):
                continue
            final_valid_polys.append(p)

        # Tạo cây chỉ mục không gian cố định chứa toàn bộ các dải nét có Metadata từ Đoạn 1
        all_lines_flat = [item["line"] for item in raw_lines_metadata]
        spatial_tree = STRtree(all_lines_flat) if all_lines_flat else None

        piece_idx = 0
        for poly in final_valid_polys:
            # 5. CLONE OBJECT GỐC: Tách biệt mảng tọa độ trên bộ nhớ RAM, tránh xung đột ghi đè biến con
            poly_base = Polygon(shell=poly.exterior.coords, holes=[h.coords for h in poly.interiors])
            if not poly_base.is_valid: 
                poly_base = poly_base.buffer(0)

            # 4 & 7. LỌC KHỬ NHIỄU CANH SỢI (GRAINLINE): Quét dung sai khoảng cách và phân loại Metadata đồ họa
            grain_angle_deg = 0.0
            max_grain_len = 0.0
            
            if spatial_tree:
                intersect_indices = spatial_tree.query(poly_base.buffer(0.02))
                for idx in intersect_indices:
                    meta = raw_lines_metadata[idx]
                    line_geom = meta["line"]
                    
                    # Định luật Gerber: Canh sợi thật phải nằm sâu trong rập, không có màu Fill nền và nét mảnh đặc trưng biệt lập
                    if (poly_base.buffer(0.02).covers(line_geom) or poly_base.distance(line_geom) < 0.01) and not meta["is_filled"]:
                        l_coords = list(line_geom.coords)
                        if len(l_coords) >= 2:
                            dx = l_coords[1][0] - l_coords[0][0]
                            dy = l_coords[1][1] - l_coords[0][1]
                            g_len = math.hypot(dx, dy)
                            
                            # Tiêu chuẩn lọc nâng cao: Bỏ qua hoàn toàn nốt bấm vát biên (Notch < 0.4 inch) hoặc các đường chỉ may lặt vặt
                            if g_len > max_grain_len and g_len > 0.4:
                                max_grain_len = g_len
                                grain_angle_deg = math.degrees(math.atan2(dy, dx))

            # 2 & 13. ORIENTATION NORMALIZE: Đập tan góc nghiêng sai lệch, đưa sớ vải về trạng thái nằm ngang tuyệt đối
            if abs(grain_angle_deg) > 0.01:
                poly_oriented = rotate(poly_base, -grain_angle_deg, origin='center')
            else:
                # Phác đồ dự phòng toán học CAD: Ép về HCN xoay tối thiểu (OBB) để tìm kiếm trục dài nhất làm chuẩn hướng sớ
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

            # 8. AREA OFFSET (SEAM ALLOWANCE): Đưa khoảng bù đường may định mức kỹ thuật vào diện tích hình học
            if seam_allowance > 0.001:
                poly_oriented_for_area = poly_oriented.buffer(seam_allowance)
                if not poly_oriented_for_area.is_valid: 
                    poly_oriented_for_area = poly_oriented_for_area.buffer(0)
            else:
                poly_oriented_for_area = poly_oriented

            # Phân tách vòng lặp nhân bản chi tiết theo cấu trúc dữ liệu BOM (Loops) + Xử lý cặp đối xứng kính (Mirror Pair)
            loops = int(target_pieces_count) if target_pieces_count > 0 else 1
            for loop_idx in range(loops):
                piece_idx += 1
                if is_mirror_pair and (loop_idx % 2 == 1):
                    # Lật gương đối xứng hoàn hảo qua trục X định vị chuẩn tâm hình học chi tiết
                    poly_final = scale(poly_oriented_for_area, xfact=-1.0, yfact=1.0, origin='center')
                else:
                    poly_final = poly_oriented_for_area
                    
                if not poly_final.is_valid: 
                    poly_final = poly_final.buffer(0)

                # 1 & 2. TÍNH BỐ TRÍ KÍCH THƯỚC: Do chi tiết đã xoay song song trục chuẩn khổ vải, bounds lúc này là kích thước thực 100%
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
        st.error(f"Lỗi hệ thống nghiêm trọng tại Đoạn 2 (Tái tạo hình học đa tầng): {str(e)}")
        return {"status": "error", "message": str(e)}
def v18_step3_execute_strip_nesting(panels_catalog, target_width=58.0, fabric_type="ONE_WAY"):
    """
    LÕI TOÁN HỌC V18 GERBER INDUSTRIAL - ĐOẠN 3A (Phần 1/2):
    Khởi tạo hệ thống Nesting Skyline thực thụ, cấu hình góc xoay tự động theo 
    loại vải từ BOM, xây dựng thuật toán gộp mảnh chân trời chống phân mảnh sơ đồ.
    [VÁ LỖI CƠ SỞ]: Điều chỉnh STRtree.query() truy xuất qua Index để tương thích hoàn hảo Shapely 2.0+.
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

    # Chiến lược tham lam công nghiệp: Sắp xếp chi tiết rập giảm dần theo diện tích
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
            if abs(curr["y1"] - next_seg["y0"]) < 0.001 and abs(curr["x"] - next_seg["x"]) < 0.005:
                curr["y1"] = next_seg["y1"]
                curr["x"] = max(curr["x"], next_seg["x"])
            else:
                merged.append(curr)
                curr = next_seg
        merged.append(curr)
        return merged
    # ==============================================================================
    # PHẦN RUỘT VÒNG LẶP HẠT NHÂN QUÉT ĐA ĐIỂM SKYLINE & VECTOR SLIDING (ĐÃ SỬA LỖI TRUY XUẤT)
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
                    y_candidates = [seg["y0"], seg["y1"] - w_piece, seg["y0"] + (seg_w - w_piece) / 2.0]
                    
                    for y_cand in y_candidates:
                        x_cand = seg["x"]
                        dx = x_cand - minx
                        dy = y_cand - miny
                        test_poly = translate(poly_rotated, xoff=dx, yoff=dy)
                        
                        _, t_miny, _, t_maxy = test_poly.bounds
                        if t_miny < 0.0 or t_maxy > STRIP_WIDTH:
                            continue
                            
                        # Gọi hàm check_collision truyền thêm mảng tham chiếu đặt đặt rập
                        if not check_collision(test_poly, spatial_index, placed_polygons):
                            low_factor = 0.0
                            high_factor = 1.0
                            optimal_dx = dx
                            
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
                            
                            if final_maxx < best_x_score:
                                best_x_score = final_maxx
                                best_placed_poly = final_test_poly

        # THỰC THI NEO ĐẶT CHI TIẾT VÀ TÁI CẤU TRÚC PHÂN ĐOẠN CHÂN TRỜI ĐỘNG
        if best_placed_poly is not None:
            placed_polygons.append(best_placed_poly)
            
            # Tái tạo cây STRtree trên danh sách mảng phẳng đã cập nhật phần tử mới đặt
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
                    new_skyline.append({"x": seg["x"], "y0": p_maxy, "y1": seg["y1"]})
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
            
            f_minx, f_miny, f_maxx, f_maxy = fallback_poly.bounds
            if f_maxx > current_marker_length:
                current_marker_length = f_maxx
                
            skyline.append({"x": current_marker_length, "y0": f_miny, "y1": f_maxy})
            skyline = _merge_skyline(skyline)

    # Tính toán hiệu suất định mức thực tế sử dụng sơ đồ (Marker Utilization %) trừ đi phần đa giác mồi ảo [0]
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

# ==============================================================================
# HỆ THỐNG TOÁN HỌC V18 GERBER INDUSTRIAL MARKER ENGINE
# ĐOẠN 4: GIAO DIỆN NGƯỜI DÙNG STREAMLIT & ĐIỀU PHỐI LUỒNG TOÀN TRÌNH (PIPELINE UI)
# ==============================================================================

st.set_page_config(page_title="Gerber V18 Engine", layout="wide")

st.title("🎛️ Hệ Thống Tính Định Mức Sơ Đồ Gerber V18")
st.caption("Lõi toán học nâng cao tích hợp Adaptive Bezier, Holes-Islands Extraction và Skyline Packing Engine")

# 📊 THANH CẤU HÌNH THÔNG SỐ CƠ SỞ (SIDEBAR CONTROLS)
st.sidebar.header("🛠️ Cấu Hình Tham Số Kỹ Thuật")

fabric_width_input = st.sidebar.number_input(
    "Khổ rộng vải hữu dụng (Inch):", 
    min_value=30.0, max_value=120.0, value=58.0, step=0.5,
    help="Chiều rộng thực tế của khổ vải sau khi đã trừ biên dập."
)

fabric_type_select = st.sidebar.selectbox(
    "Đặc tính hướng sớ vải (BOM Material Type):",
    options=["ONE_WAY", "TWO_WAY", "FREE"],
    index=1,
    help="ONE_WAY: Vải tuyết/sọc một chiều (0°). TWO_WAY: Xoay dọc đối xứng (0°/180°). FREE: Phụ liệu xoay tự do 4 hướng."
)

seam_allowance_input = st.sidebar.slider(
    "Hao hụt đường may - Seam Allowance (Inch):",
    min_value=0.0, max_value=1.5, value=0.25, step=0.05,
    help="Khoảng offset bù đường may kỹ thuật ra biên ngoài của rập."
)

st.sidebar.markdown("---")
st.sidebar.subheader("📈 Hệ Số Co Rút Vật Liệu (%)")
warp_shrinkage = st.sidebar.slider("Độ co rút sớ dọc (Warp %):", min_value=0.0, max_value=15.0, value=3.0, step=0.1)
weft_shrinkage = st.sidebar.slider("Độ co rút sớ ngang (Weft %):", min_value=0.0, max_value=15.0, value=3.0, step=0.1)

# 📂 KHỐI TẢI TỆP DỮ LIỆU ĐẦU VÀO
uploaded_file = st.file_uploader(
    "Tải lên tệp PDF Gerber Vector Nguyên Bản:", 
    type=["pdf"],
    help="Tệp PDF phải chứa cấu trúc vector hình học giải tích (không sử dụng PDF dạng scan ảnh)."
)

if uploaded_file is not None:
    # Nạp dữ liệu nhị phân vào bộ nhớ đệm Session State theo đúng thiết kế đồng bộ của Đoạn 1
    st.session_state.pdf_bytes = uploaded_file.read()
    
    st.markdown("---")
    st.subheader("⚙️ Tiến Trình Thực Thi Khối Toán Học V18")
    
    # Kích hoạt bảng điều phối Pipeline 3 bước liên kết liên tục
    with st.status("Đang chạy lõi xử lý Gerber V18...", expanded=True) as status_box:
        
        # 🔄 BƯỚC 1: Trích xuất hình học thô & Chuẩn hóa hệ tọa độ CAD Y-Flip
        st.write("🔹 [Bước 1/3] Đang phân tích PDF, nội suy Bezier thích ứng và lật trục Y sang tọa độ CAD...")
        step1_res = v18_step1_extract_raw_vectors(
            layer_name="MAIN", 
            warp=warp_shrinkage, 
            weft=weft_shrinkage,
            snap_tol=0.005
        )
        
        if step1_res["status"] == "success":
            # 🔄 BƯỚC 2: Tái cấu trúc đa giác lồng nhau (Holes/Islands) & Xoay thẳng thớ sớ vải
            st.write("🔹 [Bước 2/3] Đang khâu mạch hở, bóc tách cấu trúc đa tầng (Holes/Islands) và khử góc nghiêng sớ...")
            step2_res = v18_step2_reconstruct_and_orient_geometry(
                step1_results=step1_res, 
                seam_allowance=seam_allowance_input
            )
            
            if step2_res["status"] == "success":
                catalog = step2_res["panels_catalog"]
                
                # 🔄 BƯỚC 3: Engine Skyline thực thụ xếp sơ đồ đa hướng & Xuất báo cáo định mức
                st.write("🔹 [Bước 3/3] Đang chạy lõi tối ưu Skyline thực, trượt đa hướng mô phỏng NFP và nén sơ đồ kịch tả ngạn...")
                final_report = v18_step3_execute_strip_nesting(
                    panels_catalog=catalog, 
                    target_width=fabric_width_input, 
                    fabric_type=fabric_type_select
                )
                
                if final_report["status"] == "success":
                    status_box.update(label="Xử lý toàn trình hoàn tất thành công!", state="complete", expanded=False)
                    
                    # 📈 KHỐI HIỂN THỊ KẾT QUẢ ĐỊNH MỨC VÀ HIỆU SUẤT (MARKER KPI REPORT)
                    st.markdown("### 📊 Báo Cáo Định Mức Tiêu Hao Sơ Đồ Thực Tế")
                    
                    # Thiết lập layout hiển thị chỉ số Metric
                    m_col1, m_col2, m_col3 = st.columns(3)
                    
                    m_col1.metric(
                        label="🎯 Hiệu Suất Sơ Đồ (Marker Utilization)", 
                        value=f"{final_report['marker_utilization_percent']}%",
                        help="Tỷ lệ diện tích rập hữu ích chiếm chỗ trên tổng diện tích khổ vải sơ đồ."
                    )
                    m_col2.metric(
                        label="📏 Chiều Dài Sơ Đồ Thực Thực Tế", 
                        value=f"{final_report['marker_length_inch']} Inch",
                        help="Tổng chiều dài sơ đồ sau khi nén chặt toàn bộ chi tiết rập về bên trái."
                    )
                    m_col3.metric(
                        label="✂️ Định Mức Tiêu Hao Vải (Consumption)", 
                        value=f"{final_report['fabric_consumption_yard']} Yard",
                        help="Tổng số mét vải tiêu hao quy đổi sang đơn vị Yard ngành may."
                    )
                    
                    # Bảng dữ liệu thống kê cấu trúc chi tiết rập đã bóc tách
                    st.markdown("#### 📦 Chi Tiết Danh Sách Rập Đã Trích Xuất")
                    st.info(f"Hệ thống đã nhận dạng thành công tổng cộng **{final_report['total_pieces_nested']} chi tiết rập** từ tệp bản vẽ.")
                    
                    # Trích xuất dữ liệu bảng thô để người dùng theo dõi diện tích hình học
                    table_data = []
                    for item in catalog:
                        table_data.append({
                            "Mã Chi Tiết": item["id"],
                            "Chiều Dài (Inch)": item["length"],
                            "Chiều Rộng (Inch)": item["width"],
                            "Diện Tích Thực (Sq In)": item["area"]
                        })
                    st.dataframe(table_data, use_container_width=True)
                    
                else:
                    status_box.update(label="Thất bại tại Bước 3 (Nesting Sơ đồ)", state="error")
            else:
                status_box.update(label="Thất bại tại Bước 2 (Dựng Đa giác hình học)", state="error")
        else:
            status_box.update(label="Thất bại tại Bước 1 (Trích xuất Vector PDF)", state="error")
else:
    st.warning("👋 Vui lòng tải lên tệp PDF Gerber Vector ở trên để hệ thống bắt đầu thực thi lõi phân tích toán học.")





# =====================================================================
# HỆ THỐNG TOÁN HỌC V18 GERBER INDUSTRIAL MARKER ENGINE
# ĐOẠN 7 - PHẦN 1/6: KHỞI TẠO KHUNG WORKSPACE CHAT & CƠ CHẾ RESET (FIXED COLUMNS)
# =====================================================================

# --- PHẦN 1: KHUNG HỘI THOẠI & LỊCH SỬ WORKSPACE (UI CHAT) ---
st.markdown('<br><div class="cad-card"><div class="cad-header">💬 CHATGPT IE COLLABORATION WORKSPACE</div>', unsafe_allow_html=True)

# Khởi tạo đồng bộ toàn bộ các tầng bộ nhớ đệm Session State
if "chat_history" not in st.session_state: st.session_state.chat_history = []
if "pdf_page_one_image" not in st.session_state: st.session_state.pdf_page_one_image = None
if "accumulated_bom_rows" not in st.session_state: st.session_state.accumulated_bom_rows = {}
if "current_warp_pct" not in st.session_state: st.session_state.current_warp_pct = "3.0%"
if "current_weft_pct" not in st.session_state: st.session_state.current_weft_pct = "3.0%"
if "active_blueprint" not in st.session_state: st.session_state.active_blueprint = {}

# ✅ SỬA LỖI CHIA CỘT: Truyền tham số số lượng cột [5, 1] để đẩy nút bấm thu gọn kịch về góc phải màn hình
c_col1, c_col2 = st.columns([5, 1])
with c_col2:
    if st.button("🗑️ Clear Chat", key="btn_clear_chat_v18_final", use_container_width=True):
        st.session_state.chat_history = []
        st.session_state.active_blueprint = {}
        st.session_state.accumulated_bom_rows = {}
        st.session_state.current_warp_pct = "3.0%"
        st.session_state.current_weft_pct = "3.0%"
        st.toast("🧹 Đã dọn sạch lịch sử hội thoại và ma trận định mức!", icon="🗑️")
        st.rerun()

# Kết xuất và vẽ lại danh sách lịch sử bong bóng chat của phiên làm việc
if st.session_state.chat_history:
    for msg in st.session_state.chat_history:
        st.chat_message("user").write(msg["user"])
        st.chat_message("assistant").write(msg["ai"])

# Ô nhập liệu duy nhất khử trùng lặp Id
safe_user_prompt = st.chat_input("Gõ câu lệnh điều chỉnh thông số tại đây...", key="main_chat_input_v18_final")
st.markdown('</div>', unsafe_allow_html=True)

# 🔗 CHUYỂN TIẾP SANG PHẦN 2...

# =====================================================================
# HỆ THỐNG TOÁN HỌC V18 GERBER INDUSTRIAL MARKER ENGINE
# ĐOẠN 7 - PHẦN 2/6: BỘ TRÍCH XUẤT SPECS VÀ BỘ LỌC AN TOÀN BIÊN SỐ
# =====================================================================

# --- PHẦN 2: CORE AI ENGINE ĐIỀU PHỐI VÀ TRÍCH XUẤT THÔNG SỐ SPECS ---
if st.session_state.get("pdf_bytes") is not None and safe_user_prompt:
    current_query = str(safe_user_prompt).strip()
    
    with st.spinner("🧠 AI đang phân tách cấu trúc vật tư, song song kích hoạt Lõi Hình Học V18..."):
        try:
            import google.generativeai as genai
            import json, copy, traceback, re
            import fitz 
            
            # Khởi tạo ảnh trang 1 của tệp PDF nếu chưa được lưu trong cache bộ nhớ
            if st.session_state.pdf_page_one_image is None:
                doc_recovery = fitz.open(stream=st.session_state.pdf_bytes, filetype="pdf")
                st.session_state.pdf_page_one_image = doc_recovery.load_page(0).get_pixmap(dpi=150).tobytes("png")
            
            if "GEMINI_API_KEY" in st.secrets: 
                genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
                
            model = genai.GenerativeModel("gemini-2.5-flash", generation_config={"temperature": 0.0})
            chat_lower = current_query.lower()
            
            # =====================================================================
            # 🌟 VÁ LỖI AN TOÀN BIÊN SỐ: BỘ TRÍCH XUẤT SPECS VÀ KHÓA CHẶN SIZE RÁC CHỐT CHẶN
            # =====================================================================
            match_size = re.search(r'\b(?:size|sz|cỡ|cơ)\s*[:\-=\s]*([\w\d]+)\b', chat_lower)
            target_size_cmd = str(match_size.group(1)).upper().strip() if match_size else "30"
            
            # Chốt chặn ranh giới: Tránh hiện tượng AI bốc nhầm số trang tài liệu kỹ thuật thành số Size
            try:
                size_num_check = float(re.sub(r'[^\d\.]', '', target_size_cmd))
                if size_num_check < 20.0 or size_num_check > 50.0:
                    target_size_cmd = "30"
            except:
                pass

            # Trích xuất thông số khổ rộng cắt vải (Inch) từ câu lệnh ô chat
            match_w = re.search(r'(?:khổ|kho|width|cutwidth)\s*[:\-=\s]*([\d\.]+)', chat_lower)
            active_width = float(match_w.group(1)) if match_w else 58.0
            
            # Trích xuất tỷ lệ hao hụt co rút dọc (Warp) và co rút ngang (Weft)
            active_warp, active_weft = 3.0, 3.0
            match_warp = re.search(r'(?:dọc|doc|warp)\s*[:\-=\s]*([\d\.]+)', chat_lower)
            match_weft = re.search(r'(?:ngang|weft)\s*[:\-=\s]*([\d\.]+)', chat_lower)
            
            if match_warp: active_warp = float(match_warp.group(1))
            if match_weft: active_weft = float(match_weft.group(1))
            if not match_warp or not match_weft:
                m_sh = re.search(r'(?:co\s*rút|co\s*rut|co|shrinkage)\s*[:\-=\s]*([\d\.]+)\s*(?:-|–|x|ngang|\s+)\s*([\d\.]+)', chat_lower)
                if m_sh:
                    active_warp, active_weft = float(m_sh.group(1)), float(m_sh.group(2))

            # Ghim chặt các giá trị tỉ lệ phần trăm vào session_state để hiển thị đồng bộ lên ma trận kết quả
            st.session_state.current_warp_pct = f"{active_warp}%"
            st.session_state.current_weft_pct = f"{active_weft}%"

            techpack_text = st.session_state.get("pdf_text_cache", "Casual Twill Cargo Pants with multiple pockets.")

            # 🔗 CHUYỂN TIẾP SANG PHẦN 3: ĐÓNG GÓI PROMPT GỬI CHO GEMINI AI...
# =====================================================================
# HỆ THỐNG TOÁN HỌC V18 GERBER INDUSTRIAL MARKER ENGINE
# ĐOẠN 7 - PHẦN 3/6: CẤU TRÚC PROMPT VÀ GỌI API GEMINI AI ORCHESTRATOR
# =====================================================================

            # 🌟 PROMPT ĐIỀU PHỐI TỐI CAO: ÉP ĐỒNG BỘ LAYER CHO HÌNH HỌC V18 CHUYÊN SÂU
            prompt_instruction = f"""
            You are a Senior Apparel IE Expert and CAD Master. Your job is to analyze the Techpack data and generate a professional, detailed log for the technician.
            You must align the geometry source layers with the exact garment type found in Techpack.
            
            DATA FOUND IN TECHPACK: {techpack_text}
            CONTEXT HISTORY: {json.dumps(st.session_state.chat_history, ensure_ascii=False)}
            CURRENT USER COMMAND: "{current_query}"
            
            CRITICAL INSTRUCTION:
            - If you detect "CARGO" pockets, "FLAP", or side pockets, you MUST force the "geometry_source_layer" for Main Fabric to be "MAIN_BODY_CARGO".
            - If you detect multiple pockets for Lining (Front and Back pockets), you MUST force the layer to be "LINING" and ensure it maps to 4 pockets (8 pieces total).
            
            Return response in EXACTLY this format:
            ===START_JSON===
            {{
              "detected_product_type": "CARGO_PANT",
              "style_code": "R09-490976",
              "calculated_on_size": "{target_size_cmd}",
              "bom_rows": [
                {{
                  "component_type": "MAIN FABRIC", "placement": "BODY/POCKETS/CARGO", "fabric_classification": "MAIN_FABRIC",
                  "fabric_code": "TWILL", "fabric_color": "TBA", "fabric_width_inch": {active_width},
                  "geometry_required": true, "geometry_source_layer": "MAIN_BODY_CARGO"
                }},
                {{
                  "component_type": "INTERLINING", "placement": "WAISTBAND/FLAPS", "fabric_classification": "FUSING",
                  "fabric_code": "LIGHT KNIT", "fabric_color": "DTM", "fabric_width_inch": {active_width},
                  "_is_fusing": true, "geometry_required": true, "geometry_source_layer": "INTERLINING"
                }},
                {{
                  "component_type": "LINING", "placement": "POCKET BAGS FRONT/BACK", "fabric_classification": "LINING",
                  "fabric_code": "COTTON SHEETING", "fabric_color": "TBA", "fabric_width_inch": {active_width},
                  "_is_lining": true, "geometry_required": true, "geometry_source_layer": "LINING"
                }}
              ]
            }}
            ===END_JSON===
            ===START_CHAT===
            [WRITE YOUR DETAILED TECHPACK ANALYSIS IN VIETNAMESE HERE]
            - Hãy phân tích chi tiết kiểu dáng kỹ thuật quần casual twill cargo.
            - Giải trình cấu trúc sơ đồ, cách phân bổ cụm chi tiết chính và lót túi phụ.
            - Thuyết minh phép toán quy đổi tích phân diện tích hình học phẳng sang định mức hao hụt dệt dài dựa trên khổ vải và độ co rút.
            ===END_CHAT===
            """
            
            # Gọi mô hình để bóc tách ngữ nghĩa tệp tài liệu kỹ thuật
            response = model.generate_content(prompt_instruction)
            resp_text = response.text

            # Thực hiện phân rã các khối dữ liệu cô lập đại diện bằng Regex
            json_pattern = re.search(r'===START_JSON===\s*(.*?)\s*===END_JSON===', resp_text, re.DOTALL)
            chat_pattern = re.search(r'===START_CHAT===\s*(.*?)\s*===END_CHAT===', resp_text, re.DOTALL)
            
            ai_chat_response = chat_pattern.group(1).strip() if chat_pattern else "Đã phân tích hoàn tất hệ thống."
            
            ai_json_data = {}
            if json_pattern:
                try:
                    ai_json_data = json.loads(json_pattern.group(1).strip())
                except:
                    pass

            # 🔗 CHUYỂN TIẾP SANG PHẦN 4: PIPELINE LIÊN KẾT LUỒNG TOÁN PYTHON TÍNH ĐỊNH MỨC V18...
# =====================================================================
# HỆ THỐNG TOÁN HỌC V18 GERBER INDUSTRIAL MARKER ENGINE
# ĐOẠN 7 - PHẦN 4/6: PIPELINE KẾT NỐI LUỒNG TOÁN PYTHON TÍNH ĐỊNH MỨC V18
# =====================================================================

            updated_bom_rows = []
            geometry_reports_html = ""
            
            if ai_json_data and "bom_rows" in ai_json_data:
                # Quét duyệt tự động qua từng dòng phân tầng vật tư do AI trích xuất
                for row in ai_json_data["bom_rows"]:
                    if row.get("geometry_required", False):
                        layer_target = row.get("geometry_source_layer", "MAIN_BODY_CARGO")
                        f_width = float(row.get("fabric_width_inch", active_width))
                        f_class = str(row.get("fabric_classification", "MAIN_FABRIC"))
                        
                        # Cấu hình tự động ràng buộc hướng sớ xoay rập theo tính chất vật liệu
                        f_type = "TWO_WAY" if "MAIN" in layer_target.upper() else "FREE"
                        
                        # Kích hoạt thanh trạng thái tiến trình (Status Box) xử lý giải tích hình học thực nghiệm
                        with st.status(f"⚙️ Lõi V18 đang tự động lấp đầy sơ đồ lớp: {layer_target}...", expanded=False) as layer_status:
                            
                            # 🔄 BƯỚC 1: Gọi Hàm 1 trích xuất hình học thô và lật trục tọa độ CAD Y-Flip
                            s1 = v18_step1_extract_raw_vectors(layer_name=layer_target, warp=active_warp, weft=active_weft)
                            if s1["status"] == "success":
                                
                                # 🔄 BƯỚC 2: Gọi Hàm 2 tái dựng đa đa giác lồng nhau và khử hướng thớ nghiêng
                                s2 = v18_step2_reconstruct_and_orient_geometry(s1, seam_allowance=0.25)
                                if s2["status"] == "success" and s2["panels_catalog"]:
                                    
                                    # 🔄 BƯỚC 3: Gọi Hàm 3A+3B thực thi Engine nén Skyline dải chân trời mịn
                                    s3 = v18_step3_execute_strip_nesting(s2["panels_catalog"], target_width=f_width, fabric_type=f_type)
                                    
                                    if s3["status"] == "success":
                                        row["calculated_gross_consumption_yds"] = s3["fabric_consumption_yard"]
                                        row["consumption_note"] = f"Skyline packing complete. Marker utilization: {s3['marker_utilization_percent']}%."
                                        row["quality_gate_status"] = "PASSED"
                                        layer_status.update(label=f"✓ Lớp {layer_target} hoàn tất định mức!", state="complete")
                                        
                                        # Khởi tạo khối văn bản đồ họa HTML hiển thị nhanh thông số CAD trong ô chatbox
                                        geometry_reports_html += f"""
                                        <div style='margin-bottom:12px; padding:10px; border-left:4px solid #4CAF50; background-color:#f9f9f9;'>
                                            <b>🛠️ KẾT QUẢ ĐỊNH MỨC CAD LỚP [{layer_target}]:</b><br>
                                            • Hiệu suất sơ đồ (Utilization): <span style='color:#2E7D32; font-weight:bold;'>{s3['marker_utilization_percent']}%</span><br>
                                            • Tổng số chi tiết được xếp (Nested Pieces): {s3['total_pieces_nested']}<br>
                                            • Chiều dài sơ đồ thực tế: {s3['marker_length_inch']} Inch<br>
                                            • Định mức tiêu hao vật tư: <span style='color:#C62828; font-weight:bold;'>{s3['fabric_consumption_yard']} Yard</span> / sản phẩm
                                        </div>
                                        """
                                    else:
                                        row["calculated_gross_consumption_yds"] = 0.0
                                        row["consumption_note"] = "Nesting error fallback."
                                        row["quality_gate_status"] = "FAILED"
                                        layer_status.update(label=f"✕ Lỗi thuật toán Nesting tại lớp {layer_target}", state="error")
                                else:
                                        row["calculated_gross_consumption_yds"] = 0.0
                                        row["consumption_note"] = "No geometries or polygons found."
                                        row["quality_gate_status"] = "EMPTY"
                                        layer_status.update(label=f"⚠ Lớp {layer_target} trống hoặc không tìm thấy Polygon rập", state="warning")
                            else:
                                row["calculated_gross_consumption_yds"] = 0.0
                                row["consumption_note"] = "PDF vector extraction failed."
                                row["quality_gate_status"] = "FAILED"
                                layer_status.update(label=f"✕ Thất bại tại khâu bóc tách vector lớp {layer_target}", state="error")
                    else:
                        row["calculated_gross_consumption_yds"] = 0.0
                        row["consumption_note"] = "Calculation skipped."
                        row["quality_gate_status"] = "SKIPPED"
                        
                    updated_bom_rows.append(row)
                
                ai_json_data["bom_rows"] = updated_bom_rows
                st.session_state.active_blueprint = ai_json_data
                
                # Lưu trữ tích lũy vào bộ nhớ đệm ma trận tổng hợp
                for r in updated_bom_rows:
                    st.session_state.accumulated_bom_rows[r["component_type"]] = r

            # Ghép nối báo cáo tích phân hình học và văn bản chuyên gia AI gửi lên màn hình
            full_ai_response = ai_chat_response
            if geometry_reports_html:
                full_ai_response += "\n\n" + geometry_reports_html

            st.session_state.chat_history.append({"user": current_query, "ai": full_ai_response})
            st.rerun()

        except Exception as ai_err:
            st.error(f"Lỗi hệ thống điều phối AI Orchestrator: {str(ai_err)}")

# 🔗 CHUYỂN TIẾP SANG PHẦN 5: KHỞI DỰNG VÀ KẾT XUẤT MA TRẬN BẢNG DỮ LIỆU ĐỊNH MỨC...
# =====================================================================
# HỆ THỐNG TOÁN HỌC V18 GERBER INDUSTRIAL MARKER ENGINE
# ĐOẠN 7 - PHẦN 5/6: KHỞI DỰNG VÀ KẾT XUẤT MA TRẬN BẢNG DỮ LIỆU ĐỊNH MỨC
# =====================================================================

active_bom_source = None

# Chốt chặn kiểm tra nghiêm ngặt, cấm tự động bốc dữ liệu lịch sử rác lên hiển thị lại
if st.session_state.get("active_blueprint") and "bom_rows" in st.session_state.active_blueprint and st.session_state.active_blueprint["bom_rows"]:
    active_bom_source = st.session_state.active_blueprint
elif st.session_state.get("accumulated_bom_rows") and len(st.session_state.accumulated_bom_rows) > 0:
    active_bom_source = {"calculated_on_size": "30", "bom_rows": list(st.session_state.accumulated_bom_rows.values())}

# Chỉ render cấu trúc bảng hiển thị nếu thực sự tìm thấy dữ liệu dòng BOM hợp lệ khả dụng lớn hơn 0
if active_bom_source and active_bom_source.get("bom_rows") and len(active_bom_source["bom_rows"]) > 0:
    import pandas as pd
    extracted_size = active_bom_source.get("calculated_on_size", "30").upper()
    
    st.markdown('<div class="cad-card">', unsafe_allow_html=True)
    st.markdown(f'<div class="cad-header">📊 CALCULATED FABRIC CONSUMPTION MATRIX (SIZE TARGET: {extracted_size})</div>', unsafe_allow_html=True)
    
    # Gọi trực tiếp giá trị co rút từ bộ nhớ trạng thái an toàn để ghim thông số trên giao diện web
    warp_default = st.session_state.get("current_warp_pct", "3.0%")
    weft_default = st.session_state.get("current_weft_pct", "3.0%")
    
    display_data = []
    for r in active_bom_source["bom_rows"]:
        if not r or not isinstance(r, dict): continue
        sys_notes = r.get("consumption_note", "Optimized pattern placement via STRtree.")
        current_gross = r.get("calculated_gross_consumption_yds", 0.0)
        
        cut_width_val = f"{float(r['fabric_width_inch'])} inch" if "fabric_width_inch" in r and r["fabric_width_inch"] > 0 else "58.0 inch"
        f_class_upper = str(r.get("fabric_classification", "")).upper()
        
        # Phân rã dải co rút động: Ép phẳng về 0% cho Keo lót (Fusing) theo tiêu chuẩn kỹ thuật
        if "FUSING" in f_class_upper:
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
    st.dataframe(df_bom, use_container_width=True, hide_index=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # 🔗 CHUYỂN TIẾP SANG PHẦN 6: KHỞI TẠO BÁO CÁO EXCEL VÀ NÚT TẢI XUỐNG KHỐI CUỐI...
# =====================================================================
# HỆ THỐNG TOÁN HỌC V18 GERBER INDUSTRIAL MARKER ENGINE
# ĐOẠN 7 - PHẦN 6/6: LÕI KHỞI TẠO FILE EXCEL REPORT VÀ XỬ LÝ CLEAR BUFFER
# =====================================================================

    # KHỞI TẠO CẤU TRÚC PHÔI BẢNG TÍNH EXCEL CHUYÊN DỤNG CHO XƯỞNG MAY KHÁCH HÀNG
    try:
        import io
        from openpyxl import Workbook
        from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
        from openpyxl.utils import get_column_letter

        output = io.BytesIO()
        wb = Workbook()
        ws = wb.active
        ws.title = "BOM Fabric Consumption"
        ws.sheet_view.showGridLines = True  # Đảm bảo bật lưới ô ô tính Excel rõ ràng
        
        # Thiết kế khối Banner tiêu đề báo cáo chính (Main Corporate Title Banner)
        ws.merge_cells("A1:L1")
        ws["A1"] = f"BÁO CÁO ĐỊNH MỨC VẬT TƯ VẢI (SIZE: {extracted_size}) - STYLE: R09-490976"
        ws["A1"].font = Font(name="Calibri", size=14, bold=True, color="FFFFFF")
        ws["A1"].fill = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
        ws["A1"].alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        ws.row_dimensions[1].height = 40
        
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
        ws.row_dimensions[3].height = 28
        
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
                    cell.number_format = '#,##0.0000'  # Ghim đúng 4 số thập phân chống lệch hao hụt ngành dệt
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
            key="btn_download_excel_v18_final"  # Khóa ID tải tệp độc bản
        )
    except Exception as excel_err:
        st.warning(f"⚠️ Không thể khởi tạo nút xuất Excel báo cáo cao cấp: {str(excel_err)}")
else:
    # 🌟 KHI CLEAR TRỐNG HỆ THỐNG HOẶC MỚI KHỞI ĐỘNG TRANG: Ẩn hoàn toàn bảng ma trận, hiển thị thông báo mồi
    st.info("💡 Bộ nhớ đệm hệ thống đã được làm sạch hoàn toàn. Vui lòng nạp tệp PDF tài liệu kỹ thuật và gõ câu lệnh chatbox để chạy luồng tự động toán học mới...")
