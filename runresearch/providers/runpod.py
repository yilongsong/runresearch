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
            raise ImportError("The runpod python package is not installed. Please run: pip install runpod")
            
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
                
        # 2. No capacity available, dynamically calculate exactly what we need
        import json
        import math
        needed_gpus = max_gpus_per_pod
        try:
            with open("runresearch_state.json", "r") as f:
                state = json.load(f)
            
            pending_active_jobs = 0
            for exp_name, data in state.get("experiments", {}).items():
                if data.get("config", {}).get("status") == "active" and data.get("status") == "PENDING":
                    pending_active_jobs += 1
                    
            needed_gpus_raw = math.ceil(pending_active_jobs / max_jobs_per_gpu)
            needed_gpus = min(needed_gpus_raw, max_gpus_per_pod)
            if needed_gpus < 1: needed_gpus = 1
        except Exception:
            pass

        pod_res = None
        while needed_gpus >= 1:
            print(f"[RunPod AutoScaler] Provisioning new {needed_gpus}x GPU Pod to exactly fit demand...")
            try:
                env_dict = {}
                pub_key_path = os.path.expanduser("~/.ssh/id_rsa.pub")
                if not os.path.exists(pub_key_path): pub_key_path = os.path.expanduser("~/.ssh/id_ed25519.pub")
                if os.path.exists(pub_key_path):
                    with open(pub_key_path, "r") as f:
                        env_dict["PUBLIC_KEY"] = f.read().strip()
                
                pod_res = self.runpod.create_pod(
                    name=f"runresearch-fleet-{len(self.pods)+1}",
                    image_name=self.config.get("image", "runpod/pytorch:2.0.1-py3.10-cuda11.8.0-devel-ubuntu22.04"),
                    gpu_type_id=self.config.get("gpu_type", "NVIDIA RTX 4090"),
                    cloud_type=self.config.get("cloud_type", "COMMUNITY"),
                    gpu_count=needed_gpus,
                    network_volume_id=self.config.get("network_volume_id"),
                    volume_mount_path="/workspace",
                    ports="22/tcp",
                    env=env_dict
                )
                break
            except Exception as e:
                error_msg = str(e)
                if "QueryError" in error_msg or "No GPU found" in error_msg or "no longer any instances available" in error_msg:
                    print(f"[RunPod AutoScaler] RunPod is out of inventory for {needed_gpus}x pods. Decreasing requested GPUs to {needed_gpus - 1}...")
                    needed_gpus -= 1
                else:
                    raise e
                    
        if pod_res is None or needed_gpus < 1:
            raise RuntimeError("RunPod is completely out of inventory for all GPU sizes. Please try again later.")
            
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
            
        print(f"[RunPod AutoScaler] Pod {pod_id} API reports RUNNING. Waiting for SSH daemon to spin up...")
        
        # Wait for SSH to be fully ready
        ssh_ready = False
        for _ in range(30):
            res = subprocess.run(
                f"ssh -p {ssh_port} -o StrictHostKeyChecking=no -o PasswordAuthentication=no -o BatchMode=yes -o ConnectTimeout=5 root@{ssh_ip} 'echo ready'", 
                shell=True, capture_output=True
            )
            if res.returncode == 0:
                ssh_ready = True
                break
            time.sleep(5)
            
        if not ssh_ready:
            raise Exception(f"Failed to securely authenticate with Pod {pod_id} over SSH after 2.5 minutes.")
            
        print(f"[RunPod AutoScaler] Pod {pod_id} SSH is fully connected at {ssh_ip}:{ssh_port}")
        time.sleep(10) # Give RunPod's TCP proxy a few seconds to stabilize
        
        # Only mount SSHFS for the VERY FIRST pod, since they all share the identical network volume!
        if not self.global_mounted:
            print("[RunPod AutoScaler] Auto-mounting Network Volume locally for Telemetry...")
            local_mount = os.path.expanduser("~/runpod_workspace")
            subprocess.run(f"fusermount -uz {local_mount} 2>/dev/null", shell=True)
            try:
                os.makedirs(local_mount, exist_ok=True)
            except Exception:
                pass
            subprocess.run(
                f"sshfs root@{ssh_ip}:/workspace {local_mount} -p {ssh_port} -o StrictHostKeyChecking=no -o PasswordAuthentication=no -o BatchMode=yes -o reconnect", 
                shell=True
            )
            self.global_mounted = True
            
        pod_obj = {
            "id": pod_id,
            "ssh_ip": ssh_ip,
            "ssh_port": ssh_port,
            "num_gpus": needed_gpus,
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
        cmd = f"{env_str} nohup {experiment.command} > {log_file} 2>&1 < /dev/null &"
        
        setup_cmd = self.config.get("setup_commands", "")
        if setup_cmd:
            full_dispatch_cmd = f"nohup bash -c '{setup_cmd} && mkdir -p /workspace/outputs && cd {experiment.working_dir} && {cmd}' > /dev/null 2>&1 < /dev/null &"
        else:
            full_dispatch_cmd = f"nohup bash -c 'mkdir -p /workspace/outputs && cd {experiment.working_dir} && {cmd}' > /dev/null 2>&1 < /dev/null &"
        
        print(f"[RunPod AutoScaler] Dispatched {experiment.name} to Pod {pod['id']} -> GPU {gpu_to_use}")
        
        for i in range(5):
            res = subprocess.run(
                f"ssh -p {pod['ssh_port']} -o StrictHostKeyChecking=no -o PasswordAuthentication=no -o BatchMode=yes -o ConnectTimeout=5 root@{pod['ssh_ip']} \"{full_dispatch_cmd}\"", 
                shell=True, capture_output=True, text=True
            )
            if res.returncode == 0: break
            if i == 4:
                print(f"[RunPod AutoScaler] ERROR: Failed to dispatch {experiment.name}!\\nSTDOUT: {res.stdout}\\nSTDERR: {res.stderr}")
            time.sleep(3)
            
        time.sleep(3)
        
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
                        local_mount = os.path.expanduser("~/runpod_workspace")
                        subprocess.run(f"fusermount -u {local_mount} 2>/dev/null", shell=True)
                        self.global_mounted = False
                return
