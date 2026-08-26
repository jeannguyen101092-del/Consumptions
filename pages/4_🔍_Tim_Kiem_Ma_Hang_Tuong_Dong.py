# =====================================================================
# 🔍 TÌM KIẾM MÃ HÀNG TƯƠNG ĐỒNG
# 📦 NẠP KHO HÀNG LOẠT
#
# VERSION V4.0 - COMPLETE MASTER
#
# GEMINI 2.5 FLASH
#       ↓
# GARMENT CATEGORY RECOGNITION
#       ↓
# HARD CATEGORY RULE
#       ↓
# LOCAL CLIP IMAGE EMBEDDING
#       ↓
# SUPABASE
#       ↓
# CATEGORY-LOCKED SIMILARITY SEARCH
#
# IMPORTANT
# - KHÔNG dùng HF Vision API
# - KHÔNG hard-code secret
# - Tab 1 không cho user chọn category
# - Tab 2 AI tự nhận category
# - Clear uploader KHÔNG xóa database
# =====================================================================


# =====================================================================
# 0. IMPORT
# =====================================================================

import io
import os
import re
import json
import hashlib

import streamlit as st
import pandas as pd
import numpy as np

from PIL import Image

from supabase import create_client, Client

from google import genai
from google.genai import types


# =====================================================================
# 1. STREAMLIT CONFIG
# =====================================================================

st.set_page_config(

    page_title="AI Tìm Kiếm Mã Hàng",

    page_icon="🔍",

    layout="wide"

)


# =====================================================================
# 2. SESSION STATE
# =====================================================================

DEFAULT_SESSION = {

    "search_results": [],

    "search_category": "",

    "search_ai_result": None,

    "warehouse_ai_results": [],

    "warehouse_upload_key": 0,

    "search_upload_key": 0,

}


for key, value in DEFAULT_SESSION.items():

    if key not in st.session_state:

        st.session_state[key] = value


# =====================================================================
# 3. READ SECRETS
# =====================================================================

def get_secret(name):

    """
    Đọc secret từ Streamlit Secrets.
    Không hard-code key trong GitHub.
    """

    try:

        value = st.secrets.get(
            name,
            None
        )

    except Exception:

        value = None


    if value is None:

        value = os.getenv(
            name,
            None
        )


    if value is None:

        return None


    value = str(
        value
    ).strip()


    if not value:

        return None


    return value


# ---------------------------------------------------------------------
# SUPABASE
# ---------------------------------------------------------------------

SUPABASE_URL = get_secret(
    "SUPABASE_URL"
)

SUPABASE_KEY = get_secret(
    "SUPABASE_KEY"
)


# ---------------------------------------------------------------------
# GEMINI
# ---------------------------------------------------------------------

GEMINI_API_KEY = get_secret(
    "GEMINI_API_KEY"
)


# =====================================================================
# 4. SECRET VALIDATION
# =====================================================================

missing_keys = []


if not SUPABASE_URL:

    missing_keys.append(
        "SUPABASE_URL"
    )


if not SUPABASE_KEY:

    missing_keys.append(
        "SUPABASE_KEY"
    )


if not GEMINI_API_KEY:

    missing_keys.append(
        "GEMINI_API_KEY"
    )


if missing_keys:

    st.error(
        "❌ Không đọc được thông tin bảo mật từ "
        "Streamlit Secrets."
    )

    st.markdown(
        "Hãy kiểm tra các key sau:"
    )

    for key in missing_keys:

        st.code(
            key
        )

    st.stop()


# =====================================================================
# 5. SUPABASE CLIENT
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
# 6. GEMINI CLIENT
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
# 7. GEMINI MODEL
# =====================================================================

GEMINI_MODEL = (
    "gemini-2.5-flash"
)


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

