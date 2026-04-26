"""AST-based feature extraction from Opentrons Python scripts."""

from __future__ import annotations

import ast
import re
from typing import Dict, Optional

from protocolir.reward_model import DEFAULT_REWARD_WEIGHTS


PIPETTE_RANGES = {
    "p20": (1.0, 20.0),
    "p20_single_gen2": (1.0, 20.0),
    "p20_multi_gen2": (1.0, 20.0),
    "p300": (20.0, 300.0),
    "p300_single_gen2": (20.0, 300.0),
    "p300_multi_gen2": (20.0, 300.0),
    "p1000": (100.0, 1000.0),
    "p1000_single_gen2": (100.0, 1000.0),
}


def extract_script_features(code: str, *, expert: bool) -> Dict[str, float]:
    features = {name: 0.0 for name in DEFAULT_REWARD_WEIGHTS}
    lower = code.lower()
    pipettes = _detect_pipettes(code)

    try:
        tree = ast.parse(code)
    except SyntaxError:
        features["invalid_location_violations"] = 1.0
        return features

    last_tip_state: Dict[str, bool] = {}
    current_volume: Dict[str, float] = {}
    missing_mix = 0
    pending_plate_dispense = False

    for node in sorted(ast.walk(tree), key=lambda item: getattr(item, "lineno", 0)):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        method = node.func.attr
        pipette_var = _call_object_name(node.func.value)
        pipette_kind = pipettes.get(pipette_var, pipette_var or "")

        if method == "pick_up_tip":
            features["total_operations"] += 1
            last_tip_state[pipette_var] = True
            current_volume[pipette_var] = 0.0
        elif method == "drop_tip":
            features["tip_changes"] += 1
            features["total_operations"] += 1
            last_tip_state[pipette_var] = False
            current_volume[pipette_var] = 0.0
        elif method == "aspirate":
            volume = _numeric_arg(node, 0)
            features["aspirate_events"] += 1
            features["total_operations"] += 1
            if not last_tip_state.get(pipette_var, False) and not expert:
                features["aspirate_no_tip_violations"] += 1
            if volume is not None and _range_invalid(pipette_kind, volume):
                features["pipette_range_violations"] += 1
            current_volume[pipette_var] = current_volume.get(pipette_var, 0.0) + (volume or 0.0)
        elif method == "dispense":
            volume = _numeric_arg(node, 0)
            features["dispense_events"] += 1
            features["total_operations"] += 1
            if not last_tip_state.get(pipette_var, False) and not expert:
                features["dispense_no_tip_violations"] += 1
            if volume and volume > current_volume.get(pipette_var, 0.0) + 1e-9 and not expert:
                features["well_overflow_violations"] += 1
            current_volume[pipette_var] = max(0.0, current_volume.get(pipette_var, 0.0) - (volume or 0.0))
            pending_plate_dispense = True
        elif method == "mix":
            features["mix_events"] += 1
            features["total_operations"] += 1
            pending_plate_dispense = False
        elif method in {"transfer", "distribute", "consolidate"}:
            volume = _numeric_arg(node, 0)
            features["aspirate_events"] += 1
            features["dispense_events"] += 1
            features["complete_transfer_pairs"] += 1
            features["total_operations"] += 3
            if _new_tip(node) != "never":
                features["tip_changes"] += 1
            if volume is not None and _range_invalid(pipette_kind, volume):
                features["pipette_range_violations"] += 1
            if _has_kwarg(node, "mix_after") or _has_kwarg(node, "mix_before"):
                features["mix_events"] += 1

    if pending_plate_dispense and not expert:
        missing_mix += 1

    if expert:
        features["aspirate_no_tip_violations"] = 0
        features["dispense_no_tip_violations"] = 0
        features["well_overflow_violations"] = 0

    features["missing_mix_events"] = missing_mix if not expert else 0
    features["complete_transfer_pairs"] = max(
        features["complete_transfer_pairs"],
        min(features["aspirate_events"], features["dispense_events"], max(features["tip_changes"], 1.0)),
    )
    features["tip_changed_between_different_reagents"] = max(0.0, features["tip_changes"] - _comment_flag(lower, "same tip"))

    if not expert:
        features["contamination_violations"] += _comment_flag(lower, "cross-contamination") + _comment_flag(lower, "same tip")
        features["unknown_location_violations"] += _comment_flag(lower, "undefined")
        features["well_overflow_violations"] += _comment_flag(lower, "overflow")
        features["missing_mix_events"] += _comment_flag(lower, "mix() removed") + _comment_flag(lower, "mix_after removed")

    return features


def _detect_pipettes(code: str) -> Dict[str, str]:
    pipettes: Dict[str, str] = {}
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return pipettes
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Call):
            continue
        call = node.value
        if not isinstance(call.func, ast.Attribute) or call.func.attr != "load_instrument":
            continue
        instrument = _constant_arg(call, 0)
        if not instrument:
            continue
        for target in node.targets:
            if isinstance(target, ast.Name):
                pipettes[target.id] = instrument
    pipettes.setdefault("p20", "p20")
    pipettes.setdefault("p300", "p300")
    pipettes.setdefault("p1000", "p1000")
    return pipettes


def _call_object_name(value: ast.AST) -> str:
    if isinstance(value, ast.Name):
        return value.id
    if isinstance(value, ast.Attribute):
        return value.attr
    return "pipette"


def _numeric_arg(call: ast.Call, index: int) -> Optional[float]:
    if len(call.args) <= index:
        return None
    node = call.args[index]
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub) and isinstance(node.operand, ast.Constant):
        return -float(node.operand.value)
    return None


def _constant_arg(call: ast.Call, index: int) -> Optional[str]:
    if len(call.args) <= index:
        return None
    node = call.args[index]
    if isinstance(node, ast.Constant):
        return str(node.value)
    return None


def _range_invalid(pipette_kind: str, volume: float) -> bool:
    lower = pipette_kind.lower()
    for name, (min_v, max_v) in PIPETTE_RANGES.items():
        if name in lower:
            return volume < min_v or volume > max_v
    return False


def _new_tip(call: ast.Call) -> str:
    for kw in call.keywords:
        if kw.arg == "new_tip" and isinstance(kw.value, ast.Constant):
            return str(kw.value.value)
    return "always"


def _has_kwarg(call: ast.Call, name: str) -> bool:
    return any(kw.arg == name for kw in call.keywords)


def _comment_flag(text: str, pattern: str) -> int:
    return 1 if re.search(re.escape(pattern), text, re.I) else 0
