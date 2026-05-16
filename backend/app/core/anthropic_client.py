"""Anthropic SDK client factory.

Keeps proxy/base-url configuration in one place so app code and standalone
scripts behave the same way.
"""

from __future__ import annotations

import os
from typing import Any

import anthropic

from app.core.config import settings


def anthropic_client_options(
    *,
    api_key: str | None = None,
    base_url: str | None = None,
) -> dict[str, Any]:
    """Return kwargs for Anthropic SDK clients.

    Environment fallback is intentional: standalone scripts call
    `load_local_env()` before creating the client, but `settings` may already
    have been imported by then.
    """
    env_proxy_key = (os.getenv("ANTHROPIC_API_KEY_NOW") or "").strip()
    env_official_key = (os.getenv("ANTHROPIC_API_KEY") or "").strip()
    env_base_url = (os.getenv("ANTHROPIC_BASE_URL") or "").strip()

    resolved_base_url = (
        (base_url or "").strip()
        if base_url is not None
        else (env_base_url or settings.anthropic_base_url).strip()
    )
    if api_key is not None:
        resolved_api_key = api_key
    elif resolved_base_url:
        resolved_api_key = (
            env_proxy_key
            or settings.anthropic_api_key_now
            or settings.anthropic_api_key
            or env_official_key
        )
    else:
        resolved_api_key = (
            env_official_key
            or settings.anthropic_api_key
            or env_proxy_key
            or settings.anthropic_api_key_now
        )

    options: dict[str, Any] = {}
    if resolved_api_key:
        options["api_key"] = resolved_api_key
    if resolved_base_url:
        options["base_url"] = resolved_base_url
    return options


def create_anthropic_client(
    *,
    api_key: str | None = None,
    base_url: str | None = None,
) -> anthropic.Anthropic:
    return anthropic.Anthropic(**anthropic_client_options(api_key=api_key, base_url=base_url))


def create_async_anthropic_client(
    *,
    api_key: str | None = None,
    base_url: str | None = None,
) -> anthropic.AsyncAnthropic:
    return anthropic.AsyncAnthropic(**anthropic_client_options(api_key=api_key, base_url=base_url))
