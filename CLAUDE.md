# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status

P0 → P1 → P2 are all implemented and verified end-to-end against the real cloud Supabase project, real Voyage/Claude APIs, and real Gmail (`EMAIL_MODE=gmail` is live in `.env`; `EMAIL_MODE=mock` remains the default and a fully supported fallback). `spec2.md` is the full specification and remains the source of truth; this file summarizes the parts most likely to be violated by default AI behavior, plus standing implementation decisions not in the spec. Full day-by-day build history, bug discoveries, and verification narratives live in `docs/CHANGELOG.md` (gitignored, not part of the shared repo) — this file keeps only current, still-applicable rules.

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
11. **Do not conflate the two Google OAuth flows.** Supabase Auth's Google login (scopes: openid/email/profile, for app identity) is a separate authorization from the Gmail-send OAuth (scope: `gmail.send`, for actually sending mail) — see `spec2.md` §26. **Decided and built:** a fully separate Gmail-only OAuth flow, not an extension of Supabase's login scope — see "Standing decisions & known gotchas → Gmail OAuth" below. Don't assume the login token can send email.
12. `document_chunks.embedding` dimension (`VECTOR(N)`) must match the actual Voyage AI model's output dimension — don't guess it before checking the model docs (§9).

## Build order

Implement strictly P0 → P1 → P2 (§36), verifying the previous stage still works before moving on:

- **P0**: Google Login (Supabase Auth), Project CRUD, multi-user permission (project_members), PDF upload → Supabase Storage → parsing → chunking → Voyage embedding → pgvector, RAG, Source/Page citation.
- **P1**: Claude Vision, Agent, MCP, Email Draft generation, Human confirmation, Mock Email (`EMAIL_MODE=mock`).
- **P2**: Gmail OAuth, real Gmail API, Activity Log, UI polish, error handling, RAG evaluation.

All three stages are complete. The build followed a five-day plan (§37) — full day-by-day narrative is in `docs/CHANGELOG.md`. Two risk-reduction simplifications from §37 remain load-bearing design decisions, not just history: (a) Gmail OAuth is a fully separate flow from Supabase Auth's Google login, not an extension of the login scope (rule #11); (b) authorization is a simple "is this user a project member" check, not full owner/member role differentiation (the `role` column stays for later).

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

Local Docker runs `frontend`, `backend`, `mcp-server` — the last one is a second image built from `backend/Dockerfile.mcp` off the same `backend/` build context, so it shares `requirements.txt` and imports `app.services`/`app.models` directly rather than duplicating code into a separate top-level package. It runs Streamable HTTP on the internal compose network only, at `mcp-server:8001`, never a published port the frontend/browser can reach — spec2.md §21's "MCP 不可繞過 Project Authorization" is enforced structurally this way, since the MCP server itself has no JWT/user context to check membership against and is simply unreachable from anywhere except the already-authorized backend. No local Postgres container of our own, no ChromaDB, no local LLM.

`.env` currently points `SUPABASE_URL`/`DATABASE_URL` at the real cloud project (`*.supabase.co`, via the Session Pooler — see "Standing decisions" below). `npx supabase start` still works as a local CLI fallback stack, but check `.env` before assuming which one is live. `docker compose down` losing state is a non-issue either way because nothing persistent lives in the `frontend`/`backend`/`mcp-server` containers themselves.

Actual structure (spec2.md §33, as built):

