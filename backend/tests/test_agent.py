from dataclasses import dataclass, field
from types import SimpleNamespace

import pytest

from app.models import EmailLog, Message


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
        "app.mcp.client.call_tool",
        lambda name, args: [
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


def test_agent_draft_email_persists_draft_but_never_calls_mcp(
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

    def _fail_if_called(name, args):
        raise AssertionError(f"MCP should never be called for {name}")

    monkeypatch.setattr("app.mcp.client.call_tool", _fail_if_called)

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
