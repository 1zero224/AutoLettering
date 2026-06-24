import json
from pathlib import Path

from experiments import pipeline_coverage_report
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


def test_build_pipeline_coverage_merges_multiple_detection_runs(tmp_path: Path):
    phase1 = tmp_path / "phase1"
    phase2a = tmp_path / "phase2a"
    phase2b = tmp_path / "phase2b"
    phase3 = tmp_path / "phase3"
    _write_phase1_manifest(phase1 / "manifest.json")
    _write_jsonl(phase2a / "detections.jsonl", [_row("r1", "ok")])
    _write_jsonl(phase2b / "detections.jsonl", [_row("r2", "ok")])
    _write_jsonl(phase3 / "font-selections.jsonl", [_row("r1", "selected"), _row("r2", "selected")])

    report = build_pipeline_coverage(
        phase1_run_dir=phase1,
        detection_run_dir=[phase2a, phase2b],
        font_selection_run_dir=phase3,
        next_limit=3,
    )

    assert report["summary"]["base_stage"] == "phase2_detection"
    assert report["summary"]["base_record_count"] == 2
    assert report["stages"]["phase2_detection"]["covered_record_ids"] == ["r1", "r2"]
    assert report["stages"]["phase3_font_selection"]["covered_record_ids"] == ["r1", "r2"]
    assert report["group_summary"]["框内"]["base_count"] == 1
    assert report["group_summary"]["框外"]["base_count"] == 1
    assert report["phase1_pending_detection_count"] == 1
    assert report["phase1_pending_detection_records"] == [
        {"record_id": "r3", "group_name": "框内", "image_name": "page2.png"}
    ]


def test_build_pipeline_coverage_reports_phase1_records_missing_detection(tmp_path: Path):
    phase1 = tmp_path / "phase1"
    phase2 = tmp_path / "phase2"
    _write_phase1_manifest(phase1 / "manifest.json")
    _write_jsonl(phase2 / "detections.jsonl", [_row("r1", "ok")])

    report = build_pipeline_coverage(
        phase1_run_dir=phase1,
        detection_run_dir=phase2,
        next_limit=2,
    )

    assert report["summary"]["base_stage"] == "phase2_detection"
    assert report["summary"]["base_record_count"] == 1
    assert report["phase1_pending_detection_count"] == 2
    assert report["phase1_pending_detection_records"] == [
        {"record_id": "r2", "group_name": "框外", "image_name": "page1.png"},
        {"record_id": "r3", "group_name": "框内", "image_name": "page2.png"},
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
    assert "## Phase 1 Pending Detection" in markdown
    assert "`r2`" in markdown


def test_pipeline_coverage_cli_accepts_multiple_detection_runs(tmp_path: Path, monkeypatch, capsys):
    phase1 = tmp_path / "phase1"
    phase2a = tmp_path / "phase2a"
    phase2b = tmp_path / "phase2b"
    output_root = tmp_path / "outputs"
    _write_phase1_manifest(phase1 / "manifest.json")
    _write_jsonl(phase2a / "detections.jsonl", [_row("r1", "ok")])
    _write_jsonl(phase2b / "detections.jsonl", [_row("r2", "ok")])

    monkeypatch.setattr(
        "sys.argv",
        [
            "pipeline_coverage_report.py",
            "--phase1-run-dir",
            str(phase1),
            "--detection-run-dir",
            str(phase2a),
            "--detection-run-dir",
            str(phase2b),
            "--output-root",
            str(output_root),
            "--run-id",
            "cli-coverage",
        ],
    )

    pipeline_coverage_report.main()

    captured = capsys.readouterr()
    assert "cli-coverage" in captured.out
    payload = json.loads((output_root / "cli-coverage" / "pipeline-coverage.json").read_text(encoding="utf-8"))
    assert payload["summary"]["base_record_count"] == 2
    assert payload["stages"]["phase2_detection"]["covered_record_ids"] == ["r1", "r2"]


def test_pipeline_coverage_cli_accepts_phase6_cleanup_quality_run(tmp_path: Path, monkeypatch, capsys):
    phase1 = tmp_path / "phase1"
    phase2 = tmp_path / "phase2"
    cleanup_quality = tmp_path / "phase6-cleanup-quality"
    output_root = tmp_path / "outputs"
    _write_phase1_manifest(phase1 / "manifest.json")
    _write_jsonl(phase2 / "detections.jsonl", [_row("r1", "ok")])
    _write_jsonl(
        cleanup_quality / "cleanup-quality.jsonl",
        [
            {
                "record_id": "r1",
                "status": "evaluated",
                "usable": False,
                "original_text_removed": False,
                "art_preserved": True,
            }
        ],
    )

    monkeypatch.setattr(
        "sys.argv",
        [
            "pipeline_coverage_report.py",
            "--phase1-run-dir",
            str(phase1),
            "--detection-run-dir",
            str(phase2),
            "--phase6-cleanup-quality-run-dir",
            str(cleanup_quality),
            "--output-root",
            str(output_root),
            "--run-id",
            "cli-cleanup-quality",
        ],
    )

    pipeline_coverage_report.main()

    captured = capsys.readouterr()
    assert "cli-cleanup-quality" in captured.out
    payload = json.loads((output_root / "cli-cleanup-quality" / "pipeline-coverage.json").read_text(encoding="utf-8"))
    assert payload["quality"]["phase6_cleanup"]["evaluation_count"] == 1
    assert payload["records"]["r1"]["quality_issues"] == ["phase6_cleanup_original_text_visible"]


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
            {"image_name": "page1.png", "labels": [{"id": "r1", "group_name": "框内"}, {"id": "r2", "group_name": "框外"}]},
            {"image_name": "page2.png", "labels": [{"id": "r3", "group_name": "框内"}]},
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
