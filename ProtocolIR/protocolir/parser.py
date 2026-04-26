"""Layer 1: semantic protocol parsing with OpenRouter structured output."""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, Optional

from protocolir.llm import OpenRouterUnavailable, openrouter_json
from protocolir.rag import context_block
from protocolir.biosecurity import screen_materials
from protocolir.schemas import (
    Material,
    ParsedProtocol,
    ReagentClass,
    SemanticAction,
    SemanticActionType,
)


SYSTEM_PROMPT = """
You are ProtocolIR's semantic lab protocol extractor.

Return one strict JSON object. Do not write markdown. The JSON must match:
{
  "goal": "short protocol goal",
  "title": "optional title",
  "sample_count": 8,
  "materials": [
    {
      "name": "DNA template",
      "class": "template",
      "volume_ul": 80,
      "location_hint": "template rack",
      "notes": "optional"
    }
  ],
  "actions": [
    {
      "action_type": "transfer",
      "reagent": "DNA template",
      "volume_ul": 10,
      "source_hint": "template rack",
      "destination_hint": "PCR plate",
      "repetitions": null,
      "constraints": ["fresh tip for each sample"],
      "description": "original step text"
    }
  ],
  "ambiguities": ["missing well map"]
}

Allowed reagent classes: template, master_mix, primer, water, buffer, enzyme,
dye, salt, unknown.
Allowed action types: transfer, mix, delay, temperature, centrifuge, vortex,
incubate, comment.

Important:
- Extract structure only. Never generate Python code.
- Preserve ambiguity instead of guessing hidden scientific details.
- If a protocol says "each sample", "each well", or "corresponding well",
  set sample_count if it is stated; otherwise use 8 and add an ambiguity.
- Use microliters for volume_ul.
"""


def parse_protocol(raw_text: str, source_url: Optional[str] = None) -> ParsedProtocol:
    """
    Parse protocol text into typed semantic actions.

    OpenRouter is required. The parser intentionally fails loudly if the API key,
    model, schema support, or network call is unavailable.
    """

    try:
        data = openrouter_json(
            SYSTEM_PROMPT,
            _parser_user_prompt(raw_text),
        )
        parsed = _parsed_from_llm_data(data, raw_text, source_url)
        if parsed.actions:
            return parsed
        raise OpenRouterUnavailable("OpenRouter returned zero executable actions")
    except OpenRouterUnavailable:
        raise


def parse_protocol_with_llm_detail(raw_text: str) -> Dict[str, Any]:
    """Return the raw OpenRouter JSON parse for inspection/debugging."""

    return openrouter_json(
        SYSTEM_PROMPT,
        _parser_user_prompt(raw_text, detail=True),
    )


def _parser_user_prompt(raw_text: str, *, detail: bool = False) -> str:
    retrieved = context_block(raw_text, top_k=5)
    task = "detailed JSON" if detail else "JSON"
    if retrieved:
        return (
            f"{retrieved}\n\n"
            f"Now parse this target protocol into {task} for ProtocolIR. "
            f"Use retrieved context only to resolve labware/action conventions; "
            f"do not copy unrelated protocol steps.\n\n{raw_text}"
        )
    return f"Parse this protocol into {task} for ProtocolIR:\n\n{raw_text}"

def _parsed_from_llm_data(
    data: Dict[str, Any], raw_text: str, source_url: Optional[str]
) -> ParsedProtocol:
    sample_count = _coerce_sample_count(data.get("sample_count"), raw_text)

    materials = []
    for item in _as_list(data.get("materials")):
        if not isinstance(item, dict):
            continue
        materials.append(
            Material(
                name=str(item.get("name") or "unknown"),
                reagent_class=_coerce_reagent_class(item.get("class") or item.get("reagent_class")),
                volume_ul=_coerce_float(item.get("volume_ul")),
                location_hint=_clean_optional(item.get("location_hint")),
                notes=_clean_optional(item.get("notes")),
            )
        )

    actions = []
    for item in _as_list(data.get("actions") or data.get("steps")):
        if not isinstance(item, dict):
            continue
        actions.append(
            SemanticAction(
                action_type=_coerce_action_type(item.get("action_type") or item.get("type")),
                reagent=_clean_optional(item.get("reagent")),
                volume_ul=_coerce_float(item.get("volume_ul")),
                source_hint=_clean_optional(item.get("source_hint") or item.get("source")),
                destination_hint=_clean_optional(item.get("destination_hint") or item.get("destination")),
                repetitions=_coerce_int(item.get("repetitions")),
                constraints=[str(v) for v in _as_list(item.get("constraints"))],
                description=str(item.get("description") or ""),
            )
        )

    ambiguities = [str(v) for v in _as_list(data.get("ambiguities"))]
    if sample_count == 8 and _mentions_each_sample(raw_text) and not _sample_count_explicit(raw_text):
        ambiguities.append("Sample count not specified; defaulted to 8 demo wells.")
    biosecurity_findings = screen_materials(materials)
    ambiguities.extend(biosecurity_findings)

    return ParsedProtocol(
        goal=str(data.get("goal") or _infer_goal(raw_text)),
        title=_clean_optional(data.get("title")),
        source=source_url,
        parser_backend="openrouter",
        sample_count=sample_count,
        materials=materials,
        actions=actions,
        ambiguities=ambiguities,
    )


