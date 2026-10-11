# Changelog

## 2026-10-11 — referensi review dan tracking kontinu

- Import CVAT video mengikat review ke hash XML/video dan coverage eksplisit; sparse/draft/label tak dikenal tidak disahkan otomatis.
- Evaluasi terpisah SAHI/full-frame dan ByteTrack/BoT-SORT setiap frame, dengan HOTA/IDF1 serta prediksi raw.
- Empat scene SDD baru dan dataset/protokol/CSV tersimpan; test tidak menunjukkan peningkatan dan model studio tetap.
- SAHI0.12.8 pinned dev, runnable checks masuk CI; panduan di docs/TRACKING_ACCURACY.md.

## 2026-10-11 — CCTV dan N-gram berbukti

- Ledger v2 menautkan crossing orang/kendaraan dan observasi helm frame/interval ke bukti asli, revisi dan source group; query/ringkasan memakai filter sama.
- Koreksi tersimpan memperbarui lintasan kandidat, chat/dashboard/detail; hasil detector awal tetap tersedia.
- Runner novelty mengelompokkan salinan sumber, memilih parameter/ambang pada dev dan menjelaskan P/logP/NLL/EOS ke video; run stale tidak menjadi fakta.
- Ringkasan JSON/Markdown deterministik, REPL akademik read-only dan regresi CI baru. Training nyata RTX4060 objects/helmets teruji; kualitas kamera independen belum tersedia.
- Bukti dan batas: [Verifikasi CCTV/N-gram](reports/VERIFIKASI_CCTV_NGRAM.md).

## 2026-10-10 — migrasi React terbaru

- Seluruh halaman dan tampilan data dinamis dipindahkan ke React 19.3.0 dan
  TypeScript strict; controller auth/media/editor typed, bundle production lokal
  tanpa CDN, pemutar tetap terpasang.
- Circle tema 900 ms memakai snapshot UI nyata dalam palet tujuan lalu commit;
  snapshot inert/ID terpisah, input file/password kosong, frame video disalin.
- Wheel reversal Lenis membuang target lama sebelum menerima arah baru;
  nested scroll native, dialog/fullscreen/reduced motion tanpa smoothing.
- Sembilan suite UI, strict typecheck/build, audit 0 dan browser fixture lulus;
  backend 91 security/36 HTTP, profil/storage dan wheel/sdist exact source lulus;
  hasil CI commit belum tersedia.
- Kerumunan hanya pada login/logout eksplisit; refresh/restorasi sesi tanpa delay.

## 2026-10-10 — milestone sebelum migrasi React

- Loader login minimal 3,2 detik sesuai permintaan pengguna, menunggu data nyata
  lebih lama bila perlu; reduced motion melewati tambahan waktu, error langsung
  tampil, sesi kedaluwarsa membatalkan reveal.
- Lenis 1.3.26 dan Framer Motion 14.1.0 dom/mini dibundel lokal dengan esbuild
  0.28.2 (sekitar 30,5 KB), tanpa React. Scroll halus berhenti saat dialog,
  fullscreen, signed-out, tab hidden dan reduced motion; scroll bersarang tetap native.
- Reveal tema circle native 720 ms, fallback WebView color wipe 560 ms + fade
  160 ms; entrance dan cleanup diuji terhadap callback stale.
- Verifikasi lokal motion: tujuh suite UI, typecheck/build/audit lulus;
  belum ada hasil CI untuk commit tambahan ini.

- Login dan dashboard dirapikan mengikuti referensi 21st.dev; logo Split V,
  tema ProMotor Wow dan terang lembut, toggle tema di samping avatar.
- Orb chat serta loading kerumunan mengikuti request/pemuatan nyata, mendukung
  reduced motion dan membatalkan callback animasi yang sudah kedaluwarsa.
- Nama tampilan/foto profil disimpan privat per akun di SQLite; foto dibatasi,
  didekode dan dinormalisasi tanpa metadata. Meter password aksesibel.
