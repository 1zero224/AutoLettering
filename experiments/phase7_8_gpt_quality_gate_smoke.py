from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from autolettering.phase7 import run_phase7_preview
from autolettering.phase8 import run_phase8_photoshop_export


def run_quality_gate_smoke(
    detection_run_dir: str | Path,
    cleanup_run_dir: str | Path,
    phase6_gpt_quality_run_dir: str | Path,
    output_root: str | Path = "outputs/runs",
    run_id: str | None = None,
    sample_limit: int = 1,
) -> Path:
    run_dir = Path(output_root) / (run_id or "phase7-8-gpt-quality-gate-smoke")
    run_dir.mkdir(parents=True, exist_ok=True)
    detections = _load_jsonl_by_id(Path(detection_run_dir) / "detections.jsonl")
    cleanups = _load_jsonl_by_id(Path(cleanup_run_dir) / "cleanup-results.jsonl")
    record_ids = list(cleanups)[:sample_limit]
    layout_run = _write_layout_stub(run_dir / "runs" / "phase4-layout-stub", record_ids, cleanups)
    font_run = _write_font_stub(run_dir / "runs" / "phase3-font-stub", record_ids)
    phase7_run = run_phase7_preview(
        detection_run_dir=detection_run_dir,
        cleanup_run_dir=cleanup_run_dir,
        layout_run_dir=layout_run,
        output_root=run_dir / "runs",
        run_id="phase7-preview",
        sample_limit=sample_limit,
        phase6_gpt_quality_run_dir=phase6_gpt_quality_run_dir,
    )
    phase8_run = run_phase8_photoshop_export(
        detection_run_dir=detection_run_dir,
        font_selection_run_dir=font_run,
        layout_run_dir=layout_run,
        cleanup_run_dir=cleanup_run_dir,
        output_root=run_dir / "runs",
        run_id="phase8-export",
        sample_limit=sample_limit,
        preview_run_dir=phase7_run,
        phase6_gpt_quality_run_dir=phase6_gpt_quality_run_dir,
    )
    summary = _summary(run_dir, phase7_run, phase8_run, detections, record_ids)
    _write_json(run_dir / "quality-gate-smoke-summary.json", summary)
    _write_report(run_dir / "reports" / "quality-gate-smoke-report.md", summary)
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a local Phase 7/8 GPT replacement quality-gate smoke using existing cleanup and quality runs."
    )
    parser.add_argument("--detection-run-dir", required=True)
    parser.add_argument("--cleanup-run-dir", required=True)
    parser.add_argument("--phase6-gpt-quality-run-dir", required=True)
    parser.add_argument("--output-root", default="outputs/runs")
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--sample-limit", type=int, default=1)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    run_dir = run_quality_gate_smoke(
        detection_run_dir=Path(args.detection_run_dir),
        cleanup_run_dir=Path(args.cleanup_run_dir),
        phase6_gpt_quality_run_dir=Path(args.phase6_gpt_quality_run_dir),
        output_root=Path(args.output_root),
        run_id=args.run_id,
        sample_limit=args.sample_limit,
    )
    print(run_dir)


def _write_layout_stub(run_dir: Path, record_ids: list[str], cleanups: dict[str, dict]) -> Path:
    rows = []
    for record_id in record_ids:
        cleanup = cleanups[record_id].get("cleanup") or {}
        bbox = cleanup.get("layout_text_bbox") or cleanup.get("text_bbox") or cleanup.get("bbox")
        preview_path = run_dir / "layout_previews" / f"{_safe_name(record_id)}.png"
        _write_transparent_preview(preview_path, bbox)
        rows.append(
            {
                "record_id": record_id,
                "status": "layout_generated",
                "layout": {
                    "preview_path": str(preview_path),
                    "line_breaks": "",
                    "font_size": 24,
                    "orientation": "horizontal",
                    "angle_degrees": 0.0,
                    "line_spacing": 0,
                    "letter_spacing": 0,
                    "target_bbox": bbox,
                    "vertical_align": "top",
                    "text_color": [0, 0, 0, 255],
                    "validation": {"status": "stub_for_quality_gate_smoke"},
                },
            }
        )
    _write_jsonl(run_dir / "layout-results.jsonl", rows)
    return run_dir


def _write_font_stub(run_dir: Path, record_ids: list[str]) -> Path:
    font_path = _fallback_font_path()
    rows = [
        {
            "record_id": record_id,
            "status": "selected",
            "selected_font_id": "stub-font",
            "selected_font": {
                "font_id": "stub-font",
                "path": str(font_path),
                "filename": font_path.name,
                "family_name": "StubFont",
                "postscript_name": "StubFont",
            },
            "confidence": 0.0,
        }
        for record_id in record_ids
    ]
    _write_jsonl(run_dir / "font-selections.jsonl", rows)
    return run_dir


