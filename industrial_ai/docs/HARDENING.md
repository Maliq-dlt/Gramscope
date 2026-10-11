# Hardening Video Insight

## Fase dan batas pekerjaan

| Fase | Hasil | Status |
| --- | --- | --- |
| 1. Akses dan data | Login, RBAC, workspace, SQLite, CSRF, rate limit, audit, backup database | Diterapkan dan diuji |
| 2. Dashboard | Akses TypeScript, menu akun, kontrol lanjutan dilipat, viewer hanya baca | React/TypeScript; build dan regresi tersedia |
| 3. Deployment | Container CPU, proxy HTTPS, pengujian otomatis CI | CI container/HTTPS lulus; domain publik belum diaktifkan |
| 4. Absensi wajah | Enrollment, verifikasi identitas, PAD, aturan absensi | Rencana lanjutan, belum mengumpulkan biometrik |

## Diterapkan

- Autentikasi aktif; password di-hash dengan scrypt stdlib (N=131072/r=8/p=1, sekitar 128 MiB),
  tanpa password bawaan. Hash lama ditingkatkan setelah login berhasil.
  Owner pertama: `uv run python access.py init --username owner` (password interaktif).
  Bootstrap launcher `--generate` dapat menulis `data/security/first-access.txt` lokal;
  hapus salinan credential setelah akses diamankan dan jangan bagikan berkas itu.
- Sesi server SQLite memakai cookie HttpOnly/SameSite. HTTPS menentukan Secure cookie.
  Login memeriksa Origin; seluruh endpoint unsafe lain memerlukan token CSRF sesi.
  Rate limit login dan API diterapkan di backend.
- Profil menampilkan username/peran/workspace sesi secara readonly. Ganti password
  memeriksa password saat ini, memvalidasi ulang hash/sesi dalam transaksi, mencabut seluruh
  sesi lama, lalu menerbitkan cookie dan token CSRF baru untuk browser peminta.
  Hash scrypt bersalt bukan enkripsi; password lama tidak dapat dibaca dari hash.
  Video/anotasi/riwayat tidak dihapus. Hapus `first-access.txt` setelah akses awal
  berhasil diganti; berkas itu tidak disinkronkan dengan password baru.
- Satu workspace per pengguna; admin, reviewer, viewer. Resource dicakup workspace.
  Viewer hanya membaca hasil/chat fakta; admin mengelola daftar/pembuatan akun dan
  pencabutan sesi melalui API. CLI menambahkan pengguna/workspace.
- SQLite stdlib adalah sumber metadata authoritative untuk state, ringkasan, anotasi,
  dan koreksi. Berkas sumber/media tetap dipertahankan; migrasi tidak menghapus media.
  Revision guard melindungi perubahan bersamaan. Jalankan satu worker.
- Audit HMAC berantai memakai key dan anchor di host yang sama, di luar database.
  Startup/backup memeriksa integritas. Ini mendeteksi perubahan/penghapusan event audit; bukan checksum seluruh tabel.
  Administrator host yang menguasai key dan anchor dapat memalsukannya.
- Upload/path/ukuran/durasi/resolusi dan kotak divalidasi. FFmpeg membatasi protokol
  `file,pipe` dan format input. Proses dibatalkan melalui jalur native yang tersedia.
- UI React/TypeScript strict; token tidak disimpan di localStorage.
  Controller dan build tetap mengikuti arsitektur studio. Fullscreen, sidebar, form koordinat dan
  reduced motion dipertahankan. Pemeriksaan unit tidak membuktikan browser deployment.

Sensitive GET audit dan prosedur retensi/pemulihan: [Data policy](DATA_POLICY.md). Tidak ada auto-purge; read audit menyatakan permintaan/status, bukan penerimaan media penuh.

## Pengelolaan lokal

```powershell
uv run python access.py init --username owner
uv run python access.py user --username reviewer1 --role reviewer --workspace Local
uv run python access.py user --username viewer1 --role viewer --workspace Local
uv run python access.py verify
uv run python access.py backup .tmp/backup-security
```

Password diminta interaktif. Untuk instalasi container, buat owner dengan
`docker compose run --rm app python access.py init --username owner` sebelum login. Simpan backup dalam penyimpanan yang aksesnya dibatasi.
Backup mencakup SQLite, key/anchor dan manifest artefak; bukan salinan penuh video/model.
Salin media dan model terpisah serta cocokkan manifest sebelum pemulihan. Jangan mengganti
key/anchor agar database rusak tampak valid. Hentikan layanan saat melakukan pemulihan.

## Container dan HTTPS

