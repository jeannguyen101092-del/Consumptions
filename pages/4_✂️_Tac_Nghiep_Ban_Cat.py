import streamlit as st
import pandas as pd
import json
import io
import re

# Cấu hình trang luôn luôn đặt ở dòng đầu tiên của ứng dụng
st.set_page_config(layout="wide")

# =============================================================================
# TẦNG 1: KHỞI TẠO CẤU HÌNH HỆ THỐNG VÀ ĐỒNG BỘ THÔNG SỐ TÁC NGHIỆP THỰC TẾ
# =============================================================================

# Khóa cứng luồng luôn hiển thị giao diện tác nghiệp trực tiếp, bỏ hẳn phân hệ upload file SBD
st.session_state["purchase_ready"] = True

# Khởi tạo các biến nhớ toàn cục nền nếu hệ thống vừa kích hoạt phiên làm việc mới
if "active_sizes_global" not in st.session_state:
    st.session_state["active_sizes_global"] = ["26", "27", "28", "29", "30", "31", "32", "33", "34"]
if "current_po_target_val" not in st.session_state:
    st.session_state["current_po_target_val"] = 0
if "manual_parsed_breakdown" not in st.session_state:
    st.session_state["manual_parsed_breakdown"] = {}

# Hàm helper ép kiểu số nguyên an toàn cục bộ cho xưởng
def safe_int_final(value, default=0):
    if value is None: return default
    try:
        clean_val = str(value).replace(",", "").strip()
        if not clean_val or clean_val.lower() == "none": return default
        if "." in clean_val: clean_val = clean_val.split(".")[0]
        return int(clean_val)
    except (ValueError, TypeError):
        return default

st.markdown("#### 📋 KHAI BÁO THÔNG SỐ TÁC NGHIỆP ĐƠN HÀNG VÀ BÀN VẢI MULTI-INSEAM")

# Thiết lập hàng nhập liệu số 1 (Mã hàng, Số lượng PO, Định mức, Màu vải)
input_col1, input_col2, input_col3, input_col_color = st.columns(4)
with input_col1: 
    style_id_input = st.text_input(
        "🏷️ Tên mã hàng (Style ID):", 
        value="00143", 
        key="style_id_input_key_v2"
    )
with input_col2: 
    # Tự động cập nhật tổng sản lượng dựa trên số liệu bạn dán từ Excel ở Đoạn sau
    po_qty_input = st.number_input(
        "📦 Số lượng đơn hàng (PO Pcs):", 
        value=int(st.session_state["current_po_target_val"]), 
        step=100, 
        key="po_qty_input_key_v2"
    )
with input_col3: 
    consumption_input = st.number_input(
        "🎯 Định mức tài liệu đề xuất (Yds/Pcs):", 
        value=1.140, 
        step=0.001, 
        format="%.3f", 
        key="consumption_input_key_unique"
    )
with input_col_color: 
    color_input = st.text_input(
        "🎨 Tự gõ Màu vải:", 
        value="BLACK", 
        key="color_input_key_unique"
    )

# Thiết lập hàng nhập liệu số 2 (Chiều dài bàn, Loại vải, Khổ đi sơ đồ)
input_col4, input_col5, input_col6 = st.columns(3)
with input_col4: 
    max_table_length = st.number_input(
        "📏 Chiều dài tối đa bàn vải (Meters):", 
        value=12.00, 
        step=1.0, 
        key="max_table_length_key_unique"
    )
with input_col5:
    fabric_type_input = st.selectbox(
        "🧵 Loại vải đang tác nghiệp:", 
        ["CHÍNH", "LÓT", "KEO", "PHỐI"], 
        index=0, 
        key="fabric_selectbox_key_v2"
    )
with input_col6: 
    cuttable_width_inch = st.number_input(
        "📐 KHỔ CẮT (Khổ vải đi sơ đồ - Inches):", 
        value=56.00, 
        step=0.50, 
        format="%.2f", 
        key="cuttable_width_inch_key_unique"
    )
# =============================================================================
# TẦNG 2: KHU VỰC TIẾP NHẬN DỮ LIỆU COPY / PASTE TỪ EXCEL V24
# =============================================================================

st.markdown("<br><p style='font-size:13px; font-weight:700; color:#1E293B; margin-bottom:4px;'>📋 DÁN DỮ LIỆU MATRIX SIZE & SẢN LƯỢNG TỪ EXCEL VÀO ĐÂY:</p>", unsafe_allow_html=True)
paste_zone_data = st.text_area(
    "Dán dữ liệu matrix size và sản lượng từ excel vào đây:",
    placeholder="Mẹo: Quét chọn dòng Size và dòng Số lượng trên Excel -> Ctrl+C -> Click vào đây -> Ctrl+V\nVí dụ:\n26\t27\t28\t29\t30\n150\t200\t350\t400\t100",
    height=90,
    key="cad_paste_zone_key_unique",
    label_visibility="collapsed"
)

# Công cụ quét Regex bóc tách chuỗi dữ liệu bảng từ Excel khi phát hiện hành động Paste
if paste_zone_data.strip():
    lines = [l.strip() for l in paste_zone_data.strip().split("\n") if l.strip()]
    if len(lines) >= 2:
        # Tách hàng 1 làm danh sách tên Size, hàng 2 làm danh sách Số lượng sản phẩm
        raw_sizes = [str(x).strip().upper().replace(" ", "") for x in lines[0].split("\t") if x.strip()]
        raw_qtys = [safe_int_final(x) for x in lines[1].split("\t") if x.strip()]
        
        # Cơ chế dự phòng nếu người dùng copy khoảng cách dạng dấu cách trống (Space) thay vì phím Tab
        if len(raw_sizes) <= 1:
            raw_sizes = [str(x).strip().upper().replace(" ", "") for x in lines[0].split() if x.strip()]
            raw_qtys = [safe_int_final(x) for x in lines[1].split() if x.strip()]
            
        if len(raw_sizes) == len(raw_qtys) and len(raw_sizes) > 0:
            built_dict = {}
            for s, q in zip(raw_sizes, raw_qtys):
                built_dict[s] = q
            
            # Nếu phát hiện cụm dữ liệu dán mới khác với cụm cũ trong bộ nhớ, tự động cập nhật lại ô lưới
            if built_dict != st.session_state["manual_parsed_breakdown"]:
                st.session_state["manual_parsed_breakdown"] = built_dict
                st.session_state["active_sizes_global"] = raw_sizes
                st.session_state["current_po_target_val"] = sum(raw_qtys)
                
                # Giải phóng bộ nhớ đệm snaphot cũ để ép bảng bên dưới sinh lại số lượng cột động mới vừa dán
                st.session_state["session_editor_snapshot"] = None
                st.rerun()
