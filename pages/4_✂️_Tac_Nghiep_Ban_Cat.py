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
        # TẦNG 3: XOAY TRỤC MA TRẬN ĐỂ HIỂN THỊ ĐÚNG CHUẨN FORM EXCEL CỦA NHÀ MÁY
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

            parsed_size_columns = []
            for col_name in active_sizes:
                col_clean = str(col_name).strip().replace("'", "").replace('"', '').replace("(", "").replace(")", "")
                giang_val, size_val = "None", col_clean
                lower_clean = col_clean.lower()
                matched_group = None
                for group_name in ["regular", "missy", "petite", "pety", "tall", "plus", "misy"]:
                    if group_name in lower_clean: matched_group = group_name.upper(); break
                if matched_group:
                    giang_val = matched_group
                    size_val = re.sub(r'(regular|missy|petite|pety|tall|plus|misy)[\sXx\-\/:]*', '', col_clean, flags=re.IGNORECASE).strip()
                elif "giàng" in lower_clean or any(c in lower_clean for c in ["x", "-", "/"]):
                    parts = re.split(r'[\sXx\-\/:]+', col_clean)
                    parts_clean = [p.strip() for p in parts if p.strip().lower() not in ["giàng", "size", "sl", "siz"]]
                    if len(parts_clean) >= 2: giang_val, size_val = parts_clean, parts_clean
                    elif len(parts_clean) == 1: size_val = parts_clean
                if size_val == "": size_val = col_clean
                parsed_size_columns.append({"original": col_name, "size": size_val, "giang": giang_val})

            matrix_data = [{"BÀN CẮT/TÊN SƠ ĐỒ": item["Sơ đồ / Trạng thái"], **{sz: item["Ratios"].get(sz, 0) for sz in active_sizes}} for item in st.session_state["auto_cutting_results"]]
            df_matrix = pd.DataFrame(matrix_data).set_index("BÀN CẮT/TÊN SƠ ĐỒ")

            # Xoay bảng phẳng đưa size ra làm Index dọc bên trái
            df_matrix_rotated = df_matrix.T
            giang_list, size_list, po_qty_list = [], [], []
            for orig_key in df_matrix_rotated.index:
                p_info = next(i for i in parsed_size_columns if i["original"] == orig_key)
                giang_list.append(p_info["giang"])
                size_list.append(p_info["size"])
                po_qty_list.append(int(size_breakdown_main.get(orig_key, 0)))
                
            df_matrix_rotated.insert(0, "SẢN LƯỢNG", po_qty_list)
            df_matrix_rotated.insert(0, "SIZE", size_list)
            df_matrix_rotated.insert(0, "GIÀNG", giang_list)
            df_excel_style = df_matrix_rotated.set_index(["GIÀNG", "SIZE", "SẢN LƯỢNG"]).T
            tech_rows = []
            total_fabric_m, total_cut_pcs_sum = 0.0, 0
            for item in st.session_state["auto_cutting_results"]:
                s_name = item["Sơ đồ / Trạng thái"]
                layers, tables, sp_sd = item["Số lớp"], item["Số bàn"], item["Số sp/SĐ"]
                m_len = cad_lengths_map.get(s_name.lower().strip(), 0.0) if st.session_state.get("consumption_activated") else 0.0
                vail_can_m = m_len * layers * tables
                total_fabric_m += vail_can_m
                pcs_cut = sum(item["Ratios"].values()) * layers * tables
                total_cut_pcs_sum += pcs_cut
                dm_sd = (vail_can_m * 1.09361) / pcs_cut if pcs_cut > 0 else 0.0
                tech_rows.append({"SƠ LỚP": layers, "SỐ BÀN": tables, "DÀI SƠ ĐỒ": m_len, "SỐ SP/SĐ": sp_sd, "Đ.MỨC SĐ": round(dm_sd, 3), "VẢI CẦN (M)": round(vail_can_m, 1)})
                
            df_tech = pd.DataFrame(tech_rows, index=df_excel_style.index)
            df_final_report = pd.concat([df_excel_style, df_tech], axis=1)

            st.markdown("""<style>
                th.row_heading.level1 { background-color: #FDE047 !important; color: #000000 !important; font-weight: 800 !important; }
                th.row_heading.level0 { background-color: #CBD5E1 !important; color: #1E293B !important; font-weight: 800 !important; }
                th.col_heading { background-color: #D1FAE5 !important; color: #065F46 !important; font-weight: 700 !important; border: 1px solid #A7F3D0 !important; }
            </style>""", unsafe_allow_html=True)

            st.markdown("<p style='font-weight:700; font-size:14px; color:#1E3A8A; margin-top:15px;'>📊 GIAO DIỆN BÀN CẮT ĐA GIÀNG ĐỒNG BỘ MẪU EXCEL NHÀ MÁY DNA</p>", unsafe_allow_html=True)
            st.dataframe(df_final_report, use_container_width=True)
            
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
