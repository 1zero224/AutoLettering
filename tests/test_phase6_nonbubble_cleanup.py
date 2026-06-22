import json
import importlib.util
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageChops, ImageDraw

from autolettering.inpaint.nonbubble import build_gpt_edit_mask, build_text_mask, inpaint_crop, inpaint_nonbubble_text
from autolettering.inpaint.balloons import _restore_grayscale_if_mono
from autolettering.models.gpt_image import (
    GptImageConfig,
    gpt_image_edit_prompt,
    normalize_gpt_output_to_crop,
    normalize_openai_base_url,
)
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


def test_gpt_image_prompt_requires_exact_target_text():
    prompt = gpt_image_edit_prompt("来自桃香的唐突的提案")

    assert "Target Chinese text: 来自桃香的唐突的提案" in prompt
    assert "exactly match" in prompt
    assert "Do not omit" in prompt


def test_build_text_mask_excludes_large_solid_icon_on_light_background():
    crop = Image.new("RGB", (80, 150), "white")
    draw = ImageDraw.Draw(crop)
    draw.polygon([(40, 6), (68, 34), (40, 62), (12, 34)], fill="black")
    draw.line((22, 82, 58, 82), fill="black", width=6)
    draw.line((40, 70, 40, 118), fill="black", width=6)
    draw.line((25, 118, 55, 118), fill="black", width=6)

    text_mask = build_text_mask(crop, dark_threshold=80, dilate_px=3)

    assert text_mask.getpixel((40, 34)) == 0
    assert text_mask.getpixel((40, 82)) == 255


def test_build_text_mask_preserves_broad_square_glyph_below_icon():
    crop = Image.new("RGB", (80, 180), "white")
    draw = ImageDraw.Draw(crop)
    draw.polygon([(40, 6), (68, 34), (40, 62), (12, 34)], fill="black")
    draw.rectangle((18, 78, 62, 122), fill=(120, 120, 120))
    draw.rectangle((26, 86, 34, 114), fill="white")
    draw.rectangle((46, 86, 54, 114), fill="white")
    draw.line((18, 100, 62, 100), fill=(40, 40, 40), width=4)

    text_mask = build_text_mask(crop, dark_threshold=185, dilate_px=3)

    assert text_mask.getpixel((40, 34)) == 0
    assert text_mask.getpixel((40, 100)) == 255
    assert text_mask.getpixel((20, 80)) == 255


def test_build_text_mask_can_select_light_text_on_dark_background():
    crop = Image.new("RGB", (40, 30), (20, 20, 20))
    ImageDraw.Draw(crop).rectangle((15, 8, 25, 22), fill="white")

    text_mask = build_text_mask(crop, dilate_px=3, polarity="light_on_dark", light_threshold=210)

    assert text_mask.getpixel((20, 15)) == 255
    assert text_mask.getpixel((2, 2)) == 0


def test_build_text_mask_does_not_select_light_art_on_light_background_for_light_text():
    crop = Image.new("RGB", (80, 40), (240, 240, 240))
    draw = ImageDraw.Draw(crop)
    draw.rectangle((8, 8, 25, 25), fill="white")
    draw.rectangle((45, 6, 75, 34), fill=(20, 20, 20))
    draw.rectangle((55, 14, 65, 26), fill="white")

    text_mask = build_text_mask(crop, dilate_px=3, polarity="light_on_dark", light_threshold=210)

    assert text_mask.getpixel((16, 16)) == 0
    assert text_mask.getpixel((60, 20)) == 255


def test_inpaint_nonbubble_text_writes_artifacts_and_reduces_dark_text(tmp_path: Path):
    image_path = _write_nonbubble_image(tmp_path / "page.png")

    result = inpaint_nonbubble_text(
        image_path=image_path,
        bbox=(20, 15, 90, 75),
        output_dir=tmp_path / "nonbubble",
        record_id="page.png#2",
        method="local_diffusion",
    )

    assert result.cleaned_crop_path.exists()
    assert result.gpt_mask_path.exists()
    assert result.before_after_path.exists()
    with Image.open(result.input_crop_path) as before, Image.open(result.cleaned_crop_path) as after:
        assert ImageChops.difference(before.convert("RGB"), after.convert("RGB")).getbbox() is not None
        assert after.convert("L").getpixel((35, 25)) > before.convert("L").getpixel((35, 25))