CATEGORY_LIST = [

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
# 10. CATEGORY ALIAS
# =====================================================================

CATEGORY_ALIASES = {

    "JUMPSUIT":
        "Áo liền quần",

    "ONE PIECE":
        "Áo liền quần",

    "ONE-PIECE":
        "Áo liền quần",

    "ROMPER":
        "Áo liền quần",

    "COVERALL":
        "Áo liền quần",

    "COVERALLS":
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
        "Skirt"

}


# =====================================================================
# 11. GARMENT PROMPT
# =====================================================================

GARMENT_PROMPT = r"""
You are a SENIOR APPAREL TECHNICAL DESIGNER and
COMMERCIAL GARMENT RECOGNITION AI.

Analyze the uploaded garment image/sketch.

Your job is to identify the TRUE garment construction,
not merely visual similarity.

===========================================================
CRITICAL RULE 1 — ONE PIECE / JUMPSUIT
===========================================================

If the upper body and lower body are physically connected
as ONE garment:

category = "Áo liền quần"

Set:

one_piece = true

A one-piece garment MUST NEVER be classified as:

"Quần túi hộp"

even when it has cargo pockets.

===========================================================
CRITICAL RULE 2 — BIB OVERALL
===========================================================

If the garment has:

- bib front
- shoulder straps
- pants construction

category = "Quần yếm"

Set:

bib = true
shoulder_straps = true

Bib overall MUST NEVER be cargo pants.

===========================================================
CRITICAL RULE 3 — CARGO
===========================================================

"Quần túi hộp" is allowed ONLY if:

1. It is a SEPARATE pants garment.
2. Upper body and lower body are NOT connected.
3. Obvious external cargo/patch pockets exist.
4. Cargo pockets are located on the side legs.

Set:

one_piece = false
cargo_pockets = true

If cargo pockets are not clearly visible:

cargo_pockets = false

DO NOT GUESS.

===========================================================
CRITICAL RULE 4 — JEANS
===========================================================

Separate denim pants:

category = "Quần jean"

denim = true

===========================================================
CRITICAL RULE 5 — JOGGER
===========================================================

Separate pants with clear jogger construction,
especially elastic/rib ankle cuffs:

category = "Quần jogger"

jogger_cuffs = true

===========================================================
JACKET
===========================================================

Separate upper-body outerwear:

category = "Jacket"

===========================================================
DRESS
===========================================================

One-piece dress with skirt/dress construction:

category = "Dress"

Do NOT confuse dress with jumpsuit.

===========================================================
AVAILABLE CATEGORIES
===========================================================

Only use:

Áo liền quần
Quần yếm
Quần túi hộp
Quần jean
Quần jogger
Quần short
Quần dài
Jacket
Áo
T-shirt
Polo
Hoodie
Skirt
Dress

===========================================================
DECISION ORDER
===========================================================

1. Determine whether one-piece.
2. Determine bib overall.
3. Determine whether separate pants.
4. If separate pants, verify cargo pockets.
5. Verify denim.
6. Verify jogger construction.
7. Determine normal garment category.

===========================================================
OUTPUT
===========================================================

Return ONLY JSON.

No Markdown.

No explanation outside JSON.

category and confidence are REQUIRED.

Keep response SHORT.

Example:

{
  "category": "Áo",
  "confidence": 98,
  "one_piece": false,
  "bib": false,
  "shoulder_straps": false,
  "cargo_pockets": false,
  "denim": false,
  "jogger_cuffs": false,
  "hood": false,
  "reason": "Separate upper body garment."
}
"""


# =====================================================================
# 12. JSON EXTRACTOR
# =====================================================================

def extract_json(text):

    if not text:

        raise Exception(
            "Gemini không trả dữ liệu."
        )


    text = str(
        text
    ).strip()


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
    # FIND JSON
    # ---------------------------------------------------------------

    start = text.find(
        "{"
    )


    if start < 0:

        raise Exception(

            "Gemini không trả JSON.\n\n"
            +
            text[:2000]

        )


    json_text = text[
        start:
    ]


    # ---------------------------------------------------------------
    # NORMAL JSON
    # ---------------------------------------------------------------

    try:

        return json.loads(
            json_text
        )

    except Exception:

        pass


    # ---------------------------------------------------------------
    # FALLBACK FOR TRUNCATED JSON
    # ---------------------------------------------------------------

    result = {}


    # CATEGORY
    m = re.search(

        r'"category"\s*:\s*"([^"]+)"',

        json_text,

        flags=re.I

    )

    if m:

        result[
            "category"
        ] = m.group(1)


    # CONFIDENCE
    m = re.search(

        r'"confidence"\s*:\s*([0-9]+(?:\.[0-9]+)?)',

        json_text,

        flags=re.I

    )

    if m:

        try:

            result[
                "confidence"
            ] = float(
                m.group(1)
            )

        except Exception:

            result[
                "confidence"
            ] = 0

    else:

        result[
            "confidence"
        ] = 0


    # BOOLEAN
    boolean_fields = [

        "one_piece",

        "bib",

        "shoulder_straps",

        "cargo_pockets",

        "denim",

        "jogger_cuffs",

        "hood"

    ]


    for field in boolean_fields:

        m = re.search(

            rf'"{field}"\s*:\s*(true|false)',

            json_text,

            flags=re.I

        )


        if m:

            result[field] = (

                m.group(1).lower()
                ==
                "true"

            )

        else:

            result[field] = False


    # REASON
    m = re.search(

        r'"reason"\s*:\s*"([^"]*)"', 

        json_text,

        flags=re.I

    )


    if m:

        result[
            "reason"
        ] = m.group(1)

    else:

        result[
            "reason"
        ] = ""


    if not result.get(
        "category"
    ):

        raise Exception(

            "Gemini không trả category.\n\n"
            +
            text[:2000]

        )


    return result


# =====================================================================
# 13. NORMALIZE GARMENT RESULT
# =====================================================================

def normalize_garment_result(
    result
):

    if not isinstance(
        result,
        dict
    ):

        raise Exception(
            "Gemini result không hợp lệ."
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


    # ALIAS
    if category_upper in CATEGORY_ALIASES:

        category = CATEGORY_ALIASES[
            category_upper
        ]


    # INVALID
    if category not in CATEGORY_LIST:

        category = "Quần dài"


    result[
        "category"
    ] = category


    # BOOLEAN
    boolean_fields = [

        "one_piece",

        "bib",

        "shoulder_straps",

        "cargo_pockets",

        "denim",

        "jogger_cuffs",

        "hood"

    ]


    for field in boolean_fields:

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
                    "1"
                ]

            )


        result[field] = bool(
            value
        )


    # ================================================================
    # HARD RULE 1
    # ONE PIECE
    # ================================================================

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


        # One piece cannot be cargo
        result[
            "cargo_pockets"
        ] = False


    # ================================================================
    # HARD RULE 2
    # BIB
    # ================================================================

    elif (

        result["bib"]

        and

        result["shoulder_straps"]

    ):

        result[
            "category"
        ] = "Quần yếm"


        result[
            "cargo_pockets"
        ] = False


    # ================================================================
    # HARD RULE 3
    # CARGO REQUIRES CARGO POCKET
    # ================================================================

    elif (

        result[
            "category"
        ]
        ==
        "Quần túi hộp"

        and

        not result[
            "cargo_pockets"
        ]

    ):

        result[
            "category"
        ] = "Quần dài"


    # ================================================================
    # HARD RULE 4
    # DENIM
    # ================================================================

    elif (

        result[
            "denim"
        ]

        and

        result[
            "category"
        ]
        ==
        "Quần dài"

    ):

        result[
            "category"
        ] = "Quần jean"


    # ================================================================
    # HARD RULE 5
    # JOGGER
    # ================================================================

    elif (

        result[
            "jogger_cuffs"
        ]

        and

        result[
            "category"
        ]
        ==
        "Quần dài"

    ):

        result[
            "category"
        ] = "Quần jogger"


    # CONFIDENCE
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


    return result


