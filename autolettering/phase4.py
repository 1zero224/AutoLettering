from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict
import json
from pathlib import Path

from PIL import Image

from .layout.measure import search_fitting_layout
from .layout.render_text import measure_preview_alignment, render_layout_preview
from .record_selection import normalize_record_ids, row_matches_record_ids
from .text_bbox import selected_text_bbox


def run_phase4(
    selection_run_dir: str | Path,
    angle_run_dir: str | Path | None = None,
    detection_run_dir: str | Path | None = None,
    output_root: str | Path = "outputs/runs",
    run_id: str | None = None,
    sample_limit: int = 5,
    record_ids: Iterable[str] | None = None,
) -> Path:
    run_dir = Path(output_root) / (run_id or "phase4-layout-search")
    run_dir.mkdir(parents=True, exist_ok=True)
    selections = _load_selected_fonts(Path(selection_run_dir) / "font-selections.jsonl", sample_limit, record_ids)
    angle_rows = _load_angle_rows(angle_run_dir)
    detection_rows = _load_detection_rows(detection_run_dir)
    rows = [_layout_record(run_dir, row, angle_rows, detection_rows) for row in selections]
    _write_jsonl(run_dir / "layout-results.jsonl", rows)
    _write_report(run_dir / "reports" / "phase4-report.md", selection_run_dir, angle_run_dir, detection_run_dir, rows)
    return run_dir


def _load_selected_fonts(path: Path, sample_limit: int, record_ids: Iterable[str] | None = None) -> list[dict]:
    wanted = normalize_record_ids(record_ids)
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if len(rows) >= sample_limit:
                break
            payload = json.loads(line)
            if row_matches_record_ids(payload, wanted) and payload.get("status") == "selected" and payload.get("selected_font"):
                rows.append(payload)
    return rows


def _load_angle_rows(angle_run_dir: str | Path | None) -> dict[str, dict]:
    if angle_run_dir is None:
        return {}
    path = Path(angle_run_dir) / "angle-results.jsonl"
    rows: dict[str, dict] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            payload = json.loads(line)
            if payload.get("status") == "angle_estimated":
                rows[payload["record_id"]] = payload["orientation"]
    return rows


def _load_detection_rows(detection_run_dir: str | Path | None) -> dict[str, dict]:
    if detection_run_dir is None:
        return {}
    path = Path(detection_run_dir) / "detections.jsonl"
    rows: dict[str, dict] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            payload = json.loads(line)
            if payload.get("status") == "ok":
                rows[payload["record_id"]] = payload
    return rows


def _layout_record(
    run_dir: Path,
    row: dict,
    angle_rows: dict[str, dict],
    detection_rows: dict[str, dict],
) -> dict:
    font_path = Path(row["selected_font"]["path"])
    angle = angle_rows.get(row["record_id"])
    layout, target_bbox, target_size = _search_layout_for_record(row, font_path, angle, detection_rows)
    preview_path = run_dir / "debug" / "layout_candidates" / f"{_safe_name(row['record_id'])}.png"
    render_layout_preview(layout, font_path, preview_path, canvas_size=target_size)
    alignment = measure_preview_alignment(preview_path)
    return {
        "record_id": row["record_id"],
        "image_name": row.get("image_name"),
        "translated_text": row.get("translated_text", ""),
        "status": "layout_generated" if layout.status == "ok" else "layout_failed",
        "selected_font_id": row.get("selected_font_id"),
        "layout": _layout_payload(layout, preview_path, alignment, target_bbox),
    }


def _search_layout_for_record(row: dict, font_path: Path, angle: dict | None, detection_rows: dict[str, dict]):
    target_bboxes = _layout_target_bboxes(row, detection_rows)
    if not target_bboxes:
        target_size = _target_size_from_comparison(row)
        return _search_layout(row, font_path, target_size, angle), None, target_size

    fallback = None
    for target_bbox in target_bboxes:
        target_size = _bbox_size(target_bbox)
        layout = _search_layout(row, font_path, target_size, angle)
        fallback = layout, target_bbox, target_size
        if layout.status == "ok":
            return fallback
    return fallback


def _search_layout(row: dict, font_path: Path, target_size: tuple[int, int], angle: dict | None):
    orientation = _selected_orientation(target_size, angle)
    angle_degrees = _angle_override(angle) if orientation == _orientation_override(angle) else 0.0
    return search_fitting_layout(
        row.get("translated_text", ""),
        font_path,
        target_size,
        orientation=orientation,
        angle_degrees=angle_degrees,
    )


