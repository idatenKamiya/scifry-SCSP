"""PRE-style targeted patches for typed ProtocolIR operations."""

from __future__ import annotations

import re
from typing import List, Tuple

from protocolir.ir_builder import mix_volume_for, select_pipette
from protocolir.schemas import IROp, IROpType


def precise_patch_ir(ir_ops: List[IROp], error_text: str) -> Tuple[List[IROp], List[str]]:
    patched = [op.model_copy(deep=True) for op in ir_ops]
    repairs: List[str] = []
    lower = error_text.lower()

    if "tip" in lower and ("without" in lower or "no tip" in lower):
        idx = _first_liquid_op_without_preceding_tip(patched)
        if idx is not None and patched[idx].pipette:
            patched.insert(idx, IROp(op=IROpType.PICK_UP_TIP, pipette=patched[idx].pipette))
            repairs.append(f"PRE inserted PickUpTip before IR[{idx}] after simulator tip error.")

    if "max volume" in lower or "volume" in lower or "p20" in lower or "p300" in lower:
        changed = _patch_volume_windows(patched)
        if changed:
            repairs.append(f"PRE switched {changed} operation(s) to volume-compatible pipettes.")

    return patched, repairs


def _first_liquid_op_without_preceding_tip(ir_ops: List[IROp]) -> int | None:
    has_tip: dict[str, bool] = {}
    for idx, op in enumerate(ir_ops):
        pipette = op.pipette
        if op.op == IROpType.PICK_UP_TIP and pipette:
            has_tip[pipette] = True
        elif op.op == IROpType.DROP_TIP and pipette:
            has_tip[pipette] = False
        elif op.op in {IROpType.ASPIRATE, IROpType.DISPENSE, IROpType.MIX} and pipette:
            if not has_tip.get(pipette, False):
                return idx
    return None


def _patch_volume_windows(ir_ops: List[IROp]) -> int:
    changed = 0
    for idx, op in enumerate(ir_ops):
        if op.op not in {IROpType.ASPIRATE, IROpType.DISPENSE, IROpType.MIX}:
            continue
        if op.volume_ul is None or op.pipette is None:
            continue
        new_pipette = select_pipette(op.volume_ul)
        if new_pipette == op.pipette:
            continue
        old_pipette = op.pipette
        start, end = _transfer_window(ir_ops, idx, old_pipette)
        for window_op in ir_ops[start : end + 1]:
            if window_op.pipette == old_pipette:
                window_op.pipette = new_pipette
                changed += 1
            if window_op.op == IROpType.MIX and window_op.volume_ul is not None:
                window_op.volume_ul = mix_volume_for(window_op.volume_ul, new_pipette)
    return changed


def _transfer_window(ir_ops: List[IROp], idx: int, pipette: str) -> tuple[int, int]:
    start = idx
    while start > 0:
        if ir_ops[start].op == IROpType.PICK_UP_TIP and ir_ops[start].pipette == pipette:
            break
        start -= 1
    end = idx
    while end < len(ir_ops) - 1:
        if ir_ops[end].op == IROpType.DROP_TIP and ir_ops[end].pipette == pipette:
            break
        end += 1
    return start, end
