# Data akademik

| Data | Isi | Jenis bukti |
| --- | --- | --- |
| [academic_pilot_metrics.csv](academic_pilot_metrics.csv) | 72 konfigurasi Brown/Reuters/Wikipedia Indonesia, dev CE, test CE dan PP | Ekspor hasil pilot bahasa yang sudah tersimpan; tidak ada evaluasi ulang |
| [cctv_symbol_order_v1/](cctv_symbol_order_v1/README.md) | 11 pembanding, sesi dan probabilitas simbol CCTV | Eksperimen sintetis terkontrol baru; bukan akurasi kamera |
| [nltk_comparison.json](nltk_comparison.json) | Kesetaraan ordinary KN dengan NLTK pada subset uji | Validasi implementasi; bukan validasi eksternal MKN |

Pilot bahasa berasal persis dari [pilot_metrics.json](../reports/pilot_metrics.json), 10 Oktober 2026. Kolom `source_sha256` mengikat byte sumber lokal; `source_json_fingerprint` mengikat isi JSON secara kanonik agar tidak bergantung pada newline Windows/Linux. Sel kosong berarti metrik tidak tersedia; Stupid Backoff tidak mempunyai CE/PP probabilistik. Orde `n`, metode dan vocabulary mengikuti run asal; jangan menggabungkan PP antarcorpus sebagai ranking kualitas bahasa. [Metode dan batas pilot](../reports/ACADEMIC_LAB.md).

Folder `runs/` menyimpan receipt/model/input lokal dan tidak masuk Git. Hasil lama di folder ini dipertahankan; file historis bukan selalu evaluasi terkini. Untuk data tambahan yang siap dibaca spreadsheet gunakan dua tautan pertama. Makalah disusun pengguna; README ini hanya menjelaskan data.
