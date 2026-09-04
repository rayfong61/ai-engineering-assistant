# AI Engineering Assistant — Local Docker MVP Specification

## 1. Project Overview

建立一個本地 Docker 部署的 AI Engineering Assistant，主要以「桃園國際機場第三航廈公開工程文件」作為 Demo 資料來源。

系統目標不是建立完整企業級工程平台，而是用最小可行產品展示：

> Engineering Documents → RAG → LLM → Vision → Agent → MCP → Gmail

核心 Demo：

1. 使用者上傳 PDF
2. 系統解析 PDF 並建立 RAG Knowledge Base
3. 使用者自然語言詢問工程內容
4. AI 回答並提供來源文件與頁碼
5. 使用者上傳工程圖片
6. Vision 分析工程圖片
7. Agent 將 RAG + Vision 結果整理成會議摘要
8. 使用者要求寄 Email
9. Agent 呼叫 MCP `send_email`
10. UI 顯示 Email Preview
11. 使用者確認後才真正寄出

---

# 2. MVP Scope

## 必做

### Frontend

* React
* Tailwind CSS
* Chat UI
* PDF Upload
* Image Upload
* RAG Answer
* Source / Page 顯示
* Vision Analysis
* Email Preview
* Confirm Send

### Backend

* Python
* FastAPI
* PDF parsing
* Text chunking
* Embedding
* ChromaDB
* LLM API
* Vision API
* Agent workflow
* MCP Server
* Gmail API

### Infrastructure

* Docker
* Docker Compose
* Local persistent volumes

---

# 3. Explicitly Out of Scope

MVP 不實作：

* Kubernetes
* Cloud Run
* AWS
* GCP Storage
* PostgreSQL
* Redis
* Celery
* 完整企業權限系統
* 多租戶
* BIM Viewer
* IFC parser
* 完整 OCR pipeline
* 複雜 LangChain / LangGraph architecture
* 多 Agent
* Calendar integration
* Slack integration
* Teams integration
* 自動爬取政府網站
* 自動判斷施工品質
* 結構安全判定

如果某功能不是 Demo 必要功能，不要自行加入。

---

# 4. Recommended Architecture

```text
                    Browser
                       │
                       ▼
             React + Tailwind
                       │
                  REST API
                       │
                       ▼
                FastAPI Backend
                       │
        ┌──────────────┼──────────────┐
        │              │              │
        ▼              ▼              ▼
   Document        RAG Service    Agent Service
   Processing           │              │
        │               ▼              ▼
        │           ChromaDB         LLM API
        │                              │
        ▼                              ▼
   PDF / Image                      MCP Client
                                       │
                                       ▼
                                  MCP Server
                                       │
                                       ▼
                                   Gmail API
```

---

# 5. Docker Architecture

Use Docker Compose.

Initial services:

```yaml
services:
  frontend:
    React + Vite

  backend:
    FastAPI

  chromadb:
    ChromaDB

  mcp-server:
    Python MCP Server
```

For MVP, MCP Server may optionally be integrated into the backend process if separating it creates unnecessary complexity.

Prefer the simplest architecture that clearly demonstrates MCP.

---

# 6. Project Structure

Create:

```text
ai-engineering-assistant/
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── services/
│   │   └── App.jsx
│   ├── Dockerfile
│   └── package.json
│
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   │
│   │   ├── api/
│   │   │   ├── documents.py
│   │   │   ├── chat.py
│   │   │   ├── vision.py
│   │   │   └── agent.py
│   │   │
│   │   ├── services/
│   │   │   ├── pdf_service.py
│   │   │   ├── rag_service.py
│   │   │   ├── embedding_service.py
│   │   │   ├── llm_service.py
│   │   │   ├── vision_service.py
│   │   │   └── email_service.py
│   │   │
│   │   ├── agent/
│   │   │   └── agent_service.py
│   │   │
│   │   ├── mcp/
│   │   │   └── server.py
│   │   │
│   │   └── models/
│   │
│   ├── tests/
│   ├── requirements.txt
│   └── Dockerfile
│
├── data/
│   ├── documents/
│   ├── images/
│   └── processed/
│
├── docker-compose.yml
├── .env.example
├── .gitignore
└── README.md
```

---

# 7. Environment Variables

Create `.env.example`.

Expected configuration:

```env
LLM_PROVIDER=gemini

GEMINI_API_KEY=
ANTHROPIC_API_KEY=

EMBEDDING_API_KEY=

GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=

GMAIL_USER=
```

