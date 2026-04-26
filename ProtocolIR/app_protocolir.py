#!/usr/bin/env python3
"""Streamlit UI for ProtocolIR judge demos."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

import protocolir as pir
from main import _demo_protocol, _load_reward_model, inject_demo_unsafe_errors
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

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Before violations", len(pipeline.violations_before_repair))
    col2.metric("After violations", len(pipeline.violations_after_repair))
    col3.metric("Repairs", len(pipeline.repairs_applied))
    col4.metric("Simulator", "PASS" if pipeline.simulation_result and pipeline.simulation_result.passed else "FAIL")

    tabs = st.tabs(["Parsed", "IR", "Repairs", "Python", "Audit", "Contamination Graph", "Posterior"])
    with tabs[0]:
        st.json(pipeline.parsed.model_dump() if pipeline.parsed else {})
    with tabs[1]:
        st.json([op.model_dump() for op in (pipeline.ir_repaired or [])])
    with tabs[2]:
        st.write(pipeline.repairs_applied)
    with tabs[3]:
        st.code(pipeline.generated_script or "", language="python")
    with tabs[4]:
        st.markdown(pipeline.audit_report or "")
    with tabs[5]:
        st.code(contamination_mermaid(pipeline.ir_repaired or []), language="mermaid")
    with tabs[6]:
        report = Path("models/reward_posterior_report.md")
        st.markdown(report.read_text(encoding="utf-8") if report.exists() else "Run train_reward_model.py first.")
