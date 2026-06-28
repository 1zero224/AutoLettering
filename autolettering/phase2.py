from __future__ import annotations

import csv
import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from .detection.comic_text_bubble import (
    DEFAULT_COMIC_DETECTOR_MODEL_PATH,
    ComicTextBubbleDetection,
    ComicTextBubbleDetector,
    detections_payload,
    match_payload,
    select_comic_text_detection,
)
from .detection.cv_text import detect_text_region, detection_result_to_dict, draw_detection_debug
from .detection.ctd_masks import (
    CtdMaskComponent,
    CtdMaskMatch,
    assign_labelplus_points_to_ctd_masks,
    _ballonstranslator_ctd_config,
    ctd_mask_component_rows,
    detect_ctd_mask_components_for_image,
    labelplus_ctd_mask_distance_rows,
)
from .detection.model_text_recognition import (
    recognize_text_region_with_model,
    write_text_region_context_crop,
)
from .detection.models import CandidateBox, DetectionResult
from .detection.regions import build_search_region
from .labelplus.models import ManifestImage, ManifestLabel
from .labelplus.parser import parse_labelplus_project
from .phase1 import _select_sample_records, _timestamp_run_id
from .record_selection import normalize_record_ids
from .text_bbox import selected_text_bbox
from .text_body_bbox import selected_text_body_bbox


CTA_MATCH_DIAGNOSTICS_SCHEMA_VERSION = "autolettering.cta_mask_match_diagnostics.v1"
CTA_MATCH_DIAGNOSTICS_TOP_LIMIT = 12
FALLBACK_CONTEXT_CLUSTER_GAP_PX = 140.0
FALLBACK_CONTEXT_DISTANCE_RATIO_LIMIT = 2.0
DEFAULT_COMIC_DETECTOR_MAX_DISTANCE_PX = 120.0


def run_phase2(
    labelplus_file: str | Path,
    output_root: str | Path = "outputs/runs",
    run_id: str | None = None,
    sample_limit: int = 30,
    radius_x: int = 220,
    radius_y: int = 180,
    record_ids: Iterable[str] | None = None,
    detection_strategy: str = "cta_mask",
    ctd_max_edge_distance_px: float = 30.0,
    call_model_text_recognition: bool = False,
    model_text_recognition_client: Any | None = None,
    comic_detector_model_path: str | Path | None = None,
    comic_detector_conf_threshold: float = 0.5,
    comic_detector_max_distance_px: float = DEFAULT_COMIC_DETECTOR_MAX_DISTANCE_PX,
) -> Path:
    manifest = parse_labelplus_project(labelplus_file)
    run_dir = Path(output_root) / (run_id or _timestamp_run_id().replace("phase1", "phase2"))
    run_dir.mkdir(parents=True, exist_ok=True)

    selected = _select_detection_records(manifest, sample_limit, record_ids)
    strategy = _normalize_detection_strategy(detection_strategy)
    ok_count, failed_count = _write_detections(
        run_dir,
        selected,
        radius_x,
        radius_y,
        detection_strategy=strategy,
        ctd_max_edge_distance_px=ctd_max_edge_distance_px,
        call_model_text_recognition=call_model_text_recognition,
        model_text_recognition_client=model_text_recognition_client,
        comic_detector_model_path=comic_detector_model_path,
        comic_detector_conf_threshold=comic_detector_conf_threshold,
        comic_detector_max_distance_px=comic_detector_max_distance_px,
    )

    _write_phase2_report(
        output_path=run_dir / "reports" / "phase2-report.md",
        labelplus_file=Path(labelplus_file),
        sample_count=len(selected),
        ok_count=ok_count,
        failed_count=failed_count,
        radius_x=radius_x,
        radius_y=radius_y,
        detection_strategy=strategy,
        call_model_text_recognition=call_model_text_recognition,
        comic_detector_model_path=comic_detector_model_path or DEFAULT_COMIC_DETECTOR_MODEL_PATH,
        comic_detector_conf_threshold=comic_detector_conf_threshold,
        comic_detector_max_distance_px=comic_detector_max_distance_px,
    )
    return run_dir


def _select_detection_records(
    manifest,
    sample_limit: int,
    record_ids: Iterable[str] | None = None,
) -> list[tuple[ManifestImage, ManifestLabel]]:
    wanted = normalize_record_ids(record_ids)
    if wanted is None:
        return _select_sample_records(manifest, sample_limit)
    selected: list[tuple[ManifestImage, ManifestLabel]] = []
    for image in manifest.images:
        for label in image.labels:
            if label.id in wanted:
                selected.append((image, label))
                if len(selected) >= sample_limit:
                    return selected
    return selected


def _write_detections(
    run_dir: Path,
    selected_records: list[tuple[ManifestImage, ManifestLabel]],
    radius_x: int,
    radius_y: int,
    detection_strategy: str,
    ctd_max_edge_distance_px: float,
    call_model_text_recognition: bool,
    model_text_recognition_client: Any | None,
    comic_detector_model_path: str | Path | None,
    comic_detector_conf_threshold: float,
    comic_detector_max_distance_px: float,
) -> tuple[int, int]:
    ok_count = failed_count = 0
    rows: list[dict] = []
    if _is_cta_mask_strategy(detection_strategy):
        ctd_matches, ctd_diagnostics = _ctd_matches_by_record(run_dir, selected_records, ctd_max_edge_distance_px)
    else:
        ctd_matches = {}
        ctd_diagnostics = {}
    comic_detector = _comic_detector(detection_strategy, comic_detector_model_path, comic_detector_conf_threshold)
    comic_detections_by_image: dict[tuple[str, str], list[ComicTextBubbleDetection]] = {}
    with (run_dir / "detections.jsonl").open("w", encoding="utf-8", newline="\n") as handle:
        for image, label in selected_records:
            comic_detections = _comic_detections_for_image(comic_detector, comic_detections_by_image, image)
            payload = _detect_record(
                run_dir,
                image,
                label,
                radius_x,
                radius_y,
                detection_strategy=detection_strategy,
                ctd_match=ctd_matches.get(label.id),
                ctd_match_diagnostics=ctd_diagnostics.get(label.id),
                ctd_max_edge_distance_px=ctd_max_edge_distance_px,
                call_model_text_recognition=call_model_text_recognition,
                model_text_recognition_client=model_text_recognition_client,
                comic_detections=comic_detections,
                comic_detector_max_distance_px=comic_detector_max_distance_px,
            )
            rows.append(payload)
            ok_count += int(payload["status"] == "ok")
            failed_count += int(payload["status"] != "ok")
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
    _write_manual_review_csv(run_dir / "reports" / "manual-review.csv", rows)
    return ok_count, failed_count


