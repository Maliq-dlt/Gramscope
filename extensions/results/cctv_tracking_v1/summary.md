# Frozen public tracking reference — 11 October 2026

The fixed YOLO26n/ByteTrack pipeline failed this sampled SDD reference: IDF1=0, IDTP=0, IDFP=2, IDFN=105743. Raw post-tracker and canonical receipts each contain exactly 2 predictions across 12,115 sampled frames. Maximum GT IoU for those predictions was 0.369583 and 0.314797, below the frozen 0.5 threshold. Recomputing native metrics from receipts reproduced the recorded result exactly.

The 40.4126-minute source timeline was sampled at 4.995 Hz (stride 6), with sequential decoding of all raw frames. This covers a sampled timeline, not uninterrupted monitoring exposure.

| Clip | Sampled frames | GT detections | Predictions | Native CLEAR frames | Median GT width×height at 640 (px) |
|---|---:|---:|---:|---:|---:|
|coupa/video0|1995|13908|0|0|17.78×14.87|
|coupa/video1|1995|10177|1|1995|22.95×16.17|
|coupa/video2|1995|9588|1|1995|20.36×16.17|
|coupa/video3|1995|26588|0|0|18.42×14.55|
|hyang/video0|1895|27042|0|0|11.96×21.28|
|hyang/video1|2240|18440|0|0|9.28×18.54|

Native CLEAR 1.3.0 leaves CLR_Frames=0 when it returns early for an empty tracker sequence. The preserved native aggregate therefore reports 3,990 frames and FP_per_frame=0.000501253. The explicit companion uses all 12,115 sampled frames: 2/12,115=0.000165085 tracking false-positive detections per sampled frame. Identity/CLEAR detection counts and IDF1 remain unchanged. Neither ratio measures incident false alerts per hour.

At 640-equivalent input scale, 75.26% of GT observations have an edge below 16 px. Median widths range 9.28–22.95 px and median heights 14.55–21.28 px. These are small aerial objects. Native ByteTrack hides new tracks until confirmation; its returned results do not expose pretracking candidates. The exact detector-versus-tracker contribution cannot be recovered from these receipts. No diagnostic reinference or model tuning was performed.

Runtime: RTX 4060 Laptop GPU (cuda:0), 330.2615 seconds, 73,475,072 peak CUDA allocated bytes. Pipeline time includes decoding, setup, inference and receipts; it is not a live camera latency measurement.

Only two aerial campus scenes are represented. No helmet, factory hazard, incident timing, false-alert or identity labels exist here. The negative result does not validate factory CCTV operation, and no confidence interval is claimed. Original Stanford CC BY-NC-SA 3.0 rights apply despite the Kaggle mirror CC0 metadata.

The source manifest, acquisition code, evaluator, model weights, frozen protocol and full run remain unchanged. This export includes aggregate evidence only: no spatial boxes, images or per-object track IDs.
