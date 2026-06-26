from __future__ import annotations

import json
from pathlib import Path
import re

from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageOps

from .experiment_grid import near_square_columns
from .gpt_text_mask import build_text_pixel_gpt_mask
from .models.gpt_image import (
    GptImageConfig,
    GptImageEditClient,
    gpt_image_edit_prompt,
    gpt_image_request_summary,
    normalize_gpt_output_to_crop,
)
from .models.mimo import MimoVisionClient
from .text_bbox import matched_text_mask_bbox
from .text_body_bbox import selected_text_body_bbox


SEGMENTED_GPT_SCHEMA_VERSION = "autolettering.phase6.segmented_gpt_replace.v1"


def run_phase6_segmented_gpt_replace(
    detection_run_dir: str | Path,
    output_root: str | Path = "outputs/runs",
    run_id: str | None = None,
    sample_limit: int = 5,
    record_ids: list[str] | None = None,
    gpt_config: GptImageConfig | None = None,
    call_gpt_image: bool = False,
    mimo_client: MimoVisionClient | None = None,
    context_padding: int = 16,
    rect_mask_expand_px: int = 2,
    max_segment_chars: int = 8,
    max_segment_height: int = 640,
) -> Path:
    run_dir = Path(output_root) / (run_id or "phase6-segmented-gpt-replace")
    run_dir.mkdir(parents=True, exist_ok=True)
    detections = _load_nonbubble_detections(Path(detection_run_dir) / "detections.jsonl", sample_limit, record_ids)
    client = GptImageEditClient(gpt_config) if call_gpt_image and gpt_config else None
    rows = [
        _process_one(
            run_dir,
            detection,
            gpt_config,
            client,
            context_padding,
            rect_mask_expand_px,
            max_segment_chars,
            max_segment_height,
        )
        for detection in detections
    ]
    _write_jsonl(run_dir / "segmented-gpt-replace-results.jsonl", rows)
    _write_jsonl(run_dir / "cleanup-results.jsonl", _cleanup_rows(rows))
    grid = _write_grid(run_dir / "visuals" / "segmented-gpt-replace-grid.png", rows)
    mimo = _write_mimo_evaluation(run_dir, grid, rows, mimo_client) if mimo_client else None
    _write_manifest(run_dir / "manifest.json", detection_run_dir, rows, grid, mimo)
    _write_report(run_dir / "reports" / "phase6-segmented-gpt-replace-report.md", detection_run_dir, rows, grid, mimo)
    return run_dir


def _cleanup_rows(rows: list[dict]) -> list[dict]:
    cleanup_rows: list[dict] = []
    for row in rows:
        replacement = row.get("segmented_gpt_replace") or {}
        target_crop_path = replacement.get("target_crop_path")
        ok = replacement.get("status") == "ok" and bool(target_crop_path)
        cleanup_rows.append(
            {
                "record_id": row["record_id"],
                "image_name": row.get("image_name"),
                "translated_text": row.get("translated_text"),
                "status": "cleaned" if ok else "failed",
                "cleanup": {
                    "method": replacement.get("method") or "segmented_gpt_image2_masked_edit",
                    "bbox": row.get("bbox"),
                    "text_bbox": row.get("bbox"),
                    "mask_bbox": row.get("bbox"),
                    "layout_text_bbox": row.get("bbox"),
                    "cleaned_crop_path": target_crop_path,
                    "before_after_path": target_crop_path,
                    "text_overlay_required": False,
                    "replacement_method": "gpt_image2_masked_edit" if ok else None,
                    "replacement_crop_path": target_crop_path if ok else None,
                },
                "segmented_gpt_replace": replacement,
            }
        )
    return cleanup_rows


def _load_nonbubble_detections(path: Path, sample_limit: int, record_ids: list[str] | None) -> list[dict]:
    wanted = set(record_ids or [])
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            if wanted and row.get("record_id") not in wanted:
                continue
            if row.get("status") == "ok" and row.get("group_name") != "框内":
                rows.append(row)
                if len(rows) >= sample_limit:
                    break
    return rows


