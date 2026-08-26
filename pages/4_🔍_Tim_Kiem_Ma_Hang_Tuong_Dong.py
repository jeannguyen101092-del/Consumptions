# =====================================================================
# 🔍 PRODUCT IMAGE SEARCH & AUTO CATEGORY STORAGE
# VERSION V2.5
#
# MASTER LOCAL CLIP IMAGE EMBEDDING + ZERO-SHOT CATEGORY ENGINE
#
# MODEL:
# openai/clip-vit-base-patch32
#
# IMAGE VECTOR:
# 512D
#
# CATEGORY:
# AI tự nhận diện bằng CLIP ZERO-SHOT
#
# FLOW:
#
# IMAGE
#   ↓
# PIL RGB
#   ↓
# CLIP IMAGE ENCODER
#   ↓
# 512D IMAGE VECTOR
#
# IMAGE
#   ↓
# CLIP TEXT ENCODER
#   ↓
# CATEGORY VECTORS
#   ↓
# COSINE SIMILARITY
#   ↓
# AI CATEGORY + CONFIDENCE
#
#   ↓
# SUPABASE STORAGE
#   ↓
# products
#
# ❌ KHÔNG dùng Hugging Face Inference API
# ❌ KHÔNG cần HF_TOKEN
# ❌ KHÔNG hard-code Supabase key
#
# 🔐 SUPABASE:
# Đọc từ Streamlit Secrets / Tomy
# =====================================================================


# =====================================================================
# 1. STREAMLIT
# =====================================================================

