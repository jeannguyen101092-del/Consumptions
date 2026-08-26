# =====================================================================
# 🔍 PRODUCT IMAGE SEARCH & BULK STORAGE
# VERSION V2.3
#
# MASTER CLIP IMAGE EMBEDDING ENGINE
#
# FLOW:
#
# IMAGE
#   ↓
# NORMALIZE
#   ↓
# CLIP IMAGE EMBEDDING
#   ↓
# VECTOR
#   ↓
# SUPABASE products.embedding
#   ↓
# match_products_v2
#   ↓
# TOP SIMILAR PRODUCTS
#
# 🔐 ALL SECRETS ARE READ FROM STREAMLIT / TOMY SECRETS
# ❌ NO API KEY / TOKEN IS WRITTEN IN GITHUB
# =====================================================================


import streamlit as st
from supabase import create_client, Client

import requests
from PIL import Image

import io
import re
import hashlib
import math


# =====================================================================
# 1. STREAMLIT CONFIG
# =====================================================================

st.set_page_config(
    page_title="Quản lý & Tìm kiếm mã hàng",
    page_icon="🔍",
    layout="wide"
)


# =====================================================================
# 2. SECRET READER
# =====================================================================
# Không ghi Secret trực tiếp trong GitHub.
#
# Hàm này hỗ trợ cả:
#
# SUPABASE_URL
# SUPABASE_KEY
# HF_TOKEN
#
# và một số tên biến tương đương.
# =====================================================================

def get_secret_value(names):

    # ---------------------------------------------------------
    # A. Tìm Secret trực tiếp
    # ---------------------------------------------------------

    for name in names:

        try:

            value = st.secrets.get(name)

            if value is not None:

                value = str(value).strip()

                if value:

                    return value

        except Exception:

            pass


    # ---------------------------------------------------------
    # B. Tìm trong nhóm Secret
    # ---------------------------------------------------------

    groups = [
        "supabase",
        "SUPABASE",
        "huggingface",
        "HUGGINGFACE",
        "hf",
        "HF"
    ]


    for group_name in groups:

        try:

            group = st.secrets.get(
                group_name
            )

            if group:

                for name in names:

                    try:

                        value = group.get(
                            name
                        )

                        if value is not None:

                            value = (
                                str(value)
                                .strip()
                            )

                            if value:

                                return value

                    except Exception:

                        pass

        except Exception:

            pass


    return None


# =====================================================================
# 3. SUPABASE URL
# =====================================================================

SUPABASE_URL = get_secret_value(
    [
        "SUPABASE_URL",
        "SUPABASE_PROJECT_URL",
        "SUPABASE_PROJECT",
        "supabase_url",
        "supabase_project_url"
    ]
)


# =====================================================================
# 4. SUPABASE KEY
# =====================================================================

SUPABASE_KEY = get_secret_value(
    [
        "SUPABASE_KEY",
        "SUPABASE_ANON_KEY",
        "SUPABASE_API_KEY",
        "supabase_key",
        "supabase_anon_key",
        "anon_key",
        "api_key"
    ]
)


# =====================================================================
# 5. HUGGING FACE TOKEN
# =====================================================================

HF_TOKEN = get_secret_value(
    [
        "HF_TOKEN",
        "HUGGINGFACE_TOKEN",
        "HUGGING_FACE_TOKEN",
        "HF_API_TOKEN",
        "HUGGINGFACE_API_TOKEN",
        "huggingface_token",
        "hugging_face_token",
        "hf_token"
    ]
)


# =====================================================================
# 6. KIỂM TRA SECRET
# =====================================================================

missing_secrets = []


if not SUPABASE_URL:

    missing_secrets.append(
        "SUPABASE URL"
    )


if not SUPABASE_KEY:

    missing_secrets.append(
        "SUPABASE KEY"
    )


if not HF_TOKEN:

    missing_secrets.append(
        "HUGGING FACE TOKEN"
    )


