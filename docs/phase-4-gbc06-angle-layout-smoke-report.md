# Phase 4 GBC06 Angle-Aware Layout Smoke Report

## Commands

Generate an angle-aware layout preview from Phase 3 font selection and Phase 5 angle estimation:

```powershell
python experiments/phase4_layout_search.py --selection-run-dir outputs/runs/phase3-gbc06-mimo-font-smoke --angle-run-dir outputs/runs/phase5-gbc06-orientation-angle-smoke --run-id phase4-gbc06-angle-layout-smoke --sample-limit 1
```

Generate a full-page preview that consumes the angle-aware layout overlay:

```powershell
python experiments/phase7_page_preview.py --detection-run-dir outputs/runs/phase2-gbc06-smoke --cleanup-run-dir outputs/runs/phase6-gbc06-bubble-smoke --layout-run-dir outputs/runs/phase4-gbc06-angle-layout-smoke --run-id phase7-gbc06-angle-page-preview-smoke --sample-limit 1
```

## Output

Layout run directory:

```text
outputs/runs/phase4-gbc06-angle-layout-smoke
```

Page preview run directory:

```text
outputs/runs/phase7-gbc06-angle-page-preview-smoke
```

Generated artifacts:

- `outputs/runs/phase4-gbc06-angle-layout-smoke/layout-results.jsonl`
- `outputs/runs/phase4-gbc06-angle-layout-smoke/debug/layout_candidates/GBC06-01-png-1.png`
- `outputs/runs/phase4-gbc06-angle-layout-smoke/reports/phase4-report.md`
- `outputs/runs/phase7-gbc06-angle-page-preview-smoke/preview-results.jsonl`
- `outputs/runs/phase7-gbc06-angle-page-preview-smoke/pages/GBC06-01-png.png`

## Result Summary

- Font selection source: `outputs/runs/phase3-gbc06-mimo-font-smoke/font-selections.jsonl`
- Angle source: `outputs/runs/phase5-gbc06-orientation-angle-smoke/angle-results.jsonl`
- Record: `GBC06_01.png#1`
- Selected font: `font-07af2e938e0c`
- Layout status: `layout_generated`
- Layout orientation: `horizontal`
- Layout angle: `-10.4`
- Font size: `72`
- Target size: `375 x 342`
- Measured text: `361 x 69`
- Overflow ratio: `0.0`
- Layout preview: `outputs/runs/phase4-gbc06-angle-layout-smoke/debug/layout_candidates/GBC06-01-png-1.png`
- Layout preview image: `375 x 342`, `RGBA`, non-empty
- Page preview: `outputs/runs/phase7-gbc06-angle-page-preview-smoke/pages/GBC06-01-png.png`
- Page preview image: `1440 x 2048`, `RGB`, non-empty

The layout JSONL row is:

```json
{
  "record_id": "GBC06_01.png#1",
  "image_name": "GBC06_01.png",
  "translated_text": "街头演出？",
  "status": "layout_generated",
  "selected_font_id": "font-07af2e938e0c",
  "layout": {
    "status": "ok",
    "text": "街头演出？",
    "line_breaks": "街头演出？",
    "font_size": 72,
    "orientation": "horizontal",
    "line_spacing": 4,
    "letter_spacing": 0,
    "angle_degrees": -10.4,
    "target_width": 375,
    "target_height": 342,
    "measured_width": 361,
    "measured_height": 69,
    "overflow_ratio": 0.0,
    "failure_reason": null,
    "preview_path": "outputs\\runs\\phase4-gbc06-angle-layout-smoke\\debug\\layout_candidates\\GBC06-01-png-1.png",
    "validation": {
      "status": "deterministic_only",
      "checks": ["measured_text_bbox", "bounded_overflow"],
      "model_summary": null,
      "manual_review_required": true
    }
  }
}
```

## Interpretation

Phase 4 can now optionally consume Phase 5 angle output. When `--angle-run-dir` is provided, the layout search uses `detected_orientation` and writes `selected_angle_degrees` into `layout.angle_degrees`; `render_layout_preview` then rotates the transparent text layer before writing the overlay PNG. Phase 7 can consume that rotated overlay without further changes.

This connects the Phase 5 orientation/angle experiment to the preview chain:

1. Phase 2 detects the source text region.
2. Phase 5 estimates orientation and angle from the detected crop.
3. Phase 4 uses the estimated orientation/angle while generating the text overlay.
4. Phase 6 provides the cleaned crop.
5. Phase 7 pastes the cleaned crop and rotated overlay into the full page.

## Limitations

- The angle remains a deterministic CV estimate and is not yet selected or approved by a vision model.
- The current first GBC06 detection bbox is oversized, so the `-10.4` angle is useful for exercising the pipeline but still needs manual inspection.
- The rotated overlay is clipped to the original target bbox. This keeps page composition stable, but severe rotations or tight text boxes may need expanded placement logic later.
- Phase 4 validation still records `deterministic_only`; the MIMO validation path remains unresolved.

## Verification

```powershell
python -m pytest tests/test_phase4_layout.py tests/test_phase5_orientation.py -q
python -m pytest -q
```

Fresh results before this report was written:

```text
13 passed in 0.79s
43 passed in 1.61s
```

## Notes

- Generated `outputs/` are ignored by Git; this report records the reproducible commands and aggregate result.
