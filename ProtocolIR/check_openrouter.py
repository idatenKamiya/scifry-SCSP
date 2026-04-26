#!/usr/bin/env python3
"""Fail-fast OpenRouter connectivity and structured-output check."""

from __future__ import annotations

import os
import sys

from protocolir.parser import parse_protocol


SMOKE_PROTOCOL = (
    "Prepare 2 PCR samples. Add 10 uL DNA template to each well. "
    "Add 40 uL PCR master mix to each well. Mix gently 3 times."
)


def main() -> int:
    model = os.getenv("PROTOCOLIR_MODEL", "openrouter/free")
    if not os.getenv("OPENROUTER_API_KEY"):
        print("FAIL: OPENROUTER_API_KEY is not set")
        return 1

    try:
        parsed = parse_protocol(SMOKE_PROTOCOL, source_url="smoke://openrouter")
    except Exception as exc:
        print("FAIL: OpenRouter structured extraction did not pass")
        print(f"Model: {model}")
        print(f"Error: {exc}")
        return 1

    print("OPENROUTER OK")
    print(f"Model: {model}")
    print(f"Parser backend: {parsed.parser_backend}")
    print(f"Goal: {parsed.goal}")
    print(f"Samples: {parsed.sample_count}")
    print(f"Actions: {len(parsed.actions)}")
    print(f"Materials: {len(parsed.materials)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
