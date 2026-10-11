# Data akademik

[Siklus kualitas terbaru](../reports/ACCURACY_UPGRADE_20261011.md): [data sumber/detector/PPE](accuracy_data_v1/README.md), [tail sintetik](context_tail_v1/README.md), dan [MEVA sequence](meva_sequence_v1/selection.json). Q1–Q4 terverifikasi; batas data lokasi nyata tetap terbuka.

| Data | Isi | Jenis bukti |
| --- | --- | --- |
| [academic_pilot_metrics.csv](academic_pilot_metrics.csv) | 72 konfigurasi Brown/Reuters/Wikipedia Indonesia, dev CE, test CE dan PP | Ekspor hasil pilot bahasa yang sudah tersimpan; tidak ada evaluasi ulang |
| [cctv_symbol_order_v1/](cctv_symbol_order_v1/README.md) | 11 pembanding, sesi dan probabilitas simbol CCTV | Eksperimen sintetis terkontrol baru; bukan akurasi kamera |
| [event_validation_v1/](event_validation_v1/README.md) | Skenario pair-identik, rules/pair/9LM, tiga seed | A2 konstruksi; temuan negatif hard alert dicatat |
| [event_stress_v1/](event_stress_v1/README.md) | Noise, duration, calibration, review budgets + agregat eksplisit | A3 konstruksi; tidak mengukur derau kamera nyata |
| [idwiki_holdout_v1/](idwiki_holdout_v1/README.md) | 300 artikel baru,24testdokumen22groups,dev-only selection/pairedCI | A4 bounded holdout; CI belum mendukung keunggulan MKN |
| [cctv_detector_v1/](cctv_detector_v1/README.md) | 284 gambar val/test, TP/FP/FN/P/R/AP | C2 benchmark label publik; recall tanpa helm test15% |
| [cctv_tracking_v1/](cctv_tracking_v1/summary.md) | 6 klip, 12.115 sampel frame, Identity/CLEAR | C3 aerial reference; IDF1 nol, bukan validasi pabrik |
| [nltk_comparison.json](nltk_comparison.json) | Kesetaraan ordinary KN dengan NLTK pada subset uji | Validasi implementasi; bukan validasi eksternal MKN |

Pilot bahasa berasal persis dari [pilot_metrics.json](../reports/pilot_metrics.json), 10 Oktober 2026. Kolom `source_sha256` mengikat byte sumber lokal; `source_json_fingerprint` mengikat isi JSON secara kanonik agar tidak bergantung pada newline Windows/Linux. Sel kosong berarti metrik tidak tersedia; Stupid Backoff tidak mempunyai CE/PP probabilistik. Orde `n`, metode dan vocabulary mengikuti run asal; jangan menggabungkan PP antarcorpus sebagai ranking kualitas bahasa. [Metode dan batas pilot](../reports/ACADEMIC_LAB.md).

Folder `runs/` menyimpan receipt/model/input lokal dan tidak masuk Git. Hasil lama di folder ini dipertahankan; file historis bukan selalu evaluasi terkini. Untuk data tambahan yang siap dibaca spreadsheet gunakan tabel paket di atas. Makalah disusun pengguna; README ini hanya menjelaskan data.
