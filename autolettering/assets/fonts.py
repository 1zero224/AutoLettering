from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re
from pathlib import Path

from fontTools.ttLib import TTFont


@dataclass(frozen=True)
class FontRecord:
    font_id: str
    path: Path
    filename: str
    family_name: str
    postscript_name: str
    style_hints: list[str]
    supports_sample_text: bool
    unsupported_chars: list[str]


def scan_font_directory(font_dir: str | Path, sample_text: str = "") -> list[FontRecord]:
    root = Path(font_dir)
    font_paths = sorted(
        [*root.rglob("*.ttf"), *root.rglob("*.otf")],
        key=lambda path: path.name.casefold(),
    )
    return [_build_font_record(path.resolve(), sample_text) for path in font_paths]


def select_font_candidates(fonts: list[FontRecord], limit: int) -> list[FontRecord]:
    if limit <= 0:
        return []

    source = [font for font in fonts if font.supports_sample_text] or fonts
    selected: list[FontRecord] = []
    seen_styles: set[str] = set()
    for font in source:
        style = _primary_style_hint(font)
        if style in seen_styles:
            continue
        selected.append(font)
        seen_styles.add(style)
        if len(selected) >= limit:
            return selected

    selected_ids = {font.font_id for font in selected}
    for font in source:
        if font.font_id in selected_ids:
            continue
        selected.append(font)
        if len(selected) >= limit:
            break
    return selected


def font_record_to_dict(record: FontRecord) -> dict:
    return {
        "font_id": record.font_id,
        "path": str(record.path),
        "filename": record.filename,
        "family_name": record.family_name,
        "postscript_name": record.postscript_name,
        "style_hints": record.style_hints,
        "supports_sample_text": record.supports_sample_text,
        "unsupported_chars": record.unsupported_chars,
    }


def _build_font_record(path: Path, sample_text: str) -> FontRecord:
    cmap = _read_cmap(path)
    unsupported = _unsupported_chars(sample_text, cmap)
    return FontRecord(
        font_id=_font_id(path),
        path=path,
        filename=path.name,
        family_name=_read_family_name(path),
        postscript_name=_read_postscript_name(path),
        style_hints=_style_hints(path.stem),
        supports_sample_text=len(unsupported) == 0,
        unsupported_chars=unsupported,
    )


def _read_cmap(path: Path) -> set[int]:
    font = TTFont(path, lazy=True)
    try:
        cmap: set[int] = set()
        for table in font["cmap"].tables:
            cmap.update(table.cmap.keys())
        return cmap
    finally:
        font.close()


def _read_family_name(path: Path) -> str:
    font = TTFont(path, lazy=True)
    try:
        for name_id in (1, 4):
            value = _first_name(font, name_id)
            if value:
                return value
    finally:
        font.close()
    return path.stem


def _read_postscript_name(path: Path) -> str:
    font = TTFont(path, lazy=True)
    try:
        return _first_name(font, 6) or path.stem
    finally:
        font.close()


def _first_name(font: TTFont, name_id: int) -> str:
    for name in font["name"].names:
        if name.nameID != name_id:
            continue
        value = name.toUnicode().strip()
        if value:
            return value
    return ""


def _unsupported_chars(text: str, cmap: set[int]) -> list[str]:
    chars = sorted({char for char in text if not char.isspace()})
    return [char for char in chars if ord(char) not in cmap]


def _style_hints(stem: str) -> list[str]:
    cleaned = re.sub(r"^\[[^\]]+]", "", stem)
    tokens = [part for part in re.split(r"[-_()\[\]\s]+", cleaned) if part]
    return tokens


def _font_id(path: Path) -> str:
    digest = hashlib.sha1(str(path).encode("utf-8")).hexdigest()[:12]
    return f"font-{digest}"


def _primary_style_hint(font: FontRecord) -> str:
    if font.style_hints:
        return font.style_hints[0].casefold()
    return font.family_name.casefold() or font.filename.casefold()
