"""
LAYER 1: Semantic Protocol Parser
Converts messy protocols.io text into structured semantic actions.
Uses Claude for reliable structured extraction.
"""

import json
from typing import Optional
from anthropic import Anthropic
from protocolir.schemas import (
    ParsedProtocol,
    SemanticAction,
    SemanticActionType,
    Material,
    ReagentClass,
)

client = Anthropic()


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

    message = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=2048,
        messages=[{"role": "user", "content": extraction_prompt}],
    )

    response_text = message.content[0].text.strip()

    # Parse JSON response
    try:
        data = json.loads(response_text)
    except json.JSONDecodeError:
        # Try to extract JSON from markdown code blocks
        if "```json" in response_text:
            data = json.loads(response_text.split("```json")[1].split("```")[0])
        elif "```" in response_text:
            data = json.loads(response_text.split("```")[1].split("```")[0])
        else:
            raise ValueError(f"Could not parse LLM response as JSON: {response_text}")

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

    response1 = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=1024,
        messages=conversation_history,
    )

    parse_result = response1.content[0].text
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

    response2 = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=1024,
        messages=conversation_history,
    )

    json_text = response2.content[0].text.strip()

    try:
        data = json.loads(json_text)
    except json.JSONDecodeError:
        if "```json" in json_text:
            data = json.loads(json_text.split("```json")[1].split("```")[0])
        else:
            data = {}

    return data
