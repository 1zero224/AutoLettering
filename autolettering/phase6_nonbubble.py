from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .experiment_grid import near_square_columns, write_grid
from .inpaint.nonbubble import inpaint_nonbubble_text
from .inpaint.nonbubble import build_gpt_edit_mask, build_text_mask
from .models.gpt_image import (
    GptImageConfig,
    GptImageEditClient,
    gpt_image_edit_prompt,
    gpt_image_request_summary,
    normalize_gpt_output_to_crop,
)
from .text_bbox import matched_text_mask_bbox, selected_text_polarity
from .text_body_bbox import selected_text_body_bbox


CV_TIGHTNESS_REFINEMENT_METHODS = {
    "trim_to_light_text_ink_support",
    "trim_to_dark_background_support",
    "trim_to_dark_vertical_text_column_support",
    "recover_light_text_ink_band_near_labelplus_anchor",
    "recover_dark_text_ink_column_near_labelplus_anchor",
}
CV_TIGHTNESS_MAX_AREA_RATIO = 0.16
CV_TIGHTNESS_MAX_SHORT_SIDE_RATIO = 0.35
CV_TIGHTNESS_MAX_LONG_SIDE_RATIO = 0.9


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
    fallback_edit_padding_px: int = 16,
    fallback_mask_expand_px: int = 0,
    fallback_gpt_mask_shape: str = "rect",
) -> Path:
    run_dir = Path(output_root) / (run_id or "phase6-nonbubble-cleanup")
    run_dir.mkdir(parents=True, exist_ok=True)
    detections = _load_nonbubble_detections(Path(detection_run_dir) / "detections.jsonl", sample_limit, record_ids)
    client = GptImageEditClient(gpt_config) if call_gpt_image and gpt_config else None
    rows = [
        _cleanup_one(
            run_dir,
            detection,
            gpt_config,
            client,
            inpaint_method,
            mimo_client,
            allow_cta_method_override,
            fallback_edit_padding_px,
            fallback_mask_expand_px,
            fallback_gpt_mask_shape,
        )
        for detection in detections
    ]
    _write_jsonl(run_dir / "cleanup-results.jsonl", rows)
    _write_fallback_locator_grid(run_dir, rows)
    _write_fallback_replacement_grid(run_dir, rows)
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
    fallback_edit_padding_px: int,
    fallback_mask_expand_px: int,
    fallback_gpt_mask_shape: str,
) -> dict:
    if detection.get("status") == "fallback_required":
        return _fallback_gpt_cleanup_one(
            run_dir,
            detection,
            config,
            client,
            mimo_client,
            fallback_edit_padding_px,
            fallback_mask_expand_px,
            fallback_gpt_mask_shape,
        )
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
                "text_region_source": "ctd_refined_mask_component",
                "ballonstranslator_detector_module": "ctd",
                "requested_inpaint_method": method,
                "ballonstranslator_inpainter": method,
                "actual_inpaint_method": cleanup.get("method"),
                "source_mask_path": _ctd_component_mask_path(detection),
                "text_overlay_required": True,
            }
        )
        gpt_payload = {
            "status": "not_applicable",
            "reason": "cta_mask_matched_inpaint_path",
            "inpaint_method": method,
            "replacement_path": "not_used_for_ctd_matched_records",
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
    edit_padding_px: int = 16,
    mask_expand_px: int = 0,
    gpt_mask_shape: str = "rect",
) -> dict:
    fallback = detection.get("fallback") or {}
    context_bbox = tuple(int(value) for value in fallback.get("context_bbox_xyxy") or detection.get("search_region_xyxy"))
    context = _write_fallback_context(run_dir, detection, context_bbox)
    locator = _locate_fallback_bbox(detection, context["locator_path"], context_bbox, mimo_client)
    if locator.get("status") != "ok":
        recovered_locator = _recover_locator_from_labelplus_anchor(
            detection,
            context["input_path"],
            context_bbox,
            locator,
            {"status": "rejected", "failure_reason": "fallback_locator_semantic_rejected"},
        )
        if recovered_locator.get("status") != "ok":
            recovered_locator = _recover_dark_text_locator_from_labelplus_anchor(
                detection,
                context["input_path"],
                context_bbox,
                locator,
                {
                    "status": "rejected",
                    "failure_reason": "fallback_locator_semantic_rejected",
                    "bbox_targets_unrelated_text": True,
                },
            )
        if recovered_locator.get("status") == "ok":
            locator = recovered_locator
        else:
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
    locator = _refine_fallback_locator_bbox(locator, context["input_path"], context_bbox)
    validation = _validate_fallback_locator_semantics(run_dir, detection, locator, context["locator_path"], mimo_client)
    if validation.get("status") != "accepted":
        retry_locator = _recover_locator_from_labelplus_anchor(
            detection,
            context["input_path"],
            context_bbox,
            locator,
            validation,
        )
        if retry_locator.get("status") != "ok":
            retry_locator = _recover_dark_text_locator_from_labelplus_anchor(
                detection,
                context["input_path"],
                context_bbox,
                locator,
                validation,
            )
        if retry_locator.get("status") != "ok":
            retry_locator = _relocate_after_semantic_rejection(
                detection,
                context["locator_path"],
                context_bbox,
                locator,
                validation,
                mimo_client,
            )
        if retry_locator.get("status") == "ok":
            retry_locator = _refine_fallback_locator_bbox(retry_locator, context["input_path"], context_bbox)
            retry_validation = _validate_fallback_locator_semantics(
                run_dir,
                detection,
                retry_locator,
                context["locator_path"],
                mimo_client,
            )
            if retry_validation.get("status") == "accepted":
                locator = retry_locator
                validation = retry_validation
            else:
                if retry_locator.get("refinement", {}).get("method") in CV_TIGHTNESS_REFINEMENT_METHODS:
                    locator = _with_rejected_locator_attempt(locator, "anchor_recovery_attempt", retry_locator, retry_validation)
                anchor_locator = _recover_locator_from_labelplus_anchor(
                    detection,
                    context["input_path"],
                    context_bbox,
                    retry_locator,
                    retry_validation,
                )
                if anchor_locator.get("status") == "ok":
                    anchor_locator = _refine_fallback_locator_bbox(anchor_locator, context["input_path"], context_bbox)
                    anchor_validation = _validate_fallback_locator_semantics(
                        run_dir,
                        detection,
                        anchor_locator,
                        context["locator_path"],
                        mimo_client,
                    )
                    if anchor_validation.get("status") == "accepted":
                        locator = anchor_locator
                        validation = anchor_validation
                    else:
                        locator = _with_rejected_locator_attempt(locator, "anchor_recovery_attempt", anchor_locator, anchor_validation)
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
    if _accepted_locator_is_suspiciously_below_anchor(locator, validation, detection):
        anchor_locator = _recover_locator_from_labelplus_anchor(
            detection,
            context["input_path"],
            context_bbox,
            locator,
            {"status": "accepted", "tight_enough": False},
        )
        if anchor_locator.get("status") == "ok":
            anchor_locator = _refine_fallback_locator_bbox(anchor_locator, context["input_path"], context_bbox)
            anchor_validation = _validate_fallback_locator_semantics(
                run_dir,
                detection,
                anchor_locator,
                context["locator_path"],
                mimo_client,
            )
            if anchor_validation.get("status") == "accepted":
                locator = anchor_locator
                validation = anchor_validation
            else:
                locator = _with_rejected_locator_attempt(locator, "anchor_recovery_attempt", anchor_locator, anchor_validation)
    local_bbox = tuple(locator.get("local_bbox_xyxy") or (0, 0, context["size"][0], context["size"][1]))
    mask_local_bbox = _fallback_mask_bbox(local_bbox, context["size"], validation)
    if mask_expand_px > 0:
        mask_local_bbox = _expanded_local_bbox(mask_local_bbox, context["size"][0], context["size"][1], mask_expand_px)
    background_repair = _write_fallback_background_repair(
        run_dir,
        detection,
        context,
        mask_local_bbox,
        method="lama_large_512px",
    )
    edit_context = _write_fallback_edit_context(run_dir, detection, context, mask_local_bbox, padding_px=edit_padding_px)
    edit_mask_bbox = _rebase_bbox(mask_local_bbox, edit_context["local_context_bbox"])
    edit_context["gpt_mask_shape"] = gpt_mask_shape
    mask_path = _write_fallback_gpt_edit_mask(
        edit_context["input_path"],
        edit_context["size"],
        edit_mask_bbox,
        edit_context["mask_path"],
        gpt_mask_shape,
    )
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
        "method": background_repair["method"],
        "bbox": list(context_bbox),
        "text_bbox": list(_global_bbox(context_bbox, local_bbox)),
        "mask_bbox": list(_global_bbox(context_bbox, mask_local_bbox)),
        "layout_text_bbox": list(_global_bbox(context_bbox, local_bbox)),
        "cleaned_crop_path": str(background_repair["cleaned_crop_path"]),
        "cleanup_mask_path": str(background_repair["text_mask_path"]),
        "before_after_path": str(background_repair["before_after_path"]),
        "background_repair_method": background_repair["method"],
        "background_repair_bbox": list(background_repair["bbox"]),
        "text_overlay_required": not has_replacement,
        "gpt_mask_shape": gpt_mask_shape,
    }
    if has_replacement:
        cleanup["replacement_method"] = "gpt_image2_masked_edit"
        cleanup["replacement_crop_path"] = str(context["replacement_crop_path"])
    else:
        cleanup["replacement_failure_reason"] = gpt_payload.get("failure_reason") or "gpt_image2_replacement_not_completed"
    return {
        "record_id": detection["record_id"],
        "image_name": detection.get("image_name"),
        "translated_text": detection.get("translated_text", ""),
        "status": "cleaned",
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
        "gpt_mask_shape": edit_context.get("gpt_mask_shape", "rect"),
    }


