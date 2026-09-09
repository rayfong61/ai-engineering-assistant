import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.core.config import CLAUDE_MODEL
from app.tools import fetch_url, geo, search_documents, weather
from app.models import Conversation, Message, VisionAnalysis
from app.schemas.agent import AgentResponse, AgentToolCallOut
from app.schemas.document import SourceOut
from app.services import calendar_event_service, claude_service, email_service
from app.services.activity_service import log_activity

MAX_ITERATIONS = 6
TAIPEI_TZ = ZoneInfo("Asia/Taipei")
_WEEKDAY_ZH = "一二三四五六日"

AGENT_TOOLS = [
    {
        "name": "search_documents",
        "description": "在本專案的工程文件知識庫中搜尋語意相關段落（Voyage Embedding + pgvector）。",
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
        "name": "get_site_weather",
        "description": (
            "當使用者詢問工地/案場所在地的天氣、施工環境，或會議摘要需要天氣資訊時使用"
            "（中央氣象署開放資料）。輸入為縣市名稱（如「桃園市」），不是鄉鎮區、不是經緯度"
            "——此資料集僅提供縣市層級的預報，若剛呼叫過 check_site_location，"
            "可從其回傳的 formatted_address 取出所屬縣市名稱代入，不可直接帶入完整地址或鄉鎮區名稱。"
            "回傳的 forecasts 是約 15 個約 12 小時時段組成的陣列（涵蓋未來約一週），"
            "每個時段附 start_time/end_time——必須自行比對使用者詢問的日期或時段"
            "（例如「今晚」「明天」「這週五」）落在哪個 start_time~end_time 區間，再引用該時段的資料回答；"
            "若使用者詢問的日期超出 forecasts 涵蓋範圍（所有 end_time 都早於該日期），"
            "必須誠實告知超出可查詢範圍，不可用陣列裡最接近的時段冒充。"
        ),
        "input_schema": {
            "type": "object",
            "properties": {"location": {"type": "string", "description": "縣市名稱，如「桃園市」（非鄉鎮區）"}},
            "required": ["location"],
            "additionalProperties": False,
        },
    },
    {
        "name": "check_site_location",
        "description": (
            "當使用者提供工程地址、需要確認基地位置或對桃園市地質敏感區資料做初步空間套疊篩查時使用"
            "（OpenStreetMap Nominatim 地理編碼 + 本地地質敏感區資料）。回傳的 potential_geological_sensitive_zone "
            "是初步篩查結果，不是正式判定；data_available=false 代表沒有資料可查，不等於「確認沒有重疊」。"
            "回答時必須完整保留 disclaimer 內容，不可據此斷言工程安全或法規合規性。"
        ),
        "input_schema": {
            "type": "object",
            "properties": {"address": {"type": "string"}},
            "required": ["address"],
            "additionalProperties": False,
        },
    },
    {
        "name": "fetch_web_page",
        "description": (
            "擷取一個公開網頁的文字內容（轉為 Markdown），用於查詢法規公告、規範標準等"
            "本專案文件庫之外的最新網路資訊。與其他工具不同，這個工具是真正透過 MCP "
            "（Model Context Protocol）協定串接一個獨立的第三方 MCP Server"
            "（modelcontextprotocol 官方維護的 fetch 參考實作，以子行程 + stdio 通訊），"
            "不是本專案自己實作的函式。回傳內容來自公開網路，不是本專案已上傳並索引的工程文件，"
            "回答時必須明確告知使用者這是外部網頁內容，不可與 search_documents 取得的專案文件內容混為一談。"
        ),
        "input_schema": {
            "type": "object",
            "properties": {"url": {"type": "string", "description": "要擷取的公開網頁網址"}},
            "required": ["url"],
            "additionalProperties": False,
        },
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
    {
        "name": "create_calendar_event",
        "description": (
            "產生一個 Google Calendar 事件草稿（例如會勘、會議），寫入 calendar_event_logs 為 draft 狀態。"
            "不會真的建立日曆事件——使用者需在 Calendar Event Preview 中按 Confirm & Create 才會真正建立。"
            "start_datetime/end_datetime 必須是包含明確時區的 ISO-8601 字串"
            "（例如 2026-09-16T14:00:00+08:00），不可省略時區；請參考系統提示末尾提供的目前日期時間，"
            "將使用者說的相對日期（例如「下週三」「明天下午兩點」）換算成明確日期後再呼叫，不可自行假設日期。"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
                "start_datetime": {"type": "string", "description": "ISO-8601，需含時區，例如 2026-09-16T14:00:00+08:00"},
                "end_datetime": {"type": "string", "description": "ISO-8601，需含時區，例如 2026-09-16T15:00:00+08:00"},
                "description": {"type": "string"},
                "attendees": {"type": "array", "items": {"type": "string"}, "description": "受邀者 Email 陣列"},
            },
            "required": ["summary", "start_datetime", "end_datetime"],
            "additionalProperties": False,
        },
    },
]

