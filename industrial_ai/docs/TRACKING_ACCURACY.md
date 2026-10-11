# Referensi berlabel dan akurasi tracking

Studio tetap memakai detector/tracker yang sudah tersedia. Perbandingan offline ini menguji objek kecil dan asosiasi antarframe sebelum mengubah model produksi. [Data hasil](../../extensions/results/continuous_tracking_v1/README.md) dan [checklist](../../tasks/todo.md) membedakan implementasi dari validasi lokasi target.

## Review anotasi video

Gunakan CVAT Community atau editor studio untuk meninjau objek; kotak hasil AI tetap draft hingga reviewer memeriksa posisi, kelas, ID dan intervalnya. Importer CLI menerima **CVAT for video XML**, bukan ZIP yang diekstrak otomatis. Foto/frame berkotak AI tidak menjadi input gambar training: gunakan frame asli dan label terpisah.

Buat tugas dengan `person`, `head`, `helmet`. Pada person, atribut mutable `helmet_status` berisi `worn`, `not_worn`, `unknown`; atribut `head_visibility` berisi `visible`, `occluded`, `unknown`. Status known memerlukan `visible`. Kepala dan helm mempunyai track tersendiri; belum ada pemetaan otomatis kepala→orang. Helm yang dipegang bukan bukti helm dipakai.

Selesaikan review di seluruh interval yang akan digunakan. Versi importer ini menerima kotak **eksplisit per frame, keyframe=1**, dan marker `outside` untuk objek yang keluar. Kotak interpolasi/keyframe=0 ditolak; jangan sekadar mengganti flag hasil auto-label menjadi keyframe tanpa meninjau. Eksport yang hanya punya keyframe renggang perlu dilengkapi/direview terlebih dahulu. Ini batas sengaja untuk mencegah frame tanpa label berubah menjadi negatif.

Companion JSON berisi deklarasi review atas XML dan video tertentu:

```json
{
  "reviewer": "nama-reviewer",
  "video_sha256": "SHA256_VIDEO_64_HEX",
  "cvat_xml_sha256": "SHA256_XML_64_HEX",
  "excluded_labels": [],
  "canvas": [1920, 1080],
  "fps": "30",
  "frame_count": 900,
  "coverage": [[0, 900]],
  "frame_policy": "dense_explicit"
}
```

Nilai contoh harus diganti dengan metadata aktual. `coverage` memakai interval frame **[awal, akhir)**; frame terakhir tidak termasuk. Frame kosong di dalam coverage dinyatakan negatif oleh reviewer; di luar coverage tetap unknown. `excluded_labels` harus menyebut setiap kelas yang sengaja tidak dinilai, misalnya `car`; label tidak dikenal ditolak. Hindari mengecualikan alias person karena akan membuat orang menjadi negatif. Identitas reviewer adalah deklarasi lokal, bukan tanda tangan atau verifikasi identitas independen.

Dari root repository, setelah setup lokal:

```powershell
. .\industrial_ai\setup_lokal.ps1
Get-FileHash -Algorithm SHA256 -LiteralPath industrial_ai/data/public/video.mp4
Get-FileHash -Algorithm SHA256 -LiteralPath industrial_ai/.tmp/review/annotations.xml
& .\industrial_ai\.venv\Scripts\python.exe industrial_ai/cvat_reference.py `
  --xml industrial_ai/.tmp/review/annotations.xml `
  --review industrial_ai/.tmp/review/review.json `
  --video industrial_ai/data/public/video.mp4 `
  --output industrial_ai/.tmp/reviewed-reference-new
```

Importer memeriksa hash XML/video, canvas, frame count decode, FPS, koordinat dan coverage. Timestamp `frame/fps` bersifat nominal; sumber VFR memerlukan pemetaan PTS sebelum analisis waktu nyata. Output terpisah berisi `annotations.jsonl` dan `manifest.json`; tidak melatih model atau menulis ke ledger studio. Evaluator SDD pada siklus ini belum membaca output CVAT: evaluasi lokasi target membutuhkan adapter/protokol terpisah setelah referensi review nyata tersedia.

## Detektor dan tracker offline

Dependency `sahi==0.12.8` berada di kelompok dev terkunci. TrackEval dan SciPy sudah tersedia. Gunakan environment studio:

```powershell
. .\industrial_ai\setup_lokal.ps1
uv sync --project industrial_ai --frozen
& .\industrial_ai\.venv\Scripts\python.exe industrial_ai/tests/cvat_reference_check.py
& .\industrial_ai\.venv\Scripts\python.exe industrial_ai/tests/continuous_tracking_check.py
```

