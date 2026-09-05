# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status

Day 1 (spec2.md §37) is implemented and verified end-to-end: Docker scaffold, Supabase Auth (Google + Email/Password), Project CRUD, membership-only authorization. Day 2 is also implemented and verified end-to-end against a real T3 engineering PDF (PDF upload → Supabase Storage → PyMuPDF text extraction → fixed-size chunking → Voyage embedding → pgvector → Claude-generated answer with page citations); see "Day 2 implementation notes" below for details not in the spec. Day 3 (Claude Vision, Agent tool-selection loop, MCP server) is implemented and verified end-to-end against the same real T3 project — see "Day 3 implementation notes" below. Day 4 (Email Draft generation, Preview, Confirm & Send, Mock Email) is implemented and verified end-to-end with a real browser session — see "Day 4 implementation notes" below; Gmail OAuth (the real-send half of Day 4/§26) is intentionally not built yet, `EMAIL_MODE=mock` is the only working mode. `spec2.md` is the full specification and remains the source of truth; this file summarizes the parts most likely to be violated by default AI behavior, plus real implementation details that emerged during Days 1–4 and aren't in the spec (see "Implementation notes beyond the spec" below). Day 5 (buffer, Gmail OAuth if time allows, polish, RAG evaluation) is not yet built — follow §36/§37 build order for that.

`spec.md` is a superseded earlier draft (local-Docker-only, no auth, no multi-tenancy, ChromaDB) kept for history — do not follow it. `spec2.md` replaces it with a Supabase-backed, multi-tenant architecture.

## What this project is

A Project-scoped, multi-user AI Engineering Assistant, using 桃園國際機場第三航廈 (Taoyuan Airport Terminal 3) public engineering PDFs as demo data. The point is not a chatbot — it's a full pipeline:

```
Google Login → Project → Engineering Documents → RAG → Claude → Vision → Agent → MCP → Gmail
```

Demo flow: Google login → create project → upload PDF → RAG-index it (Voyage AI embeddings → pgvector) → ask questions in natural language → answer with source doc + page → upload an engineering image → Claude Vision analyzes it → Agent combines RAG + Vision into a meeting summary → user asks to email it → Agent drafts email → UI shows preview → user clicks Confirm Send → MCP `send_email` → Gmail API.

## Non-negotiable rules (spec2.md §32–33, §41)

1. Do not over-engineer; prefer simple Python functions over frameworks.
2. Do not introduce LangChain/LangGraph/multi-agent, BIM/IFC, or Calendar/Slack/Teams integration — these are explicit V2/V3 future extensions (§42), not MVP scope.
3. Do not add features outside `spec2.md`. Multi-tenancy is now IN scope (Project is the data-isolation unit) — this is the one major exclusion from the old `spec.md` that no longer applies.
4. **Never auto-send email.** Every send requires an explicit user "Confirm & Send" click after an Email Preview (§24–25) — this is the project's core Human-in-the-Loop demonstration.
5. Never hard-code API keys, OAuth secrets, or the Supabase service role key; keep `.env` out of git, commit only `.env.example` (§31–32).
6. **Backend never trusts a `user_id` from the frontend.** Every request must resolve identity from the JWT, then check `project_members` before allowing access to any project resource (§8, §32). Cross-project retrieval is forbidden — every RAG/vector query must filter by `project_id` (§14, §22).
7. Preserve `document_id` / `project_id` / `page` / `chunk_index` metadata through the entire RAG pipeline — the UI must always be able to show source + page number for an answer.
8. Vision analysis must describe only what's visibly observable — never assert structural safety, construction quality, or regulatory compliance unless explicit evidence exists (§17–18). Use "可觀察到 / 可能 / 疑似 / 需要人工確認" phrasing, not affirmative claims.
9. RAG answers must be grounded only in retrieved context; if context is insufficient, the LLM must respond with `目前提供的工程文件中沒有足夠資訊回答此問題。` rather than inventing facts (§16).
10. Don't log API keys, OAuth tokens, Supabase service role key, or full email contents (§32).
11. **Do not conflate the two Google OAuth flows.** Supabase Auth's Google login (scopes: openid/email/profile, for app identity) is a separate authorization from the Gmail-send OAuth (scope: `gmail.send`, for actually sending mail) — see `spec2.md` §26 for the two supported approaches (extending Supabase's OAuth with `additional_scopes` + manually persisted `provider_refresh_token`, or a fully separate Gmail-only OAuth flow). Pick one explicitly before implementing; don't assume the login token can send email.
12. `document_chunks.embedding` dimension (`VECTOR(N)`) must match the actual Voyage AI model's output dimension — don't guess it before checking the model docs (§9).

