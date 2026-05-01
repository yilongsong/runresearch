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
        self.log_files = {}
        # Get total GPUs from config (default to 4 for Giant Pods)
        self.num_gpus = self.config.get("num_gpus", 4)
        self.current_gpu_idx = 0

    def submit(self, experiment: Experiment) -> str:
        job_id = str(uuid.uuid4())[:8]
        
        gpu_to_use = self.current_gpu_idx
        self.current_gpu_idx = (self.current_gpu_idx + 1) % self.num_gpus
        
        os.makedirs("logs", exist_ok=True)
        log_path = os.path.abspath(f"logs/{experiment.name}_{job_id}.log")
        f = open(log_path, "w")
        
        print(f"[LocalProvider] Submitting {experiment.name} (Job: {job_id}) on GPU {gpu_to_use}. Logs: {log_path}")
        
        env = os.environ.copy()
        env["CUDA_VISIBLE_DEVICES"] = str(gpu_to_use)
        if experiment.env_vars:
            env.update(experiment.env_vars)

        proc = subprocess.Popen(
            experiment.command, 
            shell=True, 
            cwd=experiment.working_dir,
            env=env,
            stdout=f,
            stderr=subprocess.STDOUT
        )
        self.processes[job_id] = proc
        self.log_files[job_id] = f
        return job_id

    def get_status(self, job_id: str) -> str:
        if job_id not in self.processes:
            return "UNKNOWN"
        
        proc = self.processes[job_id]
        ret = proc.poll()
        
        if ret is not None:
            if job_id in self.log_files:
                self.log_files[job_id].close()
                del self.log_files[job_id]
                
            if ret == 0:
                return "COMPLETED"
            else:
                return "FAILED"
                
        return "RUNNING"

    def cancel(self, job_id: str):
        if job_id in self.processes:
            self.processes[job_id].terminate()
            print(f"[LocalProvider] Terminated {job_id}")