Do NOT commit real API keys.

Use `.env` locally.

---

# 8. PDF Processing

Implement:

```text
POST /api/documents/upload
```

Input:

* PDF file

Process:

```text
PDF
 ↓
Extract text
 ↓
Page separation
 ↓
Clean text
 ↓
Chunk
 ↓
Generate embeddings
 ↓
Store in ChromaDB
```

Each chunk must preserve metadata:

```json
{
  "document_name": "example.pdf",
  "page": 12,
  "chunk_id": "example_12_03"
}
```

The page number is critical because the UI must show source information.

---

# 9. Chunking

Start with simple chunking.

Recommended:

* chunk size: approximately 500–1000 tokens
* overlap: approximately 100–150 tokens

Do not over-engineer chunking.

The implementation should make chunk size configurable.

---

# 10. RAG

Implement:

```text
POST /api/chat
```

Request:

```json
{
  "message": "第三航廈有哪些主要工程內容？"
}
```

Process:

```text
User Question
      ↓
Embedding
      ↓
ChromaDB similarity search
      ↓
Top K chunks
      ↓
LLM
      ↓
Answer + Sources
```

Start with:

```text
top_k = 5
```

Make it configurable.

---

# 11. RAG Response Format

Backend should return:

```json
{
  "answer": "......",
  "sources": [
    {
      "document": "T3_document.pdf",
      "page": 12,
      "content": "......"
    }
  ]
}
```

Frontend should display:

```text
AI Answer

[Source]
T3_document.pdf
Page 12
```

---

# 12. RAG Prompt Requirements

The LLM must be instructed:

1. Answer based only on retrieved context.
2. Do not invent engineering facts.
3. If the retrieved information is insufficient, say:
   "目前提供的工程文件中沒有足夠資訊回答此問題。"
4. Always cite source document and page when possible.
5. Clearly distinguish document facts from AI-generated summaries.

This is important because the system is intended for engineering applications.

---

# 13. Vision

Implement:

```text
POST /api/vision/analyze
```

Input:

* JPG
* PNG
* WEBP

Process:

```text
Image
 ↓
Vision LLM
 ↓
Description / OCR / visible engineering information
 ↓
Structured result
```

Return:

```json
{
  "analysis": "......",
  "observations": [
    "......",
    "......"
  ],
  "limitations": [
    "無法僅由圖片判斷結構安全性",
    "無法確認施工是否符合規範"
  ]
}
```

Vision should describe visible information.

It must NOT claim:

* structural safety
* construction quality compliance
* legal compliance
* engineering approval

unless explicit evidence exists.

---

# 14. Agent

Create an Agent Service.

The Agent's responsibility:

> Decide whether it needs RAG, Vision, or external tools to complete the user's task.

For MVP, support these capabilities:

```text
search_documents
analyze_image
send_email
```

Example:

User:

```text
請把剛才第三航廈的工程資訊整理成明天會議用摘要
```

Agent:

```text
1. Search documents
2. Retrieve relevant information
3. Generate meeting summary
```

---

# 15. MCP

Implement a Python MCP Server.

MCP tools:

### Tool 1

```text
search_documents(query)
```

Purpose:

Search engineering knowledge base.

### Tool 2

```text
send_email(to, subject, body)
```

Purpose:

Send email using Gmail API.

Do not implement additional MCP tools unless necessary.

---

# 16. MCP Email Workflow

Critical requirement:

AI must NOT automatically send email.

Workflow:

```text
User:
請把剛才的摘要寄給 PM

        ↓

Agent

        ↓

Generate Email Draft

        ↓

Frontend Email Preview

        ↓

User clicks "Confirm Send"

        ↓

MCP send_email()

        ↓

Gmail API

        ↓

Success
```

---

# 17. Email Preview

Frontend must display:

```text
Email Preview

To:
pm@example.com

Subject:
桃園機場第三航廈工程會議摘要

Body:
......

[Cancel]
[Confirm Send]
```

Only after `Confirm Send` should the backend execute:

```text
MCP → send_email()
```

This demonstrates Human-in-the-Loop.

---

# 18. Gmail Integration

Use Gmail API.

OAuth should be implemented only if time permits.

For MVP development:

Phase 1:

* Build email service abstraction
* Allow mock email sending

Phase 2:

* Google OAuth
* Gmail API