## Build order

Implement strictly P0 → P1 → P2 (§36), verifying the previous stage still works before moving on:

- **P0**: Google Login (Supabase Auth), Project CRUD, multi-user permission (project_members), PDF upload → Supabase Storage → parsing → chunking → Voyage embedding → pgvector, RAG, Source/Page citation.
- **P1**: Claude Vision, Agent, MCP, Email Draft generation, Human confirmation, Mock Email (`EMAIL_MODE=mock`).
- **P2**: Gmail OAuth, real Gmail API, Activity Log, UI polish, error handling, RAG evaluation.

Mirrors the five-day plan in §37 (this project is being built ahead of a specific job interview, so the schedule assumes 5 dedicated days, not 3): Day 1 = Docker/React/FastAPI scaffold + Supabase (Auth/Postgres/Storage) + Google Login + Project CRUD + membership-only authorization. Day 2 = PDF → chunking → Voyage embedding → pgvector → RAG + citations (budget extra time here — Chinese engineering PDFs with tables/drawings often extract poorly). Day 3 = Claude Vision + Agent tool-selection logic + MCP server (search_documents, send_email) — the MCP SDK is the least-familiar piece, keep the tool wrappers minimal rather than polishing protocol details. Day 4 = Email draft + Preview + Confirm/Send + mock email (get mock working first), then Gmail OAuth. Day 5 = buffer — finish or abandon Gmail OAuth (mock email is an acceptable fallback), polish, and run the full demo end-to-end 3-5 times until it reproduces without live debugging.

Two risk-reduction simplifications apply throughout (§37): (a) Gmail OAuth is a fully separate flow from Supabase Auth's Google login — not an extension of the login scope — so a stall on one doesn't block the other; (b) authorization starts as a simple "is this user a project member" check, not full owner/member role differentiation (the `role` column stays for later).

## Target architecture (spec2.md §4)

```
Browser → React+Tailwind → FastAPI Backend (JWT-authenticated)
                                          │
                    ┌─────────────────────┼─────────────────────┐
                    ▼                     ▼                     ▼
              RAG Service           Agent Service          Vision Service
                    │                     │                     │
                    │                     ▼                     │
                    │                 MCP Client                │
                    ▼                     ▼                     ▼
        ┌───────────────────────────────────────────────────────────┐
        │                      Supabase Cloud                        │
        │   Supabase Auth  │  PostgreSQL + pgvector  │  Storage       │
        └───────────────────────────────────────────────────────────┘
                    ▲
                    │
          Voyage AI (embeddings)  /  Claude API (LLM, Vision, Agent reasoning)

Agent → MCP Server → Gmail API
```

