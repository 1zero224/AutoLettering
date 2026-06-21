import json
from pathlib import Path

from PIL import Image

from autolettering.layout.validation import (
    build_layout_validation_prompt,
    parse_layout_validation_response,
)
from autolettering.phase4_validate import run_phase4_layout_validation


class FakeLayoutValidationClient:
    def analyze_image(
        self,
        image_path: str | Path,
        prompt: str,
        kind: str = "image_analysis",
        max_completion_tokens: int | None = None,
    ) -> dict:
        assert Path(image_path).exists()
        assert kind == "layout_validation"
        assert max_completion_tokens == 96
        assert "overflow" in prompt
        return {
            "raw_text": json.dumps(
                {
                    "accepted": True,
                    "needs_revision": False,
                    "overflow_ok": True,
                    "naturalness_score": 0.86,
                    "recommended_changes": [],
                    "reasoning_summary": "The text fits cleanly and remains readable.",
                }
            ),
            "request": {
                "url": "https://example.test/v1/chat/completions",
                "model": "mimo-v2.5",
                "image_path": str(image_path),
                "prompt_chars": len(prompt),
            },
            "response": {"status": "ok"},
        }


class EmptyLayoutValidationClient:
    def analyze_image(
        self,
        image_path: str | Path,
        prompt: str,
        kind: str = "image_analysis",
        max_completion_tokens: int | None = None,
    ) -> dict:
        return {
            "raw_text": "",
            "request": {"image_path": str(image_path), "prompt_chars": len(prompt)},
            "response": {"status": "ok"},
        }


def test_parse_layout_validation_response_accepts_structured_json():
    result = parse_layout_validation_response(
        '{"accepted":true,"needs_revision":false,"overflow_ok":true,'
        '"naturalness_score":0.86,"recommended_changes":[],"reasoning_summary":"fits"}'
    )

    assert result.status == "accepted"
    assert result.accepted is True
    assert result.needs_revision is False
    assert result.overflow_ok is True
    assert result.naturalness_score == 0.86
    assert result.failure_reason is None


def test_parse_layout_validation_response_reports_invalid_json():
    result = parse_layout_validation_response("")

    assert result.status == "failed"
    assert result.failure_reason == "invalid_json"


def test_run_phase4_layout_validation_writes_results_and_api_summaries(tmp_path: Path):
    layout_run = tmp_path / "phase4"
    layout_run.mkdir()
    preview_path = tmp_path / "layout.png"
    Image.new("RGBA", (120, 80), (255, 255, 255, 0)).save(preview_path)
    _write_layout_results(layout_run / "layout-results.jsonl", preview_path)

    run_dir = run_phase4_layout_validation(
        layout_run_dir=layout_run,
        output_root=tmp_path / "outputs",
        run_id="phase4-validation-test",
        sample_limit=1,
        client=FakeLayoutValidationClient(),
    )

    validations = _read_jsonl(run_dir / "layout-validation.jsonl")
    api_calls = _read_jsonl(run_dir / "reports" / "api-calls.jsonl")
    assert validations[0]["record_id"] == "page.png#1"
    assert validations[0]["status"] == "accepted"
    assert validations[0]["accepted"] is True
    assert validations[0]["naturalness_score"] == 0.86
    assert validations[0]["layout_preview_path"] == str(preview_path)
    assert api_calls[0]["record_id"] == "page.png#1"
    assert api_calls[0]["request"]["prompt_chars"] > 0
    assert "api_key" not in json.dumps(api_calls[0]).lower()


def test_run_phase4_layout_validation_falls_back_when_model_returns_invalid_json(tmp_path: Path):
    layout_run = tmp_path / "phase4"
    layout_run.mkdir()
    preview_path = tmp_path / "layout.png"
    Image.new("RGBA", (120, 80), (255, 255, 255, 0)).save(preview_path)
    _write_layout_results(layout_run / "layout-results.jsonl", preview_path)

    run_dir = run_phase4_layout_validation(
        layout_run_dir=layout_run,
        output_root=tmp_path / "outputs",
        run_id="phase4-validation-fallback-test",
        sample_limit=1,
        client=EmptyLayoutValidationClient(),
    )

    validation = _read_jsonl(run_dir / "layout-validation.jsonl")[0]
    assert validation["status"] == "accepted"
    assert validation["accepted"] is True
    assert validation["overflow_ok"] is True
    assert validation["selection_source"] == "deterministic_fallback"
    assert validation["failure_reason"] is None
    assert validation["model_failure_reason"] == "invalid_json"
    assert "model returned invalid_json" in validation["reasoning_summary"]


def test_build_layout_validation_prompt_includes_measurements():
    prompt = build_layout_validation_prompt(
        translated_text="街头演出？",
        layout={
            "orientation": "horizontal",
            "font_size": 72,
            "overflow_ratio": 0.0,
            "target_width": 375,
            "target_height": 342,
            "measured_width": 361,
            "measured_height": 69,
        },
    )

    assert "街头演出？" in prompt
    assert "overflow" in prompt
    assert "JSON" in prompt
    assert "recommended_changes" not in prompt
    assert len(prompt) < 260


def _write_layout_results(path: Path, preview_path: Path) -> None:
    payload = {
        "record_id": "page.png#1",
        "image_name": "page.png",
        "translated_text": "街头演出？",
        "status": "layout_generated",
        "layout": {
            "orientation": "horizontal",
            "font_size": 72,
            "overflow_ratio": 0.0,
            "target_width": 120,
            "target_height": 80,
            "measured_width": 100,
            "measured_height": 40,
            "preview_path": str(preview_path),
        },
    }
    path.write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