AGENT_SYSTEM_PROMPT_TEMPLATE = """你是一個工程專案助理 Agent。可使用的工具：
search_documents（搜尋工程文件）、analyze_image（取得圖片分析）、
get_site_weather（查詢案場所在地天氣，中央氣象署開放資料）、
check_site_location（查詢案址地理位置並對桃園市地質敏感區資料做初步空間套疊篩查，
OpenStreetMap Nominatim 地理編碼 + 本地地質敏感區資料）、
fetch_web_page（透過外部 MCP Server 擷取公開網頁內容，用於專案文件庫之外的最新網路資訊）、
generate_summary（整理會議摘要）、draft_email（產生 email 草稿，不會真的寄信）、
create_calendar_event（產生 Google Calendar 事件草稿，不會真的建立事件）。

fetch_web_page 取得的是公開網路內容，不是本專案已上傳並索引的工程文件——回答時必須
明確標示資訊來源是「外部網頁」，不可與 search_documents 取得的專案文件內容混淆或
暗示兩者出處相同。

整理 check_site_location 的結果時，必須原樣保留其回傳的 disclaimer 內容給使用者，
不可省略、不可用自己的話重新包裝成更肯定的講法——這個工具只做初步篩查，不是正式地質判定，
絕不能據此斷言工程安全或法規合規性，比照現有 Vision 分析、會議摘要、email 草稿的措辭紀律。

呼叫 draft_email 或 create_calendar_event 只會產生草稿（email 存成 email_logs 的 draft，
日曆事件存成 calendar_event_logs 的 draft），讓使用者在對應的 Preview 卡片中確認——
你自己永遠不能真的寄出郵件或建立日曆事件，這兩者都必須由使用者明確點擊
Confirm & Send / Confirm & Create 才會發生。

只要使用者要求修改、精簡、調整用詞，或以任何方式變更一封已經產生的 email 草稿或
日曆事件草稿內容，你必須重新呼叫對應的 draft_email 或 create_calendar_event 工具
產生新的草稿，絕對不能只用文字描述「已經修改」卻沒有實際呼叫工具——使用者看到的
Preview 卡片只會反映真正呼叫過該工具的結果，若你沒有呼叫，畫面上顯示的仍是舊的
草稿內容，文字回覆聲稱已修改會誤導使用者按下 Confirm 時送出/建立錯誤的內容。

呼叫 create_calendar_event 時，start_datetime/end_datetime 必須是換算後的明確
ISO-8601 日期時間並包含時區，不可留下「下週三」之類的相對說法未換算——必須以本次
系統提示末尾提供的目前真實日期時間為基準換算。

取得足夠的文件/圖片資訊後，呼叫 generate_summary 產生最終回答。
"""


def _current_datetime_context() -> str:
    now = datetime.now(TAIPEI_TZ)
    return f"目前日期時間（Asia/Taipei，UTC+8）：{now.strftime('%Y-%m-%d %H:%M')}，星期{_WEEKDAY_ZH[now.weekday()]}。"


