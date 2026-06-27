from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PIL import Image


MODEL_TEXT_REGION_KIND = "phase2_model_text_region_recognition"


def build_model_text_region_prompt(
    *,
    translated_text: str,
    labelplus_point_xy: tuple[int, int],
    candidate_boxes: list[list[int]] | None = None,
) -> str:
    lines = [
        "Locate the visible original Japanese manga text region that corresponds to the Chinese translation.",
        "The LabelPlus coordinate anchor is near the target text, not necessarily the exact text center.",
        f"Chinese translation: {translated_text}",
        f"LabelPlus point in this crop: [{labelplus_point_xy[0]}, {labelplus_point_xy[1]}]",
    ]
    if candidate_boxes:
        lines.append(f"candidate_boxes_xyxy: {json.dumps(candidate_boxes, ensure_ascii=False)}")
        lines.append("The complete corresponding original text may span multiple candidate boxes.")
        lines.append("Prefer candidate boxes only when their union covers the complete corresponding original text.")
    lines.extend(
        [
            "Return the bounding box around the complete corresponding original text, not just one matching character.",
            "Return only one single JSON object, not a JSON array, with keys:",
            "found, bbox_xyxy, bbox_percent_xyxy, source_text, orientation, confidence, reasoning_summary.",
            "bbox_xyxy is [x1,y1,x2,y2] in crop pixels.",
            "bbox_percent_xyxy is [x1%,y1%,x2%,y2%] on a 0-100 scale relative to the crop and is optional.",
            "orientation must be vertical, horizontal, angled, or unknown.",
            "Set found=false when no matching original text is visible in the crop.",
        ]
    )
    return "\n".join(lines)


def recognize_text_region_with_model(
    *,
    client: Any,
    context_image_path: str | Path,
    context_bbox_xyxy: tuple[int, int, int, int],
    labelplus_point_xy: tuple[int, int],
    translated_text: str,
    candidate_boxes: list[list[int]] | None = None,
) -> dict:
    context_size = _image_size(context_image_path)
    prompt = build_model_text_region_prompt(
        translated_text=translated_text,
        labelplus_point_xy=labelplus_point_xy,
        candidate_boxes=candidate_boxes,
    )
    response = client.analyze_image(
        context_image_path,
        prompt,
        kind=MODEL_TEXT_REGION_KIND,
        max_completion_tokens=800,
    )
    result = parse_model_text_region_response(
        response.get("raw_text", ""),
        context_bbox_xyxy=context_bbox_xyxy,
        context_size=context_size,
    )
    return {
        **result,
        "raw_text": response.get("raw_text", ""),
        "request": response.get("request"),
        "response": response.get("response"),
    }


def parse_model_text_region_response(
    raw_text: str,
    *,
    context_bbox_xyxy: tuple[int, int, int, int],
    context_size: tuple[int, int],
) -> dict:
    try:
        payload = _object_payload(raw_text)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        return {"status": "failed", "failure_reason": f"invalid_model_json:{type(exc).__name__}"}

    found = payload.get("found", True)
    if found is False:
        return {
            "status": "not_found",
            "failure_reason": "model_reported_not_found",
            "reasoning_summary": _optional_text(payload.get("reasoning_summary")),
        }

    try:
        local_bbox, source, clipped = _local_bbox(payload, context_size)
    except ValueError as exc:
        return {
            "status": "failed",
            "failure_reason": str(exc),
            "reasoning_summary": _optional_text(payload.get("reasoning_summary")),
        }

    return {
        "status": "ok",
        "local_bbox_xyxy": local_bbox,
        "global_bbox_xyxy": list(_global_bbox(context_bbox_xyxy, local_bbox)),
        "bbox_coordinate_source": source,
        "bbox_clipped": clipped,
        "source_text": _optional_text(payload.get("source_text")),
        "orientation": _normalize_orientation(payload.get("orientation")),
        "confidence": _optional_float(payload.get("confidence")),
        "reasoning_summary": _optional_text(payload.get("reasoning_summary")),
    }


def write_text_region_context_crop(
    image_path: str | Path,
    context_bbox_xyxy: tuple[int, int, int, int],
    output_path: str | Path,
) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(image_path) as image:
        image.convert("RGB").crop(context_bbox_xyxy).save(output)
    return output


def _image_size(path: str | Path) -> tuple[int, int]:
    with Image.open(path) as image:
        return image.size


def _object_payload(raw_text: str) -> dict:
    payload = json.loads(_strip_json_wrapper(raw_text))
    if isinstance(payload, list) and len(payload) == 1 and isinstance(payload[0], dict):
        return payload[0]
    if not isinstance(payload, dict):
        raise ValueError("model_json_not_object")
    return payload


def _strip_json_wrapper(raw_text: str) -> str:
    text = str(raw_text).strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def _local_bbox(payload: dict, context_size: tuple[int, int]) -> tuple[list[int], str, bool]:
    width, height = context_size
    if payload.get("bbox_xyxy") is not None:
        bbox = _number_list(payload["bbox_xyxy"], "bbox_xyxy")
        validated, clipped = _validate_bbox([int(round(value)) for value in bbox], width, height)
        return validated, "bbox_xyxy", clipped
    if payload.get("bbox_percent_xyxy") is not None:
        percents = _number_list(payload["bbox_percent_xyxy"], "bbox_percent_xyxy")
        x1, y1, x2, y2 = percents
        if all(0.0 <= value <= 1.0 for value in percents):
            bbox = [
                int(round(width * x1)),
                int(round(height * y1)),
                int(round(width * x2)),
                int(round(height * y2)),
            ]
            validated, clipped = _validate_bbox(bbox, width, height)
            return validated, "bbox_percent_xyxy", clipped
        bbox = [
            int(round(width * x1 / 100.0)),
            int(round(height * y1 / 100.0)),
            int(round(width * x2 / 100.0)),
            int(round(height * y2 / 100.0)),
        ]
        validated, clipped = _validate_bbox(bbox, width, height)
        return validated, "bbox_percent_xyxy", clipped
    raise ValueError("missing_model_bbox")


def _number_list(value: object, name: str) -> list[float]:
    if not isinstance(value, list | tuple) or len(value) != 4:
        raise ValueError(f"invalid_{name}")
    try:
        return [float(item) for item in value]
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid_{name}") from exc


def _validate_bbox(bbox: list[int], width: int, height: int) -> tuple[list[int], bool]:
    if len(bbox) != 4:
        raise ValueError("invalid_model_bbox")
    original = list(bbox)
    x1, y1, x2, y2 = original
    x1 = max(0, min(width - 1, x1))
    y1 = max(0, min(height - 1, y1))
    x2 = max(1, min(width, x2))
    y2 = max(1, min(height, y2))
    if x2 <= x1 or y2 <= y1:
        raise ValueError("invalid_model_bbox")
    validated = [x1, y1, x2, y2]
    return validated, validated != original


def _global_bbox(
    context_bbox_xyxy: tuple[int, int, int, int],
    local_bbox_xyxy: list[int],
) -> tuple[int, int, int, int]:
    return (
        context_bbox_xyxy[0] + local_bbox_xyxy[0],
        context_bbox_xyxy[1] + local_bbox_xyxy[1],
        context_bbox_xyxy[0] + local_bbox_xyxy[2],
        context_bbox_xyxy[1] + local_bbox_xyxy[3],
    )


def _normalize_orientation(value: object) -> str:
    text = str(value or "unknown").strip().lower()
    if text in {"vertical", "horizontal", "angled"}:
        return text
    return "unknown"


def _optional_text(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
