from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path

from PIL import Image

from .layout.measure import search_fitting_layout
from .layout.render_text import measure_preview_alignment, render_layout_preview


def run_phase4(
    selection_run_dir: str | Path,
    angle_run_dir: str | Path | None = None,
    detection_run_dir: str | Path | None = None,
    output_root: str | Path = "outputs/runs",
    run_id: str | None = None,
    sample_limit: int = 5,
) -> Path:
    run_dir = Path(output_root) / (run_id or "phase4-layout-search")
    run_dir.mkdir(parents=True, exist_ok=True)
    selections = _load_selected_fonts(Path(selection_run_dir) / "font-selections.jsonl", sample_limit)
    angle_rows = _load_angle_rows(angle_run_dir)
    detection_rows = _load_detection_rows(detection_run_dir)
    rows = [_layout_record(run_dir, row, angle_rows, detection_rows) for row in selections]
    _write_jsonl(run_dir / "layout-results.jsonl", rows)
    _write_report(run_dir / "reports" / "phase4-report.md", selection_run_dir, angle_run_dir, detection_run_dir, rows)
    return run_dir


def _load_selected_fonts(path: Path, sample_limit: int) -> list[dict]:
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if len(rows) >= sample_limit:
                break
            payload = json.loads(line)
            if payload.get("status") == "selected" and payload.get("selected_font"):
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
    target_bbox = _layout_target_bbox(row, detection_rows)
    target_size = _bbox_size(target_bbox) if target_bbox else _target_size_from_comparison(row)
    angle = angle_rows.get(row["record_id"])
    orientation = _target_orientation(target_size) or _orientation_override(angle)
    angle_degrees = _angle_override(angle) if orientation == _orientation_override(angle) else 0.0
    layout = search_fitting_layout(
        row.get("translated_text", ""),
        font_path,
        target_size,
        orientation=orientation,
        angle_degrees=angle_degrees,
    )
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


def _layout_target_bbox(row: dict, detection_rows: dict[str, dict]) -> list[int] | None:
    detection = detection_rows.get(row["record_id"])
    if detection is None:
        return None
    return list(_text_bbox(detection))


def _text_bbox(detection: dict) -> tuple[int, int, int, int]:
    selected = tuple(detection["selected_text_box_xyxy"])
    selected_area = _area(selected)
    text_candidates = [_candidate_xyxy(item) for item in detection.get("candidate_boxes") or []]
    text_candidates = [
        bbox
        for bbox in text_candidates
        if bbox and _inside(bbox, selected) and 0 < _area(bbox) <= selected_area * 0.35
    ]
    return _union_bbox(text_candidates) if text_candidates else selected


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


def _union_bbox(bboxes: list[tuple[int, int, int, int]]) -> tuple[int, int, int, int]:
    return (
        min(bbox[0] for bbox in bboxes),
        min(bbox[1] for bbox in bboxes),
        max(bbox[2] for bbox in bboxes),
        max(bbox[3] for bbox in bboxes),
    )


def _bbox_size(bbox: list[int]) -> tuple[int, int]:
    x1, y1, x2, y2 = bbox
    return x2 - x1, y2 - y1


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
