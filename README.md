# AI Engineering Assistant

工程文件 RAG + Vision + Agent + MCP + Gmail 展示專案。完整規格見 [`spec2.md`](spec2.md)，開發準則摘要見 [`CLAUDE.md`](CLAUDE.md)。

## 目前進度：Day 1 / 5（spec2.md 第 37 節）

- [x] Docker Compose（frontend + backend）+ 本地 Supabase CLI stack（Auth + Postgres + Storage）
- [x] FastAPI 骨架、`/api/health`
- [x] React + Vite + Tailwind 骨架
- [x] Supabase Auth 串接：Google 登入（正式 demo 用）+ Email/Password（本地開發用，不需外部設定）
- [x] 資料庫 schema：SQLAlchemy models + Alembic migration（`backend/alembic/versions/0001_initial_schema.py`）
- [x] Project CRUD + membership-only 授權，已用真實 Supabase Auth token 端對端驗證
- [x] 自動化測試：CRUD、owner membership、跨使用者隔離（403）、未帶 token（401）— `backend/tests/`
- [ ] PDF 上傳 / Voyage Embedding / pgvector RAG（Day 2）
- [ ] Claude Vision / Agent / MCP（Day 3）
- [ ] Email Draft / Preview / Confirm & Send / Gmail OAuth（Day 4）
- [ ] 打磨、Activity Log、Demo 排練（Day 5）

## 架構筆記

### 開發環境：本地 Supabase CLI，不等雲端

`supabase start`（見 `supabase/config.toml`）在本機 Docker 跑出一套跟雲端一模一樣的 Auth + Postgres + Storage。雲端 Supabase 專案曾因平台 incident 一度無法建立，改用本地 CLI 完全不受影響，且本地/雲端共用同一份 Alembic migration，之後要切換只需要換 `.env` 裡的幾個值，程式碼不用改。

### 切換 local / 雲端環境

實際生效的設定永遠是 `.env`（docker-compose 讀這個檔案）。`.env.local` 和 `.env.cloud` 是兩份完整備份，**不要在 `.env` 裡同時貼兩組值**（同一個變數名稱重複，dotenv 只認最後一次出現，會混出「DB 是本地、Auth 是雲端」這種壞掉的組合）。切換方式：

```bash
cp .env.local .env    # 切回本地開發（預設）
cp .env.cloud .env    # 切成打雲端 Supabase 專案
docker compose up -d --force-recreate    # 套用新的環境變數
```

兩份檔案都在 `.gitignore` 裡，不會進 git。

### 資料表存取不走 Supabase Data API

Frontend 只透過 Supabase Auth（GoTrue）登入；所有資料表（`projects`、`documents`、`document_chunks` 等）都是 backend 用 **SQLAlchemy 直連 Postgres**（不透過 PostgREST）。好處：Supabase 的「Enable Data API」可以直接關閉，攻擊面小一點；本地/雲端只差一個 `DATABASE_URL`。

### 使用者身份驗證：JWKS，不是共用密鑰

Supabase 目前用 **ES256 非對稱簽章**簽發使用者 session token（不是舊式的 HS256 + 共用 secret）。`app/core/auth.py` 用 `PyJWKClient` 向 `SUPABASE_URL` 的 `/auth/v1/.well-known/jwks.json` 動態抓公鑰驗證，本地 CLI 和雲端專案共用同一套邏輯，不需要另外設定或同步密鑰。

### 兩種登入方式

- **Google 登入**：正式 demo 用（spec2.md 的 demo flow 就是 Google 登入），需要在 Supabase 設定 Google provider。
- **Email/Password**：本地開發/測試用，前端 Login 頁面內建表單，不需要任何外部 OAuth 設定，`supabase/config.toml` 已關閉 email 驗證信要求（本地开发用途，圖方便）。

## 前置設定

### 1. 啟動本地 Supabase（第一次或重開機後）

```bash
npx supabase start
```

第一次會拉取多個映像檔，需要一點時間。完成後會印出 `API_URL`、`DB_URL`、`ANON_KEY`、`SERVICE_ROLE_KEY` 等值——這些已經寫進 `.env.example` 對應欄位的說明裡，第一次設定時比照命令輸出貼進 `.env` 即可（見下方「環境變數」）。

```bash
npx supabase stop     # 關閉本地 stack（資料會保留）
npx supabase status   # 忘記剛才印出的值時，重新查詢
```

### 2. 資料庫 schema

