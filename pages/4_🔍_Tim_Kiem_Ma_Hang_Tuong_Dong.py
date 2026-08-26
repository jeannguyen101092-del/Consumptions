import streamlit as st
from supabase import create_client, Client
import requests
from PIL import Image
import io

# 1. Cấu hình giao diện Streamlit
st.set_page_config(page_title="Quản lý & Tìm kiếm mã hàng", page_icon="🔍", layout="wide")

# Kết nối tới cơ sở dữ liệu Supabase
SUPABASE_URL = "https://ewqqodsfvlvnrzsylawy.supabase.co"  # Thay bằng URL dự án của bạn
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImV3cXFvZHNmdmx2bnJ6c3lsYXd5Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzUxMTkyOTAsImV4cCI6MjA5MDY5NTI5MH0.BWPxOsyswBT5CLrZgluRC1F2x5EpU06oexUFyakGhyc"          # Thay bằng Anon Key của bạn
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- Lấy Token từ cấu hình bảo mật ẩn Secrets của Streamlit ---
if "HF_TOKEN" in st.secrets:
    HF_TOKEN = st.secrets["HF_TOKEN"]
else:
    st.error("⚠️ Chưa cấu hình HF_TOKEN trong cài đặt Secrets của Streamlit!")
    st.stop()

# ĐÃ THAY ĐỔI: Chuyển sang mô hình được hỗ trợ Serverless API (Giữ nguyên 512 chiều)
API_URL = "https://huggingface.co"

headers = {
    "Authorization": f"Bearer {HF_TOKEN}",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# Danh sách dòng hàng cố định để chọn lựa
CATEGORY_OPTIONS = ["Quần dài", "Quần short", "Áo", "Quần jogger", "Quần jean", "Quần túi hộp"]

def get_image_embedding_via_api(image_bytes):
    """Hàm lấy định dạng Vector từ AI"""
    response = requests.post(API_URL, headers=headers, data=image_bytes)
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Lỗi kết nối AI API: {response.text}")

def upload_image_to_storage(file_bytes, filename):
    """Hàm upload ảnh lên Supabase Storage"""
    bucket_name = "product-images"
    try:
        supabase.storage.from_(bucket_name).upload(
            path=filename,
            file=file_bytes,
            file_options={"content-type": "image/jpeg", "upsert": "true"}
        )
        return supabase.storage.from_(bucket_name).get_public_url(filename)
    except Exception as e:
        st.error(f"Lỗi lưu trữ ảnh {filename}: {e}")
        return None

# --- CHIA GIAO DIỆN THÀNH 2 TAB CHỨC NĂNG ---
tab1, tab2 = st.tabs(["🔍 TÌM KIẾM MÃ HÀNG TƯƠNG ĐỒNG", "📦 LƯU KHO HÀNG LOẠT"])

# ==========================================
# TAB 1: TÌM KIẾM MÃ HÀNG TƯƠNG ĐỒNG
# ==========================================
with tab1:
    st.header("🔍 Tìm Kiếm Mã Hàng Qua Ảnh Sketch")
    
    col_search_1, col_search_2 = st.columns(2)
    with col_search_1:
        search_category = st.selectbox("Chọn dòng hàng cần tìm kiếm:", CATEGORY_OPTIONS, key="sb_search")
        uploaded_sketch = st.file_uploader("Tải lên ảnh Sketch cần tìm:", type=["png", "jpg", "jpeg"], key="fu_search")
    
    if uploaded_sketch is not None:
        with col_search_2:
            st.image(uploaded_sketch, caption="Ảnh Sketch của bạn", width=250)
            
            if st.button("🚀 Bắt đầu quét mã tương đồng", type="primary"):
                with st.spinner("Hệ thống đang đối chiếu dữ liệu trong dòng hàng..."):
                    try:
                        sketch_bytes = uploaded_sketch.getvalue()
                        sketch_embedding = get_image_embedding_via_api(sketch_bytes)
                        
                        response = supabase.rpc("match_products_v2", {
                            "query_embedding": sketch_embedding,
                            "match_threshold": 0.4,
                            "match_count": 4,
                            "filter_category": search_category
                        }).execute()
                        
                        if response.data:
                            st.success(f"Kết quả tìm kiếm tương đồng trong nhóm [{search_category}]:")
                            cols = st.columns(len(response.data))
                            for idx, item in enumerate(response.data):
                                with cols[idx]:
                                    st.metric(label="Độ giống nhau", value=f"{item['similarity']*100:.2f}%")
                                    st.subheader(f"Mã: {item['product_code']}")
                                    if item.get('image_url'):
                                        st.image(item['image_url'], use_container_width=True)
                        else:
                            st.warning(f"Không tìm thấy sản phẩm nào tương đồng trong nhóm [{search_category}].")
                    except Exception as e:
                        st.error(f"Lỗi hệ thống: {e}")

# ==========================================
# TAB 2: LƯU KHO HÀNG LOẠT (UPLOADER)
# ==========================================
with tab2:
    st.header("📦 Đẩy Dữ Liệu Mã Hàng Hàng Loạt Lên Hệ Thống")
    st.info("💡 Cách đặt tên file để hệ thống tự động nhận diện: Tên_file_ảnh = Mã_hàng (Ví dụ: MS-1024.jpg)")
    
    col_upload_1, col_upload_2 = st.columns(2)
    with col_upload_1:
        upload_category = st.selectbox("Phân loại dòng hàng khi lưu kho:", CATEGORY_OPTIONS, key="sb_upload")
        uploaded_files = st.file_uploader("Chọn nhiều ảnh sản phẩm gốc / ảnh mẫu để lưu kho:", type=["png", "jpg", "jpeg"], accept_multiple_files=True)
    
    if uploaded_files:
        with col_upload_2:
            st.write(f"📂 Đã chọn **{len(uploaded_files)}** file ảnh sẵn sàng đẩy vào kho.")
            
            if st.button("📤 Tiến hành lưu toàn bộ vào kho"):
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                success_count = 0
                for index, file in enumerate(uploaded_files):
                    try:
                        # Tách chuỗi chuẩn xác lấy phần tên trước dấu chấm và viết hoa làm Mã Hàng
                        raw_name = file.name.split(".")[0]
                        product_code = str(raw_name).upper()
                        
                        status_text.text(f"⏳ Đang xử lý file ({index+1}/{len(uploaded_files)}): Mã {product_code}...")
                        
                        file_bytes = file.getvalue()
                        img_url = upload_image_to_storage(file_bytes, file.name)
                        
                        if img_url:
                            embedding_data = get_image_embedding_via_api(file_bytes)
                            
                            supabase.table("products").upsert({
                                "product_code": product_code,
                                "image_url": img_url,
                                "category": upload_category,
                                "embedding": embedding_data
                            }).execute()
                            
                            success_count += 1
                    except Exception as e:
                        st.error(f"Lỗi khi xử lý mã hàng {file.name}: {e}")
                    
                    progress_bar.progress((index + 1) / len(uploaded_files))
                
                status_text.empty()
                st.success(f"🎉 Hoàn thành! Đã lưu thành công **{success_count}/{len(uploaded_files)}** mã hàng vào phân loại nhóm **{upload_category}**.")
