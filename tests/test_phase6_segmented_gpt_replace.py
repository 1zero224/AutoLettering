import json
from pathlib import Path

from PIL import Image, ImageDraw

from autolettering.models.gpt_image import GptImageConfig
from autolettering.phase6_segmented_gpt_replace import _segmented_gpt_image_edit_prompt, run_phase6_segmented_gpt_replace


def test_run_phase6_segmented_gpt_replace_splits_tall_vertical_target(tmp_path: Path, monkeypatch):
    image_path = _write_tall_banner(tmp_path / "page.png")
    detection_run = tmp_path / "phase2"
    _write_detection(detection_run / "detections.jsonl", image_path)
    fake_client = FakeGptClient()
    monkeypatch.setattr("autolettering.phase6_segmented_gpt_replace.GptImageEditClient", lambda config: fake_client)

    run_dir = run_phase6_segmented_gpt_replace(
        detection_run_dir=detection_run,
        output_root=tmp_path / "outputs",
        run_id="segmented-gpt-test",
        sample_limit=1,
        gpt_config=GptImageConfig(base_url="https://example.test/v1/images", api_key="test", model="gpt-image-2"),
        call_gpt_image=True,
        mimo_client=FakeMimoClient(),
        context_padding=8,
        rect_mask_expand_px=1,
        max_segment_chars=8,
    )

    rows = _read_jsonl(run_dir / "segmented-gpt-replace-results.jsonl")
    row = rows[0]
    assert row["record_id"] == "page.png#1"
    assert row["status"] == "processed"
    assert row["segmented_gpt_replace"]["status"] == "ok"
    assert row["segmented_gpt_replace"]["segment_count"] == 3
    assert [segment["target_text"] for segment in row["segments"]] == [
        "漫画第一卷",
        "2026年6月",
        "29日发售！！",
    ]
    assert [call["target_text"] for call in fake_client.calls] == ["漫画第一卷", "2026年6月", "29日发售！！"]
    assert all(call["image_size"][1] < 760 for call in fake_client.calls)
    assert Path(row["segmented_gpt_replace"]["composed_context_path"]).exists()
    assert Path(row["segmented_gpt_replace"]["target_crop_path"]).exists()
    assert all("paste_bbox" in segment for segment in row["segments"])
    with Image.open(row["segmented_gpt_replace"]["composed_context_path"]).convert("RGB") as composed:
        assert composed.getpixel((2, 20)) == (205, 58, 72)
        assert composed.getpixel((12, 20)) == (255, 255, 255)
    assert (run_dir / "visuals" / "segmented-gpt-replace-grid.png").exists()
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["gpt_ok_count"] == 1
    assert manifest["gpt_quality_failed_count"] == 0
    assert manifest["mimo"]["quality"]["segmented_gpt_status"] == "acceptable"
    cleanup_rows = _read_jsonl(run_dir / "cleanup-results.jsonl")
    assert cleanup_rows[0]["status"] == "cleaned"
    cleanup = cleanup_rows[0]["cleanup"]
    assert cleanup["method"] == "segmented_gpt_image2_masked_edit"
    assert cleanup["replacement_method"] == "gpt_image2_masked_edit"
    assert cleanup["cleaned_crop_path"] == row["context"]["input_path"]
    assert cleanup["replacement_crop_path"] == row["segmented_gpt_replace"]["composed_context_path"]
    assert cleanup["cleaned_crop_path"] != cleanup["replacement_crop_path"]
    assert cleanup["bbox"] == [80, 22, 140, 878]
    assert cleanup["text_bbox"] == [88, 30, 132, 870]
    assert cleanup["mask_bbox"] == [88, 30, 132, 870]
    assert cleanup["layout_text_bbox"] == [88, 30, 132, 870]
    assert cleanup["text_overlay_required"] is False
    with Image.open(cleanup["cleaned_crop_path"]) as cleaned, Image.open(cleanup["replacement_crop_path"]) as replacement:
        assert cleaned.size == replacement.size == (60, 856)


