# =====================================================================
# 🔍 PRODUCT AI SEARCH & AUTO STORAGE
# VERSION V3.0
#
# MASTER GARMENT VISUAL AI ENGINE
#
# =====================================================================
#
# AI ARCHITECTURE
#
#                    IMAGE
#                      │
#          ┌───────────┴────────────┐
#          │                        │
#          ▼                        ▼
#     HF VISION AI             LOCAL CLIP
#     QWEN2.5-VL               IMAGE EMBEDDING
#          │                        │
#          ▼                        ▼
#   GARMENT ANALYSIS              512D
#          │                        │
#          │                        ▼
#          │                  SUPABASE VECTOR
#          │                        │
#          ▼                        │
#   CATEGORY / ATTRIBUTES           │
#          │                        │
#          ▼                        │
#      CATEGORY LOCK                │
#          │                        │
#          └──────────┬─────────────┘
#                     ▼
#              VECTOR SEARCH
#                     │
#                     ▼
#             TOP SIMILAR PRODUCTS
#
# =====================================================================
#
# ❌ KHÔNG hard-code HF TOKEN
# ❌ KHÔNG hard-code SUPABASE KEY
# ❌ KHÔNG gọi requests tới hf-inference
# ❌ KHÔNG cho user chọn category
#
# ✅ HF_TOKEN từ Streamlit Secrets / Tomy
# ✅ Supabase từ Streamlit Secrets / Tomy
# ✅ Hugging Face provider="auto"
# ✅ Qwen Vision nhận diện garment
# ✅ CLIP 512D giữ compatibility với database hiện tại
#
# =====================================================================


# =====================================================================
# 1. STREAMLIT
# =====================================================================

import streamlit as st

st.set_page_config(
    page_title="AI Tìm Kiếm Mã Hàng",
    page_icon="🔍",
    layout="wide"
)


# =====================================================================
# 2. IMPORT
# =====================================================================

import io
import re
import json
import base64
import hashlib
import math

import pandas as pd


# =====================================================================
# 3. OPTIONAL / REQUIRED PACKAGES
# =====================================================================

MISSING_PACKAGES = []


try:
    import torch
except Exception:
    torch = None
    MISSING_PACKAGES.append("torch")


try:
    from transformers import (
        CLIPModel,
        CLIPProcessor
    )
except Exception:
    CLIPModel = None
    CLIPProcessor = None
    MISSING_PACKAGES.append("transformers")


try:
    from PIL import (
        Image,
        ImageOps
    )
except Exception:
    Image = None
    ImageOps = None
    MISSING_PACKAGES.append("pillow")


try:
    from supabase import (
        create_client,
        Client
    )
except Exception:
    create_client = None
    Client = None
    MISSING_PACKAGES.append("supabase")


try:
    from huggingface_hub import (
        InferenceClient
    )
except Exception:
    InferenceClient = None
    MISSING_PACKAGES.append(
        "huggingface_hub"
    )


# =====================================================================
# 4. PACKAGE CHECK
# =====================================================================

if MISSING_PACKAGES:

    st.error(
        "❌ APP THIẾU PACKAGE"
    )

    st.write(
        "Các package đang thiếu:"
    )

    for package in MISSING_PACKAGES:

        st.code(
            package
        )

    st.info(
        "Thêm các package này vào requirements.txt "
        "sau đó Reboot app."
    )

    st.code(
        """
streamlit
supabase
pillow
pandas
torch
transformers
safetensors
huggingface_hub
        """,
        language="text"
    )

    st.stop()


# =====================================================================
# 5. SECRET READER
# =====================================================================

def get_secret_value(
    names
):

    # ---------------------------------------------------------
    # DIRECT
    # ---------------------------------------------------------

    for name in names:

        try:

            value = st.secrets.get(
                name
            )

            if value is not None:

                value = str(
                    value
                ).strip()

                if value:

                    return value

        except Exception:

            pass


    # ---------------------------------------------------------
    # GROUP
    # ---------------------------------------------------------

    for group_name in [
        "supabase",
        "SUPABASE",
        "huggingface",
        "HUGGINGFACE"
    ]:

        try:

            group = st.secrets.get(
                group_name
            )

            if group:

                for name in names:

                    try:

                        value = group.get(
                            name
                        )

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


    return None


# =====================================================================
# 6. SUPABASE SECRETS
# =====================================================================

SUPABASE_URL = get_secret_value(
    [
        "SUPABASE_URL",
        "SUPABASE_PROJECT_URL",
        "supabase_url"
    ]
)


SUPABASE_KEY = get_secret_value(
    [
        "SUPABASE_KEY",
        "SUPABASE_ANON_KEY",
        "SUPABASE_API_KEY",
        "supabase_key",
        "supabase_anon_key"
    ]
)


# =====================================================================
# 7. HF TOKEN
# =====================================================================

HF_TOKEN = get_secret_value(
    [
        "HF_TOKEN",
        "HUGGINGFACE_TOKEN",
        "HUGGING_FACE_TOKEN",
        "huggingface_token"
    ]
)


# =====================================================================
# 8. SECRET VALIDATION
# =====================================================================

missing = []


if not SUPABASE_URL:

    missing.append(
        "SUPABASE_URL"
    )


