import streamlit as st
import pandas as pd
import json
import io
import re

st.set_page_config(layout="wide")

# =============================================================================
# TẦNG 1: SỐ HÓA FILE SBD ĐẦU VÀO
# =============================================================================
if not st.session_state.get("purchase_ready"):
    st.markdown("""<div class="card-container"><div class="card-section-header">📋 PHÂN HỆ TÁC NGHIỆP BÀN CẮT ĐA GIÀNG NÂNG CAO</div>
    <p style="color: #64748B; font-size:13px; margin:0;">Tải lên File SBD (Excel/PDF) chứa thông tin Giàng (Inseam), Nhóm Size để hệ thống tự động bẻ ma trận nằm ngang giống Excel.</p></div>""", unsafe_allow_html=True)
    
    file_sbd_c2 = st.file_uploader("📋 Chọn File SBD Số Lượng Đơn Hàng (Excel/PDF)", type=["xlsx", "xls", "pdf"], key="purchase_sbd_c2_unique")
    if file_sbd_c2:
        trigger_btn_c2 = st.button("⚡ SỐ HÓA MA TRẬN SẢN LƯỢNG ĐƠN HÀNG TÁC NGHIỆP", type="primary", use_container_width=True, key="activate_sbd_only_ingest_c2")
        if trigger_btn_c2:
            with st.spinner("🚀 Hệ thống đang phân tích mảng phân bổ size phẳng từ file SBD..."):
                if "get_secure_gemini_key" in globals(): gemini_key = get_secure_gemini_key()
                else: gemini_key = st.secrets.get("GEMINI_API_KEY", "").strip()
                
                from google import genai
                from google.genai import types
                
                client_ai = genai.Client(api_key=gemini_key)
                sbd_bytes = file_sbd_c2.getvalue()
                sbd_content_str = ""
                sbd_parts_payload = []
                
                if file_sbd_c2.name.lower().endswith(('.xlsx', '.xls')):
                    try:
                        excel_data = pd.read_excel(io.BytesIO(sbd_bytes), sheet_name=None)
                        for sheet_name, df_sheet in excel_data.items():
                            sbd_content_str += f"\n--- SHEET: {sheet_name} ---\n{df_sheet.fillna('').to_csv(index=False)}"
                    except Exception: pass
                elif file_sbd_c2.name.lower().endswith('.pdf'):
                    sbd_parts_payload.append(types.Part.from_bytes(data=sbd_bytes, mime_type='application/pdf'))
                    
                sbd_prompt = 'Extract style_id, total_quantity, and complete flat size breakdown. Return JSON format ONLY matching schema: {"style_id": "string", "total_quantity": integer, "size_breakdown": {"Column Header Name": integer}}'
                if sbd_content_str: sbd_parts_payload.append(types.Part.from_text(text=sbd_content_str))
                sbd_parts_payload.append(types.Part.from_text(text=sbd_prompt))
                
                try:
                    res_sbd = client_ai.models.generate_content(model='gemini-2.5-flash', contents=sbd_parts_payload, config=types.GenerateContentConfig(response_mime_type="application/json"))
                    st.session_state["sbd_parsed_data"] = json.loads(res_sbd.text.strip().replace("```json", "").replace("```", "").strip())
                except Exception: pass
                
                st.session_state["pur_tp_parsed_data"] = {"dummy_status": "skipped_not_needed"}
                st.session_state["purchase_ready"] = True
                st.rerun()
