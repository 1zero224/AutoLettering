from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .models import ProjectManifest


def project_manifest_to_dict(manifest: ProjectManifest) -> dict[str, Any]:
    images = []
    label_count = 0
    for image in manifest.images:
        labels = [asdict(label) for label in image.labels]
        label_count += len(labels)
        images.append(
            {
                "image_name": image.image_name,
                "image_path": str(image.image_path),
                "width": image.width,
                "height": image.height,
                "labels": labels,
            }
        )

    missing_images = [asdict(image) for image in manifest.missing_images]

    return {
        "project_root": str(manifest.project_root),
        "labelplus_file": str(manifest.labelplus_file),
        "version": list(manifest.version),
        "groups": manifest.groups,
        "summary": {
            "available_image_count": len(manifest.images),
            "missing_image_count": len(manifest.missing_images),
            "label_count": label_count,
        },
        "images": images,
        "missing_images": missing_images,
    }


def write_project_manifest(manifest: ProjectManifest, output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(project_manifest_to_dict(manifest), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path
