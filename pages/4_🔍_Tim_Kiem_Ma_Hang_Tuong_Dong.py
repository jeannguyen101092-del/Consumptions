# =====================================================================
# 🔍 AI TÌM KIẾM MÃ HÀNG TƯƠNG ĐỒNG - VERSION V4.0
# =====================================================================

import streamlit as st
import io
import os
import json
import re
import base64
import hashlib
import math
from typing import Any, Dict, List, Optional

# --- 1. PAGE CONFIG ---
st.set_page_config(
    page_title="AI Tìm Kiếm Mã Hàng Tương Đồng",
    page_icon="🔍",
    layout="wide"
)

# --- 2. OPTIONAL IMPORT ---
try:
    from supabase import create_client, Client
except Exception as e:
    st.error("❌ Chưa cài thư viện supabase. Thêm `supabase` vào requirements.txt")
    st.stop()

try:
    from google import genai
    from google.genai import types
except Exception as e:
    st.error("❌ Chưa cài thư viện Google GenAI. Thêm `google-genai` vào requirements.txt")
    st.stop()

# =====================================================================
# 3. CONSTANTS (CẬP NHẬT CHUẨN ĐỊNH DẠNG)
# =====================================================================

APP_VERSION = "V4.0"

BUCKET_NAME = "product-images"

PRODUCT_TABLE = "products"

# Gemini Vision
VISION_MODEL = "gemini-2.5-flash"

# Gemini Multimodal Embedding ID chính xác cho SDK mới
EMBEDDING_MODEL = "text-embedding-004"

# Embedding dimension
EMBEDDING_DIMENSION = 768

SEARCH_COUNT = 12

MIN_SIMILARITY = 0.35


# --- 4. CATEGORY MASTER ---
CATEGORY_OPTIONS = [
    "Áo liền quần", "Quần yếm", "Quần túi hộp", "Quần jean", "Quần jogger",
    "Quần short", "Quần dài", "Jacket", "Áo", "T-shirt", "Polo", "Hoodie", "Skirt", "Dress"
]

# --- 5. CATEGORY ALIAS ---
CATEGORY_ALIAS = {
    "JUMPSUIT": "Áo liền quần", "ONE PIECE": "Áo liền quần", "ONE-PIECE": "Áo liền quần", "ROMPER": "Áo liền quần",
    "OVERALL": "Quần yếm", "OVERALLS": "Quần yếm", "BIB OVERALL": "Quần yếm", "DUNGAREE": "Quần yếm", "DUNGAREES": "Quần yếm",
    "CARGO": "Quần túi hộp", "CARGO PANTS": "Quần túi hộp", "CARGO TROUSERS": "Quần túi hộp",
    "JEANS": "Quần jean", "DENIM JEANS": "Quần jean", "DENIM PANTS": "Quần jean",
    "JOGGER": "Quần jogger", "JOGGERS": "Quần jogger", "JOGGER PANTS": "Quần jogger",
    "SHORT": "Quần short", "SHORTS": "Quần short",
    "PANTS": "Quần dài", "TROUSERS": "Quần dài", "TROUSER": "Quần dài", "LONG PANTS": "Quần dài",
    "SHIRT": "Áo", "TOP": "Áo", "T-SHIRT": "T-shirt", "TSHIRT": "T-shirt", "TEE": "T-shirt",
    "POLO SHIRT": "Polo", "POLO": "Polo", "HOODIE": "Hoodie",
    "JACKET": "Jacket", "BOMBER": "Jacket", "OUTERWEAR": "Jacket",
    "SKIRT": "Skirt", "DRESS": "Dress"
}

# --- 6. SECRET READER ---
def _safe_secret_get(container, key):
    try:
        if container is None: return None
        if key in container:
            value = container[key]
            if value is not None: return str(value).strip()
    except Exception: pass
    return None

