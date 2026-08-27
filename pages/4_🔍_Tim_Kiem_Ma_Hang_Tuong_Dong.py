# =====================================================================
# 🔍 AI TÌM KIẾM MÃ HÀNG TƯƠNG ĐỒNG
# VERSION V2.6
#
# GEMINI VISION
# GEMINI EMBEDDING 2
# SUPABASE + PGVECTOR
#
# KHÔNG DÙNG HUGGING FACE
# KHÔNG DÙNG CLIP
# KHÔNG DÙNG TORCH
#
# Chức năng:
# 1. Upload ảnh tìm kiếm
# 2. AI tự nhận diện category
# 3. Gemini tạo image embedding
# 4. Tìm mã hàng tương đồng trong Supabase
# 5. Upload hàng loạt vào kho
# 6. AI tự nhận diện category khi lưu
# 7. Lưu ảnh + embedding + AI analysis
# 8. Xóa file đang chờ upload
# 9. Không ảnh hưởng dữ liệu kho khi xóa file đang chờ
# =====================================================================

import streamlit as st
import json
import re
import io
import os
import uuid
import mimetypes
import numpy as np

from PIL import Image
from supabase import create_client, Client

from google import genai
from google.genai import types


# =====================================================================
# 0. PAGE CONFIG
# =====================================================================

st.set_page_config(
    page_title="AI Tìm Kiếm Mã Hàng",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)


# =====================================================================
# 1. CONSTANTS
# =====================================================================

APP_VERSION = "V2.6"

SUPABASE_BUCKET = "product-images"

# Gemini Vision
VISION_MODEL = "gemini-2.5-flash"

# Gemini multimodal embedding
EMBEDDING_MODEL = "gemini-embedding-2"

# 768 là kích thước được Google khuyến nghị cho embedding 2
EMBEDDING_DIM = 768

TOP_K = 12

# Category chuẩn của hệ thống
VALID_CATEGORIES = [
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
# 2. LOAD SECRETS
# =====================================================================

def get_secret(name, required=True):
    """
    Đọc secret an toàn từ Streamlit Secrets.

    Hỗ trợ:
        st.secrets["SUPABASE_URL"]

    hoặc:

        [api]
        SUPABASE_URL = "..."
    """

    # ---------------------------------------------------------------
    # Cách 1: flat
    # ---------------------------------------------------------------

    try:
        if name in st.secrets:

            value = st.secrets[name]

            if value is not None:
                value = str(value).strip()

                if value:
                    return value

    except Exception:
        pass


    # ---------------------------------------------------------------
    # Cách 2: [api]
    # ---------------------------------------------------------------

    try:

        if "api" in st.secrets:

            api_section = st.secrets["api"]

            if name in api_section:

                value = api_section[name]

                if value is not None:
                    value = str(value).strip()

                    if value:
                        return value

    except Exception:
        pass


    # ---------------------------------------------------------------
    # Cách 3: [secrets]
    # ---------------------------------------------------------------

    try:

        if "secrets" in st.secrets:

            secret_section = st.secrets["secrets"]

            if name in secret_section:

                value = secret_section[name]

                if value is not None:
                    value = str(value).strip()

                    if value:
                        return value

    except Exception:
        pass


    if required:
        return None

    return None


# =====================================================================
# 3. READ SECURITY KEYS
# =====================================================================

SUPABASE_URL = get_secret(
    "SUPABASE_URL"
)

SUPABASE_KEY = get_secret(
    "SUPABASE_KEY"
)

GEMINI_API_KEY = get_secret(
    "GEMINI_API_KEY"
)


# =====================================================================
# 4. SECURITY CHECK
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
        "❌ Không đọc được thông tin bảo mật từ "
        "Streamlit Secrets."
    )

    st.write(
        "Hãy kiểm tra các key sau:"
    )

    for key in missing_keys:

        st.code(
            key
        )

    st.stop()


# =====================================================================
# 5. INITIALIZE CLIENTS
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
# 6. SESSION STATE
# =====================================================================

if "pending_uploads_v26" not in st.session_state:

    st.session_state[
        "pending_uploads_v26"
    ] = []


if "search_results_v26" not in st.session_state:

    st.session_state[
        "search_results_v26"
    ] = []


if "search_ai_result_v26" not in st.session_state:

    st.session_state[
        "search_ai_result_v26"
    ] = None


if "search_file_name_v26" not in st.session_state:

    st.session_state[
        "search_file_name_v26"
    ] = None


