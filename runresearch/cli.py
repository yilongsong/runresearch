import argparse
import yaml
from runresearch.core.experiment import Experiment
from runresearch.orchestrator import Orchestrator

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

    launch_parser = subparsers.add_parser("launch")
    launch_parser.add_argument("config", help="Path to yaml config")
    launch_parser.add_argument("--provider", default="local", help="Compute provider")

    monitor_parser = subparsers.add_parser("monitor")
    monitor_parser.add_argument("--provider", default="local", help="Compute provider")

    dashboard_parser = subparsers.add_parser("dashboard", help="Launch the terminal dashboard")

    args = parser.parse_args()

    if args.command == "launch":
        experiments = load_experiments(args.config)
        orch = Orchestrator(provider_name=args.provider)
        orch.load_and_register(experiments)
        orch.monitor()  # Automatically start monitoring upon launch
    elif args.command == "monitor":
        orch = Orchestrator(provider_name=args.provider)
        orch.monitor()
    elif args.command == "dashboard":
        from runresearch.tui import run_tui
        run_tui()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()

