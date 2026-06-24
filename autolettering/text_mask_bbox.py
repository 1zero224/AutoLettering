from __future__ import annotations

from .text_bbox import matched_text_mask_bbox, selected_text_bbox


def selected_text_mask_bbox(detection: dict) -> tuple[int, int, int, int]:
    matched_mask = matched_text_mask_bbox(detection)
    if matched_mask is not None:
        return matched_mask
    selected = _selected_bbox(detection)
    if selected is None:
        return selected_text_bbox(detection)
    candidates = [_candidate(item) for item in detection.get("candidate_boxes") or []]
    candidates = [candidate for candidate in candidates if candidate is not None]
    selected_candidate = next((candidate for candidate in candidates if candidate["bbox"] == selected), None)
    if selected_candidate is None:
        return selected

    cluster = [selected_candidate]
    previous_len = -1
    while previous_len != len(cluster):
        previous_len = len(cluster)
        cluster_bbox = _union_bbox([candidate["bbox"] for candidate in cluster])
        for candidate in candidates:
            if candidate in cluster:
                continue
            if _same_text_mask_cluster(candidate, selected_candidate, cluster_bbox):
                cluster.append(candidate)
    return _union_bbox([candidate["bbox"] for candidate in cluster])


def _selected_bbox(detection: dict) -> tuple[int, int, int, int] | None:
    xyxy = detection.get("selected_text_box_xyxy")
    if isinstance(xyxy, list) and len(xyxy) == 4:
        return tuple(int(value) for value in xyxy)
    return None


def _candidate(item: dict) -> dict | None:
    xyxy = item.get("xyxy")
    if not isinstance(xyxy, list) or len(xyxy) != 4:
        return None
    score = item.get("score")
    return {
        "bbox": tuple(int(value) for value in xyxy),
        "score": float(score) if isinstance(score, (int, float)) else None,
        "polarity": item.get("polarity"),
    }


def _same_text_mask_cluster(
    candidate: dict,
    selected: dict,
    cluster_bbox: tuple[int, int, int, int],
    score_margin: float = 0.08,
) -> bool:
    bbox = candidate["bbox"]
    selected_bbox = selected["bbox"]
    if bbox == selected_bbox:
        return True
    if selected["polarity"] in {"dark_on_light", "light_on_dark"} and candidate["polarity"] != selected["polarity"]:
        return False
    if selected["score"] is not None and candidate["score"] is not None and candidate["score"] < selected["score"] - score_margin:
        return False

    selected_height = _height(selected_bbox)
    top_slack = max(24, min(64, int(round(selected_height * 0.35))))
    top_aligned_with_selected = (
        abs(bbox[1] - selected_bbox[1]) <= top_slack
        and _vertical_overlap_ratio(bbox, selected_bbox) >= 0.45
    )
    touches_cluster = (
        _vertical_relation(bbox, cluster_bbox) <= max(24, int(round(selected_height * 0.15)))
        and _vertical_overlap_ratio(bbox, cluster_bbox) >= 0.15
    )
    return (
        (top_aligned_with_selected or touches_cluster)
        and _horizontal_gap(bbox, cluster_bbox) <= max(36, int(round(_width(selected_bbox) * 1.25)))
        and _width(bbox) <= max(96, int(round(_width(selected_bbox) * 2.5)))
    )


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


def _horizontal_gap(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> int:
    return max(0, max(a[0], b[0]) - min(a[2], b[2]))


def _vertical_overlap_ratio(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
    overlap = min(a[3], b[3]) - max(a[1], b[1])
    if overlap <= 0:
        return 0.0
    return overlap / max(1, min(_height(a), _height(b)))


def _vertical_relation(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> int:
    overlap = min(a[3], b[3]) - max(a[1], b[1])
    if overlap > 0:
        return 0
    return max(0, max(a[1], b[1]) - min(a[3], b[3]))
