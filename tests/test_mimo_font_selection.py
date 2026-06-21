import json
from pathlib import Path

from PIL import Image

from autolettering.models.mimo import (
    MimoVisionClient,
    MimoVisionConfig,
    build_font_selection_prompt,
    parse_font_selection_response,
)
from autolettering.models.request_log import request_summary
from autolettering.phase3_vision import run_phase3_vision_selection


class FakeMimoVisionClient:
    def choose_font(self, comparison_image_path: str | Path, prompt: str) -> dict:
        assert Path(comparison_image_path).exists()
        assert "font-a" in prompt
        return {
            "raw_text": json.dumps(
                {
                    "selected_font_id": "font-a",
                    "confidence": 0.82,
                    "reasoning_summary": "font-a has the closest heavy handwritten style",
                }
            ),
            "request": {
                "url": "https://example.test/v1/chat/completions",
                "model": "mimo-v2.5",
                "image_path": str(comparison_image_path),
                "prompt_chars": len(prompt),
            },
            "response": {"status": "ok"},
        }


class InvalidJsonMimoVisionClient:
    def choose_font(self, comparison_image_path: str | Path, prompt: str) -> dict:
        return {
            "raw_text": "",
            "request": {"model": "mimo-v2.5", "prompt_chars": len(prompt)},
            "response": {"status": "ok"},
        }


def test_mimo_vision_client_builds_image_request_without_exposing_key(tmp_path: Path):
    image_path = tmp_path / "comparison.png"
    Image.new("RGB", (10, 10), "white").save(image_path)
    client = MimoVisionClient(MimoVisionConfig("https://api.example/v1", "secret-value", "mimo-v2.5"))

    payload = client.build_chat_payload(image_path, "Pick a font")
    summary = request_summary("font_selection", payload, image_path=image_path)

    assert payload["model"] == "mimo-v2.5"
    content = payload["messages"][1]["content"]
    assert content[0]["type"] == "image_url"
    assert content[0]["image_url"]["url"].startswith("data:image/png;base64,")
    assert content[1] == {"type": "text", "text": "Pick a font"}
    assert "secret-value" not in json.dumps(summary)
    assert summary["image_path"] == str(image_path)


def test_mimo_vision_client_can_disable_thinking_in_payload_and_summary(tmp_path: Path):
    image_path = tmp_path / "comparison.png"
    Image.new("RGB", (10, 10), "white").save(image_path)
    client = MimoVisionClient(
        MimoVisionConfig("https://api.example/v1", "secret-value", "mimo-v2.5", thinking_type="disabled")
    )

    payload = client.build_chat_payload(image_path, "Pick a font")
    summary = request_summary("font_selection", payload, image_path=image_path)

    assert payload["thinking"] == {"type": "disabled"}
    assert summary["thinking_type"] == "disabled"
    assert "secret-value" not in json.dumps(summary)


def test_mimo_vision_client_analyze_image_uses_given_image_path(tmp_path: Path, monkeypatch):
    image_path = tmp_path / "layout.png"
    Image.new("RGB", (10, 10), "white").save(image_path)
    client = MimoVisionClient(MimoVisionConfig("https://api.example/v1", "secret-value", "mimo-v2.5"))

    def fake_post_json(url: str, api_key: str, payload: dict) -> dict:
        assert url == "https://api.example/v1/chat/completions"
        assert api_key == "secret-value"
        assert payload["messages"][1]["content"][0]["image_url"]["url"].startswith("data:image/png;base64,")
        return {"choices": [{"message": {"content": "{}"}}], "model": "mimo-v2.5"}

    monkeypatch.setattr("autolettering.models.mimo._post_json", fake_post_json)
    result = client.analyze_image(image_path, "Validate layout", kind="layout_validation", max_completion_tokens=96)

    assert result["raw_text"] == "{}"
    assert result["request"]["kind"] == "layout_validation"
    assert result["request"]["image_path"] == str(image_path)
    assert result["request"]["max_completion_tokens"] == 96


def test_parse_font_selection_response_extracts_selected_candidate():
    result = parse_font_selection_response(
        raw_text='{"selected_font_id":"font-a","confidence":0.75,"reasoning_summary":"closest stroke weight"}',
        candidate_font_ids=["font-a", "font-b"],
    )

    assert result.status == "selected"
    assert result.selected_font_id == "font-a"
    assert result.confidence == 0.75
    assert result.reasoning_summary == "closest stroke weight"
    assert result.failure_reason is None


