# MOT17 ground-view diagnostic

600 contiguous frames, two original sequence IDs: dev MOT17-05-FRCNN1–300 (640×480,14fps), test MOT17-09-FRCNN1–300 (1920×1080,30fps). Public train benchmark labels are used for this local experiment; this is **not** an official hidden-test result or factory/PPE accuracy test. [Report](../../reports/MOT_GROUND_20261011.md).

`metrics.csv`: native TrackEval MOTChallenge2DBox distractor preprocessing, HOTA/IDF1/CLEAR per candidate. `*_metrics.json`: native arrays plus raw detector geometry (different distractor policy). `source_manifest.json`: image/GT/source revision hashes; source media/GT stay local. `protocol.json` and `selection.json` freeze source/config/winner. `runner_frozen.py.txt` preserves exact execution source before collector hardening; current runner intentionally rejects old protocol source fingerprints.

Test generalization failed: baseline HOTA48.10%,IDF157.84%; sliced+BoT HOTA29.76%,IDF135.06%. Dev selected sliced+BoT only by a lexical tie: dev frame640×480 fits one640tile so sliced and standard detector results were identical. This tie did not provide evidence that slicing improves unseen1920×1080frames. No candidate was promoted.

Reproduction uses local exact source bytes+weights/native-library hashes. Run `industrial_ai/mot_tracking_study.py collect`, then `freeze`, `dev`, `select`, `test` into a fresh environment/output; completed source fixed paths are not overwritten. To audit original **stored predictions** without inference/test rerun, use archived runner snapshot with original dependency hashes and `score-dev`/`score-test`, see report. Numeric exports alone cannot reproduce metrics without local GT/prediction receipts; no redistribution rights are assumed.

Small-geometry subset has0test boxes (source-pixel area≤1024); its stored `small_recall=0` is empty-denominator output and **must be interpreted N/A**, not poor accuracy on small objects. CUDA times cover detector calls, not end-to-end live guarantees.