def _recursive_find_secret(obj, target_names):
    if obj is None: return None
    try:
        if hasattr(obj, "items"):
            for key, value in obj.items():
                key_upper = str(key).upper().strip()
                if key_upper in target_names:
                    if value is not None: return str(value).strip()
                result = _recursive_find_secret(value, target_names)
                if result: return result
    except Exception: pass
    return None

def get_secret(*names):
    normalized = {str(x).upper().strip() for x in names}
    try:
        for name in normalized:
            value = _safe_secret_get(st.secrets, name)
            if value: return value
        value = _recursive_find_secret(st.secrets, normalized)
        if value: return value
    except Exception: pass
    for name in normalized:
        value = os.environ.get(name)
        if value: return value.strip()
    return None
# --- 7. LOAD SECRETS ---
SUPABASE_URL = get_secret("SUPABASE_URL", "supabase_url", "URL")
SUPABASE_KEY = get_secret("SUPABASE_KEY", "SUPABASE_ANON_KEY", "supabase_key", "anon_key", "KEY")
GEMINI_API_KEY = get_secret("GEMINI_API_KEY", "GOOGLE_API_KEY", "GEMINI_KEY", "gemini_api_key", "api_key")

# --- 8. SECRET VALIDATION ---
missing_secrets = []
if not SUPABASE_URL: missing_secrets.append("SUPABASE_URL")
if not SUPABASE_KEY: missing_secrets.append("SUPABASE_KEY")
if not GEMINI_API_KEY: missing_secrets.append("GEMINI_API_KEY")

if missing_secrets:
    st.error("❌ Không đọc được thông tin bảo mật từ Streamlit Secrets.")
    st.markdown("### Các key còn thiếu:")
    for key in missing_secrets: st.code(key, language="text")
    st.stop()

# --- 9. CREATE CLIENTS ---
try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error("❌ Không kết nối được Supabase."); st.exception(e); st.stop()

try:
    gemini_client = genai.Client(api_key=GEMINI_API_KEY)
except Exception as e:
    st.error("❌ Không khởi tạo được Gemini."); st.exception(e); st.stop()

# --- 10. SESSION STATE ---
if "search_file" not in st.session_state: st.session_state.search_file = None
if "search_result" not in st.session_state: st.session_state.search_result = None
if "search_ai_result" not in st.session_state: st.session_state.search_ai_result = None
if "pending_upload_files" not in st.session_state: st.session_state.pending_upload_files = []
if "last_upload_result" not in st.session_state: st.session_state.last_upload_result = None

# --- 11. IMAGE HELPERS ---
def get_mime_type(filename):
    ext = filename.lower().rsplit(".", 1)[-1]
    if ext == "png": return "image/png"
    if ext in ["jpg", "jpeg"]: return "image/jpeg"
    if ext == "webp": return "image/webp"
    return "image/jpeg"

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

# --- 12. FILE HASH ---
def calculate_file_hash(image_bytes):
    return hashlib.sha256(image_bytes).hexdigest()
# --- 13. GEMINI GARMENT PROMPT ---
GARMENT_PROMPT = """
You are an expert apparel technical designer and garment recognition AI.
Analyze the garment in the image. This is a COMMERCIAL APPAREL SIMILARITY SEARCH SYSTEM.
Do NOT classify only by superficial visual appearance. You must identify the actual garment construction.

=========================================================
CRITICAL GARMENT RULES
=========================================================
1. ONE PIECE / JUMPSUIT: If upper body and lower body are physically connected into one garment: category = "Áo liền quần". Do NOT classify it as cargo pants.
2. BIB OVERALL: If the garment has front bib, shoulder straps, trouser body: category = "Quần yếm".
3. CARGO PANTS: Only classify "Quần túi hộp" when it is a separate pants garment AND there are obvious external cargo/patch pockets on side legs.
4. JEANS: Separate pants made from denim: category = "Quần jean".
5. JOGGER: Separate pants with elastic or rib ankle cuffs: category = "Quần jogger".
6. SHORTS: Separate pants with short leg length: category = "Quần short".
7. LONG PANTS: Separate long trousers without strong cargo, denim, or jogger construction: category = "Quần dài".
8. JACKET: Separate upper-body outerwear garment: category = "Jacket".
9. DRESS: One-piece dress silhouette. A dress is NOT a jumpsuit.
10. SHIRT / TOP: Upper-body garment.

=========================================================
AVAILABLE CATEGORIES
=========================================================
- Áo liền quần | - Quần yếm | - Quần túi hộp | - Quần jean | - Quần jogger | - Quần short | - Quần dài | - Jacket | - Áo | - T-shirt | - Polo | - Hoodie | - Skirt | - Dress
Return ONLY JSON. Do NOT guess cargo just because the pants have pockets.
"""

