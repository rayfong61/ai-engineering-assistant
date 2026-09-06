import logging

from mcp.server.mcpserver import MCPServer

from app.mcp.tools import search_documents as search_documents_impl
from app.mcp.tools import send_email as send_email_impl

# Trust boundary: this process is reachable only from the backend container
# on the internal Docker Compose network (no published port to the
# frontend/browser). It performs no auth/membership checks itself -- project
# authorization happens exactly once, upstream, in the FastAPI route
# (require_project_member) before the Agent ever calls a tool here. The
# project_id reaching these tools is only ever a value the backend already
# authorized -- see app/mcp/tools/search_documents.py.
mcp = MCPServer("ai-engineering-assistant-mcp")


@mcp.tool()
def search_documents(query: str, project_id: str) -> list[dict]:
    """Project-scoped semantic search over ingested engineering documents
    (Voyage embedding + pgvector, via rag_service.retrieve_chunks)."""
    return search_documents_impl.run(query, project_id)


@mcp.tool()
def send_email(to: str, subject: str, body: str, user_id: str) -> dict:
    """Sends via Gmail (EMAIL_MODE=gmail, using user_id's connected Gmail
    credential) or logs a mock send (EMAIL_MODE=mock). Never invoked by the
    Agent's tool loop directly (human-in-the-loop, spec2.md section 24) --
    only email_service.confirm_and_send calls this, after an explicit user
    Confirm & Send."""
    return send_email_impl.run(to, subject, body, user_id)


if __name__ == "__main__":
    # Root logger defaults to WARNING -- without this, send_email.py's
    # [MOCK EMAIL] confirmation (logger.info) is silently dropped even
    # though the mock send itself succeeds.
    logging.basicConfig(level=logging.INFO)
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8001)
