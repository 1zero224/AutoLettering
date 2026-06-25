from __future__ import annotations

import json
from pathlib import Path
import re

from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageOps

from .experiment_grid import near_square_columns
from .models.gpt_image import (
    GptImageConfig,
    GptImageEditClient,
    gpt_image_edit_prompt,
    gpt_image_request_summary,
    normalize_gpt_output_to_crop,
)


CLEANUP_ESCALATION_GPT_SCHEMA_VERSION = "autolettering.phase6.cleanup_escalation_gpt_replace.v1"


def run_phase6_cleanup_escalation_gpt_replace(
    gate_run_dir: str | Path,
    output_root: str | Path = "outputs/runs",
    run_id: str | None = None,
    sample_limit: int = 5,
    record_ids: list[str] | None = None,
    gpt_config: GptImageConfig | None = None,
    call_gpt_image: bool = False,
    context_padding: int = 16,
    rect_mask_expand_px: int = 2,
    max_segment_chars: int = 8,
    max_segment_height: int = 640,
    single_segment: bool = False,
    path_roots: list[str | Path] | None = None,
) -> Path:
    gate_run = Path(gate_run_dir)
    run_dir = Path(output_root) / (run_id or "phase6-cleanup-escalation-gpt-replace")
    run_dir.mkdir(parents=True, exist_ok=True)
    roots = [Path(root) for root in path_roots or []]
    cleanup_run = _cleanup_run_dir(gate_run, roots)
    cleanup_rows = _rows_by_record(cleanup_run / "cleanup-results.jsonl")
    candidates = _load_candidates(gate_run / "cleanup-escalation-candidates.jsonl", sample_limit, record_ids)
    client = GptImageEditClient(gpt_config) if call_gpt_image and gpt_config else None
    rows = [
        _process_one(
            run_dir,
            candidate,
            cleanup_rows.get(str(candidate.get("record_id"))),
            cleanup_run,
            roots,
            gpt_config,
            client,
            context_padding,
            rect_mask_expand_px,
            max_segment_chars,
            max_segment_height,
            single_segment,
        )
        for candidate in candidates
    ]
    cleanup_output_rows = [_cleanup_output_row(row) for row in rows]
    _write_jsonl(run_dir / "cleanup-escalation-gpt-results.jsonl", rows)
    _write_jsonl(run_dir / "cleanup-results.jsonl", cleanup_output_rows)
    grid = _write_grid(run_dir / "visuals" / "cleanup-escalation-gpt-grid.png", rows)
    _write_manifest(run_dir / "manifest.json", gate_run, cleanup_run, rows, grid)
    _write_report(run_dir / "reports" / "phase6-cleanup-escalation-gpt-report.md", gate_run, cleanup_run, rows, grid)
    return run_dir


