from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from .labelplus.debug_draw import draw_label_point_pages
from .labelplus.manifest import project_manifest_to_dict, write_project_manifest
from .labelplus.models import ManifestImage, ManifestLabel, ProjectManifest
from .labelplus.parser import parse_labelplus_project


def run_phase1(
    labelplus_file: str | Path,
    output_root: str | Path = "outputs/runs",
    run_id: str | None = None,
    sample_limit: int = 30,
) -> Path:
    manifest = parse_labelplus_project(labelplus_file)
    run_dir = Path(output_root) / (run_id or _timestamp_run_id())

    write_project_manifest(manifest, run_dir / "manifest.json")
    draw_label_point_pages(manifest, run_dir / "debug" / "label_points")
    _write_sample_records(manifest, run_dir / "samples" / "phase1-sample.jsonl", sample_limit)
    _write_report(manifest, run_dir / "reports" / "phase1-report.md")

    return run_dir


def _timestamp_run_id() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S-phase1")


def _write_sample_records(manifest: ProjectManifest, output_path: Path, sample_limit: int) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    selected = _select_sample_records(manifest, sample_limit)
    with output_path.open("w", encoding="utf-8", newline="\n") as handle:
        for image, label in selected:
            payload = {
                "record_id": label.id,
                "image_name": image.image_name,
                "image_path": str(image.image_path),
                **asdict(label),
            }
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _select_sample_records(
    manifest: ProjectManifest,
    sample_limit: int,
) -> list[tuple[ManifestImage, ManifestLabel]]:
    if sample_limit <= 0:
        return []

    records: list[tuple[ManifestImage, ManifestLabel]] = []
    by_group: dict[int, tuple[ManifestImage, ManifestLabel]] = {}
    for image in manifest.images:
        for label in image.labels:
            by_group.setdefault(label.group_id, (image, label))
            records.append((image, label))

    selected: list[tuple[ManifestImage, ManifestLabel]] = []
    seen: set[str] = set()
    for group_id in sorted(by_group):
        image, label = by_group[group_id]
        selected.append((image, label))
        seen.add(label.id)
        if len(selected) >= sample_limit:
            return selected

    for image, label in records:
        if label.id in seen:
            continue
        selected.append((image, label))
        if len(selected) >= sample_limit:
            break
    return selected


def _write_report(manifest: ProjectManifest, output_path: Path) -> None:
    data = project_manifest_to_dict(manifest)
    summary = data["summary"]
    total_missing_labels = sum(image.label_count for image in manifest.missing_images)
    total_labels = summary["label_count"] + total_missing_labels

    lines = [
        "# Phase 1 Parse Report",
        "",
        f"LabelPlus file: `{manifest.labelplus_file}`",
        f"Project root: `{manifest.project_root}`",
        "",
        "## Summary",
        "",
        f"- Groups: {', '.join(manifest.groups)}",
        f"- Available images: {summary['available_image_count']}",
        f"- Missing images: {summary['missing_image_count']}",
        f"- Labels on available images: {summary['label_count']}",
        f"- Labels on missing images: {total_missing_labels}",
        f"- Total labels declared: {total_labels}",
        "",
        "## Missing Images",
        "",
    ]

    if manifest.missing_images:
        for missing in manifest.missing_images:
            lines.append(
                f"- `{missing.image_name}`: page {missing.page_index}, "
                f"{missing.label_count} labels, {missing.reason}"
            )
    else:
        lines.append("- None")

    lines.extend(
        [
            "",
            "## Generated Artifacts",
            "",
            "- `manifest.json`",
            "- `debug/label_points/*.png`",
            "- `samples/phase1-sample.jsonl`",
        ]
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

