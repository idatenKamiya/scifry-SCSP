"""ProtocolIR: Reward-Guided Protocol Compiler for Safe Lab Automation"""

__version__ = "1.0.0"

from protocolir.parser import parse_protocol
from protocolir.grounder import ground_actions, DEFAULT_DECK
from protocolir.ir_builder import build_ir
from protocolir.verifier import verify_ir
from protocolir.repair import repair_ir, repair_iteratively
from protocolir.compiler import compile_to_opentrons
from protocolir.simulator import simulate_opentrons_script
from protocolir.audit import generate_audit_report
from protocolir.reward_model import RewardModel, learn_reward_heuristically
from protocolir.features import extract_trajectory_features

__all__ = [
    "parse_protocol",
    "ground_actions",
    "build_ir",
    "verify_ir",
    "repair_ir",
    "repair_iteratively",
    "compile_to_opentrons",
    "simulate_opentrons_script",
    "generate_audit_report",
    "RewardModel",
    "learn_reward_heuristically",
    "extract_trajectory_features",
    "DEFAULT_DECK",
]
