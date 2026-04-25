"""
LAYER 8: Simulator Validation
Runs generated Opentrons scripts through the simulator.
"""

import subprocess
import tempfile
from pathlib import Path
from typing import Optional
from protocolir.schemas import SimulationResult


def simulate_opentrons_script(
    script: str, timeout_seconds: int = 30
) -> SimulationResult:
    """
    Simulate an Opentrons script using the built-in simulator.

    Args:
        script: Python script content
        timeout_seconds: Maximum time to wait for simulation

    Returns:
        SimulationResult with pass/fail status and details
    """

    # Write script to temporary file
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False
    ) as f:
        f.write(script)
        temp_path = f.name

    try:
        # Try to run with opentrons simulator
        result = subprocess.run(
            ["python", "-m", "opentrons.simulate", temp_path],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )

        if result.returncode == 0:
            # Parse simulation output
            sim_result = parse_simulation_output(result.stdout)
            sim_result.passed = True
            sim_result.log = result.stdout
            return sim_result
        else:
            return SimulationResult(
                passed=False,
                errors=result.stderr.split("\n") if result.stderr else [],
                log=result.stdout,
            )

    except subprocess.TimeoutExpired:
        return SimulationResult(
            passed=False,
            errors=[f"Simulation timed out after {timeout_seconds} seconds"],
        )

    except FileNotFoundError:
        # opentrons.simulate not available, do basic validation instead
        return basic_script_validation(script)

    except Exception as e:
        return SimulationResult(
            passed=False,
            errors=[str(e)],
        )

    finally:
        # Clean up temp file
        Path(temp_path).unlink(missing_ok=True)


def parse_simulation_output(output: str) -> SimulationResult:
    """
    Parse Opentrons simulator output to extract statistics.

    Args:
        output: Simulator stdout

    Returns:
        SimulationResult with parsed statistics
    """

    result = SimulationResult(passed=True, command_count=0)

    lines = output.split("\n")

    for line in lines:
        if "aspirate" in line.lower():
            result.aspirate_count += 1
            result.command_count += 1

        elif "dispense" in line.lower():
            result.dispense_count += 1
            result.command_count += 1

        elif "pick_up_tip" in line.lower() or "drop_tip" in line.lower():
            result.tip_count += 1
            result.command_count += 1

        elif "error" in line.lower() or "exception" in line.lower():
            result.errors.append(line)

        elif "warning" in line.lower():
            result.warnings.append(line)

    return result


def basic_script_validation(script: str) -> SimulationResult:
    """
    Basic validation when simulator not available.
    Checks syntax and structure without actual simulation.

    Args:
        script: Python script content

    Returns:
        SimulationResult based on basic checks
    """

    result = SimulationResult(passed=True)
    issues = []

    # Check for required imports
    if "from opentrons import protocol_api" not in script:
        issues.append("Missing required import")
        result.passed = False

    # Check for run function
    if "def run(protocol" not in script:
        issues.append("Missing run(protocol) function")
        result.passed = False

    # Try to compile as Python
    try:
        compile(script, "<string>", "exec")
    except SyntaxError as e:
        issues.append(f"Syntax error: {e}")
        result.passed = False

    # Count operations
    result.aspirate_count = script.count("aspirate(")
    result.dispense_count = script.count("dispense(")
    result.tip_count = script.count("pick_up_tip(") + script.count("drop_tip()")
    result.command_count = (
        result.aspirate_count + result.dispense_count + result.tip_count
    )

    result.errors = issues

    return result


def validate_script_before_simulation(script: str) -> tuple:
    """
    Validate script before attempting to simulate.

    Returns:
        Tuple of (is_valid, issues_list)
    """

    issues = []

    # Syntax check
    try:
        compile(script, "<string>", "exec")
    except SyntaxError as e:
        issues.append(f"Syntax error: {e}")

    # Required elements
    if "from opentrons import protocol_api" not in script:
        issues.append("Missing opentrons import")

    if "def run(protocol" not in script:
        issues.append("Missing run function")

    if "metadata" not in script:
        issues.append("Missing metadata")

    # Basic structure
    if script.count("load_labware") == 0:
        issues.append("No labware loaded")

    if script.count("load_instrument") == 0:
        issues.append("No instruments loaded")

    return (len(issues) == 0, issues)


def summarize_simulation_result(result: SimulationResult) -> str:
    """Generate human-readable summary of simulation result."""

    if result.passed:
        summary = "✓ SIMULATION PASSED\n"
        summary += f"  Commands executed: {result.command_count}\n"
        summary += f"  Aspirates: {result.aspirate_count}\n"
        summary += f"  Dispenses: {result.dispense_count}\n"
        summary += f"  Tip operations: {result.tip_count}\n"

        if result.warnings:
            summary += f"  Warnings: {len(result.warnings)}\n"

    else:
        summary = "✗ SIMULATION FAILED\n"
        if result.errors:
            summary += "  Errors:\n"
            for error in result.errors[:3]:
                summary += f"    - {error}\n"

    return summary
