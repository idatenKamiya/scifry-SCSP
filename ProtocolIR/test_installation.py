#!/usr/bin/env python3
"""Verify that ProtocolIR imports and the demo path are usable."""

import importlib
import sys


REQUIRED_DEPENDENCIES = ["pydantic", "numpy", "opentrons"]
OPTIONAL_DEPENDENCIES = ["requests", "dotenv"]
MODULES = [
    "protocolir.schemas",
    "protocolir.llm",
    "protocolir.parser",
    "protocolir.rag",
    "protocolir.biosecurity",
    "protocolir.grounder",
    "protocolir.ir_builder",
    "protocolir.verifier",
    "protocolir.features",
    "protocolir.bayesian_irl",
    "protocolir.bayesian_irl_pymc",
    "protocolir.reward_model",
    "protocolir.repair",
    "protocolir.compiler",
    "protocolir.simulator",
    "protocolir.audit",
    "protocolir.orchestration",
    "protocolir.code_safety",
    "protocolir.ast_extractor",
    "protocolir.precise_repair",
    "protocolir.human_gate",
    "protocolir.contamination_graph",
]


def main() -> int:
    print("=" * 72)
    print("PROTOCOLIR INSTALLATION TEST")
    print("=" * 72)

    ok = True
    print("\nRequired dependencies:")
    for dep in REQUIRED_DEPENDENCIES:
        try:
            importlib.import_module(dep)
            print(f"  OK {dep}")
        except ImportError as exc:
            print(f"  FAIL {dep}: {exc}")
            ok = False

    print("\nOptional dependencies:")
    for dep in OPTIONAL_DEPENDENCIES:
        try:
            importlib.import_module(dep)
            print(f"  OK {dep}")
        except ImportError:
            print(f"  SKIP {dep} (only needed for data fetching)")

    print("\nProtocolIR modules:")
    for module in MODULES:
        try:
            importlib.import_module(module)
            print(f"  OK {module}")
        except ImportError as exc:
            print(f"  FAIL {module}: {exc}")
            ok = False

    print("\nOpenRouter configuration:")
    print("  Set OPENROUTER_API_KEY for strict live LLM extraction.")
    print("  The main parser stops the run if OpenRouter is missing or invalid.")

    print("\n" + "=" * 72)
    print("ALL CHECKS PASSED" if ok else "SOME CHECKS FAILED")
    print("=" * 72)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
