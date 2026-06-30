import streamlit as st
import pandas as pd
import json
import google.generativeai as genai
from google.generativeai import types
import ezdxf
from shapely.geometry import Polygon
import io

# =====================================================================
# CẤU HÌNH TRANG VÀ BỘ NHỚ LƯU TRỮ (STATE LOCK)
# =====================================================================
st.set_page_config(page_title="3. AI FABRIC CONSUMPTION", layout="wide")
st.title("📊 TRỢ LÝ ĐỊNH MỨC NGUYÊN PHỤ LIỆU TỰ ĐỘNG (BOM)")
st.caption("Kiến trúc CAD/PLM Công nghiệp - Đồng bộ tự động Đơn vị Đo vật lý & Bảng Ánh xạ Mã Chi tiết")
st.markdown("---")

if "gemini_parsed_bom_data" not in st.session_state: st.session_state.gemini_parsed_bom_data = None
if "saved_pdf_bytes" not in st.session_state: st.session_state.saved_pdf_bytes = None
if "saved_pdf_name" not in st.session_state: st.session_state.saved_pdf_name = None
if "saved_dxf_bytes" not in st.session_state: st.session_state.saved_dxf_bytes = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = [{"role": "assistant", "content": "Xin chào! Vui lòng tải file PDF Techpack và tệp rập DXF lên để hệ thống đồng bộ dữ liệu hình học."}]

# =====================================================================
# LÕI ENGINE 1: CAD PARSER - ĐỌC ĐƠN VỊ THỰC & BÓC TÁCH DIỆN TÍCH POLYGON VẬT LÝ
# =====================================================================
def get_dxf_unit_scale_to_inch(doc) -> float:
    """Tự động xác định đơn vị đo gốc của file rập để quy đổi chính xác về Inch vuông"""
    try:
        insunits = doc.header.get("$INSUNITS", 0)
        unit_to_inch_map = {
            1: 1.0,         # Inches -> Inch
            4: 0.0393701,   # Millimeters -> Inch
            5: 0.393701,    # Centimeters -> Inch
        }
        if insunits in unit_to_inch_map:
            return unit_to_inch_map[insunits] ** 2
            
        measurement = doc.header.get("$MEASUREMENT", 1)
        if measurement == 0:
            return 1.0 
        else:
            return 0.393701 ** 2 
    except:
        return 0.393701 ** 2

def parse_dxf_and_calculate_areas(dxf_bytes) -> dict:
    """CAD POLYGON ENGINE: Trích xuất diện tích hình học thực tế kèm theo siêu dữ liệu định danh"""
    dxf_database = {}
    if not dxf_bytes: return dxf_database
        
    try:
        dxf_stream = io.StringIO(dxf_bytes.decode('utf-8', errors='ignore'))
        doc = ezdxf.read(dxf_stream)
        msp = doc.modelspace()
        
        scale_factor_to_sq_inch = get_dxf_unit_scale_to_inch(doc)
        
        for entity in msp.query('LWPOLYLINE POLYLINE'):
            handle_id = str(entity.dxf.handle).strip().upper()
            layer_name = str(entity.dxf.layer).strip().upper()
            
            block_name = ""
            if hasattr(entity, 'dxf') and hasattr(entity.dxf, 'name'):
                block_name = str(entity.dxf.name).strip().upper()
            
            vertices = []
            if entity.dxftype() == 'LWPOLYLINE':
                vertices = [(p[0], p[1]) for p in entity.get_points()]
            else:
                vertices = [(v.dxf.location.x, v.dxf.location.y) for v in entity.vertices]
                
            if len(vertices) >= 3:
                if vertices[0] != vertices[-1]:
                    vertices.append(vertices[0])
                
                poly = Polygon(vertices)
                area_sq_inch = poly.area * scale_factor_to_sq_inch
                
                record = {
                    "handle_id": handle_id,
                    "block_name": block_name,
                    "layer_name": layer_name,
                    "area_sq_inch": round(area_sq_inch, 3)
                }
                
                dxf_database[layer_name] = record
                if block_name:
                    dxf_database[block_name] = record
                dxf_database[handle_id] = record
                
    except Exception as e:
        st.sidebar.error(f"Lỗi đọc hình học tệp DXF: {str(e)}")
        
    return dxf_database