# =====================================================================
# 14. GEMINI IMAGE ANALYSIS
# =====================================================================

def analyze_garment_with_gemini(
    image_bytes
):

    try:

        response = (

            gemini_client
            .models
            .generate_content(

                model=GEMINI_MODEL,

                contents=[

                    types.Part.from_bytes(

                        data=image_bytes,

                        mime_type="image/jpeg"

                    ),

                    GARMENT_PROMPT

                ],

                config=types.GenerateContentConfig(

                    temperature=0,

                    max_output_tokens=350

                )

            )

        )


    except Exception as e:

        raise Exception(

            "Gemini Vision lỗi: "
            +
            str(e)

        )


    try:

        text = response.text

    except Exception as e:

        raise Exception(

            "Không đọc được Gemini response: "
            +
            str(e)

        )


    if not text:

        raise Exception(
            "Gemini trả response rỗng."
        )


    result = extract_json(
        text
    )


    result = normalize_garment_result(
        result
    )


    return result


# =====================================================================
# 15. CLIP MODEL LOADER
# =====================================================================

@st.cache_resource(
    show_spinner=False
)
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


        return (
            processor,
            model
        )


    except Exception as e:

        raise Exception(

            "Không tải được CLIP model: "
            +
            str(e)

        )


# =====================================================================
# 16. CLIP EMBEDDING
# =====================================================================

