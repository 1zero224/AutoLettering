from __future__ import annotations

from dataclasses import fields
import json
from pathlib import Path
from typing import Protocol

from PIL import Image

from .layout.models import LayoutResult
from .layout.render_text import render_layout_preview
from .models.mimo import parse_font_selection_response
from .phase3_context_font_artifacts import (
    CONTEXT_FONT_SCHEMA_VERSION,
    api_call_row,
    failed_api_call,
    failed_row,
    load_rows,
    result_row,
    rows_by_record,
    selection_output_row,
    selection_payload,
    skipped_api_call,
    write_jsonl,
    write_manifest,
    write_report,
)
from .phase3_context_font_candidates import context_candidates
from .phase3_context_font_review import write_context_font_grid
from .review_tiles import write_segmented_review_tile


class ContextFontSelectionClient(Protocol):
    def analyze_image(
        self,
        image_path: str | Path,
        prompt: str,
        kind: str = "image_analysis",
        max_completion_tokens: int | None = None,
    ) -> dict:
        ...


def run_phase3_context_font_selection(
    font_comparison_run_dir: str | Path,
    layout_run_dir: str | Path,
    cleanup_run_dir: str | Path,
    output_root: str | Path = "outputs/runs",
    run_id: str | None = None,
    sample_limit: int = 1,
    record_ids: list[str] | None = None,
    client: ContextFontSelectionClient | None = None,
    font_dir: str | Path | None = None,
    candidate_limit: int = 16,
) -> Path:
    run_dir = Path(output_root) / (run_id or "phase3-context-font-selection")
    run_dir.mkdir(parents=True, exist_ok=True)
    font_run = Path(font_comparison_run_dir)
    layout_run = Path(layout_run_dir)
    cleanup_run = Path(cleanup_run_dir)
    comparison_rows = load_rows(font_run / "font-comparisons.jsonl", sample_limit, record_ids, "candidates_generated")
    layouts = rows_by_record(layout_run / "layout-results.jsonl", status="layout_generated")
    cleanups = rows_by_record(cleanup_run / "cleanup-results.jsonl", status="cleaned")
    rows: list[dict] = []
    api_calls: list[dict] = []
    for comparison in comparison_rows:
        row, api_call = _process_one(
            run_dir,
            comparison,
            layouts.get(str(comparison.get("record_id"))),
            cleanups.get(str(comparison.get("record_id"))),
            font_dir,
            candidate_limit,
            client,
        )
        rows.append(row)
        api_calls.append(api_call)
    selections = [selection_output_row(row) for row in rows]
    write_jsonl(run_dir / "context-font-results.jsonl", rows)
    write_jsonl(run_dir / "font-selections.jsonl", selections)
    write_jsonl(run_dir / "reports" / "api-calls.jsonl", api_calls)
    write_manifest(run_dir / "manifest.json", font_run, layout_run, cleanup_run, rows)
    write_report(run_dir / "reports" / "phase3-context-font-selection-report.md", font_run, layout_run, cleanup_run, rows)
    return run_dir


def _process_one(
    run_dir: Path,
    comparison: dict,
    layout_row: dict | None,
    cleanup_row: dict | None,
    font_dir: str | Path | None,
    candidate_limit: int,
    client: ContextFontSelectionClient | None,
) -> tuple[dict, dict]:
    if layout_row is None:
        return failed_row(comparison, "layout_row_not_found"), skipped_api_call(comparison, "layout_row_not_found")
    if cleanup_row is None:
        return failed_row(comparison, "cleanup_row_not_found"), skipped_api_call(comparison, "cleanup_row_not_found")
    layout_payload = layout_row.get("layout") or {}
    cleanup = cleanup_row.get("cleanup") or {}
    layout = _layout_from_payload(layout_payload)
    text_color = tuple(layout_payload.get("text_color") or [0, 0, 0, 255])
    vertical_align = layout_payload.get("vertical_align")
    candidates = context_candidates(comparison, font_dir, candidate_limit)
    rendered = [
        _render_context_candidate(run_dir, comparison, candidate, layout, cleanup, text_color, vertical_align)
        for candidate in candidates
    ]
    source_crop = _resolve_path(cleanup.get("input_crop_path") or comparison.get("source_crop_path"))
    grid_path = write_context_font_grid(run_dir, comparison, rendered, source_crop)
    prompt = _context_font_prompt(comparison, rendered)
    if client is None:
        selected = rendered[0]["font_id"] if rendered else None
        result = selection_payload(
            "dry_run",
            selected,
            0.0,
            "dry run fallback to first rendered candidate",
            "dry_run",
            "context_font_fallback",
        )
        return result_row(comparison, result, rendered, grid_path, None), skipped_api_call(comparison, "dry_run", prompt, grid_path)
    try:
        response = client.analyze_image(
            grid_path,
            prompt,
            kind="phase3_context_font_selection",
            max_completion_tokens=1024,
        )
        parsed = parse_font_selection_response(response["raw_text"], [item["font_id"] for item in rendered])
        if parsed.status == "selected":
            result = selection_payload(
                parsed.status,
                parsed.selected_font_id,
                parsed.confidence,
                parsed.reasoning_summary,
                None,
                "mimo_context_font",
            )
        else:
            selected = rendered[0]["font_id"] if rendered else None
            result = selection_payload(
                "selected",
                selected,
                0.0,
                f"deterministic fallback after model failure: {parsed.failure_reason}",
                parsed.failure_reason,
                "context_font_fallback",
            )
        return result_row(comparison, result, rendered, grid_path, response["raw_text"]), api_call_row(comparison, response)
    except Exception as exc:
        selected = rendered[0]["font_id"] if rendered else None
        result = selection_payload(
            "selected",
            selected,
            0.0,
            f"deterministic fallback after model failure: api_error:{type(exc).__name__}",
            f"api_error:{type(exc).__name__}",
            "context_font_fallback",
        )
        return result_row(comparison, result, rendered, grid_path, None), failed_api_call(comparison, exc, prompt, grid_path)


