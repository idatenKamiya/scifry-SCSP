"""Judge-facing safety analysis helpers adapted for ProtocolIR."""

from protocolir.analysis.dependency_analyzer import analyze_dependencies, get_recommended_fix
from protocolir.analysis.flow_visualizer import ir_flow_mermaid
from protocolir.analysis.risk_scoring import get_severity_color, score_violations

__all__ = [
    "score_violations",
    "get_severity_color",
    "analyze_dependencies",
    "get_recommended_fix",
    "ir_flow_mermaid",
]

