# Phase 6/7 GBC06 Cleanup and Inpainting Experiment Report

## Scope

This report records the cleanup experiment for the current poor "white paint"
result. It covers:

- BallonsTranslator inpainting methods and tradeoffs.
- Bubble text cleanup optimization for `GBC06_01.png#2` to `#6`.
- Non-bubble inpainting comparison for `GBC06_01.png#16`.
- Dark-panel non-bubble cleanup for `GBC06_01.png#17`.
- `mimo-v2.5` evaluation results, including the `gpt-image-2` masked-edit result.

Generated images remain under `outputs/` and are intentionally not committed.

## BallonsTranslator Inpainting Survey

Files inspected:

- `BallonsTranslator/ballontranslator/modules/inpaint/base.py`
- `BallonsTranslator/ballontranslator/modules/inpaint/inpaint_default.py`
- `BallonsTranslator/ballontranslator/modules/inpaint/patch_match.py`
- `BallonsTranslator/ballontranslator/modules/inpaint/aot.py`
- `BallonsTranslator/ballontranslator/modules/inpaint/lama.py`

Available methods and practical tradeoffs:

| Method | Local availability | Strengths | Weaknesses | Decision |
| --- | --- | --- | --- | --- |
| OpenCV Telea / NS | Available through OpenCV | No model weights, fast, good enough on simple flat white areas | Weak on textured manga art; may smear or leave ghosts | Keep as light fallback |
| PatchMatch | `BallonsTranslator/data/libs/patchmatch_inpaint.dll` exists | Fast native repair, often good on simple texture continuation | Platform DLL dependency; fallback quality uncertain on complex screentone | Keep as fallback |
| AOT | Weight missing locally | Manga-image-translator style deep inpaint path | Requires missing `aot_inpainter.ckpt`; more setup than LaMa | Not selected for minimal experiment |
| LaMa MPE | Weight missing locally | BallonsTranslator-supported LaMa family | Requires missing `lama_mpe.ckpt` | Not selected |
| LaMa large 512px | `BallonsTranslator/data/models/lama_large_512px.ckpt` exists | Best local deep inpaint candidate; works through current integration | Heavier PyTorch path | Selected for non-bubble primary |
| Flux2 Klein | Not used | Potentially stronger generative inpaint | Heavy diffusers/transformers/GGUF stack; large dependency surface | Not selected for minimal experiment |
| `gpt-image-2` masked edit | API path already integrated experimentally | Can remove/replace the masked area in one generative call | On this sample, generated Chinese lettering is unreadable; not reliable for exact typesetting | Not selected as default |

The most important design point copied from BallonsTranslator is not a specific
model, but the separation between a large context crop and a smaller edit mask.
The current AutoLettering problem was caused by editing too much of the selected
region, not only by a weak fill algorithm.

## Bubble Cleanup Optimization

Problem found on the five-record bubble batch:

- Phase 2 selected boxes can include nearby text/noise or a broad balloon area.
- Filling that whole selected box caused large white blocks.
- Tightening cleanup to real candidate glyph boxes fixed records `#5` and `#6`.
- A too-tight target then made record `#4` fail layout because the translated
  text needed more room than the original glyph column.

Implemented behavior:

- `autolettering/text_bbox.py` centralizes selected text bbox extraction.
- Candidate boxes are filtered to stay inside `selected_text_box_xyxy`.
- Large region-like candidates are ignored by area ratio.
- Candidate scores near the max score are preferred, reducing remote/noisy boxes.
- Phase 6 cleanup uses the tight text bbox, so it no longer paints broad white
  blocks.
- Phase 4 layout first tries the tight bbox, then expands inside the selected
  box only if layout overflows. This keeps cleanup tight while allowing longer
  translated text to fit.

Bubble batch commands:

```powershell
python experiments/phase4_layout_search.py --selection-run-dir outputs/runs/phase3-gbc06-bubble-batch-mimo-font-selection --angle-run-dir outputs/runs/phase5-gbc06-bubble-batch-angle-v3 --detection-run-dir outputs/runs/phase2-gbc06-smoke --run-id phase4-gbc06-bubble-batch-layout-v7 --sample-limit 5 --record-id 'GBC06_01.png#2' --record-id 'GBC06_01.png#3' --record-id 'GBC06_01.png#4' --record-id 'GBC06_01.png#5' --record-id 'GBC06_01.png#6'
python experiments/phase6_bubble_cleanup.py --detection-run-dir outputs/runs/phase2-gbc06-smoke --layout-run-dir outputs/runs/phase4-gbc06-bubble-batch-layout-v7 --run-id phase6-gbc06-bubble-batch-region-fill-v7 --sample-limit 5 --cleanup-method region_fill
python experiments/phase7_8_integrated_smoke.py --detection-run-dir outputs/runs/phase2-gbc06-smoke --cleanup-run-dir outputs/runs/phase6-gbc06-bubble-batch-region-fill-v7 --layout-run-dir outputs/runs/phase4-gbc06-bubble-batch-layout-v7 --font-selection-run-dir outputs/runs/phase3-gbc06-bubble-batch-mimo-font-selection --run-id phase7-8-gbc06-bubble-batch-preview-v6 --sample-limit 5
```

Bubble batch result:

```json
{
  "preview_record_count": 5,
  "skipped_count": 0,
  "evaluation_status": "evaluated",
  "evaluation_score": 9,
  "evaluation_usable": true,
  "missing_cleanup_layers": 0,
  "effective_cleanup_methods": {
    "bubble_region_fill": 5
  }
}
```

MIMO notes:

- Model: `mimo-v2.5`.
- `original_text_removed=true`.
- `art_preserved=true`.
- `lettering_readable=true`.
- Main residual issue: translated text is slightly oversized on several bubbles.

Key artifacts:

- Manifest: `outputs/runs/phase7-8-gbc06-bubble-batch-preview-v6/manifest.json`
- MIMO result: `outputs/runs/phase7-8-gbc06-bubble-batch-preview-v6/runs/phase7-evaluation/preview-evaluation.jsonl`
- Contact sheet: `outputs/runs/phase7-8-gbc06-bubble-batch-preview-v6/runs/phase7-preview/debug/evaluation_contact_sheets/GBC06-01-png.png`

Decision:

- Use `bubble_region_fill` for bubble cleanup.
- Keep cleanup bbox tight.
- Allow Phase 4 layout target expansion inside the selected box only when the
  translated text cannot fit the tight bbox.

## Non-Bubble Inpainting Comparison

Test record:

- `GBC06_01.png#16`
- Translation: `来自桃香的唐突的提案`

The current integration already routes non-bubble cleanup through:

- `bt_lama_large`
- `bt_patchmatch`
- `opencv_telea`
- `opencv_ns`
- `local_diffusion`
- `gpt-image-2` masked edit path

Preview/evaluation commands used for the key comparisons:

```powershell
python experiments/phase7_page_preview.py --detection-run-dir outputs/runs/phase2-gbc06-smoke --cleanup-run-dir outputs/runs/phase6-gbc06-nonbubble-lama-large-compare --layout-run-dir outputs/runs/phase4-gbc06-nonbubble-layout-smoke --run-id phase7-gbc06-nonbubble-lama-large-preview-v2 --sample-limit 1
python experiments/phase7_page_preview.py --detection-run-dir outputs/runs/phase2-gbc06-smoke --cleanup-run-dir outputs/runs/phase6-gbc06-nonbubble-patchmatch-compare --layout-run-dir outputs/runs/phase4-gbc06-nonbubble-layout-smoke --run-id phase7-gbc06-nonbubble-patchmatch-preview-v1 --sample-limit 1
python experiments/phase7_page_preview.py --detection-run-dir outputs/runs/phase2-gbc06-smoke --cleanup-run-dir outputs/runs/phase6-gbc06-nonbubble-telea-compare --layout-run-dir outputs/runs/phase4-gbc06-nonbubble-layout-smoke --run-id phase7-gbc06-nonbubble-telea-preview-v1 --sample-limit 1
python experiments/phase7_page_preview.py --detection-run-dir outputs/runs/phase2-gbc06-smoke --cleanup-run-dir outputs/runs/phase6-gbc06-nonbubble-gpt-image-smoke --layout-run-dir outputs/runs/phase4-gbc06-nonbubble-layout-smoke --run-id phase7-gbc06-nonbubble-gpt-image-preview-v1 --sample-limit 1
python experiments/phase7_preview_evaluate.py --preview-run-dir outputs/runs/phase7-gbc06-nonbubble-lama-large-preview-v2 --run-id phase7-gbc06-nonbubble-lama-large-preview-v2-mimo-eval --sample-limit 1
python experiments/phase7_preview_evaluate.py --preview-run-dir outputs/runs/phase7-gbc06-nonbubble-gpt-image-preview-v1 --run-id phase7-gbc06-nonbubble-gpt-image-preview-v1-mimo-eval --sample-limit 1
```

