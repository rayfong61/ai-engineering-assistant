# AI Engineering Assistant

Project-scoped、多使用者的 AI 工程助理，以桃園國際機場第三航廈（T3）公開工程文件為 demo 資料。開發準則與逐日實作細節見 [`CLAUDE.md`](CLAUDE.md)。

## 這個專案展示什麼

```
Google 登入 → 建立專案 → 上傳工程 PDF/圖片 → RAG 問答 → Vision 分析 → Agent 整合 → Email 確認寄送
```

不是一個聊天機器人，而是一條完整的工程 pipeline，串起以下幾項技術能力：

- **RAG 檢索增強生成** — PDF 解析（PyMuPDF）→ 分塊 → Voyage AI embedding → pgvector 相似度檢索 → Claude 生成回答，並保留來源文件＋頁碼，禁止臆測（檢索不到就明確說沒有足夠資訊）。對 18 題真實題庫跑出 **94% 檢索準確率**（`backend/scripts/eval_rag.py`）。
- **Claude Vision** — 分析工程圖片，用「可觀察到／可能／疑似／需要人工確認」等保留語氣描述，不對結構安全、施工品質、法規合規做未經證據支持的斷言。
- **Agent 工具選擇迴圈** — 不依賴 LangChain/LangGraph 等框架，手刻 Claude tool-use 迴圈，讓 Claude 自主判斷何時呼叫 `search_documents`／`analyze_image`／`generate_summary`／`draft_email`，把 RAG 檢索與圖片分析整合成會議摘要。
- **MCP（Model Context Protocol）** — 獨立容器 `mcp-server`，只在 Docker compose 內網服務，backend 透過 MCP 呼叫 `search_documents`／`send_email`，frontend/瀏覽器完全連不到，結構性防止繞過 Project 授權。
- **Human-in-the-Loop** — Agent 只能產生 Email 草稿，永遠不能自己寄出；使用者在 Preview 畫面看到 To/Subject/Body 後，必須明確點擊 Confirm & Send 才會透過 MCP 呼叫寄信。
- **多租戶授權** — Project 是資料隔離單位，每個請求都從 JWT 解析身份、檢查 `project_members`，向量檢索一律加 `project_id` 過濾，不會跨專案洩漏資料。
- **Activity Log** — 11 個關鍵工作流程節點（登入、上傳、embedding、RAG 檢索、Vision 分析、摘要生成、Email 草稿/確認/寄出）都會留下可追溯的紀錄。
- **真實 Gmail 寄送** — 獨立於登入用 Google OAuth 的第二組 Gmail-only OAuth（`gmail.send` scope），使用者在 Settings 頁面連接自己的 Gmail 帳號後，Confirm & Send 會透過 MCP 呼叫真正的 Gmail API 寄出（`EMAIL_MODE=gmail`）；未連接時自動走 `EMAIL_MODE=mock`（記錄寄送內容但不真的呼叫 Gmail API），兩種模式都完整支援，不是互斥的取捨。

## 展示畫面

**Chat — RAG 問答，附來源文件與頁碼**
![Chat 分頁：RAG 問答附來源文件與頁碼](data/demo_pics/chat-rag-citations.png)
針對已上傳的 T3 工程 PDF 提問，答案逐條標註來源檔名與頁碼，不是憑空生成。

**已上傳圖片的分析結果**
![已上傳圖片的 Vision 分析結果，列出可觀察到的重點](data/demo_pics/chat-vision-analysis.png)
針對圖片的分析結果，以「可觀察到」清單呈現，保留語氣，不對結構安全/合規性做斷言。

**Agent — 自主判斷呼叫工具，整理成摘要**
![Agent 分頁：依序呼叫 search_documents 與 generate_summary，產生會議摘要](data/demo_pics/agent-tool-calls-summary.png)
使用者只問了一句「第三航廈的亮點整理」，Agent 自行判斷呼叫三次 `search_documents`（不同關鍵字）再呼叫 `generate_summary`，整理成結構化摘要。

**Agent — 產生 Email 草稿（Human-in-the-Loop）**
![Agent 產生 Email 草稿，顯示 Email Preview 卡片](data/demo_pics/agent-email-preview.png)
請 Agent 把摘要寫成 email 後，畫面顯示 Preview 卡片（To／Subject／Body），Agent 本身不會寄出。

**Confirm & Send 才會真正寄出**
![Email Preview 卡片下方的 Confirm & Send 按鈕](data/demo_pics/agent-confirm-send.png)
必須使用者手動點擊 Confirm & Send，才會透過 MCP 呼叫 Gmail API 真正送出——這是整個專案的核心 Human-in-the-Loop 設計。

