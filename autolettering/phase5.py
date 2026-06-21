from __future__ import annotations

import json
from pathlib import Path

from .layout.orientation import (
    draw_angle_debug_grid,
    estimate_orientation_angle,
    orientation_estimate_to_dict,
)


def run_phase5_orientation(
    detection_run_dir: str | Path,
    output_root: str | Path = "outputs/runs",
    run_id: str | None = None,
    sample_limit: int = 5,
) -> Path:
    run_dir = Path(output_root) / (run_id or "phase5-orientation-angle")
    run_dir.mkdir(parents=True, exist_ok=True)
    detections = _load_detection_rows(Path(detection_run_dir) / "detections.jsonl", sample_limit)
    rows = [_orientation_row(run_dir, row) for row in detections]
    _write_jsonl(run_dir / "angle-results.jsonl", rows)
    _write_report(run_dir / "reports" / "phase5-report.md", detection_run_dir, rows)
    return run_dir


def _load_detection_rows(path: Path, sample_limit: int) -> list[dict]:
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if len(rows) >= sample_limit:
                break
            payload = json.loads(line)
            if payload.get("status") == "ok" and payload.get("selected_text_box_xyxy"):
                rows.append(payload)
    return rows


def _orientation_row(run_dir: Path, detection: dict) -> dict:
    bbox = tuple(detection["selected_text_box_xyxy"])
    estimate = estimate_orientation_angle(detection["image_path"], bbox)
    debug_path = run_dir / "debug" / "angle_candidates" / f"{_safe_name(detection['record_id'])}.png"
    draw_angle_debug_grid(detection["image_path"], bbox, estimate, debug_path)
    orientation = orientation_estimate_to_dict(estimate)
    orientation["debug_preview_grid_path"] = str(debug_path)
    return {
        "record_id": detection["record_id"],
        "image_name": detection.get("image_name"),
        "translated_text": detection.get("translated_text", ""),
        "group_name": detection.get("group_name"),
        "status": "angle_estimated" if estimate.status == "ok" else "angle_failed",
        "orientation": orientation,
    }


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_report(output_path: Path, detection_run_dir: str | Path, rows: list[dict]) -> None:
    estimated = sum(1 for row in rows if row["status"] == "angle_estimated")
    lines = [
        "# Phase 5 Orientation Angle Report",
        "",
        f"Detection run directory: `{detection_run_dir}`",
        "",
        "## Summary",
        "",
        f"- Records processed: {len(rows)}",
        f"- Angle estimates: {estimated}",
        f"- Failures: {len(rows) - estimated}",
        "",
        "## Generated Artifacts",
        "",
        "- `angle-results.jsonl`",
        "- `debug/angle_candidates/*.png`",
        "- `reports/phase5-report.md`",
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _safe_name(value: str) -> str:
    return "".join(char if char.isalnum() else "-" for char in value).strip("-") or "record"
