import json
import importlib.util
import inspect
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageChops, ImageDraw

from autolettering.inpaint.nonbubble import build_gpt_edit_mask, build_text_mask, inpaint_crop, inpaint_nonbubble_text
from autolettering.inpaint.balloons import _restore_grayscale_if_mono
from autolettering.inpaint.models import NonBubbleInpaintResult
from autolettering.models.gpt_image import (
    GptImageConfig,
    gpt_image_edit_prompt,
    normalize_gpt_output_to_crop,
    normalize_openai_base_url,
)
from autolettering.phase6_nonbubble import _local_background_color, run_phase6_nonbubble_cleanup
from autolettering.phase6_nonbubble import _refine_fallback_locator_bbox
from autolettering.phase6_nonbubble import _recover_locator_from_labelplus_anchor
from autolettering.phase6_nonbubble import _compose_gpt_replacement_region
from autolettering.phase6_nonbubble import _write_fallback_replacement_crop
from autolettering.phase6_nonbubble import _should_retry_fallback_validation
from autolettering.phase6_nonbubble import _fallback_mask_bbox
from autolettering.phase6_nonbubble import _fallback_validation_payload
from autolettering.phase6_nonbubble import _can_try_anchor_recovery
from autolettering.phase6_nonbubble import _fallback_gpt_cleanup_one


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
    assert "Do not create gray boxes" in prompt
    assert "black-and-white line art" in prompt


def test_gpt_image_prompt_rejects_known_simplified_traditional_glyph_substitutions():
    prompt = gpt_image_edit_prompt("新川崎（暂）")

    assert "Target Chinese text: 新川崎（暂）" in prompt
    assert "The target contains Simplified Chinese `暂`" in prompt
    assert "Do not write `暫`, `仮`, or `哲`" in prompt
    assert "crisp light text on the dark background" in prompt
    assert "match the local perspective" in prompt


def test_gpt_image_prompt_spells_out_repeated_sound_effect_characters():
    prompt = gpt_image_edit_prompt("啪嗒啪嗒啪嗒")

    assert "Target Chinese text: 啪嗒啪嗒啪嗒" in prompt
    assert "Character sequence: 啪 | 嗒 | 啪 | 嗒 | 啪 | 嗒" in prompt
    assert "exactly 6 visible Chinese characters" in prompt


def test_gpt_image_prompt_preserves_non_text_art_inside_wide_mask():
    prompt = gpt_image_edit_prompt("好孩子不要看…")

    assert "detected bbox is only a loose container" in prompt
    assert "Use the bbox only to locate the intended original lettering" in prompt
    assert "If the bbox contains passerby figures" in prompt
    assert "transparent mask indicates candidate original text glyph pixels" in prompt
    assert "If the transparent mask accidentally touches non-text art" in prompt
    assert "Only replace the original Japanese text glyphs" in prompt
    assert "Do not modify any character, passerby, face, body, clothing, hair" in prompt
    assert "person, face, hair, clothing, hands, body" in prompt
    assert "background line art, screentone, panel borders, texture, and motion lines" in prompt
    assert "Do not repaint, erase, blur, white out, or simplify any non-text artwork" in prompt
    assert "Do not move the replacement text to a cleaner nearby speech bubble" in prompt
    assert "single ellipsis glyph `…`" in prompt
    assert "Do not replace `…` with three periods `...`" in prompt


def test_phase6_fallback_does_not_keep_mimo_tightness_retry_prompt():
    source_path = Path(inspect.getsourcefile(run_phase6_nonbubble_cleanup))
    source = source_path.read_text(encoding="utf-8")

    assert "phase6_fallback_text_locator_tightness_retry" not in source
    assert "remove surrounding blank space, characters' hair" not in source


def test_fallback_locator_prompts_allow_loose_bbox_when_it_contains_target_text(tmp_path: Path):
    image_path = _write_nonbubble_image(tmp_path / "page.png")
    detection_run = tmp_path / "phase2"
    detection_run.mkdir()
    _write_detection(
        detection_run / "detections.jsonl",
        image_path,
        rows=[
            {
                "record_id": "page.png#2",
                "status": "fallback_required",
                "group_name": "框外",
                "selected_text_box_xyxy": None,
                "fallback": {
                    "method": "mimo_crop_then_gpt_image2_masked_edit",
                    "context_bbox_xyxy": [10, 10, 100, 80],
                    "translated_text": "背景文字",
                },
            }
        ],
    )
    mimo = _FakeMimoLocatorPromptRecorder()

    run_phase6_nonbubble_cleanup(
        detection_run_dir=detection_run,
        output_root=tmp_path / "outputs",
        run_id="phase6-fallback-loose-prompt-contract",
        sample_limit=1,
        mimo_client=mimo,
    )

    locator_prompt = mimo.prompts["phase6_fallback_text_locator"]
    validation_prompt = mimo.prompts["phase6_fallback_text_locator_validation"]
    assert "bbox may be a loose edit container" in locator_prompt
    assert "must include all visible target text" in locator_prompt
    assert "do not reject or relocate only because it also includes passerby" in validation_prompt
    assert "bbox_targets_unrelated_text=true only when it targets a different text string" in validation_prompt


def test_internal_fallback_gpt_cleanup_defaults_to_text_pixel_mask():
    signature = inspect.signature(_fallback_gpt_cleanup_one)

    assert signature.parameters["gpt_mask_shape"].default == "text_pixels"


def test_semantically_accepted_loose_fallback_bbox_does_not_expand_editable_mask(tmp_path: Path):
    validation = _fallback_validation_payload(
        {
            "semantic_correct": True,
            "tight_enough": False,
            "bbox_on_blank_area": False,
            "bbox_targets_unrelated_text": False,
            "recommendation": "accept",
            "reasoning_summary": "The bbox contains the target text plus extra non-text artwork.",
        },
        {"raw_text": "{}"},
        tmp_path / "validation.png",
    )

    assert validation["status"] == "accepted"
    assert validation["bbox_padding_px"] == 0
    assert validation["needs_tighter_edit_mask"] is False
    assert _fallback_mask_bbox((40, 30, 70, 120), (160, 180), validation) == (40, 30, 70, 120)


def test_semantically_accepted_loose_fallback_bbox_does_not_trigger_anchor_recovery(tmp_path: Path):
    validation = _fallback_validation_payload(
        {
            "semantic_correct": True,
            "tight_enough": False,
            "bbox_on_blank_area": False,
            "bbox_targets_unrelated_text": True,
            "visible_original_text": "スッ スッ スッ スッ",
            "recommendation": "accept",
            "reasoning_summary": "The bbox includes the target text plus a passerby and background art.",
        },
        {"raw_text": "{}"},
        tmp_path / "validation.png",
    )

    assert validation["status"] == "accepted"
    assert validation["needs_tighter_edit_mask"] is False
    assert _can_try_anchor_recovery(validation) is False


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


def test_inpaint_crop_routes_balloon_method_aliases(monkeypatch):
    crop = Image.new("RGB", (12, 10), "black")
    mask = Image.new("L", crop.size, 255)

    monkeypatch.setattr(
        "autolettering.inpaint.nonbubble.balloons_lama_mpe_inpaint",
        lambda crop_arg, mask_arg: Image.new("RGB", crop_arg.size, "white"),
    )

    method, result = inpaint_crop(crop, mask, "lama_mpe")

    assert method == "bt_lama_mpe_inpaint"
    assert result.getpixel((0, 0)) == (255, 255, 255)

    routed_method, _ = inpaint_crop(crop, mask, "opencv-tela")
    assert routed_method == "bt_opencv-tela_actual_cv2_INPAINT_NS"


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


def test_inpaint_crop_supports_texture_blur_fill_for_tall_colored_banner():
    crop = Image.new("RGB", (60, 260), (205, 58, 72))
    draw = ImageDraw.Draw(crop)
    for y in range(0, 260):
        shade = 190 + (y % 18)
        draw.line((0, y, 59, y), fill=(shade, 58, 72))
    for y in range(24, 230, 42):
        draw.rectangle((18, y, 42, y + 24), fill="white")
    mask = Image.new("L", crop.size, 0)
    for y in range(24, 230, 42):
        ImageDraw.Draw(mask).rectangle((18, y, 42, y + 24), fill=255)

    method, result = inpaint_crop(crop, mask, "texture_blur_fill")

    assert method == "texture_blur_fill"
    assert result.getpixel((20, 36)) != (255, 255, 255)
    assert result.getpixel((3, 36)) != crop.getpixel((3, 36))
    assert result.getpixel((30, 250))[0] > 170


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


def test_run_phase6_nonbubble_cleanup_ctd_match_uses_lama_large_and_ctd_mask(tmp_path: Path, monkeypatch):
    image_path = _write_nonbubble_image(tmp_path / "page.png")
    mask_path = tmp_path / "ctd-component-mask.png"
    Image.new("L", (120, 100), 0).save(mask_path)
    detection_run = tmp_path / "phase2"
    detection_run.mkdir()
    _write_detection(
        detection_run / "detections.jsonl",
        image_path,
        rows=[
            {
                "record_id": "page.png#2",
                "group_name": "框外",
                "detection_method": "ctd_mask",
                "selected_text_box_xyxy": [20, 15, 90, 75],
                "ctd_match": {
                    "status": "matched",
                    "mask_path": str(mask_path),
                    "component_id": "component-0001",
                    "bbox_xyxy": [20, 15, 90, 75],
                },
            }
        ],
    )
    calls = {}

    def fake_inpaint(**kwargs):
        calls.update(kwargs)
        output_dir = Path(kwargs["output_dir"])
        cleaned = output_dir / "cleaned.png"
        mask = output_dir / "mask.png"
        gpt_mask = output_dir / "gpt-mask.png"
        before_after = output_dir / "before-after.png"
        input_crop = output_dir / "input.png"
        output_dir.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (70, 60), "white").save(cleaned)
        Image.new("RGB", (70, 60), "black").save(input_crop)
        Image.new("L", (70, 60), 255).save(mask)
        Image.new("RGBA", (70, 60), (0, 0, 0, 0)).save(gpt_mask)
        Image.new("RGB", (140, 60), "white").save(before_after)
        return NonBubbleInpaintResult(
            record_id=kwargs["record_id"],
            method="bt_lama_large_inpaint",
            bbox=kwargs["bbox"],
            input_crop_path=input_crop,
            text_mask_path=mask,
            gpt_mask_path=gpt_mask,
            cleaned_crop_path=cleaned,
            before_after_path=before_after,
            dark_pixel_count=42,
        )

    monkeypatch.setattr("autolettering.phase6_nonbubble.inpaint_nonbubble_text", fake_inpaint)

    run_dir = run_phase6_nonbubble_cleanup(
        detection_run_dir=detection_run,
        output_root=tmp_path / "outputs",
        run_id="phase6-ctd-match",
        sample_limit=1,
        inpaint_method="local_diffusion",
    )

    row = _read_jsonl(run_dir / "cleanup-results.jsonl")[0]
    assert calls["method"] == "lama_large_512px"
    assert calls["text_mask_path"] == str(mask_path)
    assert calls["bbox"] == (20, 15, 90, 75)
    assert row["cleanup"]["method"] == "bt_lama_large_inpaint"
    assert row["cleanup"]["route"] == "cta_mask_lama_large_512px"
    assert row["cleanup"]["text_region_source"] == "ctd_refined_mask_component"
    assert row["cleanup"]["ballonstranslator_detector_module"] == "ctd"
    assert row["cleanup"]["requested_inpaint_method"] == "lama_large_512px"
    assert row["cleanup"]["ballonstranslator_inpainter"] == "lama_large_512px"
    assert row["cleanup"]["actual_inpaint_method"] == "bt_lama_large_inpaint"
    assert row["cleanup"]["source_mask_path"] == str(mask_path)
    assert row["cleanup"]["text_overlay_required"] is True
    assert row["gpt_image2_edit"]["status"] == "not_applicable"
    assert row["gpt_image2_edit"]["reason"] == "cta_mask_matched_inpaint_path"
    assert row["gpt_image2_edit"]["inpaint_method"] == "lama_large_512px"
    assert row["gpt_image2_edit"]["replacement_path"] == "not_used_for_ctd_matched_records"


def test_run_phase6_nonbubble_cleanup_ctd_match_can_experimentally_override_method(tmp_path: Path, monkeypatch):
    image_path = _write_nonbubble_image(tmp_path / "page.png")
    mask_path = tmp_path / "ctd-component-mask.png"
    Image.new("L", (120, 100), 0).save(mask_path)
    detection_run = tmp_path / "phase2"
    detection_run.mkdir()
    _write_detection(
        detection_run / "detections.jsonl",
        image_path,
        rows=[
            {
                "record_id": "page.png#2",
                "group_name": "框外",
                "detection_method": "cta_mask",
                "selected_text_box_xyxy": [20, 15, 90, 75],
                "cta_match": {
                    "status": "matched",
                    "mask_path": str(mask_path),
                    "component_id": "component-0001",
                    "bbox_xyxy": [20, 15, 90, 75],
                },
            }
        ],
    )
    calls = {}

    def fake_inpaint(**kwargs):
        calls.update(kwargs)
        output_dir = Path(kwargs["output_dir"])
        cleaned = output_dir / "cleaned.png"
        mask = output_dir / "mask.png"
        gpt_mask = output_dir / "gpt-mask.png"
        before_after = output_dir / "before-after.png"
        input_crop = output_dir / "input.png"
        output_dir.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (70, 60), "white").save(cleaned)
        Image.new("RGB", (70, 60), "black").save(input_crop)
        Image.new("L", (70, 60), 255).save(mask)
        Image.new("RGBA", (70, 60), (0, 0, 0, 0)).save(gpt_mask)
        Image.new("RGB", (140, 60), "white").save(before_after)
        return NonBubbleInpaintResult(
            record_id=kwargs["record_id"],
            method="bt_patchmatch_inpaint",
            bbox=kwargs["bbox"],
            input_crop_path=input_crop,
            text_mask_path=mask,
            gpt_mask_path=gpt_mask,
            cleaned_crop_path=cleaned,
            before_after_path=before_after,
            dark_pixel_count=42,
        )

    monkeypatch.setattr("autolettering.phase6_nonbubble.inpaint_nonbubble_text", fake_inpaint)

    run_dir = run_phase6_nonbubble_cleanup(
        detection_run_dir=detection_run,
        output_root=tmp_path / "outputs",
        run_id="phase6-cta-method-override",
        sample_limit=1,
        inpaint_method="bt_patchmatch",
        allow_cta_method_override=True,
    )

    row = _read_jsonl(run_dir / "cleanup-results.jsonl")[0]
    assert calls["method"] == "bt_patchmatch"
    assert calls["text_mask_path"] == str(mask_path)
    assert row["cleanup"]["method"] == "bt_patchmatch_inpaint"
    assert row["cleanup"]["route"] == "cta_mask_lama_large_512px"
    assert row["cleanup"]["text_region_source"] == "ctd_refined_mask_component"
    assert row["cleanup"]["requested_inpaint_method"] == "bt_patchmatch"
    assert row["cleanup"]["ballonstranslator_inpainter"] == "bt_patchmatch"
    assert row["cleanup"]["actual_inpaint_method"] == "bt_patchmatch_inpaint"
    assert row["cleanup"]["source_mask_path"] == str(mask_path)
    assert row["gpt_image2_edit"]["status"] == "not_applicable"
    assert row["gpt_image2_edit"]["reason"] == "cta_mask_matched_inpaint_path"
    assert row["gpt_image2_edit"]["inpaint_method"] == "bt_patchmatch"


