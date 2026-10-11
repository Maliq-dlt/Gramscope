# Panduan dokumentasi Video Insight

[Mulai dan instalasi](../README.md) · [Riwayat perubahan](../CHANGELOG.md)

| Tujuan | Dokumen |
| --- | --- |
| Memahami pengguna, batas produk dan desain | [PRODUCT](PRODUCT.md), [DESIGN](DESIGN.md) |
| Akses, penyimpanan, deployment dan keamanan | [HARDENING](HARDENING.md), [data/retensi](DATA_POLICY.md), [verifikasi keamanan](VERIFICATION_SECURITY.md) |
| Melihat bukti UI terkini dan keterbatasannya | [Verifikasi UI](VERIFICATION_UI.md) |
| Logo dan atribusi | [Panduan logo](brand/guidelines.md), [lisensi komponen](../assets/THIRD_PARTY_LICENSES.txt) |
| Bukti publikasi, referensi dan workflow belajar | [Laporan publikasi](../reports/VERIFIKASI_PUBLIK.md), [referensi](../reports/REFERENSI_GITHUB.md), [workflow](../reports/WORKFLOW_REVIEW_BELAJAR.md) |
| Kontrak event, filter, interval dan penjelasan N-gram | [Kontrak CCTV/N-gram](EVENT_CONTRACT.md), [verifikasi integrasi/GPU](../reports/VERIFIKASI_CCTV_NGRAM.md) |
| Pengukuran akademik/detector/tracking terbaru | [Validasi 11 Oktober](../reports/VALIDATION_20261011.md), [paket CSV/JSON](../../extensions/results/README.md) |
| Review label CVAT dan eksperimen objek kecil/tracking | [Panduan akurasi](TRACKING_ACCURACY.md) |
| Roadmap dan status implementasi | [Checklist](../../tasks/todo.md), [roadmap rinci](../../tasks/roadmap_checklist.md) |

## Yang tersedia sekarang

Studio lokal menyediakan login/peran/workspace, profil privat, unggah video,
perbandingan asli/tracking AI, counting, bukti objek, koreksi/anotasi/tracking,
ekspor video, antrean review dan persetujuan dataset, fine-tuning/reanalisis,
serta chat lokal yang merujuk hasil rekaman. UI React/TypeScript mendukung
keyboard, tema, mobile, reduced motion dan fullscreen. Lihat verifikasi untuk
batas bukti; fitur tersedia tidak berarti akurasi CCTV atau produksi tervalidasi.

Absensi tersedia sebagai catatan yang diverifikasi administrator secara manual.
Input foto untuk analisis, CCTV/webcam live, OCR plat, scanner QR/pengenalan wajah dan
pencarian SOP masih roadmap. Unggah avatar bukan analisis foto umum.

## Hubungan dengan N-gram dan susunan source

[N-gram di repository induk](../../README.md) adalah proyek akademik terpisah:
notebook/CLI probabilitas bahasa, smoothing dan perplexity. Studio kini menjalankan
Lab N-gram lewat API terautentikasi, serta menyimpan ledger kejadian terverifikasi.
Runner offline dapat menilai urutan simbol kejadian; chat fakta memakai query
deterministik dari ledger. Qwen tetap menangani bahasa pada alur video yang sesuai.
N-gram tidak mendeteksi piksel atau mengenali wajah.

[Laporan akademik](../../extensions/reports/ACADEMIC_LAB.md) ·
[Verifikasi implementasi](../../extensions/reports/VERIFICATION.md)

`frontend/` menyatukan komponen React, controller auth/studio/motion TypeScript
serta konfigurasi kompilasinya. Bundle `app.js`, `auth.js`, `dashboard.js` dan
`motion.js` tetap di root subproyek karena digunakan server/distribusi.
Backend Python mempertahankan modul yang ada; hasil, model dan bukti verifikasi
berada pada lokasi semula. Dokumentasi menjadi pintu masuk tanpa perlu landing
page tambahan untuk pemakaian studio lokal.