# =============================================================================
# TẦNG 3 - ĐOẠN 6 THỐNG NHẤT: Ô LƯỚI TÁC NGHIỆP TỰ DO VÀ LIÊN KẾT THÔNG SỐ - ĐÃ VÁ LỖI BIẾN V32
# =============================================================================

def safe_int_final(value, default=0):
    if value is None: return default
    try:
        clean_val = str(value).replace(",", "").strip()
        if not clean_val or clean_val.lower() == "none": return default
        if "." in clean_val: clean_val = clean_val.split(".")
        return int(clean_val)
    except (ValueError, TypeError):
        return default

# 1. ĐỌC DỮ LIỆU ĐỘNG TỪ BỘ NHỚ EXCEL PASTE
active_sizes = st.session_state.get("active_sizes_global", ["26", "27", "28", "29", "30", "31", "32", "33", "34"])
real_size_breakdown = st.session_state.get("manual_parsed_breakdown", {})

fab_upper = str(st.session_state.get("fabric_selectbox_key_v2", "CHÍNH")).upper().strip()
prefix_letter = "L" if fab_upper == "LÓT" else "K" if fab_upper == "KEO" else "P" if fab_upper == "PHỐI" else "C"

# Sinh hệ thống tiêu đề cột bám sát dải cỡ của bạn
clean_headers_top = ["BÀN CẮT / TÊN SƠ ĐỒ", "TỔNG SẢN LƯỢNG"] + [f"CỠ {i+1}" for i in range(len(active_sizes))] + ["SƠ LỚP", "SỐ BÀN", "DÀI SƠ ĐỒ"]

# Ép dòng SẢN LƯỢNG lấy chính xác số lượng PO tổng từ ô nhập thông số phía trên
true_total_quantity = safe_int_final(st.session_state.get("po_qty_input_key_v2", 0))
if true_total_quantity == 0 and real_size_breakdown:
    true_total_quantity = sum([safe_int_final(v) for v in real_size_breakdown.values()])

giang_top_row = {"BÀN CẮT / TÊN SƠ ĐỒ": "GIÀNG", "TỔNG SẢN LƯỢNG": 0}
size_top_row = {"BÀN CẮT / TÊN SƠ ĐỒ": "SIZE", "TỔNG SẢN LƯỢNG": 0}
sl_top_row = {"BÀN CẮT / TÊN SƠ ĐỒ": "SẢN LƯỢNG", "TỔNG SẢN LƯỢNG": true_total_quantity}

for i, sz in enumerate(active_sizes):
    giang_top_row[f"CỠ {i+1}"] = "0"  # Mặc định giàng đồ short là 0, cho phép chỉnh tay
    size_top_row[f"CỠ {i+1}"] = str(sz)
    sl_top_row[f"CỠ {i+1}"] = safe_int_final(real_size_breakdown.get(sz, 0))

giang_top_row.update({"SƠ LỚP": 0, "SỐ BÀN": 0, "DÀI SƠ ĐỒ": 0.0})
size_top_row.update({"SƠ LỚP": 0, "SỐ BÀN": 0, "DÀI SƠ ĐỒ": 0.0})
sl_top_row.update({"SƠ LỚP": 0, "SỐ BÀN": 0, "DÀI SƠ ĐỒ": 0.0})

# Khôi phục trạng thái bộ nhớ đệm ô lưới
snapshot = st.session_state.get("session_editor_snapshot")
is_snapshot_valid = False
if snapshot and isinstance(snapshot, list) and len(snapshot) > 0:
    first_item = snapshot
    if isinstance(first_item, dict) and f"CỠ {len(active_sizes)}" in first_item:
        is_snapshot_valid = True

if is_snapshot_valid:
    cleaned_snapshot = [giang_top_row, size_top_row, sl_top_row]
    filtered_snapshot = [r for r in snapshot if isinstance(r, dict) and r.get("BÀN CẮT / TÊN SƠ ĐỒ") not in ["GIÀNG", "SIZE", "SẢN LƯỢNG"]]
    for row in filtered_snapshot:
        item_name = str(row.get("BÀN CẮT / TÊN SƠ ĐỒ", "")).upper().strip()
        if not item_name: item_name = f"{fab_upper} {prefix_letter}{str(len(cleaned_snapshot)-3).zfill(2)}"
        item_dict = {"BÀN CẮT / TÊN SƠ ĐỒ": item_name, "TỔNG SẢN LƯỢNG": 0}
        for c_idx, sz in enumerate(active_sizes):
            item_dict[f"CỠ {c_idx+1}"] = str(row.get(f"CỠ {c_idx+1}", "0")).strip()
        item_dict["SƠ LỚP"] = safe_int_final(row.get("SƠ LỚP", 0))
        item_dict["SỐ BÀN"] = max(1, safe_int_final(row.get("SỐ BÀN", 1)))
        try: item_dict["DÀI SƠ ĐỒ"] = float(str(row.get("DÀI SƠ ĐỒ", 0.0)).replace(",", "") or 0.0)
        except: item_dict["DÀI SƠ ĐỒ"] = 0.0
        cleaned_snapshot.append(item_dict)
    display_editor_rows = cleaned_snapshot
