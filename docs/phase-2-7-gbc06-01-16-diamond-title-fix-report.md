# GBC06_01.png#16 Diamond Title Fix

## Scope

- Record: `GBC06_01.png#16`
- Source text: `桃香からの突然の提案`
- Translation: `来自桃香的唐突的提案`
- Out of scope for this pass: `GBC06_01.png#17` / `已成功预约`

## Root Cause

The previous result had three separate issues:

1. Phase 2 searched too small a vertical region for edge non-bubble captions.
   The detected crop only covered the upper text (`桃香から`) instead of the full title.
2. The top black diamond decoration was merged into the text bbox.
   Cleanup and lettering then treated the decoration as text space.
3. Phase 4 applied a small CV angle estimate (`2.4°`) as real rotation.
   For this upright vertical title, that micro-angle was glyph-shape noise.

## Code Changes

- Expanded edge non-bubble vertical search in `autolettering/detection/cv_text.py`.
- Kept `selected_text_bbox()` as the full text evidence bbox:
  - `GBC06_01.png#16`: `(1349, 121, 1407, 684)`
- Added `selected_text_body_bbox()` for lettering/cleanup/font reference:
  - `GBC06_01.png#16`: `(1349, 177, 1407, 684)`
- Switched Phase 3 font source crop, Phase 4 layout, Phase 5 angle crop, and Phase 6 non-bubble cleanup to use the body bbox where appropriate.
- Added top alignment for decorated vertical title bodies so the first translated character stays visually related to the diamond.
- Ignored high-confidence micro-rotation angles below `3.0°` in Phase 4.
- Added a decorated-title font-size cap based on body height and character count, so removing rotation does not let the text overfill the column.

## Experiments

### Detection

- `outputs/runs/phase2-gbc06-smoke-v5/`
- Corrected source crop:
  - `outputs/runs/phase3-gbc06-01-16-font-comparison-v6/crops/source_text/GBC06-01-png-16.png`
  - crop size: `58x507`
  - excludes the top diamond and includes the full Japanese text body.

### Font Selection

MIMO on the corrected source crop selected:

- `[toolbox]拙黑体-简体(v2.4).ttf`
- Run: `outputs/runs/phase3-gbc06-01-16-mimo-font-selection-v6/`

Manual review rejected it as too heavy. The worker subagent produced an independent visual comparison and also recommended `song`:

- `outputs/runs/phase7-gbc06-01-16-diamond-font-eval-v1/gbc06-01-16-diamond-top-comparison.png`
- `outputs/runs/phase7-gbc06-01-16-diamond-font-eval-v1/gbc06-01-16-song-vs-wei-jiao-min.png`

Chosen controlled font branch:

- `[toolbox]宋体-简繁-DemiBold(v2.5).ttf`
- Run: `outputs/runs/phase3-gbc06-01-16-manual-song-selection-v1/`

### Layout And Cleanup

The final preferred branch is:

- Font: `[toolbox]宋体-简繁-DemiBold(v2.5).ttf`
- Text bbox: `[1349, 177, 1407, 684]`
- Vertical align: `top`
- Rotation: `0.0°`
- Font size: `42`
- Cleanup: `bt_lama_large`

Key outputs:

- Layout: `outputs/runs/phase4-gbc06-01-16-layout-song-body-top-noangle-v9/`
- LaMa cleanup: `outputs/runs/phase6-gbc06-01-16-lama-body-v6/`
- LaMa final preview: `outputs/runs/phase7-gbc06-01-16-lama-body-song-top-noangle-v9/`
- Telea comparison preview: `outputs/runs/phase7-gbc06-01-16-telea-body-song-top-noangle-v9/`
- Main manual comparison image:
  - `outputs/runs/phase7-gbc06-01-16-final-method-comparison-v9/debug/diamond-context-comparison.png`

## MIMO Evaluation

Final no-rotation candidates:

- `lama_noangle_v9`
  - Run: `outputs/runs/phase7-gbc06-01-16-lama-body-song-top-noangle-v9-mimo-eval/`
  - Score: `10`
  - Usable: `true`
  - Issues: none
- `telea_noangle_v9`
  - Run: `outputs/runs/phase7-gbc06-01-16-telea-body-song-top-noangle-v9-mimo-eval/`
  - Score: `9`
  - Usable: `true`
  - Issue: minor spacing note from MIMO

Older comparison points:

- `old_full_bbox`: diamond/text body were not separated and the top decoration was not preserved correctly.
- `rotated_top_v7`: better bbox and font, but still used the false `2.4°` rotation.
- `noangle_big_v8`: removed rotation but overfilled the column because the font-size search expanded to `50`.
- `noangle_v9`: removes rotation and caps decorated-title font size to avoid overfilling.

## Current Decision

Use `lama_noangle_v9` as the current best result for `GBC06_01.png#16`.

This fixes the user's two corrections:

- The source text body now covers the full `桃香からの突然の提案`, not only `桃香から`.
- The final Chinese lettering is upright vertical text with no micro-rotation applied.

Residual manual-review point:

- The translation wording itself remains `来自桃香的唐突的提案` from LabelPlus. This pass only fixed detection, cleanup, and lettering placement.
