# Phase 2/6 CTA/CTD Mask Matching And GPT Fallback Report

## Summary

This slice rewrites the non-bubble text detection path around BallonsTranslator ComicTextDetector masks.

- BallonsTranslator module name is `ctd`; the user-facing "cta" route maps to ComicTextDetector.
- Phase 2 now defaults to `--detection-strategy cta_mask`; `ctd_mask` remains a compatibility alias.
- CTD runs once per page, writes the refined full-page mask, splits it into connected components, and matches LabelPlus points by edge distance.
- A matched CTD component is expanded down the same narrow vertical column before matching is finalized. This fixes the `GBC06_01.png#16` case where the title was split into `桃香から` plus lower continuation components.
- Phase 6 matched CTA/CTD records force `lama_large_512px` and use the matched merged full-page component mask.
- Phase 6 fallback records call MIMO to locate the target bbox in the larger LabelPlus context crop and only call `gpt-image-2` after MIMO returns an in-bounds, semantically accepted crop-local bbox.
- The GPT fallback edit input is then tightened to the accepted target bbox plus local padding; the transparent mask is drawn inside that smaller edit crop, and the result is composed back into the full context crop for Phase 7/8 consumption.
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

Updated Phase 8 export contract smoke:

```powershell
python experiments/phase8_photoshop_export.py --detection-run-dir outputs/runs/phase2-gbc06-ctd-mask-01-16-v3-merged --font-selection-run-dir outputs/runs/phase3-gbc06-01-16-manual-song-selection-v1 --layout-run-dir outputs/runs/phase4-gbc06-01-16-layout-song-fs40-top-noangle-v10 --cleanup-run-dir outputs/runs/phase6-gbc06-ctd-lama-01-16-v4-merged --preview-run-dir outputs/runs/phase7-gbc06-ctd-lama-01-16-fs40-noangle-top-v2 --output-root outputs/runs --run-id phase8-gbc06-ctd-lama-01-16-fs40-psd-structure-v4 --sample-limit 1
```

Key artifacts:

- `outputs/runs/phase8-gbc06-ctd-lama-01-16-fs40-psd-structure-v4/photoshop-manifest.json`
- `outputs/runs/phase8-gbc06-ctd-lama-01-16-fs40-psd-structure-v4/photoshop-import.jsx`

The updated manifest/JSX contract now matches the requested PSD stack:

- Editable text layer names are sequential per page; this smoke exports `嵌字图层1` for `GBC06_01.png#16` while preserving `record_id` separately for traceability.
- `layer_order` remains `["text_layers", "repaired_image", "original_image"]`.
- `repaired_image_path` is the Phase 7 full-page cleaned image: `outputs\runs\phase7-gbc06-ctd-lama-01-16-fs40-noangle-top-v2\pages\cleaned\GBC06-01-png.png`.
- `photoshop-import.jsx` still names the full-page repaired bitmap layer `修复图像` and now best-effort renames the original base layer to `原图`.
- Phase 8 accepts `fallback_required` detection rows; if CTD has no selected bbox but cleanup/layout has a bbox, export can still build the corresponding record or repaired-page-only PSD entry.

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

## 2026-06-25 Update: CTA Default, Tight GPT Fallback, And Readable Grids

### CTA Default Detection Contract

`cta_mask` is now the default Phase 2 detection strategy:

```powershell
python experiments/phase2_detect_text_regions.py --labelplus-file "GBC06 (已翻 斗笠)\翻译_0.txt" --output-root outputs/runs --run-id phase2-gbc06-cta-mask-01-16-default-v2 --sample-limit 1 --record-id "GBC06_01.png#16"
```

Result:

- Status: `ok`
- Detection method: `cta_mask`
- Matched component id: `component-0001+component-0012+component-0016+component-0018+component-0026`
- Final bbox: `[1349, 122, 1407, 684]`
- Mask-edge distance: `18.788`
- `cta_match` and compatibility `ctd_match` are both written.
- `selected_text_full_xyxy` and `selected_text_body_xyxy` are both forced to the matched mask bbox.
- Source coverage: full `桃香からの突然の提案`, not only `桃香から`.

The BallonsTranslator config snapshot for this run is:

```json
{
  "device": "cpu",
  "detect_size": 1280,
  "det_rearrange_max_batches": 4,
  "mask dilate size": 2,
  "font size multiplier": 1.0,
  "font size max": -1,
  "font size min": -1
}
```

BallonsTranslator source review note: the user-facing CTA name maps to `ballontranslator.modules.textdetector.detector_ctd.ComicTextDetector`. Under the CPU/ONNX backend, BallonsTranslator's CTD model path still appears to force the internal detector size to `1024`, so `detect_size=1280` is recorded as the running config but may not fully control CPU inference scale.

### Matched Path: CTA Mask + `lama_large_512px`

Command:

```powershell
python experiments/phase6_nonbubble_cleanup.py --detection-run-dir outputs/runs/phase2-gbc06-cta-mask-01-16-default-v2 --output-root outputs/runs --run-id phase6-gbc06-cta-lama-01-16-default-v2 --sample-limit 1 --record-id "GBC06_01.png#16" --skip-mimo
```

Result:

- Status: `cleaned`
- Cleanup method: `bt_lama_large_inpaint`
- Bbox: `[1349, 122, 1407, 684]`
- GPT image status: `not_applicable`
- GPT calls: `0`

Integrated Phase 7/8 command:

```powershell
python experiments/phase7_8_integrated_smoke.py --detection-run-dir outputs/runs/phase2-gbc06-cta-mask-01-16-default-v2 --cleanup-run-dir outputs/runs/phase6-gbc06-cta-lama-01-16-default-v2 --layout-run-dir outputs/runs/phase4-gbc06-01-16-layout-song-fs40-top-noangle-v10 --font-selection-run-dir outputs/runs/phase3-gbc06-01-16-manual-song-selection-v1 --output-root outputs/runs --run-id phase7-8-gbc06-cta-lama-01-16-default-v2 --sample-limit 1
```

MIMO preview evaluation:

- Run: `outputs/runs/phase7-8-gbc06-cta-lama-01-16-default-v2/runs/phase7-evaluation`
- Score: `9`
- Usable: `true`
- Original text removed: `true`
- Art preserved: `true`
- Lettering readable: `true`
- Issue: slight spacing irregularity.

Phase 8 manifest evidence:

- Manifest: `outputs/runs/phase7-8-gbc06-cta-lama-01-16-default-v2/runs/phase8-export/photoshop-manifest.json`
- `layer_order`: `["text_layers", "repaired_image", "original_image"]`
- Page-level `repaired_image_path`: `outputs\runs\phase7-8-gbc06-cta-lama-01-16-default-v2\runs\phase7-preview\pages\cleaned\GBC06-01-png.png`
- Text layer: `嵌字图层1`
- Layout: vertical, `vertical_align=top`, `angle_degrees=0.0`, `font_size=40`.

