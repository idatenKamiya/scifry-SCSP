"""Root-cause dependency analysis for verifier violations."""

from __future__ import annotations

from typing import Dict, Iterable, List

from protocolir.schemas import Violation


def analyze_dependencies(violations: Iterable[Violation]) -> Dict[str, object]:
    violations = list(violations)
    if not violations:
        return {"chains": [], "total_chains": 0, "root_causes": 0}

    present = {violation.violation_type for violation in violations}
    chains: List[Dict[str, object]] = []

    if "ASPIRATE_NO_TIP" in present or "DISPENSE_NO_TIP" in present:
        cascading = []
        if "ASPIRATE_NO_TIP" in present:
            cascading.append("ASPIRATE_NO_TIP: aspirate attempted with no tip attached")
        if "DISPENSE_NO_TIP" in present:
            cascading.append("DISPENSE_NO_TIP: dispense attempted with no tip attached")
        chains.append(
            {
                "root_cause": "Missing tip-attachment step before liquid handling",
                "reason": "Pipette state enters aspirate/dispense operations without a tip.",
                "cascading_violations": cascading,
                "impact": "High contamination risk and batch invalidation.",
                "fix": "Insert PickUpTip before first aspirate and enforce tip state transitions.",
                "severity": "CRITICAL",
            }
        )

    if "CROSS_CONTAMINATION" in present:
        chains.append(
            {
                "root_cause": "Tip reuse across different reagents",
                "reason": "Tip lineage shows reagent switches without fresh-tip boundaries.",
                "cascading_violations": [
                    "CROSS_CONTAMINATION: reagent carryover between samples/steps",
                    "Potential downstream assay corruption from mixed chemistry",
                ],
                "impact": "Potential experiment invalidation due to reagent carryover.",
                "fix": "Insert DropTip + PickUpTip between incompatible reagent transitions.",
                "severity": "CRITICAL",
            }
        )

    if "WELL_OVERFLOW" in present or "TIP_OVER_CAPACITY" in present:
        chains.append(
            {
                "root_cause": "Volume planning exceeds physical capacities",
                "reason": "Dispense/aspirate plans exceed well or tip capacity bounds.",
                "cascading_violations": [
                    "WELL_OVERFLOW/TIP_OVER_CAPACITY: physical limit violations",
                    "Potential deck spill and contamination cascade",
                ],
                "impact": "Operational failure and possible hardware contamination.",
                "fix": "Split transfers and enforce capacity-aware scheduling.",
                "severity": "HIGH",
            }
        )

    if "PIPETTE_RANGE_VIOLATION" in present:
        chains.append(
            {
                "root_cause": "Incompatible pipette selection for requested volume",
                "reason": "Requested transfer volume outside pipette calibrated range.",
                "cascading_violations": [
                    "PIPETTE_RANGE_VIOLATION: inaccurate or unsafe volume request",
                ],
                "impact": "Reduced accuracy and potential experiment drift.",
                "fix": "Select a compatible pipette or split volume into safe increments.",
                "severity": "MEDIUM",
            }
        )

    return {
        "chains": chains,
        "total_chains": len(chains),
        "root_causes": len({chain["root_cause"] for chain in chains}),
    }


def get_recommended_fix(violation_type: str) -> str:
    fixes = {
        "ASPIRATE_NO_TIP": "Insert PickUpTip before aspirate.",
        "DISPENSE_NO_TIP": "Insert PickUpTip before dispense.",
        "MIX_NO_TIP": "Insert PickUpTip before mix.",
        "CROSS_CONTAMINATION": "Insert DropTip + PickUpTip between reagent changes.",
        "WELL_OVERFLOW": "Reduce per-dispense volume or distribute across wells.",
        "TIP_OVER_CAPACITY": "Dispense before aspirating more, or split the transfer.",
        "PIPETTE_RANGE_VIOLATION": "Switch to a compatible pipette or split volume.",
        "DROP_TIP_WITH_LIQUID": "Dispense residual liquid before dropping the tip.",
        "MISSING_MIX": "Insert a mix step immediately after dispense.",
    }
    return fixes.get(violation_type, "Manual protocol review required.")
