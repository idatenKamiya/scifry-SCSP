# ProtocolIR

ProtocolIR is a safety-first compiler for autonomous wet-lab protocols. It converts natural-language lab instructions into verified Opentrons Python by forcing the LLM to produce structured intent, then passing that intent through a typed intermediate representation, deterministic hard-safety verification, Bayesian reward scoring, repair, simulation, and audit reporting.

The core research claim is simple: simulator-passing robot code is not enough. ProtocolIR verifies lab semantics before code generation, then uses the Opentrons simulator only as the final execution check.

## Final Demo Evidence

- Direct LLM baseline: asks an LLM to write Opentrons Python directly, then simulates it.
- ProtocolIR: OpenRouter JSON parse -> RAG context -> typed IR -> verifier -> repair -> compiler -> Opentrons simulator -> audit.
- Stress demo: injects unsafe IR errors and repairs them from verifier evidence.
- Bayesian IRL: trains a MAP + Laplace reward posterior from expert Opentrons scripts and counterfactual unsafe traces.

## Repository Layout

```text
ProtocolIR/
  protocolir/              Core compiler, verifier, repair, reward, and simulator modules
  data/                    Expert protocols and protocol text used for reward learning/RAG
  models/                  Learned reward weights and posterior report
  benchmarks/              Benchmark cases and ablation runners
  app_protocolir.py        Streamlit judge-facing UI
  cloud_app/app.py         Streamlit Community Cloud entrypoint
  main.py                  Main CLI pipeline
  run_judge_demo.py        One-command judge demo runner
  compare_systems.py       Direct-LLM baseline vs ProtocolIR comparison
  train_reward_model.py    Bayesian IRL reward training
LICENSE
```

## Live Demo

- Streamlit app: `https://scifry-scspgit-cusv4klr3xnmzoy7hyjhpc.streamlit.app/`
- Cloud app path: `ProtocolIR/cloud_app/app.py`
- Secrets needed in Streamlit Cloud settings:
  - `OPENROUTER_API_KEY`
  - `PROTOCOLIR_MODEL` (optional override)
- Full simulator-backed fallback run (local/SCC):
  - `python run_judge_demo.py -o judge_demo_output`

## Run The Final Demo

Full commands are in [ProtocolIR/README.md](ProtocolIR/README.md). The short path is:

```powershell
cd ProtocolIR
python test_installation.py
python check_openrouter.py
python train_reward_model.py
python main.py --demo -o outputs_demo
python main.py --stress-demo -o stress_output
python compare_systems.py --demo -o comparison_output
python main.py --cell-culture-demo -o cell_culture_output
streamlit run app_protocolir.py
```

Set `OPENROUTER_API_KEY` and `PROTOCOLIR_MODEL` before running live LLM steps. Do not commit API keys.
