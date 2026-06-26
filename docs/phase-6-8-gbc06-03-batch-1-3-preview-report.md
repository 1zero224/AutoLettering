# Phase 6-8 GBC06_03 #1-#3 Cleanup, Preview, and Export Report

## Purpose

This run advances the first three `GBC06_03.png` speech-bubble records through
Phase 6 cleanup, Phase 7 preview/evaluation, and Phase 8 Photoshop export:

- `GBC06_03.png#1` translated as `你要去哪里？`
- `GBC06_03.png#2` translated as `我要回家`
- `GBC06_03.png#3` translated as `差不多得了`

It also records the negative control from the first integrated preview run:
MIMO scored the page `10`, but manual full-page review found that `#3` still
left the adjacent Japanese text `しろ` in the bubble. The accepted chain is the
CTA-merged v2/v4/v2/v3 sequence below.

## Negative Control

The first cleanup and integrated preview used the original CTA detection and
layout:

```powershell
python experiments/phase6_bubble_cleanup.py --detection-run-dir outputs/runs/phase2-gbc06-03-batch-1-3-cta-detection-v1 --layout-run-dir outputs/runs/phase4-gbc06-03-batch-1-3-layout-v3 --run-id phase6-gbc06-03-batch-1-3-region-fill-v1 --sample-limit 3 --cleanup-method region_fill --record-id "GBC06_03.png#1" --record-id "GBC06_03.png#2" --record-id "GBC06_03.png#3"
```

```powershell
python experiments/phase7_8_integrated_smoke.py --detection-run-dir outputs/runs/phase2-gbc06-03-batch-1-3-cta-detection-v1 --cleanup-run-dir outputs/runs/phase6-gbc06-03-batch-1-3-region-fill-v1 --layout-run-dir outputs/runs/phase4-gbc06-03-batch-1-3-layout-v3 --font-selection-run-dir outputs/runs/phase3-gbc06-03-batch-1-3-mimo-font-selection --run-id phase7-8-gbc06-03-batch-1-3-preview-v1 --sample-limit 3
```

MIMO returned `score=10` and `usable=true`, but manual inspection of the full
page preview showed `GBC06_03.png#3` still had Japanese `しろ` left of the
cleaned text. The failure was not a layout issue; the source text region was
too narrow.

## Root Cause

The v1 CTA match for `GBC06_03.png#3` selected:

```text
bbox=[1205,768,1243,891]
component_id=component-0007+component-0008
```

The actual bubble text also includes adjacent upper/left components:

```text
component-0004=[1170,735,1201,799]
component-0005=[1207,738,1225,766]
component-0006=[1225,738,1242,761]
```

Those components belong to the same speech-bubble vertical text group but were
outside the original point-edge threshold path. The fix extends CTA vertical
component grouping for `框内` labels so adjacent narrow vertical columns can be
merged when they overlap vertically and sit close to the seed column. The
accepted v2 match is:

```text
bbox=[1170,735,1243,891]
component_id=component-0004+component-0005+component-0006+component-0007+component-0008
```

The Phase 7 evaluation contact sheet was also tightened. It now prefers local
context before/after crops and explicitly treats adjacent leftover Japanese in
the green AFTER panel as failed original-text removal. This prevents the tight
crop review image from hiding the same class of failure.

## Accepted Commands

Run CTA detection with the adjacent-column grouping fix:

```powershell
python experiments/phase2_detect_text_regions.py --labelplus-file "GBC06 (已翻 斗笠)\翻译_0.txt" --output-root outputs/runs --run-id phase2-gbc06-03-batch-1-3-cta-detection-v2 --sample-limit 3 --record-id "GBC06_03.png#1" --record-id "GBC06_03.png#2" --record-id "GBC06_03.png#3" --detection-strategy cta_mask --ctd-max-edge-distance-px 20
```

Regenerate layout against the wider `#3` bbox:

```powershell
python experiments/phase4_layout_search.py --selection-run-dir outputs/runs/phase3-gbc06-03-batch-1-3-mimo-font-selection --angle-run-dir outputs/runs/phase5-gbc06-03-batch-1-3-angle --detection-run-dir outputs/runs/phase2-gbc06-03-batch-1-3-cta-detection-v2 --output-root outputs/runs --run-id phase4-gbc06-03-batch-1-3-layout-v4-cta-merged --sample-limit 3 --record-id "GBC06_03.png#1" --record-id "GBC06_03.png#2" --record-id "GBC06_03.png#3"
```

