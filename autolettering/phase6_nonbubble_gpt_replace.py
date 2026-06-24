from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageOps

from .experiment_grid import near_square_columns
from .inpaint.nonbubble import inpaint_nonbubble_text
from .models.gpt_image import (
    GptImageConfig,
    GptImageEditClient,
    gpt_image_edit_prompt,
    gpt_image_request_summary,
    normalize_gpt_output_to_crop,
)
from .models.mimo import MimoVisionClient
from .text_bbox import matched_text_mask_bbox, selected_text_polarity
from .text_body_bbox import selected_text_body_bbox


GPT_REPLACE_SCHEMA_VERSION = "autolettering.phase6.nonbubble_gpt_replace.v1"
BT_COMPARISON_METHODS = ["opencv-tela", "patchmatch", "aot", "lama_mpe", "lama_large_512px"]


def run_phase6_nonbubble_gpt_replace(
    detection_run_dir: str | Path,
    output_root: str | Path = "outputs/runs",
    run_id: str | None = None,
    sample_limit: int = 5,
    record_ids: list[str] | None = None,
    gpt_config: GptImageConfig | None = None,
    call_gpt_image: bool = False,
    bt_methods: list[str] | None = None,
    mimo_client: MimoVisionClient | None = None,
    context_padding: int = 32,
    rect_mask_expand_px: int = 2,
) -> Path:
    run_dir = Path(output_root) / (run_id or "phase6-nonbubble-gpt-replace")
    run_dir.mkdir(parents=True, exist_ok=True)
    methods = bt_methods or BT_COMPARISON_METHODS
    detections = _load_nonbubble_detections(Path(detection_run_dir) / "detections.jsonl", sample_limit, record_ids)
    gpt_client = GptImageEditClient(gpt_config) if call_gpt_image and gpt_config else None
    rows = [
        _process_one(
            run_dir,
            detection,
            methods,
            gpt_config,
            gpt_client,
            context_padding=context_padding,
            rect_mask_expand_px=rect_mask_expand_px,
        )
        for detection in detections
    ]
    _write_jsonl(run_dir / "gpt-replace-results.jsonl", rows)
    grid_path = _write_comparison_grid(run_dir / "visuals" / "gpt-replace-bt-grid.png", rows)
    mimo_result = _write_mimo_evaluation(run_dir, grid_path, rows, mimo_client) if mimo_client else None
    _write_manifest(run_dir / "manifest.json", detection_run_dir, methods, rows, grid_path, mimo_result)
    _write_report(run_dir / "reports" / "phase6-nonbubble-gpt-replace-report.md", detection_run_dir, methods, rows, grid_path, mimo_result)
    return run_dir


def _load_nonbubble_detections(path: Path, sample_limit: int, record_ids: list[str] | None = None) -> list[dict]:
    wanted = set(record_ids or [])
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            payload = json.loads(line)
            if wanted and payload.get("record_id") not in wanted:
                continue
            if payload.get("status") == "ok" and payload.get("group_name") != "框内":
                rows.append(payload)
                if len(rows) >= sample_limit:
                    break
    return rows


def _process_one(
    run_dir: Path,
    detection: dict,
    bt_methods: list[str],
    gpt_config: GptImageConfig | None,
    gpt_client: GptImageEditClient | None,
    context_padding: int,
    rect_mask_expand_px: int,
) -> dict:
    bbox = matched_text_mask_bbox(detection) or selected_text_body_bbox(detection)
    polarity = selected_text_polarity(detection, bbox)
    context = _write_gpt_context_package(
        run_dir,
        detection,
        bbox,
        context_padding=context_padding,
        rect_mask_expand_px=rect_mask_expand_px,
    )
    bt_results = [_bt_cleanup_payload(run_dir, detection, bbox, method, polarity) for method in bt_methods]
    prompt = gpt_image_edit_prompt(detection.get("translated_text", ""))
    gpt_payload = _gpt_replace_payload(run_dir, detection["record_id"], context, prompt, gpt_config, gpt_client)
    return {
        "schema_version": GPT_REPLACE_SCHEMA_VERSION,
        "record_id": detection["record_id"],
        "image_name": detection.get("image_name"),
        "translated_text": detection.get("translated_text", ""),
        "bbox": list(bbox),
        "context_bbox": list(context["context_bbox"]),
        "local_target_bbox": list(context["local_target_bbox"]),
        "polarity": polarity,
        "status": "processed",
        "gpt_context": {key: str(value) if isinstance(value, Path) else value for key, value in context.items()},
        "gpt_image2_replace": gpt_payload,
        "bt_repairs": bt_results,
    }


