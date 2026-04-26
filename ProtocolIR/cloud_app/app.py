#!/usr/bin/env python3
"""Streamlit Community Cloud entrypoint for ProtocolIR.

This app provides two modes:
- Replay: deterministic, baked-in evidence scenarios for reliable review.
- Live: real cloud-safe execution path (no local Opentrons simulator).
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict

import streamlit as st

# Make parent directory importable (ProtocolIR/).
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from protocolir.analysis.dependency_analyzer import analyze_dependencies, get_recommended_fix
from protocolir.analysis.flow_visualizer import ir_flow_mermaid
from protocolir.analysis.risk_scoring import get_severity_color, score_violations
from protocolir.audit import create_executive_summary, generate_audit_report
from protocolir.certificate import generate_certificate
from protocolir.compiler import compile_to_opentrons
from protocolir.contamination_graph import contamination_mermaid
from protocolir.features import extract_trajectory_features
from protocolir.grounder import build_deck_layout, ground_actions
from protocolir.ir_builder import build_ir
from protocolir.parser import parse_protocol
from protocolir.repair import repair_iteratively
from protocolir.reward_model import RewardModel, domain_prior_reward_model
from protocolir.schemas import ProtocolPipeline, SimulationResult
from protocolir.verifier import verify_ir

SCENARIO_ROOT = ROOT / "cloud_app" / "scenarios"
SCENARIO_INDEX = SCENARIO_ROOT / "index.json"

DEMO_TEXT = """
PCR Master Mix Setup

Materials:
- DNA template samples
- PCR master mix

