# Phase 4/7 Vertical Digit Layout Report

## Scope

This slice improves the programmatic lettering layout for the red side banner
`GBC06_33.png#1` after the previous GPT background-only repair proved usable.

- Record: `GBC06_33.png#1`
- Target text: `漫画第一卷\n2026年6月29日发售！！`
- Text bbox: `[1156, 371, 1298, 1925]`
- Cleanup run: `outputs/runs/phase6-gbc06-33-1-gpt-background-real-v1`
- Baseline layout run: `outputs/runs/phase4-gbc06-33-1-cta-full-layout-v2-light-cap`

## Problem

The previous Phase 4 render treated every digit as a normal vertical character:

```text
漫画第一卷2026年6月29日发售！！
```

That made dates look like rigid stacked glyphs. The result was readable, but it
did not match common manga banner date typography, where short digit groups are
often laid out as compact horizontal groups inside vertical text.

## Code Changes Under Test

- `autolettering/layout/vertical_text.py`
  - Adds `vertical_text_tokens()`.
  - Groups continuous 2-4 digit runs as one vertical token.
  - Adds `vertical_digit_group_scale()` so 4-digit tokens can fit the narrow
    banner without crossing panel borders.
- `autolettering/layout/measure.py`
  - Measures vertical text by tokens instead of raw characters.
  - Uses the same digit group scale during layout search.
- `autolettering/layout/render_text.py`
  - Renders vertical digit group tokens with the same scaled font used by
    measurement.
- `autolettering/phase4.py`
  - For tall narrow non-bubble CTA/CTD strips only, allows larger vertical
    line-spacing candidates: `[4, 8, 12, 16, 20]`.
  - Other vertical text keeps the existing default spacing search.

## Experiments

The experiment loop used the same GPT background-repaired crop and varied only
the Phase 4 layout.

### Baseline: per-digit vertical

```powershell
python experiments/phase7_page_preview.py --detection-run-dir outputs/runs/phase2-gbc06-33-1-cta-contract-v1 --cleanup-run-dir outputs/runs/phase6-gbc06-33-1-gpt-background-real-v1 --layout-run-dir outputs/runs/phase4-gbc06-33-1-cta-full-layout-v2-light-cap --output-root outputs/runs --run-id phase7-gbc06-33-1-gpt-background-full-layout-v1 --sample-limit 1
```

- Phase 4 layout: `font_size=54`, `line_spacing=4`, `measured_width=54`,
  `measured_height=960`.
- MIMO run: `outputs/runs/phase7-gbc06-33-1-gpt-background-full-layout-mimo-v1`
- MIMO score: `10`, `usable=true`
- Manual read: readable, but date digits look like ordinary stacked glyphs.

### Digit group compact

```powershell
python experiments/phase4_layout_search.py --selection-run-dir outputs/runs/phase3-gbc06-29-33-mimo-font-selection-v1 --detection-run-dir outputs/runs/phase2-gbc06-33-1-cta-contract-v1 --output-root outputs/runs --run-id phase4-gbc06-33-1-cta-full-layout-v4-tatechuyoko-scaled --sample-limit 1 --record-id "GBC06_33.png#1"

python experiments/phase7_page_preview.py --detection-run-dir outputs/runs/phase2-gbc06-33-1-cta-contract-v1 --cleanup-run-dir outputs/runs/phase6-gbc06-33-1-gpt-background-real-v1 --layout-run-dir outputs/runs/phase4-gbc06-33-1-cta-full-layout-v4-tatechuyoko-scaled --output-root outputs/runs --run-id phase7-gbc06-33-1-gpt-background-tatechuyoko-scaled-v1 --sample-limit 1
```

- Phase 4 layout: `font_size=54`, `line_spacing=4`, `measured_width=80`,
  `measured_height=731`.
- Manual read: digit grouping is better, but the whole Chinese column is too
  short for the long red banner.

### Digit group with spacing 28

