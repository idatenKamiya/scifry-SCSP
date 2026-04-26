#!/usr/bin/env python3
"""One-command judge demo runner for ProtocolIR."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a judge-ready ProtocolIR demo bundle.")
    parser.add_argument(
        "-o",
        "--output",
        default="judge_demo_output",
        help="Output directory for logs and artifacts.",
    )
    parser.add_argument(
        "--skip-train",
        action="store_true",
        help="Skip reward training if models are already present.",
    )
    args = parser.parse_args()

    if not os.getenv("OPENROUTER_API_KEY"):
        print("ERROR: OPENROUTER_API_KEY is not set.")
        print("Set it, then rerun this command.")
        return 2

    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    logs = output / "logs"
    logs.mkdir(parents=True, exist_ok=True)

    commands = [
        ("test_installation", [sys.executable, "test_installation.py"]),
        ("check_openrouter", [sys.executable, "check_openrouter.py"]),
    ]
    if not args.skip_train:
        commands.append(("train_reward_model", [sys.executable, "train_reward_model.py"]))
    commands.extend(
        [
            ("main_demo", [sys.executable, "main.py", "--demo", "-o", str(output / "outputs_demo")]),
            (
                "compare_demo",
                [sys.executable, "compare_systems.py", "--demo", "-o", str(output / "comparison_output")],
            ),
        ]
    )

    results: list[tuple[str, int]] = []
    for name, cmd in commands:
        print(f"\n=== Running: {name} ===")
        log_path = logs / f"{name}.log"
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
        log_path.write_text((result.stdout or "") + "\n" + (result.stderr or ""), encoding="utf-8")
        print(f"Exit code: {result.returncode}")
        print(f"Log: {log_path}")
        results.append((name, result.returncode))
        if result.returncode != 0:
            print(f"Stopping early because step failed: {name}")
            break

    summary_lines = [
        "# Judge Demo Summary",
        "",
        f"- Output directory: {output}",
        "",
        "## Step Results",
    ]
    for name, code in results:
        status = "PASS" if code == 0 else "FAIL"
        summary_lines.append(f"- {name}: {status} (exit {code})")

    demo_summary = output / "outputs_demo" / "summary.txt"
    compare_report = output / "comparison_output" / "comparison_report.md"
    cert_path = output / "outputs_demo" / "safety_certificate.json"

    summary_lines.extend(
        [
            "",
            "## Key Artifacts",
            f"- Demo summary: {demo_summary if demo_summary.exists() else 'missing'}",
            f"- Comparison report: {compare_report if compare_report.exists() else 'missing'}",
            f"- Safety certificate: {cert_path if cert_path.exists() else 'missing'}",
        ]
    )

    summary_path = output / "JUDGE_DEMO_SUMMARY.md"
    summary_path.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")
    print(f"\nSummary: {summary_path}")

    return 0 if all(code == 0 for _, code in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())

