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

Current v3 merged coverage command:

```powershell
python experiments/pipeline_coverage_report.py --phase1-run-dir outputs/runs/phase1-gbc06-smoke --detection-run-dir outputs/runs/phase2-gbc06-smoke --font-selection-run-dir outputs/runs/phase3-gbc06-nonbubble-mimo-font-smoke --font-selection-run-dir outputs/runs/phase3-gbc06-bubble-batch-mimo-font-selection --font-selection-run-dir outputs/runs/phase3-gbc06-bubble-batch-7-13-mimo-font-selection --layout-run-dir outputs/runs/phase4-gbc06-tight-text-layout-smoke --layout-run-dir outputs/runs/phase4-gbc06-bubble-batch-layout-v7 --layout-run-dir outputs/runs/phase4-gbc06-bubble-batch-7-13-layout-v3 --angle-run-dir outputs/runs/phase5-gbc06-nonbubble-angle-smoke --angle-run-dir outputs/runs/phase5-gbc06-bubble-batch-angle-v3 --angle-run-dir outputs/runs/phase5-gbc06-bubble-batch-7-13-angle --cleanup-run-dir outputs/runs/phase6-gbc06-bubble-region-fill-experiment --cleanup-run-dir outputs/runs/phase6-gbc06-nonbubble-lama-large-compare --cleanup-run-dir outputs/runs/phase6-gbc06-bubble-batch-region-fill-v7 --cleanup-run-dir outputs/runs/phase6-gbc06-bubble-batch-7-13-region-fill-v2 --preview-run-dir outputs/runs/phase7-8-gbc06-region-fill-layout-smoke/runs/phase7-preview --preview-run-dir outputs/runs/phase7-8-gbc06-bubble-batch-preview-v6/runs/phase7-preview --preview-run-dir outputs/runs/phase7-8-gbc06-bubble-batch-7-13-preview-v2/runs/phase7-preview --export-run-dir outputs/runs/phase7-8-gbc06-region-fill-layout-smoke/runs/phase8-export --export-run-dir outputs/runs/phase7-8-gbc06-bubble-batch-preview-v6/runs/phase8-export --export-run-dir outputs/runs/phase7-8-gbc06-bubble-batch-7-13-preview-v2/runs/phase8-export --run-id phase0-8-gbc06-pipeline-coverage-v3 --next-limit 12
```

Current v4 merged coverage command:

```powershell
python experiments/pipeline_coverage_report.py --phase1-run-dir outputs/runs/phase1-gbc06-smoke --detection-run-dir outputs/runs/phase2-gbc06-smoke-v3 --font-selection-run-dir outputs/runs/phase3-gbc06-nonbubble-mimo-font-smoke --font-selection-run-dir outputs/runs/phase3-gbc06-bubble-batch-mimo-font-selection --font-selection-run-dir outputs/runs/phase3-gbc06-bubble-batch-7-13-mimo-font-selection --font-selection-run-dir outputs/runs/phase3-gbc06-batch-14-15-17-mimo-font-selection --layout-run-dir outputs/runs/phase4-gbc06-tight-text-layout-smoke --layout-run-dir outputs/runs/phase4-gbc06-bubble-batch-layout-v7 --layout-run-dir outputs/runs/phase4-gbc06-bubble-batch-7-13-layout-v3 --layout-run-dir outputs/runs/phase4-gbc06-batch-14-15-layout-manual-readable-v1 --layout-run-dir outputs/runs/phase4-gbc06-batch-17-layout-polarity-white-v1 --angle-run-dir outputs/runs/phase5-gbc06-nonbubble-angle-smoke --angle-run-dir outputs/runs/phase5-gbc06-bubble-batch-angle-v3 --angle-run-dir outputs/runs/phase5-gbc06-bubble-batch-7-13-angle --angle-run-dir outputs/runs/phase5-gbc06-batch-14-15-17-angle-v2 --cleanup-run-dir outputs/runs/phase6-gbc06-bubble-region-fill-experiment --cleanup-run-dir outputs/runs/phase6-gbc06-nonbubble-lama-large-compare --cleanup-run-dir outputs/runs/phase6-gbc06-bubble-batch-region-fill-v7 --cleanup-run-dir outputs/runs/phase6-gbc06-bubble-batch-7-13-region-fill-v2 --cleanup-run-dir outputs/runs/phase6-gbc06-batch-14-15-region-fill-v1 --cleanup-run-dir outputs/runs/phase6-gbc06-batch-17-nonbubble-lama-large-polarity-v3 --preview-run-dir outputs/runs/phase7-8-gbc06-region-fill-layout-smoke/runs/phase7-preview --preview-run-dir outputs/runs/phase7-8-gbc06-bubble-batch-preview-v6/runs/phase7-preview --preview-run-dir outputs/runs/phase7-8-gbc06-bubble-batch-7-13-preview-v2/runs/phase7-preview --preview-run-dir outputs/runs/phase7-8-gbc06-batch-14-15-manual-readable-preview-v1/runs/phase7-preview --preview-run-dir outputs/runs/phase7-8-gbc06-batch-17-lama-white-preview-v1/runs/phase7-preview --export-run-dir outputs/runs/phase7-8-gbc06-region-fill-layout-smoke/runs/phase8-export --export-run-dir outputs/runs/phase7-8-gbc06-bubble-batch-preview-v6/runs/phase8-export --export-run-dir outputs/runs/phase7-8-gbc06-bubble-batch-7-13-preview-v2/runs/phase8-export --export-run-dir outputs/runs/phase7-8-gbc06-batch-14-15-manual-readable-preview-v1/runs/phase8-export --export-run-dir outputs/runs/phase7-8-gbc06-batch-17-lama-white-preview-v1/runs/phase8-export --run-id phase0-8-gbc06-pipeline-coverage-v4 --next-limit 12
```

