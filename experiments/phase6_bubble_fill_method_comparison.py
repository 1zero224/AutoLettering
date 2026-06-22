from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from autolettering.models.mimo import MimoVisionClient, MimoVisionConfig


DEFAULT_RECORD_IDS = [
    "GBC06_01.png#2",
    "GBC06_01.png#3",
    "GBC06_01.png#4",
    "GBC06_01.png#5",
    "GBC06_01.png#6",
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare hard and soft Phase 6 bubble cleanup outputs.")
    parser.add_argument("--hard-run-dir", default="outputs/runs/phase6-gbc06-bubble-batch-region-fill-v9")
    parser.add_argument("--soft-run-dir", default="outputs/runs/phase6-gbc06-bubble-batch-soft-region-fill-v2")
    parser.add_argument("--output-root", default="outputs/runs")
    parser.add_argument("--run-id", default="phase6-gbc06-bubble-soft-region-comparison-v3")
    parser.add_argument("--record-id", action="append", dest="record_ids", default=None)
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--skip-mimo", action="store_true")
    args = parser.parse_args()

    _load_env_file(Path(args.env_file))
    record_ids = args.record_ids or DEFAULT_RECORD_IDS
    run_dir = Path(args.output_root) / args.run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    hard_rows = _load_rows(Path(args.hard_run_dir) / "cleanup-results.jsonl")
    soft_rows = _load_rows(Path(args.soft_run_dir) / "cleanup-results.jsonl")
    pairs = [_pair_record(record_id, hard_rows, soft_rows, run_dir) for record_id in record_ids]
    sheet = _write_comparison_sheet(run_dir / "debug" / "bubble-hard-vs-soft-comparison.png", pairs)
    _write_mask_debug_sheet(run_dir / "debug" / "bubble-hard-vs-soft-mask-debug.png", pairs)
    mimo_result = _evaluate_mimo(run_dir, sheet, pairs, skip_mimo=args.skip_mimo)
    result = {
        "run_id": args.run_id,
        "hard_run_dir": str(Path(args.hard_run_dir)),
        "soft_run_dir": str(Path(args.soft_run_dir)),
        "record_ids": record_ids,
        "comparison_path": str(sheet),
        "mimo": mimo_result,
    }
    _write_json(run_dir / "reports" / "bubble-fill-method-comparison-result.json", result)
    _write_report(run_dir / "reports" / "phase6-bubble-fill-method-comparison-report.md", result)
    print(json.dumps({"run_dir": str(run_dir), "comparison_path": str(sheet)}, ensure_ascii=False))


def _load_rows(path: Path) -> dict[str, dict]:
    if not path.exists():
        raise SystemExit(f"missing cleanup results: {path}")
    rows: dict[str, dict] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            payload = json.loads(line)
            rows[str(payload.get("record_id"))] = payload
    return rows


def _pair_record(record_id: str, hard_rows: dict[str, dict], soft_rows: dict[str, dict], run_dir: Path) -> dict[str, Any]:
    hard = hard_rows.get(record_id)
    soft = soft_rows.get(record_id)
    if hard is None:
        raise SystemExit(f"missing hard cleanup row: {record_id}")
    if soft is None:
        raise SystemExit(f"missing soft cleanup row: {record_id}")
    context_paths = _write_contextual_cleaned_images(run_dir, record_id, hard["cleanup"], soft["cleanup"])
    return {
        "record_id": record_id,
        "hard": hard["cleanup"],
        "soft": soft["cleanup"],
        "context": context_paths,
    }


def _write_comparison_sheet(output_path: Path, pairs: list[dict[str, Any]]) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    font = ImageFont.load_default()
    labels = ["original context", "hard cleaned in context", "soft cleaned in context"]
    tile_w = 320
    tile_h = 220
    label_h = 22
    pad = 10
    row_h = label_h + tile_h + pad
    width = pad + 3 * (tile_w + pad)
    height = pad + len(pairs) * row_h + 28
    sheet = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(sheet)

    y = pad
    for pair in pairs:
        draw.text((pad, y), pair["record_id"], fill="black", font=font)
        y += label_h
        paths = [pair["context"]["original"], pair["context"]["hard"], pair["context"]["soft"]]
        x = pad
        for label, path in zip(labels, paths):
            draw.rectangle((x, y, x + tile_w, y + tile_h), outline=(180, 180, 180), fill=(250, 250, 250))
            draw.text((x + 4, y + 4), label, fill="black", font=font)
            image = Image.open(path).convert("RGB")
            image.thumbnail((tile_w - 12, tile_h - 28), Image.Resampling.LANCZOS)
            sheet.paste(image, (x + (tile_w - image.width) // 2, y + 24 + (tile_h - 28 - image.height) // 2))
            x += tile_w + pad
        y += tile_h + pad
    sheet.save(output_path)
    return output_path


def _write_mask_debug_sheet(output_path: Path, pairs: list[dict[str, Any]]) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    font = ImageFont.load_default()
    labels = ["hard mask", "soft mask"]
    tile_w = 320
    tile_h = 220
    label_h = 22
    pad = 10
    row_h = label_h + tile_h + pad
    width = pad + 2 * (tile_w + pad)
    height = pad + len(pairs) * row_h + 28
    sheet = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(sheet)
    y = pad
    for pair in pairs:
        draw.text((pad, y), pair["record_id"], fill="black", font=font)
        y += label_h
        paths = [pair["hard"].get("cleanup_mask_path"), pair["soft"].get("cleanup_mask_path")]
        x = pad
        for label, path in zip(labels, paths):
            draw.rectangle((x, y, x + tile_w, y + tile_h), outline=(180, 180, 180), fill=(250, 250, 250))
            draw.text((x + 4, y + 4), label, fill="black", font=font)
            if path:
                image = Image.open(path).convert("RGB")
                image.thumbnail((tile_w - 12, tile_h - 28), Image.Resampling.LANCZOS)
                sheet.paste(image, (x + (tile_w - image.width) // 2, y + 24 + (tile_h - 28 - image.height) // 2))
            x += tile_w + pad
        y += tile_h + pad
    sheet.save(output_path)
    return output_path


def _write_contextual_cleaned_images(run_dir: Path, record_id: str, hard: dict, soft: dict) -> dict[str, str]:
    output_dir = run_dir / "debug" / "contextual"
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_id = _safe_name(record_id)
    original = Image.open(soft["before_crop_path"]).convert("RGB")
    hard_context = original.copy()
    hard_cleaned = Image.open(hard["cleaned_crop_path"]).convert("RGB")
    soft_cleaned = Image.open(soft["cleaned_crop_path"]).convert("RGB")
    soft_bbox = tuple(int(value) for value in soft["bbox"])
    hard_bbox = tuple(int(value) for value in hard["bbox"])
    hard_context.paste(hard_cleaned, (hard_bbox[0] - soft_bbox[0], hard_bbox[1] - soft_bbox[1]))
    paths = {
        "original": output_dir / f"{safe_id}-original-context.png",
        "hard": output_dir / f"{safe_id}-hard-context.png",
        "soft": output_dir / f"{safe_id}-soft-context.png",
    }
    original.save(paths["original"])
    hard_context.save(paths["hard"])
    soft_cleaned.save(paths["soft"])
    return {key: str(path) for key, path in paths.items()}


def _evaluate_mimo(run_dir: Path, sheet: Path, pairs: list[dict[str, Any]], skip_mimo: bool) -> dict[str, Any]:
    if skip_mimo:
        return {"status": "skipped", "reason": "skip_mimo flag enabled"}
    missing = [name for name in ["MIMO_BASE_URL", "MIMO_API_KEY", "MIMO_VISION_MODEL"] if not os.environ.get(name)]
    if missing:
        return {"status": "unavailable", "reason": f"missing environment variables: {', '.join(missing)}"}
    client = MimoVisionClient(
        MimoVisionConfig(
            base_url=os.environ["MIMO_BASE_URL"],
            api_key=os.environ["MIMO_API_KEY"],
            model=os.environ["MIMO_VISION_MODEL"],
            thinking_type="disabled",
            max_completion_tokens=900,
        )
    )
    prompt = "\n".join(
        [
            "Evaluate this manga speech-bubble cleanup comparison sheet.",
            "Each row is one record with three tiles: original context, hard cleaned in the same context, soft cleaned in the same context.",
            "Score only cleanup quality: original Japanese removed, no visible white patch edge, bubble interior remains natural, nearby manga art preserved.",
            "Do not judge Chinese lettering layout here; this is cleanup-only.",
            f"Record ids: {json.dumps([pair['record_id'] for pair in pairs], ensure_ascii=False)}",
            "Return only JSON with keys: best_method, scores, per_record_notes, unacceptable_methods, reasoning_summary, caveats.",
        ]
    )
    try:
        response = client.analyze_image(sheet, prompt, kind="phase6_bubble_hard_vs_soft_fill", max_completion_tokens=900)
    except Exception as exc:
        return {"status": "failed", "reason": f"{type(exc).__name__}: {str(exc)[:500]}"}
    result = {
        "status": "ok",
        "request": response.get("request"),
        "response": response.get("response"),
        "raw_text": response.get("raw_text"),
    }
    _write_json(run_dir / "reports" / "mimo-bubble-fill-method-comparison.json", result)
    return result


def _write_report(path: Path, result: dict[str, Any]) -> None:
    lines = [
        "# Phase 6 Bubble Fill Method Comparison",
        "",
        f"Hard run: `{result['hard_run_dir']}`",
        f"Soft run: `{result['soft_run_dir']}`",
        f"Comparison sheet: `{result['comparison_path']}`",
        "",
        "## MIMO",
        "",
        "```json",
        json.dumps(result["mimo"], ensure_ascii=False, indent=2),
        "```",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        name, value = stripped.split("=", 1)
        os.environ.setdefault(name.strip(), value.strip().strip('"').strip("'"))


def _safe_name(value: str) -> str:
    return "".join(char if char.isalnum() else "-" for char in value).strip("-") or "record"


if __name__ == "__main__":
    main()
