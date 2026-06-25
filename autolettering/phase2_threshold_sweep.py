from __future__ import annotations

import csv
import json
from pathlib import Path

from .detection.ctd_masks import CtdMaskComponent, _vertical_component_group


THRESHOLD_SWEEP_SCHEMA_VERSION = "autolettering.phase2.cta_threshold_sweep.v1"
SAFE_DEFAULT_DISTANCE_PX = 80.0


def run_phase2_threshold_sweep(
    phase2_run_dir: str | Path,
    output_root: str | Path = "outputs/runs",
    run_id: str | None = None,
    thresholds: list[float] | None = None,
) -> Path:
    source_dir = Path(phase2_run_dir)
    run_dir = Path(output_root) / (run_id or "phase2-cta-threshold-sweep")
    run_dir.mkdir(parents=True, exist_ok=True)
    threshold_values = _normalize_thresholds(thresholds or [20.0, 40.0, 60.0, 80.0])
    detections = _load_jsonl(source_dir / "detections.jsonl")
    distances = _load_distance_rows(source_dir)
    payload = _threshold_sweep_payload(source_dir, detections, distances, threshold_values)
    _write_json(run_dir / "threshold-sweep.json", payload)
    _write_csv(run_dir / "threshold-sweep.csv", payload)
    _write_report(run_dir / "reports" / "phase2-threshold-sweep-report.md", payload)
    return run_dir


def _threshold_sweep_payload(
    phase2_run_dir: Path,
    detections: list[dict],
    distances_by_record: dict[str, list[dict]],
    thresholds: list[float],
) -> dict:
    claim_results = _claim_results_by_threshold(distances_by_record, thresholds)
    records = [
        _record_sweep(row, distances_by_record.get(row["record_id"], []), thresholds, claim_results)
        for row in detections
    ]
    return {
        "schema_version": THRESHOLD_SWEEP_SCHEMA_VERSION,
        "phase2_run_dir": str(phase2_run_dir),
        "thresholds_px": thresholds,
        "summary_semantics": {
            "match_counts": "canonical Phase 2 unique_component_claim replay",
            "distance_coverage_counts": "record has at least one CTD component within the distance threshold",
        },
        "summary": _summary(records, thresholds),
        "records": records,
    }


def _record_sweep(
    detection: dict,
    rows: list[dict],
    thresholds: list[float],
    claim_results: dict[float, dict[str, dict]],
) -> dict:
    sorted_rows = sorted(rows, key=lambda row: (float(row["edge_distance_px"]), row["component_id"]))
    nearest = sorted_rows[0] if sorted_rows else _nearest_from_detection(detection)
    threshold_rows = [_threshold_row(threshold, nearest, sorted_rows, claim_results) for threshold in thresholds]
    first_match = next((row["threshold_px"] for row in threshold_rows if row["canonical_would_match"]), None)
    first_distance = next((row["threshold_px"] for row in threshold_rows if row["within_distance_threshold"]), None)
    return {
        "record_id": detection["record_id"],
        "image_name": detection.get("image_name"),
        "original_status": detection.get("status"),
        "original_failure_reason": detection.get("failure_reason"),
        "original_selected_text_box_xyxy": detection.get("selected_text_box_xyxy"),
        "nearest_component_id": nearest.get("component_id") if nearest else None,
        "nearest_edge_distance_px": nearest.get("edge_distance_px") if nearest else None,
        "first_distance_threshold_px": first_distance,
        "first_canonical_matching_threshold_px": first_match,
        "first_matching_threshold_px": first_match,
        "safe_default_candidate": _safe_default_candidate(first_match, nearest),
        "distance_warning": _distance_warning(first_match, nearest),
        "thresholds": threshold_rows,
    }


