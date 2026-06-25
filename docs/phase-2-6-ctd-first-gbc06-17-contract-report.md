# Phase 2-6 CTD-first / GPT Fallback Contract Report

Date: 2026-06-25

## Scope

This report records the contract rewrite for the current text-recognition and non-bubble cleanup route:

1. User-facing `cta_mask` means a CTA-first route in this project, but the actual BallonsTranslator detector is `ctd` / `ComicTextDetector`.
2. Phase 2 runs CTD first, splits `ctd-refined-mask.png` into connected components, and uniquely matches LabelPlus points by point-to-mask-edge distance.
3. Matched CTD masks route to `lama_large_512px` repair and later editable text layers.
4. Unmatched LabelPlus records route to a near-square crop, MIMO bbox location, and `gpt-image-2` transparent masked replacement.
5. Review sheets must be near-square and readable for MIMO and manual inspection.
6. Photoshop export reads project output `photoshop-manifest.json`, not LabelPlus txt directly, and uses layer order: `嵌字图层*` above `修复图像` above `原图`.

## Code Changes

- `autolettering/phase2.py`
  - Adds explicit CTD contract fields: `ballonstranslator_detector_module=ctd`, `ballonstranslator_detector_class=ComicTextDetector`, `mask_matching_metric=labelplus_point_to_mask_edge`.
  - Adds fallback LabelPlus point fields: `labelplus_point_xy` and `context_labelplus_point_xy`.
- `autolettering/phase6_nonbubble.py`
  - Draws a blue LabelPlus cross on fallback locator images.
  - Prompts MIMO to use the blue cross as the anchor and avoid unrelated nearby bubble text.
  - Generates `visuals/fallback-replacement-grid.png` with locator, edit input, mask preview, GPT output, and final replacement.
  - Trims overly wide fallback bboxes to dark-background support when a text bbox crosses from a black card into a white bubble.
  - For light-on-dark GPT outputs, extracts light text alpha and composites it over the original dark background to avoid gray/white patch artifacts.
- `autolettering/models/gpt_image.py`
  - Adds glyph-specific prompt warnings for `暂`, explicitly rejecting `暫`, `仮`, and `哲`.
  - Adds light-on-dark perspective/style guidance.
- `autolettering/export/photoshop.py` and `autolettering/phase8.py`
  - Adds manifest/report source contract for `photoshop-manifest.json` and PSD layer order.

## Real Experiment

Target sample: `GBC06_17.png#3`, translation `新川崎（暂）`.

### Attempt 1: Contract Baseline

Command:

```powershell
python experiments/phase2_6_cta_first_cleanup.py --record-id "GBC06_17.png#3" --sample-limit 1 --run-id phase2-6-ctd-first-gbc06-17-3-gpt-contract-v1 --ctd-max-edge-distance-px 20 --call-gpt-image
```

Artifacts:

- Run: `outputs/runs/phase2-6-ctd-first-gbc06-17-3-gpt-contract-v1`
- Replacement grid: `outputs/runs/phase2-6-ctd-first-gbc06-17-3-gpt-contract-v1/runs/phase6-cta-first-cleanup/visuals/fallback-replacement-grid.png`
- MIMO quality run: `outputs/runs/phase6-replacement-quality-gbc06-17-3-contract-v1`

Result:

- CTD route: fallback required, `no_ctd_mask_within_threshold`.
- GPT call: `ok`.
- MIMO score: `3`, `usable=false`.
- Failure: MIMO/GPT target was too wide and included nearby bubble text; generated wrong glyph/region.

### Attempt 2: LabelPlus Point Anchor

Command:

```powershell
python experiments/phase2_6_cta_first_cleanup.py --record-id "GBC06_17.png#3" --sample-limit 1 --run-id phase2-6-ctd-first-gbc06-17-3-gpt-point-v1 --ctd-max-edge-distance-px 20 --call-gpt-image
```

Artifacts:

- Run: `outputs/runs/phase2-6-ctd-first-gbc06-17-3-gpt-point-v1`
- Replacement grid: `outputs/runs/phase2-6-ctd-first-gbc06-17-3-gpt-point-v1/runs/phase6-cta-first-cleanup/visuals/fallback-replacement-grid.png`
- MIMO quality run: `outputs/runs/phase6-replacement-quality-gbc06-17-3-point-v1`

Result:

- Fallback payload now records `labelplus_point_xy=[1073,272]` and `context_labelplus_point_xy=[220,220]`.
- MIMO locator returns the intended black-card text area.
- MIMO score: `6`, `usable=false`.
- Improvement: region correct, Japanese removed.
- Remaining failure: `暂` rendered as `暫`; style was blurry.

### Attempt 3: Glyph Prompt + Light-on-Dark Composition

Commands:

```powershell
python experiments/phase6_nonbubble_cleanup.py --detection-run-dir "outputs/runs/phase2-6-ctd-first-gbc06-17-3-gpt-point-v1/runs/phase2-cta-mask" --run-id phase6-ctd-first-gbc06-17-3-gpt-point-prompt-v1 --sample-limit 1 --record-id "GBC06_17.png#3" --call-gpt-image
python experiments/phase6_replacement_quality.py --cleanup-run-dir "outputs/runs/phase6-ctd-first-gbc06-17-3-gpt-point-prompt-v1" --run-id phase6-replacement-quality-gbc06-17-3-point-prompt-composed-v1 --sample-limit 1 --record-id "GBC06_17.png#3"
```

Artifacts:

- Cleanup run: `outputs/runs/phase6-ctd-first-gbc06-17-3-gpt-point-prompt-v1`
- Replacement grid: `outputs/runs/phase6-ctd-first-gbc06-17-3-gpt-point-prompt-v1/visuals/fallback-replacement-grid.png`
- MIMO quality sheet: `outputs/runs/phase6-replacement-quality-gbc06-17-3-point-prompt-composed-v1/debug/replacement_quality_sheets/GBC06-17-png-3.png`
- MIMO quality result: `outputs/runs/phase6-replacement-quality-gbc06-17-3-point-prompt-composed-v1/replacement-quality.jsonl`

Result:

- MIMO score: `8`, `usable=true`.
- `exact_text_correct=true`.
- `simplified_chinese_correct=true`.
- `no_japanese_remaining=true`.
- `region_correct=true`.
- `outside_mask_preserved=true`.
- Remaining issue: slight softness / anti-aliasing compared with the original crisp text.

## Current Conclusion

The CTD-first contract is now explicit and the fallback route has a usable real sample for `GBC06_17.png#3` after:

1. anchoring fallback localization with the LabelPlus point,
2. rejecting/repairing overly wide bbox behavior,
3. adding glyph-specific GPT prompt warnings,
4. compositing light-on-dark generated text without GPT's gray background.

This does not prove the route is robust across all non-bubble samples. It does prove the requested pipeline contract can run end-to-end on one previously problematic non-bubble sample with saved comparison images and MIMO evaluation.
