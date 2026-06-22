from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from autolettering.models.gpt_image import GptImageConfig
from autolettering.models.mimo import MimoVisionClient, MimoVisionConfig
from autolettering.phase6_nonbubble import run_phase6_nonbubble_cleanup


DEFAULT_METHODS = [
    "local_diffusion",
    "flat_median_fill",
    "opencv_telea",
    "opencv_ns",
    "bt_patchmatch",
    "bt_aot",
    "bt_lama_large",
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare Phase 6 non-bubble inpainting methods on one record.")
    parser.add_argument("--detection-run-dir", default="outputs/runs/phase2-gbc06-smoke-v3")
    parser.add_argument("--output-root", default="outputs/runs")
    parser.add_argument("--run-id", default="phase6-gbc06-inpainting-method-comparison")
    parser.add_argument("--record-id", default="GBC06_01.png#16")
    parser.add_argument("--method", action="append", dest="methods", default=None)
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--skip-mimo", action="store_true")
    parser.add_argument("--include-gpt-output", default=None)
    parser.add_argument("--call-gpt-image", action="store_true")
    args = parser.parse_args()

    _load_env_file(Path(args.env_file))
    run_dir = Path(args.output_root) / args.run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    methods = args.methods or DEFAULT_METHODS

    records = _run_methods(run_dir, args.detection_run_dir, args.record_id, methods)
    gpt_record = _gpt_record(run_dir, args, records)
    sheet = _write_comparison_sheet(run_dir, args.record_id, records, gpt_record)
    metrics = _write_metrics(run_dir, records, gpt_record)
    if not args.skip_mimo:
        _write_mimo_evaluation(run_dir, sheet, records, gpt_record)
    _write_report(run_dir, args.detection_run_dir, args.record_id, records, gpt_record, sheet, metrics)
    print(run_dir)


def _run_methods(run_dir: Path, detection_run_dir: str, record_id: str, methods: list[str]) -> list[dict]:
    records = []
    for method in methods:
        method_run = run_phase6_nonbubble_cleanup(
            detection_run_dir=detection_run_dir,
            output_root=run_dir / "runs",
            run_id=method,
            sample_limit=1,
            record_ids=[record_id],
            inpaint_method=method,
        )
        row = _load_first_jsonl(method_run / "cleanup-results.jsonl")
        cleanup = row["cleanup"]
        records.append(
            {
                "label": method,
                "method": cleanup["method"],
                "translated_text": row.get("translated_text", ""),
                "input_crop_path": cleanup["input_crop_path"],
                "text_mask_path": cleanup["text_mask_path"],
                "cleaned_crop_path": cleanup["cleaned_crop_path"],
                "before_after_path": cleanup["before_after_path"],
                "bbox": cleanup["bbox"],
            }
        )
    return records


def _gpt_record(run_dir: Path, args: argparse.Namespace, records: list[dict]) -> dict | None:
    if args.call_gpt_image:
        gpt_run = run_phase6_nonbubble_cleanup(
            detection_run_dir=args.detection_run_dir,
            output_root=run_dir / "runs",
            run_id="gpt_image2",
            sample_limit=1,
            record_ids=[args.record_id],
            gpt_config=_gpt_config_from_env(),
            call_gpt_image=True,
            inpaint_method=records[0]["label"],
        )
        payload = _load_first_jsonl(gpt_run / "cleanup-results.jsonl")
        gpt_payload = payload.get("gpt_image2_edit", {})
        if gpt_payload.get("status") == "ok" and gpt_payload.get("normalized_output_path"):
            return {
                "label": "gpt_image2_direct_replacement",
                "method": "gpt_image2_masked_edit",
                "cleaned_crop_path": gpt_payload["normalized_output_path"],
            }
        return None

    if args.include_gpt_output:
        path = Path(args.include_gpt_output)
        if path.exists():
            return {
                "label": "gpt_image2_direct_replacement",
                "method": "gpt_image2_masked_edit",
                "cleaned_crop_path": str(path),
            }
    return None


def _write_comparison_sheet(run_dir: Path, record_id: str, records: list[dict], gpt_record: dict | None) -> Path:
    output = run_dir / "debug" / f"{_safe_name(record_id)}-inpainting-comparison.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    tiles = [("original", records[0]["input_crop_path"])]
    tiles.extend((record["label"], record["cleaned_crop_path"]) for record in records)
    if gpt_record is not None:
        tiles.append((gpt_record["label"], gpt_record["cleaned_crop_path"]))

    loaded = [(label, Image.open(path).convert("RGB")) for label, path in tiles]
    scale = 4
    font = ImageFont.load_default()
    label_height = 24
    padding = 8
    tile_w = max(image.width for _, image in loaded) * scale
    tile_h = max(image.height for _, image in loaded) * scale
    width = padding + len(loaded) * (tile_w + padding)
    height = label_height + tile_h + padding * 2
    sheet = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(sheet)

    x = padding
    for label, image in loaded:
        draw.rectangle((x, 0, x + tile_w, label_height), fill=(245, 245, 245), outline=(160, 160, 160))
        draw.text((x + 4, 6), label[:34], fill="black", font=font)
        resized = image.resize((image.width * scale, image.height * scale), Image.Resampling.NEAREST)
        sheet.paste(resized, (x, label_height + padding))
        x += tile_w + padding
    sheet.save(output)
    return output


def _write_metrics(run_dir: Path, records: list[dict], gpt_record: dict | None) -> dict:
    mask = np.array(Image.open(records[0]["text_mask_path"]).convert("L")) > 0
    metric_records = [{"label": "original", "path": records[0]["input_crop_path"]}]
    metric_records.extend({"label": record["label"], "path": record["cleaned_crop_path"]} for record in records)
    if gpt_record is not None:
        metric_records.append({"label": gpt_record["label"], "path": gpt_record["cleaned_crop_path"]})
    metrics = {item["label"]: _mask_metrics(item["path"], mask) for item in metric_records}
    output = run_dir / "reports" / "mask-area-metrics.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return metrics


def _mask_metrics(image_path: str | Path, mask: np.ndarray) -> dict:
    image = Image.open(image_path).convert("RGB")
    gray = np.array(image.convert("L"), dtype=np.float32)
    if gray.shape != mask.shape:
        image = image.resize((mask.shape[1], mask.shape[0]), Image.Resampling.LANCZOS)
        gray = np.array(image.convert("L"), dtype=np.float32)
    region = gray[mask]
    edges = np.abs(np.diff(gray, axis=0)).mean() + np.abs(np.diff(gray, axis=1)).mean()
    return {
        "dark_lt80": int((region < 80).sum()) if region.size else 0,
        "mean": round(float(region.mean()), 2) if region.size else None,
        "std": round(float(region.std()), 2) if region.size else None,
        "edge": round(float(edges), 2),
    }


def _write_mimo_evaluation(run_dir: Path, sheet: Path, records: list[dict], gpt_record: dict | None) -> None:
    client = MimoVisionClient(_mimo_config_from_env())
    methods = [record["label"] for record in records]
    translated_text = str(records[0].get("translated_text", "")).strip()
    prompt = "\n".join(
        [
            "Evaluate this manga text cleanup comparison sheet.",
            "The first tile is original. Other tiles are cleanup or replacement methods.",
            "For local cleanup methods, the expected output is a clean background only; Chinese text will be rendered later by the program.",
            "For local cleanup methods, do not require translated text to appear.",
            "For local cleanup methods, score whether Japanese text is removed, whether non-text art/symbols are preserved, and whether artifacts remain.",
            f"Exact Chinese translation for direct replacement: {translated_text}",
            "For gpt_image2_direct_replacement only, require the generated Chinese text to exactly match the translation above.",
            "For gpt_image2_direct_replacement, missing characters, extra characters, wrong order, unreadable glyphs, or covering non-text art must make it unusable.",
            "If a black diamond/icon or other non-text art is present, it should be preserved unless it is explicitly part of a text glyph.",
            f"Methods: {json.dumps(methods + (['gpt_image2_direct_replacement'] if gpt_record is not None else []), ensure_ascii=False)}",
            "Return only JSON with keys: best_cleanup_method, ranking, scores, unacceptable_methods, reasoning_summary, caveats.",
        ]
    )
    response = client.analyze_image(
        sheet,
        prompt,
        kind="phase6_inpainting_method_comparison",
        max_completion_tokens=900,
    )
    output = run_dir / "reports" / "mimo-inpainting-method-evaluation.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(response, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_report(
    run_dir: Path,
    detection_run_dir: str,
    record_id: str,
    records: list[dict],
    gpt_record: dict | None,
    sheet: Path,
    metrics: dict,
) -> None:
    lines = [
        "# Phase 6 Inpainting Method Comparison",
        "",
        f"Detection run directory: `{detection_run_dir}`",
        f"Record: `{record_id}`",
        "",
        "## Methods",
        "",
        *[f"- `{record['label']}` -> `{record['method']}`" for record in records],
    ]
    if gpt_record is not None:
        lines.append("- `gpt_image2_direct_replacement` -> `gpt_image2_masked_edit`")
    lines.extend(
        [
            "",
            "## Artifacts",
            "",
            f"- Comparison sheet: `{sheet}`",
            "- Method runs: `runs/<method>/cleanup-results.jsonl`",
            "- Metrics: `reports/mask-area-metrics.json`",
            "- MIMO evaluation: `reports/mimo-inpainting-method-evaluation.json`",
            "",
            "## Mask-Area Metrics",
            "",
            "```json",
            json.dumps(metrics, ensure_ascii=False, indent=2),
            "```",
        ]
    )
    output = run_dir / "reports" / "phase6-inpainting-method-comparison-report.md"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        name, value = stripped.split("=", 1)
        os.environ.setdefault(name.strip(), value.strip().strip('"').strip("'"))


def _mimo_config_from_env() -> MimoVisionConfig:
    required = ["MIMO_BASE_URL", "MIMO_API_KEY", "MIMO_VISION_MODEL"]
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        raise SystemExit(f"Missing required environment variables: {', '.join(missing)}")
    return MimoVisionConfig(
        **{
            "base_url": os.environ["MIMO_BASE_URL"],
            "api_key": os.environ["MIMO_API_KEY"],
            "model": os.environ["MIMO_VISION_MODEL"],
            "thinking_type": "disabled",
        }
    )


def _gpt_config_from_env() -> GptImageConfig:
    required = ["GPT_IMAGE_API_KEY", "GPT_IMAGE_MODEL"]
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        raise SystemExit(f"Missing required environment variables: {', '.join(missing)}")
    return GptImageConfig(
        **{
            "base_url": os.environ.get("GPT_IMAGE_BASE_URL") or None,
            "api_key": os.environ["GPT_IMAGE_API_KEY"],
            "model": os.environ["GPT_IMAGE_MODEL"],
        }
    )


def _load_first_jsonl(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.loads(handle.readline())


def _safe_name(value: str) -> str:
    return "".join(char if char.isalnum() else "-" for char in value).strip("-") or "record"


if __name__ == "__main__":
    main()
