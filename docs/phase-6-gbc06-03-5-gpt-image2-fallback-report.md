# Phase 6 GPT Fallback Experiment: GBC06_03.png#5

Date: 2026-06-26

Target record: `GBC06_03.png#5`

Target translation: `好孩子不要看…`

## User Direction

The fallback locator should not keep chasing a bbox only because it includes a passerby, character, or background. The practical requirement is:

- the edit area must contain the original Japanese text;
- `gpt-image-2` must be prompted to replace only the text content;
- non-text manga art inside the mask is context, not permission to redraw it.

## Code Changes Tested

- Strengthened `gpt_image_edit_prompt()` so wide masks explicitly preserve people, hair, clothing, body, background line art, screentone, panel borders, texture, and motion lines.
- Added exact punctuation constraints for the single ellipsis glyph `…`.
- Added fallback GPT mask geometry controls:
  - `fallback_edit_padding_px`
  - `fallback_mask_expand_px`
  - `fallback_gpt_mask_shape`
- Changed fallback GPT replacement crop composition to paste the GPT result through the transparent edit mask, instead of extracting dark text and filling the whole bbox background. This prevents mask-internal non-text art from being cleared by postprocessing.
- Stopped treating `tight_enough=false` as a hard blocker when MIMO accepts the bbox semantically. A semantically accepted bbox can proceed to GPT even if it contains extra art or blank space.
- Stopped expanding the editable mask merely because `tight_enough=false`. Loose semantic bboxes now keep the locator bbox as the edit mask unless an explicit experiment CLI expansion is requested.
- Kept the special recovery for accepted bboxes that are clearly below the LabelPlus anchor.
- Added a local GPT artifact gate. It compares the cleaned crop and GPT replacement crop and rejects large, nearly solid dark/gray overlays even when MIMO marks the text replacement usable.

## Real Runs

All runs used the same Phase 2 detection source:

`outputs/runs/phase2-gbc06-03-batch-4-6-cta-detection-v3-threshold40-merged`

### v10: preserve-nontext prompt, wide edit padding

Command:

```powershell
python experiments/phase6_nonbubble_cleanup.py --detection-run-dir outputs/runs/phase2-gbc06-03-batch-4-6-cta-detection-v3-threshold40-merged --output-root outputs/runs --run-id phase6-gbc06-03-5-fallback-gpt-image2-v10-preserve-nontext-prompt --sample-limit 1 --record-id "GBC06_03.png#5" --call-gpt-image --fallback-edit-padding-px 80 --fallback-mask-expand-px 8
```

Artifacts:

- Replacement grid: `outputs/runs/phase6-gbc06-03-5-fallback-gpt-image2-v10-preserve-nontext-prompt/visuals/fallback-replacement-grid.png`
- Quality sheet: `outputs/runs/phase6-gbc06-03-5-fallback-gpt-image2-v10-quality/debug/replacement_quality_sheets/GBC06-03-png-5.png`
- Quality JSONL: `outputs/runs/phase6-gbc06-03-5-fallback-gpt-image2-v10-quality/replacement-quality.jsonl`

Result:

- MIMO replacement quality returned a schema-invalid answer: all score fields were `null`.
- Manual review: better than earlier v4/v8 because it no longer destroys a large character/background region, but it still exposed a pipeline issue. The GPT normalized output contained readable Chinese, while the final target crop did not, because the old postprocess/target crop path was not aligned with the edit mask.

Conclusion: not accepted, but useful for finding the mask-composition bug.

### v11: mask-compose fix, tight edit padding

Command:

```powershell
python experiments/phase6_nonbubble_cleanup.py --detection-run-dir outputs/runs/phase2-gbc06-03-batch-4-6-cta-detection-v3-threshold40-merged --output-root outputs/runs --run-id phase6-gbc06-03-5-fallback-gpt-image2-v11-wide-target-preserve-mask-compose --sample-limit 1 --record-id "GBC06_03.png#5" --call-gpt-image --fallback-edit-padding-px 16 --fallback-mask-expand-px 0 --fallback-gpt-mask-shape rect
```

Artifacts:

- Replacement grid: `outputs/runs/phase6-gbc06-03-5-fallback-gpt-image2-v11-wide-target-preserve-mask-compose/visuals/fallback-replacement-grid.png`
- Final replacement crop: `outputs/runs/phase6-gbc06-03-5-fallback-gpt-image2-v11-wide-target-preserve-mask-compose/fallback_replacement_crop/GBC06-03-png-5.png`
- Quality sheet: `outputs/runs/phase6-gbc06-03-5-fallback-gpt-image2-v11-quality/debug/replacement_quality_sheets/GBC06-03-png-5.png`
- Quality JSONL: `outputs/runs/phase6-gbc06-03-5-fallback-gpt-image2-v11-quality/replacement-quality.jsonl`

