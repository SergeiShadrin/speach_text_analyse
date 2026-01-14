import os
from pathlib import Path
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent

print(BASE_DIR)

class Settings(BaseSettings):

    # --- Database ---
    # The field is required. If missing in .env, the app will crash with a helpful error.
    DATABASE_URL: str

    # --- External Services ---
    # Default to localhost if not set in .env
    RESEARCH_ENGINE_URL: str = "http://localhost:8000"

    # --- Application Defaults ---
    DEFAULT_PROJECT_NAME: str = "Transcriptions"
    
    # --- Paths ---
    # We can automatically construct paths relative to the project root
    INPUT_FOLDER: Path = BASE_DIR / "data" / "input"

    DEFAULT_OUTPUT_FOLDER: Path = Path("data/output")

    # Pydantic Config: Tells it to look for a file named ".env"
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8",
        extra="ignore" # Ignore extra keys in .env that aren't defined here
    )

    # --- Secrets (API Keys) ---
    # use SecretStr instead of str. 
    OPENAI_API_KEY: SecretStr
    REPLICATE_API_TOKEN: SecretStr
    GEMINI_API_KEY: SecretStr
    HUGGINGFACE_API_TOKEN: SecretStr

# Instantiate the settings object once
settings = Settings()