# AI Engineering Assistant

工程文件 RAG + Vision + Agent + MCP + Gmail 展示專案。開發準則與逐日實作細節見 [`CLAUDE.md`](CLAUDE.md)。

## 目前進度：Day 5 / 5 完成（spec2.md 第 37 節，Gmail OAuth 除外）

- [x] **Day 1** — Docker Compose（frontend + backend）、Supabase Auth（Google + Email/Password）、Project CRUD、`project_members` membership-only 授權，已用真實 Supabase Auth token 端對端驗證
- [x] **Day 2** — PDF 上傳 → Supabase Storage → PyMuPDF 抽取 → 固定大小分塊 → Voyage Embedding → pgvector → Claude 生成答案（含來源文件＋頁碼引用），已對真實 T3 工程 PDF 端對端驗證
- [x] **Day 3** — Claude Vision、Agent 工具選擇迴圈、MCP server（`search_documents`、`send_email`，獨立容器 `mcp-server`，只在 compose 內網可連）
- [x] **Day 4** — Email 草稿生成（Agent 的 `draft_email` 工具）、Preview 卡片、Confirm & Send、Mock Email（`EMAIL_MODE=mock`），已用 Playwright 真實瀏覽器跑過完整流程
- [x] **Day 5** — Activity Log（新增 `activity_logs` 表，11 個工作流程節點都會記錄，見 Activity 分頁）、RAG Evaluation（`backend/scripts/eval_rag.py`，對真實 18 題題庫跑出 **94% 檢索準確率**）、error handling 補強（chat.py 例外處理、PDF 內容驗證、Email 格式驗證）
- [ ] **Gmail OAuth**（spec2.md §37 風險簡化原則明確允許不做——`EMAIL_MODE=mock` 是正式接受的 fallback，不是未完成事項；`GMAIL_CLIENT_ID` 等變數仍保留但未使用）

自動化測試：`backend/tests/`，56 個測試全過（`docker compose exec backend python -m pytest -v`）。

## 架構筆記

### 三個容器：frontend / backend / mcp-server

`docker compose up -d` 會啟動三個容器。`mcp-server`（Day 3 加入）是從 `backend/` 同一份 build context 另外建出的第二個 image（`backend/Dockerfile.mcp`），與 `backend` 共用 `requirements.txt`、直接 import `app.services`/`app.models`，不是獨立的頂層套件。它只在 compose 內網用 Streamable HTTP 提供服務（`mcp-server:8001`），host 上開的 `8001` port 純粹方便本機除錯，正式流程裡 frontend/瀏覽器永遠連不到它——這是 spec2.md 第 21 節「MCP 不可繞過 Project Authorization」的結構性保證：MCP server 本身沒有 JWT/使用者context，能檢查權限的只有已經驗證過身份的 backend。

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

- **Google 登入**：正式 demo 用（spec2.md 的 demo flow 就是 Google 登入），需要在 Supabase 設定 Google provider。
- **Email/Password**：本地開發/測試用，前端 Login 頁面內建表單，不需要任何外部 OAuth 設定。

### Email 寄送：兩組完全獨立的 OAuth，且 Gmail 那組尚未實作

Supabase Auth 的 Google 登入（scope: openid/email/profile）跟 Gmail 寄信（scope: `gmail.send`）是**兩個獨立的 OAuth 授權**，不要假設登入的 token 可以拿來寄信（詳見 spec2.md 第 26 節）。目前只有 `EMAIL_MODE=mock` 這條路可用：`app/mcp/tools/send_email.py` 會記錄 `[MOCK EMAIL] to=... subject=...`（不記完整內文）並回傳 `status: "sent"`；任何非 `mock` 的 `EMAIL_MODE` 會乾淨地回傳 `status: "failed"`，因為 Gmail client 尚未實作，`GMAIL_CLIENT_ID`/`GMAIL_CLIENT_SECRET`/`GMAIL_REDIRECT_URI` 目前只是預留變數。

## 前置設定

### 1. 環境變數

```bash
cp .env.example .env
```

`.env.example` 裡每個變數都有註解說明來源。目前預設要打雲端 Supabase 專案，需要填：

- `DATABASE_URL`、`SUPABASE_URL`、`SUPABASE_ANON_KEY`、`SUPABASE_SERVICE_ROLE_KEY`、`VITE_SUPABASE_URL`、`VITE_SUPABASE_ANON_KEY`（見下方「2. 雲端 Supabase 專案」）
- `ANTHROPIC_API_KEY`（Claude — RAG 生成答案、Vision、Agent、Email 草稿都要用）
- `VOYAGE_API_KEY`（Voyage AI — PDF 分塊後的 embedding，Day 2 起必填，否則上傳 PDF 會索引失敗）
- `EMAIL_MODE=mock`（目前唯一可用的模式）

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
4. **這組登入用的 OAuth 跟 Gmail 寄信是完全獨立的兩件事**，不要共用同一組 client／token。Gmail 寄信的 OAuth 尚未實作，目前用 `EMAIL_MODE=mock`。

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

## 建立新的 schema migration

```bash
cd backend
alembic revision -m "描述這次異動"
# 編輯產生的檔案，寫 upgrade()/downgrade()
docker compose run --rm backend alembic upgrade head
```
