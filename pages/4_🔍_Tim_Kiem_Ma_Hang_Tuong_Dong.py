# =====================================================================
# 🔍 PRODUCT IMAGE SEARCH & BULK STORAGE
# VERSION V2.0 - SUPABASE + HUGGING FACE
# =====================================================================

import io
import re
import hashlib
import requests
import streamlit as st

from PIL import Image
from supabase import create_client, Client


# =====================================================================
# 1. CẤU HÌNH STREAMLIT
# =====================================================================

st.set_page_config(
    page_title="Quản lý & Tìm kiếm mã hàng",
    page_icon="🔍",
    layout="wide"
)


# =====================================================================
# 2. ĐỌC SECRETS
# =====================================================================

def get_secret(name, default=None):
    """
    Đọc biến từ Streamlit Secrets.
    """
    try:
        value = st.secrets.get(name, default)
        return value
    except Exception:
        return default


SUPABASE_URL = get_secret("https://ewqqodsfvlvnrzsylawy.supabase.co")
SUPABASE_KEY = get_secret("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImV3cXFvZHNmdmx2bnJ6c3lsYXd5Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzUxMTkyOTAsImV4cCI6MjA5MDY5NTI5MH0.BWPxOsyswBT5CLrZgluRC1F2x5EpU06oexUFyakGhyc")

HF_TOKEN = get_secret("HF_TOKEN")

# ---------------------------------------------------------
# Hugging Face model
#
# PHẢI dùng đúng model tạo embedding tương thích
# với cột embedding trong Supabase.
#
# Ví dụ:
# sentence-transformers/clip-ViT-B-32
# ---------------------------------------------------------

HF_MODEL = get_secret(
    "HF_MODEL",
    "openai/clip-vit-base-patch32"
)

HF_API_URL = (
    f"https://router.huggingface.co/hf-inference/models/{HF_MODEL}"
)


# =====================================================================
# 3. KIỂM TRA CẤU HÌNH
# =====================================================================

missing_config = []

if not SUPABASE_URL:
    missing_config.append("SUPABASE_URL")

if not SUPABASE_KEY:
    missing_config.append("SUPABASE_KEY")

if not HF_TOKEN:
    missing_config.append("HF_TOKEN")


if missing_config:
    st.error(
        "⚠️ Chưa cấu hình các biến sau trong Streamlit Secrets:\n\n"
        + "\n".join([f"- `{x}`" for x in missing_config])
    )
    st.stop()


# =====================================================================
# 4. KẾT NỐI SUPABASE
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
# 5. HEADER HUGGING FACE
# =====================================================================

