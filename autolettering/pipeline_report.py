from __future__ import annotations

from .pipeline_quality import quality_markdown_lines


def pipeline_markdown_lines(report: dict, stage_order: list[str]) -> list[str]:
    lines = ["# Pipeline Coverage Report", "", "## Summary", ""]
    summary = report["summary"]
    lines.extend([
        f"- Base stage: `{summary['base_stage']}`",
        f"- Base records: {summary['base_record_count']}",
        f"- Complete records: {summary['complete_record_count']}",
        f"- Incomplete records: {summary['incomplete_record_count']}",
        "",
        "## Stages",
        "",
        "| Stage | Covered | Missing |",
        "| --- | ---: | ---: |",
    ])
    for name in stage_order:
        stage = report["stages"][name]
        lines.append(f"| `{name}` | {stage['covered_count']} | {stage['missing_count']} |")
    lines.extend(quality_markdown_lines(report.get("quality", {})))
    lines.extend(["", "## Next Records", ""])
    lines.extend(_next_record_lines(report["next_records"]))
    return lines


def _next_record_lines(records: list[dict]) -> list[str]:
    if not records:
        return ["- None"]
    return [_next_record_line(row) for row in records]


def _next_record_line(row: dict) -> str:
    label = row.get("first_missing_stage") or row.get("first_quality_issue")
    return f"- `{row['record_id']}` ({row.get('group_name') or 'unknown'}): `{label}`"
