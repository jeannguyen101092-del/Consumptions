# =====================================================================
# 🔍 PRODUCT IMAGE SEARCH & BULK STORAGE
# VERSION V2.2
# 🔐 SAFE SECRETS / SUPABASE / HUGGING FACE
# =====================================================================

import streamlit as st
from supabase import create_client, Client
import requests
from PIL import Image
import io
import re
import hashlib


# =====================================================================
# 1. STREAMLIT CONFIG
# =====================================================================

st.set_page_config(
    page_title="Quản lý & Tìm kiếm mã hàng",
    page_icon="🔍",
    layout="wide"
)


# =====================================================================
# 2. 🔐 SECRET READER
# =====================================================================
# Không ghi URL / KEY / TOKEN trực tiếp trong code.
#
# Hàm này thử nhiều tên thường gặp.
# Giá trị thật chỉ nằm trong Streamlit/Tomy Secrets.
# =====================================================================

def get_secret_value(names):

    # ---------------------------------------------------------
    # A. Tìm trực tiếp
    # ---------------------------------------------------------

    for name in names:

        try:

            value = st.secrets.get(name)

            if value is not None:

                if str(value).strip():

                    return str(value).strip()

        except Exception:

            pass


    # ---------------------------------------------------------
    # B. Tìm trong nhóm [supabase], [huggingface], [hf]
    # ---------------------------------------------------------

    groups = [
        "supabase",
        "SUPABASE",
        "huggingface",
        "HUGGINGFACE",
        "hf",
        "HF"
    ]


    for group_name in groups:

        try:

            group = st.secrets.get(
                group_name
            )

            if group:

                for name in names:

                    try:

                        value = group.get(name)

                        if value is not None:

                            if str(value).strip():

                                return str(
                                    value
                                ).strip()

                    except Exception:

                        pass

        except Exception:

            pass


    return None


# =====================================================================
# 3. 🔐 TỰ TÌM SUPABASE URL
# =====================================================================

SUPABASE_URL = get_secret_value(
    [
        "SUPABASE_URL",
        "SUPABASE_PROJECT_URL",
        "SUPABASE_PROJECT",
        "supabase_url",
        "supabase_project_url",
        "url"
    ]
)


# =====================================================================
# 4. 🔐 TỰ TÌM SUPABASE KEY
# =====================================================================

SUPABASE_KEY = get_secret_value(
    [
        "SUPABASE_KEY",
        "SUPABASE_ANON_KEY",
        "SUPABASE_API_KEY",
        "SUPABASE_SERVICE_KEY",
        "supabase_key",
        "supabase_anon_key",
        "anon_key",
        "api_key"
    ]
)


# =====================================================================
# 5. 🔐 TỰ TÌM HUGGING FACE TOKEN
# =====================================================================

HF_TOKEN = get_secret_value(
    [
        "HF_TOKEN",
        "HUGGINGFACE_TOKEN",
        "HUGGING_FACE_TOKEN",
        "HF_API_TOKEN",
        "HUGGINGFACE_API_TOKEN",
        "huggingface_token",
        "hugging_face_token",
        "hf_token"
    ]
)


# =====================================================================
# 6. KIỂM TRA SECRET
# =====================================================================

missing_secrets = []

if not SUPABASE_URL:

    missing_secrets.append(
        "SUPABASE URL"
    )


if not SUPABASE_KEY:

    missing_secrets.append(
        "SUPABASE KEY"
    )


if not HF_TOKEN:

    missing_secrets.append(
        "HUGGING FACE TOKEN"
    )


if missing_secrets:

    st.error(
        "❌ Không đọc được Secret cần thiết."
    )

    st.warning(
        "Các thông tin còn thiếu:\n\n"
        + "\n".join(
            [
                f"- {x}"
                for x in missing_secrets
            ]
        )
    )

    st.info(
        "⚠️ Code này không chứa key thật. "
        "Secret phải tồn tại trong phần Secrets "
        "của app."
    )

    st.stop()


# =====================================================================
# 7. MODEL HUGGING FACE
# =====================================================================
# Có thể lưu HF_MODEL trong Secrets.
#
# Nếu không có thì dùng tên mặc định.
# =====================================================================

