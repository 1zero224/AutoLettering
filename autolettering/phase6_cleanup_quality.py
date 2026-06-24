from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Protocol

from PIL import Image, ImageDraw, ImageFont, ImageOps

from .experiment_grid import near_square_columns


FINAL_REPLACEMENT_METHODS = {"gpt_image2_masked_edit", "cta_first_masked_edit"}


class CleanupQualityClient(Protocol):
    def analyze_image(
        self,
        image_path: str | Path,
        prompt: str,
        kind: str = "image_analysis",
        max_completion_tokens: int | None = None,
    ) -> dict:
        ...


@dataclass(frozen=True)
class CleanupQualityResult:
    status: str
    score: int | None
    usable: bool | None
    original_text_removed: bool | None
    art_preserved: bool | None
    issues: list[str]
    summary: str | None
    failure_reason: str | None


def run_phase6_cleanup_quality(
    cleanup_run_dir: str | Path,
    output_root: str | Path = "outputs/runs",
    run_id: str | None = None,
    sample_limit: int = 5,
    record_ids: list[str] | None = None,
    client: CleanupQualityClient | None = None,
) -> Path:
    if client is None:
        raise ValueError("client is required unless experiment script builds one from environment")
    run_dir = Path(output_root) / (run_id or "phase6-cleanup-quality")
    run_dir.mkdir(parents=True, exist_ok=True)
    rows = _load_cleanup_rows(Path(cleanup_run_dir) / "cleanup-results.jsonl", sample_limit, record_ids)
    evaluations, api_calls = _evaluate_cleanup_rows(run_dir, rows, client)
    _write_jsonl(run_dir / "cleanup-quality.jsonl", evaluations)
    _write_jsonl(run_dir / "reports" / "api-calls.jsonl", api_calls)
    _write_report(run_dir / "reports" / "phase6-cleanup-quality-report.md", cleanup_run_dir, evaluations)
    return run_dir


def build_cleanup_quality_prompt(row: dict) -> str:
    cleanup = row.get("cleanup") or {}
    payload = {
        "record_id": row.get("record_id"),
        "translated_text": row.get("translated_text", ""),
        "cleanup_method": cleanup.get("method"),
        "bbox": cleanup.get("bbox"),
    }
    return "\n".join(
        [
            "Evaluate this manga Phase 6 cleanup before/after sheet.",
            "LEFT is the original crop before cleanup. RIGHT is the AFTER cleaned crop.",
            "Long vertical cleanup crops may be split into numbered segments; combine all segments for the record-level verdict.",
            "If the image is split into segments, do not treat repeated panel borders, columns, or multiple segments as duplicated cleanup attempts.",
            "Judge segment 1 -> 2 -> 3 in order as one continuous cleanup result.",
            "Only judge the RIGHT AFTER cleaned crop for pass/fail.",
            "Do not require Chinese translated text to appear; this is background repair only.",
            "The cleaned crop should remove visible original Japanese text while preserving non-text art, tones, texture, icons, and panel details.",
            "Mark original_text_removed=false if dark glyph-shaped residue, ghosting, or readable original Japanese text remains in the AFTER cleaned crop.",
            "Mark art_preserved=false if background texture, icons, panel art, or non-text symbols are damaged or replaced by a flat block.",
            f"Record JSON: {json.dumps(payload, ensure_ascii=False)}",
            "Return only JSON with keys: score (0-10), usable, original_text_removed, art_preserved, issues, summary.",
        ]
    )


def parse_cleanup_quality_response(raw_text: str) -> CleanupQualityResult:
    try:
        payload = json.loads(_strip_json_wrapper(raw_text))
    except json.JSONDecodeError:
        return _failed("invalid_json")
    if not isinstance(payload, dict):
        return _failed("invalid_json")
    return CleanupQualityResult(
        status="evaluated",
        score=_optional_int(payload.get("score")),
        usable=_optional_bool(payload.get("usable")),
        original_text_removed=_optional_bool(payload.get("original_text_removed")),
        art_preserved=_optional_bool(payload.get("art_preserved")),
        issues=_string_list(payload.get("issues")),
        summary=str(payload.get("summary", "")).strip() or None,
        failure_reason=None,
    )


def _load_cleanup_rows(path: Path, sample_limit: int, record_ids: list[str] | None) -> list[dict]:
    wanted = set(record_ids or [])
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if len(rows) >= sample_limit:
                break
            payload = json.loads(line)
            if wanted and payload.get("record_id") not in wanted:
                continue
            if _is_evaluable_cleanup_row(payload):
                rows.append(payload)
    return rows


def _is_evaluable_cleanup_row(row: dict) -> bool:
    if row.get("status") != "cleaned":
        return False
    cleanup = row.get("cleanup") or {}
    if not cleanup.get("before_after_path"):
        return False
    method = cleanup.get("replacement_method") or cleanup.get("method")
    if method in FINAL_REPLACEMENT_METHODS:
        return False
    return True


