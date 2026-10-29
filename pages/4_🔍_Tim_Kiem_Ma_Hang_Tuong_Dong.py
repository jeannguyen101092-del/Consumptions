# =====================================================================
# 🔍 AI TÌM KIẾM MÃ HÀNG TƯƠNG ĐỒNG — V4.6 QUOTA-SAVER
#
# Giữ nguyên:
#   - Gemini Vision nhận diện garment
#   - Gemini Embedding 2, vector 768
#   - Supabase Storage bucket product-images
#   - Supabase table products
#   - RPC match_products_v4
#   - Hai tab Tìm kiếm / Nạp kho hàng loạt
#
# V4.6:
#   1. Search lấy tối đa 40 ứng viên từ vector search.
#   2. Python xếp hạng; category chỉ boost, không khóa kết quả.
#   3. Không gọi Gemini Vision lần hai trong tìm kiếm thông thường.
#   4. Phân tích khác biệt chỉ chạy khi người dùng chủ động bấm nút.
#   5. Phân tích chi tiết gửi ảnh truy vấn + tối đa 3 ảnh kết quả
#      trong MỘT lần gọi Gemini Vision.
#   6. Embedding luôn kiểm tra 768 chiều; không fallback vector giả.
#   7. Giữ queue nạp kho và báo cáo kết quả.
# =====================================================================

import streamlit as st
import io
import os
import json
import re
import hashlib
import math
import time
import requests
from typing import Any, Dict, List, Optional

st.set_page_config(
    page_title="AI Tìm Kiếm Mã Hàng Tương Đồng",
    page_icon="🔍",
    layout="wide"
)

# =====================================================================
# 1. OPTIONAL IMPORTS
# =====================================================================

try:
    from supabase import create_client, Client
except Exception as e:
    st.error(
        "❌ Chưa cài thư viện Supabase.\n\n"
        "Thêm vào requirements.txt: `supabase`"
    )
    st.exception(e)
    st.stop()

try:
    from google import genai
    from google.genai import types
except Exception as e:
    st.error(
        "❌ Chưa cài thư viện Google GenAI.\n\n"
        "Thêm vào requirements.txt: `google-genai`"
    )
    st.exception(e)
    st.stop()

# =====================================================================
# 2. CONSTANTS
# =====================================================================

APP_VERSION = "V4.6 QUOTA-SAVER"
BUCKET_NAME = "product-images"
PRODUCT_TABLE = "products"

VISION_MODEL = "gemini-3.6-flash"
EMBEDDING_MODEL = "gemini-embedding-2"
EMBEDDING_DIMENSION = 768

# RPC sẽ lấy nhiều ứng viên hơn số thẻ hiển thị.
CANDIDATE_COUNT = 40
DISPLAY_COUNT = 8
MIN_SIMILARITY = 0.20

# Phân tích khác biệt là tùy chọn. Tối đa 3 ảnh kết quả + ảnh truy vấn.
DETAIL_COMPARE_COUNT = 3
MAX_GEMINI_RETRIES = 3
RETRY_DELAY_SECONDS = 5
BULK_DELAY_SECONDS = 4.5
HTTP_TIMEOUT_SECONDS = 15

CATEGORY_OPTIONS = [
    "Áo liền quần", "Quần yếm", "Quần túi hộp", "Quần jean",
    "Quần jogger", "Quần short", "Quần dài", "Jacket", "Áo",
    "T-shirt", "Polo", "Hoodie", "Skirt", "Dress"
]

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
# 3. SECRETS
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
                if str(key).upper().strip() in target_names:
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
        if value and value.strip():
            return value.strip()
    return None


SUPABASE_URL = get_secret("SUPABASE_URL", "supabase_url")
SUPABASE_KEY = get_secret(
    "SUPABASE_KEY", "SUPABASE_ANON_KEY", "supabase_key", "anon_key"
)
GEMINI_API_KEY = get_secret(
    "GEMINI_API_KEY", "GOOGLE_API_KEY", "GEMINI_KEY",
    "gemini_api_key", "api_key"
)

missing_secrets = []
if not SUPABASE_URL:
    missing_secrets.append("SUPABASE_URL")
if not SUPABASE_KEY:
    missing_secrets.append("SUPABASE_KEY")
if not GEMINI_API_KEY:
    missing_secrets.append("GEMINI_API_KEY")

