from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from .inpaint.nonbubble import inpaint_nonbubble_text
from .models.gpt_image import (
    GptImageConfig,
    GptImageEditClient,
    gpt_image_edit_prompt,
    gpt_image_request_summary,
    normalize_gpt_output_to_crop,
)
from .text_bbox import selected_text_polarity
from .text_body_bbox import selected_text_body_bbox


def run_phase6_nonbubble_cleanup(
    detection_run_dir: str | Path,
    output_root: str | Path = "outputs/runs",
    run_id: str | None = None,
    sample_limit: int = 5,
    record_ids: list[str] | None = None,
    gpt_config: GptImageConfig | None = None,
    call_gpt_image: bool = False,
    inpaint_method: str = "bt_lama_large",
    mimo_client=None,
) -> Path:
    run_dir = Path(output_root) / (run_id or "phase6-nonbubble-cleanup")
    run_dir.mkdir(parents=True, exist_ok=True)
    detections = _load_nonbubble_detections(Path(detection_run_dir) / "detections.jsonl", sample_limit, record_ids)
    client = GptImageEditClient(gpt_config) if call_gpt_image and gpt_config else None
    rows = [_cleanup_one(run_dir, detection, gpt_config, client, inpaint_method, mimo_client) for detection in detections]
    _write_jsonl(run_dir / "cleanup-results.jsonl", rows)
    _write_report(run_dir / "reports" / "phase6-nonbubble-report.md", detection_run_dir, rows)
    return run_dir


def _load_nonbubble_detections(path: Path, sample_limit: int, record_ids: list[str] | None = None) -> list[dict]:
    wanted = set(record_ids or [])
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if len(rows) >= sample_limit:
                break
            payload = json.loads(line)
            if wanted and payload.get("record_id") not in wanted:
                continue
            if payload.get("status") in {"ok", "fallback_required"} and payload.get("group_name") != "框内":
                rows.append(payload)
    return rows


def _cleanup_one(
    run_dir: Path,
    detection: dict,
    config: GptImageConfig | None,
    client: GptImageEditClient | None,
    inpaint_method: str,
    mimo_client,
) -> dict:
    if detection.get("status") == "fallback_required":
        return _fallback_gpt_cleanup_one(run_dir, detection, config, client, mimo_client)
    bbox = _cleanup_bbox_for_detection(detection)
    method = _method_for_detection(detection, inpaint_method)
    result = inpaint_nonbubble_text(
        image_path=detection["image_path"],
        bbox=bbox,
        output_dir=run_dir / "crops",
        record_id=detection["record_id"],
        method=method,
        polarity=selected_text_polarity(detection, bbox),
        text_mask_path=_ctd_component_mask_path(detection),
    )
    cleanup = _cleanup_payload(result)
    if _is_ctd_matched_detection(detection):
        gpt_payload = {"status": "not_applicable", "reason": "ctd_mask_matched_lama_large_path"}
    else:
        prompt = gpt_image_edit_prompt(detection.get("translated_text", ""))
        gpt_payload = _gpt_image_payload(run_dir, detection["record_id"], result, prompt, config, client)
        _apply_gpt_replacement(cleanup, gpt_payload)
    return {
        "record_id": detection["record_id"],
        "image_name": detection.get("image_name"),
        "translated_text": detection.get("translated_text", ""),
        "status": "cleaned",
        "cleanup": cleanup,
        "gpt_image2_edit": gpt_payload,
    }


