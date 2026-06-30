import streamlit as st
import pandas as pd
import json
import re
import google.generativeai as genai
from google.generativeai import types

# CẤU HÌNH TRANG CHUẨN PLM ENTERPRISE
st.set_page_config(page_title="AI CAD ENTERPRISE ENGINE", layout="wide")
st.title("🧩 AI GENERATIVE PATTERN & DETAILED MARKER ENGINE (V12)")
st.caption("Lõi CAD Thương mại: AI phân rã chi tiết rập phẳng từ Sketch - Python mô phỏng sơ đồ hình học")
st.markdown("---")

# QUẢN LÝ QUY TẮC PHÂN LOẠI VẬT LIỆU TOÀN CỤC
VẬT_LIỆU_REGISTRY = {
    "MAIN_FABRIC": ["SHELL", "MAIN", "BODY", "DENIM", "COTTON", "VẢI CHÍNH"],
    "CONTRAST_FABRIC": ["CONTRAST", "PHỐI", "COMBINATION"],
    "LINING_FABRIC": ["LINING", "MESH", "TAFFETA", "TRICOT", "LÓT"],
    "POCKETING_FABRIC": ["POCKETING", "TÚI"],
    "INTERLINING_FUSING": ["INTERLINING", "FUSING", "MECK", "MEX", "KEO", "DỰNG"]
}

def safe_float(val, default=0.0) -> float:
    if val is None: return default
    val_clean = str(val).replace("%", "").replace('"', '').strip().lower()
    if val_clean in ["null", "none", "unknown", "na", "n/a", ""]: return default
    try: return float(val_clean)
    except (ValueError, TypeError): return default

# HÀM MÔ PHỎNG HIỆU SUẤT SƠ ĐỒ (MARKER EFFICIENCY SIMULATION) DỰA TRÊN ĐẶC TÍNH VẢI
def simulate_marker_efficiency(fabric_type: str, grain_rule: str, width: float) -> float:
    """Mô phỏng Gerber/Lectra Nesting: Tính % hao hụt sơ đồ dựa trên chiều cắt rập và vân vải."""
    base_efficiency = 88.5  # Hiệu suất lý tưởng của máy tính
    
    # 1. Khấu trừ theo chiều cắt rập (Grain Line Rule)
    if grain_rule == "ONE_WAY" or fabric_type in ["VELVET", "NHUNG", "TUYẾT"]:
        base_efficiency -= 4.5  # Vải một chiều tốn vải hơn vì không được xoay đầu rập
    elif grain_rule == "STRIPE_MATCH" or grain_rule == "GRID_MATCH":
        base_efficiency -= 6.0  # Vải kẻ caro/sọc phải canh trùng ô nên cực kỳ hao hụt
        
    # 2. Khấu trừ theo khổ vải cắt hữu ích
    if width < 45.0: base_efficiency -= 3.0  # Khổ vải càng nhỏ càng khó xếp rập khít
    
    return max(65.0, min(base_efficiency, 93.0))
