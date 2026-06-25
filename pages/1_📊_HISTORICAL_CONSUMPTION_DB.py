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
# 2. GIAO DIỆN ỨNG DỤNG & CHỨC NĂNG NẠP FILE EXCEL VÀO KHO
# ==============================================================================
st.title("📊 BOM CONSUMPTION MATRIX & MANAGEMENT")

st.subheader("📤 Nạp File Định Mức Vào Kho Dữ Liệu")
uploaded_file = st.file_uploader("Kéo và thả file Excel định mức vào đây để cập nhật kho", type=["xlsx", "xls"])

if uploaded_file is not None:
    st.write("📋 Xem trước dữ liệu file vừa tải lên:")
    try:
        df = pd.read_excel(uploaded_file)
        st.dataframe(df.head(5)) 
        
        if st.button("🚀 Xác Nhận Kiểm Trùng Và Nạp Vào Kho"):
            with st.spinner("Đang xử lý nạp dữ liệu hệ thống..."):
                
                # --- Lấy dữ liệu cũ từ bảng san_pham để lọc trùng ---
                db_response = supabase.table("san_pham").select("style_name, article_name").execute()
                db_data = db_response.data
                
                existing_records = {
                    (str(item["style_name"]).strip(), str(item["article_name"]).strip())
                    for item in db_data if item.get("style_name") and item.get("article_name")
                }

                rows_to_insert = []
                duplicate_count = 0
                current_time = datetime.utcnow().isoformat()
                
                for index, row in df.iterrows():
                    excel_style = str(row.get("StyleName", "")).strip() if pd.notna(row.get("StyleName")) else ""
                    excel_article = str(row.get("ArticleName", "")).strip() if pd.notna(row.get("ArticleName")) else ""
                    
                    if (excel_style, excel_article) in existing_records:
                        duplicate_count += 1
                        continue 
                    
                    # Đọc chính xác giá trị định mức từ cột 'Input Purchase Cons'
                    excel_dm = row.get("Input Purchase Cons")
                    if pd.isna(excel_dm):
                        excel_dm = 0.0
                    else:
                        try:
                            excel_dm = float(excel_dm)
                        except:
                            excel_dm = 0.0
                    
                    rows_to_insert.append({
                        "created_at": current_time,
                        "style_name": excel_style if excel_style else None,
                        "article_name": excel_article if excel_article else None,
                        "consumption_type": str(row.get("BodyType", "")).strip() if pd.notna(row.get("BodyType")) else None,
                        "material_size": str(row.get("MaterialSize", "")).strip() if pd.notna(row.get("MaterialSize")) else None,
                        "uom": str(row.get("UOM", "")).strip() if pd.notna(row.get("UOM")) else None,
                        "consumption_value": excel_dm 
                    })
                
                if duplicate_count > 0:
                    st.warning(f"⚠️ Phát hiện {duplicate_count} dòng đã tồn tại sẵn trong kho. Hệ thống tự động bỏ qua.")
                
                if rows_to_insert:
                    supabase.table("san_pham").insert(rows_to_insert).execute()
                    st.success(f"🎉 Nạp kho thành công thêm {len(rows_to_insert)} dòng sản phẩm mới kèm định mức!")
                    st.rerun()
                else:
                    st.info("💡 Không có dữ liệu mới nào cần nạp (Tất cả sản phẩm trong file đã có sẵn).")
                    
                # --- Đẩy file sao lưu vào storage ---
                try:
                    supabase.storage.from_("techpack_storage").upload(
                        file=uploaded_file.getvalue(), path=uploaded_file.name, file_options={"upsert": "true"}
                    )
                except:
                    pass
    except Exception as e:
        st.error(f"❌ Lỗi xử lý file Excel: {str(e)}")

st.write("---")

# ==============================================================================
# 3. CHỨC NĂNG KẾT HỢP TRA CỨU / TRUY VẤN KHO TRỰC TIẾP
# ==============================================================================
st.subheader("🔍 Bộ Công Cụ Tra Cứu Kho Định Mức")

# Tạo thanh tìm kiếm không phân biệt hoa thường
search_query = st.text_input(
    "Nhập Mã hàng (Style Name) hoặc Tên vật tư / Mã vải (Article Name) để tìm kiếm nhanh:",
    placeholder="Nhập từ khóa tìm kiếm tại đây..."
).strip()

if search_query:
    with st.spinner("Đang lọc dữ liệu từ kho..."):
        try:
            # Tạo chuỗi điều kiện tìm kiếm mờ (ilike) trên cả 2 cột style_name và article_name
            query_string = f"style_name.ilike.%{search_query}%,article_name.ilike.%{search_query}%"
            
            response = supabase.table("san_pham")\
                               .select("style_name, consumption_type, article_name, material_size, uom, consumption_value")\
                               .or_(query_string)\
                               .execute()
            data = response.data
            
            if data:
                df_result = pd.DataFrame(data)
                df_result.rename(columns={
                    "style_name": "Mã hàng đối chứng",
                    "consumption_type": "Phân loại vật tư (Type)",
                    "article_name": "Tên vật tư / Mã vải",
                    "material_size": "Khổ vải / Chi tiết định mức",
                    "uom": "Đơn vị (UOM)",
                    "consumption_value": "Định mức (DM)"
                }, inplace=True)
                
                st.success(f"🎉 Tìm thấy {len(df_result)} kết quả khớp với từ khóa '{search_query}'!")
                st.dataframe(df_result, use_container_width=True)
            else:
                st.warning(f"❌ Không tìm thấy mã hàng hoặc mã vải nào khớp với từ khóa '{search_query}'.")
        except Exception as search_err:
            st.error(f"Lỗi truy vấn tìm kiếm: {str(search_err)}")
else:
    # Trạng thái mặc định: Hiển thị 10 dòng số liệu mới nhất vừa nạp vào kho
    st.info("💡 Điền từ khóa vào ô trên để tìm kiếm dữ liệu cụ thể. Dưới đây là 10 dòng số liệu mới nhất trong kho:")
    try:
        response = supabase.table("san_pham")\
                           .select("style_name, consumption_type, article_name, material_size, uom, consumption_value")\
                           .order("created_at", ascending=False)\
                           .limit(10)\
                           .execute()
        if response.data:
            df_display = pd.DataFrame(response.data)
            df_display.rename(columns={
                "style_name": "Mã hàng đối chứng",
                "consumption_type": "Phân loại vật tư (Type)",
                "article_name": "Tên vật tư / Mã vải",
                "material_size": "Khổ vải / Chi tiết định mức",
                "uom": "Đơn vị (UOM)",
                "consumption_value": "Định mức (DM)"
            }, inplace=True)
            st.dataframe(df_display, use_container_width=True)
    except Exception as display_err:
        st.error(f"Lỗi hiển thị danh sách kho: {str(display_err)}")
