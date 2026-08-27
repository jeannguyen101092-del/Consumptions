# =====================================================================
# 🔍 AI TÌM KIẾM MÃ HÀNG TƯƠNG ĐỒNG
# VERSION V4.0
#
# GEMINI VISION
#        ↓
# CATEGORY RECOGNITION
#
# CLIP IMAGE EMBEDDING LOCAL
#        ↓
# SUPABASE PGVECTOR
#        ↓
# SIMILARITY SEARCH
#
# IMPORTANT:
# CATEGORY KHÔNG PHẢI HARD FILTER KHI TÌM KIẾM
# =====================================================================

import streamlit as st
import os
import io
import re
import json
import base64
import hashlib
import numpy as np
import pandas as pd

from PIL import Image

# =====================================================================
# 1. PAGE CONFIG
# =====================================================================

st.set_page_config(
    page_title="AI Tìm Kiếm Mã Hàng Tương Đồng",
    page_icon="🔍",
    layout="wide"
)


# =====================================================================
# 2. CONSTANTS
# =====================================================================

APP_VERSION = "V4.0"

BUCKET_NAME = "product-images"

CLIP_MODEL_NAME = "openai/clip-vit-base-patch32"

# CLIP ViT-B/32 image embedding = 512 dimensions
CLIP_DIMENSION = 512

SIMILARITY_THRESHOLD = 0.20

DEFAULT_RESULT_COUNT = 12


# =====================================================================
# 3. CATEGORY MASTER
# =====================================================================

