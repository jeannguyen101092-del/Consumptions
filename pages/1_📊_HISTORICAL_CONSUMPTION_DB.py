import streamlit as st
import pandas as pd
from datetime import datetime
from supabase import create_client, Client

# ==============================================================================
# 1. CẤU HÌNH THÔNG TIN SUPABASE
# ==============================================================================
SUPABASE_URL = "https://ewqqodsfvlvnrzsylawy.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImV3cXFvZHNmdmx2bnJ6c3lsYXd5Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzUxMTkyOTAsImV4cCI6MjA5MDY5NTI5MH0.BWPxOsyswBT5CLrZgluRC1F2x5EpU06oexUFyakGhyc"

@st.cache_resource
def get_supabase_client():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = get_supabase_client()

# ==============================================================================
# 2. GIAO DIỆN ỨNG DỤNG STREAMLIT
# ==============================================================================
st.title("📦 Upload File & Kiểm Trùng Nạp Vào Bảng Sản Phẩm")

# Ô tải file Excel (.xlsx) từ máy tính
uploaded_file = st.file_uploader("Kéo và thả file Excel định mức vào đây", type=["xlsx", "xls"])

if uploaded_file is not None:
    st.write("📋 Xem trước dữ liệu từ file của bạn:")
    try:
        # Đọc dữ liệu từ file Excel
        df = pd.read_excel(uploaded_file)
        st.dataframe(df.head(10)) 
        
        # Nút xác nhận xử lý đưa vào hệ thống
        if st.button("🚀 Bắt đầu Kiểm Trùng và Nạp Dữ Liệu"):
            with st.spinner("Đang kiểm tra dữ liệu cũ trên hệ thống..."):
                
                # --- BƯỚC 1: LẤY DỮ LIỆU HIỆN TẠI TỪ BẢNG ĐỂ SO SÁNH TRÙNG LẶP ---
                db_response = supabase.table("san_pham").select("style_name, article_name").execute()
                db_data = db_response.data
                
                existing_records = {
                    (str(item["style_name"]).strip(), str(item["article_name"]).strip())
                    for item in db_data if item.get("style_name") and item.get("article_name")
                }

                # --- BƯỚC 2: ĐỌC EXCEL VÀ ÁNH XẠ CHÍNH XÁC VÀO CỘT DATABASE ---
                rows_to_insert = []
                duplicate_count = 0
                current_time = datetime.utcnow().isoformat()
                
                for index, row in df.iterrows():
                    # Đọc dữ liệu từ file Excel của bạn (StyleName, ArticleName...)
                    excel_style = str(row.get("StyleName", "")).strip() if pd.notna(row.get("StyleName")) else ""
                    excel_article = str(row.get("ArticleName", "")).strip() if pd.notna(row.get("ArticleName")) else ""
                    
                    # Kiểm tra nếu đã trùng mã hàng + mã vải trong kho thì bỏ qua
                    if (excel_style, excel_article) in existing_records:
                        duplicate_count += 1
                        continue 
                    
                    # Đọc giá trị định mức từ file Excel (Thử lấy từ tiêu đề 'DM' hoặc cột số cuối)
                    # Ép kiểu dữ liệu về float để khớp với cột numeric trong database
                    excel_dm = row.get("DM", 0.0)
                    if pd.isna(excel_dm):
                        # Nếu file Excel đặt tên cột định mức là kiểu khác, hệ thống tự động bốc cột số cuối
                        try:
                            excel_dm = float(row.iloc[-1]) if pd.notna(row.iloc[-1]) else 0.0
                        except:
                            excel_dm = 0.0
                    else:
                        try:
                            excel_dm = float(excel_dm)
                        except:
                            excel_dm = 0.0
                    
                    # Ánh xạ chính xác 100% theo các cột hiển thị trên Supabase của bạn
                    data_row = {
                        "created_at": current_time,
                        "style_name": excel_style if excel_style else None,
                        "article_name": excel_article if excel_article else None,
                        "consumption_type": str(row.get("BodyType", "")).strip() if pd.notna(row.get("BodyType")) else None,
                        "material_size": str(row.get("MaterialSize", "")).strip() if pd.notna(row.get("MaterialSize")) else None,
                        "uom": str(row.get("UOM", "")).strip() if pd.notna(row.get("UOM")) else None,
                        
                        # 🔴 ĐÃ KHỚP TÊN CỘT: Nạp số liệu định mức vào đúng cột consumption_value
                        "consumption_value": excel_dm 
                    }
                    rows_to_insert.append(data_row)
                
                # --- BƯỚC 3: TIẾN HÀNH ĐẨY DỮ LIỆU VÀO SUPABASE ---
                if duplicate_count > 0:
                    st.warning(f"⚠️ Phát hiện {duplicate_count} dòng sản phẩm đã tồn tại sẵn. Hệ thống tự động bỏ qua không nạp trùng.")
                
                if rows_to_insert:
                    supabase.table("san_pham").insert(rows_to_insert).execute()
                    st.success(f"🎉 Đã nạp thành công {len(rows_to_insert)} dòng kèm số liệu định mức (consumption_value) vào bảng san_pham!")
                    st.rerun() # Làm mới giao diện để hiển thị số liệu mới ngay lập tức
                else:
                    st.info("💡 Không có dữ liệu mới nào cần nạp thêm.")
                    
                # --- BƯỚC 4: LƯU TRỮ SAO LƯU FILE VÀO KHO STORAGE ---
                try:
                    bucket_name = "techpack_storage"
                    supabase.storage.from_(bucket_name).upload(
                        file=uploaded_file.getvalue(),
                        path=uploaded_file.name,
                        file_options={"cache-control": "3600", "upsert": "true"}
                    )
                except:
                    pass # Ẩn lỗi upload file để tránh làm sập luồng ghi database chính

    except Exception as e:
        st.error(f"❌ Đã xảy ra lỗi khi xử lý dữ liệu: {str(e)}")
