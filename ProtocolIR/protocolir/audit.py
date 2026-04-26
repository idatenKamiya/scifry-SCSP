"""Layer 9: human-readable audit and demo reports."""

from __future__ import annotations

from datetime import datetime
from typing import List

from protocolir.contamination_graph import contamination_mermaid
from protocolir.schemas import ProtocolPipeline, Violation


def generate_audit_report(pipeline: ProtocolPipeline) -> str:
    report: List[str] = []
    before = pipeline.violations_before_repair or pipeline.violations
    after = pipeline.violations_after_repair

    report.append("# ProtocolIR Safety Audit Report")
    report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("")
    report.append("## Executive Claim")
    report.append(
        "Runnable robot code is not enough. ProtocolIR converts protocol text into a typed IR, "
        "enforces hard physical invariants, optimizes a reward score, repairs unsafe behavior, "
        "and compiles only the verified IR to Opentrons Python."
    )
    report.append("")

    report.append("## Input")
    if pipeline.parsed:
        report.append(f"- Goal: {pipeline.parsed.goal}")
        report.append(f"- Parser backend: {pipeline.parsed.parser_backend}")
        report.append(f"- Samples/wells planned: {pipeline.parsed.sample_count}")
        report.append(f"- Materials extracted: {len(pipeline.parsed.materials)}")
        report.append(f"- Semantic actions extracted: {len(pipeline.parsed.actions)}")
        if pipeline.parsed.ambiguities:
            report.append("- Ambiguities:")
            for ambiguity in pipeline.parsed.ambiguities[:8]:
                report.append(f"  - {ambiguity}")
    if pipeline.source_url:
        report.append(f"- Source: {pipeline.source_url}")
    report.append("")

    report.append("## Hard Safety Verification")
    report.append("| Stage | Critical | Warning | Total |")
    report.append("|---|---:|---:|---:|")
    report.append(f"| Before repair | {_count(before, 'CRITICAL')} | {_count(before, 'WARNING')} | {len(before)} |")
    report.append(f"| After repair | {_count(after, 'CRITICAL')} | {_count(after, 'WARNING')} | {len(after)} |")
    report.append("")

    if before:
        report.append("### Violations Before Repair")
        for violation in before[:12]:
            report.append(
                f"- {violation.violation_type} at IR[{violation.action_idx}]: {violation.message}"
            )
        if len(before) > 12:
            report.append(f"- ... {len(before) - 12} more")
        report.append("")

    if pipeline.repairs_applied:
        report.append("### Repairs Applied")
        for repair in pipeline.repairs_applied[:20]:
            report.append(f"- {repair}")
        if len(pipeline.repairs_applied) > 20:
            report.append(f"- ... {len(pipeline.repairs_applied) - 20} more")
        report.append("")

    if after:
        report.append("### Remaining Issues")
        for violation in after:
            report.append(f"- {violation.violation_type}: {violation.message}")
        report.append("")

    report.append("## Reward Model")
    report.append("| Metric | Before | After | Change |")
    report.append("|---|---:|---:|---:|")
    report.append(
        f"| Reward score | {pipeline.reward_before:.0f} | {pipeline.reward_after:.0f} | "
        f"{pipeline.reward_after - pipeline.reward_before:+.0f} |"
    )
    report.append(f"| Violations | {len(before)} | {len(after)} | {len(after) - len(before):+d} |")
    if pipeline.reward_score:
        report.append("")
        report.append("### Largest Reward Contributors")
        ranked = sorted(
            pipeline.reward_score.feature_scores.items(),
            key=lambda item: abs(item[1]),
            reverse=True,
        )
        for name, score in ranked[:8]:
            report.append(f"- {name}: {score:+.0f}")
    report.append("")

    report.append("## Simulator Validation")
    if pipeline.simulation_result:
        sim = pipeline.simulation_result
        mode = "real Opentrons simulator" if sim.used_real_simulator else "simulator unavailable"
        report.append(f"- Status: {'PASS' if sim.passed else 'FAIL'}")
        report.append(f"- Mode: {mode}")
        report.append(f"- Commands: {sim.command_count}")
        report.append(f"- Aspirates: {sim.aspirate_count}")
        report.append(f"- Dispenses: {sim.dispense_count}")
        report.append(f"- Tip operations: {sim.tip_count}")
        if sim.warnings:
            report.append("- Warnings:")
            for warning in sim.warnings[:5]:
                report.append(f"  - {warning}")
        if sim.errors:
            report.append("- Errors:")
            for error in sim.errors[:5]:
                report.append(f"  - {error}")
    else:
        report.append("- Status: not run")
    report.append("")

    if pipeline.ir_repaired:
        report.append("## Contamination Graph")
        report.append("```mermaid")
        report.append(contamination_mermaid(pipeline.ir_repaired))
        report.append("```")
        report.append("")

    report.append("## Verdict")
    if (
        not after
        and pipeline.simulation_result
        and pipeline.simulation_result.passed
        and pipeline.simulation_result.used_real_simulator
    ):
        report.append("PASS: no remaining verifier violations and real Opentrons simulation passes.")
    elif after:
        report.append("REVIEW: remaining verifier issues require human review before execution.")
    elif pipeline.simulation_result and not pipeline.simulation_result.used_real_simulator:
        report.append("REVIEW: simulator was skipped or unavailable; artifact is not a simulator-backed pass.")
    else:
        report.append("REVIEW: simulator validation did not pass.")
    report.append("")
    report.append("Generated by ProtocolIR v2.0.")
    return "\n".join(report)


def generate_comparison_report(
    baseline_violations: List[Violation],
    baseline_score: float,
    improved_violations: List[Violation],
    improved_score: float,
    repairs: List[str],
) -> str:
    resolved = len(baseline_violations) - len(improved_violations)
    lines = [
        "# ProtocolIR Improvement Report",
        "",
        "| Metric | Before | After | Change |",
        "|---|---:|---:|---:|",
        f"| Violations | {len(baseline_violations)} | {len(improved_violations)} | {resolved:+d} |",
        f"| Reward score | {baseline_score:.0f} | {improved_score:.0f} | {improved_score - baseline_score:+.0f} |",
        "",
        "## Repairs",
    ]
    lines.extend(f"{idx}. {repair}" for idx, repair in enumerate(repairs, 1))
    return "\n".join(lines)


def export_report_to_file(report: str, output_path: str) -> None:
    with open(output_path, "w", encoding="utf-8") as handle:
        handle.write(report)


def create_executive_summary(pipeline: ProtocolPipeline) -> str:
    before = len(pipeline.violations_before_repair or pipeline.violations)
    after = len(pipeline.violations_after_repair)
    sim = pipeline.simulation_result
    status = "PASS" if sim and sim.passed and sim.used_real_simulator and after == 0 else "REVIEW"
    lines = [
        "# Executive Summary",
        "",
        f"Status: {status}",
        f"Violations before repair: {before}",
        f"Violations after repair: {after}",
        f"Repairs applied: {len(pipeline.repairs_applied)}",
        f"Reward improvement: {pipeline.reward_after - pipeline.reward_before:+.0f}",
        f"Commands to execute: {sim.command_count if sim else 'N/A'}",
    ]
    if sim and not sim.used_real_simulator:
        lines.append("Simulator mode: unavailable; install/fix Opentrons SDK and rerun.")
    return "\n".join(lines)


def _count(violations: List[Violation], severity: str) -> int:
    return sum(1 for violation in violations if violation.severity == severity)
