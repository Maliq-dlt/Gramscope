# N-gram Academic Lab

Implementasi statistik berada di `extensions/`; core dan hasil historis tetap dibekukan. [Verifikasi publik](reports/VERIFICATION.md), [panduan root](../README.md), [blueprint dan status](../tasks/ngram_academic/plan.md), serta [checklist](../tasks/ngram_academic/todo.md) menjelaskan cakupannya.

## Metode dan kontrak

Delapan metode: Laplace, add-k, preset interpolation, Stupid Backoff, ordinary Kneser–Ney, interpolated Witten–Bell, Modified Kneser–Ney dan interpolation EM. Implementasi counts/smoothing sendiri; NLTK ordinary KN dipakai sebagai reference, bukan bukti ekuivalensi MKN.

- Witten–Bell memakai massa hitungan `N/(N+T)` dan lower-order `T/(N+T)`; base unigram diberi epsilon.
- MKN memakai raw counts pada orde tertinggi, continuation effective counts di bawahnya, serta D1/D2/D3+. Bucket estimator yang tidak memadai/invalid memakai fallback 0,75 dan dicatat dalam tuning.
- EM mempelajari bobot global komponen add-0,01 dari frekuensi dev; initialization uniform, cap 200, tolerance 1e-10. Tidak membaca test untuk fitting.
- Stupid Backoff adalah skor tak ternormalisasi: PP tidak tersedia. Diversity/repetisi generasi adalah diagnostik leksikal, bukan penilaian koherensi manusia.

## Pilot terverifikasi, 10 Oktober 2026

Seluruh pilot memakai seed 42, min_count 2, orde 1–3, delapan metode, vocabulary train-only, pemilihan dev, dan 1.000 paired group-bootstrap resamples. Exact document/sentence duplicates, source groups dan 5-gram Jaccard ≥0,9 tetap satu split. Test receipt diklaim sebelum evaluasi; run partial tidak menjadi completed dan run ID tidak dapat dipakai ulang.

| Run ID | Dokumen train/dev/test | Model dev-selected | Test PP | Ordinary KN orde sama | CI95 ΔCE (winner − KN) |
| --- | --- | --- | --- | --- | --- |
| `brown-doc-v1-20261010` | 99/10/11 | trigram MKN | 280,825 | 285,854 | [−0,021057; −0,014210] |
| `reuters-doc-v1-20261010` | 94/13/13 | trigram MKN | 93,561 | 95,272 | [−0,033105; −0,006889] |
| `idwiki-doc-v1-20261010` | 32/4/4 | bigram KN | 84,613 | 84,613 | [0; 0], model identik |

Brown/Reuters memakai 120 file ID pertama setelah diurutkan, bukan sampling populasi yang representatif. Indonesia memakai 40 introduction artikel teknologi/industri Wikipedia, 432 kalimat dan 8.251 token; bukan berita atau corpus bahasa Indonesia representatif. Sumber plaintext API resmi, URL artikel/history, observed revision IDs, hash respons/extract, tanggal dan lisensi **CC BY-SA 4.0** disimpan dalam manifest. Pemisahan kalimat punctuation/newline dapat memecah singkatan. Tidak mengambil chat atau identitas pengguna.

Run bersifat **eksploratif**: parameter direkam sebelum fitting, tetapi prior corpus exposure tidak diketahui. Source test Brown berisi 11 independent groups; Reuters 13 dokumen dalam 12 groups; Indonesia hanya empat groups. CI conditional pada split dan pilot ini, bukan holdout konfirmatori eksternal. PP lintas corpus/UNK space tidak boleh diranking sebagai mutu universal.

Transfer mempertahankan source model/vocabulary: Brown→Reuters ΔCE −0,030994, group CI [−0,035511; −0,026374], 116 target groups; Reuters→Brown −0,009517, CI [−0,010852; −0,008156], 105 groups. Runner lama tidak memberi group tags pada target rows. **Koreksi authoritative** berada di `derived/target_group_bootstrap/correction.json`, dihitung dari losses yang sudah tersimpan tanpa evaluasi ulang; artefak mentah tetap utuh. Runner sekarang memperbaiki group tags untuk run berikutnya.

## Autocomplete dan biaya

Unigram, ordinary KN orde pemenang, dan dev winner memakai 100 targets test pertama menurut sorted document ID, termasuk OOV. `mrr` memakai ranking penuh vocabulary; `mrr_at_50` adalah metrik terpotong yang terpisah. Coverage Brown/Reuters/Indonesia masing-masing 92%/85%/72%. MRR winner 0,194511/0,251425/0,111025. Pada Reuters, MRR MKN hampir sama dengan KN (0,251398), dan top-5 turun dari 0,33 menjadi 0,31. Indonesia memilih KN biasa; metode baru tidak otomatis menang.

