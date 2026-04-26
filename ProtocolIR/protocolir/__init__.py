"""ProtocolIR: Reward-Guided Protocol Compiler for Safe Lab Automation"""

__version__ = "2.0.0"

from protocolir.parser import parse_protocol
from protocolir.grounder import ground_actions, DEFAULT_DECK, build_deck_layout
from protocolir.ir_builder import build_ir
from protocolir.verifier import verify_ir
from protocolir.repair import repair_ir, repair_iteratively, repair_priority_table
from protocolir.compiler import compile_to_opentrons
from protocolir.simulator import simulate_opentrons_script
from protocolir.audit import generate_audit_report
from protocolir.reward_model import RewardModel, domain_prior_reward_model
from protocolir.features import extract_trajectory_features
from protocolir.bayesian_irl import fit_bayesian_irl
from protocolir.orchestration import agent_graph_as_dict, agent_graph_mermaid, run_protocol_graph

__all__ = [
    "parse_protocol",
    "ground_actions",
    "build_ir",
    "verify_ir",
    "repair_ir",
    "repair_iteratively",
    "repair_priority_table",
    "compile_to_opentrons",
    "simulate_opentrons_script",
    "generate_audit_report",
    "RewardModel",
    "domain_prior_reward_model",
    "extract_trajectory_features",
    "DEFAULT_DECK",
    "build_deck_layout",
    "fit_bayesian_irl",
    "agent_graph_as_dict",
    "agent_graph_mermaid",
    "run_protocol_graph",
]
