# Prioritas data, objek kecil dan tracking — hasil

P1–P3 dijalankan berurutan dengan empat sumber SDD baru dan satu evaluasi test setelah seleksi dev. Hasil **belum mendukung peningkatan akurasi lokasi baru**; konfigurasi studio tetap. [Data CSV/JSON](../results/continuous_tracking_v1/README.md) menyimpan hasil positif maupun negatif.

## P1 Referensi dan kualitas label

Empat scene belum dipakai dalam test historis: bookstore/video0+nexus/video0 untuk dev, little/video0+deathCircle/video0 untuk test. Video+anotasi+reference berjumlah 26 berkas termasuk receipt download/protokol/listing; hash, frame/canvas/FPS dan dekode penuh FFmpeg lulus. Total timeline mentah22,3863menit; **yang dievaluasi40,0400detik/1.200frame**, bukan seluruh video. 300frame pertama setiap klip dipilih sebelum inferensi, tanpa memilih interval dari hasil model. Keempat scene disjoint dari coupa/hyang sebelumnya; source video dan GT hash historis ditolak oleh prepare.

SDD aerial kampus dengan label Pedestrian serta flag generated/occluded; bukan label PPE/lokasi pabrik. Koordinat anotasi dipetakan dari reference canvas ke decoded video menggunakan rasio dimensi. Pemeriksaan visual frame0/150/299 tiap dev dan kemudian tiap test selaras secara wajar; ini pemeriksaan sampel, bukan bukti seluruh anotasi benar. Flag label turunan tetap disimpan. Label pengendara/skater dikecualikan: deteksi person pada mereka terhitung FP sehingga precision adalah **target Pedestrian**, bukan seluruh manusia. Lisensi Stanford CC BY-NC-SA3.0 berlaku, mirror CC0 tidak menggantikannya.

Importer CVAT video baru menerima companion review atas hash video dan XML yang sama, reviewer declaration, canvas/FPS/framecount, interval coverage dan excluded_labels eksplisit. Sparse/interpolated box, label salah ketik, NaN/off-canvas/duplikasi, XML DTD/entity dan overwrite ditolak. Frame di luar coverage unknown; empty covered frame merupakan deklarasi negatif reviewer. Known helmet status harus disertai head_visibility visible. Identitas manusia belum diverifikasi; self-check video5frame hanya uji fungsi, bukan tambahan data human-reviewed. Timestamp CVAT nominal frame/fps belum merupakan PTS VFR.

## P2 Objek kecil

SAHI0.12.8 pinned pada dev dependency. YOLO26n asli dipakai untuk kedua jalur: full-frame640 versus tile640 overlap0.2+full-frame pass, confidence0.1, IoU0.5, merge NMS. Raw predictions dipertahankan terpisah dari hasil tracker. Input dari decoded frame asli, konversi BGR→RGB diperiksa terhadap adapter SAHI. Kotak kecil area<=1.024px² pada canvas asli; metrik ini bukan AP COCO.

| Partisi/mode | TP | FP | FN | Recall | Small TP/GT |
| --- | ---: | ---: | ---: | ---: | ---: |
| Dev standard | 0 | 132 | 6.907 | 0% | 0/4.437 |
| Dev sliced | 215 | 1.291 | 6.692 | 3,11% | 214/4.437 |
| Test standard | 0 | 2 | 8.526 | 0% | 0/6.916 |
| Test sliced | 0 | 237 | 8.526 | 0% | 0/6.916 |

SAHI membuka sebagian deteksi di dev tetapi tidak menggeneralisasi pada dua scene test. Pengamatan offline reviewer: sliced GT-match di bookstore mencapai IoU0,727; deathCircle prediksi sering jauh lebih besar dari GT kecil, little terdapat kandidat raw IoU0,445 tetapi tidak mencapai ambang0,5. Hasil test tidak dipakai untuk tuning/menukar winner.

## P3 Tracking setiap frame

ByteTrack/BoT-SORT memperoleh input detektor identik per mode; tidak skip frame dan reset hanya antarclip. BoT-SORT tanpa Re-ID; tidak mengunduh model appearance. Dev criterion mean native HOTA, lalu IDF1 dan nama kandidat untuk seri, dibekukan sebelum test. HOTA memakai semua threshold native; CLEAR matching0,5 dan Identity memakai threshold0,5. Empty frame tetap dihitung.

| Dev kandidat | Mean HOTA | IDF1 |
| --- | ---: | ---: |
| Standard+ByteTrack | 0,001129 | 0 |
| Standard+BoT-SORT | 0,001129 | 0 |
| Sliced+ByteTrack | 0,043807 | 0,020220 |
| Sliced+BoT-SORT | 0,033674 | 0,008564 |

