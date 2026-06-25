# Phase 8 GBC06_33 Context-Font Photoshop Export Report

## Scope

This run verifies the Photoshop export contract for the latest
context-selected red side banner experiment.

- Record: `GBC06_33.png#1`
- Target text: `漫画第一卷\n2026年6月29日发售！！`
- Detection run: `outputs/runs/phase2-gbc06-33-1-cta-contract-v1`
- Font selection run: `outputs/runs/phase3-gbc06-33-1-context-font-mimo-v1`
- Layout run: `outputs/runs/phase4-gbc06-33-1-context-font-layout-v1`
- Cleanup run: `outputs/runs/phase6-gbc06-33-1-gpt-background-real-v1`
- Preview run: `outputs/runs/phase7-gbc06-33-1-context-font-preview-v1`

The user-facing PSD target is:

```text
嵌字图层1
修复图像
原图
```

For multi-record pages, additional editable text layers should appear above
`修复图像` in numbered order.

## Export Command

```powershell
python experiments/phase8_photoshop_export.py --detection-run-dir outputs/runs/phase2-gbc06-33-1-cta-contract-v1 --font-selection-run-dir outputs/runs/phase3-gbc06-33-1-context-font-mimo-v1 --layout-run-dir outputs/runs/phase4-gbc06-33-1-context-font-layout-v1 --cleanup-run-dir outputs/runs/phase6-gbc06-33-1-gpt-background-real-v1 --preview-run-dir outputs/runs/phase7-gbc06-33-1-context-font-preview-v1 --output-root outputs/runs --run-id phase8-gbc06-33-1-context-font-export-v1 --sample-limit 1
```

Output run:

```text
outputs/runs/phase8-gbc06-33-1-context-font-export-v1
```

Generated artifacts:

- `photoshop-manifest.json`
- `photoshop-import.jsx`
- `reports/phase8-report.md`
- `reports/photoshop-validation-checklist.md`

## Manifest Evidence

Summary:

```json
{
  "record_count": 1,
  "page_count": 1
}
```

Page-level contract:

```json
{
  "image_name": "GBC06_33.png",
  "repaired_image_path": "outputs\\runs\\phase7-gbc06-33-1-context-font-preview-v1\\pages\\cleaned\\GBC06-33-png.png",
  "layer_order": ["text_layers", "repaired_image", "original_image"],
  "layer_count": 1
}
```

Editable text layer:

```json
{
  "record_id": "GBC06_33.png#1",
  "text_layer_name": "嵌字图层1",
  "font_id": "font-480b676e6b6a",
  "photoshop_font_name": "toolboxYuMoGB-Medium",
  "font_confidence": 0.95,
  "orientation": "vertical",
  "vertical_align": "top",
  "angle_degrees": 0.0,
  "font_size": 54,
  "line_spacing": 20,
  "letter_spacing": 0,
  "text_color": [255, 255, 255, 255],
  "text_bbox": [1156, 371, 1298, 1925],
  "vertical_top_anchor_y_px": 371
}
```

Repair provenance:

```json
{
  "record_id": "GBC06_33.png#1",
  "bbox_xyxy": [1156, 371, 1298, 1925],
  "cleanup_method": "gpt_image2_background_repair",
  "effective_method": "gpt_image2_background_repair",
  "effective_crop_path": "outputs\\runs\\phase6-gbc06-33-1-gpt-background-real-v1\\background_repair_gpt_normalized\\GBC06-33-png-1.png",
  "text_overlay_required": true
}
```

The export uses the Phase 7 cleaned full page as the single bitmap
`修复图像` layer and keeps one editable Photoshop paragraph text layer above
it. Because a page-level repaired image is available, the JSX is expected to
skip per-record cleanup patch layers.

## Audit Command

```powershell
python experiments/phase8_export_quality_audit.py --phase8-run-dir outputs/runs/phase8-gbc06-33-1-context-font-export-v1 --output-root outputs/runs --run-id phase8-gbc06-33-1-context-font-export-audit-v1
```

Output run:

```text
outputs/runs/phase8-gbc06-33-1-context-font-export-audit-v1
```

Audit summary:

```json
{
  "record_count": 1,
  "vertical_top_layer_count": 1,
  "missing_vertical_top_anchor_count": 0,
  "unexpected_vertical_top_anchor_count": 0,
  "record_issue_count": 0,
  "jsx_anchor_logic_present": true,
  "passed": true
}
```

Record-level audit evidence:

```text
GBC06_33.png#1 orientation=vertical vertical_align=top text_position_y_px=371 vertical_top_anchor_y_px=371 issues=[]
```

## Code Fix

During this export smoke, the Phase 7 cleaned-page path was loaded correctly,
but `repair_sources` were lost when `preview-results.jsonl` overwrote the
same page entry that had already been loaded from the Phase 7 `manifest.json`.

Fix:

- `autolettering/phase8.py` now merges Phase 7 preview-result paths into the
  existing manifest-derived repaired page entry instead of replacing it.
- `_preview_repair_sources()` now recognizes Phase 7 record
  `cleanup_crop_path` as an `effective_crop_path`.

Regression test:

```powershell
python -m pytest tests/test_phase8_photoshop_export.py::test_run_phase8_photoshop_export_preserves_phase7_repair_sources_when_preview_results_exist -q
```

Red result before the fix:

```text
FAILED ... AssertionError: assert [] == [{'record_id': 'page.png#1', ...}]
```

Green result after the fix:

```text
17 passed in 1.45s
```

## Limitations

- Photoshop was not executed in this environment, so PSD creation is still a
  manual validation step.
- The generated JSX contract and manifest prove layer intent, editable text
  parameters, repaired-image placement, and top-anchor metadata. They do not
  prove Photoshop's font resolver will find the exported PostScript name on a
  specific machine.
- `outputs/` artifacts are ignored by Git. This report records the exact
  commands and artifact paths for reproduction.