def _threshold_row(
    threshold: float,
    nearest: dict | None,
    rows: list[dict],
    claim_results: dict[float, dict[str, dict]],
) -> dict:
    within_count = sum(1 for row in rows if float(row["edge_distance_px"]) <= threshold)
    record_id = rows[0]["record_id"] if rows else None
    claim = claim_results.get(threshold, {}).get(record_id or "", _fallback_claim(record_id))
    canonical_match = claim["status"] == "matched"
    return {
        "threshold_px": threshold,
        "within_distance_threshold": within_count > 0,
        "proximity_within_component_count": within_count,
        "canonical_would_match": canonical_match,
        "canonical_claim_status": claim["status"],
        "canonical_component_id": claim.get("component_id"),
        "canonical_failure_reason": claim.get("failure_reason"),
        "would_match": canonical_match,
        "within_threshold_count": within_count,
        "nearest_component_id": nearest.get("component_id") if nearest else None,
        "nearest_edge_distance_px": nearest.get("edge_distance_px") if nearest else None,
    }


def _nearest_from_detection(detection: dict) -> dict | None:
    diagnostics = detection.get("cta_match_diagnostics") or detection.get("ctd_match_diagnostics") or {}
    if not diagnostics:
        return None
    return {
        "component_id": diagnostics.get("nearest_component_id"),
        "edge_distance_px": diagnostics.get("nearest_edge_distance_px"),
    }


def _summary(records: list[dict], thresholds: list[float]) -> dict:
    match_counts = {
        _threshold_key(threshold): sum(1 for record in records if _threshold_result(record, threshold)["canonical_would_match"])
        for threshold in thresholds
    }
    distance_coverage_counts = {
        _threshold_key(threshold): sum(1 for record in records if _threshold_result(record, threshold)["within_distance_threshold"])
        for threshold in thresholds
    }
    first_match_counts = {
        _threshold_key(threshold): sum(1 for record in records if record["first_canonical_matching_threshold_px"] == threshold)
        for threshold in thresholds
    }
    first_distance_counts = {
        _threshold_key(threshold): sum(1 for record in records if record["first_distance_threshold_px"] == threshold)
        for threshold in thresholds
    }
    fallback_counts = {
        _threshold_key(threshold): sum(1 for record in records if not _threshold_result(record, threshold)["canonical_would_match"])
        for threshold in thresholds
    }
    return {
        "record_count": len(records),
        "threshold_count": len(thresholds),
        "match_counts": match_counts,
        "canonical_match_counts": match_counts,
        "distance_coverage_counts": distance_coverage_counts,
        "first_match_counts": first_match_counts,
        "first_canonical_match_counts": first_match_counts,
        "first_distance_coverage_counts": first_distance_counts,
        "fallback_counts": fallback_counts,
    }


def _threshold_result(record: dict, threshold: float) -> dict:
    for row in record["thresholds"]:
        if row["threshold_px"] == threshold:
            return row
    raise KeyError(threshold)


def _normalize_thresholds(values: list[float]) -> list[float]:
    return sorted({float(value) for value in values})


def _threshold_key(value: float) -> str:
    return f"{value:.1f}"


def _load_distance_rows(phase2_run_dir: Path) -> dict[str, list[dict]]:
    rows_by_record: dict[str, list[dict]] = {}
    for path in sorted((phase2_run_dir / "debug" / "ctd_masks").glob("*/ctd-mask-edge-distances.jsonl")):
        for row in _load_jsonl(path):
            rows_by_record.setdefault(row["record_id"], []).append(row)
    return rows_by_record


def _claim_results_by_threshold(distances_by_record: dict[str, list[dict]], thresholds: list[float]) -> dict[float, dict[str, dict]]:
    page_rows = _distance_pages(distances_by_record)
    return {threshold: _claim_results_for_threshold(page_rows, threshold) for threshold in thresholds}


def _distance_pages(distances_by_record: dict[str, list[dict]]) -> dict[str, list[dict]]:
    pages: dict[str, list[dict]] = {}
    for rows in distances_by_record.values():
        for row in rows:
            pages.setdefault(_record_page_key(row["record_id"]), []).append(row)
    return pages


def _claim_results_for_threshold(page_rows: dict[str, list[dict]], threshold: float) -> dict[str, dict]:
    results: dict[str, dict] = {}
    for rows in page_rows.values():
        results.update(_claim_page(rows, threshold))
    return results