### Fallback Path: MIMO Locator + Tight `gpt-image-2` Masked Edit

Detection command:

```powershell
python experiments/phase2_detect_text_regions.py --labelplus-file "GBC06 (已翻 斗笠)\翻译_0.txt" --output-root outputs/runs --run-id phase2-gbc06-cta-mask-fallback-16-5-v2 --sample-limit 1 --record-id "GBC06_16.png#5"
```

Result:

- Status: `fallback_required`
- Detection method: `cta_mask`
- Failure reason: `no_ctd_mask_within_threshold`
- Fallback context bbox: `[229, 47, 669, 407]`
- Translation: `哼`

Controlled real GPT command:

```powershell
python experiments/phase6_nonbubble_cleanup.py --detection-run-dir outputs/runs/phase2-gbc06-cta-mask-fallback-16-5-v2 --output-root outputs/runs --run-id phase6-gbc06-cta-fallback-gpt-16-5-tight-v2 --sample-limit 1 --record-id "GBC06_16.png#5" --call-gpt-image
```

Result:

- MIMO locator status: `ok`
- MIMO local bbox: `[158, 104, 230, 220]`
- MIMO global bbox: `[387, 151, 459, 267]`
- MIMO validation: `accepted`
- GPT call status: `ok`
- GPT edit input: `fallback_edit_input/GBC06-16-png-5.png`
- GPT edit mask: `fallback_edit_gpt_mask/GBC06-16-png-5.png`
- Edit crop size: `104x148`
- Full fallback context size: `440x360`
- Replacement crop composed for Phase 7: `fallback_replacement_crop/GBC06-16-png-5.png`

The mask convention matches the OpenAI/gpt-image-playground editing route: the mask has the same dimensions as the edit input, the target region is transparent, and the preserved region is opaque. The local `gpt-image-playground/src/app/api/images/route.ts` reference also passes `mask` into `openai.images.edit(...)` for edit mode.

Phase 7 preview command:

```powershell
python experiments/phase7_page_preview.py --detection-run-dir outputs/runs/phase2-gbc06-cta-mask-fallback-16-5-v2 --cleanup-run-dir outputs/runs/phase6-gbc06-cta-fallback-gpt-16-5-tight-v2 --layout-run-dir outputs/runs/phase4-gbc06-01-16-layout-song-fs40-top-noangle-v10 --output-root outputs/runs --run-id phase7-gbc06-cta-fallback-gpt-16-5-tight-v2 --sample-limit 1
```

Phase 7 record evidence:

- Cleanup method: `gpt_image2_masked_edit`
- Text overlay required: `false`
- Cleanup crop path: `outputs\runs\phase6-gbc06-cta-fallback-gpt-16-5-tight-v2\fallback_replacement_crop\GBC06-16-png-5.png`

MIMO evaluation command:

```powershell
python experiments/phase7_preview_evaluate.py --preview-run-dir outputs/runs/phase7-gbc06-cta-fallback-gpt-16-5-tight-v2 --output-root outputs/runs --run-id phase7-eval-gbc06-cta-fallback-gpt-16-5-tight-v2 --sample-limit 1
```

MIMO result:

- Score: `9`
- Usable: `true`
- Original text removed: `true`
- Art preserved: `true`
- Lettering readable: `true`
- Issues: `[]`
- Summary: the Chinese character `哼` is placed accurately and the surrounding artwork is preserved.

Readable grid sizes:

- Fallback locator grid: `350x374`
- Fallback Phase 7 evaluation contact sheet: `790x584`

### Font Comparison Grid Readability

The Phase 3 font comparison grid is no longer rendered as one long horizontal strip. It uses near-square columns and contained tiles:

```powershell
python experiments/phase3_font_comparison.py --labelplus-file "GBC06 (已翻 斗笠)\翻译_0.txt" --detection-run-dir outputs/runs/phase2-gbc06-cta-mask-01-16-default-v2 --font-dir "工具箱漫画字体V2.5" --output-root outputs/runs --run-id phase3-gbc06-cta-01-16-font-grid-v2 --sample-limit 1 --font-limit 12 --record-id "GBC06_01.png#16"
```

Resulting comparison image:

- Path: `outputs\runs\phase3-gbc06-cta-01-16-font-grid-v2\debug\font_comparison\GBC06-01-png-16.png`
- Size: `950x1198`

## Implementation Notes

- CTD matching keeps one-to-one uniqueness at the seed component level and now claims all merged vertical-continuation components.
- The vertical merge rule is deliberately narrow: high horizontal overlap, similar width, small vertical gap, and only downward from the seed. It excludes wide logo/art components.
- `fallback_required` rows are now carried into Phase 6, but GPT is only called when MIMO locator status is `ok`.
- MIMO bbox parsing accepts either one JSON object or a one-item JSON array.
- MIMO bbox validation rejects out-of-bounds coordinates instead of falling back to an unsafe whole-crop mask.
- GPT fallback uses a large LabelPlus context crop for MIMO locating, then uses a smaller padded edit crop for the actual `gpt-image-2` call.
- GPT replacement crop composition expands the small GPT edit result back into the full context crop and keeps pixels outside the accepted target bbox untouched; inside the masked bbox it attempts to preserve manga tone and paste only confident dark text strokes.

## 2026-06-25 Earlier Update: Mask-Edge Matching And Full-Context GPT Fallback Experiment

The CTD path now matches the requested geometry more closely:

- CTD parameters are read from `BallonsTranslator/config/config.json`; the current running config uses `ctd.detect_size=1280`, `device=cpu`, `det_rearrange_max_batches=4`, and `mask dilate size=2`.
- All configured CTD keys are passed through, including `font size multiplier`, `font size max`, and `font size min`.
- Component splitting uses 8-connected components.
- LabelPlus points are matched against real CTD mask edge segments, not only the component bbox edge.
- Points inside a solid mask still use true distance to the nearest mask edge, not a special `0px` shortcut.
- Matching is one-to-one across the page by sorting all label/component candidates by mask-edge distance, then claiming the nearest available component group.

Regression tests added:

- Hollow bbox case: a point inside a component bbox but far from the real mask edge no longer matches.
- Solid mask case: a point deep inside a filled component still fails a small edge-distance threshold.
- Diagonal mask case: diagonal contact stays in one 8-connected component.
- BallonsTranslator config loader reads the running CTD config.

The mask-edge distance is stricter than the previous bbox-edge distance. For `GBC06_01.png#16`, the nearest CTD edge distance is `18.788px`, so the real experiment uses a `20px` threshold:

```powershell
python experiments/phase2_detect_text_regions.py --labelplus-file "GBC06 (已翻 斗笠)/翻译_0.txt" --output-root outputs/runs --run-id phase2-gbc06-ctd-mask-01-16-maskedge-config1280-v3-trueedge-th20 --sample-limit 1 --record-id "GBC06_01.png#16" --detection-strategy ctd_mask
```

Result:

- Status: `ok`
- Matched component id: `component-0001+component-0012+component-0016+component-0018+component-0026`
- Final bbox: `[1349, 122, 1407, 684]`
- Mask-edge distance: `18.788`
- Source coverage: full `桃香からの突然の提案`

Fallback locator changes:

- MIMO locator input now gets a coordinate-grid crop in `fallback_locator_input/*.png`.
- Locator JSON parser accepts `bbox_xyxy`, `bbox`, `bbox_percent_xyxy`, `bbox_normalized_xyxy`, and one-level nested bbox arrays.
- Out-of-bounds locator output triggers one strict retry with crop dimensions and the previous invalid response.
- A second MIMO pass validates whether the bbox covers the target original Japanese text. Rejected bboxes do not call `gpt-image-2`.
- If the bbox is semantically correct but reported as too tight, Phase 6 expands the transparent mask bbox before creating the tight edit context.
- The run writes a near-square locator grid at `visuals/fallback-locator-grid.png`.

Five-record fallback dry-run:

```powershell
python experiments/phase6_nonbubble_cleanup.py --detection-run-dir outputs/runs/phase2-gbc06-ctd-mask-fallback-candidates-v1 --output-root outputs/runs --run-id phase6-gbc06-ctd-fallback-mimo-semantic-gate-v3-parse-validation-retry --sample-limit 5
```

Result:

- `GBC06_16.png#5`, `GBC06_17.png#3`, `GBC06_18.png#2`, `GBC06_21.png#6`: locator + semantic gate accepted, GPT dry-run only.
- `GBC06_02.png#14`: rejected because bbox missed part of the large sound effect.
- Locator grid: `outputs/runs/phase6-gbc06-ctd-fallback-mimo-semantic-gate-v3-parse-validation-retry/visuals/fallback-locator-grid.png`
- MIMO grid evaluation: `outputs/runs/phase6-gbc06-ctd-fallback-mimo-semantic-gate-v3-parse-validation-retry/reports/mimo-fallback-locator-grid-evaluation.json`

The MIMO locator remains unstable across repeated runs. A later dry-run (`phase6-gbc06-ctd-fallback-mimo-full-context-gate-v4`) accepted `GBC06_02.png#14` and `GBC06_21.png#6` but rejected some visually acceptable boxes. The current operational stance is conservative: a semantic rejection blocks GPT rather than risking a wrong masked edit.

Controlled `gpt-image-2` replacement on `GBC06_16.png#5`:

1. Tight edit crop experiment:
   - Run: `outputs/runs/phase6-gbc06-ctd-fallback-gpt-semantic-gate-16-5-v1`
   - Grid: `visuals/gpt-image2-16-5-optimized-comparison-grid.png`
   - MIMO evaluation: `reports/mimo-gpt-image2-16-5-optimized-evaluation.json`
   - Result: gray box removed by postprocessing, but the replacement glyph became an unreadable black blob.
   - MIMO score: `1/10`, recommendation `reject`.

2. Full-context masked edit experiment:
   - Run: `outputs/runs/phase6-gbc06-ctd-fallback-gpt-full-context-16-5-v1`
   - Input: full LabelPlus context crop, not the tight crop.
   - Mask: transparent only over the target bbox.
   - Grid: `visuals/gpt-image2-full-context-16-5-comparison-grid.png`
   - MIMO evaluation: `reports/mimo-gpt-image2-full-context-16-5-evaluation.json`
   - Result: target text `哼` correct, original removed, gray-box artifact removed after masked composition, artwork preserved.
   - MIMO score: `10/10`, recommendation `Accept`.

That full-context experiment remains useful evidence, but the current operational path has been tightened again after the later CTA-first rewrite: GPT receives a padded target edit crop, not the full LabelPlus context crop. The full context crop is retained as the Phase 7 replacement canvas.

## 2026-06-26 Update: Fallback Context Expansion And Semantic Relocation

This update revisited `GBC06_02.png#14` after the CTA-first rewrite. The LabelPlus point is far below the large `スタスタ...` sound effect, so the default CTA miss context was too centered around the point.

Phase 2 now keeps the strict CTA/CTD match threshold unchanged and only expands the MIMO fallback context:

- `fallback_required` remains `fallback_required`; a far CTA/CTD component is not promoted to a matched mask.
- `fallback.source_context_bbox_xyxy` keeps the original LabelPlus search region.
- `fallback.expanded_source_context_bbox_xyxy` records the union of the search region and nearby CTA/CTD diagnostic candidates.
- `fallback.context_candidate_component_ids` and `fallback.context_candidate_bboxes_xyxy` record which diagnostic components expanded the context.
- CTD diagnostics now retain 12 nearest candidates so a large sound effect split across multiple components can still be used as context evidence.

Real Phase 2 checks for `GBC06_02.png#14`:

| Run | Status | Nearest CTA component | Fallback context | Notes |
| --- | --- | --- | --- | --- |
| `phase2-gbc06-02-14-cta-default-v1` | `fallback_required` | `component-0048`, `222.056px` | `[504, 1253, 944, 1693]` | Old baseline; sound effect is partially cropped. |
| `phase2-gbc06-02-14-cta-fallback-context-v1` | `fallback_required` | `component-0048`, `222.056px` | `[484, 1173, 964, 1653]` | Includes only the nearest diagnostic component; still too narrow for the full sound effect. |
| `phase2-gbc06-02-14-cta-fallback-context-v2` | `fallback_required` | `component-0048`, `222.056px` | `[318, 1001, 970, 1653]` | Uses clustered nearby diagnostic candidates; covers the full large sound effect. |

The useful Phase 2 visual artifact is:

- `outputs/runs/phase2-gbc06-02-14-cta-fallback-context-v2/debug/fallback-context-overlay.png`

Phase 6 then exposed a separate failure mode: MIMO often described the correct sound effect but returned a bbox shifted downward. Two safeguards were added:

- MIMO JSON parsing now recovers the first complete JSON object when the model returns a valid object followed by stray trailing text such as `]`.
- When semantic validation rejects a locator bbox, Phase 6 performs one semantic relocation pass using the validation feedback, then validates the corrected bbox again. GPT remains blocked if the second validation is still rejected.

Real Phase 6 dry-runs for `GBC06_02.png#14`:

