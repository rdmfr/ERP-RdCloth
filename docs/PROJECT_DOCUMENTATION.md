# RdCloth ERP Documentation

RdCloth ERP adalah aplikasi web untuk operasional bisnis apparel dan konveksi. Aplikasi mencakup katalog produk, stok bahan baku, produksi, pembelian, penjualan, marketplace import, keuangan, laporan, dan kalkulator bisnis.

## Quick Start

### Requirements

- Python 3.10 atau lebih baru
- Node.js LTS
- Yarn 1.x
- MongoDB lokal atau MongoDB yang dapat dijangkau melalui `MONGO_URL`

Backend memiliki fallback `mongomock_motor` untuk development lokal ketika MongoDB tidak tersedia. Untuk data yang persisten, gunakan MongoDB.

### Backend

Windows PowerShell:

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m uvicorn server:app --reload --host 127.0.0.1 --port 8000
```

Linux/macOS:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn server:app --reload --host 127.0.0.1 --port 8000
```

Health check:

```text
http://127.0.0.1:8000/api/
```

### Frontend

```bash
cd frontend
yarn install
REACT_APP_BACKEND_URL=http://localhost:8000 yarn start
```

Frontend tersedia di `http://localhost:3000`.

Pada Windows PowerShell, gunakan:

```powershell
$env:REACT_APP_BACKEND_URL = "http://localhost:8000"
yarn start
```

Panduan run yang lebih singkat tersedia di [RUNNING.md](../RUNNING.md).

## Environment Variables

Backend membaca konfigurasi berikut:

| Variable | Default | Keterangan |
| --- | --- | --- |
| `MONGO_URL` | `mongodb://localhost:27017` | Connection string MongoDB |
| `DB_NAME` | `rdcloth` | Nama database |
| `JWT_SECRET` | development fallback | Secret untuk token JWT; wajib diganti di production |
| `OWNER_EMAIL` | `rddev@gmail.com` | Email owner saat seed |
| `OWNER_PASSWORD` | `rdcloth2026` | Password owner saat seed |
| `SKIP_DEMO_SEED` | kosong | Isi `1` untuk melewati seed demo |

Jangan commit file `.env` atau secret production.

## Demo Accounts

| Role | Email | Password | Fokus akses |
| --- | --- | --- | --- |
| Owner | `rddev@gmail.com` | `rdcloth2026` | Semua modul dan konfigurasi |
| Admin | `admin@rdcloth.id` | `admin123` | Sales, products, inventory, customers, suppliers, materials |
| Production | `production@rdcloth.id` | `production123` | Production, inventory, products, materials |
| Finance | `finance@rdcloth.id` | `finance123` | Finance, reports, purchasing, sales, assets |

Password di atas hanya untuk development/demo. Ganti atau nonaktifkan sebelum deployment.

## Modules and Workflows

### Dashboard

Menampilkan KPI revenue, order, HPP/COGS, gross profit, biaya marketplace, biaya operasional, net profit, cash balance, nilai inventory, dan low-stock alert. Tersedia grafik revenue/profit, channel sales, dan produk terlaris.

### Products and Materials

- Products menyimpan SKU produk, brand, kategori, harga, status, dan variant ukuran/warna.
- Materials menyimpan bahan baku, unit, stok, biaya, minimum stock, dan supplier.
- Inventory mencatat adjustment stok produk/bahan dan histori movement.

### Purchasing

1. Buat Purchase Order dan pilih supplier.
2. Tambahkan material, jumlah, biaya unit, diskon, shipping, dan tax.
3. Gunakan `Receive` untuk menambah stok material.
4. Sistem menghitung weighted average cost untuk material yang diterima.

### Production

1. Buat production order untuk produk dan variant.
2. Pilih atau susun BOM bahan baku.
3. Masukkan quantity passed dan rejected saat produksi selesai.
4. Sistem mengurangi bahan, menambah stok barang jadi, dan mencatat movement.

### Sales

1. Buat sales order dan pilih customer atau Guest.
2. Pilih channel, produk, variant, quantity, dan harga.
3. Masukkan diskon, voucher, shipping, biaya marketplace, dan advertising bila diperlukan.
4. Sistem memvalidasi stok, mengurangi variant stock, menghitung COGS dan profit, lalu mencatat pemasukan jika status pembayaran `paid`.
5. Order yang dibatalkan mengembalikan stok dan membuat transaksi refund.

