# Phase 6 GBC06 Bubble Cleanup Smoke Report

## Commands

Baseline full-rectangle fill:

```powershell
python experiments/phase6_bubble_cleanup.py --detection-run-dir outputs/runs/phase2-gbc06-smoke --layout-run-dir outputs/runs/phase4-gbc06-layout-smoke --run-id phase6-gbc06-bubble-smoke --sample-limit 1
```

Mask-limited fill:

```powershell
python experiments/phase6_bubble_cleanup.py --detection-run-dir outputs/runs/phase2-gbc06-smoke --layout-run-dir outputs/runs/phase4-gbc06-layout-smoke --run-id phase6-gbc06-bubble-mask-smoke --sample-limit 1 --cleanup-method mask_fill
```

Region-limited fill, current default:

```powershell
python experiments/phase6_bubble_cleanup.py --detection-run-dir outputs/runs/phase2-gbc06-smoke --layout-run-dir outputs/runs/phase4-gbc06-tight-text-layout-smoke --run-id phase6-gbc06-bubble-region-fill-experiment --sample-limit 1 --cleanup-method region_fill
```

Integrated preview/export with new bubble cleanup and LaMa non-bubble cleanup:

```powershell
python experiments/phase7_8_integrated_smoke.py --detection-run-dir outputs/runs/phase2-gbc06-smoke --cleanup-run-dir outputs/runs/phase6-gbc06-bubble-region-fill-experiment --cleanup-run-dir outputs/runs/phase6-gbc06-nonbubble-lama-large-compare --layout-run-dir outputs/runs/phase4-gbc06-tight-text-layout-smoke --font-selection-run-dir outputs/runs/phase3-gbc06-nonbubble-mimo-font-smoke --run-id phase7-8-gbc06-region-fill-layout-smoke --sample-limit 2
```

## Output

Baseline run:

```text
outputs/runs/phase6-gbc06-bubble-smoke
```

Mask-fill run:

```text
outputs/runs/phase6-gbc06-bubble-mask-smoke
```

Region-fill run:

```text
outputs/runs/phase6-gbc06-bubble-region-fill-experiment
```

Comparison and MIMO evaluation:

- `outputs/runs/phase6-gbc06-bubble-mask-smoke/reports/bubble-cleanup-comparison.png`
- `outputs/runs/phase6-gbc06-bubble-mask-smoke/reports/mimo-bubble-cleanup-evaluation.json`
- `outputs/runs/phase6-gbc06-bubble-region-fill-experiment/reports/bubble-region-fill-comparison.png`
- `outputs/runs/phase6-gbc06-bubble-region-fill-experiment/reports/mimo-bubble-region-fill-evaluation.json`
- `outputs/runs/phase6-gbc06-bubble-region-fill-experiment/reports/mimo-gpt-image2-reevaluation.json`
- `outputs/runs/phase7-8-gbc06-region-fill-layout-smoke/runs/phase7-preview/debug/evaluation_contact_sheets/GBC06-01-png.png`
- `outputs/runs/phase7-8-gbc06-region-fill-layout-smoke/runs/phase7-evaluation/preview-evaluation.jsonl`

## Result Summary

- Detection source: `outputs/runs/phase2-gbc06-smoke/detections.jsonl`
- Layout source: `outputs/runs/phase4-gbc06-layout-smoke/layout-results.jsonl`
- Record: `GBC06_01.png#1`
- Group: `框内`
- Translation: `街头演出？`
- Phase 2 selected bbox: `[674, 0, 1049, 342]`
- Baseline method: `bubble_fill`
- Previous method: `bubble_mask_fill`
- Current default method: `bubble_region_fill`
- Region-fill cleaned crop: `outputs/runs/phase6-gbc06-bubble-region-fill-experiment/crops/cleaned/GBC06-01-png-1.png`
- Region-fill before/after crop: `outputs/runs/phase6-gbc06-bubble-region-fill-experiment/crops/before_after/GBC06-01-png-1.png`

## Root Cause

The previous cleanup filled the entire Phase 2 selected bbox. On `GBC06_01.png#1`, that bbox includes the speech bubble plus surrounding screentone and character hair. Full-rectangle fill therefore erased valid manga art, not just source text.

The better approach follows the BallonsTranslator inpainting pattern: use the large detection region as crop context, but restrict actual cleanup to a text mask / text candidate area.

## BallonsTranslator Inpainting Survey

Files inspected:

- `BallonsTranslator/ballontranslator/modules/inpaint/base.py`
- `BallonsTranslator/ballontranslator/modules/inpaint/inpaint_default.py`
- `BallonsTranslator/ballontranslator/modules/inpaint/lama.py`
- `BallonsTranslator/ballontranslator/modules/inpaint/aot.py`
- `BallonsTranslator/ballontranslator/modules/inpaint/patch_match.py`
- `BallonsTranslator/ballontranslator/utils/textblock_mask.py`

Relevant design points:

- BallonsTranslator separates a large contextual crop from the actual edited mask. This prevents losing surrounding manga art while still giving the inpaint/fill method enough context.
- `InpainterBase` has a flat balloon shortcut: if the non-text background is uniform, it fills the balloon/text region with sampled background color instead of always running a heavy model.
- For non-bubble content, BallonsTranslator's current default family is `lama_large_512px`; it also exposes OpenCV, PatchMatch, AOT, LaMa MPE, and Flux options.

Method options and tradeoffs:

- OpenCV Telea/NS: fastest and dependency-light, but previous MIMO evaluation marked both unacceptable on the GBC06 non-bubble sample because of visible ghosting/smearing.
- PatchMatch: fast native repair and very clean on flat/near-white areas; risk is native DLL dependency and weaker generalization on complex screentone/art textures.
- AOT: manga-image-translator style model path, but local weights were not present and LaMa was already BallonsTranslator's manga default.
- LaMa large 512px: heavier PyTorch path but best prior MIMO score on non-bubble cleanup; kept as preferred non-bubble method.
- Flux2-klein: potentially stronger generative inpaint path, but much heavier diffusers/transformer/GGUF stack and not suitable for this minimal local experiment.
- gpt-image-2 masked edit: real result was re-evaluated by MIMO in this run and scored `0`, unusable for direct replacement because text length/layout/style broke the composition and overlapped nearby art. It remains an experimental path, not the default cleanup.

## Current Algorithm

`bubble_region_fill`, current default:

1. Reads Phase 2 `candidate_boxes`.
2. Filters out candidates that are effectively the large selected region.
3. Unions the smaller candidate boxes inside the selected bbox, so multiple vertical text columns are handled together.
4. Expands the union text bbox by a small padding.
5. Samples the surrounding local background color.
6. Fills the whole padded text region inside the larger crop.
7. Saves before, cleaned, and before/after crop artifacts.

`bubble_mask_fill` is still available through `--cleanup-method mask_fill` for comparison and fallback. It fills only thresholded dark glyph pixels:

1. Builds a dark-pixel mask only inside the union text bbox.
2. Dilates the text mask and fills only masked pixels with the local sampled background color.
3. Saves before, cleaned, and before/after crop artifacts.

The switch to region fill fixes the remaining faint source-text ghosts from the mask-fill method while still avoiding heavyweight inpainting for flat white speech bubbles.

## Overlapping Bubble Composition Update

The `GBC06_02.png#1-#3` batch exposed a separate composition failure:

- `GBC06_02.png#2` and `GBC06_02.png#3` use overlapping selected/crop regions.
- Whole-crop page composition pasted `#3` after `#2`, restoring old Japanese pixels inside the part of `#2` that had already been cleaned.
- MIMO scored that intermediate result `3`, unusable, even after the tight text bbox itself was corrected.

The current bubble cleanup output therefore also writes:

```text
crops/mask/*.png
cleanup.cleanup_mask_path
```

Phase 7 now pastes cleanup crops through that mask when available, and applies all cleanup layers before any text overlay. This keeps the large crop as context/debug evidence while limiting the actual page edit to the region that Phase 6 changed.

Best follow-up run:

```text
outputs/runs/phase7-8-gbc06-02-batch-1-3-preview-v3
```

MIMO result:

```json
{
  "score": 7,
  "usable": true,
  "original_text_removed": true,
  "art_preserved": true,
  "lettering_readable": true
}
```

Per-record MIMO scores:

```text
GBC06_02.png#1  score=7  usable=true
GBC06_02.png#2  score=10 usable=true
GBC06_02.png#3  score=10 usable=true
```

An attempted vertical-column top-alignment optimization was tested in `phase7-8-gbc06-02-batch-1-3-preview-v4`, but MIMO score dropped to `5`, so that rendering change was reverted and kept only as a negative experiment artifact.

## Multi-column Cleanup Crop Update