if missing_secrets:

    st.error(
        "❌ Không đọc được Secret cần thiết."
    )

    st.warning(
        "Thiếu:\n\n"
        + "\n".join(
            [
                f"- {x}"
                for x in missing_secrets
            ]
        )
    )

    st.stop()


# =====================================================================
# 7. CLIP MODEL
# =====================================================================
#
# CLIP model dùng cho image embedding.
#
# Có thể thay bằng model CLIP tương thích khác
# bằng cách tạo HF_MODEL trong Secrets.
#
# =====================================================================

HF_MODEL = get_secret_value(
    [
        "HF_MODEL",
        "HUGGINGFACE_MODEL",
        "HF_IMAGE_MODEL",
        "huggingface_model"
    ]
)


if not HF_MODEL:

    HF_MODEL = (
        "openai/clip-vit-base-patch32"
    )


# =====================================================================
# 8. HUGGING FACE FEATURE EXTRACTION API
# =====================================================================
#
# KHÔNG dùng:
#
# router.huggingface.co/hf-inference/models/...
#
# vì provider đó đã báo:
#
# Model not supported by provider hf-inference
#
# Ta dùng endpoint router với task image-feature-extraction.
# =====================================================================

HF_API_URL = (
    "https://router.huggingface.co/"
    "hf-inference/models/"
    f"{HF_MODEL}"
)


# =====================================================================
# 9. HUGGING FACE HEADERS
# =====================================================================

HF_HEADERS = {

    "Authorization":
        f"Bearer {HF_TOKEN}",

    "Content-Type":
        "application/octet-stream",

    "Accept":
        "application/json",

    "User-Agent":
        (
            "Mozilla/5.0 "
            "(Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/120.0.0.0 "
            "Safari/537.36"
        )
}


# =====================================================================
# 10. SUPABASE CONNECTION
# =====================================================================

try:

    supabase: Client = create_client(

        SUPABASE_URL,

        SUPABASE_KEY

    )

except Exception as e:

    st.error(
        "❌ Không thể kết nối Supabase."
    )

    st.exception(e)

    st.stop()


# =====================================================================
# 11. CATEGORY OPTIONS
# =====================================================================

CATEGORY_OPTIONS = [

    "Quần dài",

    "Quần short",

    "Áo",

    "Quần jogger",

    "Quần jean",

    "Quần túi hộp"

]


# =====================================================================
# 12. NORMALIZE IMAGE
# =====================================================================
#
# CLIP nhận RGB image.
#
# Tất cả PNG/JPG được chuẩn hóa thành JPEG RGB.
# =====================================================================

def normalize_image_bytes(
    file_bytes
):

    try:

        image = Image.open(
            io.BytesIO(
                file_bytes
            )
        )


        # ---------------------------------------------------------
        # RGB
        # ---------------------------------------------------------

        if image.mode != "RGB":

            image = image.convert(
                "RGB"
            )


        # ---------------------------------------------------------
        # Resize nhẹ để giảm payload
        #
        # Không crop vì crop có thể làm mất hình dáng garment.
        # Giữ nguyên aspect ratio.
        # ---------------------------------------------------------

        max_size = 1600

        width, height = image.size


        if max(
            width,
            height
        ) > max_size:

            scale = (
                max_size
                /
                max(width, height)
            )


            new_width = int(
                width * scale
            )


            new_height = int(
                height * scale
            )


            image = image.resize(

                (
                    new_width,
                    new_height
                ),

                Image.Resampling.LANCZOS

            )


        # ---------------------------------------------------------
        # JPEG
        # ---------------------------------------------------------

        output = io.BytesIO()


        image.save(

            output,

            format="JPEG",

            quality=95,

            optimize=True

        )


        return output.getvalue()


    except Exception as e:

        raise Exception(

            f"Không đọc được ảnh: {e}"

        )