def _fallback_gpt_cleanup_one(
    run_dir: Path,
    detection: dict,
    config: GptImageConfig | None,
    client: GptImageEditClient | None,
    mimo_client,
) -> dict:
    fallback = detection.get("fallback") or {}
    context_bbox = tuple(int(value) for value in fallback.get("context_bbox_xyxy") or detection.get("search_region_xyxy"))
    context = _write_fallback_context(run_dir, detection, context_bbox)
    locator = _locate_fallback_bbox(detection, context["input_path"], context_bbox, mimo_client)
    if locator.get("status") != "ok":
        return {
            "record_id": detection["record_id"],
            "image_name": detection.get("image_name"),
            "translated_text": detection.get("translated_text", ""),
            "status": "failed",
            "cleanup": {
                "method": "gpt_image2_masked_edit",
                "bbox": list(context_bbox),
                "failure_reason": locator.get("failure_reason", "fallback_locator_failed"),
                "cleaned_crop_path": str(context["input_path"]),
            },
            "fallback_locator": locator,
            "gpt_image2_edit": {"status": "not_called", "reason": "fallback_locator_failed"},
        }
    local_bbox = tuple(locator.get("local_bbox_xyxy") or (0, 0, context["size"][0], context["size"][1]))
    edit_context = _write_fallback_edit_context(run_dir, detection, context, local_bbox)
    edit_local_bbox = _rebase_bbox(local_bbox, edit_context["local_context_bbox"])
    mask_path = _write_local_gpt_mask(edit_context["size"], edit_local_bbox, edit_context["mask_path"])
    prompt = gpt_image_edit_prompt(detection.get("translated_text", ""))
    gpt_payload = _gpt_image_payload_for_paths(
        run_dir,
        detection["record_id"],
        edit_context["input_path"],
        mask_path,
        edit_context["size"],
        prompt,
        config,
        client,
    )
    _write_fallback_replacement_crop(
        gpt_payload,
        edit_context["input_path"],
        edit_context["replacement_crop_path"],
        edit_context["size"],
        edit_local_bbox,
    )
    edit_global_bbox = _global_bbox(context_bbox, edit_context["local_context_bbox"])
    cleanup = {
        "method": "gpt_image2_masked_edit",
        "bbox": list(edit_global_bbox),
        "text_bbox": list(_global_bbox(context_bbox, local_bbox)),
        "mask_bbox": list(_global_bbox(context_bbox, local_bbox)),
        "layout_text_bbox": list(_global_bbox(context_bbox, local_bbox)),
        "cleaned_crop_path": str(edit_context["input_path"]),
        "before_after_path": str(edit_context["input_path"]),
        "replacement_method": "gpt_image2_masked_edit",
        "replacement_crop_path": str(edit_context["replacement_crop_path"]) if edit_context["replacement_crop_path"].exists() else gpt_payload.get("normalized_output_path"),
    }
    return {
        "record_id": detection["record_id"],
        "image_name": detection.get("image_name"),
        "translated_text": detection.get("translated_text", ""),
        "status": "cleaned",
        "cleanup": cleanup,
        "fallback_locator": locator,
        "gpt_image2_edit": gpt_payload,
    }


def _cleanup_payload(result) -> dict:
    payload = asdict(result)
    payload["bbox"] = list(result.bbox)
    for key in ("input_crop_path", "text_mask_path", "gpt_mask_path", "cleaned_crop_path", "before_after_path"):
        payload[key] = str(payload[key])
    return payload


def _gpt_image_payload(
    run_dir: Path,
    record_id: str,
    result,
    prompt: str,
    config: GptImageConfig | None,
    client: GptImageEditClient | None,
) -> dict:
    summary = gpt_image_request_summary(config, result.input_crop_path, result.gpt_mask_path, prompt)
    if client is None:
        return {"status": "dry_run", "request": summary, "failure_reason": None}
    try:
        output_path = run_dir / "gpt_image2" / f"{_safe_name(record_id)}.png"
        response = client.edit_image(result.input_crop_path, result.gpt_mask_path, prompt, output_path)
        normalized = normalize_gpt_output_to_crop(
            response["output_path"],
            _crop_size(result.bbox),
            run_dir / "gpt_image2_normalized" / f"{_safe_name(record_id)}.png",
        )
        return {"request": summary, **response, **normalized}
    except Exception as exc:
        return {"status": "failed", "request": summary, "failure_reason": f"{type(exc).__name__}:{str(exc)[:500]}"}


def _gpt_image_payload_for_paths(
    run_dir: Path,
    record_id: str,
    image_path: Path,
    mask_path: Path,
    target_size: tuple[int, int],
    prompt: str,
    config: GptImageConfig | None,
    client: GptImageEditClient | None,
) -> dict:
    summary = gpt_image_request_summary(config, image_path, mask_path, prompt)
    if client is None:
        return {"status": "dry_run", "request": summary, "failure_reason": None}
    try:
        output_path = run_dir / "gpt_image2" / f"{_safe_name(record_id)}.png"
        response = client.edit_image(image_path, mask_path, prompt, output_path)
        normalized = normalize_gpt_output_to_crop(
            response["output_path"],
            target_size,
            run_dir / "gpt_image2_normalized" / f"{_safe_name(record_id)}.png",
        )
        return {"request": summary, **response, **normalized}
    except Exception as exc:
        return {"status": "failed", "request": summary, "failure_reason": f"{type(exc).__name__}:{str(exc)[:500]}"}


