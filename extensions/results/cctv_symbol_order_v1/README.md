# Data eksperimen urutan simbol CCTV

**Jenis data: sintetis terkontrol.** Run `cctv-symbol-order-v1-20261011`, 11 Oktober 2026. Data ini mengukur perilaku model terhadap urutan simbol; tidak mengukur akurasi YOLO, tracking, helm, absensi atau kondisi pabrik. Tidak ada video, wajah atau identitas pribadi di paket ini.

## Berkas

| File | Baris/isi | Penggunaan |
| --- | --- | --- |
| [model_comparison.csv](model_comparison.csv) | 11 pembanding | Perbandingan unigram/bigram/trigram dan baseline frekuensi pasangan |
| [order_contrasts.csv](order_contrasts.csv) | 176 baris, 16 pasangan × 11 pembanding | Selisih CE urutan terbalik minus urutan asli |
| [sessions.csv](sessions.csv) | 176 sesi | Skor model terpilih per sesi, partisi, skenario dan OOV |
| [token_probabilities.csv](token_probabilities.csv) | 638 target, termasuk EOS | P, log P, NLL, konteks dan event ID model terpilih |
| [input_events.json](input_events.json) | 572 event sintetis | Input lengkap dan provenance pembangkitan |
| [protocol.json](protocol.json) | Vocabulary, split, grid, seed, code hashes | Protokol yang dipakai runner |
| [selection.json](selection.json) | Trial dev, parameter dan threshold | Audit pemilihan model, tanpa tuning test |
| [predictions.json](predictions.json), [summary.json](summary.json) | Skor/indikator test | Hasil runner asli; metrik mutu berlabel tidak tersedia |
| [manifest.json](manifest.json) | Status, jumlah baris, hash sumber/output | Integritas paket dan receipt run asal |

## Bagaimana data dibentuk

Generator [controlled_events.py](../../experiments/controlled_events.py) memakai delapan template: orang dengan helm terpakai, tidak terpakai, tidak diketahui, perubahan unknown→worn, worn→unknown, serta mobil/bus/truk masuk–keluar. Observasi simultan menjadi satu token `BUNDLE:`; interval waktu tidak menjadi fitur durasi. Lima template orang memiliki tiga token, tiga template kendaraan memiliki dua token.

Ada **20 grup sintetis**, masing-masing berisi delapan template yang sama. SHA-256 grup adalah ID hasil generator, bukan hash video nyata. Seed 42 membagi grup 16/2/2: train **128 sesi/464 target**, dev **16 sesi/58 target**, test **32 sesi/116 target**. Target mencakup satu EOS per sesi; BOS hanya history. Grup sintetis terpisah secara administratif, tetapi memakai template identik sehingga bukan sampel kamera independen. Tidak ada inference detector atau proses annotation reviewer nyata. Status `verified` adalah fixture uji saja.

Hanya dua grup test diberi salinan urutan terbalik; setiap pasangan memakai multiset simbol identik. Jadi train/dev memuat urutan asli, sedangkan test memuat 16 urutan asli dan 16 terbalik. Template/split/seed dibekukan dalam generator sebelum run; tidak ada pencarian seed atau pemilihan model berdasarkan hasil test. Desain sengaja sederhana untuk mengisolasi sensitivitas urutan, bukan mengukur generalisasi pada pola atau kamera baru.

Runner existing membandingkan add-k unigram, KN/WB/MKN orde 1–3 (10 model probabilistik) serta baseline `pair_frequency_lt2` (11 pembanding total). Vocabulary 15 token berasal hanya dari train, termasuk EOS/UNK. OOV seluruh sesi **0**. Hyperparameter dan model terpilih memakai minimum token-weighted dev CE; threshold linear persentil ke-95 dev session CE; review jika `CE > threshold`. Baseline meminta review bila ada pasangan berurutan dengan count train <2. Baseline tidak mengikutkan BOS/EOS, sehingga unit dukungannya berbeda dari skor LM. Discount/fallback MKN dicatat di kolom `mkn_discount_details`; sparse fallback bukan bukti estimator tiga-discount teridentifikasi dengan baik.

## Arti kolom

