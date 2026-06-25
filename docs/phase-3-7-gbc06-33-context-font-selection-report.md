# Phase 3/7 Context Font Selection Report

## Scope

This slice tests a context-aware font selection path for the non-bubble red
side banner `GBC06_33.png#1`.

- Record: `GBC06_33.png#1`
- Target text: `漫画第一卷\n2026年6月29日发售！！`
- Text bbox: `[1156, 371, 1298, 1925]`
- Detection run: `outputs/runs/phase2-gbc06-33-1-cta-contract-v1`
- Cleanup run: `outputs/runs/phase6-gbc06-33-1-gpt-background-real-v1`
- Baseline layout: `outputs/runs/phase4-gbc06-33-1-cta-full-layout-v7-tatechuyoko-scaled-spacing20`
- Baseline preview: `outputs/runs/phase7-gbc06-33-1-gpt-background-tatechuyoko-scaled-spacing20-v1`

## Problem

The previous Phase 3 font selection chose
`[toolbox]与墨体-简体-Bold(v2.4).ttf`. It was usable, but the final red banner
looked more rigid than the source Japanese lettering.

The generic Phase 3 comparison sheet was not enough for this decision because
it compared source glyph style against isolated font previews. This experiment
renders each candidate directly into the repaired red banner with the current
Phase 4 layout, then asks MIMO to choose based on the final-looking context.

## Code Changes Under Test

- `autolettering/phase3_context_font_selection.py`
  - Adds a context-aware Phase 3 reranking experiment.
  - Reuses a Phase 4 layout and Phase 6 cleanup crop.
  - Renders each candidate font as a final red-banner crop.
  - Writes Phase 4-compatible `font-selections.jsonl`.
  - Writes enlarged segmented review tiles instead of shrinking the full tall
    banner into unreadable strips.
- `autolettering/phase3_context_font_candidates.py`
  - Keeps candidate merge/filter/sort policy separate from the experiment
    orchestration.
- `autolettering/phase3_context_font_review.py`
  - Builds the readable near-square context font grid.
- `autolettering/phase3_context_font_artifacts.py`
  - Owns JSONL rows, API call summaries, manifest, and run report writing.
- `autolettering/review_tiles.py`
  - Provides reusable enlarged TOP/MIDDLE/BOTTOM segment tiles for tall manga
    crops.
- `experiments/phase3_context_font_selection.py`
  - Adds a dry-run-by-default CLI.
  - Calls MIMO only when `--call-mimo` is passed.
- `autolettering/phase7_evaluate.py`
  - Clarifies that bottom segments can be intentionally blank for top-aligned
    vertical lettering.
- `autolettering/phase7_compare.py`
  - Enlarges tall method-comparison crops by splitting them into ordered
    TOP/MIDDLE/BOTTOM review segments.

## Experiments

### Dry Run: readable context grid

```powershell
python experiments/phase3_context_font_selection.py --font-comparison-run-dir outputs/runs/phase3-gbc06-29-33-font-comparison-v1 --layout-run-dir outputs/runs/phase4-gbc06-33-1-cta-full-layout-v7-tatechuyoko-scaled-spacing20 --cleanup-run-dir outputs/runs/phase6-gbc06-33-1-gpt-background-real-v1 --font-dir "工具箱漫画字体V2.5" --output-root outputs/runs --run-id phase3-gbc06-33-1-context-font-dry-v2 --sample-limit 1 --record-id "GBC06_33.png#1" --candidate-limit 16
```

- Run: `outputs/runs/phase3-gbc06-33-1-context-font-dry-v2`
- Review grid:
  `outputs/runs/phase3-gbc06-33-1-context-font-dry-v2/debug/context_font_grids/GBC06-33-png-1.png`
- Result: the grid is readable. Each tall banner is split into 4 ordered
  segments instead of being compressed into a thin vertical line.
- Refactor verification dry run:
  `outputs/runs/phase3-gbc06-33-1-context-font-dry-v3`

### Real MIMO context font selection