def training_parse_pcr_text(raw_text: str, source_url: Optional[str] = None) -> ParsedProtocol:
    text = " ".join(raw_text.split())
    lower = text.lower()
    sample_count = _coerce_sample_count(None, raw_text)
    ambiguities = []
    materials = []
    actions = []

    if _mentions_each_sample(raw_text) and not _sample_count_explicit(raw_text):
        ambiguities.append("Sample count not specified; defaulted to 8 demo wells.")
    if "well" in lower and not re.search(r"\b[a-h]\s*0?\d{1,2}\b", lower):
        ambiguities.append("Specific well map not specified; defaulted to row-major wells.")

    template_volume = _volume_near(lower, ["dna template", "template", "sample"])
    if "template" in lower or "dna" in lower or "sample" in lower:
        volume = template_volume or 10.0
        materials.append(
            Material(
                name="DNA template",
                reagent_class=ReagentClass.TEMPLATE,
                volume_ul=volume * sample_count,
                location_hint="template rack",
            )
        )
        actions.append(
            SemanticAction(
                action_type=SemanticActionType.TRANSFER,
                reagent="DNA template",
                volume_ul=volume,
                source_hint="template rack",
                destination_hint="PCR plate",
                constraints=["fresh tip for each sample"],
                description=_matching_sentence(raw_text, ["template", "dna", "sample"]),
            )
        )

    master_mix_volume = _volume_near(lower, ["master mix", "pcr mix"])
    if "master mix" in lower or "pcr mix" in lower:
        volume = master_mix_volume or 40.0
        materials.append(
            Material(
                name="PCR master mix",
                reagent_class=ReagentClass.MASTER_MIX,
                volume_ul=volume * sample_count,
                location_hint="master mix rack",
            )
        )
        actions.append(
            SemanticAction(
                action_type=SemanticActionType.TRANSFER,
                reagent="PCR master mix",
                volume_ul=volume,
                source_hint="master mix tube",
                destination_hint="PCR plate",
                constraints=["mix after dispense"],
                description=_matching_sentence(raw_text, ["master mix", "pcr mix"]),
            )
        )

    primer_volume = _volume_near(lower, ["primer"])
    if "primer" in lower:
        volume = primer_volume or 1.0
        materials.append(
            Material(
                name="Primer",
                reagent_class=ReagentClass.PRIMER,
                volume_ul=volume * sample_count,
                location_hint="template rack",
            )
        )
        actions.append(
            SemanticAction(
                action_type=SemanticActionType.TRANSFER,
                reagent="Primer",
                volume_ul=volume,
                source_hint="primer tube",
                destination_hint="PCR plate",
                constraints=["fresh tip for each sample"],
                description=_matching_sentence(raw_text, ["primer"]),
            )
        )

    water_volume = _volume_near(lower, ["water", "nuclease-free water"])
    if "water" in lower:
        volume = water_volume or 10.0
        materials.append(
            Material(
                name="Nuclease-free water",
                reagent_class=ReagentClass.WATER,
                volume_ul=volume * sample_count,
                location_hint="master mix rack",
            )
        )
        actions.append(
            SemanticAction(
                action_type=SemanticActionType.TRANSFER,
                reagent="Nuclease-free water",
                volume_ul=volume,
                source_hint="water tube",
                destination_hint="PCR plate",
                constraints=["fresh tip for each sample"],
                description=_matching_sentence(raw_text, ["water"]),
            )
        )

    if "mix" in lower:
        actions.append(
            SemanticAction(
                action_type=SemanticActionType.MIX,
                volume_ul=min(template_volume or 10.0, 20.0),
                destination_hint="PCR plate",
                repetitions=_repetition_count(lower) or 3,
                constraints=["mix gently"],
                description=_matching_sentence(raw_text, ["mix"]),
            )
        )

    if "ice" in lower or "cold" in lower:
        actions.append(
            SemanticAction(
                action_type=SemanticActionType.INCUBATE,
                destination_hint="PCR plate",
                constraints=["keep cold", "manual ice handling may be required"],
                description=_matching_sentence(raw_text, ["ice", "cold"]),
            )
        )
        ambiguities.append("Cold storage/ice step requires module or manual handling decision.")

    if not actions:
        actions.append(
            SemanticAction(
                action_type=SemanticActionType.COMMENT,
                description="No liquid-handling step could be extracted deterministically.",
            )
        )
        ambiguities.append("Could not extract executable liquid-handling actions.")

    return ParsedProtocol(
        goal=_infer_goal(raw_text),
        title=_infer_title(raw_text),
        source=source_url,
        parser_backend="training_parser",
        sample_count=sample_count,
        materials=materials,
        actions=actions,
        ambiguities=ambiguities,
    )


