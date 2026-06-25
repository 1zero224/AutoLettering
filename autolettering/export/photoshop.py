from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from .photoshop_jsx import JSX_SOURCE


SCHEMA_VERSION = "autolettering.photoshop.v1"
FINAL_REPLACEMENT_METHODS = {"gpt_image2_masked_edit", "cta_first_masked_edit"}


def build_photoshop_manifest(
    detection_rows: dict[str, dict],
    font_rows: dict[str, dict],
    layout_rows: list[dict],
    cleanup_rows: dict[str, dict],
    sample_limit: int,
    font_mapping: dict[str, str] | None = None,
    repaired_pages: dict[str, object] | None = None,
) -> dict:
    layers = _manifest_layers(detection_rows, font_rows, layout_rows, cleanup_rows, sample_limit, font_mapping or {})
    pages = _group_layers_by_page(layers, repaired_pages or {}, detection_rows)
    return {
        "schema_version": SCHEMA_VERSION,
        "source_contract": _source_contract(),
        "pages": pages,
        "summary": {
            "record_count": len(layers),
            "page_count": len(pages),
        },
    }


def _source_contract() -> dict:
    return {
        "project_manifest": "photoshop-manifest.json",
        "import_script": "photoshop-import.jsx",
        "does_not_read_labelplus_txt_directly": True,
        "layer_order_top_to_bottom": ["嵌字图层1", "嵌字图层2", "...", "修复图像", "原图"],
        "repaired_image_source": "page-level image synthesized from lama_large_512px cleanup crops and successful gpt-image-2 replacement crops",
    }


def write_photoshop_import_jsx(output_path: str | Path) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(JSX_SOURCE, encoding="utf-8", newline="\n")
    return output


def _manifest_layers(
    detection_rows: dict[str, dict],
    font_rows: dict[str, dict],
    layout_rows: list[dict],
    cleanup_rows: dict[str, dict],
    sample_limit: int,
    font_mapping: dict[str, str],
) -> list[dict]:
    layers: list[dict] = []
    for layout in layout_rows[:sample_limit]:
        record_id = layout["record_id"]
        detection = detection_rows.get(record_id)
        font_row = font_rows.get(record_id)
        if detection is None or font_row is None:
            continue
        cleanup_row = cleanup_rows.get(record_id)
        if _cleanup_already_contains_replacement_text(cleanup_row):
            continue
        layer = _layer_record(detection, font_row, layout, cleanup_row, font_mapping)
        if layer is not None:
            layers.append(layer)
    return layers


def _layer_record(
    detection: dict,
    font_row: dict,
    layout_row: dict,
    cleanup_row: dict | None,
    font_mapping: dict[str, str],
) -> dict | None:
    layout = layout_row["layout"]
    bbox = _layer_bbox(detection, cleanup_row, layout)
    if bbox is None:
        return None
    text_bbox = _text_bbox(layout, cleanup_row, bbox)
    image_size = _image_size(detection["image_path"])
    return {
        "record_id": detection["record_id"],
        "image_name": detection["image_name"],
        "image_path": detection["image_path"],
        "layer_name": f"AL {detection['record_id']}",
        "text_layer_name": "",
        "cleanup_layer_name": f"修复区域 {detection['record_id']}",
        "text": layout.get("line_breaks") or detection.get("translated_text", ""),
        "translated_text": detection.get("translated_text", ""),
        "group_name": detection.get("group_name"),
        "bbox": _bbox_payload(bbox),
        "text_bbox": _bbox_payload(text_bbox),
        "position": _position_payload(bbox, image_size),
        "text_position": _position_payload(text_bbox, image_size),
        "font": _font_payload(font_row, font_mapping),
        "layout": _layout_payload(layout),
        "photoshop": _photoshop_payload(layout, text_bbox),
        "cleanup": _cleanup_payload(cleanup_row, image_size),
        "validation": layout.get("validation", {}),
    }


def _layer_bbox(detection: dict, cleanup_row: dict | None, layout: dict) -> list[int] | None:
    selected = detection.get("selected_text_box_xyxy")
    if selected:
        return [int(value) for value in selected]
    cleanup = cleanup_row.get("cleanup", {}) if cleanup_row else {}
    for candidate in (cleanup.get("bbox"), cleanup.get("layout_text_bbox"), layout.get("target_bbox")):
        if isinstance(candidate, list) and len(candidate) == 4:
            return [int(value) for value in candidate]
    return None


def _text_bbox(layout: dict, cleanup_row: dict | None, fallback_bbox: list[int]) -> list[int]:
    cleanup = cleanup_row.get("cleanup", {}) if cleanup_row else {}
    return cleanup.get("layout_text_bbox") or layout.get("target_bbox") or fallback_bbox


