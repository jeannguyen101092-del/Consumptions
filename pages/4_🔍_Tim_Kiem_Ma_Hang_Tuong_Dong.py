# =====================================================================
# 🤖🔍 AI GARMENT SEARCH & WAREHOUSE
# VERSION V3.7
#
# VISION:
#   Google Gemini 2.5 Flash
#
# IMAGE EMBEDDING:
#   OpenAI CLIP ViT-B/32 - LOCAL
#
# DATABASE:
#   Supabase
#
# TAB 1:
#   Upload ảnh
#   Gemini tự nhận diện category
#   CLIP 512D
#   Search Supabase
#   Category Lock
#
# TAB 2:
#   Upload nhiều ảnh
#   Gemini tự nhận category
#   CLIP 512D
#   Lưu Supabase
#
# XÓA FILE:
#   Chỉ xóa file đang chờ trên màn hình
#   KHÔNG xóa database
#   KHÔNG xóa storage
#
# SECURITY:
#   Không hard-code API KEY
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
import os
import re
import json

import numpy as np
import torch

from PIL import Image

from supabase import create_client, Client

from transformers import (
    CLIPProcessor,
    CLIPModel
)

try:

    from google import genai
    from google.genai import types

except Exception:

    genai = None
    types = None


# =====================================================================
# 3. ĐỌC SECRET
# =====================================================================

def read_secret(*names):

    # ---------------------------------------------------------
    # Streamlit Secrets
    # ---------------------------------------------------------

    for name in names:

        try:

            value = st.secrets.get(
                name
            )

            if value:

                return str(
                    value
                ).strip()

        except Exception:

            pass


    # ---------------------------------------------------------
    # Environment
    # ---------------------------------------------------------

    for name in names:

        try:

            value = os.getenv(
                name
            )

            if value:

                return str(
                    value
                ).strip()

        except Exception:

            pass


    return None


# =====================================================================
# 4. SUPABASE
# =====================================================================

SUPABASE_URL = read_secret(

    "SUPABASE_URL",
    "SUPABASE_PROJECT_URL",
    "supabase_url"

)


SUPABASE_KEY = read_secret(

    "SUPABASE_KEY",
    "SUPABASE_ANON_KEY",
    "SUPABASE_PUBLISHABLE_KEY",
    "supabase_key",
    "supabase_anon_key"

)


# =====================================================================
# 5. GEMINI
# =====================================================================

GEMINI_API_KEY = read_secret(

    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "GEMINI_KEY",
    "gemini_api_key"

)


# =====================================================================
# 6. CHECK CONFIG
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


if not GEMINI_API_KEY:

    missing.append(
        "GEMINI_API_KEY"
    )


if missing:

    st.error(
        "❌ Không đọc được cấu hình bảo mật."
    )


    st.write(
        "Thiếu:"
    )


    for item in missing:

        st.write(
            f"- `{item}`"
        )


    st.info(
        "Key phải nằm trong Streamlit Secrets/Tomy, "
        "không ghi trực tiếp vào GitHub."
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
# 8. GEMINI CLIENT
# =====================================================================

if genai is None:

    st.error(
        "❌ Chưa cài google-genai."
    )

    st.code(
        "google-genai"
    )

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
# 9. MODELS
# =====================================================================

GEMINI_MODEL = (
    "gemini-2.5-flash"
)


CLIP_MODEL_NAME = (
    "openai/clip-vit-base-patch32"
)


PRODUCT_TABLE = (
    "products"
)


PRODUCT_BUCKET = (
    "product-images"
)


MATCH_RPC = (
    "match_products_v2"
)


# =====================================================================
# 10. CATEGORY
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
# 11. CATEGORY ALIAS
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
# 12. CLIP MODEL
# =====================================================================

@st.cache_resource(
    show_spinner=False
)
def load_clip_model():

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


# =====================================================================
# 13. JSON EXTRACT
# =====================================================================
# =====================================================================
# 🔧 JSON PARSER - V3.8
# FIX GEMINI TRUNCATED JSON
# =====================================================================

def extract_json(text):

    if not text:

        raise Exception(
            "Gemini không trả dữ liệu."
        )


    text = str(text).strip()


    # ================================================================
    # REMOVE MARKDOWN
    # ================================================================

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


    # ================================================================
    # 1. TÌM JSON OBJECT
    # ================================================================

    start = text.find("{")

    if start == -1:

        raise Exception(

            "Gemini không trả JSON.\n\n"
            +
            text[:2000]

        )


    json_text = text[start:]


    # ================================================================
    # 2. THỬ JSON BÌNH THƯỜNG
    # ================================================================

    try:

        return json.loads(
            json_text
        )

    except Exception:

        pass


    # ================================================================
    # 3. GEMINI BỊ CẮT JSON
    #
    # Ví dụ:
    #
    # {
    #   "category": "Áo",
    #   "confidence": 98,
    #   "one_piece": false,
    #   "bib": false,
    #   "shoulder_straps": false
    #
    # ================================================================

    # Lấy từng field quan trọng
    result = {}


    # ------------------------------------------------
    # CATEGORY
    # ------------------------------------------------

    category_match = re.search(

        r'"category"\s*:\s*"([^"]+)"',

        json_text,

        flags=re.I

    )


    if category_match:

        result[
            "category"
        ] = category_match.group(1)


    # ------------------------------------------------
    # CONFIDENCE
    # ------------------------------------------------

    confidence_match = re.search(

        r'"confidence"\s*:\s*([0-9]+(?:\.[0-9]+)?)',

        json_text,

        flags=re.I

    )


    if confidence_match:

        try:

            result[
                "confidence"
            ] = float(
                confidence_match.group(1)
            )

        except Exception:

            result[
                "confidence"
            ] = 0


    # ------------------------------------------------
    # BOOLEAN FIELDS
    # ------------------------------------------------

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

            rf'"{field}"\s*:\s*(true|false)',

            json_text,

            flags=re.I

        )


        if match:

            result[field] = (

                match.group(1)
                .lower()
                ==
                "true"

            )


        else:

            # Không có field → mặc định False

            result[field] = False


    # ------------------------------------------------
    # STRING FIELDS
    # ------------------------------------------------

    string_fields = [

        "sleeve",
        "collar",
        "silhouette",
        "length",
        "reason"

    ]


    for field in string_fields:

        match = re.search(

            rf'"{field}"\s*:\s*"([^"]*)"', 

            json_text,

            flags=re.I

        )


        if match:

            result[field] = (
                match.group(1)
            )

        else:

            result[field] = ""


    # ================================================================
    # 4. KIỂM TRA FIELD QUAN TRỌNG
    # ================================================================

    if not result.get(
        "category"
    ):

        raise Exception(

            "Gemini không trả category.\n\n"
            +
            text[:2000]

        )


    # ================================================================
    # 5. TRẢ RESULT
    # ================================================================

    return result

