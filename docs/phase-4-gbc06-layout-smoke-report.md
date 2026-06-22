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
- `layout.alignment` fields inside `layout-results.jsonl`

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
- Alpha ink bbox after visible-ink recentering: `[23, 136, 351, 205]`
- Alpha ink size: `328 x 69`
- Alpha ink center offset: `-0.5px` horizontal, `-0.5px` vertical
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
- measures the rendered alpha channel bbox and recenters the visible ink within the target canvas
- records `canvas_width`, `canvas_height`, `ink_bbox`, `ink_width`, `ink_height`, `horizontal_center_offset_px`, and `vertical_center_offset_px`
- marks validation as `deterministic_only`

This iteration adds a traceable alignment metric because the previous MIMO validation said the text was vertically centered but not horizontally centered. The root cause was that Pillow's font measurement box was centered, while the visible alpha ink was still left-biased. Before the visible-ink correction, the same smoke record measured `horizontal_center_offset_px = -16.5`; after correction it measures `-0.5`.

Current limitations:

- Vertical text is implemented for simple per-character stacking, but Japanese/Chinese punctuation rotation and multi-column vertical layout are not implemented yet.
- `angle_degrees` is fixed at `0`.
- MIMO naturalness validation is run in the paired Phase 4 validation smoke report.
- The target size in this smoke run is now read from the Phase 3 source text crop dimensions, which were produced from the Phase 2 selected text box.
- `manual_review_required` remains `true`.

The current real smoke record still selects `horizontal` because its source crop is not tall and narrow enough for the deterministic vertical rule. The next iteration should add vision-model validation and richer vertical punctuation/multi-column behavior.

## Follow-up: Short Vertical Translation Cap

The `GBC06_02.png#7-#9` expansion exposed a deterministic search weakness on short vertical translations. For `GBC06_02.png#8`, the translated text is only `循环器`, so the previous search accepted a larger font size by filling the target height instead of preserving the source glyph column width. The v1 integrated preview was still marked usable by MIMO, but the per-record assessment called the text significantly oversized and outside the original text area.

The follow-up fix caps short vertical translations using the detected source column width with a conservative multiplier. Longer vertical translations keep the existing wider multiplier so multi-column text can still use the available region.

Evidence:

```text
v1 layout for GBC06_02.png#8: font_size=43 measured_height=127
v2 layout for GBC06_02.png#8: font_size=38 measured_height=114
v2 integrated MIMO score: 9
v2 per-record scores: #7=9, #8=9, #9=9
best contact sheet: outputs/runs/phase7-8-gbc06-02-batch-7-9-preview-v2/runs/phase7-preview/debug/evaluation_contact_sheets/GBC06-02-png.png
```

## Verification

Fresh verification before this report was written:

```text
python -m pytest tests/test_phase4_layout.py -q
10 passed in 0.93s

python -m pytest -q
69 passed in 3.96s

git diff --check
passed

AST length gate
passed

diff secret scan
passed
```

## Notes

- This phase does not call MIMO or GPT image APIs.
- Generated `outputs/` are ignored by Git; this report records the reproducible command and aggregate result.