else:
    display_editor_rows = [giang_top_row, size_top_row, sl_top_row]
    item_pilot = {"BÀN CẮT / TÊN SƠ ĐỒ": "PILOT", "TỔNG SẢN LƯỢNG": 0}
    for i in range(len(active_sizes)): 
        item_pilot[f"CỠ {i+1}"] = "0"
    item_pilot.update({"SƠ LỚP": 0, "SỐ BÀN": 1, "DÀI SƠ ĐỒ": 0.0})
    display_editor_rows.append(item_pilot)
    
    for i in range(5):
        item_dict = {"BÀN CẮT / TÊN SƠ ĐỒ": f"{fab_upper} {prefix_letter}{str(i+1).zfill(2)}", "TỔNG SẢN LƯỢNG": 0}
        for idx_sz in range(len(active_sizes)): 
            item_dict[f"CỠ {idx_sz+1}"] = "0"
        item_dict.update({"SƠ LỚP": 0, "SỐ BÀN": 1, "DÀI SƠ ĐỒ": 0.0})
        display_editor_rows.append(item_dict)

st.session_state["session_editor_snapshot"] = display_editor_rows

def callback_sync_on_the_fly_final():
    if "table_manual_data_editor_final_clean_v1" in st.session_state:
        st_editor = st.session_state["table_manual_data_editor_final_clean_v1"]
        if "edited_rows" in st_editor and st_editor["edited_rows"]:
            raw_snapshot = st.session_state.get("session_editor_snapshot", display_editor_rows)
            current_snapshot = json.loads(json.dumps(raw_snapshot))
            
            for r_idx_edit, change_dict in st_editor["edited_rows"].items():
                r_idx_int = int(r_idx_edit)
                if current_snapshot and r_idx_int < len(current_snapshot):
                    for col_header, new_val in change_dict.items():
                        if str(col_header).startswith("CỠ "):
                            current_snapshot[r_idx_int][col_header] = str(new_val).strip()
                        elif col_header in ["SƠ LỚP", "SỐ BÀN"]:
                            current_snapshot[r_idx_int][col_header] = safe_int_final(new_val)
                        elif col_header == "DÀI SƠ ĐỒ":
                            try: current_snapshot[r_idx_int][col_header] = float(str(new_val).strip() or 0.0)
                            except: current_snapshot[r_idx_int][col_header] = 0.0
            
            if len(current_snapshot) > 2:
                sl_row_idx = None
                for idx, row in enumerate(current_snapshot):
                    if str(row.get("BÀN CẮT / TÊN SƠ ĐỒ", "")).upper().strip() == "SẢN LƯỢNG":
                        sl_row_idx = idx
                        break
                if sl_row_idx is not None:
                    calc_total = 0
                    for c_idx in range(len(active_sizes)):
                        calc_total += safe_int_final(current_snapshot[sl_row_idx].get(f"CỠ {c_idx+1}", 0))
                    current_snapshot[sl_row_idx]["TỔNG SẢN LƯỢNG"] = calc_total
                    
            st.session_state["session_editor_snapshot"] = current_snapshot

def wrapper_callback_sync():
    callback_sync_on_the_fly_final()
    st.rerun()

df_editor_top_render = pd.DataFrame(st.session_state["session_editor_snapshot"]).reindex(columns=clean_headers_top).fillna("0")

# Tính toán cột Tổng SL động hiển thị
for idx, row in df_editor_top_render.iterrows():
    row_name = str(row["BÀN CẮT / TÊN SƠ ĐỒ"]).upper().strip()
    if row_name not in ["GIÀNG", "SIZE"]:
        total_pcs_row = 0
        for i in range(len(active_sizes)):
            total_pcs_row += safe_int_final(row.get(f"CỠ {i+1}", 0))
        if row_name != "SẢN LƯỢNG":
            layers_val = safe_int_final(row.get("SƠ LỚP", 0))
            tables_val = max(1, safe_int_final(row.get("SỐ BÀN", 1)))
            df_editor_top_render.at[idx, "TỔNG SẢN LƯỢNG"] = int(total_pcs_row * layers_val * tables_val)
        else:
            df_editor_top_render.at[idx, "TỔNG SẢN LƯỢNG"] = int(total_pcs_row)

for col in clean_headers_top:
    if col in df_editor_top_render.columns:
        if col in ["SƠ LỚP", "SỐ BÀN"]:
            df_editor_top_render[col] = pd.to_numeric(df_editor_top_render[col], errors='coerce').fillna(0).astype(int)
        elif col == "DÀI SƠ ĐỒ":
            df_editor_top_render[col] = pd.to_numeric(df_editor_top_render[col], errors='coerce').fillna(0).astype(float)
        elif col.startswith("CỠ "):
            df_editor_top_render[col] = df_editor_top_render[col].astype(str).str.strip()

config_cot = {
    "BÀN CẮT / TÊN SƠ ĐỒ": st.column_config.TextColumn("📋 Tên Sơ Đồ", disabled=True, width="medium"), 
    "TỔNG SẢN LƯỢNG": st.column_config.NumberColumn("📊 Tổng SL", disabled=True),
    "SƠ LỚP": st.column_config.NumberColumn("🥞 Sơ Lớp", disabled=False, min_value=0, step=1, format="%d"),
    "SỐ BÀN": st.column_config.NumberColumn("🗂️ Số Bàn", disabled=False, min_value=1, step=1, format="%d"),
    "DÀI SƠ ĐỒ": st.column_config.NumberColumn("📏 Dài Sơ Đồ (m)", disabled=False, min_value=0.0, step=0.05, format="%.2f")
}
for i, sz in enumerate(active_sizes):
    config_cot[f"CỠ {i+1}"] = st.column_config.TextColumn(f"🔍 CỠ {i+1} ({sz})", disabled=False)

