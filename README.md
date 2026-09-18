# NexaBiz ERP

Self-hosted ERP template untuk UMKM dan small businesses di Indonesia maupun pasar global. NexaBiz membantu mengelola produk, inventory, purchasing, production, sales, marketplace, finance, reporting, dan pricing dalam satu workspace yang dapat dikonfigurasi per bisnis.

## Fitur Utama

- **Dashboard & Analisis**: Ringkasan KPI, grafik pendapatan, produk terlaris, dan pengeluaran operasional.
- **Manajemen Pengguna & Peran**: Akses berbasis peran (RBAC) untuk Owner, Admin, Tim Produksi, dan Tim Keuangan.
- **Manajemen Produk & Stok**: Katalog produk, varian, SKU, dan alert level stok minimum.
- **Inventaris & Bahan Baku**: Pencatatan bahan baku (kain, benang, aksesoris) beserta log mutasi stok otomatis.
- **Perintah Produksi (Production Orders)**: Tracking status produksi dari pemotongan hingga barang jadi, serta pemotongan otomatis stok bahan baku.
- **Pembelian (Purchase Orders)**: Order pembelian bahan baku ke supplier dan konfirmasi penerimaan stok.
- **Pesanan Penjualan (Sales Orders)**: Pencatatan transaksi penjualan, pengiriman barang, dan kalkulasi piutang.
- **Keuangan & Transaksi**: Pencatatan arus kas (pemasukan & pengeluaran) dan jurnal aktivitas operasional.

---

## Arsitektur & Teknologi

- **Backend**: Python 3.10+ / FastAPI, Uvicorn, PyJWT, Bcrypt
- **Database**: MongoDB (dilengkapi `mongomock_motor` fallback untuk pengujian lokal tanpa perlu instalasi MongoDB lokal)
- **Frontend**: React 19, Tailwind CSS, Radix UI / Shadcn UI, Recharts, Axios

---

## Cara Menjalankan Aplikasi (Lokal)

Dokumentasi proyek lengkap, alur kerja setiap modul, ringkasan API, role, environment variables, dan batasan versi demo tersedia di [docs/PROJECT_DOCUMENTATION.md](docs/PROJECT_DOCUMENTATION.md).

### 1. Backend Setup

```bash
cd backend

# Buat virtual environment
python -m venv .venv

# Aktivasi virtual environment
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# Linux/macOS:
source .venv/bin/activate

# Install dependency
pip install -r requirements.txt

# Jalankan backend server
python -m uvicorn server:app --reload --host 127.0.0.1 --port 8000
```

Backend API akan berjalan di `http://127.0.0.1:8000/api/`.

---

### 2. Frontend Setup

```bash
cd frontend

# Install dependency
yarn install

# Jalankan frontend server
REACT_APP_BACKEND_URL=http://localhost:8000 yarn start
```

Aplikasi frontend akan terbuka di `http://localhost:3000`.

---

## Akun Demo Bawaan

Sistem sudah dilengkapi dengan demo seed data dan beberapa akun pengguna untuk pengujian role:

| Peran (Role) | Email | Password |
|---|---|---|
| **Owner** | `rddev@gmail.com` | `rdcloth2026` |
| **Admin** | `admin@rdcloth.id` | `admin123` |
| **Production** | `production@rdcloth.id` | `production123` |
| **Finance** | `finance@rdcloth.id` | `finance123` |

---

## Struktur Folder Project

```text
RD-ERP-main/
├── backend/
│   ├── server.py             # FastAPI entrypoint & REST API endpoints
│   ├── requirements.txt      # Dependency Python
│   └── .env.example          # Contoh variabel lingkungan
├── frontend/
│   ├── src/                  # Source code React frontend
│   │   ├── components/       # Reusable UI components & layout
│   │   ├── pages/            # Halaman modul ERP
│   │   └── hooks/            # Custom hooks
│   └── package.json
└── RUNNING.md                # Panduan teknis eksekusi lokal
```

## Lisensi

Internal / Private Repository.