# =====================================================================
# 14. GEMINI CATEGORY NORMALIZER
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


# =====================================================================
# 15. GARMENT RULE ENGINE (ĐÃ DI CHUYỂN LÊN TRÊN ĐỂ TRÁNH LỖI NOT DEFINED)
# =====================================================================

def normalize_garment_result(result):
    if not isinstance(result, dict): 
        result = {}
        
    category = normalize_category(
        result.get("category", "Quần dài")
    )

    def bool_value(value):
        if isinstance(value, bool): 
            return value
        if isinstance(value, str): 
            return value.lower().strip() in ["true", "yes", "1"]
        if isinstance(value, (int, float)): 
            return bool(value)
        return False

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
# 16. GEMINI VISION ANALYSIS
# =====================================================================

def analyze_garment_with_gemini(image_bytes):
    import time
    image_bytes = normalize_image_bytes(image_bytes)
    
    max_retries = 4
    retry_delay = 5  # Số giây chờ tăng cường nếu dính giới hạn của Google

    for attempt in range(max_retries):
        try:
            response = gemini_client.models.generate_content(
                model=VISION_MODEL,
                contents=[
                    types.Part.from_bytes(
                        data=image_bytes,
                        mime_type="image/jpeg"
                    ),
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
            break
            
        except Exception as e:
            err_msg = str(e)
            if "429" in err_msg or "503" in err_msg:
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (attempt + 1))
                    continue
            raise Exception("Gemini Vision lỗi: " + err_msg)

    try:
        text = response.text
    except Exception:
        text = None

    if not text:
        raise Exception("Gemini không trả về kết quả.")

    try:
        result = json.loads(text)
    except Exception:
        cleaned = re.sub(r"```json|```", "", text, flags=re.I).strip()
        match = re.search(r"\{.*\}", cleaned, flags=re.S)
        if not match:
            raise Exception("Gemini không trả JSON hợp lệ:\n" + text[:2000])
        try:
            result = json.loads(match.group(0))
        except Exception as e:
            raise Exception("Không parse được JSON Gemini: " + str(e))

    # Gọi hàm đã được khai báo ở phía trên hoàn toàn an toàn
    result = normalize_garment_result(result)
    return result


# =====================================================================
# 17. GEMINI SEMANTIC TEXT EMBEDDING (TỐI ƯU GIẢM REQUEST)
# =====================================================================

def get_image_embedding(semantic_text: str):
    """
    Tạo vector nhúng đặc trưng từ chuỗi mô tả cấu trúc rập kỹ thuật.
    Không truyền ảnh vào đây để tránh bị trùng lặp request gây lỗi 429.
    """
    try:
        response = gemini_client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=semantic_text if semantic_text else "garment",
            config=types.EmbedContentConfig(
                output_dimensionality=EMBEDDING_DIMENSION
            )
        )
    except Exception as e:
        raise Exception("Gemini Image Embedding lỗi: " + str(e))

    try:
        if hasattr(response, "embeddings") and response.embeddings:
            values = response.embeddings.values
        elif hasattr(response, "embedding") and response.embedding:
            values = response.embedding.values
        else:
            values = response.embeddings.values
    except Exception as e:
        raise Exception("Không lấy được vector embedding: " + str(e))

    if not values:
        raise Exception("Embedding rỗng.")

    # NORMALIZE VECTOR
    norm = math.sqrt(sum(float(x) * float(x) for x in values))
    return [float(x) / norm for x in values] if norm > 0 else [float(x) for x in values]