Run bubble region-fill cleanup:

```powershell
python experiments/phase6_bubble_cleanup.py --detection-run-dir outputs/runs/phase2-gbc06-03-batch-1-3-cta-detection-v2 --layout-run-dir outputs/runs/phase4-gbc06-03-batch-1-3-layout-v4-cta-merged --run-id phase6-gbc06-03-batch-1-3-region-fill-v2-cta-merged --sample-limit 3 --cleanup-method region_fill --record-id "GBC06_03.png#1" --record-id "GBC06_03.png#2" --record-id "GBC06_03.png#3"
```

Run integrated preview, MIMO evaluation, and Photoshop export:

```powershell
python experiments/phase7_8_integrated_smoke.py --detection-run-dir outputs/runs/phase2-gbc06-03-batch-1-3-cta-detection-v2 --cleanup-run-dir outputs/runs/phase6-gbc06-03-batch-1-3-region-fill-v2-cta-merged --layout-run-dir outputs/runs/phase4-gbc06-03-batch-1-3-layout-v4-cta-merged --font-selection-run-dir outputs/runs/phase3-gbc06-03-batch-1-3-mimo-font-selection --run-id phase7-8-gbc06-03-batch-1-3-preview-v3-context-eval --sample-limit 3
```

Update registry coverage:

```powershell
python experiments/pipeline_coverage_report.py --registry-file docs/pipeline-runs.gbc06.json --registry-entry phase0-8-gbc06-v25-gbc06-03-preview-export --output-root outputs/runs --next-limit 12
```

## Accepted Results

Phase 4 layout after the CTA merge:

```text
GBC06_03.png#1  font_size=33  target=37x189  measured=35x186  angle=0.0  vertical_align=top
GBC06_03.png#2  font_size=34  target=36x130  measured=34x128  angle=0.0  vertical_align=top
GBC06_03.png#3  font_size=32  target=73x156  measured=32x153  angle=0.0  vertical_align=top
```

Phase 6 cleanup:

```text
records_processed=3
cleaned=3
skipped=0
effective_cleanup_method=bubble_region_fill
```

Phase 7/8 integrated smoke:

```text
preview_pages=1
preview_records=3
skipped_records=0
evaluation_status=evaluated
evaluation_score=10
evaluation_usable=True
exported_pages=1
exported_text_layers=3
missing_cleanup_layers=0
```

MIMO context evaluation:

```text
score=10
usable=true
original_text_removed=true
art_preserved=true
lettering_readable=true
issues=[]
```

Manual inspection of the accepted full-page preview confirmed:

- `#1` and `#2` are vertical, top-aligned, and unrotated.
- `#3` removes both `しろ` and `いい加減に`.
- `#3` renders `差不多得了` vertically, top-aligned, unrotated, and inside the bubble.

## Key Artifacts

- Detection overlay:
  `outputs/runs/phase2-gbc06-03-batch-1-3-cta-detection-v2/debug/detection/GBC06_03-3.png`
- Phase 6 before/after crops:
  `outputs/runs/phase6-gbc06-03-batch-1-3-region-fill-v2-cta-merged/crops/before_after/`
- Full preview:
  `outputs/runs/phase7-8-gbc06-03-batch-1-3-preview-v3-context-eval/runs/phase7-preview/pages/GBC06-03-png.png`
- MIMO context contact sheet:
  `outputs/runs/phase7-8-gbc06-03-batch-1-3-preview-v3-context-eval/runs/phase7-preview/debug/evaluation_contact_sheets/GBC06-03-png.png`
- Phase 8 export:
  `outputs/runs/phase7-8-gbc06-03-batch-1-3-preview-v3-context-eval/runs/phase8-export`

## Coverage Result

The v25 registry entry closes all 38 records currently in the detection base:

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

## Verification

Targeted regression for the CTA component merge and Phase 7 context evaluation:

```powershell
python -m pytest tests/test_ctd_mask_matching.py tests/test_phase7_preview.py tests/test_phase7_preview_evaluation.py -q
```

The final closeout verification also includes the integrated smoke, export, and
coverage test suites:

```powershell
python -m pytest tests/test_ctd_mask_matching.py tests/test_phase7_preview.py tests/test_phase7_preview_evaluation.py tests/test_phase7_8_smoke.py tests/test_phase8_photoshop_export.py tests/test_pipeline_coverage.py tests/test_pipeline_quality_coverage.py tests/test_pipeline_quality_phase7.py -q
```
