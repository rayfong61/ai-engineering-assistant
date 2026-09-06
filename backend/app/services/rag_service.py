import uuid
from collections import defaultdict

from sqlalchemy.orm import Session

from app.models import Document, DocumentChunk
from app.services import embedding_service, pdf_service
from app.services.activity_service import log_activity


def ingest_document(db: Session, document: Document, file_bytes: bytes) -> None:
    """Parse, chunk, embed, and store a document's chunks. Runs as a
    background task after upload responds, on its own DB session."""
    document.status = "processing"
    db.commit()

    try:
        pages = pdf_service.extract_pages(file_bytes)
        chunks = pdf_service.chunk_pages(pages)
        if not chunks:
            document.status = "failed"
            db.commit()
            return

        embeddings = embedding_service.embed_documents([c["content"] for c in chunks])
        log_activity(
            db, document.project_id, document.uploaded_by, "embedding_generated", detail=document.filename
        )

        for chunk, embedding in zip(chunks, embeddings, strict=True):
            db.add(
                DocumentChunk(
                    document_id=document.id,
                    project_id=document.project_id,
                    page=chunk["page"],
                    chunk_index=chunk["chunk_index"],
                    content=chunk["content"],
                    embedding=embedding,
                )
            )
        document.status = "ready"
        log_activity(
            db, document.project_id, document.uploaded_by, "pdf_processing_completed", detail=document.filename
        )
        db.commit()
    except Exception:
        db.rollback()
        document.status = "failed"
        db.commit()
        raise


def match_document_by_filename(db: Session, project_id: str, question: str) -> uuid.UUID | None:
    """If the question explicitly names one of the project's documents (by
    filename, extension optional), return its id so retrieval can be
    restricted to it.

    Plain vector search can't find a document from its own filename -- the
    filename string never appears in the document's body text, so
    "010705022.pdf 這份呢" embeds nowhere near that document's actual
    content and other documents win on pure similarity instead. Matching
    the filename as a literal substring of the question sidesteps that.
    Ambiguous (multiple filenames mentioned) or no-match questions fall
    back to normal similarity search across all documents.
    """
    documents = db.query(Document.id, Document.filename).filter(Document.project_id == project_id).all()
    question_lower = question.lower()

    matches = [
        doc_id
        for doc_id, filename in documents
        if (stem := filename.rsplit(".", 1)[0].lower()) and stem in question_lower
    ]
    return matches[0] if len(matches) == 1 else None


def retrieve_chunks(
    db: Session,
    project_id: str,
    query_embedding: list[float],
    top_k: int = 5,
    max_per_document: int = 3,
    document_id: uuid.UUID | None = None,
) -> list[DocumentChunk]:
    # project_id filter is mandatory -- cross-project retrieval is forbidden
    # (spec2.md section 14).
    query = db.query(DocumentChunk).filter(DocumentChunk.project_id == project_id)
    if document_id is not None:
        query = query.filter(DocumentChunk.document_id == document_id)

    # Pull a larger candidate pool, then cap how many chunks any single
    # document can contribute. Plain top-k over all chunks pooled together
    # lets a chunk-heavy document crowd out every other document (e.g. one
    # 24-chunk PDF filling all 5 slots while a 6-chunk PDF never appears),
    # which is especially visible on broad/meta questions like "what
    # documents do you have". The cap still prefers the closest matches
    # first -- it only kicks in once a document already has its share.
    candidates = (
        query.order_by(DocumentChunk.embedding.cosine_distance(query_embedding)).limit(top_k * 4).all()
    )

    selected = []
    counts: dict = defaultdict(int)
    for chunk in candidates:
        if counts[chunk.document_id] >= max_per_document:
            continue
        selected.append(chunk)
        counts[chunk.document_id] += 1
        if len(selected) == top_k:
            break
    return selected