def _process_one(
    run_dir: Path,
    candidate: dict,
    cleanup_row: dict | None,
    cleanup_run: Path,
    path_roots: list[Path],
    config: GptImageConfig | None,
    client: GptImageEditClient | None,
    context_padding: int,
    rect_mask_expand_px: int,
    max_segment_chars: int,
    max_segment_height: int,
    single_segment: bool,
) -> dict:
    if cleanup_row is None:
        return _failed_row(candidate, "cleanup_row_not_found")
    cleanup = cleanup_row.get("cleanup") or {}
    input_crop_path = _resolve_path(cleanup.get("input_crop_path"), cleanup_run, path_roots)
    text_mask_path = _resolve_path(cleanup.get("text_mask_path") or cleanup.get("source_mask_path"), cleanup_run, path_roots)
    if input_crop_path is None:
        return _failed_row(candidate, "input_crop_path_not_found", cleanup_row)
    if text_mask_path is None:
        return _failed_row(candidate, "text_mask_path_not_found", cleanup_row)
    target_text = _target_text(candidate, cleanup_row)
    text_segments = [target_text] if single_segment else _text_segments(target_text, max_segment_chars)
    context = _context_package(
        run_dir,
        candidate,
        cleanup_row,
        input_crop_path,
        text_mask_path,
        context_padding,
    )
    bbox_segments = _bbox_segments(context["local_target_bbox"], len(text_segments), max_segment_height)
    segments = [
        _run_segment(
            run_dir,
            candidate,
            index,
            text,
            context,
            local_bbox,
            rect_mask_expand_px,
            config,
            client,
        )
        for index, (text, local_bbox) in enumerate(zip(text_segments, bbox_segments), start=1)
    ]
    status = _replacement_status(segments)
    composed = _compose_segments(run_dir, str(candidate["record_id"]), context["input_path"], segments)
    target_crop = _crop_target(
        composed,
        context["local_target_bbox"],
        run_dir / "cleanup_escalation_target_crop" / f"{_safe_name(str(candidate['record_id']))}.png",
    )
    return {
        "schema_version": CLEANUP_ESCALATION_GPT_SCHEMA_VERSION,
        "record_id": candidate.get("record_id"),
        "image_name": candidate.get("image_name") or cleanup_row.get("image_name"),
        "translated_text": target_text,
        "status": "processed" if status in {"ok", "dry_run"} else "failed",
        "reason_codes": candidate.get("reason_codes") or [],
        "quality": candidate.get("quality") or {},
        "bbox": cleanup.get("bbox") or (candidate.get("cleanup") or {}).get("bbox"),
        "context": _stringify_paths(context),
        "segments": segments,
        "source_cleanup": cleanup,
        "segmented_gpt_replace": {
            "status": status,
            "segment_count": len(segments),
            "composed_context_path": str(composed),
            "target_crop_path": str(target_crop) if status == "ok" else None,
            "method": "segmented_gpt_image2_masked_edit",
        },
    }


def _cleanup_output_row(row: dict) -> dict:
    replacement = row.get("segmented_gpt_replace") or {}
    ok = replacement.get("status") == "ok" and bool(replacement.get("target_crop_path"))
    source_cleanup = row.get("source_cleanup") or {}
    cleanup = {
        "method": "segmented_gpt_image2_masked_edit",
        "bbox": source_cleanup.get("bbox") or row.get("bbox"),
        "text_bbox": source_cleanup.get("bbox") or row.get("bbox"),
        "mask_bbox": source_cleanup.get("bbox") or row.get("bbox"),
        "layout_text_bbox": source_cleanup.get("bbox") or row.get("bbox"),
        "cleaned_crop_path": source_cleanup.get("input_crop_path") or source_cleanup.get("cleaned_crop_path"),
        "before_after_path": source_cleanup.get("before_after_path") or source_cleanup.get("input_crop_path"),
        "text_overlay_required": not ok,
        "source_cleanup_method": source_cleanup.get("method"),
        "source_cleanup_route": source_cleanup.get("route"),
        "source_mask_path": source_cleanup.get("source_mask_path") or source_cleanup.get("text_mask_path"),
    }
    if ok:
        cleanup["replacement_method"] = "gpt_image2_masked_edit"
        cleanup["replacement_crop_path"] = replacement["target_crop_path"]
    else:
        cleanup["failure_reason"] = _replacement_failure_reason(row)
    return {
        "record_id": row.get("record_id"),
        "image_name": row.get("image_name"),
        "translated_text": row.get("translated_text"),
        "status": "cleaned" if ok else "failed",
        "cleanup": cleanup,
        "gpt_image2_edit": _gpt_image2_edit_payload(row),
        "cleanup_escalation_gpt_replace": replacement,
    }


def _gpt_image2_edit_payload(row: dict) -> dict:
    segments = row.get("segments") or []
    statuses = [((segment.get("gpt_image2") or {}).get("status")) for segment in segments]
    if statuses and all(status == "ok" for status in statuses):
        status = "ok"
    elif statuses and all(status == "dry_run" for status in statuses):
        status = "dry_run"
    else:
        status = "failed"
    context = row.get("context") or {}
    first_gpt = (segments[0].get("gpt_image2") if segments else {}) or {}
    return {
        "status": status,
        "request": first_gpt.get("request") or {},
        "edit_context": {
            "input_path": context.get("input_path"),
            "mask_path": context.get("mask_overlay_path"),
            "local_context_bbox": context.get("context_bbox"),
            "size": context.get("size"),
        },
        "segments": [
            {
                "index": segment.get("index"),
                "target_text": segment.get("target_text"),
                "input_path": segment.get("input_path"),
                "mask_path": segment.get("mask_path"),
                "status": (segment.get("gpt_image2") or {}).get("status"),
            }
            for segment in segments
        ],
        "normalized_output_path": (row.get("segmented_gpt_replace") or {}).get("composed_context_path"),
        "failure_reason": _replacement_failure_reason(row) if status != "ok" else None,
    }


