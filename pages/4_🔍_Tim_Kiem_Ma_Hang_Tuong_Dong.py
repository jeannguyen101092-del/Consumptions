# =====================================================================
# 🔍 AI TÌM KIẾM MÃ HÀNG TƯƠNG ĐỒNG
# VERSION V4.5
#
# MASTER VERSION
#
# ENGINE:
#   - Gemini Vision
#   - Gemini Embedding 2
#   - Supabase
#   - pgvector
#
# FIX V4.5:
#   1. FORCE EMBEDDING = 768 DIMENSIONS
#   2. KHÔNG BAO GIỜ tạo vector 3072 fallback
#   3. IMAGE UPLOAD -> IMAGE EMBEDDING 768
#   4. IMAGE SEARCH -> IMAGE EMBEDDING 768
#   5. DATABASE -> 768
#   6. RPC SEARCH -> 768
#   7. AI TỰ NHẬN DIỆN CATEGORY
#   8. KHÔNG CÒN SELECTBOX CHỌN DÒNG HÀNG
#   9. CATEGORY CHỈ BOOST, KHÔNG KHÓA SEARCH
#  10. RETRY GEMINI 429 / 503
#  11. DELAY GIỮA CÁC FILE
#  12. KIỂM TRA DIMENSION TRƯỚC DATABASE
#  13. KIỂM TRA DIMENSION TRƯỚC VECTOR SEARCH
#  14. KHÔNG DÙNG HUGGING FACE
#  15. KHÔNG DÙNG CLIP
#  16. KHÔNG DÙNG TORCH
#  17. KHÔNG DÙNG TORCHVISION
# =====================================================================


# =====================================================================
# 0. IMPORT
# =====================================================================

import streamlit as st
import io
import os
import json
import re
import hashlib
import math
import time

from typing import Any, Dict, List, Optional


# =====================================================================
# 1. PAGE CONFIG
# =====================================================================

st.set_page_config(
    page_title="AI Tìm Kiếm Mã Hàng Tương Đồng",
    page_icon="🔍",
    layout="wide"
)


# =====================================================================
# 2. OPTIONAL IMPORT
# =====================================================================

try:

    from supabase import create_client, Client

except Exception as e:

    st.error(
        "❌ Chưa cài thư viện Supabase.\n\n"
        "Thêm vào requirements.txt:\n\n"
        "supabase"
    )

    st.exception(e)

    st.stop()


try:

    from google import genai
    from google.genai import types

except Exception as e:

    st.error(
        "❌ Chưa cài thư viện Google GenAI.\n\n"
        "Thêm vào requirements.txt:\n\n"
        "google-genai"
    )

    st.exception(e)

    st.stop()


# =====================================================================
# 3. CONSTANTS
# =====================================================================

APP_VERSION = "V4.5"

BUCKET_NAME = "product-images"

PRODUCT_TABLE = "products"

# ---------------------------------------------------------
# Gemini Vision
# ---------------------------------------------------------

VISION_MODEL = "gemini-3.6-flash"

# ---------------------------------------------------------
# Gemini Embedding 2
# ---------------------------------------------------------

EMBEDDING_MODEL = "gemini-embedding-2"

# ---------------------------------------------------------
# CRITICAL:
# DATABASE HIỆN TẠI CỦA USER = 768
# ---------------------------------------------------------

EMBEDDING_DIMENSION = 768

# ---------------------------------------------------------
# Search
# ---------------------------------------------------------

SEARCH_COUNT = 12

MIN_SIMILARITY = 0.20

# ---------------------------------------------------------
# Retry
# ---------------------------------------------------------

MAX_GEMINI_RETRIES = 3

RETRY_DELAY_SECONDS = 5

# ---------------------------------------------------------
# Bulk upload delay
# ---------------------------------------------------------

BULK_DELAY_SECONDS = 4.5


# =====================================================================
# 4. CATEGORY MASTER
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

    "Dress"

]


# =====================================================================
# 5. CATEGORY ALIAS
# =====================================================================

CATEGORY_ALIAS = {

    "JUMPSUIT": "Áo liền quần",
    "ONE PIECE": "Áo liền quần",
    "ONE-PIECE": "Áo liền quần",
    "ROMPER": "Áo liền quần",

    "OVERALL": "Quần yếm",
    "OVERALLS": "Quần yếm",
    "BIB OVERALL": "Quần yếm",
    "DUNGAREE": "Quần yếm",
    "DUNGAREES": "Quần yếm",

    "CARGO": "Quần túi hộp",
    "CARGO PANTS": "Quần túi hộp",
    "CARGO TROUSERS": "Quần túi hộp",
    "CARGO TROUSER": "Quần túi hộp",

    "JEANS": "Quần jean",
    "DENIM JEANS": "Quần jean",
    "DENIM PANTS": "Quần jean",

    "JOGGER": "Quần jogger",
    "JOGGERS": "Quần jogger",
    "JOGGER PANTS": "Quần jogger",

    "SHORT": "Quần short",
    "SHORTS": "Quần short",

    "PANTS": "Quần dài",
    "TROUSERS": "Quần dài",
    "TROUSER": "Quần dài",
    "LONG PANTS": "Quần dài",

    "SHIRT": "Áo",
    "TOP": "Áo",

    "T-SHIRT": "T-shirt",
    "TSHIRT": "T-shirt",
    "TEE": "T-shirt",

    "POLO SHIRT": "Polo",
    "POLO": "Polo",

    "HOODIE": "Hoodie",

    "JACKET": "Jacket",
    "BOMBER": "Jacket",
    "OUTERWEAR": "Jacket",

    "SKIRT": "Skirt",

    "DRESS": "Dress"

}