def _claim_page(rows: list[dict], threshold: float) -> dict[str, dict]:
    components = _components_from_distance_rows(rows)
    component_by_id = {component.component_id: component for component in components}
    record_ids = sorted({row["record_id"] for row in rows})
    results = {record_id: _fallback_claim(record_id) for record_id in record_ids}
    claims: set[str] = set()
    matched: set[str] = set()
    candidates = [row for row in rows if float(row["edge_distance_px"]) <= threshold]
    for row in sorted(candidates, key=lambda item: (float(item["edge_distance_px"]), item["record_id"], item["component_id"])):
        record_id = row["record_id"]
        if record_id in matched:
            continue
        group = _vertical_component_group(component_by_id[row["component_id"]], components)
        member_ids = {component.component_id for component in group}
        if claims & member_ids:
            continue
        claims.update(member_ids)
        matched.add(record_id)
        results[record_id] = _matched_claim(record_id, row, group)
    for row in candidates:
        record_id = row["record_id"]
        if record_id not in matched and row["component_id"] in claims:
            results[record_id] = _fallback_claim(record_id, "component_already_claimed")
    return results


def _components_from_distance_rows(rows: list[dict]) -> list[CtdMaskComponent]:
    components: dict[str, CtdMaskComponent] = {}
    for row in rows:
        if row["component_id"] in components:
            continue
        bbox = tuple(row["component_bbox_xyxy"])
        components[row["component_id"]] = CtdMaskComponent(
            component_id=row["component_id"],
            bbox_xyxy=bbox,
            area_px=max(1, (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])),
            centroid_xy=((bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2),
            mask_path=Path(row["component_mask_path"]),
        )
    return sorted(components.values(), key=lambda item: (item.bbox_xyxy[1], item.bbox_xyxy[0]))


def _matched_claim(record_id: str, row: dict, group: list[CtdMaskComponent]) -> dict:
    bbox = _union_bbox([component.bbox_xyxy for component in group])
    return {
        "record_id": record_id,
        "status": "matched",
        "component_id": "+".join(component.component_id for component in group),
        "bbox_xyxy": list(bbox),
        "mask_path": row["component_mask_path"],
        "distance_px": float(row["edge_distance_px"]),
        "failure_reason": None,
    }


def _fallback_claim(record_id: str | None, reason: str = "no_ctd_mask_within_threshold") -> dict:
    return {
        "record_id": record_id,
        "status": "fallback_required",
        "component_id": None,
        "bbox_xyxy": None,
        "mask_path": None,
        "distance_px": None,
        "failure_reason": reason,
    }


def _record_page_key(record_id: str) -> str:
    return record_id.split("#", 1)[0]


def _union_bbox(bboxes: list[tuple[int, int, int, int]]) -> tuple[int, int, int, int]:
    return (
        min(bbox[0] for bbox in bboxes),
        min(bbox[1] for bbox in bboxes),
        max(bbox[2] for bbox in bboxes),
        max(bbox[3] for bbox in bboxes),
    )


def _safe_default_candidate(first_match: float | None, nearest: dict | None) -> bool:
    distance = _nearest_distance(nearest)
    return first_match is not None and first_match <= SAFE_DEFAULT_DISTANCE_PX and distance <= SAFE_DEFAULT_DISTANCE_PX


def _distance_warning(first_match: float | None, nearest: dict | None) -> str | None:
    distance = _nearest_distance(nearest)
    if first_match is None:
        return None
    if first_match > SAFE_DEFAULT_DISTANCE_PX or distance > SAFE_DEFAULT_DISTANCE_PX:
        return "high_distance_review_required"
    return None


def _nearest_distance(nearest: dict | None) -> float:
    if not nearest or nearest.get("edge_distance_px") is None:
        return float("inf")
    return float(nearest["edge_distance_px"])


