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

Current v8 merged coverage command adds `GBC06_02.png#10-#13`. It is the v7 command plus:

```powershell
--font-selection-run-dir outputs/runs/phase3-gbc06-02-batch-10-13-mimo-font-selection --layout-run-dir outputs/runs/phase4-gbc06-02-batch-10-13-layout-v5 --angle-run-dir outputs/runs/phase5-gbc06-02-batch-10-13-angle --cleanup-run-dir outputs/runs/phase6-gbc06-02-batch-10-13-region-fill-v6 --preview-run-dir outputs/runs/phase7-8-gbc06-02-batch-10-13-preview-v7/runs/phase7-preview --export-run-dir outputs/runs/phase7-8-gbc06-02-batch-10-13-preview-v7/runs/phase8-export --run-id phase0-8-gbc06-pipeline-coverage-v8 --next-limit 12
```

Current v10 merged coverage command adds the historical `GBC06_01.png#14-#15` gap-closing run. It is the v8 command plus:

```powershell
--layout-run-dir outputs/runs/phase4-gbc06-batch-14-15-layout-v2 --cleanup-run-dir outputs/runs/phase6-gbc06-batch-14-15-region-fill-v2 --preview-run-dir outputs/runs/phase7-8-gbc06-batch-14-15-preview-v5/runs/phase7-preview --export-run-dir outputs/runs/phase7-8-gbc06-batch-14-15-preview-v5/runs/phase8-export --run-id phase0-8-gbc06-pipeline-coverage-v10 --next-limit 12
```

Current v11 merged coverage command keeps the v10 structural scope, but replaces the `GBC06_02.png#10-#13` stage directories with the top-aligned vertical text run:

```powershell
--layout-run-dir outputs/runs/phase4-gbc06-02-batch-10-13-layout-v9-top-align --cleanup-run-dir outputs/runs/phase6-gbc06-02-batch-10-13-region-fill-v9-top-align --preview-run-dir outputs/runs/phase7-8-gbc06-02-batch-10-13-preview-v9-top-align/runs/phase7-preview --export-run-dir outputs/runs/phase7-8-gbc06-02-batch-10-13-preview-v9-top-align/runs/phase8-export --run-id phase0-8-gbc06-pipeline-coverage-v11 --next-limit 12
```

Current v12 keeps the v11 structural scope and adds the Phase 8 Photoshop export quality audit as a coverage gate:

```powershell
--phase8-export-audit-run-dir outputs/runs/phase8-gbc06-02-batch-10-13-top-align-export-audit-v1 --run-id phase0-8-gbc06-pipeline-coverage-v12 --next-limit 12
```

Current v13 keeps the v12 structural scope and adds Phase 7 MIMO preview evaluation as a coverage quality gate. It passes the Phase 7 evaluation run paired with each retained preview run:

```powershell
--phase7-preview-evaluation-run-dir outputs/runs/phase7-8-gbc06-region-fill-layout-smoke/runs/phase7-evaluation
--phase7-preview-evaluation-run-dir outputs/runs/phase7-8-gbc06-bubble-batch-preview-v6/runs/phase7-evaluation
--phase7-preview-evaluation-run-dir outputs/runs/phase7-8-gbc06-bubble-batch-7-13-preview-v2/runs/phase7-evaluation
--phase7-preview-evaluation-run-dir outputs/runs/phase7-8-gbc06-batch-14-15-preview-v5/runs/phase7-evaluation
--phase7-preview-evaluation-run-dir outputs/runs/phase7-8-gbc06-batch-17-lama-white-preview-v1/runs/phase7-evaluation
--phase7-preview-evaluation-run-dir outputs/runs/phase7-8-gbc06-02-batch-1-3-preview-v3/runs/phase7-evaluation
--phase7-preview-evaluation-run-dir outputs/runs/phase7-8-gbc06-02-batch-4-6-preview-v2/runs/phase7-evaluation
--phase7-preview-evaluation-run-dir outputs/runs/phase7-8-gbc06-02-batch-7-9-preview-v2/runs/phase7-evaluation
--phase7-preview-evaluation-run-dir outputs/runs/phase7-8-gbc06-02-batch-10-13-preview-v9-top-align/runs/phase7-evaluation
--run-id phase0-8-gbc06-pipeline-coverage-v13 --next-limit 12
```

Current v14 keeps the v13 structural and quality scope, but the coverage tool now also reports Phase 1 records that have not yet entered Phase 2 detection. This fixes the previous blind spot where `next_records=[]` could be misread as no remaining project work, even though the Phase 1 manifest still contains many parsed labels outside the Phase 2 base set.

```powershell
--run-id phase0-8-gbc06-pipeline-coverage-v14-phase1-pending --next-limit 12
```

Current v15 adds support for multiple detection run directories and promotes the
diverse expansion records into the same coverage base instead of treating them
as side experiments. It keeps the v14 structural scope and adds:

```powershell
--detection-run-dir outputs/runs/phase2-gbc06-diverse-expansion-v2-color-light-text
--font-selection-run-dir outputs/runs/phase3-gbc06-diverse-06-18-mimo-font-selection-v1
--layout-run-dir outputs/runs/phase4-gbc06-18-phrase-aware-layout-v1
--angle-run-dir outputs/runs/phase5-gbc06-diverse-06-18-angle-v1
--cleanup-run-dir outputs/runs/phase6-gbc06-18-text-mask-bt-lama-large-d5-v1
--preview-run-dir outputs/runs/phase7-gbc06-18-phrase-aware-layout-d5-v1
--export-run-dir outputs/runs/phase8-gbc06-18-phrase-aware-d5-v1
--phase7-preview-evaluation-run-dir outputs/runs/phase7-gbc06-18-phrase-aware-layout-d5-eval-v1
--phase8-export-audit-run-dir outputs/runs/phase8-gbc06-18-phrase-aware-d5-audit-v1
--run-id phase0-8-gbc06-pipeline-coverage-v15-diverse-detection --next-limit 12
```

Current v17 keeps the v15 diverse base, adds the existing `GBC06_06.png#3`
diverse run chain plus the new text-mask LaMa validation chain, and restores the
previous `GBC06_01.png#17` layout input so older complete records remain in the
coverage base:

```powershell
--layout-run-dir outputs/runs/phase4-gbc06-batch-17-layout-polarity-white-v1
--layout-run-dir outputs/runs/phase4-gbc06-diverse-06-18-layout-v1
--layout-run-dir outputs/runs/phase4-gbc06-06-3-layout-v2
--cleanup-run-dir outputs/runs/phase6-gbc06-diverse-06-18-region-fill-v1
--cleanup-run-dir outputs/runs/phase6-gbc06-06-3-text-mask-bt-lama-large-v1
--preview-run-dir outputs/runs/phase7-8-gbc06-diverse-06-18-preview-v1/runs/phase7-preview
--preview-run-dir outputs/runs/phase7-8-gbc06-06-3-text-mask-lama-large-v1/runs/phase7-preview
--export-run-dir outputs/runs/phase7-8-gbc06-diverse-06-18-preview-v1/runs/phase8-export
--export-run-dir outputs/runs/phase7-8-gbc06-06-3-text-mask-lama-large-v1/runs/phase8-export
--phase7-preview-evaluation-run-dir outputs/runs/phase7-8-gbc06-diverse-06-18-preview-v1/runs/phase7-evaluation
--phase7-preview-evaluation-run-dir outputs/runs/phase7-8-gbc06-06-3-text-mask-lama-large-v1/runs/phase7-evaluation
--phase8-export-audit-run-dir outputs/runs/phase8-gbc06-06-3-text-mask-lama-large-audit-v1
--run-id phase0-8-gbc06-pipeline-coverage-v17-gbc06-06-complete --next-limit 12
```

Current v18 keeps the v17 structural and quality scope, adds the corrected
`GBC06_17.png#3` black-card target chain, and promotes that record from
Phase 2-only to complete Phase 1-8 coverage:

```powershell
--detection-run-dir outputs/runs/phase2-gbc06-17-3-target-fix-v3
--font-selection-run-dir outputs/runs/phase3-gbc06-17-3-mimo-font-selection-target-fix-v2
--layout-run-dir outputs/runs/phase4-gbc06-17-3-layout-target-fix-v4
--angle-run-dir outputs/runs/phase5-gbc06-17-3-angle-target-fix-v2
--cleanup-run-dir outputs/runs/phase6-gbc06-17-3-nonbubble-patchmatch-target-fix-v2
--preview-run-dir outputs/runs/phase7-8-gbc06-17-3-patchmatch-target-fix-v1/runs/phase7-preview
--export-run-dir outputs/runs/phase7-8-gbc06-17-3-patchmatch-target-fix-v1/runs/phase8-export
--phase7-preview-evaluation-run-dir outputs/runs/phase7-8-gbc06-17-3-patchmatch-target-fix-v1/runs/phase7-evaluation
--phase8-export-audit-run-dir outputs/runs/phase8-gbc06-17-3-patchmatch-target-fix-audit-v1
--run-id phase0-8-gbc06-pipeline-coverage-v18-gbc06-17-complete --next-limit 12
```

Current v19 keeps the v18 structural and quality scope, adds the CTA matched
large non-bubble title chain for `GBC06_29.png#2`, and promotes that record from
Phase 2-only to complete Phase 1-8 coverage:

```powershell
--detection-run-dir outputs/runs/phase2-gbc06-29-2-cta-mask-v1
--font-selection-run-dir outputs/runs/phase3-gbc06-29-2-mimo-font-selection-v1
--layout-run-dir outputs/runs/phase4-gbc06-29-2-layout-v3-large-title-conservative
--angle-run-dir outputs/runs/phase5-gbc06-29-2-angle-v1
--cleanup-run-dir outputs/runs/phase6-gbc06-29-2-cta-lama-v1
--preview-run-dir outputs/runs/phase7-8-gbc06-29-2-cta-lama-large-title-v3/runs/phase7-preview
--export-run-dir outputs/runs/phase7-8-gbc06-29-2-cta-lama-large-title-v3/runs/phase8-export
--phase7-preview-evaluation-run-dir outputs/runs/phase7-8-gbc06-29-2-cta-lama-large-title-v3/runs/phase7-evaluation
--phase8-export-audit-run-dir outputs/runs/phase8-gbc06-29-2-cta-lama-large-title-audit-v3
--run-id phase0-8-gbc06-pipeline-coverage-v19-gbc06-29-complete --next-limit 12
```

Current v20 moves the long accumulated command into a strict registry entry,
adds the `GBC06_33.png#1` context-font validation chain, and fails early if any
listed run directory is missing its stage artifact:

```powershell
python experiments/pipeline_coverage_report.py --registry-file docs/pipeline-runs.gbc06.json --registry-entry phase0-8-gbc06-v20-gbc06-33-complete --output-root outputs/runs
```

Current v21 keeps the same registry-backed structural scope, but adds
`next_experiments` to the generated JSON and Markdown report. This keeps the
old `next_records` meaning intact for records already in the detection base,
while also surfacing Phase 1 parsed records that still need CTA detection as
the next experiment queue:

```powershell
python experiments/pipeline_coverage_report.py --registry-file docs/pipeline-runs.gbc06.json --registry-entry phase0-8-gbc06-v20-gbc06-33-complete --output-root outputs/runs --run-id phase0-8-gbc06-pipeline-coverage-v21-next-experiments --next-limit 12
```

Current v22 keeps v20 as the accepted complete baseline, uses registry
inheritance to append one new CTA detection run, and promotes
`GBC06_03.png#1-#3` into the detection base without copying the long v20 run
list:

```powershell
python experiments/pipeline_coverage_report.py --registry-file docs/pipeline-runs.gbc06.json --registry-entry phase0-8-gbc06-v22-gbc06-03-detection --output-root outputs/runs --next-limit 12
```

Current v23 extends v22 with the real MIMO Phase 3 font-selection run for
`GBC06_03.png#1-#3`:

```powershell
python experiments/pipeline_coverage_report.py --registry-file docs/pipeline-runs.gbc06.json --registry-entry phase0-8-gbc06-v23-gbc06-03-font-selection --output-root outputs/runs --next-limit 12
```

Current v26 extends the accepted v25 `GBC06_03.png#1-#3` chain with
`GBC06_03.png#4-#6`. The key change is that `#5` now uses the validated
`phase6-gbc06-03-5-fallback-gpt-image2-v14-text-pixels-prompt-only` result
instead of the older v4 GPT crop:

```powershell
python experiments/pipeline_coverage_report.py --registry-file docs/pipeline-runs.gbc06.json --registry-entry phase0-8-gbc06-v26-gbc06-03-4-6-gpt-v14 --output-root outputs/runs --next-limit 12
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
- `outputs/runs/phase0-8-gbc06-pipeline-coverage-v8/pipeline-coverage.json`
- `outputs/runs/phase0-8-gbc06-pipeline-coverage-v8/reports/pipeline-coverage-report.md`
- `outputs/runs/phase0-8-gbc06-pipeline-coverage-v9/pipeline-coverage.json`
- `outputs/runs/phase0-8-gbc06-pipeline-coverage-v9/reports/pipeline-coverage-report.md`
- `outputs/runs/phase0-8-gbc06-pipeline-coverage-v10/pipeline-coverage.json`
- `outputs/runs/phase0-8-gbc06-pipeline-coverage-v10/reports/pipeline-coverage-report.md`
- `outputs/runs/phase0-8-gbc06-pipeline-coverage-v11/pipeline-coverage.json`
- `outputs/runs/phase0-8-gbc06-pipeline-coverage-v11/reports/pipeline-coverage-report.md`
- `outputs/runs/phase0-8-gbc06-pipeline-coverage-v12/pipeline-coverage.json`
- `outputs/runs/phase0-8-gbc06-pipeline-coverage-v12/reports/pipeline-coverage-report.md`
- `outputs/runs/phase0-8-gbc06-pipeline-coverage-v13/pipeline-coverage.json`
- `outputs/runs/phase0-8-gbc06-pipeline-coverage-v13/reports/pipeline-coverage-report.md`
- `outputs/runs/phase0-8-gbc06-pipeline-coverage-v14-phase1-pending/pipeline-coverage.json`
- `outputs/runs/phase0-8-gbc06-pipeline-coverage-v14-phase1-pending/reports/pipeline-coverage-report.md`
- `outputs/runs/phase0-8-gbc06-pipeline-coverage-v15-diverse-detection/pipeline-coverage.json`
- `outputs/runs/phase0-8-gbc06-pipeline-coverage-v15-diverse-detection/reports/pipeline-coverage-report.md`
- `outputs/runs/phase0-8-gbc06-pipeline-coverage-v17-gbc06-06-complete/pipeline-coverage.json`
- `outputs/runs/phase0-8-gbc06-pipeline-coverage-v17-gbc06-06-complete/reports/pipeline-coverage-report.md`
- `outputs/runs/phase0-8-gbc06-pipeline-coverage-v18-gbc06-17-complete/pipeline-coverage.json`
- `outputs/runs/phase0-8-gbc06-pipeline-coverage-v18-gbc06-17-complete/reports/pipeline-coverage-report.md`
- `outputs/runs/phase0-8-gbc06-pipeline-coverage-v19-gbc06-29-complete/pipeline-coverage.json`
- `outputs/runs/phase0-8-gbc06-pipeline-coverage-v19-gbc06-29-complete/reports/pipeline-coverage-report.md`
- `outputs/runs/phase0-8-gbc06-pipeline-coverage-v20-gbc06-33-complete/pipeline-coverage.json`
- `outputs/runs/phase0-8-gbc06-pipeline-coverage-v20-gbc06-33-complete/reports/pipeline-coverage-report.md`
- `outputs/runs/phase0-8-gbc06-pipeline-coverage-v21-next-experiments/pipeline-coverage.json`
- `outputs/runs/phase0-8-gbc06-pipeline-coverage-v21-next-experiments/reports/pipeline-coverage-report.md`
- `outputs/runs/phase0-8-gbc06-pipeline-coverage-v26-gbc06-03-4-6-gpt-v14/pipeline-coverage.json`
- `outputs/runs/phase0-8-gbc06-pipeline-coverage-v26-gbc06-03-4-6-gpt-v14/reports/pipeline-coverage-report.md`
- `outputs/runs/phase2-gbc06-03-batch-1-3-cta-detection-v1/detections.jsonl`
- `outputs/runs/phase2-gbc06-03-batch-1-3-cta-detection-v1/debug/detection/GBC06_03-1.png`
- `outputs/runs/phase2-gbc06-03-batch-1-3-cta-detection-v1/debug/detection/GBC06_03-2.png`
- `outputs/runs/phase2-gbc06-03-batch-1-3-cta-detection-v1/debug/detection/GBC06_03-3.png`
- `outputs/runs/phase2-gbc06-03-batch-1-3-cta-detection-v1/debug/detection/GBC06_03-1-3-grid.png`
- `outputs/runs/phase0-8-gbc06-pipeline-coverage-v22-gbc06-03-detection/pipeline-coverage.json`
- `outputs/runs/phase0-8-gbc06-pipeline-coverage-v22-gbc06-03-detection/reports/pipeline-coverage-report.md`
- `outputs/runs/phase3-gbc06-03-batch-1-3-font-comparison/font-comparisons.jsonl`
- `outputs/runs/phase3-gbc06-03-batch-1-3-font-comparison/debug/font_comparison/GBC06_03-1-3-font-grid.png`
- `outputs/runs/phase3-gbc06-03-batch-1-3-mimo-font-selection/font-selections.jsonl`
- `outputs/runs/phase3-gbc06-03-batch-1-3-mimo-font-selection/reports/api-calls.jsonl`
- `outputs/runs/phase0-8-gbc06-pipeline-coverage-v23-gbc06-03-font-selection/pipeline-coverage.json`
- `outputs/runs/phase0-8-gbc06-pipeline-coverage-v23-gbc06-03-font-selection/reports/pipeline-coverage-report.md`
- `outputs/runs/phase5-gbc06-03-batch-1-3-angle/angle-results.jsonl`
- `outputs/runs/phase4-gbc06-03-batch-1-3-layout-v3/layout-results.jsonl`
- `outputs/runs/phase4-gbc06-03-batch-1-3-layout-v3/visuals/layout-v1-v2-v3-comparison-grid.png`
- `outputs/runs/phase4-gbc06-03-batch-1-3-layout-v3-mimo-validation/layout-validation.jsonl`
- `outputs/runs/phase0-8-gbc06-pipeline-coverage-v24-gbc06-03-layout-angle/pipeline-coverage.json`
- `outputs/runs/phase0-8-gbc06-pipeline-coverage-v24-gbc06-03-layout-angle/reports/pipeline-coverage-report.md`

`outputs/` remains ignored by Git. The source-backed summary below records the key numbers so the experiment is traceable in the repository.

## Current Coverage

Base stage: `phase2_detection`

```text
base_record_count=38
complete_record_count=35
incomplete_record_count=3
```

Stage counts:

```text
phase1_labelplus       covered=38 missing=0
phase2_detection       covered=38 missing=0
phase3_font_selection  covered=38 missing=0
phase4_layout          covered=38 missing=0
phase5_angle           covered=38 missing=0
phase6_cleanup         covered=35 missing=3
phase7_preview         covered=35 missing=3
phase8_export          covered=35 missing=3
```

Quality audits:

```text
phase7_preview evaluations=15 evaluated=15 usable=15/15 failed=0 low_score=0 records=35 record_issues=0
phase8_export audits=6 passed=6/6 records=9 vertical_top_layers=8 missing_anchor=0 unexpected_anchor=0 record_issues=0 missing_jsx_anchor_logic=0
```

Group coverage:

```text
框内: base=33 complete=30
框外: base=5  complete=5
```

## Next Records

The v13 coverage report counts these records as complete across all tracked stages and the attached Phase 7/8 quality gates:

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
GBC06_01.png#14
GBC06_01.png#15
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
GBC06_02.png#10
GBC06_02.png#11
GBC06_02.png#12
GBC06_02.png#13
```

The v20 registry report promotes all five diverse expansion records into the
coverage base. `GBC06_18.png#3`, `GBC06_06.png#3`, `GBC06_17.png#3`,
`GBC06_29.png#2`, and `GBC06_33.png#1` are complete across Phase 1-8 and all
attached quality gates. There are no remaining next records inside the current
35-record detection base.

```text
next_records=[]
```

The v20 report also keeps the remaining parsed-but-undetected Phase 1 scope
explicit:

```text
phase1_pending_detection_count=145
```

The v21 report turns the first pending Phase 1 records into an explicit
experiment queue while keeping `next_records=[]` for the current complete
35-record detection base:

```text
next_experiments[0]=GBC06_02.png#14  action=run_cta_detection  stage=phase2_detection  reason=phase1_pending_detection
next_experiments[1]=GBC06_03.png#1   action=run_cta_detection  stage=phase2_detection  reason=phase1_pending_detection
next_experiments[2]=GBC06_03.png#2   action=run_cta_detection  stage=phase2_detection  reason=phase1_pending_detection
```

The v22 report adds a real CTA detection batch for `GBC06_03.png#1-#3`.
All three records have unique CTA/CTD mask matches within the 20px threshold:

```text
GBC06_03.png#1  bbox=[1207,236,1244,425]  distance_px=8.062   translated_text=你要去哪里？
GBC06_03.png#2  bbox=[657,237,693,367]    distance_px=10.198  translated_text=我要回家
GBC06_03.png#3  bbox=[1205,768,1243,891]  distance_px=14.000  translated_text=差不多得了
```

The three newly detected records are now the first structural gaps in the
coverage report:

```text
next_records[0]=GBC06_03.png#1  first_missing_stage=phase3_font_selection
next_records[1]=GBC06_03.png#2  first_missing_stage=phase3_font_selection
next_records[2]=GBC06_03.png#3  first_missing_stage=phase3_font_selection
phase1_pending_detection_count=142
```

The v23 report adds real MIMO font selection for the same three records:

```text
GBC06_03.png#1  selected=[toolbox]文黑体-简繁-Bold(v2.4).ttf  confidence=0.95
GBC06_03.png#2  selected=[toolbox]POP1-简繁(v2.5).ttf       confidence=0.90
GBC06_03.png#3  selected=[toolbox]与墨体-简体-Bold(v2.4).ttf  confidence=0.90
```

After v23, all three records moved past Phase 3 and waited on layout:

```text
next_records[0]=GBC06_03.png#1  first_missing_stage=phase4_layout
next_records[1]=GBC06_03.png#2  first_missing_stage=phase4_layout
next_records[2]=GBC06_03.png#3  first_missing_stage=phase4_layout
phase3_font_selection covered=38 missing=0
```

The v24 report adds Phase 5 angle estimation and the accepted Phase 4 layout
run for `GBC06_03.png#1-#3`. The initial layout `v1` was rejected by manual
review because the vertical text used tight bbox advance and looked cramped
despite `overflow_ratio=0.0`. The accepted `v3` layout uses optical cell
advance for vertical text and was accepted by MIMO layout validation for all
three records:

```text
GBC06_03.png#1  font_size=33  measured=35x186  target=37x189  angle=0.0  mimo=accepted
GBC06_03.png#2  font_size=34  measured=34x128  target=36x130  angle=0.0  mimo=accepted
GBC06_03.png#3  font_size=25  measured=25x121  target=38x123  angle=0.0  mimo=accepted
```

After v24, Phase 4 and Phase 5 are covered for all 38 records in the detection
base. The three `GBC06_03.png` records now wait on cleanup:

```text
phase4_layout covered=38 missing=0
phase5_angle covered=38 missing=0
next_records[0]=GBC06_03.png#1  first_missing_stage=phase6_cleanup
next_records[1]=GBC06_03.png#2  first_missing_stage=phase6_cleanup
next_records[2]=GBC06_03.png#3  first_missing_stage=phase6_cleanup
```

The v25 report closes `GBC06_03.png#1-#3` through Phase 8. The first integrated
preview run received MIMO score `10`, but manual full-page review found that
`GBC06_03.png#3` still left the adjacent Japanese text `しろ` in the speech
bubble. The root cause was a CTA component grouping gap: the original v1
detection matched only `component-0007+component-0008` with bbox
`[1205,768,1243,891]`, while the complete bubble text also needed adjacent
components `component-0004+component-0005+component-0006`.

The accepted v25 chain therefore replaces the GBC06_03 detection, layout,
cleanup, preview, and export dirs with the CTA-merged runs:

```text
phase2-gbc06-03-batch-1-3-cta-detection-v2
phase4-gbc06-03-batch-1-3-layout-v4-cta-merged
phase6-gbc06-03-batch-1-3-region-fill-v2-cta-merged
phase7-8-gbc06-03-batch-1-3-preview-v3-context-eval/runs/phase7-preview
phase7-8-gbc06-03-batch-1-3-preview-v3-context-eval/runs/phase8-export
phase7-8-gbc06-03-batch-1-3-preview-v3-context-eval/runs/phase7-evaluation
```

The accepted `#3` detection bbox is `[1170,735,1243,891]` and the merged
component id is
`component-0004+component-0005+component-0006+component-0007+component-0008`.
The v25 Phase 7 evaluator also uses local context before/after crops instead of
only tight crops, so adjacent leftover Japanese text is visible to MIMO instead
of being hidden outside the review image. The final v3 context evaluation scored
`10`, `usable=true`, with `original_text_removed=true`,
`art_preserved=true`, and `lettering_readable=true`.

Observed v25 coverage result:

```text
base_record_count=38
complete_record_count=38
incomplete_record_count=0
phase1_labelplus covered=38 missing=0
phase2_detection covered=38 missing=0
phase3_font_selection covered=38 missing=0
phase4_layout covered=38 missing=0
phase5_angle covered=38 missing=0
phase6_cleanup covered=38 missing=0
phase7_preview covered=38 missing=0
phase8_export covered=38 missing=0
phase7_preview evaluations=16 usable=16/16 failed=0 low_score=0 records=38 record_issues=0
phase8_export audits=6 passed=6/6 records=9 record_issues=0
phase1_pending_detection_count=142
next_records=[]
next_experiments[0]=GBC06_02.png#14
next_experiments[1]=GBC06_03.png#4
```

The v26 report promotes the next `GBC06_03.png#4-#6` batch through Phase 8.
`#4` and `#6` use the existing text-mask inpaint cleanup followed by normal
editable text overlays. `#5` is the non-bubble fallback case and now uses the
accepted v14 `gpt-image-2` text-pixel masked replacement:

```text
phase2-gbc06-03-batch-4-6-cta-detection-v3-threshold40-merged
phase3-gbc06-03-batch-4-6-mimo-font-selection
phase4-gbc06-03-batch-4-6-layout-v1
phase5-gbc06-03-batch-4-6-angle
phase6-gbc06-03-batch-4-6-text-mask-inpaint-v1
phase6-gbc06-03-5-fallback-gpt-image2-v14-text-pixels-prompt-only
phase7-gbc06-03-batch-4-6-with-5-gpt-v14-preview-v1
phase8-gbc06-03-batch-4-6-with-5-gpt-v14-export-v1
phase7-gbc06-03-batch-4-6-with-5-gpt-v14-eval-v1
phase8-gbc06-03-batch-4-6-with-5-gpt-v14-audit-v1
```

The v26 Phase 7 manifest confirms that `GBC06_03.png#5` uses:

```text
cleanup_method=gpt_image2_masked_edit
cleanup_crop_path=outputs/runs/phase6-gbc06-03-5-fallback-gpt-image2-v14-text-pixels-prompt-only/fallback_replacement_crop/GBC06-03-png-5.png
text_overlay_required=false
gpt_replacement_quality.accepted=true
```

MIMO evaluated the full `#4-#6` preview at `score=8`, `usable=true`,
`original_text_removed=true`, `art_preserved=true`, and
`lettering_readable=true`. It reported two minor issues: simplified Chinese in
the translated text, and `#5` slightly obscuring the speech-bubble tail, while
still judging the page usable. The Phase 8 manifest exports two editable text
layers for `#4` and `#6`; `#5` appears only in `repair_sources[]` and the
page-level `修复图像`, because its translated text is already baked into the
quality-accepted GPT replacement crop. The Phase 8 audit passed with two
vertical top anchors and no record issues.

For this direct GPT replacement route, the fallback visual locator bbox is
treated as a text-containing locator hint rather than a clean inpainting
boundary. It may include non-target art or nearby characters as long as it
contains the intended source text; the `gpt-image-2` masked-edit prompt and text
pixel mask carry the constraint that only text content should be changed.
Coverage therefore marks `GBC06_03.png#5` complete without Phase 3 font
selection, Phase 4 layout, or Phase 5 angle records only when Phase 6 cleanup,
Phase 7 preview, and Phase 8 export evidence all exist.

Observed v26 coverage result:

```text
base_record_count=41
complete_record_count=41
incomplete_record_count=0
phase1_labelplus covered=41 missing=0
phase2_detection covered=41 missing=0
phase3_font_selection covered=40 missing=1
phase4_layout covered=40 missing=1
phase5_angle covered=40 missing=1
phase6_cleanup covered=41 missing=0
phase7_preview covered=41 missing=0
phase8_export covered=41 missing=0
GBC06_03.png#5 route_skipped_stages=phase3_font_selection,phase4_layout,phase5_angle
phase6_gpt_replacement checked=1 failures=0 record_issues=0
phase7_preview evaluations=17 usable=17/17 failed=0 low_score=0 records=41 record_issues=0
phase8_export audits=7 passed=7/7 records=11 record_issues=0
phase1_pending_detection_count=139
next_records=[]
next_experiments[0]=GBC06_02.png#14
next_experiments[1]=GBC06_03.png#7
```

The v27 report supersedes the v26 `GBC06_03.png#5` direct replacement evidence
with the latest v18 loose-bbox/text-pixel-mask GPT result. The coverage entry
keeps v26 history and appends the v18 Phase 6 cleanup, Phase 6 replacement
quality, integrated Phase 7/8 smoke, MIMO Phase 7 evaluation, and Phase 8 export
audit:

```text
phase6-gbc06-03-5-fallback-gpt-image2-v18-accepted-bbox-no-refine
phase6-gbc06-03-5-fallback-gpt-image2-v18-quality
phase7-8-gbc06-03-batch-4-6-with-5-gpt-v18-preview-v1
phase8-gbc06-03-batch-4-6-with-5-gpt-v18-audit-v1
phase0-8-gbc06-pipeline-coverage-v27-gbc06-03-4-6-gpt-v18
```

The v18 integrated Phase 7/8 smoke uses:

```text
phase2-gbc06-03-batch-4-6-cta-detection-v3-threshold40-merged
phase3-gbc06-03-batch-4-6-mimo-font-selection
phase4-gbc06-03-batch-4-6-layout-v1
phase5-gbc06-03-batch-4-6-angle
phase6-gbc06-03-batch-4-6-text-mask-inpaint-v1
phase6-gbc06-03-5-fallback-gpt-image2-v18-accepted-bbox-no-refine
phase6-gbc06-03-5-fallback-gpt-image2-v18-quality
```

MIMO evaluated the v18 full `GBC06_03.png#4-#6` page preview at `score=9`,
`usable=true`, `original_text_removed=true`, `art_preserved=true`, and
`lettering_readable=true`, with `issues=[]`. The Phase 8 manifest exports two
editable Photoshop text layers for `#4` and `#6`, and keeps `#5` only as a
quality-accepted `gpt_image2_masked_edit` repair source in the page-level
`修复图像`. The `#5` repair source stores the loose locator validation:
`tight_enough=false`, `needs_tighter_edit_mask=false`, and reasoning that the
bbox includes a character head/background while fully containing the intended
Japanese text. The Phase 8 export audit passed with two vertical top anchors and
no record issues.