def _write_fallback_background_repair(
    run_dir: Path,
    detection: dict,
    context: dict,
    local_bbox: tuple[int, int, int, int],
    method: str,
) -> dict:
    result = inpaint_nonbubble_text(
        image_path=context["input_path"],
        bbox=local_bbox,
        output_dir=run_dir / "fallback_background_repair",
        record_id=detection["record_id"],
        method=method,
        polarity=_fallback_repair_polarity(context["input_path"], local_bbox),
    )
    return _fallback_background_payload(run_dir, detection["record_id"], result, context["input_path"], context["size"], local_bbox)


def _fallback_background_payload(
    run_dir: Path,
    record_id: str,
    result,
    context_path: Path,
    context_size: tuple[int, int],
    local_bbox: tuple[int, int, int, int],
) -> dict:
    safe_id = _safe_name(record_id)
    cleaned_path = run_dir / "fallback_cleaned" / f"{safe_id}.png"
    mask_path = run_dir / "fallback_mask" / f"{safe_id}.png"
    before_after_path = run_dir / "fallback_before_after" / f"{safe_id}.png"
    cleaned_path.parent.mkdir(parents=True, exist_ok=True)
    mask_path.parent.mkdir(parents=True, exist_ok=True)
    before_after_path.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(context_path) as image, Image.open(result.cleaned_crop_path) as patch:
        repaired = image.convert("RGB").resize(context_size)
        repaired.paste(patch.convert("RGB").resize((local_bbox[2] - local_bbox[0], local_bbox[3] - local_bbox[1])), local_bbox[:2])
    with Image.open(result.text_mask_path) as patch_mask:
        mask = Image.new("L", context_size, 0)
        mask.paste(patch_mask.convert("L").resize((local_bbox[2] - local_bbox[0], local_bbox[3] - local_bbox[1])), local_bbox[:2])
    repaired.save(cleaned_path)
    mask.save(mask_path)
    _save_fallback_before_after(context_path, cleaned_path, before_after_path)
    return {
        "method": result.method,
        "bbox": local_bbox,
        "cleaned_crop_path": cleaned_path,
        "text_mask_path": mask_path,
        "before_after_path": before_after_path,
    }


def _fallback_repair_polarity(context_path: Path, local_bbox: tuple[int, int, int, int]) -> str:
    try:
        with Image.open(context_path) as image:
            crop = image.convert("RGB").crop(local_bbox)
    except (FileNotFoundError, OSError):
        return "dark_on_light"
    gray = np.array(crop.convert("L"), dtype=np.uint8)
    if gray.size == 0:
        return "dark_on_light"
    dark_ratio = float((gray < 90).mean())
    light_ratio = float((gray > 210).mean())
    return "light_on_dark" if dark_ratio >= 0.35 and light_ratio >= 0.03 else "dark_on_light"


def _save_fallback_before_after(before_path: Path, after_path: Path, output_path: Path) -> None:
    with Image.open(before_path) as before_image, Image.open(after_path) as after_image:
        before = before_image.convert("RGB")
        after = after_image.convert("RGB")
    canvas = Image.new("RGB", (before.width + after.width, max(before.height, after.height)), "white")
    canvas.paste(before, (0, 0))
    canvas.paste(after, (before.width, 0))
    canvas.save(output_path)


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
    _write_locator_grid_image(crop, locator_path, _context_labelplus_point(detection))
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
            "The blue LabelPlus cross marks the approximate label point; choose the corresponding original text nearest to that cross, not unrelated nearby bubble text.",
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
    local_bbox, coordinate_source = _mimo_local_bbox(payload, context_bbox)
    payload["_bbox_coordinate_source"] = coordinate_source
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
            "Use the blue LabelPlus cross as the anchor for the intended text; reject nearby text columns that are farther from that cross.",
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