def execute_cad_polygon_consumption(ai_blueprint: dict, user_chat: str) -> dict:
    """
    DETAILED CAD COMPONENT ENGINE:
    Nhận mảng chi tiết rập ảo từ Gemini, tự động gom nhóm theo Fabric ID,
    tính diện tích đa giác rập thực tế, áp độ co rút, hao hụt bàn cắt và kết xuất.
    """
    # 1. Bóc tách và ưu tiên số liệu đè từ cửa sổ Chat của User
    w_chat, s_l_chat, s_w_chat = None, None, None
    chat_clean = str(user_chat).lower().strip()
    match_w = re.search(r'(?:khổ|kho)\s*(\d+)', chat_clean)
    if match_w: w_chat = float(match_w.group(1))
    match_range = re.search(r'(?:co\s*rút|co\s*rut|co)\s*(\d+)\s*(?:-|–|ngang|\s+)\s*(\d+)', chat_clean)
    if match_range: 
        s_l_chat = float(match_range.group(1))
        s_w_chat = float(match_range.group(2))

    product_type = ai_blueprint.get("detected_product_type", "DEFAULT")
    
    # Khởi tạo Fabric Registry để quản lý định mức gom theo mã vải/loại vải rạch ròi
    fabric_registry = {}
    
    # 2. VÒNG LẶP QUÉT VÀ PHÂN LOẠI CHI TIẾT RẬP (PIECE-BASED CAD ENGINE)
    for row in ai_blueprint.get("bom_rows", []):
        c_type = str(row.get("component_type", "")).upper()
        placement = str(row.get("placement", "")).upper()
        body_type = str(row.get("body_type", "")).upper()
        
        # Loại bỏ 100% rác kim loại/phụ liệu cứng đếm chiếc khỏi bàn tính yards dài phẳng
        if any(k in c_type or k in placement or k in body_type for k in [
            "CHỈ", "THREAD", "ZIPPER", "DÂY KÉO", "BUTTON", "NÚT", "SHANK", "RIVET", "LABEL", "MÁC", "TAG", 
            "EYELETS", "SNAP", "HOOK", "LOOP", "STOPPER", "TOGGLE", "BUCKLE", "GROMMET"
        ]):
            row["calculated_gross_consumption_yds"] = 0.0
            row["reason_or_logs"] = "Bypass Hardware Trim"
            row["status"] = "PASS"
            row["marker_efficiency_pct"] = "N/A"
            continue

        # Định danh nhóm vải độc lập (Fabric ID Mapping)
        fabric_id = row.get("fabric_id", "MAIN_SHELL")
        fabric_class = row.get("fabric_classification", "MAIN_FABRIC")
        grain_rule = row.get("fabric_grain_rule", "TWO_WAY") # ONE_WAY, TWO_WAY, STRIPE_MATCH

        # Thu thập thông số vải vật lý nền
        w_bom = w_chat if w_chat is not None else safe_float(row.get("fabric_width_inch"), 56.0)
        s_l = s_l_chat if s_l_chat is not None else safe_float(row.get("shrinkage_warp_pct"), 3.0)
        s_w = s_w_chat if s_w_chat is not None else safe_float(row.get("shrinkage_weft_pct"), 3.0)
        
        # Kích hoạt hàm mô phỏng hiệu suất sơ đồ động ở Đoạn 1 (Không hardcode)
        eff = simulate_marker_efficiency(fabric_class, grain_rule, w_bom)
        
        cutable_w = max(40.0, w_bom - 1.5)
        shrink_warp_f = 1.0 + (s_l / 100.0)
        shrink_weft_f = 1.0 + (s_w / 100.0)
        wastage_f = 1.03 # 3% hao hụt bàn cắt

        # Khởi tạo Fabric ID trong bộ nhớ đăng ký nếu chưa tồn tại
        if fabric_id not in fabric_registry:
            fabric_registry[fabric_id] = {
                "accumulated_area_sq_in": 0.0,
                "cutable_w": cutable_w,
                "eff": eff,
                "shrink_warp_f": shrink_warp_f,
                "shrink_weft_f": shrink_weft_f,
                "wastage_f": wastage_f,
                "rows_to_update": [],
                "w_saved": w_bom, "s_l_saved": s_l, "s_w_saved": s_w
            }

        # 3. TOÁN HỌC ĐA GIÁC ĐỒNG BỘ: Tính tổng diện tích từ mảng chi tiết rập ảo (Panel Catalog)
        panels = row.get("panels_catalog", [])
        row_area_sq_in = 0.0
        
        if panels:
            for panel in panels:
                p_count = safe_float(panel.get("piece_count"), 1.0)
                p_len = safe_float(panel.get("piece_length_inch"), 0.0)
                p_wid = safe_float(panel.get("piece_width_inch"), 0.0)
                shape_factor = safe_float(panel.get("shape_factor"), 0.88) # Hệ số rã đa giác rập phẳng (hình thang, vát góc, lượn đũng)
                
                # Tính diện tích thực của mảnh rập đa giác phẳng
                panel_area = p_len * p_wid * p_count * shape_factor
                row_area_sq_in += panel_area
        else:
            # Dự phòng hình chữ nhật nền nếu Techpack bị lỗi bóc tách mảnh rập thô
            row_area_sq_in = safe_float(row.get("piece_length_inch"), 12.0) * safe_float(row.get("piece_width_inch"), 10.0) * safe_float(row.get("piece_count"), 2.0) * 0.88

        # Tích lũy diện tích đa giác thô vào đúng Fabric ID quy định
        fabric_registry[fabric_id]["accumulated_area_sq_in"] += row_area_sq_in
        fabric_registry[fabric_id]["rows_to_update"].append(row)
        
        # Đánh dấu trạng thái ban đầu
        row["calculated_gross_consumption_yds"] = 0.0
        row["marker_efficiency_pct"] = f"{int(eff)}%"
        row["reason_or_logs"] = f"Cấu kiện rập [Diện tích: {round(row_area_sq_in, 1)} sq_in] -> Chờ cộng dồn vào Fabric ID: {fabric_id}"
        row["status"] = "PASS"

    # --- 4. HỆ THỐNG PHÂN BỔ ĐỊNH MỨC XÁC ĐỊNH (FINAL FABRIC OVERLAY DISPATCHER) ---
    for f_id, data in fabric_registry.items():
        total_area = data["accumulated_area_sq_in"]
        
        # Công thức CAD đổi từ diện tích đa giác phẳng (Square Inches) sang Yards dài cây vải hữu ích
        base_cons = (total_area / (data["cutable_w"] * 36.0)) / (data["eff"] / 100.0)
        final_yds = round(base_cons * data["shrink_warp_f"] * data["shrink_weft_f"] * data["data"]["wastage_f"] if "data" in data else base_cons * data["shrink_warp_f"] * data["shrink_weft_f"] * data["wastage_f"], 2)
        
        # Kiểm soát chất lượng thông minh: Kiểm tra Warning dựa trên Raw thực tế, KHÔNG CLAMP SỐ
        row_status = "PASS"
        cfg = LIMITS.get(product_type, LIMITS["DEFAULT"])
        if final_yds > cfg["warn_thresh"]: row_status = "WARNING"
        if final_yds > 3.5: row_status = "CRITICAL"

        # Đổ con số định mức tổng xác định vào dòng Vải chính đại diện của nhóm Fabric ID đó
        rows = data["rows_to_update"]
        if rows:
            # Dòng đầu tiên trong nhóm nhận tổng số Yards dài của cây vải
            main_row = rows[0]
            main_row["calculated_gross_consumption_yds"] = final_yds
            main_row["status"] = row_status
            main_row["reason_or_logs"] = f"{int(data['w_saved'])}\"/{int(data['eff'])}%/{int(data['s_l_saved'])}x{int(data['s_w_saved'])} | Tổng diện tích rập {f_id}: {round(total_area,1)} sq_in -> Kết xuất phẳng chuẩn CAD"
            
            # Các dòng phụ cấu kiện rập còn lại tự động gán nhãn trùng khít để kế toán mua hàng đối chiếu
            for sub_row in rows[1:]:
                sub_row["calculated_gross_consumption_yds"] = "Included in " + f_id
                sub_row["status"] = "PASS"
                sub_row["reason_or_logs"] = f"Cấu kiện rập phụ phối đã được tính gộp diện tích hình học vào dòng tổng {f_id}"

    return ai_blueprint