Single-method MIMO results:

| Method | Cleanup method in preview | Score | Usable | Notes |
| --- | --- | ---: | --- | --- |
| LaMa large 512px | `bt_lama_large_inpaint` | 10 | true | Best result; original removed, art preserved, lettering readable |
| PatchMatch | `bt_patchmatch_inpaint` | 1 | false | MIMO criticized final preview orientation/size/placement; keep only as fallback pending more samples |
| OpenCV Telea | `opencv_telea_inpaint` | 0 | false | MIMO judged final preview unchanged/failed; keep only as light fallback |
| `gpt-image-2` masked edit | `gpt_image2_masked_edit` | 0 | false | Original removed, art preserved, but generated text is garbled and unreadable |

Important evaluation caveat:

- The single-method MIMO score evaluates the final preview, not pure background
  inpainting only.
- PatchMatch/OpenCV may still be acceptable for simple flat backgrounds, but
  they did not beat LaMa in the current end-to-end preview evaluation.
- A combined method-comparison sheet caused a misleading result because the
  evaluator treated the red separator line as image content. The single-method
  preview evaluations are the source of truth for this report.

Key artifacts:

- Comparison sheet: `outputs/runs/phase6-7-gbc06-inpaint-method-comparison/GBC06-01-png-16-inpaint-method-comparison.png`
- LaMa MIMO result: `outputs/runs/phase7-gbc06-nonbubble-lama-large-preview-v2-mimo-eval/preview-evaluation.jsonl`
- LaMa contact sheet: `outputs/runs/phase7-gbc06-nonbubble-lama-large-preview-v2/debug/evaluation_contact_sheets/GBC06-01-png.png`
- PatchMatch contact sheet: `outputs/runs/phase7-gbc06-nonbubble-patchmatch-preview-v1/debug/evaluation_contact_sheets/GBC06-01-png.png`
- Telea contact sheet: `outputs/runs/phase7-gbc06-nonbubble-telea-preview-v1/debug/evaluation_contact_sheets/GBC06-01-png.png`
- `gpt-image-2` MIMO result: `outputs/runs/phase7-gbc06-nonbubble-gpt-image-preview-v1-mimo-eval/preview-evaluation.jsonl`
- `gpt-image-2` contact sheet: `outputs/runs/phase7-gbc06-nonbubble-gpt-image-preview-v1/debug/evaluation_contact_sheets/GBC06-01-png.png`

Decision:

- Use `bt_lama_large` as the primary non-bubble inpainting method.
- Keep `bt_patchmatch`, OpenCV Telea, and OpenCV NS as fallback/fast paths.
- Do not use `gpt-image-2` masked edit as the default for exact readable
  translated lettering. It may still be useful as a background cleanup or
  exploratory generative path, but not as an end-to-end lettering replacement
  for this sample.

## Dark-Panel Text Cleanup

Test record:

- `GBC06_01.png#17`
- Group: `框外`
- Translation: `已成功预约`

Root cause of the bad cleanup:

- The old non-bubble text mask assumed dark glyphs on a light background.
- This record is the opposite: white UI text on a dark phone screen.
- The previous bbox selection bridged the selected text to a separate bright
  region above the target, so cleanup touched too much art.
