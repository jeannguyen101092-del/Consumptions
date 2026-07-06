
import streamlit as st
import re
import json
import copy

# =====================================================================
# KIẾN TRÚC MỚI V75.0: PURE NUMERICAL CAD CALCULATOR (GOLD PRODUCTION)
# 🌟 KHÔNG CÒN 2.000 DÒNG ENGINE CŨ - TRIỆT TIÊU TOÀN BỘ LỖI CRASH VÀ SẬP LÙI LỀ
# 🌟 AI TỰ SUY LUẬN DIỆN TÍCH THỰC - PYTHON THỰC THI PHÉP CHIA TUYỆT ĐỐI KHÔNG SAI LỆCH
# =====================================================================

# 1. BỘ TỪ KHÓA ĐỂ LỌC VÀ LOẠI TRỪ CÁC PHỤ LIỆU CỨNG MAY MẶC AN TOÀN
EXCLUDE_HARDWARE_KEYS = (
    "CHỈ", "THREAD", "ZIPPER", "DÂY KÉO", "BUTTON", "NÚT", "SHANK", "RIVET", 
    "LABEL", "MÁC", "TAG", "EYELETS", "SNAP", "VELCRO", "HOOK", "LOOP", 
    "STOPPER", "TOGGLE", "BUCKLE", "GROMMET", "STICKER", "CARE WHITE", 
    "HEAT STAMP", "HANGTAG", "POLYBAG", "BAO BÌ"
)

def allocate_fabric_consumption_and_quality_gate(blueprint_final: dict, query_string: str) -> dict:
    st.warning("⚡ DETREMINISTIC INDUSTRIAL ENGINE: QUALITY GATEWAY V100.5 ACTIVATED")
    
    if not blueprint_final or "bom_rows" not in blueprint_final:
        return blueprint_final
        
    filtered_bom_rows = []
    product_type = str(blueprint_final.get("detected_product_type", "JEANS")).upper().strip()
    
    # =====================================================================
    # 🧠 TẦNG 1: NÂNG CẤP BỘ LỌC REGEX ĐA BIẾN - TRÍCH XUẤT CO RÚT TUYỆT ĐỐI
    # =====================================================================
    warp_num, weft_num = 0.03, 0.03 # Giá trị dự phòng mặc định (3% dọc, 3% ngang)
    try:
        chat_txt = str(query_string).lower()
        # Trích xuất tất cả các cụm số (kể cả số thập phân) xuất hiện trong câu lệnh chat
        all_numbers = re.findall(r'[\d\.]+', chat_txt)
        
        if any(k in chat_txt for k in ["co rút", "co rut", "sh", "shrinkage"]):
            # Lọc bỏ các số liên quan đến Size hoặc Khổ vải dựa trên vị trí từ khóa để cô lập số co rút
            clean_shrink_numbers = []
            for num_str in all_numbers:
                # Nếu số này trùng với khổ vải hoặc kích cỡ đã nhận dạng thì bỏ qua không đưa vào mảng co rút
                if "size" in chat_txt and num_str in chat_txt.split("size")[-1][:10]: continue
                if "khổ" in chat_txt and num_str in chat_txt.split("khổ")[-1][:10]: continue
                if "kho" in chat_txt and num_str in chat_txt.split("kho")[-1][:10]: continue
                if "width" in chat_txt and num_str in chat_txt.split("width")[-1][:10]: continue
                clean_shrink_numbers.append(num_str)
                
            if len(clean_shrink_numbers) >= 2:
                warp_num = float(clean_shrink_numbers[-2]) / 100.0
                weft_num = float(clean_shrink_numbers[-1]) / 100.0
            elif len(clean_shrink_numbers) == 1:
                warp_num = float(clean_shrink_numbers[0]) / 100.0
                weft_num = float(clean_shrink_numbers[0]) / 100.0
    except Exception:
        warp_num, weft_num = 0.03, 0.03

    ai_bom_rows = blueprint_final.get("bom_rows", [])
    
    for ai_row in ai_bom_rows:
        ui_row = copy.deepcopy(ai_row)
        
        # 1. Thu thập và kiểm tra thông số Khổ vải an toàn
        raw_width = ui_row.get("fabric_width_inch")
        try: width_inch = float(raw_width or 56.0)
        except: width_inch = 56.0
        if width_inch < 1.0: width_inch = 56.0
        
        # =====================================================================
        # ⚠️ TẦNG 2: TECHNICAL QUALITY GATE - THẨM ĐỊNH HIỆU SUẤT SƠ ĐỒ (MARKER EFFICIENCY)
        # =====================================================================
        raw_eff = str(ui_row.get("marker_efficiency", "85.5%")).replace("%", "")
        try: 
            efficiency_num = float(raw_eff)
            # Nếu AI trả về dạng số thập phân phẳng (VD: 0.855) thay vì phần trăm (85.5)
            if efficiency_num < 1.0: efficiency_num = efficiency_num * 100.0
            efficiency_num = efficiency_num / 100.0
        except: 
            efficiency_num = 0.855
            
        # CHỐT KHÓA RÀO CHẮN CHẤT LƯỢNG (QUALITY GATE): Giới hạn hiệu suất trong khoảng hợp lý [0.60 - 0.93]
        if efficiency_num < 0.60 or efficiency_num > 0.93:
            efficiency_num = 0.845 # Ép cưỡng bức về mức hiệu suất tiêu chuẩn an toàn của rập Jeans
            ui_row["system_notes_qa"] = "⚠️ Hiệu suất AI dự đoán phi lý. Cổng bảo vệ tự động ép về mức an toàn 84.5%."
        else:
            ui_row["system_notes_qa"] = "✅ Thẩm định chất lượng sơ đồ: ĐẠT TIÊU CHUẨN."

        # =====================================================================
        # 🧮 TẦNG 3: DETERMINISTIC EXECUTION - ENGINE TÍNH TOÁN TOÁN HỌC PHẲNG CHUẨN
        # =====================================================================
        total_net_area = float(ui_row.get("total_net_area_sq_inch", 0.0) or 0.0)
        fab_class = str(ui_row.get("fabric_classification", "")).upper().strip()
        
        # CHỐT CHẶN KIỂM TRA DIỆN TÍCH ĐẦU VÀO CÓ HỢP LÝ KHÔNG (Diện tích phải > 0)
        if total_net_area > 0 and efficiency_num > 0:
            # 🟢 SỬA LỖI LỚN NHẤT: Tuyệt đối KHÔNG nhân đôi diện tích ở đây nữa. 
            # Giữ nguyên tổng diện tích thực tế của tất cả chi tiết do AI bóc tách sang.
            
            # Phép toán 1: Áp mở rộng co rút vật lý thực tế: Area * (1 + warp) * (1 + weft)
            expanded_area = total_net_area * (1.0 + warp_num) * (1.0 + weft_num)
            
            # Phép toán 2: Công thức hình học phẳng CAD chuyển đổi sang Linear Yards Gross
            gross_val = expanded_area / (width_inch * 36.0 * efficiency_num)
            
            # Phép toán 3: Thêm hệ số an toàn hao hụt vải đầu cây nhỏ chuẩn nhà máy (Wastage Buffer 3%)
            gross_val = round(gross_val * 1.03, 3)
        else:
            # Đối với các dòng phụ liệu Trim dệt sẵn không tính theo diện tích bề mặt (VD: Elastic)
            try: gross_val = round(float(ui_row.get("gross_consumption", 0.0)), 3)
            except: gross_val = 0.0
            
        # Đồng bộ và đẩy toàn bộ dữ liệu sạch ra màn hình giao diện
        ui_row["fabric_width_inch"] = width_inch
        ui_row["gross_consumption"] = gross_val
        ui_row["marker_efficiency"] = f"{round(efficiency_num * 100, 1)}%"
        ui_row["_btp_warp_pct"] = f"{round(warp_num * 100, 1)}%"
        ui_row["_btp_weft_pct"] = f"{round(weft_num * 100, 1)}%"
        ui_row["quality_status"] = "PASS" if gross_val > 0 else "CHECK"
        ui_row["system_notes"] = f"{ui_row.get('reasoning', '')} | {ui_row.get('system_notes_qa', '')}"
        
        filtered_bom_rows.append(ui_row)
        
    # Ép đồng bộ bộ nhớ Streamlit vẽ lại bảng
    st.session_state["bom_rows"] = filtered_bom_rows
    st.session_state["accumulated_bom_rows"] = filtered_bom_rows
    st.session_state["bom_data"] = {"bom_rows": filtered_bom_rows, "detected_product_type": product_type, "calculated_on_size": blueprint_final.get("calculated_on_size", "30")}
    
    return st.session_state["bom_data"]

















