# Phase 7/8 GBC06_02 #4-#6 Report

## Purpose

This run extends the verified auto-lettering loop to the next three `GBC06_02.png` bubble records:

- `GBC06_02.png#4`
- `GBC06_02.png#5`
- `GBC06_02.png#6`

The baseline integrated preview failed because Phase 6 cleaned only the selected detection column for `#5`, while Phase 4 correctly expanded the text layout target to the full multi-column source text region. The successful fix makes bubble cleanup crops cover the union of the selected detection bbox and the derived text bbox.

## Commands

Phase 3 font comparison:

```powershell
python experiments/phase3_font_comparison.py --labelplus-file "GBC06 (已翻 斗笠)\翻译_0.txt" --detection-run-dir outputs/runs/phase2-gbc06-smoke-v3 --font-dir "工具箱漫画字体V2.5" --run-id phase3-gbc06-02-batch-4-6-font-comparison --sample-limit 3 --font-limit 12 --record-id "GBC06_02.png#4" --record-id "GBC06_02.png#5" --record-id "GBC06_02.png#6"
```

Phase 3 MIMO font selection:

```powershell
python experiments/phase3_mimo_font_selection.py --input-run-dir outputs/runs/phase3-gbc06-02-batch-4-6-font-comparison --run-id phase3-gbc06-02-batch-4-6-mimo-font-selection --sample-limit 3 --record-id "GBC06_02.png#4" --record-id "GBC06_02.png#5" --record-id "GBC06_02.png#6"
```

Phase 5 orientation/angle:

```powershell
python experiments/phase5_orientation_angle.py --detection-run-dir outputs/runs/phase2-gbc06-smoke-v3 --run-id phase5-gbc06-02-batch-4-6-angle --sample-limit 3 --record-id "GBC06_02.png#4" --record-id "GBC06_02.png#5" --record-id "GBC06_02.png#6"
```

Phase 4 layout:

```powershell
python experiments/phase4_layout_search.py --selection-run-dir outputs/runs/phase3-gbc06-02-batch-4-6-mimo-font-selection --angle-run-dir outputs/runs/phase5-gbc06-02-batch-4-6-angle --detection-run-dir outputs/runs/phase2-gbc06-smoke-v3 --run-id phase4-gbc06-02-batch-4-6-layout-v1 --sample-limit 3 --record-id "GBC06_02.png#4" --record-id "GBC06_02.png#5" --record-id "GBC06_02.png#6"
```

Baseline Phase 6 cleanup:

```powershell
python experiments/phase6_bubble_cleanup.py --detection-run-dir outputs/runs/phase2-gbc06-smoke-v3 --layout-run-dir outputs/runs/phase4-gbc06-02-batch-4-6-layout-v1 --run-id phase6-gbc06-02-batch-4-6-region-fill-v1 --sample-limit 3 --cleanup-method region_fill --record-id "GBC06_02.png#4" --record-id "GBC06_02.png#5" --record-id "GBC06_02.png#6"
```

Baseline integrated preview:

```powershell
python experiments/phase7_8_integrated_smoke.py --detection-run-dir outputs/runs/phase2-gbc06-smoke-v3 --cleanup-run-dir outputs/runs/phase6-gbc06-02-batch-4-6-region-fill-v1 --layout-run-dir outputs/runs/phase4-gbc06-02-batch-4-6-layout-v1 --font-selection-run-dir outputs/runs/phase3-gbc06-02-batch-4-6-mimo-font-selection --run-id phase7-8-gbc06-02-batch-4-6-preview-v1 --sample-limit 3
```

Best Phase 6 cleanup after the fix:

```powershell
python experiments/phase6_bubble_cleanup.py --detection-run-dir outputs/runs/phase2-gbc06-smoke-v3 --layout-run-dir outputs/runs/phase4-gbc06-02-batch-4-6-layout-v1 --run-id phase6-gbc06-02-batch-4-6-region-fill-v2 --sample-limit 3 --cleanup-method region_fill --record-id "GBC06_02.png#4" --record-id "GBC06_02.png#5" --record-id "GBC06_02.png#6"
```

Best Phase 7/8 integrated run:

```powershell
python experiments/phase7_8_integrated_smoke.py --detection-run-dir outputs/runs/phase2-gbc06-smoke-v3 --cleanup-run-dir outputs/runs/phase6-gbc06-02-batch-4-6-region-fill-v2 --layout-run-dir outputs/runs/phase4-gbc06-02-batch-4-6-layout-v1 --font-selection-run-dir outputs/runs/phase3-gbc06-02-batch-4-6-mimo-font-selection --run-id phase7-8-gbc06-02-batch-4-6-preview-v2 --sample-limit 3
```

## Experiment Progression

### v1: Region Fill Baseline

Integrated run:

```text
outputs/runs/phase7-8-gbc06-02-batch-4-6-preview-v1
```

MIMO result:

```json
{
  "evaluation_score": 2,
  "evaluation_usable": false
}
```

Per-record MIMO summary:

| Record | Score | Usable | Notes |
| --- | ---: | --- | --- |
| `GBC06_02.png#4` | 7 | true | Text is readable but dense |
| `GBC06_02.png#5` | 2 | false | Text sits on a plain white rectangle and breaks the layout |
| `GBC06_02.png#6` | 9 | true | Well-fitted and clean |

Root cause:

- Phase 2 selected bbox for `#5` was only `[245, 516, 280, 636]`, covering the `ニナは` column.
- Phase 4 expanded the target bbox to `[167, 511, 280, 732]`, covering the multi-column source text.
- Phase 6 still emitted a cleanup crop for only `[245, 516, 280, 636]`, so the text overlay covered an area that had not been fully cleaned.

### v2: Cleanup Crop Covers Full Text BBox

Integrated run:

```text
outputs/runs/phase7-8-gbc06-02-batch-4-6-preview-v2
```

MIMO result:

```json
{
  "evaluation_score": 8,
  "evaluation_usable": true,
  "missing_cleanup_layers": 0,
  "effective_cleanup_methods": {
    "bubble_region_fill": 3
  }
}
```

Per-record MIMO summary:

| Record | Score | Usable | Notes |
| --- | ---: | --- | --- |
| `GBC06_02.png#4` | 9 | true | Background fill is clean; text is within bubble boundaries |
| `GBC06_02.png#5` | 8 | true | Original text is cleanly removed; bottom spacing is slightly tight |
| `GBC06_02.png#6` | 9 | true | Balanced placement and clean removal |

Key artifact:

```text
outputs/runs/phase7-8-gbc06-02-batch-4-6-preview-v2/runs/phase7-preview/debug/evaluation_contact_sheets/GBC06-02-png.png
```

The Phase 6 v2 cleanup result confirms the fixed crop for `#5`:

```json
{
  "record_id": "GBC06_02.png#5",
  "bbox": [167, 511, 280, 732],
  "method": "bubble_region_fill"
}
```

## Code Changes

- `autolettering/phase6.py`
  - Computes `text_bbox = selected_text_bbox(detection)`.
  - Cleans the union of the selected detection bbox and `text_bbox`.
  - Keeps the existing mask-limited composition contract intact.
- `tests/test_phase6_cleanup.py`
  - Adds a regression test for multi-column text where `text_bbox` extends outside the selected detection bbox.

## Coverage

New coverage run:

```text
outputs/runs/phase0-8-gbc06-pipeline-coverage-v6
```

Summary:

```text
base_record_count=30
complete_record_count=21
incomplete_record_count=9
```

The complete loop now includes:

```text
GBC06_02.png#4
GBC06_02.png#5
GBC06_02.png#6
```

The next practical `GBC06_02.png` expansion begins at:

```text
GBC06_02.png#7  first_missing_stage=phase3_font_selection
```

## Verification

Targeted verification during the fix:

```powershell
python -m pytest tests/test_phase6_cleanup.py::test_run_phase6_bubble_cleanup_expands_crop_to_full_text_bbox -q
python -m pytest tests/test_phase6_cleanup.py tests/test_phase7_preview.py -q
python -m pytest tests/test_text_bbox.py tests/test_phase4_layout.py::test_run_phase4_expands_tight_target_inside_selected_box_when_layout_overflows -q
```

Observed results:

```text
1 passed in 0.18s
24 passed in 0.82s
10 passed in 0.24s
```

Final full verification is recorded in the implementation turn terminal output.
