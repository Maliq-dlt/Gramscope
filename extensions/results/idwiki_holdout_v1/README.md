# Holdout baru Wikipedia Indonesia — A4

300 introduction dari urutan judul mulai **A**, 1.478 kalimat dan 20.236 token; 217 kelompok setelah duplicate grouping. Artikel pilot historis dan kelompok duplikatnya dikecualikan. Snapshot/source/lisensi CC-BY-SA-4.0 diverifikasi sebelum fitting; korpus lokal di `data/indonesian/wiki-expansion-20261011/`.

Primary seed 42: 173/22/22 kelompok train/dev/test (jumlah dokumen mengikuti ukuran kelompok). Seeds 43/44 hanya membagi ulang primary train+dev dengan jumlah kelompok yang sama; primary test tidak dipakai lagi untuk tuning. Delapan kandidat dipilih dari dev; hanya winner dan KN orde yang sama dihitung sekali pada 24 dokumen test, 22 kelompok, 1.388 target termasuk EOS.

| Model | CE nats/target | Perplexity |
| --- | --- | --- |
| MKN trigram, winner dev | 3,864967265 | 47,701710888 |
| KN trigram, baseline | 3,872619075 | 48,068115348 |

Selisih CE MKN − KN **−0,007651810**, paired group-bootstrap CI95% **[−0,020101986; +0,004477205]**, 1.000 resamples. CI mencakup nol: **belum ada bukti keunggulan**. Winner dev seeds42/43/44: MKN/KN/MKN; jangan memilih seed berdasarkan test. `mean_document_oov` adalah rerata OOV per dokumen (28,148%), bukan token-weighted corpus OOV.

| Berkas | Isi |
| --- | --- |
| `development.csv` | 24 baris seed × kandidat; dev CE, ukuran data/vocabulary |
| `test_comparison.csv` | Dua model yang dibekukan, NLL/targets/CE/PP |
| `test_documents.csv` | 48 baris model × dokumen, stored losses untuk resampling tanpa scoring ulang |
| `protocol.json`, `selection.json`, `summary.json` | Split/provenance/code hashes, keputusan sebelum test dan bootstrap |
| `manifest.json` | Hash tiap file dan receipt run lokal |

Sampel introduction berdasarkan urutan judul tidak mewakili bahasa Indonesia umum. Konfirmasi hanya berlaku pada holdout ini; penambahan artikel memperbesar unit uji dari empat kelompok pilot menjadi 22, tetapi jumlah token tetap kecil. Tokenisasi core tetap sama; revision ID Wikipedia teramati bersama extract, tidak revision-pinned. Korpus berlisensi tidak dipush; collector reproducible tersedia, snapshot/hashes lokal dipertahankan. Makalah ditulis pengguna.

```powershell
uv run python -B -m extensions.experiments.wiki_expansion --output data/indonesian/corpus-baru --download
uv run python -B -m extensions.experiments.fresh_holdout --input data/indonesian/corpus-baru/documents.jsonl --run-id holdout-baru --output extensions/results/holdout-baru
```

Source collector harus sesuai manifest; perubahan kode memerlukan snapshot/run baru. Output tidak menimpa hasil yang sudah ada.
