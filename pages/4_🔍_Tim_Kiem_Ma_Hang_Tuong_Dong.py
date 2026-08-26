# =====================================================================
# 🔍 PRODUCT IMAGE SEARCH & BULK STORAGE
# VERSION V2.1
# 🔐 SECURITY: ALL API KEYS LOADED FROM STREAMLIT SECRETS
# =====================================================================

import streamlit as st
from supabase import create_client, Client
import requests
from PIL import Image
import io
import re
import hashlib


# =====================================================================
# 1. CẤU HÌNH GIAO DIỆN STREAMLIT
# =====================================================================

st.set_page_config(
    page_title="Quản lý & Tìm kiếm mã hàng",
    page_icon="🔍",
    layout="wide"
)


# =====================================================================
# 2. 🔐 LẤY THÔNG TIN BẢO MẬT TỪ STREAMLIT SECRETS
# =====================================================================
# ⚠️ KHÔNG GHI URL / KEY / TOKEN TRỰC TIẾP Ở ĐÂY
#
# Các giá trị này phải được lưu trong:
# Streamlit App → Settings → Secrets
#
# GitHub chỉ chứa CODE.
# =====================================================================

try:

    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    HF_TOKEN = st.secrets["HF_TOKEN"]

except Exception as e:

    st.error(
        "❌ Không đọc được thông tin bảo mật từ Streamlit Secrets.\n\n"
        "Hãy kiểm tra các key sau trong phần Secrets:\n\n"
        "- SUPABASE_URL\n"
        "- SUPABASE_KEY\n"
        "- HF_TOKEN"
    )

    st.stop()


# =====================================================================
# 3. MODEL HUGGING FACE
# =====================================================================
# Có thể lưu HF_MODEL trong Secrets.
#
# Nếu chưa có HF_MODEL thì dùng model mặc định bên dưới.
#
# ⚠️ Model phải tương thích với vector đang lưu trong Supabase.
# =====================================================================

HF_MODEL = st.secrets.get(
    "HF_MODEL",
    "openai/clip-vit-base-patch32"
)


# =====================================================================
# 4. HUGGING FACE API URL
# =====================================================================
# Không chứa TOKEN trực tiếp.
# Token chỉ nằm trong Header bên dưới.
# =====================================================================

API_URL = (
    f"https://router.huggingface.co/"
    f"hf-inference/models/{HF_MODEL}"
)


# =====================================================================
# 5. HEADER API
# =====================================================================

