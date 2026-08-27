# =====================================================================
# 🔍 AI TÌM KIẾM MÃ HÀNG TƯƠNG ĐỒNG
# VERSION V4.3
#
# MASTER VERSION
#
# ENGINE:
#   - Gemini Vision
#   - Gemini Embedding 2 MULTIMODAL
#   - Supabase Storage
#   - Supabase PostgreSQL + pgvector
#
# IMPORTANT:
#   - KHÔNG chọn category thủ công khi nạp kho
#   - AI tự nhận diện category
#   - Embedding = IMAGE + AI DESCRIPTION
#   - EMBEDDING_DIMENSION = 3072
#   - Phù hợp database vector(3072)
#   - Không dùng HuggingFace
#   - Không dùng CLIP
#   - Không dùng torch
#   - Không dùng torchvision
#
# TAB 1:
#   🔍 Tìm kiếm mã hàng tương đồng
#
# TAB 2:
#   📦 Nạp kho hàng loạt
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

APP_VERSION = "V4.3"

BUCKET_NAME = "product-images"

PRODUCT_TABLE = "products"

RPC_SEARCH_FUNCTION = "match_products_v4"

VISION_MODEL = "gemini-3.6-flash"

EMBEDDING_MODEL = "gemini-embedding-2"

# ================================================================
# QUAN TRỌNG
#
# Database hiện tại của bạn báo:
#
# expected 3072 dimensions, not 768
#
# Vì vậy phải dùng 3072.
# ================================================================

EMBEDDING_DIMENSION = 3072

SEARCH_COUNT = 12

MIN_SIMILARITY = 0.25

MAX_DISPLAY_RESULTS = 8

API_RETRY_COUNT = 3

API_RETRY_DELAY = 5.0

BATCH_DELAY_SECONDS = 4.5


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
    "ONEPIECE": "Áo liền quần",
    "ROMPER": "Áo liền quần",

    "OVERALL": "Quần yếm",
    "OVERALLS": "Quần yếm",
    "BIB OVERALL": "Quần yếm",
    "BIB-OVERALL": "Quần yếm",
    "DUNGAREE": "Quần yếm",
    "DUNGAREES": "Quần yếm",

    "CARGO": "Quần túi hộp",
    "CARGO PANTS": "Quần túi hộp",
    "CARGO TROUSERS": "Quần túi hộp",
    "CARGO TROUSER": "Quần túi hộp",

    "JEANS": "Quần jean",
    "JEAN": "Quần jean",
    "DENIM": "Quần jean",
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
    "LONG TROUSERS": "Quần dài",

    "SHIRT": "Áo",
    "TOP": "Áo",

    "T-SHIRT": "T-shirt",
    "TSHIRT": "T-shirt",
    "T SHIRT": "T-shirt",
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


def _recursive_find_secret(obj, target_names):

    if obj is None:
        return None

    try:

        if hasattr(obj, "items"):

            for key, value in obj.items():

                key_upper = str(key).upper().strip()

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
        str(x).upper().strip()
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
# 8. VALIDATE SECRETS
# =====================================================================

missing_secrets = []

if not SUPABASE_URL:
    missing_secrets.append("SUPABASE_URL")

if not SUPABASE_KEY:
    missing_secrets.append("SUPABASE_KEY")

if not GEMINI_API_KEY:
    missing_secrets.append("GEMINI_API_KEY")


