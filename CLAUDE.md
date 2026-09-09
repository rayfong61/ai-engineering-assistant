# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status

P0 → P1 → P2 are all implemented and verified end-to-end against the real cloud Supabase project, real Voyage/Claude APIs, and real Gmail (`EMAIL_MODE=gmail` is live in `.env`; `EMAIL_MODE=mock` remains the default and a fully supported fallback). `spec2.md` is the full specification and remains the source of truth; this file summarizes the parts most likely to be violated by default AI behavior, plus standing implementation decisions not in the spec. Full day-by-day build history, bug discoveries, and verification narratives live in `docs/CHANGELOG.md` (gitignored, not part of the shared repo) — this file keeps only current, still-applicable rules.

**Deviation from spec2.md:** §4/§21/§30/§33 specify a separate MCP server process/protocol for tool calls. This was built as specified (Day 3), then removed entirely (not just collapsed to in-process) once it became clear `mcp-server` and `backend` share one repo, one compose file, one deploy, one maintainer, and MCP never had a second consumer — the cross-boundary problem MCP protocol solves never applied here, and keeping an unused protocol layer around was actively confusing to read, not just unnecessary. The four tools (`search_documents`, `get_site_weather`, `check_site_location`, `send_email`) are now plain Python functions in `app/tools/`, called directly like any other in-repo function. See "Standing decisions & known gotchas → Tools" below.

**Deviation from this file's own rule #2:** Rule #2 above excludes Calendar/Slack/Teams integration as V2/V3 scope. Calendar was added anyway, as a deliberate, user-approved exception — the value is the same human-in-the-loop draft→confirm pattern already proven for email (rule #4), extended to a second Google product the user already has an OAuth grant for, not a new integration surface. Concretely: reuses the *same* Gmail OAuth client/grant/refresh-token store (`gmail_credentials`), with one additional scope (`calendar.events`) added to the existing authorize request — no new OAuth flow, no new credential table, no third-party MCP server. See "Standing decisions & known gotchas → Calendar" below for the full design. Rule #2 otherwise still stands — Slack/Teams/BIM/IFC/LangChain remain excluded; this is not a precedent for adding those without the same explicit approval.

`spec.md` is a superseded earlier draft (local-Docker-only, no auth, no multi-tenancy, ChromaDB) kept for history — do not follow it. `spec2.md` replaces it with a Supabase-backed, multi-tenant architecture.

## What this project is

A Project-scoped, multi-user AI Engineering Assistant, using 桃園國際機場第三航廈 (Taoyuan Airport Terminal 3) public engineering PDFs as demo data. The point is not a chatbot — it's a full pipeline:

```
Google Login → Project → Engineering Documents → RAG → Claude → Vision → Agent → Gmail
```

Demo flow: Google login → create project → upload PDF → RAG-index it (Voyage AI embeddings → pgvector) → ask questions in natural language → answer with source doc + page → upload an engineering image → Claude Vision analyzes it → Agent combines RAG + Vision into a meeting summary → user asks to email it → Agent drafts email → UI shows preview → user clicks Confirm Send → `send_email` tool → Gmail API.

## Non-negotiable rules (spec2.md §32–33, §41)

1. Do not over-engineer; prefer simple Python functions over frameworks.
2. Do not introduce LangChain/LangGraph/multi-agent, BIM/IFC, or Calendar/Slack/Teams integration — these are explicit V2/V3 future extensions (§42), not MVP scope. (Calendar was granted a deliberate, approved exception — see "Deviation from this file's own rule #2" above; Slack/Teams remain excluded.)
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
- **P1**: Claude Vision, Agent, MCP (later fully removed — see "Deviation from spec2.md" above), Email Draft generation, Human confirmation, Mock Email (`EMAIL_MODE=mock`).
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
                    ▼                     ▼                     ▼
        ┌───────────────────────────────────────────────────────────┐
        │                      Supabase Cloud                        │
        │   Supabase Auth  │  PostgreSQL + pgvector  │  Storage       │
        └───────────────────────────────────────────────────────────┘
                    ▲
                    │
          Voyage AI (embeddings)  /  Claude API (LLM, Vision, Agent reasoning)

