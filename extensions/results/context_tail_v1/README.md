# Conditional-tail N-gram: hasil sintetik

Tiga seed (101/202/303) memakai output dan run ID eksklusif. [generator_protocol.json](generator_protocol.json) dibekukan sebelum run. Grup sintetik bukan kamera independen atau label K3. Setiap seed memisahkan 120 grup train, 40 dev, 80 calibration, dan 80 test. Test memuat 400 sesi, termasuk 80 kasus known-nohelmet yang masuk jalur aturan terpisah.

- [clean_summary.csv](clean_summary.csv): tail memicu 0/240 alarm hard; CE 19/240 dan pair frequency 15/240. Seluruh alarm hard tersebut juga terjadi pada grup normal pasangannya. Tidak ada alarm yang hanya muncul pada kasus hard.
- [review_summary.csv](review_summary.csv): dengan anggaran 40 sesi per seed, tail menemukan 54 hard dalam 120 review versus 31/120 untuk CE. Pada anggaran 80 sesi per seed, tail menemukan 138 hard dalam 240 review versus 83/240 untuk CE. Total kasus hard adalah 240; manfaat ranking ini hanya berlaku pada grammar sintetik tersebut.
- [stress_summary.csv](stress_summary.csv): fragmentasi memicu 240/240 alarm normal pada setiap metode; kalibrasi belum tahan terhadap derau detektor atau pergantian ID.

Nilai q tail adalah transformasi skor, bukan p conformal. Kalibrasi maksimum per grup normal yang terpisah memakai p=(1+#calibration≥score)/81 dan memerlukan exchangeability antargrup. Penggantian hard mempertahankan hitungan unigram/bigram sambil mengubah trigram. Skor sumber hard mencakup latar normal; selisih alarm berpasangan tidak berarti tambahan kasus yang terdeteksi. Jangan menyetel ulang dari hasil test atau menimpa hasil historis hard alarm 0/30.

Setiap seed menyimpan protocol, cases, selection, calibration, scores, sources, review, stress, summary, dan manifest. [Receipt validasi](../accuracy_data_v1/q4_receipt.json) memeriksa hash, granularitas, pemilihan pada dev, invariansi pasangan, serta angka dan bootstrap dari berkas tersimpan. Rincian hasil ada dalam [laporan per fase](../../reports/ACCURACY_UPGRADE_20261011.md).
