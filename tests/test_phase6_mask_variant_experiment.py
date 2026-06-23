import importlib.util
import inspect
from pathlib import Path

from PIL import Image, ImageDraw

import autolettering.phase6


MODULE_PATH = Path(__file__).resolve().parents[1] / "experiments" / "phase6_mask_variant_experiment.py"
SPEC = importlib.util.spec_from_file_location("phase6_mask_variant_experiment", MODULE_PATH)
phase6_mask_variant_experiment = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(phase6_mask_variant_experiment)


def test_near_square_columns_avoids_long_strip():
    assert phase6_mask_variant_experiment.near_square_columns(1) == 1
    assert phase6_mask_variant_experiment.near_square_columns(5) == 2
    assert phase6_mask_variant_experiment.near_square_columns(7) == 3
    assert phase6_mask_variant_experiment.near_square_columns(13) == 4


def test_experiment_defaults_avoid_duplicate_hybrid_mask_variant():
    assert "hybrid_rect_expand2_text_t210_d5" not in phase6_mask_variant_experiment.DEFAULT_VARIANTS
    assert "rect_expand2" in phase6_mask_variant_experiment.DEFAULT_VARIANTS


def test_experiment_is_not_imported_by_default_phase6_pipeline():
    source = inspect.getsource(autolettering.phase6)

    assert "phase6_mask_variant_experiment" not in source


def test_run_variants_writes_masks_overlays_and_cleaned_images(tmp_path: Path, monkeypatch):
    image_path = _write_sample_page(tmp_path / "page.png")
    record = {
        "record_id": "page.png#1",
        "image_path": str(image_path),
        "selected_text_box_xyxy": [80, 30, 120, 110],
        "selected_text_full_xyxy": [50, 25, 125, 130],
        "candidate_boxes": [
            {"xyxy": [80, 30, 120, 110], "score": 0.95, "polarity": "dark_on_light"},
            {"xyxy": [50, 25, 75, 120], "score": 0.9, "polarity": "dark_on_light"},
        ],
    }

    def fake_inpaint(crop, mask, method, iterations=80):
        assert method == "bt_lama_large"
        cleaned = Image.new("RGB", crop.size, "white")
        return "fake_lama", cleaned

    monkeypatch.setattr(phase6_mask_variant_experiment, "inpaint_crop", fake_inpaint)

    rows = phase6_mask_variant_experiment.run_variants(
        tmp_path / "run",
        record,
        ["tight_t185_d3", "rect_expand2"],
        "bt_lama_large",
    )
    sheet = phase6_mask_variant_experiment.write_variant_grid(tmp_path / "run" / "visuals" / "grid.png", rows)

    assert sheet.exists()
    assert [row["status"] for row in rows] == ["ok", "ok"]
    for row in rows:
        assert Path(row["mask_path"]).exists()
        assert Path(row["mask_overlay_path"]).exists()
        assert Path(row["cleaned_path"]).exists()
        assert Path(row["before_after_path"]).exists()
        assert row["mask_pixel_count"] > 0


def test_parameterized_tight_variant_is_supported():
    image = Image.new("RGB", (80, 80), "white")
    ImageDraw.Draw(image).rectangle((32, 20, 48, 60), fill=(160, 160, 160))

    mask = phase6_mask_variant_experiment.build_variant_mask(
        image,
        text_bbox=(10, 10, 70, 70),
        mask_bbox=(30, 18, 52, 62),
        variant="tight_t170_d1",
    )

    assert mask.size == (60, 60)
    assert mask.getpixel((30, 30)) == 255
    assert mask.getpixel((2, 2)) == 0


def _write_sample_page(path: Path) -> Path:
    image = Image.new("RGB", (180, 180), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((82, 35, 115, 105), fill="black")
    draw.rectangle((55, 40, 70, 118), fill="black")
    draw.line((30, 140, 150, 140), fill="black", width=2)
    image.save(path)
    return path