if missing_secrets:
    st.error("❌ Không đọc được thông tin bảo mật.")
    st.markdown("### Key còn thiếu")
    for key in missing_secrets:
        st.code(key)
    st.info(
        'Streamlit Secrets có thể khai báo:\n\n'
        'SUPABASE_URL = "https://xxxxx.supabase.co"\n\n'
        'SUPABASE_KEY = "..."\n\n'
        'GEMINI_API_KEY = "..."'
    )
    st.stop()

try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error("❌ Không khởi tạo được Supabase.")
    st.exception(e)
    st.stop()

try:
    gemini_client = genai.Client(api_key=GEMINI_API_KEY)
except Exception as e:
    st.error("❌ Không khởi tạo được Gemini.")
    st.exception(e)
    st.stop()

# =====================================================================
# 4. SESSION STATE
# =====================================================================

DEFAULT_SESSION = {
    "search_file": None,
    "search_result": None,
    "search_ai_result": None,
    "search_embedding": None,
    "pending_upload_files": [],
    "last_upload_result": None,
    "detail_report": None,
    "detail_signature": None,
}
for key, default in DEFAULT_SESSION.items():
    if key not in st.session_state:
        st.session_state[key] = default

# =====================================================================
# 5. IMAGE HELPERS
# =====================================================================

def get_mime_type(filename):
    ext = str(filename).lower().rsplit(".", 1)[-1]
    if ext == "png":
        return "image/png"
    if ext in ("jpg", "jpeg"):
        return "image/jpeg"
    if ext == "webp":
        return "image/webp"
    return "image/jpeg"


def normalize_image_bytes(image_bytes):
    try:
        from PIL import Image
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        output = io.BytesIO()
        image.save(output, format="JPEG", quality=92)
        return output.getvalue()
    except Exception:
        return image_bytes


def calculate_file_hash(image_bytes):
    return hashlib.sha256(image_bytes).hexdigest()


# =====================================================================
# 6. CATEGORY / GARMENT HELPERS
# =====================================================================

def normalize_category(category):
    if category is None:
        return "Quần dài"
    value = str(category).strip()
    upper = value.upper()
    if upper in CATEGORY_ALIAS:
        return CATEGORY_ALIAS[upper]
    for valid in CATEGORY_OPTIONS:
        if value.lower() == valid.lower():
            return valid
    return "Quần dài"


GARMENT_PROMPT = """
You are an expert apparel technical designer and garment recognition AI.
Analyze the garment shown. Return only JSON matching the schema.

Category rules:
- If upper and lower body are physically connected: "Áo liền quần".
- If bib front + shoulder straps + trouser body: "Quần yếm".
- "Quần túi hộp" only for separate pants with obvious external side-leg cargo pockets.
- Separate denim pants: "Quần jean".
- Separate jogger pants with elastic/rib ankle cuffs: "Quần jogger".
- Separate short-leg pants: "Quần short".
- Separate long trousers without cargo/denim/jogger features: "Quần dài".
- Upper-body outerwear: "Jacket".
- One-piece dress silhouette: "Dress", not jumpsuit.
- Shirt/top: "Áo"; T-shirt: "T-shirt"; polo: "Polo"; hoodie: "Hoodie"; skirt: "Skirt".

Available categories:
Áo liền quần, Quần yếm, Quần túi hộp, Quần jean, Quần jogger,
Quần short, Quần dài, Jacket, Áo, T-shirt, Polo, Hoodie, Skirt, Dress.

Inspect garment boundary, upper/lower connection, waistband, legs, pockets,
bib, straps, sleeves, collar, hood, cuffs, silhouette and length.
Return concise reason and visual attributes. Do not invent unseen details.
"""


def bool_value(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower().strip() in ("true", "yes", "1", "y")
    if isinstance(value, (int, float)):
        return bool(value)
    return False


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
        category = "Quần yếm" if bib and shoulder_straps else "Áo liền quần"
    elif bib and shoulder_straps:
        category = "Quần yếm"
    elif category == "Quần túi hộp" and not cargo_pockets:
        category = "Quần dài"

    if (
        not one_piece and not bib and denim
        and category in ("Quần dài", "Quần short")
    ):
        category = "Quần jean"

    if (
        not one_piece and not bib and jogger_cuffs
        and category == "Quần dài"
    ):
        category = "Quần jogger"

    try:
        confidence = float(result.get("confidence", 0))
    except Exception:
        confidence = 0.0
    confidence = max(0.0, min(100.0, confidence))

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
# 7. GEMINI VISION WITH RETRY
# =====================================================================

GARMENT_SCHEMA = {
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
        "hood": {"type": "boolean"},
        "sleeve": {"type": "string"},
        "collar": {"type": "string"},
        "silhouette": {"type": "string"},
        "length": {"type": "string"},
        "reason": {"type": "string"}
    },
    "required": [
        "category", "confidence", "one_piece", "bib",
        "shoulder_straps", "cargo_pockets", "denim",
        "jogger_cuffs", "hood", "reason"
    ]
}


