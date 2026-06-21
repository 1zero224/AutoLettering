from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

from PIL import Image

from .assets.font_comparison import build_font_comparison_grid
from .assets.font_render import render_text_preview
from .assets.fonts import FontRecord, font_record_to_dict, scan_font_directory, select_font_candidates
from .labelplus.parser import parse_labelplus_project
from .record_selection import normalize_record_ids, row_matches_record_ids


def run_phase3(
    labelplus_file: str | Path,
    detection_run_dir: str | Path,
    font_dir: str | Path,
    output_root: str | Path = "outputs/runs",
    run_id: str | None = None,
    sample_limit: int = 10,
    font_limit: int = 12,
    record_ids: Iterable[str] | None = None,
) -> Path:
    parse_labelplus_project(labelplus_file)
    run_dir = Path(output_root) / (run_id or "phase3-font-comparison")
    run_dir.mkdir(parents=True, exist_ok=True)

    detections = _load_detections(Path(detection_run_dir) / "detections.jsonl", sample_limit, record_ids)
    fonts = scan_font_directory(font_dir, sample_text=_sample_text(detections))
    candidate_fonts = select_font_candidates(fonts, font_limit)
    _write_font_index(run_dir / "font-index.jsonl", fonts)
    rows = _write_comparisons(run_dir, detections, candidate_fonts)
    _write_report(
        run_dir / "reports" / "phase3-report.md",
        labelplus_file,
        font_dir,
        len(rows),
        len(fonts),
        len(candidate_fonts),
    )
    return run_dir


def _load_detections(path: Path, sample_limit: int, record_ids: Iterable[str] | None = None) -> list[dict]:
    wanted = normalize_record_ids(record_ids)
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if len(rows) >= sample_limit:
                break
            payload = json.loads(line)
            if (
                row_matches_record_ids(payload, wanted)
                and payload.get("status") == "ok"
                and payload.get("selected_text_box_xyxy")
            ):
                rows.append(payload)
    return rows


def _sample_text(detections: list[dict]) -> str:
    return "".join(str(item.get("translated_text", "")) for item in detections)


def _write_font_index(path: Path, fonts: list[FontRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for font in fonts:
            handle.write(json.dumps(font_record_to_dict(font), ensure_ascii=False) + "\n")


def _write_comparisons(run_dir: Path, detections: list[dict], fonts: list[FontRecord]) -> list[dict]:
    rows: list[dict] = []
    with (run_dir / "font-comparisons.jsonl").open("w", encoding="utf-8", newline="\n") as handle:
        for detection in detections:
            row = _build_comparison(run_dir, detection, fonts)
            rows.append(row)
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    return rows


def _build_comparison(run_dir: Path, detection: dict, fonts: list[FontRecord]) -> dict:
    record_id = str(detection["record_id"])
    safe_record_id = _safe_name(record_id)
    crop_path = run_dir / "crops" / "source_text" / f"{safe_record_id}.png"
    _crop_source_text(detection["image_path"], detection["selected_text_box_xyxy"], crop_path)
    candidate_rows = _render_candidates(run_dir, safe_record_id, str(detection.get("translated_text", "")), fonts)
    comparison_path = run_dir / "debug" / "font_comparison" / f"{safe_record_id}.png"
    build_font_comparison_grid(
        crop_path,
        [(row["font_id"], row["preview_path"]) for row in candidate_rows],
        comparison_path,
    )
    return _comparison_row(detection, crop_path, comparison_path, candidate_rows)


def _crop_source_text(image_path: str, bbox: list[int], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(image_path) as image:
        image.convert("RGB").crop(tuple(bbox)).save(output_path)


def _render_candidates(run_dir: Path, record_id: str, text: str, fonts: list[FontRecord]) -> list[dict]:
    rows: list[dict] = []
    for font in fonts:
        preview_path = run_dir / "crops" / "rendered_text" / record_id / f"{font.font_id}.png"
        render_text_preview(font, text, preview_path)
        row = font_record_to_dict(font)
        row["preview_path"] = str(preview_path)
        rows.append(row)
    return rows


def _comparison_row(
    detection: dict,
    crop_path: Path,
    comparison_path: Path,
    candidates: list[dict],
) -> dict:
    return {
        "record_id": detection["record_id"],
        "image_name": detection.get("image_name"),
        "translated_text": detection.get("translated_text", ""),
        "group_name": detection.get("group_name"),
        "status": "candidates_generated" if candidates else "no_candidate_fonts",
        "source_crop_path": str(crop_path),
        "comparison_image_path": str(comparison_path),
        "candidate_fonts": candidates,
        "selected_font": None,
        "model_reasoning_summary": None,
        "confidence": None,
    }


def _write_report(
    output_path: Path,
    labelplus_file: str | Path,
    font_dir: str | Path,
    rows: int,
    indexed_fonts: int,
    candidate_fonts: int,
) -> None:
    lines = [
        "# Phase 3 Font Comparison Report",
        "",
        f"LabelPlus file: `{labelplus_file}`",
        f"Font directory: `{font_dir}`",
        "",
        "## Summary",
        "",
        f"- Records with comparison grids: {rows}",
        f"- Indexed fonts: {indexed_fonts}",
        f"- Candidate fonts per record: {candidate_fonts}",
        "",
        "## Generated Artifacts",
        "",
        "- `font-index.jsonl`",
        "- `font-comparisons.jsonl`",
        "- `crops/source_text/*.png`",
        "- `crops/rendered_text/*/*.png`",
        "- `debug/font_comparison/*.png`",
        "",
        "## Interpretation",
        "",
        "This phase generates deterministic font candidates and visual comparison grids.",
        "It does not call a vision model yet and does not claim final font selection.",
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _safe_name(value: str) -> str:
    return "".join(char if char.isalnum() else "-" for char in value).strip("-") or "record"
