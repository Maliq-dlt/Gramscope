# Derau dan durasi simbol — A3

Empat perubahan observasi konstruksi: penghapusan/duplikasi Bernoulli 10%, perubahan status helm 10% pada simbol helm, dan pembagian track di tengah. Label latent serta ID sumber/sesi tetap; **bukan hasil kesalahan detector nyata**. Model/kalibrasi bersih A2 dipulihkan dari counts/parameter beku. Clean test A2 tidak dihitung ulang.

Per seed: 7.920 baris sesi, 1.080 sumber, 44 pembanding kondisi/model, 168 ranking, 360 duration scores dan 60 duration source scores. Setiap segmen memprediksi EOS; fragment memberi **+1 target/sesi**, bukan mengubah jumlah sesi review. `score_delta_from_clean` bersifat paired.

| Seed | Drop: normal source alerts | Duplicate | Helmet flip | Fragment |
| --- | --- | --- | --- | --- |
| 42 | 18/30 | 12/30 | 17/30 | 30/30 |
| 43 | 16/30 | 14/30 | 15/30 | 30/30 |
| 44 | 17/30 | 18/30 | 12/30 | 30/30 |

Kalibrasi normal bersih tetap; exchangeability tidak dijamin pada noise distribution shift. Nilai ini menunjukkan sensitivitas simbol/segmentasi sintetis, tanpa mengklaim FPR detektor atau false-alert/jam. Tiga seed berbagi grammar/count model A2, tetapi noise/timestamps berbeda.

Duration ablation memakai bin sepertiga/dua pertiga dari gap **training saja**, vocabulary baru, tuning dev dan calibration bersih yang terpisah; slow x2 hanya diterapkan ke test. Normal source alerts base→slow: seed42 **0→0**, seed43 **1→4**, seed44 **0→0** dari 30 sumber. Hasil belum mendukung sensitivitas durasi yang konsisten. Tag `duration_outlier` terpisah dari novelty simbol. Skor model symbol-only tetap sama saat timestamp x2; `timestamp_invariance.json` adalah pemeriksaan mekanisme, bukan bukti sensor kamera.

`A3_duration_summary.csv.mean_ce_nats` adalah **rerata CE per sesi dengan bobot sesi sama**, seperti scenario mean di `A3_models.csv`. Kontrak token-weighted berlaku pada CE tiap sesi/segmen, bukan rerata lintas sesi. [aggregation.csv](aggregation.csv) menambahkan agregat yang eksplisit: `mean_session_score` (untuk baris CE) dan `token_weighted_ce_nats = sum(CE_i × targets_i)/sum(targets_i)`, dihitung dari loss tersimpan tanpa test ulang. Mean delta noise juga rerata per sesi. Kolom `oov_targets/symbol_targets` memisahkan durasi OOV dari EOS.

`A3_sessions.csv`, `A3_sources.csv`, `A3_models.csv`, `A3_review.csv` mencatat noise; `A3_duration*.csv` untuk ablation baru. `protocol/input/selection/calibration/manifest` menyimpan lineage/freeze/hash. [aggregation.json](aggregation.json) mengikat sumber tabel derivasi; counts duration privat tetap di registry.

```powershell
uv run python -B -m extensions.experiments.event_stress --source-run event-validation-42-20261011 --run-id stress-baru --output extensions/results/stress-baru
```

Sumber A2 wajib receipt dan hash kode valid. Tidak ada tuning test, training draft, atau angka akurasi lapangan. Makalah ditulis pengguna.
