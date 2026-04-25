"""
LAYER 9: Audit Report Generation
Creates human-readable safety and compliance reports.
"""

from typing import Optional, List
from datetime import datetime
from protocolir.schemas import (
    ParsedProtocol,
    ProtocolPipeline,
    Violation,
    RewardScore,
    SimulationResult,
)


def generate_audit_report(pipeline: ProtocolPipeline) -> str:
    """
    Generate comprehensive audit report for a protocol.

    Args:
        pipeline: Complete ProtocolPipeline with all stages executed

    Returns:
        Markdown-formatted audit report
    """

    report = []

    report.append("# Protocol Safety Audit Report")
    report.append(f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")
    report.append("")

    # Input section
    report.append("## Input Protocol")
    if pipeline.parsed:
        report.append(f"- **Goal:** {pipeline.parsed.goal}")
    if pipeline.source_url:
        report.append(f"- **Source:** {pipeline.source_url}")

    if pipeline.parsed and pipeline.parsed.ambiguities:
        report.append(f"- **Ambiguities detected:** {len(pipeline.parsed.ambiguities)}")
        for amb in pipeline.parsed.ambiguities[:3]:
            report.append(f"  - {amb}")
        if len(pipeline.parsed.ambiguities) > 3:
            report.append(f"  - ... and {len(pipeline.parsed.ambiguities) - 3} more")

    report.append("")

    # Violations section
    report.append("## Safety Verification")

    critical_violations = [v for v in pipeline.violations if v.severity == "CRITICAL"]
    warning_violations = [v for v in pipeline.violations if v.severity == "WARNING"]

    report.append(f"**Critical violations detected:** {len(critical_violations)}")
    report.append(f"**Warnings:** {len(warning_violations)}")

    if pipeline.violations:
        report.append("\n### Violations Found (Before Repair)")
        for v in pipeline.violations[:5]:
            report.append(f"- **{v.violation_type}** (action {v.action_idx}): {v.message}")
        if len(pipeline.violations) > 5:
            report.append(f"- ... and {len(pipeline.violations) - 5} more violations")

    report.append("")

    # Repairs section
    if pipeline.repairs_applied:
        report.append("### Repairs Applied")
        for repair in pipeline.repairs_applied[:10]:
            report.append(f"- {repair}")
        if len(pipeline.repairs_applied) > 10:
            report.append(
                f"- ... and {len(pipeline.repairs_applied) - 10} more repairs"
            )

    report.append("")

    # Reward scoring section
    report.append("## Reward Scoring")

    report.append("| Metric | Before Repair | After Repair | Change |")
    report.append("|--------|:---:|:---:|---:|")
    report.append(
        f"| Reward Score | {pipeline.reward_before:.0f} | {pipeline.reward_after:.0f} | {pipeline.reward_after - pipeline.reward_before:+.0f} |"
    )
    report.append(
        f"| Violations | {len(pipeline.violations)} | 0 | ✓ |"
    )

    if pipeline.reward_score:
        report.append("\n### Top Feature Contributors (After Repair)")
        sorted_features = sorted(
            pipeline.reward_score.feature_scores.items(),
            key=lambda x: abs(x[1]),
            reverse=True,
        )
        for feature_name, score in sorted_features[:5]:
            direction = "↑" if score > 0 else "↓"
            report.append(f"- {feature_name}: {score:+.0f} {direction}")

    report.append("")

    # Simulation section
    report.append("## Simulator Validation")

    if pipeline.simulation_result:
        sim = pipeline.simulation_result
        status_icon = "✓" if sim.passed else "✗"
        report.append(f"{status_icon} **Status:** {'PASS' if sim.passed else 'FAIL'}")
        report.append(f"- Commands executed: {sim.command_count}")
        report.append(f"- Aspirates: {sim.aspirate_count}")
        report.append(f"- Dispenses: {sim.dispense_count}")
        report.append(f"- Tip operations: {sim.tip_count}")

        if sim.errors:
            report.append(f"\n**Errors:** {len(sim.errors)}")
            for error in sim.errors[:3]:
                report.append(f"- {error}")

        if sim.warnings:
            report.append(f"\n**Warnings:** {len(sim.warnings)}")
            for warning in sim.warnings[:3]:
                report.append(f"- {warning}")
    else:
        report.append("Simulation not performed")

    report.append("")

    # Human escalations
    if pipeline.human_escalations:
        report.append("## Human Review Required")
        report.append(f"**{len(pipeline.human_escalations)} escalations for manual review:**")
        for escalation in pipeline.human_escalations:
            report.append(f"- {escalation}")

    report.append("")

    # Conclusion
    report.append("## Conclusion")

    if pipeline.simulation_result and pipeline.simulation_result.passed:
        if len(pipeline.violations) == 0:
            report.append(
                "✓ Protocol is verified safe and ready for execution."
            )
        else:
            report.append(
                f"⚠ Protocol was repaired ({len(pipeline.repairs_applied)} fixes applied) and is now ready for execution."
            )
    else:
        report.append(
            "✗ Protocol failed simulator validation. Review errors above."
        )

    report.append("")
    report.append("---")
    report.append("*Generated by ProtocolIR v1.0 - Reward-Guided Protocol Compiler*")

    return "\n".join(report)


def generate_comparison_report(
    baseline_violations: List[Violation],
    baseline_score: float,
    improved_violations: List[Violation],
    improved_score: float,
    repairs: List[str],
) -> str:
    """
    Generate a comparison report showing before/after improvements.

    Args:
        baseline_violations: Violations in original protocol
        baseline_score: Reward score before repair
        improved_violations: Violations after repair
        improved_score: Reward score after repair
        repairs: List of repairs applied

    Returns:
        Markdown-formatted comparison report
    """

    report = []

    report.append("# Protocol Improvement Report")
    report.append("")

    report.append("## Violations")
    report.append(f"| Status | Count |")
    report.append("|--------|------:|")
    report.append(f"| Before repair | {len(baseline_violations)} |")
    report.append(f"| After repair | {len(improved_violations)} |")
    report.append(f"| Resolved | {len(baseline_violations) - len(improved_violations)} ✓ |")
    report.append("")

    report.append("## Reward Score")
    report.append(f"- **Before:** {baseline_score:.1f}")
    report.append(f"- **After:** {improved_score:.1f}")
    report.append(
        f"- **Improvement:** {improved_score - baseline_score:+.1f} ({((improved_score - baseline_score) / abs(baseline_score) * 100) if baseline_score != 0 else 'N/A'}%)"
    )
    report.append("")

    report.append("## Repairs Applied")
    report.append(f"Total: {len(repairs)} repairs")
    report.append("")
    for i, repair in enumerate(repairs[:15], 1):
        report.append(f"{i}. {repair}")
    if len(repairs) > 15:
        report.append(f"\n... and {len(repairs) - 15} more repairs")

    return "\n".join(report)


def export_report_to_file(report: str, output_path: str):
    """Save report to file."""

    with open(output_path, "w") as f:
        f.write(report)


def create_executive_summary(pipeline: ProtocolPipeline) -> str:
    """Create brief executive summary for quick review."""

    summary = []

    summary.append("# Executive Summary")
    summary.append("")

    if pipeline.simulation_result and pipeline.simulation_result.passed:
        summary.append("✓ **Protocol PASSED verification**")
    else:
        summary.append("✗ **Protocol FAILED verification**")

    summary.append(f"- Violations fixed: {len(pipeline.violations)}")
    summary.append(
        f"- Reward improvement: {pipeline.reward_after - pipeline.reward_before:+.0f}"
    )
    summary.append(f"- Repairs applied: {len(pipeline.repairs_applied)}")
    summary.append(f"- Commands to execute: {pipeline.simulation_result.command_count if pipeline.simulation_result else 'N/A'}")

    if pipeline.human_escalations:
        summary.append(
            f"- Requires human review: {len(pipeline.human_escalations)} items"
        )

    return "\n".join(summary)
