# =====================================================================
# 🔍 AI TÌM KIẾM MÃ HÀNG TƯƠNG ĐỒNG
# VERSION V4.5
#
# MASTER VERSION
#
# ENGINE:
#   - Gemini Vision
#   - Gemini Embedding 2
#   - Supabase
#   - pgvector
#
# FIX V4.5:
#   1. FORCE EMBEDDING = 768 DIMENSIONS
#   2. KHÔNG BAO GIỜ tạo vector 3072 fallback
#   3. IMAGE UPLOAD -> IMAGE EMBEDDING 768
#   4. IMAGE SEARCH -> IMAGE EMBEDDING 768
#   5. DATABASE -> 768
#   6. RPC SEARCH -> 768
#   7. AI TỰ NHẬN DIỆN CATEGORY
#   8. KHÔNG CÒN SELECTBOX CHỌN DÒNG HÀNG
#   9. CATEGORY CHỈ BOOST, KHÔNG KHÓA SEARCH
#  10. RETRY GEMINI 429 / 503
#  11. DELAY GIỮA CÁC FILE
#  12. KIỂM TRA DIMENSION TRƯỚC DATABASE
#  13. KIỂM TRA DIMENSION TRƯỚC VECTOR SEARCH
#  14. KHÔNG DÙNG HUGGING FACE
#  15. KHÔNG DÙNG CLIP
#  16. KHÔNG DÙNG TORCH
#  17. KHÔNG DÙNG TORCHVISION
# =====================================================================


# =====================================================================
# 0. IMPORT
# =====================================================================

import streamlit as st
import io
import os
import json
import re
import hashlib
import math
import time

from typing import Any, Dict, List, Optional


# =====================================================================
# 1. PAGE CONFIG
# =====================================================================

st.set_page_config(
    page_title="AI Tìm Kiếm Mã Hàng Tương Đồng",
    page_icon="🔍",
    layout="wide"
)


# =====================================================================
# 2. OPTIONAL IMPORT
# =====================================================================

try:
    from supabase import create_client, Client
except Exception as e:
    st.error(
        "❌ Chưa cài thư viện Supabase.\n\n"
        "Thêm vào requirements.txt:\n\n"
        "supabase"
    )
    st.exception(e)
    st.stop()


try:
    from google import genai
    from google.genai import types
except Exception as e:
    st.error(
        "❌ Chưa cài thư viện Google GenAI.\n\n"
        "Thêm vào requirements.txt:\n\n"
        "google-genai"
    )
    st.exception(e)
    st.stop()


# =====================================================================
# 3. CONSTANTS
# =====================================================================

APP_VERSION = "V4.5"

BUCKET_NAME = "product-images"

PRODUCT_TABLE = "products"

# ---------------------------------------------------------
# Gemini Vision & Embedding
# ---------------------------------------------------------

VISION_MODEL = "gemini-2.5-flash"

EMBEDDING_MODEL = "gemini-embedding-2"

# ---------------------------------------------------------
# CRITICAL: DATABASE HIỆN TẠI CỦA USER = 768
# ---------------------------------------------------------

EMBEDDING_DIMENSION = 768

# ---------------------------------------------------------
# Search Configuration
# ---------------------------------------------------------

SEARCH_COUNT = 12

MIN_SIMILARITY = 0.20

# ---------------------------------------------------------
# Retry Configuration
# ---------------------------------------------------------

MAX_GEMINI_RETRIES = 3

RETRY_DELAY_SECONDS = 3.0

# ---------------------------------------------------------
# Bulk Upload Delay
# ---------------------------------------------------------

BULK_DELAY_SECONDS = 1.5


# =====================================================================
# 4. CATEGORY MASTER
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
# 5. CATEGORY ALIAS
# =====================================================================

