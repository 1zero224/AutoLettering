from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from .cleanup_runs import CleanupRunInput, format_cleanup_run_dirs, load_cleanup_rows_by_id
from .phase6_replacement_quality_gate import effective_cleanup_for_gpt_quality, load_replacement_quality_by_id
from .phase7_manifest import write_phase7_manifest
from .phase7_review import write_phase7_manual_review_csv
from .rendering.compose import compose_page_stages
from .rendering.debug_overlay import draw_page_debug_overlay


FINAL_REPLACEMENT_METHODS = {"gpt_image2_masked_edit", "cta_first_masked_edit"}
GPT_REPLACEMENT_METHOD = "gpt_image2_masked_edit"


def run_phase7_preview(
    detection_run_dir: str | Path,
    cleanup_run_dir: CleanupRunInput,
    layout_run_dir: str | Path,
    output_root: str | Path = "outputs/runs",
    run_id: str | None = None,
    sample_limit: int = 5,
    phase6_gpt_quality_run_dir: str | Path | list[str | Path] | None = None,
) -> Path:
    run_dir = Path(output_root) / (run_id or "phase7-page-preview")
    run_dir.mkdir(parents=True, exist_ok=True)
    detections = _load_detection_rows(Path(detection_run_dir) / "detections.jsonl")
    cleanups = load_cleanup_rows_by_id(cleanup_run_dir)
    replacement_quality = load_replacement_quality_by_id(phase6_gpt_quality_run_dir) if phase6_gpt_quality_run_dir is not None else None
    layouts = _load_jsonl_by_id(Path(layout_run_dir) / "layout-results.jsonl", "layout_generated")
    rows = _preview_rows(run_dir, detections, cleanups, layouts, sample_limit, replacement_quality)
    _write_jsonl(run_dir / "preview-results.jsonl", rows)
    write_phase7_manual_review_csv(run_dir / "reports" / "manual-review.csv", rows)
    write_phase7_manifest(
        run_dir / "manifest.json",
        run_dir,
        detection_run_dir,
        cleanup_run_dir,
        layout_run_dir,
        rows,
    )
    _write_report(run_dir / "reports" / "phase7-report.md", detection_run_dir, cleanup_run_dir, layout_run_dir, rows)
    return run_dir


def _load_detection_rows(path: Path) -> dict[str, dict]:
    rows: dict[str, dict] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            payload = json.loads(line)
            if payload.get("status") in {"ok", "fallback_required"}:
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
    replacement_quality: dict[str, dict] | None,
) -> list[dict]:
    records, skipped_rows = _preview_records(detections, cleanups, layouts, sample_limit, replacement_quality)
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
    replacement_quality: dict[str, dict] | None,
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
        effective_cleanup = effective_cleanup_for_gpt_quality(record_id, cleanup["cleanup"], replacement_quality)
        if layout is None and _text_overlay_required(effective_cleanup):
            skipped_rows.append(_skipped_row(record_id, "missing_layout"))
            continue
        records.append(_preview_record(detection, cleanup, layout, effective_cleanup))
    return records, skipped_rows


def _preview_record(detection: dict, cleanup: dict, layout: dict | None, effective_cleanup: dict | None = None) -> dict:
    cleanup_payload = effective_cleanup or cleanup["cleanup"]
    bbox = cleanup_payload["bbox"]
    text_overlay_required = _text_overlay_required(cleanup_payload)
    layout_payload = layout["layout"] if layout is not None else {}
    text_bbox = _text_overlay_bbox(cleanup_payload, layout_payload, bbox)
    record = {
        "record_id": detection["record_id"],
        "image_name": detection.get("image_name"),
        "translated_text": detection.get("translated_text", ""),
        "image_path": detection["image_path"],
        "bbox": bbox,
        "text_bbox": text_bbox,
        "cleanup_method": _cleanup_method(cleanup_payload),
        "cleaned_crop_path": _cleanup_crop_path(cleanup_payload),
        "cleanup_mask_path": _cleanup_mask_path(cleanup_payload),
        "layout_preview_path": layout_payload.get("preview_path", ""),
        "text_overlay_required": text_overlay_required,
    }
    record.update(_preview_provenance(cleanup, cleanup_payload))
    if cleanup_payload.get("gpt_replacement_quality") is not None:
        record["gpt_replacement_quality"] = cleanup_payload.get("gpt_replacement_quality")
    return record


def _preview_provenance(cleanup_row: dict, cleanup_payload: dict) -> dict:
    payload: dict = {}
    for key in ("replacement_failure_reason", "route", "text_region_source", "source_mask_path"):
        if cleanup_payload.get(key) is not None:
            payload[key] = cleanup_payload.get(key)
    for key in ("fallback_locator", "fallback_locator_validation"):
        if cleanup_row.get(key) is not None:
            payload[key] = cleanup_row.get(key)
    gpt_status = (cleanup_row.get("gpt_image2_edit") or {}).get("status")
    if gpt_status is not None:
        payload["gpt_image2_edit_status"] = gpt_status
    return payload