| Run | Locator bbox | Validation | GPT status | Result |
| --- | --- | --- | --- | --- |
| `phase6-gbc06-02-14-fallback-context-mimo-v1` | `[43, 510, 555, 635]` | `rejected` | `not_called` | Bbox shifted onto blank/hair area; guard blocked GPT. |
| `phase6-gbc06-02-14-fallback-context-mimo-v2-json-recover` | `[0, 498, 608, 608]` | `rejected` | `not_called` | JSON recovery avoided an unnecessary retry, but bbox was still too low. |
| `phase6-gbc06-02-14-fallback-context-mimo-v3-semantic-retry` | `[24, 428, 634, 515]` | `accepted` | `dry_run` | Semantic relocation moved the bbox onto the sound effect. It is usable but still loose. |
| `phase6-gbc06-02-14-fallback-context-mimo-v6-percent-fallback` | `[8, 418, 602, 562]` | `accepted`, `tight_enough=false` | `dry_run` | Pixel bbox parsing worked and the rejected tightness retry was recorded, but the final bbox remained too loose. |
| `phase6-gbc06-02-14-fallback-context-mimo-v7-tight-guard` | `[51, 549, 581, 652]` | `rejected` | `not_called` | A repeated MIMO run shifted downward again; the semantic guard correctly blocked GPT. |

Important v3 artifacts:

- Locator input: `outputs/runs/phase6-gbc06-02-14-fallback-context-mimo-v3-semantic-retry/fallback_locator_input/GBC06-02-png-14.png`
- Validation image: `outputs/runs/phase6-gbc06-02-14-fallback-context-mimo-v3-semantic-retry/fallback_locator_validation_input/GBC06-02-png-14.png`
- Locator grid: `outputs/runs/phase6-gbc06-02-14-fallback-context-mimo-v3-semantic-retry/visuals/fallback-locator-grid.png`
- Replacement grid: `outputs/runs/phase6-gbc06-02-14-fallback-context-mimo-v3-semantic-retry/visuals/fallback-replacement-grid.png`

Historical conclusion for the v1-v7 locator runs:

- This is now a partially usable fallback locator path for this previously failing sound-effect record: Phase 6 can sometimes reach `fallback_locator_validation.status=accepted`, but repeated MIMO calls still vary.
- At this historical point, loose accepted bboxes were still treated conservatively and could block real GPT calls. That policy has since been replaced: a fallback bbox only needs to contain the intended original text, while `gpt-image-2` receives a `text_pixels` mask and prompt constraints to preserve passerby/background/non-text art.
- MIMO pixel bbox parsing now falls back to `bbox_percent_xyxy` when the pixel bbox is out of bounds.
- The older MIMO tightness retry path has been removed from current code; `tight_enough=false` remains diagnostic metadata rather than a reason to chase a cleaner box that excludes non-text context.
- Rejected locators are still blocked when they miss the target text, point to blank area, or point to a different text string.

## 2026-06-26 Update: Light-background Ink Trim And Anchor Recovery

`GBC06_02.png#14` exposed an additional locator failure mode after v7: the target is a large black sound effect on a light manga background, while the LabelPlus point sits below the text. The previous `_refine_fallback_locator_bbox` only handled a dark-background support case and only trimmed horizontally, so it did not help when MIMO returned a box shifted down over hair and blank space.

Two deterministic refinements were added before any real GPT edit is allowed:

- `trim_to_light_text_ink_support`: for large loose bboxes on mostly light backgrounds, find the dense dark-ink row band and shrink around it. This is conservative and returns the original bbox if no clear band is found.
- `recover_light_text_ink_band_near_labelplus_anchor`: when a MIMO locator bbox is rejected or accepted-but-loose and is clearly below the LabelPlus anchor, search near the anchor for a light-background dark-ink band, then validate that candidate with MIMO.

Real dry-runs for `GBC06_02.png#14` after this change:

| Run | Final locator bbox | Validation | GPT status | Result |
| --- | --- | --- | --- | --- |
| `phase6-gbc06-02-14-fallback-context-mimo-v8-ink-trim` | `[23, 542, 585, 650]` | `rejected` | `not_called` | Initial MIMO bbox landed on hair/blank; shrink-only trim correctly did not pretend to fix it. |
| `phase6-gbc06-02-14-fallback-context-mimo-v10-anchor-tight-recovery` | `[0, 302, 652, 381]` | `accepted`, `tight_enough=true` | `dry_run` | Anchor recovery was too broad and jumped to the panel above; this proved MIMO can falsely accept a wrong tight bbox. |
| `phase6-gbc06-02-14-fallback-context-mimo-v12-invalid-anchor-recovery` | `[38, 397, 652, 555]` | `accepted`, `tight_enough=true` | `dry_run` | Invalid MIMO bbox was recovered to the correct sound-effect band, but still included too much lower artwork. |
| `phase6-gbc06-02-14-fallback-context-mimo-v14-accepted-loose-anchor` | `[39, 398, 649, 487]` | `accepted`, `tight_enough=true` | `dry_run` | Best current candidate: bbox visually targets the full sound effect and excludes most hair/blank area. |
| `phase6-gbc06-02-14-fallback-context-mimo-v15-current-anchor` | `[31, 531, 560, 645]` | `rejected` | `not_called` | MIMO retry returned a valid but too-low bbox; this revealed a missing second anchor-recovery chance after retry validation rejection. |
| `phase6-gbc06-02-14-fallback-context-mimo-v16-retry-reject-anchor` | `[30, 508, 628, 648]` | `rejected` | `not_called` | Current guard still blocks GPT when the final validated bbox stays on hair/blank. |

Comparison grid:

- `outputs/runs/phase6-gbc06-02-14-anchor-recovery-comparison.png`

Important behavior:

- `gpt-image-2` was not called for this sample unless the current run reached a validated tight bbox. A run attempted with `--call-gpt-image` (`phase6-gbc06-02-14-fallback-context-gpt-v2-anchor-tight`) did not actually call GPT because the MIMO locator was loose/rejected in that run, and Phase 6 returned `gpt_image2_edit.status=not_called`.
- The best current evidence is a usable locator candidate, not a successful GPT replacement. The remaining blocker is locator stability under repeated MIMO calls, especially when MIMO returns a valid but too-low retry bbox.
- MIMO validation is helpful but not sufficient as the sole gate: v10 visually targeted the wrong upper panel while MIMO marked it tight. Programmatic anchor/window guards are required before trusting `accepted + tight_enough=true`.

### 2026-06-26 Follow-up: Right-edge Cap, Historical Accepted-below-anchor Guard, And GPT Replacement Trials

Additional real runs for `GBC06_02.png#14` targeted the same bottom-panel sound effect after the earlier anchor recovery work. The then-current implemented changes were:

