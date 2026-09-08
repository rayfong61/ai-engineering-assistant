import os

from dotenv import load_dotenv

load_dotenv()

# SUPABASE_URL doubles as the JWKS endpoint base for verifying user
# session tokens (app/core/auth.py) — no shared secret needed.
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

# Direct Postgres connection (SQLAlchemy + Alembic), used for all table
# access. Points at the local Supabase CLI stack (`supabase start`) during
# development and at Supabase's own Postgres connection string (Project
# Settings > Database) once the app is ready to run against the cloud
# project — same schema, same models, just a different DATABASE_URL.
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@host.docker.internal:54322/postgres",
)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-5")

VOYAGE_API_KEY = os.getenv("VOYAGE_API_KEY", "")
# Must match document.py's EMBEDDING_DIM (1024) -- confirmed against Voyage
# AI's docs before Day 2 ingestion, per spec2.md section 9.
VOYAGE_EMBEDDING_MODEL = os.getenv("VOYAGE_EMBEDDING_MODEL", "voyage-4-large")

# Fixed bucket name (spec2.md section 10) -- not user-configurable.
STORAGE_BUCKET = "engineering-documents"

EMAIL_MODE = os.getenv("EMAIL_MODE", "mock")
GMAIL_CLIENT_ID = os.getenv("GMAIL_CLIENT_ID", "")
GMAIL_CLIENT_SECRET = os.getenv("GMAIL_CLIENT_SECRET", "")
GMAIL_REDIRECT_URI = os.getenv("GMAIL_REDIRECT_URI", "")
# Symmetric key (Fernet) for encrypting gmail_credentials.encrypted_refresh_token
# at rest -- generate with:
# python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
GMAIL_TOKEN_ENCRYPTION_KEY = os.getenv("GMAIL_TOKEN_ENCRYPTION_KEY", "")

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

# ── CWA (中央氣象署開放資料平台，天氣查詢 MCP 工具) ─────────────────
CWA_API_KEY = os.getenv("CWA_API_KEY", "")

# GIS 案址查詢工具的地理編碼改用 OpenStreetMap Nominatim（免申請、免金鑰，
# 見 app/services/geo_service.py）——TGOS 的門牌位置比對服務僅開放政府機關/
# 公營事業/學術及法人團體/公司行號申請，個人無法申請，故不採用，這裡不需要
# 對應的 API key 常數。

# The mcp-server container, reached over the internal Docker Compose network
# -- never given a published port the frontend/browser can reach (spec2.md
# section 21/30). The backend's Agent is its only client.
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://mcp-server:8001/mcp")
