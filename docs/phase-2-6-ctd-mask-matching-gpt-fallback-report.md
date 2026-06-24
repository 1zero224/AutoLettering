# Phase 2/6 CTD Mask Matching And GPT Fallback Report

## Summary

This slice rewrites the non-bubble text detection path around BallonsTranslator CTD masks.

- BallonsTranslator module name is `ctd`; the user-facing "cta" route maps to ComicTextDetector.
- Phase 2 now supports `--detection-strategy ctd_mask`.
- CTD runs once per page, writes the refined full-page mask, splits it into connected components, and matches LabelPlus points by edge distance.
- A matched CTD component is expanded down the same narrow vertical column before matching is finalized. This fixes the `GBC06_01.png#16` case where the title was split into `桃香から` plus lower continuation components.
- Phase 6 matched CTD records force `lama_large_512px` and use the CTD merged full-page mask.
- Phase 6 fallback records call MIMO to locate the target bbox in the crop and only call `gpt-image-2` if MIMO returns an in-bounds crop-local bbox.
- Phase 7 now supports GPT-direct replacement records without requiring a layout row or overlaying a second text layer.
- Phase 8 can use a page-level repaired image layer from Phase 7.

## Real Experiments

### CTD Matched Path: `GBC06_01.png#16`

Command:

```powershell
python experiments/phase2_detect_text_regions.py --labelplus-file "GBC06 (已翻 斗笠)/翻译_0.txt" --output-root outputs/runs --run-id phase2-gbc06-ctd-mask-01-16-v3-merged --sample-limit 1 --record-id "GBC06_01.png#16" --detection-strategy ctd_mask --ctd-max-edge-distance-px 16
```

Result:

- Status: `ok`
- Matched component id: `component-0001+component-0012+component-0016+component-0018+component-0026`
- Final bbox: `[1349, 122, 1407, 684]`
- Source text coverage: full `桃香からの突然の提案`

Key artifacts:

- `outputs/runs/phase2-gbc06-ctd-mask-01-16-v3-merged/detections.jsonl`
- `outputs/runs/phase2-gbc06-ctd-mask-01-16-v3-merged/debug/detection/GBC06_01-16.png`
- `outputs/runs/phase2-gbc06-ctd-mask-01-16-v3-merged/debug/ctd_masks/GBC06_01/ctd-refined-mask.png`
- `outputs/runs/phase2-gbc06-ctd-mask-01-16-v3-merged/debug/ctd_masks/GBC06_01/components/component-0001+component-0012+component-0016+component-0018+component-0026.png`

Phase 6 command:

```powershell
python experiments/phase6_nonbubble_cleanup.py --detection-run-dir outputs/runs/phase2-gbc06-ctd-mask-01-16-v3-merged --output-root outputs/runs --run-id phase6-gbc06-ctd-lama-01-16-v4-merged --sample-limit 1 --record-id "GBC06_01.png#16" --skip-mimo
```

Result:

- Method: `bt_lama_large_inpaint`
- Bbox: `[1349, 122, 1407, 684]`
- GPT calls: `0`
- MIMO evaluation: `pass`

Key artifacts:

- `outputs/runs/phase6-gbc06-ctd-lama-01-16-v4-merged/crops/input/GBC06-01-png-16.png`
- `outputs/runs/phase6-gbc06-ctd-lama-01-16-v4-merged/crops/mask/GBC06-01-png-16.png`
- `outputs/runs/phase6-gbc06-ctd-lama-01-16-v4-merged/crops/cleaned/GBC06-01-png-16.png`
- `outputs/runs/phase6-gbc06-ctd-lama-01-16-v4-merged/visuals/ctd-merged-lama-readable-grid.png`
- `outputs/runs/phase6-gbc06-ctd-lama-01-16-v4-merged/reports/mimo-ctd-lama-evaluation.json`

MIMO returned:

```json
{
  "full_text_covered": true,
  "mask_quality": "good",
  "inpaint_quality": "good",
  "visible_ghosting": "minimal",
  "usable_for_lettering": true,
  "issues": [],
  "recommendation": "pass"
}
```

### Final Preview/PSD Smoke: `GBC06_01.png#16`

The first final smoke used the no-rotation top-aligned Song layout at `font_size=42`. MIMO accepted it as usable but reported that the lettering was slightly oversized and cramped.

Optimization experiment:

- Run directory: `outputs/runs/phase4-gbc06-01-16-layout-size-variants-ctd-lama-v1`
- Grid: `outputs/runs/phase4-gbc06-01-16-layout-size-variants-ctd-lama-v1/visuals/layout-size-variant-grid.png`
- Candidates: `font_size=42`, `40`, `38`, `36`
- MIMO best variant: `song_fs40_top_noangle`
- MIMO rationale: `font_size=40` is the best balance; `42` is slightly cramped, `38/36` are acceptable but less impactful.