def _write_gpt_context_package(
    run_dir: Path,
    detection: dict,
    bbox: tuple[int, int, int, int],
    context_padding: int,
    rect_mask_expand_px: int,
) -> dict:
    with Image.open(detection["image_path"]) as image:
        source = image.convert("RGB")
    context_bbox = _expand_bbox(bbox, source.size, context_padding)
    local_target = _offset_bbox(_expand_bbox(bbox, source.size, rect_mask_expand_px), context_bbox)
    context_crop = source.crop(context_bbox)
    mask = _transparent_rect_mask(context_crop.size, local_target)
    mask_overlay = _mask_overlay(context_crop, mask)

    safe_id = _safe_name(detection["record_id"])
    input_path = run_dir / "gpt_replace_input" / f"{safe_id}.png"
    mask_path = run_dir / "gpt_replace_mask" / f"{safe_id}.png"
    overlay_path = run_dir / "gpt_replace_mask_overlay" / f"{safe_id}.png"
    input_path.parent.mkdir(parents=True, exist_ok=True)
    mask_path.parent.mkdir(parents=True, exist_ok=True)
    overlay_path.parent.mkdir(parents=True, exist_ok=True)
    context_crop.save(input_path)
    mask.save(mask_path)
    mask_overlay.save(overlay_path)
    return {
        "input_path": input_path,
        "mask_path": mask_path,
        "mask_overlay_path": overlay_path,
        "context_bbox": context_bbox,
        "local_target_bbox": local_target,
    }


def _bt_cleanup_payload(
    run_dir: Path,
    detection: dict,
    bbox: tuple[int, int, int, int],
    method: str,
    polarity: str,
) -> dict:
    try:
        result = inpaint_nonbubble_text(
            image_path=detection["image_path"],
            bbox=bbox,
            output_dir=run_dir / "bt" / method,
            record_id=detection["record_id"],
            method=method,
            polarity=polarity,
        )
        payload = asdict(result)
        payload["status"] = "ok"
        payload["requested_method"] = method
        payload["bbox"] = list(result.bbox)
        for key in ("input_crop_path", "text_mask_path", "gpt_mask_path", "cleaned_crop_path", "before_after_path"):
            payload[key] = str(payload[key])
        return payload
    except Exception as exc:
        return {"requested_method": method, "status": "failed", "failure_reason": f"{type(exc).__name__}:{str(exc)[:500]}"}


def _gpt_replace_payload(
    run_dir: Path,
    record_id: str,
    context: dict,
    prompt: str,
    config: GptImageConfig | None,
    client: GptImageEditClient | None,
) -> dict:
    summary = gpt_image_request_summary(config, context["input_path"], context["mask_path"], prompt)
    summary["mode"] = "masked_chinese_replacement"
    summary["input_scope"] = "context_crop"
    summary["target_text"] = prompt.split("Target Chinese text: ", 1)[-1] if "Target Chinese text: " in prompt else None
    if client is None:
        return {"status": "dry_run", "request": summary, "failure_reason": None}
    try:
        output_path = run_dir / "gpt_image2_replace" / f"{_safe_name(record_id)}.png"
        response = client.edit_image(context["input_path"], context["mask_path"], prompt, output_path)
        normalized = normalize_gpt_output_to_crop(
            response["output_path"],
            _image_size(context["input_path"]),
            run_dir / "gpt_image2_replace_normalized" / f"{_safe_name(record_id)}.png",
        )
        target_crop = _crop_gpt_target(
            normalized["normalized_output_path"],
            context["local_target_bbox"],
            run_dir / "gpt_image2_replace_target_crop" / f"{_safe_name(record_id)}.png",
        )
        return {"request": summary, **response, **normalized, **target_crop}
    except Exception as exc:
        return {"status": "failed", "request": summary, "failure_reason": f"{type(exc).__name__}:{str(exc)[:500]}"}