def test_run_phase6_nonbubble_cleanup_prefers_canonical_text_region_mask_path(tmp_path: Path, monkeypatch):
    image_path = _write_nonbubble_image(tmp_path / "page.png")
    legacy_mask = tmp_path / "legacy-mask.png"
    canonical_mask = tmp_path / "canonical-mask.png"
    Image.new("L", (120, 100), 0).save(legacy_mask)
    Image.new("L", (120, 100), 255).save(canonical_mask)
    detection_run = tmp_path / "phase2"
    detection_run.mkdir()
    _write_detection(
        detection_run / "detections.jsonl",
        image_path,
        rows=[
            {
                "record_id": "page.png#2",
                "group_name": "框外",
                "detection_method": "cta_mask",
                "selected_text_box_xyxy": [20, 15, 90, 75],
                "text_region_mask_path": str(canonical_mask),
                "text_region_mask_bbox_xyxy": [20, 15, 90, 75],
                "cta_match": {
                    "status": "matched",
                    "mask_path": str(legacy_mask),
                    "component_id": "component-0001",
                    "bbox_xyxy": [20, 15, 90, 75],
                },
            }
        ],
    )
    calls = {}

    def fake_inpaint(**kwargs):
        calls.update(kwargs)
        output_dir = Path(kwargs["output_dir"])
        cleaned = output_dir / "cleaned.png"
        mask = output_dir / "mask.png"
        gpt_mask = output_dir / "gpt-mask.png"
        before_after = output_dir / "before-after.png"
        input_crop = output_dir / "input.png"
        output_dir.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (70, 60), "white").save(cleaned)
        Image.new("RGB", (70, 60), "black").save(input_crop)
        Image.new("L", (70, 60), 255).save(mask)
        Image.new("RGBA", (70, 60), (0, 0, 0, 0)).save(gpt_mask)
        Image.new("RGB", (140, 60), "white").save(before_after)
        return NonBubbleInpaintResult(
            record_id=kwargs["record_id"],
            method="bt_lama_large_inpaint",
            bbox=kwargs["bbox"],
            input_crop_path=input_crop,
            text_mask_path=mask,
            gpt_mask_path=gpt_mask,
            cleaned_crop_path=cleaned,
            before_after_path=before_after,
            dark_pixel_count=42,
        )

    monkeypatch.setattr("autolettering.phase6_nonbubble.inpaint_nonbubble_text", fake_inpaint)

    run_phase6_nonbubble_cleanup(
        detection_run_dir=detection_run,
        output_root=tmp_path / "outputs",
        run_id="phase6-canonical-mask",
        sample_limit=1,
    )

    assert calls["text_mask_path"] == str(canonical_mask)


def test_run_phase6_nonbubble_cleanup_prefers_canonical_text_region_bbox(tmp_path: Path, monkeypatch):
    image_path = _write_nonbubble_image(tmp_path / "page.png")
    mask_path = tmp_path / "canonical-mask.png"
    Image.new("L", (120, 100), 255).save(mask_path)
    detection_run = tmp_path / "phase2"
    detection_run.mkdir()
    _write_detection(
        detection_run / "detections.jsonl",
        image_path,
        rows=[
            {
                "record_id": "page.png#2",
                "group_name": "框外",
                "detection_method": "cta_mask",
                "selected_text_box_xyxy": [20, 15, 90, 75],
                "text_region_mask_path": str(mask_path),
                "text_region_mask_bbox_xyxy": [24, 19, 80, 71],
                "cta_match": {
                    "status": "matched",
                    "mask_path": str(mask_path),
                    "component_id": "component-0001",
                    "bbox_xyxy": [20, 15, 90, 75],
                },
            }
        ],
    )
    calls = {}

    def fake_inpaint(**kwargs):
        calls.update(kwargs)
        output_dir = Path(kwargs["output_dir"])
        cleaned = output_dir / "cleaned.png"
        mask = output_dir / "mask.png"
        gpt_mask = output_dir / "gpt-mask.png"
        before_after = output_dir / "before-after.png"
        input_crop = output_dir / "input.png"
        output_dir.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (56, 52), "white").save(cleaned)
        Image.new("RGB", (56, 52), "black").save(input_crop)
        Image.new("L", (56, 52), 255).save(mask)
        Image.new("RGBA", (56, 52), (0, 0, 0, 0)).save(gpt_mask)
        Image.new("RGB", (112, 52), "white").save(before_after)
        return NonBubbleInpaintResult(
            record_id=kwargs["record_id"],
            method="bt_lama_large_inpaint",
            bbox=kwargs["bbox"],
            input_crop_path=input_crop,
            text_mask_path=mask,
            gpt_mask_path=gpt_mask,
            cleaned_crop_path=cleaned,
            before_after_path=before_after,
            dark_pixel_count=42,
        )

    monkeypatch.setattr("autolettering.phase6_nonbubble.inpaint_nonbubble_text", fake_inpaint)

    run_phase6_nonbubble_cleanup(
        detection_run_dir=detection_run,
        output_root=tmp_path / "outputs",
        run_id="phase6-canonical-bbox",
        sample_limit=1,
    )

    assert calls["bbox"] == (24, 19, 80, 71)


def test_run_phase6_nonbubble_cleanup_ctd_match_uses_full_component_bbox_not_trimmed_body(tmp_path: Path, monkeypatch):
    image_path = _write_decorated_nonbubble_caption(tmp_path / "page.png")
    mask_path = tmp_path / "ctd-component-mask.png"
    Image.new("L", (80, 280), 255).save(mask_path)
    detection_run = tmp_path / "phase2"
    detection_run.mkdir()
    _write_detection(
        detection_run / "detections.jsonl",
        image_path,
        rows=[
            {
                "record_id": "page.png#2",
                "group_name": "框外",
                "detection_method": "ctd_mask",
                "selected_text_box_xyxy": [10, 10, 68, 250],
                "ctd_match": {
                    "status": "matched",
                    "mask_path": str(mask_path),
                    "component_id": "component-0001",
                    "bbox_xyxy": [10, 10, 68, 250],
                },
                "candidate_boxes": [
                    {"xyxy": [10, 10, 68, 250], "score": 1.0, "polarity": "dark_on_light"},
                ],
            }
        ],
    )
    calls = {}

    def fake_inpaint(**kwargs):
        calls.update(kwargs)
        output_dir = Path(kwargs["output_dir"])
        cleaned = output_dir / "cleaned.png"
        mask = output_dir / "mask.png"
        gpt_mask = output_dir / "gpt-mask.png"
        before_after = output_dir / "before-after.png"
        input_crop = output_dir / "input.png"
        output_dir.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (58, 240), "white").save(cleaned)
        Image.new("RGB", (58, 240), "black").save(input_crop)
        Image.new("L", (58, 240), 255).save(mask)
        Image.new("RGBA", (58, 240), (0, 0, 0, 0)).save(gpt_mask)
        Image.new("RGB", (116, 240), "white").save(before_after)
        return NonBubbleInpaintResult(
            record_id=kwargs["record_id"],
            method="bt_lama_large_inpaint",
            bbox=kwargs["bbox"],
            input_crop_path=input_crop,
            text_mask_path=mask,
            gpt_mask_path=gpt_mask,
            cleaned_crop_path=cleaned,
            before_after_path=before_after,
            dark_pixel_count=42,
        )

    monkeypatch.setattr("autolettering.phase6_nonbubble.inpaint_nonbubble_text", fake_inpaint)

    run_phase6_nonbubble_cleanup(
        detection_run_dir=detection_run,
        output_root=tmp_path / "outputs",
        run_id="phase6-ctd-full-bbox",
        sample_limit=1,
        inpaint_method="local_diffusion",
    )

    assert calls["bbox"] == (10, 10, 68, 250)


def test_refine_fallback_locator_bbox_trims_adjacent_white_bubble_from_dark_card(tmp_path: Path):
    context_path = tmp_path / "context.png"
    image = Image.new("RGB", (440, 440), "white")
    draw = ImageDraw.Draw(image)
    draw.polygon([(120, 92), (292, 116), (272, 338), (86, 308)], fill="black")
    draw.rectangle((352, 90, 430, 270), fill="white")
    draw.text((154, 190), "Shinkawasaki", fill="white")
    draw.text((354, 120), "すって", fill="black")
    image.save(context_path)
    locator = {
        "status": "ok",
        "local_bbox_xyxy": [150, 186, 396, 245],
        "global_bbox_xyxy": [1003, 238, 1249, 297],
    }

    refined = _refine_fallback_locator_bbox(locator, context_path, (853, 52, 1293, 492))

    assert refined["local_bbox_xyxy"][0] == 150
    assert refined["local_bbox_xyxy"][2] <= 302
    assert refined["global_bbox_xyxy"][2] <= 1155
    assert refined["refinement"]["method"] == "trim_to_dark_background_support"
    assert refined["refinement"]["original_local_bbox_xyxy"] == [150, 186, 396, 245]


def test_refine_fallback_locator_bbox_trims_light_background_sound_effect_band(tmp_path: Path):
    context_path = tmp_path / "context.png"
    image = Image.new("RGB", (660, 660), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 659, 659), outline=(20, 20, 20), width=4)
    for left in (60, 170, 280, 390, 500):
        draw.polygon(
            [(left, 72), (left + 86, 56), (left + 98, 88), (left + 16, 104)],
            fill=(22, 22, 22),
        )
        draw.rectangle((left + 18, 102, left + 88, 136), fill=(25, 25, 25))
        draw.rectangle((left + 36, 86, left + 108, 116), fill=(24, 24, 24))
        draw.rectangle((left + 32, 93, left + 84, 110), fill="white")
    for x in range(90, 620, 34):
        draw.line((x, 328, x - 42, 600), fill=(92, 92, 92), width=2)
    draw.arc((118, 290, 552, 820), start=192, end=346, fill=(36, 36, 36), width=3)
    image.save(context_path)
    locator = {
        "status": "ok",
        "local_bbox_xyxy": [35, 45, 615, 585],
        "global_bbox_xyxy": [353, 1046, 933, 1586],
    }

    refined = _refine_fallback_locator_bbox(locator, context_path, (318, 1001, 970, 1653))

    assert refined["local_bbox_xyxy"][1] <= 64
    assert refined["local_bbox_xyxy"][3] <= 156
    assert refined["local_bbox_xyxy"][2] >= 580
    assert refined["global_bbox_xyxy"][3] <= 1157
    assert refined["refinement"]["method"] == "trim_to_light_text_ink_support"
    assert refined["refinement"]["original_local_bbox_xyxy"] == [35, 45, 615, 585]


def test_refine_fallback_locator_bbox_trims_dark_vertical_text_column(tmp_path: Path):
    context_path = _write_dark_vertical_text_near_anchor_panel(tmp_path / "context.png")
    locator = {
        "status": "ok",
        "local_bbox_xyxy": [74, 35, 132, 210],
        "global_bbox_xyxy": [74, 35, 132, 210],
    }

    refined = _refine_fallback_locator_bbox(locator, context_path, (0, 0, 220, 220))

    assert refined["local_bbox_xyxy"][0] >= 80
    assert refined["local_bbox_xyxy"][2] <= 118
    assert refined["local_bbox_xyxy"][1] <= 45
    assert refined["local_bbox_xyxy"][3] <= 156
    assert refined["refinement"]["method"] == "trim_to_dark_vertical_text_column_support"
    assert refined["refinement"]["original_local_bbox_xyxy"] == [74, 35, 132, 210]


def test_refine_fallback_locator_bbox_keeps_wide_bbox_when_trim_would_drop_target_column(tmp_path: Path):
    context_path = tmp_path / "context.png"
    image = Image.new("RGB", (140, 220), "white")
    draw = ImageDraw.Draw(image)
    for y in (38, 72, 106, 140, 174):
        draw.rectangle((22, y, 42, y + 9), fill=(25, 25, 25))
        draw.line((28, y - 8, 28, y + 20), fill=(25, 25, 25), width=3)
    for y in range(42, 182, 22):
        draw.rectangle((88, y, 110, y + 15), fill=(8, 8, 8))
    image.save(context_path)
    locator = {
        "status": "ok",
        "local_bbox_xyxy": [12, 24, 124, 208],
        "global_bbox_xyxy": [12, 24, 124, 208],
    }

    refined = _refine_fallback_locator_bbox(locator, context_path, (0, 0, 140, 220))

    assert refined["local_bbox_xyxy"] == [12, 24, 124, 208]
    assert "refinement" not in refined


