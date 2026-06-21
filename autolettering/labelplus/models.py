from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class LabelPlusRecord:
    image_name: str
    page_index: int
    record_index: int
    x_ratio: float
    y_ratio: float
    group_id: int
    group_name: str
    translated_text: str

    @property
    def record_id(self) -> str:
        return f"{self.image_name}#{self.record_index}"


@dataclass(frozen=True)
class LabelPlusPage:
    image_name: str
    page_index: int
    records: list[LabelPlusRecord] = field(default_factory=list)


@dataclass(frozen=True)
class LabelPlusDocument:
    source_name: str
    version: tuple[int, int]
    groups: list[str]
    comment: str
    pages: list[LabelPlusPage]


@dataclass(frozen=True)
class ManifestLabel:
    id: str
    page_index: int
    record_index: int
    x_ratio: float
    y_ratio: float
    x_px: int
    y_px: int
    group_id: int
    group_name: str
    translated_text: str


@dataclass(frozen=True)
class ManifestImage:
    image_name: str
    image_path: Path
    width: int
    height: int
    labels: list[ManifestLabel]


@dataclass(frozen=True)
class MissingImage:
    image_name: str
    page_index: int
    label_count: int
    reason: str


@dataclass(frozen=True)
class ProjectManifest:
    project_root: Path
    labelplus_file: Path
    version: tuple[int, int]
    groups: list[str]
    images: list[ManifestImage]
    missing_images: list[MissingImage]

