from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from math import atan2, degrees

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps


@dataclass(frozen=True)
class OrientationEstimate:
    status: str
    detected_orientation: str | None
    principal_axis_degrees: float | None
    estimated_angle_degrees: float | None
    candidate_angles: list[float]
    selected_angle_degrees: float | None
    confidence: float
    bbox: tuple[int, int, int, int]
    tight_bbox: tuple[int, int, int, int] | None
    dark_pixel_count: int
    failure_reason: str | None = None


def estimate_orientation_angle(
    image_path: str | Path,
    bbox: tuple[int, int, int, int],
    dark_threshold: int = 205,
    min_dark_pixels: int = 12,
) -> OrientationEstimate:
    mask = _load_dark_mask(image_path, bbox, dark_threshold)
    dark_count = int(mask.sum())
    if dark_count < min_dark_pixels:
        return _failed_estimate(bbox, dark_count, "insufficient_dark_pixels")

    coords = _mask_xy(mask)
    axis_angle, eigenvalues = _principal_axis(coords)
    tight_bbox = _tight_bbox(coords, bbox)
    orientation = _detect_orientation(tight_bbox, axis_angle)
    estimated_angle = _relative_angle(axis_angle, orientation)
    candidate_angles = _candidate_angles(estimated_angle)

    return OrientationEstimate(
        status="ok",
        detected_orientation=orientation,
        principal_axis_degrees=round(axis_angle, 1),
        estimated_angle_degrees=estimated_angle,
        candidate_angles=candidate_angles,
        selected_angle_degrees=estimated_angle,
        confidence=_confidence(eigenvalues, dark_count, mask.size),
        bbox=bbox,
        tight_bbox=tight_bbox,
        dark_pixel_count=dark_count,
    )


def draw_angle_debug_grid(
    image_path: str | Path,
    bbox: tuple[int, int, int, int],
    estimate: OrientationEstimate,
    output_path: str | Path,
) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(image_path) as image:
        crop = image.convert("RGB").crop(bbox)

    tiles = _debug_tiles(crop, estimate)
    canvas = Image.new("RGB", (180 * len(tiles), 190), "white")
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default()
    for index, (label, tile) in enumerate(tiles):
        thumb = ImageOps.contain(tile, (160, 150))
        x = index * 180 + 10
        canvas.paste(thumb, (x, 30))
        draw.text((x, 10), label, fill=(0, 0, 0), font=font)
    canvas.save(output)
    return output


def orientation_estimate_to_dict(estimate: OrientationEstimate) -> dict:
    return {
        "status": estimate.status,
        "detected_orientation": estimate.detected_orientation,
        "principal_axis_degrees": estimate.principal_axis_degrees,
        "estimated_angle_degrees": estimate.estimated_angle_degrees,
        "candidate_angles": estimate.candidate_angles,
        "selected_angle_degrees": estimate.selected_angle_degrees,
        "confidence": estimate.confidence,
        "bbox": list(estimate.bbox),
        "tight_bbox": list(estimate.tight_bbox) if estimate.tight_bbox else None,
        "dark_pixel_count": estimate.dark_pixel_count,
        "failure_reason": estimate.failure_reason,
    }


def _load_dark_mask(image_path: str | Path, bbox: tuple[int, int, int, int], threshold: int) -> np.ndarray:
    with Image.open(image_path) as image:
        crop = image.convert("L").crop(bbox)
    return np.array(crop) < threshold


def _failed_estimate(bbox: tuple[int, int, int, int], dark_count: int, reason: str) -> OrientationEstimate:
    return OrientationEstimate(
        status="failed",
        detected_orientation=None,
        principal_axis_degrees=None,
        estimated_angle_degrees=None,
        candidate_angles=[],
        selected_angle_degrees=None,
        confidence=0.0,
        bbox=bbox,
        tight_bbox=None,
        dark_pixel_count=dark_count,
        failure_reason=reason,
    )


def _mask_xy(mask: np.ndarray) -> np.ndarray:
    ys, xs = np.nonzero(mask)
    return np.column_stack((xs.astype(float), ys.astype(float)))


def _principal_axis(coords: np.ndarray) -> tuple[float, tuple[float, float]]:
    centered = coords - coords.mean(axis=0)
    covariance = np.cov(centered, rowvar=False)
    eigenvalues, eigenvectors = np.linalg.eigh(covariance)
    order = np.argsort(eigenvalues)
    vector = eigenvectors[:, order[-1]]
    if vector[0] < 0:
        vector = -vector
    angle = degrees(atan2(float(vector[1]), float(vector[0])))
    return _normalize_axis_angle(angle), (float(eigenvalues[order[-1]]), float(eigenvalues[order[0]]))


def _tight_bbox(coords: np.ndarray, bbox: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    x1, y1, _, _ = bbox
    min_x, min_y = coords.min(axis=0)
    max_x, max_y = coords.max(axis=0)
    return x1 + int(min_x), y1 + int(min_y), x1 + int(max_x) + 1, y1 + int(max_y) + 1


def _detect_orientation(tight_bbox: tuple[int, int, int, int], axis_angle: float) -> str:
    x1, y1, x2, y2 = tight_bbox
    width = max(1, x2 - x1)
    height = max(1, y2 - y1)
    if height >= width * 1.25:
        return "vertical"
    if width >= height * 1.25:
        return "horizontal"
    return "vertical" if abs(axis_angle) > 45 else "horizontal"


def _relative_angle(axis_angle: float, orientation: str) -> float:
    if orientation == "horizontal":
        return round(_clamp(axis_angle, -45.0, 45.0), 1)
    relative = axis_angle - 90 if axis_angle >= 0 else axis_angle + 90
    return round(_clamp(relative, -45.0, 45.0), 1)


def _candidate_angles(selected_angle: float) -> list[float]:
    values = [round(_clamp(selected_angle + offset, -45.0, 45.0), 1) for offset in (-10, -5, 0, 5, 10)]
    return list(dict.fromkeys(values))


def _confidence(eigenvalues: tuple[float, float], dark_count: int, area: int) -> float:
    major, minor = eigenvalues
    anisotropy = 0.0 if major <= 0 else max(0.0, min(1.0, (major - minor) / major))
    ink_ratio = min(1.0, dark_count / max(1, area) * 8)
    return round(0.15 + 0.65 * anisotropy + 0.2 * ink_ratio, 3)


def _debug_tiles(crop: Image.Image, estimate: OrientationEstimate) -> list[tuple[str, Image.Image]]:
    if estimate.status != "ok":
        return [(f"source:{estimate.failure_reason}", crop)]
    tiles = [("source", crop)]
    for angle in estimate.candidate_angles:
        tiles.append((f"angle {angle:+.1f}", crop.rotate(-angle, expand=True, fillcolor="white")))
    return tiles


def _normalize_axis_angle(angle: float) -> float:
    while angle <= -90:
        angle += 180
    while angle > 90:
        angle -= 180
    return angle


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