def _detect_record(
    run_dir: Path,
    image: ManifestImage,
    label: ManifestLabel,
    radius_x: int,
    radius_y: int,
    detection_strategy: str = "cv",
    ctd_match: CtdMaskMatch | None = None,
    ctd_match_diagnostics: dict | None = None,
    ctd_max_edge_distance_px: float | None = None,
    call_model_text_recognition: bool = False,
    model_text_recognition_client: Any | None = None,
    comic_detections: list[ComicTextBubbleDetection] | None = None,
    comic_detector_max_distance_px: float = DEFAULT_COMIC_DETECTOR_MAX_DISTANCE_PX,
) -> dict:
    result = _detect_with_strategy(
        image,
        label,
        radius_x,
        radius_y,
        detection_strategy=detection_strategy,
        ctd_match=ctd_match,
        comic_detections=comic_detections,
        comic_detector_max_distance_px=comic_detector_max_distance_px,
    )
    debug_path = run_dir / "debug" / "detection" / f"{Path(image.image_name).stem}-{label.record_index}.png"

    payload = detection_result_to_dict(result)
    payload.update(
        {
            "image_name": image.image_name,
            "image_path": str(image.image_path),
            "translated_text": label.translated_text,
            "group_name": label.group_name,
            "detection_method": detection_strategy,
            "debug_image_path": str(debug_path),
        }
    )
    if ctd_match is not None:
        match_payload = _ctd_match_payload(ctd_match)
        if _is_cta_mask_strategy(detection_strategy):
            payload["cta_match"] = match_payload
        payload["ctd_match"] = match_payload
    if ctd_match_diagnostics is not None:
        if _is_cta_mask_strategy(detection_strategy):
            payload["cta_match_diagnostics"] = ctd_match_diagnostics
        payload["ctd_match_diagnostics"] = ctd_match_diagnostics
    if _is_comic_text_bubble_strategy(detection_strategy):
        _add_comic_text_bubble_payload(payload, label, comic_detections or [], comic_detector_max_distance_px)
    if result.status == "fallback_required":
        fallback_candidate_context = None
        if _is_comic_text_bubble_strategy(detection_strategy):
            fallback_candidate_context = _comic_fallback_context_candidates(payload.get("comic_text_bubble_match"))
        payload["fallback"] = _mimo_gpt_fallback_payload(
            label,
            image.width,
            image.height,
            radius_x,
            radius_y,
            payload.get("failure_reason"),
            ctd_max_edge_distance_px=ctd_max_edge_distance_px,
            ctd_match_diagnostics=ctd_match_diagnostics,
            fallback_candidate_context=fallback_candidate_context,
        )
        if _is_comic_text_bubble_strategy(detection_strategy):
            payload["fallback"].update(
                {
                    "upstream_match_metric": "labelplus_point_to_comic_text_box_distance",
                    "upstream_text_region_source": "comic_text_bubble_rtdetrv2",
                    "upstream_match_threshold_px": comic_detector_max_distance_px,
                }
            )
    payload["lettering_route"] = _lettering_route_payload(payload, detection_strategy)
    payload.update(_text_region_payload(payload, detection_strategy))
    if call_model_text_recognition:
        _add_model_text_recognition(
            payload,
            run_dir,
            image,
            label,
            model_text_recognition_client,
        )
    full_bbox, body_bbox = _add_derived_text_bboxes(payload)
    draw_detection_debug(
        image.image_path,
        label,
        result,
        debug_path,
        selected_text_full_xyxy=full_bbox,
        selected_text_body_xyxy=body_bbox,
    )
    return payload


def _add_model_text_recognition(
    payload: dict,
    run_dir: Path,
    image: ManifestImage,
    label: ManifestLabel,
    client: Any | None,
) -> None:
    if client is None:
        payload["model_text_recognition"] = {
            "status": "skipped",
            "failure_reason": "model_text_recognition_client_required",
        }
        return

    context_bbox = _model_text_context_bbox(payload)
    context_path = (
        run_dir
        / "debug"
        / "model_text_recognition"
        / f"{Path(image.image_name).stem}-{label.record_index}.png"
    )
    write_text_region_context_crop(image.image_path, context_bbox, context_path)
    labelpoint_in_context = (label.x_px - context_bbox[0], label.y_px - context_bbox[1])
    candidate_boxes = _model_text_candidate_boxes(payload, context_bbox)

    try:
        recognition = recognize_text_region_with_model(
            client=client,
            context_image_path=context_path,
            context_bbox_xyxy=context_bbox,
            labelplus_point_xy=labelpoint_in_context,
            translated_text=label.translated_text,
            candidate_boxes=candidate_boxes,
        )
    except Exception as exc:  # pragma: no cover - real API failures are recorded, not re-raised.
        recognition = {
            "status": "failed",
            "failure_reason": f"model_text_recognition_error:{type(exc).__name__}",
        }

    recognition.update(
        {
            "context_image_path": str(context_path),
            "context_bbox_xyxy": list(context_bbox),
            "context_labelplus_point_xy": list(labelpoint_in_context),
            "candidate_boxes_xyxy": candidate_boxes,
        }
    )
    payload["model_text_recognition"] = recognition
    if recognition.get("status") == "ok":
        payload["recognized_source_text"] = recognition.get("source_text")
        payload["recognized_orientation"] = recognition.get("orientation")
        payload["model_text_region_bbox_xyxy"] = recognition.get("global_bbox_xyxy")


