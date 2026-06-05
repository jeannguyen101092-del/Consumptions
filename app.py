import streamlit as st

st.set_page_config(page_title="Hệ Thống Định Mức AI", layout="wide")

st.title("🎛️ Hệ Thống Tự Động Trích Xuất Techpack & Đồng Bộ Định Mức")
st.markdown("---")

st.markdown("""
### 📐 Quy trình xử lý dữ liệu 2 bước:
1. **Bước 1 (Menu bên trái -> 1 Nạp Kho Định Mức):** Tải file Excel hoặc CSV tổng hợp chứa toàn bộ thông số, định mức nguyên phụ liệu của nhà máy lên hệ thống.
2. **Bước 2 (Menu bên trái -> 2 Quet Techpack):** Tải file PDF tài liệu kỹ thuật mã hàng mới lên. AI sẽ tự động bóc tách ảnh vẽ thiết kế (Sketch), đọc tên mã hàng, khớp nối dữ liệu và đẩy toàn bộ lên Supabase Cloud.

👉 *Vui lòng chọn tính năng ở menu thanh bên cạnh (Sidebar) để bắt đầu.*
""")