def _write_comparison_grid(output_path: Path, rows: list[dict]) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tiles: list[tuple[str, Path]] = []
    for row in rows:
        record_id = row["record_id"]
        context = row["gpt_context"]
        tiles.append((f"{record_id}\noriginal", Path(context["input_path"])))
        tiles.append((f"{record_id}\nmask", Path(context["mask_overlay_path"])))
        gpt = row.get("gpt_image2_replace", {})
        gpt_path = gpt.get("normalized_output_path") or gpt.get("output_path")
        if gpt_path:
            tiles.append((f"{record_id}\ngpt-image-2 cn", Path(gpt_path)))
        for repair in row["bt_repairs"]:
            if repair.get("status") == "ok" and repair.get("cleaned_crop_path"):
                tiles.append((f"{record_id}\n{repair['requested_method']}", Path(repair["cleaned_crop_path"])))
    return _write_grid(output_path, tiles)


def _write_mimo_evaluation(run_dir: Path, grid_path: Path, rows: list[dict], client: MimoVisionClient) -> dict:
    bt_methods = sorted(
        {repair["requested_method"] for row in rows for repair in row["bt_repairs"] if repair.get("status") == "ok"}
    )
    prompt = "\n".join(
        [
            "Evaluate this near-square manga non-bubble text experiment grid.",
            "For each record, original shows the context crop, mask shows the transparent edit area overlay, gpt-image-2 cn should replace the Japanese text with the exact Chinese translation in the same masked region.",
            "The BT method tiles are background-repair-only comparisons; do not expect Chinese text in BT tiles.",
            "Score gpt-image-2 by: exact simplified Chinese text correctness, no Japanese text remaining, typography/layout fits the original region, style/angle consistency, and preservation outside the mask.",
            "Be strict about Chinese glyph variants: for example 暂 is correct when requested, but 暫 is incorrect.",
            "Score BT methods only by Japanese text removal and background preservation.",
            f"BT methods: {json.dumps(bt_methods, ensure_ascii=False)}",
            "Return only JSON with keys: gpt_image2_scores, bt_ranking, unacceptable_methods, per_record_notes, best_overall_for_user_choice, reasoning_summary, caveats.",
        ]
    )
    response = client.analyze_image(grid_path, prompt, kind="phase6_nonbubble_gpt_replace_grid", max_completion_tokens=1600)
    output = run_dir / "reports" / "mimo-gpt-replace-evaluation.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(response, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "path": str(output),
        "status": response.get("response", {}).get("status"),
        "quality": _mimo_quality_payload(response),
    }


