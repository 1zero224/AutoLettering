# Phase 5 GBC06 Orientation Angle Smoke Report

## Command

```powershell
python experiments/phase5_orientation_angle.py --detection-run-dir outputs/runs/phase2-gbc06-smoke --run-id phase5-gbc06-orientation-angle-smoke --sample-limit 1
```

## Output

Run directory:

```text
outputs/runs/phase5-gbc06-orientation-angle-smoke
```

Generated artifacts:

- `angle-results.jsonl`
- `debug/angle_candidates/*.png`
- `reports/phase5-report.md`

## Result Summary

- Detection source: `outputs/runs/phase2-gbc06-smoke/detections.jsonl`
- Records processed: 1
- Angle estimates: 1
- Failures: 0
- Record: `GBC06_01.png#1`
- Detection bbox: `[674, 0, 1049, 342]`
- Detected orientation: `horizontal`
- Principal axis: `-10.4`
- Estimated angle: `-10.4`
- Candidate angles: `[-20.4, -15.4, -10.4, -5.4, -0.4]`
- Confidence: `0.661`
- Debug grid: `outputs/runs/phase5-gbc06-orientation-angle-smoke/debug/angle_candidates/GBC06-01-png-1.png`
- Debug grid image: `1080 x 190`, `RGB`, non-empty

The JSONL row is:

```json
{
  "record_id": "GBC06_01.png#1",
  "image_name": "GBC06_01.png",
  "translated_text": "街头演出？",
  "group_name": "框内",
  "status": "angle_estimated",
  "orientation": {
    "status": "ok",
    "detected_orientation": "horizontal",
    "principal_axis_degrees": -10.4,
    "estimated_angle_degrees": -10.4,
    "candidate_angles": [-20.4, -15.4, -10.4, -5.4, -0.4],
    "selected_angle_degrees": -10.4,
    "confidence": 0.661,
    "bbox": [674, 0, 1049, 342],
    "tight_bbox": [674, 0, 1045, 342],
    "dark_pixel_count": 57594,
    "failure_reason": null,
    "debug_preview_grid_path": "outputs\\runs\\phase5-gbc06-orientation-angle-smoke\\debug\\angle_candidates\\GBC06-01-png-1.png"
  }
}
```

## Interpretation

Phase 5 now has a deterministic CV prototype for orientation and angle estimation:

1. It reads Phase 2 detection rows.
2. It crops the selected text bbox.
3. It thresholds dark pixels and estimates the principal text axis with PCA.
4. It classifies the region as horizontal or vertical using the tight dark-pixel bbox and axis angle.
5. It outputs a bounded angle estimate, candidate angles around that estimate, and a debug preview grid.

This is a local, reproducible baseline. It does not call a vision model yet, so it is suitable as a cheap first pass and as input to a later model-backed candidate chooser.

## Limitations

- The estimate is only as good as Phase 2's selected bbox. The current first GBC06 bbox is oversized and touches the page top, so the `horizontal` and `-10.4` result should be treated as a coarse CV signal, not a confirmed semantic judgment.
- The current selected angle is the PCA-derived center candidate. There is not yet a visual-model validation loop to choose among candidates.
- Phase 4 layout rendering still uses `angle_degrees = 0`; Phase 5 output is not yet integrated into final text rendering.
- This does not detect curved or multi-axis text, and it does not use OCR or a manga-specific text detector.

## Verification

```powershell
python -m pytest tests/test_phase5_orientation.py -q
```

Fresh result before this report was written:

```text
5 passed in 0.37s
```

## Notes

- Generated `outputs/` are ignored by Git; this report records the reproducible command and aggregate result.
