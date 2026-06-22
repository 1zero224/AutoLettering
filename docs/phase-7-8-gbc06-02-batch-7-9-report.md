# Phase 7/8 GBC06_02 #7-#9 Report

## Purpose

This run extends the verified auto-lettering loop to the next three `GBC06_02.png` bubble records:

- `GBC06_02.png#7`
- `GBC06_02.png#8`
- `GBC06_02.png#9`

The baseline integrated preview was usable but visually weak because short vertical translations were allowed to grow until they filled the target height. The successful fix caps short vertical translations closer to the source glyph column width.

## Commands

Phase 3 font comparison:

```powershell
python experiments/phase3_font_comparison.py --labelplus-file "GBC06 (已翻 斗笠)\翻译_0.txt" --detection-run-dir outputs/runs/phase2-gbc06-smoke-v3 --font-dir "工具箱漫画字体V2.5" --run-id phase3-gbc06-02-batch-7-9-font-comparison --sample-limit 3 --font-limit 12 --record-id "GBC06_02.png#7" --record-id "GBC06_02.png#8" --record-id "GBC06_02.png#9"
```

Phase 3 MIMO font selection:

```powershell
python experiments/phase3_mimo_font_selection.py --input-run-dir outputs/runs/phase3-gbc06-02-batch-7-9-font-comparison --run-id phase3-gbc06-02-batch-7-9-mimo-font-selection --sample-limit 3 --record-id "GBC06_02.png#7" --record-id "GBC06_02.png#8" --record-id "GBC06_02.png#9"
```

Phase 5 orientation/angle:

```powershell
python experiments/phase5_orientation_angle.py --detection-run-dir outputs/runs/phase2-gbc06-smoke-v3 --run-id phase5-gbc06-02-batch-7-9-angle --sample-limit 3 --record-id "GBC06_02.png#7" --record-id "GBC06_02.png#8" --record-id "GBC06_02.png#9"
```

Baseline Phase 4 layout:

```powershell
python experiments/phase4_layout_search.py --selection-run-dir outputs/runs/phase3-gbc06-02-batch-7-9-mimo-font-selection --angle-run-dir outputs/runs/phase5-gbc06-02-batch-7-9-angle --detection-run-dir outputs/runs/phase2-gbc06-smoke-v3 --run-id phase4-gbc06-02-batch-7-9-layout-v1 --sample-limit 3 --record-id "GBC06_02.png#7" --record-id "GBC06_02.png#8" --record-id "GBC06_02.png#9"
```

Baseline Phase 6 cleanup:

```powershell
python experiments/phase6_bubble_cleanup.py --detection-run-dir outputs/runs/phase2-gbc06-smoke-v3 --layout-run-dir outputs/runs/phase4-gbc06-02-batch-7-9-layout-v1 --run-id phase6-gbc06-02-batch-7-9-region-fill-v1 --sample-limit 3 --cleanup-method region_fill --record-id "GBC06_02.png#7" --record-id "GBC06_02.png#8" --record-id "GBC06_02.png#9"
```

Baseline integrated preview:

```powershell
python experiments/phase7_8_integrated_smoke.py --detection-run-dir outputs/runs/phase2-gbc06-smoke-v3 --cleanup-run-dir outputs/runs/phase6-gbc06-02-batch-7-9-region-fill-v1 --layout-run-dir outputs/runs/phase4-gbc06-02-batch-7-9-layout-v1 --font-selection-run-dir outputs/runs/phase3-gbc06-02-batch-7-9-mimo-font-selection --run-id phase7-8-gbc06-02-batch-7-9-preview-v1 --sample-limit 3
```

Best Phase 4 layout after the short-vertical cap:

```powershell
python experiments/phase4_layout_search.py --selection-run-dir outputs/runs/phase3-gbc06-02-batch-7-9-mimo-font-selection --angle-run-dir outputs/runs/phase5-gbc06-02-batch-7-9-angle --detection-run-dir outputs/runs/phase2-gbc06-smoke-v3 --run-id phase4-gbc06-02-batch-7-9-layout-v2 --sample-limit 3 --record-id "GBC06_02.png#7" --record-id "GBC06_02.png#8" --record-id "GBC06_02.png#9"
```

