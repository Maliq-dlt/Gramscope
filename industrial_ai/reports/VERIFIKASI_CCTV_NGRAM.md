# Verifikasi CCTV dan N-gram

Tanggal: **11 Oktober 2026** · target: demonstrasi lokal Windows.
[Penggunaan](../README.md#kejadian-cctv-dan-penjelasan-n-gram) · [Kontrak event](../docs/EVENT_CONTRACT.md) · [Checklist](../../tasks/todo.md) · [CI](https://github.com/Maliq-dlt/Gramscope/actions/workflows/ci.yml)

## Hasil yang dapat digunakan

**Video → review → ledger → query/bukti → N-gram → ringkasan.** Detector/tracker membaca piksel. Manusia mengesahkan kejadian orang/kendaraan/helm. N-gram membaca simbol per track/session dan menjelaskan P, log P, NLL serta EOS; skor jarang meminta review, bukan kesimpulan bahaya.

| Bagian | Perilaku yang diverifikasi |
| --- | --- |
| Koreksi | Kotak tersimpan memperbarui occupancy dan lintasan kandidat, dashboard, chat dan detail; hasil detector awal tetap tersedia |
| Pembelajaran | Draft/satu sumber tidak melatih; seluruh antrean disahkan dan minimal dua sumber berbeda menghasilkan checkpoint kandidat serta analisis ulang terpisah |
| Ledger v2 | Crossing person/car/bus/truck/motorcycle/bicycle, offset/revisi/sumber, dedupe/retraction dan bukti JPEG dari frame asli |
| Helm | Review frame atau interval dengan asosiasi kepala-orang pada kedua batas; kepala tertutup/helm di tangan tetap unknown |
| Query | Rekaman/revisi, kelas, arah dan rentang `[awal,akhir)`; interval helm memakai overlap, hasil tanpa coverage dibedakan dari nol crossing |
| Novelty | Split sumber asli; bundle simultan, gap/EOS, 11 baseline/model, pemilihan dan ambang dev sebelum test, run immutable |
| Bukti | Dialog membuka frame asli dan seek video pada offset bukti; revised/retracted/corrupt data gagal tertutup |
| Ringkasan | JSON/Markdown deterministik dari filter/revisi sama; tanpa LLM, novelty unavailable dinyatakan, tanpa pengiriman eksternal |
| Presentasi akademik | REPL read-only `/model`, `/topk`, `/score`, `/info`, `/quit`; tokenizer akademik tetap |

Satu kotak tanpa asosiasi track/rentang gerak tidak cukup membuktikan crossing. Menyimpan koreksi bukan memperbarui bobot secara instan. Interval disahkan oleh reviewer sepanjang rentang; algoritme tidak menginterpolasi status helm atau menyimpulkan durasinya dari dua frame. Skor novelty full-session memakai simbol pada awal interval, belum duration-aware.

## Pemeriksaan lokal

| Pemeriksaan | Hasil |
| --- | --- |
| `uv run --locked pytest -q` | **171 passed** |
| Root Ruff check/format dan Ty | Lulus; frozen core tidak diubah |
| Studio Ruff check/format dan Ty, termasuk chat | Lulus dengan pengecualian file pengguna di bawah |
| `npm run typecheck`, `npm run build`, `npm run check` | Lulus; **10 suite UI** dengan perilaku nyata dan regresi lifecycle |
| Ledger v1/v2 dan novelty v1/v2 | Lulus; actual decoded frames → ledger → grouped experiment → HTTP/proof/report |
| Storage/profile/academic/fact/security/deployment | Lulus |
| Self-check/review-counts/tracking/corrections/workflow/video-finetune | Lulus; tracking31, corrections27, workflow29 |
| Training objects/helmets pada RTX4060 | **9/9 + 9/9**; parameter berubah, candidate dipakai dan video hasil dapat didekode |
| Wheel/sdist root dan studio | Dibangun; kesamaan source/aset serta pengecualian data runtime diperiksa |
| Dependency audit | npm **0**; Python lulus dengan satu pengecualian NLTK yang tercatat |
| Preservasi | **875 berkas** core/bobot/hasil/perubahan pengguna byte-identik dengan snapshot sebelum pekerjaan |

Command root:

```powershell
. .\setup_lokal.ps1
uv run --locked pytest -q
uv run --locked ruff check core extensions jalankan_notebook.py
uv run --locked ruff format --check core extensions jalankan_notebook.py
uv run --locked ty check core/src extensions/src extensions/experiments jalankan_notebook.py
uv build --out-dir .tmp/packages
```

Command studio:

```powershell
Set-Location industrial_ai
. .\setup_lokal.ps1
npm run typecheck
npm run build
npm run check
uv run --locked ruff check . --exclude tests/e2e.py
uv run --locked ruff format --check . --exclude tests/e2e.py
uv run --locked ty check access.py storage.py app.py chat.py vision.py review.py operations.py corrections.py detector_training.py video_finetune.py setup_models.py academic.py event_ledger.py fact_query.py
uv run --locked python tests/ledger_v2_check.py
uv run --locked python tests/novelty_v2_check.py
uv run --locked python tests/review_counts_check.py
uv build --out-dir .tmp/packages
uv run --locked python tests/package_check.py .tmp/packages
```

Suite lain ada di [workflow CI](../../.github/workflows/ci.yml). CI mencakup academic/studio serta build container CPU, runtime restricted dan HTTPS/login/CSRF/logout. Docker daemon lokal tidak tersedia; keberhasilan deployment container harus dinilai dari run CI pada commit yang dipublikasikan, bukan tes deployment Python saja.

`industrial_ai/tests/e2e.py` berisi perubahan pengguna sebelum pekerjaan ini. File dipertahankan, tidak diformat/dipublikasikan, dan dikecualikan dari lint lokal. Klaim 71 E2E pada laporan lama adalah hasil historis, bukan pengujian ulang suite tersebut pada perubahan ini. Delapan artefak konsep brand untracked juga tetap lokal. Review subagent dicoba tetapi layanan menolak model (`Unknown model`); audit langsung melengkapi tes otomatis, tanpa mengklaim review independen berhasil.

Browser terisolasi memeriksa query/proof/seek/unduhan, novelty P/NLL/EOS ke bukti, keyboard/Escape, mobile390px, fullscreen anotasi dan refresh tanpa login flash. Fixture crossing/novelty terkontrol dipisahkan dari inference rekaman publik. Pengujian tidak mengganti password/akun pengguna atau memutasi server asli8765.

## GPU dan biaya terukur

Windows, **NVIDIA GeForce RTX4060 Laptop GPU**,8188MB, PyTorch2.14.1+cu130. Auto memilih `cuda:0`; CPU/fallback tetap tersedia.

| Pengujian | Hasil |
| --- | --- |
| Objects: optimizer satu epoch | 235 tensor parameter berubah;9,42 detik training |
| Helmets: optimizer satu epoch | 83 tensor parameter berubah;6,70 detik training |
| Analisis klip publik5 detik,3 pengulangan | p50 **2730ms**, p95 **5223ms** |
| Upload + analisis pada pengulangan yang sama | p50 **3468ms**, p95 **6245ms** |
| Peak RSS server inference | **1663700992 byte** (~1587MiB) |
| Sample peak VRAM seluruh GPU | **283115520 byte** (270MiB); bukan atribusi presisi per proses |
| Qwen3-1.7B + LoRA existing | Jawaban GPU nyata tidak kosong; **8,52 detik**, `cuda:0` |

Pengulangan pertama cold; hanya tiga sampel, bukan jaminan realtime/p95 produksi. Klip menghasilkan dua track dan **nol crossing**. Demo crossing/novelty memakai frame nyata dengan kejadian fixture terkontrol, bukan label kualitas detector. Tidak dilakukan fine-tuning Qwen baru. Peak RAM/VRAM ini milik inference klip, bukan peak training. CPU sebelumnya diuji terpisah; kondisi tidak cukup setara untuk mengklaim faktor percepatan.

Runner novelty juga menyimpan biaya scoring model terpilih per sesi (p50/p95) di artefak run; unit nats/simbol berbeda dari waktu detector/video.

## Batas kualitas dan keamanan

Dataset lokal hanya **dua kelompok sumber asli**, tanpa reference labels tracking/helm/novelty independen. Dua encoding scaffolding adalah satu sumber; original traffic tidak tersedia, hanya derivatif. Ini belum cukup untuk tiga split source-independent. Evaluasi IDF1, precision/recall kamera, false alerts/hour dan onset/delay belum dapat dilaporkan. Jangan menafsirkan metrik training smoke sebagai akurasi pabrik. Rubrik/split harus dibekukan sebelum menambah label evaluasi dan setiap eksperimen memakai run ID baru.

`PYSEC-2026-3740` pada NLTK masih belum ditambal upstream. Pengecualian dibatasi API model-path yang tidak digunakan proyek; boundary regression dijalankan, alasan/upgrade trigger di [SECURITY](../../SECURITY.md#nltk-model-path-advisory-exception). Varian wheel CPU/CUDA diaudit terpisah melalui versi publik torch/torchvision. Dependency audit bukan jaminan bebas kerentanan. Lisensi model pihak ketiga, termasuk Ultralytics, tetap berlaku.

Face attendance/liveness, OCR plat, CCTV live dan deployment multi-tenant produksi tidak ditambahkan. Track bukan identitas; upload timestamp bukan tanggal rekaman; unknown bukan pelanggaran. Source GitHub tidak memuat credential, dataset/footage privat, checkpoint training atau hasil runtime baru. Struktur `core/`, `extensions/`, `industrial_ai/frontend/`, `docs/`, `reports/`, `tasks/` dipertahankan agar path/checkpoint historis tidak rusak.
