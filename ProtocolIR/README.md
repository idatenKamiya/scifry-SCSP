# ProtocolIR

ProtocolIR is a verified compiler for autonomous lab protocols. It does not let an LLM write final robot code directly. The LLM only extracts structured semantic intent; ProtocolIR then grounds the protocol, builds a typed robot IR, verifies hard physical invariants, scores the trajectory with a learned Bayesian reward model, repairs unsafe IR, compiles verified IR to Opentrons Python, runs the real Opentrons simulator, and writes an audit report.

## Why This Beats Direct LLM Codegen

Most lab-code agents follow:

```text
protocol text -> LLM -> Opentrons Python -> simulator loop
```

ProtocolIR follows:

```text
protocol text
  -> OpenRouter structured JSON parser + local RAG
  -> semantic grounding
  -> typed IR
  -> hard verifier
  -> Bayesian IRL reward scoring
  -> typed repair loop
  -> deterministic Opentrons compiler
  -> real Opentrons simulator
  -> audit certificate
```

The differentiator is verify-then-generate. The simulator is a final check, not the first safety mechanism.

## Fresh Setup

Use Python 3.11 on Windows. Python 3.14 can break scientific packages and Opentrons wheels.

```powershell
cd "C:\Users\sreer\OneDrive\Documents\scifry-SCSP\ProtocolIR"

Remove-Item -Recurse -Force .venv -ErrorAction SilentlyContinue
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Set OpenRouter for live parsing:

```powershell
$env:OPENROUTER_API_KEY="YOUR_OPENROUTER_KEY"
$env:PROTOCOLIR_MODEL="inclusionai/ling-2.6-flash:free"
```

Never commit `.env` files or pasted API keys.

## Final Demo Commands

Run these in order:

```powershell
python test_installation.py
python check_openrouter.py
python train_reward_model.py
python main.py --demo -o outputs_demo
python main.py --stress-demo -o stress_output
python compare_systems.py --demo -o comparison_output
python main.py --cell-culture-demo -o cell_culture_output
streamlit run app_protocolir.py
```

Or run a judge-ready bundle in one command:

```powershell
python run_judge_demo.py -o judge_demo_output
```

This writes:
- `judge_demo_output/outputs_demo/` (pipeline outputs)
- `judge_demo_output/comparison_output/` (baseline vs ProtocolIR report)
- `judge_demo_output/JUDGE_DEMO_SUMMARY.md` (single-file run summary)

Expected judge-facing evidence:

- `check_openrouter.py`: `OPENROUTER OK`
- `train_reward_model.py`: `Inference method: MAP + Laplace`, `Diagnostic status: PASS`
- `outputs_demo/audit_report.md`: clean protocol, 0 verifier violations, real simulator PASS
- `stress_output/audit_report.md`: unsafe IR errors repaired to 0 remaining violations
- `comparison_output/comparison_report.md`: direct LLM baseline fails while ProtocolIR passes
- `outputs_demo/safety_certificate.json`: machine-readable SAFE/UNSAFE verdict
- Streamlit app: one-screen view of protocol, safety audit, reward posterior, and generated code

## Bayesian IRL

ProtocolIR uses a monotonic safety-constrained Bayesian preference model. The default inference method is MAP estimation with a Gaussian Laplace posterior approximation from the stabilized Hessian at the MAP. This is intentionally reported as Laplace inference, not MCMC.

Training writes:

```text
models/learned_weights.json
models/reward_posterior_samples.json
models/reward_posterior_report.md
DATASET_REPORT.md
```

The posterior report includes MAP weights, posterior means, 95% credible intervals, and sign probabilities for reward features.

## Core Modules

```text
protocolir/
  llm.py                 OpenRouter structured-output adapter
  rag.py                 Local retrieval context for parser prompts
  parser.py              Natural-language protocol -> structured semantic JSON
  biosecurity.py         Material/sequence review hooks
  grounder.py            Labware, deck, and well grounding
  ir_builder.py          Typed robot IR construction
  verifier.py            Hard physical and semantic safety checks
  features.py            Trajectory feature extraction
  bayesian_irl.py        MAP + Laplace Bayesian IRL
  reward_model.py        Reward scoring from learned weights
  repair.py              Deterministic typed-IR repair policy
  precise_repair.py      Targeted IR patch utilities
  compiler.py            Verified IR -> Opentrons Python
  simulator.py           Real Opentrons simulator integration
  contamination_graph.py Contamination-flow graph for audits
  audit.py               Markdown safety certificate
  orchestration.py       Typed graph executor for the full pipeline
```

## Safety Checks

The verifier catches failures that a runtime-only simulator loop can miss or catch too late:

- aspirate, dispense, or mix without a tip
- pipette volume/range violations
- tip over-capacity
- well overflow
- unknown or invalid labware locations
- cross-contamination across reagents
- dropping tips with liquid still in the tip
- missing mix after plate dispense

## Demo Script

Tell judges:

1. Direct LLM code generation is the baseline. It can fail before producing simulator-valid robot behavior.
2. ProtocolIR constrains the LLM to structured intent and never trusts it with final Python.
3. Hard verifier catches unsafe typed IR before compilation.
4. Repair is deterministic and auditable, not another black-box LLM rewrite.
5. Bayesian IRL gives a learned reward with uncertainty, used to score the before/after safety improvement.
6. The final generated Python passes the real Opentrons simulator and comes with an audit certificate.
