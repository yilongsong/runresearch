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

# 2. Install the minimal dependencies
pip install -r requirements.txt
```

## Quickstart
```bash
python -m runresearch.cli launch examples/sweep.yaml --provider local
```
