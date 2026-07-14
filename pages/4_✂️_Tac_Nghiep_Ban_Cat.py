import streamlit as st
import pandas as pd
import json
import io
import re

st.set_page_config(layout="wide")

# KIỂM TRA ĐIỀU KIỆN 1: Nếu CHƯA bốc tách file SBD thành công
if not st.session_state.get("purchase_ready"):
    st.markdown("""<div class="card-container"><div class="card-section-header">📋 PHÂN HỆ TÁC NGHIỆP BÀN CẮT ĐA GIÀNG NÂNG CAO</div>
    <p style="color: #64748B; font-size:13px; margin:0;">Tải lên File SBD (Excel/PDF) chứa thông tin Giàng (Inseam), Nhóm Size để hệ thống tự động số hóa ma trận.</p></div>""", unsafe_allow_html=True)
    
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
                    
                sbd_prompt = 'Extract style_id, total_quantity, and complete flat size breakdown. Return JSON format ONLY matching schema: {"style_id": "string", "total_quantity": integer, "size_breakdown": {"Column Header Name": integer}}'
                if sbd_content_str: 
                    sbd_parts_payload.append(types.Part.from_text(text=sbd_content_str))
                sbd_parts_payload.append(types.Part.from_text(text=sbd_prompt))
                
                try:
                    res_sbd = client_ai.models.generate_content(model='gemini-2.5-flash', contents=sbd_parts_payload, config=types.GenerateContentConfig(response_mime_type="application/json"))
                    st.session_state["sbd_parsed_data"] = json.loads(res_sbd.text.strip().replace("```json", "").replace("```", "").strip())
                except Exception: 
                    pass
                
                st.session_state["pur_tp_parsed_data"] = {"dummy_status": "skipped_not_needed"}
                st.session_state["purchase_ready"] = True
                st.rerun()
