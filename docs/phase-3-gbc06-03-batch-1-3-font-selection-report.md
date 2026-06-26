# Phase 3 GBC06_03 #1-#3 Font Selection Report

## Purpose

This run advances the first three `GBC06_03.png` CTA-matched speech-bubble
records from Phase 2 text detection into Phase 3 font selection:

- `GBC06_03.png#1`
- `GBC06_03.png#2`
- `GBC06_03.png#3`

The input detection run is `phase2-gbc06-03-batch-1-3-cta-detection-v1`.
All three records were matched by CTA/CTD mask components and were already
promoted into the v22 detection base.

## Commands

Generate deterministic font comparison grids:

```powershell
python experiments/phase3_font_comparison.py --labelplus-file "GBC06 (已翻 斗笠)\翻译_0.txt" --detection-run-dir outputs/runs/phase2-gbc06-03-batch-1-3-cta-detection-v1 --font-dir "工具箱漫画字体V2.5" --output-root outputs/runs --run-id phase3-gbc06-03-batch-1-3-font-comparison --sample-limit 3 --font-limit 12 --record-id "GBC06_03.png#1" --record-id "GBC06_03.png#2" --record-id "GBC06_03.png#3"
```

Run controlled real MIMO font selection:

```powershell
python experiments/phase3_mimo_font_selection.py --input-run-dir outputs/runs/phase3-gbc06-03-batch-1-3-font-comparison --output-root outputs/runs --run-id phase3-gbc06-03-batch-1-3-mimo-font-selection --sample-limit 3 --record-id "GBC06_03.png#1" --record-id "GBC06_03.png#2" --record-id "GBC06_03.png#3"
```

Generate updated pipeline coverage:

```powershell
python experiments/pipeline_coverage_report.py --registry-file docs/pipeline-runs.gbc06.json --registry-entry phase0-8-gbc06-v23-gbc06-03-font-selection --output-root outputs/runs --next-limit 12
```

## Generated Artifacts

- `outputs/runs/phase3-gbc06-03-batch-1-3-font-comparison/font-comparisons.jsonl`
- `outputs/runs/phase3-gbc06-03-batch-1-3-font-comparison/font-index.jsonl`
- `outputs/runs/phase3-gbc06-03-batch-1-3-font-comparison/crops/source_text/GBC06-03-png-1.png`
- `outputs/runs/phase3-gbc06-03-batch-1-3-font-comparison/crops/source_text/GBC06-03-png-2.png`
- `outputs/runs/phase3-gbc06-03-batch-1-3-font-comparison/crops/source_text/GBC06-03-png-3.png`
- `outputs/runs/phase3-gbc06-03-batch-1-3-font-comparison/debug/font_comparison/GBC06-03-png-1.png`
- `outputs/runs/phase3-gbc06-03-batch-1-3-font-comparison/debug/font_comparison/GBC06-03-png-2.png`
- `outputs/runs/phase3-gbc06-03-batch-1-3-font-comparison/debug/font_comparison/GBC06-03-png-3.png`
- `outputs/runs/phase3-gbc06-03-batch-1-3-font-comparison/debug/font_comparison/GBC06_03-1-3-font-grid.png`
- `outputs/runs/phase3-gbc06-03-batch-1-3-mimo-font-selection/font-selections.jsonl`
- `outputs/runs/phase3-gbc06-03-batch-1-3-mimo-font-selection/reports/api-calls.jsonl`
- `outputs/runs/phase0-8-gbc06-pipeline-coverage-v23-gbc06-03-font-selection/pipeline-coverage.json`
- `outputs/runs/phase0-8-gbc06-pipeline-coverage-v23-gbc06-03-font-selection/reports/pipeline-coverage-report.md`

The API call log stores request and response summaries only. It does not store
API keys.

## Font Selection Results

```text
GBC06_03.png#1  selected=[toolbox]文黑体-简繁-Bold(v2.4).ttf  confidence=0.95
GBC06_03.png#2  selected=[toolbox]POP1-简繁(v2.5).ttf       confidence=0.90
GBC06_03.png#3  selected=[toolbox]与墨体-简体-Bold(v2.4).ttf  confidence=0.90
```

All three selections were returned by the real MIMO vision path with
`selection_source=mimo_vision` and `status=selected`.

## Interpretation

The selected fonts are plausible for the three source crops:

- `#1` source text is a clean vertical speech-bubble line; MIMO selected a bold
  WenHei style for readability and impact.
- `#2` source text is softer and rounder; MIMO selected the POP1 font.
- `#3` source text is heavier and more emphatic; MIMO selected YuMo Bold.

The next pipeline stage for all three records is Phase 4 layout search. The
v23 coverage report confirms that Phase 3 is now covered for all 38 records in
the detection base.

## Verification

Observed v23 coverage result:

```text
base_record_count=38
complete_record_count=35
incomplete_record_count=3
phase3_font_selection covered=38 missing=0
phase4_layout covered=35 missing=3
next_records[0]=GBC06_03.png#1 first_missing_stage=phase4_layout
```