def _process_one(
    run_dir: Path,
    detection: dict,
    config: GptImageConfig | None,
    client: GptImageEditClient | None,
    context_padding: int,
    rect_mask_expand_px: int,
    max_segment_chars: int,
    max_segment_height: int,
) -> dict:
    bbox = matched_text_mask_bbox(detection) or selected_text_body_bbox(detection)
    translated_text = str(detection.get("translated_text", ""))
    text_segments = _text_segments(translated_text, max_segment_chars)
    context = _context_package(run_dir, detection, bbox, context_padding)
    bbox_segments = _bbox_segments(context["local_target_bbox"], len(text_segments), max_segment_height)
    segments = [
        _run_segment(
            run_dir,
            detection,
            index,
            text,
            context,
            bbox,
            local_bbox,
            rect_mask_expand_px,
            config,
            client,
        )
        for index, (text, local_bbox) in enumerate(zip(text_segments, bbox_segments), start=1)
    ]
    composed = _compose_segments(run_dir, detection["record_id"], context["input_path"], segments)
    target_crop = _crop_target(composed, context["local_target_bbox"], run_dir / "segmented_target_crop" / f"{_safe_name(detection['record_id'])}.png")
    ok = all(segment["gpt_image2"]["status"] == "ok" for segment in segments)
    return {
        "schema_version": SEGMENTED_GPT_SCHEMA_VERSION,
        "record_id": detection["record_id"],
        "image_name": detection.get("image_name"),
        "translated_text": translated_text,
        "bbox": list(bbox),
        "context": {key: str(value) if isinstance(value, Path) else value for key, value in context.items()},
        "status": "processed",
        "segments": segments,
        "segmented_gpt_replace": {
            "status": "ok" if ok else "failed",
            "segment_count": len(segments),
            "composed_context_path": str(composed),
            "target_crop_path": str(target_crop),
            "method": "segmented_gpt_image2_masked_edit",
        },
    }


def _text_segments(text: str, max_segment_chars: int) -> list[str]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    chunks: list[str] = []
    for line in [item.strip() for item in normalized.splitlines() if item.strip()]:
        if len(line) <= max_segment_chars:
            chunks.append(line)
            continue
        chunks.extend(_natural_text_chunks(line, max_segment_chars))
    return chunks or [text.strip()]


def _natural_text_chunks(line: str, max_segment_chars: int) -> list[str]:
    chunks: list[str] = []
    remaining = line
    while len(remaining) > max_segment_chars:
        split_at = _natural_split_index(remaining, max_segment_chars)
        chunks.append(remaining[:split_at])
        remaining = remaining[split_at:].strip()
    if remaining:
        chunks.append(remaining)
    return chunks


def _natural_split_index(text: str, max_segment_chars: int) -> int:
    hard_limit = max(1, min(max_segment_chars, len(text) - 1))
    candidates = _natural_boundaries(text, hard_limit)
    if candidates:
        return max(candidates)
    return hard_limit


def _natural_boundaries(text: str, hard_limit: int) -> list[int]:
    boundaries: list[int] = []
    for match in re.finditer(r"[，,。.!！?？；;、]", text[: hard_limit + 1]):
        boundary = match.end()
        if 0 < boundary <= hard_limit:
            boundaries.append(boundary)
    for index, char in enumerate(text[:hard_limit], start=1):
        if char in {"年", "月", "日"} and index < len(text):
            boundaries.append(index)
    return boundaries


def _context_package(run_dir: Path, detection: dict, bbox: tuple[int, int, int, int], padding: int) -> dict:
    with Image.open(detection["image_path"]) as image:
        source = image.convert("RGB")
    context_bbox = _expand_bbox(bbox, source.size, padding)
    context_crop = source.crop(context_bbox)
    local_target = _offset_bbox(bbox, context_bbox)
    safe_id = _safe_name(detection["record_id"])
    input_path = run_dir / "segmented_input" / f"{safe_id}.png"
    input_path.parent.mkdir(parents=True, exist_ok=True)
    context_crop.save(input_path)
    return {
        "input_path": input_path,
        "context_bbox": context_bbox,
        "local_target_bbox": local_target,
        "size": context_crop.size,
    }


