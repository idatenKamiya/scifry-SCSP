# Ready To Run

ProtocolIR is ready for the strict OpenRouter + Bayesian IRL demo path.

```powershell
cd C:\Users\sreer\OneDrive\Documents\scifry-SCSP\ProtocolIR
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python test_installation.py
$env:OPENROUTER_API_KEY="your_openrouter_key_here"
$env:PROTOCOLIR_MODEL="openrouter/free"
python check_openrouter.py
python train_reward_model.py
python main.py --stress-demo -o stress_output
```

Expected outcome:

- installation test passes with Opentrons installed
- OpenRouter returns strict JSON-schema semantic extraction
- Bayesian IRL writes posterior samples, learned weights, and uncertainty report
- stress demo shows verifier violations before repair and zero after repair
- real Opentrons simulator passes
- final artifacts are in `ProtocolIR/stress_output`
