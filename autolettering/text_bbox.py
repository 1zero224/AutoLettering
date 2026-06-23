from __future__ import annotations


def selected_text_bbox(detection: dict, area_ratio_limit: float = 0.35, score_margin: float = 0.12) -> tuple[int, int, int, int]:
    selected, candidates, search_region = _selected_text_candidates(detection, area_ratio_limit)
    if not candidates:
        return selected
    raw_candidates = [candidate for candidate in (_candidate(item) for item in detection.get("candidate_boxes") or []) if candidate]
    selected_polarity = _candidate_polarity(raw_candidates, selected) or _candidate_polarity(candidates, selected)
    if selected_polarity:
        same_polarity = [candidate for candidate in candidates if candidate["polarity"] in {selected_polarity, None}]
        candidates = same_polarity or candidates
    if not any(candidate["score"] is not None for candidate in candidates):
        return _union_bbox([candidate["bbox"] for candidate in candidates])
    strong_candidates = _score_filtered(candidates, score_margin)
    anchor = selected if selected_polarity == "light_on_dark" else _anchor_bbox(strong_candidates, selected)
    cluster = _connected_to_selected(strong_candidates, anchor, selected_polarity)
    if _is_tight_anchor(selected, search_region):
        cluster = _expand_cluster(cluster, _score_filtered(candidates, score_margin + 0.04), selected_polarity)
    if selected_polarity != "light_on_dark":
        cluster = _expand_local_vertical_columns(cluster, candidates, selected, search_region, selected_polarity)
    if selected_polarity == "light_on_dark":
        cluster = _cluster_with_selected(cluster, selected)
        cluster_bbox = _union_bbox([candidate["bbox"] for candidate in cluster]) if cluster else selected
        if _vertical_cluster_like(cluster_bbox):
            cluster = _expand_light_vertical_column(cluster, candidates, selected)
    return _union_bbox([candidate["bbox"] for candidate in cluster or strong_candidates])


def selected_text_polarity(detection: dict, bbox: tuple[int, int, int, int] | None = None) -> str:
    selected = tuple(int(value) for value in detection["selected_text_box_xyxy"])
    raw_candidates = [candidate for candidate in (_candidate(item) for item in detection.get("candidate_boxes") or []) if candidate]
    candidates = raw_candidates
    bbox = bbox or selected
    for candidate in candidates:
        if candidate["bbox"] == bbox and candidate["polarity"]:
            return candidate["polarity"]
    containing = [candidate for candidate in candidates if _inside(candidate["bbox"], bbox) and candidate["polarity"]]
    if containing:
        return max(containing, key=lambda candidate: candidate["score"] if candidate["score"] is not None else -1)["polarity"]
    selected_candidates = [candidate for candidate in candidates if candidate["bbox"] == selected and candidate["polarity"]]
    if selected_candidates:
        return selected_candidates[0]["polarity"]
    return "dark_on_light"


def _selected_text_candidates(detection: dict, area_ratio_limit: float = 0.35) -> tuple[tuple[int, int, int, int], list[dict], tuple[int, int, int, int]]:
    selected = tuple(int(value) for value in detection["selected_text_box_xyxy"])
    candidates = [_candidate(item) for item in detection.get("candidate_boxes") or []]
    search_region = _search_region(detection, selected, candidates)
    max_text_area = min(_area(search_region) * area_ratio_limit, _area(selected) * 3.0)
    filtered = [
        candidate
        for candidate in candidates
        if candidate
        and _inside(candidate["bbox"], search_region)
        and 0 < _area(candidate["bbox"]) <= max_text_area
    ]
    return selected, filtered, search_region


def _candidate(item: dict) -> dict | None:
    xyxy = item.get("xyxy")
    if not isinstance(xyxy, list) or len(xyxy) != 4:
        return None
    score = item.get("score")
    polarity = item.get("polarity")
    return {
        "bbox": tuple(int(value) for value in xyxy),
        "score": float(score) if isinstance(score, (int, float)) else None,
        "polarity": polarity if polarity in {"dark_on_light", "light_on_dark"} else None,
    }


def _search_region(
    detection: dict,
    selected: tuple[int, int, int, int],
    candidates: list[dict | None],
) -> tuple[int, int, int, int]:
    xyxy = detection.get("search_region_xyxy")
    if isinstance(xyxy, list) and len(xyxy) == 4:
        return tuple(int(value) for value in xyxy)
    candidate_bboxes = [candidate["bbox"] for candidate in candidates if candidate]
    return _union_bbox([selected, *candidate_bboxes]) if candidate_bboxes else selected


def _score_filtered(candidates: list[dict], score_margin: float) -> list[dict]:
    scores = [candidate["score"] for candidate in candidates if candidate["score"] is not None]
    if not scores:
        return candidates
    threshold = max(scores) - score_margin
    filtered = [candidate for candidate in candidates if candidate["score"] is not None and candidate["score"] >= threshold]
    return filtered or candidates


