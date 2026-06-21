# Phase 7/8 GBC06 Integrated Smoke Report

This report records the first one-command Phase 7/8 smoke run over the current GBC06 sample chain. It runs page preview generation, MIMO preview evaluation, and Photoshop export from the same entry point so the preview/export loop can be reproduced without manually stitching the phases together.

## Command

```powershell
python experiments/phase7_8_integrated_smoke.py --detection-run-dir outputs/runs/phase2-gbc06-smoke --cleanup-run-dir outputs/runs/phase6-gbc06-bubble-mask-smoke --cleanup-run-dir outputs/runs/phase6-gbc06-nonbubble-lama-large-compare --layout-run-dir outputs/runs/phase4-gbc06-nonbubble-layout-smoke --font-selection-run-dir outputs/runs/phase3-gbc06-nonbubble-mimo-font-smoke --run-id phase7-8-gbc06-integrated-lama-smoke --sample-limit 2
```

## Inputs

- Detection run: `outputs/runs/phase2-gbc06-smoke`
- Bubble cleanup run: `outputs/runs/phase6-gbc06-bubble-mask-smoke`
- Non-bubble cleanup run: `outputs/runs/phase6-gbc06-nonbubble-lama-large-compare`
- Layout run: `outputs/runs/phase4-gbc06-nonbubble-layout-smoke`
- Font selection run: `outputs/runs/phase3-gbc06-nonbubble-mimo-font-smoke`
- Sample limit: `2`

The cleanup runs are merged by `record_id`. For this smoke, `GBC06_01.png#1` uses `bubble_mask_fill`, and `GBC06_01.png#16` uses `bt_lama_large_inpaint`.

## Integrated Output

Run directory:

```text
outputs/runs/phase7-8-gbc06-integrated-lama-smoke
```

Generated subruns:

- Phase 7 preview: `outputs/runs/phase7-8-gbc06-integrated-lama-smoke/runs/phase7-preview`
- Phase 7 MIMO evaluation: `outputs/runs/phase7-8-gbc06-integrated-lama-smoke/runs/phase7-evaluation`
- Phase 8 Photoshop export: `outputs/runs/phase7-8-gbc06-integrated-lama-smoke/runs/phase8-export`

Integrated manifest summary:

```json
{
  "preview_page_count": 1,
  "preview_record_count": 2,
  "skipped_count": 0,
  "evaluation_status": "evaluated",
  "evaluation_score": 8,
  "evaluation_usable": true,
  "exported_page_count": 1,
  "exported_text_layer_count": 2,
  "missing_cleanup_layers": 0,
  "effective_cleanup_methods": {
    "bubble_mask_fill": 1,
    "bt_lama_large_inpaint": 1
  }
}
```

## Phase 7 Preview Artifacts

- Final page preview: `outputs/runs/phase7-8-gbc06-integrated-lama-smoke/runs/phase7-preview/pages/GBC06-01-png.png`
- Original page copy: `outputs/runs/phase7-8-gbc06-integrated-lama-smoke/runs/phase7-preview/pages/original/GBC06-01-png.png`
- Cleaned page: `outputs/runs/phase7-8-gbc06-integrated-lama-smoke/runs/phase7-preview/pages/cleaned/GBC06-01-png.png`
- Debug overlay: `outputs/runs/phase7-8-gbc06-integrated-lama-smoke/runs/phase7-preview/debug/page_overlays/GBC06-01-png.png`
- Before/after crops:
  - `outputs/runs/phase7-8-gbc06-integrated-lama-smoke/runs/phase7-preview/crops/before_after/GBC06-01-png-1.png`
  - `outputs/runs/phase7-8-gbc06-integrated-lama-smoke/runs/phase7-preview/crops/before_after/GBC06-01-png-16.png`
- Manual review CSV: `outputs/runs/phase7-8-gbc06-integrated-lama-smoke/runs/phase7-preview/reports/manual-review.csv`

## MIMO Evaluation Change

The initial page-level MIMO evaluation was too coarse for a sparse two-record page edit. MIMO focused on unrelated page content and returned an over-positive score. The evaluator now builds a local before/after contact sheet and submits that image instead of the whole page preview.

Evaluation contact sheet:

```text
outputs/runs/phase7-8-gbc06-integrated-lama-smoke/runs/phase7-preview/debug/evaluation_contact_sheets/GBC06-01-png.png
```

