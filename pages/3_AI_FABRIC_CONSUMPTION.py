import streamlit as st
import pandas as pd
import json
import google.generativeai as genai
from google.generativeai import types

# =====================================================================
# CẤU HÌNH TRANG VÀ KẾT NỐI API GEMINI (AI-ONLY CALCULATOR ENGINE)
# =====================================================================
st.set_page_config(page_title="AI 100% BOM CALCULATOR", layout="wide")
st.title("🤖 TRỢ LÝ ĐỊNH MỨC AI TỰ ĐỘNG TOÀN DIỆN (100% AI-DRIVEN)")
st.caption("Kiến trúc AI-Only Engine: Chỉ cần nạp file PDF, AI tự suy luận phom dáng và tự tính toán Yards xưởng")
st.markdown("---")

if "chat_history" not in st.session_state:
    st.session_state.chat_history = [{"role": "assistant", "content": "Xin chào! Bạn chỉ việc nạp file PDF Techpack lên, AI sẽ tự động bóc tách và tự tính toán định mức chuẩn xác cho toàn bộ bảng BOM."}]
if "bom_data" not in st.session_state: st.session_state.bom_data = None

if "GEMINI_API_KEY" in st.secrets: genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
elif "gemini" in st.secrets: genai.configure(api_key=st.secrets["gemini"].get("api_key", ""))

# =====================================================================
# ĐOẠN 2: BẢN VÁ LỖI CHẶN VÒNG LẶP VÔ HẠN (ANTI-LOOP ENGINE)
# =====================================================================

with st.sidebar:
    st.header("⚙️ HỆ THỐNG")
    if st.button("🗑️ Xóa lịch sử & Reset định mức", use_container_width=True):
        st.session_state.bom_data = None
        st.session_state.pdf_bytes = None
        st.session_state.pdf_name = None
        st.session_state.chat_history = [{"role": "assistant", "content": "Hệ thống đã reset sạch bộ nhớ cache. Vui lòng tải file PDF mới."}]
        st.rerun()

st.subheader("📁 BƯỚC 1: TẢI TÀI LIỆU KỸ THUẬT SẢN XUẤT (TECHPACK / BOM PDF)")
uploaded_file = st.file_uploader("Kéo và thả file PDF Techpack vào đây", type=["pdf"])
if uploaded_file is not None:
    st.session_state.pdf_bytes = uploaded_file.read()
    st.session_state.pdf_name = uploaded_file.name

chat_container = st.container(height=150)
with chat_container:
    for chat in st.session_state.get("chat_history", []):
        with st.chat_message(chat["role"]): st.markdown(chat["content"])

user_prompt = st.chat_input("Nhập thêm ghi chú cấu hình vải (khổ vải, co rút nếu có)...")

# --- ĐÃ SỬA: SỬ DỤNG NÚT BẤM KÍCH HOẠT THỦ CÔNG ĐỂ TRIỆT TIÊU LỖI NHẢY TRANG LIÊN TỤC ---
st.markdown(" ")
trigger_calc = st.button("🚀 BẮT ĐẦU CHẠY AI TÍNH ĐỊNH MỨC SẢN XUẤT", use_container_width=True, type="primary")

