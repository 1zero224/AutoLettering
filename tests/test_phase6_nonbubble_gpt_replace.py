import json
from pathlib import Path

from PIL import Image, ImageDraw

from autolettering.gpt_text_mask import build_target_text_mask, build_text_pixel_gpt_mask
from autolettering.models.gpt_image import GptImageConfig
from autolettering.phase6_nonbubble_gpt_replace import run_phase6_nonbubble_gpt_replace


def test_run_phase6_nonbubble_gpt_replace_uses_context_mask_and_target_text(tmp_path: Path, monkeypatch):
    image_path = _write_nonbubble_image(tmp_path / "page.png")
    detection_run = tmp_path / "phase2"
    detection_run.mkdir()
    _write_detection(detection_run / "detections.jsonl", image_path)
    monkeypatch.setattr("autolettering.phase6_nonbubble_gpt_replace.GptImageEditClient", lambda config: _FakeGptClient())
    monkeypatch.setattr(
        "autolettering.inpaint.nonbubble.balloons_patchmatch_inpaint",
        lambda crop_arg, mask_arg: Image.new("RGB", crop_arg.size, "white"),
    )

    run_dir = run_phase6_nonbubble_gpt_replace(
        detection_run_dir=detection_run,
        output_root=tmp_path / "outputs",
        run_id="phase6-gpt-replace-test",
        sample_limit=1,
        gpt_config=GptImageConfig(base_url="https://example.test/v1/images", api_key="test", model="gpt-image-2"),
        call_gpt_image=True,
        bt_methods=["bt_patchmatch"],
        context_padding=10,
        rect_mask_expand_px=1,
    )

    rows = _read_jsonl(run_dir / "gpt-replace-results.jsonl")
    row = rows[0]
    assert row["schema_version"] == "autolettering.phase6.nonbubble_gpt_replace.v1"
    assert row["gpt_image2_replace"]["status"] == "ok"
    assert row["gpt_image2_replace"]["request"]["mode"] == "masked_chinese_replacement"
    assert row["gpt_image2_replace"]["request"]["target_text"] == "背景文字"
    assert Path(row["gpt_context"]["input_path"]).exists()
    assert Path(row["gpt_context"]["text_mask_path"]).exists()
    assert row["gpt_context"]["mask_strategy"] == "text_pixels_within_bbox"
    assert row["gpt_context"]["editable_pixel_count"] > 0
    with Image.open(row["gpt_context"]["mask_path"]) as mask:
        assert any(value == 0 for value in mask.getchannel("A").getdata())
        assert mask.getpixel((0, 0))[3] == 255
    assert (run_dir / "visuals" / "gpt-replace-bt-grid.png").exists()
    cleanup_rows = _read_jsonl(run_dir / "cleanup-results.jsonl")
    cleanup_row = cleanup_rows[0]
    cleanup = cleanup_row["cleanup"]
    assert cleanup_row["status"] == "cleaned"
    assert cleanup["method"] == "gpt_image2_text_pixel_masked_edit"
    assert cleanup["replacement_method"] == "gpt_image2_masked_edit"
    assert cleanup["text_overlay_required"] is False
    assert cleanup["replacement_crop_path"] == row["gpt_image2_replace"]["context_replacement_crop_path"]
    assert cleanup["cleaned_crop_path"] != cleanup["replacement_crop_path"]
    assert cleanup["bbox"] == [10, 5, 100, 85]
    assert cleanup["text_bbox"] == [20, 15, 90, 75]
    assert cleanup["mask_bbox"] == [19, 14, 91, 76]
    assert cleanup["layout_text_bbox"] == [20, 15, 90, 75]
    assert Path(row["gpt_image2_replace"]["target_crop_path"]).exists()
    with Image.open(cleanup["cleaned_crop_path"]) as cleaned, Image.open(cleanup["replacement_crop_path"]) as replacement:
        assert cleaned.size == replacement.size == (90, 80)
    assert cleanup_row["gpt_image2_edit"]["status"] == "ok"