def test_segmented_gpt_prompt_rejects_unjustified_black_outline():
    prompt = _segmented_gpt_image_edit_prompt("29日发售！！")

    assert "Target Chinese text: 29日发售！！" in prompt
    assert "Do not add a black outline" in prompt
    assert "unless the original local segment already has it" in prompt
    assert "white or pale text on a colored banner" in prompt


def test_run_phase6_segmented_gpt_replace_dry_run_keeps_background_baseline(tmp_path: Path):
    image_path = _write_tall_banner(tmp_path / "page.png")
    detection_run = tmp_path / "phase2"
    _write_detection(detection_run / "detections.jsonl", image_path)

    run_dir = run_phase6_segmented_gpt_replace(
        detection_run_dir=detection_run,
        output_root=tmp_path / "outputs",
        run_id="segmented-gpt-dry-run-test",
        sample_limit=1,
        call_gpt_image=False,
        context_padding=8,
        rect_mask_expand_px=1,
        max_segment_chars=8,
    )

    row = _read_jsonl(run_dir / "segmented-gpt-replace-results.jsonl")[0]
    cleanup_row = _read_jsonl(run_dir / "cleanup-results.jsonl")[0]
    cleanup = cleanup_row["cleanup"]
    assert row["segmented_gpt_replace"]["status"] == "failed"
    assert cleanup_row["status"] == "failed"
    assert cleanup["cleaned_crop_path"] == row["context"]["input_path"]
    assert cleanup["replacement_crop_path"] is None
    assert cleanup["replacement_method"] is None
    assert cleanup["text_overlay_required"] is True


class FakeGptClient:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def edit_image(self, image_path: str, mask_path: str, prompt: str, output_path: str) -> dict:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(image_path) as image:
            target_text = prompt.split("Target Chinese text: ", 1)[-1]
            self.calls.append({"target_text": target_text, "image_size": image.size})
            edited = image.convert("RGB").copy()
        draw = ImageDraw.Draw(edited)
        draw.rectangle((4, 4, edited.width - 4, edited.height - 4), fill="white")
        draw.text((8, 8), target_text, fill="black")
        edited.save(output)
        return {"status": "ok", "output_path": str(output), "response": {"usage": {"total_tokens": 1}}}


class FakeMimoClient:
    def analyze_image(
        self,
        image_path: str | Path,
        prompt: str,
        kind: str = "image_analysis",
        max_completion_tokens: int | None = None,
    ) -> dict:
        assert Path(image_path).exists()
        assert kind == "phase6_segmented_gpt_replace_grid"
        return {
            "raw_text": json.dumps(
                {
                    "segmented_gpt_scores": {"exact_text": 9, "placement": 8},
                    "unacceptable_methods": [],
                    "best_overall_for_user_choice": "segmented_gpt_image2",
                    "reasoning_summary": "Segmented GPT replacement is acceptable.",
                    "caveats": "fake",
                }
            ),
            "request": {"kind": kind, "image_path": str(image_path), "prompt_chars": len(prompt)},
            "response": {"status": "ok"},
        }


def _write_tall_banner(path: Path) -> Path:
    image = Image.new("RGB", (220, 900), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((80, 22, 140, 878), fill=(205, 58, 72))
    for y in range(60, 830, 90):
        draw.rectangle((98, y, 122, y + 42), fill="white")
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)
    return path


def _write_detection(path: Path, image_path: Path) -> None:
    row = {
        "status": "ok",
        "image_name": "page.png",
        "image_path": str(image_path),
        "record_id": "page.png#1",
        "group_name": "框外",
        "translated_text": "漫画第一卷\n2026年6月29日发售！！",
        "selected_text_box_xyxy": [88, 30, 132, 870],
        "cta_match": {"status": "matched", "bbox_xyxy": [88, 30, 132, 870]},
        "candidate_boxes": [{"xyxy": [88, 30, 132, 870], "score": 1.0, "polarity": "dark_on_light"}],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
