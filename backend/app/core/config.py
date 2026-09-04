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
VOYAGE_API_KEY = os.getenv("VOYAGE_API_KEY", "")
VOYAGE_EMBEDDING_MODEL = os.getenv("VOYAGE_EMBEDDING_MODEL", "")

EMAIL_MODE = os.getenv("EMAIL_MODE", "mock")
GMAIL_CLIENT_ID = os.getenv("GMAIL_CLIENT_ID", "")
GMAIL_CLIENT_SECRET = os.getenv("GMAIL_CLIENT_SECRET", "")
GMAIL_REDIRECT_URI = os.getenv("GMAIL_REDIRECT_URI", "")

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
