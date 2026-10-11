# Data, retensi dan pemulihan lokal

Scope saat ini adalah studio unggahan untuk demo/riset. Video, wajah yang terekam, plat, avatar, anotasi, bukti dan ekspor dapat mengandung data pribadi. Track ID bukan identitas orang; enrollment biometrik tidak tersedia. Pengelola harus menentukan tujuan, hak akses, dasar pemrosesan dan jadwal retensi sebelum memakai rekaman pekerja. Dokumen ini bukan pernyataan kepatuhan hukum.

## Akses dan audit

Backend membatasi resource menurut workspace/peran. GET sensitif untuk ringkasan, frame/media, anotasi/koreksi/overlay/antrean review/dataset/suggestions, daftar/detail job dan training termasuk eligibility, serta ledger/fakta/export/proof/preview/novelty dicatat dalam audit HMAC: template route, ID resource tervalidasi, actor/workspace dan status HTTP. Range request dicatat masing-masing. Query, credential, header, body dan isi response tidak dicatat. Revision tercatat hanya bila ada pada nama media immutable; revision data saat GET tidak diperkaya dari database. Polling status ekspor, session dan static tidak dicatat. Detail job tetap dicatat karena responsnya menyertakan ringkasan/anotasi, bukan hanya status.

Audit menyatakan **permintaan dan status**, bukan jaminan seluruh berkas diterima klien. Streaming terputus setelah header, akses langsung lewat filesystem, log proxy dan proses di luar API tidak tercakup. Audit HMAC/key/anchor pada host yang sama mendeteksi perubahan rantai, tetapi tidak melindungi terhadap administrator yang menguasai semuanya. Satu worker tetap berlaku; biaya SQLite audit pada volume permintaan tinggi belum diukur.

## Retensi

Default saat ini: **pertahankan hasil, draft, rekaman dan checkpoint tanpa auto-purge**. Tidak ada jangka retensi operasional tersetel; ini cocok untuk pekerjaan riset saat ini, belum menjadi kebijakan produksi. Pengelola menetapkan masa simpan per kategori sebelum deployment, termasuk asal video, bukti, ekspor, avatar, log audit, dataset turunan dan salinan backup. Retensi harus berlaku pada semua salinan, bukan hanya file asli.

Permintaan penghapusan memerlukan verifikasi pemohon dan inventaris resource/ketergantungan. Hentikan job/worker terkait, identifikasi media, metadata authoritative SQLite, ledger/revisi, dataset/model turunan, ekspor/cache dan backup. Batalkan persetujuan/retract event lewat alur aplikasi bila sesuai, dokumentasikan keputusan dan jadwal hapus backup. Penghapusan aman lintas seluruh kategori **belum tersedia sebagai fitur otomatis**; jangan menghapus berkas satu-satu dari studio aktif atau mengubah tabel/audit langsung. Sampai alur ini diterapkan/diuji, data yang memerlukan jaminan penghapusan tidak boleh dimasukkan untuk deployment operasional.

## Backup

Dari folder industrial_ai, untuk target baru di dalam workspace:

```powershell
. .\setup_lokal.ps1
uv run --locked python access.py verify
uv run --locked python access.py backup .tmp/backup-security-baru
```

CLI menyalin SQLite melalui API backup native dan menyertakan `.key`/`.anchor`; `artifacts.json` adalah daftar hash, bukan salinan media. Untuk bundle lengkap: hentikan layanan/worker, backup DB, lalu salin seluruh media job/training yang tercantum, model/adapter, konfigurasi dan manifest/provenance yang dibutuhkan. Simpan hash untuk model dan file tambahan; manifest CLI tidak mencakup seluruh models/data/public. Batasi akses ke bundle karena DB berisi hash password/sesi/profil dan key memungkinkan pemeriksaan audit.

## Pemulihan

Gunakan salinan baru untuk uji; jangan menimpa studio asli yang masih berjalan. Cocokkan hash seluruh berkas, verifikasi DB/key/anchor sebagai satu bundle, lalu pulihkan ke layout/path asli. Resource dan document SQLite menyimpan absolute path; pemindahan root memerlukan migrasi yang belum tersedia. `access.py verify` hanya memeriksa audit, bukan integritas seluruh media/tabel. Lanjutkan tes login, isolasi workspace, buka/seek media, revisi koreksi, ledger/proof dan checkpoint sebelum membuka layanan.

Regresi lokal memeriksa backup SQLite, key/anchor dan salinan media kecil yang didekode. Pemulihan seluruh studio asli, backup eksternal, enkripsi volume dan penghapusan semua backup belum diuji. Jangan mengganti key/anchor untuk membuat DB rusak tampak valid.

## Data publik dan lisensi

| Sumber | Hak dan batas |
| --- | --- |
| Wikipedia Indonesia | CC BY-SA 4.0; 300 introduction snapshot lokal, provenance/revision/hash. Urutan judul A bukan sampel bahasa umum. |
| Construction-PPE | AGPL-3.0 menurut publisher Ultralytics; label gambar tidak sama dengan ground truth helm dipakai seseorang. |
| Stanford Drone Dataset via Kaggle | CC BY-NC-SA 3.0 dari Stanford; mirror bertanda CC0 tidak mengganti hak sumber asli. Enam klip aerial untuk referensi, bukan rekaman pabrik. |
| TrackEval maintained fork 1.3.0 | MIT, kovalp/TrackEval; evaluator developer, metrik Identity/CLEAR. |
| Ultralytics/YOLO | AGPL-3.0 atau enterprise yang berlaku; MIT source proyek tidak meniadakan kewajiban komponen gabungan. |
| Model helm keremberke | Lisensi bobot eksplisit belum dinyatakan; jangan redistribusikan/anggap izin komersial tersedia. |

Footage, bobot, raw predictions, DB dan credential tetap lokal. Paket `extensions/results/` baru hanya berisi angka/metadata agregat; tinjau hak/provenance sebelum redistribusi. Data test tidak dipakai memilih konfigurasi.
