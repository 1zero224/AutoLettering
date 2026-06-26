from __future__ import annotations

import json
from pathlib import Path

from .rendering.compose import compose_page_records
from .cleanup_runs import CleanupRunInput, format_cleanup_run_dirs, load_cleanup_rows_by_id
from .export.photoshop import build_photoshop_manifest, write_json, write_photoshop_import_jsx
from .phase6_replacement_quality_gate import effective_cleanup_for_gpt_quality, load_replacement_quality_by_id

GPT_REPLACEMENT_METHOD = "gpt_image2_masked_edit"


def run_phase8_photoshop_export(
    detection_run_dir: str | Path,
    font_selection_run_dir: str | Path,
    layout_run_dir: str | Path,
    cleanup_run_dir: CleanupRunInput,
    output_root: str | Path = "outputs/runs",
    run_id: str | None = None,
    sample_limit: int = 5,
    font_mapping_path: str | Path | None = None,
    preview_run_dir: str | Path | None = None,
    phase6_gpt_quality_run_dir: str | Path | list[str | Path] | None = None,
) -> Path:
    run_dir = Path(output_root) / (run_id or "phase8-photoshop-export")
    run_dir.mkdir(parents=True, exist_ok=True)
    font_mapping = _load_font_mapping(font_mapping_path)
    detection_rows = _load_jsonl_by_id(Path(detection_run_dir) / "detections.jsonl", {"ok", "fallback_required"})
    cleanup_rows = load_cleanup_rows_by_id(cleanup_run_dir)
    replacement_quality = load_replacement_quality_by_id(phase6_gpt_quality_run_dir) if phase6_gpt_quality_run_dir is not None else None
    effective_cleanup_rows = _effective_cleanup_rows(cleanup_rows, replacement_quality)
    repaired_pages = _load_repaired_pages(preview_run_dir)
    repaired_pages.update(_synthesize_repaired_pages(run_dir, detection_rows, effective_cleanup_rows, repaired_pages))
    manifest = build_photoshop_manifest(
        detection_rows=detection_rows,
        font_rows=_load_jsonl_by_id(Path(font_selection_run_dir) / "font-selections.jsonl", "selected"),
        layout_rows=_load_jsonl(Path(layout_run_dir) / "layout-results.jsonl", "layout_generated"),
        cleanup_rows=effective_cleanup_rows,
        sample_limit=sample_limit,
        font_mapping=font_mapping,
        repaired_pages=repaired_pages,
    )
    write_json(run_dir / "photoshop-manifest.json", manifest)
    write_photoshop_import_jsx(run_dir / "photoshop-import.jsx")
    _write_report(
        run_dir / "reports" / "phase8-report.md",
        detection_run_dir,
        font_selection_run_dir,
        layout_run_dir,
        cleanup_run_dir,
        manifest,
        font_mapping_path,
        preview_run_dir,
    )
    _write_photoshop_validation_checklist(run_dir / "reports" / "photoshop-validation-checklist.md", manifest, font_mapping_path)
    return run_dir


def _effective_cleanup_rows(cleanup_rows: dict[str, dict], replacement_quality: dict[str, dict] | None) -> dict[str, dict]:
    rows: dict[str, dict] = {}
    for record_id, row in cleanup_rows.items():
        payload = dict(row)
        payload["cleanup"] = effective_cleanup_for_gpt_quality(record_id, row.get("cleanup") or {}, replacement_quality)
        rows[record_id] = payload
    return rows


def _synthesize_repaired_pages(
    run_dir: Path,
    detection_rows: dict[str, dict],
    cleanup_rows: dict[str, dict],
    existing_repaired_pages: dict[str, dict],
) -> dict[str, dict]:
    records_by_image: dict[str, list[dict]] = {}
    image_paths: dict[str, str] = {}
    for record_id, cleanup_row in cleanup_rows.items():
        detection = detection_rows.get(record_id)
        if detection is None:
            continue
        image_name = detection.get("image_name")
        image_path = detection.get("image_path")
        if not image_name or not image_path or image_name in existing_repaired_pages:
            continue
        record = _cleanup_record_for_page(detection, cleanup_row)
        if record is None:
            continue
        records_by_image.setdefault(image_name, []).append(record)
        image_paths[image_name] = image_path

    repaired: dict[str, dict] = {}
    for image_name, records in records_by_image.items():
        output_path = run_dir / "repaired_pages" / f"{_safe_name(image_name)}.png"
        compose_page_records(image_paths[image_name], _repair_image_records(records), output_path)
        repaired[image_name] = {
            "image_path": image_paths[image_name],
            "repaired_image_path": str(output_path),
            "repair_sources": [_repair_source_payload(record) for record in records],
        }
    return repaired