if missing_secrets:

    st.error(
        "❌ Không đọc được thông tin bảo mật từ Streamlit Secrets."
    )

    st.markdown("### Các key còn thiếu:")

    for key in missing_secrets:
        st.code(key)

    st.info(
        """
Secrets nên có dạng:

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

DEFAULT_SESSION_VALUES = {

    "search_file": None,

    "search_result": None,

    "search_ai_result": None,

    "pending_upload_files": [],

    "last_upload_result": None

}


for key, default_value in DEFAULT_SESSION_VALUES.items():

    if key not in st.session_state:

        if isinstance(default_value, list):
            st.session_state[key] = []

        else:
            st.session_state[key] = default_value


# =====================================================================
# 12. IMAGE MIME
# =====================================================================

def get_mime_type(filename):

    filename = str(filename).lower()

    if filename.endswith(".png"):
        return "image/png"

    if filename.endswith(".webp"):
        return "image/webp"

    if filename.endswith(".jpg"):
        return "image/jpeg"

    if filename.endswith(".jpeg"):
        return "image/jpeg"

    return "image/jpeg"


# =====================================================================
# 13. NORMALIZE IMAGE
# =====================================================================

def normalize_image_bytes(image_bytes):

    try:

        from PIL import Image

        image = Image.open(
            io.BytesIO(image_bytes)
        )

        image = image.convert("RGB")

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

def calculate_file_hash(image_bytes):

    return hashlib.sha256(
        image_bytes
    ).hexdigest()


# =====================================================================
# 15. CATEGORY NORMALIZER
# =====================================================================

def normalize_category(category):

    if category is None:
        return "Áo"

    value = str(category).strip()

    if not value:
        return "Áo"

    upper = value.upper()

    if upper in CATEGORY_ALIAS:

        return CATEGORY_ALIAS[upper]

    for valid in CATEGORY_OPTIONS:

        if value.lower() == valid.lower():

            return valid

    # ---------------------------------------------------------------
    # FUZZY BASIC
    # ---------------------------------------------------------------

    upper_compact = re.sub(
        r"[^A-Z0-9]",
        "",
        upper
    )

    for alias, target in CATEGORY_ALIAS.items():

        alias_compact = re.sub(
            r"[^A-Z0-9]",
            "",
            alias
        )

        if upper_compact == alias_compact:

            return target

    return "Áo"


# =====================================================================
# 16. GEMINI GARMENT PROMPT
# =====================================================================

GARMENT_PROMPT = """
You are an expert apparel technical designer.

Analyze the garment shown in the image.

This is a COMMERCIAL GARMENT SIMILARITY SEARCH SYSTEM.

The category must be based on actual garment construction,
not only superficial appearance.

==========================================================
CRITICAL CLASSIFICATION RULES
==========================================================

1. ONE PIECE / JUMPSUIT

If upper body and lower body are physically connected
into one garment:

category = "Áo liền quần"

Do NOT classify it as pants.

----------------------------------------------------------

2. BIB OVERALL

If the garment has:

- bib front
- shoulder straps
- trouser body

category = "Quần yếm"

----------------------------------------------------------

3. CARGO PANTS

Use:

category = "Quần túi hộp"

ONLY when it is a separate pants garment and there are
obvious external cargo / patch pockets on the side legs.

Normal pockets are NOT cargo pockets.

Do NOT classify jumpsuits as cargo.

Do NOT classify overalls as cargo.

----------------------------------------------------------

4. JEANS

Separate denim pants:

category = "Quần jean"

----------------------------------------------------------

5. JOGGER

Separate pants with characteristic jogger construction,
especially elastic or rib ankle cuffs:

category = "Quần jogger"

----------------------------------------------------------

6. SHORTS

Separate short-leg pants:

category = "Quần short"

----------------------------------------------------------

7. LONG PANTS

Separate long trousers without strong cargo,
denim or jogger construction:

category = "Quần dài"

----------------------------------------------------------

8. JACKET

Separate outerwear upper-body garment:

category = "Jacket"

----------------------------------------------------------

9. DRESS

One-piece dress silhouette:

category = "Dress"

A dress is NOT a jumpsuit.

----------------------------------------------------------

10. SHIRT / TOP

Upper body garment:

category = "Áo"

----------------------------------------------------------

11. T-SHIRT

Basic knit tee:

category = "T-shirt"

----------------------------------------------------------

12. POLO

Polo collar / polo construction:

category = "Polo"

----------------------------------------------------------

13. HOODIE

Upper-body garment with hood:

category = "Hoodie"

----------------------------------------------------------

14. SKIRT

Lower-body skirt:

category = "Skirt"

==========================================================
AVAILABLE CATEGORIES
==========================================================

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

==========================================================
ANALYZE CAREFULLY
==========================================================

Look at:

- garment boundary
- upper/lower connection
- waistband
- leg construction
- pocket construction
- cargo pockets
- bib
- shoulder straps
- sleeves
- collar
- hood
- cuffs
- silhouette
- garment length
- denim appearance
- outerwear construction

Return ONLY JSON.
"""


# =====================================================================
# 17. GEMINI VISION
# =====================================================================

def analyze_garment_with_gemini(image_bytes):

    image_bytes = normalize_image_bytes(
        image_bytes
    )

    last_error = None

    for attempt in range(API_RETRY_COUNT):

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

                            "hood": {
                                "type": "boolean"
                            },

                            "sleeve": {
                                "type": "string"
                            },

                            "collar": {
                                "type": "string"
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
                        "Gemini trả về JSON không hợp lệ."
                    )

                result = json.loads(
                    match.group(0)
                )

            return normalize_garment_result(
                result
            )

        except Exception as e:

            last_error = e

            if attempt < API_RETRY_COUNT - 1:

                time.sleep(
                    API_RETRY_DELAY
                )

    raise Exception(
        "Gemini Vision lỗi sau "
        f"{API_RETRY_COUNT} lần thử: "
        f"{last_error}"
    )


# =====================================================================
# 18. GARMENT RESULT NORMALIZER
# =====================================================================

def normalize_garment_result(result):

    if not isinstance(result, dict):

        result = {}


    def bool_value(value):

        if isinstance(value, bool):
            return value

        if isinstance(value, str):

            return value.strip().lower() in [
                "true",
                "yes",
                "1",
                "y"
            ]

        if isinstance(value, (int, float)):

            return bool(value)

        return False


    category = normalize_category(
        result.get(
            "category",
            "Áo"
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

        if bib and shoulder_straps:

            category = "Quần yếm"

        else:

            category = "Áo liền quần"


    # ================================================================
    # HARD RULE 2
    # ================================================================

    elif bib and shoulder_straps:

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

        confidence = 0.0


    confidence = max(
        0.0,
        min(
            100.0,
            confidence
        )
    )


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
# 19. BUILD EMBEDDING CONTENT
# =====================================================================

def build_embedding_content(
    image_bytes,
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

    silhouette = ai_result.get(
        "silhouette",
        ""
    )

    length = ai_result.get(
        "length",
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

    one_piece = (
        "yes"
        if ai_result.get(
            "one_piece",
            False
        )
        else "no"
    )

    bib = (
        "yes"
        if ai_result.get(
            "bib",
            False
        )
        else "no"
    )

    cargo = (
        "yes"
        if ai_result.get(
            "cargo_pockets",
            False
        )
        else "no"
    )

    denim = (
        "yes"
        if ai_result.get(
            "denim",
            False
        )
        else "no"
    )

    jogger = (
        "yes"
        if ai_result.get(
            "jogger_cuffs",
            False
        )
        else "no"
    )

    hood = (
        "yes"
        if ai_result.get(
            "hood",
            False
        )
        else "no"
    )


    semantic_text = f"""
Commercial garment technical similarity representation.

Garment category:
{category}

One piece:
{one_piece}

Bib:
{bib}

Cargo pockets:
{cargo}

Denim:
{denim}

Jogger cuffs:
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

Garment construction analysis:
{reason}

This embedding is used for apparel product similarity search.
Focus on garment construction, silhouette, proportions,
pockets, panels, sleeves, collar, hood, waistband,
leg construction and overall product identity.
"""

    return semantic_text.strip()


# =====================================================================
# 20. GEMINI MULTIMODAL EMBEDDING
# =====================================================================

def get_image_embedding(
    image_bytes,
    ai_result=None
):

    image_bytes = normalize_image_bytes(
        image_bytes
    )

    if ai_result is None:

        ai_result = {
            "category": "",
            "reason": ""
        }


    semantic_text = build_embedding_content(
        image_bytes,
        ai_result
    )


    last_error = None


    for attempt in range(API_RETRY_COUNT):

        try:

            # =========================================================
            # MULTIMODAL:
            #
            # TEXT + IMAGE
            #
            # Gemini Embedding 2 đưa cả hai vào cùng một embedding
            # space.
            # =========================================================

            response = gemini_client.models.embed_content(

                model=EMBEDDING_MODEL,

                contents=[

                    semantic_text,

                    types.Part.from_bytes(
                        data=image_bytes,
                        mime_type="image/jpeg"
                    )

                ],

                config=types.EmbedContentConfig(

                    output_dimensionality=EMBEDDING_DIMENSION

                )

            )


            if not response.embeddings:

                raise Exception(
                    "Gemini không trả về embedding."
                )


            values = (
                response.embeddings[0].values
            )


            if not values:

                raise Exception(
                    "Embedding rỗng."
                )


            values = [
                float(x)
                for x in values
            ]


            # =========================================================
            # DIMENSION CHECK
            # =========================================================

            actual_dimension = len(
                values
            )


            if actual_dimension != EMBEDDING_DIMENSION:

                raise Exception(
                    "Sai dimension embedding: "
                    f"Gemini trả {actual_dimension}, "
                    f"database yêu cầu "
                    f"{EMBEDDING_DIMENSION}."
                )


            # =========================================================
            # NORMALIZE
            # =========================================================

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

            if attempt < API_RETRY_COUNT - 1:

                time.sleep(
                    API_RETRY_DELAY
                )


    raise Exception(
        "Gemini Embedding lỗi sau "
        f"{API_RETRY_COUNT} lần thử: "
        f"{last_error}"
    )


# =====================================================================
# 21. PRODUCT CODE
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

    name = name.strip()

    return name.upper()


# =====================================================================
# 22. SAFE STORAGE PATH
# =====================================================================

def build_storage_path(filename):

    filename = str(
        filename
    )

    safe_name = re.sub(
        r"[^A-Za-z0-9._-]",
        "_",
        filename
    )

    # Không tạo path quá dài
    if len(safe_name) > 180:

        base, ext = os.path.splitext(
            safe_name
        )

        safe_name = (
            base[:160]
            + ext
        )

    return safe_name


# =====================================================================
# 23. SUPABASE STORAGE UPLOAD
# =====================================================================

def upload_image_to_storage(
    image_bytes,
    filename
):

    path = build_storage_path(
        filename
    )

    mime_type = get_mime_type(
        filename
    )


    try:

        result = (
            supabase
            .storage
            .from_(BUCKET_NAME)
            .upload(

                path=path,

                file=image_bytes,

                file_options={

                    "content-type": mime_type,

                    "upsert": "true",

                    "cache-control": "3600"

                }

            )
        )


    except Exception as upload_error:

        error_text = str(
            upload_error
        )


        # ============================================================
        # RLS / UNAUTHORIZED
        # ============================================================

        if (

            "403" in error_text
            or "Unauthorized" in error_text
            or "row-level security" in error_text
            or "violates row-level security" in error_text

        ):

            raise Exception(
                "Supabase Storage bị chặn bởi RLS Policy.\n\n"
                "Bucket: "
                f"{BUCKET_NAME}\n\n"
                "Supabase đang từ chối quyền INSERT/UPLOAD "
                "cho API key hiện tại.\n\n"
                "Cần kiểm tra Storage > Policies của bucket "
                f"'{BUCKET_NAME}'.\n\n"
                f"Chi tiết: {error_text}"
            )


        # ============================================================
        # TRY UPDATE
        # ============================================================

        try:

            supabase.storage \
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

        except Exception:

            raise Exception(
                "Supabase Storage lỗi: "
                + error_text
            )


    # =================================================================
    # PUBLIC URL
    # =================================================================

    try:

        public_url = (
            supabase
            .storage
            .from_(BUCKET_NAME)
            .get_public_url(path)
        )


        if isinstance(
            public_url,
            dict
        ):

            url = (
                public_url.get(
                    "publicUrl"
                )
                or
                public_url.get(
                    "public_url"
                )
            )

        else:

            url = public_url


        if not url:

            raise Exception(
                "Public URL rỗng."
            )


        return str(
            url
        )


    except Exception as e:

        raise Exception(
            "Không lấy được Public URL: "
            + str(e)
        )


# =====================================================================
# 24. SAVE PRODUCT
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

    # ================================================================
    # FINAL DIMENSION CHECK
    # ================================================================

    if not embedding:

        raise Exception(
            "Embedding rỗng, không lưu database."
        )


    if len(embedding) != EMBEDDING_DIMENSION:

        raise Exception(
            "Không thể lưu database.\n"
            f"Embedding = {len(embedding)} dimensions.\n"
            f"Database = {EMBEDDING_DIMENSION} dimensions."
        )


    row = {

        "product_code": product_code,

        "image_url": image_url,

        # AI tự nhận diện category
        "category": category,

        # Giữ riêng AI category
        "ai_category": ai_category,

        # pgvector
        "embedding": embedding,

        # JSONB
        "ai_analysis": ai_result,

        "file_name": filename

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

        # ------------------------------------------------------------
        # VECTOR DIMENSION ERROR
        # ------------------------------------------------------------

        if (
            "dimensions" in error_text.lower()
            or "dimension" in error_text.lower()
            or "22000" in error_text
        ):

            raise Exception(
                "Database vector dimension không khớp.\n\n"
                f"Code đang gửi: {len(embedding)} dimensions.\n"
                f"Code yêu cầu: {EMBEDDING_DIMENSION} dimensions.\n\n"
                f"Supabase: {error_text}"
            )


        raise Exception(
            "Database save lỗi: "
            + error_text
        )


# =====================================================================
# 25. SEARCH SIMILAR PRODUCTS
# =====================================================================

def search_similar_products(
    embedding,
    match_count=SEARCH_COUNT
):

    if not embedding:

        raise Exception(
            "Query embedding rỗng."
        )


    if len(embedding) != EMBEDDING_DIMENSION:

        raise Exception(
            "Query embedding sai dimension.\n"
            f"Hiện tại: {len(embedding)}\n"
            f"Yêu cầu: {EMBEDDING_DIMENSION}"
        )


    last_error = None


    for attempt in range(API_RETRY_COUNT):

        try:

            response = supabase.rpc(

                RPC_SEARCH_FUNCTION,

                {

                    "query_embedding": embedding,

                    "match_threshold": MIN_SIMILARITY,

                    "match_count": match_count

                }

            ).execute()


            return response.data or []


        except Exception as e:

            last_error = e

            if attempt < API_RETRY_COUNT - 1:

                time.sleep(
                    2.0
                )


    raise Exception(
        "Supabase similarity search lỗi: "
        + str(last_error)
    )


# =====================================================================
# 26. CATEGORY BOOST
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


    # ================================================================
    # CATEGORY CHỈ BOOST
    #
    # KHÔNG KHÓA SEARCH
    # ================================================================

    if query_category == db_category:

        score += 0.08

    elif query_category == ai_category:

        score += 0.05


    return score


# =====================================================================
# 27. RANK RESULTS
# =====================================================================

def rank_results(
    results,
    query_category
):

    enriched = []


    for original_item in results:

        item = dict(
            original_item
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

        key=lambda x: float(
            x.get(
                "display_score",
                0
            )
        ),

        reverse=True

    )


    return enriched


# =====================================================================
# 28. HEADER
# =====================================================================

st.title(
    "🔍 AI TÌM KIẾM MÃ HÀNG TƯƠNG ĐỒNG"
)

st.caption(
    "Gemini Vision + Gemini Embedding 2 Multimodal + "
    f"Supabase pgvector — {APP_VERSION}"
)


# =====================================================================
# 29. SYSTEM INFO
# =====================================================================

with st.expander(
    "⚙️ Thông tin hệ thống"
):

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.metric(
            "Version",
            APP_VERSION
        )

    with c2:
        st.metric(
            "Embedding",
            f"{EMBEDDING_DIMENSION}D"
        )

    with c3:
        st.metric(
            "Model",
            EMBEDDING_MODEL
        )

    with c4:
        st.metric(
            "Search",
            f"{SEARCH_COUNT} mã"
        )


# =====================================================================
# 30. TABS
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

        key="search_uploader_v43"

    )


    # ================================================================
    # CLEAR
    # ================================================================

    col_a, col_b = st.columns(
        [1, 5]
    )


    with col_a:

        if st.button(
            "🗑️ Xóa ảnh hiện tại",
            key="clear_search_file_v43"
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

        st.session_state.search_file = image_bytes


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

                key="run_search_v43"

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
                    # MULTIMODAL EMBEDDING
                    # =================================================

                    with st.spinner(
                        "🧠 Gemini Embedding 2 đang phân tích ảnh + cấu trúc..."
                    ):

                        query_embedding = (
                            get_image_embedding(
                                image_bytes,
                                ai_result
                            )
                        )


                    # =================================================
                    # STEP 3
                    # SEARCH
                    # =================================================

                    with st.spinner(
                        "🔎 Đang đối chiếu kho..."
                    ):

                        results = (
                            search_similar_products(
                                query_embedding
                            )
                        )


                    # =================================================
                    # STEP 4
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
                        "✅ Đã hoàn thành tìm kiếm."
                    )


                except Exception as e:

                    st.error(
                        f"❌ Lỗi tìm kiếm: {str(e)}"
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


        # ------------------------------------------------------------
        # EXTRA DETAILS
        # ------------------------------------------------------------

        with st.expander(
            "🔎 Chi tiết nhận dạng"
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
                "Không tìm thấy mã hàng tương đồng trong kho."
            )


        else:

            display_results = results[
                :MAX_DISPLAY_RESULTS
            ]


            column_count = min(
                4,
                len(display_results)
            )


            columns = st.columns(
                column_count
            )


            for index, item in enumerate(
                display_results
            ):

                with columns[
                    index % column_count
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
                                "⚠️ Không tải được ảnh."
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
        "AI sẽ tự nhận diện category cho từng mã hàng."
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

        key="storage_uploader_v43"

    )


    # ================================================================
    # ADD FILES TO QUEUE
    # ================================================================

    if uploaded_files:

        current_names = {

            str(f.name)

            for f in
            st.session_state.pending_upload_files

        }


        for file in uploaded_files:

            if file.name not in current_names:

                st.session_state.pending_upload_files.append(
                    file
                )

                current_names.add(
                    file.name
                )


    # ================================================================
    # CLEAR QUEUE
    # ================================================================

    c1, c2 = st.columns(
        [1, 5]
    )


    with c1:

        if st.button(

            "🗑️ Xóa danh sách chờ",

            key="clear_pending_files_v43"

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

        preview_columns = st.columns(
            min(
                5,
                len(pending_files)
            )
        )


        for i, file in enumerate(
            pending_files
        ):

            with preview_columns[
                i % len(preview_columns)
            ]:

                try:

                    st.image(

                        file,

                        caption=file.name,

                        use_container_width=True

                    )

                except Exception:

                    st.write(
                        file.name
                    )


        st.divider()


        # ============================================================
        # START UPLOAD
        # ============================================================

        if st.button(

            "📤 BẮT ĐẦU NẠP TOÀN BỘ VÀO KHO",

            type="primary",

            use_container_width=True,

            key="start_storage_upload_v43"

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
            # LOOP FILES
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
                    # STEP 1
                    # AI VISION
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
                    # STEP 2
                    # MULTIMODAL EMBEDDING
                    # =================================================

                    status.write(

                        f"🧠 Gemini Embedding 2 "
                        f"đang tạo vector "
                        f"`{product_code}`..."

                    )


                    embedding = (
                        get_image_embedding(

                            image_bytes,

                            ai_result

                        )
                    )


                    # =================================================
                    # STEP 3
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
                    # STEP 4
                    # DATABASE
                    # =================================================

                    status.write(

                        f"💾 Lưu database "
                        f"`{product_code}`..."

                    )


                    save_product(

                        product_code=product_code,

                        image_url=image_url,

                        # =================================================
                        # QUAN TRỌNG:
                        # KHÔNG CÒN storage_category
                        #
                        # Category = AI tự nhận diện
                        # =================================================

                        category=ai_category,

                        ai_category=ai_category,

                        ai_result=ai_result,

                        embedding=embedding,

                        filename=file.name

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


                    error_text = str(
                        e
                    )


                    upload_results.append({

                        "product_code":
                            product_code,

                        "category":
                            ai_result.get(
                                "category",
                                ""
                            )
                            if "ai_result" in locals()
                            and isinstance(
                                ai_result,
                                dict
                            )
                            else "",

                        "ai_category":
                            "",

                        "confidence":
                            0,

                        "status":
                            error_text

                    })


                    st.error(

                        f"❌ `{file.name}` — "
                        f"{error_text}"

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
                # RESET LOCAL VARIABLE
                #
                # Tránh dùng nhầm AI result của file trước nếu file
                # hiện tại lỗi ngay từ bước Vision.
                # =====================================================

                if "ai_result" in locals():

                    del ai_result


                # =====================================================
                # DELAY
                # =====================================================

                if index < total - 1:

                    time.sleep(
                        BATCH_DELAY_SECONDS
                    )


            # =========================================================
            # FINISH
            # =========================================================

            status.empty()


            st.session_state.last_upload_result = (
                upload_results
            )


            # =========================================================
            # CLEAR QUEUE ONLY
            #
            # Database và Storage không bị xóa.
            # =========================================================

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

            if item.get(
                "status"
            ) == "OK":

                try:

                    confidence = float(
                        item.get(
                            "confidence",
                            0
                        )
                    )

                except Exception:

                    confidence = 0.0


                st.success(

                    f"✅ "
                    f"`{item.get('product_code', 'N/A')}` — "
                    f"AI: **{item.get('category', 'N/A')}** — "
                    f"Confidence: **{confidence:.0f}%**"

                )


            else:

                st.error(

                    f"❌ "
                    f"`{item.get('product_code', 'N/A')}` — "
                    f"{item.get('status', 'Unknown error')}"

                )


        # ============================================================
        # CLEAR LOG
        # ============================================================

        if st.button(

            "🗑️ Xóa thông báo kết quả",

            key="clear_upload_result_report_v43"

        ):

            st.session_state.last_upload_result = None

            st.rerun()


# =====================================================================
# 31. FOOTER
# =====================================================================

st.divider()

st.caption(

    "AI Garment Similarity Search — "
    "Gemini Vision + Gemini Embedding 2 Multimodal + "
    "Supabase pgvector — V4.3"

)
