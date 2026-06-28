import csv
import json
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from autolettering.detection.cv_text import detect_text_region, detection_result_to_dict
from autolettering.detection.comic_text_bubble import ComicTextBubbleDetection
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


def test_detect_text_region_selects_gbc06_17_black_card_title_instead_of_speech_bubble():
    image_path = Path("GBC06 (已翻 斗笠)") / "GBC06_17.png"
    if not image_path.exists():
        pytest.skip("GBC06 sample image is not available")

    result = detect_text_region(
        image_path=image_path,
        label=_label(image_name="GBC06_17.png", x_px=1073, y_px=272, record_index=3, group_name="框外"),
        image_width=1440,
        image_height=2048,
        radius_x=220,
        radius_y=180,
    )

    assert result.status == "ok"
    assert result.selected_text_box_xyxy is not None
    x1, y1, x2, y2 = result.selected_text_box_xyxy
    assert x1 <= 1025
    assert 210 <= y1 <= 235
    assert x2 >= 1135
    assert y2 <= 285
    assert x2 < 1187
    assert result.candidate_boxes[0].polarity == "light_on_dark"

    full_x1, full_y1, full_x2, full_y2 = selected_text_bbox(detection_result_to_dict(result))
    assert full_x1 <= 1025
    assert 210 <= full_y1 <= 235
    assert full_x2 >= 1135
    assert full_y2 <= 285


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
        detection_strategy="cv",
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
        detection_strategy="cv",
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


def test_run_phase2_can_record_direct_model_text_region_recognition(tmp_path: Path):
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
----------------[1]----------------[0.417,0.417,1]
测试
""",
        encoding="utf-8",
    )

    client = _FakeModelTextRegionClient(
        {
            "found": True,
            "bbox_xyxy": [62, 64, 91, 142],
            "source_text": "テスト",
            "orientation": "vertical",
            "confidence": 0.76,
            "reasoning_summary": "Text column near the LabelPlus point.",
        }
    )

    run_dir = run_phase2(
        project_dir / "翻译_0.txt",
        output_root=tmp_path / "outputs",
        run_id="phase2-model-recognition-test",
        sample_limit=1,
        radius_x=70,
        radius_y=90,
        detection_strategy="cv",
        call_model_text_recognition=True,
        model_text_recognition_client=client,
    )

    record = json.loads((run_dir / "detections.jsonl").read_text(encoding="utf-8").strip())
    recognition = record["model_text_recognition"]

    assert recognition["status"] == "ok"
    assert recognition["local_bbox_xyxy"] == [62, 64, 91, 142]
    assert recognition["global_bbox_xyxy"] == [92, 74, 121, 152]
    assert recognition["source_text"] == "テスト"
    assert recognition["orientation"] == "vertical"
    assert recognition["confidence"] == 0.76
    assert Path(recognition["context_image_path"]).exists()
    assert client.calls[0]["kind"] == "phase2_model_text_region_recognition"
    assert client.calls[0]["image_path"] == Path(recognition["context_image_path"])
    assert "X-AnyLabeling" not in client.calls[0]["prompt"]
    assert "LabelPlus point in this crop: [70, 90]" in client.calls[0]["prompt"]
    assert record["recognized_source_text"] == "テスト"
    assert record["recognized_orientation"] == "vertical"


def test_run_phase2_can_use_direct_comic_rtdetrv2_detector(tmp_path: Path, monkeypatch):
    project_dir = tmp_path / "sample_project"
    project_dir.mkdir()

    image_path = project_dir / "page.png"
    Image.new("RGB", (240, 240), "white").save(image_path)
    (project_dir / "翻译_0.txt").write_text(
        """1,0
-
框外
-
Comment

