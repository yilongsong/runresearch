# RunResearch

RunResearch helps you run jobs on HPCs with ease.

## Identity & Ethos
* **Lightweight & Minimalist:** Contains as few lines of code as possible.
* **Highly Hackable / Customizable:** Easily inject custom logic; easy to make work.
* **Easy to use**: Simple, elegant interface.

## Setup: The Orchestrator Environment

**CRITICAL DESIGN PATTERN:** RunResearch is an infrastructure manager, completely decoupled from your machine learning codebase. 
**Do NOT install RunResearch inside your heavy PyTorch/TensorFlow environments.** 

Instead, it is the intended design to run RunResearch in its own tiny, dedicated conda environment. Your actual ML environments will be activated dynamically via your cluster profile headers when a job actually starts.

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