CATEGORY_ALIAS = {
    "JUMPSUIT": "Áo liền quần",
    "ONE PIECE": "Áo liền quần",
    "ONE-PIECE": "Áo liền quần",
    "ROMPER": "Áo liền quần",

    "OVERALL": "Quần yếm",
    "OVERALLS": "Quần yếm",
    "BIB OVERALL": "Quần yếm",
    "DUNGAREE": "Quần yếm",
    "DUNGAREES": "Quần yếm",

    "CARGO": "Quần túi hộp",
    "CARGO PANTS": "Quần túi hộp",
    "CARGO TROUSERS": "Quần túi hộp",
    "CARGO TROUSER": "Quần túi hộp",

    "JEANS": "Quần jean",
    "DENIM JEANS": "Quần jean",
    "DENIM PANTS": "Quần jean",

    "JOGGER": "Quần jogger",
    "JOGGERS": "Quần jogger",
    "JOGGER PANTS": "Quần jogger",

    "SHORT": "Quần short",
    "SHORTS": "Quần short",

    "PANTS": "Quần dài",
    "TROUSERS": "Quần dài",
    "TROUSER": "Quần dài",
    "LONG PANTS": "Quần dài",

    "SHIRT": "Áo",
    "TOP": "Áo",

    "T-SHIRT": "T-shirt",
    "TSHIRT": "T-shirt",
    "TEE": "T-shirt",

    "POLO SHIRT": "Polo",
    "POLO": "Polo",

    "HOODIE": "Hoodie",

    "JACKET": "Jacket",
    "BOMBER": "Jacket",
    "OUTERWEAR": "Jacket",

    "SKIRT": "Skirt",

    "DRESS": "Dress"
}


# =====================================================================
# 6. SECRET HELPERS
# =====================================================================

def _safe_secret_get(container, key):
    try:
        if container is None:
            return None
        if key in container:
            value = container[key]
            if value is not None:
                value = str(value).strip()
                if value:
                    return value
    except Exception:
        pass
    return None


def _recursive_find_secret(obj, target_names):
    if obj is None:
        return None
    try:
        if hasattr(obj, "items"):
            for key, value in obj.items():
                key_upper = str(key).upper().strip()
                if key_upper in target_names:
                    if value is not None:
                        value = str(value).strip()
                        if value:
                            return value
                result = _recursive_find_secret(value, target_names)
                if result:
                    return result
    except Exception:
        pass
    return None


def get_secret(*names):
    normalized = {str(x).upper().strip() for x in names}

    try:
        for name in normalized:
            value = _safe_secret_get(st.secrets, name)
            if value:
                return value

        value = _recursive_find_secret(st.secrets, normalized)
        if value:
            return value
    except Exception:
        pass

    for name in normalized:
        value = os.environ.get(name)
        if value:
            value = value.strip()
            if value:
                return value

    return None


# =====================================================================
# 7. LOAD SECRETS
# =====================================================================

SUPABASE_URL = get_secret("SUPABASE_URL", "supabase_url")
SUPABASE_KEY = get_secret("SUPABASE_KEY", "SUPABASE_ANON_KEY", "supabase_key", "anon_key")
GEMINI_API_KEY = get_secret("GEMINI_API_KEY", "GOOGLE_API_KEY", "GEMINI_KEY", "gemini_api_key", "api_key")


# =====================================================================
# 8. SECRET VALIDATION
# =====================================================================

missing_secrets = []

if not SUPABASE_URL:
    missing_secrets.append("SUPABASE_URL")

if not SUPABASE_KEY:
    missing_secrets.append("SUPABASE_KEY")

if not GEMINI_API_KEY:
    missing_secrets.append("GEMINI_API_KEY")


if missing_secrets:
    st.error("❌ Không đọc được thông tin bảo mật.")
    st.markdown("### Key còn thiếu:")
    for key in missing_secrets:
        st.code(key)
    st.info(
        """
Streamlit Secrets có thể khai báo:

SUPABASE_URL = "https://xxxxx.supabase.co"
SUPABASE_KEY = "..."
GEMINI_API_KEY = "..."
"""
    )
    st.stop()


# =====================================================================
# 9. CREATE SUPABASE CLIENT
# =====================================================================