HF_HEADERS = {
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
# 6. DANH SÁCH DÒNG HÀNG
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
# 7. CACHE EMBEDDING
# =====================================================================

@st.cache_data(
    ttl=3600,
    show_spinner=False
)
def get_cached_embedding(image_hash, image_bytes):
    """
    Cache embedding theo hash ảnh.

    Nếu người dùng quét lại cùng một ảnh
    sẽ không gọi Hugging Face lần nữa.
    """

    return get_image_embedding_via_api(image_bytes)


# =====================================================================
# 8. CHUẨN HÓA ẢNH
# =====================================================================

def normalize_image_bytes(file_bytes):
    """
    Đọc ảnh và chuyển về JPEG RGB.
    Giúp tránh lỗi PNG RGBA / CMYK / mode lạ.
    """

    try:

        image = Image.open(io.BytesIO(file_bytes))

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
    """
    SHA256 dùng để nhận diện ảnh.
    """

    return hashlib.sha256(
        image_bytes
    ).hexdigest()


# =====================================================================
# 10. LẤY EMBEDDING TỪ HUGGING FACE
# =====================================================================

def get_image_embedding_via_api(image_bytes):
    """
    Gửi ảnh tới Hugging Face để lấy vector embedding.

    LƯU Ý:
    Model phải hỗ trợ image embedding.
    """

    try:

        response = requests.post(
            HF_API_URL,
            headers=HF_HEADERS,
            data=image_bytes,
            timeout=120
        )

    except requests.exceptions.Timeout:

        raise Exception(
            "Hugging Face timeout > 120 giây."
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
            f"Hugging Face HTTP {response.status_code}: "
            f"{error_text}"
        )


    # ---------------------------------------------------------
    # PARSE JSON
    # ---------------------------------------------------------

    try:

        result = response.json()

    except Exception:

        raise Exception(
            "Hugging Face trả về dữ liệu "
            "không phải JSON."
        )


    # ---------------------------------------------------------
    # MODEL CÓ THỂ TRẢ VỀ NHIỀU DẠNG
    # ---------------------------------------------------------

    embedding = None


    # Dạng:
    # [0.123, 0.456, ...]
    if isinstance(result, list):

        if (
            len(result) > 0
            and isinstance(result[0], (int, float))
        ):
            embedding = result


        # Dạng:
        # [[0.123, 0.456, ...]]
        elif (
            len(result) > 0
            and isinstance(result[0], list)
        ):
            embedding = result[0]


    # Dạng:
    # {"embedding": [...]}
    elif isinstance(result, dict):

        embedding = result.get("embedding")

        if embedding is None:
            embedding = result.get("vector")

        if embedding is None:
            embedding = result.get("embeddings")


    # ---------------------------------------------------------
    # VALIDATE
    # ---------------------------------------------------------

    if embedding is None:

        raise Exception(
            "Không tìm thấy vector embedding trong "
            f"response của Hugging Face: {result}"
        )


    if not isinstance(embedding, list):

        raise Exception(
            "Embedding không phải dạng list."
        )


    # Chuyển toàn bộ sang float
    try:

        embedding = [
            float(x)
            for x in embedding
        ]

    except Exception:

        raise Exception(
            "Embedding chứa dữ liệu không phải số."
        )


    if len(embedding) == 0:

        raise Exception(
            "Embedding rỗng."
        )


    return embedding


# =====================================================================
# 11. LẤY MIME TYPE
# =====================================================================

def get_content_type(filename):

    extension = filename.lower().rsplit(".", 1)[-1]

    if extension == "png":
        return "image/png"

    if extension in ["jpg", "jpeg"]:
        return "image/jpeg"

    return "application/octet-stream"


# =====================================================================
# 12. LÀM SẠCH TÊN FILE
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
# 13. LẤY MÃ HÀNG TỪ TÊN FILE
# =====================================================================

def extract_product_code(filename):

    filename_only = filename.rsplit(
        ".",
        1
    )[0]

    product_code = filename_only.strip().upper()

    return product_code


# =====================================================================
# 14. UPLOAD ẢNH SUPABASE STORAGE
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

        # ---------------------------------------------------------
        # Upload
        # ---------------------------------------------------------

        storage.upload(
            path=safe_filename,
            file=file_bytes,
            file_options={
                "content-type": content_type,
                "upsert": "true"
            }
        )

        # ---------------------------------------------------------
        # Public URL
        # ---------------------------------------------------------

        public_url = storage.get_public_url(
            safe_filename
        )

        return public_url


    except Exception as e:

        raise Exception(
            f"Lỗi upload Storage: {e}"
        )


# =====================================================================
# 15. LƯU PRODUCT
# =====================================================================

def save_product(
    product_code,
    image_url,
    category,
    embedding
):

    try:

        payload = {
            "product_code": product_code,
            "image_url": image_url,
            "category": category,
            "embedding": embedding
        }

        result = (
            supabase
            .table("products")
            .upsert(
                payload,
                on_conflict="product_code"
            )
            .execute()
        )

        return result


    except Exception as e:

        raise Exception(
            f"Lỗi lưu products: {e}"
        )


# =====================================================================
# 16. TAB
# =====================================================================

tab1, tab2 = st.tabs(
    [
        "🔍 TÌM KIẾM MÃ HÀNG TƯƠNG ĐỒNG",
        "📦 LƯU KHO HÀNG LOẠT"
    ]
)


# =====================================================================
# TAB 1
# TÌM KIẾM
# =====================================================================

with tab1:

    st.header(
        "🔍 Tìm Kiếm Mã Hàng Qua Ảnh Sketch"
    )

    col_search_1, col_search_2 = st.columns(
        2
    )


    # -------------------------------------------------------------
    # INPUT
    # -------------------------------------------------------------

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


    # -------------------------------------------------------------
    # PREVIEW
    # -------------------------------------------------------------

    if uploaded_sketch is not None:

        with col_search_2:

            st.image(
                uploaded_sketch,
                caption="Ảnh Sketch của bạn",
                width=250
            )


            # -----------------------------------------------------
            # SEARCH BUTTON
            # -----------------------------------------------------

            if st.button(
                "🚀 Bắt đầu quét mã tương đồng",
                type="primary",
                key="btn_search"
            ):

                with st.spinner(
                    "🤖 AI đang phân tích ảnh..."
                ):

                    try:

                        # -------------------------------------------------
                        # Đọc ảnh
                        # -------------------------------------------------

                        raw_bytes = (
                            uploaded_sketch
                            .getvalue()
                        )


                        # -------------------------------------------------
                        # Normalize
                        # -------------------------------------------------

                        sketch_bytes = (
                            normalize_image_bytes(
                                raw_bytes
                            )
                        )


                        # -------------------------------------------------
                        # Hash
                        # -------------------------------------------------

                        image_hash = (
                            get_image_hash(
                                sketch_bytes
                            )
                        )


                        # -------------------------------------------------
                        # Embedding
                        # -------------------------------------------------

                        sketch_embedding = (
                            get_cached_embedding(
                                image_hash,
                                sketch_bytes
                            )
                        )


                        if not sketch_embedding:

                            raise Exception(
                                "AI không tạo được embedding."
                            )


                        st.caption(
                            f"Vector AI: "
                            f"{len(sketch_embedding)} dimensions"
                        )


                        # -------------------------------------------------
                        # RPC SUPABASE
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
                        # KẾT QUẢ
                        # -------------------------------------------------

                        if response.data:

                            st.success(
                                "🎯 Kết quả tìm kiếm "
                                f"trong nhóm "
                                f"**{search_category}**:"
                            )


                            result_count = len(
                                response.data
                            )

                            cols = st.columns(
                                result_count
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
                                        label="Độ giống nhau",
                                        value=(
                                            f"{similarity * 100:.2f}%"
                                        )
                                    )


                                    product_code = (
                                        item.get(
                                            "product_code",
                                            "N/A"
                                        )
                                    )


                                    st.subheader(
                                        f"Mã: {product_code}"
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

                                    else:

                                        st.warning(
                                            "Không có ảnh."
                                        )


                        else:

                            st.warning(
                                "⚠️ Không tìm thấy sản phẩm "
                                "tương đồng trong nhóm "
                                f"**{search_category}**."
                            )


                    except Exception as e:

                        st.error(
                            "❌ Lỗi hệ thống khi tìm kiếm:"
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
        "`Tên_file_ảnh = Mã_hàng`\n\n"
        "Ví dụ: `MS-1024.jpg` → mã hàng `MS-1024`"
    )


    col_upload_1, col_upload_2 = st.columns(
        2
    )


    # -------------------------------------------------------------
    # INPUT
    # -------------------------------------------------------------

    with col_upload_1:

        upload_category = st.selectbox(
            "Phân loại dòng hàng khi lưu kho:",
            CATEGORY_OPTIONS,
            key="sb_upload"
        )


        uploaded_files = st.file_uploader(
            "Chọn nhiều ảnh sản phẩm gốc / ảnh mẫu "
            "để lưu kho:",
            type=[
                "png",
                "jpg",
                "jpeg"
            ],
            accept_multiple_files=True,
            key="fu_bulk"
        )


    # -------------------------------------------------------------
    # BULK FILES
    # -------------------------------------------------------------

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
                # LOOP FILE
                # =====================================================

                for index, file in enumerate(
                    uploaded_files
                ):

                    product_code = extract_product_code(
                        file.name
                    )


                    status_text.text(
                        f"⏳ Đang xử lý "
                        f"{index + 1}/"
                        f"{len(uploaded_files)}: "
                        f"{product_code}"
                    )


                    try:

                        # -------------------------------------------------
                        # Đọc file
                        # -------------------------------------------------

                        raw_bytes = file.getvalue()


                        if not raw_bytes:

                            raise Exception(
                                "File ảnh rỗng."
                            )


                        # -------------------------------------------------
                        # Normalize
                        # -------------------------------------------------

                        image_bytes = (
                            normalize_image_bytes(
                                raw_bytes
                            )
                        )


                        # -------------------------------------------------
                        # Tên file
                        # -------------------------------------------------

                        safe_filename = (
                            sanitize_filename(
                                file.name
                            )
                        )


                        # -------------------------------------------------
                        # Upload Storage
                        # -------------------------------------------------

                        img_url = (
                            upload_image_to_storage(
                                image_bytes,
                                safe_filename
                            )
                        )


                        if not img_url:

                            raise Exception(
                                "Không nhận được image URL."
                            )


                        # -------------------------------------------------
                        # Hash
                        # -------------------------------------------------

                        image_hash = (
                            get_image_hash(
                                image_bytes
                            )
                        )


                        # -------------------------------------------------
                        # Embedding
                        # -------------------------------------------------

                        embedding_data = (
                            get_cached_embedding(
                                image_hash,
                                image_bytes
                            )
                        )


                        if not embedding_data:

                            raise Exception(
                                "Không tạo được embedding."
                            )


                        # -------------------------------------------------
                        # Lưu DB
                        # -------------------------------------------------

                        save_product(
                            product_code=product_code,
                            image_url=img_url,
                            category=upload_category,
                            embedding=embedding_data
                        )


                        success_count += 1


                    except Exception as e:

                        failed_count += 1

                        failed_items.append(
                            {
                                "file": file.name,
                                "product_code":
                                    product_code,
                                "error": str(e)
                            }
                        )


                    # -------------------------------------------------
                    # Progress
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
                # KẾT THÚC
                # =====================================================

                status_text.empty()


                if success_count:

                    st.success(
                        f"🎉 Hoàn thành! "
                        f"Đã lưu thành công "
                        f"**{success_count}/"
                        f"{len(uploaded_files)}** "
                        f"mã hàng."
                    )


                if failed_count:

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
                                f"**{item['file']}** "
                                f"→ {item['error']}"
                            )


                st.info(
                    f"📊 Tổng kết: "
                    f"✅ {success_count} thành công | "
                    f"❌ {failed_count} lỗi | "
                    f"📦 Tổng {len(uploaded_files)} file"
                )
