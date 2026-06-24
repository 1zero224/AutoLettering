# Phase 2/6 CTA-First Detection Rewrite Experiment: GBC06_33.png#1

## Scope

This experiment validates the rewritten recognition route requested for non-bubble manga lettering:

1. Run BallonsTranslator CTA/CTD on the full page.
2. Split the refined mask into connected components.
3. Match LabelPlus points by distance to mask edges with unique component ownership.
4. For matched records, use the merged mask region as the text region and route to `lama_large_512px` cleanup.
5. Preserve a fallback contract for unmatched records: near-square MIMO locator crop, then `gpt-image-2` masked Chinese replacement.

## Code Changes Under Test

- `autolettering/detection/ctd_masks.py`
  - Added tall-promo-column continuation logic so a side promotional column can merge upper title, date, and release text components while excluding wide unrelated logo/banner masks.
- `autolettering/phase2.py`
  - Adds `lettering_route` to detection rows.
  - Matched CTA rows route to `cta_mask_lama_large_512px`.
  - Unmatched rows route to `mimo_locator_gpt_image2_masked_edit` and expose a near-square `fallback.context_bbox_xyxy` for readable vision-model crops.
- `autolettering/phase6_nonbubble.py`
  - CTA/CTD matched cleanup rows now preserve `route`, `source_mask_path`, and `text_overlay_required`.
- `autolettering/phase8.py` and `autolettering/export/photoshop.py`
  - Phase8 can synthesize a page-level repaired image from cleanup crops when Phase7 preview is not supplied.
  - GPT final replacement cleanup records are omitted from editable text layers to avoid duplicate Chinese text.

## Real Sample

- Record: `GBC06_33.png#1`
- Translation: `漫画第一卷\n2026年6月29日发售！！`
- Group: `框外`

## Commands

```powershell
python experiments/phase2_detect_text_regions.py --labelplus-file "GBC06 (已翻 斗笠)\翻译_0.txt" --output-root outputs/runs --run-id phase2-gbc06-33-1-cta-mask-edge80-v3 --sample-limit 1 --record-id "GBC06_33.png#1" --ctd-max-edge-distance-px 80

python experiments/phase6_nonbubble_cleanup.py --detection-run-dir outputs/runs/phase2-gbc06-33-1-cta-mask-edge80-v3 --output-root outputs/runs --run-id phase6-gbc06-33-1-cta-lama-large-v1 --sample-limit 1 --record-id "GBC06_33.png#1" --skip-mimo --inpaint-method bt_lama_large

python experiments/phase6_nonbubble_cleanup.py --detection-run-dir outputs/runs/phase2-gbc06-33-1-cta-mask-edge80-v3 --output-root outputs/runs --run-id phase6-gbc06-33-1-cta-patchmatch-v1 --sample-limit 1 --record-id "GBC06_33.png#1" --skip-mimo --inpaint-method bt_patchmatch --allow-cta-method-override

python experiments/phase6_nonbubble_cleanup.py --detection-run-dir outputs/runs/phase2-gbc06-33-1-cta-mask-edge80-v3 --output-root outputs/runs --run-id phase6-gbc06-33-1-cta-opencv-telea-v1 --sample-limit 1 --record-id "GBC06_33.png#1" --skip-mimo --inpaint-method opencv_telea --allow-cta-method-override

python experiments/phase6_nonbubble_cleanup.py --detection-run-dir outputs/runs/phase2-gbc06-33-1-cta-mask-edge80-v3 --output-root outputs/runs --run-id phase6-gbc06-33-1-cta-aot-v1 --sample-limit 1 --record-id "GBC06_33.png#1" --skip-mimo --inpaint-method bt_aot --allow-cta-method-override
```

## Detection Result

- Status: `ok`
- BBox: `[1156, 371, 1298, 1925]`
- Edge distance: `27.0px`
- Route: `cta_mask_lama_large_512px`
- Merged components:
  - `component-0001` through `component-0009`
  - `component-0011`
  - `component-0014`
  - `component-0015`
  - `component-0021`
  - `component-0025`
  - `component-0031`
  - `component-0032`

The selected bbox now covers the full vertical side column, including the lower `2026年6月29日発売!!` section. The previous partial match stopped around the upper title/date boundary.

## Artifacts

- Detection JSONL: `outputs/runs/phase2-gbc06-33-1-cta-mask-edge80-v3/detections.jsonl`
- Detection overlay: `outputs/runs/phase2-gbc06-33-1-cta-mask-edge80-v3/debug/detection/GBC06_33-1.png`
- Merged CTA mask: `outputs/runs/phase2-gbc06-33-1-cta-mask-edge80-v3/debug/ctd_masks/GBC06_33/components/component-0001+component-0002+component-0003+component-0004+component-0005+component-0006+component-0007+component-0008+component-0009+component-0011+component-0014+component-0015+component-0021+component-0025+component-0031+component-0032.png`
- LaMa before/after crop: `outputs/runs/phase6-gbc06-33-1-cta-lama-large-v1/crops/before_after/GBC06-33-png-1.png`
- Method comparison grid: `outputs/runs/phase6-gbc06-33-1-cta-method-compare-v1/visuals/cta-method-grid.png`
- MIMO method-grid evaluation: `outputs/runs/phase6-gbc06-33-1-cta-method-compare-v1/reports/mimo-cta-method-grid-evaluation.json`

## MIMO Evaluation Summary

MIMO ranked the methods:

1. `lama_large_512px`
2. `patchmatch`
3. `opencv_telea`
4. `aot`

MIMO marked only `lama_large_512px` as usable, but manual inspection still shows visible dark text-shaped residue in the repaired strip. Treat this as a relative ranking, not final visual acceptance.

## Conclusion

The CTA-first recognition route is working for this hard side-column sample. It correctly detects the full source text region and writes a downstream route contract.

The cleanup result is not visually final. `lama_large_512px` is the best among tested local methods, but the red textured background keeps dark remnants. This record needs a stronger follow-up cleanup strategy, likely one of:

- wider/strip-aware mask cleanup,
- full side-strip regeneration,
- or a controlled `gpt-image-2` masked replacement path even for CTA-matched records when local repair quality fails.
