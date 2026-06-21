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
    font_mapping_path: str | Path | None = None,
) -> Path:
    run_dir = Path(output_root) / (run_id or "phase8-photoshop-export")
    run_dir.mkdir(parents=True, exist_ok=True)
    font_mapping = _load_font_mapping(font_mapping_path)
    manifest = build_photoshop_manifest(
        detection_rows=_load_jsonl_by_id(Path(detection_run_dir) / "detections.jsonl", "ok"),
        font_rows=_load_jsonl_by_id(Path(font_selection_run_dir) / "font-selections.jsonl", "selected"),
        layout_rows=_load_jsonl(Path(layout_run_dir) / "layout-results.jsonl", "layout_generated"),
        cleanup_rows=load_cleanup_rows_by_id(cleanup_run_dir),
        sample_limit=sample_limit,
        font_mapping=font_mapping,
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
        font_mapping_path,
    )
    _write_photoshop_validation_checklist(run_dir / "reports" / "photoshop-validation-checklist.md", manifest, font_mapping_path)
    return run_dir


def _load_font_mapping(path: str | Path | None) -> dict[str, str]:
    if path is None:
        return {}
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return {str(key): str(value) for key, value in payload.items() if value}


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
    font_mapping_path: str | Path | None,
) -> None:
    cleanup_summary = _cleanup_summary(manifest)
    lines = [
        "# Phase 8 Photoshop Export Report",
        "",
        f"Detection run directory: `{detection_run_dir}`",
        f"Font selection run directory: `{font_selection_run_dir}`",
        f"Layout run directory: `{layout_run_dir}`",
        f"Cleanup run directories: {format_cleanup_run_dirs(cleanup_run_dir)}",
        f"Font mapping file: `{font_mapping_path}`" if font_mapping_path else "Font mapping file: none",
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
        "- Creates one editable Photoshop paragraph text layer per exported layer using `text_bbox` width, height, and position.",
        "- Keeps `bbox` for cleanup patch placement and `text_bbox` for editable text placement.",
        "- Maps `layout.line_spacing` to Photoshop leading and `layout.letter_spacing` to best-effort tracking.",
        "- Uses `font.photoshop_font_name` before falling back to `font.family_name`.",
        "- Can apply an optional JSON font mapping file before writing `font.photoshop_font_name`.",
        "",
        "## Generated Artifacts",
        "",
        "- `photoshop-manifest.json`",
        "- `photoshop-import.jsx`",
        "- `reports/phase8-report.md`",
        "- `reports/photoshop-validation-checklist.md`",
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_photoshop_validation_checklist(output_path: Path, manifest: dict, font_mapping_path: str | Path | None) -> None:
    summary = manifest["summary"]
    cleanup_patch_count = _cleanup_patch_count(manifest)
    lines = [
        "# Photoshop Validation Checklist",
        "",
        "## Run Steps",
        "",
        "1. Open Photoshop.",
        "2. Run `photoshop-import.jsx` from this export directory.",
        "3. Wait for the completion alert before inspecting saved PSD files.",
        "",
        "## Expected Output",
        "",
        "Expected PSD output folder: `psd/`",
        f"- Expected pages: {summary['page_count']}",
        f"- Expected editable text layers: {summary['record_count']}",
        f"- Expected cleanup patch layers: {cleanup_patch_count}",
        f"- Font mapping file: `{font_mapping_path}`" if font_mapping_path else "- Font mapping file: none",
        "",
        "## Manual Checks",
        "",
        "- Each PSD opens without missing image path errors.",
        "- Cleanup patch layers align with their detected text boxes.",
        "- Text layers remain editable paragraph text layers and align with `text_bbox`.",
        "- Fonts resolve to `font.photoshop_font_name` or an acceptable fallback from `font.font_name_candidates`.",
        "- Vertical, horizontal, rotation, leading, and tracking settings visually match the preview as closely as Photoshop permits.",
        "",
        "## Compatibility Notes",
        "",
        "- Photoshop was not executed by this pipeline; this checklist is the manual validation gate.",
        "- If a font does not resolve, copy the example font map and map the exported source name to the installed Photoshop font name.",
        "- If cleanup patch placement fails, the JSX should continue creating editable text layers.",
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _cleanup_patch_count(manifest: dict) -> int:
    count = 0
    for page in manifest.get("pages", []):
        for layer in page.get("layers", []):
            if layer.get("cleanup", {}).get("effective_crop_path"):
                count += 1
    return count


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