def _load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_csv(path: Path, payload: dict) -> None:
    thresholds = payload["thresholds_px"]
    fieldnames = [
        "record_id",
        "nearest_edge_distance_px",
        "first_canonical_matching_threshold_px",
        "first_distance_threshold_px",
        "safe_default_candidate",
        "distance_warning",
    ]
    for threshold in thresholds:
        key = _threshold_key(threshold)
        fieldnames.extend(
            [
                f"canonical_match_at_{key}px",
                f"distance_coverage_at_{key}px",
                f"proximity_component_count_at_{key}px",
                f"canonical_failure_at_{key}px",
            ]
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for record in payload["records"]:
            writer.writerow(_csv_row(record, thresholds))


def _csv_row(record: dict, thresholds: list[float]) -> dict:
    row = {
        "record_id": record["record_id"],
        "nearest_edge_distance_px": _csv_value(record["nearest_edge_distance_px"]),
        "first_canonical_matching_threshold_px": _csv_value(record["first_canonical_matching_threshold_px"]),
        "first_distance_threshold_px": _csv_value(record["first_distance_threshold_px"]),
        "safe_default_candidate": str(bool(record["safe_default_candidate"])).lower(),
        "distance_warning": _csv_value(record["distance_warning"]),
    }
    for threshold in thresholds:
        result = _threshold_result(record, threshold)
        key = _threshold_key(threshold)
        row[f"canonical_match_at_{key}px"] = str(bool(result["canonical_would_match"])).lower()
        row[f"distance_coverage_at_{key}px"] = str(bool(result["within_distance_threshold"])).lower()
        row[f"proximity_component_count_at_{key}px"] = str(result["proximity_within_component_count"])
        row[f"canonical_failure_at_{key}px"] = _csv_value(result["canonical_failure_reason"])
    return row


def _csv_value(value: object) -> str:
    return "" if value is None else str(value)


def _write_report(path: Path, payload: dict) -> None:
    thresholds = payload["thresholds_px"]
    lines = [
        "# Phase 2 CTA Threshold Sweep Report",
        "",
        f"Phase 2 run: `{payload['phase2_run_dir']}`",
        f"Thresholds: {_format_thresholds(thresholds)}",
        "",
        "## Summary",
        "",
        f"- Records: {payload['summary']['record_count']}",
        f"- Thresholds checked: {payload['summary']['threshold_count']}",
        f"- Canonical match counts: {_format_counts(payload['summary']['canonical_match_counts'])}",
        f"- Distance coverage counts: {_format_counts(payload['summary']['distance_coverage_counts'])}",
        f"- First canonical match counts: {_format_counts(payload['summary']['first_canonical_match_counts'])}",
        f"- First distance coverage counts: {_format_counts(payload['summary']['first_distance_coverage_counts'])}",
        f"- Canonical fallback counts: {_format_counts(payload['summary']['fallback_counts'])}",
        "",
        "## Interpretation",
        "",
        "- This sweep is diagnostic: it replays saved point-to-mask-edge distances and does not rerun CTD.",
        "- Canonical match counts replay Phase 2 `unique_component_claim` semantics; distance coverage only means at least one component is close enough.",
        "- Do not treat a high first canonical threshold as automatically safe. Large distances mean the LabelPlus point is far from the nearest closed mask edge, so the record should stay on the fallback/MIMO route unless visual evidence confirms the component.",
        "",
        "## Records",
        "",
    ]
    for record in payload["records"]:
        first = record["first_canonical_matching_threshold_px"]
        distance_first = record["first_distance_threshold_px"]
        warning = f"; warning `{record['distance_warning']}`" if record["distance_warning"] else ""
        if first is None:
            lines.append(
                f"- `{record['record_id']}` never claims canonically; first distance coverage `{distance_first}`; nearest edge distance `{record['nearest_edge_distance_px']}`{warning}."
            )
        else:
            lines.append(
                f"- `{record['record_id']}` first canonical claim at `{first}px`; first distance coverage `{distance_first}`; nearest edge distance `{record['nearest_edge_distance_px']}`{warning}."
            )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _format_thresholds(thresholds: list[float]) -> str:
    return ", ".join(f"`{_threshold_key(threshold)}`" for threshold in thresholds)


def _format_counts(counts: dict[str, int]) -> str:
    return ", ".join(f"`{key}={value}`" for key, value in counts.items())