CATEGORY_OPTIONS = [
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
# 4. GARMENT AI PROMPT
# =====================================================================

GARMENT_PROMPT = r"""
You are a professional apparel technical product recognition AI.

Your job is to identify the actual garment construction from the
uploaded garment image or fashion sketch.

This is NOT generic image classification.

You must carefully distinguish:

1. ONE PIECE / JUMPSUIT
   - Upper body and lower body are physically connected.
   - Category = "Áo liền quần"

2. BIB OVERALL / DUNGAREE
   - Bib front
   - Shoulder straps
   - Separate lower garment structure
   - Category = "Quần yếm"

3. CARGO PANTS
   - MUST be a separate pants garment.
   - MUST have obvious cargo / patch pockets on the side legs.
   - Category = "Quần túi hộp"

4. JEANS
   - Separate pants.
   - Denim construction.
   - Category = "Quần jean"

5. JOGGER
   - Separate pants.
   - Jogger construction.
   - Usually elastic or rib cuffs.
   - Category = "Quần jogger"

6. SHORTS
   - Separate lower-body garment.
   - Short length.
   - Category = "Quần short"

7. NORMAL PANTS
   - Separate pants.
   - No clear cargo construction.
   - Not jeans.
   - Not jogger.
   - Category = "Quần dài"

8. JACKET
   - Separate outerwear upper-body garment.
   - Category = "Jacket"

9. DRESS
   - One-piece dress silhouette.
   - NOT a pants-based jumpsuit.
   - Category = "Dress"

10. SHIRT / TOP
    - Category = "Áo"

11. T-SHIRT
    - Category = "T-shirt"

12. POLO
    - Category = "Polo"

13. HOODIE
    - Category = "Hoodie"

14. SKIRT
    - Category = "Skirt"


CRITICAL RULES:

- Never classify a jumpsuit as cargo pants.
- Never classify bib overalls as cargo pants.
- Cargo requires visible cargo/patch pockets.
- One-piece construction has priority over lower-body appearance.
- Do not guess cargo merely because the pants look loose.
- Do not use color alone to classify denim.
- If the image is ambiguous, choose the closest structural category
  and reduce confidence.


Return ONLY valid JSON.

Use exactly this structure:

{
  "category": "Quần dài",
  "confidence": 95,
  "one_piece": false,
  "bib": false,
  "shoulder_straps": false,
  "cargo_pockets": false,
  "denim": false,
  "jogger_cuffs": false,
  "sleeve": "long",
  "collar": "none",
  "hood": false,
  "silhouette": "straight",
  "length": "full",
  "reason": "..."
}
"""


# =====================================================================
# 5. READ STREAMLIT SECRETS
# =====================================================================

def get_secret(name):

    """
    Đọc key từ st.secrets.

    Không bao giờ ghi key trực tiếp vào GitHub.
    """

    try:

        value = st.secrets.get(name)

        if value is not None:
            value = str(value).strip()

            if value:
                return value

    except Exception:
        pass

    # fallback cho local environment
    value = os.getenv(name)

    if value:
        return value.strip()

    return None


SUPABASE_URL = get_secret("SUPABASE_URL")
SUPABASE_KEY = get_secret("SUPABASE_KEY")
GEMINI_API_KEY = get_secret("GEMINI_API_KEY")


# =====================================================================
# 6. CHECK SECRETS
# =====================================================================

missing_keys = []

if not SUPABASE_URL:
    missing_keys.append("SUPABASE_URL")

if not SUPABASE_KEY:
    missing_keys.append("SUPABASE_KEY")

if not GEMINI_API_KEY:
    missing_keys.append("GEMINI_API_KEY")


if missing_keys:

    st.error(
        "❌ Không đọc được thông tin bảo mật từ Streamlit Secrets."
    )

    st.warning(
        "Hãy kiểm tra các key sau:"
    )

    for key in missing_keys:
        st.code(key)

    st.stop()


# =====================================================================
# 7. IMPORT SUPABASE
# =====================================================================

try:

    from supabase import create_client, Client

except Exception as e:

    st.error(
        "❌ Chưa cài thư viện supabase."
    )

    st.code(
        "pip install supabase"
    )

    st.exception(e)

    st.stop()


# =====================================================================
# 8. SUPABASE CLIENT
# =====================================================================

try:

    supabase: Client = create_client(
        SUPABASE_URL,
        SUPABASE_KEY
    )

except Exception as e:

    st.error(
        "❌ Không kết nối được Supabase."
    )

    st.exception(e)

    st.stop()


# =====================================================================
# 9. LOAD GEMINI
# =====================================================================

try:

    from google import genai

    from google.genai import types

except Exception as e:

    st.error(
        "❌ Chưa cài Google GenAI SDK."
    )

    st.code(
        "pip install google-genai"
    )

    st.exception(e)

    st.stop()


# =====================================================================
# 10. GEMINI CLIENT
# =====================================================================

try:

    gemini_client = genai.Client(
        api_key=GEMINI_API_KEY
    )

except Exception as e:

    st.error(
        "❌ Không khởi tạo được Gemini."
    )

    st.exception(e)

    st.stop()


# =====================================================================
# 11. LOAD CLIP
# =====================================================================

@st.cache_resource(show_spinner=False)
def load_clip_model():

    try:

        import torch

        from transformers import (
            CLIPProcessor,
            CLIPModel
        )

        processor = CLIPProcessor.from_pretrained(
            CLIP_MODEL_NAME
        )

        model = CLIPModel.from_pretrained(
            CLIP_MODEL_NAME
        )

        model.eval()

        return processor, model, torch

    except Exception as e:

        raise RuntimeError(
            "Không load được CLIP.\n\n"
            "Hãy kiểm tra requirements.txt có:\n"
            "torch\n"
            "transformers\n\n"
            f"Chi tiết: {e}"
        )


# =====================================================================
# 12. IMAGE NORMALIZATION
# =====================================================================

def normalize_image(image_bytes):

    image = Image.open(
        io.BytesIO(image_bytes)
    )

    image = image.convert("RGB")

    # giới hạn kích thước để giảm RAM
    max_side = 1600

    if max(
        image.size
    ) > max_side:

        image.thumbnail(
            (max_side, max_side),
            Image.Resampling.LANCZOS
        )

    return image


# =====================================================================
# 13. IMAGE HASH
# =====================================================================

def make_image_hash(image_bytes):

    return hashlib.sha256(
        image_bytes
    ).hexdigest()


# =====================================================================
# 14. CLIP IMAGE EMBEDDING
# =====================================================================

def get_clip_embedding(image_bytes):

    try:

        processor, model, torch = load_clip_model()

        image = normalize_image(
            image_bytes
        )

        inputs = processor(
            images=image,
            return_tensors="pt"
        )

        with torch.no_grad():

            image_features = model.get_image_features(
                **inputs
            )

        # -------------------------------------------------------------
        # TRANSFORMERS VERSION COMPATIBILITY
        # -------------------------------------------------------------

        if hasattr(
            image_features,
            "pooler_output"
        ):

            image_features = (
                image_features.pooler_output
            )

        elif hasattr(
            image_features,
            "last_hidden_state"
        ):

            image_features = (
                image_features.last_hidden_state[:, 0, :]
            )

        # Một số version trả BaseModelOutputWithPooling
        if not hasattr(
            image_features,
            "shape"
        ):

            raise Exception(
                "CLIP trả về object không phải tensor."
            )

        # -------------------------------------------------------------
        # FLATTEN
        # -------------------------------------------------------------

        if len(
            image_features.shape
        ) > 2:

            image_features = image_features.flatten(
                start_dim=1
            )

        # -------------------------------------------------------------
        # NORMALIZE
        # -------------------------------------------------------------

        image_features = (
            image_features
            /
            image_features.norm(
                p=2,
                dim=-1,
                keepdim=True
            )
        )

        vector = (
            image_features[0]
            .cpu()
            .numpy()
            .astype(np.float32)
        )

        # -------------------------------------------------------------
        # CHECK DIMENSION
        # -------------------------------------------------------------

        if len(vector) != CLIP_DIMENSION:

            raise Exception(
                f"CLIP dimension không đúng: "
                f"{len(vector)}. "
                f"Cần {CLIP_DIMENSION}."
            )

        return vector.tolist()

    except Exception as e:

        raise Exception(
            "CLIP embedding lỗi: "
            + str(e)
        )


# =====================================================================
# 15. GEMINI JSON EXTRACTION
# =====================================================================

def extract_json(text):

    if not text:

        raise Exception(
            "Gemini không trả về dữ liệu."
        )

    text = str(
        text
    ).strip()

    # -------------------------------------------------------------
    # REMOVE MARKDOWN
    # -------------------------------------------------------------

    text = re.sub(
        r"```json",
        "",
        text,
        flags=re.I
    )

    text = re.sub(
        r"```",
        "",
        text
    )

    text = text.strip()

    # -------------------------------------------------------------
    # FIND FIRST { AND LAST }
    # -------------------------------------------------------------

    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1:

        raise Exception(
            "Gemini không trả JSON hợp lệ:\n"
            + text[:1500]
        )

    json_text = text[
        start:end + 1
    ]

    try:

        return json.loads(
            json_text
        )

    except Exception as e:

        # ---------------------------------------------------------
        # TRY REPAIR COMMON JSON
        # ---------------------------------------------------------

        json_text = json_text.replace(
            "\n",
            " "
        )

        try:

            return json.loads(
                json_text
            )

        except Exception:

            raise Exception(
                "Gemini không trả JSON hợp lệ: "
                + str(e)
                + "\n\n"
                + json_text[:2000]
            )


# =====================================================================
# 16. CATEGORY NORMALIZER
# =====================================================================

def normalize_category(result):

    if not isinstance(
        result,
        dict
    ):

        return "Quần dài"

    raw = str(
        result.get(
            "category",
            ""
        )
    ).strip()

    key = (
        raw
        .upper()
        .strip()
    )

    aliases = {

        "JUMPSUIT":
            "Áo liền quần",

        "ONE PIECE":
            "Áo liền quần",

        "ONE-PIECE":
            "Áo liền quần",

        "BIB OVERALL":
            "Quần yếm",

        "OVERALL":
            "Quần yếm",

        "OVERALLS":
            "Quần yếm",

        "DUNGAREES":
            "Quần yếm",

        "CARGO":
            "Quần túi hộp",

        "CARGO PANTS":
            "Quần túi hộp",

        "JEANS":
            "Quần jean",

        "DENIM":
            "Quần jean",

        "DENIM JEANS":
            "Quần jean",

        "JOGGER":
            "Quần jogger",

        "SHORT":
            "Quần short",

        "SHORTS":
            "Quần short",

        "PANTS":
            "Quần dài",

        "TROUSERS":
            "Quần dài",

        "SHIRT":
            "Áo",

        "TOP":
            "Áo",

        "T-SHIRT":
            "T-shirt",

        "TSHIRT":
            "T-shirt",

        "POLO SHIRT":
            "Polo",

        "HOODIE":
            "Hoodie",

        "JACKET":
            "Jacket",

        "SKIRT":
            "Skirt",

        "DRESS":
            "Dress"
    }

    if key in aliases:

        raw = aliases[key]

    if raw not in CATEGORY_OPTIONS:

        raw = "Quần dài"

    # -------------------------------------------------------------
    # HARD CONSTRUCTION RULES
    # -------------------------------------------------------------

    one_piece = bool(
        result.get(
            "one_piece",
            False
        )
    )

    bib = bool(
        result.get(
            "bib",
            False
        )
    )

    shoulder_straps = bool(
        result.get(
            "shoulder_straps",
            False
        )
    )

    cargo_pockets = bool(
        result.get(
            "cargo_pockets",
            False
        )
    )

    denim = bool(
        result.get(
            "denim",
            False
        )
    )

    jogger_cuffs = bool(
        result.get(
            "jogger_cuffs",
            False
        )
    )

    # ONE PIECE
    if one_piece:

        if bib and shoulder_straps:

            raw = "Quần yếm"

        else:

            raw = "Áo liền quần"

    # BIB OVERALL
    elif bib and shoulder_straps:

        raw = "Quần yếm"

    # CARGO REQUIRES POCKET
    elif raw == "Quần túi hộp":

        if not cargo_pockets:

            raw = "Quần dài"

    # DENIM
    elif raw == "Quần dài" and denim:

        raw = "Quần jean"

    # JOGGER
    elif raw == "Quần dài" and jogger_cuffs:

        raw = "Quần jogger"

    return raw


# =====================================================================
# 17. GEMINI VISION
# =====================================================================

def analyze_garment_with_gemini(
    image_bytes
):

    try:

        image = normalize_image(
            image_bytes
        )

        # ---------------------------------------------------------
        # CONVERT IMAGE
        # ---------------------------------------------------------

        image_buffer = io.BytesIO()

        image.save(
            image_buffer,
            format="JPEG",
            quality=92
        )

        jpeg_bytes = (
            image_buffer
            .getvalue()
        )

        # ---------------------------------------------------------
        # GEMINI
        # ---------------------------------------------------------

        response = gemini_client.models.generate_content(

            model="gemini-2.5-flash",

            contents=[

                types.Part.from_bytes(
                    data=jpeg_bytes,
                    mime_type="image/jpeg"
                ),

                GARMENT_PROMPT
            ],

            config=types.GenerateContentConfig(

                temperature=0,

                response_mime_type="application/json"
            )
        )

        text = response.text

        result = extract_json(
            text
        )

        # ---------------------------------------------------------
        # NORMALIZE
        # ---------------------------------------------------------

        category = normalize_category(
            result
        )

        result["category"] = category

        try:

            result["confidence"] = float(
                result.get(
                    "confidence",
                    0
                )
            )

        except Exception:

            result["confidence"] = 0

        return result

    except Exception as e:

        raise Exception(
            "Gemini Vision lỗi: "
            + str(e)
        )


# =====================================================================
# 18. IMAGE UPLOAD SUPABASE
# =====================================================================

def upload_image_to_storage(
    image_bytes,
    filename
):

    try:

        extension = (
            filename
            .rsplit(
                ".",
                1
            )[-1]
            .lower()
        )

        if extension not in [
            "jpg",
            "jpeg",
            "png",
            "webp"
        ]:

            extension = "jpg"

        # ---------------------------------------------------------
        # SAFE FILENAME
        # ---------------------------------------------------------

        base_name = (
            filename
            .rsplit(
                ".",
                1
            )[0]
        )

        base_name = re.sub(
            r"[^A-Za-z0-9_\-]",
            "_",
            base_name
        )

        storage_path = (
            base_name
            + "."
            + extension
        )

        if extension in [
            "jpg",
            "jpeg"
        ]:

            content_type = "image/jpeg"

        elif extension == "png":

            content_type = "image/png"

        else:

            content_type = "image/webp"

        # ---------------------------------------------------------
        # UPLOAD
        # ---------------------------------------------------------

        supabase.storage \
            .from_(BUCKET_NAME) \
            .upload(
                path=storage_path,
                file=image_bytes,
                file_options={
                    "content-type": content_type,
                    "upsert": "true"
                }
            )

        # ---------------------------------------------------------
        # PUBLIC URL
        # ---------------------------------------------------------

        url_response = (
            supabase
            .storage
            .from_(BUCKET_NAME)
            .get_public_url(
                storage_path
            )
        )

        return (
            storage_path,
            url_response
        )

    except Exception as e:

        raise Exception(
            "Storage upload lỗi: "
            + str(e)
        )


# =====================================================================
# 19. SAVE PRODUCT
# =====================================================================

def save_product(
    product_code,
    image_url,
    category,
    embedding,
    original_filename,
    ai_result
):

    try:

        row = {

            "product_code":
                product_code,

            "image_url":
                image_url,

            "category":
                category,

            "embedding":
                embedding,

            "original_filename":
                original_filename,

            "ai_result":
                ai_result
        }

        response = (
            supabase
            .table("products")
            .upsert(
                row,
                on_conflict="product_code"
            )
            .execute()
        )

        return response

    except Exception as e:

        raise Exception(
            "Database save lỗi: "
            + str(e)
        )


# =====================================================================
# 20. SEARCH VECTOR
# =====================================================================

def search_similar_products(
    query_embedding,
    match_count=DEFAULT_RESULT_COUNT,
    threshold=SIMILARITY_THRESHOLD
):

    try:

        # =============================================================
        # CRITICAL:
        #
        # KHÔNG TRUYỀN CATEGORY.
        #
        # Tìm trên TOÀN BỘ products.
        #
        # Đây là phần sửa lỗi:
        #
        # AI nhận Cargo
        # nhưng database lưu Quần dài
        #
        # → VẪN TÌM ĐƯỢC.
        # =============================================================

        response = (
            supabase
            .rpc(
                "match_products_v3",
                {
                    "query_embedding":
                        query_embedding,

                    "match_threshold":
                        threshold,

                    "match_count":
                        match_count
                }
            )
            .execute()
        )

        return response.data or []

    except Exception as e:

        raise Exception(
            "Similarity search lỗi: "
            + str(e)
        )


# =====================================================================
# 21. CURRENT FILE CLEAR
# =====================================================================

def clear_search_state():

    keys = [

        "search_file_name",
        "search_file_bytes",
        "search_ai_result",
        "search_embedding",
        "search_results",

        "upload_file_name",
        "upload_file_bytes",
        "upload_ai_result",
        "upload_embedding"
    ]

    for key in keys:

        if key in st.session_state:

            del st.session_state[key]


# =====================================================================
# 22. RESULT DISPLAY
# =====================================================================

def display_similarity_results(
    results
):

    if not results:

        st.warning(
            "⚠️ Không tìm thấy mã hàng tương đồng."
        )

        return

    st.success(
        f"🎯 Tìm thấy {len(results)} mã tương đồng."
    )

    # -------------------------------------------------------------
    # SORT
    # -------------------------------------------------------------

    results = sorted(
        results,
        key=lambda x: float(
            x.get(
                "similarity",
                0
            )
        ),
        reverse=True
    )

    cols_per_row = 4

    for start in range(
        0,
        len(results),
        cols_per_row
    ):

        row_results = results[
            start:start + cols_per_row
        ]

        cols = st.columns(
            cols_per_row
        )

        for index, item in enumerate(
            row_results
        ):

            with cols[index]:

                similarity = float(
                    item.get(
                        "similarity",
                        0
                    )
                )

                similarity_percent = (
                    similarity * 100
                )

                st.markdown(
                    f"### #{start + index + 1}"
                )

                image_url = item.get(
                    "image_url"
                )

                if image_url:

                    st.image(
                        image_url,
                        use_container_width=True
                    )

                st.markdown(
                    f"**Mã:** "
                    f"`{item.get('product_code', '-')}`"
                )

                st.metric(
                    "Độ tương đồng",
                    f"{similarity_percent:.2f}%"
                )

                category = item.get(
                    "category",
                    "-"
                )

                st.caption(
                    f"Kho: {category}"
                )

                st.divider()


# =====================================================================
# 23. HEADER
# =====================================================================

st.title(
    "🔍 AI Tìm Kiếm Mã Hàng Tương Đồng"
)

st.caption(
    f"AI Vision + CLIP + Supabase Vector Search — {APP_VERSION}"
)


# =====================================================================
# 24. TABS
# =====================================================================

tab_search, tab_upload = st.tabs(
    [
        "🔍 TÌM KIẾM TƯƠNG ĐỒNG",
        "📦 NẠP KHO HÀNG"
    ]
)


# =====================================================================
# 25. TAB 1 - SEARCH
# =====================================================================

with tab_search:

    st.header(
        "🔍 Tìm mã hàng tương đồng bằng ảnh"
    )

    st.info(
        "AI sẽ tự nhận diện chủng loại. "
        "Category chỉ dùng để phân tích/hiển thị, "
        "không khóa bộ lọc tìm kiếm. "
        "CLIP sẽ tìm trên toàn bộ kho."
    )

    # -------------------------------------------------------------
    # FILE UPLOADER
    #
    # key cố định để sau khi clear có thể thay file mới
    # -------------------------------------------------------------

    uploaded_search = st.file_uploader(

        "📷 Tải ảnh Sketch / mẫu cần tìm",

        type=[
            "jpg",
            "jpeg",
            "png",
            "webp"
        ],

        key="search_uploader"
    )

    # -------------------------------------------------------------
    # CURRENT FILE
    # -------------------------------------------------------------

    if uploaded_search is not None:

        image_bytes = (
            uploaded_search
            .getvalue()
        )

        st.session_state[
            "search_file_bytes"
        ] = image_bytes

        st.session_state[
            "search_file_name"
        ] = uploaded_search.name

        col1, col2 = st.columns(
            [1, 2]
        )

        with col1:

            st.image(
                image_bytes,
                caption=uploaded_search.name,
                use_container_width=True
            )

        with col2:

            st.markdown(
                "### 🤖 AI phân tích"
            )

            if st.button(
                "🚀 PHÂN TÍCH & TÌM TƯƠNG ĐỒNG",
                type="primary",
                use_container_width=True,
                key="btn_search"
            ):

                try:

                    with st.spinner(
                        "🤖 Gemini đang nhận diện..."
                    ):

                        ai_result = (
                            analyze_garment_with_gemini(
                                image_bytes
                            )
                        )

                    st.session_state[
                        "search_ai_result"
                    ] = ai_result

                    with st.spinner(
                        "🧠 CLIP đang tạo image embedding..."
                    ):

                        embedding = (
                            get_clip_embedding(
                                image_bytes
                            )
                        )

                    st.session_state[
                        "search_embedding"
                    ] = embedding

                    with st.spinner(
                        "🔎 Đang tìm toàn bộ kho..."
                    ):

                        results = (
                            search_similar_products(
                                embedding,
                                match_count=12,
                                threshold=0.20
                            )
                        )

                    st.session_state[
                        "search_results"
                    ] = results

                    st.rerun()

                except Exception as e:

                    st.error(
                        str(e)
                    )

    # -------------------------------------------------------------
    # AI RESULT
    # -------------------------------------------------------------

    if (
        "search_ai_result"
        in st.session_state
    ):

        result = st.session_state[
            "search_ai_result"
        ]

        st.markdown(
            "## 🤖 AI nhận diện"
        )

        ai_col1, ai_col2, ai_col3 = st.columns(
            3
        )

        with ai_col1:

            st.metric(
                "Chủng loại AI",
                result.get(
                    "category",
                    "-"
                )
            )

        with ai_col2:

            confidence = float(
                result.get(
                    "confidence",
                    0
                )
            )

            st.metric(
                "Confidence",
                f"{confidence:.1f}%"
            )

        with ai_col3:

            st.metric(
                "One Piece",
                "YES"
                if result.get(
                    "one_piece",
                    False
                )
                else "NO"
            )

        reason = result.get(
            "reason",
            ""
        )

        if reason:

            st.caption(
                "AI reasoning: "
                + str(reason)
            )

    # -------------------------------------------------------------
    # RESULTS
    # -------------------------------------------------------------

    if (
        "search_results"
        in st.session_state
    ):

        st.markdown(
            "## 🎯 Mã hàng tương đồng"
        )

        display_similarity_results(
            st.session_state[
                "search_results"
            ]
        )

    # -------------------------------------------------------------
    # CLEAR CURRENT FILE
    # -------------------------------------------------------------

    st.divider()

    if st.button(
        "🗑️ XÓA FILE ĐANG HIỂN THỊ",
        key="clear_search_file"
    ):

        # ---------------------------------------------------------
        # Chỉ xóa file hiện tại trên giao diện.
        #
        # KHÔNG xóa:
        # - products
        # - Storage
        # - dữ liệu kho
        # ---------------------------------------------------------

        for key in [

            "search_file_bytes",
            "search_file_name",
            "search_ai_result",
            "search_embedding",
            "search_results"
        ]:

            st.session_state.pop(
                key,
                None
            )

        st.rerun()


# =====================================================================
# 26. TAB 2 - UPLOAD / STORAGE
# =====================================================================

with tab_upload:

    st.header(
        "📦 Nạp mã hàng vào kho"
    )

    st.info(
        "Không cần chọn dòng hàng. "
        "Gemini tự nhận diện category và hệ thống tự lưu vào Supabase."
    )

    # -------------------------------------------------------------
    # MULTI UPLOAD
    # -------------------------------------------------------------

    uploaded_files = st.file_uploader(

        "📤 Chọn ảnh mã hàng để lưu kho",

        type=[
            "jpg",
            "jpeg",
            "png",
            "webp"
        ],

        accept_multiple_files=True,

        key="storage_uploader"
    )

    if uploaded_files:

        st.write(
            f"📂 Đã chọn **{len(uploaded_files)}** file."
        )

        # ---------------------------------------------------------
        # PREVIEW
        # ---------------------------------------------------------

        preview_cols = st.columns(
            min(
                len(uploaded_files),
                5
            )
        )

        for index, file in enumerate(
            uploaded_files
        ):

            with preview_cols[
                index % len(preview_cols)
            ]:

                st.image(
                    file,
                    caption=file.name,
                    use_container_width=True
                )

        st.divider()

        if st.button(
            "📤 PHÂN TÍCH AI & LƯU TOÀN BỘ VÀO KHO",
            type="primary",
            use_container_width=True,
            key="btn_save_all"
        ):

            progress = st.progress(
                0
            )

            status = st.empty()

            success_count = 0
            fail_count = 0

            for index, file in enumerate(
                uploaded_files
            ):

                filename = file.name

                try:

                    status.write(
                        f"⏳ "
                        f"{index + 1}/{len(uploaded_files)} "
                        f"— {filename}"
                    )

                    image_bytes = (
                        file.getvalue()
                    )

                    # -------------------------------------------------
                    # PRODUCT CODE
                    # -------------------------------------------------

                    product_code = (
                        filename
                        .rsplit(
                            ".",
                            1
                        )[0]
                        .strip()
                        .upper()
                    )

                    # -------------------------------------------------
                    # GEMINI CATEGORY
                    # -------------------------------------------------

                    ai_result = (
                        analyze_garment_with_gemini(
                            image_bytes
                        )
                    )

                    category = ai_result[
                        "category"
                    ]

                    # -------------------------------------------------
                    # CLIP
                    # -------------------------------------------------

                    embedding = (
                        get_clip_embedding(
                            image_bytes
                        )
                    )

                    # -------------------------------------------------
                    # STORAGE
                    # -------------------------------------------------

                    storage_path, image_url = (
                        upload_image_to_storage(
                            image_bytes,
                            filename
                        )
                    )

                    # -------------------------------------------------
                    # DATABASE
                    # -------------------------------------------------

                    save_product(

                        product_code=
                            product_code,

                        image_url=
                            image_url,

                        category=
                            category,

                        embedding=
                            embedding,

                        original_filename=
                            filename,

                        ai_result=
                            ai_result
                    )

                    success_count += 1

                    st.success(
                        f"✅ {filename} → "
                        f"`{product_code}` → "
                        f"**{category}**"
                    )

                except Exception as e:

                    fail_count += 1

                    st.error(
                        f"❌ {filename}: "
                        f"{str(e)}"
                    )

                progress.progress(
                    (
                        index + 1
                    )
                    /
                    len(uploaded_files)
                )

            status.empty()

            st.success(
                f"🎉 Hoàn thành: "
                f"**{success_count}** thành công / "
                f"**{fail_count}** lỗi."
            )

    # -------------------------------------------------------------
    # CLEAR UPLOAD SCREEN
    # -------------------------------------------------------------

    st.divider()

    if st.button(
        "🗑️ XÓA FILE ĐANG CHỜ UPLOAD",
        key="clear_upload_files"
    ):

        # ---------------------------------------------------------
        # Chỉ reset uploader hiện tại.
        #
        # KHÔNG đụng tới database.
        # KHÔNG xóa Storage.
        # ---------------------------------------------------------

        st.session_state[
            "storage_reset_counter"
        ] = (
            st.session_state.get(
                "storage_reset_counter",
                0
            )
            + 1
        )

        # Không thể thay đổi key của widget sau khi đã tạo,
        # nên dùng rerun và xóa trạng thái liên quan.
        st.rerun()


# =====================================================================
# 27. FOOTER
# =====================================================================

st.divider()

st.caption(
    f"AI Garment Similarity Search — {APP_VERSION}"
)
