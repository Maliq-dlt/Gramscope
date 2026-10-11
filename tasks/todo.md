## Siklus kualitas data dan akurasi (selesai)

- [x] Q1: sumber resmi/lisensi, akuisisi, audit label/decode/dedup dan protokol beku.
- [x] Q2: diagnosis detector sebelum tracker dan output tracker pada ground-camera GT.
- [x] Q3: kandidat dipilih train/dev; winner dibekukan dan satu evaluasi test baru.
- [x] Q4: hipotesis tail N-gram, CE/aturan/pasangan, data real versus konstruksi, kalibrasi/CI/budget.
- [x] Q5: tests/lint/type/build, review, preservasi, data/docs dan GitHub main + [CI commit implementasi lulus](https://github.com/Maliq-dlt/Gramscope/actions/runs/38149557004).

Gate operasional lama tetap terbuka: anotasi lokasi pabrik, onset insiden/exposure dan audit produksi tidak digantikan dataset publik.

# Checklist aktif — N-gram dan CCTV

Tanggal: **11 Oktober 2026**. [Rencana aktif](plan.md) · [Bukti implementasi sebelumnya](../extensions/reports/VERIFICATION.md).

## Siklus validasi baru

- [x] A1 Bekukan protokol/grid/rubrik/budget sebelum run dan snapshot berkas terlindungi.
- [x] A2 Run skenario bertingkat dengan rules/pair/LM dan tiga seed; cek hard pair invariance.
- [x] A3 Uji derau/durasi, calibration source terpisah dan reviewer-budget; export unit benar.
- [x] A4 Corpus ID baru/dedup, selection dev, primary holdout sekali dan robustness development.
- [x] A5 Validasi data/tes/source/build/preservasi dan review; finalkan hasil akademik.
- [x] C1 Setelah A5, buat protokol CCTV berdasarkan inventaris label/sumber aktual.
- [x] C2 Evaluator detector berlabel publik/site; batas generalisasi jelas.
- [x] C3 Verifikasi rules vs novelty, reviewer budget dan gate ground truth/exposure.
- [x] C4 Read/download audit, retensi/backup/deletion dan lisensi dalam scope lokal.
- [x] C5 Regresi, biaya, hasil, preservasi dan publikasi main terverifikasi; [CI exact commit lulus](https://github.com/Maliq-dlt/Gramscope/actions/runs/38140796838). Data lokasi target tetap gate terbuka.

Centang berarti hasil dan verifikasi ada; runner tidak berarti akurasi lapangan terbukti.

## Pekerjaan aktif — N-gram dan CCTV

Status: **implementasi fungsional fase 0–4 terverifikasi lokal; 185 tes akademik lulus. Referensi publik detector/tracking sudah diukur; kualitas kamera lokasi nyata tetap belum terbukti**. Centang menandakan pekerjaan dan bukti selesai, bukan fitur yang sekadar disebut dalam rencana. Riwayat centang lama tetap disimpan di bawah. Fitur lama di luar fokus tidak dihapus.

### Fase 0 — Kontrak dan baseline

#### 0.1 Definisi kejadian dan scope

- [x] Batasi pekerjaan baru pada N-gram dan analisis CCTV dari video unggahan; pisahkan kemampuan lama, task baru dan fitur di luar scope.
- [x] Tetapkan urutan dependency, batas data/hasil, peran detector vs N-gram, dan gerbang verifikasi.
- [x] Bekukan contoh payload versi event berikut dengan offset/interval, satuan count, status helm, simultaneous observations, revisi dan bukti berdasarkan review kode saat implementasi.

Dependency: tidak ada. Perkiraan scope: S, 1–2 dokumen. Verifikasi: contoh satu rekaman/track/helm/vehicle dapat ditelusuri ke kontrak/API; bukan placeholder runtime. Lokasi: `tasks/plan.md`, kontrak dekat `industrial_ai/event_ledger.py` dan `extensions/src/event_sequences.py`.

#### 0.2 Dataset dan baseline terukur

- [x] Pilih rekaman berizin, simpan source hashes/lisensi dan split source-group; potongan/copy sumber yang sama tetap satu split.
- [x] Bekukan rubrik, subset label untuk tracking/helm/novelty, baseline dan ambang evaluasi sebelum membuka test; data tidak cukup ditulis sebagai batas nyata.
- [x] Jalankan suite existing dan audit hasil/core/bobot/perubahan pengguna; ukur baseline biaya pada subset kecil sebelum scaling.

Dependency: 0.1. Scope: M, 3–5 file metadata/runner/report. Verifikasi: provenance/split diperiksa, baseline metrics/logs dan SHA-256 tersimpan lokal; fixture tidak disebut kualitas pabrik. Lokasi: dataset lokal ignored, runner/checks `extensions/experiments/` atau `industrial_ai/tests/`, report existing.

**Checkpoint 0:** kontrak dibekukan, data siap atau batasnya diketahui; setup/tes existing tidak dibuat ulang, hasil lama utuh.

### Fase 1 — Review menjadi kejadian

#### 1.1 Koreksi dan pembelajaran transparan

- [x] UI/API/export menampilkan sumber hasil dan revisinya: detector awal, koreksi reviewer, atau kandidat fine-tuned.
- [x] Simpan koreksi memperbarui hasil/bukti yang direview; edit membatalkan approval terkait dan stale turunan tanpa menghapus riwayat.
- [x] Reuse antrean belajar existing: draft/satu sumber tidak melatih; antrean selesai dan sumber memadai menghasilkan snapshot/checkpoint kandidat lalu analisis ulang baru. Tampilkan progress/error/cancel secara nyata.

Dependency: 0.2. Scope: M, 3–5 file; pisahkan koreksi persistensi dan presentasi learning jika lebih besar. Verifikasi: save→refresh/restart→hasil/chat/bukti; parameter update/checkpoint dipakai pada isolated learning check; latihan nyata belum membuktikan peningkatan akurasi. Lokasi: `industrial_ai/app.py`, `review.py`, `frontend/Annotation.tsx` atau controller terkait, `tests/workflow_check.py`/`review_counts_check.py`.

#### 1.2 Crossing orang dan kendaraan terverifikasi

- [x] Extend impor ledger untuk kelas kendaraan existing tanpa mengubah catatan person/schema historis; track dan crossing memiliki scope rekaman dan arah garis.
- [x] Reviewer memilih kejadian dengan frame bukti yang tepat pada waktu crossing; waktu tak diketahui tetap offset video, bukan waktu upload.
- [x] Retraction/revisi/dedup/workspace tetap aman; counts frame/track/crossing tidak digabung sebagai orang atau kendaraan unik.

Dependency: 1.1 dan 0.1. Scope: M, 3–5 file. Verifikasi: person/car/bus, crossing berulang, direction, bukti missing/stale, rollback dan akses lintas workspace pada `tests/ledger_check.py`. Lokasi: `industrial_ai/event_ledger.py`, `storage.py` bila perlu migration, `frontend/EventLedger.tsx`, ledger regression.

#### 1.3 Status helm yang dapat dipertanggungjawabkan

- [x] Review mengesahkan dipakai/tidak dipakai/unknown beserta asosiasi kepala-orang; kepala tertutup, helm di tangan dan occlusion tidak otomatis menjadi no-helmet.
- [x] Event helm terikat frame/interval, track, revisi dan bukti; status simultan dengan crossing tidak dianggap urutan fisik berdasarkan sorting saja.
- [x] Warna/label/bukti dan ledger menyatakan hal yang sama; hasil prediction/review tetap terpisah dan unknown coverage dilaporkan.

Dependency: 1.1, 1.2. Scope: M, 3–5 file. Verifikasi: fixture asosiasi helm dan review/retraction; quality dinilai pada data independen dari 0.2. Lokasi: `industrial_ai/vision.py`/`review.py`, `event_ledger.py`, event UI dan regression material.

**Bukti fase 1:** `industrial_ai/tests/ledger_v2_check.py`, legacy ledger, workflow29, security101, typecheck/build/UI suites, training objects/helmets nyata di `.tmp/` (9 checks tiap grup; parameter berubah). Kualitas dataset independen belum tersedia.

**Checkpoint 1:** satu rekaman dapat dikoreksi, disimpan, dianalisis ulang kandidat bila eligible, lalu diimpor sebagai kejadian berbukti; hasil awal tetap tersedia.

### Fase 2 — Jawaban yang mengikuti pertanyaan

#### 2.1 Filter fakta yang eksplisit

- [x] Query terstruktur mendukung rekaman/revisi, kelas, arah crossing dan rentang offset video dengan aturan boundary terdokumentasi; nol berbeda dengan tidak ada coverage.
- [x] API/UI memakai filter sama; stale/retracted/unknown tidak dipakai sebagai fakta pasti; count disertai satuan dan filter.
- [x] Bahasa chat hanya memetakan bentuk pertanyaan yang benar-benar didukung; filter ambigu/negasi/identitas/compound unsupported meminta klarifikasi atau ditolak, tidak fallback ke agregat semua rekaman.

Dependency: checkpoint 1. Scope: M, 3–5 file. Verifikasi: rentang boundary, kelas orang vs kendaraan, out-of-range, stale/retract dan akses; `tests/fact_check.py` dan ledger HTTP checks. Lokasi: `industrial_ai/fact_query.py`, `event_ledger.py`, `chat.py`/`app.py` hanya integrasi minimum, factual regressions.

#### 2.2 Bukti dan posisi video sinkron

- [x] Jawaban menyertakan event ID, sumber/revisi dan offset; klik bukti membuka frame/waktu pada rekaman dan mode hasil yang benar.
- [x] Pergantian rekaman/revisi saat request berlangsung tidak menempelkan jawaban atau bukti lama ke sumber baru; hilang/corrupt evidence tampil sebagai unavailable.
- [x] Keyboard/mobile/fullscreen tetap dapat dipakai; detail teknis diletakkan di panel lanjutan tanpa menghapus informasi penting.

Dependency: 2.1. Scope: M, 3–5 file. Verifikasi: chat orang hanya bukti orang, response race, seek/bounds, keyboard/mobile dan media regression. Lokasi: `industrial_ai/frontend/ChatPanel.tsx`, `EventLedger.tsx`, `VideoPanel.tsx` atau controller `studio.ts`, existing UI checks.

**Checkpoint 2:** pertanyaan terdukung menghasilkan count dan bukti tepat pada filter sama; angka/ID tidak dibuat oleh N-gram/Qwen.

### Fase 3 — N-gram benar-benar memakai kejadian CCTV

#### 3.1 Kontrak urutan dan label

- [x] Adapter schema baru mendukung simbol orang/kendaraan/helm yang disahkan; unit per sumber/track/session, bundling simultan, EOS/gap/unknown eksplisit dan versioned.
- [x] Training mengambil ledger valid milik workspace dengan source revisions; edit/retract membuat run turunan stale. Identitas/nama tidak menjadi token prediksi atau manifest publik.
- [x] Train/dev/test dipisah sumber asli, reviewer event bukan otomatis label novelty; label novelty memakai rubrik/provenance independen. Exposure kamera tidak disimpulkan dari jeda event.

Dependency: checkpoint 1, 0.2; bisa bersamaan dengan 2.1 setelah kontrak shared stabil. Scope: M, 3–5 file. Verifikasi: duplicate/gap/simultaneous/version mismatch/retraction dan isolasi workspace; `extensions/tests/test_event_novelty.py`, `industrial_ai/tests/novelty_api_check.py`. Lokasi: `extensions/src/event_sequences.py`, `experiments/event_novelty.py`, ledger export, tests.

#### 3.2 Eksperimen dan kalibrasi urutan

- [x] Reuse runner/registry; bandingkan frequency/unigram, KN/WB dan MKN secara dev-only dengan fixed split/units; jangan mengasumsikan MKN terbaik.
- [x] Threshold disimpan dengan model/schema/source/code fingerprints; test dijalankan sekali setelah pemilihan, reports lama tetap utuh.
- [x] Laporkan precision/recall berlabel serta false alert/jam hanya bila exposure diketahui; delay/live tidak diklaim dari full-session offline. Ukur biaya scoring/runner terpisah dari detector.

Dependency: 3.1. Scope: M, 3–5 file. Verifikasi: normalisasi, holdout sentinel, threshold boundaries, immutable receipts dan meaningful baseline; labelled replay baru memakai run ID baru. Lokasi: existing event runner/tests, benchmark/report akademik.

#### 3.3 Penjelasan skor kembali ke video

- [x] Pengguna memilih run/revisi/rekaman; UI menunjukkan model, threshold, urutan simbol, P/logP dan kontribusi NLL dengan definisi satuan, lalu membuka event/frame bukti.
- [x] Urutan jarang diberi label perlu review; no-helmet terverifikasi ditampilkan terpisah dan tidak dibatalkan oleh skor novelty rendah.
- [x] Raw JSON/provenance menjadi detail lanjutan; empty/stale/corrupt run dan unsupported simbol jelas tanpa hasil palsu.

Dependency: 3.2, 2.2. Scope: M, 3–5 file. Verifikasi: parity UI/Python, source/revision race, keyboard/mobile, unknown/gap/stale; existing Academic Lab/novelty API regressions. Lokasi: `industrial_ai/academic.py` atau read-only novelty API, `frontend/NgramLab.tsx`/`EventLedger.tsx`, UI/API checks.

**Bukti fase 3:** academic171, novelty v1/v2 HTTP, v2 source-copy grouping, bundle/EOS/NLL parity and immutable run tests. Precision/recall camera independen serta false alerts/hour tetap unavailable karena label/exposure tidak tersedia.

**Checkpoint 3:** dari video yang direview sampai penjelasan N-gram dapat digunakan end-to-end; improvement/hazard claims hanya mengikuti label dan bukti nyata.

### Fase 4 — Ringkasan dan demo yang siap dibaca

#### 4.1 Ringkasan rekaman lokal

- [x] Ekspor ringkasan dari filter/revisi ledger yang sama: periode, satuan count, observasi helm, novelty untuk review, keterbatasan dan event/frame proof.
- [x] Narasi deterministik bekerja tanpa LLM. Qwen existing tetap untuk chat; laporan memakai fakta deterministik agar tidak perlu validasi narasi tambahan.
- [x] Draft berlabel belum disahkan; revisi sumber membuatnya stale. Tidak ada pengiriman HRD/email/API eksternal atau kesimpulan identitas/bahaya dari novelty.

Dependency: checkpoint 3. Scope: M, 3–5 file. Verifikasi: parity query/export, stale/retract, deterministic facts without LLM dan akses media. Lokasi: existing chat/export path, report UI, report/fact regression yang material.

#### 4.2 Verifikasi akhir, dokumentasi dan publikasi

- [x] Demo nyata menyelesaikan upload→review→ledger→query/bukti→N-gram→ringkasan; ukur inference klip publik (3 repeats), training GPU fungsional, scoring runner dan RAM/VRAM inference; kasus crowded/quality independen dinyatakan unavailable karena belum berlabel.
- [x] Test/lint/typecheck/build/security/package lokal yang relevan lulus; CI mencakup regresi baru serta container/HTTPS dan status publik diperiksa pada commit rilis; audit dependency menyebut exception NLTK upstream secara jujur; audit hashes menjaga core/bobot/hasil dan perubahan pengguna.
- [x] Update README/checklist/report dengan kemampuan dan batas terverifikasi; source docs dirapikan tanpa rename massal, dataset/model/private footage tidak masuk GitHub. Publish main sesuai otorisasi pengguna setelah review/checks.

Dependency: 4.1. Scope: S–M per slice; pisahkan verifikasi dan publikasi jika cakupan >5 file. Verifikasi: commands di bawah, report aktual dan status exact-commit CI; bukan jaminan bebas bug/produksi.

**Checkpoint akhir:** semua task aktif yang diklaim selesai mempunyai bukti, sistem tetap berjalan, hasil lama aman; kualitas yang belum terbukti dinyatakan sebagai batas, bukan disembunyikan.

### Tambahan opsional sesudah checkpoint akhir

- [x] REPL edukasi ringan `/model <checkpoint>`, `/topk <context>`, `/score <teks>`, `/info`, `/quit`; tidak melatih/overwrite dan tidak mengubah sampler historis. Demo simbol memakai kontrak event eksplisit, bukan tokenizer kata.

Dependency: checkpoint akhir. Scope: M, 2–4 file CLI/docs/tests. Verifikasi: bad path/model menjaga sesi lama, bounded input, EOF/Ctrl-C dan parity fungsi existing; satu focused test. Lokasi perkiraan: `extensions/src/repl.py`, CLI entry minimum, test/docs. Ini tidak memblokir rilis video. Temperature/seeding/reranking/chat umum tidak menjadi task aktif.

### Data untuk makalah — tambahan 11 Oktober 2026

- [x] Ekspor 72 konfigurasi pilot bahasa ke CSV dari metrik tersimpan, tanpa evaluasi ulang test.
- [x] Run baru `cctv-symbol-order-v1-20261011`: 11 pembanding, 176 sesi, 638 target, 176 baris perbandingan urutan; sintetis terkontrol.
- [x] CSV/JSON, input/protokol/hash dan kamus data; tidak menulis makalah pengguna atau mengklaim akurasi kamera.
- [x] Tes parity NLL, split/dev selection, sensitivitas urutan, immutable output dan tamper rejection.

[Data akademik](../extensions/results/README.md). Gerbang data nyata berikut tetap terbuka.

### Evaluasi mutu yang masih memerlukan data

- [ ] Tambah rekaman lokasi target independen dengan label tracking/helm/kejadian menurut rubrik dan dasar pemrosesan data. Referensi publik kini tersedia: Construction-PPE dan SDD; belum menggantikan data pabrik.
- [ ] Evaluasi lokasi target: tracking/helm, incident precision/recall, onset/delay dan exposure untuk false alerts/hour. C2/C3 publik selesai dengan hasil negatif; tidak ada klaim keselamatan otomatis.

Ini gerbang data/evaluasi, bukan fitur runtime yang diam-diam dianggap selesai. Laporan dan batas lengkap: [Verifikasi CCTV/N-gram](../industrial_ai/reports/VERIFIKASI_CCTV_NGRAM.md).

### Command gerbang yang sudah tersedia

Jalankan hanya yang material pada setiap slice; suite penuh pada checkpoint akhir. Cache/runtime fixtures tetap di repository dan server asli tidak dipakai untuk pengujian mutasi.

```powershell
# Dari root
. .\setup_lokal.ps1
uv run --locked pytest -q
uv run --locked ruff check core extensions jalankan_notebook.py
uv run --locked ruff format --check core extensions jalankan_notebook.py
uv run --locked ty check core/src extensions/src extensions/experiments jalankan_notebook.py
uv build --out-dir .tmp/packages

# Dari industrial_ai, setelah environment existing disiapkan
Set-Location industrial_ai
. .\setup_lokal.ps1
npm run typecheck
npm run check
npm run build
uv run --locked python tests/ledger_check.py
uv run --locked python tests/fact_check.py
uv run --locked python tests/novelty_api_check.py
uv run --locked python tests/academic_check.py
uv run --locked python tests/workflow_check.py
uv run --locked python tests/tracking_check.py
uv run --locked python tests/security_check.py
uv run --locked python tests/package_check.py

git diff --check
```

Tambahkan scoped Ruff/format/Ty untuk file studio yang berubah sesuai konfigurasi existing; quality assertions baru harus menguji perilaku, bukan meniru implementasi. Training/inference nyata dijalankan dengan fixture terisolasi pada checkpoint yang menyentuh learning; quality dataset nyata tetap berbeda dari smoke fixture.

---

## Riwayat checklist sebelumnya

Status berikut merupakan snapshot bertanggal. Task lama di luar fokus tidak otomatis aktif; tidak ada fitur atau data yang dihapus oleh rencana baru.

# To-do Video Insight Lokal

Target: demonstrasi/portofolio lokal. Diperbarui 9 Oktober 2026.
Demo upload/tracking/chat sudah berjalan dan diuji. Checklist ini menunjukkan
pekerjaan aktif; kriteria seluruh fase ada di [roadmap lengkap](roadmap_checklist.md).

## Status demo lokal — 8 Oktober 2026

- [x] Subproyek terpisah; dependency Python/npm terkunci dan cache lokal.
- [x] Upload tervalidasi; dua video H264 asli/tracking dengan kontrol sinkron.
- [x] Deteksi orang/mobil/bus/truk/motor/sepeda, ByteTrack dan detector helm terpisah.
- [x] Counting terlihat/lintasan, bukti sesuai kelas, history dan unduhan MP4/JSON.
- [x] Chat Qwen3-1.7B lokal dan pilot LoRA nyata; CPU/Auto RTX 4060 teruji.
- [x] Qwen dasar berjalan tanpa adapter; fine-tuning opsional saat setup.
- [x] Anotasi kotak AI/manual, label khusus, nama/warna dan draft otomatis.
- [x] Klik kiri menggambar; klik kanan/Escape membatalkan interaksi/kotak baru.
- [x] Anotasi layar penuh dengan sidebar label/warna/edit/hapus dan kontrol keyboard.
- [x] Preview mengikuti kotak tanpa training ulang saat play/simpan/query.
- [x] Tracking koreksi tersimpan lintas restart dan ekspor MP4 per revisi.
  Rentang yang disiapkan tersimpan; label tetap perlu ditinjau sebelum training.
- [x] CLI segmentasi video panjang, seleksi frame dan draft label objek/helm.
  Split dataset memakai identitas video asal untuk mencegah kebocoran antarsegmen.
- [x] Koreksi lengkap dipakai dashboard/chat/JSON pada posisi yang disahkan.
- [x] Ringkasan mengikuti isi video dan pertanyaan orang memakai bukti orang.
- [x] Dataset YOLO dengan provenance; training kandidat terpisah dari dua sumber.
- [x] Tema sistem/terang/gelap dan pemeriksaan alur browser/mobile.
- [x] npm setup untuk Python/model lokal; dokumentasi dan npm start tersedia.
- [x] 71 pemeriksaan E2E dan 31 tracking checks, self-check/review-count checks,
  npm check/build/audit, Ruff/Ty serta build/audit paket lulus.
- [x] Source penting di GitHub; model, video pengguna dan hasil runtime tetap lokal.
- [x] 1.583 hash hasil/model/artefak akademik lama identik saat publikasi.

Bukti: [Verifikasi publik](../industrial_ai/reports/VERIFIKASI_PUBLIK.md).
Tes membuktikan alur aplikasi berjalan; belum mengukur akurasi pada semua kondisi.

## Perbaikan review dan belajar — 9 Oktober 2026

- [x] Antrean sampel, draft, deteksi meragukan dan awal target tracker hilang.
- [x] Approval objek/helm terpisah; edit geometri membatalkan approval terkait.
- [x] Training otomatis setelah seluruh antrean kelompok selesai dan dua sumber berbeda.
- [x] Snapshot disahkan, fingerprint konsisten, split menurut sumber asli.
- [x] Update parameter nyata teruji pada CPU/RTX; hasil baru memakai checkpoint kandidat.
- [x] Hasil awal tetap tersedia; koreksi pengguna diberi label terpisah dari hasil model.
- [x] Retry upload lengkap, cancel kooperatif dan ekspor CPU asinkron dengan progress.
- [x] Kandidat selesai dapat menganalisis ulang setelah followup gagal tanpa training ulang.
- [x] CI kualitas/API/media/training/paket serta audit dependency dan Dependabot.
- [x] README, CONTRIBUTING, SECURITY dan MIT source asli dengan atribusi pihak ketiga.
- [x] Struktur kode dipertahankan; peta repository dan navigasi dokumentasi diperjelas.

Bukti dan batas: [Verifikasi review/belajar](../industrial_ai/reports/WORKFLOW_REVIEW_BELAJAR.md).
Status CI berjalan ditampilkan pada [GitHub Actions](https://github.com/Maliq-dlt/N-Gram/actions/workflows/ci.yml).
Fine-tuning terbukti berjalan, tetapi peningkatan akurasi memerlukan evaluasi independen.

## Fondasi akses dan database — 9 Oktober 2026

- [x] Login, admin/reviewer/viewer, pemisahan resource/model menurut workspace.
- [x] SQLite authoritative, migrasi tanpa menghapus media, revisi dan backup database.
- [x] CSRF seluruh mutasi, pembatasan login/API, cookie HttpOnly dan header keamanan.
- [x] Audit HMAC/anchor, uji perubahan/truncation log dan restore database.
- [x] Auth TypeScript strict, kontrol viewer, menu akun dan informasi lanjutan dilipat.
- [x] Profil readonly dari identitas sesi nyata; password scrypt bersalt dan rotasi
  seluruh sesi/cookie/CSRF tanpa menghapus video atau anotasi.
- [x] Avatar/aksi akun dari adaptasi Origin UI dropdown-menu #393 dan mode hasil
  segmented-control #23552 memakai elemen native; verifikasi UI terbaru dicatat terpisah.
- [x] Docker CPU/Compose/Caddy dan CI lint/typecheck/API/security/container.
- [ ] Deployment HTTPS dengan domain nyata dan uji pemulihan seluruh media.
- [ ] Audit independen/pentest; external anchor, kuota dan worker shared sebelum skala besar.
- [ ] Enrollment wajah/PAD dan aturan absensi setelah data berizin/evaluasi tersedia.

Rincian: [fase hardening dan absensi](../industrial_ai/docs/HARDENING.md).
Status centang CI berarti pipeline tersedia; hasil run dicatat pada laporan verifikasi.

## Perbaikan berikutnya pada demo

- [ ] Ukur tracking kerumunan dengan video independen: ID switch/IDF1 dan error hitungan.
  Occlusion/objek berdekatan masih dapat menyebabkan kotak hilang atau ID tertukar.
- [ ] Perluas dataset helm/APD dan ukur FP/FN pada data yang tidak dipakai training.
- [ ] Uji setup dari clone kosong, termasuk unduhan semua model; publikasi baru
  menguji setup library dan inferensi memakai bobot lokal yang sudah tersedia.
- [ ] Tinjau label publik objek/helm, lalu evaluasi kandidat pada sumber terpisah.
  [Pipeline dan sumber data](video_training_pipeline.md); auto-label tetap draft.
- [x] Audit revisi dan backup/restore database ke direktori baru. Media tetap perlu backup terpisah.
- [ ] Bandingkan chat dasar/LoRA pada 100 prompt dengan rubrik dan decoding yang sama.

Prioritas awal: evaluasi kerumunan, data helm dan reproduksi setup. Model lebih
besar/ReID baru dipilih setelah perbandingan kecepatan/akurasi yang terukur.

## Fitur lanjutan yang belum dikerjakan

- [ ] Input foto sebagai tambahan upload video.
- [ ] Satu webcam/CCTV aktif, reconnect dan pengujian beban berkelanjutan.
- [ ] Detector/OCR plat, foto kendaraan utuh dan zoom/crop plat.
- [ ] Absensi QR, registry peserta, shift dan query absensi.
- [ ] Pencarian SOP dengan rujukan dokumen.
- [ ] Identitas wajah sebagai pengembangan opsional setelah evaluasi khusus.

Daftar ini adalah perluasan proyek; bukan syarat agar demo video/chat dapat digunakan.
Gate fase lengkap tidak dicentang hanya karena sebagian implementasi tersedia.

## Source dan panduan

- [Aplikasi di GitHub](https://github.com/Maliq-dlt/N-Gram/tree/main/industrial_ai).
- [README dan setup](../industrial_ai/README.md).
- [Rencana pengembangan](plan.md).
- [Checklist rinci seluruh fase](roadmap_checklist.md).

Bobot/adapter tidak diunggah. Clone baru memakai Qwen dasar; fine-tuning lokal
tersedia secara terpisah. Hasil lama tidak dihapus atau ditimpa oleh publikasi.


## Perbaikan referensi UI — 2026-10-10

- [x] Login nyata tanpa kredensial publik dan pendaftaran contoh.
- [x] Logo Split V dipilih pengguna; sumber SVG dan panduan di docs/brand.
- [x] Tema gelap/terang lembut, toggle di header, opsi mengikuti sistem di profil.
- [x] Nama/foto profil disimpan melalui API terotorisasi ke SQLite.
- [x] Indikator password, pengungkapan password dan rotasi sesi tetap berfungsi.
- [x] Orb lokal dalam chat dan loading kerumunan selama proses yang sebenarnya.
- [x] Regression profil/animasi masuk CI; aset lokal masuk wheel/sdist.

## Penambahan motion — 2026-10-10 (milestone sebelum migrasi React)

- [x] Loader minimum 3,2 detik sesuai permintaan pengguna, menunggu data nyata;
  reduced motion tanpa tambahan durasi, error langsung dan pembatalan sesi stale.
- [x] Lenis 1.3.26 dan Framer Motion 14.1.0 dom/mini, bundle lokal ~30,5 KB
  oleh esbuild 0.28.2; tanpa React runtime.
- [x] Circle tema native 720 ms; fallback WebView wipe 560 ms + fade 160 ms.
- [x] Lifecycle scroll dialog/fullscreen/hidden/signed-out/reduced motion dan
  cleanup animasi stale diuji; area scroll bersarang tetap native.
- [x] Verifikasi lokal: tujuh suite UI, typecheck, build dan audit lulus;
  baseline HTTP terakhir 32 pemeriksaan, terpisah dari suite motion.
Milestone motion ini digabungkan ke publikasi migrasi React di bawah.

## Migrasi React dan perbaikan scroll/tema — 2026-10-10

- [x] React/react-dom/types exact 19.3.0, bundle production lokal; audit dependency 0.
- [x] Halaman React TSX, auth/controller media/editor TypeScript strict.
- [x] Tampilan data dinamis LiveViews.tsx dan regression controller.
- [x] Circle snapshot UI nyata 900 ms, file/password kosong, inert/ID terpisah.
- [x] Wheel reversal Lenis membuang target lama; nested scroll tetap native.
- [x] HTTP deployment 36 pemeriksaan lulus pada snapshot React lokal.
- [x] Sembilan suite UI, strict typecheck/build dan audit 0.
- [x] Backend91 security/36 HTTP, profil/storage dan wheel/sdist source equality setelah auth akhir.
- [x] Browser circle kedua arah, scroll, refresh tanpa loader, login/logout, chat React dan fullscreen.
- [x] Loader hanya login/logout eksplisit; refresh/restorasi sesi tanpa delay.
- [x] Pipeline CI academic/studio/container aktif pada main; hasil setiap commit tersedia di [GitHub Actions](https://github.com/Maliq-dlt/N-Gram/actions/workflows/ci.yml).