def _recover_locator_from_labelplus_anchor(
    detection: dict,
    context_path: Path,
    context_bbox: tuple[int, int, int, int],
    locator: dict,
    validation: dict,
) -> dict:
    anchor = _context_labelplus_point(detection)
    context_size = (context_bbox[2] - context_bbox[0], context_bbox[3] - context_bbox[1])
    local_bbox = _locator_bbox_for_anchor_recovery(locator, context_size)
    if (
        not _can_try_anchor_recovery(validation)
        or anchor is None
        or local_bbox is None
    ):
        return {"status": "failed", "failure_reason": "anchor_recovery_not_applicable"}
    ax, ay = anchor
    bx1, by1, bx2, by2 = [int(value) for value in local_bbox]
    min_below_anchor = ay - 32 if validation.get("status") == "accepted" else ay + 18
    if by1 < min_below_anchor or bx2 <= ax - 40 or bx1 >= ax + 40:
        return {"status": "failed", "failure_reason": "anchor_recovery_locator_not_below_anchor"}
    try:
        with Image.open(context_path) as image:
            rgb = image.convert("RGB")
            recovered = _recover_dark_text_ink_column_near_anchor(rgb, anchor, tuple(local_bbox))
            recovery_method = "recover_dark_text_ink_column_near_labelplus_anchor"
            if recovered is None:
                recovered = _recover_light_text_ink_band_near_anchor(rgb, anchor, tuple(local_bbox))
                recovery_method = "recover_light_text_ink_band_near_labelplus_anchor"
    except (FileNotFoundError, OSError, ValueError):
        return {"status": "failed", "failure_reason": "anchor_recovery_image_unavailable"}
    if recovered is None:
        return {"status": "failed", "failure_reason": "anchor_recovery_no_light_text_band"}
    right_trim_method = None
    if recovery_method == "recover_light_text_ink_band_near_labelplus_anchor":
        recovered, right_trim_method = _trim_sparse_right_component_after_anchor_recovery(image, recovered, anchor)
    result = dict(locator)
    result["status"] = "ok"
    result.pop("failure_reason", None)
    result.pop("retry_failure_reason", None)
    result["local_bbox_xyxy"] = list(recovered)
    result["global_bbox_xyxy"] = list(_global_bbox(context_bbox, recovered))
    result["anchor_recovery_of_validation"] = validation.get("failure_reason") or "accepted_bbox_not_tight"
    refinement = {
        "method": recovery_method,
        "original_local_bbox_xyxy": [int(value) for value in local_bbox],
        "refined_local_bbox_xyxy": list(recovered),
        "labelplus_anchor_xy": anchor,
    }
    if right_trim_method:
        refinement["right_trim_method"] = right_trim_method
    result["refinement"] = refinement
    return result


def _recover_dark_text_locator_from_labelplus_anchor(
    detection: dict,
    context_path: Path,
    context_bbox: tuple[int, int, int, int],
    locator: dict,
    validation: dict,
) -> dict:
    anchor = _context_labelplus_point(detection)
    context_size = (context_bbox[2] - context_bbox[0], context_bbox[3] - context_bbox[1])
    local_bbox = _locator_bbox_for_anchor_recovery(locator, context_size)
    if (
        validation.get("failure_reason") != "fallback_locator_semantic_rejected"
        or validation.get("bbox_targets_unrelated_text") is not True
        or anchor is None
        or local_bbox is None
    ):
        return {"status": "failed", "failure_reason": "dark_anchor_recovery_not_applicable"}
    try:
        with Image.open(context_path) as image:
            recovered = _recover_dark_text_ink_column_near_anchor(image.convert("RGB"), anchor, tuple(local_bbox))
    except (FileNotFoundError, OSError, ValueError):
        return {"status": "failed", "failure_reason": "dark_anchor_recovery_image_unavailable"}
    if recovered is None:
        return {"status": "failed", "failure_reason": "dark_anchor_recovery_no_text_column"}
    result = dict(locator)
    result["status"] = "ok"
    result.pop("failure_reason", None)
    result.pop("retry_failure_reason", None)
    result["local_bbox_xyxy"] = list(recovered)
    result["global_bbox_xyxy"] = list(_global_bbox(context_bbox, recovered))
    result["anchor_recovery_of_validation"] = validation.get("failure_reason") or "fallback_locator_semantic_rejected"
    result["refinement"] = {
        "method": "recover_dark_text_ink_column_near_labelplus_anchor",
        "original_local_bbox_xyxy": [int(value) for value in local_bbox],
        "refined_local_bbox_xyxy": list(recovered),
        "labelplus_anchor_xy": anchor,
    }
    return result


def _accepted_locator_is_suspiciously_below_anchor(locator: dict, validation: dict, detection: dict) -> bool:
    if validation.get("status") != "accepted" or validation.get("tight_enough") is not True:
        return False
    anchor = _context_labelplus_point(detection)
    local_bbox = locator.get("local_bbox_xyxy")
    if anchor is None or not isinstance(local_bbox, list) or len(local_bbox) != 4:
        return False
    ax, ay = anchor
    x1, y1, x2, y2 = [int(value) for value in local_bbox]
    bbox_width = x2 - x1
    bbox_height = y2 - y1
    is_vertical_target = bbox_height >= max(bbox_width * 1.25, bbox_width + 24)
    if is_vertical_target and y1 <= ay + 24:
        return False
    if y2 <= ay + 48:
        return False
    return x1 <= ax + 40 and x2 >= ax - 40


def _with_rejected_locator_attempt(locator: dict, key: str, attempt: dict, validation: dict) -> dict:
    result = dict(locator)
    result[key] = {
        "status": "rejected",
        "local_bbox_xyxy": attempt.get("local_bbox_xyxy"),
        "global_bbox_xyxy": attempt.get("global_bbox_xyxy"),
        "refinement": attempt.get("refinement"),
        "validation": {
            "status": validation.get("status"),
            "tight_enough": validation.get("tight_enough"),
            "failure_reason": validation.get("failure_reason"),
            "reasoning_summary": validation.get("reasoning_summary"),
            "validation_image_path": validation.get("validation_image_path"),
        },
    }
    return result


def _cv_tightness_override(locator: dict, validation: dict, context_size: tuple[int, int]) -> dict | None:
    if not _semantically_accepted_loose_validation(validation):
        return None
    refinement = locator.get("refinement") or {}
    if refinement.get("method") not in CV_TIGHTNESS_REFINEMENT_METHODS:
        return None
    local_bbox = locator.get("local_bbox_xyxy")
    if not isinstance(local_bbox, list) or len(local_bbox) != 4:
        return None
    width, height = context_size
    x1, y1, x2, y2 = [int(value) for value in local_bbox]
    if width <= 0 or height <= 0 or x2 <= x1 or y2 <= y1:
        return None
    bbox_width = x2 - x1
    bbox_height = y2 - y1
    width_ratio = bbox_width / width
    height_ratio = bbox_height / height
    area_ratio = (bbox_width * bbox_height) / (width * height)
    if (
        area_ratio > CV_TIGHTNESS_MAX_AREA_RATIO
        or min(width_ratio, height_ratio) > CV_TIGHTNESS_MAX_SHORT_SIDE_RATIO
        or max(width_ratio, height_ratio) > CV_TIGHTNESS_MAX_LONG_SIDE_RATIO
    ):
        return None
    return {
        "status": "accepted",
        "reason": "semantic_correct_after_cv_refinement",
        "refinement_method": refinement.get("method"),
        "bbox_area_ratio": round(area_ratio, 4),
        "bbox_width_ratio": round(width_ratio, 4),
        "bbox_height_ratio": round(height_ratio, 4),
    }


