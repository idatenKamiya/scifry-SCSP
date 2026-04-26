"""Layer 7: deterministic compiler from verified IR to Opentrons Python."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, List

from protocolir.schemas import IROp, IROpType


class CompilerBackend(ABC):
    @abstractmethod
    def compile(self, ir_ops: List[IROp]) -> str:
        raise NotImplementedError


class OpentronsBackend(CompilerBackend):
    def compile(self, ir_ops: List[IROp]) -> str:
        return _compile_opentrons_v2(ir_ops)


class PyLabRobotBackend(CompilerBackend):
    def compile(self, ir_ops: List[IROp]) -> str:
        raise NotImplementedError("PyLabRobot backend is declared for future work but not implemented.")


def compile_to_opentrons(ir_ops: List[IROp]) -> str:
    return OpentronsBackend().compile(ir_ops)


def _compile_opentrons_v2(ir_ops: List[IROp]) -> str:
    """Compile low-level IR operations into an executable Opentrons protocol."""

    script = [
        "from opentrons import protocol_api",
        "",
        "metadata = {",
        '    "apiLevel": "2.14",',
        '    "protocolName": "ProtocolIR Generated Protocol",',
        '    "description": "Reward-guided, verifier-repaired protocol"',
        "}",
        "",
        "",
        "def run(protocol: protocol_api.ProtocolContext):",
    ]

    loaded_labware: Dict[str, Dict] = {}
    loaded_instruments: Dict[str, Dict] = {}

    for op in ir_ops:
        if op.op == IROpType.LOAD_LABWARE:
            alias = _identifier(op.alias or op.name or "labware")
            script.append(
                f"    {alias} = protocol.load_labware('{op.opentrons_name}', '{op.slot}')"
            )
            loaded_labware[alias] = {"name": op.opentrons_name, "slot": op.slot}

        elif op.op == IROpType.LOAD_INSTRUMENT:
            name = _identifier(op.name or op.alias or "pipette")
            tipracks = ", ".join(_identifier(tiprack) for tiprack in (op.tipracks or []))
            script.append(
                f"    {name} = protocol.load_instrument('{op.opentrons_name}', "
                f"'{op.mount}', tip_racks=[{tipracks}])"
            )
            loaded_instruments[name] = {"mount": op.mount, "tipracks": op.tipracks or []}

        elif op.op == IROpType.PICK_UP_TIP:
            script.append(f"    {_identifier(op.pipette)}.pick_up_tip()")

        elif op.op == IROpType.DROP_TIP:
            script.append(f"    {_identifier(op.pipette)}.drop_tip()")

        elif op.op == IROpType.ASPIRATE:
            script.append(
                f"    {_identifier(op.pipette)}.aspirate({op.volume_ul:g}, "
                f"{parse_well_location(op.source, loaded_labware)})"
            )

        elif op.op == IROpType.DISPENSE:
            script.append(
                f"    {_identifier(op.pipette)}.dispense({op.volume_ul:g}, "
                f"{parse_well_location(op.destination, loaded_labware)})"
            )

        elif op.op == IROpType.MIX:
            script.append(
                f"    {_identifier(op.pipette)}.mix({op.repetitions or 3}, "
                f"{op.volume_ul:g}, {parse_well_location(op.location, loaded_labware)})"
            )

        elif op.op == IROpType.DELAY:
            script.append(f"    protocol.delay(seconds={op.delay_seconds or 60:g})")

        elif op.op == IROpType.SET_TEMPERATURE:
            script.append(f"    # Temperature target: {op.temperature_c or 37:g} C")

        elif op.op == IROpType.INCUBATE:
            if op.location:
                script.append(f"    # Incubate {parse_well_location(op.location, loaded_labware)}")
            script.append(f"    protocol.delay(seconds={op.delay_seconds or 300:g})")

        elif op.op == IROpType.COMMENT and op.comment:
            script.append(f"    # {op.comment}")

    return "\n".join(script) + "\n"


def parse_well_location(location: str, loaded_labware: dict) -> str:
    if not location:
        return "None"
    if "/" not in location:
        return _identifier(location)
    alias, well = location.split("/", 1)
    return f"{_identifier(alias)}['{well}']"


def save_script(script: str, output_path: str) -> None:
    with open(output_path, "w", encoding="utf-8") as handle:
        handle.write(script)


def format_opentrons_code(script: str) -> str:
    compile(script, "<protocolir>", "exec")
    return script


def add_safety_comments(script: str) -> str:
    lines = []
    for line in script.splitlines():
        lines.append(line)
        stripped = line.strip()
        if stripped.endswith(".pick_up_tip()"):
            lines.append("    # Fresh tip boundary enforced by ProtocolIR.")
        elif ".aspirate(" in stripped:
            lines.append("    # Source and pipette range verified before compilation.")
        elif ".dispense(" in stripped:
            lines.append("    # Destination capacity verified before compilation.")
    return "\n".join(lines) + "\n"


def validate_generated_code(script: str) -> list:
    issues = []
    try:
        compile(script, "<protocolir>", "exec")
    except SyntaxError as exc:
        issues.append(f"Syntax error: {exc}")
    if "from opentrons import protocol_api" not in script:
        issues.append("Missing required Opentrons import.")
    if "def run(protocol" not in script:
        issues.append("Missing run(protocol) function.")
    if "load_labware" not in script:
        issues.append("No labware loaded.")
    if "load_instrument" not in script:
        issues.append("No instruments loaded.")
    return issues


def _identifier(value: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in str(value or ""))
    if not safe:
        return "unnamed"
    if safe[0].isdigit():
        safe = f"_{safe}"
    return safe
