# ProtocolIR Architecture

## Project Thesis

ProtocolIR is a verified, reward-guided compiler for autonomous lab protocols.

The winning framing is not "an LLM writes Opentrons code." The stronger and more defensible framing is:

> ProtocolIR converts messy biology protocols into a typed robot intermediate representation, enforces hard physical safety invariants, scores the trajectory with a learned reward model from expert and counterfactual traces, repairs unsafe behavior with deterministic policies, compiles the verified IR to Opentrons Python, and produces simulator-backed audit evidence.

This directly targets the SCSP Autonomous Laboratories track: automate a real scientific workflow, reduce friction for researchers, and show a credible path from natural language protocol to safe robotic execution.

## Why This Can Win

### Novelty

Most teams will build a direct LLM/RAG prototype. ProtocolIR is a compiler and verifier. The LLM is only a semantic parser; final code generation is deterministic.

### Technical Difficulty

The system has typed schemas, deck grounding, hard physical invariants, reward features, inverse preference learning, iterative repair, deterministic compilation, simulator integration, and audit reporting.

### National Impact

Safe protocol automation scales across academic labs, biotech labs, government labs, and future cloud laboratories. A verifier/audit layer is exactly the kind of infrastructure needed before agents can touch physical experiments.

### Problem-Solution Fit

Real lab protocols omit details humans infer: well maps, tip hygiene, pipette ranges, mixing, cold handling, reagent identity, and deck layout. ProtocolIR explicitly extracts ambiguities and refuses to hide them inside generated Python.

## Current SOTA Baseline

Primary-source takeaways used in this architecture:

- OpenRouter's API is OpenAI-compatible at `https://openrouter.ai/api/v1`, and OpenRouter supports strict structured outputs with `response_format.type = "json_schema"`. ProtocolIR uses this for semantic extraction while keeping final code generation deterministic.  
  Source: https://openrouter.ai/docs/api-reference/overview and https://openrouter.ai/docs/features/structured-outputs
- OpenRouter's `openrouter/free` router selects free models and filters for requested capabilities such as structured outputs. ProtocolIR still uses `require_parameters=true` and `check_openrouter.py` so a capability mismatch fails before the demo.  
  Source: https://openrouter.ai/docs/guides/routing/routers/free-models-router
- Opentrons exposes official protocol simulation through `opentrons_simulate` or `python -m opentrons.simulate`; simulation raises on execution problems and returns a run log.  
  Source: https://docs.opentrons.com/python-api/reference/execute-simulate/
- BioPlanner shows why direct LLM protocol planning is weak: LLMs struggle with multi-step planning, and scientific protocol evaluation often needs expert knowledge.  
  Source: https://aclanthology.org/2023.emnlp-main.162/
- protocols.io exposes APIs for protocol metadata, steps, and materials, making it a realistic input/evaluation corpus.  
  Source: https://apidoc.protocols.io/
- LangGraph is a good production orchestration target because it is designed for long-running, stateful workflows with durable execution and human-in-the-loop control. The hackathon implementation keeps the same node boundaries without requiring LangGraph to be installed.  
  Source: https://docs.langchain.com/oss/python/langgraph/overview

## End-to-End Pipeline

```text
Raw protocol text / protocols.io record
  -> IngestProtocol
  -> ParseToSemanticActions
  -> GroundToDeck
  -> BuildTypedIR
  -> VerifyHardConstraints
  -> ExtractRewardFeatures
  -> ScoreRewardModel
  -> NeedsRepair?
       yes -> RepairPolicy -> VerifyHardConstraints -> ScoreRewardModel
       no  -> CompileOpentrons
  -> SimulateProtocol
  -> GenerateAuditReport
```

## Multi-Agent Orchestration

ProtocolIR uses a typed, auditable agent graph rather than a single free-form
LLM agent:

| Agent | Role | Determinism |
|---|---|---|
| Semantic Parser Agent | Calls OpenRouter strict JSON schema extraction | LLM, schema-constrained |
| Grounding Agent | Maps semantic actions to deck/labware/wells | deterministic |
| IR Builder Agent | Lowers grounded actions into typed robot IR | deterministic |
| Verifier Agent | Enforces hard physical invariants | deterministic |
| Reward Agent | Scores IR with Bayesian IRL posterior mean | deterministic after training |
| Repair Agent | Applies auditable repairs and loops to verifier | deterministic |
| Compiler Agent | Compiles verified IR to Opentrons Python | deterministic |
| Simulator Agent | Runs real Opentrons simulation | deterministic runtime check |
| Audit Agent | Emits only measured pipeline evidence | deterministic |

