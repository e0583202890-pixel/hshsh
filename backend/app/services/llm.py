"""Unified LLM client.

Supports two providers, auto-detected from which API key is set:
  - OpenRouter (OpenAI-compatible chat completions) - priority if its key is set
  - Anthropic native (Messages API)

Both expose the same `complete(system, user)` call so the rest of the app
(ai_clipper, metadata_ai) is provider-agnostic. OpenRouter lets the operator use
Claude models (e.g. "anthropic/claude-3.5-sonnet") or any other model on their
OpenRouter account by setting OPENROUTER_MODEL.
"""
from __future__ import annotations

import asyncio
import logging

import httpx

from ..config import settings

log = logging.getLogger("llm")


class LLMError(RuntimeError):
    pass


def provider() -> str | None:
    if settings.openrouter_api_key:
        return "openrouter"
    if settings.anthropic_api_key:
        return "anthropic"
    return None


def active_model() -> str:
    if settings.openrouter_api_key:
        return settings.openrouter_model
    return settings.anthropic_model


def is_configured() -> bool:
    return provider() is not None


async def complete(system: str, user: str, max_tokens: int = 4096) -> str:
    p = provider()
    if p == "openrouter":
        return await _openrouter(system, user, max_tokens)
    if p == "anthropic":
        return await _anthropic(system, user, max_tokens)
    raise LLMError("No LLM API key set (OPENROUTER_API_KEY or ANTHROPIC_API_KEY)")


async def _openrouter(system: str, user: str, max_tokens: int) -> str:
    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json",
        # OpenRouter asks for these for attribution; harmless for a local tool.
        "HTTP-Referer": "http://localhost:5173",
        "X-Title": "KICKLIPS Studio",
    }
    payload = {
        "model": settings.openrouter_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_tokens": max_tokens,
    }
    async with httpx.AsyncClient(timeout=180) as client:
        resp = await client.post(f"{settings.openrouter_base_url}/chat/completions",
                                 headers=headers, json=payload)
    if resp.status_code != 200:
        raise LLMError(f"OpenRouter HTTP {resp.status_code}: {resp.text[:300]}")
    data = resp.json()
    try:
        return data["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMError(f"Unexpected OpenRouter response: {str(data)[:300]}") from exc


async def _anthropic(system: str, user: str, max_tokens: int) -> str:
    def _blocking() -> str:
        import anthropic
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        resp = client.messages.create(
            model=settings.anthropic_model, max_tokens=max_tokens,
            system=system, messages=[{"role": "user", "content": user}])
        return "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
    return await asyncio.to_thread(_blocking)