def _write_manifest(
    output_path: Path,
    detection_run_dir: str | Path,
    methods: list[str],
    rows: list[dict],
    grid_path: Path,
    mimo_result: dict | None,
) -> None:
    quality = _gpt_quality_counts(rows, mimo_result)
    payload = {
        "schema_version": GPT_REPLACE_SCHEMA_VERSION,
        "detection_run_dir": str(detection_run_dir),
        "bt_methods": methods,
        "record_count": len(rows),
        "gpt_ok_count": sum(1 for row in rows if row.get("gpt_image2_replace", {}).get("status") == "ok"),
        "gpt_failed_count": sum(1 for row in rows if row.get("gpt_image2_replace", {}).get("status") == "failed"),
        "gpt_dry_run_count": sum(1 for row in rows if row.get("gpt_image2_replace", {}).get("status") == "dry_run"),
        "gpt_quality_checked_count": quality["checked_count"],
        "gpt_quality_failed_count": quality["failed_count"],
        "bt_failed_count": sum(1 for row in rows for repair in row.get("bt_repairs", []) if repair.get("status") == "failed"),
        "grid_path": str(grid_path),
        "mimo": mimo_result,
    }
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_report(
    output_path: Path,
    detection_run_dir: str | Path,
    methods: list[str],
    rows: list[dict],
    grid_path: Path,
    mimo_result: dict | None,
) -> None:
    quality = _gpt_quality_counts(rows, mimo_result)
    mimo_quality = _mimo_quality(mimo_result)
    lines = [
        "# Phase 6 Non-Bubble GPT Replacement Experiment",
        "",
        f"Detection run directory: `{detection_run_dir}`",
        "",
        "## Summary",
        "",
        f"- Records processed: {len(rows)}",
        f"- BT methods: {', '.join(methods)}",
        f"- GPT image-2 replacement ok: {sum(1 for row in rows if row.get('gpt_image2_replace', {}).get('status') == 'ok')}",
        f"- GPT image-2 dry runs: {sum(1 for row in rows if row.get('gpt_image2_replace', {}).get('status') == 'dry_run')}",
        f"- GPT image-2 failures: {sum(1 for row in rows if row.get('gpt_image2_replace', {}).get('status') == 'failed')}",
        f"- GPT image-2 quality checks: {quality['checked_count']}",
        f"- GPT image-2 quality failures: {quality['failed_count']}",
        f"- BT method failures: {sum(1 for row in rows for repair in row.get('bt_repairs', []) if repair.get('status') == 'failed')}",
        "",
        "## Artifacts",
        "",
        "- `gpt-replace-results.jsonl`",
        f"- Grid: `{grid_path}`",
        "- `gpt_replace_input/*.png`",
        "- `gpt_replace_mask/*.png`",
        "- `gpt_replace_mask_overlay/*.png`",
        "- `gpt_image2_replace_normalized/*.png`",
        "- `bt/<method>/cleaned/*.png`",
    ]
    if mimo_result:
        lines.append(f"- MIMO evaluation: `{mimo_result['path']}`")
        lines.append(f"- MIMO GPT image-2 status: `{mimo_quality.get('gpt_image2_status', 'unknown')}`")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _gpt_quality_counts(rows: list[dict], mimo_result: dict | None) -> dict:
    gpt_ok_count = sum(1 for row in rows if row.get("gpt_image2_replace", {}).get("status") == "ok")
    quality = _mimo_quality(mimo_result)
    if quality.get("gpt_image2_status") not in {"acceptable", "unacceptable"}:
        return {"checked_count": 0, "failed_count": 0}
    return {
        "checked_count": gpt_ok_count,
        "failed_count": gpt_ok_count if quality["gpt_image2_status"] == "unacceptable" else 0,
    }


def _mimo_quality(mimo_result: dict | None) -> dict:
    if not isinstance(mimo_result, dict):
        return {"gpt_image2_status": "not_evaluated"}
    quality = mimo_result.get("quality")
    if isinstance(quality, dict):
        return quality
    return {"gpt_image2_status": "unknown"}


def _mimo_quality_payload(response: dict) -> dict:
    try:
        payload = json.loads(_strip_json_wrapper(response.get("raw_text", "")))
    except Exception as exc:
        return {
            "gpt_image2_status": "unknown",
            "unacceptable_methods": [],
            "failure_reason": f"invalid_mimo_quality_json:{type(exc).__name__}",
        }
    unacceptable = [str(item) for item in payload.get("unacceptable_methods", []) if str(item).strip()]
    gpt_status = "unacceptable" if any(_is_gpt_image2_method_label(item) for item in unacceptable) else "acceptable"
    return {
        "gpt_image2_status": gpt_status,
        "unacceptable_methods": unacceptable,
        "gpt_image2_scores": payload.get("gpt_image2_scores"),
        "bt_ranking": payload.get("bt_ranking"),
        "best_overall_for_user_choice": payload.get("best_overall_for_user_choice"),
        "reasoning_summary": payload.get("reasoning_summary"),
        "caveats": payload.get("caveats"),
        "failure_reason": None,
    }


