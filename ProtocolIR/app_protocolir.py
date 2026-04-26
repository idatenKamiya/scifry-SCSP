#!/usr/bin/env python3
"""Streamlit UI for ProtocolIR judge demos."""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

import protocolir as pir
from main import _demo_protocol, _load_reward_model, inject_demo_unsafe_errors
from protocolir.analysis.dependency_analyzer import analyze_dependencies, get_recommended_fix
from protocolir.analysis.flow_visualizer import ir_flow_mermaid
from protocolir.analysis.risk_scoring import get_severity_color, score_violations
from protocolir.certificate import generate_certificate
from protocolir.contamination_graph import contamination_mermaid


st.set_page_config(page_title="ProtocolIR", layout="wide")
st.title("ProtocolIR: Verify-Then-Generate Lab Protocol Compiler")

protocol_text = st.text_area("Protocol text", value=_demo_protocol(), height=220)
stress = st.checkbox("Inject unsafe stress case", value=True)
run = st.button("Run ProtocolIR", type="primary")

if run:
    try:
        pipeline = pir.run_protocol_graph(
            protocol_text,
            source_url="ui://protocol",
            reward_model=_load_reward_model(),
            stress_mutator=inject_demo_unsafe_errors if stress else None,
        )
    except Exception as exc:
        st.error(str(exc))
        st.stop()

    before = pipeline.violations_before_repair or pipeline.violations
    after = pipeline.violations_after_repair
    risk = score_violations(before)
    cert = generate_certificate(
        pipeline.parsed.goal if pipeline.parsed else "ProtocolIR run",
        before,
        after,
    )

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Before violations", len(before))
    col2.metric("After violations", len(after))
    col3.metric("Repairs", len(pipeline.repairs_applied))
    col4.metric("Risk level", risk["risk_level"])
    col5.metric("Simulator", "PASS" if pipeline.simulation_result and pipeline.simulation_result.passed else "FAIL")

    tabs = st.tabs(
        [
            "Parsed",
            "IR",
            "Risk",
            "Dependencies",
            "Certificate",
            "Repairs",
            "Python",
            "Audit",
            "Contamination Graph",
            "IR Flow",
            "Posterior",
        ]
    )
    with tabs[0]:
        st.json(pipeline.parsed.model_dump() if pipeline.parsed else {})
    with tabs[1]:
        st.json([op.model_dump() for op in (pipeline.ir_repaired or [])])
    with tabs[2]:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total", risk["total_violations"])
        c2.metric("Critical", risk["critical_count"])
        c3.metric("High", risk["high_count"])
        c4.metric("Medium", risk["medium_count"])
        st.metric("Estimated impact if executed", f"${int(risk['total_impact_usd']):,}")
        for vtype, details in risk["severity_details"].items():
            st.markdown(
                f"<div style='border-left:4px solid {get_severity_color(details['severity'])}; "
                f"padding:8px 12px; margin:8px 0;'>"
                f"<b>{vtype}</b> (x{details['count']}) - {details['severity']}<br/>"
                f"<small>{details['reason']}</small></div>",
                unsafe_allow_html=True,
            )
    with tabs[3]:
        deps = analyze_dependencies(before)
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
    with tabs[4]:
        st.json(cert)
        st.download_button(
            "Download safety_certificate.json",
            data=json.dumps(cert, indent=2),
            file_name="safety_certificate.json",
            mime="application/json",
        )
    with tabs[5]:
        st.write(pipeline.repairs_applied)
    with tabs[6]:
        st.code(pipeline.generated_script or "", language="python")
    with tabs[7]:
        st.markdown(pipeline.audit_report or "")
    with tabs[8]:
        st.code(contamination_mermaid(pipeline.ir_repaired or []), language="mermaid")
    with tabs[9]:
        st.code(ir_flow_mermaid(pipeline.ir_repaired or [], before), language="mermaid")
    with tabs[10]:
        report = Path("models/reward_posterior_report.md")
        st.markdown(report.read_text(encoding="utf-8") if report.exists() else "Run train_reward_model.py first.")