# =====================================================================
# 6. SECRET HELPERS
# =====================================================================

def _safe_secret_get(container, key):

    try:

        if container is None:
            return None

        if key in container:

            value = container[key]

            if value is not None:

                value = str(value).strip()

                if value:
                    return value

    except Exception:

        pass

    return None


def _recursive_find_secret(
    obj,
    target_names
):

    if obj is None:
        return None

    try:

        if hasattr(obj, "items"):

            for key, value in obj.items():

                key_upper = (
                    str(key)
                    .upper()
                    .strip()
                )

                if key_upper in target_names:

                    if value is not None:

                        value = str(value).strip()

                        if value:
                            return value

                result = _recursive_find_secret(
                    value,
                    target_names
                )

                if result:
                    return result

    except Exception:

        pass

    return None


def get_secret(*names):

    normalized = {

        str(x)
        .upper()
        .strip()

        for x in names

    }

    # ---------------------------------------------------------
    # STREAMLIT SECRETS
    # ---------------------------------------------------------

    try:

        for name in normalized:

            value = _safe_secret_get(
                st.secrets,
                name
            )

            if value:
                return value

        value = _recursive_find_secret(
            st.secrets,
            normalized
        )

        if value:
            return value

    except Exception:

        pass

    # ---------------------------------------------------------
    # ENVIRONMENT
    # ---------------------------------------------------------

    for name in normalized:

        value = os.environ.get(name)

        if value:

            value = value.strip()

            if value:
                return value

    return None


# =====================================================================
# 7. LOAD SECRETS
# =====================================================================

SUPABASE_URL = get_secret(
    "SUPABASE_URL",
    "supabase_url"
)

SUPABASE_KEY = get_secret(
    "SUPABASE_KEY",
    "SUPABASE_ANON_KEY",
    "supabase_key",
    "anon_key"
)

GEMINI_API_KEY = get_secret(
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "GEMINI_KEY",
    "gemini_api_key",
    "api_key"
)


# =====================================================================
# 8. SECRET VALIDATION
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

if not GEMINI_API_KEY:

    missing_secrets.append(
        "GEMINI_API_KEY"
    )


if missing_secrets:

    st.error(
        "❌ Không đọc được thông tin bảo mật."
    )

    st.markdown(
        "### Key còn thiếu:"
    )

    for key in missing_secrets:

        st.code(
            key
        )

    st.info(
        """
Streamlit Secrets có thể khai báo:

SUPABASE_URL = "https://xxxxx.supabase.co"
SUPABASE_KEY = "..."
GEMINI_API_KEY = "..."

Hoặc:

[supabase]
url = "https://xxxxx.supabase.co"
key = "..."

[gemini]
api_key = "..."
"""
    )

    st.stop()


# =====================================================================
# 9. CREATE SUPABASE CLIENT
# =====================================================================

try:

    supabase: Client = create_client(
        SUPABASE_URL,
        SUPABASE_KEY
    )

except Exception as e:

    st.error(
        "❌ Không khởi tạo được Supabase."
    )

    st.exception(e)

    st.stop()


# =====================================================================
# 10. CREATE GEMINI CLIENT
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
# 11. SESSION STATE
# =====================================================================

if "search_file" not in st.session_state:

    st.session_state.search_file = None


if "search_result" not in st.session_state:

    st.session_state.search_result = None


if "search_ai_result" not in st.session_state:

    st.session_state.search_ai_result = None


if "pending_upload_files" not in st.session_state:

    st.session_state.pending_upload_files = []


if "last_upload_result" not in st.session_state:

    st.session_state.last_upload_result = None


# =====================================================================
# 12. IMAGE MIME
# =====================================================================

def get_mime_type(filename):

    ext = (
        str(filename)
        .lower()
        .rsplit(".", 1)[-1]
    )

    if ext == "png":
        return "image/png"

    if ext in ["jpg", "jpeg"]:
        return "image/jpeg"

    if ext == "webp":
        return "image/webp"

    return "image/jpeg"


# =====================================================================
# 13. NORMALIZE IMAGE
# =====================================================================

def normalize_image_bytes(
    image_bytes
):

    try:

        from PIL import Image

        image = Image.open(
            io.BytesIO(image_bytes)
        )

        image = image.convert(
            "RGB"
        )

        output = io.BytesIO()

        image.save(
            output,
            format="JPEG",
            quality=92
        )

        return output.getvalue()

    except Exception:

        return image_bytes


# =====================================================================
# 14. FILE HASH
# =====================================================================

def calculate_file_hash(
    image_bytes
):

    return hashlib.sha256(
        image_bytes
    ).hexdigest()


# =====================================================================
# 15. CATEGORY NORMALIZER
# =====================================================================

def normalize_category(
    category
):

    if category is None:
        return "Quần dài"

    value = str(
        category
    ).strip()

    upper = (
        value
        .upper()
        .strip()
    )

    if upper in CATEGORY_ALIAS:

        return CATEGORY_ALIAS[
            upper
        ]

    for valid in CATEGORY_OPTIONS:

        if value.lower() == valid.lower():

            return valid

    return "Quần dài"


# =====================================================================
# 16. GARMENT PROMPT
# =====================================================================