def _model_text_context_bbox(payload: dict) -> tuple[int, int, int, int]:
    fallback = payload.get("fallback") or {}
    bbox = fallback.get("context_bbox_xyxy") or payload.get("search_region_xyxy")
    if not _is_bbox_like(bbox):
        raise ValueError("missing_model_text_context_bbox")
    return _bbox_tuple(bbox)


def _model_text_candidate_boxes(payload: dict, context_bbox: tuple[int, int, int, int]) -> list[list[int]]:
    boxes: list[list[int]] = []
    seen: set[tuple[int, int, int, int]] = set()
    for bbox in _model_text_global_candidate_bboxes(payload):
        local = _bbox_to_context(bbox, context_bbox)
        key = tuple(local)
        if key in seen:
            continue
        seen.add(key)
        boxes.append(local)
    return boxes


def _model_text_global_candidate_bboxes(payload: dict) -> list[tuple[int, int, int, int]]:
    boxes: list[tuple[int, int, int, int]] = []
    selected = payload.get("selected_text_box_xyxy")
    if _is_bbox_like(selected):
        boxes.append(_bbox_tuple(selected))
    for candidate in payload.get("candidate_boxes", []):
        bbox = candidate.get("xyxy") if isinstance(candidate, dict) else None
        if _is_bbox_like(bbox):
            boxes.append(_bbox_tuple(bbox))
    fallback = payload.get("fallback") or {}
    for bbox in fallback.get("context_candidate_bboxes_xyxy") or []:
        if _is_bbox_like(bbox):
            boxes.append(_bbox_tuple(bbox))
    return boxes


def _bbox_to_context(
    bbox: tuple[int, int, int, int],
    context_bbox: tuple[int, int, int, int],
) -> list[int]:
    return [
        bbox[0] - context_bbox[0],
        bbox[1] - context_bbox[1],
        bbox[2] - context_bbox[0],
        bbox[3] - context_bbox[1],
    ]


def _detect_with_strategy(
    image: ManifestImage,
    label: ManifestLabel,
    radius_x: int,
    radius_y: int,
    detection_strategy: str,
    ctd_match: CtdMaskMatch | None,
    comic_detections: list[ComicTextBubbleDetection] | None = None,
    comic_detector_max_distance_px: float = DEFAULT_COMIC_DETECTOR_MAX_DISTANCE_PX,
) -> DetectionResult:
    if detection_strategy == "cv":
        return detect_text_region(image.image_path, label, image.width, image.height, radius_x, radius_y)
    if _is_comic_text_bubble_strategy(detection_strategy):
        return _detect_with_comic_text_bubble(
            image,
            label,
            radius_x,
            radius_y,
            comic_detections or [],
            comic_detector_max_distance_px,
        )
    if not _is_cta_mask_strategy(detection_strategy):
        raise ValueError(f"unsupported_detection_strategy:{detection_strategy}")
    search_region = build_search_region(label.x_px, label.y_px, image.width, image.height, radius_x, radius_y)
    if ctd_match and ctd_match.status == "matched" and ctd_match.bbox_xyxy:
        bbox = ctd_match.bbox_xyxy
        return DetectionResult(
            record_id=label.id,
            status="ok",
            search_region_xyxy=search_region,
            candidate_boxes=[
                CandidateBox(
                    xyxy=bbox,
                    area=max(1, (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])),
                    dark_pixel_count=0,
                    center_distance=ctd_match.distance_px or 0.0,
                    score=1.0,
                    polarity="ctd_mask",
                )
            ],
            selected_text_box_xyxy=bbox,
            confidence=1.0,
            failure_reason=None,
        )
    reason = ctd_match.failure_reason if ctd_match else "ctd_not_run"
    return DetectionResult(
        record_id=label.id,
        status="fallback_required",
        search_region_xyxy=search_region,
        candidate_boxes=[],
        selected_text_box_xyxy=None,
        confidence=0.0,
        failure_reason=reason,
    )


def _detect_with_comic_text_bubble(
    image: ManifestImage,
    label: ManifestLabel,
    radius_x: int,
    radius_y: int,
    detections: list[ComicTextBubbleDetection],
    max_distance_px: float,
) -> DetectionResult:
    search_region = build_search_region(label.x_px, label.y_px, image.width, image.height, radius_x, radius_y)
    match = select_comic_text_detection(detections, (label.x_px, label.y_px), max_distance_px=max_distance_px)
    candidate_boxes = [
        CandidateBox(
            xyxy=detection.bbox_xyxy,
            area=max(1, (detection.bbox_xyxy[2] - detection.bbox_xyxy[0]) * (detection.bbox_xyxy[3] - detection.bbox_xyxy[1])),
            dark_pixel_count=0,
            center_distance=round(_point_to_bbox_distance((label.x_px, label.y_px), detection.bbox_xyxy), 3),
            score=detection.score,
            polarity=f"comic_text_bubble:{detection.label}",
        )
        for detection in detections
        if detection.label in {"text_bubble", "text_free"}
    ]
    selected = match.selected_detection
    if selected is None:
        return DetectionResult(
            record_id=label.id,
            status="fallback_required",
            search_region_xyxy=search_region,
            candidate_boxes=candidate_boxes,
            selected_text_box_xyxy=None,
            confidence=0.0,
            failure_reason=match.failure_reason,
        )
    return DetectionResult(
        record_id=label.id,
        status="ok",
        search_region_xyxy=search_region,
        candidate_boxes=candidate_boxes,
        selected_text_box_xyxy=selected.bbox_xyxy,
        confidence=selected.score,
        failure_reason=None,
    )


