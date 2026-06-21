# Phase 7/8 GBC06 Mixed Cleanup Smoke Report

## Commands

```powershell
python experiments/phase7_page_preview.py --detection-run-dir outputs/runs/phase2-gbc06-smoke --cleanup-run-dir outputs/runs/phase6-gbc06-bubble-smoke --cleanup-run-dir outputs/runs/phase6-gbc06-nonbubble-gpt-image-smoke --layout-run-dir outputs/runs/phase4-gbc06-nonbubble-layout-smoke --run-id phase7-gbc06-mixed-cleanup-preview-smoke --sample-limit 2
```

```powershell
python experiments/phase8_photoshop_export.py --detection-run-dir outputs/runs/phase2-gbc06-smoke --font-selection-run-dir outputs/runs/phase3-gbc06-nonbubble-mimo-font-smoke --layout-run-dir outputs/runs/phase4-gbc06-nonbubble-layout-smoke --cleanup-run-dir outputs/runs/phase6-gbc06-bubble-smoke --cleanup-run-dir outputs/runs/phase6-gbc06-nonbubble-gpt-image-smoke --run-id phase8-gbc06-mixed-cleanup-export-smoke --sample-limit 2
```

## Inputs

- Detection source: `outputs/runs/phase2-gbc06-smoke/detections.jsonl`
- Font selection source: `outputs/runs/phase3-gbc06-nonbubble-mimo-font-smoke/font-selections.jsonl`
- Layout source: `outputs/runs/phase4-gbc06-nonbubble-layout-smoke/layout-results.jsonl`
- Bubble cleanup source: `outputs/runs/phase6-gbc06-bubble-smoke/cleanup-results.jsonl`
- Non-bubble GPT cleanup source: `outputs/runs/phase6-gbc06-nonbubble-gpt-image-smoke/cleanup-results.jsonl`

Multiple `--cleanup-run-dir` values are merged by `record_id`.
If the same record appears in more than one cleanup run, later arguments override earlier ones.

## Phase 7 Output

Run directory:

```text
outputs/runs/phase7-gbc06-mixed-cleanup-preview-smoke
```

Generated page preview:

```text
outputs/runs/phase7-gbc06-mixed-cleanup-preview-smoke/pages/GBC06-01-png.png
```

Generated Phase 7 artifacts:

- `manifest.json`
- `preview-results.jsonl`
- `pages/GBC06-01-png.png`
- `crops/before_after/*.png`
- `reports/phase7-report.md`
- `reports/manual-review.csv`

Image check:

- Size: `1440 x 2048`
- Mode: `RGB`
- Channel extrema: `[(0, 255), (0, 255), (0, 255)]`

`preview-results.jsonl` contains one generated page preview with two records:

```json
{
  "image_name": "GBC06_01.png",
  "status": "page_preview_generated",
  "records": [
    {
      "record_id": "GBC06_01.png#1",
      "translated_text": "街头演出？",
      "cleanup_method": "bubble_fill",
      "cleanup_crop_path": "outputs\\runs\\phase6-gbc06-bubble-smoke\\crops\\cleaned\\GBC06-01-png-1.png",
      "preview_before_after_path": "outputs\\runs\\phase7-gbc06-mixed-cleanup-preview-smoke\\crops\\before_after\\GBC06-01-png-1.png"
    },
    {
      "record_id": "GBC06_01.png#16",
      "translated_text": "来自桃香的唐突的提案",
      "cleanup_method": "gpt_image2_masked_edit",
      "cleanup_crop_path": "outputs\\runs\\phase6-gbc06-nonbubble-gpt-image-smoke\\gpt_image2_normalized\\GBC06-01-png-16.png",
      "preview_before_after_path": "outputs\\runs\\phase7-gbc06-mixed-cleanup-preview-smoke\\crops\\before_after\\GBC06-01-png-16.png"
    }
  ],
  "preview": {
    "record_count": 2
  }
}
```

Phase 7 report summary:

- Records processed: 2
- Page previews generated: 1
- Skipped: 0
- Preview before/after crops generated: 2
- Manifest schema: `autolettering.phase7.preview.v1`
- Manifest summary: `record_count=2`, `page_count=1`, `skipped_count=0`
- Manifest artifact keys: `manual_review_csv`, `phase7_report`, `preview_results_jsonl`
- Manifest size: `2487` bytes
- `GBC06_01.png#1` preview before/after size: `750 x 342`
- `GBC06_01.png#16` preview before/after size: `116 x 257`
- Manual review CSV rows: 2
- Manual review CSV size: `1121` bytes