- Persist rejected recovery candidates under `fallback_locator.anchor_recovery_attempt` / `fallback_locator.tightness_retry`, including candidate bbox, refinement metadata, validation status, reasoning, and validation image path. This keeps failed candidate evidence visible in later grids and JSONL.
- Add a right-edge cap for anchor-recovered light-background sound effects. It trims sparse right-side screentone or a strong panel-divider column after the target text, without changing the left/top/bottom bounds.
- Add an accepted-below-anchor guard: even when MIMO marks a bbox as `accepted` and `tight_enough=true`, Phase 6 retries deterministic anchor recovery if the bbox extends far below the LabelPlus anchor and horizontally covers the anchor. This was a historical guard for earlier locator instability and has since been removed from the accepted-bbox path; current code keeps a semantically accepted bbox even if it includes nearby artwork, and only uses anchor recovery after a semantic rejection.
- Strengthen the GPT image prompt with an explicit character sequence and exact character count, e.g. `啪 | 嗒 | 啪 | 嗒 | 啪 | 嗒`, plus warnings not to substitute `啪` or `嗒`.

Locator and GPT replacement runs:

| Run | Final locator bbox | Validation | GPT/MIMO result | Manual conclusion |
| --- | --- | --- | --- | --- |
| `phase6-gbc06-02-14-fallback-context-mimo-v18-panel-divider-cap` | `[38, 398, 525, 488]` | `accepted`, `tight_enough=true` | `dry_run` | Locator became usable: full sound effect is covered and right panel screentone is excluded. |
| `phase6-gbc06-02-14-fallback-context-mimo-v19-accepted-guard` | `[38, 396, 525, 488]` | `accepted`, `tight_enough=true` | `dry_run` | Guard recovered a too-low MIMO result back to the target sound-effect band. |
| `phase6-gbc06-02-14-fallback-context-gpt-v3-panel-divider-cap` | `[38, 397, 525, 488]` | `accepted`, `tight_enough=true` | MIMO score `0`, `usable=false`, observed text `啦嗒啦嗒啦` | Region and style were close, but exact text failed and generated artifacts remained. |
| `phase6-gbc06-02-14-fallback-context-gpt-v4-exact-sequence-prompt` | `[0, 455, 652, 570]` | `accepted`, `tight_enough=true` | MIMO score `10`, `usable=true` | False-positive evaluation: manual review shows the edit region was too low and mostly cleared hair/blank area rather than producing a usable translation. |
| `phase6-gbc06-02-14-fallback-context-gpt-v5-guarded-exact-prompt` | `[38, 400, 520, 480]` | `accepted`, `tight_enough=true` | MIMO score `0`, `usable=false`, observed text `嗒嗒哈哈` | Better guarded region, but exact text still failed; GPT omitted `啪` and substituted wrong characters. |

Important artifacts:

- Locator overlay: `outputs/runs/phase6-gbc06-02-14-fallback-context-mimo-v19-accepted-guard/debug/fallback_locator_overlays/GBC06-02-png-14.png`
- GPT v3 quality sheet: `outputs/runs/phase6-gbc06-02-14-gpt-v3-mimo-quality/debug/replacement_quality_sheets/GBC06-02-png-14.png`
- GPT v4 quality sheet: `outputs/runs/phase6-gbc06-02-14-gpt-v4-mimo-quality/debug/replacement_quality_sheets/GBC06-02-png-14.png`
- GPT v5 quality sheet: `outputs/runs/phase6-gbc06-02-14-gpt-v5-mimo-quality/debug/replacement_quality_sheets/GBC06-02-png-14.png`
- Near-square comparison grid: `outputs/runs/phase6-gbc06-02-14-gpt-comparison-v1/visuals/gpt-v3-v4-v5-comparison.png`

Current conclusion for this sample:

- The fallback locator path is now usable enough to produce a tight target region for manual inspection and controlled GPT calls.
- `gpt-image-2` direct replacement was not usable in the v3/v4/v5 trial set because those runs either generated the wrong Chinese characters or edited the wrong/too-low region when the locator was unstable. A later `v3-sfx-recovery` run, recorded below, is the first accepted GPT direct-replacement result for this sample.
- MIMO replacement evaluation is useful as evidence but not sufficient as an automatic acceptance gate. It correctly rejected v3/v5, but falsely accepted v4, so manual review or an additional OCR/shape check is still required before consuming GPT direct replacements.

### 2026-06-26 Follow-up: GPT Replacement Quality Gate For Phase 7/8 Consumption

The GPT replacement trials above exposed a downstream contract bug: Phase 7 and
Phase 8 treated `gpt_image2_edit.status=ok` plus `cleanup.replacement_crop_path`
as enough evidence that a direct replacement could be consumed as final text.
That was unsafe for `GBC06_02.png#14`: v3/v5 were correctly rejected by MIMO,
and v4 was manually identified as a false-positive despite the model score.

The consumption contract is now stricter when a Phase 6 replacement-quality run
is supplied:

- `phase6_replacement_quality.py` writes `replacement-quality.jsonl` with
  `usable`, `exact_text_correct`, `simplified_chinese_correct`,
  `no_japanese_remaining`, `region_correct`, and style/preservation fields.
- Phase 7 and Phase 8 accept a repeatable `--phase6-gpt-quality-run-dir`
  argument.
- The CTA-first Phase 2/6 wrapper also accepts repeatable
  `--phase6-gpt-quality-run-dir` values. Its manifest stores
  `phase6_gpt_quality_run_dir`, and its GPT fallback summary no longer counts
  an API-ok replacement crop as completed when the supplied quality row rejects
  or misses that `record_id`.
- A `gpt_image2_masked_edit` replacement crop is consumed as final text only
  when the quality row for the same `record_id` has:
  - `status=evaluated`
  - `usable=true`
  - `exact_text_correct=true`
  - `simplified_chinese_correct=true`
  - `no_japanese_remaining=true`
  - `region_correct=true`
- If the quality row is missing or any required boolean is false, the GPT
  replacement crop is ignored by consumers. Phase 7 requires/uses the normal
  layout overlay path; Phase 8 exports an editable Photoshop text layer and
  uses the cleaned/background crop instead of baking the bad GPT text into the
  page-level `修复图像`.
- The rejected replacement keeps a compact `gpt_replacement_quality` payload in
  preview/export metadata so the user can see why the GPT crop was not used.
- Pipeline coverage now reads the new `replacement-quality.jsonl` directly and
  reports `phase6_gpt_image2_quality_unacceptable` per affected record. The
  older manifest/MIMO summary path remains supported for legacy runs.

Example gated preview:

```powershell
python experiments/phase7_page_preview.py --detection-run-dir outputs/runs/<phase2> --cleanup-run-dir outputs/runs/<phase6-gpt> --layout-run-dir outputs/runs/<phase4-layout> --phase6-gpt-quality-run-dir outputs/runs/<phase6-replacement-quality> --output-root outputs/runs --run-id <phase7-gated> --sample-limit 1
```

