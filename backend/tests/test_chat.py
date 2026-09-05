import uuid

from app.models import Conversation, Message


def _make_conversation(db_session, project_id, user_id, title="Q"):
    conversation = Conversation(project_id=project_id, user_id=user_id, title=title)
    db_session.add(conversation)
    db_session.flush()
    return conversation


def test_list_conversations_requires_membership(client, current_user_override, alice, bob):
    current_user_override(alice)
    project_id = client.post("/api/projects", json={"name": "T3"}).json()["id"]

    current_user_override(bob)
    response = client.get(f"/api/projects/{project_id}/conversations")

    assert response.status_code == 403


def test_get_conversation_requires_membership(client, db_session, current_user_override, alice, bob):
    current_user_override(alice)
    project_id = client.post("/api/projects", json={"name": "T3"}).json()["id"]
    conversation = _make_conversation(db_session, project_id, alice["id"])

    current_user_override(bob)
    response = client.get(f"/api/conversations/{conversation.id}")

    assert response.status_code == 403


def test_get_nonexistent_conversation_returns_404(client, current_user_override, alice):
    current_user_override(alice)

    response = client.get("/api/conversations/00000000-0000-0000-0000-000000000000")

    assert response.status_code == 404


def test_get_conversation_restores_message_sources(client, db_session, current_user_override, alice):
    current_user_override(alice)
    project_id = client.post("/api/projects", json={"name": "T3"}).json()["id"]
    conversation = _make_conversation(db_session, project_id, alice["id"])

    db_session.add(
        Message(conversation_id=conversation.id, user_id=alice["id"], role="user", content="問題")
    )
    document_id = uuid.uuid4()
    db_session.add(
        Message(
            conversation_id=conversation.id,
            role="assistant",
            content="答案",
            metadata_={"sources": [{"document_id": str(document_id), "filename": "a.pdf", "page": 3}]},
        )
    )
    db_session.flush()

    response = client.get(f"/api/conversations/{conversation.id}")

    assert response.status_code == 200
    messages = response.json()["messages"]
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[0]["sources"] is None
    assert messages[1]["role"] == "assistant"
    assert messages[1]["sources"] == [
        {"document_id": str(document_id), "filename": "a.pdf", "page": 3}
    ]


def test_delete_conversation_requires_membership(client, db_session, current_user_override, alice, bob):
    current_user_override(alice)
    project_id = client.post("/api/projects", json={"name": "T3"}).json()["id"]
    conversation = _make_conversation(db_session, project_id, alice["id"])

    current_user_override(bob)
    response = client.delete(f"/api/conversations/{conversation.id}")

    assert response.status_code == 403


def test_delete_conversation_removes_it_and_cascades_messages(
    client, db_session, current_user_override, alice
):
    current_user_override(alice)
    project_id = client.post("/api/projects", json={"name": "T3"}).json()["id"]
    conversation = _make_conversation(db_session, project_id, alice["id"])
    db_session.add(
        Message(conversation_id=conversation.id, user_id=alice["id"], role="user", content="問題")
    )
    db_session.flush()
    conversation_id = conversation.id

    response = client.delete(f"/api/conversations/{conversation_id}")

    assert response.status_code == 204
    assert client.get(f"/api/conversations/{conversation_id}").status_code == 404
    assert db_session.query(Message).filter_by(conversation_id=conversation_id).count() == 0
