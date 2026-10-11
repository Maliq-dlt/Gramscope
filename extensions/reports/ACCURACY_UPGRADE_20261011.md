# Kualitas data dan akurasi — hasil per fase

Eksperimen ini mempertahankan seluruh hasil historis dan menyediakan data untuk analisis akademik. Dokumen ini bukan makalah atau bukti validasi di pabrik.

## Q1 — data sumber (lulus)

SH17 resmi versi 1 berukuran 14.096.291.832 byte dan memuat 8.099 foto, 75.994 kotak, serta 922 fotografer. Semua foto berhasil didekode penuh; label YOLO valid dengan toleransi pembulatan 1e-6. Pengelompokan transitif berdasarkan fotografer dan duplikat visual (jarak pHash 6) menghasilkan 6.215 foto train, 707 dev, dan 1.177 test, tanpa fotografer atau piksel identik yang bocor antarpartisi. Ukuran VOC untuk seluruh 8.099 foto cocok dengan berkas aktual; 139 metadata Pexels mencatat ukuran sumber yang lebih besar. Audit VOC→YOLO menemukan dua koordinat VOC di luar kanvas (2/75.994 kotak), yang sudah dipotong dalam label YOLO resmi. Seluruh 112 objek pada kedua foto cocok setelah pemotongan. Kelas helmet 10 dan head 12 berbeda; head **tidak** dijadikan nohelmet. Lisensi CC BY-NC-SA 4.0 dan ketentuan sumber Pexels tidak memberi izin komersial.

MEVA resmi berlisensi CC BY 4.0 memuat 64 triplet/192 YAML, 122 aktivitas, 66.357 observasi kotak, 195 aktor lokal per klip, dan 6 tanggal. Seluruh 195 urutan aktor berupa singleton, sehingga studi per klip memakai state aktivitas. Sebanyak 16 video mentah diunduh (2.053.636.592 byte; 80,06 menit); pemeriksaan hash, frame, waktu, dan dekode penuh FFmpeg lulus. Terdapat 81 pasang klip simultan lintas kamera; partisi menggunakan tanggal. Anotasi bersifat parsial: frame atau objek tanpa label tetap unknown. MEVA tidak menyediakan label insiden maupun onset pabrik.