Current v5 merged coverage command adds the first `GBC06_02.png` batch:

```powershell
python experiments/pipeline_coverage_report.py --phase1-run-dir outputs/runs/phase1-gbc06-smoke --detection-run-dir outputs/runs/phase2-gbc06-smoke-v3 --font-selection-run-dir outputs/runs/phase3-gbc06-nonbubble-mimo-font-smoke --font-selection-run-dir outputs/runs/phase3-gbc06-bubble-batch-mimo-font-selection --font-selection-run-dir outputs/runs/phase3-gbc06-bubble-batch-7-13-mimo-font-selection --font-selection-run-dir outputs/runs/phase3-gbc06-batch-14-15-17-mimo-font-selection --font-selection-run-dir outputs/runs/phase3-gbc06-02-batch-1-3-mimo-font-selection --layout-run-dir outputs/runs/phase4-gbc06-tight-text-layout-smoke --layout-run-dir outputs/runs/phase4-gbc06-bubble-batch-layout-v7 --layout-run-dir outputs/runs/phase4-gbc06-bubble-batch-7-13-layout-v3 --layout-run-dir outputs/runs/phase4-gbc06-batch-14-15-layout-manual-readable-v1 --layout-run-dir outputs/runs/phase4-gbc06-batch-17-layout-polarity-white-v1 --layout-run-dir outputs/runs/phase4-gbc06-02-batch-1-3-layout-v2 --angle-run-dir outputs/runs/phase5-gbc06-nonbubble-angle-smoke --angle-run-dir outputs/runs/phase5-gbc06-bubble-batch-angle-v3 --angle-run-dir outputs/runs/phase5-gbc06-bubble-batch-7-13-angle --angle-run-dir outputs/runs/phase5-gbc06-batch-14-15-17-angle-v2 --angle-run-dir outputs/runs/phase5-gbc06-02-batch-1-3-angle --cleanup-run-dir outputs/runs/phase6-gbc06-bubble-region-fill-experiment --cleanup-run-dir outputs/runs/phase6-gbc06-nonbubble-lama-large-compare --cleanup-run-dir outputs/runs/phase6-gbc06-bubble-batch-region-fill-v7 --cleanup-run-dir outputs/runs/phase6-gbc06-bubble-batch-7-13-region-fill-v2 --cleanup-run-dir outputs/runs/phase6-gbc06-batch-14-15-region-fill-v1 --cleanup-run-dir outputs/runs/phase6-gbc06-batch-17-nonbubble-lama-large-polarity-v3 --cleanup-run-dir outputs/runs/phase6-gbc06-02-batch-1-3-region-fill-v3 --preview-run-dir outputs/runs/phase7-8-gbc06-region-fill-layout-smoke/runs/phase7-preview --preview-run-dir outputs/runs/phase7-8-gbc06-bubble-batch-preview-v6/runs/phase7-preview --preview-run-dir outputs/runs/phase7-8-gbc06-bubble-batch-7-13-preview-v2/runs/phase7-preview --preview-run-dir outputs/runs/phase7-8-gbc06-batch-14-15-manual-readable-preview-v1/runs/phase7-preview --preview-run-dir outputs/runs/phase7-8-gbc06-batch-17-lama-white-preview-v1/runs/phase7-preview --preview-run-dir outputs/runs/phase7-8-gbc06-02-batch-1-3-preview-v3/runs/phase7-preview --export-run-dir outputs/runs/phase7-8-gbc06-region-fill-layout-smoke/runs/phase8-export --export-run-dir outputs/runs/phase7-8-gbc06-bubble-batch-preview-v6/runs/phase8-export --export-run-dir outputs/runs/phase7-8-gbc06-bubble-batch-7-13-preview-v2/runs/phase8-export --export-run-dir outputs/runs/phase7-8-gbc06-batch-14-15-manual-readable-preview-v1/runs/phase8-export --export-run-dir outputs/runs/phase7-8-gbc06-batch-17-lama-white-preview-v1/runs/phase8-export --export-run-dir outputs/runs/phase7-8-gbc06-02-batch-1-3-preview-v3/runs/phase8-export --run-id phase0-8-gbc06-pipeline-coverage-v5 --next-limit 12
```

