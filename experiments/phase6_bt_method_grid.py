from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BT_ROOT = PROJECT_ROOT / "BallonsTranslator"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(BT_ROOT) not in sys.path:
    sys.path.insert(0, str(BT_ROOT))

from autolettering.models.mimo import MimoVisionClient, MimoVisionConfig
from autolettering.experiment_grid import near_square_columns
from autolettering.phase6 import _mask_bbox, _text_bbox
from autolettering.inpaint.nonbubble import build_text_mask, inpaint_crop


INPAINT_METHODS = [
    "opencv-tela",
    "patchmatch",
    "aot",
    "lama_mpe",
    "lama_large_512px",
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run BallonsTranslator detector and inpaint method grids.")
    parser.add_argument("--detection-run-dir", default="outputs/runs/phase2-gbc06-diverse-expansion-v2-color-light-text")
    parser.add_argument("--record-id", default="GBC06_18.png#3")
    parser.add_argument("--output-root", default="outputs/runs")
    parser.add_argument("--run-id", default="phase6-bt-method-grid-gbc06-18-v1")
    parser.add_argument("--detector", action="append", dest="detectors", default=None)
    parser.add_argument("--inpaint-method", action="append", dest="inpaint_methods", default=None)
    parser.add_argument("--skip-detection", action="store_true")
    parser.add_argument("--skip-inpaint", action="store_true")
    parser.add_argument("--skip-mimo", action="store_true")
    parser.add_argument("--env-file", default=".env")
    args = parser.parse_args()

    _load_env_file(Path(args.env_file))
    run_dir = Path(args.output_root) / args.run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    record = _load_record(Path(args.detection_run_dir), args.record_id)

    detector_records: list[dict[str, Any]] = []
    if not args.skip_detection:
        detector_records = _run_detectors(run_dir, record, args.detectors or ["ctd", "ysgyolo"])
    inpaint_records: list[dict[str, Any]] = []
    if not args.skip_inpaint:
        inpaint_records = _run_inpainters(run_dir, record, args.inpaint_methods or INPAINT_METHODS)

    detection_sheet = _write_detection_grid(run_dir, record, detector_records) if detector_records else None
    inpaint_sheet = _write_inpaint_grid(run_dir, record, inpaint_records) if inpaint_records else None
    mimo = {}
    if not args.skip_mimo:
        mimo = _run_mimo(run_dir, detection_sheet, inpaint_sheet, detector_records, inpaint_records)

    summary = {
        "record_id": args.record_id,
        "image_path": record["image_path"],
        "target_bbox": list(_text_bbox(record)),
        "mask_bbox": list(_mask_bbox(record)),
        "detectors": detector_records,
        "inpainters": inpaint_records,
        "sheets": {
            "detection": str(detection_sheet) if detection_sheet else None,
            "inpaint": str(inpaint_sheet) if inpaint_sheet else None,
        },
        "mimo": mimo,
    }
    _write_json(run_dir / "reports" / "bt-method-grid-summary.json", summary)
    _write_report(run_dir / "reports" / "bt-method-grid-report.md", summary)
    print(run_dir)


def _run_detectors(run_dir: Path, record: dict, detectors: list[str]) -> list[dict[str, Any]]:
    records = []
    for detector_name in detectors:
        started = time.perf_counter()
        try:
            mask, blocks = _detect_with_bt(detector_name, Path(record["image_path"]))
            elapsed = round(time.perf_counter() - started, 3)
            output_dir = run_dir / "detectors" / detector_name
            output_dir.mkdir(parents=True, exist_ok=True)
            mask_path = output_dir / "mask.png"
            overlay_path = output_dir / "overlay.png"
            cv2.imwrite(str(mask_path), mask)
            _write_detection_overlay(Path(record["image_path"]), blocks, mask, record, overlay_path)
            records.append(
                {
                    "method": detector_name,
                    "status": "ok",
                    "elapsed_seconds": elapsed,
                    "block_count": len(blocks),
                    "blocks": [_block_payload(block) for block in blocks],
                    "mask_path": str(mask_path),
                    "overlay_path": str(overlay_path),
                }
            )
        except Exception as exc:
            records.append(
                {
                    "method": detector_name,
                    "status": "failed",
                    "failure_reason": f"{type(exc).__name__}: {str(exc)[:500]}",
                }
            )
    return records


def _detect_with_bt(detector_name: str, image_path: Path):
    cwd = Path.cwd()
    os.chdir(BT_ROOT)
    try:
        if detector_name == "ctd":
            from ballontranslator.modules.textdetector.detector_ctd import ComicTextDetector

            detector = ComicTextDetector()
            detector.updateParam("device", "cpu")
            detector.updateParam("detect_size", 1024)
        elif detector_name == "ysgyolo":
            from ballontranslator.modules.textdetector.detector_ysg import YSGYoloDetector

            detector = YSGYoloDetector()
            detector.updateParam("device", "cpu")
            detector.updateParam("model path", "data/models/ysgyolo_1.2_OS1.0.pt")
            detector.updateParam("detect size", 1024)
        else:
            raise ValueError(f"unsupported_detector:{detector_name}")
        image = _read_cv_image(image_path)
        if image is None:
            raise RuntimeError(f"cannot_read_image:{image_path}")
        mask, blocks = detector.detect(image, None)
        return mask, blocks
    finally:
        os.chdir(cwd)


def _read_cv_image(image_path: Path) -> np.ndarray | None:
    payload = np.fromfile(str(image_path), dtype=np.uint8)
    if payload.size == 0:
        return None
    return cv2.imdecode(payload, cv2.IMREAD_COLOR)


def _run_inpainters(run_dir: Path, record: dict, methods: list[str]) -> list[dict[str, Any]]:
    records = []
    image_path = Path(record["image_path"])
    target_bbox = _text_bbox(record)
    mask_bbox = _mask_bbox(record)
    with Image.open(image_path) as image:
        source = image.convert("RGB")
    crop = source.crop(target_bbox)
    local_mask = _local_text_mask(source, target_bbox, mask_bbox)
    input_dir = run_dir / "inpaint" / "_input"
    input_dir.mkdir(parents=True, exist_ok=True)
    crop_path = input_dir / "original-crop.png"
    mask_path = input_dir / "tight-text-mask.png"
    crop.save(crop_path)
    local_mask.save(mask_path)

    for method in methods:
        started = time.perf_counter()
        method_label = _canonical_inpaint_method(method)
        output_dir = run_dir / "inpaint" / method_label
        output_dir.mkdir(parents=True, exist_ok=True)
        try:
            routed_method, cleaned = _inpaint_with_method(crop, local_mask, method)
            elapsed = round(time.perf_counter() - started, 3)
            cleaned_path = output_dir / "cleaned.png"
            before_after_path = output_dir / "before-after.png"
            cleaned.save(cleaned_path)
            _save_before_after(crop, cleaned, before_after_path)
            records.append(
                {
                    "method": method_label,
                    "routed_method": routed_method,
                    "status": "ok",
                    "elapsed_seconds": elapsed,
                    "input_crop_path": str(crop_path),
                    "mask_path": str(mask_path),
                    "cleaned_path": str(cleaned_path),
                    "before_after_path": str(before_after_path),
                }
            )
        except Exception as exc:
            records.append(
                {
                    "method": method_label,
                    "status": "failed",
                    "failure_reason": f"{type(exc).__name__}: {str(exc)[:500]}",
                    "input_crop_path": str(crop_path),
                    "mask_path": str(mask_path),
                }
            )
    return records


def _canonical_inpaint_method(method: str) -> str:
    if method == "opencv_tela":
        return "opencv-tela"
    return method


def _inpaint_with_method(crop: Image.Image, mask: Image.Image, method: str) -> tuple[str, Image.Image]:
    if method in {"opencv-tela", "opencv_tela"}:
        return "bt_opencv-tela_actual_cv2_INPAINT_NS", _opencv_tela_bt(crop, mask)
    if method == "patchmatch":
        return inpaint_crop(crop, mask, "bt_patchmatch")
    if method == "aot":
        return inpaint_crop(crop, mask, "bt_aot")
    if method == "lama_mpe":
        return "lama_mpe_inpaint", _lama_mpe_inpaint(crop, mask)
    if method == "lama_large_512px":
        return inpaint_crop(crop, mask, "bt_lama_large")
    raise ValueError(f"unsupported_inpaint_method:{method}")


def _opencv_tela_bt(crop: Image.Image, mask: Image.Image) -> Image.Image:
    image_array = np.array(crop.convert("RGB"), dtype=np.uint8)
    mask_array = np.array(mask.convert("L"), dtype=np.uint8)
    result = cv2.inpaint(image_array, mask_array, 3, cv2.INPAINT_NS)
    return Image.fromarray(result, mode="RGB")


def _lama_mpe_inpaint(crop: Image.Image, mask: Image.Image) -> Image.Image:
    from autolettering.inpaint.balloons import _load_balloons_inpaint_module, _balloons_root, _lama_large_tensors, _lama_large_output, _require_cv2, _require_torch

    bt_root = _balloons_root()
    model_path = bt_root / "data" / "models" / "lama_mpe.ckpt"
    if not model_path.exists():
        _download_file("https://huggingface.co/dreMaz/mit_models/resolve/main/lama_mpe.ckpt", model_path)
    module = _load_balloons_inpaint_module(bt_root, "lama")
    cwd = Path.cwd()
    os.chdir(bt_root)
    try:
        model = module.load_lama_mpe(str(model_path), "cpu", use_mpe=True, large_arch=False)
    finally:
        os.chdir(cwd)
    cv2_mod = _require_cv2()
    torch = _require_torch()
    original = np.array(crop.convert("RGB"), dtype=np.uint8)
    mask_array = np.array(mask.convert("L"), dtype=np.uint8) >= 127
    img_t, mask_t, padded_shape = _lama_large_tensors(original, mask_array, cv2_mod, torch)
    rel_pos, _, direct = model.load_masked_position_encoding(mask_t.cpu().squeeze(0).squeeze(0).numpy())
    rel_pos_t = torch.LongTensor(rel_pos).unsqueeze(0)
    direct_t = torch.LongTensor(direct).unsqueeze(0)
    with torch.no_grad():
        output_t = model(img_t, mask_t, rel_pos_t, direct_t)
    output = _lama_large_output(output_t, original.shape, padded_shape, cv2_mod)
    keep = (~mask_array)[:, :, None].astype(np.uint8)
    fill = mask_array[:, :, None].astype(np.uint8)
    return Image.fromarray((output * fill + original * keep).astype(np.uint8), mode="RGB")


def _local_text_mask(source: Image.Image, target_bbox: tuple[int, int, int, int], mask_bbox: tuple[int, int, int, int]) -> Image.Image:
    crop = source.crop(target_bbox)
    local_mask = Image.new("L", crop.size, 0)
    text_crop = source.crop(mask_bbox)
    text_mask = build_text_mask(text_crop, dark_threshold=185, dilate_px=3, polarity="dark_on_light")
    local_mask.paste(text_mask, (mask_bbox[0] - target_bbox[0], mask_bbox[1] - target_bbox[1]))
    return local_mask


def _write_detection_overlay(image_path: Path, blocks: list, mask: np.ndarray, record: dict, output_path: Path) -> None:
    with Image.open(image_path) as image:
        canvas = image.convert("RGB")
    target = _crop_context_bbox(_text_bbox(record), canvas.size)
    crop = canvas.crop(target)
    draw = ImageDraw.Draw(crop)
    tx1, ty1 = target[:2]
    target_bbox = _offset_bbox(_text_bbox(record), target)
    mask_bbox = _offset_bbox(_mask_bbox(record), target)
    draw.rectangle(target_bbox, outline=(255, 0, 0), width=4)
    draw.rectangle(mask_bbox, outline=(0, 160, 255), width=3)
    for index, block in enumerate(blocks):
        bbox = tuple(int(value) for value in block.xyxy)
        if not _intersects(bbox, target):
            continue
        local = _offset_bbox(bbox, target)
        draw.rectangle(local, outline=(0, 180, 0), width=3)
        draw.text((local[0] + 2, local[1] + 2), str(index), fill=(0, 120, 0), font=ImageFont.load_default())
    mask_crop = Image.fromarray(mask).convert("L").crop(target)
    mask_rgb = Image.merge("RGB", [Image.new("L", mask_crop.size, 255), Image.new("L", mask_crop.size, 230), Image.new("L", mask_crop.size, 230)])
    overlay = Image.blend(crop, Image.composite(mask_rgb, crop, mask_crop.point(lambda value: min(100, value))), 0.35)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    overlay.save(output_path)


def _write_detection_grid(run_dir: Path, record: dict, records: list[dict[str, Any]]) -> Path:
    output = run_dir / "visuals" / "detector-grid.png"
    tiles = [("current-phase2", _current_detector_tile(run_dir, record))]
    for item in records:
        if item["status"] == "ok":
            tiles.append((item["method"], item["overlay_path"]))
        else:
            tiles.append((f"{item['method']} failed", None))
    return _write_grid(output, tiles, columns=near_square_columns(len(tiles), cell_width=370, cell_height=334))


def _write_inpaint_grid(run_dir: Path, record: dict, records: list[dict[str, Any]]) -> Path:
    output = run_dir / "visuals" / "inpaint-grid.png"
    input_path = next((item.get("input_crop_path") for item in records if item.get("input_crop_path")), None)
    mask_path = next((item.get("mask_path") for item in records if item.get("mask_path")), None)
    tiles = [("original", input_path), ("tight mask", mask_path)]
    for item in records:
        tiles.append((item["method"] if item["status"] == "ok" else f"{item['method']} failed", item.get("cleaned_path")))
    return _write_grid(output, tiles, columns=near_square_columns(len(tiles), cell_width=370, cell_height=334))


def _current_detector_tile(run_dir: Path, record: dict) -> Path:
    with Image.open(record["image_path"]) as image:
        canvas = image.convert("RGB")
    target = _crop_context_bbox(_text_bbox(record), canvas.size)
    crop = canvas.crop(target)
    draw = ImageDraw.Draw(crop)
    draw.rectangle(_offset_bbox(_text_bbox(record), target), outline=(255, 0, 0), width=4)
    draw.rectangle(_offset_bbox(_mask_bbox(record), target), outline=(0, 160, 255), width=3)
    output = run_dir / "detectors" / "current-phase2" / "overlay.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    crop.save(output)
    return output


def _write_grid(output_path: Path, tiles: list[tuple[str, str | Path | None]], columns: int) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    font = ImageFont.load_default()
    loaded = []
    for label, path in tiles:
        if path and Path(path).exists():
            image = Image.open(path).convert("RGB")
        else:
            image = Image.new("RGB", (320, 260), (245, 245, 245))
            ImageDraw.Draw(image).text((12, 12), "no output", fill=(80, 80, 80), font=font)
        loaded.append((label, image))
    columns = max(1, columns)
    rows = int(np.ceil(len(loaded) / columns))
    tile_w, tile_h, label_h, pad = 360, 300, 24, 10
    sheet = Image.new("RGB", (pad + columns * (tile_w + pad), pad + rows * (tile_h + label_h + pad)), "white")
    draw = ImageDraw.Draw(sheet)
    for index, (label, image) in enumerate(loaded):
        col = index % columns
        row = index // columns
        x = pad + col * (tile_w + pad)
        y = pad + row * (tile_h + label_h + pad)
        draw.rectangle((x, y, x + tile_w, y + label_h), fill=(245, 245, 245), outline=(180, 180, 180))
        draw.text((x + 4, y + 6), label[:44], fill="black", font=font)
        thumb = image.copy()
        thumb.thumbnail((tile_w, tile_h), Image.Resampling.LANCZOS)
        draw.rectangle((x, y + label_h, x + tile_w, y + label_h + tile_h), outline=(210, 210, 210), fill="white")
        sheet.paste(thumb, (x + (tile_w - thumb.width) // 2, y + label_h + (tile_h - thumb.height) // 2))
    sheet.save(output_path)
    return output_path


def _run_mimo(run_dir: Path, detection_sheet: Path | None, inpaint_sheet: Path | None, detectors: list[dict], inpainters: list[dict]) -> dict[str, Any]:
    missing = [name for name in ["MIMO_BASE_URL", "MIMO_API_KEY", "MIMO_VISION_MODEL"] if not os.environ.get(name)]
    if missing:
        return {"status": "unavailable", "reason": f"missing env: {', '.join(missing)}"}
    client = MimoVisionClient(
        MimoVisionConfig(
            base_url=os.environ["MIMO_BASE_URL"],
            api_key=os.environ["MIMO_API_KEY"],
            model=os.environ["MIMO_VISION_MODEL"],
            thinking_type="disabled",
            max_completion_tokens=1200,
        )
    )
    results: dict[str, Any] = {"status": "ok"}
    if detection_sheet:
        prompt = "\n".join(
            [
                "Evaluate this near-square manga text detection comparison grid.",
                "Red rectangle is the current target cleanup/layout bbox. Blue rectangle is the tighter mask bbox currently derived from Phase 2 candidates. Green boxes are BallonsTranslator detector blocks.",
                "Judge whether each detector finds the Japanese text region for the target record without merging unrelated neighbor speech bubbles or background art.",
                f"Detector methods: {json.dumps([item['method'] for item in detectors], ensure_ascii=False)}",
                "Return only JSON with keys best_detector, scores, unacceptable_methods, per_method_notes, reasoning_summary, caveats.",
            ]
        )
        results["detection"] = client.analyze_image(detection_sheet, prompt, kind="bt_detector_grid", max_completion_tokens=1200)
        _write_json(run_dir / "reports" / "mimo-detector-grid.json", results["detection"])
    if inpaint_sheet:
        prompt = "\n".join(
            [
                "Evaluate this near-square manga text cleanup/inpainting comparison grid.",
                "The first tile is original crop and the second tile is the tight text mask. Other tiles are cleanup outputs.",
                "Score whether Japanese text is removed, the left neighbor speech-bubble text is preserved, the bottom line art/halftone is preserved, and no obvious white rectangle or gray dirt remains.",
                "Do not require Chinese translated text to appear; this is cleanup-only.",
                f"Inpaint methods: {json.dumps([item['method'] for item in inpainters], ensure_ascii=False)}",
                "Return only JSON with keys best_inpaint_method, ranking, scores, unacceptable_methods, per_method_notes, reasoning_summary, caveats.",
            ]
        )
        results["inpaint"] = client.analyze_image(inpaint_sheet, prompt, kind="bt_inpaint_grid", max_completion_tokens=1200)
        _write_json(run_dir / "reports" / "mimo-inpaint-grid.json", results["inpaint"])
    return results


def _load_record(detection_run_dir: Path, record_id: str) -> dict:
    with (detection_run_dir / "detections.jsonl").open("r", encoding="utf-8") as handle:
        for line in handle:
            payload = json.loads(line)
            if payload.get("record_id") == record_id:
                return payload
    raise SystemExit(f"missing_record:{record_id}")


def _block_payload(block: Any) -> dict[str, Any]:
    return {
        "xyxy": [int(value) for value in block.xyxy],
        "vertical": bool(block.vertical),
        "font_size": float(block.font_size) if block.font_size is not None else None,
        "angle": int(block.angle) if block.angle is not None else None,
        "label": getattr(block, "label", None),
    }


def _crop_context_bbox(bbox: tuple[int, int, int, int], image_size: tuple[int, int], padding: int = 180) -> tuple[int, int, int, int]:
    width, height = image_size
    return max(0, bbox[0] - padding), max(0, bbox[1] - padding), min(width, bbox[2] + padding), min(height, bbox[3] + padding)


def _offset_bbox(bbox: tuple[int, int, int, int], outer: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    return bbox[0] - outer[0], bbox[1] - outer[1], bbox[2] - outer[0], bbox[3] - outer[1]


def _intersects(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> bool:
    return min(a[2], b[2]) > max(a[0], b[0]) and min(a[3], b[3]) > max(a[1], b[1])


def _save_before_after(before: Image.Image, after: Image.Image, path: Path) -> None:
    canvas = Image.new("RGB", (before.width + after.width, max(before.height, after.height)), "white")
    canvas.paste(before.convert("RGB"), (0, 0))
    canvas.paste(after.convert("RGB"), (before.width, 0))
    canvas.save(path)


def _download_file(url: str, path: Path) -> None:
    import urllib.request

    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size > 1024:
        return
    urllib.request.urlretrieve(url, path)


def _write_report(path: Path, summary: dict[str, Any]) -> None:
    lines = [
        "# BallonsTranslator Method Grid",
        "",
        f"Record: `{summary['record_id']}`",
        f"Image: `{summary['image_path']}`",
        f"Target bbox: `{summary['target_bbox']}`",
        f"Mask bbox: `{summary['mask_bbox']}`",
        "",
        "## Sheets",
        "",
        f"- Detection grid: `{summary['sheets']['detection']}`",
        f"- Inpaint grid: `{summary['sheets']['inpaint']}`",
        "",
        "## Detector Status",
        "",
        *[f"- `{item['method']}`: `{item['status']}` {item.get('failure_reason', '')}" for item in summary["detectors"]],
        "",
        "## Inpaint Status",
        "",
        *[f"- `{item['method']}`: `{item['status']}` {item.get('failure_reason', '')}" for item in summary["inpainters"]],
        "",
        "Note: BallonsTranslator registers this OpenCV method as `opencv-tela`, but its implementation calls `cv2.INPAINT_NS`.",
        "",
        "## MIMO",
        "",
        "```json",
        json.dumps(_mimo_brief(summary.get("mimo", {})), ensure_ascii=False, indent=2),
        "```",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _mimo_brief(mimo: dict[str, Any]) -> dict[str, Any]:
    brief = {"status": mimo.get("status")}
    for key in ("detection", "inpaint"):
        if isinstance(mimo.get(key), dict):
            brief[key] = {
                "raw_text": mimo[key].get("raw_text"),
                "response": mimo[key].get("response"),
            }
    if "reason" in mimo:
        brief["reason"] = mimo["reason"]
    return brief


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


if __name__ == "__main__":
    main()