GARMENT_PROMPT = """

You are an expert apparel technical designer and garment recognition AI.

Analyze the garment shown in the image.

This system is used for commercial apparel similarity search.

Identify the actual garment construction, not only superficial appearance.

=========================================================
CRITICAL CATEGORY RULES
=========================================================

1. JUMPSUIT / ONE PIECE

If upper body and lower body are physically connected:

category = "Áo liền quần"

Do NOT classify it as cargo pants.

---------------------------------------------------------

2. BIB OVERALL

If the garment has:

- bib front
- shoulder straps
- trouser body

category = "Quần yếm"

---------------------------------------------------------

3. CARGO PANTS

Only classify as:

"Quần túi hộp"

when it is a separate pants garment AND
there are obvious external cargo / patch pockets
on the side legs.

Do NOT classify ordinary pants as cargo.

Do NOT classify jumpsuits as cargo.

Do NOT classify overalls as cargo.

---------------------------------------------------------

4. JEANS

Separate denim pants:

category = "Quần jean"

---------------------------------------------------------

5. JOGGER

Separate pants with strong jogger construction,
especially elastic / rib ankle cuffs:

category = "Quần jogger"

---------------------------------------------------------

6. SHORTS

Separate pants with short leg:

category = "Quần short"

---------------------------------------------------------

7. LONG PANTS

Separate long trousers without strong cargo,
denim or jogger construction:

category = "Quần dài"

---------------------------------------------------------

8. JACKET

Separate upper-body outerwear:

category = "Jacket"

---------------------------------------------------------

9. DRESS

One-piece dress silhouette:

category = "Dress"

A dress is NOT a jumpsuit.

---------------------------------------------------------

10. UPPER BODY

Shirt / top:

category = "Áo"

T-shirt:

category = "T-shirt"

Polo:

category = "Polo"

Hoodie:

category = "Hoodie"

---------------------------------------------------------

11. SKIRT

Skirt:

category = "Skirt"

=========================================================
AVAILABLE CATEGORIES
=========================================================

- Áo liền quần
- Quần yếm
- Quần túi hộp
- Quần jean
- Quần jogger
- Quần short
- Quần dài
- Jacket
- Áo
- T-shirt
- Polo
- Hoodie
- Skirt
- Dress

=========================================================
ANALYZE
=========================================================

Look carefully at:

- garment boundary
- upper/lower connection
- waistband
- leg construction
- pocket construction
- cargo pockets
- bib
- straps
- sleeves
- collar
- hood
- cuffs
- silhouette
- garment length
- denim appearance

Return ONLY JSON.
"""


# =====================================================================
# 17. BOOLEAN HELPER
# =====================================================================

def bool_value(value):

    if isinstance(
        value,
        bool
    ):

        return value

    if isinstance(
        value,
        str
    ):

        return (
            value
            .lower()
            .strip()
            in [
                "true",
                "yes",
                "1",
                "y"
            ]
        )

    if isinstance(
        value,
        (int, float)
    ):

        return bool(value)

    return False


# =====================================================================
# 18. NORMALIZE GARMENT RESULT
# =====================================================================

def normalize_garment_result(
    result
):

    if not isinstance(
        result,
        dict
    ):

        result = {}

    category = normalize_category(
        result.get(
            "category",
            "Quần dài"
        )
    )

    one_piece = bool_value(
        result.get(
            "one_piece",
            False
        )
    )

    bib = bool_value(
        result.get(
            "bib",
            False
        )
    )

    shoulder_straps = bool_value(
        result.get(
            "shoulder_straps",
            False
        )
    )

    cargo_pockets = bool_value(
        result.get(
            "cargo_pockets",
            False
        )
    )

    denim = bool_value(
        result.get(
            "denim",
            False
        )
    )

    jogger_cuffs = bool_value(
        result.get(
            "jogger_cuffs",
            False
        )
    )

    hood = bool_value(
        result.get(
            "hood",
            False
        )
    )

    # =========================================================
    # HARD RULE 1
    # =========================================================

    if one_piece:

        if bib and shoulder_straps:

            category = "Quần yếm"

        else:

            category = "Áo liền quần"

    # =========================================================
    # HARD RULE 2
    # =========================================================

    elif bib and shoulder_straps:

        category = "Quần yếm"

    # =========================================================
    # HARD RULE 3
    # =========================================================

    elif category == "Quần túi hộp":

        if not cargo_pockets:

            category = "Quần dài"

    # =========================================================
    # HARD RULE 4
    # =========================================================

    if (

        not one_piece

        and not bib

        and denim

        and category in [
            "Quần dài",
            "Quần short"
        ]

    ):

        category = "Quần jean"

    # =========================================================
    # HARD RULE 5
    # =========================================================

    if (

        not one_piece

        and not bib

        and jogger_cuffs

        and category == "Quần dài"

    ):

        category = "Quần jogger"

    # =========================================================
    # CONFIDENCE
    # =========================================================

    try:

        confidence = float(
            result.get(
                "confidence",
                0
            )
        )

    except Exception:

        confidence = 0

    confidence = max(
        0,
        min(
            100,
            confidence
        )
    )

    return {

        "category": category,

        "confidence": confidence,

        "one_piece": one_piece,

        "bib": bib,

        "shoulder_straps":
            shoulder_straps,

        "cargo_pockets":
            cargo_pockets,

        "denim": denim,

        "jogger_cuffs":
            jogger_cuffs,

        "hood": hood,

        "sleeve": str(
            result.get(
                "sleeve",
                ""
            )
        ),

        "collar": str(
            result.get(
                "collar",
                ""
            )
        ),

        "silhouette": str(
            result.get(
                "silhouette",
                ""
            )
        ),

        "length": str(
            result.get(
                "length",
                ""
            )
        ),

        "reason": str(
            result.get(
                "reason",
                ""
            )
        )

    }