def _comic_detector(
    detection_strategy: str,
    model_path: str | Path | None,
    conf_threshold: float,
) -> ComicTextBubbleDetector | None:
    if not _is_comic_text_bubble_strategy(detection_strategy):
        return None
    return ComicTextBubbleDetector(model_path or DEFAULT_COMIC_DETECTOR_MODEL_PATH, conf_threshold=conf_threshold)


def _comic_detections_for_image(
    detector: ComicTextBubbleDetector | None,
    cache: dict[tuple[str, str], list[ComicTextBubbleDetection]],
    image: ManifestImage,
) -> list[ComicTextBubbleDetection] | None:
    if detector is None:
        return None
    key = (image.image_name, str(image.image_path))
    if key not in cache:
        cache[key] = detector.detect_image(image.image_path)
    return cache[key]


def _add_comic_text_bubble_payload(
    payload: dict,
    label: ManifestLabel,
    detections: list[ComicTextBubbleDetection],
    threshold_px: float,
) -> None:
    match = select_comic_text_detection(detections, (label.x_px, label.y_px), max_distance_px=threshold_px)
    payload["comic_text_bubble_detections"] = detections_payload(detections)
    payload["comic_text_bubble_match"] = match_payload(match, threshold_px)


def _ctd_matches_by_record(
    run_dir: Path,
    selected_records: list[tuple[ManifestImage, ManifestLabel]],
    max_edge_distance_px: float,
) -> tuple[dict[str, CtdMaskMatch], dict[str, dict]]:
    matches: dict[str, CtdMaskMatch] = {}
    diagnostics: dict[str, dict] = {}
    for image, labels in _group_labels_by_image(selected_records):
        components = _detect_page_components(run_dir, image)
        distance_rows = _write_ctd_distance_rows(run_dir, image, labels, components, max_edge_distance_px)
        image_matches = assign_labelplus_points_to_ctd_masks(labels, components, max_edge_distance_px=max_edge_distance_px)
        matches.update(image_matches)
        diagnostics.update(_ctd_match_diagnostics_by_record(labels, distance_rows, image_matches, max_edge_distance_px))
    return matches, diagnostics


def _group_labels_by_image(
    selected_records: list[tuple[ManifestImage, ManifestLabel]],
) -> list[tuple[ManifestImage, list[ManifestLabel]]]:
    grouped: dict[tuple[str, str], tuple[ManifestImage, list[ManifestLabel]]] = {}
    for image, label in selected_records:
        key = (image.image_name, str(image.image_path))
        if key not in grouped:
            grouped[key] = (image, [])
        grouped[key][1].append(label)
    return list(grouped.values())


def _detect_page_components(run_dir: Path, image: ManifestImage) -> list[CtdMaskComponent]:
    output_dir = _ctd_mask_output_dir(run_dir, image)
    _write_json(output_dir / "ctd-config.json", _ballonstranslator_ctd_config(Path("BallonsTranslator")))
    components = detect_ctd_mask_components_for_image(image.image_path, output_dir)
    _write_json(
        output_dir / "cta-closed-mask-components.json",
        {
            "schema_version": "autolettering.cta_mask_components.v1",
            "image_name": image.image_name,
            "image_path": str(image.image_path),
            "source_mask_path": str(output_dir / "ctd-refined-mask.png"),
            "componentization": "8_connected_components_over_ballonstranslator_ctd_refined_mask",
            "components": ctd_mask_component_rows(components),
        },
    )
    return components


def _write_ctd_distance_rows(
    run_dir: Path,
    image: ManifestImage,
    labels: list[ManifestLabel],
    components: list[CtdMaskComponent],
    max_edge_distance_px: float,
) -> list[dict]:
    rows = labelplus_ctd_mask_distance_rows(labels, components, max_edge_distance_px=max_edge_distance_px)
    _write_jsonl(_ctd_mask_output_dir(run_dir, image) / "ctd-mask-edge-distances.jsonl", rows)
    return rows


def _ctd_match_diagnostics_by_record(
    labels: list[ManifestLabel],
    distance_rows: list[dict],
    matches: dict[str, CtdMaskMatch],
    threshold_px: float,
) -> dict[str, dict]:
    rows_by_record: dict[str, list[dict]] = {}
    for row in distance_rows:
        rows_by_record.setdefault(row["record_id"], []).append(row)
    return {
        label.id: _ctd_match_diagnostics_payload(
            label.id,
            rows_by_record.get(label.id, []),
            matches.get(label.id),
            threshold_px,
        )
        for label in labels
    }


def _ctd_match_diagnostics_payload(
    record_id: str,
    rows: list[dict],
    match: CtdMaskMatch | None,
    threshold_px: float,
    top_limit: int = CTA_MATCH_DIAGNOSTICS_TOP_LIMIT,
) -> dict:
    sorted_rows = sorted(rows, key=lambda item: (item["edge_distance_px"], item["component_id"]))
    nearest = sorted_rows[0] if sorted_rows else None
    return {
        "schema_version": CTA_MATCH_DIAGNOSTICS_SCHEMA_VERSION,
        "record_id": record_id,
        "match_status": match.status if match else "fallback_required",
        "failure_reason": match.failure_reason if match else "ctd_not_run",
        "threshold_px": threshold_px,
        "candidate_count": len(sorted_rows),
        "within_threshold_count": sum(1 for row in sorted_rows if row.get("within_threshold")),
        "nearest_component_id": nearest.get("component_id") if nearest else None,
        "nearest_edge_distance_px": nearest.get("edge_distance_px") if nearest else None,
        "selected_component_id": match.component_id if match and match.status == "matched" else None,
        "top_candidates": [_ctd_match_candidate_payload(row) for row in sorted_rows[:top_limit]],
    }


def _ctd_match_candidate_payload(row: dict) -> dict:
    return {
        "component_id": row["component_id"],
        "component_bbox_xyxy": row["component_bbox_xyxy"],
        "component_mask_path": row["component_mask_path"],
        "edge_distance_px": row["edge_distance_px"],
        "within_threshold": row["within_threshold"],
    }