def _context_package(
    run_dir: Path,
    candidate: dict,
    cleanup_row: dict,
    input_crop_path: Path,
    text_mask_path: Path,
    padding: int,
) -> dict:
    safe_id = _safe_name(str(candidate["record_id"]))
    with Image.open(input_crop_path) as image:
        crop = image.convert("RGB")
    with Image.open(text_mask_path) as mask_image:
        text_mask = mask_image.convert("L")
    target_bbox = _mask_bbox(text_mask) or (0, 0, crop.width, crop.height)
    context_bbox = _expand_bbox(target_bbox, crop.size, padding)
    context_crop = crop.crop(context_bbox)
    context_mask = text_mask.crop(context_bbox)
    local_target = _offset_bbox(target_bbox, context_bbox)
    input_path = run_dir / "cleanup_escalation_input" / f"{safe_id}.png"
    text_mask_out = run_dir / "cleanup_escalation_text_mask" / f"{safe_id}.png"
    mask_overlay_path = run_dir / "cleanup_escalation_mask_overlay" / f"{safe_id}.png"
    input_path.parent.mkdir(parents=True, exist_ok=True)
    text_mask_out.parent.mkdir(parents=True, exist_ok=True)
    mask_overlay_path.parent.mkdir(parents=True, exist_ok=True)
    context_crop.save(input_path)
    context_mask.save(text_mask_out)
    _mask_overlay(context_crop, _gpt_mask_from_text_mask(context_mask)).save(mask_overlay_path)
    return {
        "input_path": input_path,
        "text_mask_path": text_mask_out,
        "mask_overlay_path": mask_overlay_path,
        "context_bbox": context_bbox,
        "local_target_bbox": local_target,
        "size": context_crop.size,
        "source_input_crop_path": str(input_crop_path),
        "source_text_mask_path": str(text_mask_path),
        "source_record_id": cleanup_row.get("record_id"),
    }