MIMO result:

```json
{
  "score": 8,
  "usable": true,
  "exact_text_correct": false,
  "observed_text": "好孩子不要看...",
  "region_correct": true,
  "style_consistent": true,
  "outside_mask_preserved": true
}
```

Manual review:

- Region is correct.
- Original Japanese is removed in the target column.
- Character/background are preserved well enough for this small sample.
- Main defect: the requested `…` became `...`.

Conclusion: best current candidate. It is usable as a visual fallback prototype, but exact punctuation is not fully solved.

### v12: add explicit ellipsis glyph constraint

Command:

```powershell
python experiments/phase6_nonbubble_cleanup.py --detection-run-dir outputs/runs/phase2-gbc06-03-batch-4-6-cta-detection-v3-threshold40-merged --output-root outputs/runs --run-id phase6-gbc06-03-5-fallback-gpt-image2-v12-ellipsis-glyph --sample-limit 1 --record-id "GBC06_03.png#5" --call-gpt-image --fallback-edit-padding-px 16 --fallback-mask-expand-px 0 --fallback-gpt-mask-shape rect
```

Artifacts:

- Replacement grid: `outputs/runs/phase6-gbc06-03-5-fallback-gpt-image2-v12-ellipsis-glyph/visuals/fallback-replacement-grid.png`
- Quality sheet: `outputs/runs/phase6-gbc06-03-5-fallback-gpt-image2-v12-quality/debug/replacement_quality_sheets/GBC06-03-png-5.png`
- Quality JSONL: `outputs/runs/phase6-gbc06-03-5-fallback-gpt-image2-v12-quality/replacement-quality.jsonl`

MIMO result:

```json
{
  "score": 10,
  "usable": true,
  "exact_text_correct": true,
  "observed_text": "好孩子不要看…",
  "outside_mask_preserved": true
}
```

Manual review:

- MIMO is a false positive.
- The final visual contains an obvious dark vertical artifact block.
- This is worse than v11 despite the exact ellipsis being reported as correct.
- Local artifact gate rejects this run with `local_artifact_large_flat_overlay`.

Conclusion: rejected. Keep as evidence that exact-text MIMO score cannot override manual visual inspection.

### v13: semantic-accepted loose bbox proceeds directly

Command:

```powershell
python experiments/phase6_nonbubble_cleanup.py --detection-run-dir outputs/runs/phase2-gbc06-03-batch-4-6-cta-detection-v3-threshold40-merged --output-root outputs/runs --run-id phase6-gbc06-03-5-fallback-gpt-image2-v13-semantic-loose-direct --sample-limit 1 --record-id "GBC06_03.png#5" --call-gpt-image --fallback-edit-padding-px 16 --fallback-mask-expand-px 0 --fallback-gpt-mask-shape rect
```

Artifacts:

- Replacement grid: `outputs/runs/phase6-gbc06-03-5-fallback-gpt-image2-v13-semantic-loose-direct/visuals/fallback-replacement-grid.png`
- Quality sheet: `outputs/runs/phase6-gbc06-03-5-fallback-gpt-image2-v13-quality/debug/replacement_quality_sheets/GBC06-03-png-5.png`
- Quality JSONL: `outputs/runs/phase6-gbc06-03-5-fallback-gpt-image2-v13-quality/replacement-quality.jsonl`

MIMO result:

```json
{
  "score": 0,
  "usable": false,
  "exact_text_correct": false,
  "observed_text": "好孩子不要看...",
  "region_correct": false,
  "outside_mask_preserved": false
}
```

Manual review:

- The wide mask produced a large dark rectangle over the character/background.
- The replacement text appears in the wrong visible area.
- Local artifact gate rejects this run with `local_artifact_large_flat_overlay`.

Conclusion: rejected. This confirms that "wide bbox is acceptable" does not mean "any large editable region is safe"; the mask can include non-text context, but it still needs a reasonable edit area.

## Local Artifact Gate

Command:

```powershell
python experiments\phase6_gpt_artifact_gate.py --run-id phase6-gbc06-03-5-gpt-artifact-gate-v1 --run-dir outputs\runs\phase6-gbc06-03-5-fallback-gpt-image2-v11-wide-target-preserve-mask-compose --run-dir outputs\runs\phase6-gbc06-03-5-fallback-gpt-image2-v12-ellipsis-glyph --run-dir outputs\runs\phase6-gbc06-03-5-fallback-gpt-image2-v13-semantic-loose-direct
```

