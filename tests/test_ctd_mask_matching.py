from pathlib import Path

from PIL import Image, ImageDraw

from autolettering.detection.ctd_masks import (
    CtdMaskComponent,
    _ballonstranslator_ctd_config,
    assign_labelplus_points_to_ctd_masks,
    split_mask_components,
)
from autolettering.labelplus.models import ManifestLabel


def _label(record_index: int, x: int, y: int) -> ManifestLabel:
    return ManifestLabel(
        id=f"page.png#{record_index}",
        page_index=1,
        record_index=record_index,
        x_ratio=x / 300,
        y_ratio=y / 300,
        x_px=x,
        y_px=y,
        group_id=1,
        group_name="框外",
        translated_text=f"译文{record_index}",
    )


def _mask(path: Path) -> Path:
    image = Image.new("L", (300, 220), 0)
    draw = ImageDraw.Draw(image)
    draw.rectangle((40, 30, 100, 120), fill=255)
    draw.rectangle((190, 50, 250, 150), fill=255)
    image.save(path)
    return path


def test_split_mask_components_returns_closed_components_with_bboxes(tmp_path: Path):
    components = split_mask_components(_mask(tmp_path / "mask.png"), min_area=20)

    assert [component.bbox_xyxy for component in components] == [(40, 30, 101, 121), (190, 50, 251, 151)]
    assert all(component.area_px > 1000 for component in components)
    assert all(component.mask_path.exists() for component in components)


def test_split_mask_components_uses_8_connected_diagonal_pixels(tmp_path: Path):
    image = Image.new("L", (40, 40), 0)
    draw = ImageDraw.Draw(image)
    draw.rectangle((10, 10, 14, 14), fill=255)
    draw.rectangle((15, 15, 19, 19), fill=255)
    mask_path = tmp_path / "diagonal-mask.png"
    image.save(mask_path)

    components = split_mask_components(mask_path, min_area=5)

    assert len(components) == 1
    assert components[0].bbox_xyxy == (10, 10, 20, 20)


def test_assign_labelplus_points_to_ctd_masks_uses_edge_distance_and_unique_matching(tmp_path: Path):
    components = split_mask_components(_mask(tmp_path / "mask.png"), min_area=20)
    labels = [_label(1, 38, 80), _label(2, 253, 101)]

    matches = assign_labelplus_points_to_ctd_masks(labels, components, max_edge_distance_px=8)

    assert matches["page.png#1"].status == "matched"
    assert matches["page.png#1"].component_id == components[0].component_id
    assert matches["page.png#1"].distance_px == 2
    assert matches["page.png#1"].bbox_xyxy == (40, 30, 101, 121)
    assert matches["page.png#2"].status == "matched"
    assert matches["page.png#2"].component_id == components[1].component_id
    assert matches["page.png#2"].distance_px == 2


def test_assign_labelplus_points_to_ctd_masks_uses_real_mask_edge_not_bbox_region(tmp_path: Path):
    image = Image.new("L", (160, 160), 0)
    draw = ImageDraw.Draw(image)
    draw.rectangle((30, 30, 130, 130), outline=255, width=6)
    mask_path = tmp_path / "hollow-mask.png"
    image.save(mask_path)
    components = split_mask_components(mask_path, min_area=20)
    labels = [_label(1, 80, 80)]

    matches = assign_labelplus_points_to_ctd_masks(labels, components, max_edge_distance_px=8)

    assert matches["page.png#1"].status == "fallback_required"
    assert matches["page.png#1"].failure_reason == "no_ctd_mask_within_threshold"


def test_assign_labelplus_points_to_ctd_masks_uses_edge_distance_even_inside_solid_mask(tmp_path: Path):
    image = Image.new("L", (160, 160), 0)
    ImageDraw.Draw(image).rectangle((30, 30, 130, 130), fill=255)
    mask_path = tmp_path / "solid-mask.png"
    image.save(mask_path)
    components = split_mask_components(mask_path, min_area=20)
    labels = [_label(1, 80, 80)]

    matches = assign_labelplus_points_to_ctd_masks(labels, components, max_edge_distance_px=8)

    assert matches["page.png#1"].status == "fallback_required"
    assert matches["page.png#1"].failure_reason == "no_ctd_mask_within_threshold"


