# =====================================================================
# 🔍 PRODUCT IMAGE SEARCH & BULK STORAGE
# VERSION V2.4.1
#
# MASTER LOCAL CLIP IMAGE EMBEDDING ENGINE
#
# MODEL:
# openai/clip-vit-base-patch32
#
# OUTPUT:
# 512-dimensional image embedding
#
# ❌ KHÔNG dùng Hugging Face Inference API
# ❌ KHÔNG dùng HF_TOKEN để inference
# ❌ KHÔNG hard-code Supabase key
#
# 🔐 SUPABASE:
# Đọc từ Streamlit Secrets / Tomy
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
# 0. STREAMLIT
# =====================================================================

import streamlit as st


# =====================================================================
# 1. PAGE CONFIG
# =====================================================================

st.set_page_config(
    page_title="Quản lý & Tìm kiếm mã hàng",
    page_icon="🔍",
    layout="wide"
)


# =====================================================================
# 2. DEPENDENCY CHECK
# =====================================================================
#
# Kiểm tra trước khi import torch / transformers.
#
# Nếu thiếu package, app báo chính xác package nào thiếu.
# =====================================================================

MISSING_PACKAGES = []


try:
    import torch
except ModuleNotFoundError:
    torch = None
    MISSING_PACKAGES.append("torch")


try:
    from transformers import (
        CLIPModel,
        CLIPProcessor
    )
except ModuleNotFoundError:
    CLIPModel = None
    CLIPProcessor = None
    MISSING_PACKAGES.append("transformers")


try:
    from PIL import Image, ImageOps
except ModuleNotFoundError:
    Image = None
    ImageOps = None
    MISSING_PACKAGES.append("pillow")


try:
    from supabase import create_client, Client
except ModuleNotFoundError:
    create_client = None
    Client = None
    MISSING_PACKAGES.append("supabase")


import io
import re
import hashlib
import math


# =====================================================================
# 3. STOP NẾU THIẾU PACKAGE
# =====================================================================

if MISSING_PACKAGES:

    st.error(
        "❌ STREAMLIT ĐANG THIẾU THƯ VIỆN"
    )

    st.write(
        "Các package còn thiếu:"
    )

    for package in MISSING_PACKAGES:

        st.code(package)

    st.warning(
        "Hãy thêm các package trên vào "
        "`requirements.txt`, sau đó "
        "Reboot / Clear cache & reboot app."
    )

    st.code(
        "\n".join([
            "streamlit",
            "supabase",
            "pillow",
            "numpy",
            "torch",
            "transformers",
            "safetensors"
        ]),
        language="text"
    )

    st.stop()


# =====================================================================
# 4. SUPABASE SECRET READER
# =====================================================================
#
# KHÔNG hard-code key.
#
# Đọc từ Streamlit Secrets.
# =====================================================================

def get_secret_value(names):

    # ---------------------------------------------------------
    # A. DIRECT SECRETS
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
    # B. GROUP SECRETS
    # ---------------------------------------------------------

    group_names = [
        "supabase",
        "SUPABASE"
    ]


    for group_name in group_names:

        try:

            group = st.secrets.get(group_name)

            if group:

                for name in names:

                    try:

                        value = group.get(name)

                        if value is not None:

                            value = (
                                str(value).strip()
                            )

                            if value:

                                return value

                    except Exception:

                        pass

        except Exception:

            pass


    return None


# =====================================================================
# 5. SUPABASE URL
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
# 6. SUPABASE KEY
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
# 7. CHECK SECRETS
# =====================================================================

missing_secrets = []


if not SUPABASE_URL:

    missing_secrets.append(
        "SUPABASE_URL"
    )


if not SUPABASE_KEY:

    missing_secrets.append(
        "SUPABASE_KEY"
    )


if missing_secrets:

    st.error(
        "❌ Không đọc được thông tin bảo mật "
        "từ Streamlit Secrets."
    )

    st.warning(
        "Hãy kiểm tra các key sau:"
    )

    for item in missing_secrets:

        st.code(item)

    st.stop()


# =====================================================================
# 8. SUPABASE CONNECTION
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
# 9. CLIP CONFIG
# =====================================================================

