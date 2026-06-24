from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .experiment_grid import near_square_columns, write_grid
from .inpaint.nonbubble import inpaint_nonbubble_text
from .models.gpt_image import (
    GptImageConfig,
    GptImageEditClient,
    gpt_image_edit_prompt,
    gpt_image_request_summary,
    normalize_gpt_output_to_crop,
)
from .text_bbox import matched_text_mask_bbox, selected_text_polarity
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
    allow_cta_method_override: bool = False,
) -> Path:
    run_dir = Path(output_root) / (run_id or "phase6-nonbubble-cleanup")
    run_dir.mkdir(parents=True, exist_ok=True)
    detections = _load_nonbubble_detections(Path(detection_run_dir) / "detections.jsonl", sample_limit, record_ids)
    client = GptImageEditClient(gpt_config) if call_gpt_image and gpt_config else None
    rows = [
        _cleanup_one(run_dir, detection, gpt_config, client, inpaint_method, mimo_client, allow_cta_method_override)
        for detection in detections
    ]
    _write_jsonl(run_dir / "cleanup-results.jsonl", rows)
    _write_fallback_locator_grid(run_dir, rows)
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
    allow_cta_method_override: bool,
) -> dict:
    if detection.get("status") == "fallback_required":
        return _fallback_gpt_cleanup_one(run_dir, detection, config, client, mimo_client)
    bbox = _cleanup_bbox_for_detection(detection)
    method = _method_for_detection(detection, inpaint_method, allow_cta_method_override)
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
        cleanup.update(
            {
                "route": "cta_mask_lama_large_512px",
                "source_mask_path": _ctd_component_mask_path(detection),
                "text_overlay_required": True,
            }
        )
        gpt_payload = {
            "status": "not_applicable",
            "reason": "cta_mask_matched_inpaint_path",
            "inpaint_method": method,
        }
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
    locator = _locate_fallback_bbox(detection, context["locator_path"], context_bbox, mimo_client)
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
            "fallback_locator_validation": {"status": "not_called", "reason": "fallback_locator_failed"},
            "gpt_image2_edit": {"status": "not_called", "reason": "fallback_locator_failed"},
        }
    validation = _validate_fallback_locator_semantics(run_dir, detection, locator, context["locator_path"], mimo_client)
    if validation.get("status") != "accepted":
        return {
            "record_id": detection["record_id"],
            "image_name": detection.get("image_name"),
            "translated_text": detection.get("translated_text", ""),
            "status": "failed",
            "cleanup": {
                "method": "gpt_image2_masked_edit",
                "bbox": list(context_bbox),
                "failure_reason": validation.get("failure_reason", "fallback_locator_semantic_rejected"),
                "cleaned_crop_path": str(context["input_path"]),
            },
            "fallback_locator": locator,
            "fallback_locator_validation": validation,
            "gpt_image2_edit": {"status": "not_called", "reason": "fallback_locator_semantic_rejected"},
        }
    local_bbox = tuple(locator.get("local_bbox_xyxy") or (0, 0, context["size"][0], context["size"][1]))
    mask_local_bbox = _fallback_mask_bbox(local_bbox, context["size"], validation)
    edit_context = _write_fallback_edit_context(run_dir, detection, context, mask_local_bbox)
    edit_mask_bbox = _rebase_bbox(mask_local_bbox, edit_context["local_context_bbox"])
    mask_path = _write_local_gpt_mask(edit_context["size"], edit_mask_bbox, edit_context["mask_path"])
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
    gpt_payload["edit_context"] = _edit_context_payload(edit_context)
    _write_fallback_replacement_crop(
        gpt_payload,
        context["input_path"],
        context["replacement_crop_path"],
        context["size"],
        mask_local_bbox,
        edit_context=edit_context,
    )
    has_replacement = gpt_payload.get("status") == "ok" and context["replacement_crop_path"].exists()
    cleanup = {
        "method": "gpt_image2_masked_edit",
        "bbox": list(context_bbox),
        "text_bbox": list(_global_bbox(context_bbox, local_bbox)),
        "mask_bbox": list(_global_bbox(context_bbox, mask_local_bbox)),
        "layout_text_bbox": list(_global_bbox(context_bbox, local_bbox)),
        "cleaned_crop_path": str(context["input_path"]),
        "before_after_path": str(context["input_path"]),
        "text_overlay_required": not has_replacement,
    }
    if has_replacement:
        cleanup["replacement_method"] = "gpt_image2_masked_edit"
        cleanup["replacement_crop_path"] = str(context["replacement_crop_path"])
    else:
        cleanup["failure_reason"] = gpt_payload.get("failure_reason") or "gpt_image2_replacement_not_completed"
    return {
        "record_id": detection["record_id"],
        "image_name": detection.get("image_name"),
        "translated_text": detection.get("translated_text", ""),
        "status": "cleaned" if has_replacement else "failed",
        "cleanup": cleanup,
        "fallback_locator": locator,
        "fallback_locator_validation": validation,
        "gpt_image2_edit": gpt_payload,
    }


