import json
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw

from autolettering.inpaint.nonbubble import build_gpt_edit_mask, build_text_mask, inpaint_nonbubble_text
from autolettering.models.gpt_image import GptImageConfig, normalize_gpt_output_to_crop, normalize_openai_base_url
from autolettering.phase6_nonbubble import run_phase6_nonbubble_cleanup


def test_build_text_mask_and_gpt_mask_use_expected_alpha_convention():
    crop = Image.new("RGB", (40, 30), (180, 180, 180))
    ImageDraw.Draw(crop).rectangle((15, 8, 25, 22), fill="black")

    text_mask = build_text_mask(crop, dark_threshold=80, dilate_px=3)
    gpt_mask = build_gpt_edit_mask(text_mask)

    assert text_mask.getpixel((20, 15)) == 255
    assert text_mask.getpixel((2, 2)) == 0
    assert gpt_mask.getpixel((20, 15))[3] == 0
    assert gpt_mask.getpixel((2, 2))[3] == 255


def test_inpaint_nonbubble_text_writes_artifacts_and_reduces_dark_text(tmp_path: Path):
    image_path = _write_nonbubble_image(tmp_path / "page.png")

    result = inpaint_nonbubble_text(
        image_path=image_path,
        bbox=(20, 15, 90, 75),
        output_dir=tmp_path / "nonbubble",
        record_id="page.png#2",
    )

    assert result.cleaned_crop_path.exists()
    assert result.gpt_mask_path.exists()
    assert result.before_after_path.exists()
    with Image.open(result.input_crop_path) as before, Image.open(result.cleaned_crop_path) as after:
        assert ImageChops.difference(before.convert("RGB"), after.convert("RGB")).getbbox() is not None
        assert after.convert("L").getpixel((35, 25)) > before.convert("L").getpixel((35, 25))


def test_run_phase6_nonbubble_cleanup_writes_local_and_gpt_dry_run(tmp_path: Path):
    image_path = _write_nonbubble_image(tmp_path / "page.png")
    detection_run = tmp_path / "phase2"
    detection_run.mkdir()
    _write_detection(detection_run / "detections.jsonl", image_path)

    run_dir = run_phase6_nonbubble_cleanup(
        detection_run_dir=detection_run,
        output_root=tmp_path / "outputs",
        run_id="phase6-nonbubble-test",
        sample_limit=1,
    )

    rows = _read_jsonl(run_dir / "cleanup-results.jsonl")
    assert rows[0]["record_id"] == "page.png#2"
    assert rows[0]["status"] == "cleaned"
    assert rows[0]["cleanup"]["method"] == "local_diffusion_inpaint"
    assert rows[0]["gpt_image2_edit"]["status"] == "dry_run"
    assert rows[0]["gpt_image2_edit"]["request"]["kind"] == "gpt_image_2_masked_edit"
    assert Path(rows[0]["cleanup"]["gpt_mask_path"]).exists()
    assert (run_dir / "reports" / "phase6-nonbubble-report.md").exists()


def test_run_phase6_nonbubble_cleanup_records_gpt_success_with_fake_client(tmp_path: Path, monkeypatch):
    image_path = _write_nonbubble_image(tmp_path / "page.png")
    detection_run = tmp_path / "phase2"
    detection_run.mkdir()
    _write_detection(detection_run / "detections.jsonl", image_path)
    monkeypatch.setattr("autolettering.phase6_nonbubble.GptImageEditClient", lambda config: _FakeGptClient())

    run_dir = run_phase6_nonbubble_cleanup(
        detection_run_dir=detection_run,
        output_root=tmp_path / "outputs",
        run_id="phase6-gpt-test",
        sample_limit=1,
        gpt_config=GptImageConfig(base_url="https://example.test/v1/images", api_key="test", model="gpt-image-2"),
        call_gpt_image=True,
    )

    rows = _read_jsonl(run_dir / "cleanup-results.jsonl")
    assert rows[0]["gpt_image2_edit"]["status"] == "ok"
    assert rows[0]["gpt_image2_edit"]["output_path"].endswith(".png")
    assert rows[0]["gpt_image2_edit"]["normalized_size"] == [70, 60]
    assert rows[0]["cleanup"]["replacement_method"] == "gpt_image2_masked_edit"
    assert Path(rows[0]["cleanup"]["replacement_crop_path"]).exists()
    report = (run_dir / "reports" / "phase6-nonbubble-report.md").read_text(encoding="utf-8")
    assert "- GPT image calls: 1" in report


def test_normalize_gpt_output_to_crop_writes_target_sized_image(tmp_path: Path):
    image_path = tmp_path / "gpt.png"
    Image.new("RGB", (300, 500), "blue").save(image_path)

    result = normalize_gpt_output_to_crop(image_path, (30, 70), tmp_path / "normalized.png")

    assert result["source_size"] == [300, 500]
    assert result["normalized_size"] == [30, 70]
    with Image.open(result["normalized_output_path"]) as image:
        assert image.size == (30, 70)


def test_normalize_openai_base_url_removes_image_endpoint_suffix():
    assert normalize_openai_base_url("https://example.test/v1/images") == "https://example.test/v1"
    assert normalize_openai_base_url("https://example.test/v1/images/edits") == "https://example.test/v1"
    assert normalize_openai_base_url("https://example.test/v1") == "https://example.test/v1"


class _FakeGptClient:
    def edit_image(self, image_path: str, mask_path: str, prompt: str, output_path: str) -> dict:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (10, 10), "white").save(output)
        return {"status": "ok", "output_path": str(output), "response": {"usage": {"total_tokens": 1}}}


def _write_nonbubble_image(path: Path) -> Path:
    image = Image.new("RGB", (120, 100), (210, 205, 190))
    draw = ImageDraw.Draw(image)
    for y in range(100):
        draw.line((0, y, 120, y), fill=(190 + y // 4, 185 + y // 5, 170 + y // 6))
    draw.rectangle((35, 25, 62, 55), fill="black")
    image.save(path)
    return path


def _write_detection(path: Path, image_path: Path) -> None:
    payload = {
        "record_id": "page.png#2",
        "status": "ok",
        "image_name": "page.png",
        "image_path": str(image_path),
        "group_name": "框外",
        "translated_text": "背景文字",
        "selected_text_box_xyxy": [20, 15, 90, 75],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
