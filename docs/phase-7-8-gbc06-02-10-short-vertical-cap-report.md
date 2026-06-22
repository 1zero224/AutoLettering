# Phase 7/8 GBC06_02 #10 Short Vertical Cap Report

## Purpose

This experiment narrows the `GBC06_02.png#10` quality issue after the earlier `#10-#13` batch run.

The old batch v7 MIMO score was `4`, but a single-record re-evaluation showed that cleanup was already effective. The remaining visible defect was typography: the very short vertical translation `诶？` was rendered too large and too heavy because the layout search maximized font size against the full target height.

## Baseline Diagnosis

Single-record preview:

```text
outputs/runs/phase7-gbc06-02-10-single-preview-v1
```

Single-record MIMO evaluation:

```text
outputs/runs/phase7-gbc06-02-10-single-preview-v1-mimo-eval/preview-evaluation.jsonl
```

Result:

```json
{
  "score": 8,
  "usable": true,
  "original_text_removed": true,
  "issues": [
    "The lettering is noticeably thicker and heavier than the original text.",
    "The lettering size is slightly larger than the original text."
  ]
}
```

This changed the root-cause interpretation:

- The old batch score over-penalized `#10` from a multi-record contact sheet.
- Bubble cleanup was already good enough for `#10`.
- The useful next fix was a deterministic typography cap for very short vertical translations.

## Font Candidate Experiment

Manual candidate comparison artifacts:

```text
outputs/runs/phase3-gbc06-02-10-manual-font-candidates-v1/
outputs/runs/phase7-gbc06-02-10-font-candidate-comparison-v1/debug/local-method-comparison.png
outputs/runs/phase7-gbc06-02-10-font-size-comparison-v1/debug/local-method-comparison.png
```

Fixed-size candidates at `34px` were evaluated with MIMO:

| Candidate | MIMO score | Notes |
| --- | ---: | --- |
| `wanshu34` | 10 | Usable |
| `yuan34` | 10 | Usable |
| `yaoyang34` | 9 | Usable |
| `wenhei34` | 10 | Usable |

The result showed that the dominant problem was size, not the current selected WenHei font.

## Code Change

The layout cap now distinguishes very short vertical translations from the existing short-vertical case.

```python
def _very_short_vertical_translation(translated_text: str) -> bool:
    text = "".join(str(translated_text).split())
    return 0 < len(text) <= 2
```

For vertical translations of one or two non-whitespace characters, Phase 4 caps the maximum font size at `0.9 * source_column_width`. Existing short vertical translations of up to four characters keep the previous `1.0 * source_column_width` cap.

Regression test:

```text
tests/test_phase4_layout.py::test_run_phase4_caps_very_short_vertical_translation_below_source_glyph_width
```

## Auto Experiment v2: Size Cap

Auto layout run:

```text
outputs/runs/phase4-gbc06-02-10-auto-short-cap-v2
```

Key layout result:

```json
{
  "record_id": "GBC06_02.png#10",
  "font_size": 34,
  "target_bbox": [343, 1215, 381, 1302],
  "target_width": 38,
  "target_height": 87,
  "orientation": "vertical",
  "angle_degrees": 0.0,
  "vertical_align": "center",
  "measured_width": 34,
  "measured_height": 67
}
```

Auto preview:

```text
outputs/runs/phase7-gbc06-02-10-auto-short-cap-v2
```

Auto MIMO evaluation:

```text
outputs/runs/phase7-gbc06-02-10-auto-short-cap-v2-mimo-eval/preview-evaluation.jsonl
```

Result:

```json
{
  "score": 9,
  "usable": true,
  "original_text_removed": true,
  "art_preserved": true,
  "lettering_readable": true,
  "issues": []
}
```

Comparison image for manual review:

```text
outputs/runs/phase7-gbc06-02-10-final-comparison-v3/debug/local-method-comparison.png
```

## Auto Experiment v3: Top-Aligned Vertical Lettering

The v2 result fixed size, but it still vertically centered a very short vertical string inside a taller original text box. This is not a good default for manga vertical lettering. Phase 4 now top-aligns vertical layouts by default while keeping horizontal layouts centered.

Top-align layout run:

```text
outputs/runs/phase4-gbc06-02-10-top-align-v3
```

Key layout result:

```json
{
  "record_id": "GBC06_02.png#10",
  "font_size": 34,
  "target_bbox": [343, 1215, 381, 1302],
  "orientation": "vertical",
  "angle_degrees": 0.0,
  "vertical_align": "top",
  "alignment": {
    "ink_bbox": [2, 0, 36, 67],
    "vertical_center_offset_px": -10.0
  }
}
```

Top-align preview and MIMO evaluation:

```text
outputs/runs/phase7-8-gbc06-02-10-top-align-v3
outputs/runs/phase7-8-gbc06-02-10-top-align-v3/runs/phase7-evaluation/preview-evaluation.jsonl
```

Result:

```json
{
  "score": 9,
  "usable": true,
  "original_text_removed": true,
  "art_preserved": true,
  "lettering_readable": true,
  "issues": []
}
```

Manual comparison against the v2 centered output:

```text
outputs/runs/phase7-gbc06-02-10-center-vs-top-align-v3/debug/local-method-comparison.png
```

## Batch Re-run

Batch v8 layout:

```text
outputs/runs/phase4-gbc06-02-batch-10-13-layout-v8
```

Key layout values:

| Record | Font size | Target bbox | Line breaks | Angle |
| --- | ---: | --- | --- | ---: |
| `GBC06_02.png#10` | 34 | `[343,1215,381,1302]` | `诶？` | 0.0 |
| `GBC06_02.png#11` | 31 | `[157,1158,230,1347]` | `那个\n莫非是要…` | 0.0 |
| `GBC06_02.png#12` | 24 | `[1191,1428,1303,1587]` | `所谓的街头表\n演就是在别人\n面前唱歌吗？` | 0.0 |
| `GBC06_02.png#13` | 16 | `[899,1822,972,1918]` | `那是必然的` | 0.0 |

Batch v8 cleanup and integrated preview:

```text
outputs/runs/phase6-gbc06-02-batch-10-13-region-fill-v8
outputs/runs/phase7-8-gbc06-02-batch-10-13-preview-v8
```

Batch v8 MIMO:

```json
{
  "score": 6,
  "usable": true,
  "original_text_removed": true,
  "art_preserved": true,
  "lettering_readable": false,
  "issues": [
    "Record #11: The layout of '那个' and '莫非是要...' is disjointed and reads unnaturally. Record #12: The line breaks in the translation are incorrect and do not follow the expected reading order, resulting in garbled, unreadable text."
  ]
}
```

Batch comparison image:

```text
outputs/runs/phase7-gbc06-02-batch-10-13-v7-v8-comparison/debug/local-method-comparison.png
```

Batch v9 applies the same top-align rule to all vertical records:

```text
outputs/runs/phase4-gbc06-02-batch-10-13-layout-v9-top-align
outputs/runs/phase6-gbc06-02-batch-10-13-region-fill-v9-top-align
outputs/runs/phase7-8-gbc06-02-batch-10-13-preview-v9-top-align
```

Batch v9 MIMO:

```json
{
  "score": 9,
  "usable": true,
  "original_text_removed": true,
  "art_preserved": true,
  "lettering_readable": true,
  "issues": [
    "Minor imperfections in the background fill (slight blur/texture loss) are visible upon close inspection, but do not detract from readability or overall quality."
  ]
}
```

Batch v8/v9 comparison:

```text
outputs/runs/phase7-gbc06-02-batch-10-13-v8-v9-top-align-comparison/debug/local-method-comparison.png
```

## Conclusion

The `#10` fix is usable:

- The automatic layout now renders `诶？` at `34px` instead of the older `38px`.
- The text remains upright vertical with `angle_degrees=0.0`.
- Phase 4 now top-aligns vertical lettering by default; `#10` ink starts at the top of the target box instead of being vertically centered.
- Single-record MIMO improved from `8` with size/weight issues to `9` with no issues.
- Batch MIMO improved from v8 `6` to v9 `9`; the previous `#11/#12` layout/read-order complaint is not present in the v9 evaluation.

The current best result for this batch is `phase7-8-gbc06-02-batch-10-13-preview-v9-top-align`.