Observed v27 coverage result:

```text
base_record_count=41
complete_record_count=41
incomplete_record_count=0
phase1_labelplus covered=41 missing=0
phase2_detection covered=41 missing=0
phase3_font_selection covered=40 missing=1
phase4_layout covered=40 missing=1
phase5_angle covered=40 missing=1
phase6_cleanup covered=41 missing=0
phase7_preview covered=41 missing=0
phase8_export covered=41 missing=0
GBC06_03.png#5 route_skipped_stages=phase3_font_selection,phase4_layout,phase5_angle
phase6_gpt_replacement checked=2 failures=0 record_issues=0
phase7_preview evaluations=18 usable=18/18 failed=0 low_score=0 records=41 record_issues=0
phase8_export audits=8 passed=8/8 records=11 record_issues=0
phase1_pending_detection_count=139
next_records=[]
next_experiments[0]=GBC06_02.png#14
next_experiments[1]=GBC06_03.png#7
```

The v28 report promotes `GBC06_03.png#7`, the next speech-bubble record after
the v18 direct-GPT fallback update, through the full Phase 2-8 chain:

```text
phase2-gbc06-03-7-cta-detection-v1
phase3-gbc06-03-7-font-comparison
phase3-gbc06-03-7-mimo-font-selection
phase5-gbc06-03-7-angle
phase4-gbc06-03-7-layout-v1
phase6-gbc06-03-7-region-fill-v1
phase7-8-gbc06-03-7-preview-v1
phase8-gbc06-03-7-export-audit-v1
```

The real commands were:

```powershell
python experiments/phase2_detect_text_regions.py --labelplus-file "GBC06 (已翻 斗笠)\翻译_0.txt" --output-root outputs/runs --run-id phase2-gbc06-03-7-cta-detection-v1 --sample-limit 1 --record-id "GBC06_03.png#7" --detection-strategy cta_mask --ctd-max-edge-distance-px 20
python experiments/phase3_font_comparison.py --labelplus-file "GBC06 (已翻 斗笠)\翻译_0.txt" --detection-run-dir outputs/runs/phase2-gbc06-03-7-cta-detection-v1 --font-dir "工具箱漫画字体V2.5" --output-root outputs/runs --run-id phase3-gbc06-03-7-font-comparison --sample-limit 1 --font-limit 12 --record-id "GBC06_03.png#7"
python experiments/phase3_mimo_font_selection.py --input-run-dir outputs/runs/phase3-gbc06-03-7-font-comparison --output-root outputs/runs --run-id phase3-gbc06-03-7-mimo-font-selection --sample-limit 1 --record-id "GBC06_03.png#7"
python experiments/phase5_orientation_angle.py --detection-run-dir outputs/runs/phase2-gbc06-03-7-cta-detection-v1 --output-root outputs/runs --run-id phase5-gbc06-03-7-angle --sample-limit 1 --record-id "GBC06_03.png#7"
python experiments/phase4_layout_search.py --selection-run-dir outputs/runs/phase3-gbc06-03-7-mimo-font-selection --angle-run-dir outputs/runs/phase5-gbc06-03-7-angle --detection-run-dir outputs/runs/phase2-gbc06-03-7-cta-detection-v1 --output-root outputs/runs --run-id phase4-gbc06-03-7-layout-v1 --sample-limit 1 --record-id "GBC06_03.png#7"
python experiments/phase6_bubble_cleanup.py --detection-run-dir outputs/runs/phase2-gbc06-03-7-cta-detection-v1 --layout-run-dir outputs/runs/phase4-gbc06-03-7-layout-v1 --output-root outputs/runs --run-id phase6-gbc06-03-7-region-fill-v1 --sample-limit 1 --cleanup-method region_fill --record-id "GBC06_03.png#7"
python experiments/phase7_8_integrated_smoke.py --detection-run-dir outputs/runs/phase2-gbc06-03-7-cta-detection-v1 --cleanup-run-dir outputs/runs/phase6-gbc06-03-7-region-fill-v1 --layout-run-dir outputs/runs/phase4-gbc06-03-7-layout-v1 --font-selection-run-dir outputs/runs/phase3-gbc06-03-7-mimo-font-selection --output-root outputs/runs --run-id phase7-8-gbc06-03-7-preview-v1 --sample-limit 1
python experiments/phase8_export_quality_audit.py --phase8-run-dir outputs/runs/phase7-8-gbc06-03-7-preview-v1/runs/phase8-export --output-root outputs/runs --run-id phase8-gbc06-03-7-export-audit-v1
```

Key real-sample results:

```text
phase2 status=ok
phase2 selected_text_box_xyxy=[300,968,341,1208]
phase2 cta_component=component-0016+component-0017+component-0018
phase3 selected_font=[toolbox]拙黑体-简体(v2.4).ttf confidence=0.95
phase5 orientation=vertical selected_angle=-0.3 confidence=0.989
phase4 font_size=36 measured=36x238 target=41x240 angle=0.0 vertical_align=top
phase6 method=bubble_region_fill status=cleaned
phase7 MIMO score=10 usable=true original_text_removed=true art_preserved=true lettering_readable=true issues=[]
phase8 exported_text_layer_count=1
phase8 audit passed=true vertical_top_layer_count=1 record_issue_count=0 anchor_y=968
```

Observed v28 coverage result:

```text
base_record_count=42
complete_record_count=42
incomplete_record_count=0
phase1_labelplus covered=42 missing=0
phase2_detection covered=42 missing=0
phase3_font_selection covered=41 missing=1
phase4_layout covered=41 missing=1
phase5_angle covered=41 missing=1
phase6_cleanup covered=42 missing=0
phase7_preview covered=42 missing=0
phase8_export covered=42 missing=0
GBC06_03.png#5 route_skipped_stages=phase3_font_selection,phase4_layout,phase5_angle
phase6_gpt_replacement checked=2 failures=0 record_issues=0
phase7_preview evaluations=19 usable=19/19 failed=0 low_score=0 records=42 record_issues=0
phase8_export audits=9 passed=9/9 records=12 record_issues=0
phase1_pending_detection_count=138
next_records=[]
next_experiments[0]=GBC06_02.png#14
next_experiments[1]=GBC06_03.png#8
```

The v29 report promotes the existing accepted `GBC06_02.png#14` GPT SFX direct
replacement chain into the global registry after adding the two missing
independent quality artifacts:

```text
phase2-gbc06-02-14-cta-detection-v1
phase6-gbc06-02-14-fallback-gpt-image2-v3-sfx-recovery
phase6-gbc06-02-14-gpt-v3-sfx-recovery-quality
phase7-8-gbc06-02-14-gpt-v3-sfx-quality-gate
phase7-gbc06-02-14-gpt-v3-sfx-quality-gate-eval-v1
phase8-gbc06-02-14-gpt-v3-sfx-quality-gate-audit-v1
```

The two follow-up quality commands were:

```powershell
python experiments/phase7_preview_evaluate.py --preview-run-dir outputs/runs/phase7-8-gbc06-02-14-gpt-v3-sfx-quality-gate/runs/phase7-preview --output-root outputs/runs --run-id phase7-gbc06-02-14-gpt-v3-sfx-quality-gate-eval-v1 --sample-limit 1
python experiments/phase8_export_quality_audit.py --phase8-run-dir outputs/runs/phase7-8-gbc06-02-14-gpt-v3-sfx-quality-gate/runs/phase8-export --output-root outputs/runs --run-id phase8-gbc06-02-14-gpt-v3-sfx-quality-gate-audit-v1
```

Key `GBC06_02.png#14` result:

```text
phase2 status=fallback_required route=mimo_locator_gpt_image2_masked_edit
phase6 status=cleaned replacement_method=gpt_image2_masked_edit text_overlay_required=false
fallback_locator_validation.status=accepted semantic_correct=true tight_enough=false
gpt_image2_edit.status=ok
phase6 replacement quality score=10 usable=true exact_text_correct=true simplified_chinese_correct=true outside_mask_preserved=true issues=[]
phase7 MIMO score=8 usable=true original_text_removed=true art_preserved=true lettering_readable=true issues=[]
phase8 export has repair_source effective_method=gpt_image2_masked_edit and no editable text layer, as expected for direct GPT replacement
phase8 audit passed=true record_count=0 record_issue_count=0 jsx_anchor_logic_present=true
```

This result follows the active non-bubble GPT fallback policy: the accepted
locator bbox can be loose as long as it contains the intended original text;
the edit scope is constrained by the `text_pixels` mask and the GPT prompt. The
`tight_enough=false` diagnostic did not block the replacement because the
semantic target, exact Chinese text, and outside-mask preservation checks passed.

Observed v29 coverage result:

```text
base_record_count=43
complete_record_count=43
incomplete_record_count=0
phase1_labelplus covered=43 missing=0
phase2_detection covered=43 missing=0
phase3_font_selection covered=41 missing=2
phase4_layout covered=41 missing=2
phase5_angle covered=41 missing=2
phase6_cleanup covered=43 missing=0
phase7_preview covered=43 missing=0
phase8_export covered=43 missing=0
GBC06_02.png#14 route_skipped_stages=phase3_font_selection,phase4_layout,phase5_angle
GBC06_03.png#5 route_skipped_stages=phase3_font_selection,phase4_layout,phase5_angle
phase6_gpt_replacement checked=3 failures=0 record_issues=0
phase7_preview evaluations=20 usable=20/20 failed=0 low_score=0 records=43 record_issues=0
phase8_export audits=10 passed=10/10 records=12 record_issues=0
phase1_pending_detection_count=137
next_records=[]
next_experiments[0]=GBC06_03.png#8
next_experiments[1]=GBC06_03.png#9
```

The v30 report promotes `GBC06_03.png#8`, a speech-bubble vertical text record,
through the full Phase 2-8 chain and records the small-angle snap fix used for
the final lettering:

```text
phase2-gbc06-03-8-cta-detection-v1
phase3-gbc06-03-8-font-comparison
phase3-gbc06-03-8-mimo-font-selection
phase5-gbc06-03-8-angle
phase4-gbc06-03-8-layout-v2-angle-snap
phase6-gbc06-03-8-region-fill-v2-angle-snap
phase7-8-gbc06-03-8-preview-v2-angle-snap
phase8-gbc06-03-8-export-audit-v2-angle-snap
```

The real commands were:

```powershell
python experiments/phase2_detect_text_regions.py --labelplus-file "GBC06 (已翻 斗笠)\翻译_0.txt" --output-root outputs/runs --run-id phase2-gbc06-03-8-cta-detection-v1 --sample-limit 1 --record-id "GBC06_03.png#8" --detection-strategy cta_mask --ctd-max-edge-distance-px 20
python experiments/phase3_font_comparison.py --labelplus-file "GBC06 (已翻 斗笠)\翻译_0.txt" --detection-run-dir outputs/runs/phase2-gbc06-03-8-cta-detection-v1 --font-dir "工具箱漫画字体V2.5" --output-root outputs/runs --run-id phase3-gbc06-03-8-font-comparison --sample-limit 1 --font-limit 12 --record-id "GBC06_03.png#8"
python experiments/phase3_mimo_font_selection.py --input-run-dir outputs/runs/phase3-gbc06-03-8-font-comparison --output-root outputs/runs --run-id phase3-gbc06-03-8-mimo-font-selection --sample-limit 1 --record-id "GBC06_03.png#8"
python experiments/phase5_orientation_angle.py --detection-run-dir outputs/runs/phase2-gbc06-03-8-cta-detection-v1 --output-root outputs/runs --run-id phase5-gbc06-03-8-angle --sample-limit 1 --record-id "GBC06_03.png#8"
python experiments/phase4_layout_search.py --selection-run-dir outputs/runs/phase3-gbc06-03-8-mimo-font-selection --angle-run-dir outputs/runs/phase5-gbc06-03-8-angle --detection-run-dir outputs/runs/phase2-gbc06-03-8-cta-detection-v1 --output-root outputs/runs --run-id phase4-gbc06-03-8-layout-v2-angle-snap --sample-limit 1 --record-id "GBC06_03.png#8"
python experiments/phase6_bubble_cleanup.py --detection-run-dir outputs/runs/phase2-gbc06-03-8-cta-detection-v1 --layout-run-dir outputs/runs/phase4-gbc06-03-8-layout-v2-angle-snap --output-root outputs/runs --run-id phase6-gbc06-03-8-region-fill-v2-angle-snap --sample-limit 1 --cleanup-method region_fill --record-id "GBC06_03.png#8"
python experiments/phase7_8_integrated_smoke.py --detection-run-dir outputs/runs/phase2-gbc06-03-8-cta-detection-v1 --cleanup-run-dir outputs/runs/phase6-gbc06-03-8-region-fill-v2-angle-snap --layout-run-dir outputs/runs/phase4-gbc06-03-8-layout-v2-angle-snap --font-selection-run-dir outputs/runs/phase3-gbc06-03-8-mimo-font-selection --output-root outputs/runs --run-id phase7-8-gbc06-03-8-preview-v2-angle-snap --sample-limit 1
python experiments/phase8_export_quality_audit.py --phase8-run-dir outputs/runs/phase7-8-gbc06-03-8-preview-v2-angle-snap/runs/phase8-export --output-root outputs/runs --run-id phase8-gbc06-03-8-export-audit-v2-angle-snap
```

Key real-sample results:

```text
phase2 status=ok
phase2 selected_text_box_xyxy=[1157,1341,1272,1560]
phase2 cta_component=component-0020+component-0021+component-0022+component-0023+component-0024+component-0025+component-0026
phase3 selected_font=[toolbox]文黑体-简繁-Bold(v2.4).ttf confidence=0.95
phase5 orientation=vertical selected_angle=-6.3 confidence=0.823
phase4 angle_snap applied: angle_degrees=0.0, font_size=32, measured=33x215, target=115x219, vertical_align=top
phase6 method=bubble_region_fill status=cleaned
phase7 MIMO score=9 usable=true original_text_removed=true art_preserved=true lettering_readable=true issues=[]
phase8 exported_text_layer_count=1
phase8 audit passed=true vertical_top_layer_count=1 record_issue_count=0 anchor_y=1341
```

The source crop's PCA estimate was `-6.3` degrees, but visual review showed this
was a normal vertical manga bubble rather than a clearly tilted lettering block.
Phase 4 now snaps small high-confidence `框内` vertical angles to `0.0` before
rendering, preserving the Phase 5 diagnostic while avoiding visibly rotated
Chinese lettering. The preview contact sheet is
`outputs/runs/phase7-8-gbc06-03-8-preview-v2-angle-snap/runs/phase7-preview/debug/evaluation_contact_sheets/GBC06-03-png.png`.

Observed v30 coverage result:

```text
base_record_count=44
complete_record_count=44
incomplete_record_count=0
phase1_labelplus covered=44 missing=0
phase2_detection covered=44 missing=0
phase3_font_selection covered=42 missing=2
phase4_layout covered=42 missing=2
phase5_angle covered=42 missing=2
phase6_cleanup covered=44 missing=0
phase7_preview covered=44 missing=0
phase8_export covered=44 missing=0
GBC06_02.png#14 route_skipped_stages=phase3_font_selection,phase4_layout,phase5_angle
GBC06_03.png#5 route_skipped_stages=phase3_font_selection,phase4_layout,phase5_angle
phase6_gpt_replacement checked=3 failures=0 record_issues=0
phase7_preview evaluations=21 usable=21/21 failed=0 low_score=0 records=44 record_issues=0
phase8_export audits=11 passed=11/11 records=13 record_issues=0
phase1_pending_detection_count=136
next_records=[]
next_experiments[0]=GBC06_03.png#9
next_experiments[1]=GBC06_03.png#10
```

The first `next-limit=12` Phase 1 records missing detection in v17 are:

```text
GBC06_02.png#14  框外  GBC06_02.png
GBC06_03.png#1   框内  GBC06_03.png
GBC06_03.png#2   框内  GBC06_03.png
GBC06_03.png#3   框内  GBC06_03.png
GBC06_03.png#4   框内  GBC06_03.png
GBC06_03.png#5   框外  GBC06_03.png
GBC06_03.png#6   框内  GBC06_03.png
GBC06_03.png#7   框内  GBC06_03.png
GBC06_03.png#8   框内  GBC06_03.png
GBC06_03.png#9   框内  GBC06_03.png
GBC06_03.png#10  框内  GBC06_03.png
GBC06_03.png#11  框内  GBC06_03.png
```

For quality and diversity, the five selected diverse records now cover mixed
layout types: speech-bubble text-mask cleanup, diamond announcer text, dark-card
horizontal text, large vertical title text, and color promotional side text. The
last promoted diverse record is:

```text
GBC06_33.png#1   框外  漫画第一卷 / 2026年6月29日发售！！          color promotional side text with numbers
```

The two current authoritative artifacts used for that selection, `phase1-gbc06-smoke/manifest.json` and `phase0-8-gbc06-pipeline-coverage-v12/pipeline-coverage.json`, do not provide source Japanese strings for the unprocessed candidates, so the candidate list records only translated text and positioning evidence.

## Interpretation

The current detection prototype has produced 38 candidate records across the
core `GBC06_01.png`/`GBC06_02.png` batches, the diverse expansion records, and
the first three `GBC06_03.png` CTA matches. The v20 registry entry remains the
accepted 35-record complete baseline. The v22 registry entry extends that
baseline and appends `phase2-gbc06-03-batch-1-3-cta-detection-v1`; the v23 entry
adds the corresponding real MIMO font-selection run; the v24 entry adds
`phase5-gbc06-03-batch-1-3-angle` and the accepted optical-advance layout run
`phase4-gbc06-03-batch-1-3-layout-v3`. Coverage now reports 35 complete records
and 3 records waiting for Phase 6 cleanup. The coverage report additionally
treats Phase 7 MIMO preview evaluation failures plus Phase 8 export audit
failures as quality issues that make affected records incomplete.

The `GBC06_02.png#1-#3` expansion required two fixes: tighter adjacent-column text bbox selection and mask-aware page cleanup composition. The best MIMO-backed integrated run is `phase7-8-gbc06-02-batch-1-3-preview-v3`, with score `7` and `usable=true`; `#2` and `#3` each received per-record MIMO score `10`. A follow-up top-aligned vertical-column rendering experiment (`preview-v4`) dropped to score `5`, so it was not kept.

The `GBC06_02.png#4-#6` expansion exposed a Phase 6 cleanup-range mismatch on `#5`: Phase 4 placed text in the full multi-column source text bbox, but Phase 6 cleaned only the selected detection column. The current cleanup uses the derived `selected_text_bbox(detection)` as the bubble crop, which covers the full actual text area while avoiding large false-positive selected boxes. The best integrated run is `phase7-8-gbc06-02-batch-4-6-preview-v2`, with MIMO score `8` and `usable=true`; per-record scores were `9`, `8`, and `9`.

The `GBC06_02.png#7-#9` expansion exposed a Phase 4 font-size issue: short vertical translations could scale up until they filled the target height. The fixed layout cap uses a conservative source-column-width multiplier for short vertical translations. The best integrated run is `phase7-8-gbc06-02-batch-7-9-preview-v2`, with MIMO score `9` and `usable=true`; every record scored `9`.

The `GBC06_02.png#10-#13` expansion exposed four issues: mixed-polarity bbox selection on `#10`, overly tight adjacent-column filtering on `#11`, vertical layout search that did not try balanced reflow for longer translations, and an unnatural default vertical centering for short vertical text. The current best integrated run is `phase7-8-gbc06-02-batch-10-13-preview-v9-top-align`, with MIMO score `9` and `usable=true`. The v9 run uses `phase4-gbc06-02-batch-10-13-layout-v9-top-align`, `phase6-gbc06-02-batch-10-13-region-fill-v9-top-align`, and top-aligned vertical layout previews. The v8 centered run scored `6`; the v9 top-aligned run removed the `#11/#12` layout/read-order complaint, leaving only a minor background-fill texture note. The v12 quality gate verifies that the `GBC06_02.png#10-#13` top-aligned Photoshop export carries the expected top-anchor contract.

The `GBC06_01.png#14-#15` gap-closing run uses `phase4-gbc06-batch-14-15-layout-v2`, `phase6-gbc06-batch-14-15-region-fill-v2`, and `phase7-8-gbc06-batch-14-15-preview-v5`. It closes the structural coverage gap and exports two Photoshop text layers. The visual artifacts show original text removal and translated lettering. MIMO remained unstable as a strict OCR/translation auditor on these tight vertical Chinese crops: an earlier integrated v4 evaluation scored `3` after critiquing vertical reading order and simplified/traditional Chinese. The final integrated v5 run scored `9` and `usable=true`, with only minor font-style and alignment notes. Treat MIMO here as auxiliary visual evidence, not as final typography acceptance.

The `GBC06_18.png#3` diverse run uses
`phase4-gbc06-18-phrase-aware-layout-v1`,
`phase6-gbc06-18-text-mask-bt-lama-large-d5-v1`,
`phase7-gbc06-18-phrase-aware-layout-d5-v1`, and
`phase8-gbc06-18-phrase-aware-d5-v1`. It validates the diamond announcer block
with phrase-preserving vertical line breaks, `font_size=25`, `line_spacing=0`,
`angle_degrees=0.0`, d5 text-mask LaMa cleanup, MIMO Phase 7 score `9`, and a
Phase 8 export audit pass with one vertical top anchor.