def _semantically_accepted_loose_validation(validation: dict) -> bool:
    return (
        validation.get("status") == "accepted"
        and validation.get("semantic_correct") is True
        and validation.get("tight_enough") is not True
        and validation.get("bbox_on_blank_area") is False
        and validation.get("bbox_targets_unrelated_text") is False
    )


def _locator_bbox_for_anchor_recovery(locator: dict, context_size: tuple[int, int]) -> list[int] | None:
    local_bbox = locator.get("local_bbox_xyxy")
    if isinstance(local_bbox, list) and len(local_bbox) == 4:
        return [int(value) for value in local_bbox]
    for key in ("retry_raw_text", "raw_text"):
        raw_text = locator.get(key)
        if not raw_text:
            continue
        try:
            payload = _mimo_object_payload(str(raw_text))
            values = _number_list(payload.get("bbox_xyxy") or payload.get("bbox"), "bbox_xyxy")
        except Exception:
            continue
        return _clamped_bbox_for_anchor_recovery(values, context_size)
    return None


def _clamped_bbox_for_anchor_recovery(values: list[float], context_size: tuple[int, int]) -> list[int] | None:
    width, height = context_size
    if len(values) != 4:
        return None
    x1, y1, x2, y2 = [int(round(value)) for value in values]
    x1, y1 = max(0, min(width - 1, x1)), max(0, min(height - 1, y1))
    x2, y2 = max(1, min(width, x2)), max(1, min(height, y2))
    if x2 <= x1 or y2 <= y1:
        return None
    return [x1, y1, x2, y2]


def _can_try_anchor_recovery(validation: dict) -> bool:
    return validation.get("failure_reason") == "fallback_locator_semantic_rejected" or (
        validation.get("status") == "accepted" and validation.get("tight_enough") is not True
    )


def _recover_light_text_ink_band_near_anchor(
    image: Image.Image,
    anchor_xy: list[int],
    rejected_bbox: tuple[int, int, int, int],
) -> tuple[int, int, int, int] | None:
    width, height = image.size
    ax, ay = anchor_xy
    bx1, by1, bx2, _ = rejected_bbox
    window_x1 = max(0, min(bx1 - 60, ax - 420))
    window_x2 = min(width, max(bx2 + 60, ax + 260))
    window_y1 = max(0, ay - 120)
    window_y2 = min(height, max(by1 + 8, ay + 24))
    if window_x2 - window_x1 < 120 or window_y2 - window_y1 < 80:
        return None
    candidate = _trim_bbox_to_light_text_ink_support(image, (window_x1, window_y1, window_x2, window_y2))
    if candidate == (window_x1, window_y1, window_x2, window_y2):
        return None
    cx1, cy1, cx2, cy2 = candidate
    if cy1 > ay + 8 or cy2 <= ay - 96:
        return None
    if not (cx1 <= ax <= cx2 or abs(_bbox_center_x(candidate) - ax) <= max(80, (cx2 - cx1) * 0.45)):
        return None
    candidate = _cap_recovered_anchor_band_height(image, candidate, ay)
    return candidate


def _recover_dark_text_ink_column_near_anchor(
    image: Image.Image,
    anchor_xy: list[int],
    rejected_bbox: tuple[int, int, int, int],
) -> tuple[int, int, int, int] | None:
    width, height = image.size
    ax, ay = anchor_xy
    bx1, _, bx2, _ = rejected_bbox
    window_x1 = max(0, min(ax - 72, bx1 - 96))
    window_x2 = min(width, max(ax + 42, bx2 + 12))
    window_y1 = max(0, ay - 170)
    window_y2 = min(height, ay + 110)
    if window_x2 - window_x1 < 48 or window_y2 - window_y1 < 80:
        return None
    gray = np.array(image.convert("L"), dtype=np.uint8)
    crop = gray[window_y1:window_y2, window_x1:window_x2]
    if crop.size == 0:
        return None
    dark = crop < 95
    components = _dark_component_bboxes(dark)
    if not components:
        return None
    candidates = []
    for local_bbox in _merge_nearby_dark_text_components(components, dark.shape):
        x1, y1, x2, y2 = local_bbox
        bbox_width = x2 - x1
        bbox_height = y2 - y1
        if bbox_width < 4 or bbox_height < 28:
            continue
        if bbox_width > 54 or bbox_height / max(1, bbox_width) < 1.35:
            continue
        global_bbox = (window_x1 + x1, window_y1 + y1, window_x1 + x2, window_y1 + y2)
        gx1, gy1, gx2, gy2 = global_bbox
        if not (gx1 - 24 <= ax <= gx2 + 36 and gy1 - 24 <= ay <= gy2 + 48):
            continue
        area = bbox_width * bbox_height
        dark_count = int(dark[y1:y2, x1:x2].sum())
        fill = dark_count / max(1, area)
        if fill > 0.42:
            continue
        score = dark_count - abs(((gx1 + gx2) / 2) - ax) * 0.8 - abs(((gy1 + gy2) / 2) - ay) * 0.25
        candidates.append((score, global_bbox))
    if not candidates:
        return None
    _, best = max(candidates, key=lambda item: item[0])
    return _pad_local_bbox(best, width, height, 4, 6)


def _dark_component_bboxes(binary: np.ndarray) -> list[tuple[int, int, int, int, int]]:
    height, width = binary.shape
    visited = np.zeros_like(binary, dtype=bool)
    bboxes: list[tuple[int, int, int, int, int]] = []
    for start_y, start_x in zip(*np.where(binary & ~visited)):
        stack = [(int(start_x), int(start_y))]
        visited[start_y, start_x] = True
        xs: list[int] = []
        ys: list[int] = []
        while stack:
            x, y = stack.pop()
            xs.append(x)
            ys.append(y)
            for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if nx < 0 or ny < 0 or nx >= width or ny >= height:
                    continue
                if visited[ny, nx] or not binary[ny, nx]:
                    continue
                visited[ny, nx] = True
                stack.append((nx, ny))
        area = len(xs)
        if area < 8:
            continue
        x1, x2 = min(xs), max(xs) + 1
        y1, y2 = min(ys), max(ys) + 1
        bbox_width = x2 - x1
        bbox_height = y2 - y1
        if area > 2800 or bbox_width > 74 or bbox_height > 190:
            continue
        bboxes.append((x1, y1, x2, y2, area))
    return bboxes


def _merge_nearby_dark_text_components(
    components: list[tuple[int, int, int, int, int]],
    shape: tuple[int, int],
) -> list[tuple[int, int, int, int]]:
    height, width = shape
    groups: list[list[tuple[int, int, int, int, int]]] = []
    for component in sorted(components, key=lambda item: (item[0] + item[2]) / 2):
        cx = (component[0] + component[2]) / 2
        for group in groups:
            group_center = np.mean([(item[0] + item[2]) / 2 for item in group])
            if abs(cx - float(group_center)) <= 20:
                group.append(component)
                break
        else:
            groups.append([component])

    merged: list[tuple[int, int, int, int]] = []
    for group in groups:
        if len(group) < 2:
            continue
        x1 = max(0, min(item[0] for item in group) - 2)
        y1 = max(0, min(item[1] for item in group) - 2)
        x2 = min(width, max(item[2] for item in group) + 2)
        y2 = min(height, max(item[3] for item in group) + 2)
        merged.append((x1, y1, x2, y2))
    return merged