CLIP_MODEL_NAME = (
    "openai/clip-vit-base-patch32"
)

CLIP_DIMENSION = 512


# =====================================================================
# 10. DEVICE
# =====================================================================

if torch.cuda.is_available():

    DEVICE = torch.device("cuda")

    DEVICE_NAME = "CUDA GPU"

else:

    DEVICE = torch.device("cpu")

    DEVICE_NAME = "CPU"


# =====================================================================
# 11. LOAD CLIP
# =====================================================================
#
# Model chạy LOCAL.
#
# Không gọi:
# requests.post()
# HF inference
# router.huggingface.co
#
# Lần đầu chạy:
# Transformers tải model.
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

    model = model.to(DEVICE)

    model.eval()

    return processor, model


# =====================================================================
# 12. LOAD MODEL
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
# 13. CATEGORY
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
# 14. NORMALIZE IMAGE
# =====================================================================

def normalize_image(file_bytes):

    try:

        image = Image.open(
            io.BytesIO(file_bytes)
        )


        # ---------------------------------------------------------
        # FIX EXIF ROTATION
        # ---------------------------------------------------------

        try:

            image = ImageOps.exif_transpose(
                image
            )

        except Exception:

            pass


        # ---------------------------------------------------------
        # RGB
        # ---------------------------------------------------------

        if image.mode != "RGB":

            image = image.convert("RGB")


        return image


    except Exception as e:

        raise Exception(
            f"Không đọc được ảnh: {e}"
        )


# =====================================================================
# 15. IMAGE HASH
# =====================================================================

def get_image_hash(image_bytes):

    return hashlib.sha256(
        image_bytes
    ).hexdigest()


# =====================================================================
# 16. L2 NORMALIZATION
# =====================================================================

def normalize_embedding(embedding):

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
# 17. CLIP IMAGE EMBEDDING
# =====================================================================

def get_clip_image_embedding(image):

    try:

        # ---------------------------------------------------------
        # PROCESS IMAGE
        # ---------------------------------------------------------

        inputs = clip_processor(
            images=image,
            return_tensors="pt"
        )


        # ---------------------------------------------------------
        # MOVE INPUT TO DEVICE
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
        # CHECK OUTPUT
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


        dimension = (
            image_features.shape[-1]
        )


        # ---------------------------------------------------------
        # MUST BE 512
        # ---------------------------------------------------------

        if dimension != CLIP_DIMENSION:

            raise Exception(
                f"CLIP dimension = {dimension}, "
                f"nhưng hệ thống yêu cầu "
                f"{CLIP_DIMENSION}."
            )


        # ---------------------------------------------------------
        # NORMALIZE
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
        # CPU LIST
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
                "Embedding cuối cùng không phải "
                f"512D: {len(embedding)}"
            )


        return embedding


    except Exception as e:

        raise Exception(
            f"CLIP embedding lỗi: {e}"
        )


# =====================================================================
# 18. CACHED CLIP
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

    embedding = (
        get_clip_image_embedding(
            image
        )
    )

    return embedding


# =====================================================================
# 19. SANITIZE FILENAME
# =====================================================================

def sanitize_filename(filename):

    filename = filename.strip()

    filename = re.sub(
        r"[^A-Za-z0-9._-]",
        "_",
        filename
    )

    return filename


# =====================================================================
# 20. PRODUCT CODE
# =====================================================================

def extract_product_code(filename):

    filename_only = (
        filename
        .rsplit(".", 1)[0]
    )

    return (
        filename_only
        .strip()
        .upper()
    )


# =====================================================================
# 21. CONTENT TYPE
# =====================================================================

def get_content_type(filename):

    extension = (
        filename
        .lower()
        .rsplit(".", 1)[-1]
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
# 22. UPLOAD STORAGE
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
            .from_(bucket_name)
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
            storage.get_public_url(
                safe_filename
            )
        )


        # ---------------------------------------------------------
        # Supabase client có version trả về string,
        # có version trả về dict.
        # ---------------------------------------------------------

        if isinstance(
            public_url,
            dict
        ):

            public_url = (
                public_url.get(
                    "publicUrl"
                )
                or
                public_url.get(
                    "public_url"
                )
            )


        if not public_url:

            raise Exception(
                "Không lấy được public URL."
            )


        return public_url


    except Exception as e:

        raise Exception(
            f"Storage upload lỗi: {e}"
        )