Example gated CTA-first summary:

```powershell
python experiments/phase2_6_cta_first_cleanup.py --record-id "<record-id>" --sample-limit 1 --call-gpt-image --phase6-gpt-quality-run-dir outputs/runs/<phase6-replacement-quality> --run-id <phase2-6-gated>
```

Example gated Photoshop export:

```powershell
python experiments/phase8_photoshop_export.py --detection-run-dir outputs/runs/<phase2> --font-selection-run-dir outputs/runs/<phase3-font> --layout-run-dir outputs/runs/<phase4-layout> --cleanup-run-dir outputs/runs/<phase6-gpt> --phase6-gpt-quality-run-dir outputs/runs/<phase6-replacement-quality> --output-root outputs/runs --run-id <phase8-gated> --sample-limit 1
```

Example local Phase 7/8 quality-gate smoke without new API calls:

```powershell
python experiments/phase7_8_gpt_quality_gate_smoke.py --detection-run-dir outputs/runs/<phase2> --cleanup-run-dir outputs/runs/<phase6-gpt> --phase6-gpt-quality-run-dir outputs/runs/<phase6-replacement-quality> --output-root outputs/runs --run-id <phase7-8-quality-gated-smoke> --sample-limit 1
```

Important scope note: if no `--phase6-gpt-quality-run-dir` is supplied, the
CTA-first wrapper, Phase 7, and Phase 8 keep their previous compatibility
behavior. Strict gating is enabled by passing the quality run directory.

### Real Quality-Gated Smoke: `GBC06_02.png#14` GPT v3 Rejection

This smoke uses existing real GPT and MIMO artifacts only; it does not call
`gpt-image-2` or MIMO again.

Command:

```powershell
python experiments/phase7_8_gpt_quality_gate_smoke.py --detection-run-dir outputs/runs/phase2-gbc06-02-14-cta-fallback-context-v2 --cleanup-run-dir outputs/runs/phase6-gbc06-02-14-fallback-context-gpt-v3-panel-divider-cap --phase6-gpt-quality-run-dir outputs/runs/phase6-gbc06-02-14-gpt-v3-mimo-quality --output-root outputs/runs --run-id phase7-8-gbc06-02-14-gpt-v3-quality-gated-smoke-v1 --sample-limit 1
```

Inputs:

- Detection: `outputs/runs/phase2-gbc06-02-14-cta-fallback-context-v2`
- GPT cleanup: `outputs/runs/phase6-gbc06-02-14-fallback-context-gpt-v3-panel-divider-cap`
- MIMO replacement quality: `outputs/runs/phase6-gbc06-02-14-gpt-v3-mimo-quality`

Output:

- Run directory: `outputs/runs/phase7-8-gbc06-02-14-gpt-v3-quality-gated-smoke-v1`
- Summary: `quality-gate-smoke-summary.json`
- Run-local report: `reports/quality-gate-smoke-report.md`
- Phase 7 preview: `runs/phase7-preview/pages/GBC06-02-png.png`
- Phase 8 manifest: `runs/phase8-export/photoshop-manifest.json`
- Evidence grid: `visuals/quality-gate-evidence-grid.png`

Result:

- Quality gate: `accepted=false`, `failure_reason=quality_rejected`.
- Phase 7 used `fallback_input/GBC06-02-png-14.png`, not the bad
  `fallback_replacement_crop/GBC06-02-png-14.png`.
- Phase 7 kept `text_overlay_required=true`.
- Phase 8 exported an editable text layer for `GBC06_02.png#14`.
- Phase 8 set `replacement_method=null` and used the same cleaned/background
  crop as `effective_crop_path`, so the bad GPT text was not baked into
  `修复图像`.

Follow-up smoke with the evidence grid enabled:

```powershell
python experiments/phase7_8_gpt_quality_gate_smoke.py --detection-run-dir outputs/runs/phase2-gbc06-02-14-cta-fallback-context-v2 --cleanup-run-dir outputs/runs/phase6-gbc06-02-14-fallback-context-gpt-v3-panel-divider-cap --phase6-gpt-quality-run-dir outputs/runs/phase6-gbc06-02-14-gpt-v3-mimo-quality --output-root outputs/runs --run-id phase7-8-gbc06-02-14-gpt-v3-quality-gated-smoke-v2 --sample-limit 1
```

The new grid is near-square (`690x738`) and puts the original bbox crop,
rejected GPT crop, gated cleaned crop, and final Phase 7 before/after crop in a
single manual-review image:

- `outputs/runs/phase7-8-gbc06-02-14-gpt-v3-quality-gated-smoke-v2/visuals/quality-gate-evidence-grid.png`

Pipeline coverage reads the same `phase6_gpt_quality_run_dir` signal directly.
This smoke run is a local diagnostic package for manual review and PSD/preview
chain verification; it is not a new registry stage that should replace the
underlying Phase 6 quality run in coverage inputs.

### Real Fallback Background Repair Smoke: `GBC06_02.png#14`

The v3 quality-gated smoke above revealed a second downstream contract risk:
when a GPT direct replacement is missing, dry-run, or later rejected, the
fallback row must not expose the raw `fallback_input` crop as its effective
cleaned background. Otherwise Phase 7/8 can correctly ignore bad GPT text but
still consume an unrepaired source crop.

The fallback path now writes a local LaMA background repair before GPT
acceptance:

- `cleanup.method=bt_lama_large_inpaint`
- `cleanup.cleaned_crop_path=fallback_cleaned/<record>.png`
- `cleanup.cleanup_mask_path=fallback_mask/<record>.png`
- `cleanup.before_after_path=fallback_before_after/<record>.png`
- `cleanup.replacement_failure_reason=gpt_image2_replacement_not_completed`
- `cleanup.replacement_method` is omitted unless a GPT edit actually succeeds

MIMO locator validation can be noisy on this sample. Two guardrails were added
to avoid losing a visually usable crop to structured-output variance:

- If MIMO returns `semantic_correct=false` but its reasoning explicitly says
  the bbox corresponds to the Chinese translation, Phase 6 retries semantic
  validation instead of treating the first JSON boolean as final.
- Historical note: this run predated the current loose-bbox policy. At that
  point, a local CV tightness override was allowed for known CV-refined locator
  bboxes whose area and side ratios were small enough. Current code has removed
  that tightness override path; `tight_enough=false` is diagnostic metadata and
  does not block GPT when the target original text is visible.

Real Phase 6 command:

```powershell
python experiments/phase6_nonbubble_cleanup.py --detection-run-dir outputs/runs/phase2-gbc06-02-14-cta-fallback-context-v2 --output-root outputs/runs --run-id phase6-gbc06-02-14-fallback-context-mimo-v24-background-cleaned-status --sample-limit 1 --record-id "GBC06_02.png#14"
```

Output:

- Run directory: `outputs/runs/phase6-gbc06-02-14-fallback-context-mimo-v24-background-cleaned-status`
- Cleaned context crop: `fallback_cleaned/GBC06-02-png-14.png` (`652x652`)
- Cleanup mask: `fallback_mask/GBC06-02-png-14.png` (`652x652`)
- Before/after context comparison: `fallback_before_after/GBC06-02-png-14.png` (`1304x652`)
- Fallback locator grid: `visuals/fallback-locator-grid.png` (`350x374`)
- Fallback replacement/debug grid: `visuals/fallback-replacement-grid.png` (`690x738`)

Key result:

- `status=cleaned`
- `gpt_image2_edit.status=dry_run`
- `replacement_method=null`
- `text_overlay_required=true`
- `fallback_locator_validation.status=accepted`
- `fallback_locator_validation.tight_enough=true`

Downstream Phase 7/8 smoke command:

```powershell
python experiments/phase7_8_gpt_quality_gate_smoke.py --detection-run-dir outputs/runs/phase2-gbc06-02-14-cta-fallback-context-v2 --cleanup-run-dir outputs/runs/phase6-gbc06-02-14-fallback-context-mimo-v24-background-cleaned-status --phase6-gpt-quality-run-dir outputs/runs/phase6-empty-quality-for-fallback-cleaned-smoke --output-root outputs/runs --run-id phase7-8-gbc06-02-14-fallback-cleaned-v24-smoke --sample-limit 1
```

Output:

- Run directory: `outputs/runs/phase7-8-gbc06-02-14-fallback-cleaned-v24-smoke`
- Summary: `quality-gate-smoke-summary.json`
- Evidence grid: `visuals/quality-gate-evidence-grid.png` (`690x738`)
- Phase 7 preview: `runs/phase7-preview/pages/GBC06-02-png.png`
- Phase 7 cleaned page: `runs/phase7-preview/pages/cleaned/GBC06-02-png.png`
- Phase 8 manifest: `runs/phase8-export/photoshop-manifest.json`

Downstream result:

- Phase 7 used
  `outputs/runs/phase6-gbc06-02-14-fallback-context-mimo-v24-background-cleaned-status/fallback_cleaned/GBC06-02-png-14.png`
  as `phase7_cleanup_crop_path`.
- Phase 7 kept `phase7_text_overlay_required=true`.
- Phase 8 exported an editable text layer for `GBC06_02.png#14`.
- Phase 8 used the same `fallback_cleaned` crop as
  `phase8_effective_crop_path`.
- Phase 8 set `phase8_effective_method=bt_lama_large_inpaint` and
  `phase8_replacement_method=null`, so dry-run GPT output is not represented as
  a completed replacement.

### 2026-06-27 Follow-up: `GBC06_02.png#14` GPT v3 SFX Recovery Accepted

The latest user direction changed the fallback bbox policy: do not over-optimize
the crop to exclude passerby/background content. The box only needs to contain
the intended original text; `gpt-image-2` receives a text-pixel mask and a prompt
that says to modify only the original Japanese lettering.

Two narrow fixes were required before calling GPT again:

- MIMO validator rejections that only object to Japanese sound-effect semantics
  can be overridden when the visible original text is kana-like SFX, the bbox is
  not blank, and the reasoning says the bbox covers the sound effect.
- Anchor recovery now tries the light-background sound-effect band before the
  dark vertical-column recovery when the translation or MIMO reasoning indicates
  an SFX target. This prevents a nearby dark vertical decoy from stealing the
  bbox while preserving dark-column recovery for ordinary vertical non-bubble
  text.

Real Phase 6 command:

```powershell
python experiments/phase6_nonbubble_cleanup.py --detection-run-dir outputs/runs/phase2-gbc06-02-14-cta-detection-v1 --output-root outputs/runs --run-id phase6-gbc06-02-14-fallback-gpt-image2-v3-sfx-recovery --sample-limit 1 --record-id "GBC06_02.png#14" --call-gpt-image --fallback-gpt-mask-shape text_pixels --fallback-edit-padding-px 16 --fallback-mask-expand-px 0
```

Output:

- Run directory: `outputs/runs/phase6-gbc06-02-14-fallback-gpt-image2-v3-sfx-recovery`
- Locator overlay: `debug/fallback_locator_overlays/GBC06-02-png-14.png`
- Replacement grid: `visuals/fallback-replacement-grid.png`
- GPT output: `gpt_image2/GBC06-02-png-14.png`
- Normalized GPT output: `gpt_image2_normalized/GBC06-02-png-14.png`
- Replacement crop: `fallback_replacement_crop/GBC06-02-png-14.png`

Key result:

- `status=cleaned`
- `fallback_locator.local_bbox_xyxy=[38,398,652,496]`
- `fallback_locator.refinement.method=recover_light_text_ink_band_near_labelplus_anchor`
- `fallback_locator_validation.status=accepted`
- `gpt_image2_edit.status=ok`
- `cleanup.replacement_method=gpt_image2_masked_edit`
- `text_overlay_required=false`

MIMO replacement-quality command:

```powershell
python experiments/phase6_replacement_quality.py --cleanup-run-dir outputs/runs/phase6-gbc06-02-14-fallback-gpt-image2-v3-sfx-recovery --output-root outputs/runs --run-id phase6-gbc06-02-14-gpt-v3-sfx-recovery-quality --sample-limit 1 --record-id "GBC06_02.png#14"
```

MIMO result:

- Run directory: `outputs/runs/phase6-gbc06-02-14-gpt-v3-sfx-recovery-quality`
- Quality sheet: `debug/replacement_quality_sheets/GBC06-02-png-14.png`
- `score=10`
- `usable=true`
- `exact_text_correct=true`
- `simplified_chinese_correct=true`
- `no_japanese_remaining=true`
- `region_correct=true`
- `style_consistent=true`
- `outside_mask_preserved=true`
- `issues=[]`

Downstream Phase 7/8 quality-gate smoke command:

```powershell
python experiments/phase7_8_gpt_quality_gate_smoke.py --detection-run-dir outputs/runs/phase2-gbc06-02-14-cta-detection-v1 --cleanup-run-dir outputs/runs/phase6-gbc06-02-14-fallback-gpt-image2-v3-sfx-recovery --phase6-gpt-quality-run-dir outputs/runs/phase6-gbc06-02-14-gpt-v3-sfx-recovery-quality --output-root outputs/runs --run-id phase7-8-gbc06-02-14-gpt-v3-sfx-quality-gate --sample-limit 1
```

