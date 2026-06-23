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

`outputs/` remains ignored by Git. The source-backed summary below records the key numbers so the experiment is traceable in the repository.

## Current Coverage

Base stage: `phase2_detection`

```text
base_record_count=35
complete_record_count=31
incomplete_record_count=4
```

Stage counts:

```text
phase1_labelplus       covered=35 missing=0
phase2_detection       covered=35 missing=0
phase3_font_selection  covered=32 missing=3
phase4_layout          covered=31 missing=4
phase5_angle           covered=32 missing=3
phase6_cleanup         covered=31 missing=4
phase7_preview         covered=31 missing=4
phase8_export          covered=31 missing=4
```

Quality audits:

```text
phase7_preview evaluations=10 evaluated=10 usable=10/10 failed=0 low_score=0 records=31 record_issues=0
phase8_export audits=2 passed=2/2 records=5 vertical_top_layers=5 missing_anchor=0 unexpected_anchor=0 record_issues=0 missing_jsx_anchor_logic=0
```

Group coverage:

```text
框内: base=30 complete=29
框外: base=5  complete=2
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

The v15 report promotes the five diverse expansion records into the coverage
base. `GBC06_18.png#3` is complete across Phase 1-8 and all attached quality
gates. The other four diverse records are now visible as next work:

```text
GBC06_06.png#3   框内  first_missing_stage=phase4_layout
GBC06_17.png#3   框外  first_missing_stage=phase3_font_selection
GBC06_29.png#2   框外  first_missing_stage=phase3_font_selection
GBC06_33.png#1   框外  first_missing_stage=phase3_font_selection
```

The v15 report also keeps the remaining parsed-but-undetected Phase 1 scope
explicit:

```text
phase1_pending_detection_count=145
```

The first `next-limit=12` Phase 1 records missing detection in v15 are:

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

For quality and diversity, the next expansion should continue covering mixed
layout types. `GBC06_18.png#3` has now moved from candidate to complete. The
remaining diverse base records are:

```text
GBC06_06.png#3   框内  毫无保留地 / 只要把现在的感受 / 唱出来就好了  long regular vertical bubble
GBC06_17.png#3   框外  新川崎（暂）                              black-card/sign text, polarity-sensitive
GBC06_29.png#2   框外  囚禁中挣脱而出！                          large non-bubble page text
GBC06_33.png#1   框外  漫画第一卷 / 2026年6月29日发售！！          color promotional side text with numbers
```

The two current authoritative artifacts used for that selection, `phase1-gbc06-smoke/manifest.json` and `phase0-8-gbc06-pipeline-coverage-v12/pipeline-coverage.json`, do not provide source Japanese strings for the unprocessed candidates, so the candidate list records only translated text and positioning evidence.

## Interpretation

The current detection prototype has produced 35 candidate records across the
core `GBC06_01.png`/`GBC06_02.png` batches plus the diverse expansion records.
The v15 coverage tool can merge multiple detection run directories, counts 31
records as complete across Phase 1 through Phase 8, and additionally treats
Phase 7 MIMO preview evaluation failures plus Phase 8 export audit failures as
quality issues that make affected records incomplete.

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

## Verification

Fresh targeted verification for the coverage tool, Phase 7 evaluation failure preservation, and the latest Phase 4 top-alignment regression:

```powershell
python -m pytest tests/test_pipeline_coverage.py tests/test_pipeline_quality_coverage.py tests/test_pipeline_quality_phase7.py tests/test_phase7_preview_evaluation.py tests/test_phase4_layout.py tests/test_phase8_export_quality_audit.py -q
```

Observed result:

```text
59 passed in 4.71s
```
