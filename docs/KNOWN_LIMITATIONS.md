# ⚠️ Known Limitations & Architecture Scope — NexaBiz ERP

Dokumen ini menjelaskan batasan teknis (*known limitations*) dan ruang lingkup arsitektur NexaBiz ERP versi 2.0 agar pembeli template memahami karakteristik software secara transparan.

---

### 1. Single-Tenant Architecture
- **Karakteristik**: NexaBiz ERP didesain sebagai sistem **single-tenant** per instance deployment (1 instalasi untuk 1 perusahaan / unit bisnis).
- **Rekomendasi**: Jika Anda ingin melayani banyak perusahaan yang terpisah sama sekali datanya (SaaS multi-tenant), jalankan instance container Docker terpisah dengan database berbeda atau port berbeda.

---

### 2. Multi-Currency Accounting
- **Karakteristik**: Format mata uang tampilan dapat dikonfigurasi ke mata uang manapun (`IDR`, `USD`, `MYR`, `EUR`, dll.) melalui menu *Settings*. Namun, pembukuan jurnal buku besar beroperasi dalam **satu mata uang utama bisnis** (single functional currency).
- **Rekomendasi**: Jika menjual ke marketplace luar negeri dengan valuta asing, konversikan nilai transaksi ke mata uang utama sebelum dimasukkan ke pencatatan buku besar.

---

### 3. File Attachments & Media Storage
- **Karakteristik**: Lampiran file invoice, foto produk, dan bukti transfer disimpan pada disk lokal server (`ATTACHMENTS_DIR`) yang dimount via volume Docker. Batas ukuran default per file adalah **10 MB** (dapat diubah via variabel `MAX_ATTACHMENT_SIZE_MB`).
- **Rekomendasi**: Untuk penyimpanan skala jutaan file gambar beresolusi sangat tinggi, integrasikan dengan Object Storage eksternal seperti AWS S3 atau Cloudflare R2 jika diperlukan.

---

### 4. Skalabilitas & Concurrency
- **Karakteristik**: Arsitektur FastAPI + Async Motor MongoDB mampu menangani ribuan transaksi harian dan ratusan staf aktif secara simultan dengan penggunaan memori yang sangat efisien (RAM server < 1.5 GB).
- **Rekomendasi**: Untuk bisnis dengan jutaan transaksi per hari, pastikan mengaktifkan replica set MongoDB dan menambahkan indeks komposit sesuai pola pencarian query khusus Anda.

---

### 5. Koneksi Marketplace API Langsung
- **Karakteristik**: Integrasi marketplace (Shopee, TikTok Shop, Tokopedia) saat ini menggunakan **Universal CSV / TSV Import Engine** yang sangat fleksibel tanpa memerlukan akun developer Shopee Open Platform berbayar atau approval API yang rumit.
- **Keuntungan**: Tidak rentan terhadap pemutusan token API berkala atau perubahan kebijakan developer platform.
