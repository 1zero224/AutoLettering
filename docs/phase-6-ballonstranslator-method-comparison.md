# Phase 6 BallonsTranslator Method Comparison

## Scope

This experiment studies BallonsTranslator's text detection and inpainting implementation on the current hard bubble case:

```text
record_id: GBC06_18.png#3
image: D:\work\autolettering\GBC06 (已翻 斗笠)\GBC06_18.png
target/layout bbox: [1087, 1335, 1312, 1621]
tight cleanup mask bbox: [1197, 1335, 1312, 1527]
```

The purpose is to avoid the earlier full-rectangle white fill failure. The large target bbox contains the target announcer text, neighbor bubble text `今日が初ライブ!`, and bottom line art. Cleanup must therefore use a tighter text mask rather than filling the whole layout bbox.

## BallonsTranslator Implementation Notes

- `ctd` is implemented by `ComicTextDetector` in `BallonsTranslator/ballontranslator/modules/textdetector/detector_ctd.py`.
  - CPU loads `data/models/comictextdetector.pt.onnx`.
  - Non-CPU loads `data/models/comictextdetector.pt`.
  - Parameter name for size is `detect_size`.
- `ysgyolo` is implemented by `YSGYoloDetector` in `BallonsTranslator/ballontranslator/modules/textdetector/detector_ysg.py`.
  - Default model is `data/models/ysgyolo_1.2_OS1.0.pt`.
  - BallonsTranslator does not declare an automatic download URL for this detector; README points to the Hugging Face model page for manual download.
  - Parameter name for size is `detect size`, but the current `_detect()` implementation does not pass it into `model.predict()`, so it is not effective in this checkout.
- `BaseModule.updateParam()` expects raw values, not UI-shaped dicts. Correct usage is `detector.updateParam("device", "cpu")`, not `{"value": "cpu"}`.
- BallonsTranslator registers `opencv-tela`, but this class currently calls `cv2.inpaint(..., cv2.INPAINT_NS)`. The experiment keeps the user-facing name `opencv_tela` and records the routed method as `opencv-tela_INPAINT_NS`.
- PatchMatch uses `BallonsTranslator/data/libs/patchmatch_inpaint.dll`.
- AOT uses `BallonsTranslator/data/models/aot_inpainter.ckpt`.
- `lama_mpe` uses `BallonsTranslator/data/models/lama_mpe.ckpt`.
- `lama_large_512px` uses `BallonsTranslator/data/models/lama_large_512px.ckpt`.

## Environment Fixes

The first detector runs exposed real integration issues:

1. `pillow_jxl` was missing because BallonsTranslator imports it from `utils/io_utils.py`.
2. The initial script passed `{"value": ...}` to `updateParam()`, which caused `int(dict)` conversion errors.
3. `cv2.imread()` could not read the Windows path containing Chinese characters after `chdir(BallonsTranslator)`, so the script now uses `np.fromfile()` plus `cv2.imdecode()`.
4. Installing `ultralytics` initially pulled `numpy 2.2.6`, which broke NumPy 1.x compiled extensions used by `matplotlib`/`skimage`; the working experiment uses `numpy 1.26.4` and `opencv-python 4.10.0.84`.

Additional packages installed for the experiment:

```powershell
python -m pip install --upgrade pillow-jxl-plugin
python -m pip install --upgrade "numpy==1.26.4" "opencv-python==4.10.0.84" "opencv-python-headless==4.10.0.84"
```

Earlier installed model/runtime packages used by this experiment:

```powershell
python -m pip install --upgrade onnxruntime einops ultralytics torchvision
python -m pip install --upgrade piexif docx2txt
```

## Final Command

```powershell
python experiments/phase6_bt_method_grid.py `
  --detection-run-dir outputs/runs/phase2-gbc06-diverse-expansion-v2-color-light-text `
  --record-id "GBC06_18.png#3" `
  --run-id phase6-bt-method-grid-gbc06-18-v6
