from __future__ import annotations

import json
from pathlib import Path

from .cleanup_runs import CleanupRunInput, format_cleanup_run_dirs, load_cleanup_rows_by_id
from .rendering.compose import compose_page_records


def run_phase7_preview(
    detection_run_dir: str | Path,
    cleanup_run_dir: CleanupRunInput,
    layout_run_dir: str | Path,
    output_root: str | Path = "outputs/runs",
    run_id: str | None = None,
    sample_limit: int = 5,
) -> Path:
    run_dir = Path(output_root) / (run_id or "phase7-page-preview")
    run_dir.mkdir(parents=True, exist_ok=True)
    detections = _load_detection_rows(Path(detection_run_dir) / "detections.jsonl")
    cleanups = load_cleanup_rows_by_id(cleanup_run_dir)
    layouts = _load_jsonl_by_id(Path(layout_run_dir) / "layout-results.jsonl", "layout_generated")
    rows = _preview_rows(run_dir, detections, cleanups, layouts, sample_limit)
    _write_jsonl(run_dir / "preview-results.jsonl", rows)
    _write_report(run_dir / "reports" / "phase7-report.md", detection_run_dir, cleanup_run_dir, layout_run_dir, rows)
    return run_dir


def _load_detection_rows(path: Path) -> dict[str, dict]:
    rows: dict[str, dict] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            payload = json.loads(line)
            if payload.get("status") == "ok":
                rows[payload["record_id"]] = payload
    return rows


def _load_jsonl_by_id(path: Path, status: str) -> dict[str, dict]:
    rows: dict[str, dict] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            payload = json.loads(line)
            if payload.get("status") == status:
                rows[payload["record_id"]] = payload
    return rows


def _preview_rows(
    run_dir: Path,
    detections: dict[str, dict],
    cleanups: dict[str, dict],
    layouts: dict[str, dict],
    sample_limit: int,
) -> list[dict]:
    records, skipped_rows = _preview_records(detections, cleanups, layouts, sample_limit)
    page_rows = [
        _preview_page(run_dir, image_name, page_records)
        for image_name, page_records in _group_by_image(records).items()
    ]
    return page_rows + skipped_rows


def _preview_records(
    detections: dict[str, dict],
    cleanups: dict[str, dict],
    layouts: dict[str, dict],
    sample_limit: int,
) -> tuple[list[dict], list[dict]]:
    records: list[dict] = []
    skipped_rows: list[dict] = []
    for index, (record_id, cleanup) in enumerate(cleanups.items()):
        if index >= sample_limit:
            break
        detection = detections.get(record_id)
        layout = layouts.get(record_id)
        if detection is None:
            skipped_rows.append(_skipped_row(record_id, "missing_detection"))
            continue
        if layout is None:
            skipped_rows.append(_skipped_row(record_id, "missing_layout"))
            continue
        records.append(_preview_record(detection, cleanup, layout))
    return records, skipped_rows


def _preview_record(detection: dict, cleanup: dict, layout: dict) -> dict:
    bbox = cleanup["cleanup"]["bbox"]
    return {
        "record_id": detection["record_id"],
        "image_name": detection.get("image_name"),
        "translated_text": detection.get("translated_text", ""),
        "image_path": detection["image_path"],
        "bbox": bbox,
        "cleanup_method": _cleanup_method(cleanup["cleanup"]),
        "cleaned_crop_path": _cleanup_crop_path(cleanup["cleanup"]),
        "layout_preview_path": layout["layout"]["preview_path"],
    }


def _preview_page(run_dir: Path, image_name: str, records: list[dict]) -> dict:
    preview_path = run_dir / "pages" / f"{_safe_name(image_name)}.png"
    compose_page_records(records[0]["image_path"], records, preview_path)
    return {
        "image_name": image_name,
        "status": "page_preview_generated",
        "records": [_record_summary(record) for record in records],
        "preview": {
            "page_preview_path": str(preview_path),
            "record_count": len(records),
        },
    }


def _record_summary(record: dict) -> dict:
    return {
        "record_id": record["record_id"],
        "bbox": record["bbox"],
        "cleanup_method": record.get("cleanup_method"),
        "layout_preview_path": record["layout_preview_path"],
    }


def _cleanup_crop_path(cleanup: dict) -> str:
    return cleanup.get("replacement_crop_path") or cleanup["cleaned_crop_path"]


def _cleanup_method(cleanup: dict) -> str | None:
    return cleanup.get("replacement_method") or cleanup.get("method")


def _skipped_row(record_id: str, reason: str) -> dict:
    return {
        "record_id": record_id,
        "status": "skipped",
        "preview": {"failure_reason": reason},
    }


def _group_by_image(records: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for record in records:
        grouped.setdefault(record.get("image_name") or "unknown", []).append(record)
    return grouped


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_report(
    output_path: Path,
    detection_run_dir: str | Path,
    cleanup_run_dir: CleanupRunInput,
    layout_run_dir: str | Path,
    rows: list[dict],
) -> None:
    generated = sum(1 for row in rows if row["status"] == "page_preview_generated")
    skipped = sum(1 for row in rows if row["status"] == "skipped")
    record_count = sum(len(row.get("records", [])) for row in rows) + skipped
    lines = [
        "# Phase 7 Page Preview Report",
        "",
        f"Detection run directory: `{detection_run_dir}`",
        f"Cleanup run directories: {format_cleanup_run_dirs(cleanup_run_dir)}",
        f"Layout run directory: `{layout_run_dir}`",
        "",
        "## Summary",
        "",
        f"- Records processed: {record_count}",
        f"- Page previews generated: {generated}",
        f"- Skipped: {skipped}",
        "",
        "## Generated Artifacts",
        "",
        "- `preview-results.jsonl`",
        "- `pages/*.png`",
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _safe_name(value: str) -> str:
    return "".join(char if char.isalnum() else "-" for char in value).strip("-") or "record"
