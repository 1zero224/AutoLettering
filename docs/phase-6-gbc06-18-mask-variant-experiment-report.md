# Phase 6 GBC06_18 Mask Variant Experiment

## Purpose

This experiment targets the hard overlapping speech-bubble record:

```text
record_id: GBC06_18.png#3
image: D:\work\autolettering\GBC06 (已翻 斗笠)\GBC06_18.png
cleanup crop/text bbox: [1087, 1335, 1312, 1621]
tight mask/layout bbox: [1197, 1335, 1312, 1527]
```

The previous BallonsTranslator method comparison showed that `bt_lama_large`
is the best cleanup model for this case, but the cleaned crop still had faint
source-text residue. This follow-up keeps the same model and compares mask
shape/threshold variants, because broad rectangular masks were the root cause
of the earlier visible white-block failure.

## Implementation

New experiment entry point:

```text
experiments/phase6_mask_variant_experiment.py
```

The script is intentionally independent from the default Phase 6 pipeline:

- It reads one detection record from `detections.jsonl`.
- It writes to an explicit `outputs/runs/<run-id>` directory.
- It does not change `run_phase6_bubble_cleanup()` defaults.
- It saves per-variant `mask.png`, `mask-overlay.png`, `cleaned.png`, and `before-after.png`.
- It writes two near-square grids:
  - detailed mask + output grid for manual review
  - cleaned-only grid for MIMO
- It records MIMO request/response summaries and does not log API keys.

Phase 6 now also accepts an explicit text-mask dilation-size parameter:

```powershell
python experiments/phase6_bubble_cleanup.py `
  --cleanup-method text_mask_inpaint `
  --inpaint-method bt_lama_large `
  --mask-dilate-px 5
```

The default remains `mask_dilate_px=3`, so existing Phase 6 runs are not changed
unless this parameter is passed deliberately.

## Broad Variant Run

Command:

```powershell
python experiments/phase6_mask_variant_experiment.py `
  --detection-run-dir outputs/runs/phase2-gbc06-diverse-expansion-v2-color-light-text `
  --record-id "GBC06_18.png#3" `
  --run-id phase6-gbc06-18-mask-variant-lama-large-v2
```

Artifacts:

```text
outputs/runs/phase6-gbc06-18-mask-variant-lama-large-v2/visuals/mask-variant-grid.png
outputs/runs/phase6-gbc06-18-mask-variant-lama-large-v2/visuals/mask-variant-mimo-grid.png
outputs/runs/phase6-gbc06-18-mask-variant-lama-large-v2/reports/mimo-mask-variant-evaluation.json
outputs/runs/phase6-gbc06-18-mask-variant-lama-large-v2/reports/mask-variant-summary.json
```

Grid sizes:

```text
mask-variant-grid.png       1370x1186  ratio=1.155
mask-variant-mimo-grid.png  1030x892   ratio=1.155
```

MIMO result:

```json
{
  "best_variant": "tight_t185_d3",
  "ranking": [
    "tight_t185_d3",
    "tight_t210_d5",
    "tight_t235_d7",
    "rect_expand2",
    "tight_t210_d9",
    "hybrid_rect_expand2_text_t210_d5"
  ],
  "scores": {
    "tight_t185_d3": 8,
    "tight_t210_d5": 7,
    "tight_t235_d7": 6,
    "rect_expand2": 4,
    "tight_t210_d9": 4,
    "hybrid_rect_expand2_text_t210_d5": 2
  },
  "unacceptable_variants": [
    "rect_expand2",
    "hybrid_rect_expand2_text_t210_d5"
  ]
}
```

Interpretation:

- The tight text masks are all better than rectangular masks.
- `rect_expand2` reproduces the visible hard-edged white-block problem and
  must not be used for this case.
- The hybrid rectangular/text mask collapsed to the rectangular mask on this
  sample and was removed from the script defaults.

## Tight Finalist Run

After the broad run, the script was extended to support parameterized variants
such as `tight_t170_d1`. The finalist run compares only tight text masks.

Command:

```powershell
python experiments/phase6_mask_variant_experiment.py `
  --detection-run-dir outputs/runs/phase2-gbc06-diverse-expansion-v2-color-light-text `
  --record-id "GBC06_18.png#3" `
  --run-id phase6-gbc06-18-mask-variant-tight-finalists-v2 `
  --variant tight_t170_d1 `
  --variant tight_t185_d3 `
  --variant tight_t195_d3 `
  --variant tight_t185_d5