def _bbox_segments(
    local_target: tuple[int, int, int, int],
    segment_count: int,
    max_segment_height: int,
) -> list[tuple[int, int, int, int]]:
    x1, y1, x2, y2 = local_target
    height = y2 - y1
    count = max(segment_count, int((height + max_segment_height - 1) // max_segment_height))
    count = max(1, count)
    return [
        (x1, round(y1 + height * index / count), x2, round(y1 + height * (index + 1) / count))
        for index in range(count)
    ][:segment_count]


def _run_segment(
    run_dir: Path,
    detection: dict,
    index: int,
    target_text: str,
    context: dict,
    page_bbox: tuple[int, int, int, int],
    local_bbox: tuple[int, int, int, int],
    rect_mask_expand_px: int,
    config: GptImageConfig | None,
    client: GptImageEditClient | None,
) -> dict:
    safe_id = _safe_name(f"{detection['record_id']}-{index}")
    segment_bbox = _expand_bbox(local_bbox, context["size"], rect_mask_expand_px)
    input_path = run_dir / "segmented_gpt_input" / f"{safe_id}.png"
    mask_path = run_dir / "segmented_gpt_mask" / f"{safe_id}.png"
    overlay_path = run_dir / "segmented_gpt_mask_overlay" / f"{safe_id}.png"
    input_path.parent.mkdir(parents=True, exist_ok=True)
    mask_path.parent.mkdir(parents=True, exist_ok=True)
    overlay_path.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(context["input_path"]) as image:
        segment_input = image.convert("RGB").crop(segment_bbox)
    local_edit_bbox = _offset_bbox(local_bbox, segment_bbox)
    mask_result = build_text_pixel_gpt_mask(segment_input, local_edit_bbox, expand_px=rect_mask_expand_px)
    mask = mask_result.gpt_mask
    segment_input.save(input_path)
    mask.save(mask_path)
    _mask_overlay(segment_input, mask).save(overlay_path)
    prompt = _segmented_gpt_image_edit_prompt(target_text)
    gpt = _gpt_payload(run_dir, safe_id, input_path, mask_path, segment_input.size, prompt, config, client)
    return {
        "index": index,
        "target_text": target_text,
        "page_bbox": list(page_bbox),
        "context_segment_bbox": list(segment_bbox),
        "local_edit_bbox": list(local_edit_bbox),
        "paste_bbox": list(local_edit_bbox),
        "input_path": str(input_path),
        "mask_path": str(mask_path),
        "mask_overlay_path": str(overlay_path),
        "mask_strategy": mask_result.strategy,
        "editable_pixel_count": mask_result.editable_pixel_count,
        "gpt_image2": gpt,
    }


def _gpt_payload(
    run_dir: Path,
    safe_id: str,
    input_path: Path,
    mask_path: Path,
    size: tuple[int, int],
    prompt: str,
    config: GptImageConfig | None,
    client: GptImageEditClient | None,
) -> dict:
    summary = gpt_image_request_summary(config, input_path, mask_path, prompt)
    summary["mode"] = "segmented_masked_chinese_replacement"
    summary["target_text"] = prompt.split("Target Chinese text: ", 1)[-1] if "Target Chinese text: " in prompt else None
    if client is None:
        return {"status": "dry_run", "request": summary, "failure_reason": None}
    try:
        output_path = run_dir / "segmented_gpt_output" / f"{safe_id}.png"
        response = client.edit_image(input_path, mask_path, prompt, output_path)
        normalized = normalize_gpt_output_to_crop(
            response["output_path"],
            size,
            run_dir / "segmented_gpt_normalized" / f"{safe_id}.png",
        )
        return {"request": summary, **response, **normalized}
    except Exception as exc:
        return {"status": "failed", "request": summary, "failure_reason": f"{type(exc).__name__}:{str(exc)[:500]}"}


def _segmented_gpt_image_edit_prompt(translated_text: str) -> str:
    lines = gpt_image_edit_prompt(translated_text).splitlines()
    target_line = lines[-1]
    return "\n".join(
        [
            *lines[:-1],
            "For each segment, match the local original segment's lettering style, color, shadow, and stroke behavior.",
            "If the original segment is white or pale text on a colored banner, render white or very pale letters with the same soft shadow/highlight.",
            "Do not add a black outline, black stroke, bold comic border, or bubble-style edge unless the original local segment already has it.",
            "Keep segment scale and spacing consistent with adjacent original banner text; do not enlarge digits or glyphs to touch the crop edges.",
            target_line,
        ]
    )


def _compose_segments(run_dir: Path, record_id: str, context_path: Path, segments: list[dict]) -> Path:
    output = run_dir / "segmented_gpt_composed" / f"{_safe_name(record_id)}.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(context_path) as image:
        canvas = image.convert("RGB").copy()
    for segment in segments:
        normalized = segment["gpt_image2"].get("normalized_output_path")
        if not normalized:
            continue
        with Image.open(normalized) as edited:
            patch = edited.convert("RGB")
        segment_x1, segment_y1, _, _ = segment["context_segment_bbox"]
        paste_bbox = tuple(segment.get("paste_bbox") or segment["local_edit_bbox"])
        paste_patch = patch.crop(paste_bbox)
        canvas.paste(paste_patch, (segment_x1 + paste_bbox[0], segment_y1 + paste_bbox[1]))
    canvas.save(output)
    return output


def _crop_target(image_path: Path, bbox: tuple[int, int, int, int], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(image_path) as image:
        image.convert("RGB").crop(bbox).save(output_path)
    return output_path


def _write_grid(output_path: Path, rows: list[dict]) -> Path:
    tiles: list[tuple[str, Path]] = []
    for row in rows:
        record_id = row["record_id"]
        tiles.append((f"{record_id}\noriginal", Path(row["context"]["input_path"])))
        for segment in row["segments"]:
            tiles.append((f"seg {segment['index']}\n{segment['target_text']}", Path(segment["mask_overlay_path"])))
            normalized = segment["gpt_image2"].get("normalized_output_path")
            if normalized:
                tiles.append((f"seg {segment['index']} out", Path(normalized)))
        target = row["segmented_gpt_replace"].get("target_crop_path")
        if target:
            tiles.append((f"{record_id}\ncomposed target", Path(target)))
    return _write_tile_grid(output_path, tiles)


def _write_tile_grid(output_path: Path, tiles: list[tuple[str, Path]]) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    loaded = [(label, Image.open(path).convert("RGB")) for label, path in tiles if path.exists()]
    if not loaded:
        Image.new("RGB", (320, 180), "white").save(output_path)
        return output_path
    columns = near_square_columns(len(loaded), cell_width=310, cell_height=344)
    rows = (len(loaded) + columns - 1) // columns
    tile_w, tile_h, label_h, pad = 300, 300, 34, 10
    canvas = Image.new("RGB", (pad + columns * (tile_w + pad), pad + rows * (tile_h + label_h + pad)), "white")
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default()
    for index, (label, image) in enumerate(loaded):
        col = index % columns
        row = index // columns
        x = pad + col * (tile_w + pad)
        y = pad + row * (tile_h + label_h + pad)
        draw.rectangle((x, y, x + tile_w, y + label_h), fill=(244, 244, 244), outline=(170, 170, 170))
        _draw_label(draw, (x + 4, y + 4), label, font)
        fitted = _fit_tile(image, (tile_w, tile_h))
        canvas.paste(fitted, (x, y + label_h))
    canvas.save(output_path)
    return output_path


def _write_mimo_evaluation(run_dir: Path, grid_path: Path, rows: list[dict], client: MimoVisionClient) -> dict:
    translations = [{"record_id": row["record_id"], "translated_text": row["translated_text"]} for row in rows]
    prompt = "\n".join(
        [
            "Evaluate this near-square segmented GPT manga replacement grid.",
            "Each segment output should replace only its short target text area with the exact Simplified Chinese segment shown in the tile label.",
            "The composed target tile should read as the full Chinese translation in natural vertical manga layout.",
            "Reject if Japanese text remains, segment text is wrong, Chinese glyphs are wrong, or segment seams are visually unacceptable.",
            "Reject if a segment changes the original style family, adds an unjustified black outline/stroke, loses white-on-colored-banner styling, or uses inconsistent scale/spacing.",
            "Style mismatch is unacceptable even when the Chinese text itself is correct.",
            f"Expected records JSON: {json.dumps(translations, ensure_ascii=False)}",
            "Return only JSON with keys: segmented_gpt_scores, unacceptable_methods, per_record_notes, best_overall_for_user_choice, reasoning_summary, caveats.",
        ]
    )
    response = client.analyze_image(grid_path, prompt, kind="phase6_segmented_gpt_replace_grid", max_completion_tokens=1600)
    output = run_dir / "reports" / "mimo-segmented-gpt-replace-evaluation.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(response, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"path": str(output), "status": response.get("response", {}).get("status"), "quality": _mimo_quality_payload(response)}


def _mimo_quality_payload(response: dict) -> dict:
    try:
        payload = json.loads(_strip_json_wrapper(response.get("raw_text", "")))
    except Exception as exc:
        return {"segmented_gpt_status": "unknown", "failure_reason": f"invalid_mimo_quality_json:{type(exc).__name__}"}
    unacceptable = [str(item) for item in payload.get("unacceptable_methods", []) if str(item).strip()]
    return {
        "segmented_gpt_status": "unacceptable" if unacceptable else "acceptable",
        "unacceptable_methods": unacceptable,
        "segmented_gpt_scores": payload.get("segmented_gpt_scores"),
        "best_overall_for_user_choice": payload.get("best_overall_for_user_choice"),
        "reasoning_summary": payload.get("reasoning_summary"),
        "caveats": payload.get("caveats"),
        "failure_reason": None,
    }


def _write_manifest(output_path: Path, detection_run_dir: str | Path, rows: list[dict], grid: Path, mimo: dict | None) -> None:
    quality = (mimo or {}).get("quality") or {}
    gpt_ok = sum(1 for row in rows if row["segmented_gpt_replace"]["status"] == "ok")
    failed = gpt_ok if quality.get("segmented_gpt_status") == "unacceptable" else 0
    payload = {
        "schema_version": SEGMENTED_GPT_SCHEMA_VERSION,
        "detection_run_dir": str(detection_run_dir),
        "record_count": len(rows),
        "gpt_ok_count": gpt_ok,
        "gpt_quality_checked_count": gpt_ok if quality.get("segmented_gpt_status") in {"acceptable", "unacceptable"} else 0,
        "gpt_quality_failed_count": failed,
        "grid_path": str(grid),
        "mimo": mimo,
    }
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_report(output_path: Path, detection_run_dir: str | Path, rows: list[dict], grid: Path, mimo: dict | None) -> None:
    quality = (mimo or {}).get("quality") or {}
    lines = [
        "# Phase 6 Segmented GPT Replacement Experiment",
        "",
        f"Detection run directory: `{detection_run_dir}`",
        "",
        "## Summary",
        "",
        f"- Records processed: {len(rows)}",
        f"- Segmented GPT status: `{quality.get('segmented_gpt_status', 'not_evaluated')}`",
        f"- Grid: `{grid}`",
    ]
    if mimo:
        lines.append(f"- MIMO evaluation: `{mimo['path']}`")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _transparent_rect_mask(size: tuple[int, int], bbox: tuple[int, int, int, int]) -> Image.Image:
    mask = Image.new("RGBA", size, (0, 0, 0, 255))
    alpha = Image.new("L", size, 255)
    ImageDraw.Draw(alpha).rectangle(bbox, fill=0)
    return Image.merge("RGBA", [Image.new("L", size, 0)] * 3 + [alpha])


def _mask_overlay(image: Image.Image, mask: Image.Image) -> Image.Image:
    red = Image.new("RGB", image.size, (255, 60, 60))
    editable = ImageChops.invert(mask.getchannel("A"))
    return Image.composite(red, image.convert("RGB"), editable.point(lambda value: min(120, value))).convert("RGB")


def _expand_bbox(bbox: tuple[int, int, int, int], image_size: tuple[int, int], padding: int) -> tuple[int, int, int, int]:
    width, height = image_size
    return (
        max(0, bbox[0] - padding),
        max(0, bbox[1] - padding),
        min(width, bbox[2] + padding),
        min(height, bbox[3] + padding),
    )


def _offset_bbox(bbox: tuple[int, int, int, int], outer: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    return bbox[0] - outer[0], bbox[1] - outer[1], bbox[2] - outer[0], bbox[3] - outer[1]


def _fit_tile(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    tile_w, tile_h = size
    copy = ImageOps.contain(image.convert("RGB"), (tile_w, tile_h), method=Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", size, "white")
    canvas.paste(copy, ((tile_w - copy.width) // 2, (tile_h - copy.height) // 2))
    return canvas


def _draw_label(draw: ImageDraw.ImageDraw, xy: tuple[int, int], label: str, font: ImageFont.ImageFont) -> None:
    x, y = xy
    for line in label.splitlines()[:2]:
        draw.text((x, y), line[:42], fill="black", font=font)
        y += 13


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


def _safe_name(value: str) -> str:
    return "".join(char if char.isalnum() else "-" for char in value).strip("-") or "record"
