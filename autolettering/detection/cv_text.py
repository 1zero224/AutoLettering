from __future__ import annotations

from collections import deque
from dataclasses import asdict
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from autolettering.labelplus.models import ManifestLabel

from .models import CandidateBox, DetectionResult
from .regions import build_search_region


def detect_text_region(
    image_path: str | Path,
    label: ManifestLabel,
    image_width: int,
    image_height: int,
    radius_x: int = 220,
    radius_y: int = 180,
    dark_threshold: int = 190,
    min_area: int = 20,
    min_dark_pixels: int = 10,
) -> DetectionResult:
    search_region = build_search_region(label.x_px, label.y_px, image_width, image_height, radius_x, radius_y)
    dark_mask = _load_dark_mask(image_path, search_region, dark_threshold)
    if not bool(dark_mask.any()):
        return _failed_result(label.id, search_region, "no_dark_pixels")

    candidates = _connected_components(
        _build_component_mask(dark_mask),
        dark_mask,
        search_region,
        label.x_px,
        label.y_px,
        min_area=min_area,
        min_dark_pixels=min_dark_pixels,
    )

    if not candidates:
        return _failed_result(label.id, search_region, "no_candidate_box")

    return _success_result(label.id, search_region, candidates)


def _load_dark_mask(
    image_path: str | Path,
    search_region: tuple[int, int, int, int],
    dark_threshold: int,
) -> np.ndarray:
    with Image.open(image_path) as image:
        crop = image.convert("RGB").crop(search_region)
    return np.array(crop.convert("L")) < dark_threshold


def _build_component_mask(dark_mask: np.ndarray) -> np.ndarray:
    dilated = Image.fromarray((dark_mask.astype(np.uint8) * 255), mode="L").filter(ImageFilter.MaxFilter(9))
    return np.array(dilated) > 0


def _failed_result(record_id: str, search_region: tuple[int, int, int, int], reason: str) -> DetectionResult:
    return DetectionResult(
        record_id=record_id,
        status="failed",
        search_region_xyxy=search_region,
        candidate_boxes=[],
        selected_text_box_xyxy=None,
        confidence=0.0,
        failure_reason=reason,
    )


def _success_result(
    record_id: str,
    search_region: tuple[int, int, int, int],
    candidates: list[CandidateBox],
) -> DetectionResult:
    selected = max(candidates, key=lambda item: item.score)
    return DetectionResult(
        record_id=record_id,
        status="ok",
        search_region_xyxy=search_region,
        candidate_boxes=candidates,
        selected_text_box_xyxy=selected.xyxy,
        confidence=max(0.01, min(1.0, selected.score)),
        failure_reason=None,
    )


def draw_detection_debug(
    image_path: str | Path,
    label: ManifestLabel,
    result: DetectionResult,
    output_path: str | Path,
) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    with Image.open(image_path) as source:
        canvas = source.convert("RGB")

    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default()

    sx1, sy1, sx2, sy2 = result.search_region_xyxy
    draw.rectangle((sx1, sy1, sx2, sy2), outline=(240, 180, 20), width=4)
    _draw_cross(draw, label.x_px, label.y_px, (220, 30, 30), radius=12)

    for candidate in result.candidate_boxes:
        draw.rectangle(candidate.xyxy, outline=(30, 90, 220), width=3)

    if result.selected_text_box_xyxy:
        draw.rectangle(result.selected_text_box_xyxy, outline=(220, 30, 30), width=5)

    label_text = f"{label.record_index}:{result.status}"
    text_bbox = draw.textbbox((0, 0), label_text, font=font)
    text_w = text_bbox[2] - text_bbox[0]
    text_h = text_bbox[3] - text_bbox[1]
    tx = min(max(label.x_px + 16, 0), canvas.width - text_w - 6)
    ty = min(max(label.y_px - 18, 0), canvas.height - text_h - 6)
    draw.rectangle((tx - 3, ty - 3, tx + text_w + 3, ty + text_h + 3), fill=(255, 255, 255))
    draw.text((tx, ty), label_text, fill=(220, 30, 30), font=font)

    canvas.save(output)
    return output


