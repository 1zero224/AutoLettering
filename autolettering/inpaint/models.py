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
    before_after_path: Path
