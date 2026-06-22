from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path

from .inpaint.bubble_fill import mask_fill_text_pixels, region_fill_text_area
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
) -> Path:
    run_dir = Path(output_root) / (run_id or "phase6-bubble-cleanup")
    run_dir.mkdir(parents=True, exist_ok=True)
    detections = _load_detection_rows(Path(detection_run_dir) / "detections.jsonl")
    layouts = _load_layout_rows(Path(layout_run_dir) / "layout-results.jsonl")
    rows = _cleanup_rows(run_dir, detections, layouts, sample_limit, cleanup_method, record_ids)
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
        rows.append(_cleanup_one(run_dir, detection, layout, cleanup_method))
    return rows


def _cleanup_one(run_dir: Path, detection: dict, layout: dict, cleanup_method: str) -> dict:
    if detection.get("group_name") != "框内":
        return _skipped_row(layout, "not_bubble_group")

    text_bbox = _text_bbox(detection)
    result = _clean_bubble_crop(
        image_path=detection["image_path"],
        bbox=text_bbox,
        text_bbox=text_bbox,
        output_dir=run_dir / "crops",
        record_id=detection["record_id"],
        cleanup_method=cleanup_method,
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
    output_dir: Path,
    record_id: str,
    cleanup_method: str,
):
    if cleanup_method == "region_fill":
        return region_fill_text_area(image_path, bbox, text_bbox, output_dir, record_id)
    if cleanup_method == "mask_fill":
        return mask_fill_text_pixels(image_path, bbox, text_bbox, output_dir, record_id)
    raise ValueError(f"unsupported_bubble_cleanup_method:{cleanup_method}")


def _text_bbox(detection: dict) -> tuple[int, int, int, int]:
    return selected_text_bbox(detection)


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
