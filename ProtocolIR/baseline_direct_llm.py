#!/usr/bin/env python3
"""Direct LLM-to-Opentrons baseline for ProtocolIR comparisons."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import List

from protocolir.code_safety import analyze_opentrons_code, issue_counts
from protocolir.llm import openrouter_text
from protocolir.simulator import simulate_opentrons_script


BASELINE_SYSTEM_PROMPT = """You are a lab automation coding assistant.
Write only one complete Opentrons Python Protocol API v2 script.
Do not write markdown or explanation.
Use an OT-2 with p20_single_gen2 on left, p300_single_gen2 on right, a Bio-Rad 96-well PCR plate,
NEST 1.5 mL tube racks, and Opentrons tip racks when appropriate.
"""


DEMO_PROTOCOL = """
PCR Master Mix Setup

Materials:
- DNA template samples
- PCR master mix

Steps:
1. Prepare 8 samples in a 96-well PCR plate.
2. Add 10 uL of DNA template to the corresponding sample well.
3. Add 40 uL of PCR master mix to each well.
4. Mix gently by pipetting up and down 3 times.
5. Keep the plate on ice until thermal cycling.
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Run direct LLM-to-Python baseline.")
    parser.add_argument("input", nargs="?", default=None, help="Input protocol file or raw text.")
    parser.add_argument("-o", "--output", default="baseline_output", help="Output directory.")
    parser.add_argument("--demo", action="store_true", help="Use built-in PCR demo protocol.")
    args = parser.parse_args()

    raw_text = _load_input(args.input, args.demo)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    response = openrouter_text(
        BASELINE_SYSTEM_PROMPT,
        f"Convert this protocol to Opentrons Python:\n\n{raw_text}",
        max_tokens=4096,
        timeout_seconds=120,
    )
    script = _extract_python(response)
    (output_dir / "baseline_protocol.py").write_text(script, encoding="utf-8")
    (output_dir / "baseline_raw_response.txt").write_text(response, encoding="utf-8")

    static_issues = analyze_opentrons_code(script)
    simulation = simulate_opentrons_script(script, timeout_seconds=60)

    report = _report(script, static_issues, simulation)
    (output_dir / "baseline_report.md").write_text(report, encoding="utf-8")
    print(report)
    return 0 if simulation.passed else 1


def _load_input(input_arg: str | None, demo: bool) -> str:
    if demo or not input_arg:
        return DEMO_PROTOCOL
    path = Path(input_arg)
    if path.exists():
        return path.read_text(encoding="utf-8")
    return input_arg


def _extract_python(response: str) -> str:
    fenced = re.search(r"```(?:python)?\s*(.*?)```", response, re.S | re.I)
    script = fenced.group(1) if fenced else response
    script = script.strip()
    if "from opentrons import protocol_api" not in script:
        raise RuntimeError("Direct LLM baseline did not return an Opentrons Python script.")
    compile(script, "<direct_llm_baseline>", "exec")
    return script + "\n"


def _report(script: str, issues: List, simulation) -> str:
    counts = issue_counts(issues)
    lines = [
        "# Direct LLM Baseline Report",
        "",
        f"- Generated script bytes: {len(script)}",
        f"- Simulator status: {'PASS' if simulation.passed else 'FAIL'}",
        f"- Real simulator used: {simulation.used_real_simulator}",
        f"- Simulator commands: {simulation.command_count}",
        f"- Static safety issues: {len(issues)}",
        "",
        "## Static Safety Issue Counts",
        "",
        "| Issue | Count |",
        "|---|---:|",
    ]
    for issue_type, count in sorted(counts.items()):
        lines.append(f"| {issue_type} | {count} |")
    if not counts:
        lines.append("| none_detected | 0 |")

    lines.extend(["", "## First Static Issues", ""])
    for issue in issues[:12]:
        lines.append(f"- {issue.issue_type} at line {issue.line_no}: {issue.message}")
    if not issues:
        lines.append("- None detected by static baseline analyzer.")

    if simulation.errors:
        lines.extend(["", "## Simulator Errors", ""])
        for error in simulation.errors[:10]:
            lines.append(f"- {error}")

    payload = {
        "simulator_passed": simulation.passed,
        "real_simulator_used": simulation.used_real_simulator,
        "command_count": simulation.command_count,
        "static_issue_count": len(issues),
        "static_issue_counts": counts,
    }
    lines.extend(["", "## Machine Summary", "", "```json", json.dumps(payload, indent=2), "```"])
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    sys.exit(main())