if not SUPABASE_KEY:

    missing.append(
        "SUPABASE_KEY"
    )


if not HF_TOKEN:

    missing.append(
        "HF_TOKEN"
    )


if missing:

    st.error(
        "❌ Không đọc được thông tin bảo mật."
    )

    st.write(
        "Kiểm tra các key sau trong "
        "Streamlit Secrets / Tomy:"
    )

    for item in missing:

        st.code(
            item
        )

    st.stop()


# =====================================================================
# 9. SUPABASE
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
# 10. HUGGING FACE VISION CLIENT
# =====================================================================

try:

    hf_client = InferenceClient(
        api_key=HF_TOKEN,
        provider="auto"
    )

except Exception as e:

    st.error(
        "❌ Không khởi tạo được Hugging Face AI."
    )

    st.exception(e)

    st.stop()


# =====================================================================
# 11. AI MODEL
# =====================================================================
#
# Qwen2.5-VL-3B-Instruct là VLM.
#
# Image + Text → garment analysis.
#
# =====================================================================

VISION_MODEL = (
    "Qwen/Qwen2.5-VL-3B-Instruct"
)


# =====================================================================
# 12. CLIP MODEL
# =====================================================================
#
# Giữ model này để tạo embedding 512D tương thích với DB hiện tại.
#
# =====================================================================

CLIP_MODEL_NAME = (
    "openai/clip-vit-base-patch32"
)

CLIP_DIMENSION = 512


# =====================================================================
# 13. DEVICE
# =====================================================================

if torch.cuda.is_available():

    DEVICE = torch.device(
        "cuda"
    )

    DEVICE_NAME = "CUDA"

else:

    DEVICE = torch.device(
        "cpu"
    )

    DEVICE_NAME = "CPU"


# =====================================================================
# 14. GARMENT CATEGORY MASTER
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
# 15. CATEGORY DESCRIPTION
# =====================================================================
#
# Dùng cho VLM.
#
# =====================================================================

CATEGORY_DEFINITIONS = {

    "Áo liền quần":

        "JUMPSUIT / ONE-PIECE GARMENT. "
        "Upper body and lower body are physically connected "
        "as one garment. It is NOT ordinary separate pants.",


    "Quần yếm":

        "BIB OVERALL / DUNGAREES. "
        "The garment has a bib front and shoulder straps. "
        "It is NOT ordinary cargo pants.",


    "Quần túi hộp":

        "CARGO PANTS. "
        "Separate pants with clearly visible large external "
        "patch cargo pockets on the side legs. "
        "Do NOT classify jumpsuits or bib overalls as cargo.",


    "Quần jean":

        "DENIM JEANS / DENIM TROUSERS. "
        "Separate pants made from denim, typically with "
        "jeans construction.",


    "Quần jogger":

        "JOGGER PANTS. "
        "Separate casual or sports pants, usually with "
        "elastic cuffs or jogger silhouette.",


    "Quần short":

        "SHORTS. "
        "Separate short-length pants.",


    "Quần dài":

        "ORDINARY LONG PANTS / TROUSERS. "
        "Separate full-length pants without defining cargo, "
        "denim, jogger, or bib-overall features.",


    "Jacket":

        "JACKET / OUTERWEAR. "
        "A separate upper-body outerwear garment.",


    "Áo":

        "WOVEN SHIRT / TOP. "
        "Separate upper-body garment, not T-shirt, polo, hoodie "
        "or jacket.",


    "T-shirt":

        "T-SHIRT. "
        "Basic knit tee, usually crew neck or similar.",


    "Polo":

        "POLO SHIRT. "
        "Collared polo-style top.",


    "Hoodie":

        "HOODIE. "
        "Upper-body sweatshirt with hood.",


    "Skirt":

        "SKIRT. "
        "Separate lower-body skirt garment.",


    "Dress":

        "DRESS. "
        "One-piece upper and lower garment with dress silhouette, "
        "not a pants-based jumpsuit."

}


# =====================================================================
# 16. AI VISION SYSTEM PROMPT
# =====================================================================

VISION_SYSTEM_PROMPT = """
You are a senior garment technical designer and apparel
product recognition specialist.

You analyze fashion product images and garment sketches.

Your job is NOT to guess based only on general appearance.

You must inspect:

1. one-piece vs separate garments
2. bib and shoulder straps
3. cargo side pockets
4. denim characteristics
5. jogger cuffs
6. sleeve construction
7. collar
8. hood
9. waistband
10. garment silhouette
11. upper/lower body connection
12. visible construction details

CRITICAL RULES:

A jumpsuit is a ONE-PIECE garment where the upper body
and lower body are physically connected.

A bib overall has a bib front and shoulder straps.

Cargo pants MUST have clear external cargo/patch pockets
on the side legs.

Do NOT classify a jumpsuit as cargo pants merely because
the lower half looks like pants.

Do NOT classify overalls as cargo pants merely because
they have pockets.

Do NOT classify a dress as a jumpsuit.

Return ONLY valid JSON.
"""


# =====================================================================
# 17. VISION JSON SCHEMA
# =====================================================================