# =============================================================================
# TẦNG 2: MÀN HÌNH TÁC NGHIỆP FORM NHẬP LIỆU
# =============================================================================
else:
    sbd_data_store = st.session_state.get("sbd_parsed_data", {})
    if isinstance(sbd_data_store, dict) and sbd_data_store:
        detected_style_id = sbd_data_store.get("style_id", "UNKNOWN_STYLE")
        detected_total_po = sbd_data_store.get("total_quantity", 0)
        size_breakdown_main = sbd_data_store.get("size_breakdown", {})

        if st.button("🔄 Tải lên File SBD Khác", type="secondary"):
            st.session_state["purchase_ready"] = False
            st.session_state["sbd_parsed_data"] = {}
            st.session_state["consumption_activated"] = False
            st.session_state["auto_cutting_results"] = None
            st.rerun()

        st.markdown("#### 📋 KHAI BÁO THÔNG SỐ TÁC NGHIỆP ĐƠN HÀNG VÀ BÀN VẢI MULTI-INSEAM")
        input_col1, input_col2, input_col3 = st.columns(3)
        with input_col1: style_id_input = st.text_input("🏷️ Tên mã hàng (Style ID):", value=str(detected_style_id).strip().upper())
        with input_col2: po_qty_input = st.number_input("📦 Số lượng đơn hàng (PO Pcs):", value=int(detected_total_po), step=100)
        with input_col3: consumption_input = st.number_input("🎯 Định mức tài liệu đề xuất (Yds/Pcs):", value=1.140, step=0.001, format="%.3f")

        input_col4, input_col6 = st.columns(2)
        with input_col4: max_table_length = st.number_input("📏 Chiều gia tối đa bàn vải (Meters):", value=12.00, step=1.0)
        with input_col6: cuttable_width_inch = st.number_input("📐 KHỔ CẮT (Khổ vải đi sơ đồ - Inches):", value=56.00, step=0.50, format="%.2f")
        
        cad_paste_zone = st.text_area("Sau khi xem cấu trúc phối size phía dưới, hãy đi sơ đồ trên máy CAD rồi copy dán kết quả [Tên sơ đồ + Chiều dài mét] vào đây:", placeholder="Ví dụ dán bảng từ Excel CAD:\n5844-c01 1.05\n5844-c02 10", height=90, key="cad_bulk_paste_c2")
        
        active_sizes = [str(k) for k, v in size_breakdown_main.items() if int(v) > 0]
        if not active_sizes: active_sizes = ["S", "M", "L", "XL", "2XL", "3XL"]
        
        btn_col1, btn_col2 = st.columns(2)
        with btn_col1: trigger_auto_cutting = st.button("⚡ 1. KÍCH HOẠT TÍNH TÁC NGHIỆP SƠ ĐỒ (THUẬT TOÁN THUẦN)", type="primary", use_container_width=True, key="c2_normal_cut_btn")
        with btn_col2: trigger_consumption = st.button("🤖 2. KÍCH HOẠT NHẢY SỐ ĐỊNH MỨC VÀ ĐỐI CHIẾU CAD", type="secondary", use_container_width=True, key="c2_consumption_btn")

        if trigger_auto_cutting:
            mock_results = [{"Sơ đồ / Trạng thái": f"P{str(i+4).zfill(2)}", "Ratios": {s: (1 if s == sz else 0) for s in active_sizes}, "Số lớp": 50, "Số bàn": 1, "Số sp/SĐ": 1} for i, sz in enumerate(active_sizes)]
            st.session_state["auto_cutting_results"] = mock_results
        if trigger_consumption:
            st.session_state["consumption_activated"] = True
            st.rerun()
                # =============================================================================
                # =============================================================================
        # TẦNG 3: SỬA LỖI VALUEERROR - CHUẨN HÓA KHUNG DỮ LIỆU PHẲNG CHUẨN APACHE ARROW
        # =============================================================================
        if st.session_state.get("auto_cutting_results") is not None:
            cad_lengths_map = {}
            if cad_paste_zone.strip() and st.session_state.get("consumption_activated"):
                for line in cad_paste_zone.strip().split("\n"):
                    if not line.strip(): continue
                    match = re.search(r'(p\d{2}|c\d{2})[\s\t]+([0-9]*\.?[0-9]+)', line.lower().strip())
                    if match:
                        try: cad_lengths_map[match.group(1)] = float(match.group(2))
                        except ValueError: pass

            # 1. Thuật toán phân rã chuỗi để bẻ dấu ngoặc đơn rác (Tuple)
            giang_list = []
            size_list = []
            po_qty_list = []
            
            for col_name in active_sizes:
                col_str = str(col_name).strip().replace("'", "").replace('"', '').replace("(", "").replace(")", "")
                giang_val = "None"
                size_val = col_str
                
                parts = re.split(r'[\sXx\-\/:]+', col_str)
                parts_clean = [p.strip() for p in parts if p.strip()]
                
                if len(parts_clean) >= 2:
                    giang_val = parts_clean[0]
                    size_val = parts_clean[1]
                elif len(parts_clean) == 1:
                    size_val = parts_clean[0]
                    
                po_val = int(size_breakdown_main.get(col_name, 0))
                giang_list.append(f"GIÀNG {giang_val}" if giang_val != "None" else "None")
                size_list.append(size_val)
                po_qty_list.append(f"{po_val:,}")

            # 2. Thu thập dữ liệu tỷ lệ ma trận từ kết quả thuật toán
            matrix_rows = []
            col_headers = []
            for item in st.session_state["auto_cutting_results"]:
                r_name = str(item["Sơ đồ / Trạng thái"]).strip()
                if r_name.lower() == "balance": continue
                
                col_headers.append(r_name)
                matrix_rows.append([item["Ratios"].get(sz, 0) for sz in active_sizes])
                
            # Tạo DataFrame ma trận tỷ lệ đã xoay trục nằm ngang
            df_matrix_transposed = pd.DataFrame(matrix_rows, index=col_headers, columns=active_sizes).T
            # 3. Tính toán thông số kỹ thuật (Số lớp, số bàn...) chạy ngang theo mã sơ đồ
            tech_cols_dict = {"SƠ LỚP": [], "SỐ BÀN": [], "DÀI SƠ ĐỒ": [], "SỐ SP/SĐ": [], "Đ.MỨC SĐ": [], "VẢI CẦN (M)": []}
            total_fabric_m, total_cut_pcs_sum = 0.0, 0
            
            valid_items = [i for i in st.session_state["auto_cutting_results"] if str(i["Sơ đồ / Trạng thái"]).strip().lower() != "balance"]
            for item in valid_items:
                s_name = str(item["Sơ đồ / Trạng thái"]).strip()
                layers, tables, sp_sd = item["Số lớp"], item["Số bàn"], item["Số sp/SĐ"]
                
                m_len = cad_lengths_map.get(s_name.lower().strip(), 0.0) if st.session_state.get("consumption_activated") else 0.0
                vail_can_m = m_len * layers * tables
                total_fabric_m += vail_can_m
                
                pcs_cut = sum(item["Ratios"].values()) * layers * tables
                total_cut_pcs_sum += pcs_cut
                dm_sd = (vail_can_m * 1.09361) / pcs_cut if pcs_cut > 0 else 0.0
                
                tech_cols_dict["SƠ LỚP"].append(layers)
                tech_cols_dict["SỐ BÀN"].append(tables)
                tech_cols_dict["DÀI SƠ ĐỒ"].append(m_len)
                tech_cols_dict["SỐ SP/SĐ"].append(sp_sd)
                tech_cols_dict["Đ.MỨC SĐ"].append(round(dm_sd, 3))
                tech_cols_dict["VẢI CẦN (M)"].append(round(vail_can_m, 1))

            # 4. KỸ THUẬT TIÊN QUYẾT: Dựng bảng phẳng hoàn chỉnh bằng Dictionary để tránh lỗi đồng bộ của Pandas
            flat_report_data = {
                "GIÀNG": giang_list,
                "SIZE": size_list,
                "SẢN LƯỢNG": po_qty_list
            }
            
            # Đổ dữ liệu ma trận tỷ lệ sơ đồ vào khung phẳng
            for idx, h_name in enumerate(col_headers):
                flat_report_data[str(h_name)] = df_matrix_transposed[h_name].tolist()
                
            # Đổ dữ liệu các cột kỹ thuật chạy ngang vào khung phẳng
            for tech_key in ["SƠ LỚP", "SỐ BÀN", "DÀI SƠ ĐỒ", "SỐ SP/SĐ", "Đ.MỨC SĐ", "VẢI CẦN (M)"]:
                # Tạo mảng trống điền đầy cho các hàng nhãn Giàng/Size để không lệch cấu trúc hình học
                flat_report_data[tech_key] = tech_cols_dict[tech_key] + [""] * (len(active_sizes) - len(valid_items))

            # Chuyển đổi sang DataFrame Index phẳng sạch hoàn toàn
            df_final_report = pd.DataFrame(flat_report_data)
            df_final_report.columns = df_final_report.columns.astype(str) # Ép kiểu chuỗi toàn bộ tiêu đề cột

            # --- THIẾT LẬP MÃ CSS NHUỘM MÀU NỀN CỘT DỌC BÊN TRÁI THEO THỨ TỰ (MẪU EXCEL DNA) ---
            st.markdown("""<style>
                /* Đổ màu nền xám cho cột GIÀNG (Cột số 1 bên trái) */
                td:nth-child(1) { background-color: #CBD5E1 !important; color: #000000 !important; font-weight: 800 !important; text-align: center !important; }
                /* Đổ màu VÀNG CHUẨN EXCEL cho cột kích cỡ SIZE (Cột số 2 bên trái) */
                td:nth-child(2) { background-color: #FDE047 !important; color: #000000 !important; font-weight: 800 !important; text-align: center !important; }
                /* Đổ màu xám nhẹ cho cột SẢN LƯỢNG PO (Cột số 3 bên trái) */
                td:nth-child(3) { background-color: #F1F5F9 !important; color: #334155 !important; font-weight: 600 !important; text-align: center !important; }
                
                /* Tiêu đề thanh ngang chứa mã sơ đồ nhuộm màu Mint nhạt chuyên nghiệp */
                th { background-color: #D1FAE5 !important; color: #065F46 !important; font-weight: 700 !important; border: 1px solid #A7F3D0 !important; text-align: center !important; }
            </style>""", unsafe_allow_html=True)

            st.markdown("<p style='font-weight:700; font-size:14px; color:#1E3A8A; margin-top:15px;'>📊 BẢNG THEO DÕI TÁC NGHIỆP BAN CẮT MULTI-INSEAM CHUẨN EXCEL DNA</p>", unsafe_allow_html=True)
            st.dataframe(df_final_report, use_container_width=True, hide_index=True)
            
            # --- KHỐI THẺ KPI ĐO LƯỜNG TỔNG HỢP ---
            st.markdown("---")
            final_avg_yield = (total_fabric_m * 1.09361) / (total_cut_pcs_sum if total_cut_pcs_sum > 0 else 1)
            m_col1, m_col2, m_col3 = st.columns(3)
            with m_col1: st.metric("Tổng vải tiêu thụ tự động", f"{total_fabric_m:,.1f} Mét")
            with m_col2: st.metric("Định mức trung bình (Đ.Mức TB)", f"{final_avg_yield:.3f} Yds/Pcs" if st.session_state.get("consumption_activated") else "0.000 Yds/Pcs")
            with m_col3:
                variance = final_avg_yield - consumption_input if total_fabric_m > 0 and st.session_state.get("consumption_activated") else 0.0
                st.metric("Chênh lệch so với tài liệu", f"{variance:+.3f}" if st.session_state.get("consumption_activated") else "0.000", delta_color="inverse" if variance > 0 else "normal")
        else:
            st.info("💡 Quy trình: Bấm nút 1 để tính tác nghiệp sơ đồ -> Điền độ dài CAD -> Bấm nút 2 để kích hoạt nhảy số định mức.")