Agent → send_email tool → Gmail API
```

Local Docker runs exactly two containers: `frontend` and `backend`. There is no separate MCP server process — see the "Deviation from spec2.md" note above and "Standing decisions → Tools" below for why. No local Postgres container of our own, no ChromaDB, no local LLM.

`.env` currently points `SUPABASE_URL`/`DATABASE_URL` at the real cloud project (`*.supabase.co`, via the Session Pooler — see "Standing decisions" below). `npx supabase start` still works as a local CLI fallback stack, but check `.env` before assuming which one is live. `docker compose down` losing state is a non-issue either way because nothing persistent lives in the `frontend`/`backend` containers themselves.

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
                      EmailPreviewCard.jsx / CalendarEventPreviewCard.jsx (both rendered
                      inline inside AgentPanel -- no Email or Calendar tab),
                      ActivityPanel.jsx
    hooks/           useSession.js
    lib/             supabaseClient.js, api.js
backend/app/
  main.py
  api/               auth.py, projects.py, documents.py, chat.py, vision.py, agent.py, email.py,
                      activity.py, gmail.py (authorize-url/callback/status/disconnect,
                      account-level, not project-scoped), calendar_events.py (single
                      POST .../calendar-events/create route -- see "Standing decisions
                      -> Calendar" below for why there's no preview route)
  core/              config.py, database.py (SQLAlchemy engine/session),
                      auth.py (JWKS verification), authorization.py,
                      supabase_client.py (Storage/Auth-admin only)
  models/            SQLAlchemy ORM: project.py, document.py, conversation.py, email_log.py, vision.py,
                      activity_log.py, gmail_credential.py, calendar_event_log.py
  schemas/           project.py, document.py (Pydantic; Document/Chat/Conversation/Message),
                      vision.py, agent.py, email.py, activity.py, calendar_event.py
  services/          pdf_service.py (extract/chunk), embedding_service.py (Voyage),
                      claude_service.py (RAG + Vision + summary + email draft generation),
                      rag_service.py (ingest/retrieve orchestration), vision_service.py,
                      email_service.py (save_draft/generate_preview/confirm_and_send),
                      activity_service.py (log_activity helper),
                      gmail_service.py (OAuth code exchange/refresh/send, raw httpx
                      against Google's endpoints, no google-api-python-client),
                      calendar_service.py (Calendar API v3 create_event, raw httpx,
                      reuses gmail_service's OAuth helpers/credential -- see "Standing
                      decisions -> Calendar" below), calendar_event_service.py
                      (save_draft/confirm_and_create, mirrors email_service.py),
                      web_fetch_service.py (real MCP client -- see "Standing decisions
                      -> Tools" below; the one service in this list that talks to a
                      genuine external MCP server instead of a plain REST API)
  agent/             agent_service.py (process_request/select_tools/execute_workflow,
                     hand-rolled Claude tool-use loop, no framework)
  tools/             search_documents.py, weather.py (get_site_weather), geo.py
                     (check_site_location), send_email.py -- plain Python functions,
                     each a `run(...)` -- imported and called directly by
                     agent_service.py (the first three)/email_service.py (send_email).
                     No protocol, no server process, no separate client module -- see
                     "Deviation from spec2.md" above. fetch_url.py is one exception:
                     still a plain `run(...)` at the call site, but internally a real
                     MCP client against a third-party MCP server -- see "Standing
                     decisions -> Tools" below. create_calendar_event.py mirrors
                     send_email.py's mode-branching shape exactly, called by
                     calendar_event_service.confirm_and_create.
  alembic/           env.py, versions/0001_initial_schema.py .. 0006_calendar_event_logs.py
  alembic.ini
backend/scripts/     eval_rag.py + rag_eval_fixture.json (spec2.md §38 -- standalone, not pytest;
                     mounted into the backend container via its own docker-compose.yml volume line)
data/temp/
data/samples/        gitignored -- sample T3 PDFs used for local extraction/RAG testing, not committed
supabase/            config.toml (local CLI stack config, not mentioned in spec2.md)
docker-compose.yml   services: frontend, backend (only two -- postgres/auth/storage come from
                     Supabase -- local CLI stack or cloud project depending on .env, not a
                     container here)
```

