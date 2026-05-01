from typing import Dict, Type
import importlib
from runresearch.core.experiment import Experiment

class BaseTargetTracker:
    name: str = "Progress"
    
    def compute_progress(self, experiment: Experiment) -> float:
        raise NotImplementedError("Subclasses must implement compute_progress")
        
    def is_reached(self, experiment: Experiment) -> bool:
        if experiment.target <= 0:
            return False
        prog = self.compute_progress(experiment)
        if prog is None:
            return False
        return prog >= experiment.target

class TrackerRegistry:
    _trackers: Dict[str, Type[BaseTargetTracker]] = {}
    
    @classmethod
    def register(cls, name: str, tracker_class: Type[BaseTargetTracker]):
        cls._trackers[name] = tracker_class
        
    @classmethod
    def get(cls, name: str) -> BaseTargetTracker:
        if name not in cls._trackers:
            # Auto-load plugin from runresearch.targets dynamically
            try:
                importlib.import_module(f"runresearch.targets.{name}")
            except ImportError:
                return None
                
        tracker_cls = cls._trackers.get(name)
        return tracker_cls() if tracker_cls else None

# Default generic tracker
class NoneTracker(BaseTargetTracker):
    name = "None"
    def compute_progress(self, experiment: Experiment) -> float:
        return 0.0

TrackerRegistry.register("none", NoneTracker)
