from pathlib import Path

from PIL import Image

from autolettering.labelplus.parser import parse_labelplus_project, parse_labelplus_text


def test_parse_labelplus_text_maps_groups_and_multiline_records():
    text = """1,0
-
框内
框外
-
Comment

>>>>>>>>[page_01.png]<<<<<<<<
----------------[1]----------------[0.250,0.500,1]
第一行
第二行

----------------[2]----------------[0.750,0.125,2]
旁白
"""

    document = parse_labelplus_text(text, source_name="sample.txt")

    assert document.version == (1, 0)
    assert document.groups == ["框内", "框外"]
    assert len(document.pages) == 1
    assert document.pages[0].image_name == "page_01.png"
    assert len(document.pages[0].records) == 2

    first = document.pages[0].records[0]
    assert first.record_index == 1
    assert first.x_ratio == 0.25
    assert first.y_ratio == 0.5
    assert first.group_id == 1
    assert first.group_name == "框内"
    assert first.translated_text == "第一行\n第二行"

    second = document.pages[0].records[1]
    assert second.group_name == "框外"
    assert second.translated_text == "旁白"


def test_parse_labelplus_project_reports_image_dimensions_and_missing_images(tmp_path: Path):
    project_dir = tmp_path / "sample_project"
    project_dir.mkdir()
    labelplus_file = project_dir / "翻译_0.txt"
    image_path = project_dir / "page_01.png"

    Image.new("RGB", (100, 200), "white").save(image_path)
    labelplus_file.write_text(
        """1,0
-
框内
框外
-
Comment

>>>>>>>>[page_01.png]<<<<<<<<
----------------[1]----------------[0.250,0.500,1]
第一条

>>>>>>>>[missing.png]<<<<<<<<
----------------[1]----------------[0.100,0.200,2]
缺图条目
""",
        encoding="utf-8",
    )

    manifest = parse_labelplus_project(labelplus_file)

    assert manifest.labelplus_file == labelplus_file
    assert manifest.groups == ["框内", "框外"]
    assert len(manifest.images) == 1
    assert manifest.images[0].image_path == image_path
    assert manifest.images[0].width == 100
    assert manifest.images[0].height == 200
    assert manifest.images[0].labels[0].x_px == 25
    assert manifest.images[0].labels[0].y_px == 100

    assert len(manifest.missing_images) == 1
    assert manifest.missing_images[0].image_name == "missing.png"
    assert "not found" in manifest.missing_images[0].reason

