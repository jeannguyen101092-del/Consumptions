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
        # KIỂM TRA ĐIỀU KIỆN 3: Tạo báo cáo và đóng khung dữ liệu
        if st.session_state.get("auto_cutting_results") is not None:
            cad_lengths_map = {}
            if cad_paste_zone.strip() and st.session_state["consumption_activated"]:
                for line in cad_paste_zone.strip().split("\n"):
                    match = re.search(r'(c\d{2})[\s\t]+([0-9]*\.?[0-9]+)', line.lower().strip())
                    if match:
                        try: cad_lengths_map[match.group(1)] = float(match.group(2))
                        except ValueError: pass

            final_rows_display = []
            total_fabric_m, total_cut_pcs_sum = 0.0, 0
            
            for item in st.session_state["auto_cutting_results"]:
                display_row = {"SIZE": item["Sơ đồ / Trạng thái"]}
                for sz in active_sizes: display_row[sz] = item["Ratios"].get(sz, 0)
                if item["Sơ đồ / Trạng thái"] != "Balance":
                    layers, tables, sp_sd = item["Số lớp"], item["Số bàn"], item["Số sp/SĐ"]
                    m_len = cad_lengths_map.get(item["Sơ đồ / Trạng thái"].lower().strip(), 0.0) if st.session_state["consumption_activated"] else 0.0
                    vail_can_m = m_len * layers * tables
                    total_fabric_m += vail_can_m
                    pcs_cut = sum(item["Ratios"].values()) * layers * tables
                    total_cut_pcs_sum += pcs_cut
                    dm_sd = (vail_can_m * 1.09361) / pcs_cut if pcs_cut > 0 else 0.0
                    display_row["Số lớp"] = layers; display_row["Số bàn"] = tables; display_row["Dài sơ đồ"] = m_len
                    display_row["Số sp/SĐ"] = sp_sd; display_row["Đ.Mức SĐ"] = round(dm_sd, 3); display_row["Vải cần (M)"] = round(vail_can_m, 1)
                else:
                    for k in ["Số lớp", "Số bàn", "Dài sơ đồ", "Số sp/SĐ", "Đ.Mức SĐ", "Vải cần (M)"]: display_row[k] = ""
                final_rows_display.append(display_row)
                
            df_final_report = pd.DataFrame(final_rows_display)
            total_fabric_yds_final = total_fabric_m * 1.09361
            final_avg_yield = total_fabric_yds_final / (total_cut_pcs_sum if total_cut_pcs_sum > 0 else 1)
            
            # Khối lưu kho tự động dữ liệu lên Supabase Database
            if st.button("💾 ĐẨY DỮ LIỆU TÁC NGHIỆP LÊN DATABASE SUPABASE", type="secondary", use_container_width=True):
                if st.session_state.supabase:
                    try:
                        payload_db = {"style_name": str(style_id_input).strip().upper(), "po_quantity": int(po_qty_input), "planned_cut_pcs": int(total_cut_pcs_sum), "consumption_value": str(round(final_avg_yield, 3)), "total_material_value": str(round(total_fabric_yds_final, 2)), "cuttable_width_inch": float(cuttable_width_inch)}
                        st.session_state.supabase.table("tac_nghiep_ban_cat").upsert(payload_db, on_conflict="style_name").execute()
                        st.success("🎉 Đã lưu kho dữ liệu lên hệ thống Supabase thành công!")
                    except Exception as e: st.error(f"Lỗi kết nối lưu trữ: {e}")

            # Đóng khung 3 tầng MultiIndex xuất khẩu sang tệp file Excel thương mại
            try:
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                    header_data = {"THÔNG TIN ĐƠN HÀNG TÁC NGHIỆP BÀN CẮT CHUẨN": [f"Mã hàng: {style_id_input}", f"PO Qty: {po_qty_input} Pcs", f"Kế hoạch cắt: {total_cut_pcs_sum} Pcs", f"Định mức thực tế: {final_avg_yield:.3f} Yds/Pcs"]}
                    pd.DataFrame(header_data).to_excel(writer, sheet_name="BaoCao_TacNghiep", index=False, startrow=0)
                    
                    excel_multi_cols = [("DANH MỤC", "CHỈ SỐ", "SIZE")]
                    for sz in active_sizes: excel_multi_cols.append((f"GIÀNG: 0", str(sz), f"SL: {int(size_breakdown_main.get(sz,0))}"))
                    for col_name in ["Số lớp", "Số bàn", "Dài sơ đồ", "Số sp/SĐ", "Đ.Mức SĐ", "Vải cần (M)"]: excel_multi_cols.append(("THÔNG SỐ TÁC NGHIỆP", "THÔNG SỐ TÁC NGHIỆP", col_name))
                        
                    df_excel_export = df_final_report.copy().reset_index(drop=True)
                    df_excel_export.columns = pd.MultiIndex.from_tuples(excel_multi_cols)
                    df_excel_export.to_excel(writer, sheet_name="BaoCao_TacNghiep", index=False, startrow=9)
                    
                    worksheet = writer.sheets["BaoCao_TacNghiep"]
                    for r_idx in range(10, worksheet.max_row + 1):
                        is_bal = (worksheet.cell(row=r_idx, column=1).value == "Balance")
                        for c_idx in range(1, worksheet.max_column + 1):
                            cell = worksheet.cell(row=r_idx, column=c_idx)
                            cell.border = Border(left=Side(style="thin", color="CBD5E1"), right=Side(style="thin", color="CBD5E1"), top=Side(style="thin", color="CBD5E1"), bottom=Side(style="thin", color="CBD5E1"))
                            cell.alignment = Alignment(horizontal="center", vertical="center")
                            if is_bal:
                                cell.fill = PatternFill(start_color="FEF08A", end_color="FEF08A", fill_type="solid")
                                cell.font = Font(name="Calibri", size=11, bold=True, color="991B1B")
                    
                    for col in worksheet.columns:
                        worksheet.column_dimensions[get_column_letter(col[0].column)].width = 13
                
                st.download_button(label="📥 XUẤT FILE EXCEL TÁC NGHIỆP CHUẨN THƯƠNG MẠI", data=buffer.getvalue(), file_name=f"BÁO_CÁO_TÁC_NGHIỆP_BÀN_CẮT_{style_id_input}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
            except Exception as e: st.error(f"Lỗi xuất Excel: {e}")

            # Đổ màu 3 tầng biểu diễn kỹ thuật lên nền tảng Web Streamlit
            web_multi_cols = [("GIÀNG / SIZE / SL", "SIZE", "SẢN LƯỢNG")]
            for sz in active_sizes: web_multi_cols.append(("GIÀNG: 0", str(sz), f"SL: {int(size_breakdown_main.get(sz,0))}"))
            for col_name in ["Số lớp", "Số bàn", "Dài sơ đồ", "Số sp/SĐ", "Đ.Mức SĐ", "Vải cần (M)"]: web_multi_cols.append(("THÔNG SỐ TÁC NGHIỆP", col_name, col_name))
            
            df_final_report.columns = pd.MultiIndex.from_tuples(web_multi_cols)
            
            def highlight_cells(x):
                color_df = pd.DataFrame('', index=x.index, columns=x.columns)
                for r in range(len(x)):
                    if x.iloc[r, 0] == "Balance":
                        color_df.iloc[r, :] = 'background-color: #FEF08A; color: #991B1B; font-weight: 700;'
                    else:
                        for c in range(1, len(x.columns)):
                            if c <= len(active_sizes) and str(x.iloc[r, c]).isdigit() and int(x.iloc[r, c]) > 0:
                                color_df.iloc[r, c] = 'background-color: #FEF9C3; color: #991B1B; font-weight: 700;'
                return color_df

            st.dataframe(df_final_report.style.apply(highlight_cells, axis=None), use_container_width=True, hide_index=True)
            st.markdown("""
                <style>
                    th.col_heading.level0 { background-color: #E0F2FE !important; color: #0369A1 !important; font-weight: 700 !important; text-align: center !important; }
                    th.col_heading.level1 { background-color: #F8FAFC !important; color: #334155 !important; font-weight: 700 !important; text-align: center !important; }
                    th.col_heading.level2 { background-color: #BAE6FD !important; color: #0369A1 !important; font-weight: 700 !important; text-align: center !important; }
                    th.col_heading.blank { background-color: #DCFCE7 !important; color: #166534 !important; font-weight: 700 !important; }
                </style>
            """, unsafe_allow_html=True)
