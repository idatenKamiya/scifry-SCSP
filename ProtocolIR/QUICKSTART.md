# ProtocolIR Quick Start Guide

Get up and running in 5 minutes.

## 1. Installation

```bash
cd ProtocolIR
pip install -r requirements.txt
pip install -e .
```

## 2. Configure LLM Provider

### Option A (default, recommended): Ollama on this machine

```bash
export PROTOCOLIR_LLM_PROVIDER="ollama"
export OLLAMA_BASE_URL="http://127.0.0.1:11434"
export PROTOCOLIR_MODEL="llama3.1:8b"
```

Start Ollama if needed:

```bash
ollama serve
ollama pull llama3.1:8b
```

### Option B: Anthropic

```bash
export PROTOCOLIR_LLM_PROVIDER="anthropic"
export ANTHROPIC_API_KEY="your_api_key_here"
```

Or create a `.env` file:

```bash
cp .env.example .env
# Edit .env and add your API key
```

## 3. Run the Demo

```bash
python main.py --demo
```

This will:
- Parse an example PCR protocol
- Build and verify the IR
- Auto-repair any violations
- Compile to Opentrons code
- Simulate execution
- Generate an audit report

Output goes to `./outputs/`:
- `protocol.py` — Executable Opentrons script
- `audit_report.md` — Safety analysis
- `summary.txt` — Executive summary

## 4. Test with Your Own Protocol

```bash
python main.py "Add 10 µL DNA to plate. Add 40 µL master mix. Mix." -o ./my_output
```

Or from a file:

```bash
python main.py my_protocol.txt -o ./my_output
```

## 5. Python API

```python
import protocolir as pir

# Parse
parsed = pir.parse_protocol("Add 10 µL DNA. Add 40 µL master mix.")

# Ground
grounded = pir.ground_actions(parsed)

# Build IR
ir = pir.build_ir(grounded)

# Verify & Repair
violations = pir.verify_ir(ir)
ir_repaired, repairs = pir.repair_ir(ir, violations)

# Compile
script = pir.compile_to_opentrons(ir_repaired)

# Simulate
result = pir.simulate_opentrons_script(script)

# Score
model = pir.learn_reward_heuristically()
features = pir.extract_trajectory_features(ir_repaired, [])
score = model.score_trajectory(features)

print(f"Status: {'✓ PASS' if result.passed else '✗ FAIL'}")
print(f"Reward: {score.total_score:.0f}")
```

## 6. Project Structure

```
ProtocolIR/
├── main.py                    # Entry point
├── protocolir/                # Core package
│   ├── parser.py              # Parse text → semantic actions
│   ├── grounder.py            # Map to deck positions
│   ├── ir_builder.py          # Build typed IR
│   ├── verifier.py            # Check safety constraints
│   ├── reward_model.py        # Score trajectories
│   ├── repair.py              # Auto-fix violations
│   ├── compiler.py            # Generate Opentrons code
│   ├── simulator.py           # Run simulator
│   └── audit.py               # Generate reports
├── data/
│   ├── protocols_io_raw/      # Example protocols
│   ├── expert_scripts/        # Good Opentrons examples
│   └── corrupted_traces/      # Bad examples (for learning)
└── outputs/                   # Generated artifacts
```

## 7. Troubleshooting

### "ANTHROPIC_API_KEY not found"

```bash
export PROTOCOLIR_LLM_PROVIDER="anthropic"
export ANTHROPIC_API_KEY="your_key"
```

### "Ollama is not reachable"

```bash
export PROTOCOLIR_LLM_PROVIDER="ollama"
export OLLAMA_BASE_URL="http://127.0.0.1:11434"
ollama serve
```

### "Opentrons simulator not found"

The simulator is optional. ProtocolIR will do basic validation instead:

```python
result = pir.simulate_opentrons_script(script)
# Returns SimulationResult with .passed = True/False
```

### "Pydantic validation error"

Make sure you're using Python 3.9+:

```bash
python --version
```

## 8. Next Steps

- Read [README.md](README.md) for full documentation
- Check [demo/](demo/) for example inputs and outputs
- Explore the [data/](data/) directory for sample protocols
- Run tests: `pytest tests/`

## 9. Hackathon Tips

**For the 5-minute demo:**

1. Show raw messy protocol text
2. Run it through ProtocolIR
3. Show the baseline LLM output (has violations)
4. Show ProtocolIR output (violations fixed)
5. Run simulator, show it passes
6. Display audit report with improvements

**Key metrics to highlight:**

- Violations found and fixed
- Reward score improvement
- Simulator pass rate
- Repairs applied

**Example demo script:**

```bash
# Terminal 1: Show input
cat data/protocols_io_raw/example_pcr_protocol.txt

# Terminal 2: Run pipeline
python main.py data/protocols_io_raw/example_pcr_protocol.txt -o demo_output

# Terminal 3: Show output
cat demo_output/summary.txt
cat demo_output/audit_report.md
cat demo_output/protocol.py
```

---

**Questions?** Contact hack@scsp.ai