def gemini_generate_with_retry(*, model, contents, config):
    last_error = None
    for attempt in range(MAX_GEMINI_RETRIES):
        try:
            return gemini_client.models.generate_content(
                model=model, contents=contents, config=config
            )
        except Exception as e:
            last_error = e
            if attempt < MAX_GEMINI_RETRIES - 1:
                time.sleep(RETRY_DELAY_SECONDS)
    raise Exception(
        f"Gemini Vision lỗi sau {MAX_GEMINI_RETRIES} lần thử: {last_error}"
    )


def analyze_garment_with_gemini(image_bytes):
    image_bytes = normalize_image_bytes(image_bytes)
    response = gemini_generate_with_retry(
        model=VISION_MODEL,
        contents=[
            types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
            GARMENT_PROMPT
        ],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=GARMENT_SCHEMA,
            temperature=0.0
        )
    )
    text = getattr(response, "text", None)
    if not text:
        raise Exception("Gemini không trả về text.")
    try:
        result = json.loads(text)
    except Exception:
        cleaned = re.sub(r"```json|```", "", text, flags=re.I).strip()
        match = re.search(r"\{.*\}", cleaned, flags=re.S)
        if not match:
            raise Exception("Gemini không trả JSON hợp lệ.")
        result = json.loads(match.group(0))
    return normalize_garment_result(result)


# =====================================================================
# 8. GEMINI EMBEDDING 2 — STRICT 768 DIMENSIONS
# =====================================================================

def get_image_embedding(image_bytes):
    image_bytes = normalize_image_bytes(image_bytes)
    last_error = None

    for attempt in range(MAX_GEMINI_RETRIES):
        try:
            response = gemini_client.models.embed_content(
                model=EMBEDDING_MODEL,
                contents=[
                    types.Part.from_bytes(
                        data=image_bytes,
                        mime_type="image/jpeg"
                    )
                ],
                config=types.EmbedContentConfig(
                    output_dimensionality=EMBEDDING_DIMENSION
                )
            )

            if not response.embeddings:
                raise Exception("Gemini không trả về embedding.")

            values = response.embeddings[0].values
            if not values:
                raise Exception("Embedding rỗng.")

            values = [float(x) for x in values]
            if len(values) != EMBEDDING_DIMENSION:
                raise Exception(
                    f"Sai dimension: nhận {len(values)}, "
                    f"yêu cầu {EMBEDDING_DIMENSION}."
                )

            norm = math.sqrt(sum(x * x for x in values))
            if norm <= 0:
                raise Exception("Embedding có norm bằng 0.")

            values = [x / norm for x in values]

            if len(values) != EMBEDDING_DIMENSION:
                raise Exception("Vector cuối cùng không phải 768.")
            return values

        except Exception as e:
            last_error = e
            if attempt < MAX_GEMINI_RETRIES - 1:
                time.sleep(RETRY_DELAY_SECONDS)

    raise Exception(
        f"Gemini Image Embedding lỗi sau {MAX_GEMINI_RETRIES} lần thử: "
        f"{last_error}"
    )


# =====================================================================
# 9. SUPABASE STORAGE / DATABASE
# =====================================================================

def upload_image_to_storage(image_bytes, filename):
    safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", filename)
    file_hash = hashlib.sha256(image_bytes).hexdigest()[:12]
    base_name = safe_name.rsplit(".", 1)[0]
    ext = safe_name.rsplit(".", 1)[-1] if "." in safe_name else "jpg"
    path = f"{base_name}_{file_hash}.{ext}"
    mime_type = get_mime_type(filename)

    upload_error = None
    try:
        supabase.storage.from_(BUCKET_NAME).upload(
            path=path,
            file=image_bytes,
            file_options={
                "content-type": mime_type,
                "upsert": "true",
                "cache-control": "3600"
            }
        )
    except Exception as e:
        upload_error = e
        try:
            supabase.storage.from_(BUCKET_NAME).update(
                path=path,
                file=image_bytes,
                file_options={
                    "content-type": mime_type,
                    "upsert": "true",
                    "cache-control": "3600"
                }
            )
        except Exception:
            error_text = str(upload_error)
            if (
                "row-level security" in error_text.lower()
                or "unauthorized" in error_text.lower()
                or "403" in error_text
            ):
                raise Exception(
                    f"Supabase Storage bị chặn bởi RLS Policy. "
                    f"Bucket: {BUCKET_NAME}; API key không có quyền upload."
                )
            raise Exception(f"Supabase Storage lỗi: {error_text}")

    try:
        public_url = supabase.storage.from_(BUCKET_NAME).get_public_url(path)
        if isinstance(public_url, dict):
            public_url = public_url.get("publicUrl") or public_url.get("public_url")
        if not public_url:
            raise Exception("Public URL rỗng.")
        return public_url
    except Exception as e:
        raise Exception(f"Không lấy được Public URL: {e}")


