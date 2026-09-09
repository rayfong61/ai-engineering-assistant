import base64
import uuid
from datetime import UTC, datetime, timedelta
from email.mime.text import MIMEText
from urllib.parse import urlencode

import httpx
import jwt
from cryptography.fernet import Fernet
from sqlalchemy.orm import Session

from app.core.config import (
    GMAIL_CLIENT_ID,
    GMAIL_CLIENT_SECRET,
    GMAIL_REDIRECT_URI,
    GMAIL_TOKEN_ENCRYPTION_KEY,
)
from app.models import GmailCredential

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
GMAIL_SEND_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"
GMAIL_SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"
# calendar.events was added on top of the original gmail.send-only grant (a
# deliberate exception to CLAUDE.md rule #2, approved -- see CLAUDE.md's
# "Deviation from this file's own rule #2") so app/services/calendar_service.py
# can create real Calendar events using this exact same OAuth
# client/credential/refresh-token store, not a second OAuth flow. A user who
# connected before this change must disconnect+reconnect to actually be
# granted it -- Google doesn't retroactively add scope to an existing
# refresh token.
CALENDAR_EVENTS_SCOPE = "https://www.googleapis.com/auth/calendar.events"
# Users can connect a Gmail account that differs from their Supabase-login
# Google account, so the login email can't stand in for it -- "email" is
# requested (on top of gmail.send + calendar.events) purely so
# /oauth2/v2/userinfo can report which address was actually connected. This
# is the minimal scope for that: it does not grant any Gmail-data access
# beyond what gmail.send already did.
GMAIL_OAUTH_SCOPES = f"{GMAIL_SEND_SCOPE} {CALENDAR_EVENTS_SCOPE} email"
STATE_TTL_SECONDS = 300

_HTTP_TIMEOUT = 10


def make_state(user_id: str) -> str:
    """Short-lived CSRF token binding the OAuth redirect round trip back to
    the user who started it -- the callback is a top-level browser redirect
    from Google with no Authorization header, so identity can't come from
    the usual JWT dependency. Reuses GMAIL_CLIENT_SECRET as the signing key
    rather than a dedicated secret -- this token is only ever a 5-minute
    CSRF nonce, not a long-lived credential."""
    payload = {"sub": user_id, "exp": datetime.now(UTC) + timedelta(seconds=STATE_TTL_SECONDS)}
    return jwt.encode(payload, GMAIL_CLIENT_SECRET, algorithm="HS256")


def verify_state(state: str) -> str:
    try:
        payload = jwt.decode(state, GMAIL_CLIENT_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise ValueError("Invalid or expired OAuth state") from exc
    return payload["sub"]


def build_authorize_url(user_id: str) -> str:
    if not GMAIL_CLIENT_ID:
        raise ValueError("Gmail 尚未設定（缺少 GMAIL_CLIENT_ID）")

    params = {
        "client_id": GMAIL_CLIENT_ID,
        "redirect_uri": GMAIL_REDIRECT_URI,
        "response_type": "code",
        "scope": GMAIL_OAUTH_SCOPES,
        "access_type": "offline",
        "prompt": "consent",
        "state": make_state(user_id),
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


def _encrypt(token: str) -> str:
    return Fernet(GMAIL_TOKEN_ENCRYPTION_KEY.encode()).encrypt(token.encode()).decode()


def _decrypt(token: str) -> str:
    return Fernet(GMAIL_TOKEN_ENCRYPTION_KEY.encode()).decrypt(token.encode()).decode()


# _decrypt and _refresh_access_token (below) are imported directly by
# app/services/calendar_service.py -- deliberate, not an accidental leak.
# Both services share one OAuth grant/credential store on purpose (see
# GMAIL_OAUTH_SCOPES above), so sharing these two helpers is the minimal
# change; don't duplicate them there, and don't "fix" this by making them
# public without a real second reason.


def handle_callback(db: Session, code: str, state: str) -> str:
    user_id = verify_state(state)

    response = httpx.post(
        GOOGLE_TOKEN_URL,
        data={
            "code": code,
            "client_id": GMAIL_CLIENT_ID,
            "client_secret": GMAIL_CLIENT_SECRET,
            "redirect_uri": GMAIL_REDIRECT_URI,
            "grant_type": "authorization_code",
        },
        timeout=_HTTP_TIMEOUT,
    )
    response.raise_for_status()
    tokens = response.json()

    refresh_token = tokens.get("refresh_token")
    if not refresh_token:
        raise ValueError("Google 未回傳 refresh_token（確認 access_type=offline/prompt=consent 有生效）")

    # Best-effort only -- a failure here must not block storing the refresh
    # token; the Settings page just shows "已連接" without an address in
    # that case. Uses the standard OAuth2 userinfo endpoint (authorized by
    # the "email" scope requested above), not the Gmail API profile
    # endpoint -- that one needs gmail.readonly/modify/metadata, which
    # gmail.send alone never authorizes.
    gmail_email = None
    try:
        userinfo = httpx.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
            timeout=_HTTP_TIMEOUT,
        )
        userinfo.raise_for_status()
        gmail_email = userinfo.json().get("email")
    except httpx.HTTPError:
        gmail_email = None

    user_uuid = uuid.UUID(user_id)
    encrypted = _encrypt(refresh_token)
    credential = db.get(GmailCredential, user_uuid)
    if credential:
        credential.encrypted_refresh_token = encrypted
        credential.gmail_email = gmail_email
        credential.updated_at = datetime.now(UTC)
    else:
        db.add(
            GmailCredential(
                user_id=user_uuid,
                gmail_email=gmail_email,
                encrypted_refresh_token=encrypted,
            )
        )
    db.commit()
    return user_id


def get_status(db: Session, user_id: uuid.UUID) -> dict:
    credential = db.get(GmailCredential, user_id)
    if not credential:
        return {"connected": False, "gmail_email": None}
    return {"connected": True, "gmail_email": credential.gmail_email}


def disconnect(db: Session, user_id: uuid.UUID) -> None:
    credential = db.get(GmailCredential, user_id)
    if credential:
        db.delete(credential)
        db.commit()


def _refresh_access_token(refresh_token: str) -> str:
    response = httpx.post(
        GOOGLE_TOKEN_URL,
        data={
            "client_id": GMAIL_CLIENT_ID,
            "client_secret": GMAIL_CLIENT_SECRET,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
        timeout=_HTTP_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()["access_token"]


def send_email(db: Session, user_id: uuid.UUID, to: str, subject: str, body: str) -> dict:
    """Never raises -- the only caller (app.tools.send_email) depends on
    this always returning the {"status": ..., "message": ...} shape."""
    credential = db.get(GmailCredential, user_id)
    if not credential:
        return {"status": "failed", "message": "Gmail 尚未連接，請先於 Settings 頁面完成 Gmail 授權"}

    try:
        refresh_token = _decrypt(credential.encrypted_refresh_token)
        access_token = _refresh_access_token(refresh_token)

        message = MIMEText(body)
        message["to"] = to
        message["subject"] = subject
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

        response = httpx.post(
            GMAIL_SEND_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            json={"raw": raw},
            timeout=_HTTP_TIMEOUT,
        )
        response.raise_for_status()
    except Exception as exc:
        return {"status": "failed", "message": f"Gmail 寄送失敗：{exc}"}

    return {"status": "sent", "message": f"已透過 Gmail 寄送給 {to}"}
