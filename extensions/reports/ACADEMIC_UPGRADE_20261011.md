# Pembenahan bukti akademik — 11 Oktober 2026

Data untuk makalah pengguna; bukan makalah atau janji penerimaan jurnal. [CSV/JSON dan reproduksi](../results/academic_upgrade_v2/README.md). Core, hasil historis dan model studio dipertahankan.

## A1 Validasi MKN eksternal

KenLM upstream `4cb443e60b7bf2c0ddf3c745378f76cb59e254e5` dibangun native dengan Boost 1.89 lokal. Patch vendor hanya menghapus link Boost.System yang sudah header-only; tidak menyentuh estimator. Input terkontrol 160 kalimat/825 kata, 39 target probe per orde; probe campuran training/perturbasi known-vocab ini menguji aritmetika, bukan generalisasi/OOV. Bigram 38 token langsung dan trigram 26 token langsung merekonstruksi skor KenLM dengan residual maksimum 5.06e-7/2.27e-6 log10; conditional probability sums mendekati 1.

Skor end-to-end **tidak identik**. KenLM mengalokasikan 0.0617647 massa unigram kepada `<unk>`; implementasi lokal memakai continuation frequency dengan epsilon 1e-8. Pada trigram, 13 jenis repeated-BOS lokal menyebabkan 605 jenis versus 592 di ARPA KenLM, sehingga count-of-counts juga berbeda. Perbandingan menggunakan log10→nat dengan ln10. Ini validasi persamaan diskon/top-order bersyarat; bukan sertifikasi ekuivalensi seluruh estimator. Tidak ada cacat rumus lokal yang dibuktikan, sehingga hasil lama tidak dihitung ulang. [Data token dan panduan build](../results/academic_upgrade_v2/kenlm/BUILD.md).

## A2 Data yang diperluas

Brown 500 dokumen/981.716 token, Reuters 10.788 dokumen/1.327.141 token, Wikipedia Indonesia 2.622 artikel penuh/1.180.980 token. Total 3.489.837 token. Brown/Reuters sudah pernah dipakai proyek ini; perluasan tetap eksploratif. Reuters rerandomisasi kelompok, bukan protokol official train/test Reuters.

Wikipedia menggunakan mirror resmi `wikimedia/wikipedia` config 20231101.id, repository revision `b04c8d1ceb2f5cd4588862100d08de323dccfbaa`. Dari 160 window acak 100 baris pada 665.622 baris, 16.000 kandidat menghasilkan 4.673 eligible; top 3.000 hash-rank menjadi 2.622 setelah 378 group-overlap dikeluarkan. Artikel pilot dan expansion lama dikecualikan lewat ID/hash. Sumber full text, bukan intro atau pilihan judul alfabetis. Sampel tetap **clustered random-window**, bukan simple random sample; eligibility minimal 100 token serta penghapusan kelompok overlap membatasi populasi yang diwakili. Heading/chunk <5 kata diabaikan dan dicatat sebagai preprocessing extension, tanpa perubahan core.

Rows API tidak dapat mem-pin conversion revision. Metadata repository sebelum/sesudah cocok; raw respons dan waktu aktual dihash. Reproduksi offline dari respons tersimpan menghasilkan corpus identik byte. [Sumber/URL artikel dan response hashes](../results/academic_upgrade_v2/source_manifest/idwiki.json). Lisensi CC-BY-SA 3.0/GFDL pada snapshot; atribusi artikel tetap tercatat.

## A3 Seleksi dan hasil aktual

Grid fokus KN 1/2/3 serta MKN 2/3; min_count 2, shared train-only countbank, padding/target identik. Hyperparameter KN dipilih dev. Tiga partisi development 42/43/44 hanya merotasi train+dev, tidak menyentuh primary test. Bootstrap SE dari best-dev dipakai untuk memilih kandidat paling sederhana dalam satu SE: orde lebih kecil, lalu ordinary KN. Minimum-dev memilih MKN 3 pada seluruh 9 kombinasi corpus×seed, tetapi one-SE memilih KN 3 pada seluruhnya. One-SE adalah heuristik regularisasi, bukan jaminan generalisasi. Test primary dinilai sekali setelah protokol/selection dibekukan; model test identik didedup; kontras model identik tetap tercatat nol.

| Corpus | KN 3 PP | MKN 3 PP | ΔCE MKN−KN nat | CI95 kelompok | Grup test |
| --- | --- | --- | --- | --- | --- |
| brown | 401.241 | 395.110 | -0.015398 | [-0.017131; -0.013784] | 31 |
| reuters | 116.461 | 114.015 | -0.021229 | [-0.023403; -0.018276] | 986 |
| idwiki | 513.561 | 504.501 | -0.017799 | [-0.019516; -0.016225] | 263 |

Penurunan PP MKN 1.53%, 2.10%, 1.76% masing-masing Brown/Reuters/Indonesia. CI bersifat conditional pada training/split ini, pointwise tanpa koreksi simultan; tidak ada uji p-value keluarga hipotesis. Jangan membandingkan PP antarcorpus atau menganggap semua metode baru unggul. MKN-versus-KN serta document grouping adalah teknik mapan, bukan otomatis kontribusi baru.

