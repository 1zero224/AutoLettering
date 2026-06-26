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
phase4_layout          covered=35 missing=3
phase5_angle           covered=35 missing=3
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

After v23, all three records have moved past Phase 3 and now wait on layout:

```text
next_records[0]=GBC06_03.png#1  first_missing_stage=phase4_layout
next_records[1]=GBC06_03.png#2  first_missing_stage=phase4_layout
next_records[2]=GBC06_03.png#3  first_missing_stage=phase4_layout
phase3_font_selection covered=38 missing=0
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
adds the corresponding real MIMO font-selection run. Coverage now reports 35
complete records and 3 records waiting for Phase 4 layout search. The coverage
report additionally treats Phase 7 MIMO preview evaluation failures plus Phase 8
export audit failures as quality issues that make affected records incomplete.

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