def _repair_image_records(records: list[dict]) -> list[dict]:
    return [{**record, "text_overlay_required": False, "layout_preview_path": ""} for record in records]


def _cleanup_record_for_page(detection: dict, cleanup_row: dict) -> dict | None:
    cleanup = cleanup_row.get("cleanup") or {}
    contains_final_replacement = _cleanup_contains_final_replacement_text(cleanup)
    cleaned_path = cleanup.get("replacement_crop_path") if contains_final_replacement else cleanup.get("cleaned_crop_path")
    bbox = cleanup.get("bbox") or detection.get("selected_text_box_xyxy")
    if not cleaned_path or not bbox or not Path(cleaned_path).exists():
        return None
    return {
        "record_id": detection.get("record_id"),
        "bbox": [int(value) for value in bbox],
        "cleaned_crop_path": cleaned_path,
        "cleanup_method": cleanup.get("method"),
        "replacement_method": cleanup.get("replacement_method") if contains_final_replacement else None,
        "effective_method": cleanup.get("replacement_method") if contains_final_replacement else cleanup.get("method"),
        "effective_crop_path": cleaned_path,
        "cleanup_mask_path": None if contains_final_replacement else cleanup.get("cleanup_mask_path"),
        "source_mask_path": _source_mask_path(cleanup, detection),
        "route": _cleanup_route(cleanup, detection, cleanup_row),
        "text_region_source": _text_region_source(cleanup, detection),
        "fallback_locator": cleanup_row.get("fallback_locator"),
        "fallback_locator_validation": cleanup_row.get("fallback_locator_validation"),
        "gpt_image2_edit_status": (cleanup_row.get("gpt_image2_edit") or {}).get("status"),
        "layout_preview_path": "",
        "text_overlay_required": _cleanup_needs_text_overlay(cleanup, contains_final_replacement),
        "gpt_replacement_quality": cleanup.get("gpt_replacement_quality"),
    }


def _cleanup_needs_text_overlay(cleanup: dict, contains_final_replacement: bool) -> bool:
    if contains_final_replacement:
        return False
    quality = cleanup.get("gpt_replacement_quality")
    if isinstance(quality, dict) and quality.get("accepted") is not True:
        return True
    return bool(cleanup.get("text_overlay_required", False))


def _cleanup_contains_final_replacement_text(cleanup: dict) -> bool:
    if cleanup.get("replacement_method") != GPT_REPLACEMENT_METHOD or not cleanup.get("replacement_crop_path"):
        return False
    quality = cleanup.get("gpt_replacement_quality")
    return not isinstance(quality, dict) or quality.get("accepted") is True


def _source_mask_path(cleanup: dict, detection: dict) -> str | None:
    if cleanup.get("source_mask_path"):
        return cleanup.get("source_mask_path")
    if detection.get("text_region_mask_path"):
        return detection.get("text_region_mask_path")
    ctd_match = _ctd_match_payload(detection)
    if ctd_match.get("mask_path"):
        return ctd_match.get("mask_path")
    return cleanup.get("text_mask_path")


def _text_region_source(cleanup: dict, detection: dict) -> str | None:
    if cleanup.get("text_region_source"):
        return cleanup.get("text_region_source")
    if detection.get("text_region_source"):
        return detection.get("text_region_source")
    if _ctd_match_payload(detection).get("status") == "matched":
        return "ctd_refined_mask_component"
    if (cleanup.get("replacement_method") == "gpt_image2_masked_edit" or cleanup.get("gpt_replacement_quality")) and _is_fallback_detection(detection):
        return "mimo_vision_model"
    return None