This keeps the useful part of agent orchestration, specialized nodes with a
shared typed state and a repair loop, while preventing the LLM from writing or
modifying executable robot code.

## Layer 0: Data Ingestion

Inputs:

- pasted protocol text
- protocols.io protocol record
- optional material list
- optional deck map
- expert Opentrons scripts
- corrupted/counterfactual unsafe traces

Outputs:

```json
{
  "protocol_id": "pcr-demo-001",
  "title": "PCR plate setup",
  "raw_steps": ["Add DNA template", "Add master mix", "Mix"],
  "materials": ["DNA template", "PCR master mix"],
  "source": "protocols.io or user"
}
```

Implementation status:

- Local protocol text works now.
- Existing data folders contain protocols.io-style raw files, expert scripts, and corrupted traces.
- API fetch scripts remain optional because public demos should run without credentials.

## Layer 1: Semantic Parser

Purpose:

- convert messy protocol text into typed semantic intent
- flag ambiguity instead of hallucinating hidden lab details
- never write Python

Backend:

- OpenRouter structured outputs via `OPENROUTER_API_KEY`
- default model: `openrouter/free`
- parser failure is fatal; the run stops when OpenRouter, schema support, or the API key is wrong

Output:

```json
{
  "goal": "PCR plate setup",
  "sample_count": 8,
  "materials": [
    {"name": "DNA template", "class": "template", "volume_ul": 80},
    {"name": "PCR master mix", "class": "master_mix", "volume_ul": 320}
  ],
  "actions": [
    {
      "action_type": "transfer",
      "reagent": "DNA template",
      "volume_ul": 10,
      "source_hint": "template rack",
      "destination_hint": "PCR plate",
      "constraints": ["fresh tip for each sample"]
    }
  ],
  "ambiguities": ["Specific well map not specified"]
}
```

## Layer 2: Grounding Engine

Purpose:

- map biological concepts to robot objects
- choose deck slots
- expand "each well" into concrete well addresses
- choose source layout for 8, 12, 24, or 96 samples

Default OT-2 deck:

```json
{
  "plate": "biorad_96_wellplate_200ul_pcr, slot 1",
  "template_rack": "opentrons_24_tuberack_nest_1.5ml_snapcap, slot 2",
  "master_mix_rack": "opentrons_24_tuberack_nest_1.5ml_snapcap, slot 3",
  "tiprack_20": "opentrons_96_tiprack_20ul, slot 4",
  "tiprack_300": "opentrons_96_tiprack_300ul, slot 5",
  "template_plate": "96-well source plate, slot 6 for >24 samples"
}
```

## Layer 3: Typed IR

The IR is the central artifact. Every later layer consumes it; the LLM does not.

Example:

```json
[
  {"op": "LoadLabware", "opentrons_name": "biorad_96_wellplate_200ul_pcr", "slot": 1, "alias": "plate"},
  {"op": "LoadInstrument", "name": "p20", "opentrons_name": "p20_single_gen2", "mount": "left"},
  {"op": "PickUpTip", "pipette": "p20"},
  {"op": "Aspirate", "pipette": "p20", "volume_ul": 10, "source": "template_rack/A1", "reagent": "DNA template"},
  {"op": "Dispense", "pipette": "p20", "volume_ul": 10, "destination": "plate/A1"},
  {"op": "Mix", "pipette": "p20", "volume_ul": 8, "location": "plate/A1", "repetitions": 3},
  {"op": "DropTip", "pipette": "p20"}
]
```

## Layer 4: Hard Safety Verifier

Hard constraints cannot be overridden by the reward model:

- no aspirate, dispense, or mix without a tip
- no pipette outside min/max volume
- no tip over-capacity
- no dispense more than aspirated
- no invalid or unknown labware/well location
- no well overflow
- no cross-reagent tip contamination
- no dropping a tip containing liquid
- missing mix after plate dispense is flagged as repairable semantic risk

This is the "safety guarantee" layer. The reward model optimizes behavior; the verifier enforces invariants.

## Layer 5: Reward Model

ProtocolIR uses inverse preference reward learning:

```text
expert trajectory E preferred over corrupted trajectory C
feature_diff = phi(E) - phi(C)
learn weights w such that sigmoid(w * feature_diff) is high
```

