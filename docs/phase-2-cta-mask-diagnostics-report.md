# Phase 2 CTA Mask Match Diagnostics Report

## Scope

This slice makes Phase 2 detection rows easier to audit without joining back
to page-level debug artifacts.

The existing canonical contract remains unchanged:

- `cta_match` / `ctd_match` keep the selected component result.
- `text_region_mask_path` / `text_region_mask_bbox_xyxy` stay the downstream
  text-region source for Phase 6 and Phase 8.
- `debug/ctd_masks/<page>/ctd-mask-edge-distances.jsonl` remains the full
  candidate matrix.

The new `cta_match_diagnostics` / `ctd_match_diagnostics` payload is an
additive row-level summary for human triage and later reporting.

## Code Contract

Detection rows now include:

```json
{
  "schema_version": "autolettering.cta_mask_match_diagnostics.v1",
  "record_id": "GBC06_33.png#1",
  "match_status": "matched",
  "failure_reason": null,
  "threshold_px": 80.0,
  "candidate_count": 32,
  "within_threshold_count": 3,
  "nearest_component_id": "component-0001",
  "nearest_edge_distance_px": 27.0,
  "selected_component_id": "component-0001+...",
  "top_candidates": [
    {
      "component_id": "component-0001",
      "component_bbox_xyxy": [1182, 371, 1270, 459],
      "component_mask_path": "outputs\\runs\\...\\component-0001.png",
      "edge_distance_px": 27.0,
      "within_threshold": true
    }
  ]
}
```

`reports/manual-review.csv` also repeats the nearest mask-match fields:

- `mask_match_status`
- `mask_match_nearest_component_id`
- `mask_match_nearest_edge_distance_px`
- `mask_match_within_threshold_count`

## TDD Evidence

Red test command:

```powershell
python -m pytest tests/test_phase2_ctd_strategy.py::test_run_phase2_cta_strategy_writes_mask_component_as_primary_text_region tests/test_phase2_ctd_strategy.py::test_run_phase2_ctd_strategy_records_fallback_required_when_no_component_is_close -q
```

Initial result:

```text
FAILED ... KeyError: 'cta_match_diagnostics'
FAILED ... KeyError: 'ctd_match_diagnostics'
```

After implementation, targeted tests passed:

```text
16 passed in 11.04s
```

## Real Experiment

Two records were selected:

- `GBC06_33.png#1`: red side-banner text; expected to match only when the CTD
  edge-distance threshold is relaxed.
- `GBC06_16.png#5`: known fallback sample; expected to remain unmatched and
  continue to the MIMO locator + `gpt-image-2` route.

No external API call is made in this Phase 2 experiment. It runs local
BallonsTranslator CTD detection only.

### Threshold 20

Command:

```powershell
python experiments/phase2_detect_text_regions.py --labelplus-file "GBC06 (已翻 斗笠)\翻译_0.txt" --output-root outputs/runs --run-id phase2-gbc06-cta-diagnostics-33-1-16-5-v1 --sample-limit 2 --record-id "GBC06_33.png#1" --record-id "GBC06_16.png#5" --detection-strategy cta_mask --ctd-max-edge-distance-px 20
```

Run directory:

```text
outputs/runs/phase2-gbc06-cta-diagnostics-33-1-16-5-v1
```

Result:

```text
GBC06_16.png#5 status=fallback_required nearest=component-0003 distance=231.0 within_threshold_count=0
GBC06_33.png#1 status=fallback_required nearest=component-0001 distance=27.0 within_threshold_count=0
```

Interpretation:

- The default `20px` threshold is too strict for `GBC06_33.png#1`; its nearest
  CTD component is `27px` from the LabelPlus point, so it correctly falls back.
- The diagnostics row explains this directly; previously this required opening
  `ctd-mask-edge-distances.jsonl`.

### Threshold 80

Command:

```powershell
python experiments/phase2_detect_text_regions.py --labelplus-file "GBC06 (已翻 斗笠)\翻译_0.txt" --output-root outputs/runs --run-id phase2-gbc06-cta-diagnostics-33-1-16-5-v2-th80 --sample-limit 2 --record-id "GBC06_33.png#1" --record-id "GBC06_16.png#5" --detection-strategy cta_mask --ctd-max-edge-distance-px 80
```

Run directory:

```text
outputs/runs/phase2-gbc06-cta-diagnostics-33-1-16-5-v2-th80
```

Result:

```text
GBC06_16.png#5 status=fallback_required nearest=component-0003 distance=231.0 within_threshold_count=0
GBC06_33.png#1 status=ok nearest=component-0001 distance=27.0 within_threshold_count=3 selected_bbox=[1156, 371, 1298, 1925]
```

Manual review CSV summary:

```json
[
  {
    "record_id": "GBC06_16.png#5",
    "status": "fallback_required",
    "mask_match_status": "fallback_required",
    "mask_match_nearest_component_id": "component-0003",
    "mask_match_nearest_edge_distance_px": "231.0",
    "mask_match_within_threshold_count": "0",
    "selected_text_box_xyxy": "null"
  },
  {
    "record_id": "GBC06_33.png#1",
    "status": "ok",
    "mask_match_status": "matched",
    "mask_match_nearest_component_id": "component-0001",
    "mask_match_nearest_edge_distance_px": "27.0",
    "mask_match_within_threshold_count": "3",
    "selected_text_box_xyxy": "[1156, 371, 1298, 1925]"
  }
]
```

Visual evidence:

- `outputs/runs/phase2-gbc06-cta-diagnostics-33-1-16-5-v2-th80/debug/detection/GBC06_33-1.png`
- `outputs/runs/phase2-gbc06-cta-diagnostics-33-1-16-5-v2-th80/debug/detection/GBC06_16-5.png`
- `outputs/runs/phase2-gbc06-cta-diagnostics-33-1-16-5-v2-th80/debug/ctd_masks/GBC06_33/cta-closed-mask-components.json`
- `outputs/runs/phase2-gbc06-cta-diagnostics-33-1-16-5-v2-th80/debug/ctd_masks/GBC06_33/ctd-mask-edge-distances.jsonl`

## Decision

Keep diagnostics as an additive explainability layer.

The row-level summary is useful because it makes threshold sensitivity visible:
`GBC06_33.png#1` flips from fallback at `20px` to a valid merged CTA mask match
at `80px`, while `GBC06_16.png#5` remains a true fallback. The diagnostics
field does not replace the existing downstream contract and should not be used
as the canonical mask source by Phase 6 or Phase 8.

## Verification

```powershell
python -m pytest tests/test_phase2_ctd_strategy.py tests/test_ctd_mask_matching.py tests/test_cta_first_pipeline.py -q
```

Fresh result before this report was written:

```text
16 passed in 11.04s
```
