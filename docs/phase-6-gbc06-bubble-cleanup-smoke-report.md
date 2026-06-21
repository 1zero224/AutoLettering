# Phase 6 GBC06 Bubble Cleanup Smoke Report

## Commands

Baseline full-rectangle fill:

```powershell
python experiments/phase6_bubble_cleanup.py --detection-run-dir outputs/runs/phase2-gbc06-smoke --layout-run-dir outputs/runs/phase4-gbc06-layout-smoke --run-id phase6-gbc06-bubble-smoke --sample-limit 1
```

Mask-limited fill:

```powershell
python experiments/phase6_bubble_cleanup.py --detection-run-dir outputs/runs/phase2-gbc06-smoke --layout-run-dir outputs/runs/phase4-gbc06-layout-smoke --run-id phase6-gbc06-bubble-mask-smoke --sample-limit 1
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

Comparison and MIMO evaluation:

- `outputs/runs/phase6-gbc06-bubble-mask-smoke/reports/bubble-cleanup-comparison.png`
- `outputs/runs/phase6-gbc06-bubble-mask-smoke/reports/mimo-bubble-cleanup-evaluation.json`

## Result Summary

- Detection source: `outputs/runs/phase2-gbc06-smoke/detections.jsonl`
- Layout source: `outputs/runs/phase4-gbc06-layout-smoke/layout-results.jsonl`
- Record: `GBC06_01.png#1`
- Group: `框内`
- Translation: `街头演出？`
- Phase 2 selected bbox: `[674, 0, 1049, 342]`
- Baseline method: `bubble_fill`
- New method: `bubble_mask_fill`
- New cleaned crop: `outputs/runs/phase6-gbc06-bubble-mask-smoke/crops/cleaned/GBC06-01-png-1.png`
- New before/after crop: `outputs/runs/phase6-gbc06-bubble-mask-smoke/crops/before_after/GBC06-01-png-1.png`

## Root Cause

The previous cleanup filled the entire Phase 2 selected bbox. On `GBC06_01.png#1`, that bbox includes the speech bubble plus surrounding screentone and character hair. Full-rectangle fill therefore erased valid manga art, not just source text.

The better approach follows the BallonsTranslator inpainting pattern: use the large detection region as crop context, but restrict actual cleanup to a text mask / text candidate area.

## Current Algorithm

`bubble_mask_fill`:

1. Reads Phase 2 `candidate_boxes`.
2. Filters out candidates that are effectively the large selected region.
3. Unions the smaller candidate boxes inside the selected bbox, so multiple vertical text columns are handled together.
4. Builds a dark-pixel mask only inside that union text bbox.
5. Dilates the text mask and fills only masked pixels with the local sampled background color.
6. Saves before, cleaned, and before/after crop artifacts.

This fixes the prior over-fill while still avoiding heavyweight inpainting for flat white speech bubbles.

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

## Limitations

- The mask still depends on Phase 2 candidate boxes. If detection misses a text column, cleanup can miss it too.
- Very light gray source text or highly decorative text may require a better mask builder than the current dark-pixel threshold.
- This method is intended for flat/light bubble interiors. For complex non-bubble backgrounds, use the non-bubble inpaint methods.

## Verification

Fresh targeted verification after the mask-union fix:

```powershell
python -m pytest tests/test_phase6_cleanup.py -q
python -m pytest tests/test_phase6_nonbubble_cleanup.py tests/test_phase6_cleanup.py -q
```

Observed results:

```text
5 passed in 0.18s
14 passed in 1.29s
```

## Notes

- Generated `outputs/` are ignored by Git; this report records reproducible commands and artifact paths.
- No API credential or raw `.env` value is stored in outputs or this report.