def python_cad_consumption_calculator(bom_data: dict, dxf_bytes) -> dict:
    """
    KIẾN TRÚC ÁNH XẠ PHÂN TẦNG VÀ ĐỒNG BỘ TRẠNG THÁI (STATUS):
    1. Ưu tiên kiểm tra Piece ID/Handle/Block Name chính xác trước (Exact Match).
    2. Chạy Token Match (So khớp từng phần) làm phương án dự phòng cuối cùng.
    3. Trả về status rõ ràng ('SUCCESS' hoặc 'ERROR_MAPPING') để phục vụ quản trị và debug [INDEX].
    """
    if "bom_rows" not in bom_data: return bom_data
    
    real_dxf_db = parse_dxf_and_calculate_areas(dxf_bytes)
    
    for row in bom_data["bom_rows"]:
        comp_type = str(row.get("component_type", "")).upper()
        pieces_list = row.get("pieces", [])
        
        width = float(row.get("fabric_width_inch")) if row.get("fabric_width_inch") else 56.0
        efficiency_pct = float(row.get("marker_efficiency_target_pct")) if row.get("marker_efficiency_target_pct") else 85.0
        efficiency = efficiency_pct / 100.0
        
        shrink_l_text = str(row.get("shrinkage_warp_pct", "0")).replace("%", "")
        try: shrink_l = float(shrink_l_text) / 100.0
        except: shrink_l = 0.0
        
        total_gross_area_sq_inch = 0.0
        has_error_piece = False
        error_pieces_log = []
        
        if isinstance(pieces_list, list):
            for piece in pieces_list:
                p_name = str(piece.get("piece_name", "")).strip().upper()
                cut_qty = int(piece.get("cut_qty")) if piece.get("cut_qty") else 1
                
                matched_area = None
                
                # TẦNG 1: Ưu tiên Tuyệt đối - Exact Match với Layer Name, Block Name hoặc Handle ID [INDEX]
                if p_name in real_dxf_db:
                    matched_area = real_dxf_db[p_name]["area_sq_inch"]
                    piece["notes"] = f"Exact Mapped (Handle: {real_dxf_db[p_name]['handle_id']})"
                else:
                    # TẦNG 2: Dự phòng (Fallback) - Token Match / So khớp từng phần thông minh [INDEX]
                    for identifier, target_data in real_dxf_db.items():
                        if identifier in p_name or p_name in identifier:
                            matched_area = target_data["area_sq_inch"]
                            piece["notes"] = f"Token Mapped (Fallback Handle: {target_data['handle_id']})"
                            break
                
                if matched_area is None:
                    has_error_piece = True
                    error_pieces_log.append(p_name)
                    piece["notes"] = "PIECE_NOT_FOUND"
                else:
                    total_gross_area_sq_inch += (matched_area * cut_qty)
        
        # --- ĐỒNG BỘ TRẠNG THÁI VÀ ĐẦU RA TOÁN HỌC ---
        if has_error_piece:
            row["net_consumption_yds_pc"] = 0.000
            row["status"] = "ERROR_MAPPING"
            row["notes"] = f"❌ LỖI MAPPING: Không tìm thấy rập của chi tiết: {', '.join(error_pieces_log)}"
        elif total_gross_area_sq_inch > 0:
            usable_area_per_yard = width * 36.0 * efficiency
            net_consumption = total_gross_area_sq_inch / usable_area_per_yard
            final_yards_per_garment = net_consumption / (1.0 - shrink_l)
            row["net_consumption_yds_pc"] = round(final_yards_per_garment * 1.02, 3)
            row["status"] = "SUCCESS"
            row["notes"] = "Tính toán diện tích hình học rập thành công từ tệp DXF."
        else:
            row["net_consumption_yds_pc"] = 0.000
            row["status"] = "ERROR_MAPPING"
            row["notes"] = "Mã hàng rỗng hoặc không có danh sách chi tiết rập hợp lệ."
                
    return bom_data