```

Artifacts:

```text
outputs/runs/phase6-gbc06-18-mask-variant-tight-finalists-v2/visuals/mask-variant-grid.png
outputs/runs/phase6-gbc06-18-mask-variant-tight-finalists-v2/visuals/mask-variant-mimo-grid.png
outputs/runs/phase6-gbc06-18-mask-variant-tight-finalists-v2/reports/mimo-mask-variant-evaluation.json
outputs/runs/phase6-gbc06-18-mask-variant-tight-finalists-v2/reports/mask-variant-summary.json
```

Grid sizes:

```text
mask-variant-grid.png       1030x892  ratio=1.155
mask-variant-mimo-grid.png  690x892   ratio=0.774
```

The MIMO grid uses a `2x3` tile layout for five images, which keeps row and
column counts close instead of producing a long horizontal strip.

MIMO result:

```json
{
  "best_variant": "tight_t185_d5",
  "ranking": [
    "tight_t185_d5",
    "tight_t170_d1",
    "tight_t185_d3",
    "tight_t195_d3"
  ],
  "scores": {
    "tight_t185_d5": 90,
    "tight_t170_d1": 70,
    "tight_t185_d3": 65,
    "tight_t195_d3": 40
  },
  "unacceptable_variants": [
    "tight_t195_d3"
  ]
}
```

Mask metrics:

```json
{
  "tight_t170_d1": {
    "mask_pixels": 4623,
    "after_dark_lt80": 0,
    "after_mean": 250.43,
    "after_std": 4.29
  },
  "tight_t185_d3": {
    "mask_pixels": 4698,
    "after_dark_lt80": 0,
    "after_mean": 250.82,
    "after_std": 3.23
  },
  "tight_t195_d3": {
    "mask_pixels": 4748,
    "after_dark_lt80": 0,
    "after_mean": 250.97,
    "after_std": 2.84
  },
  "tight_t185_d5": {
    "mask_pixels": 6986,
    "after_dark_lt80": 0,
    "after_mean": 252.29,
    "after_std": 2.0
  }
}
```

Interpretation:

- Crop-level MIMO prefers `tight_t185_d5`: it removes more ghosting while
  preserving nearby text and line art in the finalist grid.
- `tight_t195_d3` is too aggressive according to MIMO and should not be used.
- `tight_t185_d5` is not a rectangular fill; it is still a text-pixel mask with
  a slightly larger dilation radius.

## Phase 7 Page-Level Check

The best crop-level finalist was then passed through the normal Phase 6 and
Phase 7 flow using the explicit dilation parameter.

Commands:

```powershell
python experiments/phase6_bubble_cleanup.py `
  --detection-run-dir outputs/runs/phase2-gbc06-diverse-expansion-v2-color-light-text `
  --layout-run-dir outputs/runs/phase4-gbc06-diverse-06-18-layout-tight-mask-v2 `
  --record-id "GBC06_18.png#3" `
  --sample-limit 1 `
  --cleanup-method text_mask_inpaint `
  --inpaint-method bt_lama_large `
  --mask-dilate-px 5 `
  --run-id phase6-gbc06-18-text-mask-bt-lama-large-d5-v1

python experiments/phase7_page_preview.py `
  --detection-run-dir outputs/runs/phase2-gbc06-diverse-expansion-v2-color-light-text `
  --cleanup-run-dir outputs/runs/phase6-gbc06-18-text-mask-bt-lama-large-d5-v1 `
  --layout-run-dir outputs/runs/phase4-gbc06-diverse-06-18-layout-tight-mask-v2 `
  --run-id phase7-gbc06-18-text-mask-lama-large-d5-v1 `
  --sample-limit 1

python experiments/phase7_preview_evaluate.py `
  --preview-run-dir outputs/runs/phase7-gbc06-18-text-mask-lama-large-d5-v1 `
  --run-id phase7-gbc06-18-text-mask-lama-large-d5-eval-v1 `
  --sample-limit 1
```

Evidence:

```text
outputs/runs/phase6-gbc06-18-text-mask-bt-lama-large-d5-v1/cleanup-results.jsonl
outputs/runs/phase7-gbc06-18-text-mask-lama-large-d5-v1/pages/GBC06-18-png.png
outputs/runs/phase7-gbc06-18-text-mask-lama-large-d5-v1/debug/evaluation_contact_sheets/GBC06-18-png.png
outputs/runs/phase7-gbc06-18-text-mask-lama-large-d5-eval-v1/preview-evaluation.jsonl
```

The cleanup result records the explicit parameter:

```json
{
  "mask_dilate_px": 5,
  "mask_bbox": [1197, 1335, 1312, 1527],
  "layout_text_bbox": [1197, 1335, 1312, 1527]
}
```

Page-level MIMO result:

```json
{
  "score": 7,
  "usable": true,
  "original_text_removed": true,
  "art_preserved": true,
  "lettering_readable": true,
  "issues": [
    "The translated lettering is noticeably larger and bolder than the original text area, causing the text to extend beyond the intended bounds, which is particularly evident with the bottom characters."
  ]
}
```

This means `tight_t185_d5` is a useful cleanup candidate but is not enough to
beat the previous page-level best run by itself. The d5 preview is still usable,
but the page-level score dropped from the earlier d3/tight-layout score `8` to
`7`, mainly because the remaining bottleneck is translated text sizing/weight
rather than cleanup.

## Decision

- Keep the current default text-mask dilation at `3`.
- Keep `--mask-dilate-px 5` as an explicit hard-case experiment option.
- Do not use rectangular masks for this case.
- The next quality work should focus on Phase 4/7 lettering size and spacing;
  cleanup alone no longer dominates the page-level score.

## Verification

Fresh targeted verification:

```powershell
python -m pytest tests/test_phase6_cleanup.py tests/test_phase6_mask_variant_experiment.py -q
```

Observed result:

```text
23 passed in 1.11s
```
