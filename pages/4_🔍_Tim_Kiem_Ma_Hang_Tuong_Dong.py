# =====================================================================
# 🔍 PRODUCT IMAGE SEARCH & BULK STORAGE
# VERSION V2.4.2
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
        "Package còn thiếu:"
    )

    for package in MISSING_PACKAGES:
        st.code(package)

    st.warning(
        "Hãy thêm package vào requirements.txt "
        "sau đó Reboot / Clear cache & reboot."
    )

    st.code(
        """streamlit
supabase
pillow
numpy
torch
transformers
safetensors""",
        language="text"
    )

    st.stop()


# =====================================================================
# 4. SUPABASE SECRET READER
# =====================================================================

def get_secret_value(names):

    for name in names:

        try:

            value = st.secrets.get(name)

            if value is not None:

                value = str(value).strip()

                if value:
                    return value

        except Exception:
            pass


    for group_name in [
        "supabase",
        "SUPABASE"
    ]:

        try:

            group = st.secrets.get(group_name)

            if group:

                for name in names:

                    try:

                        value = group.get(name)

                        if value is not None:

                            value = str(
                                value
                            ).strip()

                            if value:
                                return value

                    except Exception:
                        pass

        except Exception:
            pass


    return None


# =====================================================================
# 5. SUPABASE
# =====================================================================

SUPABASE_URL = get_secret_value(
    [
        "SUPABASE_URL",
        "SUPABASE_PROJECT_URL",
        "supabase_url",
        "supabase_project_url"
    ]
)


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
# 6. SECRET CHECK
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

    for item in missing_secrets:
        st.code(item)

    st.stop()


# =====================================================================
# 7. SUPABASE CONNECTION
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
# 8. CLIP CONFIG
# =====================================================================

CLIP_MODEL_NAME = (
    "openai/clip-vit-base-patch32"
)

CLIP_DIMENSION = 512


# =====================================================================
# 9. DEVICE
# =====================================================================

if torch.cuda.is_available():

    DEVICE = torch.device("cuda")

    DEVICE_NAME = "CUDA GPU"

else:

    DEVICE = torch.device("cpu")

    DEVICE_NAME = "CPU"


# =====================================================================
# 10. LOAD CLIP MODEL
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
# 11. LOAD MODEL
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
# 12. CATEGORY
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
# 13. IMAGE NORMALIZE
# =====================================================================

def normalize_image(file_bytes):

    try:

        image = Image.open(
            io.BytesIO(file_bytes)
        )

        try:

            image = ImageOps.exif_transpose(
                image
            )

        except Exception:
            pass


        if image.mode != "RGB":

            image = image.convert(
                "RGB"
            )


        return image


    except Exception as e:

        raise Exception(
            f"Không đọc được ảnh: {e}"
        )


# =====================================================================
# 14. IMAGE HASH
# =====================================================================

def get_image_hash(image_bytes):

    return hashlib.sha256(
        image_bytes
    ).hexdigest()


# =====================================================================
# 15. NORMALIZE VECTOR
# =====================================================================

def normalize_embedding(
    embedding
):

    # ---------------------------------------------------------
    # Chuyển Tensor → list
    # ---------------------------------------------------------

    if isinstance(
        embedding,
        torch.Tensor
    ):

        embedding = (
            embedding
            .detach()
            .float()
            .cpu()
            .flatten()
            .tolist()
        )


    values = [
        float(x)
        for x in embedding
    ]


    # ---------------------------------------------------------
    # CHECK
    # ---------------------------------------------------------

    if len(values) != CLIP_DIMENSION:

        raise Exception(
            f"Vector dimension = "
            f"{len(values)}, "
            f"expected = "
            f"{CLIP_DIMENSION}"
        )


    # ---------------------------------------------------------
    # L2
    # ---------------------------------------------------------

    norm = math.sqrt(
        sum(
            x * x
            for x in values
        )
    )


    if norm <= 0:

        raise Exception(
            "Vector norm = 0."
        )


    values = [
        x / norm
        for x in values
    ]


    return values


# =====================================================================
# 16. CLIP IMAGE EMBEDDING
# =====================================================================
#
# FIX V2.4.2
#
# Không sử dụng:
#
# image_features.ndim
#
# trước khi xác định object thực tế.
#
# Transformers version mới có thể trả:
#
# BaseModelOutputWithPooling
#
# thay vì Tensor.
#
# Vì vậy dùng:
#
# clip_model.vision_model(...)
#
# → pooler_output
#
# → visual_projection
#
# → 512D
#
# =====================================================================

