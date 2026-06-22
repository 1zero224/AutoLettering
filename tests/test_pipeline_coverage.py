import json
from pathlib import Path

from autolettering.pipeline_coverage import build_pipeline_coverage, write_pipeline_coverage_report


def test_build_pipeline_coverage_reports_stage_gaps_and_next_records(tmp_path: Path):
    phase1 = tmp_path / "phase1"
    phase2 = tmp_path / "phase2"
    phase3 = tmp_path / "phase3"
    phase4 = tmp_path / "phase4"
    phase5 = tmp_path / "phase5"
    phase6a = tmp_path / "phase6a"
    phase6b = tmp_path / "phase6b"
    phase7 = tmp_path / "phase7"
    phase8 = tmp_path / "phase8"
    _write_phase1_manifest(phase1 / "manifest.json")
    _write_jsonl(phase2 / "detections.jsonl", [_row("r1", "ok"), _row("r2", "ok"), _row("r3", "failed")])
    _write_jsonl(phase3 / "font-selections.jsonl", [_row("r1", "selected"), _row("r2", "failed")])
    _write_jsonl(phase4 / "layout-results.jsonl", [_row("r1", "layout_generated")])
    _write_jsonl(phase5 / "angle-results.jsonl", [_row("r1", "angle_estimated"), _row("r2", "angle_estimated")])
    _write_jsonl(phase6a / "cleanup-results.jsonl", [_cleanup_row("r1", "bubble_region_fill")])
    _write_jsonl(phase6b / "cleanup-results.jsonl", [_cleanup_row("r2", "bt_lama_large_inpaint")])
    _write_phase7_preview(phase7 / "preview-results.jsonl")
    _write_phase8_manifest(phase8 / "photoshop-manifest.json")

    report = build_pipeline_coverage(
        phase1_run_dir=phase1,
        detection_run_dir=phase2,
        font_selection_run_dir=phase3,
        layout_run_dir=phase4,
        angle_run_dir=phase5,
        cleanup_run_dirs=[phase6a, phase6b],
        preview_run_dir=phase7,
        export_run_dir=phase8,
        next_limit=3,
    )

    assert report["summary"]["base_stage"] == "phase2_detection"
    assert report["summary"]["base_record_count"] == 3
    assert report["stages"]["phase4_layout"]["covered_count"] == 1
    assert report["stages"]["phase6_cleanup"]["covered_record_ids"] == ["r1", "r2"]
    assert report["group_summary"]["框内"]["base_count"] == 2
    assert report["group_summary"]["框外"]["base_count"] == 1
    assert report["records"]["r2"]["missing_stages"] == ["phase3_font_selection", "phase4_layout", "phase7_preview"]
    assert report["records"]["r3"]["missing_stages"][0] == "phase2_detection"
    assert report["next_records"] == [
        {"record_id": "r2", "group_name": "框外", "first_missing_stage": "phase3_font_selection"},
        {"record_id": "r3", "group_name": "框内", "first_missing_stage": "phase2_detection"},
    ]


def test_build_pipeline_coverage_merges_multiple_runs_per_stage(tmp_path: Path):
    phase1 = tmp_path / "phase1"
    phase2 = tmp_path / "phase2"
    phase3a = tmp_path / "phase3a"
    phase3b = tmp_path / "phase3b"
    phase4a = tmp_path / "phase4a"
    phase4b = tmp_path / "phase4b"
    phase5a = tmp_path / "phase5a"
    phase5b = tmp_path / "phase5b"
    phase6a = tmp_path / "phase6a"
    phase6b = tmp_path / "phase6b"
    phase7a = tmp_path / "phase7a"
    phase7b = tmp_path / "phase7b"
    phase8a = tmp_path / "phase8a"
    phase8b = tmp_path / "phase8b"
    _write_phase1_manifest(phase1 / "manifest.json")
    _write_jsonl(phase2 / "detections.jsonl", [_row("r1", "ok"), _row("r2", "ok"), _row("r3", "ok")])
    _write_jsonl(phase3a / "font-selections.jsonl", [_row("r1", "selected")])
    _write_jsonl(phase3b / "font-selections.jsonl", [_row("r2", "selected")])
    _write_jsonl(phase4a / "layout-results.jsonl", [_row("r1", "layout_generated")])
    _write_jsonl(phase4b / "layout-results.jsonl", [_row("r2", "layout_generated")])
    _write_jsonl(phase5a / "angle-results.jsonl", [_row("r1", "angle_estimated")])
    _write_jsonl(phase5b / "angle-results.jsonl", [_row("r2", "angle_estimated")])
    _write_jsonl(phase6a / "cleanup-results.jsonl", [_cleanup_row("r1", "bubble_region_fill")])
    _write_jsonl(phase6b / "cleanup-results.jsonl", [_cleanup_row("r2", "bubble_region_fill")])
    _write_phase7_preview(phase7a / "preview-results.jsonl", ["r1"])
    _write_phase7_preview(phase7b / "preview-results.jsonl", ["r2"])
    _write_phase8_manifest(phase8a / "photoshop-manifest.json", ["r1"])
    _write_phase8_manifest(phase8b / "photoshop-manifest.json", ["r2"])

    report = build_pipeline_coverage(
        phase1_run_dir=phase1,
        detection_run_dir=phase2,
        font_selection_run_dir=[phase3a, phase3b],
        layout_run_dir=[phase4a, phase4b],
        angle_run_dir=[phase5a, phase5b],
        cleanup_run_dirs=[phase6a, phase6b],
        preview_run_dir=[phase7a, phase7b],
        export_run_dir=[phase8a, phase8b],
        next_limit=3,
    )

    assert report["summary"]["complete_record_count"] == 2
    assert report["summary"]["incomplete_record_count"] == 1
    assert report["stages"]["phase3_font_selection"]["covered_record_ids"] == ["r1", "r2"]
    assert report["stages"]["phase4_layout"]["covered_record_ids"] == ["r1", "r2"]
    assert report["stages"]["phase7_preview"]["covered_record_ids"] == ["r1", "r2"]
    assert report["stages"]["phase8_export"]["covered_record_ids"] == ["r1", "r2"]
    assert report["next_records"] == [
        {"record_id": "r3", "group_name": "框内", "first_missing_stage": "phase3_font_selection"}
    ]


def test_write_pipeline_coverage_report_writes_json_and_markdown(tmp_path: Path):
    phase1 = tmp_path / "phase1"
    phase2 = tmp_path / "phase2"
    _write_phase1_manifest(phase1 / "manifest.json")
    _write_jsonl(phase2 / "detections.jsonl", [_row("r1", "ok")])

    run_dir = write_pipeline_coverage_report(
        output_root=tmp_path / "outputs",
        run_id="coverage-test",
        phase1_run_dir=phase1,
        detection_run_dir=phase2,
    )

    payload = json.loads((run_dir / "pipeline-coverage.json").read_text(encoding="utf-8"))
    markdown = (run_dir / "reports" / "pipeline-coverage-report.md").read_text(encoding="utf-8")
    assert payload["summary"]["base_record_count"] == 1
    assert "phase2_detection" in markdown


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