VISION_SCHEMA_DESCRIPTION = """

Return exactly this JSON structure:

{
  "category": "...",
  "confidence": 0,
  "one_piece": false,
  "bib": false,
  "shoulder_straps": false,
  "cargo_pockets": false,
  "denim": false,
  "jogger_cuffs": false,
  "sleeve": "...",
  "collar": "...",
  "hood": false,
  "silhouette": "...",
  "length": "...",
  "reason": "..."
}

Allowed category values:

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

confidence must be 0-100.

one_piece, bib, shoulder_straps,
cargo_pockets, denim, jogger_cuffs, hood
must be true or false.
"""


# =====================================================================
# 18. IMAGE → DATA URL
# =====================================================================

def image_to_data_url(
    image_bytes
):

    encoded = base64.b64encode(
        image_bytes
    ).decode(
        "utf-8"
    )


    return (
        "data:image/jpeg;base64,"
        +
        encoded
    )


# =====================================================================
# 19. CLEAN AI JSON
# =====================================================================

def extract_json_from_text(
    text
):

    if not text:

        raise Exception(
            "AI không trả về dữ liệu."
        )


    text = str(
        text
    ).strip()


    # ---------------------------------------------------------
    # REMOVE CODE FENCE
    # ---------------------------------------------------------

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


    # ---------------------------------------------------------
    # FIND JSON
    # ---------------------------------------------------------

    match = re.search(
        r"\{.*\}",
        text,
        flags=re.S
    )


    if not match:

        raise Exception(
            "AI không trả JSON hợp lệ:\n"
            +
            text[:1000]
        )


    json_text = (
        match.group(0)
    )


    try:

        return json.loads(
            json_text
        )

    except Exception as e:

        raise Exception(
            "JSON AI lỗi: "
            +
            str(e)
            +
            "\n"
            +
            json_text[:1000]
        )


# =====================================================================
# 20. HF VISION ANALYSIS
# =====================================================================

def analyze_garment_with_vision(
    image_bytes
):

    image_data_url = (
        image_to_data_url(
            image_bytes
        )
    )


    category_list = "\n".join(

        [

            f"- {category}: "
            f"{definition}"

            for category, definition
            in CATEGORY_DEFINITIONS.items()

        ]

    )


    user_prompt = f"""
Analyze this garment image very carefully.

Available categories:

{category_list}

{VISION_SCHEMA_DESCRIPTION}

IMPORTANT:

Before choosing category, determine whether the garment
is one-piece or a separate garment.

If upper and lower body are physically connected:
consider JUMPSUIT or DRESS.

If there is a bib and shoulder straps:
consider BIB OVERALL.

Only use CARGO PANTS when clear external cargo patch
pockets are visible on the side legs.

Do not use Cargo Pants as a generic category for pants.

Return JSON only.
"""


    try:

        completion = (
            hf_client.chat.completions.create(

                model=VISION_MODEL,

                messages=[

                    {

                        "role":
                            "system",

                        "content":
                            VISION_SYSTEM_PROMPT

                    },

                    {

                        "role":
                            "user",

                        "content":

                            [

                                {

                                    "type":
                                        "image_url",

                                    "image_url":
                                        {

                                            "url":
                                                image_data_url

                                        }

                                },

                                {

                                    "type":
                                        "text",

                                    "text":
                                        user_prompt

                                }

                            ]

                    }

                ],

                max_tokens=700,

                temperature=0.0

            )
        )


    except Exception as e:

        raise Exception(

            "Hugging Face Vision API lỗi: "
            +
            str(e)

        )


    try:

        content = (
            completion
            .choices[0]
            .message
            .content
        )

    except Exception as e:

        raise Exception(
            "Không đọc được kết quả Vision AI: "
            +
            str(e)
        )


    result = extract_json_from_text(
        content
    )


    return validate_vision_result(
        result
    )


# =====================================================================
# 21. VALIDATE VISION RESULT
# =====================================================================

