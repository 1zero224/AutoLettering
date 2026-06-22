# Phase 6 Bubble Soft Region Fill Experiment

## Scope

This report records a controlled follow-up for the current bubble "white paint" cleanup quality. The goal was to test whether a feathered `soft_region_fill` improves over the existing hard `bubble_region_fill` for flat white speech bubbles.

The result is conservative: `soft_region_fill` is implemented as an explicit experimental option, but the default remains `region_fill` because the current GBC06 bubble samples do not prove a quality gain. The latest MIMO comparison prefers the hard baseline on these flat bubble samples because the soft method can leave tiny punctuation-like remnants.

## Code Change

New optional cleanup method:

- CLI value: `--cleanup-method soft_region_fill`
- Result method: `bubble_soft_region_fill`
- Implementation: `autolettering/inpaint/bubble_fill.py`
- Routing: `autolettering/phase6.py`

Behavior:

- Uses an expanded context crop around the derived text bbox.
- Fills the text area with the sampled bubble background color.
- Writes a feathered cleanup mask so Phase 7 can composite the cleanup back to the page through a soft edge.
- Keeps the mask core opaque for tiny or page-edge clipped regions so original glyphs do not survive as semi-transparent ghosts.
- Exports cleanup bbox and cleanup position in Phase 8 manifests so Photoshop bitmap cleanup patches align with the larger soft context crop.
- Keeps existing `region_fill` as the default.

## Commands

Soft cleanup run:

```powershell
python experiments/phase6_bubble_cleanup.py --detection-run-dir outputs/runs/phase2-gbc06-smoke-v3 --layout-run-dir outputs/runs/phase4-gbc06-bubble-batch-layout-v7 --run-id phase6-gbc06-bubble-batch-soft-region-fill-v2 --sample-limit 5 --cleanup-method soft_region_fill --record-id 'GBC06_01.png#2' --record-id 'GBC06_01.png#3' --record-id 'GBC06_01.png#4' --record-id 'GBC06_01.png#5' --record-id 'GBC06_01.png#6'
```

Fresh hard baseline with current schema:

```powershell
python experiments/phase6_bubble_cleanup.py --detection-run-dir outputs/runs/phase2-gbc06-smoke-v3 --layout-run-dir outputs/runs/phase4-gbc06-bubble-batch-layout-v7 --run-id phase6-gbc06-bubble-batch-region-fill-v9 --sample-limit 5 --cleanup-method region_fill --record-id 'GBC06_01.png#2' --record-id 'GBC06_01.png#3' --record-id 'GBC06_01.png#4' --record-id 'GBC06_01.png#5' --record-id 'GBC06_01.png#6'
```

Fair cleanup-only comparison:

```powershell
python experiments/phase6_bubble_fill_method_comparison.py --hard-run-dir outputs/runs/phase6-gbc06-bubble-batch-region-fill-v9 --soft-run-dir outputs/runs/phase6-gbc06-bubble-batch-soft-region-fill-v2 --run-id phase6-gbc06-bubble-soft-region-comparison-v3
```

Integrated preview/export with soft cleanup:

```powershell
python experiments/phase7_8_integrated_smoke.py --detection-run-dir outputs/runs/phase2-gbc06-smoke-v3 --cleanup-run-dir outputs/runs/phase6-gbc06-bubble-batch-soft-region-fill-v2 --layout-run-dir outputs/runs/phase4-gbc06-bubble-batch-layout-v7 --font-selection-run-dir outputs/runs/phase3-gbc06-bubble-batch-mimo-font-selection --run-id phase7-8-gbc06-bubble-soft-region-preview-v2 --sample-limit 5
```

## Artifacts