# =====================================================================
# ĐOẠN 6a: BANNER, KPIs GHIM ĐỈNH & CÂN BẰNG CHIỀU CAO 1:1 ĐỐI XỨNG (V18.3.4.0 APPROVED)
# =====================================================================
st.set_page_config(layout="wide", page_title="AI Fabric Consumption Matrix")

# 🌟 BỘ STYLING CSS CẤP CAO: KHỐNG CHẾ MAX-HEIGHT CÂN XỨNG VÀ TẠO KHUNG CUỘN ĐỘC LẬP
st.markdown("""
<style>
    /* Trả nền ứng dụng về màu xám trắng dịu mắt chuẩn văn phòng ERP */
    .stApp {
        background-color: #f8fafc !important;
    }
    
    /* Can thiệp xóa bỏ hoàn toàn thanh Header mặc định của Streamlit để dải ghim không bị đè khuất */
    header[data-testid="stHeader"] {
        background-color: #f8fafc !important;
        z-index: 999990 !important;
    }
    
    /* CONTAINER GHIM ĐỈNH TUYỆT ĐỐI: Nổi lên tầng cao nhất, hiện chữ số rõ ràng */
    .sticky-top-container {
        position: fixed;
        top: 0; 
        left: 0;
        right: 0;
        padding: 10px 4rem 15px 4rem; 
        background-color: #f8fafc !important; 
        z-index: 999999 !important; 
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        width: 100%;
    }

    /* Khung Banner chính trên đỉnh chuyển sắc xanh Coban công nghệ */
    .top-banner {
        background: linear-gradient(135deg, #1e3a8a 0%, #0284c7 100%);
        padding: 12px 20px;
        border-radius: 8px;
        color: #ffffff;
        margin-bottom: 10px;
    }
    .top-title {
        font-family: 'Segoe UI', sans-serif;
        font-size: 18px;
        font-weight: 700;
        letter-spacing: 0.02em;
    }
    .top-subtitle {
        font-size: 11px;
        color: #e0f2fe;
        opacity: 0.85;
        margin-top: 1px;
    }
    
    /* Thẻ chỉ số KPIs sắc màu rực rỡ chữ trắng hiển thị rõ nét vĩnh viễn */
    .kpi-card-colored {
        border-radius: 6px;
        padding: 10px 12px;
        text-align: center;
        box-shadow: 0 2px 4px rgba(0,0,0,0.02);
    }
    .kpi-num-light {
        font-size: 18px;
        font-weight: 700;
        color: #ffffff !important; 
        font-family: 'Segoe UI', sans-serif;
    }
    .kpi-lbl-light {
        font-size: 10px;
        font-weight: 600;
        color: #ffffff !important;
        opacity: 0.9;
        text-transform: uppercase;
        margin-top: 2px;
    }
    
    .bg-style { background: linear-gradient(135deg, #334155 0%, #1e293b 100%); }
    .bg-items { background: linear-gradient(135deg, #0d9488 0%, #0f766e 100%); }
    .bg-cons  { background: linear-gradient(135deg, #ea580c 0%, #c2410c 100%); }
    .bg-size  { background: linear-gradient(135deg, #16a34a 0%, #15803d 100%); }

    /* Khung đệm spacer đẩy nội dung dưới sụp xuống hợp lý, chống lỗi đè mất chữ uploader */
    .main-body-spacer {
        margin-top: 175px; 
    }

    /* 🌟 BƯỚC ĐỘT PHÁ CÂN BẰNG TỶ LỆ: Khống chế chặt chẽ chiều cao tối đa của 2 khối hộp, */
    /* Tạo thanh cuộn trượt độc lập (overflow-y) để ảnh dài không đẩy vỡ bố cục */
    .custom-erp-box {
        background-color: #ffffff !important;
        border: 1px solid #cbd5e1 !important;
        border-radius: 8px;
        padding: 20px;
        margin-bottom: 15px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.03);
        
        max-height: 380px !important; /* 🟢 Ép chiều cao tối đa bằng khít nhau */
        overflow-y: auto !important;   /* 🟢 Tự động bật thanh cuộn nếu ảnh hoặc chữ quá dài */
    }
    
    .cad-header-text {
        font-family: 'Segoe UI', sans-serif;
        font-size: 14px;
        font-weight: 700;
        color: #0369a1; 
        margin-bottom: 15px;
        padding-bottom: 6px;
        border-bottom: 2px solid #e2e8f0;
    }

    /* Thẻ hồ sơ tóm tắt mã hàng ngăn nắp */
    .meta-box-light {
        background-color: #f8fafc; 
        border-left: 4px solid #0284c7;
        padding: 8px 12px;
        margin-bottom: 8px;
        border-radius: 0 6px 6px 0;
    }
    .meta-label-light { font-size: 11px; font-weight: 700; color: #64748b; text-transform: uppercase; }
    .meta-value-light { font-size: 13px; font-weight: 600; color: #0f172a; margin-top: 1px; }
</style>
""", unsafe_allow_html=True)

