from __future__ import annotations

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

    pages: list[LabelPlusPage] = []
    current_image: str | None = None
    current_page_index = 0
    current_records: list[LabelPlusRecord] = []
    current_label: tuple[int, float, float, int] | None = None
    current_text: list[str] = []

    def flush_label() -> None:
        nonlocal current_label, current_text, current_records
        if current_label is None or current_image is None:
            return
        record_index, x_ratio, y_ratio, group_id = current_label
        group_name = groups[group_id - 1] if 1 <= group_id <= len(groups) else f"group_{group_id}"
        translated_text = "\n".join(current_text).strip()
        current_records.append(
            LabelPlusRecord(
                image_name=current_image,
                page_index=current_page_index,
                record_index=record_index,
                x_ratio=x_ratio,
                y_ratio=y_ratio,
                group_id=group_id,
                group_name=group_name,
                translated_text=translated_text,
            )
        )
        current_label = None
        current_text = []

    def flush_page() -> None:
        nonlocal current_records
        if current_image is None:
            return
        flush_label()
        pages.append(
            LabelPlusPage(
                image_name=current_image,
                page_index=current_page_index,
                records=current_records,
            )
        )
        current_records = []

    for raw_line in lines[body_start:]:
        line = raw_line.strip()
        page_match = _PAGE_RE.match(line)
        if page_match:
            flush_page()
            current_page_index += 1
            current_image = page_match.group("name")
            current_records = []
            current_label = None
            current_text = []
            continue

        label_match = _LABEL_RE.match(line)
        if label_match:
            if current_image is None:
                raise ValueError(f"{source_name}: label appears before page header")
            flush_label()
            current_label = (
                int(label_match.group("index")),
                float(label_match.group("x")),
                float(label_match.group("y")),
                int(label_match.group("group")),
            )
            current_text = []
            continue

        if current_label is not None:
            current_text.append(raw_line.rstrip())

    flush_page()

    return LabelPlusDocument(
        source_name=source_name,
        version=version,
        groups=groups,
        comment=comment,
        pages=pages,
    )


def parse_labelplus_project(labelplus_file: str | Path) -> ProjectManifest:
    labelplus_path = Path(labelplus_file).resolve()
    project_root = labelplus_path.parent
    document = parse_labelplus_text(
        labelplus_path.read_text(encoding="utf-8-sig"),
        source_name=str(labelplus_path),
    )

    images: list[ManifestImage] = []
    missing_images: list[MissingImage] = []
    for page in document.pages:
        image_path = project_root / page.image_name
        if not image_path.exists():
            missing_images.append(
                MissingImage(
                    image_name=page.image_name,
                    page_index=page.page_index,
                    label_count=len(page.records),
                    reason="declared in LabelPlus text but not found under project directory",
                )
            )
            continue

        with Image.open(image_path) as image:
            width, height = image.size

        labels = [
            ManifestLabel(
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
            for record in page.records
        ]
        images.append(
            ManifestImage(
                image_name=page.image_name,
                image_path=image_path,
                width=width,
                height=height,
                labels=labels,
            )
        )

    return ProjectManifest(
        project_root=project_root,
        labelplus_file=labelplus_path,
        version=document.version,
        groups=document.groups,
        images=images,
        missing_images=missing_images,
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