# =====================================================================
# 7. GARMENT PROMPT
# =====================================================================

GARMENT_PROMPT = r"""
You are an expert apparel product recognition AI.

Your job is to identify the actual garment construction
from a fashion sketch, tech-pack image, flat sketch,
product photo, or garment image.

This is NOT generic image classification.

You must focus on garment construction.

===========================================================
CRITICAL CLASSIFICATION RULES
===========================================================

1. ONE PIECE / JUMPSUIT

If upper body and lower body are physically connected
into one garment:

category = "Áo liền quần"

Do NOT classify a jumpsuit as cargo pants.

-----------------------------------------------------------

2. BIB OVERALL / QUẦN YẾM

If the garment has:

- bib front
- shoulder straps
- overall construction

category = "Quần yếm"

Do NOT classify bib overalls as cargo pants.

-----------------------------------------------------------

3. CARGO PANTS / QUẦN TÚI HỘP

Cargo pants must be:

- a separate pants garment
- AND have clearly visible external cargo / patch pockets
  on the side leg area.

If there are no obvious cargo pockets:

DO NOT classify as "Quần túi hộp".

-----------------------------------------------------------

4. JEANS

If the garment is separate denim jeans:

category = "Quần jean"

-----------------------------------------------------------

5. JOGGER

If separate pants have jogger construction,
especially elastic/rib cuffs:

category = "Quần jogger"

-----------------------------------------------------------

6. SHORTS

If separate pants with short leg length:

category = "Quần short"

-----------------------------------------------------------

7. NORMAL LONG PANTS

If separate long pants without clear cargo,
denim or jogger construction:

category = "Quần dài"

-----------------------------------------------------------

8. JACKET

Separate upper-body outerwear:

category = "Jacket"

-----------------------------------------------------------

9. SHIRT / TOP

Normal woven upper-body shirt:

category = "Áo"

-----------------------------------------------------------

10. T-SHIRT

T-shirt construction:

category = "T-shirt"

-----------------------------------------------------------

11. POLO

Polo construction:

category = "Polo"

-----------------------------------------------------------

12. HOODIE

Hooded sweatshirt / hoodie:

category = "Hoodie"

-----------------------------------------------------------

13. SKIRT

Skirt:

category = "Skirt"

-----------------------------------------------------------

14. DRESS

One-piece dress silhouette that is NOT pants-based:

category = "Dress"

===========================================================
IMPORTANT
===========================================================

Never use "Quần túi hộp" merely because the lower half
looks like workwear.

Cargo requires visible cargo/patch pockets.

Never classify a jumpsuit as cargo pants.

Never classify bib overall as cargo pants.

===========================================================
VALID CATEGORIES
===========================================================

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

===========================================================
RETURN
===========================================================

Return ONLY valid JSON.

Use exactly:

{
  "category": "Quần dài",
  "confidence": 95,
  "one_piece": false,
  "bib": false,
  "shoulder_straps": false,
  "cargo_pockets": false,
  "denim": false,
  "jogger_cuffs": false,
  "hood": false,
  "sleeve": "none",
  "collar": "none",
  "silhouette": "straight",
  "length": "full",
  "reason": "Separate long pants without visible cargo pockets."
}
"""


# =====================================================================
# 8. CATEGORY ALIASES
# =====================================================================

CATEGORY_ALIASES = {

    "JUMPSUIT":
        "Áo liền quần",

    "ROMPER":
        "Áo liền quần",

    "ONE PIECE":
        "Áo liền quần",

    "ONE-PIECE":
        "Áo liền quần",

    "OVERALL":
        "Quần yếm",

    "OVERALLS":
        "Quần yếm",

    "BIB OVERALL":
        "Quần yếm",

    "DUNGAREES":
        "Quần yếm",

    "CARGO":
        "Quần túi hộp",

    "CARGO PANTS":
        "Quần túi hộp",

    "CARGO TROUSERS":
        "Quần túi hộp",

    "JEANS":
        "Quần jean",

    "DENIM":
        "Quần jean",

    "DENIM JEANS":
        "Quần jean",

    "JOGGER":
        "Quần jogger",

    "JOGGERS":
        "Quần jogger",

    "SHORT":
        "Quần short",

    "SHORTS":
        "Quần short",

    "PANTS":
        "Quần dài",

    "TROUSERS":
        "Quần dài",

    "LONG PANTS":
        "Quần dài",

    "SHIRT":
        "Áo",

    "TOP":
        "Áo",

    "TEE":
        "T-shirt",

    "T-SHIRT":
        "T-shirt",

    "TSHIRT":
        "T-shirt",

    "POLO SHIRT":
        "Polo",

    "POLO":
        "Polo",

    "HOODIE":
        "Hoodie",

    "JACKET":
        "Jacket",

    "COAT":
        "Jacket",

    "DRESS":
        "Dress",

    "SKIRT":
        "Skirt",
}