# =====================================================================
# 16. GEMINI VISION
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

                    max_output_tokens=1000

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

    except Exception:

        text = None


    result = extract_json(
        text
    )


    return normalize_garment_result(
        result
    )


# =====================================================================
# 17. CLIP EMBEDDING
# =====================================================================

def get_clip_embedding(
    image_bytes
):

    try:

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

            image_features = (
                model.get_image_features(
                    **inputs
                )
            )


        # ---------------------------------------------------------
        # Transformers compatibility
        # ---------------------------------------------------------

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


        image_features = (
            image_features
            .detach()
            .cpu()
            .float()
        )


        if image_features.ndim == 1:

            vector = image_features


        elif image_features.ndim == 2:

            vector = image_features[
                0
            ]


        else:

            vector = (
                image_features
                .reshape(-1)
            )


        vector = (
            vector
            .numpy()
            .astype(
                np.float32
            )
        )


        if len(vector) != 512:

            raise Exception(

                "CLIP output không phải 512D. "
                f"Nhận {len(vector)}D."

            )


        norm = np.linalg.norm(
            vector
        )


        if norm <= 0:

            raise Exception(
                "CLIP vector norm = 0."
            )


        vector = (
            vector / norm
        )


        return vector.tolist()


    except Exception as e:

        raise Exception(

            "CLIP embedding lỗi: "
            +
            repr(e)

        )


# =====================================================================
# 18. PRODUCT CODE
# =====================================================================

def clean_product_code(
    filename
):

    filename = str(
        filename
    )


    name = (
        filename
        .rsplit(
            ".",
            1
        )[0]
    )


    name = re.sub(
        r"[^A-Za-z0-9_\-]",
        "",
        name
    )


    return name.upper()


# =====================================================================
# 19. STORAGE
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
# 20. SAVE PRODUCT
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
# 21. SEARCH SUPABASE
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
# 22. CATEGORY LOCK
# =====================================================================

def category_lock(
    results,
    category
):

    output = []


    for item in results:

        item_category = str(

            item.get(
                "category",
                ""
            )

        ).strip()


        if item_category == category:

            output.append(
                item
            )


    return output


# =====================================================================
# 23. SHOW AI RESULT
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
# 24. SHOW SEARCH RESULTS
# =====================================================================

