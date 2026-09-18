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
# MongoDB Atlas (replace <db_password>; URL-encode special characters)
MONGO_URL=mongodb+srv://rdmfr59_db_user:<db_password>@cluster0.zygezd2.mongodb.net/?retryWrites=true&w=majority
DB_NAME=rdcloth
JWT_SECRET=change-me-to-a-secure-random-value
SKIP_DEMO_SEED=1  # optional: skip demo data seeding on startup
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

If you want, I can also add a small `docker-compose.yml` later to simplify local setup.
