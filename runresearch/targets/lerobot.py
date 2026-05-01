import os
import json
import ast
from runresearch.core.targets import BaseTargetTracker, TrackerRegistry
from runresearch.core.experiment import Experiment

class LeRobotEpochTracker(BaseTargetTracker):
    name = "Epochs"

    def _get_total_frames(self, repo_path, episodes_str=None):
        if not os.path.isabs(repo_path):
            repo_path = os.path.expanduser(f"~/.cache/huggingface/lerobot/{repo_path}")
            
        info_path = os.path.join(repo_path, "meta", "info.json")
        if not os.path.exists(info_path):
            return None
            
        try:
            if not episodes_str:
                with open(info_path) as f:
                    info = json.load(f)
                return info.get("total_frames")
                
            try:
                episodes_list = ast.literal_eval(str(episodes_str))
            except Exception:
                with open(info_path) as f:
                    info = json.load(f)
                return info.get("total_frames")
                
            episodes_path = os.path.join(repo_path, "meta", "episodes.jsonl")
            if not os.path.exists(episodes_path):
                with open(info_path) as f:
                    info = json.load(f)
                return info.get("total_frames")
                
            total = 0
            with open(episodes_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line: continue
                    ep_data = json.loads(line)
                    if ep_data.get("episode_index") in episodes_list:
                        total += ep_data.get("length", 0)
            return total if total > 0 else None
        except Exception as e:
            print(f"Error calculating frames for LeRobot Tracker: {e}")
            return None

    def compute_progress(self, experiment: Experiment) -> float:
        # Dynamically extract output_dir from the bash command
        output_dir = experiment.metadata.get("output_dir")
        if not output_dir:
            cmd = experiment.command
            if "--output_dir" in cmd:
                parts = cmd.split()
                try:
                    idx = parts.index("--output_dir")
                    output_dir = parts[idx+1]
                except ValueError:
                    return 0.0
            else:
                return 0.0
        
        # Map remote /workspace to local ~/runpod_workspace
        if output_dir.startswith("/workspace"):
            output_dir = output_dir.replace("/workspace", os.path.expanduser("~/runpod_workspace"), 1)
            
        checkpoints_dir = os.path.join(output_dir, "checkpoints")
        if not os.path.exists(checkpoints_dir):
            return None
            
        highest_step = 0
        latest_ckpt_path = None
        for subdir in os.listdir(checkpoints_dir):
            if subdir.isdigit():
                step_val = int(subdir)
                if step_val > highest_step:
                    highest_step = step_val
                    latest_ckpt_path = os.path.join(checkpoints_dir, subdir)
                    
        if highest_step == 0 or latest_ckpt_path is None:
            return None
            
        cfg_path = os.path.join(latest_ckpt_path, "pretrained_model", "train_config.json")
        safe_tensor_path = os.path.join(latest_ckpt_path, "pretrained_model", "model.safetensors")
        if not os.path.exists(cfg_path) or not os.path.exists(safe_tensor_path):
            return 0.0
            
        try:
            with open(cfg_path) as f:
                cfg = json.load(f)
            batch_size = cfg.get("batch_size")
            if not batch_size: 
                return 0.0
        except Exception:
            return 0.0
            
        # Dynamically extract dataset_repo from the bash command
        dataset_repo = experiment.metadata.get("dataset_repo")
        if not dataset_repo:
            cmd = experiment.command
            if "--dataset.repo_id" in cmd:
                parts = cmd.split()
                try:
                    idx = parts.index("--dataset.repo_id")
                    dataset_repo = parts[idx+1]
                except ValueError:
                    return 0.0
            else:
                return 0.0
                
        episodes_str = experiment.metadata.get("episodes")
        if not episodes_str:
            cmd = experiment.command
            for part in cmd.split():
                if part.startswith("--dataset.episodes="):
                    episodes_str = part.split("=")[1]
                    break
        
        total_frames = self._get_total_frames(dataset_repo, episodes_str)
        if not total_frames:
            return 0.0
            
        return (highest_step * batch_size) / total_frames

TrackerRegistry.register("lerobot", LeRobotEpochTracker)