def test_run_phase6_nonbubble_cleanup_fallback_uses_mimo_bbox_and_gpt_mask(tmp_path: Path, monkeypatch):
    image_path = _write_nonbubble_image(tmp_path / "page.png")
    detection_run = tmp_path / "phase2"
    detection_run.mkdir()
    _write_detection(
        detection_run / "detections.jsonl",
        image_path,
        rows=[
            {
                "record_id": "page.png#2",
                "status": "fallback_required",
                "group_name": "框外",
                "selected_text_box_xyxy": None,
                "failure_reason": "no_ctd_mask_within_threshold",
                "fallback": {
                    "method": "mimo_crop_then_gpt_image2_masked_edit",
                    "context_bbox_xyxy": [10, 10, 100, 80],
                    "labelplus_point_xy": [48, 38],
                    "context_labelplus_point_xy": [38, 28],
                    "translated_text": "背景文字",
                },
            }
        ],
    )
    monkeypatch.setattr("autolettering.phase6_nonbubble.GptImageEditClient", lambda config: _FakeGptClient())

    run_dir = run_phase6_nonbubble_cleanup(
        detection_run_dir=detection_run,
        output_root=tmp_path / "outputs",
        run_id="phase6-fallback-gpt",
        sample_limit=1,
        gpt_config=GptImageConfig(base_url="https://example.test/v1/images", api_key="test", model="gpt-image-2"),
        call_gpt_image=True,
        mimo_client=_FakeMimoLocator(),
    )

    row = _read_jsonl(run_dir / "cleanup-results.jsonl")[0]
    assert (run_dir / "visuals" / "fallback-locator-grid.png").exists()
    replacement_grid = run_dir / "visuals" / "fallback-replacement-grid.png"
    assert replacement_grid.exists()
    with Image.open(replacement_grid) as grid:
        ratio = grid.width / grid.height
        assert 0.45 <= ratio <= 2.2
    assert row["status"] == "cleaned"
    assert row["cleanup"]["method"] == "bt_lama_large_inpaint"
    assert row["cleanup"]["bbox"] == [10, 10, 100, 80]
    assert row["cleanup"]["layout_text_bbox"] == [35, 25, 62, 55]
    _assert_fallback_background_repaired(row)
    assert row["fallback_locator"]["status"] == "ok"
    assert Path(row["fallback_locator"]["locator_image_path"]).parent.name == "fallback_locator_input"
    assert row["fallback_locator_validation"]["status"] == "accepted"
    assert Path(row["fallback_locator_validation"]["validation_image_path"]).exists()
    assert row["gpt_image2_edit"]["status"] == "ok"
    assert Path(row["gpt_image2_edit"]["request"]["image_path"]).parent.name == "fallback_edit_input"
    assert Path(row["cleanup"]["replacement_crop_path"]).parent.name == "fallback_replacement_crop"
    assert row["gpt_image2_edit"]["request"]["target_size"] == [59, 61]
    assert row["gpt_image2_edit"]["edit_context"]["local_context_bbox"] == [9, 0, 68, 61]
    with Image.open(row["fallback_locator"]["locator_image_path"]).convert("RGB") as locator_image:
        assert _has_reddish_pixel(locator_image)
    with Image.open(row["gpt_image2_edit"]["request"]["mask_path"]) as mask:
        assert mask.size == (59, 61)
        assert _has_editable_pixel(mask)
        assert mask.getpixel((0, 0))[3] == 255
    with Image.open(row["cleanup"]["cleaned_crop_path"]).convert("RGB") as original:
        with Image.open(row["cleanup"]["replacement_crop_path"]).convert("RGB") as replacement:
            assert replacement.getpixel((0, 0)) == original.getpixel((0, 0))
            assert ImageChops.difference(original, replacement).getbbox() is not None


def test_run_phase6_nonbubble_cleanup_fallback_accepts_edit_padding_and_mask_expand(tmp_path: Path, monkeypatch):
    image_path = _write_nonbubble_image(tmp_path / "page.png")
    detection_run = tmp_path / "phase2"
    detection_run.mkdir()
    _write_detection(
        detection_run / "detections.jsonl",
        image_path,
        rows=[
            {
                "record_id": "page.png#2",
                "status": "fallback_required",
                "group_name": "框外",
                "selected_text_box_xyxy": None,
                "failure_reason": "no_ctd_mask_within_threshold",
                "fallback": {
                    "method": "mimo_crop_then_gpt_image2_masked_edit",
                    "context_bbox_xyxy": [10, 10, 100, 80],
                    "labelplus_point_xy": [48, 38],
                    "context_labelplus_point_xy": [38, 28],
                    "translated_text": "背景文字",
                },
            }
        ],
    )
    monkeypatch.setattr("autolettering.phase6_nonbubble.GptImageEditClient", lambda config: _FakeGptClient())

    run_dir = run_phase6_nonbubble_cleanup(
        detection_run_dir=detection_run,
        output_root=tmp_path / "outputs",
        run_id="phase6-fallback-gpt-expanded-mask",
        sample_limit=1,
        gpt_config=GptImageConfig(base_url="https://example.test/v1/images", api_key="test", model="gpt-image-2"),
        call_gpt_image=True,
        mimo_client=_FakeMimoLocator(),
        fallback_edit_padding_px=24,
        fallback_mask_expand_px=8,
    )

    row = _read_jsonl(run_dir / "cleanup-results.jsonl")[0]
    assert row["cleanup"]["mask_bbox"] == [27, 17, 70, 63]
    assert row["gpt_image2_edit"]["request"]["target_size"] == [84, 70]
    assert row["gpt_image2_edit"]["edit_context"]["local_context_bbox"] == [0, 0, 84, 70]
    with Image.open(row["gpt_image2_edit"]["request"]["mask_path"]) as mask:
        assert mask.size == (84, 70)
        assert _has_editable_pixel(mask)
        assert mask.getpixel((4, 4))[3] == 255


def test_run_phase6_nonbubble_cleanup_fallback_can_use_text_ink_gpt_mask(tmp_path: Path, monkeypatch):
    image_path = _write_sparse_ink_nonbubble_image(tmp_path / "page.png")
    detection_run = tmp_path / "phase2"
    detection_run.mkdir()
    _write_detection(
        detection_run / "detections.jsonl",
        image_path,
        rows=[
            {
                "record_id": "page.png#2",
                "status": "fallback_required",
                "group_name": "框外",
                "selected_text_box_xyxy": None,
                "failure_reason": "no_ctd_mask_within_threshold",
                "fallback": {
                    "method": "mimo_crop_then_gpt_image2_masked_edit",
                    "context_bbox_xyxy": [10, 10, 100, 80],
                    "labelplus_point_xy": [48, 38],
                    "context_labelplus_point_xy": [38, 28],
                    "translated_text": "背景文字",
                },
            }
        ],
    )
    monkeypatch.setattr("autolettering.phase6_nonbubble.GptImageEditClient", lambda config: _FakeGptClient())

    run_dir = run_phase6_nonbubble_cleanup(
        detection_run_dir=detection_run,
        output_root=tmp_path / "outputs",
        run_id="phase6-fallback-gpt-text-ink-mask",
        sample_limit=1,
        gpt_config=GptImageConfig(base_url="https://example.test/v1/images", api_key="test", model="gpt-image-2"),
        call_gpt_image=True,
        mimo_client=_FakeMimoLocator(),
        fallback_gpt_mask_shape="text_ink",
    )

    row = _read_jsonl(run_dir / "cleanup-results.jsonl")[0]
    assert row["cleanup"]["gpt_mask_shape"] == "text_ink"
    assert row["gpt_image2_edit"]["edit_context"]["gpt_mask_shape"] == "text_ink"
    with Image.open(row["gpt_image2_edit"]["request"]["mask_path"]) as mask:
        assert mask.size == (59, 61)
        assert mask.getpixel((27, 30))[3] == 0
        assert mask.getpixel((16, 15))[3] == 255
        assert mask.getpixel((52, 52))[3] == 255


def test_run_phase6_nonbubble_cleanup_fallback_accepts_mimo_bbox_array_response(tmp_path: Path, monkeypatch):
    image_path = _write_nonbubble_image(tmp_path / "page.png")
    detection_run = tmp_path / "phase2"
    detection_run.mkdir()
    _write_detection(
        detection_run / "detections.jsonl",
        image_path,
        rows=[
            {
                "record_id": "page.png#2",
                "status": "fallback_required",
                "group_name": "框外",
                "selected_text_box_xyxy": None,
                "fallback": {
                    "method": "mimo_crop_then_gpt_image2_masked_edit",
                    "context_bbox_xyxy": [10, 10, 100, 80],
                    "translated_text": "背景文字",
                },
            }
        ],
    )
    monkeypatch.setattr("autolettering.phase6_nonbubble.GptImageEditClient", lambda config: _FakeGptClient())

    run_dir = run_phase6_nonbubble_cleanup(
        detection_run_dir=detection_run,
        output_root=tmp_path / "outputs",
        run_id="phase6-fallback-gpt-array",
        sample_limit=1,
        gpt_config=GptImageConfig(base_url="https://example.test/v1/images", api_key="test", model="gpt-image-2"),
        call_gpt_image=True,
        mimo_client=_FakeMimoLocatorArray(),
    )

    row = _read_jsonl(run_dir / "cleanup-results.jsonl")[0]
    assert row["fallback_locator"]["status"] == "ok"
    assert row["fallback_locator_validation"]["status"] == "accepted"
    assert row["cleanup"]["layout_text_bbox"] == [35, 25, 62, 55]
    assert row["gpt_image2_edit"]["status"] == "ok"


def test_run_phase6_nonbubble_cleanup_fallback_accepts_mimo_percent_bbox(tmp_path: Path):
    image_path = _write_nonbubble_image(tmp_path / "page.png")
    detection_run = tmp_path / "phase2"
    detection_run.mkdir()
    _write_detection(
        detection_run / "detections.jsonl",
        image_path,
        rows=[
            {
                "record_id": "page.png#2",
                "status": "fallback_required",
                "group_name": "框外",
                "selected_text_box_xyxy": None,
                "fallback": {
                    "method": "mimo_crop_then_gpt_image2_masked_edit",
                    "context_bbox_xyxy": [10, 10, 100, 80],
                    "translated_text": "背景文字",
                },
            }
        ],
    )

    run_dir = run_phase6_nonbubble_cleanup(
        detection_run_dir=detection_run,
        output_root=tmp_path / "outputs",
        run_id="phase6-fallback-percent",
        sample_limit=1,
        mimo_client=_FakeMimoLocatorPercent(),
    )

    row = _read_jsonl(run_dir / "cleanup-results.jsonl")[0]
    assert row["fallback_locator"]["status"] == "ok"
    assert row["fallback_locator_validation"]["status"] == "accepted"
    assert row["fallback_locator"]["local_bbox_xyxy"] == [25, 15, 52, 45]
    assert row["cleanup"]["layout_text_bbox"] == [35, 25, 62, 55]
    assert row["status"] == "cleaned"
    assert row["cleanup"]["text_overlay_required"] is True
    assert "failure_reason" not in row["cleanup"]
    assert row["cleanup"]["replacement_failure_reason"] == "gpt_image2_replacement_not_completed"
    assert "replacement_method" not in row["cleanup"]
    _assert_fallback_background_repaired(row)
    assert row["gpt_image2_edit"]["status"] == "dry_run"


def test_run_phase6_nonbubble_cleanup_fallback_writes_repaired_background_before_gpt_acceptance(tmp_path: Path):
    image_path = _write_nonbubble_image(tmp_path / "page.png")
    detection_run = tmp_path / "phase2"
    detection_run.mkdir()
    _write_detection(
        detection_run / "detections.jsonl",
        image_path,
        rows=[
            {
                "record_id": "page.png#2",
                "status": "fallback_required",
                "group_name": "框外",
                "selected_text_box_xyxy": None,
                "fallback": {
                    "method": "mimo_crop_then_gpt_image2_masked_edit",
                    "context_bbox_xyxy": [10, 10, 100, 80],
                    "translated_text": "背景文字",
                },
            }
        ],
    )

    run_dir = run_phase6_nonbubble_cleanup(
        detection_run_dir=detection_run,
        output_root=tmp_path / "outputs",
        run_id="phase6-fallback-background-before-gpt",
        sample_limit=1,
        mimo_client=_FakeMimoLocatorPercent(),
    )

    row = _read_jsonl(run_dir / "cleanup-results.jsonl")[0]
    cleanup = row["cleanup"]
    assert row["status"] == "cleaned"
    assert cleanup["text_overlay_required"] is True
    assert cleanup["replacement_failure_reason"] == "gpt_image2_replacement_not_completed"
    _assert_fallback_background_repaired(row)
    assert "replacement_method" not in cleanup
    assert row["gpt_image2_edit"]["status"] == "dry_run"
    with Image.open(cleanup["cleaned_crop_path"]).convert("RGB") as repaired:
        assert repaired.size == (90, 70)


def test_run_phase6_nonbubble_cleanup_fallback_uses_percent_bbox_when_pixel_bbox_is_out_of_bounds(tmp_path: Path):
    image_path = _write_nonbubble_image(tmp_path / "page.png")
    detection_run = tmp_path / "phase2"
    detection_run.mkdir()
    _write_detection(
        detection_run / "detections.jsonl",
        image_path,
        rows=[
            {
                "record_id": "page.png#2",
                "status": "fallback_required",
                "group_name": "框外",
                "selected_text_box_xyxy": None,
                "fallback": {
                    "method": "mimo_crop_then_gpt_image2_masked_edit",
                    "context_bbox_xyxy": [10, 10, 100, 80],
                    "translated_text": "背景文字",
                },
            }
        ],
    )
    mimo = _FakeMimoLocatorPixelOutPercentOk()

    run_dir = run_phase6_nonbubble_cleanup(
        detection_run_dir=detection_run,
        output_root=tmp_path / "outputs",
        run_id="phase6-fallback-pixel-out-percent-ok",
        sample_limit=1,
        mimo_client=mimo,
    )

    row = _read_jsonl(run_dir / "cleanup-results.jsonl")[0]
    assert mimo.kinds == ["phase6_fallback_text_locator", "phase6_fallback_text_locator_validation"]
    assert row["fallback_locator"]["status"] == "ok"
    assert row["fallback_locator"]["local_bbox_xyxy"] == [25, 15, 52, 45]
    assert row["fallback_locator"]["bbox_coordinate_source"] == "bbox_percent_xyxy"
    assert row["fallback_locator_validation"]["status"] == "accepted"


def test_run_phase6_nonbubble_cleanup_fallback_retries_invalid_mimo_bbox(tmp_path: Path):
    image_path = _write_nonbubble_image(tmp_path / "page.png")
    detection_run = tmp_path / "phase2"
    detection_run.mkdir()
    _write_detection(
        detection_run / "detections.jsonl",
        image_path,
        rows=[
            {
                "record_id": "page.png#2",
                "status": "fallback_required",
                "group_name": "框外",
                "selected_text_box_xyxy": None,
                "fallback": {
                    "method": "mimo_crop_then_gpt_image2_masked_edit",
                    "context_bbox_xyxy": [10, 10, 100, 80],
                    "translated_text": "背景文字",
                },
            }
        ],
    )
    mimo = _FakeMimoLocatorRetry()

    run_dir = run_phase6_nonbubble_cleanup(
        detection_run_dir=detection_run,
        output_root=tmp_path / "outputs",
        run_id="phase6-fallback-retry",
        sample_limit=1,
        mimo_client=mimo,
    )

    row = _read_jsonl(run_dir / "cleanup-results.jsonl")[0]
    assert mimo.kinds == [
        "phase6_fallback_text_locator",
        "phase6_fallback_text_locator_retry",
        "phase6_fallback_text_locator_validation",
    ]
    assert row["status"] == "cleaned"
    assert row["fallback_locator"]["retry_of_error"] == "ValueError"
    assert row["fallback_locator"]["local_bbox_xyxy"] == [25, 15, 52, 45]
    assert row["fallback_locator_validation"]["status"] == "accepted"
    assert row["cleanup"]["text_overlay_required"] is True
    assert row["cleanup"]["replacement_failure_reason"] == "gpt_image2_replacement_not_completed"
    assert "replacement_method" not in row["cleanup"]
    _assert_fallback_background_repaired(row)
    assert row["gpt_image2_edit"]["status"] == "dry_run"