try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error("❌ Không khởi tạo được Supabase.")
    st.exception(e)
    st.stop()


# =====================================================================
# 10. CREATE GEMINI CLIENT
# =====================================================================

try:
    gemini_client = genai.Client(api_key=GEMINI_API_KEY)
except Exception as e:
    st.error("❌ Không khởi tạo được Gemini.")
    st.exception(e)
    st.stop()


# =====================================================================
# 11. SESSION STATE
# =====================================================================

if "search_file" not in st.session_state:
    st.session_state.search_file = None

if "search_result" not in st.session_state:
    st.session_state.search_result = None

if "search_ai_result" not in st.session_state:
    st.session_state.search_ai_result = None

if "pending_upload_files" not in st.session_state:
    st.session_state.pending_upload_files = []

if "last_upload_result" not in st.session_state:
    st.session_state.last_upload_result = None


# =====================================================================
# 12. IMAGE MIME
# =====================================================================

def get_mime_type(filename):
    ext = str(filename).lower().rsplit(".", 1)[-1]
    if ext == "png":
        return "image/png"
    if ext in ["jpg", "jpeg"]:
        return "image/jpeg"
    if ext == "webp":
        return "image/webp"
    return "image/jpeg"


# =====================================================================
# 13. NORMALIZE IMAGE
# =====================================================================

def normalize_image_bytes(image_bytes):
    try:
        from PIL import Image
        image = Image.open(io.BytesIO(image_bytes))
        image = image.convert("RGB")
        output = io.BytesIO()
        image.save(output, format="JPEG", quality=92)
        return output.getvalue()
    except Exception:
        return image_bytes


# =====================================================================
# 14. FILE HASH
# =====================================================================

def calculate_file_hash(image_bytes):
    return hashlib.sha256(image_bytes).hexdigest()


# =====================================================================
# 15. CATEGORY NORMALIZER
# =====================================================================

def normalize_category(category):
    if category is None:
        return "Quần dài"

    value = str(category).strip()
    upper = value.upper().strip()

    if upper in CATEGORY_ALIAS:
        return CATEGORY_ALIAS[upper]

    for valid in CATEGORY_OPTIONS:
        if value.lower() == valid.lower():
            return valid

    return "Quần dài"


# =====================================================================
# 16. GARMENT PROMPT
# =====================================================================

GARMENT_PROMPT = """
You are an expert apparel technical designer and garment recognition AI.
Analyze the garment shown in the image.
This system is used for commercial apparel similarity search.
Identify the actual garment construction, not only superficial appearance.

AVAILABLE CATEGORIES:
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

Return ONLY JSON.
"""


# =====================================================================
# 17. BOOLEAN HELPER
# =====================================================================

