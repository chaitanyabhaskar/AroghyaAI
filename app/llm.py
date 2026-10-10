"""Thin streaming client for any OpenAI-compatible /chat/completions endpoint.

Works with Groq, the official Llama API, OpenRouter, Together, OpenAI, or a local
Ollama / llama.cpp server - only LLM_BASE_URL and the model name change.
"""

from __future__ import annotations

import json
from typing import Any, AsyncIterator

import httpx

from .certs import ssl_verify
from .config import Settings

# GenAI Generated code - Start


class LLMError(RuntimeError):
    """Raised when the provider rejects the request or the transport fails."""


def build_user_content(text: str, image_data_url: str | None) -> Any:
    """Return either a plain string or the multimodal content array."""
    if not image_data_url:
        return text
    parts: list[dict[str, Any]] = []
    if text:
        parts.append({"type": "text", "text": text})
    parts.append({"type": "image_url", "image_url": {"url": image_data_url}})
    return parts


async def stream_chat(
    messages: list[dict[str, Any]],
    *,
    settings: Settings,
    model: str | None = None,
) -> AsyncIterator[str]:
    """Yield response text chunks as they arrive."""
    if not settings.api_key:
        raise LLMError(
            "LLM_API_KEY is not set. Copy .env.example to .env and add your key."
        )

    payload = {
        "model": model or settings.text_model,
        "messages": messages,
        "temperature": settings.temperature,
        "max_tokens": settings.max_tokens,
        "stream": True,
    }
    headers = {
        "Authorization": f"Bearer {settings.api_key}",
        "Content-Type": "application/json",
    }
    url = f"{settings.base_url}/chat/completions"

    try:
        async with httpx.AsyncClient(
            timeout=settings.timeout, verify=ssl_verify()
        ) as client:
            async with client.stream(
                "POST", url, json=payload, headers=headers
            ) as response:
                if response.status_code >= 400:
                    body = (await response.aread()).decode("utf-8", "replace")
                    raise LLMError(_friendly_error(response.status_code, body))
                async for line in response.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if not data or data == "[DONE]":
                        if data == "[DONE]":
                            return
                        continue
                    try:
                        chunk = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    for choice in chunk.get("choices") or []:
                        delta = choice.get("delta") or {}
                        piece = delta.get("content")
                        if piece:
                            yield piece
    except httpx.TimeoutException as exc:  # pragma: no cover - network dependent
        raise LLMError("The model took too long to respond. Please try again.") from exc
    except httpx.HTTPError as exc:  # pragma: no cover - network dependent
        raise LLMError(f"Could not reach the model provider: {exc}") from exc


def _friendly_error(status: int, body: str) -> str:
    detail = body.strip()
    try:
        parsed = json.loads(body)
        detail = (
            parsed.get("error", {}).get("message")
            if isinstance(parsed.get("error"), dict)
            else parsed.get("error") or detail
        ) or detail
    except (json.JSONDecodeError, AttributeError):
        pass
    detail = str(detail)[:300]
    if status in (401, 403):
        return f"The model provider rejected the API key ({status}). {detail}"
    if status == 404:
        return (
            f"Model not found ({status}). Check LLM_TEXT_MODEL / LLM_VISION_MODEL "
            f"against your provider's current model list. {detail}"
        )
    if status == 429:
        return "Rate limit reached at the model provider. Wait a moment and retry."
    if status == 413:
        return "The attached image is too large for this model. Try a smaller photo."
    return f"Model provider error {status}. {detail}"
# GenAI Generated code - End
