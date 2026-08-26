# =====================================================================
# 🤖 GEMINI VISION ENGINE
# VERSION V3.9
# FIX:
# - GARMENT_PROMPT undefined
# - Gemini trả JSON bị cắt
# - Áo liền quần không bị nhận thành Cargo
# - Quần yếm không bị nhận thành Cargo
# =====================================================================

import re
import json
import streamlit as st

from google import genai
from google.genai import types


# =====================================================================
# 1. GEMINI MODEL
# =====================================================================

GEMINI_MODEL = "gemini-2.5-flash"


# =====================================================================
# 2. CATEGORY MASTER
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
# 3. CATEGORY ALIAS
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
# 4. GARMENT PROMPT
# =====================================================================

GARMENT_PROMPT = r"""
You are a SENIOR APPAREL TECHNICAL DESIGNER and
COMMERCIAL GARMENT RECOGNITION AI.

Analyze the uploaded garment image/sketch for a
commercial apparel similarity database.

Your primary job is to identify the TRUE garment
construction, NOT merely the visual silhouette.

===========================================================
CRITICAL CLASSIFICATION RULES
===========================================================

RULE 1 — JUMPSUIT / ONE-PIECE
-----------------------------------------------------------

If the upper body and lower body are physically connected
as one garment:

category = "Áo liền quần"

Examples:
- jumpsuit
- coverall
- one-piece utility garment
- one-piece workwear

IMPORTANT:

A one-piece garment MUST NEVER be classified as:

"Quần túi hộp"

even if the lower body has cargo pockets.

Set:

one_piece = true


===========================================================
RULE 2 — BIB OVERALL / QUẦN YẾM
===========================================================

If the garment has:

- bib front
- shoulder straps
- pants bottom
- separate overall construction

category = "Quần yếm"

Set:

bib = true
shoulder_straps = true

A bib overall MUST NEVER be classified as cargo pants.


===========================================================
RULE 3 — CARGO PANTS
===========================================================

"Quần túi hộp" is ONLY allowed when ALL conditions
are satisfied:

1. It is a SEPARATE pants garment.
2. Upper and lower body are NOT connected.
3. There are clearly visible external cargo / patch pockets.
4. The pockets are located on the side legs.

Set:

one_piece = false
cargo_pockets = true

If cargo pockets are NOT clearly visible:

cargo_pockets = false

DO NOT GUESS cargo pockets.


===========================================================
RULE 4 — JEANS
===========================================================

Separate denim pants.

category = "Quần jean"

Set:

denim = true


===========================================================
RULE 5 — JOGGER
===========================================================

Separate pants with clear jogger construction,
especially elastic/rib ankle cuffs.

category = "Quần jogger"

Set:

jogger_cuffs = true


===========================================================
RULE 6 — JACKET
===========================================================

Separate upper-body outerwear garment.

category = "Jacket"


===========================================================
RULE 7 — DRESS
===========================================================

A one-piece dress silhouette is:

category = "Dress"

Do NOT confuse a dress with a jumpsuit.

The lower section of a dress does NOT have separate
pant legs.


===========================================================
AVAILABLE CATEGORIES
===========================================================

Only use one of:

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
IMPORTANT DECISION ORDER
===========================================================

Before selecting category, determine in this order:

1. Is it one-piece?
2. Is it bib overall?
3. Is it a separate pants?
4. If separate pants, does it have cargo pockets?
5. Is it denim?
6. Is it jogger?
7. Otherwise determine the normal garment type.


===========================================================
OUTPUT
===========================================================

Return ONLY JSON.

Do not return Markdown.

Do not return explanation outside JSON.

category and confidence are REQUIRED.

Keep the JSON SHORT.

Use this exact structure:

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
  "reason": "..."
}

"""


# =====================================================================
# 5. JSON PARSER
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
    # FIND {
    # ---------------------------------------------------------------

    start = text.find("{")

    if start < 0:

        raise Exception(

            "Gemini không trả JSON.\n\n"
            + text[:2000]

        )


    json_text = text[start:]


    # ---------------------------------------------------------------
    # FIRST TRY
    # ---------------------------------------------------------------

    try:

        return json.loads(
            json_text
        )

    except Exception:

        pass


    # ---------------------------------------------------------------
    # GEMINI JSON BỊ CẮT
    # ---------------------------------------------------------------

    result = {}


    # ---------------------------------------------------------------
    # CATEGORY
    # ---------------------------------------------------------------

    m = re.search(

        r'"category"\s*:\s*"([^"]+)"',

        json_text,

        flags=re.I

    )

    if m:

        result[
            "category"
        ] = m.group(1)


    # ---------------------------------------------------------------
    # CONFIDENCE
    # ---------------------------------------------------------------

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


    # ---------------------------------------------------------------
    # REASON
    # ---------------------------------------------------------------

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


    # ---------------------------------------------------------------
    # REQUIRED CATEGORY
    # ---------------------------------------------------------------

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
# 6. NORMALIZE RESULT
# =====================================================================

def normalize_garment_result(
    result
):

    if not isinstance(
        result,
        dict
    ):

        raise Exception(
            "Gemini result không phải dictionary."
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
    # INVALID CATEGORY
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
    # 🔒 HARD RULE 1
    # ONE PIECE
    # ================================================================

    if result[
        "one_piece"
    ]:

        # ------------------------------------------------------------
        # Bib + straps → Overall
        # ------------------------------------------------------------

        if (

            result["bib"]

            and

            result["shoulder_straps"]

        ):

            result[
                "category"
            ] = "Quần yếm"

        # ------------------------------------------------------------
        # Normal jumpsuit
        # ------------------------------------------------------------

        else:

            result[
                "category"
            ] = "Áo liền quần"


        # ------------------------------------------------------------
        # FORCE REMOVE CARGO
        # ------------------------------------------------------------

        result[
            "cargo_pockets"
        ] = False


    # ================================================================
    # 🔒 HARD RULE 2
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
    # 🔒 HARD RULE 3
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
    # 🔒 HARD RULE 4
    # DENIM
    # ================================================================

    elif (

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


    # ================================================================
    # 🔒 HARD RULE 5
    # JOGGER
    # ================================================================

    elif (

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
# 7. GEMINI VISION FUNCTION
# =====================================================================

def analyze_garment_with_gemini(
    image_bytes
):

    try:

        # ============================================================
        # SEND IMAGE TO GEMINI
        # ============================================================

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


    # ================================================================
    # READ RESPONSE
    # ================================================================

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


    # ================================================================
    # PARSE JSON
    # ================================================================

    result = extract_json(
        text
    )


    # ================================================================
    # NORMALIZE
    # ================================================================

    result = normalize_garment_result(
        result
    )


    return result
