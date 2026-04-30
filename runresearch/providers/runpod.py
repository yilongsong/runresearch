import os
from typing import Dict, Any
from runresearch.core.experiment import Experiment
from runresearch.providers.base import BaseProvider

class RunPodProvider(BaseProvider):
    def __init__(self, profile_config: Dict[str, Any] = None):
        super().__init__(profile_config)
        try:
            import runpod
            self.runpod = runpod
        except ImportError:
            raise ImportError("Please install the runpod SDK: pip install runpod")
            
        self.api_key = self.config.get("api_key")
        if self.api_key:
            self.runpod.api_key = self.api_key

    def submit(self, experiment: Experiment) -> str:
        if not self.api_key:
            raise ValueError("RunPod API key missing in profile config.")
            
        # Get pod specs from profile
        gpu_type = self.config.get("gpu_type", "NVIDIA RTX A5000")
        image = self.config.get("image", "runpod/pytorch:2.0.1-py3.10-cuda11.8.0-devel-ubuntu22.04")
        volume_id = self.config.get("network_volume_id")
        cloud_type = self.config.get("cloud_type", "COMMUNITY") # SECURE or COMMUNITY
        
        # When using Network Volumes, it is normally mounted at /workspace
        # We wrap the command to redirect logs to the network volume so we don't lose them when the pod is destroyed!
        safe_cmd = (
            f"cd {experiment.working_dir} && "
            f"{experiment.command} "
            f"> /workspace/{experiment.name}.log 2>&1"
        )
        
        print(f"[RunPodProvider] Spinning up {gpu_type} pod for {experiment.name}...")
        
        try:
            pod = self.runpod.create_pod(
                name=f"runresearch-{experiment.name}",
                image_name=image,
                gpu_type_id=gpu_type,
                cloud_type=cloud_type,
                gpu_count=experiment.resources.get("gpus", 1),
                network_volume_id=volume_id,
                # This makes the container run our script and then EXIT.
                docker_args=f"bash -c \"{safe_cmd}\""
            )
            return pod["id"]
        except Exception as e:
            print(f"[RunPodProvider] Failed to create pod: {e}")
            return "FAILED"

    def get_status(self, job_id: str) -> str:
        if not job_id or job_id == "FAILED":
            return "UNKNOWN"
            
        try:
            pod = self.runpod.get_pod(job_id)
            if not pod:
                return "UNKNOWN"
            
            status = pod.get("desiredStatus", "UNKNOWN")
            
            if status == "RUNNING":
                return "RUNNING"
            elif status == "EXITED":
                # CRITICAL: RunPod charges for EXITED pods until they are terminated!
                # We must instantly terminate the pod to save the user money.
                # (Logs and checkpoints are safe because they were written to the Network Volume)
                print(f"[RunPodProvider] Pod {job_id} exited. Terminating to save money...")
                self.runpod.terminate_pod(job_id)
                
                # We can't cleanly get exit codes via the basic API easily without reading the logs,
                # so we assume COMPLETED for now. 
                return "COMPLETED" 
            else:
                return "PENDING"
                
        except Exception:
            return "UNKNOWN"

    def cancel(self, job_id: str):
        print(f"[RunPodProvider] Force terminating pod {job_id}")
        try:
            self.runpod.terminate_pod(job_id)
        except Exception as e:
            print(f"[RunPodProvider] Failed to terminate {job_id}: {e}")
