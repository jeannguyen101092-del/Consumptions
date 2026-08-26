# =====================================================================
# 🤖 AI GARMENT VISION ENGINE
# VERSION V3.1.1
# MODEL: GLM-4.5V
# PROVIDER: NOVITA
#
# FIX:
# - NameError: st
# - HF_TOKEN đọc từ Streamlit Secrets
# - Không hard-code token
# - Không gọi hf-inference
# - Garment rule engine
# - Jumpsuit != Cargo
# - Overall != Cargo
# =====================================================================


# =====================================================================
# 1. STREAMLIT - PHẢI ĐẶT TRƯỚC TẤT CẢ
# =====================================================================

import streamlit as st

st.set_page_config(
    page_title="AI Garment Vision",
    page_icon="🤖",
    layout="wide"
)


# =====================================================================
# 2. IMPORT
# =====================================================================

import base64
import json
import re


# =====================================================================
# 3. HUGGING FACE
# =====================================================================

try:

    from huggingface_hub import InferenceClient

except Exception as e:

    st.error(
        "❌ Chưa cài huggingface_hub."
    )

    st.code(
        "huggingface_hub>=0.33.0"
    )

    st.exception(e)

    st.stop()


# =====================================================================
# 4. ĐỌC HF TOKEN TỪ STREAMLIT SECRETS / TOMY
# =====================================================================

def get_hf_token():

    # ---------------------------------------------------------
    # DIRECT SECRETS
    # ---------------------------------------------------------

    possible_keys = [

        "HF_TOKEN",
        "HUGGINGFACE_TOKEN",
        "HUGGING_FACE_TOKEN"

    ]


    for key in possible_keys:

        try:

            value = st.secrets.get(
                key
            )

            if value:

                value = str(
                    value
                ).strip()

                if value:

                    return value

        except Exception:

            pass


    # ---------------------------------------------------------
    # GROUP SECRETS
    # ---------------------------------------------------------

    for group_name in [

        "huggingface",
        "HUGGINGFACE"

    ]:

        try:

            group = st.secrets.get(
                group_name
            )

            if group:

                for key in possible_keys:

                    try:

                        value = group.get(
                            key
                        )

                        if value:

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
# 5. HF TOKEN
# =====================================================================

HF_TOKEN = get_hf_token()


if not HF_TOKEN:

    st.error(
        "❌ Không đọc được HF_TOKEN từ Streamlit Secrets."
    )

    st.info(
        "Hãy kiểm tra Secrets/Tomy có:"
    )

    st.code(
        'HF_TOKEN = "hf_xxxxxxxxxxxxxxxxx"'
    )

    st.stop()


# =====================================================================
# 6. MODEL + PROVIDER
# =====================================================================

VISION_MODEL = (
    "zai-org/GLM-4.5V"
)

VISION_PROVIDER = (
    "novita"
)


# =====================================================================
# 7. HUGGING FACE CLIENT
# =====================================================================

try:

    hf_client = InferenceClient(

        api_key=HF_TOKEN,

        provider=VISION_PROVIDER

    )

except Exception as e:

    st.error(
        "❌ Không khởi tạo được Hugging Face Vision."
    )

    st.exception(e)

    st.stop()


# =====================================================================
# 8. AI STATUS
# =====================================================================

with st.sidebar:

    st.success(
        "🤖 AI Vision: ONLINE"
    )

    st.caption(
        f"Model: {VISION_MODEL}"
    )

    st.caption(
        f"Provider: {VISION_PROVIDER}"
    )


# =====================================================================
# 9. IMAGE → DATA URL
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
# 10. CLEAN AI JSON
# =====================================================================

