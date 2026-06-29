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
        st.markdown("### 📐 DANH MỤC CÁC CHI TIẾT RẬP THÔ KỸ THUẬT MAY (GROSS PANEL LOG)")
        
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

            # CHUẨN HÓA VÀ LÀM SẠCH CHUỖI TOÀN DIỆN CHỐNG LỖI KÝ TỰ VIẾT HOA
            name_lower = str(name).lower().strip()
            category_upper = str(category).upper()

            # BỘ LỌC KIỂM TRA CHU VI RẬP PHẲNG:
            if "PANT" in category_upper or "quần" in name_lower:
                # Đối với Quần: Nếu thông số rộng rập thân (>28 inch) bị bóc trúng cả vòng hông/mông, bắt buộc chia 4 về mảnh rập 1/4 đơn lẻ
                if any(x in name_lower for x in ["thân trước", "thân sau", "front", "back", "panel"]):
                    if w_inch > 28.0:
                        w_inch = w_inch / 4.0
            else:
                # Đối với Áo khoác Jacket/Bomber: Thân sau là mảnh lớn chia 2 nếu bóc trúng cả vòng chu vi ngực
                if any(x in name_lower for x in ["thân sau", "back body", "back main"]) and w_inch > 40.0:
                    w_inch = w_inch / 2.0
                elif w_inch < 35.0 and any(x in name_lower for x in ["thân", "lưng", "cạp", "waist", "hip"]):
                    w_inch = w_inch * 2.0

            # Áp dụng công thức rập thô: Cộng biên đường may ráp nối (+0.44" mỗi đầu chi tiết)
            p_length = l_inch + (2 * sewing_seam_allowance)
            if any(x in name_lower for x in ["thân", "main", "outseam"]):
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
            materials.append({"placement": "POCKETING", "width_inch": 56.0, "shrinkage_warp": 0.0, "shrinkage_weft": 0.0, "material_name": "TC POCKETING (Vải lót túi)"})
        if not has_interlining:
            materials.append({"placement": "INTERLINING", "width_inch": 59.0, "shrinkage_warp": 0.0, "shrinkage_weft": 0.0, "material_name": "TRICOT FUSING (Keo lót phôi)"})
        data["materials_bom"] = materials

       # --- SECTION 2b2a: CAD DATA GEOMETRY EXTRACTION & FABRIC CONFIGURATION ---
        materials = data.get("materials_bom", [])
        bom_debug_log = {}

        # RAM OPTIMIZATION: Initialize fabric area variables safely at segment start, clearing locals/globals scope
        v_shell = safe_float(shell_fabric_area) if 'shell_fabric_area' in locals() or 'shell_fabric_area' in globals() else 0.0
        v_pocket = safe_float(pocketing_fabric_area) if 'pocketing_fabric_area' in locals() or 'pocketing_fabric_area' in globals() else 0.0
        v_inter = safe_float(interlining_fabric_area) if 'interlining_fabric_area' in locals() or 'interlining_fabric_area' in globals() else 0.0

        # LENGTH/WIDTH SWAP GUARD:
        for p in panels:
            p_name = str(p.get("panel_name", "")).lower()
            if any(x in p_name for x in ["thân", "front", "back", "body", "panel"]):
                raw_len = parse_garment_fraction(p.get("length_inch"))
                raw_wid = parse_garment_fraction(p.get("width_inch"))
                if raw_wid > raw_len and raw_len < 10.0:
                    orig_len = p.get("length_inch")
                    p["length_inch"] = p.get("width_inch")
                    p["width_inch"] = orig_len

        # AREA CORRECTION STREAM FOR CLEAN CAD DATA
        for p in panels:
            p_area = safe_float(p.get("area_inch2", 0.0))
            p_qty = safe_float(p.get("quantity", p.get("sl", 1.0)))
            if p_qty <= 0: p_qty = 1.0
            raw_len = parse_garment_fraction(p.get("length_inch"))
            raw_wid = parse_garment_fraction(p.get("width_inch"))
            
            if p_area < 1.0 and raw_len > 0 and raw_wid > 0:
                p["area_inch2"] = raw_len * raw_wid * p_qty

        # Dynamically aggregate total material areas directly from the parsed pattern table
        v_shell = sum([safe_float(p.get("area_inch2", 0.0)) for p in panels if "shell" in str(p.get("material", "shell")).lower() or "vải chính" in str(p.get("material", "")).lower()])
        v_pocket = sum([safe_float(p.get("area_inch2", 0.0)) for p in panels if "pocket" in str(p.get("material", "")).lower() or "lót" in str(p.get("material", "")).lower()])
        v_inter = sum([safe_float(p.get("area_inch2", 0.0)) for p in panels if "inter" in str(p.get("material", "")).lower() or "keo" in str(p.get("material", "")).lower() or "mếch" in str(p.get("material", "")).lower()])

        # GLOBAL BODY PANELS FILTER: Gerber/Lectra techpack filtering regex
        body_keywords = ["front", "back", "body", "panel", "side", "thân", "trước", "sau", "sườn"]
        noise_keywords = ["yoke", "cầu vai", "đô", "waistband", "cạp", "lưng", "hood", "nón", "mũ", "pocket", "túi", "cuff", "bo", "collar", "cổ", "flap"]
        
        body_panels = [
            p for p in panels 
            if any(x in str(p.get("panel_name", "")).lower() for x in body_keywords) 
            and not any(y in str(p.get("panel_name", "")).lower() for y in noise_keywords)
        ]
        
        max_body_length = max([parse_garment_fraction(p.get("length_inch")) for p in body_panels] or [33.13])
        max_body_width = max([parse_garment_fraction(p.get("width_inch")) for p in body_panels] or [24.0])
        
        max_front_pant = max([parse_garment_fraction(p.get("length_inch")) for p in body_panels if any(x in str(p.get("panel_name", "")).lower() for x in ["trước", "front", "front body"])] or [45.26])
        max_back_pant = max([parse_garment_fraction(p.get("length_inch")) for p in body_panels if any(x in str(p.get("panel_name", "")).lower() for x in ["sau", "back", "back body"])] or [50.76])
        
        sleeve_panels = [p for p in panels if any(x in str(p.get("panel_name", "")).lower() for x in ["tay", "sleeve"])]
        max_sleeve = max([parse_garment_fraction(p.get("length_inch")) for p in sleeve_panels] or [34.88])

        is_raglan_or_kimono = any(x in str(data.get("description", "")).lower() or x in str(data.get("style_code", "")).lower() for x in ["raglan", "kimono", "dolman"])
        if is_raglan_or_kimono and "pant" not in category.lower():
            max_body_length = max_body_length * 1.12

        chat_history = st.session_state.get("sidebar_chat_history", [])
        last_chat = str(chat_history[-1].get("content", "")).lower() if len(chat_history) > 1 else ""
