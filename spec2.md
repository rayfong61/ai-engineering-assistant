# AI Engineering Assistant — Development Spec v2.0

## 1. Project Overview

### Project Name

**AI Engineering Assistant**

### Project Positioning

以工程文件為知識基礎，結合 **RAG、Vision、Agent、MCP**，協助工程人員快速查詢工程資料、理解工程圖片、產生會議摘要，並透過 Gmail 執行實際工作流程。

核心目標：

> 建立一個具備「工程知識理解 → AI 分析 → Agent 工作流程 → MCP 工具執行」能力的 AI 工程助理。

---

# 2. Demo Scenario

主要資料來源：

**桃園國際機場第三航廈公開工程文件**

Demo 流程：

```text
Google Login
    ↓
Create Project
    ↓
Upload Engineering PDF
    ↓
PDF Processing
    ↓
Chunking
    ↓
Voyage AI Embedding
    ↓
Supabase PostgreSQL + pgvector
    ↓
RAG Question Answering
    ↓
Document / Page Citation
    ↓
Upload Engineering Image
    ↓
Claude Vision
    ↓
Agent
    ↓
Generate Meeting Summary
    ↓
Generate Email Draft
    ↓
Human Confirmation
    ↓
MCP
    ↓
Gmail API
    ↓
Email Sent
```

---

# 3. Technology Stack

| Layer          | Technology          | Responsibility         |
| -------------- | ------------------- | ---------------------- |
| Frontend       | React               | UI                     |
| UI             | Tailwind CSS        | Styling                |
| Backend        | FastAPI             | REST API               |
| Authentication | Supabase Auth       | Google OAuth / JWT     |
| Database       | Supabase PostgreSQL | Application data       |
| Vector DB      | pgvector            | Semantic search        |
| File Storage   | Supabase Storage    | PDF / Image            |
| LLM            | **Claude API**      | Reasoning / Generation |
| Vision         | **Claude API**      | Image understanding    |
| Embedding      | **Voyage AI**       | Text embeddings        |
| Agent          | Python              | Workflow orchestration |
| Tool Protocol  | Python MCP SDK      | Tool integration       |
| Email          | Gmail API           | Email sending          |
| Container      | Docker Compose      | Local deployment       |

---

# 4. Architecture

```text
                         Browser
                            │
                            ▼
                   React + Tailwind
                            │
                            │ JWT
                            ▼
                    FastAPI Backend
                            │
          ┌─────────────────┼──────────────────┐
          │                 │                  │
          ▼                 ▼                  ▼
     RAG Service       Agent Service      Vision Service
          │                 │                  │
          │                 ▼                  │
          │             MCP Client             │
          │                 │                  │
          ▼                 ▼                  ▼
┌────────────────────────────────────────────────────────┐
│                    Supabase Cloud                      │
│                                                        │
│  Supabase Auth                                         │
│       │                                                │
│  PostgreSQL + pgvector                                 │
│       │                                                │
│  Supabase Storage                                      │
└────────────────────────────────────────────────────────┘
          ▲
          │
          │
    Voyage AI API
    Claude API
          │
          ▼
      AI Services

Agent
  │
  ▼
MCP Server
  │
  ▼
Gmail API
```

---

# 5. AI Provider Architecture

## 5.1 Claude API

Claude 負責：

```text
LLM
Vision
Agent Reasoning
Summary Generation
Email Draft Generation
```

主要用途：

### RAG Answer

```text
User Question
+
Retrieved Context
        ↓
    Claude API
        ↓
Engineering Answer
```

### Vision

```text
Engineering Image
        ↓
    Claude Vision
        ↓
Image Analysis
```

### Meeting Summary

```text
RAG Context
+
Vision Result
        ↓
    Claude API
        ↓
Meeting Summary
```

---

# 6. Voyage AI Embedding

Voyage AI 專門負責 Embedding。

## PDF ingestion

```text
PDF
 ↓
Text Extraction
 ↓
Chunking
 ↓
Voyage AI
 ↓
Embedding Vector
 ↓
pgvector
```

## User Query