def ai_gemini_vision_pdf_parser(pdf_bytes, user_custom_prompt, dxf_bytes) -> dict:
    try:
        if "GEMINI_API_KEY" in st.secrets: genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        elif "gemini" in st.secrets: genai.configure(api_key=st.secrets["gemini"].get("api_key", ""))
        else: return {"error": "Chưa cấu hình GEMINI_API_KEY trong Streamlit Secrets."}
        
        pdf_blob = {"mime_type": "application/pdf", "data": pdf_bytes}
        json_schema = {
            "type": "OBJECT",
            "properties": {
                "style_code": {"type": "STRING"}, "description": {"type": "STRING"},
                "base_size": {"type": "STRING"}, "base_pattern_fit": {"type": "STRING"},
                "technical_features": {"type": "ARRAY", "items": {"type": "STRING"}},
                "bom_rows": {
                    "type": "ARRAY",
                    "items": {
                        "type": "OBJECT",
                        "properties": {
                            "component_type": {"type": "STRING"}, "material_code": {"type": "STRING"},
                            "fabric_composition": {"type": "STRING"}, "fabric_gsm": {"type": "INTEGER", "nullable": True},
                            "fabric_width_inch": {"type": "INTEGER", "nullable": True}, "shrinkage_warp_pct": {"type": "STRING"},
                            "shrinkage_weft_pct": {"type": "STRING"}, "marker_efficiency_target_pct": {"type": "INTEGER", "nullable": True},
                            "seam_allowance": {"type": "STRING"},
                            "pieces": {
                                "type": "ARRAY",
                                "items": {
                                    "type": "OBJECT",
                                    "properties": {
                                        "piece_name": {"type": "STRING"}, "cut_qty": {"type": "INTEGER", "nullable": True},
                                        "mirror": {"type": "BOOLEAN", "nullable": True}, "grainline": {"type": "STRING"}
                                    },
                                    "required": ["piece_name"]
                                }
                            },
                            "notes": {"type": "STRING"}
                        },
                        "required": ["component_type", "pieces"]
                    }
                }
            },
            "required": ["style_code", "bom_rows"]
        }

        base_prompt = f"""
        Bạn là một Trợ lý AI chuyên trách bóc tách tài liệu kỹ thuật (Techpack & BOM Parser) đầu vào cho hệ thống CAD/PLM thương mại.
        Nhiệm vụ duy nhất: ĐỌC, PHÂN TÁCH và ĐIỀN dữ liệu thực tế từ file PDF vào hệ thống cấu trúc [INDEX].
        Tuyệt đối không tự tính toán định mức tiêu hao, giữ giá trị null nếu tài liệu không đề cập [INDEX].

        YÊU CẦU BỔ SUNG TỪ Ô CHAT CỦA USER:
        "{user_custom_prompt}"
        """

        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content(
            [pdf_blob, base_prompt],
            generation_config=types.GenerationConfig(response_mime_type="application/json", response_schema=json_schema, temperature=0.1)
        )
        
        raw_json = json.loads(response.text.strip())
        calculated_json = python_cad_consumption_calculator(raw_json, dxf_bytes)
        return calculated_json
    except Exception as e:
        return {"error": f"Lỗi bóc tách siêu dữ liệu AI: {str(e)}"}
# =====================================================================
# SIDEBAR CONTROL & INTERFACE LUỒNG CHÍNH
# =====================================================================
with st.sidebar:
    st.header("⚙️ HỆ THỐNG")
    if st.button("🗑️ Xóa lịch sử & Reset định mức", use_container_width=True):
        st.session_state.gemini_parsed_bom_data = None
        st.session_state.saved_pdf_bytes = None
        st.session_state.saved_pdf_name = None
        st.session_state.saved_dxf_bytes = None
        st.session_state.chat_history = [{"role": "assistant", "content": "Hệ thống đã reset. Vui lòng tải file mới."}]
        st.cache_data.clear()
        st.rerun()

st.subheader("📁 BƯỚC 1: NẠP TÀI LIỆU SẢN XUẤT (PDF & RẬP DXF)")
up_col1, up_col2 = st.columns(2)
with up_col1:
    uploaded_file = st.file_uploader("Nạp tài liệu kỹ thuật (Techpack / BOM PDF)", type=["pdf"], key="main_pdf_uploader")
with up_col2:
    uploaded_dxf = st.file_uploader("Nạp tệp sơ đồ rập hình học phẳng (.DXF)", type=["dxf"], key="main_dxf_uploader")

if uploaded_file is not None:
    st.session_state.saved_pdf_bytes = uploaded_file.read()
    st.session_state.saved_pdf_name = uploaded_file.name

if uploaded_dxf is not None:
    st.session_state.saved_dxf_bytes = uploaded_dxf.read()

# --- BƯỚC 2: CHAT AI NẰM NGAY DƯỚI KHU VỰC UPLOAD ---
st.markdown("---")
st.subheader("💬 TRỢ LÝ SẢN XUẤT AI")

chat_container = st.container(height=250)
with chat_container:
    for chat in st.session_state.chat_history:
        with st.chat_message(chat["role"]): st.markdown(chat["content"])

