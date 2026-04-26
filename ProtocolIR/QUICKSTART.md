# ProtocolIR Quick Start

## 1. Verify The Environment

```bash
cd ProtocolIR
python test_installation.py
```

Required for the core demo:

- Python 3.11 recommended
- pydantic
- numpy
- Opentrons SDK

Optional for data collection:

- requests/python-dotenv for protocols.io fetch scripts

## 2. Configure OpenRouter

Do not hardcode real keys in this repo. Set the key in your shell:

```powershell
$env:OPENROUTER_API_KEY="your_key_here"
$env:PROTOCOLIR_MODEL="openrouter/free"
```

Use `openrouter/free` for faster/cheaper extraction.

Then verify the live model supports strict JSON schema output:

```powershell
python check_openrouter.py
```

If the key or model is wrong, this command stops with the exact OpenRouter error.

## 3. Train Bayesian IRL Reward Posterior

```powershell
python train_reward_model.py
```

This writes the learned reward posterior mean, full samples, credible intervals,
R-hat, ESS, and dataset report.

## 4. Run The Demo

```powershell
python main.py --stress-demo -o stress_output
```

Outputs:

```text
stress_output/
  protocol.py
  audit_report.md
  summary.txt
  ir_original.json
  ir_repaired.json
```

## 5. Run Your Own Protocol

```powershell
python main.py "Prepare 8 samples. Add 10 uL DNA template to each well. Add 40 uL PCR master mix. Mix gently." -o my_output
```

Or from a file:

```powershell
python main.py my_protocol.txt -o my_output
```

## 6. Python API

```python
import protocolir as pir

parsed = pir.parse_protocol("Prepare 8 samples. Add 10 uL DNA. Add 40 uL master mix. Mix.")
grounded = pir.ground_actions(parsed)
ir = pir.build_ir(grounded)
violations = pir.verify_ir(ir)
fixed_ir, repairs, remaining = pir.repair_iteratively(ir, violations)
script = pir.compile_to_opentrons(fixed_ir)
result = pir.simulate_opentrons_script(script)

print(result.passed)
print(repairs)
```

## 7. Demo Talking Points

1. LLMs can generate runnable code that is still unsafe.
2. ProtocolIR makes the LLM produce structured JSON, not Python.
3. The typed IR is verified against physical invariants.
4. Repair is deterministic and auditable.
5. The final artifact is an Opentrons script plus a safety report.

See `../ARCHITECTURE.md` for the full system design and source-backed SOTA rationale.





