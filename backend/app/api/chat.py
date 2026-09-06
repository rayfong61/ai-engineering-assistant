import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.authorization import require_project_member
from app.core.database import get_db
from app.models import Conversation, Document, Message
from app.schemas.document import (
    ChatRequest,
    ChatResponse,
    ConversationDetailOut,
    ConversationOut,
    MessageOut,
    MessageSourceOut,
    SourceOut,
)
from app.services import claude_service, embedding_service, rag_service
from app.services.activity_service import log_activity

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/projects/{project_id}", tags=["chat"])
conversation_router = APIRouter(prefix="/api/conversations", tags=["chat"])

TOP_K = 5


@router.post("/chat", response_model=ChatResponse)
def chat(
    project_id: str,
    payload: ChatRequest,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_project_member(db, project_id, user)

    if payload.conversation_id:
        conversation = (
            db.query(Conversation)
            .filter(Conversation.id == payload.conversation_id, Conversation.project_id == project_id)
            .first()
        )
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
    else:
        conversation = Conversation(
            project_id=project_id, user_id=uuid.UUID(user["id"]), title=payload.message[:50]
        )
        db.add(conversation)
        db.flush()

    db.add(
        Message(
            conversation_id=conversation.id,
            user_id=uuid.UUID(user["id"]),
            role="user",
            content=payload.message,
        )
    )

    try:
        # project_id filter happens inside retrieve_chunks -- cross-project
        # retrieval is forbidden (spec2.md section 14).
        matched_document_id = rag_service.match_document_by_filename(db, project_id, payload.message)
        query_embedding = embedding_service.embed_query(payload.message)
        chunks = rag_service.retrieve_chunks(
            db, project_id, query_embedding, top_k=TOP_K, document_id=matched_document_id
        )
        log_activity(db, project_id, user["id"], "rag_search_executed", detail=payload.message[:200])

        filenames: dict[uuid.UUID, str] = {}
        if chunks:
            doc_ids = {c.document_id for c in chunks}
            filenames = {d.id: d.filename for d in db.query(Document).filter(Document.id.in_(doc_ids)).all()}

        context = [
            {"filename": filenames.get(c.document_id, "unknown"), "page": c.page, "content": c.content}
            for c in chunks
        ]
        answer = claude_service.generate_answer(payload.message, context)
    except Exception as exc:
        logger.exception("Chat request failed for project %s", project_id)
        raise HTTPException(status_code=502, detail="回答問題失敗，請稍後再試") from exc

    db.add(
        Message(
            conversation_id=conversation.id,
            role="assistant",
            content=answer,
            metadata_={
                "sources": [
                    {
                        "document_id": str(c.document_id),
                        "filename": filenames.get(c.document_id, "unknown"),
                        "page": c.page,
                    }
                    for c in chunks
                ]
            },
        )
    )
    conversation.updated_at = datetime.now(timezone.utc)
    db.commit()

    return ChatResponse(
        conversation_id=conversation.id,
        answer=answer,
        sources=[
            SourceOut(
                document_id=c.document_id,
                filename=filenames.get(c.document_id, "unknown"),
                page=c.page,
                content=c.content,
            )
            for c in chunks
        ],
    )


@router.get("/conversations", response_model=list[ConversationOut])
def list_conversations(
    project_id: str, user: dict = Depends(get_current_user), db: Session = Depends(get_db)
):
    require_project_member(db, project_id, user)
    return (
        db.query(Conversation)
        .filter(Conversation.project_id == project_id)
        .order_by(Conversation.updated_at.desc())
        .all()
    )


@conversation_router.get("/{conversation_id}", response_model=ConversationDetailOut)
def get_conversation(
    conversation_id: str, user: dict = Depends(get_current_user), db: Session = Depends(get_db)
):
    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    require_project_member(db, str(conversation.project_id), user)

    messages = (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
        .all()
    )
    return ConversationDetailOut(
        id=conversation.id,
        project_id=conversation.project_id,
        title=conversation.title,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        messages=[
            MessageOut(
                id=m.id,
                role=m.role,
                content=m.content,
                created_at=m.created_at,
                sources=(
                    [MessageSourceOut(**s) for s in m.metadata_["sources"]]
                    if m.metadata_ and m.metadata_.get("sources")
                    else None
                ),
            )
            for m in messages
        ],
    )


@conversation_router.delete("/{conversation_id}", status_code=204)
def delete_conversation(
    conversation_id: str, user: dict = Depends(get_current_user), db: Session = Depends(get_db)
):
    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    require_project_member(db, str(conversation.project_id), user)

    db.delete(conversation)  # cascades to messages
    db.commit()

    return Response(status_code=204)
