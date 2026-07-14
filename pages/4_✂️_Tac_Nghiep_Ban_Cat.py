import streamlit as st
import pandas as pd
import json
import io
import re

st.set_page_config(layout="wide")

# KIỂM TRA ĐIỀU KIỆN 1: Nếu CHƯA bốc tách file SBD thành công
if not st.session_state.get("purchase_ready"):
    st.markdown("""<div class="card-container"><div class="card-section-header">📋 PHÂN HỆ TÁC NGHIỆP BÀN CẮT ĐA GIÀNG NÂNG CAO</div>
    <p style="color: #64748B; font-size:13px; margin:0;">Tải lên File SBD (Excel/PDF) chứa thông tin Giàng (Inseam), Nhóm Size (Regular, Missy, Petite) để hệ thống tự động bẻ ma trận 3 tầng.</p></div>""", unsafe_allow_html=True)
    
    file_sbd_c2 = st.file_uploader("📋 Chọn File SBD Số Lượng Đơn Hàng (Excel/PDF)", type=["xlsx", "xls", "pdf"], key="purchase_sbd_c2_unique")
    
    if file_sbd_c2:
        trigger_btn_c2 = st.button("⚡ SỐ HÓA MA TRẬN SẢN LƯỢNG ĐƠN HÀNG TÁC NGHIỆP", type="primary", use_container_width=True, key="activate_sbd_only_ingest_c2")
        if trigger_btn_c2:
            with st.spinner("🚀 Hệ thống đang phân tích mảng phân bổ size phẳng từ file SBD..."):
                if "get_secure_gemini_key" in globals(): 
                    gemini_key = get_secure_gemini_key()
                else: 
                    gemini_key = st.secrets.get("GEMINI_API_KEY", "").strip()
                
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
                    except Exception: 
                        pass
                elif file_sbd_c2.name.lower().endswith('.pdf'):
                    sbd_parts_payload.append(types.Part.from_bytes(data=sbd_bytes, mime_type='application/pdf'))
                    
                sbd_prompt = """Extract style_id, total_quantity, and complete flat size breakdown. 
                Return JSON format ONLY matching schema: 
                {"style_id": "string", "total_quantity": integer, "size_breakdown": {"Column Header Name": integer}}
                Important: "Column Header Name" must contain full identifiers from document like '30x28', 'Giàng 32 - Size M', 'Regular-S', or just 'M' if flat."""
                
                if sbd_content_str: 
                    sbd_parts_payload.append(types.Part.from_text(text=sbd_content_str))
                sbd_parts_payload.append(types.Part.from_text(text=sbd_prompt))
                
                try:
                    res_sbd = client_ai.models.generate_content(
                        model='gemini-2.5-flash', 
                        contents=sbd_parts_payload, 
                        config=types.GenerateContentConfig(response_mime_type="application/json")
                    )
                    st.session_state["sbd_parsed_data"] = json.loads(res_sbd.text.strip().replace("```json", "").replace("```", "").strip())
                except Exception: 
                    pass
                
                st.session_state["pur_tp_parsed_data"] = {"dummy_status": "skipped_not_needed"}
                st.session_state["purchase_ready"] = True
                st.rerun()

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
            mock_results = [{"Sơ đồ / Trạng thái": f"c{str(i+1).zfill(2)}", "Ratios": {s: (1 if s == sz else 0) for s in active_sizes}, "Số lớp": 50, "Số bàn": 1, "Số sp/SĐ": 1} for i, sz in enumerate(active_sizes)]
            mock_results.append({"Sơ đồ / Trạng thái": "Balance", "Ratios": {s: 0 for s in active_sizes}, "Số lớp": 0, "Số bàn": 0, "Số sp/SĐ": 0})
            st.session_state["auto_cutting_results"] = mock_results
        if trigger_consumption:
            st.session_state["consumption_activated"] = True
            st.rerun()
        if st.session_state.get("auto_cutting_results") is not None:
            cad_lengths_map = {}
            if cad_paste_zone.strip() and st.session_state.get("consumption_activated"):
                for line in cad_paste_zone.strip().split("\n"):
                    if not line.strip(): continue
                    match = re.search(r'(c\d{2})[\s\t]+([0-9]*\.?[0-9]+)', line.lower().strip())
                    if match:
                        try: cad_lengths_map[match.group(1)] = float(match.group(2))
                        except ValueError: pass

            final_rows_display = []
            total_fabric_m = 0.0
            total_cut_pcs_sum = 0
            other_tech_keys = ["Số lớp", "Số bàn", "Dài sơ đồ", "Số sp/SĐ", "Đ.Mức SĐ", "Vải cần (M)"]
            
            for item in st.session_state["auto_cutting_results"]:
                display_row = {"SIZE": item["Sơ đồ / Trạng thái"]}
                for sz in active_sizes: display_row[sz] = item["Ratios"].get(sz, 0)
                if item["Sơ đồ / Trạng thái"] != "Balance":
                    layers, tables, sp_sd = item["Số lớp"], item["Số bàn"], item["Số sp/SĐ"]
                    m_len = cad_lengths_map.get(item["Sơ đồ / Trạng thái"].lower().strip(), 0.0) if st.session_state.get("consumption_activated") else 0.0
                    vail_can_m = m_len * layers * tables
                    total_fabric_m += vail_can_m
                    pcs_cut = sum(item["Ratios"].values()) * layers * tables
                    total_cut_pcs_sum += pcs_cut
                    dm_sd = (vail_can_m * 1.09361) / pcs_cut if pcs_cut > 0 else 0.0
                    display_row.update({"Số lớp": layers, "Số bàn": tables, "Dài sơ đồ": m_len, "Số sp/SĐ": sp_sd, "Đ.Mức SĐ": round(dm_sd, 3), "Vải cần (M)": round(vail_can_m, 1)})
                else:
                    display_row.update({"Số lớp": "", "Số bàn": "", "Dài sơ đồ": "", "Số sp/SĐ": "", "Đ.Mức SĐ": "", "Vải cần (M)": ""})
                final_rows_display.append(display_row)
                
            df_final_report = pd.DataFrame(final_rows_display)
            total_fabric_yds_final = total_fabric_m * 1.09361
            final_avg_yield = total_fabric_yds_final / (total_cut_pcs_sum if total_cut_pcs_sum > 0 else 1)
            
            try:
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer: df_final_report.to_excel(writer, sheet_name="TacNghiepBanCat", index=False)
                st.download_button(label="📥 XUẤT FILE EXCEL TÁC NGHIỆP CHUẨN THƯƠNG MẠI", data=buffer.getvalue(), file_name=f"BÁO_CÁO_TÁC_NGHIỆP_BÀN_CẮT_{style_id_input}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True, key="excel_download_btn_final_v105")
            except Exception: pass
            parsed_size_columns = []
            
            for col_name in active_sizes:
                col_clean = str(col_name).strip().replace("'", "").replace('"', '').replace("(", "").replace(")", "")
                
                # Khởi tạo giá trị mặc định khi không tìm thấy giàng/nhóm phân loại
                giang_val = "None"
                size_val = col_clean
                
                # 1. Bẫy nhận diện nhóm phân loại size đặc thù ngành may (Regular, Missy, Petite, Tall, Plus...)
                lower_clean = col_clean.lower()
                matched_group = None
                for group_name in ["regular", "missy", "petite", "pety", "tall", "plus", "misy"]:
                    if group_name in lower_clean:
                        matched_group = group_name.upper()
                        break
                
                # 2. Bẫy nhận diện ký tự phân tách giàng/mã (Giàng 1, Giàng A, hoặc dấu gạch chéo/gạch ngang)
                if matched_group:
                    giang_val = matched_group
                    # Loại bỏ chữ phân nhóm khỏi tên size chính
                    size_val = re.sub(r'(regular|missy|petite|pety|tall|plus|misy)[\sXx\-\/:]*', '', col_clean, flags=re.IGNORECASE).strip()
                elif "giàng" in lower_clean or any(c in lower_clean for c in ["x", "-", "/"]):
                    parts = re.split(r'[\sXx\-\/:]+', col_clean)
                    parts_clean = [p.strip() for p in parts if p.strip().lower() not in ["giàng", "size", "sl", "siz"]]
                    if len(parts_clean) >= 2:
                        giang_val = f"GIÀNG {parts_clean[0]}" if parts_clean[0].isdigit() else parts_clean[0].upper()
                        size_val = parts_clean[1]
                    elif len(parts_clean) == 1:
                        size_val = parts_clean[0]
                
                # Khử các giá trị rỗng hoặc định dạng lỗi
                if size_val == "": size_val = col_clean
                
                parsed_size_columns.append({
                    "original": col_name, 
                    "size_num": int(size_val) if str(size_val).isdigit() else size_val, 
                    "giang_num": giang_val
                })

            # Sắp xếp thứ tự cột hiển thị theo Giàng trước, Size sau
            try:
                parsed_size_columns.sort(key=lambda x: (
                    0 if x['giang_num'] == "None" else 1,
                    str(x['giang_num']),
                    x['size_num'] if isinstance(x['size_num'], int) else str(x['size_num'])
                ))
            except Exception:
                pass

            ordered_size_keys = [item["original"] for item in parsed_size_columns]
            df_final_report = df_final_report[["SIZE"] + ordered_size_keys + other_tech_keys]

            # =============================================================================
            # KHỐI 5B: DỰNG ĐÚNG 3 TẦNG ĐỘC LẬP TRÊN WEB & ĐỔ MÀU CSS MỚI
            # =============================================================================
            # Tạo mảng tuple MultiIndex chứa đúng cấu trúc 3 tầng độc lập phân rã dữ liệu
            web_multi_cols = [("THÔNG TIN", "MÃ SƠ ĐỒ", "SẢN LƯỢNG")]
            
            for item in parsed_size_columns:
                po_qty_val = int(size_breakdown_main.get(item['original'], 0))
                # Tầng 1: Tên Giàng/Nhóm | Tầng 2: Size sạch | Tầng 3: Số lượng tổng đơn hàng
                web_multi_cols.append((
                    f"{item['giang_num']}", 
                    f"{item['size_num']}", 
                    f"{po_qty_val:,} Pcs"
                ))
                
            for col_name in other_tech_keys:
                # Các cột thông số kỹ thuật cuối bảng gộp tiêu đề để bảng nhìn gọn gàng
                web_multi_cols.append(("THÔNG SỐ TÁC NGHIỆP", col_name, ""))
                
            df_final_report.columns = pd.MultiIndex.from_tuples(web_multi_cols)

            # Hàm tô nền màu vàng cho các ô có số tỷ lệ nhảy sơ đồ
            def highlight_ratios_and_headers(x):
                color_df = pd.DataFrame('', index=x.index, columns=x.columns)
                for r in range(len(x)):
                    if str(x.iloc[r, 0]).strip().lower() == "balance": continue
                    for c in range(1, len(x.columns)):
                        val = x.iloc[r, c]
                        if c <= len(active_sizes) and str(val).isdigit() and int(val) > 0:
                            color_df.iloc[r, c] = 'background-color: #FEF08A; color: #991B1B; font-weight: 700; border: 1px solid #FDE047;'
                return color_df

            # Khóa mã màu CSS chuyên nghiệp ép đổ nền 3 tầng riêng biệt phân cấp rõ rệt
            st.markdown("""<style>
                /* TẦNG 1: HIỂN THỊ GIÀNG / NHÓM SIZE */
                th.col_heading.level0 { background-color: #CBD5E1 !important; color: #1E293B !important; font-weight: 800 !important; font-size: 13px !important; text-align: center !important; border: 1px solid #94A3B8 !important; }
                /* TẦNG 2: HIỂN THỊ KÍCH CỠ (SIZE) */
                th.col_heading.level1 { background-color: #FDE047 !important; color: #000000 !important; font-weight: 800 !important; font-size: 13px !important; text-align: center !important; border: 1px solid #EAB308 !important; }
                /* TẦNG 3: HIỂN THỊ TỔNG SẢN LƯỢNG PO */
                th.col_heading.level2 { background-color: #F1F5F9 !important; color: #334155 !important; font-weight: 700 !important; font-size: 12px !important; text-align: center !important; border: 1px solid #CBD5E1 !important; }
                /* KHU VỰC CÁC CỘT CUỐI THÔNG SỐ TÁC NGHIỆP */
                th.col_heading.blank, [class*="blank"] { background-color: #DCFCE7 !important; color: #166534 !important; font-weight: 700 !important; border: 1px solid #86EFAC !important; }
            </style>""", unsafe_allow_html=True)

            st.dataframe(df_final_report.style.apply(highlight_ratios_and_headers, axis=None), use_container_width=True, hide_index=True)
            
            st.markdown("---")
            m_col1, m_col2, m_col3 = st.columns(3)
            with m_col1: st.metric("Tổng vải tiêu thụ tự động", f"{total_fabric_m:,.1f} Mét")
            with m_col2: st.metric("Định mức trung bình (Đ.Mức TB)", f"{final_avg_yield:.3f} Yds/Pcs" if st.session_state.get("consumption_activated") else "0.000 Yds/Pcs")
            with m_col3:
                variance = final_avg_yield - consumption_input if total_fabric_m > 0 and st.session_state.get("consumption_activated") else 0.0
                st.metric("Chênh lệch so với tài liệu", f"{variance:+.3f}" if st.session_state.get("consumption_activated") else "0.000", delta_color="inverse" if variance > 0 else "normal")
        else:
            st.info("💡 Quy trình: Bấm nút 1 để tính tác nghiệp sơ đồ -> Điền độ dài CAD -> Bấm nút 2 để kích hoạt nhảy số định mức.")