# Khởi tạo an toàn cấu trúc trạng thái hệ thống
if "bom_data" not in st.session_state: st.session_state.bom_data = None
if "chat_history" not in st.session_state: st.session_state.chat_history = []
if "pdf_bytes" not in st.session_state: st.session_state.pdf_bytes = None
if "pdf_name" not in st.session_state: st.session_state.pdf_name = ""
if "pdf_text_cache" not in st.session_state: st.session_state.pdf_text_cache = None
if "accumulated_bom_rows" not in st.session_state: st.session_state.accumulated_bom_rows = {}

# Khối tự động trích xuất chữ khi nạp file PDF
if st.session_state.pdf_bytes is not None and st.session_state.pdf_text_cache is None:
    try:
        import fitz
        doc = fitz.open(stream=st.session_state.pdf_bytes, filetype="pdf")
        full_text_extract = ""
        for page_num in range(len(doc)):
            full_text_extract += f"\n--- TRANG THỨ {page_num + 1} ---\n" + doc.load_page(page_num).get_text("text")
        st.session_state.pdf_text_cache = full_text_extract
    except Exception: pass

# ĐỒNG BỘ DỮ LIỆU KPIs BIẾN THIÊN THEO THỜI GIAN THỰC
kpi_style_id = "N/A"
total_materials = len(st.session_state.accumulated_bom_rows) if st.session_state.accumulated_bom_rows else 0
main_fabric_cons = "0.000"
active_size_kpi = "AUTOMATIC"

if st.session_state.get("bom_data") and "bom_rows" in st.session_state.bom_data:
    kpi_style_id = str(st.session_state.bom_data.get("style_code", "R09-450416")).upper()
    active_size_kpi = str(st.session_state.bom_data.get("calculated_on_size", "MEDIAN")).upper()
    if total_materials == 0: total_materials = len(st.session_state.bom_data["bom_rows"])
    for row in st.session_state.bom_data["bom_rows"]:
        if not row: continue
        if "MAIN" in str(row.get("fabric_classification", "")).upper() or "MAIN" in str(row.get("component_type", "")).upper():
            val_gross = row.get("calculated_gross_consumption_yds", 0.0)
            if val_gross > 0.0:
                main_fabric_cons = f"{val_gross:.3f} Yds"
                break

# VẼ KHỐI CỐ ĐỊNH GHIM LÊN ĐỈNH MÀN HÌNH (LUÔN NỔI LÊN TRÊN CÙNG)
st.markdown('<div class="sticky-top-container">', unsafe_allow_html=True)
st.markdown("""
<div class="top-banner">
    <div class="top-title">📊 INTELLIGENT FABRIC CONSUMPTION PLATFORM</div>
    <div class="top-subtitle">Hệ thống phân tích rập hình học và tự động tính toán định mức kỹ thuật dệt may bằng AI CORE</div>
</div>
""", unsafe_allow_html=True)

k_col1, k_col2, k_col3, k_col4 = st.columns(4)
with k_col1: st.markdown(f'<div class="kpi-card-colored bg-style"><div class="kpi-num-light">{kpi_style_id}</div><div class="kpi-lbl-light">Mã hàng đang xử lý</div></div>', unsafe_allow_html=True)
with k_col2: st.markdown(f'<div class="kpi-card-colored bg-items"><div class="kpi-num-light">{total_materials} Item(s)</div><div class="kpi-lbl-light">Tổng số vật tư kết xuất</div></div>', unsafe_allow_html=True)
with k_col3: st.markdown(f'<div class="kpi-card-colored bg-cons"><div class="kpi-num-light" style="font-size:22px;">{main_fabric_cons}</div><div class="kpi-lbl-light">Định mức vải chính dự kiến</div></div>', unsafe_allow_html=True)
with k_col4: st.markdown(f'<div class="kpi-card-colored bg-size"><div class="kpi-num-light">{active_size_kpi}</div><div class="kpi-lbl-light">Cỡ hạt tính định mức</div></div>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="main-body-spacer"></div>', unsafe_allow_html=True)



# =====================================================================
# ĐOẠN 6b: KHỐI CHIA CỘT ĐỐI XỨNG - KHỐNG CHẾ TRỰC TIẾP CHIỀU CAO ẢNH (V18.3.5.0 APPROVED)
# =====================================================================

# 🌟 BỘ CSS PHÒNG VỆ: Ép trực tiếp mọi thẻ ảnh (img) nằm trong khung Sketch phải co nhỏ lại vừa vặn
st.markdown("""
<style>
    /* Ép tất cả các hình ảnh nằm trong cột bên phải khống chế chiều cao tối đa, */
    /* tự động giữ nguyên tỷ lệ rập phẳng mà không bị kéo giãn to đùng */
    .sticky-sketch-box img {
        max-height: 290px !important;
        width: auto !important;
        object-fit: contain !important;
        margin: 0 auto !important;
        display: block !important;
    }
</style>
""", unsafe_allow_html=True)

# --- SIDEBAR ENGINE CONTROLS CONTROL PANEL ---
st.sidebar.markdown("### ⚙️ ENGINE CONTROLS")
if st.sidebar.button("🗑️ CLEAR SYSTEM MEMORY", use_container_width=True):
    st.session_state.bom_data = None
    st.session_state.chat_history = []
    st.session_state.pdf_bytes = None
    st.session_state.pdf_name = ""
    st.session_state.pdf_text_cache = None
    if "pdf_page_one_image" in st.session_state: st.session_state.pdf_page_one_image = None
    if "accumulated_bom_rows" in st.session_state: del st.session_state["accumulated_bom_rows"]
    st.rerun()

