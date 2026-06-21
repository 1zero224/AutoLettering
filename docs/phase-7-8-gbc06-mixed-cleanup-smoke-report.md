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
      "cleanup_method": "bubble_fill"
    },
    {
      "record_id": "GBC06_01.png#16",
      "cleanup_method": "gpt_image2_masked_edit"
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
- Manifest size: `5578` bytes
- JSX size: `2418` bytes
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

## Limitations

- Photoshop was not available in this environment, so the generated JSX was not executed inside Photoshop.
- The JSX still creates editable text layers only; bitmap cleanup/replacement paths are available in the manifest but are not placed as Photoshop image layers yet.
- The mixed smoke covers two records on one real page. Broader coverage still depends on upstream Phase 2/3/4/6 runs producing aligned rows for more records.

## Verification

```powershell
python -m pytest tests/test_phase7_preview.py -q
python -m pytest tests/test_phase8_photoshop_export.py -q
python -m pytest -q
```

Fresh result before this report was written:

```text
5 passed in 0.35s
3 passed in 0.27s
55 passed in 3.51s
```
