# Kualitas data dan akurasi

Data ini mendukung analisis akademik N-gram dan diagnosis CCTV. [Laporan per fase](../../reports/ACCURACY_UPGRADE_20261011.md) membedakan hasil pada data nyata, eksperimen sintetik, dan gerbang validasi lokasi yang belum terpenuhi. Q1–Q4 selesai; Q5 menunggu receipt publikasi final. Foto, video, bobot, dan prediksi mentah tetap lokal.

| Berkas | Isi dan batas |
| --- | --- |
| data_quality.json, source_hashes.json | Sumber resmi SH17/MEVA, lisensi, inventaris, dan fingerprint |
| sh17_samples.csv, sh17_split_counts.json | 8.099 foto, fotografer/grup visual, partisi train/dev/test, support, dan hash; head bukan nohelmet |
| voc_yolo_audit.json | Dua koordinat VOC di luar kanvas sudah dipotong dalam label YOLO resmi; dataset tidak diubah |
| meva_metrics.csv, meva_selection.json, meva_protocol.json | Recall target berlabel sebelum dan sesudah ByteTrack; frame/objek tanpa label tetap unknown |
| meva_size_recall.csv, meva_size_diagnostics.json | Ukuran GT asli, frame tanpa prediksi mentah/tracker, dan provenance; bucket <32 piksel tidak memiliki target |
| ppe_test_metrics.csv, ppe_training_results.csv | Pelatihan 20 epoch pada RTX 4060; 1.177 foto test dievaluasi sekali, ambang confidence dipilih dari dev |
| ppe_selection.json, ppe_operating_selection.json, ppe_evaluation_protocol.json | Checkpoint, ambang, skema, versi, dan hash yang dibekukan |
| ppe_uncertainty.json, ppe_per_group_counts.csv | Bootstrap berpasangan 2.000 draw pada 93 grup; deskriptif post-hoc; CI selisih F1 mencakup nol |
| ppe_completed.json, ppe_export_manifest.json | Hash input lokal dan ekspor ringkas; tidak berisi bobot model |
| q1_receipt.json–q4_receipt.json | Bukti gerbang fase, pemeriksaan angka, dan keterbatasan |
| *_snapshot.py.txt | Byte kode eksekusi/validator; snapshot historis tidak diimpor sebagai modul |

Untuk kelas helmet, kandidat menghasilkan TP/FP/FN 61/26/70, precision 70,11%, dan recall 46,56%. Baseline menghasilkan TP/FP/FN 62/149/69, precision 29,38%, dan recall 47,33%. Kelas head anatomis tidak membuktikan ketiadaan helm atau bahwa helm dipakai oleh orang tertentu. Kandidat belum dipasang di studio. `ppe_training_execution.json` adalah receipt historis saat pelatihan dimulai; selection/completed dan CSV berisi 20 epoch membuktikan penyelesaiannya.

MEVA menyediakan diagnostik pada target berlabel dari anotasi parsial. Hasilnya tidak mengukur precision, IDF1 seluruh video, insiden, delay, atau false alert per jam di pabrik. Koordinat identitas didukung batas kotak, FAQ, dan pemeriksaan visual sampel, tetapi belum dibuktikan secara menyeluruh dari metadata anotasi. SH17 terdiri dari foto Pexels berlisensi **CC BY-NC-SA 4.0** beserta ketentuan sumber; MEVA berlisensi **CC BY 4.0** dengan aktor dan skenario terkontrol.

Studi N-gram tersedia di [context_tail_v1](../context_tail_v1/README.md) dan [meva_sequence_v1](../meva_sequence_v1/selection.json). Tail tidak menghasilkan alarm yang hanya muncul pada kasus hard; manfaat ranking hanya ditunjukkan pada grammar sintetik. [Review pose, crop, dan TensorRT](pose_recommendation_review.json) tidak mengubah detektor aktif atau mengklaim performa vendor.

Sumber resmi: [SH17—Mughees et al.](https://github.com/ahmadmughees/SH17dataset), [Kaggle penulis](https://www.kaggle.com/datasets/mugheesahmad/sh17-dataset-for-ppe-detection), [MEVA—Kitware/ActEV](https://mevadata.org/), [lisensi MEVA](https://mevadata.org/resources/MEVA-data-license.txt). Collector dan runner direproduksi dari checkout source; wheel studio tidak memuat seluruh skrip riset.