**查無資料時誠實說明，不臆測**
![Agent 對「台灣高鐵月台設計規範」的提問誠實回覆知識庫沒有相關資料](data/demo_pics/agent-honest-no-data.png)
問了知識庫裡沒有的「台灣高鐵月台設計規範」，Agent 呼叫 `search_documents` 後如實說明查無直接相關資料、列出知識庫實際收錄的內容，並主動釐清使用者是否問錯了對象——不會硬套 T3 的文件充當答案。

## 刻意不做的取捨

- **文件上傳只支援 PDF**，圖片只支援 JPG/PNG/WEBP，沒有 Word/Excel 等格式——超出 MVP 範圍。
- **授權只做「是否為專案成員」的檢查**，沒有做 owner/member 權限差異化（`role` 欄位保留，之後可以擴充）。
- **不使用 LangChain/LangGraph 等 Agent 框架**，Tool-use 迴圈是手刻的簡單迴圈——換取的是完全掌控 Prompt 與工具邊界（例如結構性保證 Agent 不會呼叫真正的寄信工具），而不是框架的便利性。

## 建置過程（Day 1-5 + Gmail OAuth follow-up，均已對真實資料端對端驗證，非僅單元測試）

- [x] **Day 1** — Docker Compose、Supabase Auth（Google + Email/Password）、Project CRUD、`project_members` membership-only 授權
- [x] **Day 2** — PDF 上傳 → Supabase Storage → PyMuPDF 抽取 → 分塊 → Voyage Embedding → pgvector → Claude 生成答案（含來源文件＋頁碼引用）
- [x] **Day 3** — Claude Vision、Agent 工具選擇迴圈、MCP server（`search_documents`、`send_email`）
- [x] **Day 4** — Email 草稿生成、Preview 卡片、Confirm & Send、Mock Email
- [x] **Day 5** — Activity Log、RAG Evaluation（94% 檢索準確率）、error handling 補強
- [x] **Gmail OAuth follow-up** — 真實 Gmail API 寄送、Settings 頁面 Connect/Disconnect、encrypted refresh token（Fernet）

自動化測試：`backend/tests/`，78 個測試全過（`docker compose exec backend python -m pytest -v`）。

## 架構筆記

### 三個容器：frontend / backend / mcp-server

`docker compose up -d` 會啟動三個容器。`mcp-server`（Day 3 加入）是從 `backend/` 同一份 build context 另外建出的第二個 image（`backend/Dockerfile.mcp`），與 `backend` 共用 `requirements.txt`、直接 import `app.services`/`app.models`，不是獨立的頂層套件。它只在 compose 內網用 Streamable HTTP 提供服務（`mcp-server:8001`），host 上開的 `8001` port 純粹方便本機除錯，正式流程裡 frontend/瀏覽器永遠連不到它——這是「MCP 不可繞過 Project Authorization」的結構性保證：MCP server 本身沒有 JWT/使用者context，能檢查權限的只有已經驗證過身份的 backend。

`mcp-server` **沒有 hot-reload**（`backend` 有，靠 `uvicorn --reload`）。改了 `backend/app/mcp/` 底下的東西之後，要手動：

```bash
docker compose restart mcp-server
```

Database/Auth/Storage 都不是這裡的 container，來自 Supabase（見下一節：本地 CLI stack 或雲端專案，看 `.env` 指向哪邊）。

### 開發環境：目前 `.env` 預設指向雲端 Supabase 專案

Day 1 剛開始時因為 Supabase 雲端平台一度發生 incident 無法建立專案，改用本地 CLI stack（`supabase start`，見 `supabase/config.toml`）在本機 Docker 跑一套跟雲端一模一樣的 Auth + Postgres + Storage。**Day 3 之後，雲端專案已經建好，`.env` 已經改成預設指向雲端**（`SUPABASE_URL`/`DATABASE_URL` 都是 `*.supabase.co`）。本地 CLI stack 仍然可以當 fallback 用，但一個全新的 `docker compose up` 預設打的是雲端專案，不要假設是本地——先看 `.env` 再判斷。

### 切換 local / 雲端環境

實際生效的設定永遠是 `.env`（docker-compose 讀這個檔案）。`.env.local` 和 `.env.cloud` 是兩份完整備份，**不要在 `.env` 裡同時貼兩組值**（同一個變數名稱重複，dotenv 只認最後一次出現，會混出「DB 是本地、Auth 是雲端」這種壞掉的組合）。切換方式：

```bash
cp .env.local .env    # 切回本地 Supabase CLI stack
cp .env.cloud .env    # 切成打雲端 Supabase 專案（目前預設）
docker compose up -d --force-recreate    # 套用新的環境變數
```

三份檔案（`.env`、`.env.local`、`.env.cloud`）都在 `.gitignore` 裡，不會進 git。

### 雲端專案的 `DATABASE_URL` 要用 Session Pooler