Feature families:

- contamination violations
- pipette range violations
- well overflow
- missing tip events
- missing mix events
- complete transfer pairs
- tip changes between reagent classes
- total operations
- simulator success

For hackathon robustness, hard safety priors remain dominant and learned preferences tune softer efficiency and style terms.

## Layer 6: Repair Policy

Deterministic repairs:

| Violation | Repair |
|---|---|
| `ASPIRATE_NO_TIP` | insert `PickUpTip` |
| `DISPENSE_NO_TIP` | insert `PickUpTip` |
| `MIX_NO_TIP` | insert `PickUpTip` |
| `CROSS_CONTAMINATION` | insert `DropTip` + `PickUpTip` |
| `PIPETTE_RANGE_VIOLATION` | switch the whole transfer window to compatible pipette |
| `MISSING_MIX` | insert `Mix` after dispense |
| `WELL_OVERFLOW` | human review |
| `UNKNOWN_*` / `INVALID_*` | human review |

The loop runs:

```text
verify -> repair -> verify -> repair -> ... -> compile
```

## Layer 7: Deterministic Opentrons Compiler

The compiler emits low-level API calls:

```python
p20.pick_up_tip()
p20.aspirate(10, template_rack["A1"])
p20.dispense(10, plate["A1"])
p20.mix(3, 8, plate["A1"])
p20.drop_tip()
```

It avoids direct LLM code generation because low-level deterministic code is easier to verify and audit.

## Layer 8: Simulator Validation

Preferred:

```bash
python -m opentrons.simulate outputs/protocol.py
```

Strict requirements:

- Python syntax compilation must pass
- required Opentrons structure checks must pass
- real Opentrons simulation must pass

The simulator must be installed; simulator failure is a product failure to fix, not a pass.

## Layer 9: Audit Report

The audit report is the demo artifact judges can understand quickly:

- input goal
- extracted material/action count
- ambiguities
- violations before repair
- repairs applied
- violations after repair
- reward score before/after
- simulator status
- final verdict

## Benchmark Plan

Minimum publishable benchmark:

```text
10 PCR/qPCR protocols x 3 systems

systems:
1. direct LLM to Opentrons code
2. LLM plus simulator feedback loop
3. ProtocolIR typed IR plus verifier plus reward repair
```

Metrics:

- simulator pass rate
- hard verifier violations
- cross-contamination events
- pipette range violations
- well overflow violations
- reward score improvement
- human clarification count
- generated code length and command count

Implemented benchmark entry point:

```powershell
python compare_systems.py -o comparison_output
```

This runs a direct LLM-to-Opentrons baseline and ProtocolIR on the same input,
then emits `comparison_output/comparison_report.md`.

## Demo Script

0:00-0:30: "Runnable lab code is not safe lab behavior."

0:30-1:15: Show a messy PCR protocol and ambiguity list.

1:15-2:00: Show direct LLM baseline failure: reused tips, wrong pipette, or missing mix.

2:00-3:30: Show ProtocolIR graph, typed IR, verifier violations, and repairs.

3:30-4:30: Show generated Opentrons script and simulator/audit output.

4:30-5:00: Tie to impact: safer cloud labs and reproducible autonomous science.

## Implementation Status

Implemented now:

- OpenRouter structured-output parser adapter
- no legacy LLM SDK dependency in the core package
- strict OpenRouter parsing with fatal production errors
- deck grounding and sample expansion
- typed IR
- hard verifier
- reward model without sklearn dependency
- deterministic repair loop
- Opentrons compiler
- strict real-simulator integration
- `--skip-simulator` backup mode that writes artifacts without claiming PASS
- unsafe compilation gate: ProtocolIR refuses to compile if verifier violations remain after repair
- Bayesian IRL reward posterior with adaptive multi-chain HMC, MAP estimate,
  95% credible intervals, posterior sign probabilities, R-hat, and ESS
- typed multi-agent graph manifest for demos, UI, and presentation diagrams
- direct LLM baseline and comparison runner for evidence-backed judging
- audit report and IR artifact export

Next highest-impact upgrades:

- install Opentrons SDK in the judging/runtime environment
- add a small benchmark harness with real measured baseline numbers
- add a simple local UI to show raw protocol, IR, repair diff, generated code, and audit report
- add protocols.io API ingestion once credentials are available