# =====================================================================
# ĐOẠN 3: AI BLUEGRAPH OBJECT PARSER VÀ RENDERING GIAO DIỆN PHẲNG V12
# =====================================================================

# KHỞI TẠO BỘ NHỚ STATE CHỐNG SẬP ỨNG DỤNG KHÔNG ĐÁNG CÓ
if "bom_data" not in st.session_state: st.session_state.bom_data = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = [{"role": "assistant", "content": "Hệ thống CAD V12 đã sẵn sàng. Tải tệp PDF lên để AI phân rã đa giác rập chi tiết phẳng."}]

with st.sidebar:
    st.header("⚙️ HỆ THỐNG")
    if st.button("🗑️ Xóa lịch sử & Reset định mức", use_container_width=True):
        st.session_state.bom_data = None
        st.session_state.pdf_bytes = None
        st.session_state.pdf_name = None
        st.session_state.chat_history = [{"role": "assistant", "content": "Hệ thống đã reset sạch cache. Vui lòng tải file PDF mới."}]
        st.rerun()

st.subheader("📁 BƯỚC 1: TẢI BIỂU MẪU SẢN XUẤT TECHPACK PDF")
uploaded_file = st.file_uploader("Kéo và thả file PDF Techpack vào đây", type=["pdf"], key="final_v12_uploader")
if uploaded_file is not None:
    st.session_state.pdf_bytes = uploaded_file.read()
    st.session_state.pdf_name = uploaded_file.name

