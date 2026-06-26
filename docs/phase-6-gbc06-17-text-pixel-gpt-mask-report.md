# Phase 6 GBC06_17 Text-Pixel GPT Mask Report

## Scope

This run updates the non-bubble `gpt-image-2` replacement path so a detected bbox is treated as a loose container for target text, not as permission to edit every object inside the rectangle.

The editable mask now targets detected original-text pixels inside the bbox. Nearby people, hair, props, panel texture, and background should be preserved by mask construction and prompt wording.

## Code Change Summary

- Added `autolettering.gpt_text_mask.build_text_pixel_gpt_mask()`.
- `phase6_nonbubble_gpt_replace` now writes:
  - `gpt_replace_text_mask/*.png`
  - `gpt_replace_mask/*.png`
  - `mask_strategy`
  - `editable_pixel_count`
- Fallback `phase6_nonbubble` GPT masks now default to `text_pixels`, while legacy `rect` and `text_ink` remain available as explicit options.
- MIMO locator validation no longer hard-rejects a bbox only because it contains extra non-text artwork when the intended text is present.
- Replacement-quality prompts now state that extra non-text context inside a loose bbox is not a wrong-region failure by itself.

## Real Sample Experiment

Record:

- `GBC06_17.png#3`
- Target translation: `新川崎（暂）`
- Detection run: `outputs/runs/phase2-gbc06-17-3-target-fix-v3`

Dry-run mask check:

```powershell
python experiments/phase6_nonbubble_gpt_replace.py --detection-run-dir outputs/runs/phase2-gbc06-17-3-target-fix-v3 --run-id phase6-gbc06-17-3-text-pixel-mask-dryrun-v2 --sample-limit 1 --record-id "GBC06_17.png#3" --bt-method patchmatch --context-padding 16 --rect-mask-expand-px 2 --skip-mimo
```

Key artifact:

- `outputs/runs/phase6-gbc06-17-3-text-pixel-mask-dryrun-v2/visuals/gpt-replace-bt-grid.png`

The mask overlay protects the right-side bright panel edge and marks only the original white lettering pixels.

Real `gpt-image-2` + MIMO evaluation:

```powershell
python experiments/phase6_nonbubble_gpt_replace.py --detection-run-dir outputs/runs/phase2-gbc06-17-3-target-fix-v3 --run-id phase6-gbc06-17-3-text-pixel-mask-gpt-v1 --sample-limit 1 --record-id "GBC06_17.png#3" --bt-method patchmatch --context-padding 16 --rect-mask-expand-px 2 --call-gpt-image
```

Run directory:

- `outputs/runs/phase6-gbc06-17-3-text-pixel-mask-gpt-v1`

Key artifacts:

- Grid: `outputs/runs/phase6-gbc06-17-3-text-pixel-mask-gpt-v1/visuals/gpt-replace-bt-grid.png`
- GPT input: `outputs/runs/phase6-gbc06-17-3-text-pixel-mask-gpt-v1/gpt_replace_input/GBC06-17-png-3.png`
- Text mask: `outputs/runs/phase6-gbc06-17-3-text-pixel-mask-gpt-v1/gpt_replace_text_mask/GBC06-17-png-3.png`
- GPT mask: `outputs/runs/phase6-gbc06-17-3-text-pixel-mask-gpt-v1/gpt_replace_mask/GBC06-17-png-3.png`
- GPT output crop: `outputs/runs/phase6-gbc06-17-3-text-pixel-mask-gpt-v1/gpt_image2_replace_target_crop/GBC06-17-png-3.png`
- MIMO evaluation: `outputs/runs/phase6-gbc06-17-3-text-pixel-mask-gpt-v1/reports/mimo-gpt-replace-evaluation.json`

Manifest highlights:

```json
{
  "record_count": 1,
  "gpt_ok_count": 1,
  "gpt_quality_checked_count": 1,
  "gpt_quality_failed_count": 0
}
```

Mask metadata:

```json
{
  "mask_strategy": "text_pixels_within_bbox",
  "editable_pixel_count": 2748
}
```

MIMO judged `gpt-image-2 cn` acceptable and scored text correctness, original-text removal, layout, style consistency, and background preservation as `10`.

Manual inspection of the grid agrees with the direction of the MIMO result for this sample: the output remains in the target region, does not move to nearby content, and preserves the bright right edge outside the text mask. The visible target text appears to be `新川崎（暂）`.

## Verification

```powershell
python -m pytest tests/test_phase6_nonbubble_gpt_replace.py tests/test_phase6_nonbubble_cleanup.py tests/test_phase6_replacement_quality.py tests/test_phase6_replacement_quality_gate.py tests/test_phase6_segmented_gpt_replace.py -q
```

Result:

```text
91 passed in 43.59s
```

Additional CLI regression:

```powershell
python -m pytest tests/test_experiment_clis.py::test_phase6_nonbubble_cli_can_disable_mimo_locator tests/test_experiment_clis.py::test_phase6_nonbubble_cli_accepts_fallback_gpt_mask_geometry -q
```

## Current Caveat

The text-pixel mask is now the default for GPT direct replacement, but it remains a heuristic. Light-on-dark samples with large bright non-text graphics may still need per-sample mask diagnostics before paid GPT calls. The next useful batch should use small controlled GPT calls plus MIMO review and keep the generated grid near-square.
