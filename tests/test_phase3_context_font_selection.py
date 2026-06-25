import json
import shutil
from pathlib import Path

import pytest
from PIL import Image

from autolettering.phase3_context_font_selection import run_phase3_context_font_selection


def test_run_phase3_context_font_selection_renders_candidates_and_selects_with_mimo(tmp_path: Path):
    font_path = _copy_test_font(tmp_path)
    font_run = tmp_path / "phase3-fonts"
    layout_run = tmp_path / "phase4-layout"
    cleanup_run = tmp_path / "phase6-cleanup"
    _write_font_comparison(font_run / "font-comparisons.jsonl", font_path)
    _write_layout(layout_run / "layout-results.jsonl")
    _write_cleanup(cleanup_run / "cleanup-results.jsonl", cleanup_run / "cleaned.png", cleanup_run / "source.png")
    fake_client = FakeMimoClient("font-b")

    run_dir = run_phase3_context_font_selection(
        font_comparison_run_dir=font_run,
        layout_run_dir=layout_run,
        cleanup_run_dir=cleanup_run,
        output_root=tmp_path / "outputs",
        run_id="context-font-test",
        sample_limit=1,
        client=fake_client,
        candidate_limit=2,
    )

    rows = _read_jsonl(run_dir / "context-font-results.jsonl")
    selections = _read_jsonl(run_dir / "font-selections.jsonl")
    api_calls = _read_jsonl(run_dir / "reports" / "api-calls.jsonl")

    assert rows[0]["record_id"] == "page.png#1"
    assert rows[0]["status"] == "selected"
    assert rows[0]["selected_font_id"] == "font-b"
    assert rows[0]["selected_font"]["font_id"] == "font-b"
    assert rows[0]["selection_source"] == "mimo_context_font"
    assert Path(rows[0]["comparison_image_path"]).exists()
    assert all(Path(item["context_crop_path"]).exists() for item in rows[0]["candidate_fonts"])
    assert all(Path(item["review_context_path"]).exists() for item in rows[0]["candidate_fonts"])
    with Image.open(rows[0]["comparison_image_path"]) as grid:
        assert grid.height >= 600
    assert selections[0]["selected_font_id"] == "font-b"
    assert api_calls[0]["status"] == "ok"
    assert fake_client.calls[0]["kind"] == "phase3_context_font_selection"
    assert "SOURCE" in fake_client.calls[0]["prompt"]


def test_run_phase3_context_font_selection_dry_run_writes_first_candidate(tmp_path: Path):
    font_path = _copy_test_font(tmp_path)
    font_run = tmp_path / "phase3-fonts"
    layout_run = tmp_path / "phase4-layout"
    cleanup_run = tmp_path / "phase6-cleanup"
    _write_font_comparison(font_run / "font-comparisons.jsonl", font_path)
    _write_layout(layout_run / "layout-results.jsonl")
    _write_cleanup(cleanup_run / "cleanup-results.jsonl", cleanup_run / "cleaned.png", cleanup_run / "source.png")

    run_dir = run_phase3_context_font_selection(
        font_comparison_run_dir=font_run,
        layout_run_dir=layout_run,
        cleanup_run_dir=cleanup_run,
        output_root=tmp_path / "outputs",
        run_id="context-font-dry-test",
        sample_limit=1,
        client=None,
        candidate_limit=2,
    )

    rows = _read_jsonl(run_dir / "context-font-results.jsonl")
    api_calls = _read_jsonl(run_dir / "reports" / "api-calls.jsonl")

    assert rows[0]["status"] == "dry_run"
    assert rows[0]["selected_font_id"] == "font-a"
    assert rows[0]["selection_source"] == "context_font_fallback"
    assert api_calls[0]["status"] == "skipped"
    assert api_calls[0]["response"]["reason"] == "dry_run"


def test_run_phase3_context_font_selection_marks_model_parse_fallback_source(tmp_path: Path):
    font_path = _copy_test_font(tmp_path)
    font_run = tmp_path / "phase3-fonts"
    layout_run = tmp_path / "phase4-layout"
    cleanup_run = tmp_path / "phase6-cleanup"
    _write_font_comparison(font_run / "font-comparisons.jsonl", font_path)
    _write_layout(layout_run / "layout-results.jsonl")
    _write_cleanup(cleanup_run / "cleanup-results.jsonl", cleanup_run / "cleaned.png", cleanup_run / "source.png")

    run_dir = run_phase3_context_font_selection(
        font_comparison_run_dir=font_run,
        layout_run_dir=layout_run,
        cleanup_run_dir=cleanup_run,
        output_root=tmp_path / "outputs",
        run_id="context-font-fallback-test",
        sample_limit=1,
        client=FakeMimoClient("font-unknown"),
        candidate_limit=2,
    )

    rows = _read_jsonl(run_dir / "context-font-results.jsonl")
    api_calls = _read_jsonl(run_dir / "reports" / "api-calls.jsonl")

    assert rows[0]["status"] == "selected"
    assert rows[0]["selected_font_id"] == "font-a"
    assert rows[0]["selection_source"] == "context_font_fallback"
    assert rows[0]["failure_reason"] == "selected_font_not_in_candidates"
    assert "deterministic fallback after model failure" in rows[0]["model_reasoning_summary"]
    assert rows[0]["raw_model_text"]
    assert api_calls[0]["status"] == "ok"


