from __future__ import annotations

from dataclasses import dataclass, field
import re
from pathlib import Path

from PIL import Image

from .models import (
    LabelPlusDocument,
    LabelPlusPage,
    LabelPlusRecord,
    ManifestImage,
    ManifestLabel,
    MissingImage,
    ProjectManifest,
)


_PAGE_RE = re.compile(r"^>{6,}\[(?P<name>.+)]<{6,}$")
_LABEL_RE = re.compile(
    r"^-{6,}\[(?P<index>\d+)]-{6,}\[(?P<x>[^,\]]+),(?P<y>[^,\]]+),(?P<group>\d+)]$"
)


def parse_labelplus_text(text: str, source_name: str = "<memory>") -> LabelPlusDocument:
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    version, groups, comment, body_start = _parse_header(lines, source_name)
    pages = _parse_pages(lines[body_start:], groups, source_name)

    return LabelPlusDocument(
        source_name=source_name,
        version=version,
        groups=groups,
        comment=comment,
        pages=pages,
    )


def parse_labelplus_project(labelplus_file: str | Path) -> ProjectManifest:
    labelplus_path = Path(labelplus_file).resolve()
    document = parse_labelplus_text(
        labelplus_path.read_text(encoding="utf-8-sig"),
        source_name=str(labelplus_path),
    )
    return _build_project_manifest(labelplus_path, document)


def _parse_pages(
    body_lines: list[str],
    groups: list[str],
    source_name: str,
) -> list[LabelPlusPage]:
    state = _PageParseState(groups=groups, source_name=source_name)

    for raw_line in body_lines:
        line = raw_line.strip()
        page_match = _PAGE_RE.match(line)
        if page_match:
            state.begin_page(page_match.group("name"))
            continue

        label_match = _LABEL_RE.match(line)
        if label_match:
            state.begin_label(_parse_label_match(label_match))
            continue

        state.add_text(raw_line)

    state.flush_page()
    return state.pages


@dataclass
class _PageParseState:
    groups: list[str]
    source_name: str
    pages: list[LabelPlusPage] = field(default_factory=list)
    current_image: str | None = None
    current_page_index: int = 0
    current_records: list[LabelPlusRecord] = field(default_factory=list)
    current_label: tuple[int, float, float, int] | None = None
    current_text: list[str] = field(default_factory=list)

    def begin_page(self, image_name: str) -> None:
        self.flush_page()
        self.current_page_index += 1
        self.current_image = image_name
        self.current_records = []
        self.current_label = None
        self.current_text = []

    def begin_label(self, label_values: tuple[int, float, float, int]) -> None:
        if self.current_image is None:
            raise ValueError(f"{self.source_name}: label appears before page header")
        self.flush_label()
        self.current_label = label_values
        self.current_text = []

    def add_text(self, raw_line: str) -> None:
        if self.current_label is not None:
            self.current_text.append(raw_line.rstrip())

    def flush_label(self) -> None:
        if self.current_label is None or self.current_image is None:
            return
        self.current_records.append(
            _build_record(
                self.current_image,
                self.current_page_index,
                self.current_label,
                self.current_text,
                self.groups,
            )
        )
        self.current_label = None
        self.current_text = []

    def flush_page(self) -> None:
        if self.current_image is None:
            return
        self.flush_label()
        self.pages.append(
            LabelPlusPage(
                image_name=self.current_image,
                page_index=self.current_page_index,
                records=self.current_records,
            )
        )
        self.current_records = []


def _build_project_manifest(labelplus_path: Path, document: LabelPlusDocument) -> ProjectManifest:
    project_root = labelplus_path.parent
    images: list[ManifestImage] = []
    missing_images: list[MissingImage] = []
    for page in document.pages:
        image, missing = _resolve_manifest_page(project_root, page)
        if missing is not None:
            missing_images.append(missing)
        if image is not None:
            images.append(image)

    return ProjectManifest(
        project_root=project_root,
        labelplus_file=labelplus_path,
        version=document.version,
        groups=document.groups,
        images=images,
        missing_images=missing_images,
    )


def _parse_label_match(match: re.Match[str]) -> tuple[int, float, float, int]:
    return (
        int(match.group("index")),
        float(match.group("x")),
        float(match.group("y")),
        int(match.group("group")),
    )


def _build_record(
    image_name: str,
    page_index: int,
    label_values: tuple[int, float, float, int],
    text_lines: list[str],
    groups: list[str],
) -> LabelPlusRecord:
    record_index, x_ratio, y_ratio, group_id = label_values
    group_name = groups[group_id - 1] if 1 <= group_id <= len(groups) else f"group_{group_id}"
    return LabelPlusRecord(
        image_name=image_name,
        page_index=page_index,
        record_index=record_index,
        x_ratio=x_ratio,
        y_ratio=y_ratio,
        group_id=group_id,
        group_name=group_name,
        translated_text="\n".join(text_lines).strip(),
    )


def _resolve_manifest_page(
    project_root: Path,
    page: LabelPlusPage,
) -> tuple[ManifestImage | None, MissingImage | None]:
    image_path = project_root / page.image_name
    if not image_path.exists():
        return None, MissingImage(
            image_name=page.image_name,
            page_index=page.page_index,
            label_count=len(page.records),
            reason="declared in LabelPlus text but not found under project directory",
        )

    with Image.open(image_path) as image:
        width, height = image.size

    labels = [_record_to_manifest_label(record, width, height) for record in page.records]
    return ManifestImage(page.image_name, image_path, width, height, labels), None


def _record_to_manifest_label(record: LabelPlusRecord, width: int, height: int) -> ManifestLabel:
    return ManifestLabel(
        id=record.record_id,
        page_index=record.page_index,
        record_index=record.record_index,
        x_ratio=record.x_ratio,
        y_ratio=record.y_ratio,
        x_px=round(record.x_ratio * width),
        y_px=round(record.y_ratio * height),
        group_id=record.group_id,
        group_name=record.group_name,
        translated_text=record.translated_text,
    )


def _parse_header(
    lines: list[str],
    source_name: str,
) -> tuple[tuple[int, int], list[str], str, int]:
    first_page_index = next((i for i, line in enumerate(lines) if _PAGE_RE.match(line.strip())), None)
    if first_page_index is None:
        raise ValueError(f"{source_name}: page header not found")

    header_lines = lines[:first_page_index]
    separators = [i for i, line in enumerate(header_lines) if line.strip() == "-"]
    if len(separators) < 2:
        raise ValueError(f"{source_name}: LabelPlus header must contain two '-' separators")

    version_line = next((line.strip() for line in header_lines[: separators[0]] if line.strip()), "")
    version_parts = [part.strip() for part in version_line.split(",")]
    if len(version_parts) != 2:
        raise ValueError(f"{source_name}: invalid LabelPlus version line")
    version = (int(version_parts[0]), int(version_parts[1]))

    groups = [line.strip() for line in header_lines[separators[0] + 1 : separators[1]] if line.strip()]
    if not groups:
        raise ValueError(f"{source_name}: group list is empty")

    comment = "\n".join(header_lines[separators[1] + 1 :]).strip()
    return version, groups, comment, first_page_index
