import time
from runresearch.core.state import StateManager, JobStatus
from runresearch.providers.local import LocalProvider
from runresearch.providers.slurm import SlurmProvider

class Orchestrator:
    def __init__(self, provider_name="local"):
        self.state_manager = StateManager()
        if provider_name == "slurm":
            self.provider = SlurmProvider()
        else:
            self.provider = LocalProvider()

    def launch(self, experiments):
        for exp in experiments:
            job_id = self.provider.submit(exp)
            self.state_manager.update_job(job_id, JobStatus.RUNNING, details={"name": exp.name})
            print(f"Launched {exp.name} with Job ID {job_id}")

    def monitor(self):
        print("Starting orchestrator monitoring loop...")
        while True:
            # Poll status of running jobs
            for job_id, job_info in self.state_manager.state.get("jobs", {}).items():
                if job_info["status"] == JobStatus.RUNNING.value:
                    status = self.provider.get_status(job_id)
                    if status != JobStatus.RUNNING.value:
                        self.state_manager.update_job(job_id, JobStatus(status))
                        print(f"Job {job_id} changed status to {status}")
                        
                        # Self-healing could happen here
                        if status == JobStatus.FAILED.value:
                            print(f"Self-healing: would resume {job_id}")
            time.sleep(5)