def _text_overlay_bbox(cleanup: dict, layout: dict, bbox: list[int]) -> list[int]:
    return cleanup.get("layout_text_bbox") or layout.get("target_bbox") or bbox


def _preview_page(run_dir: Path, image_name: str, records: list[dict]) -> dict:
    page_name = f"{_safe_name(image_name)}.png"
    stage_paths = compose_page_stages(
        records[0]["image_path"],
        records,
        run_dir / "pages" / "original" / page_name,
        run_dir / "pages" / "cleaned" / page_name,
        run_dir / "pages" / page_name,
    )
    debug_overlay_path = draw_page_debug_overlay(
        stage_paths["page_preview_path"],
        records,
        run_dir / "debug" / "page_overlays" / page_name,
    )
    _write_record_before_after_crops(run_dir, stage_paths["page_preview_path"], records)
    return {
        "image_name": image_name,
        "status": "page_preview_generated",
        "records": [_record_summary(record) for record in records],
        "preview": {
            "original_page_path": str(stage_paths["original_page_path"]),
            "cleaned_page_path": str(stage_paths["cleaned_page_path"]),
            "page_preview_path": str(stage_paths["page_preview_path"]),
            "debug_overlay_path": str(debug_overlay_path),
            "record_count": len(records),
        },
    }


def _record_summary(record: dict) -> dict:
    payload = {
        "record_id": record["record_id"],
        "bbox": record["bbox"],
        "text_bbox": record.get("text_bbox", record["bbox"]),
        "translated_text": record.get("translated_text", ""),
        "cleanup_method": record.get("cleanup_method"),
        "cleanup_crop_path": record.get("cleaned_crop_path", ""),
        "layout_preview_path": record.get("layout_preview_path", ""),
        "text_overlay_required": record.get("text_overlay_required", True),
        "preview_before_after_path": record.get("preview_before_after_path", ""),
    }
    _copy_optional_fields(
        payload,
        record,
        (
            "replacement_failure_reason",
            "route",
            "text_region_source",
            "source_mask_path",
            "fallback_locator",
            "fallback_locator_validation",
            "gpt_image2_edit_status",
        ),
    )
    if record.get("gpt_replacement_quality") is not None:
        payload["gpt_replacement_quality"] = record.get("gpt_replacement_quality")
    return payload


def _copy_optional_fields(target: dict, source: dict, keys: tuple[str, ...]) -> None:
    for key in keys:
        if source.get(key) is not None:
            target[key] = source.get(key)


def _cleanup_crop_path(cleanup: dict) -> str:
    if _cleanup_contains_final_replacement_text(cleanup):
        return cleanup["replacement_crop_path"]
    return cleanup["cleaned_crop_path"]


def _cleanup_mask_path(cleanup: dict) -> str | None:
    if _cleanup_contains_final_replacement_text(cleanup):
        return None
    return cleanup.get("cleanup_mask_path")


def _cleanup_method(cleanup: dict) -> str | None:
    if _cleanup_contains_final_replacement_text(cleanup):
        return cleanup.get("replacement_method")
    return cleanup.get("method")


def _text_overlay_required(cleanup: dict) -> bool:
    return not _cleanup_contains_final_replacement_text(cleanup)


def _cleanup_contains_final_replacement_text(cleanup: dict) -> bool:
    method = cleanup.get("replacement_method")
    if method not in FINAL_REPLACEMENT_METHODS or not cleanup.get("replacement_crop_path"):
        return False
    if method != GPT_REPLACEMENT_METHOD:
        return True
    quality = cleanup.get("gpt_replacement_quality")
    return not isinstance(quality, dict) or quality.get("accepted") is True


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


def _write_record_before_after_crops(run_dir: Path, preview_path: Path, records: list[dict]) -> None:
    with Image.open(records[0]["image_path"]) as original_image:
        original = original_image.convert("RGB")
    with Image.open(preview_path) as preview_image:
        preview = preview_image.convert("RGB")
    for record in records:
        output_path = run_dir / "crops" / "before_after" / f"{_safe_name(record['record_id'])}.png"
        _save_before_after_crop(original, preview, tuple(record["bbox"]), output_path)
        record["preview_before_after_path"] = str(output_path)


def _save_before_after_crop(original: Image.Image, preview: Image.Image, bbox: tuple[int, int, int, int], path: Path) -> None:
    before = original.crop(bbox)
    after = preview.crop(bbox)
    comparison = Image.new("RGB", (before.width + after.width, before.height), "white")
    comparison.paste(before, (0, 0))
    comparison.paste(after, (before.width, 0))
    path.parent.mkdir(parents=True, exist_ok=True)
    comparison.save(path)


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
        "- `manifest.json`",
        "- `preview-results.jsonl`",
        "- `pages/original/*.png`",
        "- `pages/cleaned/*.png`",
        "- `pages/*.png`",
        "- `debug/page_overlays/*.png`",
        "- `crops/before_after/*.png`",
        "- `reports/manual-review.csv`",
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _safe_name(value: str) -> str:
    return "".join(char if char.isalnum() else "-" for char in value).strip("-") or "record"
