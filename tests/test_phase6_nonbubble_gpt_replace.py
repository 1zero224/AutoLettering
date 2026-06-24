import json
from pathlib import Path

from PIL import Image, ImageDraw

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
    with Image.open(row["gpt_context"]["mask_path"]) as mask:
        local = row["local_target_bbox"]
        assert mask.getpixel((local[0], local[1]))[3] == 0
        assert mask.getpixel((0, 0))[3] == 255
    assert (run_dir / "visuals" / "gpt-replace-bt-grid.png").exists()


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


class _FakeGptClient:
    def edit_image(self, image_path: str, mask_path: str, prompt: str, output_path: str) -> dict:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(image_path) as image:
            Image.new("RGB", image.size, "white").save(output)
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


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