The `GBC06_02.png#4-#6` batch exposed another cleanup-range mismatch:

- `GBC06_02.png#5` Phase 2 selected bbox was only `[245, 516, 280, 636]`, covering the rightmost source text column.
- Phase 4 correctly expanded the layout/text target to `[167, 511, 280, 732]`, covering the full multi-column source text area.
- Phase 6 still cleaned only the selected bbox, so the final text overlay occupied a region that had not been fully cleaned.

Phase 6 now cleans the union of:

```text
detection.selected_text_box_xyxy
selected_text_bbox(detection)
```

This keeps the large crop/context and mask-aware composition behavior from the previous update, while ensuring the actual cleaned crop is at least as large as the derived text region used by layout and preview.

Baseline failed run:

```text
outputs/runs/phase7-8-gbc06-02-batch-4-6-preview-v1
```

MIMO result:

```json
{
  "score": 2,
  "usable": false
}
```

Best follow-up run:

```text
outputs/runs/phase7-8-gbc06-02-batch-4-6-preview-v2
```

MIMO result:

```json
{
  "score": 8,
  "usable": true,
  "original_text_removed": true,
  "art_preserved": true,
  "lettering_readable": true
}
```

Per-record MIMO scores:

```text
GBC06_02.png#4  score=9 usable=true
GBC06_02.png#5  score=8 usable=true
GBC06_02.png#6  score=9 usable=true
```

## MIMO Evaluation

MIMO vision model: `mimo-v2.5`

Evaluation file:

```text
outputs/runs/phase6-gbc06-bubble-mask-smoke/reports/mimo-bubble-cleanup-evaluation.json
```

Returned ranking:

```json
{
  "best_method": "new_mask_fill",
  "ranking": ["new_mask_fill", "old_full_rect_fill"],
  "scores": {
    "new_mask_fill": 9,
    "old_full_rect_fill": 2
  },
  "unacceptable_methods": ["old_full_rect_fill"]
}
```

MIMO summary: the old full-rectangle fill destroys the speech bubble, outline, screentone, and nearby art. The new mask fill isolates the text, preserves the bubble border and surrounding background, and leaves a clean area for later Chinese lettering. Remaining issue: a faint artifact can still be visible near the bubble edge.

Second evaluation, comparing `old_mask_fill` against `new_region_fill`:

```json
{
  "best_method": "new_region_fill",
  "ranking": ["new_region_fill", "old_mask_fill"],
  "scores": {
    "old_mask_fill": 9,
    "new_region_fill": 10
  },
  "unacceptable_methods": []
}
```

MIMO summary: both methods remove the main Japanese text and preserve nearby art, but `old_mask_fill` leaves very faint ghost-like remnants. `new_region_fill` produces a cleaner, more uniform white fill.

Integrated Phase 7/8 MIMO evaluation with `bubble_region_fill` plus `bt_lama_large_inpaint`:

```json
{
  "score": 9,
  "usable": true,
  "original_text_removed": true,
  "art_preserved": true,
  "lettering_readable": true,
  "issues": []
}
```

The integrated smoke manifest confirms the effective cleanup methods:

```json
{
  "bubble_region_fill": 1,
  "bt_lama_large_inpaint": 1
}
```

gpt-image-2 direct replacement MIMO re-evaluation:

```json
{
  "method": "gpt_image2_direct_replacement",
  "score": 0,
  "usable": false
}
```

MIMO summary: the translation semantics are acceptable, but the generated replacement text is much too long, uses the wrong style, breaks the vertical composition, and overlaps the top diamond mark.

## Limitations

- The region still depends on Phase 2 candidate boxes. If detection misses a text column, cleanup can miss it too.
- Region fill is intentionally for flat/light bubble interiors. It can erase decorative in-bubble art if the candidate text union includes non-text art.
- This method is intended for flat/light bubble interiors. For complex non-bubble backgrounds, use the non-bubble inpaint methods.

## Verification

Fresh targeted verification after the region-fill change:

```powershell
python -m pytest tests/test_phase6_cleanup.py -q
python -m pytest tests/test_phase6_nonbubble_cleanup.py tests/test_phase6_cleanup.py -q
python -m pytest -q
```

Observed results:

```text
7 passed in 0.25s
16 passed in 1.46s
89 passed in 3.31s
```

## Notes

- Generated `outputs/` are ignored by Git; this report records reproducible commands and artifact paths.
- No API credential or raw `.env` value is stored in outputs or this report.
