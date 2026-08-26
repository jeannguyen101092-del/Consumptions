# =====================================================================
# 🔍 AI TÌM KIẾM MÃ HÀNG TƯƠNG ĐỒNG
# 📦 NẠP KHO HÀNG LOẠT
#
# VERSION V4.2 - MASTER COMPLETE
#
# GEMINI VISION
#      ↓
# GARMENT CATEGORY RECOGNITION
#      ↓
# HARD CATEGORY RULE
#      ↓
# LOCAL CLIP IMAGE EMBEDDING
#      ↓
# SUPABASE STORAGE
#      ↓
# SUPABASE PRODUCTS
#      ↓
# CATEGORY-LOCKED SIMILARITY SEARCH
#
# =====================================================================
# IMPORTANT
#
# 1. Không dùng Hugging Face Vision API
# 2. Không hard-code API key
# 3. Tab 1 AI tự nhận category
# 4. Tab 2 AI tự nhận category
# 5. Category được khóa khi tìm kiếm
# 6. Nút xóa file chỉ xóa file đang chờ trên màn hình
# 7. Không xóa dữ liệu đã lưu trong Supabase
# =====================================================================


# =====================================================================
# 1. IMPORT
# =====================================================================

import io
import os
import re
import json
import hashlib

import numpy as np
import pandas as pd
import streamlit as st

from PIL import Image

from supabase import create_client, Client

from google import genai
from google.genai import types


# =====================================================================
# 2. STREAMLIT CONFIG
# =====================================================================

st.set_page_config(

    page_title="AI Tìm Kiếm Mã Hàng",

    page_icon="🔍",

    layout="wide"

)


# =====================================================================
# 3. SESSION STATE
# =====================================================================

if "search_upload_key" not in st.session_state:

    st.session_state.search_upload_key = 0


if "warehouse_upload_key" not in st.session_state:

    st.session_state.warehouse_upload_key = 0


if "search_ai_result" not in st.session_state:

    st.session_state.search_ai_result = None


if "search_results" not in st.session_state:

    st.session_state.search_results = []


if "warehouse_results" not in st.session_state:

    st.session_state.warehouse_results = []


# =====================================================================
# 4. SECRET READER
# =====================================================================

def read_secret(*names):

    """
    Đọc Secret theo nhiều cách.

    Hỗ trợ:

    SUPABASE_URL = "..."
    SUPABASE_KEY = "..."
    GEMINI_API_KEY = "..."

    hoặc:

    [supabase]
    url = "..."
    key = "..."

    [gemini]
    api_key = "..."
    """

    # ---------------------------------------------------------------
    # DIRECT STREAMLIT SECRET
    # ---------------------------------------------------------------

    try:

        for name in names:

            try:

                value = st.secrets[name]

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


    # ---------------------------------------------------------------
    # ENVIRONMENT
    # ---------------------------------------------------------------

    for name in names:

        try:

            value = os.getenv(
                name,
                ""
            )

            if value:

                value = str(
                    value
                ).strip()

                if value:

                    return value

        except Exception:

            pass


    return None


# =====================================================================
# 5. READ SUPABASE
# =====================================================================

SUPABASE_URL = read_secret(

    "SUPABASE_URL",

    "SUPABASE_PROJECT_URL",

    "supabase_url"

)


SUPABASE_KEY = read_secret(

    "SUPABASE_KEY",

    "SUPABASE_ANON_KEY",

    "supabase_key"

)


# =====================================================================
# 6. SUPPORT [supabase] SECTION
# =====================================================================

if not SUPABASE_URL:

    try:

        if "supabase" in st.secrets:

            section = st.secrets[
                "supabase"
            ]

            for key in [

                "url",

                "SUPABASE_URL",

                "project_url"

            ]:

                try:

                    value = section.get(
                        key,
                        None
                    )

                    if value:

                        SUPABASE_URL = str(
                            value
                        ).strip()

                        break

                except Exception:

                    pass

    except Exception:

        pass


if not SUPABASE_KEY:

    try:

        if "supabase" in st.secrets:

            section = st.secrets[
                "supabase"
            ]

            for key in [

                "key",

                "anon_key",

                "SUPABASE_KEY",

                "SUPABASE_ANON_KEY"

            ]:

                try:

                    value = section.get(
                        key,
                        None
                    )

                    if value:

                        SUPABASE_KEY = str(
                            value
                        ).strip()

                        break

                except Exception:

                    pass

    except Exception:

        pass