def _pad_local_bbox(
    bbox: tuple[int, int, int, int],
    width: int,
    height: int,
    x_pad: int,
    y_pad: int,
) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = bbox
    return max(0, x1 - x_pad), max(0, y1 - y_pad), min(width, x2 + x_pad), min(height, y2 + y_pad)


def _trim_sparse_right_component_after_anchor_recovery(
    image: Image.Image,
    bbox: tuple[int, int, int, int],
    anchor_xy: list[int],
) -> tuple[tuple[int, int, int, int], str | None]:
    x1, y1, x2, y2 = bbox
    width = x2 - x1
    if width < 240:
        return bbox, None
    gray = np.array(image.convert("L"), dtype=np.uint8)
    crop = gray[y1:y2, x1:x2]
    if crop.size == 0:
        return bbox, None
    dark = crop < 105
    col_density = dark.mean(axis=0)
    peak = float(col_density.max())
    if peak < 0.08:
        return bbox, None
    divider_x2 = _right_panel_divider_cap_x2(col_density, x1, x2, anchor_xy)
    if divider_x2 is not None:
        return (x1, y1, divider_x2, y2), "trim_right_panel_divider"
    smoothed = np.convolve(col_density, np.ones(9) / 9, mode="same")
    strong_threshold = max(0.18, min(0.32, peak * 0.30))
    strong_runs = _true_runs(smoothed >= strong_threshold, min_width=5)
    if not strong_runs:
        return bbox, None
    ax, _ = anchor_xy
    anchor_col = ax - x1
    eligible_runs = [run for run in strong_runs if run[0] <= anchor_col + 128]
    if not eligible_runs:
        return bbox, None
    support_end = max(run[1] for run in eligible_runs)
    trimmed_x2 = x1 + support_end + 16
    if trimmed_x2 <= ax + 32 or x2 - trimmed_x2 < 36:
        return bbox, None
    if trimmed_x2 - x1 < max(180, int(width * 0.55)):
        return bbox, None
    tail = col_density[support_end:]
    body = col_density[max(0, support_end - 140) : support_end]
    if tail.size == 0 or body.size == 0:
        return bbox, None
    if float(tail.mean()) > max(0.14, float(body.mean()) * 0.75):
        return bbox, None
    return (x1, y1, trimmed_x2, y2), "trim_sparse_right_screentone_component"


def _right_panel_divider_cap_x2(
    col_density: np.ndarray,
    x1: int,
    x2: int,
    anchor_xy: list[int],
) -> int | None:
    ax, _ = anchor_xy
    width = x2 - x1
    anchor_col = ax - x1
    if x2 <= ax + 80 or anchor_col < 0:
        return None
    threshold = max(0.82, float(col_density.max()) * 0.82)
    support = col_density >= threshold
    runs = _true_runs(support, min_width=6)
    for start, end in runs:
        divider_x1 = x1 + start
        divider_x2 = x1 + end
        if divider_x1 <= ax + 24:
            continue
        if divider_x2 >= x2 - 24:
            continue
        left_width = divider_x1 - x1
        right_width = x2 - divider_x2
        if left_width < max(220, int(width * 0.55)) or right_width < 60:
            continue
        return max(x1 + 1, divider_x1 - 4)
    return None


def _bbox_center_x(bbox: tuple[int, int, int, int]) -> float:
    return (bbox[0] + bbox[2]) / 2


def _cap_recovered_anchor_band_height(
    image: Image.Image,
    bbox: tuple[int, int, int, int],
    anchor_y: int,
) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = bbox
    if y2 - y1 < 110:
        return bbox
    gray = np.array(image.convert("L"), dtype=np.uint8)
    crop = gray[y1:y2, x1:x2]
    if crop.size == 0:
        return bbox
    row_density = (crop < 105).mean(axis=1)
    peak = float(row_density.max())
    if peak < 0.12:
        return bbox
    tail_threshold = max(0.06, peak * 0.32)
    active = np.flatnonzero(row_density >= tail_threshold)
    if len(active) == 0:
        return bbox
    capped_y2 = min(y2, y1 + int(active.max()) + 12)
    if capped_y2 < anchor_y + 16:
        capped_y2 = min(y2, anchor_y + 16)
    if capped_y2 <= y1 + 48 or y2 - capped_y2 < 18:
        return bbox
    return x1, y1, x2, capped_y2


def _relocate_after_semantic_rejection(
    detection: dict,
    context_path: Path,
    context_bbox: tuple[int, int, int, int],
    locator: dict,
    validation: dict,
    mimo_client,
) -> dict:
    if mimo_client is None:
        return {"status": "failed", "failure_reason": "mimo_client_required_for_semantic_locator_retry"}
    width = context_bbox[2] - context_bbox[0]
    height = context_bbox[3] - context_bbox[1]
    prompt = "\n".join(
        [
            "Previous yellow bbox validation rejected the locator result.",
            f"Crop dimensions are width={width} and height={height} pixels.",
            f"Chinese translation: {detection.get('translated_text', '')}",
            f"Previous bbox_xyxy: {locator.get('local_bbox_xyxy')}",
            f"Validation feedback: {validation.get('reasoning_summary', '')}",
            "Use the feedback to return a corrected crop-local bbox for the original Japanese text.",
            "If feedback says the target is above, below, left, or right of the yellow bbox, move the bbox accordingly.",
            "Return only JSON with bbox_xyxy, confidence, and reasoning_summary.",
        ]
    )
    response = mimo_client.analyze_image(
        context_path,
        prompt,
        kind="phase6_fallback_text_locator_semantic_retry",
        max_completion_tokens=800,
    )
    try:
        payload, local_bbox = _parse_mimo_locator_response(response, context_bbox)
    except Exception as exc:
        return {
            "status": "failed",
            "failure_reason": f"invalid_mimo_bbox_semantic_retry:{type(exc).__name__}",
            "raw_text": response.get("raw_text", ""),
            "locator_image_path": str(context_path),
            "request": response.get("request"),
            "response": response.get("response"),
            "first_raw_text": locator.get("raw_text", ""),
            "first_validation_raw_text": validation.get("raw_text", ""),
        }
    result = _fallback_locator_payload(payload, local_bbox, response, context_bbox, context_path)
    result["first_raw_text"] = locator.get("raw_text", "")
    result["first_request"] = locator.get("request")
    result["first_response"] = locator.get("response")
    result["first_validation_raw_text"] = validation.get("raw_text", "")
    result["semantic_retry_of_validation"] = validation.get("failure_reason", "fallback_locator_semantic_rejected")
    return result


