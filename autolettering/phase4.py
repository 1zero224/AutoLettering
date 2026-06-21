from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path

from PIL import Image

from .layout.measure import search_fitting_layout
from .layout.render_text import render_layout_preview


def run_phase4(
    selection_run_dir: str | Path,
    output_root: str | Path = "outputs/runs",
    run_id: str | None = None,
    sample_limit: int = 5,
) -> Path:
    run_dir = Path(output_root) / (run_id or "phase4-layout-search")
    run_dir.mkdir(parents=True, exist_ok=True)
    selections = _load_selected_fonts(Path(selection_run_dir) / "font-selections.jsonl", sample_limit)
    rows = [_layout_record(run_dir, row) for row in selections]
    _write_jsonl(run_dir / "layout-results.jsonl", rows)
    _write_report(run_dir / "reports" / "phase4-report.md", selection_run_dir, rows)
    return run_dir


def _load_selected_fonts(path: Path, sample_limit: int) -> list[dict]:
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if len(rows) >= sample_limit:
                break
            payload = json.loads(line)
            if payload.get("status") == "selected" and payload.get("selected_font"):
                rows.append(payload)
    return rows


def _layout_record(run_dir: Path, row: dict) -> dict:
    font_path = Path(row["selected_font"]["path"])
    target_size = _target_size_from_comparison(row)
    layout = search_fitting_layout(row.get("translated_text", ""), font_path, target_size)
    preview_path = run_dir / "debug" / "layout_candidates" / f"{_safe_name(row['record_id'])}.png"
    render_layout_preview(layout, font_path, preview_path, canvas_size=target_size)
    return {
        "record_id": row["record_id"],
        "image_name": row.get("image_name"),
        "translated_text": row.get("translated_text", ""),
        "status": "layout_generated" if layout.status == "ok" else "layout_failed",
        "selected_font_id": row.get("selected_font_id"),
        "layout": _layout_payload(layout, preview_path),
    }


def _target_size_from_comparison(row: dict) -> tuple[int, int]:
    source_crop_path = row.get("source_crop_path")
    if source_crop_path and Path(source_crop_path).exists():
        with Image.open(source_crop_path) as image:
            return image.size

    comparison_path = row.get("comparison_image_path")
    if comparison_path and Path(comparison_path).exists():
        with Image.open(comparison_path) as image:
            return max(80, image.width // 8), max(60, image.height // 3)
    return 180, 120


def _layout_payload(layout, preview_path: Path) -> dict:
    payload = asdict(layout)
    payload["preview_path"] = str(preview_path)
    payload["validation"] = {
        "status": "deterministic_only",
        "checks": ["measured_text_bbox", "bounded_overflow"],
        "model_summary": None,
        "manual_review_required": True,
    }
    return payload


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_report(output_path: Path, selection_run_dir: str | Path, rows: list[dict]) -> None:
    generated = sum(1 for row in rows if row["status"] == "layout_generated")
    lines = [
        "# Phase 4 Layout Search Report",
        "",
        f"Selection run directory: `{selection_run_dir}`",
        "",
        "## Summary",
        "",
        f"- Records processed: {len(rows)}",
        f"- Layouts generated: {generated}",
        f"- Layout failures: {len(rows) - generated}",
        "",
        "## Generated Artifacts",
        "",
        "- `layout-results.jsonl`",
        "- `debug/layout_candidates/*.png`",
        "- `reports/phase4-report.md`",
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _safe_name(value: str) -> str:
    return "".join(char if char.isalnum() else "-" for char in value).strip("-") or "record"
