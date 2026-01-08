import os
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("❌ DATABASE_URL is missing from .env")

# Configure connection args based on DB type
connect_args = {}
if "sqlite" in DATABASE_URL:
    # Required for SQLite to work with FastAPI/multithreading
    connect_args = {"check_same_thread": False}

# 1. Create the Engine
# pool_pre_ping=True prevents "server has gone away" errors in production
engine = create_engine(
    DATABASE_URL, 
    connect_args=connect_args, 
    pool_pre_ping=True
)

# 2. Create the Session Factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 3. Create the Base class
# All your models (User, Audio, etc.) should inherit from this 'Base'
Base = declarative_base()

def get_db() -> Generator[Session, None, None]:
    """
    Generator helper for FastAPI/Flask dependency injection.
    Automatically closes the session after the request is done.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()