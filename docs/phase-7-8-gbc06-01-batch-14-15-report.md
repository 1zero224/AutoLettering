# Phase 7/8 GBC06_01 #14-#15 Report

## Purpose

This run closes the historical `GBC06_01.png#14` and `GBC06_01.png#15`
coverage gaps with real Phase 4, Phase 6, Phase 7, Phase 8, and MIMO
evaluation artifacts.

Generated images remain under `outputs/` and are intentionally not committed.

## Commands

Phase 4 layout:

```powershell
python experiments/phase4_layout_search.py --selection-run-dir outputs/runs/phase3-gbc06-batch-14-15-17-mimo-font-selection --angle-run-dir outputs/runs/phase5-gbc06-batch-14-15-17-angle-v2 --detection-run-dir outputs/runs/phase2-gbc06-smoke-v3 --run-id phase4-gbc06-batch-14-15-layout-v2 --sample-limit 2 --record-id "GBC06_01.png#14" --record-id "GBC06_01.png#15"
```

Phase 6 cleanup:

```powershell
python experiments/phase6_bubble_cleanup.py --detection-run-dir outputs/runs/phase2-gbc06-smoke-v3 --layout-run-dir outputs/runs/phase4-gbc06-batch-14-15-layout-v2 --run-id phase6-gbc06-batch-14-15-region-fill-v2 --sample-limit 2 --cleanup-method region_fill --record-id "GBC06_01.png#14" --record-id "GBC06_01.png#15"
```

Phase 7/8 integrated preview:

```powershell
python experiments/phase7_8_integrated_smoke.py --detection-run-dir outputs/runs/phase2-gbc06-smoke-v3 --cleanup-run-dir outputs/runs/phase6-gbc06-batch-14-15-region-fill-v2 --layout-run-dir outputs/runs/phase4-gbc06-batch-14-15-layout-v2 --font-selection-run-dir outputs/runs/phase3-gbc06-batch-14-15-17-mimo-font-selection --run-id phase7-8-gbc06-batch-14-15-preview-v5 --sample-limit 2
```

The standalone visual-only evaluation that produced the most stable result:

```powershell
python experiments/phase7_preview_evaluate.py --preview-run-dir outputs/runs/phase7-8-gbc06-batch-14-15-preview-v3/runs/phase7-preview --run-id phase7-gbc06-batch-14-15-preview-v3-mimo-eval-v3 --sample-limit 1
```

## Result Artifacts

Manual evaluation index produced by the subagent:

```text
outputs/runs/manual-eval-subagent-20260622-122655/manual-evaluation-index.md
outputs/runs/manual-eval-subagent-20260622-122655/manual-evaluation-preview.html
```

Main Phase 7/8 artifacts:

```text
outputs/runs/phase7-8-gbc06-batch-14-15-preview-v5/manifest.json
outputs/runs/phase7-8-gbc06-batch-14-15-preview-v5/runs/phase7-preview/pages/GBC06-01-png.png
outputs/runs/phase7-8-gbc06-batch-14-15-preview-v5/runs/phase7-preview/crops/before_after/GBC06-01-png-14.png
outputs/runs/phase7-8-gbc06-batch-14-15-preview-v5/runs/phase7-preview/crops/before_after/GBC06-01-png-15.png
outputs/runs/phase7-8-gbc06-batch-14-15-preview-v5/runs/phase7-preview/debug/evaluation_contact_sheets/GBC06-01-png.png
outputs/runs/phase7-8-gbc06-batch-14-15-preview-v5/runs/phase8-export/photoshop-manifest.json
outputs/runs/phase7-8-gbc06-batch-14-15-preview-v5/runs/phase8-export/photoshop-import.jsx
```

## Phase Results

Phase 4 generated layouts for both records:

| Record | Target bbox | Font size | Line breaks | Overflow |
| --- | --- | ---: | --- | ---: |
| `GBC06_01.png#14` | `[120,1789,205,1917]` | 31 | `昴也好\n仁菜也好` | 0.0 |
| `GBC06_01.png#15` | `[799,145,874,300]` | 38 | `锵~锵` | 0.0 |

Phase 6 cleanup used `bubble_region_fill` for both records and produced
before/after crops:

```text
outputs/runs/phase6-gbc06-batch-14-15-region-fill-v2/crops/before_after/GBC06-01-png-14.png
outputs/runs/phase6-gbc06-batch-14-15-region-fill-v2/crops/before_after/GBC06-01-png-15.png
```

Phase 7/8 integrated run `phase7-8-gbc06-batch-14-15-preview-v5` produced:

```json
{
  "preview_page_count": 1,
  "preview_record_count": 2,
  "skipped_count": 0,
  "evaluation_score": 9,
  "evaluation_usable": true,
  "exported_text_layer_count": 2,
  "missing_cleanup_layers": 0,
  "effective_cleanup_methods": {
    "bubble_region_fill": 2
  }
}
```

## MIMO Evaluation Findings

The evaluation contact sheet was changed from equal-sized left/right panels to:

- a large green `AFTER RESULT` panel that is the only scoring target;
- a smaller gray `BEFORE original` panel used only as reference;
- smooth upscaling for the scoring panel to reduce pixel-grid OCR artifacts.

This fixed one concrete failure mode: MIMO no longer has to infer which side of
the old before/after crop should be scored.

Observed real MIMO calls:

| Run | Score | Usable | Interpretation |
| --- | ---: | --- | --- |
| `phase7-gbc06-batch-14-15-preview-v2-mimo-eval-subagent` | 0 | false | Subagent run still confused before/original source text with the after result. |
| `phase7-gbc06-batch-14-15-preview-v2-mimo-eval-v2` | 10 | true | Same visual target after the first prompt/contact-sheet fix; MIMO judged removal/readability usable. |
| `phase7-gbc06-batch-14-15-preview-v3-mimo-eval-v3` | 9 | true | After smooth upscaling and page-level prompt; MIMO judged the visual edit usable. |
| `phase7-8-gbc06-batch-14-15-preview-v4` integrated evaluation | 3 | false | MIMO shifted into translation/OCR critique: vertical reading order, simplified/traditional Chinese, and text-size comments. |
| `phase7-gbc06-batch-14-15-preview-v4-mimo-eval-final` | 10 | true | Final prompt/runtime evaluation: one page-level JSON result, original text removed, art preserved, lettering readable. |
| `phase7-8-gbc06-batch-14-15-preview-v5` integrated evaluation | 9 | true | Final integrated run with current code; MIMO only notes minor font-style and alignment deviation. |

The current conclusion is that MIMO is useful as an auxiliary visual cleanup
judge after the prompt is constrained to page-level visual assessment, but
unstable as a strict OCR or translation auditor on tight vertical Chinese
crops. The `preview-v5` image artifacts should still be judged manually for
reading order and final lettering preference.

For the current objective, the cleanup result is materially better than the old
white-paint failure: both original text areas are cleared and the translated
lettering is visible in the intended bubbles. Remaining quality work is layout
semantics, especially vertical reading order and font/style choices.

## Coverage

New coverage run:

```text
outputs/runs/phase0-8-gbc06-pipeline-coverage-v9
```

Summary:

```text
base_record_count=30
complete_record_count=30
incomplete_record_count=0
```

`GBC06_01.png#14` and `GBC06_01.png#15` are now complete across:

```text
phase1_labelplus
phase2_detection
phase3_font_selection
phase4_layout
phase5_angle
phase6_cleanup
phase7_preview
phase8_export
```

## Verification

Targeted verification:

```powershell
python -m pytest tests/test_phase7_preview_evaluation.py -q
git diff --check
```

Observed result before final full-suite verification:

```text
8 passed
git diff --check produced no output.
```
