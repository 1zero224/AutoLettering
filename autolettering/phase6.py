from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path

from PIL import Image

from .inpaint.bubble_fill import mask_fill_text_pixels, region_fill_text_area, soft_region_fill_text_area, text_mask_inpaint
from .record_selection import normalize_record_ids, row_matches_record_ids
from .text_bbox import selected_text_bbox


def run_phase6_bubble_cleanup(
    detection_run_dir: str | Path,
    layout_run_dir: str | Path,
    output_root: str | Path = "outputs/runs",
    run_id: str | None = None,
    sample_limit: int = 5,
    cleanup_method: str = "region_fill",
    record_ids: list[str] | None = None,
    inpaint_method: str = "opencv_telea",
) -> Path:
    run_dir = Path(output_root) / (run_id or "phase6-bubble-cleanup")
    run_dir.mkdir(parents=True, exist_ok=True)
    detections = _load_detection_rows(Path(detection_run_dir) / "detections.jsonl")
    layouts = _load_layout_rows(Path(layout_run_dir) / "layout-results.jsonl")
    rows = _cleanup_rows(run_dir, detections, layouts, sample_limit, cleanup_method, record_ids, inpaint_method)
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


def _cleanup_rows(
    run_dir: Path,
    detections: dict[str, dict],
    layouts: list[dict],
    sample_limit: int,
    cleanup_method: str,
    record_ids: list[str] | None = None,
    inpaint_method: str = "opencv_telea",
) -> list[dict]:
    wanted = normalize_record_ids(record_ids)
    rows: list[dict] = []
    for layout in layouts:
        if not row_matches_record_ids(layout, wanted):
            continue
        if len(rows) >= sample_limit:
            break
        detection = detections.get(layout["record_id"])
        if detection is None:
            rows.append(_skipped_row(layout, "missing_detection"))
            continue
        rows.append(_cleanup_one(run_dir, detection, layout, cleanup_method, inpaint_method))
    return rows


def _cleanup_one(run_dir: Path, detection: dict, layout: dict, cleanup_method: str, inpaint_method: str) -> dict:
    if detection.get("group_name") != "框内":
        return _skipped_row(layout, "not_bubble_group")

    text_bbox = _text_bbox(detection)
    result = _clean_bubble_crop(
        image_path=detection["image_path"],
        bbox=text_bbox,
        text_bbox=text_bbox,
        mask_bbox=_mask_bbox(detection),
        output_dir=run_dir / "crops",
        record_id=detection["record_id"],
        cleanup_method=cleanup_method,
        inpaint_method=inpaint_method,
    )
    return {
        "record_id": detection["record_id"],
        "image_name": detection.get("image_name"),
        "translated_text": detection.get("translated_text", ""),
        "status": "cleaned",
        "cleanup": _cleanup_payload(result),
    }


def _clean_bubble_crop(
    image_path: str | Path,
    bbox: tuple[int, int, int, int],
    text_bbox: tuple[int, int, int, int],
    mask_bbox: tuple[int, int, int, int],
    output_dir: Path,
    record_id: str,
    cleanup_method: str,
    inpaint_method: str = "opencv_telea",
):
    if cleanup_method == "region_fill":
        return region_fill_text_area(image_path, bbox, text_bbox, output_dir, record_id)
    if cleanup_method == "soft_region_fill":
        return soft_region_fill_text_area(image_path, _context_bbox(image_path, text_bbox), text_bbox, output_dir, record_id)
    if cleanup_method == "mask_fill":
        return mask_fill_text_pixels(image_path, bbox, mask_bbox, output_dir, record_id)
    if cleanup_method == "text_mask_inpaint":
        return text_mask_inpaint(image_path, bbox, text_bbox, output_dir, record_id, inpaint_method, mask_bbox=mask_bbox)
    raise ValueError(f"unsupported_bubble_cleanup_method:{cleanup_method}")


def _context_bbox(image_path: str | Path, bbox: tuple[int, int, int, int], padding_px: int = 10) -> tuple[int, int, int, int]:
    with Image.open(image_path) as image:
        width, height = image.size
    x1, y1, x2, y2 = bbox
    return max(0, x1 - padding_px), max(0, y1 - padding_px), min(width, x2 + padding_px), min(height, y2 + padding_px)


def _text_bbox(detection: dict) -> tuple[int, int, int, int]:
    return selected_text_bbox(detection)