# =====================================================================
# 7. READ GEMINI
# =====================================================================

GEMINI_API_KEY = read_secret(

    "GEMINI_API_KEY",

    "GOOGLE_API_KEY",

    "GEMINI_KEY",

    "gemini_api_key"

)


# =====================================================================
# 8. SUPPORT [gemini] SECTION
# =====================================================================

if not GEMINI_API_KEY:

    try:

        if "gemini" in st.secrets:

            section = st.secrets[
                "gemini"
            ]

            for key in [

                "api_key",

                "GEMINI_API_KEY",

                "GOOGLE_API_KEY",

                "key"

            ]:

                try:

                    value = section.get(
                        key,
                        None
                    )

                    if value:

                        GEMINI_API_KEY = str(
                            value
                        ).strip()

                        break

                except Exception:

                    pass

    except Exception:

        pass


# =====================================================================
# 9. CHECK SECRETS
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

        "❌ Không đọc được thông tin bảo mật "
        "từ Streamlit Secrets."

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
# 10. CONNECT SUPABASE
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
# 11. CONNECT GEMINI
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
# 12. CONFIG
# =====================================================================

GEMINI_MODEL = (
    "gemini-2.5-flash"
)


CLIP_MODEL_NAME = (
    "openai/clip-vit-base-patch32"
)


CLIP_DIMENSION = 512


BUCKET_NAME = (
    "product-images"
)


# =====================================================================
# 13. CATEGORY MASTER
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
# 14. CATEGORY ALIAS
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
# 15. GARMENT PROMPT
# =====================================================================

GARMENT_PROMPT = r"""
You are a SENIOR APPAREL TECHNICAL DESIGNER.

Analyze the uploaded garment image/sketch.

Your task is to identify the TRUE garment construction.

This is a commercial garment similarity system.

DO NOT classify only by visual appearance.

===========================================================
STEP 1 — ONE PIECE
===========================================================

First determine whether the upper body and lower body
are physically connected into ONE garment.

If connected:

one_piece = true

A connected upper + lower garment is:

"Áo liền quần"

UNLESS it is clearly a bib overall with bib front
and shoulder straps.

A jumpsuit MUST NEVER be classified as cargo pants.

===========================================================
STEP 2 — BIB OVERALL
===========================================================

If the garment has:

- bib front
- shoulder straps
- separate pant legs

then:

category = "Quần yếm"

bib = true

shoulder_straps = true

Quần yếm MUST NEVER be cargo pants.

===========================================================
STEP 3 — CARGO PANTS
===========================================================

"Quần túi hộp" is allowed ONLY when:

- It is a separate pants garment.
- There is NO connected upper body.
- Obvious external cargo/patch pockets are visible.
- Cargo pockets are positioned on the side legs.

If these conditions are not clearly satisfied:

cargo_pockets = false

DO NOT GUESS.

===========================================================
STEP 4 — JEANS
===========================================================

Separate denim pants:

category = "Quần jean"

denim = true

===========================================================
STEP 5 — JOGGER
===========================================================

Separate pants with clear jogger construction,
especially elastic or rib ankle cuffs:

category = "Quần jogger"

jogger_cuffs = true

===========================================================
STEP 6 — JACKET
===========================================================

Separate upper-body outerwear:

category = "Jacket"

===========================================================
STEP 7 — DRESS
===========================================================

One-piece dress with skirt/dress construction:

category = "Dress"

Do NOT confuse dress with jumpsuit.

===========================================================
AVAILABLE CATEGORIES
===========================================================

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
CRITICAL DECISION ORDER
===========================================================

1. ONE PIECE?
2. BIB OVERALL?
3. SEPARATE PANTS?
4. CARGO POCKETS?
5. DENIM?
6. JOGGER CUFFS?
7. NORMAL CATEGORY?

===========================================================
RETURN ONLY JSON
===========================================================

Use:

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

Do not return Markdown.
Do not return explanations outside JSON.
"""


