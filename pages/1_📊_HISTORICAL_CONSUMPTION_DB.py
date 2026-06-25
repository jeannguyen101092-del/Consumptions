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
                    
                    excel_dm = row.get("Input Purchase Cons")
                    if pd.isna(excel_dm):
                        excel_dm = 0.0
                    else:
                        try: excel_dm = float(excel_dm)
                        except: excel_dm = 0.0
                    
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
                    st.info("💡 Không có dữ liệu mới nào cần nạp.")
    except Exception as e:
        st.error(f"❌ Lỗi xử lý file Excel: {str(e)}")

st.write("---")

# ==============================================================================
# 3. 🔴 CHỨC NĂNG SỬA ĐỔI: XÓA CHÍNH XÁC 1 DÒNG SẢN PHẨM KHỚP MÃ
# ==============================================================================
st.subheader("🗑️ Quản Lý Xóa Dòng Dữ Liệu Lỗi")
with st.expander("👉 Bấm vào đây để mở vùng xóa duy nhất 1 dòng lỗi", expanded=False):
    col1, col2 = st.columns(2)
    with col1:
        delete_style_code = st.text_input("1. Nhập Mã hàng (Style Name):", placeholder="Ví dụ: P08-500722").strip()
    with col2:
        delete_article_code = st.text_input("2. Nhập Mã vải / Vật tư (Article Name):", placeholder="Ví dụ: D01527").strip()
    
    if delete_style_code and delete_article_code:
        st.warning(f"⚠️ Hệ thống sẽ xóa duy nhất dòng có Mã hàng: `{delete_style_code}` và Mã vải: `{delete_article_code}`.")
        if st.button("🔥 Xác nhận xóa dòng này khỏi kho", type="primary"):
            with st.spinner("Đang thực hiện xóa dòng chỉ định..."):
                try:
                    # Lệnh xóa kết hợp 2 điều kiện bằng .eq() nối tiếp nhau để định vị đúng 1 dòng duy nhất
                    delete_response = supabase.table("san_pham")\
                                              .delete()\
                                              .eq("style_name", delete_style_code)\
                                              .eq("article_name", delete_article_code)\
                                              .execute()
                    
                    if delete_response.data:
                        st.success(f"✅ Đã xóa thành công dòng sản phẩm khớp mã khỏi database!")
                        st.rerun()
                    else:
                        st.error("❌ Không tìm thấy dòng nào khớp chính xác đồng thời cả Mã hàng và Mã vải trên.")
                except Exception as del_err:
                    st.error(f"Lỗi khi thực hiện xóa: {str(del_err)}")

st.write("---")

# ==============================================================================
# 4. CHỨC NĂNG KẾT HỢP TRA CỨU / TRUY VẤN KHO TRỰC TIẾP
# ==============================================================================
st.subheader("🔍 Bộ Công Cụ Tra Cứu Kho Định Mức")

search_query = st.text_input(
    "Nhập Mã hàng (Style Name) hoặc Tên vật tư / Mã vải (Article Name) để tìm kiếm nhanh:",
    placeholder="Nhập từ khóa tìm kiếm tại đây...",
    key="search_input_unique"
).strip()

if search_query:
    with st.spinner("Đang lọc dữ liệu từ kho..."):
        try:
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
        pass
