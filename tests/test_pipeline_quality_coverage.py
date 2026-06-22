import json
from pathlib import Path

from autolettering.pipeline_coverage import build_pipeline_coverage, write_pipeline_coverage_report


def test_build_pipeline_coverage_includes_phase8_export_quality_audit(tmp_path: Path):
    phase1 = tmp_path / "phase1"
    phase2 = tmp_path / "phase2"
    phase8_audit = tmp_path / "phase8-audit"
    _write_phase1_manifest(phase1 / "manifest.json")
    _write_jsonl(phase2 / "detections.jsonl", [_row("r1", "ok")])
    _write_phase8_export_audit(phase8_audit / "phase8-export-audit.json")

    report = build_pipeline_coverage(
        phase1_run_dir=phase1,
        detection_run_dir=phase2,
        phase8_export_audit_run_dir=phase8_audit,
    )

    quality = report["quality"]["phase8_export"]
    assert {
        key: quality[key]
        for key in [
            "audit_count",
            "passed_count",
            "record_count",
            "vertical_top_layer_count",
            "missing_vertical_top_anchor_count",
            "unexpected_vertical_top_anchor_count",
            "record_issue_count",
            "jsx_anchor_logic_missing_count",
        ]
    } == {
        "audit_count": 1,
        "passed_count": 1,
        "record_count": 1,
        "vertical_top_layer_count": 1,
        "missing_vertical_top_anchor_count": 0,
        "unexpected_vertical_top_anchor_count": 0,
        "record_issue_count": 0,
        "jsx_anchor_logic_missing_count": 0,
    }
    assert quality["records"][0]["record_id"] == "r1"
    assert report["records"]["r1"]["quality_issues"] == []


def test_build_pipeline_coverage_marks_phase8_quality_failures_incomplete(tmp_path: Path):
    phase1 = tmp_path / "phase1"
    phase2 = tmp_path / "phase2"
    phase8 = tmp_path / "phase8"
    phase8_audit = tmp_path / "phase8-audit"
    _write_phase1_manifest(phase1 / "manifest.json")
    _write_jsonl(phase2 / "detections.jsonl", [_row("r1", "ok")])
    _write_phase8_manifest(phase8 / "photoshop-manifest.json", ["r1"])
    _write_phase8_export_audit(
        phase8_audit / "phase8-export-audit.json",
        passed=False,
        issues=["missing_vertical_top_anchor_y_px"],
    )

    report = build_pipeline_coverage(
        phase1_run_dir=phase1,
        detection_run_dir=phase2,
        export_run_dir=phase8,
        phase8_export_audit_run_dir=phase8_audit,
    )

    assert report["summary"]["complete_record_count"] == 0
    assert report["summary"]["incomplete_record_count"] == 1
    assert report["records"]["r1"]["missing_stages"] == []
    assert report["records"]["r1"]["quality_issues"] == ["missing_vertical_top_anchor_y_px"]
    assert report["next_records"] == [
        {"record_id": "r1", "group_name": "框内", "first_quality_issue": "missing_vertical_top_anchor_y_px"}
    ]


def test_build_pipeline_coverage_deduplicates_phase8_quality_records(tmp_path: Path):
    phase1 = tmp_path / "phase1"
    phase2 = tmp_path / "phase2"
    audit_a = tmp_path / "audit-a"
    audit_b = tmp_path / "audit-b"
    _write_phase1_manifest(phase1 / "manifest.json")
    _write_jsonl(phase2 / "detections.jsonl", [_row("r1", "ok")])
    _write_phase8_export_audit(audit_a / "phase8-export-audit.json")
    _write_phase8_export_audit(audit_b / "phase8-export-audit.json")

    report = build_pipeline_coverage(
        phase1_run_dir=phase1,
        detection_run_dir=phase2,
        phase8_export_audit_run_dir=[audit_a, audit_b],
    )

    quality = report["quality"]["phase8_export"]
    assert quality["audit_count"] == 2
    assert quality["passed_count"] == 2
    assert quality["record_count"] == 1
    assert quality["vertical_top_layer_count"] == 1


def test_build_pipeline_coverage_marks_missing_jsx_anchor_logic_as_quality_issue(tmp_path: Path):
    phase1 = tmp_path / "phase1"
    phase2 = tmp_path / "phase2"
    phase8 = tmp_path / "phase8"
    phase8_audit = tmp_path / "phase8-audit"
    _write_phase1_manifest(phase1 / "manifest.json")
    _write_jsonl(phase2 / "detections.jsonl", [_row("r1", "ok")])
    _write_phase8_manifest(phase8 / "photoshop-manifest.json", ["r1"])
    _write_phase8_export_audit(phase8_audit / "phase8-export-audit.json", jsx_anchor_logic_present=False)

    report = build_pipeline_coverage(
        phase1_run_dir=phase1,
        detection_run_dir=phase2,
        export_run_dir=phase8,
        phase8_export_audit_run_dir=phase8_audit,
    )

    assert report["summary"]["complete_record_count"] == 0
    assert report["records"]["r1"]["quality_issues"] == ["missing_jsx_anchor_logic"]
    assert report["next_records"][0]["first_quality_issue"] == "missing_jsx_anchor_logic"


def test_write_pipeline_coverage_report_includes_quality_section(tmp_path: Path):
    phase1 = tmp_path / "phase1"
    phase2 = tmp_path / "phase2"
    phase8_audit = tmp_path / "phase8-audit"
    _write_phase1_manifest(phase1 / "manifest.json")
    _write_jsonl(phase2 / "detections.jsonl", [_row("r1", "ok")])
    _write_phase8_export_audit(phase8_audit / "phase8-export-audit.json")

    run_dir = write_pipeline_coverage_report(
        output_root=tmp_path / "outputs",
        run_id="coverage-quality-test",
        phase1_run_dir=phase1,
        detection_run_dir=phase2,
        phase8_export_audit_run_dir=phase8_audit,
    )

    markdown = (run_dir / "reports" / "pipeline-coverage-report.md").read_text(encoding="utf-8")
    assert "## Quality Audits" in markdown
    assert "phase8_export" in markdown
    assert "Passed audits: 1/1" in markdown
    assert "Records audited: 1" in markdown
    assert "Record issues: 0" in markdown
    assert "Missing JSX anchor logic audits: 0" in markdown


def _row(record_id: str, status: str) -> dict:
    return {"record_id": record_id, "status": status}


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


def _write_phase8_manifest(path: Path, record_ids: list[str] | None = None) -> None:
    payload = {"pages": [{"layers": [{"record_id": record_id} for record_id in record_ids or ["r1", "r2"]]}]}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_phase8_export_audit(
    path: Path,
    passed: bool = True,
    issues: list[str] | None = None,
    jsx_anchor_logic_present: bool = True,
) -> None:
    record_issues = issues or []
    payload = {
        "summary": {
            "record_count": 1,
            "vertical_top_layer_count": 1,
            "missing_vertical_top_anchor_count": int("missing_vertical_top_anchor_y_px" in record_issues),
            "unexpected_vertical_top_anchor_count": 0,
            "record_issue_count": len(record_issues),
            "jsx_anchor_logic_present": jsx_anchor_logic_present,
            "passed": passed and jsx_anchor_logic_present,
        },
        "records": [
            {
                "record_id": "r1",
                "orientation": "vertical",
                "vertical_align": "top",
                "expected_vertical_top_anchor": True,
                "issues": record_issues,
            }
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