def save_product(
    product_code, image_url, category, ai_category,
    ai_result, embedding, filename
):
    if not isinstance(embedding, list) or len(embedding) != EMBEDDING_DIMENSION:
        got = len(embedding) if isinstance(embedding, list) else "không phải list"
        raise Exception(f"Database BLOCK: embedding phải 768 chiều; nhận {got}.")

    row = {
        "product_code": product_code,
        "image_url": image_url,
        "category": category,
        "ai_category": ai_category,
        "embedding": embedding,
        "ai_analysis": ai_result,
        "file_name": filename
    }
    try:
        return supabase.table(PRODUCT_TABLE).upsert(
            row, on_conflict="product_code"
        ).execute()
    except Exception as e:
        raise Exception(f"Database save lỗi: {e}")


# =====================================================================
# 10. VECTOR SEARCH + RANKING
# =====================================================================

def search_similar_products(embedding, match_count=CANDIDATE_COUNT):
    if not isinstance(embedding, list) or len(embedding) != EMBEDDING_DIMENSION:
        got = len(embedding) if isinstance(embedding, list) else "không phải list"
        raise Exception(
            f"Vector search bị chặn: query phải 768 chiều; nhận {got}."
        )

    try:
        response = supabase.rpc(
            "match_products_v4",
            {
                "query_embedding": embedding,
                "match_threshold": MIN_SIMILARITY,
                "match_count": int(match_count)
            }
        ).execute()
        return response.data or []
    except Exception as e:
        error_text = str(e)
        if "different vector dimensions" in error_text.lower():
            raise Exception(
                "Supabase RPC đang dùng vector dimension không đồng nhất. "
                f"Yêu cầu 768 chiều. Chi tiết: {error_text}"
            )
        raise Exception(f"Supabase similarity search lỗi: {error_text}")


def calculate_display_score(item, query_category):
    try:
        similarity = float(item.get("similarity", 0))
    except Exception:
        similarity = 0.0

    db_category = normalize_category(item.get("category", ""))
    ai_category = normalize_category(item.get("ai_category", ""))

    # Boost nhẹ, không loại mã hàng khác category.
    if query_category == db_category:
        similarity += 0.08
    elif query_category == ai_category:
        similarity += 0.05

    return similarity


def rank_results(results, query_category):
    enriched = []
    for original in results:
        item = dict(original)
        item["display_score"] = calculate_display_score(item, query_category)
        enriched.append(item)

    enriched.sort(
        key=lambda x: float(x.get("display_score", 0)),
        reverse=True
    )
    return enriched


def product_code_from_filename(filename):
    return str(filename).rsplit(".", 1)[0].strip().upper()


# =====================================================================
# 11. ON-DEMAND VISUAL DIFFERENCE ANALYSIS — ONE GEMINI CALL
# =====================================================================

DETAIL_COMPARE_PROMPT = """
You are an apparel technical designer comparing garment images for style similarity.
The first image is the QUERY garment. Following images are numbered candidate garments
in the same order as their labels in the prompt.

Compare visible construction only. Do not infer hidden construction or fabric composition.
For each candidate, assess:
- overall silhouette and garment type
- upper/lower connection, bib and straps if visible
- waistband, rise and leg shape if visible
- pocket type and placement
- sleeves, collar, hood and cuffs if visible
- visible paneling, seams and closures
- length/proportion
- major differences that may affect whether it is a useful historical consumption reference

Return JSON only with:
{
  "summary": "short overall summary",
  "candidates": [
    {
      "candidate_number": 1,
      "similarity_level": "Rất gần | Khá gần | Trung bình | Khác biệt đáng kể",
      "matching_features": ["..."],
      "differences": ["..."],
      "consumption_reference_warning": "short practical warning",
      "recommendation": "Ưu tiên tham khảo | Có thể tham khảo, cần kiểm tra | Không nên dùng làm mã tham chiếu chính"
    }
  ]
}
Do not give a numeric accuracy probability. Mention when a detail cannot be confirmed from the images.
"""