def test_inpaint_nonbubble_text_supports_opencv_telea_method(tmp_path: Path):
    if importlib.util.find_spec("cv2") is None:
        pytest.skip("opencv-python-headless is optional for local inpaint experiments")
    image_path = _write_nonbubble_image(tmp_path / "page.png")

    result = inpaint_nonbubble_text(
        image_path=image_path,
        bbox=(20, 15, 90, 75),
        output_dir=tmp_path / "nonbubble",
        record_id="page.png#2",
        method="opencv_telea",
    )

    assert result.method == "opencv_telea_inpaint"
    assert result.cleaned_crop_path.exists()
    with Image.open(result.input_crop_path) as before, Image.open(result.cleaned_crop_path) as after:
        assert ImageChops.difference(before.convert("RGB"), after.convert("RGB")).getbbox() is not None


def test_inpaint_crop_routes_balloon_lama_large_method(monkeypatch):
    crop = Image.new("RGB", (12, 10), "black")
    mask = Image.new("L", crop.size, 255)

    monkeypatch.setattr(
        "autolettering.inpaint.nonbubble.balloons_lama_large_inpaint",
        lambda crop_arg, mask_arg: Image.new("RGB", crop_arg.size, "white"),
    )

    method, result = inpaint_crop(crop, mask, "bt_lama_large")

    assert method == "bt_lama_large_inpaint"
    assert result.getpixel((0, 0)) == (255, 255, 255)


def test_inpaint_crop_routes_balloon_patchmatch_method(monkeypatch):
    crop = Image.new("RGB", (12, 10), "black")
    mask = Image.new("L", crop.size, 255)

    monkeypatch.setattr(
        "autolettering.inpaint.nonbubble.balloons_patchmatch_inpaint",
        lambda crop_arg, mask_arg: Image.new("RGB", crop_arg.size, "white"),
    )

    method, result = inpaint_crop(crop, mask, "bt_patchmatch")

    assert method == "bt_patchmatch_inpaint"
    assert result.getpixel((0, 0)) == (255, 255, 255)


def test_inpaint_crop_routes_balloon_aot_method(monkeypatch):
    crop = Image.new("RGB", (12, 10), "black")
    mask = Image.new("L", crop.size, 255)

    monkeypatch.setattr(
        "autolettering.inpaint.nonbubble.balloons_aot_inpaint",
        lambda crop_arg, mask_arg: Image.new("RGB", crop_arg.size, "white"),
    )

    method, result = inpaint_crop(crop, mask, "bt_aot")

    assert method == "bt_aot_inpaint"
    assert result.getpixel((0, 0)) == (255, 255, 255)


def test_aot_grayscale_postprocess_only_applies_to_mono_sources():
    mono_original = np.full((2, 2, 3), 120, dtype=np.uint8)
    color_result = np.array(
        [
            [[60, 120, 200], [70, 130, 210]],
            [[80, 140, 220], [90, 150, 230]],
        ],
        dtype=np.uint8,
    )
    restored = _restore_grayscale_if_mono(mono_original, color_result)

    assert np.array_equal(restored[:, :, 0], restored[:, :, 1])
    assert np.array_equal(restored[:, :, 1], restored[:, :, 2])

    color_original = color_result.copy()
    unchanged = _restore_grayscale_if_mono(color_original, color_result)

    assert np.array_equal(unchanged, color_result)


def test_inpaint_crop_supports_dark_panel_fill_method():
    crop = Image.new("RGB", (30, 20), (18, 18, 18))
    ImageDraw.Draw(crop).rectangle((10, 6, 18, 14), fill="white")
    mask = Image.new("L", crop.size, 0)
    ImageDraw.Draw(mask).rectangle((10, 6, 18, 14), fill=255)

    method, result = inpaint_crop(crop, mask, "dark_panel_fill")

    assert method == "dark_panel_fill"
    assert result.convert("L").getpixel((14, 10)) < 80
    assert result.getpixel((2, 2)) == (18, 18, 18)