HF_MODEL = get_secret_value(
    [
        "HF_MODEL",
        "HUGGINGFACE_MODEL",
        "HF_IMAGE_MODEL",
        "huggingface_model"
    ]
)


if not HF_MODEL:

    HF_MODEL = (
        "openai/clip-vit-base-patch32"
    )


# =====================================================================
# 8. HUGGING FACE API URL
# =====================================================================

API_URL = (
    "https://router.huggingface.co/"
    "hf-inference/models/"
    f"{HF_MODEL}"
)


# =====================================================================
# 9. HUGGING FACE HEADERS
# =====================================================================

headers = {

    "Authorization":
        f"Bearer {HF_TOKEN}",

    "Content-Type":
        "application/octet-stream",

    "User-Agent":
        (
            "Mozilla/5.0 "
            "(Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/120.0.0.0 "
            "Safari/537.36"
        )
}


# =====================================================================
# 10. KẾT NỐI SUPABASE
# =====================================================================

try:

    supabase: Client = create_client(
        SUPABASE_URL,
        SUPABASE_KEY
    )

except Exception as e:

    st.error(
        "❌ Không thể kết nối Supabase."
    )

    st.exception(e)

    st.stop()


# =====================================================================
# 11. CATEGORY
# =====================================================================

CATEGORY_OPTIONS = [

    "Quần dài",

    "Quần short",

    "Áo",

    "Quần jogger",

    "Quần jean",

    "Quần túi hộp"
]


# =====================================================================
# 12. NORMALIZE IMAGE
# =====================================================================

def normalize_image_bytes(
    file_bytes
):

    try:

        image = Image.open(
            io.BytesIO(
                file_bytes
            )
        )


        if image.mode != "RGB":

            image = image.convert(
                "RGB"
            )


        output = io.BytesIO()


        image.save(
            output,
            format="JPEG",
            quality=95
        )


        return output.getvalue()


    except Exception as e:

        raise Exception(
            f"Không đọc được ảnh: {e}"
        )


# =====================================================================
# 13. IMAGE HASH
# =====================================================================

def get_image_hash(
    image_bytes
):

    return hashlib.sha256(
        image_bytes
    ).hexdigest()


# =====================================================================
# 14. GET IMAGE EMBEDDING
# =====================================================================

def get_image_embedding_via_api(
    image_bytes
):

    try:

        response = requests.post(

            API_URL,

            headers=headers,

            data=image_bytes,

            timeout=120

        )


    except requests.exceptions.Timeout:

        raise Exception(
            "Hugging Face timeout "
            "sau 120 giây."
        )


    except requests.exceptions.RequestException as e:

        raise Exception(
            f"Lỗi kết nối Hugging Face: {e}"
        )


    # ---------------------------------------------------------
    # HTTP ERROR
    # ---------------------------------------------------------

    if response.status_code != 200:

        error_text = response.text

        try:

            error_json = (
                response.json()
            )

            if isinstance(
                error_json,
                dict
            ):

                error_text = (

                    error_json.get(
                        "error"
                    )

                    or

                    error_json.get(
                        "message"
                    )

                    or

                    error_text

                )

        except Exception:

            pass


        raise Exception(

            "Hugging Face HTTP "
            f"{response.status_code}: "
            f"{error_text}"

        )


    # ---------------------------------------------------------
    # JSON
    # ---------------------------------------------------------

    try:

        result = response.json()

    except Exception:

        raise Exception(
            "Hugging Face trả về "
            "dữ liệu không phải JSON."
        )


    # ---------------------------------------------------------
    # EXTRACT EMBEDDING
    # ---------------------------------------------------------

    embedding = None


    # Dạng:
    #
    # [0.123, 0.456, ...]
    #

    if isinstance(
        result,
        list
    ):

        if (

            len(result) > 0

            and

            isinstance(
                result[0],
                (int, float)
            )

        ):

            embedding = result


        # -----------------------------------------------------
        # Dạng:
        #
        # [[0.123, 0.456, ...]]
        # -----------------------------------------------------

        elif (

            len(result) > 0

            and

            isinstance(
                result[0],
                list
            )

        ):

            embedding = result[0]


    # ---------------------------------------------------------
    # Dạng dictionary
    # ---------------------------------------------------------

    elif isinstance(
        result,
        dict
    ):

        embedding = (
            result.get(
                "embedding"
            )
        )


        if embedding is None:

            embedding = (
                result.get(
                    "vector"
                )
            )


        if embedding is None:

            embedding = (
                result.get(
                    "embeddings"
                )
            )


    # ---------------------------------------------------------
    # CHECK
    # ---------------------------------------------------------

    if embedding is None:

        raise Exception(

            "Không tìm thấy embedding "
            "trong response Hugging Face."

        )


    if not isinstance(
        embedding,
        list
    ):

        raise Exception(
            "Embedding không phải dạng list."
        )


    try:

        embedding = [

            float(x)

            for x in embedding

        ]

    except Exception:

        raise Exception(
            "Embedding chứa dữ liệu "
            "không phải số."
        )


    if len(embedding) == 0:

        raise Exception(
            "Embedding rỗng."
        )


    return embedding


