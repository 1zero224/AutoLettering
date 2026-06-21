from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path

from .inpaint.bubble_fill import mask_fill_text_pixels


def run_phase6_bubble_cleanup(
    detection_run_dir: str | Path,
    layout_run_dir: str | Path,
    output_root: str | Path = "outputs/runs",
    run_id: str | None = None,
    sample_limit: int = 5,
) -> Path:
    run_dir = Path(output_root) / (run_id or "phase6-bubble-cleanup")
    run_dir.mkdir(parents=True, exist_ok=True)
    detections = _load_detection_rows(Path(detection_run_dir) / "detections.jsonl")
    layouts = _load_layout_rows(Path(layout_run_dir) / "layout-results.jsonl")
    rows = _cleanup_rows(run_dir, detections, layouts, sample_limit)
    _write_jsonl(run_dir / "cleanup-results.jsonl", rows)
    _write_report(run_dir / "reports" / "phase6-report.md", detection_run_dir, layout_run_dir, rows)
    return run_dir


def _load_detection_rows(path: Path) -> dict[str, dict]:
    rows: dict[str, dict] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            payload = json.loads(line)
            if payload.get("status") == "ok":
                rows[payload["record_id"]] = payload
    return rows


def _load_layout_rows(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            payload = json.loads(line)
            if payload.get("status") == "layout_generated":
                rows.append(payload)
    return rows


def _cleanup_rows(run_dir: Path, detections: dict[str, dict], layouts: list[dict], sample_limit: int) -> list[dict]:
    rows: list[dict] = []
    for layout in layouts:
        if len(rows) >= sample_limit:
            break
        detection = detections.get(layout["record_id"])
        if detection is None:
            rows.append(_skipped_row(layout, "missing_detection"))
            continue
        rows.append(_cleanup_one(run_dir, detection, layout))
    return rows


def _cleanup_one(run_dir: Path, detection: dict, layout: dict) -> dict:
    if detection.get("group_name") != "框内":
        return _skipped_row(layout, "not_bubble_group")

    result = mask_fill_text_pixels(
        image_path=detection["image_path"],
        bbox=tuple(detection["selected_text_box_xyxy"]),
        text_bbox=_text_bbox(detection),
        output_dir=run_dir / "crops",
        record_id=detection["record_id"],
    )
    return {
        "record_id": detection["record_id"],
        "image_name": detection.get("image_name"),
        "translated_text": detection.get("translated_text", ""),
        "status": "cleaned",
        "cleanup": _cleanup_payload(result),
    }


def _text_bbox(detection: dict) -> tuple[int, int, int, int]:
    selected = tuple(detection["selected_text_box_xyxy"])
    candidates = detection.get("candidate_boxes") or []
    selected_area = _area(selected)
    text_candidates = [_candidate_xyxy(item) for item in candidates]
    text_candidates = [
        bbox
        for bbox in text_candidates
        if bbox and _inside(bbox, selected) and 0 < _area(bbox) <= selected_area * 0.35
    ]
    if not text_candidates:
        return selected
    return _union_bbox(text_candidates)


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


def _cleanup_payload(result) -> dict:
    payload = asdict(result)
    payload["bbox"] = list(result.bbox)
    payload["fill_color"] = list(result.fill_color)
    payload["before_crop_path"] = str(result.before_crop_path)
    payload["cleaned_crop_path"] = str(result.cleaned_crop_path)
    payload["before_after_path"] = str(result.before_after_path)
    return payload


def _skipped_row(layout: dict, reason: str) -> dict:
    return {
        "record_id": layout.get("record_id"),
        "image_name": layout.get("image_name"),
        "translated_text": layout.get("translated_text", ""),
        "status": "skipped",
        "cleanup": {"method": None, "failure_reason": reason},
    }


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_report(output_path: Path, detection_run_dir: str | Path, layout_run_dir: str | Path, rows: list[dict]) -> None:
    cleaned = sum(1 for row in rows if row["status"] == "cleaned")
    skipped = len(rows) - cleaned
    lines = [
        "# Phase 6 Bubble Cleanup Report",
        "",
        f"Detection run directory: `{detection_run_dir}`",
        f"Layout run directory: `{layout_run_dir}`",
        "",
        "## Summary",
        "",
        f"- Records processed: {len(rows)}",
        f"- Cleaned: {cleaned}",
        f"- Skipped: {skipped}",
        "",
        "## Generated Artifacts",
        "",
        "- `cleanup-results.jsonl`",
        "- `crops/before/*.png`",
        "- `crops/cleaned/*.png`",
        "- `crops/before_after/*.png`",
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
