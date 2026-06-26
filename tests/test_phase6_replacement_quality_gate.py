from pathlib import Path

from PIL import Image, ImageDraw

from autolettering.phase6_replacement_quality_gate import (
    effective_cleanup_for_gpt_quality,
    gpt_replacement_quality_gate,
)


def test_gpt_replacement_quality_gate_rejects_large_dark_overlay_even_when_mimo_accepts(tmp_path: Path):
    cleaned_path = tmp_path / "cleaned.png"
    replacement_path = tmp_path / "replacement.png"
    _write_clean_context(cleaned_path)
    _write_context_with_dark_overlay(replacement_path)
    cleanup = {
        "method": "lama_large_512px",
        "cleaned_crop_path": str(cleaned_path),
        "replacement_method": "gpt_image2_masked_edit",
        "replacement_crop_path": str(replacement_path),
        "text_overlay_required": False,
    }
    quality_by_id = {
        "page.png#1": {
            "record_id": "page.png#1",
            "status": "evaluated",
            "usable": True,
            "exact_text_correct": True,
            "simplified_chinese_correct": True,
            "no_japanese_remaining": True,
            "region_correct": True,
            "style_consistent": True,
            "outside_mask_preserved": True,
            "issues": [],
            "source_cleaned_crop_path": str(cleaned_path),
            "source_replacement_crop_path": str(replacement_path),
        }
    }

    gate = gpt_replacement_quality_gate("page.png#1", cleanup, quality_by_id)
    effective = effective_cleanup_for_gpt_quality("page.png#1", cleanup, quality_by_id)

    assert gate["accepted"] is False
    assert gate["failure_reason"] == "quality_rejected"
    assert gate["local_artifact_gate_passed"] is False
    assert "local_artifact_large_flat_overlay" in gate["issues"]
    assert effective["text_overlay_required"] is True
    assert effective["gpt_replacement_quality"]["local_artifact_gate_passed"] is False
    assert "replacement_method" not in effective
    assert "replacement_crop_path" not in effective


def test_gpt_replacement_quality_gate_accepts_sparse_text_like_changes(tmp_path: Path):
    cleaned_path = tmp_path / "cleaned.png"
    replacement_path = tmp_path / "replacement.png"
    _write_clean_context(cleaned_path)
    _write_context_with_sparse_vertical_text(replacement_path)
    cleanup = {
        "method": "lama_large_512px",
        "cleaned_crop_path": str(cleaned_path),
        "replacement_method": "gpt_image2_masked_edit",
        "replacement_crop_path": str(replacement_path),
        "text_overlay_required": False,
    }
    quality_by_id = {
        "page.png#1": {
            "record_id": "page.png#1",
            "status": "evaluated",
            "usable": True,
            "exact_text_correct": True,
            "simplified_chinese_correct": True,
            "no_japanese_remaining": True,
            "region_correct": True,
            "style_consistent": True,
            "outside_mask_preserved": True,
            "issues": [],
            "source_cleaned_crop_path": str(cleaned_path),
            "source_replacement_crop_path": str(replacement_path),
        }
    }

    gate = gpt_replacement_quality_gate("page.png#1", cleanup, quality_by_id)

    assert gate["accepted"] is True
    assert gate["local_artifact_gate_passed"] is True
    assert "local_artifact_large_flat_overlay" not in gate["issues"]


def _write_clean_context(path: Path) -> None:
    image = Image.new("RGB", (180, 180), "white")
    draw = ImageDraw.Draw(image)
    draw.line((8, 130, 172, 50), fill=(180, 180, 180), width=2)
    draw.line((10, 150, 160, 88), fill=(190, 190, 190), width=2)
    draw.arc((58, 20, 122, 84), 180, 360, fill=(30, 30, 30), width=2)
    draw.line((90, 84, 90, 155), fill=(40, 40, 40), width=2)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def _write_context_with_dark_overlay(path: Path) -> None:
    image = Image.open(path.with_name("cleaned.png")).convert("RGB")
    draw = ImageDraw.Draw(image)
    draw.rectangle((70, 24, 112, 154), fill=(45, 48, 52))
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def _write_context_with_sparse_vertical_text(path: Path) -> None:
    image = Image.open(path.with_name("cleaned.png")).convert("RGB")
    draw = ImageDraw.Draw(image)
    for index, y in enumerate(range(38, 128, 18)):
        x = 88 + (index % 2)
        draw.line((x, y, x, y + 11), fill=(20, 20, 20), width=2)
        draw.line((x - 4, y + 5, x + 6, y + 5), fill=(20, 20, 20), width=2)
    image.save(path)
