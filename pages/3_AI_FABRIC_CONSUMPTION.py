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
st.caption("Cấu trúc lõi 13-Engine VECTOR CAD/AI - Phân tích rập thô xếp ly, cơi đáp túi mổ thực tế xưởng sản xuất")
st.markdown("---")

if "width_inch_override" not in st.session_state: st.session_state.width_inch_override = None
if "shrinkage_override" not in st.session_state: st.session_state.shrinkage_override = None
if "is_calculated" not in st.session_state: st.session_state.is_calculated = False
if "gemini_parsed_bom_data" not in st.session_state: st.session_state.gemini_parsed_bom_data = None
if "saved_pdf_bytes" not in st.session_state: st.session_state.saved_pdf_bytes = None
if "saved_pdf_name" not in st.session_state: st.session_state.saved_pdf_name = None

if "sidebar_chat_history" not in st.session_state:
    st.session_state.sidebar_chat_history = [
        {"role": "assistant", "content": "Xin chào!."}
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
# AI GEMINI VISION PARSER QUÉT CẤU TRÚC MAY RẬP THÔ THỰC TẾ
# =====================================================================
def ai_gemini_vision_pdf_parser(pdf_file_name, pdf_bytes) -> dict:
    """Ép buộc AI đóng vai trò Pattern Maker bóc tách rập thô dựa trên kỹ thuật may ráp"""
    try:
        if "GEMINI_API_KEY" in st.secrets: genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        elif "gemini" in st.secrets: genai.configure(api_key=st.secrets["gemini"].get("api_key", ""))
        
        pdf_blob = {"mime_type": "application/pdf", "data": pdf_bytes}
        prompt = """
        Bạn là một Trưởng phòng kỹ thuật rập CAD (Pattern Master). Hãy phân tích toàn bộ tài liệu kỹ thuật PDF này (Bản vẽ Sketch, Bảng thông số, Mô tả quy cách may).
        Nhiệm vụ bắt buộc là phải bóc tách đầy đủ các chi tiết rập thô (Gross Pattern Pieces) trước khi may ráp, cụ thể:
        1. KIỂM TRA XẾP LY (Pleats/Tucks): Xem thân áo/quần hay túi hộp có xếp ly không. Nếu có, kích thước rập thô bắt buộc phải CỘNG THÊM độ sâu của ly (Ví dụ: ly lật cộng thêm 1.5 inch đến 3 inch tùy quy cách ly).
        2. KIỂM TRA CẤU TRÚC TÚI MỔ (Welt/Piping Pocket): Nếu có túi mổ, bắt buộc phải bóc tách thêm chi tiết vải chính gồm: Cơi túi (Welt), Đáp cơi túi (Facing), và các miếng Lót túi (Pocket Bag) bằng vải lót phối.
        3. KIỂM TRA TÚI HỘP (Cargo Pocket): Xác định xem túi có thành túi (Pocket Wall/Bellow) và xếp ly không. Kích thước rập thô của túi phải bằng: Ngang thành phẩm + (Độ sâu ly * số lượng) + (Chiều cao thành túi * 2) + Đường may.
        4. Tuyệt đối liệt kê đủ tất cả chi tiết vải chính (SHELL) cấu thành nên sản phẩm thật trên bàn cắt.

        Trả về chuỗi JSON duy nhất theo cấu trúc chính xác dưới đây:
        {
            "style_code": "Mã style hàng",
            "description": "Mô tả sản phẩm",
            "category": "pant hoặc jacket hoặc shirt",
            "sewing_spec": {
                "hem_allowance_inch": Chiều rộng đường may lai gấu (dạng số, ví dụ gấu cuộn 1.5 inch thì ghi 1.5)"
            },
            "materials_bom": [
                {"placement": "SHELL", "width_inch": 58.0, "shrinkage_warp": 5.0, "shrinkage_weft": 15.0, "material_name": "Vải chính"}
            ],
            "garment_panels": [
                {
                    "panel_name": "Tên chi tiết rập thô (Ví dụ: Thân Trước, Thân Sau, Lưng/Cạp, Cơi Túi Mổ, Đáp Túi Mổ, Túi Hộp Cargo, Nắp Túi, Đỉa...)",
                    "quantity_per_garment": Số lượng chi tiết này cần cắt trên 1 sản phẩm dạng số,
                    "length_inch": "Kích thước chiều dài thành phẩm đo từ bảng (chuỗi hoặc số)",
                    "width_inch": "Kích thước chiều rộng thành phẩm đo từ bảng (chuỗi hoặc số)",
                    "measurement_type": "half hoặc full",
                    "added_allowance_for_pleats_or_walls": "Ghi chú kỹ thuật số inch đã cộng thêm cho xếp ly/thành túi/đáp cơi (Ví dụ: '+3.0 inch cho ly hộp và thành túi', hoặc '0' nếu không có)"
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
# =====================================================================
# SIDEBAR CONTROL (ĐOẠN 2a: VÁ LỖI CƠ CHẾ LƯU STATE LOCK CHỐNG ĐƠ TRANG)
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
    
    for chat in st.session_state.sidebar_chat_history:
        with st.chat_message(chat["role"]): st.markdown(chat["content"])
            
    user_prompt = st.chat_input("Gửi thông số cho AI...", key="garment_chat_input_unique")

# XỬ LÝ LỆNH CHAT: Đồng bộ và khóa cứng dữ liệu vào core RAM hệ thống trước khi rerun
if user_prompt:
    st.session_state.sidebar_chat_history.append({"role": "user", "content": user_prompt})
    
    # 1. Trích xuất NLP và lưu thẳng vào Session State vĩnh viễn
    text_lower = user_prompt.lower()
    width_match = re.search(r'(?:khổ|width|vải|đm|mức|cắt)\s*(\d+)', text_lower)
    if width_match: 
        st.session_state.width_inch_override = float(width_match.group(1))
        st.session_state.is_calculated = True

    co_l_match = re.search(r'(?:co dọc|dọc|l|warp)\s*(\d+)', text_lower)
    if co_l_match: 
        st.session_state.shrinkage_override = float(co_l_match.group(1))
    else:
        generic_co = re.search(r'(?:co rút|độ co|co)\s*(\d+)', text_lower)
        if generic_co: st.session_state.shrinkage_override = float(generic_co.group(1))
        
    # 2. Tạo câu phản hồi của AI
    st.session_state.sidebar_chat_history.append({
        "role": "assistant", 
        "content": f"⚙️ Đã ghi nhận thông số: '{user_prompt}'. Tiến hành giải mã sơ đồ diện tích rập thô và đẩy định mức mới cập nhật lên bảng BOM lập tức..."
    })
    st.rerun()

# =====================================================================
# ENGINE QUY ĐỔI PHÂN SỐ NGÀNH MAY 
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
        with st.spinner("AI đang bóc tách quy cách may, tính toán bù xếp ly và cấu trúc túi mổ..."):
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
        st.markdown("### 📐 DANH MỤC CÁ C CHI TIẾT RẬP THÔ KỸ THUẬT MAY (GROSS PANEL LOG)")
        
        panel_records = []
        sewing_seam_allowance = 0.44  # Biên đường may ráp công đoạn 0.44" chuẩn
        sewing_spec = data.get("sewing_spec", {})
        hem_allowance = parse_garment_fraction(sewing_spec.get("hem_allowance_inch", 0.75))

        # Tạo 3 lớp tích lũy diện tích riêng biệt dựa trên bản chất cấu phần rập thực tế
        shell_fabric_area = 0.0       
        pocketing_fabric_area = 0.0   
        interlining_fabric_area = 0.0  

        for p in panels:
            name = p.get("panel_name", "Chi tiết phụ")
            qty = int(safe_float(p.get("quantity_per_garment", 1.0)))
            l_inch = parse_garment_fraction(p.get("length_inch"))
            w_inch = parse_garment_fraction(p.get("width_inch"))
            allowance_note = p.get("added_allowance_for_pleats_or_walls", "0")

            # HIỆU CHỈNH CHU VI RẬP CAD CHỐNG VỌT SỐ (ÁP DỤNG ĐỒNG BỘ QUẦN VÀ ÁO):
            name_lower = name.lower()
            if "pant" in category.upper() or "quần" in name_lower:
                # Đối với Quần: Nếu thông số rộng rập thân (>35 inch) bị bóc trúng cả vòng, bắt buộc chia 4 để ra mảnh rập 1/4 đơn lẻ
                if any(x in name_lower for x in ["thân trước", "thân sau", "front body", "back body", "panel"]) and w_inch > 35.0:
                    w_inch = w_inch / 4.0
                elif w_inch < 15.0 and any(x in name_lower for x in ["thân trước", "thân sau", "front", "back"]):
                    # Nếu rập đã là 1/4 sẵn, giữ nguyên
                    pass
            else:
                # Đối với Áo khoác Jacket/Bomber: Thân sau là mảnh lớn chia 2 nếu bóc trúng cả vòng
                if any(x in name_lower for x in ["thân sau", "back body", "back main"]) and w_inch > 40.0:
                    w_inch = w_inch / 2.0
                elif w_inch < 35.0 and any(x in name_lower for x in ["thân", "lưng", "cạp", "waist", "hip"]):
                    w_inch = w_inch * 2.0

            # Áp dụng công thức rập thô: Cộng biên đường may ráp nối (+0.44" mỗi đầu chi tiết)
            p_length = l_inch + (2 * sewing_seam_allowance)
            if any(x in name.lower() for x in ["thân", "main", "outseam"]):
                p_length += hem_allowance
                
            p_width = w_inch + (2 * sewing_seam_allowance)

            # Diện tích hình học rập phẳng thô của cấu phần (SL * Dài rập * Rộng rập)
            panel_area = p_length * p_width * qty

            # PHÂN LOẠI DIỆN TÍCH THEO NHÓM VẬT LIỆU CHÍNH XÁC:
            if "bag" in name_lower or "lót túi" in name_lower or "pocket bag" in name_lower:
                pocketing_fabric_area += panel_area
                shell_fabric_area += (p_length * 3.0 * qty) 
            elif "keo" in name_lower or "mếch" in name_lower or "fusing" in name_lower or "interlining" in name_lower:
                interlining_fabric_area += panel_area
            else:
                shell_fabric_area += panel_area
                if any(x in name_lower for x in ["cổ", "collar", "cạp", "lưng", "waistband", "nẹp", "placket", "cuff", "bo tay"]):
                    interlining_fabric_area += panel_area

            panel_records.append({
                "Chi tiết rập thô": name,
                "Số lượng (SL)": qty,
                "Dài rập thô (+May)": round(p_length, 2),
                "Rộng rập thô (+May)": round(p_width, 2),
                "Cộng bù kỹ thuật (Ly/Cơi/Thành)": allowance_note,
                "Diện tích rập (inch²)": round(panel_area, 2)
            })

        df_panels = pd.DataFrame(panel_records)
        st.dataframe(df_panels, use_container_width=True, hide_index=True)

        # ĐỒNG BỘ BẢO TOÀN DANH MỤC PHỤ LIỆU GỐC
        materials = data.get("materials_bom", [])
        has_pocketing = any("POCKETING" in str(m.get("placement")).upper() for m in materials)
        has_interlining = any("INTERLINING" in str(m.get("placement")).upper() for m in materials)
        
        if not has_pocketing:
            materials.append({"placement": "POCKETING", "width_inch": 60.0, "shrinkage_warp": 0.0, "shrinkage_weft": 0.0, "material_name": "TC POCKETING (Vải lót túi)"})
        if not has_interlining:
            materials.append({"placement": "INTERLINING", "width_inch": 44.0, "shrinkage_warp": 0.0, "shrinkage_weft": 0.0, "material_name": "TRICOT FUSING (Keo lót phôi)"})
        data["materials_bom"] = materials

                 # --- ĐOẠN 2b2a: TRÍCH XUẤT THÔNG SỐ RẬP VÀ ĐỒNG BỘ Ô CHAT AI ---
        materials = data.get("materials_bom", [])
        
        # Mảng lưu dữ liệu cấu hình debug để hiển thị chính xác theo từng hàng
        bom_debug_log = {}

        # 1. Thuật toán trích xuất chiều dài thân trước, thân sau và tay áo làm gốc tính toán sơ đồ
        max_front_pant_length = 0.0
        max_back_pant_length = 0.0
        max_body_length = 0.0
        max_body_width = 0.0
        max_sleeve_length = 0.0
        
        for p in panels:
            name_lower = p.get("panel_name", "").lower()
            l_val = parse_garment_fraction(p.get("length_inch"))
            w_val = parse_garment_fraction(p.get("width_inch"))
            
            if any(x in name_lower for x in ["thân trước", "front pant", "front body"]):
                if l_val > max_front_pant_length: max_front_pant_length = l_val
            if any(x in name_lower for x in ["thân sau", "back pant", "back body"]):
                if l_val > max_back_pant_length: max_back_pant_length = l_val
                
            if any(x in name_lower for x in ["thân", "main", "outseam", "sau", "trước", "body"]) and "sleeve" not in name_lower:
                if l_val > max_body_length: max_body_length = l_val
                if w_val > max_body_width: max_body_width = w_val
            if any(x in name_lower for x in ["tay", "sleeve"]):
                if l_val > max_sleeve_length: max_sleeve_length = l_val

        # Bộ số dự phòng an toàn nếu file khuyết nhãn chi tiết chính
        if max_body_length == 0: max_body_length = 42.5 if "pant" in category.upper() else 33.13
        if max_front_pant_length == 0: max_front_pant_length = 43.89
        if max_back_pant_length == 0: max_back_pant_length = 49.51
        if max_sleeve_length == 0 and "pant" not in category.upper(): max_sleeve_length = round(max_body_length * 0.75, 2)

        # CƠ CHẾ KIỂM TRA LỆNH AI: Quét lịch sử chat xem người dùng đã ra lệnh tính toán chưa
        chat_history = st.session_state.get("sidebar_chat_history", [])
        has_user_command = False
        last_user_chat_content = ""
        
        # Nếu lịch sử chat có nhiều hơn 1 câu (tức là người dùng đã gõ tương tác)
        if len(chat_history) > 1:
            has_user_command = True
            # Tìm câu gõ mới nhất của người dùng để bóc tách thông số phụ liệu rời
            for msg in reversed(chat_history):
                if msg.get("role") == "user":
                    last_user_chat_content = str(msg.get("content", "")).lower()
                    break

        if len(panels) > 0:
            for mat in materials:
                placement_upper = str(mat.get("placement")).upper()
                
                # KHỞI TẠO BIẾN ĐẦU VÒNG LẶP Chặn đứng lỗi UnboundLocalError
                calc_consumption = 0.0
                target_panel_area = 0.0
                
                # --- ENGINE ĐỒNG BỘ KHỔ VẢI ĐỘNG TỪ Ô CHAT AI ---
                if st.session_state.width_inch_override and "SHELL" in placement_upper:
                    mat["width_inch"] = st.session_state.width_inch_override
                
                # Xử lý khổ riêng biệt cho phụ liệu lót và keo khi gõ chỉ định đích danh
                if has_user_command and any(x in last_user_chat_content for x in ["keo", "mếch", "lót", "phối"]):
                    if "lót" in last_user_chat_content and "POCKETING" in placement_upper:
                        # Tìm con số khổ đi liền sau chữ lót
                        pocket_w_match = re.search(r'(?:lót|khổ)\s*(\d+)', last_user_chat_content)
                        if pocket_w_match: mat["width_inch"] = float(pocket_w_match.group(1))
                    if any(x in last_user_chat_content for x in ["keo", "mếch"]) and "INTERLINING" in placement_upper:
                        inter_w_match = re.search(r'(?:keo|mếch|khổ)\s*(\d+)', last_user_chat_content)
                        if inter_w_match: mat["width_inch"] = float(inter_w_match.group(1))

                # Gán khổ vật lý nền an toàn nếu chưa gõ biến đè
                w_inch = parse_garment_fraction(mat.get("width_inch"))
                if w_inch == 0:
                    if "POCKETING" in placement_upper: w_inch = 60.0; mat["width_inch"] = 60.0
                    elif "INTERLINING" in placement_upper: w_inch = 44.0; mat["width_inch"] = 44.0
                    else: w_inch = 58.0; mat["width_inch"] = 58.0

                # --- ENGINE ĐỒNG BỘ ĐỘ CO RÚT ĐỘNG TỪ Ô CHAT AI ---
                s_warp = 0.0
                s_weft = 0.0
                
                if "SHELL" in placement_upper:
                    # Đọc con số co dọc (warp) từ Bộ nhớ Core Session State
                    if st.session_state.shrinkage_override:
                        s_warp = st.session_state.shrinkage_override / 100.0
                    
                    # Đọc con số co ngang (weft) trực tiếp từ chuỗi chat mới nhất
                    if has_user_command:
                        weft_match = re.search(r'(?:co ngang|ngang|w|weft)\s*(\d+)', last_user_chat_content)
                        if weft_match:
                            s_weft = float(weft_match.group(1)) / 100.0
                        else:
                            # Phân tích định dạng gộp gạch ngang (Ví dụ: '3-3' hoặc '5-15')
                            generic_match = re.search(r'\d+\s*-\s*(\d+)', last_user_chat_content)
                            if generic_match: s_weft = float(generic_match.group(1)) / 100.0
                    
                    # Đồng bộ ngược giá trị hiển thị lên cấu trúc bảng dữ liệu BOM
                    mat["shrinkage_warp"] = round(s_warp * 100, 1)
                    mat["shrinkage_weft"] = round(s_weft * 100, 1)

                # Bảo toàn an toàn biến diện tích đa lớp từ Đoạn 2b1
                v_shell_area = safe_float(shell_fabric_area) if 'shell_fabric_area' in locals() or 'shell_fabric_area' in globals() else 0.0
                v_pocket_area = safe_float(pocketing_fabric_area) if 'pocketing_fabric_area' in locals() or 'pocketing_fabric_area' in globals() else 0.0
                v_inter_area = safe_float(interlining_fabric_area) if 'interlining_fabric_area' in locals() or 'interlining_fabric_area' in globals() else 0.0

                effective_width_inch = w_inch * (1.0 - s_weft)

                       # --- ĐOẠN 2b2: ĐỒNG BỘ CHAT VÀ TÍNH ĐỊNH MỨC RẬP CAD RÚT GỌN ---
        materials = data.get("materials_bom", [])
        bom_debug_log = {}

        max_body_length = max([parse_garment_fraction(p.get("length_inch")) for p in panels] or [42.5])
        max_front_pant = max([parse_garment_fraction(p.get("length_inch")) for p in panels if "trước" in p.get("panel_name", "").lower()] or [43.89])
        max_back_pant = max([parse_garment_fraction(p.get("length_inch")) for p in panels if "sau" in p.get("panel_name", "").lower()] or [49.51])
        max_sleeve = max([parse_garment_fraction(p.get("length_inch")) for p in panels if "tay" in p.get("panel_name", "").lower()] or [24.0])

        # Đọc câu lệnh chat mới nhất từ Sidebar
        chat_history = st.session_state.get("sidebar_chat_history", [])
        last_chat = str(chat_history[-1].get("content", "")).lower() if len(chat_history) > 1 else ""

        if len(panels) > 0:
            for mat in materials:
                placement = str(mat.get("placement")).upper()
                calc_consumption, target_area = 0.0, 0.0
                
                # 1. Đồng bộ khổ vải vật lý động từ ô chat
                if "SHELL" in placement:
                    w_inch = st.session_state.width_inch_override if st.session_state.width_inch_override else 58.0
                elif "POCKETING" in placement:
                    pkt_match = re.search(r'lót khổ\s*(\d+)', last_chat)
                    w_inch = float(pkt_match.group(1)) if pkt_match else 60.0
                else:
                    fus_match = re.search(r'keo khổ\s*(\d+)', last_chat)
                    w_inch = float(fus_match.group(1)) if fus_match else 44.0
                mat["width_inch"] = w_inch

                # 2. Đồng bộ độ co rút dọc/ngang động từ ô chat
                s_warp, s_weft = 0.0, 0.0
                if "SHELL" in placement:
                    if st.session_state.shrinkage_override: s_warp = st.session_state.shrinkage_override / 100.0
                    weft_match = re.search(r'(?:co ngang|ngang|w|weft)\s*(\d+)', last_chat)
                    if weft_match: s_weft = float(weft_match.group(1)) / 100.0
                    else:
                        g_match = re.search(r'\d+\s*-\s*(\d+)', last_chat)
                        if g_match: s_weft = float(g_match.group(1)) / 100.0
                    mat["shrinkage_warp"], mat["shrinkage_weft"] = round(s_warp*100, 1), round(s_weft*100, 1)

                effective_width = w_inch * (1.0 - s_weft)
                v_shell = safe_float(shell_fabric_area) if 'shell_fabric_area' in locals() or 'shell_fabric_area' in globals() else 0.0
                v_pocket = safe_float(pocketing_fabric_area) if 'pocketing_fabric_area' in locals() or 'pocketing_fabric_area' in globals() else 0.0
                v_inter = safe_float(interlining_fabric_area) if 'interlining_fabric_area' in locals() or 'interlining_fabric_area' in globals() else 0.0

                # 3. Lập ma trận hiệu suất sơ đồ và tính định mức mét
                if "SHELL" in placement:
                    target_area = v_shell
                    eff, loss = (0.84, 1.04) if "PANT" in category.upper() else (0.85, 1.03)
                elif "POCKETING" in placement:
                    eff, loss, target_area = 0.86, 1.02, v_pocket
                    if v_pocket == 0: calc_consumption = (0.25 if "PANT" in category.upper() else 0.38) * (1.0 + s_warp) * loss
                else:
                    eff, loss, target_area = 0.88, 1.02, v_inter
                    if v_inter == 0: calc_consumption = (0.12 if "PANT" in category.upper() else 0.65) * (1.0 + s_warp) * loss

                if target_area > 0 and effective_width > 0:
                    if "PANT" in category.upper():
                        total_pair_len = (max_front_pant + max_back_pant) + (4 * sewing_seam_allowance) + hem_allowance
                        pant_eff = 1.445 if effective_width <= 55.0 else 1.520
                        calc_consumption = (total_pair_len * (1.0 + s_warp) / pant_eff) / 39.37 * 1.035
                        if "POCKETING" in placement: calc_consumption = round((max_body_length / 39.37) * 0.22, 3)
                        elif "INTERLINING" in placement: calc_consumption = round((max_body_length / 39.37) * 0.10, 3)
                    else:
                        m_len = (target_area * (1.0 + s_warp)) / effective_width
                        calc_consumption = (m_len / 39.37) / eff * loss
                
                mat["consumption_meter_per_pcs"] = round(calc_consumption, 3)
                mat["consumption_yard_per_pcs"] = round(calc_consumption * 1.09361, 3)
                bom_debug_log[placement] = {"area": round(target_area, 1), "eff": round(eff*100, 1), "loss": loss, "w": round(effective_width, 2), "warp": round(s_warp*100, 1), "weft": round(s_weft*100, 1)}

        st.markdown("### 🧵 BẢNG ĐỊNH MỨC NGUYÊN PHỤ LIỆU ĐỘNG (MATERIALS BOM)")
        df_bom = pd.DataFrame(materials)
        cols_order = ['placement', 'material_name', 'consumption_meter_per_pcs', 'consumption_yard_per_pcs', 'width_inch', 'shrinkage_warp', 'shrinkage_weft', 'gsm']
        st.dataframe(df_bom[[c for c in cols_order if c in df_bom.columns]], use_container_width=True)
        
        for k, dbg in bom_debug_log.items():
            if dbg["area"] > 0: st.caption(f"📍 **{k}** | Diện tích: `{dbg['area']} in²` | Co dọc: `{dbg['warp']}%` | Co ngang: `{dbg['weft']}%` | Khổ hữu dụng: `{dbg['w']}\"` | Hiệu suất: `{dbg['eff']}%` | Hao hụt: `{dbg['loss']}`")
            else: st.caption(f"📍 **{k}** | [Dự phòng] | Khổ cắt: `{dbg['w']}\"` | Đã áp mốc tiêu chuẩn kỹ thuật nhà máy.")
    else: st.warning("⚠️ Hệ thống chưa nhận được bảng chi tiết cấu phần rập từ hồ sơ PDF.")
else: st.warning("⚠️ AI không thể trích xuất cấu trúc dữ liệu từ file PDF này.")
