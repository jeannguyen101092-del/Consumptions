# =====================================================================
# 🔍 AI TÌM KIẾM MÃ HÀNG TƯƠNG ĐỒNG
# VERSION V4.2
#
# MASTER COMMERCIAL GARMENT SIMILARITY ENGINE
#
# ENGINE:
#   - Gemini Vision
#   - Gemini Embedding 2
#   - Supabase
#   - pgvector
#
# KHÔNG DÙNG:
#   - Hugging Face
#   - CLIP API
#   - torch
#   - torchvision
#
# PIPELINE:
#
#   IMAGE
#      ↓
#   GEMINI VISION
#      ↓
#   GARMENT STRUCTURE JSON
#      ↓
#   SEMANTIC TEXT
#      ↓
#   GEMINI EMBEDDING 2
#      ↓
#   768 DIMENSIONS
#      ↓
#   SUPABASE PGVECTOR
#
# CHỨC NĂNG:
#
#   1. AI tự nhận dạng garment
#   2. Upload kho hàng loạt
#   3. AI category
#   4. Warehouse category
#   5. Semantic embedding 768D
#   6. Search similar products
#   7. Category boost
#   8. Không khóa cứng category
#   9. Retry 429 / 503
#   10. Chống duplicate widget key
#   11. Pending upload queue
#   12. Không dùng vector giả
#
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
# 2. OPTIONAL IMPORT - SUPABASE
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


# =====================================================================
# 3. OPTIONAL IMPORT - GOOGLE GENAI
# =====================================================================

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
# 4. CONSTANTS
# =====================================================================

APP_VERSION = "V4.2"


# ---------------------------------------------------------------------
# SUPABASE
# ---------------------------------------------------------------------

BUCKET_NAME = "product-images"

PRODUCT_TABLE = "products"


# ---------------------------------------------------------------------
# GEMINI
# ---------------------------------------------------------------------

VISION_MODEL = "gemini-3.6-flash"

EMBEDDING_MODEL = "gemini-embedding-2"


# ---------------------------------------------------------------------
# CRITICAL:
# SUPABASE COLUMN MUST BE vector(768)
# ---------------------------------------------------------------------

EMBEDDING_DIMENSION = 768


# ---------------------------------------------------------------------
# SEARCH
# ---------------------------------------------------------------------

SEARCH_COUNT = 12

MIN_SIMILARITY = 0.35


# ---------------------------------------------------------------------
# API RETRY
# ---------------------------------------------------------------------

MAX_RETRIES = 3

BASE_RETRY_DELAY = 5

UPLOAD_DELAY = 4.5


# =====================================================================
# 5. CATEGORY MASTER
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
# 6. CATEGORY ALIAS
# =====================================================================

CATEGORY_ALIAS = {

    "JUMPSUIT":
        "Áo liền quần",

    "ONE PIECE":
        "Áo liền quần",

    "ONE-PIECE":
        "Áo liền quần",

    "ROMPER":
        "Áo liền quần",

    "OVERALL":
        "Quần yếm",

    "OVERALLS":
        "Quần yếm",

    "BIB OVERALL":
        "Quần yếm",

    "DUNGAREE":
        "Quần yếm",

    "DUNGAREES":
        "Quần yếm",

    "CARGO":
        "Quần túi hộp",

    "CARGO PANTS":
        "Quần túi hộp",

    "CARGO TROUSERS":
        "Quần túi hộp",

    "CARGO TROUSER":
        "Quần túi hộp",

    "JEANS":
        "Quần jean",

    "JEAN":
        "Quần jean",

    "DENIM JEANS":
        "Quần jean",

    "DENIM PANTS":
        "Quần jean",

    "DENIM TROUSERS":
        "Quần jean",

    "JOGGER":
        "Quần jogger",

    "JOGGERS":
        "Quần jogger",

    "JOGGER PANTS":
        "Quần jogger",

    "SHORT":
        "Quần short",

    "SHORTS":
        "Quần short",

    "PANTS":
        "Quần dài",

    "TROUSERS":
        "Quần dài",

    "TROUSER":
        "Quần dài",

    "LONG PANTS":
        "Quần dài",

    "SHIRT":
        "Áo",

    "TOP":
        "Áo",

    "BLOUSE":
        "Áo",

    "T-SHIRT":
        "T-shirt",

    "TSHIRT":
        "T-shirt",

    "TEE":
        "T-shirt",

    "POLO SHIRT":
        "Polo",

    "POLO":
        "Polo",

    "HOODIE":
        "Hoodie",

    "JACKET":
        "Jacket",

    "BOMBER":
        "Jacket",

    "OUTERWEAR":
        "Jacket",

    "SKIRT":
        "Skirt",

    "DRESS":
        "Dress"

}


# =====================================================================
# 7. SESSION STATE
# =====================================================================

SESSION_DEFAULTS = {

    "search_file":
        None,

    "search_result":
        None,

    "search_ai_result":
        None,

    "pending_upload_files":
        [],

    "last_upload_result":
        None,

    "search_running":
        False,

    "storage_running":
        False

}


for key, default_value in SESSION_DEFAULTS.items():

    if key not in st.session_state:

        st.session_state[key] = default_value


# =====================================================================
# 8. SECRET READER
# =====================================================================

