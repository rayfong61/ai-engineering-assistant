# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status

This repository currently contains only `spec2.md` — no code has been written yet (no `frontend/`, `backend/`, `docker-compose.yml`, `README.md`, or git history). `spec2.md` is the full specification and is the source of truth; this file summarizes the parts most likely to be violated by default AI behavior. When implementation starts, follow the three-day plan in `spec2.md` §37 and the build priority in §36 exactly, and update this file (commands, architecture) as real code lands.

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

Local Docker only runs `frontend`, `backend`, `mcp-server` (§30) — no local Postgres, no ChromaDB, no local LLM. All data/state lives in Supabase; `docker compose down` losing local state is a non-issue because nothing persistent is stored locally.

Planned structure (spec2.md §33):

```
frontend/            React + Vite + Tailwind (components/, pages/, hooks/, services/, types/, App.jsx)
backend/app/
  main.py
  api/               auth.py, projects.py, documents.py, chat.py, vision.py, agent.py, email.py
  services/          supabase_service.py, storage_service.py, pdf_service.py,
                      embedding_service.py, rag_service.py, claude_service.py,
                      vision_service.py, gmail_service.py
  agent/agent_service.py
  mcp/server.py, mcp/tools/search_documents.py, mcp/tools/send_email.py
  models/, schemas/, core/
data/temp/
docker-compose.yml   services: frontend, backend, mcp-server
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

No build tooling exists yet. Once implemented per `spec2.md` §30, the documented Docker workflow will be:

```bash
docker compose build
docker compose up -d
docker compose logs -f
docker compose down
docker compose restart
```

Backend Swagger docs will be served at `/docs`. Update this section with actual test-runner commands (pytest, npm test, etc.) once `backend/` and `frontend/` exist.
