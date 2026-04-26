"""Local biosecurity screening hooks for parsed protocol materials."""

from __future__ import annotations

import re
from typing import Iterable, List

from protocolir.schemas import Material


DNA_RE = re.compile(r"\b[ACGT]{30,}\b", re.I)
WATCH_TERMS = {
    "toxin",
    "botulinum",
    "ricin",
    "anthrax",
    "select agent",
    "virulence",
    "pathogenicity island",
}


def screen_materials(materials: Iterable[Material]) -> List[str]:
    findings: List[str] = []
    for material in materials:
        text = " ".join(
            value
            for value in [material.name, material.notes or "", material.location_hint or ""]
            if value
        )
        lower = text.lower()
        for term in sorted(WATCH_TERMS):
            if term in lower:
                findings.append(f"Biosecurity review term '{term}' found in material '{material.name}'.")
        for match in DNA_RE.findall(text):
            findings.append(
                f"DNA-like sequence of length {len(match)} found in material '{material.name}'; screen externally."
            )
    return findings
