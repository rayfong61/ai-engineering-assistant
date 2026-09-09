import uuid

import httpx

from app.models import GmailCredential
from app.services import calendar_service, gmail_service


class _Response:
    """Minimal stand-in for httpx.Response -- matches tests/test_gmail.py's
    _Response, just enough for the code paths calendar_service touches
    (raise_for_status / json)."""

    def __init__(self, status_code=200, json_data=None):
        self.status_code = status_code
        self._json = json_data or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=None, response=self)

    def json(self):
        return self._json


def test_create_event_no_credential_returns_failed_not_exception(db_session, alice):
    result = calendar_service.create_event(
        db_session, uuid.UUID(alice["id"]), "會勘", "2026-09-16T14:00:00+08:00", "2026-09-16T15:00:00+08:00"
    )

    assert result["status"] == "failed"
    assert result["google_event_id"] is None


def test_create_event_happy_path(db_session, alice, monkeypatch):
    db_session.add(
        GmailCredential(
            user_id=uuid.UUID(alice["id"]),
            gmail_email="a@example.com",
            encrypted_refresh_token=gmail_service._encrypt("rt-1"),
        )
    )
    db_session.flush()

    monkeypatch.setattr("app.services.calendar_service._refresh_access_token", lambda rt: "at-fresh")
    monkeypatch.setattr(
        "app.services.calendar_service.httpx.post",
        lambda url, headers=None, params=None, json=None, timeout=None: _Response(json_data={"id": "evt-1"}),
    )

    result = calendar_service.create_event(
        db_session, uuid.UUID(alice["id"]), "會勘", "2026-09-16T14:00:00+08:00", "2026-09-16T15:00:00+08:00"
    )

    assert result["status"] == "created"
    assert result["google_event_id"] == "evt-1"


def test_create_event_refresh_failure_returns_failed_not_exception(db_session, alice, monkeypatch):
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

    monkeypatch.setattr("app.services.calendar_service._refresh_access_token", raise_refresh)

    result = calendar_service.create_event(
        db_session, uuid.UUID(alice["id"]), "會勘", "2026-09-16T14:00:00+08:00", "2026-09-16T15:00:00+08:00"
    )

    assert result["status"] == "failed"
    assert result["google_event_id"] is None


def test_create_event_send_failure_returns_failed_not_exception(db_session, alice, monkeypatch):
    # Also covers the "credential connected before calendar.events was
    # added" case -- Google returns a 403 insufficient-scope error the same
    # shape as any other Calendar API failure, no special-casing needed.
    db_session.add(
        GmailCredential(
            user_id=uuid.UUID(alice["id"]),
            gmail_email="a@example.com",
            encrypted_refresh_token=gmail_service._encrypt("rt-1"),
        )
    )
    db_session.flush()

    monkeypatch.setattr("app.services.calendar_service._refresh_access_token", lambda rt: "at-fresh")
    monkeypatch.setattr(
        "app.services.calendar_service.httpx.post",
        lambda url, headers=None, params=None, json=None, timeout=None: _Response(status_code=403),
    )

    result = calendar_service.create_event(
        db_session, uuid.UUID(alice["id"]), "會勘", "2026-09-16T14:00:00+08:00", "2026-09-16T15:00:00+08:00"
    )

    assert result["status"] == "failed"
    assert result["google_event_id"] is None
