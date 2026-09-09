import re
from dataclasses import dataclass, field
from types import SimpleNamespace

import pytest

from app.agent import agent_service
from app.models import CalendarEventLog, EmailLog, Message


@dataclass
class _FakeMessage:
    content: list
    stop_reason: str = "tool_use"


def _tool_use_block(name: str, input_: dict, id_: str = "toolu_1"):
    return SimpleNamespace(type="tool_use", name=name, input=input_, id=id_)


def _text_block(text: str):
    return SimpleNamespace(type="text", text=text)


def test_non_member_cannot_use_agent(client, current_user_override, alice, bob):
    current_user_override(alice)
    project_id = client.post("/api/projects", json={"name": "T3"}).json()["id"]

    current_user_override(bob)
    response = client.post(f"/api/projects/{project_id}/agent", json={"message": "hello"})

    assert response.status_code == 403


def test_agent_persists_tool_and_assistant_messages(client, current_user_override, alice, db_session, monkeypatch):
    current_user_override(alice)
    project_id = client.post("/api/projects", json={"name": "T3"}).json()["id"]

    turns = iter(
        [
            _FakeMessage(content=[_tool_use_block("search_documents", {"query": "屋頂結構"})]),
            _FakeMessage(content=[_text_block("這是會議摘要。")], stop_reason="end_turn"),
        ]
    )
    monkeypatch.setattr("app.agent.agent_service.select_tools", lambda messages: next(turns))
    monkeypatch.setattr(
        "app.tools.search_documents.run",
        lambda query, project_id, top_k=5: [
            {"document_id": "00000000-0000-0000-0000-000000000001", "filename": "a.pdf", "page": 3, "content": "內容"}
        ],
    )

    response = client.post(f"/api/projects/{project_id}/agent", json={"message": "請整理摘要"})
    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "這是會議摘要。"
    assert [tc["tool"] for tc in body["tool_calls"]] == ["search_documents"]
    assert len(body["sources"]) == 1

    messages = (
        db_session.query(Message)
        .filter(Message.conversation_id == body["conversation_id"])
        .order_by(Message.created_at)
        .all()
    )
    roles = [m.role for m in messages]
    assert roles == ["user", "tool", "assistant"]
    tool_message = messages[1]
    assert tool_message.metadata_["tool_name"] == "search_documents"
    assert messages[2].metadata_["sources"][0]["filename"] == "a.pdf"


def test_agent_draft_email_persists_draft_but_never_sends(
    client, current_user_override, alice, db_session, monkeypatch
):
    current_user_override(alice)
    project_id = client.post("/api/projects", json={"name": "T3"}).json()["id"]

    turns = iter(
        [
            _FakeMessage(
                content=[
                    _tool_use_block(
                        "draft_email", {"to": "pm@example.com", "subject": "摘要", "body": "內容"}
                    )
                ]
            ),
            _FakeMessage(content=[_text_block("已產生草稿，請確認後送出。")], stop_reason="end_turn"),
        ]
    )
    monkeypatch.setattr("app.agent.agent_service.select_tools", lambda messages: next(turns))

    def _fail_if_called(*args, **kwargs):
        raise AssertionError("send_email should never be called from the Agent's tool loop")

    monkeypatch.setattr("app.tools.send_email.run", _fail_if_called)

    response = client.post(f"/api/projects/{project_id}/agent", json={"message": "寄給 PM"})
    assert response.status_code == 200
    body = response.json()

    draft_call = next(tc for tc in body["tool_calls"] if tc["tool"] == "draft_email")
    assert draft_call["output"]["status"] == "draft"
    assert draft_call["output"]["to"] == "pm@example.com"

    email_log = db_session.query(EmailLog).filter_by(project_id=project_id).one()
    assert email_log.status == "draft"
    assert email_log.recipient == "pm@example.com"
    assert email_log.subject == "摘要"
    assert email_log.body == "內容"
    assert str(email_log.project_id) == project_id
    assert str(email_log.user_id) == alice["id"]


