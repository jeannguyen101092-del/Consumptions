# =====================================================================
# 🔍 AI TÌM KIẾM MÃ HÀNG TƯƠNG ĐỒNG
# FILE:
# 4_🔍_Tim_Kiem_Ma_Hang_Tuong_Dong.py
#
# VERSION V4.3
#
# =====================================================================
# MASTER FEATURES
#
# 1. AI tự nhận dạng garment
# 2. KHÔNG CHO USER CHỌN CATEGORY KHO THỦ CÔNG
# 3. AI CATEGORY = CATEGORY LƯU KHO
# 4. Gemini Vision
# 5. Gemini Embedding 2
# 6. Embedding 3072 DIMENSIONS
# 7. Supabase + pgvector
# 8. Supabase Storage
# 9. Upload hàng loạt
# 10. Search toàn bộ kho
# 11. Category chỉ dùng để BOOST, không khóa search
# 12. Retry chống 429 / 503
# 13. Delay chống quá tải Free Tier
# 14. Hỗ trợ SUPABASE_SERVICE_ROLE_KEY cho Storage RLS
# 15. Không xóa dữ liệu Supabase khi xóa hàng đợi
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

APP_VERSION = "V4.3"

# ---------------------------------------------------------------------
# SUPABASE
# ---------------------------------------------------------------------

BUCKET_NAME = "product-images"

PRODUCT_TABLE = "products"

MATCH_RPC_NAME = "match_products_v4"


# ---------------------------------------------------------------------
# GEMINI
# ---------------------------------------------------------------------

VISION_MODEL = "gemini-3.6-flash"

EMBEDDING_MODEL = "gemini-embedding-2"


# ---------------------------------------------------------------------
# IMPORTANT
#
# DATABASE CỦA BẠN ĐANG YÊU CẦU:
#
# expected 3072 dimensions
#
# Vì vậy KHÓA 3072.
# ---------------------------------------------------------------------

EMBEDDING_DIMENSION = 3072


# ---------------------------------------------------------------------
# SEARCH
# ---------------------------------------------------------------------

SEARCH_COUNT = 12

MIN_SIMILARITY = 0.35


# ---------------------------------------------------------------------
# API CONTROL
# ---------------------------------------------------------------------

GEMINI_RETRY_COUNT = 3

GEMINI_RETRY_DELAY = 5

UPLOAD_DELAY_SECONDS = 4.5


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

    "JUMPSUIT": "Áo liền quần",

    "ONE PIECE": "Áo liền quần",

    "ONE-PIECE": "Áo liền quần",

    "ONEPIECE": "Áo liền quần",

    "ROMPER": "Áo liền quần",

    "OVERALL": "Quần yếm",

    "OVERALLS": "Quần yếm",

    "BIB OVERALL": "Quần yếm",

    "BIB OVERALLS": "Quần yếm",

    "DUNGAREE": "Quần yếm",

    "DUNGAREES": "Quần yếm",

    "CARGO": "Quần túi hộp",

    "CARGO PANTS": "Quần túi hộp",

    "CARGO TROUSERS": "Quần túi hộp",

    "CARGO TROUSER": "Quần túi hộp",

    "UTILITY PANTS": "Quần túi hộp",

    "JEANS": "Quần jean",

    "JEAN": "Quần jean",

    "DENIM JEANS": "Quần jean",

    "DENIM PANTS": "Quần jean",

    "DENIM TROUSERS": "Quần jean",

    "JOGGER": "Quần jogger",

    "JOGGERS": "Quần jogger",

    "JOGGER PANTS": "Quần jogger",

    "SWEATPANTS": "Quần jogger",

    "SWEAT PANTS": "Quần jogger",

    "SHORT": "Quần short",

    "SHORTS": "Quần short",

    "PANTS": "Quần dài",

    "TROUSERS": "Quần dài",

    "TROUSER": "Quần dài",

    "LONG PANTS": "Quần dài",

    "SHIRT": "Áo",

    "TOP": "Áo",

    "BLOUSE": "Áo",

    "T-SHIRT": "T-shirt",

    "TSHIRT": "T-shirt",

    "TEE": "T-shirt",

    "POLO SHIRT": "Polo",

    "POLO": "Polo",

    "HOODIE": "Hoodie",

    "SWEATSHIRT": "Hoodie",

    "JACKET": "Jacket",

    "BOMBER": "Jacket",

    "OUTERWEAR": "Jacket",

    "COAT": "Jacket",

    "SKIRT": "Skirt",

    "DRESS": "Dress"

}


