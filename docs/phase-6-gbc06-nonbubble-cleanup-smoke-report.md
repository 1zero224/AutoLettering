# Phase 6 GBC06 Non-Bubble Cleanup Smoke Report

## BallonsTranslator Inpaint Survey

Files inspected:

- `BallonsTranslator/ballontranslator/modules/inpaint/base.py`
- `BallonsTranslator/ballontranslator/modules/inpaint/inpaint_default.py`
- `BallonsTranslator/ballontranslator/modules/inpaint/patch_match.py`
- `BallonsTranslator/ballontranslator/modules/inpaint/aot.py`
- `BallonsTranslator/ballontranslator/modules/inpaint/lama.py`
- `BallonsTranslator/ballontranslator/utils/textblock_mask.py`
- `BallonsTranslator/README.md`

Relevant BallonsTranslator design points:

- It separates mask generation from inpainting. The large crop gives context, while a mask/textblock limits what actually changes.
- `InpainterBase` can inpaint per text block and has a fast path for flat balloon regions by sampling the surrounding background.
- The default config uses `lama_large_512px`, a manga-tuned LaMa variant.

Method options and tradeoffs:

- `opencv-tela` / OpenCV inpaint: no model weights, fast, easy dependency; on this sample it left obvious ghosting/smearing and MIMO marked OpenCV variants unacceptable.
- `patchmatch`: non-deep-learning algorithm similar to Photoshop healing/content-aware repair; needs native `data/libs` DLLs. After installing the BallonsTranslator Windows DLLs, it produced a very clean white background on this flat crop. Risk: native binary dependency and likely weaker on complex textured art.
- `aot`: manga-image-translator model; needs PyTorch and `aot_inpainter.ckpt`. Not selected first because LaMa is BallonsTranslator's current default and had a manga-specific large checkpoint.
- `lama_mpe` / `lama_large_512px`: PyTorch checkpoint models; heavier than OpenCV/PatchMatch but most promising for non-flat manga backgrounds. `lama_large_512px` was selected for the main minimal integration experiment.
- `flux2-klein`: much heavier diffusers/transformer/GGUF stack; not suitable for the first minimal local integration.

## Commands

Existing local diffusion baseline:

```powershell
python experiments/phase6_nonbubble_cleanup.py --detection-run-dir outputs/runs/phase2-gbc06-smoke --run-id phase6-gbc06-nonbubble-diffusion-compare --sample-limit 1 --inpaint-method local_diffusion
```

OpenCV variants:

```powershell
python experiments/phase6_nonbubble_cleanup.py --detection-run-dir outputs/runs/phase2-gbc06-smoke --run-id phase6-gbc06-nonbubble-telea-compare --sample-limit 1 --inpaint-method opencv_telea
python experiments/phase6_nonbubble_cleanup.py --detection-run-dir outputs/runs/phase2-gbc06-smoke --run-id phase6-gbc06-nonbubble-ns-compare --sample-limit 1 --inpaint-method opencv_ns
```

BallonsTranslator-backed variants:

```powershell
python experiments/phase6_nonbubble_cleanup.py --detection-run-dir outputs/runs/phase2-gbc06-smoke --run-id phase6-gbc06-nonbubble-lama-large-compare --sample-limit 1 --inpaint-method bt_lama_large
python experiments/phase6_nonbubble_cleanup.py --detection-run-dir outputs/runs/phase2-gbc06-smoke --run-id phase6-gbc06-nonbubble-patchmatch-compare --sample-limit 1 --inpaint-method bt_patchmatch
```

Controlled real `gpt-image-2` masked edit call from the earlier smoke:

```powershell
python experiments/phase6_nonbubble_cleanup.py --detection-run-dir outputs/runs/phase2-gbc06-smoke --run-id phase6-gbc06-nonbubble-gpt-image-smoke --sample-limit 1 --call-gpt-image
```

## Output

Comparison images:

- `outputs/runs/phase6-gbc06-inpaint-comparison/GBC06-01-png-16-inpaint-comparison.png`
- `outputs/runs/phase6-gbc06-inpaint-comparison/GBC06-01-png-16-cleanup-only-x4.png`
- `outputs/runs/phase6-gbc06-inpaint-comparison/GBC06-01-png-16-gpt-image2-x4.png`

MIMO evaluation files:

- `outputs/runs/phase6-gbc06-inpaint-comparison/reports/mimo-cleanup-only-x4-evaluation-0-10.json`
- `outputs/runs/phase6-gbc06-inpaint-comparison/reports/mimo-gpt-image2-x4-evaluation.json`
- Earlier mixed comparison kept for traceability: `outputs/runs/phase6-gbc06-inpaint-comparison/reports/mimo-inpaint-evaluation.json`

## Result Summary

- Detection source: `outputs/runs/phase2-gbc06-smoke/detections.jsonl`
- Record: `GBC06_01.png#16`
- Group: `框外`
- Translated text: `来自桃香的唐突的提案`
- Detection bbox: `[1349, 121, 1407, 378]`
- Crop size: `58 x 257`
- Text mask pixels: `7779`
- GPT edit mask convention: source text alpha `0`, preserved region alpha `255`

Standard run outputs:

- LaMa large: `outputs/runs/phase6-gbc06-nonbubble-lama-large-compare/crops/before_after/GBC06-01-png-16.png`
- PatchMatch: `outputs/runs/phase6-gbc06-nonbubble-patchmatch-compare/crops/before_after/GBC06-01-png-16.png`
- OpenCV Telea: `outputs/runs/phase6-gbc06-nonbubble-telea-compare/crops/before_after/GBC06-01-png-16.png`
- OpenCV NS: `outputs/runs/phase6-gbc06-nonbubble-ns-compare/crops/before_after/GBC06-01-png-16.png`
- Local diffusion: `outputs/runs/phase6-gbc06-nonbubble-diffusion-compare/crops/before_after/GBC06-01-png-16.png`
- GPT image normalized crop: `outputs/runs/phase6-gbc06-nonbubble-gpt-image-smoke/gpt_image2_normalized/GBC06-01-png-16.png`