```powershell
python experiments/phase3_context_font_selection.py --font-comparison-run-dir outputs/runs/phase3-gbc06-29-33-font-comparison-v1 --layout-run-dir outputs/runs/phase4-gbc06-33-1-cta-full-layout-v7-tatechuyoko-scaled-spacing20 --cleanup-run-dir outputs/runs/phase6-gbc06-33-1-gpt-background-real-v1 --font-dir "工具箱漫画字体V2.5" --output-root outputs/runs --run-id phase3-gbc06-33-1-context-font-mimo-v1 --sample-limit 1 --record-id "GBC06_33.png#1" --candidate-limit 16 --call-mimo
```

- Run: `outputs/runs/phase3-gbc06-33-1-context-font-mimo-v1`
- MIMO selected: `font-480b676e6b6a`
- Font: `[toolbox]与墨体-简体-Medium(v2.4).ttf`
- Confidence: `0.95`
- MIMO summary: Medium weight best matched the clean, geometric source banner
  without the excessive blockiness of heavier candidates.
- Review grid:
  `outputs/runs/phase3-gbc06-33-1-context-font-mimo-v1/debug/context_font_grids/GBC06-33-png-1.png`
- API summary:
  `outputs/runs/phase3-gbc06-33-1-context-font-mimo-v1/reports/api-calls.jsonl`

### Phase 4 layout with selected Medium font

```powershell
python experiments/phase4_layout_search.py --selection-run-dir outputs/runs/phase3-gbc06-33-1-context-font-mimo-v1 --detection-run-dir outputs/runs/phase2-gbc06-33-1-cta-contract-v1 --output-root outputs/runs --run-id phase4-gbc06-33-1-context-font-layout-v1 --sample-limit 1 --record-id "GBC06_33.png#1"
```

- Run: `outputs/runs/phase4-gbc06-33-1-context-font-layout-v1`
- Font size: `54`
- Line spacing: `20`
- Orientation: `vertical`
- Angle: `0.0`
- Vertical alignment: `top`
- Measured text box: `76 x 943`
- Target box: `142 x 1554`
- Result: no overflow; same top-aligned vertical contract as the previous best
  layout.

### Phase 7 preview and MIMO evaluation

```powershell
python experiments/phase7_page_preview.py --detection-run-dir outputs/runs/phase2-gbc06-33-1-cta-contract-v1 --cleanup-run-dir outputs/runs/phase6-gbc06-33-1-gpt-background-real-v1 --layout-run-dir outputs/runs/phase4-gbc06-33-1-context-font-layout-v1 --output-root outputs/runs --run-id phase7-gbc06-33-1-context-font-preview-v1 --sample-limit 1

python experiments/phase7_preview_evaluate.py --preview-run-dir outputs/runs/phase7-gbc06-33-1-context-font-preview-v1 --output-root outputs/runs --run-id phase7-gbc06-33-1-context-font-preview-mimo-v2 --sample-limit 1
```

- Preview run: `outputs/runs/phase7-gbc06-33-1-context-font-preview-v1`
- Before/after crop:
  `outputs/runs/phase7-gbc06-33-1-context-font-preview-v1/crops/before_after/GBC06-33-png-1.png`
- Evaluation run:
  `outputs/runs/phase7-gbc06-33-1-context-font-preview-mimo-v2`
- MIMO score: `10`
- Usable: `true`
- Original text removed: `true`
- Art preserved: `true`
- Lettering readable: `true`

The first MIMO evaluation run,
`outputs/runs/phase7-gbc06-33-1-context-font-preview-mimo-v1`, returned a
false negative score of `1` because it treated blank bottom segments as missing
translation text. The prompt now states that top-aligned vertical lettering can
legitimately leave later bottom segments blank. The corrected `v2` run scored
the same preview as `10`.

### Old Bold vs context-selected Medium comparison

```powershell
python experiments/phase7_preview_method_comparison.py --method "old_bold=outputs/runs/phase7-gbc06-33-1-gpt-background-tatechuyoko-scaled-spacing20-v1" --method "context_medium=outputs/runs/phase7-gbc06-33-1-context-font-preview-v1" --evaluation "old_bold=outputs/runs/phase7-gbc06-33-1-gpt-background-tatechuyoko-scaled-spacing20-mimo-v1" --evaluation "context_medium=outputs/runs/phase7-gbc06-33-1-context-font-preview-mimo-v2" --output-root outputs/runs --run-id phase7-gbc06-33-1-font-context-method-comparison-v2 --crop-mode text --mimo
```

