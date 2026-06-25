from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageOps

from .experiment_grid import near_square_columns
from .models.gpt_image import GptImageConfig, GptImageEditClient, gpt_image_request_summary, normalize_gpt_output_to_crop


BACKGROUND_REPAIR_SCHEMA_VERSION = "autolettering.phase6.cleanup_escalation_gpt_background_repair.v1"


def run_phase6_cleanup_escalation_gpt_background_repair(
    gate_run_dir: str | Path,
    output_root: str | Path = "outputs/runs",
    run_id: str | None = None,
    sample_limit: int = 5,
    record_ids: list[str] | None = None,
    gpt_config: GptImageConfig | None = None,
    call_gpt_image: bool = False,
    mask_dilation_px: int = 6,
    path_roots: list[str | Path] | None = None,
) -> Path:
    gate_run = Path(gate_run_dir)
    run_dir = Path(output_root) / (run_id or "phase6-cleanup-escalation-gpt-background-repair")
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
            mask_dilation_px,
        )
        for candidate in candidates
    ]
    cleanup_output_rows = [_cleanup_output_row(row) for row in rows]
    _write_jsonl(run_dir / "cleanup-escalation-gpt-background-results.jsonl", rows)
    _write_jsonl(run_dir / "cleanup-results.jsonl", cleanup_output_rows)
    grid = _write_grid(run_dir / "visuals" / "cleanup-escalation-gpt-background-grid.png", rows)
    _write_manifest(run_dir / "manifest.json", gate_run, cleanup_run, rows, grid)
    _write_report(run_dir / "reports" / "phase6-cleanup-escalation-gpt-background-report.md", gate_run, cleanup_run, rows, grid)
    return run_dir