def test_agent_fetch_web_page_calls_external_mcp_server_tool(
    client, current_user_override, alice, db_session, monkeypatch
):
    # Confirms the dispatch wiring (agent_service.execute_workflow's
    # fetch_web_page branch -> app.tools.fetch_url.run) end-to-end. The
    # MCP client itself is mocked at web_fetch_service's subprocess
    # boundary in tests/test_tools.py -- this test only needs to prove the
    # Agent actually calls that tool function, not re-verify the MCP
    # transport.
    current_user_override(alice)
    project_id = client.post("/api/projects", json={"name": "T3"}).json()["id"]

    turns = iter(
        [
            _FakeMessage(content=[_tool_use_block("fetch_web_page", {"url": "https://example.com"})]),
            _FakeMessage(content=[_text_block("這是外部網頁的內容摘要。")], stop_reason="end_turn"),
        ]
    )
    monkeypatch.setattr("app.agent.agent_service.select_tools", lambda messages: next(turns))
    monkeypatch.setattr(
        "app.tools.fetch_url.run",
        lambda url, max_length=5000: {"url": url, "content": "# Example Domain"},
    )

    response = client.post(
        f"/api/projects/{project_id}/agent", json={"message": "幫我看一下 https://example.com 的內容"}
    )
    assert response.status_code == 200
    body = response.json()

    fetch_call = next(tc for tc in body["tool_calls"] if tc["tool"] == "fetch_web_page")
    assert fetch_call["input"]["url"] == "https://example.com"
    assert fetch_call["output"]["content"] == "# Example Domain"


def test_agent_create_calendar_event_persists_draft_but_never_creates(
    client, current_user_override, alice, db_session, monkeypatch
):
    current_user_override(alice)
    project_id = client.post("/api/projects", json={"name": "T3"}).json()["id"]

    turns = iter(
        [
            _FakeMessage(
                content=[
                    _tool_use_block(
                        "create_calendar_event",
                        {
                            "summary": "會勘",
                            "start_datetime": "2026-09-16T14:00:00+08:00",
                            "end_datetime": "2026-09-16T15:00:00+08:00",
                        },
                    )
                ]
            ),
            _FakeMessage(content=[_text_block("已產生日曆事件草稿，請確認後建立。")], stop_reason="end_turn"),
        ]
    )
    monkeypatch.setattr("app.agent.agent_service.select_tools", lambda messages: next(turns))

    def _fail_if_called(*args, **kwargs):
        raise AssertionError("create_calendar_event tool should never be called from the Agent's tool loop")

    monkeypatch.setattr("app.tools.create_calendar_event.run", _fail_if_called)

    response = client.post(f"/api/projects/{project_id}/agent", json={"message": "安排一個會勘"})
    assert response.status_code == 200
    body = response.json()

    draft_call = next(tc for tc in body["tool_calls"] if tc["tool"] == "create_calendar_event")
    assert draft_call["output"]["status"] == "draft"
    assert draft_call["output"]["summary"] == "會勘"

    event_log = db_session.query(CalendarEventLog).filter_by(project_id=project_id).one()
    assert event_log.status == "draft"
    assert event_log.summary == "會勘"
    assert str(event_log.project_id) == project_id
    assert str(event_log.user_id) == alice["id"]


def test_agent_system_prompt_includes_current_taipei_datetime():
    prompt = agent_service._build_system_prompt()

    assert "Asia/Taipei" in prompt
    assert re.search(r"\d{4}-\d{2}-\d{2}", prompt)


def _image_bytes() -> bytes:
    # Not a real decodable PNG -- fine, analyze_engineering_image is mocked
    # below and the upload route never decodes the image itself (matches
    # test_vision.py's own fixture).
    return b"\x89PNG\r\n\x1a\nfake-png-bytes-for-testing"


