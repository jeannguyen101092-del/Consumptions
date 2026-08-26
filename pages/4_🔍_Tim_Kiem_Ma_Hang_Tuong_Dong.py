# =====================================================================
# 🔍📦 AI GARMENT SEARCH & WAREHOUSE
# VERSION V3.2 - FULL MASTER
#
# TAB 1:
#   AI nhận diện category
#   CLIP embedding
#   Tự tìm mã tương đồng
#   KHÔNG cho người dùng chọn category
#
# TAB 2:
#   Upload hàng loạt
#   AI tự nhận category
#   CLIP embedding
#   Lưu Supabase
#   Lưu Storage
#
# EXTRA:
#   Jumpsuit != Cargo
#   Overall != Cargo
#   Cargo phải có cargo pockets
#   Denim -> Jeans
#   Jogger cuffs -> Jogger
#   Xóa toàn bộ kho
#
# SECURITY:
#   Không hard-code SUPABASE URL / KEY / HF TOKEN
#   Đọc từ Streamlit Secrets / Tomy
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

import base64
import io
import json
import re
import hashlib
import requests

from PIL import Image

from supabase import create_client, Client

try:
    from huggingface_hub import InferenceClient
except Exception:
    InferenceClient = None


# =====================================================================
# 3. SECRET READER
# =====================================================================

def read_secret(*keys):

    # ---------------------------------------------------------
    # DIRECT
    # ---------------------------------------------------------

    for key in keys:

        try:

            value = st.secrets.get(key)

            if value is not None:

                value = str(value).strip()

                if value:

                    return value

        except Exception:

            pass


    # ---------------------------------------------------------
    # GROUPED SECRETS
    # ---------------------------------------------------------

    for group_name in [
        "supabase",
        "SUPABASE",
        "huggingface",
        "HUGGINGFACE"
    ]:

        try:

            group = st.secrets.get(group_name)

            if group:

                for key in keys:

                    try:

                        value = group.get(key)

                        if value:

                            value = str(value).strip()

                            if value:

                                return value

                    except Exception:

                        pass

        except Exception:

            pass


    return None


# =====================================================================
# 4. SECURITY CONFIG
# =====================================================================

SUPABASE_URL = read_secret(
    "SUPABASE_URL",
    "SUPABASE_PROJECT_URL"
)

SUPABASE_KEY = read_secret(
    "SUPABASE_KEY",
    "SUPABASE_ANON_KEY",
    "SUPABASE_PUBLISHABLE_KEY"
)

HF_TOKEN = read_secret(
    "HF_TOKEN",
    "HUGGINGFACE_TOKEN",
    "HUGGING_FACE_TOKEN"
)


# =====================================================================
# 5. VALIDATE SECRETS
# =====================================================================

missing_secrets = []

if not SUPABASE_URL:
    missing_secrets.append("SUPABASE_URL")

if not SUPABASE_KEY:
    missing_secrets.append("SUPABASE_KEY")

if not HF_TOKEN:
    missing_secrets.append("HF_TOKEN")


if missing_secrets:

    st.error(
        "❌ Không đọc được thông tin bảo mật từ Streamlit Secrets."
    )

    st.write(
        "Hãy kiểm tra các key sau trong Secrets:"
    )

    for item in missing_secrets:

        st.write(
            f"- `{item}`"
        )

    st.stop()


# =====================================================================
# 6. SUPABASE CLIENT
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
# 7. HUGGING FACE CLIENT
# =====================================================================

if InferenceClient is None:

    st.error(
        "❌ Chưa cài huggingface_hub."
    )

    st.code(
        "huggingface_hub>=0.33.0"
    )

    st.stop()


# =====================================================================
# 8. VISION MODEL
# =====================================================================
#
# Hugging Face hiện có tài liệu Novita cho VLM.
# Dùng provider-qualified model để tránh lỗi:
#
# model_not_supported
#
# =====================================================================

VISION_MODEL = (
    "moonshotai/Kimi-K2.7-Code:novita"
)


try:

    hf_client = InferenceClient(
        api_key=HF_TOKEN
    )

except Exception as e:

    st.error(
        "❌ Không khởi tạo được Hugging Face Client."
    )

    st.exception(e)

    st.stop()


# =====================================================================
# 9. CLIP MODEL
# =====================================================================
#
# CLIP được gọi qua Hugging Face.
#
# openai/clip-vit-base-patch32
#
# Output chuẩn CLIP image embedding = 512 dimensions.
#
# =====================================================================

