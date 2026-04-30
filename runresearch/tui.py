from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, DataTable
from runresearch.core.state import StateManager

class DashboardApp(App):
    """A Textual app to monitor RunResearch jobs."""
    
    # Define keyboard shortcuts for the bottom footer
    BINDINGS = [
        ("q", "quit", "Quit Dashboard"),
        ("p", "toggle_pause", "Pause/Resume Orchestrator")
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
        self.col_exp, self.col_id, self.col_status = table.add_columns("Experiment Name", "Current Job ID", "Status")
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
            
            # Inject some rich text colors based on status
            if status == "RUNNING":
                status = f"[bold green]{status}[/bold green]"
            elif status in ["FAILED", "TIMEOUT"]:
                status = f"[bold red]{status}[/bold red]"
            elif status == "COMPLETED":
                status = f"[bold blue]{status}[/bold blue]"
            elif status == "PENDING":
                status = f"[bold yellow]{status}[/bold yellow]"
                
            if exp_name not in self.added_rows:
                table.add_row(exp_name, str(job_id), status, key=exp_name)
                self.added_rows.add(exp_name)
            else:
                # Update existing cells to preserve cursor position and prevent flickering
                table.update_cell(exp_name, self.col_id, str(job_id))
                table.update_cell(exp_name, self.col_status, status)
            
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

def run_tui():
    app = DashboardApp()
    app.run()

if __name__ == "__main__":
    run_tui()