def bool_value(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower().strip() in ["true", "yes", "1", "y"]
    if isinstance(value, (int, float)):
        return bool(value)
    return False


# =====================================================================
# 18. NORMALIZE GARMENT RESULT
# =====================================================================

def normalize_garment_result(result):
    if not isinstance(result, dict):
        result = {}

    category = normalize_category(result.get("category", "Quần dài"))
    one_piece = bool_value(result.get("one_piece", False))
    bib = bool_value(result.get("bib", False))
    shoulder_straps = bool_value(result.get("shoulder_straps", False))
    cargo_pockets = bool_value(result.get("cargo_pockets", False))
    denim = bool_value(result.get("denim", False))
    jogger_cuffs = bool_value(result.get("jogger_cuffs", False))
    hood = bool_value(result.get("hood", False))

    if one_piece:
        category = "Quần yếm" if (bib and shoulder_straps) else "Áo liền quần"
    elif bib and shoulder_straps:
        category = "Quần yếm"
    elif category == "Quần túi hộp" and not cargo_pockets:
        category = "Quần dài"

    if not one_piece and not bib and denim and category in ["Quần dài", "Quần short"]:
        category = "Quần jean"

    if not one_piece and not bib and jogger_cuffs and category == "Quần dài":
        category = "Quần jogger"

    try:
        confidence = float(result.get("confidence", 0))
    except Exception:
        confidence = 0
    confidence = max(0, min(100, confidence))

    return {
        "category": category,
        "confidence": confidence,
        "one_piece": one_piece,
        "bib": bib,
        "shoulder_straps": shoulder_straps,
        "cargo_pockets": cargo_pockets,
        "denim": denim,
        "jogger_cuffs": jogger_cuffs,
        "hood": hood,
        "sleeve": str(result.get("sleeve", "")),
        "collar": str(result.get("collar", "")),
        "silhouette": str(result.get("silhouette", "")),
        "length": str(result.get("length", "")),
        "reason": str(result.get("reason", ""))
    }


# =====================================================================
# 19. GEMINI VISION
# =====================================================================

def analyze_garment_with_gemini(image_bytes):
    image_bytes = normalize_image_bytes(image_bytes)
    last_error = None

    for attempt in range(MAX_GEMINI_RETRIES):
        try:
            response = gemini_client.models.generate_content(
                model=VISION_MODEL,
                contents=[
                    types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
                    GARMENT_PROMPT
                ],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema={
                        "type": "object",
                        "properties": {
                            "category": {"type": "string"},
                            "confidence": {"type": "number"},
                            "one_piece": {"type": "boolean"},
                            "bib": {"type": "boolean"},
                            "shoulder_straps": {"type": "boolean"},
                            "cargo_pockets": {"type": "boolean"},
                            "denim": {"type": "boolean"},
                            "jogger_cuffs": {"type": "boolean"},
                            "sleeve": {"type": "string"},
                            "collar": {"type": "string"},
                            "hood": {"type": "boolean"},
                            "silhouette": {"type": "string"},
                            "length": {"type": "string"},
                            "reason": {"type": "string"}
                        },
                        "required": [
                            "category", "confidence", "one_piece", "bib", 
                            "shoulder_straps", "cargo_pockets", "denim", 
                            "jogger_cuffs", "hood", "reason"
                        ]
                    },
                    temperature=0.0
                )
            )

            text = getattr(response, "text", None)
            if not text:
                raise Exception("Gemini không trả về text.")

            result = json.loads(text)
            return normalize_garment_result(result)

        except Exception as e:
            last_error = e
            if attempt < MAX_GEMINI_RETRIES - 1:
                time.sleep(RETRY_DELAY_SECONDS)

    raise Exception(f"Gemini Vision lỗi sau {MAX_GEMINI_RETRIES} lần thử: {last_error}")


# =====================================================================
# 20. GEMINI IMAGE EMBEDDING
# =====================================================================

def get_image_embedding(image_bytes):
    image_bytes = normalize_image_bytes(image_bytes)
    last_error = None

    for attempt in range(MAX_GEMINI_RETRIES):
        try:
            response = gemini_client.models.embed_content(
                model=EMBEDDING_MODEL,
                contents=[
                    types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")
                ],
                config=types.EmbedContentConfig(
                    output_dimensionality=768
                )
            )

            if not response.embeddings or not response.embeddings[0].values:
                raise Exception("Gemini không trả về embedding hợp lệ.")

            values = [float(x) for x in response.embeddings[0].values]

            if len(values) != EMBEDDING_DIMENSION:
                raise Exception(
                    f"SAI DIMENSION: Gemini trả về {len(values)} dimensions, hệ thống yêu cầu {EMBEDDING_DIMENSION}."
                )

            norm = math.sqrt(sum(x * x for x in values))
            if norm > 0:
                values = [x / norm for x in values]

            return values

        except Exception as e:
            last_error = e
            if attempt < MAX_GEMINI_RETRIES - 1:
                time.sleep(RETRY_DELAY_SECONDS)

    raise Exception(f"Gemini Image Embedding lỗi sau {MAX_GEMINI_RETRIES} lần thử: {last_error}")


# =====================================================================
# 21. STORAGE UPLOAD
# =====================================================================