# =====================================================================
# 13. IMAGE HASH
# =====================================================================

def get_image_hash(
    image_bytes
):

    return hashlib.sha256(
        image_bytes
    ).hexdigest()


# =====================================================================
# 14. L2 NORMALIZATION
# =====================================================================
#
# CLIP similarity thường sử dụng cosine similarity.
#
# Normalize vector giúp:
#
# cosine_similarity(A,B)
#
# tương đương:
#
# dot(normalize(A), normalize(B))
# =====================================================================

def normalize_embedding(
    embedding
):

    if not embedding:

        raise Exception(
            "Embedding rỗng."
        )


    norm = math.sqrt(

        sum(

            float(x) * float(x)

            for x in embedding

        )

    )


    if norm <= 0:

        raise Exception(
            "Embedding có norm = 0."
        )


    return [

        float(x) / norm

        for x in embedding

    ]


# =====================================================================
# 15. FLATTEN VECTOR
# =====================================================================
#
# HF có thể trả:
#
# [vector]
#
# hoặc:
#
# [[token1], [token2], ...]
#
# hoặc:
#
# [[[...]]]
#
# Ta phải gom thành một vector duy nhất.
# =====================================================================

def flatten_numeric_vector(
    data
):

    # ---------------------------------------------------------
    # Nếu data là số
    # ---------------------------------------------------------

    if isinstance(
        data,
        (int, float)
    ):

        return [
            float(data)
        ]


    # ---------------------------------------------------------
    # Nếu data là list
    # ---------------------------------------------------------

    if isinstance(
        data,
        list
    ):

        # -----------------------------------------------------
        # list rỗng
        # -----------------------------------------------------

        if not data:

            return []


        # -----------------------------------------------------
        # toàn số
        # -----------------------------------------------------

        if all(

            isinstance(
                x,
                (int, float)
            )

            for x in data

        ):

            return [

                float(x)

                for x in data

            ]


        # -----------------------------------------------------
        # nested list
        # -----------------------------------------------------

        vectors = []


        for item in data:

            sub_vector = (
                flatten_numeric_vector(
                    item
                )
            )


            if sub_vector:

                vectors.append(
                    sub_vector
                )


        if not vectors:

            return []


        # -----------------------------------------------------
        # Nếu chỉ có một vector
        # -----------------------------------------------------

        if len(vectors) == 1:

            return vectors[0]


        # -----------------------------------------------------
        # Mean pooling
        #
        # Ví dụ:
        #
        # token vectors:
        #
        # [512]
        # [512]
        # [512]
        #
        # → một image vector [512]
        # -----------------------------------------------------

        dimension = len(
            vectors[0]
        )


        valid_vectors = [

            v

            for v in vectors

            if len(v) == dimension

        ]


        if not valid_vectors:

            return []


        pooled = [

            sum(

                v[i]

                for v in valid_vectors

            )

            /

            len(valid_vectors)

            for i in range(
                dimension
            )

        ]


        return pooled


    return []


# =====================================================================
# 16. CALL CLIP IMAGE EMBEDDING
# =====================================================================

