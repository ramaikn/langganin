# Peta teknis Langganin

## Jalur baca

| Bagian | Tanggung jawab |
| --- | --- |
| `config/settings.py` | Environment, PostgreSQL/SQLite, Redis, autentikasi, HTTPS, static files |
| `crm/models.py` dan `migrations/` | Pelanggan, pembelian, hadiah, penukaran, buku besar, kampanye, audit |
| `crm/services.py` | Satu pintu perubahan saldo/stok, transaksi atomik dan idempotensi |
| `crm/selectors.py` | Agregasi pelanggan dan aturan segmen |
| `crm/forms.py` | Validasi input, normalisasi telepon, snapshot stok saat pengeditan |
| `crm/views.py`, `crm/urls.py` | Otorisasi, halaman, formulir, pagination, health endpoint |
| `crm/middleware.py` | Pembatasan login berbasis alamat jaringan dan akun di Redis |
| `templates/`, `static/` | Antarmuka responsif tanpa dependensi frontend |
| `management/commands/` | Pembuatan akun/peran dan demo opsional |
| `crm/demo.py` | Perapian aman record contoh lama, referensi struk dan urutan tanggal |
| `crm/tests.py` | Pengujian alur kritis serta dua skenario paralel PostgreSQL |
| `scripts/` | Setup, menjalankan, menguji, dan menghentikan lingkungan Windows |

## Aturan bisnis

- Satu workspace, satu usaha. Ini bukan SaaS multi-tenant atau integrasi kasir fisik.
- Pembelian menerima total akhir rupiah bulat, minimum Rp1.000 dan batas formulir Rp100 juta. `amount // 10000` menghasilkan poin. Tidak ada poin kedaluwarsa atau pengembalian dana pada versi ini. Jangan menghapus transaksi untuk mengoreksi saldo.
- Poin saat ini disimpan pada pelanggan untuk akses cepat; buku besar menyimpan setiap perubahan sebagai sumber rekonsiliasi. Tidak ada formulir mengedit poin secara langsung.
- Pencatatan pembelian mengunci baris pelanggan, memeriksa kunci permintaan dan struk unik, membuat transaksi, memperbarui saldo dengan ekspresi database, membuat entri poin dan audit dalam satu transaksi database.
- Penukaran mengunci pelanggan lalu hadiah dengan urutan tetap. Saldo dan stok dicek ulang di dalam kunci. Jika salah satu langkah gagal, semua perubahan dibatalkan.
- Permintaan ulang dengan UUID sama dan isi sama mengembalikan hasil sebelumnya. UUID sama dengan isi berbeda ditolak. UUID baru dengan struk sama ditolak.
- Edit profil memperbarui kolom profil saja agar saldo terbaru tidak tertimpa. Edit hadiah menggunakan pembandingan stok awal dan penguncian, menolak formulir lama jika stok berubah.
- Kampanye mengunci baris kampanye; snapshot penerima dibuat satu kali ketika terbit. Kombinasi pelanggan/kampanye unik. Hanya pelanggan dengan `consent=True` yang menjadi penerima. Pencabutan persetujuan berlaku untuk kampanye berikutnya, tidak menghapus riwayat.

## Segmen dan metrik

- Loyal: sedikitnya 3 pembelian sepanjang waktu dan pembelian terakhir dalam 30 hari.
- Perlu disapa: pernah membeli, pembelian terakhir lebih dari 30 hari lalu.
- Baru: mendaftar dalam 14 hari dan kurang dari 3 pembelian.
- Reguler: pelanggan lain pada label profil.
- Filter “baru” dan “perlu disapa” dapat tumpang tindih untuk data impor dengan tanggal historis; label profil memprioritaskan “perlu disapa”, kemudian “loyal”, lalu “baru”. Demo tidak memiliki tumpang tindih ini.
- Pembeli berulang: jumlah pelanggan dengan ≥2 transaksi dalam periode terpilih dibagi jumlah pelanggan yang membeli pada periode yang sama. Bukan retention cohort.
- Pilihan penjualan 7/14/30 hari mencakup hari ini serta hari-hari sebelumnya, berdasarkan zona waktu Asia/Makassar. Default 14 hari. Nilai periode tidak dikenal kembali ke default; tanggal masa depan tidak disertakan. Pelanggan teratas berdasarkan total transaksi sepanjang waktu, bukan hanya periode grafik.

## Tampilan portofolio

Atas arahan pengguna, tidak ada banner data contoh atau catatan developer pada aplikasi. Asal data tetap disebut sintetis di README dan dokumentasi, tidak diklaim sebagai hasil bisnis nyata. Telepon ditampilkan tersamarkan, email contoh memakai domain khusus dokumentasi. Formulir edit tetap menampilkan nilai telepon lengkap untuk pengelola. Tidak ada pengiriman pesan eksternal.

## Akses

Pengelola: semua halaman, edit profil, kelola hadiah, kampanye, dan audit. Kasir: ringkasan, tambah/lihat pelanggan, catat pembelian, lihat hadiah, dan penukaran. Tidak ada pendaftaran akun publik. Pembuatan akun melalui perintah operator. Superuser dianggap pengelola; jangan membagikan superuser untuk pemakaian rutin.

## Keamanan dan batas

Django menangani hashing kata sandi, CSRF, escaping HTML, cookie sesi, serta query berparameter. Login dibatasi 10 percobaan per 10 menit per alamat jaringan/akun. Kunci alamat tidak dihapus setelah login sukses agar pergantian nama akun tidak melewati batas. Di balik proxy, siapkan alamat klien tepercaya karena semua pengguna bisa terlihat berasal dari proxy yang sama.

Audit hanya menyimpan aktor, aktivitas, jenis objek, ID, waktu, bukan salinan email/telepon. Audit tidak memiliki endpoint edit/hapus, tetapi belum tamper-proof terhadap administrator database. Tidak ada MFA, SSO, anonimisasi, portal pelanggan, pembatalan transaksi, antrean pengiriman eksternal, atau benchmark skala produksi. Menambahkan fitur tersebut memerlukan aturan bisnis tersendiri, bukan sekadar tombol UI.

Tidak mengklaim keamanan mutlak. Sebelum data asli: HTTPS, backup/restore teruji, akun database berhak minimum, izin privasi, pengelolaan retensi, pemantauan, pembaruan dependensi, dan pemeriksaan keamanan independen.
