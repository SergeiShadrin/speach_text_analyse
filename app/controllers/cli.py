import typer
import questionary
from typing import Optional
from datetime import datetime
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from pathlib import Path

from app.models.transcriber.transcriber_services import TranscriptionService
from app.core.engine_client import ResearchEngineClient
from app.core.config import settings

# 1. Create a "Sub-App" for this module
app = typer.Typer(help="Manage audio transcriptions.")
console = Console()

# =========================================================
#  COMMAND 1: Register Existing Texts
# =========================================================
@app.command("enregistrate_texts_already_transcribed")
def enregistrate_transcriptions(
    folder: Path = typer.Argument(..., help="Path to input folder", exists=True),
    project: str = typer.Option("Default", help="Project name to tag files with"), 
    event: str = typer.Option(None, "--event", "-e", help="Name of the event (e.g. 'Board Meeting')"),
    event_date: datetime = typer.Option(None, "--date", help="Date of the event (YYYY-MM-DD)")
):
    """
    Registrate all text files in the present folder as transcriptions in the DB.
    """
    service = TranscriptionService()
    
    console.rule(f"[bold blue]🚀 Starting enregistration[/]")
    console.print(f"📂 Folder: {folder}")
    console.print(f"🏷️  Project: {project}")
    if event: console.print(f"📅 Event:   {event} ({event_date})")

    service.save_to_db_existing_transcriptions(
        directory=folder, 
        description=project,
        event=event,      
        event_date=event_date  
    )
    
    console.print("[bold green]✅ Processing complete.[/]")


# =========================================================
#  COMMAND 2: Process Audio/Video
# =========================================================
@app.command("process")
def process_folder(
    folder: Path = typer.Argument(None, help="Path to input folder", exists=True),
    # Metadata Options
    project: str = typer.Option(settings.DEFAULT_PROJECT_NAME, "--project", "-p", help="Project Tag (Description)"),
    event: str = typer.Option(None, "--event", "-e", help="Event Name"),
    event_date: datetime = typer.Option(None, "--date", help="Event Date (YYYY-MM-DD)"),
    # Processing Options
    diarization: bool = typer.Option(True, "--diarization/--no-diarization", "-d/-D"),
    language: str = typer.Option("fr", "--language", "-l"),
    # Output Options
    output: Path = typer.Option(
        None, 
        "--output", "-o", 
        help="Folder to save the resulting ZIP."
    )
):
    """
    Scans a folder, processes audio, and automatically downloads the results.
    """
    
    # 1. Handle Defaults
    if folder is None:
        # ✅ FIX: Convert string setting to Path object
        folder = Path(settings.INPUT_FOLDER)
        
    if output is None:
        # ✅ FIX: Convert string setting to Path object
        output = Path(settings.DEFAULT_OUTPUT_FOLDER)
        
    # 2. Display Info
    console.rule("[bold blue]🚀 Starting Transcription Job")
    console.print(f"📂 Source:     {folder}")
    console.print(f"💾 Output:     {output}")
    console.print(f"🏷️  Tag:        {project}")
    if event: 
        console.print(f"📅 Event:      {event} ({event_date})")

    service = TranscriptionService()
    client = ResearchEngineClient() 

    # 3. Processing Loop
    try:
        with console.status("[bold cyan]Step 1/2: Processing audio files...[/]", spinner="dots"):
            # ✅ Pass new params to the service logic
            service.run(
                description=project, 
                input_dir=folder, 
                diarization=diarization, 
                language=language,
                event=event,           
                event_date=event_date  
            )
        console.print("[bold green]✅ Step 1 Complete: Processing finished.[/]")
        
        # 4. Automatic Download
        console.print(f"[cyan]⬇️  Step 2/2: Downloading results for tag '{project}'...[/]")

        search_date = event_date.date() if event_date else None
        
        saved_path = client.search_and_download(
            search_query=project,                 
            project_name=settings.DEFAULT_PROJECT_NAME, 
            date_from=search_date,               
            output_dir=str(output)
        )
        
        if saved_path:
            console.print(Panel(f"Results saved to:\n[bold underline]{saved_path}[/]", style="green"))
        else:
            console.print("[bold red]⚠️  Processing finished, but download failed (or no files found).[/]")

    except Exception as e:
        console.print(f"[bold red]❌ Critical Error:[/]")
        console.print(str(e))
        raise typer.Exit(code=1)
    

# =========================================================
#  COMMAND: SEARCH & DOWNLOAD (Batch Action)
# =========================================================
@app.command("download")
def download_results(
    query: str = typer.Option(None, "--query", "-q", help="Search text (Filename, Description, Event)"),
    date: datetime = typer.Option(None, "--date", "-d", help="Filter by event date (YYYY-MM-DD)"),
    project: str = typer.Option(settings.DEFAULT_PROJECT_NAME, "--project", "-p", help="Project bucket"),
    output: Path = typer.Option(settings.DEFAULT_OUTPUT_FOLDER, "--output", "-o", help="Target folder")
):
    """
    Directly download a ZIP of transcriptions matching your search criteria.
    """
    client = ResearchEngineClient()
    
    console.rule(f"[bold blue]⬇️  Downloading: {project}[/]")
    console.print(f"🔎 Query:  {query if query else '[All]'}")
    console.print(f"📅 Date:   {date.date() if date else '[Any]'}")
    console.print(f"📂 Output: {output}")

    # Convert datetime to date object for the API
    date_obj = date.date() if date else None

    saved_path = client.search_and_download(
        search_query=query,
        project_name=project,
        date_from=date_obj,
        output_dir=output
    )

    if saved_path:
        console.print(Panel(f"✅ Download Complete!\n[bold underline]{saved_path}[/]", style="green"))
    else:
        console.print("[red]❌ Download failed. No files found or server error.[/]")


