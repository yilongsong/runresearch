import time
from runresearch.core.state import StateManager, JobStatus
from runresearch.core.experiment import Experiment
from runresearch.core.config import load_profile
from runresearch.providers.local import LocalProvider
from runresearch.providers.slurm import SlurmProvider

class Orchestrator:
    def __init__(self, provider_name="local", profile_name="default"):
        self.state_manager = StateManager()
        
        profile_config = load_profile(provider_name, profile_name)
        
        if provider_name == "slurm":
            self.provider = SlurmProvider(profile_config)
        elif provider_name == "runpod":
            from runresearch.providers.runpod import RunPodProvider
            self.provider = RunPodProvider(profile_config)
        else:
            self.provider = LocalProvider(profile_config)

    def load_and_register(self, experiments):
        """Loads experiments into the state manager."""
        for exp in experiments:
            self.state_manager.register_experiment(exp.name, exp.to_dict())

    def monitor(self):
        print("Starting RunResearch Orchestrator Loop...")
        while True:
            # 1. Reload state from disk every tick to catch manual IDE edits or Pause commands
            self.state_manager._load() 
            
            if self.state_manager.is_paused():
                print("Orchestrator is globally paused. Waiting...")
                time.sleep(10)
                continue

            experiments_state = self.state_manager.get_experiments()

            for exp_name, state_data in experiments_state.items():
                status_str = state_data.get("status")
                job_id = state_data.get("current_job_id")
                exp_config = state_data.get("config", {})
                
                # Reconstruct the pure Experiment object
                exp = Experiment(
                    name=exp_config.get("name"),
                    command=exp_config.get("command"),
                    resume_command=exp_config.get("resume_command"),
                    working_dir=exp_config.get("working_dir", "."),
                    env_vars=exp_config.get("env_vars", {}),
                    resources=exp_config.get("resources", {}),
                    metadata=exp_config.get("metadata", {}),
                    status=exp_config.get("status", "active"),
                    tracker=exp_config.get("tracker", "none"),
                    target=exp_config.get("target", 0.0),
                    current_progress=exp_config.get("current_progress", 0.0)
                )
                
                cluster_status_str = state_data.get("status")

                # Check for inactive / finished kills
                if exp.status in ["inactive", "finished"]:
                    if job_id and cluster_status_str in [JobStatus.RUNNING.value, JobStatus.PENDING.value]:
                        print(f"[{exp_name}] Config State is {exp.status}. Terminating active cluster job {job_id}...")
                        self.provider.cancel(job_id)
                        self.provider.sync_down(exp, job_id)
                        self.state_manager.update_job(exp_name, None, JobStatus.COMPLETED)
                    continue

                # Tracker Evaluation
                from runresearch.core.targets import TrackerRegistry
                tracker = TrackerRegistry.get(exp.tracker)
                if tracker:
                    progress = tracker.compute_progress(exp)
                    if progress is not None:
                        self.state_manager.update_config_meta(exp_name, "current_progress", progress)
                        
                    if tracker.is_reached(exp):
                        print(f"[{exp_name}] Target reached! Terminating...")
                        if job_id and cluster_status_str in [JobStatus.RUNNING.value, JobStatus.PENDING.value]:
                            self.provider.cancel(job_id)
                            self.provider.sync_down(exp, job_id)
                        self.state_manager.update_job(exp_name, None, JobStatus.COMPLETED)
                        self.state_manager.update_config_meta(exp_name, "status", "finished")
                        continue

                # Case A: Fresh Job that needs to be submitted
                if cluster_status_str == JobStatus.PENDING.value and not job_id:
                    if exp.current_progress > 0 and exp.resume_command:
                        print(f"[{exp_name}] Checkpoint exists (progress {exp.current_progress} > 0). Using resume_command for fresh submission.")
                        exp.command = exp.resume_command
                        
                    print(f"[{exp_name}] Found PENDING job. Initiating sync and submission...")
                    self.provider.sync_up(exp)
                    new_job_id = self.provider.submit(exp)
                    if new_job_id != "FAILED":
                        self.state_manager.update_job(exp_name, new_job_id, JobStatus.RUNNING)
                    continue

                # Case B: Active Job that needs to be polled
                if cluster_status_str in [JobStatus.RUNNING.value, JobStatus.PENDING.value] and job_id:
                    current_cluster_status = self.provider.get_status(job_id)
                    
                    if current_cluster_status != cluster_status_str:
                        print(f"[{exp_name}] Job {job_id} changed status: {cluster_status_str} -> {current_cluster_status}")
                        
                        # 1. Job Finished Cleanly
                        if current_cluster_status == JobStatus.COMPLETED.value:
                            self.provider.sync_down(exp, job_id)
                            self.state_manager.update_job(exp_name, job_id, JobStatus.COMPLETED)
                            
                        # 2. Timeout/Preemption Detected (AUTO-RESUMPTION)
                        elif current_cluster_status == JobStatus.TIMEOUT.value:
                            print(f"[{exp_name}] TIMEOUT OR PREEMPTION DETECTED. Checking for resume_command...")
                            self.provider.sync_down(exp, job_id)
                            
                            if exp.resume_command:
                                print(f"[{exp_name}] Auto-resuming via resume_command!")
                                # Magically swap the original command for the resume command
                                exp.command = exp.resume_command 
                                new_job_id = self.provider.submit(exp)
                                self.state_manager.update_job(exp_name, new_job_id, JobStatus.RUNNING)
                            else:
                                print(f"[{exp_name}] No resume_command provided. Marking as permanently TIMEOUT.")
                                self.state_manager.update_job(exp_name, job_id, JobStatus.TIMEOUT)
                                
                        # 3. Crash/Failure Detected (Requires Manual Intervention)
                        elif current_cluster_status == JobStatus.FAILED.value:
                            print(f"[{exp_name}] ERROR DETECTED: Job failed. Skipping auto-resume so you can check logs.")
                            self.provider.sync_down(exp, job_id)
                            self.state_manager.update_job(exp_name, job_id, JobStatus.FAILED)
                        
                        else:
                            self.state_manager.update_job(exp_name, job_id, JobStatus(current_cluster_status))

            # Sleep lightly to avoid hammering the cluster's squeue API
            time.sleep(15)