# =====================================================================
# 15. CACHE EMBEDDING
# =====================================================================

@st.cache_data(
    ttl=3600,
    show_spinner=False
)
def get_cached_embedding(
    image_hash,
    image_bytes
):

    return get_image_embedding_via_api(
        image_bytes
    )


# =====================================================================
# 16. CONTENT TYPE
# =====================================================================

def get_content_type(
    filename
):

    extension = (

        filename
        .lower()
        .rsplit(
            ".",
            1
        )[-1]

    )


    if extension == "png":

        return "image/png"


    if extension in [
        "jpg",
        "jpeg"
    ]:

        return "image/jpeg"


    return (
        "application/octet-stream"
    )


# =====================================================================
# 17. SANITIZE FILENAME
# =====================================================================

def sanitize_filename(
    filename
):

    filename = filename.strip()


    filename = re.sub(

        r"[^A-Za-z0-9._-]",

        "_",

        filename

    )


    return filename


# =====================================================================
# 18. EXTRACT PRODUCT CODE
# =====================================================================

def extract_product_code(
    filename
):

    filename_only = (
        filename.rsplit(
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
# 19. UPLOAD IMAGE STORAGE
# =====================================================================

def upload_image_to_storage(

    file_bytes,

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


    try:

        content_type = (
            get_content_type(
                safe_filename
            )
        )


        storage = (
            supabase
            .storage
            .from_(
                bucket_name
            )
        )


        storage.upload(

            path=safe_filename,

            file=file_bytes,

            file_options={

                "content-type":
                    content_type,

                "upsert":
                    "true"

            }

        )


        public_url = (
            storage
            .get_public_url(
                safe_filename
            )
        )


        return public_url


    except Exception as e:

        raise Exception(

            f"Lỗi upload Storage "
            f"{filename}: {e}"

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

    try:

        (

            supabase

            .table(
                "products"
            )

            .upsert(

                {

                    "product_code":
                        product_code,

                    "image_url":
                        image_url,

                    "category":
                        category,

                    "embedding":
                        embedding

                },

                on_conflict=
                    "product_code"

            )

            .execute()

        )


    except Exception as e:

        raise Exception(

            f"Lỗi lưu product "
            f"{product_code}: {e}"

        )


# =====================================================================
# 21. TABS
# =====================================================================

tab1, tab2 = st.tabs(

    [

        "🔍 TÌM KIẾM MÃ HÀNG TƯƠNG ĐỒNG",

        "📦 LƯU KHO HÀNG LOẠT"

    ]

)


# =====================================================================
# TAB 1
# SEARCH
# =====================================================================

with tab1:

    st.header(
        "🔍 Tìm Kiếm Mã Hàng Qua Ảnh Sketch"
    )


    col_search_1, col_search_2 = (
        st.columns(2)
    )


    # -----------------------------------------------------------------
    # INPUT
    # -----------------------------------------------------------------

    with col_search_1:

        search_category = (
            st.selectbox(

                "Chọn dòng hàng cần tìm kiếm:",

                CATEGORY_OPTIONS,

                key="sb_search"

            )
        )


        uploaded_sketch = (
            st.file_uploader(

                "Tải lên ảnh Sketch cần tìm:",

                type=[

                    "png",

                    "jpg",

                    "jpeg"

                ],

                key="fu_search"

            )
        )


    # -----------------------------------------------------------------
    # PREVIEW
    # -----------------------------------------------------------------

    if uploaded_sketch is not None:

        with col_search_2:

            st.image(

                uploaded_sketch,

                caption=
                    "Ảnh Sketch của bạn",

                width=250

            )


            # ---------------------------------------------------------
            # SEARCH BUTTON
            # ---------------------------------------------------------

            if st.button(

                "🚀 Bắt đầu quét mã tương đồng",

                type="primary",

                key="btn_search"

            ):

                with st.spinner(

                    "🤖 Hệ thống đang phân tích ảnh..."

                ):

                    try:

                        # -------------------------------------------------
                        # READ
                        # -------------------------------------------------

                        raw_bytes = (
                            uploaded_sketch
                            .getvalue()
                        )


                        # -------------------------------------------------
                        # NORMALIZE
                        # -------------------------------------------------

                        sketch_bytes = (
                            normalize_image_bytes(
                                raw_bytes
                            )
                        )


                        # -------------------------------------------------
                        # HASH
                        # -------------------------------------------------

                        image_hash = (
                            get_image_hash(
                                sketch_bytes
                            )
                        )


                        # -------------------------------------------------
                        # EMBEDDING
                        # -------------------------------------------------

                        sketch_embedding = (
                            get_cached_embedding(

                                image_hash,

                                sketch_bytes

                            )
                        )


                        if not sketch_embedding:

                            raise Exception(

                                "AI không tạo được "
                                "embedding."

                            )


                        # -------------------------------------------------
                        # SUPABASE RPC
                        # -------------------------------------------------

                        response = (

                            supabase

                            .rpc(

                                "match_products_v2",

                                {

                                    "query_embedding":
                                        sketch_embedding,

                                    "match_threshold":
                                        0.40,

                                    "match_count":
                                        4,

                                    "filter_category":
                                        search_category

                                }

                            )

                            .execute()

                        )


                        # -------------------------------------------------
                        # RESULTS
                        # -------------------------------------------------

                        if response.data:

                            st.success(

                                "🎯 Kết quả tìm kiếm "
                                f"trong nhóm "
                                f"**{search_category}**:"

                            )


                            cols = (
                                st.columns(
                                    len(
                                        response.data
                                    )
                                )
                            )


                            for idx, item in enumerate(

                                response.data

                            ):

                                with cols[idx]:

                                    similarity = float(

                                        item.get(

                                            "similarity",

                                            0

                                        )

                                    )


                                    st.metric(

                                        "Độ giống nhau",

                                        f"{similarity * 100:.2f}%"

                                    )


                                    st.subheader(

                                        "Mã: "

                                        +

                                        str(

                                            item.get(

                                                "product_code",

                                                "N/A"

                                            )

                                        )

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


                        else:

                            st.warning(

                                "⚠️ Không tìm thấy "
                                "sản phẩm tương đồng "
                                f"trong nhóm "
                                f"**{search_category}**."

                            )


                    except Exception as e:

                        st.error(
                            "❌ Lỗi hệ thống:"
                        )

                        st.exception(e)


# =====================================================================
# TAB 2
# BULK UPLOAD
# =====================================================================

with tab2:

    st.header(

        "📦 Đẩy Dữ Liệu Mã Hàng Hàng Loạt "
        "Lên Hệ Thống"

    )


    st.info(

        "💡 Cách đặt tên file:\n\n"

        "**Tên_file_ảnh = Mã_hàng**\n\n"

        "Ví dụ: `MS-1024.jpg` → "
        "`MS-1024`"

    )


    col_upload_1, col_upload_2 = (
        st.columns(2)
    )


    # -----------------------------------------------------------------
    # INPUT
    # -----------------------------------------------------------------

    with col_upload_1:

        upload_category = (
            st.selectbox(

                "Phân loại dòng hàng khi lưu kho:",

                CATEGORY_OPTIONS,

                key="sb_upload"

            )
        )


        uploaded_files = (
            st.file_uploader(

                "Chọn nhiều ảnh sản phẩm gốc / "
                "ảnh mẫu để lưu kho:",

                type=[

                    "png",

                    "jpg",

                    "jpeg"

                ],

                accept_multiple_files=True,

                key="fu_bulk"

            )
        )


    # -----------------------------------------------------------------
    # FILES
    # -----------------------------------------------------------------

    if uploaded_files:

        with col_upload_2:

            st.write(

                f"📂 Đã chọn "
                f"**{len(uploaded_files)}** "
                f"file ảnh."

            )


            if st.button(

                "📤 Tiến hành lưu toàn bộ vào kho",

                type="primary",

                key="btn_bulk_upload"

            ):

                progress_bar = (
                    st.progress(0)
                )


                status_text = (
                    st.empty()
                )


                success_count = 0

                failed_count = 0

                failed_items = []


                # =====================================================
                # LOOP
                # =====================================================

                for index, file in enumerate(
                    uploaded_files
                ):

                    product_code = (
                        extract_product_code(
                            file.name
                        )
                    )


                    status_text.text(

                        f"⏳ Đang xử lý "
                        f"({index + 1}/"
                        f"{len(uploaded_files)}): "
                        f"{product_code}"

                    )


                    try:

                        # -------------------------------------------------
                        # FILE
                        # -------------------------------------------------

                        raw_bytes = (
                            file.getvalue()
                        )


                        if not raw_bytes:

                            raise Exception(
                                "File ảnh rỗng."
                            )


                        # -------------------------------------------------
                        # NORMALIZE
                        # -------------------------------------------------

                        image_bytes = (
                            normalize_image_bytes(
                                raw_bytes
                            )
                        )


                        # -------------------------------------------------
                        # FILENAME
                        # -------------------------------------------------

                        safe_filename = (
                            sanitize_filename(
                                file.name
                            )
                        )


                        # -------------------------------------------------
                        # STORAGE
                        # -------------------------------------------------

                        img_url = (
                            upload_image_to_storage(

                                image_bytes,

                                safe_filename

                            )
                        )


                        if not img_url:

                            raise Exception(

                                "Không nhận được "
                                "image URL."

                            )


                        # -------------------------------------------------
                        # HASH
                        # -------------------------------------------------

                        image_hash = (
                            get_image_hash(
                                image_bytes
                            )
                        )


                        # -------------------------------------------------
                        # EMBEDDING
                        # -------------------------------------------------

                        embedding_data = (
                            get_cached_embedding(

                                image_hash,

                                image_bytes

                            )
                        )


                        if not embedding_data:

                            raise Exception(

                                "Không tạo được "
                                "embedding."

                            )


                        # -------------------------------------------------
                        # SAVE DATABASE
                        # -------------------------------------------------

                        save_product(

                            product_code=
                                product_code,

                            image_url=
                                img_url,

                            category=
                                upload_category,

                            embedding=
                                embedding_data

                        )


                        success_count += 1


                    except Exception as e:

                        failed_count += 1


                        failed_items.append(

                            {

                                "file":
                                    file.name,

                                "product_code":
                                    product_code,

                                "error":
                                    str(e)

                            }

                        )


                    # -------------------------------------------------
                    # PROGRESS
                    # -------------------------------------------------

                    progress_bar.progress(

                        int(

                            (

                                (index + 1)

                                /

                                len(
                                    uploaded_files
                                )

                            )

                            *

                            100

                        )

                    )


                # =====================================================
                # COMPLETE
                # =====================================================

                status_text.empty()


                if success_count > 0:

                    st.success(

                        f"🎉 Hoàn thành! "
                        f"Đã lưu thành công "
                        f"**{success_count}/"
                        f"{len(uploaded_files)}** "
                        f"mã hàng vào nhóm "
                        f"**{upload_category}**."

                    )


                if failed_count > 0:

                    st.warning(

                        f"⚠️ Có "
                        f"**{failed_count}** "
                        f"file chưa lưu được."

                    )


                    with st.expander(

                        "🔎 Xem chi tiết file lỗi"

                    ):

                        for item in failed_items:

                            st.error(

                                f"**{item['file']}**\n\n"

                                f"Mã: "
                                f"{item['product_code']}\n\n"

                                f"Lỗi: "
                                f"{item['error']}"

                            )


                st.info(

                    f"📊 Tổng kết: "

                    f"✅ {success_count} thành công | "

                    f"❌ {failed_count} lỗi | "

                    f"📦 {len(uploaded_files)} file"

                )