# =========================================================
#  COMMAND: EXPLORE (Search -> Read -> Manage)
# =========================================================
@app.command("explore")
def explore_files(
    query: str = typer.Option(None, "--query", "-q", help="Initial search text"),
    date: datetime = typer.Option(None, "--date", "-d", help="Initial date filter"),
    project: str = typer.Option(settings.DEFAULT_PROJECT_NAME, "--project", "-p")
):
    """
    Interactive dashboard: Search files, Read full text, Delete, or Download.
    """
    client = ResearchEngineClient()
    current_query = query
    current_date = date.date() if date else None

    # --- MAIN INTERACTIVE LOOP ---
    while True:
        console.clear()
        console.rule(f"[bold blue]🔍 Research Engine: {project}[/]")
        
        # 1. Fetch Data
        with console.status("Fetching files...", spinner="dots"):
            files = client.list_files(
                project_name=project, 
                q=current_query, 
                date_from=current_date
            )

        # 2. Display Status Header
        q_display = current_query if current_query else "[All]"
        d_display = current_date if current_date else "[Any]"
        console.print(f"🔎 Filters: Query='[bold cyan]{q_display}[/]' | Date='[bold cyan]{d_display}[/]'")
        console.print(f"📄 Found: {len(files)} files\n")

        # 3. Build Selection Menu
        choices = []
        file_map = {} # Maps the menu label string back to the File ID

        if files:
            for f in files:
                # Create a nice label: "📅 2024-01-01 | MyFile.mp3 (Event Name)"
                event_str = f"| Event: {f['event']}" if f.get('event') else ""
                date_str = f"📅 {f['event_date']}" if f.get('event_date') else "📅 ----"
                
                label = f"{date_str} | {f['name']} {event_str}"
                choices.append(label)
                file_map[label] = f['id']
            
            choices.append(questionary.Separator())

        # 4. Add Action Options
        choices.extend([
            "🔎 Change Search Filters",
            "⬇️  Download These Results (ZIP)",
            "❌ Exit"
        ])

        # 5. Ask User
        selection = questionary.select(
            "Select a file to read or an action:",
            choices=choices,
            use_indicator=True
        ).ask()

        # --- HANDLE ACTIONS ---
        
        if selection == "❌ Exit":
            break

        elif selection == "🔎 Change Search Filters":
            current_query = questionary.text("New Search Query (press Enter for None):").ask() or None
            date_str = questionary.text("New Date (YYYY-MM-DD) or Enter for None:").ask()
            try:
                current_date = datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else None
            except ValueError:
                console.print("[red]Invalid date format. Ignoring date.[/]")
                current_date = None
            continue

        elif selection == "⬇️  Download These Results (ZIP)":
            output_dir = settings.DEFAULT_OUTPUT_FOLDER
            console.print(f"[cyan]Downloading to {output_dir}...[/]")
            client.search_and_download(
                search_query=current_query,
                project_name=project,
                date_from=current_date,
                output_dir=output_dir
            )
            questionary.press_any_key_to_continue().ask()
            continue

        # --- HANDLE FILE SELECTION (Read Mode) ---
        else:
            file_id = file_map[selection]
            details = client.get_file_details(file_id)

            if details:
                # 6. Show File Details Screen
                console.clear()
                console.rule(f"[bold]📄 {details['filename']}[/]")
                
                # Metadata Panel
                meta_text = (
                    f"[bold]ID:[/]\t\t{details['id']}\n"
                    f"[bold]Project:[/]\t{details['project_name']}\n"
                    f"[bold]Event:[/]\t\t{details.get('event', '-')}\n"
                    f"[bold]Date:[/]\t\t{details.get('event_date', '-')}\n"
                    f"[bold]Status:[/]\t{details['status']}\n"
                    f"[bold]Description:[/]\t{details.get('description', '-')}"
                )
                console.print(Panel(meta_text, title="Metadata", border_style="blue"))

                # Full Text
                console.print("\n[bold underline]Transcription Content:[/]")
                full_text = details.get("full_text", "")
                if full_text:
                    # Using Markdown renders it nicely (headers, lists, bold text)
                    console.print(Markdown(full_text))
                else:
                    console.print("[italic yellow]No text content available.[/]")
                
                console.print("\n")

                # 7. File Context Menu
                action = questionary.select(
                    "What do you want to do with this file?",
                    choices=[
                        "🔙 Back to List",
                        "🗑️  Delete File permanently"
                    ]
                ).ask()

                if action == "🗑️  Delete File permanently":
                    confirm = questionary.confirm("Are you sure? This cannot be undone.").ask()
                    if confirm:
                        client.delete_file(file_id)
                        console.print("[green]File deleted.[/]")
                        questionary.press_any_key_to_continue().ask()
            
            else:
                console.print("[red]Error: Could not fetch file details.[/]")
                questionary.press_any_key_to_continue().ask()