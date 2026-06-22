from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path


RunDirInput = str | Path | Iterable[str | Path] | None
PHASE7_MIN_USABLE_SCORE = 7


def build_quality_summary(
    phase7_preview_evaluation_run_dir: RunDirInput,
    phase8_export_audit_run_dir: RunDirInput,
) -> dict[str, dict]:
    return {
        "phase7_preview": _phase7_preview_quality_summary(phase7_preview_evaluation_run_dir),
        "phase8_export": _phase8_export_quality_summary(phase8_export_audit_run_dir),
    }


def quality_issues_by_record(quality: dict) -> dict[str, list[str]]:
    issues: dict[str, list[str]] = {}
    _merge_record_issues(issues, _phase7_preview_issues(quality.get("phase7_preview", {})))
    phase8 = quality.get("phase8_export", {})
    global_issues = ["missing_jsx_anchor_logic"] if phase8.get("jsx_anchor_logic_missing_count") else []
    for record in phase8.get("records", []):
        record_id = record.get("record_id")
        record_issues = [*global_issues, *(record.get("issues") or [])]
        if record_id and record_issues:
            _merge_record_issues(issues, {str(record_id): [str(issue) for issue in record_issues]})
    return issues


def quality_markdown_lines(quality: dict) -> list[str]:
    phase7 = quality.get("phase7_preview", {})
    phase8 = quality.get("phase8_export", {})
    if not _has_phase7_quality(phase7) and not _has_phase8_quality(phase8):
        return ["", "## Quality Audits", "", "- None"]
    lines = ["", "## Quality Audits"]
    if _has_phase7_quality(phase7):
        lines.extend([
            "",
            "### phase7_preview",
            "",
            f"- Preview evaluations: {phase7['evaluation_count']}",
            f"- Usable previews: {phase7['usable_count']}/{phase7['evaluated_count']}",
            f"- Failed evaluations: {phase7['failed_count']}",
            f"- Low-score previews: {phase7['low_score_count']}",
            f"- Records evaluated: {phase7['record_count']}",
            f"- Record issues: {phase7['record_issue_count']}",
        ])
    if _has_phase8_quality(phase8):
        lines.extend([
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
        ])
    return lines


def _phase7_preview_quality_summary(run_dir: RunDirInput) -> dict:
    rows = _phase7_preview_rows(run_dir)
    records = _phase7_preview_records(rows)
    return {
        "evaluation_count": len(rows),
        "evaluated_count": sum(1 for row in rows if row.get("status") == "evaluated"),
        "usable_count": sum(1 for row in rows if row.get("status") == "evaluated" and row.get("usable") is True),
        "failed_count": sum(1 for row in rows if row.get("status") != "evaluated"),
        "low_score_count": sum(1 for row in rows if _is_low_phase7_score(row)),
        "record_count": len(records),
        "record_issue_count": sum(len(record.get("issues") or []) for record in records),
        "records": records,
    }


def _phase7_preview_rows(run_dir: RunDirInput) -> list[dict]:
    rows: list[dict] = []
    for item in _run_dirs(run_dir):
        path = Path(item) / "preview-evaluation.jsonl"
        if path.exists():
            rows.extend(json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    return rows


def _phase7_preview_records(rows: list[dict]) -> list[dict]:
    by_record: dict[str, dict] = {}
    for row in rows:
        row_issues = _phase7_preview_row_issues(row)
        for record in row.get("records", []):
            record_id = record.get("record_id")
            if not record_id:
                continue
            by_record[str(record_id)] = {
                "record_id": str(record_id),
                "image_name": row.get("image_name"),
                "score": row.get("score"),
                "usable": row.get("usable"),
                "status": row.get("status"),
                "failure_reason": row.get("failure_reason"),
                "issues": row_issues,
            }
    return list(by_record.values())


def _phase7_preview_row_issues(row: dict) -> list[str]:
    if row.get("status") != "evaluated":
        return ["phase7_evaluation_failed"]
    issues: list[str] = []
    if row.get("usable") is not True:
        issues.append("phase7_unusable")
    if _is_low_phase7_score(row):
        issues.append("phase7_low_score")
    return issues


def _phase7_preview_issues(phase7: dict) -> dict[str, list[str]]:
    return {
        str(record["record_id"]): [str(issue) for issue in record.get("issues", [])]
        for record in phase7.get("records", [])
        if record.get("record_id") and record.get("issues")
    }


def _is_low_phase7_score(row: dict) -> bool:
    score = row.get("score")
    return isinstance(score, int | float) and score < PHASE7_MIN_USABLE_SCORE


def _merge_record_issues(target: dict[str, list[str]], source: dict[str, list[str]]) -> None:
    for record_id, record_issues in source.items():
        current = target.setdefault(record_id, [])
        for issue in record_issues:
            if issue not in current:
                current.append(issue)


def _has_phase7_quality(phase7: dict) -> bool:
    return bool(phase7 and phase7.get("evaluation_count"))


def _has_phase8_quality(phase8: dict) -> bool:
    return bool(phase8 and phase8.get("audit_count"))


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