## Data model (spec2.md §9)

Core tables: `projects`, `project_members` (role: owner/member), `documents` (status: uploaded/processing/ready/failed), `document_chunks` (page, chunk_index, embedding VECTOR(N)), `conversations`, `messages` (role: user/assistant/system/tool), `email_logs` (status: draft/confirmed/sent/failed/cancelled). Storage path convention: `projects/{project_id}/documents/{document_id}/{filename}` and `projects/{project_id}/images/{image_id}/{filename}` (§10).

`vision_analyses` (not in spec2.md §9 -- the spec never defines a table for Vision results, only the §17 response shape `{analysis, observations, limitations}`): `id`, `project_id`, `uploaded_by`, `filename`, `storage_path`, `file_size`, `analysis` (text), `observations`/`limitations` (JSONB arrays), `created_at`. Named for the analysis row, not the raw image (which lives only in Storage) -- same split as `documents` vs `document_chunks`.

`activity_logs` (backing spec2.md §29's Activity Log): `id`, `project_id` (nullable -- `NULL` only for the `user_logged_in` event, which has no project context), `user_id`, `event_type` (`CheckConstraint`-enforced to 14 values -- spec2.md §29's original 11-value workflow chain plus 3 calendar event types added in migration 0006), `detail` (free text -- recipient/filename/attendee-emails only, never email body/subject/event summary/description or API keys), `created_at`.

`gmail_credentials` (not in spec2.md §9): `user_id` (primary key, bare Supabase UUID, no FK -- same no-local-users-table pattern as `project_members.user_id`), `gmail_email` (nullable, best-effort), `encrypted_refresh_token` (Fernet ciphertext, never plaintext), `created_at`/`updated_at`. One row per user -- connecting again overwrites the prior credential. Deliberately **not** logged in `activity_logs` (connect/disconnect aren't part of spec2.md §29's 11-value event chain). Also backs Calendar event creation, not just Gmail send -- see "Standing decisions → Calendar" below.

`calendar_event_logs` (not in spec2.md §9 -- mirrors `email_logs`): `id`, `project_id` (nullable, FK->projects.id ON DELETE SET NULL), `user_id`, `summary`, `description`, `start_datetime`/`end_datetime` (DateTime timezone=True), `attendees` (JSONB array of email strings), `status` (CheckConstraint: draft/confirmed/created/failed/cancelled -- same shape as `email_logs.status`, "created" standing in for "sent"), `google_event_id` (nullable, populated only after a successful real Calendar API call), `created_at`.

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
POST /api/projects/{project_id}/email/send     -- must go through the send_email tool function, never call Gmail API directly
POST /api/projects/{project_id}/calendar-events/create -- must go through the create_calendar_event tool function, never call Google Calendar API directly
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
- Every route file wraps Voyage/Claude/external-tool failures in `HTTPException(502, "...")` with a Chinese message — `chat.py`, `agent.py` included.

