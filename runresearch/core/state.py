import os
import json
from enum import Enum

class JobStatus(Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"
    UNKNOWN = "UNKNOWN"

class StateManager:
    def __init__(self, db_path="runresearch_state.json"):
        self.db_path = db_path
        self._load()

    def _load(self):
        if os.path.exists(self.db_path):
            with open(self.db_path, "r") as f:
                self.state = json.load(f)
        else:
            self.state = {"jobs": {}}

    def _save(self):
        with open(self.db_path, "w") as f:
            json.dump(self.state, f, indent=2)

    def update_job(self, job_id: str, status: JobStatus, details: dict = None):
        if job_id not in self.state["jobs"]:
            self.state["jobs"][job_id] = {}
        self.state["jobs"][job_id]["status"] = status.value
        if details:
            self.state["jobs"][job_id].update(details)
        self._save()

    def get_job_status(self, job_id: str) -> str:
        return self.state["jobs"].get(job_id, {}).get("status", JobStatus.UNKNOWN.value)
