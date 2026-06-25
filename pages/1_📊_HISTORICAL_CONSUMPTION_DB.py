import streamlit as st
import pandas as pd
from datetime import datetime
from supabase import create_client, Client

# 1. Cấu hình thông tin Supabase của bạn
SUPABASE_URL = "https://ewqqodsfvlvnrzsylawy.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImV3cXFvZHNmdmx2bnJ6c3lsYXd5Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzUxMTkyOTAsImV4cCI6MjA5MDY5NTI5MH0.BWPxOsyswBT5CLrZgluRC1F2x5EpU06oexUFyakGhyc"

@st.cache_resource
def get_supabase_client():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = get_supabase_client()

# Giao diện ứng dụng Streamlit
st.title("📊 Upload File & Thêm Số Liệu Vào Bảng Thống Sơ Techpack")

# Ô tải file Excel (.xlsx) từ máy tính
uploaded_file = st.file_uploader("Kéo và thả file Excel định mức vào đây", type=["xlsx", "xls"])

if uploaded_file is not None:
    st.write("📋 Xem trước dữ liệu từ file của bạn:")
    try:
        # Đọc dữ liệu từ file Excel
        df = pd.read_excel(uploaded_file)
        st.dataframe(df.head(10)) 
        
        # Nút xác nhận xử lý đưa vào hệ thống
        if st.button("🚀 Bắt đầu Up File và Thêm Số Liệu"):
            with st.spinner("Đang xử lý hệ thống..."):
                
                # --- BƯỚC 1: UPLOAD FILE VÀO KHO STORAGE ---
                bucket_name = "techpack_storage"
                file_name = uploaded_file.name
                file_data = uploaded_file.getvalue()
                
                supabase.storage.from_(bucket_name).upload(
                    file=file_data,
                    path=file_name,
                    file_options={"cache-control": "3600", "upsert": "true"}
                )
                st.success(f"📦 Đã lưu file '{file_name}' vào kho lưu trữ thành công!")

                # --- BƯỚC 2: ĐỌC DỮ LIỆU EXCEL VÀ UP VÀO BẢNG SUPABASE ---
                rows_to_insert = []
                current_time = datetime.utcnow().isoformat()
                
                for index, row in df.iterrows():
                    # Ánh xạ chính xác từ tên cột trong file Excel (StyleName, BodyType...)
                    # sang tên cột chữ thường trong database Supabase
                    data_row = {
                        "created_at": current_time,
                        "style_name": str(row.get("StyleName", "")).strip() if pd.notna(row.get("StyleName")) else None,
                        "article_name": str(row.get("ArticleName", "")).strip() if pd.notna(row.get("ArticleName")) else None,
                        "consumption_type": str(row.get("BodyType", "")).strip() if pd.notna(row.get("BodyType")) else None,
                        "material_size": str(row.get("MaterialSize", "")).strip() if pd.notna(row.get("MaterialSize")) else None,
                        "uom": str(row.get("UOM", "")).strip() if pd.notna(row.get("UOM")) else None
                    }
                    rows_to_insert.append(data_row)
                
                # Tiến hành thêm hàng loạt dữ liệu vào đúng bảng thong_so_techpack
                if rows_to_insert:
                    response = supabase.table("thong_so_techpack").insert(rows_to_insert).execute()
                    st.success(f"🎉 Đã thêm thành công {len(rows_to_insert)} dòng số liệu vào bảng thong_so_techpack!")
                else:
                    st.warning("⚠️ Không tìm thấy số liệu hợp lệ trong file Excel để nạp.")
                    
    except Exception as e:
        st.error(f"❌ Đã xảy ra lỗi khi xử lý: {str(e)}")