st.data_editor(df_editor_top_render, column_config=config_cot, use_container_width=True, hide_index=True, key="table_manual_data_editor_final_clean_v1", on_change=wrapper_callback_sync)

st.markdown("<br>", unsafe_allow_html=True)
if st.button("🚀 KÍCH HOẠT THUẬT TOÁN TỰ ĐỘNG CHIA SƠ ĐỒ VÀ VẾT ĐƠN", type="primary", use_container_width=True, key="trigger_python_engine_solve_btn"):
    st.session_state["c2_normal_cut_btn"] = True
    st.success("🤖 Đang kích hoạt điều độ ngược theo chiều dài bàn vải...")
    st.rerun()





import math
# =============================================================================
# TẦNG 3 - ĐOẠN 7a: KHỐI ENGINE TOÁN HỌC TÁC NGHIỆP NGƯỢC - ĐÃ KHỬ SẠCH ĐOẠN THỪA V36
# =============================================================================

# THUẬT TOÁN CHỈ CHẠY KHI NGƯỜI DÙNG CHỦ ĐỘNG BẤM NÚT ĐỎ TRÊN MÀN HÌNH
if st.session_state.get("c2_normal_cut_btn", False):
    active_sizes = st.session_state.get("active_sizes_global", [])
    snapshot_current = st.session_state.get("session_editor_snapshot", [])
    
    current_order_balances = {}
    final_snapshot_rows = []
    
    # 1. Thu thập số lượng đơn hàng đầu vào từ hàng SẢN LƯỢNG đã nhập tay/paste Excel
    if snapshot_current:
        for row in snapshot_current:
            if str(row.get("BÀN CẮT / TÊN SƠ ĐỒ", "")).upper().strip() == "SẢN LƯỢNG":
                for idx_sz, sz in enumerate(active_sizes):
                    current_order_balances[sz] = safe_int_final(row.get(f"CỠ {idx_sz+1}", 0))
                break
                
    total_sum_po_qty = sum(current_order_balances.values())
    
    # Đẩy 3 hàng thông tin mốc (GIÀNG, SIZE, SẢN LƯỢNG) vào danh sách báo cáo đầu ra
    for row in snapshot_current:
        if str(row.get("BÀN CẮT / TÊN SƠ ĐỒ", "")).upper().strip() in ["GIÀNG", "SIZE", "SẢN LƯỢNG"]:
            final_snapshot_rows.append(row)

    # 2. Khấu trừ lượng hàng xưởng đã chủ động tác nghiệp phối tay (Dòng PILOT hoặc sơ đồ nhập tay)
    for row in snapshot_current:
        row_name = str(row.get("BÀN CẮT / TÊN SƠ ĐỒ", "")).upper().strip()
        if row_name not in ["GIÀNG", "SIZE", "SẢN LƯỢNG"] and ("PILOT" in row_name or "SS" in row_name or "C" in row_name):
            layers = safe_int_final(row.get("SƠ LỚP", 0))
            tables = max(1, safe_int_final(row.get("SỐ BÀN", 1)))
            
            # Nếu dòng này đã được người dùng gõ tỷ lệ phối và số sơ lớp, tiến hành trừ lùi đơn hàng
            if layers > 0:
                r_dict = {}
                for idx_sz, sz in enumerate(active_sizes):
                    r_val = safe_int_final(row.get(f"CỠ {idx_sz+1}", 0))
                    r_dict[sz] = r_val
                    if r_val > 0:
                        allocated_pcs = r_val * layers * tables
                        current_order_balances[sz] = max(0, current_order_balances[sz] - allocated_pcs)
                
                # Giữ nguyên bản ghi sơ đồ phối tay
                final_snapshot_rows.append(row)

    # 3. Thu thập định mức tài liệu kỹ thuật và Chiều dài tối đa bàn vải để làm mốc chia tỷ lệ
    consumption_in_yards = st.session_state.get("consumption_input_key_unique", 1.140)
    dm_met = round(consumption_in_yards * 0.9144, 4)  # Đổi Yards sang Mét của bàn vải
    
    max_table_len_val = st.session_state.get("max_table_length_key_unique", 12.0)
    max_target_layers = 60  # Số lớp rải vải tối đa xưởng quy định

    # THUẬT TOÁN ĐIỀU ĐỘ NGƯỢC: Tính tổng số sản phẩm cực đại trên sơ đồ dựa vào chiều dài bàn cắt tối đa
    garments_per_marker = math.floor(max_table_len_val / dm_met) if (max_table_len_val > 0 and dm_met > 0) else 6
    if garments_per_marker <= 0: garments_per_marker = 6

    marker_counter, max_safety_loops = 1, 30
    
    # Vòng lặp chia tỷ lệ cuốn chiếu động giảm dần cho đến khi triệt tiêu đơn hàng về 0
    while sum(current_order_balances.values()) > 0 and marker_counter <= max_safety_loops:
        s_marker_name = f"CHÍNH C{str(marker_counter).zfill(2)}"
        total_remaining_po_at_row = sum(current_order_balances.values())
        if total_remaining_po_at_row <= 0: break
            
        base_values, remainders = {}, []
        for sz in active_sizes:
            sz_remaining_qty = current_order_balances.get(sz, 0)
            if sz_remaining_qty <= 0:
                base_values[sz] = 0
                continue
            # Phân bổ tỷ lệ bám sát cơ cấu phần trăm sản lượng còn lại của từng size
            sz_ratio_pct = sz_remaining_qty / total_remaining_po_at_row
            theoretical_qty = garments_per_marker * sz_ratio_pct
            base_qty = int(theoretical_qty)
            base_values[sz] = base_qty
            remainders.append({"size": sz, "remainder": theoretical_qty - base_qty})
            
        allocated_more = garments_per_marker - sum(base_values.values())
        remainders.sort(key=lambda x: x["remainder"], reverse=True)
        for k in range(min(max(0, allocated_more), len(remainders))):
            if current_order_balances.get(remainders[k]["size"], 0) > 0:
                base_values[remainders[k]["size"]] += 1
                
        r_dict = base_values
        row_ratios_total = sum(r_dict.values())
        
        possible_layers_dynamic = []
        for sz in active_sizes:
            if r_dict.get(sz, 0) > 0:
                max_layers_sz = math.floor(current_order_balances.get(sz, 0) / r_dict.get(sz, 0))
                possible_layers_dynamic.append(max_layers_sz if max_layers_sz > 0 else 1)
                    
        calculated_layers = min(possible_layers_dynamic) if possible_layers_dynamic else 1
        row_layers = min(max_target_layers, calculated_layers)
        
        if row_layers <= 0 or row_ratios_total <= 0: break
            
        # Khấu trừ số lượng vào mảng tồn dư
        for sz in active_sizes:
            current_order_balances[sz] = max(0, current_order_balances[sz] - (r_dict.get(sz, 0) * row_layers))
            
        # TUYỆT ĐỐI CHỪA TRỐNG Ô DÀI SƠ ĐỒ ĐỂ NGƯỜI DÙNG TỰ COPPY TỪ CAD VÀO
        item_auto = {
            "BÀN CẮT / TÊN SƠ ĐỒ": s_marker_name, "SƠ LỚP": row_layers, "SỐ BÀN": 1,
            "DÀI SƠ ĐỒ": 0.0, 
            "TỔNG SẢN LƯỢNG": row_ratios_total * row_layers
        }
        for idx_sz, sz in enumerate(active_sizes):
            item_auto[f"CỠ {idx_sz+1}"] = r_dict.get(sz, 0)
            
        item_auto["REMAINING_SNAPSHOT_AFTER"] = dict(current_order_balances)
        final_snapshot_rows.append(item_auto)
        
        # Giảm dần dung lượng tỷ lệ phối sơ đồ cho vòng tiếp theo để vét đơn mượt mà
        garments_per_marker = max(2, garments_per_marker - 1)
        marker_counter += 1

    # 4. Giai đoạn kết thúc đơn: Chèn dòng vét sạch toàn bộ số lượng hàng lẻ còn sót lại
    leftover_sum = sum(current_order_balances.values())
    if leftover_sum > 0:
        s_marker_name = f"CHÍNH C{str(marker_counter).zfill(2)} (VÉT SẠCH ĐƠN HÀNG)"
        item_vet = {"BÀN CẮT / TÊN SƠ ĐỒ": s_marker_name, "SƠ LỚP": 1, "SỐ BÀN": 1, "DÀI SƠ ĐỒ": 0.0, "TỔNG SẢN LƯỢNG": leftover_sum}
        
        for idx_sz, sz in enumerate(active_sizes):
            qty_left = current_order_balances.get(sz, 0)
            item_vet[f"CỠ {idx_sz+1}"] = qty_left
            current_order_balances[sz] = 0
            
        item_vet["REMAINING_SNAPSHOT_AFTER"] = dict(current_order_balances)
        final_snapshot_rows.append(item_vet)

    # Đẩy toàn bộ mảng dữ liệu hoàn chỉnh lên kho bộ nhớ đệm trung tâm
    st.session_state["session_editor_snapshot"] = final_snapshot_rows
    st.session_state["final_snapshot_rows_global"] = final_snapshot_rows
    
    # Hạ cờ giải phóng nút bấm
    st.session_state["c2_normal_cut_btn"] = False
    st.success("🎉 Thuật toán điều độ ngược bàn vải cuốn chiếu đã hoàn tất thành công!")
    st.rerun()