```text
User Question
 ↓
Voyage AI
 ↓
Query Embedding
 ↓
pgvector Similarity Search
 ↓
Top K Chunks
 ↓
Claude API
```

### Design Principle

Claude 不負責 Vector Search。

Voyage AI 不負責產生最終答案。

兩者職責分離：

```text
Voyage AI
→ Retrieval

Claude
→ Understanding / Reasoning / Generation
```

---

# 7. Supabase Responsibilities

Supabase 負責：

### Authentication

```text
Google OAuth
    ↓
Supabase Auth
    ↓
JWT
    ↓
FastAPI
```

### PostgreSQL

儲存：

```text
users
projects
project_members
documents
document_chunks
conversations
messages
email_logs
```

### pgvector

儲存：

```text
document embedding
```

並執行：

```text
Similarity Search
```

### Storage

儲存：

```text
PDF
Engineering Images
```

---

# 8. Multi-user Architecture

Project 是主要資料隔離單位。

```text
User
 │
 ├── Project A
 │      ├── Documents
 │      ├── Conversations
 │      └── Members
 │
 └── Project B
        ├── Documents
        └── Conversations
```

User A 不可以讀取 User B 沒有權限的 Project。

## Authorization Rules

Backend 不信任 Frontend 傳入的 user_id。

正確：

```text
JWT
 ↓
FastAPI
 ↓
Get current_user
 ↓
Check project_members
 ↓
Allow / Deny
```

---

# 9. Database Schema

## projects

```sql
id UUID PRIMARY KEY
name TEXT NOT NULL
description TEXT
created_by UUID NOT NULL
created_at TIMESTAMPTZ
```

---

## project_members

```sql
project_id UUID NOT NULL
user_id UUID NOT NULL
role TEXT NOT NULL
created_at TIMESTAMPTZ
```

Roles：

```text
owner
member
```

---

## documents

```sql
id UUID PRIMARY KEY
project_id UUID NOT NULL
uploaded_by UUID NOT NULL
filename TEXT NOT NULL
storage_path TEXT NOT NULL
file_size BIGINT
status TEXT NOT NULL
created_at TIMESTAMPTZ
```

Status：

```text
uploaded
processing
ready
failed
```

---

## document_chunks

```sql
id UUID PRIMARY KEY
document_id UUID NOT NULL
project_id UUID NOT NULL
page INTEGER
chunk_index INTEGER
content TEXT NOT NULL
embedding VECTOR(N)
created_at TIMESTAMPTZ
```

`N` 必須與實際使用的 Voyage embedding model dimension 一致。

**不要在開發初期自行假設 dimension。**

---

## conversations

```sql
id UUID PRIMARY KEY
project_id UUID NOT NULL
user_id UUID NOT NULL
title TEXT
created_at TIMESTAMPTZ
updated_at TIMESTAMPTZ
```

---

## messages

```sql
id UUID PRIMARY KEY
conversation_id UUID NOT NULL
user_id UUID
role TEXT NOT NULL
content TEXT NOT NULL
metadata JSONB
created_at TIMESTAMPTZ
```

Roles：

```text
user
assistant
system
tool
```

---

## email_logs

```sql
id UUID PRIMARY KEY
project_id UUID
user_id UUID NOT NULL
recipient TEXT
subject TEXT
body TEXT
status TEXT
created_at TIMESTAMPTZ
```

Status：

```text
draft
confirmed
sent
failed
cancelled
```

---

# 10. Supabase Storage

Bucket：

```text
engineering-documents
```

Storage path：

```text
projects/{project_id}/documents/{document_id}/{filename}
```

Example：

```text
projects/
  project-001/
    documents/
      document-001/
        T3-engineering.pdf
```

工程圖片可以：

```text
projects/{project_id}/images/{image_id}/{filename}
```

---

# 11. RAG Pipeline

## Document Ingestion

```text
Upload PDF
     ↓
Supabase Storage
     ↓
FastAPI
     ↓
PDF Parser
     ↓
Text Extraction
     ↓
Chunking
     ↓
Voyage AI Embedding
     ↓
PostgreSQL + pgvector
```

---

