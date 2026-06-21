# Phase 2 GBC06 Smoke Report

## Command

```powershell
python experiments/phase2_detect_text_regions.py --labelplus-file "GBC06 (已翻 斗笠)\翻译_0.txt" --run-id phase2-gbc06-smoke --sample-limit 30 --radius-x 220 --radius-y 180
```

## Output

Run directory:

```text
outputs/runs/phase2-gbc06-smoke
```

Generated artifacts:

- `detections.jsonl`
- `debug/detection/*.png`
- `reports/phase2-report.md`

## Result Summary

- Sample records: 30
- Records with at least one selected candidate: 30
- Failed records: 0
- Search radius: `220 x 180`

## Interpretation

This phase is a deterministic CV prototype, not a final-quality text detector.

The current method:

- builds a fixed search window around each LabelPlus point
- thresholds dark pixels
- expands nearby dark regions with a max filter
- finds connected components
- scores candidates by distance to the LabelPlus point and ink density
- saves every selected region and candidate overlay for human inspection

The `30/30` result means the prototype produced a candidate region for every sampled record. It does not mean every selected box is semantically correct. The next iteration should add visual/manual review fields and improve candidate scoring with text-shape constraints.

## Verification

```powershell
python -m pytest -q
```

Result:

```text
9 passed in 0.41s
```

## Notes

- This phase does not call MIMO or GPT image APIs.
- Generated `outputs/` are ignored by Git; this report records the reproducible command and aggregate result.
