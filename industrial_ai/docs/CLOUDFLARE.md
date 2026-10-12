# Cloudflare untuk Video Insight

Setup ini menerbitkan **aplikasi lengkap melalui Cloudflare Tunnel**. Landing, login,
API, Q&A N-gram, video dan analisis tetap berasal dari satu origin. Ini bukan upload
aplikasi Python ke Pages: host Docker/komputer/VPS tetap menjalankan FastAPI dan
menyimpan SQLite, media serta model. Host harus menyala agar situs dapat diakses.

Pages cocok untuk situs statis. Cloudflare Containers memiliki disk ephemeral;
memindahkan database/model/media ke sana membutuhkan perubahan penyimpanan yang
belum diterapkan. Konfigurasi ini mempertahankan volume dan autentikasi yang ada.

## Persiapan akun dan host

1. Siapkan Docker Compose dan domain aktif dalam akun Cloudflare.
2. Buka Cloudflare One → Networks → Connectors → Cloudflare Tunnels dan buat
   tunnel remotely-managed jenis `cloudflared`.
3. Tambahkan published application dengan hostname milik Anda. Service type **HTTP**,
   URL **app:8765**. Pada pengaturan origin, isi **HTTP Host Header** dengan hostname
   publik yang sama. Jangan arahkan ke localhost: localhost di container tunnel adalah
   container tunnel sendiri.
4. Salin token tunnel dari dashboard **ke file lokal**, bukan ke kode/Git/chat.
   Jangan menyalin seluruh command Docker, hanya nilai tokennya.

Jalankan dari direktori `industrial_ai`:

```powershell
Copy-Item cloudflare.env.example .env.cloudflare
New-Item -ItemType Directory -Path .secrets -Force
```

Edit `.env.cloudflare`: ganti `CF_HOSTNAME` dengan domain asli tanpa `https://`
atau path. Buat `.secrets/cloudflare-tunnel-token.txt` dan isi token dari dashboard.
File secret dan env diabaikan Git serta Docker build context; token dipasang sebagai
Compose secret, tidak dicantumkan pada command/proses atau konfigurasi yang dipublikasikan.

## Jalankan aplikasi lengkap

```powershell
docker compose --env-file .env.cloudflare -f compose.yaml -f compose.cloudflare.yaml config --quiet
docker compose --env-file .env.cloudflare -f compose.yaml -f compose.cloudflare.yaml build app
docker compose --env-file .env.cloudflare -f compose.yaml -f compose.cloudflare.yaml run --rm app python access.py init --username owner
docker compose --env-file .env.cloudflare -f compose.yaml -f compose.cloudflare.yaml run --rm app python setup_models.py --vision-only
docker compose --env-file .env.cloudflare -f compose.yaml -f compose.cloudflare.yaml up -d app cloudflared
```

Password owner diminta interaktif. Volume baru tidak membawa akun/data dari aplikasi
Windows lokal. Gunakan prosedur migrasi/backup di [HARDENING.md](HARDENING.md) bila ingin
memindahkannya; jangan menimpa volume. Untuk chat video berbasis Qwen, jalankan
`setup_models.py` tanpa `--vision-only`. **Chatbot Q&A N-gram tidak membutuhkan model LLM.**
Container yang tersedia memakai CPU; GPU lokal Windows tidak diteruskan otomatis.

Proxy Caddy berada di profile `direct-https` sehingga tidak diterbitkan pada jalur ini.
App dan tunnel tidak membuka port host. Origin HTTP hanya berjalan pada jaringan
internal Docker; URL browser HTTPS memakai domain Cloudflare. Secure cookie, allowlist
Host, login Origin dan CSRF mengikuti hostname yang dikonfigurasi.

## Aturan domain dan upload

- Buat Cache Rule dengan **Bypass cache untuk seluruh hostname aplikasi**. Media dan
  API berisi data workspace, bukan konten cache publik. Jangan aktifkan Cache Everything.
- Free/Pro saat dokumentasi diperiksa membatasi request upload 100 MB; zone dapat
  mengatur batas lebih kecil. Overlay membatasi video **95 MiB** dan UI membaca batas
  server. Periksa Network → Maximum Upload Size; pilih paling sedikit 100 MB.
- Analisis/training menggunakan job background dan polling yang sudah ada. Upload
  tetap satu request; chunked upload belum diterapkan. Kecilkan video yang melebihi
  batas; peningkatan plan tidak otomatis menaikkan batas overlay ini.
