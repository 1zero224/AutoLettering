from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path

from PIL import Image

from .inpaint.bubble_fill import mask_fill_text_pixels, region_fill_text_area, soft_region_fill_text_area, text_mask_inpaint
from .inpaint.mask_refinement import MaskRefinementOptions, refine_cleanup_artifacts
from .record_selection import normalize_record_ids, row_matches_record_ids
from .text_bbox import selected_text_bbox
from .text_mask_bbox import selected_text_mask_bbox


def run_phase6_bubble_cleanup(
    detection_run_dir: str | Path,
    layout_run_dir: str | Path,
    output_root: str | Path = "outputs/runs",
    run_id: str | None = None,
    sample_limit: int = 5,
    cleanup_method: str = "region_fill",
    record_ids: list[str] | None = None,
    inpaint_method: str = "opencv_telea",
    mask_dilate_px: int = 3,
    mask_adjust_dilate_px: int = 0,
    mask_adjust_erode_px: int = 0,
    mask_extend_left_px: int = 0,
    mask_extend_right_px: int = 0,
    mask_extend_up_px: int = 0,
    mask_extend_down_px: int = 0,
) -> Path:
    run_dir = Path(output_root) / (run_id or "phase6-bubble-cleanup")
    run_dir.mkdir(parents=True, exist_ok=True)
    detections = _load_detection_rows(Path(detection_run_dir) / "detections.jsonl")
    layouts = _load_layout_rows(Path(layout_run_dir) / "layout-results.jsonl")
    refinement_options = MaskRefinementOptions(
        dilate_px=mask_adjust_dilate_px,
        erode_px=mask_adjust_erode_px,
        extend_left_px=mask_extend_left_px,
        extend_right_px=mask_extend_right_px,
        extend_up_px=mask_extend_up_px,
        extend_down_px=mask_extend_down_px,
    )
    rows = _cleanup_rows(
        run_dir,
        detections,
        layouts,
        sample_limit,
        cleanup_method,
        record_ids,
        inpaint_method,
        mask_dilate_px,
        refinement_options,
    )
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
    mask_dilate_px: int = 3,
    refinement_options: MaskRefinementOptions | None = None,
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
        rows.append(_cleanup_one(run_dir, detection, layout, cleanup_method, inpaint_method, mask_dilate_px, refinement_options))
    return rows


def _cleanup_one(
    run_dir: Path,
    detection: dict,
    layout: dict,
    cleanup_method: str,
    inpaint_method: str,
    mask_dilate_px: int,
    refinement_options: MaskRefinementOptions | None,
) -> dict:
    if detection.get("group_name") != "框内":
        return _skipped_row(layout, "not_bubble_group")

    text_bbox = _text_bbox(detection)
    mask_bbox = _mask_bbox(detection)
    result = _clean_bubble_crop(
        image_path=detection["image_path"],
        bbox=text_bbox,
        text_bbox=text_bbox,
        mask_bbox=mask_bbox,
        output_dir=run_dir / "crops",
        record_id=detection["record_id"],
        cleanup_method=cleanup_method,
        inpaint_method=inpaint_method,
        mask_dilate_px=mask_dilate_px,
    )
    refinement = _refine_cleanup_result(run_dir, result, detection["record_id"], refinement_options)
    return {
        "record_id": detection["record_id"],
        "image_name": detection.get("image_name"),
        "translated_text": detection.get("translated_text", ""),
        "status": "cleaned",
        "cleanup": _cleanup_payload(result, cleanup_method, text_bbox, mask_bbox, mask_dilate_px, refinement),
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
    mask_dilate_px: int = 3,
):
    if cleanup_method == "region_fill":
        return region_fill_text_area(image_path, bbox, text_bbox, output_dir, record_id)
    if cleanup_method == "soft_region_fill":
        return soft_region_fill_text_area(image_path, _context_bbox(image_path, text_bbox), text_bbox, output_dir, record_id)
    if cleanup_method == "mask_fill":
        return mask_fill_text_pixels(image_path, bbox, mask_bbox, output_dir, record_id)
    if cleanup_method == "text_mask_inpaint":
        return text_mask_inpaint(image_path, bbox, text_bbox, output_dir, record_id, inpaint_method, mask_bbox=mask_bbox, dilate_px=mask_dilate_px)
    raise ValueError(f"unsupported_bubble_cleanup_method:{cleanup_method}")


def _context_bbox(image_path: str | Path, bbox: tuple[int, int, int, int], padding_px: int = 10) -> tuple[int, int, int, int]:
    with Image.open(image_path) as image:
        width, height = image.size
    x1, y1, x2, y2 = bbox
    return max(0, x1 - padding_px), max(0, y1 - padding_px), min(width, x2 + padding_px), min(height, y2 + padding_px)


def _text_bbox(detection: dict) -> tuple[int, int, int, int]:
    return _phase2_bbox(detection, "selected_text_full_xyxy") or selected_text_bbox(detection)