# =====================================================================
# 16. JSON EXTRACTOR
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
    # FIND JSON OBJECT
    # ---------------------------------------------------------------

    start = text.find(
        "{"
    )


    if start < 0:

        raise Exception(

            "Gemini không trả JSON hợp lệ:\n"
            +
            text[:2000]

        )


    candidate = text[
        start:
    ].strip()


    # ---------------------------------------------------------------
    # DIRECT JSON
    # ---------------------------------------------------------------

    try:

        return json.loads(
            candidate
        )

    except Exception:

        pass


    # ---------------------------------------------------------------
    # FIND LAST COMPLETE }
    # ---------------------------------------------------------------

    end = candidate.rfind(
        "}"
    )


    if end >= 0:

        try:

            return json.loads(

                candidate[
                    :end + 1
                ]

            )

        except Exception:

            pass


    # ---------------------------------------------------------------
    # FALLBACK PARSER
    # Handles truncated Gemini response
    # ---------------------------------------------------------------

    result = {}


    # CATEGORY
    match = re.search(

        r'"category"\s*:\s*"([^"]+)"',

        candidate,

        flags=re.I

    )


    if match:

        result[
            "category"
        ] = match.group(1)


    # CONFIDENCE
    match = re.search(

        r'"confidence"\s*:\s*'
        r'([0-9]+(?:\.[0-9]+)?)',

        candidate,

        flags=re.I

    )


    if match:

        try:

            result[
                "confidence"
            ] = float(
                match.group(1)
            )

        except Exception:

            result[
                "confidence"
            ] = 0

    else:

        result[
            "confidence"
        ] = 0


    # BOOLEAN FIELDS
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

        match = re.search(

            rf'"{field}"\s*:\s*'
            r'(true|false)',

            candidate,

            flags=re.I

        )


        if match:

            result[field] = (

                match.group(1).lower()
                ==
                "true"

            )

        else:

            result[field] = False


    # REASON
    match = re.search(

        r'"reason"\s*:\s*"([^"]*)"', 

        candidate,

        flags=re.I

    )


    if match:

        result[
            "reason"
        ] = match.group(1)

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
            candidate[:2000]

        )


    return result


# =====================================================================
# 17. NORMALIZE CATEGORY
# =====================================================================

