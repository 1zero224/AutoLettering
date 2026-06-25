from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path


RunDirInput = str | Path | Iterable[str | Path] | None
PHASE7_MIN_USABLE_SCORE = 7


def build_quality_summary(
    phase7_preview_evaluation_run_dir: RunDirInput,
    phase8_export_audit_run_dir: RunDirInput,
    phase6_gpt_quality_run_dir: RunDirInput = None,
    phase6_cleanup_quality_run_dir: RunDirInput = None,
) -> dict[str, dict]:
    return {
        "phase6_cleanup": _phase6_cleanup_quality_summary(phase6_cleanup_quality_run_dir),
        "phase6_gpt_replacement": _phase6_gpt_replacement_quality_summary(phase6_gpt_quality_run_dir),
        "phase7_preview": _phase7_preview_quality_summary(phase7_preview_evaluation_run_dir),
        "phase8_export": _phase8_export_quality_summary(phase8_export_audit_run_dir),
    }


def quality_issues_by_record(quality: dict) -> dict[str, list[str]]:
    issues: dict[str, list[str]] = {}
    _merge_record_issues(issues, _phase6_cleanup_issues(quality.get("phase6_cleanup", {})))
    _merge_record_issues(issues, _phase6_gpt_replacement_issues(quality.get("phase6_gpt_replacement", {})))
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
    phase6_cleanup = quality.get("phase6_cleanup", {})
    phase6 = quality.get("phase6_gpt_replacement", {})
    phase7 = quality.get("phase7_preview", {})
    phase8 = quality.get("phase8_export", {})
    if (
        not _has_phase6_cleanup_quality(phase6_cleanup)
        and not _has_phase6_gpt_quality(phase6)
        and not _has_phase7_quality(phase7)
        and not _has_phase8_quality(phase8)
    ):
        return ["", "## Quality Audits", "", "- None"]
    lines = ["", "## Quality Audits"]
    if _has_phase6_cleanup_quality(phase6_cleanup):
        lines.extend([
            "",
            "### phase6_cleanup",
            "",
            f"- Cleanup evaluations: {phase6_cleanup['evaluation_count']}",
            f"- Usable cleanups: {phase6_cleanup['usable_count']}/{phase6_cleanup['evaluated_count']}",
            f"- Failed evaluations: {phase6_cleanup['failed_count']}",
            f"- Record issues: {phase6_cleanup['record_issue_count']}",
        ])
    if _has_phase6_gpt_quality(phase6):
        lines.extend([
            "",
            "### phase6_gpt_replacement",
            "",
            f"- GPT replacement runs: {phase6['run_count']}",
            f"- GPT quality checked: {phase6['gpt_quality_checked_count']}",
            f"- GPT quality failures: {phase6['gpt_quality_failed_count']}",
            f"- Record issues: {phase6['record_issue_count']}",
        ])
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


def _phase6_cleanup_quality_summary(run_dir: RunDirInput) -> dict:
    rows = _phase6_cleanup_rows(run_dir)
    records = _phase6_cleanup_records(rows)
    return {
        "evaluation_count": len(rows),
        "evaluated_count": sum(1 for row in rows if row.get("status") == "evaluated"),
        "usable_count": sum(1 for row in rows if row.get("status") == "evaluated" and row.get("usable") is True),
        "failed_count": sum(1 for row in rows if row.get("status") != "evaluated"),
        "record_count": len(records),
        "record_issue_count": sum(len(record.get("issues") or []) for record in records),
        "records": records,
    }


def _phase6_cleanup_rows(run_dir: RunDirInput) -> list[dict]:
    rows: list[dict] = []
    for item in _run_dirs(run_dir):
        path = Path(item) / "cleanup-quality.jsonl"
        if path.exists():
            rows.extend(_jsonl_rows(path))
    return rows