def get_clip_image_embedding(
    image_bytes
):

    # ---------------------------------------------------------
    # Gửi image tới Hugging Face
    # ---------------------------------------------------------

    try:

        response = requests.post(

            HF_API_URL,

            headers=HF_HEADERS,

            data=image_bytes,

            timeout=180

        )


    except requests.exceptions.Timeout:

        raise Exception(

            "Hugging Face timeout "
            "sau 180 giây."

        )


    except requests.exceptions.RequestException as e:

        raise Exception(

            f"Lỗi kết nối Hugging Face: {e}"

        )


    # ---------------------------------------------------------
    # HTTP ERROR
    # ---------------------------------------------------------

    if response.status_code != 200:

        error_text = response.text


        try:

            error_json = (
                response.json()
            )


            if isinstance(
                error_json,
                dict
            ):

                error_text = (

                    error_json.get(
                        "error"
                    )

                    or

                    error_json.get(
                        "message"
                    )

                    or

                    error_text

                )

        except Exception:

            pass


        raise Exception(

            "Hugging Face HTTP "
            f"{response.status_code}: "
            f"{error_text}"

        )


    # ---------------------------------------------------------
    # PARSE RESPONSE
    # ---------------------------------------------------------

    try:

        result = response.json()

    except Exception:

        raise Exception(

            "Hugging Face trả về "
            "response không phải JSON."

        )


    # ---------------------------------------------------------
    # DEBUG RESPONSE SHAPE
    # ---------------------------------------------------------

    embedding = None


    # ---------------------------------------------------------
    # DẠNG 1
    #
    # [0.1, 0.2, ...]
    # ---------------------------------------------------------

    if isinstance(
        result,
        list
    ):

        embedding = (
            flatten_numeric_vector(
                result
            )
        )


    # ---------------------------------------------------------
    # DẠNG 2
    #
    # {"embedding": [...]}
    # ---------------------------------------------------------

    elif isinstance(
        result,
        dict
    ):

        possible_keys = [

            "embedding",

            "embeddings",

            "vector",

            "feature",

            "features"

        ]


        for key in possible_keys:

            if key in result:

                embedding = (
                    flatten_numeric_vector(
                        result[key]
                    )
                )

                if embedding:

                    break


    # ---------------------------------------------------------
    # CHECK
    # ---------------------------------------------------------

    if not embedding:

        raise Exception(

            "Không lấy được CLIP image embedding.\n\n"

            f"Response type: "
            f"{type(result).__name__}\n\n"

            f"Response: {str(result)[:1000]}"

        )


    # ---------------------------------------------------------
    # FLOAT
    # ---------------------------------------------------------

    try:

        embedding = [

            float(x)

            for x in embedding

        ]

    except Exception:

        raise Exception(

            "CLIP embedding chứa "
            "giá trị không phải số."

        )


    # ---------------------------------------------------------
    # NORMALIZE
    # ---------------------------------------------------------

    embedding = (
        normalize_embedding(
            embedding
        )
    )


    # ---------------------------------------------------------
    # FINAL CHECK
    # ---------------------------------------------------------

    if len(embedding) < 2:

        raise Exception(

            "CLIP embedding dimension "
            "không hợp lệ."

        )


    return embedding


# =====================================================================
# 17. CACHE CLIP EMBEDDING
# =====================================================================

@st.cache_data(
    ttl=86400,
    show_spinner=False
)
def get_cached_clip_embedding(

    image_hash,

    image_bytes

):

    return get_clip_image_embedding(
        image_bytes
    )


# =====================================================================
# 18. CONTENT TYPE
# =====================================================================

def get_content_type(
    filename
):

    extension = (

        filename
        .lower()
        .rsplit(
            ".",
            1
        )[-1]

    )


    if extension == "png":

        return "image/png"


    if extension in [
        "jpg",
        "jpeg"
    ]:

        return "image/jpeg"


    return (
        "application/octet-stream"
    )


# =====================================================================
# 19. SANITIZE FILENAME
# =====================================================================

def sanitize_filename(
    filename
):

    filename = filename.strip()


    filename = re.sub(

        r"[^A-Za-z0-9._-]",

        "_",

        filename

    )


    return filename


# =====================================================================
# 20. EXTRACT PRODUCT CODE
# =====================================================================

def extract_product_code(
    filename
):

    filename_only = (
        filename.rsplit(
            ".",
            1
        )[0]
    )


    return (

        filename_only

        .strip()

        .upper()

    )


# =====================================================================
# 21. UPLOAD IMAGE
# =====================================================================

