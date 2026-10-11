# Deteksi publik orang dan helm — C2

Construction-PPE: 143 gambar validasi dan 141 test, label bawaan publisher. Model dasar YOLO26n dan keremberke helmet dipakai tanpa fine-tuning atau perubahan ambang berdasarkan test. Dua head berjalan terpisah pada RTX 4060, 640 px, FP32; IoU matching 0,5. Ini mengukur kotak kelas pada gambar, belum asosiasi helm dipakai oleh orang.

| Test | TP / FP / FN | Precision | Recall | AP50 |
| --- | --- | --- | --- | --- |
| person | 188 / 67 / 48 | 73,73% | 79,66% | 77,51% |
| Hardhat | 111 / 50 / 81 | 68,94% | 57,81% | 68,27% |
| NO-Hardhat | 6 / 22 / 34 | 21,43% | 15,00% | 9,95% |

mAP50 **0,519108**, mAP50:95 **0,203066**. Recall tanpa helm rendah dan extent label no_helmet bervariasi; hasil tidak membuktikan kemampuan menentukan kepatuhan K3. Overlap pretraining dan duplikat lokasi/visual belum diketahui; exact cross-split SHA duplikat nol. Sepuluh label train tanpa gambar tetap disimpan.

[metrics.csv](metrics.csv) berisi enam baris split × kelas; [summary.json](summary.json) menambahkan mAP/timing, [provenance.json](provenance.json) memuat dataset, lisensi AGPL, model/config/source hashes dan deviasi, [manifest.json](manifest.json) mengikat byte ekspor. Tidak ada gambar, bbox atau bobot dalam paket data publik.

Test awal berhenti pada index29: predictor menghasilkan dua kotak Hardhat dengan tinggi nol. Evaluator diperbaiki agar prediksi finite/ordered berukuran nol tetap unmatched FP (IoU nol); GT tetap wajib positif. Recovery menggunakan **29 cache awal identik + satu diagnostic repeat pada index29 + 111 gambar tersisa**. Raw output disimpan sebelum validasi. Bobot/ambang tidak berubah; cache, failure dan claim awal dipertahankan. Diagnostic command memakai CUDA0, tetapi nama/device tidak tercatat independen dalam metadata diagnostic; batas bukti ini disimpan.

Val p50/p95 per gambar **19,622/36,141 ms**, kedua head dan decode, cold inference termasuk. Test p50/p95 **24,639/64,785 ms** berasal dari sesi cache/diagnostic/recovery. Total4,888detik hanya continuation111gambar; bukan throughput kontinu141gambar dan bukan latensi sistem CCTV.

Untuk verifikasi lokal tanpa inferensi ulang:

```powershell
. .\industrial_ai\setup_lokal.ps1
industrial_ai/.venv/Scripts/python.exe -B industrial_ai/detector_benchmark.py --check --output industrial_ai/.tmp/detector-benchmark-20261011-test-recovered
```

Run baru memerlukan output/claim dan protokol baru. Data makalah disiapkan; penulisan makalah tetap oleh pengguna.