def extract_json_from_ai(
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
    # REMOVE MARKDOWN CODE FENCE
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
    # FIND JSON OBJECT
    # ---------------------------------------------------------

    match = re.search(

        r"\{.*\}",

        text,

        flags=re.S

    )


    if not match:

        raise Exception(

            "AI không trả về JSON hợp lệ:\n"
            +
            text[:2000]

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
            "\n\n"
            +
            json_text[:2000]

        )


# =====================================================================
# 11. GARMENT VISION PROMPT
# =====================================================================

GARMENT_VISION_PROMPT = """

You are a senior apparel technical designer and garment
recognition specialist.

Analyze the garment image extremely carefully.

This image will be used to search a commercial garment
database, therefore construction accuracy is more important
than generic visual similarity.

============================================================
CRITICAL GARMENT CLASSIFICATION
============================================================

FIRST determine:

A. ONE PIECE
B. SEPARATE GARMENT

------------------------------------------------------------
JUMPSUIT
------------------------------------------------------------

If the upper body and lower body are physically connected
into ONE garment:

category = "Áo liền quần"

NEVER classify a jumpsuit as Cargo Pants.

------------------------------------------------------------
BIB OVERALL
------------------------------------------------------------

If there is:

- bib front
- shoulder straps
- overall construction

category = "Quần yếm"

NEVER classify a bib overall as Cargo Pants.

------------------------------------------------------------
CARGO PANTS
------------------------------------------------------------

Cargo Pants must satisfy BOTH:

1. It is a SEPARATE pants garment.
2. It has obvious external cargo/patch pockets on side legs.

If the garment is one-piece, it is NOT Cargo Pants.

If there are no clear cargo pockets, do NOT classify it as
Cargo Pants.

------------------------------------------------------------
JEANS
------------------------------------------------------------

Separate denim pants with denim construction.

------------------------------------------------------------
JOGGER
------------------------------------------------------------

Separate pants with jogger construction, especially
elastic/rib ankle cuffs.

------------------------------------------------------------
JACKET
------------------------------------------------------------

Separate upper-body outerwear garment.

------------------------------------------------------------
DRESS
------------------------------------------------------------

One-piece dress silhouette.

Do NOT confuse a dress with a pants-based jumpsuit.

============================================================
AVAILABLE CATEGORIES
============================================================

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

============================================================
ANALYZE
============================================================

Return:

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

============================================================
OUTPUT
============================================================

Return ONLY valid JSON.

Example:

{
  "category": "Áo liền quần",
  "confidence": 95,
  "one_piece": true,
  "bib": false,
  "shoulder_straps": false,
  "cargo_pockets": false,
  "denim": false,
  "jogger_cuffs": false,
  "sleeve": "long",
  "collar": "shirt collar",
  "hood": false,
  "silhouette": "straight",
  "length": "full",
  "reason": "Upper and lower body are physically connected."
}

"""


# =====================================================================
# 12. CALL GLM-4.5V
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
                                                image_url

                                        }

                                },

                                {

                                    "type":
                                        "text",

                                    "text":
                                        GARMENT_VISION_PROMPT

                                }

                            ]

                    }

                ],

                max_tokens=1000,

                temperature=0.0

            )

        )


    except Exception as e:

        error_text = str(
            e
        )


        # =====================================================
        # PROVIDER NOT SUPPORTED
        # =====================================================

        if (
            "model_not_supported"
            in error_text.lower()
        ):

            raise Exception(

                "❌ MODEL KHÔNG ĐƯỢC PROVIDER HỖ TRỢ.\n\n"

                f"Model: {VISION_MODEL}\n"

                f"Provider: {VISION_PROVIDER}\n\n"

                "HF_TOKEN hiện tại không có quyền "
                "sử dụng model/provider này.\n\n"

                "Đây là lỗi Hugging Face provider, "
                "không phải lỗi ảnh."

            )


        # =====================================================
        # BAD REQUEST
        # =====================================================

        if (
            "bad request"
            in error_text.lower()
        ):

            raise Exception(

                "❌ Hugging Face từ chối request.\n\n"
                +
                error_text

            )


        raise Exception(

            "❌ Hugging Face GLM-4.5V lỗi:\n"
            +
            error_text

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

            "❌ Không đọc được response "
            "từ GLM-4.5V:\n"
            +
            str(e)

        )


    # =================================================================
    # JSON
    # =================================================================

    result = (
        extract_json_from_ai(
            content
        )
    )


    # =================================================================
    # NORMALIZE
    # =================================================================

    result = (
        normalize_garment_result(
            result
        )
    )


    return result