Downstream result:

- Run directory: `outputs/runs/phase7-8-gbc06-02-14-gpt-v3-sfx-quality-gate`
- Evidence grid: `visuals/quality-gate-evidence-grid.png`
- `gpt_quality_accepted=true`
- Phase 7 used `fallback_replacement_crop/GBC06-02-png-14.png`
- Phase 7 kept `phase7_text_overlay_required=false`
- Phase 8 wrote no editable text layer for this record.
- Phase 8 repair source uses `effective_method=gpt_image2_masked_edit` and
  `effective_crop_path=outputs\runs\phase6-gbc06-02-14-fallback-gpt-image2-v3-sfx-recovery\fallback_replacement_crop\GBC06-02-png-14.png`

Manual-review caveat: this is the first accepted direct GPT result for this SFX
sample, but prior v4 showed a false-positive MIMO score. The compact quality
sheet and evidence grid should remain part of manual review before treating the
style/readability as final.

### 2026-06-27 Follow-up: `GBC06_03.png#5` Loose Bbox With Text-pixel Mask Accepted

The latest user policy is now the active fallback contract: for non-bubble GPT
fallback, the MIMO locator bbox only needs to contain the intended original
text. It may include nearby people, hair, props, background, or other non-text
manga art. Phase 6 should not retry, relocate, or reject solely to make that
bbox visually cleaner. The edit scope is controlled by the generated
`text_pixels` mask and the `gpt-image-2` prompt, which instructs the model to
replace only the original Japanese lettering.

Code-level effects in the current implementation:

- The MIMO tightness retry prompt/path was removed.
- Semantically accepted fallback locator bboxes are no longer automatically
  refined by CV before GPT.
- Accepted-below-anchor recovery is no longer run for accepted bboxes.
- `needs_tighter_edit_mask=false` is always recorded; `tight_enough=false`
  remains diagnostic metadata.
- If MIMO's structured JSON rejects only because the bbox is loose or includes
  non-text artwork while its reasoning says the target text is visible, Phase 6
  normalizes that validation to accepted.

Real Phase 6 command:

```powershell
python experiments/phase6_nonbubble_cleanup.py --detection-run-dir outputs/runs/phase2-gbc06-03-batch-4-6-cta-detection-v3-threshold40-merged --output-root outputs/runs --run-id phase6-gbc06-03-5-fallback-gpt-image2-v18-accepted-bbox-no-refine --sample-limit 1 --record-id "GBC06_03.png#5" --call-gpt-image --fallback-edit-padding-px 16 --fallback-mask-expand-px 0
```

Output:

- Run directory: `outputs/runs/phase6-gbc06-03-5-fallback-gpt-image2-v18-accepted-bbox-no-refine`
- Locator grid: `visuals/fallback-locator-grid.png`
- Replacement grid: `visuals/fallback-replacement-grid.png`
- GPT mask: `fallback_edit_gpt_mask/GBC06-03-png-5.png`
- Mask preview: `debug/fallback_replacement_mask_previews/GBC06-03-png-5.png`
- Replacement crop: `fallback_replacement_crop/GBC06-03-png-5.png`

Key result:

- `status=cleaned`
- `fallback_locator.local_bbox_xyxy=[194,103,243,395]`
- `fallback_locator.refinement.method=recover_dark_text_ink_column_near_labelplus_anchor`
- `fallback_locator.anchor_recovery_of_validation=fallback_locator_semantic_rejected`
- `fallback_locator_validation.status=accepted`
- `fallback_locator_validation.tight_enough=false`
- `fallback_locator_validation.needs_tighter_edit_mask=false`
- `gpt_image2_edit.status=ok`
- `gpt_image2_edit.edit_context.mask_strategy=text_pixels_within_bbox`
- `cleanup.replacement_method=gpt_image2_masked_edit`
- `text_overlay_required=false`

Manual inspection of the replacement grid shows the accepted locator region
includes non-text manga art, but the transparent edit mask follows the original
Japanese glyph pixels rather than a full rectangle. The final replacement writes
the Chinese text `好孩子不要看…` into the target vertical text region without
turning the whole locator bbox into a white block.

MIMO replacement-quality command:

```powershell
python experiments/phase6_replacement_quality.py --cleanup-run-dir outputs/runs/phase6-gbc06-03-5-fallback-gpt-image2-v18-accepted-bbox-no-refine --output-root outputs/runs --run-id phase6-gbc06-03-5-fallback-gpt-image2-v18-quality --sample-limit 1 --record-id "GBC06_03.png#5"
```

MIMO result:

- Run directory: `outputs/runs/phase6-gbc06-03-5-fallback-gpt-image2-v18-quality`
- Quality sheet: `debug/replacement_quality_sheets/GBC06-03-png-5.png`
- `score=9`
- `usable=true`
- `exact_text_correct=true`
- `simplified_chinese_correct=true`
- `no_japanese_remaining=true`
- `region_correct=true`
- `style_consistent=true`
- `outside_mask_preserved=true`
- `issues=[]`

Manual-review caveat: MIMO accepted this result and the quality sheet is
visually consistent with the new loose-bbox contract, but previous GPT fallback
runs have shown false-positive model scoring. Keep the replacement grid and
quality sheet in the manual review package before treating GPT-direct
replacement as final.

## Current Recommendation

Use the CTD matched path with `lama_large_512px` for non-bubble text when CTD detects the original text. This remains the most deterministic route.

Keep the GPT fallback route behind the CTA miss path rather than using it for all non-bubble text. For GPT fallback, prefer `text_pixels` masks and allow loose bboxes that contain the intended original text; do not chase bbox purity just to exclude passerby/background artwork. Remaining blockers are:

- MIMO bbox coordinates are still unstable on some crops and can return coordinates outside the crop dimensions.
- `gpt-image-2` can still introduce gray/dark rectangular artifacts on harder regions.
- Postprocessing reduces blast radius but cannot reliably recover clean manga background from every bad GPT output.

Next experiments should focus on fallback locator stability:

- Add a coordinate-ruler or numbered-grid locator image for MIMO, while keeping the GPT edit input clean.
- Ask MIMO for percentage coordinates and convert to pixels as a fallback.
- Keep GPT edits on masks shaped from detected original glyph pixels rather than a broad rectangle.
- Reject GPT outputs with gray-box artifacts before Phase 7/8 consumption.

## Verification

```powershell
python -m pytest tests/test_phase6_nonbubble_cleanup.py tests/test_phase7_preview.py tests/test_phase8_photoshop_export.py tests/test_phase7_8_gpt_quality_gate_smoke.py tests/test_cta_first_pipeline.py -q
```

Result: `107 passed`.

Full regression:

```powershell
python -m pytest -q
```

Result: `366 passed`.
