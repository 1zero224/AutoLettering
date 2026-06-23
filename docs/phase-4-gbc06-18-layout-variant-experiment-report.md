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

## Implementation Notes

This is intentionally an experiment script, not a global default change. The
current Phase 4 search still optimizes for the largest fitting font and
character-balanced line breaks. Promoting this behavior into the pipeline should
come after adding phrase-aware line-break scoring and a visual-mass/bottom-margin
penalty to the layout objective.

Next implementation direction:

1. Add phrase-aware vertical line-break candidates so common phrases are not
   split across columns.
2. Score layout candidates by natural phrase boundaries, overflow, edge margin,
   and visual density, not only maximum font size.
3. Search `line_spacing` separately for vertical column spacing and per-character
   spacing instead of binding both to one value.