Best Phase 6 cleanup:

```powershell
python experiments/phase6_bubble_cleanup.py --detection-run-dir outputs/runs/phase2-gbc06-smoke-v3 --layout-run-dir outputs/runs/phase4-gbc06-02-batch-7-9-layout-v2 --run-id phase6-gbc06-02-batch-7-9-region-fill-v2 --sample-limit 3 --cleanup-method region_fill --record-id "GBC06_02.png#7" --record-id "GBC06_02.png#8" --record-id "GBC06_02.png#9"
```

Best Phase 7/8 integrated run:

```powershell
python experiments/phase7_8_integrated_smoke.py --detection-run-dir outputs/runs/phase2-gbc06-smoke-v3 --cleanup-run-dir outputs/runs/phase6-gbc06-02-batch-7-9-region-fill-v2 --layout-run-dir outputs/runs/phase4-gbc06-02-batch-7-9-layout-v2 --font-selection-run-dir outputs/runs/phase3-gbc06-02-batch-7-9-mimo-font-selection --run-id phase7-8-gbc06-02-batch-7-9-preview-v2 --sample-limit 3
```

## Experiment Progression

### v1: Usable But Oversized

Integrated run:

```text
outputs/runs/phase7-8-gbc06-02-batch-7-9-preview-v1
```

MIMO result:

```json
{
  "evaluation_score": 5,
  "evaluation_usable": true
}
```

Per-record MIMO summary:

| Record | Score | Usable | Notes |
| --- | ---: | --- | --- |
| `GBC06_02.png#7` | 7 | true | Slightly larger than original |
| `GBC06_02.png#8` | 5 | true | Significantly oversized and outside original text area |
| `GBC06_02.png#9` | 6 | true | Larger and wider than original text area |

Root cause:

- The deterministic layout search selects the largest font size that fits the target box.
- For very short vertical text such as `循环器`, this can scale the glyphs up to fill the height, even when the source text column width indicates a smaller original style.

### v2: Short Vertical Font Cap

Integrated run:

```text
outputs/runs/phase7-8-gbc06-02-batch-7-9-preview-v2
```

MIMO result:

```json
{
  "evaluation_score": 9,
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
| `GBC06_02.png#7` | 9 | true | Fits original bounds without overlapping adjacent art |
| `GBC06_02.png#8` | 9 | true | Clear and respects original boundaries |
| `GBC06_02.png#9` | 9 | true | Neatly placed and preserves surrounding space |

Key artifact:

```text
outputs/runs/phase7-8-gbc06-02-batch-7-9-preview-v2/runs/phase7-preview/debug/evaluation_contact_sheets/GBC06-02-png.png
```

The useful layout change is visible on `GBC06_02.png#8`:

```text
v1 font_size=43 measured_height=127
v2 font_size=38 measured_height=114
```

## Code Changes

- `autolettering/phase4.py`
  - Passes the current selected row's `translated_text` into the vertical font-size cap.
  - Uses a conservative source-column-width multiplier for short vertical translations of 4 non-whitespace characters or fewer.
- `tests/test_phase4_layout.py`
  - Adds a regression test based on the `GBC06_02.png#8` geometry.

## Coverage

New coverage run:

```text
outputs/runs/phase0-8-gbc06-pipeline-coverage-v7
```

Summary:

```text
base_record_count=30
complete_record_count=24
incomplete_record_count=6
```

The complete loop now includes:

```text
GBC06_02.png#7
GBC06_02.png#8
GBC06_02.png#9
```

The next practical `GBC06_02.png` expansion begins at:

```text
GBC06_02.png#10  first_missing_stage=phase3_font_selection
```

## Verification

Targeted verification during the fix:

```powershell
python -m pytest tests/test_phase4_layout.py::test_run_phase4_keeps_short_vertical_translation_close_to_source_glyph_width -q
python -m pytest tests/test_phase4_layout.py -q
```

Observed results:

```text
1 passed in 0.17s
22 passed in 1.34s
```

Final full verification is recorded in the implementation turn terminal output.