```
frontend/            React + Vite + Tailwind
  src/
    App.jsx, main.jsx, index.css
    pages/           Login.jsx (Google + Email/Password), Projects.jsx, ProjectDetail.jsx,
                      Settings.jsx (Connect/Disconnect Gmail -- the one account-level,
                      non-project-scoped page)
    components/      Button/Input/Alert/Card/Badge/EmptyState/Tabs/Header/PageShell/Spinner,
                      DocumentsPanel.jsx, ChatPanel.jsx, VisionPanel.jsx, AgentPanel.jsx,
                      EmailPreviewCard.jsx (rendered inline inside AgentPanel -- no Email tab),
                      ActivityPanel.jsx
    hooks/           useSession.js
    lib/             supabaseClient.js, api.js
backend/app/
  main.py
  api/               auth.py, projects.py, documents.py, chat.py, vision.py, agent.py, email.py,
                      activity.py, gmail.py (authorize-url/callback/status/disconnect,
                      account-level, not project-scoped)
  core/              config.py, database.py (SQLAlchemy engine/session),
                      auth.py (JWKS verification), authorization.py,
                      supabase_client.py (Storage/Auth-admin only)
  models/            SQLAlchemy ORM: project.py, document.py, conversation.py, email_log.py, vision.py,
                      activity_log.py, gmail_credential.py
  schemas/           project.py, document.py (Pydantic; Document/Chat/Conversation/Message),
                      vision.py, agent.py, email.py, activity.py
  services/          pdf_service.py (extract/chunk), embedding_service.py (Voyage),
                      claude_service.py (RAG + Vision + summary + email draft generation),
                      rag_service.py (ingest/retrieve orchestration), vision_service.py,
                      email_service.py (save_draft/generate_preview/confirm_and_send),
                      activity_service.py (log_activity helper),
                      gmail_service.py (OAuth code exchange/refresh/send, raw httpx
                      against Google's endpoints, no google-api-python-client)
  agent/             agent_service.py (process_request/select_tools/execute_workflow,
                     hand-rolled Claude tool-use loop, no framework)
  mcp/               server.py, client.py, tools/{search_documents,send_email}.py
                     (ships into backend/Dockerfile.mcp, a second image from the same build context)
  alembic/           env.py, versions/0001_initial_schema.py .. 0005_gmail_credentials.py
  alembic.ini
backend/scripts/     eval_rag.py + rag_eval_fixture.json (spec2.md §38 -- standalone, not pytest;
                     mounted into the backend container via its own docker-compose.yml volume line)
data/temp/
data/samples/        gitignored -- sample T3 PDFs used for local extraction/RAG testing, not committed
supabase/            config.toml (local CLI stack config, not mentioned in spec2.md)
docker-compose.yml   services: frontend, backend, mcp-server (postgres/auth/storage come from
                     Supabase -- local CLI stack or cloud project depending on .env, not a
                     container here)
```

## Data model (spec2.md §9)

Core tables: `projects`, `project_members` (role: owner/member), `documents` (status: uploaded/processing/ready/failed), `document_chunks` (page, chunk_index, embedding VECTOR(N)), `conversations`, `messages` (role: user/assistant/system/tool), `email_logs` (status: draft/confirmed/sent/failed/cancelled). Storage path convention: `projects/{project_id}/documents/{document_id}/{filename}` and `projects/{project_id}/images/{image_id}/{filename}` (§10).

`vision_analyses` (not in spec2.md §9 -- the spec never defines a table for Vision results, only the §17 response shape `{analysis, observations, limitations}`): `id`, `project_id`, `uploaded_by`, `filename`, `storage_path`, `file_size`, `analysis` (text), `observations`/`limitations` (JSONB arrays), `created_at`. Named for the analysis row, not the raw image (which lives only in Storage) -- same split as `documents` vs `document_chunks`.

`activity_logs` (backing spec2.md §29's Activity Log): `id`, `project_id` (nullable -- `NULL` only for the `user_logged_in` event, which has no project context), `user_id`, `event_type` (`CheckConstraint`-enforced to the 11 values in spec2.md §29's workflow chain), `detail` (free text -- recipient/filename only, never email body/subject or API keys), `created_at`.