# 12. Chunking

MVP 使用固定大小 Chunk。

例如：

```text
chunk_size = 800~1200 tokens
overlap = 100~200 tokens
```

實際數值可透過測試調整。

每個 chunk 必須保留：

```text
document_id
project_id
page
chunk_index
content
embedding
```

Page metadata 是為了最後顯示來源。

---

# 13. Retrieval

API：

```http
POST /api/projects/{project_id}/chat
```

Request：

```json
{
  "conversation_id": "...",
  "message": "第三航廈有哪些主要工程內容？"
}
```

Processing：

```text
Question
 ↓
Voyage Embedding
 ↓
pgvector similarity search
 ↓
Filter project_id
 ↓
Top K
 ↓
Retrieved Context
 ↓
Claude API
```

預設：

```text
top_k = 5
```

---

# 14. Project-scoped Retrieval

RAG 查詢必須包含：

```text
project_id
```

概念：

```sql
SELECT *
FROM document_chunks
WHERE project_id = :project_id
ORDER BY embedding <=> :query_embedding
LIMIT 5;
```

實際 SQL operator 依 pgvector cosine / distance 設定決定。

**禁止跨 Project Retrieval。**

---

# 15. RAG Response

Response：

```json
{
  "answer": "第三航廈工程主要包含……",
  "sources": [
    {
      "document_id": "...",
      "filename": "T3-engineering.pdf",
      "page": 12,
      "content": "..."
    }
  ]
}
```

Frontend 顯示：

```text
AI Answer

第三航廈主要工程包含……

Sources
├── T3-engineering.pdf — Page 12
├── T3-engineering.pdf — Page 18
└── T3-engineering.pdf — Page 35
```

---

# 16. RAG Prompt

Claude System Prompt：

```text
You are an AI engineering assistant.

Answer questions only using the provided retrieved context.

Do not invent engineering information.

If the provided context is insufficient, clearly state that
the available engineering documents do not contain enough
information to answer the question.

Always preserve source attribution when available.

Do not make unsupported claims about:
- structural safety
- construction quality
- regulatory compliance
- engineering approval
- inspection approval
```

---

# 17. Vision

API：

```http
POST /api/projects/{project_id}/vision
```

Input：

```text
JPG
PNG
WEBP
```

Flow：

```text
Engineering Image
       ↓
Claude Vision
       ↓
Observation
       ↓
Analysis
       ↓
Limitations
```

Response：

```json
{
  "analysis": "...",
  "observations": [
    "..."
  ],
  "limitations": [
    "無法僅由圖片判斷結構安全性"
  ]
}
```

---

# 18. Vision Safety Boundary

AI 不可僅依據圖片直接宣稱：

```text
結構安全
施工品質合格
法規合規
工程驗收通過
```

應使用：

```text
可觀察到
可能
疑似
需要人工確認
```

例如：

> 「圖片中可觀察到鋼構構件與施工設備，但僅憑圖片無法確認施工品質或結構安全性。」

---

# 19. Agent

MVP 不使用 LangChain / LangGraph。

使用 Python 自行建立簡單 Agent。

Agent Tools：

```text
search_documents
analyze_image
generate_summary
send_email
```

Agent Input：

```text
user
project
conversation
message
```

Agent 決定：

```text
需要搜尋文件？
需要分析圖片？
需要產生摘要？
需要寄信？
```

---

# 20. Agent Example

User：

> 請把剛才第三航廈的工程資料和圖片分析整理成明天會議摘要。

Agent：

```text
User Request
    ↓
search_documents
    ↓
Retrieve Engineering Context
    ↓
analyze_image
    ↓
Vision Result
    ↓
Claude
    ↓
Meeting Summary
```

---

# 21. MCP

使用：

**Python MCP SDK**

MCP Server Tools：

```text
search_documents
send_email
```

架構：

```text
Agent
 ↓
MCP Client
 ↓
MCP Server
 ↓
Tool
 ↓
Service
```

---

# 22. MCP — search_documents

Tool：

```text
search_documents(
    query,
    project_id
)
```

Processing：

