import streamlit as st
import pandas as pd
import json
import io
import math
import re
import datetime
import openpyxl
from openpyxl.styles import PatternFill, Font, Border, Side, Alignment
from openpyxl.utils import get_column_letter

# Cấu hình trang độc lập PPJ GROUP
st.set_page_config(
    page_title="PPJ Group - Tác Nghiệp Bàn Cắt",
    page_icon="✂️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Khởi tạo trạng thái hệ thống
if "purchase_ready" not in st.session_state:
    st.session_state["purchase_ready"] = False
if "sbd_parsed_data" not in st.session_state:
    st.session_state["sbd_parsed_data"] = {}
if "auto_cutting_results" not in st.session_state:
    st.session_state["auto_cutting_results"] = None
if "consumption_activated" not in st.session_state:
    st.session_state["consumption_activated"] = False
if "supabase" not in st.session_state:
    st.session_state["supabase"] = None 

# Giao diện CSS CSS Header Block
st.markdown("""
<style>
    .main-header { font-size: 24px; font-weight: 700; color: #1E3A8A; margin-bottom: 5px; }
    .card-container { background-color: #FFFFFF; padding: 20px; border-radius: 8px; border: 1px solid #E2E8F0; margin-bottom: 15px; }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header">📋 PHÂN HỆ TÁC NGHIỆP BÀN CẮT ĐA GIÀNG HOÀN CHỈNH</div>', unsafe_allow_html=True)

# KIỂM TRA ĐIỀU KIỆN 1: Số hóa dữ liệu đầu vào
if not st.session_state["purchase_ready"]:
    st.markdown('<div class="card-container"><p style="color: #475569; font-size:13px; margin:0;">Tải lên File SBD số lượng để hệ thống tự động tính toán chia tỷ lệ bàn cắt.</p></div>', unsafe_allow_html=True)
    file_sbd_c2 = st.file_uploader("📋 Chọn File SBD Số Lượng Đơn Hàng (Excel/PDF)", type=["xlsx", "xls", "pdf"], key="purchase_sbd_standalone")
    
    if file_sbd_c2:
        if st.button("⚡ SỐ HÓA MA TRẬN SẢN LƯỢNG ĐƠN HÀNG TÁC NGHIỆP", type="primary", use_container_width=True):
            with st.spinner("🚀 Đang phân tích mảng phân bổ size phẳng từ file SBD..."):
                if file_sbd_c2.name.lower().endswith(('.xlsx', '.xls')):
                    st.session_state["sbd_parsed_data"] = {
                        "style_id": "PPJ-STYLE-SAMPLE", "total_quantity": 5000,
                        "size_breakdown": {"28": 500, "29": 1000, "30": 1500, "31": 1200, "32": 800}, "inseam_group": "30-32-34"
                    }
                else:
                    st.session_state["sbd_parsed_data"] = {
                        "style_id": "PPJ-DENIM-2026", "total_quantity": 3600,
                        "size_breakdown": {"S": 400, "M": 1200, "L": 1400, "XL": 600}, "inseam_group": "None"
                    }
                st.session_state["purchase_ready"] = True
                st.rerun()
# KIỂM TRA ĐIỀU KIỆN 2: Đã số hóa xong -> Chuyển sang màn hình tác nghiệp sản xuất
else:
    sbd_data_store = st.session_state.get("sbd_parsed_data", {})
    if isinstance(sbd_data_store, dict) and sbd_data_store:
        detected_style_id = sbd_data_store.get("style_id", "UNKNOWN_STYLE")
        detected_total_po = sbd_data_store.get("total_quantity", 0)
        size_breakdown_main = sbd_data_store.get("size_breakdown", {})
        detected_inseam = sbd_data_store.get("inseam_group", "None")

        if st.button("🔄 Tải lên File SBD Khác", type="secondary"):
            st.session_state["purchase_ready"] = False
            st.session_state["sbd_parsed_data"] = {}
            st.session_state["auto_cutting_results"] = None
            st.session_state["consumption_activated"] = False
            st.rerun()

        # Khai báo thông số đầu vào bàn vải
        st.markdown("#### 📋 KHAI BÁO THÔNG SỐ TÁC NGHIỆP ĐƠN HÀNG VÀ BÀN VẢI MULTI-INSEAM")
        input_col1, input_col2, input_col3 = st.columns(3)
        with input_col1: style_id_input = st.text_input("🏷️ Tên mã hàng (Style ID):", value=str(detected_style_id).strip().upper())
        with input_col2: po_qty_input = st.number_input("📦 Số lượng đơn hàng (PO Pcs):", value=int(detected_total_po), step=100)
        with input_col3: consumption_input = st.number_input("🎯 Định mức tài liệu đề xuất (Yds/Pcs):", value=1.140, step=0.001, format="%.3f")

        input_col4, input_col6 = st.columns(2)
        with input_col4: max_table_length = st.number_input("📏 Chiều dài tối đa bàn vải (Meters):", value=12.00, step=1.0)
        with input_col6: cuttable_width_inch = st.number_input("📐 KHỔ CẮT (Inches):", value=56.00, step=0.50, format="%.2f")
        
        cad_paste_zone = st.text_area("Sau khi xem cấu trúc phối size, hãy đi sơ đồ trên máy CAD rồi copy dán kết quả [Tên sơ đồ + Chiều dài mét] vào đây:", placeholder="Ví dụ:\nc01 6.55\nc02 8.20", height=90, key="cad_bulk_paste_standalone")
        
        if size_breakdown_main:
            st.dataframe(pd.DataFrame([size_breakdown_main]), use_container_width=True, hide_index=True)

        active_sizes = [str(k) for k, v in size_breakdown_main.items() if int(v) > 0]
        if not active_sizes: active_sizes = ["S", "M", "L", "XL"]

        btn_col1, btn_col2 = st.columns(2)
        with btn_col1: trigger_auto_cutting = st.button("⚡ 1. KÍCH HOẠT TÍNH TÁC NGHIỆP SƠ ĐỒ (THUẬT TOÁN THUẦN)", type="primary", use_container_width=True)
        with btn_col2: trigger_consumption = st.button("📊 2. KÍCH HOẠT TÍNH ĐỊNH MỨC (KHI ĐÃ CÓ CAD)", type="secondary", use_container_width=True)

        if trigger_consumption:
            st.session_state["consumption_activated"] = True
            st.rerun()

        # Thuật toán phân bổ sơ đồ hình tháp bẻ ngắn bàn vải
        if trigger_auto_cutting:
            st.session_state["consumption_activated"] = False
            with st.spinner("🚀 Hệ thống đang phân bổ sơ đồ hình tháp..."):
                cons_meters = consumption_input / 1.09361
                max_pcs_per_marker = math.floor(max_table_length / (cons_meters if cons_meters > 0 else 1.0))
                if max_pcs_per_marker <= 0: max_pcs_per_marker = 6
                
                balance_tracker = {sz: int(size_breakdown_main.get(sz, 0)) for sz in active_sizes}
                calculated_steps = []
                step_idx = 1
                
                while sum(balance_tracker.values()) > 0 and step_idx <= 25:
                    marker_id = f"c{step_idx:02d}"
                    target_layers = 150 if step_idx == 1 else (120 if step_idx == 2 else (90 if step_idx == 3 else 60))
                    sorted_sizes = sorted(balance_tracker.items(), key=lambda x: x[1], reverse=True)
                    current_ratios = {sz: 0 for sz in active_sizes}
                    assigned_pcs = 0
                    
                    max_remaining_bal = max(balance_tracker.values()) if balance_tracker.values() else 0
                    effective_max_pcs = max_pcs_per_marker
                    if max_remaining_bal < target_layers and max_remaining_bal > 0:
                        effective_max_pcs = min(2, max_pcs_per_marker)
                        target_layers = max_remaining_bal
                    
                    for sz, bal in sorted_sizes:
                        if bal <= 0 or assigned_pcs >= effective_max_pcs: continue
                        needed_ratio = math.floor(bal / target_layers)
                        if needed_ratio > 4: needed_ratio = 4
                        if needed_ratio == 0 and bal > (target_layers / 2): needed_ratio = 1
                        if assigned_pcs + needed_ratio > effective_max_pcs: needed_ratio = effective_max_pcs - assigned_pcs
                        current_ratios[sz] = needed_ratio
                        assigned_pcs += needed_ratio
                    
                    layer_candidates = [math.ceil(balance_tracker[sz] / r) for sz, r in current_ratios.items() if r > 0]
                    computed_layers = min(layer_candidates) if layer_candidates else target_layers
                    num_tables = math.ceil(computed_layers / 120) if computed_layers > 150 else 1
                    if num_tables > 1: computed_layers = math.ceil(computed_layers / num_tables)
                        
                    calculated_steps.append({"Sơ đồ / Trạng thái": marker_id, "Số lớp": computed_layers, "Số bàn": num_tables, "Dài sơ đồ": 0.0, "Số sp/SĐ": assigned_pcs, "Ratios": current_ratios})
                    for sz in active_sizes:
                        balance_tracker[sz] = max(0, balance_tracker[sz] - (current_ratios[sz] * computed_layers * num_tables))
                    calculated_steps.append({"Sơ đồ / Trạng thái": "Balance", "Số lớp": "", "Số bàn": "", "Dài sơ đồ": "", "Số sp/SĐ": "", "Ratios": balance_tracker.copy()})
                    step_idx += 1
                st.session_state["auto_cutting_results"] = calculated_steps
                 # KHỞI TẠO CÁC CỘT KỸ THUẬT MỞ RỘNG THEO MẪU NHÀ XƯỞNG
        tech_cols_factory = ["Số lớp", "Tổng SL Cắt", "Tổng SL Còn Lại", "Dài SĐ YC (M)", "Hiệu suất SĐ (%)", "Đầu bàn (M)", "SL Vải TT Cần Cắt", "Hiệu suất chung"]
        
        st.markdown("<p style='font-weight:700; font-size:14px; color:#1E3A8A; margin-top:15px;'>🏗️ TẦNG 1: TÁC NGHIỆP THỦ CÔNG (NGƯỜI DÙNG TỰ NHẬP TAY SƠ ĐỒ)</p>", unsafe_allow_html=True)
        st.markdown("<p style='font-size:12px; color:#64748B; margin:0;'>Bạn có thể tự nhập tỷ lệ phối size (Ratio), số lớp và thông số hình học để hệ thống đối chiếu sản lượng còn lại.</p>", unsafe_allow_html=True)

        # Tạo bảng nhập liệu động (Data Editor) cho Tầng 1
        if "manual_cutting_plan" not in st.session_state:
            initial_rows = [{"BÀN CẮT/TÊN SĐ": f"M_c0{i}", "Số lớp": 0, "Dài SĐ YC (M)": 0.0, "Hiệu suất SĐ (%)": 82.5, "Đầu bàn (M)": 0.15} for i in range(1, 4)]
            for r in initial_rows:
                for sz in active_sizes: r[sz] = 0 # Khởi tạo tỷ lệ ban đầu bằng 0
            st.session_state["manual_cutting_plan"] = pd.DataFrame(initial_rows)

        # Cấu hình kiểu nhập liệu cho từng cột trên lưới
        column_config_t1 = {
            "BÀN CẮT/TÊN SĐ": st.column_config.TextColumn("BÀN CẮT/TÊN SĐ", width="medium", required=True),
            "Số lớp": st.column_config.NumberColumn("Số lớp", min_value=0, max_value=500, step=1, default=0),
            "Dài SĐ YC (M)": st.column_config.NumberColumn("Dài SĐ YC (M)", min_value=0.0, step=0.01, format="%.2f"),
            "Hiệu suất SĐ (%)": st.column_config.NumberColumn("Hiệu suất SĐ (%)", min_value=0.0, max_value=100.0, step=0.1, format="%.1f"),
            "Đầu bàn (M)": st.column_config.NumberColumn("Đầu bàn (M)", min_value=0.0, step=0.01, format="%.2f")
        }
        for sz in active_sizes:
            column_config_t1[sz] = st.column_config.NumberColumn(f"{sz}", min_value=0, max_value=10, step=1, default=0)

        # Hiển thị bảng chỉnh sửa dữ liệu Tầng 1
        edited_df_t1 = st.data_editor(
            st.session_state["manual_cutting_plan"],
            column_config=column_config_t1,
            num_rows="dynamic",
            use_container_width=True,
            key="factory_data_editor_t1"
        )
        st.session_state["manual_cutting_plan"] = edited_df_t1

        # XỬ LÝ TOÁN HỌC ĐỐI CHIẾU SẢN LƯỢNG SAU KHI NGƯỜI DÙNG NHẬP TAY TẦNG 1
        manual_totals = {sz: 0 for sz in active_sizes}
        for _, row in edited_df_t1.iterrows():
            layers = int(row.get("Số lớp") or 0)
            for sz in active_sizes:
                ratio = int(row.get(sz) or 0)
                manual_totals[sz] += ratio * layers

        # Tính toán lượng sản phẩm còn lại cần giải quyết cho Tầng 2
        remaining_balance_t2 = {}
        for sz in active_sizes:
            orig_po = int(size_breakdown_main.get(sz, 0))
            remaining_balance_t2[sz] = max(0, orig_po - manual_totals[sz])
        st.markdown("<br><p style='font-weight:700; font-size:14px; color:#065F46;'>🤖 TẦNG 2: TÁC NGHIỆP TỰ ĐỘNG (THUẬT TOÁN VÉT SẢN LƯỢNG CÒN LẠI)</p>", unsafe_allow_html=True)
        
        trigger_t2_auto = st.button("⚡ KÍCH HOẠT TỰ ĐỘNG BẺ SƠ ĐỒ HÌNH THÁP CHO LƯỢNG CÒN LẠI", type="primary", use_container_width=True)
        
        if trigger_t2_auto or st.session_state["auto_cutting_results"] is not None:
            if trigger_t2_auto:
                with st.spinner("🚀 Hệ thống đang quét dư lượng Tầng 1 để lập kế hoạch Tầng 2..."):
                    cons_meters = consumption_input / 1.09361
                    max_pcs_per_marker = math.floor(max_table_length / (cons_meters if cons_meters > 0 else 1.0))
                    if max_pcs_per_marker <= 0: max_pcs_per_marker = 6
                    
                    balance_tracker = remaining_balance_t2.copy()
                    calculated_steps = []
                    step_idx = 1
                    
                    while sum(balance_tracker.values()) > 0 and step_idx <= 15:
                        marker_id = f"Auto_c{step_idx:02d}"
                        target_layers = 120 if step_idx == 1 else 80
                        sorted_sizes = sorted(balance_tracker.items(), key=lambda x: x[1], reverse=True)
                        current_ratios = {sz: 0 for sz in active_sizes}
                        assigned_pcs = 0
                        
                        max_remaining_bal = max(balance_tracker.values()) if balance_tracker.values() else 0
                        effective_max_pcs = max_pcs_per_marker
                        if max_remaining_bal < target_layers and max_remaining_bal > 0:
                            effective_max_pcs = min(2, max_pcs_per_marker)
                            target_layers = max_remaining_bal
                        
                        for sz, bal in sorted_sizes:
                            if bal <= 0 or assigned_pcs >= effective_max_pcs: continue
                            needed_ratio = math.floor(bal / target_layers)
                            if needed_ratio > 4: needed_ratio = 4
                            if needed_ratio == 0 and bal > (target_layers / 2): needed_ratio = 1
                            if assigned_pcs + needed_ratio > effective_max_pcs: needed_ratio = effective_max_pcs - assigned_pcs
                            current_ratios[sz] = needed_ratio
                            assigned_pcs += needed_ratio
                        
                        layer_candidates = [math.ceil(balance_tracker[sz] / r) for sz, r in current_ratios.items() if r > 0]
                        computed_layers = min(layer_candidates) if layer_candidates else target_layers
                        if computed_layers <= 0: computed_layers = 1
                            
                        calculated_steps.append({"Sơ đồ / Trạng thái": marker_id, "Số lớp": computed_layers, "Ratios": current_ratios})
                        for sz in active_sizes:
                            balance_tracker[sz] = max(0, balance_tracker[sz] - (current_ratios[sz] * computed_layers))
                        step_idx += 1
                    st.session_state["auto_cutting_results"] = calculated_steps

            # --- TỔNG HỢP VÀ DỰNG BẢNG ĐẦY ĐỦ THÔNG SỐ THEO HÌNH ẢNH MẪU CỦA KHÁCH HÀNG ---
            final_factory_rows = []
            current_balance = {sz: int(size_breakdown_main.get(sz, 0)) for sz in active_sizes}
            
            # 1. Đưa dữ liệu Tầng 1 (Nhập tay) vào danh sách hiển thị tổng hợp
            for _, row in edited_df_t1.iterrows():
                name = row.get("BÀN CẮT/TÊN SĐ")
                layers = int(row.get("Số lớp") or 0)
                m_len = float(row.get("Dài SĐ YC (M)") or 0.0)
                eff_sd = float(row.get("Hiệu suất SĐ (%)") or 0.0)
                db_m = float(row.get("Đầu bàn (M)") or 0.0)
                
                ratios_sum = sum(int(row.get(sz) or 0) for sz in active_sizes)
                total_cut_pcs = ratios_sum * layers
                
                display_row = {"BÀN CẮT/TÊN SĐ": name, "Số lớp": layers, "Tổng SL Cắt": total_cut_pcs}
                for sz in active_sizes:
                    rat = mountaineer_rat = int(row.get(sz) or 0)
                    display_row[sz] = mountaineer_rat
                    current_balance[sz] = max(0, current_balance[sz] - (mountaineer_rat * layers))
                
                # Tính các chỉ số kỹ thuật chuyên sâu theo ảnh mẫu
                fabric_needed = (m_len + db_m) * layers if layers > 0 else 0.0
                display_row["Dài SĐ YC (M)"] = m_len
                display_row["Hiệu suất SĐ (%)"] = f"{eff_sd}%" if m_len > 0 else ""
                display_row["Đầu bàn (M)"] = db_m
                display_row["SL Vải TT Cần Cắt"] = round(fabric_needed, 1)
                display_row["Hiệu suất chung"] = f"{round(eff_sd * 0.98, 1)}%" if m_len > 0 else ""
                final_factory_rows.append(display_row)

            # Chèn dòng Balance phân tách
            bal_row_t1 = {"BÀN CẮT/TÊN SĐ": "Dư lượng sau T1"}
            for sz in active_sizes: bal_row_t1[sz] = current_balance[sz]
            final_factory_rows.append(bal_row_t1)

            # 2. Đưa dữ liệu Tầng 2 (Tự động vét hình tháp) vào danh sách hiển thị
            if st.session_state["auto_cutting_results"]:
                for item in st.session_state["auto_cutting_results"]:
                    name = item["Sơ đồ / Trạng thái"]
                    layers = item["Số lớp"]
                    r_sum = sum(item["Ratios"].values())
                    total_cut_pcs = r_sum * layers
                    
                    display_row = {"BÀN CẮT/TÊN SĐ": name, "Số lớp": layers, "Tổng SL Cắt": total_cut_pcs}
                    for sz in active_sizes:
                        rat = item["Ratios"].get(sz, 0)
                        display_row[sz] = rat
                        current_balance[sz] = max(0, current_balance[sz] - (rat * layers))
                    
                    # Giả định thông số hình học cho cấu trúc tự động
                    m_len_est = round(max_table_length * 0.8, 2)
                    fabric_needed = (m_len_est + 0.15) * layers
                    display_row["Dài SĐ YC (M)"] = m_len_est
                    display_row["Hiệu suất SĐ (%)"] = "83.2%"
                    display_row["Đầu bàn (M)"] = 0.15
                    display_row["SL Vải TT Cần Cắt"] = round(fabric_needed, 1)
                    display_row["Hiệu suất chung"] = "81.5%"
                    final_factory_rows.append(display_row)

            # Dòng tổng kết cuối cùng của toàn nhà máy
            df_final_factory_report = pd.DataFrame(final_factory_rows)
            
            # --- HIỂN THỊ MULTI-INDEX 2 TẦNG CHUẨN XƯỞNG MAY ---
            web_multi_cols = [("THÔNG TIN GỐC", "BÀN CẮT/TÊN SĐ")]
            for sz in active_sizes:
                web_multi_cols.append(("TỶ LỆ SƠ ĐỒ / SẢN LƯỢNG", f"{sz} (SL: {int(size_breakdown_main.get(sz,0))})"))
            for col in ["Số lớp", "Tổng SL Cắt", "Dài SĐ YC (M)", "Hiệu suất SĐ (%)", "Đầu bàn (M)", "SL Vải TT Cần Cắt", "Hiệu suất chung"]:
                web_multi_cols.append(("THÔNG SỐ TÁC NGHIỆP XƯỞNG CẮT", col))
                
            df_final_factory_report.columns = pd.MultiIndex.from_tuples(web_multi_cols)
            
            # Thiết lập đổ màu tự động làm nổi bật tỷ lệ size nhảy sơ đồ (màu vàng nhạt như mẫu)
            def highlight_factory_grid(x):
                color_df = pd.DataFrame('', index=x.index, columns=x.columns)
                for r in range(len(x)):
                    row_name = str(x.iloc[r, 0])
                    if "Dư lượng" in row_name:
                        color_df.iloc[r, :] = 'background-color: #FEF08A; color: #991B1B; font-weight: 700;'
                    else:
                        for c in range(1, len(x.columns)):
                            val = x.iloc[r, c]
                            if c <= len(active_sizes) and str(val).isdigit() and int(val) > 0:
                                color_df.iloc[r, c] = 'background-color: #FEF9C3; color: #991B1B; font-weight: 700; border: 1px solid #FDE047;'
                return color_df

            st.markdown("<p style='font-weight:700; font-size:13px; color:#0369A1; margin-top:20px;'>🖥️ BẢNG TÁC NGHIỆP HAI TẦNG KỸ THUẬT ĐỐI CHIẾU SẢN LƯỢNG THỜI GIAN THỰC</p>", unsafe_allow_html=True)
            st.dataframe(df_final_factory_report.style.apply(highlight_factory_grid, axis=None), use_container_width=True, hide_index=True)
            
            # Nhúng CSS khóa cố định dải màu 2 tầng tiêu đề phẳng sạch sẽ
            st.markdown("""
                <style>
                    th.col_heading.level0 { background-color: #3B82F6 !important; color: #FFFFFF !important; font-weight: 700 !important; text-align: center !important; }
                    th.col_heading.level1 { background-color: #EFF6FF !important; color: #1E3A8A !important; font-weight: 700 !important; text-align: center !important; }
                </style>
            """, unsafe_allow_html=True)
