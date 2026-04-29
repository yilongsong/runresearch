import argparse
import yaml
from runresearch.core.experiment import Experiment
from runresearch.orchestrator import Orchestrator
from runresearch.core.config import init_config_dir

def load_experiments(yaml_path):
    with open(yaml_path, 'r') as f:
        data = yaml.safe_load(f)
        
    experiments = []
    for exp_data in data.get("experiments", []):
        experiments.append(Experiment(**exp_data))
    return experiments

def main():
    parser = argparse.ArgumentParser(description="RunResearch Orchestrator")
    subparsers = parser.add_subparsers(dest="command")

    init_parser = subparsers.add_parser("init", help="Initialize configuration directory")

    launch_parser = subparsers.add_parser("launch")
    launch_parser.add_argument("config", help="Path to yaml config")
    launch_parser.add_argument("--provider", default="local", help="Compute provider")
    launch_parser.add_argument("--profile", default="default", help="Provider profile (e.g., msi)")

    monitor_parser = subparsers.add_parser("monitor")
    monitor_parser.add_argument("--provider", default="local", help="Compute provider")
    monitor_parser.add_argument("--profile", default="default", help="Provider profile")

    dashboard_parser = subparsers.add_parser("dashboard", help="Launch the terminal dashboard")

    args = parser.parse_args()

    if args.command == "init":
        init_config_dir()
        print("Initialized ~/.config/runresearch/")
    elif args.command == "launch":
        experiments = load_experiments(args.config)
        orch = Orchestrator(provider_name=args.provider, profile_name=args.profile)
        orch.load_and_register(experiments)
        orch.monitor()
    elif args.command == "monitor":
        orch = Orchestrator(provider_name=args.provider, profile_name=args.profile)
        orch.monitor()
    elif args.command == "dashboard":
        from runresearch.tui import run_tui
        run_tui()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()

