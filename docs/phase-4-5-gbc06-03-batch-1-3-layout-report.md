# Phase 4/5 GBC06_03 #1-#3 Layout and Angle Report

## Purpose

This run advances the first three `GBC06_03.png` CTA-matched speech-bubble
records from Phase 3 font selection into Phase 5 angle estimation and Phase 4
layout search:

- `GBC06_03.png#1`
- `GBC06_03.png#2`
- `GBC06_03.png#3`

The accepted layout run is `phase4-gbc06-03-batch-1-3-layout-v3`. The earlier
`v1` output is preserved as a negative control because the vertical text looked
visually cramped despite `overflow_ratio=0.0`.

## Commands

Estimate orientation and angle:

```powershell
python experiments/phase5_orientation_angle.py --detection-run-dir outputs/runs/phase2-gbc06-03-batch-1-3-cta-detection-v1 --output-root outputs/runs --run-id phase5-gbc06-03-batch-1-3-angle --sample-limit 3 --record-id "GBC06_03.png#1" --record-id "GBC06_03.png#2" --record-id "GBC06_03.png#3"
```

Generate the accepted Phase 4 layout run:

```powershell
python experiments/phase4_layout_search.py --selection-run-dir outputs/runs/phase3-gbc06-03-batch-1-3-mimo-font-selection --angle-run-dir outputs/runs/phase5-gbc06-03-batch-1-3-angle --detection-run-dir outputs/runs/phase2-gbc06-03-batch-1-3-cta-detection-v1 --output-root outputs/runs --run-id phase4-gbc06-03-batch-1-3-layout-v3 --sample-limit 3 --record-id "GBC06_03.png#1" --record-id "GBC06_03.png#2" --record-id "GBC06_03.png#3"
```

Run MIMO layout validation:

```powershell
python experiments/phase4_layout_validate.py --layout-run-dir outputs/runs/phase4-gbc06-03-batch-1-3-layout-v3 --output-root outputs/runs --run-id phase4-gbc06-03-batch-1-3-layout-v3-mimo-validation --sample-limit 3
```

Generate updated pipeline coverage:

```powershell
python experiments/pipeline_coverage_report.py --registry-file docs/pipeline-runs.gbc06.json --registry-entry phase0-8-gbc06-v24-gbc06-03-layout-angle --output-root outputs/runs --next-limit 12
```

## Generated Artifacts

- `outputs/runs/phase5-gbc06-03-batch-1-3-angle/angle-results.jsonl`
- `outputs/runs/phase5-gbc06-03-batch-1-3-angle/debug/angle_candidates/GBC06-03-png-1.png`
- `outputs/runs/phase5-gbc06-03-batch-1-3-angle/debug/angle_candidates/GBC06-03-png-2.png`
- `outputs/runs/phase5-gbc06-03-batch-1-3-angle/debug/angle_candidates/GBC06-03-png-3.png`
- `outputs/runs/phase4-gbc06-03-batch-1-3-layout-v3/layout-results.jsonl`
- `outputs/runs/phase4-gbc06-03-batch-1-3-layout-v3/debug/layout_candidates/GBC06-03-png-1.png`
- `outputs/runs/phase4-gbc06-03-batch-1-3-layout-v3/debug/layout_candidates/GBC06-03-png-2.png`
- `outputs/runs/phase4-gbc06-03-batch-1-3-layout-v3/debug/layout_candidates/GBC06-03-png-3.png`
- `outputs/runs/phase4-gbc06-03-batch-1-3-layout-v3/visuals/layout-v1-v2-v3-comparison-grid.png`
- `outputs/runs/phase4-gbc06-03-batch-1-3-layout-v3-mimo-validation/layout-validation.jsonl`
- `outputs/runs/phase4-gbc06-03-batch-1-3-layout-v3-mimo-validation/reports/api-calls.jsonl`
- `outputs/runs/phase0-8-gbc06-pipeline-coverage-v24-gbc06-03-layout-angle/pipeline-coverage.json`
- `outputs/runs/phase0-8-gbc06-pipeline-coverage-v24-gbc06-03-layout-angle/reports/pipeline-coverage-report.md`

The MIMO API call log stores request and response summaries only. It does not
store API keys.

## Angle Results

```text
GBC06_03.png#1  orientation=vertical  selected_angle=0.1   confidence=0.989
GBC06_03.png#2  orientation=vertical  selected_angle=0.4   confidence=0.982
GBC06_03.png#3  orientation=vertical  selected_angle=-0.1  confidence=0.950
```

All three angles are below `MIN_APPLIED_ANGLE_DEGREES=3.0`, so the accepted
Phase 4 layout correctly uses `angle_degrees=0.0`.

## Layout Iteration

The first layout run used tight glyph-bbox height as the vertical advance. This
made the renderer and measurement internally consistent, but allowed the search
to choose a too-large font with visible glyph crowding:

```text
v1: #1 font_size=34 measured=36x186 target=37x189
v1: #2 font_size=35 measured=35x129 target=36x130
v1: #3 font_size=25 measured=25x119 target=38x123
```

The fix changes vertical measurement and rendering to use an optical cell
advance of `max(ink_height, round(font_size * 0.95))`. This keeps the text from
using only tight ink bounds while avoiding the overly narrow `100%` cell-advance
variant that MIMO rejected for `#1`.

Accepted v3 layout:

```text
GBC06_03.png#1  text=你要去哪里？  font_size=33  measured=35x186  target=37x189  angle=0.0  vertical_align=top
GBC06_03.png#2  text=我要回家      font_size=34  measured=34x128  target=36x130  angle=0.0  vertical_align=top
GBC06_03.png#3  text=差不多得了    font_size=25  measured=25x121  target=38x123  angle=0.0  vertical_align=top
```

## MIMO Validation

`phase4-gbc06-03-batch-1-3-layout-v2-mimo-validation` was useful as an
intermediate check: it accepted `#2` and `#3`, but requested revision for `#1`
because the text was slightly narrower than the target box.

The accepted v3 MIMO validation result:

```text
GBC06_03.png#1  accepted=true  reason=vertical text, character count and measured height match with no overflow
GBC06_03.png#2  accepted=true  reason=vertical orientation and target dimensions closely match measured values
GBC06_03.png#3  accepted=true  reason=vertical text aligned within target bounds
```

This Phase 4 validation uses the existing layout-preview-only MIMO gate. It
does not replace the later Phase 7 before/after contact-sheet evaluation.

## Coverage Result

Observed v24 coverage result:

```text
base_record_count=38
complete_record_count=35
incomplete_record_count=3
phase4_layout covered=38 missing=0
phase5_angle covered=38 missing=0
phase6_cleanup covered=35 missing=3
next_records[0]=GBC06_03.png#1 first_missing_stage=phase6_cleanup
next_records[1]=GBC06_03.png#2 first_missing_stage=phase6_cleanup
next_records[2]=GBC06_03.png#3 first_missing_stage=phase6_cleanup
```

## Verification

Targeted Phase 4 regression:

```powershell
python -m pytest tests/test_phase4_layout.py -q
```

Observed result:

```text
41 passed
```
