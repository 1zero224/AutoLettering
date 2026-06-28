import builtins
from pathlib import Path

import pytest
from PIL import Image

from autolettering.detection.comic_text_bubble import (
    ComicTextBubbleDetection,
    ComicTextBubbleDetector,
    select_comic_text_detection,
)


def test_rtdetrv2_detector_parses_labels_boxes_scores_from_onnx_session(tmp_path: Path):
    image_path = tmp_path / "page.png"
    Image.new("RGB", (200, 100), "white").save(image_path)
    session = _FakeRtdetrv2Session()

    detector = ComicTextBubbleDetector(
        model_path=tmp_path / "fake.onnx",
        conf_threshold=0.5,
        classes=["bubble", "text_bubble", "text_free"],
        session=session,
    )

    detections = detector.detect_image(image_path)

    assert session.input_shape == (1, 3, 640, 640)
    assert session.orig_target_sizes == [[200, 100]]
    assert detections == [
        ComicTextBubbleDetection(label="text_bubble", score=0.91, bbox_xyxy=(10, 20, 51, 81)),
        ComicTextBubbleDetection(label="text_free", score=0.72, bbox_xyxy=(120, 10, 180, 31)),
    ]


def test_rtdetrv2_detector_reports_missing_model_path(tmp_path: Path):
    with pytest.raises(FileNotFoundError, match="comic_detector_model_not_found"):
        ComicTextBubbleDetector(model_path=tmp_path / "missing.onnx")


def test_rtdetrv2_detector_reports_missing_onnxruntime(tmp_path: Path, monkeypatch):
    model_path = tmp_path / "detector.onnx"
    model_path.write_bytes(b"fake")
    original_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "onnxruntime":
            raise ImportError("missing onnxruntime")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    with pytest.raises(RuntimeError, match="comic_detector_requires_onnxruntime"):
        ComicTextBubbleDetector(model_path=model_path)


def test_rtdetrv2_detector_rejects_invalid_conf_threshold(tmp_path: Path):
    session = _FakeRtdetrv2Session()

    with pytest.raises(ValueError, match="comic_detector_conf_threshold"):
        ComicTextBubbleDetector(model_path=tmp_path / "fake.onnx", conf_threshold=float("nan"), session=session)

    with pytest.raises(ValueError, match="comic_detector_conf_threshold"):
        ComicTextBubbleDetector(model_path=tmp_path / "fake.onnx", conf_threshold=1.01, session=session)


def test_select_comic_text_detection_prefers_text_region_over_bubble():
    detections = [
        ComicTextBubbleDetection(label="bubble", score=0.99, bbox_xyxy=(0, 0, 120, 120)),
        ComicTextBubbleDetection(label="text_bubble", score=0.8, bbox_xyxy=(45, 30, 75, 80)),
        ComicTextBubbleDetection(label="text_free", score=0.7, bbox_xyxy=(170, 30, 210, 80)),
    ]

    match = select_comic_text_detection(detections, labelplus_point_xy=(60, 55), max_distance_px=40)

    assert match.status == "matched"
    assert match.selected_detection == detections[1]
    assert match.distance_px == 0.0
    assert match.top_candidates[0]["label"] == "text_bubble"
    assert match.top_candidates[0]["contains_labelplus_point"] is True


def test_select_comic_text_detection_reports_fallback_when_no_text_box_is_near():
    detections = [
        ComicTextBubbleDetection(label="bubble", score=0.99, bbox_xyxy=(0, 0, 120, 120)),
        ComicTextBubbleDetection(label="text_free", score=0.7, bbox_xyxy=(300, 300, 340, 340)),
    ]

    match = select_comic_text_detection(detections, labelplus_point_xy=(60, 55), max_distance_px=40)

    assert match.status == "fallback_required"
    assert match.selected_detection is None
    assert match.failure_reason == "no_comic_text_box_within_threshold"


def test_select_comic_text_detection_reports_no_text_box_for_bubble_only_detections():
    detections = [
        ComicTextBubbleDetection(label="bubble", score=0.99, bbox_xyxy=(0, 0, 120, 120)),
    ]

    match = select_comic_text_detection(detections, labelplus_point_xy=(60, 55), max_distance_px=40)

    assert match.status == "fallback_required"
    assert match.selected_detection is None
    assert match.failure_reason == "no_comic_text_box"
    assert match.top_candidates[0]["label"] == "bubble"


def test_select_comic_text_detection_rejects_invalid_max_distance():
    with pytest.raises(ValueError, match="comic_detector_max_distance"):
        select_comic_text_detection([], labelplus_point_xy=(60, 55), max_distance_px=float("nan"))

    with pytest.raises(ValueError, match="comic_detector_max_distance"):
        select_comic_text_detection([], labelplus_point_xy=(60, 55), max_distance_px=-1)


class _FakeRtdetrv2Session:
    def __init__(self) -> None:
        self.input_shape = None
        self.orig_target_sizes = None

    def get_inputs(self):
        return [
            _FakeIo("images", [1, 3, 640, 640]),
            _FakeIo("orig_target_sizes", [1, 2]),
        ]

    def run(self, output_names, inputs):
        self.input_shape = tuple(inputs["images"].shape)
        self.orig_target_sizes = inputs["orig_target_sizes"].tolist()
        return [
            [[1, 2, 0]],
            [[[10.2, 20.1, 50.8, 80.9], [120.4, 10.1, 180.2, 30.8], [0.0, 0.0, 200.0, 100.0]]],
            [[0.91, 0.72, 0.49]],
        ]


class _FakeIo:
    def __init__(self, name: str, shape: list[int]) -> None:
        self.name = name
        self.shape = shape
