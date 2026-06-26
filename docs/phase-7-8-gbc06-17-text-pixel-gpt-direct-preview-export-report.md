# Phase 7/8 GBC06_17 Text-Pixel GPT Direct Preview And Export Report

Date: 2026-06-27

## Scope

This report records the end-to-end adapter check for the real outside-bubble sample that was already replaced by `gpt-image-2` with a text-pixel mask.

Target sample:

- Record: `GBC06_17.png#3`
- Translation: `新川崎（暂）`
- Detection run: `outputs/runs/phase2-gbc06-17-3-target-fix-v3`
- Phase 6 GPT run: `outputs/runs/phase6-gbc06-17-3-text-pixel-mask-gpt-v1`

The goal of this increment was not to call `gpt-image-2` again. The existing real GPT result was adapted into the standard Phase 6 cleanup contract so Phase 7 preview and Phase 8 Photoshop export can consume it like other cleanup runs.

## Bbox Policy

For outside-bubble GPT replacement, the detected bbox is treated as a loose container for the intended original text. It does not need to exclude non-text content such as people, hair, props, background texture, or panel edges.

The pass/fail boundary is:

- pass when the bbox contains the intended original text and the GPT edit is constrained by the text-pixel mask;
- fail when the bbox misses the intended original text, lands on blank area, or targets a different text string;
- judge final quality by whether target lettering changed, original lettering disappeared, and non-text manga content was preserved.

This matches the current product direction: do not waste retries trying to remove unrelated non-text context from the locator rectangle. The prompt and mask should ask `gpt-image-2` to modify only the original lettering.

## Code Contract Update

`autolettering.phase6_nonbubble_gpt_replace` now writes `cleanup-results.jsonl` next to `gpt-replace-results.jsonl`.

For successful GPT direct replacements, the cleanup row uses:

```json
{
  "status": "cleaned",
  "cleanup": {
    "method": "gpt_image2_text_pixel_masked_edit",
    "replacement_method": "gpt_image2_masked_edit",
    "text_overlay_required": false,
    "text_region_source": "phase6_nonbubble_gpt_replace_text_pixels"
  }
}
```

The cleanup contract keeps two coordinate layers:

- `bbox` is the global context patch bbox pasted back to the page.
- `mask_bbox` is the global target edit bbox derived from `context_bbox + local_target_bbox`.
- `text_bbox` and `layout_text_bbox` preserve the original detected text region.
- `cleaned_crop_path` is the context-sized baseline/background crop.
- `replacement_crop_path` is the context-sized GPT result with final translated lettering.
- `gpt_image2_replace.target_crop_path` is retained only as a local review crop, not as the patch pasted by Phase 7/8.

This preserves the existing cleanup contract: quality gates can compare a baseline context crop against the GPT result, while Phase 7 and Phase 8 can paste a context-sized repaired crop without resizing a tight target crop over the wrong area.

Phase 7 also preserves:

- `replacement_method`
- `effective_crop_path`

This is required when Phase 8 is given `--preview-run-dir`: Phase 8 reuses Phase 7's page-level cleaned bitmap as `修复图像`, and reads Phase 7 records to populate `repair_sources`.

## Real Phase 7 Preview Run

Command:

```powershell
python experiments/phase7_page_preview.py --detection-run-dir outputs/runs/phase2-gbc06-17-3-target-fix-v3 --cleanup-run-dir outputs/runs/phase6-gbc06-17-3-text-pixel-mask-gpt-v1 --layout-run-dir outputs/runs/phase4-gbc06-17-3-layout-target-fix-v4 --output-root outputs/runs --run-id phase7-gbc06-17-3-text-pixel-gpt-preview-v1 --sample-limit 1
```

Run directory:

- `outputs/runs/phase7-gbc06-17-3-text-pixel-gpt-preview-v1`

Manifest summary:

- `record_count=1`
- `page_count=1`
- `skipped_count=0`
- `records[0].cleanup_method=gpt_image2_masked_edit`
- `records[0].replacement_method=gpt_image2_masked_edit`
- `records[0].text_overlay_required=false`
- `records[0].bbox=[1010,205,1158,294]`
- `records[0].text_bbox=[1026,221,1142,278]`
- `records[0].effective_crop_path=outputs/runs/phase6-gbc06-17-3-text-pixel-mask-gpt-v1/gpt_image2_replace_context_crop/GBC06-17-png-3.png`

Key artifacts:

- Preview page: `outputs/runs/phase7-gbc06-17-3-text-pixel-gpt-preview-v1/pages/GBC06-17-png.png`
- Cleaned page: `outputs/runs/phase7-gbc06-17-3-text-pixel-gpt-preview-v1/pages/cleaned/GBC06-17-png.png`
- Before/after crop: `outputs/runs/phase7-gbc06-17-3-text-pixel-gpt-preview-v1/crops/before_after/GBC06-17-png-3.png`
- Context before/after crop: `outputs/runs/phase7-gbc06-17-3-text-pixel-gpt-preview-v1/crops/context_before_after/GBC06-17-png-3.png`
- Debug overlay: `outputs/runs/phase7-gbc06-17-3-text-pixel-gpt-preview-v1/debug/page_overlays/GBC06-17-png.png`

