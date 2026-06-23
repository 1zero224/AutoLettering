import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "experiments" / "phase6_bt_method_grid.py"
SPEC = importlib.util.spec_from_file_location("phase6_bt_method_grid", MODULE_PATH)
phase6_bt_method_grid = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(phase6_bt_method_grid)


def test_bt_method_grid_defaults_use_ballonstranslator_method_names():
    assert phase6_bt_method_grid.INPAINT_METHODS == [
        "opencv-tela",
        "patchmatch",
        "aot",
        "lama_mpe",
        "lama_large_512px",
    ]


def test_bt_method_grid_routes_legacy_opencv_tela_alias(monkeypatch):
    calls = []

    monkeypatch.setattr(phase6_bt_method_grid, "_opencv_tela_bt", lambda crop, mask: calls.append((crop, mask)) or crop)

    crop = object()
    mask = object()
    method, result = phase6_bt_method_grid._inpaint_with_method(crop, mask, "opencv_tela")

    assert method == "bt_opencv-tela_actual_cv2_INPAINT_NS"
    assert result is crop
    assert calls == [(crop, mask)]


def test_bt_method_grid_canonicalizes_legacy_opencv_tela_output_label(tmp_path: Path, monkeypatch):
    crop_path = tmp_path / "crop.png"
    mask_path = tmp_path / "mask.png"

    def fake_inpaint(crop, mask, method):
        assert method == "opencv_tela"
        return "fake_opencv", crop

    monkeypatch.setattr(phase6_bt_method_grid, "_text_bbox", lambda record: (0, 0, 2, 2))
    monkeypatch.setattr(phase6_bt_method_grid, "_mask_bbox", lambda record: (0, 0, 2, 2))
    monkeypatch.setattr(phase6_bt_method_grid, "_local_text_mask", lambda source, target_bbox, mask_bbox: source.convert("L"))
    monkeypatch.setattr(phase6_bt_method_grid, "_inpaint_with_method", fake_inpaint)

    from PIL import Image

    Image.new("RGB", (2, 2), "white").save(crop_path)
    rows = phase6_bt_method_grid._run_inpainters(
        tmp_path,
        {"image_path": str(crop_path)},
        ["opencv_tela"],
    )

    assert rows[0]["method"] == "opencv-tela"
    assert Path(rows[0]["cleaned_path"]).parts[-2] == "opencv-tela"
    assert Path(rows[0]["mask_path"]) == tmp_path / "inpaint" / "_input" / "tight-text-mask.png"


def test_bt_method_grid_uses_near_square_columns_for_mimo_sheets(tmp_path: Path, monkeypatch):
    calls = []

    def fake_write_grid(output_path, tiles, columns):
        calls.append((output_path.name, len(tiles), columns))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"fake")
        return output_path

    monkeypatch.setattr(phase6_bt_method_grid, "_write_grid", fake_write_grid)
    monkeypatch.setattr(phase6_bt_method_grid, "_current_detector_tile", lambda run_dir, record: tmp_path / "current.png")
    monkeypatch.setattr(phase6_bt_method_grid, "near_square_columns", lambda count, cell_width, cell_height: 99 + count)

    phase6_bt_method_grid._write_detection_grid(
        tmp_path,
        {"image_path": "page.png"},
        [
            {"method": "ctd", "status": "ok", "overlay_path": tmp_path / "ctd.png"},
            {"method": "ysgyolo", "status": "failed"},
        ],
    )
    phase6_bt_method_grid._write_inpaint_grid(
        tmp_path,
        {},
        [
            {"method": "opencv-tela", "status": "ok", "input_crop_path": tmp_path / "input.png", "mask_path": tmp_path / "mask.png", "cleaned_path": tmp_path / "opencv.png"},
            {"method": "patchmatch", "status": "ok", "cleaned_path": tmp_path / "patchmatch.png"},
            {"method": "aot", "status": "failed"},
            {"method": "lama_mpe", "status": "ok", "cleaned_path": tmp_path / "lama-mpe.png"},
            {"method": "lama_large_512px", "status": "ok", "cleaned_path": tmp_path / "lama-large.png"},
        ],
    )

    assert calls == [
        ("detector-grid.png", 3, 102),
        ("inpaint-grid.png", 7, 106),
    ]