Sumber: [SH17](https://github.com/ahmadmughees/SH17dataset), [Kaggle penulis](https://www.kaggle.com/datasets/mugheesahmad/sh17-dataset-for-ppe-detection), [MEVA](https://mevadata.org/), [lisensi](https://mevadata.org/resources/MEVA-data-license.txt), [r13 FAQ](https://mevadata.org/transcoding-faq.html). Data dan bobot tetap lokal; hash serta protokol numerik diekspor setelah gerbang akhir.

## Q2 — diagnosis detector/tracker (lulus dengan hasil negatif)

YOLO26n dasar diuji dengan confidence 0.1 dan IoU 0.5 pada semua frame berlabel person yang lolos stride 6 (~5 Hz). Prediksi mentah detektor dan hasil tracker dicatat terpisah. Tracker direset saat sampel terputus; hasilnya bukan tracking video penuh. Koordinat identitas diasumsikan dari FAQ r13 tentang frame yang sama, batas kotak, serta inspeksi visual satu frame awal dan enam frame GT tambahan (tiga dev, tiga test); asumsi ini belum dipastikan dari metadata kanvas anotasi. Kotak pada enam frame tambahan selaras secara visual dengan aktor berlabel. Pemeriksaan sampel ini belum membuktikan keselarasan seluruh 66.357 observasi.

| Partisi/resolusi | GT berlabel | Raw match | Raw recall | Track match | Track recall | Perubahan ID/link cocok berurutan |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Dev 640 | 2517 | 1588 | 0.630910 | 836 | 0.332141 | 6/746 |
| Dev 960 | 2517 | 2176 | 0.864521 | 1902 | 0.755662 | 5/1816 |
| Test 960 | 522 | 271 | 0.519157 | 83 | 0.159004 | 1/66 |

Resolusi 960 dipilih berdasarkan recall detektor mentah pada dev sebelum evaluasi test. Test mencakup empat tanggal lain dan recall menurun; pergeseran domain serta kerapuhan tracker masih nyata. GT parsial tidak mendukung penghitungan precision, FP, atau IDF1 seluruh video; 80 menit video mentah bukan exposure insiden yang telah dievaluasi. Ledger mentah dari run awal tidak menyimpan confidence, sehingga replay asosiasinya tidak identik. Evaluator berikutnya kini menyimpan confidence, kelas, dan dimensi, tetapi test awal tidak dijalankan ulang setelah penambahan metadata itu. Snapshot kode yang dipakai dalam run awal dipertahankan dengan hash yang cocok.

Agregasi tambahan dari ledger tersimpan membagi tinggi GT asli menjadi <32, 32–95, dan >=96 piksel. Bucket <32 tidak memiliki target. Seluruh 68 target dev setinggi 32–95 piksel gagal dicocokkan, baik sebelum maupun sesudah tracker, pada kedua resolusi. Pada test 32–95 piksel, terdapat 57 GT, 12 kecocokan mentah, dan 6 kecocokan tracker; pada test >=96 piksel, terdapat 465 GT, 259 kecocokan mentah, dan 77 kecocokan tracker. Ini diagnosis skala objek, bukan AP COCO atau ukuran setelah letterbox. [CSV ukuran](../results/accuracy_data_v1/meva_size_recall.csv) menyimpan pembilang dan penyebut; [JSON](../results/accuracy_data_v1/meva_size_diagnostics.json) menyimpan hash dan frame kosong. Pada test, prediksi mentah/tracker kosong masing-masing pada 21/73 dari 319 frame berlabel; frame kosong tetap dihitung.

## Q3 — kandidat train/dev dan satu test baru (selesai)

Kandidat YOLO26n dilatih pada 6.215 foto train; 707 foto dev digunakan untuk memilih checkpoint terbaik. Kelasnya person, helmet, dan head. Sebanyak 1.177 foto test ditahan hingga checkpoint dan ambang confidence disegel, lalu dievaluasi sekali. Bobot dasar tidak ditimpa dan kandidat belum dipasang di studio. Label helmet pada foto Pexels tidak membuktikan apakah helm dipakai oleh orang tertentu.

Konfigurasi dibekukan pada 20 epoch, imgsz 640, batch 8, freeze 10, AdamW lr 0.001, seed 20261011, mosaic 0.5, close_mosaic 5, workers 0, dan AMP. Pelatihan menggunakan CUDA RTX 4060; snapshot kode dan argumen aktual disimpan. Sebanyak 16.199 berkas turunan diperiksa melalui SHA-256; cache pelatihan dikecualikan dari inventaris sumber. Perbaikan reproduksi evaluator dibuat sebelum test tanpa mengubah snapshot kode pelatihan.

Evaluasi membandingkan kelas helmet kandidat dengan Hardhat dari baseline yang sudah ada. NO-Hardhat tidak dipetakan paksa menjadi head. Pemetaan nama kelas checkpoint diverifikasi; ambang confidence tiap model dipilih hanya dari F1 helmet pada dev (0.1/0.25/0.5). Klaim eksklusif atas seluruh gambar dan label test mencegah evaluasi ulang melalui salinan direktori. Metrik person dan head untuk baseline tidak dilaporkan sebagai nol karena model itu tidak mendukung kedua kelas tersebut.

### Hasil Q3 yang disegel

Pelatihan 20 epoch selesai (log 3041,6 detik); checkpoint `28be8609427011034833fa61894fe8f84575cee9ff6c6710bdb7cab73021be82` dipilih dari dev. Confidence kandidat 0,25 dan baseline 0,5 dipilih berdasarkan F1 helmet pada dev, kemudian 1.177 foto test dievaluasi sekali. Untuk 131 target helmet yang sama, TP/FP/FN kandidat adalah 61/26/70 dan baseline 62/149/69. Precision kandidat 70,11% versus baseline 29,38%; recall 46,56% versus 47,33%; F1 55,96% versus 36,26%. AP50 helmet 0,50565 versus 0,31212 dan AP50:95 0,31203 versus 0,14889. Recall kandidat untuk person 82,44% dan head 81,65%; baseline tidak mendukung kedua kelas tersebut.

Bootstrap berpasangan dengan 2.000 draw pada 93 grup fotografer dan visual bersifat deskriptif post-hoc. CI 95% untuk selisih kandidat−baseline: precision [0,0484; 0,5311], recall [−0,0953; 0,0556], dan F1 [−0,0025; 0,2780]. Interval F1 mencakup nol, sehingga peningkatan F1 populasi belum terbukti. Kandidat mengurangi kotak false positive helmet (26 versus 149 pada 1.177 foto), tetapi tidak meningkatkan recall helmet dan belum menjadi detektor tanpa helm yang tervalidasi. Evaluasi memakai thumbnail 960 lalu inferensi 640, bukan foto pada resolusi penuh. Status running dalam training_execution adalah receipt historis saat pelatihan dimulai; selection/completed dan 20 baris CSV membuktikan penyelesaiannya.

Pembaca perbandingan offline diperbaiki agar menerima protokol persiapan lama yang sudah disegel tanpa field input_protocol_sha256. Dukungan hanya berlaku untuk hash protokol lama tersebut dan isi audit pengelompokan; protokol, evaluator, serta prediksi test tidak diubah atau dijalankan ulang. Data hasil, snapshot byte aktual, CI per grup, dan manifest tersedia di accuracy_data_v1.

## Q4 — skor urutan, kalibrasi dan data aktivitas nyata (selesai)

Tiga seed (101/202/303) masing-masing memakai 120 grup train, 40 dev, 80 calibration, dan 80 test sintetik baru. Trigram Witten–Bell dengan epsilon 1e-8 dipilih hanya dari dev. Pada 240 grup test, tail memicu 0 alarm normal dan 0 alarm hard; CE memicu 19/19, pair frequency 15/15, dan allowed_pairs 0/0 (normal/hard). Semua alarm hard dari CE dan pair frequency juga terjadi pada grup normal pasangannya: **tidak ada hard-only alarm**. CI berpasangan untuk selisih tingkat alarm tail−CE adalah [−0,10; −0,0125], [−0,20; −0,05], dan [−0,125; −0,0125]. Selisih ini mengukur tingkat alarm, bukan keberhasilan mendeteksi tambahan perubahan. Skor kasus hard lebih tinggi daripada pasangan normal pada 240/240 perbandingan tail maupun CE, tetapi ambang maksimum per sumber tidak memisahkan keduanya. Nilai p minimum untuk hard pada tail adalah 7/81 ≈ 0,0864, di atas alpha 0,05.

Dengan anggaran review 40 sesi per seed, tail menempatkan 54 hard dalam 120 sesi yang ditinjau, sedangkan CE menempatkan 31/120. Pada anggaran 80 sesi per seed, tail menempatkan 138 hard dalam 240 sesi dan CE 83/240; totalnya 240 kasus hard. Manfaat ranking ini hanya berlaku **dalam konstruksi grammar ini**, bukan ukuran ketepatan K3 atau waktu kerja reviewer manusia. Seluruh 240 kasus known-nohelmet masuk jalur aturan terpisah. ID sumber sintetik bukan kamera nyata. Nilai q tail hanya transformasi skor; p conformal yang terpisah memerlukan exchangeability. Jumlah alarm tidak dipaksa tepat 5%.

Fragmentasi dalam uji stres memicu 240/240 alarm normal pada setiap metode. Drop memicu 27/240 alarm normal pada tail; duplicate dan flip memicu 0. Uji derau memakai kalibrasi clean yang dibekukan dan tidak menjamin ketahanan saat distribusi berubah. Skor belum tahan terhadap ID tracking yang terpecah. [clean_summary.csv](../results/context_tail_v1/clean_summary.csv), [review_summary.csv](../results/context_tail_v1/review_summary.csv), dan [stress_summary.csv](../results/context_tail_v1/stress_summary.csv) memudahkan pembacaan data tanpa mengubah run per seed.

Pada MEVA nyata, partisi train memuat 29 klip/83 state, dev 13/21 state, dan test 22/35 state. Seluruh 195 urutan aktor berupa singleton. Setiap state menggambarkan irisan label aktif per klip, bukan rantai kausal atau perilaku satu orang. Bigram KN memperoleh CE dev 5,32572, seri dengan MKN; nama model memutus seri. Pada test 13 Maret, CE untuk 24 target adalah 4,22012; pada 15 Maret, CE untuk 33 target adalah 7,09925. Gabungan 57 target termasuk EOS menghasilkan CE 5,88698/PP 360,32. Unigram WB menghasilkan CE gabungan 5,83189/PP 341,00, lebih rendah secara numerik; test tidak digunakan untuk memilih ulang model. OOV terdapat pada 8/57 target. Loss KN dan MKN identik; interval bootstrap per model dapat berbeda akibat seed resampling, bukan efek metode. Bootstrap klip dari dua tanggal bersifat deskriptif, bukan CI populasi. Tidak tersedia ground truth insiden maupun precision/recall novelty nyata.

Pemeriksaan independen memverifikasi seluruh CSV/JSON, granularitas, partisi, invariansi pasangan, pemilihan pada dev, bootstrap, dan hash; hasilnya tercatat dalam [q4_receipt.json](../results/accuracy_data_v1/q4_receipt.json). Bug yang menggabungkan state sama di dua sisi gap diperbaiki sebelum seleksi dan test, serta memiliki regression test; gap tetap unknown. Hasil historis hard alarm 0/30 tidak disentuh.

Perintah yang dijalankan untuk Q4 (output bawaan kini sudah diterbitkan):

```powershell
uv run python -m extensions.experiments.context_tail_study --seed 101
uv run python -m extensions.experiments.context_tail_study --seed 202
uv run python -m extensions.experiments.context_tail_study --seed 303
uv run python -m extensions.experiments.meva_sequence_study select
uv run python -m extensions.experiments.meva_sequence_study test
```

Runner menolak output, run, atau klaim yang sudah ada; karena output bawaan sudah diterbitkan, perintah di atas tidak dapat langsung dijalankan ulang pada checkout yang memuatnya. Verifikasi hasil menggunakan manifest dan validator offline yang tersimpan. Eksperimen baru memerlukan ID run serta lokasi output baru; jangan menghapus klaim atau memilih konfigurasi berdasarkan hasil test yang sudah dibaca. Prediksi PPE tersimpan dapat dianalisis offline melalui ppe_comparison.py tanpa mengulang inferensi test.

## Reproduksi dan bukti lokal

Jalankan dari root repositori dalam PowerShell. Perintah prepare dan train menggunakan folder baru sehingga hasil sebelumnya tetap tersimpan. Akuisisi sumber sudah selesai; data dan bobot tetap lokal.

```powershell
. .\setup_lokal.ps1
uv sync --frozen
. .\industrial_ai\setup_lokal.ps1
$studioPython = ".\industrial_ai\.venv\Scripts\python.exe"
# Kolektor memerlukan output baru dan akses sumber resmi.
& $studioPython industrial_ai\prepare_sh17.py --output industrial_ai/data/public/sh17-new
& $studioPython industrial_ai\sh17_quality.py industrial_ai/data/public/sh17-new --output-name quality-parallel
& $studioPython industrial_ai\prepare_meva_reference.py --output industrial_ai/data/public/meva-new
& $studioPython industrial_ai\prepare_meva_reference.py --output industrial_ai/data/public/meva-new-video12 --videos 12 --reuse-annotations industrial_ai/data/public/meva-new
& $studioPython industrial_ai\prepare_meva_reference.py --output industrial_ai/data/public/meva-new-extra --video-dates 2018-03-11 2018-03-12 2018-03-13 2018-03-15 --reuse-annotations industrial_ai/data/public/meva-new
& $studioPython industrial_ai\ppe_accuracy_study.py prepare --source industrial_ai/data/public/sh17-new --output industrial_ai/.tmp/accuracy-ppe-new
& $studioPython industrial_ai\ppe_accuracy_study.py train --output industrial_ai/.tmp/accuracy-ppe-new
& $studioPython industrial_ai\ppe_accuracy_study.py evaluate --output industrial_ai/.tmp/accuracy-ppe-new
```

Bukti run tersimpan di `industrial_ai/.tmp/accuracy-ppe-q3-final/`, `industrial_ai/.tmp/accuracy-meva-q2/`, dan `.tmp/accuracy-upgrade/`. JSON/CSV publik tercantum dalam [accuracy_data_v1](../results/accuracy_data_v1/README.md). Folder `quality/` yang terinterupsi dan percobaan prepare awal yang gagal dipertahankan sebagai riwayat; hasil siklus ini menggunakan `quality-parallel/` dan `accuracy-ppe-q3-final/`.

## Verifikasi program

Sebanyak 187 tes akademik lulus, begitu juga Ruff check/format dan Ty. Wheel/sdist akademik serta studio berhasil dibangun. Sebelumnya, 24 suite backend studio dan 10 suite UI lulus; self-check akuisisi/hash dijalankan ulang setelah perbaikan. UI tidak diubah dalam siklus kualitas ini. Pemeriksaan paket dan `git diff --check` lulus. Ini verifikasi program, bukan ukuran akurasi model. Q3 dan Q4 memiliki receipt penyelesaian; Q5 masih menunggu publikasi dan CI pada commit yang tepat.

## Penilaian saran pose, crop dan TensorRT

Asosiasi PPE saat ini mengharuskan pusat kotak berada pada 35% bagian atas kotak tepat satu orang (`industrial_ai/vision.py`). Heuristik ini perlu diuji pada kepala menunduk, orang berimpitan, dan kepala tertutup. Kandidat tanpa helm sudah memerlukan status kontinu selama dua detik; review kepala membedakan worn, not_worn, dan unknown. Geofence poligon serta estimasi jarak berbasis kalibrasi kamera belum tersedia.

Crop yang diarahkan model pose layak dibandingkan secara offline setelah tersedia label kepala CCTV independen. COCO-Pose memiliki 17 keypoint tanpa leher; kepala kecil atau tertutup dapat membuat keypoint tidak terdeteksi. Model pose yang hanya mengenali person juga tidak menggantikan deteksi kendaraan. Crop 128×128 memperbesar gambar, tetapi tidak mengembalikan detail dari sumber 15 piksel. Kelas head SH17 bukan label kepala tanpa helm, sehingga tidak dapat langsung dipakai untuk membuat klasifier biner. Crop yang ambigu atau tidak terlihat harus tetap unknown.

Debounce 70% selama 2–3 detik, cooldown 30 detik, dan ambang 16 piksel masih berupa usulan, bukan standar universal atau hasil pengujian. Batas 30 meter memerlukan kalibrasi kamera. Pilih aturan menggunakan dev dengan label interval, lalu ukur recall kejadian, alarm per jam, delay, dan cakupan unknown pada test independen. Alarm bahaya eksplisit tetap terpisah dari skor novelty N-gram.

TensorRT FP16 dapat mempercepat inferensi, tetapi engine terikat pada GPU dan versi runtime. Klaim 5 ms, 150+ FPS, <1 GB, dan 4–5 kamera belum diukur di laptop ini, termasuk biaya dekode, pose, crop/klasifikasi, tracker, render, dan chat. Angka itu tidak dapat disebut hasil benchmark maupun praktik internal vendor NVIDIA/Intenseye/Protex/AWS tanpa sumber langsung. Siklus ini tidak mengganti detektor studio, melatih klasifier biner, atau memasang engine baru.

Sumber resmi diperiksa: [COCO-Pose](https://docs.ultralytics.com/tasks/pose/), [TensorRT export](https://docs.ultralytics.com/integrations/tensorrt/). Review source dilakukan terpisah oleh GPT-6 Sol; semua inference/training tetap pada runner lokal Codex.

Collector dan runner riset dijalankan dari checkout source. Wheel studio memuat aplikasi yang sudah terdaftar, tetapi tidak memuat seluruh skrip akuisisi dan eksperimen. Reproduksi memerlukan sumber resmi, environment lock, dan ruang penyimpanan dataset. Foto, video, bobot, serta prediksi mentah tidak diterbitkan ke GitHub.
