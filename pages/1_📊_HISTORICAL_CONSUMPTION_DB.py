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

uploaded_file = st.file_uploader("Kéo và thả file Excel định mức vào đây", type=["xlsx", "xls"])

if uploaded_file is not None:
    st.write("📋 Xem trước dữ liệu từ file của bạn:")
    try:
        df = pd.read_excel(uploaded_file)
        st.dataframe(df.head(10)) 
        
        if st.button("🚀 Bắt đầu Kiểm Trùng và Nạp Dữ Liệu"):
            with st.spinner("Đang kiểm tra dữ liệu cũ trên hệ thống..."):
                
                # --- BƯỚC 1: LẤY DỮ LIỆU HIỆN TẠI TỪ BẢNG ĐỂ SO SÁNH ---
                db_response = supabase.table("san_pham").select("style_name, article_name").execute()
                db_data = db_response.data
                
                existing_records = {
                    (str(item["style_name"]).strip(), str(item["article_name"]).strip())
                    for item in db_data if item.get("style_name") and item.get("article_name")
                }

                # --- BƯỚC 2: ĐỌC EXCEL, LẤY ĐỊNH MỨC VÀ LỌC TRÙNG ---
                rows_to_insert = []
                duplicate_count = 0
                current_time = datetime.utcnow().isoformat()
                
                for index, row in df.iterrows():
                    excel_style = str(row.get("StyleName", "")).strip() if pd.notna(row.get("StyleName")) else ""
                    excel_article = str(row.get("ArticleName", "")).strip() if pd.notna(row.get("ArticleName")) else ""
                    
                    # KIỂM TRA TRÙNG LẶP
                    if (excel_style, excel_article) in existing_records:
                        duplicate_count += 1
                        continue 
                    
                    # LẤY GIÁ TRỊ ĐỊNH MỨC (Cột F trong file Excel của bạn: 3, 0.2, 0.65...)
                    # Ép kiểu dữ liệu về dạng số thực (float), nếu rỗng hoặc lỗi thì để mặc định là 0
                    try:
                        excel_dm = float(row.iloc[5]) if pd.notna(row.iloc[5]) else 0.0
                    except:
                        excel_dm = 0.0
                    
                    # Tạo cấu trúc dữ liệu đẩy vào bảng san_pham
                    data_row = {
                        "created_at": current_time,
                        "style_name": excel_style if excel_style else None,
                        "article_name": excel_article if excel_article else None,
                        "consumption_type": str(row.get("BodyType", "")).strip() if pd.notna(row.get("BodyType")) else None,
                        "material_size": str(row.get("MaterialSize", "")).strip() if pd.notna(row.get("MaterialSize")) else None,
                        "uom": str(row.get("UOM", "")).strip() if pd.notna(row.get("UOM")) else None,
                        
                        # 🔴 NẠP GIÁ TRỊ ĐỊNH MỨC VÀO ĐÂY (Thay "consumption" bằng tên chuẩn cột định mức trong DB của bạn nếu khác)
                        "consumption": excel_dm 
                    }
                    rows_to_insert.append(data_row)
                
                # --- BƯỚC 3: TIẾN HÀNH NẠP DỮ LIỆU ---
                if duplicate_count > 0:
                    st.warning(f"⚠️ Phát hiện {duplicate_count} dòng sản phẩm đã tồn tại sẵn. Hệ thống tự động bỏ qua không nạp trùng.")
                
                if rows_to_insert:
                    supabase.table("san_pham").insert(rows_to_insert).execute()
                    st.success(f"🎉 Đã nạp thành công {len(rows_to_insert)} dòng kèm số liệu định mức chuẩn vào bảng san_pham!")
                    st.rerun() # Làm mới lại giao diện Streamlit để cập nhật bảng số liệu mới nhất
                else:
                    st.info("💡 Không có dữ liệu mới nào được nạp thêm.")
                    
                # --- BƯỚC 4: LƯU TRỮ FILE ---
                try:
                    supabase.storage.from_("techpack_storage").upload(
                        file=uploaded_file.getvalue(),
                        path=uploaded_file.name,
                        file_options={"cache-control": "3600", "upsert": "true"}
                    )
                except:
                    pass

    except Exception as e:
        st.error(f"❌ Đã xảy ra lỗi khi xử lý dữ liệu: {str(e)}")