def upload_image_to_storage(image_bytes, filename):
    safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", filename)
    file_hash = hashlib.sha256(image_bytes).hexdigest()[:12]
    
    parts = safe_name.rsplit(".", 1)
    base_name = parts[0]
    ext = parts[1] if len(parts) > 1 else "jpg"

    path = f"{base_name}_{file_hash}.{ext}"
    mime_type = get_mime_type(filename)

    try:
        supabase.storage.from_(BUCKET_NAME).upload(
            path=path,
            file=image_bytes,
            file_options={"content-type": mime_type, "upsert": "true", "cache-control": "3600"}
        )
    except Exception as e:
        error_text = str(e)
        if any(err in error_text.lower() for err in ["row-level security", "unauthorized", "403"]):
            raise Exception(f"Supabase Storage RLS Error: Bucket {BUCKET_NAME} bị chặn truy cập.")

        try:
            supabase.storage.from_(BUCKET_NAME).update(
                path=path,
                file=image_bytes,
                file_options={"content-type": mime_type, "upsert": "true", "cache-control": "3600"}
            )
        except Exception:
            raise Exception(f"Supabase Storage lỗi: {error_text}")

    try:
        public_url = supabase.storage.from_(BUCKET_NAME).get_public_url(path)
        if isinstance(public_url, dict):
            return public_url.get("publicUrl") or public_url.get("public_url")
        return public_url
    except Exception as e:
        raise Exception(f"Không lấy được Public URL: {str(e)}")


# =====================================================================
# 22. SAVE PRODUCT
# =====================================================================

def save_product(product_code, image_url, category, ai_category, ai_result, embedding, filename):
    if not isinstance(embedding, list) or len(embedding) != 768:
        raise Exception(f"Database BLOCK: Embedding phải chuẩn 768 dimensions.")

    row = {
        "product_code": product_code,
        "image_url": image_url,
        "category": category,
        "ai_category": ai_category,
        "ai_result": ai_result,
        "embedding": embedding,
        "filename": filename
    }

    try:
        response = supabase.table(PRODUCT_TABLE).upsert(row, on_conflict="product_code").execute()
        return response
    except Exception as e:
        raise Exception(f"Lỗi lưu Database: {str(e)}")


# =====================================================================
# 23. VECTOR SEARCH VIA SUPABASE RPC
# =====================================================================

def search_similar_products(
    query_embedding: List[float],
    match_count: int = SEARCH_COUNT,
    similarity_threshold: float = MIN_SIMILARITY
) -> List[Dict[str, Any]]:
    if len(query_embedding) != EMBEDDING_DIMENSION:
        raise Exception(f"Lỗi Vector Dimension: Cần 768 chiều, nhận được {len(query_embedding)} chiều.")

    rpc_params = {
        "query_embedding": query_embedding,
        "match_threshold": similarity_threshold,
        "match_count": match_count
    }

    try:
        response = supabase.rpc("match_products_v4", rpc_params).execute()
        return response.data if response.data else []
    except Exception as e:
        raise Exception(f"Lỗi thực thi RPC Vector Search: {str(e)}")


# =====================================================================
# 24. STREAMLIT UI/UX LOGIC
# =====================================================================

st.title(f"🔍 AI Tìm Kiếm Mã Hàng Tương Đồng ({APP_VERSION})")
st.caption("Engine: Gemini Vision | Gemini Embedding 2 (768 Dimensions) | Supabase pgvector")

tab_search, tab_upload = st.tabs(["🔎 Tìm Kiếm Mã Hàng", "📤 Tải Lên Dữ Liệu"])