def test_run_phase6_nonbubble_gpt_replace_masks_text_pixels_inside_large_bbox(tmp_path: Path, monkeypatch):
    image_path = _write_large_bbox_image(tmp_path / "page-large.png")
    detection_run = tmp_path / "phase2"
    detection_run.mkdir()
    _write_large_bbox_detection(detection_run / "detections.jsonl", image_path)
    monkeypatch.setattr(
        "autolettering.inpaint.nonbubble.balloons_patchmatch_inpaint",
        lambda crop_arg, mask_arg: Image.new("RGB", crop_arg.size, "white"),
    )

    run_dir = run_phase6_nonbubble_gpt_replace(
        detection_run_dir=detection_run,
        output_root=tmp_path / "outputs",
        run_id="phase6-gpt-replace-large-bbox-mask-test",
        sample_limit=1,
        bt_methods=["bt_patchmatch"],
        context_padding=4,
        rect_mask_expand_px=1,
    )

    rows = _read_jsonl(run_dir / "gpt-replace-results.jsonl")
    row = rows[0]
    local = row["local_target_bbox"]
    with Image.open(row["gpt_context"]["mask_path"]) as mask_image:
        alpha = mask_image.getchannel("A")
        editable_pixels = sum(1 for value in alpha.getdata() if value == 0)
        target_area = (local[2] - local[0] + 1) * (local[3] - local[1] + 1)
        assert editable_pixels < target_area * 0.45
        # The non-text solid figure is inside the broad bbox, but must remain protected.
        assert alpha.getpixel((local[0] + 12, local[1] + 12)) == 255
        # The text strokes inside the same bbox are editable.
        assert alpha.getpixel((local[0] + 73, local[1] + 14)) == 0
    assert row["gpt_context"]["mask_strategy"] == "text_pixels_within_bbox"
    cleanup_row = _read_jsonl(run_dir / "cleanup-results.jsonl")[0]
    cleanup = cleanup_row["cleanup"]
    assert cleanup_row["status"] == "cleaned"
    assert cleanup["text_overlay_required"] is True
    assert cleanup["replacement_method"] is None
    assert cleanup["replacement_crop_path"] is None
    assert cleanup["cleaned_crop_path"] != cleanup["replacement_crop_path"]
    assert cleanup["bbox"] == [6, 11, 124, 94]
    assert cleanup["text_bbox"] == [10, 15, 120, 90]
    assert cleanup["mask_bbox"] == [9, 14, 121, 91]
    assert cleanup["layout_text_bbox"] == [10, 15, 120, 90]


def test_light_on_dark_text_pixel_mask_excludes_bright_crop_edge():
    crop = Image.new("RGB", (120, 60), "black")
    draw = ImageDraw.Draw(crop)
    for x in range(20, 84, 12):
        draw.rectangle((x, 20, x + 7, 34), fill="white")
    draw.rectangle((112, 0, 119, 59), fill="white")

    mask = build_target_text_mask(crop, polarity="light_on_dark", expand_px=2)

    assert mask.getpixel((24, 24)) == 255
    assert mask.getpixel((116, 30)) == 0


def test_text_pixel_gpt_mask_does_not_fallback_to_full_rect_when_no_text_pixels():
    crop = Image.new("RGB", (140, 100), (235, 232, 224))

    result = build_text_pixel_gpt_mask(crop, (10, 10, 120, 90), polarity="dark_on_light", expand_px=1)

    assert result.strategy == "no_text_pixels_protected"
    assert result.editable_pixel_count == 0
    assert not any(value == 0 for value in result.gpt_mask.getchannel("A").getdata())


def test_run_phase6_nonbubble_gpt_replace_records_bt_method_failures(tmp_path: Path, monkeypatch):
    image_path = _write_nonbubble_image(tmp_path / "page.png")
    detection_run = tmp_path / "phase2"
    detection_run.mkdir()
    _write_detection(detection_run / "detections.jsonl", image_path)
    monkeypatch.setattr(
        "autolettering.inpaint.nonbubble.balloons_patchmatch_inpaint",
        lambda crop_arg, mask_arg: Image.new("RGB", crop_arg.size, "white"),
    )

    run_dir = run_phase6_nonbubble_gpt_replace(
        detection_run_dir=detection_run,
        output_root=tmp_path / "outputs",
        run_id="phase6-gpt-replace-bt-failure-test",
        sample_limit=1,
        bt_methods=["bt_patchmatch", "bad_method"],
    )

    rows = _read_jsonl(run_dir / "gpt-replace-results.jsonl")
    assert rows[0]["bt_repairs"][0]["status"] == "ok"
    assert rows[0]["bt_repairs"][1]["status"] == "failed"
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["bt_failed_count"] == 1


