# Phase 7/8 GBC06_02 #10-#13 Report

## Purpose

This run extends the verified auto-lettering loop to the next four `GBC06_02.png` bubble records:

- `GBC06_02.png#10`
- `GBC06_02.png#11`
- `GBC06_02.png#12`
- `GBC06_02.png#13`

The baseline integrated preview was unusable. `#10` selected a large merged detection region that included neighboring text, while `#11` and `#12` failed layout because the original target boxes were too tight for the translated text.

## Commands

Phase 3 font comparison:

```powershell
python experiments/phase3_font_comparison.py --labelplus-file "GBC06 (已翻 斗笠)\翻译_0.txt" --detection-run-dir outputs/runs/phase2-gbc06-smoke-v3 --font-dir "工具箱漫画字体V2.5" --run-id phase3-gbc06-02-batch-10-13-font-comparison --sample-limit 4 --font-limit 12 --record-id "GBC06_02.png#10" --record-id "GBC06_02.png#11" --record-id "GBC06_02.png#12" --record-id "GBC06_02.png#13"
```

Phase 3 MIMO font selection:

```powershell
python experiments/phase3_mimo_font_selection.py --input-run-dir outputs/runs/phase3-gbc06-02-batch-10-13-font-comparison --run-id phase3-gbc06-02-batch-10-13-mimo-font-selection --sample-limit 4 --record-id "GBC06_02.png#10" --record-id "GBC06_02.png#11" --record-id "GBC06_02.png#12" --record-id "GBC06_02.png#13"
```

Phase 5 orientation/angle:

```powershell
python experiments/phase5_orientation_angle.py --detection-run-dir outputs/runs/phase2-gbc06-smoke-v3 --run-id phase5-gbc06-02-batch-10-13-angle --sample-limit 4 --record-id "GBC06_02.png#10" --record-id "GBC06_02.png#11" --record-id "GBC06_02.png#12" --record-id "GBC06_02.png#13"
```

Baseline Phase 4 layout:

```powershell
python experiments/phase4_layout_search.py --selection-run-dir outputs/runs/phase3-gbc06-02-batch-10-13-mimo-font-selection --angle-run-dir outputs/runs/phase5-gbc06-02-batch-10-13-angle --detection-run-dir outputs/runs/phase2-gbc06-smoke-v3 --run-id phase4-gbc06-02-batch-10-13-layout-v1 --sample-limit 4 --record-id "GBC06_02.png#10" --record-id "GBC06_02.png#11" --record-id "GBC06_02.png#12" --record-id "GBC06_02.png#13"
```

Baseline Phase 6 cleanup:

```powershell
python experiments/phase6_bubble_cleanup.py --detection-run-dir outputs/runs/phase2-gbc06-smoke-v3 --layout-run-dir outputs/runs/phase4-gbc06-02-batch-10-13-layout-v1 --run-id phase6-gbc06-02-batch-10-13-region-fill-v1 --sample-limit 4 --cleanup-method region_fill --record-id "GBC06_02.png#10" --record-id "GBC06_02.png#11" --record-id "GBC06_02.png#12" --record-id "GBC06_02.png#13"
```

Baseline integrated preview:

```powershell
python experiments/phase7_8_integrated_smoke.py --detection-run-dir outputs/runs/phase2-gbc06-smoke-v3 --cleanup-run-dir outputs/runs/phase6-gbc06-02-batch-10-13-region-fill-v1 --layout-run-dir outputs/runs/phase4-gbc06-02-batch-10-13-layout-v1 --font-selection-run-dir outputs/runs/phase3-gbc06-02-batch-10-13-mimo-font-selection --run-id phase7-8-gbc06-02-batch-10-13-preview-v1 --sample-limit 4
```

Best Phase 4 layout:

```powershell
python experiments/phase4_layout_search.py --selection-run-dir outputs/runs/phase3-gbc06-02-batch-10-13-mimo-font-selection --angle-run-dir outputs/runs/phase5-gbc06-02-batch-10-13-angle --detection-run-dir outputs/runs/phase2-gbc06-smoke-v3 --run-id phase4-gbc06-02-batch-10-13-layout-v5 --sample-limit 4 --record-id "GBC06_02.png#10" --record-id "GBC06_02.png#11" --record-id "GBC06_02.png#12" --record-id "GBC06_02.png#13"
```

Best Phase 6 cleanup:

```powershell
python experiments/phase6_bubble_cleanup.py --detection-run-dir outputs/runs/phase2-gbc06-smoke-v3 --layout-run-dir outputs/runs/phase4-gbc06-02-batch-10-13-layout-v5 --run-id phase6-gbc06-02-batch-10-13-region-fill-v6 --sample-limit 4 --cleanup-method region_fill --record-id "GBC06_02.png#10" --record-id "GBC06_02.png#11" --record-id "GBC06_02.png#12" --record-id "GBC06_02.png#13"
```

Best Phase 7/8 integrated run:

```powershell
python experiments/phase7_8_integrated_smoke.py --detection-run-dir outputs/runs/phase2-gbc06-smoke-v3 --cleanup-run-dir outputs/runs/phase6-gbc06-02-batch-10-13-region-fill-v6 --layout-run-dir outputs/runs/phase4-gbc06-02-batch-10-13-layout-v5 --font-selection-run-dir outputs/runs/phase3-gbc06-02-batch-10-13-mimo-font-selection --run-id phase7-8-gbc06-02-batch-10-13-preview-v7 --sample-limit 4
```

