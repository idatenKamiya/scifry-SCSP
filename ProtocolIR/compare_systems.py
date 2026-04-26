#!/usr/bin/env python3
"""Run ProtocolIR and direct-LLM baseline on the same protocol."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path


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
    parser = argparse.ArgumentParser(description="Compare ProtocolIR with direct LLM baseline.")
    parser.add_argument("input", nargs="?", default=None, help="Input protocol file or raw text.")
    parser.add_argument("-o", "--output", default="comparison_output", help="Output directory.")
    parser.add_argument("--demo", action="store_true", help="Use built-in PCR demo protocol.")
    args = parser.parse_args()

    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    protocol_path = output / "input_protocol.txt"
    protocol_path.write_text(_load_input(args.input, args.demo), encoding="utf-8")

    baseline_dir = _fresh_dir(output / "direct_llm")
    protocolir_dir = _fresh_dir(output / "protocolir")

    baseline_cmd = [sys.executable, "baseline_direct_llm.py", str(protocol_path), "-o", str(baseline_dir)]
    protocolir_cmd = [sys.executable, "main.py", str(protocol_path), "-o", str(protocolir_dir)]

    baseline = _run(baseline_cmd)
    protocolir = _run(protocolir_cmd)

    summary = _build_summary(baseline, protocolir, baseline_dir, protocolir_dir)
    (output / "comparison_report.md").write_text(summary, encoding="utf-8")
    print(summary)
    return 0 if protocolir.returncode == 0 else 1


def _load_input(input_arg: str | None, demo: bool = False) -> str:
    if demo or not input_arg:
        return DEMO_PROTOCOL
    path = Path(input_arg)
    if path.exists():
        return path.read_text(encoding="utf-8")
    return input_arg


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=240)


def _fresh_dir(path: Path) -> Path:
    if path.exists():
        try:
            shutil.rmtree(path)
        except PermissionError:
            path = path.with_name(f"{path.name}_{time.strftime('%Y%m%d_%H%M%S')}")
    path.mkdir(parents=True, exist_ok=True)
    return path


def _build_summary(baseline, protocolir, baseline_dir: Path, protocolir_dir: Path) -> str:
    baseline_metrics = _baseline_metrics(baseline_dir)
    protocolir_metrics = _protocolir_metrics(protocolir_dir)
    rows = [
        ("Command exit code", baseline.returncode, protocolir.returncode),
        ("Real simulator pass", baseline_metrics["real_sim_pass"], protocolir_metrics["real_sim_pass"]),
        ("Static/built-in safety issues", baseline_metrics["static_issues"], protocolir_metrics["violations_after"]),
        ("Violations before repair", "N/A", protocolir_metrics["violations_before"]),
        ("Violations after repair", "N/A", protocolir_metrics["violations_after"]),
        ("Repairs applied", "N/A", protocolir_metrics["repairs"]),
        ("Commands", baseline_metrics["commands"], protocolir_metrics["commands"]),
    ]
    lines = [
        "# ProtocolIR vs Direct LLM Comparison",
        "",
        "| Metric | Direct LLM Baseline | ProtocolIR |",
        "|---|---:|---:|",
    ]
    for metric, baseline_value, protocolir_value in rows:
        lines.append(f"| {metric} | {baseline_value} | {protocolir_value} |")

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- Direct LLM baseline is allowed to write Opentrons Python directly.",
            "- ProtocolIR constrains the LLM to semantic JSON, then verifies and repairs typed IR before compilation.",
            "- Static baseline issues are conservative code-level checks, not a replacement for ProtocolIR typed-IR verification.",
            "",
            "## Baseline stderr/stdout tail",
            "",
            "```text",
            (baseline.stdout + baseline.stderr)[-3000:],
            "```",
            "",
            "## ProtocolIR stderr/stdout tail",
            "",
            "```text",
            (protocolir.stdout + protocolir.stderr)[-3000:],
            "```",
        ]
    )
    return "\n".join(lines) + "\n"


def _baseline_metrics(path: Path) -> dict:
    report = path / "baseline_report.md"
    if not report.exists():
        return {"real_sim_pass": False, "static_issues": "N/A", "commands": "N/A"}
    text = report.read_text(encoding="utf-8", errors="replace")
    payload = _json_block(text)
    return {
        "real_sim_pass": bool(payload.get("simulator_passed") and payload.get("real_simulator_used")),
        "static_issues": payload.get("static_issue_count", "N/A"),
        "commands": payload.get("command_count", "N/A"),
    }


def _protocolir_metrics(path: Path) -> dict:
    summary = path / "summary.txt"
    if not summary.exists():
        return {
            "real_sim_pass": False,
            "violations_before": "N/A",
            "violations_after": "N/A",
            "repairs": "N/A",
            "commands": "N/A",
        }
    text = summary.read_text(encoding="utf-8", errors="replace")
    return {
        "real_sim_pass": "Status: PASS" in text,
        "violations_before": _line_value(text, "Violations before repair"),
        "violations_after": _line_value(text, "Violations after repair"),
        "repairs": _line_value(text, "Repairs applied"),
        "commands": _line_value(text, "Commands to execute"),
    }


def _json_block(text: str) -> dict:
    marker = "```json"
    if marker not in text:
        return {}
    block = text.split(marker, 1)[1].split("```", 1)[0]
    return json.loads(block)


def _line_value(text: str, label: str) -> str:
    prefix = f"{label}:"
    for line in text.splitlines():
        if line.startswith(prefix):
            return line.split(":", 1)[1].strip()
    return "N/A"


if __name__ == "__main__":
    sys.exit(main())
