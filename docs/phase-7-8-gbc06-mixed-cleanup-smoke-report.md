# Phase 7/8 GBC06 Mixed Cleanup Smoke Report

This run refreshes the earlier mixed cleanup smoke with the improved Phase 6 cleanup chain:

- Bubble text: `bubble_mask_fill` from `outputs/runs/phase6-gbc06-bubble-mask-smoke`
- Non-bubble text: `bt_lama_large_inpaint` from `outputs/runs/phase6-gbc06-nonbubble-lama-large-compare`

The previous mixed smoke used `bubble_fill` plus `gpt_image2_masked_edit`. That combination is superseded because the full-rectangle bubble fill damaged nearby art, and the GPT direct replacement was rated unusable in the Phase 6 MIMO evaluation.

## Commands

```powershell
python experiments/phase7_page_preview.py --detection-run-dir outputs/runs/phase2-gbc06-smoke --cleanup-run-dir outputs/runs/phase6-gbc06-bubble-mask-smoke --cleanup-run-dir outputs/runs/phase6-gbc06-nonbubble-lama-large-compare --layout-run-dir outputs/runs/phase4-gbc06-nonbubble-layout-smoke --run-id phase7-gbc06-lama-cleanup-preview-smoke --sample-limit 2
```

```powershell
python experiments/phase7_preview_evaluate.py --preview-run-dir outputs/runs/phase7-gbc06-lama-cleanup-preview-smoke --run-id phase7-gbc06-lama-cleanup-preview-mimo-eval --sample-limit 1
```

```powershell
python experiments/phase8_photoshop_export.py --detection-run-dir outputs/runs/phase2-gbc06-smoke --font-selection-run-dir outputs/runs/phase3-gbc06-nonbubble-mimo-font-smoke --layout-run-dir outputs/runs/phase4-gbc06-nonbubble-layout-smoke --cleanup-run-dir outputs/runs/phase6-gbc06-bubble-mask-smoke --cleanup-run-dir outputs/runs/phase6-gbc06-nonbubble-lama-large-compare --run-id phase8-gbc06-lama-cleanup-export-smoke --sample-limit 2
```

## Inputs

- Detection source: `outputs/runs/phase2-gbc06-smoke/detections.jsonl`
- Font selection source: `outputs/runs/phase3-gbc06-nonbubble-mimo-font-smoke/font-selections.jsonl`
- Layout source: `outputs/runs/phase4-gbc06-nonbubble-layout-smoke/layout-results.jsonl`
- Bubble cleanup source: `outputs/runs/phase6-gbc06-bubble-mask-smoke/cleanup-results.jsonl`
- Non-bubble cleanup source: `outputs/runs/phase6-gbc06-nonbubble-lama-large-compare/cleanup-results.jsonl`

Multiple `--cleanup-run-dir` values are merged by `record_id`.
If the same record appears in more than one cleanup run, later arguments override earlier ones.

## Phase 7 Output

Run directory:

```text
outputs/runs/phase7-gbc06-lama-cleanup-preview-smoke
```

Generated page preview:

```text
outputs/runs/phase7-gbc06-lama-cleanup-preview-smoke/pages/GBC06-01-png.png
```

Generated Phase 7 artifacts:

- `manifest.json`
- `preview-results.jsonl`
- `pages/original/GBC06-01-png.png`
- `pages/cleaned/GBC06-01-png.png`
- `pages/GBC06-01-png.png`
- `debug/page_overlays/GBC06-01-png.png`
- `crops/before_after/GBC06-01-png-1.png`
- `crops/before_after/GBC06-01-png-16.png`
- `reports/phase7-report.md`
- `reports/manual-review.csv`

Image check:

- Original page image: `1440 x 2048`, `RGB`, size `3144189` bytes
- Cleaned page image: `1440 x 2048`, `RGB`, size `3139629` bytes
- Final page image: `1440 x 2048`, `RGB`, size `3149871` bytes
- Debug overlay image: `1440 x 2048`, `RGB`, size `3146863` bytes
- Original vs cleaned changed: `true`
- Cleaned vs final preview changed: `true`
- Final preview vs debug overlay changed: `true`
- Debug overlay bbox pixels: `GBC06_01.png#1@(674,0)=(255,0,0)`, `GBC06_01.png#16@(1349,121)=(255,0,0)`
- `GBC06_01.png#1` preview before/after size: `750 x 342`
- `GBC06_01.png#16` preview before/after size: `116 x 257`

`preview-results.jsonl` contains one generated page preview with two records:

```json
{
  "image_name": "GBC06_01.png",
  "status": "page_preview_generated",
  "records": [
    {
      "record_id": "GBC06_01.png#1",
      "translated_text": "街头演出？",
      "cleanup_method": "bubble_mask_fill",
      "cleanup_crop_path": "outputs\\runs\\phase6-gbc06-bubble-mask-smoke\\crops\\cleaned\\GBC06-01-png-1.png",
      "preview_before_after_path": "outputs\\runs\\phase7-gbc06-lama-cleanup-preview-smoke\\crops\\before_after\\GBC06-01-png-1.png"
    },
    {
      "record_id": "GBC06_01.png#16",
      "translated_text": "来自桃香的唐突的提案",
      "cleanup_method": "bt_lama_large_inpaint",
      "cleanup_crop_path": "outputs\\runs\\phase6-gbc06-nonbubble-lama-large-compare\\crops\\cleaned\\GBC06-01-png-16.png",
      "preview_before_after_path": "outputs\\runs\\phase7-gbc06-lama-cleanup-preview-smoke\\crops\\before_after\\GBC06-01-png-16.png"
    }
  ],
  "preview": {
    "original_page_path": "outputs\\runs\\phase7-gbc06-lama-cleanup-preview-smoke\\pages\\original\\GBC06-01-png.png",
    "cleaned_page_path": "outputs\\runs\\phase7-gbc06-lama-cleanup-preview-smoke\\pages\\cleaned\\GBC06-01-png.png",
    "page_preview_path": "outputs\\runs\\phase7-gbc06-lama-cleanup-preview-smoke\\pages\\GBC06-01-png.png",
    "debug_overlay_path": "outputs\\runs\\phase7-gbc06-lama-cleanup-preview-smoke\\debug\\page_overlays\\GBC06-01-png.png",
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
- Manifest size: `2862` bytes
- Preview results size: `1592` bytes
- Manual review CSV rows: 2
- Manual review CSV size: `1121` bytes

Visual inspection notes:

- `GBC06_01.png#1`: `bubble_mask_fill` removes the original text while preserving the speech bubble boundary, screentone, and visible character art inside the large detected bbox.
- `GBC06_01.png#16`: `bt_lama_large_inpaint` cleans the non-bubble side text area before the vertical translated lettering is rendered.