Current v6 merged coverage command adds `GBC06_02.png#4-#6`:

```powershell
python experiments/pipeline_coverage_report.py --phase1-run-dir outputs/runs/phase1-gbc06-smoke --detection-run-dir outputs/runs/phase2-gbc06-smoke-v3 --font-selection-run-dir outputs/runs/phase3-gbc06-nonbubble-mimo-font-smoke --font-selection-run-dir outputs/runs/phase3-gbc06-bubble-batch-mimo-font-selection --font-selection-run-dir outputs/runs/phase3-gbc06-bubble-batch-7-13-mimo-font-selection --font-selection-run-dir outputs/runs/phase3-gbc06-batch-14-15-17-mimo-font-selection --font-selection-run-dir outputs/runs/phase3-gbc06-02-batch-1-3-mimo-font-selection --font-selection-run-dir outputs/runs/phase3-gbc06-02-batch-4-6-mimo-font-selection --layout-run-dir outputs/runs/phase4-gbc06-tight-text-layout-smoke --layout-run-dir outputs/runs/phase4-gbc06-bubble-batch-layout-v7 --layout-run-dir outputs/runs/phase4-gbc06-bubble-batch-7-13-layout-v3 --layout-run-dir outputs/runs/phase4-gbc06-batch-14-15-layout-manual-readable-v1 --layout-run-dir outputs/runs/phase4-gbc06-batch-17-layout-polarity-white-v1 --layout-run-dir outputs/runs/phase4-gbc06-02-batch-1-3-layout-v2 --layout-run-dir outputs/runs/phase4-gbc06-02-batch-4-6-layout-v1 --angle-run-dir outputs/runs/phase5-gbc06-nonbubble-angle-smoke --angle-run-dir outputs/runs/phase5-gbc06-bubble-batch-angle-v3 --angle-run-dir outputs/runs/phase5-gbc06-bubble-batch-7-13-angle --angle-run-dir outputs/runs/phase5-gbc06-batch-14-15-17-angle-v2 --angle-run-dir outputs/runs/phase5-gbc06-02-batch-1-3-angle --angle-run-dir outputs/runs/phase5-gbc06-02-batch-4-6-angle --cleanup-run-dir outputs/runs/phase6-gbc06-bubble-region-fill-experiment --cleanup-run-dir outputs/runs/phase6-gbc06-nonbubble-lama-large-compare --cleanup-run-dir outputs/runs/phase6-gbc06-bubble-batch-region-fill-v7 --cleanup-run-dir outputs/runs/phase6-gbc06-bubble-batch-7-13-region-fill-v2 --cleanup-run-dir outputs/runs/phase6-gbc06-batch-14-15-region-fill-v1 --cleanup-run-dir outputs/runs/phase6-gbc06-batch-17-nonbubble-lama-large-polarity-v3 --cleanup-run-dir outputs/runs/phase6-gbc06-02-batch-1-3-region-fill-v3 --cleanup-run-dir outputs/runs/phase6-gbc06-02-batch-4-6-region-fill-v2 --preview-run-dir outputs/runs/phase7-8-gbc06-region-fill-layout-smoke/runs/phase7-preview --preview-run-dir outputs/runs/phase7-8-gbc06-bubble-batch-preview-v6/runs/phase7-preview --preview-run-dir outputs/runs/phase7-8-gbc06-bubble-batch-7-13-preview-v2/runs/phase7-preview --preview-run-dir outputs/runs/phase7-8-gbc06-batch-14-15-manual-readable-preview-v1/runs/phase7-preview --preview-run-dir outputs/runs/phase7-8-gbc06-batch-17-lama-white-preview-v1/runs/phase7-preview --preview-run-dir outputs/runs/phase7-8-gbc06-02-batch-1-3-preview-v3/runs/phase7-preview --preview-run-dir outputs/runs/phase7-8-gbc06-02-batch-4-6-preview-v2/runs/phase7-preview --export-run-dir outputs/runs/phase7-8-gbc06-region-fill-layout-smoke/runs/phase8-export --export-run-dir outputs/runs/phase7-8-gbc06-bubble-batch-preview-v6/runs/phase8-export --export-run-dir outputs/runs/phase7-8-gbc06-bubble-batch-7-13-preview-v2/runs/phase8-export --export-run-dir outputs/runs/phase7-8-gbc06-batch-14-15-manual-readable-preview-v1/runs/phase8-export --export-run-dir outputs/runs/phase7-8-gbc06-batch-17-lama-white-preview-v1/runs/phase8-export --export-run-dir outputs/runs/phase7-8-gbc06-02-batch-1-3-preview-v3/runs/phase8-export --export-run-dir outputs/runs/phase7-8-gbc06-02-batch-4-6-preview-v2/runs/phase8-export --run-id phase0-8-gbc06-pipeline-coverage-v6 --next-limit 12
```

