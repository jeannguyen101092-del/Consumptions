# =====================================================================
# 🤖 HUGGING FACE VISION ENGINE
# VERSION V3.1
# MODEL: GLM-4.5V
# PROVIDER: NOVITA
# =====================================================================

from huggingface_hub import InferenceClient
import base64
import json
import re


# =====================================================================
# 1. MODEL + PROVIDER
# =====================================================================

VISION_MODEL = "zai-org/GLM-4.5V"

VISION_PROVIDER = "novita"


# =====================================================================
# 2. HF CLIENT
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
# 3. IMAGE → DATA URL
# =====================================================================

def image_to_data_url(image_bytes):

    encoded = base64.b64encode(
        image_bytes
    ).decode("utf-8")

    return (
        "data:image/jpeg;base64,"
        + encoded
    )


# =====================================================================
# 4. CLEAN JSON
# =====================================================================

def extract_json_from_ai(text):

    if not text:

        raise Exception(
            "AI không trả về dữ liệu."
        )

    text = str(
        text
    ).strip()

    # ---------------------------------------------------------
    # REMOVE MARKDOWN
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
            "AI không trả về JSON hợp lệ:\n"
            + text[:1500]
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
            + str(e)
            + "\n"
            + json_text[:1500]
        )


# =====================================================================
# 5. GARMENT VISION
# =====================================================================

def analyze_garment_with_vision(
    image_bytes
):

    image_url = (
        image_to_data_url(
            image_bytes
        )
    )


    prompt = """
You are an expert apparel product recognition AI.

Analyze this garment image/sketch for commercial
garment similarity search.

This is NOT a generic image classification task.

You must identify the actual garment construction.

CRITICAL:

1. Determine if it is ONE PIECE or a SEPARATE GARMENT.

2. JUMPSUIT:
   Upper body and lower body are physically connected.
   Classify as "Áo liền quần".

3. BIB OVERALL:
   Has bib front and shoulder straps.
   Classify as "Quần yếm".

4. CARGO PANTS:
   Must be a SEPARATE PANTS garment AND have obvious
   external cargo/patch pockets on the side legs.

5. NEVER classify a jumpsuit as cargo pants simply because
   the lower half looks like cargo pants.

6. NEVER classify bib overalls as cargo pants.

7. DENIM JEANS:
   Separate denim pants.

8. JOGGER:
   Separate pants with jogger construction,
   especially elastic/rib cuffs.

9. JACKET:
   Separate outerwear upper-body garment.

10. DRESS:
    One-piece dress silhouette, NOT pants-based jumpsuit.

Available categories:

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


Analyze these attributes:

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

Return ONLY valid JSON.

Use this exact format:

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
  "reason": "..."
}
"""


    # =================================================================
    # CALL GLM-4.5V
    # =================================================================

    try:

        response = hf_client.chat.completions.create(

            model=VISION_MODEL,

            messages=[

                {
                    "role": "user",

                    "content": [

                        {
                            "type": "image_url",

                            "image_url": {
                                "url": image_url
                            }
                        },

                        {
                            "type": "text",

                            "text": prompt
                        }

                    ]
                }

            ],

            max_tokens=1000,

            temperature=0.0

        )


    except Exception as e:

        error_text = str(e)


        # ---------------------------------------------------------
        # PROVIDER ERROR
        # ---------------------------------------------------------

        if (
            "model_not_supported"
            in error_text.lower()
        ):

            raise Exception(

                "Hugging Face không cho phép "
                "provider Novita cho token hiện tại.\n\n"

                "Model: zai-org/GLM-4.5V\n"

                "Provider: Novita\n\n"

                "Hãy kiểm tra Inference Providers "
                "trong Hugging Face account."

            )


        raise Exception(
            "Hugging Face GLM-4.5V lỗi: "
            + error_text
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
            "Không đọc được kết quả GLM-4.5V: "
            + str(e)
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

    result = normalize_garment_result(
        result
    )


    return result


# =====================================================================
# 6. GARMENT RULE ENGINE
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
    # VALID CATEGORY
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
    # BOOLEAN
    # =================================================================

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
                    "1"
                ]
            )


        result[field] = bool(
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
    # ONE PIECE → NEVER CARGO
    # =================================================================

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


    # =================================================================
    # 🔒 HARD RULE 2
    # BIB → OVERALL
    # =================================================================

    elif (

        result["bib"]

        and

        result["shoulder_straps"]

    ):

        result[
            "category"
        ] = "Quần yếm"


    # =================================================================
    # 🔒 HARD RULE 3
    # CARGO REQUIRES CARGO POCKET
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
