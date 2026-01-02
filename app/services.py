import os
import shutil
import logging
from pathlib import Path
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

# Constants (converted to Path objects for safety)
_INPUT_DIR = Path("data/input/")
_OUTPUT_DIR = Path("data/output/transcriptions/")
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

    # ---------------------------------------------------------
    # HELPER: Clean Temp Files
    # ---------------------------------------------------------
    def _clean_dir(self, job_temp_dir: Path, wav_path: str) -> None:
        """
        Deletes the specific temporary folder for this job and the extracted wav.
        """
        # 1. Delete the extracted WAV file
        try:
            Path(wav_path).unlink(missing_ok=True)
            logger.info(f"Deleted temp audio: {wav_path}")
        except Exception as e:
            logger.warning(f"Could not delete wav file: {e}")

        # 2. Delete the entire job temp directory (audio chunks + text chunks)
        # shutil.rmtree is safer and faster than looping manually
        if job_temp_dir.exists():
            try:
                shutil.rmtree(job_temp_dir)
                logger.info(f"Deleted temp directory: {job_temp_dir}")
            except OSError as e:
                logger.error(f"Error removing temp dir {job_temp_dir}: {e}")

    # ---------------------------------------------------------
    # PROCESS SINGLE FILE
    # ---------------------------------------------------------
    def process_file(self, 
                     input_file_path: Path, 
                     output_dir: Path,
                     diarization: bool = True,
                     language: str = "fr") -> str:
        
        if not input_file_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_file_path}")
        
        # Ensure output exists
        output_dir.mkdir(parents=True, exist_ok=True)

        # Create specific temp subfolders for this job using _TEMP_FOLDER
        file_stem = input_file_path.stem  # e.g., "my_meeting"
        job_dir = _TEMP_FOLDER / file_stem
        chunks_audio_dir = job_dir / "audio_chunks"
        chunks_text_dir = job_dir / "text_chunks"

        # Create dirs
        chunks_audio_dir.mkdir(parents=True, exist_ok=True)
        chunks_text_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"🚀 Starting pipeline for: {file_stem}")

        # ---------------------------------------------------------
        # STEP 1: Extract Audio (Convert)
        # ---------------------------------------------------------
        logger.info("Step 1: Extracting audio...")
        # Passing str(job_dir) because some libs expect strings, not Path objects
        wav_path = self.converter.extract_audio(str(input_file_path))
        logger.info(f"   -> Audio saved to: {wav_path}")

        # ---------------------------------------------------------
        # STEP 2: Split Audio (Chunk)
        # ---------------------------------------------------------
        logger.info("Step 2: Splitting audio...")
        audio_chunk_paths = self.chunker.split(wav_path, str(chunks_audio_dir), chunk_size_mb=90)
        logger.info(f"   -> Created {len(audio_chunk_paths)} audio chunks.")

        # ---------------------------------------------------------
        # STEP 3: Transcribe Loop
        # ---------------------------------------------------------
        logger.info("Step 3: Transcribing chunks...")

        # Sort chunks to ensure order (important for merging later)
        audio_chunk_paths.sort() 

        for i, audio_chunk in enumerate(audio_chunk_paths):
            # --- 🛡️ SAFETY CHECK: Skip Empty/Tiny Files ---
            file_size = os.path.getsize(audio_chunk)
            if file_size < 1024 * 10:  # If less than 10KB (approx 0.5 sec of audio)
                logger.warning(f"⚠️ Skipping chunk {audio_chunk.name} (File too small: {file_size} bytes)")
                continue
            # ----------------------------------------------
            logger.info(f"   -> Transcribing part {i+1}/{len(audio_chunk_paths)}...")
            
            transcription_chunk = self.transcriber.transcribe(
                input_path=audio_chunk, 
                diarization=diarization, 
                language=language
            )

            chunk_filename = f"chunk_{i:03d}.txt"
            save_path = chunks_text_dir / chunk_filename

            with open(save_path, "w", encoding="utf-8") as f:
                f.write(transcription_chunk)

        # ---------------------------------------------------------
        # STEP 4: Normalize & Merge
        # ---------------------------------------------------------
        logger.info("Step 4: Normalizing and merging text...")
        norm_transcription = self.normaliser.post_process(input_dir=str(chunks_text_dir))

        # ---------------------------------------------------------
        # STEP 5: Final Save
        # ---------------------------------------------------------
        final_save_path = output_dir / f"transcription_{file_stem}.txt"
        with open(final_save_path, "w", encoding="utf-8") as f:
            f.write(norm_transcription)

        logger.info(f"✅ Pipeline Complete! Result saved to: {final_save_path}")

        # ---------------------------------------------------------
        # STEP 6: Clean Up
        # ---------------------------------------------------------
        self._clean_dir(job_dir, wav_path)

        return str(final_save_path)
    
    # ---------------------------------------------------------
    # MAIN ENTRY POINT
    # ---------------------------------------------------------
    def run(self, 
            input_dir: Path = _INPUT_DIR, 
            archives_dir: Path = _ARCHIVES, 
            output_dir: Path = _OUTPUT_DIR,
            diarization: bool = True,
            language: str = "fr") -> None:
        
        # Ensure dirs exist
        if not input_dir.exists():
            logger.error(f"Input directory not found: {input_dir}")
            return
        archives_dir.mkdir(parents=True, exist_ok=True)

        # 1. Get List of Files to Process
        # (Compare against archives to avoid re-work)
        archived_files = set(os.listdir(archives_dir))
        
        input_files = [
            f for f in os.listdir(input_dir) 
            if f not in archived_files and not f.startswith('.') 
            # Added check to ignore .DS_Store or hidden files
        ]

        logger.info(f"Found {len(input_files)} files to process.")

        for filename in input_files:
            file_path = input_dir / filename
            
            # Skip if it's a directory
            if file_path.is_dir():
                continue

            try:
                # 2. Process
                self.process_file(
                    input_file_path=file_path, 
                    output_dir=output_dir, # Passed explicitly
                    diarization=diarization, 
                    language=language
                )

                # 3. Archive (Move original file)
                dst_path = archives_dir / filename
                shutil.move(str(file_path), str(dst_path))
                logger.info(f"Moved {filename} to archives.")

            except Exception as e:
                logger.error(f"❌ Failed to process {filename}: {e}", exc_info=True)

# Run logic check
if __name__ == "__main__":
    service = TranscriptionService()
    service.run()