Current v7 merged coverage command adds `GBC06_02.png#7-#9`:

```powershell
python experiments/pipeline_coverage_report.py --phase1-run-dir outputs/runs/phase1-gbc06-smoke --detection-run-dir outputs/runs/phase2-gbc06-smoke-v3 --font-selection-run-dir outputs/runs/phase3-gbc06-nonbubble-mimo-font-smoke --font-selection-run-dir outputs/runs/phase3-gbc06-bubble-batch-mimo-font-selection --font-selection-run-dir outputs/runs/phase3-gbc06-bubble-batch-7-13-mimo-font-selection --font-selection-run-dir outputs/runs/phase3-gbc06-batch-14-15-17-mimo-font-selection --font-selection-run-dir outputs/runs/phase3-gbc06-02-batch-1-3-mimo-font-selection --font-selection-run-dir outputs/runs/phase3-gbc06-02-batch-4-6-mimo-font-selection --font-selection-run-dir outputs/runs/phase3-gbc06-02-batch-7-9-mimo-font-selection --layout-run-dir outputs/runs/phase4-gbc06-tight-text-layout-smoke --layout-run-dir outputs/runs/phase4-gbc06-bubble-batch-layout-v7 --layout-run-dir outputs/runs/phase4-gbc06-bubble-batch-7-13-layout-v3 --layout-run-dir outputs/runs/phase4-gbc06-batch-14-15-layout-manual-readable-v1 --layout-run-dir outputs/runs/phase4-gbc06-batch-17-layout-polarity-white-v1 --layout-run-dir outputs/runs/phase4-gbc06-02-batch-1-3-layout-v2 --layout-run-dir outputs/runs/phase4-gbc06-02-batch-4-6-layout-v1 --layout-run-dir outputs/runs/phase4-gbc06-02-batch-7-9-layout-v2 --angle-run-dir outputs/runs/phase5-gbc06-nonbubble-angle-smoke --angle-run-dir outputs/runs/phase5-gbc06-bubble-batch-angle-v3 --angle-run-dir outputs/runs/phase5-gbc06-bubble-batch-7-13-angle --angle-run-dir outputs/runs/phase5-gbc06-batch-14-15-17-angle-v2 --angle-run-dir outputs/runs/phase5-gbc06-02-batch-1-3-angle --angle-run-dir outputs/runs/phase5-gbc06-02-batch-4-6-angle --angle-run-dir outputs/runs/phase5-gbc06-02-batch-7-9-angle --cleanup-run-dir outputs/runs/phase6-gbc06-bubble-region-fill-experiment --cleanup-run-dir outputs/runs/phase6-gbc06-nonbubble-lama-large-compare --cleanup-run-dir outputs/runs/phase6-gbc06-bubble-batch-region-fill-v7 --cleanup-run-dir outputs/runs/phase6-gbc06-bubble-batch-7-13-region-fill-v2 --cleanup-run-dir outputs/runs/phase6-gbc06-batch-14-15-region-fill-v1 --cleanup-run-dir outputs/runs/phase6-gbc06-batch-17-nonbubble-lama-large-polarity-v3 --cleanup-run-dir outputs/runs/phase6-gbc06-02-batch-1-3-region-fill-v3 --cleanup-run-dir outputs/runs/phase6-gbc06-02-batch-4-6-region-fill-v2 --cleanup-run-dir outputs/runs/phase6-gbc06-02-batch-7-9-region-fill-v2 --preview-run-dir outputs/runs/phase7-8-gbc06-region-fill-layout-smoke/runs/phase7-preview --preview-run-dir outputs/runs/phase7-8-gbc06-bubble-batch-preview-v6/runs/phase7-preview --preview-run-dir outputs/runs/phase7-8-gbc06-bubble-batch-7-13-preview-v2/runs/phase7-preview --preview-run-dir outputs/runs/phase7-8-gbc06-batch-14-15-manual-readable-preview-v1/runs/phase7-preview --preview-run-dir outputs/runs/phase7-8-gbc06-batch-17-lama-white-preview-v1/runs/phase7-preview --preview-run-dir outputs/runs/phase7-8-gbc06-02-batch-1-3-preview-v3/runs/phase7-preview --preview-run-dir outputs/runs/phase7-8-gbc06-02-batch-4-6-preview-v2/runs/phase7-preview --preview-run-dir outputs/runs/phase7-8-gbc06-02-batch-7-9-preview-v2/runs/phase7-preview --export-run-dir outputs/runs/phase7-8-gbc06-region-fill-layout-smoke/runs/phase8-export --export-run-dir outputs/runs/phase7-8-gbc06-bubble-batch-preview-v6/runs/phase8-export --export-run-dir outputs/runs/phase7-8-gbc06-bubble-batch-7-13-preview-v2/runs/phase8-export --export-run-dir outputs/runs/phase7-8-gbc06-batch-14-15-manual-readable-preview-v1/runs/phase8-export --export-run-dir outputs/runs/phase7-8-gbc06-batch-17-lama-white-preview-v1/runs/phase8-export --export-run-dir outputs/runs/phase7-8-gbc06-02-batch-1-3-preview-v3/runs/phase8-export --export-run-dir outputs/runs/phase7-8-gbc06-02-batch-4-6-preview-v2/runs/phase8-export --export-run-dir outputs/runs/phase7-8-gbc06-02-batch-7-9-preview-v2/runs/phase8-export --run-id phase0-8-gbc06-pipeline-coverage-v7 --next-limit 12
```