def validate_vision_result(
    result
):

    if not isinstance(
        result,
        dict
    ):

        raise Exception(
            "Vision result không phải dict."
        )


    category = str(

        result.get(
            "category",
            ""
        )

    ).strip()


    # ---------------------------------------------------------
    # CATEGORY NORMALIZATION
    # ---------------------------------------------------------

    aliases = {

        "JUMPSUIT":
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

        "CARGO":
            "Quần túi hộp",

        "CARGO PANTS":
            "Quần túi hộp",

        "JEANS":
            "Quần jean",

        "DENIM":
            "Quần jean",

        "JOGGER":
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

        "DRESS":
            "Dress",

        "SKIRT":
            "Skirt"

    }


    category_upper = (
        category
        .upper()
        .strip()
    )


    if category_upper in aliases:

        category = aliases[
            category_upper
        ]


    # ---------------------------------------------------------
    # CATEGORY VALIDATION
    # ---------------------------------------------------------

    if category not in CATEGORY_OPTIONS:

        raise Exception(

            "AI trả category không hợp lệ: "
            +
            str(category)

        )


    result["category"] = category


    # ---------------------------------------------------------
    # BOOLEAN NORMALIZATION
    # ---------------------------------------------------------

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
                .lower()
                .strip()
                in [
                    "true",
                    "yes",
                    "1"
                ]
            )


        result[field] = bool(
            value
        )


    # ---------------------------------------------------------
    # CONFIDENCE
    # ---------------------------------------------------------

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


    result[
        "confidence"
    ] = confidence


    # =========================================================
    # HARD GARMENT RULES
    # =========================================================

    # ---------------------------------------------------------
    # RULE 1:
    # JUMPSUIT
    # ---------------------------------------------------------

    if (

        result["one_piece"]

        and

        category
        ==
        "Quần túi hộp"

    ):

        # Cargo không được thắng
        # nếu garment là one-piece.

        if result["bib"]:

            category = (
                "Quần yếm"
            )

        else:

            category = (
                "Áo liền quần"
            )


        result[
            "category"
        ] = category


    # ---------------------------------------------------------
    # RULE 2:
    # BIB
    # ---------------------------------------------------------

    if (

        result["bib"]

        and

        result["shoulder_straps"]

    ):

        result[
            "category"
        ] = "Quần yếm"


    # ---------------------------------------------------------
    # RULE 3:
    # CARGO MUST HAVE POCKET
    # ---------------------------------------------------------

    if (

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

        # Không đủ bằng chứng Cargo.
        #
        # Chuyển về Quần dài.

        result[
            "category"
        ] = "Quần dài"


    # ---------------------------------------------------------
    # RULE 4:
    # DENIM
    # ---------------------------------------------------------

    if (

        result["denim"]

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


    # ---------------------------------------------------------
    # RULE 5:
    # JOGGER
    # ---------------------------------------------------------

    if (

        result["jogger_cuffs"]

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


    return result


# =====================================================================
# 22. LOAD LOCAL CLIP
# =====================================================================

@st.cache_resource(
    show_spinner="🤖 Đang tải CLIP embedding engine..."
)
def load_clip():

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


    model = (
        model
        .to(
            DEVICE
        )
    )


    model.eval()


    return (
        processor,
        model
    )


# =====================================================================
# 23. INITIALIZE CLIP
# =====================================================================

try:

    clip_processor, clip_model = (
        load_clip()
    )

except Exception as e:

    st.error(
        "❌ Không tải được CLIP."
    )

    st.exception(e)

    st.stop()


# =====================================================================
# 24. IMAGE NORMALIZE
# =====================================================================

def normalize_image(
    image_bytes
):

    try:

        image = Image.open(
            io.BytesIO(
                image_bytes
            )
        )


        try:

            image = ImageOps.exif_transpose(
                image
            )

        except Exception:

            pass


        if image.mode != "RGB":

            image = image.convert(
                "RGB"
            )


        return image


    except Exception as e:

        raise Exception(
            "Không đọc được ảnh: "
            +
            str(e)
        )


# =====================================================================
# 25. IMAGE HASH
# =====================================================================

def get_image_hash(
    image_bytes
):

    return hashlib.sha256(
        image_bytes
    ).hexdigest()


# =====================================================================
# 26. LOCAL CLIP EMBEDDING
# =====================================================================
#
# FIX lỗi:
#
# 'BaseModelOutputWithPooling'
# object has no attribute 'ndim'
#
# Không dùng output trực tiếp.
#
# Lấy pooler_output → visual_projection.
#
# =====================================================================

def get_clip_image_embedding(
    image
):

    try:

        inputs = clip_processor(
            images=image,
            return_tensors="pt"
        )


        pixel_values = (
            inputs[
                "pixel_values"
            ]
            .to(
                DEVICE
            )
        )


        with torch.inference_mode():

            vision_outputs = (
                clip_model
                .vision_model(
                    pixel_values=
                        pixel_values
                )
            )


        # ---------------------------------------------------------
        # POOLER
        # ---------------------------------------------------------

        if hasattr(
            vision_outputs,
            "pooler_output"
        ):

            pooled_output = (
                vision_outputs
                .pooler_output
            )

        elif isinstance(
            vision_outputs,
            tuple
        ):

            pooled_output = (
                vision_outputs[1]
            )

        else:

            raise Exception(
                "Không lấy được pooler_output."
            )


        # ---------------------------------------------------------
        # PROJECT TO CLIP 512D
        # ---------------------------------------------------------

        with torch.inference_mode():

            image_features = (
                clip_model
                .visual_projection(
                    pooled_output
                )
            )


        image_features = (
            image_features
            .detach()
            .float()
            .cpu()
            .flatten()
        )


        if (
            image_features.numel()
            !=
            CLIP_DIMENSION
        ):

            raise Exception(

                f"CLIP vector phải "
                f"{CLIP_DIMENSION}D, "
                f"nhận "
                f"{image_features.numel()}D."

            )


        # ---------------------------------------------------------
        # NORMALIZE
        # ---------------------------------------------------------

        norm = torch.linalg.vector_norm(
            image_features
        )


        if norm.item() <= 0:

            raise Exception(
                "CLIP vector norm = 0."
            )


        image_features = (
            image_features
            /
            norm
        )


        return (
            image_features
            .tolist()
        )


    except Exception as e:

        raise Exception(
            "CLIP embedding lỗi: "
            +
            str(e)
        )


# =====================================================================
# 27. CACHE EMBEDDING
# =====================================================================

@st.cache_data(
    ttl=86400,
    show_spinner=False
)
def get_cached_embedding(
    image_hash,
    image_bytes
):

    image = normalize_image(
        image_bytes
    )


    return get_clip_image_embedding(
        image
    )


# =====================================================================
# 28. STORAGE
# =====================================================================

def sanitize_filename(
    filename
):

    return re.sub(
        r"[^A-Za-z0-9._-]",
        "_",
        filename
    )


def get_content_type(
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


    return (
        "application/octet-stream"
    )


def upload_image_to_storage(
    image_bytes,
    filename
):

    bucket_name = (
        "product-images"
    )


    safe_filename = (
        sanitize_filename(
            filename
        )
    )


    storage = (
        supabase
        .storage
        .from_(
            bucket_name
        )
    )


    try:

        storage.upload(

            path=safe_filename,

            file=image_bytes,

            file_options={

                "content-type":
                    get_content_type(
                        safe_filename
                    ),

                "upsert":
                    "true"

            }

        )

    except Exception as e:

        error_text = (
            str(e)
            .lower()
        )


        if (
            "already exists"
            not in error_text
            and
            "duplicate"
            not in error_text
        ):

            raise Exception(
                "Storage upload lỗi: "
                +
                str(e)
            )


    try:

        url = (
            storage
            .get_public_url(
                safe_filename
            )
        )


        if isinstance(
            url,
            dict
        ):

            url = (

                url.get(
                    "publicUrl"
                )

                or

                url.get(
                    "public_url"
                )

            )


        if not url:

            raise Exception(
                "Không lấy được public URL."
            )


        return url


    except Exception as e:

        raise Exception(
            "Không lấy được image URL: "
            +
            str(e)
        )


# =====================================================================
# 29. PRODUCT CODE
# =====================================================================

def extract_product_code(
    filename
):

    filename_only = (
        filename
        .rsplit(
            ".",
            1
        )[0]
    )


    return (
        filename_only
        .strip()
        .upper()
    )


# =====================================================================
# 30. SAVE PRODUCT
# =====================================================================

def save_product(
    product_code,
    image_url,
    category,
    embedding,
    ai_analysis
):

    if len(
        embedding
    ) != CLIP_DIMENSION:

        raise Exception(
            "Embedding không phải 512D."
        )


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


    # ---------------------------------------------------------
    # DATABASE
    # ---------------------------------------------------------

    try:

        result = (

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


        return result


    except Exception as e:

        raise Exception(
            "Database save lỗi: "
            +
            str(e)
        )


# =====================================================================
# 31. DISPLAY AI ANALYSIS
# =====================================================================

def display_ai_analysis(
    analysis
):

    category = (
        analysis[
            "category"
        ]
    )


    confidence = (
        analysis[
            "confidence"
        ]
    )


    st.success(

        f"🤖 AI nhận diện: "
        f"**{category}**"

    )


    c1, c2, c3 = st.columns(3)


    with c1:

        st.metric(
            "Category",
            category
        )


    with c2:

        st.metric(
            "AI Confidence",
            f"{confidence:.1f}%"
        )


    with c3:

        st.metric(
            "One Piece",
            "YES"
            if analysis[
                "one_piece"
            ]
            else
            "NO"
        )


    with st.expander(
        "🔎 AI phân tích chi tiết"
    ):

        details = {

            "Category":
                analysis[
                    "category"
                ],

            "Confidence":
                analysis[
                    "confidence"
                ],

            "One Piece":
                analysis[
                    "one_piece"
                ],

            "Bib":
                analysis[
                    "bib"
                ],

            "Shoulder Straps":
                analysis[
                    "shoulder_straps"
                ],

            "Cargo Pockets":
                analysis[
                    "cargo_pockets"
                ],

            "Denim":
                analysis[
                    "denim"
                ],

            "Jogger Cuffs":
                analysis[
                    "jogger_cuffs"
                ],

            "Sleeve":
                analysis.get(
                    "sleeve",
                    ""
                ),

            "Collar":
                analysis.get(
                    "collar",
                    ""
                ),

            "Hood":
                analysis[
                    "hood"
                ],

            "Silhouette":
                analysis.get(
                    "silhouette",
                    ""
                ),

            "Length":
                analysis.get(
                    "length",
                    ""
                ),

            "Reason":
                analysis.get(
                    "reason",
                    ""
                )

        }


        st.json(
            details
        )


# =====================================================================
# 32. TABS
# =====================================================================

tab1, tab2 = st.tabs(

    [

        "🔍 AI TÌM MÃ HÀNG",

        "📦 AI LƯU KHO"

    ]

)


# =====================================================================
# TAB 1
# AI AUTO SEARCH
# =====================================================================

with tab1:

    st.header(
        "🔍 AI TỰ NHẬN DIỆN & TÌM MÃ HÀNG"
    )


    st.info(

        "Không cần chọn dòng hàng. "
        "AI Vision tự nhận diện garment → "
        "khóa category → tìm mã tương đồng."

    )


    uploaded_search = st.file_uploader(

        "📂 Tải ảnh Sketch / ảnh mẫu:",

        type=[
            "png",
            "jpg",
            "jpeg"
        ],

        key="search_v30"

    )


    if uploaded_search:

        col1, col2 = st.columns(
            [1, 2]
        )


        with col1:

            st.image(

                uploaded_search,

                caption="Ảnh cần tìm",

                use_container_width=True

            )


        with col2:

            if st.button(

                "🤖 AI NHẬN DIỆN & TÌM MÃ",

                type="primary",

                key="search_button_v30"

            ):

                try:

                    raw_bytes = (
                        uploaded_search
                        .getvalue()
                    )


                    # =================================================
                    # AI VISION
                    # =================================================

                    with st.spinner(
                        "🧠 AI Vision đang nhìn và phân tích garment..."
                    ):

                        vision_result = (
                            analyze_garment_with_vision(
                                raw_bytes
                            )
                        )


                    # =================================================
                    # DISPLAY
                    # =================================================

                    display_ai_analysis(
                        vision_result
                    )


                    ai_category = (
                        vision_result[
                            "category"
                        ]
                    )


                    # =================================================
                    # CLIP EMBEDDING
                    # =================================================

                    with st.spinner(
                        "🔎 Đang tạo vector hình ảnh..."
                    ):

                        image_hash = (
                            get_image_hash(
                                raw_bytes
                            )
                        )


                        query_embedding = (
                            get_cached_embedding(

                                image_hash,

                                raw_bytes

                            )
                        )


                    # =================================================
                    # CATEGORY LOCK
                    # =================================================

                    st.divider()


                    st.subheader(
                        "🔒 CATEGORY LOCK"
                    )


                    st.success(

                        f"Chỉ tìm trong nhóm: "
                        f"**{ai_category}**"

                    )


                    # =================================================
                    # SUPABASE VECTOR SEARCH
                    # =================================================

                    with st.spinner(

                        f"🔎 Đang tìm "
                        f"mã {ai_category}..."

                    ):

                        response = (

                            supabase

                            .rpc(

                                "match_products_v2",

                                {

                                    "query_embedding":
                                        query_embedding,

                                    "match_threshold":
                                        0.30,

                                    "match_count":
                                        12,

                                    "filter_category":
                                        ai_category

                                }

                            )

                            .execute()

                        )


                    data = (
                        response.data
                        or []
                    )


                    # =================================================
                    # HARD FILTER
                    # =================================================

                    locked_results = []


                    target = (
                        ai_category
                        .strip()
                        .lower()
                    )


                    for item in data:

                        item_category = str(

                            item.get(
                                "category",
                                ""
                            )

                        ).strip().lower()


                        if (
                            item_category
                            ==
                            target
                        ):

                            locked_results.append(
                                item
                            )


                    # =================================================
                    # SORT
                    # =================================================

                    locked_results.sort(

                        key=lambda x:

                            float(

                                x.get(
                                    "similarity",
                                    0
                                )

                            ),

                        reverse=True

                    )


                    # =================================================
                    # RESULT
                    # =================================================

                    st.divider()


                    st.subheader(
                        "🎯 MÃ HÀNG TƯƠNG ĐỒNG"
                    )


                    if locked_results:

                        st.success(

                            f"Tìm được "
                            f"{len(locked_results)} "
                            f"mã trong nhóm "
                            f"**{ai_category}**."

                        )


                        cols = st.columns(
                            4
                        )


                        for index, item in enumerate(

                            locked_results[:12]

                        ):

                            with cols[
                                index % 4
                            ]:

                                st.markdown(
                                    "---"
                                )


                                product_code = str(

                                    item.get(
                                        "product_code",
                                        "N/A"
                                    )

                                )


                                st.subheader(
                                    product_code
                                )


                                image_url = (
                                    item.get(
                                        "image_url"
                                    )
                                )


                                if image_url:

                                    st.image(

                                        image_url,

                                        use_container_width=True

                                    )


                                similarity = float(

                                    item.get(
                                        "similarity",
                                        0
                                    )

                                )


                                st.metric(

                                    "Similarity",

                                    f"{similarity * 100:.2f}%"

                                )


                                st.success(

                                    f"🏷️ "
                                    f"{ai_category}"

                                )


                    else:

                        st.warning(

                            f"Không có mã "
                            f"**{ai_category}** "
                            "đủ tương đồng."

                        )


                except Exception as e:

                    st.error(
                        "❌ AI SEARCH ERROR"
                    )

                    st.exception(e)


# =====================================================================
# TAB 2
# AI AUTO STORAGE
# =====================================================================

with tab2:

    st.header(
        "📦 AI TỰ NHẬN DIỆN & LƯU KHO"
    )


    st.info(

        "Không cần chọn category. "
        "AI Vision sẽ tự nhận diện từng ảnh "
        "trước khi lưu."

    )


    uploaded_files = st.file_uploader(

        "📂 Chọn nhiều ảnh sản phẩm:",

        type=[
            "png",
            "jpg",
            "jpeg"
        ],

        accept_multiple_files=True,

        key="upload_v30"

    )


    if uploaded_files:

        st.write(

            f"📂 Đã chọn "
            f"**{len(uploaded_files)}** ảnh."

        )


        if st.button(

            "🤖 AI PHÂN LOẠI & TỰ ĐỘNG LƯU",

            type="primary",

            key="upload_button_v30"

        ):

            total = len(
                uploaded_files
            )


            progress = st.progress(
                0
            )


            status = st.empty()


            success_count = 0

            failed_count = 0


            results = []

            errors = []


            for index, file in enumerate(
                uploaded_files
            ):

                product_code = (
                    extract_product_code(
                        file.name
                    )
                )


                try:

                    # =================================================
                    # READ
                    # =================================================

                    raw_bytes = (
                        file.getvalue()
                    )


                    # =================================================
                    # VISION
                    # =================================================

                    status.text(

                        f"🧠 AI đang nhận diện "
                        f"{product_code}..."

                    )


                    vision_result = (
                        analyze_garment_with_vision(
                            raw_bytes
                        )
                    )


                    ai_category = (
                        vision_result[
                            "category"
                        ]
                    )


                    confidence = (
                        vision_result[
                            "confidence"
                        ]
                    )


                    # =================================================
                    # CLIP
                    # =================================================

                    status.text(

                        f"🔎 Đang tạo vector "
                        f"{product_code}..."

                    )


                    image_hash = (
                        get_image_hash(
                            raw_bytes
                        )
                    )


                    embedding = (
                        get_cached_embedding(

                            image_hash,

                            raw_bytes

                        )
                    )


                    # =================================================
                    # STORAGE
                    # =================================================

                    status.text(

                        f"☁️ Đang upload "
                        f"{product_code}..."

                    )


                    image_url = (
                        upload_image_to_storage(

                            raw_bytes,

                            file.name

                        )
                    )


                    # =================================================
                    # DATABASE
                    # =================================================

                    status.text(

                        f"💾 Đang lưu "
                        f"{product_code} → "
                        f"{ai_category}"

                    )


                    save_product(

                        product_code=
                            product_code,

                        image_url=
                            image_url,

                        category=
                            ai_category,

                        embedding=
                            embedding,

                        ai_analysis=
                            vision_result

                    )


                    # =================================================
                    # SUCCESS
                    # =================================================

                    success_count += 1


                    results.append({

                        "Mã hàng":
                            product_code,

                        "AI Category":
                            ai_category,

                        "Confidence":
                            f"{confidence:.1f}%",

                        "One Piece":
                            "YES"
                            if vision_result[
                                "one_piece"
                            ]
                            else
                            "NO",

                        "Cargo Pocket":
                            "YES"
                            if vision_result[
                                "cargo_pockets"
                            ]
                            else
                            "NO",

                        "Status":
                            "✅ Đã lưu"

                    })


                except Exception as e:

                    failed_count += 1


                    errors.append({

                        "File":
                            file.name,

                        "Mã":
                            product_code,

                        "Lỗi":
                            str(e)

                    })


                    results.append({

                        "Mã hàng":
                            product_code,

                        "AI Category":
                            "—",

                        "Confidence":
                            "—",

                        "One Piece":
                            "—",

                        "Cargo Pocket":
                            "—",

                        "Status":
                            "❌ Lỗi"

                    })


                progress.progress(

                    int(

                        (
                            index + 1
                        )
                        /
                        total
                        *
                        100

                    )

                )


            status.empty()


            # =========================================================
            # SUMMARY
            # =========================================================

            st.divider()


            c1, c2, c3 = st.columns(
                3
            )


            with c1:

                st.metric(
                    "Tổng ảnh",
                    total
                )


            with c2:

                st.metric(
                    "Đã lưu",
                    success_count
                )


            with c3:

                st.metric(
                    "Lỗi",
                    failed_count
                )


            # =========================================================
            # RESULT TABLE
            # =========================================================

            if results:

                st.subheader(
                    "📊 KẾT QUẢ AI"
                )


                df_result = pd.DataFrame(
                    results
                )


                st.dataframe(

                    df_result,

                    use_container_width=True,

                    hide_index=True

                )


            # =========================================================
            # ERRORS
            # =========================================================

            if errors:

                with st.expander(
                    "🔎 Chi tiết lỗi"
                ):

                    for error in errors:

                        st.error(

                            f"📄 "
                            f"{error['File']}\n\n"
                            f"🏷️ "
                            f"{error['Mã']}\n\n"
                            f"❌ "
                            f"{error['Lỗi']}"

                        )


            if success_count:

                st.success(

                    f"🎉 Hoàn thành! "
                    f"AI đã nhận diện và lưu "
                    f"{success_count}/{total} mã."

                )
# =====================================================================
# 🗑️ DELETE ALL PRODUCT DATA
# =====================================================================

st.divider()

st.subheader("🗑️ QUẢN LÝ KHO HÀNG")

st.warning(
    "⚠️ Chức năng này sẽ xóa TOÀN BỘ mã hàng và ảnh "
    "đã lưu trong kho sản phẩm. Không thể hoàn tác."
)

if "confirm_delete_all_products" not in st.session_state:
    st.session_state[
        "confirm_delete_all_products"
    ] = False


# =====================================================================
# BUTTON 1 - SHOW CONFIRMATION
# =====================================================================

if st.button(
    "🗑️ XÓA TẤT CẢ DỮ LIỆU KHO",
    type="secondary",
    key="delete_all_products_button"
):

    st.session_state[
        "confirm_delete_all_products"
    ] = True


# =====================================================================
# CONFIRMATION
# =====================================================================

if st.session_state[
    "confirm_delete_all_products"
]:

    st.error(
        "🚨 BẠN ĐANG YÊU CẦU XÓA TOÀN BỘ KHO HÀNG!"
    )

    st.write(
        "Thao tác này sẽ xóa:"
    )

    st.write(
        "• Toàn bộ records trong bảng `products`"
    )

    st.write(
        "• Toàn bộ ảnh trong bucket `product-images`"
    )

    st.write(
        "• Dữ liệu sẽ không thể khôi phục bằng nút Undo."
    )


    confirm_text = st.text_input(
        "Nhập chính xác DELETE để xác nhận:",
        key="delete_confirmation_text"
    )


    col_delete_1, col_delete_2 = st.columns(2)


    # =================================================================
    # CONFIRM DELETE
    # =================================================================

    with col_delete_1:

        if st.button(
            "🔥 XÁC NHẬN XÓA TOÀN BỘ",
            type="primary",
            key="confirm_delete_all"
        ):

            if (
                confirm_text.strip().upper()
                !=
                "DELETE"
            ):

                st.error(
                    "❌ Bạn phải nhập chính xác: DELETE"
                )

            else:

                try:

                    # =================================================
                    # 1. LẤY DANH SÁCH PRODUCTS
                    # =================================================

                    with st.spinner(
                        "🔎 Đang lấy danh sách dữ liệu..."
                    ):

                        products_response = (
                            supabase
                            .table("products")
                            .select(
                                "id, product_code, image_url"
                            )
                            .execute()
                        )


                        products_data = (
                            products_response.data
                            or []
                        )


                    # =================================================
                    # 2. XÓA DATABASE RECORDS
                    # =================================================

                    with st.spinner(
                        "🗑️ Đang xóa dữ liệu products..."
                    ):

                        # ------------------------------------------------
                        # Xóa theo ID nếu có
                        # ------------------------------------------------

                        delete_errors = []


                        for product in products_data:

                            product_id = product.get(
                                "id"
                            )


                            try:

                                if product_id is not None:

                                    (
                                        supabase
                                        .table("products")
                                        .delete()
                                        .eq(
                                            "id",
                                            product_id
                                        )
                                        .execute()
                                    )

                                else:

                                    product_code = (
                                        product.get(
                                            "product_code"
                                        )
                                    )

                                    if product_code:

                                        (
                                            supabase
                                            .table("products")
                                            .delete()
                                            .eq(
                                                "product_code",
                                                product_code
                                            )
                                            .execute()
                                        )

                            except Exception as e:

                                delete_errors.append(
                                    str(e)
                                )


                    # =================================================
                    # 3. XÓA STORAGE IMAGES
                    # =================================================

                    with st.spinner(
                        "☁️ Đang xóa toàn bộ ảnh trong Storage..."
                    ):

                        bucket_name = (
                            "product-images"
                        )


                        storage = (
                            supabase
                            .storage
                            .from_(
                                bucket_name
                            )
                        )


                        # ------------------------------------------------
                        # Lấy file list
                        # ------------------------------------------------

                        storage_files = (
                            storage
                            .list()
                        )


                        file_paths = []


                        if storage_files:

                            for item in storage_files:

                                file_name = (
                                    item.get(
                                        "name"
                                    )
                                )


                                if file_name:

                                    file_paths.append(
                                        file_name
                                    )


                        # ------------------------------------------------
                        # Xóa theo batch
                        # ------------------------------------------------

                        if file_paths:

                            batch_size = 100


                            for start in range(
                                0,
                                len(file_paths),
                                batch_size
                            ):

                                batch = file_paths[
                                    start:
                                    start + batch_size
                                ]


                                storage.remove(
                                    batch
                                )


                    # =================================================
                    # 4. RESET SESSION
                    # =================================================

                    st.session_state[
                        "confirm_delete_all_products"
                    ] = False


                    st.session_state[
                        "delete_confirmation_text"
                    ] = ""


                    # =================================================
                    # 5. RESULT
                    # =================================================

                    if delete_errors:

                        st.warning(
                            "⚠️ Đã thực hiện xóa nhưng "
                            "một số record có lỗi."
                        )

                        with st.expander(
                            "Chi tiết lỗi"
                        ):

                            for error in delete_errors:

                                st.error(
                                    error
                                )

                    else:

                        st.success(
                            "🎉 ĐÃ XÓA TOÀN BỘ KHO HÀNG!"
                        )

                        st.info(
                            "Bảng products và các ảnh "
                            "trong bucket product-images "
                            "đã được dọn."
                        )


                    st.rerun()


                except Exception as e:

                    st.error(
                        "❌ Không thể xóa toàn bộ kho."
                    )

                    st.exception(e)


    # =================================================================
    # CANCEL
    # =================================================================

    with col_delete_2:

        if st.button(
            "↩️ HỦY",
            key="cancel_delete_all"
        ):

            st.session_state[
                "confirm_delete_all_products"
            ] = False


            st.session_state[
                "delete_confirmation_text"
            ] = ""


            st.rerun()

# =====================================================================
# END V3.0
# =====================================================================
