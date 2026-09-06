import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.config import CLAUDE_MODEL
from app.mcp import client as mcp_client
from app.models import Conversation, Message, VisionAnalysis
from app.schemas.agent import AgentResponse, AgentToolCallOut
from app.schemas.document import SourceOut
from app.services import claude_service, email_service, embedding_service, rag_service
from app.services.activity_service import log_activity

MAX_ITERATIONS = 6

AGENT_TOOLS = [
    {
        "name": "search_documents",
        "description": "在本專案的工程文件知識庫中搜尋語意相關段落（經 MCP，Voyage Embedding + pgvector）。",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
            "additionalProperties": False,
        },
    },
    {
        "name": "analyze_image",
        "description": "取得本專案某張工程圖片已產生的 Claude Vision 分析結果。",
        "input_schema": {
            "type": "object",
            "properties": {"image_id": {"type": "string", "description": "留空則使用最新上傳的圖片"}},
            "required": [],
            "additionalProperties": False,
        },
    },
    {
        "name": "generate_summary",
        "description": "將目前已取得的文件檢索內容與圖片分析結果整理成會議摘要。取得足夠資訊後呼叫。",
        "input_schema": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
    },
    {
        "name": "draft_email",
        "description": (
            "產生一封 email 草稿（收件人/主旨/內容），寫入 email_logs 為 draft 狀態。"
            "不會真的寄出信件——使用者需在 Email Preview 中按 Confirm & Send 才會真正寄送。"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "to": {"type": "string"},
                "subject": {"type": "string"},
                "body": {"type": "string"},
            },
            "required": ["to", "subject", "body"],
            "additionalProperties": False,
        },
    },
]

AGENT_SYSTEM_PROMPT = """你是一個工程專案助理 Agent。可使用的工具：
search_documents（搜尋工程文件）、analyze_image（取得圖片分析）、
generate_summary（整理會議摘要）、draft_email（產生 email 草稿，不會真的寄信）。

呼叫 draft_email 只會產生草稿並存成 draft 狀態，讓使用者在 Email Preview 中確認——
你自己永遠不能真的寄出郵件，寄送必須由使用者明確點擊 Confirm & Send 才會發生。

只要使用者要求修改、精簡、調整用詞，或以任何方式變更一封已經產生的 email 草稿內容，
你必須重新呼叫 draft_email 產生新的草稿，絕對不能只用文字描述「已經修改」卻沒有實際
呼叫工具——使用者看到的 Email Preview 卡片只會反映真正呼叫過 draft_email 的結果，
若你沒有呼叫，畫面上顯示的仍是舊的草稿內容，文字回覆聲稱已修改會誤導使用者按下
Confirm & Send 時寄出錯誤的內容。

取得足夠的文件/圖片資訊後，呼叫 generate_summary 產生最終回答。
"""


@dataclass
class AgentLoopState:
    context_chunks: list[dict] = field(default_factory=list)
    vision_analyses: list[dict] = field(default_factory=list)
    tool_calls: list[dict] = field(default_factory=list)


def select_tools(messages: list[dict]):
    """One Claude turn against AGENT_TOOLS; caller inspects stop_reason."""
    return claude_service._client().messages.create(
        model=CLAUDE_MODEL,
        # 1024 was too tight for a detailed multi-section Chinese answer
        # with citations -- got observed cutting off mid-sentence.
        max_tokens=4096,
        system=AGENT_SYSTEM_PROMPT,
        tools=AGENT_TOOLS,
        messages=messages,
    )


def _lookup_vision_analysis(db: Session, project_id: str, image_id: str | None) -> dict:
    query = db.query(VisionAnalysis).filter(VisionAnalysis.project_id == project_id)
    if image_id:
        try:
            uuid.UUID(image_id)
        except ValueError:
            # Claude sometimes passes a filename or other non-UUID text as
            # image_id instead of leaving it blank -- querying with that
            # directly raises an unhandled psycopg.InvalidTextRepresentation
            # (the id column is UUID) that used to bubble up as a 502 for
            # the whole /agent request. Fail gracefully as a tool error
            # instead, so Claude can ask the user to clarify.
            return {"error": "找不到指定的圖片，請留空 image_id 以使用最新上傳的圖片。"}
        record = query.filter(VisionAnalysis.id == image_id).first()
    else:
        record = query.order_by(VisionAnalysis.created_at.desc()).first()
    if not record:
        return {"error": "尚未有已分析的工程圖片，請先在 Vision 分頁上傳並分析圖片。"}
    return {
        "image_id": str(record.id),
        "filename": record.filename,
        "analysis": record.analysis,
        "observations": record.observations,
        "limitations": record.limitations,
    }


