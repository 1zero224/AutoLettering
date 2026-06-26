from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
from PIL import Image


LARGE_FLAT_OVERLAY_ISSUE = "local_artifact_large_flat_overlay"
UNMEASURED_INPUT_ISSUE = "local_artifact_inputs_missing"


@dataclass(frozen=True)
class GptArtifactGateResult:
    passed: bool | None
    issues: list[str]
    metrics: dict


def evaluate_gpt_replacement_artifacts(
    cleaned_crop_path: str | Path | None,
    replacement_crop_path: str | Path | None,
    path_roots: list[str | Path] | None = None,
) -> GptArtifactGateResult:
    cleaned_path = _resolve_existing_path(cleaned_crop_path, path_roots)
    replacement_path = _resolve_existing_path(replacement_crop_path, path_roots)
    if cleaned_path is None or replacement_path is None:
        return GptArtifactGateResult(
            passed=None,
            issues=[UNMEASURED_INPUT_ISSUE],
            metrics={
                "status": "not_evaluated",
                "cleaned_crop_path_exists": cleaned_path is not None,
                "replacement_crop_path_exists": replacement_path is not None,
            },
        )
    try:
        with Image.open(cleaned_path) as cleaned_image, Image.open(replacement_path) as replacement_image:
            cleaned = cleaned_image.convert("L")
            replacement = replacement_image.convert("L")
            if cleaned.size != replacement.size:
                cleaned = cleaned.resize(replacement.size, Image.Resampling.BILINEAR)
            result = _evaluate_grayscale_pair(cleaned, replacement)
    except (OSError, ValueError) as exc:
        return GptArtifactGateResult(
            passed=None,
            issues=[UNMEASURED_INPUT_ISSUE],
            metrics={"status": "not_evaluated", "error_type": type(exc).__name__},
        )
    return result


def gpt_artifact_payload(result: GptArtifactGateResult) -> dict:
    return {
        "local_artifact_gate_passed": result.passed,
        "local_artifact_issues": list(result.issues),
        "local_artifact_metrics": dict(result.metrics),
    }


def local_artifact_gate_passes(row: dict) -> bool:
    passed = row.get("local_artifact_gate_passed")
    return passed is not False


def local_artifact_gate_for_quality_row(row: dict, cleanup: dict | None = None) -> GptArtifactGateResult:
    if "local_artifact_gate_passed" in row:
        return GptArtifactGateResult(
            passed=row.get("local_artifact_gate_passed"),
            issues=list(row.get("local_artifact_issues") or []),
            metrics=dict(row.get("local_artifact_metrics") or {}),
        )
    cleanup = cleanup or {}
    cleaned_path = row.get("source_cleaned_crop_path") or cleanup.get("cleaned_crop_path")
    replacement_path = row.get("source_replacement_crop_path") or row.get("replacement_crop_path") or cleanup.get("replacement_crop_path")
    return evaluate_gpt_replacement_artifacts(cleaned_path, replacement_path)


def _evaluate_grayscale_pair(cleaned: Image.Image, replacement: Image.Image) -> GptArtifactGateResult:
    cleaned_array = np.asarray(cleaned, dtype=np.int16)
    replacement_array = np.asarray(replacement, dtype=np.int16)
    darken_mask = (cleaned_array - replacement_array >= 45) & (replacement_array < 220)
    largest = _largest_component(darken_mask)
    total_pixels = max(1, int(darken_mask.size))
    area_ratio = largest["area"] / total_pixels
    issues: list[str] = []
    if _is_large_flat_overlay(largest, area_ratio):
        issues.append(LARGE_FLAT_OVERLAY_ISSUE)
    metrics = {
        "status": "evaluated",
        "image_width": int(replacement.width),
        "image_height": int(replacement.height),
        "darken_pixel_ratio": float(darken_mask.mean()),
        "largest_darken_component_area": int(largest["area"]),
        "largest_darken_component_area_ratio": float(area_ratio),
        "largest_darken_component_bbox": list(largest["bbox"]),
        "largest_darken_component_fill_ratio": float(largest["fill_ratio"]),
    }
    return GptArtifactGateResult(passed=not issues, issues=issues, metrics=metrics)


def _is_large_flat_overlay(component: dict, area_ratio: float) -> bool:
    x1, y1, x2, y2 = component["bbox"]
    width = x2 - x1
    height = y2 - y1
    return (
        area_ratio >= 0.035
        and component["fill_ratio"] >= 0.85
        and width >= 20
        and height >= 40
    )


def _largest_component(mask: np.ndarray) -> dict:
    height, width = mask.shape
    seen = np.zeros(mask.shape, dtype=bool)
    best = {"area": 0, "bbox": (0, 0, 0, 0), "fill_ratio": 0.0}
    for y in range(height):
        for x in range(width):
            if not mask[y, x] or seen[y, x]:
                continue
            component = _component_from(mask, seen, x, y)
            if component["area"] > best["area"]:
                best = component
    return best


def _component_from(mask: np.ndarray, seen: np.ndarray, start_x: int, start_y: int) -> dict:
    stack = [(start_x, start_y)]
    seen[start_y, start_x] = True
    area = 0
    min_x = max_x = start_x
    min_y = max_y = start_y
    while stack:
        x, y = stack.pop()
        area += 1
        min_x = min(min_x, x)
        max_x = max(max_x, x)
        min_y = min(min_y, y)
        max_y = max(max_y, y)
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < mask.shape[1] and 0 <= ny < mask.shape[0] and mask[ny, nx] and not seen[ny, nx]:
                seen[ny, nx] = True
                stack.append((nx, ny))
    bbox = (int(min_x), int(min_y), int(max_x + 1), int(max_y + 1))
    bbox_area = max(1, (bbox[2] - bbox[0]) * (bbox[3] - bbox[1]))
    return {"area": int(area), "bbox": bbox, "fill_ratio": float(area / bbox_area)}


def _resolve_existing_path(path: str | Path | None, path_roots: list[str | Path] | None) -> Path | None:
    if not path:
        return None
    candidate = Path(path)
    if candidate.exists():
        return candidate
    for root in path_roots or []:
        rooted = Path(root) / candidate
        if rooted.exists():
            return rooted
    return None