Sliced+ByteTrack dipilih dari dev. **Test baseline dan kandidat sama-sama HOTA0/IDF1=0**. Kandidat tracking TP0/FP31/FN8.526; baseline TP0/FP0/FN8.526. Zero IDSW di sini berarti tidak ada match yang memadai, bukan identitas stabil. Unit adalah deteksi perframe, bukan8.526 orang unik. Dua sumber test dan40detik total evaluasi tidak mendukung CI populasi/klaim enterprise.

RTX4060 dipakai. P50/P95 detektor test: standard18,38/28,32ms, sliced85,96/120,41ms; biaya slicing sekitar4,68x median. P50/P95 ByteTrack test: standard0,196/0,272ms dan sliced0,094/0,597ms. Nilai tracker cepat pada deteksi nyaris kosong bukan benchmark kerumunan yang berhasil. GPU peak allocated78.508.544byte, tidak termasuk seluruh VRAM reserved/decode/aplikasi. Dev112,51detik, test73,05detik untuk kedua jalur sekaligus. Inference timing mencakup normalisasi/postprocess, mengecualikan decode/konversi warna; bukan latency live.

## P4 Verifikasi dan batas

Offline scorer menghasilkan metrics byte-equivalent secara struktural terhadap hasil tersimpan. Review silang memeriksa source/API native, frame/GT, CSV/JSON, selection, claim dan manifest. Celah CVAT typo serta review/XML binding diperbaiki dan mutation test lulus. Script test satu file per fitur masuk CI; dependency/data tetap terpisah. Hasil lama/core/model dan perubahan pengguna diperiksa melalui audit preservasi.

Perintah run aktual dari root (sudah selesai; **jangan ulang test**):

```powershell
. .\industrial_ai\setup_lokal.ps1
uv sync --project industrial_ai --frozen
& .\industrial_ai\.venv\Scripts\python.exe industrial_ai/continuous_tracking_study.py prepare --dataset industrial_ai/data/public/sdd-continuous-20261011-p1 --output industrial_ai/reports/runtime/priority_tracking_v1/protocol.json --frames 300 --dev-scenes bookstore,nexus --test-scenes little,deathCircle
& .\industrial_ai\.venv\Scripts\python.exe industrial_ai/continuous_tracking_study.py run --protocol industrial_ai/reports/runtime/priority_tracking_v1/protocol.json --phase dev --output industrial_ai/reports/runtime/priority_tracking_v1/dev --device auto
& .\industrial_ai\.venv\Scripts\python.exe industrial_ai/continuous_tracking_study.py select --protocol industrial_ai/reports/runtime/priority_tracking_v1/protocol.json --dev-run industrial_ai/reports/runtime/priority_tracking_v1/dev --output industrial_ai/reports/runtime/priority_tracking_v1/selection.json
& .\industrial_ai\.venv\Scripts\python.exe industrial_ai/continuous_tracking_study.py run --protocol industrial_ai/reports/runtime/priority_tracking_v1/protocol.json --phase test --selection industrial_ai/reports/runtime/priority_tracking_v1/selection.json --output industrial_ai/reports/runtime/priority_tracking_v1/test --device auto
```

CLI dan sumber eksperimen dijalankan dari checkout repository; belum adapter CVAT→evaluator SDD maupun integrasi ke model studio. Data berikutnya yang bernilai adalah review lokasi CCTV sebenarnya, terutama objek jauh/gelap/teroklusi dan status helm dipakai. Mengganti model/TensorRT tidak otomatis menutup kegagalan ini. N-gram tetap untuk urutan simbol terverifikasi; pipeline visual yang salah belum mendukung klaim deteksi insiden.

Verifikasi lokal:187tes akademik,26suite backend plus PPE self-check dan satu extra training smoke CPU,10suiteUI,typecheck/build/audit serta package source equality lulus. Whole-folder formatter menemukan masalah lama pada tests/e2e.py milik pengguna;77file lainnya lulus dan file pengguna tetap identik. Package check awal membaca build lama gagal, lalu rebuild final source equality lulus. Audit akhir2.987berkas: hanya indeks hasil diperbarui sengaja dengan backup yang hash-nya cocok; tidak ada berkas hilang dan15hashcore cocok. Detail command/status berada di verification_local.json. Tidak ada pelatihan kandidat baru untuk deployment. Review akhir menutup prasyarat clone bersih (manifest SDD historis, bobot terverifikasi, gate environment) dan batas agregat kolektor200MBvideo/100MBaux. Snapshot kolektor hasil tetap historis; penguatan kode setelah akuisisi tidak mengubah evaluasi test.