chat_container = st.container(height=150)
with chat_container:
    for chat in st.session_state.get("chat_history", []):
        with st.chat_message(chat["role"]): st.markdown(chat["content"])

user_prompt = st.chat_input("Nhập thông số cấu hình...")
trigger_calc = st.button("🚀 KÍCH HOẠT AI PHÂN RÃ CHI TIẾT RẬP VÀ MÔ PHỎNG", use_container_width=True, type="primary")

if (trigger_calc and "pdf_bytes" in st.session_state) or (user_prompt and "pdf_bytes" in st.session_state):
    current_prompt = user_prompt if user_prompt else "Hãy tự động phân rã đa giác rập chi tiết cho file này."
    if user_prompt: st.session_state.chat_history.append({"role": "user", "content": user_prompt})
    
    # SYSTEM JSON SCHEMA MÔ PHỎNG PHẦN MỀM CAD LECTRA/GERBER TIÊU CHUẨN
    json_schema = {
        "type": "OBJECT",
        "properties": {
            "style_code": {"type": "STRING"},
            "detected_product_type": {"type": "STRING", "enum": ["JACKET", "PANT", "CAPRI_PANT", "CARGO_PANT", "JORT", "DRESS", "TSHIRT", "SHIRT", "DEFAULT"]},
            "extracted_body_length": {"type": "STRING"}, "extracted_sleeve_length": {"type": "STRING"}, "extracted_chest_width": {"type": "STRING"},
            "extracted_outseam_length": {"type": "STRING"}, "extracted_hip_width": {"type": "STRING"}, "extracted_skirt_hem_width": {"type": "STRING"},
            "bom_rows": {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "component_type": {"type": "STRING"}, "placement": {"type": "STRING"}, "body_type": {"type": "STRING"},
                        "fabric_id": {"type": "STRING"}, # Mã nhóm định danh vải phẳng (V dụ: SHELL_A, LINING_B)
                        "fabric_classification": {"type": "STRING", "enum": ["MAIN_FABRIC", "CONTRAST_FABRIC", "LINING_FABRIC", "POCKETING_FABRIC", "INTERLINING_FUSING"]},
                        "fabric_grain_rule": {"type": "STRING", "enum": ["ONE_WAY", "TWO_WAY", "STRIPE_MATCH", "GRID_MATCH"]},
                        "fabric_width_inch": {"type": "STRING"}, "marker_efficiency_pct": {"type": "STRING"}, "shrinkage_warp_pct": {"type": "STRING"}, "shrinkage_weft_pct": {"type": "STRING"},
                        # KHỐI DANH MỤC MẢNH RẬP PHÂN RÃ HÌNH HỌC (PANEL CATALOG)
                        "panels_catalog": {
                            "type": "ARRAY",
                            "items": {
                                "type": "OBJECT",
                                "properties": {
                                    "panel_name": {"type": "STRING"},       # Tên mảnh rập thô (Ví dụ: Thân trước, Thân sau, Cổ áo)
                                    "piece_count": {"type": "STRING"},      # Số lượng cấu kiện rập chi tiết cho 1 sản phẩm
                                    "piece_length_inch": {"type": "STRING"},# Chiều dài bao rập thô của chi tiết
                                    "piece_width_inch": {"type": "STRING"}, # Chiều rộng bao rập thô của chi tiết
                                    "shape_factor": {"type": "STRING"}     # Hệ số rã hình đa giác phẳng (Ví dụ: 0.78 cho rập hình vát góc đũng)
                                },
                                "required": ["panel_name", "piece_count", "piece_length_inch", "piece_width_inch"]
                            }
                        }
                    },
                    "required": ["component_type", "placement", "fabric_id", "fabric_classification"]
                }
            }
        },
        "required": ["detected_product_type", "bom_rows"]
    }

    ocr_master_prompt = f"""
    Bạn là Senior CAD Pattern & Data Engineer chuyên số hóa rập và bóc tách hồ sơ PLM.
    Nhiệm vụ của bạn: Đọc file PDF Techpack kết hợp Sketch hình ảnh để lập Bản thiết kế đa giác rập chi tiết (Panel Catalog Blueprint).
    
    ⚠️ QUY TẮC CỐT LÕI: TUYỆT ĐỐI KHÔNG ĐƯỢC TỰ TÍNH TOÁN HOẶC ĐƯA RA CON SỐ ĐỊNH MỨC YARDS CUỐI CÙNG [INDEX].
    
    HƯỚNG DẪN TRÍCH XUẤT VÀ PHÂN RÃ CHI TIẾT RẬP:
    1. ĐỌC BẢNG POM: Trích xuất thông số Spec nền hình học thô (Length, Ngực, Mông, Outseam...) điền ngoài Schema. Nhận diện kiểu đồ để gán loại trang phục chuẩn xác.
    2. GOM NHÓM THEO FABRIC ID: Hãy đọc kỹ bảng BOM. Phân nhóm tất cả các dòng phụ liệu dùng chung một loại vải vào cùng 1 mã fabric_id (Ví dụ: Vải chính thân, túi cắt từ vải chính, dây luồn lưng cắt từ vải chính đều gán fabric_id='MAIN_FABRIC_SHELL').
    3. PHÂN RÃ MẢNH RẬP ẢO (panels_catalog): Nhìn vào Sketch và bản vẽ kết cấu để phân rã nguyên liệu đó thành danh mục các mảnh rập chi tiết cấu kiện (Ví dụ: Dòng Vải chính gồm Front Panel x2, Back Panel x2, Pocket Flap x2...; Dòng dây rút gồm Waist Drawstring x1). Tìm hoặc tự suy luận thông số dài/rộng/số lượng mảnh của từng miếng rập phụ thuộc vào bảng Spec POM để điền vào Schema. Nếu chi tiết rập vát hình thang, lượn đũng cong tốn vải thì áp shape_factor trong dải từ 0.75 - 0.90 tùy độ phức tạp của chi tiết rập phẳng.
    
    Yêu cầu bổ sung: {current_prompt}
    """

    with st.spinner("AI đang bóc tách kết cấu và phân rã mảnh rập cấu kiện..."):
        try:
            pdf_blob = {"mime_type": "application/pdf", "data": st.session_state.pdf_bytes}
            model = genai.GenerativeModel('gemini-2.5-flash')
            response = model.generate_content([pdf_blob, ocr_master_prompt], generation_config=types.GenerationConfig(response_mime_type="application/json", response_schema=json_schema, temperature=0.1))
            ai_blueprint = json.loads(response.text.strip())
            
            # Gửi mảng chi tiết rập ảo qua bộ xử lý số học toán CAD phẳng ở Đoạn 2
            st.session_state.bom_data = execute_cad_polygon_consumption(ai_blueprint, user_prompt)
            st.session_state.chat_history.append({"role": "assistant", "content": "🤖 Thành công V12: AI đã rã mảnh rập ảo dựa trên Sketch, Python Engine đã mô phỏng sơ đồ cắt phẳng dứt điểm ổn định."})
        except Exception as e:
            st.session_state.chat_history.append({"role": "assistant", "content": f"❌ Lỗi: {str(e)}. Hãy chờ 1 phút rồi nhấn chạy lại nút 🚀."})
    st.rerun()

# KHỐI HIỂN THỊ BẢNG ĐỊNH MỨC CAO CẤP V12 THƯƠNG MẠI
if st.session_state.get("bom_data"):
    st.markdown(f"### 📋 BẢNG ĐỊNH MỨC CAD COMPONENT ENGINE - PHOM RẬP: `{st.session_state.bom_data.get('detected_product_type')}`")
    flat_rows = []
    for r in st.session_state.bom_data["bom_rows"]:
        flat_rows.append({
            "Giám Sát PLM": "🟢 PASS" if r.get("status") == "PASS" else ("🟡 WARNING" if r.get("status") == "WARNING" else "🔴 CRITICAL"),
            "Nguyên phụ liệu": r.get("component_type"), 
            "Vị trí sử dụng": r.get("placement"),
            "Hiệu suất sơ đồ": r.get("marker_efficiency_pct"), 
            "Định mức Gross (Yds/Pc)": r.get("calculated_gross_consumption_yds"),
            "Nhật ký Telemetry / Bản thiết kế sơ đồ CAD": r.get("reason_or_logs")
        })
    st.dataframe(pd.DataFrame(flat_rows), use_container_width=True)
