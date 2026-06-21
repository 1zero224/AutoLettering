# Phase 7 GBC06 Non-Bubble GPT Preview Smoke Report

## Commands

Generate font comparison grids for the first two detected records, including the first non-bubble record:

```powershell
python experiments/phase3_font_comparison.py --labelplus-file "GBC06 (已翻 斗笠)\翻译_0.txt" --detection-run-dir outputs/runs/phase2-gbc06-smoke --font-dir "工具箱漫画字体V2.5" --run-id phase3-gbc06-nonbubble-font-smoke --sample-limit 2 --font-limit 12
```

Run controlled MIMO font selection:

```powershell
python experiments/phase3_mimo_font_selection.py --input-run-dir outputs/runs/phase3-gbc06-nonbubble-font-smoke --run-id phase3-gbc06-nonbubble-mimo-font-smoke --sample-limit 2
```

Estimate orientation and angle for the same records:

```powershell
python experiments/phase5_orientation_angle.py --detection-run-dir outputs/runs/phase2-gbc06-smoke --run-id phase5-gbc06-nonbubble-angle-smoke --sample-limit 2
```

Generate angle-aware layout:

```powershell
python experiments/phase4_layout_search.py --selection-run-dir outputs/runs/phase3-gbc06-nonbubble-mimo-font-smoke --angle-run-dir outputs/runs/phase5-gbc06-nonbubble-angle-smoke --run-id phase4-gbc06-nonbubble-layout-smoke --sample-limit 2
```

Generate full-page preview using the normalized gpt-image-2 replacement crop:

```powershell
python experiments/phase7_page_preview.py --detection-run-dir outputs/runs/phase2-gbc06-smoke --cleanup-run-dir outputs/runs/phase6-gbc06-nonbubble-gpt-image-smoke --layout-run-dir outputs/runs/phase4-gbc06-nonbubble-layout-smoke --run-id phase7-gbc06-nonbubble-gpt-preview-smoke --sample-limit 1
```

## Output

Preview run directory:

```text
outputs/runs/phase7-gbc06-nonbubble-gpt-preview-smoke
```

Generated artifacts:

- `preview-results.jsonl`
- `pages/GBC06-01-png.png`
- `reports/phase7-report.md`

## Result Summary

- Record: `GBC06_01.png#16`
- Group: `框外`
- Cleanup method used by Phase 7: `gpt_image2_masked_edit`
- Cleanup bbox: `[1349, 121, 1407, 378]`
- Normalized replacement crop: `outputs/runs/phase6-gbc06-nonbubble-gpt-image-smoke/gpt_image2_normalized/GBC06-01-png-16.png`
- Selected font: `font-73f8e41116cb`
- Font family: `[toolbox]YuMo-GB-Bold`
- Font selection source: `mimo_vision`
- Layout orientation: `vertical`
- Layout angle: `0.2`
- Layout font size: `22`
- Layout target size: `58 x 257`
- Layout measured size: `23 x 251`
- Layout overflow ratio: `0.0`
- Page preview: `outputs/runs/phase7-gbc06-nonbubble-gpt-preview-smoke/pages/GBC06-01-png.png`
- Page preview image: `1440 x 2048`, `RGB`, non-empty

The Phase 7 JSONL row is:

```json
{
  "image_name": "GBC06_01.png",
  "status": "page_preview_generated",
  "records": [
    {
      "record_id": "GBC06_01.png#16",
      "bbox": [1349, 121, 1407, 378],
      "cleanup_method": "gpt_image2_masked_edit",
      "layout_preview_path": "outputs\\runs\\phase4-gbc06-nonbubble-layout-smoke\\debug\\layout_candidates\\GBC06-01-png-16.png"
    }
  ],
  "preview": {
    "page_preview_path": "outputs\\runs\\phase7-gbc06-nonbubble-gpt-preview-smoke\\pages\\GBC06-01-png.png",
    "record_count": 1
  }
}
```

## Interpretation

This smoke connects the non-bubble gpt-image path to the page preview chain:

1. Phase 6 creates a local crop, text mask, gpt-image-2 mask, real gpt-image-2 output, and a normalized replacement crop.
2. Phase 7 prefers `cleanup.replacement_crop_path` over the local cleaned crop when present.
3. The normalized gpt-image-2 crop is pasted into the original page.
4. The deterministic layout overlay is then pasted on top.

This is the first preview smoke where a non-bubble region uses a real gpt-image-2 edit result in the page composition path.

## Limitations

- The gpt-image-2 output is center-fit back to the detected bbox size. This is deterministic but may not preserve the best part of the generated image.
- The detected non-bubble bbox is narrow and tall, so both inpainting and text rendering remain highly sensitive to Phase 2 detection quality.
- Layout validation remains deterministic-only; the final page preview is not yet model-approved.
- This non-bubble-only preview covers one record. Mixed bubble/non-bubble composition is now covered by `docs/phase-7-8-gbc06-mixed-cleanup-smoke-report.md`, using repeated `--cleanup-run-dir` inputs.

## Verification

```powershell
python -m pytest tests/test_phase6_nonbubble_cleanup.py -q
python -m pytest tests/test_phase7_preview.py -q
python -m pytest tests/test_mimo_font_selection.py -q
python -m pytest -q
```

Fresh results before this report was written:

```text
6 passed in 2.09s
4 passed in 0.37s
7 passed in 0.50s
53 passed in 3.51s
```

## Notes

- Generated `outputs/` are ignored by Git; this report records the reproducible commands and aggregate result.
- The MIMO call succeeded for the non-bubble record in this run. Phase 3 now also has a deterministic fallback when the model returns invalid JSON.