def test_agent_image_attachment_hints_claude_and_persists_metadata(
    client, current_user_override, alice, db_session, monkeypatch
):
    monkeypatch.setattr(
        "app.services.vision_service.analyze_engineering_image",
        lambda *a, **k: {"analysis": "測試分析", "observations": [], "limitations": []},
    )
    current_user_override(alice)
    project_id = client.post("/api/projects", json={"name": "T3"}).json()["id"]

    upload = client.post(
        f"/api/projects/{project_id}/vision",
        files={"file": ("photo.png", _image_bytes(), "image/png")},
    )
    assert upload.status_code == 200
    image_id = upload.json()["id"]

    turns = iter(
        [
            _FakeMessage(content=[_tool_use_block("analyze_image", {"image_id": image_id})]),
            _FakeMessage(content=[_text_block("這張圖片顯示...")], stop_reason="end_turn"),
        ]
    )
    first_call_last_content = {}

    def _fake_select_tools(messages):
        # `messages` is the same list object mutated in place across the
        # loop's later iterations -- snapshot the string content now, don't
        # hold a reference to the list itself.
        first_call_last_content.setdefault("value", messages[-1]["content"])
        return next(turns)

    monkeypatch.setattr("app.agent.agent_service.select_tools", _fake_select_tools)

    response = client.post(
        f"/api/projects/{project_id}/agent",
        json={"message": "這張圖片重點是什麼", "image_id": image_id},
    )
    assert response.status_code == 200

    # The hint steering Claude toward analyze_image(image_id=...) was
    # appended to this turn's user message before the first Claude call.
    assert f'analyze_image(image_id="{image_id}")' in first_call_last_content["value"]

    analyze_call = next(tc for tc in response.json()["tool_calls"] if tc["tool"] == "analyze_image")
    assert "error" not in analyze_call["output"]

    user_message = (
        db_session.query(Message)
        .filter(Message.conversation_id == response.json()["conversation_id"], Message.role == "user")
        .one()
    )
    assert user_message.metadata_["image"]["image_id"] == image_id
    assert user_message.metadata_["image"]["filename"] == "photo.png"


def test_agent_ignores_image_id_from_another_project(
    client, current_user_override, alice, bob, db_session, monkeypatch
):
    # A stale/foreign image_id must degrade to "no image attached" -- never
    # leak another project's filename/storage_path, never error the request.
    monkeypatch.setattr(
        "app.services.vision_service.analyze_engineering_image",
        lambda *a, **k: {"analysis": "測試分析", "observations": [], "limitations": []},
    )
    current_user_override(bob)
    other_project_id = client.post("/api/projects", json={"name": "Other"}).json()["id"]
    upload = client.post(
        f"/api/projects/{other_project_id}/vision",
        files={"file": ("secret.png", _image_bytes(), "image/png")},
    )
    foreign_image_id = upload.json()["id"]

    current_user_override(alice)
    project_id = client.post("/api/projects", json={"name": "T3"}).json()["id"]

    turns = iter([_FakeMessage(content=[_text_block("好的")], stop_reason="end_turn")])
    monkeypatch.setattr("app.agent.agent_service.select_tools", lambda messages: next(turns))

    response = client.post(
        f"/api/projects/{project_id}/agent",
        json={"message": "hello", "image_id": foreign_image_id},
    )
    assert response.status_code == 200

    user_message = (
        db_session.query(Message)
        .filter(Message.conversation_id == response.json()["conversation_id"], Message.role == "user")
        .one()
    )
    assert user_message.metadata_ is None


def test_agent_analyze_image_with_non_uuid_image_id_fails_cleanly(
    client, current_user_override, alice, monkeypatch
):
    # Claude sometimes passes a filename (or other non-UUID text) as
    # image_id instead of leaving it blank -- this used to crash the whole
    # request with a 502 (psycopg.InvalidTextRepresentation querying a UUID
    # column). It must instead surface as a normal tool-error output that
    # Claude can react to in its next turn.
    current_user_override(alice)
    project_id = client.post("/api/projects", json={"name": "T3"}).json()["id"]

    turns = iter(
        [
            _FakeMessage(
                content=[_tool_use_block("analyze_image", {"image_id": "螢幕擷取畫面 2026-09-06.png"})]
            ),
            _FakeMessage(content=[_text_block("請確認圖片是否已上傳。")], stop_reason="end_turn"),
        ]
    )
    monkeypatch.setattr("app.agent.agent_service.select_tools", lambda messages: next(turns))

    response = client.post(f"/api/projects/{project_id}/agent", json={"message": "整理這張圖片重點"})

    assert response.status_code == 200
    analyze_call = next(tc for tc in response.json()["tool_calls"] if tc["tool"] == "analyze_image")
    assert "error" in analyze_call["output"]
