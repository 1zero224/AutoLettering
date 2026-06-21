from __future__ import annotations

import json
from pathlib import Path

from .cleanup_runs import CleanupRunInput, format_cleanup_run_dirs, load_cleanup_rows_by_id
from .export.photoshop import build_photoshop_manifest, write_json, write_photoshop_import_jsx


def run_phase8_photoshop_export(
    detection_run_dir: str | Path,
    font_selection_run_dir: str | Path,
    layout_run_dir: str | Path,
    cleanup_run_dir: CleanupRunInput,
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
        cleanup_rows=load_cleanup_rows_by_id(cleanup_run_dir),
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
    cleanup_run_dir: CleanupRunInput,
    manifest: dict,
) -> None:
    cleanup_summary = _cleanup_summary(manifest)
    lines = [
        "# Phase 8 Photoshop Export Report",
        "",
        f"Detection run directory: `{detection_run_dir}`",
        f"Font selection run directory: `{font_selection_run_dir}`",
        f"Layout run directory: `{layout_run_dir}`",
        f"Cleanup run directories: {format_cleanup_run_dirs(cleanup_run_dir)}",
        "",
        "## Summary",
        "",
        f"- Pages exported: {manifest['summary']['page_count']}",
        f"- Text layers exported: {manifest['summary']['record_count']}",
        "",
        "## Cleanup Summary",
        "",
        f"- Missing cleanup layers: {cleanup_summary['missing_count']}",
        f"- Effective cleanup methods: {_format_counts(cleanup_summary['effective_methods'])}",
        "",
        "## JSX Behavior",
        "",
        "- Places `cleanup.effective_crop_path` as a bitmap patch layer when available.",
        "- Creates one editable Photoshop paragraph text layer per exported layer using the bbox width and height.",
        "",
        "## Generated Artifacts",
        "",
        "- `photoshop-manifest.json`",
        "- `photoshop-import.jsx`",
        "- `reports/phase8-report.md`",
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _cleanup_summary(manifest: dict) -> dict:
    missing_count = 0
    effective_methods: dict[str, int] = {}
    for page in manifest.get("pages", []):
        for layer in page.get("layers", []):
            cleanup = layer.get("cleanup", {})
            if cleanup.get("status") == "missing":
                missing_count += 1
            method = cleanup.get("effective_method")
            if method:
                effective_methods[method] = effective_methods.get(method, 0) + 1
    return {"missing_count": missing_count, "effective_methods": effective_methods}


def _format_counts(counts: dict[str, int]) -> str:
    if not counts:
        return "none"
    return ", ".join(f"`{key}={counts[key]}`" for key in sorted(counts))