def _phase6_cleanup_records(rows: list[dict]) -> list[dict]:
    by_record: dict[str, dict] = {}
    for row in rows:
        record_id = row.get("record_id")
        if not record_id:
            continue
        by_record[str(record_id)] = {
            "record_id": str(record_id),
            "image_name": row.get("image_name"),
            "status": row.get("status"),
            "usable": row.get("usable"),
            "original_text_removed": row.get("original_text_removed"),
            "art_preserved": row.get("art_preserved"),
            "issues": _phase6_cleanup_row_issues(row),
        }
    return list(by_record.values())


def _phase6_cleanup_row_issues(row: dict) -> list[str]:
    if row.get("status") != "evaluated":
        return ["phase6_cleanup_evaluation_failed"]
    issues: list[str] = []
    if row.get("original_text_removed") is False:
        issues.append("phase6_cleanup_original_text_visible")
    if row.get("art_preserved") is False:
        issues.append("phase6_cleanup_art_not_preserved")
    if row.get("usable") is not True and not issues:
        issues.append("phase6_cleanup_unusable")
    return _dedupe(issues)


def _phase6_cleanup_issues(phase6_cleanup: dict) -> dict[str, list[str]]:
    return {
        str(record["record_id"]): [str(issue) for issue in record.get("issues", [])]
        for record in phase6_cleanup.get("records", [])
        if record.get("record_id") and record.get("issues")
    }


def _phase6_gpt_replacement_quality_summary(run_dir: RunDirInput) -> dict:
    replacement_rows = _phase6_replacement_quality_rows(run_dir)
    if replacement_rows:
        records = _phase6_replacement_quality_records(replacement_rows)
        return {
            "run_count": len(_run_dirs(run_dir)),
            "gpt_quality_checked_count": sum(1 for row in replacement_rows if row.get("status") == "evaluated"),
            "gpt_quality_failed_count": len(records),
            "record_count": len(records),
            "record_issue_count": sum(len(record.get("issues") or []) for record in records),
            "records": records,
        }
    manifests = _phase6_gpt_replacement_manifests(run_dir)
    runs = [_phase6_gpt_replacement_run(item, manifest) for item, manifest in manifests]
    records = _phase6_gpt_replacement_records(run_dir, runs)
    return {
        "run_count": len(runs),
        "gpt_quality_checked_count": sum(run["checked_count"] for run in runs),
        "gpt_quality_failed_count": sum(run["failed_count"] for run in runs),
        "record_count": len(records),
        "record_issue_count": sum(len(record.get("issues") or []) for record in records),
        "records": records,
    }


def _phase6_replacement_quality_rows(run_dir: RunDirInput) -> list[dict]:
    rows: list[dict] = []
    for item in _run_dirs(run_dir):
        path = Path(item) / "replacement-quality.jsonl"
        if path.exists():
            rows.extend(_jsonl_rows(path))
    return rows


def _phase6_replacement_quality_records(rows: list[dict]) -> list[dict]:
    records: list[dict] = []
    for row in rows:
        if _phase6_replacement_quality_accepted(row):
            continue
        record_id = row.get("record_id")
        if not record_id:
            continue
        issues = ["phase6_gpt_image2_quality_unacceptable", *[str(item) for item in row.get("issues") or []]]
        records.append(
            {
                "record_id": str(record_id),
                "image_name": row.get("image_name"),
                "status": row.get("status"),
                "usable": row.get("usable"),
                "exact_text_correct": row.get("exact_text_correct"),
                "simplified_chinese_correct": row.get("simplified_chinese_correct"),
                "region_correct": row.get("region_correct"),
                "issues": _dedupe(issues),
            }
        )
    return records


def _phase6_replacement_quality_accepted(row: dict) -> bool:
    return (
        row.get("status") == "evaluated"
        and row.get("usable") is True
        and row.get("exact_text_correct") is True
        and row.get("simplified_chinese_correct") is True
        and row.get("no_japanese_remaining") is True
        and row.get("region_correct") is True
    )


def _phase6_gpt_replacement_manifests(run_dir: RunDirInput) -> list[tuple[Path, dict]]:
    manifests: list[tuple[Path, dict]] = []
    for item in _run_dirs(run_dir):
        path = Path(item) / "manifest.json"
        if path.exists():
            manifests.append((Path(item), json.loads(path.read_text(encoding="utf-8"))))
    return manifests


