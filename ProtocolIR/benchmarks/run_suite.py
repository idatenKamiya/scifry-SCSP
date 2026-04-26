#!/usr/bin/env python3
"""Small benchmark suite for ProtocolIR vs direct LLM baseline."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


CASES = [
    "Prepare 8 PCR samples. Add 10 uL DNA template to each well. Add 40 uL PCR master mix. Mix gently 3 times.",
    "Set up 12 qPCR reactions. Add 5 uL template, 15 uL qPCR master mix, and mix each reaction.",
    "Prepare 6 PCR wells. Add 2 uL primer, 8 uL water, 10 uL template, and 30 uL master mix. Mix after dispense.",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run ProtocolIR benchmark suite.")
    parser.add_argument("--cases", type=int, default=len(CASES), help="Number of built-in cases to run.")
    parser.add_argument("--output", default="benchmarks/results", help="Output directory.")
    args = parser.parse_args()

    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    rows = []

    for idx, protocol in enumerate(CASES[: args.cases], 1):
        case_dir = output / f"case_{idx:02d}"
        case_dir.mkdir(parents=True, exist_ok=True)
        input_path = case_dir / "protocol.txt"
        input_path.write_text(protocol, encoding="utf-8")
        result = subprocess.run(
            [sys.executable, "compare_systems.py", str(input_path), "-o", str(case_dir / "comparison")],
            capture_output=True,
            text=True,
            timeout=300,
        )
        rows.append(
            {
                "case": idx,
                "returncode": result.returncode,
                "comparison_report": str(case_dir / "comparison" / "comparison_report.md"),
                "stdout_tail": result.stdout[-1000:],
                "stderr_tail": result.stderr[-1000:],
            }
        )

    (output / "results.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    (output / "summary.md").write_text(_summary(rows), encoding="utf-8")
    print(_summary(rows))
    return 0 if all(row["returncode"] == 0 for row in rows) else 1


def _summary(rows: list[dict]) -> str:
    passed = sum(1 for row in rows if row["returncode"] == 0)
    lines = [
        "# ProtocolIR Benchmark Suite",
        "",
        f"- Cases: {len(rows)}",
        f"- ProtocolIR successful comparisons: {passed}/{len(rows)}",
        "",
        "| Case | Exit Code | Report |",
        "|---:|---:|---|",
    ]
    for row in rows:
        lines.append(f"| {row['case']} | {row['returncode']} | {row['comparison_report']} |")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
