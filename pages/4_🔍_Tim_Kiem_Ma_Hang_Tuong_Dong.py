# =====================================================================
# 🔍 AI TÌM KIẾM MÃ HÀNG TƯƠNG ĐỒNG
# VERSION V2.6
# ĐOẠN 1/2
#
# GEMINI VISION
# GEMINI EMBEDDING 2
# SUPABASE + PGVECTOR
#
# KHÔNG DÙNG HUGGING FACE
# KHÔNG DÙNG CLIP
# KHÔNG DÙNG TORCH
# =====================================================================

import streamlit as st
import json
import re
import io
import os
import uuid
import numpy as np

from PIL import Image
from supabase import create_client, Client
from google import genai
from google.genai import types


# =====================================================================
# 1. PAGE CONFIG
# =====================================================================

st.set_page_config(
    page_title="AI Tìm Kiếm Mã Hàng",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)


# =====================================================================
# 2. CONSTANTS
# =====================================================================

APP_VERSION = "V2.6"

SUPABASE_BUCKET = "product-images"

VISION_MODEL = "gemini-2.5-flash"

EMBEDDING_MODEL = "gemini-embedding-2"

EMBEDDING_DIM = 768

TOP_K = 12


VALID_CATEGORIES = [
    "Áo liền quần",
    "Quần yếm",
    "Quần túi hộp",
    "Quần jean",
    "Quần jogger",
    "Quần short",
    "Quần dài",
    "Jacket",
    "Áo",
    "T-shirt",
    "Polo",
    "Hoodie",
    "Skirt",
    "Dress",
]


# =====================================================================
# 3. STREAMLIT SECRETS
# =====================================================================

def read_secret(name):

    """
    Đọc Secret theo nhiều cấu trúc:

    Cách 1:
        SUPABASE_URL = "..."

    Cách 2:
        [supabase]
        SUPABASE_URL = "..."

    Cách 3:
        [api]
        SUPABASE_URL = "..."

    Cách 4:
        [secrets]
        SUPABASE_URL = "..."

    Đồng thời thử Environment Variable.
    """

    # ---------------------------------------------------------------
    # A. STREAMLIT FLAT
    # ---------------------------------------------------------------

    try:

        value = st.secrets.get(name)

        if value is not None:

            value = str(value).strip()

            if value:
                return value

    except Exception:
        pass


    # ---------------------------------------------------------------
    # B. STREAMLIT SECTIONS
    # ---------------------------------------------------------------

    sections = [
        "supabase",
        "api",
        "secrets",
        "gemini"
    ]

    for section_name in sections:

        try:

            section = st.secrets.get(
                section_name
            )

            if section is not None:

                try:

                    value = section.get(name)

                except Exception:

                    value = None

                if value is not None:

                    value = str(
                        value
                    ).strip()

                    if value:

                        return value

        except Exception:

            pass


    # ---------------------------------------------------------------
    # C. ENVIRONMENT VARIABLE
    # ---------------------------------------------------------------

    try:

        value = os.getenv(name)

        if value:

            value = str(
                value
            ).strip()

            if value:

                return value

    except Exception:

        pass


    return None


# =====================================================================
# 4. LOAD SECURITY KEYS
# =====================================================================

SUPABASE_URL = read_secret(
    "SUPABASE_URL"
)

SUPABASE_KEY = read_secret(
    "SUPABASE_KEY"
)

GEMINI_API_KEY = read_secret(
    "GEMINI_API_KEY"
)


# =====================================================================
# 5. SECURITY CHECK
# =====================================================================

missing_keys = []


if not SUPABASE_URL:

    missing_keys.append(
        "SUPABASE_URL"
    )


if not SUPABASE_KEY:

    missing_keys.append(
        "SUPABASE_KEY"
    )


if not GEMINI_API_KEY:

    missing_keys.append(
        "GEMINI_API_KEY"
    )