def _tighten_accepted_locator_bbox(
    detection: dict,
    context_path: Path,
    context_bbox: tuple[int, int, int, int],
    locator: dict,
    validation: dict,
    mimo_client,
) -> dict:
    if mimo_client is None:
        return {"status": "failed", "failure_reason": "mimo_client_required_for_tightness_retry"}
    width = context_bbox[2] - context_bbox[0]
    height = context_bbox[3] - context_bbox[1]
    prompt = "\n".join(
        [
            "The previous bbox was semantically correct but too loose.",
            f"Crop dimensions are width={width} and height={height} pixels.",
            f"Chinese translation: {detection.get('translated_text', '')}",
            f"Previous bbox_xyxy: {locator.get('local_bbox_xyxy')}",
            f"Validation feedback: {validation.get('reasoning_summary', '')}",
            "Return a tighter crop-local bbox around only the visible original Japanese text.",
            "Keep all visible target characters, but remove surrounding blank space, characters' hair, panel background, unrelated text, and UI/grid marks.",
            "Return only JSON with bbox_xyxy, confidence, and reasoning_summary.",
        ]
    )
    response = mimo_client.analyze_image(
        context_path,
        prompt,
        kind="phase6_fallback_text_locator_tightness_retry",
        max_completion_tokens=800,
    )
    try:
        payload, local_bbox = _parse_mimo_locator_response(response, context_bbox)
    except Exception as exc:
        return {
            "status": "failed",
            "failure_reason": f"invalid_mimo_bbox_tightness_retry:{type(exc).__name__}",
            "raw_text": response.get("raw_text", ""),
            "locator_image_path": str(context_path),
            "request": response.get("request"),
            "response": response.get("response"),
            "first_raw_text": locator.get("raw_text", ""),
            "first_validation_raw_text": validation.get("raw_text", ""),
        }
    result = _fallback_locator_payload(payload, local_bbox, response, context_bbox, context_path)
    result["first_raw_text"] = locator.get("raw_text", "")
    result["first_request"] = locator.get("request")
    result["first_response"] = locator.get("response")
    result["first_validation_raw_text"] = validation.get("raw_text", "")
    result["tightness_retry_of_validation"] = "accepted_bbox_not_tight"
    return result


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
        "bbox_coordinate_source": payload.get("_bbox_coordinate_source"),
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
    needs_tighter_edit_mask = accepted and tight_enough is not True
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
        "needs_tighter_edit_mask": needs_tighter_edit_mask,
        "bbox_padding_px": 0,
        "failure_reason": None if accepted else "fallback_locator_semantic_rejected",
        "validation_image_path": str(validation_image_path),
        "raw_text": response.get("raw_text", ""),
        "request": response.get("request"),
        "response": response.get("response"),
    }


def _should_retry_fallback_validation(validation: dict) -> bool:
    inconclusive_semantic_rejection = (
        validation.get("tight_enough") is True
        and validation.get("bbox_on_blank_area") is False
        and validation.get("bbox_targets_unrelated_text") is False
        and validation.get("semantic_correct") is not True
    )
    return inconclusive_semantic_rejection or _has_contradictory_positive_semantic_reasoning(validation)


def _has_contradictory_positive_semantic_reasoning(validation: dict) -> bool:
    if (
        validation.get("semantic_correct") is not False
        or validation.get("bbox_on_blank_area") is True
        or validation.get("bbox_targets_unrelated_text") is True
    ):
        return False
    summary = str(validation.get("reasoning_summary") or "").lower()
    visible = str(validation.get("visible_original_text") or "").strip()
    if not visible:
        return False
    positive_markers = (
        "corresponds to the chinese translation",
        "corresponds to",
        "matches the meaning",
        "correctly identifies",
        "correctly targets",
        "targets the correct",
    )
    return any(marker in summary for marker in positive_markers)


def _write_locator_grid_image(crop: Image.Image, output_path: Path, labelplus_point_xy: list[int] | None = None) -> Path:
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
    _draw_labelplus_cross(draw, labelplus_point_xy, width, height)
    draw.text((6, max(4, height - 18)), f"w={width} h={height}", fill=(255, 0, 0, 255), font=font)
    image.save(output_path)
    return output_path


def _context_labelplus_point(detection: dict) -> list[int] | None:
    point = (detection.get("fallback") or {}).get("context_labelplus_point_xy")
    if not isinstance(point, list) or len(point) != 2:
        return None
    return [int(point[0]), int(point[1])]


def _draw_labelplus_cross(draw: ImageDraw.ImageDraw, point: list[int] | None, width: int, height: int) -> None:
    if point is None:
        return
    x, y = point
    if not (0 <= x < width and 0 <= y < height):
        return
    color = (0, 90, 255, 235)
    draw.line((max(0, x - 18), y, min(width - 1, x + 18), y), fill=color, width=4)
    draw.line((x, max(0, y - 18), x, min(height - 1, y + 18)), fill=color, width=4)
    draw.ellipse((x - 7, y - 7, x + 7, y + 7), outline=color, width=3)


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


def _write_fallback_replacement_grid(run_dir: Path, rows: list[dict]) -> Path | None:
    tiles: list[tuple[str, Path]] = []
    for row in rows:
        cleanup = row.get("cleanup") or {}
        if not row.get("fallback_locator"):
            continue
        record_id = row["record_id"]
        safe_id = _safe_name(record_id)
        _append_existing_tile(tiles, f"{record_id}\nlocator bbox", run_dir / "debug" / "fallback_locator_overlays" / f"{safe_id}.png")
        gpt_payload = row.get("gpt_image2_edit") or {}
        request = gpt_payload.get("request") or {}
        edit_context = gpt_payload.get("edit_context") or {}
        _append_existing_tile(tiles, f"{record_id}\nedit input", edit_context.get("input_path") or request.get("image_path"))
        mask_preview = _fallback_mask_preview(run_dir, record_id, edit_context.get("mask_path") or request.get("mask_path"))
        _append_existing_tile(tiles, f"{record_id}\ntransparent mask", mask_preview)
        _append_existing_tile(
            tiles,
            f"{record_id}\ngpt-image-2 output",
            gpt_payload.get("normalized_output_path") or gpt_payload.get("output_path"),
        )
        _append_existing_tile(tiles, f"{record_id}\nfinal replacement", cleanup.get("replacement_crop_path"))
    if not tiles:
        return None
    return write_grid(
        run_dir / "visuals" / "fallback-replacement-grid.png",
        tiles,
        columns=near_square_columns(len(tiles)),
        tile_size=(330, 330),
    )


def _append_existing_tile(tiles: list[tuple[str, Path]], label: str, path: str | Path | None) -> None:
    if not path:
        return
    candidate = Path(path)
    if candidate.exists():
        tiles.append((label, candidate))


def _fallback_mask_preview(run_dir: Path, record_id: str, mask_path: str | Path | None) -> Path | None:
    if not mask_path:
        return None
    source = Path(mask_path)
    if not source.exists():
        return None
    output = run_dir / "debug" / "fallback_replacement_mask_previews" / f"{_safe_name(record_id)}.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as image:
        alpha = np.array(image.convert("RGBA").getchannel("A"), dtype=np.uint8)
    preview = np.full((*alpha.shape, 3), 235, dtype=np.uint8)
    preview[alpha == 0] = (255, 70, 70)
    preview[alpha > 0] = (230, 230, 230)
    Image.fromarray(preview, mode="RGB").save(output)
    return output


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