def test_run_phase6_nonbubble_cleanup_fallback_recovers_json_object_with_trailing_bracket(tmp_path: Path):
    image_path = _write_nonbubble_image(tmp_path / "page.png")
    detection_run = tmp_path / "phase2"
    detection_run.mkdir()
    _write_detection(
        detection_run / "detections.jsonl",
        image_path,
        rows=[
            {
                "record_id": "page.png#2",
                "status": "fallback_required",
                "group_name": "框外",
                "selected_text_box_xyxy": None,
                "fallback": {
                    "method": "mimo_crop_then_gpt_image2_masked_edit",
                    "context_bbox_xyxy": [10, 10, 100, 80],
                    "translated_text": "背景文字",
                },
            }
        ],
    )
    mimo = _FakeMimoLocatorTrailingBracket()

    run_dir = run_phase6_nonbubble_cleanup(
        detection_run_dir=detection_run,
        output_root=tmp_path / "outputs",
        run_id="phase6-fallback-trailing-bracket",
        sample_limit=1,
        mimo_client=mimo,
    )

    row = _read_jsonl(run_dir / "cleanup-results.jsonl")[0]
    assert mimo.kinds == ["phase6_fallback_text_locator", "phase6_fallback_text_locator_validation"]
    assert row["fallback_locator"]["status"] == "ok"
    assert row["fallback_locator"]["local_bbox_xyxy"] == [25, 15, 52, 45]
    assert "retry_of_error" not in row["fallback_locator"]
    assert row["fallback_locator_validation"]["status"] == "accepted"


def test_run_phase6_nonbubble_cleanup_fallback_accepts_nested_mimo_bbox(tmp_path: Path):
    image_path = _write_nonbubble_image(tmp_path / "page.png")
    detection_run = tmp_path / "phase2"
    detection_run.mkdir()
    _write_detection(
        detection_run / "detections.jsonl",
        image_path,
        rows=[
            {
                "record_id": "page.png#2",
                "status": "fallback_required",
                "group_name": "框外",
                "selected_text_box_xyxy": None,
                "fallback": {
                    "method": "mimo_crop_then_gpt_image2_masked_edit",
                    "context_bbox_xyxy": [10, 10, 100, 80],
                    "translated_text": "背景文字",
                },
            }
        ],
    )

    run_dir = run_phase6_nonbubble_cleanup(
        detection_run_dir=detection_run,
        output_root=tmp_path / "outputs",
        run_id="phase6-fallback-nested-bbox",
        sample_limit=1,
        mimo_client=_FakeMimoLocatorNestedBbox(),
    )

    row = _read_jsonl(run_dir / "cleanup-results.jsonl")[0]
    assert row["fallback_locator"]["status"] == "ok"
    assert row["fallback_locator"]["local_bbox_xyxy"] == [25, 15, 52, 45]
    assert row["fallback_locator_validation"]["status"] == "accepted"
    assert row["status"] == "cleaned"
    assert row["cleanup"]["text_overlay_required"] is True
    assert row["cleanup"]["replacement_failure_reason"] == "gpt_image2_replacement_not_completed"
    assert "replacement_method" not in row["cleanup"]
    _assert_fallback_background_repaired(row)
    assert row["gpt_image2_edit"]["status"] == "dry_run"


def test_run_phase6_nonbubble_cleanup_fallback_retries_inconclusive_semantic_validation(tmp_path: Path):
    image_path = _write_nonbubble_image(tmp_path / "page.png")
    detection_run = tmp_path / "phase2"
    detection_run.mkdir()
    _write_detection(
        detection_run / "detections.jsonl",
        image_path,
        rows=[
            {
                "record_id": "page.png#2",
                "status": "fallback_required",
                "group_name": "框外",
                "selected_text_box_xyxy": None,
                "fallback": {
                    "method": "mimo_crop_then_gpt_image2_masked_edit",
                    "context_bbox_xyxy": [10, 10, 100, 80],
                    "translated_text": "背景文字",
                },
            }
        ],
    )
    mimo = _FakeMimoLocatorValidationRetry()

    run_dir = run_phase6_nonbubble_cleanup(
        detection_run_dir=detection_run,
        output_root=tmp_path / "outputs",
        run_id="phase6-fallback-validation-retry",
        sample_limit=1,
        mimo_client=mimo,
    )

    row = _read_jsonl(run_dir / "cleanup-results.jsonl")[0]
    assert mimo.kinds == [
        "phase6_fallback_text_locator",
        "phase6_fallback_text_locator_validation",
        "phase6_fallback_text_locator_validation_retry",
    ]
    assert row["status"] == "cleaned"
    assert row["fallback_locator_validation"]["status"] == "accepted"
    assert row["fallback_locator_validation"]["retry_of_error"] == "semantic_validation_inconclusive"
    assert row["cleanup"]["text_overlay_required"] is True
    assert row["cleanup"]["replacement_failure_reason"] == "gpt_image2_replacement_not_completed"
    assert "replacement_method" not in row["cleanup"]
    _assert_fallback_background_repaired(row)
    assert row["gpt_image2_edit"]["status"] == "dry_run"


def test_run_phase6_nonbubble_cleanup_fallback_retries_locator_after_semantic_rejection(tmp_path: Path):
    image_path = _write_nonbubble_image(tmp_path / "page.png")
    detection_run = tmp_path / "phase2"
    detection_run.mkdir()
    _write_detection(
        detection_run / "detections.jsonl",
        image_path,
        rows=[
            {
                "record_id": "page.png#2",
                "status": "fallback_required",
                "group_name": "框外",
                "selected_text_box_xyxy": None,
                "fallback": {
                    "method": "mimo_crop_then_gpt_image2_masked_edit",
                    "context_bbox_xyxy": [10, 10, 100, 80],
                    "translated_text": "背景文字",
                },
            }
        ],
    )
    mimo = _FakeMimoLocatorSemanticLocatorRetry()

    run_dir = run_phase6_nonbubble_cleanup(
        detection_run_dir=detection_run,
        output_root=tmp_path / "outputs",
        run_id="phase6-fallback-semantic-locator-retry",
        sample_limit=1,
        mimo_client=mimo,
    )

    row = _read_jsonl(run_dir / "cleanup-results.jsonl")[0]
    assert mimo.kinds == [
        "phase6_fallback_text_locator",
        "phase6_fallback_text_locator_validation",
        "phase6_fallback_text_locator_semantic_retry",
        "phase6_fallback_text_locator_validation",
    ]
    assert row["fallback_locator"]["status"] == "ok"
    assert row["fallback_locator"]["local_bbox_xyxy"] == [25, 15, 52, 45]
    assert row["fallback_locator"]["semantic_retry_of_validation"] == "fallback_locator_semantic_rejected"
    assert row["fallback_locator_validation"]["status"] == "accepted"
    assert row["status"] == "cleaned"
    assert row["cleanup"]["replacement_failure_reason"] == "gpt_image2_replacement_not_completed"
    assert "replacement_method" not in row["cleanup"]
    _assert_fallback_background_repaired(row)
    assert row["gpt_image2_edit"]["status"] == "dry_run"


def test_run_phase6_nonbubble_cleanup_fallback_keeps_semantically_accepted_loose_bbox(tmp_path: Path):
    image_path = _write_nonbubble_image(tmp_path / "page.png")
    detection_run = tmp_path / "phase2"
    detection_run.mkdir()
    _write_detection(
        detection_run / "detections.jsonl",
        image_path,
        rows=[
            {
                "record_id": "page.png#2",
                "status": "fallback_required",
                "group_name": "框外",
                "selected_text_box_xyxy": None,
                "fallback": {
                    "method": "mimo_crop_then_gpt_image2_masked_edit",
                    "context_bbox_xyxy": [10, 10, 100, 80],
                    "translated_text": "背景文字",
                },
            }
        ],
    )
    mimo = _FakeMimoLocatorTightnessRetry()

    run_dir = run_phase6_nonbubble_cleanup(
        detection_run_dir=detection_run,
        output_root=tmp_path / "outputs",
        run_id="phase6-fallback-tightness-retry",
        sample_limit=1,
        mimo_client=mimo,
    )

    row = _read_jsonl(run_dir / "cleanup-results.jsonl")[0]
    assert mimo.kinds == [
        "phase6_fallback_text_locator",
        "phase6_fallback_text_locator_validation",
    ]
    assert row["fallback_locator"]["status"] == "ok"
    assert row["fallback_locator"]["local_bbox_xyxy"] == [5, 8, 84, 62]
    assert "tightness_retry_of_validation" not in row["fallback_locator"]
    assert row["fallback_locator_validation"]["status"] == "accepted"
    assert row["fallback_locator_validation"]["tight_enough"] is False
    assert row["cleanup"]["layout_text_bbox"] == [15, 18, 94, 72]
    assert row["gpt_image2_edit"]["status"] == "dry_run"