# --- SECTION 2b2b: UNIVERSAL COMMERCIAL CAD MARKER ENGINE ---
        if len(panels) > 0:
            for mat in materials:
                placement = str(mat.get("placement")).upper()
                calc_consumption, target_area = 0.0, 0.0
                
                # A. PHYSICAL FABRIC WIDTH EXTRACTION FROM AI CHAT STREAM
                if "SHELL" in placement:
                    shell_w_match = re.search(r'(?:khổ|k|w|width)\s*(\d+(?:\.\d+)?)', last_chat) if last_chat else None
                    if shell_w_match:
                        w_inch = float(shell_w_match.group(1))
                    else:
                        w_inch = st.session_state.width_inch_override if st.session_state.width_inch_override else 58.0
                elif "POCKETING" in placement:
                    pkt_match = re.search(r'(?:lót khổ|lining width|pocketing)\s*(\d+(?:\.\d+)?)', last_chat) if last_chat else None
                    w_inch = float(pkt_match.group(1)) if pkt_match else 57.0
                else:
                    fus_match = re.search(r'(?:keo khổ|fus|interlining)\s*(\d+(?:\.\d+)?)', last_chat) if last_chat else None
                    w_inch = float(fus_match.group(1)) if fus_match else 59.0
                mat["width_inch"] = w_inch

                # B. SHRINKAGE FACTOR EXTRACTION FROM AI CHAT STREAM
                s_warp, s_weft = 0.0, 0.0
                if "SHELL" in placement:
                    has_chat_shrinkage = False
                    if last_chat:
                        warp_match = re.search(r'(?:co dọc|dọc|warp|length)\s*(\d+(?:\.\d+)?)', last_chat)
                        weft_match = re.search(r'(?:co ngang|ngang|w|weft|width)\s*(\d+(?:\.\d+)?)', last_chat)
                        generic_match = re.search(r'(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)', last_chat)
                        
                        if warp_match:
                            s_warp = float(warp_match.group(1)) / 100.0
                            has_chat_shrinkage = True
                        if weft_match:
                            s_weft = float(weft_match.group(1)) / 100.0
                            has_chat_shrinkage = True
                        if not has_chat_shrinkage and generic_match:
                            s_warp = float(generic_match.group(1)) / 100.0
                            s_weft = float(generic_match.group(2)) / 100.0
                            has_chat_shrinkage = True

                    if not has_chat_shrinkage:
                        if st.session_state.shrinkage_override:
                            s_warp = st.session_state.shrinkage_override / 100.0
                        else:
                            s_warp = safe_float(mat.get("shrinkage_warp", 5.0)) / 100.0
                        s_weft = safe_float(mat.get("shrinkage_weft", 15.0)) / 100.0
                    
                    mat["shrinkage_warp"], mat["shrinkage_weft"] = round(s_warp*100, 1), round(s_weft*100, 1)

                # ZERO-DIVISION SAFEGUARD: Compute effective width before wash (minus 1 inch safety border)
                effective_width = max(10.0, w_inch - 1.0)

                # -----------------------------------------------------------------
                # ARITHMETIC CORE ENGINE: AUTOMATIC NESTING EFFICIENCY FOR ALL CATEGORIES
                # -----------------------------------------------------------------
                loss = 1.0  # Loại bỏ hoàn toàn hao hụt dư thừa (Loss = 1.0)
                cat_upper = str(category).upper()

                if "PANT" in cat_upper:
                    # --- THUẬT TOÁN ĐỊNH MỨC QUẦN DÀI (DIỆN TÍCH THỰC TẾ 1 SẢN PHẨM KHÔNG CHIA ĐÔI) ---
                    main_body_area = sum([safe_float(p.get("area_inch2")) for p in body_panels if any(x in str(p.get("panel_name", "")).lower() for x in ["thân", "front", "back"])])
                    target_area = main_body_area if main_body_area > 10.0 else v_shell
                    eff = 0.82  # Hiệu suất sơ đồ tinh chuẩn Gerber cho phom quần Jeans
                    
                    if "POCKETING" in placement: 
                        calc_consumption = round(((max_back_pant) / 39.37) * 0.21, 3); target_area = v_pocket; eff = 0.86
                    elif "INTERLINING" in placement: 
                        calc_consumption = round(((max_back_pant) / 39.37) * 0.09, 3); target_area = v_inter; eff = 0.88
                    else:
                        if target_area > 0 and effective_width > 0:
                            marker_length_inch = target_area / effective_width
                            # SỬA DỨT ĐIỂM: Bỏ chia đôi, tính chuẩn xác 100% không gian chiếm chỗ của một chiếc quần dài hoàn chỉnh
                            calc_consumption = (marker_length_inch / 39.37) / eff * loss
                        else: calc_consumption = 0.0

                elif any(x in cat_upper for x in ["JACKET", "BOMBER", "COAT"]):
                    # --- THUẬT TOÁN ĐỊNH MỨC ÁO KHOÁC (JACKET, BOMBER...) ---
                    target_area = v_shell
                    eff = 0.85  
                    
                    if "POCKETING" in placement:
                        calc_consumption = round(((max_body_length + max_sleeve) / 39.37) * 0.22, 3); target_area = v_pocket; eff = 0.86
                    elif "INTERLINING" in placement:
                        if v_inter > 0 and effective_width > 0:
                            calc_consumption = (v_inter / effective_width / 39.37) / 0.88
                        else: calc_consumption = round(((max_body_length) / 39.37) * 0.15, 3)
                        target_area = v_inter; eff = 0.88
                    else:
                        if target_area > 0 and effective_width > 0:
                            marker_length_inch = target_area / effective_width
                            calc_consumption = (marker_length_inch / 39.37) / eff * loss
                        else: calc_consumption = 0.0

                else:
                    # --- THUẬT TOÁN ĐỊNH MỨC CHO CÁC DÒNG HÀNG CÒN LẠI (SHIRT, T-SHIRT, HOODIE...) ---
                    target_area = v_shell
                    eff = 0.88  
                    
                    if "POCKETING" in placement:
                        calc_consumption = round((max_body_length / 39.37) * 0.12, 3); target_area = v_pocket; eff = 0.86
                    elif "INTERLINING" in placement:
                        calc_consumption = round((max_body_length / 39.37) * 0.05, 3); target_area = v_inter; eff = 0.88
                    else:
                        if target_area > 0 and effective_width > 0:
                            marker_length_inch = target_area / effective_width
                            calc_consumption = (marker_length_inch / 39.37) / eff * loss
                        else: calc_consumption = 0.0

                # DATA STREAM COMPILATION AND ASSIGNMENT
                final_consumption = round(max(0.0, calc_consumption), 3)
                mat["calculated_consumption"] = final_consumption
                
                bom_debug_log[placement] = {
                    "material_name": mat.get("material_name", ""),
                    "width_inch": w_inch,
                    "effective_width": round(effective_width, 2),
                    "shrinkage_warp": round(s_warp * 100, 1),
                    "shrinkage_weft": round(s_weft * 100, 1),
                    "target_area_inch2": round(target_area, 2),
                    "efficiency": eff,
                    "loss_factor": loss,
                    "final_consumption_yds": final_consumption
                }






