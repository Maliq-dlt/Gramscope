# Verifikasi tambahan akademik — 11 Oktober 2026

A1–A5 selesai berurutan. Makalah ditulis pengguna; keluaran berupa data, runner dan receipt. [Checklist/hasil per fase](validation_phases.json) · [CSV/JSON](../results/README.md).

A2 membandingkan hard pair-identik dan rare-valid dengan rules/pair/9LM. A3 memakai checkpoint/kalibrasi A2 yang sama, derau paired dan duration model terpisah. A4 korpus baru300artikel/217groups, test24dokumen22groups; MKN vsKN CI mencakup nol. Seluruh hasil negatif dipertahankan. Tiga seed simbol berbagi grammar/count model; bukan replikasi kamera. Dataset publik/image dan data lokasi di fase CCTV tidak membuktikan label expert/false-alert-hour.

185 tes root lulus; Ruff lint/format70Pythonfiles, Ty dan wheel/sdist lulus. Semua3.681berkas snapshot core/hasil/bobot/data/perubahan pengguna SHA256 identik, tidak ada yang hilang. Review independen memeriksa hashes/lineage, split, NLL/CE/PP, p-value/CI dari loss tersimpan tanpa model-scoring ulang. Tabel derivasi138agregat direproduksi dari CSV publik saja. `core/` tidak diubah dan hasil test historis tidak dihitung ulang.

```powershell
. .\setup_lokal.ps1
uv run --locked pytest -q
uv run --locked ruff check core extensions jalankan_notebook.py
uv run --locked ruff format --check core extensions jalankan_notebook.py
uv run --locked ty check core/src extensions/src extensions/experiments jalankan_notebook.py
uv build --out-dir .tmp/academic-validation/packages
uv run --locked python -m extensions.experiments.stress_aggregation --check extensions/results/event_stress_v1/aggregation.csv
git diff --check
```

Artifact lokal `.tmp/academic-validation/` dan registry private; hasil publishable berada di direktori A2/A3/A4 terpisah. Berkas `mean_ce_nats` duration lama adalah rerata sesi; companion menamai bobot/denominator eksplisit. Protokol awal tidak ditimpa; kontrak run merinci pilihan hard path, anggaran jumlah sesi, prevalence dan batas conformal. Dokumentasi historis tetap dibaca sesuai tanggal.

Publikasi akhir: implementasi `40fa363` pada main; [CI academic/studio/container lulus](https://github.com/Maliq-dlt/Gramscope/actions/runs/38140796838). Audit pasca-CCTV tetap tidak menemukan berkas hilang; satu perubahan sengaja pada indeks `extensions/results/README.md` mempunyai backup versi awal dengan hash yang cocok. Data eksperimen dan core tetap identik.