def _apply_gpt_replacement(cleanup: dict, gpt_payload: dict) -> None:
    if gpt_payload.get("status") != "ok" or not gpt_payload.get("normalized_output_path"):
        return
    cleanup["replacement_method"] = "gpt_image2_masked_edit"
    cleanup["replacement_crop_path"] = gpt_payload["normalized_output_path"]


def _crop_size(bbox: tuple[int, int, int, int]) -> tuple[int, int]:
    x1, y1, x2, y2 = bbox
    return x2 - x1, y2 - y1


def _method_for_detection(detection: dict, requested_method: str) -> str:
    if _is_ctd_matched_detection(detection):
        return "lama_large_512px"
    return requested_method


def _cleanup_bbox_for_detection(detection: dict) -> tuple[int, int, int, int]:
    if _is_ctd_matched_detection(detection):
        match_bbox = (detection.get("ctd_match") or {}).get("bbox_xyxy")
        if isinstance(match_bbox, list) and len(match_bbox) == 4:
            return tuple(int(value) for value in match_bbox)
    return selected_text_body_bbox(detection)


def _is_ctd_matched_detection(detection: dict) -> bool:
    match = detection.get("ctd_match") or {}
    return detection.get("detection_method") == "ctd_mask" and match.get("status") == "matched"


def _ctd_component_mask_path(detection: dict) -> str | None:
    match = detection.get("ctd_match") or {}
    if match.get("status") != "matched":
        return None
    return match.get("mask_path")


def _write_fallback_context(run_dir: Path, detection: dict, context_bbox: tuple[int, int, int, int]) -> dict:
    x1, y1, x2, y2 = context_bbox
    safe_id = _safe_name(detection["record_id"])
    input_path = run_dir / "fallback_input" / f"{safe_id}.png"
    mask_path = run_dir / "fallback_gpt_mask" / f"{safe_id}.png"
    replacement_crop_path = run_dir / "fallback_replacement_crop" / f"{safe_id}.png"
    input_path.parent.mkdir(parents=True, exist_ok=True)
    mask_path.parent.mkdir(parents=True, exist_ok=True)
    replacement_crop_path.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(detection["image_path"]) as image:
        crop = image.convert("RGB").crop(context_bbox)
    crop.save(input_path)
    return {
        "input_path": input_path,
        "mask_path": mask_path,
        "replacement_crop_path": replacement_crop_path,
        "size": (x2 - x1, y2 - y1),
    }


def _write_fallback_edit_context(
    run_dir: Path,
    detection: dict,
    context: dict,
    local_bbox: tuple[int, int, int, int],
    padding_px: int = 16,
) -> dict:
    context_width, context_height = context["size"]
    local_context_bbox = _expanded_local_bbox(local_bbox, context_width, context_height, padding_px)
    safe_id = _safe_name(detection["record_id"])
    input_path = run_dir / "fallback_edit_input" / f"{safe_id}.png"
    mask_path = run_dir / "fallback_edit_gpt_mask" / f"{safe_id}.png"
    replacement_crop_path = run_dir / "fallback_edit_replacement_crop" / f"{safe_id}.png"
    input_path.parent.mkdir(parents=True, exist_ok=True)
    mask_path.parent.mkdir(parents=True, exist_ok=True)
    replacement_crop_path.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(context["input_path"]) as image:
        image.convert("RGB").crop(local_context_bbox).save(input_path)
    x1, y1, x2, y2 = local_context_bbox
    return {
        "input_path": input_path,
        "mask_path": mask_path,
        "replacement_crop_path": replacement_crop_path,
        "local_context_bbox": local_context_bbox,
        "size": (x2 - x1, y2 - y1),
    }