def _group_layers_by_page(layers: list[dict], repaired_pages: dict[str, object], detection_rows: dict[str, dict]) -> list[dict]:
    pages: dict[str, dict] = {}
    for layer in layers:
        page = pages.setdefault(layer["image_name"], _page_payload_from_layer(layer, repaired_pages.get(layer["image_name"])))
        page["layers"].append(layer)
        layer["text_layer_name"] = f"嵌字图层{len(page['layers'])}"
    for image_name, repaired_info in repaired_pages.items():
        if image_name in pages:
            continue
        page = _page_payload_from_repaired_page(image_name, repaired_info, detection_rows)
        if page is not None:
            pages[image_name] = page
    return list(pages.values())


def _page_payload_from_layer(layer: dict, repaired_info: object) -> dict:
    return {
        "image_name": layer["image_name"],
        "image_path": layer["image_path"],
        "width": layer["position"]["page_width"],
        "height": layer["position"]["page_height"],
        "repaired_image_path": _repaired_image_path(repaired_info),
        "repair_sources": _repair_sources(repaired_info),
        "layer_order": ["text_layers", "repaired_image", "original_image"],
        "layers": [],
    }


def _page_payload_from_repaired_page(image_name: str, repaired_info: object, detection_rows: dict[str, dict]) -> dict | None:
    info = repaired_info if isinstance(repaired_info, dict) else {}
    image_path = (
        info.get("image_path")
        or info.get("original_page_path")
        or _detection_image_path_for_page(image_name, detection_rows)
    )
    repaired_image_path = _repaired_image_path(repaired_info)
    if not image_path or not repaired_image_path:
        return None
    width, height = _image_size(image_path)
    return {
        "image_name": image_name,
        "image_path": str(image_path),
        "width": width,
        "height": height,
        "repaired_image_path": repaired_image_path,
        "repair_sources": _repair_sources(repaired_info),
        "layer_order": ["text_layers", "repaired_image", "original_image"],
        "layers": [],
    }


def _detection_image_path_for_page(image_name: str, detection_rows: dict[str, dict]) -> str | None:
    for detection in detection_rows.values():
        if detection.get("image_name") == image_name and detection.get("image_path"):
            return str(detection["image_path"])
    return None


def _repaired_image_path(repaired_info: object) -> str | None:
    if isinstance(repaired_info, str):
        return repaired_info
    if isinstance(repaired_info, dict):
        value = repaired_info.get("repaired_image_path") or repaired_info.get("cleaned_page_path")
        return str(value) if value else None
    return None


def _repair_sources(repaired_info: object) -> list[dict]:
    if not isinstance(repaired_info, dict):
        return []
    sources = repaired_info.get("repair_sources")
    if not isinstance(sources, list):
        return []
    normalized: list[dict] = []
    for source in sources:
        if isinstance(source, dict):
            normalized.append(_repair_source_payload(source))
    return normalized


def _repair_source_payload(source: dict) -> dict:
    payload = {
        "record_id": source.get("record_id"),
        "bbox_xyxy": source.get("bbox_xyxy"),
        "cleanup_method": source.get("cleanup_method"),
        "replacement_method": source.get("replacement_method"),
        "effective_method": source.get("effective_method"),
        "effective_crop_path": source.get("effective_crop_path"),
        "route": source.get("route"),
        "text_region_source": source.get("text_region_source"),
        "source_mask_path": source.get("source_mask_path"),
        "fallback_locator": source.get("fallback_locator"),
        "fallback_locator_validation": source.get("fallback_locator_validation"),
        "gpt_image2_edit_status": source.get("gpt_image2_edit_status"),
        "text_overlay_required": bool(source.get("text_overlay_required", False)),
    }
    if source.get("gpt_replacement_quality") is not None:
        payload["gpt_replacement_quality"] = source.get("gpt_replacement_quality")
    return payload


def _bbox_payload(bbox: list[int]) -> dict:
    x1, y1, x2, y2 = bbox
    return {"x": x1, "y": y1, "width": x2 - x1, "height": y2 - y1, "xyxy": bbox}


def _position_payload(bbox: list[int], image_size: tuple[int, int]) -> dict:
    x1, y1, x2, y2 = bbox
    width, height = image_size
    return {
        "x_px": x1,
        "y_px": y1,
        "center_x_px": round((x1 + x2) / 2, 3),
        "center_y_px": round((y1 + y2) / 2, 3),
        "x_ratio": round(x1 / width, 6),
        "y_ratio": round(y1 / height, 6),
        "page_width": width,
        "page_height": height,
    }


def _font_payload(font_row: dict, font_mapping: dict[str, str]) -> dict:
    selected = font_row.get("selected_font") or {}
    postscript_name = selected.get("postscript_name")
    family_name = selected.get("family_name")
    mapped_from = _mapped_font_source(font_mapping, postscript_name, family_name)
    photoshop_font_name = font_mapping.get(mapped_from) if mapped_from else postscript_name or family_name
    return {
        "font_id": font_row.get("selected_font_id"),
        "family_name": family_name,
        "postscript_name": postscript_name,
        "photoshop_font_name": photoshop_font_name,
        "font_name_candidates": _font_name_candidates(photoshop_font_name, postscript_name, family_name),
        "mapped_from": mapped_from,
        "filename": selected.get("filename"),
        "path": selected.get("path"),
        "model_confidence": font_row.get("confidence"),
    }


