from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from autolettering.inpaint.nonbubble import build_text_mask, inpaint_crop
from autolettering.models.mimo import MimoVisionClient, MimoVisionConfig
from autolettering.text_bbox import selected_text_bbox
from autolettering.text_mask_bbox import selected_text_mask_bbox


DEFAULT_VARIANTS = [
    "tight_t185_d3",
    "tight_t210_d5",
    "tight_t235_d7",
    "tight_t210_d9",
    "rect_expand2",
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare cleanup mask variants for one hard bubble record.")
    parser.add_argument("--detection-run-dir", default="outputs/runs/phase2-gbc06-diverse-expansion-v2-color-light-text")
    parser.add_argument("--record-id", default="GBC06_18.png#3")
    parser.add_argument("--output-root", default="outputs/runs")
    parser.add_argument("--run-id", default="phase6-gbc06-18-mask-variant-lama-large-v1")
    parser.add_argument("--inpaint-method", default="bt_lama_large")
    parser.add_argument("--variant", action="append", dest="variants", default=None)
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--skip-mimo", action="store_true")
    args = parser.parse_args()

    load_env_file(Path(args.env_file))
    run_dir = Path(args.output_root) / args.run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    record = load_record(Path(args.detection_run_dir), args.record_id)
    variants = args.variants or DEFAULT_VARIANTS

    records = run_variants(run_dir, record, variants, args.inpaint_method)
    sheet = write_variant_grid(run_dir / "visuals" / "mask-variant-grid.png", records)
    mimo_sheet = write_mimo_grid(run_dir / "visuals" / "mask-variant-mimo-grid.png", records)
    metrics = write_metrics(run_dir / "reports" / "mask-variant-metrics.json", records)
    mimo = {}
    if not args.skip_mimo:
        mimo = run_mimo(run_dir, mimo_sheet, records)

    summary = {
        "record_id": args.record_id,
        "image_path": record["image_path"],
        "text_bbox": list(selected_text_bbox(record)),
        "mask_bbox": list(selected_text_mask_bbox(record)),
        "inpaint_method": args.inpaint_method,
        "variants": records,
        "sheet": str(sheet),
        "mimo_sheet": str(mimo_sheet),
        "metrics": metrics,
        "mimo": mimo,
    }
    write_json(run_dir / "reports" / "mask-variant-summary.json", summary)
    write_report(run_dir / "reports" / "phase6-mask-variant-report.md", summary)
    print(json.dumps({"run_dir": str(run_dir), "sheet": str(sheet)}, ensure_ascii=False))


def run_variants(run_dir: Path, record: dict, variants: list[str], inpaint_method: str) -> list[dict[str, Any]]:
    image_path = Path(record["image_path"])
    text_bbox = selected_text_bbox(record)
    mask_bbox = selected_text_mask_bbox(record)
    with Image.open(image_path) as image:
        source = image.convert("RGB")
    crop = source.crop(text_bbox)

    input_dir = run_dir / "input"
    input_dir.mkdir(parents=True, exist_ok=True)
    crop_path = input_dir / "original-crop.png"
    crop.save(crop_path)

    records: list[dict[str, Any]] = []
    for name in variants:
        started = time.perf_counter()
        output_dir = run_dir / "variants" / name
        output_dir.mkdir(parents=True, exist_ok=True)
        try:
            mask = build_variant_mask(source, text_bbox, mask_bbox, name)
            method_name, cleaned = inpaint_crop(crop, mask, inpaint_method)
            elapsed = round(time.perf_counter() - started, 3)

            mask_path = output_dir / "mask.png"
            mask_overlay_path = output_dir / "mask-overlay.png"
            cleaned_path = output_dir / "cleaned.png"
            before_after_path = output_dir / "before-after.png"
            mask.save(mask_path)
            save_mask_overlay(crop, mask, mask_overlay_path)
            cleaned.save(cleaned_path)
            save_before_after(crop, cleaned, before_after_path)
            records.append(
                {
                    "variant": name,
                    "status": "ok",
                    "method": method_name,
                    "elapsed_seconds": elapsed,
                    "input_crop_path": str(crop_path),
                    "mask_path": str(mask_path),
                    "mask_overlay_path": str(mask_overlay_path),
                    "cleaned_path": str(cleaned_path),
                    "before_after_path": str(before_after_path),
                    "mask_pixel_count": int(np.array(mask.convert("L")).sum() // 255),
                }
            )
        except Exception as exc:
            records.append(
                {
                    "variant": name,
                    "status": "failed",
                    "method": inpaint_method,
                    "failure_reason": f"{type(exc).__name__}: {str(exc)[:500]}",
                }
            )
    return records


def build_variant_mask(
    source: Image.Image,
    text_bbox: tuple[int, int, int, int],
    mask_bbox: tuple[int, int, int, int],
    variant: str,
) -> Image.Image:
    if variant == "tight_t185_d3":
        return local_text_mask(source, text_bbox, mask_bbox, dark_threshold=185, dilate_px=3)
    if variant == "tight_t210_d5":
        return local_text_mask(source, text_bbox, mask_bbox, dark_threshold=210, dilate_px=5)
    if variant == "tight_t235_d7":
        return local_text_mask(source, text_bbox, mask_bbox, dark_threshold=235, dilate_px=7)
    if variant == "tight_t210_d9":
        return local_text_mask(source, text_bbox, mask_bbox, dark_threshold=210, dilate_px=9)
    if variant == "rect_expand2":
        return local_rect_mask(source, text_bbox, mask_bbox, expand_px=2)
    if variant == "hybrid_rect_expand2_text_t210_d5":
        rect = local_rect_mask(source, text_bbox, mask_bbox, expand_px=2)
        text = local_text_mask(source, text_bbox, mask_bbox, dark_threshold=210, dilate_px=5)
        return ImageChops.lighter(rect, text)
    if match := re.fullmatch(r"tight_t(\d+)_d(\d+)", variant):
        threshold, dilate = (int(value) for value in match.groups())
        return local_text_mask(source, text_bbox, mask_bbox, dark_threshold=threshold, dilate_px=dilate)
    if match := re.fullmatch(r"rect_expand(\d+)", variant):
        return local_rect_mask(source, text_bbox, mask_bbox, expand_px=int(match.group(1)))
    if match := re.fullmatch(r"hybrid_rect_expand(\d+)_text_t(\d+)_d(\d+)", variant):
        expand, threshold, dilate = (int(value) for value in match.groups())
        rect = local_rect_mask(source, text_bbox, mask_bbox, expand_px=expand)
        text = local_text_mask(source, text_bbox, mask_bbox, dark_threshold=threshold, dilate_px=dilate)
        return ImageChops.lighter(rect, text)
    raise ValueError(f"unsupported_mask_variant:{variant}")


def local_text_mask(
    source: Image.Image,
    text_bbox: tuple[int, int, int, int],
    mask_bbox: tuple[int, int, int, int],
    dark_threshold: int,
    dilate_px: int,
) -> Image.Image:
    crop = source.crop(text_bbox)
    local_mask = Image.new("L", crop.size, 0)
    text_crop = source.crop(mask_bbox)
    text_mask = build_text_mask(text_crop, dark_threshold=dark_threshold, dilate_px=dilate_px, polarity="dark_on_light")
    local_mask.paste(text_mask, (mask_bbox[0] - text_bbox[0], mask_bbox[1] - text_bbox[1]))
    return local_mask


def local_rect_mask(
    source: Image.Image,
    text_bbox: tuple[int, int, int, int],
    mask_bbox: tuple[int, int, int, int],
    expand_px: int,
) -> Image.Image:
    crop = source.crop(text_bbox)
    expanded = expand_bbox(mask_bbox, source.size, expand_px)
    local = offset_bbox(expanded, text_bbox)
    mask = Image.new("L", crop.size, 0)
    ImageDraw.Draw(mask).rectangle(local, fill=255)
    return mask.filter(ImageFilter.MaxFilter(3))


def write_variant_grid(output_path: Path, records: list[dict[str, Any]]) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tiles: list[tuple[str, str | None]] = []
    input_path = next((record.get("input_crop_path") for record in records if record.get("input_crop_path")), None)
    if input_path:
        tiles.append(("original", input_path))
    for record in records:
        tiles.append((f"{record['variant']} mask", record.get("mask_overlay_path")))
        tiles.append((record["variant"], record.get("cleaned_path")))
    columns = near_square_columns(len(tiles))
    return write_grid(output_path, tiles, columns)


def write_mimo_grid(output_path: Path, records: list[dict[str, Any]]) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tiles: list[tuple[str, str | None]] = []
    input_path = next((record.get("input_crop_path") for record in records if record.get("input_crop_path")), None)
    if input_path:
        tiles.append(("original", input_path))
    tiles.extend((record["variant"], record.get("cleaned_path")) for record in records)
    return write_grid(output_path, tiles, near_square_columns(len(tiles)))


def write_grid(output_path: Path, tiles: list[tuple[str, str | Path | None]], columns: int) -> Path:
    font = ImageFont.load_default()
    loaded: list[tuple[str, Image.Image]] = []
    for label, path in tiles:
        if path and Path(path).exists():
            image = Image.open(path).convert("RGB")
        else:
            image = Image.new("RGB", (320, 260), (245, 245, 245))
            ImageDraw.Draw(image).text((12, 12), "no output", fill=(80, 80, 80), font=font)
        loaded.append((label, image))

    rows = int(np.ceil(len(loaded) / columns))
    tile_w, tile_h, label_h, pad = 330, 260, 24, 10
    sheet = Image.new("RGB", (pad + columns * (tile_w + pad), pad + rows * (tile_h + label_h + pad)), "white")
    draw = ImageDraw.Draw(sheet)
    for index, (label, image) in enumerate(loaded):
        col = index % columns
        row = index // columns
        x = pad + col * (tile_w + pad)
        y = pad + row * (tile_h + label_h + pad)
        draw.rectangle((x, y, x + tile_w, y + label_h), fill=(245, 245, 245), outline=(180, 180, 180))
        draw.text((x + 4, y + 6), label[:42], fill="black", font=font)
        thumb = image.copy()
        thumb.thumbnail((tile_w, tile_h), Image.Resampling.LANCZOS)
        draw.rectangle((x, y + label_h, x + tile_w, y + label_h + tile_h), outline=(210, 210, 210), fill="white")
        sheet.paste(thumb, (x + (tile_w - thumb.width) // 2, y + label_h + (tile_h - thumb.height) // 2))
    sheet.save(output_path)
    return output_path


def near_square_columns(count: int) -> int:
    if count <= 0:
        return 1
    cell_width = 340
    cell_height = 294
    best_columns = 1
    best_score = float("inf")
    for columns in range(1, count + 1):
        rows = int(np.ceil(count / columns))
        ratio = (columns * cell_width) / max(1, rows * cell_height)
        score = abs(np.log(ratio))
        if score < best_score:
            best_score = score
            best_columns = columns
    return best_columns


def save_mask_overlay(crop: Image.Image, mask: Image.Image, output_path: Path) -> None:
    base = crop.convert("RGB")
    red = Image.new("RGB", base.size, (255, 60, 60))
    alpha = mask.convert("L").point(lambda value: min(120, value), mode="L")
    overlay = Image.composite(red, base, alpha)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    overlay.save(output_path)


def save_before_after(before: Image.Image, after: Image.Image, output_path: Path) -> None:
    canvas = Image.new("RGB", (before.width + after.width, max(before.height, after.height)), "white")
    canvas.paste(before.convert("RGB"), (0, 0))
    canvas.paste(after.convert("RGB"), (before.width, 0))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path)


def write_metrics(output_path: Path, records: list[dict[str, Any]]) -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    for record in records:
        if record.get("status") != "ok":
            metrics[record["variant"]] = {"status": "failed", "reason": record.get("failure_reason")}
            continue
        mask = np.array(Image.open(record["mask_path"]).convert("L")) > 0
        before = Image.open(record["input_crop_path"]).convert("L")
        after = Image.open(record["cleaned_path"]).convert("L")
        metrics[record["variant"]] = mask_metrics(before, after, mask)
    write_json(output_path, metrics)
    return metrics


def mask_metrics(before: Image.Image, after: Image.Image, mask: np.ndarray) -> dict[str, Any]:
    before_arr = np.array(before, dtype=np.float32)
    after_arr = np.array(after, dtype=np.float32)
    if not bool(mask.any()):
        return {"status": "empty_mask"}
    return {
        "status": "ok",
        "mask_pixels": int(mask.sum()),
        "before_dark_lt80": int((before_arr[mask] < 80).sum()),
        "after_dark_lt80": int((after_arr[mask] < 80).sum()),
        "after_mean": round(float(after_arr[mask].mean()), 2),
        "after_std": round(float(after_arr[mask].std()), 2),
        "abs_change_mean": round(float(np.abs(after_arr[mask] - before_arr[mask]).mean()), 2),
    }


def run_mimo(run_dir: Path, sheet: Path, records: list[dict[str, Any]]) -> dict[str, Any]:
    missing = [name for name in ["MIMO_BASE_URL", "MIMO_API_KEY", "MIMO_VISION_MODEL"] if not os.environ.get(name)]
    if missing:
        result = {"status": "unavailable", "reason": f"missing env: {', '.join(missing)}"}
        write_json(run_dir / "reports" / "mimo-mask-variant-evaluation.json", result)
        return result
    client = MimoVisionClient(
        MimoVisionConfig(
            base_url=os.environ["MIMO_BASE_URL"],
            api_key=os.environ["MIMO_API_KEY"],
            model=os.environ["MIMO_VISION_MODEL"],
            thinking_type="disabled",
            max_completion_tokens=1200,
        )
    )
    methods = [record["variant"] for record in records]
    prompt = "\n".join(
        [
            "Evaluate this near-square manga speech-bubble cleanup mask-variant grid.",
            "The first tile is the original crop. Each method then appears as two tiles: a red mask overlay and its cleaned output.",
            "Judge cleanup only: Japanese source text should disappear; the neighbor speech-bubble text on the left and bottom line art must remain intact.",
            "Reject variants that create a visible white rectangle, leave readable ghost text, damage line art, or over-clean the neighboring bubble text.",
            "Do not require Chinese translated text to appear.",
            f"Mask variants: {json.dumps(methods, ensure_ascii=False)}",
            "Return only JSON with keys best_variant, ranking, scores, unacceptable_variants, per_variant_notes, reasoning_summary, caveats.",
        ]
    )
    try:
        response = client.analyze_image(sheet, prompt, kind="phase6_mask_variant_experiment", max_completion_tokens=1200)
        result = {"status": "ok", **response}
    except Exception as exc:
        result = {
            "status": "failed",
            "reason": f"{type(exc).__name__}: {str(exc)[:500]}",
            "request": {
                "kind": "phase6_mask_variant_experiment",
                "image_path": str(sheet),
                "variant_count": len(records),
            },
        }
    write_json(run_dir / "reports" / "mimo-mask-variant-evaluation.json", result)
    return result


def load_record(detection_run_dir: Path, record_id: str) -> dict:
    with (detection_run_dir / "detections.jsonl").open("r", encoding="utf-8") as handle:
        for line in handle:
            payload = json.loads(line)
            if payload.get("record_id") == record_id:
                return payload
    raise SystemExit(f"missing_record:{record_id}")


def expand_bbox(bbox: tuple[int, int, int, int], image_size: tuple[int, int], padding: int) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = bbox
    width, height = image_size
    return max(0, x1 - padding), max(0, y1 - padding), min(width, x2 + padding), min(height, y2 + padding)


def offset_bbox(inner: tuple[int, int, int, int], outer: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    return inner[0] - outer[0], inner[1] - outer[1], inner[2] - outer[0], inner[3] - outer[1]


def write_report(path: Path, summary: dict[str, Any]) -> None:
    lines = [
        "# Phase 6 Mask Variant Experiment",
        "",
        f"Record: `{summary['record_id']}`",
        f"Image: `{summary['image_path']}`",
        f"Text bbox: `{summary['text_bbox']}`",
        f"Mask bbox: `{summary['mask_bbox']}`",
        f"Inpaint method: `{summary['inpaint_method']}`",
        "",
        "## Artifacts",
        "",
        f"- Variant grid: `{summary['sheet']}`",
        f"- MIMO grid: `{summary['mimo_sheet']}`",
        "- Variant details: `variants/<variant>/`",
        "- Metrics: `reports/mask-variant-metrics.json`",
        "- MIMO: `reports/mimo-mask-variant-evaluation.json`",
        "",
        "## Variant Status",
        "",
        *[
            f"- `{item['variant']}`: `{item['status']}` {item.get('failure_reason', '')}"
            for item in summary["variants"]
        ],
        "",
        "## MIMO",
        "",
        "```json",
        json.dumps(mimo_brief(summary.get("mimo", {})), ensure_ascii=False, indent=2),
        "```",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def mimo_brief(mimo: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": mimo.get("status"),
        "raw_text": mimo.get("raw_text"),
        "response": mimo.get("response"),
        "reason": mimo.get("reason"),
    }


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        name, value = stripped.split("=", 1)
        os.environ.setdefault(name.strip(), value.strip().strip('"').strip("'"))


if __name__ == "__main__":
    main()