Dari clone bersih, `data/public/` dan bobot model tidak ikut Git. Sebelum membuat protokol baru, siapkan `models/yolo26n.pt` yang diverifikasi checksum, manifest SDD historis **tepat di** `industrial_ai/data/public/sdd-reference-20261011/manifest.json`, lalu koleksi empat scene baru. Kolektor hanya menerima direktori output yang belum ada; lewati akuisisi historis jika data lokal tersebut sudah tersedia dan terverifikasi.

```powershell
& .\industrial_ai\.venv\Scripts\python.exe industrial_ai/setup_models.py --vision-only
& .\industrial_ai\.venv\Scripts\python.exe industrial_ai/prepare_tracking_reference.py `
  --output industrial_ai/data/public/sdd-reference-20261011
& .\industrial_ai\.venv\Scripts\python.exe industrial_ai/prepare_continuous_reference.py `
  --output industrial_ai/data/public/sdd-continuous-new
```

Kolektor continuous saat ini menolak listing melebihi **200 MB video atau 100 MB anotasi/foto sebelum mengunduh**. Penguatan ini dibuat setelah akuisisi yang dilaporkan; snapshot kode kolektor dalam paket hasil tetap bukti historis dan tidak ditimpa. Akuisisi ulang manifest lama dari mirror hanya memenuhi prasyarat path untuk pemeriksaan hash sumber lama; itu **bukan** bukti bahwa manifest baru byte-identik dengan akuisisi historis.

`continuous_tracking_study.py prepare` juga mensyaratkan hash bobot serta versi dan hash source native dalam `native_receipt` sama dengan protokol historis (`industrial_ai/reports/tracking_protocol_20261011.json`), termasuk versi Windows/CUDA yang terkunci (Torch `2.14.1+cu130`). Cek fungsional di CI/CPU tidak membuktikan replay protokol itu. Bila gate tersebut tidak cocok, hentikan reproduksi alih-alih melonggarkan protokol; jangan menjalankan ulang test yang sudah disegel.

Empat scene baru SDD digunakan: bookstore+nexus sebagai dev; little+deathCircle sebagai test. Masing-masing 300 frame pertama berturut-turut dipilih sebelum inferensi. Model YOLO26n yang sama dipakai oleh deteksi biasa640 dan SAHI tile640, overlap0.2, full-image pass. NMS penggabungan IoU0.5; confidence0.1. ByteTrack/BoT-SORT memperoleh prediksi raw yang sama, BoT-SORT tanpa Re-ID. Tracker menerima setiap frame, termasuk deteksi kosong; reset hanya pada pergantian klip.

Prepare/freeze, run dev, select, dan satu test berjalan melalui `continuous_tracking_study.py`. Gunakan **output baru** dan sumber yang belum dievaluasi; hasil/test sebelumnya tidak dihapus untuk mengulang tuning. Source, model, dataset dan dependency dicatat dalam protokol; run menyimpan prediksi raw dan hasil tracking terpisah. Perintah run yang sudah selesai merupakan riwayat, bukan instruksi mengulang test.

Ukuran deteksi: TP/FP/FN dengan assignment IoU>=0.5 dan recall kotak kecil area<=1024 piksel pada canvas asli. Ini bukan AP COCO. Label target hanya SDD Pedestrian; person pada pengendara/skater tetap FP karena kelas tersebut dikecualikan dari GT. Tracking: native IDF1/CLEAR/HOTA serta rincian threshold HOTA. Angka latency detektor mencakup inferensi+postprocess/normalisasi dengan sinkronisasi CUDA, mengecualikan decode/konversi warna; waktu total run juga tersedia.

SDD aerial kampus, bukan footage pabrik atau data helm dipakai. Lisensi sumber Stanford **CC BY-NC-SA3.0** berlaku walaupun mirror menyebut CC0. Model Ultralytics juga mempunyai ketentuan lisensi tersendiri. Kandidat offline tidak otomatis dipasang ke studio.

## N-gram tetap fondasinya

Deteksi/tracking menghasilkan observasi simbol. Setelah review, N-gram mempelajari urutan dan memprioritaskan sesi tidak biasa. Memperbaiki objek kecil/fragmentasi mengurangi derau input; tidak membuktikan skor N-gram mampu mendeteksi insiden. Alarm bahaya yang sudah diketahui tetap jalur aturan tersendiri. Durasi, IDF1 lokasi target, precision/recall status helm, false alerts per jam dan beban reviewer memerlukan referensi independen tersendiri.

Referensi: [SAHI](https://arxiv.org/abs/2202.06934), [ByteTrack](https://arxiv.org/abs/2110.06864), [BoT-SORT](https://arxiv.org/abs/2206.14651), [HOTA](https://arxiv.org/abs/2009.07736), [CVAT video XML](https://docs.cvat.ai/docs/dataset_management/formats/format-cvat/), [SDD Stanford](https://cvgl.stanford.edu/projects/uav_data/).