def _safe_secret_get(
    container,
    key
):

    try:

        if container is None:

            return None

        if key not in container:

            return None

        value = container[key]

        if value is None:

            return None

        value = str(value).strip()

        if not value:

            return None

        return value

    except Exception:

        return None


# =====================================================================
# 9. RECURSIVE SECRET SEARCH
# =====================================================================

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
                    .strip()
                    .upper()
                )

                if key_upper in target_names:

                    if value is not None:

                        value_text = (
                            str(value)
                            .strip()
                        )

                        if value_text:

                            return value_text

                nested = (
                    _recursive_find_secret(
                        value,
                        target_names
                    )
                )

                if nested:

                    return nested

    except Exception:

        pass

    return None


# =====================================================================
# 10. GET SECRET
# =====================================================================

def get_secret(
    *names
):

    normalized = {

        str(name)
        .strip()
        .upper()

        for name in names

    }

    # -----------------------------------------------------------------
    # STREAMLIT SECRETS
    # -----------------------------------------------------------------

    try:

        for name in normalized:

            value = _safe_secret_get(
                st.secrets,
                name
            )

            if value:

                return value

        recursive_value = (
            _recursive_find_secret(
                st.secrets,
                normalized
            )
        )

        if recursive_value:

            return recursive_value

    except Exception:

        pass


    # -----------------------------------------------------------------
    # ENVIRONMENT VARIABLES
    # -----------------------------------------------------------------

    for name in normalized:

        value = os.environ.get(
            name
        )

        if value:

            value = value.strip()

            if value:

                return value


    return None


# =====================================================================
# 11. LOAD SECRETS
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

    "google_api_key",

    "api_key"

)


