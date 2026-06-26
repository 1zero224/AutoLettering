from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from autolettering.experiment_grid import near_square_columns, write_grid
from autolettering.layout.measure import measure_text_layout
from autolettering.layout.models import LayoutResult
from autolettering.layout.render_text import measure_preview_alignment, render_layout_preview
from autolettering.models.mimo import MimoVisionClient, MimoVisionConfig


@dataclass(frozen=True)
class LayoutVariantSpec:
    name: str
    line_breaks: str
    font_size: int
    line_spacing: int
    vertical_align: str = "top"
    angle_degrees: float = 0.0


DEFAULT_VARIANTS = [
    LayoutVariantSpec("current_fs33_s4", "-快看接下\n来登场的乐\n队竟然！", 33, 4),
    LayoutVariantSpec("phrase_fs29_s0", "-快看\n接下来登场的乐队\n竟然！", 29, 0),
    LayoutVariantSpec("phrase_fs27_s0", "-快看\n接下来登场的乐队\n竟然！", 27, 0),
    LayoutVariantSpec("phrase_fs27_s1", "-快看\n接下来登场的乐队\n竟然！", 27, 1),
    LayoutVariantSpec("phrase_fs26_s0", "-快看\n接下来登场的乐队\n竟然！", 26, 0),
    LayoutVariantSpec("phrase_fs25_s0", "-快看\n接下来登场的乐队\n竟然！", 25, 0),
    LayoutVariantSpec("phrase_fs24_s1", "-快看\n接下来登场的乐队\n竟然！", 24, 1),
    LayoutVariantSpec("scene_fs28_s1", "-快看\n接下来登场\n的乐队竟然！", 28, 1),
    LayoutVariantSpec("current_fs28_s1", "-快看接下\n来登场的乐\n队竟然！", 28, 1),
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare lettering layout variants for one hard manga record.")
    parser.add_argument("--detection-run-dir", default="outputs/runs/phase2-gbc06-diverse-expansion-v2-color-light-text")
    parser.add_argument("--cleanup-run-dir", default="outputs/runs/phase6-gbc06-18-text-mask-bt-lama-large-v2")
    parser.add_argument("--layout-run-dir", default="outputs/runs/phase4-gbc06-diverse-06-18-layout-tight-mask-v2")
    parser.add_argument("--font-selection-run-dir", default="outputs/runs/phase3-gbc06-diverse-06-18-mimo-font-selection-v1")
    parser.add_argument("--record-id", default="GBC06_18.png#3")
    parser.add_argument("--output-root", default="outputs/runs")
    parser.add_argument("--run-id", default="phase4-gbc06-18-layout-variants-v1")
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--skip-mimo", action="store_true")
    args = parser.parse_args()

    _load_env_file(Path(args.env_file))
    run_dir = Path(args.output_root) / args.run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    detection = _load_record(Path(args.detection_run_dir) / "detections.jsonl", args.record_id, "ok")
    cleanup = _load_record(Path(args.cleanup_run_dir) / "cleanup-results.jsonl", args.record_id, "cleaned")
    layout = _load_record(Path(args.layout_run_dir) / "layout-results.jsonl", args.record_id, "layout_generated")
    font = _load_record(Path(args.font_selection_run_dir) / "font-selections.jsonl", args.record_id, "selected")

    rows = run_variants(run_dir, detection, cleanup, layout, font, DEFAULT_VARIANTS)
    grid = write_variant_grid(run_dir / "visuals" / "layout-variant-grid.png", rows)
    mimo: dict[str, Any] = {}
    if not args.skip_mimo:
        mimo = run_mimo(run_dir, grid, rows)

    summary = {
        "record_id": args.record_id,
        "image_path": detection["image_path"],
        "cleanup_run_dir": str(args.cleanup_run_dir),
        "layout_run_dir": str(args.layout_run_dir),
        "font_selection_run_dir": str(args.font_selection_run_dir),
        "variants": rows,
        "grid": str(grid),
        "mimo": mimo,
    }
    _write_json(run_dir / "reports" / "layout-variant-summary.json", summary)
    print(json.dumps({"run_dir": str(run_dir), "grid": str(grid)}, ensure_ascii=False))


def run_variants(
    run_dir: Path,
    detection: dict,
    cleanup_row: dict,
    layout_row: dict,
    font_row: dict,
    variants: list[LayoutVariantSpec],
) -> list[dict[str, Any]]:
    image_path = Path(detection["image_path"])
    cleanup = cleanup_row["cleanup"]
    cleanup_bbox = tuple(cleanup["bbox"])
    text_bbox = tuple(cleanup.get("layout_text_bbox") or layout_row["layout"].get("target_bbox") or cleanup_bbox)
    font_path = Path(font_row["selected_font"]["path"])
    translated_text = detection.get("translated_text") or layout_row.get("translated_text") or ""
    cleaned_crop = _resize_to_bbox(_cleanup_crop_path(cleanup), cleanup_bbox).convert("RGB")

    rows: list[dict[str, Any]] = []
    for spec in variants:
        started = time.perf_counter()
        variant_dir = run_dir / "variants" / spec.name
        variant_dir.mkdir(parents=True, exist_ok=True)
        layout = build_layout(translated_text, text_bbox, font_path, spec)
        layout_path = variant_dir / "text-layer.png"
        render_layout_preview(layout, font_path, layout_path, canvas_size=_bbox_size(text_bbox), vertical_align=spec.vertical_align)
        alignment = measure_preview_alignment(layout_path)
        crop_path = variant_dir / "final-crop.png"
        compose_variant_crop(cleaned_crop, layout_path, cleanup_bbox, text_bbox, crop_path)
        rows.append(
            {
                "variant": spec.name,
                "status": "ok",
                "elapsed_seconds": round(time.perf_counter() - started, 3),
                "spec": asdict(spec),
                "layout": {**asdict(layout), "alignment": alignment},
                "paths": {
                    "text_layer_path": str(layout_path),
                    "final_crop_path": str(crop_path),
                },
            }
        )
    return rows


def build_layout(
    translated_text: str,
    text_bbox: tuple[int, int, int, int],
    font_path: Path,
    spec: LayoutVariantSpec,
) -> LayoutResult:
    target_width, target_height = _bbox_size(text_bbox)
    measured = measure_text_layout(
        spec.line_breaks,
        font_path,
        spec.font_size,
        line_spacing=spec.line_spacing,
        orientation="vertical",
    )
    overflow = _overflow_ratio(measured.width, measured.height, target_width, target_height)
    return LayoutResult(
        status="ok" if overflow <= 0.08 else "failed",
        text=translated_text,
        line_breaks=spec.line_breaks,
        font_size=spec.font_size,
        orientation="vertical",
        line_spacing=spec.line_spacing,
        letter_spacing=0,
        angle_degrees=spec.angle_degrees,
        target_width=target_width,
        target_height=target_height,
        measured_width=measured.width,
        measured_height=measured.height,
        overflow_ratio=round(overflow, 4),
        failure_reason=None if overflow <= 0.08 else "overflow",
    )


def compose_variant_crop(
    cleaned_crop: Image.Image,
    text_layer_path: str | Path,
    cleanup_bbox: tuple[int, int, int, int],
    text_bbox: tuple[int, int, int, int],
    output_path: str | Path,
) -> Path:
    canvas = cleaned_crop.copy()
    overlay = Image.open(text_layer_path).convert("RGBA")
    canvas.paste(overlay, (text_bbox[0] - cleanup_bbox[0], text_bbox[1] - cleanup_bbox[1]), overlay)
    return _save_image(canvas, output_path)


def write_variant_grid(output_path: Path, rows: list[dict[str, Any]]) -> Path:
    tiles = [(row["variant"], row["paths"]["final_crop_path"]) for row in rows]
    return write_grid(output_path, tiles, near_square_columns(len(tiles)))


def run_mimo(run_dir: Path, grid_path: Path, rows: list[dict[str, Any]]) -> dict[str, Any]:
    client = MimoVisionClient(_mimo_config_from_env())
    prompt = _mimo_prompt(rows)
    result = client.analyze_image(
        grid_path,
        prompt,
        kind="phase4_layout_variant_grid",
        system_prompt="You judge manga lettering layouts from labeled comparison crops. Return only compact JSON.",
        max_completion_tokens=1600,
    )
    _write_json(run_dir / "reports" / "mimo-layout-variant-evaluation.json", result)
    return result


def _mimo_prompt(rows: list[dict[str, Any]]) -> str:
    variants = [
        {
            "variant": row["variant"],
            "font_size": row["spec"]["font_size"],
            "line_spacing": row["spec"]["line_spacing"],
            "line_breaks": row["spec"]["line_breaks"],
            "overflow_ratio": row["layout"]["overflow_ratio"],
            "ink_bbox": row["layout"]["alignment"]["ink_bbox"],
        }
        for row in rows
    ]
    return "\n".join(
        [
            "Compare these labeled crop candidates for one Japanese manga speech-bubble translation.",
            "The target is the first diamond announcer block only; ignore any unrelated appointment-style text.",
            "Choose natural vertical Chinese lettering for manga. It should be top-aligned, not vertically centered.",
            "Angle should stay 0 degrees; penalize any variant that looks rotated or slanted.",
            "The text must not cover the neighboring Japanese bubble text '今日が初ライブ!' or the bottom line art.",
            "Reject variants with overflow_ratio > 0.08 or ink_bbox visibly touching/clipping the bottom edge.",
            "Prefer readable text that is not too large, too bold, cramped, or awkwardly split across columns.",
            f"Variants JSON: {json.dumps(variants, ensure_ascii=False)}",
            "Return JSON with keys: best_variant, ranking, scores, unacceptable_variants, per_variant_notes, reasoning_summary.",
        ]
    )


def _load_record(path: Path, record_id: str, status: str) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            payload = json.loads(line)
            if payload.get("record_id") == record_id and payload.get("status") == status:
                return payload
    raise RuntimeError(f"record_not_found:{path}:{record_id}:{status}")


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
        base_url=os.environ["MIMO_BASE_URL"],
        api_key=os.environ["MIMO_API_KEY"],
        model=os.environ["MIMO_VISION_MODEL"],
        thinking_type="disabled",
    )


def _cleanup_crop_path(cleanup: dict) -> str:
    quality = cleanup.get("gpt_replacement_quality")
    if isinstance(quality, dict) and quality.get("accepted") is not True:
        return cleanup["cleaned_crop_path"]
    return cleanup.get("replacement_crop_path") or cleanup["cleaned_crop_path"]


def _resize_to_bbox(image_path: str | Path, bbox: tuple[int, int, int, int]) -> Image.Image:
    target_size = _bbox_size(bbox)
    with Image.open(image_path) as image:
        source = image.copy()
    if source.size == target_size:
        return source
    return source.resize(target_size)


def _bbox_size(bbox: tuple[int, int, int, int]) -> tuple[int, int]:
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def _overflow_ratio(width: int, height: int, target_width: int, target_height: int) -> float:
    width_over = max(0, width - target_width) / max(1, target_width)
    height_over = max(0, height - target_height) / max(1, target_height)
    return max(width_over, height_over)


def _save_image(image: Image.Image, path: str | Path) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output)
    return output


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
