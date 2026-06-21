import json
from pathlib import Path

from PIL import Image

from autolettering.layout.candidates import generate_line_break_candidates
from autolettering.layout.measure import measure_text_layout, search_fitting_layout
from autolettering.layout.render_text import render_layout_preview
from autolettering.phase4 import run_phase4


def test_generate_line_break_candidates_includes_single_line_and_wrapped_forms():
    candidates = generate_line_break_candidates("街头演出？", max_lines=3)

    assert "街头演出？" in candidates
    assert any("\n" in candidate for candidate in candidates)
    assert len(candidates) == len(set(candidates))


def test_search_fitting_layout_selects_largest_font_with_bounded_overflow(tmp_path: Path):
    font_path = _copy_font(tmp_path)

    result = search_fitting_layout(
        text="街头演出？",
        font_path=font_path,
        target_size=(150, 80),
        min_font_size=12,
        max_font_size=64,
        allow_overflow_ratio=0.05,
    )

    measured = measure_text_layout(result.line_breaks, font_path, result.font_size)
    assert result.orientation == "horizontal"
    assert result.font_size >= 12
    assert result.overflow_ratio <= 0.05
    assert measured.width <= int(150 * 1.05)
    assert measured.height <= int(80 * 1.05)


def test_render_layout_preview_writes_non_empty_transparent_png(tmp_path: Path):
    font_path = _copy_font(tmp_path)
    output_path = tmp_path / "preview.png"
    layout = search_fitting_layout("街头演出？", font_path, (160, 90), max_font_size=42)

    result = render_layout_preview(layout, font_path, output_path, canvas_size=(160, 90))

    assert result == output_path
    assert output_path.exists()
    with Image.open(output_path) as image:
        assert image.mode == "RGBA"
        assert image.getbbox() is not None


def test_run_phase4_writes_layout_results_and_previews(tmp_path: Path):
    font_path = _copy_font(tmp_path)
    phase3_run = tmp_path / "phase3-selection"
    phase3_run.mkdir()
    _write_font_selection(phase3_run / "font-selections.jsonl", font_path)

    run_dir = run_phase4(
        selection_run_dir=phase3_run,
        output_root=tmp_path / "outputs",
        run_id="phase4-test",
        sample_limit=1,
    )

    rows = _read_jsonl(run_dir / "layout-results.jsonl")
    assert rows[0]["record_id"] == "page.png#1"
    assert rows[0]["status"] == "layout_generated"
    assert rows[0]["layout"]["font_size"] >= 12
    assert rows[0]["layout"]["orientation"] == "horizontal"
    assert rows[0]["layout"]["validation"]["status"] == "deterministic_only"
    assert Path(rows[0]["layout"]["preview_path"]).exists()
    assert (run_dir / "reports" / "phase4-report.md").exists()


def _copy_font(tmp_path: Path) -> Path:
    source = sorted(Path("C:/Windows/Fonts").glob("*.ttf"))[0]
    target = tmp_path / source.name
    target.write_bytes(source.read_bytes())
    return target


def _write_font_selection(path: Path, font_path: Path) -> None:
    payload = {
        "record_id": "page.png#1",
        "image_name": "page.png",
        "translated_text": "街头演出？",
        "status": "selected",
        "selected_font_id": "font-test",
        "selected_font": {"font_id": "font-test", "path": str(font_path), "family_name": "Test"},
        "comparison_image_path": str(path.parent / "comparison.png"),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