headers = {
    "Authorization": f"Bearer {HF_TOKEN}",
    "Content-Type": "application/octet-stream",
    "User-Agent": (
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


# =====================================================================
# 6. KẾT NỐI SUPABASE
# =====================================================================

try:

    supabase: Client = create_client(
        SUPABASE_URL,
        SUPABASE_KEY
    )

except Exception as e:

    st.error(
        f"❌ Không thể kết nối Supabase:\n\n{e}"
    )

    st.stop()


# =====================================================================
# 7. DANH SÁCH DÒNG HÀNG
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
# 8. CHUẨN HÓA ẢNH
# =====================================================================

def normalize_image_bytes(file_bytes):

    try:

        image = Image.open(
            io.BytesIO(file_bytes)
        )

        # Chuyển tất cả về RGB
        if image.mode != "RGB":
            image = image.convert("RGB")

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
# 9. TẠO HASH ẢNH
# =====================================================================

def get_image_hash(image_bytes):

    return hashlib.sha256(
        image_bytes
    ).hexdigest()


# =====================================================================
# 10. LẤY EMBEDDING TỪ HUGGING FACE
# =====================================================================

def get_image_embedding_via_api(image_bytes):

    try:

        response = requests.post(
            API_URL,
            headers=headers,
            data=image_bytes,
            timeout=120
        )

    except requests.exceptions.Timeout:

        raise Exception(
            "Hugging Face timeout sau 120 giây."
        )

    except requests.exceptions.RequestException as e:

        raise Exception(
            f"Lỗi kết nối Hugging Face: {e}"
        )


    # ---------------------------------------------------------
    # KIỂM TRA HTTP
    # ---------------------------------------------------------

    if response.status_code != 200:

        error_text = response.text

        try:

            error_json = response.json()

            if isinstance(error_json, dict):

                error_text = (
                    error_json.get("error")
                    or error_json.get("message")
                    or error_text
                )

        except Exception:
            pass

        raise Exception(
            f"Hugging Face HTTP "
            f"{response.status_code}: "
            f"{error_text}"
        )


    # ---------------------------------------------------------
    # ĐỌC JSON
    # ---------------------------------------------------------

    try:

        result = response.json()

    except Exception:

        raise Exception(
            "Hugging Face trả về dữ liệu "
            "không phải JSON."
        )


    # ---------------------------------------------------------
    # TÌM VECTOR
    # ---------------------------------------------------------

    embedding = None


    # Dạng:
    # [0.123, 0.456, ...]
    if isinstance(result, list):

        if (
            len(result) > 0
            and isinstance(
                result[0],
                (int, float)
            )
        ):

            embedding = result


        # Dạng:
        # [[0.123, 0.456, ...]]
        elif (
            len(result) > 0
            and isinstance(
                result[0],
                list
            )
        ):

            embedding = result[0]


    # Dạng:
    # {"embedding": [...]}
    elif isinstance(result, dict):

        embedding = result.get(
            "embedding"
        )

        if embedding is None:

            embedding = result.get(
                "vector"
            )

        if embedding is None:

            embedding = result.get(
                "embeddings"
            )


    # ---------------------------------------------------------
    # KHÔNG CÓ VECTOR
    # ---------------------------------------------------------

    if embedding is None:

        raise Exception(
            "Không tìm thấy vector embedding "
            "trong response Hugging Face."
        )


    # ---------------------------------------------------------
    # CHUẨN HÓA FLOAT
    # ---------------------------------------------------------

    try:

        embedding = [
            float(x)
            for x in embedding
        ]

    except Exception:

        raise Exception(
            "Embedding chứa dữ liệu không hợp lệ."
        )


    if len(embedding) == 0:

        raise Exception(
            "Embedding rỗng."
        )


    return embedding


# =====================================================================
# 11. CACHE EMBEDDING
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
# 12. LẤY CONTENT TYPE
# =====================================================================

def get_content_type(filename):

    extension = (
        filename
        .lower()
        .rsplit(".", 1)[-1]
    )

    if extension == "png":
        return "image/png"

    if extension in [
        "jpg",
        "jpeg"
    ]:
        return "image/jpeg"

    return "application/octet-stream"


# =====================================================================
# 13. LÀM SẠCH TÊN FILE
# =====================================================================

def sanitize_filename(filename):

    filename = filename.strip()

    filename = re.sub(
        r"[^A-Za-z0-9._-]",
        "_",
        filename
    )

    return filename


# =====================================================================
# 14. TÁCH MÃ HÀNG
# =====================================================================

def extract_product_code(filename):

    filename_only = filename.rsplit(
        ".",
        1
    )[0]

    return filename_only.strip().upper()


# =====================================================================
# 15. UPLOAD ẢNH LÊN SUPABASE STORAGE
# =====================================================================

def upload_image_to_storage(
    file_bytes,
    filename
):

    bucket_name = "product-images"

    safe_filename = sanitize_filename(
        filename
    )

    try:

        content_type = get_content_type(
            safe_filename
        )

        storage = supabase.storage.from_(
            bucket_name
        )

        storage.upload(
            path=safe_filename,
            file=file_bytes,
            file_options={
                "content-type": content_type,
                "upsert": "true"
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
            f"Lỗi lưu trữ ảnh "
            f"{filename}: {e}"
        )


# =====================================================================
# 16. LƯU PRODUCT VÀO DATABASE
# =====================================================================

def save_product(
    product_code,
    image_url,
    category,
    embedding
):

    try:

        supabase.table(
            "products"
        ).upsert(
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
            on_conflict="product_code"
        ).execute()

    except Exception as e:

        raise Exception(
            f"Lỗi lưu mã hàng "
            f"{product_code}: {e}"
        )


# =====================================================================
# 17. CHIA TAB
# =====================================================================

tab1, tab2 = st.tabs(
    [
        "🔍 TÌM KIẾM MÃ HÀNG TƯƠNG ĐỒNG",
        "📦 LƯU KHO HÀNG LOẠT"
    ]
)


# =====================================================================
# TAB 1
# TÌM KIẾM MÃ HÀNG
# =====================================================================

with tab1:

    st.header(
        "🔍 Tìm Kiếm Mã Hàng Qua Ảnh Sketch"
    )


    col_search_1, col_search_2 = st.columns(
        2
    )


    # ---------------------------------------------------------------
    # INPUT
    # ---------------------------------------------------------------

    with col_search_1:

        search_category = st.selectbox(
            "Chọn dòng hàng cần tìm kiếm:",
            CATEGORY_OPTIONS,
            key="sb_search"
        )


        uploaded_sketch = st.file_uploader(
            "Tải lên ảnh Sketch cần tìm:",
            type=[
                "png",
                "jpg",
                "jpeg"
            ],
            key="fu_search"
        )


    # ---------------------------------------------------------------
    # PREVIEW + SEARCH
    # ---------------------------------------------------------------

    if uploaded_sketch is not None:

        with col_search_2:

            st.image(
                uploaded_sketch,
                caption="Ảnh Sketch của bạn",
                width=250
            )


            if st.button(
                "🚀 Bắt đầu quét mã tương đồng",
                type="primary",
                key="btn_search"
            ):

                with st.spinner(
                    "🤖 Hệ thống đang phân tích ảnh..."
                ):

                    try:

                        # ---------------------------------------------------
                        # ĐỌC ẢNH
                        # ---------------------------------------------------

                        raw_bytes = (
                            uploaded_sketch
                            .getvalue()
                        )


                        # ---------------------------------------------------
                        # CHUẨN HÓA
                        # ---------------------------------------------------

                        sketch_bytes = (
                            normalize_image_bytes(
                                raw_bytes
                            )
                        )


                        # ---------------------------------------------------
                        # HASH
                        # ---------------------------------------------------

                        image_hash = (
                            get_image_hash(
                                sketch_bytes
                            )
                        )


                        # ---------------------------------------------------
                        # EMBEDDING
                        # ---------------------------------------------------

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


                        # ---------------------------------------------------
                        # SEARCH SUPABASE
                        # ---------------------------------------------------

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


                        # ---------------------------------------------------
                        # HIỂN THỊ KẾT QUẢ
                        # ---------------------------------------------------

                        if response.data:

                            st.success(
                                "🎯 Kết quả tìm kiếm "
                                f"trong nhóm "
                                f"**{search_category}**:"
                            )


                            cols = st.columns(
                                len(
                                    response.data
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
                                        f"Mã: "
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
# LƯU KHO HÀNG LOẠT
# =====================================================================

with tab2:

    st.header(
        "📦 Đẩy Dữ Liệu Mã Hàng Hàng Loạt "
        "Lên Hệ Thống"
    )


    st.info(
        "💡 Cách đặt tên file:\n\n"
        "**Tên_file_ảnh = Mã_hàng**\n\n"
        "Ví dụ: `MS-1024.jpg` → `MS-1024`"
    )


    col_upload_1, col_upload_2 = st.columns(
        2
    )


    # ---------------------------------------------------------------
    # INPUT
    # ---------------------------------------------------------------

    with col_upload_1:

        upload_category = st.selectbox(
            "Phân loại dòng hàng khi lưu kho:",
            CATEGORY_OPTIONS,
            key="sb_upload"
        )


        uploaded_files = st.file_uploader(
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


    # ---------------------------------------------------------------
    # FILE ĐÃ CHỌN
    # ---------------------------------------------------------------

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

                progress_bar = st.progress(
                    0
                )

                status_text = st.empty()

                success_count = 0

                failed_count = 0

                failed_items = []


                # =====================================================
                # XỬ LÝ TỪNG FILE
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
                        # FILE BYTES
                        # -------------------------------------------------

                        raw_bytes = file.getvalue()


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
                        # UPLOAD STORAGE
                        # -------------------------------------------------

                        img_url = (
                            upload_image_to_storage(
                                image_bytes,
                                safe_filename
                            )
                        )


                        if not img_url:

                            raise Exception(
                                "Không lấy được "
                                "image URL."
                            )


                        # -------------------------------------------------
                        # IMAGE HASH
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
                                / len(uploaded_files)
                            ) * 100
                        )
                    )


                # =====================================================
                # KẾT QUẢ
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
                                f"Mã: {item['product_code']}\n\n"
                                f"Lỗi: {item['error']}"
                            )


                st.info(
                    f"📊 Tổng kết: "
                    f"✅ {success_count} thành công | "
                    f"❌ {failed_count} lỗi | "
                    f"📦 {len(uploaded_files)} file"
                )
