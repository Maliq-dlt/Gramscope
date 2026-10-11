# Kontrak CCTV dan N-gram, versi 2

Tanggal protokol: 11 Oktober 2026. Versi 1 tetap dibaca dengan semantik historisnya.

## Kejadian yang disahkan

Request impor menggunakan `schema_version: 2`, `crossing_indices`, `expected_fingerprint` dari preview, dan `recorded_at` opsional (ISO8601 dengan timezone). Preview dan impor harus menunjuk revisi yang sama. Orang, car, bus, truck, motorcycle dan bicycle mengikuti kelas detector existing. Count crossing adalah kejadian lintasan garis, bukan jumlah objek unik. Satu track dapat melintas berkali-kali.

Payload mencatat recording_id, original_source_sha256, source_revision, annotation_revision, correction_revision, model_id, result_source, class_name, direction, seconds, interval_seconds, frame_index, evidence_mode dan evidence_sha256. Satuan offset adalah detik sejak awal video. Boundary filter `[start_seconds, end_seconds)`; crossing instan memakai start <= seconds < end. Interval helm beririsan dengan rentang tersebut. Filter tanpa akhir mencakup akhir rekaman. `occurred_at` null berarti tanggal asli tidak diketahui; kolom internal SQLite memakai `video+<offset>` dan tidak ditafsirkan sebagai kalender.

Bukti versi 2 adalah frame footage asli tepat pada frame terdekat crossing (floor(seconds*fps), dibatasi jumlah frame). Posisi bukti = frame_index/fps, selisih kuantisasi < satu frame. Reviewer mengesahkan crossing dan asosiasi kepala-orang; model tidak mengesahkan pelanggaran. URL bukti memakai event ID, memeriksa workspace, status/revisi dan hash sebelum mengirim. Bukti stale/ditarik gagal 409.

Helm: worn, not_worn atau unknown. Worn/not_worn memerlukan head_bbox normalized dan alasan head_visible, dengan kepala jelas terkait orang pada track. Held_in_hand, occluded, ambiguous atau unreviewed harus unknown. Head_bbox adalah asosiasi reviewer, bukan pengenalan identitas. Event simultan crossing/helm dibundel sebagai satu simbol canonical saat membentuk urutan; sorting tidak menciptakan urutan fisik.

## Pembelajaran dan hasil

Simpan koreksi mengubah hasil review dan revision; tidak mengubah weights. Antrean yang selesai dan >=2 sumber asli berbeda menjalankan optimizer existing, menyimpan kandidat baru lalu reanalysis. Detector belajar pixels; N-gram belajar simbol event yang disahkan. Hasil asli tetap tersedia. Edit membatalkan approval kelompok terkait dan membuat ledger/run/report turunannya stale.

## Evaluasi sebelum test

Unit split = sumber rekaman asli, bukan job/segmen. Source hash dan source_group tetap satu partition. Tracking: per-frame class/box IoU >=0.5 plus ID association review. Helm: worn/not_worn/unknown hanya kepala terlihat; laporkan unknown coverage terpisah. Novelty label diberikan reviewer independen terhadap skor, dengan rubrik pola urutan jarang; bukan label bahaya. Selection minimum dev token-weighted CE; threshold dev quantile95, strict score > threshold. Test receipt immutable, tidak memilih model dari test.

Dataset lokal public CC BY-SA 3.0: dua versi scaffolding merupakan satu sumber; traffic sumber kedua (original lokal belum tersedia, derivatives tersedia). Tidak cukup untuk tiga partition independen berlabel. Tidak ada precision/recall kualitas publik atau false alerts/hour sampai label dan exposure kamera tersedia. Controlled tests membuktikan fungsi, bukan akurasi pabrik. Full-session offline tidak membuktikan latensi deteksi live.
