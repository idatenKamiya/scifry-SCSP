"""Executable typed graph orchestration for ProtocolIR."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

from protocolir.audit import generate_audit_report
from protocolir.compiler import compile_to_opentrons
from protocolir.features import extract_trajectory_features
from protocolir.grounder import build_deck_layout, ground_actions
from protocolir.human_gate import human_gate_checkpoint, summarize_checkpoint
from protocolir.ir_builder import build_ir
from protocolir.parser import parse_protocol
from protocolir.precise_repair import precise_patch_ir
from protocolir.repair import repair_iteratively
from protocolir.reward_model import RewardModel
from protocolir.schemas import IROp, ProtocolPipeline
from protocolir.simulator import simulate_opentrons_script, validate_script_before_simulation
from protocolir.verifier import verify_ir


@dataclass(frozen=True)
class OrchestrationNode:
    name: str
    role: str
    deterministic: bool


PROTOCOLIR_AGENT_GRAPH: Tuple[OrchestrationNode, ...] = (
    OrchestrationNode("SemanticParser", "OpenRouter strict JSON-schema extraction with local RAG context", False),
    OrchestrationNode("HumanGateParse", "Human approval checkpoint after semantic extraction", True),
    OrchestrationNode("Grounder", "Map semantic actions to OT-2 deck, labware, and wells", True),
    OrchestrationNode("IRBuilder", "Lower grounded actions into typed robot IR", True),
    OrchestrationNode("Verifier", "Enforce hard physical safety invariants", True),
    OrchestrationNode("RepairAgent", "Apply auditable deterministic IR repairs", True),
    OrchestrationNode("RewardAgent", "Score trajectory with Bayesian IRL posterior mean", True),
    OrchestrationNode("HumanGateRepair", "Human approval checkpoint after verification/repair", True),
    OrchestrationNode("Compiler", "Compile verified IR to Opentrons Python", True),
    OrchestrationNode("HumanGateCompile", "Human approval checkpoint before simulation", True),
    OrchestrationNode("Simulator", "Run real Opentrons simulation", True),
    OrchestrationNode("PreciseRepair", "Patch typed IR from simulator error and recompile", True),
    OrchestrationNode("Auditor", "Emit measured audit artifacts", True),
)

PROTOCOLIR_EDGES: Tuple[Tuple[str, str], ...] = (
    ("SemanticParser", "HumanGateParse"),
    ("HumanGateParse", "Grounder"),
    ("Grounder", "IRBuilder"),
    ("IRBuilder", "Verifier"),
    ("RepairAgent", "Verifier"),
    ("Verifier", "RewardAgent"),
    ("RewardAgent", "HumanGateRepair"),
    ("HumanGateRepair", "Compiler"),
    ("Compiler", "HumanGateCompile"),
    ("HumanGateCompile", "Simulator"),
    ("PreciseRepair", "Compiler"),
    ("Simulator", "Auditor"),
)

PROTOCOLIR_CONDITIONAL_EDGES: Tuple[Tuple[str, str, str], ...] = (
    ("Verifier", "RepairAgent", "violations remain"),
    ("Verifier", "RewardAgent", "verified"),
    ("Simulator", "PreciseRepair", "simulation error and patchable"),
    ("Simulator", "Auditor", "simulation pass"),
)


def run_protocol_graph(
    raw_text: str,
    *,
    source_url: Optional[str],
    reward_model: RewardModel,
    stress_mutator: Optional[Callable[[List[IROp]], List[IROp]]] = None,
    max_repair_iterations: int = 5,
    max_simulation_patch_iterations: int = 3,
) -> ProtocolPipeline:
    pipeline = ProtocolPipeline(raw_text=raw_text, source_url=source_url)

    print("\n[1/9] Parsing protocol with OpenRouter strict structured output + local RAG...")
    pipeline.parsed = parse_protocol(raw_text, source_url)
    print(f"  Goal: {pipeline.parsed.goal}")
    print(f"  Parser backend: {pipeline.parsed.parser_backend}")
    print(f"  Samples: {pipeline.parsed.sample_count}")
    print(f"  Materials: {len(pipeline.parsed.materials)}")
    print(f"  Semantic actions: {len(pipeline.parsed.actions)}")
    if pipeline.parsed.ambiguities:
        print(f"  Ambiguities / reviews flagged: {len(pipeline.parsed.ambiguities)}")
    if not human_gate_checkpoint("post_parser", summarize_checkpoint(pipeline.parsed)):
        raise RuntimeError("Human gate rejected parsed protocol.")

    print("\n[2/9] Grounding semantic actions to deck/labware/wells...")
    pipeline.deck_layout = build_deck_layout(pipeline.parsed.sample_count)
    pipeline.grounded = ground_actions(pipeline.parsed, pipeline.deck_layout)
    print(f"  Grounded actions: {len(pipeline.grounded)}")

    print("\n[3/9] Building typed IR...")
    pipeline.ir_original = build_ir(pipeline.grounded, pipeline.deck_layout)
    if stress_mutator:
        pipeline.ir_original = stress_mutator(pipeline.ir_original)
        print("  Stress demo enabled: injected no-tip, wrong-pipette, and missing-mix errors")
    print(f"  IR operations: {len(pipeline.ir_original)}")

    print("\n[4/9] Verifying hard physical constraints...")
    current_ir = pipeline.ir_original
    pipeline.violations_before_repair = verify_ir(current_ir)
    pipeline.violations = pipeline.violations_before_repair
    _print_violation_summary(pipeline.violations_before_repair)

    print("\n[5/9] Scoring trajectory before repair...")
    features_before = extract_trajectory_features(current_ir, pipeline.violations_before_repair)
    pipeline.reward_before = reward_model.score_trajectory(features_before).total_score
    print(f"  Reward before repair: {pipeline.reward_before:.0f}")

    print("\n[6/9] Repairing policy violations with typed IR repair loop...")
    if pipeline.violations_before_repair:
        repaired, repairs, remaining = repair_iteratively(
            current_ir,
            pipeline.violations_before_repair,
            max_iterations=max_repair_iterations,
        )
        pipeline.ir_repaired = repaired
        pipeline.repairs_applied = repairs
        pipeline.violations_after_repair = remaining
        print(f"  Repairs applied: {len(repairs)}")
        _print_violation_summary(remaining, prefix="  Remaining")
    else:
        pipeline.ir_repaired = current_ir
        pipeline.violations_after_repair = []
        print("  No repairs needed.")

    features_after = extract_trajectory_features(pipeline.ir_repaired, pipeline.violations_after_repair)
    pipeline.reward_score = reward_model.score_trajectory(features_after)
    pipeline.reward_after = pipeline.reward_score.total_score
    print(f"  Reward after repair: {pipeline.reward_after:.0f}")

    if pipeline.violations_after_repair:
        raise RuntimeError(
            f"Unsafe pipeline gate blocked compilation: {len(pipeline.violations_after_repair)} violations remain."
        )
    if not human_gate_checkpoint("post_verifier", summarize_checkpoint(pipeline.repairs_applied)):
        raise RuntimeError("Human gate rejected verifier/repair result.")

    print("\n[7/9] Compiling verified IR to Opentrons Python...")
    pipeline.generated_script = _compile_checked(pipeline.ir_repaired)
    print(f"  Generated script bytes: {len(pipeline.generated_script)}")
    if not human_gate_checkpoint("post_compiler", pipeline.generated_script[:3000]):
        raise RuntimeError("Human gate rejected generated Python.")

    print("\n[8/9] Simulating generated protocol with the real Opentrons simulator...")
    for attempt in range(max_simulation_patch_iterations + 1):
        pipeline.simulation_result = simulate_opentrons_script(pipeline.generated_script)
        sim = pipeline.simulation_result
        mode = "real Opentrons simulator" if sim.used_real_simulator else "simulator unavailable"
        print(f"  Status: {'PASS' if sim.passed else 'FAIL'} ({mode})")
        print(f"  Commands: {sim.command_count}")
        if sim.passed and sim.used_real_simulator:
            break
        if attempt >= max_simulation_patch_iterations:
            raise RuntimeError("; ".join(sim.errors or ["Opentrons simulator did not pass"]))
        patched_ir, patches = precise_patch_ir(pipeline.ir_repaired, sim.log or "\n".join(sim.errors))
        if not patches:
            raise RuntimeError("; ".join(sim.errors or ["Simulation failed and PRE found no typed patch"]))
        pipeline.ir_repaired = patched_ir
        pipeline.repairs_applied.extend(patches)
        pipeline.violations_after_repair = verify_ir(pipeline.ir_repaired)
        if pipeline.violations_after_repair:
            raise RuntimeError("PRE patch introduced verifier violations.")
        pipeline.generated_script = _compile_checked(pipeline.ir_repaired)
        print(f"  PRE patches applied: {len(patches)}; recompiling and re-simulating.")

    print("\n[9/9] Generating audit artifacts...")
    pipeline.audit_report = generate_audit_report(pipeline)
    print("  Audit report generated.")
    return pipeline


def agent_graph_as_dict() -> Dict[str, List[Dict[str, object]]]:
    return {
        "nodes": [
            {"name": node.name, "role": node.role, "deterministic": node.deterministic}
            for node in PROTOCOLIR_AGENT_GRAPH
        ],
        "edges": [{"from": source, "to": target} for source, target in PROTOCOLIR_EDGES],
        "conditional_edges": [
            {"from": source, "to": target, "condition": condition}
            for source, target, condition in PROTOCOLIR_CONDITIONAL_EDGES
        ],
    }


def agent_graph_mermaid() -> str:
    lines = ["flowchart LR"]
    for node in PROTOCOLIR_AGENT_GRAPH:
        label = f"{node.name}<br/>{node.role}"
        lines.append(f'    {node.name}["{label}"]')
    for source, target in PROTOCOLIR_EDGES:
        lines.append(f"    {source} --> {target}")
    for source, target, condition in PROTOCOLIR_CONDITIONAL_EDGES:
        lines.append(f"    {source} -- {condition} --> {target}")
    return "\n".join(lines)


def _compile_checked(ir_ops: List[IROp]) -> str:
    script = compile_to_opentrons(ir_ops)
    valid, issues = validate_script_before_simulation(script)
    if not valid:
        raise RuntimeError("; ".join(issues))
    return script


def _print_violation_summary(violations, prefix: str = "  Found") -> None:
    critical = sum(1 for violation in violations if violation.severity == "CRITICAL")
    warnings = sum(1 for violation in violations if violation.severity == "WARNING")
    print(f"{prefix}: {len(violations)} total ({critical} critical, {warnings} warning)")
    for violation in violations[:5]:
        print(f"    - {violation.violation_type}: {violation.message}")
    if len(violations) > 5:
        print(f"    - ... {len(violations) - 5} more")