Artifacts:

- Result JSON: `outputs/runs/phase6-gbc06-03-5-gpt-artifact-gate-v1/gpt-artifact-gate-results.json`
- Evidence grid: `outputs/runs/phase6-gbc06-03-5-gpt-artifact-gate-v1/visuals/gpt-artifact-gate-grid.png`

Result:

| Run | Gate | Largest darken component area ratio | Notes |
| --- | --- | ---: | --- |
| v11 | pass | `0.0035` | Sparse text/line-art changes, no solid overlay. |
| v12 | fail | `0.0568` | Nearly solid vertical dark block; MIMO false positive. |
| v13 | fail | `0.0999` | Large dark/gray rectangle over character/background. |

The gate does not reject wide locator context by itself. It only rejects replacement crops that contain a large continuous darkened overlay compared with the cleaned crop.

## Current Recommendation

Use v11 as the current best GPT-image-2 fallback candidate for `GBC06_03.png#5`:

- `fallback_edit_padding_px=16`
- `fallback_mask_expand_px=0`
- `fallback_gpt_mask_shape=rect`
- prompt must explicitly preserve all non-text manga art
- final replacement composition must use the transparent edit mask, not black-text extraction plus bbox fill

Do not trust MIMO alone for this route. It gave a false positive on v12 and a schema-invalid response on v10. The acceptance rule should be:

1. MIMO replacement quality is useful as a first-pass signal.
2. The local artifact gate must pass before Phase 7/8 can consume the GPT replacement crop.
3. Manual review remains required for gpt-image-2 fallback outputs.
4. A result with obvious gray/dark blocks or character/background damage is rejected even if MIMO scores it high.

## Open Issues

- Exact punctuation for `…` remains unstable. v11 is visually better but uses `...`; v12 satisfies MIMO text exactness but has unacceptable artifacting.
- `gpt-image-2` can still interpret a large transparent rectangle as permission to repaint the whole area despite prompt constraints.
- The local artifact gate catches the v12/v13 gray-block failures, but it is intentionally narrow. It does not replace manual review for typography, exact punctuation, or subtle style mismatch.

## Verification

Targeted tests run during this experiment:

```powershell
python -m pytest tests/test_phase6_nonbubble_cleanup.py::test_gpt_image_prompt_requires_exact_target_text tests/test_phase6_nonbubble_cleanup.py::test_gpt_image_prompt_rejects_known_simplified_traditional_glyph_substitutions tests/test_phase6_nonbubble_cleanup.py::test_gpt_image_prompt_spells_out_repeated_sound_effect_characters tests/test_phase6_nonbubble_cleanup.py::test_gpt_image_prompt_preserves_non_text_art_inside_wide_mask -q
```

Result: `4 passed`.

```powershell
python -m pytest tests/test_phase6_nonbubble_cleanup.py::test_refine_fallback_locator_bbox_keeps_wide_bbox_when_trim_would_drop_target_column tests/test_phase6_nonbubble_cleanup.py::test_write_fallback_replacement_crop_uses_edit_mask_without_clearing_non_text_art tests/test_phase6_nonbubble_cleanup.py::test_refine_fallback_locator_bbox_trims_dark_vertical_text_column -q
```

Result: `3 passed`.

Additional verification after adding the local artifact gate:

```powershell
python -m pytest tests/test_phase6_replacement_quality_gate.py tests/test_phase6_replacement_quality.py::test_run_phase6_replacement_quality_records_local_artifact_rejection tests/test_phase6_replacement_quality.py::test_run_phase6_replacement_quality_writes_results_and_review_sheet tests/test_phase6_nonbubble_cleanup.py::test_semantically_accepted_loose_fallback_bbox_does_not_expand_editable_mask tests/test_experiment_clis.py::test_phase6_gpt_artifact_gate_experiment_writes_near_square_grid -q
```

Result: `6 passed`.

```powershell
python -m pytest tests/test_phase6_nonbubble_cleanup.py::test_run_phase6_nonbubble_cleanup_fallback_keeps_semantically_accepted_loose_bbox tests/test_phase6_nonbubble_cleanup.py::test_run_phase6_nonbubble_cleanup_fallback_calls_gpt_when_accepted_bbox_stays_loose tests/test_phase6_nonbubble_cleanup.py::test_run_phase6_nonbubble_cleanup_recovers_accepted_tight_bbox_that_is_below_anchor -q
```

Result: `3 passed`.
