#!/Users/sergeishadrin/Dev/Work/audio_transcription/venv/bin/python
import typer
from app.controllers.cli import app as transcription_cli

# 1. Initialize the Main Application
# no_args_is_help=True means if you run "python main_cli.py" without args, it shows the help menu.
app = typer.Typer(
    help="Research Engine CLI: Manage media, transcriptions, and knowledge.",
    no_args_is_help=True,
    add_completion=False 
)

# 2. Register Modules
# This mounts all commands from cli.py under the "transcription" namespace.
app.add_typer(
    transcription_cli, 
    name="transcription", 
    help="Manage audio processing, text registration, and file exploration."
)

# 3. Global Callback (Optional)
# Useful for defining global flags like --version or --verbose
@app.callback()
def main(
    verbose: bool = typer.Option(False, help="Enable verbose logging."),
    version: bool = typer.Option(False, "--version", "-v", help="Show application version.")
):
    """
    The centralized Research Engine Command Line Interface.
    """
    if version:
        typer.echo("Research Engine CLI v1.0.0")
        raise typer.Exit()
    
    if verbose:
        typer.echo("Verbose mode enabled.")

# 4. Entry Point
if __name__ == "__main__":
    app()