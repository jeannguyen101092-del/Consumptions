# =====================================================================
# 🤖🔍 AI GARMENT SEARCH & WAREHOUSE
# VERSION V3.3 - FULL CODE
#
# TAB 1:
#   Upload ảnh
#   AI tự nhận diện category
#   CLIP embedding
#   Tự tìm mã tương đồng
#   KHÔNG chọn category thủ công
#
# TAB 2:
#   Upload nhiều ảnh
#   AI tự nhận category
#   CLIP embedding
#   Lưu Storage
#   Lưu products
#   Xóa toàn bộ kho
#
# SECURITY:
#   KHÔNG hard-code SUPABASE KEY
#   KHÔNG hard-code HF TOKEN
#   Đọc từ Streamlit Secrets / Environment
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

import os
import io
import re
import json
import base64

from PIL import Image

from supabase import create_client, Client

try:
    from huggingface_hub import InferenceClient
except Exception:
    InferenceClient = None


# =====================================================================
# 3. ĐỌC CONFIG AN TOÀN
# =====================================================================

def _clean_value(value):

    if value is None:
        return None

    try:
        value = str(value).strip()
    except Exception:
        return None

    if not value:
        return None

    return value


def read_config(*names):

    # ---------------------------------------------------------
    # A. Streamlit Secrets trực tiếp
    # ---------------------------------------------------------

    for name in names:

        try:

            value = st.secrets.get(name)

            value = _clean_value(value)

            if value:
                return value

        except Exception:
            pass


    # ---------------------------------------------------------
    # B. Environment variable
    # ---------------------------------------------------------

    for name in names:

        try:

            value = os.getenv(name)

            value = _clean_value(value)

            if value:
                return value

        except Exception:
            pass


    # ---------------------------------------------------------
    # C. Các group thường gặp
    # ---------------------------------------------------------

    groups = [
        "supabase",
        "SUPABASE",
        "Supabase",
        "huggingface",
        "HUGGINGFACE",
        "HuggingFace",
        "hf",
        "HF"
    ]


    for group_name in groups:

        try:

            group = st.secrets.get(
                group_name
            )

        except Exception:

            group = None


        if not group:
            continue


        for name in names:

            try:

                value = group.get(name)

                value = _clean_value(value)

                if value:
                    return value

            except Exception:
                pass


    return None


# =====================================================================
# 4. SUPABASE CONFIG
# =====================================================================

SUPABASE_URL = read_config(

    "SUPABASE_URL",
    "SUPABASE_PROJECT_URL",
    "supabase_url",
    "supabase_project_url",
    "url"

)


SUPABASE_KEY = read_config(

    "SUPABASE_KEY",
    "SUPABASE_ANON_KEY",
    "SUPABASE_PUBLISHABLE_KEY",
    "supabase_key",
    "supabase_anon_key",
    "anon_key",
    "key"

)


# =====================================================================
# 5. HUGGING FACE TOKEN
# =====================================================================

HF_TOKEN = read_config(

    "HF_TOKEN",
    "HUGGINGFACE_TOKEN",
    "HUGGING_FACE_TOKEN",
    "HF_API_TOKEN",
    "huggingface_token",
    "hf_token"

)


# =====================================================================
# 6. KIỂM TRA SUPABASE
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
        "❌ Không đọc được cấu hình bảo mật."
    )

    st.write(
        "Hệ thống đang tìm các tên cấu hình sau:"
    )

    for x in missing:
        st.write(
            f"- `{x}`"
        )


    st.info(
        "Không cần ghi key trực tiếp vào code."
    )

    st.stop()


# =====================================================================
# 7. SUPABASE CLIENT
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
# 8. HUGGING FACE CLIENT
# =====================================================================

if InferenceClient is None:

    st.error(
        "❌ Chưa cài huggingface_hub."
    )

    st.code(
        "huggingface_hub>=0.33.0"
    )

    st.stop()


