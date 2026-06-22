# Phase 8 GBC06_02 Top-Align Export Quality Audit Report

## Context

The pipeline coverage report can prove that records reached Phase 8, but it only counts exported Photoshop layers.
It does not prove that vertical top-aligned text layers carry the Photoshop-specific anchor fields needed by `photoshop-import.jsx`.

This audit closes that gap for the current `GBC06_02.png#10-#13` top-align export.

## Command

```powershell
python experiments/phase8_export_quality_audit.py --phase8-run-dir outputs/runs/phase8-gbc06-02-batch-10-13-top-align-export-v1 --run-id phase8-gbc06-02-batch-10-13-top-align-export-audit-v1
```

## Output

Run directory:

```text
outputs/runs/phase8-gbc06-02-batch-10-13-top-align-export-audit-v1
```

Generated artifacts:

- `phase8-export-audit.json`
- `reports/phase8-export-audit-report.md`

## Result Summary

```text
record_count=4
vertical_top_layer_count=4
missing_vertical_top_anchor_count=0
unexpected_vertical_top_anchor_count=0
record_issue_count=0
jsx_anchor_logic_present=true
passed=true
```

Record evidence:

```text
GBC06_02.png#10 orientation=vertical vertical_align=top text_position_y_px=1215 vertical_top_anchor_y_px=1215 issues=[]
GBC06_02.png#11 orientation=vertical vertical_align=top text_position_y_px=1158 vertical_top_anchor_y_px=1158 issues=[]
GBC06_02.png#12 orientation=vertical vertical_align=top text_position_y_px=1428 vertical_top_anchor_y_px=1428 issues=[]
GBC06_02.png#13 orientation=vertical vertical_align=top text_position_y_px=1822 vertical_top_anchor_y_px=1822 issues=[]
```

## Interpretation

This is a stricter Phase 8 check than structural pipeline coverage.
For every audited layer, the manifest now proves:

- `layout.orientation=vertical`
- `layout.vertical_align=top`
- `photoshop.vertical_top_anchor_y_px` exists
- the anchor y matches `text_position.y_px`
- the JSX contains the expected anchor logic (`applyVerticalTopAnchor`, `vertical_top_anchor_y_px`, `moveLayerTop`)

The audit still does not execute Photoshop locally. It verifies the exported manifest and JSX contract that Photoshop will consume.

## Verification

```powershell
python -m pytest tests/test_phase8_export_quality_audit.py -q
```

Fresh result before this report was written:

```text
2 passed in 0.14s
```