## Experiment Progression

### v1: Unusable Baseline

Integrated run:

```text
outputs/runs/phase7-8-gbc06-02-batch-10-13-preview-v1
```

MIMO result:

```json
{
  "evaluation_score": 0,
  "evaluation_usable": false
}
```

Root causes:

- `#10` used `selected_text_box_xyxy=[177,1116,617,1376]`, a large aggregate region covering `へぇ〜` and neighboring Japanese text. The translation `诶？` was placed into the wrong area and the target original text stayed visible.
- `#11` failed Phase 4 because only the `あの` column was selected; the adjacent `もしかして...` column was excluded by the area filter.
- `#12` failed Phase 4 because the minimum 12px vertical layout overflowed slightly, but the layout search only accepted zero-overflow candidates.

### v5/v6: BBox, Layout, and Cleanup Fixes

Best layout run:

```text
outputs/runs/phase4-gbc06-02-batch-10-13-layout-v5
```

Key layout results:

| Record | Target bbox | Font size | Line breaks | Overflow |
| --- | --- | ---: | --- | ---: |
| `GBC06_02.png#10` | `[343,1215,381,1302]` | 38 | `诶？` | 0.0 |
| `GBC06_02.png#11` | `[157,1158,230,1347]` | 31 | `那个\n莫非是要…` | 0.0 |
| `GBC06_02.png#12` | `[1191,1428,1303,1587]` | 24 | `所谓的街头表\n演就是在别人\n面前唱歌吗？` | 0.0 |
| `GBC06_02.png#13` | `[899,1822,972,1918]` | 16 | `那是必然的` | 0.0 |

Best cleanup run:

```text
outputs/runs/phase6-gbc06-02-batch-10-13-region-fill-v6
```

The cleanup now uses the derived actual text bbox as the crop bbox. This avoids large false-positive selected boxes from polluting per-record preview crops, especially for `#10`.

### v7: Best Integrated Result

Integrated run:

```text
outputs/runs/phase7-8-gbc06-02-batch-10-13-preview-v7
```

MIMO result:

```json
{
  "evaluation_score": 4,
  "evaluation_usable": true,
  "missing_cleanup_layers": 0,
  "effective_cleanup_methods": {
    "bubble_region_fill": 4
  }
}
```

Per-record MIMO summary:

| Record | Score | Usable | Notes |
| --- | ---: | --- | --- |
| `GBC06_02.png#10` | 4 | true | MIMO still reports partial original-text visibility; visual contact sheet shows the tight crop is cleaned, but this remains the weakest item. |
| `GBC06_02.png#11` | 8 | true | Original text removed; lettering readable but slightly condensed. |
| `GBC06_02.png#12` | 7 | true | Original text removed; text is readable but slightly wide for the original area. |
| `GBC06_02.png#13` | 8 | true | Original text removed; lettering well placed and readable. |

Key artifact:

```text
outputs/runs/phase7-8-gbc06-02-batch-10-13-preview-v7/runs/phase7-preview/debug/evaluation_contact_sheets/GBC06-02-png.png
```

An attempted widened/upscaled evaluation-contact-sheet format caused MIMO to over-penalize tight crops as if full speech-bubble backgrounds were missing. That change was rejected; the selected artifact remains v7.

## Code Changes

- `autolettering/text_bbox.py`
  - Uses the selected candidate's original polarity before falling back to filtered candidate polarity, preventing white bubble interiors from making dark-on-light text look like light-on-dark text.
  - Allows tight selected columns to retain adjacent high-score columns.
  - Joins short same-column vertical glyph fragments, fixing the missing top `へ` fragment in `#10`.
- `autolettering/layout/measure.py`
  - Tries zero-overflow layouts first, then bounded-overflow layouts.
  - Generates balanced vertical reflow candidates for longer translations.
  - Keeps short vertical translations as one column.
- `autolettering/phase4.py`
  - Caps explicit multi-column vertical translations below the source column width to avoid oversized dense text.
- `autolettering/phase6.py`
  - Uses the actual derived text bbox as the bubble cleanup crop, rather than unioning it with an often-large selected detection bbox.
- `autolettering/phase7_evaluate.py`
  - Clarifies that MIMO should judge original removal on the after side of the before/after contact sheet.

## Coverage

New coverage run:

```text
outputs/runs/phase0-8-gbc06-pipeline-coverage-v8
```

Summary:

```text
base_record_count=30
complete_record_count=28
incomplete_record_count=2
```

The complete loop now includes:

```text
GBC06_02.png#10
GBC06_02.png#11
GBC06_02.png#12
GBC06_02.png#13
```

The remaining coverage gaps are the historical records:

```text
GBC06_01.png#14  first_missing_stage=phase4_layout
GBC06_01.png#15  first_missing_stage=phase4_layout
```

## Verification

Targeted verification during the fix:

```powershell
python -m pytest tests/test_text_bbox.py -q
python -m pytest tests/test_phase4_layout.py -q
python -m pytest tests/test_phase6_cleanup.py -q
python -m pytest tests/test_phase7_preview_evaluation.py -q
```

Fresh final verification before commit:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'; python -m pytest -q
git diff --check
```

Observed result:

```text
144 passed in 5.21s
git diff --check produced no output.
```