Do not allow credentials or access tokens to be hard-coded.

Architecture:

```text
Google OAuth
      ↓
Authorization
      ↓
Gmail API
      ↑
MCP send_email()
```

Important distinction:

```text
OAuth = authentication / authorization

MCP = tool integration layer

Gmail API = actual email execution
```

---

# 19. Frontend UI

Create a simple professional engineering dashboard.

Layout:

```text
┌──────────────────────────────────────────────┐
│ AI Engineering Assistant                    │
├───────────────┬──────────────────────────────┤
│ Documents     │                              │
│               │ Chat                         │
│ Upload PDF    │                              │
│               │ User: ...                    │
│ Documents     │                              │
│ - T3.pdf      │ AI: ...                      │
│               │                              │
│               │ Sources                      │
│               │ T3.pdf - Page 12             │
│               │                              │
│               │ [Ask]                       │
└───────────────┴──────────────────────────────┘
```

Add Image Analysis section:

```text
Upload Engineering Image

[Upload]

Vision Analysis:
...
```

Email section:

```text
Generate Email
      ↓
Email Preview
      ↓
Confirm Send
```

Keep UI simple.

Do not spend excessive time on visual design.

---

# 20. API Endpoints

Implement:

```text
GET  /api/health

POST /api/documents/upload

GET  /api/documents

POST /api/chat

POST /api/vision/analyze

POST /api/agent

POST /api/email/preview

POST /api/email/send
```

The `/api/email/send` endpoint must execute the MCP email tool rather than bypassing MCP.

---

# 21. Example Complete Demo

The final MVP must support this scenario.

### Step 1

User uploads:

```text
T3工程文件.pdf
```

### Step 2

Backend:

```text
PDF
→ text extraction
→ chunking
→ embedding
→ ChromaDB
```

### Step 3

User asks:

```text
第三航廈有哪些主要工程內容？
```

### Step 4

RAG:

```text
Question
→ vector search
→ relevant chunks
→ LLM
→ answer
```

UI:

```text
主要工程內容包括......

Sources:
T3工程文件.pdf
Page 15
Page 27
```

### Step 5

User uploads:

```text
engineering-plan.jpg
```

### Step 6

Vision:

```text
工程圖中可觀察到......
```

### Step 7

User:

```text
把剛才的工程資料與圖片分析整理成明天會議用摘要
```

Agent:

```text
RAG + Vision
      ↓
Meeting Summary
```

### Step 8

User:

```text
寄給 PM
```

Agent creates:

```text
Email Preview
```

### Step 9

User clicks:

```text
Confirm Send
```

### Step 10

Execution:

```text
Agent
 ↓
MCP Client
 ↓
MCP Server
 ↓
send_email()
 ↓
Gmail API
```

UI:

```text
✓ Email sent successfully
```

---

# 22. Error Handling

Implement basic handling for:

* invalid PDF
* empty PDF
* unsupported image format
* LLM API timeout
* LLM API error
* embedding API error
* ChromaDB unavailable
* Gmail authentication failure
* Gmail API failure
* MCP tool failure

Do not expose API keys or sensitive credentials in error messages.

---

# 23. Logging

Backend should log:

```text
[DOCUMENT]
PDF uploaded

[RAG]
Document indexed

[RAG]
Query received

[RAG]
Retrieved 5 chunks

[LLM]
Generating answer

[AGENT]
Tool selected: search_documents

[MCP]
Tool called: send_email

[EMAIL]
Email sent successfully
```

Do not log:

* API keys
* OAuth tokens
* email access tokens
* full sensitive email contents

---

# 24. Persistence

Use Docker volumes.

Required:

```text
documents
images
chroma
```

Example:

```yaml
volumes:
  document_data:
  image_data:
  chroma_data:
```

Running:

```bash
docker compose down
```

should NOT delete uploaded documents or vector data.

---

# 25. Docker Commands

README must document:

### Build

```bash
docker compose build
```

### Start

```bash
docker compose up -d
```

### Logs

```bash
docker compose logs -f
```

### Stop

```bash
docker compose down
```

### Restart

```bash
docker compose restart
```

Frontend should be accessible locally.

Backend should expose Swagger:

```text
/docs
```

---

# 26. Health Check

Implement:

```text
GET /api/health
```

Return:

```json
{
  "status": "ok",
  "services": {
    "api": "ok",
    "chromadb": "ok",
    "llm": "configured",
    "mcp": "ok"
  }
}
```

