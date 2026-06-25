from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageOps

from .experiment_grid import near_square_columns


def write_replacement_quality_sheet(run_dir: Path, cleanup_run_dir: Path, row: dict, path_roots: list[Path] | None = None) -> str:
    output = run_dir / "debug" / "replacement_quality_sheets" / f"{safe_name(str(row.get('record_id')))}.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    tiles = _replacement_review_tiles(run_dir, cleanup_run_dir, row, path_roots or [])
    _write_tile_sheet(output, tiles, row)
    return str(output)


def resolve_existing_path(value: object, base_dir: Path, path_roots: list[Path] | None = None) -> Path | None:
    if not value:
        return None
    path = Path(str(value))
    candidates = [path]
    if not path.is_absolute():
        candidates.append(base_dir / path)
        candidates.append(Path.cwd() / path)
        candidates.extend(root / path for root in path_roots or [])
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def safe_name(value: str) -> str:
    return "".join(char if char.isalnum() else "-" for char in value).strip("-") or "record"


def _replacement_review_tiles(
    run_dir: Path,
    cleanup_run_dir: Path,
    row: dict,
    path_roots: list[Path],
) -> list[tuple[str, Path]]:
    cleanup = row.get("cleanup") or {}
    gpt = row.get("gpt_image2_edit") or {}
    edit_context = gpt.get("edit_context") or {}
    candidates = [
        ("original context", cleanup.get("cleaned_crop_path")),
        ("locator validation", (row.get("fallback_locator_validation") or {}).get("validation_image_path")),
        ("gpt edit input", edit_context.get("input_path")),
        ("gpt normalized output", gpt.get("normalized_output_path") or gpt.get("output_path")),
        ("final replacement", cleanup.get("replacement_crop_path")),
    ]
    tiles: list[tuple[str, Path]] = []
    for label, value in candidates:
        path = resolve_existing_path(value, cleanup_run_dir, path_roots)
        if path:
            tiles.append((label, path))
    overlay = _write_mask_overlay_tile(run_dir, cleanup_run_dir, row, path_roots)
    if overlay:
        tiles.insert(min(3, len(tiles)), ("mask overlay", overlay))
    target_crop = _write_final_target_crop(run_dir, cleanup_run_dir, row, path_roots)
    if target_crop:
        tiles.append(("final target crop", target_crop))
    return tiles


def _write_mask_overlay_tile(run_dir: Path, cleanup_run_dir: Path, row: dict, path_roots: list[Path]) -> Path | None:
    gpt = row.get("gpt_image2_edit") or {}
    edit_context = gpt.get("edit_context") or {}
    input_path = resolve_existing_path(edit_context.get("input_path"), cleanup_run_dir, path_roots)
    mask_path = resolve_existing_path(edit_context.get("mask_path") or gpt.get("mask_path"), cleanup_run_dir, path_roots)
    if not input_path or not mask_path:
        return None
    output = run_dir / "debug" / "replacement_mask_overlays" / f"{safe_name(str(row.get('record_id')))}.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(input_path) as image, Image.open(mask_path) as mask:
        _mask_overlay(image.convert("RGB"), mask.convert("RGBA")).save(output)
    return output


def _write_final_target_crop(run_dir: Path, cleanup_run_dir: Path, row: dict, path_roots: list[Path]) -> Path | None:
    cleanup = row.get("cleanup") or {}
    replacement_path = resolve_existing_path(cleanup.get("replacement_crop_path"), cleanup_run_dir, path_roots)
    local_bbox = _local_target_bbox(cleanup)
    if not replacement_path or not local_bbox:
        return None
    output = run_dir / "debug" / "replacement_target_crops" / f"{safe_name(str(row.get('record_id')))}.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(replacement_path) as image:
        image.convert("RGB").crop(local_bbox).save(output)
    return output


def _local_target_bbox(cleanup: dict) -> tuple[int, int, int, int] | None:
    mask_bbox = _bbox(cleanup.get("mask_bbox") or cleanup.get("text_bbox"))
    outer_bbox = _bbox(cleanup.get("bbox"))
    if not mask_bbox or not outer_bbox:
        return None
    return (
        max(0, mask_bbox[0] - outer_bbox[0]),
        max(0, mask_bbox[1] - outer_bbox[1]),
        max(0, mask_bbox[2] - outer_bbox[0]),
        max(0, mask_bbox[3] - outer_bbox[1]),
    )