The contact sheet puts the original crop on the left and the generated preview crop on the right for each record. It also draws a red split line between before and after so the model does not need to infer the boundary from layout alone.

Prompt constraints were tightened to ask MIMO to compare generated lettering against the original text area, not just readability. The prompt now explicitly says to lower the score or mark the result unusable if translated lettering is oversized, outside the original text area, or covers nearby art.

## MIMO Result

Request summary:

- Kind: `phase7_preview_evaluation`
- Model: `mimo-v2.5`
- Image count: `1`
- Prompt chars: `873`
- Max completion tokens: `512`
- Thinking: `disabled`
- Prompt tokens: `782`
- Image tokens: `504`
- Completion tokens: `170`

MIMO returned:

```json
{
  "score": 8,
  "usable": true,
  "original_text_removed": true,
  "art_preserved": true,
  "lettering_readable": true,
  "issues": [
    "Record #1: The translated text '街头演出？' is slightly too large and overlaps the original speech bubble's left outline.",
    "Record #16: The vertical translated text is a bit cramped, though still readable."
  ]
}
```

Manual inspection agrees with the direction of this result:

- `GBC06_01.png#1`: cleanup is good, but the current rendered Chinese is too large and slants across the bubble. This is a Phase 4/7 layout tuning problem, not a Phase 6 cleanup failure.
- `GBC06_01.png#16`: LaMa cleanup remains usable. The vertical Chinese is readable, but spacing is tight.

## Phase 8 Export

The integrated run writes:

- `outputs/runs/phase7-8-gbc06-integrated-lama-smoke/runs/phase8-export/photoshop-manifest.json`
- `outputs/runs/phase7-8-gbc06-integrated-lama-smoke/runs/phase8-export/photoshop-import.jsx`
- `outputs/runs/phase7-8-gbc06-integrated-lama-smoke/runs/phase8-export/reports/phase8-report.md`
- `outputs/runs/phase7-8-gbc06-integrated-lama-smoke/runs/phase8-export/reports/photoshop-validation-checklist.md`

Export summary:

- Pages exported: `1`
- Editable text layers exported: `2`
- Missing cleanup layers: `0`
- Cleanup patch methods: `bubble_mask_fill=1`, `bt_lama_large_inpaint=1`

Photoshop itself was not available in this environment, so the JSX remains file-validated but not Photoshop-executed.

## Behavior Added

- Added `autolettering.phase7_8_smoke.run_phase7_8_smoke` as the integrated smoke runner.
- Added `experiments/phase7_8_integrated_smoke.py` as the CLI wrapper.
- Added integrated manifest/report generation under the smoke run directory.
- Strengthened Phase 7 MIMO evaluation:
  - local before/after contact sheet input
  - per-record JSON array response support
  - string `issues` support
  - `evaluation_image_path` traceability
  - larger MIMO response budget: `max_completion_tokens=512`

## Current Decision

Keep the current cleanup defaults:

- Bubble default: `bubble_mask_fill`
- Non-bubble default: `bt_lama_large_inpaint`
- Non-bubble fallback: `bt_patchmatch`
- Do not use `gpt_image2_masked_edit` as the default cleanup path.

The next useful optimization target is layout, especially reducing the `GBC06_01.png#1` translated text size and improving placement inside the speech bubble.

## Tight Text Layout Follow-up

The first integrated smoke made `GBC06_01.png#1` usable from a cleanup perspective, but MIMO and manual review both showed the rendered translation was oversized and crossed the speech bubble boundary. The root cause was that Phase 4 used the full detected cleanup bbox `[674, 0, 1049, 342]` as the layout canvas. That bbox contains the speech bubble, screentone, and character hair, while the actual source text occupies the smaller candidate union `[799, 145, 874, 300]`.

Phase 4 now accepts an optional detection run and uses the tight text candidate union as the layout target when available:

```powershell
python experiments/phase4_layout_search.py --selection-run-dir outputs/runs/phase3-gbc06-nonbubble-mimo-font-smoke --angle-run-dir outputs/runs/phase5-gbc06-nonbubble-angle-smoke --detection-run-dir outputs/runs/phase2-gbc06-smoke --run-id phase4-gbc06-tight-text-layout-smoke --sample-limit 2
```