def _is_gpt_image2_method_label(value: str) -> bool:
    normalized = value.lower().replace("_", "-").replace(" ", "")
    return "gpt-image-2" in normalized or "gptimage2" in normalized


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


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_grid(output_path: Path, tiles: list[tuple[str, Path]]) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    font = ImageFont.load_default()
    loaded = [(label, Image.open(path).convert("RGB")) for label, path in tiles if path.exists()]
    if not loaded:
        Image.new("RGB", (320, 180), "white").save(output_path)
        return output_path
    columns = near_square_columns(len(loaded), cell_width=310, cell_height=344)
    rows = (len(loaded) + columns - 1) // columns
    tile_w, tile_h, label_h, pad = 300, 300, 34, 10
    canvas = Image.new("RGB", (pad + columns * (tile_w + pad), pad + rows * (tile_h + label_h + pad)), "white")
    draw = ImageDraw.Draw(canvas)
    for index, (label, image) in enumerate(loaded):
        col = index % columns
        row = index // columns
        x = pad + col * (tile_w + pad)
        y = pad + row * (tile_h + label_h + pad)
        draw.rectangle((x, y, x + tile_w, y + label_h), fill=(244, 244, 244), outline=(170, 170, 170))
        _draw_multiline_label(draw, (x + 4, y + 4), label, font)
        fitted = _fit_tile(image, (tile_w, tile_h))
        canvas.paste(fitted, (x, y + label_h))
    canvas.save(output_path)
    return output_path


def _transparent_rect_mask(size: tuple[int, int], bbox: tuple[int, int, int, int]) -> Image.Image:
    mask = Image.new("RGBA", size, (0, 0, 0, 255))
    alpha = Image.new("L", size, 255)
    ImageDraw.Draw(alpha).rectangle(bbox, fill=0)
    return Image.merge("RGBA", [Image.new("L", size, 0)] * 3 + [alpha])


def _mask_overlay(image: Image.Image, mask: Image.Image) -> Image.Image:
    red = Image.new("RGB", image.size, (255, 60, 60))
    editable = ImageChops.invert(mask.getchannel("A"))
    return Image.composite(red, image.convert("RGB"), editable.point(lambda value: min(120, value))).convert("RGB")


def _crop_gpt_target(
    image_path: str | Path,
    bbox: tuple[int, int, int, int] | list[int],
    output_path: str | Path,
) -> dict:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(image_path) as image:
        image.convert("RGB").crop(tuple(int(v) for v in bbox)).save(output)
    return {"target_crop_path": str(output)}


def _expand_bbox(
    bbox: tuple[int, int, int, int],
    image_size: tuple[int, int],
    padding: int,
) -> tuple[int, int, int, int]:
    width, height = image_size
    return (
        max(0, bbox[0] - padding),
        max(0, bbox[1] - padding),
        min(width, bbox[2] + padding),
        min(height, bbox[3] + padding),
    )


def _offset_bbox(
    bbox: tuple[int, int, int, int],
    outer: tuple[int, int, int, int],
) -> tuple[int, int, int, int]:
    return bbox[0] - outer[0], bbox[1] - outer[1], bbox[2] - outer[0], bbox[3] - outer[1]


def _image_size(path: str | Path) -> tuple[int, int]:
    with Image.open(path) as image:
        return image.size


def _fit_tile(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    tile_w, tile_h = size
    copy = ImageOps.contain(image.convert("RGB"), (tile_w, tile_h), method=Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", size, "white")
    canvas.paste(copy, ((tile_w - copy.width) // 2, (tile_h - copy.height) // 2))
    return canvas


def _draw_multiline_label(draw: ImageDraw.ImageDraw, xy: tuple[int, int], label: str, font: ImageFont.ImageFont) -> None:
    x, y = xy
    for line in label.splitlines()[:2]:
        draw.text((x, y), line[:42], fill="black", font=font)
        y += 13


def _safe_name(value: str) -> str:
    return "".join(char if char.isalnum() else "-" for char in value).strip("-") or "record"