---

# 27. Testing

At minimum implement:

### Unit tests

* PDF extraction
* chunking
* RAG retrieval
* email validation

### Integration test

Test:

```text
PDF
→ indexing
→ query
→ retrieval
→ LLM
```

For Gmail, provide a mock mode.

Example:

```env
EMAIL_MODE=mock
```

Then:

```text
send_email()
```

does not actually send an email but logs:

```text
[MOCK EMAIL]
To: ...
Subject: ...
```

This allows local development without Gmail OAuth.

---

# 28. Configuration Strategy

Use:

```env
LLM_PROVIDER=gemini
EMAIL_MODE=mock
```

Support:

```text
gemini
anthropic
```

through a service abstraction.

Do NOT tightly couple the entire application to one LLM provider.

---

# 29. Security

Minimum requirements:

* `.env` in `.gitignore`
* `.env.example` committed
* no API keys in source code
* validate uploaded file types
* limit upload size
* sanitize filenames
* validate email addresses
* do not automatically send email
* human confirmation required before sending

Suggested PDF limit:

```text
100 MB
```

Suggested image limit:

```text
10 MB
```

---

# 30. Development Priority

Implement strictly in this order:

## P0

```text
Docker
FastAPI
React
PDF Upload
PDF Parsing
ChromaDB
RAG
Chat
Sources / Page
```

## P1

```text
Vision
Agent
MCP
Mock Email
Email Preview
Human Confirmation
```

## P2

```text
Google OAuth
Gmail API
```

If time is limited, P0 + P1 must be completed before P2.

---

# 31. Definition of Done

The MVP is considered complete when the following can be demonstrated locally:

```text
docker compose up
        ↓
Open browser
        ↓
Upload T3 PDF
        ↓
PDF indexed
        ↓
Ask engineering question
        ↓
RAG answer
        ↓
Display source + page
        ↓
Upload engineering image
        ↓
Vision analysis
        ↓
Ask Agent to create meeting summary
        ↓
Generate email
        ↓
Show Email Preview
        ↓
User confirms
        ↓
MCP send_email()
        ↓
Email sent / mock sent
```

---

# 32. Important Engineering Principles

The project should demonstrate:

### RAG

LLM does not directly rely on its own knowledge.

```text
Documents
→ Retrieval
→ Context
→ LLM
```

### Vision

Vision understands visible engineering information but does not make unsupported safety/compliance conclusions.

### Agent

Agent decides which capability/tool is required.

### MCP

MCP provides a standardized tool interface for external actions.

### Human-in-the-Loop

Actions with external side effects require user confirmation.

### Traceability

AI answers should provide source document and page number whenever possible.

---

# 33. Coding Instructions for Claude Code

You are implementing this project as a working MVP.

Rules:

1. Do not over-engineer.
2. Prefer simple Python functions over complex frameworks.
3. Do not introduce LangChain or LangGraph unless clearly necessary.
4. Keep services modular.
5. Write readable Python.
6. Use type hints.
7. Add basic error handling.
8. Add tests for important services.
9. Keep Docker configuration simple.
10. Do not add features outside this specification.
11. Do not hard-code API keys.
12. Do not automatically send email.
13. Preserve document/page metadata throughout RAG.
14. Make the application runnable with `docker compose up`.
15. Update README as implementation progresses.

Before implementing a new dependency, evaluate whether it is actually necessary.

---

# 34. First Development Task

Start by creating:

```text
frontend/
backend/
data/
docker-compose.yml
.env.example
.gitignore
README.md
```

Then implement:

```text
Docker
→ FastAPI
→ React
→ ChromaDB
→ PDF upload
→ PDF parsing
→ RAG
→ Chat
```

Do not implement Gmail OAuth until the basic RAG workflow is working.

After P0 is working, continue with:

```text
Vision
→ Agent
→ MCP
→ Email Preview
→ Mock Email
→ Gmail OAuth
→ Gmail API
```

At each stage, ensure the previous workflow still works.

# 35. Final Demo Goal

The most important demonstration is:

> 「我不是只做一個 Chatbot，而是讓 AI 從工程文件中取得可信資訊，再透過 Agent 判斷要使用什麼工具，最後透過 MCP 執行實際工作；涉及 Email 等外部操作時，仍保留 Human-in-the-Loop。」

This is the primary purpose of the MVP.
