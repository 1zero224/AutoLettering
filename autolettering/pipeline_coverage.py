from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from .pipeline_quality import build_quality_summary, quality_issues_by_record
from .pipeline_report import pipeline_markdown_lines


RunDirInput = str | Path | Iterable[str | Path] | None


STAGE_ORDER = [
    "phase1_labelplus",
    "phase2_detection",
    "phase3_font_selection",
    "phase4_layout",
    "phase5_angle",
    "phase6_cleanup",
    "phase7_preview",
    "phase8_export",
]


def build_pipeline_coverage(
    phase1_run_dir: str | Path | None = None,
    detection_run_dir: str | Path | None = None,
    font_selection_run_dir: RunDirInput = None,
    layout_run_dir: RunDirInput = None,
    angle_run_dir: RunDirInput = None,
    cleanup_run_dirs: Iterable[str | Path] | None = None,
    preview_run_dir: RunDirInput = None,
    export_run_dir: RunDirInput = None,
    phase7_preview_evaluation_run_dir: RunDirInput = None,
    phase8_export_audit_run_dir: RunDirInput = None,
    next_limit: int = 10,
) -> dict:
    meta, phase1_ids = _phase1_records(phase1_run_dir)
    detection_rows = _jsonl_rows(_maybe_path(detection_run_dir, "detections.jsonl"))
    detection_all = _row_ids(detection_rows)
    detection_ok = _status_ids(detection_rows, "ok")
    _merge_row_meta(meta, detection_rows)
    stages = _stage_records(
        phase1_ids,
        detection_ok,
        font_selection_run_dir,
        layout_run_dir,
        angle_run_dir,
        cleanup_run_dirs,
        preview_run_dir,
        export_run_dir,
    )
    base_stage, base_ids = _base_records(detection_run_dir, detection_all, phase1_ids)
    quality = build_quality_summary(phase7_preview_evaluation_run_dir, phase8_export_audit_run_dir)
    records = _record_coverage(base_ids, meta, stages, quality_issues_by_record(quality))
    phase1_pending_detection = _phase1_pending_detection_records(phase1_ids, detection_all, meta, next_limit)
    return {
        "summary": _summary(base_stage, base_ids, records),
        "stages": _stage_summary(stages, base_ids),
        "quality": quality,
        "group_summary": _group_summary(base_ids, records),
        "records": records,
        "next_records": _next_records(base_ids, records, next_limit),
        "phase1_pending_detection_count": max(0, len(phase1_ids) - len(set(detection_all))),
        "phase1_pending_detection_records": phase1_pending_detection,
    }


def write_pipeline_coverage_report(
    output_root: str | Path = "outputs/runs",
    run_id: str | None = None,
    **kwargs,
) -> Path:
    run_dir = Path(output_root) / (run_id or "pipeline-coverage-report")
    run_dir.mkdir(parents=True, exist_ok=True)
    report = build_pipeline_coverage(**kwargs)
    _write_json(run_dir / "pipeline-coverage.json", report)
    _write_markdown(run_dir / "reports" / "pipeline-coverage-report.md", report)
    return run_dir


def _stage_records(
    phase1_ids: list[str],
    detection_ok: list[str],
    font_selection_run_dir: RunDirInput,
    layout_run_dir: RunDirInput,
    angle_run_dir: RunDirInput,
    cleanup_run_dirs: Iterable[str | Path] | None,
    preview_run_dir: RunDirInput,
    export_run_dir: RunDirInput,
) -> dict[str, list[str]]:
    return {
        "phase1_labelplus": phase1_ids,
        "phase2_detection": detection_ok,
        "phase3_font_selection": _status_ids(_jsonl_at_many(font_selection_run_dir, "font-selections.jsonl"), "selected"),
        "phase4_layout": _status_ids(_jsonl_at_many(layout_run_dir, "layout-results.jsonl"), "layout_generated"),
        "phase5_angle": _status_ids(_jsonl_at_many(angle_run_dir, "angle-results.jsonl"), "angle_estimated"),
        "phase6_cleanup": _cleanup_ids(cleanup_run_dirs),
        "phase7_preview": _preview_ids(preview_run_dir),
        "phase8_export": _export_ids(export_run_dir),
    }


def _record_coverage(
    base_ids: list[str],
    meta: dict[str, dict],
    stages: dict[str, list[str]],
    quality_issues: dict[str, list[str]],
) -> dict[str, dict]:
    result: dict[str, dict] = {}
    stage_sets = {name: set(ids) for name, ids in stages.items() if ids}
    for record_id in base_ids:
        missing = [name for name in STAGE_ORDER if name in stage_sets and record_id not in stage_sets[name]]
        result[record_id] = {
            "record_id": record_id,
            "group_name": meta.get(record_id, {}).get("group_name"),
            "image_name": meta.get(record_id, {}).get("image_name"),
            "covered_stages": [name for name in STAGE_ORDER if record_id in stage_sets.get(name, set())],
            "missing_stages": missing,
            "quality_issues": quality_issues.get(record_id, []),
        }
    return result


def _phase1_records(run_dir: str | Path | None) -> tuple[dict[str, dict], list[str]]:
    path = _maybe_path(run_dir, "manifest.json")
    if path is None or not path.exists():
        return {}, []
    payload = json.loads(path.read_text(encoding="utf-8"))
    meta: dict[str, dict] = {}
    ids: list[str] = []
    for image in payload.get("images", []):
        for label in image.get("labels", []):
            record_id = str(label.get("id"))
            ids.append(record_id)
            meta[record_id] = {"group_name": label.get("group_name"), "image_name": image.get("image_name")}
    return meta, _unique(ids)


