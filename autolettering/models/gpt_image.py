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
    return "\n".join(
        [
            "Edit only the transparent masked text area.",
            "Remove the original Japanese manga text and preserve the surrounding artwork.",
            "Render the Chinese replacement text naturally in the edited area.",
            "The text must exactly match the target string below.",
            "Do not omit, add, reorder, paraphrase, translate, or keep any Japanese characters.",
            "If the area is vertical, keep a natural vertical manga lettering layout.",
            f"Target Chinese text: {translated_text}",
        ]
    )


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
