#!/usr/bin/env python3
"""Streamlit Community Cloud entrypoint for ProtocolIR.

This app intentionally runs a cloud-safe pipeline path that skips the local
Opentrons simulator step while preserving parsing, grounding, IR verification,
repair, reward scoring, compilation, and audit/certificate generation.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

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


st.set_page_config(page_title="ProtocolIR Cloud Demo", layout="wide")
st.title("ProtocolIR Cloud Demo")
st.caption(
    "Live, cloud-safe judge UI: parse -> verify -> repair -> compile -> audit/certificate."
)
st.info(
    "Simulation is intentionally skipped in cloud mode. Full simulator-backed demo is available in local/SCC runs."
)

protocol_text = st.text_area("Protocol text", value=DEMO_TEXT, height=220)
run = st.button("Run ProtocolIR", type="primary")

if run:
    try:
        pipeline = run_cloud_pipeline(protocol_text, source_url="cloud://streamlit")
    except Exception as exc:
        st.error(f"Pipeline failed: {exc}")
        st.stop()

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

