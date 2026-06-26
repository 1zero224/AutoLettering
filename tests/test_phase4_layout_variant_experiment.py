import importlib.util
import sys
from pathlib import Path

from PIL import Image, ImageDraw

from autolettering.experiment_grid import near_square_columns


MODULE_PATH = Path(__file__).resolve().parents[1] / "experiments" / "phase4_layout_variant_experiment.py"
SPEC = importlib.util.spec_from_file_location("phase4_layout_variant_experiment", MODULE_PATH)
phase4_layout_variant_experiment = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = phase4_layout_variant_experiment
SPEC.loader.exec_module(phase4_layout_variant_experiment)


def test_near_square_columns_handles_nine_layout_variants():
    assert near_square_columns(1) == 1
    assert near_square_columns(5) == 3
    assert near_square_columns(9) == 3


def test_default_variants_keep_vertical_top_align_and_no_rotation():
    variants = phase4_layout_variant_experiment.DEFAULT_VARIANTS

    assert len(variants) == 9
    assert variants[0].name == "current_fs33_s4"
    assert {variant.vertical_align for variant in variants} == {"top"}
    assert {variant.angle_degrees for variant in variants} == {0.0}


def test_cleanup_crop_path_ignores_rejected_gpt_replacement():
    cleanup = {
        "cleaned_crop_path": "cleaned.png",
        "replacement_method": "gpt_image2_masked_edit",
        "replacement_crop_path": "bad-gpt.png",
        "gpt_replacement_quality": {"accepted": False, "failure_reason": "quality_rejected"},
    }

    assert phase4_layout_variant_experiment._cleanup_crop_path(cleanup) == "cleaned.png"


def test_run_variants_writes_text_layers_final_crops_and_grid(tmp_path: Path):
    page_path = _write_page(tmp_path / "page.png")
    cleaned_crop_path = _write_cleaned_crop(tmp_path / "cleaned.png")
    font_path = _font_path()
    detection = {
        "record_id": "page.png#1",
        "status": "ok",
        "image_path": str(page_path),
        "translated_text": "-快看\n接下来登场的乐队\n竟然！",
    }
    cleanup = {
        "record_id": "page.png#1",
        "status": "cleaned",
        "cleanup": {
            "bbox": [10, 10, 90, 130],
            "cleaned_crop_path": str(cleaned_crop_path),
            "layout_text_bbox": [40, 10, 80, 110],
        },
    }
    layout = {
        "record_id": "page.png#1",
        "status": "layout_generated",
        "layout": {"target_bbox": [40, 10, 80, 110]},
    }
    font = {
        "record_id": "page.png#1",
        "status": "selected",
        "selected_font": {"path": str(font_path)},
    }
    specs = [phase4_layout_variant_experiment.LayoutVariantSpec("candidate", "-快看\n接下来", 16, 2)]

    rows = phase4_layout_variant_experiment.run_variants(tmp_path / "run", detection, cleanup, layout, font, specs)
    grid = phase4_layout_variant_experiment.write_variant_grid(tmp_path / "run" / "visuals" / "grid.png", rows)

    assert grid.exists()
    assert rows[0]["status"] == "ok"
    assert rows[0]["layout"]["orientation"] == "vertical"
    assert rows[0]["layout"]["angle_degrees"] == 0.0
    assert rows[0]["layout"]["alignment"]["ink_bbox"][1] == 0
    assert Path(rows[0]["paths"]["text_layer_path"]).exists()
    assert Path(rows[0]["paths"]["final_crop_path"]).exists()


def _write_page(path: Path) -> Path:
    image = Image.new("RGB", (120, 150), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((10, 10, 90, 130), outline="black", width=2)
    draw.text((16, 40), "neighbor", fill="black")
    image.save(path)
    return path


def _write_cleaned_crop(path: Path) -> Path:
    image = Image.new("RGB", (80, 120), "white")
    ImageDraw.Draw(image).line((0, 110, 80, 110), fill="black", width=2)
    image.save(path)
    return path


def _font_path() -> Path:
    for name in ["msyh.ttc", "simsun.ttc", "arial.ttf"]:
        path = Path("C:/Windows/Fonts") / name
        if path.exists():
            return path
    return sorted(Path("C:/Windows/Fonts").glob("*.ttf"))[0]
