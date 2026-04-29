import os
import subprocess
from typing import Dict, Any
from runresearch.core.experiment import Experiment
from runresearch.providers.base import BaseProvider

class SlurmProvider(BaseProvider):
    def __init__(self, profile_config: Dict[str, Any] = None):
        super().__init__(profile_config)
        self.sbatch_dir = os.path.abspath(".runresearch/sbatch_scripts")
        os.makedirs(self.sbatch_dir, exist_ok=True)

    def submit(self, experiment: Experiment) -> str:
        sbatch_file = os.path.join(self.sbatch_dir, f"{experiment.name}.sbatch")
        
        # 1. Start with the template headers from the user's config
        headers = self.config.get("headers", [
            "#SBATCH --partition=gpu",
            "#SBATCH --time=24:00:00"
        ])
        
        script_lines = ["#!/bin/bash"]
        script_lines.extend(headers)
        
        # 2. Inject job name & log output paths
        script_lines.append(f"#SBATCH --job-name={experiment.name}")
        
        # 3. Setup environment and working directory
        script_lines.append(f"cd {os.path.abspath(experiment.working_dir)}")
        for k, v in experiment.env_vars.items():
            script_lines.append(f"export {k}={v}")
            
        # 4. Inject the actual command
        script_lines.append(experiment.command)
        
        script_content = "\n".join(script_lines) + "\n"
        
        with open(sbatch_file, "w") as f:
            f.write(script_content)
            
        print(f"[SlurmProvider] Submitting {sbatch_file} to SLURM")
        
        try:
            result = subprocess.run(["sbatch", sbatch_file], capture_output=True, text=True, check=True)
            # Typical output: "Submitted batch job 123456"
            job_id = result.stdout.strip().split()[-1]
            return job_id
        except subprocess.CalledProcessError as e:
            print(f"[SlurmProvider] Failed to submit job: {e.stderr}")
            return "FAILED"

    def get_status(self, job_id: str) -> str:
        if not job_id or job_id == "FAILED":
            return "UNKNOWN"
            
        try:
            # Poll squeue for the specific job ID
            result = subprocess.run(
                ["squeue", "-j", job_id, "-h", "-o", "%T"], 
                capture_output=True, text=True, check=True
            )
            state = result.stdout.strip()
            
            if not state:
                # If SLURM removes it from squeue, it finished (success/fail/timeout)
                # The Orchestrator daemon will check the exit codes/logs next.
                return "UNKNOWN"
                
            # Map SLURM states to Generic States
            if state in ["PENDING", "CONFIGURING"]:
                return "PENDING"
            elif state in ["RUNNING", "COMPLETING"]:
                return "RUNNING"
            elif state == "COMPLETED":
                return "COMPLETED"
            elif state in ["TIMEOUT", "PREEMPTED"]:
                return "TIMEOUT"
            elif state in ["FAILED", "OUT_OF_MEMORY"]:
                return "FAILED"
            elif state == "CANCELLED":
                return "CANCELLED"
            else:
                return "UNKNOWN"
                
        except subprocess.CalledProcessError:
            # squeue errors if the job ID is totally invalid or long expired
            return "UNKNOWN"

    def cancel(self, job_id: str):
        print(f"[SlurmProvider] Cancelling job {job_id}")
        try:
            subprocess.run(["scancel", job_id], check=True)
        except subprocess.CalledProcessError as e:
            print(f"[SlurmProvider] Failed to cancel job {job_id}: {e.stderr}")

