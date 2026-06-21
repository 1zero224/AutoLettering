import json
from pathlib import Path

from PIL import Image

from autolettering.labelplus.debug_draw import draw_label_point_pages
from autolettering.labelplus.manifest import project_manifest_to_dict, write_project_manifest
from autolettering.labelplus.models import (
    ManifestImage,
    ManifestLabel,
    MissingImage,
    ProjectManifest,
)


def _sample_manifest(tmp_path: Path) -> ProjectManifest:
    image_path = tmp_path / "page_01.png"
    Image.new("RGB", (100, 200), "white").save(image_path)
    return ProjectManifest(
        project_root=tmp_path,
        labelplus_file=tmp_path / "翻译_0.txt",
        version=(1, 0),
        groups=["框内", "框外"],
        images=[
            ManifestImage(
                image_name="page_01.png",
                image_path=image_path,
                width=100,
                height=200,
                labels=[
                    ManifestLabel(
                        id="page_01.png#1",
                        page_index=1,
                        record_index=1,
                        x_ratio=0.25,
                        y_ratio=0.5,
                        x_px=25,
                        y_px=100,
                        group_id=1,
                        group_name="框内",
                        translated_text="第一条",
                    )
                ],
            )
        ],
        missing_images=[
            MissingImage(
                image_name="missing.png",
                page_index=2,
                label_count=1,
                reason="declared in LabelPlus text but not found under project directory",
            )
        ],
    )


def test_write_project_manifest_serializes_paths_and_counts(tmp_path: Path):
    manifest = _sample_manifest(tmp_path)
    output_path = tmp_path / "manifest.json"

    write_project_manifest(manifest, output_path)

    loaded = json.loads(output_path.read_text(encoding="utf-8"))
    assert loaded["project_root"] == str(tmp_path)
    assert loaded["labelplus_file"] == str(tmp_path / "翻译_0.txt")
    assert loaded["summary"] == {
        "available_image_count": 1,
        "missing_image_count": 1,
        "label_count": 1,
    }
    assert loaded["images"][0]["labels"][0]["id"] == "page_01.png#1"
    assert loaded["missing_images"][0]["image_name"] == "missing.png"

    as_dict = project_manifest_to_dict(manifest)
    assert as_dict["version"] == [1, 0]


def test_draw_label_point_pages_outputs_nonblank_debug_image(tmp_path: Path):
    manifest = _sample_manifest(tmp_path)
    output_dir = tmp_path / "debug"

    output_paths = draw_label_point_pages(manifest, output_dir)

    assert output_paths == [output_dir / "page_01.png"]
    assert output_paths[0].exists()

    debug_image = Image.open(output_paths[0]).convert("RGB")
    assert debug_image.size == (100, 200)
    assert debug_image.getpixel((25, 100)) != (255, 255, 255)

