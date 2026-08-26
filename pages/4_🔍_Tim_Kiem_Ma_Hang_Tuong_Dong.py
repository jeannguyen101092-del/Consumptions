# =====================================================================
# 🔍 PRODUCT IMAGE SEARCH & BULK STORAGE
# VERSION V2.4
#
# MASTER LOCAL CLIP IMAGE EMBEDDING ENGINE
#
# MODEL:
# openai/clip-vit-base-patch32
#
# OUTPUT:
# 512-dimensional image embedding
#
# IMPORTANT:
# ❌ KHÔNG dùng Hugging Face Inference API
# ❌ KHÔNG dùng HF_TOKEN để inference
# ❌ KHÔNG gọi router.huggingface.co
#
# CLIP được chạy LOCAL bằng:
# transformers + torch
#
# FLOW:
#
# IMAGE
#   ↓
# PIL RGB
#   ↓
# CLIPProcessor
#   ↓
# CLIPModel.get_image_features()
#   ↓
# 512D VECTOR
#   ↓
# L2 NORMALIZATION
#   ↓
# Supabase products.embedding
#   ↓
# match_products_v2()
#   ↓
# TOP 4 SIMILAR PRODUCTS
# =====================================================================


# =====================================================================
# 0. IMPORT
# =====================================================================

import io
import re
import hashlib
import math

import streamlit as st

from PIL import Image

import torch

from transformers import (
    CLIPModel,
    CLIPProcessor
)

from supabase import (
    create_client,
    Client
)


# =====================================================================
# 1. STREAMLIT CONFIG
# =====================================================================

st.set_page_config(

    page_title="Quản lý & Tìm kiếm mã hàng",

    page_icon="🔍",

    layout="wide"

)


# =====================================================================
# 2. SUPABASE SECRET READER
# =====================================================================
#
# Key thật KHÔNG nằm trong GitHub.
#
# Chỉ đọc từ Streamlit/Tomy Secrets.
# =====================================================================

def get_secret_value(names):

    # ---------------------------------------------------------
    # Tìm trực tiếp
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
    # Tìm trong group
    # ---------------------------------------------------------

    groups = [

        "supabase",

        "SUPABASE"

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

        "anon_key"

    ]

)


# =====================================================================
# 5. CHECK SUPABASE SECRET
# =====================================================================

missing = []


if not SUPABASE_URL:

    missing.append(
        "SUPABASE_URL"
    )


if not SUPABASE_KEY:

    missing.append(
        "SUPABASE_KEY"
    )


if missing:

    st.error(
        "❌ Không đọc được Supabase Secrets."
    )

    st.warning(

        "Thiếu:\n\n"

        +

        "\n".join(
            [
                f"- {x}"
                for x in missing
            ]
        )

    )

    st.stop()


# =====================================================================
# 6. SUPABASE CONNECTION
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
# 7. CLIP CONFIG
# =====================================================================

CLIP_MODEL_NAME = (
    "openai/clip-vit-base-patch32"
)


CLIP_DIMENSION = 512


# =====================================================================
# 8. DEVICE
# =====================================================================

if torch.cuda.is_available():

    DEVICE = torch.device(
        "cuda"
    )

    DEVICE_NAME = "CUDA GPU"

else:

    DEVICE = torch.device(
        "cpu"
    )

    DEVICE_NAME = "CPU"


# =====================================================================
# 9. LOAD CLIP MODEL
# =====================================================================
#
# Model chỉ load một lần trong Streamlit.
#
# Không gọi Hugging Face inference API.
#
# Lần đầu chạy app sẽ tải model về.
# =====================================================================

@st.cache_resource(
    show_spinner="🤖 Đang tải CLIP AI model..."
)
def load_clip_model():

    processor = CLIPProcessor.from_pretrained(

        CLIP_MODEL_NAME

    )


    model = CLIPModel.from_pretrained(

        CLIP_MODEL_NAME

    )


    model = model.to(
        DEVICE
    )


    model.eval()


    return processor, model