The first attempt generated a smaller Phase 4 layout, but Phase 7 still resized that small text image back to the full cleanup bbox. That produced large blurry text in the page preview. Phase 7 now separates the cleanup bbox from the text overlay bbox:

- `bbox`: cleanup/patch area.
- `text_bbox`: layout target and overlay placement area.

The corrected integrated command is:

```powershell
python experiments/phase7_8_integrated_smoke.py --detection-run-dir outputs/runs/phase2-gbc06-smoke --cleanup-run-dir outputs/runs/phase6-gbc06-bubble-mask-smoke --cleanup-run-dir outputs/runs/phase6-gbc06-nonbubble-lama-large-compare --layout-run-dir outputs/runs/phase4-gbc06-tight-text-layout-smoke --font-selection-run-dir outputs/runs/phase3-gbc06-nonbubble-mimo-font-smoke --run-id phase7-8-gbc06-tight-layout-smoke --sample-limit 2
```

New output directory:

```text
outputs/runs/phase7-8-gbc06-tight-layout-smoke
```

The Phase 4 row for `GBC06_01.png#1` now records:

```json
{
  "font_size": 30,
  "orientation": "vertical",
  "angle_degrees": 0.0,
  "target_width": 75,
  "target_height": 155,
  "target_bbox": [799, 145, 874, 300],
  "measured_width": 30,
  "measured_height": 155,
  "overflow_ratio": 0.0
}
```

The Phase 7 preview row now preserves both bboxes:

```json
{
  "record_id": "GBC06_01.png#1",
  "bbox": [674, 0, 1049, 342],
  "text_bbox": [799, 145, 874, 300],
  "cleanup_method": "bubble_mask_fill"
}
```

Phase 8 now preserves the same split in `photoshop-manifest.json` and the generated JSX:

- cleanup patch placement uses `bbox`
- editable Photoshop paragraph text uses `text_bbox`
- text layer position uses `text_position`

For `GBC06_01.png#1`, the exported Photoshop layer now contains:

```json
{
  "bbox": {"x": 674, "y": 0, "width": 375, "height": 342, "xyxy": [674, 0, 1049, 342]},
  "text_bbox": {"x": 799, "y": 145, "width": 75, "height": 155, "xyxy": [799, 145, 874, 300]},
  "text_position": {"x_px": 799, "y_px": 145}
}
```

The evaluation contact sheet label was also tightened to avoid model confusion. Earlier labels rendered Chinese translated text with the default bitmap font, producing square placeholder glyphs that MIMO could misread as generated artifacts. Contact sheet labels now use only the record id and cleanup method; the translated text remains in the prompt `Records JSON`.

The parser now rejects a per-record array that merely echoes `Records JSON` without verdict fields. The prompt also explicitly says not to echo the records and requires `score` and `usable` in every returned object.

MIMO result for the corrected tight-layout run after the Phase 8/text-bbox and evaluation-input fixes:

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

Manual inspection of `outputs/runs/phase7-8-gbc06-tight-layout-smoke/runs/phase7-preview/debug/evaluation_contact_sheets/GBC06-01-png.png` confirms the earlier oversized/blurry overlay is gone. `GBC06_01.png#1` is now readable and contained inside the bubble. Remaining layout work is finer placement/style tuning, not cleanup failure.

## Verification

Fresh verification after the integrated runner and MIMO evaluation changes:

```powershell
python -m pytest tests/test_phase7_preview_evaluation.py tests/test_phase7_8_smoke.py -q
python -m pytest tests/test_phase7_preview.py tests/test_phase8_photoshop_export.py -q
python -m pytest -q
git diff --check
```

Observed results:

```text
7 passed in 0.24s
14 passed in 0.55s
81 passed in 3.39s
git diff --check: exit 0
AST length gate (project code): ok
```

Additional verification after the tight text layout and `text_bbox` overlay follow-up:

```powershell
python -m pytest tests/test_phase4_layout.py tests/test_phase7_preview.py -q
python -m pytest tests/test_phase7_preview_evaluation.py tests/test_phase7_8_smoke.py -q
python -m pytest tests/test_phase8_photoshop_export.py -q
python -m pytest -q
git diff --check
```

Observed results:

```text
25 passed in 1.21s
12 passed in 0.25s
87 passed in 3.21s
git diff --check: exit 0
AST length gate (project code): ok
```
