# Migrasi Database RD-ERP ke PostgreSQL & PgBouncer

Rencana komprehensif untuk memigrasikan basis data **RD-ERP** dari **MongoDB (NoSQL)** ke **PostgreSQL 16** dengan **PgBouncer** sebagai connection pooler berperforma tinggi (*transaction pooling mode*), sekaligus memastikan autentikasi login dan seluruh endpoint API tetap kompatibel dengan frontend React.

---

## User Review Required

> [!IMPORTANT]
> **Skala Perubahan: Arsitektur Backend & Basis Data**
> Saat ini backend (`backend/server.py`) memiliki ~3.700 baris kode yang menggunakan driver MongoDB (`motor`). Migrasi ke PostgreSQL akan memodernisasi backend menggunakan **SQLAlchemy 2.0 (Async) + asyncpg**.
> 
> * **Zero-Downtime / Fresh Setup**: Karena Anda mengonfirmasi ERP ini *belum jadi* (tahap pengembangan), migrasi akan dilakukan secara bersih (*clean relational schema*) tanpa memerlukan pipeline ETL data legacy yang rumit.
> * **Akun Default & Demo**: Akun owner utama akan otomatis dibuat pada saat startup (`rddev@gmail.com` / `rdcloth2026`) beserta akun demo (`admin@example.com`, `finance@example.com`, `production@example.com`), sehingga tombol login demo di frontend langsung berfungsi normal.

> [!WARNING]
> **Catatan Teknis PgBouncer (Transaction Mode)**
> Saat menggunakan PgBouncer dengan mode `transaction`, koneksi async Python (`asyncpg`) perlu menonaktifkan cache prepared statement (`prepared_statement_cache_size = 0`) untuk menghindari tabrakan query ID antar sesi connection pool. Pengaturan ini sudah diperhitungkan dalam konfigurasi engine SQLAlchemy.

---

## Proposed Architecture

```
                      ┌──────────────────────┐
                      │   Frontend (React)   │
                      │       Port 80        │
                      └──────────┬───────────┘
                                 │ HTTP API /api
                      ┌──────────▼───────────┐
                      │   Backend (FastAPI)  │
                      │  SQLAlchemy + asyncpg│
                      └──────────┬───────────┘
                                 │ Port 6432
                      ┌──────────▼───────────┐
                      │      PgBouncer       │
                      │  (Transaction Pool)  │
                      └──────────┬───────────┘
                                 │ Port 5432
                      ┌──────────▼───────────┐
                      │    PostgreSQL 16     │
                      │   Relational + JSONB │
                      └──────────────────────┘
```

---

## Proposed Changes

### 1. Infrastruktur & Docker Compose

#### [MODIFY] [docker-compose.yml](file:///d:/Project/RD-ERP-main/docker-compose.yml)
* Mengganti service `mongo` dengan:
  * `postgres`: Image `postgres:16-alpine`, volume `pg_data`, healthcheck `pg_isready`.
  * `pgbouncer`: Image `edoburu/pgbouncer:v1.22.0`, mode `transaction`, port `6432`, terhubung ke `postgres:5432`.
* Memperbarui service `backend`:
  * Menghubungkan variabel `DATABASE_URL` ke `postgresql+asyncpg://postgres:${POSTGRES_PASSWORD}@pgbouncer:6432/${DB_NAME}`.
  * Menyediakan `DIRECT_DATABASE_URL` langsung ke `postgres:5432` (berguna untuk DDL / migrasi).
  * Menyesuaikan environment `OWNER_EMAIL=rddev@gmail.com` dan `OWNER_PASSWORD=rdcloth2026`.

