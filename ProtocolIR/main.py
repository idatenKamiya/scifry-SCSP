#!/usr/bin/env python3
"""
ProtocolIR Main Entry Point
End-to-end protocol compilation pipeline.
"""

import argparse
import sys
from pathlib import Path

import protocolir as pir
from protocolir.schemas import ProtocolPipeline
from protocolir.audit import generate_audit_report, create_executive_summary
from protocolir.simulator import validate_script_before_simulation


def process_protocol(
    raw_text: str,
    source_url: str = None,
    output_dir: str = "./outputs",
    reward_model: pir.RewardModel = None,
) -> ProtocolPipeline:
    """
    Full pipeline: Parse → Ground → IR → Verify → Repair → Compile → Simulate → Report.

    Args:
        raw_text: Raw protocol text
        source_url: Optional source URL
        output_dir: Output directory for artifacts
        reward_model: Reward model for scoring

    Returns:
        Completed ProtocolPipeline
    """

    if reward_model is None:
        reward_model = pir.learn_reward_heuristically()

    pipeline = ProtocolPipeline(raw_text=raw_text, source_url=source_url)

    print("\n" + "=" * 70)
    print("PROTOCOLIR: REWARD-GUIDED PROTOCOL COMPILER")
    print("=" * 70)

    # Step 1: Parse
    print("\n[1/9] PARSING PROTOCOL...")
    try:
        pipeline.parsed = pir.parse_protocol(raw_text, source_url)
        print(f"  ✓ Goal: {pipeline.parsed.goal}")
        print(f"  ✓ Materials: {len(pipeline.parsed.materials)}")
        print(f"  ✓ Actions: {len(pipeline.parsed.actions)}")
        if pipeline.parsed.ambiguities:
            print(f"  ⚠ Ambiguities: {len(pipeline.parsed.ambiguities)}")
    except Exception as e:
        print(f"  ✗ Parsing failed: {e}")
        return pipeline

    # Step 2: Ground
    print("\n[2/9] GROUNDING TO DECK...")
    try:
        pipeline.grounded = pir.ground_actions(pipeline.parsed)
        print(f"  ✓ Grounded {len(pipeline.grounded)} actions")
    except Exception as e:
        print(f"  ✗ Grounding failed: {e}")
        return pipeline

    # Step 3: Build IR
    print("\n[3/9] BUILDING TYPED IR...")
    try:
        pipeline.ir_original = pir.build_ir(pipeline.grounded)
        print(f"  ✓ Built {len(pipeline.ir_original)} IR operations")
    except Exception as e:
        print(f"  ✗ IR building failed: {e}")
        return pipeline

    # Step 4: Verify
    print("\n[4/9] VERIFYING SAFETY CONSTRAINTS...")
    try:
        pipeline.violations = pir.verify_ir(pipeline.ir_original)
        if pipeline.violations:
            print(f"  ⚠ Found {len(pipeline.violations)} violations")
            for v in pipeline.violations[:3]:
                print(f"    - {v.violation_type}: {v.message}")
            if len(pipeline.violations) > 3:
                print(f"    ... and {len(pipeline.violations) - 3} more")
        else:
            print(f"  ✓ No violations detected")
    except Exception as e:
        print(f"  ✗ Verification failed: {e}")
        return pipeline

    # Step 5: Extract features and score
    print("\n[5/9] SCORING TRAJECTORY...")
    try:
        features_before = pir.extract_trajectory_features(
            pipeline.ir_original, pipeline.violations
        )
        score_before = reward_model.score_trajectory(features_before)
        pipeline.reward_before = score_before.total_score
        print(f"  Reward score (before repair): {pipeline.reward_before:.1f}")
    except Exception as e:
        print(f"  ✗ Scoring failed: {e}")
        pipeline.reward_before = 0

    # Step 6: Repair
    print("\n[6/9] REPAIRING VIOLATIONS...")
    try:
        if pipeline.violations:
            pipeline.ir_repaired, pipeline.repairs_applied, remaining = (
                pir.repair_iteratively(pipeline.ir_original, pipeline.violations, max_iterations=3)
            )
            print(f"  ✓ Applied {len(pipeline.repairs_applied)} repairs")
            if remaining:
                print(f"  ⚠ {len(remaining)} violations remain (escalated)")
                pipeline.violations = remaining
            else:
                print(f"  ✓ All violations resolved")
        else:
            pipeline.ir_repaired = pipeline.ir_original
            print(f"  ✓ No repairs needed")

        # Re-score after repair
        features_after = pir.extract_trajectory_features(
            pipeline.ir_repaired, pipeline.violations
        )
        score_after = reward_model.score_trajectory(features_after)
        pipeline.reward_after = score_after.total_score
        print(f"  Reward score (after repair): {pipeline.reward_after:.1f}")

    except Exception as e:
        print(f"  ✗ Repair failed: {e}")
        pipeline.ir_repaired = pipeline.ir_original

    # Step 7: Compile
    print("\n[7/9] COMPILING TO OPENTRONS...")
    try:
        pipeline.generated_script = pir.compile_to_opentrons(pipeline.ir_repaired)

        # Validate before simulating
        is_valid, issues = validate_script_before_simulation(pipeline.generated_script)
        if is_valid:
            print(f"  ✓ Generated valid Opentrons script ({len(pipeline.generated_script)} bytes)")
        else:
            print(f"  ⚠ Script has issues: {issues}")

    except Exception as e:
        print(f"  ✗ Compilation failed: {e}")
        return pipeline

    # Step 8: Simulate
    print("\n[8/9] SIMULATING PROTOCOL...")
    try:
        pipeline.simulation_result = pir.simulate_opentrons_script(
            pipeline.generated_script
        )
        if pipeline.simulation_result.passed:
            print(f"  ✓ Simulation PASSED")
            print(f"    - Commands: {pipeline.simulation_result.command_count}")
            print(f"    - Aspirates: {pipeline.simulation_result.aspirate_count}")
            print(f"    - Dispenses: {pipeline.simulation_result.dispense_count}")
        else:
            print(f"  ✗ Simulation FAILED")
            if pipeline.simulation_result.errors:
                for error in pipeline.simulation_result.errors[:2]:
                    print(f"    - {error}")

    except Exception as e:
        print(f"  ✗ Simulation failed: {e}")

    # Step 9: Generate report
    print("\n[9/9] GENERATING AUDIT REPORT...")
    try:
        pipeline.audit_report = generate_audit_report(pipeline)
        print(f"  ✓ Audit report generated")
    except Exception as e:
        print(f"  ✗ Report generation failed: {e}")

    # Save artifacts
    print("\n" + "=" * 70)
    print("SAVING ARTIFACTS...")
    print("=" * 70)

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    if pipeline.generated_script:
        script_path = output_path / "protocol.py"
        with open(script_path, "w") as f:
            f.write(pipeline.generated_script)
        print(f"  ✓ Script: {script_path}")

    if pipeline.audit_report:
        report_path = output_path / "audit_report.md"
        with open(report_path, "w") as f:
            f.write(pipeline.audit_report)
        print(f"  ✓ Report: {report_path}")

    summary = create_executive_summary(pipeline)
    summary_path = output_path / "summary.txt"
    with open(summary_path, "w") as f:
        f.write(summary)
    print(f"  ✓ Summary: {summary_path}")

    print("\n" + "=" * 70)
    print("PIPELINE COMPLETE")
    print("=" * 70)

    return pipeline


