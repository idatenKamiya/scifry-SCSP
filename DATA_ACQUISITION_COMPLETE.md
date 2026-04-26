# Data Acquisition Status

The repo already contains local demo data:

- `ProtocolIR/data/protocols_io_raw/`
- `ProtocolIR/data/expert_scripts/`
- `ProtocolIR/data/corrupted_traces/`
- `ProtocolIR/models/learned_weights.json`

These files support the hackathon demo and reward-model story without requiring live downloads.

Current local training signal:

- 8 expert Opentrons scripts
- 2 hand-written corrupted traces
- 32 generated counterfactual unsafe traces
- 14 protocols.io JSON records
- 14 protocols.io step records

The generated counterfactuals are deterministic negative trajectories used for
inverse-preference learning, not claimed as real protocols.

Optional live ingestion:

- protocols.io API credentials can be configured through `PROTOCOLS_IO_*` environment variables.
- The current core demo does not require protocols.io credentials.

OpenRouter:

- Set `OPENROUTER_API_KEY` for live semantic extraction.
- Do not commit real keys.