`gmail_credentials` (not in spec2.md §9): `user_id` (primary key, bare Supabase UUID, no FK -- same no-local-users-table pattern as `project_members.user_id`), `gmail_email` (nullable, best-effort), `encrypted_refresh_token` (Fernet ciphertext, never plaintext), `created_at`/`updated_at`. One row per user -- connecting again overwrites the prior credential. Deliberately **not** logged in `activity_logs` (connect/disconnect aren't part of spec2.md §29's 11-value event chain).

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
GET  /api/projects/{project_id}/vision       -- beyond spec2.md §27, for VisionPanel history
POST /api/projects/{project_id}/agent
POST /api/projects/{project_id}/email/preview
POST /api/projects/{project_id}/email/send     -- must go through the MCP tool, never bypass MCP
GET  /api/projects/{project_id}/activity       -- beyond spec2.md §27, backs the Activity tab
GET  /api/gmail/authorize-url                  -- account-level (not project-scoped)
GET  /api/gmail/callback                       -- Google's redirect target; no auth dependency, see notes below
GET  /api/gmail/status
POST /api/gmail/disconnect
GET  /api/health
```

Every project-scoped route must resolve `current_user` from the JWT and verify `project_members` before touching that project's rows.

## Standing decisions & known gotchas

Settled, not re-litigated. Full narrative/discovery context for each of these is in `docs/CHANGELOG.md` if you need it — this section only states what's still true.

**Database & backend**
- Table access is SQLAlchemy + Alembic direct Postgres connection, never Supabase's Data API/PostgREST — Data API is deliberately disabled. `supabase_client.py` (`supabase-py`) is only for Storage and Auth-admin calls.
- JWT verification uses JWKS (ES256 via `jwt.PyJWKClient`), not a shared HS256 secret — there is no `SUPABASE_JWT_SECRET`. `jwt.decode(..., leeway=30)` is required to tolerate clock skew between the backend container and Supabase's token `iat` — do not remove.
- Cloud `DATABASE_URL` must use the Session Pooler (`postgres.<ref>@aws-0-<region>.pooler.supabase.com:5432`), not the direct connection host — the direct host is IPv6-only and unreachable from Docker.
- `SessionLocal(autoflush=False)` project-wide — a just-`db.add()`-ed row is not visible to a subsequent query in the same session without an explicit `db.flush()`.
- PyMuPDF is imported as `pymupdf`, not `fitz`. Tables lose grid structure on extraction — accepted for MVP, do not build table-aware extraction.
- Chunking uses character count as a token-count proxy (`CHUNK_SIZE=1000`/`CHUNK_OVERLAP=150`), not a real tokenizer. Chunks never cross a page boundary.
- Storage bucket (`engineering-documents`) is created lazily at runtime (`_ensure_bucket()`), not via config or migration.
- Background PDF ingestion opens its own `SessionLocal()` — the request-scoped session is already closed by the time `BackgroundTasks` runs.
- PDF upload validates both the `.pdf` extension and a `%PDF-` magic-byte check; a failed background ingestion is caught and logged (`logger.exception`), not left to vanish silently.
- `CLAUDE_MODEL` defaults to `claude-sonnet-5`.
- Every route file wraps Voyage/Claude/MCP failures in `HTTPException(502, "...")` with a Chinese message — `chat.py`, `agent.py` included.

**MCP**
- SDK is `mcp` 2.x: `from mcp.server.mcpserver import MCPServer` (not the pre-2.0 `fastmcp` import). Client uses `mcp.client.streamable_http.streamable_http_client`, which yields a 2-tuple `(read, write)`.
- A tool returning a bare `list` is auto-wrapped by the SDK as `{"result": [...]}`; `app/mcp/client.py`'s `call_tool()` unwraps this transparently. A `dict` return (e.g. `send_email`) passes through unchanged.
- `mcp-server` has **no hot-reload** — restart after any edit under `backend/app/mcp/`: `docker compose restart mcp-server`.
- Python's root logger defaults to `WARNING`; `app/mcp/server.py` calls `logging.basicConfig(level=logging.INFO)` so `logger.info` calls are actually visible in `docker compose logs mcp-server`.
- `send_email`'s MCP tool signature requires a `user_id` argument — Gmail mode needs to know whose credential to use, and MCP has no session/JWT context of its own.

**Agent**
- The Agent's email tool is `draft_email`, not `send_email` — it only ever persists an `EmailLog(status="draft")` via `email_service.save_draft` and **never calls the MCP client**. `tests/test_agent.py` pins this human-in-the-loop boundary.
- `analyze_image` looks up an already-persisted `vision_analyses` row (no image bytes in `/agent` requests, so nothing to re-analyze). Validate `image_id` as a UUID before querying it — a non-UUID string (e.g. a pasted filename) must return `{"error": ...}`, not crash the request with an unhandled Postgres type error.
- A request to revise/shorten/reword an already-generated draft must trigger a fresh `draft_email` tool call — `AGENT_SYSTEM_PROMPT` explicitly requires this, because the Agent only replays plain-text history across turns (no structural memory of prior tool calls) and could otherwise narrate a fabricated "revised" draft with no real tool call behind it.
- `execute_workflow` must catch its own `ValueError` (e.g. bad email format from `save_draft`) and return `{"error": ...}` as the tool's output — never let it propagate, since `app/api/agent.py`'s `except ValueError` is reserved for "conversation not found" and would mislabel the error.

**Email / Gmail**
- `draft_email` (Agent tool) and `POST /email/preview` both converge on `email_service.save_draft` as the single persistence point — no duplicated logic between the two trigger paths.
- `confirm_and_send` takes the confirming user's `user_id` (not necessarily whoever drafted the email) so `email_sent`/`user_confirmed_email` activity events attribute correctly.
- No Google client libraries — `gmail_service.py` makes three raw `httpx` calls (auth-code exchange, refresh-token exchange, send) directly against Google's endpoints.
- No access-token caching — every send re-exchanges the encrypted refresh token (Fernet, `GMAIL_TOKEN_ENCRYPTION_KEY`) for an access token immediately before sending.
- `GET /api/gmail/callback` has no JWT/`get_current_user` dependency (Google's redirect is a top-level browser navigation with no Authorization header) — identity comes from a short-lived (5 min) signed `state` JWT, signed with `GMAIL_CLIENT_SECRET`.
- `gmail_email` (shown on Settings) is best-effort and often `NULL` — the `gmail.send` scope does not authorize the profile-lookup endpoint. **Do not widen the OAuth scope** just to populate this cosmetic field.
- One Gmail account per user (`gmail_credentials.user_id` is the primary key) — reconnecting overwrites the previous row.
- `gmail_service.send_email` never raises — any failure is caught and returned as `{"status": "failed", "message": ...}`, since its only caller (`confirm_and_send`) depends on that exact shape.
- No new Activity Log event types for Gmail connect/disconnect — `activity_logs.event_type`'s `CheckConstraint` stays at exactly spec2.md §29's 11 values; `/api/gmail/*` routes never call `log_activity`.
- Settings page (`/settings`) is the one account-level, non-project-scoped page in the frontend.
- Real Gmail OAuth requires external, out-of-band setup (Google Cloud Console OAuth consent screen + a second Client ID separate from Supabase's Google login provider + Gmail API enabled) — see `.env.example`'s `GMAIL_*` block. Already completed; `EMAIL_MODE=gmail` is live in `.env`.

**RAG evaluation**
- Run as `docker compose exec backend python -m scripts.eval_rag <project_id>` — the `scripts/__init__.py` file and `-m` invocation are required, or `from app...` imports fail with `ModuleNotFoundError`.
- `embed_query` has no rate-limit throttling (Voyage account capped at 3 RPM); `eval_rag.py` adds a 25s delay + retry-with-backoff between fixture questions. **Do not `docker compose restart backend` while `eval_rag.py` is running inside it** — the restart kills the exec'd process (exit 137), losing all progress.

**Activity Log**
- `activity_service.log_activity` wraps its insert in `db.begin_nested()` (a SAVEPOINT) so a logging failure never aborts the caller's real transaction.
- `user_logged_in` events have `project_id=None` (login never touches the backend directly — `useSession.js` fires a fire-and-forget `GET /api/auth/me` on `SIGNED_IN` purely to trigger the log). `GET /activity` must `OR` in the requesting user's own `project_id IS NULL` rows alongside project-scoped ones.
- `event_type` is `CheckConstraint`-enforced to exactly spec2.md §29's 11 values — adding new event types means an Alembic migration.

## LLM / embedding providers

Unlike the earlier draft, `spec2.md` does **not** ask for a swappable multi-provider abstraction: Claude API is the fixed LLM/Vision provider, Voyage AI is the fixed embedding provider (§5–6, §41). Still isolate them behind `claude_service.py` / `embedding_service.py` so provider-specific details don't leak into `rag_service.py` or `agent_service.py` — but don't build a `LLM_PROVIDER=gemini|anthropic` switch; that abstraction was dropped in this spec version.

Claude handles reasoning/generation/vision; Voyage AI only does embeddings; pgvector only does similarity search. Don't blur these responsibilities (§6, §41).

## Email execution path

Two independent OAuth concerns, per rule #11 and `spec2.md` §26 — do not build one and assume it covers the other:

```
Supabase Auth (Google login, app identity)         ──unrelated to──►  Gmail OAuth (gmail.send scope, execution)
                                                                              │ authorize-url / callback / status / disconnect
                                                                              │ (app/api/gmail.py, app/services/gmail_service.py)
                                                                              ▼
                                                        MCP send_email() → Gmail API
```

`EMAIL_MODE=mock` (default — `app/mcp/tools/send_email.py` logs `[MOCK EMAIL] to=... subject=...`, never the body, and returns `status: "sent"`) and `EMAIL_MODE=gmail` (real send via the Gmail OAuth flow above) are both fully built and supported — this was never an either/or. `email_send` always goes through the MCP tool — never call Gmail API directly from an API route; `email_service.confirm_and_send` is the only caller of `mcp_client.call_tool("send_email", ...)`, itself only reachable from `POST /email/send`, itself only reachable from a user's explicit "Confirm & Send" click.

## Security minimums (spec2.md §32)

Validate uploaded file types and filenames; enforce upload size limits (PDF 100MB, image 10MB — carried over from `spec.md`, not restated numerically in `spec2.md` but still the working assumption); validate email addresses; never expose API keys, OAuth secrets, or the Supabase service role key in error messages or logs. `SUPABASE_SERVICE_ROLE_KEY` must only ever exist in the backend, never sent to the frontend.

## Commands

```bash
npx supabase start                                      # local Auth/Postgres/Storage fallback stack (only if .env points at it)
docker compose build
docker compose up -d                                     # frontend, backend, mcp-server
docker compose run --rm backend alembic upgrade head    # first run, or whenever a migration is added
docker compose logs -f
docker compose logs -f mcp-server                        # MCP server's own log stream
docker compose restart mcp-server                        # required after any edit under backend/app/mcp/ -- no hot-reload
docker compose exec backend python -m scripts.eval_rag <project_id>  # RAG retrieval accuracy (spec2.md §38) -- don't restart backend while this runs
docker compose down                                      # frontend/backend/mcp-server only; Supabase data untouched either way
npx supabase stop                                        # stop local Supabase fallback stack (keeps data)
```

- Frontend: http://localhost:5173
- Backend Swagger: http://localhost:8000/docs
- Health check: http://localhost:8000/api/health
- MCP server (internal only in production; host-published for local debugging): http://localhost:8001/mcp
- Supabase Studio (local stack only): http://localhost:54323
- Inbucket (local stack dev email catcher): http://localhost:54324

Backend tests require whatever `DATABASE_URL` in `.env` currently points at to be reachable (cloud project or local CLI stack): `docker compose exec backend python -m pytest -v`. Tests override `get_current_user` with fake users (`tests/conftest.py`) — they exercise our authorization/CRUD logic, not Supabase's token issuance — and wrap each test in a rolled-back SAVEPOINT against the real Postgres schema (UUID/JSONB/pgvector types don't work cleanly against SQLite, so this isn't mocked out).
