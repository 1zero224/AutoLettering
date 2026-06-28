from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image


COMIC_TEXT_BUBBLE_CLASSES = ["bubble", "text_bubble", "text_free"]
COMIC_TEXT_LABELS = {"text_bubble", "text_free"}
DEFAULT_COMIC_DETECTOR_MODEL_PATH = Path("comic-text-and-bubble-detector") / "detector_int8.onnx"


@dataclass(frozen=True)
class ComicTextBubbleDetection:
    label: str
    score: float
    bbox_xyxy: tuple[int, int, int, int]


@dataclass(frozen=True)
class ComicTextBubbleMatch:
    status: str
    selected_detection: ComicTextBubbleDetection | None
    distance_px: float | None
    failure_reason: str | None
    top_candidates: list[dict]


class ComicTextBubbleDetector:
    def __init__(
        self,
        model_path: str | Path = DEFAULT_COMIC_DETECTOR_MODEL_PATH,
        conf_threshold: float = 0.5,
        classes: list[str] | None = None,
        session: Any | None = None,
        input_size: tuple[int, int] | None = None,
    ) -> None:
        self.model_path = Path(model_path)
        self.conf_threshold = _validate_conf_threshold(conf_threshold)
        self.classes = classes or COMIC_TEXT_BUBBLE_CLASSES
        self.session = session or _create_session(self.model_path)
        self.image_input_name = self.session.get_inputs()[0].name
        self.size_input_name = self.session.get_inputs()[1].name
        self.input_size = input_size or _input_size_from_session(self.session) or (640, 640)

    @classmethod
    def from_model_dir(
        cls,
        model_dir: str | Path = "comic-text-and-bubble-detector",
        model_name: str = DEFAULT_COMIC_DETECTOR_MODEL_PATH.name,
        conf_threshold: float = 0.5,
    ) -> ComicTextBubbleDetector:
        return cls(Path(model_dir) / model_name, conf_threshold=conf_threshold)

    def detect_image(self, image_path: str | Path) -> list[ComicTextBubbleDetection]:
        image_array, original_size = _load_rgb_array(image_path)
        inputs = self._preprocess(image_array, original_size)
        outputs = self.session.run(None, inputs)
        return self._postprocess(outputs, original_size)

    def _preprocess(self, image: np.ndarray, original_size: tuple[int, int]) -> dict:
        input_h, input_w = self.input_size
        resized = Image.fromarray(image).resize((input_w, input_h), Image.Resampling.BILINEAR)
        tensor = np.asarray(resized, dtype=np.float32).transpose((2, 0, 1))
        tensor = np.ascontiguousarray(tensor / 255.0)[None, :, :, :]
        width, height = original_size
        return {
            self.image_input_name: tensor,
            self.size_input_name: np.array([[width, height]], dtype=np.int64),
        }

    def _postprocess(
        self,
        outputs: list[np.ndarray] | tuple[np.ndarray, ...],
        original_size: tuple[int, int],
    ) -> list[ComicTextBubbleDetection]:
        labels = _first_batch(np.asarray(outputs[0]))
        boxes = _first_batch(np.asarray(outputs[1]))
        scores = _first_batch(np.asarray(outputs[2]))
        width, height = original_size
        detections: list[ComicTextBubbleDetection] = []
        for label_idx, box, score in zip(labels, boxes, scores):
            score_value = float(score)
            if score_value < self.conf_threshold:
                continue
            class_index = int(label_idx)
            if class_index < 0 or class_index >= len(self.classes):
                continue
            bbox = _clamp_bbox([int(round(value)) for value in box.tolist()], width, height)
            if bbox is None:
                continue
            detections.append(
                ComicTextBubbleDetection(
                    label=self.classes[class_index],
                    score=round(score_value, 4),
                    bbox_xyxy=bbox,
                )
            )
        return detections


def select_comic_text_detection(
    detections: list[ComicTextBubbleDetection],
    labelplus_point_xy: tuple[int, int],
    max_distance_px: float = 120.0,
) -> ComicTextBubbleMatch:
    max_distance = _validate_max_distance_px(max_distance_px)
    candidates = [_candidate_payload(detection, labelplus_point_xy) for detection in detections]
    candidates = sorted(candidates, key=lambda item: (item["distance_px"], item["label_priority"], -item["score"]))
    text_candidates = [item for item in candidates if item["label"] in COMIC_TEXT_LABELS]
    if not text_candidates:
        return ComicTextBubbleMatch(
            status="fallback_required",
            selected_detection=None,
            distance_px=None,
            failure_reason="no_comic_text_box",
            top_candidates=candidates,
        )
    selected = text_candidates[0]
    if selected["distance_px"] > max_distance:
        return ComicTextBubbleMatch(
            status="fallback_required",
            selected_detection=None,
            distance_px=selected["distance_px"],
            failure_reason="no_comic_text_box_within_threshold",
            top_candidates=candidates,
        )
    return ComicTextBubbleMatch(
        status="matched",
        selected_detection=selected["detection"],
        distance_px=selected["distance_px"],
        failure_reason=None,
        top_candidates=candidates,
    )


