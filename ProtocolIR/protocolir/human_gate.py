"""Human-in-the-loop checkpoints for safety-critical protocol execution."""

from __future__ import annotations

import os
from typing import Any


def human_gate_checkpoint(name: str, summary: str, *, require: bool | None = None) -> bool:
    """Approve a checkpoint when human gates are required.

    Set PROTOCOLIR_REQUIRE_HUMAN=1 to force interactive approval in CLI runs.
    Non-interactive automated demos keep a recorded checkpoint without blocking.
    """

    require_gate = require if require is not None else os.getenv("PROTOCOLIR_REQUIRE_HUMAN") == "1"
    if not require_gate:
        return True
    print("\n" + "=" * 72)
    print(f"HUMAN GATE: {name}")
    print("=" * 72)
    print(summary)
    answer = input("Approve this checkpoint? Type YES to continue: ").strip()
    return answer == "YES"


def summarize_checkpoint(payload: Any, max_chars: int = 2000) -> str:
    text = str(payload)
    return text if len(text) <= max_chars else text[:max_chars] + "\n... [truncated]"