def test_run_phase6_nonbubble_cleanup_does_not_refine_semantically_accepted_bbox(tmp_path: Path):
    image_path = tmp_path / "page.png"
    image = Image.new("RGB", (160, 160), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((30, 42, 124, 110), fill=(250, 250, 250))
    _draw_fake_text_strokes(draw, origin=(56, 58))
    image.save(image_path)
    detection_run = tmp_path / "phase2"
    detection_run.mkdir()
    _write_detection(
        detection_run / "detections.jsonl",
        image_path,
        rows=[
            {
                "record_id": "page.png#2",
                "status": "fallback_required",
                "group_name": "框外",
                "selected_text_box_xyxy": None,
                "fallback": {
                    "method": "mimo_crop_then_gpt_image2_masked_edit",
                    "context_bbox_xyxy": [0, 0, 160, 160],
                    "context_labelplus_point_xy": [80, 82],
                    "translated_text": "背景文字",
                },
            }
        ],
    )
    mimo = _FakeMimoLocatorLooseAcceptedWideInkBand()

    run_dir = run_phase6_nonbubble_cleanup(
        detection_run_dir=detection_run,
        output_root=tmp_path / "outputs",
        run_id="phase6-fallback-accepted-wide-bbox-not-refined",
        sample_limit=1,
        mimo_client=mimo,
    )

    row = _read_jsonl(run_dir / "cleanup-results.jsonl")[0]
    assert mimo.kinds == [
        "phase6_fallback_text_locator",
        "phase6_fallback_text_locator_validation",
    ]
    assert row["fallback_locator"]["local_bbox_xyxy"] == [20, 30, 130, 130]
    assert "refinement" not in row["fallback_locator"]
    assert row["cleanup"]["layout_text_bbox"] == [20, 30, 130, 130]
    assert row["gpt_image2_edit"]["edit_context"]["mask_strategy"] == "text_pixels_within_bbox"


def test_run_phase6_nonbubble_cleanup_fallback_calls_gpt_when_accepted_bbox_stays_loose(
    tmp_path: Path,
    monkeypatch,
):
    image_path = _write_nonbubble_image(tmp_path / "page.png")
    detection_run = tmp_path / "phase2"
    detection_run.mkdir()
    _write_detection(
        detection_run / "detections.jsonl",
        image_path,
        rows=[
            {
                "record_id": "page.png#2",
                "status": "fallback_required",
                "group_name": "框外",
                "selected_text_box_xyxy": None,
                "fallback": {
                    "method": "mimo_crop_then_gpt_image2_masked_edit",
                    "context_bbox_xyxy": [10, 10, 100, 80],
                    "translated_text": "背景文字",
                },
            }
        ],
    )
    calls = {"gpt": 0}

    class FakeGptClient:
        def edit_image(self, image_path: str, mask_path: str, prompt: str, output_path: str) -> dict:
            calls["gpt"] += 1
            return _FakeGptClient().edit_image(image_path, mask_path, prompt, output_path)

    monkeypatch.setattr("autolettering.phase6_nonbubble.GptImageEditClient", lambda config: FakeGptClient())

    mimo = _FakeMimoLocatorLooseAcceptedStillLoose()
    run_dir = run_phase6_nonbubble_cleanup(
        detection_run_dir=detection_run,
        output_root=tmp_path / "outputs",
        run_id="phase6-fallback-loose-accepted-gpt",
        sample_limit=1,
        gpt_config=GptImageConfig(base_url="https://example.test/v1/images", api_key="test", model="gpt-image-2"),
        call_gpt_image=True,
        mimo_client=mimo,
    )

    row = _read_jsonl(run_dir / "cleanup-results.jsonl")[0]
    assert calls["gpt"] == 1
    assert "phase6_fallback_text_locator_tightness_retry" not in mimo.kinds
    assert row["status"] == "cleaned"
    assert row["cleanup"]["replacement_method"] == "gpt_image2_masked_edit"
    assert row["cleanup"]["gpt_mask_shape"] == "text_pixels"
    assert row["fallback_locator_validation"]["status"] == "accepted"
    assert row["fallback_locator_validation"]["tight_enough"] is False
    assert row["gpt_image2_edit"]["status"] == "ok"
    assert row["gpt_image2_edit"]["edit_context"]["gpt_mask_shape"] == "text_pixels"
    assert row["gpt_image2_edit"]["edit_context"]["mask_strategy"] == "text_pixels_within_bbox"


def test_should_retry_validation_when_boolean_contradicts_reasoning_match():
    validation = {
        "semantic_correct": False,
        "tight_enough": False,
        "bbox_on_blank_area": False,
        "bbox_targets_unrelated_text": False,
        "visible_original_text": "スッスッスッスッ",
        "reasoning_summary": "The yellow bounding box correctly identifies the onomatopoeia and corresponds to the Chinese translation.",
    }

    assert _should_retry_fallback_validation(validation) is True


def test_should_not_retry_validation_for_clear_unrelated_rejection():
    validation = {
        "semantic_correct": False,
        "tight_enough": False,
        "bbox_on_blank_area": False,
        "bbox_targets_unrelated_text": True,
        "visible_original_text": "unrelated",
        "reasoning_summary": "The bbox targets unrelated text.",
    }

    assert _should_retry_fallback_validation(validation) is False


def test_should_retry_validation_when_unrelated_flag_conflicts_with_visible_target_text():
    validation = {
        "semantic_correct": False,
        "tight_enough": False,
        "bbox_on_blank_area": False,
        "bbox_targets_unrelated_text": True,
        "visible_original_text": "スッ スッ スッ スッ",
        "reasoning_summary": "The yellow bbox contains the intended target text, but also includes a passerby and background art.",
    }

    assert _should_retry_fallback_validation(validation) is True


def test_fallback_validation_accepts_target_text_with_extra_non_text_artwork(tmp_path: Path):
    response = {
        "raw_text": "{}",
        "request": {"kind": "phase6_fallback_text_locator_validation"},
        "response": {"status": "ok"},
    }
    payload = {
        "semantic_correct": True,
        "tight_enough": False,
        "bbox_on_blank_area": False,
        "bbox_targets_unrelated_text": True,
        "visible_original_text": "スッ スッ スッ スッ",
        "recommendation": "accept",
        "reasoning_summary": "The bbox contains the target text and also covers nearby hair/background.",
    }

    validation = _fallback_validation_payload(payload, response, tmp_path / "validation.png")

    assert validation["status"] == "accepted"
    assert validation["failure_reason"] is None
    assert validation["needs_tighter_edit_mask"] is False
    assert validation["bbox_targets_unrelated_text"] is True


def test_fallback_validation_normalizes_non_text_context_rejection_when_target_text_is_visible(tmp_path: Path):
    response = {
        "raw_text": "{}",
        "request": {"kind": "phase6_fallback_text_locator_validation"},
        "response": {"status": "ok"},
    }
    payload = {
        "semantic_correct": False,
        "tight_enough": False,
        "bbox_on_blank_area": False,
        "bbox_targets_unrelated_text": True,
        "visible_original_text": "スッ スッ スッ",
        "recommendation": "reject",
        "reasoning_summary": "The yellow bbox contains the target text but also includes a passerby and background art.",
    }

    validation = _fallback_validation_payload(payload, response, tmp_path / "validation.png")

    assert validation["status"] == "accepted"
    assert validation["semantic_correct"] is True
    assert validation["recommendation"] == "accept"
    assert validation["needs_tighter_edit_mask"] is False
    assert validation["semantic_correct_overridden_from_non_text_context"] is True
    assert validation["failure_reason"] is None


def test_fallback_validation_normalizes_tightness_only_rejection_when_target_text_is_visible(tmp_path: Path):
    response = {
        "raw_text": "{}",
        "request": {"kind": "phase6_fallback_text_locator_validation"},
        "response": {"status": "ok"},
    }
    payload = {
        "semantic_correct": False,
        "tight_enough": False,
        "bbox_on_blank_area": False,
        "bbox_targets_unrelated_text": False,
        "visible_original_text": "見ちゃダメよ…",
        "recommendation": "reject",
        "reasoning_summary": (
            "The bounding box encloses the correct vertical Japanese text '見ちゃダメよ…'. "
            "However, the box is extremely loose and includes the character's face, hair, and surrounding artwork."
        ),
    }

    validation = _fallback_validation_payload(payload, response, tmp_path / "validation.png")

    assert validation["status"] == "accepted"
    assert validation["semantic_correct"] is True
    assert validation["recommendation"] == "accept"
    assert validation["needs_tighter_edit_mask"] is False
    assert validation["semantic_correct_overridden_from_tightness_only_rejection"] is True
    assert validation["failure_reason"] is None


def test_fallback_validation_accepts_japanese_sound_effect_when_rejected_only_by_sound_semantics(tmp_path: Path):
    response = {
        "raw_text": "{}",
        "request": {"kind": "phase6_fallback_text_locator_validation"},
        "response": {"status": "ok"},
    }
    payload = {
        "semantic_correct": False,
        "tight_enough": False,
        "bbox_on_blank_area": False,
        "bbox_targets_unrelated_text": True,
        "visible_original_text": "スパスパスパ",
        "recommendation": "reject",
        "reasoning_summary": (
            "The yellow bounding box targets the large 'スパスパスパ' sound effect. "
            "The provided Chinese translation '啪嗒啪嗒啪嗒' corresponds to a different sound effect."
        ),
    }

    validation = _fallback_validation_payload(payload, response, tmp_path / "validation.png")

    assert validation["status"] == "accepted"
    assert validation["semantic_correct"] is True
    assert validation["recommendation"] == "accept"
    assert validation["needs_tighter_edit_mask"] is False
    assert validation["semantic_correct_overridden_from_sound_effect_context"] is True
    assert validation["failure_reason"] is None


def test_run_phase6_nonbubble_cleanup_fallback_does_not_call_gpt_when_semantic_validation_rejects(
    tmp_path: Path,
    monkeypatch,
):
    image_path = _write_nonbubble_image(tmp_path / "page.png")
    detection_run = tmp_path / "phase2"
    detection_run.mkdir()
    _write_detection(
        detection_run / "detections.jsonl",
        image_path,
        rows=[
            {
                "record_id": "page.png#2",
                "status": "fallback_required",
                "group_name": "框外",
                "selected_text_box_xyxy": None,
                "fallback": {
                    "method": "mimo_crop_then_gpt_image2_masked_edit",
                    "context_bbox_xyxy": [10, 10, 100, 80],
                    "translated_text": "背景文字",
                },
            }
        ],
    )
    calls = {"gpt": 0}

    class FakeGptClient:
        def edit_image(self, image_path: str, mask_path: str, prompt: str, output_path: str) -> dict:
            calls["gpt"] += 1
            return _FakeGptClient().edit_image(image_path, mask_path, prompt, output_path)

    monkeypatch.setattr("autolettering.phase6_nonbubble.GptImageEditClient", lambda config: FakeGptClient())

    run_dir = run_phase6_nonbubble_cleanup(
        detection_run_dir=detection_run,
        output_root=tmp_path / "outputs",
        run_id="phase6-fallback-semantic-reject",
        sample_limit=1,
        gpt_config=GptImageConfig(base_url="https://example.test/v1/images", api_key="test", model="gpt-image-2"),
        call_gpt_image=True,
        mimo_client=_FakeMimoLocatorSemanticReject(),
    )

    row = _read_jsonl(run_dir / "cleanup-results.jsonl")[0]
    assert calls["gpt"] == 0
    assert row["status"] == "failed"
    assert row["fallback_locator"]["status"] == "ok"
    assert row["fallback_locator_validation"]["status"] == "rejected"
    assert row["fallback_locator_validation"]["semantic_correct"] is False
    assert row["gpt_image2_edit"]["status"] == "not_called"
    assert row["gpt_image2_edit"]["reason"] == "fallback_locator_semantic_rejected"


def test_run_phase6_nonbubble_cleanup_fallback_recovers_light_text_band_above_anchor(tmp_path: Path):
    image_path = _write_light_sound_effect_panel(tmp_path / "page.png")
    detection_run = tmp_path / "phase2"
    detection_run.mkdir()
    _write_detection(
        detection_run / "detections.jsonl",
        image_path,
        rows=[
            {
                "record_id": "page.png#2",
                "status": "fallback_required",
                "group_name": "框外",
                "selected_text_box_xyxy": None,
                "failure_reason": "no_ctd_mask_within_threshold",
                "fallback": {
                    "method": "mimo_crop_then_gpt_image2_masked_edit",
                    "context_bbox_xyxy": [0, 0, 660, 660],
                    "context_labelplus_point_xy": [410, 472],
                    "translated_text": "啪嗒啪嗒啪嗒",
                },
            }
        ],
    )
    mimo = _FakeMimoLocatorLowRejectedThenAnchorRecovered()

    run_dir = run_phase6_nonbubble_cleanup(
        detection_run_dir=detection_run,
        output_root=tmp_path / "outputs",
        run_id="phase6-fallback-anchor-band-recovery",
        sample_limit=1,
        mimo_client=mimo,
    )

    row = _read_jsonl(run_dir / "cleanup-results.jsonl")[0]
    assert mimo.kinds == [
        "phase6_fallback_text_locator",
        "phase6_fallback_text_locator_validation",
        "phase6_fallback_text_locator_validation",
    ]
    assert row["fallback_locator"]["anchor_recovery_of_validation"] == "fallback_locator_semantic_rejected"
    assert row["fallback_locator"]["local_bbox_xyxy"][1] < 450
    assert row["fallback_locator"]["local_bbox_xyxy"][3] <= 545
    assert row["fallback_locator"]["refinement"]["method"] == "recover_light_text_ink_band_near_labelplus_anchor"
    assert row["fallback_locator_validation"]["status"] == "accepted"
    assert row["fallback_locator_validation"]["tight_enough"] is True
    assert row["gpt_image2_edit"]["status"] == "dry_run"


def test_run_phase6_nonbubble_cleanup_fallback_recovers_anchor_band_after_invalid_locator(tmp_path: Path):
    image_path = _write_light_sound_effect_panel(tmp_path / "page.png")
    detection_run = tmp_path / "phase2"
    detection_run.mkdir()
    _write_detection(
        detection_run / "detections.jsonl",
        image_path,
        rows=[
            {
                "record_id": "page.png#2",
                "status": "fallback_required",
                "group_name": "框外",
                "selected_text_box_xyxy": None,
                "failure_reason": "no_ctd_mask_within_threshold",
                "fallback": {
                    "method": "mimo_crop_then_gpt_image2_masked_edit",
                    "context_bbox_xyxy": [0, 0, 660, 660],
                    "context_labelplus_point_xy": [410, 472],
                    "translated_text": "啪嗒啪嗒啪嗒",
                },
            }
        ],
    )
    mimo = _FakeMimoLocatorInvalidLowThenAnchorRecovered()

    run_dir = run_phase6_nonbubble_cleanup(
        detection_run_dir=detection_run,
        output_root=tmp_path / "outputs",
        run_id="phase6-fallback-invalid-anchor-band-recovery",
        sample_limit=1,
        mimo_client=mimo,
    )

    row = _read_jsonl(run_dir / "cleanup-results.jsonl")[0]
    assert mimo.kinds == [
        "phase6_fallback_text_locator",
        "phase6_fallback_text_locator_retry",
        "phase6_fallback_text_locator_validation",
    ]
    assert row["fallback_locator"]["anchor_recovery_of_validation"] == "fallback_locator_semantic_rejected"
    assert row["fallback_locator"]["local_bbox_xyxy"][1] < 450
    assert row["fallback_locator"]["refinement"]["method"] == "recover_light_text_ink_band_near_labelplus_anchor"
    assert row["fallback_locator_validation"]["status"] == "accepted"
    assert row["gpt_image2_edit"]["status"] == "dry_run"


def test_run_phase6_nonbubble_cleanup_fallback_recovers_dark_vertical_text_near_anchor(tmp_path: Path):
    image_path = _write_dark_vertical_text_near_anchor_panel(tmp_path / "page.png")
    detection_run = tmp_path / "phase2"
    detection_run.mkdir()
    _write_detection(
        detection_run / "detections.jsonl",
        image_path,
        rows=[
            {
                "record_id": "page.png#2",
                "status": "fallback_required",
                "group_name": "框外",
                "selected_text_box_xyxy": None,
                "failure_reason": "no_ctd_mask_within_threshold",
                "fallback": {
                    "method": "mimo_crop_then_gpt_image2_masked_edit",
                    "context_bbox_xyxy": [0, 0, 220, 220],
                    "context_labelplus_point_xy": [100, 92],
                    "translated_text": "好孩子不要看…",
                },
            }
        ],
    )
    mimo = _FakeMimoLocatorRightArtworkThenDarkAnchorRecovered()

    run_dir = run_phase6_nonbubble_cleanup(
        detection_run_dir=detection_run,
        output_root=tmp_path / "outputs",
        run_id="phase6-fallback-dark-anchor-column-recovery",
        sample_limit=1,
        mimo_client=mimo,
    )

    row = _read_jsonl(run_dir / "cleanup-results.jsonl")[0]
    assert mimo.kinds == [
        "phase6_fallback_text_locator",
        "phase6_fallback_text_locator_validation",
        "phase6_fallback_text_locator_validation",
    ]
    assert row["fallback_locator"]["anchor_recovery_of_validation"] == "fallback_locator_semantic_rejected"
    assert row["fallback_locator"]["refinement"]["method"] == "recover_dark_text_ink_column_near_labelplus_anchor"
    x1, y1, x2, y2 = row["fallback_locator"]["local_bbox_xyxy"]
    assert 76 <= x1 <= 98
    assert 106 <= x2 <= 124
    assert y1 <= 52
    assert y2 >= 135
    assert row["fallback_locator_validation"]["status"] == "accepted"
    assert row["gpt_image2_edit"]["status"] == "dry_run"


def test_run_phase6_nonbubble_cleanup_fallback_recovers_after_retry_validation_rejects(tmp_path: Path):
    image_path = _write_light_sound_effect_panel(tmp_path / "page.png")
    detection_run = tmp_path / "phase2"
    detection_run.mkdir()
    _write_detection(
        detection_run / "detections.jsonl",
        image_path,
        rows=[
            {
                "record_id": "page.png#2",
                "status": "fallback_required",
                "group_name": "框外",
                "selected_text_box_xyxy": None,
                "failure_reason": "no_ctd_mask_within_threshold",
                "fallback": {
                    "method": "mimo_crop_then_gpt_image2_masked_edit",
                    "context_bbox_xyxy": [0, 0, 660, 660],
                    "context_labelplus_point_xy": [410, 472],
                    "translated_text": "啪嗒啪嗒啪嗒",
                },
            }
        ],
    )
    mimo = _FakeMimoLocatorRetryLowRejectedThenAnchorRecovered()

    run_dir = run_phase6_nonbubble_cleanup(
        detection_run_dir=detection_run,
        output_root=tmp_path / "outputs",
        run_id="phase6-fallback-retry-reject-anchor-recovery",
        sample_limit=1,
        mimo_client=mimo,
    )

    row = _read_jsonl(run_dir / "cleanup-results.jsonl")[0]
    assert mimo.kinds == [
        "phase6_fallback_text_locator",
        "phase6_fallback_text_locator_retry",
        "phase6_fallback_text_locator_validation",
        "phase6_fallback_text_locator_validation",
    ]
    assert row["fallback_locator"]["anchor_recovery_of_validation"] == "fallback_locator_semantic_rejected"
    assert row["fallback_locator"]["local_bbox_xyxy"][1] < 450
    assert row["fallback_locator_validation"]["status"] == "accepted"
    assert row["gpt_image2_edit"]["status"] == "dry_run"


def test_run_phase6_nonbubble_cleanup_keeps_accepted_bbox_even_when_below_anchor(tmp_path: Path):
    image_path = _write_light_sound_effect_panel_with_right_panel_divider(tmp_path / "page.png")
    detection_run = tmp_path / "phase2"
    detection_run.mkdir()
    _write_detection(
        detection_run / "detections.jsonl",
        image_path,
        rows=[
            {
                "record_id": "page.png#2",
                "status": "fallback_required",
                "group_name": "框外",
                "selected_text_box_xyxy": None,
                "failure_reason": "no_ctd_mask_within_threshold",
                "fallback": {
                    "method": "mimo_crop_then_gpt_image2_masked_edit",
                    "context_bbox_xyxy": [0, 0, 660, 660],
                    "context_labelplus_point_xy": [410, 472],
                    "translated_text": "啪嗒啪嗒啪嗒",
                },
            }
        ],
    )
    mimo = _FakeMimoLocatorAcceptedTightBelowAnchorThenRecovered()

    run_dir = run_phase6_nonbubble_cleanup(
        detection_run_dir=detection_run,
        output_root=tmp_path / "outputs",
        run_id="phase6-fallback-accepted-below-anchor-kept",
        sample_limit=1,
        mimo_client=mimo,
    )

    row = _read_jsonl(run_dir / "cleanup-results.jsonl")[0]
    assert mimo.kinds == [
        "phase6_fallback_text_locator",
        "phase6_fallback_text_locator_validation",
    ]
    assert "anchor_recovery_of_validation" not in row["fallback_locator"]
    assert row["fallback_locator"]["local_bbox_xyxy"] == [0, 455, 652, 570]
    assert row["fallback_locator_validation"]["status"] == "accepted"
    assert row["gpt_image2_edit"]["status"] == "dry_run"


def test_run_phase6_nonbubble_cleanup_records_rejected_anchor_recovery_attempt(tmp_path: Path):
    image_path = _write_light_sound_effect_panel(tmp_path / "page.png")
    detection_run = tmp_path / "phase2"
    detection_run.mkdir()
    _write_detection(
        detection_run / "detections.jsonl",
        image_path,
        rows=[
            {
                "record_id": "page.png#2",
                "status": "fallback_required",
                "group_name": "框外",
                "selected_text_box_xyxy": None,
                "failure_reason": "no_ctd_mask_within_threshold",
                "fallback": {
                    "method": "mimo_crop_then_gpt_image2_masked_edit",
                    "context_bbox_xyxy": [0, 0, 660, 660],
                    "context_labelplus_point_xy": [410, 472],
                    "translated_text": "啪嗒啪嗒啪嗒",
                },
            }
        ],
    )
    mimo = _FakeMimoLocatorRetryLowRejectedThenAnchorRejected()

    run_dir = run_phase6_nonbubble_cleanup(
        detection_run_dir=detection_run,
        output_root=tmp_path / "outputs",
        run_id="phase6-fallback-retry-reject-anchor-attempt-recorded",
        sample_limit=1,
        mimo_client=mimo,
    )

    row = _read_jsonl(run_dir / "cleanup-results.jsonl")[0]
    attempt = row["fallback_locator"]["anchor_recovery_attempt"]
    assert row["status"] == "failed"
    assert row["fallback_locator"]["local_bbox_xyxy"] == [31, 531, 560, 645]
    assert attempt["status"] == "rejected"
    assert attempt["local_bbox_xyxy"][1] < 450
    assert attempt["validation"]["status"] == "rejected"
    assert attempt["validation"]["failure_reason"] == "fallback_locator_semantic_rejected"
    assert Path(attempt["validation"]["validation_image_path"]).exists()
    assert row["gpt_image2_edit"]["status"] == "not_called"


def test_anchor_recovery_tightens_sparse_right_screentone_component(tmp_path: Path):
    image_path = _write_light_sound_effect_panel_with_sparse_right_screentone(tmp_path / "page.png")
    detection = {
        "record_id": "page.png#2",
        "fallback": {"context_labelplus_point_xy": [410, 472]},
    }
    locator = {"status": "ok", "local_bbox_xyxy": [30, 508, 628, 648]}
    validation = {
        "status": "rejected",
        "failure_reason": "fallback_locator_semantic_rejected",
    }

    recovered = _recover_locator_from_labelplus_anchor(
        detection,
        image_path,
        (0, 0, 660, 660),
        locator,
        validation,
    )

    assert recovered["status"] == "ok"
    assert recovered["local_bbox_xyxy"][0] <= 60
    assert recovered["local_bbox_xyxy"][2] <= 530
    assert recovered["refinement"]["method"] == "recover_light_text_ink_band_near_labelplus_anchor"
    assert recovered["refinement"]["right_trim_method"] == "trim_sparse_right_screentone_component"


def test_anchor_recovery_prefers_light_sound_effect_band_for_invalid_sfx_locator(tmp_path: Path):
    image_path = _write_light_sound_effect_panel(tmp_path / "page.png")
    detection = {
        "record_id": "page.png#2",
        "translated_text": "啪嗒啪嗒啪嗒",
        "fallback": {"context_labelplus_point_xy": [410, 472]},
    }
    locator = {
        "status": "failed",
        "failure_reason": "invalid_mimo_bbox:ValueError",
        "raw_text": json.dumps(
            {
                "bbox_xyxy": [20, 543, 638, 737],
                "bbox_percent_xyxy": [3.07, 83.28, 97.85, 113.04],
                "confidence": 0.95,
                "reasoning_summary": "The bbox encloses the Japanese sound effect text for 啪嗒啪嗒啪嗒.",
            },
            ensure_ascii=False,
        ),
        "retry_raw_text": json.dumps(
            {
                "bbox_xyxy": [18, 541, 573, 726],
                "bbox_percent_xyxy": [2.76, 82.98, 87.88, 111.35],
                "confidence": 0.95,
                "reasoning_summary": "The bbox encloses the complete Japanese sound effect text.",
            },
            ensure_ascii=False,
        ),
    }
    validation = {
        "status": "rejected",
        "failure_reason": "fallback_locator_semantic_rejected",
    }

    recovered = _recover_locator_from_labelplus_anchor(
        detection,
        image_path,
        (0, 0, 660, 660),
        locator,
        validation,
    )

    assert recovered["status"] == "ok"
    assert recovered["refinement"]["method"] == "recover_light_text_ink_band_near_labelplus_anchor"
    assert recovered["local_bbox_xyxy"][1] < 450
    assert recovered["local_bbox_xyxy"][3] < 540


def test_anchor_recovery_prefers_sound_effect_band_over_dark_vertical_decoy(tmp_path: Path):
    image_path = _write_light_sound_effect_panel_with_dark_vertical_decoy(tmp_path / "page.png")
    detection = {
        "record_id": "page.png#2",
        "translated_text": "啪嗒啪嗒啪嗒",
        "fallback": {"context_labelplus_point_xy": [410, 472]},
    }
    locator = {
        "status": "failed",
        "failure_reason": "invalid_mimo_bbox:ValueError",
        "retry_raw_text": json.dumps(
            {
                "bbox_xyxy": [18, 541, 573, 726],
                "bbox_percent_xyxy": [2.76, 82.98, 87.88, 111.35],
                "confidence": 0.95,
                "reasoning_summary": "The bbox encloses the complete Japanese sound effect text.",
            },
            ensure_ascii=False,
        ),
    }
    validation = {
        "status": "rejected",
        "failure_reason": "fallback_locator_semantic_rejected",
    }

    recovered = _recover_locator_from_labelplus_anchor(
        detection,
        image_path,
        (0, 0, 660, 660),
        locator,
        validation,
    )

    assert recovered["status"] == "ok"
    assert recovered["refinement"]["method"] == "recover_light_text_ink_band_near_labelplus_anchor"
    x1, y1, x2, y2 = recovered["local_bbox_xyxy"]
    assert x2 - x1 > 240
    assert y1 < 450
    assert y2 < 540


def test_anchor_recovery_caps_right_edge_before_panel_divider(tmp_path: Path):
    image_path = _write_light_sound_effect_panel_with_right_panel_divider(tmp_path / "page.png")
    detection = {
        "record_id": "page.png#2",
        "fallback": {"context_labelplus_point_xy": [410, 472]},
    }
    locator = {"status": "ok", "local_bbox_xyxy": [30, 508, 628, 648]}
    validation = {
        "status": "rejected",
        "failure_reason": "fallback_locator_semantic_rejected",
    }

    recovered = _recover_locator_from_labelplus_anchor(
        detection,
        image_path,
        (0, 0, 660, 660),
        locator,
        validation,
    )

    assert recovered["status"] == "ok"
    assert 470 <= recovered["local_bbox_xyxy"][2] <= 505
    assert recovered["refinement"]["right_trim_method"] == "trim_right_panel_divider"


def test_run_phase6_nonbubble_cleanup_fallback_does_not_call_gpt_when_mimo_bbox_is_invalid(tmp_path: Path, monkeypatch):
    image_path = _write_nonbubble_image(tmp_path / "page.png")
    detection_run = tmp_path / "phase2"
    detection_run.mkdir()
    _write_detection(
        detection_run / "detections.jsonl",
        image_path,
        rows=[
            {
                "record_id": "page.png#2",
                "status": "fallback_required",
                "group_name": "框外",
                "selected_text_box_xyxy": None,
                "fallback": {
                    "method": "mimo_crop_then_gpt_image2_masked_edit",
                    "context_bbox_xyxy": [10, 10, 100, 80],
                    "translated_text": "背景文字",
                },
            }
        ],
    )
    calls = {"gpt": 0}

    class FakeGptClient:
        def edit_image(self, image_path: str, mask_path: str, prompt: str, output_path: str) -> dict:
            calls["gpt"] += 1
            return _FakeGptClient().edit_image(image_path, mask_path, prompt, output_path)

    monkeypatch.setattr("autolettering.phase6_nonbubble.GptImageEditClient", lambda config: FakeGptClient())

    run_dir = run_phase6_nonbubble_cleanup(
        detection_run_dir=detection_run,
        output_root=tmp_path / "outputs",
        run_id="phase6-fallback-invalid-mimo",
        sample_limit=1,
        gpt_config=GptImageConfig(base_url="https://example.test/v1/images", api_key="test", model="gpt-image-2"),
        call_gpt_image=True,
        mimo_client=_FakeMimoLocatorInvalidBbox(),
    )

    row = _read_jsonl(run_dir / "cleanup-results.jsonl")[0]
    assert calls["gpt"] == 0
    assert row["status"] == "failed"
    assert row["fallback_locator"]["status"] == "failed"
    assert row["fallback_locator_validation"]["status"] == "not_called"
    assert row["gpt_image2_edit"]["status"] == "not_called"


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


def test_local_background_color_prefers_outer_light_background_over_line_art():
    image = Image.new("RGB", (80, 80), "white")
    draw = ImageDraw.Draw(image)
    draw.line((8, 8, 72, 72), fill=(25, 25, 25), width=3)
    draw.rectangle((28, 24, 54, 56), fill=(245, 245, 245))
    draw.rectangle((36, 32, 46, 48), fill="black")

    color = _local_background_color(image, (32, 28, 50, 52))

    assert min(color) >= 235


def test_local_background_color_preserves_dark_panel_background():
    image = Image.new("RGB", (80, 80), (24, 24, 24))
    draw = ImageDraw.Draw(image)
    draw.rectangle((36, 32, 46, 48), fill="white")

    color = _local_background_color(image, (32, 28, 50, 52))

    assert max(color) <= 40


def test_compose_gpt_replacement_region_extracts_light_text_without_gray_box():
    original = Image.new("RGB", (120, 80), "white")
    draw = ImageDraw.Draw(original)
    draw.rectangle((20, 20, 92, 52), fill=(8, 8, 8))
    draw.rectangle((36, 30, 70, 38), fill="white")
    edited = original.copy()
    edit_draw = ImageDraw.Draw(edited)
    edit_draw.rectangle((30, 24, 86, 46), fill=(155, 155, 155))
    edit_draw.rectangle((38, 30, 78, 36), fill="white")

    result = _compose_gpt_replacement_region(original, edited, (30, 24, 86, 46))

    assert max(result.getpixel((34, 28))) < 40
    assert min(result.getpixel((50, 32))) > 235


def test_write_fallback_replacement_crop_uses_edit_mask_without_clearing_non_text_art(tmp_path: Path):
    context_path = tmp_path / "context.png"
    original = Image.new("RGB", (100, 80), "white")
    draw = ImageDraw.Draw(original)
    draw.rectangle((54, 20, 76, 62), fill=(12, 12, 12))
    draw.line((15, 45, 88, 18), fill=(35, 35, 35), width=2)
    original.save(context_path)

    edited = original.crop((10, 10, 90, 70))
    edit_draw = ImageDraw.Draw(edited)
    edit_draw.rectangle((14, 16, 30, 48), fill=(20, 20, 20))
    normalized = tmp_path / "normalized.png"
    edited.save(normalized)

    mask = Image.new("RGBA", (80, 60), (0, 0, 0, 255))
    alpha = Image.new("L", (80, 60), 255)
    ImageDraw.Draw(alpha).rectangle((10, 10, 70, 54), fill=0)
    Image.merge("RGBA", [Image.new("L", (80, 60), 0)] * 3 + [alpha]).save(tmp_path / "edit-mask.png")
    output = tmp_path / "replacement.png"

    _write_fallback_replacement_crop(
        {"normalized_output_path": str(normalized)},
        context_path,
        output,
        (100, 80),
        (20, 20, 80, 64),
        edit_context={
            "local_context_bbox": (10, 10, 90, 70),
            "mask_path": tmp_path / "edit-mask.png",
        },
    )

    with Image.open(output).convert("RGB") as result:
        assert result.getpixel((64, 35)) == (12, 12, 12)
        assert result.getpixel((24, 32)) == (20, 20, 20)
        assert result.getpixel((5, 5)) == (255, 255, 255)


class _FakeGptClient:
    def edit_image(self, image_path: str, mask_path: str, prompt: str, output_path: str) -> dict:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (10, 10), "white").save(output)
        return {"status": "ok", "output_path": str(output), "response": {"usage": {"total_tokens": 1}}}


