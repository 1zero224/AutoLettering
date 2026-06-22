# Phase 6 AOT and GPT Exact-Prompt Experiment Report

Date: 2026-06-22

## Scope

This report records the follow-up experiment after the initial BallonsTranslator
inpainting comparison:

- Add BallonsTranslator AOT as an explicit non-bubble inpaint candidate.
- Fix AOT color artifacts on grayscale manga crops.
- Compare AOT against the existing local methods with `mimo-v2.5`.
- Strengthen the `gpt-image-2` direct replacement prompt and run controlled real
  calls on two records.

Generated images remain under `outputs/` and are intentionally not committed.

## BallonsTranslator AOT Setup

AOT was previously skipped because the checkpoint was missing. The checkpoint is
now downloaded into the ignored reference-project model directory:

```text
BallonsTranslator/data/models/aot_inpainter.ckpt
sha256=878d541c68648969bc1b042a6e997f3a58e49b6c07c5636ad55130736977149f
```

Code changes:

- `autolettering/inpaint/balloons.py` adds a minimal AOT adapter using
  BallonsTranslator's `load_aot_model`.
- `autolettering/inpaint/nonbubble.py` exposes `bt_aot`.
- `experiments/phase6_nonbubble_cleanup.py` accepts `--inpaint-method bt_aot`.
- `experiments/phase6_inpainting_method_comparison.py` includes `bt_aot` in the
  default method list.
- AOT is not the default; `bt_lama_large` remains the default non-bubble method.

## AOT Optimization

The first #17 AOT run removed text but introduced purple/color artifacts on a
grayscale manga crop. The adapter now detects near-monochrome input crops and
converts the AOT composite result back to grayscale. This preserves AOT's
luminance repair while removing model-generated chroma noise.

The #17 v2 comparison confirms the color issue is gone, but AOT still leaves a
larger reconstructed patch than LaMa on the screentone phone crop.

## AOT Comparison Commands

```powershell
python experiments/phase6_inpainting_method_comparison.py --detection-run-dir outputs/runs/phase2-gbc06-smoke-v3 --run-id phase6-gbc06-01-16-inpainting-aot-comparison-v2 --record-id "GBC06_01.png#16" --method local_diffusion --method bt_patchmatch --method bt_aot --method bt_lama_large --include-gpt-output outputs/runs/phase6-gbc06-nonbubble-gpt-image-smoke/gpt_image2_normalized/GBC06-01-png-16.png
python experiments/phase6_inpainting_method_comparison.py --detection-run-dir outputs/runs/phase2-gbc06-smoke-v3 --run-id phase6-gbc06-01-17-inpainting-aot-comparison-v2 --record-id "GBC06_01.png#17" --method local_diffusion --method bt_patchmatch --method bt_aot --method bt_lama_large --include-gpt-output outputs/runs/phase6-gbc06-batch-17-gpt-image2-polarity-v1/gpt_image2_normalized/GBC06-01-png-17.png
```

Key artifacts:

- #16 sheet: `outputs/runs/phase6-gbc06-01-16-inpainting-aot-comparison-v2/debug/GBC06-01-png-16-inpainting-comparison.png`
- #16 MIMO: `outputs/runs/phase6-gbc06-01-16-inpainting-aot-comparison-v2/reports/mimo-inpainting-method-evaluation.json`
- #17 sheet: `outputs/runs/phase6-gbc06-01-17-inpainting-aot-comparison-v2/debug/GBC06-01-png-17-inpainting-comparison.png`
- #17 MIMO: `outputs/runs/phase6-gbc06-01-17-inpainting-aot-comparison-v2/reports/mimo-inpainting-method-evaluation.json`

## AOT MIMO Results

`mimo-v2.5` ranked the #16 local cleanup result as:

```json
{
  "best_cleanup_method": "local_diffusion",
  "ranking": [
    "local_diffusion",
    "bt_lama_large",
    "bt_aot",
    "bt_patchmatch",
    "gpt_image2_direct_replacement"
  ],
  "unacceptable_methods": ["gpt_image2_direct_replacement"]
}
```