def _evaluate_cleanup_rows(run_dir: Path, rows: list[dict], client: CleanupQualityClient) -> tuple[list[dict], list[dict]]:
    evaluations: list[dict] = []
    api_calls: list[dict] = []
    for row in rows:
        evaluation, api_call = _evaluate_one(run_dir, row, client)
        evaluations.append(evaluation)
        api_calls.append(api_call)
    return evaluations, api_calls


def _evaluate_one(run_dir: Path, row: dict, client: CleanupQualityClient) -> tuple[dict, dict]:
    prompt = build_cleanup_quality_prompt(row)
    image_path = _write_cleanup_quality_sheet(run_dir, row)
    try:
        response = client.analyze_image(
            image_path,
            prompt,
            kind="phase6_cleanup_quality",
            max_completion_tokens=900,
        )
        result = parse_cleanup_quality_response(response["raw_text"])
        return _evaluation_row(row, result, response["raw_text"], image_path), _api_call_row(row, response)
    except Exception as exc:
        return _failure_evaluation(row, exc, image_path), _failure_api_call(row, exc, prompt, image_path)


def _evaluation_row(row: dict, result: CleanupQualityResult, raw_text: str, image_path: str) -> dict:
    return {
        "record_id": row.get("record_id"),
        "image_name": row.get("image_name"),
        "status": result.status,
        "score": result.score,
        "usable": result.usable,
        "original_text_removed": result.original_text_removed,
        "art_preserved": result.art_preserved,
        "issues": result.issues,
        "summary": result.summary,
        "failure_reason": result.failure_reason,
        "cleanup_method": (row.get("cleanup") or {}).get("method"),
        "before_after_path": (row.get("cleanup") or {}).get("before_after_path"),
        "evaluation_image_path": image_path,
        "raw_model_text": raw_text,
    }


def _api_call_row(row: dict, response: dict) -> dict:
    return {
        "record_id": row.get("record_id"),
        "image_name": row.get("image_name"),
        "status": "ok",
        "request": response.get("request", {}),
        "response": response.get("response", {}),
    }


def _failure_evaluation(row: dict, exc: Exception, image_path: str) -> dict:
    return {
        "record_id": row.get("record_id"),
        "image_name": row.get("image_name"),
        "status": "failed",
        "score": None,
        "usable": None,
        "original_text_removed": None,
        "art_preserved": None,
        "issues": [],
        "summary": None,
        "failure_reason": f"api_error:{type(exc).__name__}",
        "cleanup_method": (row.get("cleanup") or {}).get("method"),
        "before_after_path": (row.get("cleanup") or {}).get("before_after_path"),
        "evaluation_image_path": image_path,
        "raw_model_text": None,
    }


def _failure_api_call(row: dict, exc: Exception, prompt: str, image_path: str) -> dict:
    return {
        "record_id": row.get("record_id"),
        "image_name": row.get("image_name"),
        "status": "failed",
        "request": {"prompt_chars": len(prompt), "image_path": image_path},
        "response": {"error_type": type(exc).__name__, "error_message": str(exc)[:500]},
    }


def _write_cleanup_quality_sheet(run_dir: Path, row: dict) -> str:
    cleanup = row.get("cleanup") or {}
    before_after_path = cleanup.get("before_after_path")
    output = run_dir / "debug" / "cleanup_quality_sheets" / f"{_safe_name(str(row.get('record_id')))}.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    before, after = _split_before_after(before_after_path)
    segments = _cleanup_review_segments(before, after)
    font = _font(13)
    small = _font(11)
    header_height = 58
    label_height = 82
    padding = 12
    after_box = (300, 320)
    before_box = (160, 320)
    cell_width = padding * 3 + before_box[0] + after_box[0]
    cell_height = label_height + after_box[1] + padding
    columns = near_square_columns(len(segments), cell_width=cell_width, cell_height=cell_height)
    rows = (len(segments) + columns - 1) // columns
    width = padding + columns * (cell_width + padding)
    height = header_height + padding + rows * (cell_height + padding)
    sheet = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(sheet)
    _draw_cleanup_header(draw, width, font)
    for index, (before_segment, after_segment) in enumerate(segments):
        column = index % columns
        row_index = index // columns
        x = padding + column * (cell_width + padding)
        y = header_height + padding + row_index * (cell_height + padding)
        _draw_cleanup_cell(
            draw,
            sheet,
            (x, y),
            before_segment,
            after_segment,
            row,
            index + 1,
            len(segments),
            before_box,
            after_box,
            font,
            small,
        )
    sheet.save(output)
    return str(output)


def _draw_cleanup_header(draw: ImageDraw.ImageDraw, width: int, font: ImageFont.ImageFont) -> None:
    draw.rectangle((0, 0, width, 50), fill=(244, 248, 250), outline=(180, 190, 200))
    draw.text((12, 8), "MIMO REVIEW SHEET: Phase 6 cleanup only, no translated text required.", fill=(0, 80, 120), font=font)
    draw.text((12, 29), "Long vertical crops are split into ordered segments. Judge segment 1 -> 2 -> 3 as one result.", fill=(0, 80, 120), font=font)


