# Validasi akademik dan CCTV — 11 Oktober 2026

[Rencana](../../tasks/plan.md) · [Receipt fase](../../extensions/reports/validation_phases.json) · [Data untuk makalah](../../extensions/results/README.md)

Fase akademik A1–A5 diselesaikan sebelum CCTV C1–C5. Implementasi dipublikasikan ke main pada commit `40fa3632a9339f6382cb1ead10809ee48cef2be0`. [CI pada commit tersebut](https://github.com/Maliq-dlt/Gramscope/actions/runs/38140796838) lulus untuk academic, studio dan container, termasuk deployment HTTPS. Data dan dokumentasi teknis disiapkan untuk analisis pengguna. Core dan hasil eksperimen historis dipertahankan.

| Fase | Hasil dan batas |
| --- | --- |
| A1 | Protokol, split, model, budget review dan snapshot 3.681 berkas dibekukan sebelum eksperimen. |
| A2 | Rules, baseline pasangan dan sembilan LM diuji pada skenario bertingkat. Trigram Witten-Bell dipilih pada dev, tetapi alarm sumber hard hanya 0/30. Tiga seed berbagi grammar/counts; bukan tiga kamera independen. |
| A3 | Uji derau 10%, fragmentasi dan durasi dengan batas bin dari train. Kalibrasi bersih tidak menjamin FPR setelah distribusi berubah. Tidak ditemukan sensitivitas durasi yang konsisten. Companion berisi 138 agregat dengan bobot dan denominator eksplisit. |
| A4 | 300 introduction Wikipedia baru, 217 grup; holdout 24 dokumen dari 22 grup. PP MKN 47,70 versus KN 48,07; CI95% selisih CE [−0,020102; +0,004477] mencakup nol. Sampel judul A terbatas. |
| A5 | 185 tes, lint, format, Ty, wheel/sdist dan review independen atas split, hash, perhitungan serta bootstrap tanpa menghitung ulang skor model test. |
| C1 | Pengelompokan sumber transitif berdasarkan SHA, URL dan ancestry. Unggahan lengkap milik workspace menjadi bukti identitas, termasuk penghubung yang tidak dipilih/draft/failed. Label tetap mengikuti seleksi/persetujuan; kebocoran antar-split ditolak sebelum komputasi. |
| C2 | Construction-PPE: 143 gambar val dan 141 test. Precision/recall test: orang 73,73/79,66%; helm 68,94/57,81%; tanpa helm 21,43/15%. mAP50:.95 = 0,203066. Label gambar belum membuktikan hubungan helm dengan pemakainya. |
| C3 | Enam klip SDD, 40,41 menit timeline dan 12.115 frame sampel; 105.743 observasi GT. Hanya dua prediksi setelah ByteTrack, IDF1 = 0. Konfigurasi ini gagal pada objek kecil dari kamera udara; dua scene kampus bukan rekaman pabrik. |
| C4 | Audit akses sensitif, termasuk ringkasan/anotasi dalam detail job dan training. Tes mencakup range, penolakan, error 500 dan privasi. Backup SQLite/key/anchor serta JPEG kecil berhasil dipulihkan; pemulihan seluruh studio dan penghapusan menyeluruh belum tersedia. |
| C5 | Regresi backend/UI, audit dependency, packaging, training GPU terkontrol dan preservasi lulus. CI mencakup academic, studio dan container; status run tetap menjadi bukti publikasi. |

## Koreksi evaluator dan hasil negatif

Run C2 awal berhenti pada index 29 karena native clipping menghasilkan dua kotak Hardhat dengan tinggi nol dan confidence sekitar 0,001. GT tetap wajib memiliki luas positif. Prediksi finite dengan koordinat terurut tetapi luas nol dipertahankan sebagai unmatched FP. Pemulihan memakai 29 cache byte-identik, satu pengulangan diagnostik pada index 29, lalu 111 gambar tersisa. Model, confidence dan protokol tetap; failure/cache/claim awal disimpan. Metadata diagnostik tidak menyimpan nama/device independen; command CUDA 0 dan batas bukti dicatat. Val tidak diinfer ulang. Total waktu test 4,888 detik hanya untuk kelanjutan 111 gambar, bukan throughput kontinu 141 gambar.

Cache dan metrik asli C3 tidak ditimpa. TrackEval CLEAR 1.3.0 mengembalikan CLR_Frames = 0 untuk empat klip tanpa prediksi, sehingga denominator native gabungan hanya 3.990 frame. Companion memakai seluruh 12.115 frame: dua FP dibagi 12.115 frame sampel. Ini bukan false alerts per jam kejadian. Sebanyak 75,26% GT memiliki sisi di bawah 16 px pada skala input 640. Output yang direkam sesudah tracker belum memisahkan kontribusi detector dan tracker; tidak dilakukan inferensi diagnostik atau tuning threshold.

Aturan untuk bahaya yang diketahui dan novelty tetap dua jalur berbeda. Label kejadian K3, onset, exposure monitoring dan beban reviewer lapangan belum tersedia. Metrik tersebut tidak dibuat dari track atau label sintetis. Penelitian lanjutan memerlukan data target dan protokol eksperimen baru.

## Verifikasi lokal

- 185 tes root; Ruff lint/format dan Ty lulus.
- 21 suite backend, termasuk 108 assertion security, 36 pemeriksaan HTTP, tracking 31, corrections 27 dan workflow 29.
- 10 suite UI, typecheck, build dan npm audit lulus.
- Training RTX 4060 terkontrol: objects 9/9 pemeriksaan dengan 235 tensor berubah; helmets 9/9 dengan 83 tensor berubah. Checkpoint dipakai untuk inferensi, bobot dasar tetap identik. Ini bukti fungsi belajar, bukan peningkatan akurasi independen.
- Wheel/sdist diperiksa kesamaan source dan pengecualian data runtime.
- Review C4 menutup akses alternatif lewat overlays, review-queue, detail job, suggestions dan training. Route pertama yang benar menentukan nama audit; isi response/query/credential tidak dicatat.

```powershell
. .\setup_lokal.ps1
uv run --locked pytest -q
uv run --locked ruff check core extensions jalankan_notebook.py
uv run --locked ruff format --check core extensions jalankan_notebook.py
uv run --locked ty check core/src extensions/src extensions/experiments jalankan_notebook.py
uv run --locked python -m extensions.experiments.stress_aggregation --check extensions/results/event_stress_v1/aggregation.csv

# Jalankan pemeriksaan studio dari subproyek:
Set-Location industrial_ai
. .\setup_lokal.ps1
npm run typecheck
npm run check
npm run build
npm audit --audit-level=high
uv run --locked python tests/source_group_check.py
uv run --locked python tests/detector_benchmark_check.py
uv run --locked python tests/tracking_reference_check.py
uv run --locked python tests/tracking_benchmark_check.py
uv run --locked python tests/audit_read_check.py
```

Audit Python menemukan satu exception NLTK PYSEC-2026-3740 yang telah didokumentasikan sebelumnya, tanpa temuan baru. Versi publik Torch/Torchvision diaudit terpisah karena suffix wheel CUDA lokal tidak tersedia di PyPI. Perubahan pengguna pada tests/e2e.py mempunyai format lokal berbeda; berkas ini tidak diubah atau dipublikasikan. Self-check memerlukan working directory industrial_ai; command awal dari root ditolak batas cache lalu diperbaiki tanpa mengubah batas tersebut.

## Data dan preservasi

Paket [A2](../../extensions/results/event_validation_v1/README.md), [A3](../../extensions/results/event_stress_v1/README.md), [A4](../../extensions/results/idwiki_holdout_v1/README.md), [C2](../../extensions/results/cctv_detector_v1/README.md) dan [C3](../../extensions/results/cctv_tracking_v1/summary.md) menyediakan CSV/JSON beserta lineage. Korpus, raw video, prediksi per objek, bobot dan database tetap lokal. Source beku dan byte hasil numerik dijaga melalui .gitattributes.

Pemeriksaan akhir meliputi 3.681 berkas terlindungi: tidak ada yang hilang; satu perubahan sengaja pada extensions/results/README.md untuk indeks paket baru. Versi indeks lama disimpan lokal dengan hash yang cocok. Sembilan manifest, 83 hash hasil, 54 hash source pada checkout dan 15 berkas core cocok. Perubahan pengguna pada e2e.py serta delapan konsep brand dikecualikan dari publikasi.

[Data policy](../docs/DATA_POLICY.md) menjelaskan retensi, backup dan penghapusan; [NOTICE](../../NOTICE.md) menjelaskan lisensi. SDD memakai CC BY-NC-SA 3.0; Ultralytics memakai AGPL atau lisensi enterprise yang berlaku. Lisensi bobot helm belum jelas. Validasi ini belum membuktikan kesiapan produksi, biometrik, CCTV langsung atau keputusan K3 otomatis.
