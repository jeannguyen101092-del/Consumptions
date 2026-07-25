import streamlit as st
import pandas as pd
import json, io, math, re

st.set_page_config(page_title="PPJ - Tác Nghiệp", layout="wide")

if "purchase_ready" not in st.session_state: st.session_state["purchase_ready"] = False
if "sbd_parsed_data" not in st.session_state: st.session_state["sbd_parsed_data"] = {}
if "auto_cutting_results" not in st.session_state: st.session_state["auto_cutting_results"] = None

st.markdown('<h3 style="color: #1E3A8A;">📋 PHÂN HỆ TÁC NGHIỆP BÀN CẮT ĐA GIÀNG CHUẨN XƯỞNG</h3>', unsafe_allow_html=True)

if not st.session_state["purchase_ready"]:
    file_sbd = st.file_uploader("📋 Chọn File SBD Số Lượng", type=["xlsx", "xls", "pdf"])
    if file_sbd and st.button("⚡ SỐ HÓA ĐƠN HÀNG", type="primary", use_container_width=True):
        st.session_state["sbd_parsed_data"] = {"style_id": "PPJ-DENIM-2026", "total_quantity": 3600, "size_breakdown": {"S": 400, "M": 1200, "L": 1400, "XL": 600}}
        st.session_state["purchase_ready"] = True
        st.rerun()