```text
query
 ↓
Voyage Embedding
 ↓
pgvector
 ↓
Project-scoped Search
 ↓
Top K Chunks
```

MCP 不可繞過 Project Authorization。

---

# 23. MCP — send_email

Tool：

```text
send_email(
    to,
    subject,
    body
)
```

Flow：

```text
Agent
 ↓
MCP Client
 ↓
MCP Server
 ↓
Gmail Service
 ↓
Gmail API
```

---

# 24. Human-in-the-loop

**禁止 Agent 自動寄信。**

錯誤：

```text
User
 ↓
"寄給 PM"
 ↓
Agent
 ↓
Gmail API
```

正確：

```text
User
 ↓
"寄給 PM"
 ↓
Agent
 ↓
Generate Email Draft
 ↓
Frontend Preview
 ↓
User Confirm
 ↓
MCP send_email()
 ↓
Gmail API
```

---

# 25. Email Preview

Frontend：

```text
┌─────────────────────────────────┐
│ Email Preview                   │
│                                 │
│ To: PM                          │
│                                 │
│ Subject: 第三航廈工程會議摘要     │
│                                 │
│ Body:                           │
│ 第三航廈目前工程重點如下……        │
│                                 │
│ [Cancel]      [Confirm & Send]  │
└─────────────────────────────────┘
```

只有：

```text
Confirm & Send
```

之後才能真正呼叫：

```text
send_email()
```

---

# 26. Gmail API

**注意：App Login 與 Gmail 寄信是兩組不同的 OAuth 授權，不可混用同一組 token。**

```text
App Login (Supabase Auth)
    Google OAuth
    scope: openid, email, profile
    ↓
    Supabase JWT（給 FastAPI 驗證身份用）

Gmail Send (獨立授權)
    Google OAuth
    scope: https://www.googleapis.com/auth/gmail.send
    ↓
    Access Token + Refresh Token（給 gmail_service.py 呼叫 Gmail API 用）
```

若想沿用 Supabase Auth 的 Google 登入流程一併取得 gmail.send scope，必須：

```text
1. 在 Supabase Auth 的 Google provider 設定額外 scope（additional_scopes）
2. signInWithOAuth 時帶入 scopes: 'https://www.googleapis.com/auth/gmail.send'
   並設定 access_type=offline, prompt=consent 才會拿到 refresh_token
3. 自行將 provider_token / provider_refresh_token 存入自己的資料表
   （Supabase 預設不會長期保存這兩個值，session 過期後就取不到）
```

否則應採用**獨立的 Gmail OAuth flow**（不透過 Supabase Auth），單純為 `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` / `GOOGLE_REDIRECT_URI` 走一次 gmail.send 專用授權，token 存在 backend（例如 users 表新增 `gmail_refresh_token` 欄位，加密儲存）。

MVP 開發順序不受影響：先用 `EMAIL_MODE=mock`，Gmail OAuth 留到 Day 3 再實作，並在該階段明確選定上述其中一種方式。

Token 不可以明文寫入 Git。

MVP 可以先：

```env
EMAIL_MODE=mock
```

完成完整 Workflow 後再：

```env
EMAIL_MODE=gmail
```

---

# 27. API Endpoints

## Authentication

```http
GET /api/auth/me
```

---

## Projects

```http
GET /api/projects

POST /api/projects

GET /api/projects/{project_id}
```

---

## Documents

```http
POST /api/projects/{project_id}/documents

GET /api/projects/{project_id}/documents

DELETE /api/projects/{project_id}/documents/{document_id}
```

---

## Chat / RAG

```http
POST /api/projects/{project_id}/chat

GET /api/projects/{project_id}/conversations

GET /api/conversations/{conversation_id}
```

---

## Vision

```http
POST /api/projects/{project_id}/vision
```

---

## Agent

```http
POST /api/projects/{project_id}/agent
```

---

## Email

```http
POST /api/projects/{project_id}/email/preview

POST /api/projects/{project_id}/email/send
```

---

## Health

```http
GET /api/health
```

---

# 28. Frontend Pages

```text
/login

/projects

/projects/:id

/projects/:id/chat

/projects/:id/documents
```