def _mapped_font_source(font_mapping: dict[str, str], *names: str | None) -> str | None:
    for name in names:
        if name and name in font_mapping:
            return name
    return None


def _font_name_candidates(*names: str | None) -> list[str]:
    candidates: list[str] = []
    for name in names:
        if name and name not in candidates:
            candidates.append(name)
    return candidates


def _layout_payload(layout: dict) -> dict:
    return {
        "font_size": layout.get("font_size"),
        "orientation": layout.get("orientation"),
        "angle_degrees": layout.get("angle_degrees", 0.0),
        "vertical_align": layout.get("vertical_align", "center"),
        "line_breaks": layout.get("line_breaks"),
        "line_spacing": layout.get("line_spacing"),
        "letter_spacing": layout.get("letter_spacing"),
        "target_width": layout.get("target_width"),
        "target_height": layout.get("target_height"),
        "overflow_ratio": layout.get("overflow_ratio"),
        "text_color": _text_color_payload(layout.get("text_color")),
    }


def _photoshop_payload(layout: dict, text_bbox: list[int]) -> dict:
    vertical_top_anchor_y = text_bbox[1] if _uses_vertical_top_anchor(layout) else None
    return {
        "vertical_top_anchor_y_px": vertical_top_anchor_y,
        "text_layer_name_suffix": " vertical_align=top" if vertical_top_anchor_y is not None else "",
    }


def _uses_vertical_top_anchor(layout: dict) -> bool:
    return layout.get("orientation") == "vertical" and layout.get("vertical_align") == "top"


def _text_color_payload(value: object) -> list[int]:
    if not isinstance(value, (list, tuple)) or len(value) < 3:
        return [0, 0, 0, 255]
    alpha = value[3] if len(value) >= 4 else 255
    return [_clamp_color(value[0]), _clamp_color(value[1]), _clamp_color(value[2]), _clamp_color(alpha)]


def _clamp_color(value: object) -> int:
    try:
        number = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0
    return max(0, min(255, number))


def _cleanup_payload(cleanup_row: dict | None, image_size: tuple[int, int] | None = None) -> dict:
    if cleanup_row is None:
        return {
            "status": "missing",
            "method": None,
            "bbox": None,
            "text_bbox": None,
            "mask_bbox": None,
            "layout_text_bbox": None,
            "position": None,
            "cleaned_crop_path": None,
            "before_after_path": None,
            "replacement_method": None,
            "replacement_crop_path": None,
            "effective_method": None,
            "effective_crop_path": None,
        }
    cleanup = cleanup_row.get("cleanup", {})
    replacement_crop_path = cleanup.get("replacement_crop_path")
    cleaned_crop_path = cleanup.get("cleaned_crop_path")
    replacement_method = cleanup.get("replacement_method")
    method = cleanup.get("method")
    bbox = cleanup.get("bbox")
    payload = {
        "status": cleanup_row.get("status"),
        "method": method,
        "bbox": _bbox_payload(bbox) if bbox else None,
        "text_bbox": _optional_bbox_payload(cleanup.get("text_bbox")),
        "mask_bbox": _optional_bbox_payload(cleanup.get("mask_bbox")),
        "layout_text_bbox": _optional_bbox_payload(cleanup.get("layout_text_bbox")),
        "position": _position_payload(bbox, image_size) if bbox and image_size else None,
        "cleaned_crop_path": cleaned_crop_path,
        "before_after_path": cleanup.get("before_after_path"),
        "replacement_method": replacement_method,
        "replacement_crop_path": replacement_crop_path,
        "effective_method": replacement_method or method,
        "effective_crop_path": replacement_crop_path or cleaned_crop_path,
    }
    if cleanup.get("gpt_replacement_quality") is not None:
        payload["gpt_replacement_quality"] = cleanup.get("gpt_replacement_quality")
    return payload


def _cleanup_already_contains_replacement_text(cleanup_row: dict | None) -> bool:
    if cleanup_row is None:
        return False
    cleanup = cleanup_row.get("cleanup") or {}
    method = cleanup.get("replacement_method")
    return method in FINAL_REPLACEMENT_METHODS and bool(cleanup.get("replacement_crop_path"))


def _optional_bbox_payload(value: object) -> dict | None:
    if not isinstance(value, list) or len(value) != 4:
        return None
    return _bbox_payload([int(item) for item in value])


def _image_size(image_path: str | Path) -> tuple[int, int]:
    with Image.open(image_path) as image:
        return image.size


def write_json(path: str | Path, payload: dict) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output
