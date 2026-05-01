import os
import json
from enum import Enum
from typing import Dict, Any

class JobStatus(Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"
    UNKNOWN = "UNKNOWN"
    PAUSED = "PAUSED"

class StateManager:
    def __init__(self, db_path="runresearch_state.json"):
        self.db_path = db_path
        self._load()

    def _load(self):
        if os.path.exists(self.db_path):
            with open(self.db_path, "r") as f:
                self.state = json.load(f)
        else:
            self.state = {"global_pause": False, "experiments": {}}

    def _save(self):
        with open(self.db_path, "w") as f:
            json.dump(self.state, f, indent=2)

    def register_experiment(self, exp_name: str, exp_dict: Dict[str, Any]):
        """Registers a new experiment if it doesn't exist."""
        if exp_name not in self.state["experiments"]:
            self.state["experiments"][exp_name] = {
                "config": exp_dict,
                "current_job_id": None,
                "status": JobStatus.PENDING.value,
                "history": []
            }
            self._save()
        else:
            # Update the config but preserve state
            self.state["experiments"][exp_name]["config"] = exp_dict
            self._save()

    def update_job(self, exp_name: str, job_id: str, status: JobStatus):
        if exp_name in self.state["experiments"]:
            old_job_id = self.state["experiments"][exp_name].get("current_job_id")
            if job_id and job_id != old_job_id:
                import time
                self.state["experiments"][exp_name]["start_time"] = time.time()
                
            self.state["experiments"][exp_name]["current_job_id"] = job_id
            self.state["experiments"][exp_name]["status"] = status.value
            self._save()
            
    def update_config_meta(self, exp_name: str, key: str, value: Any):
        if exp_name in self.state["experiments"]:
            self.state["experiments"][exp_name]["config"][key] = value
            self._save()

    def set_pause(self, paused: bool):
        self.state["global_pause"] = paused
        self._save()

    def get_experiments(self):
        return self.state["experiments"]

    def is_paused(self) -> bool:
        return self.state.get("global_pause", False)
