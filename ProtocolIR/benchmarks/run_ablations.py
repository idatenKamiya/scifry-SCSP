#!/usr/bin/env python3
"""Run ProtocolIR ablations for paper-style evidence tables."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.protocol_cases import get_cases
from main import inject_demo_unsafe_errors, process_protocol
from protocolir.features import extract_trajectory_features
from protocolir.grounder import build_deck_layout, ground_actions
from protocolir.ir_builder import build_ir
from protocolir.parser import parse_protocol
from protocolir.reward_model import DEFAULT_REWARD_WEIGHTS, RewardModel
from protocolir.verifier import verify_ir


def main() -> int:
    parser = argparse.ArgumentParser(description="Run verifier/repair/reward ablations.")
    parser.add_argument("--cases", type=int, default=1, help="Number of benchmark cases to run.")
    parser.add_argument("--output", default="benchmarks/ablations", help="Output directory.")
    parser.add_argument(
        "--stress",
        action="store_true",
        help="Inject deterministic unsafe IR errors before verifier/repair ablations.",
    )
    args = parser.parse_args()

    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    rows = []
    learned_model = RewardModel.load("models/learned_weights.json")

    for case in get_cases(args.cases):
        case_dir = output / case.case_id
        case_dir.mkdir(parents=True, exist_ok=True)
        rows.append(_run_full(case, case_dir / "full", learned_model, args.stress))
        rows.append(_run_no_repair(case, case_dir / "no_repair", learned_model, args.stress))
        rows.append(_run_prior_reward(case, case_dir / "prior_reward", args.stress))
        rows.append(_run_random_reward(case, case_dir / "random_reward", args.stress))
        rows.append(_run_direct_llm(case, case_dir / "direct_llm"))

    (output / "ablation_results.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    (output / "ablation_report.md").write_text(_report(rows), encoding="utf-8")
    print(_report(rows))
    return 0 if all(row["expected_outcome"] == row["observed_outcome"] for row in rows) else 1


def _run_full(case, output: Path, model: RewardModel, stress: bool) -> dict:
    start = time.perf_counter()
    pipeline = process_protocol(case.text, source_url=f"benchmark://{case.case_id}", output_dir=str(output), reward_model=model, stress_test=stress)
    elapsed = time.perf_counter() - start
    return _pipeline_row(case, "full_system", pipeline, elapsed, "PASS")


def _run_prior_reward(case, output: Path, stress: bool) -> dict:
    start = time.perf_counter()
    pipeline = process_protocol(
        case.text,
        source_url=f"benchmark://{case.case_id}",
        output_dir=str(output),
        reward_model=RewardModel(DEFAULT_REWARD_WEIGHTS),
        stress_test=stress,
    )
    elapsed = time.perf_counter() - start
    return _pipeline_row(case, "no_learned_reward_prior_weights", pipeline, elapsed, "PASS")


def _run_random_reward(case, output: Path, stress: bool) -> dict:
    rng = np.random.default_rng(7)
    weights = {
        name: float(rng.normal(0.0, 1.0))
        for name in DEFAULT_REWARD_WEIGHTS
    }
    start = time.perf_counter()
    pipeline = process_protocol(
        case.text,
        source_url=f"benchmark://{case.case_id}",
        output_dir=str(output),
        reward_model=RewardModel(weights),
        stress_test=stress,
    )
    elapsed = time.perf_counter() - start
    return _pipeline_row(case, "random_reward_weights", pipeline, elapsed, "PASS")


def _run_no_repair(case, output: Path, model: RewardModel, stress: bool) -> dict:
    start = time.perf_counter()
    parsed = parse_protocol(case.text, source_url=f"benchmark://{case.case_id}")
    deck = build_deck_layout(parsed.sample_count)
    grounded = ground_actions(parsed, deck)
    ir_ops = build_ir(grounded, deck)
    if stress:
        ir_ops = inject_demo_unsafe_errors(ir_ops)
    violations = verify_ir(ir_ops)
    features = extract_trajectory_features(ir_ops, violations)
    score = model.score_trajectory(features)
    elapsed = time.perf_counter() - start

    output.mkdir(parents=True, exist_ok=True)
    payload = {
        "case_id": case.case_id,
        "variant": "no_repair",
        "protocol_class": case.protocol_class,
        "violations_before": len(violations),
        "violations_after": len(violations),
        "repairs": 0,
        "real_sim_pass": False,
        "reward": score.total_score,
        "elapsed_seconds": elapsed,
    }
    (output / "summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    payload["expected_outcome"] = "FAIL" if stress else "PASS"
    payload["observed_outcome"] = "PASS" if len(violations) == 0 else "FAIL"
    return payload


def _run_direct_llm(case, output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    input_path = output / "protocol.txt"
    input_path.write_text(case.text, encoding="utf-8")
    start = time.perf_counter()
    result = subprocess.run(
        [sys.executable, "baseline_direct_llm.py", str(input_path), "-o", str(output)],
        capture_output=True,
        text=True,
        timeout=240,
    )
    elapsed = time.perf_counter() - start
    payload = _baseline_payload(output / "baseline_report.md")
    row = {
        "case_id": case.case_id,
        "variant": "direct_llm_no_typed_ir",
        "protocol_class": case.protocol_class,
        "violations_before": "N/A",
        "violations_after": payload.get("static_issue_count", "N/A"),
        "repairs": "N/A",
        "real_sim_pass": bool(payload.get("simulator_passed") and payload.get("real_simulator_used")),
        "reward": "N/A",
        "elapsed_seconds": elapsed,
        "returncode": result.returncode,
        "expected_outcome": "MEASURE",
        "observed_outcome": "MEASURE",
    }
    (output / "ablation_stdout_tail.txt").write_text((result.stdout + result.stderr)[-4000:], encoding="utf-8")
    return row


def _pipeline_row(case, variant: str, pipeline, elapsed: float, expected: str) -> dict:
    sim = pipeline.simulation_result
    observed = "PASS" if sim and sim.passed and sim.used_real_simulator and not pipeline.violations_after_repair else "FAIL"
    return {
        "case_id": case.case_id,
        "variant": variant,
        "protocol_class": case.protocol_class,
        "violations_before": len(pipeline.violations_before_repair or pipeline.violations),
        "violations_after": len(pipeline.violations_after_repair),
        "repairs": len(pipeline.repairs_applied),
        "real_sim_pass": bool(sim and sim.passed and sim.used_real_simulator),
        "reward": pipeline.reward_after,
        "elapsed_seconds": elapsed,
        "expected_outcome": expected,
        "observed_outcome": observed,
    }


def _baseline_payload(path: Path) -> dict:
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8", errors="replace")
    marker = "```json"
    if marker not in text:
        return {}
    block = text.split(marker, 1)[1].split("```", 1)[0]
    return json.loads(block)


def _report(rows: list[dict]) -> str:
    lines = [
        "# ProtocolIR Ablation Report",
        "",
        "| Case | Class | Variant | Before | After | Repairs | Real Sim Pass | Reward | Seconds |",
        "|---|---|---|---:|---:|---:|---|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['case_id']} | {row['protocol_class']} | {row['variant']} | "
            f"{row['violations_before']} | {row['violations_after']} | {row['repairs']} | "
            f"{row['real_sim_pass']} | {row['reward']} | {float(row['elapsed_seconds']):.2f} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- `full_system` tests parser, typed IR, verifier, repair, learned reward scoring, compiler, and real simulator.",
            "- `no_repair` isolates the verifier by refusing to repair remaining unsafe IR.",
            "- `no_learned_reward_prior_weights` shows the deterministic safety path without learned posterior weights.",
            "- `random_reward_weights` sanity-checks that random reward weights do not replace hard verification.",
            "- `direct_llm_no_typed_ir` is the generate-Python-directly baseline.",
        ]
    )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
