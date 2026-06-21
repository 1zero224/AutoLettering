# Phase 7 GBC06 Page Preview Smoke Report

## Command

```powershell
python experiments/phase7_page_preview.py --detection-run-dir outputs/runs/phase2-gbc06-smoke --cleanup-run-dir outputs/runs/phase6-gbc06-bubble-smoke --layout-run-dir outputs/runs/phase4-gbc06-layout-smoke --run-id phase7-gbc06-page-group-preview-smoke --sample-limit 1
```

## Output

Run directory:

```text
outputs/runs/phase7-gbc06-page-group-preview-smoke
```

Generated artifacts:

- `preview-results.jsonl`
- `pages/*.png`
- `reports/phase7-report.md`

## Result Summary

- Detection source: `outputs/runs/phase2-gbc06-smoke/detections.jsonl`
- Cleanup source: `outputs/runs/phase6-gbc06-bubble-smoke/cleanup-results.jsonl`
- Layout source: `outputs/runs/phase4-gbc06-layout-smoke/layout-results.jsonl`
- Records processed: 1
- Page previews generated: 1
- Skipped: 0
- Image: `GBC06_01.png`
- Records on page: `GBC06_01.png#1`
- Page preview: `outputs/runs/phase7-gbc06-page-group-preview-smoke/pages/GBC06-01-png.png`
- Preview image size: `1440 x 2048`
- Text bbox: `[674, 0, 1049, 342]`
- Cleanup method: `bubble_fill`
- Layout preview: `outputs/runs/phase4-gbc06-layout-smoke/debug/layout_candidates/GBC06-01-png-1.png`

The page-level JSONL row is now grouped by image:

```json
{
  "image_name": "GBC06_01.png",
  "status": "page_preview_generated",
  "records": [
    {
      "record_id": "GBC06_01.png#1",
      "bbox": [674, 0, 1049, 342],
      "cleanup_method": "bubble_fill",
      "layout_preview_path": "outputs\\runs\\phase4-gbc06-layout-smoke\\debug\\layout_candidates\\GBC06-01-png-1.png"
    }
  ],
  "preview": {
    "page_preview_path": "outputs\\runs\\phase7-gbc06-page-group-preview-smoke\\pages\\GBC06-01-png.png",
    "record_count": 1
  }
}
```

## Interpretation

This is the first complete local preview chain:

1. Phase 2 detects a source-text region.
2. Phase 3 selects a candidate font through the model-backed font experiment.
3. Phase 4 searches a deterministic layout and renders a transparent text preview.
4. Phase 6 fills the detected source-text region for a bubble record.
5. Phase 7 groups valid records by source page, then pastes each cleaned crop and text overlay back into the original page canvas.

This creates one inspectable full-page preview per processed source image. Synthetic tests cover multiple records on the same page; the current GBC06 smoke still uses one real record because the upstream Phase 3/4/6 runs only contain one aligned record.
Records missing matching detection or layout rows are kept as `skipped` rows with a failure reason instead of being silently dropped.

## Limitations

- The real preview contains only one processed record because upstream font/layout/cleanup results currently cover one aligned record.
- If Phase 2 over-selects the text region, Phase 6 and Phase 7 will erase/paste over the same oversized region.
- Phase 4 layout validation with MIMO currently records `invalid_json`; the preview is not model-approved.
- Page-level composition is implemented, but it still depends on upstream phases producing matching detection, cleanup, and layout rows for every record.
- This does not create Photoshop layers or export a Photoshop intermediate format yet.

## Verification

```powershell
python -m pytest -q
```

Fresh result before this report was written:

```text
36 passed in 1.41s
```

## Notes

- Generated `outputs/` are ignored by Git; this report records the reproducible command and aggregate result.