def _write_fallback_gpt_edit_mask(
    image_path: Path,
    size: tuple[int, int],
    local_bbox: tuple[int, int, int, int],
    output_path: Path,
    mask_shape: str,
) -> Path:
    if mask_shape == "rect":
        return _write_local_gpt_mask(size, local_bbox, output_path)
    if mask_shape != "text_ink":
        raise ValueError(f"unsupported_fallback_gpt_mask_shape:{mask_shape}")

    with Image.open(image_path) as image:
        crop = image.convert("RGB").resize(size).crop(local_bbox)
    text_mask = build_text_mask(crop, dark_threshold=170, dilate_px=5, polarity="dark_on_light")
    full_mask = Image.new("L", size, 0)
    full_mask.paste(text_mask, local_bbox[:2])
    build_gpt_edit_mask(full_mask).save(output_path)
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
        mask_path = edit_context.get("mask_path")
        if mask_path:
            original = _compose_masked_edit_crop_to_context(original, edited, local_context_bbox, Path(mask_path))
            original.save(output_path)
            return
        edited = _expand_edit_crop_to_context(edited, original, local_context_bbox)
    else:
        edited = edited.resize(size)
    original = _compose_gpt_replacement_region(original, edited, local_bbox)
    original.save(output_path)


def _compose_masked_edit_crop_to_context(
    original: Image.Image,
    edited: Image.Image,
    local_context_bbox: tuple[int, int, int, int],
    mask_path: Path,
) -> Image.Image:
    x1, y1, x2, y2 = local_context_bbox
    patch_size = (x2 - x1, y2 - y1)
    if patch_size[0] <= 0 or patch_size[1] <= 0:
        return original
    patch = edited.convert("RGB").resize(patch_size)
    with Image.open(mask_path) as mask_image:
        mask_alpha = mask_image.convert("RGBA").getchannel("A").resize(patch_size)
    editable_alpha = mask_alpha.point(lambda value: 255 - value)
    canvas = original.copy()
    canvas.paste(patch, (x1, y1), editable_alpha)
    return canvas


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
    if _looks_light_text_on_dark(original, local_bbox):
        light_alpha = _light_text_alpha(edited, local_bbox)
        if light_alpha is not None:
            cleaned = original.copy()
            ImageDraw.Draw(cleaned).rectangle(local_bbox, fill=_local_dark_background_color(original, local_bbox))
            cleaned.paste(edited, (0, 0), light_alpha)
            return cleaned

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


def _looks_light_text_on_dark(original: Image.Image, local_bbox: tuple[int, int, int, int]) -> bool:
    gray = np.array(original.convert("L"), dtype=np.uint8)
    x1, y1, x2, y2 = local_bbox
    region = gray[y1:y2, x1:x2]
    if region.size == 0:
        return False
    return float((region < 80).mean()) >= 0.35 and float((region > 180).mean()) >= 0.03


def _light_text_alpha(edited: Image.Image, local_bbox: tuple[int, int, int, int]) -> Image.Image | None:
    gray = np.array(edited.convert("L"), dtype=np.uint8)
    x1, y1, x2, y2 = local_bbox
    light = np.zeros_like(gray, dtype=np.uint8)
    light_region = gray[y1:y2, x1:x2] > 205
    if int(light_region.sum()) < 20:
        return None
    light[y1:y2, x1:x2] = light_region.astype(np.uint8) * 255
    return Image.fromarray(light, mode="L")


def _local_dark_background_color(original: Image.Image, local_bbox: tuple[int, int, int, int]) -> tuple[int, int, int]:
    array = np.array(original.convert("RGB"), dtype=np.uint8)
    x1, y1, x2, y2 = local_bbox
    region = array[y1:y2, x1:x2]
    if region.size == 0:
        return (0, 0, 0)
    luma = region.astype(np.float32).mean(axis=2)
    samples = region[luma <= 80]
    if len(samples) < 12:
        return (0, 0, 0)
    median = np.median(samples, axis=0)
    return tuple(int(value) for value in median)


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
    payload = _loads_mimo_json_payload(_strip_json_wrapper(raw_text))
    if isinstance(payload, list):
        if not payload or not isinstance(payload[0], dict):
            raise ValueError("mimo_bbox_array_empty_or_invalid")
        payload = payload[0]
    if not isinstance(payload, dict):
        raise ValueError("mimo_bbox_payload_not_object")
    return payload


def _loads_mimo_json_payload(text: str) -> object:
    try:
        return json.loads(text)
    except json.JSONDecodeError as first_error:
        try:
            payload, _ = json.JSONDecoder().raw_decode(text)
        except json.JSONDecodeError:
            raise first_error
        return payload


def _refine_fallback_locator_bbox(locator: dict, context_path: str | Path, context_bbox: tuple[int, int, int, int]) -> dict:
    local_bbox = locator.get("local_bbox_xyxy")
    if locator.get("status") != "ok" or not isinstance(local_bbox, list) or len(local_bbox) != 4:
        return locator
    try:
        with Image.open(context_path) as image:
            rgb = image.convert("RGB")
            original = tuple(int(value) for value in local_bbox)
            for method, trimmer in (
                ("trim_to_dark_background_support", _trim_bbox_to_dark_background_support),
                ("trim_to_light_text_ink_support", _trim_bbox_to_light_text_ink_support),
                ("trim_to_dark_vertical_text_column_support", _trim_bbox_to_dark_vertical_text_column_support),
            ):
                refined = trimmer(rgb, original)
                if refined != original:
                    break
            else:
                refined = original
                method = ""
    except (FileNotFoundError, OSError, ValueError):
        return locator
    if refined == tuple(int(value) for value in local_bbox):
        return locator
    result = dict(locator)
    result["local_bbox_xyxy"] = list(refined)
    result["global_bbox_xyxy"] = list(_global_bbox(context_bbox, refined))
    result["refinement"] = {
        "method": method,
        "original_local_bbox_xyxy": [int(value) for value in local_bbox],
        "refined_local_bbox_xyxy": list(refined),
    }
    return result


