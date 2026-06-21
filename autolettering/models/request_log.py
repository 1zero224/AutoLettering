from __future__ import annotations

from pathlib import Path
from typing import Any


def request_summary(kind: str, payload: dict[str, Any], image_path: str | Path | None = None) -> dict[str, Any]:
    user_content = payload["messages"][1]["content"]
    text_parts = [part["text"] for part in user_content if part.get("type") == "text"]
    image_count = sum(1 for part in user_content if part.get("type") == "image_url")
    summary: dict[str, Any] = {
        "kind": kind,
        "model": payload.get("model"),
        "image_count": image_count,
        "prompt_chars": sum(len(text) for text in text_parts),
        "max_completion_tokens": payload.get("max_completion_tokens"),
    }
    thinking = payload.get("thinking")
    if isinstance(thinking, dict):
        summary["thinking_type"] = thinking.get("type")
    if image_path is not None:
        summary["image_path"] = str(image_path)
    return summary
