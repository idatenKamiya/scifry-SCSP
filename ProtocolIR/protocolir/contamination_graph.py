"""Contamination graph extraction from typed IR."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Set

from protocolir.schemas import IROp, IROpType


@dataclass(frozen=True)
class TransferEdge:
    source: str
    destination: str
    reagent: str
    contaminated: bool


def build_contamination_edges(ir_ops: List[IROp]) -> List[TransferEdge]:
    tip_reagent: dict[str, str | None] = {}
    seen_reagents: dict[str, Set[str]] = {}
    last_source: dict[str, str] = {}
    edges: List[TransferEdge] = []

    for op in ir_ops:
        pipette = op.pipette or ""
        if op.op == IROpType.PICK_UP_TIP:
            tip_reagent[pipette] = None
            seen_reagents[pipette] = set()
        elif op.op == IROpType.DROP_TIP:
            tip_reagent.pop(pipette, None)
            seen_reagents.pop(pipette, None)
            last_source.pop(pipette, None)
        elif op.op == IROpType.ASPIRATE:
            reagent = op.reagent or "unknown"
            tip_reagent[pipette] = reagent
            seen_reagents.setdefault(pipette, set()).add(reagent)
            if op.source:
                last_source[pipette] = op.source
        elif op.op == IROpType.DISPENSE and op.destination:
            edges.append(
                TransferEdge(
                    source=last_source.get(pipette, "unknown"),
                    destination=op.destination,
                    reagent=tip_reagent.get(pipette) or "unknown",
                    contaminated=len(seen_reagents.get(pipette, set())) > 1,
                )
            )
    return edges


def contamination_mermaid(ir_ops: List[IROp]) -> str:
    edges = build_contamination_edges(ir_ops)
    lines = ["flowchart LR"]
    if not edges:
        lines.append('    none["No liquid transfer edges detected"]')
        return "\n".join(lines)
    for idx, edge in enumerate(edges):
        source = _node(edge.source)
        dest = _node(edge.destination)
        style = ":::bad" if edge.contaminated else ":::safe"
        lines.append(f'    {source}["{edge.source}"] -->|"{edge.reagent}"| {dest}["{edge.destination}"] {style}')
    lines.append("    classDef safe stroke:#2e7d32,stroke-width:2px;")
    lines.append("    classDef bad stroke:#c62828,stroke-width:3px,stroke-dasharray: 6 3;")
    return "\n".join(lines)


def _node(value: str) -> str:
    return "n_" + "".join(ch if ch.isalnum() else "_" for ch in value)