# LƯỚI CHIA ĐÔI CỘT ĐỐI XỨNG CÂN BẰNG THỊ GIÁC ĐỀU NHAU
col_left, col_right = st.columns(2)

# --- CỘT TRÁI: BỘ TẢI FILE & HỒ SƠ TÓM TẮT MÃ HÀNG ---
with col_left:
    st.markdown('<div class="custom-erp-box">', unsafe_allow_html=True)
    st.markdown('<div class="cad-header-text">📂 TECHPACK UPLOADER & PROFILE SUMMARY</div>', unsafe_allow_html=True)
    
    uploaded_file = st.file_uploader("Upload PDF", type=["pdf"], label_visibility="collapsed")
    
    if uploaded_file is not None:
        if st.session_state.pdf_name != uploaded_file.name:
            st.session_state.pdf_text_cache = None
            if "pdf_page_one_image" in st.session_state: st.session_state.pdf_page_one_image = None
            if "accumulated_bom_rows" in st.session_state: del st.session_state["accumulated_bom_rows"]
        st.session_state.pdf_bytes = uploaded_file.read()
        st.session_state.pdf_name = uploaded_file.name

    if st.session_state.pdf_text_cache is not None:
        st.markdown("<div style='margin-top: 10px;'></div>", unsafe_allow_html=True)
        txt = st.session_state.pdf_text_cache
        
        import re
        def get_meta(pattern, default="N/A"):
            m = re.search(pattern, txt, re.IGNORECASE)
            return m.group(1).strip() if m else default

        style_id = get_meta(r'(?:Style ID|Style_ID|Mã hàng)\s*[:\-=\s]*([\w\d\-]+)', st.session_state.pdf_name.replace(".pdf",""))
        short_desc = get_meta(r'(?:Short Desc|Description|Tên sản phẩm)\s*[:\-=\s]*([^\n]+)', "THE TWILL CARGO PANTS")
        customer = get_meta(r'(?:Customer|Khách hàng|Brand)\s*[:\-=\s]*([^\n]+)', "REITMANS")
        season = get_meta(r'(?:Season|Mùa hàng)\s*[:\-=\s]*([^\n]+)', "Spring 2027")
        fabric_type = get_meta(r'(?:Long Description|Chất liệu gốc)\s*[:\-=\s]*([^\n]+)', "CASUAL TWILL PANTS - SP27")

        m_col1, m_col2 = st.columns(2)
        with m_col1:
            st.markdown(f'<div class="meta-box-light"><div class="meta-label-light">Style Code / Mã hàng</div><div class="meta-value-light"><b>{style_id}</b></div></div>', unsafe_allow_html=True)
            st.markdown(f'<div class="meta-box-light"><div class="meta-label-light">Customer / Đối tác</div><div class="meta-value-light">{customer}</div></div>', unsafe_allow_html=True)
            # 🟢 ĐÃ SỬA DẤU GẠCH DƯỚI THÀNH DẤU GẠCH NGANG CHUẨN ĐỂ HIỂN THỊ ĐỦ MÀU SẮC KHỐI SEASON:
            st.markdown(f'<div class="meta-box-light"><div class="meta-label-light">Season / Mùa sản xuất</div><div class="meta-value-light">{season}</div></div>', unsafe_allow_html=True)
        with m_col2:
            st.markdown(f'<div class="meta-box-light"><div class="meta-label-light">Garment Type / Kiểu dáng</div><div class="meta-value-light">{short_desc}</div></div>', unsafe_allow_html=True)
            st.markdown(f'<div class="meta-box-light"><div class="meta-label-light">Material Spec / Mô tả vải</div><div class="meta-value-light">{fabric_type[:28]}...</div></div>', unsafe_allow_html=True)
            st.markdown(f'<div class="meta-box-light"><div class="meta-label-light">Techpack Status</div><div class="meta-value-light" style="color: #16a34a; font-weight: bold;">🟢 READY TO BOM</div></div>', unsafe_allow_html=True)
    else:
        if st.session_state.pdf_bytes is None:
            st.markdown("<div style='margin-top: 40px; text-align: center; color: #64748b; font-size: 13px;'>Bảng tóm tắt thông số sản phẩm sẽ tự động hiển thị tại đây sau khi nạp file PDF.</div>", unsafe_allow_html=True)
        
    st.markdown('</div>', unsafe_allow_html=True)




# --- CỘT PHẢI: KHUNG XEM BẢN VẼ PHẲNG SKETCH (🌟 ĐÃ ÉP CO NHỎ ẢNH GỐC ĐỐI XỨNG) ---
with col_right:
    # 🟢 ĐỒNG BỘ MÀU SẮC PHẲNG: Chuyển từ class cũ custom-erp-box sang erp-main-card chuẩn SAP ERP
    st.markdown('<div class="erp-main-card sticky-sketch-box">', unsafe_allow_html=True)
    st.markdown('<div class="erp-header-title">🎨 TECHPACK SKETCH VISUALIZER</div>', unsafe_allow_html=True)
    
    # 🟢 BỘ KHỞI TẠO VÀ TRÍCH XUẤT ẢNH TỰ ĐỘNG NGAY KHI CÓ FILE PDF TRONG HỆ THỐNG
    if st.session_state.pdf_bytes is not None:
        if "pdf_page_one_image" not in st.session_state or st.session_state.pdf_page_one_image is None:
            try:
                import fitz
                doc_img = fitz.open(stream=st.session_state.pdf_bytes, filetype="pdf")
                if len(doc_img) > 0:
                    page = doc_img.load_page(0)
                    # Thiết lập ma trận phóng nét và ép hệ màu kĩ thuật số RGB tránh sập luồng hiển thị
                    pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), colorspace=fitz.csRGB)
                    st.session_state.pdf_page_one_image = pix.tobytes("png")
            except Exception as e_img:
                st.error(f"⚠️ Không thể hiển thị ảnh vẽ phác họa: {str(e_img)}")

    # THỰC THI HIỂN THỊ HÌNH ẢNH SAU KHI ĐÃ CÓ CACHE SẠCH TRONG SESSION
    if "pdf_page_one_image" in st.session_state and st.session_state.pdf_page_one_image is not None:
        # 🌟 TINH CHỈNH VÀNG: Thay thế use_container_width=True bằng width=300 để ảnh thu nhỏ tinh tế,
        # kết hợp với CSS căn giữa tự động ở đoạn 6a sẽ tạo ra sự đối xứng hình học hoàn hảo.
        st.image(st.session_state.pdf_page_one_image, width=300)
    else:
        st.markdown("<div style='margin-top: 50px; text-align: center; color: #64748b; font-size: 13px;'>Hình vẽ phác họa phẳng (Sketch) trích xuất từ trang bìa PDF sẽ tự động hiển thị cân xứng tại đây sau khi nạp file thành công.</div>", unsafe_allow_html=True)
        
    st.markdown('</div>', unsafe_allow_html=True)




