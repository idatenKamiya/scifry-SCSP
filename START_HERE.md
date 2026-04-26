# Start Here

ProtocolIR is a strict OpenRouter-powered, Bayesian reward-guided compiler for safe autonomous lab protocols.

## Product

The end product is not a chatbot. It is a compiler pipeline that turns protocol text into verified Opentrons Python plus an audit report.

## Run It

```powershell
cd C:\Users\sreer\OneDrive\Documents\scifry-SCSP\ProtocolIR
.\.venv\Scripts\Activate.ps1
python test_installation.py
$env:OPENROUTER_API_KEY="your_openrouter_key_here"
$env:PROTOCOLIR_MODEL="openrouter/free"
python check_openrouter.py
python train_reward_model.py
python main.py --stress-demo -o stress_output
```

The demo writes:

```text
ProtocolIR/stress_output/
  protocol.py
  audit_report.md
  summary.txt
  ir_original.json
  ir_repaired.json
```

## What To Show Judges

1. Raw messy protocol text.
2. OpenRouter semantic parse and ambiguity list.
3. Bayesian IRL posterior report with credible intervals and diagnostics.
4. Typed IR before repair.
5. Verifier violations before repair.
6. Deterministic repairs and zero remaining violations.
7. Generated Opentrons Python.
8. Real Opentrons simulator PASS and audit report.

Read `ARCHITECTURE.md` for the refined architecture and source-backed rationale.