def normalize_garment_result(
    result
):

    if not isinstance(
        result,
        dict
    ):

        raise Exception(
            "AI result không hợp lệ."
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


    # ---------------------------------------------------------------
    # ALIAS
    # ---------------------------------------------------------------

    if category_upper in CATEGORY_ALIASES:

        category = CATEGORY_ALIASES[
            category_upper
        ]


    # ---------------------------------------------------------------
    # INVALID
    # ---------------------------------------------------------------

    if category not in CATEGORY_LIST:

        category = "Quần dài"


    result[
        "category"
    ] = category


    # ---------------------------------------------------------------
    # BOOLEAN
    # ---------------------------------------------------------------

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


        # Không cho one-piece thành cargo
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
    # CARGO
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
# 18. GEMINI IMAGE ANALYSIS
# =====================================================================

def analyze_garment_with_gemini(
    image_bytes,
    mime_type="image/jpeg"
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

                        mime_type=mime_type

                    ),

                    GARMENT_PROMPT

                ],

                config=types.GenerateContentConfig(

                    temperature=0,

                    max_output_tokens=500

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
# 19. LOAD CLIP
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


        processor = (

            CLIPProcessor
            .from_pretrained(

                CLIP_MODEL_NAME

            )

        )


        model = (

            CLIPModel
            .from_pretrained(

                CLIP_MODEL_NAME

            )

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
# 20. CLIP EMBEDDING
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
        # IMPORTANT FIX
        #
        # Một số transformers version trả:
        #
        # BaseModelOutputWithPooling
        #
        # Không được gọi ndim trực tiếp.
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
        # TENSOR CHECK
        # ============================================================

        if not torch.is_tensor(
            embedding
        ):

            raise Exception(

                "CLIP output không phải Tensor."

            )


        # ============================================================
        # IF 3D → MEAN POOL
        # ============================================================

        if embedding.dim() == 3:

            embedding = embedding.mean(
                dim=1
            )


        # ============================================================
        # FLATTEN
        # ============================================================

        embedding = embedding.reshape(
            -1
        )


        # ============================================================
        # NORMALIZE
        # ============================================================

        norm = embedding.norm(
            p=2
        )


        if norm.item() == 0:

            raise Exception(
                "CLIP vector có norm = 0."
            )


        embedding = (
            embedding
            /
            norm
        )


        # ============================================================
        # NUMPY
        # ============================================================

        vector = (

            embedding
            .cpu()
            .numpy()
            .astype(
                np.float32
            )
            .tolist()

        )


        # ============================================================
        # DIMENSION CHECK
        # ============================================================

        if len(vector) != CLIP_DIMENSION:

            raise Exception(

                f"CLIP dimension = "
                f"{len(vector)}, "
                f"không phải "
                f"{CLIP_DIMENSION}."

            )


        return vector


    except Exception as e:

        raise Exception(

            "CLIP embedding lỗi: "
            +
            str(e)

        )


# =====================================================================
# 21. IMAGE STORAGE
# =====================================================================

def upload_image_to_storage(

    file_bytes,

    filename

):

    try:

        # -------------------------------------------------------------
        # FILE EXTENSION
        # -------------------------------------------------------------

        ext = "jpg"


        if "." in filename:

            ext = (

                filename
                .rsplit(
                    ".",
                    1
                )[1]
                .lower()

            )


        if ext not in [

            "jpg",

            "jpeg",

            "png",

            "webp"

        ]:

            ext = "jpg"


        # -------------------------------------------------------------
        # SAFE FILE NAME
        # -------------------------------------------------------------

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


        # -------------------------------------------------------------
        # HASH
        # -------------------------------------------------------------

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
            "."
            +
            ext

        )


        # -------------------------------------------------------------
        # MIME
        # -------------------------------------------------------------

        mime_type = {

            "jpg":
                "image/jpeg",

            "jpeg":
                "image/jpeg",

            "png":
                "image/png",

            "webp":
                "image/webp"

        }.get(

            ext,

            "image/jpeg"

        )


        # -------------------------------------------------------------
        # UPLOAD
        # -------------------------------------------------------------

        supabase.storage.from_(
            BUCKET_NAME
        ).upload(

            path=storage_path,

            file=file_bytes,

            file_options={

                "content-type":
                    mime_type,

                "upsert":
                    "true"

            }

        )


        # -------------------------------------------------------------
        # PUBLIC URL
        # -------------------------------------------------------------

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
# 22. PRODUCT CODE
# =====================================================================

def get_product_code(
    filename
):

    base_name = (

        filename
        .rsplit(
            ".",
            1
        )[0]

    )


    return (

        str(
            base_name
        )
        .strip()
        .upper()

    )


# =====================================================================
# 23. SAVE PRODUCT
# =====================================================================

def save_product_to_database(

    product_code,

    image_url,

    category,

    embedding

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


    try:

        response = (

            supabase
            .table(
                "products"
            )
            .upsert(

                payload,

                on_conflict=
                    "product_code"

            )
            .execute()

        )


        return response


    except Exception as e:

        raise Exception(

            "Database save lỗi: "
            +
            str(e)

        )


# =====================================================================
# 24. SEARCH SIMILARITY
# =====================================================================

def search_similar_products(

    query_embedding,

    category,

    threshold=0.35,

    match_count=8

):

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

            "Similarity search lỗi: "
            +
            str(e)

        )


# =====================================================================
# 25. PROCESS ONE WAREHOUSE FILE
# =====================================================================

def process_product_file(
    uploaded_file
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
            "Ảnh rỗng."
        )


    # ---------------------------------------------------------------
    # MIME
    # ---------------------------------------------------------------

    extension = (

        filename
        .rsplit(
            ".",
            1
        )[-1]
        .lower()

    )


    mime_type = {

        "jpg":
            "image/jpeg",

        "jpeg":
            "image/jpeg",

        "png":
            "image/png",

        "webp":
            "image/webp"

    }.get(

        extension,

        "image/jpeg"

    )


    # ================================================================
    # GEMINI CATEGORY
    # ================================================================

    ai_result = (

        analyze_garment_with_gemini(

            image_bytes,

            mime_type

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

    image_url, storage_path = (

        upload_image_to_storage(

            image_bytes,

            filename

        )

    )


    # ================================================================
    # DATABASE
    # ================================================================

    save_product_to_database(

        product_code=

            product_code,

        image_url=

            image_url,

        category=

            category,

        embedding=

            embedding

    )


    # ================================================================
    # RETURN
    # ================================================================

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

        "storage_path":
            storage_path

    }


# =====================================================================
# 26. HEADER
# =====================================================================

st.title(
    "🔍 AI TÌM KIẾM MÃ HÀNG TƯƠNG ĐỒNG"
)


st.caption(

    "Gemini Vision + Local CLIP + Supabase"

)


# =====================================================================
# 27. TABS
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
# TAB 1 — SEARCH
#
# #####################################################################
# #####################################################################

with tab1:

    st.header(
        "🔍 Tìm mã hàng tương đồng"
    )


    st.info(

        "AI tự nhận diện loại hàng. "
        "Bạn không cần chọn category."

    )


    # ================================================================
    # UPLOAD SEARCH FILE
    # ================================================================

    uploaded_search = st.file_uploader(

        "📷 Tải ảnh Sketch / ảnh mẫu cần tìm",

        type=[

            "jpg",

            "jpeg",

            "png",

            "webp"

        ],

        key=(

            "search_file_"
            +
            str(
                st.session_state
                .search_upload_key
            )

        )

    )


    # ================================================================
    # CLEAR SEARCH FILE
    # ================================================================

    if st.button(

        "🗑️ Xóa file hiện tại",

        key="clear_search_file"

    ):

        st.session_state.search_upload_key += 1

        st.session_state.search_ai_result = None

        st.session_state.search_results = []

        st.rerun()


    # ================================================================
    # SHOW SEARCH IMAGE
    # ================================================================

    if uploaded_search:

        col_image, col_ai = st.columns(

            [1, 1]

        )


        with col_image:

            st.image(

                uploaded_search,

                caption=
                    uploaded_search.name,

                width=350

            )


        # ============================================================
        # SEARCH BUTTON
        # ============================================================

        if st.button(

            "🚀 AI NHẬN DIỆN + TÌM MÃ TƯƠNG ĐỒNG",

            type="primary",

            key="search_button"

        ):

            try:

                image_bytes = (

                    uploaded_search
                    .getvalue()

                )


                extension = (

                    uploaded_search.name
                    .rsplit(
                        ".",
                        1
                    )[-1]
                    .lower()

                )


                mime_type = {

                    "jpg":
                        "image/jpeg",

                    "jpeg":
                        "image/jpeg",

                    "png":
                        "image/png",

                    "webp":
                        "image/webp"

                }.get(

                    extension,

                    "image/jpeg"

                )


                # ====================================================
                # GEMINI
                # ====================================================

                with st.spinner(

                    "🤖 Gemini đang nhận diện garment..."

                ):

                    ai_result = (

                        analyze_garment_with_gemini(

                            image_bytes,

                            mime_type

                        )

                    )


                st.session_state[
                    "search_ai_result"
                ] = ai_result


                # ====================================================
                # SHOW AI
                # ====================================================

                with col_ai:

                    st.success(
                        "✅ AI nhận diện thành công"
                    )


                    st.metric(

                        "Loại hàng",

                        ai_result[
                            "category"
                        ]

                    )


                    st.metric(

                        "Độ tin cậy",

                        f"{ai_result.get('confidence', 0):.1f}%"

                    )


                    st.write(

                        "One Piece:",

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

                        "Cargo Pocket:",

                        "✅"
                        if ai_result.get(
                            "cargo_pockets",
                            False
                        )
                        else
                        "❌"

                    )


                    st.write(

                        "Denim:",

                        "✅"
                        if ai_result.get(
                            "denim",
                            False
                        )
                        else
                        "❌"

                    )


                    st.write(

                        "Jogger Cuff:",

                        "✅"
                        if ai_result.get(
                            "jogger_cuffs",
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

                    "🧠 CLIP đang tạo vector hình ảnh..."

                ):

                    query_embedding = (

                        get_clip_embedding(

                            image_bytes

                        )

                    )


                # ====================================================
                # CATEGORY LOCK
                # ====================================================

                detected_category = (

                    ai_result[
                        "category"
                    ]

                )


                st.info(

                    "🔒 Đã khóa tìm kiếm theo category AI: "
                    +
                    detected_category

                )


                # ====================================================
                # SEARCH
                # ====================================================

                with st.spinner(

                    "🔎 Đang tìm mã hàng tương đồng..."

                ):

                    results = (

                        search_similar_products(

                            query_embedding,

                            detected_category,

                            threshold=0.35,

                            match_count=8

                        )

                    )


                st.session_state[
                    "search_results"
                ] = results


                # ====================================================
                # RESULTS
                # ====================================================

                st.divider()


                st.subheader(

                    "🎯 MÃ HÀNG TƯƠNG ĐỒNG"

                )


                if not results:

                    st.warning(

                        "Không tìm thấy mã hàng nào "
                        "trong đúng category "
                        f"「{detected_category}」."

                    )

                else:

                    st.success(

                        f"Tìm thấy "
                        f"{len(results)} "
                        "mã hàng."

                    )


                    # ------------------------------------------------
                    # DISPLAY 4 PER ROW
                    # ------------------------------------------------

                    for row_start in range(

                        0,

                        len(results),

                        4

                    ):

                        row_items = results[
                            row_start:
                            row_start + 4
                        ]


                        cols = st.columns(
                            len(row_items)
                        )


                        for idx, item in enumerate(
                            row_items
                        ):

                            with cols[idx]:

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
                                            detected_category
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
# TAB 2 — WAREHOUSE
#
# #####################################################################
# #####################################################################

with tab2:

    st.header(
        "📦 Nạp kho hàng loạt"
    )


    st.info(

        "Tên file = mã hàng. "
        "Gemini sẽ tự nhận diện category. "
        "Không cần chọn dòng hàng."

    )


    # ================================================================
    # UPLOAD MULTIPLE FILES
    # ================================================================

    uploaded_files = st.file_uploader(

        "📂 Chọn nhiều ảnh sản phẩm để nạp kho",

        type=[

            "jpg",

            "jpeg",

            "png",

            "webp"

        ],

        accept_multiple_files=True,

        key=(

            "warehouse_files_"
            +
            str(
                st.session_state
                .warehouse_upload_key
            )

        )

    )


    # ================================================================
    # CLEAR CURRENT QUEUE
    #
    # CHỈ XÓA FILE ĐANG CHỜ
    #
    # KHÔNG XÓA SUPABASE
    # ================================================================

    if st.button(

        "🗑️ Xóa file đang chờ",

        key="clear_warehouse_queue"

    ):

        st.session_state.warehouse_upload_key += 1

        st.session_state.warehouse_results = []

        st.rerun()


    # ================================================================
    # FILE COUNT
    # ================================================================

    if uploaded_files:

        st.success(

            f"📂 Đã chọn "
            f"**{len(uploaded_files)}** "
            f"file ảnh."

        )


        # ============================================================
        # PROCESS BUTTON
        # ============================================================

        if st.button(

            "📤 AI NHẬN DIỆN + LƯU TOÀN BỘ VÀO KHO",

            type="primary",

            key="warehouse_process_button"

        ):

            total_files = len(
                uploaded_files
            )


            progress = st.progress(
                0
            )


            status = st.empty()


            success_count = 0

            fail_count = 0


            results = []


            # ========================================================
            # PROCESS EACH FILE
            # ========================================================

            for index, file in enumerate(
                uploaded_files
            ):

                filename = file.name


                status.text(

                    f"⏳ Đang xử lý "
                    f"{index + 1}/"
                    f"{total_files}: "
                    f"{filename}"

                )


                try:

                    result = (

                        process_product_file(

                            file

                        )

                    )


                    results.append(
                        result
                    )


                    success_count += 1


                    st.success(

                        f"✅ "
                        f"{filename} → "
                        f"{result['category']} "
                        f"({result['confidence']:.1f}%)"

                    )


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
                    total_files

                )


            status.empty()


            st.session_state[
                "warehouse_results"
            ] = results


            # ========================================================
            # SUMMARY
            # ========================================================

            st.divider()


            if fail_count == 0:

                st.success(

                    f"🎉 Đã lưu thành công "
                    f"**{success_count}/{total_files}** "
                    "mã hàng vào kho."

                )

            else:

                st.warning(

                    f"Hoàn thành: "
                    f"**{success_count}** thành công / "
                    f"**{fail_count}** lỗi."

                )


    # ================================================================
    # SHOW RESULTS
    # ================================================================

    warehouse_results = (

        st.session_state
        .get(
            "warehouse_results",
            []
        )

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


        if table_data:

            df_results = pd.DataFrame(
                table_data
            )


            st.dataframe(

                df_results,

                use_container_width=True,

                hide_index=True

            )


        # ============================================================
        # SHOW SAVED IMAGES
        # ============================================================

        st.subheader(
            "📸 Ảnh đã nạp"
        )


        for item in warehouse_results:

            col1, col2 = st.columns(

                [1, 3]

            )


            with col1:

                if item.get(
                    "image_url"
                ):

                    st.image(

                        item[
                            "image_url"
                        ],

                        width=180

                    )


            with col2:

                st.markdown(

                    f"### "
                    f"{item.get('product_code', '')}"

                )


                st.write(

                    "Category:",
                    item.get(
                        "category",
                        ""
                    )

                )


                st.write(

                    "Confidence:",
                    f"{item.get('confidence', 0):.1f}%"

                )


                if item.get(
                    "reason"
                ):

                    st.caption(

                        item[
                            "reason"
                        ]

                    )


# =====================================================================
# 28. FOOTER
# =====================================================================

st.divider()


st.caption(

    "AI Garment Search V4.2 | "
    "Gemini Vision + Local CLIP + Supabase"

)