Project Page：

```text
┌─────────────────────────────────────────┐
│ 桃園機場第三航廈                         │
├─────────────────────────────────────────┤
│ Documents │ Chat │ Vision │ Activity    │
├─────────────────────────────────────────┤
│                                         │
│              Main Content               │
│                                         │
└─────────────────────────────────────────┘
```

---

# 29. Activity Log

顯示重要 AI Workflow：

```text
User logged in
       ↓
Project created
       ↓
PDF uploaded
       ↓
PDF processing completed
       ↓
Embedding generated
       ↓
RAG search executed
       ↓
Vision analysis completed
       ↓
Meeting summary generated
       ↓
Email draft generated
       ↓
User confirmed email
       ↓
Email sent
```

---

# 30. Docker

Local Docker 只需要：

```text
frontend
backend
mcp-server
```

不需要：

```text
PostgreSQL
ChromaDB
Local LLM
```

Architecture：

```text
Docker Compose
├── frontend
├── backend
└── mcp-server
```

Cloud：

```text
Supabase
├── Auth
├── PostgreSQL
├── pgvector
└── Storage
```

External:

```text
Claude API
Voyage AI
Gmail API
```

---

# 31. Environment Variables

`.env.example`

```env
SUPABASE_URL=
SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=

ANTHROPIC_API_KEY=

VOYAGE_API_KEY=
VOYAGE_EMBEDDING_MODEL=

GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=

EMAIL_MODE=mock

FRONTEND_URL=http://localhost:5173
BACKEND_URL=http://localhost:8000
```

---

# 32. Security Rules

## Never commit

```text
.env
API Keys
OAuth Secrets
Access Tokens
Service Role Key
```

## Backend

必須驗證：

```text
JWT
 ↓
current_user
 ↓
project membership
 ↓
resource access
```

## Service Role Key

只能存在 Backend。

Frontend 不可取得：

```text
SUPABASE_SERVICE_ROLE_KEY
```

---

# 33. Project Structure

```text
ai-engineering-assistant/
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── hooks/
│   │   ├── services/
│   │   ├── types/
│   │   └── App.jsx
│   ├── Dockerfile
│   └── package.json
│
├── backend/
│   ├── app/
│   │   ├── main.py
│   │
│   │   ├── api/
│   │   │   ├── auth.py
│   │   │   ├── projects.py
│   │   │   ├── documents.py
│   │   │   ├── chat.py
│   │   │   ├── vision.py
│   │   │   ├── agent.py
│   │   │   └── email.py
│   │
│   │   ├── services/
│   │   │   ├── supabase_service.py
│   │   │   ├── storage_service.py
│   │   │   ├── pdf_service.py
│   │   │   ├── embedding_service.py
│   │   │   ├── rag_service.py
│   │   │   ├── claude_service.py
│   │   │   ├── vision_service.py
│   │   │   └── gmail_service.py
│   │
│   │   ├── agent/
│   │   │   └── agent_service.py
│   │
│   │   ├── mcp/
│   │   │   ├── server.py
│   │   │   └── tools/
│   │   │       ├── search_documents.py
│   │   │       └── send_email.py
│   │
│   │   ├── models/
│   │   ├── schemas/
│   │   └── core/
│   │
│   ├── tests/
│   ├── requirements.txt
│   └── Dockerfile
│
├── data/
│   └── temp/
│
├── docker-compose.yml
├── .env.example
├── .gitignore
└── README.md
```

---

# 34. Service Responsibilities

## claude_service.py

```text
generate_answer()
analyze_image()
generate_summary()
generate_email_draft()
```

---

## embedding_service.py

```text
embed_text()
embed_documents()
```

Implementation：

```text
Voyage AI API
```

---

## rag_service.py

```text
retrieve_chunks()
build_context()
answer_question()
```

---

## vision_service.py

```text
analyze_engineering_image()
```

---

## agent_service.py

```text
process_request()
select_tools()
execute_workflow()
```

---

## gmail_service.py

```text
create_message()
send_message()
```

---

# 35. Error Handling

PDF：