def test_run_phase6_nonbubble_gpt_replace_surfaces_mimo_quality_failure(tmp_path: Path, monkeypatch):
    image_path = _write_nonbubble_image(tmp_path / "page.png")
    detection_run = tmp_path / "phase2"
    detection_run.mkdir()
    _write_detection(detection_run / "detections.jsonl", image_path)
    monkeypatch.setattr("autolettering.phase6_nonbubble_gpt_replace.GptImageEditClient", lambda config: _FakeGptClient())
    monkeypatch.setattr(
        "autolettering.inpaint.nonbubble.balloons_patchmatch_inpaint",
        lambda crop_arg, mask_arg: Image.new("RGB", crop_arg.size, "white"),
    )

    run_dir = run_phase6_nonbubble_gpt_replace(
        detection_run_dir=detection_run,
        output_root=tmp_path / "outputs",
        run_id="phase6-gpt-replace-quality-failure-test",
        sample_limit=1,
        gpt_config=GptImageConfig(base_url="https://example.test/v1/images", api_key="test", model="gpt-image-2"),
        call_gpt_image=True,
        bt_methods=["bt_patchmatch"],
        mimo_client=_FakeMimoClient(),
    )

    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["gpt_ok_count"] == 1
    assert manifest["gpt_quality_checked_count"] == 1
    assert manifest["gpt_quality_failed_count"] == 1
    assert manifest["mimo"]["quality"]["gpt_image2_status"] == "unacceptable"
    assert manifest["mimo"]["quality"]["unacceptable_methods"] == ["gpt-image-2 cn"]
    report = (run_dir / "reports" / "phase6-nonbubble-gpt-replace-report.md").read_text(encoding="utf-8")
    assert "- GPT image-2 quality failures: 1" in report
    assert "- MIMO GPT image-2 status: `unacceptable`" in report


class _FakeGptClient:
    def edit_image(self, image_path: str, mask_path: str, prompt: str, output_path: str) -> dict:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(image_path) as image:
            Image.new("RGB", image.size, "white").save(output)
        return {"status": "ok", "output_path": str(output), "response": {"usage": {"total_tokens": 1}}}


class _FakeMimoClient:
    def analyze_image(self, image_path: str, prompt: str, kind: str = "image_analysis", max_completion_tokens: int | None = None):
        return {
            "raw_text": json.dumps(
                {
                    "gpt_image2_scores": {
                        "exact_simplified_chinese_text_correctness": 0,
                        "no_japanese_text_remaining": 0,
                    },
                    "bt_ranking": ["bt_patchmatch"],
                    "unacceptable_methods": ["gpt-image-2 cn"],
                    "best_overall_for_user_choice": "bt_patchmatch",
                    "reasoning_summary": "gpt-image-2 produced the wrong language.",
                    "caveats": "fake response",
                },
                ensure_ascii=False,
            ),
            "request": {"kind": kind, "image_path": str(image_path), "prompt_chars": len(prompt)},
            "response": {"status": "ok"},
        }


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


def _write_large_bbox_image(path: Path) -> Path:
    image = Image.new("RGB", (160, 120), (235, 232, 224))
    draw = ImageDraw.Draw(image)
    draw.rectangle((15, 20, 45, 84), fill=(36, 36, 36))
    for y in range(28, 82, 18):
        draw.rectangle((82, y, 104, y + 8), fill=(20, 20, 20))
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)
    return path


def _write_detection(path: Path, image_path: Path) -> None:
    row = {
        "status": "ok",
        "image_name": "page.png",
        "image_path": str(image_path),
        "record_id": "page.png#2",
        "group_name": "框外",
        "translated_text": "背景文字",
        "selected_text_box_xyxy": [20, 15, 90, 75],
    }
    path.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_large_bbox_detection(path: Path, image_path: Path) -> None:
    row = {
        "status": "ok",
        "image_name": "page-large.png",
        "image_path": str(image_path),
        "record_id": "page-large.png#1",
        "group_name": "框外",
        "translated_text": "只改文字",
        "selected_text_box_xyxy": [10, 15, 120, 90],
        "candidate_boxes": [{"xyxy": [10, 15, 120, 90], "score": 1.0, "polarity": "dark_on_light"}],
    }
    path.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
