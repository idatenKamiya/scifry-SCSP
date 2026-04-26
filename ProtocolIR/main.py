#!/usr/bin/env python3
"""ProtocolIR command-line entry point."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

import protocolir as pir
from protocolir.audit import create_executive_summary, generate_audit_report
from protocolir.grounder import build_deck_layout
from protocolir.ir_builder import ir_to_dict_list
from protocolir.orchestration import run_protocol_graph
from protocolir.schemas import IROpType, ProtocolPipeline
from protocolir.simulator import validate_script_before_simulation


def process_protocol(
    raw_text: str,
    source_url: Optional[str] = None,
    output_dir: str = "./outputs",
    reward_model: Optional[pir.RewardModel] = None,
    stress_test: bool = False,
) -> ProtocolPipeline:
    """Run the complete reward-guided compiler pipeline."""

    reward_model = reward_model or _load_reward_model()

    _banner("PROTOCOLIR: VERIFIED, REWARD-GUIDED PROTOCOL COMPILER")
    pipeline = run_protocol_graph(
        raw_text,
        source_url=source_url,
        reward_model=reward_model,
        stress_mutator=inject_demo_unsafe_errors if stress_test else None,
    )

    _save_artifacts(pipeline, output_dir)
    _banner("PIPELINE COMPLETE")
    return pipeline


def main() -> None:
    parser = argparse.ArgumentParser(
        description="ProtocolIR: reward-guided compiler for safe lab automation."
    )
    parser.add_argument("input", nargs="?", default=None, help="Input protocol file or raw text.")
    parser.add_argument("-o", "--output", default="./outputs", help="Output directory.")
    parser.add_argument("-u", "--url", default=None, help="Optional source URL.")
    parser.add_argument("--demo", action="store_true", help="Run an 8-sample PCR demo.")
    parser.add_argument(
        "--stress-demo",
        action="store_true",
        help="Run demo with injected unsafe IR errors so repair is visible.",
    )
    parser.add_argument(
        "--cell-culture-demo",
        action="store_true",
        help="Run a cell culture passaging demo (multi-protocol evaluation).",
    )
    args = parser.parse_args()

    if args.demo or args.stress_demo:
        process_protocol(
            _demo_protocol(),
            source_url="demo://pcr_setup",
            output_dir=args.output,
            stress_test=args.stress_demo,
        )
        return

    if args.cell_culture_demo:
        process_protocol(
            _cell_culture_demo_protocol(),
            source_url="demo://cell_culture_passaging",
            output_dir=args.output,
            stress_test=False,
        )
        return

    if args.input:
        input_path = Path(args.input)
        if input_path.exists():
            protocol_text = input_path.read_text(encoding="utf-8")
        else:
            protocol_text = args.input
        process_protocol(protocol_text, source_url=args.url, output_dir=args.output)
        return

    parser.print_help()
    sys.exit(1)


def _save_artifacts(pipeline: ProtocolPipeline, output_dir: str) -> None:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    if pipeline.generated_script:
        (output_path / "protocol.py").write_text(pipeline.generated_script, encoding="utf-8")
        print(f"  Script: {output_path / 'protocol.py'}")

    if pipeline.audit_report:
        (output_path / "audit_report.md").write_text(pipeline.audit_report, encoding="utf-8")
        print(f"  Report: {output_path / 'audit_report.md'}")

    (output_path / "summary.txt").write_text(create_executive_summary(pipeline), encoding="utf-8")
    print(f"  Summary: {output_path / 'summary.txt'}")

    if pipeline.ir_original:
        (output_path / "ir_original.json").write_text(
            json.dumps(ir_to_dict_list(pipeline.ir_original), indent=2),
            encoding="utf-8",
        )
    if pipeline.ir_repaired:
        (output_path / "ir_repaired.json").write_text(
            json.dumps(ir_to_dict_list(pipeline.ir_repaired), indent=2),
            encoding="utf-8",
        )


def inject_demo_unsafe_errors(ir_ops):
    """
    Create a deliberately unsafe trajectory for judge-facing repair demos.

    This simulates the kind of direct-LLM robot code that runs syntactically but
    violates lab semantics: missing tip setup, wrong pipette for 40 uL, and no
    post-dispense mix.
    """

    corrupted = [op.model_copy(deep=True) for op in ir_ops]

    # Remove the first pickup before a transfer.
    for idx, op in enumerate(list(corrupted)):
        if op.op == IROpType.PICK_UP_TIP:
            del corrupted[idx]
            break

    # Force the first 40 uL master-mix transfer onto p20.
    for idx, op in enumerate(corrupted):
        if op.op == IROpType.ASPIRATE and op.volume_ul and op.volume_ul > 20:
            old_pipette = op.pipette
            for window_idx in range(max(0, idx - 1), min(len(corrupted), idx + 4)):
                if corrupted[window_idx].pipette == old_pipette:
                    corrupted[window_idx].pipette = "p20"
            break

    # Remove the first plate mix after a dispense.
    for idx, op in enumerate(list(corrupted)):
        if op.op == IROpType.MIX and op.location and op.location.startswith("plate/"):
            del corrupted[idx]
            break

    return corrupted


def _print_violation_summary(violations, prefix: str = "  Found") -> None:
    critical = sum(1 for violation in violations if violation.severity == "CRITICAL")
    warnings = sum(1 for violation in violations if violation.severity == "WARNING")
    print(f"{prefix}: {len(violations)} total ({critical} critical, {warnings} warning)")
    for violation in violations[:5]:
        print(f"    - {violation.violation_type}: {violation.message}")
    if len(violations) > 5:
        print(f"    - ... {len(violations) - 5} more")


def _banner(text: str) -> None:
    print("\n" + "=" * 72)
    print(text)
    print("=" * 72)


def _load_reward_model() -> pir.RewardModel:
    learned_path = Path("models/learned_weights.json")
    report_path = Path("models/reward_posterior_report.md")
    if report_path.exists():
        report = report_path.read_text(encoding="utf-8", errors="replace")
        if "Diagnostic status: PASS" not in report:
            raise RuntimeError(
                "Bayesian reward posterior is not diagnostic-clean. "
                "Inspect models/reward_posterior_report.md and rerun train_reward_model.py."
            )
    if learned_path.exists():
        print(f"Loaded Bayesian reward posterior mean from {learned_path}")
        return pir.RewardModel.load(str(learned_path))
    raise RuntimeError(
        "Missing models/learned_weights.json. Run python train_reward_model.py before running main.py."
    )


def _demo_protocol() -> str:
    return """
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


def _cell_culture_demo_protocol() -> str:
    return """
Cell Culture Plate Media Exchange

Materials:
- cell culture samples
- fresh media
- PBS buffer

Steps:
1. Prepare 6 wells containing adherent cells in a 96-well plate.
2. Add 50 uL PBS buffer to each well.
3. Add 100 uL fresh media to each well.
4. Mix gently without disturbing cells.
"""


if __name__ == "__main__":
    main()
