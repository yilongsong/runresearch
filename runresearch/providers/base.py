from abc import ABC, abstractmethod
from typing import Dict, Any
from runresearch.core.experiment import Experiment

class BaseProvider(ABC):
    def __init__(self, profile_config: Dict[str, Any] = None):
        """
        Initialize the provider with a specific profile configuration.
        """
        self.config = profile_config or {}

    @abstractmethod
    def submit(self, experiment: Experiment) -> str:
        """Submits an experiment and returns a job_id."""
        pass

    @abstractmethod
    def get_status(self, job_id: str) -> str:
        """Returns the current status of the job."""
        pass

    @abstractmethod
    def cancel(self, job_id: str):
        """Cancels a running job."""
        pass

    def sync_up(self, experiment: Experiment) -> bool:
        """
        Hook to sync data to the compute environment before submission.
        Returns True if successful or not needed (e.g., shared filesystem).
        """
        return True

    def sync_down(self, experiment: Experiment, job_id: str) -> bool:
        """
        Hook to retrieve data from the compute environment after completion.
        Returns True if successful or not needed.
        """
        return True