def _anchor_bbox(candidates: list[dict], selected: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    inside = [candidate for candidate in candidates if _inside(candidate["bbox"], selected)]
    scored = [candidate for candidate in inside if candidate["score"] is not None]
    if scored:
        return max(scored, key=lambda candidate: candidate["score"])["bbox"]
    if inside:
        return inside[0]["bbox"]
    return selected


def _candidate_polarity(candidates: list[dict], selected: tuple[int, int, int, int]) -> str | None:
    exact = [candidate for candidate in candidates if candidate["bbox"] == selected and candidate["polarity"]]
    if exact:
        return exact[0]["polarity"]
    inside = [candidate for candidate in candidates if _inside(candidate["bbox"], selected) and candidate["polarity"]]
    if inside:
        return max(inside, key=lambda candidate: candidate["score"] if candidate["score"] is not None else -1)["polarity"]
    return None


def _cluster_with_selected(cluster: list[dict], selected: tuple[int, int, int, int]) -> list[dict]:
    if not cluster:
        return [{"bbox": selected, "score": None, "polarity": "light_on_dark"}]
    if any(candidate["bbox"] == selected for candidate in cluster):
        return cluster
    if any(_inside(candidate["bbox"], selected) for candidate in cluster):
        return [{"bbox": selected, "score": None, "polarity": "light_on_dark"}]
    return cluster


def _expand_light_vertical_column(
    cluster: list[dict],
    candidates: list[dict],
    selected: tuple[int, int, int, int],
) -> list[dict]:
    previous_len = -1
    while len(cluster) != previous_len:
        previous_len = len(cluster)
        cluster_bbox = _union_bbox([candidate["bbox"] for candidate in cluster]) if cluster else selected
        for candidate in candidates:
            if candidate in cluster:
                continue
            if _light_vertical_column_continuation(candidate["bbox"], cluster_bbox, selected):
                cluster.append(candidate)
    return cluster


def _light_vertical_column_continuation(
    bbox: tuple[int, int, int, int],
    cluster: tuple[int, int, int, int],
    selected: tuple[int, int, int, int],
) -> bool:
    if bbox[1] < selected[1]:
        return False
    return (
        _horizontal_overlap_ratio(bbox, cluster) >= 0.65
        and _vertical_relation(bbox, cluster) <= max(36, int(round(_height(selected) * 1.35)))
        and _width(bbox) <= max(96, int(round(_width(selected) * 1.6)))
        and _height(bbox) <= max(140, int(round(_height(selected) * 2.6)))
    )


def _expand_local_vertical_columns(
    cluster: list[dict],
    candidates: list[dict],
    selected: tuple[int, int, int, int],
    search_region: tuple[int, int, int, int],
    polarity: str | None,
) -> list[dict]:
    local_candidates = _local_text_candidates(candidates, selected, search_region, cluster)
    previous_len = -1
    while len(cluster) != previous_len:
        previous_len = len(cluster)
        cluster_bbox = _union_bbox([candidate["bbox"] for candidate in cluster]) if cluster else selected
        for candidate in local_candidates:
            if candidate in cluster:
                continue
            if _touches_text_cluster(candidate["bbox"], cluster_bbox, polarity) or _vertical_column_continuation(candidate["bbox"], cluster_bbox, selected):
                cluster.append(candidate)
    return cluster


def _local_text_candidates(
    candidates: list[dict],
    selected: tuple[int, int, int, int],
    search_region: tuple[int, int, int, int],
    cluster: list[dict],
) -> list[dict]:
    if not cluster:
        return []
    cluster_bbox = _union_bbox([candidate["bbox"] for candidate in cluster])
    max_area = max(_area(cluster_bbox) * 1.25, 9000)
    max_width = max(_width(cluster_bbox) * 1.25, 96)
    max_height = max(_height(cluster_bbox) * 1.35, 240)
    return [
        candidate
        for candidate in candidates
        if _inside(candidate["bbox"], search_region)
        and _near_selected_column(candidate["bbox"], selected, cluster_bbox)
        and _area(candidate["bbox"]) <= max_area
        and _width(candidate["bbox"]) <= max_width
        and _height(candidate["bbox"]) <= max_height
    ]


def _near_selected_column(
    bbox: tuple[int, int, int, int],
    selected: tuple[int, int, int, int],
    cluster: tuple[int, int, int, int],
) -> bool:
    if _inside(bbox, selected):
        return True
    if (
        _horizontal_overlap_ratio(bbox, selected) >= 0.45
        and _vertical_relation(bbox, selected) <= max(360, int(round(_height(selected) * 1.35)))
    ):
        return True
    return (
        _horizontal_overlap_ratio(bbox, cluster) >= 0.45
        and _vertical_relation(bbox, cluster) <= max(24, int(round(_height(cluster) * 0.08)))
    )


def _vertical_column_continuation(
    bbox: tuple[int, int, int, int],
    cluster: tuple[int, int, int, int],
    selected: tuple[int, int, int, int],
) -> bool:
    return (
        _vertical_cluster_like(cluster)
        and _vertical_like(bbox)
        and _horizontal_gap(bbox, cluster) <= _vertical_column_gap_limit(bbox, cluster)
        and _vertical_overlap_ratio(bbox, cluster) >= 0.25
        and _vertical_relation(bbox, cluster) <= max(160, int(round(_height(cluster) * 0.9)))
    )


def _vertical_like(bbox: tuple[int, int, int, int]) -> bool:
    return _height(bbox) >= _width(bbox) * 1.45


def _vertical_cluster_like(bbox: tuple[int, int, int, int]) -> bool:
    return _height(bbox) >= _width(bbox) * 1.25


def _is_tight_anchor(selected: tuple[int, int, int, int], search_region: tuple[int, int, int, int]) -> bool:
    return _area(selected) <= _area(search_region) * 0.25


def _connected_to_selected(candidates: list[dict], selected: tuple[int, int, int, int], polarity: str | None = None) -> list[dict]:
    cluster = [candidate for candidate in candidates if _touches_text_cluster(candidate["bbox"], selected, polarity)]
    return _expand_cluster(cluster, candidates, polarity)


def _expand_cluster(cluster: list[dict], candidates: list[dict], polarity: str | None = None) -> list[dict]:
    previous_len = -1
    while len(cluster) != previous_len:
        previous_len = len(cluster)
        if not cluster:
            return cluster
        cluster_bbox = _union_bbox([candidate["bbox"] for candidate in cluster])
        for candidate in candidates:
            if candidate in cluster:
                continue
            if _touches_text_cluster(candidate["bbox"], cluster_bbox, polarity):
                cluster.append(candidate)
    return cluster


def _touches_text_cluster(bbox: tuple[int, int, int, int], cluster: tuple[int, int, int, int], polarity: str | None = None) -> bool:
    vertical_limit = 18 if polarity == "light_on_dark" else 96
    same_column = (
        _width(bbox) <= max(96, _width(cluster) * 2.5)
        and (not _vertical_like(cluster) or _vertical_like(bbox))
        and _horizontal_overlap_ratio(bbox, cluster) >= 0.5
        and _vertical_relation(bbox, cluster) <= vertical_limit
        and (polarity != "light_on_dark" or bbox[1] >= cluster[1])
    )
    adjacent_column = (
        _horizontal_gap(bbox, cluster) <= _adjacent_column_gap_limit(bbox, cluster)
        and _vertical_overlap_ratio(bbox, cluster) >= 0.35
    )
    return same_column or adjacent_column or _vertical_glyph_continuation(bbox, cluster, polarity)


def _vertical_glyph_continuation(
    bbox: tuple[int, int, int, int],
    cluster: tuple[int, int, int, int],
    polarity: str | None = None,
) -> bool:
    return (
        polarity != "light_on_dark"
        and _vertical_cluster_like(cluster)
        and _horizontal_overlap_ratio(bbox, cluster) >= 0.45
        and _vertical_relation(bbox, cluster) <= 8
        and _width(bbox) <= max(64, int(round(_width(cluster) * 1.8)))
        and _height(bbox) <= max(64, int(round(_height(cluster) * 0.85)))
    )


def _adjacent_column_gap_limit(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> int:
    reference_width = max(_width(a), min(_width(b), 48))
    return max(18, min(36, int(round(reference_width * 0.85))))


def _vertical_column_gap_limit(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> int:
    return max(_adjacent_column_gap_limit(a, b), min(64, int(round(_width(b) * 0.45))))


def _horizontal_gap(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> int:
    return max(0, max(a[0], b[0]) - min(a[2], b[2]))


def _vertical_relation(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> int:
    overlap = min(a[3], b[3]) - max(a[1], b[1])
    if overlap > 0:
        return 0
    return max(0, max(a[1], b[1]) - min(a[3], b[3]))


def _vertical_overlap_ratio(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
    overlap = min(a[3], b[3]) - max(a[1], b[1])
    if overlap <= 0:
        return 0.0
    return overlap / max(1, min(_height(a), _height(b)))


def _horizontal_overlap_ratio(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
    overlap = min(a[2], b[2]) - max(a[0], b[0])
    if overlap <= 0:
        return 0.0
    return overlap / max(1, min(_width(a), _width(b)))


def _width(bbox: tuple[int, int, int, int]) -> int:
    return max(0, bbox[2] - bbox[0])


def _height(bbox: tuple[int, int, int, int]) -> int:
    return max(0, bbox[3] - bbox[1])


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