# =============================================================================
# TẦNG 3 - ĐOẠN 7a (PHẦN 2): TOÁN HỌC CUỐN CHIẾU LIÊN HOÀN VÀ VÉT SẠCH SỐ LẺ - ĐA VÁ LỖI V3
# =============================================================================

# --- 4. BƯỚC 3: ĐỌC CẤU HÌNH RẢI SƠ ĐỒ CHÍNH TỪ DÒNG ĐẦU CẦN ĐIỀU ĐỘ CHÍNH ---
max_target_length = 11.46
max_target_layers = 60

if not edited_df_raw.empty:
    chinh_rows_input = edited_df_raw[edited_df_raw["BÀN CẮT / TÊN SƠ ĐỒ"].str.contains("CHÍNH|C01", na=False, case=False)]
    if not chinh_rows_input.empty:
        first_chinh = chinh_rows_input.iloc[0]
        try: 
            max_target_length = float(str(first_chinh["DÀI SƠ ĐỒ"]).replace(",", "").strip() or 11.46)
        except: 
            max_target_length = 11.46
        
        user_layers = safe_int_final(first_chinh["SƠ LỚP"])
        max_target_layers = user_layers if user_layers > 1 else 60

if max_target_length <= 0: max_target_length = 11.46

# --- 5. BƯỚC 4: THUẬT TOÁN ĐIỀU PHỐI ĐỘNG CUỐN CHIẾU PHÒNG VỆ CHẶN TREO SERVER ---
marker_counter, max_safety_loops = 1, 30
while sum(current_order_balances.values()) > 0 and marker_counter <= max_safety_loops:
    s_marker_name = f"CHÍNH C{str(marker_counter).zfill(2)}"
    total_remaining_po_at_row = sum(current_order_balances.values())
    
    garments_per_marker = math.floor(max_target_length / consumption_in_yards) if (max_target_length > 0 and consumption_in_yards > 0) else 0
    if garments_per_marker <= 0 or total_remaining_po_at_row <= 0: break
        
    base_values, remainders = {}, []
    for sz in active_sizes:
        if current_order_balances.get(sz, 0) <= 0:
            base_values[sz] = 0
            remainders.append({"size": sz, "remainder": 0.0})
            continue
        sz_remaining_qty = current_order_balances.get(sz, 0)
        sz_ratio_pct = sz_remaining_qty / total_remaining_po_at_row if total_remaining_po_at_row > 0 else 0
        theoretical_qty = garments_per_marker * sz_ratio_pct
        base_qty = int(theoretical_qty)
        base_values[sz] = base_qty
        remainders.append({"size": sz, "remainder": theoretical_qty - base_qty})
        
    allocated_more = garments_per_marker - sum(base_values.values())
    remainders.sort(key=lambda x: x["remainder"], reverse=True)
    for k in range(min(max(0, allocated_more), len(remainders))):
        if current_order_balances.get(remainders[k]["size"], 0) > 0:
            base_values[remainders[k]["size"]] += 1
            
    r_dict = base_values
    row_ratios_total = sum(r_dict.values())
    
    # Tính số lớp vải trải cuốn chiếu tối đa theo từng size đơn hàng lẻ
    possible_layers_dynamic = []
    for sz in active_sizes:
        if r_dict.get(sz, 0) > 0:
            max_layers_allowed_for_sz = math.floor(current_order_balances.get(sz, 0) / r_dict.get(sz, 0))
            possible_layers_dynamic.append(max_layers_allowed_for_sz if max_layers_allowed_for_sz > 0 else 1)
                
    calculated_layers = min(possible_layers_dynamic) if possible_layers_dynamic else 1
    row_layers = min(max_target_layers, calculated_layers)
    
    # 🎯 FIX LỖI CHÍ MẠNG CHẶN VÒNG LẶP VÔ HẠN: Nếu thuật toán không thể tính thêm số lớp, bẻ gãy vòng lặp lập tức
    if row_layers <= 0 or row_ratios_total <= 0: 
        break
        
    for sz in active_sizes:
        current_order_balances[sz] = max(0, current_order_balances[sz] - (r_dict.get(sz, 0) * row_layers))
        
    item_auto = {
        "BÀN CẮT / TÊN SƠ ĐỒ": s_marker_name, "SƠ LỚP": row_layers, "SỐ BÀN": 1,
        "DÀI SƠ ĐỒ": round(row_ratios_total * consumption_in_yards, 2),
        "TỔNG SẢN LƯỢNG": row_ratios_total * row_layers
    }
    item_auto.update(r_dict)
    item_auto["REMAINING_SNAPSHOT_AFTER"] = dict(current_order_balances)
    final_snapshot_rows.append(item_auto)
    
    marker_counter += 1

