# Phase 7 GBC06 Page Preview Smoke Report

## Command

```powershell
python experiments/phase7_page_preview.py --detection-run-dir outputs/runs/phase2-gbc06-smoke --cleanup-run-dir outputs/runs/phase6-gbc06-bubble-smoke --layout-run-dir outputs/runs/phase4-gbc06-layout-smoke --run-id phase7-gbc06-page-preview-smoke --sample-limit 1
```

## Output

Run directory:

```text
outputs/runs/phase7-gbc06-page-preview-smoke
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
- Record: `GBC06_01.png#1`
- Page preview: `outputs/runs/phase7-gbc06-page-preview-smoke/pages/GBC06-01-png-1.png`
- Preview image size: `1440 x 2048`
- Text bbox: `[674, 0, 1049, 342]`
- Cleanup method: `bubble_fill`
- Layout preview: `outputs/runs/phase4-gbc06-layout-smoke/debug/layout_candidates/GBC06-01-png-1.png`

## Interpretation

This is the first complete local preview chain:

1. Phase 2 detects a source-text region.
2. Phase 3 selects a candidate font through the model-backed font experiment.
3. Phase 4 searches a deterministic layout and renders a transparent text preview.
4. Phase 6 fills the detected source-text region for a bubble record.
5. Phase 7 pastes the cleaned crop and text overlay back into the original page.

This creates a full-page preview image that can be inspected manually.

## Limitations

- The preview contains only one processed record.
- If Phase 2 over-selects the text region, Phase 6 and Phase 7 will erase/paste over the same oversized region.
- Phase 4 layout validation with MIMO currently records `invalid_json`; the preview is not model-approved.
- The composition handles one record at a time in this first prototype; same-page multi-record batching still needs follow-up.
- This does not create Photoshop layers or export a Photoshop intermediate format yet.

## Verification

```powershell
python -m pytest -q
```

Fresh result before this report was written:

```text
35 passed in 1.26s
```

## Notes

- Generated `outputs/` are ignored by Git; this report records the reproducible command and aggregate result.
