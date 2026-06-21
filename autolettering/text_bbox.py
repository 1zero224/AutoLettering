from __future__ import annotations


def selected_text_bbox(detection: dict, area_ratio_limit: float = 0.35, score_margin: float = 0.12) -> tuple[int, int, int, int]:
    selected = tuple(int(value) for value in detection["selected_text_box_xyxy"])
    selected_area = _area(selected)
    candidates = [_candidate(item) for item in detection.get("candidate_boxes") or []]
    candidates = [
        candidate
        for candidate in candidates
        if candidate
        and _inside(candidate["bbox"], selected)
        and 0 < _area(candidate["bbox"]) <= selected_area * area_ratio_limit
    ]
    if not candidates:
        return selected
    return _union_bbox([candidate["bbox"] for candidate in _score_filtered(candidates, score_margin)])


def _candidate(item: dict) -> dict | None:
    xyxy = item.get("xyxy")
    if not isinstance(xyxy, list) or len(xyxy) != 4:
        return None
    score = item.get("score")
    return {
        "bbox": tuple(int(value) for value in xyxy),
        "score": float(score) if isinstance(score, (int, float)) else None,
    }


def _score_filtered(candidates: list[dict], score_margin: float) -> list[dict]:
    scores = [candidate["score"] for candidate in candidates if candidate["score"] is not None]
    if not scores:
        return candidates
    threshold = max(scores) - score_margin
    filtered = [candidate for candidate in candidates if candidate["score"] is not None and candidate["score"] >= threshold]
    return filtered or candidates


def _inside(inner: tuple[int, int, int, int], outer: tuple[int, int, int, int]) -> bool:
    ix1, iy1, ix2, iy2 = inner
    ox1, oy1, ox2, oy2 = outer
    return ox1 <= ix1 < ix2 <= ox2 and oy1 <= iy1 < iy2 <= oy2


def _area(bbox: tuple[int, int, int, int]) -> int:
    x1, y1, x2, y2 = bbox
    return max(0, x2 - x1) * max(0, y2 - y1)


def _union_bbox(bboxes: list[tuple[int, int, int, int]]) -> tuple[int, int, int, int]:
    return (
        min(bbox[0] for bbox in bboxes),
        min(bbox[1] for bbox in bboxes),
        max(bbox[2] for bbox in bboxes),
        max(bbox[3] for bbox in bboxes),
    )