CLIP_MODEL = (
    "openai/clip-vit-base-patch32"
)


# =====================================================================
# 10. SUPABASE CONFIG
# =====================================================================

PRODUCT_TABLE = "products"

PRODUCT_BUCKET = "product-images"

MATCH_RPC = "match_products_v2"


# =====================================================================
# 11. CATEGORY MASTER
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

def image_to_data_url(image_bytes):

    try:

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

        jpeg_bytes = output.getvalue()

    except Exception:

        jpeg_bytes = image_bytes


    encoded = base64.b64encode(
        jpeg_bytes
    ).decode("utf-8")


    return (
        "data:image/jpeg;base64,"
        +
        encoded
    )


# =====================================================================
# 14. EXTRACT JSON
# =====================================================================

def extract_json_from_ai(text):

    if not text:

        raise Exception(
            "AI không trả về kết quả."
        )


    text = str(
        text
    ).strip()


    # ---------------------------------------------------------
    # Remove markdown
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


    # ---------------------------------------------------------
    # Find JSON
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
            text[:2000]
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
            "JSON parse lỗi: "
            +
            str(e)
            +
            "\n\n"
            +
            json_text[:2000]
        )


# =====================================================================
# 15. GARMENT PROMPT
# =====================================================================

GARMENT_PROMPT = """

You are a senior apparel technical designer.

You specialize in recognizing garment construction from
fashion sketches, product images and technical apparel images.

This is for a COMMERCIAL GARMENT SIMILARITY SEARCH DATABASE.

Accuracy of garment construction is more important than generic
visual similarity.

============================================================
STEP 1 - DETERMINE GARMENT CONSTRUCTION
============================================================

First decide whether the garment is:

ONE PIECE

or

SEPARATE GARMENT

============================================================
JUMPSUIT / ONE PIECE
============================================================

If upper body and lower body are physically connected:

category = "Áo liền quần"

This rule has priority.

NEVER classify a jumpsuit as cargo pants.

============================================================
BIB OVERALL
============================================================

If the garment has:

- bib front
- shoulder straps
- overall construction

category = "Quần yếm"

NEVER classify it as cargo pants.

============================================================
CARGO PANTS
============================================================

Cargo Pants require:

1. SEPARATE pants garment
2. Clearly visible external cargo/patch pockets
   on side legs

If cargo pockets are not clearly visible:

DO NOT classify as Cargo Pants.

If it is one-piece:

DO NOT classify as Cargo Pants.

============================================================
JEANS
============================================================

Separate denim pants.

============================================================
JOGGER
============================================================

Separate pants with jogger construction,
especially elastic/rib ankle cuffs.

============================================================
JACKET
============================================================

Separate upper-body outerwear.

============================================================
DRESS
============================================================

One-piece dress silhouette.

Do not confuse dress with pants-based jumpsuit.

============================================================
AVAILABLE CATEGORY
============================================================

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

============================================================
RETURN
============================================================

Return ONLY JSON.

Required fields:

category
confidence
one_piece
bib
shoulder_straps
cargo_pockets
denim
jogger_cuffs
sleeve
collar
hood
silhouette
length
reason

Example:

{
  "category": "Quần túi hộp",
  "confidence": 95,
  "one_piece": false,
  "bib": false,
  "shoulder_straps": false,
  "cargo_pockets": true,
  "denim": false,
  "jogger_cuffs": false,
  "sleeve": "none",
  "collar": "none",
  "hood": false,
  "silhouette": "straight",
  "length": "full",
  "reason": "Separate pants with visible cargo pockets on both side legs."
}

"""


# =====================================================================
# 16. AI GARMENT VISION
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
            +
            str(e)
        )


    # =================================================================
    # READ RESPONSE
    # =================================================================

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
            +
            str(e)
        )


    # =================================================================
    # JSON
    # =================================================================

    result = extract_json_from_ai(
        content
    )


    # =================================================================
    # NORMALIZE
    # =================================================================

    return normalize_garment_result(
        result
    )


