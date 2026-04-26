# ProtocolIR vs Direct LLM Comparison

| Metric | Direct LLM Baseline | ProtocolIR |
|---|---:|---:|
| Command exit code | 1 | 1 |
| Real simulator pass | False | False |
| Static/built-in safety issues | 1 | N/A |
| Violations before repair | N/A | N/A |
| Violations after repair | N/A | N/A |
| Repairs applied | N/A | N/A |
| Commands | 0 | N/A |

## Interpretation

- Direct LLM baseline is allowed to write Opentrons Python directly.
- ProtocolIR constrains the LLM to semantic JSON, then verifies and repairs typed IR before compilation.
- Static baseline issues are conservative code-level checks, not a replacement for ProtocolIR typed-IR verification.

## Baseline stderr/stdout tail

```text
# Direct LLM Baseline Report

- Generated script bytes: 1795
- Simulator status: FAIL
- Real simulator used: True
- Simulator commands: 0
- Static safety issues: 1

## Static Safety Issue Counts

| Issue | Count |
|---|---:|
| PIPETTE_RANGE_VIOLATION | 1 |

## First Static Issues

- PIPETTE_RANGE_VIOLATION at line 44: p300 attempts 3 uL outside expected range.

## Simulator Errors

- /usr4/cs585/skandan/.opentrons/robot_settings.json not found. Loading defaults
- Deck calibration not found.
- /usr4/cs585/skandan/.opentrons/deck_calibration.json not found. Loading defaults
- Traceback (most recent call last):
-   File "/projectnb/se740/scifry-SCSP/ProtocolIR/.venv/lib64/python3.12/site-packages/opentrons/protocols/execution/execute_python.py", line 159, in exec_run
-     exec("run(__context)", new_globs)
-   File "<string>", line 1, in <module>
-   File "/scratch/tmpuw2js5_k.py", line 12, in run
-     plate = ctx.load_labware('bio-rad-96-well-pcr-plate', '1', '96-well PCR plate')
-             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

## Machine Summary

```json
{
  "simulator_passed": false,
  "real_simulator_used": true,
  "command_count": 0,
  "static_issue_count": 1,
  "static_issue_counts": {
    "PIPETTE_RANGE_VIOLATION": 1
  },
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
  Goal: Prepare 12 qPCR reactions in a 96-well optical plate
  Parser backend: openrouter
  Samples: 96
  Materials: 3
  Semantic actions: 4
  Ambiguities / reviews flagged: 4

[2/9] Grounding semantic actions to deck/labware/wells...
  Grounded actions: 4

[3/9] Building typed IR...
  IR operations: 1736

[4/9] Verifying hard physical constraints...
  Found: 0 total (0 critical, 0 warning)

[5/9] Scoring trajectory before repair...
  Reward before repair: 367143

[6/9] Repairing policy violations with typed IR repair loop...
  No repairs needed.
  Reward after repair: 367143

[7/9] Compiling verified IR to Opentrons Python...
  Generated script bytes: 50928

[8/9] Simulating generated protocol with the real Opentrons simulator...
  Status: FAIL (real Opentrons simulator)
  Commands: 0
Traceback (most recent call last):
  File "/projectnb/se740/scifry-SCSP/ProtocolIR/main.py", line 227, in <module>
    main()
  File "/projectnb/se740/scifry-SCSP/ProtocolIR/main.py", line 89, in main
    process_protocol(protocol_text, source_url=args.url, output_dir=args.output)
  File "/projectnb/se740/scifry-SCSP/ProtocolIR/main.py", line 33, in process_protocol
    pipeline = run_protocol_graph(
               ^^^^^^^^^^^^^^^^^^^
  File "/projectnb/se740/scifry-SCSP/ProtocolIR/protocolir/orchestration.py", line 163, in run_protocol_graph
    raise RuntimeError("; ".join(sim.errors or ["Simulation failed and PRE found no typed patch"]))
RuntimeError: /usr4/cs585/skandan/.opentrons/robot_settings.json not found. Loading defaults; Deck calibration not found.; /usr4/cs585/skandan/.opentrons/deck_calibration.json not found. Loading defaults; OutOfTipsError [line 499]: 

```