```powershell
python experiments/phase4_layout_search.py --selection-run-dir outputs/runs/phase3-gbc06-29-33-mimo-font-selection-v1 --detection-run-dir outputs/runs/phase2-gbc06-33-1-cta-contract-v1 --output-root outputs/runs --run-id phase4-gbc06-33-1-cta-full-layout-v6-tatechuyoko-scaled-spacing28 --sample-limit 1 --record-id "GBC06_33.png#1"

python experiments/phase7_page_preview.py --detection-run-dir outputs/runs/phase2-gbc06-33-1-cta-contract-v1 --cleanup-run-dir outputs/runs/phase6-gbc06-33-1-gpt-background-real-v1 --layout-run-dir outputs/runs/phase4-gbc06-33-1-cta-full-layout-v6-tatechuyoko-scaled-spacing28 --output-root outputs/runs --run-id phase7-gbc06-33-1-gpt-background-tatechuyoko-scaled-spacing28-v1 --sample-limit 1

python experiments/phase7_preview_evaluate.py --preview-run-dir outputs/runs/phase7-gbc06-33-1-gpt-background-tatechuyoko-scaled-spacing28-v1 --output-root outputs/runs --run-id phase7-gbc06-33-1-gpt-background-tatechuyoko-scaled-spacing28-mimo-v1 --sample-limit 1
```

- Phase 4 layout: `font_size=54`, `line_spacing=28`, `measured_width=80`,
  `measured_height=1067`.
- MIMO score: `9`, `usable=true`
- Manual read: better than compact, but the column starts to feel too loose.

### Selected: digit group with spacing 20

```powershell
python experiments/phase4_layout_search.py --selection-run-dir outputs/runs/phase3-gbc06-29-33-mimo-font-selection-v1 --detection-run-dir outputs/runs/phase2-gbc06-33-1-cta-contract-v1 --output-root outputs/runs --run-id phase4-gbc06-33-1-cta-full-layout-v7-tatechuyoko-scaled-spacing20 --sample-limit 1 --record-id "GBC06_33.png#1"

python experiments/phase7_page_preview.py --detection-run-dir outputs/runs/phase2-gbc06-33-1-cta-contract-v1 --cleanup-run-dir outputs/runs/phase6-gbc06-33-1-gpt-background-real-v1 --layout-run-dir outputs/runs/phase4-gbc06-33-1-cta-full-layout-v7-tatechuyoko-scaled-spacing20 --output-root outputs/runs --run-id phase7-gbc06-33-1-gpt-background-tatechuyoko-scaled-spacing20-v1 --sample-limit 1

python experiments/phase7_preview_evaluate.py --preview-run-dir outputs/runs/phase7-gbc06-33-1-gpt-background-tatechuyoko-scaled-spacing20-v1 --output-root outputs/runs --run-id phase7-gbc06-33-1-gpt-background-tatechuyoko-scaled-spacing20-mimo-v1 --sample-limit 1
```

- Phase 4 layout: `font_size=54`, `line_spacing=20`, `measured_width=80`,
  `measured_height=955`.
- MIMO score: `10`, `usable=true`
- Manual read: best current candidate. It keeps `2026` and `29` as readable
  compact digit groups without crossing the border, and the column is less loose
  than the spacing-28 version.

## Evidence

- Four-way comparison:
  `outputs/runs/phase7-gbc06-33-1-gpt-background-tatechuyoko-scaled-spacing20-v1/debug/tatechuyoko_method_comparison_gbc06-33-1.png`
- Selected crop:
  `outputs/runs/phase7-gbc06-33-1-gpt-background-tatechuyoko-scaled-spacing20-v1/crops/before_after/GBC06-33-png-1.png`
- Selected MIMO sheet:
  `outputs/runs/phase7-gbc06-33-1-gpt-background-tatechuyoko-scaled-spacing20-v1/debug/evaluation_contact_sheets/GBC06-33-png.png`
- Selected MIMO JSON:
  `outputs/runs/phase7-gbc06-33-1-gpt-background-tatechuyoko-scaled-spacing20-mimo-v1/preview-evaluation.jsonl`

## Decision

Use the `spacing20` digit-group result as the current best Phase 4 layout for
`GBC06_33.png#1`.

This does not solve font style fully. The selected Chinese font is still more
rigid than the source lettering. The next improvement should be a font-selection
or font-styling pass, not another background repair pass.

## Verification

Targeted tests:

```powershell
python -m pytest tests/test_phase4_layout.py::test_run_phase4_infers_light_text_for_tall_cta_mask_source tests/test_phase4_layout.py::test_render_layout_preview_groups_multidigit_numbers_in_vertical_text -q
```

Result: `2 passed in 1.51s`.

Phase 4 focused suite:

```powershell
python -m pytest tests/test_phase4_layout.py tests/test_phase4_layout_validation.py tests/test_phase4_layout_variant_experiment.py -q
```

Result: `52 passed in 6.41s`.

Full suite:

```powershell
python -m pytest -q
```

Result: `318 passed in 50.06s`.

Whitespace check:

```powershell
git diff --check
```

Result: no output.