# =====================================================================
# 23. SAVE PRODUCT
# =====================================================================

def save_product(
    product_code,
    image_url,
    category,
    embedding
):

    # ---------------------------------------------------------
    # HARD VALIDATION
    # ---------------------------------------------------------

    if not isinstance(
        embedding,
        list
    ):

        raise Exception(
            "Embedding phải là list."
        )


    if len(embedding) != 512:

        raise Exception(
            "Không ghi database vì embedding "
            f"không phải 512D: "
            f"{len(embedding)}"
        )


    # ---------------------------------------------------------
    # CLEAN VECTOR
    # ---------------------------------------------------------

    embedding = normalize_embedding(
        embedding
    )


    # ---------------------------------------------------------
    # SAVE
    # ---------------------------------------------------------

    try:

        result = (
            supabase
            .table("products")
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

                on_conflict="product_code"

            )
            .execute()
        )


        return result


    except Exception as e:

        raise Exception(
            f"Database save lỗi: {e}"
        )


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
# 25. TAB 1 - SEARCH
# =====================================================================

with tab1:

    st.header(
        "🔍 Tìm Kiếm Mã Hàng Qua Ảnh Sketch"
    )


    # ---------------------------------------------------------
    # AI STATUS
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

        search_category = st.selectbox(

            "Chọn dòng hàng cần tìm kiếm:",

            CATEGORY_OPTIONS,

            key="sb_search"

        )


        uploaded_sketch = st.file_uploader(

            "Tải lên ảnh Sketch cần tìm:",

            type=[
                "png",
                "jpg",
                "jpeg"
            ],

            key="fu_search"

        )


    # ---------------------------------------------------------
    # PREVIEW
    # ---------------------------------------------------------

    if uploaded_sketch is not None:

        with col_search_2:

            st.image(

                uploaded_sketch,

                caption="Ảnh Sketch của bạn",

                width=250

            )


            # -------------------------------------------------
            # SEARCH BUTTON
            # -------------------------------------------------

            if st.button(

                "🚀 Bắt đầu quét mã tương đồng",

                type="primary",

                key="btn_search"

            ):

                with st.spinner(
                    "🤖 CLIP đang phân tích ảnh..."
                ):

                    try:

                        # -----------------------------------------
                        # BYTES
                        # -----------------------------------------

                        raw_bytes = (
                            uploaded_sketch
                            .getvalue()
                        )


                        if not raw_bytes:

                            raise Exception(
                                "Ảnh rỗng."
                            )


                        # -----------------------------------------
                        # HASH
                        # -----------------------------------------

                        image_hash = (
                            get_image_hash(
                                raw_bytes
                            )
                        )


                        # -----------------------------------------
                        # CLIP
                        # -----------------------------------------

                        sketch_embedding = (
                            get_cached_clip_embedding(
                                image_hash,
                                raw_bytes
                            )
                        )


                        # -----------------------------------------
                        # VERIFY
                        # -----------------------------------------

                        if len(
                            sketch_embedding
                        ) != 512:

                            raise Exception(
                                "CLIP vector "
                                "không phải 512D."
                            )


                        st.success(
                            "✅ CLIP embedding thành công."
                        )


                        st.caption(
                            "Vector dimension: "
                            +
                            str(
                                len(
                                    sketch_embedding
                                )
                            )
                        )


                        # -----------------------------------------
                        # RPC
                        # -----------------------------------------

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


                        # -----------------------------------------
                        # RESULTS
                        # -----------------------------------------

                        if response.data:

                            st.success(
                                f"🎯 Tìm thấy "
                                f"{len(response.data)} "
                                "mã tương đồng."
                            )


                            result_count = len(
                                response.data
                            )


                            cols = st.columns(
                                result_count
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
                                "sản phẩm tương đồng."
                            )


                    except Exception as e:

                        st.error(
                            "❌ LỖI TÌM KIẾM"
                        )

                        st.exception(e)


