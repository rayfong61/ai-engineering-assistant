from functools import lru_cache

import jwt
from fastapi import Header, HTTPException
from jwt import PyJWKClient

from app.core.config import SUPABASE_URL


@lru_cache
def _jwk_client() -> PyJWKClient:
    # Supabase signs user session tokens with a per-project asymmetric key
    # (ES256/RS256) published at this well-known JWKS endpoint — this works
    # unchanged for both the local Supabase CLI stack and the cloud
    # project, since both expose the same endpoint shape.
    return PyJWKClient(f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json")


def get_current_user(authorization: str | None = Header(default=None)) -> dict:
    """Resolve the current user from the Supabase-issued JWT.

    The frontend never sends a user_id directly — identity always comes
    from this decoded token, per spec2.md section 8.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")

    token = authorization.removeprefix("Bearer ").strip()
    try:
        signing_key = _jwk_client().get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["ES256", "RS256"],
            audience="authenticated",
            # Tolerates small clock drift between this container and
            # Supabase's auth server -- without it, a token's iat can land
            # in the future from this container's perspective and get
            # rejected as ImmatureSignatureError moments after being issued.
            leeway=30,
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from exc

    return {"id": payload["sub"], "email": payload.get("email")}