# =====================================================================
# 19. GEMINI VISION
# =====================================================================

def analyze_garment_with_gemini(
    image_bytes
):

    image_bytes = normalize_image_bytes(
        image_bytes
    )

    last_error = None

    for attempt in range(
        MAX_GEMINI_RETRIES
    ):

        try:

            response = gemini_client.models.generate_content(

                model=VISION_MODEL,

                contents=[

                    types.Part.from_bytes(

                        data=image_bytes,

                        mime_type="image/jpeg"

                    ),

                    GARMENT_PROMPT

                ],

                config=types.GenerateContentConfig(

                    response_mime_type="application/json",

                    response_schema={

                        "type": "object",

                        "properties": {

                            "category": {
                                "type": "string"
                            },

                            "confidence": {
                                "type": "number"
                            },

                            "one_piece": {
                                "type": "boolean"
                            },

                            "bib": {
                                "type": "boolean"
                            },

                            "shoulder_straps": {
                                "type": "boolean"
                            },

                            "cargo_pockets": {
                                "type": "boolean"
                            },

                            "denim": {
                                "type": "boolean"
                            },

                            "jogger_cuffs": {
                                "type": "boolean"
                            },

                            "sleeve": {
                                "type": "string"
                            },

                            "collar": {
                                "type": "string"
                            },

                            "hood": {
                                "type": "boolean"
                            },

                            "silhouette": {
                                "type": "string"
                            },

                            "length": {
                                "type": "string"
                            },

                            "reason": {
                                "type": "string"
                            }

                        },

                        "required": [

                            "category",
                            "confidence",
                            "one_piece",
                            "bib",
                            "shoulder_straps",
                            "cargo_pockets",
                            "denim",
                            "jogger_cuffs",
                            "hood",
                            "reason"

                        ]

                    },

                    temperature=0.0

                )

            )

            text = getattr(
                response,
                "text",
                None
            )

            if not text:

                raise Exception(
                    "Gemini không trả về text."
                )

            try:

                result = json.loads(
                    text
                )

            except Exception:

                cleaned = re.sub(
                    r"```json|```",
                    "",
                    text,
                    flags=re.I
                ).strip()

                match = re.search(
                    r"\{.*\}",
                    cleaned,
                    flags=re.S
                )

                if not match:

                    raise Exception(
                        "Gemini không trả JSON hợp lệ."
                    )

                result = json.loads(
                    match.group(0)
                )

            return normalize_garment_result(
                result
            )

        except Exception as e:

            last_error = e

            if attempt < MAX_GEMINI_RETRIES - 1:

                time.sleep(
                    RETRY_DELAY_SECONDS
                )

    raise Exception(
        "Gemini Vision lỗi sau "
        f"{MAX_GEMINI_RETRIES} lần thử: "
        f"{last_error}"
    )


# =====================================================================
# 20. GEMINI IMAGE EMBEDDING
#
# CRITICAL:
#   IMAGE -> GEMINI EMBEDDING 2 -> 768
#
# KHÔNG TEXT FALLBACK
# KHÔNG 3072 FALLBACK
# KHÔNG ZERO VECTOR
# =====================================================================

def get_image_embedding(
    image_bytes
):

    image_bytes = normalize_image_bytes(
        image_bytes
    )

    last_error = None

    for attempt in range(
        MAX_GEMINI_RETRIES
    ):

        try:

            response = gemini_client.models.embed_content(

                model=EMBEDDING_MODEL,

                contents=[

                    types.Part.from_bytes(

                        data=image_bytes,

                        mime_type="image/jpeg"

                    )

                ],

                config=types.EmbedContentConfig(

                    output_dimensionality=768

                )

            )

            if not response.embeddings:

                raise Exception(
                    "Gemini không trả về embedding."
                )

            values = response.embeddings[0].values

            if not values:

                raise Exception(
                    "Embedding rỗng."
                )

            values = [

                float(x)

                for x in values

            ]

            # =====================================================
            # ABSOLUTE DIMENSION LOCK
            # =====================================================

            if len(values) != EMBEDDING_DIMENSION:

                raise Exception(

                    "SAI DIMENSION: Gemini trả về "
                    f"{len(values)} dimensions, "
                    f"hệ thống yêu cầu "
                    f"{EMBEDDING_DIMENSION}."

                )

            # =====================================================
            # NORMALIZE
            # =====================================================

            norm = math.sqrt(

                sum(
                    x * x
                    for x in values
                )

            )

            if norm > 0:

                values = [

                    x / norm

                    for x in values

                ]

            # =====================================================
            # FINAL CHECK
            # =====================================================

            if len(values) != 768:

                raise Exception(
                    "Vector cuối cùng không phải 768."
                )

            return values

        except Exception as e:

            last_error = e

            if attempt < MAX_GEMINI_RETRIES - 1:

                time.sleep(
                    RETRY_DELAY_SECONDS
                )

    raise Exception(

        "Gemini Image Embedding lỗi sau "
        f"{MAX_GEMINI_RETRIES} lần thử: "
        f"{last_error}"

    )


