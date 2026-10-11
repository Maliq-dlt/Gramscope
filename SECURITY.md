# Keamanan

## Lingkup dukungan

Perbaikan ditujukan ke versi terbaru `main`. Video Insight memakai autentikasi,
workspace/role dan SQLite lokal, dengan satu worker. Default tetap loopback. CI container/HTTPS lokal telah lulus pada commit terdahulu; domain/deployment publik belum divalidasi.
[Hardening dan batas implementasi](industrial_ai/docs/HARDENING.md) serta [data policy](industrial_ai/docs/DATA_POLICY.md) menjelaskan setup,
backup, audit, serta fitur yang masih direncanakan.

## Melaporkan celah secara privat

Gunakan [Report a vulnerability](https://github.com/Maliq-dlt/N-Gram/security/advisories/new).
Sertakan commit, komponen, reproduksi minimal dan dampak tanpa credential/data pribadi.
Jika kanal tidak tersedia, buka issue yang hanya meminta kanal privat; jangan sertakan
payload eksploitasi atau rekaman sensitif. Tidak ada janji waktu respons enterprise.

## Boundary keamanan

Cookie sesi HttpOnly/SameSite, CSRF pada unsafe API selain login yang dilindungi Origin,
validasi Host/Origin, role/workspace dan rate limit diterapkan backend. Password memakai
scrypt; tidak ada password bawaan. UI tidak menggantikan otorisasi backend. Media/path,
input kotak dan batas upload divalidasi; FFmpeg membatasi protokol dan format. Checkpoint
berasal dari sumber setup tepercaya; API tidak menerima checkpoint arbitrer.

SQLite menyimpan metadata authoritative; media asli tetap berupa berkas. Audit HMAC
mempunyai key/anchor di host yang sama di luar DB, bukan proteksi terhadap administrator
host berprivilege. Backup SQLite/key/anchor dan manifest tidak menyalin semua video/model.

## Data dan batas penggunaan

`industrial_ai/data/`, `models/` dan cache tidak masuk Git. Berkas akses awal
`data/security/first-access.txt`, database, key dan backup adalah data sensitif. Periksa
log/screenshot sebelum berbagi wajah atau plat. Jangan mengunggah credential ke issue.

Deteksi/percakapan dan nama objek manual bukan pengenal wajah atau penentu keselamatan.
Facial enrollment, embeddings, PAD dan evaluasi identitas belum diterapkan. Gunakan review
manusia dan evaluasi independen sebelum pemakaian operasional. Patuhi lisensi Ultralytics
AGPL-3.0/enterprise serta hak masing-masing checkpoint sebelum redistribusi.


## NLTK model-path advisory exception

Pada 10 Oktober 2026, lock memakai NLTK 3.10.3 dan audit CI melaporkan
[PYSEC-2026-3740 / CVE-2026-81726 / GHSA-8mgp-746c-j5xp](https://osv.dev/vulnerability/GHSA-8mgp-746c-j5xp).
Metadata [PyPI NLTK](https://pypi.org/pypi/nltk/json) yang diperiksa menyebut 3.10.3
sebagai rilis terbaru dan advisory belum mempunyai `fixed_in`. NLTK yang dipakai
**belum diperbaiki upstream**; pengecualian ini bukan patch dependency atau klaim
nol kerentanan Python.

Advisory mencakup bypass sandbox `nltk.pathsec` pada path model yang dikendalikan
pemanggil: `TransitionParser.train/parse`, `AveragedPerceptron.save/load`,
`PerceptronTagger.save_to_json`, dan `nltk.classify.maxent.save_maxent_params`.
Source aktif hanya mengimpor corpus Brown/Reuters, tokenizer `wordpunct_tokenize`,
serta `KneserNeyInterpolated`/`Vocabulary` untuk pembanding KN biasa. Corpus dan
resource tokenizer masuk direktori repository. Persistensi model aplikasi memakai
schema JSON/gzip sendiri (`extensions/src/cli.py`), bukan persistence parser/tagger
NLTK. API studio tidak menerima path model NLTK dari pengguna. Library NLTK tetap
terpasang dan import transitifnya tidak dianggap bukti API berbahaya dipanggil.

Satu guard [test_nltk_boundary.py](extensions/tests/test_nltk_boundary.py) memeriksa
allowlist import source aktif (core/extensions/studio), lalu mengintersep keenam
fungsi terdampak agar panggilan apa pun menggagalkan tes. Guard menjalankan reader
corpus NLTK nyata pada tiga dokumen test lokal, tokenizer nyata, perbandingan KN
1–3 yang nyata, dan round-trip checkpoint JSON/gzip aplikasi. Tidak ada download,
training parser/tagger, atau eksploitasi file di luar workspace. Source core dan
artefak eksperimen historis tidak diubah. Jalankan:

```powershell
.venv/Scripts/python.exe -m pytest extensions/tests/test_nltk_boundary.py -q
industrial_ai/.venv/Scripts/python.exe extensions/tests/test_nltk_boundary.py
```

CI menjalankan guard sebelum audit studio, lalu mengabaikan **hanya**
`PYSEC-2026-3740` (alias advisory di atas). Kerentanan lain tetap fatal; audit versi
publik wheel CPU/CUDA Torch/torchvision tidak mempunyai pengecualian ini. Guard
adalah bukti jalur yang diuji saat ini, bukan sandbox runtime baru atau bukti semua
pemakaian NLTK aman.

Hapus pengecualian setelah tersedia rilis resmi yang memperbaiki advisory ini:
upgrade NLTK, perbarui kedua lock tanpa upgrade tak terkait, jalankan guard,
perbandingan KN/tes akademik, dan audit tanpa ignore. Jika import NLTK baru,
parser/tagger/maxent, model-path persistence, atau input path NLTK dari pengguna
akan ditambahkan, tinjau ulang boundary **sebelum** perubahan diterima; jangan
memperluas allowlist/ignore untuk membungkam kegagalan guard. Tidak ada pengecualian
untuk advisory NLTK lain atau artifact/model tak tepercaya.
