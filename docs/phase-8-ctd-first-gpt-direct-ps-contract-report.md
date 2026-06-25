# Phase 8 CTD-first GPT Direct Photoshop Contract Report

Date: 2026-06-25

## Scope

This report records the Photoshop export contract check for a CTD-first fallback record that was directly replaced by `gpt-image-2`.

Target sample:

- Record: `GBC06_17.png#3`
- Translation: `新川崎（暂）`
- Detection route: CTD-first fallback, because no unique CTD refined-mask component matched within threshold.
- Cleanup route: MIMO locator + `gpt-image-2` transparent masked edit.

## Code Contract Update

`photoshop-manifest.json` now preserves page-level `repair_sources` for synthesized repaired images. This matters when a cleanup route already contains final translated text, because the editable text layer is intentionally skipped and the only Photoshop-visible result is the page-level `修复图像` layer.

Each `repair_sources` entry records:

- `record_id`
- `bbox_xyxy`
- `cleanup_method`
- `replacement_method`
- `effective_method`
- `effective_crop_path`
- `text_overlay_required`

The Phase 8 report now counts page-level repaired image sources so direct replacement records do not disappear from the cleanup summary.

## Real Export Run

Command:

```powershell
python experiments/phase8_photoshop_export.py --detection-run-dir "outputs/runs/phase2-6-ctd-first-gbc06-17-3-gpt-point-v1/runs/phase2-cta-mask" --font-selection-run-dir "outputs/runs/phase3-gbc06-17-3-mimo-font-selection-target-fix-v2" --layout-run-dir "outputs/runs/phase4-gbc06-17-3-layout-target-fix-v4" --cleanup-run-dir "outputs/runs/phase6-ctd-first-gbc06-17-3-gpt-point-prompt-v1" --output-root outputs/runs --run-id phase8-gbc06-17-3-ctd-first-gpt-direct-ps-contract-v2 --sample-limit 1
```

Artifacts:

- Export run: `outputs/runs/phase8-gbc06-17-3-ctd-first-gpt-direct-ps-contract-v2`
- Manifest: `outputs/runs/phase8-gbc06-17-3-ctd-first-gpt-direct-ps-contract-v2/photoshop-manifest.json`
- JSX: `outputs/runs/phase8-gbc06-17-3-ctd-first-gpt-direct-ps-contract-v2/photoshop-import.jsx`
- Repaired page: `outputs/runs/phase8-gbc06-17-3-ctd-first-gpt-direct-ps-contract-v2/repaired_pages/GBC06-17-png.png`
- Report: `outputs/runs/phase8-gbc06-17-3-ctd-first-gpt-direct-ps-contract-v2/reports/phase8-report.md`

Manifest summary:

- `record_count=0`
- `page_count=1`
- `pages[0].layers=[]`
- `pages[0].repaired_image_path=outputs/runs/phase8-gbc06-17-3-ctd-first-gpt-direct-ps-contract-v2/repaired_pages/GBC06-17-png.png`
- `pages[0].repair_sources[0].effective_method=gpt_image2_masked_edit`
- `pages[0].repair_sources[0].text_overlay_required=false`

Image probe:

- Repaired image size: `1440x2048`
- Target-area changed pixels versus original: `2484 / 6272`

## Result

The current Phase 8 exporter now satisfies the direct replacement PSD structure for this sample:

1. `photoshop-import.jsx` reads the project manifest, not the LabelPlus txt.
2. The PSD import should place the page-level repaired bitmap as `修复图像` above `原图`.
3. No editable `嵌字图层*` is emitted for `GBC06_17.png#3`, because the `gpt-image-2` replacement crop already contains final translated text.
4. The source of the repaired bitmap remains auditable through `repair_sources`.

Photoshop itself was not executed in this run; the validation is manifest-level plus generated bitmap inspection.
