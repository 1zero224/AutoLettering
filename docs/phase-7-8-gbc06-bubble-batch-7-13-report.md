# Phase 7/8 GBC06 Bubble Batch #7-#13 Report

This report records the `GBC06_01.png#7` through `GBC06_01.png#13` closed-loop batch. The batch expanded the existing verified bubble pipeline from the previous `#2` through `#6` run and kept all visual artifacts under ignored `outputs/`.

## Purpose

The previous `#7` through `#13` preview attempt was unusable because text-region aggregation selected the wrong layout target for several adjacent speech bubbles:

- `GBC06_01.png#8` selected only one narrow source-text column.
- `GBC06_01.png#9` lost part of the intended text area.
- `GBC06_01.png#10` bridged across a wide gap and captured neighboring bubble text, producing an oversized white block and oversized lettering.
- `GBC06_01.png#11` was flagged by MIMO as a wrong or confused placement.

The fix target was Phase 4 layout input selection, not the bubble cleanup algorithm itself. Bubble cleanup still uses deterministic `bubble_region_fill`.

## Commands

Phase 3 deterministic font comparison:

```powershell
python experiments/phase3_font_comparison.py --detection-run-dir outputs/runs/phase2-gbc06-smoke --run-id phase3-gbc06-bubble-batch-7-13-font-comparison --sample-limit 7 --font-limit 12 --record-id 'GBC06_01.png#7' --record-id 'GBC06_01.png#8' --record-id 'GBC06_01.png#9' --record-id 'GBC06_01.png#10' --record-id 'GBC06_01.png#11' --record-id 'GBC06_01.png#12' --record-id 'GBC06_01.png#13'
```

Phase 5 orientation/angle:

```powershell
python experiments/phase5_orientation_angle.py --detection-run-dir outputs/runs/phase2-gbc06-smoke --run-id phase5-gbc06-bubble-batch-7-13-angle --sample-limit 7 --record-id 'GBC06_01.png#7' --record-id 'GBC06_01.png#8' --record-id 'GBC06_01.png#9' --record-id 'GBC06_01.png#10' --record-id 'GBC06_01.png#11' --record-id 'GBC06_01.png#12' --record-id 'GBC06_01.png#13'
```

Phase 3 MIMO font selection:

```powershell
python experiments/phase3_mimo_font_selection.py --input-run-dir outputs/runs/phase3-gbc06-bubble-batch-7-13-font-comparison --run-id phase3-gbc06-bubble-batch-7-13-mimo-font-selection --sample-limit 7 --record-id 'GBC06_01.png#7' --record-id 'GBC06_01.png#8' --record-id 'GBC06_01.png#9' --record-id 'GBC06_01.png#10' --record-id 'GBC06_01.png#11' --record-id 'GBC06_01.png#12' --record-id 'GBC06_01.png#13'
```

Corrected Phase 4 layout run:

```powershell
python experiments/phase4_layout_search.py --selection-run-dir outputs/runs/phase3-gbc06-bubble-batch-7-13-mimo-font-selection --angle-run-dir outputs/runs/phase5-gbc06-bubble-batch-7-13-angle --detection-run-dir outputs/runs/phase2-gbc06-smoke --run-id phase4-gbc06-bubble-batch-7-13-layout-v3 --sample-limit 7 --record-id 'GBC06_01.png#7' --record-id 'GBC06_01.png#8' --record-id 'GBC06_01.png#9' --record-id 'GBC06_01.png#10' --record-id 'GBC06_01.png#11' --record-id 'GBC06_01.png#12' --record-id 'GBC06_01.png#13'
```

Phase 6 cleanup:

```powershell
python experiments/phase6_bubble_cleanup.py --detection-run-dir outputs/runs/phase2-gbc06-smoke --layout-run-dir outputs/runs/phase4-gbc06-bubble-batch-7-13-layout-v3 --run-id phase6-gbc06-bubble-batch-7-13-region-fill-v2 --sample-limit 7 --cleanup-method region_fill
```

Phase 7/8 integrated preview, MIMO evaluation, and Photoshop export:

```powershell
python experiments/phase7_8_integrated_smoke.py --detection-run-dir outputs/runs/phase2-gbc06-smoke --cleanup-run-dir outputs/runs/phase6-gbc06-bubble-batch-7-13-region-fill-v2 --layout-run-dir outputs/runs/phase4-gbc06-bubble-batch-7-13-layout-v3 --font-selection-run-dir outputs/runs/phase3-gbc06-bubble-batch-7-13-mimo-font-selection --run-id phase7-8-gbc06-bubble-batch-7-13-preview-v2 --sample-limit 7
```

## Text Bbox Fix

`autolettering.text_bbox.selected_text_bbox` now uses score-aware text-column clustering:

- For scored candidates, it anchors on the best small candidate inside the selected detection instead of using the whole selected box as the anchor.
- A tight anchor can expand to nearby lower-scored adjacent columns, which fixes the single-column selection in `GBC06_01.png#8`.
- Adjacent-column expansion is capped by candidate width instead of current cluster width, which prevents `GBC06_01.png#10` from bridging into the neighboring bubble.
- Unscored legacy candidates keep the compatibility behavior of unioning all filtered small candidates. This preserves older wide multicolumn detection rows used by Phase 4 tests.