def _locate_fallback_bbox(detection: dict, context_path: Path, context_bbox: tuple[int, int, int, int], mimo_client) -> dict:
    if mimo_client is None:
        return {
            "status": "failed",
            "failure_reason": "mimo_client_required_for_fallback",
            "local_bbox_xyxy": [0, 0, context_bbox[2] - context_bbox[0], context_bbox[3] - context_bbox[1]],
        }
    prompt = "\n".join(
        [
            "Find the original Japanese text region corresponding to this Chinese translation inside the crop.",
            f"The crop dimensions are width={context_bbox[2] - context_bbox[0]} and height={context_bbox[3] - context_bbox[1]} pixels.",
            f"Chinese translation: {detection.get('translated_text', '')}",
            "Return one JSON object, not an array.",
            "The bbox_xyxy must use crop-local pixel coordinates, with 0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height.",
            "Return only JSON with bbox_xyxy as [x1,y1,x2,y2], confidence, and reasoning_summary.",
        ]
    )
    response = mimo_client.analyze_image(context_path, prompt, kind="phase6_fallback_text_locator", max_completion_tokens=800)
    try:
        payload = _mimo_bbox_payload(response.get("raw_text", ""))
        local_bbox = [int(value) for value in payload["bbox_xyxy"]]
        _validate_local_bbox(local_bbox, context_bbox)
    except Exception as exc:
        return {
            "status": "failed",
            "failure_reason": f"invalid_mimo_bbox:{type(exc).__name__}",
            "raw_text": response.get("raw_text", ""),
        }
    return {
        "status": "ok",
        "local_bbox_xyxy": local_bbox,
        "global_bbox_xyxy": list(_global_bbox(context_bbox, tuple(local_bbox))),
        "confidence": payload.get("confidence"),
        "reasoning_summary": payload.get("reasoning_summary"),
        "raw_text": response.get("raw_text", ""),
        "request": response.get("request"),
        "response": response.get("response"),
    }


def _write_local_gpt_mask(
    size: tuple[int, int],
    local_bbox: tuple[int, int, int, int],
    output_path: Path,
) -> Path:
    mask = Image.new("RGBA", size, (0, 0, 0, 255))
    alpha = Image.new("L", size, 255)
    ImageDraw.Draw(alpha).rectangle(local_bbox, fill=0)
    Image.merge("RGBA", [Image.new("L", size, 0)] * 3 + [alpha]).save(output_path)
    return output_path


def _expanded_local_bbox(
    bbox: tuple[int, int, int, int],
    width: int,
    height: int,
    padding_px: int,
) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = bbox
    return (
        max(0, x1 - padding_px),
        max(0, y1 - padding_px),
        min(width, x2 + padding_px),
        min(height, y2 + padding_px),
    )


def _rebase_bbox(
    bbox: tuple[int, int, int, int],
    origin_bbox: tuple[int, int, int, int],
) -> tuple[int, int, int, int]:
    return (
        bbox[0] - origin_bbox[0],
        bbox[1] - origin_bbox[1],
        bbox[2] - origin_bbox[0],
        bbox[3] - origin_bbox[1],
    )


def _write_fallback_replacement_crop(
    gpt_payload: dict,
    input_path: Path,
    output_path: Path,
    size: tuple[int, int],
    local_bbox: tuple[int, int, int, int],
) -> None:
    normalized = gpt_payload.get("normalized_output_path")
    if not normalized:
        return
    with Image.open(input_path) as original_image, Image.open(normalized) as edited_image:
        original = original_image.convert("RGB").resize(size)
        edited = edited_image.convert("RGB").resize(size)
    original = _compose_gpt_replacement_region(original, edited, local_bbox)
    original.save(output_path)


def _compose_gpt_replacement_region(
    original: Image.Image,
    edited: Image.Image,
    local_bbox: tuple[int, int, int, int],
) -> Image.Image:
    text_alpha = _dark_text_alpha(edited, local_bbox)
    if text_alpha is None:
        alpha = Image.new("L", original.size, 0)
        ImageDraw.Draw(alpha).rectangle(local_bbox, fill=255)
        original.paste(edited, (0, 0), alpha)
        return original

    background = _local_background_color(original, local_bbox)
    cleaned = original.copy()
    ImageDraw.Draw(cleaned).rectangle(local_bbox, fill=background)
    cleaned.paste(edited, (0, 0), text_alpha)
    return cleaned