def _ctd_mask_output_dir(run_dir: Path, image: ManifestImage) -> Path:
    return run_dir / "debug" / "ctd_masks" / Path(image.image_name).stem


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _ctd_match_payload(match: CtdMaskMatch) -> dict:
    return {
        "record_id": match.record_id,
        "status": match.status,
        "component_id": match.component_id,
        "bbox_xyxy": list(match.bbox_xyxy) if match.bbox_xyxy else None,
        "mask_path": str(match.mask_path) if match.mask_path else None,
        "distance_px": match.distance_px,
        "failure_reason": match.failure_reason,
    }


def _normalize_detection_strategy(strategy: str) -> str:
    if strategy in {"comic_rtdetrv2", "comic_text_bubble_rtdetrv2"}:
        return "comic_rtdetrv2"
    if strategy == "ctd_mask":
        return "ctd_mask"
    if strategy in {"cta_mask", "cta"}:
        return "cta_mask"
    if strategy == "cv":
        return "cv"
    raise ValueError(f"unsupported_detection_strategy:{strategy}")


def _is_cta_mask_strategy(strategy: str) -> bool:
    return strategy in {"cta_mask", "ctd_mask"}


def _is_comic_text_bubble_strategy(strategy: str) -> bool:
    return strategy == "comic_rtdetrv2"


def _mimo_gpt_fallback_payload(
    label: ManifestLabel,
    image_width: int,
    image_height: int,
    radius_x: int,
    radius_y: int,
    trigger_reason: str | None = None,
    ctd_max_edge_distance_px: float | None = None,
    ctd_match_diagnostics: dict | None = None,
    fallback_candidate_context: _FallbackContextCandidates | None = None,
) -> dict:
    source_bbox = build_search_region(label.x_px, label.y_px, image_width, image_height, radius_x, radius_y)
    candidate_context = fallback_candidate_context or _fallback_context_candidates(ctd_match_diagnostics)
    expanded_source_bbox = _union_bboxes([source_bbox, *candidate_context.bboxes])
    context_bbox = _near_square_bbox(expanded_source_bbox, image_width, image_height)
    payload = {
        "method": "mimo_crop_then_gpt_image2_masked_edit",
        "context_bbox_xyxy": list(context_bbox),
        "source_context_bbox_xyxy": list(source_bbox),
        "expanded_source_context_bbox_xyxy": list(expanded_source_bbox),
        "context_source": candidate_context.source,
        "labelplus_point_xy": [label.x_px, label.y_px],
        "context_labelplus_point_xy": [label.x_px - context_bbox[0], label.y_px - context_bbox[1]],
        "context_shape": "near_square",
        "translated_text": label.translated_text,
        "trigger_reason": trigger_reason,
        "upstream_match_attempted": True,
        "upstream_match_metric": "point_to_mask_edge",
        "upstream_match_threshold_px": ctd_max_edge_distance_px,
        "locator_target_kind": "original_text_region_inside_context",
        "preferred_mask_shape": "tight_local_bbox",
    }
    if candidate_context.bboxes:
        payload[candidate_context.id_field] = candidate_context.candidate_ids
        payload["context_candidate_bboxes_xyxy"] = [list(bbox) for bbox in candidate_context.bboxes]
        payload.update(candidate_context.extra_fields)
    return payload


class _FallbackContextCandidates:
    def __init__(
        self,
        candidate_ids: list[str],
        bboxes: list[tuple[int, int, int, int]],
        source_with_candidates: str = "labelplus_search_region_plus_ctd_candidates",
        id_field: str = "context_candidate_component_ids",
        extra_fields: dict | None = None,
    ) -> None:
        self.candidate_ids = candidate_ids
        self.bboxes = bboxes
        self.source_with_candidates = source_with_candidates
        self.id_field = id_field
        self.extra_fields = extra_fields or {}

    @property
    def source(self) -> str:
        if self.bboxes:
            return self.source_with_candidates
        return "labelplus_search_region"


def _fallback_context_candidates(ctd_match_diagnostics: dict | None) -> _FallbackContextCandidates:
    if not ctd_match_diagnostics or ctd_match_diagnostics.get("match_status") != "fallback_required":
        return _FallbackContextCandidates([], [])
    top_candidates = ctd_match_diagnostics.get("top_candidates") or []
    if not top_candidates:
        return _FallbackContextCandidates([], [])
    usable_candidates = []
    for candidate in top_candidates:
        parsed_candidate = _fallback_context_candidate_tuple(candidate)
        if parsed_candidate is not None:
            usable_candidates.append(parsed_candidate)
    if not usable_candidates:
        return _FallbackContextCandidates([], [])
    selected = [usable_candidates[0]]
    selected_bbox = usable_candidates[0][1]
    max_distance = usable_candidates[0][2] * FALLBACK_CONTEXT_DISTANCE_RATIO_LIMIT
    for candidate in usable_candidates[1:]:
        if candidate[2] > max_distance:
            continue
        if _bbox_gap_px(candidate[1], selected_bbox) > FALLBACK_CONTEXT_CLUSTER_GAP_PX:
            continue
        selected.append(candidate)
        selected_bbox = _union_bboxes([selected_bbox, candidate[1]])
    return _FallbackContextCandidates(
        [candidate[0] for candidate in selected],
        [candidate[1] for candidate in selected],
    )