def test_inpaint_crop_supports_flat_median_fill_method():
    crop = Image.new("RGB", (42, 32), (248, 248, 246))
    draw = ImageDraw.Draw(crop)
    draw.rectangle((14, 7, 26, 24), fill="black")
    draw.line((0, 30, 41, 30), fill=(20, 20, 20), width=1)
    mask = Image.new("L", crop.size, 0)
    ImageDraw.Draw(mask).rectangle((14, 7, 26, 24), fill=255)

    method, result = inpaint_crop(crop, mask, "flat_median_fill")

    assert method == "flat_median_fill"
    assert result.convert("L").getpixel((20, 15)) > 240
    assert result.convert("L").getpixel((20, 30)) < 40


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
        inpaint_method="opencv_telea",
    )

    rows = _read_jsonl(run_dir / "cleanup-results.jsonl")
    assert rows[0]["record_id"] == "page.png#2"
    assert rows[0]["status"] == "cleaned"
    assert rows[0]["cleanup"]["method"] == "opencv_telea_inpaint"
    assert rows[0]["gpt_image2_edit"]["status"] == "dry_run"
    assert rows[0]["gpt_image2_edit"]["request"]["kind"] == "gpt_image_2_masked_edit"
    assert Path(rows[0]["cleanup"]["gpt_mask_path"]).exists()
    assert (run_dir / "reports" / "phase6-nonbubble-report.md").exists()


def test_run_phase6_nonbubble_cleanup_defaults_to_lama_large(tmp_path: Path, monkeypatch):
    image_path = _write_nonbubble_image(tmp_path / "page.png")
    detection_run = tmp_path / "phase2"
    detection_run.mkdir()
    _write_detection(detection_run / "detections.jsonl", image_path)
    monkeypatch.setattr(
        "autolettering.inpaint.nonbubble.balloons_lama_large_inpaint",
        lambda crop_arg, mask_arg: Image.new("RGB", crop_arg.size, "white"),
    )

    run_dir = run_phase6_nonbubble_cleanup(
        detection_run_dir=detection_run,
        output_root=tmp_path / "outputs",
        run_id="phase6-nonbubble-default",
        sample_limit=1,
    )

    rows = _read_jsonl(run_dir / "cleanup-results.jsonl")
    assert rows[0]["cleanup"]["method"] == "bt_lama_large_inpaint"


def test_run_phase6_nonbubble_cleanup_can_filter_record_ids(tmp_path: Path):
    image_path = _write_nonbubble_image(tmp_path / "page.png")
    detection_run = tmp_path / "phase2"
    detection_run.mkdir()
    _write_detection(
        detection_run / "detections.jsonl",
        image_path,
        rows=[
            {"record_id": "page.png#1", "group_name": "框外", "selected_text_box_xyxy": [20, 15, 90, 75]},
            {"record_id": "page.png#2", "group_name": "框外", "selected_text_box_xyxy": [22, 18, 92, 78]},
        ],
    )

    run_dir = run_phase6_nonbubble_cleanup(
        detection_run_dir=detection_run,
        output_root=tmp_path / "outputs",
        run_id="phase6-nonbubble-filtered",
        sample_limit=5,
        record_ids=["page.png#2"],
        inpaint_method="opencv_telea",
    )

    rows = _read_jsonl(run_dir / "cleanup-results.jsonl")
    assert [row["record_id"] for row in rows] == ["page.png#2"]


def test_run_phase6_nonbubble_cleanup_uses_tight_text_bbox(tmp_path: Path):
    image_path = _write_nonbubble_image(tmp_path / "page.png")
    detection_run = tmp_path / "phase2"
    detection_run.mkdir()
    _write_detection(
        detection_run / "detections.jsonl",
        image_path,
        rows=[
            {
                "record_id": "page.png#2",
                "group_name": "框外",
                "selected_text_box_xyxy": [10, 10, 110, 90],
                "candidate_boxes": [
                    {"xyxy": [10, 10, 110, 90], "score": 1.0},
                    {"xyxy": [35, 25, 62, 55], "score": 0.95},
                ],
            },
        ],
    )

    run_dir = run_phase6_nonbubble_cleanup(
        detection_run_dir=detection_run,
        output_root=tmp_path / "outputs",
        run_id="phase6-nonbubble-tight-bbox",
        sample_limit=1,
        inpaint_method="opencv_telea",
    )

    rows = _read_jsonl(run_dir / "cleanup-results.jsonl")
    assert rows[0]["cleanup"]["bbox"] == [35, 25, 62, 55]


