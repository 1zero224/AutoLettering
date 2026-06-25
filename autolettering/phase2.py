from __future__ import annotations

import csv
import json
from collections.abc import Iterable
from pathlib import Path

from .detection.cv_text import detect_text_region, detection_result_to_dict, draw_detection_debug
from .detection.ctd_masks import (
    CtdMaskComponent,
    CtdMaskMatch,
    assign_labelplus_points_to_ctd_masks,
    _ballonstranslator_ctd_config,
    detect_ctd_mask_components_for_image,
)
from .detection.models import CandidateBox, DetectionResult
from .detection.regions import build_search_region
from .labelplus.models import ManifestImage, ManifestLabel
from .labelplus.parser import parse_labelplus_project
from .phase1 import _select_sample_records, _timestamp_run_id
from .record_selection import normalize_record_ids
from .text_bbox import selected_text_bbox
from .text_body_bbox import selected_text_body_bbox


def run_phase2(
    labelplus_file: str | Path,
    output_root: str | Path = "outputs/runs",
    run_id: str | None = None,
    sample_limit: int = 30,
    radius_x: int = 220,
    radius_y: int = 180,
    record_ids: Iterable[str] | None = None,
    detection_strategy: str = "cta_mask",
    ctd_max_edge_distance_px: float = 20.0,
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
) -> tuple[int, int]:
    ok_count = failed_count = 0
    rows: list[dict] = []
    ctd_matches = (
        _ctd_matches_by_record(run_dir, selected_records, ctd_max_edge_distance_px)
        if _is_cta_mask_strategy(detection_strategy)
        else {}
    )
    with (run_dir / "detections.jsonl").open("w", encoding="utf-8", newline="\n") as handle:
        for image, label in selected_records:
            payload = _detect_record(
                run_dir,
                image,
                label,
                radius_x,
                radius_y,
                detection_strategy=detection_strategy,
                ctd_match=ctd_matches.get(label.id),
                ctd_max_edge_distance_px=ctd_max_edge_distance_px,
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
    ctd_max_edge_distance_px: float | None = None,
) -> dict:
    result = _detect_with_strategy(
        image,
        label,
        radius_x,
        radius_y,
        detection_strategy=detection_strategy,
        ctd_match=ctd_match,
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
    if result.status == "fallback_required":
        payload["fallback"] = _mimo_gpt_fallback_payload(
            label,
            image.width,
            image.height,
            radius_x,
            radius_y,
            payload.get("failure_reason"),
            ctd_max_edge_distance_px=ctd_max_edge_distance_px,
        )
    payload["lettering_route"] = _lettering_route_payload(payload, detection_strategy)
    payload.update(_text_region_payload(payload, detection_strategy))
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


def _detect_with_strategy(
    image: ManifestImage,
    label: ManifestLabel,
    radius_x: int,
    radius_y: int,
    detection_strategy: str,
    ctd_match: CtdMaskMatch | None,
) -> DetectionResult:
    if detection_strategy == "cv":
        return detect_text_region(image.image_path, label, image.width, image.height, radius_x, radius_y)
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


def _ctd_matches_by_record(
    run_dir: Path,
    selected_records: list[tuple[ManifestImage, ManifestLabel]],
    max_edge_distance_px: float,
) -> dict[str, CtdMaskMatch]:
    matches: dict[str, CtdMaskMatch] = {}
    for image, labels in _group_labels_by_image(selected_records):
        components = _detect_page_components(run_dir, image)
        matches.update(assign_labelplus_points_to_ctd_masks(labels, components, max_edge_distance_px=max_edge_distance_px))
    return matches


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
    output_dir = run_dir / "debug" / "ctd_masks" / Path(image.image_name).stem
    _write_json(output_dir / "ctd-config.json", _ballonstranslator_ctd_config(Path("BallonsTranslator")))
    return detect_ctd_mask_components_for_image(image.image_path, output_dir)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


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
    if strategy == "ctd_mask":
        return "ctd_mask"
    if strategy in {"cta_mask", "cta"}:
        return "cta_mask"
    if strategy == "cv":
        return "cv"
    raise ValueError(f"unsupported_detection_strategy:{strategy}")


def _is_cta_mask_strategy(strategy: str) -> bool:
    return strategy in {"cta_mask", "ctd_mask"}


def _mimo_gpt_fallback_payload(
    label: ManifestLabel,
    image_width: int,
    image_height: int,
    radius_x: int,
    radius_y: int,
    trigger_reason: str | None = None,
    ctd_max_edge_distance_px: float | None = None,
) -> dict:
    source_bbox = build_search_region(label.x_px, label.y_px, image_width, image_height, radius_x, radius_y)
    context_bbox = _near_square_bbox(source_bbox, image_width, image_height)
    return {
        "method": "mimo_crop_then_gpt_image2_masked_edit",
        "context_bbox_xyxy": list(context_bbox),
        "source_context_bbox_xyxy": list(source_bbox),
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


def _text_region_payload(payload: dict, detection_strategy: str) -> dict:
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
        return {
            "route": "mimo_locator_gpt_image2_masked_edit",
            "text_region_source": "mimo_vision_model",
            "text_region_user_strategy": detection_strategy,
            "upstream_text_region_source": "ctd_refined_mask_component" if _is_cta_mask_strategy(detection_strategy) else None,
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

    if payload.get("detection_method") in {"cta_mask", "ctd_mask"}:
        bbox = tuple(int(value) for value in payload["selected_text_box_xyxy"])
        payload["selected_text_full_xyxy"] = list(bbox)
        payload["selected_text_body_xyxy"] = list(bbox)
        return bbox, bbox

    full_bbox = selected_text_bbox(payload)
    body_bbox = selected_text_body_bbox(payload)
    payload["selected_text_full_xyxy"] = list(full_bbox)
    payload["selected_text_body_xyxy"] = list(body_bbox)
    return full_bbox, body_bbox


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
    return {
        "record_id": row["record_id"],
        "status": row["status"],
        "confidence": row["confidence"],
        "failure_reason": row.get("failure_reason") or "",
        "candidate_count": len(row.get("candidate_boxes", [])),
        "selected_text_box_xyxy": json.dumps(row.get("selected_text_box_xyxy"), ensure_ascii=False),
        "selected_text_full_xyxy": json.dumps(row.get("selected_text_full_xyxy"), ensure_ascii=False),
        "selected_text_body_xyxy": json.dumps(row.get("selected_text_body_xyxy"), ensure_ascii=False),
        "debug_image_path": row.get("debug_image_path", ""),
        "manual_decision": "",
        "review_notes": "",
    }


def _write_phase2_report(
    output_path: Path,
    labelplus_file: Path,
    sample_count: int,
    ok_count: int,
    failed_count: int,
    radius_x: int,
    radius_y: int,
    detection_strategy: str,
) -> None:
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
        "- CTA strategy note: `cta_mask` is the user-facing CTA-first route; the actual BallonsTranslator detector module is `ctd` / `ComicTextDetector`.",
        "- CTD mask matching: split `ctd-refined-mask.png` into connected components, then uniquely match LabelPlus points by point-to-mask-edge distance.",
        "",
        "## Generated Artifacts",
        "",
        "- `detections.jsonl`",
        "- `debug/detection/*.png`",
        "- `reports/manual-review.csv`",
        "",
        "Debug overlay colors: raw selected box = red, full text evidence box = green, body text box = purple.",
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
