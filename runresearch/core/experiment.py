from dataclasses import dataclass, field
from typing import Dict, Optional, Any

@dataclass
class Experiment:
    name: str
    command: str
    resume_command: Optional[str] = None
    working_dir: str = "."
    env_vars: Dict[str, str] = field(default_factory=dict)
    resources: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Target Scheme Additions
    status: str = "active" # active, inactive, finished
    tracker: str = "none" # e.g. 'lerobot'
    target: float = 0.0
    current_progress: float = 0.0

    def to_dict(self):
        return {
            "name": self.name,
            "command": self.command,
            "resume_command": self.resume_command,
            "working_dir": self.working_dir,
            "env_vars": self.env_vars,
            "resources": self.resources,
            "metadata": self.metadata,
            "status": self.status,
            "tracker": self.tracker,
            "target": self.target,
            "current_progress": self.current_progress
        }
