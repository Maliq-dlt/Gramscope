# Data pembenahan akademik v2

[Hasil dan batas](../../reports/ACADEMIC_UPGRADE_20261011.md). Data aktual, bukan makalah. Brown 500, Reuters 10.788, Wikipedia Indonesia 2.622 full articles; total 3.489.837 token sebelum EOS.

| Berkas | Isi |
| --- | --- |
| test_models.csv | KN3/MKN3 test utama; CE=ΣNLL/Σtargets, PP=exp(CE) |
| probe_contrasts.csv | Efek paired exposure/control, seed-averaged lalu group bootstrap |
| split_protocols.csv | Split dokumen vs random-sentence, tiga seed; target berbeda, deskriptif |
| brown/, reuters/, idwiki/ | Protokol, seleksi, summary, budget serta loss per unit/seed |
| kenlm/ | Skor token eksternal, ARPA fixture, count/discount/normalisasi dan BUILD.md |
| dev_reproduction/ | Loss dev dan replay independen SE/one-SE, tanpa test rescore |
| source_manifest/ | Source snapshot, URL artikel, lisensi, raw-response hashes; corpus/raw lokal |
| verification_local.json, preservation.json | Angka verifikasi terbaru dan audit perlindungan berkas asli |
| code_provenance.json | Hash kode yang dijalankan dan padanannya pada blob Git |

`test_comparison.csv` model-level, `probe_documents.csv` doc-probe×arm×seed×model, `sentence_split_losses.csv` unit×arm×seed×model. `predicted_tokens` termasuk satu EOS per kalimat, bukan BOS. `nll` dalam nat. Group ID bukan identitas orang. Confidence intervals pointwise conditional pada split/training; seeds bukan grup independen. Partial run tidak diekspor.

## Reproduksi

Dari root PowerShell:

```powershell
. .\setup_lokal.ps1
uv sync --locked
uv run --locked python -m extensions.experiments.prepare_academic_corpora --download --windows 160 --target 3000
uv run --locked python -m extensions.experiments.academic_upgrade --corpus brown --run-id MY-NEW-brown --output extensions/results/MY-NEW-brown
uv run --locked python -m extensions.experiments.academic_upgrade --corpus reuters --run-id MY-NEW-reuters --output extensions/results/MY-NEW-reuters
uv run --locked python -m extensions.experiments.academic_upgrade --corpus idwiki --input data/academic_upgrade_v2/idwiki_20231101_full/documents.jsonl --run-id MY-NEW-idwiki --output extensions/results/MY-NEW-idwiki
```

Hash protokol merekam byte kode Windows CRLF; sebagian blob Git memakai LF. [Pemetaan hash](code_provenance.json) membuktikan isi setara setelah normalisasi akhir baris. Frozen core tidak boleh dinormalisasi tanpa mencocokkan hash manifest aslinya.

Gunakan run ID/output baru. Unduhan ulang API tidak menjamin corpus identik jika conversion berubah; reproduksi numerik menggunakan **raw respons yang hash-nya sama**. Corpus full dan cache lokal `data/academic_upgrade_v2/` tidak diunggah ke Git. Kolektor menolak overwrite dataset selesai. KenLM membutuhkan native C++/Boost, lihat [panduan](kenlm/BUILD.md); estimator core tidak mengimpor KenLM dan CI cepat tidak membangun C++.

## Batas pemakaian

Korpus Inggris pernah terpapar proyek; Indonesia clustered-window dan eligibility-filtered, bukan SRS atau populasi seluruh bahasa. Reuters official partition tidak digunakan. One-SE memilih KN3 di semua seed; MKN3 efek PP kecil 1,5–2,1%. PP berbeda split tidak otomatis efek kausal. KenLM mendukung persamaan, dengan kebijakan BOS/UNK berbeda; tidak ekuivalen seluruh model. Paket ini tidak membuktikan kualitas tracking/helm lokasi pabrik atau kelayakan Q1.
