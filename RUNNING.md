NexaBiz ERP — Local Run Instructions

Overview

This document explains how to run the backend and frontend locally for development and testing.

Prerequisites

- Python 3.10+ (or compatible)
- Node.js (LTS) and Yarn (v1) installed
- MongoDB running locally (or set `MONGO_URL` to a reachable MongoDB)

Backend (Windows)

1. Create and activate a virtualenv:

```powershell
cd D:\Project\RD-ERP-main\backend
python -m venv .venv
.venv\Scripts\Activate.ps1
```

2. Install Python dependencies:

```powershell
pip install -r requirements.txt
```

3. Create an env file or set env vars. Example `.env` values:

```
MONGO_URL=mongodb://127.0.0.1:27017
DB_NAME=nexabiz
JWT_SECRET=replace-with-a-random-secret-at-least-32-characters
OWNER_EMAIL=owner@example.com
OWNER_PASSWORD=change-this-demo-password
OWNER_NAME=Business Owner
ATTACHMENTS_DIR=./data/attachments
SKIP_DEMO_SEED=1  # optional: skip demo data seeding on startup
DEMO_MODE=false
MAX_ATTACHMENT_SIZE_MB=10
```

The backend pings MongoDB during startup. For an Atlas URL, invalid credentials or
network access configuration will stop startup instead of silently using mock data.
In MongoDB Atlas, add the development machine IP under Network Access and URL-encode
reserved password characters such as `@`, `:`, `/`, and `#`.

For deployment, configure `MONGO_URL`, `DB_NAME`, `JWT_SECRET`, `OWNER_EMAIL`,
`OWNER_PASSWORD`, and `SKIP_DEMO_SEED` as environment variables in the hosting
platform. Do not commit `backend/.env`; deployment platforms do not receive ignored
local files from GitHub. Once configured, every deployment uses the same Atlas
database and existing data remains available.

Note: For local dev you can set `SKIP_DEMO_SEED=1` to avoid seeding if Mongo is not available.

4. Start the backend:

```powershell
python -m uvicorn server:app --reload --host 0.0.0.0 --port 8000
```

Verify health:

```powershell
curl http://127.0.0.1:8000/api/
# expected: {"app":"NexaBiz ERP","status":"ok"}
```

Untuk memverifikasi bahwa backend benar-benar memakai Atlas, jalankan dari folder `backend`:

```powershell
python -c "import server; print('Atlas:', not server.use_mock)"
```

Hasil yang benar adalah `Atlas: True`. Jika URI memakai `mongodb+srv` tetapi username,
password, atau Network Access salah, backend akan gagal start dan menampilkan error
autentikasi/koneksi.

Frontend

1. Install dependencies (only once or when package.json changes):

```bash
cd D:/Project/RD-ERP-main/frontend
yarn install
```

2. Start the dev server (pointing to local backend):

```bash
REACT_APP_BACKEND_URL=http://localhost:8000 yarn start
```

- If port 3000 is already in use, CRA will prompt to run on another port (e.g., 3001). Accept to continue.
- The app will open in the browser at the selected port.

Notes and troubleshooting

- If you remove or change private packages, ensure `requirements.txt` and `package.json` reflect the correct set for your environment.
- `.env` files should not be committed. Use `.env.example` as a template for collaborators.
- To force a port when starting CRA, set `PORT=3001` in the environment before `yarn start`.

Example single-line startup (PowerShell):

```powershell
# Backend
cd D:\Project\RD-ERP-main\backend; .venv\Scripts\Activate.ps1; python -m uvicorn server:app --reload --host 0.0.0.0 --port 8000

# Frontend (new shell)
cd D:\Project\RD-ERP-main\frontend; $env:REACT_APP_BACKEND_URL='http://localhost:8000'; yarn start
```

## Docker self-hosted deployment

This repository includes a production-style Docker Compose stack:

- MongoDB 7 with a persistent named volume
- FastAPI backend with persistent attachment storage
- React production build served by Nginx
- Same-origin `/api` reverse proxy
- Container health checks and startup ordering

From the repository root:

```powershell
Copy-Item .env.docker.example .env
# Edit .env and set JWT_SECRET and OWNER_PASSWORD
.\scripts\install.ps1
```

Open `http://localhost` after the health checks complete. To stop the services:

```

The Docker frontend uses the same-origin `/api` proxy automatically. Do not set
`REACT_APP_BACKEND_URL` to `http://localhost:8000` for the Docker deployment; that
address would point to the buyer's browser machine rather than the backend container.powershell
.\scripts\stop.ps1
```

To remove containers but keep data, use `docker compose down`. Do not use
`docker compose down -v` unless you intentionally want to delete the MongoDB and
attachment volumes. Back up first with the scripts below.

## Production security checklist

- Set `ENVIRONMENT=production`, `DEMO_MODE=false`, and `SKIP_DEMO_SEED=1`.
- Generate a unique `JWT_SECRET` of at least 32 random characters.
- Use a restricted MongoDB user and never expose MongoDB directly to the internet.
- Set `CORS_ORIGINS` to the exact HTTPS frontend origin; do not use `*`.
- Put the application behind HTTPS and a reverse proxy.
- Review attachment size/type limits and protect the attachment directory.
- Schedule database and attachment backups, then perform a restore test.
- Rotate credentials and dependencies regularly.

## Micro business quick start

For daily operations, use **Quick Sale** instead of the full Sales Order form. It
records the product, quantity, payment method, and stock movement in one short flow.
Use **Receipt** from the Sales list to print a customer receipt. The Dashboard shows
today's cash in, cash out, net cash, and total account balance. The Light CRM page
links customer phone numbers to WhatsApp and shows recent order history.

## Backup and restore

Install MongoDB Database Tools, set `MONGO_URL`, `DB_NAME`, and `ATTACHMENTS_DIR`,
then run from the repository root:

```powershell
.\scripts\backup.ps1
.\scripts\restore.ps1 -Backup .\backups\20260918-120000
```

Restore replaces the selected database. Stop application traffic first and verify the
backup folder before restoring.
