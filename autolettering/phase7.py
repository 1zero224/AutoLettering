from __future__ import annotations

import json
from pathlib import Path

from .rendering.compose import compose_page_preview


def run_phase7_preview(
    detection_run_dir: str | Path,
    cleanup_run_dir: str | Path,
    layout_run_dir: str | Path,
    output_root: str | Path = "outputs/runs",
    run_id: str | None = None,
    sample_limit: int = 5,
) -> Path:
    run_dir = Path(output_root) / (run_id or "phase7-page-preview")
    run_dir.mkdir(parents=True, exist_ok=True)
    detections = _load_detection_rows(Path(detection_run_dir) / "detections.jsonl")
    cleanups = _load_jsonl_by_id(Path(cleanup_run_dir) / "cleanup-results.jsonl", "cleaned")
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
    rows: list[dict] = []
    for record_id, cleanup in cleanups.items():
        if len(rows) >= sample_limit:
            break
        rows.append(_preview_one(run_dir, record_id, detections, cleanup, layouts))
    return rows


def _preview_one(
    run_dir: Path,
    record_id: str,
    detections: dict[str, dict],
    cleanup: dict,
    layouts: dict[str, dict],
) -> dict:
    detection = detections.get(record_id)
    layout = layouts.get(record_id)
    if detection is None:
        return _skipped_row(record_id, "missing_detection")
    if layout is None:
        return _skipped_row(record_id, "missing_layout")

    bbox = tuple(cleanup["cleanup"]["bbox"])
    preview_path = run_dir / "pages" / f"{_safe_name(record_id)}.png"
    compose_page_preview(
        detection["image_path"],
        bbox,
        cleanup["cleanup"]["cleaned_crop_path"],
        layout["layout"]["preview_path"],
        preview_path,
    )
    return {
        "record_id": record_id,
        "image_name": detection.get("image_name"),
        "translated_text": detection.get("translated_text", ""),
        "status": "preview_generated",
        "preview": {
            "page_preview_path": str(preview_path),
            "bbox": list(bbox),
            "cleanup_method": cleanup["cleanup"].get("method"),
            "layout_preview_path": layout["layout"]["preview_path"],
        },
    }


def _skipped_row(record_id: str, reason: str) -> dict:
    return {
        "record_id": record_id,
        "status": "skipped",
        "preview": {"failure_reason": reason},
    }


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_report(
    output_path: Path,
    detection_run_dir: str | Path,
    cleanup_run_dir: str | Path,
    layout_run_dir: str | Path,
    rows: list[dict],
) -> None:
    generated = sum(1 for row in rows if row["status"] == "preview_generated")
    lines = [
        "# Phase 7 Page Preview Report",
        "",
        f"Detection run directory: `{detection_run_dir}`",
        f"Cleanup run directory: `{cleanup_run_dir}`",
        f"Layout run directory: `{layout_run_dir}`",
        "",
        "## Summary",
        "",
        f"- Records processed: {len(rows)}",
        f"- Page previews generated: {generated}",
        f"- Skipped: {len(rows) - generated}",
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
