import csv
import json
from pathlib import Path

from PIL import Image, ImageDraw

from autolettering.detection.cv_text import detect_text_region, detection_result_to_dict
from autolettering.detection.regions import build_search_region
from autolettering.labelplus.models import ManifestImage, ManifestLabel
from autolettering.phase2 import run_phase2
from autolettering.text_bbox import selected_text_bbox


def _label(
    image_name: str = "page.png",
    x_px: int = 100,
    y_px: int = 100,
    record_index: int = 1,
    group_name: str = "框内",
) -> ManifestLabel:
    return ManifestLabel(
        id=f"{image_name}#{record_index}",
        page_index=1,
        record_index=record_index,
        x_ratio=x_px / 240,
        y_ratio=y_px / 240,
        x_px=x_px,
        y_px=y_px,
        group_id=1,
        group_name=group_name,
        translated_text="测试",
    )


def test_build_search_region_clamps_to_image_bounds():
    assert build_search_region(5, 8, width=100, height=120, radius_x=30, radius_y=40) == (0, 0, 35, 48)
    assert build_search_region(95, 110, width=100, height=120, radius_x=30, radius_y=40) == (65, 70, 100, 120)


def test_detect_text_region_selects_dark_cluster_near_label_point(tmp_path: Path):
    image_path = tmp_path / "page.png"
    image = Image.new("RGB", (240, 240), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((90, 72, 115, 150), fill="black")
    draw.rectangle((160, 20, 190, 50), fill="black")
    image.save(image_path)

    result = detect_text_region(
        image_path=image_path,
        label=_label(x_px=102, y_px=110),
        image_width=240,
        image_height=240,
        radius_x=70,
        radius_y=90,
    )

    assert result.status == "ok"
    assert result.selected_text_box_xyxy is not None
    x1, y1, x2, y2 = result.selected_text_box_xyxy
    assert x1 <= 90
    assert y1 <= 72
    assert x2 >= 115
    assert y2 >= 150
    assert result.confidence > 0.5
    assert result.failure_reason is None


def test_detect_text_region_selects_light_text_on_dark_background_near_label_point(tmp_path: Path):
    image_path = tmp_path / "dark-panel.png"
    image = Image.new("RGB", (240, 240), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((45, 45, 175, 170), fill=(20, 20, 20))
    draw.rectangle((88, 70, 108, 125), fill="white")
    draw.rectangle((116, 70, 136, 125), fill="white")
    draw.rectangle((170, 20, 205, 55), fill="black")
    image.save(image_path)

    result = detect_text_region(
        image_path=image_path,
        label=_label(image_name="dark-panel.png", x_px=112, y_px=105),
        image_width=240,
        image_height=240,
        radius_x=90,
        radius_y=90,
    )

    assert result.status == "ok"
    assert result.selected_text_box_xyxy is not None
    x1, y1, x2, y2 = result.selected_text_box_xyxy
    assert x1 <= 88
    assert y1 <= 70
    assert x2 >= 136
    assert y2 >= 125
    assert result.candidate_boxes[0].polarity == "light_on_dark"


def test_detect_text_region_selects_light_text_on_mid_dark_color_background(tmp_path: Path):
    image_path = tmp_path / "red-promo.png"
    image = Image.new("RGB", (240, 420), (205, 112, 112))
    draw = ImageDraw.Draw(image)
    for y in range(80, 320, 46):
        draw.rectangle((158, y, 188, y + 28), fill=(250, 250, 250))
        draw.rectangle((188, y + 8, 198, y + 18), fill=(80, 70, 70))
    draw.rectangle((118, 360, 150, 386), fill=(255, 255, 255))
    image.save(image_path)

    result = detect_text_region(
        image_path=image_path,
        label=_label(image_name="red-promo.png", x_px=176, y_px=104, group_name="框外"),
        image_width=240,
        image_height=420,
        radius_x=80,
        radius_y=220,
    )

    assert result.status == "ok"
    assert result.selected_text_box_xyxy is not None
    x1, y1, x2, y2 = selected_text_bbox(detection_result_to_dict(result))
    assert x1 <= 158
    assert y1 <= 80
    assert x2 >= 188
    assert y2 >= 300
    assert result.candidate_boxes[0].polarity == "light_on_dark"


def test_detect_text_region_reports_no_dark_pixels_on_blank_image(tmp_path: Path):
    image_path = tmp_path / "blank.png"
    Image.new("RGB", (120, 120), "white").save(image_path)

    result = detect_text_region(
        image_path=image_path,
        label=_label(image_name="blank.png", x_px=60, y_px=60),
        image_width=120,
        image_height=120,
        radius_x=40,
        radius_y=40,
    )

    assert result.status == "failed"
    assert result.selected_text_box_xyxy is None
    assert result.candidate_boxes == []
    assert result.failure_reason == "no_dark_pixels"


def test_detect_text_region_expands_vertical_search_for_nonbubble_edge_caption(tmp_path: Path):
    image_path = tmp_path / "edge-caption.png"
    image = Image.new("RGB", (300, 900), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((245, 70, 270, 220), fill="black")
    draw.rectangle((246, 360, 269, 500), fill="black")
    image.save(image_path)

    result = detect_text_region(
        image_path=image_path,
        label=_label(image_name="edge-caption.png", x_px=286, y_px=120, group_name="框外"),
        image_width=300,
        image_height=900,
        radius_x=70,
        radius_y=80,
    )

    assert result.status == "ok"
    assert result.search_region_xyxy[3] >= 680
    assert any(candidate.xyxy[1] >= 340 for candidate in result.candidate_boxes)


def test_run_phase2_writes_detections_and_debug_overlays(tmp_path: Path):
    project_dir = tmp_path / "sample_project"
    project_dir.mkdir()

    image_path = project_dir / "page.png"
    image = Image.new("RGB", (240, 240), "white")
    ImageDraw.Draw(image).rectangle((90, 72, 115, 150), fill="black")
    image.save(image_path)

    (project_dir / "翻译_0.txt").write_text(
        """1,0
-
框内
-
Comment

>>>>>>>>[page.png]<<<<<<<<
----------------[1]----------------[0.425,0.458,1]
测试
""",
        encoding="utf-8",
    )

    run_dir = run_phase2(
        project_dir / "翻译_0.txt",
        output_root=tmp_path / "outputs",
        run_id="phase2-test",
        sample_limit=1,
        radius_x=70,
        radius_y=90,
    )

    detection_path = run_dir / "detections.jsonl"
    assert detection_path.exists()
    records = [json.loads(line) for line in detection_path.read_text(encoding="utf-8").splitlines()]
    assert records[0]["record_id"] == "page.png#1"
    assert records[0]["status"] == "ok"
    assert records[0]["selected_text_box_xyxy"] is not None
    assert Path(records[0]["debug_image_path"]).exists()
    review_path = run_dir / "reports" / "manual-review.csv"
    review_rows = list(csv.DictReader(review_path.read_text(encoding="utf-8").splitlines()))
    assert review_rows[0]["record_id"] == "page.png#1"
    assert review_rows[0]["status"] == "ok"
    assert review_rows[0]["manual_decision"] == ""
    assert review_rows[0]["candidate_count"] == str(len(records[0]["candidate_boxes"]))
    assert review_rows[0]["selected_text_box_xyxy"] == json.dumps(records[0]["selected_text_box_xyxy"])
    assert review_rows[0]["selected_text_full_xyxy"] == json.dumps(records[0]["selected_text_full_xyxy"])
    assert review_rows[0]["selected_text_body_xyxy"] == json.dumps(records[0]["selected_text_body_xyxy"])
    assert Path(review_rows[0]["debug_image_path"]).exists()
    assert (run_dir / "reports" / "phase2-report.md").exists()


def test_run_phase2_reports_full_and_body_text_bboxes(tmp_path: Path):
    project_dir = tmp_path / "sample_project"
    project_dir.mkdir()

    image_path = project_dir / "edge-title.png"
    image = Image.new("RGB", (240, 420), "white")
    draw = ImageDraw.Draw(image)
    draw.polygon([(200, 22), (224, 46), (200, 70), (176, 46)], fill="black")
    for y in (94, 140, 186, 232, 278, 324):
        draw.rectangle((188, y, 214, y + 6), fill="black")
        draw.rectangle((198, y, 204, y + 30), fill="black")
    image.save(image_path)

    (project_dir / "翻译_0.txt").write_text(
        """1,0
-
框外
-
Comment

>>>>>>>>[edge-title.png]<<<<<<<<
----------------[1]----------------[0.921,0.119,1]
来自桃香的唐突的提案
""",
        encoding="utf-8",
    )

    run_dir = run_phase2(
        project_dir / "翻译_0.txt",
        output_root=tmp_path / "outputs",
        run_id="phase2-derived-bbox-test",
        sample_limit=1,
        radius_x=70,
        radius_y=70,
    )

    record = json.loads((run_dir / "detections.jsonl").read_text(encoding="utf-8").strip())
    review_row = next(csv.DictReader((run_dir / "reports" / "manual-review.csv").read_text(encoding="utf-8").splitlines()))

    assert record["selected_text_box_xyxy"][1] <= 22
    assert record["selected_text_full_xyxy"][1] <= 22
    assert record["selected_text_full_xyxy"][3] >= 350
    assert record["selected_text_body_xyxy"][1] >= 90
    assert record["selected_text_body_xyxy"][3] == record["selected_text_full_xyxy"][3]
    assert review_row["selected_text_full_xyxy"] == json.dumps(record["selected_text_full_xyxy"])
    assert review_row["selected_text_body_xyxy"] == json.dumps(record["selected_text_body_xyxy"])


def test_run_phase2_can_filter_by_record_id(tmp_path: Path):
    project_dir = tmp_path / "sample_project"
    project_dir.mkdir()

    image_path = project_dir / "page.png"
    image = Image.new("RGB", (240, 240), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((35, 35, 55, 80), fill="black")
    draw.rectangle((150, 125, 175, 200), fill="black")
    image.save(image_path)

    (project_dir / "翻译_0.txt").write_text(
        """1,0
-
框内
-
Comment

>>>>>>>>[page.png]<<<<<<<<
----------------[1]----------------[0.188,0.240,1]
第一条
----------------[2]----------------[0.677,0.677,1]
第二条
""",
        encoding="utf-8",
    )

    run_dir = run_phase2(
        project_dir / "翻译_0.txt",
        output_root=tmp_path / "outputs",
        run_id="phase2-record-filter-test",
        sample_limit=1,
        radius_x=70,
        radius_y=90,
        record_ids=["page.png#2"],
    )

    records = [json.loads(line) for line in (run_dir / "detections.jsonl").read_text(encoding="utf-8").splitlines()]

    assert [record["record_id"] for record in records] == ["page.png#2"]
    assert records[0]["translated_text"] == "第二条"