# =====================================================================
# 9. IMAGE UTILITIES
# =====================================================================

def normalize_image(image_bytes):

    try:

        image = Image.open(
            io.BytesIO(image_bytes)
        )

        image = image.convert(
            "RGB"
        )

        return image

    except Exception as e:

        raise Exception(
            f"Không đọc được hình ảnh: {e}"
        )


def get_image_mime(image_bytes):

    try:

        image = Image.open(
            io.BytesIO(image_bytes)
        )

        fmt = (
            image.format
            or "JPEG"
        ).upper()

    except Exception:

        fmt = "JPEG"


    if fmt == "PNG":
        return "image/png"

    if fmt == "WEBP":
        return "image/webp"

    if fmt == "GIF":
        return "image/gif"

    return "image/jpeg"


# =====================================================================
# 10. JSON CLEANER
# =====================================================================

def extract_json(text):

    if text is None:

        raise Exception(
            "Gemini không trả về dữ liệu."
        )


    text = str(
        text
    ).strip()


    if not text:

        raise Exception(
            "Gemini trả về nội dung rỗng."
        )


    # ---------------------------------------------------------------
    # REMOVE MARKDOWN
    # ---------------------------------------------------------------

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


    # ---------------------------------------------------------------
    # FIND JSON OBJECT
    # ---------------------------------------------------------------

    start = text.find("{")

    end = text.rfind("}")


    if start == -1 or end == -1:

        raise Exception(
            "Gemini không trả JSON hợp lệ:\n"
            + text[:2000]
        )


    json_text = text[
        start:end + 1
    ]


    try:

        return json.loads(
            json_text
        )

    except Exception as e:

        # -----------------------------------------------------------
        # TRY REPAIR SIMPLE TRUNCATION
        # -----------------------------------------------------------

        repaired = json_text

        repaired = repaired.replace(
            "\n",
            " "
        )

        repaired = repaired.replace(
            ",}",
            "}"
        )

        repaired = repaired.replace(
            ", }",
            "}"
        )


        try:

            return json.loads(
                repaired
            )

        except Exception:

            raise Exception(
                "Gemini không trả JSON hợp lệ: "
                + str(e)
                + "\n\n"
                + text[:2000]
            )


# =====================================================================
# 11. NORMALIZE AI RESULT
# =====================================================================