if missing_keys:

    st.error(
        "❌ Không đọc được thông tin bảo mật "
        "từ Streamlit Secrets."
    )

    st.markdown(
        """
### Hãy kiểm tra Secrets

Trong Streamlit Cloud → **Settings → Secrets**,
đặt dạng:

```toml
SUPABASE_URL = "https://xxxxx.supabase.co"
SUPABASE_KEY = "your-supabase-key"
GEMINI_API_KEY = "your-gemini-api-key"

---

# 🟦 ĐOẠN 2 — GIAO DIỆN SEARCH + NẠP KHO

**Dán nguyên đoạn này ngay sau Đoạn 1.**

```python
# =====================================================================
# 🔍 AI TÌM KIẾM MÃ HÀNG TƯƠNG ĐỒNG
# VERSION V2.6
# ĐOẠN 2/2
#
# SEARCH UI
# WAREHOUSE UPLOAD
# PENDING FILES
# RESULTS
# =====================================================================


# =====================================================================
# 21. DISPLAY AI RESULT
# =====================================================================

def display_ai_result(
    result
):

    if not result:

        return


    category = result.get(
        "category",
        "Không xác định"
    )


    confidence = result.get(
        "confidence",
        0
    )


    st.success(
        f"🤖 AI nhận diện: **{category}** "
        f"— Confidence **{confidence:.0f}%**"
    )


    col1, col2, col3, col4 = st.columns(
        4
    )


    with col1:

        st.metric(
            "Category",
            category
        )


    with col2:

        st.metric(
            "Confidence",
            f"{confidence:.0f}%"
        )


    with col3:

        st.metric(
            "One Piece",
            "YES"
            if result.get(
                "one_piece",
                False
            )
            else "NO"
        )


    with col4:

        st.metric(
            "Cargo Pocket",
            "YES"
            if result.get(
                "cargo_pockets",
                False
            )
            else "NO"
        )


    with st.expander(
        "🔎 Chi tiết AI"
    ):

        st.json(
            result
        )


# =====================================================================
# 22. DISPLAY SEARCH RESULTS
# =====================================================================

def display_search_results(
    results
):

    if not results:

        st.warning(
            "Không tìm thấy mã hàng tương đồng."
        )

        return


    st.subheader(
        f"🎯 Tìm thấy {len(results)} mã tương đồng"
    )


    cols = st.columns(
        min(
            len(results),
            4
        )
    )


    for index, item in enumerate(
        results
    ):

        with cols[
            index % len(cols)
        ]:

            product_code = item.get(
                "product_code",
                "N/A"
            )


            category = item.get(
                "category",
                ""
            )


            similarity = item.get(
                "similarity",
                item.get(
                    "final_score",
                    0
                )
            )


            try:

                similarity_percent = (
                    float(
                        similarity
                    )
                    * 100
                )

            except Exception:

                similarity_percent = 0


            st.markdown(
                f"### 🏷️ {product_code}"
            )


            st.caption(
                f"Loại: {category}"
            )


            st.metric(
                "Độ tương đồng",
                f"{similarity_percent:.2f}%"
            )


            image_url = item.get(
                "image_url"
            )


            if image_url:

                try:

                    st.image(
                        image_url,
                        use_container_width=True
                    )

                except Exception:

                    st.caption(
                        "Không hiển thị được ảnh."
                    )


            st.divider()


# =====================================================================
# 23. ADD PENDING FILES
# =====================================================================

def add_pending_files(
    uploaded_files
):

    existing_names = {

        item["name"]

        for item
        in st.session_state[
            "pending_uploads_v26"
        ]

    }


    added = 0


    for uploaded_file in uploaded_files:

        if uploaded_file.name in existing_names:

            continue


        file_bytes = uploaded_file.getvalue()


        st.session_state[
            "pending_uploads_v26"
        ].append({

            "name":
                uploaded_file.name,

            "bytes":
                file_bytes

        })


        existing_names.add(
            uploaded_file.name
        )


        added += 1


    return added


# =====================================================================
# 24. REMOVE PENDING FILE
# =====================================================================

def remove_pending_file(
    index
):

    files = st.session_state[
        "pending_uploads_v26"
    ]


    if (
        0
        <= index
        < len(files)
    ):

        files.pop(
            index
        )


# =====================================================================
# 25. CLEAR PENDING FILES
# =====================================================================

def clear_pending_files():

    st.session_state[
        "pending_uploads_v26"
    ] = []


# =====================================================================
# 26. HEADER
# =====================================================================

st.title(
    "🔍 AI TÌM KIẾM MÃ HÀNG TƯƠNG ĐỒNG"
)

st.caption(
    f"AI Garment Similarity Search — {APP_VERSION} "
    "| Gemini Vision + Gemini Embedding 2 + Supabase"
)


# =====================================================================
# 27. TABS
# =====================================================================

tab_search, tab_upload = st.tabs([

    "🔍 TÌM KIẾM MÃ HÀNG",

    "📦 NẠP KHO HÀNG LOẠT"

])


# =====================================================================
# 28. TAB SEARCH
# =====================================================================

with tab_search:

    st.header(
        "🔍 Tìm mã hàng tương đồng qua ảnh"
    )


    st.info(
        "AI tự nhận diện loại hàng. "
        "Không cần chọn Category."
    )


    search_file = st.file_uploader(

        "📷 Tải ảnh Sketch / ảnh mẫu cần tìm",

        type=[
            "jpg",
            "jpeg",
            "png",
            "webp"
        ],

        key="search_upload_v26"

    )


    if search_file:

        search_bytes = search_file.getvalue()


        col_a, col_b = st.columns(
            [1, 2]
        )


        with col_a:

            st.image(
                search_bytes,
                caption=search_file.name,
                use_container_width=True
            )


        with col_b:

            if st.button(

                "🚀 PHÂN TÍCH & TÌM MÃ TƯƠNG ĐỒNG",

                type="primary",

                use_container_width=True,

                key="btn_search_v26"

            ):

                try:

                    # =================================================
                    # STEP 1
                    # AI VISION
                    # =================================================

                    with st.spinner(
                        "🤖 Gemini đang nhận diện cấu trúc sản phẩm..."
                    ):

                        ai_result = (
                            analyze_garment_with_gemini(
                                search_bytes
                            )
                        )


                    st.session_state[
                        "search_ai_result_v26"
                    ] = ai_result


                    st.session_state[
                        "search_file_name_v26"
                    ] = search_file.name


                    display_ai_result(
                        ai_result
                    )


                    # =================================================
                    # STEP 2
                    # EMBEDDING
                    # =================================================

                    with st.spinner(
                        "🧠 Gemini đang tạo image embedding..."
                    ):

                        embedding = (
                            create_image_embedding(
                                search_bytes
                            )
                        )


                    # =================================================
                    # STEP 3
                    # SEARCH
                    # =================================================

                    with st.spinner(
                        "🔎 Đang tìm mã tương đồng trong kho..."
                    ):

                        results = (
                            search_similar_products(

                                embedding,

                                ai_result[
                                    "category"
                                ],

                                TOP_K

                            )
                        )


                    st.session_state[
                        "search_results_v26"
                    ] = results


                    st.success(
                        "✅ Phân tích và tìm kiếm hoàn tất."
                    )


                    display_search_results(
                        results
                    )


                except Exception as e:

                    st.error(
                        f"❌ Tìm kiếm lỗi: {e}"
                    )


    elif st.session_state[
        "search_results_v26"
    ]:

        ai_result = (
            st.session_state[
                "search_ai_result_v26"
            ]
        )


        if ai_result:

            display_ai_result(
                ai_result
            )


        display_search_results(

            st.session_state[
                "search_results_v26"
            ]

        )


# =====================================================================
# 29. TAB WAREHOUSE
# =====================================================================

with tab_upload:

    st.header(
        "📦 Nạp mã hàng vào kho"
    )


    st.info(
        "AI tự nhận diện Category. "
        "Tên file được dùng làm Mã hàng."
    )


    # ================================================================
    # FILE UPLOADER
    # ================================================================

    new_files = st.file_uploader(

        "📤 Chọn ảnh sản phẩm cần nạp kho",

        type=[
            "jpg",
            "jpeg",
            "png",
            "webp"
        ],

        accept_multiple_files=True,

        key="warehouse_file_picker_v26"

    )


    if new_files:

        added_count = add_pending_files(
            new_files
        )


        if added_count:

            st.success(
                f"Đã thêm {added_count} file vào danh sách chờ."
            )


    # ================================================================
    # PENDING FILES
    # ================================================================

    pending_files = (
        st.session_state[
            "pending_uploads_v26"
        ]
    )


    st.markdown(
        "### 📋 Danh sách file đang chờ nạp"
    )


    if not pending_files:

        st.warning(
            "Chưa có file nào đang chờ."
        )


    else:

        st.write(
            f"Đang chờ **{len(pending_files)}** file."
        )


        # ============================================================
        # CLEAR PENDING
        # ============================================================

        if st.button(

            "🗑️ XÓA TOÀN BỘ FILE ĐANG CHỜ",

            key="clear_pending_v26",

            use_container_width=True

        ):

            clear_pending_files()

            st.rerun()


        # ============================================================
        # FILE LIST
        # ============================================================

        for index, item in enumerate(
            pending_files
        ):

            col1, col2, col3 = st.columns(
                [1, 4, 1]
            )


            with col1:

                try:

                    st.image(
                        item["bytes"],
                        width=100
                    )

                except Exception:

                    st.write(
                        "📷"
                    )


            with col2:

                st.markdown(
                    f"**{item['name']}**"
                )

                st.caption(
                    "Chưa lưu vào kho"
                )


            with col3:

                if st.button(

                    "❌",

                    key=f"remove_pending_{index}"

                ):

                    remove_pending_file(
                        index
                    )

                    st.rerun()


    # ================================================================
    # UPLOAD ALL
    # ================================================================

    if pending_files:

        st.divider()


        if st.button(

            "📤 BẮT ĐẦU NẠP TOÀN BỘ VÀO KHO",

            type="primary",

            use_container_width=True,

            key="upload_all_v26"

        ):

            total = len(
                pending_files
            )


            progress = st.progress(
                0
            )


            status = st.empty()


            success_count = 0

            failed_count = 0


            files_to_process = list(
                pending_files
            )


            for index, item in enumerate(
                files_to_process
            ):

                filename = item[
                    "name"
                ]


                file_bytes = item[
                    "bytes"
                ]


                product_code = (
                    extract_product_code(
                        filename
                    )
                )


                status.write(
                    f"🤖 AI đang xử lý "
                    f"**{product_code}** "
                    f"({index + 1}/{total})"
                )


                try:

                    # =================================================
                    # STEP 1
                    # GEMINI VISION
                    # =================================================

                    ai_result = (
                        analyze_garment_with_gemini(
                            file_bytes
                        )
                    )


                    category = (
                        ai_result[
                            "category"
                        ]
                    )


                    st.write(
                        f"🤖 {product_code}: "
                        f"**{category}** "
                        f"({ai_result['confidence']:.0f}%)"
                    )


                    # =================================================
                    # STEP 2
                    # EMBEDDING
                    # =================================================

                    embedding = (
                        create_image_embedding(
                            file_bytes
                        )
                    )


                    # =================================================
                    # STEP 3
                    # STORAGE
                    # =================================================

                    (
                        image_url,
                        storage_path

                    ) = upload_image_to_storage(

                        file_bytes,

                        filename

                    )


                    # =================================================
                    # STEP 4
                    # DATABASE
                    # =================================================

                    save_product_to_database(

                        product_code=
                            product_code,

                        image_url=
                            image_url,

                        storage_path=
                            storage_path,

                        category=
                            category,

                        ai_analysis=
                            ai_result,

                        embedding=
                            embedding

                    )


                    success_count += 1


                    st.success(
                        f"✅ {filename} → "
                        f"{category}"
                    )


                except Exception as e:

                    failed_count += 1


                    st.error(
                        f"❌ {filename}: {e}"
                    )


                progress.progress(
                    (index + 1)
                    /
                    total
                )


            status.empty()


            # =========================================================
            # CHỈ XÓA DANH SÁCH CHỜ
            #
            # KHÔNG XÓA:
            # - Storage
            # - products
            # =========================================================

            st.session_state[
                "pending_uploads_v26"
            ] = []


            st.success(
                f"🎉 Hoàn tất! "
                f"Thành công: {success_count} | "
                f"Lỗi: {failed_count}"
            )


            st.info(
                "Danh sách file chờ đã được làm sạch. "
                "Dữ liệu trong kho vẫn được giữ nguyên."
            )


# =====================================================================
# 30. FOOTER
# =====================================================================

st.divider()

st.caption(
    "AI Garment Similarity Search "
    f"| {APP_VERSION} "
    "| Gemini Vision + Gemini Embedding 2 + Supabase pgvector"
)
