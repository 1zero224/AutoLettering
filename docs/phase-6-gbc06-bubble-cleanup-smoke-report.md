# Phase 6 GBC06 Bubble Cleanup Smoke Report

## Command

```powershell
python experiments/phase6_bubble_cleanup.py --detection-run-dir outputs/runs/phase2-gbc06-smoke --layout-run-dir outputs/runs/phase4-gbc06-layout-smoke --run-id phase6-gbc06-bubble-smoke --sample-limit 1
```

## Output

Run directory:

```text
outputs/runs/phase6-gbc06-bubble-smoke
```

Generated artifacts:

- `cleanup-results.jsonl`
- `crops/before/*.png`
- `crops/cleaned/*.png`
- `crops/before_after/*.png`
- `reports/phase6-report.md`

## Result Summary

- Detection source: `outputs/runs/phase2-gbc06-smoke/detections.jsonl`
- Layout source: `outputs/runs/phase4-gbc06-layout-smoke/layout-results.jsonl`
- Records processed: 1
- Cleaned: 1
- Skipped: 0
- Record: `GBC06_01.png#1`
- Group: `框内`
- Method: `bubble_fill`
- Text bbox: `[674, 0, 1049, 342]`
- Fill color: `[253, 253, 253]`
- Before crop: `outputs/runs/phase6-gbc06-bubble-smoke/crops/before/GBC06-01-png-1.png`
- Cleaned crop: `outputs/runs/phase6-gbc06-bubble-smoke/crops/cleaned/GBC06-01-png-1.png`
- Before/after crop: `outputs/runs/phase6-gbc06-bubble-smoke/crops/before_after/GBC06-01-png-1.png`

## Interpretation

This phase is a deterministic bubble-text cleanup prototype.

The current method:

- joins Phase 2 detection rows with Phase 4 layout rows by `record_id`
- runs only on `group_name == "框内"`
- samples the local border around the detected text box
- fills the selected text box with the median border color
- saves before, cleaned, and before/after crop artifacts

This does not attempt non-bubble inpainting yet and does not call MIMO or GPT image APIs.

## Limitations

- The method fills the full selected text bbox. If Phase 2 over-selects speech bubble content, this can erase more than just source text.
- It assumes bubble backgrounds are approximately flat and light.
- It does not yet compose the cleaned crop back into a full-page preview.
- It does not validate text removal with a vision model.

## Verification

```powershell
python -m pytest -q
```

Fresh result before this report was written:

```text
33 passed in 1.19s
```

## Notes

- Generated `outputs/` are ignored by Git; this report records the reproducible command and aggregate result.