The `GBC06_06.png#3` diverse run exposed a repeated bbox contract issue across
Phase 4 and Phase 6. Phase 2 had already persisted the complete multi-column
text bbox `[557, 490, 750, 649]`, but rerunning Phase 4/6 from candidate boxes
could recompute a narrower right-side cluster `[636, 490, 750, 649]`. The fix is
to prefer Phase 2 persisted full/body bboxes and only prefer a text-mask bbox
when it is materially smaller in height, which preserves `GBC06_18.png#3`'s
overlapping-bubble mask behavior while keeping regular multi-column bubbles
complete. The new validation chain uses `phase4-gbc06-06-3-layout-v2`,
`phase6-gbc06-06-3-text-mask-bt-lama-large-v1`,
`phase7-8-gbc06-06-3-text-mask-lama-large-v1`, and
`phase8-gbc06-06-3-text-mask-lama-large-audit-v1`. MIMO scored the Phase 7
preview `9`, `usable=true`; the Phase 8 audit passed with one vertical top
anchor. An older region-fill chain,
`phase7-8-gbc06-diverse-06-18-preview-v1`, also scored `9`, confirming that a
plain white-bubble fill remains a valid simpler baseline for this record.

The `GBC06_17.png#3` diverse run exposed a target-selection failure: the original
Phase 2 diverse run selected the nearby speech-bubble vertical text
`…ですって`, while the LabelPlus translation `新川崎（暂）` belongs to the
black-card title `新川崎（仮）`. The fix changes light-on-dark detection from a
loose "bright pixel near any dark context" mask to a local dark-density mask,
which selects `[988, 221, 1142, 278]` instead of the speech bubble. A second fix
keeps horizontal light-on-dark text from vertically merging with lower card
details, and `selected_text_body_bbox()` trims the leading white logo from the
layout/cleanup body bbox, yielding `[1026, 221, 1142, 278]`.

The validation chain uses `phase2-gbc06-17-3-target-fix-v3`,
`phase3-gbc06-17-3-mimo-font-selection-target-fix-v2`,
`phase4-gbc06-17-3-layout-target-fix-v4`,
`phase5-gbc06-17-3-angle-target-fix-v2`,
`phase6-gbc06-17-3-nonbubble-patchmatch-target-fix-v2`, and
`phase7-8-gbc06-17-3-patchmatch-target-fix-v1`. The final layout is horizontal,
single-line, white text, `angle_degrees=0.0`; Phase 7 MIMO scored it `10` with
`usable=true`; Phase 8 export audit passed with one horizontal Photoshop layer
and no unexpected vertical top-anchor requirement. `bt_lama_large` was preserved
as a failed comparison for this small dark-card crop because it left visible
ghosting, while `bt_patchmatch` removed the title cleanly enough without
damaging the logo.

The alternative accepted GPT direct-replacement chain uses the same Phase 2-5
target-fix inputs but replaces Phase 6-8 with
`phase6-gbc06-17-3-text-pixel-mask-gpt-v1`,
`phase7-gbc06-17-3-text-pixel-gpt-preview-v1`, and
`phase8-gbc06-17-3-text-pixel-gpt-export-v1`. In that Phase 8 manifest,
`layers=[]` and `repair_sources[0].record_id=GBC06_17.png#3`, because the final
Chinese lettering is already inside the repaired page image. Pipeline coverage
therefore treats both editable text layers and `repair_sources[]` entries as
Phase 8 export evidence. The dedicated registry entry
`phase0-8-gbc06-17-gpt-direct-repair-source` keeps this contract test separate
from the older patchmatch export chain.

The `GBC06_29.png#2` diverse run validates the CTA matched path on a large
non-bubble vertical title. Phase 2 uses BallonsTranslator CTA/CTD masks and
matches the merged closed component
`component-0004+component-0005+component-0006+component-0007+component-0008+component-0009`
to the LabelPlus point by `7.211px` mask-edge distance, yielding the full title
bbox `[86, 815, 354, 1985]`. MIMO selected
`[toolbox]与墨体-简体-Bold(v2.4).ttf` with confidence `0.85`; Phase 5 estimated
a `1.5` degree vertical micro-angle, and Phase 4 correctly ignored that
micro-rotation for final `angle_degrees=0.0`.

The retained validation chain uses `phase2-gbc06-29-2-cta-mask-v1`,
`phase3-gbc06-29-2-mimo-font-selection-v1`,
`phase4-gbc06-29-2-layout-v3-large-title-conservative`,
`phase5-gbc06-29-2-angle-v1`, `phase6-gbc06-29-2-cta-lama-v1`, and
`phase7-8-gbc06-29-2-cta-lama-large-title-v3`. The final layout is vertical,
top-aligned, `font_size=102`, `angle_degrees=0.0`, and uses
`bt_lama_large_inpaint`. Phase 7 MIMO scored it `9`, `usable=true`, with no
issues; Phase 8 export audit passed with one vertical top anchor and
page-level repaired-image layer.

The `GBC06_33.png#1` diverse run validates the color promotional side-text path.
The retained chain uses `phase2-gbc06-33-1-cta-contract-v1`,
`phase3-gbc06-33-1-context-font-mimo-v1`,
`phase4-gbc06-33-1-context-font-layout-v1`,
`phase5-gbc06-29-33-angle-v1`,
`phase6-gbc06-33-1-gpt-background-real-v1`,
`phase7-gbc06-33-1-context-font-preview-v1`, and
`phase8-gbc06-33-1-context-font-export-v1`. MIMO selected
`[toolbox]与墨体-简体-Medium(v2.4).ttf` with confidence `0.95`. The final
layout is vertical, top-aligned, `font_size=54`, `line_spacing=20`, and
`angle_degrees=0.0`; the Phase 5 visual candidates estimated a small `4.1`
degree source tilt, but the retained lettering correctly keeps the vertical
text unrotated. Phase 6 uses `gpt-image-2` as background-repair-only cleanup,
leaving text rendering to the normal overlay path. Phase 7 MIMO scored the
preview `10`, `usable=true`; Phase 8 export audit passed with one vertical top
anchor and no record issues.

Two negative controls are preserved. `bt_patchmatch` was run through
`phase6-gbc06-29-2-cta-patchmatch-v1` with the experimental CTA method override
and scored `4` in the integrated preview; it left more visible repair artifacts
than LaMa. A real `gpt-image-2` direct replacement call in
`phase6-gbc06-29-2-gpt-replace-v1` completed at the API level, but MIMO marked
the generated text quality unacceptable: exact simplified Chinese text `0`,
no-Japanese remaining `0`, typography/layout `0`, while preservation outside
the mask was `10`. Therefore `gpt_ok_count=1` in that manifest should be read
only as transport success, not quality success.

## Verification

Fresh v20 registry coverage generation:

```powershell
python experiments/pipeline_coverage_report.py --registry-file docs/pipeline-runs.gbc06.json --registry-entry phase0-8-gbc06-v20-gbc06-33-complete --output-root outputs/runs
```

Observed result:

```text
outputs\runs\phase0-8-gbc06-pipeline-coverage-v20-gbc06-33-complete
base_record_count=35 complete_record_count=35 incomplete_record_count=0
phase7_preview evaluations=15 records=35 record_issues=0
phase8_export audits=6 records=9 record_issues=0
```

Fresh v21 next-experiments registry coverage generation:

```powershell
python experiments/pipeline_coverage_report.py --registry-file docs/pipeline-runs.gbc06.json --registry-entry phase0-8-gbc06-v20-gbc06-33-complete --output-root outputs/runs --run-id phase0-8-gbc06-pipeline-coverage-v21-next-experiments --next-limit 12
```

Observed result:

```text
outputs\runs\phase0-8-gbc06-pipeline-coverage-v21-next-experiments
base_record_count=35 complete_record_count=35 incomplete_record_count=0
phase1_pending_detection_count=145
next_records=[]
next_experiments[0].record_id=GBC06_02.png#14
next_experiments[0].action=run_cta_detection
```

Fresh v22 registry extension coverage generation:

```powershell
python experiments/pipeline_coverage_report.py --registry-file docs/pipeline-runs.gbc06.json --registry-entry phase0-8-gbc06-v22-gbc06-03-detection --output-root outputs/runs --next-limit 12
```

Observed result:

```text
outputs\runs\phase0-8-gbc06-pipeline-coverage-v22-gbc06-03-detection
base_record_count=38 complete_record_count=35 incomplete_record_count=3
phase1_pending_detection_count=142
next_records[0].record_id=GBC06_03.png#1
next_records[0].first_missing_stage=phase3_font_selection
```

Fresh v23 registry extension coverage generation:

```powershell
python experiments/pipeline_coverage_report.py --registry-file docs/pipeline-runs.gbc06.json --registry-entry phase0-8-gbc06-v23-gbc06-03-font-selection --output-root outputs/runs --next-limit 12
```

Observed result:

```text
outputs\runs\phase0-8-gbc06-pipeline-coverage-v23-gbc06-03-font-selection
base_record_count=38 complete_record_count=35 incomplete_record_count=3
phase3_font_selection covered=38 missing=0
next_records[0].record_id=GBC06_03.png#1
next_records[0].first_missing_stage=phase4_layout
```

Fresh v24 registry extension coverage generation:

```powershell
python experiments/pipeline_coverage_report.py --registry-file docs/pipeline-runs.gbc06.json --registry-entry phase0-8-gbc06-v24-gbc06-03-layout-angle --output-root outputs/runs --next-limit 12
```

Observed result:

```text
outputs\runs\phase0-8-gbc06-pipeline-coverage-v24-gbc06-03-layout-angle
base_record_count=38 complete_record_count=35 incomplete_record_count=3
phase4_layout covered=38 missing=0
phase5_angle covered=38 missing=0
next_records[0].record_id=GBC06_03.png#1
next_records[0].first_missing_stage=phase6_cleanup
```

Fresh Phase 4 layout validation:

```powershell
python experiments/phase4_layout_validate.py --layout-run-dir outputs/runs/phase4-gbc06-03-batch-1-3-layout-v3 --output-root outputs/runs --run-id phase4-gbc06-03-batch-1-3-layout-v3-mimo-validation --sample-limit 3
```

Observed result:

```text
Records submitted: 3
Accepted: 3
Needs revision: 0
Failed: 0
```

Fresh GPT direct repair-source coverage generation:

```powershell
python experiments/pipeline_coverage_report.py --registry-file docs/pipeline-runs.gbc06.json --registry-entry phase0-8-gbc06-17-gpt-direct-repair-source --output-root outputs/runs
```

Observed result:

```text
outputs\runs\phase0-8-gbc06-17-gpt-direct-coverage-v1
base_record_count=1 complete_record_count=1 incomplete_record_count=0
phase8_export covered=1 missing=0 covered_record_ids=[GBC06_17.png#3]
records[GBC06_17.png#3].missing_stages=[]
records[GBC06_17.png#3].quality_issues=[]
```

Fresh targeted verification for pipeline coverage, Phase 6/7/8 quality
aggregation, and registry CLI behavior:

```powershell
python -m pytest tests/test_pipeline_coverage.py tests/test_pipeline_quality_coverage.py tests/test_pipeline_quality_phase7.py -q
```

Observed result:

```text
25 passed
```

Full regression:

```powershell
python -m pytest -q
```

Observed result:

```text
368 passed in 88.41s (0:01:28)
```

Diff hygiene:

```powershell
git diff --check
```

Observed result:

```text
exit 0, no whitespace errors reported
```

Fresh v30 registry coverage generation:

```powershell
python experiments/pipeline_coverage_report.py --registry-file docs/pipeline-runs.gbc06.json --registry-entry phase0-8-gbc06-v30-gbc06-03-8-angle-snap --output-root outputs/runs --next-limit 12
```

Observed result:

```text
outputs\runs\phase0-8-gbc06-pipeline-coverage-v30-gbc06-03-8-angle-snap
base_record_count=44 complete_record_count=44 incomplete_record_count=0
phase7_preview evaluations=21 usable=21/21 failed=0 low_score=0 records=44 record_issues=0
phase8_export audits=11 passed=11/11 records=13 record_issues=0
next_experiments[0].record_id=GBC06_03.png#9
```

Fresh targeted verification for the v30 angle snap, coverage, and Phase 7/8
quality gates:

```powershell
python -m pytest tests/test_pipeline_coverage.py tests/test_pipeline_quality_coverage.py tests/test_pipeline_quality_phase7.py tests/test_phase7_preview_evaluation.py tests/test_phase8_export_quality_audit.py tests/test_phase7_8_smoke.py tests/test_phase4_layout.py tests/test_phase5_orientation.py -q
```

Observed result:

```text
93 passed in 7.88s
```

Fresh full regression:

```powershell
python -m pytest -q
```

Observed result:

```text
409 passed in 71.07s (0:01:11)
```

Fresh v31 registry extension for `GBC06_03.png#9`:

```powershell
python experiments/phase2_detect_text_regions.py --labelplus-file "GBC06 (已翻 斗笠)\翻译_0.txt" --output-root outputs/runs --run-id phase2-gbc06-03-9-cta-detection-v1 --sample-limit 1 --record-id "GBC06_03.png#9" --detection-strategy cta_mask --ctd-max-edge-distance-px 20
python experiments/phase2_detect_text_regions.py --labelplus-file "GBC06 (已翻 斗笠)\翻译_0.txt" --output-root outputs/runs --run-id phase2-gbc06-03-9-cta-detection-v2-threshold45 --sample-limit 1 --record-id "GBC06_03.png#9" --detection-strategy cta_mask --ctd-max-edge-distance-px 45
python experiments/phase3_font_comparison.py --labelplus-file "GBC06 (已翻 斗笠)\翻译_0.txt" --detection-run-dir outputs/runs/phase2-gbc06-03-9-cta-detection-v2-threshold45 --font-dir "工具箱漫画字体V2.5" --output-root outputs/runs --run-id phase3-gbc06-03-9-font-comparison --sample-limit 1 --font-limit 12 --record-id "GBC06_03.png#9"
python experiments/phase5_orientation_angle.py --detection-run-dir outputs/runs/phase2-gbc06-03-9-cta-detection-v2-threshold45 --output-root outputs/runs --run-id phase5-gbc06-03-9-angle --sample-limit 1 --record-id "GBC06_03.png#9"
python experiments/phase3_mimo_font_selection.py --input-run-dir outputs/runs/phase3-gbc06-03-9-font-comparison --output-root outputs/runs --run-id phase3-gbc06-03-9-mimo-font-selection --sample-limit 1 --record-id "GBC06_03.png#9"
python experiments/phase4_layout_search.py --selection-run-dir outputs/runs/phase3-gbc06-03-9-mimo-font-selection --angle-run-dir outputs/runs/phase5-gbc06-03-9-angle --detection-run-dir outputs/runs/phase2-gbc06-03-9-cta-detection-v2-threshold45 --output-root outputs/runs --run-id phase4-gbc06-03-9-layout-v2-multicolumn --sample-limit 1 --record-id "GBC06_03.png#9"
python experiments/phase6_bubble_cleanup.py --detection-run-dir outputs/runs/phase2-gbc06-03-9-cta-detection-v2-threshold45 --layout-run-dir outputs/runs/phase4-gbc06-03-9-layout-v2-multicolumn --output-root outputs/runs --run-id phase6-gbc06-03-9-region-fill-v1 --sample-limit 1 --cleanup-method region_fill --record-id "GBC06_03.png#9"
python experiments/phase7_8_integrated_smoke.py --detection-run-dir outputs/runs/phase2-gbc06-03-9-cta-detection-v2-threshold45 --cleanup-run-dir outputs/runs/phase6-gbc06-03-9-region-fill-v1 --layout-run-dir outputs/runs/phase4-gbc06-03-9-layout-v2-multicolumn --font-selection-run-dir outputs/runs/phase3-gbc06-03-9-mimo-font-selection --output-root outputs/runs --run-id phase7-8-gbc06-03-9-preview-v2-eval-sheet --sample-limit 1
python experiments/phase8_export_quality_audit.py --phase8-run-dir outputs/runs/phase7-8-gbc06-03-9-preview-v2-eval-sheet/runs/phase8-export --output-root outputs/runs --run-id phase8-gbc06-03-9-export-audit-v1
```

Observed result:

```text
phase2 first attempt status=fallback_required threshold=20 nearest_edge_distance=26.077
phase2 retry status=ok threshold=45 bbox=[804,1738,958,1874] route=cta_mask_lama_large_512px
font=[toolbox]拙黑体-简体(v2.4).ttf confidence=0.85
phase5 detected_orientation=horizontal confidence=0.611 selected_angle=-0.6
phase4 final orientation=vertical angle=0.0 vertical_align=top font_size=28 target=154x136 measured=84x135
phase6 cleanup_method=bubble_region_fill bbox=[804,1738,958,1874]
phase7 MIMO score=10 usable=true original_text_removed=true art_preserved=true lettering_readable=true issues=[]
phase8 audit passed=true vertical_top_layer_count=1 record_issue_count=0 anchor_y=1738
```

Two fixes were needed for this record:

- Phase 4 now uses CTA/CTD component structure as low-confidence orientation evidence. `GBC06_03.png#9` has a low-confidence horizontal angle estimate, but the matched mask diagnostics contain multiple narrow vertical components inside the target bbox, so final layout is vertical and top-aligned with no rotation.
- Phase 7 evaluation contact sheets no longer split medium-height context crops that fit inside the review panel. The first v1 evaluation split this bubble into top/bottom segments and MIMO incorrectly scored it `2`; the v2 single-panel sheet scored `10`.

Review artifacts:

```text
outputs/runs/phase4-gbc06-03-9-layout-v2-multicolumn/debug/layout_candidates/GBC06-03-png-9.png
outputs/runs/phase6-gbc06-03-9-region-fill-v1/crops/before_after/GBC06-03-png-9.png
outputs/runs/phase7-8-gbc06-03-9-preview-v2-eval-sheet/runs/phase7-preview/crops/context_before_after/GBC06-03-png-9.png
outputs/runs/phase7-8-gbc06-03-9-preview-v2-eval-sheet/runs/phase7-preview/debug/evaluation_contact_sheets/GBC06-03-png.png
outputs/runs/phase7-8-gbc06-03-9-preview-v2-eval-sheet/runs/phase7-preview/pages/GBC06-03-png.png
```

Fresh v31 registry coverage generation:

```powershell
python experiments/pipeline_coverage_report.py --registry-file docs/pipeline-runs.gbc06.json --registry-entry phase0-8-gbc06-v31-gbc06-03-9-multicolumn-eval-sheet --output-root outputs/runs --next-limit 12
```

Observed result:

```text
outputs\runs\phase0-8-gbc06-pipeline-coverage-v31-gbc06-03-9-multicolumn-eval-sheet
base_record_count=45 complete_record_count=45 incomplete_record_count=0
phase7_preview evaluations=22 usable=22/22 failed=0 low_score=0 records=45 record_issues=0
phase8_export audits=12 passed=12/12 records=14 record_issues=0
phase1_pending_detection_count=135
next_experiments[0].record_id=GBC06_03.png#10
```

Fresh v32 registry extension for `GBC06_03.png#10`:

```powershell
python experiments/phase2_detect_text_regions.py --labelplus-file "GBC06 (已翻 斗笠)\翻译_0.txt" --output-root outputs/runs --run-id phase2-gbc06-03-10-cta-detection-v1 --sample-limit 1 --record-id "GBC06_03.png#10" --detection-strategy cta_mask --ctd-max-edge-distance-px 20
python experiments/phase3_font_comparison.py --labelplus-file "GBC06 (已翻 斗笠)\翻译_0.txt" --detection-run-dir outputs/runs/phase2-gbc06-03-10-cta-detection-v1 --font-dir "工具箱漫画字体V2.5" --output-root outputs/runs --run-id phase3-gbc06-03-10-font-comparison --sample-limit 1 --font-limit 12 --record-id "GBC06_03.png#10"
python experiments/phase5_orientation_angle.py --detection-run-dir outputs/runs/phase2-gbc06-03-10-cta-detection-v1 --output-root outputs/runs --run-id phase5-gbc06-03-10-angle --sample-limit 1 --record-id "GBC06_03.png#10"
python experiments/phase3_mimo_font_selection.py --input-run-dir outputs/runs/phase3-gbc06-03-10-font-comparison --output-root outputs/runs --run-id phase3-gbc06-03-10-mimo-font-selection --sample-limit 1 --record-id "GBC06_03.png#10"
python experiments/phase4_layout_search.py --selection-run-dir outputs/runs/phase3-gbc06-03-10-mimo-font-selection --angle-run-dir outputs/runs/phase5-gbc06-03-10-angle --detection-run-dir outputs/runs/phase2-gbc06-03-10-cta-detection-v1 --output-root outputs/runs --run-id phase4-gbc06-03-10-layout-v1 --sample-limit 1 --record-id "GBC06_03.png#10"
python experiments/phase6_bubble_cleanup.py --detection-run-dir outputs/runs/phase2-gbc06-03-10-cta-detection-v1 --layout-run-dir outputs/runs/phase4-gbc06-03-10-layout-v1 --output-root outputs/runs --run-id phase6-gbc06-03-10-region-fill-v1 --sample-limit 1 --cleanup-method region_fill --record-id "GBC06_03.png#10"
python experiments/phase7_8_integrated_smoke.py --detection-run-dir outputs/runs/phase2-gbc06-03-10-cta-detection-v1 --cleanup-run-dir outputs/runs/phase6-gbc06-03-10-region-fill-v1 --layout-run-dir outputs/runs/phase4-gbc06-03-10-layout-v1 --font-selection-run-dir outputs/runs/phase3-gbc06-03-10-mimo-font-selection --output-root outputs/runs --run-id phase7-8-gbc06-03-10-preview-v1 --sample-limit 1
python experiments/phase8_export_quality_audit.py --phase8-run-dir outputs/runs/phase7-8-gbc06-03-10-preview-v1/runs/phase8-export --output-root outputs/runs --run-id phase8-gbc06-03-10-export-audit-v1
```