def get_clip_image_embedding(image):

    try:

        # ---------------------------------------------------------
        # PROCESS
        # ---------------------------------------------------------

        inputs = clip_processor(
            images=image,
            return_tensors="pt"
        )


        # ---------------------------------------------------------
        # DEVICE
        # ---------------------------------------------------------

        pixel_values = (
            inputs["pixel_values"]
            .to(DEVICE)
        )


        # ---------------------------------------------------------
        # VISION ENCODER
        # ---------------------------------------------------------

        with torch.inference_mode():

            vision_outputs = (
                clip_model.vision_model(
                    pixel_values=pixel_values
                )
            )


        # ---------------------------------------------------------
        # GET POOLER OUTPUT
        # ---------------------------------------------------------

        if hasattr(
            vision_outputs,
            "pooler_output"
        ):

            pooled_output = (
                vision_outputs.pooler_output
            )

        elif isinstance(
            vision_outputs,
            tuple
        ):

            pooled_output = (
                vision_outputs[1]
            )

        else:

            raise Exception(
                "Không lấy được "
                "pooler_output từ CLIP vision encoder."
            )


        # ---------------------------------------------------------
        # CHECK TENSOR
        # ---------------------------------------------------------

        if not isinstance(
            pooled_output,
            torch.Tensor
        ):

            raise Exception(
                "pooler_output không phải Tensor."
            )


        # ---------------------------------------------------------
        # VISUAL PROJECTION
        # ---------------------------------------------------------
        #
        # CLIP vision hidden size:
        # 768
        #
        # Projection:
        # 768 → 512
        #
        # Đây là embedding chuẩn của CLIP.
        # ---------------------------------------------------------

        with torch.inference_mode():

            image_features = (
                clip_model.visual_projection(
                    pooled_output
                )
            )


        # ---------------------------------------------------------
        # FLATTEN
        # ---------------------------------------------------------

        image_features = (
            image_features
            .detach()
            .float()
            .cpu()
            .flatten()
        )


        # ---------------------------------------------------------
        # CHECK 512
        # ---------------------------------------------------------

        if image_features.numel() != 512:

            raise Exception(
                "CLIP image embedding "
                f"không phải 512D: "
                f"{image_features.numel()}"
            )


        # ---------------------------------------------------------
        # L2 NORMALIZATION
        # ---------------------------------------------------------

        norm = torch.linalg.vector_norm(
            image_features
        )


        if norm.item() <= 0:

            raise Exception(
                "CLIP embedding norm = 0."
            )


        image_features = (
            image_features / norm
        )


        # ---------------------------------------------------------
        # FINAL LIST
        # ---------------------------------------------------------

        embedding = (
            image_features
            .tolist()
        )


        # ---------------------------------------------------------
        # FINAL HARD CHECK
        # ---------------------------------------------------------

        if len(embedding) != 512:

            raise Exception(
                f"Embedding cuối cùng = "
                f"{len(embedding)}D"
            )


        return embedding


    except Exception as e:

        raise Exception(
            f"CLIP embedding lỗi: {e}"
        )


# =====================================================================
# 17. CACHE CLIP
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
# 18. FILENAME
# =====================================================================

def sanitize_filename(filename):

    filename = filename.strip()

    return re.sub(
        r"[^A-Za-z0-9._-]",
        "_",
        filename
    )


# =====================================================================
# 19. PRODUCT CODE
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
# 20. CONTENT TYPE
# =====================================================================

def get_content_type(filename):

    ext = (
        filename
        .lower()
        .rsplit(".", 1)[-1]
    )


    if ext == "png":
        return "image/png"


    if ext in ["jpg", "jpeg"]:
        return "image/jpeg"


    return "application/octet-stream"


# =====================================================================
# 21. STORAGE
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


    storage = (
        supabase
        .storage
        .from_(bucket_name)
    )


    try:

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


    except Exception as e:

        # ---------------------------------------------------------
        # Một số version supabase có thể báo duplicate.
        # Với upsert=true vẫn có thể khác behavior.
        # ---------------------------------------------------------

        error_text = str(e).lower()

        if (
            "already exists" not in error_text
            and
            "duplicate" not in error_text
        ):

            raise Exception(
                f"Storage upload lỗi: {e}"
            )


    try:

        public_url = (
            storage.get_public_url(
                safe_filename
            )
        )


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
            f"Không lấy được image URL: {e}"
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

    embedding = normalize_embedding(
        embedding
    )


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
# 23. TABS
# =====================================================================

tab1, tab2 = st.tabs(

    [

        "🔍 TÌM KIẾM MÃ HÀNG TƯƠNG ĐỒNG",

        "📦 LƯU KHO HÀNG LOẠT"

    ]

)


# =====================================================================
# 24. TAB 1 - SEARCH
# =====================================================================

with tab1:

    st.header(
        "🔍 Tìm Kiếm Mã Hàng Qua Ảnh Sketch"
    )


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


    if uploaded_sketch is not None:

        with col_search_2:

            st.image(
                uploaded_sketch,
                caption="Ảnh Sketch của bạn",
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

                        raw_bytes = (
                            uploaded_sketch
                            .getvalue()
                        )


                        if not raw_bytes:

                            raise Exception(
                                "Ảnh rỗng."
                            )


                        image_hash = (
                            get_image_hash(
                                raw_bytes
                            )
                        )


                        sketch_embedding = (
                            get_cached_clip_embedding(
                                image_hash,
                                raw_bytes
                            )
                        )


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
                            +
                            str(
                                len(
                                    sketch_embedding
                                )
                            )
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


                        if response.data:

                            st.success(
                                f"🎯 Tìm thấy "
                                f"{len(response.data)} "
                                "mã tương đồng."
                            )


                            cols = st.columns(
                                len(response.data)
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
# 25. TAB 2 - BULK UPLOAD
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


                for index, file in enumerate(
                    uploaded_files
                ):

                    product_code = (
                        extract_product_code(
                            file.name
                        )
                    )


                    try:

                        status.text(

                            f"⏳ Đang xử lý "
                            f"{index + 1}/"
                            f"{total_files}: "
                            f"{product_code}"

                        )


                        # -----------------------------------------
                        # READ
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
                        # 512 CHECK
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

                            f"☁️ Đang upload "
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

                            f"💾 Đang lưu "
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


                status.empty()


                if success_count:

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
# END
# =====================================================================