def detections_payload(detections: list[ComicTextBubbleDetection]) -> list[dict]:
    return [
        {
            "label": detection.label,
            "score": detection.score,
            "bbox_xyxy": list(detection.bbox_xyxy),
        }
        for detection in detections
    ]


def match_payload(match: ComicTextBubbleMatch, threshold_px: float) -> dict:
    selected = match.selected_detection
    return {
        "schema_version": "autolettering.comic_text_bubble_rtdetrv2_match.v1",
        "status": match.status,
        "failure_reason": match.failure_reason,
        "selected_label": selected.label if selected else None,
        "selected_score": selected.score if selected else None,
        "selected_bbox_xyxy": list(selected.bbox_xyxy) if selected else None,
        "distance_px": match.distance_px,
        "threshold_px": threshold_px,
        "top_candidates": [_public_candidate_payload(candidate) for candidate in match.top_candidates[:12]],
    }


def _create_session(model_path: Path):
    if not model_path.exists():
        raise FileNotFoundError(f"comic_detector_model_not_found:{model_path}")
    try:
        import onnxruntime as ort
    except ImportError as exc:
        raise RuntimeError("comic_detector_requires_onnxruntime") from exc
    return ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])


def _validate_conf_threshold(value: float) -> float:
    threshold = float(value)
    if not math.isfinite(threshold) or threshold < 0.0 or threshold > 1.0:
        raise ValueError("comic_detector_conf_threshold_must_be_finite_between_0_and_1")
    return threshold


def _validate_max_distance_px(value: float) -> float:
    distance = float(value)
    if not math.isfinite(distance) or distance < 0.0:
        raise ValueError("comic_detector_max_distance_px_must_be_finite_nonnegative")
    return distance


def _input_size_from_session(session: Any) -> tuple[int, int] | None:
    shape = session.get_inputs()[0].shape
    if len(shape) < 4:
        return None
    height, width = shape[-2], shape[-1]
    if isinstance(height, int) and isinstance(width, int):
        return height, width
    return None


def _load_rgb_array(image_path: str | Path) -> tuple[np.ndarray, tuple[int, int]]:
    with Image.open(image_path) as image:
        rgb = image.convert("RGB")
        return np.asarray(rgb), rgb.size


def _first_batch(value: np.ndarray) -> np.ndarray:
    if value.ndim >= 2:
        return value[0]
    return value


def _clamp_bbox(values: list[int], width: int, height: int) -> tuple[int, int, int, int] | None:
    if len(values) != 4:
        return None
    x1, y1, x2, y2 = values
    x1 = max(0, min(width - 1, x1))
    y1 = max(0, min(height - 1, y1))
    x2 = max(1, min(width, x2))
    y2 = max(1, min(height, y2))
    if x2 <= x1 or y2 <= y1:
        return None
    return x1, y1, x2, y2


def _candidate_payload(detection: ComicTextBubbleDetection, point_xy: tuple[int, int]) -> dict:
    distance = round(_point_to_bbox_distance(point_xy, detection.bbox_xyxy), 3)
    return {
        "detection": detection,
        "label": detection.label,
        "score": detection.score,
        "bbox_xyxy": list(detection.bbox_xyxy),
        "distance_px": distance,
        "contains_labelplus_point": distance == 0.0,
        "label_priority": 0 if detection.label in COMIC_TEXT_LABELS else 1,
    }


def _public_candidate_payload(candidate: dict) -> dict:
    return {
        "label": candidate["label"],
        "score": candidate["score"],
        "bbox_xyxy": candidate["bbox_xyxy"],
        "distance_px": candidate["distance_px"],
        "contains_labelplus_point": candidate["contains_labelplus_point"],
    }


def _point_to_bbox_distance(point_xy: tuple[int, int], bbox: tuple[int, int, int, int]) -> float:
    x, y = point_xy
    x1, y1, x2, y2 = bbox
    dx = max(x1 - x, x - x2, 0)
    dy = max(y1 - y, y - y2, 0)
    return float((dx * dx + dy * dy) ** 0.5)