def _target_size_from_comparison(row: dict) -> tuple[int, int]:
    source_crop_path = row.get("source_crop_path")
    if source_crop_path and Path(source_crop_path).exists():
        with Image.open(source_crop_path) as image:
            return image.size

    comparison_path = row.get("comparison_image_path")
    if comparison_path and Path(comparison_path).exists():
        with Image.open(comparison_path) as image:
            return max(80, image.width // 8), max(60, image.height // 3)
    return 180, 120


def _layout_target_bboxes(row: dict, detection_rows: dict[str, dict]) -> list[list[int]]:
    detection = detection_rows.get(row["record_id"])
    if detection is None:
        return []
    tight_bbox = _text_bbox(detection)
    selected_bbox = tuple(int(value) for value in detection["selected_text_box_xyxy"])
    return [list(bbox) for bbox in _expand_target_bboxes(tight_bbox, selected_bbox)]


def _layout_target_bbox(row: dict, detection_rows: dict[str, dict]) -> list[int] | None:
    bboxes = _layout_target_bboxes(row, detection_rows)
    if not bboxes:
        return None
    return bboxes[0]


def _text_bbox(detection: dict) -> tuple[int, int, int, int]:
    return selected_text_bbox(detection)


def _bbox_size(bbox: list[int]) -> tuple[int, int]:
    x1, y1, x2, y2 = bbox
    return x2 - x1, y2 - y1


def _expand_target_bboxes(
    tight_bbox: tuple[int, int, int, int],
    selected_bbox: tuple[int, int, int, int],
) -> list[tuple[int, int, int, int]]:
    candidates = [tight_bbox]
    selected_area = _area(selected_bbox)
    for scale in (1.2, 1.4, 1.7, 2.0):
        expanded = _scale_bbox_inside(tight_bbox, selected_bbox, scale)
        if expanded != candidates[-1] and _area(expanded) <= selected_area * 0.75:
            candidates.append(expanded)
    return candidates


def _scale_bbox_inside(
    bbox: tuple[int, int, int, int],
    outer: tuple[int, int, int, int],
    scale: float,
) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = bbox
    ox1, oy1, ox2, oy2 = outer
    cx = (x1 + x2) / 2
    cy = (y1 + y2) / 2
    width = min(ox2 - ox1, max(1, int(round((x2 - x1) * scale))))
    height = min(oy2 - oy1, max(1, int(round((y2 - y1) * scale))))
    nx1 = int(round(cx - width / 2))
    ny1 = int(round(cy - height / 2))
    nx2 = nx1 + width
    ny2 = ny1 + height
    if nx1 < ox1:
        nx2 += ox1 - nx1
        nx1 = ox1
    if ny1 < oy1:
        ny2 += oy1 - ny1
        ny1 = oy1
    if nx2 > ox2:
        nx1 -= nx2 - ox2
        nx2 = ox2
    if ny2 > oy2:
        ny1 -= ny2 - oy2
        ny2 = oy2
    return max(ox1, nx1), max(oy1, ny1), min(ox2, nx2), min(oy2, ny2)


def _area(bbox: tuple[int, int, int, int]) -> int:
    x1, y1, x2, y2 = bbox
    return max(0, x2 - x1) * max(0, y2 - y1)


def _target_orientation(target_size: tuple[int, int]) -> str | None:
    width, height = target_size
    if height >= width * 1.35:
        return "vertical"
    if width >= height * 1.35:
        return "horizontal"
    return None


def _layout_payload(layout, preview_path: Path, alignment: dict, target_bbox: list[int] | None = None) -> dict:
    payload = asdict(layout)
    payload["preview_path"] = str(preview_path)
    payload["target_bbox"] = target_bbox
    payload["alignment"] = alignment
    payload["validation"] = {
        "status": "deterministic_only",
        "checks": ["measured_text_bbox", "bounded_overflow"],
        "model_summary": None,
        "manual_review_required": True,
    }
    return payload


def _orientation_override(angle: dict | None) -> str | None:
    if not angle:
        return None
    orientation = angle.get("detected_orientation")
    return orientation if orientation in {"horizontal", "vertical"} else None


def _selected_orientation(target_size: tuple[int, int], angle: dict | None) -> str:
    angle_orientation = _orientation_override(angle)
    if angle_orientation and _angle_confidence(angle) >= 0.8:
        return angle_orientation
    return _target_orientation(target_size) or angle_orientation or "horizontal"


def _angle_confidence(angle: dict | None) -> float:
    if not angle:
        return 0.0
    try:
        return float(angle.get("confidence") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _angle_override(angle: dict | None) -> float:
    if not angle:
        return 0.0
    return float(angle.get("selected_angle_degrees") or 0.0)


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_report(
    output_path: Path,
    selection_run_dir: str | Path,
    angle_run_dir: str | Path | None,
    detection_run_dir: str | Path | None,
    rows: list[dict],
) -> None:
    generated = sum(1 for row in rows if row["status"] == "layout_generated")
    lines = [
        "# Phase 4 Layout Search Report",
        "",
        f"Selection run directory: `{selection_run_dir}`",
        f"Angle run directory: `{angle_run_dir or 'not provided'}`",
        f"Detection run directory: `{detection_run_dir or 'not provided'}`",
        "",
        "## Summary",
        "",
        f"- Records processed: {len(rows)}",
        f"- Layouts generated: {generated}",
        f"- Layout failures: {len(rows) - generated}",
        "",
        "## Generated Artifacts",
        "",
        "- `layout-results.jsonl`",
        "- `debug/layout_candidates/*.png`",
        "- `reports/phase4-report.md`",
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _safe_name(value: str) -> str:
    return "".join(char if char.isalnum() else "-" for char in value).strip("-") or "record"