def get_clip_embedding(
    image_bytes
):

    try:

        import torch


        processor, model = (
            load_clip_model()
        )


        image = Image.open(
            io.BytesIO(
                image_bytes
            )
        ).convert(
            "RGB"
        )


        inputs = processor(

            images=image,

            return_tensors="pt"

        )


        with torch.no_grad():

            outputs = model.get_image_features(
                **inputs
            )


        # ============================================================
        # FIX:
        #
        # Không gọi ndim trực tiếp trên
        # BaseModelOutputWithPooling.
        # ============================================================

        if hasattr(
            outputs,
            "pooler_output"
        ):

            embedding = (
                outputs.pooler_output
            )

        elif hasattr(
            outputs,
            "image_embeds"
        ):

            embedding = (
                outputs.image_embeds
            )

        elif hasattr(
            outputs,
            "last_hidden_state"
        ):

            embedding = (
                outputs.last_hidden_state
            )

        else:

            embedding = outputs


        # ============================================================
        # Tensor validation
        # ============================================================

        if not torch.is_tensor(
            embedding
        ):

            raise Exception(
                "CLIP không trả Tensor."
            )


        # ============================================================
        # Flatten
        # ============================================================

        embedding = embedding.reshape(
            -1
        )


        # ============================================================
        # Normalize
        # ============================================================

        embedding = (

            embedding
            /
            embedding.norm(
                p=2
            )

        )


        vector = (
            embedding
            .cpu()
            .numpy()
            .astype(
                np.float32
            )
            .tolist()
        )


        if len(vector) != CLIP_DIMENSION:

            raise Exception(

                f"CLIP dimension sai: "
                f"{len(vector)}. "
                f"Cần {CLIP_DIMENSION}."

            )


        return vector


    except Exception as e:

        raise Exception(

            "CLIP embedding lỗi: "
            +
            str(e)

        )


# =====================================================================
# 17. IMAGE STORAGE
# =====================================================================

BUCKET_NAME = (
    "product-images"
)


def upload_image_to_storage(
    file_bytes,
    filename
):

    try:

        # -------------------------------------------------------------
        # Create safe unique path
        # -------------------------------------------------------------

        ext = ".jpg"

        original_ext = (
            filename
            .rsplit(
                ".",
                1
            )[-1]
            .lower()
        )


        if original_ext in [
            "png",
            "jpg",
            "jpeg",
            "webp"
        ]:

            ext = (
                "."
                +
                original_ext
            )


        base_name = (
            filename
            .rsplit(
                ".",
                1
            )[0]
        )


        safe_name = re.sub(

            r"[^A-Za-z0-9_\-]",

            "_",

            base_name

        )


        file_hash = hashlib.md5(
            file_bytes
        ).hexdigest()[:12]


        storage_path = (

            safe_name
            +
            "_"
            +
            file_hash
            +
            ext

        )


        supabase.storage.from_(
            BUCKET_NAME
        ).upload(

            path=storage_path,

            file=file_bytes,

            file_options={

                "content-type":
                    "image/jpeg",

                "upsert":
                    "true"

            }

        )


        public_url = (

            supabase
            .storage
            .from_(
                BUCKET_NAME
            )
            .get_public_url(
                storage_path
            )

        )


        return (
            public_url,
            storage_path
        )


    except Exception as e:

        raise Exception(

            "Supabase Storage lỗi: "
            +
            str(e)

        )


# =====================================================================
# 18. PRODUCT CODE
# =====================================================================

def get_product_code(
    filename
):

    base = filename.rsplit(
        ".",
        1
    )[0]


    return str(
        base
    ).strip().upper()


# =====================================================================
# 19. SAVE PRODUCT
# =====================================================================

def save_product_to_database(

    product_code,

    image_url,

    storage_path,

    category,

    embedding,

    ai_result

):

    payload = {

        "product_code":
            product_code,

        "image_url":
            image_url,

        "category":
            category,

        "embedding":
            embedding

    }


    # ---------------------------------------------------------------
    # Optional metadata columns
    #
    # KHÔNG gửi các field này mặc định vì database hiện tại của user
    # có thể chưa có.
    # ---------------------------------------------------------------

    response = (

        supabase
        .table(
            "products"
        )
        .upsert(

            payload,

            on_conflict="product_code"

        )
        .execute()

    )


    return response


