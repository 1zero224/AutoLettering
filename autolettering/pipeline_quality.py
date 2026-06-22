from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path


RunDirInput = str | Path | Iterable[str | Path] | None


def build_quality_summary(phase8_export_audit_run_dir: RunDirInput) -> dict[str, dict]:
    return {"phase8_export": _phase8_export_quality_summary(phase8_export_audit_run_dir)}


def quality_issues_by_record(quality: dict) -> dict[str, list[str]]:
    issues: dict[str, list[str]] = {}
    phase8 = quality.get("phase8_export", {})
    global_issues = ["missing_jsx_anchor_logic"] if phase8.get("jsx_anchor_logic_missing_count") else []
    for record in phase8.get("records", []):
        record_id = record.get("record_id")
        record_issues = [*global_issues, *(record.get("issues") or [])]
        if record_id and record_issues:
            issues[str(record_id)] = [str(issue) for issue in record_issues]
    return issues


def quality_markdown_lines(quality: dict) -> list[str]:
    phase8 = quality.get("phase8_export", {})
    if not phase8 or not phase8.get("audit_count"):
        return ["", "## Quality Audits", "", "- None"]
    return [
        "",
        "## Quality Audits",
        "",
        "### phase8_export",
        "",
        f"- Passed audits: {phase8['passed_count']}/{phase8['audit_count']}",
        f"- Records audited: {phase8['record_count']}",
        f"- Vertical top layers audited: {phase8['vertical_top_layer_count']}",
        f"- Missing vertical top anchors: {phase8['missing_vertical_top_anchor_count']}",
        f"- Unexpected vertical top anchors: {phase8['unexpected_vertical_top_anchor_count']}",
        f"- Record issues: {phase8['record_issue_count']}",
        f"- Missing JSX anchor logic audits: {phase8['jsx_anchor_logic_missing_count']}",
    ]


def _phase8_export_quality_summary(run_dir: RunDirInput) -> dict:
    audits = _phase8_export_audits(run_dir)
    summaries = [audit.get("summary", {}) for audit in audits]
    records = _phase8_export_records(audits)
    return {
        "audit_count": len(summaries),
        "passed_count": sum(1 for summary in summaries if summary.get("passed") is True),
        "record_count": len(records),
        "vertical_top_layer_count": sum(1 for record in records if record.get("expected_vertical_top_anchor")),
        "missing_vertical_top_anchor_count": _count_record_issue(records, "missing_vertical_top_anchor_y_px"),
        "unexpected_vertical_top_anchor_count": _count_record_issue(records, "unexpected_vertical_top_anchor_y_px"),
        "record_issue_count": sum(len(record.get("issues") or []) for record in records),
        "jsx_anchor_logic_missing_count": sum(1 for summary in summaries if summary.get("jsx_anchor_logic_present") is False),
        "records": records,
    }


def _phase8_export_audits(run_dir: RunDirInput) -> list[dict]:
    audits: list[dict] = []
    for item in _run_dirs(run_dir):
        path = Path(item) / "phase8-export-audit.json"
        if path.exists():
            audits.append(json.loads(path.read_text(encoding="utf-8")))
    return audits


def _phase8_export_records(audits: list[dict]) -> list[dict]:
    by_record: dict[str, dict] = {}
    anonymous: list[dict] = []
    for audit in audits:
        for record in audit.get("records", []):
            record_id = record.get("record_id")
            if record_id:
                by_record[str(record_id)] = record
            else:
                anonymous.append(record)
    return list(by_record.values()) + anonymous


def _count_record_issue(records: list[dict], issue: str) -> int:
    return sum(1 for record in records if issue in (record.get("issues") or []))


def _run_dirs(run_dir: RunDirInput) -> list[str | Path]:
    if run_dir is None:
        return []
    if isinstance(run_dir, str | Path):
        return [run_dir]
    return list(run_dir)
