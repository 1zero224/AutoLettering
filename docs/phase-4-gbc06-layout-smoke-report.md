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
- Selected font: `font-07af2e938e0c`
- Orientation: `horizontal`
- Font size: 72
- Line breaks: `街头演出？`
- Target size: `375 x 342`
- Measured text size: `361 x 69`
- Overflow ratio: `0.0`
- Preview: `outputs/runs/phase4-gbc06-layout-smoke/debug/layout_candidates/GBC06-01-png-1.png`

## Interpretation

This phase is a deterministic layout-search prototype.

The current method:

- reads selected fonts from the Phase 3 MIMO font-selection run
- chooses `vertical` when the target crop is tall and narrow, otherwise `horizontal`
- generates simple balanced line-break candidates
- searches from larger to smaller font sizes
- measures rendered text with Pillow
- accepts the first layout whose measured text box fits the target area
- renders a transparent preview PNG
- marks validation as `deterministic_only`

Current limitations:

- Vertical text is implemented for simple per-character stacking, but Japanese/Chinese punctuation rotation and multi-column vertical layout are not implemented yet.
- `angle_degrees` is fixed at `0`.
- MIMO naturalness validation is not run yet.
- The target size in this smoke run is now read from the Phase 3 source text crop dimensions, which were produced from the Phase 2 selected text box.
- `manual_review_required` remains `true`.

The current real smoke record still selects `horizontal` because its source crop is not tall and narrow enough for the deterministic vertical rule. The next iteration should add vision-model validation and richer vertical punctuation/multi-column behavior.

## Verification

```powershell
python -m pytest -q
```

Fresh result before this report was written:

```text
25 passed in 1.13s
```

## Notes

- This phase does not call MIMO or GPT image APIs.
- Generated `outputs/` are ignored by Git; this report records the reproducible command and aggregate result.