Steps:
1. Prepare 8 samples in a 96-well PCR plate.
2. Add 10 uL of DNA template to the corresponding sample well.
3. Add 40 uL of PCR master mix to each well.
4. Mix gently by pipetting up and down 3 times.
5. Keep the plate on ice until thermal cycling.
""".strip()


@st.cache_resource
def _load_reward_model() -> RewardModel:
    learned_path = ROOT / "models" / "learned_weights.json"
    if learned_path.exists():
        return RewardModel.load(str(learned_path))
    return domain_prior_reward_model()


def run_cloud_pipeline(raw_text: str, source_url: str) -> ProtocolPipeline:
    pipeline = ProtocolPipeline(raw_text=raw_text, source_url=source_url)

    parsed = parse_protocol(raw_text, source_url=source_url)
    pipeline.parsed = parsed

    pipeline.deck_layout = build_deck_layout(parsed.sample_count)
    pipeline.grounded = ground_actions(parsed, pipeline.deck_layout)

    pipeline.ir_original = build_ir(pipeline.grounded, pipeline.deck_layout)
    pipeline.violations_before_repair = verify_ir(pipeline.ir_original)
    pipeline.violations = list(pipeline.violations_before_repair)

    reward_model = _load_reward_model()
    before_features = extract_trajectory_features(
        pipeline.ir_original, pipeline.violations_before_repair
    )
    pipeline.reward_before = reward_model.score_trajectory(before_features).total_score

    if pipeline.violations_before_repair:
        repaired, repairs, remaining = repair_iteratively(
            pipeline.ir_original,
            pipeline.violations_before_repair,
            max_iterations=5,
        )
        pipeline.ir_repaired = repaired
        pipeline.repairs_applied = repairs
        pipeline.violations_after_repair = remaining
    else:
        pipeline.ir_repaired = pipeline.ir_original
        pipeline.violations_after_repair = []

    after_features = extract_trajectory_features(
        pipeline.ir_repaired or [],
        pipeline.violations_after_repair,
    )
    pipeline.reward_score = reward_model.score_trajectory(after_features)
    pipeline.reward_after = pipeline.reward_score.total_score

    pipeline.generated_script = compile_to_opentrons(pipeline.ir_repaired or [])
    pipeline.simulation_result = SimulationResult(
        passed=not pipeline.violations_after_repair,
        used_real_simulator=False,
        warnings=[
            "Cloud mode: local Opentrons simulator is skipped in this deployment.",
        ],
    )

    pipeline.audit_report = generate_audit_report(pipeline)
    return pipeline


def _load_scenario_index() -> Dict[str, Any]:
    if not SCENARIO_INDEX.exists():
        return {"scenarios": []}
    return json.loads(SCENARIO_INDEX.read_text(encoding="utf-8"))


def _read_text(base: Path, rel: str) -> str:
    path = base / rel
    if not path.exists():
        return f"[missing] {path}"
    return path.read_text(encoding="utf-8", errors="replace")


def _read_json(base: Path, rel: str) -> Dict[str, Any]:
    path = base / rel
    if not path.exists():
        return {"_error": f"missing file: {path}"}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"_error": f"invalid json in {path}: {exc}"}


_PATH_PATTERNS = [
    r"/projectnb/[^\s`]+",
    r"/usr[^\s`]*",
    r"/scratch/[^\s`]+",
    r"/tmp/[^\s`]+",
    r"/home/[^\s`]+",
    r"/opt/[^\s`]+",
    r"[A-Za-z]:\\[^\s`]+",
    r"\b(?:judge_demo_output|demo_bundle_output|comparison_output|outputs_demo|results)[^\s`]*",
]


def _sanitize_text(text: str) -> str:
    sanitized = text
    for pattern in _PATH_PATTERNS:
        sanitized = re.sub(pattern, "[redacted-path]", sanitized)
    return sanitized


def _sanitize_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _sanitize_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_sanitize_json(v) for v in value]
    if isinstance(value, str):
        return _sanitize_text(value)
    return value


def _status_badge(status: str) -> str:
    color = {
        "PASS": "#16a34a",
        "EXPECTED_FAILURE": "#ea580c",
        "FAIL": "#dc2626",
    }.get(status, "#334155")
    return (
        f"<span style='display:inline-block;padding:3px 8px;border-radius:10px;"
        f"background:{color};color:white;font-size:12px'>{status}</span>"
    )


def _summarize_comparison_report(report_text: str) -> Dict[str, Any]:
    summary: Dict[str, Any] = {
        "protocolir_exit": "unknown",
        "baseline_exit": "unknown",
        "out_of_tips": False,
        "labware_error": False,
        "sim_fail": False,
    }
    for line in report_text.splitlines():
        if "| Command exit code |" in line:
            parts = [part.strip() for part in line.split("|") if part.strip()]
            if len(parts) >= 3:
                summary["baseline_exit"] = parts[1]
                summary["protocolir_exit"] = parts[2]
        if "OutOfTipsError" in line:
            summary["out_of_tips"] = True
        if "load_labware(" in line and ("bio-rad" in line or "biorad-" in line):
            summary["labware_error"] = True
        if "Status: FAIL" in line or "simulator status: fail" in line.lower():
            summary["sim_fail"] = True
    return summary


def render_pipeline_result(pipeline: ProtocolPipeline) -> None:
    before = pipeline.violations_before_repair or pipeline.violations
    after = pipeline.violations_after_repair
    risk = score_violations(before)
    cert = generate_certificate(
        pipeline.parsed.goal if pipeline.parsed else "ProtocolIR cloud run",
        before,
        after,
    )
    deps = analyze_dependencies(before)

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Before violations", len(before))
    c2.metric("After violations", len(after))
    c3.metric("Repairs", len(pipeline.repairs_applied))
    c4.metric("Risk level", risk["risk_level"])
    c5.metric("Status", "PASS" if len(after) == 0 else "REVIEW")

    tabs = st.tabs(
        [
            "Summary",
            "Risk",
            "Dependencies",
            "Parsed",
            "IR",
            "Repairs",
            "Python",
            "Audit",
            "Certificate",
            "Contamination Graph",
            "IR Flow",
        ]
    )

    with tabs[0]:
        st.code(create_executive_summary(pipeline), language="markdown")

    with tabs[1]:
        rc1, rc2, rc3, rc4 = st.columns(4)
        rc1.metric("Total", risk["total_violations"])
        rc2.metric("Critical", risk["critical_count"])
        rc3.metric("High", risk["high_count"])
        rc4.metric("Medium", risk["medium_count"])
        st.metric("Estimated impact if executed", f"${int(risk['total_impact_usd']):,}")
        for vtype, details in risk["severity_details"].items():
            st.markdown(
                f"<div style='border-left:4px solid {get_severity_color(details['severity'])}; "
                f"padding:8px 12px; margin:8px 0;'>"
                f"<b>{vtype}</b> (x{details['count']}) - {details['severity']}<br/>"
                f"<small>{details['reason']}</small></div>",
                unsafe_allow_html=True,
            )

    with tabs[2]:
        if not deps["chains"]:
            st.success("No dependency chains detected from violations.")
        for chain in deps["chains"]:
            with st.expander(f"{chain['severity']}: {chain['root_cause']}"):
                st.write(f"Reason: {chain['reason']}")
                st.write("Cascading effects:")
                for effect in chain["cascading_violations"]:
                    st.write(f"- {effect}")
                st.write(f"Impact: {chain['impact']}")
                st.write(f"Fix: {chain['fix']}")
        if before:
            st.subheader("Violation-specific recommended fixes")
            for vtype in sorted({violation.violation_type for violation in before}):
                st.write(f"- {vtype}: {get_recommended_fix(vtype)}")

    with tabs[3]:
        st.json(pipeline.parsed.model_dump() if pipeline.parsed else {})
    with tabs[4]:
        st.json([op.model_dump() for op in (pipeline.ir_repaired or [])])
    with tabs[5]:
        st.write(pipeline.repairs_applied or ["No repairs applied."])
    with tabs[6]:
        st.code(pipeline.generated_script or "", language="python")
    with tabs[7]:
        st.markdown(pipeline.audit_report or "")
    with tabs[8]:
        st.json(cert)
        st.download_button(
            "Download safety_certificate.json",
            data=json.dumps(cert, indent=2),
            file_name="safety_certificate.json",
            mime="application/json",
        )
    with tabs[9]:
        st.code(contamination_mermaid(pipeline.ir_repaired or []), language="mermaid")
    with tabs[10]:
        st.code(ir_flow_mermaid(pipeline.ir_repaired or [], before), language="mermaid")


def render_replay_mode() -> None:
    index = _load_scenario_index()
    scenarios = index.get("scenarios", [])
    if not scenarios:
        st.error("No replay scenarios found.")
        return

    ids = {scenario["name"]: scenario for scenario in scenarios}
    selected_name = st.selectbox("Scenario", list(ids.keys()))
    scenario = ids[selected_name]
    scenario_dir = SCENARIO_ROOT / scenario["id"]

    st.markdown(
        f"**Type:** `{scenario.get('classification', 'unknown')}`  \n"
        f"**Mode:** `{scenario.get('mode', 'unknown')}`  \n"
        f"**Status:** {_status_badge(scenario.get('status', 'UNKNOWN'))}",
        unsafe_allow_html=True,
    )
    st.write(scenario.get("description", ""))

    ev = scenario.get("evidence", {})
    tabs = st.tabs(["Overview", "Artifacts", "Detailed Logs (Advanced)"])

    with tabs[0]:
        cert_obj = _sanitize_json(_read_json(scenario_dir, ev["certificate"])) if "certificate" in ev else {}
        risk_obj = _sanitize_json(_read_json(scenario_dir, ev["risk"])) if "risk" in ev else {}
        total_v = risk_obj.get("total_violations", "N/A") if isinstance(risk_obj, dict) else "N/A"
        risk_level = risk_obj.get("risk_level", "N/A") if isinstance(risk_obj, dict) else "N/A"
        cert_status = cert_obj.get("verdict", "N/A") if isinstance(cert_obj, dict) else "N/A"
        c1, c2, c3 = st.columns(3)
        c1.metric("Verdict", cert_status)
        c2.metric("Risk Level", risk_level)
        c3.metric("Violations", total_v)

        scenario_class = scenario.get("classification")
        if scenario_class == "repair_positive":
            st.success(
                "Interpretation: This is an unsafe-input recovery case. The system detected violations, "
                "applied repairs, and reached a simulator-validated SAFE outcome."
            )
        elif scenario.get("status") == "PASS":
            st.success(
                "Interpretation: This run is a positive sanity case. The protocol completed "
                "with a SAFE verdict and auditable artifacts."
            )
        elif scenario.get("status") == "EXPECTED_FAILURE":
            st.warning(
                "Interpretation: This is an intentional negative sanity case. Failure traces are "
                "expected and demonstrate transparent error handling."
            )
        else:
            st.info(
                "Interpretation: Review the artifacts below to confirm safety and execution behavior."
            )

        if scenario.get("status") == "EXPECTED_FAILURE":
            st.warning(
                "This scenario is intentionally included as a negative sanity case. "
                "Failure traces are expected and demonstrate transparent error reporting."
            )
        if "summary" in ev:
            st.subheader("Summary")
            st.code(_sanitize_text(_read_text(scenario_dir, ev["summary"])), language="markdown")
        if "comparison_report" in ev:
            st.subheader("Comparison Report")
            report = _read_text(scenario_dir, ev["comparison_report"])
            parsed = _summarize_comparison_report(report)
            c1, c2, c3 = st.columns(3)
            c1.metric("ProtocolIR exit", parsed["protocolir_exit"])
            c2.metric("Baseline exit", parsed["baseline_exit"])
            c3.metric("OutOfTips detected", "Yes" if parsed["out_of_tips"] else "No")
            if parsed["labware_error"]:
                st.info("Report includes a baseline labware-resolution error trace.")
            if parsed["sim_fail"]:
                st.info("Simulation failure is present in this scenario report.")
            with st.expander("Open full comparison report"):
                st.markdown(_sanitize_text(report))
        if "certificate" in ev:
            st.subheader("Safety Certificate")
            with st.expander("Open certificate details", expanded=False):
                st.json(_sanitize_json(_read_json(scenario_dir, ev["certificate"])))
        if "risk" in ev:
            st.subheader("Risk Summary")
            with st.expander("Open risk details", expanded=False):
                st.json(_sanitize_json(_read_json(scenario_dir, ev["risk"])))
        if "dependency" in ev:
            st.subheader("Dependency Summary")
            with st.expander("Open dependency details", expanded=False):
                st.json(_sanitize_json(_read_json(scenario_dir, ev["dependency"])))

    with tabs[1]:
        for label, rel in ev.items():
            path = scenario_dir / rel
            exists = path.exists()
            st.write(f"- `{label}` -> `{rel}` ({'ok' if exists else 'missing'})")

    with tabs[2]:
        st.caption("Advanced artifacts for technical review and debugging.")
        for label, rel in ev.items():
            st.markdown(f"### {label}")
            path = scenario_dir / rel
            if path.suffix.lower() == ".json":
                st.json(_sanitize_json(_read_json(scenario_dir, rel)))
            else:
                st.code(_sanitize_text(_read_text(scenario_dir, rel)))


def render_live_mode() -> None:
    if not os.getenv("OPENROUTER_API_KEY"):
        st.warning("`OPENROUTER_API_KEY` is not set. Live mode will fail until the secret is configured.")
    protocol_text = st.text_area("Protocol text", value=DEMO_TEXT, height=220)
    run = st.button("Run Live Pipeline", type="primary")
    if not run:
        return
    try:
        pipeline = run_cloud_pipeline(protocol_text, source_url="cloud://streamlit")
    except Exception as exc:
        st.error(f"Pipeline failed: {_sanitize_text(str(exc))}")
        st.stop()
    render_pipeline_result(pipeline)


st.set_page_config(page_title="ProtocolIR Cloud Demo", layout="wide")
st.title("ProtocolIR Cloud Demo")
st.caption("Replay deterministic scenarios or run live cloud-safe execution.")
st.info(
    "Replay mode is deterministic and recommended for quick sanity checks. "
    "Live mode performs real parsing/verification/compilation in cloud-safe mode."
)

mode = st.radio("Execution mode", ["Replay Scenarios", "Live Run"], horizontal=True)
if mode == "Replay Scenarios":
    render_replay_mode()
else:
    render_live_mode()