Supabase 直連 host（`db.<ref>.supabase.co:5432`）只有 IPv6，Docker 容器預設連不上會出現 `Network is unreachable`。要用 Project Settings → Database → Connection string 的 **Session pooler**（不是 Direct connection，也不是 Transaction pooler）——支援 IPv4，且跟直連一樣是 session 模式（支援 prepared statements），適合 FastAPI 這種長連線 process。使用者名稱要帶上 project ref（`postgres.<ref>`）。

### 資料表存取不走 Supabase Data API

Frontend 只透過 Supabase Auth（GoTrue）登入；所有資料表都是 backend 用 **SQLAlchemy + Alembic 直連 Postgres**（不透過 PostgREST）。好處：Supabase 的「Enable Data API」可以直接關閉，攻擊面小一點；本地/雲端只差一個 `DATABASE_URL`。Storage 才用 `supabase-py`（`app/core/supabase_client.py`）。

### 使用者身份驗證：JWKS，不是共用密鑰

Supabase 用 **ES256 非對稱簽章**簽發使用者 session token（不是舊式的 HS256 + 共用 secret）。`app/core/auth.py` 用 `PyJWKClient` 向 `SUPABASE_URL` 的 `/auth/v1/.well-known/jwks.json` 動態抓公鑰驗證，本地 CLI 和雲端專案共用同一套邏輯。`jwt.decode(...)` 帶 `leeway=30`，避免容器時鐘略微落後導致 `ImmatureSignatureError`。

### 兩種登入方式

- **Google 登入**：正式 demo 用，需要在 Supabase 設定 Google provider。
- **Email/Password**：本地開發/測試用，前端 Login 頁面內建表單，不需要任何外部 OAuth 設定。

### Email 寄送：兩組完全獨立的 OAuth

Supabase Auth 的 Google 登入（scope: openid/email/profile）跟 Gmail 寄信（scope: `gmail.send`）是**兩個獨立的 OAuth 授權**，不要假設登入的 token 可以拿來寄信——這是刻意的架構決策（spec2.md §26/§37），不是偷懶少做一半。

- `EMAIL_MODE=mock`（預設，且永遠完整支援的 fallback）：`app/mcp/tools/send_email.py` 記錄 `[MOCK EMAIL] to=... subject=...`（不記完整內文）並回傳 `status: "sent"`，不需要任何 Gmail 設定。
- `EMAIL_MODE=gmail`：真的透過 Gmail API 寄信。使用者在 Settings 頁面連接自己的 Gmail 帳號（`/api/gmail/authorize-url` → Google 同意畫面 → `/api/gmail/callback`），refresh token 用 Fernet 加密存進 `gmail_credentials`，每次寄送前才即時換取 access token（不快取）。純 `httpx` 打 Google 的三支 API（授權碼交換、refresh 交換、實際寄送），沒有引入 `google-api-python-client` 之類的 client SDK。需要 `GMAIL_CLIENT_ID`/`GMAIL_CLIENT_SECRET`/`GMAIL_REDIRECT_URI`/`GMAIL_TOKEN_ENCRYPTION_KEY` 四個變數（見下方「前置設定」），且這組 OAuth Client 必須是跟登入用 Google Provider **不同**的 Client ID。

## 前置設定

### 1. 環境變數

```bash
cp .env.example .env
```

`.env.example` 裡每個變數都有註解說明來源。目前預設要打雲端 Supabase 專案，需要填：

- `DATABASE_URL`、`SUPABASE_URL`、`SUPABASE_ANON_KEY`、`SUPABASE_SERVICE_ROLE_KEY`、`VITE_SUPABASE_URL`、`VITE_SUPABASE_ANON_KEY`（見下方「2. 雲端 Supabase 專案」）
- `ANTHROPIC_API_KEY`（Claude — RAG 生成答案、Vision、Agent、Email 草稿都要用）
- `VOYAGE_API_KEY`（Voyage AI — PDF 分塊後的 embedding，Day 2 起必填，否則上傳 PDF 會索引失敗）
- `EMAIL_MODE=mock`（預設值，不需要任何 Gmail 設定就能跑完整 demo；要真的寄信才需要填下面四個 `GMAIL_*` 變數並設成 `EMAIL_MODE=gmail`，見上方「Email 寄送」一節）

想改跑本地 Supabase CLI stack 的話，見上方「切換 local / 雲端環境」，改用 `cp .env.local .env` 再跑第 3 步的 `npx supabase start`。

### 2. 雲端 Supabase 專案（目前預設環境）