## MIMO Phase 7 Evaluation

Command:

```powershell
python experiments/phase7_preview_evaluate.py --preview-run-dir outputs/runs/phase7-gbc06-17-3-text-pixel-gpt-preview-v1 --output-root outputs/runs --run-id phase7-gbc06-17-3-text-pixel-gpt-preview-mimo-v1 --sample-limit 1
```

Run directory:

- `outputs/runs/phase7-gbc06-17-3-text-pixel-gpt-preview-mimo-v1`

Result:

- `status=evaluated`
- `score=10`
- `usable=true`
- `original_text_removed=true`
- `art_preserved=true`
- `lettering_readable=true`
- `issues=[]`

MIMO summary:

> The original Japanese text has been perfectly replaced with the expected Chinese translation. The lettering is accurately placed within the original text area, is highly readable, and the surrounding artwork is preserved.

Caveat: previous experiments on this same sample showed MIMO can be weak at strict simplified-vs-traditional glyph checks such as `暂` versus `暫`. Treat the model result as a useful gate, not a replacement for manual visual inspection.

## Real Phase 8 Photoshop Export Run

Command:

```powershell
python experiments/phase8_photoshop_export.py --detection-run-dir outputs/runs/phase2-gbc06-17-3-target-fix-v3 --font-selection-run-dir outputs/runs/phase3-gbc06-17-3-mimo-font-selection-target-fix-v2 --layout-run-dir outputs/runs/phase4-gbc06-17-3-layout-target-fix-v4 --cleanup-run-dir outputs/runs/phase6-gbc06-17-3-text-pixel-mask-gpt-v1 --preview-run-dir outputs/runs/phase7-gbc06-17-3-text-pixel-gpt-preview-v1 --output-root outputs/runs --run-id phase8-gbc06-17-3-text-pixel-gpt-export-v1 --sample-limit 1
```

Run directory:

- `outputs/runs/phase8-gbc06-17-3-text-pixel-gpt-export-v1`

Manifest summary:

- `summary.record_count=0`
- `summary.page_count=1`
- `pages[0].layers=[]`
- `pages[0].repaired_image_path=outputs/runs/phase7-gbc06-17-3-text-pixel-gpt-preview-v1/pages/cleaned/GBC06-17-png.png`
- `pages[0].repair_sources[0].bbox_xyxy=[1010,205,1158,294]`
- `pages[0].repair_sources[0].replacement_method=gpt_image2_masked_edit`
- `pages[0].repair_sources[0].effective_method=gpt_image2_masked_edit`
- `pages[0].repair_sources[0].effective_crop_path=outputs/runs/phase6-gbc06-17-3-text-pixel-mask-gpt-v1/gpt_image2_replace_context_crop/GBC06-17-png-3.png`
- `pages[0].repair_sources[0].text_overlay_required=false`

This matches the intended PSD structure:

```text
修复图像
原图
```

No editable `嵌字图层*` is emitted for this record because the GPT crop already contains final translated lettering. The source remains auditable through `repair_sources`.

Photoshop itself was not executed in this run; validation is manifest-level plus generated bitmap inspection.

## Verification

Targeted tests run during development:

```powershell
python -m pytest tests/test_phase6_nonbubble_gpt_replace.py::test_run_phase6_nonbubble_gpt_replace_uses_context_mask_and_target_text -q
python -m pytest tests/test_phase6_nonbubble_gpt_replace.py -q
python -m pytest tests/test_phase7_preview.py::test_run_phase7_preview_does_not_require_or_overlay_layout_for_gpt_direct_replacement -q
python -m pytest tests/test_phase6_nonbubble_gpt_replace.py tests/test_phase7_preview.py::test_run_phase7_preview_does_not_require_or_overlay_layout_for_gpt_direct_replacement tests/test_phase7_preview.py::test_run_phase7_preview_prefers_replacement_crop_when_available tests/test_phase8_photoshop_export.py::test_run_phase8_photoshop_export_skips_text_layer_for_gpt_replacement_cleanup -q
python -m pytest tests/test_phase7_preview.py::test_run_phase7_preview_uses_cleaned_crop_when_gpt_replacement_quality_fails tests/test_phase8_photoshop_export.py::test_run_phase8_photoshop_export_preserves_phase7_gpt_direct_replacement_provenance tests/test_phase8_photoshop_export.py::test_run_phase8_photoshop_export_uses_phase7_rejected_gpt_fallback_provenance -q
```

Final regression for this increment:

```powershell
python -m pytest tests/test_phase6_nonbubble_gpt_replace.py tests/test_phase7_preview.py tests/test_phase8_photoshop_export.py tests/test_phase7_8_gpt_quality_gate_smoke.py -q
git diff --check
```

## Result

The Phase 6 GPT direct replacement path is now usable by Phase 7 and Phase 8 without a special one-off adapter script. The real `GBC06_17.png#3` result can be previewed as a page bitmap and exported into the Photoshop manifest as a page-level repaired image with no duplicate editable text layer.
