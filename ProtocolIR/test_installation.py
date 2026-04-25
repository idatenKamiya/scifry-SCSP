#!/usr/bin/env python3
"""
Test script to verify ProtocolIR installation and dependencies.
Run with: python3 test_installation.py
"""

import sys
import importlib

print("=" * 70)
print("PROTOCOLIR INSTALLATION TEST")
print("=" * 70)

dependencies = [
    "anthropic",
    "pydantic",
    "numpy",
    "sklearn",
    "pandas",
    "matplotlib",
]

print("\nChecking dependencies...")

all_ok = True
for dep in dependencies:
    try:
        if dep == "sklearn":
            importlib.import_module("sklearn")
        else:
            importlib.import_module(dep)
        print(f"  ✓ {dep}")
    except ImportError as e:
        print(f"  ✗ {dep}: {e}")
        all_ok = False

print("\nChecking ProtocolIR modules...")

protocolir_modules = [
    "protocolir.schemas",
    "protocolir.parser",
    "protocolir.grounder",
    "protocolir.ir_builder",
    "protocolir.verifier",
    "protocolir.features",
    "protocolir.reward_model",
    "protocolir.repair",
    "protocolir.compiler",
    "protocolir.simulator",
    "protocolir.audit",
]

for module in protocolir_modules:
    try:
        importlib.import_module(module)
        print(f"  ✓ {module}")
    except ImportError as e:
        print(f"  ✗ {module}: {e}")
        all_ok = False

print("\n" + "=" * 70)

if all_ok:
    print("✓ ALL CHECKS PASSED - Ready to use ProtocolIR!")
    print("\nNext steps:")
    print("  1. Set your API key: export ANTHROPIC_API_KEY='your_key'")
    print("  2. Run demo: python3 main.py --demo")
    print("  3. Read QUICKSTART.md for usage examples")
    print("=" * 70)
    sys.exit(0)
else:
    print("✗ SOME CHECKS FAILED - Please install missing dependencies")
    print("  Run: pip install -r requirements.txt")
    print("=" * 70)
    sys.exit(1)
