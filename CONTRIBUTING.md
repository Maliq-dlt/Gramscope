# Berkontribusi

Mulai dari area yang ingin diubah: [studio](industrial_ai/README.md) atau [N-gram](README.md).

## Perubahan yang mudah direview

1. Jelaskan masalah, contoh pemicu, dan perilaku yang diharapkan di issue/PR.
2. Buat branch dengan satu tujuan; ikuti arsitektur yang ada dan batasi diff.
3. Tambahkan tes regresi untuk logika baru/bug yang diperbaiki.
4. Cantumkan command verifikasi, hasil, dan keterbatasannya di PR.
5. Sertakan screenshot untuk UI serta bukti evaluasi untuk klaim akurasi AI.

Jangan memasukkan video pribadi, bobot, dataset, credential, cache, atau virtualenv.
Pertahankan hasil lama. `core/` dikunci oleh `verifikasi/core_manifest.json`;
tuning hanya memakai dev dan test tidak dipakai memilih parameter.

## Verifikasi studio — PowerShell

```powershell
cd industrial_ai
. .\setup_lokal.ps1
$env:npm_config_cache = Join-Path $PWD '.cache/npm'
npm ci
npm run typecheck
npm run check
npm run build
npm audit --audit-level=high
uv run --frozen ruff check .
uv run --frozen ty check access.py storage.py app.py vision.py review.py operations.py corrections.py detector_training.py video_finetune.py
uv run --frozen python tests/storage_check.py
uv run --frozen python tests/security_check.py
uv run --frozen python tests/deployment_check.py
uv run --frozen python tests/self_check.py
uv run --frozen python tests/review_counts_check.py
uv run --frozen python tests/tracking_check.py
uv run --frozen python tests/corrections_check.py
uv run --frozen python tests/workflow_check.py
uv run --frozen python tests/video_finetune_check.py
uv run --frozen python tests/source_group_check.py
uv run --frozen python tests/detector_benchmark_check.py
uv run --frozen python tests/tracking_reference_check.py
uv run --frozen python tests/tracking_benchmark_check.py
uv run --frozen python tests/audit_read_check.py
```

FFmpeg/FFprobe diperlukan untuk tes media. Setelah model diunduh, jalankan
`uv run --frozen python tests/training_check.py auto` (atau `cpu`). Smoke ini membuat
dataset terkontrol/kandidat di `.tmp/`, tidak menyetujui draft publik atau mengubah
bobot dasar. Ini menguji optimizer dan inferensi, bukan peningkatan akurasi.

Periksa UI di browser: antrean, fullscreen/sidebar, klik kanan, tema, playback,
serta simpan → menunggu/training → hasil baru. CI menjalankan regresi playback;
pemeriksaan visual tetap diperlukan.

## Verifikasi N-gram — root repository

```powershell
. .\setup_lokal.ps1
uv sync --locked
uv run pytest -q
uv run ruff check core extensions jalankan_notebook.py
uv run ty check core/src extensions/src extensions/experiments jalankan_notebook.py
```

## Checklist PR

- [ ] Masalah dan perubahan jelas untuk pembaca baru.
- [ ] Tes relevan dijalankan; batasnya disebutkan.
- [ ] Dokumentasi sesuai perilaku final.
- [ ] Core, hasil lama, dan perubahan pengguna di luar scope dipertahankan.
- [ ] Data/secret/weights tidak masuk diff; atribusi pihak ketiga tetap ada.

Celah keamanan: [SECURITY.md](SECURITY.md). Lisensi: [NOTICE.md](NOTICE.md).
