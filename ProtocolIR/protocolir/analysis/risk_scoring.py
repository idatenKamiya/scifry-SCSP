"""Risk severity scoring for ProtocolIR verifier outputs."""

from __future__ import annotations

from typing import Dict, Iterable

from protocolir.schemas import Violation


VIOLATION_SEVERITY = {
    "ASPIRATE_NO_TIP": {
        "severity": "CRITICAL",
        "impact_usd": 500000,
        "reason": "Pipette can be contaminated and invalidate downstream samples.",
    },
    "DISPENSE_NO_TIP": {
        "severity": "CRITICAL",
        "impact_usd": 500000,
        "reason": "Destination can be contaminated and invalidate the batch.",
    },
    "CROSS_CONTAMINATION": {
        "severity": "CRITICAL",
        "impact_usd": 250000,
        "reason": "A tip carrying multiple reagents can corrupt reaction chemistry.",
    },
    "WELL_OVERFLOW": {
        "severity": "HIGH",
        "impact_usd": 100000,
        "reason": "Spillage risks deck contamination and equipment damage.",
    },
    "PIPETTE_RANGE_VIOLATION": {
        "severity": "MEDIUM",
        "impact_usd": 50000,
        "reason": "Volume outside calibrated range makes measurements unreliable.",
    },
    "DROP_TIP_WITH_LIQUID": {
        "severity": "MEDIUM",
        "impact_usd": 50000,
        "reason": "Dropping a liquid-filled tip can lose reagents and break stoichiometry.",
    },
    "MISSING_MIX": {
        "severity": "MEDIUM",
        "impact_usd": 30000,
        "reason": "Incomplete mixing can cause non-uniform concentrations.",
    },
}


def score_violations(violations: Iterable[Violation]) -> Dict[str, object]:
    violations = list(violations)
    if not violations:
        return {
            "total_violations": 0,
            "critical_count": 0,
            "high_count": 0,
            "medium_count": 0,
            "total_impact_usd": 0,
            "risk_level": "SAFE",
            "violations_by_type": {},
            "severity_details": {},
        }

    violations_by_type: Dict[str, int] = {}
    for violation in violations:
        vtype = violation.violation_type
        violations_by_type[vtype] = violations_by_type.get(vtype, 0) + 1

    def _count(level: str) -> int:
        return sum(
            count
            for vtype, count in violations_by_type.items()
            if VIOLATION_SEVERITY.get(vtype, {}).get("severity") == level
        )

    critical_count = _count("CRITICAL")
    high_count = _count("HIGH")
    medium_count = _count("MEDIUM")

    total_impact = sum(
        VIOLATION_SEVERITY.get(vtype, {}).get("impact_usd", 0) * count
        for vtype, count in violations_by_type.items()
    )

    risk_level = "LOW"
    if critical_count > 0:
        risk_level = "CRITICAL"
    elif high_count > 0:
        risk_level = "HIGH"
    elif medium_count > 0:
        risk_level = "MEDIUM"

    return {
        "total_violations": len(violations),
        "critical_count": critical_count,
        "high_count": high_count,
        "medium_count": medium_count,
        "total_impact_usd": total_impact,
        "risk_level": risk_level,
        "violations_by_type": violations_by_type,
        "severity_details": {
            vtype: {
                "count": count,
                "severity": VIOLATION_SEVERITY.get(vtype, {}).get("severity", "UNKNOWN"),
                "impact_per_violation": VIOLATION_SEVERITY.get(vtype, {}).get("impact_usd", 0),
                "reason": VIOLATION_SEVERITY.get(vtype, {}).get("reason", "Manual review required."),
            }
            for vtype, count in violations_by_type.items()
        },
    }


def get_severity_color(severity: str) -> str:
    colors = {
        "CRITICAL": "#e74c3c",
        "HIGH": "#f39c12",
        "MEDIUM": "#f1c40f",
        "LOW": "#2ecc71",
        "UNKNOWN": "#95a5a6",
    }
    return colors.get(severity, "#95a5a6")

