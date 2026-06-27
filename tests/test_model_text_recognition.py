import json
from pathlib import Path

from PIL import Image

from autolettering.detection.model_text_recognition import (
    build_model_text_region_prompt,
    parse_model_text_region_response,
    recognize_text_region_with_model,
    write_text_region_context_crop,
)


def test_parse_model_text_region_response_accepts_percent_bbox():
    result = parse_model_text_region_response(
        raw_text=json.dumps(
            {
                "found": True,
                "bbox_percent_xyxy": [10, 20, 60, 80],
                "source_text": "ありがとう",
                "orientation": "vertical",
                "confidence": 0.82,
                "reasoning_summary": "Japanese text column near the label point.",
            },
            ensure_ascii=False,
        ),
        context_bbox_xyxy=(100, 200, 300, 400),
        context_size=(200, 200),
    )

    assert result["status"] == "ok"
    assert result["local_bbox_xyxy"] == [20, 40, 120, 160]
    assert result["global_bbox_xyxy"] == [120, 240, 220, 360]
    assert result["bbox_coordinate_source"] == "bbox_percent_xyxy"
    assert result["source_text"] == "ありがとう"
    assert result["orientation"] == "vertical"
    assert result["confidence"] == 0.82
    assert result["reasoning_summary"] == "Japanese text column near the label point."


def test_parse_model_text_region_response_accepts_single_object_array_wrapper():
    result = parse_model_text_region_response(
        raw_text="""```json
[
  {
    "found": true,
    "bbox_xyxy": [12, 18, 80, 50],
    "source_text": "仮",
    "orientation": "horizontal",
    "confidence": 0.9
  }
]
```""",
        context_bbox_xyxy=(100, 200, 300, 400),
        context_size=(200, 200),
    )

    assert result["status"] == "ok"
    assert result["local_bbox_xyxy"] == [12, 18, 80, 50]
    assert result["global_bbox_xyxy"] == [112, 218, 180, 250]
    assert result["source_text"] == "仮"


def test_parse_model_text_region_response_accepts_ratio_percent_bbox():
    result = parse_model_text_region_response(
        raw_text=json.dumps(
            {
                "found": True,
                "bbox_percent_xyxy": [0.1, 0.2, 0.6, 0.8],
            }
        ),
        context_bbox_xyxy=(100, 200, 300, 400),
        context_size=(200, 200),
    )

    assert result["status"] == "ok"
    assert result["local_bbox_xyxy"] == [20, 40, 120, 160]
    assert result["bbox_coordinate_source"] == "bbox_percent_xyxy"


def test_parse_model_text_region_response_marks_clipped_model_bbox():
    result = parse_model_text_region_response(
        raw_text=json.dumps(
            {
                "found": True,
                "bbox_xyxy": [10, -5, 250, 260],
            }
        ),
        context_bbox_xyxy=(100, 200, 300, 400),
        context_size=(200, 200),
    )

    assert result["status"] == "ok"
    assert result["local_bbox_xyxy"] == [10, 0, 200, 200]
    assert result["global_bbox_xyxy"] == [110, 200, 300, 400]
    assert result["bbox_clipped"] is True


def test_parse_model_text_region_response_reports_not_found():
    result = parse_model_text_region_response(
        raw_text='{"found": false, "reasoning_summary": "no matching text"}',
        context_bbox_xyxy=(0, 0, 100, 100),
        context_size=(100, 100),
    )

    assert result == {
        "status": "not_found",
        "failure_reason": "model_reported_not_found",
        "reasoning_summary": "no matching text",
    }


def test_recognize_text_region_with_model_calls_existing_vision_client(tmp_path: Path):
    image_path = tmp_path / "context.png"
    Image.new("RGB", (120, 100), "white").save(image_path)
    client = _FakeVisionClient(
        {
            "found": True,
            "bbox_xyxy": [12, 20, 52, 70],
            "source_text": "カナ",
            "orientation": "horizontal",
            "confidence": 0.7,
            "reasoning_summary": "Text near the red LabelPlus point.",
        }
    )

    result = recognize_text_region_with_model(
        client=client,
        context_image_path=image_path,
        context_bbox_xyxy=(300, 400, 420, 500),
        labelplus_point_xy=(28, 35),
        translated_text="假名",
    )

    assert result["status"] == "ok"
    assert result["local_bbox_xyxy"] == [12, 20, 52, 70]
    assert result["global_bbox_xyxy"] == [312, 420, 352, 470]
    assert result["request"] == {"kind": "phase2_model_text_region_recognition"}
    assert result["response"] == {"status": "ok"}
    assert client.calls[0]["kind"] == "phase2_model_text_region_recognition"
    assert "single JSON object" in client.calls[0]["prompt"]
    assert "Chinese translation: 假名" in client.calls[0]["prompt"]
    assert "LabelPlus point in this crop: [28, 35]" in client.calls[0]["prompt"]


def test_write_text_region_context_crop_writes_requested_crop(tmp_path: Path):
    image_path = tmp_path / "page.png"
    Image.new("RGB", (100, 100), "white").save(image_path)

    output = write_text_region_context_crop(image_path, (10, 20, 50, 70), tmp_path / "crop.png")

    with Image.open(output) as crop:
        assert crop.size == (40, 50)


def test_build_model_text_region_prompt_is_ui_independent():
    prompt = build_model_text_region_prompt(
        translated_text="谢谢",
        labelplus_point_xy=(10, 20),
        candidate_boxes=[[1, 2, 30, 40]],
    )

    assert "X-AnyLabeling" not in prompt
    assert "annotation UI" not in prompt
    assert "red LabelPlus point" not in prompt
    assert "LabelPlus coordinate anchor" in prompt
    assert "candidate_boxes_xyxy" in prompt
    assert "bbox_xyxy" in prompt
    assert "bbox_percent_xyxy" in prompt
    assert "single JSON object" in prompt
    assert "complete corresponding original text" in prompt
    assert "may span multiple candidate boxes" in prompt


class _FakeVisionClient:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.calls: list[dict] = []

    def analyze_image(self, image_path: str | Path, prompt: str, kind: str, max_completion_tokens: int) -> dict:
        self.calls.append(
            {
                "image_path": Path(image_path),
                "prompt": prompt,
                "kind": kind,
                "max_completion_tokens": max_completion_tokens,
            }
        )
        return {
            "raw_text": json.dumps(self.payload, ensure_ascii=False),
            "request": {"kind": kind},
            "response": {"status": "ok"},
        }
