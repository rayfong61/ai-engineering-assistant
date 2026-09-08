import uuid
from datetime import UTC, datetime, timedelta

import httpx
import jwt
import pytest

from app.models import GmailCredential
from app.services import gmail_service


class _Response:
    """Minimal stand-in for httpx.Response, just enough for the code paths
    gmail_service touches (raise_for_status / json)."""

    def __init__(self, status_code=200, json_data=None):
        self.status_code = status_code
        self._json = json_data or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=None, response=self)

    def json(self):
        return self._json


@pytest.fixture(autouse=True)
def _gmail_env(monkeypatch):
    monkeypatch.setattr("app.services.gmail_service.GMAIL_CLIENT_ID", "test-client-id")
    monkeypatch.setattr("app.services.gmail_service.GMAIL_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setattr("app.services.gmail_service.GMAIL_REDIRECT_URI", "http://localhost:8000/api/gmail/callback")
    # A real Fernet key, generated once for tests -- not the production key.
    monkeypatch.setattr(
        "app.services.gmail_service.GMAIL_TOKEN_ENCRYPTION_KEY", "zJLq9x5m5f6r1c1p8s6b0v2s3t4u5w6x7y8z9A0b1C4="
    )


def test_authorize_url_returns_signed_state_bound_to_user(alice):
    url = gmail_service.build_authorize_url(alice["id"])

    assert "client_id=test-client-id" in url
    assert "scope=https" in url
    state = url.split("state=")[1].split("&")[0]
    assert gmail_service.verify_state(state) == alice["id"]


def test_authorize_url_fails_when_gmail_not_configured(monkeypatch, alice):
    monkeypatch.setattr("app.services.gmail_service.GMAIL_CLIENT_ID", "")

    with pytest.raises(ValueError):
        gmail_service.build_authorize_url(alice["id"])


def test_verify_state_rejects_expired_token(alice):
    expired = jwt.encode(
        {"sub": alice["id"], "exp": datetime.now(UTC) - timedelta(seconds=1)},
        "test-client-secret",
        algorithm="HS256",
    )

    with pytest.raises(ValueError):
        gmail_service.verify_state(expired)


def test_verify_state_rejects_garbage():
    with pytest.raises(ValueError):
        gmail_service.verify_state("not-a-jwt")


def test_callback_success_upserts_credential(db_session, alice, monkeypatch):
    state = gmail_service.make_state(alice["id"])

    def fake_post(url, data=None, timeout=None):
        assert url == gmail_service.GOOGLE_TOKEN_URL
        return _Response(json_data={"access_token": "at-1", "refresh_token": "rt-1"})

    def fake_get(url, headers=None, timeout=None):
        return _Response(json_data={"email": "connected@example.com"})

    monkeypatch.setattr("app.services.gmail_service.httpx.post", fake_post)
    monkeypatch.setattr("app.services.gmail_service.httpx.get", fake_get)

    user_id = gmail_service.handle_callback(db_session, "auth-code", state)

    assert user_id == alice["id"]
    credential = db_session.get(GmailCredential, uuid.UUID(alice["id"]))
    assert credential is not None
    assert credential.gmail_email == "connected@example.com"
    assert credential.encrypted_refresh_token != "rt-1"  # must be encrypted, not plaintext
    assert gmail_service._decrypt(credential.encrypted_refresh_token) == "rt-1"


def test_callback_profile_lookup_failure_is_non_fatal(db_session, alice, monkeypatch):
    state = gmail_service.make_state(alice["id"])

    monkeypatch.setattr(
        "app.services.gmail_service.httpx.post",
        lambda url, data=None, timeout=None: _Response(
            json_data={"access_token": "at-1", "refresh_token": "rt-1"}
        ),
    )

    def fake_get(url, headers=None, timeout=None):
        raise httpx.HTTPError("profile scope not authorized")

    monkeypatch.setattr("app.services.gmail_service.httpx.get", fake_get)

    gmail_service.handle_callback(db_session, "auth-code", state)

    credential = db_session.get(GmailCredential, uuid.UUID(alice["id"]))
    assert credential is not None
    assert credential.gmail_email is None


def test_callback_missing_refresh_token_raises(db_session, alice, monkeypatch):
    state = gmail_service.make_state(alice["id"])
    monkeypatch.setattr(
        "app.services.gmail_service.httpx.post",
        lambda url, data=None, timeout=None: _Response(json_data={"access_token": "at-1"}),
    )

    with pytest.raises(ValueError):
        gmail_service.handle_callback(db_session, "auth-code", state)


def test_callback_invalid_state_raises(db_session):
    with pytest.raises(ValueError):
        gmail_service.handle_callback(db_session, "auth-code", "garbage-state")


def test_status_reports_connected_and_disconnected(db_session, alice):
    assert gmail_service.get_status(db_session, uuid.UUID(alice["id"])) == {
        "connected": False,
        "gmail_email": None,
    }

    db_session.add(
        GmailCredential(
            user_id=uuid.UUID(alice["id"]),
            gmail_email="a@example.com",
            encrypted_refresh_token=gmail_service._encrypt("rt"),
        )
    )
    db_session.flush()

    assert gmail_service.get_status(db_session, uuid.UUID(alice["id"])) == {
        "connected": True,
        "gmail_email": "a@example.com",
    }


def test_disconnect_removes_credential(db_session, alice):
    db_session.add(
        GmailCredential(
            user_id=uuid.UUID(alice["id"]),
            gmail_email="a@example.com",
            encrypted_refresh_token=gmail_service._encrypt("rt"),
        )
    )
    db_session.flush()

    gmail_service.disconnect(db_session, uuid.UUID(alice["id"]))

    assert db_session.get(GmailCredential, uuid.UUID(alice["id"])) is None


def test_send_email_no_credential_returns_failed_not_exception(db_session, alice):
    result = gmail_service.send_email(db_session, uuid.UUID(alice["id"]), "to@example.com", "s", "b")

    assert result["status"] == "failed"


def test_send_email_happy_path(db_session, alice, monkeypatch):
    db_session.add(
        GmailCredential(
            user_id=uuid.UUID(alice["id"]),
            gmail_email="a@example.com",
            encrypted_refresh_token=gmail_service._encrypt("rt-1"),
        )
    )
    db_session.flush()

    monkeypatch.setattr("app.services.gmail_service._refresh_access_token", lambda rt: "at-fresh")
    monkeypatch.setattr(
        "app.services.gmail_service.httpx.post",
        lambda url, headers=None, json=None, timeout=None: _Response(json_data={"id": "msg-1"}),
    )

    result = gmail_service.send_email(db_session, uuid.UUID(alice["id"]), "to@example.com", "subject", "body")

    assert result["status"] == "sent"


def test_send_email_refresh_failure_returns_failed_not_exception(db_session, alice, monkeypatch):
    db_session.add(
        GmailCredential(
            user_id=uuid.UUID(alice["id"]),
            gmail_email="a@example.com",
            encrypted_refresh_token=gmail_service._encrypt("rt-1"),
        )
    )
    db_session.flush()

    def raise_refresh(rt):
        raise httpx.HTTPStatusError("invalid_grant", request=None, response=_Response(status_code=400))

    monkeypatch.setattr("app.services.gmail_service._refresh_access_token", raise_refresh)

    result = gmail_service.send_email(db_session, uuid.UUID(alice["id"]), "to@example.com", "subject", "body")

    assert result["status"] == "failed"


def test_send_email_send_failure_returns_failed_not_exception(db_session, alice, monkeypatch):
    db_session.add(
        GmailCredential(
            user_id=uuid.UUID(alice["id"]),
            gmail_email="a@example.com",
            encrypted_refresh_token=gmail_service._encrypt("rt-1"),
        )
    )
    db_session.flush()

    monkeypatch.setattr("app.services.gmail_service._refresh_access_token", lambda rt: "at-fresh")
    monkeypatch.setattr(
        "app.services.gmail_service.httpx.post",
        lambda url, headers=None, json=None, timeout=None: _Response(status_code=500),
    )

    result = gmail_service.send_email(db_session, uuid.UUID(alice["id"]), "to@example.com", "subject", "body")

    assert result["status"] == "failed"


def test_authorize_url_route_requires_auth(client):
    response = client.get("/api/gmail/authorize-url")
    assert response.status_code == 401


def test_authorize_url_route_returns_url(client, current_user_override, alice, _gmail_env):
    current_user_override(alice)
    response = client.get("/api/gmail/authorize-url")
    assert response.status_code == 200
    assert "accounts.google.com" in response.json()["url"]


def test_status_route_reflects_db_state(client, db_session, current_user_override, alice):
    current_user_override(alice)
    assert client.get("/api/gmail/status").json() == {"connected": False, "gmail_email": None}

    db_session.add(
        GmailCredential(
            user_id=uuid.UUID(alice["id"]),
            gmail_email="a@example.com",
            encrypted_refresh_token=gmail_service._encrypt("rt"),
        )
    )
    db_session.commit()

    assert client.get("/api/gmail/status").json() == {"connected": True, "gmail_email": "a@example.com"}


def test_disconnect_route_removes_credential(client, db_session, current_user_override, alice):
    db_session.add(
        GmailCredential(
            user_id=uuid.UUID(alice["id"]),
            gmail_email="a@example.com",
            encrypted_refresh_token=gmail_service._encrypt("rt"),
        )
    )
    db_session.commit()
    current_user_override(alice)

    response = client.post("/api/gmail/disconnect")

    assert response.status_code == 200
    assert db_session.get(GmailCredential, uuid.UUID(alice["id"])) is None


def test_callback_route_missing_params_redirects_with_error(client):
    response = client.get("/api/gmail/callback", follow_redirects=False)

    assert response.status_code in (302, 307)
    assert "gmail=error" in response.headers["location"]


def test_callback_route_success_redirects_connected(client, alice, monkeypatch):
    state = gmail_service.make_state(alice["id"])
    monkeypatch.setattr(
        "app.services.gmail_service.httpx.post",
        lambda url, data=None, timeout=None: _Response(
            json_data={"access_token": "at-1", "refresh_token": "rt-1"}
        ),
    )
    monkeypatch.setattr(
        "app.services.gmail_service.httpx.get",
        lambda url, headers=None, timeout=None: _Response(json_data={"email": "a@example.com"}),
    )

    response = client.get(
        f"/api/gmail/callback?code=auth-code&state={state}", follow_redirects=False
    )

    assert response.status_code in (302, 307)
    assert "gmail=connected" in response.headers["location"]