#### [MODIFY] [backend/.env](file:///d:/Project/RD-ERP-main/backend/.env) & [.env](file:///d:/Project/RD-ERP-main/.env)
* Mengubah konfigurasi koneksi:
  * `POSTGRES_HOST=pgbouncer` (atau `localhost` jika dijalankan lokal tanpa docker)
  * `POSTGRES_PORT=6432`
  * `POSTGRES_USER=postgres`
  * `POSTGRES_PASSWORD=postgres123`
  * `POSTGRES_DB=rdcloth`
  * `DATABASE_URL=postgresql+asyncpg://postgres:postgres123@127.0.0.1:6432/rdcloth`

#### [MODIFY] [backend/requirements.txt](file:///d:/Project/RD-ERP-main/backend/requirements.txt)
* Menghapus dependensi `motor`, `pymongo`, `mongomock-motor`.
* Menambahkan:
  * `sqlalchemy[asyncio]>=2.0.28`
  * `asyncpg>=0.29.0`
  * `alembic>=1.13.1`
  * `psycopg2-binary>=2.9.9` (opsional untuk helper scripts/sync tools)

---

### 2. Lapisan Database & Model Relasional

Membagi kode database menjadi struktur modular agar rapi dan mudah di-maintain:

#### [NEW] [backend/database.py](file:///d:/Project/RD-ERP-main/backend/database.py)
* Konfigurasi `create_async_engine` dengan:
  * `connect_args={"prepared_statement_cache_size": 0}` (wajib untuk PgBouncer transaction mode).
  * `async_sessionmaker` untuk session dependency FastAPI (`get_db`).
  * Base class deklaratif `Base = declarative_base()`.

#### [NEW] [backend/models.py](file:///d:/Project/RD-ERP-main/backend/models.py)
Memetakan 28 koleksi MongoDB menjadi tabel PostgreSQL relasional dengan tipe data yang tepat (UUID/String PK, Foreign Keys, Index, dan `JSONB` untuk payload dinamis):
* **Auth & Keamanan**:
  * `users` (id, email UNIQUE, password_hash, name, role, status, created_at, updated_at)
  * `login_attempts` (id, email, ip, success, timestamp)
  * `audit_logs` (id, user_id, user_email, action, entity, entity_id, old_value JSONB, new_value JSONB, created_at)
  * `settings_kv` (key PK, value JSONB, updated_at)
  * `attachments` (id, entity_type, entity_id, original_name, stored_name, content_type, size, uploaded_by, created_at)
* **Master Data & Inventaris**:
  * `categories` (id, name, description, created_at)
  * `products` (id, name, sku, category_id, base_price, description, variants JSONB, images JSONB, status, created_at, updated_at)
  * `materials` (id, code, name, category, unit, stock, min_stock, cost_price, created_at, updated_at)
  * `suppliers` (id, name, contact_person, phone, email, address, created_at)
  * `customers` (id, name, phone, email, address, notes, created_at)
  * `inventory_movements` (id, item_id, item_type, type, qty, balance_after, ref_type, ref_id, notes, created_at)
* **Transaksi Penjualan & Pembelian**:
  * `sales_orders` (id, order_number UNIQUE, customer_id, items JSONB, total_amount, discount, tax, payment_status, fulfillment_status, channel, created_at, updated_at)
  * `invoices` (id, invoice_number UNIQUE, order_id, customer_id, amount, status, due_date, items JSONB, created_at)
  * `returns` (id, return_number, order_id, items JSONB, reason, status, refund_amount, created_at)
  * `purchase_orders` (id, po_number UNIQUE, supplier_id, items JSONB, total_amount, status, payment_status, created_at, updated_at)
  * `bills` (id, bill_number, po_id, supplier_id, amount, status, due_date, items JSONB, created_at)
* **Manufaktur & Produksi**:
  * `boms` (id, product_id, variant_id, materials JSONB, notes, created_at)
  * `production_orders` (id, prod_number, product_id, quantity, status, stage, assigned_to, start_date, due_date, notes, created_at, updated_at)