def upload_image_to_storage(

    file_bytes,

    filename

):

    bucket_name = (
        "product-images"
    )


    safe_filename = (
        sanitize_filename(
            filename
        )
    )


    try:

        content_type = (
            get_content_type(
                safe_filename
            )
        )


        storage = (
            supabase
            .storage
            .from_(
                bucket_name
            )
        )


        storage.upload(

            path=safe_filename,

            file=file_bytes,

            file_options={

                "content-type":
                    content_type,

                "upsert":
                    "true"

            }

        )


        public_url = (
            storage
            .get_public_url(
                safe_filename
            )
        )


        return public_url


    except Exception as e:

        raise Exception(

            f"Lỗi upload Storage: "
            f"{e}"

        )


# =====================================================================
# 22. SAVE PRODUCT
# =====================================================================

def save_product(

    product_code,

    image_url,

    category,

    embedding

):

    try:

        result = (

            supabase

            .table(
                "products"
            )

            .upsert(

                {

                    "product_code":
                        product_code,

                    "image_url":
                        image_url,

                    "category":
                        category,

                    "embedding":
                        embedding

                },

                on_conflict=
                    "product_code"

            )

            .execute()

        )


        return result


    except Exception as e:

        raise Exception(

            f"Lỗi lưu product "
            f"{product_code}: {e}"

        )


# =====================================================================
# 23. CATEGORY
# =====================================================================

CATEGORY_OPTIONS = [

    "Quần dài",

    "Quần short",

    "Áo",

    "Quần jogger",

    "Quần jean",

    "Quần túi hộp"

]


# =====================================================================
# 24. TABS
# =====================================================================

tab1, tab2 = st.tabs(

    [

        "🔍 TÌM KIẾM MÃ HÀNG TƯƠNG ĐỒNG",

        "📦 LƯU KHO HÀNG LOẠT"

    ]

)


# =====================================================================
# TAB 1
# SEARCH
# =====================================================================