# --- 6. BƯỚC 5: KIỂM TRA DƯ THIẾU CUỐI ĐƠN - TỰ ĐỘNG CHÈN DÒNG VÉT SẠCH VẢI VỤN (DÒNG CUỐI) ---
leftover_sum = sum(current_order_balances.values())
if leftover_sum > 0:
    s_marker_name = f"CHÍNH C{str(marker_counter).zfill(2)} (VÉT SẠCH ĐƠN HÀNG)"
    vet_ratios = {}
    total_vet_pants = 0
    
    for sz in active_sizes:
        qty_left = current_order_balances.get(sz, 0)
        vet_ratios[sz] = qty_left
        total_vet_pants += qty_left
        current_order_balances[sz] = 0
        
    item_vet = {
        "BÀN CẮT / TÊN SƠ ĐỒ": s_marker_name, "SƠ LỚP": 1, "SỐ BÀN": 1,
        "DÀI SƠ ĐỒ": round(total_vet_pants * consumption_in_yards, 2),
        "TỔNG SẢN LƯỢNG": total_vet_pants
    }
    item_vet.update(vet_ratios)
    item_vet["REMAINING_SNAPSHOT_AFTER"] = dict(current_order_balances)
    final_snapshot_rows.append(item_vet)

# =============================================================================
# ĐOẠN ĐƯỢC BỔ SUNG: ĐỒNG BỘ DỮ LIỆU CHÍNH THỨC LÊN Ô LƯỚI
# =============================================================================
if final_snapshot_rows:
    # Ghi nhận toàn bộ mảng sơ đồ điều phối tự động vào Snapshot trung tâm
    st.session_state["session_editor_snapshot"] = final_snapshot_rows
import streamlit as st
import pandas as pd
import io
import re

# =============================================================================
# TẦNG 3 - ĐOẠN 7b (PHẦN 1): TÁI CẤU TRÚC PHIẾU BÁO CÁO ĐỒNG BỘ SẢN LƯỢNG THẬT - ĐÃ VÁ LỖI V3
# =============================================================================
# =============================================================================


# Khai báo lại hàm helper cục bộ phòng vệ an toàn hệ thống
def safe_int_final(value, default=0):
    if value is None: return default
    try:
        clean_val = str(value).replace(",", "").strip()
        if not clean_val or clean_val.lower() == "none": return default
        if "." in clean_val: clean_val = clean_val.split(".")[0]
        return int(clean_val)
    except (ValueError, TypeError):
        return default

# 🎯 FIX ĐỒNG BỘ BIẾN GIAO DIỆN: Trích xuất an toàn từ session_state widget toàn cục tránh lỗi NameError
style_id_clean = str(st.session_state.get("style_id_input_key_v2", "UNKNOWN")).strip().upper()
color_clean = str(st.session_state.get("color_input_key_unique", "BLACK")).strip().upper()
fab_type_clean = str(st.session_state.get("fabric_selectbox_key_v2", "CHÍNH")).strip().upper()

# 🎯 ĐỒNG BỘ DANH SÁCH SIZE TOÀN CỤC: Đảm bảo bảng báo cáo bung cột khớp với bảng nhập liệu
active_sizes = st.session_state.get("active_sizes_global", [])
if not active_sizes:
    active_sizes = ["26X30", "27X30", "28X30", "29X30", "30X30", "31X30", "32X30", "33X30", "34X30"]