# =====================================================================
# 26. TAB 2 - BULK UPLOAD
# =====================================================================

with tab2:

    st.header(
        "📦 Đẩy Dữ Liệu Mã Hàng Hàng Loạt "
        "Lên Hệ Thống"
    )


    st.info(

        "💡 Tên file = mã hàng.\n\n"
        "Ví dụ:\n\n"
        "`R09-490416.JPG` → `R09-490416`"

    )


    col_upload_1, col_upload_2 = (
        st.columns(2)
    )


    # ---------------------------------------------------------
    # CATEGORY
    # ---------------------------------------------------------

    with col_upload_1:

        upload_category = st.selectbox(

            "Phân loại dòng hàng khi lưu kho:",

            CATEGORY_OPTIONS,

            key="sb_upload"

        )


        uploaded_files = st.file_uploader(

            "Chọn nhiều ảnh sản phẩm:",

            type=[
                "png",
                "jpg",
                "jpeg"
            ],

            accept_multiple_files=True,

            key="fu_bulk"

        )


    # ---------------------------------------------------------
    # BULK PREVIEW
    # ---------------------------------------------------------

    if uploaded_files:

        with col_upload_2:

            st.write(
                f"📂 Đã chọn "
                f"**{len(uploaded_files)}** file."
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


                total_files = len(
                    uploaded_files
                )


                # =================================================
                # PROCESS FILES
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
                        f"{index + 1}/{total_files}: "
                        f"{product_code}"

                    )


                    try:

                        # -----------------------------------------
                        # READ FILE
                        # -----------------------------------------

                        raw_bytes = (
                            file.getvalue()
                        )


                        if not raw_bytes:

                            raise Exception(
                                "File rỗng."
                            )


                        # -----------------------------------------
                        # IMAGE
                        # -----------------------------------------

                        image = (
                            normalize_image(
                                raw_bytes
                            )
                        )


                        # -----------------------------------------
                        # CLIP
                        # -----------------------------------------

                        status.text(

                            f"🤖 CLIP đang xử lý "
                            f"{product_code}..."

                        )


                        embedding = (
                            get_clip_image_embedding(
                                image
                            )
                        )


                        # -----------------------------------------
                        # CHECK 512
                        # -----------------------------------------

                        if len(
                            embedding
                        ) != 512:

                            raise Exception(
                                "CLIP vector "
                                f"không phải 512D: "
                                f"{len(embedding)}"
                            )


                        # -----------------------------------------
                        # STORAGE
                        # -----------------------------------------

                        status.text(

                            f"☁️ Đang upload ảnh "
                            f"{product_code}..."

                        )


                        image_url = (
                            upload_image_to_storage(

                                raw_bytes,

                                file.name

                            )
                        )


                        # -----------------------------------------
                        # DATABASE
                        # -----------------------------------------

                        status.text(

                            f"💾 Đang lưu database "
                            f"{product_code}..."

                        )


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


                    # -----------------------------------------
                    # PROGRESS
                    # -----------------------------------------

                    progress.progress(

                        int(

                            (

                                index + 1

                            )

                            /

                            total_files

                            *

                            100

                        )

                    )


                # =================================================
                # COMPLETE
                # =================================================

                status.empty()


                if success_count > 0:

                    st.success(

                        "🎉 HOÀN THÀNH!\n\n"

                        f"✅ Thành công: "
                        f"{success_count}\n\n"

                        f"❌ Lỗi: "
                        f"{failed_count}"

                    )

                else:

                    st.error(
                        "❌ Không có file nào "
                        "được lưu thành công."
                    )


                # =================================================
                # FAILED FILES
                # =================================================

                if failed_items:

                    with st.expander(
                        "🔎 Chi tiết file lỗi"
                    ):

                        for item in failed_items:

                            st.error(

                                f"📄 File: "
                                f"{item['file']}\n\n"

                                f"🏷️ Mã: "
                                f"{item['product_code']}\n\n"

                                f"❌ Lỗi: "
                                f"{item['error']}"

                            )


# =====================================================================
# 27. END
# =====================================================================