def detection_result_to_dict(result: DetectionResult) -> dict:
    return {
        "record_id": result.record_id,
        "status": result.status,
        "search_region_xyxy": list(result.search_region_xyxy),
        "candidate_boxes": [
            {**asdict(candidate), "xyxy": list(candidate.xyxy)}
            for candidate in result.candidate_boxes
        ],
        "selected_text_box_xyxy": list(result.selected_text_box_xyxy)
        if result.selected_text_box_xyxy
        else None,
        "confidence": result.confidence,
        "failure_reason": result.failure_reason,
    }


def _connected_components(
    component_mask: np.ndarray,
    dark_mask: np.ndarray,
    search_region: tuple[int, int, int, int],
    label_x: int,
    label_y: int,
    min_area: int,
    min_dark_pixels: int,
) -> list[CandidateBox]:
    height, width = component_mask.shape
    visited = np.zeros_like(component_mask, dtype=bool)
    candidates: list[CandidateBox] = []
    sx1, sy1, sx2, sy2 = search_region
    diag = max(1.0, ((sx2 - sx1) ** 2 + (sy2 - sy1) ** 2) ** 0.5)

    for y in range(height):
        for x in range(width):
            if visited[y, x] or not component_mask[y, x]:
                continue
            min_x, min_y, max_x, max_y, area = _flood_fill(component_mask, visited, x, y)
            if area < min_area:
                continue

            dark_crop = dark_mask[min_y : max_y + 1, min_x : max_x + 1]
            dark_count = int(dark_crop.sum())
            if dark_count < min_dark_pixels:
                continue

            gx1 = sx1 + min_x
            gy1 = sy1 + min_y
            gx2 = sx1 + max_x + 1
            gy2 = sy1 + max_y + 1
            center_x = (gx1 + gx2) / 2
            center_y = (gy1 + gy2) / 2
            distance = ((center_x - label_x) ** 2 + (center_y - label_y) ** 2) ** 0.5
            distance_score = max(0.0, 1.0 - distance / diag)
            ink_score = min(1.0, dark_count / 400.0)
            score = 0.75 * distance_score + 0.25 * ink_score
            candidates.append(
                CandidateBox(
                    xyxy=(gx1, gy1, gx2, gy2),
                    area=area,
                    dark_pixel_count=dark_count,
                    center_distance=round(distance, 3),
                    score=round(score, 4),
                )
            )

    return sorted(candidates, key=lambda item: item.score, reverse=True)


def _flood_fill(mask: np.ndarray, visited: np.ndarray, start_x: int, start_y: int) -> tuple[int, int, int, int, int]:
    queue: deque[tuple[int, int]] = deque([(start_x, start_y)])
    visited[start_y, start_x] = True
    min_x = max_x = start_x
    min_y = max_y = start_y
    area = 0
    height, width = mask.shape

    while queue:
        x, y = queue.popleft()
        area += 1
        min_x = min(min_x, x)
        min_y = min(min_y, y)
        max_x = max(max_x, x)
        max_y = max(max_y, y)

        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if nx < 0 or ny < 0 or nx >= width or ny >= height:
                continue
            if visited[ny, nx] or not mask[ny, nx]:
                continue
            visited[ny, nx] = True
            queue.append((nx, ny))

    return min_x, min_y, max_x, max_y, area


def _draw_cross(draw: ImageDraw.ImageDraw, x: int, y: int, color: tuple[int, int, int], radius: int) -> None:
    draw.line((x - radius, y, x + radius, y), fill=color, width=3)
    draw.line((x, y - radius, x, y + radius), fill=color, width=3)
    draw.ellipse((x - radius // 2, y - radius // 2, x + radius // 2, y + radius // 2), outline=color, width=3)