```text
Upload
 ↓
Processing
 ↓
Failed
```

Frontend 顯示：

```text
Document processing failed.
Please try again.
```

RAG：

```text
No relevant context
 ↓
Claude
 ↓
「目前提供的工程文件中沒有足夠資訊回答此問題。」
```

Vision：

```text
Unsupported image
 ↓
400 Bad Request
```

Gmail：

```text
API failure
 ↓
email_logs.status = failed
```

---

# 36. MVP Scope

## P0 — 必須完成

```text
Google Login
Project
Multi-user Permission
PDF Upload
Supabase Storage
PDF Processing
Voyage Embedding
pgvector
RAG
Source / Page Citation
```

---

## P1 — Demo 核心

```text
Claude Vision
Agent
MCP
Email Draft
Human Confirmation
Mock Email
```

---

## P2 — 有時間再做

```text
Gmail OAuth
Gmail API
Activity Log
UI Polish
Error Handling
RAG Evaluation
```

---

# 37. Five-Day Development Plan

## Risk-reduction simplifications (apply across all 5 days)

```text
1. Gmail OAuth 使用獨立的 Gmail-only OAuth flow，
   不透過延伸 Supabase Auth 的 login scope 取得。
   兩組 client / 兩組 token，互不依賴。
   若時程吃緊，可隨時退回 EMAIL_MODE=mock，
   demo 完整性不受影響（Human-in-the-loop 才是重點，
   不是「真的寄出去」）。

2. Authorization 第一版只做「是否為 project 成員」的檢查，
   不做 owner/member 差異化權限（例如 member 能否刪除文件）。
   role 欄位保留，differentiated permission 留到有餘裕再做。
```

## Day 1 — Foundation + Auth + Project

```text
Docker
React
FastAPI
Supabase 專案設定（Auth / Postgres / Storage）
Google Login（Supabase Auth）
Database Schema
Project CRUD
Authorization（membership-only check）
```

Day 1 最終成果：

```text
Login
 ↓
Create Project
 ↓
（同帳號可見自己的 Project，跨帳號互相看不到）
```

---

## Day 2 — RAG Pipeline

```text
PDF Upload
Storage
PDF Parsing
Chunking
Voyage Embedding
pgvector
RAG Retrieval
Claude Answer Generation
Source / Page Citation
```

Day 2 最終成果：

```text
Upload PDF
 ↓
Build Knowledge Base
 ↓
Ask Question
 ↓
RAG
 ↓
Source + Page
```

風險提醒：中文工程 PDF 常含表格與圖面，文字抽取品質可能不理想，預留時間人工檢查抽取結果、必要時調整 chunking 或改用更適合的 PDF parser。

---

## Day 3 — Vision + Agent + MCP

```text
Claude Vision
Agent（工具選擇邏輯）
MCP Server（search_documents, send_email）
Agent → MCP Client 串接
Meeting Summary 生成
```

Day 3 最終成果：

```text
PDF + Engineering Image
 ↓
RAG + Vision
 ↓
Claude
 ↓
Meeting Summary
```

風險提醒：Python MCP SDK 是團隊最不熟悉的部分，優先把 search_documents / send_email 包成最簡單的 tool wrapper，不要在協定細節上過度打磨。若嚴重卡關，可依 spec.md 舊有彈性原則，先把 MCP Server 邏輯併入 backend process，待穩定後再視時間拆分。

---

## Day 4 — Email Draft + Preview + Gmail OAuth

```text
Email Draft 生成
Email Preview UI
Confirm & Send
Mock Email（EMAIL_MODE=mock）
Gmail OAuth（獨立 flow，見上方風險簡化）
Gmail API 串接
```

Day 4 最終成果：

```text
Meeting Summary
 ↓
Email Draft
 ↓
Email Preview
 ↓
Confirm & Send
 ↓
Mock Send（一定要先跑通）
 ↓
Real Gmail Send（有餘裕才做，跑不完就停在 Mock）
```

---

## Day 5 — Buffer + Polish + Demo Prep