# --- SECTION 2b3: STREAMLIT BOM INTERFACE RENDERER & EXCEL EXPORTER ---
        import pandas as pd
        import io

        if bom_debug_log:
            st.markdown("### 📊 BILL OF MATERIALS AND CONSUMPTION REPORT (BOM)")
            
            bom_display_data = []
            for position, details in bom_debug_log.items():
                bom_display_data.append({
                    "Placement (Material Class)": position,
                    "Material Description": details["material_name"],
                    "Physical Width (Inch)": details["width_inch"],
                    "Effective Cut Width (Inch)": details["effective_width"],
                    "Warp Shrinkage (%)": details["shrinkage_warp"],
                    "Weft Shrinkage (%)": details["shrinkage_weft"],
                    "Nesting Area (Inch²)": details["target_area_inch2"],
                    "Marker Efficiency (Eff)": details["efficiency"],
                    "Waste Factor (Loss = 1.0)": details["loss_factor"],
                    "Final Consumption (Yds)": details["final_consumption_yds"]
                })
            
            df_bom = pd.DataFrame(bom_display_data)
            st.dataframe(df_bom, use_container_width=True)

            # --- RAM BUFFER XLSX WRITER FILE COMPILATION ENGINE ---
            try:
                style_code = str(data.get("style_code", "BOM_Report")).strip()
                excel_filename = f"BOM_{style_code}.xlsx"

                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
                    df_bom.to_excel(writer, index=False, sheet_name="BOM Summary")
                
                buffer.seek(0)

                st.download_button(
                    label="📥 Export Bill of Materials to Excel (XLSX)",
                    data=buffer,
                    file_name=excel_filename,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            except Exception as ex:
                st.warning(f"Technical Notice: Excel export down due to missing system wheels (xlsxwriter): {str(ex)}")
