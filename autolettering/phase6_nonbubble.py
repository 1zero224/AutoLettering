from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path

from .inpaint.nonbubble import inpaint_nonbubble_text
from .models.gpt_image import (
    GptImageConfig,
    GptImageEditClient,
    gpt_image_edit_prompt,
    gpt_image_request_summary,
    normalize_gpt_output_to_crop,
)
from .text_bbox import selected_text_polarity
from .text_body_bbox import selected_text_body_bbox


def run_phase6_nonbubble_cleanup(
    detection_run_dir: str | Path,
    output_root: str | Path = "outputs/runs",
    run_id: str | None = None,
    sample_limit: int = 5,
    record_ids: list[str] | None = None,
    gpt_config: GptImageConfig | None = None,
    call_gpt_image: bool = False,
    inpaint_method: str = "bt_lama_large",
) -> Path:
    run_dir = Path(output_root) / (run_id or "phase6-nonbubble-cleanup")
    run_dir.mkdir(parents=True, exist_ok=True)
    detections = _load_nonbubble_detections(Path(detection_run_dir) / "detections.jsonl", sample_limit, record_ids)
    client = GptImageEditClient(gpt_config) if call_gpt_image and gpt_config else None
    rows = [_cleanup_one(run_dir, detection, gpt_config, client, inpaint_method) for detection in detections]
    _write_jsonl(run_dir / "cleanup-results.jsonl", rows)
    _write_report(run_dir / "reports" / "phase6-nonbubble-report.md", detection_run_dir, rows)
    return run_dir


def _load_nonbubble_detections(path: Path, sample_limit: int, record_ids: list[str] | None = None) -> list[dict]:
    wanted = set(record_ids or [])
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if len(rows) >= sample_limit:
                break
            payload = json.loads(line)
            if wanted and payload.get("record_id") not in wanted:
                continue
            if payload.get("status") == "ok" and payload.get("group_name") != "框内":
                rows.append(payload)
    return rows


def _cleanup_one(
    run_dir: Path,
    detection: dict,
    config: GptImageConfig | None,
    client: GptImageEditClient | None,
    inpaint_method: str,
) -> dict:
    bbox = selected_text_body_bbox(detection)
    result = inpaint_nonbubble_text(
        image_path=detection["image_path"],
        bbox=bbox,
        output_dir=run_dir / "crops",
        record_id=detection["record_id"],
        method=inpaint_method,
        polarity=selected_text_polarity(detection, bbox),
    )
    prompt = gpt_image_edit_prompt(detection.get("translated_text", ""))
    cleanup = _cleanup_payload(result)
    gpt_payload = _gpt_image_payload(run_dir, detection["record_id"], result, prompt, config, client)
    _apply_gpt_replacement(cleanup, gpt_payload)
    return {
        "record_id": detection["record_id"],
        "image_name": detection.get("image_name"),
        "translated_text": detection.get("translated_text", ""),
        "status": "cleaned",
        "cleanup": cleanup,
        "gpt_image2_edit": gpt_payload,
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
        normalized = normalize_gpt_output_to_crop(
            response["output_path"],
            _crop_size(result.bbox),
            run_dir / "gpt_image2_normalized" / f"{_safe_name(record_id)}.png",
        )
        return {"request": summary, **response, **normalized}
    except Exception as exc:
        return {"status": "failed", "request": summary, "failure_reason": f"{type(exc).__name__}:{str(exc)[:500]}"}


def _apply_gpt_replacement(cleanup: dict, gpt_payload: dict) -> None:
    if gpt_payload.get("status") != "ok" or not gpt_payload.get("normalized_output_path"):
        return
    cleanup["replacement_method"] = "gpt_image2_masked_edit"
    cleanup["replacement_crop_path"] = gpt_payload["normalized_output_path"]


def _crop_size(bbox: tuple[int, int, int, int]) -> tuple[int, int]:
    x1, y1, x2, y2 = bbox
    return x2 - x1, y2 - y1


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
        f"- Local methods: {_method_summary(rows)}",
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


def _method_summary(rows: list[dict]) -> str:
    methods: dict[str, int] = {}
    for row in rows:
        method = row.get("cleanup", {}).get("method") or "unknown"
        methods[method] = methods.get(method, 0) + 1
    return ", ".join(f"{name}={count}" for name, count in sorted(methods.items())) or "none"


def _safe_name(value: str) -> str:
    return "".join(char if char.isalnum() else "-" for char in value).strip("-") or "record"