# =====================================================================
# 7. SECRET READER
# =====================================================================

def _safe_secret_get(
    container,
    key
):

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


# =====================================================================
# 8. RECURSIVE SECRET SEARCH
# =====================================================================

def _recursive_find_secret(
    obj,
    target_names
):

    if obj is None:

        return None

    try:

        if hasattr(
            obj,
            "items"
        ):

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


# =====================================================================
# 9. GET SECRET
# =====================================================================

def get_secret(
    *names
):

    normalized = {

        str(x)
        .upper()
        .strip()

        for x in names

    }

    # ---------------------------------------------------------------
    # STREAMLIT SECRETS
    # ---------------------------------------------------------------

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


    # ---------------------------------------------------------------
    # ENVIRONMENT VARIABLES
    # ---------------------------------------------------------------

    for name in normalized:

        value = os.environ.get(
            name
        )

        if value:

            return value.strip()


    return None


# =====================================================================
# 10. LOAD SECRETS
# =====================================================================

SUPABASE_URL = get_secret(

    "SUPABASE_URL",

    "supabase_url"

)


# ---------------------------------------------------------------------
# ANON / PUBLISHABLE KEY
# ---------------------------------------------------------------------

SUPABASE_KEY = get_secret(

    "SUPABASE_KEY",

    "SUPABASE_ANON_KEY",

    "supabase_key",

    "anon_key"

)


# ---------------------------------------------------------------------
# SERVICE ROLE KEY
#
# Dùng để bypass Storage RLS.
#
# Không bắt buộc nếu Storage Policy đã cho anon upload.
# ---------------------------------------------------------------------

SUPABASE_SERVICE_ROLE_KEY = get_secret(

    "SUPABASE_SERVICE_ROLE_KEY",

    "SUPABASE_SERVICE_KEY",

    "supabase_service_role_key",

    "service_role_key"

)


# ---------------------------------------------------------------------
# GEMINI
# ---------------------------------------------------------------------

GEMINI_API_KEY = get_secret(

    "GEMINI_API_KEY",

    "GOOGLE_API_KEY",

    "GEMINI_KEY",

    "gemini_api_key",

    "google_api_key",

    "api_key"

)


# =====================================================================
# 11. VALIDATE SECRETS
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
        "❌ Không đọc được thông tin bảo mật từ Streamlit Secrets."
    )

    st.markdown(
        "### Key đang thiếu:"
    )

    for key in missing_secrets:

        st.code(
            key,
            language="text"
        )


    st.info(
        """
Cấu hình trong Streamlit Secrets:

SUPABASE_URL = "https://xxxxx.supabase.co"

SUPABASE_KEY = "your-anon-key"

GEMINI_API_KEY = "your-gemini-key"

Nếu Storage báo lỗi 403 RLS, thêm:

SUPABASE_SERVICE_ROLE_KEY = "your-service-role-key"

Không đưa Service Role Key lên giao diện hoặc chia sẻ công khai.
"""
    )

    st.stop()


# =====================================================================
# 12. CREATE SUPABASE CLIENT
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
# 13. CREATE SUPABASE STORAGE ADMIN CLIENT
# =====================================================================
#
# Nếu có SERVICE ROLE KEY:
#
# upload Storage bằng admin client
#
# => không bị RLS INSERT.
#
# Nếu không có:
#
# dùng client thường.
#
# =====================================================================

supabase_storage = supabase


if SUPABASE_SERVICE_ROLE_KEY:

    try:

        supabase_storage = create_client(

            SUPABASE_URL,

            SUPABASE_SERVICE_ROLE_KEY

        )

    except Exception:

        supabase_storage = supabase


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
# 15. SESSION STATE
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
# 16. IMAGE MIME
# =====================================================================

