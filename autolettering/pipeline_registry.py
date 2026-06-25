from __future__ import annotations

import json
from pathlib import Path
from typing import Any


PIPELINE_REGISTRY_SCHEMA_VERSION = "autolettering.pipeline_registry.v1"


RUN_DIR_FIELDS = (
    "detection_run_dir",
    "font_selection_run_dir",
    "layout_run_dir",
    "angle_run_dir",
    "cleanup_run_dirs",
    "preview_run_dir",
    "export_run_dir",
    "phase6_cleanup_quality_run_dir",
    "phase6_gpt_quality_run_dir",
    "phase7_preview_evaluation_run_dir",
    "phase8_export_audit_run_dir",
)


REQUIRED_ARTIFACTS_BY_FIELD = {
    "phase1_run_dir": ("manifest.json",),
    "detection_run_dir": ("detections.jsonl",),
    "font_selection_run_dir": ("font-selections.jsonl",),
    "layout_run_dir": ("layout-results.jsonl",),
    "angle_run_dir": ("angle-results.jsonl",),
    "cleanup_run_dirs": ("cleanup-results.jsonl",),
    "preview_run_dir": ("preview-results.jsonl",),
    "export_run_dir": ("photoshop-manifest.json",),
    "phase6_cleanup_quality_run_dir": ("cleanup-quality.jsonl",),
    "phase6_gpt_quality_run_dir": ("manifest.json",),
    "phase7_preview_evaluation_run_dir": ("preview-evaluation.jsonl",),
    "phase8_export_audit_run_dir": ("phase8-export-audit.json",),
}


class PipelineRegistryValidationError(ValueError):
    """Raised when a registry entry points at missing pipeline artifacts."""


def load_pipeline_registry_entry(
    registry_path: str | Path,
    entry_name: str,
    *,
    validate: bool = False,
) -> dict[str, Any]:
    path = Path(registry_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    _validate_schema(payload)
    entries = payload.get("entries", {})
    if entry_name not in entries:
        available = ", ".join(sorted(entries))
        raise KeyError(f"pipeline_registry_entry_not_found:{entry_name}; available={available}")
    entry = dict(entries[entry_name])
    entry.setdefault("schema_version", payload.get("schema_version"))
    base_dir = (path.parent / payload.get("base_dir", ".")).resolve()
    normalized = _normalize_entry_paths(entry, base_dir)
    if validate:
        validate_pipeline_registry_entry(normalized)
    return normalized


def validate_pipeline_registry_entry(entry: dict[str, Any]) -> None:
    missing: list[str] = []
    for field, artifacts in REQUIRED_ARTIFACTS_BY_FIELD.items():
        paths = _entry_paths(entry, field)
        for run_dir in paths:
            for artifact in artifacts:
                artifact_path = run_dir / artifact
                if not artifact_path.exists():
                    missing.append(f"{field}: {artifact_path}")
    if missing:
        details = "\n".join(f"- {item}" for item in missing)
        raise PipelineRegistryValidationError(f"pipeline_registry_missing_artifacts:\n{details}")


def _normalize_entry_paths(entry: dict[str, Any], base_dir: Path) -> dict[str, Any]:
    normalized = dict(entry)
    if normalized.get("phase1_run_dir"):
        normalized["phase1_run_dir"] = _resolve_path(base_dir, normalized["phase1_run_dir"])
    for field in RUN_DIR_FIELDS:
        if field not in normalized:
            continue
        normalized[field] = [_resolve_path(base_dir, item) for item in _as_list(normalized[field])]
    return normalized


def _resolve_path(base_dir: Path, value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return (base_dir / path).resolve()


def _validate_schema(payload: dict[str, Any]) -> None:
    schema_version = payload.get("schema_version")
    if schema_version != PIPELINE_REGISTRY_SCHEMA_VERSION:
        raise ValueError(
            "pipeline_registry_schema_version_mismatch:"
            f" expected={PIPELINE_REGISTRY_SCHEMA_VERSION}; actual={schema_version}"
        )


def _entry_paths(entry: dict[str, Any], field: str) -> list[Path]:
    if field == "phase1_run_dir":
        value = entry.get(field)
        return [value] if isinstance(value, Path) else []
    return [item for item in _as_list(entry.get(field)) if isinstance(item, Path)]


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]