```text
Gmail OAuth 收尾（若 Day 4 未完成，此日截止仍卡關則退回 Mock Email）
UI Polish
Error Handling
Activity Log
端到端完整跑 3-5 次，找出並修正流程斷點
README / Demo Script
面試講稿與問答準備
```

Definition of Done（第 5 天結束時）：完整 demo flow（Login → Project → PDF → RAG → Vision → Agent → Meeting Summary → Email Preview → Confirm → Send/Mock Send）至少能穩定重現 3 次以上，不需要臨場除錯。

---

# 38. RAG Evaluation

建立 10～20 個固定問題。

例如：

```text
Q1 第三航廈主要工程內容？
Q2 航站區有哪些設施？
Q3 機電工程包含哪些項目？
Q4 停機坪工程內容？
Q5 航站樓結構相關資訊？
```

記錄：

```text
Question
Expected Page
Top 5 Retrieved
Correct / Incorrect
```

基本評估：

```text
Retrieval Accuracy
=
找到正確來源的問題數
/
總問題數
```

---

# 39. Final Demo Flow

面試現場：

### Step 1

Google Login

### Step 2

建立：

```text
桃園機場第三航廈
```

### Step 3

Upload：

```text
T3-engineering.pdf
```

### Step 4

等待：

```text
Processing → Ready
```

### Step 5

詢問：

> 第三航廈有哪些主要工程內容？

### Step 6

Claude 回答：

```text
工程內容……

Sources:
T3-engineering.pdf — Page 12
T3-engineering.pdf — Page 35
```

### Step 7

Upload 工程圖片。

### Step 8

詢問：

> 分析這張工程圖。

Claude Vision：

```text
Observations
Limitations
```

### Step 9

詢問：

> 把剛才的工程資料和圖片分析整理成明天會議摘要。

Agent：

```text
RAG
+
Vision
 ↓
Claude
 ↓
Meeting Summary
```

### Step 10

詢問：

> 幫我寄給 PM。

Agent：

```text
Generate Email Draft
```

### Step 11

UI：

```text
Email Preview

[Cancel] [Confirm & Send]
```

### Step 12

按：

```text
Confirm & Send
```

### Step 13

```text
MCP
 ↓
send_email()
 ↓
Gmail API
 ↓
Email Sent
```

---

# 40. Interview Architecture Explanation

面試時可以這樣說：

> 「我把系統設計成 Project-scoped 的 AI Engineering Assistant。使用 Supabase 處理 Authentication、PostgreSQL、Storage 以及 pgvector；工程 PDF 經過 Chunking 後使用 Voyage AI 產生 Embedding，建立工程知識庫。使用者提問時先透過 pgvector 做 Retrieval，再將相關工程內容交給 Claude 產生回答並附上來源頁碼。圖片則透過 Claude Vision 分析。當使用者需要執行工作時，由 Agent 判斷需要哪些工具，再透過 MCP 呼叫，例如產生 Email Draft。涉及真正的外部操作時加入 Human-in-the-loop，使用者確認後才透過 MCP 呼叫 Gmail API 寄信。」

---

# 41. Core Architecture Principle

整個系統的核心分工：

```text
Supabase
→ Identity / Data / Storage

Voyage AI
→ Embedding / Retrieval

pgvector
→ Vector Search

Claude
→ Understanding / Reasoning / Generation / Vision

Agent
→ Decide What To Do

MCP
→ Standardized Tool Integration

Gmail API
→ Real-world Action

Human
→ Final Approval
```

最終形成：

```text
Engineering Documents
        ↓
      RAG
        ↓
    Claude AI
        ↓
     Vision
        ↓
      Agent
        ↓
       MCP
        ↓
External Tools
        ↓
   Human Approval
```

---

# 42. Future Extension

MVP 完成後可以擴充：

```text
V2
├── Reranking
├── Hybrid Search
├── Better Chunking
├── Engineering Metadata
└── RAG Evaluation

V3
├── LangChain
├── LangGraph
├── Multi-Agent
├── BIM Data
├── CAD / IFC
└── Engineering Workflow Automation
```

LangChain / LangGraph 不納入三天 MVP，避免增加不必要的框架複雜度。
