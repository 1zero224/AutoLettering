import json
from pathlib import Path

from PIL import Image, ImageDraw

from autolettering.layout.orientation import draw_angle_debug_grid, estimate_orientation_angle
from autolettering.phase5 import run_phase5_orientation


def test_estimate_orientation_angle_detects_horizontal_text_region(tmp_path: Path):
    image_path = tmp_path / "horizontal.png"
    image = Image.new("RGB", (160, 100), "white")
    ImageDraw.Draw(image).rectangle((30, 45, 130, 58), fill="black")
    image.save(image_path)

    estimate = estimate_orientation_angle(image_path, (0, 0, 160, 100))

    assert estimate.status == "ok"
    assert estimate.detected_orientation == "horizontal"
    assert abs(estimate.estimated_angle_degrees) <= 1.0
    assert estimate.selected_angle_degrees in estimate.candidate_angles


def test_estimate_orientation_angle_detects_vertical_text_region(tmp_path: Path):
    image_path = tmp_path / "vertical.png"
    image = Image.new("RGB", (120, 160), "white")
    ImageDraw.Draw(image).rectangle((55, 20, 70, 140), fill="black")
    image.save(image_path)

    estimate = estimate_orientation_angle(image_path, (0, 0, 120, 160))

    assert estimate.status == "ok"
    assert estimate.detected_orientation == "vertical"
    assert abs(estimate.estimated_angle_degrees) <= 1.0
    assert estimate.confidence > 0.5


def test_estimate_orientation_angle_reports_insufficient_dark_pixels(tmp_path: Path):
    image_path = tmp_path / "blank.png"
    Image.new("RGB", (80, 80), "white").save(image_path)

    estimate = estimate_orientation_angle(image_path, (0, 0, 80, 80))

    assert estimate.status == "failed"
    assert estimate.failure_reason == "insufficient_dark_pixels"
    assert estimate.candidate_angles == []


def test_draw_angle_debug_grid_writes_candidate_preview(tmp_path: Path):
    image_path = tmp_path / "vertical.png"
    image = Image.new("RGB", (120, 160), "white")
    ImageDraw.Draw(image).rectangle((55, 20, 70, 140), fill="black")
    image.save(image_path)
    estimate = estimate_orientation_angle(image_path, (0, 0, 120, 160))

    output_path = draw_angle_debug_grid(image_path, (0, 0, 120, 160), estimate, tmp_path / "grid.png")

    assert output_path.exists()
    with Image.open(output_path) as debug:
        assert debug.size[0] >= 180
        assert debug.size[1] == 190


def test_run_phase5_orientation_writes_results_and_report(tmp_path: Path):
    image_path = tmp_path / "page.png"
    image = Image.new("RGB", (120, 160), "white")
    ImageDraw.Draw(image).rectangle((55, 20, 70, 140), fill="black")
    image.save(image_path)
    detection_run = tmp_path / "phase2"
    detection_run.mkdir()
    _write_detection(detection_run / "detections.jsonl", image_path)

    run_dir = run_phase5_orientation(
        detection_run_dir=detection_run,
        output_root=tmp_path / "outputs",
        run_id="phase5-test",
        sample_limit=1,
    )

    rows = _read_jsonl(run_dir / "angle-results.jsonl")
    assert rows[0]["record_id"] == "page.png#1"
    assert rows[0]["status"] == "angle_estimated"
    assert rows[0]["orientation"]["detected_orientation"] == "vertical"
    assert Path(rows[0]["orientation"]["debug_preview_grid_path"]).exists()
    assert (run_dir / "reports" / "phase5-report.md").exists()


def _write_detection(path: Path, image_path: Path) -> None:
    payload = {
        "record_id": "page.png#1",
        "status": "ok",
        "image_name": "page.png",
        "image_path": str(image_path),
        "translated_text": "测试",
        "group_name": "框内",
        "selected_text_box_xyxy": [0, 0, 120, 160],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