```bash
docker compose run --rm backend alembic upgrade head
```

### 3. Google 登入（正式 demo 用，非必要不影響本地開發）

1. 在 Google Cloud Console 建立一個 OAuth 2.0 Client（Web application）。
2. Redirect URI 填 Supabase Dashboard（本地是 `npx supabase status` 印出的 Studio URL，雲端是 Project Dashboard）→ Authentication → Providers → Google 頁面上提供的 callback URL。
3. 把 Client ID / Secret 貼進該頁面並啟用。
4. **這組登入用的 OAuth 跟 Gmail 寄信是完全獨立的兩件事**，不要共用同一組 client／token（詳見 `spec2.md` 第 26 節）。Gmail 寄信的 OAuth 設定留到 Day 4 再做，目前先用 `EMAIL_MODE=mock`。

本地開發不想設定 Google OAuth 的話，直接用前端 Login 頁面的 Email/Password 表單即可，不受影響。

### 4. 雲端 Supabase 專案（Auth + Storage 正式環境；Day 2 起會需要，Day 1 可以先跳過）

1. 到 [supabase.com](https://supabase.com) 建立新專案。
2. 到 Project Settings → API，複製 `Project URL`、`anon public` key、`service_role` key。
3. 到 Project Settings → Data API，把「**Enable Data API**」關掉（table 存取不經過這層；Storage/Auth 不受影響）。
4. 把 `.env` 的 `DATABASE_URL`、`SUPABASE_URL`、`SUPABASE_ANON_KEY`、`SUPABASE_SERVICE_ROLE_KEY`、`VITE_SUPABASE_URL`、`VITE_SUPABASE_ANON_KEY` 換成雲端的值。`DATABASE_URL` 要用 Project Settings → Database → Connection string 的 **Session pooler**（不是 Direct connection，也不是 Transaction pooler）——Supabase 現在的直連 host 只有 IPv6，Docker 容器預設連不上會出現 `Network is unreachable`；Session pooler 支援 IPv4，且跟直連一樣是 session 模式（支援 prepared statements 等），適合 FastAPI 這種長連線 process。注意 pooler 連線的使用者名稱要帶上 project ref（`postgres.<ref>`，不是單純 `postgres`）。
5. 對雲端跑一次 `alembic upgrade head`，schema 完全一致。

### 5. 環境變數

```bash
cp .env.example .env
```

依照 `npx supabase start` 印出的值填入 `.env`（本地開發用，雲端切換見上方第 4 點）。

## 本機執行

```bash
npx supabase start                                      # 第一次或重開機後
docker compose build
docker compose up -d
docker compose run --rm backend alembic upgrade head    # 第一次啟動、或 schema 有更新時執行
docker compose logs -f
```

- 前端：http://localhost:5173
- 後端 Swagger：http://localhost:8000/docs
- 健康檢查：http://localhost:8000/api/health
- Supabase Studio（本地管理介面，可以看 Auth 使用者、資料表）：http://localhost:54323
- Inbucket（本地假信箱，Email 驗證信會寄到這裡）：http://localhost:54324

```bash
docker compose down       # frontend/backend 容器，不影響本地 Supabase 資料
docker compose restart
npx supabase stop         # 關閉本地 Supabase（資料保留）
npx supabase stop --no-backup   # 連本地 Supabase 資料一起清掉，重新來過用
```

## 後端測試

測試會對真的 Postgres 下 query（用 SAVEPOINT 包住每個測試、結束就 rollback，不會留垃圾資料），所以本地 Supabase（`npx supabase start`）要先跑著。

```bash
docker compose exec backend python -m pytest -v    # 容器內執行，DATABASE_URL 已經是對的
```

或在 host 上用自己的 venv（需要把 `DATABASE_URL` 的 `host.docker.internal` 換成 `localhost`）：

```bash
cd backend
pip install -r requirements.txt
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:54322/postgres pytest -v
```

`get_current_user`（JWT/JWKS 驗證）在測試裡是用假使用者 override 掉的（見 `tests/conftest.py`）——測試在驗證我們自己寫的 Project CRUD／授權邏輯，不是重新驗證 Supabase 的 token 簽發機制，那部分已經用真實登入手動測過。

## 建立新的 schema migration

```bash
cd backend
alembic revision -m "描述這次異動"
# 編輯產生的檔案，寫 upgrade()/downgrade()
docker compose run --rm backend alembic upgrade head
```