def _cleanup_route(cleanup: dict, detection: dict, cleanup_row: dict) -> str | None:
    if cleanup.get("route"):
        return cleanup.get("route")
    route = detection.get("lettering_route") or {}
    if isinstance(route, dict) and route.get("route"):
        return route.get("route")
    if _ctd_match_payload(detection).get("status") == "matched" and "lama_large" in str(cleanup.get("method", "")):
        return "cta_mask_lama_large_512px"
    gpt_edit = cleanup_row.get("gpt_image2_edit") or {}
    if (
        cleanup.get("replacement_method") == "gpt_image2_masked_edit"
        or cleanup.get("gpt_replacement_quality")
        or gpt_edit.get("status") == "ok"
    ) and _is_fallback_detection(detection):
        return "mimo_locator_gpt_image2_masked_edit"
    return None


def _is_fallback_detection(detection: dict) -> bool:
    return detection.get("status") == "fallback_required" or isinstance(detection.get("fallback"), dict)


def _ctd_match_payload(detection: dict) -> dict:
    match = detection.get("cta_match") or detection.get("ctd_match") or {}
    return match if isinstance(match, dict) else {}


def _repair_source_payload(record: dict) -> dict:
    payload = {
        "record_id": record.get("record_id"),
        "bbox_xyxy": record.get("bbox"),
        "cleanup_method": record.get("cleanup_method"),
        "replacement_method": record.get("replacement_method"),
        "effective_method": record.get("effective_method"),
        "effective_crop_path": record.get("effective_crop_path") or record.get("cleaned_crop_path"),
        "route": record.get("route"),
        "text_region_source": record.get("text_region_source"),
        "source_mask_path": record.get("source_mask_path"),
        "fallback_locator": _compact_locator_payload(record.get("fallback_locator")),
        "fallback_locator_validation": _compact_validation_payload(record.get("fallback_locator_validation")),
        "gpt_image2_edit_status": record.get("gpt_image2_edit_status"),
        "text_overlay_required": bool(record.get("text_overlay_required", False)),
    }
    if record.get("gpt_replacement_quality") is not None:
        payload["gpt_replacement_quality"] = record.get("gpt_replacement_quality")
    return payload


def _compact_locator_payload(locator: object) -> dict | None:
    if not isinstance(locator, dict):
        return None
    return {
        "status": locator.get("status"),
        "local_bbox_xyxy": locator.get("local_bbox_xyxy"),
        "global_bbox_xyxy": locator.get("global_bbox_xyxy"),
        "confidence": locator.get("confidence"),
        "locator_image_path": locator.get("locator_image_path"),
    }


def _compact_validation_payload(validation: object) -> dict | None:
    if not isinstance(validation, dict):
        return None
    return {
        "status": validation.get("status"),
        "semantic_correct": validation.get("semantic_correct"),
        "tight_enough": validation.get("tight_enough"),
        "validation_image_path": validation.get("validation_image_path"),
    }


def _safe_name(value: str) -> str:
    return "".join(char if char.isalnum() else "-" for char in value).strip("-") or "page"


def _load_font_mapping(path: str | Path | None) -> dict[str, str]:
    if path is None:
        return {}
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return {str(key): str(value) for key, value in payload.items() if value}


def _load_repaired_pages(path: str | Path | None) -> dict[str, dict]:
    if path is None:
        return {}
    run_dir = Path(path)
    repaired = _load_repaired_pages_from_manifest(run_dir / "manifest.json")
    preview_results_path = run_dir / "preview-results.jsonl"
    if not preview_results_path.exists():
        return repaired
    rows = _load_jsonl(preview_results_path, "page_preview_generated")
    for row in rows:
        cleaned = row.get("preview", {}).get("cleaned_page_path")
        image_name = row.get("image_name")
        if not image_name or not cleaned:
            continue
        existing = repaired.get(image_name, {})
        repaired[image_name] = {
            **existing,
            "image_path": row.get("preview", {}).get("original_page_path") or existing.get("image_path"),
            "repaired_image_path": cleaned,
            "repair_sources": existing.get("repair_sources") or _preview_repair_sources(row),
        }
    return repaired


