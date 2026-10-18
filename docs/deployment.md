# Deployment dan operasional

## Status

Demo Windows dengan PostgreSQL dan Redis sudah dijalankan lokal. Dockerfile/Compose disediakan untuk Linux, **belum diuji** karena Docker tidak tersedia di mesin pengerjaan. Jangan menyebut deployment publik sudah selesai.

## Container Linux

1. Salin `.env.example` ke `.env`. Isi secret Django acak minimal 50 karakter, password PostgreSQL acak URL-safe, serta hostname asli. Jangan commit `.env`.
2. `docker compose build` dan `docker compose up -d db redis`.
3. `docker compose run --rm web uv run --frozen manage.py migrate --noinput`.
4. `docker compose run --rm web uv run --frozen manage.py collectstatic --noinput`.
5. Buat akun dengan `docker compose run --rm -e LANGGANIN_MANAGER_PASSWORD -e LANGGANIN_CASHIER_PASSWORD web uv run --frozen manage.py setup_roles`. Isi kedua environment variable pada shell operator dahulu, jangan menulis kata sandi dalam riwayat perintah.
6. Opsional demo pada database kosong: `docker compose run --rm web uv run --frozen manage.py seed_demo`.
7. `docker compose up -d web`.
8. Letakkan Caddy/Nginx pada host di depan `127.0.0.1:8017`, gunakan TLS yang valid, dan **timpa** header `X-Forwarded-Proto` sesuai protokol HTTPS. Port aplikasi, PostgreSQL, dan Redis tidak boleh dapat diakses publik.

Mode production mengaktifkan redirect HTTPS dan secure cookies. Mengakses port 8017 langsung lewat HTTP tidak cukup. `DJANGO_TRUST_PROXY=1` pada Compose hanya aman dengan proxy tepercaya dan aplikasi tetap terikat loopback. Bila topologi berubah, konfigurasi harus diperiksa ulang. Tidak mengaktifkan HSTS preload otomatis karena memerlukan persetujuan pemilik domain.

Untuk deployment sungguhan, pisahkan akun pemilik migrasi dan akun runtime database dengan izin minimum. Compose awal menggunakan pemilik database untuk kemudahan demo. Redis di jaringan internal tidak menyimpan data poin atau saldo; data utama selalu PostgreSQL. Cache yang hilang menghapus pembatasan login, bukan transaksi.

## Backup lokal

Data Windows berada di `%LOCALAPPDATA%\Temp\opencode\langganin`, bukan di repo. Simpan backup di lokasi persisten sebelum membersihkan Temp. Gunakan `pg_dump -Fc` pada database `langganin`, host `127.0.0.1`, port `5547`, pengguna `langganin`. Baca kata sandi dari file kredensial lokal, isi `PGPASSWORD` hanya selama proses, lalu hapus environment variable tersebut. Jangan menaruh backup berisi data pelanggan di repo publik.

Pemulihan harus diuji pada database baru dengan `pg_restore`; jangan menimpa database aktif tanpa rencana. Perintah stop tidak menghapus data. Untuk berpindah dari demo ke data nyata, gunakan database/runtime baru. Antarmuka portofolio tidak memasang banner demo; penanda database dan penjelasan sumber data sintetis tetap dipertahankan dalam dokumentasi.

## Batas kesiapan

Sebelum penggunaan bisnis: backup dan restore, kebijakan privasi/retensi, monitoring, akun database minimum, perawatan dependensi, serta pengujian beban berdasarkan kebutuhan. Belum ada integrasi pembayaran, verifikasi kepemilikan telepon, diskon checkout otomatis, atau mekanisme refund. Penukaran hadiah berarti pencatatan penyerahan oleh kasir, bukan voucher terhubung POS.