def main():
    """Command-line interface."""

    parser = argparse.ArgumentParser(
        description="ProtocolIR: Reward-Guided Protocol Compiler"
    )
    parser.add_argument(
        "input",
        nargs="?",
        default=None,
        help="Input protocol file or text",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="./outputs",
        help="Output directory for generated artifacts",
    )
    parser.add_argument(
        "-u",
        "--url",
        default=None,
        help="Source URL of protocol",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run demo with example protocol",
    )

    args = parser.parse_args()

    if args.demo:
        # Demo protocol
        demo_protocol = """
        PCR Master Mix Setup

        Materials:
        - DNA template samples
        - PCR master mix

        Steps:
        1. Add 10 µL of DNA template to each well of the 96-well PCR plate.
        2. Add 40 µL of PCR master mix to each well.
        3. Mix gently by pipetting up and down 3 times.
        4. Keep the plate on ice until thermal cycling.
        """

        print("Running DEMO with example PCR protocol...")
        process_protocol(
            demo_protocol,
            source_url="demo://pcr_setup",
            output_dir=args.output,
        )

    elif args.input:
        # Read from file or stdin
        if Path(args.input).exists():
            with open(args.input, "r") as f:
                protocol_text = f.read()
        else:
            # Assume it's raw text
            protocol_text = args.input

        process_protocol(
            protocol_text,
            source_url=args.url,
            output_dir=args.output,
        )

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