- Tidak ada kredensial tertanam, signup/SSO contoh, feed CCTV contoh, atau
  klaim operasional yang tidak dibuktikan. Data/video dan kontrol anotasi tetap.
- CI menambahkan regression profil serta lifecycle animasi; distribusi memuat
  logo dan ilustrasi lokal dengan atribusi.

## 2026-10-09

- Profil inline menampilkan identitas akun/workspace nyata secara readonly.
  Ganti password merotasi cookie/CSRF, mencabut seluruh sesi lama dan mempertahankan
  video/anotasi; password memakai hash scrypt, bukan enkripsi.
- Avatar/pengelompokan aksi akun mengadaptasi Origin UI dropdown-menu #393;
  mode hasil mengadaptasi segmented-control #23552 ke radio native tanpa runtime React/Radix/Motion.
- Fondasi akses: login tanpa password default, admin/reviewer/viewer, isolasi
  workspace, cookie server/CSRF, pembatasan permintaan dan audit HMAC.
- Metadata SQLite dengan migrasi idempotent; JSON menjadi snapshot kompatibel,
  dan video/model lama tetap tersedia. Backup database serta manifest artefak.
- Auth TypeScript strict, menu akun dan viewer hanya baca; pemutar/editor native
  tetap dipertahankan. Docker CPU, Compose dengan proxy Caddy HTTPS dan CI deployment.
- Absensi wajah/enrollment/PAD didokumentasikan sebagai fase lanjutan.

- Antrean review objek/helm, approval terpisah, dan training otomatis setelah
  seluruh posisi kelompok selesai serta tersedia dua sumber asli berbeda.
- Snapshot label yang disahkan konsisten dengan fingerprint; perubahan berikutnya
  masuk run berikutnya. Parameter pilot `nbs=2` memastikan update setiap batch.
- Checkpoint baru menjalankan analisis ulang tanpa menimpa hasil sebelumnya;
  hasil mencatat model ID, SHA-256, waktu training dan metrik.
- Retry upload lengkap, pembatalan frame/batch/proses native, dan ekspor MP4
  asinkron dengan progress; followup gagal dapat dicoba ulang tanpa training ulang.
- CI untuk core beku, kualitas Python/UI, audit dependency, API/media, training
  objek/helm nyata pada CPU, serta isi wheel/sdist. Dependabot mingguan tersedia.
- Upgrade Torch/Transformers/setuptools untuk advisori dependency; setup vision-only
  mempertahankan metadata chat. README, kontribusi, keamanan dan batas lisensi dirapikan.

- Editor anotasi layar penuh dengan sidebar label/warna/edit/hapus; kotak dan
  posisi video tetap sama saat masuk/keluar.
- Tracking koreksi tersimpan lintas restart; ekspor MP4 H264/audio per revisi
  memakai kotak manual/tracker dan mempertahankan hasil AI awal.
- CLI video panjang: segmentasi tervalidasi, seleksi pHash/jarak waktu dan
  auto-label batch objek/helm dengan Auto RTX/CPU. Label tetap draft untuk review.
- Split training mengikuti sumber asli serta posisi global antarsegmen;
  metadata asal dipertahankan ketika analisis ulang.

## 0.1.0 — 2026-10-08

- Publikasi awal Video Insight Lokal: upload video, deteksi/tracking, counting,
  bukti, chatbot lokal, tema terang/gelap dan koreksi manual.
- Koreksi yang disahkan dipakai dashboard/chat/ekspor; preview memakai penuntun
  detector dan optical flow tanpa melatih ulang model saat play/simpan/query.
- Setup Python dan unduh model melalui `npm run setup`; bobot/data tetap lokal.
- Fine-tuning detector/chat tersedia sebagai proses terpisah, belum tervalidasi
  untuk keputusan keselamatan atau identitas di pabrik.