Local Docker runs `frontend`, `backend`, `mcp-server` (the last one added Day 3, §30/§33 — a second image built from `backend/Dockerfile.mcp` off the same `backend/` build context, so it shares `requirements.txt` and imports `app.services`/`app.models` directly rather than duplicating code into a separate top-level package; Streamable HTTP on the internal compose network only, at `mcp-server:8001`, never a published port the frontend/browser can reach — spec2.md §21's "MCP 不可繞過 Project Authorization" is enforced structurally this way, since the MCP server itself has no JWT/user context to check membership against and is simply unreachable from anywhere except the already-authorized backend). No local Postgres container of our own, no ChromaDB, no local LLM. "Supabase Cloud" in the diagram above was, early in development, actually the **local Supabase CLI stack** (`supabase start`); as of the Day 3 session, `.env` points at the real cloud project (`SUPABASE_URL`/`DATABASE_URL` both target `*.supabase.co`, the latter via the Session Pooler per implementation note 5 below) — the local CLI stack still works as a fallback (`npx supabase start`) but is no longer what a fresh `docker compose up` talks to by default; check `.env` before assuming which one is live. `docker compose down` losing state is a non-issue either way because nothing persistent lives in the `frontend`/`backend`/`mcp-server` containers themselves.

Actual structure (spec2.md §33, as built):

```
frontend/            React + Vite + Tailwind
  src/
    App.jsx, main.jsx, index.css
    pages/           Login.jsx (Google + Email/Password), Projects.jsx, ProjectDetail.jsx
    components/      Button/Input/Alert/Card/Badge/EmptyState/Tabs/Header/PageShell/Spinner,
                      DocumentsPanel.jsx, ChatPanel.jsx (Day 2), VisionPanel.jsx, AgentPanel.jsx (Day 3),
                      EmailPreviewCard.jsx (Day 4, rendered inline inside AgentPanel -- no Email tab)
    hooks/           useSession.js
    lib/             supabaseClient.js, api.js
backend/app/
  main.py
  api/               auth.py, projects.py, documents.py, chat.py, vision.py, agent.py, email.py (Day 4)
  core/              config.py, database.py (SQLAlchemy engine/session),
                      auth.py (JWKS verification), authorization.py,
                      supabase_client.py (Storage/Auth-admin only)
  models/            SQLAlchemy ORM: project.py, document.py, conversation.py, email_log.py, vision.py (Day 3)
  schemas/           project.py, document.py (Pydantic; Document/Chat/Conversation/Message),
                      vision.py, agent.py (Day 3), email.py (Day 4)
  services/          pdf_service.py (extract/chunk), embedding_service.py (Voyage),
                      claude_service.py (RAG + Vision + summary + email draft generation),
                      rag_service.py (ingest/retrieve orchestration), vision_service.py (Day 3),
                      email_service.py (Day 4 -- save_draft/generate_preview/confirm_and_send)
  agent/             agent_service.py (Day 3 -- process_request/select_tools/execute_workflow,
                     hand-rolled Claude tool-use loop, no framework; Day 4 added the draft_email
                     branch, see "Day 4 implementation notes")
  mcp/               server.py, client.py, tools/{search_documents,send_email}.py (Day 3 scaffold,
                     send_email.py's real mock-mode logic landed Day 4 --
                     ships into backend/Dockerfile.mcp, a second image from the same build context)
  alembic/           env.py, versions/0001_initial_schema.py .. 0003_vision_analyses.py
  alembic.ini
data/temp/
data/samples/        gitignored -- sample T3 PDFs used for local extraction/RAG testing, not committed
supabase/            config.toml (local CLI stack config, spec2.md doesn't mention this —
                     it's a Day-1 addition, see below)
docker-compose.yml   services: frontend, backend, mcp-server (postgres/auth/storage come from
                     Supabase -- local CLI stack or cloud project depending on .env, not a
                     container here)
```

## Data model (spec2.md §9)

Core tables: `projects`, `project_members` (role: owner/member), `documents` (status: uploaded/processing/ready/failed), `document_chunks` (page, chunk_index, embedding VECTOR(N)), `conversations`, `messages` (role: user/assistant/system/tool), `email_logs` (status: draft/confirmed/sent/failed/cancelled). Storage path convention: `projects/{project_id}/documents/{document_id}/{filename}` and `projects/{project_id}/images/{image_id}/{filename}` (§10).

`vision_analyses` (Day 3 addition, not in spec2.md §9 -- the spec never defines a table for Vision results, only the §17 response shape `{analysis, observations, limitations}`): `id`, `project_id`, `uploaded_by`, `filename`, `storage_path`, `file_size`, `analysis` (text), `observations`/`limitations` (JSONB arrays), `created_at`. Named for the analysis row, not the raw image (which lives only in Storage) -- same split as `documents` vs `document_chunks`.

## Key API endpoints (spec2.md §27)

```
GET  /api/auth/me
GET  /api/projects
POST /api/projects
GET  /api/projects/{project_id}
POST /api/projects/{project_id}/documents
GET  /api/projects/{project_id}/documents
DELETE /api/projects/{project_id}/documents/{document_id}
POST /api/projects/{project_id}/chat
GET  /api/projects/{project_id}/conversations
GET  /api/conversations/{conversation_id}
POST /api/projects/{project_id}/vision
GET  /api/projects/{project_id}/vision       -- Day 3 addition beyond spec2.md §27, for VisionPanel history
POST /api/projects/{project_id}/agent
POST /api/projects/{project_id}/email/preview  -- Day 4
POST /api/projects/{project_id}/email/send     -- Day 4, must go through the MCP tool, never bypass MCP
GET  /api/health
```

Every project-scoped route must resolve `current_user` from the JWT and verify `project_members` before touching that project's rows.

## Implementation notes beyond the spec

These are Day 1 decisions/discoveries that aren't in `spec2.md` but should be treated as settled, not re-litigated:

1. **Table access is SQLAlchemy + Alembic, direct Postgres connection — not Supabase's Data API/PostgREST.** `spec2.md` says "Database: Supabase PostgreSQL" but doesn't mandate `supabase-py`'s `.table()` client. Since the frontend never queries tables directly (only `backend/app/core/database.py` does, via `DATABASE_URL`), routing through PostgREST added no value and only added attack surface — so Supabase's **"Enable Data API" setting is turned off**. `supabase_client.py` (the `supabase-py` client) is kept only for Storage (Day 2+) and any Auth-admin calls, never for table CRUD. Schema changes go through Alembic revisions (`backend/alembic/versions/`), applied identically to local and cloud via `alembic upgrade head` against whatever `DATABASE_URL` points at.

2. **User session tokens are verified via JWKS, not a shared HS256 secret.** Current Supabase (both the local CLI stack and, most likely, any newly-created cloud project) signs user JWTs with an asymmetric key (ES256), published at `<SUPABASE_URL>/auth/v1/.well-known/jwks.json`. `app/core/auth.py` uses `jwt.PyJWKClient` against that endpoint — there is no `SUPABASE_JWT_SECRET` env var. If a real cloud project ever turns out to still issue legacy HS256 tokens, this would need a fallback path, but don't add one speculatively — confirm first (decode a real token's header and check `alg`).

