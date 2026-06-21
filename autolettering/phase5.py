from __future__ import annotations

from collections.abc import Iterable
import json
from pathlib import Path

from .layout.orientation import (
    draw_angle_debug_grid,
    estimate_orientation_angle,
    orientation_estimate_to_dict,
)
from .record_selection import normalize_record_ids, row_matches_record_ids


def run_phase5_orientation(
    detection_run_dir: str | Path,
    output_root: str | Path = "outputs/runs",
    run_id: str | None = None,
    sample_limit: int = 5,
    record_ids: Iterable[str] | None = None,
) -> Path:
    run_dir = Path(output_root) / (run_id or "phase5-orientation-angle")
    run_dir.mkdir(parents=True, exist_ok=True)
    detections = _load_detection_rows(Path(detection_run_dir) / "detections.jsonl", sample_limit, record_ids)
    rows = [_orientation_row(run_dir, row) for row in detections]
    _write_jsonl(run_dir / "angle-results.jsonl", rows)
    _write_report(run_dir / "reports" / "phase5-report.md", detection_run_dir, rows)
    return run_dir


def _load_detection_rows(path: Path, sample_limit: int, record_ids: Iterable[str] | None = None) -> list[dict]:
    wanted = normalize_record_ids(record_ids)
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if len(rows) >= sample_limit:
                break
            payload = json.loads(line)
            if (
                row_matches_record_ids(payload, wanted)
                and payload.get("status") == "ok"
                and payload.get("selected_text_box_xyxy")
            ):
                rows.append(payload)
    return rows


def _orientation_row(run_dir: Path, detection: dict) -> dict:
    bbox = _angle_bbox(detection)
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


def _angle_bbox(detection: dict) -> tuple[int, int, int, int]:
    selected = tuple(detection["selected_text_box_xyxy"])
    selected_area = _area(selected)
    text_candidates = [_candidate_xyxy(item) for item in detection.get("candidate_boxes") or []]
    text_candidates = [
        bbox
        for bbox in text_candidates
        if bbox and _inside(bbox, selected) and 0 < _area(bbox) <= selected_area * 0.35
    ]
    return _representative_text_column(text_candidates) if text_candidates else selected


def _representative_text_column(bboxes: list[tuple[int, int, int, int]]) -> tuple[int, int, int, int]:
    return max(bboxes, key=lambda bbox: (_height_ratio(bbox), _area(bbox)))


def _height_ratio(bbox: tuple[int, int, int, int]) -> float:
    x1, y1, x2, y2 = bbox
    return (y2 - y1) / max(1, x2 - x1)


def _candidate_xyxy(item: dict) -> tuple[int, int, int, int] | None:
    xyxy = item.get("xyxy")
    if not isinstance(xyxy, list) or len(xyxy) != 4:
        return None
    return tuple(int(value) for value in xyxy)


def _inside(inner: tuple[int, int, int, int], outer: tuple[int, int, int, int]) -> bool:
    ix1, iy1, ix2, iy2 = inner
    ox1, oy1, ox2, oy2 = outer
    return ox1 <= ix1 < ix2 <= ox2 and oy1 <= iy1 < iy2 <= oy2


def _area(bbox: tuple[int, int, int, int]) -> int:
    x1, y1, x2, y2 = bbox
    return max(0, x2 - x1) * max(0, y2 - y1)


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
