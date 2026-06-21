# Phase 1 GBC06 Smoke Report

## Command

```powershell
python experiments/phase1_parse_sample.py --labelplus-file "GBC06 (已翻 斗笠)\翻译_0.txt" --run-id phase1-gbc06-smoke --sample-limit 30
```

## Output

Run directory:

```text
outputs/runs/phase1-gbc06-smoke
```

Generated artifacts:

- `manifest.json`
- `debug/label_points/*.png`
- `samples/phase1-sample.jsonl`
- `reports/phase1-report.md`

## Result Summary

- Available images: 19
- Missing images: 14
- Labels on available images: 180
- Labels on missing images: 88
- Total labels declared: 268
- Sample JSONL records: 30
- Label-point debug images: 19

## Missing Images

The LabelPlus text declares pages that are not present in the local sample image directory:

- `GBC06_08.png`: page 8, 8 labels
- `GBC06_09.png`: page 9, 8 labels
- `GBC06_10.png`: page 10, 11 labels
- `GBC06_11.png`: page 11, 11 labels
- `GBC06_12.png`: page 12, 6 labels
- `GBC06_13.png`: page 13, 14 labels
- `GBC06_23.png`: page 23, 4 labels
- `GBC06_24.png`: page 24, 5 labels
- `GBC06_25.png`: page 25, 1 label
- `GBC06_26.png`: page 26, 1 label
- `GBC06_27.png`: page 27, 1 label
- `GBC06_28.png`: page 28, 9 labels
- `GBC06_31.png`: page 31, 2 labels
- `GBC06_32.png`: page 32, 7 labels

## Verification

```powershell
python -m pytest -q
```

Result:

```text
5 passed in 0.33s
```

## Notes

- This phase does not call MIMO or GPT image APIs.
- Generated `outputs/` are ignored by Git; this report records the reproducible command and aggregate result.