3. **Local development runs against the Supabase CLI (`supabase start`), not supabase.com**, because Supabase had a platform-side outage affecting project creation during Day 1. The CLI spins up a full local stack (Postgres, GoTrue Auth, Storage, Kong gateway, Studio, Inbucket for catching dev emails) — see `supabase/config.toml`. `docker-compose.yml` no longer runs its own `postgres` service; the `backend`/`frontend` containers reach the CLI stack via `host.docker.internal`. Moving to the real cloud project later is: create it, disable its Data API, copy its URL/keys into `.env`, re-run `alembic upgrade head` against it — no code changes. **Update, Day 3:** this has since happened — `.env` now points at the real cloud project (matches implementation note 5's Session Pooler `DATABASE_URL`), so a fresh `docker compose up` talks to the cloud project by default, not the local CLI stack. `npx supabase start` still works as a fallback stack, but check `.env` before assuming which one is live.

4. **Email/Password login exists alongside Google login, for local dev convenience only.** `spec2.md`'s demo flow (§2, §39) is Google-login-only — don't remove the Google button or make Email/Password the primary flow in any user-facing copy. It's there because wiring real Google OAuth requires external setup (Google Cloud Console + Supabase provider config) that shouldn't block testing the rest of the stack; `supabase/config.toml` has `enable_confirmations = false` under `[auth.email]` so signup doesn't need a confirmation-email round trip locally.

5. **The cloud project's `DATABASE_URL` must use the Session Pooler, not the direct connection.** Supabase's direct-connection host (`db.<ref>.supabase.co:5432`) is IPv6-only; Docker containers have no IPv6 route by default, so `alembic upgrade head` / the app fail with `Network is unreachable`. Use the Session Pooler connection string instead (`postgres.<ref>@aws-0-<region>.pooler.supabase.com:5432` — note the username includes the project ref) — it's IPv4 and, unlike the Transaction Pooler, still supports prepared statements/session state, so it's fine for FastAPI's long-running process. Also: Alembic's `alembic.ini` is backed by `configparser`, which treats `%` as its own interpolation syntax — a URL-encoded password containing `%25` breaks `config.set_main_option()` unless escaped to `%%` first (see `backend/alembic/env.py`).

## Day 2 implementation notes

Verified against 4 real public T3 engineering PDFs (129 pages total; see `data/samples/`, gitignored — not committed, copyrighted third-party content). Full pipeline (upload → extract → chunk → embed → retrieve → generate) confirmed end-to-end via direct API calls against the real local Supabase stack, real Voyage AI, and real Claude API — not just unit tests.

1. **PyMuPDF (`pymupdf`, imported as `pymupdf`, not the older `fitz` alias) for text extraction.** Chinese body text extracts cleanly with correct encoding. Confirmed risk from spec2.md §37: tables lose their grid structure — cells come out as a flat sequence of lines with no column association (e.g. a "year | passenger count" table becomes a run of years and numbers with no pairing). Accepted as-is for MVP (numbers/labels are still present for semantic retrieval, just not precisely aligned) — do not build table-aware extraction unless retrieval quality on tabular questions turns out to actually matter in the demo.

2. **Chunking uses character count as a token-count proxy, not a real tokenizer.** `CHUNK_SIZE=1000` / `CHUNK_OVERLAP=150` (`backend/app/services/pdf_service.py`) approximate spec2.md §12's 800-1200 token / 100-200 overlap target — Chinese text runs roughly 1 token/char under most tokenizers, so pulling in `tiktoken` or similar for this estimate would be over-engineering. Chunks never cross a page boundary, so `page` metadata stays exact.

3. **Storage bucket (`engineering-documents`) is created lazily at runtime**, not via `supabase/config.toml` or a migration — `documents.py`'s `_ensure_bucket()` calls `storage.create_bucket` and swallows the "already exists" error. No local-only bucket config exists for it, so this same code path provisions it identically on first use against the cloud project too.

4. **Background ingestion runs on its own DB session, not the request's.** `BackgroundTasks` (FastAPI) executes after the upload response is sent, by which point the request-scoped `Depends(get_db)` session is already closed — `_process_document_task` opens a fresh `SessionLocal()` instead. Tests that upload documents monkeypatch `rag_service.ingest_document` to a no-op (see `tests/test_documents.py`) so the suite doesn't make real Voyage API calls on every run; the real ingestion path is covered by manual end-to-end testing plus `tests/test_rag.py`'s pure-DB tests of `retrieve_chunks` (project isolation, cosine-distance ordering) using hand-inserted embedding vectors.

5. **`CLAUDE_MODEL` defaults to `claude-sonnet-5`.**

## Day 3 implementation notes

Verified end-to-end against the same real ingested T3 project from Day 2 (all 4 PDFs, `project_id a736dc13-...`): a real construction-photo-style image through `POST /vision`, a real `search_documents`/`analyze_image`/`generate_summary` Agent run producing a genuine Meeting Summary with page-cited sources, a real cross-container MCP round trip (`backend` → `mcp-server:8001` → real pgvector results), and a real `send_email` request confirming zero `email_logs` rows and zero MCP calls for that tool. Not just unit tests — see `tests/test_vision.py`, `tests/test_agent.py`, `tests/test_mcp_tools.py` for the mocked/pure-DB automated coverage on top of that.

1. **MCP SDK is `mcp` 2.x, where `FastMCP` was renamed to `MCPServer`.** Most existing tutorials/examples describe the pre-2.0 `from mcp.server.fastmcp import FastMCP` API; that import raises `ModuleNotFoundError` on this installed version. Use `from mcp.server.mcpserver import MCPServer` instead — `@mcp.tool()`, `mcp.run(transport=...)` work the same shape. Client side: the streamable-HTTP connector function is `mcp.client.streamable_http.streamable_http_client` (not `streamablehttp_client`, despite that being the v1 name), and it yields a 2-tuple `(read, write)`, not v1's 3-tuple with a session-id getter.

2. **A tool whose return type annotation is a `list` gets auto-wrapped by the SDK as `{"result": [...]}`**, because MCP structured content must be a JSON object at the top level — a bare list return isn't valid structured content. `app/mcp/client.py`'s `call_tool()` unwraps this (`{"result": [...]}` → `[...]`) transparently so callers never see the envelope; a tool returning a `dict` (e.g. `send_email`) passes through unchanged. Confirmed empirically (`fn_metadata.output_schema` on the registered tool), not assumed from memory of an older SDK version.

3. **Fixed a real, pre-existing JWT clock-skew bug while testing Day 3 against the cloud project**: `app/core/auth.py`'s `jwt.decode(...)` had no `leeway`, so a freshly-issued Supabase token could intermittently fail with `ImmatureSignatureError('The token is not yet valid (iat)')` if the backend container's clock was even a couple seconds behind the token's `iat`. This isn't Day-3-specific (it affects every authenticated route) but surfaced during Day 3's heavier request cadence — fixed with `leeway=30` on the `jwt.decode` call. Not a Day 3 scope creep to leave in place; a genuine correctness fix.

4. **`vision_analyses` is a Day 3 schema addition beyond spec2.md §9** (see "Data model" above) — the spec's data model section predates Vision/Agent and never defines a table for analysis results. Chosen over "no persistence" or piggybacking on `messages.metadata` so the Agent's `analyze_image` tool (see note 6) has something durable to look up, and so `VisionPanel.jsx` can show history across page loads.

5. **`mcp-server` ships as a second Docker image from the same `backend/` build context** (`backend/Dockerfile.mcp`), not a separate top-level package — see "Target architecture" above for why. `requirements.txt` is shared between the two images; adding `mcp` to it covers both.

6. **The Agent's `analyze_image` tool looks up an already-persisted `vision_analyses` row rather than re-running Claude Vision mid-conversation.** The `POST /agent` request body is just `{conversation_id, message}` — no image bytes — so there's nothing to re-analyze even if it wanted to. The intended flow is: upload+analyze once via the Vision tab, then ask the Agent to fold that result into a summary (matches spec2.md §20's example flow exactly: `search_documents → analyze_image → generate_summary`). `image_id` is optional in the tool's input schema; omitted, it uses the project's most recently analyzed image.

7. **`send_email` is registered as a real tool Claude can select** (so tool-selection logic is genuinely exercised, not stubbed out of the loop entirely), **but `agent_service.execute_workflow`'s branch for it never calls the MCP client** — it returns a canned "not yet available" dict locally. This is deliberate, not a shortcut: spec2.md §24 forbids the Agent from auto-sending, and Day 3's job is only to prove `search_documents`/`send_email` are wired through MCP at all, not to let the Agent actually invoke a send. The real `send_email` MCP tool is proven separately, directly, bypassing the Agent (`tests/test_mcp_tools.py`, and manually via `app/mcp/client.py`). `tests/test_agent.py::test_agent_never_calls_mcp_send_email` pins this boundary by making the MCP client raise if it's ever called for `send_email`.

8. **`SessionLocal(autoflush=False)` project-wide** (see `app/core/database.py`) means a just-`db.add()`-ed row isn't visible to a subsequent query in the same session without an explicit `db.flush()` — hit `agent_service.process_request` once (the freshly-added user `Message` wasn't visible when building the conversation history for the first Claude call, raising `anthropic.BadRequestError: messages: at least one message is required`). Fixed with an explicit `db.flush()` right after adding it. Worth remembering for any future code that adds-then-immediately-queries within one request.

## Day 4 implementation notes

Verified end-to-end with a real headless-browser session (Playwright, driven manually — not just `pytest`): logged in, opened a fresh project, asked the Agent in natural language to email someone, got back a real Claude-composed draft rendered as an inline Email Preview card, clicked Confirm & Send, and confirmed the `email_logs` row reached `status="sent"` with `mcp-server`'s log showing `[MOCK EMAIL] to=... subject=...`. Automated coverage: `tests/test_email.py` (new), plus updated `tests/test_agent.py`/`tests/test_mcp_tools.py` — 52/52 passing.

1. **The Agent's Day 3 `send_email` tool is renamed to `draft_email`.** It never sent anything even in Day 3 (see Day 3 note 7) — keeping the name `send_email` for a tool that only ever drafts was judged actively misleading (a tool-call log entry reading "Agent called send_email" looks like a violation of spec2.md §24 even though it isn't). `draft_email` now actually does something: `agent_service.execute_workflow`'s branch persists an `EmailLog(status="draft")` via `app/services/email_service.save_draft` — still **never touches `mcp_client`**, so `tests/test_agent.py`'s human-in-the-loop guarantee test (renamed `test_agent_draft_email_persists_draft_but_never_calls_mcp`) still pins the same boundary Day 3 established, just with a real assertion instead of a stub check.