# =====================================================================
# 10. LOAD MODEL
# =====================================================================

try:

    clip_processor, clip_model = (
        load_clip_model()
    )

except Exception as e:

    st.error(
        "❌ Không thể tải CLIP model."
    )

    st.exception(e)

    st.stop()


# =====================================================================
# 11. CATEGORY
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

def normalize_image(
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
        # EXIF orientation
        # ---------------------------------------------------------

        try:

            from PIL import ImageOps

            image = ImageOps.exif_transpose(
                image
            )

        except Exception:

            pass


        return image


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

def normalize_embedding(
    embedding
):

    values = [

        float(x)

        for x in embedding

    ]


    norm = math.sqrt(

        sum(

            x * x

            for x in values

        )

    )


    if norm <= 0:

        raise Exception(

            "Embedding norm = 0."

        )


    return [

        x / norm

        for x in values

    ]


# =====================================================================
# 15. CLIP IMAGE EMBEDDING
# =====================================================================
#
# Đây là phần QUAN TRỌNG NHẤT.
#
# Không có requests.post()
# Không có HF API
# Không có HF_TOKEN
#
# Chạy trực tiếp:
#
# image
# ↓
# processor
# ↓
# CLIP vision encoder
# ↓
# visual projection
# ↓
# 512D
# =====================================================================

def get_clip_image_embedding(
    image
):

    try:

        # ---------------------------------------------------------
        # PROCESS IMAGE
        # ---------------------------------------------------------

        inputs = clip_processor(

            images=image,

            return_tensors="pt"

        )


        # ---------------------------------------------------------
        # MOVE TO DEVICE
        # ---------------------------------------------------------

        inputs = {

            key: value.to(DEVICE)

            for key, value in inputs.items()

        }


        # ---------------------------------------------------------
        # CLIP IMAGE FEATURES
        # ---------------------------------------------------------

        with torch.inference_mode():

            image_features = (
                clip_model.get_image_features(
                    **inputs
                )
            )


        # ---------------------------------------------------------
        # EXPECTED SHAPE:
        #
        # [1, 512]
        # ---------------------------------------------------------

        if image_features.ndim != 2:

            raise Exception(

                "CLIP output shape không hợp lệ: "

                +

                str(
                    tuple(
                        image_features.shape
                    )
                )

            )


        # ---------------------------------------------------------
        # CHECK DIMENSION
        # ---------------------------------------------------------

        dimension = (
            image_features.shape[-1]
        )


        if dimension != CLIP_DIMENSION:

            raise Exception(

                f"CLIP dimension sai: "
                f"{dimension}. "
                f"Expected: "
                f"{CLIP_DIMENSION}."

            )


        # ---------------------------------------------------------
        # L2 NORMALIZE
        # ---------------------------------------------------------

        image_features = (

            image_features

            /

            image_features.norm(

                p=2,

                dim=-1,

                keepdim=True

            )

        )


        # ---------------------------------------------------------
        # CPU
        # ---------------------------------------------------------

        embedding = (

            image_features[0]

            .detach()

            .cpu()

            .float()

            .tolist()

        )


        # ---------------------------------------------------------
        # FINAL CHECK
        # ---------------------------------------------------------

        if len(embedding) != 512:

            raise Exception(

                f"Embedding cuối cùng "
                f"không phải 512D: "
                f"{len(embedding)}"

            )


        return embedding


    except Exception as e:

        raise Exception(

            f"Lỗi CLIP image embedding: {e}"

        )


# =====================================================================
# 16. CACHE EMBEDDING
# =====================================================================

@st.cache_data(

    ttl=86400,

    show_spinner=False

)
def get_cached_clip_embedding(

    image_hash,

    image_bytes

):

    image = normalize_image(

        image_bytes

    )


    return get_clip_image_embedding(

        image

    )


# =====================================================================
# 17. SANITIZE FILENAME
# =====================================================================

def sanitize_filename(
    filename
):

    filename = (
        filename.strip()
    )


    filename = re.sub(

        r"[^A-Za-z0-9._-]",

        "_",

        filename

    )


    return filename


# =====================================================================
# 18. EXTRACT PRODUCT CODE
# =====================================================================

def extract_product_code(
    filename
):

    filename_only = (

        filename

        .rsplit(
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
# 19. CONTENT TYPE
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


    return "application/octet-stream"


# =====================================================================
# 20. UPLOAD IMAGE TO SUPABASE STORAGE
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
                    get_content_type(
                        safe_filename
                    ),

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

            f"Storage upload lỗi: {e}"

        )


# =====================================================================
# 21. SAVE PRODUCT
# =====================================================================

def save_product(

    product_code,

    image_url,

    category,

    embedding

):

    # ---------------------------------------------------------
    # HARD CHECK
    # ---------------------------------------------------------

    if len(embedding) != 512:

        raise Exception(

            "Không ghi DB vì embedding "
            f"không phải 512D: "
            f"{len(embedding)}"

        )


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

            f"Database save lỗi: {e}"

        )


# =====================================================================
# 22. TAB
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

        "🔍 Tìm Kiếm Mã Hàng Qua Ảnh Sketch"

    )


    # ---------------------------------------------------------
    # SYSTEM STATUS
    # ---------------------------------------------------------

    st.success(

        "🤖 CLIP LOCAL READY"

    )


    st.caption(

        f"Model: {CLIP_MODEL_NAME} | "

        f"Vector: {CLIP_DIMENSION}D | "

        f"Device: {DEVICE_NAME}"

    )


    col_search_1, col_search_2 = (
        st.columns(2)
    )


    # ---------------------------------------------------------
    # INPUT
    # ---------------------------------------------------------

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


    # ---------------------------------------------------------
    # SEARCH
    # ---------------------------------------------------------

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
                        # READ
                        # -------------------------------------------------

                        raw_bytes = (
                            uploaded_sketch
                            .getvalue()
                        )


                        if not raw_bytes:

                            raise Exception(

                                "Ảnh rỗng."

                            )


                        # -------------------------------------------------
                        # HASH
                        # -------------------------------------------------

                        image_hash = (
                            get_image_hash(
                                raw_bytes
                            )
                        )


                        # -------------------------------------------------
                        # EMBEDDING
                        # -------------------------------------------------

                        sketch_embedding = (

                            get_cached_clip_embedding(

                                image_hash,

                                raw_bytes

                            )

                        )


                        # -------------------------------------------------
                        # VERIFY
                        # -------------------------------------------------

                        if len(
                            sketch_embedding
                        ) != 512:

                            raise Exception(

                                "Vector CLIP "
                                "không phải 512D."

                            )


                        st.success(

                            "✅ CLIP embedding "
                            "thành công."

                        )


                        st.caption(

                            "Vector dimension: "
                            f"{len(sketch_embedding)}"

                        )


                        # -------------------------------------------------
                        # RPC
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

                                f"🎯 Tìm thấy "
                                f"{len(response.data)} "
                                "mã tương đồng."

                            )


                            cols = st.columns(

                                len(
                                    response.data
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


                                    st.subheader(

                                        "Mã: "

                                        +

                                        str(

                                            item.get(

                                                "product_code",

                                                "N/A"

                                            )

                                        )

                                    )


                                    if item.get(
                                        "image_url"
                                    ):

                                        st.image(

                                            item[
                                                "image_url"
                                            ],

                                            use_container_width=True

                                        )


                                    st.caption(

                                        "Category: "

                                        +

                                        str(

                                            item.get(

                                                "category",

                                                ""

                                            )

                                        )

                                    )


                        else:

                            st.warning(

                                "⚠️ Không tìm thấy "
                                "mã tương đồng."

                            )


                    except Exception as e:

                        st.error(

                            "❌ SEARCH ERROR"

                        )

                        st.exception(e)


# =====================================================================
# TAB 2
# BULK UPLOAD
# =====================================================================

with tab2:

    st.header(

        "📦 Đẩy Dữ Liệu Mã Hàng Hàng Loạt "
        "Lên Hệ Thống"

    )


    st.info(

        "💡 Tên file = mã hàng.\n\n"

        "Ví dụ:\n\n"

        "`R09-490416.JPG`"

        " → "

        "`R09-490416`"

    )


    col_upload_1, col_upload_2 = (
        st.columns(2)
    )


    # ---------------------------------------------------------
    # INPUT
    # ---------------------------------------------------------

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

                "Chọn nhiều ảnh sản phẩm:",

                type=[

                    "png",

                    "jpg",

                    "jpeg"

                ],

                accept_multiple_files=True,

                key="fu_bulk"

            )
        )


    # ---------------------------------------------------------
    # BULK
    # ---------------------------------------------------------

    if uploaded_files:

        with col_upload_2:

            st.write(

                f"📂 Đã chọn "
                f"**{len(uploaded_files)}** "
                "file."

            )


            if st.button(

                "📤 Tiến hành lưu toàn bộ vào kho",

                type="primary",

                key="btn_bulk"

            ):

                progress = st.progress(0)

                status = st.empty()


                success_count = 0

                failed_count = 0

                failed_items = []


                # =================================================
                # LOOP
                # =================================================

                for index, file in enumerate(

                    uploaded_files

                ):

                    product_code = (

                        extract_product_code(

                            file.name

                        )

                    )


                    status.text(

                        f"⏳ Đang xử lý "
                        f"{index + 1}/"
                        f"{len(uploaded_files)}: "
                        f"{product_code}"

                    )


                    try:

                        # ---------------------------------------------
                        # READ
                        # ---------------------------------------------

                        raw_bytes = (
                            file.getvalue()
                        )


                        if not raw_bytes:

                            raise Exception(

                                "File rỗng."

                            )


                        # ---------------------------------------------
                        # NORMALIZE IMAGE
                        # ---------------------------------------------

                        image = (
                            normalize_image(
                                raw_bytes
                            )
                        )


                        # ---------------------------------------------
                        # CLIP
                        # ---------------------------------------------

                        embedding = (

                            get_clip_image_embedding(

                                image

                            )

                        )


                        # ---------------------------------------------
                        # VERIFY
                        # ---------------------------------------------

                        if len(
                            embedding
                        ) != 512:

                            raise Exception(

                                "CLIP vector "
                                f"không phải 512D: "
                                f"{len(embedding)}"

                            )


                        # ---------------------------------------------
                        # STORAGE
                        # ---------------------------------------------

                        image_url = (

                            upload_image_to_storage(

                                raw_bytes,

                                file.name

                            )

                        )


                        if not image_url:

                            raise Exception(

                                "Không lấy được "
                                "image URL."

                            )


                        # ---------------------------------------------
                        # DATABASE
                        # ---------------------------------------------

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


                    # ---------------------------------------------
                    # PROGRESS
                    # ---------------------------------------------

                    progress.progress(

                        int(

                            (

                                index + 1

                            )

                            /

                            len(
                                uploaded_files
                            )

                            *

                            100

                        )

                    )


                # =================================================
                # COMPLETE
                # =================================================

                status.empty()


                if success_count:

                    st.success(

                        "🎉 Hoàn thành!\n\n"

                        f"✅ Thành công: "
                        f"{success_count}\n\n"

                        f"❌ Lỗi: "
                        f"{failed_count}"

                    )


                if failed_items:

                    with st.expander(

                        "🔎 Chi tiết file lỗi"

                    ):

                        for item in failed_items:

                            st.error(

                                f"File: "
                                f"{item['file']}\n\n"

                                f"Mã: "
                                f"{item['product_code']}\n\n"

                                f"Lỗi: "
                                f"{item['error']}"

                            )


# =====================================================================
# END
# =====================================================================