Mask-area metrics from the comparison crop:

```text
original         dark_lt80=3723 mean=125.28 std=116.94 edge=59.67
local_diffusion  dark_lt80=0    mean=252.66 std=1.62   edge=0.74
opencv_telea     dark_lt80=0    mean=252.88 std=1.78   edge=1.15
opencv_ns        dark_lt80=0    mean=251.54 std=2.55   edge=1.15
bt_patchmatch    dark_lt80=0    mean=254.99 std=0.09   edge=0.02
bt_lama_large    dark_lt80=0    mean=250.63 std=2.79   edge=2.42
gpt_image2       dark_lt80=2027 mean=176.82 std=104.66 edge=41.04
```

Interpretation of metrics:

- Cleanup-only methods all removed dark original glyph pixels.
- `bt_patchmatch` is numerically closest to a flat white fill on this crop.
- `bt_lama_large` is slightly noisier on the flat-white crop but is expected to generalize better to non-flat backgrounds.
- `gpt_image2` is excluded from cleanup-only metrics because it is a direct replacement result with generated Chinese text.

## MIMO Evaluation

MIMO vision model: `mimo-v2.5`

Cleanup-only 4x evaluation:

```json
{
  "best_cleanup_method": "bt_lama_large",
  "ranking": [
    "bt_lama_large",
    "bt_patchmatch",
    "local_diffusion",
    "opencv_telea",
    "opencv_ns"
  ],
  "scores": {
    "local_diffusion": 8,
    "opencv_telea": 4,
    "opencv_ns": 3,
    "bt_patchmatch": 9,
    "bt_lama_large": 10
  },
  "unacceptable_methods": [
    "opencv_telea",
    "opencv_ns"
  ]
}
```

MIMO summary: `bt_lama_large` and `bt_patchmatch` successfully remove the Japanese text and leave a clean background. `local_diffusion` removes text but leaves gray smearing and ghost artifacts. OpenCV variants leave visible ghost glyphs/smearing and are not acceptable on this sample.

GPT image direct replacement evaluation:

```json
{
  "method": "gpt_image2_direct_replacement",
  "score": 0,
  "usable": false
}
```

MIMO summary: the black diamond was preserved, but the direct replacement hallucinated/overgenerated Chinese text, used an unmatched font style, changed the composition, and is not usable as a direct replacement for this crop.

## Current Recommendation

Use `bt_lama_large` as the preferred non-bubble cleanup method for the next integrated preview experiment.

Rationale:

- It is BallonsTranslator's current default model family.
- It ran successfully in a minimal CPU experiment after installing PyTorch and downloading `lama_large_512px.ckpt`.
- MIMO ranked it first on the zoomed cleanup-only comparison.
- It should have better upside than PatchMatch on real textured manga backgrounds.

Keep `bt_patchmatch` as the first fallback:

- It was very clean on this flat-white crop.
- It is fast and does not require PyTorch once DLLs are present.
- It may be less robust on complex backgrounds, so it should not replace LaMa as the primary non-bubble choice yet.

Do not use `gpt-image-2` direct replacement by default:

- The real smoke call produced an unusable direct replacement on this sample.
- It remains useful as an experiment path, but output must be MIMO-checked and should not bypass the programmatic layout/rendering pipeline.

## Implementation Notes

Added non-bubble method choices:

- `local_diffusion`
- `opencv_telea`
- `opencv_ns`
- `bt_lama_large`
- `bt_patchmatch`

BallonsTranslator-specific adapter:

- `autolettering/inpaint/balloons.py`
- `BALLONSTRANSLATOR_ROOT` may override the reference project path.
- `BT_LAMA_LARGE_CKPT` may override the LaMa checkpoint path.
- Large models and native DLLs are loaded lazily only when the selected method needs them.

Local experiment dependencies installed during this run:

- `opencv-python-headless`
- `torch` CPU wheel
- `py7zr`
- `shapely`, `ordered-set`, `natsort`, `opencc-python-reimplemented`
- BallonsTranslator PatchMatch Windows DLLs under ignored `BallonsTranslator/data/libs`
- BallonsTranslator LaMa checkpoint under ignored `BallonsTranslator/data/models/lama_large_512px.ckpt`

The repo still treats these as experiment/runtime dependencies rather than committed artifacts.

## Limitations

- Current sample is a mostly white non-bubble caption area. More complex backgrounds must be evaluated before declaring general quality.
- `bt_lama_large` currently runs on CPU through the minimal adapter; GPU selection is not yet exposed.
- `bt_patchmatch` requires native DLLs and is Windows-specific in the current local setup.
- The current text mask is still a dark-pixel threshold plus dilation. Better masks will matter more than the inpaint model on textured backgrounds.
- The `gpt-image-2` path still normalizes a model-sized output back into the small crop; direct replacement remains unstable.

## Verification

Fresh targeted verification:

```powershell
python -m pytest tests/test_phase6_nonbubble_cleanup.py -q
python -m pytest tests/test_phase6_nonbubble_cleanup.py tests/test_phase6_cleanup.py -q
```

Observed results:

```text
9 passed in 1.16s
14 passed in 1.29s
```

## Notes

- Generated `outputs/` are ignored by Git; this report records reproducible commands and artifact paths.
- No API credential or raw `.env` value is stored in JSONL rows or this report.
