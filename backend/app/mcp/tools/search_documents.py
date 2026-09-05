from app.core.database import SessionLocal
from app.models import Document
from app.services import embedding_service, rag_service


def run(query: str, project_id: str, top_k: int = 5) -> list[dict]:
    """Runs on the mcp-server process -- its own DB session, since there's
    no FastAPI Depends(get_db) here.

    Trust boundary: project_id is trusted as-is. The MCP server has no
    JWT/user context to check project membership against -- the only
    caller is the backend's Agent, which already ran require_project_member
    before invoking this tool (see app/mcp/server.py's module docstring).
    """
    db = SessionLocal()
    try:
        query_embedding = embedding_service.embed_query(query)
        chunks = rag_service.retrieve_chunks(db, project_id, query_embedding, top_k=top_k)
        doc_ids = {c.document_id for c in chunks}
        filenames = (
            {d.id: d.filename for d in db.query(Document).filter(Document.id.in_(doc_ids)).all()}
            if chunks
            else {}
        )
        return [
            {
                "document_id": str(c.document_id),
                "filename": filenames.get(c.document_id, "unknown"),
                "page": c.page,
                "content": c.content,
            }
            for c in chunks
        ]
    finally:
        db.close()
