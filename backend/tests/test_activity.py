from app.models import ActivityLog
from app.services.activity_service import log_activity


def test_log_activity_records_project_created_event(client, db_session, current_user_override, alice):
    current_user_override(alice)

    project_id = client.post("/api/projects", json={"name": "T3"}).json()["id"]

    event = (
        db_session.query(ActivityLog)
        .filter(ActivityLog.project_id == project_id, ActivityLog.event_type == "project_created")
        .one()
    )
    assert str(event.user_id) == alice["id"]
    assert event.detail == "T3"


def test_log_activity_failure_does_not_abort_caller_transaction(db_session):
    """log_activity wraps its insert in a SAVEPOINT specifically so a
    logging failure can't poison the caller's own transaction. Passing an
    invalid event_type trips the DB's CheckConstraint -- if the SAVEPOINT
    wrapping were missing, this would abort db_session entirely and even
    an unrelated subsequent query would fail."""
    log_activity(db_session, None, "00000000-0000-0000-0000-000000000001", "not_a_real_event")

    # The session must still be usable after the failed insert.
    assert db_session.query(ActivityLog).count() >= 0


def test_list_activity_requires_membership(client, current_user_override, alice, bob):
    current_user_override(alice)
    project_id = client.post("/api/projects", json={"name": "T3"}).json()["id"]

    current_user_override(bob)
    response = client.get(f"/api/projects/{project_id}/activity")

    assert response.status_code == 403


def test_list_activity_scopes_to_project_plus_own_login_events(
    client, db_session, current_user_override, alice, bob
):
    current_user_override(alice)
    alice_project_id = client.post("/api/projects", json={"name": "T3-alice"}).json()["id"]
    client.get("/api/auth/me")  # records a user_logged_in event for alice (project_id=None)

    current_user_override(bob)
    bob_project_id = client.post("/api/projects", json={"name": "T3-bob"}).json()["id"]

    current_user_override(alice)
    response = client.get(f"/api/projects/{alice_project_id}/activity")

    assert response.status_code == 200
    body = response.json()
    event_types = {e["event_type"] for e in body}
    assert "project_created" in event_types
    assert "user_logged_in" in event_types
    # Bob's project-scoped event must never leak into Alice's view.
    assert all(e["project_id"] in (alice_project_id, None) for e in body)
    assert bob_project_id not in {e["project_id"] for e in body}