def execute_workflow(
    db: Session, project_id: str, user: dict, tool_use_blocks: list, state: AgentLoopState
) -> list[dict]:
    """Dispatches each tool_use block and returns tool_result content blocks
    for the next Claude turn."""
    tool_results = []
    for block in tool_use_blocks:
        name = block.name
        tool_input = block.input

        if name == "search_documents":
            query_embedding = embedding_service.embed_query(tool_input["query"])
            output = mcp_client.call_tool(
                "search_documents", {"query": tool_input["query"], "project_id": str(project_id)}
            )
            state.context_chunks.extend(output)
            log_activity(
                db, project_id, user["id"], "rag_search_executed", detail=tool_input["query"][:200]
            )
        elif name == "analyze_image":
            output = _lookup_vision_analysis(db, project_id, tool_input.get("image_id"))
            if "error" not in output:
                state.vision_analyses.append(output)
        elif name == "generate_summary":
            output = claude_service.generate_summary(state.context_chunks, state.vision_analyses)
            log_activity(db, project_id, user["id"], "meeting_summary_generated")
        elif name == "draft_email":
            # Only ever persists a draft row -- never reaches the MCP
            # client. spec2.md section 24 forbids the Agent from
            # auto-sending; the real send only happens via
            # email_service.confirm_and_send, triggered by an explicit
            # user "Confirm & Send" click (POST /email/send).
            try:
                email_log = email_service.save_draft(
                    db,
                    project_id,
                    uuid.UUID(user["id"]),
                    tool_input["to"],
                    tool_input["subject"],
                    tool_input["body"],
                )
                output = {
                    "email_log_id": str(email_log.id),
                    "to": email_log.recipient,
                    "subject": email_log.subject,
                    "body": email_log.body,
                    "status": "draft",
                }
            except ValueError as exc:
                # e.g. malformed recipient address -- surfaced back to Claude
                # as a tool error so it can ask the user for a correction,
                # rather than crashing the whole /agent request.
                output = {"error": str(exc)}
        else:
            output = {"error": f"未知工具：{name}"}

        state.tool_calls.append({"tool": name, "input": tool_input, "output": output})
        content = output if isinstance(output, str) else json.dumps(output, ensure_ascii=False)
        tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": content})
    return tool_results


def process_request(
    db: Session, project_id: str, user: dict, conversation_id: uuid.UUID | None, message: str
) -> AgentResponse:
    if conversation_id:
        conversation = (
            db.query(Conversation)
            .filter(Conversation.id == conversation_id, Conversation.project_id == project_id)
            .first()
        )
        if not conversation:
            raise ValueError("Conversation not found")
    else:
        conversation = Conversation(
            project_id=project_id, user_id=uuid.UUID(user["id"]), title=message[:50]
        )
        db.add(conversation)
        db.flush()

    db.add(
        Message(
            conversation_id=conversation.id, user_id=uuid.UUID(user["id"]), role="user", content=message
        )
    )
    db.flush()  # make the just-added user message visible to the history query below (autoflush=False)

    # Only replay plain-text user/assistant history -- each Agent request is
    # a self-contained tool loop; replaying past tool_use/tool_result pairs
    # across requests risks malformed Claude message sequences and isn't
    # needed since only the prior text turns matter for context.
    history = (
        db.query(Message)
        .filter(Message.conversation_id == conversation.id, Message.role.in_(["user", "assistant"]))
        .order_by(Message.created_at)
        .all()
    )
    messages = [{"role": m.role, "content": m.content} for m in history]

    state = AgentLoopState()
    final_text = None

    for _ in range(MAX_ITERATIONS):
        response = select_tools(messages)
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason != "tool_use":
            final_text = next(
                (block.text for block in response.content if block.type == "text"), None
            )
            break

        tool_use_blocks = [block for block in response.content if block.type == "tool_use"]
        tool_results = execute_workflow(db, project_id, user, tool_use_blocks, state)
        messages.append({"role": "user", "content": tool_results})

    if final_text is None:
        # Loop exhausted MAX_ITERATIONS without Claude settling on an answer
        # -- synthesize one from whatever context/vision was gathered rather
        # than returning nothing.
        final_text = claude_service.generate_summary(state.context_chunks, state.vision_analyses)

    for call in state.tool_calls:
        db.add(
            Message(
                conversation_id=conversation.id,
                role="tool",
                content=json.dumps(call, ensure_ascii=False),
                metadata_={"tool_name": call["tool"]},
            )
        )

    sources = [
        {"document_id": c["document_id"], "filename": c["filename"], "page": c["page"]}
        for c in state.context_chunks
    ]
    db.add(
        Message(
            conversation_id=conversation.id,
            role="assistant",
            content=final_text,
            metadata_={"sources": sources},
        )
    )
    conversation.updated_at = datetime.now(timezone.utc)
    db.commit()

    return AgentResponse(
        conversation_id=conversation.id,
        answer=final_text,
        tool_calls=[AgentToolCallOut(**call) for call in state.tool_calls],
        sources=[
            SourceOut(
                document_id=c["document_id"], filename=c["filename"], page=c["page"], content=c["content"]
            )
            for c in state.context_chunks
        ],
    )
