from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import json
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
    edge_pixels_xy: tuple[tuple[int, int], ...] | None = None
    edge_segments_xyxy: tuple[tuple[int, int, int, int], ...] | None = None


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
    matches: dict[str, CtdMaskMatch] = {label.id: _fallback(label.id, "no_ctd_mask_within_threshold") for label in labels}
    if not labels or not components:
        return matches

    candidates: list[tuple[float, ManifestLabel, CtdMaskComponent]] = []
    for label in labels:
        for component in components:
            distance = _point_to_component_edge_distance(label.x_px, label.y_px, component)
            if distance <= max_edge_distance_px:
                candidates.append((distance, label, component))

    claims: set[str] = set()
    matched_labels: set[str] = set()
    for distance, label, component in sorted(candidates, key=lambda item: (item[0], item[1].id, item[2].component_id)):
        if label.id in matched_labels:
            continue
        group = _vertical_component_group(component, components, label)
        member_ids = {item.component_id for item in group}
        if claims & member_ids:
            continue
        merged = _merged_component(group)
        claims.update(member_ids)
        matched_labels.add(label.id)
        matches[label.id] = CtdMaskMatch(
            record_id=label.id,
            status="matched",
            component_id=merged.component_id,
            bbox_xyxy=merged.bbox_xyxy,
            mask_path=merged.mask_path,
            distance_px=round(distance, 3),
            failure_reason=None,
        )

    close_claimed_labels = {
        label.id
        for distance, label, component in candidates
        if label.id not in matched_labels and component.component_id in claims
    }
    for record_id in close_claimed_labels:
        matches[record_id] = _fallback(record_id, "component_already_claimed")
    return matches


def labelplus_ctd_mask_distance_rows(
    labels: list[ManifestLabel],
    components: list[CtdMaskComponent],
    max_edge_distance_px: float = 12.0,
) -> list[dict]:
    rows: list[dict] = []
    for label in labels:
        for component in components:
            distance = _point_to_component_edge_distance(label.x_px, label.y_px, component)
            rows.append(
                {
                    "record_id": label.id,
                    "labelplus_point_xy": [label.x_px, label.y_px],
                    "component_id": component.component_id,
                    "component_bbox_xyxy": list(component.bbox_xyxy),
                    "component_mask_path": str(component.mask_path),
                    "edge_distance_px": round(distance, 3),
                    "within_threshold": distance <= max_edge_distance_px,
                    "threshold_px": max_edge_distance_px,
                }
            )
    return sorted(rows, key=lambda item: (item["record_id"], item["edge_distance_px"], item["component_id"]))


def ctd_mask_component_rows(components: list[CtdMaskComponent]) -> list[dict]:
    return [
        {
            "component_id": component.component_id,
            "bbox_xyxy": list(component.bbox_xyxy),
            "area_px": component.area_px,
            "centroid_xy": list(component.centroid_xy),
            "mask_path": str(component.mask_path),
        }
        for component in components
    ]


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
    edge_pixels = _edge_pixels(mask)
    edge_segments = _edge_segments(mask)
    return CtdMaskComponent(
        component_id=component_id,
        bbox_xyxy=(x1, y1, x2, y2),
        area_px=len(pixels),
        centroid_xy=(round(float(np.mean(xs)), 3), round(float(np.mean(ys)), 3)),
        mask_path=mask_path,
        edge_pixels_xy=edge_pixels,
        edge_segments_xyxy=edge_segments,
    )


def _vertical_component_group(
    seed: CtdMaskComponent,
    components: list[CtdMaskComponent],
    label: ManifestLabel | None = None,
) -> list[CtdMaskComponent]:
    group = [seed]
    previous_len = -1
    while previous_len != len(group):
        previous_len = len(group)
        cluster_bbox = _union_bbox([item.bbox_xyxy for item in group])
        for component in sorted(components, key=lambda item: (item.bbox_xyxy[1], item.bbox_xyxy[0])):
            if component in group:
                continue
            if _is_vertical_continuation(component.bbox_xyxy, cluster_bbox, seed.bbox_xyxy) or _is_bubble_adjacent_vertical_column(
                component.bbox_xyxy,
                cluster_bbox,
                seed.bbox_xyxy,
                label,
            ):
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
    if _horizontal_overlap_ratio(bbox, cluster) < 0.72:
        return False
    gap = _vertical_gap(bbox, cluster)
    width_limit = max(seed_width * 1.35, seed_width + 20)
    if gap <= max(10, int(round(_height(seed) * 0.08))):
        return _width(bbox) <= width_limit or _is_tall_promo_column_continuation(bbox, cluster, seed, gap)
    if _width(bbox) > width_limit and not _is_tall_promo_column_continuation(bbox, cluster, seed, gap):
        return False
    return _is_tall_promo_column_continuation(bbox, cluster, seed, gap)