# --- 18. UPLOAD IMAGE TO SUPABASE STORAGE ---
def upload_image_to_storage(image_bytes, filename):
    path = re.sub(r"[^A-Za-z0-9._-]", "_", filename)
    mime_type = get_mime_type(filename)
    try:
        supabase.storage.from_(BUCKET_NAME).upload(path=path, file=image_bytes, file_options={"content-type": mime_type, "upsert": "true", "cache-control": "3600"})
    except Exception as e:
        error_text = str(e)
        try: supabase.storage.from_(BUCKET_NAME).update(path=path, file=image_bytes, file_options={"content-type": mime_type, "upsert": "true", "cache-control": "3600"})
        except Exception: raise Exception("Supabase Storage lỗi: " + error_text)
    try:
        public_url = supabase.storage.from_(BUCKET_NAME).get_public_url(path)
        return public_url.get("publicUrl") if isinstance(public_url, dict) else public_url
    except Exception as e: raise Exception("Không lấy được Public URL: " + str(e))

# --- 19. SAVE PRODUCT ---
def save_product(product_code, image_url, category, ai_category, ai_result, embedding, filename):
    row = {"product_code": product_code, "image_url": image_url, "category": category, "ai_category": ai_category, "embedding": embedding, "ai_analysis": ai_result, "file_name": filename}
    try: return supabase.table(PRODUCT_TABLE).upsert(row, on_conflict="product_code").execute()
    except Exception as e: raise Exception("Database save lỗi: " + str(e))

# --- 20. SEARCH SIMILAR PRODUCTS ---
def search_similar_products(embedding, match_count=SEARCH_COUNT):
    try:
        response = supabase.rpc("match_products_v4", {"query_embedding": embedding, "match_threshold": MIN_SIMILARITY, "match_count": match_count}).execute()
        return response.data or []
    except Exception as e: raise Exception("Supabase similarity search lỗi: " + str(e))

# --- 21. CATEGORY BOOST ---
def calculate_display_score(item, query_category):
    try: similarity = float(item.get("similarity", 0))
    except Exception: similarity = 0
    db_category = normalize_category(item.get("category", ""))
    ai_category = normalize_category(item.get("ai_category", ""))
    score = similarity
    if query_category == db_category: score += 0.08
    elif query_category == ai_category: score += 0.05
    return score

# --- 22. SORT SEARCH RESULTS ---
def rank_results(results, query_category):
    enriched = []
    for item in results:
        item = dict(item)
        item["display_score"] = calculate_display_score(item, query_category)
        enriched.append(item)
    enriched.sort(key=lambda x: x.get("display_score", 0), reverse=True)
    return enriched

# --- 23. PRODUCT CODE FROM FILE NAME ---
def product_code_from_filename(filename):
    name = filename.rsplit(".", 1)[0]
    return str(name).strip().upper()
# --- 24. HEADER & TABS ---
st.title("🔍 AI TÌM KIẾM MÃ HÀNG TƯƠNG ĐỒNG")
st.caption(f"AI Garment Recognition + Gemini Embedding 2 + Supabase Vector Search — {APP_VERSION}")
tab_search, tab_storage = st.tabs(["🔍 TÌM KIẾM TƯƠNG ĐỒNG", "📦 NẠP KHO HÀNG LOẠT"])