def _draw_cleanup_cell(
    draw: ImageDraw.ImageDraw,
    sheet: Image.Image,
    xy: tuple[int, int],
    before: Image.Image,
    after: Image.Image,
    row: dict,
    segment_index: int,
    segment_count: int,
    before_box: tuple[int, int],
    after_box: tuple[int, int],
    font: ImageFont.ImageFont,
    small: ImageFont.ImageFont,
) -> None:
    x, y = xy
    padding = 12
    label = f"Phase 6 cleanup: {row.get('record_id')}"
    if segment_count > 1:
        label = f"{label} | segment {segment_index}/{segment_count} {_segment_position(segment_index, segment_count)}"
    method = f"method={(row.get('cleanup') or {}).get('method')}"
    draw.text((x, y + 6), label[:56], fill="black", font=font)
    draw.text((x, y + 27), method[:56], fill=(40, 40, 40), font=small)
    draw.text((x, y + 54), "BEFORE reference", fill=(90, 90, 90), font=small)
    after_x = x + padding * 2 + before_box[0]
    draw.text((after_x, y + 54), "SCORE THIS: AFTER cleaned crop", fill=(0, 110, 60), font=small)
    panel_y = y + 82
    before_panel = _fit_panel(before, before_box)
    after_panel = _fit_panel(after, after_box)
    draw.rectangle((x - 1, panel_y - 1, x + before_box[0], panel_y + before_box[1]), outline=(150, 150, 150), width=1)
    draw.rectangle((after_x - 2, panel_y - 2, after_x + after_box[0] + 1, panel_y + after_box[1] + 1), outline=(0, 160, 80), width=3)
    sheet.paste(before_panel, (x + (before_box[0] - before_panel.width) // 2, panel_y))
    sheet.paste(after_panel, (after_x + (after_box[0] - after_panel.width) // 2, panel_y))


def _cleanup_review_segments(before: Image.Image, after: Image.Image, max_segment_height: int = 260) -> list[tuple[Image.Image, Image.Image]]:
    if after.height <= max_segment_height:
        return [(before, after)]
    segment_count = max(1, int(round((after.height + max_segment_height - 1) // max_segment_height)))
    segments: list[tuple[Image.Image, Image.Image]] = []
    for index in range(segment_count):
        y1 = round(after.height * index / segment_count)
        y2 = round(after.height * (index + 1) / segment_count)
        segments.append((before.crop((0, y1, before.width, y2)), after.crop((0, y1, after.width, y2))))
    return segments


def _segment_position(index: int, total: int) -> str:
    if index == 1:
        return "TOP"
    if index == total:
        return "BOTTOM"
    return "MIDDLE"


def _split_before_after(path: str | Path) -> tuple[Image.Image, Image.Image]:
    image = Image.open(path).convert("RGB")
    midpoint = image.width // 2
    return image.crop((0, 0, midpoint, image.height)), image.crop((midpoint, 0, image.width, image.height))


def _fit_panel(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    return ImageOps.contain(image.convert("RGB"), size, method=Image.Resampling.LANCZOS)


def _font(size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size)
    except OSError:
        return ImageFont.load_default()


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_report(output_path: Path, cleanup_run_dir: str | Path, evaluations: list[dict]) -> None:
    evaluated = [row for row in evaluations if row["status"] == "evaluated"]
    usable = sum(1 for row in evaluated if row.get("usable") is True)
    failed = sum(1 for row in evaluations if row["status"] != "evaluated")
    lines = [
        "# Phase 6 Cleanup Quality Report",
        "",
        f"Cleanup run directory: `{cleanup_run_dir}`",
        "",
        "## Summary",
        "",
        f"- Records submitted: {len(evaluations)}",
        f"- Evaluated: {len(evaluated)}",
        f"- Usable cleanups: {usable}",
        f"- Failed evaluations: {failed}",
        "",
        "## Generated Artifacts",
        "",
        "- `cleanup-quality.jsonl`",
        "- `reports/api-calls.jsonl`",
        "- `debug/cleanup_quality_sheets/*.png`",
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _strip_json_wrapper(raw_text: str) -> str:
    text = raw_text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def _optional_int(value: object) -> int | None:
    try:
        score = int(value)
    except (TypeError, ValueError):
        return None
    return max(0, min(10, score))


def _optional_bool(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    return None


def _string_list(value: object) -> list[str]:
    if isinstance(value, str):
        stripped = value.strip()
        return [stripped] if stripped else []
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _failed(reason: str) -> CleanupQualityResult:
    return CleanupQualityResult(
        status="failed",
        score=None,
        usable=None,
        original_text_removed=None,
        art_preserved=None,
        issues=[],
        summary=None,
        failure_reason=reason,
    )


def _safe_name(value: str) -> str:
    return "".join(char if char.isalnum() else "-" for char in value).strip("-") or "record"