try:

    hf_client = InferenceClient(
        api_key=HF_TOKEN
    )

except Exception as e:

    st.error(
        "❌ Không khởi tạo được Hugging Face."
    )

    st.exception(e)

    st.stop()


# =====================================================================
# 9. MODEL
# =====================================================================

# Vision model
VISION_MODEL = (
    "moonshotai/Kimi-K2.7-Code:novita"
)

# CLIP
CLIP_MODEL = (
    "openai/clip-vit-base-patch32"
)


# =====================================================================
# 10. DATABASE
# =====================================================================

PRODUCT_TABLE = "products"

PRODUCT_BUCKET = "product-images"

MATCH_RPC = "match_products_v2"


# =====================================================================
# 11. CATEGORY
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
# 12. CATEGORY ALIAS
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
# 13. IMAGE → DATA URL
# =====================================================================

def image_to_data_url(
    image_bytes
):

    try:

        image = Image.open(
            io.BytesIO(
                image_bytes
            )
        )

        image = image.convert(
            "RGB"
        )

        buffer = io.BytesIO()

        image.save(
            buffer,
            format="JPEG",
            quality=92
        )

        image_bytes = (
            buffer.getvalue()
        )

    except Exception:
        pass


    encoded = base64.b64encode(
        image_bytes
    ).decode(
        "utf-8"
    )


    return (
        "data:image/jpeg;base64,"
        + encoded
    )


# =====================================================================
# 14. JSON PARSER
# =====================================================================

def extract_json_from_ai(
    text
):

    if not text:

        raise Exception(
            "AI không trả dữ liệu."
        )


    text = str(
        text
    ).strip()


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


    match = re.search(
        r"\{.*\}",
        text,
        flags=re.S
    )


    if not match:

        raise Exception(
            "AI không trả JSON hợp lệ:\n"
            + text[:2000]
        )


    json_text = match.group(
        0
    )


    try:

        return json.loads(
            json_text
        )

    except Exception as e:

        raise Exception(
            "JSON AI lỗi: "
            + str(e)
            + "\n"
            + json_text[:2000]
        )


# =====================================================================
# 15. VISION PROMPT
# =====================================================================

GARMENT_PROMPT = """

You are a senior apparel technical designer.

Analyze the garment construction very carefully.

This image will be used for commercial garment similarity search.

IMPORTANT:

FIRST determine whether this is ONE PIECE or a SEPARATE GARMENT.

=========================================================
JUMPSUIT
=========================================================

If upper body and lower body are physically connected:

category = "Áo liền quần"

NEVER classify a jumpsuit as cargo pants.

=========================================================
BIB OVERALL
=========================================================

If there is a bib front and shoulder straps:

category = "Quần yếm"

NEVER classify bib overall as cargo pants.

=========================================================
CARGO PANTS
=========================================================

Cargo requires:

- separate pants
- visible external cargo/patch pockets
- pockets located on side legs

If pockets are not clearly visible:

cargo_pockets = false

Do NOT classify as cargo.

=========================================================
JEANS
=========================================================

Separate denim pants.

=========================================================
JOGGER
=========================================================

Separate pants with elastic/rib ankle cuffs.

=========================================================
JACKET
=========================================================

Separate upper-body outerwear.

=========================================================
DRESS
=========================================================

One-piece dress silhouette.

Do not confuse dress with jumpsuit.

=========================================================
CATEGORIES
=========================================================

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

=========================================================
RETURN ONLY JSON
=========================================================

{
  "category": "Quần dài",
  "confidence": 95,
  "one_piece": false,
  "bib": false,
  "shoulder_straps": false,
  "cargo_pockets": false,
  "denim": false,
  "jogger_cuffs": false,
  "sleeve": "none",
  "collar": "none",
  "hood": false,
  "silhouette": "straight",
  "length": "full",
  "reason": "..."
}

"""


