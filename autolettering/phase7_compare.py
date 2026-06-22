from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


@dataclass(frozen=True)
class PreviewMethodInput:
    label: str
    preview_run_dir: Path
    evaluation_run_dir: Path | None = None


def run_phase7_method_comparison(
    methods: list[PreviewMethodInput],
    output_root: str | Path = "outputs/runs",
    run_id: str | None = None,
) -> Path:
    if not methods:
        raise ValueError("at least one method is required")
    run_dir = Path(output_root) / (run_id or "phase7-method-comparison")
    run_dir.mkdir(parents=True, exist_ok=True)
    results = [_load_method_result(method) for method in methods]
    local_sheet = _write_local_sheet(run_dir / "debug" / "local-method-comparison.png", results)
    page_sheet = _write_page_sheet(run_dir / "debug" / "page-method-comparison.png", results)
    _write_json(run_dir / "method-comparison.json", {"methods": results})
    _write_index(run_dir / "index.md", results, local_sheet, page_sheet)
    return run_dir


def _load_method_result(method: PreviewMethodInput) -> dict[str, Any]:
    preview_rows = _load_preview_rows(method.preview_run_dir / "preview-results.jsonl")
    evaluation_rows = _load_evaluation_rows(method.evaluation_run_dir) if method.evaluation_run_dir else []
    return {
        "label": method.label,
        "preview_run_dir": str(method.preview_run_dir),
        "evaluation_run_dir": str(method.evaluation_run_dir) if method.evaluation_run_dir else None,
        "preview_rows": preview_rows,
        "evaluation_rows": evaluation_rows,
    }


def _load_preview_rows(path: Path) -> list[dict[str, Any]]:
    return [row for row in _load_jsonl(path) if row.get("status") == "page_preview_generated"]


def _load_evaluation_rows(run_dir: Path) -> list[dict[str, Any]]:
    path = run_dir / "preview-evaluation.jsonl"
    if not path.exists():
        return [{"status": "missing", "failure_reason": "missing_preview_evaluation_jsonl"}]
    return _load_jsonl(path)


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _write_local_sheet(path: Path, results: list[dict[str, Any]]) -> Path:
    items = _local_items(results)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not items:
        _blank_sheet(path, "No local preview records found")
        return path
    font = ImageFont.load_default()
    label_w, panel_w, panel_h = 190, 220, 180
    header_h, row_h, pad = 26, panel_h + 34, 12
    width = label_w + panel_w * 3 + pad * 5
    height = pad + sum(header_h + row_h * len(group) for group in _group_items(items).values()) + pad
    sheet = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(sheet)
    y = pad
    for record_id, group in _group_items(items).items():
        draw.text((pad, y), f"Record: {record_id}", fill="black", font=font)
        y += header_h
        for item in group:
            _draw_local_row(draw, sheet, item, (pad, y), (label_w, panel_w, panel_h), font)
            y += row_h
    sheet.save(path)
    return path