2. **`mcp-server` has no hot-reload — a source edit there needs `docker compose restart mcp-server`.** Unlike `backend` (runs `uvicorn --reload`, confirmed by its startup log: "Started reloader process ... using WatchFiles"), `Dockerfile.mcp`'s `CMD ["python", "-m", "app.mcp.server"]` has no reload wrapper, even though the same `./backend/app:/app/app` volume is mounted. Editing `app/mcp/tools/send_email.py` and testing against the already-running container silently exercised the *old* Day-3 stub — the browser-driven verification run first "confirmed" a real bug (an `email_logs` row stuck at `status="failed"`) that was actually just a stale container. Always restart `mcp-server` after touching anything under `app/mcp/`.

3. **Python's root logger defaults to `WARNING`, so a bare `logger.info(...)` is silently dropped unless something configures the level.** `send_email.py`'s mock-send confirmation log used `logger.info` and never appeared anywhere, even after the `mcp-server` restart from note 2 — nothing in this codebase calls `logging.basicConfig` or configures level for app loggers (`main.py`'s `logger.exception(...)` "worked" only because `.exception()` logs at ERROR, always above the default threshold). Fixed with `logging.basicConfig(level=logging.INFO)` in `app/mcp/server.py`'s `if __name__ == "__main__":` block, scoped to the `mcp-server` process since that's the only place a new INFO-level log was added. If `backend` ever needs INFO-level app logging, it will need the same treatment — don't assume `logger.info` calls anywhere in this codebase are actually visible without checking.

4. **A real frontend bug, caught only by the manual browser run, not by `pytest`:** `EmailPreviewCard.jsx`'s send handler originally called `setStatus('sent')` unconditionally whenever `apiPost` didn't throw — but `POST /email/send` can return HTTP 200 with `{"status": "failed", ...}` as a legitimate business outcome (e.g. a non-mock `EMAIL_MODE`), not just via an HTTP error. The card was showing "已寄出" for a send that had actually failed. Fixed to read the response body's own `status` field. This is exactly the class of bug the "start the dev server and use the feature in a browser" rule exists to catch — the backend test suite was fully green the whole time this bug existed, because no backend test exercises the frontend's interpretation of a 200 response.

5. **`draft_email`'s content and `/email/preview`'s content converge on one function, `email_service.save_draft`.** The Agent tool path has Claude compose `to`/`subject`/`body` directly as tool-call arguments (one Claude call, already in the tool-use loop); `POST /email/preview` is a standalone entrypoint (spec2.md §27) that does a dedicated `claude_service.generate_email_draft` call first, optionally seeded with an existing conversation's message history. Both then call the same `save_draft` to persist a `status="draft"` row — no duplicated persistence logic between the two trigger paths.

6. **No new "Email" tab.** spec2.md §28's own Project Page mockup lists only `Documents │ Chat │ Vision │ Activity` — Email Preview is drawn as a card, not a tab, and §24's flow diagram starts at "User → Agent". The Preview (§25's exact To/Subject/Body/Cancel/Confirm & Send layout) renders inline inside `AgentPanel.jsx` whenever a tool call's `tool === 'draft_email'` is found. Cancel is client-side only (no `cancelled` status is ever written) — the `draft` row is harmless history, and there's no cancel/delete endpoint in spec2.md §27's Email section to call anyway.

7. **Scope stops at Mock Email.** `app/mcp/tools/send_email.py` now branches on `EMAIL_MODE`: `"mock"` logs and returns `status: "sent"`; anything else returns `status: "failed"` with an explanatory message, rather than pretending to send. Real Gmail OAuth (spec2.md §26) is a deliberately separate, not-yet-started follow-up — see "Email execution path" below, now updated to match.

## LLM / embedding providers

Unlike the earlier draft, `spec2.md` does **not** ask for a swappable multi-provider abstraction: Claude API is the fixed LLM/Vision provider, Voyage AI is the fixed embedding provider (§5–6, §41). Still isolate them behind `claude_service.py` / `embedding_service.py` so provider-specific details don't leak into `rag_service.py` or `agent_service.py` — but don't build a `LLM_PROVIDER=gemini|anthropic` switch; that abstraction was dropped in this spec version.

Claude handles reasoning/generation/vision; Voyage AI only does embeddings; pgvector only does similarity search. Don't blur these responsibilities (§6, §41).

## Email execution path

Two independent OAuth concerns, per §11 above and `spec2.md` §26 — do not build one and assume it covers the other:

```
Supabase Auth (Google login, app identity)         ──unrelated to──►  Gmail OAuth (gmail.send scope, execution)
                                                                              │
                                                                              ▼
                                                        MCP send_email() → Gmail API
```

The mock-mode path (`EMAIL_MODE=mock`, `app/mcp/tools/send_email.py` logs `[MOCK EMAIL] to=... subject=...` — never the body, per the no-full-email-content logging rule below — and returns `status: "sent"`) is built and verified as of Day 4; see "Day 4 implementation notes" above. `email_send` always goes through the MCP tool — never call Gmail API directly from an API route; `email_service.confirm_and_send` (`app/services/email_service.py`) is the only caller of `mcp_client.call_tool("send_email", ...)`, itself only reachable from `POST /email/send`, itself only reachable from a user's explicit "Confirm & Send" click.

**Real Gmail OAuth is not yet built.** A non-mock `EMAIL_MODE` currently makes `send_email.py` return `status: "failed"` cleanly rather than attempting anything — no Gmail client/service file exists anywhere in the codebase yet, and `GMAIL_CLIENT_ID`/`GMAIL_CLIENT_SECRET`/`GMAIL_REDIRECT_URI` are declared in `config.py` but unused. Per spec2.md §37's own risk-reduction note, this is an acceptable place to stop for the MVP demo (mock email is a legitimate fallback) — pick up real Gmail OAuth as a separate follow-up, choosing one of the two approaches in §26 explicitly before implementing (don't assume which one without deciding first).

## Security minimums (spec2.md §32)

Validate uploaded file types and filenames; enforce upload size limits (PDF 100MB, image 10MB — carried over from `spec.md`, not restated numerically in `spec2.md` but still the working assumption); validate email addresses; never expose API keys, OAuth secrets, or the Supabase service role key in error messages or logs. `SUPABASE_SERVICE_ROLE_KEY` must only ever exist in the backend, never sent to the frontend.

## Commands

```bash
npx supabase start                                      # local Auth/Postgres/Storage fallback stack (only if .env points at it)
docker compose build
docker compose up -d                                     # frontend, backend, mcp-server
docker compose run --rm backend alembic upgrade head    # first run, or whenever a migration is added
docker compose logs -f
docker compose logs -f mcp-server                        # MCP server's own log stream (Day 3)
docker compose restart mcp-server                        # required after any edit under backend/app/mcp/ -- no hot-reload (Day 4 note 2)
docker compose down                                      # frontend/backend/mcp-server only; Supabase data untouched either way
npx supabase stop                                        # stop local Supabase fallback stack (keeps data)
```

- Frontend: http://localhost:5173
- Backend Swagger: http://localhost:8000/docs
- Health check: http://localhost:8000/api/health
- MCP server (internal only in production; host-published for local debugging): http://localhost:8001/mcp
- Supabase Studio (local stack only): http://localhost:54323
- Inbucket (local stack dev email catcher): http://localhost:54324

Backend tests require whatever `DATABASE_URL` in `.env` currently points at to be reachable (cloud project or local CLI stack — see implementation note 3 above): `docker compose exec backend python -m pytest -v`. Tests override `get_current_user` with fake users (`tests/conftest.py`) — they exercise our authorization/CRUD logic, not Supabase's token issuance — and wrap each test in a rolled-back SAVEPOINT against the real Postgres schema (UUID/JSONB/pgvector types don't work cleanly against SQLite, so this isn't mocked out).
