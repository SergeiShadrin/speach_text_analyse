# Audio Transcription & Research Engine

A powerful, local-first Research Engine CLI designed to manage media files, perform audio transcriptions, and enable semantic search over your knowledge base.

## 🚀 Features

- **Media Management**: Organize audio and video files with metadata (Events, Dates, Projects).
- **Automated Transcription**: Transcribe media using state-of-the-art models (OpenAI Whisper, etc.).
- **Speaker Diarization**: Detect and label different speakers in your audio.
- **Semantic Search**: Explore your transcribed text using natural language queries.
- **Data Persistence**: Store all transcriptions and vector embeddings in a local PostgreSQL database.
- **Interactive CLI**: Easy-to-use terminal interface for all operations.

## 📋 Prerequisites

Ensure you have the following installed on your system:

- **Python** 3.9 or higher
- **PostgreSQL** (with `pgvector` extension enabled)
- **ffmpeg** (required for audio processing)

## 🛠️ Installation

1.  **Clone the repository**
    ```bash
    git clone <repository_url>
    cd audio_transcription
    ```

2.  **Set up a Virtual Environment**
    ```bash
    python -m venv venv
    source venv/bin/activate
    ```

3.  **Install Dependencies**
    ```bash
    pip install -r requirements.txt
    ```

## ⚙️ Configuration

Create a `.env` file in the project root to configure your database and API keys.

```ini
# Database (Required)
DATABASE_URL=postgresql+psycopg2://user:password@localhost:5432/your_db_name

# API Keys (Required for different transcribers)
OPENAI_API_KEY=sk-...
GEMINI_API_KEY=...
REPLICATE_API_TOKEN=...
HUGGINGFACE_API_TOKEN=...

# Application Settings
RESEARCH_ENGINE_URL=http://localhost:8000
```

## 🚀 Usage

### 1. Initialize the Database
Before running any commands, ensure your database tables are created.
```bash
python init_db.py
```

### 2. Run the CLI
The main entry point is `main_cli.py`. You can access the help menu to see all available commands:
```bash
python main_cli.py --help
```

### Key Commands

#### **Process Media (Transcribe)**
Scan a folder, transcribe audio/video files, and save results to the database.
```bash
# Basic usage (defaults to settings.INPUT_FOLDER)
python main_cli.py transcription process

# Specify input folder and project name
python main_cli.py transcription process /path/to/media --project "My Interview" --language fr
```
**Options:**
- `--diarization` / `--no-diarization`: Enable/disable speaker detection.
- `--language`: Language code (e.g., `en`, `fr`).

#### **Explore & Search**
Launch an interactive terminal dashboard to search, read, and manage files.
```bash
python main_cli.py transcription explore
```
**Options:**
- `--query`: Start with a search query.
- `--date`: Filter by event date.

#### **Import Existing Transcriptions**
If you already have text files, you can import them directly into the system.
```bash
python main_cli.py transcription enregistrate_texts_already_transcribed /path/to/texts --project "Archives"
```

#### **Download Results**
Batch download transcriptions as a ZIP file.
```bash
python main_cli.py transcription download --project "My Interview"
```

## 🧪 Testing

This project uses `pytest` for testing.

```bash
# Run all tests
pytest

# Run a specific test file
pytest tests/test_cli.py
```
