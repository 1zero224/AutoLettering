from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter


SCHEMA_VERSION = "autolettering.mask_refinement.v1"


@dataclass(frozen=True)
class MaskRefinementOptions:
    dilate_px: int = 0
    erode_px: int = 0
    extend_left_px: int = 0
    extend_right_px: int = 0
    extend_up_px: int = 0
    extend_down_px: int = 0

    def enabled(self) -> bool:
        return any(value > 0 for value in self.operations().values())

    def operations(self) -> dict[str, int]:
        return {
            "dilate_px": max(0, int(self.dilate_px)),
            "erode_px": max(0, int(self.erode_px)),
            "extend_left_px": max(0, int(self.extend_left_px)),
            "extend_right_px": max(0, int(self.extend_right_px)),
            "extend_up_px": max(0, int(self.extend_up_px)),
            "extend_down_px": max(0, int(self.extend_down_px)),
        }


@dataclass(frozen=True)
class MaskRefinementArtifact:
    schema_version: str
    operations: dict[str, int]
    source_mask_path: Path
    refined_mask_path: Path
    mask_overlay_path: Path
    refined_cleaned_crop_path: Path
    before_after_path: Path
    input_mask_pixel_count: int
    output_mask_pixel_count: int


def refine_cleanup_artifacts(
    *,
    before_crop_path: str | Path,
    cleaned_crop_path: str | Path,
    source_mask_path: str | Path,
    fill_color: tuple[int, int, int],
    output_dir: str | Path,
    record_id: str,
    options: MaskRefinementOptions,
) -> MaskRefinementArtifact | None:
    if not options.enabled():
        return None
    with Image.open(before_crop_path) as before_image, Image.open(source_mask_path) as mask_image:
        before = before_image.convert("RGB")
        source_mask = mask_image.convert("L")
    refined_mask = refine_mask(source_mask, options)
    fill_layer = Image.new("RGB", before.size, fill_color)
    refined_cleaned = Image.composite(fill_layer, before, refined_mask)
    root = Path(output_dir)
    safe_id = _safe_name(record_id)
    refined_mask_path = root / "refined_mask" / f"{safe_id}.png"
    overlay_path = root / "refined_mask_overlay" / f"{safe_id}.png"
    cleaned_path = root / "refined_cleaned" / f"{safe_id}.png"
    before_after_path = root / "refined_before_after" / f"{safe_id}.png"
    _save(refined_mask, refined_mask_path)
    _save(mask_overlay(before, refined_mask), overlay_path)
    _save(refined_cleaned, cleaned_path)
    _save_before_after(before, refined_cleaned, before_after_path)
    return MaskRefinementArtifact(
        schema_version=SCHEMA_VERSION,
        operations=options.operations(),
        source_mask_path=Path(source_mask_path),
        refined_mask_path=refined_mask_path,
        mask_overlay_path=overlay_path,
        refined_cleaned_crop_path=cleaned_path,
        before_after_path=before_after_path,
        input_mask_pixel_count=_mask_pixel_count(source_mask),
        output_mask_pixel_count=_mask_pixel_count(refined_mask),
    )


def refine_mask(mask: Image.Image, options: MaskRefinementOptions) -> Image.Image:
    refined = mask.convert("L").point(lambda value: 255 if value > 0 else 0, mode="L")
    ops = options.operations()
    if ops["dilate_px"] > 0:
        refined = refined.filter(ImageFilter.MaxFilter(_filter_size(ops["dilate_px"])))
    if ops["erode_px"] > 0:
        refined = refined.filter(ImageFilter.MinFilter(_filter_size(ops["erode_px"])))
    return _extend_mask(refined, ops)


def mask_overlay(crop: Image.Image, mask: Image.Image) -> Image.Image:
    base = crop.convert("RGB")
    red = Image.new("RGB", base.size, (255, 60, 60))
    alpha = mask.convert("L").point(lambda value: min(120, value), mode="L")
    return Image.composite(red, base, alpha)


def _extend_mask(mask: Image.Image, ops: dict[str, int]) -> Image.Image:
    binary = np.array(mask.convert("L"), dtype=np.uint8) > 0
    if not bool(binary.any()):
        return mask.convert("L")
    result = binary.copy()
    height, width = result.shape
    for y, x in zip(*np.where(binary)):
        result[y, max(0, x - ops["extend_left_px"]) : min(width, x + ops["extend_right_px"] + 1)] = True
        result[max(0, y - ops["extend_up_px"]) : min(height, y + ops["extend_down_px"] + 1), x] = True
    return Image.fromarray(result.astype(np.uint8) * 255, mode="L")


def _filter_size(radius_px: int) -> int:
    return max(3, int(radius_px) * 2 + 1)


def _mask_pixel_count(mask: Image.Image) -> int:
    return int(np.array(mask.convert("L"), dtype=np.uint8).sum() // 255)


def _save(image: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def _save_before_after(before: Image.Image, after: Image.Image, path: Path) -> None:
    canvas = Image.new("RGB", (before.width + after.width, max(before.height, after.height)), "white")
    canvas.paste(before.convert("RGB"), (0, 0))
    canvas.paste(after.convert("RGB"), (before.width, 0))
    _save(canvas, path)


def _safe_name(value: str) -> str:
    return "".join(char if char.isalnum() else "-" for char in value).strip("-") or "record"