```

The script creates near-square grids rather than long strips:

```text
outputs/runs/phase6-bt-method-grid-gbc06-18-v6/visuals/detector-grid.png
outputs/runs/phase6-bt-method-grid-gbc06-18-v6/visuals/inpaint-grid.png
```

MIMO records:

```text
outputs/runs/phase6-bt-method-grid-gbc06-18-v6/reports/mimo-detector-grid.json
outputs/runs/phase6-bt-method-grid-gbc06-18-v6/reports/mimo-inpaint-grid.json
outputs/runs/phase6-bt-method-grid-gbc06-18-v6/reports/bt-method-grid-summary.json
```

## Detector Results

| Method | Status | Observed result | MIMO score | Decision |
| --- | --- | --- | --- | --- |
| `ctd` | ok | Found a target block `[1194, 1332, 1314, 1526]`, very close to the tight cleanup mask `[1197, 1335, 1312, 1527]`, and separately found the neighbor bubble. | 8.5 | Best detector for this case. Good candidate for Phase 2 fallback/refinement. |
| `ysgyolo` | ok | Found the target but also generated large overlapping boxes and unrelated/background boxes. | 4.0 | Not acceptable as direct cleanup mask source without additional filtering. |

MIMO detector judgment:

```json
{
  "best_detector": "ctd",
  "scores": {
    "ctd": 8.5,
    "ysgyolo": 4.0
  },
  "unacceptable_methods": ["ysgyolo"]
}
```

Manual reading agrees with MIMO: `ctd` gives the cleanest target text grouping, while `ysgyolo` needs strict post-filtering by LabelPlus point/search region and box scale before it can be useful.

## Inpainting Results

All inpainting methods used the same local crop and tight text mask, so the comparison is about cleanup quality, not detection differences.

| Method | Status | MIMO score | Decision |
| --- | --- | ---: | --- |
| `lama_large_512px` | ok | 0.92 | Best final result in the v6 MIMO run. Cleanest target removal with neighbor text and bottom line art preserved. |
| `patchmatch` | ok | 0.85 | Strong lightweight fallback. Leaves some gray residue but avoids the big white rectangle. |
| `aot` | ok | 0.65 | Usable but leaves faint smudges. |
| `opencv_tela` | ok | 0.20 | Not acceptable here; leaves obvious ghost text. |
| `lama_mpe` | ok | 0.15 | Not acceptable in the final v6 run; leaves visible ghosting/smearing. |

MIMO inpaint ranking:

```json
{
  "best_inpaint_method": "lama_large_512px",
  "ranking": [
    "lama_large_512px",
    "patchmatch",
    "aot",
    "opencv_tela",
    "lama_mpe"
  ],
  "unacceptable_methods": ["opencv_tela", "lama_mpe"]
}
```

Manual reading of the grid mostly matches the ranking. `opencv_tela` is clearly too weak for this bubble. `patchmatch`, `aot`, and `lama_large_512px` all preserve the left neighbor text and bottom art; `lama_large_512px` is the best candidate for higher-quality output, while `patchmatch` is much faster and good enough as a local fallback.

## Integration Decision

Use this as the next Phase 6 direction:

1. Prefer `ctd` for BallonsTranslator-based text detection refinement around difficult LabelPlus records.
2. Keep the current Phase 2 candidate-cluster tight mask logic for cleanup, because it excludes the neighbor `今日が初ライブ!` and bottom line art.
3. Use `text_mask_inpaint` with `bt_lama_large` as the quality-first bubble cleanup method.
4. Keep `bt_patchmatch` as a faster fallback/comparison method.
5. Do not use full-bbox `region_fill` for diamond/overlapping bubble cases.
6. Do not use `opencv_tela` for this case except as a negative baseline.
7. Do not use raw `ysgyolo` output as a cleanup mask without post-filtering.

## Preserved Evidence Runs

The intermediate runs are intentionally preserved because they document the integration failures and fixes:

```text
phase6-bt-method-grid-gbc06-18-v1  missing pillow_jxl
phase6-bt-method-grid-gbc06-18-v2  wrong updateParam dict values
phase6-bt-detectors-gbc06-18-v3    Windows/Chinese path cv2.imread failure
phase6-bt-detectors-gbc06-18-v4    ctd succeeded, ysgyolo blocked by numpy 2 ABI
phase6-bt-detectors-gbc06-18-v5    ctd and ysgyolo both succeeded
phase6-bt-method-grid-gbc06-18-v6  final detector + inpaint + MIMO run
```