**Tools**
- `app/tools/{search_documents,weather,geo,send_email}.py` are the only implementations of these four tools — no protocol layer, no server process, no dispatch/lookup table. `agent_service.py`'s `execute_workflow` imports `app.tools.{search_documents,weather,geo}` and calls `.run(...)` directly in each `if/elif` branch; `email_service.confirm_and_send` imports `app.tools.send_email` and calls `.run(...)` directly. Both are indistinguishable from any other in-repo function call.
- This project built and then fully removed an MCP (Model Context Protocol) server for these same tools (spec2.md §4/§21/§30/§33 called for one) — see "Deviation from spec2.md" at the top of this file. Don't re-introduce a protocol/server/dispatch layer for these tools without a real second consumer (something other than this backend) to justify it; if that ever happens, treat it as a new integration to design, not a revival of the deleted code.
- Since tool code now lives under `backend/app/`, it's covered by the backend's `uvicorn --reload` like everything else — no separate restart needed for edits there.
- `send_email.run(...)` requires a `user_id` argument — Gmail mode needs to know whose credential to use, and this function has no session/JWT context of its own.
- `fetch_web_page` (`app/tools/fetch_url.py` → `app/services/web_fetch_service.py`) is the one deliberate exception to "no protocol layer": it's a real MCP **client** talking to a genuine third-party MCP **server** — `mcp-server-fetch`, the official `modelcontextprotocol/servers` reference "fetch" implementation, maintained by a different project than this repo, spawned as a subprocess per call and driven over real stdio JSON-RPC (`mcp` + `mcp-server-fetch` packages in `requirements.txt`). This is the "new integration to design" case the bullet above anticipates, not a revival of the deleted internal MCP server — the earlier removal was specifically about protocol overhead with no second party on the other end (this backend was both the only client and the only server), and here there genuinely is one. Returns web content, not project documents — `AGENT_SYSTEM_PROMPT` requires the Agent to label it as external and never conflate it with `search_documents` results. `web_fetch_service._call_fetch_tool` is async (the `mcp` SDK is asyncio-based); the wrapping `fetch_url.run(...)` is sync (`asyncio.run(...)` + a 20s timeout) to match every other tool's plain-function signature and because `POST /agent` is a sync FastAPI route (no running event loop to conflict with).

**Agent**
- The Agent's email tool is `draft_email`, not `send_email` — it only ever persists an `EmailLog(status="draft")` via `email_service.save_draft` and **never calls `app.tools.send_email`**. `tests/test_agent.py` pins this human-in-the-loop boundary.
- `analyze_image` looks up an already-persisted `vision_analyses` row (no image bytes in `/agent` requests, so nothing to re-analyze). Validate `image_id` as a UUID before querying it — a non-UUID string (e.g. a pasted filename) must return `{"error": ...}`, not crash the request with an unhandled Postgres type error.
- A request to revise/reschedule/adjust an already-generated draft (email OR calendar event) must trigger a fresh `draft_email`/`create_calendar_event` tool call — `AGENT_SYSTEM_PROMPT_TEMPLATE` explicitly requires this, because the Agent only replays plain-text history across turns (no structural memory of prior tool calls) and could otherwise narrate a fabricated "revised" draft with no real tool call behind it.
- The Agent's calendar tool is `create_calendar_event`, mirroring `draft_email`'s human-in-the-loop boundary exactly — see "Standing decisions → Calendar" below.
- `execute_workflow` must catch its own `ValueError` (e.g. bad email format from `save_draft`) and return `{"error": ...}` as the tool's output — never let it propagate, since `app/api/agent.py`'s `except ValueError` is reserved for "conversation not found" and would mislabel the error.

