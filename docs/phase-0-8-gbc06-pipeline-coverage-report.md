# Phase 0-8 GBC06 Pipeline Coverage Report

## Purpose

This report records the cross-phase coverage audit for the current GBC06 experiment runs. It answers which records already flow through the full auto-lettering loop and which stage blocks the next coverage expansion.

The coverage tool now accepts multiple run directories for Phase 3, Phase 4, Phase 5, Phase 7, and Phase 8. This matters because the project deliberately grows through small verified batches; a single coverage report must merge the initial smoke run, the non-bubble run, and later bubble batch runs.

## Command

```powershell
python experiments/pipeline_coverage_report.py --phase1-run-dir outputs/runs/phase1-gbc06-smoke --detection-run-dir outputs/runs/phase2-gbc06-smoke --font-selection-run-dir outputs/runs/phase3-gbc06-nonbubble-mimo-font-smoke --layout-run-dir outputs/runs/phase4-gbc06-tight-text-layout-smoke --angle-run-dir outputs/runs/phase5-gbc06-nonbubble-angle-smoke --cleanup-run-dir outputs/runs/phase6-gbc06-bubble-region-fill-experiment --cleanup-run-dir outputs/runs/phase6-gbc06-nonbubble-lama-large-compare --preview-run-dir outputs/runs/phase7-8-gbc06-region-fill-layout-smoke/runs/phase7-preview --export-run-dir outputs/runs/phase7-8-gbc06-region-fill-layout-smoke/runs/phase8-export --run-id phase0-8-gbc06-pipeline-coverage --next-limit 12
```

Current merged coverage command:

```powershell
python experiments/pipeline_coverage_report.py --phase1-run-dir outputs/runs/phase1-gbc06-smoke --detection-run-dir outputs/runs/phase2-gbc06-smoke --font-selection-run-dir outputs/runs/phase3-gbc06-nonbubble-mimo-font-smoke --font-selection-run-dir outputs/runs/phase3-gbc06-bubble-batch-mimo-font-selection --layout-run-dir outputs/runs/phase4-gbc06-tight-text-layout-smoke --layout-run-dir outputs/runs/phase4-gbc06-bubble-batch-layout-v7 --angle-run-dir outputs/runs/phase5-gbc06-nonbubble-angle-smoke --angle-run-dir outputs/runs/phase5-gbc06-bubble-batch-angle-v3 --cleanup-run-dir outputs/runs/phase6-gbc06-bubble-region-fill-experiment --cleanup-run-dir outputs/runs/phase6-gbc06-nonbubble-lama-large-compare --cleanup-run-dir outputs/runs/phase6-gbc06-bubble-batch-region-fill-v7 --preview-run-dir outputs/runs/phase7-8-gbc06-region-fill-layout-smoke/runs/phase7-preview --preview-run-dir outputs/runs/phase7-8-gbc06-bubble-batch-preview-v6/runs/phase7-preview --export-run-dir outputs/runs/phase7-8-gbc06-region-fill-layout-smoke/runs/phase8-export --export-run-dir outputs/runs/phase7-8-gbc06-bubble-batch-preview-v6/runs/phase8-export --run-id phase0-8-gbc06-pipeline-coverage-v2 --next-limit 12
```

## Generated Artifacts

- `outputs/runs/phase0-8-gbc06-pipeline-coverage/pipeline-coverage.json`
- `outputs/runs/phase0-8-gbc06-pipeline-coverage/reports/pipeline-coverage-report.md`
- `outputs/runs/phase0-8-gbc06-pipeline-coverage-v2/pipeline-coverage.json`
- `outputs/runs/phase0-8-gbc06-pipeline-coverage-v2/reports/pipeline-coverage-report.md`

`outputs/` remains ignored by Git. The source-backed summary below records the key numbers so the experiment is traceable in the repository.

## Current Coverage

Base stage: `phase2_detection`

```text
base_record_count=30
complete_record_count=7
incomplete_record_count=23
```

Stage counts:

```text
phase1_labelplus       covered=30 missing=0
phase2_detection       covered=30 missing=0
phase3_font_selection  covered=7  missing=23
phase4_layout          covered=7  missing=23
phase5_angle           covered=7  missing=23
phase6_cleanup         covered=7  missing=23
phase7_preview         covered=7  missing=23
phase8_export          covered=7  missing=23
```

Group coverage:

```text
框内: base=28 complete=6
框外: base=2  complete=1
```

## Next Records

The complete cross-phase loop now covers:

```text
GBC06_01.png#1
GBC06_01.png#2
GBC06_01.png#3
GBC06_01.png#4
GBC06_01.png#5
GBC06_01.png#6
GBC06_01.png#16
```

The next unblocked expansion still starts at `phase3_font_selection`. The v2 report recommends these first records:

```text
GBC06_01.png#7  框内  first_missing_stage=phase3_font_selection
GBC06_01.png#8  框内  first_missing_stage=phase3_font_selection
GBC06_01.png#9  框内  first_missing_stage=phase3_font_selection
GBC06_01.png#10 框内  first_missing_stage=phase3_font_selection
GBC06_01.png#11 框内  first_missing_stage=phase3_font_selection
GBC06_01.png#12 框内  first_missing_stage=phase3_font_selection
GBC06_01.png#13 框内  first_missing_stage=phase3_font_selection
GBC06_01.png#14 框内  first_missing_stage=phase3_font_selection
GBC06_01.png#15 框内  first_missing_stage=phase3_font_selection
GBC06_01.png#17 框外  first_missing_stage=phase3_font_selection
GBC06_02.png#1  框内  first_missing_stage=phase3_font_selection
GBC06_02.png#2  框内  first_missing_stage=phase3_font_selection
```

## Interpretation

The current detection prototype has already produced 30 candidate records across `GBC06_01.png` and `GBC06_02.png`. The closed-loop experiment is now complete for seven records: the initial `GBC06_01.png#1`, the non-bubble `GBC06_01.png#16`, and the five-record bubble batch `GBC06_01.png#2` through `#6`.

The immediate bottleneck is not detection or cleanup. It is the beginning of the post-detection chain: font selection, layout, angle, cleanup, preview, and export need to be scaled beyond the seven-record set. A sensible next expansion is a small batch over `GBC06_01.png#7` through `#13`, reusing the deterministic `bubble_region_fill` cleanup path for `框内` records and limiting MIMO calls to font selection/evaluation checkpoints.

## Verification

Fresh verification for the coverage tool:

```powershell
python -m pytest tests/test_pipeline_coverage.py -q
```

Observed result:

```text
4 passed in 0.14s
```