Final optimized preview:

```powershell
python experiments/phase7_page_preview.py --detection-run-dir outputs/runs/phase2-gbc06-ctd-mask-01-16-v3-merged --cleanup-run-dir outputs/runs/phase6-gbc06-ctd-lama-01-16-v4-merged --layout-run-dir outputs/runs/phase4-gbc06-01-16-layout-song-fs40-top-noangle-v10 --output-root outputs/runs --run-id phase7-gbc06-ctd-lama-01-16-fs40-noangle-top-v2 --sample-limit 1
```

Key artifacts:

- `outputs/runs/phase7-gbc06-ctd-lama-01-16-fs40-noangle-top-v2/pages/GBC06-01-png.png`
- `outputs/runs/phase7-gbc06-ctd-lama-01-16-fs40-noangle-top-v2/pages/cleaned/GBC06-01-png.png`
- `outputs/runs/phase7-gbc06-ctd-lama-01-16-fs40-noangle-top-v2/crops/before_after/GBC06-01-png-16.png`
- `outputs/runs/phase7-gbc06-ctd-lama-01-16-fs40-noangle-top-v2/debug/evaluation_contact_sheets/GBC06-01-png.png`

MIMO preview evaluation:

- Run directory: `outputs/runs/phase7-eval-gbc06-ctd-lama-01-16-fs40-noangle-top-v1`
- Score: `9`
- Usable: `true`
- Original text removed: `true`
- Art preserved: `true`
- Lettering readable: `true`
- Issue: minor softness/inpainting artifacts around some strokes.

The Phase 7 evaluation contact sheet now splits tall vertical before/after crops into ordered segments and arranges them in a near-square grid. For this sample the sheet is `790x1104` instead of a very tall strip, and the prompt explicitly tells MIMO that segments are consecutive slices, not duplicated lettering.

Final Photoshop export:

```powershell
python experiments/phase8_photoshop_export.py --detection-run-dir outputs/runs/phase2-gbc06-ctd-mask-01-16-v3-merged --font-selection-run-dir outputs/runs/phase3-gbc06-01-16-manual-song-selection-v1 --layout-run-dir outputs/runs/phase4-gbc06-01-16-layout-song-fs40-top-noangle-v10 --cleanup-run-dir outputs/runs/phase6-gbc06-ctd-lama-01-16-v4-merged --preview-run-dir outputs/runs/phase7-gbc06-ctd-lama-01-16-fs40-noangle-top-v2 --output-root outputs/runs --run-id phase8-gbc06-ctd-lama-01-16-fs40-psd-structure-v3 --sample-limit 1
```

Key artifacts:

- `outputs/runs/phase8-gbc06-ctd-lama-01-16-fs40-psd-structure-v3/photoshop-manifest.json`
- `outputs/runs/phase8-gbc06-ctd-lama-01-16-fs40-psd-structure-v3/photoshop-import.jsx`
- `outputs/runs/phase8-gbc06-ctd-lama-01-16-fs40-psd-structure-v3/reports/phase8-report.md`

The manifest page has:

- `layer_order`: `["text_layers", "repaired_image", "original_image"]`
- `repaired_image_path`: `outputs/runs/phase7-gbc06-ctd-lama-01-16-fs40-noangle-top-v2/pages/cleaned/GBC06-01-png.png`
- Text layer name: `嵌字图层 GBC06_01.png#16`
- Layout: vertical, top-aligned, `angle_degrees=0.0`, `font_size=40`

The JSX imports `repaired_image_path` as a page-level bitmap layer named `修复图像`. If that page-level repaired image exists, it skips per-record cleanup patch layers and then creates editable text layers above it.

### GPT Fallback Path

Candidate detection command:

```powershell
python experiments/phase2_detect_text_regions.py --labelplus-file "GBC06 (已翻 斗笠)/翻译_0.txt" --output-root outputs/runs --run-id phase2-gbc06-ctd-mask-fallback-candidates-v1 --sample-limit 5 --record-id "GBC06_17.png#3" --record-id "GBC06_16.png#5" --record-id "GBC06_18.png#2" --record-id "GBC06_21.png#6" --record-id "GBC06_02.png#14" --detection-strategy ctd_mask --ctd-max-edge-distance-px 16
```

MIMO-only locator command:

```powershell
python experiments/phase6_nonbubble_cleanup.py --detection-run-dir outputs/runs/phase2-gbc06-ctd-mask-fallback-candidates-v1 --output-root outputs/runs --run-id phase6-gbc06-ctd-fallback-mimo-locator-candidates-v1 --sample-limit 5
```