def normalize_garment_result(
    result
):

    if not isinstance(
        result,
        dict
    ):

        raise Exception(
            "AI result không phải dictionary."
        )


    category = str(
        result.get(
            "category",
            ""
        )
    ).strip()


    category_upper = (
        category
        .upper()
        .strip()
    )


    if category_upper in CATEGORY_ALIASES:

        category = CATEGORY_ALIASES[
            category_upper
        ]


    if category not in VALID_CATEGORIES:

        category = "Quần dài"


    result[
        "category"
    ] = category


    # ---------------------------------------------------------------
    # BOOLEAN
    # ---------------------------------------------------------------

    bool_fields = [

        "one_piece",
        "bib",
        "shoulder_straps",
        "cargo_pockets",
        "denim",
        "jogger_cuffs",
        "hood"

    ]


    for field in bool_fields:

        value = result.get(
            field,
            False
        )


        if isinstance(
            value,
            str
        ):

            value = (
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


        result[
            field
        ] = bool(
            value
        )


    # ---------------------------------------------------------------
    # CONFIDENCE
    # ---------------------------------------------------------------

    try:

        confidence = float(
            result.get(
                "confidence",
                0
            )
        )

    except Exception:

        confidence = 0


    result[
        "confidence"
    ] = max(
        0,
        min(
            100,
            confidence
        )
    )


    # ===============================================================
    # HARD RULE 1
    # ONE PIECE
    # ===============================================================

    if result[
        "one_piece"
    ]:

        if (
            result["bib"]
            and
            result["shoulder_straps"]
        ):

            result[
                "category"
            ] = "Quần yếm"

        else:

            result[
                "category"
            ] = "Áo liền quần"


    # ===============================================================
    # HARD RULE 2
    # BIB
    # ===============================================================

    elif (
        result["bib"]
        and
        result["shoulder_straps"]
    ):

        result[
            "category"
        ] = "Quần yếm"


    # ===============================================================
    # HARD RULE 3
    # CARGO
    # ===============================================================

    elif (
        result["category"]
        ==
        "Quần túi hộp"
        and
        not result["cargo_pockets"]
    ):

        result[
            "category"
        ] = "Quần dài"


    # ===============================================================
    # HARD RULE 4
    # DENIM
    # ===============================================================

    elif (
        result["denim"]
        and
        result["category"]
        ==
        "Quần dài"
    ):

        result[
            "category"
        ] = "Quần jean"


    # ===============================================================
    # HARD RULE 5
    # JOGGER
    # ===============================================================

    elif (
        result["jogger_cuffs"]
        and
        result["category"]
        ==
        "Quần dài"
    ):

        result[
            "category"
        ] = "Quần jogger"


    return result


# =====================================================================
# 12. GEMINI VISION
# =====================================================================

def analyze_garment_with_gemini(
    image_bytes
):

    mime_type = get_image_mime(
        image_bytes
    )


    try:

        response = gemini_client.models.generate_content(

            model=VISION_MODEL,

            contents=[

                types.Part.from_bytes(
                    data=image_bytes,
                    mime_type=mime_type
                ),

                GARMENT_PROMPT

            ],

            config=types.GenerateContentConfig(

                temperature=0,

                max_output_tokens=1200

            )

        )


    except Exception as e:

        raise Exception(
            "Gemini Vision lỗi: "
            + str(e)
        )


    try:

        text = (
            response.text
            if response
            else ""
        )

    except Exception:

        text = ""


    if not text:

        raise Exception(
            "Gemini Vision không trả kết quả."
        )


    result = extract_json(
        text
    )


    result = normalize_garment_result(
        result
    )


    return result


# =====================================================================
# 13. GEMINI IMAGE EMBEDDING 2
# =====================================================================

def create_image_embedding(
    image_bytes
):

    mime_type = get_image_mime(
        image_bytes
    )


    try:

        response = gemini_client.models.embed_content(

            model=EMBEDDING_MODEL,

            contents=[

                types.Content(
                    parts=[

                        types.Part.from_bytes(
                            data=image_bytes,
                            mime_type=mime_type
                        )

                    ]
                )

            ],

            config=types.EmbedContentConfig(

                output_dimensionality=EMBEDDING_DIM

            )

        )

    except Exception as e:

        raise Exception(
            "Gemini Embedding lỗi: "
            + str(e)
        )


    try:

        embeddings = (
            response.embeddings
        )


        if not embeddings:

            raise Exception(
                "Không có embedding."
            )


        values = (
            embeddings[0].values
        )


        vector = np.asarray(
            values,
            dtype=np.float32
        )


    except Exception as e:

        raise Exception(
            "Không đọc được Gemini embedding: "
            + str(e)
        )


    if vector.size != EMBEDDING_DIM:

        raise Exception(
            f"Embedding dimension không đúng. "
            f"Nhận được {vector.size}, "
            f"cần {EMBEDDING_DIM}."
        )


    # ---------------------------------------------------------------
    # NORMALIZE
    # ---------------------------------------------------------------

    norm = np.linalg.norm(
        vector
    )


    if norm > 0:

        vector = (
            vector / norm
        )


    return vector.tolist()


# =====================================================================
# 14. VECTOR FORMAT FOR SUPABASE
# =====================================================================

def vector_to_pgvector(
    vector
):

    return (
        "["
        +
        ",".join(
            f"{float(x):.8f}"
            for x in vector
        )
        +
        "]"
    )


# =====================================================================
# 15. PRODUCT CODE
# =====================================================================

def extract_product_code(
    filename
):

    name = os.path.basename(
        filename
    )


    stem = os.path.splitext(
        name
    )[0]


    return (
        stem
        .strip()
        .upper()
    )


# =====================================================================
# 16. STORAGE UPLOAD
# =====================================================================

def upload_image_to_storage(
    file_bytes,
    original_filename
):

    extension = (
        os.path.splitext(
            original_filename
        )[1]
        or ".jpg"
    ).lower()


    safe_code = re.sub(
        r"[^A-Za-z0-9_\-]",
        "_",
        os.path.splitext(
            original_filename
        )[0]
    )


    unique_name = (
        safe_code
        + "_"
        + uuid.uuid4().hex[:8]
        + extension
    )


    mime_type = get_image_mime(
        file_bytes
    )


    try:

        result = supabase.storage.from_(
            SUPABASE_BUCKET
        ).upload(

            path=unique_name,

            file=file_bytes,

            file_options={
                "content-type": mime_type,
                "upsert": "true"
            }

        )


    except Exception as e:

        raise Exception(
            "Upload Storage lỗi: "
            + str(e)
        )


    try:

        public_url = (
            supabase
            .storage
            .from_(
                SUPABASE_BUCKET
            )
            .get_public_url(
                unique_name
            )
        )

    except Exception as e:

        raise Exception(
            "Không lấy được URL ảnh: "
            + str(e)
        )


    return (
        public_url,
        unique_name
    )


# =====================================================================
# 17. DELETE STORAGE IMAGE
# =====================================================================

def delete_storage_image(
    storage_path
):

    if not storage_path:

        return


    try:

        supabase.storage.from_(
            SUPABASE_BUCKET
        ).remove(
            [storage_path]
        )

    except Exception as e:

        st.warning(
            "Không xóa được ảnh Storage: "
            + str(e)
        )


# =====================================================================
# 18. SAVE PRODUCT
# =====================================================================

def save_product_to_database(
    product_code,
    image_url,
    storage_path,
    category,
    ai_analysis,
    embedding
):

    embedding_pg = vector_to_pgvector(
        embedding
    )


    payload = {

        "product_code":
            product_code,

        "image_url":
            image_url,

        "storage_path":
            storage_path,

        "category":
            category,

        "ai_analysis":
            ai_analysis,

        "embedding":
            embedding_pg

    }


    try:

        response = (
            supabase
            .table("products")
            .upsert(
                payload,
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
# 19. SEARCH PRODUCTS
# =====================================================================

def search_similar_products(
    embedding,
    category,
    limit=TOP_K
):

    vector_pg = vector_to_pgvector(
        embedding
    )


    # ===============================================================
    # METHOD 1
    # RPC V2.6
    # ===============================================================

    try:

        response = supabase.rpc(

            "match_products_v26",

            {

                "query_embedding":
                    vector_pg,

                "match_count":
                    limit,

                "filter_category":
                    category

            }

        ).execute()


        if response.data is not None:

            return response.data


    except Exception:
        pass


    # ===============================================================
    # METHOD 2
    # NO CATEGORY FILTER
    #
    # Quan trọng:
    # Không khóa cứng category.
    #
    # Nếu AI nhận nhầm Cargo/Pants,
    # vẫn có thể tìm được sản phẩm tương đồng.
    # ===============================================================

    try:

        response = supabase.rpc(

            "match_products_v26_all",

            {

                "query_embedding":
                    vector_pg,

                "match_count":
                    limit

            }

        ).execute()


        if response.data is not None:

            return response.data


    except Exception:
        pass


    # ===============================================================
    # METHOD 3
    # FALLBACK
    # ===============================================================

    try:

        response = (
            supabase
            .table("products")
            .select(
                "product_code,"
                "image_url,"
                "storage_path,"
                "category,"
                "ai_analysis,"
                "embedding"
            )
            .limit(500)
            .execute()
        )


        rows = response.data or []


        if not rows:

            return []


        q = np.asarray(
            embedding,
            dtype=np.float32
        )


        results = []


        for row in rows:

            raw_vector = (
                row.get(
                    "embedding"
                )
            )


            if not raw_vector:

                continue


            try:

                if isinstance(
                    raw_vector,
                    str
                ):

                    clean = (
                        raw_vector
                        .strip()
                        .replace(
                            "[",
                            ""
                        )
                        .replace(
                            "]",
                            ""
                        )
                    )


                    db_vector = np.asarray(

                        [
                            float(x)
                            for x in clean.split(",")
                        ],

                        dtype=np.float32

                    )

                else:

                    db_vector = np.asarray(
                        raw_vector,
                        dtype=np.float32
                    )


            except Exception:

                continue


            if (
                db_vector.size
                !=
                q.size
            ):

                continue


            denominator = (
                np.linalg.norm(q)
                *
                np.linalg.norm(
                    db_vector
                )
            )


            if denominator == 0:

                continue


            similarity = (
                float(
                    np.dot(
                        q,
                        db_vector
                    )
                    /
                    denominator
                )
            )


            # -------------------------------------------------------
            # CATEGORY BOOST
            # -------------------------------------------------------

            row_category = str(
                row.get(
                    "category",
                    ""
                )
            )


            category_boost = 0.0


            if (
                row_category
                ==
                category
            ):

                category_boost = 0.04


            final_score = (
                similarity
                +
                category_boost
            )


            row_copy = dict(
                row
            )


            row_copy[
                "similarity"
            ] = similarity


            row_copy[
                "final_score"
            ] = final_score


            results.append(
                row_copy
            )


        results.sort(
            key=lambda x:
                x.get(
                    "final_score",
                    0
                ),
            reverse=True
        )


        return results[:limit]


    except Exception as e:

        raise Exception(
            "Không thể tìm kiếm database: "
            + str(e)
        )


# =====================================================================
# 20. DISPLAY AI RESULT
# =====================================================================

def display_ai_result(
    result
):

    if not result:

        return


    category = result.get(
        "category",
        "Không xác định"
    )


    confidence = result.get(
        "confidence",
        0
    )


    st.success(
        f"🤖 AI nhận diện: **{category}** "
        f"— Confidence **{confidence:.0f}%**"
    )


    col1, col2, col3, col4 = st.columns(4)


    with col1:

        st.metric(
            "Category",
            category
        )


    with col2:

        st.metric(
            "Confidence",
            f"{confidence:.0f}%"
        )


    with col3:

        st.metric(
            "One Piece",
            "YES"
            if result.get(
                "one_piece"
            )
            else "NO"
        )


    with col4:

        st.metric(
            "Cargo Pocket",
            "YES"
            if result.get(
                "cargo_pockets"
            )
            else "NO"
        )


    with st.expander(
        "🔎 Chi tiết AI"
    ):

        st.json(
            result
        )


# =====================================================================
# 21. DISPLAY SEARCH RESULTS
# =====================================================================

def display_search_results(
    results
):

    if not results:

        st.warning(
            "Không tìm thấy mã hàng tương đồng."
        )

        return


    st.subheader(
        f"🎯 Tìm thấy {len(results)} mã tương đồng"
    )


    cols = st.columns(
        min(
            len(results),
            4
        )
    )


    for index, item in enumerate(
        results
    ):

        col = cols[
            index
            %
            len(cols)
        ]


        with col:

            product_code = item.get(
                "product_code",
                "N/A"
            )


            category = item.get(
                "category",
                ""
            )


            similarity = item.get(
                "similarity",
                item.get(
                    "final_score",
                    0
                )
            )


            try:

                similarity_percent = (
                    float(similarity)
                    *
                    100
                )

            except Exception:

                similarity_percent = 0


            st.markdown(
                f"### 🏷️ {product_code}"
            )


            st.caption(
                f"Loại: {category}"
            )


            st.metric(
                "Độ tương đồng",
                f"{similarity_percent:.2f}%"
            )


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


            st.divider()


# =====================================================================
# 22. ADD UPLOAD FILES TO SESSION
# =====================================================================

def add_pending_files(
    uploaded_files
):

    existing_names = {

        item[
            "name"
        ]

        for item
        in st.session_state[
            "pending_uploads_v26"
        ]

    }


    added = 0


    for uploaded_file in uploaded_files:

        if uploaded_file.name in existing_names:

            continue


        file_bytes = (
            uploaded_file
            .getvalue()
        )


        st.session_state[
            "pending_uploads_v26"
        ].append({

            "name":
                uploaded_file.name,

            "bytes":
                file_bytes

        })


        existing_names.add(
            uploaded_file.name
        )


        added += 1


    return added


# =====================================================================
# 23. REMOVE PENDING FILE
# =====================================================================

def remove_pending_file(
    index
):

    files = st.session_state[
        "pending_uploads_v26"
    ]


    if (
        0
        <=
        index
        <
        len(files)
    ):

        files.pop(
            index
        )


# =====================================================================
# 24. CLEAR PENDING FILES
# =====================================================================

def clear_pending_files():

    st.session_state[
        "pending_uploads_v26"
    ] = []


# =====================================================================
# 25. HEADER
# =====================================================================

st.title(
    "🔍 AI TÌM KIẾM MÃ HÀNG TƯƠNG ĐỒNG"
)

st.caption(
    f"AI Garment Similarity Search — {APP_VERSION} "
    "| Gemini Vision + Gemini Embedding 2 + Supabase"
)


# =====================================================================
# 26. TABS
# =====================================================================

tab_search, tab_upload = st.tabs([

    "🔍 TÌM KIẾM MÃ HÀNG",

    "📦 NẠP KHO HÀNG LOẠT"

])


# =====================================================================
# =====================================================================
# TAB 1
# TÌM KIẾM
# =====================================================================
# =====================================================================

with tab_search:

    st.header(
        "🔍 Tìm mã hàng tương đồng qua ảnh"
    )


    st.info(
        "AI sẽ tự nhận diện loại hàng. "
        "Bạn không cần chọn Quần dài / Cargo / Jacket..."
    )


    search_file = st.file_uploader(

        "📷 Tải ảnh Sketch / ảnh mẫu cần tìm",

        type=[
            "jpg",
            "jpeg",
            "png",
            "webp"
        ],

        key="search_upload_v26"

    )


    if search_file:

        search_bytes = (
            search_file
            .getvalue()
        )


        col_a, col_b = st.columns(
            [1, 2]
        )


        with col_a:

            st.image(
                search_bytes,
                caption=search_file.name,
                use_container_width=True
            )


        with col_b:

            if st.button(

                "🚀 PHÂN TÍCH & TÌM MÃ TƯƠNG ĐỒNG",

                type="primary",

                use_container_width=True,

                key="btn_search_v26"

            ):

                try:

                    # -------------------------------------------------
                    # AI CATEGORY
                    # -------------------------------------------------

                    with st.spinner(
                        "🤖 Gemini đang nhận diện cấu trúc sản phẩm..."
                    ):

                        ai_result = (
                            analyze_garment_with_gemini(
                                search_bytes
                            )
                        )


                    st.session_state[
                        "search_ai_result_v26"
                    ] = ai_result


                    st.session_state[
                        "search_file_name_v26"
                    ] = search_file.name


                    display_ai_result(
                        ai_result
                    )


                    # -------------------------------------------------
                    # IMAGE EMBEDDING
                    # -------------------------------------------------

                    with st.spinner(
                        "🧠 Gemini đang tạo image embedding..."
                    ):

                        embedding = (
                            create_image_embedding(
                                search_bytes
                            )
                        )


                    # -------------------------------------------------
                    # SEARCH
                    # -------------------------------------------------

                    with st.spinner(
                        "🔎 Đang tìm mã tương đồng trong kho..."
                    ):

                        results = (
                            search_similar_products(

                                embedding,

                                ai_result[
                                    "category"
                                ],

                                TOP_K

                            )
                        )


                    st.session_state[
                        "search_results_v26"
                    ] = results


                    st.success(
                        "✅ Phân tích và tìm kiếm hoàn tất."
                    )


                    display_search_results(
                        results
                    )


                except Exception as e:

                    st.error(
                        f"❌ Tìm kiếm lỗi: {e}"
                    )


    # ---------------------------------------------------------------
    # SHOW PREVIOUS RESULTS
    # ---------------------------------------------------------------

    elif (
        st.session_state[
            "search_results_v26"
        ]
    ):

        ai_result = (
            st.session_state[
                "search_ai_result_v26"
            ]
        )


        if ai_result:

            display_ai_result(
                ai_result
            )


        display_search_results(

            st.session_state[
                "search_results_v26"
            ]

        )


# =====================================================================
# =====================================================================
# TAB 2
# NẠP KHO
# =====================================================================
# =====================================================================

with tab_upload:

    st.header(
        "📦 Nạp mã hàng vào kho"
    )


    st.info(
        "AI tự nhận diện category. "
        "Tên file sẽ được dùng làm Mã hàng."
    )


    # ================================================================
    # FILE UPLOADER
    # ================================================================

    new_files = st.file_uploader(

        "📤 Chọn ảnh sản phẩm cần nạp kho",

        type=[
            "jpg",
            "jpeg",
            "png",
            "webp"
        ],

        accept_multiple_files=True,

        key="warehouse_file_picker_v26"

    )


    if new_files:

        added_count = add_pending_files(
            new_files
        )


        if added_count:

            st.success(
                f"Đã thêm {added_count} file vào danh sách chờ."
            )


    # ================================================================
    # PENDING FILES
    # ================================================================

    pending_files = (
        st.session_state[
            "pending_uploads_v26"
        ]
    )


    st.markdown(
        "### 📋 Danh sách file đang chờ nạp"
    )


    if not pending_files:

        st.warning(
            "Chưa có file nào đang chờ."
        )


    else:

        st.write(
            f"Đang chờ **{len(pending_files)}** file."
        )


        # ------------------------------------------------------------
        # CLEAR WAITING FILES
        # ------------------------------------------------------------

        if st.button(

            "🗑️ XÓA TOÀN BỘ FILE ĐANG CHỜ",

            key="clear_pending_v26",

            use_container_width=True

        ):

            clear_pending_files()

            st.rerun()


        # ------------------------------------------------------------
        # DISPLAY FILES
        # ------------------------------------------------------------

        for index, item in enumerate(
            pending_files
        ):

            col1, col2, col3 = st.columns(
                [1, 4, 1]
            )


            with col1:

                try:

                    st.image(
                        item["bytes"],
                        width=100
                    )

                except Exception:

                    st.write(
                        "📷"
                    )


            with col2:

                st.markdown(
                    f"**{item['name']}**"
                )


                st.caption(
                    "Chưa lưu vào kho"
                )


            with col3:

                if st.button(

                    "❌",

                    key=f"remove_pending_{index}"

                ):

                    remove_pending_file(
                        index
                    )

                    st.rerun()


    # ================================================================
    # UPLOAD ALL
    # ================================================================

    if pending_files:

        st.divider()


        if st.button(

            "📤 BẮT ĐẦU NẠP TOÀN BỘ VÀO KHO",

            type="primary",

            use_container_width=True,

            key="upload_all_v26"

        ):

            total = len(
                pending_files
            )


            progress = st.progress(
                0
            )


            status = st.empty()


            success_count = 0

            failed_count = 0


            files_to_process = list(
                pending_files
            )


            for index, item in enumerate(
                files_to_process
            ):

                filename = item[
                    "name"
                ]


                file_bytes = item[
                    "bytes"
                ]


                product_code = (
                    extract_product_code(
                        filename
                    )
                )


                status.write(
                    f"🤖 AI đang xử lý "
                    f"**{product_code}** "
                    f"({index + 1}/{total})"
                )


                try:

                    # =================================================
                    # STEP 1
                    # GEMINI VISION
                    # =================================================

                    ai_result = (
                        analyze_garment_with_gemini(
                            file_bytes
                        )
                    )


                    category = (
                        ai_result[
                            "category"
                        ]
                    )


                    st.write(
                        f"🤖 {product_code}: "
                        f"**{category}** "
                        f"({ai_result['confidence']:.0f}%)"
                    )


                    # =================================================
                    # STEP 2
                    # IMAGE EMBEDDING
                    # =================================================

                    embedding = (
                        create_image_embedding(
                            file_bytes
                        )
                    )


                    # =================================================
                    # STEP 3
                    # STORAGE
                    # =================================================

                    (
                        image_url,
                        storage_path

                    ) = upload_image_to_storage(

                        file_bytes,

                        filename

                    )


                    # =================================================
                    # STEP 4
                    # DATABASE
                    # =================================================

                    save_product_to_database(

                        product_code=
                            product_code,

                        image_url=
                            image_url,

                        storage_path=
                            storage_path,

                        category=
                            category,

                        ai_analysis=
                            ai_result,

                        embedding=
                            embedding

                    )


                    success_count += 1


                    st.success(
                        f"✅ {filename} → "
                        f"{category}"
                    )


                except Exception as e:

                    failed_count += 1


                    st.error(
                        f"❌ {filename}: {e}"
                    )


                progress.progress(
                    (index + 1)
                    /
                    total
                )


            status.empty()


            # =========================================================
            # REMOVE PROCESSED FILES FROM WAITING LIST
            #
            # Chỉ xóa khỏi danh sách chờ.
            # KHÔNG xóa ảnh trong Storage.
            # KHÔNG xóa record trong products.
            # =========================================================

            st.session_state[
                "pending_uploads_v26"
            ] = []


            st.success(
                f"🎉 Hoàn tất! "
                f"Thành công: {success_count} | "
                f"Lỗi: {failed_count}"
            )


            st.info(
                "Danh sách file chờ đã được làm sạch. "
                "Dữ liệu đã lưu trong kho vẫn còn nguyên."
            )


# =====================================================================
# 27. FOOTER
# =====================================================================

st.divider()

st.caption(
    "AI Garment Similarity Search "
    f"| {APP_VERSION} "
    "| Gemini Vision + Gemini Embedding 2 + Supabase pgvector"
)