def _run_segment(
    run_dir: Path,
    candidate: dict,
    index: int,
    target_text: str,
    context: dict,
    local_bbox: tuple[int, int, int, int],
    rect_mask_expand_px: int,
    config: GptImageConfig | None,
    client: GptImageEditClient | None,
) -> dict:
    safe_id = _safe_name(f"{candidate['record_id']}-{index}")
    segment_bbox = _expand_bbox(local_bbox, context["size"], rect_mask_expand_px)
    input_path = run_dir / "cleanup_escalation_gpt_input" / f"{safe_id}.png"
    mask_path = run_dir / "cleanup_escalation_gpt_mask" / f"{safe_id}.png"
    overlay_path = run_dir / "cleanup_escalation_gpt_mask_overlay" / f"{safe_id}.png"
    input_path.parent.mkdir(parents=True, exist_ok=True)
    mask_path.parent.mkdir(parents=True, exist_ok=True)
    overlay_path.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(context["input_path"]) as image, Image.open(context["text_mask_path"]) as text_mask_image:
        segment_input = image.convert("RGB").crop(segment_bbox)
        text_mask = text_mask_image.convert("L").crop(segment_bbox)
    local_edit_bbox = _offset_bbox(local_bbox, segment_bbox)
    edit_source_bbox = _estimated_text_bbox(segment_input, text_mask, local_edit_bbox)
    edit_bbox = _expand_bbox(edit_source_bbox, segment_input.size, max(rect_mask_expand_px, 8))
    gpt_mask = _gpt_mask_from_text_mask(_rect_mask(segment_input.size, edit_bbox))
    segment_input.save(input_path)
    gpt_mask.save(mask_path)
    _mask_overlay(segment_input, gpt_mask).save(overlay_path)
    prompt = _cleanup_escalation_prompt(target_text)
    gpt = _gpt_payload(run_dir, safe_id, input_path, mask_path, segment_input.size, prompt, config, client)
    return {
        "index": index,
        "target_text": target_text,
        "context_segment_bbox": list(segment_bbox),
        "local_edit_bbox": list(edit_bbox),
        "paste_bbox": list(edit_bbox),
        "input_path": str(input_path),
        "mask_path": str(mask_path),
        "mask_overlay_path": str(overlay_path),
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
    summary["mode"] = "cleanup_escalation_segmented_masked_chinese_replacement"
    summary["target_text"] = prompt.split("Target Chinese text: ", 1)[-1] if "Target Chinese text: " in prompt else None
    if client is None:
        return {"status": "dry_run", "request": summary, "failure_reason": None}
    try:
        output_path = run_dir / "cleanup_escalation_gpt_output" / f"{safe_id}.png"
        response = client.edit_image(input_path, mask_path, prompt, output_path)
        normalized = normalize_gpt_output_to_crop(
            response["output_path"],
            size,
            run_dir / "cleanup_escalation_gpt_normalized" / f"{safe_id}.png",
        )
        return {"request": summary, **response, **normalized}
    except Exception as exc:
        return {"status": "failed", "request": summary, "failure_reason": f"{type(exc).__name__}:{str(exc)[:500]}"}


def _cleanup_escalation_prompt(translated_text: str) -> str:
    marker = "Target Chinese text: "
    base_prompt = gpt_image_edit_prompt(translated_text)
    if marker not in base_prompt:
        return base_prompt
    prefix, target_text = base_prompt.split(marker, 1)
    return "\n".join(
        [
            prefix.rstrip(),
            "This is an escalation after local LaMA cleanup left visible original Japanese glyph residue.",
            "Use the transparent text mask as the only editable target; preserve the colored banner/background outside it.",
            "For each segment, match the local original segment's lettering style, color, shadow, and stroke behavior.",
            "If the original segment is white or pale text on a colored banner, render white or very pale letters with the same soft shadow/highlight.",
            "Do not add a black outline, black stroke, bold comic border, or bubble-style edge unless the original local segment already has it.",
            f"{marker}{target_text}",
        ]
    )


def _compose_segments(run_dir: Path, record_id: str, context_path: Path, segments: list[dict]) -> Path:
    output = run_dir / "cleanup_escalation_gpt_composed" / f"{_safe_name(record_id)}.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(context_path) as image:
        canvas = image.convert("RGB").copy()
    for segment in segments:
        normalized = (segment.get("gpt_image2") or {}).get("normalized_output_path")
        if not normalized:
            continue
        with Image.open(normalized) as edited:
            patch = edited.convert("RGB")
        segment_x1, segment_y1, _, _ = segment["context_segment_bbox"]
        paste_bbox = tuple(segment["paste_bbox"])
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
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tiles: list[tuple[str, Path]] = []
    for row in rows:
        record_id = str(row.get("record_id"))
        context = row.get("context") or {}
        _append_tile(tiles, f"{record_id}\nsource", context.get("input_path"))
        _append_tile(tiles, f"{record_id}\nmask", context.get("mask_overlay_path"))
        for segment in row.get("segments") or []:
            _append_tile(tiles, f"seg {segment['index']}\n{segment['target_text']}", segment.get("mask_overlay_path"))
            gpt = segment.get("gpt_image2") or {}
            _append_tile(tiles, f"seg {segment['index']} out", gpt.get("normalized_output_path") or gpt.get("output_path"))
        replacement = row.get("segmented_gpt_replace") or {}
        _append_tile(tiles, f"{record_id}\ncomposed target", replacement.get("target_crop_path"))
    return _write_tile_grid(output_path, tiles)


def _write_tile_grid(output_path: Path, tiles: list[tuple[str, Path]]) -> Path:
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
        fitted = ImageOps.contain(image, (tile_w, tile_h), method=Image.Resampling.LANCZOS)
        canvas.paste(fitted, (x + (tile_w - fitted.width) // 2, y + label_h + (tile_h - fitted.height) // 2))
    canvas.save(output_path)
    return output_path


def _write_manifest(output_path: Path, gate_run: Path, cleanup_run: Path, rows: list[dict], grid: Path) -> None:
    payload = {
        "schema_version": CLEANUP_ESCALATION_GPT_SCHEMA_VERSION,
        "gate_run_dir": str(gate_run),
        "cleanup_run_dir": str(cleanup_run),
        "candidate_count": len(rows),
        "replacement_cleanup_count": sum(1 for row in rows if (row.get("segmented_gpt_replace") or {}).get("status") == "ok"),
        "gpt_ok_count": sum(1 for row in rows if (row.get("segmented_gpt_replace") or {}).get("status") == "ok"),
        "gpt_dry_run_count": sum(1 for row in rows if (row.get("segmented_gpt_replace") or {}).get("status") == "dry_run"),
        "gpt_failed_count": sum(1 for row in rows if (row.get("segmented_gpt_replace") or {}).get("status") == "failed"),
        "grid_path": str(grid),
    }
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_report(output_path: Path, gate_run: Path, cleanup_run: Path, rows: list[dict], grid: Path) -> None:
    lines = [
        "# Phase 6 Cleanup Escalation GPT Replacement",
        "",
        f"Gate run directory: `{gate_run}`",
        f"Cleanup run directory: `{cleanup_run}`",
        "",
        "## Summary",
        "",
        f"- Candidates processed: {len(rows)}",
        f"- GPT replacements ok: {sum(1 for row in rows if (row.get('segmented_gpt_replace') or {}).get('status') == 'ok')}",
        f"- GPT dry runs: {sum(1 for row in rows if (row.get('segmented_gpt_replace') or {}).get('status') == 'dry_run')}",
        f"- GPT failures: {sum(1 for row in rows if (row.get('segmented_gpt_replace') or {}).get('status') == 'failed')}",
        f"- Grid: `{grid}`",
        "",
        "## Generated Artifacts",
        "",
        "- `cleanup-escalation-gpt-results.jsonl`",
        "- `cleanup-results.jsonl`",
        "- `cleanup_escalation_gpt_input/*.png`",
        "- `cleanup_escalation_gpt_mask/*.png`",
        "- `cleanup_escalation_gpt_composed/*.png`",
        "- `cleanup_escalation_target_crop/*.png`",
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _cleanup_run_dir(gate_run: Path, path_roots: list[Path]) -> Path:
    manifest_path = gate_run / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"cleanup_gate_manifest_not_found:{manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    cleanup_run = _resolve_path(manifest.get("cleanup_run_dir"), gate_run, path_roots)
    if cleanup_run is None:
        raise FileNotFoundError("cleanup_run_dir_not_found")
    return cleanup_run


def _load_candidates(path: Path, sample_limit: int, record_ids: list[str] | None) -> list[dict]:
    wanted = set(record_ids or [])
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if len(rows) >= sample_limit:
                break
            row = json.loads(line)
            if wanted and row.get("record_id") not in wanted:
                continue
            if row.get("status") == "candidate":
                rows.append(row)
    return rows


def _rows_by_record(path: Path) -> dict[str, dict]:
    rows: dict[str, dict] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            record_id = row.get("record_id")
            if record_id:
                rows[str(record_id)] = row
    return rows


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
    return max(candidates) if candidates else hard_limit


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


def _bbox_segments(
    local_target: tuple[int, int, int, int],
    segment_count: int,
    max_segment_height: int,
) -> list[tuple[int, int, int, int]]:
    del max_segment_height
    x1, y1, x2, y2 = local_target
    height = y2 - y1
    count = max(1, segment_count)
    return [
        (x1, round(y1 + height * index / count), x2, round(y1 + height * (index + 1) / count))
        for index in range(count)
    ]


def _mask_bbox(mask: Image.Image) -> tuple[int, int, int, int] | None:
    bbox = mask.convert("L").point(lambda value: 255 if value > 0 else 0).getbbox()
    if bbox is None:
        return None
    return tuple(int(value) for value in bbox)


def _estimated_text_bbox(
    image: Image.Image,
    cleanup_mask: Image.Image,
    fallback_bbox: tuple[int, int, int, int],
) -> tuple[int, int, int, int]:
    gray = image.convert("L")
    area = max(1, gray.width * gray.height)
    candidates: list[tuple[float, tuple[int, int, int, int]]] = []
    for thresholded in (
        gray.point(lambda value: 255 if value > 205 else 0, mode="L"),
        gray.point(lambda value: 255 if value < 55 else 0, mode="L"),
    ):
        bbox = _mask_bbox(thresholded)
        if bbox is None:
            continue
        coverage = thresholded.histogram()[255] / area
        if 0.002 <= coverage <= 0.45:
            candidates.append((coverage, bbox))
    if candidates:
        return max(candidates, key=lambda item: item[0])[1]
    return _mask_bbox(cleanup_mask) or fallback_bbox


def _gpt_mask_from_text_mask(text_mask: Image.Image) -> Image.Image:
    alpha = ImageChops.invert(text_mask.convert("L"))
    return Image.merge("RGBA", [Image.new("L", text_mask.size, 255)] * 3 + [alpha])


def _rect_mask(size: tuple[int, int], bbox: tuple[int, int, int, int]) -> Image.Image:
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rectangle(bbox, fill=255)
    return mask


def _mask_overlay(image: Image.Image, mask: Image.Image) -> Image.Image:
    red = Image.new("RGB", image.size, (255, 60, 60))
    editable = ImageChops.invert(mask.getchannel("A"))
    return Image.composite(red, image.convert("RGB"), editable.point(lambda value: min(130, value))).convert("RGB")


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


def _replacement_status(segments: list[dict]) -> str:
    statuses = [(segment.get("gpt_image2") or {}).get("status") for segment in segments]
    if statuses and all(status == "ok" for status in statuses):
        return "ok"
    if statuses and all(status == "dry_run" for status in statuses):
        return "dry_run"
    return "failed"


def _replacement_failure_reason(row: dict) -> str | None:
    replacement = row.get("segmented_gpt_replace") or {}
    if replacement.get("status") == "ok":
        return None
    failures = [
        (segment.get("gpt_image2") or {}).get("failure_reason") or (segment.get("gpt_image2") or {}).get("status")
        for segment in row.get("segments") or []
        if (segment.get("gpt_image2") or {}).get("status") != "ok"
    ]
    return ";".join(str(item) for item in failures if item) or replacement.get("status")


def _failed_row(candidate: dict, reason: str, cleanup_row: dict | None = None) -> dict:
    return {
        "schema_version": CLEANUP_ESCALATION_GPT_SCHEMA_VERSION,
        "record_id": candidate.get("record_id"),
        "image_name": candidate.get("image_name") or (cleanup_row or {}).get("image_name"),
        "translated_text": _target_text(candidate, cleanup_row or {}),
        "status": "failed",
        "reason_codes": candidate.get("reason_codes") or [],
        "failure_reason": reason,
        "source_cleanup": (cleanup_row or {}).get("cleanup") or {},
        "segments": [],
        "segmented_gpt_replace": {"status": "failed", "segment_count": 0, "failure_reason": reason},
    }


def _target_text(candidate: dict, cleanup_row: dict) -> str:
    contract = candidate.get("gpt_image2_contract") or {}
    return str(contract.get("target_text") or cleanup_row.get("translated_text") or "")


def _stringify_paths(payload: dict) -> dict:
    return {key: str(value) if isinstance(value, Path) else value for key, value in payload.items()}


def _resolve_path(value: object, base_dir: Path, path_roots: list[Path]) -> Path | None:
    if not value:
        return None
    path = Path(str(value))
    candidates = [path]
    if not path.is_absolute():
        candidates.append(base_dir / path)
        candidates.append(Path.cwd() / path)
        candidates.extend(root / path for root in path_roots)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _append_tile(tiles: list[tuple[str, Path]], label: str, path: str | Path | None) -> None:
    if path and Path(path).exists():
        tiles.append((label, Path(path)))


def _draw_label(draw: ImageDraw.ImageDraw, xy: tuple[int, int], label: str, font: ImageFont.ImageFont) -> None:
    x, y = xy
    for line in label.splitlines()[:2]:
        draw.text((x, y), line[:42], fill="black", font=font)
        y += 13


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _safe_name(value: str) -> str:
    return "".join(char if char.isalnum() else "-" for char in value).strip("-") or "record"