# ---------------------------------------------------------------------
# TAB 1: TÌM KIẾM
# ---------------------------------------------------------------------
with tab_search:
    st.subheader("Tìm sản phẩm tương đồng qua Hình Ảnh")
    uploaded_search_file = st.file_uploader(
        "Tải lên ảnh mã hàng cần tìm kiếm:",
        type=["jpg", "jpeg", "png", "webp"],
        key="search_uploader"
    )

    if uploaded_search_file:
        search_bytes = uploaded_search_file.getvalue()
        
        col_img, col_info = st.columns([1, 2])
        with col_img:
            st.image(search_bytes, caption="Ảnh tìm kiếm", use_container_width=True)

        with col_info:
            if st.button("🚀 Bắt đầu Phân Tích & Tìm Kiếm", type="primary"):
                with st.spinner("AI đang nhận diện dòng hàng & tạo Vector Embedding (768)..."):
                    try:
                        # 1. AI Vision Phân tích dòng hàng
                        ai_info = analyze_garment_with_gemini(search_bytes)
                        st.session_state.search_ai_result = ai_info

                        # 2. Tạo Image Embedding 768
                        query_emb = get_image_embedding(search_bytes)

                        # 3. Vector Search
                        results = search_similar_products(query_emb)
                        st.session_state.search_result = results

                        st.success(f"Phân tích thành công! Nhận diện Category: **{ai_info['category']}**")

                    except Exception as err:
                        st.error(f"❌ Lỗi tìm kiếm: {str(err)}")

    if st.session_state.search_ai_result:
        ai_res = st.session_state.search_ai_result
        with st.expander("📊 Chi tiết Phân tích AI", expanded=False):
            st.json(ai_res)

    if st.session_state.search_result is not None:
        st.divider()
        st.subheader("Kết quả Mã Hàng Tương Đồng")
        results = st.session_state.search_result

        if not results:
            st.warning("Không tìm thấy mã hàng tương đồng đáp ứng độ chính xác tối thiểu.")
        else:
            cols = st.columns(4)
            for idx, item in enumerate(results):
                with cols[idx % 4]:
                    st.image(item.get("image_url", ""), use_container_width=True)
                    st.markdown(f"**Mã SP:** `{item.get('product_code', 'N/A')}`")
                    st.markdown(f"**Loại:** {item.get('category', 'N/A')}")
                    sim = item.get("similarity", 0) * 100
                    st.progress(min(1.0, item.get("similarity", 0)))
                    st.caption(f"Độ tương đồng: **{sim:.2f}%**")


# ---------------------------------------------------------------------
# TAB 2: BULK UPLOAD DỮ LIỆU
# ---------------------------------------------------------------------
with tab_upload:
    st.subheader("Tải lên danh mục Mã Hàng mới")
    upload_files = st.file_uploader(
        "Chọn danh sách ảnh sản phẩm (Tên file sẽ làm Mã Sản Phẩm):",
        type=["jpg", "jpeg", "png", "webp"],
        accept_multiple_files=True,
        key="bulk_uploader"
    )

    if upload_files and st.button(f"📥 Xử lý & Lưu {len(upload_files)} sản phẩm", type="primary"):
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        success_count = 0
        error_count = 0

        for idx, file in enumerate(upload_files):
            filename = file.name
            product_code = filename.rsplit(".", 1)[0].upper().strip()
            status_text.text(f"[{idx+1}/{len(upload_files)}] Đang xử lý: {product_code}...")

            try:
                img_bytes = file.getvalue()

                # 1. Upload Storage
                img_url = upload_image_to_storage(img_bytes, filename)

                # 2. Gemini Vision
                ai_info = analyze_garment_with_gemini(img_bytes)

                # 3. Gemini Embedding (768)
                emb = get_image_embedding(img_bytes)

                # 4. Save Database
                save_product(
                    product_code=product_code,
                    image_url=img_url,
                    category=ai_info["category"],
                    ai_category=ai_info["category"],
                    ai_result=ai_info,
                    embedding=emb,
                    filename=filename
                )
                success_count += 1

            except Exception as e:
                st.error(f"❌ Lỗi file {filename}: {str(e)}")
                error_count += 1

            # Cập nhật progress bar
            progress_bar.progress((idx + 1) / len(upload_files))
            time.sleep(BULK_DELAY_SECONDS)

        status_text.empty()
        st.success(f"🎉 Hoàn tất! Thành công: **{success_count}**, Lỗi: **{error_count}**")
