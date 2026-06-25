import json
from pathlib import Path

from autolettering.phase2_threshold_sweep import run_phase2_threshold_sweep


def test_run_phase2_threshold_sweep_reuses_distance_rows_without_rerunning_ctd(tmp_path: Path):
    phase2_run = tmp_path / "phase2"
    page_dir = phase2_run / "debug" / "ctd_masks" / "page"
    page_dir.mkdir(parents=True)
    _write_jsonl(
        phase2_run / "detections.jsonl",
        [
            {
                "record_id": "page.png#1",
                "image_name": "page.png",
                "status": "fallback_required",
                "cta_match_diagnostics": {
                    "nearest_component_id": "component-0001",
                    "nearest_edge_distance_px": 27.0,
                },
            },
            {
                "record_id": "page.png#2",
                "image_name": "page.png",
                "status": "fallback_required",
                "cta_match_diagnostics": {
                    "nearest_component_id": "component-0003",
                    "nearest_edge_distance_px": 231.0,
                },
            },
        ],
    )
    _write_jsonl(
        page_dir / "ctd-mask-edge-distances.jsonl",
        [
            _distance_row("page.png#1", "component-0001", 27.0),
            _distance_row("page.png#1", "component-0002", 36.4),
            _distance_row("page.png#1", "component-0003", 64.6),
            _distance_row("page.png#1", "component-0004", 90.1),
            _distance_row("page.png#2", "component-0003", 231.0),
        ],
    )

    run_dir = run_phase2_threshold_sweep(
        phase2_run_dir=phase2_run,
        output_root=tmp_path / "outputs",
        run_id="sweep",
        thresholds=[20, 40, 80],
    )

    payload = json.loads((run_dir / "threshold-sweep.json").read_text(encoding="utf-8"))
    assert payload["schema_version"] == "autolettering.phase2.cta_threshold_sweep.v1"
    assert payload["phase2_run_dir"] == str(phase2_run)
    assert payload["thresholds_px"] == [20.0, 40.0, 80.0]
    assert payload["summary"] == {
        "record_count": 2,
        "threshold_count": 3,
        "match_counts": {"20.0": 0, "40.0": 1, "80.0": 1},
        "canonical_match_counts": {"20.0": 0, "40.0": 1, "80.0": 1},
        "distance_coverage_counts": {"20.0": 0, "40.0": 1, "80.0": 1},
        "first_match_counts": {"20.0": 0, "40.0": 1, "80.0": 0},
        "first_canonical_match_counts": {"20.0": 0, "40.0": 1, "80.0": 0},
        "first_distance_coverage_counts": {"20.0": 0, "40.0": 1, "80.0": 0},
        "fallback_counts": {"20.0": 2, "40.0": 1, "80.0": 1},
    }
    records = {record["record_id"]: record for record in payload["records"]}
    assert records["page.png#1"]["nearest_edge_distance_px"] == 27.0
    assert records["page.png#1"]["first_distance_threshold_px"] == 40.0
    assert records["page.png#1"]["first_canonical_matching_threshold_px"] == 40.0
    assert records["page.png#1"]["safe_default_candidate"] is True
    assert records["page.png#1"]["thresholds"] == [
        {
            "threshold_px": 20.0,
            "within_distance_threshold": False,
            "proximity_within_component_count": 0,
            "canonical_would_match": False,
            "canonical_claim_status": "fallback_required",
            "canonical_component_id": None,
            "canonical_failure_reason": "no_ctd_mask_within_threshold",
            "would_match": False,
            "within_threshold_count": 0,
            "nearest_component_id": "component-0001",
            "nearest_edge_distance_px": 27.0,
        },
        {
            "threshold_px": 40.0,
            "within_distance_threshold": True,
            "proximity_within_component_count": 2,
            "canonical_would_match": True,
            "canonical_claim_status": "matched",
            "canonical_component_id": "component-0001+component-0002+component-0003+component-0004",
            "canonical_failure_reason": None,
            "would_match": True,
            "within_threshold_count": 2,
            "nearest_component_id": "component-0001",
            "nearest_edge_distance_px": 27.0,
        },
        {
            "threshold_px": 80.0,
            "within_distance_threshold": True,
            "proximity_within_component_count": 3,
            "canonical_would_match": True,
            "canonical_claim_status": "matched",
            "canonical_component_id": "component-0001+component-0002+component-0003+component-0004",
            "canonical_failure_reason": None,
            "would_match": True,
            "within_threshold_count": 3,
            "nearest_component_id": "component-0001",
            "nearest_edge_distance_px": 27.0,
        },
    ]
    assert records["page.png#2"]["first_matching_threshold_px"] is None
    csv_text = (run_dir / "threshold-sweep.csv").read_text(encoding="utf-8")
    assert "page.png#1,27.0,40.0,40.0,true,,false,false,0,no_ctd_mask_within_threshold,true,true,2,,true,true,3," in csv_text
    report = (run_dir / "reports" / "phase2-threshold-sweep-report.md").read_text(encoding="utf-8")
    assert "Thresholds: `20.0`, `40.0`, `80.0`" in report
    assert "This sweep is diagnostic" in report
    assert "`page.png#1` first canonical claim at `40.0px`" in report


def test_run_phase2_threshold_sweep_replays_unique_component_claims(tmp_path: Path):
    phase2_run = tmp_path / "phase2"
    page_dir = phase2_run / "debug" / "ctd_masks" / "page"
    page_dir.mkdir(parents=True)
    _write_jsonl(
        phase2_run / "detections.jsonl",
        [
            {"record_id": "page.png#1", "image_name": "page.png", "status": "fallback_required"},
            {"record_id": "page.png#2", "image_name": "page.png", "status": "fallback_required"},
        ],
    )
    _write_jsonl(
        page_dir / "ctd-mask-edge-distances.jsonl",
        [
            _distance_row("page.png#1", "component-0001", 2.0, label_point=[38, 80]),
            _distance_row("page.png#2", "component-0001", 4.0, label_point=[42, 84]),
        ],
    )

    run_dir = run_phase2_threshold_sweep(
        phase2_run_dir=phase2_run,
        output_root=tmp_path / "outputs",
        run_id="sweep",
        thresholds=[8],
    )

    payload = json.loads((run_dir / "threshold-sweep.json").read_text(encoding="utf-8"))
    assert payload["summary"]["distance_coverage_counts"] == {"8.0": 2}
    assert payload["summary"]["canonical_match_counts"] == {"8.0": 1}
    records = {record["record_id"]: record for record in payload["records"]}
    assert records["page.png#1"]["thresholds"][0]["canonical_claim_status"] == "matched"
    assert records["page.png#2"]["thresholds"][0]["canonical_claim_status"] == "fallback_required"
    assert records["page.png#2"]["thresholds"][0]["canonical_failure_reason"] == "component_already_claimed"


def _distance_row(
    record_id: str,
    component_id: str,
    distance: float,
    label_point: list[int] | None = None,
    bbox: list[int] | None = None,
) -> dict:
    return {
        "record_id": record_id,
        "labelplus_point_xy": label_point or [1, 2],
        "component_id": component_id,
        "component_bbox_xyxy": bbox or [40, 30, 101, 121],
        "component_mask_path": f"{component_id}.png",
        "edge_distance_px": distance,
        "within_threshold": False,
        "threshold_px": 20.0,
    }


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