def show_results(
    results
):

    if not results:

        st.warning(

            "Không tìm thấy mã tương đồng "
            "trong cùng category."

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
# 25. HEADER
# =====================================================================

st.title(
    "🔍 AI TÌM KIẾM MÃ HÀNG TƯƠNG ĐỒNG"
)


st.caption(
    "Gemini Vision + Local CLIP + Supabase"
)


# =====================================================================
# 26. TABS
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

        "AI tự nhận diện category. "
        "Không cần chọn dòng hàng."

    )


    uploaded_sketch = st.file_uploader(

        "📂 Tải ảnh cần tìm",

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

                "**File:** "
                +
                uploaded_sketch.name

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


                    # ------------------------------------------------
                    # GEMINI
                    # ------------------------------------------------

                    with st.spinner(
                        "🤖 Gemini đang nhận diện..."
                    ):

                        ai_result = (
                            analyze_garment_with_gemini(
                                image_bytes
                            )
                        )


                    show_ai_result(
                        ai_result
                    )


                    # ------------------------------------------------
                    # CLIP
                    # ------------------------------------------------

                    with st.spinner(
                        "🧠 CLIP đang tạo vector 512D..."
                    ):

                        embedding = (
                            get_clip_embedding(
                                image_bytes
                            )
                        )


                    st.caption(
                        "CLIP: 512D"
                    )


                    # ------------------------------------------------
                    # SUPABASE
                    # ------------------------------------------------

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


                    # ------------------------------------------------
                    # CATEGORY LOCK
                    # ------------------------------------------------

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

                        f"CLIP tìm thấy "
                        f"**{len(results)}** mã."

                    )


                    st.write(

                        f"Cùng category: "
                        f"**{len(locked)}** mã."

                    )


                    show_results(
                        locked[:8]
                    )


                except Exception as e:

                    st.error(
                        "❌ Lỗi tìm kiếm."
                    )

                    st.exception(e)


# #####################################################################
# TAB 2
# #####################################################################

with tab2:

    st.header(
        "📦 ĐẨY DỮ LIỆU MÃ HÀNG HÀNG LOẠT"
    )


    st.info(

        "Gemini tự nhận diện category. "
        "Không cần chọn dòng hàng."

    )


    # =================================================================
    # UPLOADER VERSION
    # =================================================================

    if (
        "warehouse_uploader_version"
        not in st.session_state
    ):

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
    # CHỈ 1 FILE UPLOADER
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
    # FILE ĐANG CHỜ
    # =================================================================

    if uploaded_files:

        st.write(

            f"📂 Đang có "
            f"**{len(uploaded_files)}** "
            f"file chờ xử lý."

        )


        with st.expander(

            "📋 Danh sách file đang chờ",

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
        # SAVE
        # =============================================================

        if st.button(

            "📤 GEMINI + CLIP → LƯU KHO",

            type="primary",

            key="save_all_products"

        ):

            progress = st.progress(
                0
            )


            status = st.empty()


            total = len(
                uploaded_files
            )


            success = 0

            errors = 0


            results = []


            # ---------------------------------------------------------
            # LOOP
            # ---------------------------------------------------------

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
                    f"— {product_code}"

                )


                try:

                    image_bytes = (
                        file.getvalue()
                    )


                    # =================================================
                    # GEMINI CATEGORY
                    # =================================================

                    ai_result = (

                        analyze_garment_with_gemini(

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

                    (index + 1)
                    /
                    total

                )


            status.empty()


            st.session_state[
                "warehouse_results"
            ] = results


            st.success(

                f"🎉 Đã lưu "
                f"**{success}/{total}** "
                f"mã hàng."

            )


            if errors:

                st.warning(

                    f"⚠️ Có {errors} file lỗi."

                )


    # =================================================================
    # RESULT
    # =================================================================

    if (

        "warehouse_results"
        in st.session_state

    ):

        results = (

            st.session_state[
                "warehouse_results"
            ]

        )


        if results:

            st.markdown(
                "### 🤖 KẾT QUẢ GEMINI"
            )


            st.dataframe(

                results,

                use_container_width=True

            )


    # =================================================================
    # 🗑️ XÓA FILE ĐANG CHỜ
    # =================================================================
    #
    # CHỈ RESET FILE UPLOADER
    #
    # KHÔNG XÓA SUPABASE
    #
    # =================================================================

    st.divider()


    if st.button(

        "🗑️ XÓA FILE ĐANG CHỜ",

        key="clear_pending_upload"

    ):

        st.session_state[
            "warehouse_uploader_version"
        ] += 1


        if (

            "warehouse_results"
            in st.session_state

        ):

            del st.session_state[
                "warehouse_results"
            ]


        st.rerun()


# =====================================================================
# SIDEBAR
# =====================================================================

with st.sidebar:

    st.header(
        "⚙️ AI ENGINE"
    )


    st.success(
        "Supabase Connected"
    )


    st.success(
        "Gemini Connected"
    )


    st.caption(
        "Vision:"
    )


    st.caption(
        GEMINI_MODEL
    )


    st.caption(
        "Embedding:"
    )


    st.caption(
        "CLIP ViT-B/32 — 512D"
    )


    st.caption(
        "Database:"
    )


    st.caption(
        PRODUCT_TABLE
    )


# =====================================================================
# END
# =====================================================================
