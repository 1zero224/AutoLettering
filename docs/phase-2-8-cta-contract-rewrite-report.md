# Phase 2-8 CTA Contract Rewrite Report

## Scope

This slice tightens the project contract requested for CTA-first manga text recognition and downstream repair/export:

- BallonsTranslator's user-facing route is `cta_mask`, implemented with the actual `ctd` / `ComicTextDetector` module.
- Each page writes the CTD refined mask, connected component manifest, and per-LabelPlus-point mask-edge distance rows.
- Matched LabelPlus records use the CTD mask region as the text region, route to `lama_large_512px`, and keep editable text layers.
- Unmatched records keep the MIMO locator plus `gpt-image-2` transparent-mask direct replacement contract.
- Phase 8 reads project outputs, not LabelPlus txt, and exports PSD structure as editable text layers above one repaired image layer above the original image.

## Code Contract

Updated files:

- `autolettering/detection/ctd_masks.py`
  - Adds `ctd_mask_component_rows()` for closed component manifest rows.
  - Adds `labelplus_ctd_mask_distance_rows()` for all LabelPlus point to CTD component edge distances.
- `autolettering/phase2.py`
  - Writes `debug/ctd_masks/<page>/cta-closed-mask-components.json`.
  - Writes `debug/ctd_masks/<page>/ctd-mask-edge-distances.jsonl`.
- `autolettering/cta_first_pipeline.py`
  - Documents component and distance artifacts in the CTA-first manifest contract.
  - Documents explicit PSD layer order: `嵌字图层1`, `嵌字图层2`, ..., `修复图像`, `原图`.
- `autolettering/phase8.py`
  - Preserves repair provenance from cleanup rows into the page-level repaired image sources.
  - Synthesizes full-page repaired images from LaMA cleanup crops and successful `gpt-image-2` replacement crops when no Phase 7 page is supplied.
- `autolettering/export/photoshop.py`
  - Carries repair source provenance in `photoshop-manifest.json`.
- `autolettering/export/photoshop_jsx.py`
  - Adds text layers in reverse creation order so Photoshop's top-to-bottom stack appears as `嵌字图层1`, `嵌字图层2`, ...
- `autolettering/inpaint/nonbubble.py`
  - Dilates externally supplied CTD masks before inpainting.
  - Adds an experimental `texture_blur_fill` cleanup method for tall colored side strips.
- `autolettering/phase6_segmented_gpt_replace.py`
  - Writes standard `cleanup-results.jsonl`.
  - Uses each segment's `paste_bbox` so only the intended local edit region is pasted back.

## Real Experiment: CTA Detection

Command:

```powershell
python experiments/phase2_detect_text_regions.py --labelplus-file "GBC06 (已翻 斗笠)/翻译_0.txt" --output-root outputs/runs --run-id phase2-gbc06-33-1-cta-contract-v1 --sample-limit 1 --record-id "GBC06_33.png#1" --detection-strategy cta_mask --ctd-max-edge-distance-px 80
```

Result:

- Record: `GBC06_33.png#1`
- Status: `ok`
- Route: `cta_mask_lama_large_512px`
- Selected bbox: `[1156, 371, 1298, 1925]`
- Nearest component edge distance: `27.0px`
- Threshold: `80.0px`
- Matched component group: `component-0001+component-0002+component-0003+component-0004+component-0005+component-0006+component-0007+component-0008+component-0009+component-0011+component-0014+component-0015+component-0021+component-0025+component-0031+component-0032`

Key artifacts:

- `outputs/runs/phase2-gbc06-33-1-cta-contract-v1/detections.jsonl`
- `outputs/runs/phase2-gbc06-33-1-cta-contract-v1/debug/detection/GBC06_33-1.png`
- `outputs/runs/phase2-gbc06-33-1-cta-contract-v1/debug/ctd_masks/GBC06_33/ctd-refined-mask.png`
- `outputs/runs/phase2-gbc06-33-1-cta-contract-v1/debug/ctd_masks/GBC06_33/cta-closed-mask-components.json`
- `outputs/runs/phase2-gbc06-33-1-cta-contract-v1/debug/ctd_masks/GBC06_33/ctd-mask-edge-distances.jsonl`

Manual visual note: the detection overlay covers the full vertical red side-column text region, including the lower release-date text. This validates the intended "LabelPlus point to nearby CTD mask component" route on this hard non-bubble sample.

## Real Experiment: LaMA Matched Path

Command:

```powershell
python experiments/phase6_nonbubble_cleanup.py --detection-run-dir outputs/runs/phase2-gbc06-33-1-cta-contract-v1 --output-root outputs/runs --run-id phase6-gbc06-33-1-cta-contract-lama-large-v1 --sample-limit 1 --record-id "GBC06_33.png#1" --skip-mimo --inpaint-method bt_lama_large
```

Result:

- Status: `cleaned`
- Method: `bt_lama_large_inpaint`
- Source mask: matched CTD merged component mask.
- GPT status: `not_applicable`, because this is the matched CTA/LaMA path.
- Text overlay required: `true`, so Phase 8 should still create an editable text layer.

Key artifacts:

- `outputs/runs/phase6-gbc06-33-1-cta-contract-lama-large-v1/cleanup-results.jsonl`
- `outputs/runs/phase6-gbc06-33-1-cta-contract-lama-large-v1/crops/input/GBC06-33-png-1.png`
- `outputs/runs/phase6-gbc06-33-1-cta-contract-lama-large-v1/crops/mask/GBC06-33-png-1.png`
- `outputs/runs/phase6-gbc06-33-1-cta-contract-lama-large-v1/crops/cleaned/GBC06-33-png-1.png`
- `outputs/runs/phase6-gbc06-33-1-cta-contract-lama-large-v1/crops/before_after/GBC06-33-png-1.png`

Manual visual note: LaMA removes part of the white original glyphs, but leaves heavy dark text-shaped ghosting on the red strip. This path satisfies the requested architecture, but the visual result is not final quality for this sample.

## Real Experiment: Tall-Strip Cleanup Optimization

Command:

```powershell
python experiments/phase6_nonbubble_cleanup.py --detection-run-dir outputs/runs/phase2-gbc06-33-1-cta-contract-v1 --output-root outputs/runs --run-id phase6-gbc06-33-1-cta-contract-texture-blur-v1 --sample-limit 1 --record-id "GBC06_33.png#1" --skip-mimo --inpaint-method texture_blur_fill --allow-cta-method-override
```

Result:

- Status: `cleaned`
- Method: `texture_blur_fill`
- This is an experimental override only; the default CTA matched route remains `lama_large_512px`.

Key artifacts:

- `outputs/runs/phase6-gbc06-33-1-cta-contract-texture-blur-v1/cleanup-results.jsonl`
- `outputs/runs/phase6-gbc06-33-1-cta-contract-texture-blur-v1/crops/cleaned/GBC06-33-png-1.png`
- `outputs/runs/phase6-gbc06-33-1-cta-contract-texture-blur-v1/crops/before_after/GBC06-33-png-1.png`

Manual visual note: `texture_blur_fill` removes the white source text more completely than LaMA on this tall red strip, but it creates an over-smooth red column with pale blur spots. It is a useful fallback/optimization candidate, not a final default.

## Phase 8 PSD Contract

The export contract is now explicit:

- Input source: `photoshop-manifest.json`, not the LabelPlus txt.
- PSD top-to-bottom order: `嵌字图层1`, `嵌字图层2`, ..., `修复图像`, `原图`.
- `修复图像` can be a full-page composite built from both:
  - `lama_large_512px` cleanup crops for matched CTA records.
  - `gpt-image-2` replacement crops for fallback records only after the same
    `record_id` passes the optional `replacement-quality.jsonl` gate.
- Records already containing quality-accepted final GPT replacement text are omitted from editable text layers to avoid duplicate Chinese text.

## Real Experiment: Phase 8 Synthesized Repaired Page

Command:

```powershell
python experiments/phase8_photoshop_export.py --detection-run-dir outputs/runs/phase2-gbc06-cta-mask-01-16-default-v2 --font-selection-run-dir outputs/runs/phase3-gbc06-01-16-manual-song-selection-v1 --layout-run-dir outputs/runs/phase4-gbc06-01-16-layout-song-fs40-top-noangle-v10 --cleanup-run-dir outputs/runs/phase6-gbc06-cta-lama-01-16-default-v2 --output-root outputs/runs --run-id phase8-gbc06-cta-lama-01-16-synth-repair-v1 --sample-limit 1
```

This run deliberately omits `--preview-run-dir`, so Phase 8 has to synthesize the full-page `修复图像` from cleanup crops.

Result:

- Run directory: `outputs/runs/phase8-gbc06-cta-lama-01-16-synth-repair-v1`
- Manifest: `photoshop-manifest.json`
- Import script: `photoshop-import.jsx`
- Synthesized repaired page: `repaired_pages/GBC06-01-png.png`
- Repaired page size: `1440x2048`
- Text layer name: `嵌字图层1`
- Source contract layer order: `嵌字图层1 > 嵌字图层2 > ... > 修复图像 > 原图`
- Repair source method: `bt_lama_large_inpaint`
- Repair source route: `cta_mask_lama_large_512px`
- Repair source text region: `ctd_refined_mask_component`
- Repair source mask: `outputs/runs/phase2-gbc06-cta-mask-01-16-default-v2/debug/ctd_masks/GBC06_01/components/component-0001+component-0012+component-0016+component-0018+component-0026.png`

Compatibility note: this experiment uses older Phase 2/6 outputs that predate the newer explicit `route` and `text_region_source` fields. Phase 8 now recovers that provenance from legacy `cta_match` / `ctd_match` rows when the cleanup method is LaMA.

## Current Conclusion

The CTA-first recognition contract is now backed by machine-readable artifacts and a real GBC06 detection run. The matched route correctly uses the CTD mask as the text region and produces the required LaMA cleanup row for downstream editable lettering.

The main remaining quality issue is in image repair, not in the detection contract. On `GBC06_33.png#1`, `lama_large_512px` is architecturally correct but visually weak, while `texture_blur_fill` is cleaner but too smooth. The next useful experiment is a quality-gated fallback that can escalate a CTA-matched but visually poor LaMA repair into a controlled `gpt-image-2` masked replacement, without losing the editable-text PSD path for ordinary matched records.