def download_candidate_image(image_url):
    if not image_url:
        return None
    try:
        response = requests.get(
            image_url,
            timeout=HTTP_TIMEOUT_SECONDS,
            headers={"User-Agent": "Mozilla/5.0"}
        )
        response.raise_for_status()
        content_type = response.headers.get("content-type", "").lower()
        if not content_type.startswith("image/"):
            return None
        return normalize_image_bytes(response.content)
    except Exception:
        return None


def analyze_candidate_differences(query_image_bytes, candidates):
    """
    candidates: danh sách tối đa DETAIL_COMPARE_COUNT item.
    Chỉ gọi hàm này sau khi user bấm nút phân tích.
    """
    selected = candidates[:DETAIL_COMPARE_COUNT]
    if not selected:
        raise Exception("Không có ứng viên để phân tích.")

    contents = [
        types.Part.from_bytes(
            data=normalize_image_bytes(query_image_bytes),
            mime_type="image/jpeg"
        ),
        "Ảnh đầu tiên là ảnh QUERY. Các ảnh tiếp theo là ứng viên theo thứ tự sau:"
    ]

    usable_codes = []
    skipped = []

    for idx, item in enumerate(selected, start=1):
        code = str(item.get("product_code", f"Ứng viên {idx}"))
        image_url = item.get("image_url")
        candidate_bytes = download_candidate_image(image_url)
        if not candidate_bytes:
            skipped.append(code)
            continue

        contents.append(
            f"Candidate number {idx}: product code {code}."
        )
        contents.append(
            types.Part.from_bytes(
                data=candidate_bytes,
                mime_type="image/jpeg"
            )
        )
        usable_codes.append((idx, code))

    if not usable_codes:
        raise Exception(
            "Không tải được ảnh ứng viên từ Storage. "
            "Kiểm tra public URL hoặc quyền truy cập bucket."
        )

    contents.append(DETAIL_COMPARE_PROMPT)
    contents.append(
        "Candidate numbers available for comparison: "
        + ", ".join(f"{n} = {code}" for n, code in usable_codes)
    )

    schema = {
        "type": "object",
        "properties": {
            "summary": {"type": "string"},
            "candidates": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "candidate_number": {"type": "integer"},
                        "similarity_level": {"type": "string"},
                        "matching_features": {
                            "type": "array",
                            "items": {"type": "string"}
                        },
                        "differences": {
                            "type": "array",
                            "items": {"type": "string"}
                        },
                        "consumption_reference_warning": {"type": "string"},
                        "recommendation": {"type": "string"}
                    },
                    "required": [
                        "candidate_number", "similarity_level",
                        "matching_features", "differences",
                        "consumption_reference_warning", "recommendation"
                    ]
                }
            }
        },
        "required": ["summary", "candidates"]
    }

    response = gemini_generate_with_retry(
        model=VISION_MODEL,
        contents=contents,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=schema,
            temperature=0.0
        )
    )

    response_text = getattr(response, "text", None)
    if not response_text:
        raise Exception("Gemini không trả kết quả phân tích khác biệt.")

    try:
        report = json.loads(response_text)
    except Exception:
        cleaned = re.sub(r"```json|```", "", response_text, flags=re.I).strip()
        match = re.search(r"\{.*\}", cleaned, flags=re.S)
        if not match:
            raise Exception("Gemini trả JSON phân tích không hợp lệ.")
        report = json.loads(match.group(0))

    report["_candidate_code_map"] = {
        str(n): code for n, code in usable_codes
    }
    report["_skipped_images"] = skipped
    return report


# =====================================================================
# 12. SHARED UI HELPERS
# =====================================================================

def render_ai_summary(ai_result):
    if not ai_result:
        return

    st.divider()
    st.markdown("### 🤖 Kết quả AI nhận dạng")
    c1, c2, c3, c4 = st.columns(4)

    c1.metric("Category AI", ai_result.get("category", "N/A"))
    c2.metric("Confidence nhận dạng", f"{float(ai_result.get('confidence', 0)):.0f}%")
    c3.metric("One Piece", "YES" if ai_result.get("one_piece") else "NO")
    c4.metric("Cargo Pocket", "YES" if ai_result.get("cargo_pockets") else "NO")

    if ai_result.get("reason"):
        st.info("🧠 " + str(ai_result["reason"]))


