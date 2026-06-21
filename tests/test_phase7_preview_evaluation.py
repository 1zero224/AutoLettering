import json
from pathlib import Path

from PIL import Image

from autolettering.phase7_evaluate import (
    build_preview_evaluation_prompt,
    parse_preview_evaluation_response,
    run_phase7_preview_evaluation,
)


class FakePreviewEvaluationClient:
    def analyze_image(
        self,
        image_path: str | Path,
        prompt: str,
        kind: str = "image_analysis",
        max_completion_tokens: int | None = None,
    ) -> dict:
        assert Path(image_path).exists()
        assert kind == "phase7_preview_evaluation"
        assert max_completion_tokens == 192
        assert "bubble_mask_fill" in prompt
        assert "bt_lama_large_inpaint" in prompt
        return {
            "raw_text": json.dumps(
                {
                    "score": 8,
                    "usable": True,
                    "original_text_removed": True,
                    "art_preserved": True,
                    "lettering_readable": True,
                    "issues": ["bubble translation is too large"],
                    "summary": "The cleanup is usable; lettering still needs layout tuning.",
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


def test_parse_preview_evaluation_response_extracts_structured_json():
    result = parse_preview_evaluation_response(
        '{"score":8,"usable":true,"original_text_removed":true,'
        '"art_preserved":true,"lettering_readable":false,'
        '"issues":["too large"],"summary":"usable cleanup"}'
    )

    assert result.status == "evaluated"
    assert result.score == 8
    assert result.usable is True
    assert result.original_text_removed is True
    assert result.art_preserved is True
    assert result.lettering_readable is False
    assert result.issues == ["too large"]
    assert result.summary == "usable cleanup"
    assert result.failure_reason is None


def test_parse_preview_evaluation_response_reports_invalid_json():
    result = parse_preview_evaluation_response("")

    assert result.status == "failed"
    assert result.failure_reason == "invalid_json"


def test_build_preview_evaluation_prompt_lists_records_and_methods():
    prompt = build_preview_evaluation_prompt(
        {
            "records": [
                {
                    "record_id": "page.png#1",
                    "translated_text": "街头演出？",
                    "cleanup_method": "bubble_mask_fill",
                    "bbox": [1, 2, 3, 4],
                }
            ]
        }
    )

    assert "page.png#1" in prompt
    assert "街头演出？" in prompt
    assert "bubble_mask_fill" in prompt
    assert "score" in prompt


def test_run_phase7_preview_evaluation_writes_results_and_api_summaries(tmp_path: Path):
    preview_run = tmp_path / "phase7"
    preview_page = preview_run / "pages" / "page.png"
    preview_page.parent.mkdir(parents=True)
    Image.new("RGB", (64, 64), "white").save(preview_page)
    _write_preview_results(preview_run / "preview-results.jsonl", preview_page)

    run_dir = run_phase7_preview_evaluation(
        preview_run_dir=preview_run,
        output_root=tmp_path / "outputs",
        run_id="phase7-eval-test",
        sample_limit=1,
        client=FakePreviewEvaluationClient(),
    )

    evaluations = _read_jsonl(run_dir / "preview-evaluation.jsonl")
    api_calls = _read_jsonl(run_dir / "reports" / "api-calls.jsonl")
    report = (run_dir / "reports" / "phase7-evaluation-report.md").read_text(encoding="utf-8")

    assert evaluations[0]["image_name"] == "page.png"
    assert evaluations[0]["status"] == "evaluated"
    assert evaluations[0]["score"] == 8
    assert evaluations[0]["usable"] is True
    assert evaluations[0]["preview_path"] == str(preview_page)
    assert "bubble translation is too large" in evaluations[0]["issues"]
    assert api_calls[0]["image_name"] == "page.png"
    assert api_calls[0]["request"]["prompt_chars"] > 0
    assert "api_key" not in json.dumps(api_calls[0]).lower()
    assert "Average score: 8.0" in report


def _write_preview_results(path: Path, preview_page: Path) -> None:
    row = {
        "image_name": "page.png",
        "status": "page_preview_generated",
        "records": [
            {
                "record_id": "page.png#1",
                "translated_text": "街头演出？",
                "cleanup_method": "bubble_mask_fill",
                "bbox": [1, 2, 3, 4],
            },
            {
                "record_id": "page.png#16",
                "translated_text": "来自桃香的唐突的提案",
                "cleanup_method": "bt_lama_large_inpaint",
                "bbox": [5, 6, 7, 8],
            },
        ],
        "preview": {"page_preview_path": str(preview_page), "record_count": 2},
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