def _is_tall_promo_column_continuation(
    bbox: tuple[int, int, int, int],
    cluster: tuple[int, int, int, int],
    seed: tuple[int, int, int, int],
    gap: int,
) -> bool:
    if _height(cluster) < max(_width(cluster) * 4, _height(seed) * 4):
        return False
    if _height(bbox) < _width(bbox) * 0.45:
        return False
    if _width(bbox) > max(_width(cluster) * 1.25, _width(seed) * 1.6):
        return False
    if _horizontal_center_delta_ratio(bbox, cluster) > 0.36:
        return False
    return gap <= max(90, int(round(_height(cluster) * 0.18)))


def _is_bubble_adjacent_vertical_column(
    bbox: tuple[int, int, int, int],
    cluster: tuple[int, int, int, int],
    seed: tuple[int, int, int, int],
    label: ManifestLabel | None,
) -> bool:
    if label is None or label.group_name != "框内":
        return False
    seed_width = _width(seed)
    if _width(bbox) > max(seed_width * 1.25, seed_width + 16):
        return False
    if _height(bbox) > max(_height(seed) * 1.25, _height(seed) + 36):
        return False
    vertical_gap = _vertical_gap(bbox, cluster)
    if _horizontal_overlap_ratio(bbox, cluster) >= 0.55:
        return vertical_gap <= max(10, int(round(_height(seed) * 0.08)))
    if _vertical_overlap_ratio(bbox, cluster) < 0.35:
        return False
    horizontal_gap = _horizontal_gap(bbox, cluster)
    return horizontal_gap <= max(12, int(round(seed_width * 0.35))) and vertical_gap == 0


def _merged_component(group: list[CtdMaskComponent]) -> CtdMaskComponent:
    if len(group) == 1:
        return group[0]
    bbox = _union_bbox([item.bbox_xyxy for item in group])
    component_id = "+".join(item.component_id for item in group)
    mask_path, merged_mask = _write_merged_mask(group, component_id)
    total_area = sum(item.area_px for item in group)
    centroid_x = sum(item.centroid_xy[0] * item.area_px for item in group) / max(1, total_area)
    centroid_y = sum(item.centroid_xy[1] * item.area_px for item in group) / max(1, total_area)
    return CtdMaskComponent(
        component_id=component_id,
        bbox_xyxy=bbox,
        area_px=total_area,
        centroid_xy=(round(float(centroid_x), 3), round(float(centroid_y), 3)),
        mask_path=mask_path,
        edge_pixels_xy=_edge_pixels(merged_mask),
        edge_segments_xyxy=_edge_segments(merged_mask),
    )


def _write_merged_mask(group: list[CtdMaskComponent], component_id: str) -> tuple[Path, np.ndarray]:
    arrays: list[np.ndarray] = []
    for component in group:
        with Image.open(component.mask_path) as image:
            arrays.append(np.array(image.convert("L"), dtype=np.uint8))
    merged = np.maximum.reduce(arrays)
    output = group[0].mask_path.parent / f"{component_id}.png"
    Image.fromarray(merged, mode="L").save(output)
    return output, merged


def _point_to_rect_edge_distance(x: int, y: int, bbox: tuple[int, int, int, int]) -> float:
    x1, y1, x2, y2 = bbox
    if x1 <= x <= x2 and y1 <= y <= y2:
        return float(min(x - x1, x2 - x, y - y1, y2 - y))
    dx = max(x1 - x, 0, x - x2)
    dy = max(y1 - y, 0, y - y2)
    return float((dx * dx + dy * dy) ** 0.5)


def _point_to_component_edge_distance(x: int, y: int, component: CtdMaskComponent) -> float:
    edge_segments = component.edge_segments_xyxy
    if edge_segments is None:
        edge_segments = _load_edge_segments(component.mask_path)
    if edge_segments is None:
        return _point_to_rect_edge_distance(x, y, component.bbox_xyxy)
    if not edge_segments:
        return _point_to_rect_region_distance(x, y, component.bbox_xyxy)
    return _point_to_segments_distance(x, y, edge_segments)


def _point_to_rect_region_distance(x: int, y: int, bbox: tuple[int, int, int, int]) -> float:
    x1, y1, x2, y2 = bbox
    if x1 <= x <= x2 and y1 <= y <= y2:
        return 0.0
    dx = max(x1 - x, 0, x - x2)
    dy = max(y1 - y, 0, y - y2)
    return float((dx * dx + dy * dy) ** 0.5)