def render_difference_report(report):
    if not report:
        return

    st.divider()
    st.markdown("### 🧵 Phân tích khác biệt chi tiết")
    st.info(report.get("summary", ""))

    code_map = report.get("_candidate_code_map", {})

    for candidate in report.get("candidates", []):
        number = str(candidate.get("candidate_number", ""))
        code = code_map.get(number, f"Ứng viên {number}")
        st.markdown(f"#### 🏷️ {code} — {candidate.get('similarity_level', 'N/A')}")

        matches = candidate.get("matching_features", [])
        differences = candidate.get("differences", [])

        left, right = st.columns(2)
        with left:
            st.markdown("**Điểm giống**")
            if matches:
                for value in matches:
                    st.write(f"• {value}")
            else:
                st.caption("Chưa ghi nhận điểm giống cụ thể.")

        with right:
            st.markdown("**Điểm khác**")
            if differences:
                for value in differences:
                    st.write(f"• {value}")
            else:
                st.caption("Không phát hiện khác biệt rõ qua ảnh.")

        if candidate.get("consumption_reference_warning"):
            st.warning(
                "⚠️ Lưu ý khi dùng tham chiếu ĐM: "
                + str(candidate["consumption_reference_warning"])
            )
        if candidate.get("recommendation"):
            st.write("**Khuyến nghị:** " + str(candidate["recommendation"]))

    if report.get("_skipped_images"):
        st.caption(
            "Không tải được ảnh các mã: "
            + ", ".join(report["_skipped_images"])
        )


# =====================================================================
# 13. HEADER
# =====================================================================

st.title("🔍 AI TÌM KIẾM MÃ HÀNG TƯƠNG ĐỒNG")
st.caption(
    "Gemini Vision + Gemini Embedding 2 + Supabase pgvector — "
    f"{APP_VERSION} — Embedding LOCK: 768"
)
st.caption(
    "Tiết kiệm quota: tìm kiếm thường không gọi Gemini Vision lần hai; "
    "phân tích khác biệt chỉ chạy khi bạn chủ động yêu cầu."
)

tab_search, tab_storage = st.tabs([
    "🔍 TÌM KIẾM TƯƠNG ĐỒNG",
    "📦 NẠP KHO HÀNG LOẠT"
])

# =====================================================================
# TAB 1 — SEARCH
# =====================================================================

