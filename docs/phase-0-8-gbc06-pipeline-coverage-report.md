# Phase 0-8 GBC06 Pipeline Coverage Report

## Purpose

This report records the first cross-phase coverage audit for the current GBC06 experiment runs. It answers which records already flow through the full auto-lettering loop and which stage blocks the next coverage expansion.

## Command

```powershell
python experiments/pipeline_coverage_report.py --phase1-run-dir outputs/runs/phase1-gbc06-smoke --detection-run-dir outputs/runs/phase2-gbc06-smoke --font-selection-run-dir outputs/runs/phase3-gbc06-nonbubble-mimo-font-smoke --layout-run-dir outputs/runs/phase4-gbc06-tight-text-layout-smoke --angle-run-dir outputs/runs/phase5-gbc06-nonbubble-angle-smoke --cleanup-run-dir outputs/runs/phase6-gbc06-bubble-region-fill-experiment --cleanup-run-dir outputs/runs/phase6-gbc06-nonbubble-lama-large-compare --preview-run-dir outputs/runs/phase7-8-gbc06-region-fill-layout-smoke/runs/phase7-preview --export-run-dir outputs/runs/phase7-8-gbc06-region-fill-layout-smoke/runs/phase8-export --run-id phase0-8-gbc06-pipeline-coverage --next-limit 12
```

## Generated Artifacts

- `outputs/runs/phase0-8-gbc06-pipeline-coverage/pipeline-coverage.json`
- `outputs/runs/phase0-8-gbc06-pipeline-coverage/reports/pipeline-coverage-report.md`

`outputs/` remains ignored by Git. The source-backed summary below records the key numbers so the experiment is traceable in the repository.

## Current Coverage

Base stage: `phase2_detection`

```text
base_record_count=30
complete_record_count=2
incomplete_record_count=28
```

Stage counts:

```text
phase1_labelplus       covered=30 missing=0
phase2_detection       covered=30 missing=0
phase3_font_selection  covered=2  missing=28
phase4_layout          covered=2  missing=28
phase5_angle           covered=2  missing=28
phase6_cleanup         covered=2  missing=28
phase7_preview         covered=2  missing=28
phase8_export          covered=2  missing=28
```

Group coverage:

```text
框内: base=28 complete=1
框外: base=2  complete=1
```

## Next Records

The next unblocked expansion starts at `phase3_font_selection`. The report recommends these first records:

```text
GBC06_01.png#2  框内  first_missing_stage=phase3_font_selection
GBC06_01.png#3  框内  first_missing_stage=phase3_font_selection
GBC06_01.png#4  框内  first_missing_stage=phase3_font_selection
GBC06_01.png#5  框内  first_missing_stage=phase3_font_selection
GBC06_01.png#6  框内  first_missing_stage=phase3_font_selection
GBC06_01.png#7  框内  first_missing_stage=phase3_font_selection
GBC06_01.png#8  框内  first_missing_stage=phase3_font_selection
GBC06_01.png#9  框内  first_missing_stage=phase3_font_selection
GBC06_01.png#10 框内  first_missing_stage=phase3_font_selection
GBC06_01.png#11 框内  first_missing_stage=phase3_font_selection
GBC06_01.png#12 框内  first_missing_stage=phase3_font_selection
GBC06_01.png#13 框内  first_missing_stage=phase3_font_selection
```

## Interpretation

The current detection prototype has already produced 30 candidate records across `GBC06_01.png` and `GBC06_02.png`, but the closed-loop experiment is still only complete for two records: `GBC06_01.png#1` and `GBC06_01.png#16`.

The immediate bottleneck is not detection or cleanup. It is the beginning of the post-detection chain: font selection, layout, angle, cleanup, preview, and export need to be scaled beyond the two-record smoke set. A sensible next expansion is a small batch over the recommended `框内` records, reusing the deterministic `bubble_region_fill` cleanup path and limiting MIMO calls to font selection/evaluation checkpoints.

## Verification

Fresh verification for the coverage tool:

```powershell
python -m pytest tests/test_pipeline_coverage.py -q
```

Observed result:

```text
2 passed in 0.07s
```
