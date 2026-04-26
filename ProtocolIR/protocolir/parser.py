"""
LAYER 1: Semantic Protocol Parser
Converts messy protocols.io text into structured semantic actions.
Uses configurable LLM providers for structured extraction.
"""

import os
import json
from typing import Optional, List, Dict, Any

import requests
from protocolir.schemas import (
    ParsedProtocol,
    SemanticAction,
    SemanticActionType,
    Material,
    ReagentClass,
)

try:
    from dotenv import load_dotenv

    load_dotenv(".env.local")
except ImportError:
    pass


class LLMClient:
    """Provider-agnostic LLM client for protocol parsing."""

    def __init__(self) -> None:
        self.provider = os.getenv("PROTOCOLIR_LLM_PROVIDER", "ollama").strip().lower()
        self.temperature = float(os.getenv("PROTOCOLIR_TEMPERATURE", "0"))
        self.max_tokens = int(os.getenv("PROTOCOLIR_MAX_TOKENS", "2048"))
        self.timeout_seconds = int(os.getenv("PROTOCOLIR_LLM_TIMEOUT", "120"))
        self.model = self._resolve_model()
        self._anthropic_client = None

    def _resolve_model(self) -> str:
        configured_model = os.getenv("PROTOCOLIR_MODEL")
        if configured_model:
            return configured_model

        if self.provider == "anthropic":
            return "claude-sonnet-4-5"

        # Default for local inference.
        return os.getenv("OLLAMA_MODEL", "llama3.1:8b")

    def chat(self, messages: List[Dict[str, str]], max_tokens: Optional[int] = None) -> str:
        target_max_tokens = max_tokens or self.max_tokens

        if self.provider == "anthropic":
            return self._chat_anthropic(messages, target_max_tokens)
        if self.provider == "ollama":
            return self._chat_ollama(messages)

        raise ValueError(
            "Unsupported PROTOCOLIR_LLM_PROVIDER. Use 'ollama' or 'anthropic'."
        )

    def _chat_anthropic(self, messages: List[Dict[str, str]], max_tokens: int) -> str:
        if self._anthropic_client is None:
            try:
                from anthropic import Anthropic
            except ImportError as exc:
                raise ImportError(
                    "anthropic package is required for provider='anthropic'. "
                    "Install with: pip install anthropic"
                ) from exc
            self._anthropic_client = Anthropic()

        response = self._anthropic_client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=self.temperature,
            messages=messages,
        )

        text_chunks = [block.text for block in response.content if hasattr(block, "text")]
        return "\n".join(text_chunks).strip()

    def _chat_ollama(self, messages: List[Dict[str, str]]) -> str:
        base_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
        endpoint = f"{base_url}/api/chat"
        api_key = os.getenv("OLLAMA_API_KEY", "").strip()

        headers: Dict[str, str] = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": self.temperature},
        }

        response = requests.post(
            endpoint,
            headers=headers,
            json=payload,
            timeout=self.timeout_seconds,
        )

        if response.status_code >= 400:
            raise ValueError(
                f"Ollama request failed ({response.status_code}): {response.text[:300]}"
            )

        data = response.json()
        message = data.get("message", {})
        content = message.get("content", "")
        if not content:
            raise ValueError("Ollama response did not include message.content")
        return content.strip()


client = LLMClient()


def _parse_json_response(response_text: str) -> dict:
    """Best-effort JSON extraction for LLM responses."""
    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        if "```json" in response_text:
            candidate = response_text.split("```json", 1)[1].split("```", 1)[0]
            return json.loads(candidate)
        if "```" in response_text:
            candidate = response_text.split("```", 1)[1].split("```", 1)[0]
            return json.loads(candidate)
        raise ValueError(f"Could not parse LLM response as JSON: {response_text}")


def parse_protocol(raw_text: str, source_url: Optional[str] = None) -> ParsedProtocol:
    """
    Parse a messy natural-language protocol into structured semantic actions.

    Args:
        raw_text: Raw protocol text from protocols.io or user input
        source_url: Optional URL of the source protocol

    Returns:
        ParsedProtocol with extracted goal, materials, actions, and ambiguities
    """

    extraction_prompt = f"""
You are an expert lab protocol parser. Extract structured information from this protocol.

PROTOCOL TEXT:
{raw_text}

Output a JSON object with these fields:
1. goal: One-line description of what this protocol achieves
2. materials: List of reagents/materials (name, class, estimated volume)
   - Classes: template, master_mix, primer, water, buffer, enzyme, dye, salt, unknown
3. steps: List of semantic actions
   - For each step, extract: action_type, reagent, volume_ul, source_hint, destination_hint, constraints
   - action_types: transfer, mix, delay, temperature, centrifuge, vortex, incubate, comment
4. ambiguities: List of missing details (unknown well numbers, unspecified temperatures, etc.)

Be precise. If a detail is missing, flag it in ambiguities.

Return ONLY valid JSON, no markdown, no explanations.
"""

    response_text = client.chat([{"role": "user", "content": extraction_prompt}], max_tokens=2048)
    data = _parse_json_response(response_text)

    # Convert to Pydantic models
    materials = [
        Material(
            name=m.get("name", "unknown"),
            reagent_class=ReagentClass(m.get("class", "unknown").lower()),
            volume_ul=m.get("volume_ul"),
            notes=m.get("notes"),
        )
        for m in data.get("materials", [])
    ]

    actions = [
        SemanticAction(
            action_type=SemanticActionType(s.get("action_type", "comment").lower()),
            reagent=s.get("reagent"),
            volume_ul=s.get("volume_ul"),
            source_hint=s.get("source_hint"),
            destination_hint=s.get("destination_hint"),
            repetitions=s.get("repetitions"),
            constraints=s.get("constraints", []),
            description=s.get("description", ""),
        )
        for s in data.get("steps", [])
    ]

    parsed = ParsedProtocol(
        goal=data.get("goal", "Unknown protocol"),
        source=source_url,
        materials=materials,
        actions=actions,
        ambiguities=data.get("ambiguities", []),
    )

    return parsed


def parse_protocol_with_llm_detail(raw_text: str) -> dict:
    """
    Extended parsing with more LLM interaction for clarification.
    Used when protocol is particularly ambiguous.
    """
    conversation_history = []

    # First pass: get baseline parse
    first_prompt = f"""
Parse this lab protocol step-by-step. Be very detailed about each step.

PROTOCOL:
{raw_text}

For each step, extract:
1. Action type (transfer, mix, incubate, etc.)
2. What reagents/items are involved
3. Volumes (if specified)
4. Source and destination (specific tubes/wells if named)
5. Any special conditions (temperature, time, etc.)
6. Ambiguities or missing information

Format as a numbered list, one step per line.
"""

    conversation_history.append({"role": "user", "content": first_prompt})

    parse_result = client.chat(conversation_history, max_tokens=1024)
    conversation_history.append({"role": "assistant", "content": parse_result})

    # Second pass: ask for JSON
    json_prompt = """
Now, convert your analysis above into a single JSON object with these fields:
{
  "goal": "...",
  "materials": [{"name": "...", "class": "...", "volume_ul": ...}],
  "steps": [{"action_type": "...", "reagent": "...", "volume_ul": ..., "source_hint": "...", "destination_hint": "...", "constraints": [...]}],
  "ambiguities": ["..."]
}

Return ONLY the JSON object, no markdown or explanation.
"""

    conversation_history.append({"role": "user", "content": json_prompt})

    json_text = client.chat(conversation_history, max_tokens=1024).strip()
    try:
        data = _parse_json_response(json_text)
    except ValueError:
        data = {}

    return data
