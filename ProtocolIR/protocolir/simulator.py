"""Layer 8: strict Opentrons simulator integration."""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

from protocolir.schemas import SimulationResult


def simulate_opentrons_script(
    script: str, timeout_seconds: int = 30
) -> SimulationResult:
    """Run the generated protocol through Opentrons simulation if installed."""

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, encoding="utf-8"
    ) as handle:
        handle.write(script)
        temp_path = handle.name

    try:
        result = subprocess.run(
            [sys.executable, "-m", "opentrons.simulate", temp_path],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        combined = "\n".join([result.stdout or "", result.stderr or ""])
        if result.returncode == 0:
            sim_result = parse_simulation_output(result.stdout)
            sim_result.passed = True
            sim_result.log = result.stdout
            sim_result.used_real_simulator = True
            return sim_result
        return SimulationResult(
            passed=False,
            errors=[line for line in combined.splitlines() if line.strip()],
            log=combined,
            used_real_simulator=True,
        )
    except subprocess.TimeoutExpired:
        return SimulationResult(
            passed=False,
            errors=[f"Simulation timed out after {timeout_seconds} seconds."],
            used_real_simulator=True,
        )
    except Exception as exc:
        return SimulationResult(
            passed=False,
            errors=[f"Real Opentrons simulator unavailable: {exc}"],
            used_real_simulator=False,
        )
    finally:
        Path(temp_path).unlink(missing_ok=True)


def parse_simulation_output(output: str) -> SimulationResult:
    result = SimulationResult(passed=True, command_count=0, used_real_simulator=True)
    for line in output.splitlines():
        lower = line.lower()
        if "aspirat" in lower:
            result.aspirate_count += 1
            result.command_count += 1
        elif "dispens" in lower:
            result.dispense_count += 1
            result.command_count += 1
        elif "pick" in lower and "tip" in lower:
            result.tip_count += 1
            result.command_count += 1
        elif "drop" in lower and "tip" in lower:
            result.tip_count += 1
            result.command_count += 1
        elif "warning" in lower:
            result.warnings.append(line)
        elif "error" in lower or "exception" in lower:
            result.errors.append(line)
    return result


def basic_script_validation(script: str) -> SimulationResult:
    result = SimulationResult(passed=True, used_real_simulator=False)
    try:
        compile(script, "<protocolir>", "exec")
    except SyntaxError as exc:
        result.passed = False
        result.errors.append(f"Syntax error: {exc}")

    for required in [
        "from opentrons import protocol_api",
        "def run(protocol",
        "load_labware",
        "load_instrument",
    ]:
        if required not in script:
            result.passed = False
            result.errors.append(f"Missing required code: {required}")

    result.aspirate_count = script.count(".aspirate(")
    result.dispense_count = script.count(".dispense(")
    result.tip_count = script.count(".pick_up_tip(") + script.count(".drop_tip(")
    result.command_count = result.aspirate_count + result.dispense_count + result.tip_count
    return result


def validate_script_before_simulation(script: str) -> tuple:
    issues = []
    try:
        compile(script, "<protocolir>", "exec")
    except SyntaxError as exc:
        issues.append(f"Syntax error: {exc}")
    for required in [
        "from opentrons import protocol_api",
        "def run(protocol",
        "load_labware",
        "load_instrument",
    ]:
        if required not in script:
            issues.append(f"Missing required code: {required}")
    return (len(issues) == 0, issues)


def summarize_simulation_result(result: SimulationResult) -> str:
    if result.passed:
        mode = "real Opentrons simulator" if result.used_real_simulator else "simulator unavailable"
        return (
            f"SIMULATION PASS ({mode})\n"
            f"  Commands executed: {result.command_count}\n"
            f"  Aspirates: {result.aspirate_count}\n"
            f"  Dispenses: {result.dispense_count}\n"
            f"  Tip operations: {result.tip_count}\n"
        )
    errors = "\n".join(f"    - {error}" for error in result.errors[:3])
    return f"SIMULATION FAIL\n  Errors:\n{errors}\n"