>>>>>>>>[page.png]<<<<<<<<
----------------[1]----------------[0.500,0.500,1]
测试框外
""",
        encoding="utf-8",
    )

    fake_model = tmp_path / "detector.onnx"
    fake_model.write_bytes(b"fake")
    monkeypatch.setattr("autolettering.phase2.ComicTextBubbleDetector", _FakeComicTextBubbleDetector)

    run_dir = run_phase2(
        project_dir / "翻译_0.txt",
        output_root=tmp_path / "outputs",
        run_id="phase2-comic-rtdetrv2-test",
        sample_limit=1,
        detection_strategy="comic_rtdetrv2",
        comic_detector_model_path=fake_model,
        comic_detector_conf_threshold=0.42,
        comic_detector_max_distance_px=80,
    )

    record = json.loads((run_dir / "detections.jsonl").read_text(encoding="utf-8").strip())
    match = record["comic_text_bubble_match"]

    assert record["status"] == "ok"
    assert record["detection_method"] == "comic_rtdetrv2"
    assert record["selected_text_box_xyxy"] == [88, 82, 135, 150]
    assert record["selected_text_full_xyxy"] == [88, 82, 135, 150]
    assert record["selected_text_body_xyxy"] == [88, 82, 135, 150]
    assert record["text_region_kind"] == "comic_text_bubble_rtdetrv2_matched"
    assert record["text_region_source"] == "comic_text_bubble_rtdetrv2"
    assert record["lettering_route"]["route"] == "comic_text_bubble_detect_then_configured_cleanup"
    assert match["status"] == "matched"
    assert match["selected_label"] == "text_free"
    assert match["selected_score"] == 0.88
    assert match["threshold_px"] == 80
    assert record["comic_text_bubble_detections"][0]["label"] == "text_free"
    review_row = next(csv.DictReader((run_dir / "reports" / "manual-review.csv").read_text(encoding="utf-8").splitlines()))
    assert review_row["comic_match_status"] == "matched"
    assert review_row["comic_match_label"] == "text_free"
    assert review_row["comic_match_score"] == "0.88"
    assert review_row["comic_match_distance_px"] == "0.0"
    assert review_row["comic_match_threshold_px"] == "80"
    report = (run_dir / "reports" / "phase2-report.md").read_text(encoding="utf-8")
    assert "Comic text/bubble RT-DETRv2" in report
    assert "`comic_text_bubble_detections`" in report
    assert "selected comic detector label" in report
    assert f"Comic detector model: `{fake_model}`" in report
    assert "Comic detector confidence threshold: `0.42`" in report
    assert "Comic detector max match distance: `80px`" in report


def test_run_phase2_comic_fallback_expands_context_with_detector_candidates(tmp_path: Path, monkeypatch):
    project_dir = tmp_path / "sample_project"
    project_dir.mkdir()

    image_path = project_dir / "page.png"
    Image.new("RGB", (300, 300), "white").save(image_path)
    (project_dir / "翻译_0.txt").write_text(
        """1,0
-
框外
-
Comment

>>>>>>>>[page.png]<<<<<<<<
----------------[1]----------------[0.500,0.500,1]
测试框外
""",
        encoding="utf-8",
    )

    fake_model = tmp_path / "detector.onnx"
    fake_model.write_bytes(b"fake")
    monkeypatch.setattr("autolettering.phase2.ComicTextBubbleDetector", _FakeDistantComicTextBubbleDetector)

    run_dir = run_phase2(
        project_dir / "翻译_0.txt",
        output_root=tmp_path / "outputs",
        run_id="phase2-comic-rtdetrv2-fallback-test",
        sample_limit=1,
        radius_x=20,
        radius_y=20,
        detection_strategy="comic_rtdetrv2",
        comic_detector_model_path=fake_model,
        comic_detector_max_distance_px=10,
    )

    record = json.loads((run_dir / "detections.jsonl").read_text(encoding="utf-8").strip())
    fallback = record["fallback"]

    assert record["status"] == "fallback_required"
    assert record["comic_text_bubble_match"]["failure_reason"] == "no_comic_text_box_within_threshold"
    assert fallback["context_source"] == "labelplus_search_region_plus_comic_text_bubble_candidates"
    assert fallback["source_context_bbox_xyxy"] == [130, 130, 170, 170]
    assert fallback["expanded_source_context_bbox_xyxy"] == [130, 130, 260, 260]
    assert fallback["context_candidate_detection_ids"] == ["text_free-1"]
    assert fallback["context_candidate_bboxes_xyxy"] == [[220, 220, 260, 260]]
    assert fallback["context_candidate_labels"] == ["text_free"]
    assert fallback["context_candidate_scores"] == [0.74]
    assert fallback["upstream_match_metric"] == "labelplus_point_to_comic_text_box_distance"
    assert fallback["upstream_match_threshold_px"] == 10


def test_run_phase2_comic_fallback_does_not_use_bubble_only_candidates(tmp_path: Path, monkeypatch):
    project_dir = tmp_path / "sample_project"
    project_dir.mkdir()

    image_path = project_dir / "page.png"
    Image.new("RGB", (300, 300), "white").save(image_path)
    (project_dir / "翻译_0.txt").write_text(
        """1,0