# KIỂM TRA ĐIỀU KIỆN 2: Nếu ĐÃ số hóa xong file SBD -> Màn hình tác nghiệp sản xuất
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
        input_col1, input_col2, input_col3, input_col_color = st.columns(4)
        with input_col1: style_id_input = st.text_input("🏷️ Tên mã hàng (Style ID):", value=str(detected_style_id).strip().upper())
        with input_col2: po_qty_input = st.number_input("📦 Số lượng đơn hàng (PO Pcs):", value=int(detected_total_po), step=100)
        with input_col3: consumption_input = st.number_input("🎯 Định mức tài liệu đề xuất (Yds/Pcs):", value=1.140, step=0.001, format="%.3f")
        with input_col_color: color_input = st.text_input("🎨 Tự gõ Màu vải:", value="BLACK")
        input_col4, input_col5, input_col6 = st.columns(3)
        with input_col4: max_table_length = st.number_input("📏 Chiều gia tối đa bàn vải (Meters):", value=12.00, step=1.0)
        with input_col5: fabric_type_input = st.text_input("🧵 Tự gõ Loại vải:", value="CHÍNH")
        with input_col6: cuttable_width_inch = st.number_input("📐 KHỔ CẮT (Khổ vải đi sơ đồ - Inches):", value=56.00, step=0.50, format="%.2f")
        
        cad_paste_zone = st.text_area("Sau khi xem cấu trúc phối size phía dưới, hãy đi sơ đồ trên máy CAD rồi copy dán kết quả [Tên sơ đồ + Chiều dài mét] vào đây:", placeholder="Ví dụ dán bảng từ Excel CAD:\n5844-c01 1.05\n5844-c02 10", height=90, key="cad_bulk_paste_c2")
        
        active_sizes = [str(k) for k, v in size_breakdown_main.items() if int(v) > 0]
        if not active_sizes: active_sizes = ["S", "M", "L", "XL", "2XL", "3XL"]
        
        btn_col1, btn_col2 = st.columns(2)
        with btn_col1: trigger_auto_cutting = st.button("⚡ 1. KÍCH HOẠT TÍNH TÁC NGHIỆP SƠ ĐỒ (AI GIẢI MA TRẬN TỶ LỆ)", type="primary", use_container_width=True, key="c2_normal_cut_btn")
        with btn_col2: trigger_consumption = st.button("🤖 2. KÍCH HOẠT NHẢY SỐ ĐỊNH MỨC VÀ ĐỐI CHIẾU CAD", type="secondary", use_container_width=True, key="c2_consumption_btn")
        if trigger_auto_cutting:
            with st.spinner("🤖 AI đang tính toán tổ hợp sơ đồ theo cấu trúc Kim tự tháp ngược..."):
                if "get_secure_gemini_key" in globals(): 
                    gemini_key = get_secure_gemini_key()
                else: 
                    gemini_key = st.secrets.get("GEMINI_API_KEY", "").strip()
                
                from google import genai
                from google.genai import types
                
                client_ai = genai.Client(api_key=gemini_key)
                
                # NÂNG CẤP PROMPT ÉP AI GIẢI THEO NGUYÊN LÝ KIM TỰ THÁP NGƯỢC
                ai_cutting_prompt = f"""
                Bạn là chuyên gia điều độ bàn cắt may mặc công nghiệp. Hãy lập kế hoạch sơ đồ bàn cắt cho đơn hàng này.
                - Ma trận sản lượng PO cần cắt: {json.dumps(size_breakdown_main)}
                - Chiều dài bàn vải tối đa cho phép: {max_table_length} Mét
                - Định mức tài liệu đề xuất: {consumption_input} Yds/Pcs
                - Khổ vải cắt: {cuttable_width_inch} Inches
                - Loại vải: {fabric_type_input}
                
                QUY TẮC PHỐI TỶ LỆ ÉP BUỘC (CẤU TRÚC KIM TỰ THÁP NGƯỢC):
                1. SƠ ĐỒ CHÍNH (BÀN ĐẦU): Gom các size có sản lượng lớn lại với nhau để đi các sơ đồ gộp có tổng tỷ lệ lớn nhất (ví dụ: tổng tỷ lệ bằng 8, 10 hoặc 12 quần trên 1 sơ đồ) sao cho chiều dài sơ đồ đạt sát mức tối đa {max_table_length}m nhằm giải quyết nhanh số lượng lớn.
                2. TRIỆT TIÊU DẦN SẢN LƯỢNG: Trừ lùi sản lượng lũy tiến qua từng bàn, ép sản lượng các size lớn về 0 trước.
                3. SƠ ĐỒ VÉT DƯỚI ĐUÔI (KIM TỰ THÁP NGƯỢC): Ở các bàn cuối cùng, khi sản lượng của các size lớn đã hết, sơ đồ PHẢI vuốt đuôi nhỏ lại, chỉ phối các sơ đồ vét ngắn chứa 1 quần (hoặc tối đa 2 quần) cho các size nhỏ/size lẻ mồ côi còn lại để vét sạch sản lượng.
                
                Đảm bảo số dư 'CÒN LẠI' ở dòng cuối cùng của bảng phải bằng 0 tuyệt đối cho tất cả các cỡ.
                Trả về kết quả duy nhất dạng mảng JSON gốc sạch sẽ:
                [
                    {{"Sơ đồ / Trạng thái": "c01", "Ratios": {{"Tên_Size_A": 3, "Tên_Size_B": 4, "Tên_Size_C": 3}}, "Số lớp": 100, "Số bàn": 1, "Số sp/SĐ": 10}},
                    {{"Sơ đồ / Trạng thái": "c02", "Ratios": {{"Tên_Size_D": 1}}, "Số lớp": 10, "Số bàn": 1, "Số sp/SĐ": 1}}
                ]
                """
                try:
                    res_cutting = client_ai.models.generate_content(
                        model='gemini-2.5-flash', 
                        contents=[ai_cutting_prompt]
                    )
                    st.session_state["auto_cutting_results"] = json.loads(res_cutting.text.strip().replace("```json", "").replace("```", "").strip())
                    st.success("🎯 AI đã tối ưu thành công hệ thống sơ đồ theo phom Kim tự tháp ngược!")
                except Exception:
                    # Khối dự phòng nếu mất kết nối
                    st.session_state["auto_cutting_results"] = [{"Sơ đồ / Trạng thái": f"c{str(i+1).zfill(2)}", "Ratios": {s: (1 if s == sz else 0) for s in active_sizes}, "Số lớp": 50, "Số bàn": 1, "Số sp/SĐ": 1} for i, sz in enumerate(active_sizes)]

        if trigger_consumption:
            st.session_state["consumption_activated"] = True
            st.rerun()


        if st.session_state.get("auto_cutting_results") is not None:
            cad_lengths_map = {}
            if cad_paste_zone.strip() and st.session_state.get("consumption_activated"):
                for line in cad_paste_zone.strip().split("\n"):
                    if not line.strip(): continue
                    match = re.search(r'(p\d{2}|c\d{2})[\s\t]+([0-9]*\.?[0-9]+)', line.lower().strip())
                    if match:
                        try: cad_lengths_map[match.group(1)] = float(match.group(2))
                        except ValueError: pass

            t_header_ma_hang = ["Mã hàng:", f" {style_id_input.strip().upper()}"]
            t_header_mau = ["Màu:", f" {color_input.strip().upper()}"]
            t_header_loai_vai = ["Loại vải:", f" {fabric_type_input.strip().upper()}"]

            t1_giang_row, t2_size_row, t3_sl_row = ["GIÀNG"], ["SIZE"], ["SẢN LƯỢNG"]
            po_qty_matrix = []
            for col_name in active_sizes:
                col_str = str(col_name).strip().replace("'", "").replace('"', '').replace("(", "").replace(")", "")
                giang_val, size_val = "None", col_str
                parts = re.split(r'[\sXx\-\/:]+', col_str)
                parts_clean = [p.strip() for p in parts if p.strip()]
                if len(parts_clean) >= 2: giang_val, size_val = parts_clean, parts_clean
                elif len(parts_clean) == 1: size_val = parts_clean
                po_val = int(size_breakdown_main.get(col_name, 0))
                po_qty_matrix.append(po_val)
                t1_giang_row.append(f"{giang_val}" if giang_val != "None" else "None")
                t2_size_row.append(f"{size_val}")
                t3_sl_row.append(f"{po_val:,}")

            total_cols_count = 1 + len(active_sizes) + 6
            while len(t_header_ma_hang) < total_cols_count: t_header_ma_hang.append("")
            while len(t_header_mau) < total_cols_count: t_header_mau.append("")
            while len(t_header_loai_vai) < total_cols_count: t_header_loai_vai.append("")
            for _ in range(6):
                t1_giang_row.append(""); t2_size_row.append(""); t3_sl_row.append("")

            matrix_body_rows = []
            remaining_balances = list(po_qty_matrix)
            valid_items = [i for i in st.session_state["auto_cutting_results"] if str(i["Sơ đồ / Trạng thái"]).strip().lower() != "balance"]
            for item in valid_items:
                s_name = str(item["Sơ đồ / Trạng thái"]).strip().upper()
                layers, tables, sp_sd = item["Số lớp"], item["Số bàn"], item["Số sp/SĐ"]
                m_len = cad_lengths_map.get(s_name.lower().strip(), 0.0) if st.session_state.get("consumption_activated") else 0.0
                vail_can_m = m_len * layers * tables
                pcs_cut_marker = sum(item["Ratios"].values()) * layers * tables
                dm_sd = (vail_can_m * 1.09361) / pcs_cut_marker if pcs_cut_marker > 0 else 0.0
                
                marker_num_match = re.search(r'\d+', s_name)
                marker_num_str = str(int(marker_num_match.group(0))) if marker_num_match else "1"
                fabric_prefix = f"{fabric_type_input.strip().upper()}{marker_num_str}:"
                
                active_ratio_parts = []
                for sz in active_sizes:
                    sz_clean = str(sz).strip().split(":")[-1].split("/")[-1].split(" ")[-1]
                    if item["Ratios"].get(sz, 0) > 0: active_ratio_parts.append(f"{sz_clean}/{item['Ratios'].get(sz, 0)}")
                ratio_row_title = f"{fabric_prefix} " + " ".join(active_ratio_parts) if active_ratio_parts else f"{fabric_prefix} TRỐNG"

                ratio_row = [ratio_row_title] + [item["Ratios"].get(sz, 0) for sz in active_sizes] + [layers, tables, m_len, sp_sd, round(dm_sd, 3), round(vail_can_m, 1)]
                matrix_body_rows.append(ratio_row)
                
                remaining_row = ["CÒN LẠI"]
                for idx, sz in enumerate(active_sizes):
                    remaining_balances[idx] = max(0, remaining_balances[idx] - (item["Ratios"].get(sz, 0) * layers * tables))
                    remaining_row.append(f"{remaining_balances[idx]:,}")
                remaining_row.extend(["", "", "", "", "", ""])
                matrix_body_rows.append(remaining_row)

            # 🎯 THUẬT TOÁN TÔ MÀU VÀNG CHO Ô CHỨA TỶ LỆ SƠ ĐỒ (RATIOS > 0)
            # 🎯 THUẬT TOÁN ĐỒNG BỘ BIẾN: Tô màu nền vàng cho ô chứa tỷ lệ sơ đồ (Ratios > 0)
            # 🎯 THUẬT TOÁN ĐỒNG BỘ: Tô màu nền vàng cho ô chứa tỷ lệ sơ đồ (Ratios > 0)
            def highlight_ratios(x):
                color_df = pd.DataFrame('', index=x.index, columns=x.columns)
                num_size_cols = len(active_sizes)
                
                for r in range(len(x)):
                    if r < 6: continue
                    if str(x.iloc[r, 0]).strip().upper() == "CÒN LẠI": continue
                    
                    for c in range(1, len(x.columns)):
                        if c <= num_size_cols:
                            val = x.iloc[r, c]
                            try:
                                if pd.notna(val) and float(val) > 0:
                                    color_df.iloc[r, c] = 'background-color: #FEF08A !important; color: #991B1B !important; font-weight: 800 !important; border: 1px solid #FDE047 !important;'
                            except ValueError: pass
                return color_df

            # Ép gán chính xác một tên biến duy nhất xuyên suốt
            styled_report_df = df_final_report.style.apply(highlight_ratios, axis=None)

            st.markdown("""<style>
                th { background-color: #D1FAE5 !important; color: #065F46 !important; font-weight: 700 !important; text-align: center !important; border: 1px solid #A7F3D0 !important; position: sticky; top: 0; z-index: 10; }
                
                tr:nth-child(1) td { position: sticky; top: 25px; z-index: 9; background-color: #E2E8F0 !important; font-weight: 700 !important; }
                tr:nth-child(2) td { position: sticky; top: 50px; z-index: 9; background-color: #E2E8F0 !important; font-weight: 700 !important; }
                tr:nth-child(3) td { position: sticky; top: 75px; z-index: 9; background-color: #E2E8F0 !important; font-weight: 700 !important; }
                tr:nth-child(4) td { position: sticky; top: 100px; z-index: 9; background-color: #CBD5E1 !important; color: #000000 !important; font-weight: 800 !important; text-align: center !important; border: 1px solid #94A3B8 !important; }
                tr:nth-child(5) td { position: sticky; top: 125px; z-index: 9; background-color: #FDE047 !important; color: #000000 !important; font-weight: 800 !important; text-align: center !important; border: 1px solid #EAB308 !important; }
                tr:nth-child(6) td { position: sticky; top: 175px; z-index: 9; background-color: #E2E8F0 !important; color: #1E293B !important; font-weight: 700 !important; text-align: center !important; border: 1px solid #CBD5E1 !important; }
                
                tr:nth-child(1) td, tr:nth-child(2) td, tr:nth-child(3) td { text-align: left !important; border: 1px solid #CBD5E1 !important; }
                tr:nth-child(2) td:nth-child(2), tr:nth-child(3) td:nth-child(2) { color: #DC2626 !important; font-weight: 800 !important; font-size: 14px !important; }
                
                tr:nth-child(even):nth-child(n+7) td { background-color: #EFF6FF !important; color: #1E40AF !important; font-weight: 600 !important; border: 1px solid #BFDBFE !important; }
                td:nth-child(1) { font-weight: 700 !important; text-align: left !important; padding-left: 10px !important; }
                tr:nth-child(even):nth-child(n+7) td:nth-child(1) { text-align: center !important; padding-left: 0px !important; }
            </style>""", unsafe_allow_html=True)

            st.markdown("<p style='font-weight:700; font-size:14px; color:#1E3A8A; margin-top:15px;'>📊 BẢNG THEO DÕI TÁC NGHIỆP BAN CẮT MULTI-INSEAM CHUẨN EXCEL DNA</p>", unsafe_allow_html=True)
            
            # Gọi chính xác tên biến styled_report_df đã khai báo ở trên để hiển thị lên Web
            st.dataframe(styled_report_df, use_container_width=True, hide_index=True)
            st.markdown("---")
            st.success("🎉 Hệ thống ma trận tỷ lệ nhảy rập đã được bôi nền vàng chữ đỏ trực quan thương mại thành công!")
        else:
            st.info("💡 Quy trình: Bấm nút 1 để tính tác nghiệp sơ đồ -> Điền độ dài CAD -> Bấm nút 2 để kích hoạt nhảy số định mức.")
