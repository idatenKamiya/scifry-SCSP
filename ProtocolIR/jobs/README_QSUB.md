# ProtocolIR QSUB Jobs (SCC)

Use these scripts for intensive operations on SCC instead of interactive shells.

All jobs are designed to keep caches and artifacts inside this project folder.

## Prerequisites

1. You are in the project directory:
   - `cd /projectnb/se740/scifry-SCSP/ProtocolIR`
2. Required modules are available:
   - `module load python3/3.12.4 uv/0.7.3`
3. Optional local Ollama binary exists for local-inference jobs:
   - `.tools/ollama/bin/ollama`

## Submit Jobs

From `ProtocolIR/`:

```bash
qsub jobs/qsub_demo_ollama.qsub
qsub jobs/qsub_train_reward_ollama.qsub
qsub jobs/qsub_train_on_real_data.qsub
```

## Logs

Job logs are written to:

- `logs/qsub/<job_name>.<job_id>.log`

## Useful Commands

```bash
qstat -u "$USER"
qdel <job_id>
```

## Notes

- The Ollama-based jobs start and stop a local Ollama server within the job.
- Model/cache paths are project-local (`.ollama/`, `.uv-cache/`).
- If your queue requires different resources, edit the `#$ -l ...` and `#$ -pe ...` lines in each script.