if (trigger_calc and "pdf_bytes" in st.session_state) or (user_prompt and "pdf_bytes" in st.session_state):
    current_prompt = user_prompt if user_prompt else "Hãy tự động bóc tách và tính toán định mức thực tế xưởng cho file này."
    if user_prompt:
        st.session_state.chat_history.append({"role": "user", "content": user_prompt})
    
    json_schema = {
        "type": "OBJECT",
        "properties": {
            "style_code": {"type": "STRING"},
            "detected_product_style": {"type": "STRING"},
            "bom_rows": {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "component_type": {"type": "STRING"},
                        "placement": {"type": "STRING"},
                        "fabric_width_inch": {"type": "STRING"},
                        "marker_efficiency": {"type": "STRING"},
                        "final_gross_consumption_yds": {"type": "NUMBER"},
                        "ai_calculation_log": {"type": "STRING"}
                    },
                    "required": ["component_type", "placement", "final_gross_consumption_yds"]
                }
            }
        },
        "required": ["detected_product_style", "bom_rows"]
    }

    master_reasoning_prompt = f"""
    Bạn là một Chuyên gia Cấp cao về Sơ đồ Rập và Kỹ sư IE (Industrial Engineer) tại xưởng may mặc công nghiệp quy mô lớn.
    Nhiệm vụ của bạn: Đọc toàn bộ file PDF Techpack được cung cấp, tự suy luận, tự phân tích cấu trúc hình học rập và TỰ TÍNH TOÁN định mức Yards thực tế cuối cùng (Gross Consumption) cho từng dòng nguyên phụ liệu.
    
    QUY TẮC SUY LUẬN VÀ TOÁN HỌC CỦA AI:
    1. NHẬN DIỆN PHOM DÁNG & SPEC ẨN: Hãy đọc bảng POM/Spec kích thước. Tự xác định chính xác kiểu đồ (Ví dụ: Nếu thấy từ 'Capri' hoặc chiều dài quần lửng, hãy tự biết đây là quần ngố Capri nữ; nếu thấy 'Jort' hay 'Short' là quần đùi ngắn). Nếu Techpack bị thiếu hoặc để trống thông số chiều dài Outseam, bạn phải tự suy luận ra chiều dài vật lý chuẩn của phom đồ đó (Ví dụ: Quần ngố Capri dài ~30-31 inch, quần dài ~39-40 inch, quần đùi shorts ~13-16 inch).
    2. TOÁN HỌC VẢI THÂN CHÍNH (Main Fabric / Shell / Denim): Sử dụng thông số kích thước phẳng của sản phẩm, tự nhân đôi thân trước/thân sau, tự bù thêm lượng dư đường may, tự nhân hệ số co rút dọc và ngang (Nếu PDF dính co rút lớn như Denim 5x10% thì phải nhân bù tương ứng). Tự áp hiệu suất sơ đồ mục tiêu của xưởng (Quần thường đạt 86-88%, Áo khoác đạt 84-86%) để tính ra Yards thô. Nhóm quần ngố Capri dứt điểm ép định mức tổng về khoảng 1.09 - 1.13 yds.
    3. CƠ CHẾ CỘNG DỒN CHI TIẾT PHỐI VẢI CHÍNH (SELF Component): Hãy quét kỹ bảng BOM. Nếu phát hiện các dòng chi tiết phụ như túi (Pocketing) hoặc dây luồn lưng (Drawstrings) ghi rõ dùng vải "SELF" hoặc cắt từ vải chính, bạn phải TỰ TÍNH DIỆN TÍCH các cấu kiện rập phụ đó và CỘNG DỒN THẲNG LƯỢNG TIÊU HAO VÀO DÒNG VẢI THÂN CHÍNH LỚN. Ở dòng chi tiết phối đó, ghi định mức bằng 0 và ghi chú rõ 'Included in Main'.
    4. VẢI LÓT & KEO DỰNG (Pocketing Fabric / Interlining): Nếu lót túi là vải lót chuyên dụng độc lập, tự tính riêng (Quần short/ngố ~0.15 yds, quần dài ~0.25 yds). Nếu là keo dựng (Interlining/Fusing) cho quần ngố/quần dài, tự gán đúng mức ép keo lưng quần là 0.10 yds (Tuyệt đối không áp nhầm mức 0.65 yds của áo khoác). Hiệu suất sơ đồ của keo gán chữ 'N/A'.
    5. Gạt bỏ hoàn toàn chỉ may và dây kéo zipper cứng khỏi bảng kết quả Yards phẳng.
    
    Yêu cầu bổ sung của người dùng (nếu có): {current_prompt}
    """

    with st.spinner("Hệ thống AI đang tự đọc tài liệu, phân rã chi tiết rập và tự tính định mức Yards..."):
        try:
            pdf_blob = {"mime_type": "application/pdf", "data": st.session_state.pdf_bytes}
            model = genai.GenerativeModel('gemini-2.5-flash')
            response = model.generate_content(
                [pdf_blob, master_reasoning_prompt],
                generation_config=types.GenerationConfig(response_mime_type="application/json", response_schema=json_schema, temperature=0.1)
            )
            st.session_state.bom_data = json.loads(response.text.strip())
            st.session_state.chat_history.append({"role": "assistant", "content": f"✅ Đã xử lý xong file `{st.session_state.pdf_name}`. AI đã tự tính toán xong định mức Yards."})
        except Exception as e:
            # ĐÃ SỬA: Lưu thông tin lỗi thô ra ô chat để ngắt luồng st.rerun(), giải phóng tình trạng đứng đơ màn hình
            st.session_state.chat_history.append({"role": "assistant", "content": f"❌ Lỗi API Google (Vượt quá giới hạn miễn phí): {str(e)}. Vui lòng chờ 1 phút hoặc đổi sang API Key trả phí (Pay-as-you-go)."})
    st.rerun()

# =====================================================================
# HIỂN THỊ BẢNG KẾT QUẢ PHẲNG DO AI TỰ ĐỔ SỐ
# =====================================================================
if st.session_state.bom_data:
    st.markdown(f"### 📋 BẢNG ĐỊNH MỨC AI TỰ TÍNH TOÁN (Phom dáng nhận diện: `{st.session_state.bom_data.get('detected_product_style')}` )")
    
    flat_rows = []
    for r in st.session_state.bom_data["bom_rows"]:
        display_yds = r.get("final_gross_consumption_yds")
        if display_yds == 0 and any(k in str(r.get("ai_calculation_log")).upper() for k in ["INCLUDED", "CỘNG DỒN", "MAIN"]):
            display_yds = "Included in Main"
            
        flat_rows.append({
            "Loại nguyên liệu (Component)": r.get("component_type"),
            "Vị trí sử dụng (Placement)": r.get("placement"),
            "Khổ vải": r.get("fabric_width_inch", "N/A"),
            "Hiệu suất sơ đồ": r.get("marker_efficiency", "N/A"),
            "Định mức Yards Gross (AI Calc)": display_yds,
            "Nhật ký Nhật giải toán học của AI": r.get("ai_calculation_log")
        })
    st.dataframe(pd.DataFrame(flat_rows), use_container_width=True)