- Run: `outputs/runs/phase7-gbc06-33-1-font-context-method-comparison-v2`
- Near-square comparison:
  `outputs/runs/phase7-gbc06-33-1-font-context-method-comparison-v2/debug/near-square-result-grid.png`
- MIMO method comparison:
  `outputs/runs/phase7-gbc06-33-1-font-context-method-comparison-v2/reports/mimo-near-square-comparison.json`
- MIMO ranking: `context_medium`, then `old_bold`
- MIMO scores: both `10`
- MIMO summary: both remove source text cleanly and keep natural vertical
  lettering; they are visually indistinguishable in quality.

The earlier method comparison `v1` used unreadably small full-height strips and
produced a wrong explanation claiming `context_medium` was horizontal text
forced into a vertical column. The fixed `v2` comparison uses enlarged 4-segment
tiles and no longer shows that error.

## Decision

Promote the context-aware Phase 3 selection path as the better experiment
contract for final-looking font reranking.

For `GBC06_33.png#1`, both the old Bold font and new context-selected Medium
font are usable and receive MIMO score `10`. The context-selected Medium result
is slightly lighter and less rigid, so it is a valid next candidate for manual
review. The difference is subtle; this experiment does not prove that Medium
should globally replace Bold.

## Evidence

- Context font selection result:
  `outputs/runs/phase3-gbc06-33-1-context-font-mimo-v1/context-font-results.jsonl`
- Context font grid:
  `outputs/runs/phase3-gbc06-33-1-context-font-mimo-v1/debug/context_font_grids/GBC06-33-png-1.png`
- New layout result:
  `outputs/runs/phase4-gbc06-33-1-context-font-layout-v1/layout-results.jsonl`
- New final crop:
  `outputs/runs/phase7-gbc06-33-1-context-font-preview-v1/crops/before_after/GBC06-33-png-1.png`
- New MIMO evaluation:
  `outputs/runs/phase7-gbc06-33-1-context-font-preview-mimo-v2/preview-evaluation.jsonl`
- Old vs new method comparison:
  `outputs/runs/phase7-gbc06-33-1-font-context-method-comparison-v2/index.md`

## Verification

Targeted tests:

```powershell
python -m pytest tests/test_phase3_context_font_selection.py tests/test_experiment_clis.py::test_phase3_context_font_selection_cli_defaults_to_dry_run_contract -q
```

Result: `3 passed in 2.52s`.

Phase 7 review prompt and method comparison tests:

```powershell
python -m pytest tests/test_phase7_method_comparison.py tests/test_phase7_preview_evaluation.py::test_build_preview_evaluation_prompt_lists_records_and_methods -q
```

Result: `3 passed in 2.40s`.

After splitting the Phase 3 implementation into smaller modules, targeted tests
were rerun:

```powershell
python -m pytest tests/test_phase3_context_font_selection.py tests/test_experiment_clis.py::test_phase3_context_font_selection_cli_defaults_to_dry_run_contract tests/test_phase7_method_comparison.py tests/test_phase7_preview_evaluation.py::test_build_preview_evaluation_prompt_lists_records_and_methods -q
```

Result: `6 passed in 4.91s`.

After code review, two failure-path issues were fixed:

- MIMO parse/selection failure fallback now keeps `selection_source` as
  `context_font_fallback` instead of `mimo_context_font`.
- Upstream `layout-results.jsonl` and `cleanup-results.jsonl` are filtered to
  successful rows (`layout_generated` and `cleaned`) before matching by
  `record_id`.

Review-fix tests:

```powershell
python -m pytest tests/test_phase3_context_font_selection.py tests/test_phase7_method_comparison.py tests/test_phase7_preview_evaluation.py::test_build_preview_evaluation_prompt_lists_records_and_methods -q
```

Result: `8 passed in 2.63s`.

Full suite:

```powershell
python -m pytest -q
```

Result: `321 passed in 60.50s`.

Whitespace check:

```powershell
git diff --check
```

Result: no output.