# =====================================================================
# 16. NORMALIZE AI
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


    if category_upper in CATEGORY_ALIASES:

        category = CATEGORY_ALIASES[
            category_upper
        ]


    if category not in CATEGORY_LIST:

        category = "Quần dài"


    result[
        "category"
    ] = category


    # ---------------------------------------------------------
    # Boolean
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


        result[
            field
        ] = bool(
            value
        )


    # ---------------------------------------------------------
    # Confidence
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


    result[
        "confidence"
    ] = max(
        0,
        min(
            100,
            confidence
        )
    )


    # =========================================================
    # HARD RULE
    # =========================================================

    # Jumpsuit
    if result[
        "one_piece"
    ]:

        if (

            result[
                "bib"
            ]

            and

            result[
                "shoulder_straps"
            ]

        ):

            result[
                "category"
            ] = "Quần yếm"

        else:

            result[
                "category"
            ] = "Áo liền quần"


    # Bib overall
    elif (

        result[
            "bib"
        ]

        and

        result[
            "shoulder_straps"
        ]

    ):

        result[
            "category"
        ] = "Quần yếm"


    # Cargo
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


    # Denim
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


    # Jogger
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


    return result


# =====================================================================
# 17. VISION AI
# =====================================================================

def analyze_garment_with_vision(
    image_bytes
):

    image_url = (
        image_to_data_url(
            image_bytes
        )
    )


    try:

        response = (

            hf_client
            .chat
            .completions
            .create(

                model=VISION_MODEL,

                messages=[

                    {
                        "role": "user",

                        "content": [

                            {
                                "type":
                                    "image_url",

                                "image_url": {
                                    "url":
                                        image_url
                                }
                            },

                            {
                                "type":
                                    "text",

                                "text":
                                    GARMENT_PROMPT
                            }

                        ]
                    }

                ],

                max_tokens=1200,

                temperature=0.0

            )

        )


    except Exception as e:

        raise Exception(
            "Hugging Face Vision API lỗi: "
            + str(e)
        )


    try:

        content = (
            response
            .choices[0]
            .message
            .content
        )

    except Exception as e:

        raise Exception(
            "Không đọc được Vision response: "
            + str(e)
        )


    result = extract_json_from_ai(
        content
    )


    return normalize_garment_result(
        result
    )

# =====================================================================
# 🧠 CLIP LOCAL IMAGE EMBEDDING
# VERSION V3.5
# KHÔNG DÙNG HUGGING FACE INFERENCE CHO CLIP
# OUTPUT = 512D
# =====================================================================

import io
import numpy as np
import torch
import streamlit as st

from PIL import Image
from transformers import CLIPProcessor, CLIPModel


# =====================================================================
# 1. LOAD CLIP MODEL
# =====================================================================

@st.cache_resource(show_spinner=False)
def load_clip_model():

    model_name = "openai/clip-vit-base-patch32"

    processor = CLIPProcessor.from_pretrained(
        model_name
    )

    model = CLIPModel.from_pretrained(
        model_name
    )

    model.eval()

    return processor, model


# =====================================================================
# 2. IMAGE → CLIP 512D
# =====================================================================