# =====================================================================
# TAB 1: TÌM KIẾM MÃ TƯƠNG ĐỒNG (ĐÃ SỬA LỖI TRÙNG LOGIC & CHỐNG 503/429)
# =====================================================================
with tab_search:
    st.subheader("🔍 Tìm mã hàng bằng ảnh")
    st.info("Không cần chọn dòng hàng. AI sẽ tự nhận dạng garment và tìm trên toàn bộ kho.")
    
    # ---------------------------------------------------------
    # FILE UPLOADER
    # ---------------------------------------------------------
    search_file = st.file_uploader(
        "📷 Tải ảnh Sketch / ảnh mẫu cần tìm", 
        type=["jpg", "jpeg", "png", "webp"], 
        key="search_uploader"
    )

    # ---------------------------------------------------------
    # CLEAR CURRENT SEARCH FILE
    # ---------------------------------------------------------
    col_a, _ = st.columns([1, 5])
    with col_a:
        if st.button("🗑️ Xóa ảnh hiện tại", key="clear_search_file"):
            st.session_state.search_file = None
            st.session_state.search_result = None
            st.session_state.search_ai_result = None
            st.rerun()

    # ---------------------------------------------------------
    # SEARCH FILE PROCESS
    # ---------------------------------------------------------
    if search_file is not None:
        image_bytes = search_file.getvalue()
        st.session_state.search_file = image_bytes

        col1, col2 = st.columns()

        with col1:
            st.image(image_bytes, caption=search_file.name, use_container_width=True)

        with col2:
            st.markdown("### 🤖 AI nhận dạng")

            if st.button(
                "🚀 PHÂN TÍCH & TÌM MÃ TƯƠNG ĐỒNG",
                type="primary",
                use_container_width=True,
                key="run_search"
            ):
                import time
                try:
                    # Cấu hình cơ chế tự động thử lại (Retry) nếu Gemini quá tải cục bộ
                    max_retries = 3
                    retry_delay = 4
                    ai_result = None
                    
                    # =================================================
                    # STEP 1: AI VISION (Phân tích cấu trúc rập)
                    # =================================================
                    for attempt in range(max_retries):
                        try:
                            with st.spinner("🤖 AI đang nhận dạng garment..."):
                                ai_result = analyze_garment_with_gemini(image_bytes)
                            break
                        except Exception as ai_err:
                            if "503" in str(ai_err) or "429" in str(ai_err):
                                if attempt < max_retries - 1:
                                    st.warning(f"⚠️ Hệ thống bận, đang tự động tìm kiếm lại sau {retry_delay} giây...")
                                    time.sleep(retry_delay)
                                    continue
                            raise ai_err

                    if not ai_result:
                        raise Exception("Không nhận được phản hồi từ hệ thống AI Vision.")
                        
                    st.session_state.search_ai_result = ai_result

                    # Chuyển đổi thông tin lập luận sang chuỗi ngữ nghĩa vector
                    text_for_embedding = ai_result.get("reason", ai_result["category"])

                    # =================================================
                    # STEP 2: IMAGE EMBEDDING (Đồng bộ xử lý text mã hóa)
                    # =================================================
                    with st.spinner("🧠 Đang tạo image embedding..."):
                        query_embedding = get_image_embedding(text_for_embedding)

                    # =================================================
                    # STEP 3: VECTOR SEARCH (Quét cơ sở dữ liệu)
                    # =================================================
                    with st.spinner("🔎 Đang tìm mã tương đồng..."):
                        results = search_similar_products(query_embedding)

                    # =================================================
                    # STEP 4: RANK & BOOST (Tối ưu thứ tự xếp hạng)
                    # =================================================
                    results = rank_results(results, ai_result["category"])
                    st.session_state.search_result = results

                except Exception as e:
                    st.error(f"Lỗi tìm kiếm: {str(e)}")

        # ---------------------------------------------------------
        # DISPLAY AI RESULT (Hiển thị thông số cấu trúc bóc tách)
        # ---------------------------------------------------------
        ai_result = st.session_state.search_ai_result
        if ai_result:
            st.divider()
            st.markdown("### 🤖 Kết quả AI")

            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.metric("Category AI", ai_result["category"])
            with c2:
                st.metric("Confidence", f"{ai_result['confidence']:.0f}%")
            with c3:
                st.metric("One Piece", "YES" if ai_result["one_piece"] else "NO")
            with c4:
                st.metric("Cargo Pocket", "YES" if ai_result["cargo_pockets"] else "NO")

            if ai_result.get("reason"):
                st.info("🧠 " + ai_result["reason"])

        # ---------------------------------------------------------
        # DISPLAY SEARCH RESULTS (Hiển thị dạng Grid)
        # ---------------------------------------------------------
        results = st.session_state.search_result
        if results is not None:
            st.divider()
            st.markdown("### 🎯 Mã hàng tương đồng")

            if not results:
                st.warning("Không tìm thấy mã hàng tương đồng trong kho.")
            else:
                display_results = results[:8]
                columns = st.columns(min(4, len(display_results)))

                for index, item in enumerate(display_results):
                    with columns[index % len(columns)]:
                        st.markdown("---")

                        # IMAGE public URL
                        image_url = item.get("image_url")
                        if image_url:
                            try:
                                st.image(image_url, use_container_width=True)
                            except Exception:
                                pass

                        # PRODUCT CODE
                        st.markdown(f"### 🏷️ {item.get('product_code', 'N/A')}")

                        # SIMILARITY
                        similarity = float(item.get("similarity", 0))
                        st.metric("Độ tương đồng", f"{similarity * 100:.2f}%")

                        # CATEGORIES
                        st.write("📦 Kho:", item.get("category", "N/A"))
                        st.write("🤖 AI:", item.get("ai_category", "N/A"))



