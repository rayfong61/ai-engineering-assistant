from functools import lru_cache

from supabase import Client, create_client

from app.core.config import SUPABASE_SERVICE_ROLE_KEY, SUPABASE_URL


@lru_cache
def get_supabase() -> Client:
    """Server-side Supabase client using the service role key.

    Used for Storage (PDF/image buckets, from Day 2 onward) and any
    Auth-admin calls only. Table data access does NOT go through this —
    see app/core/database.py (SQLAlchemy, direct Postgres connection)
    for that. The Data API/PostgREST layer this client would otherwise
    use for table queries is disabled on the Supabase project.
    Never expose SUPABASE_SERVICE_ROLE_KEY to the frontend.
    """
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
