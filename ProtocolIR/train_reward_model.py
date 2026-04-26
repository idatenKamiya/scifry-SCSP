#!/usr/bin/env python3
"""Train Bayesian IRL reward posterior from local expert/corrupted traces."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any, Dict, List

from protocolir.ast_extractor import extract_script_features
from protocolir.bayesian_irl import fit_bayesian_irl, save_posterior_report
from protocolir.features import extract_trajectory_features
from protocolir.ir_builder import build_ir
from protocolir.parser import training_parse_pcr_text
from protocolir.grounder import ground_actions
from protocolir.reward_model import DEFAULT_REWARD_WEIGHTS
from protocolir.schemas import IROpType
from protocolir.verifier import verify_ir


def main() -> None:
    print("=" * 72)
    print("PROTOCOLIR BAYESIAN IRL TRAINING")
    print("=" * 72)

    data_report = audit_local_data()
    print(f"Expert scripts: {data_report['expert_scripts']}")
    print(f"Corrupted traces: {data_report['corrupted_traces']}")
    print(f"Generated counterfactual traces: {data_report['generated_counterfactuals']}")
    print(f"protocols.io JSON records: {data_report['protocols_io_json']}")
    print(f"protocols.io step records: {data_report['protocols_io_steps']}")

    expert_features = load_expert_features()
    corrupted_features = load_corrupted_features()
    corrupted_features.extend(load_generated_counterfactual_features())
    expert_features.extend(load_protocol_text_expert_features())
    expert_features.extend(load_protocols_io_json_expert_features())

    if not expert_features:
        raise RuntimeError("No expert feature vectors found")
    if not corrupted_features:
        raise RuntimeError("No corrupted feature vectors found")

    draws = int(_env_or_default("PROTOCOLIR_MCMC_DRAWS", "1000"))
    warmup = int(_env_or_default("PROTOCOLIR_MCMC_WARMUP", "500"))
    chains = int(_env_or_default("PROTOCOLIR_MCMC_CHAINS", "4"))
    max_pairs = int(_env_or_default("PROTOCOLIR_MAX_PAIRS", "0"))
    method = _env_or_default("PROTOCOLIR_BAYESIAN_METHOD", "laplace")

    print(
        f"Fitting Bayesian IRL posterior: chains={chains}, warmup={warmup}, "
        f"draws={draws}, max_pairs={'all' if max_pairs <= 0 else max_pairs}, method={method}"
    )
    posterior = fit_bayesian_irl(
        expert_features,
        corrupted_features,
        draws=draws,
        warmup=warmup,
        chains=chains,
        max_pairs=max_pairs,
        method=method,
    )

    models = Path("models")
    models.mkdir(exist_ok=True)
    posterior_samples_path = models / "reward_posterior_samples.json"
    posterior_report_path = models / "reward_posterior_report.md"
    learned_weights_path = models / "learned_weights.json"
    posterior.save(str(posterior_samples_path))
    save_posterior_report(posterior, str(posterior_report_path))
    save_dataset_report(data_report, "DATASET_REPORT.md")

    max_rhat = _max_finite(posterior.r_hat)
    min_ess = _min_finite(posterior.effective_sample_size)
    print(f"Inference method: {posterior.inference_method}")
    print(f"Acceptance rate: {posterior.acceptance_rate:.3f}")
    print(f"Max R-hat: {max_rhat:.3f}")
    print(f"Min ESS: {min_ess:.1f}")
    if posterior.diagnostic_status != "PASS":
        if learned_weights_path.exists():
            try:
                learned_weights_path.unlink()
            except OSError:
                print(
                    "WARNING: could not remove existing models/learned_weights.json; "
                    "main.py will still reject it while diagnostics are REVIEW."
                )
        raise RuntimeError(
            "Bayesian IRL posterior diagnostics did not pass "
            f"(method={posterior.inference_method}, max R-hat={max_rhat:.3f}, min ESS={min_ess:.1f}). "
            "Inspect models/reward_posterior_report.md before using this reward model."
        )

    posterior.reward_model().save(str(learned_weights_path))
    print("Saved:")
    print("  models/learned_weights.json")
    print("  models/reward_posterior_samples.json")
    print("  models/reward_posterior_report.md")
    print("  DATASET_REPORT.md")


def audit_local_data() -> Dict[str, int]:
    expert_script_count = len(_expert_script_paths())
    return {
        "expert_scripts": expert_script_count,
        "corrupted_traces": len(_corrupted_script_paths()),
        "generated_counterfactuals": expert_script_count * 4,
        "protocols_io_text": len(list(Path("data/protocols_io_raw").glob("*.txt"))),
        "opentrons_library_text": len(list(Path("data/protocols_io_raw/opentrons_library").glob("*.txt"))),
        "protocols_io_json": len(list(Path("data/protocols_io_raw/json").glob("*.json"))),
        "protocols_io_steps": len(list(Path("data/protocols_io_raw/steps").glob("*.json"))),
    }


def load_expert_features() -> List[Dict[str, float]]:
    features = []
    for path in _expert_script_paths():
        features.append(script_features(path.read_text(encoding="utf-8", errors="replace"), expert=True))
    return features


def load_corrupted_features() -> List[Dict[str, float]]:
    features = []
    for path in _corrupted_script_paths():
        features.append(script_features(path.read_text(encoding="utf-8", errors="replace"), expert=False))
    return features


def load_generated_counterfactual_features() -> List[Dict[str, float]]:
    """
    Create deterministic unsafe alternatives from expert scripts.

    These are not claimed as real protocols. They are counterfactual negative
    trajectories used by inverse-preference learning: expert traces should score
    higher than missing-tip, missing-mix, over-range, and contamination variants.
    """

    features = []
    for path in _expert_script_paths():
        code = path.read_text(encoding="utf-8", errors="replace")
        for corrupted in _counterfactual_scripts(code):
            features.append(script_features(corrupted, expert=False))
    return features


def load_protocol_text_expert_features() -> List[Dict[str, float]]:
    """
    Use local protocol text as additional weak expert evidence.

    This does not call the production LLM parser. It builds a deterministic IR
    only for reward-training data augmentation, then verifies the resulting IR.
    The production parser remains strict OpenRouter-only.
    """

    features = []
    text_paths = list(Path("data/protocols_io_raw").glob("*.txt"))
    text_paths.extend(Path("data/protocols_io_raw/opentrons_library").glob("*.txt"))
    for path in sorted(text_paths):
        text = path.read_text(encoding="utf-8", errors="replace")
        parsed = training_parse_pcr_text(text, source_url=str(path))
        ir = build_ir(ground_actions(parsed))
        violations = verify_ir(ir)
        features.append(extract_trajectory_features(ir, violations).model_dump(exclude_unset=False))
    return features


def _expert_script_paths() -> List[Path]:
    paths = list(Path("data/expert_scripts").glob("*.py"))
    paths.extend(Path("data/expert_scripts_large").glob("*.py"))
    paths.extend(Path("../AIZU/data/expert_scripts").glob("*.py"))
    return sorted(paths)


def _corrupted_script_paths() -> List[Path]:
    paths = list(Path("data/corrupted_traces").glob("*.py"))
    paths.extend(Path("../AIZU/data/corrupted_traces").glob("*.py"))
    return sorted(paths)


def load_protocols_io_json_expert_features() -> List[Dict[str, float]]:
    features = []
    text_by_stem: Dict[str, str] = {}

    for path in sorted(Path("data/protocols_io_raw/json").glob("*.json")):
        payload = _read_json(path)
        text = _extract_text(payload)
        if text.strip():
            text_by_stem[path.stem] = text

    for path in sorted(Path("data/protocols_io_raw/steps").glob("*.json")):
        stem = path.name.replace(".steps.json", "")
        payload = _read_json(path)
        step_text = _extract_text(payload)
        if step_text.strip():
            text_by_stem[stem] = "\n".join([text_by_stem.get(stem, ""), step_text]).strip()

    for stem, text in sorted(text_by_stem.items()):
        parsed = training_parse_pcr_text(text, source_url=f"protocols.io://{stem}")
        ir = build_ir(ground_actions(parsed))
        violations = verify_ir(ir)
        features.append(extract_trajectory_features(ir, violations).model_dump(exclude_unset=False))
    return features


def script_features(code: str, *, expert: bool) -> Dict[str, float]:
    return extract_script_features(code, expert=expert)


def legacy_script_features(code: str, *, expert: bool) -> Dict[str, float]:
    aspirates = code.count(".aspirate(")
    dispenses = code.count(".dispense(")
    mixes = code.count(".mix(")
    pickups = code.count("pick_up_tip(")
    drops = code.count("drop_tip(")
    p20_over_range = len(
        [
            float(match)
            for match in re.findall(r"p20\.aspirate\((\d+(?:\.\d+)?)", code)
            if float(match) > 20
        ]
    )
    lower = code.lower()

    contamination = 0 if expert else int("cross-contamination" in lower or "same tip" in lower)
    overflow = 0 if expert else int("overflow" in lower)
    missing_mix = 0 if mixes else max(1, dispenses // 12)
    if expert:
        missing_mix = 0
    no_tip = 0 if expert else int(pickups < max(1, aspirates // 2))

    feature = {name: 0.0 for name in DEFAULT_REWARD_WEIGHTS}
    feature.update(
        {
            "contamination_violations": contamination,
            "pipette_range_violations": p20_over_range,
            "well_overflow_violations": overflow,
            "aspirate_no_tip_violations": no_tip,
            "dispense_no_tip_violations": no_tip,
            "mix_no_tip_violations": 0,
            "unknown_location_violations": 0,
            "invalid_location_violations": 0,
            "drop_tip_with_liquid_violations": 0,
            "missing_mix_events": missing_mix,
            "tip_changes": drops,
            "aspirate_events": aspirates,
            "dispense_events": dispenses,
            "mix_events": mixes,
            "total_operations": aspirates + dispenses + mixes + pickups + drops,
            "tip_changed_between_different_reagents": max(0, min(pickups, drops) - contamination),
            "complete_transfer_pairs": min(aspirates, dispenses, pickups, drops),
        }
    )
    return feature


def _counterfactual_scripts(code: str) -> List[str]:
    no_tip = re.sub(r"^\s*.*pick_up_tip\(.*\)\s*$", "", code, flags=re.MULTILINE)
    missing_mix = re.sub(r"^\s*.*\.mix\(.*\)\s*$", "", code, flags=re.MULTILINE)
    contaminated = code + "\n# cross-contamination same tip counterfactual\n"
    over_range = re.sub(
        r"p300\.aspirate\((\d+(?:\.\d+)?)",
        lambda match: f"p20.aspirate({max(float(match.group(1)), 40.0):g}",
        code,
        count=1,
    )
    if over_range == code:
        over_range = code + "\np20.aspirate(40, plate['A1'])  # over-range counterfactual\n"
    return [no_tip, missing_mix, contaminated, over_range]


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8", errors="replace"))


def _extract_text(value: Any) -> str:
    chunks: List[str] = []

    def walk(item: Any, key: str = "") -> None:
        if isinstance(item, dict):
            for child_key, child_value in item.items():
                walk(child_value, str(child_key))
        elif isinstance(item, list):
            for child in item:
                walk(child, key)
        elif isinstance(item, str):
            normalized_key = key.lower()
            if normalized_key in {
                "title",
                "name",
                "abstract",
                "description",
                "body",
                "content",
                "markdown",
                "text",
                "materials",
                "guidelines",
            }:
                cleaned = re.sub(r"<[^>]+>", " ", item)
                cleaned = " ".join(cleaned.split())
                if len(cleaned) > 20:
                    chunks.append(cleaned)

    walk(value)
    return "\n".join(dict.fromkeys(chunks))


def save_dataset_report(data_report: Dict[str, int], path: str) -> None:
    lines = [
        "# ProtocolIR Dataset Report",
        "",
        "| Dataset Slice | Count |",
        "|---|---:|",
    ]
    for key, value in data_report.items():
        lines.append(f"| {key} | {value} |")
    lines.extend(
        [
            "",
            "Interpretation:",
            "- This is sufficient for a hackathon demonstration and honest posterior uncertainty.",
            "- It is not yet sufficient to claim broad cross-domain biology generalization.",
            "- The strongest validated scope is PCR/qPCR liquid-handling protocol compilation.",
        ]
    )
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def corrupt_trajectory(ir_ops):
    corrupted = [op.model_copy(deep=True) for op in ir_ops]
    removed_pickup = False
    for idx, op in enumerate(list(corrupted)):
        if op.op == IROpType.PICK_UP_TIP and not removed_pickup:
            del corrupted[idx]
            removed_pickup = True
            break
    for op in corrupted:
        if op.op in {IROpType.ASPIRATE, IROpType.DISPENSE, IROpType.MIX} and op.volume_ul and op.volume_ul > 20:
            op.pipette = "p20"
    return corrupted


def _env_or_default(name: str, default: str) -> str:
    import os

    return os.getenv(name, default)


def _max_finite(values: Dict[str, float]) -> float:
    finite = [value for value in values.values() if math.isfinite(value)]
    return max(finite) if finite else float("nan")


def _min_finite(values: Dict[str, float]) -> float:
    finite = [value for value in values.values() if math.isfinite(value)]
    return min(finite) if finite else float("nan")


if __name__ == "__main__":
    main()
