"""Machine-readable safety certificate utilities."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from protocolir.schemas import Violation


def generate_certificate(
    protocol_name: str,
    violations_before: Iterable[Violation],
    violations_after: Iterable[Violation],
    *,
    coverage: float = 0.95,
) -> dict:
    before = list(violations_before)
    after = list(violations_after)
    certified = len(after) == 0
    return {
        "protocol": protocol_name,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "certified": certified,
        "coverage_guarantee": coverage if certified else None,
        "violations_before": len(before),
        "violations_after": len(after),
        "violation_types_found": sorted({violation.violation_type for violation in before}),
        "verdict": "SAFE" if certified else "UNSAFE",
    }


def save_certificate_json(certificate: dict, output_path: str) -> str:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(certificate, indent=2), encoding="utf-8")
    return str(path)