def _process_one(
    run_dir: Path,
    candidate: dict,
    cleanup_row: dict | None,
    cleanup_run: Path,
    path_roots: list[Path],
    config: GptImageConfig | None,
    client: GptImageEditClient | None,
    mask_dilation_px: int,
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
    package = _write_repair_package(run_dir, candidate, input_crop_path, text_mask_path, mask_dilation_px)
    prompt = _background_repair_prompt()
    gpt = _gpt_payload(run_dir, _safe_name(str(candidate["record_id"])), package, prompt, config, client)
    before_after = _write_before_after(run_dir, candidate, input_crop_path, gpt.get("normalized_output_path"))
    ok = gpt.get("status") == "ok" and bool(gpt.get("normalized_output_path"))
    return {
        "schema_version": BACKGROUND_REPAIR_SCHEMA_VERSION,
        "record_id": candidate.get("record_id"),
        "image_name": candidate.get("image_name") or cleanup_row.get("image_name"),
        "translated_text": _target_text(candidate, cleanup_row),
        "status": "processed" if ok else "failed",
        "reason_codes": candidate.get("reason_codes") or [],
        "quality": candidate.get("quality") or {},
        "bbox": cleanup.get("bbox") or (candidate.get("cleanup") or {}).get("bbox"),
        "source_cleanup": cleanup,
        "repair_input": _stringify_paths(package),
        "gpt_image2_background_repair": gpt,
        "before_after_path": str(before_after) if before_after else None,
    }


def _write_repair_package(
    run_dir: Path,
    candidate: dict,
    input_crop_path: Path,
    text_mask_path: Path,
    mask_dilation_px: int,
) -> dict:
    safe_id = _safe_name(str(candidate["record_id"]))
    with Image.open(input_crop_path) as image:
        input_crop = image.convert("RGB")
    with Image.open(text_mask_path) as mask_image:
        text_mask = mask_image.convert("L").resize(input_crop.size, Image.Resampling.NEAREST)
    edit_mask = _dilated_binary_mask(text_mask, mask_dilation_px)
    gpt_mask = _gpt_mask_from_edit_mask(edit_mask)
    input_path = run_dir / "background_repair_input" / f"{safe_id}.png"
    edit_mask_path = run_dir / "background_repair_edit_mask" / f"{safe_id}.png"
    gpt_mask_path = run_dir / "background_repair_gpt_mask" / f"{safe_id}.png"
    overlay_path = run_dir / "background_repair_mask_overlay" / f"{safe_id}.png"
    for path in (input_path, edit_mask_path, gpt_mask_path, overlay_path):
        path.parent.mkdir(parents=True, exist_ok=True)
    input_crop.save(input_path)
    edit_mask.save(edit_mask_path)
    gpt_mask.save(gpt_mask_path)
    _mask_overlay(input_crop, gpt_mask).save(overlay_path)
    return {
        "input_path": input_path,
        "edit_mask_path": edit_mask_path,
        "gpt_mask_path": gpt_mask_path,
        "mask_overlay_path": overlay_path,
        "source_input_crop_path": str(input_crop_path),
        "source_text_mask_path": str(text_mask_path),
        "size": input_crop.size,
        "mask_dilation_px": mask_dilation_px,
    }


def _gpt_payload(
    run_dir: Path,
    safe_id: str,
    package: dict,
    prompt: str,
    config: GptImageConfig | None,
    client: GptImageEditClient | None,
) -> dict:
    summary = gpt_image_request_summary(config, package["input_path"], package["gpt_mask_path"], prompt)
    summary["mode"] = "cleanup_escalation_background_repair_only"
    summary["target_size"] = list(package["size"])
    if client is None:
        return {"status": "dry_run", "request": summary, "failure_reason": None}
    try:
        output_path = run_dir / "background_repair_gpt_output" / f"{safe_id}.png"
        response = client.edit_image(package["input_path"], package["gpt_mask_path"], prompt, output_path)
        normalized = normalize_gpt_output_to_crop(
            response["output_path"],
            package["size"],
            run_dir / "background_repair_gpt_normalized" / f"{safe_id}.png",
        )
        return {"request": summary, **response, **normalized}
    except Exception as exc:
        return {"status": "failed", "request": summary, "failure_reason": f"{type(exc).__name__}:{str(exc)[:500]}"}


def _cleanup_output_row(row: dict) -> dict:
    repair = row.get("gpt_image2_background_repair") or {}
    source_cleanup = row.get("source_cleanup") or {}
    ok = repair.get("status") == "ok" and bool(repair.get("normalized_output_path"))
    cleanup = {
        "method": "gpt_image2_background_repair",
        "bbox": source_cleanup.get("bbox") or row.get("bbox"),
        "text_bbox": source_cleanup.get("text_bbox") or source_cleanup.get("bbox") or row.get("bbox"),
        "mask_bbox": source_cleanup.get("mask_bbox") or source_cleanup.get("bbox") or row.get("bbox"),
        "layout_text_bbox": source_cleanup.get("layout_text_bbox") or source_cleanup.get("bbox") or row.get("bbox"),
        "input_crop_path": (row.get("repair_input") or {}).get("input_path"),
        "text_mask_path": (row.get("repair_input") or {}).get("edit_mask_path"),
        "gpt_mask_path": (row.get("repair_input") or {}).get("gpt_mask_path"),
        "cleaned_crop_path": repair.get("normalized_output_path") or source_cleanup.get("cleaned_crop_path"),
        "before_after_path": row.get("before_after_path") or source_cleanup.get("before_after_path"),
        "text_overlay_required": True,
        "source_cleanup_method": source_cleanup.get("method"),
        "source_cleanup_route": source_cleanup.get("route"),
        "source_mask_path": source_cleanup.get("source_mask_path") or source_cleanup.get("text_mask_path"),
    }
    if not ok:
        cleanup["failure_reason"] = repair.get("failure_reason") or repair.get("status") or row.get("failure_reason")
    return {
        "record_id": row.get("record_id"),
        "image_name": row.get("image_name"),
        "translated_text": row.get("translated_text"),
        "status": "cleaned" if ok else "failed",
        "cleanup": cleanup,
        "gpt_image2_background_repair": repair,
        "gpt_image2_edit": {
            "status": repair.get("status"),
            "mode": "background_repair_only",
            "request": repair.get("request") or {},
            "normalized_output_path": repair.get("normalized_output_path"),
            "failure_reason": repair.get("failure_reason"),
        },
    }


def _background_repair_prompt() -> str:
    return "\n".join(
        [
            "Edit only the transparent masked manga text pixels.",
            "Remove all visible Japanese text, numerals, glyph strokes, shadows, and text residue from the editable area.",
            "Reconstruct only the original background: red banner texture, gradient, panel tone, edge shading, and nearby non-text artwork.",
            "Do not write, draw, render, or invent any Chinese, Japanese, English, digits, punctuation, symbols, captions, or lettering.",
            "Do not add boxes, blur patches, glow, stickers, or new design elements.",
            "Preserve every opaque unmasked area exactly, including borders and non-text art.",
            "The result must be a clean background image only; translated text will be rendered later by the program.",
        ]
    )


def _dilated_binary_mask(mask: Image.Image, dilation_px: int) -> Image.Image:
    binary = mask.convert("L").point(lambda value: 255 if value > 0 else 0, mode="L")
    radius = max(0, int(dilation_px))
    if radius <= 0:
        return binary
    kernel_size = radius * 2 + 1
    return binary.filter(ImageFilter.MaxFilter(kernel_size))


def _gpt_mask_from_edit_mask(edit_mask: Image.Image) -> Image.Image:
    alpha = ImageChops.invert(edit_mask.convert("L"))
    return Image.merge("RGBA", [Image.new("L", edit_mask.size, 255)] * 3 + [alpha])


def _mask_overlay(image: Image.Image, gpt_mask: Image.Image) -> Image.Image:
    red = Image.new("RGB", image.size, (255, 60, 60))
    editable = ImageChops.invert(gpt_mask.getchannel("A"))
    return Image.composite(red, image.convert("RGB"), editable.point(lambda value: min(130, value))).convert("RGB")


def _write_before_after(run_dir: Path, candidate: dict, before_path: Path, after_path: str | None) -> Path | None:
    if not after_path:
        return None
    output = run_dir / "background_repair_before_after" / f"{_safe_name(str(candidate['record_id']))}.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(before_path) as before_image, Image.open(after_path) as after_image:
        before = before_image.convert("RGB")
        after = after_image.convert("RGB").resize(before.size)
    canvas = Image.new("RGB", (before.width * 2, before.height), "white")
    canvas.paste(before, (0, 0))
    canvas.paste(after, (before.width, 0))
    canvas.save(output)
    return output


def _write_grid(output_path: Path, rows: list[dict]) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tiles: list[tuple[str, Path]] = []
    for row in rows:
        record_id = str(row.get("record_id"))
        repair_input = row.get("repair_input") or {}
        repair = row.get("gpt_image2_background_repair") or {}
        _append_tile(tiles, f"{record_id}\nsource", repair_input.get("input_path"))
        _append_tile(tiles, f"{record_id}\nmask", repair_input.get("mask_overlay_path"))
        _append_tile(tiles, f"{record_id}\nbackground", repair.get("normalized_output_path") or repair.get("output_path"))
        _append_tile(tiles, f"{record_id}\nbefore after", row.get("before_after_path"))
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
        "schema_version": BACKGROUND_REPAIR_SCHEMA_VERSION,
        "gate_run_dir": str(gate_run),
        "cleanup_run_dir": str(cleanup_run),
        "candidate_count": len(rows),
        "gpt_ok_count": sum(1 for row in rows if (row.get("gpt_image2_background_repair") or {}).get("status") == "ok"),
        "gpt_dry_run_count": sum(1 for row in rows if (row.get("gpt_image2_background_repair") or {}).get("status") == "dry_run"),
        "gpt_failed_count": sum(1 for row in rows if (row.get("gpt_image2_background_repair") or {}).get("status") == "failed"),
        "grid_path": str(grid),
    }
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_report(output_path: Path, gate_run: Path, cleanup_run: Path, rows: list[dict], grid: Path) -> None:
    lines = [
        "# Phase 6 Cleanup Escalation GPT Background Repair",
        "",
        f"Gate run directory: `{gate_run}`",
        f"Cleanup run directory: `{cleanup_run}`",
        "",
        "## Summary",
        "",
        f"- Candidates processed: {len(rows)}",
        f"- GPT background repairs ok: {sum(1 for row in rows if (row.get('gpt_image2_background_repair') or {}).get('status') == 'ok')}",
        f"- GPT dry runs: {sum(1 for row in rows if (row.get('gpt_image2_background_repair') or {}).get('status') == 'dry_run')}",
        f"- GPT failures: {sum(1 for row in rows if (row.get('gpt_image2_background_repair') or {}).get('status') == 'failed')}",
        f"- Grid: `{grid}`",
        "",
        "## Generated Artifacts",
        "",
        "- `cleanup-escalation-gpt-background-results.jsonl`",
        "- `cleanup-results.jsonl`",
        "- `background_repair_input/*.png`",
        "- `background_repair_gpt_mask/*.png`",
        "- `background_repair_gpt_normalized/*.png`",
        "- `background_repair_before_after/*.png`",
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


def _failed_row(candidate: dict, reason: str, cleanup_row: dict | None = None) -> dict:
    return {
        "schema_version": BACKGROUND_REPAIR_SCHEMA_VERSION,
        "record_id": candidate.get("record_id"),
        "image_name": candidate.get("image_name") or (cleanup_row or {}).get("image_name"),
        "translated_text": _target_text(candidate, cleanup_row or {}),
        "status": "failed",
        "reason_codes": candidate.get("reason_codes") or [],
        "failure_reason": reason,
        "source_cleanup": (cleanup_row or {}).get("cleanup") or {},
        "gpt_image2_background_repair": {"status": "failed", "failure_reason": reason},
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