# =====================================================================
# 13. GARMENT NORMALIZATION
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


    # =================================================================
    # CATEGORY ALIAS
    # =================================================================

    aliases = {

        "JUMPSUIT":
            "Áo liền quần",

        "ONE PIECE":
            "Áo liền quần",

        "ONE-PIECE":
            "Áo liền quần",

        "ROMPER":
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

        "JEANS":
            "Quần jean",

        "DENIM JEANS":
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


    # =================================================================
    # VALID CATEGORIES
    # =================================================================

    valid_categories = [

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


    if category not in valid_categories:

        category = "Quần dài"


    result[
        "category"
    ] = category


    # =================================================================
    # BOOLEAN NORMALIZATION
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
    # 🔒 HARD RULE 1
    # ONE PIECE
    # =================================================================

    if result[
        "one_piece"
    ]:

        # -------------------------------------------------------------
        # BIB + STRAPS
        # -------------------------------------------------------------

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
    # 🔒 HARD RULE 2
    # BIB OVERALL
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
    # 🔒 HARD RULE 3
    # CARGO MUST HAVE CARGO POCKET
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
    # 🔒 HARD RULE 4
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
    # 🔒 HARD RULE 5
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
# 14. DISPLAY RESULT
# =====================================================================

def display_garment_result(
    result
):

    st.subheader(
        "🤖 AI GARMENT ANALYSIS"
    )


    col1, col2, col3 = st.columns(
        3
    )


    with col1:

        st.metric(

            "🏷️ Category",

            result[
                "category"
            ]

        )


    with col2:

        st.metric(

            "🎯 Confidence",

            f"{result['confidence']:.1f}%"

        )


    with col3:

        st.metric(

            "👕 One Piece",

            "YES"
            if result[
                "one_piece"
            ]
            else
            "NO"

        )


    # =================================================================
    # DETAILS
    # =================================================================

    with st.expander(
        "🔎 Chi tiết AI nhận diện"
    ):

        c1, c2 = st.columns(
            2
        )


        with c1:

            st.write(
                "Bib:",
                result[
                    "bib"
                ]
            )

            st.write(
                "Shoulder Straps:",
                result[
                    "shoulder_straps"
                ]
            )

            st.write(
                "Cargo Pockets:",
                result[
                    "cargo_pockets"
                ]
            )

            st.write(
                "Denim:",
                result[
                    "denim"
                ]
            )


        with c2:

            st.write(
                "Jogger Cuffs:",
                result[
                    "jogger_cuffs"
                ]
            )

            st.write(
                "Sleeve:",
                result.get(
                    "sleeve",
                    ""
                )
            )

            st.write(
                "Collar:",
                result.get(
                    "collar",
                    ""
                )
            )

            st.write(
                "Silhouette:",
                result.get(
                    "silhouette",
                    ""
                )
            )


        st.write(
            "📝 AI Reason:"
        )

        st.write(
            result.get(
                "reason",
                ""
            )
        )


# =====================================================================
# 15. TEST UI
# =====================================================================

st.title(
    "🤖 AI Garment Vision Engine V3.1.1"
)


st.info(

    "AI tự nhận diện garment. "
    "Không cần chọn category."

)


uploaded_file = st.file_uploader(

    "📂 Tải ảnh Sketch / ảnh sản phẩm",

    type=[
        "jpg",
        "jpeg",
        "png"
    ]

)


if uploaded_file:

    st.image(

        uploaded_file,

        caption=uploaded_file.name,

        width=350

    )


    if st.button(

        "🤖 NHẬN DIỆN GARMENT",

        type="primary"

    ):

        try:

            image_bytes = (
                uploaded_file
                .getvalue()
            )


            with st.spinner(
                "🧠 GLM-4.5V đang phân tích..."
            ):

                result = (
                    analyze_garment_with_vision(
                        image_bytes
                    )
                )


            display_garment_result(
                result
            )


            st.success(
                "✅ Nhận diện hoàn tất."
            )


        except Exception as e:

            st.error(
                "❌ AI nhận diện thất bại."
            )

            st.exception(e)


# =====================================================================
# END
# =====================================================================