def _coerce_reagent_class(value: Any) -> ReagentClass:
    text = str(value or "unknown").strip().lower().replace(" ", "_")
    return ReagentClass(text) if text in {item.value for item in ReagentClass} else ReagentClass.UNKNOWN


def _coerce_action_type(value: Any) -> SemanticActionType:
    text = str(value or "comment").strip().lower().replace(" ", "_")
    return (
        SemanticActionType(text)
        if text in {item.value for item in SemanticActionType}
        else SemanticActionType.COMMENT
    )


def _coerce_float(value: Any) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_int(value: Any) -> Optional[int]:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _coerce_sample_count(value: Any, raw_text: str) -> int:
    explicit = _explicit_sample_count(raw_text)
    if explicit:
        return max(1, min(96, explicit))
    coerced = _coerce_int(value)
    return max(1, min(96, coerced or 8))


def _explicit_sample_count(raw_text: str) -> Optional[int]:
    lower = raw_text.lower()
    patterns = [
        r"\b(\d{1,2})\s+(?:samples?|wells?|reactions?)\b",
        r"\bfor\s+(\d{1,2})\s+(?:samples?|wells?|reactions?)\b",
        r"\b(\d{1,2})-well\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, lower)
        if match:
            value = int(match.group(1))
            if value in {24, 48, 96} and "plate" in lower and "sample" not in lower:
                continue
            return value
    if "96-well" in lower and ("each well" in lower or "96 samples" in lower):
        return 96
    return None


def _sample_count_explicit(raw_text: str) -> bool:
    return _explicit_sample_count(raw_text) is not None


def _mentions_each_sample(raw_text: str) -> bool:
    lower = raw_text.lower()
    return any(term in lower for term in ["each sample", "each well", "corresponding well"])


def _volume_near(lower_text: str, terms: Iterable[str]) -> Optional[float]:
    best_value = None
    best_distance = None
    for term in terms:
        for term_match in re.finditer(re.escape(term), lower_text):
            idx = term_match.start()
            start = max(0, idx - 120)
            window = lower_text[start : idx + len(term) + 120]
            matches = list(
                re.finditer(
                    r"(\d+(?:\.\d+)?)\s*(?:ul|\u00b5l|microliter|microliters)",
                    window,
                    re.I,
                )
            )
            for match in matches:
                distance = abs((start + match.start()) - idx)
                if best_distance is None or distance < best_distance:
                    best_distance = distance
                    best_value = float(match.group(1))
    if best_value is not None:
        return best_value
    match = re.search(
        r"(\d+(?:\.\d+)?)\s*(?:ul|\u00b5l|microliter|microliters)",
        lower_text,
        re.I,
    )
    return float(match.group(1)) if match else None


def _repetition_count(lower_text: str) -> Optional[int]:
    match = re.search(r"(\d+)\s+times", lower_text)
    return int(match.group(1)) if match else None


def _matching_sentence(raw_text: str, terms: Iterable[str]) -> str:
    sentences = re.split(r"(?<=[.!?])\s+|\n+", raw_text.strip())
    for sentence in sentences:
        if any(term.lower() in sentence.lower() for term in terms):
            return sentence.strip()
    return ""


def _infer_goal(raw_text: str) -> str:
    lower = raw_text.lower()
    if "qpcr" in lower:
        return "qPCR plate setup"
    if "pcr" in lower:
        return "PCR plate setup"
    if "plate" in lower:
        return "Plate preparation"
    return "Lab protocol execution"


def _infer_title(raw_text: str) -> Optional[str]:
    for line in raw_text.splitlines():
        stripped = line.strip(" #\t")
        if stripped:
            return stripped[:120]
    return None


def _clean_optional(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _as_list(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]