-
框外
-
Comment

>>>>>>>>[page.png]<<<<<<<<
----------------[1]----------------[0.500,0.500,1]
测试框外
""",
        encoding="utf-8",
    )

    fake_model = tmp_path / "detector.onnx"
    fake_model.write_bytes(b"fake")
    monkeypatch.setattr("autolettering.phase2.ComicTextBubbleDetector", _FakeBubbleOnlyComicTextBubbleDetector)

    run_dir = run_phase2(
        project_dir / "翻译_0.txt",
        output_root=tmp_path / "outputs",
        run_id="phase2-comic-rtdetrv2-bubble-only-fallback-test",
        sample_limit=1,
        radius_x=20,
        radius_y=20,
        detection_strategy="comic_rtdetrv2",
        comic_detector_model_path=fake_model,
        comic_detector_max_distance_px=10,
    )

    record = json.loads((run_dir / "detections.jsonl").read_text(encoding="utf-8").strip())
    fallback = record["fallback"]

    assert record["status"] == "fallback_required"
    assert record["comic_text_bubble_match"]["failure_reason"] == "no_comic_text_box"
    assert record["comic_text_bubble_match"]["top_candidates"][0]["label"] == "bubble"
    assert fallback["context_source"] == "labelplus_search_region"
    assert fallback["source_context_bbox_xyxy"] == [130, 130, 170, 170]
    assert fallback["expanded_source_context_bbox_xyxy"] == [130, 130, 170, 170]
    assert "context_candidate_detection_ids" not in fallback
    assert "context_candidate_bboxes_xyxy" not in fallback


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


class _FakeModelTextRegionClient:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.calls: list[dict] = []

    def analyze_image(self, image_path: str | Path, prompt: str, kind: str, max_completion_tokens: int) -> dict:
        self.calls.append(
            {
                "image_path": Path(image_path),
                "prompt": prompt,
                "kind": kind,
                "max_completion_tokens": max_completion_tokens,
            }
        )
        return {
            "raw_text": json.dumps(self.payload, ensure_ascii=False),
            "request": {"kind": kind},
            "response": {"status": "ok"},
        }


class _FakeComicTextBubbleDetector:
    def __init__(self, model_path, conf_threshold=0.5, classes=None):
        self.model_path = Path(model_path)
        self.conf_threshold = conf_threshold

    def detect_image(self, image_path: str | Path):
        return [
            ComicTextBubbleDetection(label="text_free", score=0.88, bbox_xyxy=(88, 82, 135, 150)),
            ComicTextBubbleDetection(label="bubble", score=0.99, bbox_xyxy=(20, 20, 210, 210)),
        ]


class _FakeDistantComicTextBubbleDetector:
    def __init__(self, model_path, conf_threshold=0.5, classes=None):
        self.model_path = Path(model_path)
        self.conf_threshold = conf_threshold

    def detect_image(self, image_path: str | Path):
        return [
            ComicTextBubbleDetection(label="text_free", score=0.74, bbox_xyxy=(220, 220, 260, 260)),
        ]


class _FakeBubbleOnlyComicTextBubbleDetector:
    def __init__(self, model_path, conf_threshold=0.5, classes=None):
        self.model_path = Path(model_path)
        self.conf_threshold = conf_threshold

    def detect_image(self, image_path: str | Path):
        return [
            ComicTextBubbleDetection(label="bubble", score=0.95, bbox_xyxy=(105, 105, 195, 195)),
        ]
