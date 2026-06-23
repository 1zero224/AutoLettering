from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw

from autolettering.phase7_compare import PreviewMethodInput, run_phase7_method_comparison


def test_phase7_method_comparison_writes_index_and_sheets(tmp_path: Path):
    lama_preview = _write_preview_run(tmp_path / "lama-preview", "bt_lama_large", (255, 255, 255), (220, 220, 220))
    aot_preview = _write_preview_run(tmp_path / "aot-preview", "bt_aot", (230, 230, 240), (210, 210, 230))
    lama_eval = _write_eval_run(tmp_path / "lama-eval", 8)
    aot_eval = _write_eval_run(tmp_path / "aot-eval", 6)

    run_dir = run_phase7_method_comparison(
        [
            PreviewMethodInput("bt_lama_large", lama_preview, lama_eval),
            PreviewMethodInput("bt_aot", aot_preview, aot_eval),
        ],
        output_root=tmp_path,
        run_id="comparison",
    )

    assert (run_dir / "index.md").exists()
    assert (run_dir / "method-comparison.json").exists()
    assert (run_dir / "debug" / "local-method-comparison.png").exists()
    assert (run_dir / "debug" / "page-method-comparison.png").exists()
    assert (run_dir / "debug" / "near-square-result-grid.png").exists()
    index = (run_dir / "index.md").read_text(encoding="utf-8")
    assert "bt_lama_large" in index
    assert "score=8" in index
    assert "bt_aot" in index
    assert "score=6" in index


def test_phase7_method_comparison_near_square_grid_uses_text_bbox(tmp_path: Path):
    runs = []
    evals = []
    for index in range(4):
        label = f"method-{index}"
        runs.append(_write_preview_run(tmp_path / f"{label}-preview", label, (250, 250, 250), (230 - index, 230, 230)))
        evals.append(_write_eval_run(tmp_path / f"{label}-eval", 8 - index))

    run_dir = run_phase7_method_comparison(
        [
            PreviewMethodInput(f"method-{index}", runs[index], evals[index])
            for index in range(4)
        ],
        output_root=tmp_path,
        run_id="square-comparison",
    )

    payload = json.loads((run_dir / "method-comparison.json").read_text(encoding="utf-8"))
    assert payload["mimo"]["status"] == "not_requested"
    assert payload["near_square_sheet"].endswith("near-square-result-grid.png")

    with Image.open(run_dir / "debug" / "near-square-result-grid.png") as grid:
        ratio = grid.width / grid.height
    assert 0.75 <= ratio <= 1.35


def _write_preview_run(path: Path, cleanup_method: str, cleaned_color: tuple[int, int, int], final_color: tuple[int, int, int]) -> Path:
    page_name = "GBC06-01-png.png"
    original = _page(path / "pages" / "original" / page_name, (255, 255, 255))
    cleaned = _page(path / "pages" / "cleaned" / page_name, cleaned_color)
    final = _page(path / "pages" / page_name, final_color)
    before_after = path / "crops" / "before_after" / "GBC06-01-png-16.png"
    before_after.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (80, 40), final_color).save(before_after)
    row = {
        "image_name": "GBC06_01.png",
        "status": "page_preview_generated",
        "records": [
            {
                "record_id": "GBC06_01.png#16",
                "bbox": [20, 15, 70, 65],
                "text_bbox": [30, 20, 60, 55],
                "translated_text": "text",
                "cleanup_method": cleanup_method,
                "preview_before_after_path": str(before_after),
            }
        ],
        "preview": {
            "original_page_path": str(original),
            "cleaned_page_path": str(cleaned),
            "page_preview_path": str(final),
            "record_count": 1,
        },
    }
    _write_jsonl(path / "preview-results.jsonl", [row])
    return path


def _page(path: Path, color: tuple[int, int, int]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (120, 90), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((20, 15, 70, 65), fill=color, outline="black")
    image.save(path)
    return path


def _write_eval_run(path: Path, score: int) -> Path:
    row = {
        "image_name": "GBC06_01.png",
        "status": "evaluated",
        "score": score,
        "usable": True,
        "art_preserved": True,
    }
    _write_jsonl(path / "preview-evaluation.jsonl", [row])
    return path


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