else:
    sbd_data = st.session_state["sbd_parsed_data"]
    size_breakdown_main = sbd_data["size_breakdown"]
    active_sizes = list(size_breakdown_main.keys())

    style_id_input = st.text_input("🏷️ Style ID:", value=sbd_data["style_id"])
    max_table_length = st.number_input("📏 Chiều dài tối đa bàn (Meters):", value=12.0)
    consumption_input = st.number_input("🎯 Định mức tài liệu đề xuất (Yds):", value=1.140, format="%.3f")

    st.markdown("#### 🏗️ TẦNG 1: TÁC NGHIỆP THỦ CÔNG (NHẬP TAY SƠ ĐỒ)")
    if "manual_cutting_plan" not in st.session_state:
        init_rows = [{"BÀN CẮT/TÊN SĐ": f"M_c0{i}", "Số lớp": 0, "Dài SĐ YC (M)": 0.0, "Hiệu suất SĐ (%)": 82.5, "Đầu bàn (M)": 0.15} for i in range(1, 4)]
        for r in init_rows:
            for sz in active_sizes: r[sz] = 0
        st.session_state["manual_cutting_plan"] = pd.DataFrame(init_rows)

    cfg = {"BÀN CẮT/TÊN SĐ": st.column_config.TextColumn(required=True), "Số lớp": st.column_config.NumberColumn(min_value=0), "Dài SĐ YC (M)": st.column_config.NumberColumn(format="%.2f")}
    for sz in active_sizes: cfg[sz] = st.column_config.NumberColumn(min_value=0)

    edited_df_t1 = st.data_editor(st.session_state["manual_cutting_plan"], column_config=cfg, num_rows="dynamic", use_container_width=True)
    st.session_state["manual_cutting_plan"] = edited_df_t1

    manual_totals = {sz: 0 for sz in active_sizes}
    for _, row in edited_df_t1.iterrows():
        lyr = int(float(row.get("Số lớp") or 0))
        for sz in active_sizes:
            manual_totals[sz] += int(float(row.get(sz) or 0)) * lyr

    remaining_balance_t2 = {sz: max(0, int(size_breakdown_main[sz]) - manual_totals[sz]) for sz in active_sizes}
        st.markdown("#### 🤖 TẦNG 2: TÁC NGHIỆP TỰ ĐỘNG (VÉT SẢN LƯỢNG CÒN LẠI)")
    if st.button("⚡ KÍCH HOẠT TỰ ĐỘNG VÉT HÌNH THÁP", type="primary", use_container_width=True) or st.session_state["auto_cutting_results"] is not None:
        if st.session_state["auto_cutting_results"] is None:
            bal = remaining_balance_t2.copy()
            steps, idx = [], 1
            while sum(bal.values()) > 0 and idx <= 10:
                m_id = f"Auto_c{idx:02d}"
                lyrs = 120 if idx == 1 else 80
                ratios = {sz: 0 for sz in active_sizes}
                for sz in sorted(bal, key=bal.get, reverse=True):
                    if bal[sz] <= 0: continue
                    r_val = min(4, math.floor(bal[sz] / lyrs))
                    if r_val == 0 and bal[sz] > 0: r_val = 1
                    ratios[sz] = r_val
                c_lyrs = min([math.ceil(bal[sz]/r) for sz, r in ratios.items() if r > 0] or [lyrs])
                steps.append({"Sơ đồ / Trạng thái": m_id, "Số lớp": c_lyrs, "Ratios": ratios})
                for sz in active_sizes: bal[sz] = max(0, bal[sz] - (ratios[sz] * c_lyrs))
                idx += 1
            st.session_state["auto_cutting_results"] = steps

        f_rows = []
        cur_bal = {sz: int(size_breakdown_main[sz]) for sz in active_sizes}
        for _, row in edited_df_t1.iterrows():
            lyr = int(float(row.get("Số lớp") or 0))
            m_l = float(row.get("Dài SĐ YC (M)") or 0.0)
            db = float(row.get("Đầu bàn (M)") or 0.0)
            r_sum = sum(int(float(row.get(sz) or 0)) for sz in active_sizes)
            r_dict = {"BÀN CẮT/TÊN SĐ": row.get("BÀN CẮT/TÊN SĐ"), "Số lớp": lyr, "Tổng SL Cắt": r_sum * lyr}
            for sz in active_sizes:
                val = int(float(row.get(sz) or 0))
                r_dict[sz] = val
                cur_bal[sz] = max(0, cur_bal[sz] - (val * lyr))
            r_dict.update({"Dài SĐ YC (M)": m_l, "Hiệu suất SĐ (%)": f"{row.get('Hiệu suất SĐ (%)')}%", "Đầu bàn (M)": db, "SL Vải TT Cần Cắt": round((m_l+db)*lyr, 1), "Hiệu suất chung": "81.0%"})
            f_rows.append(r_dict)

        # Tạo dòng Dư lượng sạch để tránh ép kiểu lỗi
        bal_row = {"BÀN CẮT/TÊN SĐ": "Dư lượng sau T1", "Số lớp": "", "Tổng SL Cắt": ""}
        for sz in active_sizes: bal_row[sz] = cur_bal[sz]
        for c in ["Dài SĐ YC (M)", "Hiệu suất SĐ (%)", "Đầu bàn (M)", "SL Vải TT Cần Cắt", "Hiệu suất chung"]: bal_row[c] = ""
        f_rows.append(bal_row)

        # VÁ LỖI AN TOÀN TẠI ĐÂY: Kiểm tra chuỗi rỗng trước khi xử lý chuyển đổi kiểu số
        if st.session_state["auto_cutting_results"]:
            for item in st.session_state["auto_cutting_results"]:
                raw_lyr = item["Sơ đồ / Trạng thái"] if "Dư lượng" in str(item.get("BÀN CẮT/TÊN SĐ")) else item.get("Số lớp", 0)
                lyr = int(float(raw_lyr)) if pd.notna(raw_lyr) and str(raw_lyr).strip() != "" else 0
                r_sum = sum(item["Ratios"].values())
                r_dict = {"BÀN CẮT/TÊN SĐ": item["Sơ đồ / Trạng thái"], "Số lớp": lyr, "Tổng SL Cắt": r_sum * lyr}
                for sz in active_sizes:
                    r_dict[sz] = int(item["Ratios"].get(sz, 0))
                r_dict.update({"Dài SĐ YC (M)": 9.6, "Hiệu suất SĐ (%)": "83.2%", "Đầu bàn (M)": 0.15, "SL Vải TT Cần Cắt": round(9.75*lyr, 1), "Hiệu suất chung": "81.5%"})
                f_rows.append(r_dict)

        df_rep = pd.DataFrame(f_rows)
        w_cols = [("GỐC", "BÀN CẮT/TÊN SĐ")] + [("SẢN LƯỢNG", f"{s} ({size_breakdown_main[s]})") for s in active_sizes] + [("KỸ THUẬT", c) for c in ["Số lớp", "Tổng SL Cắt", "Dài SĐ YC (M)", "Hiệu suất SĐ (%)", "Đầu bàn (M)", "SL Vải TT Cần Cắt", "Hiệu suất chung"]]
        df_rep.columns = pd.MultiIndex.from_tuples(w_cols)

        def style_g(x):
            c = pd.DataFrame('', index=x.index, columns=x.columns)
            for r in range(len(x)):
                if "Dư lượng" in str(x.iloc[r, 0]): c.iloc[r, :] = 'background-color: #FEF08A; font-weight: 700;'
                else:
                    for col in range(1, len(x.columns)):
                        if col <= len(active_sizes) and str(x.iloc[r, col]).replace('.0','').isdigit() and int(float(x.iloc[r, col] or 0)) > 0:
                            c.iloc[r, col] = 'background-color: #FEF9C3; font-weight: 700;'
            return c

        st.dataframe(df_rep.style.apply(style_g, axis=None), use_container_width=True, hide_index=True)
        st.markdown("<style>th.col_heading.level0{background-color:#3B82F6!important;color:#FFF!important;}th.col_heading.level1{background-color:#EFF6FF!important;color:#1E3A8A!important;}</style>", unsafe_allow_html=True)
