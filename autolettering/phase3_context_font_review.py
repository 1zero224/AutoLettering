from __future__ import annotations

from pathlib import Path

from .experiment_grid import near_square_columns, write_grid
from .review_tiles import write_segmented_review_tile


def write_context_font_grid(run_dir: Path, comparison: dict, rendered: list[dict], source_crop: Path | None) -> Path:
    record_safe = _safe_name(str(comparison["record_id"]))
    tiles: list[tuple[str, str | Path]] = []
    if source_crop is not None:
        source_review = run_dir / "review_context_tiles" / record_safe / "SOURCE-original.png"
        write_segmented_review_tile(source_crop, source_review)
        tiles.append(("SOURCE original", source_review))
    for item in rendered:
        label = f"{item['font_id']} {_short_font_name(item)}"
        tiles.append((label, item.get("review_context_path") or item["context_crop_path"]))
    columns = near_square_columns(len(tiles), cell_width=380, cell_height=690)
    return write_grid(
        run_dir / "debug" / "context_font_grids" / f"{record_safe}.png",
        tiles,
        columns,
        tile_size=(360, 640),
    )


def _short_font_name(item: dict) -> str:
    return str(item.get("filename") or item.get("family_name") or "")[:36]


def _safe_name(value: str) -> str:
    return "".join(char if char.isalnum() else "-" for char in value).strip("-") or "record"