def test_run_phase3_context_font_selection_ignores_failed_upstream_rows(tmp_path: Path):
    font_path = _copy_test_font(tmp_path)
    font_run = tmp_path / "phase3-fonts"
    layout_run = tmp_path / "phase4-layout"
    cleanup_run = tmp_path / "phase6-cleanup"
    _write_font_comparison(font_run / "font-comparisons.jsonl", font_path)
    _write_layout_with_failed_tail(layout_run / "layout-results.jsonl")
    _write_cleanup_with_skipped_tail(cleanup_run / "cleanup-results.jsonl", cleanup_run / "cleaned.png", cleanup_run / "source.png")

    run_dir = run_phase3_context_font_selection(
        font_comparison_run_dir=font_run,
        layout_run_dir=layout_run,
        cleanup_run_dir=cleanup_run,
        output_root=tmp_path / "outputs",
        run_id="context-font-upstream-filter-test",
        sample_limit=1,
        client=None,
        candidate_limit=2,
    )

    rows = _read_jsonl(run_dir / "context-font-results.jsonl")

    assert rows[0]["status"] == "dry_run"
    assert rows[0]["selected_font_id"] == "font-a"
    assert Path(rows[0]["candidate_fonts"][0]["context_crop_path"]).exists()


class FakeMimoClient:
    def __init__(self, selected_font_id: str) -> None:
        self.selected_font_id = selected_font_id
        self.calls: list[dict] = []

    def analyze_image(
        self,
        image_path: str | Path,
        prompt: str,
        kind: str = "image_analysis",
        max_completion_tokens: int | None = None,
    ) -> dict:
        self.calls.append(
            {
                "image_path": str(image_path),
                "prompt": prompt,
                "kind": kind,
                "max_completion_tokens": max_completion_tokens,
            }
        )
        return {
            "raw_text": json.dumps(
                {
                    "selected_font_id": self.selected_font_id,
                    "confidence": 0.82,
                    "reasoning_summary": "font-b better matches the banner preview",
                }
            ),
            "request": {"image_path": str(image_path), "prompt_chars": len(prompt)},
            "response": {"status": "ok"},
        }


def _copy_test_font(tmp_path: Path) -> Path:
    fonts_root = Path("C:/Windows/Fonts")
    candidates = sorted(list(fonts_root.glob("*.ttf")) + list(fonts_root.glob("*.otf")))
    if not candidates:
        pytest.skip("No system TTF/OTF font available for font rendering tests")
    target = tmp_path / candidates[0].name
    shutil.copy2(candidates[0], target)
    return target


def _write_font_comparison(path: Path, font_path: Path) -> None:
    row = {
        "record_id": "page.png#1",
        "image_name": "page.png",
        "translated_text": "ABC2026",
        "group_name": "框外",
        "status": "candidates_generated",
        "source_crop_path": str(path.parent / "source-text.png"),
        "comparison_image_path": str(path.parent / "comparison.png"),
        "candidate_fonts": [
            _candidate("font-a", font_path),
            _candidate("font-b", font_path),
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (80, 180), (180, 60, 70)).save(path.parent / "source-text.png")
    path.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")


def _candidate(font_id: str, font_path: Path) -> dict:
    return {
        "font_id": font_id,
        "path": str(font_path),
        "filename": f"{font_id}.ttf",
        "family_name": font_id,
        "postscript_name": font_id,
        "style_hints": [font_id],
        "supports_sample_text": True,
        "unsupported_chars": [],
    }


def _write_layout(path: Path) -> None:
    row = {
        "record_id": "page.png#1",
        "image_name": "page.png",
        "translated_text": "ABC2026",
        "status": "layout_generated",
        "layout": {
            "status": "ok",
            "text": "ABC2026",
            "line_breaks": "ABC2026",
            "font_size": 24,
            "orientation": "vertical",
            "line_spacing": 4,
            "letter_spacing": 0,
            "angle_degrees": 0.0,
            "target_width": 90,
            "target_height": 260,
            "measured_width": 42,
            "measured_height": 180,
            "overflow_ratio": 0.0,
            "failure_reason": None,
            "target_bbox": [0, 0, 90, 260],
            "text_color": [255, 255, 255, 255],
            "vertical_align": "top",
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_layout_with_failed_tail(path: Path) -> None:
    _write_layout(path)
    failed = {
        "record_id": "page.png#1",
        "image_name": "page.png",
        "translated_text": "ABC2026",
        "status": "layout_failed",
        "layout": {"failure_reason": "test failure"},
    }
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(failed, ensure_ascii=False) + "\n")


def _write_cleanup(path: Path, cleaned_path: Path, source_path: Path) -> None:
    cleaned_path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (90, 260), (195, 70, 80)).save(cleaned_path)
    Image.new("RGB", (90, 260), (180, 60, 70)).save(source_path)
    row = {
        "record_id": "page.png#1",
        "image_name": "page.png",
        "translated_text": "ABC2026",
        "status": "cleaned",
        "cleanup": {
            "method": "gpt_image2_background_repair",
            "bbox": [0, 0, 90, 260],
            "input_crop_path": str(source_path),
            "cleaned_crop_path": str(cleaned_path),
            "text_overlay_required": True,
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_cleanup_with_skipped_tail(path: Path, cleaned_path: Path, source_path: Path) -> None:
    _write_cleanup(path, cleaned_path, source_path)
    skipped = {
        "record_id": "page.png#1",
        "image_name": "page.png",
        "translated_text": "ABC2026",
        "status": "skipped",
        "cleanup": {"failure_reason": "test skipped"},
    }
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(skipped, ensure_ascii=False) + "\n")


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
