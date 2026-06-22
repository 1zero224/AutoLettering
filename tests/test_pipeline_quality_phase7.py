import json
from pathlib import Path

from autolettering.pipeline_coverage import build_pipeline_coverage, write_pipeline_coverage_report


def test_build_pipeline_coverage_marks_phase7_preview_evaluation_failures_incomplete(tmp_path: Path):
    phase1 = tmp_path / "phase1"
    phase2 = tmp_path / "phase2"
    phase3 = tmp_path / "phase3"
    phase4 = tmp_path / "phase4"
    phase5 = tmp_path / "phase5"
    phase6 = tmp_path / "phase6"
    phase7 = tmp_path / "phase7"
    phase8 = tmp_path / "phase8"
    phase7_evaluation = tmp_path / "phase7-evaluation"
    _write_phase1_manifest(phase1 / "manifest.json")
    _write_jsonl(phase2 / "detections.jsonl", [_row("r1", "ok")])
    _write_jsonl(phase3 / "font-selections.jsonl", [_row("r1", "selected")])
    _write_jsonl(phase4 / "layout-results.jsonl", [_row("r1", "layout_generated")])
    _write_jsonl(phase5 / "angle-results.jsonl", [_row("r1", "angle_estimated")])
    _write_jsonl(phase6 / "cleanup-results.jsonl", [_cleanup_row("r1", "bubble_region_fill")])
    _write_phase7_preview(phase7 / "preview-results.jsonl", ["r1"])
    _write_phase8_manifest(phase8 / "photoshop-manifest.json", ["r1"])
    _write_phase7_preview_evaluation(
        phase7_evaluation / "preview-evaluation.jsonl",
        score=5,
        usable=False,
        record_ids=["r1"],
    )

    report = build_pipeline_coverage(
        phase1_run_dir=phase1,
        detection_run_dir=phase2,
        font_selection_run_dir=phase3,
        layout_run_dir=phase4,
        angle_run_dir=phase5,
        cleanup_run_dirs=[phase6],
        preview_run_dir=phase7,
        export_run_dir=phase8,
        phase7_preview_evaluation_run_dir=phase7_evaluation,
    )

    quality = report["quality"]["phase7_preview"]
    assert quality["evaluation_count"] == 1
    assert quality["evaluated_count"] == 1
    assert quality["usable_count"] == 0
    assert quality["low_score_count"] == 1
    assert quality["failed_count"] == 0
    assert quality["record_count"] == 1
    assert quality["record_issue_count"] == 2
    assert report["summary"]["complete_record_count"] == 0
    assert report["records"]["r1"]["missing_stages"] == []
    assert report["records"]["r1"]["quality_issues"] == ["phase7_unusable", "phase7_low_score"]
    assert report["next_records"] == [
        {"record_id": "r1", "group_name": "框内", "first_quality_issue": "phase7_unusable"}
    ]


def test_build_pipeline_coverage_marks_failed_phase7_preview_evaluation_per_record(tmp_path: Path):
    phase1 = tmp_path / "phase1"
    phase2 = tmp_path / "phase2"
    phase7_evaluation = tmp_path / "phase7-evaluation"
    _write_phase1_manifest(phase1 / "manifest.json")
    _write_jsonl(phase2 / "detections.jsonl", [_row("r1", "ok")])
    _write_phase7_preview_evaluation(
        phase7_evaluation / "preview-evaluation.jsonl",
        status="failed",
        score=None,
        usable=None,
        failure_reason="api_error:TimeoutError",
        record_ids=["r1"],
    )

    report = build_pipeline_coverage(
        phase1_run_dir=phase1,
        detection_run_dir=phase2,
        phase7_preview_evaluation_run_dir=phase7_evaluation,
    )

    assert report["quality"]["phase7_preview"]["failed_count"] == 1
    assert report["records"]["r1"]["quality_issues"] == ["phase7_evaluation_failed"]


def test_write_pipeline_coverage_report_includes_phase7_quality_section(tmp_path: Path):
    phase1 = tmp_path / "phase1"
    phase2 = tmp_path / "phase2"
    phase7_evaluation = tmp_path / "phase7-evaluation"
    _write_phase1_manifest(phase1 / "manifest.json")
    _write_jsonl(phase2 / "detections.jsonl", [_row("r1", "ok")])
    _write_phase7_preview_evaluation(
        phase7_evaluation / "preview-evaluation.jsonl",
        score=9,
        usable=True,
        record_ids=["r1"],
    )

    run_dir = write_pipeline_coverage_report(
        output_root=tmp_path / "outputs",
        run_id="coverage-phase7-quality-test",
        phase1_run_dir=phase1,
        detection_run_dir=phase2,
        phase7_preview_evaluation_run_dir=phase7_evaluation,
    )

    markdown = (run_dir / "reports" / "pipeline-coverage-report.md").read_text(encoding="utf-8")
    assert "### phase7_preview" in markdown
    assert "Preview evaluations: 1" in markdown
    assert "Usable previews: 1/1" in markdown
    assert "Low-score previews: 0" in markdown


def _row(record_id: str, status: str) -> dict:
    return {"record_id": record_id, "status": status}


def _cleanup_row(record_id: str, method: str) -> dict:
    return {"record_id": record_id, "status": "cleaned", "cleanup": {"method": method}}


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def _write_phase1_manifest(path: Path) -> None:
    payload = {
        "images": [
            {"labels": [{"id": "r1", "group_name": "框内"}, {"id": "r2", "group_name": "框外"}]},
            {"labels": [{"id": "r3", "group_name": "框内"}]},
        ]
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _write_phase7_preview(path: Path, record_ids: list[str] | None = None) -> None:
    rows = [{"status": "page_preview_generated", "records": [{"record_id": record_id} for record_id in record_ids or ["r1"]]}]
    _write_jsonl(path, rows)


def _write_phase7_preview_evaluation(
    path: Path,
    status: str = "evaluated",
    score: int | None = 9,
    usable: bool | None = True,
    failure_reason: str | None = None,
    record_ids: list[str] | None = None,
) -> None:
    rows = [
        {
            "image_name": "page.png",
            "status": status,
            "score": score,
            "usable": usable,
            "original_text_removed": True if status == "evaluated" else None,
            "art_preserved": True if status == "evaluated" else None,
            "lettering_readable": True if status == "evaluated" else None,
            "issues": [],
            "failure_reason": failure_reason,
            "records": [{"record_id": record_id} for record_id in record_ids or ["r1"]],
        }
    ]
    _write_jsonl(path, rows)


def _write_phase8_manifest(path: Path, record_ids: list[str] | None = None) -> None:
    payload = {"pages": [{"layers": [{"record_id": record_id} for record_id in record_ids or ["r1", "r2"]]}]}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
