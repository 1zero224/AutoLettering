from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
from typing import Any, Protocol

from PIL import Image, ImageDraw, ImageFont

from .review_tiles import segmented_review_tile


@dataclass(frozen=True)
class PreviewMethodInput:
    label: str
    preview_run_dir: Path
    evaluation_run_dir: Path | None = None


class PreviewComparisonClient(Protocol):
    def analyze_image(
        self,
        image_path: str | Path,
        prompt: str,
        kind: str = "image_analysis",
        max_completion_tokens: int | None = None,
    ) -> dict:
        ...


def run_phase7_method_comparison(
    methods: list[PreviewMethodInput],
    output_root: str | Path = "outputs/runs",
    run_id: str | None = None,
    client: PreviewComparisonClient | None = None,
    crop_mode: str = "text",
) -> Path:
    if not methods:
        raise ValueError("at least one method is required")
    if crop_mode not in {"text", "record"}:
        raise ValueError(f"unsupported crop_mode: {crop_mode}")
    run_dir = Path(output_root) / (run_id or "phase7-method-comparison")
    run_dir.mkdir(parents=True, exist_ok=True)
    results = [_load_method_result(method) for method in methods]
    local_sheet = _write_local_sheet(run_dir / "debug" / "local-method-comparison.png", results)
    page_sheet = _write_page_sheet(run_dir / "debug" / "page-method-comparison.png", results)
    square_sheet = _write_near_square_result_sheet(
        run_dir / "debug" / "near-square-result-grid.png",
        results,
        crop_mode=crop_mode,
    )
    mimo = _run_mimo_comparison(run_dir, square_sheet, results, client) if client else {"status": "not_requested"}
    _write_json(
        run_dir / "method-comparison.json",
        {"methods": results, "near_square_sheet": str(square_sheet), "mimo": mimo},
    )
    _write_index(run_dir / "index.md", results, local_sheet, page_sheet, square_sheet, mimo)
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


def _write_near_square_result_sheet(path: Path, results: list[dict[str, Any]], crop_mode: str) -> Path:
    items = _result_items(results, crop_mode)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not items:
        _blank_sheet(path, "No final preview records found")
        return path

    font = ImageFont.load_default()
    columns = _near_square_columns(len(items), cell_width=360, cell_height=690)
    rows = math.ceil(len(items) / columns)
    tile_w, tile_h, label_h, pad = 340, 620, 42, 12
    width = pad + columns * (tile_w + pad)
    height = pad + rows * (tile_h + label_h + pad)
    sheet = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(sheet)

    for index, item in enumerate(items):
        col = index % columns
        row = index // columns
        x = pad + col * (tile_w + pad)
        y = pad + row * (tile_h + label_h + pad)
        draw.rectangle((x, y, x + tile_w, y + label_h), fill=(245, 245, 245), outline=(180, 180, 180))
        draw.text((x + 5, y + 5), item["method"][:44], fill="black", font=font)
        draw.text((x + 5, y + 23), _score_label(item)[:44], fill=(70, 70, 70), font=font)
        review_tile = segmented_review_tile(item["image"], size=(tile_w, tile_h))
        sheet.paste(review_tile, (x, y + label_h))
        draw.rectangle((x, y + label_h, x + tile_w, y + label_h + tile_h), outline=(210, 210, 210))

    sheet.save(path)
    return path


def _result_items(results: list[dict[str, Any]], crop_mode: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for result in results:
        evaluation = _first_evaluation(result)
        for row in result["preview_rows"]:
            preview = row.get("preview", {})
            for record in row.get("records", []):
                bbox = record.get("text_bbox") if crop_mode == "text" else record.get("bbox")
                if not bbox:
                    bbox = record.get("bbox")
                items.append(
                    {
                        "method": result["label"],
                        "record_id": record.get("record_id"),
                        "image": _crop_image(preview.get("page_preview_path"), tuple(bbox)),
                        "evaluation": evaluation,
                    }
                )
    return items


def _near_square_columns(count: int, cell_width: int, cell_height: int) -> int:
    best_columns = 1
    best_score = float("inf")
    for columns in range(1, count + 1):
        rows = math.ceil(count / columns)
        ratio = (columns * cell_width) / max(1, rows * cell_height)
        score = abs(math.log(ratio))
        if score < best_score:
            best_score = score
            best_columns = columns
    return best_columns


def _score_label(item: dict[str, Any]) -> str:
    evaluation = item.get("evaluation") or {}
    if evaluation.get("status") == "evaluated":
        return f"score={evaluation.get('score')} usable={evaluation.get('usable')}"
    return "no evaluated MIMO result"


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
    row = _first_evaluation(result)
    if not row:
        return "no evaluated MIMO result"
    return f"score={row.get('score')} usable={row.get('usable')} art={row.get('art_preserved')}"


def _first_evaluation(result: dict[str, Any]) -> dict[str, Any] | None:
    evaluated = [row for row in result["evaluation_rows"] if row.get("status") == "evaluated"]
    return evaluated[0] if evaluated else None


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
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _run_mimo_comparison(
    run_dir: Path,
    square_sheet: Path,
    results: list[dict[str, Any]],
    client: PreviewComparisonClient,
) -> dict[str, Any]:
    prompt = "\n".join(
        [
            "Evaluate this near-square manga lettering comparison grid.",
            "Each tile is the same target text area after a different cleanup/layout method.",
            "Tall vertical text areas are enlarged by splitting each tile into ordered TOP/MIDDLE/BOTTOM segments; judge all segments for the same method together.",
            "Prefer methods that fully remove Japanese source text, keep surrounding manga art intact, preserve natural vertical manga lettering, avoid rotation, avoid oversized/heavy lettering, and keep phrase breaks natural.",
            "Do not claim a method is horizontal or rotated unless that is visibly different in the candidate tile.",
            "Do not judge translation meaning; compare visual editing quality only.",
            f"Methods JSON: {json.dumps([result['label'] for result in results], ensure_ascii=False)}",
            "Return only JSON with keys: best_method, ranking, scores, unacceptable_methods, per_method_notes, reasoning_summary.",
        ]
    )
    response = client.analyze_image(
        square_sheet,
        prompt,
        kind="phase7_near_square_method_comparison",
        max_completion_tokens=1200,
    )
    _write_json(run_dir / "reports" / "mimo-near-square-comparison.json", response)
    return {"status": "ok", **response}


def _write_index(
    path: Path,
    results: list[dict[str, Any]],
    local_sheet: Path,
    page_sheet: Path,
    square_sheet: Path,
    mimo: dict[str, Any],
) -> None:
    lines = [
        "# Phase 7 Preview Method Comparison",
        "",
        "## Artifacts",
        "",
        f"- Local method sheet: `{local_sheet}`",
        f"- Page method sheet: `{page_sheet}`",
        f"- Near-square result grid: `{square_sheet}`",
        f"- MIMO near-square result: `{path.parent / 'reports' / 'mimo-near-square-comparison.json'}`",
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
    lines.extend(["", "## MIMO Near-Square Comparison", "", "```json", json.dumps(_mimo_brief(mimo), ensure_ascii=False, indent=2), "```"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _mimo_brief(mimo: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": mimo.get("status"),
        "raw_text": mimo.get("raw_text"),
        "request": mimo.get("request"),
        "response": mimo.get("response"),
    }