## Generated Artifacts

- `outputs/runs/phase0-8-gbc06-pipeline-coverage/pipeline-coverage.json`
- `outputs/runs/phase0-8-gbc06-pipeline-coverage/reports/pipeline-coverage-report.md`
- `outputs/runs/phase0-8-gbc06-pipeline-coverage-v2/pipeline-coverage.json`
- `outputs/runs/phase0-8-gbc06-pipeline-coverage-v2/reports/pipeline-coverage-report.md`
- `outputs/runs/phase0-8-gbc06-pipeline-coverage-v3/pipeline-coverage.json`
- `outputs/runs/phase0-8-gbc06-pipeline-coverage-v3/reports/pipeline-coverage-report.md`
- `outputs/runs/phase0-8-gbc06-pipeline-coverage-v4/pipeline-coverage.json`
- `outputs/runs/phase0-8-gbc06-pipeline-coverage-v4/reports/pipeline-coverage-report.md`
- `outputs/runs/phase0-8-gbc06-pipeline-coverage-v5/pipeline-coverage.json`
- `outputs/runs/phase0-8-gbc06-pipeline-coverage-v5/reports/pipeline-coverage-report.md`
- `outputs/runs/phase0-8-gbc06-pipeline-coverage-v6/pipeline-coverage.json`
- `outputs/runs/phase0-8-gbc06-pipeline-coverage-v6/reports/pipeline-coverage-report.md`
- `outputs/runs/phase0-8-gbc06-pipeline-coverage-v7/pipeline-coverage.json`
- `outputs/runs/phase0-8-gbc06-pipeline-coverage-v7/reports/pipeline-coverage-report.md`