- Jangan gunakan Quick Tunnel acak untuk setup produksi: hostname origin/auth harus
  tetap. DNS-only tidak dapat menggantikan route Tunnel ini.

## Verifikasi setelah aktivasi

```powershell
docker compose --env-file .env.cloudflare -f compose.yaml -f compose.cloudflare.yaml ps
docker compose --env-file .env.cloudflare -f compose.yaml -f compose.cloudflare.yaml logs --tail 50 cloudflared
```

Periksa tunnel **Healthy** di dashboard, buka hostname HTTPS, lalu uji login, Q&A N-gram,
upload video kecil, hasil dan logout. `/api/jobs` tanpa login harus ditolak; browser
harus menerima cookie Secure/HttpOnly. Jangan pakai loglevel debug karena dapat memuat
header rahasia. Untuk update connector, jalankan `pull cloudflared` lalu `up -d cloudflared`
dengan argumen Compose yang sama. Jangan memakai `down -v` karena menghapus volume.

Konfigurasi lokal dapat diverifikasi dengan `python tests/cloudflare_check.py` tanpa
menghubungkan tunnel. Itu tidak membuktikan domain publik, token, inference CPU atau
Docker daemon berfungsi. Account/domain/token belum diaktifkan oleh setup sumber ini.

Sumber resmi (diakses 12 Oktober 2026):
- [Tunnel token file](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/configure-tunnels/cloudflared-parameters/run-parameters/#token-file)
- [Published application](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/routing-to-tunnel/)
- [Upload limit](https://developers.cloudflare.com/support/troubleshooting/http-status-codes/4xx-client-error/error-413/)
- [Containers storage](https://developers.cloudflare.com/containers/concepts/architecture/)

## Uji coba Windows tanpa domain (Quick Tunnel)

Untuk laptop yang sudah memiliki akun, data dan model lokal, jalankan connector
Windows langsung ke studio. Ini mempertahankan model GPU lokal; Docker tidak
perlu dijalankan untuk mode ini. URL `trycloudflare.com` berubah setiap peluncuran
serta berhenti ketika proses/komputer ditutup. Mode ini untuk uji coba, bukan hosting
permanen. Login aplikasi dan CSRF tetap diperlukan untuk membuka data.

Connector resmi yang dipakai launcher dipin ke versi **2026.10.0** dan hash rilis
GitHub diverifikasi sebelum dijalankan. Dari root repository:

```powershell
. ./industrial_ai/setup_lokal.ps1
New-Item -ItemType Directory -Path .cache/cloudflared -Force
Invoke-WebRequest https://github.com/cloudflare/cloudflared/releases/download/2026.10.0/cloudflared-windows-amd64.exe -OutFile .cache/cloudflared/cloudflared-2026.10.0.exe
./industrial_ai/cloudflare_lokal.ps1
```

Selesaikan upload/analisis/training, lalu tutup server lokal lama sebelum menjalankan
launcher. Launcher menolak port yang sudah terpakai; tidak menutup server lain.
Ia membuat URL sementara, mengatur origin HTTPS/allowlist Host/batas 95 MiB, lalu
menjalankan satu studio pada loopback port 8765 menggunakan akun dan model yang sudah tersedia.
Buka URL yang dicetak dan login dengan akun studio biasa. **Ctrl+C** menutup studio
serta Tunnel. Untuk kembali ke mode lokal, jalankan `industrial_ai/jalankan.ps1`.

Log dan URL terakhir ada di `.tmp/cloudflare/`, binary di `.cache/cloudflared/`;
semuanya tetap lokal dan tidak masuk Git. Tidak ada token akun yang diperlukan.
Untuk memperbarui connector, ambil rilis resmi dan ganti pin versi/hash pada launcher.

Pemeriksaan HTTP nyata setelah URL siap:

```powershell
./industrial_ai/.venv/Scripts/python.exe industrial_ai/tests/quick_tunnel_check.py https://URL-ANDA.trycloudflare.com
```

Check ini memverifikasi halaman/aset HTTPS, penolakan akses tanpa login dan origin
login/CSRF. Ia tidak memverifikasi inference video/Qwen atau login dengan akun nyata.
Sumber: [Quick Tunnels](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/do-more-with-tunnels/trycloudflare/).