Only `GBC06_16.png#5` produced a valid in-bounds MIMO bbox in that batch:

- Local bbox: `[170, 115, 280, 220]`
- Global bbox: `[399, 162, 509, 267]`

Controlled GPT command:

```powershell
python experiments/phase6_nonbubble_cleanup.py --detection-run-dir outputs/runs/phase2-gbc06-ctd-mask-fallback-candidates-v1 --output-root outputs/runs --run-id phase6-gbc06-ctd-fallback-gpt-16-5-v2-tight-edit --sample-limit 1 --record-id "GBC06_16.png#5" --call-gpt-image
```

Result:

- GPT call status: `ok`
- Tight edit crop was used.
- GPT raw output wrote a large `哼`, but the output had a gray/dark rectangle artifact.
- Postprocessing reduced only part of the damage; the result remains not usable.

Key artifacts:

- `outputs/runs/phase6-gbc06-ctd-fallback-gpt-16-5-v2-tight-edit/fallback_input/GBC06-16-png-5.png`
- `outputs/runs/phase6-gbc06-ctd-fallback-gpt-16-5-v2-tight-edit/fallback_edit_input/GBC06-16-png-5.png`
- `outputs/runs/phase6-gbc06-ctd-fallback-gpt-16-5-v2-tight-edit/fallback_edit_gpt_mask/GBC06-16-png-5.png`
- `outputs/runs/phase6-gbc06-ctd-fallback-gpt-16-5-v2-tight-edit/gpt_image2/GBC06-16-png-5.png`
- `outputs/runs/phase6-gbc06-ctd-fallback-gpt-16-5-v2-tight-edit/fallback_edit_replacement_crop/GBC06-16-png-5.png`
- `outputs/runs/phase6-gbc06-ctd-fallback-gpt-16-5-v2-tight-edit/visuals/gpt-fallback-tight-edit-readable-grid-v3-threshold36.png`
- `outputs/runs/phase6-gbc06-ctd-fallback-gpt-16-5-v2-tight-edit/reports/mimo-gpt-fallback-evaluation.json`

MIMO evaluation:

```json
{
  "target_text_correct": false,
  "original_removed": false,
  "no_gray_box": false,
  "artwork_preserved": false,
  "usable": false,
  "recommendation": "This is a failed replacement. Do not use."
}
```

## Implementation Notes

- CTD matching keeps one-to-one uniqueness at the seed component level and now claims all merged vertical-continuation components.
- The vertical merge rule is deliberately narrow: high horizontal overlap, similar width, small vertical gap, and only downward from the seed. It excludes wide logo/art components.
- `fallback_required` rows are now carried into Phase 6, but GPT is only called when MIMO locator status is `ok`.
- MIMO bbox parsing accepts either one JSON object or a one-item JSON array.
- MIMO bbox validation rejects out-of-bounds coordinates instead of falling back to an unsafe whole-crop mask.
- GPT fallback uses a tight edit crop around the MIMO bbox rather than the entire LabelPlus search crop.
- GPT replacement crop composition keeps bbox outside the edit crop untouched; inside the masked bbox it attempts to preserve manga tone and paste only confident dark text strokes.

## Current Recommendation

Use the CTD matched path with `lama_large_512px` for non-bubble text when CTD detects the original text. This is the currently usable route.

Do not enable the GPT fallback route as an automatic production path yet. The current blockers are:

- MIMO bbox coordinates are unstable on some crops and often return coordinates outside the crop dimensions.
- `gpt-image-2` may render the target text but introduce gray/dark rectangular artifacts.
- Postprocessing can reduce blast radius but cannot reliably recover clean manga background from a bad GPT output.

Next experiments should focus on fallback locator stability:

- Add a coordinate-ruler or numbered-grid locator image for MIMO, while keeping the GPT edit input clean.
- Ask MIMO for percentage coordinates and convert to pixels as a fallback.
- Run GPT on a mask shaped from detected original glyph pixels rather than a broad rectangle.
- Reject GPT outputs with gray-box artifacts before Phase 7/8 consumption.

## Verification

```powershell
python -m pytest tests/test_ctd_mask_matching.py tests/test_phase2_ctd_strategy.py tests/test_phase2_detection.py tests/test_phase6_nonbubble_cleanup.py tests/test_phase6_nonbubble_gpt_replace.py tests/test_phase7_preview.py tests/test_phase7_preview_evaluation.py tests/test_phase8_photoshop_export.py tests/test_phase8_photoshop_export_alignment.py tests/test_experiment_clis.py -q
```

Result: `86 passed`.

Full regression:

```powershell
python -m pytest -q
```

Result: `233 passed`.