with tab_search:
    st.subheader("🔍 Tìm mã hàng bằng ảnh")
    st.info(
        "Không cần chọn dòng hàng. AI tự nhận dạng garment và tìm trên toàn bộ kho. "
        "Tìm kiếm thường dùng 1 lần Vision + 1 lần Embedding."
    )

    search_file = st.file_uploader(
        "📷 Tải ảnh Sketch / ảnh mẫu cần tìm",
        type=["jpg", "jpeg", "png", "webp"],
        key="search_uploader_v46"
    )

    col_clear, _ = st.columns([1, 5])
    with col_clear:
        if st.button("🗑️ Xóa ảnh hiện tại", key="clear_search_file_v46"):
            st.session_state.search_file = None
            st.session_state.search_result = None
            st.session_state.search_ai_result = None
            st.session_state.search_embedding = None
            st.session_state.detail_report = None
            st.session_state.detail_signature = None
            st.rerun()

    if search_file is not None:
        image_bytes = search_file.getvalue()
        st.session_state.search_file = image_bytes

        col1, col2 = st.columns([1, 2])
        with col1:
            st.image(image_bytes, caption=search_file.name, use_container_width=True)

        with col2:
            st.markdown("### 🤖 AI nhận dạng")
            if st.button(
                "🚀 PHÂN TÍCH & TÌM MÃ TƯƠNG ĐỒNG",
                type="primary",
                use_container_width=True,
                key="run_search_v46"
            ):
                try:
                    st.session_state.detail_report = None
                    st.session_state.detail_signature = None

                    with st.spinner("🤖 AI đang nhận dạng garment..."):
                        ai_result = analyze_garment_with_gemini(image_bytes)
                    st.session_state.search_ai_result = ai_result

                    with st.spinner("🧠 Gemini Embedding 2 — vector 768..."):
                        query_embedding = get_image_embedding(image_bytes)

                    if len(query_embedding) != EMBEDDING_DIMENSION:
                        raise Exception(
                            f"Query embedding sai dimension: {len(query_embedding)}."
                        )
                    st.session_state.search_embedding = query_embedding

                    with st.spinner(
                        f"🔎 Đang lấy tối đa {CANDIDATE_COUNT} ứng viên từ kho..."
                    ):
                        results = search_similar_products(
                            query_embedding,
                            match_count=CANDIDATE_COUNT
                        )

                    results = rank_results(results, ai_result["category"])
                    st.session_state.search_result = results

                    if not results:
                        st.warning(
                            "Không có kết quả vượt ngưỡng similarity hiện tại "
                            f"({MIN_SIMILARITY:.2f}). Có thể kiểm tra ngưỡng RPC "
                            "nếu kho có mã phù hợp nhưng không được trả về."
                        )

                except Exception as e:
                    st.session_state.search_result = None
                    st.error(f"❌ Lỗi tìm kiếm: {e}")

    render_ai_summary(st.session_state.search_ai_result)

    results = st.session_state.search_result
    if results is not None:
        st.divider()
        st.markdown("### 🎯 Mã hàng tương đồng")
        st.caption(
            f"Đã xếp hạng {len(results)} ứng viên; hiển thị tối đa "
            f"{min(DISPLAY_COUNT, len(results))} mã. "
            "Điểm xếp hạng có cộng ưu tiên category, không phải xác suất chính xác."
        )

        if not results:
            st.warning("Không tìm thấy mã hàng tương đồng trong kho.")
        else:
            display_results = results[:DISPLAY_COUNT]
            columns = st.columns(min(4, len(display_results)))

            for index, item in enumerate(display_results):
                with columns[index % len(columns)]:
                    st.markdown("---")
                    image_url = item.get("image_url")
                    if image_url:
                        try:
                            st.image(image_url, use_container_width=True)
                        except Exception:
                            st.caption("Không hiển thị được ảnh.")

                    code = str(item.get("product_code", "N/A"))
                    st.markdown(f"### 🏷️ {code}")

                    try:
                        similarity = float(item.get("similarity", 0))
                    except Exception:
                        similarity = 0.0
                    try:
                        display_score = float(item.get("display_score", similarity))
                    except Exception:
                        display_score = similarity

                    st.metric("Điểm vector", f"{similarity * 100:.2f}%")
                    st.caption(f"Điểm xếp hạng sau category boost: {display_score * 100:.2f}%")
                    st.write("📦 Kho:", item.get("category", "N/A"))
                    st.write("🤖 AI:", item.get("ai_category", "N/A"))

            st.divider()
            st.markdown("### 🧵 Kiểm tra khác biệt (tùy chọn)")
            st.caption(
                f"Chỉ gửi ảnh khi bạn bấm nút. Mỗi lần phân tích dùng 1 lần gọi Gemini "
                f"cho ảnh truy vấn và tối đa {DETAIL_COMPARE_COUNT} ảnh ứng viên."
            )

            candidate_codes = [
                str(x.get("product_code", f"Ứng viên {i + 1}"))
                for i, x in enumerate(display_results[:DETAIL_COMPARE_COUNT])
            ]
            default_selection = candidate_codes[:]
            selected_codes = st.multiselect(
                "Chọn tối đa 3 mã để so sánh trực quan",
                options=candidate_codes,
                default=default_selection,
                max_selections=DETAIL_COMPARE_COUNT,
                key="detail_candidate_select_v46"
            )

            selected_candidates = [
                item for item in display_results
                if str(item.get("product_code", "")) in selected_codes
            ]

            if st.button(
                "🔬 PHÂN TÍCH ĐIỂM GIỐNG / KHÁC",
                type="secondary",
                use_container_width=True,
                disabled=not selected_candidates,
                key="run_detail_compare_v46"
            ):
                try:
                    if not st.session_state.search_file:
                        raise Exception("Không còn ảnh truy vấn. Vui lòng tải ảnh và tìm lại.")
                    with st.spinner(
                        "Gemini đang so sánh ảnh truy vấn với các mã đã chọn..."
                    ):
                        report = analyze_candidate_differences(
                            st.session_state.search_file,
                            selected_candidates
                        )
                    st.session_state.detail_report = report
                    st.session_state.detail_signature = "|".join(selected_codes)
                except Exception as e:
                    st.session_state.detail_report = None
                    st.error(f"❌ Không phân tích được khác biệt: {e}")

            render_difference_report(st.session_state.detail_report)

# =====================================================================
# TAB 2 — BULK STORAGE
# =====================================================================

