from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import os
from pathlib import Path
import sys

import numpy as np
from PIL import Image

from autolettering.labelplus.models import ManifestLabel


@dataclass(frozen=True)
class CtdMaskComponent:
    component_id: str
    bbox_xyxy: tuple[int, int, int, int]
    area_px: int
    centroid_xy: tuple[float, float]
    mask_path: Path


@dataclass(frozen=True)
class CtdMaskMatch:
    record_id: str
    status: str
    component_id: str | None
    bbox_xyxy: tuple[int, int, int, int] | None
    mask_path: Path | None
    distance_px: float | None
    failure_reason: str | None


def split_mask_components(
    mask_path: str | Path,
    output_dir: str | Path | None = None,
    min_area: int = 50,
) -> list[CtdMaskComponent]:
    path = Path(mask_path)
    root = Path(output_dir) if output_dir else path.parent / f"{path.stem}-components"
    root.mkdir(parents=True, exist_ok=True)
    with Image.open(path) as image:
        binary = np.array(image.convert("L"), dtype=np.uint8) > 0

    visited = np.zeros_like(binary, dtype=bool)
    components: list[CtdMaskComponent] = []
    for start_y, start_x in zip(*np.where(binary & ~visited)):
        pixels = _component_pixels(binary, visited, int(start_x), int(start_y))
        if len(pixels) < min_area:
            continue
        component_id = f"component-{len(components) + 1:04d}"
        component = _component_record(component_id, pixels, binary.shape, root)
        components.append(component)
    return sorted(components, key=lambda item: (item.bbox_xyxy[1], item.bbox_xyxy[0]))


def detect_ctd_mask_components_for_image(
    image_path: str | Path,
    output_dir: str | Path,
    ballonstranslator_root: str | Path = "BallonsTranslator",
    min_area: int = 50,
) -> list[CtdMaskComponent]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    mask = _run_ballonstranslator_ctd(image_path, ballonstranslator_root)
    mask_path = output / "ctd-refined-mask.png"
    Image.fromarray(mask.astype(np.uint8), mode="L").save(mask_path)
    return split_mask_components(mask_path, output / "components", min_area=min_area)


def assign_labelplus_points_to_ctd_masks(
    labels: list[ManifestLabel],
    components: list[CtdMaskComponent],
    max_edge_distance_px: float = 12.0,
) -> dict[str, CtdMaskMatch]:
    claims: set[str] = set()
    matches: dict[str, CtdMaskMatch] = {}
    for label in labels:
        candidate = _nearest_component(label, components)
        if candidate is None or candidate[1] > max_edge_distance_px:
            matches[label.id] = _fallback(label.id, "no_ctd_mask_within_threshold")
            continue
        component, distance = candidate
        group = _vertical_component_group(component, components)
        member_ids = {item.component_id for item in group}
        if claims & member_ids:
            matches[label.id] = _fallback(label.id, "component_already_claimed")
            continue
        merged = _merged_component(group)
        claims.update(member_ids)
        matches[label.id] = CtdMaskMatch(
            record_id=label.id,
            status="matched",
            component_id=merged.component_id,
            bbox_xyxy=merged.bbox_xyxy,
            mask_path=merged.mask_path,
            distance_px=round(distance, 3),
            failure_reason=None,
        )
    return matches


def _component_record(
    component_id: str,
    pixels: list[tuple[int, int]],
    shape: tuple[int, int],
    output_dir: Path,
) -> CtdMaskComponent:
    ys, xs = zip(*pixels)
    x1, y1 = min(xs), min(ys)
    x2, y2 = max(xs) + 1, max(ys) + 1
    mask = np.zeros(shape, dtype=np.uint8)
    mask[np.array(ys), np.array(xs)] = 255
    mask_path = output_dir / f"{component_id}.png"
    Image.fromarray(mask, mode="L").save(mask_path)
    return CtdMaskComponent(
        component_id=component_id,
        bbox_xyxy=(x1, y1, x2, y2),
        area_px=len(pixels),
        centroid_xy=(round(float(np.mean(xs)), 3), round(float(np.mean(ys)), 3)),
        mask_path=mask_path,
    )


def _nearest_component(
    label: ManifestLabel,
    components: list[CtdMaskComponent],
) -> tuple[CtdMaskComponent, float] | None:
    if not components:
        return None
    scored = [(component, _point_to_rect_edge_distance(label.x_px, label.y_px, component.bbox_xyxy)) for component in components]
    return min(scored, key=lambda item: item[1])


def _vertical_component_group(
    seed: CtdMaskComponent,
    components: list[CtdMaskComponent],
) -> list[CtdMaskComponent]:
    group = [seed]
    previous_len = -1
    while previous_len != len(group):
        previous_len = len(group)
        cluster_bbox = _union_bbox([item.bbox_xyxy for item in group])
        for component in sorted(components, key=lambda item: (item.bbox_xyxy[1], item.bbox_xyxy[0])):
            if component in group:
                continue
            if _is_vertical_continuation(component.bbox_xyxy, cluster_bbox, seed.bbox_xyxy):
                group.append(component)
    return sorted(group, key=lambda item: (item.bbox_xyxy[1], item.bbox_xyxy[0]))