with tab1:

    st.header(

        "🔍 Tìm Kiếm Mã Hàng "
        "Qua Ảnh Sketch"

    )


    col_search_1, col_search_2 = (
        st.columns(2)
    )


    # -----------------------------------------------------------------
    # INPUT
    # -----------------------------------------------------------------

    with col_search_1:

        search_category = (
            st.selectbox(

                "Chọn dòng hàng cần tìm kiếm:",

                CATEGORY_OPTIONS,

                key="sb_search"

            )
        )


        uploaded_sketch = (
            st.file_uploader(

                "Tải lên ảnh Sketch cần tìm:",

                type=[

                    "png",

                    "jpg",

                    "jpeg"

                ],

                key="fu_search"

            )
        )


    # -----------------------------------------------------------------
    # PREVIEW
    # -----------------------------------------------------------------

    if uploaded_sketch is not None:

        with col_search_2:

            st.image(

                uploaded_sketch,

                caption=
                    "Ảnh Sketch của bạn",

                width=250

            )


            if st.button(

                "🚀 Bắt đầu quét mã tương đồng",

                type="primary",

                key="btn_search"

            ):

                with st.spinner(

                    "🤖 CLIP đang phân tích ảnh..."

                ):

                    try:

                        # -------------------------------------------------
                        # READ IMAGE
                        # -------------------------------------------------

                        raw_bytes = (
                            uploaded_sketch
                            .getvalue()
                        )


                        # -------------------------------------------------
                        # NORMALIZE
                        # -------------------------------------------------

                        sketch_bytes = (
                            normalize_image_bytes(
                                raw_bytes
                            )
                        )


                        # -------------------------------------------------
                        # HASH
                        # -------------------------------------------------

                        image_hash = (
                            get_image_hash(
                                sketch_bytes
                            )
                        )


                        # -------------------------------------------------
                        # CLIP EMBEDDING
                        # -------------------------------------------------

                        sketch_embedding = (

                            get_cached_clip_embedding(

                                image_hash,

                                sketch_bytes

                            )

                        )


                        # -------------------------------------------------
                        # SHOW VECTOR INFO
                        # -------------------------------------------------

                        st.caption(

                            "CLIP vector dimension: "

                            +

                            str(
                                len(
                                    sketch_embedding
                                )
                            )

                        )


                        # -------------------------------------------------
                        # SUPABASE RPC
                        # -------------------------------------------------

                        response = (

                            supabase

                            .rpc(

                                "match_products_v2",

                                {

                                    "query_embedding":
                                        sketch_embedding,

                                    "match_threshold":
                                        0.40,

                                    "match_count":
                                        4,

                                    "filter_category":
                                        search_category

                                }

                            )

                            .execute()

                        )


                        # -------------------------------------------------
                        # RESULTS
                        # -------------------------------------------------

                        if response.data:

                            st.success(

                                "🎯 Tìm thấy "
                                f"{len(response.data)} "
                                "mã hàng tương đồng "
                                f"trong nhóm "
                                f"**{search_category}**."

                            )


                            cols = (
                                st.columns(
                                    len(
                                        response.data
                                    )
                                )
                            )


                            for idx, item in enumerate(

                                response.data

                            ):

                                with cols[idx]:

                                    similarity = float(

                                        item.get(

                                            "similarity",

                                            0

                                        )

                                    )


                                    st.metric(

                                        "Độ giống nhau",

                                        f"{similarity * 100:.2f}%"

                                    )


                                    product_code = (

                                        item.get(

                                            "product_code",

                                            "N/A"

                                        )

                                    )


                                    st.subheader(

                                        f"Mã: "
                                        f"{product_code}"

                                    )


                                    image_url = (

                                        item.get(

                                            "image_url"

                                        )

                                    )


                                    if image_url:

                                        st.image(

                                            image_url,

                                            use_container_width=True

                                        )


                                    else:

                                        st.warning(

                                            "Không có "
                                            "ảnh sản phẩm."

                                        )


                        else:

                            st.warning(

                                "⚠️ Không tìm thấy "
                                "mã hàng tương đồng "
                                f"trong nhóm "
                                f"**{search_category}**."

                            )


                    except Exception as e:

                        st.error(

                            "❌ Lỗi khi tìm kiếm:"

                        )

                        st.exception(e)


# =====================================================================
# TAB 2
# BULK STORAGE
# =====================================================================

