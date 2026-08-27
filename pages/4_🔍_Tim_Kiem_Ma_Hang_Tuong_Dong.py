# =====================================================================
# 🔍 AI TÌM KIẾM MÃ HÀNG TƯƠNG ĐỒNG
# VERSION V4.2
#
# MASTER VERSION
#
# ENGINE:
#   - Gemini Vision
#   - Gemini Embedding
#   - Supabase
#   - pgvector
#
# V4.2 CHANGES:
#   - XÓA HOÀN TOÀN CATEGORY NHẬP THỦ CÔNG
#   - AI TỰ NHẬN DIỆN CATEGORY
#   - CATEGORY DATABASE = AI CATEGORY
#   - EMBEDDING = 3072 DIMENSIONS
#   - SEARCH / UPLOAD DÙNG CÙNG EMBEDDING PIPELINE
#   - RETRY 429 / 503
#   - KHÔNG DÙNG VECTOR GIẢ
#   - KHÔNG KHÓA SEARCH THEO CATEGORY
#   - UPLOAD HÀNG LOẠT
#   - PRODUCT CODE = TÊN FILE
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
        "❌ Chưa cài thư viện supabase.\n\n"
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

APP_VERSION = "V4.2"

BUCKET_NAME = "product-images"

PRODUCT_TABLE = "products"

# ---------------------------------------------------------
# Gemini Vision
# ---------------------------------------------------------

VISION_MODEL = "gemini-3.6-flash"

# ---------------------------------------------------------
# Gemini Embedding
# ---------------------------------------------------------

EMBEDDING_MODEL = "gemini-embedding-2"

# ---------------------------------------------------------
# QUAN TRỌNG
#
# Supabase pgvector của bạn đang yêu cầu:
#
# expected 3072 dimensions
#
# Vì vậy BẮT BUỘC:
# 3072
# ---------------------------------------------------------

EMBEDDING_DIMENSION = 3072

# ---------------------------------------------------------
# Search
# ---------------------------------------------------------

SEARCH_COUNT = 12

MIN_SIMILARITY = 0.35


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
# 6. SECRET READER
# =====================================================================

def _safe_secret_get(container, key):

    try:

        if container is None:
            return None

        if key in container:

            value = container[key]

            if value is not None:

                return str(value).strip()

    except Exception:

        pass

    return None


# ---------------------------------------------------------------------
# Recursive secret finder
# ---------------------------------------------------------------------

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

                        return str(
                            value
                        ).strip()

                result = _recursive_find_secret(
                    value,
                    target_names
                )

                if result:

                    return result

    except Exception:

        pass

    return None