def _is_vertical_continuation(
    bbox: tuple[int, int, int, int],
    cluster: tuple[int, int, int, int],
    seed: tuple[int, int, int, int],
) -> bool:
    if bbox[1] < seed[1]:
        return False
    seed_width = _width(seed)
    if _width(bbox) > max(seed_width * 1.35, seed_width + 20):
        return False
    if _horizontal_overlap_ratio(bbox, cluster) < 0.72:
        return False
    gap = _vertical_gap(bbox, cluster)
    return gap <= max(10, int(round(_height(seed) * 0.08)))


def _merged_component(group: list[CtdMaskComponent]) -> CtdMaskComponent:
    if len(group) == 1:
        return group[0]
    bbox = _union_bbox([item.bbox_xyxy for item in group])
    component_id = "+".join(item.component_id for item in group)
    mask_path = _write_merged_mask(group, component_id)
    total_area = sum(item.area_px for item in group)
    centroid_x = sum(item.centroid_xy[0] * item.area_px for item in group) / max(1, total_area)
    centroid_y = sum(item.centroid_xy[1] * item.area_px for item in group) / max(1, total_area)
    return CtdMaskComponent(
        component_id=component_id,
        bbox_xyxy=bbox,
        area_px=total_area,
        centroid_xy=(round(float(centroid_x), 3), round(float(centroid_y), 3)),
        mask_path=mask_path,
    )


def _write_merged_mask(group: list[CtdMaskComponent], component_id: str) -> Path:
    arrays: list[np.ndarray] = []
    for component in group:
        with Image.open(component.mask_path) as image:
            arrays.append(np.array(image.convert("L"), dtype=np.uint8))
    merged = np.maximum.reduce(arrays)
    output = group[0].mask_path.parent / f"{component_id}.png"
    Image.fromarray(merged, mode="L").save(output)
    return output


def _point_to_rect_edge_distance(x: int, y: int, bbox: tuple[int, int, int, int]) -> float:
    x1, y1, x2, y2 = bbox
    if x1 <= x <= x2 and y1 <= y <= y2:
        return 0.0
    dx = max(x1 - x, 0, x - x2)
    dy = max(y1 - y, 0, y - y2)
    return float((dx * dx + dy * dy) ** 0.5)


def _union_bbox(bboxes: list[tuple[int, int, int, int]]) -> tuple[int, int, int, int]:
    return (
        min(bbox[0] for bbox in bboxes),
        min(bbox[1] for bbox in bboxes),
        max(bbox[2] for bbox in bboxes),
        max(bbox[3] for bbox in bboxes),
    )


def _width(bbox: tuple[int, int, int, int]) -> int:
    return max(0, bbox[2] - bbox[0])


def _height(bbox: tuple[int, int, int, int]) -> int:
    return max(0, bbox[3] - bbox[1])


def _vertical_gap(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> int:
    overlap = min(a[3], b[3]) - max(a[1], b[1])
    if overlap > 0:
        return 0
    return max(0, max(a[1], b[1]) - min(a[3], b[3]))


def _horizontal_overlap_ratio(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
    overlap = min(a[2], b[2]) - max(a[0], b[0])
    if overlap <= 0:
        return 0.0
    return overlap / max(1, min(_width(a), _width(b)))


def _fallback(record_id: str, reason: str) -> CtdMaskMatch:
    return CtdMaskMatch(
        record_id=record_id,
        status="fallback_required",
        component_id=None,
        bbox_xyxy=None,
        mask_path=None,
        distance_px=None,
        failure_reason=reason,
    )


def _component_pixels(binary: np.ndarray, visited: np.ndarray, start_x: int, start_y: int) -> list[tuple[int, int]]:
    queue: deque[tuple[int, int]] = deque([(start_x, start_y)])
    visited[start_y, start_x] = True
    pixels: list[tuple[int, int]] = []
    height, width = binary.shape
    while queue:
        x, y = queue.popleft()
        pixels.append((y, x))
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if nx < 0 or ny < 0 or nx >= width or ny >= height:
                continue
            if visited[ny, nx] or not binary[ny, nx]:
                continue
            visited[ny, nx] = True
            queue.append((nx, ny))
    return pixels


def _run_ballonstranslator_ctd(image_path: str | Path, ballonstranslator_root: str | Path) -> np.ndarray:
    import cv2

    root = Path(ballonstranslator_root).resolve()
    if not root.exists():
        raise FileNotFoundError(f"BallonsTranslator root not found: {root}")
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    payload = np.fromfile(str(image_path), dtype=np.uint8)
    image = cv2.imdecode(payload, cv2.IMREAD_COLOR)
    if image is None:
        raise RuntimeError(f"cannot_read_image:{image_path}")

    cwd = Path.cwd()
    os.chdir(root)
    try:
        from ballontranslator.modules.textdetector.detector_ctd import ComicTextDetector

        detector = ComicTextDetector()
        detector.updateParam("device", "cpu")
        detector.updateParam("detect_size", 1024)
        detector.updateParam("det_rearrange_max_batches", 4)
        detector.updateParam("mask dilate size", 2)
        mask, _blocks = detector.detect(image, None)
    finally:
        os.chdir(cwd)
    return mask
