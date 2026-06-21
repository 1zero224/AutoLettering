import json
from pathlib import Path

from PIL import Image, ImageDraw

from autolettering.detection.cv_text import detect_text_region
from autolettering.detection.regions import build_search_region
from autolettering.labelplus.models import ManifestImage, ManifestLabel
from autolettering.phase2 import run_phase2


def _label(
    image_name: str = "page.png",
    x_px: int = 100,
    y_px: int = 100,
    record_index: int = 1,
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
        group_name="框内",
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
    assert (run_dir / "reports" / "phase2-report.md").exists()