def get_mime_type(
    filename
):

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
# 17. NORMALIZE IMAGE
# =====================================================================

def normalize_image_bytes(
    image_bytes
):

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
# 18. HASH
# =====================================================================

def calculate_file_hash(
    image_bytes
):

    return hashlib.sha256(
        image_bytes
    ).hexdigest()


# =====================================================================
# 19. PRODUCT CODE
# =====================================================================

def product_code_from_filename(
    filename
):

    name = filename.rsplit(
        ".",
        1
    )[0]

    name = str(
        name
    ).strip()

    return name.upper()


# =====================================================================
# 20. CATEGORY NORMALIZER
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

        if (
            value.lower()
            ==
            valid.lower()
        ):

            return valid


    # ---------------------------------------------------------------
    # PARTIAL MATCH
    # ---------------------------------------------------------------

    for alias, target in CATEGORY_ALIAS.items():

        if alias in upper:

            return target


    return "Quần dài"


# =====================================================================
# 21. GARMENT PROMPT
# =====================================================================

GARMENT_PROMPT = """

You are an expert apparel technical designer,
pattern technician and commercial garment recognition AI.

Analyze the garment shown in the image.

This system is used for:

COMMERCIAL APPAREL SIMILARITY SEARCH.

The goal is to identify the actual garment construction,
not merely superficial visual similarity.

=========================================================
CRITICAL CLASSIFICATION RULES
=========================================================

RULE 1 - JUMPSUIT / ONE PIECE
---------------------------------------------------------

If the upper body and lower body are physically connected
as ONE garment:

category = "Áo liền quần"

Do NOT classify as pants.

Do NOT classify as cargo pants.

If it is a true dress silhouette, classify as Dress instead.

---------------------------------------------------------

RULE 2 - BIB OVERALL
---------------------------------------------------------

If there is:

- bib front
- shoulder straps
- trouser body

category = "Quần yếm"

Do NOT classify as cargo pants.

---------------------------------------------------------

RULE 3 - CARGO PANTS
---------------------------------------------------------

Use:

category = "Quần túi hộp"

ONLY when the garment is a separate pants garment
AND there are obvious external cargo / patch pockets
attached to the side legs.

Do NOT classify ordinary pants with normal pockets as cargo.

Do NOT classify jumpsuits as cargo.

Do NOT classify overalls as cargo.

---------------------------------------------------------

RULE 4 - JEANS
---------------------------------------------------------

Separate pants made from denim.

category = "Quần jean"

---------------------------------------------------------

RULE 5 - JOGGER
---------------------------------------------------------

Separate pants with characteristic jogger construction.

Typical indicators:

- elastic ankle
- rib ankle cuff
- sweatpant construction
- tapered jogger silhouette

category = "Quần jogger"

---------------------------------------------------------

RULE 6 - SHORTS
---------------------------------------------------------

Separate pants with clearly short leg length.

category = "Quần short"

---------------------------------------------------------

RULE 7 - LONG PANTS
---------------------------------------------------------

Separate long trousers without strong cargo,
denim or jogger characteristics.

category = "Quần dài"

---------------------------------------------------------

RULE 8 - JACKET
---------------------------------------------------------

Separate upper-body outerwear.

Examples:

- bomber
- work jacket
- denim jacket
- padded jacket
- utility jacket

category = "Jacket"

---------------------------------------------------------

RULE 9 - DRESS
---------------------------------------------------------

One-piece dress silhouette.

A dress is NOT a jumpsuit.

category = "Dress"

---------------------------------------------------------

RULE 10 - T-SHIRT
---------------------------------------------------------

Basic knit short sleeve T-shirt.

category = "T-shirt"

---------------------------------------------------------

RULE 11 - POLO
---------------------------------------------------------

Polo construction with polo collar / placket.

category = "Polo"

---------------------------------------------------------

RULE 12 - HOODIE
---------------------------------------------------------

Upper body garment with hood.

category = "Hoodie"

---------------------------------------------------------

RULE 13 - SKIRT
---------------------------------------------------------

Separate lower-body skirt.

category = "Skirt"

---------------------------------------------------------

RULE 14 - SHIRT / TOP
---------------------------------------------------------

Upper body garment without strong hoodie,
polo or jacket characteristics.

category = "Áo"

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
ANALYZE THESE FEATURES
=========================================================

Look carefully at:

- garment boundaries
- upper/lower connection
- waistband
- fly
- leg construction
- pocket construction
- side cargo pockets
- bib
- straps
- sleeves
- collar
- hood
- cuffs
- ankle opening
- silhouette
- garment length
- denim appearance
- outerwear construction
- dress construction

=========================================================
IMPORTANT
=========================================================

Do NOT classify cargo merely because the garment has pockets.

Do NOT classify a jumpsuit as pants.

Do NOT classify an overall as cargo.

Do NOT classify a normal trouser as cargo.

Return ONLY JSON.

"""


