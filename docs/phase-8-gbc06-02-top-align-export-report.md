# Phase 8 GBC06_02 Top-Align Photoshop Export Report

## Context

The Phase 4 layout pipeline now renders manga-style vertical text with `vertical_align=top`.
This follow-up checks the Phase 8 Photoshop export path, because editable Photoshop layers are generated from `photoshop-manifest.json` and could otherwise lose the top-anchor layout intent.

## Command

```powershell
python experiments/phase8_photoshop_export.py --detection-run-dir outputs/runs/phase2-gbc06-smoke-v3 --font-selection-run-dir outputs/runs/phase3-gbc06-02-batch-10-13-mimo-font-selection --layout-run-dir outputs/runs/phase4-gbc06-02-batch-10-13-layout-v9-top-align --cleanup-run-dir outputs/runs/phase6-gbc06-02-batch-10-13-region-fill-v9-top-align --run-id phase8-gbc06-02-batch-10-13-top-align-export-v1 --sample-limit 4
```

## Output

Run directory:

```text
outputs/runs/phase8-gbc06-02-batch-10-13-top-align-export-v1
```

Generated artifacts:

- `photoshop-manifest.json`
- `photoshop-import.jsx`
- `reports/phase8-report.md`
- `reports/photoshop-validation-checklist.md`

## Manifest Evidence

The export kept the top-aligned vertical layout metadata for all four sampled records:

```text
GBC06_02.png#10 orientation=vertical angle=0.0 vertical_align=top anchor_y=1215 text_bbox=[343, 1215, 381, 1302]
GBC06_02.png#11 orientation=vertical angle=0.0 vertical_align=top anchor_y=1158 text_bbox=[157, 1158, 230, 1347]
GBC06_02.png#12 orientation=vertical angle=0.0 vertical_align=top anchor_y=1428 text_bbox=[1191, 1428, 1303, 1587]
GBC06_02.png#13 orientation=vertical angle=0.0 vertical_align=top anchor_y=1822 text_bbox=[899, 1822, 972, 1918]
```

Summary:

```text
record_count=4
page_count=1
```

## JSX Behavior

The manifest now derives `photoshop.vertical_top_anchor_y_px` from records where `layout.orientation=vertical` and `layout.vertical_align=top`.
`photoshop-import.jsx` reads that Photoshop-specific field, appends `vertical_align=top` to the layer name for manual inspection, and calls `applyVerticalTopAnchor()` after optional rotation.
That helper attempts to move the rendered layer bounds top to the exported anchor y coordinate, so the editable Photoshop layer no longer relies only on Photoshop's default paragraph baseline behavior.

This is intentionally conservative. The export preserves the layout intent and validation checklist, but it does not claim exact Photoshop raster parity without running Photoshop locally.

## Result

- Programmatic preview source: `outputs/runs/phase4-gbc06-02-batch-10-13-layout-v9-top-align`
- Preview quality already checked by MIMO in the related Phase 7/8 report: score `9`, usable `true`
- Phase 8 export now carries the same `vertical_align=top` intent into the manifest, JSX behavior, and validation checklist
- All four sampled records keep `angle_degrees=0.0`, so upright vertical text is not given a small accidental rotation

## Limitations

- Photoshop was not executed in this environment.
- The JSX creates editable paragraph text layers and applies a rendered-bounds top translation for vertical `vertical_align=top` layers, but final PSD baseline behavior still requires manual Photoshop inspection.
- Generated `outputs/` are ignored by Git; this report records the reproducible command and manifest evidence.

## Verification

```powershell
python -m pytest tests/test_phase8_photoshop_export.py tests/test_phase8_photoshop_export_alignment.py -q
```

Fresh result before this report was written:

```text
6 passed in 0.42s
```