## Phase 7 MIMO Evaluation

Run directory:

```text
outputs/runs/phase7-gbc06-lama-cleanup-preview-mimo-eval
```

Generated artifacts:

- `preview-evaluation.jsonl`
- `reports/api-calls.jsonl`
- `reports/phase7-evaluation-report.md`

MIMO request summary:

- Kind: `phase7_preview_evaluation`
- Model: `mimo-v2.5`
- Image count: 1
- Prompt chars: 563
- Max completion tokens: 192
- Thinking: `disabled`
- Prompt tokens: 3096
- Image tokens: 2880
- Completion tokens: 133

MIMO returned:

```json
{
  "score": 9,
  "usable": true,
  "original_text_removed": true,
  "art_preserved": true,
  "lettering_readable": true,
  "issues": [
    "The English title 'GIRLS BAND CRY' in the banner is slightly pixelated.",
    "The vertical text overlay in the top right is slightly transparent."
  ]
}
```

MIMO summary: the original Japanese text was completely removed with good background preservation, and the translated lettering is readable. The result is usable. The reported issues are minor page-level concerns and do not block this cleanup combination.

## Phase 8 Output

Run directory:

```text
outputs/runs/phase8-gbc06-lama-cleanup-export-smoke
```

Generated artifacts:

- `photoshop-manifest.json`
- `photoshop-import.jsx`
- `reports/phase8-report.md`
- `reports/photoshop-validation-checklist.md`

Manifest summary:

- Pages exported: 1
- Text layers exported: 2
- Manifest size: `5994` bytes
- JSX size: `4103` bytes
- Phase 8 report size: `1247` bytes
- Photoshop checklist size: `1146` bytes
- Missing cleanup layers: 0
- Effective cleanup methods: `bt_lama_large_inpaint=1`, `bubble_mask_fill=1`

The exported cleanup paths are:

```json
[
  {
    "record_id": "GBC06_01.png#1",
    "effective_method": "bubble_mask_fill",
    "effective_crop_path": "outputs\\runs\\phase6-gbc06-bubble-mask-smoke\\crops\\cleaned\\GBC06-01-png-1.png"
  },
  {
    "record_id": "GBC06_01.png#16",
    "effective_method": "bt_lama_large_inpaint",
    "effective_crop_path": "outputs\\runs\\phase6-gbc06-nonbubble-lama-large-compare\\crops\\cleaned\\GBC06-01-png-16.png"
  }
]
```

Photoshop validation checklist expectations:

- Expected pages: 1
- Expected editable text layers: 2
- Expected cleanup patch layers: 2
- Font mapping file: none

## Behavior Added

- Phase 7 now has a dedicated MIMO preview evaluation path:
  - `autolettering/phase7_evaluate.py`
  - `experiments/phase7_preview_evaluate.py`
  - `tests/test_phase7_preview_evaluation.py`
- The evaluator reads Phase 7 page preview rows, sends the final page preview to MIMO, and saves:
  - structured page evaluation rows
  - API request/response summaries without secrets
  - a short evaluation report
- The experiment uses `thinking_type="disabled"` to keep response tokens focused on the JSON verdict.

## Current Decision

Use this cleanup combination for the next integrated preview/export work:

- Bubble default: `bubble_mask_fill`
- Non-bubble default: `bt_lama_large_inpaint`
- Non-bubble fallback: `bt_patchmatch`
- Do not use `gpt_image2_masked_edit` as the default cleanup path; it remains an experimental direct-replacement branch only.

## Font Mapping Notes

The refreshed real MIMO font selection run selected `[toolbox]POP1GB-JF-W5` with PostScript name `toolboxPOP1GBJF-W5`.
For `GBC06_01.png#16`, MIMO returned invalid JSON and the existing deterministic fallback selected the first candidate while preserving `failure_reason = "invalid_json"`.

## Limitations

- Photoshop was not available in this environment, so the generated JSX was not executed inside Photoshop.
- Cleanup patch placement is best-effort: if the bitmap path is missing or Photoshop cannot open it, the script still continues to create the editable text layer.
- The mixed smoke covers two records on one real page. Broader coverage still depends on upstream Phase 2/3/4/6 runs producing aligned rows for more records.
- MIMO evaluation was a single page-level check; it is not a substitute for per-record human review.

## Verification

```powershell
python -m pytest tests/test_phase7_preview_evaluation.py -q
python -m pytest tests/test_phase7_preview.py tests/test_phase8_photoshop_export.py -q
python -m pytest -q
git diff --check
```

Recorded verification results during this report refresh:

```text
4 passed in 0.13s
14 passed in 0.60s
78 passed in 2.98s
git diff --check: exit 0
AST length gate (project code): ok
```