def _phase6_gpt_replacement_run(run_dir: Path, manifest: dict) -> dict:
    unacceptable = _phase6_gpt_replacement_unacceptable(run_dir, manifest)
    gpt_ok_count = int(manifest.get("gpt_ok_count") or 0)
    checked_count = int(manifest.get("gpt_quality_checked_count") or 0)
    failed_count = int(manifest.get("gpt_quality_failed_count") or 0)
    if checked_count == 0 and unacceptable:
        checked_count = gpt_ok_count
    if failed_count == 0 and unacceptable:
        failed_count = gpt_ok_count
    return {
        "run_dir": run_dir,
        "unacceptable": unacceptable,
        "checked_count": checked_count,
        "failed_count": failed_count,
    }


def _phase6_gpt_replacement_records(run_dir: RunDirInput, runs: list[dict]) -> list[dict]:
    if not any(run["unacceptable"] for run in runs):
        return []
    by_record: dict[str, dict] = {}
    for item in [run["run_dir"] for run in runs if run["unacceptable"]]:
        path = Path(item) / "gpt-replace-results.jsonl"
        if not path.exists():
            continue
        for row in _jsonl_rows(path):
            record_id = row.get("record_id")
            if not record_id:
                continue
            by_record[str(record_id)] = {
                "record_id": str(record_id),
                "image_name": row.get("image_name"),
                "issues": ["phase6_gpt_image2_quality_unacceptable"],
            }
    return list(by_record.values())


def _phase6_gpt_replacement_unacceptable(run_dir: Path, manifest: dict) -> bool:
    if int(manifest.get("gpt_quality_failed_count") or 0) > 0:
        return True
    mimo = manifest.get("mimo") if isinstance(manifest.get("mimo"), dict) else {}
    quality = (mimo.get("quality") or {}) if isinstance(mimo, dict) else {}
    if quality.get("gpt_image2_status") == "unacceptable":
        return True
    return _legacy_mimo_gpt_replacement_unacceptable(run_dir, mimo)


def _legacy_mimo_gpt_replacement_unacceptable(run_dir: Path, mimo: dict) -> bool:
    path_value = mimo.get("path") if isinstance(mimo, dict) else None
    if not path_value:
        return False
    path = Path(path_value)
    if not path.is_absolute():
        path = run_dir / path
        if not path.exists():
            path = run_dir / Path(path_value).name
        if not path.exists():
            path = run_dir / "reports" / Path(path_value).name
    if not path.exists():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        raw_text = str(payload.get("raw_text", ""))
        parsed = json.loads(_strip_json_wrapper(raw_text))
    except Exception:
        return False
    unacceptable = [str(item) for item in parsed.get("unacceptable_methods", []) if str(item).strip()]
    return any(_is_gpt_image2_method_label(item) for item in unacceptable)


def _phase6_gpt_replacement_issues(phase6: dict) -> dict[str, list[str]]:
    return {
        str(record["record_id"]): [str(issue) for issue in record.get("issues", [])]
        for record in phase6.get("records", [])
        if record.get("record_id") and record.get("issues")
    }


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


def _has_phase6_cleanup_quality(phase6_cleanup: dict) -> bool:
    return bool(phase6_cleanup and phase6_cleanup.get("evaluation_count"))


def _has_phase6_gpt_quality(phase6: dict) -> bool:
    return bool(phase6 and phase6.get("run_count"))


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


def _is_gpt_image2_method_label(value: str) -> bool:
    normalized = value.lower().replace("_", "-").replace(" ", "")
    return "gpt-image-2" in normalized or "gptimage2" in normalized


def _strip_json_wrapper(raw_text: str) -> str:
    text = raw_text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _run_dirs(run_dir: RunDirInput) -> list[str | Path]:
    if run_dir is None:
        return []
    if isinstance(run_dir, str | Path):
        return [run_dir]
    return list(run_dir)


def _jsonl_rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