`manifest.json` is the Phase 7 run-level traceability index for the mixed cleanup preview. It records the Phase 2 detection run, both Phase 6 cleanup runs, the Phase 4 layout run, the generated page preview, both page records, and an empty `skipped_records` list.

`crops/before_after/*.png` stores per-record side-by-side crops. The left half is the original page crop for the detected bbox, and the right half is the same bbox from the final composed page preview.

`reports/manual-review.csv` now gives the human review queue for the generated page preview. It contains one row per record, including `record_id`, preview status, image name, translated text, bbox, cleanup method/crop, layout preview path, page preview path, preview before/after crop path, failure reason, and blank `manual_decision` / `review_notes` columns. In this smoke, the two review rows cover:

- `GBC06_01.png#1`: `bubble_fill`
- `GBC06_01.png#16`: `gpt_image2_masked_edit`

## Phase 8 Output

Run directory:

```text
outputs/runs/phase8-gbc06-mixed-cleanup-export-smoke
```

Generated artifacts:

- `photoshop-manifest.json`
- `photoshop-import.jsx`
- `reports/phase8-report.md`

Manifest summary:

- Pages exported: 1
- Text layers exported: 2
- Manifest size: `6017` bytes
- JSX size: `4103` bytes
- Missing cleanup layers: 0
- Effective cleanup methods: `bubble_fill=1`, `gpt_image2_masked_edit=1`

The exported cleanup paths are:

```json
[
  {
    "record_id": "GBC06_01.png#1",
    "effective_method": "bubble_fill",
    "effective_crop_path": "outputs\\runs\\phase6-gbc06-bubble-smoke\\crops\\cleaned\\GBC06-01-png-1.png"
  },
  {
    "record_id": "GBC06_01.png#16",
    "effective_method": "gpt_image2_masked_edit",
    "effective_crop_path": "outputs\\runs\\phase6-gbc06-nonbubble-gpt-image-smoke\\gpt_image2_normalized\\GBC06-01-png-16.png"
  }
]
```

## Behavior Change

- Phase 7 and Phase 8 now accept one or more cleanup run directories.
- The experiment CLI keeps the same `--cleanup-run-dir` name but allows repeating it.
- This removes the previous need to manually create a merged cleanup run before composing a mixed bubble/non-bubble page.
- Phase 7 now writes `reports/manual-review.csv` so generated page previews and skipped records can be accepted, rejected, or annotated during human inspection.
- Phase 7 now writes per-record `crops/before_after/*.png` previews so manual review can inspect local changes without opening the full page.
- Phase 7 now writes `manifest.json` so input runs, summary counts, artifact paths, generated page records, and skipped records are available from one run-level index.
- The Photoshop JSX now attempts to place each layer's `cleanup.effective_crop_path` as a bitmap patch layer named `AL cleanup <record_id>` before adding the editable text layer.
- The editable text layer is now `TextType.PARAGRAPHTEXT` with `item.width` and `item.height` set from the detected bbox dimensions.
- The JSX maps `layout.line_spacing` to Photoshop `leading` and maps `layout.letter_spacing` to best-effort `tracking`.
- The manifest now exports `font.postscript_name`, `font.photoshop_font_name`, and `font.font_name_candidates`; JSX tries `photoshop_font_name` before falling back to `family_name`.

## Font Mapping Notes

The refreshed real MIMO font selection run selected `[toolbox]POP1GB-JF-W5` with PostScript name `toolboxPOP1GBJF-W5`.
For `GBC06_01.png#16`, MIMO returned invalid JSON and the existing deterministic fallback selected the first candidate while preserving `failure_reason = "invalid_json"`.

## Limitations

- Photoshop was not available in this environment, so the generated JSX was not executed inside Photoshop.
- Cleanup patch placement is best-effort: if the bitmap path is missing or Photoshop cannot open it, the script still continues to create the editable text layer.
- The mixed smoke covers two records on one real page. Broader coverage still depends on upstream Phase 2/3/4/6 runs producing aligned rows for more records.

## Verification

```powershell
python -m pytest tests/test_phase3_fonts.py -q
python -m pytest tests/test_phase7_preview.py -q
python -m pytest tests/test_phase8_photoshop_export.py -q
python -m pytest -q
```

Recorded verification results during this report refresh:

```text
5 passed in 0.72s
7 passed in 0.55s
4 passed in 0.34s
59 passed in 3.24s
```