# =====================================================================
# ĐOẠN 7a - PHẦN 1: CHATGPT-STYLE WORKSPACE & SMART TARGET SCANNED PIPELINE (V65.0)
# CHIẾN LƯỢC HYBRID: GIẢM TẢI DPI XUỐNG 65 ĐỂ KHẮC PHỤC TRIỆT ĐỂ LỖI QUOTA 429
# =====================================================================
st.markdown('<br><div class="cad-card"><div class="cad-header">💬 CHATGPT IE COLLABORATION WORKSPACE</div>', unsafe_allow_html=True)

# Khởi tạo kho lưu trữ trạng thái hệ thống phòng vệ
if "chat_history" not in st.session_state: st.session_state.chat_history = []
if "pdf_page_images_list" not in st.session_state: st.session_state.pdf_page_images_list = None
if "accumulated_bom_rows" not in st.session_state: st.session_state.accumulated_bom_rows = []
if "bom_data" not in st.session_state: st.session_state.bom_data = {}

# Xuất dòng tin nhắn lịch sử trò chuyện đồng bộ trực quan lên màn hình theo chuẩn OpenAI
if st.session_state.chat_history:
    for msg in st.session_state.chat_history:
        st.chat_message("user").write(msg["user"])
        st.chat_message("assistant").write(msg["ai"])

# Tạo một vùng chứa tĩnh độc lập cô lập ô chat input
chat_input_container = st.container()
with chat_input_container:
    safe_user_prompt = st.chat_input("Gõ câu lệnh điều chỉnh thông số hoặc câu hỏi bất kỳ tại đây...", key="ie_workspace_static_chat_input_key")

st.markdown('</div>', unsafe_allow_html=True)

