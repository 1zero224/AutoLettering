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


def test_run_phase5_orientation_estimates_angle_from_tight_text_candidates(tmp_path: Path):
    image_path = tmp_path / "page.png"
    image = Image.new("RGB", (240, 200), "white")
    draw = ImageDraw.Draw(image)
    draw.line((0, 20, 220, 190), fill="black", width=8)
    draw.rectangle((42, 82, 148, 94), fill="black")
    image.save(image_path)
    detection_run = tmp_path / "phase2"
    detection_run.mkdir()
    payload = {
        "record_id": "page.png#1",
        "status": "ok",
        "image_name": "page.png",
        "image_path": str(image_path),
        "translated_text": "测试",
        "group_name": "框内",
        "selected_text_box_xyxy": [0, 0, 240, 200],
        "candidate_boxes": [
            {"xyxy": [0, 0, 240, 200], "area": 48000},
            {"xyxy": [40, 80, 150, 96], "area": 1760},
        ],
    }
    _write_jsonl(detection_run / "detections.jsonl", [payload])

    run_dir = run_phase5_orientation(
        detection_run_dir=detection_run,
        output_root=tmp_path / "outputs",
        run_id="phase5-tight-text-angle",
        sample_limit=1,
    )

    row = _read_jsonl(run_dir / "angle-results.jsonl")[0]
    orientation = row["orientation"]
    assert orientation["bbox"] == [40, 80, 150, 96]
    assert orientation["detected_orientation"] == "horizontal"
    assert abs(orientation["selected_angle_degrees"]) <= 1.0


def test_run_phase5_orientation_detects_vertical_from_multiple_text_columns(tmp_path: Path):
    image_path = tmp_path / "page.png"
    image = Image.new("RGB", (260, 220), "white")
    draw = ImageDraw.Draw(image)
    for x1, x2 in [(50, 74), (105, 129), (160, 184)]:
        draw.rectangle((x1, 45, x2, 175), fill="black")
    image.save(image_path)
    detection_run = tmp_path / "phase2"
    detection_run.mkdir()
    payload = {
        "record_id": "page.png#1",
        "status": "ok",
        "image_name": "page.png",
        "image_path": str(image_path),
        "translated_text": "测试",
        "group_name": "框内",
        "selected_text_box_xyxy": [20, 20, 220, 200],
        "candidate_boxes": [
            {"xyxy": [20, 20, 220, 200], "area": 36000},
            {"xyxy": [50, 45, 74, 175], "area": 3120},
            {"xyxy": [105, 45, 129, 175], "area": 3120},
            {"xyxy": [160, 45, 184, 175], "area": 3120},
        ],
    }
    _write_jsonl(detection_run / "detections.jsonl", [payload])

    run_dir = run_phase5_orientation(
        detection_run_dir=detection_run,
        output_root=tmp_path / "outputs",
        run_id="phase5-multi-column-angle",
        sample_limit=1,
    )

    orientation = _read_jsonl(run_dir / "angle-results.jsonl")[0]["orientation"]
    assert orientation["bbox"] == [50, 45, 74, 175]
    assert orientation["detected_orientation"] == "vertical"
    assert abs(orientation["selected_angle_degrees"]) <= 1.0


def test_run_phase5_orientation_filters_by_record_id_before_sample_limit(tmp_path: Path):
    image_path = tmp_path / "page.png"
    image = Image.new("RGB", (120, 160), "white")
    ImageDraw.Draw(image).rectangle((55, 20, 70, 140), fill="black")
    image.save(image_path)
    detection_run = tmp_path / "phase2"
    detection_run.mkdir()
    _write_detection(detection_run / "detections.jsonl", image_path, record_ids=["page.png#1", "page.png#2"])

    run_dir = run_phase5_orientation(
        detection_run_dir=detection_run,
        output_root=tmp_path / "outputs",
        run_id="phase5-filter-test",
        sample_limit=1,
        record_ids=["page.png#2"],
    )

    rows = _read_jsonl(run_dir / "angle-results.jsonl")
    assert [row["record_id"] for row in rows] == ["page.png#2"]


def _write_detection(path: Path, image_path: Path, record_ids: list[str] | None = None) -> None:
    rows = []
    for record_id in record_ids or ["page.png#1"]:
        rows.append(
            {
                "record_id": record_id,
                "status": "ok",
                "image_name": "page.png",
                "image_path": str(image_path),
                "translated_text": "测试",
                "group_name": "框内",
                "selected_text_box_xyxy": [0, 0, 120, 160],
            }
        )
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def _write_jsonl(path: Path, payloads: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in payloads),
        encoding="utf-8",
    )


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