def test_assign_labelplus_points_to_ctd_masks_merges_vertical_continuation_components(tmp_path: Path):
    components = [
        _component(tmp_path, "component-0001", (140, 20, 198, 276), 9000),
        _component(tmp_path, "component-0012", (144, 280, 194, 324), 1600),
        _component(tmp_path, "component-0016", (142, 325, 197, 430), 4800),
        _component(tmp_path, "component-0018", (144, 432, 194, 476), 1600),
        _component(tmp_path, "component-0020", (0, 440, 120, 560), 24000),
        _component(tmp_path, "component-0026", (141, 476, 197, 582), 5000),
    ]
    labels = [_label(1, 214, 103)]

    matches = assign_labelplus_points_to_ctd_masks(labels, components, max_edge_distance_px=16)

    match = matches["page.png#1"]
    assert match.status == "matched"
    assert match.component_id == "component-0001+component-0012+component-0016+component-0018+component-0026"
    assert match.bbox_xyxy == (140, 20, 198, 582)
    assert match.mask_path is not None
    assert match.mask_path.exists()
    with Image.open(match.mask_path) as mask:
        assert mask.getpixel((170, 40)) == 255
        assert mask.getpixel((170, 500)) == 255
        assert mask.getpixel((40, 500)) == 0


def test_assign_labelplus_points_to_ctd_masks_rejects_ambiguous_component_claims():
    components = [
        CtdMaskComponent(
            component_id="component-0001",
            bbox_xyxy=(40, 30, 101, 121),
            area_px=5551,
            centroid_xy=(70.0, 75.0),
            mask_path=Path("component.png"),
        )
    ]
    labels = [_label(1, 38, 80), _label(2, 42, 84)]

    matches = assign_labelplus_points_to_ctd_masks(labels, components, max_edge_distance_px=8)

    assert matches["page.png#1"].status == "matched"
    assert matches["page.png#2"].status == "fallback_required"
    assert matches["page.png#2"].failure_reason == "component_already_claimed"


def test_assign_labelplus_points_to_ctd_masks_falls_back_when_no_mask_is_close():
    components = [
        CtdMaskComponent(
            component_id="component-0001",
            bbox_xyxy=(40, 30, 101, 121),
            area_px=5551,
            centroid_xy=(70.0, 75.0),
            mask_path=Path("component.png"),
        )
    ]
    labels = [_label(1, 180, 190)]

    matches = assign_labelplus_points_to_ctd_masks(labels, components, max_edge_distance_px=8)

    assert matches["page.png#1"].status == "fallback_required"
    assert matches["page.png#1"].component_id is None
    assert matches["page.png#1"].failure_reason == "no_ctd_mask_within_threshold"


def test_ballonstranslator_ctd_config_reads_running_config(tmp_path: Path):
    root = tmp_path / "BallonsTranslator"
    config_dir = root / "config"
    config_dir.mkdir(parents=True)
    (config_dir / "config.json").write_text(
        """{"module":{"textdetector_params":{"ctd":{"detect_size":1280,"det_rearrange_max_batches":5,"device":"cpu","mask dilate size":3,"font size multiplier":1.2,"font size max":40,"font size min":8}}}}""",
        encoding="utf-8",
    )

    config = _ballonstranslator_ctd_config(root)

    assert config == {
        "device": "cpu",
        "detect_size": 1280,
        "det_rearrange_max_batches": 5,
        "mask dilate size": 3,
        "font size multiplier": 1.2,
        "font size max": 40,
        "font size min": 8,
    }


def _component(tmp_path: Path, component_id: str, bbox: tuple[int, int, int, int], area: int) -> CtdMaskComponent:
    image = Image.new("L", (240, 640), 0)
    ImageDraw.Draw(image).rectangle((bbox[0], bbox[1], bbox[2] - 1, bbox[3] - 1), fill=255)
    mask_path = tmp_path / f"{component_id}.png"
    image.save(mask_path)
    return CtdMaskComponent(
        component_id=component_id,
        bbox_xyxy=bbox,
        area_px=area,
        centroid_xy=((bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2),
        mask_path=mask_path,
    )
