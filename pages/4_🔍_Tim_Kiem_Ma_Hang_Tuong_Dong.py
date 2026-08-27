
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

APP_VERSION = "V4.2"

BUCKET_NAME = "product-images"

PRODUCT_TABLE = "products"

VISION_MODEL = "gemini-3.6-flash"

EMBEDDING_MODEL = "gemini-embedding-2"

EMBEDDING_DIMENSION = 768

SEARCH_COUNT = 12

MIN_SIMILARITY = 0.20

EMBEDDING_RETRIES = 3

EMBEDDING_RETRY_DELAY = 5.0

UPLOAD_RETRY_DELAY = 4.5


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
    missing_secrets.append("SUPABASE_URL")

if not SUPABASE_KEY:
    missing_secrets.append("SUPABASE_KEY")

if not GEMINI_API_KEY:
    missing_secrets.append("GEMINI_API_KEY")


if missing_secrets:

    st.error(
        "❌ Không đọc được thông tin bảo mật từ Streamlit Secrets."
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
Cấu hình `.streamlit/secrets.toml`:

SUPABASE_URL = "https://xxxxx.supabase.co"
SUPABASE_KEY = "xxxxx"
GEMINI_API_KEY = "xxxxx"

Hoặc:

[supabase]
url = "https://xxxxx.supabase.co"
key = "xxxxx"

[gemini]
api_key = "xxxxx"
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

DEFAULT_SESSION_STATE = {

    "search_file": None,

    "search_result": None,

    "search_ai_result": None,

    "pending_upload_files": [],

    "last_upload_result": None

}


for key, default_value in DEFAULT_SESSION_STATE.items():

    if key not in st.session_state:

        st.session_state[key] = default_value


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


def normalize_image_bytes(
    image_bytes
):

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

You are an expert apparel technical designer and garment recognition AI.

Analyze the garment in the image.

This is a COMMERCIAL APPAREL SIMILARITY SEARCH SYSTEM.

The objective is to identify the garment construction as accurately as possible.

Do NOT classify only from superficial visual appearance.

=========================================================
CRITICAL GARMENT RULES
=========================================================

1. ONE PIECE / JUMPSUIT

If upper body and lower body are physically connected
into one garment:

category = "Áo liền quần"

Do NOT classify it as cargo pants.

---------------------------------------------------------

2. BIB OVERALL

If the garment has:

- bib front
- shoulder straps
- trouser body

category = "Quần yếm"

Do NOT classify it as cargo pants.

---------------------------------------------------------

3. CARGO PANTS

Only classify:

"Quần túi hộp"

when the garment is a separate pants garment
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

Separate pants with characteristic jogger construction,
especially elastic or rib ankle cuffs.

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

---------------------------------------------------------

10. SHIRT / TOP

Upper-body garment.

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
- upper/lower connection
- waistband
- pockets
- cargo pockets
- bib
- shoulder straps
- sleeves
- collar
- hood
- cuffs
- silhouette
- length
- denim appearance
- garment construction

IMPORTANT:

The "reason" field must describe the garment
using technical construction language.

Mention important visible construction features.

Return ONLY JSON.
"""


# =====================================================================
# 15. CATEGORY NORMALIZER
# =====================================================================

def normalize_category(category):

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

    return "Quần dài"


# =====================================================================
# 16. BOOLEAN NORMALIZER
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

        return value.lower().strip() in [

            "true",
            "yes",
            "1",
            "y"

        ]

    if isinstance(
        value,
        (int, float)
    ):

        return bool(value)

    return False


# =====================================================================
# 17. GARMENT RESULT NORMALIZER
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
# 18. FALLBACK AI RESULT
# =====================================================================

def create_fallback_ai_result(
    category="Quần dài",
    reason=""
):

    return normalize_garment_result({

        "category": category,

        "confidence": 0,

        "one_piece": False,

        "bib": False,

        "shoulder_straps": False,

        "cargo_pockets": False,

        "denim": False,

        "jogger_cuffs": False,

        "hood": False,

        "sleeve": "",

        "collar": "",

        "silhouette": "",

        "length": "",

        "reason": reason

    })


# =====================================================================
# 19. GEMINI VISION
# =====================================================================

def analyze_garment_with_gemini(
    image_bytes
):

    image_bytes = normalize_image_bytes(
        image_bytes
    )

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


# =====================================================================
# 20. BUILD SEMANTIC TEXT
# =====================================================================

def build_semantic_text(
    ai_result
):

    if not ai_result:

        return "garment apparel clothing"


    parts = []


    category = ai_result.get(
        "category",
        ""
    )

    if category:
        parts.append(
            f"category {category}"
        )


    if ai_result.get(
        "one_piece"
    ):

        parts.append(
            "one piece connected upper body and lower body"
        )


    if ai_result.get(
        "bib"
    ):

        parts.append(
            "bib overall construction"
        )


    if ai_result.get(
        "shoulder_straps"
    ):

        parts.append(
            "shoulder straps"
        )


    if ai_result.get(
        "cargo_pockets"
    ):

        parts.append(
            "external cargo patch pockets"
        )


    if ai_result.get(
        "denim"
    ):

        parts.append(
            "denim jeans fabric appearance"
        )


    if ai_result.get(
        "jogger_cuffs"
    ):

        parts.append(
            "jogger elastic ankle cuffs"
        )


    if ai_result.get(
        "hood"
    ):

        parts.append(
            "hooded garment"
        )


    for key in [

        "sleeve",
        "collar",
        "silhouette",
        "length"

    ]:

        value = ai_result.get(
            key,
            ""
        )

        if value:

            parts.append(
                str(value)
            )


    reason = ai_result.get(
        "reason",
        ""
    )

    if reason:

        parts.append(
            reason
        )


    text = ". ".join(
        parts
    )


    return text[:8000]


# =====================================================================
# 21. TEXT EMBEDDING
# =====================================================================

def get_text_embedding(
    text
):

    if not text:

        text = "garment apparel clothing"


    last_error = None


    for attempt in range(
        EMBEDDING_RETRIES
    ):

        try:

            response = gemini_client.models.embed_content(

                model=EMBEDDING_MODEL,

                contents=text,

                config=types.EmbedContentConfig(

                    output_dimensionality=EMBEDDING_DIMENSION

                )

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


            # -------------------------------------------------
            # DIMENSION CHECK
            # -------------------------------------------------

            if len(values) != EMBEDDING_DIMENSION:

                raise Exception(

                    f"Embedding dimension không đúng: "
                    f"{len(values)} "
                    f"(expected {EMBEDDING_DIMENSION})"

                )


            # -------------------------------------------------
            # NORMALIZE
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

            if attempt < EMBEDDING_RETRIES - 1:

                time.sleep(
                    EMBEDDING_RETRY_DELAY
                )


    raise Exception(
        "Gemini Text Embedding lỗi sau "
        f"{EMBEDDING_RETRIES} lần: "
        f"{last_error}"
    )


# =====================================================================
# 22. BACKWARD COMPATIBILITY
# =====================================================================
#
# Hàm này giữ tên cũ để toàn bộ code TAB 1 / TAB 2
# vẫn có thể gọi get_image_embedding().
#
# Nhưng bên trong:
# image -> AI Vision -> semantic text -> embedding
#
# =====================================================================

def get_image_embedding(
    source
):

    # ---------------------------------------------------------
    # Nếu truyền bytes ảnh
    # ---------------------------------------------------------

    if isinstance(
        source,
        (bytes, bytearray)
    ):

        ai_result = analyze_garment_with_gemini(
            bytes(source)
        )

        semantic_text = build_semantic_text(
            ai_result
        )

        return get_text_embedding(
            semantic_text
        )


    # ---------------------------------------------------------
    # Nếu truyền text
    # ---------------------------------------------------------

    return get_text_embedding(
        str(source)
    )


# =====================================================================
# 23. UPLOAD IMAGE TO SUPABASE STORAGE
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
    # Dùng hash để tránh trùng filename
    # ---------------------------------------------------------

    file_hash = calculate_file_hash(
        image_bytes
    )[:12]


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

                    "content-type": mime_type,

                    "upsert": "true",

                    "cache-control": "3600"

                }

            )

    except Exception as e:

        error_text = str(e)


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
# 25. SEARCH SIMILAR PRODUCTS
# =====================================================================

def search_similar_products(
    embedding,
    match_count=SEARCH_COUNT
):

    # ---------------------------------------------------------
    # CRITICAL DIMENSION CHECK
    # ---------------------------------------------------------

    if not embedding:

        raise Exception(
            "Query embedding rỗng."
        )


    if len(embedding) != EMBEDDING_DIMENSION:

        raise Exception(

            f"Query embedding có {len(embedding)} chiều. "
            f"Database yêu cầu {EMBEDDING_DIMENSION}."

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

        raise Exception(
            "Supabase similarity search lỗi: "
            + str(e)
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
    # CATEGORY BOOST
    #
    # KHÔNG LOẠI RECORD.
    # ---------------------------------------------------------

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
# 28. PRODUCT CODE
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
# 29. HEADER
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
# TÌM KIẾM MÃ TƯƠNG ĐỒNG
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


    # ---------------------------------------------------------
    # FILE UPLOADER
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
    # CLEAR
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
    # PROCESS SEARCH
    # ---------------------------------------------------------

    if search_file is not None:

        image_bytes = search_file.getvalue()


        st.session_state.search_file = (
            image_bytes
        )


        col1, col2 = st.columns(
            [1, 1]
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

                    # =========================================
                    # STEP 1
                    # VISION
                    # =========================================

                    with st.spinner(

                        "🤖 AI đang nhận dạng garment..."

                    ):

                        try:

                            ai_result = (
                                analyze_garment_with_gemini(
                                    image_bytes
                                )
                            )


                        except Exception as vision_err:

                            # ---------------------------------
                            # FALLBACK
                            # ---------------------------------

                            st.warning(

                                "⚠️ Gemini Vision đang "
                                "tạm thời không phản hồi. "
                                "Chuyển sang chế độ tìm kiếm "
                                "an toàn."

                            )


                            ai_result = (
                                create_fallback_ai_result(

                                    category="Quần dài",

                                    reason=(

                                        "Không thể phân tích "
                                        "Vision tại thời điểm này. "
                                        "Kết quả tìm kiếm sử dụng "
                                        "vector ngữ nghĩa dự phòng."

                                    )

                                )
                            )


                    st.session_state.search_ai_result = (
                        ai_result
                    )


                    # =========================================
                    # STEP 2
                    # SEMANTIC TEXT
                    # =========================================

                    semantic_text = (
                        build_semantic_text(
                            ai_result
                        )
                    )


                    # =========================================
                    # STEP 3
                    # EMBEDDING
                    # =========================================

                    with st.spinner(

                        "🧠 Đang tạo đặc trưng vector..."

                    ):

                        query_embedding = None

                        last_embedding_error = None


                        for attempt in range(
                            EMBEDDING_RETRIES
                        ):

                            try:

                                query_embedding = (
                                    get_text_embedding(
                                        semantic_text
                                    )
                                )

                                break


                            except Exception as emb_err:

                                last_embedding_error = (
                                    emb_err
                                )

                                if attempt < (
                                    EMBEDDING_RETRIES - 1
                                ):

                                    time.sleep(
                                        EMBEDDING_RETRY_DELAY
                                    )


                        if query_embedding is None:

                            raise Exception(

                                "Không tạo được embedding: "
                                + str(
                                    last_embedding_error
                                )

                            )


                    # =========================================
                    # STEP 4
                    # VECTOR SEARCH
                    # =========================================

                    with st.spinner(

                        "🔎 Đang đối chiếu dữ liệu kho..."

                    ):

                        results = (
                            search_similar_products(
                                query_embedding
                            )
                        )


                    # =========================================
                    # STEP 5
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


                    st.success(
                        f"Đã tìm thấy {len(results)} mã tương đồng."
                    )


                except Exception as e:

                    st.error(
                        f"❌ Lỗi hệ thống: {str(e)}"
                    )


        # -----------------------------------------------------
        # DISPLAY AI RESULT
        # -----------------------------------------------------

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


            if ai_result.get(
                "reason"
            ):

                st.info(

                    "🧠 "
                    + ai_result[
                        "reason"
                    ]

                )


        # -----------------------------------------------------
        # DISPLAY SEARCH RESULTS
        # -----------------------------------------------------

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

                            f"Score sau Category Boost: "
                            f"{display_score * 100:.2f}%"

                        )


                        # CATEGORY

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
# TAB 2: 📦 NẠP KHO HÀNG LOẠT
# VERSION V4.1
#
# FIX:
#   - Embedding thống nhất 768 dimensions
#   - Không tạo vector giả 3072
#   - Chống upload trùng
#   - Chống lỗi API 429/503
#   - Có retry Gemini
#   - AI Vision -> Text Semantic Embedding
#   - Storage -> Database
# =====================================================================

with tab_storage:

    st.subheader("📦 Nạp mã hàng vào kho")

    st.info(
        "Category kho là phân loại nghiệp vụ. "
        "AI vẫn tự nhận dạng garment và lưu thêm AI category."
    )

    # ================================================================
    # 1. CATEGORY KHO
    # ================================================================

    storage_category = st.selectbox(
        "📦 Chọn dòng hàng để lưu kho",
        CATEGORY_OPTIONS,
        key="storage_category_tab2_v41"
    )

    # ================================================================
    # 2. UPLOAD FILE
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
        key="storage_uploader_tab2_v41"
    )

    # ================================================================
    # 3. ĐƯA FILE VÀO HÀNG ĐỢI
    # ================================================================

    if uploaded_files:

        current_names = {
            str(f.name).strip().lower()
            for f in st.session_state.pending_upload_files
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
    # 4. XÓA HÀNG ĐỢI
    # ================================================================

    c1, _ = st.columns([1, 5])

    with c1:

        if st.button(
            "🗑️ Xóa danh sách chờ",
            key="clear_pending_files_tab2_v41"
        ):

            st.session_state.pending_upload_files = []

            st.rerun()

    # ================================================================
    # 5. LẤY DANH SÁCH CHỜ
    # ================================================================

    pending_files = (
        st.session_state.pending_upload_files
    )

    if pending_files:

        st.success(
            f"📂 Đang chờ **{len(pending_files)}** "
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

        for i, file in enumerate(pending_files):

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
        # 6. BẮT ĐẦU NẠP
        # ============================================================

        if st.button(
            "📤 BẮT ĐẦU NẠP TOÀN BỘ VÀO KHO",
            type="primary",
            use_container_width=True,
            key="start_storage_upload_tab2_v41"
        ):

            import time

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
            # LOOP TỪNG FILE
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
                    f"— Đang xử lý `{product_code}`"
                )

                try:

                    # =================================================
                    # READ IMAGE
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
                    # GEMINI VISION
                    # =================================================

                    status.write(
                        f"🤖 AI đang nhận dạng "
                        f"`{product_code}`..."
                    )

                    ai_result = None

                    vision_error = None

                    # Retry tối đa 3 lần
                    for attempt in range(3):

                        try:

                            ai_result = (
                                analyze_garment_with_gemini(
                                    image_bytes
                                )
                            )

                            break

                        except Exception as e:

                            vision_error = e

                            if attempt < 2:

                                wait_seconds = (
                                    5 * (attempt + 1)
                                )

                                time.sleep(
                                    wait_seconds
                                )

                    # Nếu Vision thất bại hoàn toàn
                    if not ai_result:

                        raise Exception(
                            "Gemini Vision thất bại sau 3 lần thử: "
                            + str(vision_error)
                        )

                    # =================================================
                    # AI CATEGORY
                    # =================================================

                    ai_category = (
                        ai_result.get(
                            "category",
                            "Quần dài"
                        )
                    )

                    # Đảm bảo category hợp lệ
                    ai_category = normalize_category(
                        ai_category
                    )

                    # =================================================
                    # STEP 2
                    # TEXT SEMANTIC EMBEDDING
                    # =================================================

                    status.write(
                        f"🧠 Đang tạo semantic embedding "
                        f"`{product_code}`..."
                    )

                    # -------------------------------------------------
                    # Tạo text giàu thông tin hơn chỉ dùng "reason"
                    # -------------------------------------------------

                    text_for_embedding = (
                        f"Garment category: {ai_category}. "
                        f""
                        f"One piece: "
                        f"{ai_result.get('one_piece', False)}. "
                        f""
                        f"Bib: "
                        f"{ai_result.get('bib', False)}. "
                        f""
                        f"Shoulder straps: "
                        f"{ai_result.get('shoulder_straps', False)}. "
                        f""
                        f"Cargo pockets: "
                        f"{ai_result.get('cargo_pockets', False)}. "
                        f""
                        f"Denim: "
                        f"{ai_result.get('denim', False)}. "
                        f""
                        f"Jogger cuffs: "
                        f"{ai_result.get('jogger_cuffs', False)}. "
                        f""
                        f"Hood: "
                        f"{ai_result.get('hood', False)}. "
                        f""
                        f"Sleeve: "
                        f"{ai_result.get('sleeve', '')}. "
                        f""
                        f"Collar: "
                        f"{ai_result.get('collar', '')}. "
                        f""
                        f"Silhouette: "
                        f"{ai_result.get('silhouette', '')}. "
                        f""
                        f"Length: "
                        f"{ai_result.get('length', '')}. "
                        f""
                        f"Construction description: "
                        f"{ai_result.get('reason', '')}"
                    )

                    # =================================================
                    # IMPORTANT
                    #
                    # get_image_embedding() hiện tại của bạn phải
                    # chấp nhận TEXT và trả về 768 dimensions.
                    # =================================================

                    embedding = None

                    embedding_error = None

                    for attempt in range(3):

                        try:

                            embedding = (
                                get_image_embedding(
                                    text_for_embedding
                                )
                            )

                            break

                        except Exception as e:

                            embedding_error = e

                            if attempt < 2:

                                wait_seconds = (
                                    5 * (attempt + 1)
                                )

                                time.sleep(
                                    wait_seconds
                                )

                    if not embedding:

                        raise Exception(
                            "Gemini Embedding thất bại sau 3 lần thử: "
                            + str(embedding_error)
                        )

                    # =================================================
                    # CRITICAL DIMENSION CHECK
                    # =================================================

                    embedding_dimension = len(
                        embedding
                    )

                    if (
                        embedding_dimension
                        != EMBEDDING_DIMENSION
                    ):

                        raise Exception(
                            f"Embedding dimension không đúng: "
                            f"Gemini trả {embedding_dimension}, "
                            f"hệ thống yêu cầu {EMBEDDING_DIMENSION}."
                        )

                    # =================================================
                    # STEP 3
                    # SUPABASE STORAGE
                    # =================================================

                    status.write(
                        f"☁️ Đang upload ảnh "
                        f"`{product_code}`..."
                    )

                    image_url = (
                        upload_image_to_storage(
                            image_bytes,
                            file.name
                        )
                    )

                    if not image_url:

                        raise Exception(
                            "Supabase Storage không trả về image URL."
                        )

                    # =================================================
                    # STEP 4
                    # DATABASE
                    # =================================================

                    status.write(
                        f"💾 Đang lưu database "
                        f"`{product_code}`..."
                    )

                    save_product(
                        product_code=product_code,
                        image_url=image_url,
                        category=storage_category,
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

                # =====================================================
                # ERROR
                # =====================================================

                except Exception as e:

                    failed_count += 1

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
                            str(e)

                    })

                    st.error(
                        f"❌ `{file.name}` — {str(e)}"
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
                # RATE LIMIT DELAY
                # =====================================================

                if index < total - 1:

                    time.sleep(
                        4.5
                    )

            # ========================================================
            # FINISH
            # ========================================================

            status.empty()

            st.session_state.last_upload_result = (
                upload_results
            )

            # Chỉ xóa hàng đợi
            st.session_state.pending_upload_files = []

            # ========================================================
            # REPORT
            # ========================================================

            if success_count:

                st.success(
                    f"🎉 Đã nạp thành công "
                    f"**{success_count}/{total}** mã hàng."
                )

            if failed_count:

                st.warning(
                    f"⚠️ Có "
                    f"**{failed_count}** mã hàng xử lý thất bại."
                )

            # Không rerun ngay ở đây.
            # Giữ report hiển thị cho người dùng.
            st.rerun()

    # =================================================================
    # 7. KẾT QUẢ NẠP KHO
    # =================================================================

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
                    f"Confidence: {item['confidence']:.0f}% — "
                    f"Vector: {item['embedding_dim']}D"

                )

            else:

                st.error(

                    f"❌ `{item['product_code']}` — "
                    f"Kho: {item['category']} — "
                    f"Lỗi: {item['status']}"

                )

        # =============================================================
        # CLEAR REPORT
        # =============================================================

        if st.button(
            "🗑️ Xóa thông báo kết quả",
            key="clear_upload_result_report_tab2_v41"
        ):

            st.session_state.last_upload_result = None

            st.rerun()
