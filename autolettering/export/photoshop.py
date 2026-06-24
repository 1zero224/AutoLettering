from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from .photoshop_jsx import JSX_SOURCE


SCHEMA_VERSION = "autolettering.photoshop.v1"


def build_photoshop_manifest(
    detection_rows: dict[str, dict],
    font_rows: dict[str, dict],
    layout_rows: list[dict],
    cleanup_rows: dict[str, dict],
    sample_limit: int,
    font_mapping: dict[str, str] | None = None,
    repaired_pages: dict[str, str] | None = None,
) -> dict:
    layers = _manifest_layers(detection_rows, font_rows, layout_rows, cleanup_rows, sample_limit, font_mapping or {})
    return {
        "schema_version": SCHEMA_VERSION,
        "pages": _group_layers_by_page(layers, repaired_pages or {}),
        "summary": {
            "record_count": len(layers),
            "page_count": len({layer["image_name"] for layer in layers}),
        },
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
        layers.append(_layer_record(detection, font_row, layout, cleanup_rows.get(record_id), font_mapping))
    return layers


def _layer_record(
    detection: dict,
    font_row: dict,
    layout_row: dict,
    cleanup_row: dict | None,
    font_mapping: dict[str, str],
) -> dict:
    bbox = detection["selected_text_box_xyxy"]
    layout = layout_row["layout"]
    text_bbox = _text_bbox(layout, cleanup_row, bbox)
    image_size = _image_size(detection["image_path"])
    return {
        "record_id": detection["record_id"],
        "image_name": detection["image_name"],
        "image_path": detection["image_path"],
        "layer_name": f"AL {detection['record_id']}",
        "text_layer_name": f"嵌字图层 {detection['record_id']}",
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


def _text_bbox(layout: dict, cleanup_row: dict | None, fallback_bbox: list[int]) -> list[int]:
    cleanup = cleanup_row.get("cleanup", {}) if cleanup_row else {}
    return cleanup.get("layout_text_bbox") or layout.get("target_bbox") or fallback_bbox


def _group_layers_by_page(layers: list[dict], repaired_pages: dict[str, str]) -> list[dict]:
    pages: dict[str, dict] = {}
    for layer in layers:
        page = pages.setdefault(
            layer["image_name"],
            {
                "image_name": layer["image_name"],
                "image_path": layer["image_path"],
                "width": layer["position"]["page_width"],
                "height": layer["position"]["page_height"],
                "repaired_image_path": repaired_pages.get(layer["image_name"]),
                "layer_order": ["text_layers", "repaired_image", "original_image"],
                "layers": [],
            },
        )
        page["layers"].append(layer)
    return list(pages.values())


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
    return {
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
