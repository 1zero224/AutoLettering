from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path

from .inpaint.nonbubble import inpaint_nonbubble_text
from .models.gpt_image import GptImageConfig, GptImageEditClient, gpt_image_edit_prompt, gpt_image_request_summary


def run_phase6_nonbubble_cleanup(
    detection_run_dir: str | Path,
    output_root: str | Path = "outputs/runs",
    run_id: str | None = None,
    sample_limit: int = 5,
    gpt_config: GptImageConfig | None = None,
    call_gpt_image: bool = False,
) -> Path:
    run_dir = Path(output_root) / (run_id or "phase6-nonbubble-cleanup")
    run_dir.mkdir(parents=True, exist_ok=True)
    detections = _load_nonbubble_detections(Path(detection_run_dir) / "detections.jsonl", sample_limit)
    client = GptImageEditClient(gpt_config) if call_gpt_image and gpt_config else None
    rows = [_cleanup_one(run_dir, detection, gpt_config, client) for detection in detections]
    _write_jsonl(run_dir / "cleanup-results.jsonl", rows)
    _write_report(run_dir / "reports" / "phase6-nonbubble-report.md", detection_run_dir, rows)
    return run_dir


def _load_nonbubble_detections(path: Path, sample_limit: int) -> list[dict]:
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if len(rows) >= sample_limit:
                break
            payload = json.loads(line)
            if payload.get("status") == "ok" and payload.get("group_name") != "框内":
                rows.append(payload)
    return rows


def _cleanup_one(run_dir: Path, detection: dict, config: GptImageConfig | None, client: GptImageEditClient | None) -> dict:
    result = inpaint_nonbubble_text(
        image_path=detection["image_path"],
        bbox=tuple(detection["selected_text_box_xyxy"]),
        output_dir=run_dir / "crops",
        record_id=detection["record_id"],
    )
    prompt = gpt_image_edit_prompt(detection.get("translated_text", ""))
    return {
        "record_id": detection["record_id"],
        "image_name": detection.get("image_name"),
        "translated_text": detection.get("translated_text", ""),
        "status": "cleaned",
        "cleanup": _cleanup_payload(result),
        "gpt_image2_edit": _gpt_image_payload(run_dir, detection["record_id"], result, prompt, config, client),
    }


def _cleanup_payload(result) -> dict:
    payload = asdict(result)
    payload["bbox"] = list(result.bbox)
    for key in ("input_crop_path", "text_mask_path", "gpt_mask_path", "cleaned_crop_path", "before_after_path"):
        payload[key] = str(payload[key])
    return payload


def _gpt_image_payload(
    run_dir: Path,
    record_id: str,
    result,
    prompt: str,
    config: GptImageConfig | None,
    client: GptImageEditClient | None,
) -> dict:
    summary = gpt_image_request_summary(config, result.input_crop_path, result.gpt_mask_path, prompt)
    if client is None:
        return {"status": "dry_run", "request": summary, "failure_reason": None}
    try:
        output_path = run_dir / "gpt_image2" / f"{_safe_name(record_id)}.png"
        response = client.edit_image(result.input_crop_path, result.gpt_mask_path, prompt, output_path)
        return {"request": summary, **response}
    except Exception as exc:
        return {"status": "failed", "request": summary, "failure_reason": f"{type(exc).__name__}:{str(exc)[:500]}"}


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_report(output_path: Path, detection_run_dir: str | Path, rows: list[dict]) -> None:
    called = sum(1 for row in rows if row["gpt_image2_edit"]["status"] == "ok")
    lines = [
        "# Phase 6 Non-Bubble Cleanup Report",
        "",
        f"Detection run directory: `{detection_run_dir}`",
        "",
        "## Summary",
        "",
        f"- Records processed: {len(rows)}",
        f"- Local inpainted: {sum(1 for row in rows if row['status'] == 'cleaned')}",
        f"- GPT image calls: {called}",
        f"- GPT dry runs: {sum(1 for row in rows if row['gpt_image2_edit']['status'] == 'dry_run')}",
        f"- GPT failures: {sum(1 for row in rows if row['gpt_image2_edit']['status'] == 'failed')}",
        "",
        "## Generated Artifacts",
        "",
        "- `cleanup-results.jsonl`",
        "- `crops/input/*.png`",
        "- `crops/mask/*.png`",
        "- `crops/gpt_mask/*.png`",
        "- `crops/cleaned/*.png`",
        "- `crops/before_after/*.png`",
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _safe_name(value: str) -> str:
    return "".join(char if char.isalnum() else "-" for char in value).strip("-") or "record"
