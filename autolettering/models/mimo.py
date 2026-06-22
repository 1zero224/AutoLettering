from __future__ import annotations

from dataclasses import dataclass
import base64
import json
import mimetypes
from pathlib import Path
import urllib.error
import urllib.request

from .request_log import request_summary


@dataclass(frozen=True)
class MimoVisionConfig:
    base_url: str
    api_key: str
    model: str
    max_completion_tokens: int = 512
    thinking_type: str | None = None


@dataclass(frozen=True)
class FontSelectionResult:
    status: str
    selected_font_id: str | None
    confidence: float | None
    reasoning_summary: str | None
    failure_reason: str | None


class MimoVisionClient:
    def __init__(self, config: MimoVisionConfig) -> None:
        self.config = config

    def build_chat_payload(
        self,
        image_path: str | Path,
        prompt: str,
        system_prompt: str | None = None,
        max_completion_tokens: int | None = None,
    ) -> dict:
        payload = {
            "model": self.config.model,
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt or "You inspect manga lettering images and return structured JSON.",
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": _image_data_url(image_path)},
                        },
                        {"type": "text", "text": prompt},
                    ],
                },
            ],
            "max_completion_tokens": max_completion_tokens or self.config.max_completion_tokens,
        }
        if self.config.thinking_type:
            payload["thinking"] = {"type": self.config.thinking_type}
        return payload

    def choose_font(self, comparison_image_path: str | Path, prompt: str) -> dict:
        system_prompt = "You select manga lettering fonts from labeled comparison images. Return only compact JSON."
        return self.analyze_image(
            comparison_image_path,
            prompt,
            kind="font_selection",
            system_prompt=system_prompt,
            max_completion_tokens=max(1024, self.config.max_completion_tokens),
        )

    def analyze_image(
        self,
        image_path: str | Path,
        prompt: str,
        kind: str = "image_analysis",
        system_prompt: str | None = None,
        max_completion_tokens: int | None = None,
    ) -> dict:
        image_path = Path(image_path)
        payload = self.build_chat_payload(
            image_path,
            prompt,
            system_prompt=system_prompt,
            max_completion_tokens=max_completion_tokens,
        )
        response = _post_json(self._chat_completions_url(), self.config.api_key, payload)
        return {
            "raw_text": _message_content(response),
            "request": {
                "url": self._chat_completions_url(),
                **request_summary(kind, payload, image_path=image_path),
            },
            "response": _response_summary(response),
        }

    def _chat_completions_url(self) -> str:
        return f"{self.config.base_url.rstrip('/')}/chat/completions"


def build_font_selection_prompt(translated_text: str, candidate_fonts: list[dict]) -> str:
    candidates = [
        {
            "font_id": item["font_id"],
            "family_name": item.get("family_name", ""),
            "style_hints": item.get("style_hints", []),
        }
        for item in candidate_fonts
    ]
    return "\n".join(
        [
            "Choose the candidate font whose rendered preview best matches the source manga text style.",
            "Use only the visible candidate font IDs below.",
            f"Translated text: {translated_text}",
            f"Candidates JSON: {json.dumps(candidates, ensure_ascii=False)}",
            "Return only JSON with keys: selected_font_id, confidence, reasoning_summary.",
        ]
    )


def parse_font_selection_response(raw_text: str, candidate_font_ids: list[str]) -> FontSelectionResult:
    try:
        payload = json.loads(_strip_json_wrapper(raw_text))
    except json.JSONDecodeError:
        return _failed("invalid_json")

    selected = payload.get("selected_font_id")
    if selected not in candidate_font_ids:
        return _failed("selected_font_not_in_candidates")

    return FontSelectionResult(
        status="selected",
        selected_font_id=selected,
        confidence=_optional_float(payload.get("confidence")),
        reasoning_summary=str(payload.get("reasoning_summary", "")).strip() or None,
        failure_reason=None,
    )


def _image_data_url(image_path: str | Path) -> str:
    path = Path(image_path)
    mime_type = mimetypes.guess_type(path.name)[0] or "image/png"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def _post_json(url: str, api_key: str, payload: dict) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "api-key": api_key,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"mimo_http_error:{exc.code}:{body[:500]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"mimo_url_error:{exc.reason}") from exc


def _message_content(response: dict) -> str:
    return str(response["choices"][0]["message"]["content"])


def _response_summary(response: dict) -> dict:
    usage = response.get("usage") if isinstance(response.get("usage"), dict) else None
    return {
        "status": "ok",
        "id": response.get("id"),
        "model": response.get("model"),
        "usage": usage,
    }


def _strip_json_wrapper(raw_text: str) -> str:
    text = raw_text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _failed(reason: str) -> FontSelectionResult:
    return FontSelectionResult(
        status="failed",
        selected_font_id=None,
        confidence=None,
        reasoning_summary=None,
        failure_reason=reason,
    )
