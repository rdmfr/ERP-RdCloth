# ❓ Frequently Asked Questions (FAQ) — NexaBiz ERP

Berikut adalah rangkuman pertanyaan yang sering diajukan oleh pembeli template dan pengguna baru NexaBiz ERP.

---

### 1. Apakah aplikasi ini memerlukan biaya langganan bulanan?
**Tidak.** NexaBiz ERP bersifat **100% Self-Hosted & One-Time Purchase**. Anda memiliki kode sumber penuh (full source code) dan dapat meng-hostingnya di server lokal komputer toko, VPS, atau cloud milik Anda sendiri tanpa biaya langganan software bulanan.

---

### 2. Apakah saya bisa mengganti nama, logo, dan mata uang aplikasi?
**Ya, sangat mudah.**
- Nama bisnis, alamat, no telepon, format mata uang (`IDR`, `USD`, `MYR`, `SGD`, dll.), dan tarif pajak dapat diubah langsung dari menu **Settings -> Profil Bisnis**.
- Untuk kustomisasi nama brand / logo aplikasi, Anda dapat mengedit file `frontend/src/config/appConfig.js`.

---

### 3. Bisakah dijalankan di komputer Windows tanpa VPS?
**Ya.** Anda dapat menjalankan NexaBiz di Windows menggunakan dua cara:
1. **Docker Desktop** (Sangat mudah, satu klik jalankan `docker compose up`).
2. **Local Python & Node.js** (Menjalankan virtualenv Python FastAPI di backend dan React di frontend).

---

### 4. Apakah data aman jika terjadi mati listrik atau server restart?
**Ya.** Seluruh data transaksi, mutasi stok, dan akun tersimpan secara persisten di database MongoDB. Pada mode Docker Compose, data disimpan di volume Docker persisten (`mongo_data`, `attachments_data`, `backups_data`) sehingga aman meskipun container di-restart.

---

### 5. Bagaimana cara mengimpor ribuan produk atau data penjualan dari Shopee / TikTok Shop?
Gunakan menu **Universal Import Wizard** (`/marketplace-import`):
- Download template CSV resmi yang telah disediakan.
- Buka di Excel atau Google Sheets, isi data Anda, lalu copy-paste atau upload file CSV.
- Fitur **Live Preview** akan memvalidasi apakah ada SKU duplikat atau harga salah sebelum disimpan ke database.

---

### 6. Apakah NexaBiz ERP mendukung multi-user dan pembatasan hak akses staf?
**Ya.** Terdapat 4 peran hak akses bawaan (Role-Based Access Control):
- **Owner**: Akses ke seluruh sistem, laporan keuangan rahasia, audit trail, dan manajemen staf.
- **Admin**: Operasional pesanan, katalog produk, CRM pelanggan, dan vendor supplier.
- **Finance**: Pembukuan buku besar, faktur, kas/bank, rekonsiliasi, dan laporan laba rugi.
- **Production**: Alur kerja perintah produksi, resep BOM, dan pemotongan bahan baku.

---

### 7. Bagaimana jika saya lupa password akun Owner?
Jika Anda memiliki akses ke server/terminal:
1. Anda dapat mereset password langsung dengan mengedit `OWNER_PASSWORD` di file `.env` dan me-restart service.
2. Atau jalankan perintah script reset password yang disediakan di folder `scripts/`.

---

### 8. Apakah laporan keuangan bisa dicetak untuk keperluan kantor pajak / akuntan?
**Ya.** NexaBiz ERP dilengkapi generator laporan PDF resmi (Laba Rugi Komprehensif, Neraca Keuangan, Neraca Saldo, dan Buku Besar Rekening) serta tombol ekspor data lengkap ke format Microsoft Excel / CSV.

---

### 9. Bagaimana cara menghubungkan ke domain sendiri (misal: `erp.namabisnis.com`) dan memasang SSL (HTTPS)?
Anda dapat mengarahkan DNS domain ke IP VPS Anda, lalu memasang reverse proxy seperti **Nginx Proxy Manager**, **Caddy**, atau **Certbot Let's Encrypt**:
```bash
# Contoh dengan Certbot
sudo certbot --nginx -d erp.namabisnis.com
```
Atau cukup gunakan Cloudflare SSL dengan mode Flexible/Full.
