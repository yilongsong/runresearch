# RunResearch

RunResearch helps you run and manage jobs on HPCs with ease.

## Setup

RunResearch should be installed in a dedicated lightweight conda environment. Your ML environments will be dynamically activated via your cluster profile headers when a job actually starts.

```bash
# 1. Create a dedicated, lightweight environment for the orchestrator
conda create -n runresearch python=3.10
conda activate runresearch

# 2. Install RunResearch globally within this environment
pip install -e .

# 3. Initialize your configuration directories (~/.config/runresearch)
runresearch init
```

## Quickstart
Once installed, you can launch jobs from any directory on your machine as long as the `runresearch` conda environment is active.

```bash
# Launch an experiment sweep using your specific cluster profile (e.g. msi)
runresearch launch examples/sweep.yaml --provider slurm --profile msi

# Launch the interactive terminal dashboard to monitor progress
runresearch dashboard
```
