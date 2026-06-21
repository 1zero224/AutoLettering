# Phase 8 GBC06 Photoshop Export Smoke Report

## Command

```powershell
python experiments/phase8_photoshop_export.py --detection-run-dir outputs/runs/phase2-gbc06-smoke --font-selection-run-dir outputs/runs/phase3-gbc06-mimo-font-smoke --layout-run-dir outputs/runs/phase4-gbc06-angle-layout-smoke --cleanup-run-dir outputs/runs/phase6-gbc06-bubble-smoke --run-id phase8-gbc06-photoshop-export-smoke --sample-limit 1
```

## Output

Run directory:

```text
outputs/runs/phase8-gbc06-photoshop-export-smoke
```

Generated artifacts:

- `photoshop-manifest.json`
- `photoshop-import.jsx`
- `reports/phase8-report.md`

## Result Summary

- Detection source: `outputs/runs/phase2-gbc06-smoke/detections.jsonl`
- Font selection source: `outputs/runs/phase3-gbc06-mimo-font-smoke/font-selections.jsonl`
- Layout source: `outputs/runs/phase4-gbc06-angle-layout-smoke/layout-results.jsonl`
- Cleanup source: `outputs/runs/phase6-gbc06-bubble-smoke/cleanup-results.jsonl`
- Schema: `autolettering.photoshop.v1`
- Pages exported: 1
- Text layers exported: 1
- Manifest size: `2593` bytes
- JSX size: `2418` bytes

Exported page and layer:

- Page: `GBC06_01.png`
- Page size: `1440 x 2048`
- Record: `GBC06_01.png#1`
- Text: `街头演出？`
- Layer name: `AL GBC06_01.png#1`
- Bbox: `[674, 0, 1049, 342]`
- Font: `[toolbox]WenHei-JF-Bold`
- Font size: `72`
- Orientation: `horizontal`
- Angle: `-10.4`
- Cleanup method: `bubble_fill`
- Validation: `deterministic_only`

The manifest layer stores the Photoshop-relevant fields:

```json
{
  "record_id": "GBC06_01.png#1",
  "layer_name": "AL GBC06_01.png#1",
  "text": "街头演出？",
  "bbox": {
    "x": 674,
    "y": 0,
    "width": 375,
    "height": 342,
    "xyxy": [674, 0, 1049, 342]
  },
  "font": {
    "font_id": "font-07af2e938e0c",
    "family_name": "[toolbox]WenHei-JF-Bold"
  },
  "layout": {
    "font_size": 72,
    "orientation": "horizontal",
    "angle_degrees": -10.4,
    "line_spacing": 4,
    "letter_spacing": 0
  },
  "cleanup": {
    "status": "cleaned",
    "method": "bubble_fill"
  },
  "validation": {
    "status": "deterministic_only"
  }
}
```

## JSX Behavior

`photoshop-import.jsx` is designed to be placed next to `photoshop-manifest.json`. When run inside Photoshop, it should:

1. Read `photoshop-manifest.json` from the script directory.
2. Open each source image listed in the manifest.
3. Create one editable Photoshop text layer per exported layer.
4. Set text contents, font size, font family when Photoshop can resolve it, direction, pixel position, and rotation angle.
5. Save PSD files under a sibling `psd/` folder.

This follows the existing `PS-Script/src/importer.ts` model of creating Photoshop `LayerKind.TEXT` layers, but uses a richer project manifest instead of the old LabelPlus txt format.

## Limitations

- Photoshop is not available in this environment, so the JSX was not executed inside Photoshop.
- Photoshop font lookup uses `family_name` and may require manual font mapping if Photoshop expects a different PostScript font name.
- The script currently creates editable text layers only; it does not yet recreate cleaned bitmap patches as separate Photoshop layers.
- Text position uses the detected bbox top-left as the initial anchor. Photoshop text baseline behavior may require manual adjustment for production use.
- The export covers one real aligned record because upstream font/layout/cleanup runs currently cover one record.

## Verification

```powershell
python -m pytest tests/test_phase8_photoshop_export.py -q
python -m pytest -q
```

Fresh result before this report was written:

```text
2 passed in 0.18s
45 passed in 2.62s
```

## Notes

- Generated `outputs/` are ignored by Git; this report records the reproducible command and exported manifest summary.
