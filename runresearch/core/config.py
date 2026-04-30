import os
import yaml
from pathlib import Path
from typing import Dict, Any

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "runresearch"

def load_profile(provider_name: str, profile_name: str = "default") -> Dict[str, Any]:
    """
    Loads a provider-specific profile configuration.
    E.g., ~/.config/runresearch/profiles/slurm/msi.yaml
    """
    profile_path = DEFAULT_CONFIG_DIR / "profiles" / provider_name / f"{profile_name}.yaml"
    
    if not profile_path.exists():
        return {}
        
    with open(profile_path, "r") as f:
        return yaml.safe_load(f) or {}

def init_config_dir():
    """Initializes the configuration directory structure for the user."""
    profiles_dir = DEFAULT_CONFIG_DIR / "profiles"
    os.makedirs(profiles_dir / "slurm", exist_ok=True)
    os.makedirs(profiles_dir / "runpod", exist_ok=True)
    
    # Create a template slurm profile if it doesn't exist
    template_path = profiles_dir / "slurm" / "template.yaml"
    if not template_path.exists():
        with open(template_path, "w") as f:
            f.write("# SLURM Profile Configuration\n")
            f.write("# Use this to define cluster-specific headers\n")
            f.write("headers:\n")
            f.write("  - \"#SBATCH --partition=gpu\"\n")
            f.write("  - \"#SBATCH --time=24:00:00\"\n")
            f.write("  - \"#SBATCH --mem=64G\"\n")
            f.write("  - \"#SBATCH --gres=gpu:1\"\n")

    # Create a template runpod profile if it doesn't exist
    runpod_template_path = profiles_dir / "runpod" / "template.yaml"
    if not runpod_template_path.exists():
        with open(runpod_template_path, "w") as f:
            f.write("# RunPod Profile Configuration\n")
            f.write("api_key: \"YOUR_RUNPOD_API_KEY_HERE\"\n")
            f.write("network_volume_id: \"YOUR_VOLUME_ID_HERE\"\n")
            f.write("gpu_type: \"NVIDIA RTX A5000\"\n")
            f.write("image: \"runpod/pytorch:2.0.1-py3.10-cuda11.8.0-devel-ubuntu22.04\"\n")
            f.write("cloud_type: \"COMMUNITY\" # or SECURE\n")