class _FakeMimoLocator:
    def analyze_image(self, image_path: str, prompt: str, kind: str = "image_analysis", max_completion_tokens: int | None = None):
        assert Path(image_path).exists()
        if kind == "phase6_fallback_text_locator_validation":
            assert Path(image_path).parent.name == "fallback_locator_validation_input"
            assert "yellow bbox" in prompt
            assert "semantic_correct" in prompt
            return _mimo_validation_response(kind, image_path, accepted=True)
        assert Path(image_path).parent.name == "fallback_locator_input"
        assert "背景文字" in prompt
        assert "coordinate grid" in prompt
        assert "blue LabelPlus cross" in prompt
        assert "bbox_percent_xyxy" in prompt
        return {
            "raw_text": json.dumps(
                {
                    "bbox_xyxy": [25, 15, 52, 45],
                    "confidence": 0.82,
                    "reasoning_summary": "target text region",
                },
                ensure_ascii=False,
            ),
            "request": {"kind": kind, "image_path": str(image_path)},
            "response": {"status": "ok"},
        }


class _FakeMimoLocatorPromptRecorder(_FakeMimoLocator):
    def __init__(self) -> None:
        self.prompts: dict[str, str] = {}

    def analyze_image(self, image_path: str, prompt: str, kind: str = "image_analysis", max_completion_tokens: int | None = None):
        self.prompts[kind] = prompt
        return super().analyze_image(image_path, prompt, kind, max_completion_tokens)


