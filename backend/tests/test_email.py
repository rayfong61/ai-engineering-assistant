from app.models import EmailLog


def _monkeypatch_draft(monkeypatch, to="pm@example.com", subject="摘要", body="內容"):
    monkeypatch.setattr(
        "app.services.claude_service.generate_email_draft",
        lambda instruction, context: {"to": to, "subject": subject, "body": body},
    )


def test_non_member_cannot_preview_email(client, current_user_override, alice, bob):
    current_user_override(alice)
    project_id = client.post("/api/projects", json={"name": "T3"}).json()["id"]

    current_user_override(bob)
    response = client.post(
        f"/api/projects/{project_id}/email/preview", json={"instruction": "寄給 PM"}
    )

    assert response.status_code == 403


def test_non_member_cannot_send_email(client, current_user_override, alice, bob):
    current_user_override(alice)
    project_id = client.post("/api/projects", json={"name": "T3"}).json()["id"]

    current_user_override(bob)
    response = client.post(
        f"/api/projects/{project_id}/email/send",
        json={"email_log_id": "00000000-0000-0000-0000-000000000000"},
    )

    assert response.status_code == 403


def test_preview_email_creates_draft(client, db_session, current_user_override, alice, monkeypatch):
    _monkeypatch_draft(monkeypatch)
    current_user_override(alice)
    project_id = client.post("/api/projects", json={"name": "T3"}).json()["id"]

    response = client.post(
        f"/api/projects/{project_id}/email/preview", json={"instruction": "寄給 PM"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["recipient"] == "pm@example.com"
    assert body["status"] == "draft"

    email_log = db_session.query(EmailLog).filter_by(id=body["id"]).one()
    assert email_log.status == "draft"
    assert str(email_log.project_id) == project_id


def test_preview_email_with_invalid_conversation_returns_404(
    client, current_user_override, alice, monkeypatch
):
    _monkeypatch_draft(monkeypatch)
    current_user_override(alice)
    project_id = client.post("/api/projects", json={"name": "T3"}).json()["id"]

    response = client.post(
        f"/api/projects/{project_id}/email/preview",
        json={
            "instruction": "寄給 PM",
            "conversation_id": "00000000-0000-0000-0000-000000000000",
        },
    )

    assert response.status_code == 404


def test_send_email_happy_path(client, db_session, current_user_override, alice, monkeypatch):
    _monkeypatch_draft(monkeypatch)
    monkeypatch.setattr("app.mcp.client.call_tool", lambda name, args: {"status": "sent"})
    current_user_override(alice)
    project_id = client.post("/api/projects", json={"name": "T3"}).json()["id"]

    draft = client.post(
        f"/api/projects/{project_id}/email/preview", json={"instruction": "寄給 PM"}
    ).json()

    response = client.post(
        f"/api/projects/{project_id}/email/send", json={"email_log_id": draft["id"]}
    )

    assert response.status_code == 200
    assert response.json()["status"] == "sent"
    assert db_session.query(EmailLog).filter_by(id=draft["id"]).one().status == "sent"


def test_send_email_already_sent_returns_409(client, current_user_override, alice, monkeypatch):
    _monkeypatch_draft(monkeypatch)
    monkeypatch.setattr("app.mcp.client.call_tool", lambda name, args: {"status": "sent"})
    current_user_override(alice)
    project_id = client.post("/api/projects", json={"name": "T3"}).json()["id"]

    draft = client.post(
        f"/api/projects/{project_id}/email/preview", json={"instruction": "寄給 PM"}
    ).json()
    client.post(f"/api/projects/{project_id}/email/send", json={"email_log_id": draft["id"]})

    response = client.post(
        f"/api/projects/{project_id}/email/send", json={"email_log_id": draft["id"]}
    )

    assert response.status_code == 409


def test_send_email_mcp_failure_marks_failed(client, db_session, current_user_override, alice, monkeypatch):
    _monkeypatch_draft(monkeypatch)

    def _raise(name, args):
        raise RuntimeError("MCP unreachable")

    monkeypatch.setattr("app.mcp.client.call_tool", _raise)
    current_user_override(alice)
    project_id = client.post("/api/projects", json={"name": "T3"}).json()["id"]

    draft = client.post(
        f"/api/projects/{project_id}/email/preview", json={"instruction": "寄給 PM"}
    ).json()

    response = client.post(
        f"/api/projects/{project_id}/email/send", json={"email_log_id": draft["id"]}
    )

    assert response.status_code == 502
    assert db_session.query(EmailLog).filter_by(id=draft["id"]).one().status == "failed"