# =====================================================================
# 17. CATEGORY NORMALIZATION
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


    if category not in CATEGORY_LIST:

        category = "Quần dài"


    result[
        "category"
    ] = category


    # =================================================================
    # BOOLEAN
    # =================================================================

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
                    "1",
                    "y"
                ]
            )


        result[
            field
        ] = bool(
            value
        )


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


    # =================================================================
    # 🔒 MASTER RULE 1
    # ONE PIECE
    # =================================================================

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


    # =================================================================
    # 🔒 MASTER RULE 2
    # BIB
    # =================================================================

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


    # =================================================================
    # 🔒 MASTER RULE 3
    # CARGO REQUIRES POCKET
    # =================================================================

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


    # =================================================================
    # 🔒 MASTER RULE 4
    # DENIM
    # =================================================================

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


    # =================================================================
    # 🔒 MASTER RULE 5
    # JOGGER
    # =================================================================

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
# 18. CLIP EMBEDDING VIA HUGGING FACE
# =====================================================================

def get_clip_embedding(
    image_bytes
):

    image_url = (
        image_to_data_url(
            image_bytes
        )
    )


    try:

        # -------------------------------------------------------------
        # Hugging Face feature extraction
        # -------------------------------------------------------------

        result = hf_client.feature_extraction(
            image_url,
            model=CLIP_MODEL
        )


    except Exception as first_error:

        # -------------------------------------------------------------
        # Some HF versions expect bytes instead of data URL
        # -------------------------------------------------------------

        try:

            result = hf_client.feature_extraction(
                image_bytes,
                model=CLIP_MODEL
            )

        except Exception as second_error:

            raise Exception(
                "CLIP embedding lỗi:\n"
                +
                str(second_error)
            )


    # =================================================================
    # CONVERT TO FLAT LIST
    # =================================================================

    def flatten(
        value
    ):

        if isinstance(
            value,
            (list, tuple)
        ):

            output = []

            for x in value:

                output.extend(
                    flatten(x)
                )

            return output


        try:

            return [
                float(value)
            ]

        except Exception:

            return []


    vector = flatten(
        result
    )


    # =================================================================
    # CLIP VECTOR CLEAN
    # =================================================================

    if not vector:

        raise Exception(
            "CLIP không trả về vector."
        )


    # -------------------------------------------------------------
    # HF có thể trả token embeddings
    # -------------------------------------------------------------
    #
    # CLIP image embedding chuẩn phải là 512D.
    #
    # Nếu trả tensor 257 x 512, flatten sẽ thành 131584.
    #
    # Không được lưu trực tiếp.
    #
    # -------------------------------------------------------------

    if len(vector) == 512:

        final_vector = vector


    elif len(vector) % 512 == 0:

        rows = (
            len(vector) // 512
        )

        # ---------------------------------------------------------
        # Mean pooling
        # ---------------------------------------------------------

        final_vector = []

        for col in range(512):

            total = 0.0

            for row in range(rows):

                total += vector[
                    row * 512 + col
                ]

            final_vector.append(
                total / rows
            )


    else:

        raise Exception(

            "CLIP vector không đúng kích thước.\n"
            f"Received: {len(vector)}\n"
            "Expected: 512"

        )


    # =================================================================
    # L2 NORMALIZATION
    # =================================================================

    norm = sum(
        x * x
        for x in final_vector
    ) ** 0.5


    if norm > 0:

        final_vector = [

            x / norm
            for x in final_vector

        ]


    return final_vector


# =====================================================================
# 19. SAFE FILE NAME
# =====================================================================

def clean_product_code(
    filename
):

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
# 20. UPLOAD IMAGE STORAGE
# =====================================================================

def upload_image_to_storage(
    file_bytes,
    filename
):

    try:

        bucket = (
            supabase
            .storage
            .from_(
                PRODUCT_BUCKET
            )
        )


        bucket.upload(

            path=filename,

            file=file_bytes,

            file_options={

                "content-type":
                    "image/jpeg",

                "upsert":
                    "true"

            }

        )


        public_url = (
            bucket
            .get_public_url(
                filename
            )
        )


        return public_url


    except Exception as e:

        raise Exception(
            "Storage upload lỗi: "
            +
            str(e)
        )


# =====================================================================
# 21. SAVE PRODUCT
# =====================================================================

def save_product_to_supabase(
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
                PRODUCT_TABLE
            )
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
            +
            str(e)
        )


# =====================================================================
# 22. SEARCH SIMILAR PRODUCTS
# =====================================================================