class _FakeMimoLocatorArray:
    def analyze_image(self, image_path: str, prompt: str, kind: str = "image_analysis", max_completion_tokens: int | None = None):
        if kind == "phase6_fallback_text_locator_validation":
            return _mimo_validation_response(kind, image_path, accepted=True)
        return {
            "raw_text": json.dumps(
                [
                    {
                        "bbox_xyxy": [25, 15, 52, 45],
                        "confidence": 0.82,
                        "reasoning_summary": "target text region",
                    }
                ],
                ensure_ascii=False,
            ),
            "request": {"kind": kind, "image_path": str(image_path)},
            "response": {"status": "ok"},
        }


class _FakeMimoLocatorPercent:
    def analyze_image(self, image_path: str, prompt: str, kind: str = "image_analysis", max_completion_tokens: int | None = None):
        if kind == "phase6_fallback_text_locator_validation":
            return _mimo_validation_response(kind, image_path, accepted=True)
        assert Path(image_path).parent.name == "fallback_locator_input"
        return {
            "raw_text": json.dumps(
                {
                    "bbox_percent_xyxy": [27.777, 21.428, 57.777, 64.285],
                    "confidence": 0.78,
                    "reasoning_summary": "target text region from grid percent coordinates",
                },
                ensure_ascii=False,
            ),
            "request": {"kind": kind, "image_path": str(image_path)},
            "response": {"status": "ok"},
        }


class _FakeMimoLocatorPixelOutPercentOk:
    def __init__(self):
        self.kinds = []

    def analyze_image(self, image_path: str, prompt: str, kind: str = "image_analysis", max_completion_tokens: int | None = None):
        self.kinds.append(kind)
        if kind == "phase6_fallback_text_locator_validation":
            return _mimo_validation_response(kind, image_path, accepted=True)
        return {
            "raw_text": json.dumps(
                {
                    "bbox_xyxy": [25, 15, 120, 99],
                    "bbox_percent_xyxy": [27.777, 21.428, 57.777, 64.285],
                    "confidence": 0.78,
                    "reasoning_summary": "pixel bbox is outside, percent bbox is usable",
                },
                ensure_ascii=False,
            ),
            "request": {"kind": kind, "image_path": str(image_path)},
            "response": {"status": "ok"},
        }


class _FakeMimoLocatorInvalidBbox:
    def analyze_image(self, image_path: str, prompt: str, kind: str = "image_analysis", max_completion_tokens: int | None = None):
        return {
            "raw_text": json.dumps(
                {
                    "bbox_xyxy": [401, 385, 831, 539],
                    "confidence": 0.99,
                    "reasoning_summary": "out of crop bounds",
                },
                ensure_ascii=False,
            ),
            "request": {"kind": kind, "image_path": str(image_path)},
            "response": {"status": "ok"},
        }


class _FakeMimoLocatorRetry:
    def __init__(self):
        self.kinds = []

    def analyze_image(self, image_path: str, prompt: str, kind: str = "image_analysis", max_completion_tokens: int | None = None):
        self.kinds.append(kind)
        if kind == "phase6_fallback_text_locator":
            return {
                "raw_text": json.dumps(
                    {
                        "bbox_xyxy": [401, 385, 831, 539],
                        "confidence": 0.99,
                        "reasoning_summary": "out of crop bounds",
                    },
                    ensure_ascii=False,
                ),
                "request": {"kind": kind, "image_path": str(image_path)},
                "response": {"status": "ok"},
            }
        if kind == "phase6_fallback_text_locator_retry":
            assert "Previous invalid response" in prompt
            return {
                "raw_text": json.dumps(
                    {
                        "bbox_xyxy": [25, 15, 52, 45],
                        "confidence": 0.82,
                        "reasoning_summary": "corrected target text region",
                    },
                    ensure_ascii=False,
                ),
                "request": {"kind": kind, "image_path": str(image_path)},
                "response": {"status": "ok"},
            }
        return _mimo_validation_response(kind, image_path, accepted=True)


class _FakeMimoLocatorTrailingBracket:
    def __init__(self):
        self.kinds = []

    def analyze_image(self, image_path: str, prompt: str, kind: str = "image_analysis", max_completion_tokens: int | None = None):
        self.kinds.append(kind)
        if kind == "phase6_fallback_text_locator_validation":
            return _mimo_validation_response(kind, image_path, accepted=True)
        return {
            "raw_text": (
                "```json\n"
                "{\n"
                "  \"bbox_xyxy\": [25, 15, 52, 45],\n"
                "  \"confidence\": 0.82,\n"
                "  \"reasoning_summary\": \"target text region\"\n"
                "}\n"
                "]\n"
                "```"
            ),
            "request": {"kind": kind, "image_path": str(image_path)},
            "response": {"status": "ok"},
        }


class _FakeMimoLocatorNestedBbox:
    def analyze_image(self, image_path: str, prompt: str, kind: str = "image_analysis", max_completion_tokens: int | None = None):
        if kind == "phase6_fallback_text_locator_validation":
            return _mimo_validation_response(kind, image_path, accepted=True)
        return {
            "raw_text": json.dumps(
                {
                    "bbox_xyxy": [[25, 15, 52, 45]],
                    "confidence": 0.82,
                    "reasoning_summary": "target text region",
                },
                ensure_ascii=False,
            ),
            "request": {"kind": kind, "image_path": str(image_path)},
            "response": {"status": "ok"},
        }


class _FakeMimoLocatorValidationRetry:
    def __init__(self):
        self.kinds = []

    def analyze_image(self, image_path: str, prompt: str, kind: str = "image_analysis", max_completion_tokens: int | None = None):
        self.kinds.append(kind)
        if kind == "phase6_fallback_text_locator":
            return {
                "raw_text": json.dumps(
                    {
                        "bbox_xyxy": [25, 15, 52, 45],
                        "confidence": 0.82,
                        "reasoning_summary": "target text region",
                    },
                    ensure_ascii=False,
                ),
                "request": {"kind": kind, "image_path": str(image_path)},
                "response": {"status": "ok"},
            }
        if kind == "phase6_fallback_text_locator_validation":
            return {
                "raw_text": json.dumps(
                    {
                        "semantic_correct": False,
                        "tight_enough": True,
                        "bbox_on_blank_area": False,
                        "bbox_targets_unrelated_text": False,
                        "visible_original_text": "背景文字",
                        "recommendation": "reject",
                        "reasoning_summary": "overly strict rejection despite the target being visible",
                    },
                    ensure_ascii=False,
                ),
                "request": {"kind": kind, "image_path": str(image_path)},
                "response": {"status": "ok"},
            }
        return _mimo_validation_response(kind, image_path, accepted=True)


class _FakeMimoLocatorSemanticLocatorRetry:
    def __init__(self):
        self.kinds = []

    def analyze_image(self, image_path: str, prompt: str, kind: str = "image_analysis", max_completion_tokens: int | None = None):
        self.kinds.append(kind)
        if kind == "phase6_fallback_text_locator":
            return {
                "raw_text": json.dumps(
                    {
                        "bbox_xyxy": [25, 55, 52, 68],
                        "confidence": 0.92,
                        "reasoning_summary": "bbox is below the intended text",
                    },
                    ensure_ascii=False,
                ),
                "request": {"kind": kind, "image_path": str(image_path)},
                "response": {"status": "ok"},
            }
        if kind == "phase6_fallback_text_locator_validation":
            if self.kinds.count("phase6_fallback_text_locator_validation") == 1:
                return {
                    "raw_text": json.dumps(
                        {
                            "semantic_correct": False,
                            "tight_enough": False,
                            "bbox_on_blank_area": True,
                            "bbox_targets_unrelated_text": False,
                            "visible_original_text": "",
                            "recommendation": "reject",
                            "reasoning_summary": "The target text is above the yellow bbox; the current bbox is on blank area.",
                        },
                        ensure_ascii=False,
                    ),
                    "request": {"kind": kind, "image_path": str(image_path)},
                    "response": {"status": "ok"},
                }
            return _mimo_validation_response(kind, image_path, accepted=True)
        if kind == "phase6_fallback_text_locator_semantic_retry":
            assert "Previous yellow bbox validation rejected" in prompt
            assert "above the yellow bbox" in prompt
            return {
                "raw_text": json.dumps(
                    {
                        "bbox_xyxy": [25, 15, 52, 45],
                        "confidence": 0.86,
                        "reasoning_summary": "corrected to the target text above the rejected bbox",
                    },
                    ensure_ascii=False,
                ),
                "request": {"kind": kind, "image_path": str(image_path)},
                "response": {"status": "ok"},
            }
        raise AssertionError(f"unexpected kind {kind}")


class _FakeMimoLocatorTightnessRetry:
    def __init__(self):
        self.kinds = []

    def analyze_image(self, image_path: str, prompt: str, kind: str = "image_analysis", max_completion_tokens: int | None = None):
        self.kinds.append(kind)
        if kind == "phase6_fallback_text_locator":
            return {
                "raw_text": json.dumps(
                    {
                        "bbox_xyxy": [5, 8, 84, 62],
                        "confidence": 0.9,
                        "reasoning_summary": "loose but semantically correct region",
                    },
                    ensure_ascii=False,
                ),
                "request": {"kind": kind, "image_path": str(image_path)},
                "response": {"status": "ok"},
            }
        if kind == "phase6_fallback_text_locator_validation":
            if self.kinds.count("phase6_fallback_text_locator_validation") == 1:
                return {
                    "raw_text": json.dumps(
                        {
                            "semantic_correct": True,
                            "tight_enough": False,
                            "bbox_on_blank_area": False,
                            "bbox_targets_unrelated_text": False,
                            "visible_original_text": "背景文字",
                            "recommendation": "reject",
                            "reasoning_summary": "The bbox targets the right text but includes too much surrounding blank space.",
                        },
                        ensure_ascii=False,
                    ),
                    "request": {"kind": kind, "image_path": str(image_path)},
                    "response": {"status": "ok"},
                }
            return _mimo_validation_response(kind, image_path, accepted=True)
        raise AssertionError(f"unexpected kind {kind}")


class _FakeMimoLocatorLooseAcceptedStillLoose:
    def __init__(self):
        self.kinds = []

    def analyze_image(self, image_path: str, prompt: str, kind: str = "image_analysis", max_completion_tokens: int | None = None):
        self.kinds.append(kind)
        if kind == "phase6_fallback_text_locator":
            return {
                "raw_text": json.dumps(
                    {
                        "bbox_xyxy": [5, 8, 84, 62],
                        "confidence": 0.9,
                        "reasoning_summary": "loose but semantically correct region",
                    },
                    ensure_ascii=False,
                ),
                "request": {"kind": kind, "image_path": str(image_path)},
                "response": {"status": "ok"},
            }
        if kind == "phase6_fallback_text_locator_validation":
            return {
                "raw_text": json.dumps(
                    {
                        "semantic_correct": True,
                        "tight_enough": False,
                        "bbox_on_blank_area": False,
                        "bbox_targets_unrelated_text": False,
                        "visible_original_text": "背景文字",
                        "recommendation": "reject",
                        "reasoning_summary": "The bbox targets the right text but remains too loose.",
                    },
                    ensure_ascii=False,
                ),
                "request": {"kind": kind, "image_path": str(image_path)},
                "response": {"status": "ok"},
            }
        raise AssertionError(f"unexpected kind {kind}")


class _FakeMimoLocatorLooseAcceptedWideInkBand:
    def __init__(self):
        self.kinds = []

    def analyze_image(self, image_path: str, prompt: str, kind: str = "image_analysis", max_completion_tokens: int | None = None):
        self.kinds.append(kind)
        if kind == "phase6_fallback_text_locator":
            return {
                "raw_text": json.dumps(
                    {
                        "bbox_xyxy": [20, 30, 130, 130],
                        "confidence": 0.9,
                        "reasoning_summary": "loose bbox contains target text and non-text context",
                    },
                    ensure_ascii=False,
                ),
                "request": {"kind": kind, "image_path": str(image_path)},
                "response": {"status": "ok"},
            }
        if kind == "phase6_fallback_text_locator_validation":
            return {
                "raw_text": json.dumps(
                    {
                        "semantic_correct": True,
                        "tight_enough": False,
                        "bbox_on_blank_area": False,
                        "bbox_targets_unrelated_text": False,
                        "visible_original_text": "背景文字",
                        "recommendation": "accept",
                        "reasoning_summary": "The bbox contains the target text and some nearby background.",
                    },
                    ensure_ascii=False,
                ),
                "request": {"kind": kind, "image_path": str(image_path)},
                "response": {"status": "ok"},
            }
        raise AssertionError(f"unexpected kind {kind}")


class _FakeMimoLocatorSemanticReject:
    def analyze_image(self, image_path: str, prompt: str, kind: str = "image_analysis", max_completion_tokens: int | None = None):
        if kind == "phase6_fallback_text_locator_validation":
            return _mimo_validation_response(kind, image_path, accepted=False)
        return {
            "raw_text": json.dumps(
                {
                    "bbox_xyxy": [25, 15, 52, 45],
                    "confidence": 0.82,
                    "reasoning_summary": "target text region",
                },
                ensure_ascii=False,
            ),
            "request": {"kind": kind, "image_path": str(image_path)},
            "response": {"status": "ok"},
        }


