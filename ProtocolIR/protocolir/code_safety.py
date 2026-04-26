"""Static safety checks for generated Opentrons Python baselines.

These checks are intentionally conservative. They do not replace typed-IR
verification, but they let benchmark scripts inspect direct LLM-generated code
that has no ProtocolIR IR.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass(frozen=True)
class CodeSafetyIssue:
    issue_type: str
    line_no: int
    message: str
    severity: str = "WARNING"


CALL_RE = re.compile(r"(?P<pipette>\w+)\.(?P<method>pick_up_tip|drop_tip|aspirate|dispense|mix)\((?P<args>.*)\)")


def analyze_opentrons_code(script: str) -> List[CodeSafetyIssue]:
    issues: List[CodeSafetyIssue] = []
    has_tip: Dict[str, bool] = {}
    current_volume: Dict[str, float] = {}
    last_dispense_line: Optional[int] = None
    last_dispense_location: Optional[str] = None

    for line_no, line in enumerate(script.splitlines(), 1):
        match = CALL_RE.search(line.strip())
        if not match:
            continue

        pipette = match.group("pipette")
        method = match.group("method")
        args = match.group("args")

        if method == "pick_up_tip":
            has_tip[pipette] = True
            current_volume[pipette] = 0.0
            continue

        if method == "drop_tip":
            if not has_tip.get(pipette, False):
                issues.append(
                    CodeSafetyIssue(
                        "DROP_TIP_WITHOUT_TIP",
                        line_no,
                        f"{pipette} drops a tip without a known attached tip.",
                    )
                )
            has_tip[pipette] = False
            current_volume[pipette] = 0.0
            continue

        volume = _first_number(args)

        if method in {"aspirate", "dispense", "mix"} and not has_tip.get(pipette, False):
            issues.append(
                CodeSafetyIssue(
                    f"{method.upper()}_NO_TIP",
                    line_no,
                    f"{pipette}.{method} occurs before a visible pick_up_tip().",
                    severity="CRITICAL",
                )
            )

        if volume is not None and _pipette_volume_invalid(pipette, volume):
            issues.append(
                CodeSafetyIssue(
                    "PIPETTE_RANGE_VIOLATION",
                    line_no,
                    f"{pipette} attempts {volume:g} uL outside expected range.",
                    severity="CRITICAL",
                )
            )

        if method == "aspirate" and volume is not None:
            current_volume[pipette] = current_volume.get(pipette, 0.0) + volume

        if method == "dispense":
            if volume is not None and volume > current_volume.get(pipette, 0.0) + 1e-9:
                issues.append(
                    CodeSafetyIssue(
                        "DISPENSE_MORE_THAN_ASPIRATED",
                        line_no,
                        f"{pipette} dispenses {volume:g} uL but visible state has less liquid.",
                        severity="CRITICAL",
                    )
                )
            current_volume[pipette] = max(0.0, current_volume.get(pipette, 0.0) - (volume or 0.0))
            if _looks_like_plate_destination(args):
                if last_dispense_line and last_dispense_location:
                    issues.append(
                        CodeSafetyIssue(
                            "MISSING_MIX",
                            last_dispense_line,
                            f"Dispense into {last_dispense_location} was not followed by visible mix().",
                        )
                    )
                last_dispense_line = line_no
                last_dispense_location = _location_text(args)

        if method == "mix" and last_dispense_line:
            last_dispense_line = None
            last_dispense_location = None

    if last_dispense_line and last_dispense_location:
        issues.append(
            CodeSafetyIssue(
                "MISSING_MIX",
                last_dispense_line,
                f"Dispense into {last_dispense_location} was not followed by visible mix().",
            )
        )

    return issues


def issue_counts(issues: List[CodeSafetyIssue]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for issue in issues:
        counts[issue.issue_type] = counts.get(issue.issue_type, 0) + 1
    return counts


def _first_number(args: str) -> Optional[float]:
    match = re.search(r"(?<![\w.])(\d+(?:\.\d+)?)", args)
    return float(match.group(1)) if match else None


def _pipette_volume_invalid(pipette: str, volume: float) -> bool:
    lower = pipette.lower()
    if "p20" in lower:
        return volume < 1.0 or volume > 20.0
    if "p300" in lower:
        return volume < 20.0 or volume > 300.0
    return False


def _looks_like_plate_destination(args: str) -> bool:
    lower = args.lower()
    return "plate" in lower and ("[" in lower or ".wells" in lower or ".well" in lower)


def _location_text(args: str) -> str:
    parts = args.split(",", 1)
    return parts[1].strip() if len(parts) > 1 else args.strip()
