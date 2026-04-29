import subprocess
from runresearch.core.experiment import Experiment
from runresearch.providers.base import BaseProvider

class SlurmProvider(BaseProvider):
    def submit(self, experiment: Experiment) -> str:
        # Construct sbatch script
        sbatch_script = f"""#!/bin/bash
#SBATCH --job-name={experiment.name}
#SBATCH --gpus={experiment.num_gpus}
cd {experiment.working_dir}
{experiment.command}
"""
        # Typically we'd save this to a tmp file and run `sbatch tmp.sh`
        print("[SlurmProvider] Mock submitting to SLURM")
        return "slurm_job_001"

    def get_status(self, job_id: str) -> str:
        # Would parse `squeue -j {job_id}`
        return "RUNNING"

    def cancel(self, job_id: str):
        # Would run `scancel {job_id}`
        print(f"[SlurmProvider] Mock scancel {job_id}")