def _build_system_prompt() -> str:
    return f"{AGENT_SYSTEM_PROMPT_TEMPLATE}\n\n{_current_datetime_context()}"


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
        system=_build_system_prompt(),
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
            output = search_documents.run(tool_input["query"], str(project_id))
            state.context_chunks.extend(output)
            log_activity(
                db, project_id, user["id"], "rag_search_executed", detail=tool_input["query"][:200]
            )
        elif name == "get_site_weather":
            output = weather.run(tool_input["location"])
        elif name == "check_site_location":
            output = geo.run(tool_input["address"])
        elif name == "fetch_web_page":
            output = fetch_url.run(tool_input["url"])
        elif name == "analyze_image":
            output = _lookup_vision_analysis(db, project_id, tool_input.get("image_id"))
            if "error" not in output:
                state.vision_analyses.append(output)
        elif name == "generate_summary":
            output = claude_service.generate_summary(state.context_chunks, state.vision_analyses)
            log_activity(db, project_id, user["id"], "meeting_summary_generated")
        elif name == "draft_email":
            # Only ever persists a draft row -- never calls send_email.
            # spec2.md section 24 forbids the Agent from auto-sending; the
            # real send only happens via email_service.confirm_and_send,
            # triggered by an explicit user "Confirm & Send" click
            # (POST /email/send).
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
        elif name == "create_calendar_event":
            # Only ever persists a draft row -- never calls
            # create_calendar_event directly. Mirrors draft_email exactly:
            # the real creation only happens via
            # calendar_event_service.confirm_and_create, triggered by an
            # explicit user "Confirm & Create" click
            # (POST .../calendar-events/create).
            try:
                event_log = calendar_event_service.save_draft(
                    db,
                    project_id,
                    uuid.UUID(user["id"]),
                    tool_input["summary"],
                    tool_input["start_datetime"],
                    tool_input["end_datetime"],
                    tool_input.get("description"),
                    tool_input.get("attendees"),
                )
                output = {
                    "calendar_event_log_id": str(event_log.id),
                    "summary": event_log.summary,
                    "start_datetime": event_log.start_datetime.isoformat(),
                    "end_datetime": event_log.end_datetime.isoformat(),
                    "description": event_log.description,
                    "attendees": event_log.attendees,
                    "status": "draft",
                }
            except ValueError as exc:
                # e.g. end before start, missing timezone, malformed
                # attendee email -- surfaced back to Claude as a tool error
                # so it can ask the user for a correction, rather than
                # crashing the whole /agent request.
                output = {"error": str(exc)}
        else:
            output = {"error": f"未知工具：{name}"}

        state.tool_calls.append({"tool": name, "input": tool_input, "output": output})
        content = output if isinstance(output, str) else json.dumps(output, ensure_ascii=False)
        tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": content})
    return tool_results


def process_request(
    db: Session,
    project_id: str,
    user: dict,
    conversation_id: uuid.UUID | None,
    message: str,
    image_id: str | None = None,
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

    image_record = None
    if image_id:
        # Independent, project_id-scoped lookup -- NOT a reuse of
        # _lookup_vision_analysis (different return shape, no storage_path).
        # A tampered/foreign-project/stale image_id just resolves to None,
        # degrading to "no image attached" rather than leaking another
        # project's file or erroring the whole /agent request.
        image_record = (
            db.query(VisionAnalysis)
            .filter(VisionAnalysis.project_id == project_id, VisionAnalysis.id == image_id)
            .first()
        )

    db.add(
        Message(
            conversation_id=conversation.id,
            user_id=uuid.UUID(user["id"]),
            role="user",
            content=message,  # raw user text only -- never mutated
            metadata_=(
                {
                    "image": {
                        "image_id": str(image_record.id),
                        "filename": image_record.filename,
                        "storage_path": image_record.storage_path,
                    }
                }
                if image_record
                else None
            ),
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

    if image_record:
        # In-memory only, not persisted -- steers Claude to call the existing,
        # unmodified analyze_image tool with a known-good id instead of the
        # user having to type a filename it can't resolve.
        messages[-1]["content"] += (
            f"\n\n[使用者在此訊息上傳了一張圖片，image_id={image_record.id}。"
            f'請先呼叫 analyze_image(image_id="{image_record.id}") 取得分析結果，再回答使用者的問題。]'
        )

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
