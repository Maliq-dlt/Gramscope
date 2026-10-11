# Urutan simbol — validasi A2

Data konstruksi sintetis, **bukan akurasi CCTV atau label pakar K3**. Tiap folder seed berisi 180 sesi uji dan 11 pembanding. Tiga seed mengubah ID sumber, waktu dan urutan review; pola/count training dan model sama, sehingga bukan tiga replikasi lokasi atau tata bahasa independen.

| Berkas tiap seed | Grain dan kegunaan |
| --- | --- |
| `A2_models.csv` | 11 pembanding: mean skor setiap skenario, delta hard–normal dan source alerts |
| `A2_sessions.csv` | 1.980 baris: seed × sesi × model; CE dalam nats per target termasuk EOS, baseline berupa jumlah pelanggaran/pasangan langka |
| `A2_sources.csv` | 270 baris: source group × 9 LM; p-value dari 30 kelompok calibration normal yang terpisah |
| `A2_review.csv` | 42 baris: model/strategi × budget **10/20/40 sesi**, precision/recall konstruksi dan rare-valid reviewed |
| `input_cases.json`, `support.json` | Label/rubrik, waktu, split dan bukti kesamaan unigram/pair multisets termasuk BOS/EOS |
| `protocol.json`, `selection.json`, `calibration.json`, `manifest.json` | Parameter dev-only, kalibrasi dan fingerprint hasil/source |

Skenario hard memiliki jumlah simbol dan pasangan identik dengan normal, tetapi trigram berbeda. Aturan transisi, frekuensi pasangan dan unigram/bigram memberi delta nol. Trigram Witten–Bell yang dipilih dev memberi delta CE **0,767264651**, namun **0/30** hard-with-normal sources terkena alarm: contoh rare-valid mendominasi maksimum kalibrasi. Seluruh easy+hard sources terkena alarm karena easy-order; jangan menyebutnya keberhasilan mendeteksi hard. Ranking pada budget 40 juga hanya menangkap 30/60 novelty, semuanya easy-order.

Known-nohelmet adalah tag aturan terpisah, menjadi contoh normal secara statistik. Strategi joint-rule tidak menjamin semua hazard ditinjau pertama. Rare-valid muncul 1/91 training sessions dan 30/180 test sessions; perubahan prevalensi ini disengaja. Nilai precision/recall hanya terhadap rubrik konstruksi, tanpa false-alert/jam atau delay kamera. P-value konservatif memakai `(1 + count(cal_max >= test_max))/(30+1)`; guarantee memerlukan kelompok normal yang exchangeable, tidak menjamin sesi/jam/antar-kamera.

```powershell
uv run python -B -m extensions.experiments.event_study --seed 42 --run-id study-baru-42 --output extensions/results/study-baru/seed42
```

Run/output harus baru. Hasil lama tidak ditimpa; counts/checkpoint privat disimpan di registry lokal. Makalah ditulis pengguna.
