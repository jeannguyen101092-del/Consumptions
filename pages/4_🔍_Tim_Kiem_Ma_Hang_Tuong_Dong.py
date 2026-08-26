import streamlit as st
from supabase import create_client, Client
import requests
from PIL import Image
import torch
from transformers import CLIPProcessor, CLIPModel
import io

# 1. Cấu hình giao diện Streamlit
st.set_page_config(page_title="Tìm kiếm mã hàng tương đồng", page_icon="🔍", layout="wide")
st.title("🔍 HỆ THỐNG TÌM KIẾM MÃ HÀNG TƯƠNG ĐỒNG QUA SKETCH")

# 2. Kết nối tới cơ sở dữ liệu Supabase
SUPABASE_URL = "https://ewqqodsfvlvnrzsylawy.supabase.co"  # Thay bằng URL dự án của bạn
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImV3cXFvZHNmdmx2bnJ6c3lsYXd5Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzUxMTkyOTAsImV4cCI6MjA5MDY5NTI5MH0.BWPxOsyswBT5CLrZgluRC1F2x5EpU06oexUFyakGhyc"          # Thay bằng Anon Key của bạn
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# 3. Tải mô hình AI xử lý hình ảnh (CLIP của OpenAI)
@st.cache_resource
def load_ai_model():
    # Sử dụng mô hình chuyên xử lý độ tương đồng giữa các dạng ảnh
    model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
    processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
    return model, processor

model, processor = load_ai_model()

def get_image_embedding(image_bytes):
    """Hàm chuyển đổi ảnh sang Vector số (Embedding)"""
    image = Image.open(io.BytesIO(image_bytes))
    inputs = processor(images=image, return_tensors="pt")
    with torch.no_grad():
        image_features = model.get_image_features(**inputs)
    # Chuyển dữ liệu vector về dạng danh sách số (list) thông thường
    return image_features.squeeze().tolist()

# 4. Giao diện người dùng trên App
uploaded_file = st.file_uploader("Tải lên hình ảnh Sketch / Phác thảo của bạn", type=["png", "jpg", "jpeg"])

if uploaded_file is not None:
    # Hiển thị ảnh người dùng vừa tải lên
    st.image(uploaded_file, caption="Ảnh Sketch đã tải lên", width=300)
    
    if st.button("Bắt đầu tìm kiếm mã hàng"):
        with st.spinner("Hệ thống đang phân tích đường nét vẽ..."):
            try:
                # Bước a: Trích xuất Vector từ ảnh sketch
                img_bytes = uploaded_file.getvalue()
                sketch_embedding = get_image_embedding(img_bytes)
                
                # Bước b: Gọi hàm xử lý đối chiếu trên dữ liệu Supabase
                # (Hàm rpc 'match_products' cần được tạo sẵn bằng SQL trên Supabase)
                response = supabase.rpc("match_products", {
                    "query_embedding": sketch_embedding,
                    "match_threshold": 0.5,  # Ngưỡng tương đồng tối thiểu (50%)
                    "match_count": 4         # Lấy ra tối đa 4 kết quả tốt nhất
                }).execute()
                
                # Bước c: Hiển thị kết quả ra màn hình App
                if response.data:
                    st.success("Đã tìm thấy các mã hàng có nét tương đồng!")
                    
                    # Tạo các cột để hiển thị danh sách sản phẩm tìm được
                    cols = st.columns(len(response.data))
                    for idx, item in enumerate(response.data):
                        with cols[idx]:
                            st.metric(label="Độ chính xác", value=f"{item['similarity']*100:.2f}%")
                            st.subheader(f"Mã: {item['product_code']}")
                            if item.get('image_url'):
                                st.image(item['image_url'], use_container_width=True)
                else:
                    st.warning("Không tìm thấy mã hàng nào phù hợp với nét phác thảo này.")
                    
            except Exception as e:
                st.error(f"Đã xảy ra lỗi trong quá trình xử lý: {e}")

