import streamlit as st
import pandas as pd
import re
import json
import io
import google.generativeai as genai

# =====================================================================
# CẤU HÌNH TRANG VÀ KHÓA BỘ NHỚ FILE VĨNH VIỄN (STATE LOCK)
# =====================================================================
st.set_page_config(
    page_title="3. AI FABRIC CONSUMPTION", 
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("📊 TRỢ LÝ ĐỊNH MỨC NGUYÊN PHỤ LIỆU TỰ ĐỘNG (BOM)")
st.caption("Cấu trúc lõi 13-Engine VECTOR CAD/AI - Mô phỏng biến hình hình học đa giác và sơ đồ cắt thực tế")
st.markdown("---")

if "width_inch_override" not in st.session_state: st.session_state.width_inch_override = None
if "shrinkage_override" not in st.session_state: st.session_state.shrinkage_override = None
if "is_calculated" not in st.session_state: st.session_state.is_calculated = False
if "gemini_parsed_bom_data" not in st.session_state: st.session_state.gemini_parsed_bom_data = None
if "saved_pdf_bytes" not in st.session_state: st.session_state.saved_pdf_bytes = None
if "saved_pdf_name" not in st.session_state: st.session_state.saved_pdf_name = None

if "sidebar_chat_history" not in st.session_state:
    st.session_state.sidebar_chat_history = [
        {"role": "assistant", "content": "Xin chào! Hệ thống đã được nâng cấp lên Lõi Quét Chi Tiết Rập Hình Học. Vui lòng tải PDF Techpack lên, AI sẽ tự động phân tích Bản vẽ (Sketch) và Bảng thông số để bóc tách diện tích từng chi tiết rập ráp nối."}
    ]

def update_config_from_text(text: str):
    """NLP Parser công nghiệp: Tự động trích xuất thông số từ nội dung chat"""
    if not text: return
    text_lower = text.lower()
    
    # 1. Quét tìm khổ vải vật lý
    width_match = re.search(r'(?:khổ|width|vải|đm|mức|cắt)\s*(\d+)', text_lower)
    if width_match: 
        st.session_state.width_inch_override = float(width_match.group(1))
        st.session_state.is_calculated = True

    # 2. Quét tìm độ co rút dọc L
    co_l_match = re.search(r'(?:co dọc|dọc|l|warp)\s*(\d+)', text_lower)
    if co_l_match: 
        st.session_state.shrinkage_override = float(co_l_match.group(1))
    else:
        generic_co = re.search(r'(?:co rút|độ co|co)\s*(\d+)', text_lower)
        if generic_co: st.session_state.shrinkage_override = float(generic_co.group(1))

    # 3. Quét tìm độ co rút ngang W
    co_w_match = re.search(r'(?:co ngang|ngang|w|weft)\s*(\d+)', text_lower)
    if co_w_match:
        if "gemini_parsed_bom_data" in st.session_state and st.session_state.gemini_parsed_bom_data:
            materials = st.session_state.gemini_parsed_bom_data.get("materials_bom", [])
            if isinstance(materials, list):
                for mat in materials:
                    if isinstance(mat, dict) and mat.get("placement") == "SHELL":
                        mat["shrinkage_weft"] = float(co_w_match.group(1))

def safe_float(val, default=0.0) -> float:
    if val is None: return default
    try: return float(val)
    except (ValueError, TypeError): return default

# =====================================================================
# AI GEMINI QUÉT ẢNH BẢN VẼ + BẢNG THÔNG SỐ ĐỂ BÓC TÁCH TỪNG CHI TIẾT RẬP
# =====================================================================
def ai_gemini_vision_pdf_parser(pdf_file_name, pdf_bytes) -> dict:
    """Ép buộc AI phân tích sâu hình ảnh bản vẽ sketch và bảng số đo để lập sơ đồ rập chi tiết"""
    try:
        if "GEMINI_API_KEY" in st.secrets: genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        elif "gemini" in st.secrets: genai.configure(api_key=st.secrets["gemini"].get("api_key", ""))
        
        pdf_blob = {"mime_type": "application/pdf", "data": pdf_bytes}
        prompt = """
        Bạn là một kỹ thuật viên sơ đồ CAD (Marker Planner) cấp cao. Hãy đọc thật kỹ tài liệu kỹ thuật PDF này bao gồm trang vẽ phác thảo cấu trúc (Sketch) và bảng thông số (POM).
        
        Nhiệm vụ bắt buộc:
        1. Phân tích hình ảnh bản vẽ mẫu quần/áo để liệt kê toàn bộ các chi tiết cấu thành bằng vải chính (SHELL) xuất hiện trên sản phẩm (Ví dụ Quần Jeans: Thân trước, Thân sau, Cạp/Lưng quần, Túi đắp sau, Đáp túi trước, Túi xu, Đáp khóa Fly, Cầu ngực/Đáp đô sau...).
        2. Dò tìm kích thước dài và rộng tương ứng của TỪNG chi tiết rập đó trong bảng thông số (POM). Nếu bảng thông số thiếu số đo chi tiết nhỏ (ví dụ túi xu), hãy dùng quy cách kỹ thuật chuẩn ngành để ước lượng.
        3. Phân biệt rõ số đo bề ngang trích xuất là NỬA VÒNG (half) hay CẢ VÒNG (full).

        Trả về một chuỗi JSON duy nhất có cấu trúc chính xác như sau:
        {
            "style_code": "Mã style hàng",
            "description": "Mô tả sản phẩm",
            "category": "pant hoặc jacket hoặc shirt",
            "sewing_spec": {
                "hem_allowance_inch": Chiều rộng đường may lai gấu (Ví dụ: 0.75 hoặc 1.0)"
            },
            "materials_bom": [
                {"placement": "SHELL", "width_inch": 58.0, "shrinkage_warp": 5.0, "shrinkage_weft": 15.0, "material_name": "Vải chính"}
            ],
            "garment_panels": [
                {
                    "panel_name": "Tên chi tiết rập (Ví dụ: Thân Trước, Thân Sau, Lưng/Cạp, Túi Đắp Sau, Đáp Túi, Túi Xu, Đáp Khóa...)",
                    "quantity_per_garment": Số lượng chi tiết này trên 1 sản phẩm dạng số (Ví dụ: Thân trước cần 2, Thân sau cần 2, Túi sau cần 2...)",
                    "length_inch": "Số đo chiều dài rập tìm thấy dạng chuỗi phân số hoặc số thập phân (Ví dụ: '31 1/2' hoặc '11')",
                    "width_inch": "Số đo chiều rộng rập tìm thấy dạng chuỗi phân số hoặc số thập phân (Ví dụ: '16 1/2' hoặc '6')",
                    "measurement_type": "half hoặc full (Ghi rõ số đo rộng này là nửa vòng hay cả vòng của chi tiết)"
                }
            ]
        }
        """
        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content([pdf_blob, prompt])
        clean_text = response.text.strip().replace("```json", "").replace("```", "")
        return json.loads(clean_text)
    except Exception as e:
        st.error(f"Lỗi phân tích AI: {str(e)}")
        return None
# =====================================================================
# ENGINE QUY ĐỔI PHÂN SỐ NGÀNH MAY (ĐÃ ĐƯA LÊN ĐẦU ĐOẠN ĐỂ VÁ LỖI BIÊN DỊCH)
# =====================================================================
def parse_garment_fraction(val) -> float:
    """Chuyển đổi chính xác phân số hỗn hợp ngành may thành số thập phân thực tế"""
    if val is None: return 0.0
    val_str = str(val).strip()
    if not val_str or val_str.lower() in ['none', 'null', 'n/a']: return 0.0
    
    # 1. Nếu bản chất đã là số thập phân, ép kiểu trực tiếp
    try: 
        return float(val_str)
    except ValueError: 
        pass
    
    # 2. Xử lý phân số bằng thuật toán bóc tách Pop/Unpack (Chống lỗi nuốt ký tự)
    try:
        if '/' in val_str:
            parts_list = re.split(r'[\s\-]+', val_str)
            
            if len(parts_list) == 2:
                # Dạng hỗn số: '16 1/2'
                frac_part_str = parts_list.pop()
                whole_part_str = parts_list.pop()
                
                whole_num = float(whole_part_str)
                
                sub_parts = frac_part_str.split('/')
                den_num = float(sub_parts.pop())
                num_num = float(sub_parts.pop())
                
                return whole_num + (num_num / den_num)
                
            elif len(parts_list) == 1:
                # Dạng phân số thuần: '1/2'
                frac_part_str = parts_list.pop()
                sub_parts = frac_part_str.split('/')
                den_num = float(sub_parts.pop())
                num_num = float(sub_parts.pop())
                
                return num_num / den_num
    except Exception:
        pass
        
    return safe_float(val, 0.0)

# =====================================================================
# SIDEBAR CONTROL (KHÔI PHỤC HOÀN TOÀN Ô CHAT VÀ LỊCH SỬ TƯƠNG TÁC)
# =====================================================================
with st.sidebar:
    st.header("💬 TRỢ LÝ SẢN XUẤT AI")
    if st.button("🗑️ Xóa lịch sử & Reset định mức", use_container_width=True):
        st.session_state.width_inch_override = None
        st.session_state.shrinkage_override = None
        st.session_state.is_calculated = False
        st.session_state.gemini_parsed_bom_data = None
        st.session_state.saved_pdf_bytes = None
        st.session_state.saved_pdf_name = None
        st.session_state.sidebar_chat_history = [
            {"role": "assistant", "content": "Hệ thống đã reset. Vui lòng tải file PDF Techpack mới để bắt đầu quy trình."}
        ]
        st.cache_data.clear()
        st.rerun()
        
    st.write("Nhập bổ sung thông tin vải, độ co rút sau khi tải PDF.")
    st.markdown("---")
    
    # Kết nối bộ nhớ đệm hiển thị lại toàn bộ lịch sử chat chit
    for chat in st.session_state.sidebar_chat_history:
        with st.chat_message(chat["role"]): st.markdown(chat["content"])
            
    user_prompt = st.chat_input("Gửi thông số cho AI...", key="garment_chat_input_unique")

if user_prompt:
    st.session_state.sidebar_chat_history.append({"role": "user", "content": user_prompt})
    update_config_from_text(user_prompt)
    st.session_state.sidebar_chat_history.append({
        "role": "assistant", 
        "content": f"⚙️ Đã nhận diện thông số: '{user_prompt}'. Tiến hành giải mã phân số bảng POM và đẩy định mức mới cập nhật vào bảng BOM ngay lặp tức..."
    })
    st.rerun()

# =====================================================================
# ENGINE QUY ĐỔI PHÂN SỐ NGÀNH MAY (ĐÃ ĐƯA LÊN ĐẦU ĐOẠN ĐỂ VÁ LỖI BIÊN DỊCH)
# =====================================================================
def parse_garment_fraction(val) -> float:
    """Chuyển đổi chính xác phân số hỗn hợp ngành may thành số thập phân thực tế"""
    if val is None: return 0.0
    val_str = str(val).strip()
    if not val_str or val_str.lower() in ['none', 'null', 'n/a']: return 0.0
    
    try: return float(val_str)
    except ValueError: pass
    
    try:
        if '/' in val_str:
            parts_list = re.split(r'[\s\-]+', val_str)
            if len(parts_list) == 2:
                frac_part_str = parts_list.pop()
                whole_part_str = parts_list.pop()
                whole_num = float(whole_part_str)
                
                sub_parts = frac_part_str.split('/')
                den_num = float(sub_parts.pop())
                num_num = float(sub_parts.pop())
                return whole_num + (num_num / den_num)
            elif len(parts_list) == 1:
                frac_part_str = parts_list.pop()
                sub_parts = frac_part_str.split('/')
                den_num = float(sub_parts.pop())
                num_num = float(sub_parts.pop())
                return num_num / den_num
    except Exception:
        pass
    return safe_float(val, 0.0)

# =====================================================================
# ĐOẠN 2b1: GIAO DIỆN CHÍNH, KHÓA BỘ NHỚ VÀ ENGINE BÓC TÁCH CHI TIẾT RẬP CAD
# =====================================================================
st.subheader("📁 BƯỚC 1: TẢI TÀI LIỆU KỸ THUẬT SẢN XUẤT (TECHPACK / BOM)")
uploaded_file = st.file_uploader("Kéo và thả file PDF Techpack hoặc bảng BOM của bạn vào đây", type=["pdf"], key="pdf_uploader")

if uploaded_file is not None:
    if st.session_state.saved_pdf_name != uploaded_file.name:
        st.session_state.saved_pdf_bytes = uploaded_file.read()
        st.session_state.saved_pdf_name = uploaded_file.name
        st.session_state.gemini_parsed_bom_data = None  

if st.session_state.saved_pdf_bytes is not None:
    st.success(f"📥 **Hệ thống đã khóa file và duy trì liên tục:** `{st.session_state.saved_pdf_name}`")
    
    if st.session_state.gemini_parsed_bom_data is None:
        with st.spinner("AI đang quét hình Sketch vẽ mẫu và Bảng thông số để lập danh mục chi tiết rập..."):
            st.session_state.gemini_parsed_bom_data = ai_gemini_vision_pdf_parser(
                st.session_state.saved_pdf_name, st.session_state.saved_pdf_bytes
            )

    data = st.session_state.gemini_parsed_bom_data
    if data:
        st.markdown("### 📋 THÔNG TIN CHUNG SẢN PHẨM")
        col1, col2, col3 = st.columns(3)
        col1.metric("Mã sản phẩm (Style)", data.get("style_code", "N/A"))
        col2.metric("Mô tả", data.get("description", "N/A"))
        category = data.get("category", "pant").lower()
        col3.metric("Phân loại cấu trúc", category.upper())

        # LƯU TRỮ VÀ HIỂN THỊ DANH MỤC CHI TIẾT RẬP AI BÓC TÁCH ĐƯỢC TỪ TRANG SKETCH/POM
        panels = data.get("garment_panels", [])
        st.markdown("### 📐 DANH MỤC CÁC CHI TIẾT RẬP VẢI CHÍNH TỰ ĐỘNG BÓC TÁCH (PANEL LOG)")
        
        panel_records = []
        sewing_seam_allowance = 0.44  # Biên đường may ráp công đoạn 0.44" chuẩn
        sewing_spec = data.get("sewing_spec", {})
        hem_allowance = parse_garment_fraction(sewing_spec.get("hem_allowance_inch", 0.75))

        total_garment_fabric_area = 0.0  # Biến tích lũy diện tích rập hình học thực tế

        for p in panels:
            name = p.get("panel_name", "Chi tiết phụ")
            qty = int(safe_float(p.get("quantity_per_garment", 1.0)))
            l_inch = parse_garment_fraction(p.get("length_inch"))
            w_inch = parse_garment_fraction(p.get("width_inch"))

            # SỬA LỖI TẠI ĐÂY: Xóa bỏ hoàn toàn lệnh nhân đôi cưỡng ép cũ.
            # Đối với bảng liệt kê chi tiết rập đơn lẻ, kích thước đã là kích thước rập thật.
            m_display = "Kích thước rập phẳng thực tế chi tiết"

            # Áp dụng công thức rập may: Cộng biên đường may ráp nối (+0.44" mỗi đầu chi tiết)
            p_length = l_inch + (2 * sewing_seam_allowance)
            if any(x in name.lower() for x in ["thân", "main", "outseam"]):
                p_length += hem_allowance
                
            p_width = w_inch + (2 * sewing_seam_allowance)

            # Tính diện tích rập phẳng chiếm dụng thật của cấu phần này (SL * Dài * Rộng)
            panel_area = p_length * p_width * qty
            total_garment_fabric_area += panel_area

            panel_records.append({
                "Chi tiết rập": name,
                "Số lượng cắt (SL)": qty,
                "Dài rập (+May)": round(p_length, 2),
                "Rộng rập (+May)": round(p_width, 2),
                "Quy cách": m_display,
                "Diện tích tích lũy (inch vuông)": round(panel_area, 2)
            })

        df_panels = pd.DataFrame(panel_records)
        st.dataframe(df_panels, use_container_width=True, hide_index=True)

        # ĐỒNG BỘ BẢO TOÀN DANH MỤC PHỤ LIỆU (Ép thêm Keo lót lót và Lót túi nếu thiếu)
        materials = data.get("materials_bom", [])
        has_pocketing = any("POCKETING" in str(m.get("placement")).upper() for m in materials)
        has_interlining = any("INTERLINING" in str(m.get("placement")).upper() for m in materials)
        
        if not has_pocketing:
            materials.append({"placement": "POCKETING", "width_inch": 60.0, "shrinkage_warp": 0.0, "shrinkage_weft": 0.0, "material_name": "TC POCKETING (Vải lót túi)"})
        if not has_interlining:
            materials.append({"placement": "INTERLINING", "width_inch": 44.0, "shrinkage_warp": 0.0, "shrinkage_weft": 0.0, "material_name": "TRICOT FUSING (Keo lót phôi)"})
        data["materials_bom"] = materials

               # --- ĐOẠN 2b2: TOÁN HỌC SƠ ĐỒ CÔNG NGHIỆP CỘNG DỒN CHI TIẾT RẬP VÀ ĐỔ BẢNG BOM ---
        materials = data.get("materials_bom", [])
        
        for mat in materials:
            placement_upper = str(mat.get("placement")).upper()
            
            # Đồng bộ thông số khổ vải và độ co rút tương tác động từ ô chat bên trái
            if "SHELL" in placement_upper:
                if st.session_state.width_inch_override: mat["width_inch"] = st.session_state.width_inch_override
                if st.session_state.shrinkage_override: mat["shrinkage_warp"] = st.session_state.shrinkage_override
            elif any(x in placement_upper for x in ["INTERLINING", "POCKETING"]):
                chat_content = str(st.session_state.sidebar_chat_history[-1].get("content", "")).lower()
                if any(x in chat_content for x in ["keo", "mếch", "lót", "phối"]) and st.session_state.width_inch_override:
                    mat["width_inch"] = st.session_state.width_inch_override

            # Gán khổ mặc định an toàn cho phụ liệu lót và mếch dán phôi nếu tài liệu bị khuyết khổ vải
            w_inch = parse_garment_fraction(mat.get("width_inch"))
            if w_inch == 0:
                if "POCKETING" in placement_upper: w_inch = 60.0; mat["width_inch"] = 60.0
                elif "INTERLINING" in placement_upper: w_inch = 44.0; mat["width_inch"] = 44.0
                else: w_inch = 58.0; mat["width_inch"] = 58.0

            s_warp = safe_float(mat.get("shrinkage_warp", 5.0 if "SHELL" in placement_upper else 0.0)) / 100.0
            s_weft = safe_float(mat.get("shrinkage_weft", 15.0 if "SHELL" in placement_upper else 0.0)) / 100.0
            
            # Ghi đè đồng bộ lệnh co rút dọc từ bộ nhớ chat bên trái
            if "SHELL" in placement_upper and st.session_state.shrinkage_override:
                s_warp = st.session_state.shrinkage_override / 100.0

            # THUẬT TOÁN ĐỊNH MỨC SƠ ĐỒ BÀN CẮT BASED ON PANEL AREA:
            if total_garment_fabric_area > 0:
                # 1. Nhân hệ số co rút cơ học cho diện tích rập tổng hợp (Phình rập theo warp và weft)
                final_fabric_area_sq_inch = total_garment_fabric_area * (1 + s_warp) * (1 + s_weft)
                
                # 2. Quy đổi diện tích chi tiết rập chiếm dụng sang số mét chiều dài của cây vải:
                base_consumption_meter = (final_fabric_area_sq_inch / w_inch) / 39.37
                
                # 3. Áp dụng Hiệu suất đi sơ đồ bàn cắt công nghiệp (Marker Efficiency Factor):
                calc_consumption = base_consumption_meter / 0.84
                
                # 4. Cộng thêm đầu cây hao hụt biên lỗi cắt kỹ thuật đầu cây (5%)
                calc_consumption = calc_consumption * 1.05
                
                # Gán định mức riêng biệt cho các vị trí phụ trợ lót túi và mếch theo tiêu chuẩn ngành may
                if "POCKETING" in placement_upper: 
                    calc_consumption = 0.25  
                elif "INTERLINING" in placement_upper: 
                    calc_consumption = 0.12  

                mat["consumption_meter_per_pcs"] = round(calc_consumption, 3)
                mat["consumption_yard_per_pcs"] = round(calc_consumption * 1.09361, 3)
            else:
                mat["consumption_meter_per_pcs"] = "Khuyết số đo chi tiết rập"
                mat["consumption_yard_per_pcs"] = "Khuyết số đo chi tiết rập"

        st.markdown("### 🧵 BẢNG ĐỊNH MỨC NGUYÊN PHỤ LIỆU ĐỘNG (MATERIALS BOM)")
        df_bom = pd.DataFrame(materials)
        
        # Ép sắp xếp và hiển thị bảng định mức BOM động ra màn hình chính
        cols_order = ['placement', 'material_name', 'consumption_meter_per_pcs', 'consumption_yard_per_pcs', 'width_inch', 'shrinkage_warp', 'shrinkage_weft', 'gsm']
        df_bom = df_bom[[c for c in cols_order if c in df_bom.columns]]
        st.dataframe(df_bom, use_container_width=True)
        
        # SỬA LỖI TẠI ĐÂY: Xóa bỏ hoàn toàn ký tự mũ 2 đặc biệt, viết chữ inch vuông thuần túy
        st.info(f"⚙️ **Lõi Sơ đồ CAD Tích lũy:** Tổng diện tích hình học rập dải phẳng (thân+lưng+túi+đáp) có cộng biên may ráp ráp (+0.44\"): `{round(total_garment_fabric_area, 2)} inch vuong`. Hieu suat di so do thuc te xuong: `84.0%`")
    else:
        st.warning("⚠️ AI không thể trích xuất cấu trúc dữ liệu từ file PDF này. Vui lòng kiểm tra lại chất lượng file.")
else:
    st.info("💡 Vui lòng tải một file PDF Techpack lên để hệ thống phân tích hình học đa giác.")