def _load_edge_segments(mask_path: Path) -> tuple[tuple[int, int, int, int], ...] | None:
    try:
        with Image.open(mask_path) as image:
            mask = np.array(image.convert("L"), dtype=np.uint8)
    except (FileNotFoundError, OSError):
        return None
    return _edge_segments(mask)


def _point_to_segments_distance(
    x: int,
    y: int,
    segments: tuple[tuple[int, int, int, int], ...],
) -> float:
    data = np.array(segments, dtype=np.float64)
    x1 = data[:, 0]
    y1 = data[:, 1]
    x2 = data[:, 2]
    y2 = data[:, 3]
    vx = x2 - x1
    vy = y2 - y1
    length_sq = np.maximum(vx * vx + vy * vy, 1.0)
    t = np.clip(((float(x) - x1) * vx + (float(y) - y1) * vy) / length_sq, 0.0, 1.0)
    proj_x = x1 + t * vx
    proj_y = y1 + t * vy
    squared = (proj_x - float(x)) ** 2 + (proj_y - float(y)) ** 2
    return float(np.sqrt(float(squared.min())))


def _edge_pixels(mask: np.ndarray) -> tuple[tuple[int, int], ...]:
    binary = mask > 0
    if not bool(binary.any()):
        return ()
    edge = binary & ~_erode_8(binary)
    ys, xs = np.where(edge)
    return tuple((int(x), int(y)) for y, x in zip(ys, xs))


def _edge_segments(mask: np.ndarray) -> tuple[tuple[int, int, int, int], ...]:
    binary = mask > 0
    if not bool(binary.any()):
        return ()
    padded = np.pad(binary, 1, mode="constant", constant_values=False)
    center = padded[1:-1, 1:-1]
    left = center & ~padded[1:-1, :-2]
    right = center & ~padded[1:-1, 2:]
    top = center & ~padded[:-2, 1:-1]
    bottom = center & ~padded[2:, 1:-1]
    segments: list[tuple[int, int, int, int]] = []
    for ys, xs, side in (
        (*np.where(left), "left"),
        (*np.where(right), "right"),
        (*np.where(top), "top"),
        (*np.where(bottom), "bottom"),
    ):
        for y, x in zip(ys, xs):
            px = int(x)
            py = int(y)
            if side == "left":
                segments.append((px, py, px, py + 1))
            elif side == "right":
                segments.append((px + 1, py, px + 1, py + 1))
            elif side == "top":
                segments.append((px, py, px + 1, py))
            else:
                segments.append((px, py + 1, px + 1, py + 1))
    return tuple(segments)


def _erode_8(binary: np.ndarray) -> np.ndarray:
    padded = np.pad(binary, 1, mode="constant", constant_values=False)
    neighbors = [
        padded[dy : dy + binary.shape[0], dx : dx + binary.shape[1]]
        for dy in range(3)
        for dx in range(3)
    ]
    return np.logical_and.reduce(neighbors)


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


def _vertical_overlap_ratio(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
    overlap = min(a[3], b[3]) - max(a[1], b[1])
    if overlap <= 0:
        return 0.0
    return overlap / max(1, min(_height(a), _height(b)))


def _horizontal_gap(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> int:
    return max(0, max(a[0], b[0]) - min(a[2], b[2]))


def _horizontal_center_delta_ratio(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
    center_a = (a[0] + a[2]) / 2
    center_b = (b[0] + b[2]) / 2
    return abs(center_a - center_b) / max(1, min(_width(a), _width(b)))


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
        for nx, ny in (
            (x - 1, y - 1),
            (x, y - 1),
            (x + 1, y - 1),
            (x - 1, y),
            (x + 1, y),
            (x - 1, y + 1),
            (x, y + 1),
            (x + 1, y + 1),
        ):
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
    config = _ballonstranslator_ctd_config(root)
    os.chdir(root)
    try:
        from ballontranslator.modules.textdetector.detector_ctd import ComicTextDetector

        detector = ComicTextDetector()
        for key, value in config.items():
            detector.updateParam(key, value)
        mask, _blocks = detector.detect(image, None)
    finally:
        os.chdir(cwd)
    return mask


def _ballonstranslator_ctd_config(root: Path) -> dict[str, object]:
    defaults: dict[str, object] = {
        "device": "cpu",
        "detect_size": 1024,
        "det_rearrange_max_batches": 4,
        "mask dilate size": 2,
    }
    config_path = root / "config" / "config.json"
    if not config_path.exists():
        return defaults
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return defaults
    configured = (
        payload.get("module", {})
        .get("textdetector_params", {})
        .get("ctd", {})
    )
    if not isinstance(configured, dict):
        return defaults
    result = defaults.copy()
    result.update(configured)
    return result