def test_parse_font_selection_response_rejects_unknown_font_id():
    result = parse_font_selection_response(
        raw_text='{"selected_font_id":"font-z","confidence":0.75,"reasoning_summary":"not in candidate set"}',
        candidate_font_ids=["font-a", "font-b"],
    )

    assert result.status == "failed"
    assert result.selected_font_id is None
    assert result.failure_reason == "selected_font_not_in_candidates"


def test_run_phase3_vision_selection_writes_results_and_api_summaries(tmp_path: Path):
    comparison_path = tmp_path / "comparison.png"
    Image.new("RGB", (32, 32), "white").save(comparison_path)
    input_run = tmp_path / "phase3"
    input_run.mkdir()
    _write_comparison_jsonl(input_run / "font-comparisons.jsonl", comparison_path)

    run_dir = run_phase3_vision_selection(
        input_run_dir=input_run,
        output_root=tmp_path / "outputs",
        run_id="phase3-vision-test",
        sample_limit=1,
        client=FakeMimoVisionClient(),
    )

    selections = _read_jsonl(run_dir / "font-selections.jsonl")
    api_calls = _read_jsonl(run_dir / "reports" / "api-calls.jsonl")
    assert selections[0]["record_id"] == "page.png#1"
    assert selections[0]["status"] == "selected"
    assert selections[0]["selected_font_id"] == "font-a"
    assert selections[0]["selected_font"]["font_id"] == "font-a"
    assert selections[0]["selection_source"] == "mimo_vision"
    assert selections[0]["source_crop_path"] == str(comparison_path)
    assert api_calls[0]["record_id"] == "page.png#1"
    assert api_calls[0]["request"]["prompt_chars"] > 0
    assert "api_key" not in json.dumps(api_calls[0]).lower()


def test_run_phase3_vision_selection_falls_back_when_model_returns_invalid_json(tmp_path: Path):
    comparison_path = tmp_path / "comparison.png"
    Image.new("RGB", (32, 32), "white").save(comparison_path)
    input_run = tmp_path / "phase3"
    input_run.mkdir()
    _write_comparison_jsonl(input_run / "font-comparisons.jsonl", comparison_path)

    run_dir = run_phase3_vision_selection(
        input_run_dir=input_run,
        output_root=tmp_path / "outputs",
        run_id="phase3-fallback-test",
        sample_limit=1,
        client=InvalidJsonMimoVisionClient(),
    )

    selections = _read_jsonl(run_dir / "font-selections.jsonl")
    assert selections[0]["status"] == "selected"
    assert selections[0]["selected_font_id"] == "font-a"
    assert selections[0]["selection_source"] == "deterministic_fallback"
    assert selections[0]["failure_reason"] == "invalid_json"


def test_run_phase3_vision_selection_filters_by_record_id_before_sample_limit(tmp_path: Path):
    comparison_path = tmp_path / "comparison.png"
    Image.new("RGB", (32, 32), "white").save(comparison_path)
    input_run = tmp_path / "phase3"
    input_run.mkdir()
    _write_comparison_jsonl(
        input_run / "font-comparisons.jsonl",
        comparison_path,
        record_ids=["page.png#1", "page.png#2"],
    )

    run_dir = run_phase3_vision_selection(
        input_run_dir=input_run,
        output_root=tmp_path / "outputs",
        run_id="phase3-vision-filter-test",
        sample_limit=1,
        record_ids=["page.png#2"],
        client=FakeMimoVisionClient(),
    )

    selections = _read_jsonl(run_dir / "font-selections.jsonl")
    assert [row["record_id"] for row in selections] == ["page.png#2"]


def test_build_font_selection_prompt_lists_candidate_ids():
    prompt = build_font_selection_prompt(
        translated_text="测试",
        candidate_fonts=[
            {"font_id": "font-a", "family_name": "A", "style_hints": ["黑体"]},
            {"font_id": "font-b", "family_name": "B", "style_hints": ["楷体"]},
        ],
    )

    assert "font-a" in prompt
    assert "font-b" in prompt
    assert "JSON" in prompt


def _write_comparison_jsonl(path: Path, comparison_path: Path, record_ids: list[str] | None = None) -> None:
    rows = []
    for record_id in record_ids or ["page.png#1"]:
        rows.append(
            {
                "record_id": record_id,
                "image_name": "page.png",
                "translated_text": "测试",
                "group_name": "框内",
                "status": "candidates_generated",
                "source_crop_path": str(comparison_path),
                "comparison_image_path": str(comparison_path),
                "candidate_fonts": [
                    {"font_id": "font-a", "family_name": "Font A", "style_hints": ["黑体"]},
                    {"font_id": "font-b", "family_name": "Font B", "style_hints": ["楷体"]},
                ],
            }
        )
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
