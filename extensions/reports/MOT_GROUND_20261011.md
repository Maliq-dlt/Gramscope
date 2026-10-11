# Diagnosis tracking pada MOT17 — 11 Oktober 2026

Menindaklanjuti kritik domain aerial SDD. Model YOLO26n serta tracker existing dievaluasi pada dua sequence ground-view publik, tanpa training/promosi model. [Data dan batas](../results/mot_ground_v1/README.md).

## Fase C1 Sumber dan protokol

Mirror Hugging Face `Lekim89/MOT17`, revision `f93908467986c77765667925a526ad07be8ad630`;600 JPEG dan 4 GT/seqinfo, 604 files terikat hash remote LFS/Git serta hash lokal. Frame 1–300 berurutan pada sequence 05 dev/09 test (distinct base sequence, bukan detector-variant footage duplicate). Dev 2.556 dan test 2.917 pedestrian GT valid. Native TrackEval `MotChallenge2DBox` membuang matched distractors lalu menilai valid pedestrian; bbox alignment/empty frames tetap tersedia. Dataset card license:other; original rights belum terverifikasi. Gambar dan GT tidak didistribusikan; bukan izin komersial.

Kandidat sebelum inferensi: standard 640/sliced 640 overlap .2+full × ByteTrack/BoT-SORT tanpa Re-ID. Conf .1, IoU .5 dan semua konfigurasi existing tercatat protocol. Objective dev max mean HOTA lalu IDF1 lalu lexical name. RTX 4060 Laptop CUDA 0 digunakan; GT test tidak dipakai memilih kandidat. Baseline+pemenang dinilai sekali pada test setelah selection dibekukan.

## Fase C2 Hasil negatif yang perlu dipertahankan

| Test MOT17-09 | HOTA | IDF1 | MOTA | TP | FP | FN | ID switch |
| --- | --- | --- | --- | --- | --- | --- | --- |
| standard+ByteTrack | 48.10% | 57.84% | 55.61% | 2003 | 357 | 914 | 24 |
| sliced+BoT-SORT (dev-selected) | 29.76% | 35.06% | -24.13% | 2090 | 2682 | 827 | 112 |

Dev standard/sliced memiliki deteksi identik karena 640×480 cocok satu tile 640; max HOTA seri antara standard+BoT dan sliced+BoT. Pilihan sliced+BoT berasal lexical tie, **bukan evidence slicing unggul**. Pada test 1920×1080, raw geometry recall naik 71.51→72.92% tetapi raw FP 1149→4911. Raw detector FP tidak sama dengan native tracking FP karena distractor preprocessing dan tracker filtering berbeda. Ini diagnosis generalisasi gagal, bukan alasan tuning ulang test. Kandidat tidak dipasang ke studio.

Tidak ada box test source area ≤1024 px²: metric small_recall 0 adalah N/A denominator 0, jangan menafsir sebagai bukti objek kecil. Detector standard test p50/p95 17.24/26.66 ms; sliced p95 189.80 ms. Total test 54.67 s/300 frames mencakup dua detector/tracker dan receipt I/O, tidak sama dengan live FPS. Peak Torch CUDA allocated 78.5 MB tidak mencakup seluruh VRAM proses. Dataset training pretrain overlap tidak dapat diaudit penuh.

## Fase C3 Validasi dan sisa kebutuhan

Frozen execution source SHA `68587336b7774d1feee38cd38db4834eeae51b4e8a20e9531f330edd585838ef` disimpan pada runner_frozen.py.txt. Scoring ulang stored predictions dengan source tersebut menghasilkan JSON semantik identik tanpa inference. Sesudah test selesai, collector ditambah batas metadata 2 MiB, JPEG 8 MiB, text 10 MiB, total 200 MiB, pathset 604 persis serta hash/symlink validation. Current source berbeda sengaja dan menolak protocol lama; tidak mengubah hasil/protokol. Ini perbaikan input boundary, bukan retraining/test reselection.

Runnable native distractor+candidate-lock check, collector boundmutation check, Ruff/format/Ty dan paket lulus; CI check disertakan. Reproduksi original:

```powershell
. .\industrial_ai\setup_lokal.ps1
$env:PYTHONPATH = (Join-Path (Get-Location) 'industrial_ai')
& .\industrial_ai\.venv\Scripts\python.exe industrial_ai/reports/runtime/mot-ground-v1/runner_frozen.py score-dev
& .\industrial_ai\.venv\Scripts\python.exe industrial_ai/reports/runtime/mot-ground-v1/runner_frozen.py score-test
```

Kedua command hanya membaca GT/prediksi lokal yang bound hash, bukan inference. Source runtime+data tidak dibundel wheel; gunakan checkout+dataset/model hash sesuai protocol. Source terkini dapat menjalankan studi baru setelah memilih output baru secara terarah; tidak meng-overwrite hasil tersegel.

Label lokasi target **worn/not_worn/unknown plus person-head relation** dan incident onset/exposure masih belum tersedia. Dataset Construction-PPE memberikan400 no_helmet train boxes, tetapi tidak memverifikasi relasi pemakai helm atau kondisi pabrik target; SH17 Head generic bukan negatif. Jangan mengklaim precision, false alerts/hour/delay atau menutup gate operasional dari benchmark MOT. N-gram tetap mengolah simbol yang direview; tracking ID bukan employee ID.