- `ce_nats`/`test_ce_nats`: `sum(-ln P)/jumlah target`, natural log, nats per target termasuk EOS. Agregat test berbobot jumlah target, bukan rata-rata CE sesi.
- `perplexity`/`test_perplexity`: `exp(CE)`; bandingkan hanya pada alphabet/tokenizer/target yang sama. PP simbol CCTV tidak sebanding langsung dengan PP kata Brown.
- `delta_ce_nats`: CE terbalik minus CE asli pada pasangan yang sama. Positif berarti urutan terbalik lebih mengejutkan bagi model.
- `probability`, `log_probability`, `nll`: P, ln P dan −ln P untuk `mapped_symbol` pada `context`. `position` dimulai dari 0; EOS mempunyai `seconds` kosong dan event ID kosong.
- `partition`: train/dev/test. Skor train/dev di `sessions.csv` adalah diagnostik, bukan generalisasi.
- `needs_review`, `canonical_alerts`, `reversed_alerts`: indikator berbasis threshold; bukan bahaya, pelanggaran, precision atau recall.
- `parameters`, `mkn_discount_details`: JSON di dalam sel CSV. Nilai kosong berarti tidak tersedia, bukan nol. Baseline frekuensi tidak mempunyai CE/PP probabilistik.
- `scenario`, `variant`, `pair_id`: tag pembangkitan sintetis, bukan label ground truth independen. Track ID fiktif bukan orang unik atau identitas karyawan.

## Hasil aktual dan batas penggunaan

Model terpilih dev adalah **trigram Witten–Bell** (CE dev 0.575531 nats). Pada test, CE urutan asli 0.575531, CE urutan terbalik 6.450959. Model terpilih meminta review untuk **16/16** urutan terbalik dan **0/16** urutan asli. Semua model berkonteks serta baseline frekuensi pasangan juga memisahkan pasangan tersebut; unigram tidak berubah karena multiset token sama. Tidak ada bukti keunggulan atas baseline sederhana pada fixture ini. MKN tidak menjadi winner; hasil negatif ini tetap dicatat.

Jangan menyebut hasil tersebut sebagai akurasi 100%, sensitivity/recall operasional, atau penurunan pelanggaran helm. Template `person_not_worn` ada di train/dev: kejadian helm tidak terpakai bisa biasa secara statistik tetapi tetap perlu pemeriksaan K3. `HELMET_UNKNOWN` bukan pelanggaran. Tidak tersedia label novelty independen, CI populasi, exposure kamera, onset/delay, IDF1 atau precision/recall kamera. Dua sumber video lokal yang ada tidak digunakan sebagai pengganti grup sintetis dan belum cukup untuk split kamera independen train/dev/test.

## Reproduksi dan pemeriksaan

Dari root repository:

```powershell
. .\setup_lokal.ps1
uv run --locked python -m extensions.experiments.controlled_events --output extensions/results/cctv_symbol_order_v1 --check
uv run --locked pytest extensions/tests/test_controlled_events.py -q
# Eksperimen baru selalu memakai ID/path baru; hasil completed tidak ditimpa.
uv run --locked python -m extensions.experiments.controlled_events --run-id cctv-order-replica-01 --output .tmp/cctv-order-replica-01
```

Manifest memverifikasi byte CSV/JSON. README tidak termasuk hash data karena dokumentasinya dapat diperbarui. `.gitattributes` mempertahankan byte data ketika checkout Windows/Linux. Waktu scoring dalam `summary.json` adalah diagnostik run lokal tanpa warmup/affinity/repeats benchmark, bukan SLA. Nilai timing/manifests tidak harus sama antar-replika; angka model/split deterministik dengan input/kode/versi sama.

Verifikasi lokal paket pada 11 Oktober 2026: **172 tes akademik lulus**, Ruff/format/Ty dan wheel/sdist build lulus; parity probabilitas/NLL/EOS, jumlah baris dan manifest diperiksa. Audit 898 berkas lama/terlindungi tetap identik; 87 tautan lokal valid. Cache Ruff lama `.ruff_cache/` (7 file/1,514 byte) dihapus karena konfigurasi aktif memakai `.cache/ruff/`. Makalah dan hasil lama tidak diubah.