def _render_context_candidate(
    run_dir: Path,
    comparison: dict,
    candidate: dict,
    layout: LayoutResult,
    cleanup: dict,
    text_color: tuple[int, int, int, int],
    vertical_align: str | None,
) -> dict:
    record_safe = _safe_name(str(comparison["record_id"]))
    font_id = str(candidate["font_id"])
    overlay_path = run_dir / "overlays" / record_safe / f"{font_id}.png"
    crop_path = run_dir / "context_crops" / record_safe / f"{font_id}.png"
    review_path = run_dir / "review_context_tiles" / record_safe / f"{font_id}.png"
    render_layout_preview(
        layout,
        candidate["path"],
        overlay_path,
        canvas_size=(layout.target_width, layout.target_height),
        text_color=text_color,
        vertical_align=vertical_align,
    )
    background_path = _resolve_path(cleanup.get("cleaned_crop_path") or cleanup.get("input_crop_path"))
    if background_path is None:
        raise FileNotFoundError("context_background_crop_not_found")
    crop_path.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(background_path) as background, Image.open(overlay_path) as overlay:
        canvas = background.convert("RGB").resize((layout.target_width, layout.target_height))
        rgba = overlay.convert("RGBA")
        canvas.paste(rgba, (0, 0), rgba)
    canvas.save(crop_path)
    write_segmented_review_tile(crop_path, review_path)
    payload = dict(candidate)
    payload["overlay_path"] = str(overlay_path)
    payload["context_crop_path"] = str(crop_path)
    payload["review_context_path"] = str(review_path)
    return payload


def _context_font_prompt(comparison: dict, rendered: list[dict]) -> str:
    candidates = [
        {
            "font_id": item["font_id"],
            "filename": item.get("filename"),
            "family_name": item.get("family_name"),
            "style_hints": item.get("style_hints", []),
        }
        for item in rendered
    ]
    return "\n".join(
        [
            "Choose the best Chinese font for this final manga lettering preview.",
            "The sheet contains one SOURCE original red banner tile plus candidate Chinese renderings on the repaired red banner.",
            "Each tall banner tile is enlarged by splitting it into ordered TOP/MIDDLE/BOTTOM segments; judge all segments as one continuous candidate.",
            "Choose only from the candidate font_id values, never choose SOURCE.",
            "Judge source-style similarity first: bold white manga banner lettering, rounded/POP feel, stroke weight, compactness, readability, and fit inside the red strip.",
            "Do not reward a font just because the translation is readable; penalize stiff, overly formal, thin, or border-colliding lettering.",
            f"Translated text: {comparison.get('translated_text', '')}",
            f"Candidates JSON: {json.dumps(candidates, ensure_ascii=False)}",
            "Return only JSON with keys: selected_font_id, confidence, reasoning_summary.",
        ]
    )


def _layout_from_payload(payload: dict) -> LayoutResult:
    keys = {field.name for field in fields(LayoutResult)}
    return LayoutResult(**{key: payload[key] for key in keys if key in payload})


def _resolve_path(value: object) -> Path | None:
    if not value:
        return None
    path = Path(str(value))
    candidates = [path] if path.is_absolute() else [path, Path.cwd() / path]
    return next((candidate for candidate in candidates if candidate.exists()), None)


def _safe_name(value: str) -> str:
    return "".join(char if char.isalnum() else "-" for char in value).strip("-") or "record"