- Phase 4 rendered black translated text by default, making the result
  unreadable on the dark phone screen even when inpainting was acceptable.

Implemented behavior:

- Phase 2 now records candidate polarity and can detect `light_on_dark` text.
- `selected_text_bbox()` filters candidate clusters by polarity and avoids
  bridging the #17 white UI text to unrelated upper bright art.
- Phase 6 passes the selected polarity into non-bubble mask generation, so
  `light_on_dark` masks target bright glyph pixels constrained by a dark local
  background.
- Phase 4 renders `light_on_dark` records in white and stores
  `layout.text_color`.
- Phase 8 exports `layout.text_color`; the generated JSX converts it to a
  Photoshop `SolidColor` before creating the editable text layer.

Key cleanup bbox after the fix:

```text
record_id=GBC06_01.png#17
cleanup_bbox=[286, 277, 393, 361]
polarity=light_on_dark
mask_pixels=3594
crop_size=107x84
```

Dark-panel experiment artifacts:

- Cleanup comparison sheet: `outputs/runs/phase6-gbc06-batch-17-inpaint-polarity-comparison/GBC06-01-png-17-cleanup-comparison-v4-dark-fill.png`
- Corrected LaMa cleanup: `outputs/runs/phase6-gbc06-batch-17-nonbubble-lama-large-polarity-v3/crops/before_after/GBC06-01-png-17.png`
- Corrected layout: `outputs/runs/phase4-gbc06-batch-17-layout-polarity-white-v1/layout-results.jsonl`
- Corrected preview/evaluation: `outputs/runs/phase7-8-gbc06-batch-17-lama-white-preview-v1`
- Photoshop export with white text color: `outputs/runs/phase8-gbc06-batch-17-lama-white-text-export-v1/photoshop-manifest.json`

`mimo-v2.5` results for #17:

| Method | Final preview cleanup method | Score | Usable | Main issue |
| --- | --- | ---: | --- | --- |
| LaMa large + polarity mask + white text | `bt_lama_large_inpaint` | 8 | true | Translated lettering is slightly oversized |
| Median dark-panel fill + white text | `dark_panel_fill` | 6 | true | Original removed, but the solid dark fill patch is visible |
| `gpt-image-2` masked edit + white text | `gpt_image2_masked_edit` | 4 | false | Generated lettering is oversized and covers surrounding artwork |

`gpt-image-2` call status:

```json
{
  "status": "ok",
  "model": "gpt-image-2",
  "input_tokens": 56,
  "output_tokens": 1584,
  "total_tokens": 1640,
  "normalized_size": [107, 84]
}
```

Decision:

- Keep `bt_lama_large` as the default non-bubble cleanup method.
- Keep `dark_panel_fill` as a narrow fallback for dark UI/panel backgrounds
  when deep inpainting leaves visible residue.
- Do not use `gpt-image-2` as the default exact-lettering path. On #17 it
  removed the source text, but it also generated its own oversized text inside
  the replacement crop, which made the final programmatic overlay cluttered.

## Verification

Regression tests already exercised this change set:

```powershell
python -m pytest tests/test_record_selection.py tests/test_phase3_fonts.py tests/test_mimo_font_selection.py tests/test_phase4_layout.py tests/test_phase5_orientation.py tests/test_phase6_cleanup.py tests/test_phase7_8_smoke.py tests/test_text_bbox.py tests/test_phase6_nonbubble_cleanup.py -q
```

Observed result:

```text
64 passed
```

Phase 4 expansion regression was verified red/green:

```powershell
python -m pytest tests/test_phase4_layout.py::test_run_phase4_expands_tight_target_inside_selected_box_when_layout_overflows -q
```

After implementation:

```text
1 passed
```

Latest focused layout/cleanup/preview suite:

```powershell
python -m pytest tests/test_phase4_layout.py tests/test_phase5_orientation.py tests/test_phase6_cleanup.py tests/test_phase7_8_smoke.py tests/test_text_bbox.py -q
```

Observed result:

```text
37 passed
```

Fresh final verification should still be run before committing.