def _comic_fallback_context_candidates(match: dict | None) -> _FallbackContextCandidates:
    source = "labelplus_search_region_plus_comic_text_bubble_candidates"
    if not match or match.get("status") != "fallback_required":
        return _FallbackContextCandidates([], [], source_with_candidates=source)
    usable_candidates = []
    for index, candidate in enumerate(match.get("top_candidates") or [], start=1):
        parsed_candidate = _comic_fallback_context_candidate_tuple(candidate, index)
        if parsed_candidate is not None:
            usable_candidates.append(parsed_candidate)
    if not usable_candidates:
        return _FallbackContextCandidates([], [], source_with_candidates=source)
    selected = [usable_candidates[0]]
    selected_bbox = usable_candidates[0][1]
    max_distance = usable_candidates[0][2] * FALLBACK_CONTEXT_DISTANCE_RATIO_LIMIT
    for candidate in usable_candidates[1:]:
        if candidate[2] > max_distance:
            continue
        if _bbox_gap_px(candidate[1], selected_bbox) > FALLBACK_CONTEXT_CLUSTER_GAP_PX:
            continue
        selected.append(candidate)
        selected_bbox = _union_bboxes([selected_bbox, candidate[1]])
    return _FallbackContextCandidates(
        [candidate[0] for candidate in selected],
        [candidate[1] for candidate in selected],
        source_with_candidates=source,
        id_field="context_candidate_detection_ids",
        extra_fields={
            "context_candidate_labels": [candidate[3] for candidate in selected],
            "context_candidate_scores": [candidate[4] for candidate in selected],
            "context_candidate_distances_px": [candidate[2] for candidate in selected],
        },
    )


def _fallback_context_candidate_tuple(
    candidate: dict,
) -> tuple[str, tuple[int, int, int, int], float] | None:
    bbox = candidate.get("component_bbox_xyxy")
    if not _is_bbox_like(bbox):
        return None
    component_id = candidate.get("component_id")
    distance_px = candidate.get("edge_distance_px")
    if not isinstance(distance_px, int | float):
        return None
    return str(component_id), _bbox_tuple(bbox), float(distance_px)


def _comic_fallback_context_candidate_tuple(
    candidate: dict,
    index: int,
) -> tuple[str, tuple[int, int, int, int], float, str, float] | None:
    label = candidate.get("label")
    if label not in {"text_bubble", "text_free"}:
        return None
    bbox = candidate.get("bbox_xyxy")
    if not _is_bbox_like(bbox):
        return None
    distance_px = candidate.get("distance_px")
    if not isinstance(distance_px, int | float):
        return None
    score = candidate.get("score")
    if not isinstance(score, int | float):
        return None
    return f"{label}-{index}", _bbox_tuple(bbox), float(distance_px), str(label), float(score)


def _is_bbox_like(value: object) -> bool:
    return (
        isinstance(value, list | tuple)
        and len(value) == 4
        and all(isinstance(item, int | float) for item in value)
    )


def _bbox_tuple(value: list[int | float] | tuple[int | float, ...]) -> tuple[int, int, int, int]:
    return tuple(int(round(item)) for item in value)  # type: ignore[return-value]


def _union_bboxes(bboxes: list[tuple[int, int, int, int]]) -> tuple[int, int, int, int]:
    return (
        min(bbox[0] for bbox in bboxes),
        min(bbox[1] for bbox in bboxes),
        max(bbox[2] for bbox in bboxes),
        max(bbox[3] for bbox in bboxes),
    )


