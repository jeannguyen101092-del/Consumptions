# ============================================================
# 🔐 SECRET LOADER
# Không chứa API KEY trực tiếp
# ============================================================

def get_secret_value(*names):

    for name in names:

        try:
            value = st.secrets.get(name)

            if value:
                return value

        except Exception:
            pass

    return None


SUPABASE_URL = get_secret_value(
    "SUPABASE_URL",
    "SUPABASE_PROJECT_URL",
    "supabase_url",
    "SUPABASE_URL_KEY"
)

SUPABASE_KEY = get_secret_value(
    "SUPABASE_KEY",
    "SUPABASE_ANON_KEY",
    "SUPABASE_SERVICE_KEY",
    "supabase_key",
    "SUPABASE_ANON"
)

HF_TOKEN = get_secret_value(
    "HF_TOKEN",
    "HUGGINGFACE_TOKEN",
    "HF_API_TOKEN",
    "HUGGINGFACE_API_KEY",
    "huggingface_token"
)
