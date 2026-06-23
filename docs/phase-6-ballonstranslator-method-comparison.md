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

Grid dimensions were checked after the final run:

```text
detector-grid.png 750x678
inpaint-grid.png  1120x1012
```

Both sheets keep the row/column count close enough for MIMO inspection and
avoid the long-strip failure mode.

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

## Method Label Mapping

The experiment labels intentionally keep short CLI-safe names, while the routed
implementation records the exact BallonsTranslator path used for each method.

| Experiment label | Routed method | BallonsTranslator source | Directly instantiated BT class? | Note |
| --- | --- | --- | --- | --- |
| `ctd` | `ComicTextDetector` | `ballontranslator/modules/textdetector/detector_ctd.py` | yes | CPU path loads `comictextdetector.pt.onnx`. |
| `ysgyolo` | `YSGYoloDetector` | `ballontranslator/modules/textdetector/detector_ysg.py` | yes | Current BT `_detect()` does not pass `detect size` into `model.predict()`. |
| `opencv_tela` | `opencv-tela_INPAINT_NS` | `ballontranslator/modules/inpaint/inpaint_default.py` | behavior matched directly | BT registers `opencv-tela`, but the implementation calls `cv2.INPAINT_NS`, not `cv2.INPAINT_TELEA`. |
| `patchmatch` | `bt_patchmatch_inpaint` | `ballontranslator/modules/inpaint/patch_match.py` | via project wrapper | Wrapper loads BT's native PatchMatch DLL path. |
| `aot` | `bt_aot_inpaint` | `ballontranslator/modules/inpaint/aot.py` | via project wrapper | Wrapper loads BT's AOT checkpoint and tensor preprocessing path. |
| `lama_mpe` | `lama_mpe_inpaint` | `ballontranslator/modules/inpaint/lama.py` | direct loader call | The script calls BT's `load_lama_mpe(..., use_mpe=True)`. |
| `lama_large_512px` | `bt_lama_large_inpaint` | `ballontranslator/modules/inpaint/lama.py` | via project wrapper | Wrapper calls `load_lama_mpe(..., use_mpe=False, large_arch=True)`. |

## Integration Decision

Use this as the next Phase 6 direction:

1. Prefer `ctd` for BallonsTranslator-based text detection refinement around difficult LabelPlus records.
2. Keep the current Phase 2 candidate-cluster tight mask logic for cleanup, because it excludes the neighbor `今日が初ライブ!` and bottom line art.
3. Use `text_mask_inpaint` with `bt_lama_large` as the quality-first bubble cleanup method.
4. Keep `bt_patchmatch` as a faster fallback/comparison method.
5. Do not use full-bbox `region_fill` for diamond/overlapping bubble cases.
6. Do not use `opencv_tela` for this case except as a negative baseline.
7. Do not use raw `ysgyolo` output as a cleanup mask without post-filtering.

## Phase 7 Follow-up: Tight Layout Target

After connecting the best cleanup path into Phase 7, MIMO exposed a second issue: cleanup was fixed, but lettering was still using the large layout bbox.

| Run | Cleanup bbox | Text/layout bbox | Layout source | MIMO score | Result |
| --- | --- | --- | --- | ---: | --- |
| `phase7-gbc06-18-text-mask-lama-large-v1` | `[1087, 1335, 1312, 1621]` | `[1087, 1335, 1312, 1621]` | old large layout | 4 | Text overlapped the adjacent `今日が初ライブ!` bubble text. |
| `phase7-gbc06-18-text-mask-lama-large-v2` | `[1087, 1335, 1312, 1621]` | `[1197, 1335, 1312, 1527]` | old layout squeezed into tight bbox | 7 | No longer covered the neighbor text, but lettering was still slightly too large. |
| `phase7-gbc06-18-text-mask-lama-large-v3` | `[1087, 1335, 1312, 1621]` | `[1197, 1335, 1312, 1527]` | tight-mask layout `115x192` | 8 | Text is readable and placed inside the intended area; remaining issues are minor inpaint edge artifacts and slightly tight spacing. |

The fix is now shared across phases:

- `autolettering/text_mask_bbox.py` contains the same-record text-mask clustering used for this case.
- Phase 6 writes `cleanup.text_bbox`, `cleanup.mask_bbox`, and `cleanup.layout_text_bbox`.
- Phase 7 prefers `cleanup.layout_text_bbox` over stale `layout.target_bbox` when composing the page.
- Phase 4 also uses the same mask bbox for bubble layout targets when the selected/full bbox includes neighboring speech bubble text.

Current evidence:

```text
outputs/runs/phase4-gbc06-diverse-06-18-layout-tight-mask-v2/layout-results.jsonl
outputs/runs/phase6-gbc06-18-text-mask-bt-lama-large-v2/cleanup-results.jsonl
outputs/runs/phase7-gbc06-18-text-mask-lama-large-v3/preview-results.jsonl
outputs/runs/phase7-gbc06-18-text-mask-lama-large-eval-v3/preview-evaluation.jsonl
outputs/runs/phase7-gbc06-18-text-mask-lama-large-v3/debug/evaluation_contact_sheets/GBC06-18-png.png
```

The v3 MIMO result:

```json
{
  "score": 8,
  "usable": true,
  "original_text_removed": true,
  "art_preserved": true,
  "lettering_readable": true,
  "issues": [
    "Minor anti-aliasing artifacts visible around the text edges from the inpainting process.",
    "The spacing between the second and third lines is slightly tight."
  ]
}
```

## Phase 8 Follow-up: Photoshop Export

The tight text bbox now also flows into Photoshop export:

- Cleanup bitmap patch placement remains `cleanup.bbox = [1087, 1335, 1312, 1621]`, so the inpainted crop covers the full local context.
- Editable Photoshop text placement uses `text_bbox = [1197, 1335, 1312, 1527]`, so the text layer does not cover neighboring speech-bubble text.
- Vertical top anchoring uses `vertical_top_anchor_y_px = 1335`, matching `text_position.y_px`.
- `cleanup.text_bbox`, `cleanup.mask_bbox`, and `cleanup.layout_text_bbox` are exported in `photoshop-manifest.json` for auditability.

Current evidence:

```text
outputs/runs/phase8-gbc06-18-text-mask-lama-large-v1/photoshop-manifest.json
outputs/runs/phase8-gbc06-18-text-mask-lama-large-v1/photoshop-import.jsx
outputs/runs/phase8-gbc06-18-text-mask-lama-large-audit-v1/phase8-export-audit.json
```

Phase 8 audit result:

```json
{
  "record_count": 1,
  "vertical_top_layer_count": 1,
  "missing_vertical_top_anchor_count": 0,
  "unexpected_vertical_top_anchor_count": 0,
  "record_issue_count": 0,
  "jsx_anchor_logic_present": true,
  "passed": true
}
```

## Phase 6 Follow-up: Mask Variant Tuning

A follow-up experiment keeps the best `bt_lama_large` inpainter fixed and
compares cleanup mask shapes/thresholds for the same hard record. The key
result is that broad rectangular masks reproduce the visible white-block
failure, while tight text-pixel masks remain the usable direction.

Evidence:

```text
docs/phase-6-gbc06-18-mask-variant-experiment-report.md
outputs/runs/phase6-gbc06-18-mask-variant-lama-large-v2/visuals/mask-variant-grid.png
outputs/runs/phase6-gbc06-18-mask-variant-lama-large-v2/reports/mimo-mask-variant-evaluation.json
outputs/runs/phase6-gbc06-18-mask-variant-tight-finalists-v2/visuals/mask-variant-mimo-grid.png
outputs/runs/phase6-gbc06-18-mask-variant-tight-finalists-v2/reports/mimo-mask-variant-evaluation.json
```

Crop-level MIMO preferred `tight_t185_d5` among tight-mask finalists, so Phase 6
now exposes `--mask-dilate-px` for explicit hard-case experiments. The default
remains `3`: the d5 page-level preview is usable, but its MIMO score was `7`,
below the previous d3/tight-layout page score `8`, because the remaining
bottleneck is translated lettering size/weight rather than cleanup.

## Phase 7 Follow-up: Layout and Cleanup Coupling

After the phrase-aware vertical layout was promoted into the Phase 4 search, the
same d3 cleanup became visibly worse at page-preview level. The smaller,
narrower Chinese lettering no longer covered the residual inpaint artifacts, so
MIMO correctly downgraded the page:

```text
outputs/runs/phase7-gbc06-18-phrase-aware-layout-v1/preview-evaluation.jsonl
score: 4
issue: original Japanese text still visible / cluttered overlap
```

Re-running the same layout with the stronger d5 text mask fixed that failure:

```text
outputs/runs/phase7-gbc06-18-phrase-aware-layout-d5-v1/pages/GBC06-18-png.png
outputs/runs/phase7-gbc06-18-phrase-aware-layout-d5-eval-v1/preview-evaluation.jsonl
score: 9
usable: true
original_text_removed: true
```

A near-square MIMO comparison grid was then generated from the same target
`text_bbox`, so the unrelated neighboring `今日が初ライブ!` block was not scored:

```powershell
python experiments/phase7_preview_method_comparison.py `
  --method old_fs33_d3=outputs/runs/phase7-gbc06-18-text-mask-lama-large-v3 `
  --method phrase_fs25_d3=outputs/runs/phase7-gbc06-18-phrase-aware-layout-v1 `
  --method phrase_fs25_d5=outputs/runs/phase7-gbc06-18-phrase-aware-layout-d5-v1 `
  --evaluation old_fs33_d3=outputs/runs/phase7-gbc06-18-text-mask-lama-large-eval-v3 `
  --evaluation phrase_fs25_d3=outputs/runs/phase7-gbc06-18-phrase-aware-layout-eval-v1 `
  --evaluation phrase_fs25_d5=outputs/runs/phase7-gbc06-18-phrase-aware-layout-d5-eval-v1 `
  --run-id phase7-gbc06-18-layout-cleanup-comparison-v1 `
  --crop-mode text `
  --mimo
```

Evidence:

```text
outputs/runs/phase7-gbc06-18-layout-cleanup-comparison-v1/debug/near-square-result-grid.png
outputs/runs/phase7-gbc06-18-layout-cleanup-comparison-v1/reports/mimo-near-square-comparison.json
outputs/runs/phase7-gbc06-18-layout-cleanup-comparison-v1/method-comparison.json
```

The comparison grid is `636x760`. MIMO selected `phrase_fs25_d5`:

```json
{
  "best_method": "phrase_fs25_d5",
  "ranking": ["phrase_fs25_d5", "old_fs33_d3", "phrase_fs25_d3"],
  "scores": {
    "phrase_fs25_d5": 9,
    "old_fs33_d3": 8,
    "phrase_fs25_d3": 4
  },
  "unacceptable_methods": ["phrase_fs25_d3"]
}
```

Updated decision for this hard record:

1. Keep `lama_large_512px` as the quality-first inpainter.
2. Keep tight text-pixel masking; never fall back to a full rectangular white
   fill for this overlapping diamond block.
3. Use d5 dilation as the explicit hard-case cleanup setting when the final
   lettering is narrower than the removed source text and d3 residuals become
   visible.
4. Treat cleanup and lettering as coupled: a layout that is typographically
   better can reveal inpaint defects that were hidden by an oversized old
   layout.

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