def search_similar_products(
    embedding,
    match_count=8,
    match_threshold=0.20
):

    try:

        response = (

            supabase
            .rpc(

                MATCH_RPC,

                {

                    "query_embedding":
                        embedding,

                    "match_threshold":
                        match_threshold,

                    "match_count":
                        match_count

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
            "RPC search lỗi: "
            +
            str(e)
        )


# =====================================================================
# 23. CATEGORY SEARCH FILTER
# =====================================================================
#
# Vì RPC cũ có thể không nhận filter_category,
# ta lọc category SAU KHI lấy CLIP results.
#
# Điều này tránh lỗi RPC.
#
# =====================================================================

def filter_results_by_ai_category(
    results,
    ai_category
):

    if not results:

        return []


    # ---------------------------------------------------------
    # Exact category first
    # ---------------------------------------------------------

    exact = [

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


    if exact:

        return exact


    # ---------------------------------------------------------
    # Nếu không có exact category:
    #
    # Không ép category khác vào.
    # Đây là điểm quan trọng để:
    #
    # Áo không ra quần
    # Jumpsuit không ra cargo
    # Overall không ra cargo
    #
    # ---------------------------------------------------------

    return []


# =====================================================================
# 24. DISPLAY AI RESULT
# =====================================================================

def display_ai_result(
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
            "🏷️ Category",
            result[
                "category"
            ]
        )


    with c2:

        st.metric(
            "🎯 Confidence",
            f"{result['confidence']:.1f}%"
        )


    with c3:

        st.metric(
            "👕 One Piece",
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
# 25. DISPLAY SEARCH RESULTS
# =====================================================================

def display_search_results(
    results
):

    if not results:

        st.warning(
            "Không tìm thấy mã tương đồng phù hợp."
        )

        return


    st.success(
        f"🔎 Tìm thấy {len(results)} mã tương đồng."
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

        with cols[
            index % len(cols)
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


            category = item.get(
                "category",
                ""
            )


            st.caption(
                f"Category: {category}"
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

                    st.write(
                        image_url
                    )


# =====================================================================
# 26. DELETE ALL STORAGE FILES
# =====================================================================

def delete_all_storage_files():

    bucket = (
        supabase
        .storage
        .from_(
            PRODUCT_BUCKET
        )
    )


    deleted = 0


    try:

        items = bucket.list()


        if not items:

            return 0


        paths = []


        for item in items:

            name = item.get(
                "name"
            )


            if name:

                paths.append(
                    name
                )


        # -------------------------------------------------------------
        # Delete batches
        # -------------------------------------------------------------

        batch_size = 100


        for start in range(
            0,
            len(paths),
            batch_size
        ):

            batch = paths[
                start:
                start + batch_size
            ]


            bucket.remove(
                batch
            )


            deleted += len(
                batch
            )


        return deleted


    except Exception as e:

        raise Exception(
            "Storage delete lỗi: "
            +
            str(e)
        )


# =====================================================================
# 27. DELETE ALL DATABASE
# =====================================================================

def delete_all_products():

    try:

        # -------------------------------------------------------------
        # Try deleting using product_code not null
        # -------------------------------------------------------------

        response = (

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


        return response


    except Exception as e:

        raise Exception(
            "Database delete lỗi: "
            +
            str(e)
        )


# =====================================================================
# 28. HEADER
# =====================================================================

st.title(
    "🔍 AI TÌM KIẾM MÃ HÀNG TƯƠNG ĐỒNG"
)

st.caption(
    "AI Vision + CLIP + Supabase"
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
# #####################################################################
#
# TAB 1
#
# #####################################################################
# #####################################################################

with tab1:

    st.header(
        "🔍 Tìm mã hàng qua ảnh"
    )


    st.info(

        "💡 Không cần chọn dòng hàng. "
        "AI sẽ tự nhận diện category trước "
        "rồi tìm mã tương đồng."

    )


    uploaded_sketch = st.file_uploader(

        "📂 Tải ảnh Sketch / ảnh mẫu",

        type=[
            "png",
            "jpg",
            "jpeg",
            "JPG",
            "JPEG"
        ],

        key="search_sketch"

    )


    if uploaded_sketch:

        col1, col2 = st.columns(
            2
        )


        with col1:

            st.image(

                uploaded_sketch,

                caption=uploaded_sketch.name,

                width=350

            )


        with col2:

            st.write(
                "### 📋 Thông tin file"
            )

            st.write(
                f"File: `{uploaded_sketch.name}`"
            )

            st.write(
                f"Size: `{uploaded_sketch.size:,} bytes`"
            )


        if st.button(

            "🚀 AI NHẬN DIỆN & TÌM MÃ",

            type="primary",

            key="search_ai_button"

        ):

            try:

                image_bytes = (
                    uploaded_sketch
                    .getvalue()
                )


                # =====================================================
                # STEP 1
                # =====================================================

                with st.spinner(
                    "🤖 AI Vision đang nhận diện garment..."
                ):

                    ai_result = (
                        analyze_garment_with_vision(
                            image_bytes
                        )
                    )


                display_ai_result(
                    ai_result
                )


                # =====================================================
                # STEP 2
                # =====================================================

                with st.spinner(
                    "🧠 CLIP đang tạo image embedding..."
                ):

                    embedding = (
                        get_clip_embedding(
                            image_bytes
                        )
                    )


                st.caption(
                    f"CLIP vector: {len(embedding)} dimensions"
                )


                # =====================================================
                # STEP 3
                # =====================================================

                with st.spinner(
                    "🔎 Đang tìm mã tương đồng..."
                ):

                    raw_results = (
                        search_similar_products(
                            embedding,
                            match_count=30,
                            match_threshold=0.15
                        )
                    )


                # =====================================================
                # STEP 4
                # CATEGORY LOCK
                # =====================================================

                filtered_results = (
                    filter_results_by_ai_category(

                        raw_results,

                        ai_result[
                            "category"
                        ]

                    )
                )


                # =====================================================
                # SHOW SEARCH INFO
                # =====================================================

                st.markdown(
                    "### 🔒 CATEGORY LOCK"
                )


                st.write(
                    "AI Category:"
                )

                st.success(
                    ai_result[
                        "category"
                    ]
                )


                st.write(
                    f"CLIP tìm được ban đầu: "
                    f"{len(raw_results)} mã"
                )


                st.write(
                    f"Sau Category Lock: "
                    f"{len(filtered_results)} mã"
                )


                # =====================================================
                # RESULTS
                # =====================================================

                display_search_results(
                    filtered_results[:8]
                )


                # =====================================================
                # IF NO EXACT CATEGORY
                # =====================================================

                if (
                    not filtered_results
                    and
                    raw_results
                ):

                    st.warning(

                        "⚠️ Có mã tương đồng về hình ảnh "
                        "nhưng khác category AI. "
                        "Hệ thống đã loại bỏ để tránh "
                        "Áo/Jumpsuit/Overall bị lẫn với quần."

                    )


            except Exception as e:

                st.error(
                    "❌ Tìm kiếm thất bại."
                )

                st.exception(e)


# #####################################################################
# #####################################################################
#
# TAB 2
#
# #####################################################################
# #####################################################################

with tab2:

    st.header(
        "📦 Lưu kho hàng loạt"
    )


    st.info(

        "💡 Chỉ cần upload ảnh. "
        "AI tự nhận diện category và tự lưu vào kho."

    )


    uploaded_files = st.file_uploader(

        "📂 Chọn nhiều ảnh sản phẩm",

        type=[
            "png",
            "jpg",
            "jpeg",
            "JPG",
            "JPEG"
        ],

        accept_multiple_files=True,

        key="warehouse_upload"

    )


    if uploaded_files:

        st.write(
            f"📂 Đã chọn **{len(uploaded_files)}** ảnh."
        )


        if st.button(

            "📤 AI NHẬN DIỆN & LƯU TOÀN BỘ",

            type="primary",

            key="warehouse_save_button"

        ):

            progress = st.progress(
                0
            )

            status = st.empty()


            success_count = 0

            failed_count = 0


            all_results = []


            total_files = len(
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
                    f"({index + 1}/{total_files}) "
                    f"Đang xử lý: "
                    f"**{product_code}**"

                )


                try:

                    image_bytes = (
                        file.getvalue()
                    )


                    # =================================================
                    # IMAGE VALIDATION
                    # =================================================

                    try:

                        image = Image.open(
                            io.BytesIO(
                                image_bytes
                            )
                        )

                        image.verify()

                    except Exception:

                        raise Exception(
                            "File ảnh không hợp lệ."
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

                    storage_filename = (
                        product_code
                        +
                        ".jpg"
                    )


                    img_url = (
                        upload_image_to_storage(

                            image_bytes,

                            storage_filename

                        )
                    )


                    if not img_url:

                        raise Exception(
                            "Không lấy được image URL."
                        )


                    # =================================================
                    # DATABASE
                    # =================================================

                    save_product_to_supabase(

                        product_code=
                            product_code,

                        image_url=
                            img_url,

                        category=
                            category,

                        embedding=
                            embedding

                    )


                    success_count += 1


                    all_results.append({

                        "product_code":
                            product_code,

                        "category":
                            category,

                        "confidence":
                            ai_result[
                                "confidence"
                            ],

                        "status":
                            "SUCCESS"

                    })


                except Exception as e:

                    failed_count += 1


                    all_results.append({

                        "product_code":
                            product_code,

                        "category":
                            "ERROR",

                        "confidence":
                            0,

                        "status":
                            str(e)

                    })


                    st.error(

                        f"❌ {file.name}: "
                        f"{str(e)}"

                    )


                progress.progress(

                    (index + 1)
                    /
                    total_files

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
                    "📦 Tổng file",
                    total_files
                )


            with c2:

                st.metric(
                    "✅ Thành công",
                    success_count
                )


            with c3:

                st.metric(
                    "❌ Lỗi",
                    failed_count
                )


            # =========================================================
            # RESULT TABLE
            # =========================================================

            if all_results:

                st.markdown(
                    "### 📊 KẾT QUẢ AI"
                )


                st.dataframe(

                    all_results,

                    use_container_width=True

                )


            if success_count > 0:

                st.success(

                    f"🎉 Đã lưu thành công "
                    f"{success_count}/{total_files} mã."

                )


# #####################################################################
# #####################################################################
#
# DELETE WAREHOUSE
#
# #####################################################################
# #####################################################################

with tab2:

    st.divider()


    st.subheader(
        "🗑️ Quản lý kho"
    )


    st.warning(

        "⚠️ Chức năng bên dưới sẽ xóa "
        "toàn bộ records trong `products` "
        "và ảnh trong bucket `product-images`."

    )


    if (
        "confirm_delete_all"
        not in
        st.session_state
    ):

        st.session_state[
            "confirm_delete_all"
        ] = False


    if st.button(

        "🗑️ XÓA TẤT CẢ KHO",

        key="show_delete_all"

    ):

        st.session_state[
            "confirm_delete_all"
        ] = True


    if st.session_state[
        "confirm_delete_all"
    ]:

        st.error(

            "🚨 ĐANG CHUẨN BỊ XÓA TOÀN BỘ KHO!"

        )


        st.write(
            "Nhập `DELETE` để xác nhận."
        )


        delete_confirm = st.text_input(

            "Xác nhận:",

            key="delete_confirm_text"

        )


        col_a, col_b = st.columns(
            2
        )


        with col_a:

            if st.button(

                "🔥 XÁC NHẬN XÓA",

                type="primary",

                key="confirm_delete_button"

            ):

                if (
                    delete_confirm
                    .strip()
                    .upper()
                    !=
                    "DELETE"
                ):

                    st.error(
                        "❌ Phải nhập chính xác DELETE."
                    )

                else:

                    try:

                        # =============================================
                        # DELETE DATABASE
                        # =============================================

                        with st.spinner(
                            "🗑️ Đang xóa database..."
                        ):

                            delete_all_products()


                        # =============================================
                        # DELETE STORAGE
                        # =============================================

                        with st.spinner(
                            "☁️ Đang xóa Storage..."
                        ):

                            deleted_files = (
                                delete_all_storage_files()
                            )


                        st.session_state[
                            "confirm_delete_all"
                        ] = False


                        st.success(

                            "🎉 ĐÃ XÓA TOÀN BỘ KHO!\n\n"
                            f"Đã xử lý {deleted_files} ảnh."

                        )


                        st.rerun()


                    except Exception as e:

                        st.error(
                            "❌ Xóa kho thất bại."
                        )

                        st.exception(e)


        with col_b:

            if st.button(

                "↩️ HỦY",

                key="cancel_delete_button"

            ):

                st.session_state[
                    "confirm_delete_all"
                ] = False


                st.rerun()


# =====================================================================
# SIDEBAR STATUS
# =====================================================================

with st.sidebar:

    st.divider()

    st.subheader(
        "⚙️ SYSTEM"
    )

    st.success(
        "Supabase: Connected"
    )

    st.success(
        "Hugging Face: Connected"
    )

    st.caption(
        f"Vision: {VISION_MODEL}"
    )

    st.caption(
        f"CLIP: {CLIP_MODEL}"
    )

    st.caption(
        "Embedding: 512D"
    )

    st.caption(
        f"RPC: {MATCH_RPC}"
    )

# =====================================================================
# END
# =====================================================================