Split berdasarkan kelompok duplikat/sentence/source-explicit/5gram Jaccard ≥0.9. Field `source` saja tidak menyatukan seluruh corpus. Brown train berisi kelompok 185 dokumen yang menyumbang 42.6% token train; Reuters test 986 grup tetapi effective count berbobot token hanya 20.2 karena satu grup 21.8% token. Brown test 31 grup, Indonesia 263 grup dengan effective count 77.1. Jumlah raw dokumen bukan ukuran independensi penuh. Efek training randomness tidak dicakup CI test primary.

## Perbandingan split dan paparan saudara

Perbandingan random-sentence 80/10/10 versus document menggunakan corpus sama, model KN 3 D=.75/MKN 3 tetap, seed 42/43/44 semua dilaporkan. Vocabulary fit **hanya pada irisan occurrence train kedua arm**, bukan corpus/test. Loss per sentence menyimpan parent/group ID. Target/training berbeda sehingga selisih PP bersifat deskriptif, **tanpa CI berpasangan/tafsir kausal**. Pada seed 42 MKN PP document→sentence: Brown 368.18→315.08, Reuters 110.81→82.08, Indonesia 464.15→349.19. PP split kalimat lebih rendah pada ketiga korpus, tetapi selisih ini tidak mengukur besar bias leakage; matched probe di bawah menguji mekanismenya.

Untuk mengisolasi mekanisme lebih baik, satu probe acak per dokumen test yang mempunyai saudara dijaga sama. Seluruh kemunculan exact probe dibuang dari kandidat train. Semua arm berbagi base train dan vocabulary strict-train; fill event budget cocok, residual whole-sentence 0–5 target token (termasuk EOS). Arm exposure memakai saudara test, dua strict arm memakai primary-train lain. MKN ΔCE exposure−strict seed-averaged: Brown −0.44357, Reuters −0.14885, Indonesia −0.44062 nat; seluruh CI pointwise di bawah 0. Strict-resample control dekat 0 dan CI mencakup 0. Ini mendukung efek paparan dokumen saudara pada probe terkontrol, bukan validasi representativitas semua random split. Long/multidocument groups lebih berbobot pada estimand token-weighted; seed bukan sampel independen.

## A4 Reproduksi dan status

CSV mentah, NLL per unit, split/group IDs, seed, discount trials, vocabulary/budget/protocol/source/code fingerprints disimpan. Registry completed tidak boleh ditimpa. Data publik tidak memuat corpus penuh, checkpoint atau video pribadi. Metrik paling baru pada paket ini; angka 185/187 tes dan jumlah hash pada laporan terdahulu tetap snapshot historis, bukan diganti blind dengan angka terbaru.

Verifikasi lokal awal: 198 tes akademik lulus; Ruff lint/format 89 file, Ty dan wheel/sdist lulus. Audit numerik independen pada loss tersimpan cocok untuk seluruh CE/PP/CI/probe/split. Audit dev-only tambahan mereproduksi SE/seleksi dari parameter tersimpan tanpa retune atau rescore test: 20.295 baris loss dev, maksimum selisih 4×10⁻¹⁴; [data turunan](../results/academic_upgrade_v2/dev_reproduction/). Preservasi akhir dicatat pada paket. Tidak mengubah UI/runtime studio pada fase akademik.

## CCTV: batas yang tetap harus dipenuhi

Studi sintetis/MEVA historis serta kegagalan fragmentasi tidak ditulis ulang menjadi hasil positif. Ground-view MOT memberi diagnosis tracking yang lebih sesuai skala, tetapi bukan label helm-dipakai/tidak-dipakai di lokasi target. Recall tanpa helm 15% historis dan ketiadaan person-head association tetap kekurangan nyata. Fine-tuning crop head baru memerlukan review independen worn/not_worn/unknown; head generic SH17 tidak boleh otomatis menjadi tanpa helm. CVAT importer reviewed sudah tersedia. Tidak mengarang precision, false alerts/hour atau delay dari data yang tidak punya incident labels.

## Referensi dan penggunaan alat

- [KenLM estimation](https://kheafield.com/code/kenlm/estimation/) dan [upstream](https://github.com/kpu/kenlm): estimator pembanding, log10 dan kebijakan UNK.
- [Wikipedia snapshot](https://huggingface.co/datasets/wikimedia/wikipedia): sumber/lisensi full text.
- [Chen & Goodman 1996](https://aclanthology.org/P96-1041/): smoothing mapan; bukan klaim novelty proyek.
- Kassis, T., Agarwal, V., He, Y., Patel, D., & Brueckner, A. M. (2026). [Scientific Agent Skills: A Library of Procedural Knowledge for Research Agents](https://doi.org/10.48550/arXiv.2609.00065). Metadata latest v2 diperiksa 11 Oktober 2026; acuan workflow statistical-analysis, bukan sumber data atau validasi hasil.

Codex melakukan implementasi/eksekusi, dengan subagent yang dikonfigurasi GPT-6 Sol untuk review dan akuisisi. Identitas runtime yang dikonfigurasi bukan bukti nama model provider di balik routing. Pengguna perlu mengungkap alat yang benar-benar dipakai pada makalah; dokumen ini tidak mengubah pernyataan penulis makalah.
