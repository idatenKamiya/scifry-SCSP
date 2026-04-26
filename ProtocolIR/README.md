# ProtocolIR

ProtocolIR is a reward-guided compiler for safe autonomous lab protocols.

The core claim: runnable robot code is not the same thing as safe lab behavior. ProtocolIR uses an LLM only for structured semantic extraction, then routes the result through a typed IR, hard verifier, learned reward model, deterministic repair policy, Opentrons compiler, simulator check, and audit report.

## Why It Is Different

Baseline lab copilots often do:

```text
protocol text -> LLM -> Opentrons Python
```

ProtocolIR does:

```text
protocol text
  -> OpenRouter structured semantic parser
  -> deck grounding
  -> typed robot IR
  -> hard physical verifier
  -> reward model
  -> deterministic repair loop
  -> Opentrons Python compiler
  -> real Opentrons simulator validation
  -> audit report
```

The LLM never writes final Python. It extracts structured intent; compiler and verifier logic own execution.

## Quick Start

```bash
cd ProtocolIR
python -m pip install -r requirements.txt
python test_installation.py
$env:OPENROUTER_API_KEY="your_key_here"
$env:PROTOCOLIR_MODEL="openrouter/free"
python check_openrouter.py
python train_reward_model.py
python main.py --stress-demo -o stress_output
python compare_systems.py -o comparison_output
```

If `python` is not configured on your machine, use the Python executable from your environment manager.

## OpenRouter Setup

ProtocolIR reads OpenRouter configuration from environment variables:

```bash
$env:OPENROUTER_API_KEY="your_key_here"
$env:PROTOCOLIR_MODEL="openrouter/free"
```

Do not hardcode API keys in the repo. If `OPENROUTER_API_KEY` is not set, the parser fails loudly.
OpenRouter structured output support is required. If the selected model rejects
`response_format=json_schema`, choose a free OpenRouter model that supports
structured outputs and rerun `python check_openrouter.py`.

## Bayesian IRL Reward Training

Run this before the main pipeline:

```bash
python train_reward_model.py
```

This writes:

```text
models/learned_weights.json
models/reward_posterior_samples.json
models/reward_posterior_report.md
DATASET_REPORT.md
```

The report includes posterior means, MAP estimates, 95% credible intervals,
posterior sign probabilities, R-hat, ESS, and HMC acceptance rate.

## Baseline Comparison

Run the direct LLM baseline and ProtocolIR on the same protocol:

```powershell
python compare_systems.py -o comparison_output
```

This writes:

```text
comparison_output/
  comparison_report.md
  direct_llm/baseline_protocol.py
  direct_llm/baseline_report.md
  protocolir/protocol.py
  protocolir/audit_report.md
```

The baseline is intentionally allowed to generate Opentrons Python directly.
ProtocolIR is constrained to semantic parsing, typed IR verification, repair,
and deterministic compilation.

## Outputs

Running the demo writes:

```text
stress_output/
  protocol.py
  audit_report.md
  summary.txt
  ir_original.json
  ir_repaired.json
```

## Core Modules

```text
protocolir/
  llm.py          OpenRouter structured-output adapter
  parser.py       semantic extraction
  grounder.py     deck, labware, and well mapping
  ir_builder.py   typed robot IR builder
  verifier.py     hard safety constraints
  features.py     reward feature extraction
  bayesian_irl.py adaptive multi-chain HMC posterior fitting
  reward_model.py inverse preference reward model
  repair.py       deterministic repair policy
  compiler.py     Opentrons Python compiler
  simulator.py    Opentrons simulator integration
  audit.py        safety report generation
  orchestration.py typed agent graph manifest
  code_safety.py  static analyzer for direct-LLM baseline code
```

## Safety Checks

The verifier catches issues that can be missed by "does this Python run?" simulation:

- aspirating, dispensing, or mixing without a tip
- pipette range violations
- tip over-capacity
- well overflow
- unknown or invalid labware locations
- cross-contamination across reagents
- dropping tips with liquid still in the tip
- missing mix after plate dispense

## Hackathon Demo Flow

1. Show a messy PCR protocol.
2. Show semantic ambiguities and typed IR.
3. Show verifier violations before repair.
4. Show deterministic repairs.
5. Show reward improvement.
6. Show generated Opentrons Python and audit report.

See [ARCHITECTURE.md](../ARCHITECTURE.md) for the refined technical architecture and judging-rubric mapping.