def get_clip_embedding(image_bytes):

    try:

        # -------------------------------------------------------------
        # LOAD MODEL
        # -------------------------------------------------------------

        processor, model = load_clip_model()


        # -------------------------------------------------------------
        # OPEN IMAGE
        # -------------------------------------------------------------

        image = Image.open(
            io.BytesIO(
                image_bytes
            )
        ).convert(
            "RGB"
        )


        # -------------------------------------------------------------
        # PROCESS IMAGE
        # -------------------------------------------------------------

        inputs = processor(
            images=image,
            return_tensors="pt"
        )


        # -------------------------------------------------------------
        # CLIP IMAGE EMBEDDING
        # -------------------------------------------------------------

        with torch.no_grad():

            image_features = (
                model.get_image_features(
                    **inputs
                )
            )


        # -------------------------------------------------------------
        # FIX TRANSFORMERS OUTPUT
        # -------------------------------------------------------------

        if hasattr(
            image_features,
            "pooler_output"
        ):

            image_features = (
                image_features
                .pooler_output
            )


        if not torch.is_tensor(
            image_features
        ):

            image_features = torch.tensor(
                image_features
            )


        # -------------------------------------------------------------
        # FLATTEN
        # -------------------------------------------------------------

        image_features = (
            image_features
            .detach()
            .cpu()
            .float()
        )


        # -------------------------------------------------------------
        # EXPECTED SHAPE
        # -------------------------------------------------------------

        if image_features.ndim == 1:

            vector = image_features


        elif image_features.ndim == 2:

            vector = image_features[0]


        else:

            vector = image_features.reshape(
                -1
            )


        # -------------------------------------------------------------
        # CHECK 512D
        # -------------------------------------------------------------

        vector = vector.numpy()


        if len(vector) != 512:

            raise Exception(

                "CLIP output không phải 512D. "
                f"Shape={tuple(image_features.shape)}, "
                f"Length={len(vector)}"

            )


        # -------------------------------------------------------------
        # L2 NORMALIZATION
        # -------------------------------------------------------------

        norm = np.linalg.norm(
            vector
        )


        if norm == 0:

            raise Exception(
                "CLIP vector có norm = 0."
            )


        vector = (
            vector / norm
        )


        # -------------------------------------------------------------
        # PYTHON LIST
        # -------------------------------------------------------------

        return vector.astype(
            np.float32
        ).tolist()


    except Exception as e:

        raise Exception(

            "CLIP LOCAL embedding lỗi: "
            + repr(e)

        )

# =====================================================================
# 19. PRODUCT CODE
# =====================================================================

def clean_product_code(
    filename
):

    filename = str(
        filename
    )


    filename_only = (
        filename
        .rsplit(
            ".",
            1
        )[0]
    )


    product_code = re.sub(
        r"[^A-Za-z0-9_\-]",
        "",
        filename_only
    )


    return product_code.upper()


# =====================================================================
# 20. STORAGE
# =====================================================================

def upload_image_to_storage(
    image_bytes,
    filename
):

    bucket = (
        supabase
        .storage
        .from_(
            PRODUCT_BUCKET
        )
    )


    bucket.upload(

        path=filename,

        file=image_bytes,

        file_options={
            "content-type":
                "image/jpeg",
            "upsert":
                "true"
        }

    )


    return bucket.get_public_url(
        filename
    )


# =====================================================================
# 21. SAVE DATABASE
# =====================================================================