**Email / Gmail**
- `draft_email` (Agent tool) and `POST /email/preview` both converge on `email_service.save_draft` as the single persistence point — no duplicated logic between the two trigger paths.
- `confirm_and_send` takes the confirming user's `user_id` (not necessarily whoever drafted the email) so `email_sent`/`user_confirmed_email` activity events attribute correctly.
- No Google client libraries — `gmail_service.py` makes three raw `httpx` calls (auth-code exchange, refresh-token exchange, send) directly against Google's endpoints.
- No access-token caching — every send re-exchanges the encrypted refresh token (Fernet, `GMAIL_TOKEN_ENCRYPTION_KEY`) for an access token immediately before sending.
- `GET /api/gmail/callback` has no JWT/`get_current_user` dependency (Google's redirect is a top-level browser navigation with no Authorization header) — identity comes from a short-lived (5 min) signed `state` JWT, signed with `GMAIL_CLIENT_SECRET`.
- The Gmail OAuth authorize URL requests `gmail.send email` (not `gmail.send` alone) — a connected Google account can differ from the Supabase-login one, so the login email can't stand in for it. `gmail_email` is populated by calling the standard `https://www.googleapis.com/oauth2/v2/userinfo` endpoint (authorized by the `email` scope) right after the token exchange in `handle_callback`, never the Gmail API's own `users.getProfile` endpoint — that one needs `gmail.readonly`/`gmail.modify`/`gmail.metadata`, which would be a much bigger scope than this cosmetic field is worth. Still best-effort/nullable (`gmail_email` stays `NULL` on a userinfo-call failure, and for any credential connected before this scope change until the user reconnects) — a failure here must never block storing the refresh token itself.
- One Gmail account per user (`gmail_credentials.user_id` is the primary key) — reconnecting overwrites the previous row.
- `gmail_service.send_email` never raises — any failure is caught and returned as `{"status": "failed", "message": ...}`, since its only caller (`confirm_and_send`) depends on that exact shape.
- No new Activity Log event types for Gmail connect/disconnect — `/api/gmail/*` routes never call `log_activity` (unlike Calendar, which added 3 values for its own draft/confirm/create workflow — see "Standing decisions → Calendar" below).
- Settings page (`/settings`) is the one account-level, non-project-scoped page in the frontend.
- Real Gmail OAuth requires external, out-of-band setup (Google Cloud Console OAuth consent screen + a second Client ID separate from Supabase's Google login provider + Gmail API enabled) — see `.env.example`'s `GMAIL_*` block. Already completed; `EMAIL_MODE=gmail` is live in `.env`.

**Calendar**
- Reuses the *same* Gmail OAuth grant, not a separate flow -- `GMAIL_OAUTH_SCOPES` (`gmail_service.py`) now requests `gmail.send calendar.events email`. One Google Cloud OAuth client, one `gmail_credentials` row per user, one Fernet-encrypted refresh token, reused by both `gmail_service.send_email` and `calendar_service.create_event`.
- Any user who connected before this scope change must reconnect (Settings → 中斷連接 → 連接 Google 帳號) to actually be granted `calendar.events` -- Google does not retroactively add scope to an existing refresh token, and this backend does not detect or warn about this proactively (documented limitation, not a bug): a stale-scope credential's first `create_calendar_event` confirm just fails with whatever error Google's API returns, surfaced as the standard `{"status": "failed", ...}` shape.
- `calendar_service.py` imports `gmail_service._decrypt`/`gmail_service._refresh_access_token` directly (underscore-prefixed) -- deliberate, not an accidental leak: shared by two services on purpose. Don't "fix" this by making them public without a real reason; don't duplicate them either.
- `CALENDAR_MODE` (default `mock`, alternative `google_calendar`) mirrors `EMAIL_MODE` exactly -- same two-mode shape, same "never raises" contract.
- `calendar_service.create_event` always passes `sendUpdates=all` on the `POST .../events` call -- without it, the Calendar API's default (`none`) silently adds attendees to the event with no invite email ever sent, which looks like success (event exists, attendee listed) but isn't a real notification. Discovered live: an event created without this param showed up correctly on Google Calendar with the attendee listed as "還沒回覆" but no email ever arrived.
- Enabling `CALENDAR_MODE=google_calendar` requires the Calendar API to actually be enabled on the Google Cloud project backing `GMAIL_CLIENT_ID` (APIs & Services → Library → Google Calendar API → Enable) -- a disabled-but-correctly-scoped credential fails with a 403 `accessNotConfigured`/`SERVICE_DISABLED` error, which looks identical to an insufficient-scope 403 in the generic `{"status": "failed", ...}` shape; don't assume "reconnect" fixes a 403 without checking which cause it actually is (verify via a direct call, or check the API's enabled status in Console).
- The Agent's calendar tool is `create_calendar_event`, not a direct Calendar API call -- it only ever persists a `CalendarEventLog(status="draft")` via `calendar_event_service.save_draft` and never calls `app.tools.create_calendar_event`. Mirrors `draft_email`'s human-in-the-loop boundary exactly.
- There is no `POST .../calendar-events/preview` HTTP endpoint -- deliberate, mirroring that email's own `/email/preview` is confirmed unused by the frontend. Only `POST .../calendar-events/create` (the Confirm & Create action) exists.
- `agent_service.select_tools` renders the system prompt per-call via `_build_system_prompt()`, appending the current real date/time (`Asia/Taipei`, via `zoneinfo`) so Claude can resolve relative date expressions ("下週三", "明天下午") against a real anchor -- no earlier tool needed this; `AGENT_SYSTEM_PROMPT` is no longer a static string, `AGENT_SYSTEM_PROMPT_TEMPLATE` is.
- Activity events: `calendar_event_draft_generated` (`save_draft`), `user_confirmed_calendar_event` (`confirm_and_create`, before the real API call), `calendar_event_created` (`confirm_and_create`, only on success). `detail` logs attendee emails only, never `summary`/`description`.
- No `calendar_connected`/`calendar_disconnected` activity events -- same reasoning as Gmail connect/disconnect.

**RAG evaluation**
- Run as `docker compose exec backend python -m scripts.eval_rag <project_id>` — the `scripts/__init__.py` file and `-m` invocation are required, or `from app...` imports fail with `ModuleNotFoundError`.
- `embed_query` has no rate-limit throttling (Voyage account capped at 3 RPM); `eval_rag.py` adds a 25s delay + retry-with-backoff between fixture questions. **Do not `docker compose restart backend` while `eval_rag.py` is running inside it** — the restart kills the exec'd process (exit 137), losing all progress.

**Activity Log**
- `activity_service.log_activity` wraps its insert in `db.begin_nested()` (a SAVEPOINT) so a logging failure never aborts the caller's real transaction.
- `user_logged_in` events have `project_id=None` (login never touches the backend directly — `useSession.js` fires a fire-and-forget `GET /api/auth/me` on `SIGNED_IN` purely to trigger the log). `GET /activity` must `OR` in the requesting user's own `project_id IS NULL` rows alongside project-scoped ones.
- `event_type` is `CheckConstraint`-enforced to exactly 14 values (spec2.md §29's original 11 plus 3 calendar event types added in migration 0006) — adding new event types means an Alembic migration.

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
                                                        send_email.run() → Gmail API
```

`EMAIL_MODE=mock` (default — `app/tools/send_email.py` logs `[MOCK EMAIL] to=... subject=...`, never the body, and returns `status: "sent"`) and `EMAIL_MODE=gmail` (real send via the Gmail OAuth flow above) are both fully built and supported — this was never an either/or. `email_send` always goes through this one `send_email` tool function (`app/tools/send_email.py`) — never call Gmail API directly from an API route. `email_service.confirm_and_send` is the only caller, calling it directly in-process; itself only reachable from `POST /email/send`, itself only reachable from a user's explicit "Confirm & Send" click.

## Security minimums (spec2.md §32)

Validate uploaded file types and filenames; enforce upload size limits (PDF 100MB, image 10MB — carried over from `spec.md`, not restated numerically in `spec2.md` but still the working assumption); validate email addresses; never expose API keys, OAuth secrets, or the Supabase service role key in error messages or logs. `SUPABASE_SERVICE_ROLE_KEY` must only ever exist in the backend, never sent to the frontend.

## Commands

```bash
npx supabase start                                      # local Auth/Postgres/Storage fallback stack (only if .env points at it)
docker compose build
docker compose up -d                                     # frontend, backend -- that's the whole stack
docker compose run --rm backend alembic upgrade head    # first run, or whenever a migration is added
docker compose logs -f
docker compose exec backend python -m scripts.eval_rag <project_id>  # RAG retrieval accuracy (spec2.md §38) -- don't restart backend while this runs
docker compose down                                      # frontend/backend; Supabase data untouched either way
npx supabase stop                                        # stop local Supabase fallback stack (keeps data)
```

- Frontend: http://localhost:5173
- Backend Swagger: http://localhost:8000/docs
- Health check: http://localhost:8000/api/health
- Supabase Studio (local stack only): http://localhost:54323
- Inbucket (local stack dev email catcher): http://localhost:54324

Backend tests require whatever `DATABASE_URL` in `.env` currently points at to be reachable (cloud project or local CLI stack): `docker compose exec backend python -m pytest -v`. Tests override `get_current_user` with fake users (`tests/conftest.py`) — they exercise our authorization/CRUD logic, not Supabase's token issuance — and wrap each test in a rolled-back SAVEPOINT against the real Postgres schema (UUID/JSONB/pgvector types don't work cleanly against SQLite, so this isn't mocked out).
