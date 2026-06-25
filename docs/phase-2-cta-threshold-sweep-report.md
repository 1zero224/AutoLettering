# Phase 2 CTA Threshold Sweep Report

## Scope

This slice adds a lightweight threshold-sweep tool for CTA/CTD mask matching.
It reuses an existing Phase 2 run instead of rerunning BallonsTranslator CTD for
every threshold.

Input artifacts:

- `detections.jsonl`
- `debug/ctd_masks/<page>/ctd-mask-edge-distances.jsonl`

Output artifacts:

- `threshold-sweep.json`
- `threshold-sweep.csv`
- `reports/phase2-threshold-sweep-report.md`

The sweep is diagnostic only. It does not change the canonical Phase 2
contracts: downstream stages should still read `cta_match`, `ctd_match`,
`text_region_mask_path`, and `text_region_mask_bbox_xyxy` from the original
Phase 2 run.

## Implementation

New entry points:

- `autolettering.phase2_threshold_sweep.run_phase2_threshold_sweep`
- `experiments/phase2_cta_threshold_sweep.py`

The JSON schema version is:

```text
autolettering.phase2.cta_threshold_sweep.v1
```

For each record, the tool reports:

- nearest CTD component id
- nearest point-to-mask-edge distance
- first threshold where any component enters distance coverage
- first threshold where Phase 2 `unique_component_claim` would canonically match
- per-threshold canonical claim status and distance coverage count

The report explicitly warns that high first canonical thresholds are not safe
by themselves. A large first-matching distance means the LabelPlus point is far
from the closest closed mask edge, so the record should stay on the fallback
route unless the debug overlay confirms the component.

Two summary families are intentionally separate:

- `canonical_match_counts`: replays Phase 2 page-level
  `unique_component_claim`, so two labels cannot both claim the same component
  group.
- `distance_coverage_counts`: proximity-only coverage, meaning at least one
  component is within the edge-distance threshold.

## Real Experiment

Source Phase 2 run:

```text
outputs/runs/phase2-gbc06-cta-diagnostics-33-1-16-5-v2-th80
```

Command:

```powershell
python experiments/phase2_cta_threshold_sweep.py --phase2-run-dir outputs/runs/phase2-gbc06-cta-diagnostics-33-1-16-5-v2-th80 --output-root outputs/runs --run-id phase2-gbc06-cta-threshold-sweep-33-1-16-5-v1 --threshold 20 --threshold 40 --threshold 60 --threshold 80 --threshold 120 --threshold 240
```

Run directory:

```text
outputs/runs/phase2-gbc06-cta-threshold-sweep-33-1-16-5-v1
```

Summary:

```json
{
  "record_count": 2,
  "threshold_count": 6,
  "match_counts": {
    "20.0": 0,
    "40.0": 1,
    "60.0": 1,
    "80.0": 1,
    "120.0": 1,
    "240.0": 2
  },
  "canonical_match_counts": {
    "20.0": 0,
    "40.0": 1,
    "60.0": 1,
    "80.0": 1,
    "120.0": 1,
    "240.0": 2
  },
  "distance_coverage_counts": {
    "20.0": 0,
    "40.0": 1,
    "60.0": 1,
    "80.0": 1,
    "120.0": 1,
    "240.0": 2
  },
  "first_match_counts": {
    "20.0": 0,
    "40.0": 1,
    "60.0": 0,
    "80.0": 0,
    "120.0": 0,
    "240.0": 1
  },
  "first_canonical_match_counts": {
    "20.0": 0,
    "40.0": 1,
    "60.0": 0,
    "80.0": 0,
    "120.0": 0,
    "240.0": 1
  },
  "first_distance_coverage_counts": {
    "20.0": 0,
    "40.0": 1,
    "60.0": 0,
    "80.0": 0,
    "120.0": 0,
    "240.0": 1
  },
  "fallback_counts": {
    "20.0": 2,
    "40.0": 1,
    "60.0": 1,
    "80.0": 1,
    "120.0": 1,
    "240.0": 0
  }
}
```

Record-level result:

```csv
record_id,nearest_edge_distance_px,first_canonical_matching_threshold_px,first_distance_threshold_px,safe_default_candidate,distance_warning
GBC06_16.png#5,231.0,240.0,240.0,false,high_distance_review_required
GBC06_33.png#1,27.0,40.0,40.0,true,
```

Visual evidence from the source Phase 2 run:

- `outputs/runs/phase2-gbc06-cta-diagnostics-33-1-16-5-v2-th80/debug/detection/GBC06_33-1.png`
- `outputs/runs/phase2-gbc06-cta-diagnostics-33-1-16-5-v2-th80/debug/detection/GBC06_16-5.png`

## Decision

Do not globally raise the default CTA/CTD edge-distance threshold to a very high
value.

The sweep shows two different cases:

- `GBC06_33.png#1` has a nearest edge distance of `27px`; thresholds from
  `40px` canonically claim the intended vertical side-banner mask.
- `GBC06_16.png#5` has a nearest edge distance of `231px`; it only starts
  canonically claiming at `240px`, and the run marks it
  `high_distance_review_required`. This is too broad to trust as an automatic
  default and should remain on the MIMO locator plus `gpt-image-2` fallback
  route.

This supports keeping a moderate default threshold and using the sweep/diagnostic
artifacts for sample-specific tuning instead of silently turning every distant
mask into a match.

## Verification

Targeted tests after implementation:

```powershell
python -m pytest tests/test_phase2_threshold_sweep.py tests/test_experiment_clis.py -q
```

Result:

```text
21 passed in 1.55s
```

The regression suite includes a synthetic conflict case where two labels are
within range of the same component. `distance_coverage_counts` reports two
covered records, while `canonical_match_counts` reports one canonical claim and
one `component_already_claimed` fallback.