def _mask_bbox(detection: dict) -> tuple[int, int, int, int]:
    text_bbox = _text_bbox(detection)
    mask_bbox = selected_text_mask_bbox(detection)
    if _prefer_mask_bbox(mask_bbox, text_bbox):
        return mask_bbox
    return text_bbox


def _phase2_bbox(detection: dict, key: str) -> tuple[int, int, int, int] | None:
    xyxy = detection.get(key)
    if not isinstance(xyxy, list) or len(xyxy) != 4:
        return None
    return tuple(int(value) for value in xyxy)


def _prefer_mask_bbox(
    mask_bbox: tuple[int, int, int, int],
    text_bbox: tuple[int, int, int, int],
) -> bool:
    return (
        mask_bbox != text_bbox
        and _inside(mask_bbox, text_bbox)
        and _area(mask_bbox) <= _area(text_bbox) * 0.75
        and _height(mask_bbox) <= _height(text_bbox) * 0.9
    )


def _cleanup_payload(
    result,
    cleanup_method: str,
    text_bbox: tuple[int, int, int, int] | None = None,
    mask_bbox: tuple[int, int, int, int] | None = None,
    mask_dilate_px: int = 3,
    refinement=None,
) -> dict:
    payload = asdict(result)
    payload["bbox"] = list(result.bbox)
    payload["fill_color"] = list(result.fill_color)
    payload["before_crop_path"] = str(result.before_crop_path)
    payload["cleaned_crop_path"] = str(result.cleaned_crop_path)
    payload["cleanup_mask_path"] = str(result.cleanup_mask_path) if result.cleanup_mask_path else None
    payload["before_after_path"] = str(result.before_after_path)
    if refinement is not None:
        payload["cleaned_crop_path"] = str(refinement.refined_cleaned_crop_path)
        payload["cleanup_mask_path"] = str(refinement.refined_mask_path)
        payload["before_after_path"] = str(refinement.before_after_path)
        payload["mask_refinement"] = _mask_refinement_payload(refinement)
    if text_bbox is not None:
        payload["text_bbox"] = list(text_bbox)
    if mask_bbox is not None:
        payload["mask_bbox"] = list(mask_bbox)
    if cleanup_method == "text_mask_inpaint":
        payload["mask_dilate_px"] = mask_dilate_px
    layout_text_bbox = _layout_text_bbox(cleanup_method, text_bbox, mask_bbox)
    if layout_text_bbox is not None:
        payload["layout_text_bbox"] = list(layout_text_bbox)
    return payload


def _refine_cleanup_result(run_dir: Path, result, record_id: str, options: MaskRefinementOptions | None):
    if options is None or not options.enabled() or result.cleanup_mask_path is None:
        return None
    return refine_cleanup_artifacts(
        before_crop_path=result.before_crop_path,
        cleaned_crop_path=result.cleaned_crop_path,
        source_mask_path=result.cleanup_mask_path,
        fill_color=result.fill_color,
        output_dir=run_dir / "mask_refinement",
        record_id=record_id,
        options=options,
    )


def _mask_refinement_payload(refinement) -> dict:
    return {
        "schema_version": refinement.schema_version,
        "operations": refinement.operations,
        "source_mask_path": str(refinement.source_mask_path),
        "refined_mask_path": str(refinement.refined_mask_path),
        "mask_overlay_path": str(refinement.mask_overlay_path),
        "refined_cleaned_crop_path": str(refinement.refined_cleaned_crop_path),
        "before_after_path": str(refinement.before_after_path),
        "input_mask_pixel_count": refinement.input_mask_pixel_count,
        "output_mask_pixel_count": refinement.output_mask_pixel_count,
    }


def _layout_text_bbox(
    cleanup_method: str,
    text_bbox: tuple[int, int, int, int] | None,
    mask_bbox: tuple[int, int, int, int] | None,
) -> tuple[int, int, int, int] | None:
    if cleanup_method in {"mask_fill", "text_mask_inpaint"} and mask_bbox is not None:
        return mask_bbox
    return text_bbox


def _inside(inner: tuple[int, int, int, int], outer: tuple[int, int, int, int]) -> bool:
    ix1, iy1, ix2, iy2 = inner
    ox1, oy1, ox2, oy2 = outer
    return ox1 <= ix1 < ix2 <= ox2 and oy1 <= iy1 < iy2 <= oy2


def _height(bbox: tuple[int, int, int, int]) -> int:
    return max(0, bbox[3] - bbox[1])


def _area(bbox: tuple[int, int, int, int]) -> int:
    x1, y1, x2, y2 = bbox
    return max(0, x2 - x1) * max(0, y2 - y1)


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
    refined = sum(1 for row in rows if (row.get("cleanup") or {}).get("mask_refinement"))
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
        f"- Mask refinement applied: {refined}",
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
