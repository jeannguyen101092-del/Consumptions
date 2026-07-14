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
               # =============================================================================
               # =============================================================================
                # =============================================================================
               # =============================================================================
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

        input_col4, input_col5, input_col6 = st.columns(3)
        with input_col4: max_table_length = st.number_input("📏 Chiều gia tối đa bàn vải (Meters):", value=12.00, step=1.0)
        with input_col5: fabric_type_input = st.selectbox("🧵 Loại vải tác nghiệp:", ["CHÍNH", "LÓT", "PHỐI"], key="c2_fabric_type_select")
        with input_col6: cuttable_width_inch = st.number_input("📐 KHỔ CẮT (Khổ vải đi sơ đồ - Inches):", value=56.00, step=0.50, format="%.2f")
        
        cad_paste_zone = st.text_area("Sau khi xem cấu trúc phối size phía dưới, hãy đi sơ đồ trên máy CAD rồi copy dán kết quả [Tên sơ đồ + Chiều dài mét] vào đây:", placeholder="Ví dụ dán bảng từ Excel CAD:\n5844-c01 1.05\n5844-c02 10", height=90, key="cad_bulk_paste_c2")
        
        active_sizes = [str(k) for k, v in size_breakdown_main.items() if int(v) > 0]
        if not active_sizes: active_sizes = ["S", "M", "L", "XL", "2XL", "3XL"]
        
        btn_col1, btn_col2 = st.columns(2)
        with btn_col1: trigger_auto_cutting = st.button("⚡ 1. KÍCH HOẠT TÍNH TÁC NGHIỆP SƠ ĐỒ (THUẬT TOÁN THUẦN)", type="primary", use_container_width=True, key="c2_normal_cut_btn")
        with btn_col2: trigger_consumption = st.button("🤖 2. KÍCH HOẠT NHẢY SỐ ĐỊNH MỨC VÀ ĐỐI CHIẾU CAD", type="secondary", use_container_width=True, key="c2_consumption_btn")

        if trigger_auto_cutting:
            mock_results = [{"Sơ đồ / Trạng thái": f"c{str(i+1).zfill(2)}", "Ratios": {s: (1 if s == sz else 0) for s in active_sizes}, "Số lớp": 50, "Số bàn": 1, "Số sp/SĐ": 1} for i, sz in enumerate(active_sizes)]
            st.session_state["auto_cutting_results"] = mock_results
        if trigger_consumption:
            st.session_state["consumption_activated"] = True
            st.rerun()
            for item in valid_items:
                s_name = str(item["Sơ đồ / Trạng thái"]).strip().upper()
                layers, tables, sp_sd = item["Số lớp"], item["Số bàn"], item["Số sp/SĐ"]
                
                m_len = cad_lengths_map.get(s_name.lower().strip(), 0.0) if st.session_state.get("consumption_activated") else 0.0
                vail_can_m = m_len * layers * tables
                total_ratios_sum = sum(item["Ratios"].values())
                pcs_cut_marker = total_ratios_sum * layers * tables
                dm_sd = (vail_can_m * 1.09361) / pcs_cut_marker if pcs_cut_marker > 0 else 0.0
                
                # 🎯 THUẬT TOÁN ĐỘNG: Tự động bắt loại vải ghép số thứ tự (Ví dụ: CHÍNH1:, LÓT2:)
                marker_num_match = re.search(r'\d+', s_name)
                marker_num_str = str(int(marker_num_match.group(0))) if marker_num_match else "1"
                fabric_prefix = f"{fabric_type_input.strip().upper()}{marker_num_str}:"
                
                # Quét mảng để nhặt các size có tỷ lệ rập lớn hơn 0 ở bàn này
                active_ratio_parts = []
                for sz in active_sizes:
                    sz_clean = str(sz).strip().split(":")[-1].split("/")[-1].split(" ")[-1]
                    r_val = item["Ratios"].get(sz, 0)
                    if r_val > 0:
                        active_ratio_parts.append(f"{sz_clean}/{r_val}")
                
                if active_ratio_parts:
                    ratio_row_title = f"{fabric_prefix} " + " ".join(active_ratio_parts)
                else:
                    ratio_row_title = f"{fabric_prefix} TRỐNG SƠ ĐỒ"

                # A. NẠP DÒNG TỶ LỆ KÈM CHUỖI TÊN BÀN CẮT MỚI VỪA DỰNG
                ratio_row = [ratio_row_title]
                for sz in active_sizes: ratio_row.append(item["Ratios"].get(sz, 0))
                ratio_row.extend([layers, tables, m_len, sp_sd, round(dm_sd, 3), round(vail_can_m, 1)])
                matrix_body_rows.append(ratio_row)
                
                # B. NẠP DÒNG CÒN LẠI LŨY TIẾN KHÔNG ĐỔI
                remaining_row = ["CÒN LẠI"]
                for idx, sz in enumerate(active_sizes):
                    current_ratio = item["Ratios"].get(sz, 0)
                    allocated_pcs = current_ratio * layers * tables
                    remaining_balances[idx] = max(0, remaining_balances[idx] - allocated_pcs)
                    remaining_row.append(f"{remaining_balances[idx]:,}")
                remaining_row.extend(["", "", "", "", "", ""])
                matrix_body_rows.append(remaining_row)

            # Gộp nối toàn bộ dữ liệu cấu trúc phẳng
            final_table_rows = [t_header_ma_hang, t_header_mau, t_header_loai_vai, t1_giang_row, t2_size_row, t3_sl_row] + matrix_body_rows

            clean_headers = ["BÀN CẮT / TÊN SƠ ĐỒ"] + [f"CỠ {i+1}" for i in range(len(active_sizes))] + ["SƠ LỚP", "SỐ BÀN", "DÀI SƠ ĐỒ", "SỐ SP/SĐ", "Đ.MỨC SĐ", "VẢI CẦN (M)"]
            df_final_report = pd.DataFrame(final_table_rows, columns=clean_headers)

            # --- THIẾT LẬP MÃ CSS NHUỘM MÀU CHỮ ĐỎ & NỀN XANH ĐÚNG KHU VỰC EXCEL GỐC ---
            st.markdown("""<style>
                th { background-color: #D1FAE5 !important; color: #065F46 !important; font-weight: 700 !important; text-align: center !important; border: 1px solid #A7F3D0 !important; }
                
                tr:nth-child(1) td, tr:nth-child(2) td, tr:nth-child(3) td { background-color: #E2E8F0 !important; color: #000000 !important; font-weight: 700 !important; text-align: left !important; border: 1px solid #CBD5E1 !important; }
                tr:nth-child(2) td:nth-child(2), tr:nth-child(3) td:nth-child(2) { color: #DC2626 !important; font-weight: 800 !important; font-size: 14px !important; }
                
                tr:nth-child(4) td { background-color: #CBD5E1 !important; color: #000000 !important; font-weight: 800 !important; text-align: center !important; border: 1px solid #94A3B8 !important; }
                tr:nth-child(5) td { background-color: #FDE047 !important; color: #000000 !important; font-weight: 800 !important; text-align: center !important; border: 1px solid #EAB308 !important; }
                tr:nth-child(6) td { background-color: #E2E8F0 !important; color: #1E293B !important; font-weight: 700 !important; text-align: center !important; border: 1px solid #CBD5E1 !important; }
                
                tr:nth-child(even):nth-child(n+7) td { background-color: #EFF6FF !important; color: #1E40AF !important; font-weight: 600 !important; border: 1px solid #BFDBFE !important; }
                
                /* Định dạng cột đầu tiên chứa chuỗi phối size chữ đậm */
                td:nth-child(1) { font-weight: 700 !important; text-align: left !important; padding-left: 10px !important; }
                tr:nth-child(even):nth-child(n+7) td:nth-child(1) { text-align: center !important; padding-left: 0px !important; }
            </style>""", unsafe_allow_html=True)

            st.markdown("<p style='font-weight:700; font-size:14px; color:#1E3A8A; margin-top:15px;'>📊 BẢNG THEO DÕI TÁC NGHIỆP BAN CẮT MULTI-INSEAM CHUẨN EXCEL DNA</p>", unsafe_allow_html=True)
            st.dataframe(df_final_report, use_container_width=True, hide_index=True)
            
            st.markdown("---")
            st.success("🎉 Tên các bàn cắt đã tự động chuyển đổi sang định dạng chuỗi phối kích cỡ lót/chính thương mại.")
        else:
            st.info("💡 Quy trình: Bấm nút 1 để tính tác nghiệp sơ đồ -> Điền độ dài CAD -> Bấm nút 2 để kích hoạt nhảy số định mức.")