Observed result:

```text
record_id=GBC06_03.png#10 translated_text=没关系
phase2 status=ok threshold=20 bbox=[449,1340,487,1438] nearest_edge_distance=20.0 route=cta_mask_lama_large_512px
phase2 visual QA: selected the target "大丈夫" text region; bbox purity was not treated as a failure because the desired text content is contained
font=[toolbox]与墨体-简体-Bold(v2.4).ttf confidence=0.95
phase5 detected_orientation=vertical confidence=0.957 selected_angle=0.0
phase4 final orientation=vertical angle=0.0 vertical_align=top font_size=33 target=38x98 measured=33x97
phase6 cleanup_method=bubble_region_fill bbox=[449,1340,487,1438]
phase7 MIMO score=10 usable=true original_text_removed=true art_preserved=true lettering_readable=true issues=[]
phase8 audit passed=true vertical_top_layer_count=1 record_issue_count=0 anchor_y=1340
```

This sample keeps the relaxed detection acceptance rule explicit: the CTA mask was accepted because it contains the intended source text. The nearby LabelPlus point is outside the tight text bbox by about `20px`, but that is an expected point-to-mask-edge match and should not trigger bbox expansion or visual fallback on its own.

Review artifacts:

```text
outputs/runs/phase2-gbc06-03-10-cta-detection-v1/debug/detection/GBC06_03-10.png
outputs/runs/phase4-gbc06-03-10-layout-v1/debug/layout_candidates/GBC06-03-png-10.png
outputs/runs/phase6-gbc06-03-10-region-fill-v1/crops/before_after/GBC06-03-png-10.png
outputs/runs/phase7-8-gbc06-03-10-preview-v1/runs/phase7-preview/crops/context_before_after/GBC06-03-png-10.png
outputs/runs/phase7-8-gbc06-03-10-preview-v1/runs/phase7-preview/debug/evaluation_contact_sheets/GBC06-03-png.png
outputs/runs/phase7-8-gbc06-03-10-preview-v1/runs/phase7-preview/pages/GBC06-03-png.png
outputs/runs/phase8-gbc06-03-10-export-audit-v1/phase8-export-audit.json
```

Fresh v32 registry coverage generation:

```powershell
python experiments/pipeline_coverage_report.py --registry-file docs/pipeline-runs.gbc06.json --registry-entry phase0-8-gbc06-v32-gbc06-03-10 --output-root outputs/runs --next-limit 12
```

Observed result:

```text
outputs\runs\phase0-8-gbc06-pipeline-coverage-v32-gbc06-03-10
base_record_count=46 complete_record_count=46 incomplete_record_count=0
phase7_preview evaluations=23 usable=23/23 failed=0 low_score=0 records=46 record_issues=0
phase8_export audits=13 passed=13/13 records=15 record_issues=0
phase1_pending_detection_count=134
next_experiments[0].record_id=GBC06_03.png#11
```

Fresh v33 registry extension for `GBC06_03.png#11`:

```powershell
python experiments/phase2_detect_text_regions.py --labelplus-file "GBC06 (已翻 斗笠)\翻译_0.txt" --output-root outputs/runs --run-id phase2-gbc06-03-11-cta-detection-v1 --sample-limit 1 --record-id "GBC06_03.png#11" --detection-strategy cta_mask --ctd-max-edge-distance-px 20
python experiments/phase2_detect_text_regions.py --labelplus-file "GBC06 (已翻 斗笠)\翻译_0.txt" --output-root outputs/runs --run-id phase2-gbc06-03-11-cta-detection-v2-threshold45 --sample-limit 1 --record-id "GBC06_03.png#11" --detection-strategy cta_mask --ctd-max-edge-distance-px 45
python experiments/phase3_font_comparison.py --labelplus-file "GBC06 (已翻 斗笠)\翻译_0.txt" --detection-run-dir outputs/runs/phase2-gbc06-03-11-cta-detection-v2-threshold45 --font-dir "工具箱漫画字体V2.5" --output-root outputs/runs --run-id phase3-gbc06-03-11-font-comparison --sample-limit 1 --font-limit 12 --record-id "GBC06_03.png#11"
python experiments/phase5_orientation_angle.py --detection-run-dir outputs/runs/phase2-gbc06-03-11-cta-detection-v2-threshold45 --output-root outputs/runs --run-id phase5-gbc06-03-11-angle --sample-limit 1 --record-id "GBC06_03.png#11"
python experiments/phase3_mimo_font_selection.py --input-run-dir outputs/runs/phase3-gbc06-03-11-font-comparison --output-root outputs/runs --run-id phase3-gbc06-03-11-mimo-font-selection --sample-limit 1 --record-id "GBC06_03.png#11"
python experiments/phase4_layout_search.py --selection-run-dir outputs/runs/phase3-gbc06-03-11-mimo-font-selection --angle-run-dir outputs/runs/phase5-gbc06-03-11-angle --detection-run-dir outputs/runs/phase2-gbc06-03-11-cta-detection-v2-threshold45 --output-root outputs/runs --run-id phase4-gbc06-03-11-layout-v1 --sample-limit 1 --record-id "GBC06_03.png#11"
python experiments/phase6_bubble_cleanup.py --detection-run-dir outputs/runs/phase2-gbc06-03-11-cta-detection-v2-threshold45 --layout-run-dir outputs/runs/phase4-gbc06-03-11-layout-v1 --output-root outputs/runs --run-id phase6-gbc06-03-11-region-fill-v1 --sample-limit 1 --cleanup-method region_fill --record-id "GBC06_03.png#11"
python experiments/phase7_8_integrated_smoke.py --detection-run-dir outputs/runs/phase2-gbc06-03-11-cta-detection-v2-threshold45 --cleanup-run-dir outputs/runs/phase6-gbc06-03-11-region-fill-v1 --layout-run-dir outputs/runs/phase4-gbc06-03-11-layout-v1 --font-selection-run-dir outputs/runs/phase3-gbc06-03-11-mimo-font-selection --output-root outputs/runs --run-id phase7-8-gbc06-03-11-preview-v1 --sample-limit 1
python experiments/phase8_export_quality_audit.py --phase8-run-dir outputs/runs/phase7-8-gbc06-03-11-preview-v1/runs/phase8-export --output-root outputs/runs --run-id phase8-gbc06-03-11-export-audit-v1
```

Observed result:

```text
record_id=GBC06_03.png#11 translated_text=万一出了什么事 / 就由我来解决
phase2 first attempt threshold=20 -> fallback_required nearest_edge_distance=21.213
phase2 retry threshold=45 -> ok bbox=[141,1689,255,1903] selected_component_id=component-0027+component-0028+component-0029+component-0030 route=cta_mask_lama_large_512px
phase2 visual check: accepted because the bbox contains the full lower-left bubble text columns, not because the LabelPlus point is inside the box
font=[toolbox]与墨体-简体-Bold(v2.4).ttf confidence=0.8
phase5 detected_orientation=vertical confidence=0.762 selected_angle=-6.0
phase4 final orientation=vertical angle=0.0 vertical_align=top font_size=38 target=114x214 measured=114x183
phase4 line_breaks=万一出了什 / 么事就由 / 我来解决
phase6 cleanup_method=bubble_region_fill bbox=[141,1689,255,1903]
phase7 MIMO score=10 usable=true original_text_removed=true art_preserved=true lettering_readable=true issues=[]
phase8 audit passed=true vertical_top_layer_count=1 record_issue_count=0 anchor_y=1689
```

The Phase 5 raw angle estimate was `-6.0`, but Phase 4 correctly snapped the final lettering angle to `0.0` for this obvious vertical bubble text. The final preview is top-aligned; MIMO's contact sheet split the tall review crop into two ordered segments and still scored the result as usable.

Review artifacts:

```text
outputs/runs/phase2-gbc06-03-11-cta-detection-v1/debug/detection/GBC06_03-11.png
outputs/runs/phase2-gbc06-03-11-cta-detection-v2-threshold45/debug/detection/GBC06_03-11.png
outputs/runs/phase4-gbc06-03-11-layout-v1/debug/layout_candidates/GBC06-03-png-11.png
outputs/runs/phase6-gbc06-03-11-region-fill-v1/crops/before_after/GBC06-03-png-11.png
outputs/runs/phase7-8-gbc06-03-11-preview-v1/runs/phase7-preview/crops/context_before_after/GBC06-03-png-11.png
outputs/runs/phase7-8-gbc06-03-11-preview-v1/runs/phase7-preview/debug/evaluation_contact_sheets/GBC06-03-png.png
outputs/runs/phase7-8-gbc06-03-11-preview-v1/runs/phase7-preview/pages/GBC06-03-png.png
outputs/runs/phase8-gbc06-03-11-export-audit-v1/phase8-export-audit.json
```

Fresh v33 registry coverage generation:

```powershell
python experiments/pipeline_coverage_report.py --registry-file docs/pipeline-runs.gbc06.json --registry-entry phase0-8-gbc06-v33-gbc06-03-11 --output-root outputs/runs --next-limit 12
```

Observed result:

```text
outputs\runs\phase0-8-gbc06-pipeline-coverage-v33-gbc06-03-11
base_record_count=47 complete_record_count=47 incomplete_record_count=0
phase7_preview evaluations=24 usable=24/24 failed=0 low_score=0 records=47 record_issues=0
phase8_export audits=14 passed=14/14 records=16 record_issues=0
phase1_pending_detection_count=133
next_experiments[0].record_id=GBC06_04.png#1
```