def test_run_phase6_nonbubble_cleanup_uses_body_bbox_below_diamond(tmp_path: Path):
    image_path = _write_decorated_nonbubble_caption(tmp_path / "page.png")
    detection_run = tmp_path / "phase2"
    detection_run.mkdir()
    _write_detection(
        detection_run / "detections.jsonl",
        image_path,
        rows=[
            {
                "record_id": "page.png#2",
                "group_name": "框外",
                "selected_text_box_xyxy": [10, 10, 68, 250],
                "candidate_boxes": [
                    {"xyxy": [10, 10, 68, 250], "score": 0.95, "polarity": "dark_on_light"},
                ],
            },
        ],
    )

    run_dir = run_phase6_nonbubble_cleanup(
        detection_run_dir=detection_run,
        output_root=tmp_path / "outputs",
        run_id="phase6-nonbubble-body-bbox",
        sample_limit=1,
        inpaint_method="local_diffusion",
    )

    rows = _read_jsonl(run_dir / "cleanup-results.jsonl")
    assert rows[0]["cleanup"]["bbox"] == [10, 80, 68, 250]


def test_run_phase6_nonbubble_cleanup_uses_selected_candidate_polarity(tmp_path: Path):
    image_path = _write_light_nonbubble_image(tmp_path / "dark-panel.png")
    detection_run = tmp_path / "phase2"
    detection_run.mkdir()
    _write_detection(
        detection_run / "detections.jsonl",
        image_path,
        rows=[
            {
                "record_id": "dark-panel.png#2",
                "group_name": "框外",
                "selected_text_box_xyxy": [30, 20, 80, 60],
                "candidate_boxes": [
                    {
                        "xyxy": [30, 20, 80, 60],
                        "score": 0.95,
                        "polarity": "light_on_dark",
                    }
                ],
            },
        ],
    )

    run_dir = run_phase6_nonbubble_cleanup(
        detection_run_dir=detection_run,
        output_root=tmp_path / "outputs",
        run_id="phase6-nonbubble-light-mask",
        sample_limit=1,
        inpaint_method="local_diffusion",
    )

    rows = _read_jsonl(run_dir / "cleanup-results.jsonl")
    mask_path = Path(rows[0]["cleanup"]["text_mask_path"])
    with Image.open(mask_path) as mask:
        assert mask.getpixel((20, 20)) == 255
        assert mask.getpixel((2, 2)) == 0


def test_run_phase6_nonbubble_cleanup_records_gpt_success_with_fake_client(tmp_path: Path, monkeypatch):
    image_path = _write_nonbubble_image(tmp_path / "page.png")
    detection_run = tmp_path / "phase2"
    detection_run.mkdir()
    _write_detection(detection_run / "detections.jsonl", image_path)
    monkeypatch.setattr("autolettering.phase6_nonbubble.GptImageEditClient", lambda config: _FakeGptClient())
    monkeypatch.setattr(
        "autolettering.inpaint.nonbubble.balloons_lama_large_inpaint",
        lambda crop_arg, mask_arg: Image.new("RGB", crop_arg.size, "white"),
    )

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


def _write_light_nonbubble_image(path: Path) -> Path:
    image = Image.new("RGB", (120, 100), (20, 20, 20))
    draw = ImageDraw.Draw(image)
    draw.rectangle((40, 30, 70, 50), fill="white")
    image.save(path)
    return path


def _write_decorated_nonbubble_caption(path: Path) -> Path:
    image = Image.new("RGB", (80, 280), "white")
    draw = ImageDraw.Draw(image)
    draw.polygon([(39, 16), (64, 41), (39, 66), (14, 41)], fill="black")
    for y in (80, 126, 172, 218):
        draw.rectangle((24, y, 54, y + 6), fill="black")
        draw.rectangle((36, y, 42, y + 30), fill="black")
    image.save(path)
    return path


def _write_detection(path: Path, image_path: Path, rows: list[dict] | None = None) -> None:
    payloads = rows or [
        {"record_id": "page.png#2", "group_name": "框外", "selected_text_box_xyxy": [20, 15, 90, 75]},
    ]
    lines = []
    for payload in payloads:
        row = {
            "status": "ok",
            "image_name": "page.png",
            "image_path": str(image_path),
            "translated_text": "背景文字",
            **payload,
        }
        lines.append(json.dumps(row, ensure_ascii=False))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