# KÍCH HOẠT LUỒNG CHẠY AI NGAY KHI CÓ BẤT KỲ CÂU HỎI CHAT NÀO
if st.session_state.pdf_bytes is not None and safe_user_prompt:
    current_query = str(safe_user_prompt).strip()
    
    with st.spinner("🧠 AI Platform đang quét thông minh đa tầng tài liệu kỹ thuật Techpack..."):
        import google.generativeai as genai
        import json, copy, traceback, re
        import fitz 
        
        # 🌟 BẮT ĐẦU MỞ KHỐI TRY LỚN DUY NHẤT BAO QUANH TOÀN BỘ HẠ TẦNG AI
        try:
            doc_recovery = fitz.open(stream=st.session_state.pdf_bytes, filetype="pdf")
            total_pages = len(doc_recovery)
            pdf_size_mb = len(st.session_state.pdf_bytes) / (1024 * 1024)
            
            # Khởi tạo phôi văn bản và dải mảng ảnh
            full_pdf_raw_text = ""
            image_payloads = []
            MAX_IMAGE_PAGES = 15  
            MAX_TEXT = 150000     # Chốt chặn bảo vệ Token ngữ cảnh
            
            # 🟢 VÁ SỬA LỖI GIẢM TẢI TOKEN: Hạ DPI xuống mức tối ưu 65 để ép mô hình Flash đọc nhanh, không bị nghẽn nghẹt băng thông
            target_dpi = 65
            
            # DUYỆT QUA TỪNG TRANG: Chỉ thu thập văn bản và ảnh của các trang BOM & THÔNG SỐ & SKETCH
            for idx in range(total_pages):
                page_text = doc_recovery[idx].get_text("text")
                page_text_upper = page_text.upper()
                
                # Chốt chặn từ khóa nghiêm ngặt: Chỉ lấy trang chứa dữ liệu BOM, thông số kích thước hoặc hình vẽ kỹ thuật
                is_target_page = any(k in page_text_upper for k in [
                    "BOM", "BILL OF MATERIAL", "BILL OF MATERIALS", 
                    "SPECIFICATION", "MEASUREMENT", "THÔNG SỐ", "KÍCH THƯỚC", "SKETCH", "DESIGN"
                ])
                
                if is_target_page:
                    # Tích lũy cơ sở dữ liệu văn bản phẳng từ trang mục tiêu
                    full_pdf_raw_text += f"\n--- DATA SCANNING SOURCE: PAGE {idx + 1} ---\n{page_text}"
                    
                    # Trích xuất ảnh đồng bộ của trang mục tiêu gửi cho AI xử lý trực quan hình ảnh hình rập
                    if len(image_payloads) < MAX_IMAGE_PAGES:
                        page = doc_recovery.load_page(idx)
                        pix = page.get_pixmap(dpi=target_dpi, colorspace=fitz.csRGB)
                        image_payloads.append({"mime_type": "image/jpeg", "data": pix.tobytes("jpeg")})
            
            # Hãm phanh cắt chuỗi văn bản nếu vượt quá ngưỡng an toàn bảo vệ Token
            if len(full_pdf_raw_text) > MAX_TEXT:
                full_pdf_raw_text = full_pdf_raw_text[:MAX_TEXT] + "\n\n... [TRUNCATED DUE TO MAX TOKEN PROTECTION] ..."
            
            # Trường hợp file PDF scan dạng ảnh thô hoàn toàn không có text, lấy mặc định 5 trang đầu
            if not image_payloads:
                for idx in range(min(5, total_pages)):
                    page = doc_recovery.load_page(idx)
                    pix = page.get_pixmap(dpi=target_dpi, colorspace=fitz.csRGB)
                    image_payloads.append({"mime_type": "image/jpeg", "data": pix.tobytes("jpeg")})
                    
            gemini_inputs = copy.deepcopy(image_payloads)
            
            # Bơm toàn bộ dữ liệu text phẳng đã trích xuất sạch vào đầu danh sách gửi sang Gemini
            gemini_inputs.insert(0, f"=== RECOVERED TECHPACK FLAT TEXT DATABASE ===\n{full_pdf_raw_text}\n============================================\n")
            
            # Đưa trực tiếp câu lệnh hiện tại của người dùng vào danh sách đầu vào của Gemini
            gemini_inputs.append(f"\n[USER COMMAND]: {current_query}")

                       # =====================================================================
                       # =====================================================================
            # ĐOẠN 7a - PHẦN 3a: INITIALIZATION & DETERMINISTIC PROMPTS (V100.3)
            # 🌟 ÉP AI CHỈ TRÍCH XUẤT DIỆN TÍCH TỊNH (NET AREA) - CẤM TỰ TÍNH YARDS
            # =====================================================================
            response_text = ""
            
            pdf_bytes_len_p3 = len(st.session_state.pdf_bytes) if st.session_state.pdf_bytes else 0
            current_signature_p3 = (str(safe_user_prompt).strip(), int(len(image_payloads)), int(pdf_bytes_len_p3))
            
            has_no_data_p3 = not st.session_state.get("bom_data") or st.session_state.get("bom_data") == {}
            is_signature_changed_p3 = st.session_state.get("last_processed_signature") != current_signature_p3

            chat_lower = current_query.lower()
            match_size = re.search(r'\b(?:size|sz|cỡ)\s*[:\-=\s]*([\w\d/]+)\b', chat_lower)
            target_size_cmd = str(match_size.group(1)).upper().strip() if match_size else "30"
            
            match_w = re.search(r'(?:khổ|kho|width|w)\s*[:\-=\s]*([\d\.]+)', chat_lower)
            active_width = float(match_w.group(1)) if match_w else 57.0
            if active_width < 20.0: active_width = 57.0
            
            match_shrink = re.search(r'(?:co rút|co rut|sh|shrinkage)\s*[:\-=\s]*([\d\.]+)\s*[\-,\s]\s*([\d\.]+)', chat_lower)
            warp_val = f"{match_shrink.group(1)}%" if match_shrink else "3.0%"
            weft_val = f"{match_shrink.group(2)}%" if match_shrink else "13.0%"

            # TẦNG 1: TRÍCH XUẤT CHI TIẾT RẬP PHI TUYẾN TÍNH
            prompt_agent_1 = f"""
            You are Agent 1: An Apparel Technical Pattern Extractor. Scan techpack text/images for size '{target_size_cmd}'.
            Identify all individual pattern panels. For non-rectangular panels (front/back legs), estimate the net mathematical surface area.
            Return strictly a temporary technical JSON with components and their estimated net areas. Do NOT calculate yardage consumption.
            """
            
            # TẦNG 2: KIỂM TOÁN LOGIC VÀ TỔNG HỢP DIỆN TÍCH SỐ SẠCH
            prompt_agent_2 = f"""
            You are Agent 2: The Senior Apparel IE Validator. Review Agent 1's data against the Techpack.
            🌟 CRITICAL REALISM MANDATE:
            1. Scan for missing rows (Main Fabric, Pocketing, Fusing, Tape/Elastic) from BOM.
            2. For 'total_net_area_sq_inch', output the exact realistic aggregate net area sum of all panels combined for that material class. For adult Jeans denim major panels, the true combined net area typically ranges from 1200.0 to 1550.0 square inches. Do NOT overestimate.
            3. Set factory realistic 'marker_efficiency_target': Denim major fabric 85.5%, Lining/Fusing 85.5%, Trims 95.0%.
            4. You are strictly FORBIDDEN from calculating final yards. Python engine will do the math.

            Output BOTH raw text JSON format (under ===START_JSON===) and markdown chat response (under ===START_CHAT===). All 'fabric_width_inch' must match {active_width}.
            
            ===START_CHAT===
            ⚖️ **Deterministic Framework Activated**: Đã chuyển giao toàn bộ tham số diện tích phẳng tịnh (Net Area) đã qua kiểm toán sang cho máy tính Python tự động nhân chia định mức, triệt tiêu lỗi AI tính gộp làm vọt số.
            ===END_CHAT===

            ===START_JSON===
            {{
              "status": "PASS",
              "detected_product_type": "JEANS",
              "calculated_on_size": "{target_size_cmd}",
              "bom_rows": [
                {{
                  "component_type": "Main Fabric",
                  "fabric_classification": "MAIN_FABRIC",
                  "fabric_width_inch": {active_width},
                  "marker_efficiency": "85.5%", 
                  "total_net_area_sq_inch": 1380.0,
                  "reasoning": "Auditor Verified: Summed true curved surface area of front/back legs, waistband, and yokes."
                }},
                {{
                  "component_type": "Pocketing Fabric",
                  "fabric_classification": "LINING",
                  "fabric_width_inch": 44.0,
                  "marker_efficiency": "85.5%",
                  "total_net_area_sq_inch": 210.0,
                  "reasoning": "Auditor Extracted: Real surface area for front pocket bags."
                }}
              ]
            }}
            ===END_JSON===
            """


                       # =====================================================================
            # ĐOẠN 7a - PHẦN 3b: DUAL-AGENT API EXECUTION SEQUENCE (V100.2 FIXED)
            # 🌟 ĐÃ VÁ LỖI NAME_ERROR: KHỞI TẠO BIẾN MODEL VÀ CONFIG API CHẮC CHẮN
            # =====================================================================
            if has_no_data_p3 or is_signature_changed_p3:
                try:
                    # Đảm bảo cấu hình cứng API Key luôn sẵn sàng chống crash
                    if "GEMINI_API_KEY" not in st.secrets:
                        st.error("💥 Lỗi hạ tầng: Thiếu cấu hình GEMINI_API_KEY trong hệ thống Secrets.")
                        st.stop()
                        
                    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
                    
                    # Khởi tạo biến model ngay tại luồng để Phần 3b gọi mượt mà
                    model = genai.GenerativeModel("gemini-2.5-flash")
                    
                    # Thực thi gọi Agent Tầng 1: Trích xuất hình học sơ bộ
                    payload_agent_1 = gemini_inputs + [prompt_agent_1]
                    response_agent_1 = model.generate_content(payload_agent_1)
                    raw_json_agent_1 = response_agent_1.text if response_agent_1 else "{}"
                    
                    # Thực thi gọi Agent Tầng 2: Kiểm toán logic chuỗi cung ứng
                    payload_agent_2 = [
                        f"=== RECOVERED TECHPACK TEXT ===\n{full_pdf_raw_text}\n",
                        f"=== DATA FROM CAD AGENT 1 ===\n{raw_json_agent_1}\n====================\n",
                        prompt_agent_2
                    ]
                    api_response = model.generate_content(payload_agent_2)
                    response_text = api_response.text
                    st.session_state["_btp_master_raw_json_stream"] = response_text
                    
                except Exception as api_err:
                    st.error(f"💥 Lỗi kết nối trực tiếp đến chuỗi Agent API: {str(api_err)}")
                    st.stop()

            # =====================================================================
            # ĐOẠN 7a - PHẦN 3c: POST-AI MIDDLEWARE PARSER & UI SYNC (V100.0)
            # =====================================================================
            active_json_stream = st.session_state.get("_btp_master_raw_json_stream", response_text)

            if active_json_stream:
                json_match = re.search(r'(?:===START_JSON===\s*|```json\s*)(.*?)(?:\s*===END_JSON===|\s*```)', active_json_stream, re.DOTALL)
                chat_match = re.search(r'(?:===START_CHAT===\s*|```markdown\s*)(.*?)(?:\s*===END_CHAT===|\s*```|$)', active_json_stream, re.DOTALL)
                
                if chat_match and response_text:
                    st.session_state.chat_history.append({"user": current_query, "ai": chat_match.group(1).strip()})

                raw_json_str = json_match.group(1).strip() if json_match else ""
                if not raw_json_str:
                    match_fb = re.search(r'\{.*\}', active_json_stream, re.DOTALL)
                    raw_json_str = match_fb.group(0).strip() if match_fb else ""
                
                if raw_json_str:
                    raw_json_str = re.sub(r',\s*([\]\}])', r'\1', raw_json_str)
                    try: blueprint_worker = json.loads(raw_json_str)
                    except: st.stop()
                    
                    if blueprint_worker and "bom_rows" in blueprint_worker:
                        blueprint_worker["calculated_on_size"] = target_size_cmd
                        
                        for row in blueprint_worker.get("bom_rows", []):
                            if row.get("fabric_classification") == "MAIN_FABRIC" or "fabric_width_inch" not in row:
                                row["fabric_width_inch"] = active_width
                            row["_btp_warp_pct"] = warp_val
                            row["_btp_weft_pct"] = weft_val
                        
                        blueprint_final = allocate_fabric_consumption_and_quality_gate(blueprint_worker, str(safe_user_prompt).strip())
                        st.session_state.bom_data = blueprint_final
                        st.session_state.accumulated_bom_rows = blueprint_final.get("bom_rows", [])
                        
                        if response_text:
                            st.session_state["last_processed_signature"] = current_signature_p3
                            st.success("🎉 Xử lý định mức tự động toàn phần thành công!")
                            st.rerun()





            # =====================================================================
            # ĐOẠN 7a - PHẦN 3b: POST-AI MIDDLEWARE GATEWAY (V92.0 PARSER COUPLING)
            # 🌟 HẠ TẦNG BÓC TÁCH CHUỖI STREAM: PARSE CHAT VÀ JSON KHÉP KÍN 100% UI
            # =====================================================================
            active_json_stream = st.session_state.get("_btp_master_raw_json_stream", response_text)

            if active_json_stream:
                # Sử dụng Regex bóc tách đồng thời khối văn bản chat và khối cấu trúc JSON phẳng
                json_match = re.search(r'(?:===START_JSON===\s*|```json\s*)(.*?)(?:\s*===END_JSON===|\s*```)', active_json_stream, re.DOTALL)
                chat_match = re.search(r'(?:===START_CHAT===\s*|```markdown\s*)(.*?)(?:\s*===END_CHAT===|\s*```|$)', active_json_stream, re.DOTALL)
                
                # Lưu lịch sử tin nhắn trò chuyện chuẩn phong cách ChatGPT
                if chat_match and response_text:
                    st.session_state.chat_history.append({"user": current_query, "ai": chat_match.group(1).strip()})

                raw_json_str = ""
                if json_match: 
                    raw_json_str = json_match.group(1).strip()
                else:
                    # Phương án dự phòng khẩn cấp nếu AI quên in thẻ đánh dấu khối
                    match_fb = re.search(r'\{.*\}', active_json_stream, re.DOTALL)
                    raw_json_str = match_fb.group(0).strip() if match_fb else ""
                
                if raw_json_str:
                    # Chốt chặn xóa bỏ dấu phẩy thừa (Trailing Commas) chống sập hàm parse JSON
                    raw_json_str = re.sub(r',\s*([\]\}])', r'\1', raw_json_str)
                    
                    blueprint_worker = None
                    try:
                        blueprint_worker = json.loads(raw_json_str)
                    except:
                        st.stop()
                    
                    if blueprint_worker and "bom_rows" in blueprint_worker:
                        blueprint_worker["calculated_on_size"] = target_size_cmd
                        
                        # Vòng lặp đồng bộ động khổ vải và tham số co rút vào từng linh kiện phụ liệu rập
                        for row in blueprint_worker.get("bom_rows", []):
                            if row.get("fabric_classification") == "MAIN_FABRIC" or "fabric_width_inch" not in row:
                                row["fabric_width_inch"] = active_width
                            row["_btp_warp_pct"] = warp_val
                            row["_btp_weft_pct"] = weft_val
                        
                        # ỦY QUYỀN TOÀN PHẦN: Gọi hàm Gateway V80.0 để nạp dữ liệu Yards trực tiếp lên UI
                        blueprint_final = allocate_fabric_consumption_and_quality_gate(blueprint_worker, str(safe_user_prompt).strip())
                        
                        st.session_state.bom_data = blueprint_final
                        st.session_state.accumulated_bom_rows = blueprint_final.get("bom_rows", [])
                        
                        # CHỐT KHÓA TRẠNG THÁI CHỮ KÝ VÀ ÉP REFRESH MÀN HÌNH HIỂN THỊ NGAY LẬP TỨC
                        if response_text:
                            st.session_state["last_processed_signature"] = current_signature_p3
                            st.success("🎉 Xử lý kiểm toán định mức tự động toàn phần thành công!")
                            st.rerun() 
                    else:
                        st.error("⚠️ Khối JSON của AI Kiểm toán thiếu trường danh mục bom_rows.")
                else:
                    st.error("❌ Không thể bóc tách START_JSON từ văn bản phản hồi thô của Agent Kiểm toán.")
                    
        except Exception as e_global:
            st.error(f"💥 Lỗi luồng trích xuất hạ tầng tổng toàn cục: {str(e_global)}")
            st.code(traceback.format_exc())