# =====================================================================
# 21. STORAGE UPLOAD
# =====================================================================

def upload_image_to_storage(
    image_bytes,
    filename
):

    safe_name = re.sub(

        r"[^A-Za-z0-9._-]",

        "_",

        filename

    )

    # ---------------------------------------------------------
    # Không dùng trực tiếp filename để tránh duplicate
    # ---------------------------------------------------------

    file_hash = hashlib.sha256(
        image_bytes
    ).hexdigest()[:12]

    base_name = safe_name.rsplit(
        ".",
        1
    )[0]

    ext = (
        safe_name.rsplit(
            ".",
            1
        )[-1]
        if "." in safe_name
        else "jpg"
    )

    path = (
        f"{base_name}_{file_hash}.{ext}"
    )

    mime_type = get_mime_type(
        filename
    )

    try:

        supabase.storage \
            .from_(BUCKET_NAME) \
            .upload(

                path=path,

                file=image_bytes,

                file_options={

                    "content-type":
                        mime_type,

                    "upsert":
                        "true",

                    "cache-control":
                        "3600"

                }

            )

    except Exception as e:

        error_text = str(e)

        # =====================================================
        # RLS
        # =====================================================

        if (

            "row-level security"
            in error_text.lower()

            or "unauthorized"
            in error_text.lower()

            or "403"
            in error_text

        ):

            raise Exception(

                "Supabase Storage bị chặn bởi RLS Policy. "

                f"Bucket: {BUCKET_NAME}. "

                "API key hiện tại không có quyền INSERT/UPLOAD."

            )

        # =====================================================
        # TRY UPDATE
        # =====================================================

        try:

            supabase.storage \
                .from_(BUCKET_NAME) \
                .update(

                    path=path,

                    file=image_bytes,

                    file_options={

                        "content-type":
                            mime_type,

                        "upsert":
                            "true",

                        "cache-control":
                            "3600"

                    }

                )

        except Exception:

            raise Exception(
                "Supabase Storage lỗi: "
                + error_text
            )

    # =========================================================
    # PUBLIC URL
    # =========================================================

    try:

        public_url = (

            supabase.storage
            .from_(BUCKET_NAME)
            .get_public_url(path)

        )

        if isinstance(
            public_url,
            dict
        ):

            return (

                public_url.get(
                    "publicUrl"
                )

                or

                public_url.get(
                    "public_url"
                )

            )

        return public_url

    except Exception as e:

        raise Exception(
            "Không lấy được Public URL: "
            + str(e)
        )


# =====================================================================
# 22. SAVE PRODUCT
# =====================================================================