* **Akuntansi & Finansial**:
  * `accounts` / COA (id, code UNIQUE, name, category, type, balance, is_system, created_at)
  * `journal_entries` (id, entry_number, date, description, ref_type, ref_id, lines JSONB, total_debit, total_credit, created_at)
  * `financial_transactions` (id, type, amount, account_id, description, ref_type, ref_id, date, created_at)
  * `expenses` & `expense_categories` (id, date, category, description, amount, account_id, created_at)
  * `assets` (id, name, purchase_price, purchase_date, useful_life_years, residual_value, created_at)
  * `reconciliations` (id, account_id, statement_date, statement_balance, book_balance, diff, items JSONB, created_at)
* **Marketplace & CRM**:
  * `marketplaces` (id, name, admin_fee_pct, service_fee_pct, payment_fee_pct, handling_fee, commission_cap, return_fee_cap, created_at)
  * `marketplace_settlements` (id, marketplace_id, settlement_date, net_amount, raw_data JSONB, created_at)
  * `crm_activities` (id, customer_id, type, notes, date, created_at)

---

### 3. Logika Backend & Refactoring

#### [MODIFY] [backend/server.py](file:///d:/Project/RD-ERP-main/backend/server.py)
* Mengganti inisialisasi Mongo dengan SQLAlchemy Async Session.
* Memperbarui helper transaksi:
  ```python
  @asynccontextmanager
  async def db_transaction():
      async with async_session_factory() as session:
          async with session.begin():
              yield session
  ```
* Mengonversi fungsi autentikasi:
  * `check_login_rate_limit()`: Query tabel `login_attempts` via SQLAlchemy.
  * `login()`: Query tabel `users` via `select(User).where(func.lower(User.email) == email)`.
  * `seed_all()` & `ensure_coa_seeded()`: Insert default COA dan akun admin `rddev@gmail.com` ke PostgreSQL saat aplikasi start.
* Mengonversi endpoint CRUD di seluruh modul (Master Data, Orders, Accounting, Inventory) agar menggunakan SQLAlchemy async query, menjaga response format JSON persis sama seperti yang diharapkan React.

---

### 4. Frontend & Koneksi API

#### [MODIFY] [frontend/src/lib/api.js](file:///d:/Project/RD-ERP-main/frontend/src/lib/api.js)
* Memperbaiki logika deteksi `backendUrl`: memastikan jika frontend dibuka di port non-3000 (misal 3001 atau 80) saat development, tetap mengarah ke port backend yang tepat (`:8000` atau relative `/api`).

---

## Verification Plan

### Automated Tests
1. **Verifikasi Driver & Koneksi PostgreSQL + PgBouncer**:
   * Menjalankan container `postgres` dan `pgbouncer`.
   * Menguji handshake asyncpg melalui PgBouncer port 6432 dengan query `SELECT 1;`.
2. **Unit Tests Autentikasi**:
   * Menjalankan test suite autentikasi (`tests/test_auth_hardening.py`) yang disesuaikan untuk menguji rate-limit, password hashing, dan token issuance di PostgreSQL.
3. **Pengujian Endpoint Login API**:
   * Menguji `POST /api/auth/login` menggunakan curl / python test client:
     * Email: `rddev@gmail.com`, Password: `rdcloth2026` ➔ Status `200 OK`, mengembalikan JWT token.
     * Cek demo staff: `admin@example.com` / `admin123` ➔ Status `200 OK`.

### Manual Verification
1. **Docker Compose Build & Run**:
   * Menjalankan `docker compose up -d --build`.
   * Memastikan semua container (`postgres`, `pgbouncer`, `backend`, `frontend`) berstatus *healthy*.
2. **Browser Testing (UI Login)**:
   * Membuka `http://localhost` di browser.
   * Menekan tombol cepat demo **Owner** (`rddev@gmail.com`).
   * Memverifikasi login berhasil, toast "Selamat datang kembali" muncul, dan dashboard ERP terbuka dengan data terisi.