# =====================================================================
# 20. SEARCH SIMILAR PRODUCTS
# =====================================================================

def search_similar_products(

    query_embedding,

    category,

    threshold=0.35,

    match_count=8

):

    # ================================================================
    # CATEGORY-LOCKED SEARCH
    # ================================================================

    try:

        response = (

            supabase
            .rpc(

                "match_products_v2",

                {

                    "query_embedding":
                        query_embedding,

                    "match_threshold":
                        threshold,

                    "match_count":
                        match_count,

                    "filter_category":
                        category

                }

            )
            .execute()

        )


        return (
            response.data
            or []
        )


    except Exception as e:

        raise Exception(

            "Supabase similarity search lỗi: "
            +
            str(e)

        )


# =====================================================================
# 21. PROCESS ONE FILE
# =====================================================================

def process_product_file(

    uploaded_file,

    save_to_database=True

):

    filename = (
        uploaded_file.name
    )


    product_code = (
        get_product_code(
            filename
        )
    )


    image_bytes = (
        uploaded_file.getvalue()
    )


    if not image_bytes:

        raise Exception(
            "File ảnh rỗng."
        )


    # ================================================================
    # GEMINI
    # ================================================================

    ai_result = (
        analyze_garment_with_gemini(
            image_bytes
        )
    )


    category = (
        ai_result[
            "category"
        ]
    )


    # ================================================================
    # CLIP
    # ================================================================

    embedding = (
        get_clip_embedding(
            image_bytes
        )
    )


    # ================================================================
    # STORAGE
    # ================================================================

    image_url = None

    storage_path = None


    if save_to_database:

        (

            image_url,

            storage_path

        ) = upload_image_to_storage(

            image_bytes,

            filename

        )


        # ============================================================
        # DATABASE
        # ============================================================

        save_product_to_database(

            product_code=

                product_code,

            image_url=

                image_url,

            storage_path=

                storage_path,

            category=

                category,

            embedding=

                embedding,

            ai_result=

                ai_result

        )


    return {

        "filename":
            filename,

        "product_code":
            product_code,

        "category":
            category,

        "confidence":
            ai_result.get(
                "confidence",
                0
            ),

        "one_piece":
            ai_result.get(
                "one_piece",
                False
            ),

        "bib":
            ai_result.get(
                "bib",
                False
            ),

        "cargo_pockets":
            ai_result.get(
                "cargo_pockets",
                False
            ),

        "denim":
            ai_result.get(
                "denim",
                False
            ),

        "jogger_cuffs":
            ai_result.get(
                "jogger_cuffs",
                False
            ),

        "reason":
            ai_result.get(
                "reason",
                ""
            ),

        "image_url":
            image_url,

        "embedding":
            embedding

    }


# =====================================================================
# 22. HEADER
# =====================================================================

st.title(
    "🔍 AI TÌM KIẾM MÃ HÀNG TƯƠNG ĐỒNG"
)

st.caption(

    "Gemini Vision + CLIP + Supabase"

)


# =====================================================================
# 23. TABS
# =====================================================================

tab1, tab2 = st.tabs(

    [

        "🔍 TÌM KIẾM MÃ HÀNG",

        "📦 NẠP KHO HÀNG LOẠT"

    ]

)


# #####################################################################
# #####################################################################
#
# TAB 1
#
# #####################################################################
# #####################################################################

