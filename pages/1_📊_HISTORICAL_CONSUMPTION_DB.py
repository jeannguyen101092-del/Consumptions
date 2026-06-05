import streamlit as st
import pandas as pd
import requests

# Cấu hình an toàn bằng requests tương tự file app.py chính của bạn
SB_URL = "https://ewqqodsfvlvnrzsylawy.supabase.co"
SB_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImV3cXFvZHNmdmx2bnJ6c3lsYXd5Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzUxMTkyOTAsImV4cCI6MjA5MDY5NTI5MH0.BWPxOsyswBT5CLrZgluRC1F2x5EpU06oexUFyakGhyc"

st.title("📊 Bộ Tải Dữ Liệu Định Mức Lớn Lên Supabase")
st.markdown("Đồng bộ file Excel tổng vào bảng `san_pham` làm dữ liệu nền.")

uploaded_file = st.file_uploader("Chọn file định mức tổng hợp:", type=["xlsx", "xls", "csv"])

if uploaded_file:
    try:
        # Tối ưu đọc file linh hoạt cho cả CSV và Excel dữ liệu lớn của phân xưởng
        if uploaded_file.name.endswith('.csv'):
            try:
                df = pd.read_csv(uploaded_file, encoding='utf-8')
            except UnicodeDecodeError:
                uploaded_file.seek(0)
                df = pd.read_csv(uploaded_file, encoding='cp1252')
        else:
            df = pd.read_excel(uploaded_file)
            
        st.success(f"📊 Đã đọc file thành công! Tổng cộng: {len(df):,} dòng.")
        st.dataframe(df.head(5))
        
        if st.button("🚀 Bắt đầu chia cụm và đẩy dữ liệu lên Cloud"):
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            records_to_insert = []
            for _, row in df.iterrows():
                # ---------------------------------------------------------------------
                # ⚙️ ÁNH XẠ KHỚP TIÊU ĐỀ FILE EXCEL THỰC TẾ VÀO CÁC CỘT SQL CHỮ THƯỜNG
                # ---------------------------------------------------------------------
                
                # 1. Đọc chính xác giá trị định mức số thực từ cột viết tắt 'Input Purchase Cons' trong file Excel
                raw_cons = row.get('Input Purchase Cons', row.get('Input P', row.get('Input Purpose', row.get('consumption_value', 0.0))))
                try:
                    consumption_value_num = float(raw_cons) if pd.notnull(raw_cons) and str(raw_cons).strip() != "" else 0.0
                except ValueError:
                    consumption_value_num = 0.0

                # 2. Đọc cột loại phụ liệu/loại tiêu thụ (Main Fabric, Pocketing, Interlining) từ cột 'BodyType'
                consumption_type_val = row.get('BodyType', row.get('consumption_type', 'CUT'))

                # 3. Đọc cột loại vải nền (SJ-8002, NP430) từ đúng cột 'Article' trong file Excel của bạn
                article_name_val = row.get('Article', row.get('ArticleName', row.get('article_name', '')))

                record = {
                    "style_name": str(row.get('StyleName', row.get('style_name', ''))).strip(),
                    "article_name": str(article_name_val).strip(),
                    "consumption_type": str(consumption_type_val).strip(),
                    "material_size": str(row.get('MaterialSize', row.get('material_size', ''))).strip(),
                    "uom": str(row.get('UOM', row.get('uom', 'YRD'))).strip(),
                    "consumption_value": consumption_value_num,
                    "notes": str(row.get('Notes', row.get('notes', ''))).strip() if pd.notnull(row.get('Notes')) or pd.notnull(row.get('notes')) else ''
                }
                records_to_insert.append(record)
            
            # Cấu hình headers chuẩn PostgREST API cho Supabase
            headers = {
                "apikey": SB_KEY,
                "Authorization": f"Bearer {SB_KEY}",
                "Content-Type": "application/json",
                "Prefer": "resolution=merge-duplicates"
            }
            insert_url = f"{SB_URL.rstrip('/')}/rest/v1/san_pham"

            # Chia cụm (Batch) tối ưu 200 dòng một lần đẩy bằng Requests để tránh quá tải đường truyền
            batch_size = 200
            total_records = len(records_to_insert)
            
            for i in range(0, total_records, batch_size):
                batch = records_to_insert[i:i + batch_size]
                
                # Đẩy dữ liệu qua phương thức POST HTTP thuần túy
                res = requests.post(insert_url, headers=headers, json=batch, timeout=20)
                
                if res.status_code < 200 or res.status_code > 299:
                    st.error(f"❌ Lỗi đẩy dữ liệu tại dòng {i}: HTTP {res.status_code} - {res.text}")
                    st.stop()
                
                percent_complete = min(int((i + batch_size) / total_records * 100), 100)
                progress_bar.progress(percent_complete)
                status_text.text(f"⏳ Đã tải lên thành công: {min(i + batch_size, total_records):,} / {total_records:,} dòng...")
                
            st.balloons()
            st.success(f"🎉 Hoàn thành! Đã nạp thành công toàn bộ {total_records:,} dòng vào Supabase mới.")
            
    except Exception as e:
        st.error(f"❌ Xảy ra lỗi xử lý dữ liệu file: {e}")