Visual interpretation for #16:

- `local_diffusion` is the cleanest white/smooth-background cleanup.
- `bt_lama_large` and `bt_aot` are usable but leave faint vertical texture.
- `gpt-image-2` from the older prompt was still rejected because it did not
  reliably render the exact text.

`mimo-v2.5` ranked the harder #17 screentone crop as:

```json
{
  "best_cleanup_method": "bt_lama_large",
  "ranking": [
    "bt_lama_large",
    "bt_aot",
    "local_diffusion",
    "bt_patchmatch",
    "gpt_image2_direct_replacement"
  ],
  "unacceptable_methods": ["gpt_image2_direct_replacement"]
}
```

Visual interpretation for #17:

- `bt_lama_large` remains best because it preserves the screentone and diagonal
  structure better than the alternatives.
- `bt_aot` is usable as an experimental fallback, especially after grayscale
  post-processing, but it still creates a visible reconstructed patch.
- `local_diffusion` destroys the screentone texture.
- `gpt-image-2` direct replacement is not acceptable on this art-heavy crop.

Decision:

- Keep `bt_lama_large` as default.
- Keep `bt_patchmatch` as a fast/native fallback.
- Add `bt_aot` as an explicit experimental fallback, not a default.

## GPT Exact-Prompt Optimization

The prompt now explicitly requires the generated text to match the target string:

```text
The text must exactly match the target string below.
Do not omit, add, reorder, paraphrase, translate, or keep any Japanese characters.
Target Chinese text: <translation>
```

Controlled real calls:

```powershell
python experiments/phase6_inpainting_method_comparison.py --detection-run-dir outputs/runs/phase2-gbc06-smoke-v3 --run-id phase6-gbc06-01-16-gpt-image-exact-prompt-v1 --record-id "GBC06_01.png#16" --method bt_lama_large --call-gpt-image
python experiments/phase6_inpainting_method_comparison.py --detection-run-dir outputs/runs/phase2-gbc06-smoke-v3 --run-id phase6-gbc06-01-17-gpt-image-exact-prompt-v1 --record-id "GBC06_01.png#17" --method bt_lama_large --call-gpt-image
```

Key artifacts:

- #16 sheet: `outputs/runs/phase6-gbc06-01-16-gpt-image-exact-prompt-v1/debug/GBC06-01-png-16-inpainting-comparison.png`
- #16 MIMO: `outputs/runs/phase6-gbc06-01-16-gpt-image-exact-prompt-v1/reports/mimo-inpainting-method-evaluation.json`
- #17 sheet: `outputs/runs/phase6-gbc06-01-17-gpt-image-exact-prompt-v1/debug/GBC06-01-png-17-inpainting-comparison.png`
- #17 MIMO: `outputs/runs/phase6-gbc06-01-17-gpt-image-exact-prompt-v1/reports/mimo-inpainting-method-evaluation.json`

Results:

- #16 improved materially. `gpt-image-2` generated the complete string
  `来自桃香的唐突的提案`, while older runs often omitted or garbled characters.
  MIMO still preferred `bt_lama_large` for local cleanup because the generated
  text is pixelated and stylistically weaker than programmatic lettering.
- #17 is still not usable as a direct replacement. The text is readable, but the
  generated result behaves like a white pasted text patch and obscures local
  screentone/line art. MIMO marked `gpt_image2_direct_replacement` unacceptable.

MIMO caveat:

- In the #17 exact-prompt run, MIMO's reasoning misquoted the target text even
  though the JSONL row records `translated_text=已成功预约`. Treat the visual
  sheet and saved request/response metadata as the source of truth when MIMO OCR
  commentary conflicts with the input manifest.

Decision:

- Keep `gpt-image-2` direct replacement as an experimental user-selectable path.
- Do not promote it to default. Programmatic inpainting plus deterministic text
  rendering remains more controllable for exact manga lettering.

## Verification

Targeted tests:

```powershell
python -m pytest tests/test_phase6_nonbubble_cleanup.py -q
```

Observed result:

```text
22 passed
```
