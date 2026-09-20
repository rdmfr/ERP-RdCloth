# 🚀 NexaBiz ERP — Panduan Pembeli & Onboarding Template

Selamat datang di **NexaBiz ERP**! Dokumen ini adalah panduan resmi bagi pembeli template untuk melakukan setup, konfigurasi awal, dan menjalankan operasional bisnis harian secara optimal.

---

## 📋 Daftar Isi
1. [Kebutuhan Sistem](#1-kebutuhan-sistem)
2. [Cara Instalasi Cepat (Docker & Manual)](#2-cara-instalasi-cepat)
3. [Setup Awal & Onboarding Wizard](#3-setup-awal--onboarding-wizard)
4. [Bagan Akun (COA) & Input Saldo Awal](#4-bagan-akun-coa--input-saldo-awal)
5. [Universal Import Wizard (Import Data Excel/CSV)](#5-universal-import-wizard)
6. [Export Laporan Keuangan untuk Akuntan (PDF/Excel)](#6-export-laporan-keuangan)
7. [Manajemen Pengguna & Keamanan](#7-manajemen-pengguna--keamanan)
8. [Tips Backup & Pemulihan Data](#8-tips-backup--pemulihan-data)

---

## 1. Kebutuhan Sistem

### Rekomendasi Server / VPS:
- **OS**: Ubuntu 22.04 LTS / Debian 12 / Windows 10/11 Pro (dengan WSL2 & Docker Desktop).
- **CPU**: 1 Core (Rekomendasi 2 Core).
- **RAM**: 2 GB (Rekomendasi 4 GB untuk Docker Compose).
- **Storage**: 20 GB SSD.
- **Port**: 80 (HTTP) atau 443 (HTTPS via Nginx Reverse Proxy / Cloudflare).

---

## 2. Cara Instalasi Cepat

### A. Menggunakan Docker Compose (Direkomendasikan untuk Production / VPS)
1. Salin repository ke server/komputer Anda:
   ```bash
   git clone https://github.com/rdmfr/ERP-RdCloth.git
   cd ERP-RdCloth
   ```
2. Buat file `.env` dari contoh konfigurasi Docker:
   ```bash
   cp .env.docker.example .env
   ```
3. Edit file `.env` dan atur credential Owner:
   ```env
   DB_NAME=nexabiz
   JWT_SECRET=buat_kunci_rahasia_acak_minimal_32_karakter_disini
   OWNER_EMAIL=owner@bisnisanda.com
   OWNER_PASSWORD=PasswordKuatOwner123!
   OWNER_NAME=Nama Pemilik Bisnis
   ENVIRONMENT=production
   DEMO_MODE=false
   PORT=80
   ```
4. Jalankan stack Docker:
   - **Linux/VPS**: `docker compose up -d`
   - **Windows (PowerShell)**: `.\scripts\install.ps1`
5. Akses ERP melalui browser di `http://IP_SERVER` atau `http://localhost`.

---

## 3. Setup Awal & Onboarding Wizard

Saat pertama kali login dengan akun Owner:
1. Masuk ke menu **Settings** (`/settings`).
2. Lengkapi **Profil Bisnis**:
   - Nama Perusahaan / Brand.
   - Mata Uang (cth: `IDR` / `Rp`), Format Wilayah (`id-ID`), dan Zona Waktu (`Asia/Jakarta`).
   - Alamat & Kontak resmi (akan tercetak otomatis di Invoice & Laporan PDF).
3. Atur konfigurasi biaya komisi Marketplace di menu **Marketplace Fees** (`/marketplace-settings`).

---

## 4. Bagan Akun (COA) & Input Saldo Awal

NexaBiz ERP dilengkapi dengan standar Chart of Accounts (COA) akuntansi Indonesia (1-xxxx Aset, 2-xxxx Kewajiban, 3-xxxx Ekuitas, 4-xxxx Pendapatan, 5-xxxx HPP, 6-xxxx Beban):

1. Masuk ke menu **Finance Suite** (`/finance-suite`) -> Tab **Bagan Akun (COA)**.
2. Tambah akun bank Anda (misal: *Bank BCA*, *Bank Mandiri*, *BRI*).
3. Masuk ke Tab **Saldo Awal**:
   - Masukkan saldo kas riil, saldo bank, piutang, hutang, dan persediaan awal Anda.
   - Centang opsi *Otomatis seimbangkan selisih ke Ekuitas Saldo Awal*.
   - Klik **Simpan Saldo Awal**. Jurnal pembuka akan otomatis dibukukan.

---

## 5. Universal Import Wizard

Gunakan menu **Import Orders & Data** (`/marketplace-import`) untuk migrasi data dari spreadsheet lama:
1. Pilih modul yang ingin diimpor:
   - 🛒 **Order Penjualan & Marketplace** (Shopee, TikTok Shop, WhatsApp, Offline)
   - 📦 **Master Produk & Varian**
   - 🧵 **Master Bahan Baku**
   - 👥 **Data Pelanggan**
   - 🏭 **Data Supplier**
   - ⚖️ **Saldo Awal Akun COA**
2. Klik tombol **Download Template** untuk mendapatkan format CSV resmi.
3. Salin/Tempel data dari Microsoft Excel atau Google Sheets ke area teks.
4. Klik **Preview & Validasi Baris**:
   - Sistem akan memeriksa duplikasi SKU, validitas angka, dan ketersediaan akun/stok.
   - Baris valid ditandai hijau `✓ Valid`, baris salah ditandai merah `✕ Error` lengkap dengan penyebabnya.
5. Klik **Eksekusi Import**. Mode Ketat menjamin *atomic rollback* jika ada data gagal.

---

## 6. Export Laporan Keuangan untuk Akuntan

NexaBiz ERP menyediakan generator laporan resmi berstandar akuntansi:
- **Laporan Laba Rugi (Profit & Loss)**: Klik tombol **PDF Resmi** atau **CSV** di `/reports` atau `/finance-suite`.
- **Laporan Neraca (Balance Sheet)**: Tersedia export CSV & PDF di `/finance-suite` -> Tab Laporan Akuntansi.
- **Neraca Saldo (Trial Balance)**: Verifikasi keseimbangan debit-kredit dalam format PDF/CSV.
- **Buku Besar (General Ledger)**: Export mutasi rekening dan saldo berjalan per akun ke PDF/CSV.
- **Laporan Valuasi Stok Persediaan**: Export nilai HPP dan kuantitas persediaan di `/reports`.

---

## 7. Manajemen Pengguna & Keamanan

- **Akses Berbasis Peran (RBAC)**:
  - `Owner`: Akses penuh ke seluruh modul, pengaturan, audit log, dan manajemen user.
  - `Admin`: Akses ke Penjualan, Produk, Bahan Baku, Pelanggan, Supplier, dan Import.
  - `Finance`: Akses ke Finance Suite, Pembelian, Kas/Bank, Pengeluaran, dan Laporan.
  - `Production`: Akses ke Perintah Produksi, BOM, Bahan Baku, dan Inventaris.
- **Proteksi Brute-Force**: Penguncian otomatis 15 menit jika terjadi 5x percobaan login gagal.
- **Password Hardening**: Kebijakan minimal 8 karakter kombinasi huruf dan angka.

---

## 8. Tips Backup & Pemulihan Data

1. **Backup Database MongoDB**:
   ```bash
   docker compose exec mongo mongodump --db nexabiz --out /data/db/backup_$(date +%F)
   ```
2. **Download Backup via API / Settings**:
   - Cek status backup dan unduh file lampiran/database langsung di menu **Settings**.

---

*Terima kasih telah menggunakan NexaBiz ERP! Template ini siap dipublikasikan, digunakan untuk operasional internal, atau dijual kembali sebagai solusi ERP bisnis.*