Regression tests now cover:

- tight candidate union inside a large detection
- low-score remote noise exclusion
- adjacent vertical cluster preservation
- tight selected-column expansion to adjacent columns
- wide-gap bridge prevention into a neighboring bubble
- unscored wide multicolumn candidate preservation

## Phase 4 Result

`outputs/runs/phase4-gbc06-bubble-batch-7-13-layout-v3/layout-results.jsonl` produced seven `layout_generated` rows:

```text
GBC06_01.png#7   font=34 orientation=vertical bbox=[143, 905, 178, 1029]   overflow=0.0
GBC06_01.png#8   font=14 orientation=vertical bbox=[1172, 1377, 1288, 1560] overflow=0.0
GBC06_01.png#9   font=13 orientation=vertical bbox=[722, 1365, 925, 1494]  overflow=0.0
GBC06_01.png#10  font=35 orientation=vertical bbox=[577, 1367, 653, 1555]  overflow=0.0
GBC06_01.png#11  font=28 orientation=vertical bbox=[678, 1831, 713, 1921]  overflow=0.0
GBC06_01.png#12  font=31 orientation=vertical bbox=[552, 1781, 584, 1952]  overflow=0.0
GBC06_01.png#13  font=25 orientation=vertical bbox=[334, 1379, 489, 1567]  overflow=0.0
```

The important correction is `GBC06_01.png#10`: the previous bad target captured `[441, 1336, 881, 1679]`; the corrected target is `[577, 1367, 653, 1555]`.

## Integrated Output

Run directory:

```text
outputs/runs/phase7-8-gbc06-bubble-batch-7-13-preview-v2
```

Generated subruns:

- Phase 7 preview: `outputs/runs/phase7-8-gbc06-bubble-batch-7-13-preview-v2/runs/phase7-preview`
- Phase 7 MIMO evaluation: `outputs/runs/phase7-8-gbc06-bubble-batch-7-13-preview-v2/runs/phase7-evaluation`
- Phase 8 Photoshop export: `outputs/runs/phase7-8-gbc06-bubble-batch-7-13-preview-v2/runs/phase8-export`

Key visual artifact:

```text
outputs/runs/phase7-8-gbc06-bubble-batch-7-13-preview-v2/runs/phase7-preview/debug/evaluation_contact_sheets/GBC06-01-png.png
```

Integrated manifest summary:

```json
{
  "preview_page_count": 1,
  "preview_record_count": 7,
  "skipped_count": 0,
  "evaluation_status": "evaluated",
  "evaluation_score": 8,
  "evaluation_usable": true,
  "exported_page_count": 1,
  "exported_text_layer_count": 7,
  "missing_cleanup_layers": 0,
  "effective_cleanup_methods": {
    "bubble_region_fill": 7
  }
}
```

## MIMO Evaluation

MIMO model: `mimo-v2.5`

MIMO returned a usable page score:

```json
{
  "score": 8,
  "usable": true,
  "original_text_removed": true,
  "art_preserved": true,
  "lettering_readable": true
}
```

Per-record scores from the raw model response:

```text
GBC06_01.png#7   score=9 usable=true
GBC06_01.png#8   score=9 usable=true
GBC06_01.png#9   score=9 usable=true
GBC06_01.png#10  score=8 usable=true
GBC06_01.png#11  score=8 usable=true
GBC06_01.png#12  score=8 usable=true
GBC06_01.png#13  score=8 usable=true
```

Reported issues:

- `GBC06_01.png#10`: line break in `不满 / 渗透而出` is slightly awkward.
- `GBC06_01.png#11`, `#12`, and `#13`: MIMO notes simplified Chinese text in a traditionally lettered comic. This is a source-text/localization policy issue, not a cleanup failure.

Manual inspection of the contact sheet agrees with MIMO on the main outcome: original text is removed, art is preserved, and the corrected `#10` no longer covers adjacent bubble content. The remaining visible work is typography and translation-form refinement.

## Coverage Impact

The v3 pipeline coverage report includes this batch and raises closed-loop coverage from 7 to 14 records:

```text
base_record_count=30
complete_record_count=14
incomplete_record_count=16
```

Newly completed records:

```text
GBC06_01.png#7
GBC06_01.png#8
GBC06_01.png#9
GBC06_01.png#10
GBC06_01.png#11
GBC06_01.png#12
GBC06_01.png#13
```

## Verification

Targeted tests after the bbox fix:

```powershell
python -m pytest tests/test_text_bbox.py -q
python -m pytest tests/test_phase4_layout.py tests/test_phase6_cleanup.py -q
python -m pytest -q
```

Observed results:

```text
6 passed in 0.07s
25 passed in 1.40s
113 passed in 4.03s
```

The integrated run performed a real MIMO evaluation and wrote the evaluation JSONL at:

```text
outputs/runs/phase7-8-gbc06-bubble-batch-7-13-preview-v2/runs/phase7-evaluation/preview-evaluation.jsonl
```
