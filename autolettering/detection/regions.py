from __future__ import annotations


def build_search_region(
    x_px: int,
    y_px: int,
    width: int,
    height: int,
    radius_x: int,
    radius_y: int,
) -> tuple[int, int, int, int]:
    return (
        max(0, x_px - radius_x),
        max(0, y_px - radius_y),
        min(width, x_px + radius_x),
        min(height, y_px + radius_y),
    )