- Soft cleanup run: `outputs/runs/phase6-gbc06-bubble-batch-soft-region-fill-v2`
- Hard baseline run: `outputs/runs/phase6-gbc06-bubble-batch-region-fill-v9`
- Fair comparison sheet: `outputs/runs/phase6-gbc06-bubble-soft-region-comparison-v3/debug/bubble-hard-vs-soft-comparison.png`
- Mask debug sheet: `outputs/runs/phase6-gbc06-bubble-soft-region-comparison-v3/debug/bubble-hard-vs-soft-mask-debug.png`
- MIMO cleanup comparison: `outputs/runs/phase6-gbc06-bubble-soft-region-comparison-v3/reports/mimo-bubble-fill-method-comparison.json`
- Integrated preview run: `outputs/runs/phase7-8-gbc06-bubble-soft-region-preview-v2`
- Integrated preview MIMO result: `outputs/runs/phase7-8-gbc06-bubble-soft-region-preview-v2/runs/phase7-evaluation/preview-evaluation.jsonl`
- Integrated preview contact sheet: `outputs/runs/phase7-8-gbc06-bubble-soft-region-preview-v2/runs/phase7-preview/debug/evaluation_contact_sheets/GBC06-01-png.png`
- Phase 8 manifest with cleanup bbox: `outputs/runs/phase7-8-gbc06-bubble-soft-region-preview-v2/runs/phase8-export/photoshop-manifest.json`
- Latest worker manual review package: `outputs/runs/manual-eval-soft-region-fill-worker-20260622-140733`
- Latest worker contact sheet: `outputs/runs/manual-eval-soft-region-fill-worker-20260622-140733/contact-sheet.png`
- Subagent manual review index: `outputs/runs/manual-eval-soft-region-fill-subagent-20260622-132445/index.md`
- Subagent HTML preview: `outputs/runs/manual-eval-soft-region-fill-subagent-20260622-132445/preview.html`

Generated `outputs/` remain ignored by Git.

## MIMO Results

Cleanup-only fair comparison used `mimo-v2.5` and compared three tiles per record: original context, hard cleaned in the same context, and soft cleaned in the same context.

Latest v3 result summary:

```json
{
  "best_method": "hard_cleaned",
  "scores": {
    "GBC06_01.png#2": 10,
    "GBC06_01.png#3": 10,
    "GBC06_01.png#4": 10,
    "GBC06_01.png#5": 10,
    "GBC06_01.png#6": 10
  },
  "unacceptable_methods": [],
  "reasoning_summary": "Both methods successfully remove the original Japanese text without leaving noticeable white patch edges or damaging the surrounding bubble context. However, the soft cleaned version consistently leaves minor artifacts at the bottom of the text area, while the hard cleaned version produces a completely clean result."
}
```

MIMO caveat:

- The samples are mostly flat white bubble interiors, so `region_fill` is already strong.
- The first comparison attempt included masks in the scoring sheet and produced misleading edge-artifact criticism. Later comparisons removed masks from the scoring sheet and kept masks only in a debug sheet.

Integrated Phase 7/8 preview with `bubble_soft_region_fill`:

```json
{
  "preview_record_count": 5,
  "evaluation_score": 9,
  "evaluation_usable": true,
  "missing_cleanup_layers": 0,
  "effective_cleanup_methods": {
    "bubble_soft_region_fill": 5
  }
}
```

Phase 8 manifest verification:

- Each exported layer now includes `cleanup.bbox` and `cleanup.position`.
- `photoshop-import.jsx` places cleanup bitmap patches by `cleanup.position` when present, falling back to the detection position only for older cleanup rows.
- In the v2 integrated run, the first exported layer keeps text `bbox.xyxy = [526, 149, 563, 337]` while cleanup `bbox.xyxy = [478, 139, 609, 347]`, proving the expanded soft context crop is preserved for Photoshop export.

## Decision

- Keep default bubble cleanup as `region_fill`.
- Keep `soft_region_fill` as an explicit experimental/fallback option.
- Do not promote `soft_region_fill` to default until it wins on samples where hard region fill creates visible white-patch edges. On the latest GBC06 samples, MIMO prefers the hard baseline.
- The remaining visible issues in this bubble batch are dominated by lettering layout/scale, not by the white cleanup itself.

## Verification

Focused TDD verification:

```powershell
python -m pytest tests/test_phase6_cleanup.py::test_soft_region_fill_text_area_feathers_cleanup_mask_edges -q
python -m pytest tests/test_phase6_cleanup.py -q
python -m pytest tests/test_phase6_cleanup.py tests/test_phase8_photoshop_export.py -q
python -m pytest -q
git diff --check
```

Observed:

```text
1 passed
12 passed
18 passed
150 passed
clean
```