def _merge_row_meta(meta: dict[str, dict], rows: list[dict]) -> None:
    for row in rows:
        record_id = row.get("record_id")
        if not record_id:
            continue
        current = meta.setdefault(str(record_id), {})
        for key in ("group_name", "image_name"):
            if row.get(key):
                current[key] = row[key]


def _base_records(
    detection_run_dir: str | Path | None,
    detection_all: list[str],
    phase1_ids: list[str],
) -> tuple[str, list[str]]:
    if detection_run_dir is not None and detection_all:
        return "phase2_detection", detection_all
    return "phase1_labelplus", phase1_ids


def _summary(base_stage: str, base_ids: list[str], records: dict[str, dict]) -> dict:
    complete = sum(1 for row in records.values() if not row["missing_stages"] and not row["quality_issues"])
    return {
        "base_stage": base_stage,
        "base_record_count": len(base_ids),
        "complete_record_count": complete,
        "incomplete_record_count": len(base_ids) - complete,
    }


def _stage_summary(stages: dict[str, list[str]], base_ids: list[str]) -> dict[str, dict]:
    base = set(base_ids)
    summary: dict[str, dict] = {}
    for name in STAGE_ORDER:
        ids = [record_id for record_id in stages.get(name, []) if record_id in base]
        summary[name] = {
            "covered_count": len(ids),
            "missing_count": max(0, len(base_ids) - len(ids)),
            "covered_record_ids": sorted(ids),
        }
    return summary


def _group_summary(base_ids: list[str], records: dict[str, dict]) -> dict[str, dict]:
    grouped: dict[str, dict] = {}
    for record_id in base_ids:
        row = records[record_id]
        group = row.get("group_name") or "unknown"
        item = grouped.setdefault(group, {"base_count": 0, "complete_count": 0})
        item["base_count"] += 1
        item["complete_count"] += 0 if row["missing_stages"] or row["quality_issues"] else 1
    return grouped


def _next_records(base_ids: list[str], records: dict[str, dict], limit: int) -> list[dict]:
    items = [
        {
            "record_id": record_id,
            "group_name": records[record_id].get("group_name"),
            "first_missing_stage": records[record_id]["missing_stages"][0],
        }
        for record_id in base_ids
        if records[record_id]["missing_stages"]
    ]
    for record_id in base_ids:
        row = records[record_id]
        if not row["missing_stages"] and row["quality_issues"]:
            items.append({
                "record_id": record_id,
                "group_name": row.get("group_name"),
                "first_quality_issue": row["quality_issues"][0],
            })
    return items[: max(0, limit)]


def _phase1_pending_detection_records(
    phase1_ids: list[str],
    detection_all: list[str],
    meta: dict[str, dict],
    limit: int,
) -> list[dict]:
    detected = set(detection_all)
    records = [
        {
            "record_id": record_id,
            "group_name": meta.get(record_id, {}).get("group_name"),
            "image_name": meta.get(record_id, {}).get("image_name"),
        }
        for record_id in phase1_ids
        if record_id not in detected
    ]
    return records[: max(0, limit)]


def _cleanup_ids(run_dirs: Iterable[str | Path] | None) -> list[str]:
    ids: list[str] = []
    for run_dir in run_dirs or []:
        ids.extend(_status_ids(_jsonl_at(run_dir, "cleanup-results.jsonl"), "cleaned"))
    return _unique(ids)


def _preview_ids(run_dir: RunDirInput) -> list[str]:
    ids: list[str] = []
    for item in _run_dirs(run_dir):
        for row in _jsonl_at(item, "preview-results.jsonl"):
            if row.get("status") != "page_preview_generated":
                continue
            ids.extend(str(record.get("record_id")) for record in row.get("records", []) if record.get("record_id"))
    return _unique(ids)


def _export_ids(run_dir: RunDirInput) -> list[str]:
    ids: list[str] = []
    for item in _run_dirs(run_dir):
        path = _maybe_path(item, "photoshop-manifest.json")
        if path is None or not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        ids.extend(str(layer["record_id"]) for page in payload.get("pages", []) for layer in page.get("layers", []))
    return _unique(ids)


def _jsonl_at_many(run_dir: RunDirInput, name: str) -> list[dict]:
    rows: list[dict] = []
    for item in _run_dirs(run_dir):
        rows.extend(_jsonl_at(item, name))
    return rows


def _run_dirs(run_dir: RunDirInput) -> list[str | Path]:
    if run_dir is None:
        return []
    if isinstance(run_dir, str | Path):
        return [run_dir]
    return list(run_dir)


def _jsonl_at(run_dir: str | Path | None, name: str) -> list[dict]:
    return _jsonl_rows(_maybe_path(run_dir, name))


def _jsonl_rows(path: Path | None) -> list[dict]:
    if path is None or not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _status_ids(rows: list[dict], status: str) -> list[str]:
    return _unique(str(row["record_id"]) for row in rows if row.get("status") == status and row.get("record_id"))


def _row_ids(rows: list[dict]) -> list[str]:
    return _unique(str(row["record_id"]) for row in rows if row.get("record_id"))


def _maybe_path(run_dir: str | Path | None, name: str) -> Path | None:
    return None if run_dir is None else Path(run_dir) / name


def _unique(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_markdown(path: Path, report: dict) -> None:
    lines = pipeline_markdown_lines(report, STAGE_ORDER)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
