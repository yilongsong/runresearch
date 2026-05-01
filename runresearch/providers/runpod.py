import os
import subprocess
import time
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
            pass
            
        self.api_key = self.config.get("api_key")
        if self.api_key and hasattr(self, 'runpod'):
            self.runpod.api_key = self.api_key
            
        self.pods = [] # List of dicts tracking running capacity
        self.global_mounted = False

    def _get_or_create_pod(self) -> dict:
        max_jobs_per_gpu = self.config.get("max_jobs_per_gpu", 1)
        max_gpus_per_pod = self.config.get("max_gpus_per_pod", 4)
        
        # 1. Find existing pod with capacity
        for pod in self.pods:
            capacity = pod["num_gpus"] * max_jobs_per_gpu
            if len(pod["running_jobs"]) < capacity:
                return pod
                
        # 2. No capacity available, dynamically provision a new pod
        print(f"[RunPod AutoScaler] Provisioning new {max_gpus_per_pod}x GPU Pod to accommodate policy...")
        pod_res = self.runpod.create_pod(
            name=f"runresearch-fleet-{len(self.pods)+1}",
            image_name=self.config.get("image", "runpod/pytorch:2.0.1-py3.10-cuda11.8.0-devel-ubuntu22.04"),
            gpu_type_id=self.config.get("gpu_type", "NVIDIA RTX 4090"),
            cloud_type=self.config.get("cloud_type", "COMMUNITY"),
            gpu_count=max_gpus_per_pod,
            network_volume_id=self.config.get("network_volume_id"),
            docker_args="sleep infinity"
        )
        pod_id = pod_res["id"]
        
        ssh_ip, ssh_port = None, None
        while True:
            status = self.runpod.get_pod(pod_id)
            if status and status.get("desiredStatus") == "RUNNING" and status.get("runtime"):
                ports = status["runtime"].get("ports", [])
                for p in ports:
                    if p.get("privatePort") == 22:
                        ssh_ip = p.get("ip")
                        ssh_port = p.get("publicPort")
                        break
                if ssh_ip: break
            time.sleep(5)
            
        print(f"[RunPod AutoScaler] Pod {pod_id} RUNNING at {ssh_ip}:{ssh_port}")
        
        # Only mount SSHFS for the VERY FIRST pod, since they all share the identical network volume!
        if not self.global_mounted:
            print("[RunPod AutoScaler] Auto-mounting Network Volume locally for Telemetry...")
            os.makedirs("/workspace", exist_ok=True)
            subprocess.run("fusermount -u /workspace 2>/dev/null", shell=True)
            subprocess.run(
                f"sshfs root@{ssh_ip}:/workspace /workspace -p {ssh_port} -o StrictHostKeyChecking=no -o Reconnect", 
                shell=True
            )
            self.global_mounted = True
            
        setup_cmd = self.config.get("setup_commands", "")
        if setup_cmd:
            print(f"[RunPod AutoScaler] Running Setup Commands on {pod_id}...")
            subprocess.run(f"ssh -p {ssh_port} -o StrictHostKeyChecking=no root@{ssh_ip} '{setup_cmd}'", shell=True)
            
        pod_obj = {
            "id": pod_id,
            "ssh_ip": ssh_ip,
            "ssh_port": ssh_port,
            "num_gpus": max_gpus_per_pod,
            "current_gpu_idx": 0,
            "running_jobs": set()
        }
        self.pods.append(pod_obj)
        return pod_obj

    def submit(self, experiment: Experiment) -> str:
        pod = self._get_or_create_pod()
        
        gpu_to_use = pod["current_gpu_idx"]
        pod["current_gpu_idx"] = (pod["current_gpu_idx"] + 1) % pod["num_gpus"]
        
        env_str = f"CUDA_VISIBLE_DEVICES={gpu_to_use} "
        for k, v in experiment.env_vars.items():
            env_str += f"{k}={v} "
            
        log_file = f"/workspace/outputs/{experiment.name}.log"
        subprocess.run(f"ssh -p {pod['ssh_port']} -o StrictHostKeyChecking=no root@{pod['ssh_ip']} 'mkdir -p /workspace/outputs'", shell=True)
        
        cmd = f"{env_str} nohup {experiment.command} > {log_file} 2>&1 &"
        
        print(f"[RunPod AutoScaler] Dispatched {experiment.name} to Pod {pod['id']} -> GPU {gpu_to_use}")
        subprocess.run(
            f"ssh -p {pod['ssh_port']} -o StrictHostKeyChecking=no root@{pod['ssh_ip']} \"cd {experiment.working_dir} && {cmd}\"", 
            shell=True
        )
        
        job_id = f"{pod['id']}_{experiment.name}"
        pod["running_jobs"].add(job_id)
        return job_id

    def get_status(self, job_id: str) -> str:
        for pod in self.pods:
            if job_id in pod["running_jobs"]:
                return "RUNNING"
        return "UNKNOWN"

    def cancel(self, job_id: str):
        for pod in self.pods:
            if job_id in pod["running_jobs"]:
                exp_name = job_id.split("_")[1]
                kill_cmd = f"pkill -f {exp_name}"
                subprocess.run(f"ssh -p {pod['ssh_port']} -o StrictHostKeyChecking=no root@{pod['ssh_ip']} '{kill_cmd}'", shell=True)
                pod["running_jobs"].remove(job_id)
                
                # Auto-Scaler Cleanup
                if len(pod["running_jobs"]) == 0:
                    print(f"[RunPod AutoScaler] All jobs on Pod {pod['id']} finished. Terminating Pod to save money...")
                    self.runpod.terminate_pod(pod["id"])
                    self.pods.remove(pod)
                    
                    if len(self.pods) == 0:
                        subprocess.run("fusermount -u /workspace 2>/dev/null", shell=True)
                        self.global_mounted = False
                return