`outputs/` remains ignored by Git. The source-backed summary below records the key numbers so the experiment is traceable in the repository.

## Current Coverage

Base stage: `phase2_detection`

```text
base_record_count=30
complete_record_count=24
incomplete_record_count=6
```

Stage counts:

```text
phase1_labelplus       covered=30 missing=0
phase2_detection       covered=30 missing=0
phase3_font_selection  covered=26 missing=4
phase4_layout          covered=24 missing=6
phase5_angle           covered=26 missing=4
phase6_cleanup         covered=24 missing=6
phase7_preview         covered=24 missing=6
phase8_export          covered=24 missing=6
```

Group coverage:

```text
框内: base=28 complete=22
框外: base=2  complete=2
```

## Next Records

The v7 coverage report counts these records as complete across all tracked stages:

```text
GBC06_01.png#1
GBC06_01.png#2
GBC06_01.png#3
GBC06_01.png#4
GBC06_01.png#5
GBC06_01.png#6
GBC06_01.png#7
GBC06_01.png#8
GBC06_01.png#9
GBC06_01.png#10
GBC06_01.png#11
GBC06_01.png#12
GBC06_01.png#13
GBC06_01.png#16
GBC06_01.png#17
GBC06_02.png#1
GBC06_02.png#2
GBC06_02.png#3
GBC06_02.png#4
GBC06_02.png#5
GBC06_02.png#6
GBC06_02.png#7
GBC06_02.png#8
GBC06_02.png#9
```

The next `GBC06_02.png` expansion still starts at `phase3_font_selection`. The v7
report recommends these first `GBC06_02.png` records:

```text
GBC06_02.png#10 框内  first_missing_stage=phase3_font_selection
GBC06_02.png#11 框内  first_missing_stage=phase3_font_selection
GBC06_02.png#12 框内  first_missing_stage=phase3_font_selection
GBC06_02.png#13 框内  first_missing_stage=phase3_font_selection
```

## Interpretation

The current detection prototype has already produced 30 candidate records across `GBC06_01.png` and `GBC06_02.png`. The v7 coverage tool counts 24 complete records: the initial `GBC06_01.png#1`, both non-bubble records `GBC06_01.png#16` and `#17`, the bubble records `GBC06_01.png#2` through `#13`, and `GBC06_02.png#1` through `#9`.

The `GBC06_02.png#1-#3` expansion required two fixes: tighter adjacent-column text bbox selection and mask-aware page cleanup composition. The best MIMO-backed integrated run is `phase7-8-gbc06-02-batch-1-3-preview-v3`, with score `7` and `usable=true`; `#2` and `#3` each received per-record MIMO score `10`. A follow-up top-aligned vertical-column rendering experiment (`preview-v4`) dropped to score `5`, so it was not kept.

The `GBC06_02.png#4-#6` expansion exposed a Phase 6 cleanup-range mismatch on `#5`: Phase 4 placed text in the full multi-column source text bbox, but Phase 6 cleaned only the selected detection column. The fixed cleanup uses the union of `selected_text_box_xyxy` and `selected_text_bbox(detection)`. The best integrated run is `phase7-8-gbc06-02-batch-4-6-preview-v2`, with MIMO score `8` and `usable=true`; per-record scores were `9`, `8`, and `9`.

The `GBC06_02.png#7-#9` expansion exposed a Phase 4 font-size issue: short vertical translations could scale up until they filled the target height. The fixed layout cap uses a conservative source-column-width multiplier for short vertical translations. The best integrated run is `phase7-8-gbc06-02-batch-7-9-preview-v2`, with MIMO score `9` and `usable=true`; every record scored `9`.

The v7 generated coverage report still lists `GBC06_01.png#14` and `#15` as missing Phase 4 in the next-record table. That is a limitation of the current merged coverage command and historical manual-readable run accounting; it does not affect the new `GBC06_02.png#7-#9` evidence. The practical next expansion target is `GBC06_02.png#10`.

## Verification

Fresh verification for the coverage tool:

```powershell
python -m pytest tests/test_pipeline_coverage.py -q
```

Observed result:

```text
3 passed in 0.10s
```
