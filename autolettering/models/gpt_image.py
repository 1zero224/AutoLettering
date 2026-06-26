from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import base64

from openai import OpenAI
from PIL import Image, ImageOps


@dataclass(frozen=True)
class GptImageConfig:
    base_url: str | None
    api_key: str
    model: str


class GptImageEditClient:
    def __init__(self, config: GptImageConfig) -> None:
        self.config = config
        kwargs = {"api_key": config.api_key}
        if config.base_url:
            kwargs["base_url"] = normalize_openai_base_url(config.base_url)
        self.client = OpenAI(**kwargs)

    def edit_image(
        self,
        image_path: str | Path,
        mask_path: str | Path,
        prompt: str,
        output_path: str | Path,
    ) -> dict:
        with Path(image_path).open("rb") as image_file, Path(mask_path).open("rb") as mask_file:
            result = self.client.images.edit(
                model=self.config.model,
                image=image_file,
                mask=mask_file,
                prompt=prompt,
                n=1,
                size="auto",
                quality="auto",
            )
        return _save_first_image(result, output_path)


def gpt_image_edit_prompt(translated_text: str) -> str:
    lines = [
        "Edit only the transparent masked original-text pixels.",
        "The detected bbox is only a loose container for the target text; it may include people, props, background, or other manga artwork.",
        "The transparent mask indicates candidate original text glyph pixels, not permission to repaint every object inside the bbox.",
        "If the bbox contains passerby figures or other non-text artwork, leave them unchanged.",
        "Only replace the original Japanese text glyphs that correspond to the target Chinese text.",
        "Remove the original Japanese manga text and preserve the surrounding artwork.",
        "Inside and outside the mask, preserve every non-text element: person, face, hair, clothing, hands, body, props, background line art, screentone, panel borders, texture, and motion lines.",
        "Do not repaint, erase, blur, white out, or simplify any non-text artwork, even when it is inside the transparent masked area.",
        "Render the Chinese replacement text naturally inside the transparent masked area only.",
        "The output text must exactly match the target string below, character for character.",
        "Do not write text anywhere outside the transparent masked area.",
        "Do not use speech bubbles, margins, or unmasked areas for the replacement text.",
        "Do not create gray boxes, shaded rectangles, glow, blur, gradients, or dark overlays around the replacement text.",
        "Keep the manga background tone inside the edited area consistent with nearby black-and-white line art.",
        "Use clean black manga lettering unless the original local text is visibly light-on-dark.",
        "For light-on-dark source text, render crisp light text on the dark background and match the local perspective, skew, scale, and angle.",
        "Do not omit, add, reorder, paraphrase, translate, or keep any original Japanese characters.",
        "Never generate Japanese kana or Japanese-only kanji variants. Use simplified Chinese punctuation and characters exactly as provided.",
        "If the area is vertical, keep a natural vertical manga lettering layout.",
        *_glyph_variant_warnings(translated_text),
        *_exact_target_text_constraints(translated_text),
        f"Target Chinese text: {translated_text}",
    ]
    return "\n".join(lines)


def _exact_target_text_constraints(translated_text: str) -> list[str]:
    if not translated_text:
        return []
    length_label = "visible Chinese characters" if all(_is_cjk_unified(char) for char in translated_text) else "visible target characters"
    constraints = [
        f"Character sequence: {' | '.join(translated_text)}",
        f"Write exactly {len(translated_text)} {length_label}; each listed character must appear once in order.",
    ]
    if "啪" in translated_text:
        constraints.append("Do not replace `啪` with `啦`, `吧`, `拍`, `哇`, or any visually similar character.")
    if "嗒" in translated_text:
        constraints.append("Do not replace `嗒` with `哒`, `啦`, `搭`, `塔`, or any visually similar character.")
    if "…" in translated_text:
        constraints.append("The target contains the single ellipsis glyph `…`; copy that exact glyph.")
        constraints.append("Do not replace `…` with three periods `...`, two periods `..`, centered dots, or any other punctuation.")
    return constraints


def _is_cjk_unified(char: str) -> bool:
    return "\u4e00" <= char <= "\u9fff"


def _glyph_variant_warnings(translated_text: str) -> list[str]:
    warnings: list[str] = []
    if "暂" in translated_text:
        warnings.append("The target contains Simplified Chinese `暂`; copy that exact glyph.")
        warnings.append("Do not write `暫`, `仮`, or `哲` for `暂`.")
    return warnings


def normalize_openai_base_url(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    for suffix in ("/images/edits", "/images"):
        if normalized.endswith(suffix):
            return normalized[: -len(suffix)]
    return normalized


def gpt_image_request_summary(
    config: GptImageConfig | None,
    image_path: str | Path,
    mask_path: str | Path,
    prompt: str,
) -> dict:
    return {
        "kind": "gpt_image_2_masked_edit",
        "model": config.model if config else None,
        "base_url_configured": bool(config and config.base_url),
        "image_path": str(image_path),
        "mask_path": str(mask_path),
        "prompt_chars": len(prompt),
        "size": "auto",
        "quality": "auto",
        "n": 1,
    }


def _save_first_image(result, output_path: str | Path) -> dict:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    image_data = result.data[0]
    if not image_data.b64_json:
        raise RuntimeError("gpt_image_missing_b64_json")
    output.write_bytes(base64.b64decode(image_data.b64_json))
    return {
        "status": "ok",
        "output_path": str(output),
        "response": {
            "created": getattr(result, "created", None),
            "usage": _usage_payload(getattr(result, "usage", None)),
        },
    }


def normalize_gpt_output_to_crop(
    image_path: str | Path,
    target_size: tuple[int, int],
    output_path: str | Path,
) -> dict:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(image_path) as image:
        source = image.convert("RGB")
        normalized = ImageOps.fit(source, target_size, method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
    normalized.save(output)
    return {
        "normalized_output_path": str(output),
        "normalized_size": list(target_size),
        "source_size": list(source.size),
    }


def _usage_payload(usage) -> dict | None:
    if usage is None:
        return None
    if hasattr(usage, "model_dump"):
        return usage.model_dump()
    return dict(usage) if isinstance(usage, dict) else None
