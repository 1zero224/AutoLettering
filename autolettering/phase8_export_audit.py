from __future__ import annotations

import json
from pathlib import Path


def audit_phase8_export(phase8_run_dir: str | Path) -> dict:
    run_dir = Path(phase8_run_dir)
    manifest = _read_json(run_dir / "photoshop-manifest.json")
    jsx_source = _read_text(run_dir / "photoshop-import.jsx")
    records = [_audit_layer(layer) for page in manifest.get("pages", []) for layer in page.get("layers", [])]
    summary = _summary(records, jsx_source)
    return {
        "phase8_run_dir": str(run_dir),
        "summary": summary,
        "records": records,
    }


def write_phase8_export_audit(
    phase8_run_dir: str | Path,
    output_root: str | Path = "outputs/runs",
    run_id: str | None = None,
) -> Path:
    output_dir = Path(output_root) / (run_id or "phase8-export-quality-audit")
    output_dir.mkdir(parents=True, exist_ok=True)
    report = audit_phase8_export(phase8_run_dir)
    _write_json(output_dir / "phase8-export-audit.json", report)
    _write_markdown(output_dir / "reports" / "phase8-export-audit-report.md", report)
    return output_dir


def _audit_layer(layer: dict) -> dict:
    layout = layer.get("layout", {})
    photoshop = layer.get("photoshop", {})
    anchor_y = photoshop.get("vertical_top_anchor_y_px")
    suffix = photoshop.get("text_layer_name_suffix") or ""
    expected_anchor = layout.get("orientation") == "vertical" and layout.get("vertical_align") == "top"
    text_y = _text_position_y(layer)
    issues = _layer_issues(expected_anchor, anchor_y, suffix, text_y)
    return {
        "record_id": layer.get("record_id"),
        "orientation": layout.get("orientation"),
        "vertical_align": layout.get("vertical_align"),
        "text_position_y_px": text_y,
        "vertical_top_anchor_y_px": anchor_y,
        "text_layer_name_suffix": suffix,
        "expected_vertical_top_anchor": expected_anchor,
        "issues": issues,
    }


def _layer_issues(expected_anchor: bool, anchor_y: object, suffix: str, text_y: int | None) -> list[str]:
    if expected_anchor:
        return _expected_anchor_issues(anchor_y, suffix, text_y)
    issues: list[str] = []
    if anchor_y is not None:
        issues.append("unexpected_vertical_top_anchor_y_px")
    if suffix:
        issues.append("unexpected_vertical_top_suffix")
    return issues


def _expected_anchor_issues(anchor_y: object, suffix: str, text_y: int | None) -> list[str]:
    issues: list[str] = []
    if anchor_y is None:
        issues.append("missing_vertical_top_anchor_y_px")
    elif text_y is not None and anchor_y != text_y:
        issues.append("mismatched_vertical_top_anchor_y_px")
    if suffix != " vertical_align=top":
        issues.append("missing_vertical_top_suffix")
    return issues


def _summary(records: list[dict], jsx_source: str) -> dict:
    missing_anchor = _count_issue(records, "missing_vertical_top_anchor_y_px")
    unexpected_anchor = _count_issue(records, "unexpected_vertical_top_anchor_y_px")
    jsx_anchor = _jsx_anchor_logic_present(jsx_source)
    issue_count = sum(len(record["issues"]) for record in records)
    return {
        "record_count": len(records),
        "vertical_top_layer_count": sum(1 for record in records if record["expected_vertical_top_anchor"]),
        "missing_vertical_top_anchor_count": missing_anchor,
        "unexpected_vertical_top_anchor_count": unexpected_anchor,
        "record_issue_count": issue_count,
        "jsx_anchor_logic_present": jsx_anchor,
        "passed": issue_count == 0 and jsx_anchor,
    }


def _text_position_y(layer: dict) -> int | None:
    text_position = layer.get("text_position", {})
    if text_position.get("y_px") is not None:
        return int(text_position["y_px"])
    text_bbox = layer.get("text_bbox", {})
    if text_bbox.get("y") is not None:
        return int(text_bbox["y"])
    return None


def _count_issue(records: list[dict], issue: str) -> int:
    return sum(1 for record in records if issue in record["issues"])


def _jsx_anchor_logic_present(source: str) -> bool:
    required = ["applyVerticalTopAnchor", "vertical_top_anchor_y_px", "moveLayerTop"]
    return all(item in source for item in required)


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_markdown(path: Path, report: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(_markdown_lines(report)) + "\n", encoding="utf-8")


def _markdown_lines(report: dict) -> list[str]:
    summary = report["summary"]
    lines = [
        "# Phase 8 Photoshop Export Quality Audit",
        "",
        f"Phase 8 run directory: `{report['phase8_run_dir']}`",
        "",
        "## Summary",
        "",
        f"- Records audited: {summary['record_count']}",
        f"- Vertical top layers: {summary['vertical_top_layer_count']}",
        f"- Missing vertical top anchors: {summary['missing_vertical_top_anchor_count']}",
        f"- Unexpected vertical top anchors: {summary['unexpected_vertical_top_anchor_count']}",
        f"- JSX anchor logic present: `{summary['jsx_anchor_logic_present']}`",
        f"- Passed: `{summary['passed']}`",
        "",
        "## Records",
        "",
    ]
    lines.extend(_record_lines(report["records"]))
    return lines


def _record_lines(records: list[dict]) -> list[str]:
    if not records:
        return ["- None"]
    return [
        f"- `{record['record_id']}` orientation=`{record['orientation']}` vertical_align=`{record['vertical_align']}` "
        f"anchor_y=`{record['vertical_top_anchor_y_px']}` issues={record['issues']}"
        for record in records
    ]
