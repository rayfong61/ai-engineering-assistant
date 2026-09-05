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
def send_email(to: str, subject: str, body: str) -> dict:
    """Stub for Day 4's real Gmail send -- never invoked by the Agent's
    tool loop directly (human-in-the-loop, spec2.md section 24); wired here
    so the MCP plumbing itself is provably end-to-end."""
    return send_email_impl.run(to, subject, body)


if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8001)
