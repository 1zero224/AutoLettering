from __future__ import annotations

import json
from pathlib import Path

from .export.photoshop import build_photoshop_manifest, write_json, write_photoshop_import_jsx


def run_phase8_photoshop_export(
    detection_run_dir: str | Path,
    font_selection_run_dir: str | Path,
    layout_run_dir: str | Path,
    cleanup_run_dir: str | Path,
    output_root: str | Path = "outputs/runs",
    run_id: str | None = None,
    sample_limit: int = 5,
) -> Path:
    run_dir = Path(output_root) / (run_id or "phase8-photoshop-export")
    run_dir.mkdir(parents=True, exist_ok=True)
    manifest = build_photoshop_manifest(
        detection_rows=_load_jsonl_by_id(Path(detection_run_dir) / "detections.jsonl", "ok"),
        font_rows=_load_jsonl_by_id(Path(font_selection_run_dir) / "font-selections.jsonl", "selected"),
        layout_rows=_load_jsonl(Path(layout_run_dir) / "layout-results.jsonl", "layout_generated"),
        cleanup_rows=_load_jsonl_by_id(Path(cleanup_run_dir) / "cleanup-results.jsonl", "cleaned"),
        sample_limit=sample_limit,
    )
    write_json(run_dir / "photoshop-manifest.json", manifest)
    write_photoshop_import_jsx(run_dir / "photoshop-import.jsx")
    _write_report(
        run_dir / "reports" / "phase8-report.md",
        detection_run_dir,
        font_selection_run_dir,
        layout_run_dir,
        cleanup_run_dir,
        manifest,
    )
    return run_dir


def _load_jsonl(path: Path, status: str) -> list[dict]:
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            payload = json.loads(line)
            if payload.get("status") == status:
                rows.append(payload)
    return rows


def _load_jsonl_by_id(path: Path, status: str) -> dict[str, dict]:
    rows: dict[str, dict] = {}
    for payload in _load_jsonl(path, status):
        rows[payload["record_id"]] = payload
    return rows


def _write_report(
    output_path: Path,
    detection_run_dir: str | Path,
    font_selection_run_dir: str | Path,
    layout_run_dir: str | Path,
    cleanup_run_dir: str | Path,
    manifest: dict,
) -> None:
    lines = [
        "# Phase 8 Photoshop Export Report",
        "",
        f"Detection run directory: `{detection_run_dir}`",
        f"Font selection run directory: `{font_selection_run_dir}`",
        f"Layout run directory: `{layout_run_dir}`",
        f"Cleanup run directory: `{cleanup_run_dir}`",
        "",
        "## Summary",
        "",
        f"- Pages exported: {manifest['summary']['page_count']}",
        f"- Text layers exported: {manifest['summary']['record_count']}",
        "",
        "## Generated Artifacts",
        "",
        "- `photoshop-manifest.json`",
        "- `photoshop-import.jsx`",
        "- `reports/phase8-report.md`",
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