def _summary(
    run_dir: Path,
    phase7_run: Path,
    phase8_run: Path,
    detections: dict[str, dict],
    record_ids: list[str],
) -> dict:
    phase7_rows = _load_jsonl(phase7_run / "preview-results.jsonl")
    phase8_manifest = json.loads((phase8_run / "photoshop-manifest.json").read_text(encoding="utf-8"))
    return {
        "schema_version": "autolettering.phase7_8_gpt_quality_gate_smoke.v1",
        "run_dir": str(run_dir),
        "phase7_run_dir": str(phase7_run),
        "phase8_run_dir": str(phase8_run),
        "records": [
            _record_summary(record_id, detections.get(record_id) or {}, phase7_rows, phase8_manifest)
            for record_id in record_ids
        ],
    }


def _record_summary(record_id: str, detection: dict, phase7_rows: list[dict], phase8_manifest: dict) -> dict:
    phase7_record = _phase7_record(record_id, phase7_rows)
    phase8_layer = _phase8_layer(record_id, phase8_manifest)
    phase8_source = _phase8_repair_source(record_id, phase8_manifest)
    quality = (phase7_record or {}).get("gpt_replacement_quality") or (phase8_source or {}).get("gpt_replacement_quality")
    return {
        "record_id": record_id,
        "image_name": detection.get("image_name"),
        "gpt_quality_accepted": quality.get("accepted") if isinstance(quality, dict) else None,
        "gpt_quality_failure_reason": quality.get("failure_reason") if isinstance(quality, dict) else None,
        "phase7_status": _phase7_status(record_id, phase7_rows),
        "phase7_cleanup_method": (phase7_record or {}).get("cleanup_method"),
        "phase7_cleanup_crop_path": (phase7_record or {}).get("cleanup_crop_path"),
        "phase7_text_overlay_required": (phase7_record or {}).get("text_overlay_required"),
        "phase8_text_layer_exported": phase8_layer is not None,
        "phase8_replacement_method": (phase8_layer or phase8_source or {}).get("replacement_method")
        or ((phase8_layer or {}).get("cleanup") or {}).get("replacement_method"),
        "phase8_effective_method": (phase8_layer or phase8_source or {}).get("effective_method")
        or ((phase8_layer or {}).get("cleanup") or {}).get("effective_method"),
        "phase8_effective_crop_path": (phase8_layer or phase8_source or {}).get("effective_crop_path")
        or ((phase8_layer or {}).get("cleanup") or {}).get("effective_crop_path"),
        "phase8_text_overlay_required": (phase8_source or {}).get("text_overlay_required"),
    }


def _phase7_status(record_id: str, rows: list[dict]) -> str | None:
    for row in rows:
        if any(record.get("record_id") == record_id for record in row.get("records", [])):
            return row.get("status")
        if row.get("record_id") == record_id:
            return row.get("status")
    return None


def _phase7_record(record_id: str, rows: list[dict]) -> dict | None:
    for row in rows:
        for record in row.get("records", []):
            if record.get("record_id") == record_id:
                return record
    return None


def _phase8_layer(record_id: str, manifest: dict) -> dict | None:
    for page in manifest.get("pages", []):
        for layer in page.get("layers", []):
            if layer.get("record_id") == record_id:
                return layer
    return None


def _phase8_repair_source(record_id: str, manifest: dict) -> dict | None:
    for page in manifest.get("pages", []):
        for source in page.get("repair_sources", []):
            if source.get("record_id") == record_id:
                return source
    return None


def _load_jsonl_by_id(path: Path) -> dict[str, dict]:
    return {row["record_id"]: row for row in _load_jsonl(path) if row.get("record_id")}


def _load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_report(path: Path, summary: dict) -> None:
    lines = [
        "# Phase 7/8 GPT Quality Gate Smoke",
        "",
        f"Phase 7 run: `{summary['phase7_run_dir']}`",
        f"Phase 8 run: `{summary['phase8_run_dir']}`",
        "",
        "## Records",
        "",
    ]
    for record in summary["records"]:
        lines.append(
            "- "
            f"{record['record_id']}: accepted={record['gpt_quality_accepted']}, "
            f"phase7_crop=`{record['phase7_cleanup_crop_path']}`, "
            f"phase8_crop=`{record['phase8_effective_crop_path']}`, "
            f"text_layer={record['phase8_text_layer_exported']}"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_transparent_preview(path: Path, bbox: list[int] | None) -> None:
    width = 1
    height = 1
    if isinstance(bbox, list) and len(bbox) == 4:
        width = max(1, int(bbox[2]) - int(bbox[0]))
        height = max(1, int(bbox[3]) - int(bbox[1]))
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", (width, height), (255, 255, 255, 0)).save(path)


def _fallback_font_path() -> Path:
    for name in ("msyh.ttc", "simsun.ttc", "arial.ttf"):
        path = Path("C:/Windows/Fonts") / name
        if path.exists():
            return path
    fonts = sorted(Path("C:/Windows/Fonts").glob("*.ttf"))
    if not fonts:
        raise RuntimeError("No fallback font found under C:/Windows/Fonts")
    return fonts[0]


def _safe_name(value: str) -> str:
    return "".join(char if char.isalnum() else "-" for char in value).strip("-") or "record"


if __name__ == "__main__":
    main()