Dockerfile CPU mengambil dependency dari `uv.lock` frozen dan wheel Torch CPU seperti CI.
App memakai UID 10001, satu worker, root filesystem readonly, capability dibuang dan
`no-new-privileges`, batas 8 GiB/4 CPU/256 proses atau thread (RAM/CPU dapat diatur). Volume persistent memetakan `/app/data`, `/app/models`, `/app/.cache`;
`/app/.tmp` memakai tmpfs. Aplikasi hanya tersedia pada jaringan internal Compose; Caddy mengekspos HTTPS
ke `127.0.0.1:443` dan HTTP redirect ke `127.0.0.1:80`. Healthcheck internal memakai `/healthz`.
Model tidak otomatis disertakan ke image; gunakan setup CLI dan volume model persistent.

```powershell
docker compose config --quiet
docker compose run --rm app python access.py init --username owner
docker compose up --build -d
# Model vision saja; setup penuh mengunduh Qwen juga:
docker compose run --rm app python setup_models.py --vision-only
```

Untuk proxy publik, tetapkan origin/host eksplisit dan domain milik Anda:

```powershell
$env:DOMAIN = 'video.example.com'
$env:INSIGHT_PUBLIC_URL = 'https://video.example.com'
$env:INSIGHT_HOSTS = 'video.example.com'
$env:PUBLIC_BIND = '0.0.0.0'
docker compose config --quiet
docker compose up --build -d
```

Caddy memakai konfigurasi contoh dan volume sertifikat. Default `https://localhost`
menggunakan CA lokal Caddy; pengguna harus mempercayai sertifikat root dari volume
`caddy_data` pada perangkatnya sebelum membuka halaman. Jangan melewati peringatan
sertifikat. Domain publik memakai sertifikat otomatis setelah DNS dan port 80/443
tersedia; hostname di atas hanyalah contoh konfigurasi. App tidak mengekspos port host.
Origin non-loopback wajib HTTPS; Host tidak memakai wildcard. Jangan mempercayai
forwarded headers dari alamat sembarang. Proxy memakai user default image Caddy,
hanya capability `NET_BIND_SERVICE` untuk binary Caddy/port 80 dan 443,
dan `no-new-privileges`; isolasi app bukan jaminan isolasi host.

Validasi yang dijalankan: TypeScript strict, build UI, regresi playback/tracking/auth,
dan Compose config untuk localhost serta domain HTTPS. [CI](https://github.com/Maliq-dlt/N-Gram/actions/runs/37948789812)
lulus untuk image build, container readonly, volume aplikasi, sertifikat CA lokal,
login HTTPS dan CSRF melalui published port. Docker daemon lokal tidak tersedia;
setup model pada volume deployment dan domain publik belum diverifikasi.

## Fase lanjutan, belum diterapkan

- Uji pemulihan penuh dengan media, deployment HTTPS nyata, dan isolasi proses pada host target.
- Audit anchor di penyimpanan independen dan antrean worker shared sebelum multiworker.
- Facial enrollment, embeddings, PAD/liveness dan evaluasi false-match berbasis dataset
  terpisah. Identifikasi wajah serta keputusan otomatis belum tersedia; keputusan
  operasional harus ditinjau manusia. Label nama saat ini metadata manual.

FastAPI/SQLite memenuhi boundary akses saat ini; Laravel tidak diperlukan. Dependensi
Ultralytics mengikuti AGPL-3.0 atau lisensi enterprise yang berlaku. Hak checkpoint helm
perlu diperiksa terpisah; kode terbuka tidak otomatis memberi hak redistribusi semua bobot.
Lihat [lisensi dan sumber](../README.md#sumber-dan-lisensi) sebelum distribusi komersial.

## Absensi wajah: mekanisme yang disiapkan

Enrollment menyimpan ID peserta dan embedding dari beberapa sampel wajah yang
berizin. Model tidak perlu di-fine-tuning untuk setiap orang. Track ID video
saat ini hanya mengikuti objek dan belum mengidentifikasi peserta.

Alurnya: deteksi wajah → kualitas/occlusion → PAD/liveness → pencocokan embedding
terhadap peserta terdaftar → aturan shift/duplikasi → event absensi. Wajah tertutup,
keyakinan rendah atau PAD gagal menghasilkan **tidak terverifikasi** dan jalur
manual, tanpa mencatat kehadiran otomatis.

Sebelum fitur diaktifkan, uji foto/kertas, layar/video replay, masker, tangan,
cahaya dan sudut pada kamera target. Gerak/blink dari kamera RGB saja belum
membuktikan ketahanan spoof. Ukur false accept/reject dan error PAD pada sumber
terpisah; pilih sensor/model yang sesuai hasilnya. Tetapkan persetujuan,
penghapusan/retensi embedding, enkripsi penyimpanan dan akses administrator
biometrik, serta periksa lisensi model wajah. Tidak ada pengumpulan wajah atau
keputusan kehadiran dalam fase yang sudah diterapkan.