def _load_repaired_pages_from_manifest(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    repaired: dict[str, dict] = {}
    for page in payload.get("pages", []):
        image_name = page.get("image_name")
        cleaned = page.get("cleaned_page_path")
        if image_name and cleaned:
            repaired[image_name] = {
                "image_path": page.get("original_page_path"),
                "repaired_image_path": cleaned,
                "repair_sources": _preview_repair_sources(page),
            }
    return repaired


def _preview_repair_sources(page: dict) -> list[dict]:
    sources: list[dict] = []
    for record in page.get("records", []):
        payload = {
            "record_id": record.get("record_id"),
            "bbox_xyxy": record.get("bbox") or record.get("cleanup_bbox"),
            "cleanup_method": record.get("cleanup_method"),
            "replacement_method": record.get("replacement_method"),
            "effective_method": record.get("replacement_method") or record.get("cleanup_method"),
            "effective_crop_path": record.get("effective_crop_path")
            or record.get("cleaned_crop_path")
            or record.get("cleanup_crop_path"),
            "route": record.get("route"),
            "text_region_source": record.get("text_region_source"),
            "source_mask_path": record.get("source_mask_path"),
            "fallback_locator": _compact_locator_payload(record.get("fallback_locator")),
            "fallback_locator_validation": _compact_validation_payload(record.get("fallback_locator_validation")),
            "gpt_image2_edit_status": record.get("gpt_image2_edit_status"),
            "text_overlay_required": bool(record.get("text_overlay_required", True)),
        }
        if record.get("gpt_replacement_quality") is not None:
            payload["gpt_replacement_quality"] = record.get("gpt_replacement_quality")
        sources.append(payload)
    return sources


def _load_jsonl(path: Path, status: str | set[str]) -> list[dict]:
    rows: list[dict] = []
    allowed = {status} if isinstance(status, str) else status
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            payload = json.loads(line)
            if payload.get("status") in allowed:
                rows.append(payload)
    return rows


def _load_jsonl_by_id(path: Path, status: str | set[str]) -> dict[str, dict]:
    rows: dict[str, dict] = {}
    for payload in _load_jsonl(path, status):
        rows[payload["record_id"]] = payload
    return rows


def _write_report(
    output_path: Path,
    detection_run_dir: str | Path,
    font_selection_run_dir: str | Path,
    layout_run_dir: str | Path,
    cleanup_run_dir: CleanupRunInput,
    manifest: dict,
    font_mapping_path: str | Path | None,
    preview_run_dir: str | Path | None,
) -> None:
    cleanup_summary = _cleanup_summary(manifest)
    lines = [
        "# Phase 8 Photoshop Export Report",
        "",
        f"Detection run directory: `{detection_run_dir}`",
        f"Font selection run directory: `{font_selection_run_dir}`",
        f"Layout run directory: `{layout_run_dir}`",
        f"Cleanup run directories: {format_cleanup_run_dirs(cleanup_run_dir)}",
        f"Preview run directory: `{preview_run_dir}`" if preview_run_dir else "Preview run directory: none",
        f"Font mapping file: `{font_mapping_path}`" if font_mapping_path else "Font mapping file: none",
        "",
        "## Summary",
        "",
        f"- Pages exported: {manifest['summary']['page_count']}",
        f"- Text layers exported: {manifest['summary']['record_count']}",
        "- `photoshop-import.jsx` reads project output `photoshop-manifest.json`, not the LabelPlus txt directly.",
        "- PSD layer order is editable `嵌字图层1`, `嵌字图层2`, ... above `修复图像`, above `原图`.",
        "",
        "## Cleanup Summary",
        "",
        f"- Missing cleanup layers: {cleanup_summary['missing_count']}",
        f"- Effective cleanup methods: {_format_counts(cleanup_summary['effective_methods'])}",
        f"- Page-level repaired image sources: {cleanup_summary['repair_source_count']}",
        "",
        "## JSX Behavior",
        "",
        "- Adds page-level `repaired_image_path` as a bitmap layer named `修复图像` above the original image when a Phase 7 preview run is supplied.",
        "- Synthesizes page-level `repaired_image_path` from LaMA cleanup crops and quality-accepted `gpt-image-2` replacement crops when no Phase 7 repaired page is supplied and source crop files exist.",
        "- Skips per-record cleanup patch layers when a page-level repaired image is available.",
        "- Places `cleanup.effective_crop_path` as a bitmap patch layer only when no page-level repaired image is available.",
        "- Creates one editable Photoshop paragraph text layer per exported layer using `text_bbox` width, height, and initial position.",
        "- Keeps `bbox` for cleanup patch placement and `text_bbox` for editable text placement.",
        "- Chooses editable text placement from `cleanup.layout_text_bbox` first, then `layout.target_bbox`, then the detected bbox.",
        "- Maps `layout.line_spacing` to Photoshop leading and `layout.letter_spacing` to best-effort tracking.",
        "- Applies `layout.text_color` to the editable text layer with Photoshop `SolidColor`.",
        "- Preserves `layout.vertical_align`; vertical top-aligned layers are labeled with `vertical_align=top` and translated after optional rotation so their rendered bounds top starts near `text_position.y_px`.",
        "- Uses `font.photoshop_font_name` before falling back to `font.family_name`.",
        "- Can apply an optional JSON font mapping file before writing `font.photoshop_font_name`.",
        "",
        "## Generated Artifacts",
        "",
        "- `photoshop-manifest.json`",
        "- `photoshop-import.jsx`",
        "- `reports/phase8-report.md`",
        "- `reports/photoshop-validation-checklist.md`",
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_photoshop_validation_checklist(output_path: Path, manifest: dict, font_mapping_path: str | Path | None) -> None:
    summary = manifest["summary"]
    cleanup_patch_count = _cleanup_patch_count(manifest)
    repaired_page_count = _repaired_page_count(manifest)
    lines = [
        "# Photoshop Validation Checklist",
        "",
        "## Run Steps",
        "",
        "1. Open Photoshop.",
        "2. Run `photoshop-import.jsx` from this export directory.",
        "3. Wait for the completion alert before inspecting saved PSD files.",
        "",
        "## Expected Output",
        "",
        "Expected PSD output folder: `psd/`",
        f"- Expected pages: {summary['page_count']}",
        f"- Expected editable text layers: {summary['record_count']}",
        f"- Expected page-level repaired image layers: {repaired_page_count}",
        f"- Expected cleanup patch layers: {cleanup_patch_count}",
        f"- Font mapping file: `{font_mapping_path}`" if font_mapping_path else "- Font mapping file: none",
        "",
        "## Manual Checks",
        "",
        "- Each PSD opens without missing image path errors.",
        "- Page-level `修复图像` layers align with the original canvas when exported.",
        "- Cleanup patch layers align with their detected text boxes when no page-level repaired image is exported.",
        "- Text layers remain editable paragraph text layers initialized from `text_bbox`.",
        "- Text layer colors match `layout.text_color`, especially white text on dark panels.",
        "- Fonts resolve to `font.photoshop_font_name` or an acceptable fallback from `font.font_name_candidates`.",
        "- Vertical layers labeled `vertical_align=top` attempt to move rendered layer bounds near `text_position.y_px`, not vertically centered.",
        "- Vertical, horizontal, rotation, leading, and tracking settings visually match the preview as closely as Photoshop permits.",
        "",
        "## Compatibility Notes",
        "",
        "- Photoshop was not executed by this pipeline; this checklist is the manual validation gate.",
        "- If a font does not resolve, copy the example font map and map the exported source name to the installed Photoshop font name.",
        "- If cleanup patch placement fails, the JSX should continue creating editable text layers.",
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _cleanup_patch_count(manifest: dict) -> int:
    count = 0
    for page in manifest.get("pages", []):
        if page.get("repaired_image_path"):
            continue
        for layer in page.get("layers", []):
            if layer.get("cleanup", {}).get("effective_crop_path"):
                count += 1
    return count


def _repaired_page_count(manifest: dict) -> int:
    return sum(1 for page in manifest.get("pages", []) if page.get("repaired_image_path"))


def _cleanup_summary(manifest: dict) -> dict:
    missing_count = 0
    effective_methods: dict[str, int] = {}
    repair_source_count = 0
    for page in manifest.get("pages", []):
        has_repair_sources = bool(page.get("repair_sources"))
        for source in page.get("repair_sources", []):
            repair_source_count += 1
            method = source.get("effective_method")
            if method:
                effective_methods[method] = effective_methods.get(method, 0) + 1
        for layer in page.get("layers", []):
            cleanup = layer.get("cleanup", {})
            if cleanup.get("status") == "missing":
                missing_count += 1
            if has_repair_sources:
                continue
            method = cleanup.get("effective_method")
            if method:
                effective_methods[method] = effective_methods.get(method, 0) + 1
    return {
        "missing_count": missing_count,
        "effective_methods": effective_methods,
        "repair_source_count": repair_source_count,
    }


def _format_counts(counts: dict[str, int]) -> str:
    if not counts:
        return "none"
    return ", ".join(f"`{key}={counts[key]}`" for key in sorted(counts))
