import os
import shutil
import logging
from pathlib import Path
from typing import List

from app.core.database import SessionLocal
from app.repositories.media_repository import MediaRepository

from dotenv import load_dotenv

# App imports
from app.models.interfaces import (
    TranscriberInterface, 
    MediaConverterInterface,
    MediaChunkerInterface,
    TranscriptionNormaliser,
)
from app.models.transcriber.media_chunker import AudioChunker
from app.models.transcriber.media_converter import FFmpegMediaConverter
# TYPO FIX: OpanAI -> OpenAI
from app.models.transcriber.opanai_transcriber import OpanAITranscriber 
from app.models.transcriber.replicate_transcriber import ReplicateTranscriber
from app.models.transcriber.output_normaliser import Normaliser

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()

# Constants
_INPUT_DIR = Path("data/input/")
_TEMP_FOLDER = Path("data/_temp/")
_ARCHIVES = Path("data/_archives/") 

class TranscriptionService:
    """
    The Orchestrator. 
    It coordinates the Media Converter, Chunker, Transcriber, and Normaliser.
    """
    def __init__(self):
        self.converter: MediaConverterInterface = FFmpegMediaConverter()
        self.chunker: MediaChunkerInterface = AudioChunker()
        self.transcriber: TranscriberInterface = ReplicateTranscriber()
        self.transcriber_beta: TranscriberInterface = OpanAITranscriber()
        self.normaliser: TranscriptionNormaliser = Normaliser(
            prompt_path="prompts/post_processing.txt",
            model_name="gemini-3-flash-preview" 
        )
        self.db = SessionLocal()

        self.repo = MediaRepository(self.db) # Pass DB session explicitly if needed

    # ---------------------------------------------------------
    # HELPERS
    # ---------------------------------------------------------
    def _clean_dir(self, job_temp_dir: Path) -> None:
        """
        Deletes the entire temporary workspace for this job.
        """
        if job_temp_dir.exists():
            try:
                shutil.rmtree(job_temp_dir)
                logger.info(f"🧹 Cleaned up temp directory: {job_temp_dir}")
            except OSError as e:
                logger.error(f"⚠️ Error removing temp dir {job_temp_dir}: {e}")

    def _text_splitter(self, text: str, chunk_size: int = 1000) -> List[str]:
        """
        Splits clean text into semantic pieces (paragraphs).
        """
        paragraphs = text.split("\n\n")
        chunks = []
        current_chunk = ""
        
        for para in paragraphs:
            if len(current_chunk) + len(para) < chunk_size:
                current_chunk += para + "\n\n"
            else:
                chunks.append(current_chunk.strip())
                current_chunk = para + "\n\n"
        
        if current_chunk:
            chunks.append(current_chunk.strip())
            
        return chunks

    # ---------------------------------------------------------
    # PROCESS SINGLE FILE
    # ---------------------------------------------------------
    def process_file(self, 
                     input_file_path: Path, 
                     diarization: bool = True,
                     language: str = "fr") -> None:
        
        if not input_file_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_file_path}")

        file_stem = input_file_path.stem
        logger.info(f"🚀 Starting pipeline for: {file_stem}")

        # ---------------------------------------------------------
        # STEP 0: DB Initialization & Workspace Setup
        # ---------------------------------------------------------
        # Detect type
        media_type = self.converter.detect_media_type(str(input_file_path))

        # Create Parent Record
        media_record = self.repo.create_media_file(
            filename=input_file_path.name, 
            path=str(input_file_path), 
            media_type=media_type
        )
        
        file_id = media_record.id
        self.repo.mark_as_processing(file_id)

        # Create ID-Based Workspace (Prevents collisions)
        job_dir = _TEMP_FOLDER / str(file_id)
        chunks_audio_dir = job_dir / "audio_chunks"
        chunks_audio_dir.mkdir(parents=True, exist_ok=True)

        # ---------------------------------------------------------
        # STEP 1: Extract Audio
        # ---------------------------------------------------------
        logger.info("Step 1: Extracting audio...")
        try:
            wav_path = self.converter.extract_audio(str(input_file_path))
            # Move wav to temp folder to keep things clean
            temp_wav_path = job_dir / "full_audio.wav"
            shutil.move(wav_path, temp_wav_path)
            logger.info(f"   -> Audio extracted to workspace.")
        except Exception as e:
            logger.error(f"Audio extraction failed: {e}")
            raise e

        # ---------------------------------------------------------
        # STEP 2: Split Audio
        # ---------------------------------------------------------
        logger.info("Step 2: Splitting audio...")
        audio_chunk_paths = self.chunker.split(str(temp_wav_path), str(chunks_audio_dir), chunk_size_mb=20)
        audio_chunk_paths.sort() 

        # ---------------------------------------------------------
        # STEP 3: Transcribe Loop (Raw Data)
        # ---------------------------------------------------------
        logger.info("Step 3: Transcribing chunks...")
        
        # Init "Shell" Transcription
        transcription_record = self.repo.init_transcription(
            media_file_id=file_id, 
            model="whisperX"
        )
        transcription_id = transcription_record.id

        for i, audio_chunk in enumerate(audio_chunk_paths):
            # Safety check for tiny files
            if os.path.getsize(audio_chunk) < 1024 * 5: 
                continue

            # Transcribe
            chunk_text = self.transcriber.transcribe(
                input_path=audio_chunk, 
                diarization=diarization, 
                language=language
            )
            
            # Save Raw Chunk to DB
            self.repo.create_chunk(
                transcription_id=transcription_id,
                index=i,
                text=chunk_text
            )
            logger.info(f"   -> Chunk {i+1} saved.")

        # ---------------------------------------------------------
        # STEP 4: Merge & Normalize
        # ---------------------------------------------------------
        logger.info("Step 4: Normalizing text...")
        
        raw_chunks = self.repo.get_all_chunks_text(transcription_id)
        full_raw_text = "\n\n".join(raw_chunks)

        # AI Post-Processing
        norm_transcription = self.normaliser.post_process(row_transcription=full_raw_text)

        # Update Parent Record with Final Text
        self.repo.update_transcription_full_text(transcription_id, norm_transcription)

        # ---------------------------------------------------------
        # STEP 5: The "Swap" (Replace Dirty Chunks with Clean Ones)
        # ---------------------------------------------------------
        logger.info("Step 5: Re-chunking for RAG...")

        # A. Delete old "dirty" chunks
        self.repo.delete_all_chunks(transcription_id)

        # B. Split the clean text into smart paragraphs
        new_text_segments = self._text_splitter(norm_transcription)

        # C. Prepare data for bulk insert
        new_chunks_data = []
        for i, segment in enumerate(new_text_segments):
            new_chunks_data.append({
                "index": i,
                "text": segment,
                "vector": None # Ready for embedding service
            })

        # D. Save new chunks
        self.repo.save_chunks(transcription_id, new_chunks_data)

        logger.info(f"✅ Pipeline Complete for {file_stem}!")

        # ---------------------------------------------------------
        # STEP 6: Clean Up
        # ---------------------------------------------------------
        self._clean_dir(job_dir)
    
    # ---------------------------------------------------------
    # Import existing text files
    # ---------------------------------------------------------
    def save_to_db_existing_transcriptions(self, directory: str):
        dir_path = Path(directory)
        if not dir_path.exists():
            return

        for file_path in dir_path.iterdir():
            if file_path.suffix == ".txt":
                with open(file_path, "r", encoding="utf-8") as f:
                    _text = f.read()
                
                self.repo.create_text_only_entry(
                    filename=file_path.name, 
                    full_text=_text
                )
                logger.info(f"Imported: {file_path.name}")

    # ---------------------------------------------------------
    # MAIN RUNNER
    # ---------------------------------------------------------
    def run(self, 
            input_dir: Path = _INPUT_DIR, 
            archives_dir: Path = _ARCHIVES, 
            diarization: bool = True,
            language: str = "fr") -> None:
        
        if not input_dir.exists():
            logger.error(f"Input directory not found: {input_dir}")
            return
            
        archives_dir.mkdir(parents=True, exist_ok=True)
        
        # Simple list filtering
        input_files = [
            f for f in input_dir.iterdir() 
            if f.is_file() and not f.name.startswith('.')
        ]

        logger.info(f"Found {len(input_files)} files to process.")

        for file_path in input_files:
            try:
                self.process_file(
                    input_file_path=file_path, 
                    diarization=diarization, 
                    language=language
                )

                # Archive
                shutil.move(str(file_path), str(archives_dir / file_path.name))
                logger.info(f"📦 Archived: {file_path.name}")

            except Exception as e:
                logger.error(f"❌ Failed to process {file_path.name}: {e}", exc_info=True)

if __name__ == "__main__":
    service = TranscriptionService()
    service.run()