def _bbox(value: object) -> tuple[int, int, int, int] | None:
    if not isinstance(value, list) or len(value) != 4:
        return None
    try:
        return tuple(int(item) for item in value)
    except (TypeError, ValueError):
        return None


def _write_tile_sheet(output_path: Path, tiles: list[tuple[str, Path]], row: dict) -> Path:
    if not tiles:
        Image.new("RGB", (360, 220), "white").save(output_path)
        return output_path
    loaded = [(label, Image.open(path).convert("RGB")) for label, path in tiles if path.exists()]
    tile_w, tile_h, label_h, pad = 260, 260, 42, 10
    header_h = 70
    columns = near_square_columns(len(loaded), cell_width=tile_w + pad, cell_height=tile_h + label_h + pad)
    rows = (len(loaded) + columns - 1) // columns
    width = pad + columns * (tile_w + pad)
    height = header_h + pad + rows * (tile_h + label_h + pad)
    sheet = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(sheet)
    font = _font(13)
    small = _font(11)
    _draw_header(draw, width, row, font, small)
    for index, (label, image) in enumerate(loaded):
        _draw_tile(sheet, draw, index, columns, (tile_w, tile_h, label_h, pad), label, image, row, font)
    sheet.save(output_path)
    return output_path


def _draw_tile(
    sheet: Image.Image,
    draw: ImageDraw.ImageDraw,
    index: int,
    columns: int,
    dims: tuple[int, int, int, int],
    label: str,
    image: Image.Image,
    row: dict,
    font: ImageFont.ImageFont,
) -> None:
    tile_w, tile_h, label_h, pad = dims
    col = index % columns
    row_index = index // columns
    x = pad + col * (tile_w + pad)
    y = 70 + pad + row_index * (tile_h + label_h + pad)
    draw.rectangle((x, y, x + tile_w, y + label_h), fill=(244, 244, 244), outline=(170, 170, 170))
    _draw_label(draw, (x + 4, y + 4), label, font, row.get("record_id"))
    fitted = _fit_tile(image, (tile_w, tile_h))
    draw.rectangle((x, y + label_h, x + tile_w, y + label_h + tile_h), fill="white", outline=(210, 210, 210))
    sheet.paste(fitted, (x + (tile_w - fitted.width) // 2, y + label_h + (tile_h - fitted.height) // 2))


def _draw_header(
    draw: ImageDraw.ImageDraw,
    width: int,
    row: dict,
    font: ImageFont.ImageFont,
    small: ImageFont.ImageFont,
) -> None:
    draw.rectangle((0, 0, width, 62), fill=(248, 246, 240), outline=(185, 180, 170))
    draw.text((12, 8), "MIMO REVIEW SHEET: gpt-image-2 direct Chinese replacement.", fill=(110, 70, 0), font=font)
    label = f"record={row.get('record_id')} target={row.get('translated_text', '')}"
    draw.text((12, 32), label[:120], fill=(30, 30, 30), font=small)


def _draw_label(draw: ImageDraw.ImageDraw, xy: tuple[int, int], label: str, font: ImageFont.ImageFont, record_id: object) -> None:
    x, y = xy
    draw.text((x, y), str(record_id)[:38], fill="black", font=font)
    draw.text((x, y + 18), label[:42], fill=(45, 45, 45), font=font)


def _mask_overlay(image: Image.Image, mask: Image.Image) -> Image.Image:
    red = Image.new("RGB", image.size, (255, 60, 60))
    editable = ImageChops.invert(mask.getchannel("A"))
    return Image.composite(red, image.convert("RGB"), editable.point(lambda value: min(130, value))).convert("RGB")


def _fit_tile(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    return ImageOps.contain(image.convert("RGB"), size, method=Image.Resampling.LANCZOS)


def _font(size: int) -> ImageFont.ImageFont:
    for path in _cjk_font_candidates():
        if path.exists():
            try:
                return ImageFont.truetype(str(path), size)
            except OSError:
                continue
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size)
    except OSError:
        return ImageFont.load_default()


def _cjk_font_candidates() -> list[Path]:
    return [
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/MSGothic_WenQuanYi_cnjp.ttf"),
        Path("C:/Windows/Fonts/simsun.ttc"),
        Path("C:/Windows/Fonts/meiryo.ttc"),
        Path("C:/Windows/Fonts/msgothic.ttc"),
    ]