1. 到 [supabase.com](https://supabase.com) 建立新專案。
2. 到 Project Settings → API，複製 `Project URL`、`anon public` key、`service_role` key。
3. 到 Project Settings → Data API，把「**Enable Data API**」關掉（table 存取不經過這層；Storage/Auth 不受影響）。
4. `DATABASE_URL` 用 Project Settings → Database → Connection string 的 **Session pooler**（見上方說明，注意 IPv6/IPv4 跟 prepared statements 的坑）。
5. 對雲端跑一次 `alembic upgrade head`（見下方「本機執行」）。

### 3. 本地 Supabase CLI stack（fallback，非預設）

```bash
npx supabase start
```

第一次會拉取多個映像檔，需要一點時間。完成後會印出 `API_URL`、`DB_URL`、`ANON_KEY`、`SERVICE_ROLE_KEY`，比照貼進 `.env.local` 再 `cp .env.local .env`。

```bash
npx supabase stop     # 關閉本地 stack（資料會保留）
npx supabase status   # 忘記剛才印出的值時，重新查詢
```

### 4. Google 登入（正式 demo 用，非必要不影響本地開發）

1. 在 Google Cloud Console 建立一個 OAuth 2.0 Client（Web application）。
2. Redirect URI 填 Supabase Dashboard（本地是 `npx supabase status` 印出的 Studio URL，雲端是 Project Dashboard）→ Authentication → Providers → Google 頁面上提供的 callback URL。
3. 把 Client ID / Secret 貼進該頁面並啟用。
4. **這組登入用的 OAuth 跟 Gmail 寄信是完全獨立的兩件事**，不要共用同一組 client／token。要真的寄信（`EMAIL_MODE=gmail`）需要另外在 Google Cloud Console 建**第二個** OAuth Client，scope 只要 `gmail.send`，Authorized redirect URI 要精確等於 `GMAIL_REDIRECT_URI`（例如 `http://localhost:8000/api/gmail/callback`），並在該 Google Cloud 專案啟用 Gmail API——這組設定跟這裡的登入 Google Provider 完全分開。不想處理這段的話，`EMAIL_MODE=mock` 是完整支援、不需要任何額外設定的預設值。

本地開發不想設定 Google OAuth 的話，直接用前端 Login 頁面的 Email/Password 表單即可，不受影響。

## 本機執行

```bash
docker compose build
docker compose up -d                                     # frontend, backend, mcp-server
docker compose run --rm backend alembic upgrade head    # 第一次啟動、或 schema 有更新時執行
docker compose logs -f
docker compose logs -f mcp-server                        # MCP server 自己的 log
```

- 前端：http://localhost:5173
- 後端 Swagger：http://localhost:8000/docs
- 健康檢查：http://localhost:8000/api/health
- MCP server（正式環境僅內網可連，這裡開 port 純粹方便本機除錯）：http://localhost:8001/mcp
- Supabase Studio（本地 CLI stack 才有）：http://localhost:54323
- Inbucket（本地 CLI stack 的假信箱，Email 驗證信會寄到這裡）：http://localhost:54324

```bash
docker compose down                       # frontend/backend/mcp-server，不影響 Supabase 資料（本地或雲端都一樣）
docker compose restart
docker compose restart mcp-server         # 改了 backend/app/mcp/ 底下的東西之後一定要做
npx supabase stop                         # 只有在用本地 CLI stack 時才需要（資料保留）
npx supabase stop --no-backup             # 連本地 Supabase 資料一起清掉，重新來過用
```

## 後端測試

測試會對 `.env` 目前指向的 Postgres（雲端或本地 CLI stack）下真的 query（用 SAVEPOINT 包住每個測試、結束就 rollback，不會留垃圾資料），所以該資料庫要能連得到。上傳文件相關的測試會 monkeypatch `rag_service.ingest_document` 成 no-op，不會真的呼叫 Voyage API。

```bash
docker compose exec backend python -m pytest -v    # 容器內執行，DATABASE_URL 已經是對的
```

或在 host 上用自己的 venv（若目前 `.env` 指向本地 CLI stack，需要把 `DATABASE_URL` 的 `host.docker.internal` 換成 `localhost`）：

```bash
cd backend
pip install -r requirements.txt
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:54322/postgres pytest -v
```

`get_current_user`（JWT/JWKS 驗證）在測試裡是用假使用者 override 掉的（見 `tests/conftest.py`）——測試在驗證我們自己寫的授權/CRUD/RAG/Agent/Email 邏輯，不是重新驗證 Supabase 的 token 簽發機制，那部分已經用真實登入手動測過。

RAG 檢索準確率評估（對真實 18 題題庫，跑真實 Voyage/Claude API）：

```bash
docker compose exec backend python -m scripts.eval_rag <project_id>
```

## 建立新的 schema migration

```bash
cd backend
alembic revision -m "描述這次異動"
# 編輯產生的檔案，寫 upgrade()/downgrade()
docker compose run --rm backend alembic upgrade head
```
