# Pipeline Results Demo

The strict product demo should be generated with:

```powershell
cd C:\Users\sreer\OneDrive\Documents\scifry-SCSP\ProtocolIR
.\.venv\Scripts\Activate.ps1
$env:OPENROUTER_API_KEY="your_openrouter_key_here"
$env:PROTOCOLIR_MODEL="openrouter/free"
python check_openrouter.py
python train_reward_model.py
python main.py --stress-demo -o stress_output
```

The current Bayesian IRL training run produced:

```text
Expert scripts: 8
Corrupted traces: 2
Generated counterfactual traces: 32
Pairwise preferences: 306
Posterior samples: 4000
HMC acceptance rate: 0.788
```

The main pipeline now requires the OpenRouter key and the real Opentrons simulator. If either fails, the command exits with an error so the result is not misrepresented.