with tab1:

    st.header(
        "🔍 Tìm mã hàng tương đồng qua ảnh"
    )


    st.info(

        "AI sẽ tự nhận diện loại hàng. "
        "Không cần chọn category thủ công."

    )


    # ================================================================
    # UPLOAD
    # ================================================================

    uploaded_search = st.file_uploader(

        "📷 Tải ảnh Sketch / mẫu cần tìm",

        type=[

            "jpg",

            "jpeg",

            "png",

            "webp"

        ],

        key=f"search_file_{st.session_state.search_upload_key}"

    )


    # ================================================================
    # CLEAR CURRENT FILE
    #
    # KHÔNG XÓA SUPABASE
    # ================================================================

    col_clear_1, col_clear_2 = st.columns(
        [1, 5]
    )


    with col_clear_1:

        if st.button(

            "🗑️ Xóa file hiện tại",

            key="clear_search_file"

        ):

            st.session_state[
                "search_upload_key"
            ] += 1


            st.session_state[
                "search_ai_result"
            ] = None


            st.session_state[
                "search_results"
            ] = []


            st.rerun()


    # ================================================================
    # SHOW IMAGE
    # ================================================================

    if uploaded_search:

        col_img, col_ai = st.columns(

            [1, 1]

        )


        with col_img:

            st.image(

                uploaded_search,

                caption=
                    uploaded_search.name,

                width=350

            )


        # ============================================================
        # RUN SEARCH
        # ============================================================

        if st.button(

            "🚀 AI NHẬN DIỆN + TÌM TƯƠNG ĐỒNG",

            type="primary",

            key="run_similarity_search"

        ):

            try:

                image_bytes = (
                    uploaded_search.getvalue()
                )


                # ====================================================
                # GEMINI CATEGORY
                # ====================================================

                with st.spinner(
                    "🤖 Gemini đang nhận diện garment..."
                ):

                    ai_result = (

                        analyze_garment_with_gemini(

                            image_bytes

                        )

                    )


                st.session_state[
                    "search_ai_result"
                ] = ai_result


                category = (
                    ai_result[
                        "category"
                    ]
                )


                # ====================================================
                # SHOW AI
                # ====================================================

                with col_ai:

                    st.success(
                        "✅ AI nhận diện thành công"
                    )


                    st.metric(

                        "Category",

                        category

                    )


                    st.metric(

                        "Confidence",

                        f"{ai_result.get('confidence', 0):.1f}%"

                    )


                    st.write(

                        "One piece:",

                        "✅"
                        if ai_result.get(
                            "one_piece",
                            False
                        )
                        else
                        "❌"

                    )


                    st.write(

                        "Bib:",

                        "✅"
                        if ai_result.get(
                            "bib",
                            False
                        )
                        else
                        "❌"

                    )


                    st.write(

                        "Cargo pockets:",

                        "✅"
                        if ai_result.get(
                            "cargo_pockets",
                            False
                        )
                        else
                        "❌"

                    )


                    if ai_result.get(
                        "reason"
                    ):

                        st.caption(

                            ai_result[
                                "reason"
                            ]

                        )


                # ====================================================
                # CLIP
                # ====================================================

                with st.spinner(
                    "🧠 CLIP đang tạo vector ảnh..."
                ):

                    query_embedding = (

                        get_clip_embedding(

                            image_bytes

                        )

                    )


                # ====================================================
                # SEARCH
                # ====================================================

                with st.spinner(

                    f"🔎 Đang tìm trong nhóm: "
                    f"{category}"

                ):

                    results = (

                        search_similar_products(

                            query_embedding,

                            category,

                            threshold=0.35,

                            match_count=8

                        )

                    )


                st.session_state[
                    "search_results"
                ] = results


                # ====================================================
                # RESULT
                # ====================================================

                st.divider()


                st.subheader(

                    f"🎯 Kết quả trong nhóm: "
                    f"{category}"

                )


                if not results:

                    st.warning(

                        "Không tìm thấy mã hàng tương đồng "
                        "trong đúng category này."

                    )

                else:

                    result_cols = st.columns(
                        len(results)
                    )


                    for idx, item in enumerate(
                        results
                    ):

                        with result_cols[idx]:

                            similarity = float(

                                item.get(
                                    "similarity",
                                    0
                                )

                            )


                            st.metric(

                                "Độ tương đồng",

                                f"{similarity * 100:.2f}%"

                            )


                            st.markdown(

                                f"### "
                                f"{item.get('product_code', 'N/A')}"

                            )


                            if item.get(
                                "image_url"
                            ):

                                st.image(

                                    item[
                                        "image_url"
                                    ],

                                    use_container_width=True

                                )


                            st.caption(

                                "Category: "
                                +
                                str(

                                    item.get(
                                        "category",
                                        category
                                    )

                                )

                            )


            except Exception as e:

                st.error(
                    "❌ " + str(e)
                )


# #####################################################################
# #####################################################################
#
# TAB 2
#
# #####################################################################
# #####################################################################