with tab_storage:
    st.subheader("📦 Nạp mã hàng vào kho")
    st.info(
        "AI tự nhận diện dòng hàng. Mỗi ảnh nạp kho cần 1 lần Gemini Vision "
        "+ 1 lần Gemini Embedding."
    )

    uploaded_files = st.file_uploader(
        "📷 Chọn ảnh mã hàng",
        type=["jpg", "jpeg", "png", "webp"],
        accept_multiple_files=True,
        key="storage_uploader_v46"
    )

    if uploaded_files:
        current_keys = [
            (f.name, len(f.getvalue()))
            for f in st.session_state.pending_upload_files
        ]
        for file in uploaded_files:
            file_key = (file.name, len(file.getvalue()))
            if file_key not in current_keys:
                st.session_state.pending_upload_files.append(file)
                current_keys.append(file_key)

    c1, _ = st.columns([1, 5])
    with c1:
        if st.button("🗑️ Xóa danh sách chờ", key="clear_pending_files_v46"):
            st.session_state.pending_upload_files = []
            st.rerun()

    pending_files = st.session_state.pending_upload_files
    if pending_files:
        st.success(f"📂 Đang chờ **{len(pending_files)}** file để nạp kho.")

        preview_cols = st.columns(min(5, len(pending_files)))
        for i, file in enumerate(pending_files):
            with preview_cols[i % len(preview_cols)]:
                st.image(file.getvalue(), caption=file.name, use_container_width=True)

        st.divider()

        if st.button(
            "📤 BẮT ĐẦU NẠP TOÀN BỘ VÀO KHO",
            type="primary",
            use_container_width=True,
            key="start_storage_upload_v46"
        ):
            total = len(pending_files)
            success_count = 0
            failed_count = 0
            progress = st.progress(0)
            status = st.empty()
            upload_results = []

            for index, file in enumerate(pending_files):
                product_code = product_code_from_filename(file.name)
                status.write(f"⏳ {index + 1}/{total} — `{product_code}`")

                try:
                    image_bytes = file.getvalue()
                    if not image_bytes:
                        raise Exception("File ảnh rỗng.")

                    status.write(f"🤖 AI đang nhận dạng `{product_code}`...")
                    ai_result = analyze_garment_with_gemini(image_bytes)
                    ai_category = normalize_category(ai_result.get("category", "Quần dài"))

                    status.write(f"🧠 Tạo image embedding 768 `{product_code}`...")
                    embedding = get_image_embedding(image_bytes)
                    if len(embedding) != EMBEDDING_DIMENSION:
                        raise Exception(
                            f"Embedding của {product_code} không đúng 768 chiều."
                        )

                    status.write(f"☁️ Upload ảnh `{product_code}`...")
                    image_url = upload_image_to_storage(image_bytes, file.name)

                    status.write(f"💾 Lưu database `{product_code}`...")
                    save_product(
                        product_code=product_code,
                        image_url=image_url,
                        category=ai_category,
                        ai_category=ai_category,
                        ai_result=ai_result,
                        embedding=embedding,
                        filename=file.name
                    )

                    success_count += 1
                    upload_results.append({
                        "product_code": product_code,
                        "category": ai_category,
                        "ai_category": ai_category,
                        "confidence": float(ai_result.get("confidence", 0)),
                        "status": "OK"
                    })

                except Exception as e:
                    failed_count += 1
                    upload_results.append({
                        "product_code": product_code,
                        "category": "",
                        "ai_category": "",
                        "confidence": 0,
                        "status": str(e)
                    })
                    st.error(f"❌ `{product_code}` — {e}")

                progress.progress(int((index + 1) / total * 100))
                if index < total - 1:
                    time.sleep(BULK_DELAY_SECONDS)

            status.empty()
            st.session_state.last_upload_result = upload_results
            st.session_state.pending_upload_files = []

            if success_count:
                st.success(f"🎉 Đã nạp thành công **{success_count}/{total}** mã hàng.")
            if failed_count:
                st.warning(f"⚠️ Có **{failed_count}** file xử lý thất bại.")

            st.rerun()

    if st.session_state.last_upload_result:
        st.divider()
        st.markdown("### 📋 Kết quả nạp kho")
        for item in st.session_state.last_upload_result:
            if item.get("status") == "OK":
                st.success(
                    f"✅ {item.get('product_code', 'N/A')} — "
                    f"AI: {item.get('ai_category', 'N/A')} — "
                    f"Độ tự tin: {float(item.get('confidence', 0)):.0f}%"
                )
            else:
                st.error(
                    f"❌ {item.get('product_code', 'N/A')} — "
                    f"Lỗi: {item.get('status', 'Unknown')}"
                )

        if st.button("🗑️ Xóa thông báo kết quả", key="clear_upload_result_report_v46"):
            st.session_state.last_upload_result = None
            st.rerun()

# =====================================================================
# FOOTER
# =====================================================================

st.divider()
st.caption(
    "AI Garment Similarity Search — Gemini Vision + Gemini Embedding 2 "
    "+ Supabase pgvector — VECTOR DIMENSION: 768 — V4.6 QUOTA-SAVER"
)