Benchmark turunan memakai subprocess baru per model, CPU affinity satu CPU, satu BLAS thread, warmup 1, repeats 3 dan 30 fixed **dev** targets; tidak mengevaluasi test lagi. Seluruh 72 model-workloads selesai. Build mencakup CountBank dan dev-only tuning; score mencakup mapping; top-5 exact vocabulary scan. Peak RSS/working set mencakup seluruh worker/import/cache/warmup, bukan ukuran objek atau incremental model RAM.

| Winner | Top-5 p50/p95 ms | Whole-worker peak MiB |
| --- | --- | --- |
| Brown trigram MKN | 36,65 / 70,69 | 169,50 |
| Reuters trigram MKN | 2,73 / 3,20 | 62,97 |
| Indonesia bigram KN | 1,51 / 1,76 | 58,04 |

Brown ordinary trigram KN lebih murah: top-5 32,01/43,10 ms dan 140,99 MiB. Unwarmed autocomplete latency dan benchmark affinity bukan pengukuran yang dapat dipertukarkan; angka bukan jaminan lintas mesin.

## Jalankan run baru

Dari root PowerShell; ganti ID untuk setiap run. Ini membuat eksperimen baru, bukan membuka ulang receipt lama.

```powershell
. .\setup_lokal.ps1
uv run python -m extensions.experiments.research --corpus brown --target-corpus reuters --limit-documents 120 --run-id brown-baru --orders 1 2 3 --resamples 1000 --download
uv run python -m extensions.experiments.benchmark --run-id brown-baru --warmup 1 --repeats 3 --targets 30
uv run python -m extensions.experiments.prepare_indonesian --output data/indonesian/pilot-baru --limit 40 --download
uv run python -m extensions.experiments.research --input data/indonesian/pilot-baru/documents.jsonl --run-id indonesia-baru --orders 1 2 3 --resamples 1000
```

Download hanya eksplisit; cache/output corpus berada dalam repository. Tambahkan `--public-models` hanya untuk membagikan checkpoint berizin secara read-only ke browser. Default tidak membagikan model. Penulis tidak menimpa corpus directory atau run yang sudah ada.

Checkpoint v2 memiliki schema/algorithm/preprocessing/source/split/vocabulary fingerprints dan sidecar; v1 tetap dibaca ketat. CLI tambahan: `ngram-lm score --model PATH --input UTF8_LINES`, `ngram-lm info --model PATH`, `ngram-lm list --dir DIR`; scoring tidak mengganti test receipts. Source `extensions.src.cli` bisa digunakan tanpa entry point.

Artefak lokal tiap run: `protocol.json`, `splits.json`, `selection.json`, `summary.json`, `tuning/`, `metrics/`, `receipts/`, `autocomplete.json`, `diagnostics.json`, `generated.json`; benchmark di `derived/benchmark/summary.json`. Source delapan berkas pilot lama diarsipkan dan hash-verified dalam `derived/frozen_sources/`; salinan tidak dieksekusi. `read_run` tetap memverifikasi hasil, sedangkan `selected_run` menolak recomputation ketika source live berbeda. Reproduksi lama membutuhkan source frozen dan versi dependency yang tercatat; source sekarang menghasilkan run ID baru.

## Jembatan studio

Lab browser menampilkan probabilitas/top-k/generasi dan completed run metrics melalui API authenticated. Video tetap dianalisis detector/tracker pada piksel. Reviewer mengesahkan observasi ke ledger SQLite; N-gram offline memodelkan **simbol kejadian per track/session**, bukan wajah atau orang unik. Absensi adalah linkage manual admin dengan sumber/verifier/revisi; badge/QR belum didekode.

Novelty runner dan tes replay/grouping tersedia. Tanpa rekaman berlabel independen, onset serta exposure hours, belum ada bukti kualitas nyata, false alerts/hour atau delay. Rare sequence bukan hazard. Face recognition, liveness, CCTV causal live dan jawaban temporal bebas tetap membutuhkan evaluasi/implementasi tersendiri.

Verifikasi akademik: `uv run pytest extensions/tests -q`, Ruff/Ty dan build dari [README root](../README.md). Paket publik mempertahankan source/hasil ringkasan; corpus lokal, bobot, video dan identitas tidak ikut.


## REPL untuk presentasi

```powershell
uv run ngram-lm repl --model PATH_CHECKPOINT.json.gz
```

`/model <path>` mengganti checkpoint, `/topk <context>` memperlihatkan prediksi, `/score <teks>` menghitung skor/perplexity, `/info` membaca metadata dan `/quit` keluar. Path gagal mempertahankan model aktif; tidak melatih atau mengubah checkpoint. REPL memakai tokenizer kata baku. Simbol CCTV memakai runner event tersendiri.

Ledger versi 2 mendukung kendaraan, helm per frame/interval, offset/revisi, bundle simultan, provenance sumber dan EOS. Interval dipertahankan sebagai bukti; scoring belum memodelkan durasi. [Panduan studio](../industrial_ai/README.md#kejadian-cctv-dan-penjelasan-n-gram).
