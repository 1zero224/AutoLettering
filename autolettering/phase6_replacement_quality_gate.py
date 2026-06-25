from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path


RunDirInput = str | Path | Iterable[str | Path] | None
GPT_REPLACEMENT_METHOD = "gpt_image2_masked_edit"
QUALITY_REJECTION_REASON = "quality_rejected"
MISSING_QUALITY_REASON = "quality_missing"


def load_replacement_quality_by_id(run_dir: RunDirInput) -> dict[str, dict]:
    rows: dict[str, dict] = {}
    for item in _run_dirs(run_dir):
        path = Path(item) / "replacement-quality.jsonl"
        if not path.exists():
            continue
        for row in _jsonl_rows(path):
            record_id = row.get("record_id")
            if record_id:
                rows[str(record_id)] = row
    return rows


def gpt_replacement_quality_gate(record_id: str | None, cleanup: dict, quality_by_id: dict[str, dict] | None) -> dict:
    if cleanup.get("replacement_method") != GPT_REPLACEMENT_METHOD:
        return {"accepted": True, "status": "not_applicable"}
    if not cleanup.get("replacement_crop_path"):
        return {"accepted": False, "status": "not_applicable", "failure_reason": "replacement_crop_missing"}
    if quality_by_id is None:
        return {"accepted": True, "status": "not_required"}
    quality = quality_by_id.get(str(record_id)) if record_id else None
    if not quality:
        return {
            "accepted": False,
            "status": "missing",
            "failure_reason": MISSING_QUALITY_REASON,
            "issues": [MISSING_QUALITY_REASON],
        }
    accepted = _quality_accepts_replacement(quality)
    return {
        "accepted": accepted,
        "status": quality.get("status"),
        "usable": quality.get("usable"),
        "exact_text_correct": quality.get("exact_text_correct"),
        "simplified_chinese_correct": quality.get("simplified_chinese_correct"),
        "no_japanese_remaining": quality.get("no_japanese_remaining"),
        "region_correct": quality.get("region_correct"),
        "style_consistent": quality.get("style_consistent"),
        "failure_reason": None if accepted else QUALITY_REJECTION_REASON,
        "issues": list(quality.get("issues") or []),
    }


def accepts_gpt_replacement(record_id: str | None, cleanup: dict, quality_by_id: dict[str, dict] | None) -> bool:
    return bool(gpt_replacement_quality_gate(record_id, cleanup, quality_by_id).get("accepted"))


def effective_cleanup_for_gpt_quality(record_id: str | None, cleanup: dict, quality_by_id: dict[str, dict] | None) -> dict:
    if quality_by_id is None:
        return dict(cleanup)
    gate = gpt_replacement_quality_gate(record_id, cleanup, quality_by_id)
    if gate.get("accepted"):
        payload = dict(cleanup)
        if cleanup.get("replacement_method") == GPT_REPLACEMENT_METHOD:
            payload["gpt_replacement_quality"] = gate
        return payload
    payload = dict(cleanup)
    payload.pop("replacement_method", None)
    payload.pop("replacement_crop_path", None)
    payload["text_overlay_required"] = True
    payload["gpt_replacement_quality"] = gate
    return payload


def _quality_accepts_replacement(row: dict) -> bool:
    return (
        row.get("status") == "evaluated"
        and row.get("usable") is True
        and row.get("exact_text_correct") is True
        and row.get("simplified_chinese_correct") is True
        and row.get("no_japanese_remaining") is True
        and row.get("region_correct") is True
    )


def _run_dirs(run_dir: RunDirInput) -> list[Path]:
    if run_dir is None:
        return []
    if isinstance(run_dir, (str, Path)):
        return [Path(run_dir)]
    return [Path(item) for item in run_dir]


def _jsonl_rows(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            rows.append(json.loads(stripped))
    return rows