def _mask_bbox(detection: dict) -> tuple[int, int, int, int]:
    selected = _selected_bbox(detection)
    if selected is None:
        return _text_bbox(detection)
    candidates = [_candidate(item) for item in detection.get("candidate_boxes") or []]
    candidates = [candidate for candidate in candidates if candidate is not None]
    selected_candidate = next((candidate for candidate in candidates if candidate["bbox"] == selected), None)
    if selected_candidate is None:
        return selected

    cluster = [selected_candidate]
    previous_len = -1
    while previous_len != len(cluster):
        previous_len = len(cluster)
        cluster_bbox = _union_bbox([candidate["bbox"] for candidate in cluster])
        for candidate in candidates:
            if candidate in cluster:
                continue
            if _same_text_mask_cluster(candidate, selected_candidate, cluster_bbox):
                cluster.append(candidate)
    return _union_bbox([candidate["bbox"] for candidate in cluster])


def _selected_bbox(detection: dict) -> tuple[int, int, int, int] | None:
    xyxy = detection.get("selected_text_box_xyxy")
    if isinstance(xyxy, list) and len(xyxy) == 4:
        return tuple(int(value) for value in xyxy)
    return None


def _candidate(item: dict) -> dict | None:
    xyxy = item.get("xyxy")
    if not isinstance(xyxy, list) or len(xyxy) != 4:
        return None
    score = item.get("score")
    return {
        "bbox": tuple(int(value) for value in xyxy),
        "score": float(score) if isinstance(score, (int, float)) else None,
        "polarity": item.get("polarity"),
    }


def _same_text_mask_cluster(
    candidate: dict,
    selected: dict,
    cluster_bbox: tuple[int, int, int, int],
    score_margin: float = 0.08,
) -> bool:
    bbox = candidate["bbox"]
    selected_bbox = selected["bbox"]
    if bbox == selected_bbox:
        return True
    if selected["polarity"] in {"dark_on_light", "light_on_dark"} and candidate["polarity"] != selected["polarity"]:
        return False
    if selected["score"] is not None and candidate["score"] is not None and candidate["score"] < selected["score"] - score_margin:
        return False

    selected_height = _height(selected_bbox)
    top_slack = max(24, min(64, int(round(selected_height * 0.35))))
    top_aligned_with_selected = (
        abs(bbox[1] - selected_bbox[1]) <= top_slack
        and _vertical_overlap_ratio(bbox, selected_bbox) >= 0.45
    )
    touches_cluster = (
        _vertical_relation(bbox, cluster_bbox) <= max(24, int(round(selected_height * 0.15)))
        and _vertical_overlap_ratio(bbox, cluster_bbox) >= 0.15
    )
    return (
        (top_aligned_with_selected or touches_cluster)
        and _horizontal_gap(bbox, cluster_bbox) <= max(36, int(round(_width(selected_bbox) * 1.25)))
        and _width(bbox) <= max(96, int(round(_width(selected_bbox) * 2.5)))
    )


def _union_bbox(bboxes: list[tuple[int, int, int, int]]) -> tuple[int, int, int, int]:
    return (
        min(bbox[0] for bbox in bboxes),
        min(bbox[1] for bbox in bboxes),
        max(bbox[2] for bbox in bboxes),
        max(bbox[3] for bbox in bboxes),
    )


def _width(bbox: tuple[int, int, int, int]) -> int:
    return max(0, bbox[2] - bbox[0])


def _height(bbox: tuple[int, int, int, int]) -> int:
    return max(0, bbox[3] - bbox[1])


def _horizontal_gap(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> int:
    return max(0, max(a[0], b[0]) - min(a[2], b[2]))


def _vertical_overlap_ratio(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
    overlap = min(a[3], b[3]) - max(a[1], b[1])
    if overlap <= 0:
        return 0.0
    return overlap / max(1, min(_height(a), _height(b)))


def _vertical_relation(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> int:
    overlap = min(a[3], b[3]) - max(a[1], b[1])
    if overlap > 0:
        return 0
    return max(0, max(a[1], b[1]) - min(a[3], b[3]))


def _cleanup_payload(result) -> dict:
    payload = asdict(result)
    payload["bbox"] = list(result.bbox)
    payload["fill_color"] = list(result.fill_color)
    payload["before_crop_path"] = str(result.before_crop_path)
    payload["cleaned_crop_path"] = str(result.cleaned_crop_path)
    payload["cleanup_mask_path"] = str(result.cleanup_mask_path) if result.cleanup_mask_path else None
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