# =====================================================================
# 22. BOOLEAN HELPER
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

        return bool(
            value
        )


    return False


# =====================================================================
# 23. NORMALIZE AI RESULT
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


    # ================================================================
    # HARD RULE 1
    # ================================================================

    if one_piece:

        if (
            bib
            and shoulder_straps
        ):

            category = "Quần yếm"

        else:

            category = "Áo liền quần"


    # ================================================================
    # HARD RULE 2
    # ================================================================

    elif (
        bib
        and shoulder_straps
    ):

        category = "Quần yếm"


    # ================================================================
    # HARD RULE 3
    # ================================================================

    elif category == "Quần túi hộp":

        if not cargo_pockets:

            category = "Quần dài"


    # ================================================================
    # HARD RULE 4
    # ================================================================

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


    # ================================================================
    # HARD RULE 5
    # ================================================================

    if (

        not one_piece

        and not bib

        and jogger_cuffs

        and category == "Quần dài"

    ):

        category = "Quần jogger"


    # ================================================================
    # CONFIDENCE
    # ================================================================

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


    # ================================================================
    # FINAL
    # ================================================================

    return {

        "category": category,

        "confidence": confidence,

        "one_piece": one_piece,

        "bib": bib,

        "shoulder_straps": shoulder_straps,

        "cargo_pockets": cargo_pockets,

        "denim": denim,

        "jogger_cuffs": jogger_cuffs,

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
# 24. GEMINI VISION WITH RETRY
# =====================================================================

def analyze_garment_with_gemini(
    image_bytes
):

    image_bytes = normalize_image_bytes(
        image_bytes
    )


    last_error = None


    for attempt in range(
        GEMINI_RETRY_COUNT
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
                    "Gemini không trả về kết quả."
                )


            # --------------------------------------------------------
            # PARSE JSON
            # --------------------------------------------------------

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


            if attempt < GEMINI_RETRY_COUNT - 1:

                time.sleep(
                    GEMINI_RETRY_DELAY
                )


    raise Exception(

        "Gemini Vision lỗi sau "
        f"{GEMINI_RETRY_COUNT} lần thử: "
        f"{last_error}"

    )


# =====================================================================
# 25. BUILD SEMANTIC TEXT
# =====================================================================
#
# QUAN TRỌNG:
#
# Warehouse và Search đều dùng CÙNG FORMAT TEXT.
#
# Không được warehouse dùng image vector,
# search dùng text vector.
#
# =====================================================================

def build_embedding_text(
    ai_result
):

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
        "cargo side pockets"
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
        "jogger ankle cuff"
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

Commercial apparel garment similarity representation.

Category:
{category}

Construction:
{one_piece}

Bib:
{bib}

Cargo pocket:
{cargo}

Denim:
{denim}

Jogger cuff:
{jogger}

Hood:
{hood}

Sleeve:
{sleeve}

Collar:
{collar}

Silhouette:
{silhouette}

Length:
{length}

Construction analysis:
{reason}

"""


    return text.strip()


# =====================================================================
# 26. TEXT EMBEDDING
# =====================================================================
#
# V4.3:
#
# LUÔN REQUEST 3072 DIMENSIONS.
#
# =====================================================================

def get_image_embedding(
    text_for_embedding
):

    if not text_for_embedding:

        text_for_embedding = (
            "commercial apparel garment"
        )


    last_error = None


    for attempt in range(
        GEMINI_RETRY_COUNT
    ):

        try:

            response = gemini_client.models.embed_content(

                model=EMBEDDING_MODEL,

                contents=text_for_embedding,

                config=types.EmbedContentConfig(

                    output_dimensionality=EMBEDDING_DIMENSION

                )

            )


            embeddings = getattr(

                response,

                "embeddings",

                None

            )


            if not embeddings:

                raise Exception(
                    "Gemini không trả embeddings."
                )


            values = getattr(

                embeddings[0],

                "values",

                None

            )


            if values is None:

                raise Exception(
                    "Embedding không có values."
                )


            values = [

                float(x)

                for x in values

            ]


            # --------------------------------------------------------
            # CRITICAL DIMENSION CHECK
            # --------------------------------------------------------

            if len(values) != EMBEDDING_DIMENSION:

                raise Exception(

                    f"Embedding sai dimension: "
                    f"{len(values)}. "
                    f"Database yêu cầu "
                    f"{EMBEDDING_DIMENSION}."

                )


            # --------------------------------------------------------
            # NORMALIZE
            # --------------------------------------------------------

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


            if attempt < GEMINI_RETRY_COUNT - 1:

                time.sleep(
                    GEMINI_RETRY_DELAY
                )


    raise Exception(

        "Gemini Embedding lỗi sau "
        f"{GEMINI_RETRY_COUNT} lần thử: "
        f"{last_error}"

    )


# =====================================================================
# 27. STORAGE PATH
# =====================================================================

def build_storage_path(
    image_bytes,
    filename
):

    safe_name = re.sub(

        r"[^A-Za-z0-9._-]",

        "_",

        filename

    )


    file_hash = calculate_file_hash(
        image_bytes
    )[:12]


    # ---------------------------------------------------------------
    # Hash + filename
    #
    # Tránh hai file cùng tên ghi đè nhau.
    # ---------------------------------------------------------------

    return (

        f"{file_hash}_"
        f"{safe_name}"

    )


# =====================================================================
# 28. UPLOAD IMAGE STORAGE
# =====================================================================

def upload_image_to_storage(
    image_bytes,
    filename
):

    path = build_storage_path(

        image_bytes,

        filename

    )


    mime_type = get_mime_type(
        filename
    )


    try:

        # ============================================================
        # UPLOAD
        # ============================================================

        supabase_storage.storage \

            .from_(BUCKET_NAME) \

            .upload(

                path=path,

                file=image_bytes,

                file_options={

                    "content-type": mime_type,

                    "upsert": "true",

                    "cache-control": "3600"

                }

            )


    except Exception as upload_error:

        upload_error_text = str(
            upload_error
        )


        # ============================================================
        # TRY UPDATE
        # ============================================================

        try:

            supabase_storage.storage \

                .from_(BUCKET_NAME) \

                .update(

                    path=path,

                    file=image_bytes,

                    file_options={

                        "content-type": mime_type,

                        "upsert": "true",

                        "cache-control": "3600"

                    }

                )


        except Exception as update_error:

            update_text = str(
                update_error
            )


            # --------------------------------------------------------
            # RLS MESSAGE
            # --------------------------------------------------------

            if (

                "row-level security"
                in upload_error_text.lower()

                or "403"
                in upload_error_text

                or "unauthorized"
                in upload_error_text.lower()

            ):

                raise Exception(

                    "Supabase Storage bị chặn bởi RLS 403.\n\n"

                    "Bucket: "
                    f"{BUCKET_NAME}\n\n"

                    "Cách 1 - Khuyến nghị:\n"
                    "Thêm SUPABASE_SERVICE_ROLE_KEY "
                    "vào Streamlit Secrets.\n\n"

                    "Cách 2:\n"
                    "Tạo Storage INSERT/UPDATE policy "
                    "cho bucket này.\n\n"

                    f"Upload error: {upload_error_text}\n\n"
                    f"Update error: {update_text}"

                )


            raise Exception(

                "Supabase Storage lỗi:\n"

                f"{upload_error_text}\n\n"

                f"Update fallback:\n"
                f"{update_text}"

            )


    # ================================================================
    # PUBLIC URL
    # ================================================================

    try:

        public_url = (

            supabase_storage.storage

            .from_(BUCKET_NAME)

            .get_public_url(path)

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
                "Public URL rỗng."
            )


        return public_url


    except Exception as e:

        raise Exception(

            "Upload thành công nhưng "
            "không lấy được Public URL: "
            + str(e)

        )


# =====================================================================
# 29. SAVE PRODUCT
# =====================================================================

def save_product(
    product_code,
    image_url,
    ai_category,
    ai_result,
    embedding,
    filename
):

    # ---------------------------------------------------------------
    # IMPORTANT:
    #
    # CATEGORY = AI CATEGORY
    #
    # Không còn category thủ công.
    # ---------------------------------------------------------------

    row = {

        "product_code":
            product_code,

        "image_url":
            image_url,

        "category":
            ai_category,

        "ai_category":
            ai_category,

        "embedding":
            embedding,

        "ai_analysis":
            ai_result,

        "file_name":
            filename

    }


    # ---------------------------------------------------------------
    # DIMENSION CHECK TRƯỚC DATABASE
    # ---------------------------------------------------------------

    if len(embedding) != EMBEDDING_DIMENSION:

        raise Exception(

            "Không lưu Database vì embedding "
            f"có {len(embedding)} chiều, "
            f"database yêu cầu "
            f"{EMBEDDING_DIMENSION}."

        )


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


        if (
            "expected 3072 dimensions"
            in error_text.lower()
        ):

            raise Exception(

                "Database đang yêu cầu 3072 dimensions "
                "nhưng vector truyền vào không đúng.\n\n"

                f"Embedding hiện tại: "
                f"{len(embedding)}\n"

                f"Database: {EMBEDDING_DIMENSION}\n\n"

                f"Chi tiết: {error_text}"

            )


        raise Exception(

            "Database save lỗi: "
            + error_text

        )


# =====================================================================
# 30. SEARCH SIMILAR PRODUCTS
# =====================================================================

def search_similar_products(
    embedding,
    match_count=SEARCH_COUNT
):

    if len(embedding) != EMBEDDING_DIMENSION:

        raise Exception(

            "Không search được vì embedding có "
            f"{len(embedding)} chiều. "
            f"Yêu cầu {EMBEDDING_DIMENSION}."

        )


    try:

        response = supabase.rpc(

            MATCH_RPC_NAME,

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

        raise Exception(

            "Supabase similarity search lỗi: "
            + str(e)

        )


# =====================================================================
# 31. DISPLAY SCORE
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


    # ---------------------------------------------------------------
    # CATEGORY BOOST
    #
    # KHÔNG LOẠI RECORD.
    # ---------------------------------------------------------------

    if query_category == db_category:

        score += 0.08

    elif query_category == ai_category:

        score += 0.05


    return score


# =====================================================================
# 32. RANK RESULTS
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
# 33. HEADER
# =====================================================================

st.title(
    "🔍 AI TÌM KIẾM MÃ HÀNG TƯƠNG ĐỒNG"
)


st.caption(

    "AI Garment Recognition + "
    "Gemini Embedding 2 + "
    "Supabase pgvector — "
    f"{APP_VERSION}"

)


# =====================================================================
# 34. SYSTEM STATUS
# =====================================================================

with st.expander(
    "⚙️ Trạng thái hệ thống",
    expanded=False
):

    c1, c2, c3, c4 = st.columns(4)


    with c1:

        st.metric(
            "Embedding",
            f"{EMBEDDING_DIMENSION}D"
        )


    with c2:

        st.metric(
            "AI Vision",
            VISION_MODEL
        )


    with c3:

        st.metric(
            "Embedding Model",
            EMBEDDING_MODEL
        )


    with c4:

        if SUPABASE_SERVICE_ROLE_KEY:

            st.success(
                "Storage Admin: ON"
            )

        else:

            st.warning(
                "Storage Admin: OFF"
            )


# =====================================================================
# 35. TABS
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


    # ================================================================
    # FILE UPLOADER
    # ================================================================

    search_file = st.file_uploader(

        "📷 Tải ảnh Sketch / ảnh mẫu cần tìm",

        type=[

            "jpg",
            "jpeg",
            "png",
            "webp"

        ],

        key="v43_search_uploader"

    )


    # ================================================================
    # CLEAR
    # ================================================================

    clear_col, _ = st.columns(
        [1, 5]
    )


    with clear_col:

        if st.button(

            "🗑️ Xóa ảnh hiện tại",

            key="v43_clear_search"

        ):

            st.session_state.search_file = None

            st.session_state.search_result = None

            st.session_state.search_ai_result = None

            st.rerun()


    # ================================================================
    # SEARCH
    # ================================================================

    if search_file is not None:

        image_bytes = search_file.getvalue()


        st.session_state.search_file = (
            image_bytes
        )


        col1, col2 = st.columns(
            [1, 2]
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
        # AI
        # ------------------------------------------------------------

        with col2:

            st.markdown(
                "### 🤖 AI nhận dạng"
            )


            if st.button(

                "🚀 PHÂN TÍCH & TÌM MÃ TƯƠNG ĐỒNG",

                type="primary",

                use_container_width=True,

                key="v43_run_search"

            ):

                try:

                    # =================================================
                    # STEP 1 - VISION
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
                    # STEP 2 - BUILD TEXT
                    # =================================================

                    embedding_text = (
                        build_embedding_text(
                            ai_result
                        )
                    )


                    # =================================================
                    # STEP 3 - EMBEDDING
                    # =================================================

                    with st.spinner(

                        "🧠 Đang tạo vector 3072 chiều..."

                    ):

                        query_embedding = (
                            get_image_embedding(
                                embedding_text
                            )
                        )


                    # =================================================
                    # STEP 4 - SEARCH
                    # =================================================

                    with st.spinner(

                        "🔎 Đang đối chiếu kho hàng..."

                    ):

                        results = (
                            search_similar_products(
                                query_embedding
                            )
                        )


                    # =================================================
                    # STEP 5 - RANK
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
                        f"Đã tìm thấy {len(results)} mã tương đồng."
                    )


                except Exception as e:

                    st.error(
                        f"❌ Lỗi hệ thống: {str(e)}"
                    )


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


        c1, c2, c3, c4 = st.columns(4)


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

                else

                "NO"

            )


        with c4:

            st.metric(

                "Cargo Pocket",

                "YES"

                if ai_result.get(
                    "cargo_pockets",
                    False
                )

                else

                "NO"

            )


        # ------------------------------------------------------------
        # DETAIL
        # ------------------------------------------------------------

        if ai_result.get(
            "reason"
        ):

            st.info(

                "🧠 "
                + ai_result[
                    "reason"
                ]

            )


        with st.expander(
            "🔬 Chi tiết AI"
        ):

            st.json(
                ai_result
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

                "Không tìm thấy mã hàng tương đồng "
                "trong kho."

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
                                "Không tải được ảnh."
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


                    # ------------------------------------------------
                    # DISPLAY SCORE
                    # ------------------------------------------------

                    st.caption(

                        "Điểm xếp hạng: "

                        f"{display_score * 100:.2f}%"

                    )


                    # ------------------------------------------------
                    # CATEGORY
                    # ------------------------------------------------

                    st.write(

                        "📦 Category:",

                        item.get(
                            "category",
                            "N/A"
                        )

                    )


                    st.write(

                        "🤖 AI Category:",

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

        "🤖 Không cần chọn dòng hàng thủ công. "
        "AI sẽ tự nhận dạng Category và lưu "
        "Category AI đó vào kho."

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

        key="v43_storage_uploader"

    )


    # ================================================================
    # ADD FILES TO QUEUE
    # ================================================================

    if uploaded_files:

        existing_keys = {

            (
                f.name,
                getattr(
                    f,
                    "size",
                    0
                )

            )

            for f in st.session_state
            .pending_upload_files

        }


        for file in uploaded_files:

            file_key = (

                file.name,

                getattr(
                    file,
                    "size",
                    0
                )

            )


            if file_key not in existing_keys:

                st.session_state \
                    .pending_upload_files \
                    .append(file)


                existing_keys.add(
                    file_key
                )


    # ================================================================
    # CLEAR QUEUE
    # ================================================================

    c1, _ = st.columns(
        [1, 5]
    )


    with c1:

        if st.button(

            "🗑️ Xóa danh sách chờ",

            key="v43_clear_pending"

        ):

            st.session_state.pending_upload_files = []

            st.rerun()


    # ================================================================
    # PENDING
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

                st.image(

                    file,

                    caption=file.name,

                    use_container_width=True

                )


        st.divider()


        # ============================================================
        # START
        # ============================================================

        if st.button(

            "📤 BẮT ĐẦU AI PHÂN TÍCH & NẠP TOÀN BỘ",

            type="primary",

            use_container_width=True,

            key="v43_start_storage"

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
            # LOOP
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

                    f"⏳ "
                    f"{index + 1}/{total} "
                    f"— `{product_code}`"

                )


                try:

                    image_bytes = (
                        file.getvalue()
                    )


                    # =================================================
                    # STEP 1 - VISION
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


                    ai_category = (
                        ai_result[
                            "category"
                        ]
                    )


                    # =================================================
                    # STEP 2 - SEMANTIC TEXT
                    # =================================================

                    status.write(

                        f"📝 Chuẩn bị đặc trưng "
                        f"`{product_code}`..."

                    )


                    embedding_text = (
                        build_embedding_text(
                            ai_result
                        )
                    )


                    # =================================================
                    # STEP 3 - EMBEDDING 3072
                    # =================================================

                    status.write(

                        f"🧠 Tạo embedding 3072D "
                        f"`{product_code}`..."

                    )


                    embedding = (
                        get_image_embedding(
                            embedding_text
                        )
                    )


                    # =================================================
                    # STEP 4 - STORAGE
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
                    # STEP 5 - DATABASE
                    # =================================================

                    status.write(

                        f"💾 Lưu Database "
                        f"`{product_code}`..."

                    )


                    save_product(

                        product_code=product_code,

                        image_url=image_url,

                        ai_category=ai_category,

                        ai_result=ai_result,

                        embedding=embedding,

                        filename=file.name

                    )


                    # =================================================
                    # SUCCESS
                    # =================================================

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

                    # =================================================
                    # FAILED
                    # =================================================

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
                # DELAY
                # =====================================================

                if index < total - 1:

                    time.sleep(
                        UPLOAD_DELAY_SECONDS
                    )


            # ==========================================================
            # FINISH
            # ==========================================================

            status.empty()


            st.session_state.last_upload_result = (
                upload_results
            )


            # ----------------------------------------------------------
            # CHỈ XÓA HÀNG ĐỢI
            # ----------------------------------------------------------

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
                    f"file lỗi."

                )


            # ----------------------------------------------------------
            # Không rerun ngay.
            #
            # Để người dùng nhìn thấy kết quả.
            # ----------------------------------------------------------

            st.rerun()


    # ================================================================
    # UPLOAD LOG
    # ================================================================

    if st.session_state.last_upload_result:

        st.divider()


        st.markdown(
            "### 📋 Kết quả nạp kho"
        )


        for item in (
            st.session_state.last_upload_result
        ):

            if item[
                "status"
            ] == "OK":

                st.success(

                    f"✅ "
                    f"{item['product_code']} — "

                    f"AI: "
                    f"{item['ai_category']} — "

                    f"Độ tự tin: "
                    f"{float(item['confidence']):.0f}%"

                )

            else:

                st.error(

                    f"❌ "
                    f"{item['product_code']} — "

                    f"{item['status']}"

                )


        if st.button(

            "🗑️ Xóa thông báo kết quả",

            key="v43_clear_upload_report"

        ):

            st.session_state.last_upload_result = None

            st.rerun()


# =====================================================================
# 36. FOOTER
# =====================================================================

st.divider()


st.caption(

    "AI Garment Similarity Search "
    "— V4.3 — "
    "Gemini Vision + Gemini Embedding 2 "
    "(3072D) + Supabase pgvector"

)