def _dark_text_alpha(edited: Image.Image, local_bbox: tuple[int, int, int, int]) -> Image.Image | None:
    gray = np.array(edited.convert("L"), dtype=np.uint8)
    x1, y1, x2, y2 = local_bbox
    dark = np.zeros_like(gray, dtype=np.uint8)
    dark_region = gray[y1:y2, x1:x2] < 36
    if int(dark_region.sum()) < 20:
        return None
    dark[y1:y2, x1:x2] = dark_region.astype(np.uint8) * 255
    return Image.fromarray(dark, mode="L")


def _local_background_color(original: Image.Image, local_bbox: tuple[int, int, int, int]) -> tuple[int, int, int]:
    array = np.array(original.convert("RGB"), dtype=np.uint8)
    x1, y1, x2, y2 = local_bbox
    pad = 6
    rx1, ry1 = max(0, x1 - pad), max(0, y1 - pad)
    rx2, ry2 = min(array.shape[1], x2 + pad), min(array.shape[0], y2 + pad)
    ring = array[ry1:ry2, rx1:rx2].copy()
    ring[max(0, y1 - ry1) : max(0, y2 - ry1), max(0, x1 - rx1) : max(0, x2 - rx1)] = 255
    samples = ring.reshape(-1, 3)
    samples = samples[np.any(samples < 245, axis=1)]
    if samples.size == 0:
        return (255, 255, 255)
    median = np.median(samples, axis=0)
    return tuple(int(value) for value in median)


def _global_bbox(context_bbox: tuple[int, int, int, int], local_bbox: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    return (
        context_bbox[0] + local_bbox[0],
        context_bbox[1] + local_bbox[1],
        context_bbox[0] + local_bbox[2],
        context_bbox[1] + local_bbox[3],
    )


def _strip_json_wrapper(raw_text: str) -> str:
    text = raw_text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def _mimo_bbox_payload(raw_text: str) -> dict:
    payload = json.loads(_strip_json_wrapper(raw_text))
    if isinstance(payload, list):
        if not payload or not isinstance(payload[0], dict):
            raise ValueError("mimo_bbox_array_empty_or_invalid")
        payload = payload[0]
    if not isinstance(payload, dict):
        raise ValueError("mimo_bbox_payload_not_object")
    return payload


def _validate_local_bbox(local_bbox: list[int], context_bbox: tuple[int, int, int, int]) -> None:
    if len(local_bbox) != 4:
        raise ValueError("mimo_bbox_must_have_four_values")
    x1, y1, x2, y2 = local_bbox
    width = context_bbox[2] - context_bbox[0]
    height = context_bbox[3] - context_bbox[1]
    if not (0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height):
        raise ValueError("mimo_bbox_out_of_crop_bounds")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_report(output_path: Path, detection_run_dir: str | Path, rows: list[dict]) -> None:
    called = sum(1 for row in rows if row["gpt_image2_edit"]["status"] == "ok")
    lines = [
        "# Phase 6 Non-Bubble Cleanup Report",
        "",
        f"Detection run directory: `{detection_run_dir}`",
        "",
        "## Summary",
        "",
        f"- Records processed: {len(rows)}",
        f"- Local inpainted: {sum(1 for row in rows if row['status'] == 'cleaned')}",
        f"- Local methods: {_method_summary(rows)}",
        f"- GPT image calls: {called}",
        f"- GPT dry runs: {sum(1 for row in rows if row['gpt_image2_edit']['status'] == 'dry_run')}",
        f"- GPT failures: {sum(1 for row in rows if row['gpt_image2_edit']['status'] == 'failed')}",
        "",
        "## Generated Artifacts",
        "",
        "- `cleanup-results.jsonl`",
        "- `crops/input/*.png`",
        "- `crops/mask/*.png`",
        "- `crops/gpt_mask/*.png`",
        "- `crops/cleaned/*.png`",
        "- `crops/before_after/*.png`",
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _method_summary(rows: list[dict]) -> str:
    methods: dict[str, int] = {}
    for row in rows:
        method = row.get("cleanup", {}).get("method") or "unknown"
        methods[method] = methods.get(method, 0) + 1
    return ", ".join(f"{name}={count}" for name, count in sorted(methods.items())) or "none"


def _safe_name(value: str) -> str:
    return "".join(char if char.isalnum() else "-" for char in value).strip("-") or "record"
