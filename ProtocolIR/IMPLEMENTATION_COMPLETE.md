# ProtocolIR Implementation Complete

This repo has been recoded around the refined ProtocolIR architecture:

- OpenRouter strict structured-output parsing (`OPENROUTER_API_KEY`, `PROTOCOLIR_MODEL`)
- fail-fast production parser and simulator path
- typed Pydantic contracts across every layer
- OT-2 deck grounding with sample-to-well expansion
- low-level robot IR
- hard physical verifier
- Bayesian IRL reward posterior with adaptive multi-chain HMC
- posterior report with MAP, means, credible intervals, R-hat, ESS, and acceptance rate
- deterministic repair loop
- deterministic Opentrons compiler
- real Opentrons simulator integration
- audit report, summary, and IR JSON artifact export

Run:

```powershell
python test_installation.py
$env:OPENROUTER_API_KEY="your_openrouter_key_here"
$env:PROTOCOLIR_MODEL="openrouter/free"
python check_openrouter.py
python train_reward_model.py
python main.py --stress-demo -o stress_output
```

Primary architecture file:

```text
../ARCHITECTURE.md
```

Security note: keep real API keys in environment variables only. Do not commit them.
