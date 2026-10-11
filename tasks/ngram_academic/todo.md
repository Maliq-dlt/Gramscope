# Checklist — N-gram Academic Lab

> **Scope aktif, 11 Oktober 2026:** pekerjaan berikut berfokus pada N-gram dan kejadian CCTV. [Rencana aktif](../plan.md) dan [task aktif](../todo.md#pekerjaan-aktif--n-gram-dan-cctv) mengambil prioritas; blueprint/checklist berikut tetap menjadi riwayat implementasi dan evaluasi. Usulan di luar fokus tidak otomatis dijalankan.

[Penjelasan dan arsitektur](plan.md) · [Status video yang terpisah](../todo.md)

Tanggal: **10 Oktober 2026**. Checklist diperbarui setelah implementasi, tiga pilot eksploratif dan 72 benchmark model. Kotak tercentang berarti bukti implementasi/gate yang disebut tersedia; kotak kosong menunjukkan kriteria yang belum lengkap, bukan menyatakan seluruh modul belum dibuat. [Hasil dan biaya](../../extensions/README.md) · [Verifikasi publik](../../extensions/reports/VERIFICATION.md).

| Lingkup | Status terverifikasi | Batas yang tetap terbuka |
| --- | --- | --- |
| Registry/CLI/metode | Run eksklusif, checkpoint v2, score/info/list, WB/MKN/EM dan tes correctness | Reference NLTK ordinary KN tidak memvalidasi MKN |
| Pilot bahasa | Brown/Reuters120 + Wikipedia Indonesia40; dev selection, vocabulary train-only, test receipts sekali | Prior exposure unknown; independent test groups11/12/4, belum corpus konfirmatori eksternal |
| Uncertainty/biaya | Group CI, diagnostik/generasi, 72 native-memory single-CPU subprocess benchmarks | Koreksi target CI turunan; metrik leksikal bukan human quality, latency bukan lintas mesin |
| Lab browser | Explorer/top-k/generation, metric table/filter/CSV, provenance/dev trace | Gate browser/accessibility lengkap mengikuti bukti verifikasi, bukan asumsi dari source |
| CCTV/ledger | Review→ledger, workspace/revisi/stale/retract, per-track symbols dan novelty runner offline | Belum mutu novelty berlabel nyata, exposure/onset, false alerts/hour/delay atau causal live |
| Absensi | Linkage manual admin, ambiguous identity unknown, facts dengan provenance | Scanner badge/QR, face/liveness, arbitrary time/subject-filtered chat belum tersedia |

**167 tes akademik lulus** pada verifikasi akhir. Coverage source akademik **80,83%** gabungan line+branch; bukan coverage seluruh repo atau akurasi model. Video/chat isolated E2E **71 passed**, bukan validasi kualitas pabrik. Source delapan file tiap pilot diarsipkan sebelum future target-group fix; hasil lama tidak direvaluasi. Original blueprint berikut dipertahankan, tetapi dependency/gate tidak berarti seluruh cakupan domain selesai.

Setiap task baru wajib lolos tes yang material, `git diff --check`, lint/typecheck source yang berubah, dan build bila packaging terpengaruh. Hash core/hasil lama diperiksa pada setiap checkpoint. Command akademik diawali `. .\setup_lokal.ps1`. Angka keberhasilan ilmiah tidak dijanjikan sebelum eksperimen.

## Fase 0 — Setup yang diverifikasi

- [x] **0.1 Inventaris source dan hasil:** baca spesifikasi/core/extensions/CLI, identifikasi KN satu diskon dan preset interpolation; pisahkan CCTV/Qwen dari N-gram.
- [x] **0.2 Tools:** sync root `.venv` melalui lock; tambah pytest-cov dev; tidak mengganti versi scientific dependency existing.
- [x] **0.3 Baseline dan rencana:** 48 tes lulus, coverage dicatat, Ruff/format/Ty/build/CLI diperiksa; plan dan task disimpan tanpa menimpa checklist CCTV.

**Checkpoint 0:** coverage display 68% (gabungan line+branch), bukan akurasi model. Bukti lokal pada `.tmp/ngram-plan/`; hash/links/diff akhir ditulis pada `verification.json`. Ini snapshot awal sebelum implementasi; status terbaru ada pada tabel di atas.

## Fase 1 — Eksperimen aman

### 1.1 Run registry dan output runner

Dependency: 0.3. Scope: M, 3–4 file. Lokasi: `extensions/experiments/run.py`, helper registry di `extensions/experiments/` (baru), tes di `extensions/tests/` (baru).

- [x] `run_id` tervalidasi membuat direktori eksklusif; path traversal/collision ditolak. Hasil historis tidak dipindah, dihapus atau ditimpa.
- [x] Manifest config/corpus/split/code/dependency fingerprints dan status atomik tersedia; failure/resume tidak menyamar sebagai completed atau mengevaluasi test setelah model berubah.
- [x] Tiny synthetic integration run dan simulasi interrupted write membuktikan isolation; hash hasil lama tetap sama.

Verifikasi: `uv run --locked pytest extensions/tests -q`, dengan tes registry dan filesystem failure; tidak memakai corpus/test historis untuk smoke.

### 1.2 Semua analisis memakai run yang dipilih

Dependency: 1.1. Scope: M, 4–5 file. Lokasi: `extensions/experiments/analyze.py`, `profile.py`, `compare_nltk.py`, tes integration.

- [x] Analyzer/profiler/reference membaca run yang eksplisit dan menulis turunan ke run itu; default historis tetap dapat dibaca tanpa overwrite.
- [x] Schema/config/fingerprint yang tidak cocok menghasilkan error jelas; run partial tidak dibaca sebagai hasil final.

Verifikasi: `uv run --locked pytest extensions/tests -q`; synthetic run → analisis → inspeksi artefak dan hash historis. **Checkpoint 1A:** semua penulis output baru terisolasi sebelum eksperimen berikutnya.

### 1.3 Checkpoint v2 dan provenance

Dependency: 1.1. Scope: M, 3–4 file. Lokasi: `extensions/src/cli.py`, `extensions/src/models.py`, `extensions/tests/test_cli.py`, dokumen schema extensions.

- [x] V2 memuat format/algorithm/preprocessing version, effective model parameters, trace/manifest reference dan source/split/vocabulary fingerprints; v1 tetap bisa dibaca dengan validasi schema lama.
- [x] Round-trip memberi peluang yang sama; unknown key/version, invalid count/weight, oversize/corrupt gzip dan partial write ditolak, tanpa pickle atau overwrite.

Verifikasi: `uv run --locked pytest extensions/tests/test_cli.py -q`; build dan pemeriksaan isi wheel/sdist. V2 belum melonggarkan v1.

### 1.4 CLI batch score dan metadata

Dependency: 1.2, 1.3. Scope: S–M, 2–3 file. Lokasi: `extensions/src/cli.py`, `extensions/tests/test_cli.py`, `extensions/README.md`.

- [x] Batch scoring streaming menghasilkan token count, NLL/CE/PP sesuai satuan dan tokenizer manifest; Stupid Backoff memakai score loss/PP N/A. Input kosong/tidak valid/terlalu besar teruji.
- [x] Info/list membaca sidecar bounded yang terikat ke artifact/run tanpa load seluruh counts; metadata stale/corrupt terdeteksi dan tidak dipercaya sebagai model valid.

Verifikasi: tes CLI subprocess pada corpus mini berizin internal, stdout schema/exit code, dan `ngram-lm --help`. **Checkpoint 1B:** output aman, legacy checkpoint kompatibel, CLI failure paths yang penting tercakup.

## Fase 2 — Metode probabilistik

### 2.1 Interpolated Witten–Bell

Dependency: 1.3, 1.4. Scope: M, 3–4 file. Lokasi: `extensions/src/models.py`, `pipeline.py`, CLI schema v2, `extensions/tests/test_models.py`.

- [x] Formula N/(N+T), T/(N+T), base distribution dan empty-history backoff terdokumentasi; baseline lama tidak berubah peluangnya.
- [x] Hitungan manual, BOS/EOS/UNK dan unseen/all-singleton contexts lulus normalisasi/nonnegatif/finite pada vocabulary prediksi.

Verifikasi: `uv run --locked pytest extensions/tests/test_models.py -q`; round-trip checkpoint untuk metode baru. Tidak tuning pada test.

### 2.2 Modified Kneser–Ney

Dependency: 2.1. Scope: M, 3–5 file. Lokasi: models/pipeline/schema v2, tes MKN independen (baru), catatan rumus extensions.

- [x] Sumber teknis estimator diverifikasi; raw highest-order dan lower continuation effective counts, count-of-counts per orde, D1/D2/D3+ serta context backoff mass mengikuti kontrak plan.
- [x] Fallback missing/invalid buckets serta epsilon policy eksplisit; contoh independently derived, unseen contexts, boundaries, finite/nonnegative dan normalization lulus. Ordinary KN tetap metode baseline.
- [x] Pengujian menunjukkan checkpoint deterministic/round-trip; NLTK ordinary KN tidak dipakai untuk klaim ekuivalensi MKN.

Verifikasi: `uv run --locked pytest extensions/tests -q`; inspeksi contoh counts dan peluang dengan hitungan tangan. **Checkpoint 2A:** correctness sebelum run corpus besar.

### 2.3 EM untuk bobot interpolasi global

Dependency: 2.1, 1.3. Scope: M, 3–4 file. Lokasi: `extensions/src/pipeline.py`, `models.py`, tes tuning (baru), schema trace v2.

- [x] Komponen tetap; update memakai frekuensi token dev, bobot sum=1/nonnegatif; zero denominator, tolerance, cap dan initialization tercatat.
- [x] Log-likelihood dev tidak menurun di luar toleransi; tests sentinel membuktikan test tokens tidak dibaca saat tuning; preset lama tersedia untuk pembanding.

Verifikasi: tes synthetic EM termasuk data duplikat untuk membedakan token-weighted dan unique-event update. **Checkpoint 2B:** berlaku setelah seluruh task 2.1–2.3 lulus; tiga metode baru teruji; bukti peningkatan PP dibatasi pada pilot eksploratif dalam laporan, bukan janji universal.

## Fase 3 — Dataset dan evaluasi

### 3.1 Protokol dan grouped loader

Dependency: 1.2, 2.3. Scope: M, 3–5 file. Lokasi: loader/split extensions (baru), `pipeline.py`, tes leakage (baru), protokol run.

- [x] Provenance/lisensi/file hashes/document IDs dan duplicate policy tersedia; group train/dev/test disjoint; preprocessing vocabulary/bins hanya fit train.
- [x] Corpus/task/tokenizer/UNK/metrics/grid/stopping policy direkam sebelum fitting/test; pilot dan test historis ditandai exploratory. Holdout konfirmatori independen belum tersedia.

Verifikasi: tes deliberate duplicate/group leakage, reproducible split dan corpus version mismatch. Core split tidak disentuh.

### 3.2 Eksperimen in-domain terkontrol

Dependency: 3.1, seluruh fase 2. Scope: M, 2–4 file. Lokasi: runner/pipeline extensions, registry receipts, laporan run (baru).

- [x] Baseline dan metode baru dinilai pada tokenization/target vocabulary/padding yang sama; grid tidak diranking lintas UNK threshold yang berbeda.
- [x] Semua kandidat dipilih dev; final artifact/protocol dibekukan dan test dibuka sekali per final model. Receipt final dipertahankan; run ID yang pernah dicoba tidak dipakai ulang untuk retuning/test.

Verifikasi: dry run synthetic end-to-end, then train/dev pilot, kemudian final run sesuai protocol; manifest config/tuning/final receipt diaudit. Tidak menjalankan runner historis dengan output lama.

### 3.3 Cross-domain dan genre

Dependency: 3.2. Scope: M, 3–4 file. Lokasi: grouped loaders/runner, CLI evaluate policy v2, laporan domain.

- [x] Brown→Reuters dan arah balik eksplisit sebagai domain-shift protocol; source-model/vocabulary/preprocessing immutable. Unduhan Reuters berprovenance dan cache lokal.
- [ ] Jika adaptation dibandingkan, semua metode berbagi target holdout yang sama dan hanya memakai target train/dev yang diizinkan; OOV/coverage dan genre dilaporkan.

Verifikasi: incompatible corpus evaluation ditolak secara default; cross-domain mode menyimpan **dua** source/target fingerprints tanpa mematikan pemeriksaan integritas. **Checkpoint 3:** hasil konfirmatori versus exploratory terbaca jelas.

## Fase 4 — Ketidakpastian, kualitas dan biaya

### 4.1 Paired grouped bootstrap

Dependency: 3.2. Scope: S–M, 2–3 file. Lokasi: analyzer uncertainty extensions (baru), tes mini, laporan run.

- [x] Token-weighted CE/PP dan paired per-document NLL differences benar; resampling mempertahankan group/paired records dengan seed dan jumlah resamples tercatat.
- [x] CI 95% dan effect size dilaporkan; seed split yang berbagi corpus tidak diperlakukan sebagai sampel independen. Test digunakan untuk analisis model tetap, tidak pemilihan baru.

Verifikasi: synthetic unequal-length documents dan identical-model difference=0; agreement hitungan tangan/NumPy.

### 4.2 Error, entropi dan generasi

Dependency: 3.2, 4.1. Scope: M, 3–4 file. Lokasi: `extensions/src/quality.py`, experiment analyzer, tes quality, laporan.

- [x] NLL by train-frequency/length/genre, dev-vs-test gap dan context entropy memakai distribusi probabilistik yang terdefinisi; zero probability ditangani tanpa angka palsu.
- [x] Distinct-3, repeat-ngram rate, unigram generated-vs-reference entropy dan UNK tersedia; seed tersimpan pada protocol, diversity tidak diklaim sebagai koherensi.
- [ ] Statistik alasan EOS/cap tiap sampel generasi riset belum disimpan terpisah; source sampler beku membatasi 40 token. Lab menampilkan seed/cap/stop reason per permintaan.

Verifikasi: `uv run --locked pytest extensions/tests/test_quality.py -q`; fixtures mini termasuk repetisi/kalimat kosong/panjang berbeda.

### 4.3 Benchmark CPU dan efisiensi

Dependency: 3.2, 1.4. Scope: M, 2–4 file. Lokasi: `extensions/experiments/profile.py`, `extensions/src/sparse.py` bila pengukuran membenarkan, tes profiler.

- [x] Build/score/top-k p50/p95, corpus/model size, whole-process peak memory dan ukuran count index dibedakan; warmup, repeats, platform dan load kondisi dicatat.
- [x] Cache/pruning/parallel runner/higher order hanya ditambah jika bottleneck terukur; distribusi/akurasi baseline tidak berubah diam-diam dan tradeoff dilaporkan.

Verifikasi: benchmark fixed workload + equality check dan memory-counter validity; tidak memakai angka object size sebagai klaim peak RAM. **Checkpoint 4:** bukti manfaat/biaya dan keterbatasan siap ditampilkan.

## Fase 5 — Lab edukasi di studio

### 5.1 Contract scoring Python ↔ UI

Dependency: 1.4, 2.3. Scope: M, 3–5 file. Lokasi: scoring extensions, backend router studio (baru), dependency lock studio bila dibutuhkan, contract tests.

- [x] Input context/order/model/run tervalidasi dan dibatasi, response numeric/trace schema versioned; selected checkpoint load/release lifecycle teruji tanpa memuat YOLO/Qwen untuk lab.
- [x] Paket N-gram lokal terkunci kompatibel di environment studio; auth/CSRF/workspace isolation tetap berlaku, path/model upload bebas tidak diterima.

Verifikasi: contract/HTTP tests melalui server fixture lokal; root scientific lock dan studio lock tidak saling menimpa. Tidak mengubah password/sesi owner untuk testing.

### 5.2 Playground dan probability explorer

Dependency: 5.1. Scope: M, 3–5 file. Lokasi: `industrial_ai/frontend/` lab components (baru), styling existing, UI contract tests.

- [x] Top-k, sliding context, token generation dan seed/stop reason memakai nilai backend; count/denominator/P/logP/NLL/LL/PP ditampilkan dengan formula substitusi dan underflow demo.
- [x] Keyboard/mobile dan PP N/A diperiksa; reduced motion melalui suite otomatis, tidak dipaksakan di IAB. Selector memakai langkah generasi tersimpan tanpa membuka test/training ulang. Cakupan browser rinci ada pada verifikasi.

Verifikasi: `npm run typecheck`, `npm run check`, `npm run build` di `industrial_ai`, plus real browser comparison dengan fixture Python deterministik. Tidak menambah landing page.

### 5.3 Experiment lab

Dependency: 5.2, 4.1–4.3. Scope: M, 3–4 file. Lokasi: lab UI, read-only run-export API, regression tests.

- [x] Heatmap/tabel/filter hanya membaca completed run yang sesuai schema; corpus/split/vocabulary/run dan CI terlihat, missing/partial/error state jelas.
- [x] Jejak dev dan validasi ordinary KN vs NLTK tersedia; metode berbeda target space tidak diranking bersama dan MKN tidak diberi validasi NLTK palsu.

Verifikasi: numeric values/csv-export parity, workspace isolation, keyboard/mobile/browser; checkpoint fase 5 menyertakan UI suites dan root tests. **Checkpoint 5:** demo dapat menjelaskan mekanisme, bukan hanya menampilkan skor.

## Fase 6 — Autocomplete dan paket akademik

### 6.1 Data Indonesia/domain

Dependency: 3.1. Scope: M, 2–4 file. Lokasi: loader/config preprocessing extensions (baru), manifest data, tes split.

- [x] Sumber teks berizin tercatat, batas dokumen/template-family dan duplicate policy jelas; tidak menyerap percakapan/identitas pengguna otomatis.
- [x] Tokenizer/normalizer domain terversi terpisah dari core; prefix/suffix/UNK policy dan locked holdout ditetapkan sebelum evaluasi.

Verifikasi: data sample/encoding/boundary/duplicate tests dan provenance audit. Pilot kini memakai Wikipedia Indonesia API plaintext CC BY-SA 4.0 dengan atribusi dan manifest; tidak mengambil data pribadi.

### 6.2 Autocomplete yang diukur

Dependency: 6.1, 4.3, 5.1. Scope: M, 3–5 file. Lokasi: top-k extensions, evaluasi autocomplete, UI input lab, tes ranking.

- [x] Unigram, ordinary KN dan model dev-selected dibandingkan dengan top-1/3/5 accuracy, MRR, OOV/coverage dan p50/p95 CPU latency pada prefix/targets yang sama.
- [x] Saran bisa diabaikan/dipilih dengan keyboard; tidak menjadi jawaban fakta atau identitas. Prefix/no-match diuji pada backend, keyboard pemilihan diuji browser.

Verifikasi: exact ranking fixtures + split-safe offline benchmark, browser autocomplete dan typed API parity.

### 6.3 Laporan, reproducibility dan CI akademik

Dependency: fase 1–5 serta 6.1–6.2 selesai. Scope: M, 3–5 file. Lokasi: laporan akademik baru dalam extensions, `extensions/README.md`, CI academic existing, root navigation, public verification.

- [x] Rumus, hasil aktual, efek/CI, biaya, sumber/lisensi, ancaman validitas dan hasil negatif jelas; hasil historis tidak ditulis ulang sebagai hasil baru.
- [x] Dua wheel dipasang ke environment baru, memakai dependency lokal existing; smoke corpus mini/API/assets lulus. Lock root/studio diverifikasi.
- [x] CI remote [38038065071](https://github.com/Maliq-dlt/N-Gram/actions/runs/38038065071) pada commit `47dacf8` lulus: academic, studio dan container/HTTPS. Audit NLTK memakai exception spesifik serta guard, bukan klaim dependency patched.
- [x] Source/docs penting dipublikasi ke main setelah review; private data, weights dan cache tidak ikut. Audit 188 berkas core/hasil/perubahan pengguna tetap identik.

Verifikasi: root pytest/Ruff/format/Ty/build/package audit; reproducibility pada source mini; exact published commit CI bila publikasi dilakukan. **Checkpoint 6:** proyek akademik kuat selesai; CCTV/absensi berikut adalah aplikasi tambahan.

## Fase 7 — Jembatan CCTV offline

### 7.1 Ledger kejadian dan revisi

Dependency: 6.3. Scope: M, 3–5 file. Lokasi: SQLite schema/migration studio, reviewed event export, tests ledger/provenance (baru).

- [x] Transaksi/constraints menyimpan workspace, session, time/timezone, event/model/review/revision/evidence; draft/auto-label tidak disahkan otomatis dan original tidak ditimpa.
- [x] Review/correction/retraction memperbarui current projection serta invalidasi turunan stale; query lintas workspace dan orphan evidence ditolak.

Verifikasi: migration/rollback/duplicate/retracted/stale/workspace tests dengan fixture; tidak memigrasikan data produksi tanpa backup/verifikasi migration terlebih dulu.

### 7.2 Eventization dan sequence dataset

Dependency: 7.1, 3.1. Scope: M, 3–4 file. Lokasi: event adapter extensions (baru), fixture exporter, grouped dataset/tests.

- [x] Unit sequence per observed track/recording/session, alphabet/boundaries enter/exit/unknown, camera-gap session, dedupe dan simultaneous ordering deterministik; tidak satu event per frame.
- [ ] Duration bins belum ditambahkan: membutuhkan train-fitted bins dan exposure/onset evidence; ceiling ini eksplisit pada source runner.
- [x] Derivatives/window/frame/crop satu rekaman tetap dalam satu split; ID pribadi disimpan di provenance, tidak sebagai predictive token.

Verifikasi: replay fixtures dengan FPS/timestamp variasi, multi-event simultan, camera gap, missing helmet observation, group leakage tests serta dua track terinterleaving `ENTER(A), HELMET_UNKNOWN(B), EXIT(A)` yang harus tetap terpisah. Track pecah/ambigu tidak digabung otomatis.

### 7.3 Model urutan tidak biasa

Dependency: 7.2, 4.1. Scope: M, 3–5 file. Lokasi: sequence runner/evaluator extensions, read-only UI result, fixture tests.

- [x] Unigram/frequency threshold, bigram dan dev-selected N-gram dibandingkan; threshold berasal calibration/dev, score memiliki boundary/units yang jelas.
- [ ] Dengan episode test berlabel, laporkan precision/recall, false alerts/hour dan delay pada held-out recordings/kondisi. Tanpa label independen, hanya novelty diagnostics, tidak klaim hazard detection.
- [x] Offline/future-frame assumptions dinyatakan; live/real-time baru boleh diklaim setelah causal replay dan end-to-end latency diverifikasi.

Verifikasi: labelled synthetic cases untuk correctness, lalu dataset nyata berizin untuk kualitas; baseline dan confidence intervals dilaporkan. **Checkpoint 7:** jalur simbol/replay terimplementasi; kualitas pada rekaman independen masih terbuka.

## Fase 8 — Catatan absensi terverifikasi

### 8.1 Verified identity linkage

Dependency: 7.1. Scope: M, 3–5 file. Lokasi: attendance records/linkage storage studio (baru), API/UI verification, auth/record tests.

- [x] Badge/QR authorized atau manual-verified linkage mencatat source ID, scope/time, verification status, verifier dan evidence; track ID/display name tidak menjadi employee ID otomatis.
- [x] Duplicate/ambiguous/missing/retracted linkage menjadi unknown/review; identitas sensitif terlindungi role/workspace, tidak masuk publik/run manifest.

Verifikasi: ambiguity, revocation, authorization, timezone/dedup dan source lineage fixtures. Face enrollment, face fine-tuning, liveness dan anti-spoofing tidak termasuk task ini.

### 8.2 Query fakta dan jawaban berbukti

Dependency: 8.1, 7.1, 6.2. Scope: M, 3–5 file. Lokasi: validated query module studio, `industrial_ai/chat.py`, evidence UI, factual-answer tests.

- [x] Count/attendance yang didukung berasal query deterministik; jawaban mencantumkan event ID/timestamp/provenance. Stale/retracted dan ambiguous identity tidak dipakai sebagai fakta baru.
- [ ] Arbitrary time/subject filter belum didukung; query tersebut ditolak dengan pesan jelas, tidak dihitung sebagai agregat semua catatan.
- [x] N-gram hanya autocomplete/sequence scoring; Qwen hanya merangkai bahasa. Lintasan tidak berarti hadir sepanjang shift; personal/negative/compound/counting filters yang tidak didukung ditolak dan regresi HTTP lulus.

Verifikasi: question→exact expected facts/provenance, unrelated entity regression, stale corrections, unsupported query dan access isolation tests; suite studio dan root tetap lulus. **Checkpoint 8:** ledger dan fakta terbatas tersedia; temporal/subject-filtered chat umum serta gate terakhir tetap dibatasi, tanpa klaim HR/biometrik produksi.

## Sesudah rencana ini

- Biometrik/liveness: kebutuhan kamera, izin peserta, data, error rates, spoof dataset dan keputusan verifikasi direncanakan sebagai proyek tersendiri bila diminta.
- Parallel runner, cache berlapis, pruning, n>4, external MKN benchmark dan database server baru hanya masuk ketika measurement fase 4 membenarkan biaya.
- Council tetap dihentikan. Review dilakukan dalam workspace Codex; tidak mengirim ke OpenCode.