# 🎯 FIX KEY ĐỒNG BỘ MẤU CHỐT: Đọc chính xác mảng kết quả sau tính toán toán học từ Đoạn 7a
snapshot_current = st.session_state.get("session_editor_snapshot", [])
edited_df_raw = pd.DataFrame(snapshot_current) if snapshot_current else pd.DataFrame()

size_breakdown_main = {}
if not edited_df_raw.empty:
    sl_row_data = edited_df_raw[edited_df_raw["BÀN CẮT / TÊN SƠ ĐỒ"] == "SẢN LƯỢNG"]
    if not sl_row_data.empty:
        target_row = sl_row_data.iloc[0]
        for idx_sz, sz in enumerate(active_sizes):
            size_breakdown_main[sz] = safe_int_final(target_row.get(f"CỠ {idx_sz+1}", 0))

total_sum_po_qty = sum(size_breakdown_main.values())

# Tạo 3 hàng tiêu đề thông tin tổng quát của phiếu đơn hàng dệt may
t_header_ma_hang = ["Mã hàng:", f" {style_id_clean}"] + [""] * (len(active_sizes) + 6)
t_header_mau = ["Màu:", f" {color_clean}"] + [""] * (len(active_sizes) + 6)
t_header_loai_vai = ["Loại vải:", f" {fab_type_clean}"] + [""] * (len(active_sizes) + 6)

t1_giang_row = ["GIÀNG", ""]
t2_size_row = ["SIZE", ""]
po_qty_matrix = []

# Dựng ma trận thông số hình học Eo và Giàng cho tiêu đề báo cáo
for col_name in active_sizes:
    c_str = str(col_name).strip().upper().replace(" ", "")
    g_val, s_val = "30", c_str
    parts = re.split(r'[X_x-]', c_str)
    
    if len(parts) >= 2:
        s_val = str(parts[0]).strip()
        g_val = str(parts[1]).strip()
    elif len(parts) == 1:
        s_val = str(parts[0]).strip()
        
    po_v = safe_int_final(size_breakdown_main.get(col_name, 0))
    po_qty_matrix.append(po_v)
    
    t1_giang_row.append(re.sub(r'_\d+$', '', g_val))
    t2_size_row.append(re.sub(r'_\d+$', '', s_val))
    
for _ in range(6): 
    t1_giang_row.append("")
    t2_size_row.append("")
    
t3_sl_row = ["SẢN LƯỢNG", f"{total_sum_po_qty:,}"] + [f"{v:,}" for v in po_qty_matrix] + [""] * 6
    
matrix_body_rows = []
# Lọc dứt điểm các dòng sản xuất thực tế, bỏ qua dòng mốc cố định
production_rows = [r for r in snapshot_current if isinstance(r, dict) and r.get("BÀN CẮT / TÊN SƠ ĐỒ") not in ["GIÀNG", "SIZE", "SẢN LƯỢNG"]]

# Vòng lặp bóc tách toàn bộ các sơ đồ CHÍNH C01, C02 đã được thuật toán rải tự động
for r_idx, row_data in enumerate(production_rows):
    s_name = str(row_data.get("BÀN CẮT / TÊN SƠ ĐỒ", f"SƠ ĐỒ C{r_idx+1}")).upper().strip()
    layers = safe_int_final(row_data.get("SƠ LỚP", 0))
    tables = max(1, safe_int_final(row_data.get("SỐ BÀN", 1)))
    try: m_len = float(str(row_data.get("DÀI SƠ ĐỒ", 0.0)).replace(",", "").strip() or 0.0)
    except: m_len = 0.0
    
    row_ratios_list = []
    ratios_sum = 0
    
    for c_idx, sz in enumerate(active_sizes):
        r_val = safe_int_final(row_data.get(sz, row_data.get(f"CỠ {c_idx+1}", 0)))
        ratios_sum += r_val
        row_ratios_list.append(r_val)
    
    # Tính định mức sơ đồ hệ mét chuyển đổi
    dm_sd = (m_len * 1.09361) / ratios_sum if (m_len > 0 and ratios_sum > 0) else 0.0
    vail_can_m = m_len * layers * tables
    total_cut_in_row = ratios_sum * layers * tables
    
    # Thêm hàng tỷ lệ phối bàn vải thực tế
    ratio_row = [s_name, f"{total_cut_in_row:,}"] + [f"{v:,}" if isinstance(v, int) else v for v in row_ratios_list] + [layers, tables, round(m_len, 2), ratios_sum, round(dm_sd, 3), round(vail_can_m, 1)]
    matrix_body_rows.append(ratio_row)
    
    # Chèn hàng snapshot "CÒN LẠI" khấu trừ lũy tiến cuốn chiếu xuống dưới
    row_remaining_snapshot = row_data.get("REMAINING_SNAPSHOT_AFTER", {})
    remaining_row = ["CÒN LẠI", ""]
    for sz in active_sizes:
        rem_sz_val = safe_int_final(row_remaining_snapshot.get(sz, 0))
        remaining_row.append(f"{rem_sz_val:,}" if rem_sz_val > 0 else "0")
    remaining_row.extend(["", "", "", "", "", ""])
    matrix_body_rows.append(remaining_row)

clean_headers = ["BÀN CẮT / TÊN SƠ ĐỒ", "TỔNG SẢN LƯỢNG"] + [f"CỠ {i+1}" for i in range(len(active_sizes))] + ["SƠ LỚP", "SỐ BÀN", "DÀI SƠ ĐỒ", "SỐ SP/SĐ", "Đ.MỨC SĐ", "VẢI CẦN (M)"]
final_table_rows = [t_header_ma_hang, t_header_mau, t_header_loai_vai, t1_giang_row, t2_size_row, t3_sl_row] + matrix_body_rows

df_final_report = pd.DataFrame(final_table_rows, columns=clean_headers)
# ĐOẠN CODE BỔ SUNG: NÚT XÓA SẠCH DỮ LIỆU ĐỂ LẬP PHIẾU MỚI
# =============================================================================
st.markdown("<br>", unsafe_allow_html=True)