def _local_items(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for result in results:
        for row in result["preview_rows"]:
            preview = row.get("preview", {})
            for record in row.get("records", []):
                items.append({"method": result["label"], "record": record, "preview": preview})
    return items


def _group_items(items: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in sorted(items, key=lambda value: (value["record"].get("record_id", ""), value["method"])):
        grouped.setdefault(str(item["record"].get("record_id", "")), []).append(item)
    return grouped


def _draw_local_row(
    draw: ImageDraw.ImageDraw,
    sheet: Image.Image,
    item: dict[str, Any],
    origin: tuple[int, int],
    sizes: tuple[int, int, int],
    font: ImageFont.ImageFont,
) -> None:
    label_w, panel_w, panel_h = sizes
    x, y = origin
    record = item["record"]
    bbox = tuple(record["bbox"])
    labels = ["original crop", "cleaned crop", "final preview crop"]
    images = [
        _crop_image(item["preview"]["original_page_path"], bbox),
        _crop_image(item["preview"]["cleaned_page_path"], bbox),
        _crop_image(item["preview"]["page_preview_path"], bbox),
    ]
    draw.text((x, y), item["method"], fill="black", font=font)
    draw.text((x, y + 16), str(record.get("cleanup_method", ""))[:30], fill=(70, 70, 70), font=font)
    for index, (label, image) in enumerate(zip(labels, images, strict=True)):
        panel_x = x + label_w + index * (panel_w + 12)
        draw.text((panel_x, y), label, fill="black", font=font)
        _paste_fitted(sheet, image, (panel_x, y + 20, panel_w, panel_h))
        draw.rectangle((panel_x, y + 20, panel_x + panel_w, y + 20 + panel_h), outline=(160, 160, 160))


def _write_page_sheet(path: Path, results: list[dict[str, Any]]) -> Path:
    rows = _page_items(results)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        _blank_sheet(path, "No page previews found")
        return path
    font = ImageFont.load_default()
    label_w, panel_w, panel_h, pad = 190, 260, 360, 12
    row_h = panel_h + 38
    width = label_w + panel_w * 3 + pad * 5
    height = pad + row_h * len(rows) + pad
    sheet = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(sheet)
    for index, row in enumerate(rows):
        _draw_page_row(draw, sheet, row, (pad, pad + index * row_h), (label_w, panel_w, panel_h), font)
    sheet.save(path)
    return path


def _page_items(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in results:
        for row in result["preview_rows"]:
            rows.append({"method": result["label"], "row": row, "evaluation": _evaluation_summary(result)})
    return rows


def _draw_page_row(
    draw: ImageDraw.ImageDraw,
    sheet: Image.Image,
    item: dict[str, Any],
    origin: tuple[int, int],
    sizes: tuple[int, int, int],
    font: ImageFont.ImageFont,
) -> None:
    label_w, panel_w, panel_h = sizes
    x, y = origin
    preview = item["row"].get("preview", {})
    labels = ["original page", "cleaned page", "final page preview"]
    paths = [preview.get("original_page_path"), preview.get("cleaned_page_path"), preview.get("page_preview_path")]
    draw.text((x, y), item["method"], fill="black", font=font)
    draw.text((x, y + 16), str(item.get("evaluation") or "no eval")[:34], fill=(70, 70, 70), font=font)
    for index, (label, image_path) in enumerate(zip(labels, paths, strict=True)):
        panel_x = x + label_w + index * (panel_w + 12)
        draw.text((panel_x, y), label, fill="black", font=font)
        _paste_fitted(sheet, _open_rgb(image_path), (panel_x, y + 20, panel_w, panel_h))
        draw.rectangle((panel_x, y + 20, panel_x + panel_w, y + 20 + panel_h), outline=(160, 160, 160))


def _evaluation_summary(result: dict[str, Any]) -> str:
    evaluated = [row for row in result["evaluation_rows"] if row.get("status") == "evaluated"]
    if not evaluated:
        return "no evaluated MIMO result"
    row = evaluated[0]
    return f"score={row.get('score')} usable={row.get('usable')} art={row.get('art_preserved')}"


def _crop_image(path: str | Path, bbox: tuple[int, int, int, int]) -> Image.Image:
    with Image.open(path) as image:
        return image.convert("RGB").crop(bbox)


def _open_rgb(path: str | Path | None) -> Image.Image:
    if not path:
        return Image.new("RGB", (32, 32), "white")
    with Image.open(path) as image:
        return image.convert("RGB")


def _paste_fitted(sheet: Image.Image, image: Image.Image, box: tuple[int, int, int, int]) -> None:
    x, y, width, height = box
    fitted = image.copy()
    fitted.thumbnail((width, height), Image.Resampling.LANCZOS)
    bg = Image.new("RGB", (width, height), (248, 248, 248))
    bg.paste(fitted, ((width - fitted.width) // 2, (height - fitted.height) // 2))
    sheet.paste(bg, (x, y))


def _blank_sheet(path: Path, message: str) -> None:
    sheet = Image.new("RGB", (480, 120), "white")
    ImageDraw.Draw(sheet).text((16, 48), message, fill="black", font=ImageFont.load_default())
    sheet.save(path)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_index(path: Path, results: list[dict[str, Any]], local_sheet: Path, page_sheet: Path) -> None:
    lines = [
        "# Phase 7 Preview Method Comparison",
        "",
        "## Artifacts",
        "",
        f"- Local method sheet: `{local_sheet}`",
        f"- Page method sheet: `{page_sheet}`",
        f"- Structured summary: `{path.parent / 'method-comparison.json'}`",
        "",
        "## Methods",
        "",
        "| Method | Preview run | Evaluation run | Evaluation summary |",
        "| --- | --- | --- | --- |",
    ]
    for result in results:
        lines.append(
            "| "
            + " | ".join(
                [
                    result["label"],
                    f"`{result['preview_run_dir']}`",
                    f"`{result['evaluation_run_dir']}`" if result["evaluation_run_dir"] else "n/a",
                    _evaluation_summary(result),
                ]
            )
            + " |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
