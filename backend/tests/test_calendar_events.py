import uuid

import pytest

from app.models import CalendarEventLog
from app.services import calendar_event_service

_START = "2026-09-16T14:00:00+08:00"
_END = "2026-09-16T15:00:00+08:00"


def _make_draft(db_session, project_id, user_id, **overrides):
    kwargs = {
        "summary": "會勘",
        "start_datetime": _START,
        "end_datetime": _END,
        "description": None,
        "attendees": None,
    }
    kwargs.update(overrides)
    return calendar_event_service.save_draft(db_session, project_id, uuid.UUID(user_id), **kwargs)


def test_non_member_cannot_create_calendar_event(client, current_user_override, alice, bob):
    current_user_override(alice)
    project_id = client.post("/api/projects", json={"name": "T3"}).json()["id"]

    current_user_override(bob)
    response = client.post(
        f"/api/projects/{project_id}/calendar-events/create",
        json={"calendar_event_log_id": "00000000-0000-0000-0000-000000000000"},
    )

    assert response.status_code == 403


def test_confirm_and_create_missing_draft_returns_404(client, current_user_override, alice):
    current_user_override(alice)
    project_id = client.post("/api/projects", json={"name": "T3"}).json()["id"]

    response = client.post(
        f"/api/projects/{project_id}/calendar-events/create",
        json={"calendar_event_log_id": "00000000-0000-0000-0000-000000000000"},
    )

    assert response.status_code == 404


def test_confirm_and_create_happy_path(client, db_session, current_user_override, alice, monkeypatch):
    monkeypatch.setattr(
        "app.tools.create_calendar_event.run",
        lambda **kwargs: {"status": "created", "message": "ok", "google_event_id": "evt-1"},
    )
    current_user_override(alice)
    project_id = client.post("/api/projects", json={"name": "T3"}).json()["id"]
    draft = _make_draft(db_session, project_id, alice["id"])

    response = client.post(
        f"/api/projects/{project_id}/calendar-events/create",
        json={"calendar_event_log_id": str(draft.id)},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "created"
    assert body["google_event_id"] == "evt-1"

    event_log = db_session.query(CalendarEventLog).filter_by(id=draft.id).one()
    assert event_log.status == "created"
    assert event_log.google_event_id == "evt-1"


def test_confirm_and_create_already_created_returns_409(client, db_session, current_user_override, alice, monkeypatch):
    monkeypatch.setattr(
        "app.tools.create_calendar_event.run",
        lambda **kwargs: {"status": "created", "message": "ok", "google_event_id": "evt-1"},
    )
    current_user_override(alice)
    project_id = client.post("/api/projects", json={"name": "T3"}).json()["id"]
    draft = _make_draft(db_session, project_id, alice["id"])

    client.post(
        f"/api/projects/{project_id}/calendar-events/create",
        json={"calendar_event_log_id": str(draft.id)},
    )
    response = client.post(
        f"/api/projects/{project_id}/calendar-events/create",
        json={"calendar_event_log_id": str(draft.id)},
    )

    assert response.status_code == 409


def test_confirm_and_create_tool_failure_marks_failed(client, db_session, current_user_override, alice, monkeypatch):
    def _raise(**kwargs):
        raise RuntimeError("Calendar API unreachable")

    monkeypatch.setattr("app.tools.create_calendar_event.run", _raise)
    current_user_override(alice)
    project_id = client.post("/api/projects", json={"name": "T3"}).json()["id"]
    draft = _make_draft(db_session, project_id, alice["id"])

    response = client.post(
        f"/api/projects/{project_id}/calendar-events/create",
        json={"calendar_event_log_id": str(draft.id)},
    )

    assert response.status_code == 502
    assert db_session.query(CalendarEventLog).filter_by(id=draft.id).one().status == "failed"


def test_save_draft_rejects_end_before_start(db_session, current_user_override, alice, client):
    current_user_override(alice)
    project_id = client.post("/api/projects", json={"name": "T3"}).json()["id"]

    with pytest.raises(ValueError):
        _make_draft(db_session, project_id, alice["id"], start_datetime=_END, end_datetime=_START)


def test_save_draft_rejects_missing_timezone(db_session, current_user_override, alice, client):
    current_user_override(alice)
    project_id = client.post("/api/projects", json={"name": "T3"}).json()["id"]

    with pytest.raises(ValueError):
        _make_draft(db_session, project_id, alice["id"], start_datetime="2026-09-16T14:00:00")


def test_save_draft_rejects_unparseable_datetime(db_session, current_user_override, alice, client):
    current_user_override(alice)
    project_id = client.post("/api/projects", json={"name": "T3"}).json()["id"]

    with pytest.raises(ValueError):
        _make_draft(db_session, project_id, alice["id"], start_datetime="下週三下午兩點")


def test_save_draft_rejects_malformed_attendee_email(db_session, current_user_override, alice, client):
    current_user_override(alice)
    project_id = client.post("/api/projects", json={"name": "T3"}).json()["id"]

    with pytest.raises(ValueError):
        _make_draft(db_session, project_id, alice["id"], attendees=["not-an-email"])
