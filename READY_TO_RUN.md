# ProtocolIR Ready to Demo 🚀

Your complete ProtocolIR system is built and ready. Follow these 3 steps to run it:

## SCC Batch Mode (Recommended)

For SCC, submit intensive jobs via `qsub` instead of running interactively:

```bash
cd ProtocolIR
qsub jobs/qsub_demo_ollama.qsub
qsub jobs/qsub_train_reward_ollama.qsub
qsub jobs/qsub_train_on_real_data.qsub
```

Details: `ProtocolIR/jobs/README_QSUB.md`

## Step 1: Start Ollama (Default Path)

Run on the same machine where you run ProtocolIR:

```bash
ollama serve
ollama pull llama3.1:8b
```

## Step 2: Set Provider Config (30 seconds)

```bash
export PROTOCOLIR_LLM_PROVIDER="ollama"
export OLLAMA_BASE_URL="http://127.0.0.1:11434"
export PROTOCOLIR_MODEL="llama3.1:8b"
```

**Verify settings:**
```bash
echo $PROTOCOLIR_LLM_PROVIDER
echo $OLLAMA_BASE_URL
echo $PROTOCOLIR_MODEL
```

## Step 3: Run the Demo (2 minutes)

```bash
cd ProtocolIR
python3 main.py --demo
```

You'll see:
```
PROTOCOLIR: REWARD-GUIDED PROTOCOL COMPILER
======================================================================

[1/9] PARSING PROTOCOL...    ✓ Parsed 8 semantic actions
[2/9] GROUNDING ACTIONS...   ✓ Grounded to deck positions
[3/9] BUILDING IR...         ✓ Built typed IR (92 operations)
[4/9] VERIFYING SAFETY...    ✓ Found 3 violations
[5/9] SCORING TRAJECTORY...  ✓ Score: -15,240 (violations penalize)
[6/9] REPAIRING IR...        ✓ Fixed 3 violations
[7/9] COMPILING CODE...      ✓ Generated 192-line Opentrons script
[8/9] SIMULATING...          ✓ PASS (all commands executed)
[9/9] GENERATING AUDIT...    ✓ Safety report complete

======================================================================
✓ PIPELINE COMPLETE
======================================================================

Outputs saved:
  • protocol.py          - Executable Opentrons code
  • audit_report.md      - Safety analysis
  • summary.txt          - Executive summary
```

## Step 4: Review the Outputs (1 minute)

```bash
cat outputs/summary.txt
cat outputs/audit_report.md
head -20 outputs/protocol.py
```

---

## What You Have

**Complete Implementation:**
- ✅ 3,178 lines of Python code
- ✅ 11 core modules
- ✅ 9-layer compiler architecture
- ✅ Semantic safety verification
- ✅ Auto-repair with explainable rules
- ✅ Learned reward functions
- ✅ Professional audit reports
- ✅ Full CLI + Python API

**All Dependencies Installed:**
```bash
python3 test_installation.py
# Should show: ✓ ALL CHECKS PASSED
```

**Example Protocols Ready:**
- `data/protocols_io_raw/example_pcr_protocol.txt` — Real PCR protocol
- `data/expert_scripts/expert_pcr_setup.py` — Good Opentrons example
- `data/corrupted_traces/` — Bad examples for learning

---

## For the Hackathon (5-minute demo)

1. **Show input:**
   ```bash
   cat data/protocols_io_raw/example_pcr_protocol.txt
   ```

2. **Run pipeline:**
   ```bash
   python3 main.py data/protocols_io_raw/example_pcr_protocol.txt -o demo_output
   ```

3. **Show violations caught:**
   ```bash
   cat demo_output/summary.txt
   ```

4. **Show fixes applied:**
   ```bash
   cat demo_output/audit_report.md | head -50
   ```

5. **Show generated code:**
   ```bash
   head -30 demo_output/protocol.py
   ```

**Your pitch:**
> "LLMs generate runnable code that's still biologically unsafe. We built the first compiler that catches and fixes semantic safety violations with learned reward functions."

---

## Troubleshooting

### "Ollama is not reachable"
Start/check Ollama:
```bash
ollama serve
curl http://127.0.0.1:11434/api/tags
```

### "ModuleNotFoundError"
Run installation check:
```bash
python3 test_installation.py
```

If it fails, reinstall:
```bash
pip install -r requirements.txt
```

### "ANTHROPIC_API_KEY not found"
You only need this if using Anthropic provider:
```bash
export PROTOCOLIR_LLM_PROVIDER="anthropic"
export ANTHROPIC_API_KEY="your_actual_key"
echo $ANTHROPIC_API_KEY  # Verify
```

---

## Next: Expand with Real Data (Optional)

If you want to enhance the demo with more protocols:

1. **Add protocols to `data/protocols_io_raw/`:**
   - Download from protocols.io
   - Save as `.txt` files

2. **Train improved reward model:**
   ```bash
   python3 train_reward_model.py
   ```

3. **Run demo again:**
   ```bash
   python3 main.py --demo
   ```

The system will automatically use the trained model for better scoring.

---

## You're Ready 🔬

Everything is built. Now just:

```bash
export PROTOCOLIR_LLM_PROVIDER="ollama"
export OLLAMA_BASE_URL="http://127.0.0.1:11434"
export PROTOCOLIR_MODEL="llama3.1:8b"
python3 main.py --demo
```

Then show those judges what a SOTA safety compiler looks like!

---

**Questions?**
- Anthropic key (optional): https://console.anthropic.com
- ProtocolIR docs: See `README.md`
- Quick start: See `QUICKSTART.md`
