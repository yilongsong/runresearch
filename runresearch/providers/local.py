import subprocess
import uuid
import time
from typing import Dict, Any
from runresearch.core.experiment import Experiment
from runresearch.providers.base import BaseProvider

class LocalProvider(BaseProvider):
    def __init__(self, profile_config: Dict[str, Any] = None):
        super().__init__(profile_config)
        self.processes = {}

    def submit(self, experiment: Experiment) -> str:
        job_id = str(uuid.uuid4())[:8]
        print(f"[LocalProvider] Submitting {experiment.name} (Job: {job_id})")
        
        # In a real implementation, you'd handle stdout/stderr and env vars.
        proc = subprocess.Popen(
            experiment.command, 
            shell=True, 
            cwd=experiment.working_dir
        )
        self.processes[job_id] = proc
        return job_id

    def get_status(self, job_id: str) -> str:
        if job_id not in self.processes:
            return "UNKNOWN"
        
        proc = self.processes[job_id]
        ret = proc.poll()
        if ret is None:
            return "RUNNING"
        elif ret == 0:
            return "COMPLETED"
        else:
            return "FAILED"

    def cancel(self, job_id: str):
        if job_id in self.processes:
            self.processes[job_id].terminate()
            print(f"[LocalProvider] Terminated {job_id}")
