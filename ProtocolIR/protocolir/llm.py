"""OpenRouter adapter used only for strict structured semantic extraction."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


class OpenRouterUnavailable(RuntimeError):
    """Raised when OpenRouter cannot return a valid structured parse."""


@dataclass(frozen=True)
class OpenRouterConfig:
    api_key: str
    model: str = "openrouter/free"
    base_url: str = "https://openrouter.ai/api/v1"
    max_tokens: int = 4096
    timeout_seconds: int = 90


PROTOCOL_PARSE_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "goal": {"type": "string"},
        "title": {"type": ["string", "null"]},
        "sample_count": {"type": "integer", "minimum": 1, "maximum": 96},
        "materials": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "class": {
                        "type": "string",
                        "enum": [
                            "template",
                            "master_mix",
                            "primer",
                            "water",
                            "buffer",
                            "enzyme",
                            "dye",
                            "salt",
                            "unknown",
                        ],
                    },
                    "volume_ul": {"type": ["number", "null"]},
                    "location_hint": {"type": ["string", "null"]},
                    "notes": {"type": ["string", "null"]},
                },
                "required": ["name", "class", "volume_ul", "location_hint", "notes"],
                "additionalProperties": False,
            },
        },
        "actions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "action_type": {
                        "type": "string",
                        "enum": [
                            "transfer",
                            "mix",
                            "delay",
                            "temperature",
                            "centrifuge",
                            "vortex",
                            "incubate",
                            "comment",
                        ],
                    },
                    "reagent": {"type": ["string", "null"]},
                    "volume_ul": {"type": ["number", "null"]},
                    "source_hint": {"type": ["string", "null"]},
                    "destination_hint": {"type": ["string", "null"]},
                    "repetitions": {"type": ["integer", "null"]},
                    "constraints": {"type": "array", "items": {"type": "string"}},
                    "description": {"type": "string"},
                },
                "required": [
                    "action_type",
                    "reagent",
                    "volume_ul",
                    "source_hint",
                    "destination_hint",
                    "repetitions",
                    "constraints",
                    "description",
                ],
                "additionalProperties": False,
            },
        },
        "ambiguities": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["goal", "title", "sample_count", "materials", "actions", "ambiguities"],
    "additionalProperties": False,
}


def load_openrouter_config(
    model: Optional[str] = None,
    max_tokens: Optional[int] = None,
    timeout_seconds: int = 90,
) -> OpenRouterConfig:
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise OpenRouterUnavailable("OPENROUTER_API_KEY is not set")

    return OpenRouterConfig(
        api_key=api_key,
        model=model or os.getenv("PROTOCOLIR_MODEL", "openrouter/free"),
        base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").rstrip("/"),
        max_tokens=max_tokens or int(os.getenv("PROTOCOLIR_MAX_TOKENS", "4096")),
        timeout_seconds=timeout_seconds,
    )


def openrouter_json(
    system_prompt: str,
    user_prompt: str,
    *,
    model: Optional[str] = None,
    max_tokens: Optional[int] = None,
    timeout_seconds: int = 90,
) -> Dict[str, Any]:
    """
    Call OpenRouter Chat Completions with strict JSON-schema output.

    OpenRouter normalizes the OpenAI Chat Completions schema at
    https://openrouter.ai/api/v1/chat/completions. The free router can be used
    as model "openrouter/free"; OpenRouter will route to a compatible free model.
    """

    config = load_openrouter_config(model, max_tokens, timeout_seconds)
    payload = {
        "model": config.model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "protocolir_semantic_parse",
                "strict": True,
                "schema": PROTOCOL_PARSE_SCHEMA,
            },
        },
        "provider": {
            "require_parameters": True,
        },
        "temperature": 0.0,
        "max_tokens": config.max_tokens,
        "stream": False,
    }

    request = urllib.request.Request(
        f"{config.base_url}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "HTTP-Referer": "https://github.com/protocolir/protocolir",
            "X-Title": "ProtocolIR",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=config.timeout_seconds) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise OpenRouterUnavailable(
            f"OpenRouter request failed with HTTP {exc.code}: {body[:800]}"
        ) from exc
    except urllib.error.URLError as exc:
        raise OpenRouterUnavailable(f"OpenRouter request failed: {exc.reason}") from exc
    except TimeoutError as exc:
        raise OpenRouterUnavailable("OpenRouter request timed out") from exc

    try:
        data = json.loads(raw)
        choices: List[Dict[str, Any]] = data.get("choices", [])
        content = choices[0]["message"]["content"] if choices else ""
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise OpenRouterUnavailable("OpenRouter returned an unexpected response shape") from exc

    if not content:
        raise OpenRouterUnavailable("OpenRouter returned empty JSON content")

    try:
        return json.loads(content)
    except json.JSONDecodeError as exc:
        raise OpenRouterUnavailable("OpenRouter structured output was not valid JSON") from exc


def openrouter_text(
    system_prompt: str,
    user_prompt: str,
    *,
    model: Optional[str] = None,
    max_tokens: Optional[int] = None,
    timeout_seconds: int = 90,
    temperature: float = 0.0,
) -> str:
    """Call OpenRouter Chat Completions for text output used by baselines."""

    config = load_openrouter_config(model, max_tokens, timeout_seconds)
    payload = {
        "model": config.model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "provider": {"require_parameters": False},
        "temperature": temperature,
        "max_tokens": config.max_tokens,
        "stream": False,
    }

    request = urllib.request.Request(
        f"{config.base_url}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "HTTP-Referer": "https://github.com/protocolir/protocolir",
            "X-Title": "ProtocolIR Baseline",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=config.timeout_seconds) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise OpenRouterUnavailable(
            f"OpenRouter baseline request failed with HTTP {exc.code}: {body[:800]}"
        ) from exc
    except urllib.error.URLError as exc:
        raise OpenRouterUnavailable(f"OpenRouter baseline request failed: {exc.reason}") from exc
    except TimeoutError as exc:
        raise OpenRouterUnavailable("OpenRouter baseline request timed out") from exc

    try:
        data = json.loads(raw)
        choices: List[Dict[str, Any]] = data.get("choices", [])
        content = choices[0]["message"]["content"] if choices else ""
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise OpenRouterUnavailable("OpenRouter returned an unexpected baseline response shape") from exc

    if not content:
        raise OpenRouterUnavailable("OpenRouter returned empty baseline content")
    return str(content)
