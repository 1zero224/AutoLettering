from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PIL import Image, ImageDraw, ImageFont

from autolettering.layout.models import LayoutResult
from autolettering.layout.render_text import render_layout_preview
from autolettering.models.mimo import MimoVisionClient, MimoVisionConfig


SHEET_BG = (255, 255, 255, 255)
TITLE_BG = (245, 245, 245, 255)
TITLE_BORDER = (200, 200, 200, 255)
TITLE_TEXT = (0, 0, 0, 255)
FOOTER_H = 52


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare vertical_column_order=rtl/ltr for a single GBC06 record."
    )
    parser.add_argument(
        "--layout-run-dir",
        default="outputs/runs/phase4-gbc06-batch-14-15-layout-v2",
        help="Input phase4 layout run dir containing layout-results.jsonl",
    )
    parser.add_argument(
        "--font-run-dir",
        default="outputs/runs/phase3-gbc06-batch-14-15-17-mimo-font-selection",
        help="Input phase3 font-selection run dir containing font-selections.jsonl",
    )
    parser.add_argument(
        "--cleaned-crop",
        default="outputs/runs/phase6-gbc06-batch-14-15-region-fill-v2/crops/cleaned/GBC06-01-png-14.png",
        help="Input cleaned crop image path",
    )
    parser.add_argument(
        "--before-after-crop",
        default="outputs/runs/phase7-8-gbc06-batch-14-15-preview-v5/runs/phase7-preview/crops/before_after/GBC06-01-png-14.png",
        help="Input before/after reference image path",
    )
    parser.add_argument(
        "--record-id",
        default="GBC06_01.png#14",
        help="Target record_id",
    )
    parser.add_argument(
        "--expected-text",
        default="昴也好\n仁菜也好",
        help="Expected translated text used for experiment reference",
    )
    parser.add_argument(
        "--output-root",
        default="outputs/runs",
        help="Output root directory",
    )
    parser.add_argument(
        "--run-id",
        default="phase4-gbc06-01-14-vertical-column-order-v1",
        help="Run directory name under output-root",
    )
    parser.add_argument("--env-file", default=".env", help="Load environment variables from this file")
    parser.add_argument(
        "--skip-mimo",
        action="store_true",
        help="Skip MIMO run even when env credentials exist",
    )
    args = parser.parse_args()

    run_dir = Path(args.output_root) / args.run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    load_env_file(Path(args.env_file))

    input_data = collect_inputs(
        layout_run_dir=Path(args.layout_run_dir),
        font_run_dir=Path(args.font_run_dir),
        record_id=args.record_id,
    )
    clean_output = _ensure_output_image(Path(args.cleaned_crop))
    before_after_output = _ensure_output_image(Path(args.before_after_crop))

    layout = input_data["layout"]
    font_path = input_data["font_path"]
    translated_text = input_data["translated_text"]

    expected_matches = translated_text == args.expected_text

    rtl_render = run_dir / "debug" / "render" / f"{safe_name(args.record_id)}-rtl.png"
    ltr_render = run_dir / "debug" / "render" / f"{safe_name(args.record_id)}-ltr.png"
    render_layout_preview(layout, font_path, rtl_render, canvas_size=(layout.target_width, layout.target_height), vertical_column_order="rtl")
    render_layout_preview(layout, font_path, ltr_render, canvas_size=(layout.target_width, layout.target_height), vertical_column_order="ltr")

    rtl_overlay = run_dir / "debug" / "overlay" / f"{safe_name(args.record_id)}-rtl-on-cleaned.png"
    ltr_overlay = run_dir / "debug" / "overlay" / f"{safe_name(args.record_id)}-ltr-on-cleaned.png"
    make_text_overlay(clean_output, rtl_render, rtl_overlay)
    make_text_overlay(clean_output, ltr_render, ltr_overlay)

    comparison_path = run_dir / "debug" / "comparison" / f"{safe_name(args.record_id)}-vertical-column-order-comparison.png"
    comparison_path.parent.mkdir(parents=True, exist_ok=True)
    comparison_path = write_comparison_sheet(
        output_path=comparison_path,
        before_after_path=before_after_output,
        cleaned_path=clean_output,
        rtl_render_path=rtl_render,
        rtl_overlay_path=rtl_overlay,
        ltr_render_path=ltr_render,
        ltr_overlay_path=ltr_overlay,
        record_id=args.record_id,
    )

    mimo_result = evaluate_mimo_or_record_reason(
        run_dir=run_dir,
        comparison_path=comparison_path,
        record_id=args.record_id,
        translated_text=translated_text,
        skip_mimo=args.skip_mimo,
    )

    result = {
        "run_id": args.run_id,
        "record_id": args.record_id,
        "expected_text": args.expected_text,
        "translated_text_in_data": translated_text,
        "translated_text_matches_expected": expected_matches,
        "inputs": {
            "layout_run_dir": str(Path(args.layout_run_dir)),
            "font_run_dir": str(Path(args.font_run_dir)),
            "cleaned_crop_path": str(clean_output),
            "before_after_crop_path": str(before_after_output),
        },
        "outputs": {
            "rtl_render_path": str(rtl_render),
            "ltr_render_path": str(ltr_render),
            "rtl_overlay_path": str(rtl_overlay),
            "ltr_overlay_path": str(ltr_overlay),
            "comparison_path": str(comparison_path),
        },
        "mimo": mimo_result,
    }
    write_jsonl_run_result(run_dir / "reports" / "vertical-column-order-comparison-result.json", result)
    print(json.dumps({"run_dir": str(run_dir), "comparison_path": str(comparison_path), "record_id": args.record_id}, ensure_ascii=False))


