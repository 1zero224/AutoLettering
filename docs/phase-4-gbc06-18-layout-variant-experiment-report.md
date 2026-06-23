# Phase 4 GBC06_18 Layout Variant Experiment

## Scope

This experiment focuses only on `GBC06_18.png#3`, the first diamond announcer
block. Cleanup is fixed to the previous `bt_lama_large` result so the
comparison isolates translated lettering layout.

Inputs:

```text
detection: outputs/runs/phase2-gbc06-diverse-expansion-v2-color-light-text
font: outputs/runs/phase3-gbc06-diverse-06-18-mimo-font-selection-v1
layout baseline: outputs/runs/phase4-gbc06-diverse-06-18-layout-tight-mask-v2
cleanup: outputs/runs/phase6-gbc06-18-text-mask-bt-lama-large-v2
```

The baseline layout was:

```json
{
  "line_breaks": "-快看接下\n来登场的乐\n队竟然！",
  "font_size": 33,
  "line_spacing": 4,
  "vertical_align": "top",
  "angle_degrees": 0.0
}
```

That result is readable, but it splits the phrase `接下来`, and the translated
lettering is visually too heavy for the source region.

## Experiment

Script:

```powershell
python experiments/phase4_layout_variant_experiment.py --run-id phase4-gbc06-18-layout-variants-v2
```

Artifacts:

```text
outputs/runs/phase4-gbc06-18-layout-variants-v2/visuals/layout-variant-grid.png
outputs/runs/phase4-gbc06-18-layout-variants-v2/reports/layout-variant-summary.json
outputs/runs/phase4-gbc06-18-layout-variants-v2/reports/mimo-layout-variant-evaluation.json
```

The MIMO grid is near-square: `1030x1102`.

## Results

MIMO selected `phrase_fs27_s0`:

```json
{
  "best_variant": "phrase_fs27_s0",
  "scores": {
    "phrase_fs27_s0": 95,
    "phrase_fs26_s0": 92,
    "phrase_fs25_s0": 90,
    "phrase_fs24_s1": 88,
    "current_fs28_s1": 85,
    "scene_fs28_s1": 83,
    "phrase_fs27_s1": 80,
    "current_fs33_s4": 75,
    "phrase_fs29_s0": 40
  },
  "unacceptable_variants": ["phrase_fs29_s0"]
}
```

Programmatic measurement adds a stricter boundary check:

| Variant | Line breaks | Font size | Spacing | Overflow | Ink bbox |
| --- | --- | ---: | ---: | ---: | --- |
| `phrase_fs27_s0` | `-快看 / 接下来登场的乐队 / 竟然！` | 27 | 0 | 0.0365 | `[17, 0, 98, 192]` |
| `phrase_fs26_s0` | `-快看 / 接下来登场的乐队 / 竟然！` | 26 | 0 | 0.0312 | `[18, 0, 96, 192]` |
| `phrase_fs25_s0` | `-快看 / 接下来登场的乐队 / 竟然！` | 25 | 0 | 0.0 | `[20, 0, 95, 190]` |
| `phrase_fs24_s1` | `-快看 / 接下来登场的乐队 / 竟然！` | 24 | 1 | 0.0 | `[20, 0, 94, 190]` |

Decision:

- Best model-preferred candidate: `phrase_fs27_s0`.
- Best conservative candidate for the pipeline: `phrase_fs25_s0`.
- Keep `angle_degrees=0.0`; none of the useful candidates require rotation.
- Keep `vertical_align=top`, but avoid text layers whose ink reaches the bottom
  edge.

The conservative candidate preserves the phrase `接下来登场的乐队`, removes the
mechanical `接下 / 来` split, and leaves a small bottom margin.

## Core Search Integration

The conservative `phrase_fs25_s0` behavior is now promoted into the core Phase 4
layout search instead of remaining an isolated experiment.

Changed code:

```text
autolettering/layout/measure.py
tests/test_phase4_layout.py
```

New behavior:

- Vertical search keeps explicit multi-line input as the first candidate.
- Vertical layouts search `line_spacing` candidates `[0, 1, 2, 4]` instead of
  using fixed spacing `4`.
- Candidate scoring can choose a phrase-preserving explicit layout over the
  absolute largest fitting balanced split, but only when the explicit layout is
  title-like and still at least 70% of the largest available font size.
- Angle remains `0.0`; this case is plain vertical manga text and should not be
  rotated.
- The output remains top-aligned through the existing Phase 4/7 text placement
  path.

Regression target:

```python
result.line_breaks == "-快看\n接下来登场的乐队\n竟然！"
"接下\n来" not in result.line_breaks
result.font_size <= 25
result.overflow_ratio == 0.0
```

Verification:

```text
python -m pytest tests/test_phase4_layout.py tests/test_phase4_layout_variant_experiment.py -q
37 passed
```

Hard-record rerun:

```powershell
python experiments/phase4_layout_search.py `
  --selection-run-dir outputs/runs/phase3-gbc06-diverse-06-18-mimo-font-selection-v1 `
  --detection-run-dir outputs/runs/phase2-gbc06-diverse-expansion-v2-color-light-text `
  --run-id phase4-gbc06-18-phrase-aware-layout-v1 `
  --sample-limit 1 `
  --record-id "GBC06_18.png#3"
```

Output:

```text
outputs/runs/phase4-gbc06-18-phrase-aware-layout-v1/layout-results.jsonl
```

The generated layout is:

```json
{
  "line_breaks": "-快看\n接下来登场的乐队\n竟然！",
  "font_size": 25,
  "orientation": "vertical",
  "line_spacing": 0,
  "angle_degrees": 0.0,
  "target_width": 115,
  "target_height": 192,
  "measured_width": 75,
  "measured_height": 190,
  "overflow_ratio": 0.0,
  "vertical_align": "top"
}
```

## Phase 7 Coupled Cleanup Validation

The new layout was then tested in real Phase 7 previews. The first attempt used
the previous d3 `bt_lama_large` cleanup:

```text
outputs/runs/phase7-gbc06-18-phrase-aware-layout-v1
outputs/runs/phase7-gbc06-18-phrase-aware-layout-eval-v1/preview-evaluation.jsonl
```

MIMO score: `4`. The narrower, better-phrased text exposed residual cleanup
artifacts that the old oversized text had hidden.

The same layout with the stronger d5 text mask produced the usable result:

```text
outputs/runs/phase7-gbc06-18-phrase-aware-layout-d5-v1
outputs/runs/phase7-gbc06-18-phrase-aware-layout-d5-eval-v1/preview-evaluation.jsonl
```

MIMO result:

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

Finally, a near-square comparison grid evaluated three layout/cleanup
combinations from the same target `text_bbox`:

```text
outputs/runs/phase7-gbc06-18-layout-cleanup-comparison-v1/debug/near-square-result-grid.png
outputs/runs/phase7-gbc06-18-layout-cleanup-comparison-v1/reports/mimo-near-square-comparison.json
```

Grid size: `636x760`.

MIMO ranking:

```json
{
  "best_method": "phrase_fs25_d5",
  "ranking": ["phrase_fs25_d5", "old_fs33_d3", "phrase_fs25_d3"],
  "scores": {
    "phrase_fs25_d5": 9,
    "old_fs33_d3": 8,
    "phrase_fs25_d3": 4
  },
  "unacceptable_methods": ["phrase_fs25_d3"]
}
```

The current best path for `GBC06_18.png#3` is therefore:

```text
ctd-informed/tight text bbox -> bt_lama_large cleanup with d5 text-mask dilation -> phrase-aware vertical layout, fs25, spacing 0, angle 0
```
