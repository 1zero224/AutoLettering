from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class BubbleFillResult:
    record_id: str
    method: str
    bbox: tuple[int, int, int, int]
    fill_color: tuple[int, int, int]
    before_crop_path: Path
    cleaned_crop_path: Path
    cleanup_mask_path: Path | None
    before_after_path: Path


@dataclass(frozen=True)
class NonBubbleInpaintResult:
    record_id: str
    method: str
    bbox: tuple[int, int, int, int]
    input_crop_path: Path
    text_mask_path: Path
    gpt_mask_path: Path
    cleaned_crop_path: Path
    before_after_path: Path
    dark_pixel_count: int
