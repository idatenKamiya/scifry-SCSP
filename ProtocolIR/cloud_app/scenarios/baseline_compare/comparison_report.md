# ProtocolIR vs Direct LLM Comparison

| Metric | Direct LLM Baseline | ProtocolIR |
|---|---:|---:|
| Command exit code | 1 | 0 |
| Real simulator pass | False | True |
| Safety certificate issued | N/A | True |
| Static/built-in safety issues | 0 | 0 |
| Violations before repair | N/A | 0 |
| Violations after repair | N/A | 0 |
| Repairs applied | N/A | 0 |
| Commands | 0 | 304 |

## Interpretation

- Direct LLM baseline is allowed to write Opentrons Python directly.
- ProtocolIR constrains the LLM to semantic JSON, then verifies and repairs typed IR before compilation.
- Static baseline issues are conservative code-level checks, not a replacement for ProtocolIR typed-IR verification.

## Baseline stderr/stdout tail

```text
# Direct LLM Baseline Report

- Generated script bytes: 1677
- Simulator status: FAIL
- Real simulator used: True
- Simulator commands: 0
- Static safety issues: 0

## Static Safety Issue Counts

| Issue | Count |
|---|---:|
| none_detected | 0 |

## First Static Issues

- None detected by static baseline analyzer.

## Simulator Errors

- /usr4/cs585/skandan/.opentrons/robot_settings.json not found. Loading defaults
- Deck calibration not found.
- /usr4/cs585/skandan/.opentrons/deck_calibration.json not found. Loading defaults
- Traceback (most recent call last):
-   File "/projectnb/se740/scifry-SCSP/ProtocolIR/.venv/lib64/python3.12/site-packages/opentrons/protocols/execution/execute_python.py", line 159, in exec_run
-     exec("run(__context)", new_globs)
-   File "<string>", line 1, in <module>
-   File "/scratch/tmp6zm_0lz6.py", line 9, in run
-     pcr_plate = protocol.load_labware(
-                 ^^^^^^^^^^^^^^^^^^^^^^

## Machine Summary

```json
{
  "simulator_passed": false,
  "real_simulator_used": true,
  "command_count": 0,
  "static_issue_count": 0,
  "static_issue_counts": {},
  "failure_reason": ""
}
```


```

## ProtocolIR stderr/stdout tail

```text
Loaded Bayesian reward posterior mean from models/learned_weights.json

========================================================================
PROTOCOLIR: VERIFIED, REWARD-GUIDED PROTOCOL COMPILER
========================================================================

[1/9] Parsing protocol with OpenRouter strict structured output + local RAG...
  Goal: Prepare a 96-well PCR plate with DNA templates and PCR master mix for thermal cycling.
  Parser backend: openrouter
  Samples: 8
  Materials: 2
  Semantic actions: 4
  Ambiguities / reviews flagged: 2

[2/9] Grounding semantic actions to deck/labware/wells...
  Grounded actions: 4

[3/9] Building typed IR...
  IR operations: 113

[4/9] Verifying hard physical constraints...
  Found: 0 total (0 critical, 0 warning)

[5/9] Scoring trajectory before repair...
  Reward before repair: 22075

[6/9] Repairing policy violations with typed IR repair loop...
  No repairs needed.
  Reward after repair: 22075

[7/9] Compiling verified IR to Opentrons Python...
  Generated script bytes: 3951

[8/9] Simulating generated protocol with the real Opentrons simulator...
  Status: PASS (real Opentrons simulator)
  Commands: 304

[9/9] Generating audit artifacts...
  Audit report generated.
  Script: judge_demo_output/comparison_output/protocolir/protocol.py
  Report: judge_demo_output/comparison_output/protocolir/audit_report.md
  Summary: judge_demo_output/comparison_output/protocolir/summary.txt
  Certificate: judge_demo_output/comparison_output/protocolir/safety_certificate.json
  Risk: judge_demo_output/comparison_output/protocolir/risk_summary.json
  Dependencies: judge_demo_output/comparison_output/protocolir/dependency_summary.json

========================================================================
PIPELINE COMPLETE
========================================================================

```