def save_product(
    product_code,
    image_url,
    category,
    ai_category,
    ai_result,
    embedding,
    filename
):

    # =========================================================
    # CRITICAL DATABASE DIMENSION CHECK
    # =========================================================

    if not isinstance(
        embedding,
        list
    ):

        raise Exception(
            "Embedding không phải list."
        )

    embedding_dimension = len(
        embedding
    )

    if embedding_dimension != 768:

        raise Exception(

            "Database BLOCK: embedding phải "
            f"768 dimensions nhưng code đang có "
            f"{embedding_dimension}."

        )

    # =========================================================
    # ROW
    # =========================================================

    row = {

        "product_code":
            product_code,

        "image_url":
            image_url,

        "category":
            category,

        "ai_category":
            ai_category,

        "embedding":
            embedding,

        "ai_analysis":
            ai_result,

        "file_name":
            filename

    }

    # =========================================================
    # UPSERT
    # =========================================================

    try:

        response = (

            supabase
            .table(PRODUCT_TABLE)
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
# 23. SEARCH SIMILAR PRODUCTS
# =====================================================================

def search_similar_products(
    embedding,
    match_count=SEARCH_COUNT
):

    # =========================================================
    # CRITICAL DIMENSION CHECK
    # =========================================================

    if not isinstance(
        embedding,
        list
    ):

        raise Exception(
            "Query embedding không phải list."
        )

    dimension = len(
        embedding
    )

    if dimension != 768:

        raise Exception(

            "Vector search bị chặn: "
            f"query có {dimension} dimensions, "
            "database yêu cầu 768."

        )

    try:

        response = supabase.rpc(

            "match_products_v4",

            {

                "query_embedding":
                    embedding,

                "match_threshold":
                    MIN_SIMILARITY,

                "match_count":
                    match_count

            }

        ).execute()

        return response.data or []

    except Exception as e:

        error_text = str(e)

        if (
            "different vector dimensions"
            in error_text.lower()
        ):

            raise Exception(

                "Supabase RPC đang dùng vector dimension "
                "không đồng nhất. Database hiện tại yêu cầu "
                "768 dimensions. "
                f"Chi tiết: {error_text}"

            )

        raise Exception(
            "Supabase similarity search lỗi: "
            + error_text
        )


# =====================================================================
# 24. CATEGORY BOOST
# =====================================================================

def calculate_display_score(
    item,
    query_category
):

    try:

        similarity = float(
            item.get(
                "similarity",
                0
            )
        )

    except Exception:

        similarity = 0

    db_category = normalize_category(
        item.get(
            "category",
            ""
        )
    )

    ai_category = normalize_category(
        item.get(
            "ai_category",
            ""
        )
    )

    score = similarity

    # =========================================================
    # CATEGORY CHỈ BOOST
    # KHÔNG LOẠI RECORD
    # =========================================================

    if query_category == db_category:

        score += 0.08

    elif query_category == ai_category:

        score += 0.05

    return score


# =====================================================================
# 25. RANK RESULTS
# =====================================================================

def rank_results(
    results,
    query_category
):

    enriched = []

    for item in results:

        item = dict(
            item
        )

        score = calculate_display_score(
            item,
            query_category
        )

        item[
            "display_score"
        ] = score

        enriched.append(
            item
        )

    enriched.sort(

        key=lambda x:
            float(
                x.get(
                    "display_score",
                    0
                )
            ),

        reverse=True

    )

    return enriched


# =====================================================================
# 26. PRODUCT CODE FROM FILE
# =====================================================================

def product_code_from_filename(
    filename
):

    name = str(
        filename
    ).rsplit(
        ".",
        1
    )[0]

    return (
        name
        .strip()
        .upper()
    )


# =====================================================================
# 27. HEADER
# =====================================================================

st.title(
    "🔍 AI TÌM KIẾM MÃ HÀNG TƯƠNG ĐỒNG"
)

st.caption(

    "AI Garment Recognition + "
    "Gemini Embedding 2 + "
    "Supabase pgvector — "
    f"{APP_VERSION} — "
    "Embedding LOCK: 768"

)


# =====================================================================
# 28. TABS
# =====================================================================

tab_search, tab_storage = st.tabs(

    [

        "🔍 TÌM KIẾM TƯƠNG ĐỒNG",

        "📦 NẠP KHO HÀNG LOẠT"

    ]

)


# =====================================================================
# =====================================================================
# TAB 1
# TÌM KIẾM
# =====================================================================
# =====================================================================

with tab_search:

    st.subheader(
        "🔍 Tìm mã hàng bằng ảnh"
    )

    st.info(

        "Không cần chọn dòng hàng. "
        "AI tự nhận dạng garment và tìm trên toàn bộ kho."

    )

    # ---------------------------------------------------------
    # UPLOAD SEARCH IMAGE
    # ---------------------------------------------------------

    search_file = st.file_uploader(

        "📷 Tải ảnh Sketch / ảnh mẫu cần tìm",

        type=[
            "jpg",
            "jpeg",
            "png",
            "webp"
        ],

        key="search_uploader_v45"

    )

    # ---------------------------------------------------------
    # CLEAR SEARCH
    # ---------------------------------------------------------

    col_a, _ = st.columns(
        [1, 5]
    )

    with col_a:

        if st.button(

            "🗑️ Xóa ảnh hiện tại",

            key="clear_search_file_v45"

        ):

            st.session_state.search_file = None

            st.session_state.search_result = None

            st.session_state.search_ai_result = None

            st.rerun()

    # ---------------------------------------------------------
    # SEARCH PROCESS
    # ---------------------------------------------------------

    if search_file is not None:

        image_bytes = search_file.getvalue()

        st.session_state.search_file = (
            image_bytes
        )

        col1, col2 = st.columns(
            [1, 2]
        )

        # =====================================================
        # IMAGE
        # =====================================================

        with col1:

            st.image(

                image_bytes,

                caption=search_file.name,

                use_container_width=True

            )

        # =====================================================
        # ACTION
        # =====================================================

        with col2:

            st.markdown(
                "### 🤖 AI nhận dạng"
            )

            if st.button(

                "🚀 PHÂN TÍCH & TÌM MÃ TƯƠNG ĐỒNG",

                type="primary",

                use_container_width=True,

                key="run_search_v45"

            ):

                try:

                    # =========================================
                    # STEP 1
                    # VISION
                    # =========================================

                    with st.spinner(
                        "🤖 AI đang nhận dạng garment..."
                    ):

                        ai_result = (
                            analyze_garment_with_gemini(
                                image_bytes
                            )
                        )

                    st.session_state.search_ai_result = (
                        ai_result
                    )

                    # =========================================
                    # STEP 2
                    # IMAGE EMBEDDING 768
                    # =========================================

                    with st.spinner(
                        "🧠 Gemini Embedding 2 — vector 768..."
                    ):

                        query_embedding = (
                            get_image_embedding(
                                image_bytes
                            )
                        )

                    # =========================================
                    # ABSOLUTE CHECK
                    # =========================================

                    if len(
                        query_embedding
                    ) != 768:

                        raise Exception(

                            "Query embedding không đúng 768 "
                            f"(đang là {len(query_embedding)})."

                        )

                    # =========================================
                    # STEP 3
                    # VECTOR SEARCH
                    # =========================================

                    with st.spinner(
                        "🔎 Đang đối chiếu toàn bộ kho..."
                    ):

                        results = (
                            search_similar_products(
                                query_embedding
                            )
                        )

                    # =========================================
                    # STEP 4
                    # RANK
                    # =========================================

                    results = rank_results(

                        results,

                        ai_result[
                            "category"
                        ]

                    )

                    st.session_state.search_result = (
                        results
                    )

                except Exception as e:

                    st.session_state.search_result = None

                    st.error(
                        f"❌ Lỗi tìm kiếm: {str(e)}"
                    )

    # =========================================================
    # DISPLAY AI
    # =========================================================

    ai_result = (
        st.session_state.search_ai_result
    )

    if ai_result:

        st.divider()

        st.markdown(
            "### 🤖 Kết quả AI"
        )

        c1, c2, c3, c4 = st.columns(
            4
        )

        with c1:

            st.metric(

                "Category AI",

                ai_result.get(
                    "category",
                    "N/A"
                )

            )

        with c2:

            st.metric(

                "Confidence",

                f"{float(ai_result.get('confidence', 0)):.0f}%"

            )

        with c3:

            st.metric(

                "One Piece",

                (
                    "YES"
                    if ai_result.get(
                        "one_piece",
                        False
                    )
                    else "NO"
                )

            )

        with c4:

            st.metric(

                "Cargo Pocket",

                (
                    "YES"
                    if ai_result.get(
                        "cargo_pockets",
                        False
                    )
                    else "NO"
                )

            )

        if ai_result.get(
            "reason"
        ):

            st.info(

                "🧠 "
                + str(
                    ai_result[
                        "reason"
                    ]
                )

            )

    # =========================================================
    # DISPLAY RESULTS
    # =========================================================

    results = (
        st.session_state.search_result
    )

    if results is not None:

        st.divider()

        st.markdown(
            "### 🎯 Mã hàng tương đồng"
        )

        if not results:

            st.warning(
                "Không tìm thấy mã hàng tương đồng trong kho."
            )

        else:

            display_results = (
                results[:8]
            )

            columns = st.columns(
                min(
                    4,
                    len(display_results)
                )
            )

            for index, item in enumerate(
                display_results
            ):

                with columns[
                    index % len(columns)
                ]:

                    st.markdown(
                        "---"
                    )

                    # -----------------------------------------
                    # IMAGE
                    # -----------------------------------------

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

                    # -----------------------------------------
                    # CODE
                    # -----------------------------------------

                    st.markdown(

                        f"### 🏷️ "
                        f"{item.get('product_code', 'N/A')}"

                    )

                    # -----------------------------------------
                    # SIMILARITY
                    # -----------------------------------------

                    try:

                        similarity = float(
                            item.get(
                                "similarity",
                                0
                            )
                        )

                    except Exception:

                        similarity = 0

                    try:

                        display_score = float(
                            item.get(
                                "display_score",
                                similarity
                            )
                        )

                    except Exception:

                        display_score = similarity

                    st.metric(

                        "Độ tương đồng",

                        f"{similarity * 100:.2f}%"

                    )

                    st.caption(

                        "Điểm xếp hạng: "
                        f"{display_score * 100:.2f}%"

                    )

                    # -----------------------------------------
                    # CATEGORY
                    # -----------------------------------------

                    st.write(

                        "📦 Kho:",

                        item.get(
                            "category",
                            "N/A"
                        )

                    )

                    st.write(

                        "🤖 AI:",

                        item.get(
                            "ai_category",
                            "N/A"
                        )

                    )


# =====================================================================
# =====================================================================
# TAB 2
# NẠP KHO HÀNG LOẠT
# =====================================================================
# =====================================================================

with tab_storage:

    st.subheader(
        "📦 Nạp mã hàng vào kho"
    )

    st.info(

        "AI sẽ tự nhận diện dòng hàng. "
        "Không cần chọn Category thủ công."

    )

    # ---------------------------------------------------------
    # UPLOAD FILES
    # ---------------------------------------------------------

    uploaded_files = st.file_uploader(

        "📷 Chọn ảnh mã hàng",

        type=[
            "jpg",
            "jpeg",
            "png",
            "webp"
        ],

        accept_multiple_files=True,

        key="storage_uploader_v45"

    )

    # ---------------------------------------------------------
    # ADD NEW FILES TO QUEUE
    # ---------------------------------------------------------

    if uploaded_files:

        current_keys = [

            (
                f.name,
                len(
                    f.getvalue()
                )

            )

            for f in
            st.session_state.pending_upload_files

        ]

        for file in uploaded_files:

            file_key = (

                file.name,

                len(
                    file.getvalue()
                )

            )

            if file_key not in current_keys:

                st.session_state \
                    .pending_upload_files \
                    .append(
                        file
                    )

    # ---------------------------------------------------------
    # CLEAR QUEUE
    # ---------------------------------------------------------

    c1, _ = st.columns(
        [1, 5]
    )

    with c1:

        if st.button(

            "🗑️ Xóa danh sách chờ",

            key="clear_pending_files_v45"

        ):

            st.session_state.pending_upload_files = []

            st.rerun()

    # ---------------------------------------------------------
    # PENDING FILES
    # ---------------------------------------------------------

    pending_files = (
        st.session_state.pending_upload_files
    )

    if pending_files:

        st.success(

            f"📂 Đang chờ "
            f"**{len(pending_files)}** "
            f"file để nạp kho."

        )

        # =====================================================
        # PREVIEW
        # =====================================================

        preview_cols = st.columns(

            min(
                5,
                len(pending_files)
            )

        )

        for i, file in enumerate(
            pending_files
        ):

            with preview_cols[
                i % len(preview_cols)
            ]:

                st.image(

                    file,

                    caption=file.name,

                    use_container_width=True

                )

        st.divider()

        # =====================================================
        # START BULK UPLOAD
        # =====================================================

        if st.button(

            "📤 BẮT ĐẦU NẠP TOÀN BỘ VÀO KHO",

            type="primary",

            use_container_width=True,

            key="start_storage_upload_v45"

        ):

            total = len(
                pending_files
            )

            success_count = 0

            failed_count = 0

            progress = st.progress(
                0
            )

            status = st.empty()

            upload_results = []

            # =================================================
            # PROCESS EACH FILE
            # =================================================

            for index, file in enumerate(
                pending_files
            ):

                product_code = (
                    product_code_from_filename(
                        file.name
                    )
                )

                status.write(

                    f"⏳ "
                    f"{index + 1}/{total} "
                    f"— `{product_code}`"

                )

                try:

                    # =========================================
                    # GET BYTES
                    # =========================================

                    image_bytes = (
                        file.getvalue()
                    )

                    if not image_bytes:

                        raise Exception(
                            "File ảnh rỗng."
                        )

                    # =========================================
                    # STEP 1
                    # AI VISION
                    # =========================================

                    status.write(

                        f"🤖 AI đang nhận dạng "
                        f"`{product_code}`..."

                    )

                    ai_result = (
                        analyze_garment_with_gemini(
                            image_bytes
                        )
                    )

                    # =========================================
                    # AI CATEGORY
                    # =========================================

                    ai_category = normalize_category(

                        ai_result.get(
                            "category",
                            "Quần dài"
                        )

                    )

                    # =========================================
                    # STEP 2
                    # IMAGE EMBEDDING
                    # =========================================

                    status.write(

                        f"🧠 Tạo image embedding 768 "
                        f"`{product_code}`..."

                    )

                    embedding = (
                        get_image_embedding(
                            image_bytes
                        )
                    )

                    # =========================================
                    # ABSOLUTE DIMENSION CHECK
                    # =========================================

                    if len(
                        embedding
                    ) != 768:

                        raise Exception(

                            f"Embedding của {product_code} "
                            f"không đúng 768 dimensions."

                        )

                    # =========================================
                    # STEP 3
                    # STORAGE
                    # =========================================

                    status.write(

                        f"☁️ Upload ảnh "
                        f"`{product_code}`..."

                    )

                    image_url = (
                        upload_image_to_storage(

                            image_bytes,

                            file.name

                        )
                    )

                    # =========================================
                    # STEP 4
                    # DATABASE
                    # =========================================

                    status.write(

                        f"💾 Lưu database "
                        f"`{product_code}`..."

                    )

                    save_product(

                        product_code=
                            product_code,

                        image_url=
                            image_url,

                        # -------------------------------------
                        # CATEGORY = AI AUTO DETECT
                        # -------------------------------------

                        category=
                            ai_category,

                        ai_category=
                            ai_category,

                        ai_result=
                            ai_result,

                        embedding=
                            embedding,

                        filename=
                            file.name

                    )

                    # =========================================
                    # SUCCESS
                    # =========================================

                    success_count += 1

                    upload_results.append({

                        "product_code":
                            product_code,

                        "category":
                            ai_category,

                        "ai_category":
                            ai_category,

                        "confidence":
                            float(
                                ai_result.get(
                                    "confidence",
                                    0
                                )
                            ),

                        "status":
                            "OK"

                    })

                except Exception as e:

                    failed_count += 1

                    error_text = str(e)

                    upload_results.append({

                        "product_code":
                            product_code,

                        "category":
                            "",

                        "ai_category":
                            "",

                        "confidence":
                            0,

                        "status":
                            error_text

                    })

                    st.error(

                        f"❌ `{product_code}` — "
                        f"{error_text}"

                    )

                # =================================================
                # PROGRESS
                # =================================================

                progress.progress(

                    int(

                        (
                            index + 1
                        )
                        / total
                        * 100

                    )

                )

                # =================================================
                # DELAY
                # =================================================

                if index < total - 1:

                    time.sleep(
                        BULK_DELAY_SECONDS
                    )

            # =====================================================
            # FINISH
            # =====================================================

            status.empty()

            st.session_state.last_upload_result = (
                upload_results
            )

            # -----------------------------------------------------
            # Chỉ xóa queue sau khi xử lý
            # -----------------------------------------------------

            st.session_state.pending_upload_files = []

            if success_count:

                st.success(

                    f"🎉 Đã nạp thành công "
                    f"**{success_count}/{total}** "
                    f"mã hàng."

                )

            if failed_count:

                st.warning(

                    f"⚠️ Có "
                    f"**{failed_count}** "
                    f"file xử lý thất bại."

                )

            st.rerun()

    # ---------------------------------------------------------
    # UPLOAD REPORT
    # ---------------------------------------------------------

    if st.session_state.last_upload_result:

        st.divider()

        st.markdown(
            "### 📋 Kết quả nạp kho"
        )

        for item in (
            st.session_state.last_upload_result
        ):

            if item.get(
                "status"
            ) == "OK":

                st.success(

                    f"✅ "
                    f"{item.get('product_code', 'N/A')} — "
                    f"AI: {item.get('ai_category', 'N/A')} — "
                    f"Độ tự tin: "
                    f"{float(item.get('confidence', 0)):.0f}%"

                )

            else:

                st.error(

                    f"❌ "
                    f"{item.get('product_code', 'N/A')} — "
                    f"Lỗi: "
                    f"{item.get('status', 'Unknown')}"

                )

        if st.button(

            "🗑️ Xóa thông báo kết quả",

            key="clear_upload_result_report_v45"

        ):

            st.session_state.last_upload_result = None

            st.rerun()


# =====================================================================
# 29. FOOTER
# =====================================================================

st.divider()

st.caption(

    "AI Garment Similarity Search — "
    "Gemini Vision + Gemini Embedding 2 + "
    "Supabase pgvector — "
    "VECTOR DIMENSION: 768"

)