# =====================================================================
# TAB 2: NẠP KHO HÀNG LOẠT (ĐÃ ĐỒNG BỘ TEXT EMBEDDING & CHỐNG LỖI QUÁ TẢI)
# =====================================================================
with tab_storage:
    st.subheader("📦 Nạp mã hàng vào kho")
    st.info("Category kho là phân loại nghiệp vụ. AI vẫn tự nhận dạng và lưu thêm AI category.")
    
    # --- DÒNG HÀNG KHO ---
    storage_category = st.selectbox(
        "📦 Chọn dòng hàng để lưu kho", 
        CATEGORY_OPTIONS, 
        key="storage_category"
    )

    # --- WIDGET UPLOAD ---
    uploaded_files = st.file_uploader(
        "📷 Chọn ảnh mã hàng", 
        type=["jpg", "jpeg", "png", "webp"], 
        accept_multiple_files=True, 
        key="storage_uploader"
    )

    # Nạp tệp mới vào hàng đợi session_state
    if uploaded_files:
        current_names = [f.name for f in st.session_state.pending_upload_files]
        for file in uploaded_files:
            if file.name not in current_names: 
                st.session_state.pending_upload_files.append(file)

    # --- HỦY DANH SÁCH CHỜ ---
    c1, _ = st.columns([1, 5])
    with c1:
        if st.button("🗑️ Xóa danh sách chờ", key="clear_pending_files"):
            st.session_state.pending_upload_files = []
            st.rerun()

    # --- XỬ LÝ HÀNG ĐỢI ---
    pending_files = st.session_state.pending_upload_files
    if pending_files:
        st.success(f"📂 Đang chờ **{len(pending_files)}** file để nạp kho.")
        
        # Xem trước ảnh hàng đợi dạng Grid nhỏ
        preview_cols = st.columns(min(5, len(pending_files)))
        for i, file in enumerate(pending_files):
            with preview_cols[i % len(preview_cols)]: 
                st.image(file, caption=file.name, use_container_width=True)

        st.divider()
        
        # Kích hoạt tiến trình đồng bộ
        if st.button(
            "📤 BẮT ĐẦU NẠP TOÀN BỘ VÀO KHO", 
            type="primary", 
            use_container_width=True, 
            key="start_storage_upload"
        ):
            import time  # Thêm thư viện thời gian để tạo độ trễ an toàn
            
            total = len(pending_files)
            success_count = 0
            failed_count = 0

            progress = st.progress(0)
            status = st.empty()
            upload_results = []

            for index, file in enumerate(pending_files):
                product_code = product_code_from_filename(file.name)
                status.write(f"⏳ {index + 1}/{total} — Xử lý mã: `{product_code}`")
                
                try:
                    image_bytes = file.getvalue()

                    # STEP 1: AI VISION
                    status.write(f"🤖 AI đang phân tích rập `{product_code}`...")
                    ai_result = analyze_garment_with_gemini(image_bytes)
                    ai_category = ai_result["category"]
                    
                    # Bóc tách text ngữ nghĩa để chuẩn bị tạo không gian vector
                    text_for_embedding = ai_result.get("reason", ai_category)

                    # STEP 2: IMAGE EMBEDDING (Đồng bộ: Truyền Text, KHÔNG truyền byte ảnh thô)
                    status.write(f"🧠 Tạo đặc trưng vector ngữ nghĩa cho `{product_code}`...")
                    embedding = get_image_embedding(text_for_embedding)

                    # STEP 3: STORAGE
                    status.write(f"☁️ Upload tệp hình ảnh `{product_code}` lên Storage...")
                    image_url = upload_image_to_storage(image_bytes, file.name)

                    # STEP 4: DATABASE
                    status.write(f"💾 Thực thi đồng bộ dữ liệu `{product_code}` vào Database...")
                    save_product(
                        product_code=product_code,
                        image_url=image_url,
                        category=storage_category,
                        ai_category=ai_category,
                        ai_result=ai_result,
                        embedding=embedding,
                        filename=file.name
                    )

                    success_count += 1
                    upload_results.append({
                        "product_code": product_code, 
                        "category": storage_category, 
                        "ai_category": ai_category, 
                        "confidence": ai_result["confidence"], 
                        "status": "OK"
                    })
                    
                except Exception as e:
                    failed_count += 1
                    upload_results.append({
                        "product_code": product_code, 
                        "category": storage_category, 
                        "ai_category": "", 
                        "confidence": 0, 
                        "status": str(e)
                    })
                    st.error(f"❌ Mã hàng `{file.name}` gặp lỗi: {str(e)}")
                    
                # Cập nhật trạng thái thanh tiến trình
                progress.progress(int((index + 1) / total * 100))
                
                # CHÈN ĐỘ TRỄ GIÃN CÁCH để không làm nghẽn máy chủ API của Google (Free Tier)
                if index < total - 1:
                    time.sleep(4.5)

            status.empty()
            st.session_state.last_upload_result = upload_results
            st.session_state.pending_upload_files = []

            if success_count: 
                st.success(f"🎉 Đã nạp thành công **{success_count}/{total}** mã hàng vào hệ thống.")
            if failed_count: 
                st.warning(f"⚠️ Phát hiện **{failed_count}** tệp tin xử lý thất bại.")
            st.rerun()

    # --- IN NHẬT KÝ BÁO CÁO (LOGS) ---
    if st.session_state.last_upload_result:
        st.divider()
        st.markdown("### 📋 Kết quả nạp kho")
        
        for item in st.session_state.last_upload_result:
            if item["status"] == "OK": 
                st.success(
                    f"✅ {item['product_code']} — "
                    f"Kho: {item['category']} — "
                    f"AI: {item['ai_category']} — "
                    f"Độ tự tin: {item['confidence']:.0f}%"
                )
            else: 
                st.error(
                    f"❌ {item['product_code']} — "
                    f"Kho: {item['category']} — "
                    f"Lỗi hệ thống: {item['status']}"
                )
                
        if st.button("🗑️ Xóa thông báo kết quả", key="clear_upload_result_report"):
            st.session_state.last_upload_result = None
            st.rerun()
