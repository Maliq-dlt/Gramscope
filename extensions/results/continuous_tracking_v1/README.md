# Referensi deteksi kecil dan tracking kontinu

[Hasil fase dan keterbatasan](../../reports/PRIORITY_TRACKING_20261011.md) · [Panduan CVAT](../../../industrial_ai/docs/TRACKING_ACCURACY.md)

Empat scene SDD baru,1.200frame berurutan/40,04detik: dua dev dan dua test. Model YOLO26n tetap, perbandingan SAHI dan tracker ByteTrack/BoT-SORT. **Test tidak menunjukkan peningkatan: HOTA/IDF1 keduanya0; jangan memasang kandidat sebagai peningkatan tervalidasi.** SDD bukan label status helm atau pabrik.

- `detection_metrics.csv`: TP/FP/FN, recall dan small-area recall sebelum tracker.
- `tracking_metrics.csv`: HOTA/IDF1/CLEAR perclip dan gabungan.
- `dev_metrics.json`, `test_metrics.json`: angka lengkap termasuk threshold HOTA.
- `protocol.json`, `selection.json`: konfigurasi/source snapshot dan pilihan dev.
- `dev_complete.json`, `test_complete.json`: hash predictions lokal, biaya GPU/latency.
- `sources.json`: provenance/download/hash, canvas/koordinat, partisi dan lisensiNC-SA.
- `*.py.txt`: snapshot source; data/weights/prediction individual tetap lokal.

Empty frames disertakan. GT generated/occluded disertakan; pengendara yang dideteksi person dapat FP karena target hanya Pedestrian. Angka orang adalah deteksi perframe, bukan orang unik. Macro pemeriksaan40detik tidak sama dengan seluruh22,39menit download. `manifest.json` mengikat seluruh data yang dipublikasikan. Snapshot kolektor adalah kode saat akuisisi; kolektor saat ini ditambah batas unduhan setelah akuisisi, tanpa mengulang inferensi/test. Prasyarat clone bersih dan gate environment historis dijelaskan dalam panduan CVAT/tracking di atas.