import streamlit as st


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

    st.write("Package còn thiếu:")

    for package in MISSING_PACKAGES:
        st.code(package)

    st.warning(
        "Hãy thêm các package trên vào "
        "requirements.txt rồi Reboot / "
        "Clear cache & reboot."
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

    # ---------------------------------------------------------
    # DIRECT SECRETS
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
    # GROUP SECRETS
    # ---------------------------------------------------------

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
# 5. SUPABASE CONFIG
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
# 6. SECRET VALIDATION
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

    st.write(
        "Hãy kiểm tra:"
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
# 9. CATEGORY MASTER
# =====================================================================
#
# AI sẽ phân loại ảnh vào một trong các nhóm này.
#
# Có thể thêm category mới ở đây mà không cần sửa database.
# =====================================================================

CATEGORY_CONFIG = {

    "Quần dài": [
        "long pants",
        "trousers",
        "full length pants",
        "long leg pants",
        "straight leg pants"
    ],

    "Quần short": [
        "shorts",
        "short pants",
        "short trousers"
    ],

    "Quần jean": [
        "jeans",
        "denim jeans",
        "denim pants",
        "denim trousers"
    ],

    "Quần jogger": [
        "jogger pants",
        "joggers",
        "jogger trousers",
        "sports jogger pants"
    ],

    "Quần túi hộp": [
        "cargo pants",
        "cargo trousers",
        "utility cargo pants",
        "multi pocket pants"
    ],

    "Áo": [
        "shirt",
        "top",
        "casual shirt",
        "woven shirt",
        "fashion top"
    ],

    "T-shirt": [
        "t-shirt",
        "tee shirt",
        "short sleeve t-shirt",
        "cotton t-shirt"
    ],

    "Polo": [
        "polo shirt",
        "polo top",
        "polo t-shirt"
    ],

    "Hoodie": [
        "hoodie",
        "hooded sweatshirt",
        "hooded top"
    ],

    "Jacket": [
        "jacket",
        "fashion jacket",
        "casual jacket",
        "outerwear jacket"
    ],

    "Skirt": [
        "skirt",
        "women's skirt",
        "fashion skirt"
    ],

    "Dress": [
        "dress",
        "women's dress",
        "fashion dress"
    ]

}


CATEGORY_OPTIONS = list(
    CATEGORY_CONFIG.keys()
)


# =====================================================================
# 10. AI CATEGORY PROMPTS
# =====================================================================
#
# Dùng prompt đầy đủ để CLIP hiểu đây là ảnh sản phẩm may mặc.
# =====================================================================

CATEGORY_PROMPTS = {

    category: [
        (
            "a garment product photo of "
            + prompt
        )

        for prompt in prompts
    ]

    for category, prompts
    in CATEGORY_CONFIG.items()

}


# =====================================================================
# 11. DEVICE
# =====================================================================

if torch.cuda.is_available():

    DEVICE = torch.device("cuda")

    DEVICE_NAME = "CUDA GPU"

else:

    DEVICE = torch.device("cpu")

    DEVICE_NAME = "CPU"


# =====================================================================
# 12. LOAD CLIP
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
# 13. LOAD MODEL
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
# 14. IMAGE NORMALIZE
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
# 15. IMAGE HASH
# =====================================================================

def get_image_hash(image_bytes):

    return hashlib.sha256(
        image_bytes
    ).hexdigest()


# =====================================================================
# 16. NORMALIZE VECTOR
# =====================================================================

def normalize_embedding(
    embedding
):

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


    if len(values) != CLIP_DIMENSION:

        raise Exception(
            f"Vector dimension = "
            f"{len(values)}, "
            f"expected = "
            f"{CLIP_DIMENSION}"
        )


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


    return [
        x / norm
        for x in values
    ]


# =====================================================================
# 17. IMAGE EMBEDDING
# =====================================================================
#
# FIX tương thích transformers mới:
#
# vision_model()
#      ↓
# pooler_output
#      ↓
# visual_projection
#      ↓
# 512D
# =====================================================================

def get_clip_image_embedding(
    image
):

    try:

        inputs = clip_processor(
            images=image,
            return_tensors="pt"
        )


        pixel_values = (
            inputs["pixel_values"]
            .to(DEVICE)
        )


        with torch.inference_mode():

            vision_outputs = (
                clip_model.vision_model(
                    pixel_values=pixel_values
                )
            )


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
                "Không lấy được pooler_output."
            )


        if not isinstance(
            pooled_output,
            torch.Tensor
        ):

            raise Exception(
                "pooler_output không phải Tensor."
            )


        with torch.inference_mode():

            image_features = (
                clip_model.visual_projection(
                    pooled_output
                )
            )


        image_features = (
            image_features
            .detach()
            .float()
            .cpu()
            .flatten()
        )


        if image_features.numel() != 512:

            raise Exception(
                "Image embedding không phải "
                f"512D: "
                f"{image_features.numel()}"
            )


        norm = torch.linalg.vector_norm(
            image_features
        )


        if norm.item() <= 0:

            raise Exception(
                "Image embedding norm = 0."
            )


        image_features = (
            image_features / norm
        )


        embedding = (
            image_features.tolist()
        )


        if len(embedding) != 512:

            raise Exception(
                f"Embedding cuối cùng = "
                f"{len(embedding)}D"
            )


        return embedding


    except Exception as e:

        raise Exception(
            f"CLIP image embedding lỗi: {e}"
        )


# =====================================================================
# 18. TEXT EMBEDDING
# =====================================================================
#
# Không dùng get_text_features() trực tiếp để tránh vấn đề
# BaseModelOutputWithPooling tương tự image encoder.
#
# Flow:
#
# text_model
#    ↓
# pooler_output
#    ↓
# text_projection
#    ↓
# 512D
# =====================================================================

def get_clip_text_embedding(
    text
):

    try:

        inputs = clip_processor(
            text=[text],
            return_tensors="pt",
            padding=True,
            truncation=True
        )


        input_ids = (
            inputs["input_ids"]
            .to(DEVICE)
        )


        attention_mask = None


        if "attention_mask" in inputs:

            attention_mask = (
                inputs["attention_mask"]
                .to(DEVICE)
            )


        with torch.inference_mode():

            if attention_mask is not None:

                text_outputs = (
                    clip_model.text_model(
                        input_ids=input_ids,
                        attention_mask=attention_mask
                    )
                )

            else:

                text_outputs = (
                    clip_model.text_model(
                        input_ids=input_ids
                    )
                )


        if hasattr(
            text_outputs,
            "pooler_output"
        ):

            pooled_output = (
                text_outputs.pooler_output
            )

        elif isinstance(
            text_outputs,
            tuple
        ):

            pooled_output = (
                text_outputs[1]
            )

        else:

            raise Exception(
                "Không lấy được text pooler_output."
            )


        with torch.inference_mode():

            text_features = (
                clip_model.text_projection(
                    pooled_output
                )
            )


        text_features = (
            text_features
            .detach()
            .float()
            .cpu()
            .flatten()
        )


        if text_features.numel() != 512:

            raise Exception(
                "Text embedding không phải "
                f"512D: "
                f"{text_features.numel()}"
            )


        norm = torch.linalg.vector_norm(
            text_features
        )


        if norm.item() <= 0:

            raise Exception(
                "Text embedding norm = 0."
            )


        text_features = (
            text_features / norm
        )


        return text_features.tolist()


    except Exception as e:

        raise Exception(
            f"CLIP text embedding lỗi: {e}"
        )


# =====================================================================
# 19. PRE-COMPUTE CATEGORY TEXT EMBEDDINGS
# =====================================================================
#
# Tạo vector category một lần.
#
# Không cần chạy lại cho từng ảnh.
# =====================================================================

@st.cache_resource(
    show_spinner="🧠 Đang xây dựng AI Category Engine..."
)
def build_category_embeddings():

    category_vectors = {}


    for category, prompts in CATEGORY_PROMPTS.items():

        prompt_vectors = []


        for prompt in prompts:

            vector = get_clip_text_embedding(
                prompt
            )

            prompt_vectors.append(
                vector
            )


        # ---------------------------------------------------------
        # AVERAGE PROMPTS
        # ---------------------------------------------------------

        tensor_vectors = torch.tensor(
            prompt_vectors,
            dtype=torch.float32
        )


        category_vector = (
            tensor_vectors.mean(
                dim=0
            )
        )


        # ---------------------------------------------------------
        # NORMALIZE CATEGORY VECTOR
        # ---------------------------------------------------------

        category_vector = (
            category_vector
            /
            torch.linalg.vector_norm(
                category_vector
            )
        )


        category_vectors[
            category
        ] = category_vector


    return category_vectors


# =====================================================================
# 20. BUILD CATEGORY ENGINE
# =====================================================================

try:

    CATEGORY_VECTORS = (
        build_category_embeddings()
    )

except Exception as e:

    st.error(
        "❌ Không thể xây dựng "
        "AI Category Engine."
    )

    st.exception(e)

    st.stop()


# =====================================================================
# 21. AUTO CATEGORY CLASSIFICATION
# =====================================================================
#
# INPUT:
# image embedding 512D
#
# OUTPUT:
# category
# confidence
# all scores
# =====================================================================

def classify_product_category(
    image_embedding
):

    try:

        image_vector = torch.tensor(
            image_embedding,
            dtype=torch.float32
        )


        image_vector = (
            image_vector
            /
            torch.linalg.vector_norm(
                image_vector
            )
        )


        results = []


        for category, category_vector in (
            CATEGORY_VECTORS.items()
        ):

            similarity = torch.dot(
                image_vector,
                category_vector
            ).item()


            results.append(

                {

                    "category":
                        category,

                    "similarity":
                        similarity

                }

            )


        # ---------------------------------------------------------
        # SORT
        # ---------------------------------------------------------

        results.sort(
            key=lambda x:
                x["similarity"],
            reverse=True
        )


        best = results[0]


        # ---------------------------------------------------------
        # CONVERT SIMILARITY TO DISPLAY
        #
        # CLIP cosine có thể âm/dương.
        # Không gọi đây là xác suất tuyệt đối.
        # ---------------------------------------------------------

        raw_score = (
            best["similarity"]
        )


        # ---------------------------------------------------------
        # DISPLAY CONFIDENCE
        #
        # Đây là confidence tương đối để người dùng dễ đọc,
        # không phải probability thống kê.
        # ---------------------------------------------------------

        confidence = max(
            0.0,
            min(
                100.0,
                (
                    raw_score + 1.0
                )
                /
                2.0
                *
                100.0
            )
        )


        # ---------------------------------------------------------
        # MARGIN
        # ---------------------------------------------------------

        if len(results) >= 2:

            margin = (
                results[0]["similarity"]
                -
                results[1]["similarity"]
            )

        else:

            margin = 1.0


        return {

            "category":
                best["category"],

            "similarity":
                raw_score,

            "confidence":
                confidence,

            "margin":
                margin,

            "ranking":
                results

        }


    except Exception as e:

        raise Exception(
            f"AI category lỗi: {e}"
        )


# =====================================================================
# 22. IMAGE HASH
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
# 23. FILENAME
# =====================================================================

def sanitize_filename(
    filename
):

    filename = filename.strip()

    return re.sub(
        r"[^A-Za-z0-9._-]",
        "_",
        filename
    )


# =====================================================================
# 24. PRODUCT CODE
# =====================================================================

def extract_product_code(
    filename
):

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
# 25. CONTENT TYPE
# =====================================================================

def get_content_type(
    filename
):

    ext = (
        filename
        .lower()
        .rsplit(".", 1)[-1]
    )


    if ext == "png":

        return "image/png"


    if ext in [
        "jpg",
        "jpeg"
    ]:

        return "image/jpeg"


    return "application/octet-stream"


# =====================================================================
# 26. STORAGE
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

        error_text = str(e).lower()

        if (
            "already exists"
            not in error_text
            and
            "duplicate"
            not in error_text
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
# 27. SAVE PRODUCT
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
# 28. DISPLAY AI RESULT
# =====================================================================

def display_ai_category_result(
    classification
):

    category = (
        classification["category"]
    )

    confidence = (
        classification["confidence"]
    )

    similarity = (
        classification["similarity"]
    )

    margin = (
        classification["margin"]
    )

    ranking = (
        classification["ranking"]
    )


    # ---------------------------------------------------------
    # CATEGORY
    # ---------------------------------------------------------

    st.success(
        f"🤖 AI nhận diện: **{category}**"
    )


    col1, col2, col3 = st.columns(3)


    with col1:

        st.metric(
            "AI Category",
            category
        )


    with col2:

        st.metric(
            "Similarity",
            f"{similarity * 100:.2f}%"
        )


    with col3:

        st.metric(
            "AI Confidence",
            f"{confidence:.1f}%"
        )


    # ---------------------------------------------------------
    # MARGIN
    # ---------------------------------------------------------

    st.caption(
        f"Category separation margin: "
        f"{margin * 100:.2f}%"
    )


    # ---------------------------------------------------------
    # TOP RESULTS
    # ---------------------------------------------------------

    with st.expander(
        "🔎 Xem AI phân tích các chủng loại"
    ):

        for index, item in enumerate(
            ranking[:6]
        ):

            score = (
                item["similarity"]
            )

            st.write(
                f"{index + 1}. "
                f"**{item['category']}**"
                f" — "
                f"{score * 100:.2f}%"
            )


# =====================================================================
# 29. TABS
# =====================================================================

tab1, tab2 = st.tabs(

    [

        "🔍 TÌM KIẾM MÃ HÀNG TƯƠNG ĐỒNG",

        "📦 LƯU KHO TỰ ĐỘNG BẰNG AI"

    ]

)


# =====================================================================
# TAB 1 - AI AUTO SEARCH
# VERSION V2.6
#
# 🔒 CATEGORY LOCK SEARCH
#
# FLOW:
#
# ẢNH SKETCH
#     ↓
# CLIP IMAGE EMBEDDING 512D
#     ↓
# AI NHẬN DIỆN CHỦNG LOẠI
#     ↓
# CATEGORY LOCK
#     ↓
# SUPABASE RPC
#     ↓
# CHỈ SEARCH ĐÚNG CATEGORY
#
# ❌ KHÔNG CHO USER CHỌN CATEGORY
# ❌ KHÔNG SEARCH TOÀN BỘ KHO
# ❌ KHÔNG ĐỂ QUẦN LỌT VÀO KẾT QUẢ ÁO
#
# =====================================================================

with tab1:

    st.header(
        "🔍 AI TỰ NHẬN DIỆN & TÌM MÃ HÀNG TƯƠNG ĐỒNG"
    )

    st.info(
        "🤖 AI sẽ tự nhận diện chủng loại từ ảnh "
        "→ khóa đúng nhóm hàng → chỉ tìm mã tương đồng "
        "trong đúng nhóm đó."
    )

    st.caption(
        f"CLIP: {CLIP_MODEL_NAME} | "
        f"Vector: 512D | "
        f"Device: {DEVICE_NAME}"
    )


    # =================================================================
    # 1. UPLOAD IMAGE
    # =================================================================

    uploaded_sketch = st.file_uploader(

        "📂 Tải lên ảnh Sketch / ảnh mẫu cần tìm:",

        type=[
            "png",
            "jpg",
            "jpeg"
        ],

        key="fu_search_v26"

    )


    # =================================================================
    # 2. IMAGE PREVIEW
    # =================================================================

    if uploaded_sketch is not None:

        col_img, col_ai = st.columns(
            [1, 2]
        )


        # =============================================================
        # IMAGE
        # =============================================================

        with col_img:

            st.image(

                uploaded_sketch,

                caption="Ảnh cần tìm",

                use_container_width=True

            )


        # =============================================================
        # BUTTON
        # =============================================================

        with col_ai:

            st.write(
                "### 🤖 AI SEARCH"
            )

            st.write(
                "AI sẽ tự quyết định chủng loại. "
                "Không cần chọn thủ công."
            )


            if st.button(

                "🚀 AI NHẬN DIỆN & TÌM MÃ",

                type="primary",

                key="btn_ai_search_v26"

            ):

                try:

                    # =================================================
                    # STEP 1
                    # READ IMAGE
                    # =================================================

                    raw_bytes = (
                        uploaded_sketch.getvalue()
                    )


                    if not raw_bytes:

                        raise Exception(
                            "File ảnh rỗng."
                        )


                    # =================================================
                    # STEP 2
                    # IMAGE EMBEDDING
                    # =================================================

                    with st.spinner(
                        "🤖 CLIP đang phân tích hình ảnh..."
                    ):

                        image_hash = (
                            get_image_hash(
                                raw_bytes
                            )
                        )


                        query_embedding = (
                            get_cached_clip_embedding(

                                image_hash,

                                raw_bytes

                            )
                        )


                    # =================================================
                    # VALIDATE VECTOR
                    # =================================================

                    if not query_embedding:

                        raise Exception(
                            "Không tạo được image embedding."
                        )


                    if len(
                        query_embedding
                    ) != 512:

                        raise Exception(

                            "CLIP embedding phải "
                            f"512D nhưng nhận được "
                            f"{len(query_embedding)}D."

                        )


                    # =================================================
                    # STEP 3
                    # AI CATEGORY
                    # =================================================

                    with st.spinner(
                        "🧠 AI đang nhận diện chủng loại..."
                    ):

                        classification = (
                            classify_product_category(
                                query_embedding
                            )
                        )


                    ai_category = str(

                        classification.get(
                            "category",
                            ""
                        )

                    ).strip()


                    ai_confidence = float(

                        classification.get(
                            "confidence",
                            0
                        )

                    )


                    ai_similarity = float(

                        classification.get(
                            "similarity",
                            0
                        )

                    )


                    ai_margin = float(

                        classification.get(
                            "margin",
                            0
                        )

                    )


                    # =================================================
                    # CATEGORY VALIDATION
                    # =================================================

                    if not ai_category:

                        raise Exception(
                            "AI không xác định được category."
                        )


                    if ai_category not in CATEGORY_OPTIONS:

                        raise Exception(

                            f"AI trả về category "
                            f"không hợp lệ: "
                            f"{ai_category}"

                        )


                    # =================================================
                    # STEP 4
                    # CATEGORY LOCK
                    # =================================================

                    st.divider()

                    st.subheader(
                        "🤖 AI CATEGORY LOCK"
                    )


                    lock_col1, lock_col2, lock_col3 = (
                        st.columns(3)
                    )


                    with lock_col1:

                        st.metric(

                            "AI nhận diện",

                            ai_category

                        )


                    with lock_col2:

                        st.metric(

                            "Similarity",

                            f"{ai_similarity * 100:.2f}%"

                        )


                    with lock_col3:

                        st.metric(

                            "Confidence",

                            f"{ai_confidence:.1f}%"

                        )


                    st.success(

                        f"🔒 CATEGORY ĐÃ KHÓA: "
                        f"**{ai_category}**"

                    )


                    st.caption(

                        f"Category margin: "
                        f"{ai_margin * 100:.2f}%"

                    )


                    # =================================================
                    # STEP 5
                    # SHOW TOP CATEGORY ANALYSIS
                    # =================================================

                    with st.expander(
                        "🔎 Xem AI phân tích category"
                    ):

                        ranking = (
                            classification.get(
                                "ranking",
                                []
                            )
                        )


                        for rank_index, item in enumerate(
                            ranking[:6]
                        ):

                            category_name = str(

                                item.get(
                                    "category",
                                    ""
                                )

                            )


                            score = float(

                                item.get(
                                    "similarity",
                                    0
                                )

                            )


                            if category_name == ai_category:

                                st.success(

                                    f"{rank_index + 1}. "
                                    f"**{category_name}** "
                                    f"— "
                                    f"{score * 100:.2f}%"

                                )

                            else:

                                st.write(

                                    f"{rank_index + 1}. "
                                    f"{category_name} "
                                    f"— "
                                    f"{score * 100:.2f}%"

                                )


                    # =================================================
                    # STEP 6
                    # SEARCH ONLY LOCKED CATEGORY
                    # =================================================
                    #
                    # 🔒 QUAN TRỌNG:
                    #
                    # filter_category = ai_category
                    #
                    # KHÔNG dùng None
                    # KHÔNG search toàn bộ products
                    #
                    # =================================================

                    with st.spinner(

                        f"🔎 Đang tìm mã "
                        f"{ai_category} "
                        f"trong kho..."

                    ):

                        response = (

                            supabase

                            .rpc(

                                "match_products_v2",

                                {

                                    "query_embedding":
                                        query_embedding,

                                    "match_threshold":
                                        0.30,

                                    "match_count":
                                        12,

                                    # =================================
                                    # 🔒 CATEGORY LOCK
                                    # =================================

                                    "filter_category":
                                        ai_category

                                }

                            )

                            .execute()

                        )


                    # =================================================
                    # STEP 7
                    # GET RESULTS
                    # =================================================

                    data = (
                        response.data
                        or []
                    )


                    # =================================================
                    # STEP 8
                    # HARD CATEGORY FILTER
                    # =================================================
                    #
                    # Ngoài filter SQL,
                    # Python tiếp tục khóa category.
                    #
                    # Đây là lớp bảo vệ thứ 2.
                    #
                    # =================================================

                    locked_results = []


                    ai_category_normalized = (

                        ai_category
                        .strip()
                        .lower()

                    )


                    for item in data:

                        item_category = str(

                            item.get(
                                "category",
                                ""
                            )

                        ).strip().lower()


                        if (

                            item_category
                            ==
                            ai_category_normalized

                        ):

                            locked_results.append(
                                item
                            )


                    # =================================================
                    # STEP 9
                    # SORT BY SIMILARITY
                    # =================================================

                    locked_results.sort(

                        key=lambda x: float(

                            x.get(
                                "similarity",
                                0
                            )

                        ),

                        reverse=True

                    )


                    # =================================================
                    # STEP 10
                    # DISPLAY RESULT
                    # =================================================

                    st.divider()

                    st.subheader(

                        "🎯 KẾT QUẢ TÌM KIẾM"

                    )


                    if locked_results:

                        st.success(

                            f"Đã tìm thấy "
                            f"**{len(locked_results)}** "
                            f"mã thuộc nhóm "
                            f"**{ai_category}**."

                        )


                        st.caption(

                            "🔒 Tất cả kết quả bên dưới "
                            "đã được khóa theo category AI. "
                            "Các category khác bị loại."

                        )


                        # =================================================
                        # DISPLAY 4 COLUMNS
                        # =================================================

                        display_count = min(

                            len(
                                locked_results
                            ),

                            12

                        )


                        cols = st.columns(4)


                        for idx in range(
                            display_count
                        ):

                            item = (
                                locked_results[idx]
                            )


                            with cols[
                                idx % 4
                            ]:

                                st.markdown(
                                    "---"
                                )


                                # -----------------------------------------
                                # PRODUCT CODE
                                # -----------------------------------------

                                product_code = str(

                                    item.get(
                                        "product_code",
                                        "N/A"
                                    )

                                )


                                st.subheader(
                                    product_code
                                )


                                # -----------------------------------------
                                # IMAGE
                                # -----------------------------------------

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

                                    st.caption(
                                        "Không có ảnh."
                                    )


                                # -----------------------------------------
                                # CATEGORY
                                # -----------------------------------------

                                result_category = str(

                                    item.get(
                                        "category",
                                        ""
                                    )

                                )


                                st.success(

                                    f"🏷️ "
                                    f"{result_category}"

                                )


                                # -----------------------------------------
                                # SIMILARITY
                                # -----------------------------------------

                                result_similarity = float(

                                    item.get(
                                        "similarity",
                                        0
                                    )

                                )


                                st.metric(

                                    "Độ tương đồng",

                                    f"{result_similarity * 100:.2f}%"

                                )


                    else:

                        # =================================================
                        # NO RESULT
                        # =================================================

                        st.warning(

                            f"⚠️ Không tìm thấy mã "
                            f"**{ai_category}** "
                            "đủ tương đồng trong kho."

                        )


                        st.info(

                            "💡 AI đã khóa đúng chủng loại "
                            f"**{ai_category}**, "
                            "nhưng database hiện chưa có "
                            "mẫu đủ giống trong nhóm này."

                        )


                        # =================================================
                        # DEBUG CATEGORY
                        # =================================================

                        with st.expander(
                            "🔧 Thông tin AI"
                        ):

                            st.write(
                                "AI Category:",
                                ai_category
                            )

                            st.write(
                                "Confidence:",
                                f"{ai_confidence:.2f}%"
                            )

                            st.write(
                                "Similarity:",
                                f"{ai_similarity:.4f}"
                            )

                            st.write(
                                "Vector dimension:",
                                len(
                                    query_embedding
                                )
                            )


                except Exception as e:

                    st.error(
                        "❌ AI SEARCH LỖI"
                    )

                    st.exception(e)

# =====================================================================
# 31. TAB 2 - AI AUTO CLASSIFICATION + BULK UPLOAD
# =====================================================================

with tab2:

    st.header(
        "📦 Lưu Kho Hàng Loạt — AI Tự Nhận Diện"
    )


    st.info(
        "🤖 Không cần chọn chủng loại. "
        "AI sẽ tự phân loại từng ảnh trước khi lưu."
    )


    st.caption(
        "Ví dụ: "
        "`R09-490416.JPG` → "
        "AI nhận diện → Quần jean → "
        "lưu Supabase."
    )


    uploaded_files = st.file_uploader(

        "📂 Chọn nhiều ảnh sản phẩm:",

        type=[
            "png",
            "jpg",
            "jpeg"
        ],

        accept_multiple_files=True,

        key="fu_bulk_v25"

    )


    # ================================================================
    # FILE SELECTED
    # ================================================================

    if uploaded_files:

        st.write(
            f"📂 Đã chọn "
            f"**{len(uploaded_files)}** ảnh."
        )


        if st.button(

            "🤖 PHÂN LOẠI AI & TỰ ĐỘNG LƯU",

            type="primary",

            key="btn_bulk_v25"

        ):

            progress = st.progress(0)

            status = st.empty()


            success_count = 0

            failed_count = 0

            failed_items = []


            results_table = []


            total_files = len(
                uploaded_files
            )


            # ========================================================
            # PROCESS EACH IMAGE
            # ========================================================

            for index, file in enumerate(
                uploaded_files
            ):

                product_code = (
                    extract_product_code(
                        file.name
                    )
                )


                try:

                    # ------------------------------------------------
                    # STATUS
                    # ------------------------------------------------

                    status.text(

                        f"⏳ "
                        f"{index + 1}/"
                        f"{total_files} — "
                        f"{product_code}"

                    )


                    # ------------------------------------------------
                    # READ IMAGE
                    # ------------------------------------------------

                    raw_bytes = (
                        file.getvalue()
                    )


                    if not raw_bytes:

                        raise Exception(
                            "File rỗng."
                        )


                    image = (
                        normalize_image(
                            raw_bytes
                        )
                    )


                    # ------------------------------------------------
                    # IMAGE EMBEDDING
                    # ------------------------------------------------

                    status.text(

                        f"🤖 CLIP đang phân tích "
                        f"{product_code}..."

                    )


                    image_hash = (
                        get_image_hash(
                            raw_bytes
                        )
                    )


                    embedding = (
                        get_cached_clip_embedding(

                            image_hash,

                            raw_bytes

                        )
                    )


                    if len(
                        embedding
                    ) != 512:

                        raise Exception(
                            "Image vector "
                            "không phải 512D."
                        )


                    # ------------------------------------------------
                    # AI CATEGORY
                    # ------------------------------------------------

                    status.text(

                        f"🧠 AI đang nhận diện "
                        f"chủng loại "
                        f"{product_code}..."

                    )


                    classification = (
                        classify_product_category(
                            embedding
                        )
                    )


                    ai_category = (
                        classification[
                            "category"
                        ]
                    )


                    ai_confidence = (
                        classification[
                            "confidence"
                        ]
                    )


                    ai_similarity = (
                        classification[
                            "similarity"
                        ]
                    )


                    # ------------------------------------------------
                    # STORAGE
                    # ------------------------------------------------

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


                    # ------------------------------------------------
                    # DATABASE
                    # ------------------------------------------------

                    status.text(

                        f"💾 Đang lưu "
                        f"{product_code} → "
                        f"{ai_category}"

                    )


                    save_product(

                        product_code=
                            product_code,

                        image_url=
                            image_url,

                        category=
                            ai_category,

                        embedding=
                            embedding

                    )


                    # ------------------------------------------------
                    # SUCCESS
                    # ------------------------------------------------

                    success_count += 1


                    results_table.append(

                        {

                            "Mã hàng":
                                product_code,

                            "AI nhận diện":
                                ai_category,

                            "Confidence":
                                f"{ai_confidence:.1f}%",

                            "Similarity":
                                f"{ai_similarity * 100:.2f}%",

                            "Trạng thái":
                                "✅ Đã lưu"

                        }

                    )


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


                    results_table.append(

                        {

                            "Mã hàng":
                                product_code,

                            "AI nhận diện":
                                "—",

                            "Confidence":
                                "—",

                            "Similarity":
                                "—",

                            "Trạng thái":
                                "❌ Lỗi"

                        }

                    )


                # ----------------------------------------------------
                # PROGRESS
                # ----------------------------------------------------

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


            # ========================================================
            # COMPLETE
            # ========================================================

            status.empty()


            st.divider()


            st.subheader(
                "📊 KẾT QUẢ AI"
            )


            # ========================================================
            # SUMMARY
            # ========================================================

            col1, col2, col3 = st.columns(3)


            with col1:

                st.metric(
                    "Tổng ảnh",
                    total_files
                )


            with col2:

                st.metric(
                    "AI + lưu thành công",
                    success_count
                )


            with col3:

                st.metric(
                    "Lỗi",
                    failed_count
                )


            # ========================================================
            # RESULT TABLE
            # ========================================================

            if results_table:

                import pandas as pd

                df_result = pd.DataFrame(
                    results_table
                )


                st.dataframe(

                    df_result,

                    use_container_width=True,

                    hide_index=True

                )


            # ========================================================
            # FAILED DETAILS
            # ========================================================

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


            # ========================================================
            # SUCCESS
            # ========================================================

            if success_count > 0:

                st.success(

                    f"🎉 Hoàn thành! "
                    f"AI đã tự nhận diện và "
                    f"lưu thành công "
                    f"{success_count}/"
                    f"{total_files} mã hàng."

                )


            if failed_count > 0:

                st.warning(

                    f"⚠️ Có "
                    f"{failed_count} "
                    "file chưa lưu được."

                )


# =====================================================================
# END V2.5
# =====================================================================