class _FakeMimoLocatorLowRejectedThenAnchorRecovered:
    def __init__(self):
        self.kinds = []

    def analyze_image(self, image_path: str, prompt: str, kind: str = "image_analysis", max_completion_tokens: int | None = None):
        self.kinds.append(kind)
        if kind == "phase6_fallback_text_locator":
            return {
                "raw_text": json.dumps(
                    {
                        "bbox_xyxy": [25, 542, 585, 650],
                        "confidence": 1.0,
                        "reasoning_summary": "the bbox is below the sound effect and over character hair",
                    },
                    ensure_ascii=False,
                ),
                "request": {"kind": kind, "image_path": str(image_path)},
                "response": {"status": "ok"},
            }
        if kind == "phase6_fallback_text_locator_validation":
            if self.kinds.count("phase6_fallback_text_locator_validation") == 1:
                return {
                    "raw_text": json.dumps(
                        {
                            "semantic_correct": False,
                            "tight_enough": False,
                            "bbox_on_blank_area": True,
                            "bbox_targets_unrelated_text": False,
                            "visible_original_text": "",
                            "recommendation": "reject",
                            "reasoning_summary": "The yellow bbox is below the intended sound effect and covers hair.",
                        },
                        ensure_ascii=False,
                    ),
                    "request": {"kind": kind, "image_path": str(image_path)},
                    "response": {"status": "ok"},
                }
            return _mimo_validation_response(kind, image_path, accepted=True)
        raise AssertionError(f"unexpected kind {kind}")


class _FakeMimoLocatorInvalidLowThenAnchorRecovered:
    def __init__(self):
        self.kinds = []

    def analyze_image(self, image_path: str, prompt: str, kind: str = "image_analysis", max_completion_tokens: int | None = None):
        self.kinds.append(kind)
        if kind == "phase6_fallback_text_locator":
            return {
                "raw_text": json.dumps(
                    {
                        "bbox_xyxy": [38, 584, 595, 734],
                        "confidence": 0.95,
                        "reasoning_summary": "bbox extends below the crop",
                    },
                    ensure_ascii=False,
                ),
                "request": {"kind": kind, "image_path": str(image_path)},
                "response": {"status": "ok"},
            }
        if kind == "phase6_fallback_text_locator_retry":
            return {
                "raw_text": json.dumps(
                    {
                        "bbox_xyxy": [38, 545, 605, 668],
                        "confidence": 0.95,
                        "reasoning_summary": "bbox still extends below the crop",
                    },
                    ensure_ascii=False,
                ),
                "request": {"kind": kind, "image_path": str(image_path)},
                "response": {"status": "ok"},
            }
        if kind == "phase6_fallback_text_locator_validation":
            return _mimo_validation_response(kind, image_path, accepted=True)
        raise AssertionError(f"unexpected kind {kind}")


class _FakeMimoLocatorRightArtworkThenDarkAnchorRecovered:
    def __init__(self):
        self.kinds = []

    def analyze_image(self, image_path: str, prompt: str, kind: str = "image_analysis", max_completion_tokens: int | None = None):
        self.kinds.append(kind)
        if kind == "phase6_fallback_text_locator":
            return {
                "raw_text": json.dumps(
                    {
                        "bbox_xyxy": [146, 62, 202, 180],
                        "confidence": 0.94,
                        "reasoning_summary": "bbox falls on the right-side artwork, not the dark vertical text near the anchor",
                    },
                    ensure_ascii=False,
                ),
                "request": {"kind": kind, "image_path": str(image_path)},
                "response": {"status": "ok"},
            }
        if kind == "phase6_fallback_text_locator_validation":
            if self.kinds.count("phase6_fallback_text_locator_validation") == 1:
                return {
                    "raw_text": json.dumps(
                        {
                            "semantic_correct": False,
                            "tight_enough": False,
                            "bbox_on_blank_area": False,
                            "bbox_targets_unrelated_text": True,
                            "visible_original_text": "",
                            "recommendation": "reject",
                            "reasoning_summary": "The bbox is over unrelated character artwork to the right of the intended vertical text.",
                        },
                        ensure_ascii=False,
                    ),
                    "request": {"kind": kind, "image_path": str(image_path)},
                    "response": {"status": "ok"},
                }
            return _mimo_validation_response(kind, image_path, accepted=True)
        raise AssertionError(f"unexpected kind {kind}")


class _FakeMimoLocatorRetryLowRejectedThenAnchorRecovered:
    def __init__(self):
        self.kinds = []

    def analyze_image(self, image_path: str, prompt: str, kind: str = "image_analysis", max_completion_tokens: int | None = None):
        self.kinds.append(kind)
        if kind == "phase6_fallback_text_locator":
            return {
                "raw_text": json.dumps(
                    {
                        "bbox_xyxy": [31, 531, 599, 671],
                        "confidence": 0.99,
                        "reasoning_summary": "bbox extends below the crop",
                    },
                    ensure_ascii=False,
                ),
                "request": {"kind": kind, "image_path": str(image_path)},
                "response": {"status": "ok"},
            }
        if kind == "phase6_fallback_text_locator_retry":
            return {
                "raw_text": json.dumps(
                    {
                        "bbox_xyxy": [31, 531, 560, 645],
                        "confidence": 0.99,
                        "reasoning_summary": "bbox is valid but below the intended sound effect",
                    },
                    ensure_ascii=False,
                ),
                "request": {"kind": kind, "image_path": str(image_path)},
                "response": {"status": "ok"},
            }
        if kind == "phase6_fallback_text_locator_validation":
            if self.kinds.count("phase6_fallback_text_locator_validation") == 1:
                return {
                    "raw_text": json.dumps(
                        {
                            "semantic_correct": False,
                            "tight_enough": False,
                            "bbox_on_blank_area": False,
                            "bbox_targets_unrelated_text": True,
                            "visible_original_text": "スッ スッ スッ スッ",
                            "recommendation": "reject",
                            "reasoning_summary": "The bbox is directly below the target text and covers hair.",
                        },
                        ensure_ascii=False,
                    ),
                    "request": {"kind": kind, "image_path": str(image_path)},
                    "response": {"status": "ok"},
                }
            return _mimo_validation_response(kind, image_path, accepted=True)
        raise AssertionError(f"unexpected kind {kind}")


class _FakeMimoLocatorRetryLowRejectedThenAnchorRejected(_FakeMimoLocatorRetryLowRejectedThenAnchorRecovered):
    def analyze_image(self, image_path: str, prompt: str, kind: str = "image_analysis", max_completion_tokens: int | None = None):
        response = super().analyze_image(image_path, prompt, kind, max_completion_tokens)
        if (
            kind == "phase6_fallback_text_locator_validation"
            and self.kinds.count("phase6_fallback_text_locator_validation") == 2
        ):
            return {
                "raw_text": json.dumps(
                    {
                        "semantic_correct": False,
                        "tight_enough": False,
                        "bbox_on_blank_area": False,
                        "bbox_targets_unrelated_text": True,
                        "visible_original_text": "",
                        "recommendation": "reject",
                        "reasoning_summary": "The recovered bbox still includes unrelated artwork.",
                    },
                    ensure_ascii=False,
                ),
                "request": {"kind": kind, "image_path": str(image_path)},
                "response": {"status": "ok"},
            }
        return response


class _FakeMimoLocatorAcceptedTightBelowAnchorThenRecovered:
    def __init__(self):
        self.kinds = []

    def analyze_image(self, image_path: str, prompt: str, kind: str = "image_analysis", max_completion_tokens: int | None = None):
        self.kinds.append(kind)
        if kind == "phase6_fallback_text_locator":
            return {
                "raw_text": json.dumps(
                    {
                        "bbox_xyxy": [0, 455, 652, 570],
                        "confidence": 0.99,
                        "reasoning_summary": "bbox is accepted by the model but below the anchor text band",
                    },
                    ensure_ascii=False,
                ),
                "request": {"kind": kind, "image_path": str(image_path)},
                "response": {"status": "ok"},
            }
        if kind == "phase6_fallback_text_locator_validation":
            return _mimo_validation_response(kind, image_path, accepted=True)
        raise AssertionError(f"unexpected kind {kind}")


def _mimo_validation_response(kind: str, image_path: str | Path, accepted: bool) -> dict:
    payload = {
        "semantic_correct": accepted,
        "tight_enough": accepted,
        "bbox_on_blank_area": not accepted,
        "bbox_targets_unrelated_text": not accepted,
        "visible_original_text": "背景文字" if accepted else "",
        "recommendation": "accept" if accepted else "reject",
        "reasoning_summary": "bbox matches target text" if accepted else "bbox is on the wrong region",
    }
    return {
        "raw_text": json.dumps(payload, ensure_ascii=False),
        "request": {"kind": kind, "image_path": str(image_path)},
        "response": {"status": "ok"},
    }


def _has_reddish_pixel(image: Image.Image) -> bool:
    width, height = image.size
    for y in range(height):
        for x in range(width):
            red, green, blue = image.getpixel((x, y))
            if red > 150 and red > green + 40 and red > blue + 40:
                return True
    return False


def _has_editable_pixel(mask: Image.Image) -> bool:
    return any(value == 0 for value in mask.convert("RGBA").getchannel("A").getdata())


def _write_nonbubble_image(path: Path) -> Path:
    image = Image.new("RGB", (120, 100), (210, 205, 190))
    draw = ImageDraw.Draw(image)
    for y in range(100):
        draw.line((0, y, 120, y), fill=(190 + y // 4, 185 + y // 5, 170 + y // 6))
    _draw_fake_text_strokes(draw, origin=(35, 25))
    image.save(path)
    return path


def _draw_fake_text_strokes(draw: ImageDraw.ImageDraw, origin: tuple[int, int]) -> None:
    ox, oy = origin
    for offset in (0, 10, 20):
        x = ox + offset
        draw.line((x, oy, x, oy + 28), fill="black", width=3)
        draw.line((x - 5, oy + 12, x + 6, oy + 12), fill="black", width=2)


def _write_sparse_ink_nonbubble_image(path: Path) -> Path:
    image = Image.new("RGB", (120, 100), (230, 226, 214))
    draw = ImageDraw.Draw(image)
    for y in range(100):
        draw.line((0, y, 120, y), fill=(220 + y // 8, 216 + y // 9, 204 + y // 10))
    draw.line((46, 34, 46, 48), fill="black", width=3)
    draw.line((43, 40, 49, 40), fill="black", width=2)
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


def _write_light_sound_effect_panel(path: Path) -> Path:
    image = Image.new("RGB", (660, 660), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 659, 659), outline=(20, 20, 20), width=4)
    for left in (60, 170, 280, 390, 500):
        draw.polygon(
            [(left, 415), (left + 86, 399), (left + 98, 431), (left + 16, 447)],
            fill=(22, 22, 22),
        )
        draw.rectangle((left + 18, 445, left + 88, 479), fill=(25, 25, 25))
        draw.rectangle((left + 36, 429, left + 108, 459), fill=(24, 24, 24))
        draw.rectangle((left + 32, 436, left + 84, 453), fill="white")
    for x in range(90, 620, 34):
        draw.line((x, 542, x - 42, 655), fill=(92, 92, 92), width=2)
    draw.arc((118, 520, 552, 1040), start=192, end=346, fill=(36, 36, 36), width=3)
    image.save(path)
    return path


def _write_dark_vertical_text_near_anchor_panel(path: Path) -> Path:
    image = Image.new("RGB", (220, 220), "white")
    draw = ImageDraw.Draw(image)
    for offset, y in enumerate(range(42, 145, 18)):
        x = 92 + (offset % 2) * 8
        draw.line((x, y, x, y + 12), fill="black", width=3)
        draw.line((x - 4, y + 5, x + 5, y + 5), fill="black", width=2)
    draw.rectangle((154, 58, 205, 184), fill="black")
    draw.line((12, 170, 210, 118), fill=(160, 160, 160), width=2)
    image.save(path)
    return path


def _write_light_sound_effect_panel_with_sparse_right_screentone(path: Path) -> Path:
    image = Image.new("RGB", (660, 660), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 659, 659), outline=(20, 20, 20), width=4)
    for left in (60, 170, 280, 390):
        draw.polygon(
            [(left, 415), (left + 86, 399), (left + 98, 431), (left + 16, 447)],
            fill=(22, 22, 22),
        )
        draw.rectangle((left + 18, 445, left + 88, 479), fill=(25, 25, 25))
        draw.rectangle((left + 36, 429, left + 108, 459), fill=(24, 24, 24))
        draw.rectangle((left + 32, 436, left + 84, 453), fill="white")
    for x in range(515, 650, 18):
        draw.line((x, 407, x - 26, 516), fill=(82, 82, 82), width=2)
    for x in range(90, 620, 34):
        draw.line((x, 542, x - 42, 655), fill=(92, 92, 92), width=2)
    draw.arc((118, 520, 552, 1040), start=192, end=346, fill=(36, 36, 36), width=3)
    image.save(path)
    return path


def _write_light_sound_effect_panel_with_right_panel_divider(path: Path) -> Path:
    image = Image.new("RGB", (660, 660), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 659, 659), outline=(20, 20, 20), width=4)
    for left in (60, 170, 280, 390):
        draw.polygon(
            [(left, 415), (left + 86, 399), (left + 98, 431), (left + 16, 447)],
            fill=(22, 22, 22),
        )
        draw.rectangle((left + 18, 445, left + 88, 479), fill=(25, 25, 25))
        draw.rectangle((left + 36, 429, left + 108, 459), fill=(24, 24, 24))
        draw.rectangle((left + 32, 436, left + 84, 453), fill="white")
    draw.rectangle((486, 392, 505, 660), fill=(8, 8, 8))
    for x in range(525, 650, 16):
        draw.line((x, 407, x - 24, 516), fill=(82, 82, 82), width=2)
    for x in range(90, 620, 34):
        draw.line((x, 542, x - 42, 655), fill=(92, 92, 92), width=2)
    draw.arc((118, 520, 552, 1040), start=192, end=346, fill=(36, 36, 36), width=3)
    image.save(path)
    return path


def _write_light_sound_effect_panel_with_dark_vertical_decoy(path: Path) -> Path:
    image_path = _write_light_sound_effect_panel(path)
    with Image.open(image_path) as source:
        image = source.convert("RGB")
    draw = ImageDraw.Draw(image)
    for offset, y in enumerate(range(438, 548, 18)):
        x = 402 + (offset % 2) * 8
        draw.line((x, y, x, y + 12), fill=(8, 8, 8), width=4)
        draw.line((x - 5, y + 6, x + 6, y + 6), fill=(8, 8, 8), width=2)
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


def _assert_fallback_background_repaired(row: dict) -> None:
    cleanup = row["cleanup"]
    assert cleanup["method"] == "bt_lama_large_inpaint"
    assert cleanup["background_repair_method"] == "bt_lama_large_inpaint"
    assert Path(cleanup["cleaned_crop_path"]).parent.name == "fallback_cleaned"
    assert Path(cleanup["cleanup_mask_path"]).parent.name == "fallback_mask"
    assert Path(cleanup["before_after_path"]).parent.name == "fallback_before_after"
    assert Path(cleanup["cleaned_crop_path"]).exists()
    assert Path(cleanup["cleanup_mask_path"]).exists()
    assert Path(cleanup["before_after_path"]).exists()
