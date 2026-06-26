from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from autolettering.experiment_grid import near_square_columns, write_grid
from autolettering.phase6_gpt_artifact_gate import evaluate_gpt_replacement_artifacts, gpt_artifact_payload


def run_artifact_gate_experiment(
    run_dirs: list[str | Path],
    output_root: str | Path = "outputs/runs",
    run_id: str = "phase6-gpt-artifact-gate",
) -> Path:
    run_dir = Path(output_root) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    rows = [_evaluate_run(Path(item)) for item in run_dirs]
    _write_json(run_dir / "gpt-artifact-gate-results.json", {"records": rows})
    _write_grid(run_dir, rows)
    _write_report(run_dir / "reports" / "gpt-artifact-gate-report.md", rows)
    return run_dir


def _evaluate_run(run_dir: Path) -> dict:
    record_id = _record_id_from_quality(run_dir) or run_dir.name
    cleaned = _first_existing(run_dir / "fallback_cleaned")
    replacement = _first_existing(run_dir / "fallback_replacement_crop")
    result = evaluate_gpt_replacement_artifacts(cleaned, replacement)
    payload = gpt_artifact_payload(result)
    return {
        "run_dir": str(run_dir),
        "record_id": record_id,
        "cleaned_crop_path": str(cleaned) if cleaned else None,
        "replacement_crop_path": str(replacement) if replacement else None,
        **payload,
    }


def _record_id_from_quality(run_dir: Path) -> str | None:
    quality_path = run_dir / "replacement-quality.jsonl"
    if not quality_path.exists():
        return None
    for line in quality_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            return json.loads(line).get("record_id")
    return None


def _first_existing(directory: Path) -> Path | None:
    if not directory.exists():
        return None
    for path in sorted(directory.glob("*.png")):
        return path
    return None


def _write_grid(run_dir: Path, rows: list[dict]) -> None:
    tiles: list[tuple[str, str | Path]] = []
    for row in rows:
        label = _tile_label(row)
        for key, title in (
            ("cleaned_crop_path", "cleaned"),
            ("replacement_crop_path", "replacement"),
        ):
            path = row.get(key)
            if path:
                tiles.append((f"{label} {title}", path))
        replacement = row.get("replacement_crop_path")
        if replacement:
            overlay_path = _write_metric_overlay(run_dir, row, Path(replacement))
            tiles.append((f"{label} gate", overlay_path))
    if not tiles:
        return
    columns = near_square_columns(len(tiles))
    write_grid(run_dir / "visuals" / "gpt-artifact-gate-grid.png", tiles, columns=columns)


def _write_metric_overlay(run_dir: Path, row: dict, image_path: Path) -> Path:
    output_path = run_dir / "debug" / "gate_overlays" / f"{_safe_name(row['run_dir'])}.png"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(image_path) as image:
        canvas = image.convert("RGB")
    draw = ImageDraw.Draw(canvas)
    metrics = row.get("local_artifact_metrics") or {}
    bbox = metrics.get("largest_darken_component_bbox") or [0, 0, 0, 0]
    if bbox != [0, 0, 0, 0]:
        color = "red" if row.get("local_artifact_gate_passed") is False else "green"
        draw.rectangle(tuple(bbox), outline=color, width=3)
    canvas.save(output_path)
    return output_path


def _tile_label(row: dict) -> str:
    status = "PASS" if row.get("local_artifact_gate_passed") is not False else "FAIL"
    metrics = row.get("local_artifact_metrics") or {}
    ratio = metrics.get("largest_darken_component_area_ratio")
    ratio_text = "n/a" if ratio is None else f"{ratio:.3f}"
    return f"{Path(row['run_dir']).name}\n{status} area={ratio_text}"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_report(path: Path, rows: list[dict]) -> None:
    failed = [row for row in rows if row.get("local_artifact_gate_passed") is False]
    lines = [
        "# Phase 6 GPT Artifact Gate Report",
        "",
        "## Summary",
        "",
        f"- Runs evaluated: {len(rows)}",
        f"- Local artifact failures: {len(failed)}",
        "",
        "## Generated Artifacts",
        "",
        "- `gpt-artifact-gate-results.json`",
        "- `visuals/gpt-artifact-gate-grid.png`",
        "",
        "## Records",
        "",
    ]
    for row in rows:
        lines.append(
            f"- `{Path(row['run_dir']).name}`: passed={row.get('local_artifact_gate_passed')}, "
            f"issues={row.get('local_artifact_issues')}"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _safe_name(value: str) -> str:
    return "".join(char if char.isalnum() else "-" for char in value).strip("-") or "run"


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate local artifact gate for GPT replacement runs.")
    parser.add_argument("--run-dir", action="append", required=True, help="Phase 6 GPT replacement run directory.")
    parser.add_argument("--output-root", default="outputs/runs")
    parser.add_argument("--run-id", default="phase6-gpt-artifact-gate")
    args = parser.parse_args()
    run_artifact_gate_experiment(args.run_dir, args.output_root, args.run_id)


if __name__ == "__main__":
    main()