### Marketplace Import

Export order dari Shopee Seller Center atau TikTok Shop Center sebagai CSV, lalu paste ke halaman Import Orders. Kolom wajib:

```text
variant_sku, quantity, selling_price
```

Kolom tambahan yang didukung adalah `order_number`, `date`, `customer_name`, `sales_channel`, `discount`, `shipping`, `marketplace_fee`, dan `advertising_cost`.

Gunakan Preview untuk memeriksa kecocokan SKU sebelum melakukan import.

### Finance and Reports

Finance mengelola account, transaksi manual, dan expenses. Sales yang paid, pembelian paid, modal awal, withdrawal, dan expense dapat memengaruhi saldo account.

Reports menyediakan:

- Profit and Loss berdasarkan rentang tanggal
- Sales CSV
- Inventory CSV
- Profit and Loss CSV
- Print/PDF melalui dialog print browser

### Pricing and BEP

- HPP Calculator menghitung komponen biaya, fee marketplace, advertising, margin, dan health margin.
- Pricing Simulator membandingkan beberapa harga jual.
- BEP menghitung contribution margin, unit break-even, dan revenue break-even berdasarkan fixed cost, variable cost, dan selling price.

### Settings

Owner dapat mengelola kategori, marketplace, expense category, user, dan audit log. Settings juga menyediakan theme toggle dan Setup Wizard untuk business profile, currency, modal awal, marketplace, produk, dan opening inventory.

## API Overview

API menggunakan prefix `/api` dan autentikasi Bearer token atau cookie `access_token`.

| Area | Endpoint utama |
| --- | --- |
| Auth | `POST /api/auth/login`, `GET /api/auth/me`, `POST /api/auth/logout` |
| Dashboard | `GET /api/dashboard/kpi`, `GET /api/dashboard/charts` |
| Master data | `/api/products`, `/api/materials`, `/api/suppliers`, `/api/customers`, `/api/assets` |
| Inventory | `GET /api/inventory/movements`, `POST /api/inventory/products/adjust`, `POST /api/inventory/materials/adjust` |
| Purchasing | `/api/purchase_orders`, `POST /api/purchase_orders/{id}/receive` |
| Production | `/api/production_orders`, `POST /api/production_orders/{id}/complete` |
| Sales | `/api/sales_orders`, `POST /api/sales_orders/{id}/cancel` |
| Import | `POST /api/marketplace/import` |
| Finance | `/api/accounts`, `/api/financial_transactions`, `/api/expenses` |
| Reports | `GET /api/reports/profit_loss`, `/api/reports/export/*` |
| Business tools | `POST /api/hpp/calculate`, `POST /api/hpp/simulate`, `POST /api/bep/calculate` |
| Administration | `GET /api/users`, `POST /api/users`, `GET /api/audit_logs` |

Swagger/OpenAPI tersedia di `http://127.0.0.1:8000/docs` saat backend berjalan.

## Project Structure

```text
RD-ERP-main/
├── backend/
│   ├── server.py             # FastAPI app, API route, auth, seed
│   ├── requirements.txt      # Python dependencies
│   └── pytest.ini            # Pytest configuration
├── frontend/
│   ├── src/App.js            # React routes
│   ├── src/components/       # Layout and reusable UI
│   ├── src/pages/            # ERP modules
│   └── src/lib/              # API client and export helpers
├── tests/                    # Test package
├── RUNNING.md                # Local run guide
└── docs/                     # Project documentation
```

## Testing and Quality Checks

Backend tests:

```bash
cd backend
pytest
```

Frontend production build:

```bash
cd frontend
yarn build
```

Dependency validation:

```bash
python -m pip check
```

## Current Limitations

The current demo release still needs follow-up work before production use:

- Global search and notification buttons are present in the UI but not yet connected to a full workflow.
- Sales, Purchase Order, and Production Order have limited editing capabilities after creation.
- Numeric input and stock transition validation should be strengthened on both frontend and backend.
- BEP should show an explicit warning when selling price is not greater than variable cost.
- Business profile editing and full user lifecycle management are still limited.
- Demo credentials and development JWT defaults must be replaced in a real deployment.

## Deployment Notes

For production, use a managed MongoDB instance, a strong random `JWT_SECRET`, HTTPS, restricted CORS, separate frontend/backend environment variables, and a process manager for Uvicorn. Disable demo seeding with `SKIP_DEMO_SEED=1` after the initial setup.
