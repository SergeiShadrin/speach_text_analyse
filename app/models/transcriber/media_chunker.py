import os
import subprocess
import math
import glob
from ..interfaces import MediaChunkerInterface
from typing import List
from pathlib import Path




class AudioChunker(MediaChunkerInterface):
    """
    Splits a large WAV file into smaller chunks suitable for the Whisper API.
    It calculates the split duration based on bitrate to ensure chunks are 
    under the target size (e.g., 25MB).
    """

    def split(self, input_path: str, output_dir: str = None, chunk_size_mb: int = 24) -> List[str]: 
        """
        Splits the audio file into chronologically ordered parts.

        Args:
            input_path: Path to the source WAV file (must be 16kHz 16-bit Mono).
            output_dir: Directory where chunks will be stored.
            chunk_size_mb: Max size target in MB (Default: 24).

        Returns:
            List[str]: A list of file paths sorted by time (part 1, part 2, etc.).
        """

        if not os.path.exists(input_path):
            raise FileNotFoundError(f"Input file not found: {input_path}")

        # Make the output directory if it doesn't exist 
        if output_dir is None: 
            input_p = Path(input_path)
            output_dir = input_p.parent / input_p.stem

        Path(output_dir).mkdir(parents=True, exist_ok=True)

        file_name = Path(input_path).stem

        # 1. SAFETY: Remove any old chunks from previous Returns
        old_files = glob.glob(os.path.join(output_dir, f"{file_name}_*.wav"))
        for f in old_files:
            try:
                os.remove(f)
            except OSError:
                pass
 
        # 2. Calculate Split duration
        bytes_per_sec = 32000
        target_bytes = chunk_size_mb * 1024 * 1024

        segment_time = math.floor((target_bytes / bytes_per_sec) * 0.95)

        # 3. Define Output Pattern with Zero Padding
        output_pattern = os.path.join(output_dir, f"{file_name}_%03d.wav")

        # 4. Build FFmpeg Command
        command = [
            "ffmpeg",
            "-i", input_path,
            "-f", "segment",
            "-segment_time", str(segment_time),
            "-c", "copy",
            output_pattern,
            "-y",
            "-loglevel", "error"
        ]

        try:
            subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            # 5. Return Sorted List
            chunks = sorted([
                str(p) for p in Path(output_dir).glob(f"{file_name}_*.wav")
            ])
            if not chunks:
                raise RuntimeError("FFmpeg ran but produced no chunks.")

            return chunks

        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.decode() if e.stderr else "Unknown error"
            raise RuntimeError(f"Chunking failed: {error_msg}")



  
