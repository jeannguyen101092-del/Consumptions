import streamlit as st
import pandas as pd
from datetime import datetime
from supabase import create_client, Client

# ==============================================================================
# 1. CẤU HÌNH THÔNG TIN SUPABASE
# ==============================================================================
SUPABASE_URL = "https://ewqqodsfvlvnrzsylawy.supabase.co"

# 🔴 LƯU Ý: Thay bằng Service Role Key (Secret Key) lấy từ Project Settings -> API
# của Supabase để có toàn quyền ghi vào database và storage.
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImV3cXFvZHNmdmx2bnJ6c3lsYXd5Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzUxMTkyOTAsImV4cCI6MjA5MDY5NTI5MH0.BWPxOsyswBT5CLrZgluRC1F2x5EpU06oexUFyakGhyc"

@st.cache_resource
def get_supabase_client():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = get_supabase_client()

# ==============================================================================
# 2. GIAO DIỆN ỨNG DỤNG STREAMLIT
# ==============================================================================
st.title("📦 Upload File & Nạp Số Liệu Vào Bảng Sản Phẩm")

# Ô tải file Excel từ máy tính
uploaded_file = st.file_uploader("Kéo và thả file Excel định mức vào đây", type=["xlsx", "xls"])

if uploaded_file is not None:
    st.write("📋 Xem trước dữ liệu từ file của bạn:")
    try:
        # Đọc dữ liệu từ file Excel
        df = pd.read_excel(uploaded_file)
        st.dataframe(df.head(10)) 
        
        # Nút xác nhận xử lý nạp vào bảng san_pham
        if st.button("🚀 Bắt đầu Up File và Nạp Vào Bảng Sản Phẩm"):
            with st.spinner("Đang xử lý nạp dữ liệu hệ thống..."):
                
                # --- BƯỚC 1: UPLOAD FILE VÀO KHO STORAGE (Có bảo vệ tránh lỗi sập app) ---
                bucket_name = "techpack_storage" 
                file_name = uploaded_file.name
                file_data = uploaded_file.getvalue()
                
                try:
                    supabase.storage.from_(bucket_name).upload(
                        file=file_data,
                        path=file_name,
                        file_options={"cache-control": "3600", "upsert": "true"}
                    )
                    st.success(f"📦 Đã lưu file vật lý '{file_name}' vào kho techpack_storage!")
                except Exception as storage_err:
                    st.warning(f"⚠️ Cảnh báo Storage: Không thể up file vật lý do '{str(storage_err)}'. Hệ thống vẫn tiếp tục nạp số liệu vào bảng dữ liệu...")

                # --- BƯỚC 2: ĐỌC EXCEL VÀ NẠP CHÍNH XÁC VÀO BẢNG san_pham ---
                rows_to_insert = []
                current_time = datetime.utcnow().isoformat()
                
                for index, row in df.iterrows():
                    # Ánh xạ dữ liệu từ file Excel sang cấu trúc của bảng san_pham.
                    # Đoạn này tự động lấy theo các cột có sẵn trong file Excel của bạn:
                    data_row = {
                        "created_at": current_time,
                        "style_name": str(row.get("StyleName", "")).strip() if pd.notna(row.get("StyleName")) else None,
                        "article_name": str(row.get("ArticleName", "")).strip() if pd.notna(row.get("ArticleName")) else None,
                        "consumption_type": str(row.get("BodyType", "")).strip() if pd.notna(row.get("BodyType")) else None,
                        "material_size": str(row.get("MaterialSize", "")).strip() if pd.notna(row.get("MaterialSize")) else None,
                        "uom": str(row.get("UOM", "")).strip() if pd.notna(row.get("UOM")) else None
                    }
                    rows_to_insert.append(data_row)
                
                # Thực hiện đẩy hàng loạt dữ liệu trực tiếp vào bảng san_pham
                if rows_to_insert:
                    # Đổi tên bảng đích chính xác thành "san_pham" ở đây
                    supabase.table("san_pham").insert(rows_to_insert).execute()
                    st.success(f"🎉 Đã nạp thành công {len(rows_to_insert)} dòng số liệu vào bảng san_pham!")
                else:
                    st.warning("⚠️ Không tìm thấy số liệu hợp lệ trong file Excel để nạp.")
                    
    except Exception as e:
        st.error(f"❌ Đã xảy ra lỗi khi xử lý dữ liệu: {str(e)}")
