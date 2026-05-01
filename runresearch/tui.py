from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, DataTable
from runresearch.core.state import StateManager

class DashboardApp(App):
    """A Textual app to monitor RunResearch jobs."""
    
    # Define keyboard shortcuts for the bottom footer
    BINDINGS = [
        ("q", "quit", "Quit Dashboard"),
        ("p", "toggle_pause", "Pause/Resume Orchestrator"),
        ("a", "toggle_active", "Toggle Active/Inactive"),
        ("r", "restart_job", "Restart Job (Clear ID)")
    ]

    def __init__(self):
        super().__init__()
        self.state_manager = StateManager()

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header()
        yield DataTable(id="jobs_table")
        yield Footer()

    def on_mount(self) -> None:
        """Called when the app starts."""
        table = self.query_one(DataTable)
        table.cursor_type = "row"
        table.zebra_stripes = True
        # Define the columns and store their keys for updating later
        self.col_exp, self.col_active, self.col_id, self.col_status, self.col_prog = table.add_columns("Experiment", "Active", "Job ID", "Status", "Progress")
        self.added_rows = set()
        
        self.update_table()
        # Automatically refresh the table every 2 seconds
        self.set_interval(2.0, self.update_table)

    def update_table(self) -> None:
        """Update the data table with the latest state from the Orchestrator."""
        self.state_manager._load() # Reload to get the absolute latest state
        
        table = self.query_one(DataTable)
        
        experiments = self.state_manager.get_experiments()
        # Sort to ensure consistent ordering when adding new rows
        for exp_name, data in sorted(experiments.items()):
            job_id = data.get("current_job_id") or "None"
            status = data.get("status", "UNKNOWN")
            
            config = data.get("config", {})
            active_str = "[bold green]YES[/bold green]" if config.get("status", "active") == "active" else "[dim]NO[/dim]"
            
            prog = config.get("current_progress", 0.0)
            target = config.get("target", 1000)
            prog_str = f"{prog:.1f} / {target}"
            
            import time
            start_time = data.get("start_time")
            elapsed_str = ""
            if status in ["RUNNING", "UNKNOWN"] and start_time:
                seconds = time.time() - start_time
                if seconds < 60:
                    elapsed_str = f" ({int(seconds)}s)"
                elif seconds < 3600:
                    elapsed_str = f" ({int(seconds//60)}m)"
                else:
                    h = int(seconds//3600)
                    m = int((seconds%3600)//60)
                    elapsed_str = f" ({h}h {m}m)"
                    
            # Inject some rich text colors based on status
            if status == "RUNNING":
                status = f"[bold green]{status}{elapsed_str}[/bold green]"
            elif status == "UNKNOWN":
                status = f"[dim]{status}{elapsed_str}[/dim]"
            elif status in ["FAILED", "TIMEOUT"]:
                status = f"[bold red]{status}[/bold red]"
            elif status == "COMPLETED":
                status = f"[bold blue]{status}[/bold blue]"
            elif status == "PENDING":
                status = f"[bold yellow]{status}[/bold yellow]"
                
            if exp_name not in self.added_rows:
                table.add_row(exp_name, active_str, str(job_id), status, prog_str, key=exp_name)
                self.added_rows.add(exp_name)
            else:
                # Update existing cells to preserve cursor position and prevent flickering
                table.update_cell(exp_name, self.col_active, active_str)
                table.update_cell(exp_name, self.col_id, str(job_id))
                table.update_cell(exp_name, self.col_status, status)
                table.update_cell(exp_name, self.col_prog, prog_str)
            
        # Update the header title based on the pause state
        if self.state_manager.is_paused():
            self.title = "RunResearch Dashboard ⚠️ [PAUSED]"
        else:
            self.title = "RunResearch Dashboard 🚀 [ACTIVE]"

    def action_toggle_pause(self) -> None:
        """An action to toggle the global orchestrator pause state."""
        self.state_manager._load()
        current_pause = self.state_manager.is_paused()
        self.state_manager.set_pause(not current_pause)
        self.update_table()
        
    def action_toggle_active(self) -> None:
        table = self.query_one(DataTable)
        try:
            row_key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key
            exp_name = row_key.value
        except Exception:
            return
            
        self.state_manager._load()
        experiments = self.state_manager.get_experiments()
        if exp_name in experiments:
            config = experiments[exp_name].get("config", {})
            current = config.get("status", "active")
            new_status = "inactive" if current == "active" else "active"
            
            # Update state DB instantly
            self.state_manager.update_config_meta(exp_name, "status", new_status)
            
            # Persist to experiments.yaml so it stays across reboots
            try:
                import yaml
                with open("experiments.yaml", "r") as f:
                    data = yaml.safe_load(f)
                for exp in data.get("experiments", []):
                    if exp["name"] == exp_name:
                        exp["status"] = new_status
                with open("experiments.yaml", "w") as f:
                    yaml.dump(data, f, default_flow_style=False, sort_keys=False)
            except Exception as e:
                pass
                
            self.update_table()

    def action_restart_job(self) -> None:
        table = self.query_one(DataTable)
        try:
            row_key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key
            exp_name = row_key.value
        except Exception:
            return
            
        self.state_manager._load()
        experiments = self.state_manager.get_experiments()
        if exp_name in experiments:
            # First set config status to active to ensure it actually runs
            self.state_manager.update_config_meta(exp_name, "status", "active")
            
            # Wipe job ID and set to PENDING
            self.state_manager.update_job(exp_name, None, __import__("runresearch.core.state", fromlist=["JobStatus"]).JobStatus.PENDING)
            
            # Wipe start_time
            if "start_time" in self.state_manager.state["experiments"][exp_name]:
                del self.state_manager.state["experiments"][exp_name]["start_time"]
                self.state_manager._save()
                
            self.update_table()

def run_tui():
    app = DashboardApp()
    app.run()

if __name__ == "__main__":
    run_tui()
