from app.core.database import engine
from app.core.entities import Base
from sqlalchemy import text
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_db():
    """
    Reads all models inheriting from 'Base' and creates tables in Postgres.
    """
    logger.info("🚀 Connecting to Database...")
    
    try:
        # This line does the magic:
        # It looks at all imported classes (MediaFile, Transcription...) 
        # and generates the 'CREATE TABLE' SQL commands.
        with engine.connect() as connection:
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            connection.commit()
            print("✅ pgvector extension enabled.")

        Base.metadata.create_all(bind=engine)
        
        logger.info("✅ Database tables created successfully!")
        logger.info("   - media_files")
        logger.info("   - transcriptions")
        logger.info("   - transcription_chunks")
        
    except Exception as e:
        logger.error(f"❌ Error creating database: {e}")

if __name__ == "__main__":
    init_db()