# Tạo một hàng mới riêng biệt cho tính năng Reset hệ thống
clear_col1, clear_col2, clear_col3 = st.columns([1, 2, 1])

with clear_col2:
    if st.button("🗑️ XÓA TOÀN BỘ DỮ LIỆU TÁC NGHIỆP HIỆN TẠI", use_container_width=True, type="secondary", key="clear_all_planning_data_final_btn"):
        # 1. Kích hoạt cờ xóa dữ liệu để kích hoạt cơ chế phòng vệ khóa chặn
        st.session_state["planning_cleared"] = True
        
        # 2. Reset toàn bộ các biến trạng thái lưu trữ cốt lõi về mặc định
        st.session_state["purchase_ready"] = False
        st.session_state["sbd_parsed_data"] = None
        st.session_state["pur_tp_parsed_data"] = None
        st.session_state["session_editor_snapshot"] = None
        st.session_state["active_sizes_global"] = []
        
        # Xóa các bộ nhớ đệm lịch sử đồng bộ cũ
        if "auto_cutting_results_recovered" in st.session_state:
            del st.session_state["auto_cutting_results_recovered"]
        if "auto_cutting_results" in st.session_state:
            del st.session_state["auto_cutting_results"]
            
        # 3. Tắt lại cờ phòng vệ sau khi đã dọn dẹp xong bộ nhớ để chuẩn bị cho lượt up file tiếp theo
        st.session_state["planning_cleared"] = False
        
        st.success("🔄 Đã xóa sạch dữ liệu cấu trúc cũ! Hệ thống đang quay về màn hình tải file...")
        st.rerun() # Tải lại trang ngay lập tức để đưa người dùng về Tầng 1

import streamlit as st
import pandas as pd
import io
import re
# 🎯 FIX LỖI CHÍ MẠNG: Thêm import hàm tạo kết nối Client cho Cloud Supabase
from supabase import create_client 

# =============================================================================
# TẦNG 3 - ĐOẠN 7b (PHẦN 2): RENDERING GIAO DIỆN VÀ ĐỒNG BỘ CLOUD SUPABASE - ĐÃ VÁ LỖI V3
# =============================================================================

# Bộ định dạng giao diện hiển thị bảng may mặc chuyên nghiệp bằng CSS
st.markdown("""<style>
    .report-table th { background-color: #F1F5F9 !important; color: #1E293B !important; font-weight: 700 !important; text-align: center !important; border: 1px solid #CBD5E1 !important; }
    .report-table td { background-color: #FFFFFF !important; color: #0F172A !important; border: 1px solid #E2E8F0 !important; text-align: center !important; font-weight: 500 !important; }
</style>""", unsafe_allow_html=True)

st.markdown("### 📊 PHIẾU TÁC NGHIỆP LIÊN KẾT BÀN CẮT CHÍNH THỨC")
st.dataframe(df_final_report, use_container_width=True, hide_index=True)

st.markdown("---")
action_col1, action_col2 = st.columns(2)

# NÚT BẤM 1: Xuất tệp tin Excel (.xlsx) tải về máy cá nhân
with action_col1:
    output_excel = io.BytesIO()
    # Sử dụng công cụ xlsxwriter chuẩn hóa bảng dữ liệu
    with pd.ExcelWriter(output_excel, engine='xlsxwriter') as writer:
        df_final_report.to_excel(writer, sheet_name='TAC_NGHIEP_BAN_CAT', index=False)
    processed_data = output_excel.getvalue()
    st.download_button(
        label="📥 TẢI PHIẾU TÁC NGHIỆP EXCEL (.XLSX)", data=processed_data,
        file_name=f"Phieu_Tac_Nghiep_{style_id_clean}_{fab_type_clean}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", 
        use_container_width=True, 
        type="primary"
    )

# NÚT BẤM 2: Gói Payload và Upsert trực tiếp lên kho cơ sở dữ liệu trung tâm Cloud Supabase
with action_col2:
    if st.button("💾 ĐẨY PHIẾU LÊN HỆ THỐNG TRUNG TÂM CLOUD SUPABASE", use_container_width=True, key="push_to_supabase_cloud_final_btn"):
        try:
            url_direct_push = st.secrets.get("SUPABASE_URL", "")
            key_direct_push = st.secrets.get("SUPABASE_KEY", "")
            
            if not url_direct_push or not key_direct_push: 
                st.error("❌ Hệ thống chưa được cấu hình đầy đủ biến môi trường SUPABASE_URL hoặc SUPABASE_KEY trong Secrets.")
            else:
                # Gọi hàm kết nối cloud an toàn
                sb_client_push = create_client(url_direct_push, key_direct_push)
                
                # Khôi phục dữ liệu ma trận thật từ lưới ô để đẩy lên cloud lưu trữ lịch sử
                snapshot_to_cloud = st.session_state.get("session_editor_snapshot", [])
                
                # Phòng vệ an toàn kiểu dữ liệu số nguyên cho tổng PO Pcs
                try:
                    cloud_total_qty = int(float(str(total_sum_po_qty).replace(",", "")))
                except:
                    cloud_total_qty = 0
                
                payload_save = {
                    "style_id": str(style_id_clean), 
                    "fabric_type": str(fab_type_clean),
                    "total_po_qty": cloud_total_qty, 
                    "cutting_matrix_data": snapshot_to_cloud, 
                    "color_name": str(color_clean)
                }
                
                # Sử dụng cơ chế upsert ràng buộc theo cặp khóa (style_id, fabric_type) chống ghi trùng lặp dữ liệu
                res_push = sb_client_push.table("cutting_orders_db").upsert(payload_save, on_conflict="style_id,fabric_type").execute()
                st.success("🎉 Hệ thống đã đồng bộ phiếu tác nghiệp lên Cloud Supabase thành công!")
        except Exception as e: 
            st.error(f"❌ Trục trặc khi gửi gói tin lên Supabase: {str(e)}")
