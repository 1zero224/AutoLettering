# Phase 4 GBC06 Layout Smoke Report

## Command

```powershell
python experiments/phase4_layout_search.py --selection-run-dir outputs/runs/phase3-gbc06-mimo-font-smoke --run-id phase4-gbc06-layout-smoke --sample-limit 1
```

## Output

Run directory:

```text
outputs/runs/phase4-gbc06-layout-smoke
```

Generated artifacts:

- `layout-results.jsonl`
- `debug/layout_candidates/*.png`
- `reports/phase4-report.md`

## Result Summary

- Selection source: `outputs/runs/phase3-gbc06-mimo-font-smoke/font-selections.jsonl`
- Records processed: 1
- Layouts generated: 1
- Layout failures: 0
- Record: `GBC06_01.png#1`
- Selected font: `font-51a342d311b2`
- Orientation: `horizontal`
- Font size: 72
- Line breaks: `街头演出？`
- Target size: `633 x 129`
- Measured text size: `360 x 67`
- Overflow ratio: `0.0`
- Preview: `outputs/runs/phase4-gbc06-layout-smoke/debug/layout_candidates/GBC06-01-png-1.png`

## Interpretation

This phase is a deterministic layout-search prototype.

The current method:

- reads selected fonts from the Phase 3 MIMO font-selection run
- generates simple balanced line-break candidates
- searches from larger to smaller font sizes
- measures rendered text with Pillow
- accepts the first layout whose measured text box fits the target area
- renders a transparent preview PNG
- marks validation as `deterministic_only`

Current limitations:

- The first prototype only generates horizontal text.
- `angle_degrees` is fixed at `0`.
- MIMO naturalness validation is not run yet.
- The target size in this smoke run is derived from the Phase 3 comparison image dimensions, not the exact Phase 2 detected text bbox.
- `manual_review_required` remains `true`.

The next iteration should feed exact text-region bbox dimensions into Phase 4 and then add vertical layout and vision-model validation.

## Verification

```powershell
python -m pytest -q
```

Fresh result before this report was written:

```text
23 passed in 0.98s
```

## Notes

- This phase does not call MIMO or GPT image APIs.
- Generated `outputs/` are ignored by Git; this report records the reproducible command and aggregate result.