def _trim_bbox_to_dark_background_support(image: Image.Image, bbox: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = bbox
    if x2 - x1 < 80 or y2 - y1 < 16:
        return bbox
    gray = np.array(image.convert("L"), dtype=np.uint8)
    crop = gray[y1:y2, x1:x2]
    if crop.size == 0:
        return bbox
    dark_ratio = (crop < 90).mean(axis=0)
    support = dark_ratio >= 0.25
    runs = _true_runs(support, min_width=8)
    if not runs:
        return bbox
    best = max(runs, key=lambda item: (item[1] - item[0], float(dark_ratio[item[0] : item[1]].mean())))
    run_width = best[1] - best[0]
    width = x2 - x1
    if run_width >= width * 0.9:
        return bbox
    refined_x1 = max(x1, x1 + best[0] - 2)
    refined_x2 = min(x2, x1 + best[1] + 2)
    if refined_x2 - refined_x1 < max(24, int(width * 0.25)):
        return bbox
    return refined_x1, y1, refined_x2, y2


def _trim_bbox_to_light_text_ink_support(image: Image.Image, bbox: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = bbox
    width, height = x2 - x1, y2 - y1
    if width < 120 or height < 80:
        return bbox
    gray = np.array(image.convert("L"), dtype=np.uint8)
    crop = gray[y1:y2, x1:x2]
    if crop.size == 0:
        return bbox
    dark_ratio = float((crop < 105).mean())
    if float((crop > 168).mean()) < 0.35 or dark_ratio < 0.01 or dark_ratio > 0.35:
        return bbox
    dark = crop < 105
    row_density = dark.mean(axis=1)
    if float(row_density.max()) < 0.045:
        return bbox
    window = min(15, max(5, (height // 36) * 2 + 1))
    smoothed = np.convolve(row_density, np.ones(window) / window, mode="same")
    threshold = max(0.035, min(0.12, float(np.percentile(smoothed, 92)) * 0.55))
    min_height = max(8, min(22, height // 14))
    candidates = _light_text_ink_band_candidates(dark, smoothed, threshold, width, height, min_height)
    if not candidates:
        return bbox
    _, start, end, left, right = max(candidates, key=lambda item: item[0])
    loose_threshold = max(0.012, threshold * 0.35)
    while start > 0 and row_density[start - 1] >= loose_threshold:
        start -= 1
    while end < height and row_density[end] >= loose_threshold:
        end += 1
    y_pad = min(12, max(5, height // 50))
    x_pad = min(14, max(6, width // 80))
    refined = (max(x1, x1 + left - x_pad), max(y1, y1 + start - y_pad), min(x2, x1 + right + x_pad), min(y2, y1 + end + y_pad))
    if (refined[2] - refined[0]) * (refined[3] - refined[1]) > width * height * 0.85:
        return bbox
    if refined[3] - refined[1] < max(18, int(height * 0.08)):
        return bbox
    return refined


def _trim_bbox_to_dark_vertical_text_column_support(image: Image.Image, bbox: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = bbox
    width, height = x2 - x1, y2 - y1
    if width < 24 or width > 120 or height < 90:
        return bbox
    if width > 80:
        return bbox
    gray = np.array(image.convert("L"), dtype=np.uint8)
    crop = gray[y1:y2, x1:x2]
    if crop.size == 0:
        return bbox
    if float((crop > 210).mean()) < 0.45:
        return bbox
    dark = crop < 105
    components = _dark_component_bboxes(dark)
    candidates = _merge_nearby_dark_text_components(components, dark.shape)
    if not candidates:
        return bbox
    scored = []
    for cx1, cy1, cx2, cy2 in candidates:
        candidate_width = cx2 - cx1
        candidate_height = cy2 - cy1
        if candidate_width > max(52, width * 0.72) or candidate_height < 40:
            continue
        if candidate_height / max(1, candidate_width) < 1.35:
            continue
        fill = float(dark[cy1:cy2, cx1:cx2].mean())
        if fill > 0.45:
            continue
        score = int(dark[cy1:cy2, cx1:cx2].sum()) - abs(((cx1 + cx2) / 2) - width / 2) * 0.35
        scored.append((score, (cx1, cy1, cx2, cy2)))
    if not scored:
        return bbox
    _, local = max(scored, key=lambda item: item[0])
    padded = _pad_local_bbox(local, width, height, 5, 8)
    refined = (x1 + padded[0], y1 + padded[1], x1 + padded[2], y1 + padded[3])
    if (refined[2] - refined[0]) * (refined[3] - refined[1]) > width * height * 0.72:
        return bbox
    return refined


def _light_text_ink_band_candidates(
    dark: np.ndarray,
    smoothed: np.ndarray,
    threshold: float,
    width: int,
    height: int,
    min_height: int,
) -> list[tuple[float, int, int, int, int]]:
    candidates: list[tuple[float, int, int, int, int]] = []
    for start, end in _true_runs(smoothed >= threshold, min_width=min_height):
        band = dark[start:end, :]
        if int(band.sum()) < max(80, int(width * (end - start) * 0.025)):
            continue
        col_density = band.mean(axis=0)
        col_threshold = max(0.012, min(0.08, float(col_density.max()) * 0.18))
        columns = np.flatnonzero(col_density >= col_threshold)
        if len(columns) == 0:
            continue
        left, right = int(columns.min()), int(columns.max()) + 1
        span_ratio = (right - left) / width
        if span_ratio < 0.18:
            continue
        center = ((start + end) / 2) / height
        score = float(smoothed[start:end].mean()) * (end - start) * span_ratio * (1.0 - center * 0.2)
        candidates.append((score, start, end, left, right))
    return candidates


def _true_runs(values: np.ndarray, min_width: int) -> list[tuple[int, int]]:
    runs: list[tuple[int, int]] = []
    start: int | None = None
    for index, value in enumerate(values):
        if bool(value) and start is None:
            start = index
        if (not bool(value) or index == len(values) - 1) and start is not None:
            end = index + 1 if bool(value) and index == len(values) - 1 else index
            if end - start >= min_width:
                runs.append((start, end))
            start = None
    return runs


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
    errors: list[Exception] = []
    for key in ("bbox_xyxy", "bbox"):
        if key in payload:
            try:
                bbox = _number_list(payload[key], key)
                if _looks_normalized_bbox(bbox):
                    return _validated_scaled_bbox(bbox, context_bbox, scale=1.0), key
                return _validated_pixel_bbox(bbox, context_bbox), key
            except ValueError as exc:
                errors.append(exc)
    if "bbox_percent_xyxy" in payload:
        try:
            return (
                _validated_scaled_bbox(
                    _number_list(payload["bbox_percent_xyxy"], "bbox_percent_xyxy"),
                    context_bbox,
                    scale=100.0,
                ),
                "bbox_percent_xyxy",
            )
        except ValueError as exc:
            errors.append(exc)
    if "bbox_normalized_xyxy" in payload:
        try:
            return (
                _validated_scaled_bbox(
                    _number_list(payload["bbox_normalized_xyxy"], "bbox_normalized_xyxy"),
                    context_bbox,
                    scale=1.0,
                ),
                "bbox_normalized_xyxy",
            )
        except ValueError as exc:
            errors.append(exc)
    if errors:
        raise errors[0]
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


def _validated_pixel_bbox(values: list[float], context_bbox: tuple[int, int, int, int]) -> list[int]:
    local_bbox = [int(round(value)) for value in values]
    _validate_local_bbox(local_bbox, context_bbox)
    return local_bbox


def _validated_scaled_bbox(values: list[float], context_bbox: tuple[int, int, int, int], scale: float) -> list[int]:
    local_bbox = _scaled_bbox(values, context_bbox, scale)
    _validate_local_bbox(local_bbox, context_bbox)
    return local_bbox


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
        "- `visuals/fallback-replacement-grid.png`",
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
