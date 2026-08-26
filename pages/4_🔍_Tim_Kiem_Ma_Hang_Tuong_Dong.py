import streamlit as st
from supabase import create_client, Client
import requests
from PIL import Image
import io

# 1. Cấu hình giao diện Streamlit
st.set_page_config(page_title="Tìm kiếm mã hàng tương đồng", page_icon="🔍", layout="wide")
st.title("🔍 HỆ THỐNG TÌM KIẾM MÃ HÀNG TƯƠNG ĐỒNG QUA SKETCH")

# 2. Kết nối tới cơ sở dữ liệu Supabase
SUPABASE_URL = "https://ewqqodsfvlvnrzsylawy.supabase.co"  # Thay bằng URL dự án của bạn
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImV3cXFvZHNmdmx2bnJ6c3lsYXd5Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzUxMTkyOTAsImV4cCI6MjA5MDY5NTI5MH0.BWPxOsyswBT5CLrZgluRC1F2x5EpU06oexUFyakGhyc"          # Thay bằng Anon Key của bạn
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# 3. Cấu hình Hugging Face API (Sử dụng mô hình CLIP xử lý ảnh/sketch miễn phí)
# Bạn có thể lấy Token miễn phí tại: https://huggingface.co
HF_TOKEN = "YOUR_HUGGINGFACE_API_TOKEN" 
API_URL = "https://huggingface.co"
headers = {"Authorization": f"Bearer {HF_TOKEN}"}

def get_image_embedding_via_api(image_bytes):
    """Gửi ảnh qua API Hugging Face để lấy chuỗi số Vector nhanh gọn"""
    response = requests.post(API_URL, headers=headers, data=image_bytes)
    if response.status_code == 200:
        # Kết quả trả về là một mảng vector số
        return response.json()
    else:
        raise Exception(f"Lỗi kết nối AI API: {response.text}")

# 4. Giao diện người dùng trên App
uploaded_file = st.file_uploader("Tải lên hình ảnh Sketch / Phác thảo của bạn", type=["png", "jpg", "jpeg"])

if uploaded_file is not None:
    st.image(uploaded_file, caption="Ảnh Sketch đã tải lên", width=300)
    
    if st.button("Bắt đầu tìm kiếm mã hàng"):
        with st.spinner("Đang gửi ảnh tới AI xử lý..."):
            try:
                img_bytes = uploaded_file.getvalue()
                
                # Gọi API để lấy Vector (Chỉ mất 0.5 giây thay vì load cả model nặng)
                sketch_embedding = get_image_embedding_via_api(img_bytes)
                
                # Đối chiếu dữ liệu trên Supabase
                response = supabase.rpc("match_products", {
                    "query_embedding": sketch_embedding,
                    "match_threshold": 0.5,
                    "match_count": 4
                }).execute()
                
                if response.data:
                    st.success("Đã tìm thấy các mã hàng tương đồng!")
                    cols = st.columns(len(response.data))
                    for idx, item in enumerate(response.data):
                        with cols[idx]:
                            st.metric(label="Độ tương đồng", value=f"{item['similarity']*100:.2f}%")
                            st.subheader(f"Mã: {item['product_code']}")
                            if item.get('image_url'):
                                st.image(item['image_url'], use_container_width=True)
                else:
                    st.warning("Không tìm thấy mã hàng nào phù hợp.")
                    
            except Exception as e:
                st.error(f"Lỗi: {e}")