def save_product(
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


    return (

        supabase
        .table(
            PRODUCT_TABLE
        )
        .upsert(

            payload,

            on_conflict=
                "product_code"

        )
        .execute()

    )


# =====================================================================
# 22. SEARCH
# =====================================================================

def search_products(
    embedding,
    count=30,
    threshold=0.15
):

    response = (

        supabase
        .rpc(

            MATCH_RPC,

            {
                "query_embedding":
                    embedding,

                "match_threshold":
                    threshold,

                "match_count":
                    count
            }

        )
        .execute()

    )


    return (
        response.data
        or []
    )


# =====================================================================
# 23. CATEGORY LOCK
# =====================================================================

def category_lock(
    results,
    ai_category
):

    if not results:
        return []


    return [

        item

        for item in results

        if str(
            item.get(
                "category",
                ""
            )
        ).strip()
        ==
        ai_category

    ]


# =====================================================================
# 24. SHOW AI
# =====================================================================

def show_ai_result(
    result
):

    st.markdown(
        "### 🤖 AI NHẬN DIỆN"
    )


    c1, c2, c3 = st.columns(
        3
    )


    with c1:

        st.metric(
            "Category",
            result[
                "category"
            ]
        )


    with c2:

        st.metric(
            "Confidence",
            f"{result['confidence']:.1f}%"
        )


    with c3:

        st.metric(

            "One Piece",

            "YES"
            if result[
                "one_piece"
            ]
            else
            "NO"

        )


    with st.expander(
        "🔎 Chi tiết AI"
    ):

        st.json(
            result
        )


# =====================================================================
# 25. SHOW RESULTS
# =====================================================================

def show_results(
    results
):

    if not results:

        st.warning(
            "Không tìm thấy mã tương đồng cùng category."
        )

        return


    cols = st.columns(
        min(
            len(results),
            4
        )
    )


    for i, item in enumerate(
        results
    ):

        with cols[
            i % len(cols)
        ]:

            similarity = item.get(
                "similarity",
                0
            )


            try:

                similarity = float(
                    similarity
                )

            except Exception:

                similarity = 0


            st.metric(

                "Độ tương đồng",

                f"{similarity * 100:.2f}%"

            )


            st.subheader(
                str(
                    item.get(
                        "product_code",
                        "N/A"
                    )
                )
            )


            st.caption(
                "Category: "
                +
                str(
                    item.get(
                        "category",
                        ""
                    )
                )
            )


            image_url = item.get(
                "image_url"
            )


            if image_url:

                st.image(
                    image_url,
                    use_container_width=True
                )


# =====================================================================
# 26. DELETE DATABASE
# =====================================================================

def delete_all_products():

    return (

        supabase
        .table(
            PRODUCT_TABLE
        )
        .delete()
        .not_.is_(
            "product_code",
            "null"
        )
        .execute()

    )


# =====================================================================
# 27. DELETE STORAGE
# =====================================================================

def delete_all_storage():

    bucket = (
        supabase
        .storage
        .from_(
            PRODUCT_BUCKET
        )
    )


    files = bucket.list()


    if not files:
        return 0


    names = []


    for item in files:

        name = item.get(
            "name"
        )

        if name:
            names.append(
                name
            )


    deleted = 0


    for start in range(
        0,
        len(names),
        100
    ):

        batch = names[
            start:
            start + 100
        ]


        bucket.remove(
            batch
        )


        deleted += len(
            batch
        )


    return deleted


# =====================================================================
# 28. HEADER
# =====================================================================

st.title(
    "🔍 AI TÌM KIẾM MÃ HÀNG TƯƠNG ĐỒNG"
)

st.caption(
    "Vision AI + CLIP + Supabase"
)


# =====================================================================
# 29. TABS
# =====================================================================

tab1, tab2 = st.tabs(

    [
        "🔍 TÌM KIẾM MÃ HÀNG TƯƠNG ĐỒNG",
        "📦 LƯU KHO HÀNG LOẠT"
    ]

)


# #####################################################################
# TAB 1
# #####################################################################

with tab1:

    st.header(
        "🔍 Tìm mã hàng qua ảnh"
    )


    st.info(

        "AI tự nhận diện loại hàng. "
        "Không cần chọn dòng hàng."

    )


    uploaded_sketch = st.file_uploader(

        "📂 Tải ảnh Sketch / ảnh mẫu",

        type=[
            "png",
            "jpg",
            "jpeg"
        ],

        key="search_image"

    )


    if uploaded_sketch:

        c1, c2 = st.columns(
            2
        )


        with c1:

            st.image(

                uploaded_sketch,

                width=350

            )


        with c2:

            st.write(
                f"**File:** {uploaded_sketch.name}"
            )


            if st.button(

                "🚀 AI NHẬN DIỆN & TÌM MÃ",

                type="primary",

                key="search_button"

            ):

                try:

                    image_bytes = (
                        uploaded_sketch
                        .getvalue()
                    )


                    # =================================================
                    # AI
                    # =================================================

                    with st.spinner(
                        "🤖 AI đang nhận diện..."
                    ):

                        ai_result = (
                            analyze_garment_with_vision(
                                image_bytes
                            )
                        )


                    show_ai_result(
                        ai_result
                    )


                    # =================================================
                    # CLIP
                    # =================================================

                    with st.spinner(
                        "🧠 CLIP đang phân tích hình ảnh..."
                    ):

                        embedding = (
                            get_clip_embedding(
                                image_bytes
                            )
                        )


                    st.caption(
                        f"CLIP: {len(embedding)}D"
                    )


                    # =================================================
                    # SEARCH
                    # =================================================

                    with st.spinner(
                        "🔎 Đang tìm mã tương đồng..."
                    ):

                        results = (
                            search_products(
                                embedding,
                                count=30,
                                threshold=0.15
                            )
                        )


                    # =================================================
                    # CATEGORY LOCK
                    # =================================================

                    locked = (
                        category_lock(

                            results,

                            ai_result[
                                "category"
                            ]

                        )
                    )


                    st.markdown(
                        "### 🔒 CATEGORY LOCK"
                    )


                    st.success(

                        "AI nhận diện: "
                        +
                        ai_result[
                            "category"
                        ]

                    )


                    st.write(
                        f"CLIP tìm thấy: {len(results)} mã"
                    )


                    st.write(
                        f"Cùng category: {len(locked)} mã"
                    )


                    show_results(
                        locked[:8]
                    )


                    if (
                        not locked
                        and
                        results
                    ):

                        st.warning(

                            "Có kết quả giống hình ảnh "
                            "nhưng khác loại hàng. "
                            "Hệ thống đã loại bỏ để tránh "
                            "Áo/Jumpsuit/Overall bị lẫn với quần."

                        )


                except Exception as e:

                    st.error(
                        "❌ Lỗi tìm kiếm:"
                    )

                    st.exception(e)


# #####################################################################
# TAB 2
# #####################################################################

with tab2:

    st.header(
        "📦 Đẩy dữ liệu mã hàng hàng loạt"
    )


    st.info(

        "AI tự nhận diện category. "
        "Không cần chọn dòng hàng."

    )


    uploaded_files = st.file_uploader(

        "📂 Chọn nhiều ảnh",

        type=[
            "png",
            "jpg",
            "jpeg"
        ],

        accept_multiple_files=True,

        key="warehouse_files"

    )


    if uploaded_files:

        st.write(
            f"Đã chọn **{len(uploaded_files)}** file."
        )


        if st.button(

            "📤 AI NHẬN DIỆN & LƯU TOÀN BỘ",

            type="primary",

            key="save_all_button"

        ):

            progress = st.progress(
                0
            )

            status = st.empty()


            success = 0
            errors = 0


            results = []


            total = len(
                uploaded_files
            )


            for index, file in enumerate(
                uploaded_files
            ):

                product_code = (
                    clean_product_code(
                        file.name
                    )
                )


                status.write(

                    f"⏳ "
                    f"{index + 1}/{total} "
                    f"- {product_code}"

                )


                try:

                    image_bytes = (
                        file.getvalue()
                    )


                    # =================================================
                    # AI CATEGORY
                    # =================================================

                    ai_result = (
                        analyze_garment_with_vision(
                            image_bytes
                        )
                    )


                    category = ai_result[
                        "category"
                    ]


                    # =================================================
                    # CLIP
                    # =================================================

                    embedding = (
                        get_clip_embedding(
                            image_bytes
                        )
                    )


                    # =================================================
                    # STORAGE
                    # =================================================

                    storage_name = (
                        product_code
                        +
                        ".jpg"
                    )


                    image_url = (
                        upload_image_to_storage(

                            image_bytes,

                            storage_name

                        )
                    )


                    # =================================================
                    # DATABASE
                    # =================================================

                    save_product(

                        product_code,

                        image_url,

                        category,

                        embedding

                    )


                    success += 1


                    results.append({

                        "Mã hàng":
                            product_code,

                        "AI Category":
                            category,

                        "Confidence":
                            round(
                                ai_result[
                                    "confidence"
                                ],
                                1
                            ),

                        "Status":
                            "✅ SUCCESS"

                    })


                except Exception as e:

                    errors += 1


                    results.append({

                        "Mã hàng":
                            product_code,

                        "AI Category":
                            "ERROR",

                        "Confidence":
                            0,

                        "Status":
                            "❌ "
                            +
                            str(e)

                    })


                    st.error(

                        f"{file.name}: "
                        f"{str(e)}"

                    )


                progress.progress(
                    (index + 1) / total
                )


            status.empty()


            st.divider()


            c1, c2, c3 = st.columns(
                3
            )


            with c1:

                st.metric(
                    "Tổng",
                    total
                )


            with c2:

                st.metric(
                    "Thành công",
                    success
                )


            with c3:

                st.metric(
                    "Lỗi",
                    errors
                )


            if results:

                st.markdown(
                    "### 🤖 KẾT QUẢ AI"
                )


                st.dataframe(

                    results,

                    use_container_width=True

                )


# =====================================================================
# 📦 TAB 2 - LƯU KHO HÀNG LOẠT
# VERSION V3.6
#
# 🗑️ XÓA FILE HIỆN TẠI = CHỈ XÓA FILE ĐANG CHỜ TRÊN MÀN HÌNH
#
# ❌ KHÔNG XÓA SUPABASE
# ❌ KHÔNG XÓA DATABASE
# ❌ KHÔNG XÓA STORAGE
# =====================================================================

with tab2:

    st.header(
        "📦 ĐẨY DỮ LIỆU MÃ HÀNG HÀNG LOẠT"
    )

    st.info(
        "AI tự nhận diện category. "
        "Sau khi lưu, dữ liệu trong Supabase vẫn được giữ nguyên."
    )


    # =================================================================
    # 1. TẠO VERSION CHO FILE UPLOADER
    # =================================================================

    if "warehouse_uploader_version" not in st.session_state:

        st.session_state[
            "warehouse_uploader_version"
        ] = 0


    uploader_key = (
        "warehouse_files_"
        +
        str(
            st.session_state[
                "warehouse_uploader_version"
            ]
        )
    )


    # =================================================================
    # 2. FILE UPLOADER
    # =================================================================

    uploaded_files = st.file_uploader(

        "📂 Chọn nhiều ảnh sản phẩm",

        type=[
            "png",
            "jpg",
            "jpeg"
        ],

        accept_multiple_files=True,

        key=uploader_key

    )


    # =================================================================
    # 3. NẾU CÓ FILE ĐANG CHỜ
    # =================================================================

    if uploaded_files:

        st.write(
            f"📂 Đang có **{len(uploaded_files)}** file chờ xử lý."
        )


        # -------------------------------------------------------------
        # HIỂN THỊ DANH SÁCH FILE
        # -------------------------------------------------------------

        with st.expander(
            "📋 Xem danh sách file đang chờ",
            expanded=True
        ):

            for i, file in enumerate(
                uploaded_files,
                start=1
            ):

                st.write(
                    f"{i}. `{file.name}`"
                )


        st.divider()


        # =============================================================
        # 4. NÚT LƯU KHO
        # =============================================================

        if st.button(

            "📤 AI NHẬN DIỆN & LƯU TOÀN BỘ",

            type="primary",

            key="save_all_button_v36"

        ):

            progress = st.progress(
                0
            )

            status = st.empty()

            success = 0
            errors = 0

            total = len(
                uploaded_files
            )

            results = []


            # ---------------------------------------------------------
            # XỬ LÝ TỪNG FILE
            # ---------------------------------------------------------

            for index, file in enumerate(
                uploaded_files
            ):

                product_code = clean_product_code(
                    file.name
                )


                status.write(

                    f"⏳ Đang xử lý "
                    f"{index + 1}/{total}: "
                    f"**{product_code}**"

                )


                try:

                    image_bytes = (
                        file.getvalue()
                    )


                    # =================================================
                    # AI NHẬN DIỆN
                    # =================================================

                    ai_result = (
                        analyze_garment_with_vision(
                            image_bytes
                        )
                    )


                    category = ai_result[
                        "category"
                    ]


                    # =================================================
                    # CLIP
                    # =================================================

                    embedding = (
                        get_clip_embedding(
                            image_bytes
                        )
                    )


                    # =================================================
                    # STORAGE
                    # =================================================

                    storage_name = (
                        product_code
                        +
                        ".jpg"
                    )


                    image_url = (
                        upload_image_to_storage(

                            image_bytes,

                            storage_name

                        )
                    )


                    # =================================================
                    # DATABASE
                    # =================================================

                    save_product(

                        product_code,

                        image_url,

                        category,

                        embedding

                    )


                    success += 1


                    results.append({

                        "Mã hàng":
                            product_code,

                        "Category":
                            category,

                        "Confidence":
                            round(
                                ai_result[
                                    "confidence"
                                ],
                                1
                            ),

                        "Status":
                            "✅ SUCCESS"

                    })


                except Exception as e:

                    errors += 1


                    results.append({

                        "Mã hàng":
                            product_code,

                        "Category":
                            "ERROR",

                        "Confidence":
                            0,

                        "Status":
                            "❌ "
                            +
                            str(e)

                    })


                progress.progress(
                    (index + 1) / total
                )


            status.empty()


            # ---------------------------------------------------------
            # LƯU KẾT QUẢ VÀO SESSION
            # ---------------------------------------------------------

            st.session_state[
                "warehouse_results"
            ] = results


            # ---------------------------------------------------------
            # THỐNG KÊ
            # ---------------------------------------------------------

            st.success(

                f"🎉 Hoàn thành: "
                f"**{success}/{total}** mã hàng."

            )


            if errors:

                st.warning(

                    f"⚠️ Có {errors} file lỗi."

                )


    # =================================================================
    # 5. HIỂN THỊ KẾT QUẢ LƯU
    # =================================================================

    if (
        "warehouse_results"
        in st.session_state
    ):

        results = st.session_state[
            "warehouse_results"
        ]


        if results:

            st.markdown(
                "### 🤖 KẾT QUẢ AI"
            )


            st.dataframe(

                results,

                use_container_width=True

            )


    # =================================================================
    # 6. 🗑️ XÓA FILE ĐANG CHỜ TRÊN MÀN HÌNH
    # =================================================================
    #
    # QUAN TRỌNG:
    #
    # NÚT NÀY KHÔNG XÓA DATABASE
    # NÚT NÀY KHÔNG XÓA STORAGE
    # NÚT NÀY KHÔNG XÓA PRODUCTS
    #
    # Nó chỉ reset widget file_uploader.
    # =================================================================

    st.divider()


    if st.button(

        "🗑️ XÓA FILE ĐANG CHỜ",

        key="clear_pending_files_v36"

    ):

        # -------------------------------------------------------------
        # TĂNG VERSION
        #
        # Streamlit sẽ tạo một file_uploader mới hoàn toàn.
        # File cũ trong mục "chờ" sẽ biến mất.
        # -------------------------------------------------------------

        st.session_state[
            "warehouse_uploader_version"
        ] += 1


        # -------------------------------------------------------------
        # XÓA KẾT QUẢ HIỂN THỊ TẠM
        # -------------------------------------------------------------

        for key in [

            "warehouse_results",
            "warehouse_processing",
            "warehouse_current_result"

        ]:

            if key in st.session_state:

                del st.session_state[key]


        # -------------------------------------------------------------
        # RERUN
        # -------------------------------------------------------------

        st.rerun()