user_prompt = st.chat_input("Nhập thông số vải hoặc yêu cầu điều chỉnh...", key="main_chat_input_unique")

if user_prompt:
    st.session_state.chat_history.append({"role": "user", "content": user_prompt})
    if not st.session_state.saved_pdf_bytes:
        st.session_state.chat_history.append({"role": "assistant", "content": "⚠️ Vui lòng tải file PDF ở Bước 1 trước."})
        st.rerun()
    else:
        with st.spinner("Hệ thống đang đồng bộ AI trích xuất và CAD Engine giải hình học không gian..."):
            parsed_result = ai_gemini_vision_pdf_parser(
                st.session_state.saved_pdf_bytes, 
                user_prompt, 
                st.session_state.saved_dxf_bytes
            )
            if parsed_result and "error" not in parsed_result:
                st.session_state.gemini_parsed_bom_data = parsed_result
                ai_response_text = f"**🤖 HỆ THỐNG ĐÃ XỬ LÝ XONG:** `{st.session_state.saved_pdf_name}`\n\n* **Mã Style:** {parsed_result.get('style_code', 'N/A')}\n* **Mô tả:** {parsed_result.get('description', 'N/A')}\n\n👉 *Mời xem bảng định mức tự động tính từ diện tích Polygon tệp rập DXF ở dưới.*"
                st.session_state.chat_history.append({"role": "assistant", "content": ai_response_text})
            else:
                st.session_state.chat_history.append({"role": "assistant", "content": f"❌ Lỗi: {parsed_result.get('error', 'Lỗi dữ liệu')}"})
        st.rerun()

# BẢNG HIỂN THỊ ĐỊNH MỨC DẠNG HÀNG DỌC XẾP CHỒNG THEO DÒNG VẬT LIỆU
if st.session_state.gemini_parsed_bom_data:
    st.markdown("---")
    st.subheader("📋 BẢNG ĐỊNH MỨC MỌI BỘ - ĐỒNG BỘ ENGINE PYTHON CAD")
    
    col1, col2, col3 = st.columns(3)
    col1.markdown(f"📌 **Mã Style:** `{st.session_state.gemini_parsed_bom_data.get('style_code', 'N/A')}`")
    col2.markdown(f"📏 **Kích cỡ (Size):** `{st.session_state.gemini_parsed_bom_data.get('base_size', 'N/A')}`")
    col3.markdown(f"🧥 **Mô tả dáng:** {st.session_state.gemini_parsed_bom_data.get('description', 'N/A')}")
        
    bom_rows = st.session_state.gemini_parsed_bom_data.get("bom_rows", [])
    if bom_rows and isinstance(bom_rows, list):
        flat_table_data = []
        for row in bom_rows:
            pieces_list = row.get("pieces", [])
            pieces_names = ", ".join([f"{p.get('piece_name', '')} (x{p.get('cut_qty', 1)})" for p in pieces_list]) if isinstance(pieces_list, list) else ""
            
            # Quản trị mã hiển thị: Đổi chữ SUCCESS/ERROR sang biểu tượng trạng thái trực quan
            status_raw = row.get("status", "SUCCESS")
            status_icon = "🟢 SUCCESS" if status_raw == "SUCCESS" else "🔴 ERROR_MAPPING"
            
            flat_table_data.append({
                "Trạng Thái CAD": status_icon,
                "Loại Nguyên Phụ Liệu": row.get("component_type"),
                "Mã vật liệu": row.get("material_code"),
                "Khổ vải (inch)": row.get("fabric_width_inch"),
                "Định lượng (GSM)": row.get("fabric_gsm"),
                "Độ co L (Dọc)": row.get("shrinkage_warp_pct"),
                "Độ co W (Ngang)": row.get("shrinkage_weft_pct"),
                "Hiệu suất sơ đồ": row.get("marker_efficiency_target_pct"),
                "Định mức CAD (yds/pc)": row.get("net_consumption_yds_pc"),
                "Chi tiết rập bóc được": pieces_names,
                "Ghi chú Hệ thống / Mã Lỗi": row.get("notes")
            })
            
        df_display = pd.DataFrame(flat_table_data)
        st.dataframe(df_display, use_container_width=True)
        
        csv = df_display.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 Tải bảng định mức CAD Engine (.CSV)", data=csv, file_name="cad_engine_bom_report.csv", mime="text/csv")