def _fallback_mask_bbox(
    local_bbox: tuple[int, int, int, int],
    context_size: tuple[int, int],
    validation: dict,
) -> tuple[int, int, int, int]:
    padding = int(validation.get("bbox_padding_px") or 0)
    if padding <= 0:
        return local_bbox
    return _expanded_local_bbox(local_bbox, context_size[0], context_size[1], padding)


def _edit_context_payload(edit_context: dict) -> dict:
    return {
        "input_path": str(edit_context["input_path"]),
        "mask_path": str(edit_context["mask_path"]),
        "local_context_bbox": list(edit_context["local_context_bbox"]),
        "size": list(edit_context["size"]),
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
    summary["target_size"] = list(target_size)
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


def _method_for_detection(detection: dict, requested_method: str, allow_cta_method_override: bool = False) -> str:
    if _is_ctd_matched_detection(detection) and not allow_cta_method_override:
        return "lama_large_512px"
    return requested_method


def _cleanup_bbox_for_detection(detection: dict) -> tuple[int, int, int, int]:
    matched_bbox = matched_text_mask_bbox(detection)
    if matched_bbox is not None:
        return matched_bbox
    return selected_text_body_bbox(detection)


def _is_ctd_matched_detection(detection: dict) -> bool:
    return matched_text_mask_bbox(detection) is not None


def _ctd_component_mask_path(detection: dict) -> str | None:
    canonical = detection.get("text_region_mask_path")
    if canonical:
        return str(canonical)
    match = detection.get("cta_match") or detection.get("ctd_match") or {}
    if match.get("status") != "matched":
        return None
    return match.get("mask_path")


def _write_fallback_context(run_dir: Path, detection: dict, context_bbox: tuple[int, int, int, int]) -> dict:
    x1, y1, x2, y2 = context_bbox
    safe_id = _safe_name(detection["record_id"])
    input_path = run_dir / "fallback_input" / f"{safe_id}.png"
    locator_path = run_dir / "fallback_locator_input" / f"{safe_id}.png"
    mask_path = run_dir / "fallback_gpt_mask" / f"{safe_id}.png"
    replacement_crop_path = run_dir / "fallback_replacement_crop" / f"{safe_id}.png"
    input_path.parent.mkdir(parents=True, exist_ok=True)
    locator_path.parent.mkdir(parents=True, exist_ok=True)
    mask_path.parent.mkdir(parents=True, exist_ok=True)
    replacement_crop_path.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(detection["image_path"]) as image:
        crop = image.convert("RGB").crop(context_bbox)
    crop.save(input_path)
    _write_locator_grid_image(crop, locator_path)
    return {
        "input_path": input_path,
        "locator_path": locator_path,
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
            "locator_image_path": str(context_path),
        }
    prompt = "\n".join(
        [
            "Find the original Japanese text region corresponding to this Chinese translation inside the crop.",
            "The image includes a green coordinate grid and red pixel labels. The labels are guides only; do not include them in the target bbox.",
            f"The crop dimensions are width={context_bbox[2] - context_bbox[0]} and height={context_bbox[3] - context_bbox[1]} pixels.",
            f"Chinese translation: {detection.get('translated_text', '')}",
            "Return one JSON object, not an array.",
            "The bbox_xyxy must use crop-local pixel coordinates, with 0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height.",
            "Do not return any coordinate outside the crop dimensions.",
            "If exact pixels are hard, also return bbox_percent_xyxy as [x1%,y1%,x2%,y2%] relative to the crop; all percent values must be between 0 and 100.",
            "Return only JSON with bbox_xyxy, optional bbox_percent_xyxy, confidence, and reasoning_summary.",
        ]
    )
    response = mimo_client.analyze_image(context_path, prompt, kind="phase6_fallback_text_locator", max_completion_tokens=800)
    try:
        payload, local_bbox = _parse_mimo_locator_response(response, context_bbox)
    except Exception as exc:
        return _retry_locate_fallback_bbox(detection, context_path, context_bbox, response, exc, mimo_client)
    return _fallback_locator_payload(payload, local_bbox, response, context_bbox, context_path)


def _parse_mimo_locator_response(
    response: dict,
    context_bbox: tuple[int, int, int, int],
) -> tuple[dict, list[int]]:
    payload = _mimo_bbox_payload(response.get("raw_text", ""))
    local_bbox = _mimo_local_bbox(payload, context_bbox)
    _validate_local_bbox(local_bbox, context_bbox)
    return payload, local_bbox


def _retry_locate_fallback_bbox(
    detection: dict,
    context_path: Path,
    context_bbox: tuple[int, int, int, int],
    first_response: dict,
    first_error: Exception,
    mimo_client,
) -> dict:
    width = context_bbox[2] - context_bbox[0]
    height = context_bbox[3] - context_bbox[1]
    prompt = "\n".join(
        [
            "Your previous bbox JSON was invalid because at least one coordinate was outside the crop.",
            f"Crop dimensions are width={width} and height={height} pixels.",
            f"Chinese translation: {detection.get('translated_text', '')}",
            "Re-locate the original Japanese text region in this same image.",
            "Return corrected crop-local pixel coordinates only: 0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height.",
            "For vertical Japanese text, include the full visible top-to-bottom text column, not just the lower part.",
            "Return only JSON with bbox_xyxy, confidence, and reasoning_summary.",
            f"Previous invalid response: {first_response.get('raw_text', '')[:1200]}",
        ]
    )
    retry_response = mimo_client.analyze_image(
        context_path,
        prompt,
        kind="phase6_fallback_text_locator_retry",
        max_completion_tokens=800,
    )
    try:
        payload, local_bbox = _parse_mimo_locator_response(retry_response, context_bbox)
    except Exception as retry_error:
        return {
            "status": "failed",
            "failure_reason": f"invalid_mimo_bbox:{type(first_error).__name__}",
            "retry_failure_reason": f"invalid_mimo_bbox_retry:{type(retry_error).__name__}",
            "raw_text": first_response.get("raw_text", ""),
            "retry_raw_text": retry_response.get("raw_text", ""),
            "locator_image_path": str(context_path),
            "request": first_response.get("request"),
            "response": first_response.get("response"),
            "retry_request": retry_response.get("request"),
            "retry_response": retry_response.get("response"),
        }
    return _fallback_locator_payload(
        payload,
        local_bbox,
        retry_response,
        context_bbox,
        context_path,
        first_response=first_response,
        retry_of_error=type(first_error).__name__,
    )


def _fallback_locator_payload(
    payload: dict,
    local_bbox: list[int],
    response: dict,
    context_bbox: tuple[int, int, int, int],
    context_path: Path,
    first_response: dict | None = None,
    retry_of_error: str | None = None,
) -> dict:
    result = {
        "status": "ok",
        "local_bbox_xyxy": local_bbox,
        "global_bbox_xyxy": list(_global_bbox(context_bbox, tuple(local_bbox))),
        "confidence": payload.get("confidence"),
        "reasoning_summary": payload.get("reasoning_summary"),
        "raw_text": response.get("raw_text", ""),
        "locator_image_path": str(context_path),
        "request": response.get("request"),
        "response": response.get("response"),
    }
    if first_response is not None:
        result["first_raw_text"] = first_response.get("raw_text", "")
        result["first_request"] = first_response.get("request")
        result["first_response"] = first_response.get("response")
        result["retry_of_error"] = retry_of_error
    return result


def _validate_fallback_locator_semantics(
    run_dir: Path,
    detection: dict,
    locator: dict,
    locator_path: Path,
    mimo_client,
) -> dict:
    validation_image_path = run_dir / "fallback_locator_validation_input" / f"{_safe_name(detection['record_id'])}.png"
    _write_locator_validation_image(locator_path, locator, detection["record_id"], validation_image_path)
    if mimo_client is None:
        return {
            "status": "rejected",
            "failure_reason": "mimo_client_required_for_fallback_validation",
            "validation_image_path": str(validation_image_path),
        }
    prompt = "\n".join(
        [
            "Validate the yellow bbox on this manga crop.",
            "The yellow bbox must cover the visible original Japanese text region that corresponds to the Chinese translation.",
            "Reject if the yellow bbox is on blank background, unrelated text, English lettering, UI marks, only a partial phrase, or includes large unrelated artwork.",
            "A slightly loose bbox is acceptable only when it still clearly targets the same original Japanese text.",
            f"Chinese translation: {detection.get('translated_text', '')}",
            "Return only JSON with keys: semantic_correct, tight_enough, bbox_on_blank_area, bbox_targets_unrelated_text, visible_original_text, recommendation, reasoning_summary.",
            "recommendation must be either accept or reject.",
        ]
    )
    response = mimo_client.analyze_image(
        validation_image_path,
        prompt,
        kind="phase6_fallback_text_locator_validation",
        max_completion_tokens=800,
    )
    try:
        payload = _mimo_object_payload(response.get("raw_text", ""))
    except Exception as exc:
        return {
            "status": "rejected",
            "failure_reason": f"invalid_mimo_validation:{type(exc).__name__}",
            "validation_image_path": str(validation_image_path),
            "raw_text": response.get("raw_text", ""),
            "request": response.get("request"),
            "response": response.get("response"),
        }
    validation = _fallback_validation_payload(payload, response, validation_image_path)
    if validation["status"] == "rejected" and _should_retry_fallback_validation(validation):
        return _retry_validate_fallback_locator_semantics(detection, validation_image_path, response, mimo_client)
    return validation


def _retry_validate_fallback_locator_semantics(
    detection: dict,
    validation_image_path: Path,
    first_response: dict,
    mimo_client,
) -> dict:
    prompt = "\n".join(
        [
            "Re-check the yellow bbox only for target correctness.",
            "Do not reject because you cannot confidently transcribe the Japanese characters.",
            "Accept if the yellow bbox covers the visible Japanese manga sound effect, interjection, title, or caption that naturally corresponds to the Chinese translation.",
            "Reject only if the bbox is on blank background, a non-text object, unrelated text, English-only text, or misses important visible characters.",
            f"Chinese translation: {detection.get('translated_text', '')}",
            "Return only JSON with keys: semantic_correct, tight_enough, bbox_on_blank_area, bbox_targets_unrelated_text, visible_original_text, recommendation, reasoning_summary.",
            "recommendation must be either accept or reject.",
        ]
    )
    retry_response = mimo_client.analyze_image(
        validation_image_path,
        prompt,
        kind="phase6_fallback_text_locator_validation_retry",
        max_completion_tokens=800,
    )
    try:
        payload = _mimo_object_payload(retry_response.get("raw_text", ""))
    except Exception as exc:
        return {
            "status": "rejected",
            "failure_reason": f"invalid_mimo_validation_retry:{type(exc).__name__}",
            "validation_image_path": str(validation_image_path),
            "raw_text": first_response.get("raw_text", ""),
            "retry_raw_text": retry_response.get("raw_text", ""),
            "request": first_response.get("request"),
            "response": first_response.get("response"),
            "retry_request": retry_response.get("request"),
            "retry_response": retry_response.get("response"),
        }
    validation = _fallback_validation_payload(payload, retry_response, validation_image_path)
    validation["first_raw_text"] = first_response.get("raw_text", "")
    validation["first_request"] = first_response.get("request")
    validation["first_response"] = first_response.get("response")
    validation["retry_of_error"] = "semantic_validation_inconclusive"
    return validation


def _fallback_validation_payload(payload: dict, response: dict, validation_image_path: Path) -> dict:
    semantic_correct = _mimo_bool(payload.get("semantic_correct"))
    tight_enough = _mimo_bool(payload.get("tight_enough"))
    bbox_on_blank_area = _mimo_bool(payload.get("bbox_on_blank_area"))
    bbox_targets_unrelated_text = _mimo_bool(payload.get("bbox_targets_unrelated_text"))
    recommendation = str(payload.get("recommendation", "")).strip().lower()
    hard_reject = semantic_correct is False or bbox_on_blank_area is True or bbox_targets_unrelated_text is True
    accepted = semantic_correct is True and not hard_reject
    needs_padding = accepted and (tight_enough is not True or recommendation == "reject")
    status = "accepted" if accepted else "rejected"
    return {
        "status": status,
        "semantic_correct": semantic_correct,
        "tight_enough": tight_enough,
        "bbox_on_blank_area": bbox_on_blank_area,
        "bbox_targets_unrelated_text": bbox_targets_unrelated_text,
        "visible_original_text": str(payload.get("visible_original_text", "")).strip() or None,
        "recommendation": recommendation or None,
        "reasoning_summary": payload.get("reasoning_summary"),
        "bbox_padding_px": 12 if needs_padding else 0,
        "failure_reason": None if accepted else "fallback_locator_semantic_rejected",
        "validation_image_path": str(validation_image_path),
        "raw_text": response.get("raw_text", ""),
        "request": response.get("request"),
        "response": response.get("response"),
    }


def _should_retry_fallback_validation(validation: dict) -> bool:
    return (
        validation.get("tight_enough") is True
        and validation.get("bbox_on_blank_area") is False
        and validation.get("bbox_targets_unrelated_text") is False
        and validation.get("semantic_correct") is not True
    )


def _write_locator_grid_image(crop: Image.Image, output_path: Path) -> Path:
    image = crop.convert("RGB").copy()
    draw = ImageDraw.Draw(image, "RGBA")
    font = _locator_font()
    width, height = image.size
    step = _locator_grid_step(width, height)
    draw.rectangle((0, 0, width - 1, height - 1), outline=(255, 0, 0, 255), width=3)
    for x in range(0, width, step):
        draw.line((x, 0, x, height), fill=(0, 210, 90, 105), width=1)
        draw.text((x + 2, 2), str(x), fill=(255, 0, 0, 255), font=font)
    for y in range(0, height, step):
        draw.line((0, y, width, y), fill=(0, 210, 90, 105), width=1)
        draw.text((2, y + 2), str(y), fill=(255, 0, 0, 255), font=font)
    draw.text((6, max(4, height - 18)), f"w={width} h={height}", fill=(255, 0, 0, 255), font=font)
    image.save(output_path)
    return output_path


def _write_fallback_locator_grid(run_dir: Path, rows: list[dict]) -> Path | None:
    tiles: list[tuple[str, Path]] = []
    for row in rows:
        locator = row.get("fallback_locator") or {}
        locator_path = locator.get("locator_image_path")
        if not locator_path or not Path(locator_path).exists():
            continue
        overlay_path = run_dir / "debug" / "fallback_locator_overlays" / f"{_safe_name(row['record_id'])}.png"
        validation = row.get("fallback_locator_validation") or {}
        _write_locator_overlay(Path(locator_path), locator, row["record_id"], overlay_path, validation)
        label = f"{row['record_id']}\nloc={locator.get('status', 'unknown')} val={validation.get('status', 'none')}"
        tiles.append((label, overlay_path))
    if not tiles:
        return None
    return write_grid(
        run_dir / "visuals" / "fallback-locator-grid.png",
        tiles,
        columns=near_square_columns(len(tiles)),
        tile_size=(330, 330),
    )


def _write_locator_validation_image(locator_path: Path, locator: dict, record_id: str, output_path: Path) -> Path:
    return _write_locator_overlay(locator_path, locator, record_id, output_path, {"status": "pending"})


def _write_locator_overlay(
    locator_path: Path,
    locator: dict,
    record_id: str,
    output_path: Path,
    validation: dict | None = None,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(locator_path) as image:
        overlay = image.convert("RGB")
    draw = ImageDraw.Draw(overlay, "RGBA")
    bbox = locator.get("local_bbox_xyxy")
    color = _locator_overlay_color(locator, validation or {})
    if isinstance(bbox, list) and len(bbox) == 4:
        draw.rectangle(tuple(int(value) for value in bbox), outline=color, width=4)
    draw.rectangle((0, 0, min(overlay.width, 360), 24), fill=(255, 255, 255, 210))
    draw.text(
        (4, 4),
        f"{record_id} loc={locator.get('status', 'unknown')} val={(validation or {}).get('status', 'none')}",
        fill=(0, 0, 0, 255),
        font=_locator_font(),
    )
    overlay.save(output_path)
    return output_path


def _locator_overlay_color(locator: dict, validation: dict) -> tuple[int, int, int, int]:
    if locator.get("status") != "ok":
        return (255, 0, 0, 230)
    if validation.get("status") == "accepted":
        return (20, 190, 90, 235)
    if validation.get("status") == "rejected":
        return (255, 0, 0, 235)
    return (255, 230, 0, 230)


def _locator_grid_step(width: int, height: int) -> int:
    longest = max(width, height)
    if longest <= 240:
        return 40
    if longest <= 520:
        return 50
    return 100


def _locator_font() -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype("DejaVuSans.ttf", 13)
    except OSError:
        return ImageFont.load_default()


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
    edit_context: dict | None = None,
) -> None:
    normalized = gpt_payload.get("normalized_output_path")
    if not normalized:
        return
    with Image.open(input_path) as original_image, Image.open(normalized) as edited_image:
        original = original_image.convert("RGB").resize(size)
        edited = edited_image.convert("RGB")
    if edit_context is not None:
        local_context_bbox = edit_context["local_context_bbox"]
        edited = _expand_edit_crop_to_context(edited, original, local_context_bbox)
    else:
        edited = edited.resize(size)
    original = _compose_gpt_replacement_region(original, edited, local_bbox)
    original.save(output_path)


def _expand_edit_crop_to_context(
    edited: Image.Image,
    original: Image.Image,
    local_context_bbox: tuple[int, int, int, int],
) -> Image.Image:
    canvas = original.copy()
    x1, y1, x2, y2 = local_context_bbox
    patch = edited.convert("RGB").resize((x2 - x1, y2 - y1))
    canvas.paste(patch, (x1, y1))
    return canvas


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
    ring = array[ry1:ry2, rx1:rx2]
    mask = np.ones(ring.shape[:2], dtype=bool)
    mask[max(0, y1 - ry1) : max(0, y2 - ry1), max(0, x1 - rx1) : max(0, x2 - rx1)] = False
    samples = ring[mask]
    if samples.size == 0:
        return (255, 255, 255)
    luma = samples.astype(np.float32).mean(axis=1)
    bright = samples[luma >= 235]
    if len(bright) >= 12:
        median = np.median(bright, axis=0)
        return tuple(int(value) for value in median)
    light = samples[luma >= 210]
    if len(light) >= 12:
        median = np.median(light, axis=0)
        return tuple(int(value) for value in median)
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
    return _mimo_object_payload(raw_text)


def _mimo_object_payload(raw_text: str) -> dict:
    payload = json.loads(_strip_json_wrapper(raw_text))
    if isinstance(payload, list):
        if not payload or not isinstance(payload[0], dict):
            raise ValueError("mimo_bbox_array_empty_or_invalid")
        payload = payload[0]
    if not isinstance(payload, dict):
        raise ValueError("mimo_bbox_payload_not_object")
    return payload


def _mimo_bool(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in {0, 1}:
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "y", "1", "accept", "accepted"}:
            return True
        if normalized in {"false", "no", "n", "0", "reject", "rejected"}:
            return False
    return None


def _mimo_local_bbox(payload: dict, context_bbox: tuple[int, int, int, int]) -> list[int]:
    for key in ("bbox_xyxy", "bbox"):
        if key in payload:
            bbox = _number_list(payload[key], key)
            if _looks_normalized_bbox(bbox):
                return _scaled_bbox(bbox, context_bbox, scale=1.0)
            return [int(round(value)) for value in bbox]
    if "bbox_percent_xyxy" in payload:
        return _scaled_bbox(_number_list(payload["bbox_percent_xyxy"], "bbox_percent_xyxy"), context_bbox, scale=100.0)
    if "bbox_normalized_xyxy" in payload:
        return _scaled_bbox(_number_list(payload["bbox_normalized_xyxy"], "bbox_normalized_xyxy"), context_bbox, scale=1.0)
    raise ValueError("mimo_bbox_missing")


def _number_list(value: object, field_name: str) -> list[float]:
    if isinstance(value, list) and len(value) == 1 and isinstance(value[0], list):
        value = value[0]
    if not isinstance(value, list) or len(value) != 4:
        raise ValueError(f"{field_name}_must_have_four_values")
    try:
        return [float(item) for item in value]
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name}_must_be_numeric") from exc


def _looks_normalized_bbox(values: list[float]) -> bool:
    return all(0.0 <= value <= 1.0 for value in values) and values[2] > values[0] and values[3] > values[1]


def _scaled_bbox(values: list[float], context_bbox: tuple[int, int, int, int], scale: float) -> list[int]:
    width = context_bbox[2] - context_bbox[0]
    height = context_bbox[3] - context_bbox[1]
    x1, y1, x2, y2 = values
    return [
        int(round(x1 / scale * width)),
        int(round(y1 / scale * height)),
        int(round(x2 / scale * width)),
        int(round(y2 / scale * height)),
    ]


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
        f"- Cleanup methods: {_method_summary(rows)}",
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
        "- `fallback_locator_input/*.png`",
        "- `fallback_locator_validation_input/*.png`",
        "- `debug/fallback_locator_overlays/*.png`",
        "- `visuals/fallback-locator-grid.png`",
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
