# Phase 7/8 GBC06_02 #1-#3 Report

## Purpose

This run extends the closed auto-lettering loop from `GBC06_01.png` to the first three `GBC06_02.png` bubble records:

- `GBC06_02.png#1`
- `GBC06_02.png#2`
- `GBC06_02.png#3`

The initial integrated preview was unusable because overlapping cleanup crops restored previously removed Japanese text. This report records the diagnosis, the successful fix, and the failed optimization attempt that was not kept.

## BallonsTranslator Inpainting Notes

Files inspected:

- `BallonsTranslator/ballontranslator/modules/inpaint/base.py`
- `BallonsTranslator/ballontranslator/modules/inpaint/inpaint_default.py`
- `BallonsTranslator/ballontranslator/modules/inpaint/aot.py`
- `autolettering/inpaint/balloons.py`
- `autolettering/inpaint/nonbubble.py`

Available methods and tradeoffs:

| Method | Strength | Weakness | Current role |
| --- | --- | --- | --- |
| Flat region fill | Fast, deterministic, best for white speech bubbles | Requires correct text bbox and can damage non-text art if bbox is wrong | Bubble default |
| OpenCV Telea/NS | No model weights, fast fallback | Prior GBC06 non-bubble result left visible artifacts | Fallback only |
| PatchMatch | Fast native repair, clean on simple textures | Windows DLL dependency, uncertain on complex screentone | Fallback |
| AOT | Manga-image-translator style inpainting | Local weight not present; extra setup | Not selected |
| LaMa large 512px | Best prior non-bubble MIMO result; manga-oriented | Heavier PyTorch path | Non-bubble default |
| Flux2-klein | Potentially strong generative inpaint | Heavy diffusers/transformers/GGUF stack | Not selected |
| `gpt-image-2` masked edit | Can attempt direct text replacement | Prior result broke layout/style; MIMO marked unusable | Experimental only |

The useful BallonsTranslator pattern for this batch is not a heavier model. It is the separation of a large contextual crop from the actual edited mask. The project now follows that pattern more closely by saving a cleanup mask and applying only masked pixels during page composition.

## Commands

Phase 3 font comparison:

```powershell
python experiments/phase3_font_comparison.py --labelplus-file "GBC06 (已翻 斗笠)\翻译_0.txt" --detection-run-dir outputs/runs/phase2-gbc06-smoke-v3 --font-dir "工具箱漫画字体V2.5" --run-id phase3-gbc06-02-batch-1-3-font-comparison --sample-limit 3 --font-limit 12 --record-id "GBC06_02.png#1" --record-id "GBC06_02.png#2" --record-id "GBC06_02.png#3"
```

Phase 3 MIMO font selection:

```powershell
python experiments/phase3_mimo_font_selection.py --input-run-dir outputs/runs/phase3-gbc06-02-batch-1-3-font-comparison --run-id phase3-gbc06-02-batch-1-3-mimo-font-selection --sample-limit 3 --record-id "GBC06_02.png#1" --record-id "GBC06_02.png#2" --record-id "GBC06_02.png#3"
```

Phase 5 orientation/angle:

```powershell
python experiments/phase5_orientation_angle.py --detection-run-dir outputs/runs/phase2-gbc06-smoke-v3 --run-id phase5-gbc06-02-batch-1-3-angle --sample-limit 3 --record-id "GBC06_02.png#1" --record-id "GBC06_02.png#2" --record-id "GBC06_02.png#3"
```

Best Phase 4 layout:

```powershell
python experiments/phase4_layout_search.py --selection-run-dir outputs/runs/phase3-gbc06-02-batch-1-3-mimo-font-selection --angle-run-dir outputs/runs/phase5-gbc06-02-batch-1-3-angle --detection-run-dir outputs/runs/phase2-gbc06-smoke-v3 --run-id phase4-gbc06-02-batch-1-3-layout-v2 --sample-limit 3 --record-id "GBC06_02.png#1" --record-id "GBC06_02.png#2" --record-id "GBC06_02.png#3"
```

Best Phase 6 cleanup:

```powershell
python experiments/phase6_bubble_cleanup.py --detection-run-dir outputs/runs/phase2-gbc06-smoke-v3 --layout-run-dir outputs/runs/phase4-gbc06-02-batch-1-3-layout-v2 --run-id phase6-gbc06-02-batch-1-3-region-fill-v3 --sample-limit 3 --cleanup-method region_fill --record-id "GBC06_02.png#1" --record-id "GBC06_02.png#2" --record-id "GBC06_02.png#3"
```

Best Phase 7/8 integrated run:

```powershell
python experiments/phase7_8_integrated_smoke.py --detection-run-dir outputs/runs/phase2-gbc06-smoke-v3 --cleanup-run-dir outputs/runs/phase6-gbc06-02-batch-1-3-region-fill-v3 --layout-run-dir outputs/runs/phase4-gbc06-02-batch-1-3-layout-v2 --font-selection-run-dir outputs/runs/phase3-gbc06-02-batch-1-3-mimo-font-selection --run-id phase7-8-gbc06-02-batch-1-3-preview-v3 --sample-limit 3
```

## Experiment Progression

### v1: Region Fill Baseline

Integrated run:

```text
outputs/runs/phase7-8-gbc06-02-batch-1-3-preview-v1
```

MIMO result:

```json
{
  "evaluation_score": 2,
  "evaluation_usable": false
}
```

Failure:

- `#1` was good.
- `#2` missed a lower-score left text column.
- `#3` selected a too-large target box and overlapped `#2`.

Root cause: tight text bbox selection was brittle for adjacent vertical columns in the same bubble/panel.

### v2: Text BBox Fix

Integrated run:

```text
outputs/runs/phase7-8-gbc06-02-batch-1-3-preview-v2
```

MIMO result:

```json
{
  "evaluation_score": 3,
  "evaluation_usable": false
}
```

Improvement:

- `#2` target bbox became `[892, 391, 1102, 728]`.
- `#3` target bbox became `[866, 539, 940, 728]`.

Remaining failure:

- `#3` cleanup crop still contained old `#2` Japanese text in the overlapping area.
- Page composition pasted whole cleaned crops, so the later `#3` crop restored old pixels over the earlier `#2` cleanup.

### v3: Masked Cleanup Composition

Integrated run:

```text
outputs/runs/phase7-8-gbc06-02-batch-1-3-preview-v3
```

MIMO result:

```json
{
  "evaluation_score": 7,
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
| `GBC06_02.png#1` | 7 | true | Clean removal and readable text; spacing less natural |
| `GBC06_02.png#2` | 10 | true | Original removed, well-fitted, readable |
| `GBC06_02.png#3` | 10 | true | Original removed, well-placed, readable |

Key artifact:

```text
outputs/runs/phase7-8-gbc06-02-batch-1-3-preview-v3/runs/phase7-preview/debug/evaluation_contact_sheets/GBC06-02-png.png
```

### v4: Failed Layout Optimization

Integrated run:

```text
outputs/runs/phase7-8-gbc06-02-batch-1-3-preview-v4
```

MIMO result:

```json
{
  "evaluation_score": 5,
  "evaluation_usable": true
}
```

Attempt:

- Top-align vertical columns of different lengths.

Why not kept:

- MIMO judged `#2` and `#3` vertically cropped/oversized.
- Score dropped from `7` to `5`.

The code change was reverted; v4 remains only as a negative experiment artifact.

## Code Changes

- `autolettering/text_bbox.py`
  - Expands local vertical text columns when there is enough vertical overlap, while avoiding unrelated top columns and panel borders.
- `autolettering/phase6.py`
  - Supports `--record-id` filtering before `sample_limit`.
  - Emits `cleanup_mask_path` for bubble cleanup outputs.
- `autolettering/inpaint/bubble_fill.py`
  - Saves cleanup masks for full-box, mask-fill, and region-fill modes.
- `autolettering/rendering/compose.py`
  - Applies all cleanup crops before text overlays.
  - Applies cleanup crops through `cleanup_mask_path` when available, preventing overlapping records from restoring old source pixels.
- `autolettering/phase7.py`
  - Passes cleanup masks through to page composition.

## Coverage

New coverage run:

```text
outputs/runs/phase0-8-gbc06-pipeline-coverage-v5
```

Summary:

```text
base_record_count=30
complete_record_count=18
incomplete_record_count=12
```

The complete loop now includes:

```text
GBC06_02.png#1
GBC06_02.png#2
GBC06_02.png#3
```

The next `GBC06_02.png` expansion begins at:

```text
GBC06_02.png#4  first_missing_stage=phase3_font_selection
```

The coverage tool also reports `GBC06_01.png#14` and `GBC06_01.png#15` as missing Phase 4 in this merged command because the current coverage command does not include the older manual-readable run in a form counted for those records. That is a coverage-command/history issue, not a blocker for the new `GBC06_02.png#1-#3` result.

## Verification

Targeted tests after the successful changes:

```powershell
python -m pytest tests/test_text_bbox.py tests/test_phase6_cleanup.py tests/test_phase4_layout.py tests/test_phase7_preview.py tests/test_phase7_8_smoke.py -q
python -m pytest tests/test_phase4_layout.py tests/test_phase7_preview.py tests/test_phase6_cleanup.py tests/test_text_bbox.py -q
```

Observed results:

```text
53 passed in 2.00s
53 passed in 1.97s
```

Final full test result is recorded in the terminal output of this implementation turn.