def collect_inputs(layout_run_dir: Path, font_run_dir: Path, record_id: str) -> dict[str, Any]:
    layout_row = find_record(layout_run_dir / "layout-results.jsonl", record_id)
    font_row = find_record(font_run_dir / "font-selections.jsonl", record_id)
    if layout_row is None:
        raise SystemExit(f"layout record not found in {layout_run_dir / 'layout-results.jsonl'}")
    if font_row is None:
        raise SystemExit(f"font selection record not found in {font_run_dir / 'font-selections.jsonl'}")

    layout_payload = layout_row.get("layout", {})
    filtered_layout = {
        key: layout_payload.get(key)
        for key in [
            "status",
            "text",
            "line_breaks",
            "font_size",
            "orientation",
            "line_spacing",
            "letter_spacing",
            "angle_degrees",
            "target_width",
            "target_height",
            "measured_width",
            "measured_height",
            "overflow_ratio",
            "failure_reason",
        ]
    }
    layout = LayoutResult(**filtered_layout)
    selected_font = font_row.get("selected_font")
    if not isinstance(selected_font, dict) or not selected_font.get("path"):
        raise SystemExit(f"selected_font.path is missing for record={record_id} in {font_run_dir / 'font-selections.jsonl'}")
    font_path = Path(selected_font["path"])
    if not font_path.exists():
        raise SystemExit(f"selected font path does not exist for record={record_id}: {font_path}")

    return {
        "layout": layout,
        "font_path": font_path,
        "font_id": font_row.get("selected_font_id"),
        "translated_text": str(layout_row.get("translated_text", "")),
        "layout_status": str(layout_row.get("status", "")),
    }


