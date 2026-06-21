import json
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw

from autolettering.inpaint.bubble_fill import fill_text_box, sample_border_color
from autolettering.phase6 import run_phase6_bubble_cleanup


def test_sample_border_color_uses_pixels_around_bbox(tmp_path: Path):
    image = Image.new("RGB", (80, 80), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((20, 20, 60, 60), fill="black")
    image_path = tmp_path / "page.png"
    image.save(image_path)

    color = sample_border_color(image_path, (20, 20, 60, 60), inset=2)

    assert all(channel >= 240 for channel in color)


def test_fill_text_box_writes_cleaned_crop_and_before_after(tmp_path: Path):
    image = Image.new("RGB", (100, 100), "white")
    ImageDraw.Draw(image).rectangle((40, 30, 60, 70), fill="black")
    image_path = tmp_path / "page.png"
    image.save(image_path)

    result = fill_text_box(
        image_path=image_path,
        bbox=(35, 25, 65, 75),
        output_dir=tmp_path / "cleanup",
        record_id="page.png#1",
    )

    assert result.cleaned_crop_path.exists()
    assert result.before_after_path.exists()
    with Image.open(result.cleaned_crop_path) as cleaned:
        assert ImageChops.difference(cleaned.convert("RGB"), Image.new("RGB", cleaned.size, "white")).getbbox() is None


def test_run_phase6_bubble_cleanup_writes_results_and_artifacts(tmp_path: Path):
    image_path = _write_sample_image(tmp_path / "page.png")
    detection_run = tmp_path / "phase2"
    layout_run = tmp_path / "phase4"
    detection_run.mkdir()
    layout_run.mkdir()
    _write_detection(detection_run / "detections.jsonl", image_path)
    _write_layout(layout_run / "layout-results.jsonl")

    run_dir = run_phase6_bubble_cleanup(
        detection_run_dir=detection_run,
        layout_run_dir=layout_run,
        output_root=tmp_path / "outputs",
        run_id="phase6-test",
        sample_limit=1,
    )

    rows = _read_jsonl(run_dir / "cleanup-results.jsonl")
    assert rows[0]["record_id"] == "page.png#1"
    assert rows[0]["status"] == "cleaned"
    assert rows[0]["cleanup"]["method"] == "bubble_fill"
    assert Path(rows[0]["cleanup"]["cleaned_crop_path"]).exists()
    assert Path(rows[0]["cleanup"]["before_after_path"]).exists()
    assert (run_dir / "reports" / "phase6-report.md").exists()


def _write_sample_image(path: Path) -> Path:
    image = Image.new("RGB", (120, 120), "white")
    ImageDraw.Draw(image).rectangle((42, 35, 72, 85), fill="black")
    image.save(path)
    return path


def _write_detection(path: Path, image_path: Path) -> None:
    payload = {
        "record_id": "page.png#1",
        "status": "ok",
        "image_name": "page.png",
        "image_path": str(image_path),
        "group_name": "框内",
        "selected_text_box_xyxy": [35, 25, 80, 90],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_layout(path: Path) -> None:
    payload = {
        "record_id": "page.png#1",
        "status": "layout_generated",
        "layout": {"preview_path": "unused.png"},
    }
    path.write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
