"""IR flow visualization helpers for judge-facing UI."""

from __future__ import annotations

from typing import Iterable, List, Set

from protocolir.schemas import IROp, Violation


def ir_flow_mermaid(
    ir_ops: List[IROp],
    violations: Iterable[Violation] | None = None,
    *,
    max_nodes: int = 140,
) -> str:
    """Render a compact Mermaid flowchart of typed IR operations."""

    violation_indices: Set[int] = set()
    for violation in violations or []:
        violation_indices.add(violation.action_idx)

    if not ir_ops:
        return 'flowchart LR\n    n0["No IR operations"]'

    lines = ["flowchart LR"]
    count = min(len(ir_ops), max_nodes)
    for idx, op in enumerate(ir_ops[:count]):
        node_id = f"n{idx}"
        detail = _detail(op)
        label = f"{idx}: {op.op.value}\\n{detail}" if detail else f"{idx}: {op.op.value}"
        css = ":::bad" if idx in violation_indices else ":::safe"
        lines.append(f'    {node_id}["{label}"] {css}')
        if idx > 0:
            lines.append(f"    n{idx-1} --> {node_id}")

    if len(ir_ops) > max_nodes:
        lines.append(f'    trunc["... truncated {len(ir_ops) - max_nodes} ops"]')
        lines.append(f"    n{count-1} --> trunc")

    lines.append("    classDef safe stroke:#2e7d32,stroke-width:2px;")
    lines.append("    classDef bad stroke:#c62828,stroke-width:3px,stroke-dasharray: 6 3;")
    return "\n".join(lines)


def _detail(op: IROp) -> str:
    parts: List[str] = []
    if op.pipette:
        parts.append(op.pipette)
    if op.volume_ul is not None:
        parts.append(f"{op.volume_ul:g}uL")
    if op.source:
        parts.append(f"from {op.source}")
    if op.destination:
        parts.append(f"to {op.destination}")
    if op.location:
        parts.append(f"at {op.location}")
    if op.alias and op.slot is not None:
        parts.append(f"{op.alias}@{op.slot}")
    if op.name and op.mount:
        parts.append(f"{op.name}@{op.mount}")
    return " | ".join(parts)