with tab2:

    st.header(

        "📦 Đẩy Dữ Liệu Mã Hàng Hàng Loạt "
        "Lên Hệ Thống"

    )


    st.info(

        "💡 Đặt tên ảnh bằng mã hàng.\n\n"

        "Ví dụ:\n\n"

        "`R09-490416.JPG` "
        "→ mã hàng `R09-490416`"

    )


    col_upload_1, col_upload_2 = (
        st.columns(2)
    )


    # -----------------------------------------------------------------
    # INPUT
    # -----------------------------------------------------------------

    with col_upload_1:

        upload_category = (
            st.selectbox(

                "Phân loại dòng hàng khi lưu kho:",

                CATEGORY_OPTIONS,

                key="sb_upload"

            )
        )


        uploaded_files = (
            st.file_uploader(

                "Chọn nhiều ảnh sản phẩm "
                "gốc / ảnh mẫu để lưu kho:",

                type=[

                    "png",

                    "jpg",

                    "jpeg"

                ],

                accept_multiple_files=True,

                key="fu_bulk"

            )
        )


    # -----------------------------------------------------------------
    # FILE LIST
    # -----------------------------------------------------------------

    if uploaded_files:

        with col_upload_2:

            st.write(

                f"📂 Đã chọn "
                f"**{len(uploaded_files)}** "
                f"file ảnh."

            )


            if st.button(

                "📤 Tiến hành lưu toàn bộ vào kho",

                type="primary",

                key="btn_bulk_upload"

            ):

                progress_bar = (
                    st.progress(0)
                )


                status_text = (
                    st.empty()
                )


                success_count = 0

                failed_count = 0

                failed_items = []


                # =====================================================
                # LOOP
                # =====================================================

                for index, file in enumerate(

                    uploaded_files

                ):

                    product_code = (

                        extract_product_code(

                            file.name

                        )

                    )


                    status_text.text(

                        f"⏳ Đang xử lý "
                        f"({index + 1}/"
                        f"{len(uploaded_files)}): "
                        f"{product_code}"

                    )


                    try:

                        # -------------------------------------------------
                        # READ
                        # -------------------------------------------------

                        raw_bytes = (
                            file.getvalue()
                        )


                        if not raw_bytes:

                            raise Exception(
                                "File ảnh rỗng."
                            )


                        # -------------------------------------------------
                        # NORMALIZE
                        # -------------------------------------------------

                        image_bytes = (

                            normalize_image_bytes(

                                raw_bytes

                            )

                        )


                        # -------------------------------------------------
                        # STORAGE FILENAME
                        # -------------------------------------------------

                        safe_filename = (

                            sanitize_filename(

                                file.name

                            )

                        )


                        # -------------------------------------------------
                        # UPLOAD STORAGE
                        # -------------------------------------------------

                        image_url = (

                            upload_image_to_storage(

                                image_bytes,

                                safe_filename

                            )

                        )


                        if not image_url:

                            raise Exception(

                                "Không lấy được "
                                "image URL."

                            )


                        # -------------------------------------------------
                        # HASH
                        # -------------------------------------------------

                        image_hash = (

                            get_image_hash(

                                image_bytes

                            )

                        )


                        # -------------------------------------------------
                        # CLIP IMAGE EMBEDDING
                        # -------------------------------------------------

                        embedding = (

                            get_cached_clip_embedding(

                                image_hash,

                                image_bytes

                            )

                        )


                        # -------------------------------------------------
                        # VECTOR VALIDATION
                        # -------------------------------------------------

                        if not embedding:

                            raise Exception(

                                "CLIP không tạo "
                                "được embedding."

                            )


                        # -------------------------------------------------
                        # SAVE
                        # -------------------------------------------------

                        save_product(

                            product_code=
                                product_code,

                            image_url=
                                image_url,

                            category=
                                upload_category,

                            embedding=
                                embedding

                        )


                        success_count += 1


                    except Exception as e:

                        failed_count += 1


                        failed_items.append(

                            {

                                "file":
                                    file.name,

                                "product_code":
                                    product_code,

                                "error":
                                    str(e)

                            }

                        )


                    # -------------------------------------------------
                    # PROGRESS
                    # -------------------------------------------------

                    progress_bar.progress(

                        int(

                            (

                                (index + 1)

                                /

                                len(
                                    uploaded_files
                                )

                            )

                            *

                            100

                        )

                    )


                # =====================================================
                # COMPLETE
                # =====================================================

                status_text.empty()


                if success_count > 0:

                    st.success(

                        f"🎉 Hoàn thành!\n\n"

                        f"Đã lưu thành công "
                        f"**{success_count}/"
                        f"{len(uploaded_files)}** "
                        "mã hàng."

                    )


                if failed_count > 0:

                    st.warning(

                        f"⚠️ Có "
                        f"**{failed_count}** "
                        "file chưa lưu được."

                    )


                    with st.expander(

                        "🔎 Xem chi tiết file lỗi"

                    ):

                        for item in failed_items:

                            st.error(

                                f"**{item['file']}**\n\n"

                                f"Mã: "
                                f"{item['product_code']}\n\n"

                                f"Lỗi: "
                                f"{item['error']}"

                            )


                st.info(

                    f"📊 Tổng kết: "

                    f"✅ {success_count} thành công | "

                    f"❌ {failed_count} lỗi | "

                    f"📦 {len(uploaded_files)} file"

                )
