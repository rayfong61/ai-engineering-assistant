# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status

Day 1 (spec2.md §37) is implemented and verified end-to-end: Docker scaffold, Supabase Auth (Google + Email/Password), Project CRUD, membership-only authorization. `spec2.md` is the full specification and remains the source of truth; this file summarizes the parts most likely to be violated by default AI behavior, plus real implementation details that emerged during Day 1 and aren't in the spec (see "Implementation notes beyond the spec" below). Days 2–5 are not yet built — follow §36/§37 build order for those.

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

Local Docker runs `frontend`, `backend` (`mcp-server` joins in Day 3, §30) — no local Postgres container of our own, no ChromaDB, no local LLM. "Supabase Cloud" in the diagram above is, during development, actually the **local Supabase CLI stack** (`supabase start` — see "Implementation notes beyond the spec" below), not supabase.com; swapping to the real cloud project later is purely an env-var change. `docker compose down` losing state is a non-issue either way because nothing persistent lives in the `frontend`/`backend` containers themselves.

Actual structure (spec2.md §33, as built):

```
frontend/            React + Vite + Tailwind
  src/
    App.jsx, main.jsx, index.css
    pages/           Login.jsx (Google + Email/Password), Projects.jsx, ProjectDetail.jsx
    hooks/           useSession.js
    lib/             supabaseClient.js, api.js
backend/app/
  main.py
  api/               auth.py, projects.py   (documents/chat/vision/agent/email land Day 2-4)
  core/              config.py, database.py (SQLAlchemy engine/session),
                      auth.py (JWKS verification), authorization.py,
                      supabase_client.py (Storage/Auth-admin only, Day 2+)
  models/            SQLAlchemy ORM: project.py, document.py, conversation.py, email_log.py
  schemas/           project.py (Pydantic)
  alembic/           env.py, versions/0001_initial_schema.py
  alembic.ini
data/temp/
supabase/            config.toml (local CLI stack config, spec2.md doesn't mention this —
                     it's a Day-1 addition, see below)
docker-compose.yml   services: frontend, backend (postgres/auth/storage come from `supabase start`, not here)
```

## Data model (spec2.md §9)

Core tables: `projects`, `project_members` (role: owner/member), `documents` (status: uploaded/processing/ready/failed), `document_chunks` (page, chunk_index, embedding VECTOR(N)), `conversations`, `messages` (role: user/assistant/system/tool), `email_logs` (status: draft/confirmed/sent/failed/cancelled). Storage path convention: `projects/{project_id}/documents/{document_id}/{filename}` and `projects/{project_id}/images/{image_id}/{filename}` (§10).

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
POST /api/projects/{project_id}/agent
POST /api/projects/{project_id}/email/preview
POST /api/projects/{project_id}/email/send   -- must go through the MCP tool, never bypass MCP
GET  /api/health
```

Every project-scoped route must resolve `current_user` from the JWT and verify `project_members` before touching that project's rows.

## Implementation notes beyond the spec

These are Day 1 decisions/discoveries that aren't in `spec2.md` but should be treated as settled, not re-litigated:

1. **Table access is SQLAlchemy + Alembic, direct Postgres connection — not Supabase's Data API/PostgREST.** `spec2.md` says "Database: Supabase PostgreSQL" but doesn't mandate `supabase-py`'s `.table()` client. Since the frontend never queries tables directly (only `backend/app/core/database.py` does, via `DATABASE_URL`), routing through PostgREST added no value and only added attack surface — so Supabase's **"Enable Data API" setting is turned off**. `supabase_client.py` (the `supabase-py` client) is kept only for Storage (Day 2+) and any Auth-admin calls, never for table CRUD. Schema changes go through Alembic revisions (`backend/alembic/versions/`), applied identically to local and cloud via `alembic upgrade head` against whatever `DATABASE_URL` points at.

2. **User session tokens are verified via JWKS, not a shared HS256 secret.** Current Supabase (both the local CLI stack and, most likely, any newly-created cloud project) signs user JWTs with an asymmetric key (ES256), published at `<SUPABASE_URL>/auth/v1/.well-known/jwks.json`. `app/core/auth.py` uses `jwt.PyJWKClient` against that endpoint — there is no `SUPABASE_JWT_SECRET` env var. If a real cloud project ever turns out to still issue legacy HS256 tokens, this would need a fallback path, but don't add one speculatively — confirm first (decode a real token's header and check `alg`).

3. **Local development runs against the Supabase CLI (`supabase start`), not supabase.com**, because Supabase had a platform-side outage affecting project creation during Day 1. The CLI spins up a full local stack (Postgres, GoTrue Auth, Storage, Kong gateway, Studio, Inbucket for catching dev emails) — see `supabase/config.toml`. `docker-compose.yml` no longer runs its own `postgres` service; the `backend`/`frontend` containers reach the CLI stack via `host.docker.internal`. Moving to the real cloud project later is: create it, disable its Data API, copy its URL/keys into `.env`, re-run `alembic upgrade head` against it — no code changes.

4. **Email/Password login exists alongside Google login, for local dev convenience only.** `spec2.md`'s demo flow (§2, §39) is Google-login-only — don't remove the Google button or make Email/Password the primary flow in any user-facing copy. It's there because wiring real Google OAuth requires external setup (Google Cloud Console + Supabase provider config) that shouldn't block testing the rest of the stack; `supabase/config.toml` has `enable_confirmations = false` under `[auth.email]` so signup doesn't need a confirmation-email round trip locally.

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

Build the mock-mode path (`EMAIL_MODE=mock`, logs `[MOCK EMAIL]` instead of sending) before wiring real Gmail OAuth. `email_send` always goes through the MCP tool — never call Gmail API directly from an API route.

## Security minimums (spec2.md §32)

Validate uploaded file types and filenames; enforce upload size limits (PDF 100MB, image 10MB — carried over from `spec.md`, not restated numerically in `spec2.md` but still the working assumption); validate email addresses; never expose API keys, OAuth secrets, or the Supabase service role key in error messages or logs. `SUPABASE_SERVICE_ROLE_KEY` must only ever exist in the backend, never sent to the frontend.

## Commands

```bash
npx supabase start                                      # local Auth/Postgres/Storage stack (first run / after reboot)
docker compose build
docker compose up -d
docker compose run --rm backend alembic upgrade head    # first run, or whenever a migration is added
docker compose logs -f
docker compose down                                      # frontend/backend only; local Supabase data untouched
npx supabase stop                                        # stop local Supabase (keeps data)
```

- Frontend: http://localhost:5173
- Backend Swagger: http://localhost:8000/docs
- Health check: http://localhost:8000/api/health
- Supabase Studio (local): http://localhost:54323
- Inbucket (local dev email catcher): http://localhost:54324

Backend tests (require the local Supabase Postgres reachable — `npx supabase start` first): `docker compose exec backend python -m pytest -v`. Tests override `get_current_user` with fake users (`tests/conftest.py`) — they exercise our authorization/CRUD logic, not Supabase's token issuance — and wrap each test in a rolled-back SAVEPOINT against the real Postgres schema (UUID/JSONB/pgvector types don't work cleanly against SQLite, so this isn't mocked out).