# =====================================================================
# 12. SECRET VALIDATION
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
        "### Key đang bị thiếu:"
    )

    for key in missing_secrets:

        st.code(
            key,
            language="text"
        )

    st.info(
        """
Bạn có thể đặt trong Streamlit Secrets:

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
# 13. CREATE SUPABASE CLIENT
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
# 14. CREATE GEMINI CLIENT
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
# 15. IMAGE MIME
# =====================================================================

def get_mime_type(
    filename
):

    filename = str(
        filename or ""
    )

    ext = (

        filename
        .lower()
        .rsplit(
            ".",
            1
        )[-1]

    )

    if ext == "png":

        return "image/png"

    if ext in [
        "jpg",
        "jpeg"
    ]:

        return "image/jpeg"

    if ext == "webp":

        return "image/webp"

    return "image/jpeg"


# =====================================================================
# 16. NORMALIZE IMAGE
# =====================================================================

def normalize_image_bytes(
    image_bytes
):

    if not image_bytes:

        raise Exception(
            "Ảnh đầu vào rỗng."
        )

    try:

        from PIL import Image

        image = Image.open(
            io.BytesIO(
                image_bytes
            )
        )

        image = image.convert(
            "RGB"
        )

        output = io.BytesIO()

        image.save(

            output,

            format="JPEG",

            quality=92,

            optimize=True

        )

        return output.getvalue()

    except Exception:

        return image_bytes


# =====================================================================
# 17. FILE HASH
# =====================================================================

def calculate_file_hash(
    image_bytes
):

    return hashlib.sha256(
        image_bytes
    ).hexdigest()


# =====================================================================
# 18. CATEGORY NORMALIZER
# =====================================================================

def normalize_category(
    category
):

    if category is None:

        return "Quần dài"

    value = str(
        category
    ).strip()

    if not value:

        return "Quần dài"

    upper = value.upper()

    if upper in CATEGORY_ALIAS:

        return CATEGORY_ALIAS[
            upper
        ]

    for valid in CATEGORY_OPTIONS:

        if value.lower() == valid.lower():

            return valid

    # fuzzy basic matching

    for alias, mapped in CATEGORY_ALIAS.items():

        if alias in upper:

            return mapped

    return "Quần dài"


# =====================================================================
# 19. BOOLEAN NORMALIZER
# =====================================================================

def bool_value(
    value
):

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
            .strip()
            .lower()
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
# 20. GARMENT PROMPT
# =====================================================================

GARMENT_PROMPT = """

You are an expert apparel technical designer,
pattern technician and garment recognition AI.

Analyze the garment in the supplied image.

This system is used for COMMERCIAL APPAREL
SIMILARITY SEARCH.

The objective is to identify the actual garment
construction, not merely superficial appearance.

=========================================================
CRITICAL GARMENT CLASSIFICATION RULES
=========================================================

1. ONE PIECE / JUMPSUIT

If upper body and lower body are physically connected
into ONE garment:

category = "Áo liền quần"

Do NOT classify as cargo pants.

Do NOT classify as ordinary pants.

---------------------------------------------------------

2. BIB OVERALL

If garment has:

- bib front
- shoulder straps
- trouser body

category = "Quần yếm"

Do NOT classify as cargo pants.

---------------------------------------------------------

3. CARGO PANTS

Only classify "Quần túi hộp" when:

- separate pants garment
- obvious external cargo / patch pockets
- pockets are located on side leg areas

Do NOT classify ordinary pants as cargo.

Do NOT classify jumpsuits as cargo.

Do NOT classify overalls as cargo.

---------------------------------------------------------

4. JEANS

Separate pants made from denim.

category = "Quần jean"

---------------------------------------------------------

5. JOGGER

Separate pants with typical jogger construction,
especially elastic or rib ankle cuffs.

category = "Quần jogger"

---------------------------------------------------------

6. SHORTS

Separate pants with short leg length.

category = "Quần short"

---------------------------------------------------------

7. LONG PANTS

Separate long trousers without strong cargo,
denim or jogger construction.

category = "Quần dài"

---------------------------------------------------------

8. JACKET

Separate upper-body outerwear.

category = "Jacket"

---------------------------------------------------------

9. DRESS

One-piece dress silhouette.

A dress is NOT a jumpsuit.

category = "Dress"

---------------------------------------------------------

10. SHIRT / TOP

Upper-body garment.

category = "Áo"

---------------------------------------------------------

11. T-SHIRT

Basic knit tee construction.

category = "T-shirt"

---------------------------------------------------------

12. POLO

Polo collar / placket construction.

category = "Polo"

---------------------------------------------------------

13. HOODIE

Upper-body garment with hood,
typically sweatshirt construction.

category = "Hoodie"

---------------------------------------------------------

14. SKIRT

Separate lower-body skirt garment.

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
ANALYZE STRUCTURE
=========================================================

Look carefully at:

- garment boundaries
- upper/lower connection
- waistband
- fly
- leg construction
- pockets
- cargo pockets
- bib
- straps
- sleeves
- collar
- hood
- cuffs
- silhouette
- length
- denim appearance
- outerwear construction
- knit construction

Do NOT guess cargo just because the garment has pockets.

=========================================================
OUTPUT
=========================================================

Return ONLY JSON.

"""


# =====================================================================
# 21. NORMALIZE GARMENT RESULT
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


    # =================================================================
    # HARD RULE 1 - ONE PIECE
    # =================================================================

    if one_piece:

        if bib and shoulder_straps:

            category = "Quần yếm"

        else:

            category = "Áo liền quần"


    # =================================================================
    # HARD RULE 2 - BIB
    # =================================================================

    elif bib and shoulder_straps:

        category = "Quần yếm"


    # =================================================================
    # HARD RULE 3 - CARGO
    # =================================================================

    elif category == "Quần túi hộp":

        if not cargo_pockets:

            category = "Quần dài"


    # =================================================================
    # HARD RULE 4 - DENIM
    # =================================================================

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


    # =================================================================
    # HARD RULE 5 - JOGGER
    # =================================================================

    if (

        not one_piece

        and not bib

        and jogger_cuffs

        and category == "Quần dài"

    ):

        category = "Quần jogger"


    # =================================================================
    # CONFIDENCE
    # =================================================================

    try:

        confidence = float(

            result.get(
                "confidence",
                0
            )

        )

    except Exception:

        confidence = 0.0


    confidence = max(

        0.0,

        min(
            100.0,
            confidence
        )

    )


    # =================================================================
    # FINAL
    # =================================================================

    return {

        "category":
            category,

        "confidence":
            confidence,

        "one_piece":
            one_piece,

        "bib":
            bib,

        "shoulder_straps":
            shoulder_straps,

        "cargo_pockets":
            cargo_pockets,

        "denim":
            denim,

        "jogger_cuffs":
            jogger_cuffs,

        "hood":
            hood,

        "sleeve":
            str(
                result.get(
                    "sleeve",
                    ""
                )
            ),

        "collar":
            str(
                result.get(
                    "collar",
                    ""
                )
            ),

        "silhouette":
            str(
                result.get(
                    "silhouette",
                    ""
                )
            ),

        "length":
            str(
                result.get(
                    "length",
                    ""
                )
            ),

        "reason":
            str(
                result.get(
                    "reason",
                    ""
                )
            )

    }


# =====================================================================
# 22. GEMINI VISION
# =====================================================================

def analyze_garment_with_gemini(
    image_bytes
):

    image_bytes = normalize_image_bytes(
        image_bytes
    )


    last_error = None


    for attempt in range(
        MAX_RETRIES
    ):

        try:

            response = (
                gemini_client
                .models
                .generate_content(

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
            )


            text = getattr(
                response,
                "text",
                None
            )


            if not text:

                raise Exception(
                    "Gemini Vision không trả kết quả."
                )


            # ---------------------------------------------------------
            # PARSE JSON
            # ---------------------------------------------------------

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

                        "Gemini không trả JSON hợp lệ:\n"
                        + text[:2000]

                    )


                result = json.loads(

                    match.group(0)

                )


            return normalize_garment_result(
                result
            )


        except Exception as e:

            last_error = e

            error_text = str(e).lower()


            # ---------------------------------------------------------
            # RETRY CHO 429 / 503 / RESOURCE EXHAUSTED
            # ---------------------------------------------------------

            retryable = any(

                keyword in error_text

                for keyword in [

                    "429",

                    "503",

                    "resource exhausted",

                    "rate limit",

                    "temporarily unavailable",

                    "unavailable",

                    "overloaded"

                ]

            )


            if (
                attempt < MAX_RETRIES - 1
                and retryable
            ):

                time.sleep(

                    BASE_RETRY_DELAY
                    * (
                        attempt + 1
                    )

                )

                continue


            break


    raise Exception(

        "Gemini Vision lỗi: "
        + str(last_error)

    )


# =====================================================================
# 23. BUILD SEMANTIC TEXT
# =====================================================================

def build_garment_embedding_text(
    ai_result
):

    category = normalize_category(

        ai_result.get(
            "category",
            "Quần dài"
        )

    )


    text = f"""

Commercial apparel garment description.

Category:
{category}

One piece:
{ai_result.get("one_piece", False)}

Bib:
{ai_result.get("bib", False)}

Shoulder straps:
{ai_result.get("shoulder_straps", False)}

Cargo pockets:
{ai_result.get("cargo_pockets", False)}

Denim:
{ai_result.get("denim", False)}

Jogger cuffs:
{ai_result.get("jogger_cuffs", False)}

Hood:
{ai_result.get("hood", False)}

Sleeve:
{ai_result.get("sleeve", "")}

Collar:
{ai_result.get("collar", "")}

Silhouette:
{ai_result.get("silhouette", "")}

Length:
{ai_result.get("length", "")}

Construction:
{ai_result.get("reason", "")}

"""

    return text.strip()


# =====================================================================
# 24. EXTRACT EMBEDDING VALUES
# =====================================================================

def extract_embedding_values(
    response
):

    # -----------------------------------------------------------------
    # Standard Gemini response
    # -----------------------------------------------------------------

    try:

        embeddings = response.embeddings

        if embeddings:

            first = embeddings[0]

            values = first.values

            if values:

                return [
                    float(x)
                    for x in values
                ]

    except Exception:

        pass


    # -----------------------------------------------------------------
    # Fallback
    # -----------------------------------------------------------------

    try:

        embedding = response.embedding

        if embedding:

            values = embedding.values

            if values:

                return [
                    float(x)
                    for x in values
                ]

    except Exception:

        pass


    return []


# =====================================================================
# 25. NORMALIZE VECTOR
# =====================================================================

def normalize_vector(
    values
):

    if not values:

        raise Exception(
            "Embedding rỗng."
        )


    values = [

        float(x)

        for x in values

    ]


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


    return values


# =====================================================================
# 26. GEMINI TEXT EMBEDDING
# =====================================================================

def get_text_embedding(
    text
):

    if not text:

        raise Exception(
            "Text embedding rỗng."
        )


    last_error = None


    for attempt in range(
        MAX_RETRIES
    ):

        try:

            response = (

                gemini_client
                .models
                .embed_content(

                    model=EMBEDDING_MODEL,

                    contents=text,

                    config=types.EmbedContentConfig(

                        output_dimensionality=
                            EMBEDDING_DIMENSION

                    )

                )

            )


            values = extract_embedding_values(
                response
            )


            if not values:

                raise Exception(
                    "Gemini không trả vector."
                )


            values = normalize_vector(
                values
            )


            # =========================================================
            # CRITICAL DIMENSION CHECK
            # =========================================================

            dimension = len(
                values
            )


            if dimension != EMBEDDING_DIMENSION:

                raise Exception(

                    f"Embedding dimension không đúng. "
                    f"Gemini trả {dimension}D, "
                    f"hệ thống yêu cầu "
                    f"{EMBEDDING_DIMENSION}D."

                )


            return values


        except Exception as e:

            last_error = e

            error_text = str(e).lower()


            retryable = any(

                keyword in error_text

                for keyword in [

                    "429",

                    "503",

                    "resource exhausted",

                    "rate limit",

                    "temporarily unavailable",

                    "unavailable",

                    "overloaded"

                ]

            )


            if (

                attempt < MAX_RETRIES - 1

                and retryable

            ):

                time.sleep(

                    BASE_RETRY_DELAY
                    * (
                        attempt + 1
                    )

                )

                continue


            break


    raise Exception(

        "Gemini Text Embedding lỗi: "
        + str(last_error)

    )


# =====================================================================
# 27. IMAGE -> SEMANTIC EMBEDDING
# =====================================================================
#
# LƯU Ý:
#
# Hệ thống V4.2 không gửi ảnh trực tiếp vào embedding.
#
# IMAGE
#   ↓
# VISION
#   ↓
# STRUCTURE JSON
#   ↓
# TEXT DESCRIPTION
#   ↓
# EMBEDDING 768D
#
# =====================================================================

def get_image_embedding(
    image_bytes
):

    ai_result = (
        analyze_garment_with_gemini(
            image_bytes
        )
    )


    text = build_garment_embedding_text(
        ai_result
    )


    embedding = get_text_embedding(
        text
    )


    return embedding


# =====================================================================
# 28. IMAGE -> AI + EMBEDDING
# =====================================================================

def analyze_and_embed_image(
    image_bytes
):

    ai_result = (
        analyze_garment_with_gemini(
            image_bytes
        )
    )


    text_for_embedding = (
        build_garment_embedding_text(
            ai_result
        )
    )


    embedding = get_text_embedding(
        text_for_embedding
    )


    if len(embedding) != EMBEDDING_DIMENSION:

        raise Exception(

            f"Embedding phải là "
            f"{EMBEDDING_DIMENSION}D nhưng nhận "
            f"{len(embedding)}D."

        )


    return (
        ai_result,
        embedding
    )


# =====================================================================
# 29. UPLOAD IMAGE TO SUPABASE STORAGE
# =====================================================================

def upload_image_to_storage(
    image_bytes,
    filename
):

    safe_name = re.sub(

        r"[^A-Za-z0-9._-]",

        "_",

        str(filename)

    )


    if not safe_name:

        raise Exception(
            "Tên file không hợp lệ."
        )


    # -----------------------------------------------------------------
    # Dùng hash để tránh 2 file cùng tên ghi đè sai
    # -----------------------------------------------------------------

    file_hash = calculate_file_hash(
        image_bytes
    )[:12]


    name_without_ext = (
        safe_name.rsplit(
            ".",
            1
        )[0]
    )


    ext = "jpg"


    if "." in safe_name:

        ext = safe_name.rsplit(
            ".",
            1
        )[-1].lower()


    storage_filename = (

        f"{name_without_ext}_"
        f"{file_hash}."
        f"{ext}"

    )


    path = storage_filename


    mime_type = get_mime_type(
        filename
    )


    last_error = None


    for attempt in range(
        MAX_RETRIES
    ):

        try:

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

            except Exception:

                # -----------------------------------------------------
                # Nếu tồn tại -> update
                # -----------------------------------------------------

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


            public_url = (

                supabase.storage
                .from_(BUCKET_NAME)
                .get_public_url(
                    path
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
                    "Không lấy được Public URL."
                )


            return public_url


        except Exception as e:

            last_error = e

            error_text = str(e).lower()


            retryable = any(

                keyword in error_text

                for keyword in [

                    "429",

                    "503",

                    "timeout",

                    "temporarily",

                    "rate"

                ]

            )


            if (

                attempt < MAX_RETRIES - 1

                and retryable

            ):

                time.sleep(

                    BASE_RETRY_DELAY
                    * (
                        attempt + 1
                    )

                )

                continue


            break


    raise Exception(

        "Supabase Storage lỗi: "
        + str(last_error)

    )


# =====================================================================
# 30. SAVE PRODUCT
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

    # -----------------------------------------------------------------
    # CRITICAL EMBEDDING VALIDATION
    # -----------------------------------------------------------------

    if not embedding:

        raise Exception(
            "Không có embedding."
        )


    dimension = len(
        embedding
    )


    if dimension != EMBEDDING_DIMENSION:

        raise Exception(

            f"Không thể lưu database. "
            f"Vector hiện tại = {dimension}D, "
            f"yêu cầu = {EMBEDDING_DIMENSION}D."

        )


    row = {

        "product_code":
            str(product_code),

        "image_url":
            str(image_url),

        "category":
            normalize_category(
                category
            ),

        "ai_category":
            normalize_category(
                ai_category
            ),

        "embedding":
            embedding,

        "ai_analysis":
            ai_result,

        "file_name":
            str(filename)

    }


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

        error_text = str(e)


        # -------------------------------------------------------------
        # Cảnh báo rõ nếu DB vẫn đang 3072D
        # -------------------------------------------------------------

        if (
            "expected 3072 dimensions"
            in error_text
        ):

            raise Exception(

                "SUPABASE ĐANG DÙNG vector(3072), "
                "trong khi V4.2 dùng vector(768). "
                "Hãy đổi cột products.embedding "
                "và RPC match_products_v4 sang vector(768)."

            )


        raise Exception(

            "Database save lỗi: "
            + error_text

        )


# =====================================================================
# 31. SEARCH SIMILAR PRODUCTS
# =====================================================================

def search_similar_products(
    embedding,
    match_count=SEARCH_COUNT
):

    # -----------------------------------------------------------------
    # CRITICAL DIMENSION CHECK
    # -----------------------------------------------------------------

    if not embedding:

        raise Exception(
            "Query embedding rỗng."
        )


    dimension = len(
        embedding
    )


    if dimension != EMBEDDING_DIMENSION:

        raise Exception(

            f"Query embedding = {dimension}D. "
            f"Yêu cầu = {EMBEDDING_DIMENSION}D."

        )


    try:

        response = (

            supabase
            .rpc(

                "match_products_v4",

                {

                    "query_embedding":
                        embedding,

                    "match_threshold":
                        MIN_SIMILARITY,

                    "match_count":
                        match_count

                }

            )
            .execute()

        )


        return response.data or []


    except Exception as e:

        error_text = str(e)


        if (
            "expected 3072 dimensions"
            in error_text
        ):

            raise Exception(

                "RPC match_products_v4 "
                "vẫn đang yêu cầu 3072D. "
                "Hãy đổi RPC sang vector(768)."

            )


        raise Exception(

            "Supabase similarity search lỗi: "
            + error_text

        )


# =====================================================================
# 32. CATEGORY BOOST
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

        similarity = 0.0


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


    # -----------------------------------------------------------------
    # CATEGORY BOOST
    #
    # KHÔNG LOẠI RECORD
    # -----------------------------------------------------------------

    if query_category == db_category:

        score += 0.08

    elif query_category == ai_category:

        score += 0.05


    return score


# =====================================================================
# 33. RANK RESULTS
# =====================================================================

def rank_results(
    results,
    query_category
):

    enriched = []


    for raw_item in results:

        item = dict(
            raw_item
        )


        item["display_score"] = (

            calculate_display_score(

                item,

                query_category

            )

        )


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
# 34. PRODUCT CODE FROM FILE NAME
# =====================================================================

def product_code_from_filename(
    filename
):

    name = str(
        filename
    )


    if "." in name:

        name = name.rsplit(
            ".",
            1
        )[0]


    name = name.strip()


    if not name:

        return "UNKNOWN"


    return name.upper()


# =====================================================================
# 35. FORMAT ERROR
# =====================================================================

def clean_error_message(
    error
):

    text = str(
        error
    ).strip()


    if len(text) > 1500:

        text = text[:1500] + "..."

    return text


# =====================================================================
# 36. HEADER
# =====================================================================

st.title(
    "🔍 AI TÌM KIẾM MÃ HÀNG TƯƠNG ĐỒNG"
)

st.caption(

    "Gemini Vision + Gemini Embedding 2 "
    "+ Supabase pgvector — "
    f"{APP_VERSION} — "
    f"Embedding {EMBEDDING_DIMENSION}D"

)


# =====================================================================
# 37. SYSTEM STATUS
# =====================================================================

with st.expander(
    "⚙️ Trạng thái hệ thống",
    expanded=False
):

    s1, s2, s3, s4 = st.columns(4)


    with s1:

        st.metric(
            "Version",
            APP_VERSION
        )


    with s2:

        st.metric(
            "Embedding",
            f"{EMBEDDING_DIMENSION}D"
        )


    with s3:

        st.metric(
            "Vision",
            "Gemini"
        )


    with s4:

        st.metric(
            "Vector DB",
            "pgvector"
        )


# =====================================================================
# 38. TABS
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
        "AI tự nhận dạng garment và tìm "
        "trên toàn bộ kho."

    )


    # ================================================================
    # FILE UPLOAD
    # ================================================================

    search_file = st.file_uploader(

        "📷 Tải ảnh Sketch / ảnh mẫu cần tìm",

        type=[

            "jpg",

            "jpeg",

            "png",

            "webp"

        ],

        key="search_uploader_v42"

    )


    # ================================================================
    # CLEAR SEARCH
    # ================================================================

    col_clear, _ = st.columns(
        [1, 5]
    )


    with col_clear:

        if st.button(

            "🗑️ Xóa ảnh hiện tại",

            key="clear_search_file_v42"

        ):

            st.session_state.search_file = None

            st.session_state.search_result = None

            st.session_state.search_ai_result = None

            st.rerun()


    # ================================================================
    # SEARCH IMAGE
    # ================================================================

    if search_file is not None:

        image_bytes = (
            search_file.getvalue()
        )


        st.session_state.search_file = (
            image_bytes
        )


        col1, col2 = st.columns(
            [1, 1]
        )


        # ------------------------------------------------------------
        # IMAGE
        # ------------------------------------------------------------

        with col1:

            st.image(

                image_bytes,

                caption=search_file.name,

                use_container_width=True

            )


        # ------------------------------------------------------------
        # AI SEARCH
        # ------------------------------------------------------------

        with col2:

            st.markdown(
                "### 🤖 AI nhận dạng"
            )


            if st.button(

                "🚀 PHÂN TÍCH & TÌM MÃ TƯƠNG ĐỒNG",

                type="primary",

                use_container_width=True,

                key="run_search_v42"

            ):

                st.session_state.search_running = True


                try:

                    # =================================================
                    # STEP 1
                    # VISION
                    # =================================================

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


                    # =================================================
                    # STEP 2
                    # BUILD TEXT
                    # =================================================

                    semantic_text = (
                        build_garment_embedding_text(
                            ai_result
                        )
                    )


                    # =================================================
                    # STEP 3
                    # EMBEDDING 768D
                    # =================================================

                    with st.spinner(

                        "🧠 Đang tạo semantic embedding 768D..."

                    ):

                        query_embedding = (
                            get_text_embedding(
                                semantic_text
                            )
                        )


                    # =================================================
                    # SHOW DIMENSION
                    # =================================================

                    if len(query_embedding) != EMBEDDING_DIMENSION:

                        raise Exception(

                            f"Vector search sai dimension: "
                            f"{len(query_embedding)}D."

                        )


                    # =================================================
                    # STEP 4
                    # VECTOR SEARCH
                    # =================================================

                    with st.spinner(

                        "🔎 Đang đối chiếu dữ liệu kho..."

                    ):

                        results = (
                            search_similar_products(
                                query_embedding
                            )
                        )


                    # =================================================
                    # STEP 5
                    # RANK
                    # =================================================

                    results = rank_results(

                        results,

                        ai_result[
                            "category"
                        ]

                    )


                    st.session_state.search_result = (
                        results
                    )


                    st.success(

                        f"✅ Đã tìm thấy "
                        f"{len(results)} kết quả."

                    )


                except Exception as e:

                    st.session_state.search_result = None

                    st.error(

                        "❌ Lỗi tìm kiếm:\n\n"
                        + clean_error_message(e)

                    )


                finally:

                    st.session_state.search_running = False


    # ================================================================
    # DISPLAY AI RESULT
    # ================================================================

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

            confidence = float(

                ai_result.get(
                    "confidence",
                    0
                )

            )

            st.metric(

                "Confidence",

                f"{confidence:.0f}%"

            )


        with c3:

            st.metric(

                "One Piece",

                "YES"
                if ai_result.get(
                    "one_piece",
                    False
                )
                else "NO"

            )


        with c4:

            st.metric(

                "Cargo Pocket",

                "YES"
                if ai_result.get(
                    "cargo_pockets",
                    False
                )
                else "NO"

            )


        # ------------------------------------------------------------
        # EXTRA STRUCTURE
        # ------------------------------------------------------------

        with st.expander(
            "🔎 Chi tiết cấu trúc AI",
            expanded=False
        ):

            a1, a2, a3 = st.columns(3)


            with a1:

                st.write(

                    "Denim:",

                    "YES"
                    if ai_result.get(
                        "denim",
                        False
                    )
                    else "NO"

                )

                st.write(

                    "Jogger cuff:",

                    "YES"
                    if ai_result.get(
                        "jogger_cuffs",
                        False
                    )
                    else "NO"

                )


            with a2:

                st.write(

                    "Bib:",

                    "YES"
                    if ai_result.get(
                        "bib",
                        False
                    )
                    else "NO"

                )

                st.write(

                    "Shoulder straps:",

                    "YES"
                    if ai_result.get(
                        "shoulder_straps",
                        False
                    )
                    else "NO"

                )


            with a3:

                st.write(

                    "Hood:",

                    "YES"
                    if ai_result.get(
                        "hood",
                        False
                    )
                    else "NO"

                )

                st.write(

                    "Silhouette:",

                    ai_result.get(
                        "silhouette",
                        ""
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


    # ================================================================
    # DISPLAY SEARCH RESULTS
    # ================================================================

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

                "Không tìm thấy mã hàng "
                "tương đồng trong kho."

            )

        else:

            st.caption(

                f"Hiển thị {min(8, len(results))} "
                f"/ {len(results)} kết quả."

            )


            display_results = results[:8]


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


                    # ------------------------------------------------
                    # IMAGE
                    # ------------------------------------------------

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


                    # ------------------------------------------------
                    # PRODUCT CODE
                    # ------------------------------------------------

                    st.markdown(

                        f"### 🏷️ "
                        f"{item.get('product_code', 'N/A')}"

                    )


                    # ------------------------------------------------
                    # SIMILARITY
                    # ------------------------------------------------

                    try:

                        similarity = float(

                            item.get(
                                "similarity",
                                0
                            )

                        )

                    except Exception:

                        similarity = 0.0


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


                    if display_score != similarity:

                        st.caption(

                            f"Điểm xếp hạng: "
                            f"{display_score * 100:.2f}%"

                        )


                    # ------------------------------------------------
                    # CATEGORY
                    # ------------------------------------------------

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

# --- WIDGET UPLOAD ---
uploaded_files = st.file_uploader(
    "📷 Chọn ảnh mã hàng", 
    type=["jpg", "jpeg", "png", "webp"], 
    accept_multiple_files=True, 
    key="storage_uploader"
)

    


    # ================================================================
    # FILE UPLOADER
    # ================================================================

    uploaded_files = st.file_uploader(

        "📷 Chọn ảnh mã hàng",

        type=[

            "jpg",

            "jpeg",

            "png",

            "webp"

        ],

        accept_multiple_files=True,

        key="storage_uploader_v42"

    )


    # ================================================================
    # ADD FILES TO QUEUE
    # ================================================================

    if uploaded_files:

        current_names = {

            str(file.name)
            .strip()
            .lower()

            for file
            in st.session_state.pending_upload_files

        }


        for file in uploaded_files:

            filename_key = (

                str(file.name)
                .strip()
                .lower()

            )


            if filename_key not in current_names:

                st.session_state.pending_upload_files.append(
                    file
                )

                current_names.add(
                    filename_key
                )


    # ================================================================
    # CLEAR PENDING
    # ================================================================

    c1, _ = st.columns(
        [1, 5]
    )


    with c1:

        if st.button(

            "🗑️ Xóa danh sách chờ",

            key="clear_pending_files_v42"

        ):

            st.session_state.pending_upload_files = []

            st.rerun()


    # ================================================================
    # PENDING FILES
    # ================================================================

    pending_files = (
        st.session_state.pending_upload_files
    )


    if pending_files:

        st.success(

            f"📂 Đang chờ "
            f"**{len(pending_files)}** "
            f"file để nạp kho."

        )


        # ============================================================
        # PREVIEW
        # ============================================================

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

                try:

                    st.image(

                        file,

                        caption=file.name,

                        use_container_width=True

                    )

                except Exception:

                    st.write(
                        f"📄 {file.name}"
                    )


        st.divider()


        # ============================================================
        # START UPLOAD
        # ============================================================

        if st.button(

            "📤 BẮT ĐẦU NẠP TOÀN BỘ VÀO KHO",

            type="primary",

            use_container_width=True,

            key="start_storage_upload_v42"

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


            # ========================================================
            # PROCESS FILES
            # ========================================================

            for index, file in enumerate(
                pending_files
            ):

                product_code = (
                    product_code_from_filename(
                        file.name
                    )
                )


                status.write(

                    f"⏳ {index + 1}/{total} "
                    f"— `{product_code}`"

                )


                try:

                    # =================================================
                    # IMAGE
                    # =================================================

                    image_bytes = (
                        file.getvalue()
                    )


                    if not image_bytes:

                        raise Exception(
                            "File ảnh rỗng."
                        )


                    # =================================================
                    # STEP 1
                    # VISION
                    # =================================================

                    status.write(

                        f"🤖 AI đang nhận dạng "
                        f"`{product_code}`..."

                    )


                    ai_result = (
                        analyze_garment_with_gemini(
                            image_bytes
                        )
                    )


                    ai_category = normalize_category(

                        ai_result.get(
                            "category",
                            "Quần dài"
                        )

                    )


                    # =================================================
                    # STEP 2
                    # BUILD SEMANTIC TEXT
                    # =================================================

                    status.write(

                        f"🧠 Chuẩn bị semantic "
                        f"description `{product_code}`..."

                    )


                    semantic_text = (
                        build_garment_embedding_text(
                            ai_result
                        )
                    )


                    # =================================================
                    # STEP 3
                    # EMBEDDING
                    # =================================================

                    status.write(

                        f"🧠 Tạo embedding "
                        f"{EMBEDDING_DIMENSION}D "
                        f"`{product_code}`..."

                    )


                    embedding = (
                        get_text_embedding(
                            semantic_text
                        )
                    )


                    # =================================================
                    # HARD DIMENSION CHECK
                    # =================================================

                    embedding_dimension = len(
                        embedding
                    )


                    if (
                        embedding_dimension
                        != EMBEDDING_DIMENSION
                    ):

                        raise Exception(

                            f"Embedding sai dimension: "
                            f"{embedding_dimension}D. "
                            f"Yêu cầu "
                            f"{EMBEDDING_DIMENSION}D."

                        )


                    # =================================================
                    # STEP 4
                    # STORAGE
                    # =================================================

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


                    # =================================================
                    # STEP 5
                    # DATABASE
                    # =================================================

                    status.write(

                        f"💾 Lưu database "
                        f"`{product_code}`..."

                    )


                    save_product(

                        product_code=
                            product_code,

                        image_url=
                            image_url,

                        category=
                            storage_category,

                        ai_category=
                            ai_category,

                        ai_result=
                            ai_result,

                        embedding=
                            embedding,

                        filename=
                            file.name

                    )


                    # =================================================
                    # SUCCESS
                    # =================================================

                    success_count += 1


                    upload_results.append({

                        "product_code":
                            product_code,

                        "category":
                            storage_category,

                        "ai_category":
                            ai_category,

                        "confidence":
                            float(
                                ai_result.get(
                                    "confidence",
                                    0
                                )
                            ),

                        "embedding_dim":
                            embedding_dimension,

                        "status":
                            "OK"

                    })


                except Exception as e:

                    # =================================================
                    # ERROR
                    # =================================================

                    failed_count += 1


                    error_message = (
                        clean_error_message(
                            e
                        )
                    )


                    upload_results.append({

                        "product_code":
                            product_code,

                        "category":
                            storage_category,

                        "ai_category":
                            "",

                        "confidence":
                            0,

                        "embedding_dim":
                            0,

                        "status":
                            error_message

                    })


                    st.error(

                        f"❌ `{file.name}` — "
                        f"{error_message}"

                    )


                # =====================================================
                # PROGRESS
                # =====================================================

                progress.progress(

                    int(

                        (
                            index + 1
                        )
                        / total
                        * 100

                    )

                )


                # =====================================================
                # API DELAY
                # =====================================================

                if index < total - 1:

                    time.sleep(
                        UPLOAD_DELAY
                    )


            # ========================================================
            # FINISH
            # ========================================================

            status.empty()


            st.session_state.last_upload_result = (
                upload_results
            )


            # --------------------------------------------------------
            # CHỈ XÓA QUEUE
            # --------------------------------------------------------

            st.session_state.pending_upload_files = []


            # ========================================================
            # SUMMARY
            # ========================================================

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
                    f"mã hàng xử lý thất bại."

                )


            st.rerun()


    # ================================================================
    # UPLOAD RESULT REPORT
    # ================================================================

    if st.session_state.last_upload_result:

        st.divider()


        st.markdown(
            "### 📋 Kết quả nạp kho"
        )


        for item in (
            st.session_state.last_upload_result
        ):

            if item["status"] == "OK":

                st.success(

                    f"✅ `{item['product_code']}` — "
                    f"Kho: {item['category']} — "
                    f"AI: {item['ai_category']} — "
                    f"Confidence: "
                    f"{item['confidence']:.0f}% — "
                    f"Vector: "
                    f"{item['embedding_dim']}D"

                )

            else:

                st.error(

                    f"❌ `{item['product_code']}` — "
                    f"Kho: {item['category']} — "
                    f"Lỗi: {item['status']}"

                )


        # ============================================================
        # CLEAR REPORT
        # ============================================================

        if st.button(

            "🗑️ Xóa thông báo kết quả",

            key="clear_upload_result_report_v42"

        ):

            st.session_state.last_upload_result = None

            st.rerun()


# =====================================================================
# 39. FOOTER
# =====================================================================

st.divider()

st.caption(

    "AI Garment Similarity Search — "
    "Gemini Vision + Gemini Embedding 2 + "
    f"Supabase pgvector {EMBEDDING_DIMENSION}D — "
    f"{APP_VERSION}"

)