# ---------------------------------------------------------------------
# Main secret reader
# ---------------------------------------------------------------------

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

        value = os.environ.get(
            name
        )

        if value:

            return value.strip()


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
        "### Các key còn thiếu:"
    )

    for key in missing_secrets:

        st.code(
            key,
            language="text"
        )

    st.info(
        """
Cấu hình Streamlit Secrets:

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
        "❌ Không kết nối được Supabase."
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
# 12. IMAGE HELPERS
# =====================================================================

def get_mime_type(filename):

    ext = (

        filename
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


# ---------------------------------------------------------------------
# Normalize image
# ---------------------------------------------------------------------

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
# 13. FILE HASH
# =====================================================================

def calculate_file_hash(
    image_bytes
):

    return hashlib.sha256(
        image_bytes
    ).hexdigest()


# =====================================================================
# 14. GARMENT PROMPT
# =====================================================================

GARMENT_PROMPT = """

You are an expert apparel technical designer
and commercial garment recognition AI.

Analyze the garment shown in the image.

This system is used for commercial apparel
similarity search.

You MUST identify garment construction,
not just superficial appearance.

=========================================================
CRITICAL CLASSIFICATION RULES
=========================================================

1. JUMPSUIT / ONE PIECE

If upper body and lower body are physically
connected into one garment:

category = "Áo liền quần"

Do NOT classify it as pants.

---------------------------------------------------------

2. BIB OVERALL

If garment has:

- bib front
- shoulder straps
- trouser body

category = "Quần yếm"

Do NOT classify it as cargo pants.

---------------------------------------------------------

3. CARGO PANTS

Only classify as:

"Quần túi hộp"

when it is a separate pants garment
AND has obvious external cargo / patch pockets
on the side legs.

Do NOT classify ordinary trousers as cargo.

Do NOT classify jumpsuits as cargo.

Do NOT classify overalls as cargo.

---------------------------------------------------------

4. JEANS

Separate pants made from denim.

category = "Quần jean"

---------------------------------------------------------

5. JOGGER

Separate pants with characteristic jogger
construction, especially elastic or rib ankle cuffs.

category = "Quần jogger"

---------------------------------------------------------

6. SHORTS

Separate pants with short leg length.

category = "Quần short"

---------------------------------------------------------

7. LONG PANTS

Separate long trousers without strong cargo,
denim, or jogger construction.

category = "Quần dài"

---------------------------------------------------------

8. JACKET

Separate upper-body outerwear garment.

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

category = "T-shirt"

---------------------------------------------------------

12. POLO

category = "Polo"

---------------------------------------------------------

13. HOODIE

category = "Hoodie"

---------------------------------------------------------

14. SKIRT

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

- garment boundaries
- upper/lower body connection
- waistband
- leg construction
- cargo pockets
- patch pockets
- bib
- straps
- sleeves
- collar
- hood
- cuffs
- silhouette
- garment length
- denim appearance

Do NOT guess cargo simply because the garment
has ordinary pockets.

Return ONLY JSON.

"""


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


    upper = value.upper()


    if upper in CATEGORY_ALIAS:

        return CATEGORY_ALIAS[
            upper
        ]


    for valid in CATEGORY_OPTIONS:

        if value.lower() == valid.lower():

            return valid


    # ---------------------------------------------------------
    # fuzzy keyword
    # ---------------------------------------------------------

    if "cargo" in upper:

        return "Quần túi hộp"

    if "jean" in upper or "denim" in upper:

        return "Quần jean"

    if "jogger" in upper:

        return "Quần jogger"

    if "short" in upper:

        return "Quần short"

    if "jacket" in upper:

        return "Jacket"

    if "hoodie" in upper:

        return "Hoodie"

    if "polo" in upper:

        return "Polo"

    if "t-shirt" in upper or "tshirt" in upper:

        return "T-shirt"

    if "shirt" in upper:

        return "Áo"

    if "dress" in upper:

        return "Dress"

    if "skirt" in upper:

        return "Skirt"


    return "Quần dài"


# =====================================================================
# 16. BOOL NORMALIZER
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
                "1"

            ]

        )


    if isinstance(
        value,
        (int, float)
    ):

        return bool(
            value
        )


    return False


# =====================================================================
# 17. NORMALIZE AI RESULT
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
    # ONE PIECE
    # =========================================================

    if one_piece:

        if bib and shoulder_straps:

            category = "Quần yếm"

        else:

            category = "Áo liền quần"


    # =========================================================
    # HARD RULE 2
    # BIB
    # =========================================================

    elif bib and shoulder_straps:

        category = "Quần yếm"


    # =========================================================
    # HARD RULE 3
    # CARGO
    # =========================================================

    elif category == "Quần túi hộp":

        if not cargo_pockets:

            category = "Quần dài"


    # =========================================================
    # HARD RULE 4
    # DENIM
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
    # JOGGER
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


    # =========================================================
    # FINAL
    # =========================================================

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
# 18. GEMINI VISION
# =====================================================================

def analyze_garment_with_gemini(
    image_bytes
):

    image_bytes = normalize_image_bytes(
        image_bytes
    )


    max_retries = 3


    last_error = None


    for attempt in range(
        max_retries
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

                    config=(
                        types
                        .GenerateContentConfig(

                            response_mime_type=(
                                "application/json"
                            ),

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
            )


            text = getattr(
                response,
                "text",
                None
            )


            if not text:

                raise Exception(
                    "Gemini không trả về kết quả."
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


            retryable = (

                "429" in error_text

                or "503" in error_text

                or "resource exhausted"
                in error_text

                or "unavailable"
                in error_text

                or "timeout"
                in error_text

            )


            if (

                retryable
                and attempt < max_retries - 1

            ):

                time.sleep(
                    4 * (attempt + 1)
                )

                continue


            break


    raise Exception(

        "Gemini Vision lỗi: "
        + str(last_error)

    )


# =====================================================================
# 19. BUILD SEMANTIC TEXT
# =====================================================================

def build_embedding_text(
    ai_result
):

    """

    Tạo text mô tả garment thống nhất.

    SEARCH và STORAGE phải dùng cùng format.

    """

    category = ai_result.get(
        "category",
        ""
    )


    reason = ai_result.get(
        "reason",
        ""
    )


    sleeve = ai_result.get(
        "sleeve",
        ""
    )


    collar = ai_result.get(
        "collar",
        ""
    )


    silhouette = ai_result.get(
        "silhouette",
        ""
    )


    length = ai_result.get(
        "length",
        ""
    )


    one_piece = (

        "one piece"
        if ai_result.get(
            "one_piece",
            False
        )
        else "separate garment"

    )


    bib = (

        "bib overall"
        if ai_result.get(
            "bib",
            False
        )
        else ""

    )


    cargo = (

        "cargo pockets"
        if ai_result.get(
            "cargo_pockets",
            False
        )
        else ""

    )


    denim = (

        "denim"
        if ai_result.get(
            "denim",
            False
        )
        else ""

    )


    jogger = (

        "jogger cuffs"
        if ai_result.get(
            "jogger_cuffs",
            False
        )
        else ""

    )


    hood = (

        "hood"
        if ai_result.get(
            "hood",
            False
        )
        else ""

    )


    text = f"""
Commercial apparel garment similarity description.

Category: {category}

Construction: {one_piece}

Bib: {bib}

Cargo pockets: {cargo}

Denim: {denim}

Jogger cuffs: {jogger}

Hood: {hood}

Sleeve: {sleeve}

Collar: {collar}

Silhouette: {silhouette}

Length: {length}

Technical visual description:
{reason}
"""


    return text.strip()


# =====================================================================
# 20. GEMINI TEXT EMBEDDING
# =====================================================================

def get_text_embedding(
    text
):

    if not text:

        raise Exception(
            "Không có text để tạo embedding."
        )


    max_retries = 3

    last_error = None


    for attempt in range(
        max_retries
    ):

        try:

            response = (

                gemini_client
                .models
                .embed_content(

                    model=EMBEDDING_MODEL,

                    contents=text,

                    config=(
                        types
                        .EmbedContentConfig(

                            output_dimensionality=(
                                EMBEDDING_DIMENSION
                            )

                        )
                    )

                )

            )


            if not getattr(
                response,
                "embeddings",
                None
            ):

                raise Exception(
                    "Gemini không trả embedding."
                )


            values = (
                response
                .embeddings[0]
                .values
            )


            if not values:

                raise Exception(
                    "Embedding rỗng."
                )


            values = [

                float(x)

                for x in values

            ]


            # -------------------------------------------------
            # CHECK DIMENSION
            # -------------------------------------------------

            actual_dimension = len(
                values
            )


            if actual_dimension != EMBEDDING_DIMENSION:

                raise Exception(

                    f"Embedding dimension sai: "
                    f"Gemini trả {actual_dimension}, "
                    f"nhưng hệ thống yêu cầu "
                    f"{EMBEDDING_DIMENSION}."

                )


            # -------------------------------------------------
            # NORMALIZE VECTOR
            # -------------------------------------------------

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


        except Exception as e:

            last_error = e

            error_text = str(e).lower()


            retryable = (

                "429" in error_text

                or "503" in error_text

                or "resource exhausted"
                in error_text

                or "unavailable"
                in error_text

                or "timeout"
                in error_text

            )


            if (

                retryable
                and attempt < max_retries - 1

            ):

                time.sleep(
                    4 * (attempt + 1)
                )

                continue


            break


    raise Exception(

        "Gemini Text Embedding lỗi: "
        + str(last_error)

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


    path = safe_name


    mime_type = get_mime_type(
        filename
    )


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


    except Exception as e:

        raise Exception(

            "Supabase Storage lỗi: "
            + str(e)

        )


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

                or public_url.get(
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

    # ---------------------------------------------------------
    # SAFETY CHECK
    # ---------------------------------------------------------

    if len(embedding) != EMBEDDING_DIMENSION:

        raise Exception(

            f"Không thể lưu Database: "
            f"embedding có {len(embedding)} chiều, "
            f"Database yêu cầu {EMBEDDING_DIMENSION}."

        )


    # ---------------------------------------------------------
    # IMPORTANT
    #
    # category = AI category
    #
    # KHÔNG còn category nhập thủ công.
    # ---------------------------------------------------------

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

    if len(embedding) != EMBEDDING_DIMENSION:

        raise Exception(

            f"Search embedding sai dimension: "
            f"{len(embedding)}. "
            f"Database yêu cầu "
            f"{EMBEDDING_DIMENSION}."

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

        raise Exception(

            "Supabase similarity search lỗi: "
            + str(e)

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


    # ---------------------------------------------------------
    # CATEGORY CHỈ BOOST
    #
    # KHÔNG FILTER
    # ---------------------------------------------------------

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
            x.get(
                "display_score",
                0
            ),

        reverse=True

    )


    return enriched


# =====================================================================
# 26. PRODUCT CODE
# =====================================================================

def product_code_from_filename(
    filename
):

    name = filename.rsplit(
        ".",
        1
    )[0]


    return str(
        name
    ).strip().upper()


# =====================================================================
# 27. HEADER
# =====================================================================

st.title(
    "🔍 AI TÌM KIẾM MÃ HÀNG TƯƠNG ĐỒNG"
)


st.caption(

    "AI Garment Recognition + "
    "Gemini Embedding + "
    "Supabase pgvector — "
    f"{APP_VERSION}"

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
        "AI tự nhận dạng garment và "
        "tìm trên toàn bộ kho."

    )


    # ---------------------------------------------------------
    # FILE UPLOAD
    # ---------------------------------------------------------

    search_file = st.file_uploader(

        "📷 Tải ảnh Sketch / ảnh mẫu cần tìm",

        type=[

            "jpg",
            "jpeg",
            "png",
            "webp"

        ],

        key="search_uploader"

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

            key="clear_search_file"

        ):

            st.session_state.search_file = None

            st.session_state.search_result = None

            st.session_state.search_ai_result = None

            st.rerun()


    # ---------------------------------------------------------
    # PROCESS SEARCH IMAGE
    # ---------------------------------------------------------

    if search_file is not None:

        image_bytes = search_file.getvalue()


        st.session_state.search_file = (
            image_bytes
        )


        col1, col2 = st.columns(
            [1, 2]
        )


        # -----------------------------------------------------
        # IMAGE
        # -----------------------------------------------------

        with col1:

            st.image(

                image_bytes,

                caption=search_file.name,

                use_container_width=True

            )


        # -----------------------------------------------------
        # AI
        # -----------------------------------------------------

        with col2:

            st.markdown(
                "### 🤖 AI nhận dạng"
            )


            if st.button(

                "🚀 PHÂN TÍCH & TÌM MÃ TƯƠNG ĐỒNG",

                type="primary",

                use_container_width=True,

                key="run_search"

            ):

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

                    text_for_embedding = (
                        build_embedding_text(
                            ai_result
                        )
                    )


                    # =================================================
                    # STEP 3
                    # EMBEDDING 3072
                    # =================================================

                    with st.spinner(

                        "🧠 Đang tạo embedding 3072 chiều..."

                    ):

                        query_embedding = (
                            get_text_embedding(
                                text_for_embedding
                            )
                        )


                    # =================================================
                    # STEP 4
                    # VECTOR SEARCH
                    # =================================================

                    with st.spinner(

                        "🔎 Đang tìm mã tương đồng trong kho..."

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


                except Exception as e:

                    st.error(
                        f"❌ Lỗi hệ thống: {str(e)}"
                    )


    # ---------------------------------------------------------
    # AI RESULT
    # ---------------------------------------------------------

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


    # ---------------------------------------------------------
    # SEARCH RESULT
    # ---------------------------------------------------------

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


                    # IMAGE
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

                            pass


                    # PRODUCT CODE
                    st.markdown(

                        f"### 🏷️ "
                        f"{item.get('product_code', 'N/A')}"

                    )


                    # SIMILARITY
                    try:

                        similarity = float(

                            item.get(
                                "similarity",
                                0
                            )

                        )

                    except Exception:

                        similarity = 0


                    st.metric(

                        "Độ tương đồng",

                        f"{similarity * 100:.2f}%"

                    )


                    # DISPLAY SCORE
                    try:

                        display_score = float(

                            item.get(
                                "display_score",
                                similarity
                            )

                        )

                    except Exception:

                        display_score = similarity


                    st.caption(

                        f"Điểm xếp hạng: "
                        f"{display_score * 100:.2f}%"

                    )


                    # CATEGORY
                    st.write(

                        "📦 Category:",

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

        "🤖 Không cần chọn dòng hàng. "
        "AI sẽ tự nhận diện Category cho từng ảnh "
        "và tự lưu Category vào kho."

    )


    # =========================================================
    # KHÔNG CÒN:
    #
    # storage_category = st.selectbox(...)
    #
    # =========================================================


    # ---------------------------------------------------------
    # FILE UPLOADER
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

        key="storage_uploader"

    )


    # ---------------------------------------------------------
    # ADD NEW FILES TO QUEUE
    # ---------------------------------------------------------

    if uploaded_files:

        current_names = [

            f.name

            for f in (
                st.session_state
                .pending_upload_files
            )

        ]


        for file in uploaded_files:

            if file.name not in current_names:

                st.session_state \
                    .pending_upload_files \
                    .append(file)


    # ---------------------------------------------------------
    # CLEAR PENDING
    # ---------------------------------------------------------

    c1, _ = st.columns(
        [1, 5]
    )


    with c1:

        if st.button(

            "🗑️ Xóa danh sách chờ",

            key="clear_pending_files"

        ):

            st.session_state.pending_upload_files = []

            st.rerun()


    # ---------------------------------------------------------
    # PENDING FILES
    # ---------------------------------------------------------

    pending_files = (

        st.session_state
        .pending_upload_files

    )


    if pending_files:

        st.success(

            f"📂 Đang chờ "
            f"**{len(pending_files)}** "
            f"file để nạp kho."

        )


        # -----------------------------------------------------
        # PREVIEW
        # -----------------------------------------------------

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


        # -----------------------------------------------------
        # START UPLOAD
        # -----------------------------------------------------

        if st.button(

            "📤 BẮT ĐẦU NẠP TOÀN BỘ VÀO KHO",

            type="primary",

            use_container_width=True,

            key="start_storage_upload"

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

                    f"⏳ {index + 1}/{total} "
                    f"— Mã hàng: `{product_code}`"

                )


                try:

                    image_bytes = (
                        file.getvalue()
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


                    ai_category = (

                        ai_result[
                            "category"
                        ]

                    )


                    # =========================================
                    # STEP 2
                    # BUILD SEMANTIC TEXT
                    # =========================================

                    text_for_embedding = (

                        build_embedding_text(

                            ai_result

                        )

                    )


                    # =========================================
                    # STEP 3
                    # EMBEDDING 3072
                    # =========================================

                    status.write(

                        f"🧠 Đang tạo embedding "
                        f"3072 chiều cho `{product_code}`..."

                    )


                    embedding = (

                        get_text_embedding(

                            text_for_embedding

                        )

                    )


                    # =========================================
                    # STEP 4
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
                    # STEP 5
                    # DATABASE
                    # =========================================

                    status.write(

                        f"💾 Lưu Database "
                        f"`{product_code}`..."

                    )


                    # -------------------------------------------------
                    # QUAN TRỌNG:
                    #
                    # category = AI CATEGORY
                    #
                    # Không còn storage_category.
                    # -------------------------------------------------

                    save_product(

                        product_code=
                            product_code,

                        image_url=
                            image_url,

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


                    success_count += 1


                    upload_results.append({

                        "product_code":
                            product_code,

                        "category":
                            ai_category,

                        "ai_category":
                            ai_category,

                        "confidence":
                            ai_result.get(
                                "confidence",
                                0
                            ),

                        "status":
                            "OK"

                    })


                except Exception as e:

                    failed_count += 1


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
                            str(e)

                    })


                    st.error(

                        f"❌ `{file.name}` — "
                        f"{str(e)}"

                    )


                # -------------------------------------------------
                # PROGRESS
                # -------------------------------------------------

                progress.progress(

                    int(

                        (
                            index + 1
                        )
                        / total
                        * 100

                    )

                )


                # -------------------------------------------------
                # API DELAY
                # -------------------------------------------------

                if index < total - 1:

                    time.sleep(
                        4.5
                    )


            # =================================================
            # FINISH
            # =================================================

            status.empty()


            st.session_state.last_upload_result = (
                upload_results
            )


            # -------------------------------------------------
            # CLEAR QUEUE
            # -------------------------------------------------

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


            # -------------------------------------------------
            # RERUN
            # -------------------------------------------------

            st.rerun()


    # ---------------------------------------------------------
    # UPLOAD RESULT LOG
    # ---------------------------------------------------------

    if st.session_state.last_upload_result:

        st.divider()


        st.markdown(
            "### 📋 Kết quả nạp kho"
        )


        for item in (

            st.session_state
            .last_upload_result

        ):

            if item["status"] == "OK":

                st.success(

                    f"✅ "
                    f"{item['product_code']} — "
                    f"Category AI: "
                    f"{item['ai_category']} — "
                    f"Confidence: "
                    f"{float(item['confidence']):.0f}%"

                )

            else:

                st.error(

                    f"❌ "
                    f"{item['product_code']} — "
                    f"Lỗi: "
                    f"{item['status']}"

                )


        # -----------------------------------------------------
        # CLEAR REPORT
        # -----------------------------------------------------

        if st.button(

            "🗑️ Xóa thông báo kết quả",

            key="clear_upload_result_report"

        ):

            st.session_state.last_upload_result = None

            st.rerun()


# =====================================================================
# 29. FOOTER
# =====================================================================

st.divider()


st.caption(

    "AI Garment Similarity Search — "
    "Gemini Vision + Gemini Embedding + "
    "Supabase pgvector — V4.2"

)
