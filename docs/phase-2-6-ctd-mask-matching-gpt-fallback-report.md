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

## Current Recommendation

Use the CTD matched path with `lama_large_512px` for non-bubble text when CTD detects the original text. This is the currently usable route.

Keep the GPT fallback route behind the CTA miss path rather than using it for all non-bubble text. Remaining blockers are:

- MIMO bbox coordinates are still unstable on some crops and can return coordinates outside the crop dimensions.
- `gpt-image-2` can still introduce gray/dark rectangular artifacts on harder regions.
- Postprocessing reduces blast radius but cannot reliably recover clean manga background from every bad GPT output.

Next experiments should focus on fallback locator stability:

- Add a coordinate-ruler or numbered-grid locator image for MIMO, while keeping the GPT edit input clean.
- Ask MIMO for percentage coordinates and convert to pixels as a fallback.
- Run GPT on a mask shaped from detected original glyph pixels rather than a broad rectangle.
- Reject GPT outputs with gray-box artifacts before Phase 7/8 consumption.

## Verification

```powershell
python -m pytest tests/test_ctd_mask_matching.py tests/test_phase2_ctd_strategy.py tests/test_phase2_detection.py tests/test_experiment_clis.py tests/test_text_bbox.py tests/test_phase3_fonts.py tests/test_phase6_nonbubble_cleanup.py tests/test_phase6_nonbubble_gpt_replace.py tests/test_phase7_preview.py tests/test_phase7_preview_evaluation.py tests/test_phase8_photoshop_export.py tests/test_phase8_photoshop_export_alignment.py tests/test_phase7_8_smoke.py -q
```

Result: `130 passed`.

Full regression:

```powershell
python -m pytest -q
```

Result: `252 passed`.