with tab2:

    st.header(
        "📦 Nạp kho hàng loạt"
    )


    st.info(

        "Tên file sẽ được dùng làm mã hàng. "
        "AI tự nhận diện category — không cần chọn dòng hàng."

    )


    # ================================================================
    # FILE UPLOADER
    #
    # KEY ĐỔI KHI NHẤN CLEAR
    # ================================================================

    uploaded_files = st.file_uploader(

        "📂 Chọn nhiều ảnh sản phẩm",

        type=[

            "jpg",

            "jpeg",

            "png",

            "webp"

        ],

        accept_multiple_files=True,

        key=(

            f"warehouse_files_"
            f"{st.session_state.warehouse_upload_key}"

        )

    )


    # ================================================================
    # CLEAR CURRENT QUEUE
    #
    # CHỈ XÓA FILE ĐANG CHỜ TRÊN GIAO DIỆN
    #
    # KHÔNG XÓA:
    # - products
    # - product-images
    # - dữ liệu đã upload
    # ================================================================

    col_clear_a, col_clear_b = st.columns(
        [1, 5]
    )


    with col_clear_a:

        if st.button(

            "🗑️ Xóa file đang chờ",

            key="clear_warehouse_queue"

        ):

            st.session_state[
                "warehouse_upload_key"
            ] += 1


            st.session_state[
                "warehouse_ai_results"
            ] = []


            st.rerun()


    # ================================================================
    # FILE COUNT
    # ================================================================

    if uploaded_files:

        st.success(

            f"📂 Đã chọn "
            f"**{len(uploaded_files)}** "
            f"file."

        )


        # ============================================================
        # PROCESS BUTTON
        # ============================================================

        if st.button(

            "📤 AI NHẬN DIỆN + LƯU TOÀN BỘ VÀO KHO",

            type="primary",

            key="process_warehouse"

        ):

            progress = st.progress(
                0
            )


            status = st.empty()


            success_count = 0

            fail_count = 0

            results = []


            # ========================================================
            # LOOP
            # ========================================================

            for index, file in enumerate(
                uploaded_files
            ):

                filename = file.name


                status.text(

                    f"⏳ "
                    f"{index + 1}/"
                    f"{len(uploaded_files)} — "
                    f"{filename}"

                )


                try:

                    result = (

                        process_product_file(

                            file,

                            save_to_database=True

                        )

                    )


                    results.append(
                        result
                    )


                    success_count += 1


                except Exception as e:

                    fail_count += 1


                    st.error(

                        f"❌ "
                        f"{filename}: "
                        f"{e}"

                    )


                progress.progress(

                    (index + 1)
                    /
                    len(uploaded_files)

                )


            status.empty()


            st.session_state[
                "warehouse_ai_results"
            ] = results


            # ========================================================
            # SUMMARY
            # ========================================================

            st.divider()


            if fail_count == 0:

                st.success(

                    f"🎉 Hoàn thành "
                    f"{success_count}/"
                    f"{len(uploaded_files)} "
                    f"mã hàng."

                )

            else:

                st.warning(

                    f"Hoàn thành: "
                    f"{success_count} thành công / "
                    f"{fail_count} lỗi."

                )


    # ================================================================
    # DISPLAY AI RESULTS
    # ================================================================

    warehouse_results = st.session_state.get(

        "warehouse_ai_results",

        []

    )


    if warehouse_results:

        st.divider()


        st.subheader(
            "🤖 Kết quả AI nhận diện"
        )


        table_data = []


        for item in warehouse_results:

            table_data.append({

                "Mã hàng":
                    item.get(
                        "product_code",
                        ""
                    ),

                "Category":
                    item.get(
                        "category",
                        ""
                    ),

                "Confidence":
                    f"{item.get('confidence', 0):.1f}%",

                "One Piece":
                    "YES"
                    if item.get(
                        "one_piece",
                        False
                    )
                    else
                    "NO",

                "Bib":
                    "YES"
                    if item.get(
                        "bib",
                        False
                    )
                    else
                    "NO",

                "Cargo":
                    "YES"
                    if item.get(
                        "cargo_pockets",
                        False
                    )
                    else
                    "NO",

                "Denim":
                    "YES"
                    if item.get(
                        "denim",
                        False
                    )
                    else
                    "NO",

                "Jogger":
                    "YES"
                    if item.get(
                        "jogger_cuffs",
                        False
                    )
                    else
                    "NO"

            })


        df_results = pd.DataFrame(
            table_data
        )


        st.dataframe(

            df_results,

            use_container_width=True,

            hide_index=True

        )


# =====================================================================
# 24. FOOTER
# =====================================================================

st.divider()


st.caption(

    "AI Garment Search V4.0 | "
    "Gemini Vision + Local CLIP + Supabase"

)