def _bbox_gap_px(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
    dx = max(a[0] - b[2], b[0] - a[2], 0)
    dy = max(a[1] - b[3], b[1] - a[3], 0)
    return float((dx * dx + dy * dy) ** 0.5)


def _text_region_payload(payload: dict, detection_strategy: str) -> dict:
    if _is_comic_text_bubble_strategy(detection_strategy):
        match = payload.get("comic_text_bubble_match") or {}
        if payload.get("status") == "ok" and match.get("status") == "matched":
            return {
                "text_region_kind": "comic_text_bubble_rtdetrv2_matched",
                "text_region_source": "comic_text_bubble_rtdetrv2",
                "text_region_mask_path": None,
                "text_region_mask_bbox_xyxy": match.get("selected_bbox_xyxy"),
                "match_status": "matched",
                "text_region_user_strategy": detection_strategy,
                "upstream_text_region_source": "comic_text_bubble_detector",
                "comic_text_bubble_detector_class": match.get("selected_label"),
                "comic_text_bubble_detector_score": match.get("selected_score"),
            }
        if payload.get("status") == "fallback_required":
            return {
                "text_region_kind": "comic_text_bubble_rtdetrv2_fallback_context_only",
                "text_region_source": "mimo_vision_model",
                "text_region_mask_path": None,
                "text_region_mask_bbox_xyxy": None,
                "match_status": "fallback_required",
                "text_region_user_strategy": detection_strategy,
                "upstream_text_region_source": "comic_text_bubble_rtdetrv2",
            }
    if _is_cta_mask_strategy(detection_strategy):
        match = payload.get("cta_match") or payload.get("ctd_match") or {}
        common = _ctd_text_region_contract(detection_strategy)
        if payload.get("status") == "ok" and match.get("status") == "matched":
            return {
                "text_region_kind": "cta_mask_matched",
                "text_region_source": "ctd_refined_mask_component",
                "text_region_mask_path": match.get("mask_path"),
                "text_region_mask_bbox_xyxy": match.get("bbox_xyxy"),
                "match_status": "matched",
                **common,
            }
        if payload.get("status") == "fallback_required":
            return {
                "text_region_kind": "fallback_context_only",
                "text_region_source": "mimo_vision_model",
                "text_region_mask_path": None,
                "text_region_mask_bbox_xyxy": None,
                "match_status": "fallback_required",
                **common,
            }
    if payload.get("status") == "ok":
        return {
            "text_region_kind": "cv_candidate_box",
            "text_region_source": "cv_text_detection",
            "text_region_mask_path": None,
            "text_region_mask_bbox_xyxy": None,
            "match_status": "matched",
        }
    return {
        "text_region_kind": "unknown",
        "text_region_source": "unknown",
        "text_region_mask_path": None,
        "text_region_mask_bbox_xyxy": None,
        "match_status": payload.get("status"),
    }


def _ctd_text_region_contract(detection_strategy: str) -> dict:
    return {
        "text_region_user_strategy": detection_strategy,
        "upstream_text_region_source": "ctd_refined_mask_component",
        "ballonstranslator_detector_module": "ctd",
        "ballonstranslator_detector_class": "ComicTextDetector",
        "mask_matching_metric": "labelplus_point_to_mask_edge",
        "mask_matching_cardinality": "unique_component_claim",
    }


def _near_square_bbox(
    bbox: tuple[int, int, int, int],
    image_width: int,
    image_height: int,
) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = bbox
    width = x2 - x1
    height = y2 - y1
    target = max(width, height)
    return _expand_bbox_to_size(bbox, image_width, image_height, target, target)


def _expand_bbox_to_size(
    bbox: tuple[int, int, int, int],
    image_width: int,
    image_height: int,
    target_width: int,
    target_height: int,
) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = bbox
    center_x = (x1 + x2) / 2
    center_y = (y1 + y2) / 2
    new_x1 = int(round(center_x - target_width / 2))
    new_y1 = int(round(center_y - target_height / 2))
    new_x2 = new_x1 + target_width
    new_y2 = new_y1 + target_height
    if new_x1 < 0:
        new_x2 -= new_x1
        new_x1 = 0
    if new_y1 < 0:
        new_y2 -= new_y1
        new_y1 = 0
    if new_x2 > image_width:
        shift = new_x2 - image_width
        new_x1 = max(0, new_x1 - shift)
        new_x2 = image_width
    if new_y2 > image_height:
        shift = new_y2 - image_height
        new_y1 = max(0, new_y1 - shift)
        new_y2 = image_height
    return new_x1, new_y1, new_x2, new_y2


def _lettering_route_payload(payload: dict, detection_strategy: str) -> dict:
    if _is_comic_text_bubble_strategy(detection_strategy) and payload.get("status") == "ok":
        return {
            "route": "comic_text_bubble_detect_then_configured_cleanup",
            "text_region_source": "comic_text_bubble_rtdetrv2",
            "text_region_user_strategy": detection_strategy,
            "repair_method": "configured_by_phase6",
            "requires_mimo_locator": False,
            "requires_gpt_image2_replacement": False,
        }
    if _is_cta_mask_strategy(detection_strategy) and payload.get("status") == "ok":
        return {
            "route": "cta_mask_lama_large_512px",
            "text_region_source": "ctd_refined_mask_component",
            "text_region_user_strategy": detection_strategy,
            "ballonstranslator_detector_module": "ctd",
            "repair_method": "lama_large_512px",
            "requires_mimo_locator": False,
            "requires_gpt_image2_replacement": False,
        }
    if payload.get("status") == "fallback_required":
        upstream_source = None
        if _is_cta_mask_strategy(detection_strategy):
            upstream_source = "ctd_refined_mask_component"
        elif _is_comic_text_bubble_strategy(detection_strategy):
            upstream_source = "comic_text_bubble_rtdetrv2"
        return {
            "route": "mimo_locator_gpt_image2_masked_edit",
            "text_region_source": "mimo_vision_model",
            "text_region_user_strategy": detection_strategy,
            "upstream_text_region_source": upstream_source,
            "repair_method": "gpt_image2_masked_edit",
            "requires_mimo_locator": True,
            "requires_gpt_image2_replacement": True,
        }
    return {
        "route": "cv_detect_then_configured_cleanup",
        "text_region_source": "cv_text_detection",
        "repair_method": "configured_by_phase6",
        "requires_mimo_locator": False,
        "requires_gpt_image2_replacement": False,
    }


def _add_derived_text_bboxes(payload: dict) -> tuple[tuple[int, int, int, int] | None, tuple[int, int, int, int] | None]:
    if payload.get("status") != "ok" or not payload.get("selected_text_box_xyxy"):
        payload["selected_text_full_xyxy"] = None
        payload["selected_text_body_xyxy"] = None
        return None, None

    if payload.get("detection_method") in {"cta_mask", "ctd_mask", "comic_rtdetrv2"}:
        bbox = tuple(int(value) for value in payload["selected_text_box_xyxy"])
        payload["selected_text_full_xyxy"] = list(bbox)
        payload["selected_text_body_xyxy"] = list(bbox)
        return bbox, bbox

    full_bbox = selected_text_bbox(payload)
    body_bbox = selected_text_body_bbox(payload)
    payload["selected_text_full_xyxy"] = list(full_bbox)
    payload["selected_text_body_xyxy"] = list(body_bbox)
    return full_bbox, body_bbox


def _point_to_bbox_distance(point_xy: tuple[int, int], bbox: tuple[int, int, int, int]) -> float:
    x, y = point_xy
    x1, y1, x2, y2 = bbox
    dx = max(x1 - x, x - x2, 0)
    dy = max(y1 - y, y - y2, 0)
    return float((dx * dx + dy * dy) ** 0.5)


def _write_manual_review_csv(output_path: Path, rows: list[dict]) -> None:
    fieldnames = [
        "record_id",
        "status",
        "confidence",
        "failure_reason",
        "candidate_count",
        "selected_text_box_xyxy",
        "selected_text_full_xyxy",
        "selected_text_body_xyxy",
        "mask_match_status",
        "mask_match_nearest_component_id",
        "mask_match_nearest_edge_distance_px",
        "mask_match_within_threshold_count",
        "comic_match_status",
        "comic_match_label",
        "comic_match_score",
        "comic_match_distance_px",
        "comic_match_threshold_px",
        "debug_image_path",
        "manual_decision",
        "review_notes",
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(_manual_review_row(row))


def _manual_review_row(row: dict) -> dict:
    diagnostics = row.get("cta_match_diagnostics") or row.get("ctd_match_diagnostics") or {}
    comic_match = row.get("comic_text_bubble_match") or {}
    return {
        "record_id": row["record_id"],
        "status": row["status"],
        "confidence": row["confidence"],
        "failure_reason": row.get("failure_reason") or "",
        "candidate_count": len(row.get("candidate_boxes", [])),
        "selected_text_box_xyxy": json.dumps(row.get("selected_text_box_xyxy"), ensure_ascii=False),
        "selected_text_full_xyxy": json.dumps(row.get("selected_text_full_xyxy"), ensure_ascii=False),
        "selected_text_body_xyxy": json.dumps(row.get("selected_text_body_xyxy"), ensure_ascii=False),
        "mask_match_status": diagnostics.get("match_status", ""),
        "mask_match_nearest_component_id": diagnostics.get("nearest_component_id", ""),
        "mask_match_nearest_edge_distance_px": _csv_value(diagnostics.get("nearest_edge_distance_px")),
        "mask_match_within_threshold_count": _csv_value(diagnostics.get("within_threshold_count")),
        "comic_match_status": comic_match.get("status", ""),
        "comic_match_label": comic_match.get("selected_label", ""),
        "comic_match_score": _csv_value(comic_match.get("selected_score")),
        "comic_match_distance_px": _csv_value(comic_match.get("distance_px")),
        "comic_match_threshold_px": _csv_value(comic_match.get("threshold_px")),
        "debug_image_path": row.get("debug_image_path", ""),
        "manual_decision": "",
        "review_notes": "",
    }


def _csv_value(value: object) -> str:
    if value is None:
        return ""
    return str(value)


def _write_phase2_report(
    output_path: Path,
    labelplus_file: Path,
    sample_count: int,
    ok_count: int,
    failed_count: int,
    radius_x: int,
    radius_y: int,
    detection_strategy: str,
    call_model_text_recognition: bool = False,
    comic_detector_model_path: str | Path | None = None,
    comic_detector_conf_threshold: float | None = None,
    comic_detector_max_distance_px: float | None = None,
) -> None:
    strategy_notes = _phase2_strategy_notes(detection_strategy)
    detector_notes = _phase2_detector_notes(
        detection_strategy,
        comic_detector_model_path,
        comic_detector_conf_threshold,
        comic_detector_max_distance_px,
    )
    artifacts = _phase2_artifact_lines(detection_strategy)
    lines = [
        "# Phase 2 Detection Report",
        "",
        f"LabelPlus file: `{labelplus_file}`",
        "",
        "## Summary",
        "",
        f"- Sample records: {sample_count}",
        f"- Detected records: {ok_count}",
        f"- Failed records: {failed_count}",
        f"- Search radius: `{radius_x} x {radius_y}`",
        f"- Detection strategy: `{detection_strategy}`",
        f"- Direct model text-region recognition: `{call_model_text_recognition}`",
        *detector_notes,
        *strategy_notes,
        "",
        "## Generated Artifacts",
        "",
        *artifacts,
        "",
        *_phase2_row_notes(detection_strategy),
        *_phase2_manual_review_notes(detection_strategy),
        "",
        "Debug overlay colors: raw selected box = red, full text evidence box = green, body text box = purple.",
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _phase2_strategy_notes(detection_strategy: str) -> list[str]:
    if _is_comic_text_bubble_strategy(detection_strategy):
        return [
            "- Comic text/bubble RT-DETRv2: directly runs the local ONNX detector and matches LabelPlus points to `text_bubble` / `text_free` boxes.",
            "- Detector labels: `bubble`, `text_bubble`, `text_free`; only text labels are selected as Phase 2 text regions.",
        ]
    if _is_cta_mask_strategy(detection_strategy):
        return [
            "- CTA strategy note: `cta_mask` is the user-facing CTA-first route; the actual BallonsTranslator detector module is `ctd` / `ComicTextDetector`.",
            "- CTD mask matching: split `ctd-refined-mask.png` into connected components, then uniquely match LabelPlus points by point-to-mask-edge distance.",
        ]
    return ["- CV strategy note: legacy local connected-component text detection prototype."]


def _phase2_detector_notes(
    detection_strategy: str,
    comic_detector_model_path: str | Path | None,
    comic_detector_conf_threshold: float | None,
    comic_detector_max_distance_px: float | None,
) -> list[str]:
    if not _is_comic_text_bubble_strategy(detection_strategy):
        return []
    return [
        f"- Comic detector model: `{comic_detector_model_path or DEFAULT_COMIC_DETECTOR_MODEL_PATH}`",
        f"- Comic detector confidence threshold: `{comic_detector_conf_threshold}`",
        f"- Comic detector max match distance: `{comic_detector_max_distance_px}px`",
    ]


def _phase2_artifact_lines(detection_strategy: str) -> list[str]:
    lines = [
        "- `detections.jsonl`",
        "- `debug/detection/*.png`",
        "- `reports/manual-review.csv`",
    ]
    if _is_cta_mask_strategy(detection_strategy):
        lines.insert(2, "- `debug/ctd_masks/<page>/cta-closed-mask-components.json`")
        lines.insert(3, "- `debug/ctd_masks/<page>/ctd-mask-edge-distances.jsonl`")
    return lines


def _phase2_row_notes(detection_strategy: str) -> list[str]:
    if _is_comic_text_bubble_strategy(detection_strategy):
        return [
            "Comic RT-DETRv2 rows include `comic_text_bubble_detections` and `comic_text_bubble_match` with all detector boxes, nearest candidates, and selected class/score.",
        ]
    if _is_cta_mask_strategy(detection_strategy):
        return [
            "CTA/CTD detection rows include `cta_match_diagnostics` / `ctd_match_diagnostics` with nearest mask candidates, threshold counts, and the selected component id.",
        ]
    return []


def _phase2_manual_review_notes(detection_strategy: str) -> list[str]:
    if _is_comic_text_bubble_strategy(detection_strategy):
        return [
            "`manual-review.csv` repeats the selected comic detector label, score, and LabelPlus-point distance for fast spreadsheet triage.",
        ]
    if _is_cta_mask_strategy(detection_strategy):
        return [
            "`manual-review.csv` repeats the nearest mask-match fields for fast spreadsheet triage.",
        ]
    return [
        "`manual-review.csv` repeats selected text boxes and debug image paths for fast spreadsheet triage.",
    ]