def find_record(path: Path, record_id: str) -> dict | None:
    if not path.exists():
        raise SystemExit(f"Input jsonl not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            if str(row.get("record_id")) == record_id:
                return row
    return None


def _ensure_output_image(path: Path) -> Path:
    if not path.exists():
        raise SystemExit(f"required image not found: {path}")
    with Image.open(path) as image:
        image.verify()
    return path


def make_text_overlay(cleaned_path: Path, text_render_path: Path, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(cleaned_path) as cleaned_src:
        cleaned = cleaned_src.convert("RGBA")
    with Image.open(text_render_path) as text_src:
        text_overlay = text_src.convert("RGBA")
    if cleaned.size != text_overlay.size:
        text_overlay = text_overlay.resize(cleaned.size)
    composite = cleaned.copy()
    composite.alpha_composite(text_overlay, dest=(0, 0))
    composite.convert("RGB").save(output_path)
    return output_path


def write_comparison_sheet(
    output_path: Path,
    before_after_path: Path,
    cleaned_path: Path,
    rtl_render_path: Path,
    rtl_overlay_path: Path,
    ltr_render_path: Path,
    ltr_overlay_path: Path,
    record_id: str,
) -> Path:
    tiles = [
        ("before-after 参考（原图|渲染）", before_after_path),
        ("cleaned base", cleaned_path),
        ("RTL 渲染（透明文字图）", rtl_render_path),
        ("RTL overlay（叠加到 cleaned）", rtl_overlay_path),
        ("LTR 渲染（透明文字图）", ltr_render_path),
        ("LTR overlay（叠加到 cleaned）", ltr_overlay_path),
    ]
    loaded: list[tuple[str, Image.Image]] = []
    for label, path in tiles:
        with Image.open(path) as image:
            loaded.append((label, image.convert("RGBA") if path == ltr_render_path or path == rtl_render_path else image.convert("RGB").convert("RGBA")))

    scale = 4
    pad = 12
    header_h = 34
    label_font = load_label_font()
    max_w = max(image.width for _, image in loaded)
    max_h = max(image.height for _, image in loaded)
    columns = 3
    rows = (len(loaded) + columns - 1) // columns
    tile_w = max_w * scale + 2
    tile_h = max_h * scale + 2
    width = pad + columns * (tile_w + pad)
    height = pad + rows * (tile_h + header_h + pad) + FOOTER_H

    sheet = Image.new("RGBA", (width, height), SHEET_BG)
    draw = ImageDraw.Draw(sheet)

    x = pad
    y = pad
    for index, (label, image) in enumerate(loaded):
        if index and index % columns == 0:
            y += header_h + tile_h + pad
            x = pad
        draw.rectangle((x, y, x + tile_w, y + header_h), fill=TITLE_BG, outline=TITLE_BORDER)
        draw.text((x + 6, y + 9), f"{index + 1}. {label}", fill=TITLE_TEXT, font=label_font)

        scaled = image.resize((image.width * scale, image.height * scale), Image.Resampling.NEAREST).convert("RGBA")
        bg = Image.new("RGBA", (tile_w, tile_h), (255, 255, 255, 255))
        x_off = (tile_w - scaled.width) // 2
        y_off = (tile_h - scaled.height) // 2
        bg.paste(scaled, (max(0, x_off), max(0, y_off)))
        sheet.alpha_composite(bg, (x, y + header_h))
        x += tile_w + pad

    footer = [
        f"Record: {record_id}",
        "Legend: 透明文字图=文字底图(带 alpha)，overlay=与 cleaned 合成图",
        "RTL/LTR 仅改变竖排列顺序，不改变字形和字号",
    ]
    footer_y = height - FOOTER_H + 6
    for index, item in enumerate(footer):
        draw.text((10, footer_y + index * 15), item, fill=(30, 30, 30, 255), font=label_font)

    sheet.convert("RGB").save(output_path)
    return output_path


def load_label_font() -> ImageFont.ImageFont:
    candidates = [
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("C:/Windows/Fonts/simsun.ttc"),
    ]
    for path in candidates:
        if path.exists():
            return ImageFont.truetype(str(path), 14)
    return ImageFont.load_default()


def evaluate_mimo_or_record_reason(
    run_dir: Path,
    comparison_path: Path,
    record_id: str,
    translated_text: str,
    skip_mimo: bool = False,
) -> dict[str, Any]:
    if skip_mimo:
        return {
            "status": "skipped",
            "reason": "skip_mimo flag enabled",
            "request": None,
            "response": None,
        }

    missing = [name for name in ["MIMO_BASE_URL", "MIMO_API_KEY", "MIMO_VISION_MODEL"] if not os.environ.get(name)]
    if missing:
        return {
            "status": "unavailable",
            "reason": f"missing environment variables: {', '.join(missing)}",
            "request": None,
            "response": None,
        }

    client = MimoVisionClient(
        MimoVisionConfig(
            base_url=os.environ["MIMO_BASE_URL"],
            api_key=os.environ["MIMO_API_KEY"],
            model=os.environ["MIMO_VISION_MODEL"],
            thinking_type="disabled",
        )
    )

    prompt = "\n".join(
        [
            "你是漫画嵌字视觉评审助手。",
            "请评估这张对照图里竖排中文文本渲染在两种列顺序（RTL/LTR）下的差异。",
            "请重点判断：",
            "1) 人眼可读性与字形连贯性；",
            "2) 每幅图中列的左右顺序是否符合中文漫画常见竖排阅读习惯（阅读顺序从右到左）；",
            "3) 与左侧 before-after 参考在版面自然度、边界齐整与留白感受的接近程度；",
            "4) 是否出现明显倒序/错位导致的阅读跳动。",
            f"已知翻译文本（用于语义一致性检查，不作为硬校验）：{translated_text}",
            f"Record: {record_id}",
            "返回仅 JSON，字段需包含：best_order（值为 rtl 或 ltr）、readability_score、naturalness_score、order_error_notes、localization_fit。",
        ]
    )

    try:
        response = client.analyze_image(
            comparison_path,
            prompt,
            kind="phase4_vertical_column_order_comparison",
            max_completion_tokens=800,
        )
        result = {
            "status": "ok",
            "request": response.get("request"),
            "response": response.get("response"),
            "raw_text": response.get("raw_text"),
        }
        (run_dir / "reports").mkdir(parents=True, exist_ok=True)
        (run_dir / "reports" / "vertical-column-order-mimo-eval.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return result
    except Exception as exc:
        reason = f"{type(exc).__name__}: {exc}"
        return {
            "status": "failed",
            "reason": reason,
            "request": None,
            "response": None,
        }


def write_jsonl_run_result(output_path: Path, payload: dict[str, Any]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        name, value = stripped.split("=", 1)
        os.environ.setdefault(name.strip(), value.strip().strip('"').strip("'"))


def safe_name(value: str) -> str:
    return "".join(ch if ch.isalnum() else "-" for ch in value).strip("-") or "record"


if __name__ == "__main__":
    main()
