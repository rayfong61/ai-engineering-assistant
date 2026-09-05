from app.mcp.tools import search_documents, send_email
from app.models import Document, DocumentChunk, Project
from app.models.document import EMBEDDING_DIM


class _NonClosingSession:
    """Wraps the test's db_session so app.mcp.tools.search_documents.run()
    (which opens its own SessionLocal() and always calls db.close() in a
    finally block, since it normally runs on the separate mcp-server
    process with no request-scoped session to reuse) operates against the
    test's SAVEPOINT-rolled-back session instead of a real, separate
    connection -- close() is swallowed so the fixture's session stays open
    for the test's own assertions afterward."""

    def __init__(self, session):
        self._session = session

    def close(self):
        pass

    def __getattr__(self, name):
        return getattr(self._session, name)


def test_search_documents_tool_scopes_to_project(db_session, alice, monkeypatch):
    monkeypatch.setattr(
        "app.mcp.tools.search_documents.SessionLocal", lambda: _NonClosingSession(db_session)
    )
    monkeypatch.setattr(
        "app.services.embedding_service.embed_query", lambda text: [0.1] * EMBEDDING_DIM
    )

    project_a = Project(name="Project A", created_by=alice["id"])
    project_b = Project(name="Project B", created_by=alice["id"])
    db_session.add_all([project_a, project_b])
    db_session.flush()

    doc_a = Document(
        project_id=project_a.id, uploaded_by=alice["id"], filename="a.pdf",
        storage_path="x", status="ready",
    )
    doc_b = Document(
        project_id=project_b.id, uploaded_by=alice["id"], filename="b.pdf",
        storage_path="x", status="ready",
    )
    db_session.add_all([doc_a, doc_b])
    db_session.flush()

    shared_vector = [0.1] * EMBEDDING_DIM
    db_session.add(
        DocumentChunk(
            document_id=doc_a.id, project_id=project_a.id, page=1, chunk_index=0,
            content="content in project A", embedding=shared_vector,
        )
    )
    db_session.add(
        DocumentChunk(
            document_id=doc_b.id, project_id=project_b.id, page=1, chunk_index=0,
            content="content in project B", embedding=shared_vector,
        )
    )
    db_session.flush()

    results = search_documents.run("query", str(project_a.id))

    assert len(results) == 1
    assert results[0]["filename"] == "a.pdf"
    assert results[0]["content"] == "content in project A"


def test_search_documents_tool_returns_empty_for_project_with_no_chunks(db_session, alice, monkeypatch):
    monkeypatch.setattr(
        "app.mcp.tools.search_documents.SessionLocal", lambda: _NonClosingSession(db_session)
    )
    monkeypatch.setattr(
        "app.services.embedding_service.embed_query", lambda text: [0.1] * EMBEDDING_DIM
    )

    project = Project(name="Empty Project", created_by=alice["id"])
    db_session.add(project)
    db_session.flush()

    assert search_documents.run("query", str(project.id)) == []


def test_send_email_tool_mock_mode_returns_sent(monkeypatch):
    monkeypatch.setattr("app.mcp.tools.send_email.EMAIL_MODE", "mock")

    result = send_email.run("pm@example.com", "subject", "body")

    assert result["status"] == "sent"


def test_send_email_tool_non_mock_mode_fails_cleanly(monkeypatch):
    # Real Gmail sending isn't wired up yet -- a non-mock EMAIL_MODE must
    # fail rather than silently pretending to send.
    monkeypatch.setattr("app.mcp.tools.send_email.EMAIL_MODE", "gmail")

    result = send_email.run("pm@example.com", "subject", "body")

    assert result["status"] == "failed"


# The full MCP protocol round trip (Agent -> MCP Client -> mcp-server
# container -> tool -> service, over real Streamable HTTP on the Docker
# Compose network) is verified manually rather than with an in-process
# ASGI test here -- spec2.md section 37's Day 3 risk note explicitly says
# not to over-polish MCP protocol details given the SDK is the team's
# least-familiar piece. Manual verification: `docker compose up mcp-server
# backend`, then call app.mcp.client.call_tool("search_documents", {...})
# from a backend shell against a project with real ingested documents and
# confirm real chunks come back through the network hop.