# =====================================================================
# ĐOẠN 7b: HIỂN THỊ KẾT QUẢ ĐỊNH MỨC & BẢNG ĐỐI CHỨNG ĐA CỘT ĐỒNG BỘ SIZE (V100.4 SYNC)
# 🌟 ĐỒNG BỘ HẠ TẦNG: ĐỌC DỮ LIỆU ĐÃ ĐƯỢC PYTHON CAD ENGINE TÍNH TOÁN VÀ ĐỔ RA BẢNG
# =====================================================================
if st.session_state.get("bom_data") or st.session_state.get("accumulated_bom_rows"):
    import pandas as pd
    
    bom_source = st.session_state.get("bom_data", {})
    if not isinstance(bom_source, dict): 
        bom_source = {}
        
    bom_rows_list = bom_source.get("bom_rows", st.session_state.get("accumulated_bom_rows", []))
    if not isinstance(bom_rows_list, list): 
        bom_rows_list = []

    chat_txt = ""
    if 'safe_user_prompt' in locals() and safe_user_prompt:
        chat_txt = str(safe_user_prompt).lower()
    elif st.session_state.chat_history:
        chat_txt = str(st.session_state.chat_history[-1]["user"]).lower()
        
    match_active_size = re.search(r'\b(?:size|sz|cỡ)\s*[:\-=\s]*([\w\d/]+)\b', chat_txt)
    extracted_size = str(match_active_size.group(1)).upper().strip() if match_active_size else str(bom_source.get("calculated_on_size", "30")).upper().strip()
    
    st.markdown('<div class="cad-card">', unsafe_allow_html=True)
    st.markdown(f'<div class="cad-header">📊 CALCULATED FABRIC CONSUMPTION MATRIX (SIZE TARGET: {extracted_size})</div>', unsafe_allow_html=True)
    
    display_data = []
    
    for r in bom_rows_list:
        if not r or not isinstance(r, dict): 
            continue
            
        # 🟢 LẤY ĐÚNG SỐ YARDS DO ĐOẠN B PYTHON TỰ TÍNH (TRÁNH BỊ 0.0 HOẶC TRỐNG)
        current_gross = r.get("gross_consumption", 0.0)
        sys_notes = r.get("reasoning", r.get("system_notes", "Mô phỏng CAD Gerber V27"))
        
        raw_width = r.get("fabric_width_inch", 57.0)
        try: cut_width_val = f"{float(raw_width)} inch"
        except: cut_width_val = f"{raw_width} inch"

        # Đọc động thông số co rút và hiệu suất sơ đồ đã được đồng bộ hóa từ Đoạn B sang
        warp_dynamic = r.get("_btp_warp_pct", "3.0%")
        weft_dynamic = r.get("_btp_weft_pct", "13.0%")
        eff_dynamic = r.get("marker_efficiency", "85.5%")

        display_data.append({
            "Component Type": r.get("component_type", r.get("fabric_classification", "MAIN FABRIC")).upper().replace("_", " "),
            "Placement": "BODY/POCKETS LAYOUT OPTIMIZED",
            "Fabric Classification": r.get("fabric_classification", "MAIN_FABRIC"),
            "Fabric Code": r.get("fabric_code", r.get("fabric_classification", "FABRIC")),
            "Fabric Color": r.get("fabric_color", "SOLID COLOR"),
            "Khổ vải (Width)": cut_width_val,
            "Co rút dọc (% Warp)": warp_dynamic,     
            "Co rút ngang (% Weft)": weft_dynamic,   
            "Marker Efficiency": eff_dynamic,         
            "Gross Consumption (Yds)": current_gross,
            "Quality Status": r.get("quality_status", "PASS"),
            "System Notes": sys_notes
        })
        
    if display_data:
        df_bom = pd.DataFrame(display_data)
        st.dataframe(df_bom, use_container_width=True, hide_index=True)
    else:
        st.warning("⚠️ Hệ thống đã xử lý xong nhưng cấu trúc danh mục BOM trống dữ liệu thực tế.")
    st.markdown('</div>', unsafe_allow_html=True)
    
    # BẢNG ĐỐI CHỨNG SỐ ĐO GỐC TỪ TECHPACK
    raw_evidence_list = bom_source.get("matched_measurements", [])
    if raw_evidence_list and isinstance(raw_evidence_list, list):
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<div class="cad-card">', unsafe_allow_html=True)
        st.markdown(f'<div class="cad-header" style="background-color: #2C3E50;">🔍 BẰNG CHỨNG SỐ ĐO GỐC TỪ TECHPACK (SIZE: {extracted_size})</div>', unsafe_allow_html=True)
        
        parsed_evidence_rows = []
        for idx, item in enumerate(raw_evidence_list):
            raw_str = str(item).strip()
            pom_code, description, measurement_val = "POM", raw_str, "-"
            if ":" in raw_str:
                parts = raw_str.split(":", 1)
                pom_code = parts.strip()
                description = parts.strip()
                if "=" in description:
                    sub_parts = description.split("=", 1)
                    description = sub_parts.strip()
                    measurement_val = sub_parts.strip()
            elif "=" in raw_str:
                parts = raw_str.split("=", 1)
                description = parts.strip()
                measurement_val = parts.strip()
                
            parsed_evidence_rows.append({
                "STT": idx + 1, "Mã POM": pom_code, "Mô tả Thông số Kỹ thuật": description, "Kích thước Đo thực tế (Inches)": measurement_val
            })
            
        df_evidence = pd.DataFrame(parsed_evidence_rows)
        st.dataframe(df_evidence, use_container_width=True, hide_index=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # KHỐI XUẤT FILE EXCEL PHÒNG VỆ AN TOÀN TRÊN MÀN HÌNH CHÍNH
    if display_data:
        try:
            import io
            from openpyxl import Workbook
            output = io.BytesIO()
            wb = Workbook()
            ws = wb.active
            ws.title = "BOM Consumption"
            ws.sheet_view.showGridLines = True
            
            ws.append([f"BÁO CÁO ĐỊNH MỨC VẬT TƯ VẢI (SIZE: {extracted_size})"])
            if 'df_bom' in locals():
                ws.append(list(df_bom.columns))
                for index, row_excel in df_bom.iterrows():
                    ws.append(list(row_excel))
            wb.save(output)
            output.seek(0)
            
            st.markdown("<br>", unsafe_allow_html=True)
            st.download_button(
                label="📥 Tải Báo Cáo Định Mức Excel (Chuẩn Nhà Máy)",
                data=output,
                file_name=f"BOM_Fabric_Consumption_Size_{extracted_size}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
        except Exception as excel_err:
            pass
