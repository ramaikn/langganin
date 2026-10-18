# Hasil verifikasi

## Pembaruan tampilan pengguna, 14 Oktober 2026

- Sesuai permintaan pengguna, banner demo, footer slogan, subjudul pemasaran halaman operasional, dan catatan developer dihapus. Label bidang, nilai periode, status kampanye, dan instruksi yang dibutuhkan untuk transaksi tetap tersedia.
- Dashboard mendukung pilihan 7, 14, 30 hari. Periode tidak valid kembali ke 14 hari. Transaksi masa depan tidak dihitung.
- 92 referensi struk pada database lokal lama dirapikan menjadi `TRX-tanggal-nomor`, tanpa menghapus transaksi atau mengubah saldo. Perapian membatasi record yang dikenali sebagai contoh, menyesuaikan tanggal daftar bila lebih lambat dari pembelian pertama, dan menyelaraskan waktu audit pembelian.
- Seed baru memiliki variasi jam operasional dan tanggal daftar; pengujian baru menghasilkan 91 transaksi karena urutan angka acak berubah. Database review lama tetap memiliki 92 transaksi. Ini bukan kehilangan transaksi.
- **21/21 pengujian lolos dalam 8,514 detik**, termasuk periode dashboard, UI tanpa banner, penolakan perapian pada database bukan demo, perapian berulang tanpa duplikasi, perlindungan data tambahan pengguna, dan kronologi daftar/pembelian. Pembersihan database berhasil.
- Pemeriksaan deployment selesai dengan satu peringatan HSTS preload yang sama, tanpa error.
- Tampilan aktual diperiksa pada desktop 1440×900 dan mobile 390×844. Klik periode 14 hari dari 30 hari berhasil. Screenshot desktop diperbarui di `screenshots/dashboard-desktop.jpg`.
- Autentikasi kata sandi lokal untuk `pengelola` dan `kasir` diverifikasi berhasil tanpa mengubah kata sandinya. Kredensial tidak ditulis ke dokumentasi atau kode.
- Data tetap sintetis. Tidak ada klaim pelanggan nyata, deployment production, atau pengiriman pesan eksternal.

## Verifikasi implementasi awal

Tanggal: 14 Oktober 2026. Semua hasil berikut lokal, bukan pengujian layanan Stamps atau deployment publik.

## Lingkungan

- Windows, Python 3.14.7 melalui uv 0.12.19.
- Django 5.2.18, psycopg 3.3.6, PostgreSQL portabel 17.9.
- Redis port komunitas Windows 8.10.2, SHA-256 diverifikasi terhadap metadata rilis. Aplikasi memakai Redis database 0, pengujian database 1.
- PostgreSQL khusus Langganin `127.0.0.1:5547`, Redis `127.0.0.1:6397`, aplikasi `127.0.0.1:8017`.
- Lingkungan Python/cache/runtime di C:, source di `project/langganin` E:.

## Pengujian otomatis

Pengujian pertama: 17 skenario lolos, tetapi pembersihan database gagal karena koneksi worker pengujian paralel masih terbuka. Diperbaiki dengan menutup koneksi per worker, bukan mengubah aturan transaksi.

Pengujian kedua: **19/19 lolos dalam 5,124 detik**, database `test_langganin` berhasil dihapus. Tidak ada perubahan schema yang belum dimigrasikan.

Skenario:

1. Pembulatan poin, saldo, ledger, dan audit transaksi.
2. Pengulangan UUID tidak menggandakan transaksi; payload berbeda ditolak; struk ganda ditolak.
3. Nilai transaksi tidak valid tidak meninggalkan perubahan.
4. Penukaran dan pengiriman ulang tidak menggandakan pengurangan poin/stok.
5. Penukaran poin kurang atau stok habis dibatalkan.
6. Kampanye menghormati consent, segmen, dan publikasi sekali.
7. Batas segmen berbasis tanggal.
8. Normalisasi dan keunikan nomor telepon.
9. Wajib login dan pembatasan peran kasir.
10. Seluruh halaman utama merender; nama pelanggan berisi HTML di-escape.
11. CSRF serta perubahan hanya melalui POST.
12. Alur formulir transaksi, pengiriman ulang, dan penukaran.
13. Login dibatasi setelah 10 percobaan.
14. Demo ditolak pada database usaha yang telah berisi data.
15. Demo dapat dijalankan ulang tanpa duplikasi; saldo semua pelanggan cocok dengan ledger.
16. Edit profil tidak mengubah poin.
17. Formulir hadiah dengan stok lama ditolak.
18. Dua penukaran paralel pada PostgreSQL tidak menghabiskan stok/poin dua kali.
19. Dua transaksi paralel dengan UUID sama menambah poin sekali.

Setelah pengujian, skrip pemeriksaan deployment awal belum memasok secret ketika beralih ke production. Skrip diperbaiki untuk memakai kunci lokal yang sudah dibuat. Pemeriksaan deployment lalu dijalankan terpisah: **tanpa error**, satu peringatan `security.W021` tentang HSTS preload yang sengaja tidak diaktifkan tanpa domain dan persetujuan pemilik. Tidak menyembunyikan peringatan tersebut.

## Pemeriksaan browser

- Login nyata sebagai pengelola berhasil dan membuka dashboard.
- Dashboard menampilkan 24 pelanggan dan data transaksi demo dari PostgreSQL, bukan angka UI hardcoded. Demo awal berisi 92 transaksi sepanjang waktu; 83 termasuk jendela 14 hari pada saat pemeriksaan.
- Tampilan desktop diperiksa pada 1440×900 dan mobile pada 390×844. Navigasi mobile dapat digeser; tabel memiliki scroll internal.
- Screenshot desktop asli: `screenshots/dashboard-desktop.jpg`.
- Halaman pencatatan transaksi mobile dan tombol keluar mobile diperiksa setelah server dimuat ulang. Screenshot: `screenshots/transaksi-mobile.jpg`.
- Endpoint `/health/` memberikan HTTP 200 dengan `{"status":"ok"}` setelah pembaruan terakhir.
- Tidak ada error JavaScript yang dilaporkan snapshot browser. Aplikasi tidak membutuhkan JavaScript.
- Server sempat dihentikan sengaja untuk memuat perubahan karena dijalankan dengan `--noreload`, kemudian dijalankan kembali. Exit `-1` pada proses lama berasal dari penghentian ini.

## Kendala setup yang diselesaikan

ExecutionPolicy Windows menghalangi pemanggilan `.ps1` langsung; perintah dokumentasi memakai bypass khusus proses. Arsip Redis memiliki folder pembungkus sehingga pencarian executable dibuat rekursif. Pemeriksaan database kosong PowerShell diperbaiki agar database yang belum ada benar-benar dibuat. Instalasi terakhir dan pengisian demo berhasil.

## Belum diverifikasi

Docker/Compose, domain publik dan HTTPS nyata, performa beban tinggi, audit keamanan eksternal, dan pemulihan backup. Tidak ada klaim aplikasi bebas kerentanan atau sudah layak menyimpan data pelanggan produksi. Lihat `deployment.md` untuk langkah operasional sebelum penggunaan nyata.
