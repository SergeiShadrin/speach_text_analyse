import os
import subprocess
from pathlib import Path
from .interfaces import MediaConverterInterface


class FFmpegMediaConverter(MediaConverterInterface):
    """
    Converter that handles both Video and Audio inputs 
    and normalizes them to a standard WAV format.
    """

    def extract_audio(self,
                      input_path: str, 
                      output_path: str = None) -> str:
        """
        Converts any media file (mp4, mkv, mp3, flac, ogg, etc.) to a 
        16kHz, Mono, PCM WAV file suitable for AI Transcription.
        
        Args:
            input_path: Path to the source file.
            output_path: Optional path for the result. If None, it replaces 
                         the extension of input_path with .wav.
        """
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"Input file not found: {input_path}")

        # 1. Determine the output path
        if output_path is None:
            filename = os.path.basename(input_path)
            _name = os.path.splitext(filename)[0]
            output_path = f"data/input/audio/{_name}.wav"

        # 2. Build the FFmpeg Command
        command = [
                "ffmpeg",
                "-i", input_path,
                "-vn",
                "-acodec", "pcm_s16le",
                "-ar", "16000", 
                "-ac", "1",
                output_path,
                "-y",
                "-loglevel", "error"
                ]

        try:
            # 3. Run the Conversion
            subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return output_path

        # 4. Handle Conversion Failures
        # This catches cases where the input file is corrupted 
        # or the format is totally unrecognizable by FFmpeg.
        except subprocess.CalledProcessError as e:
            error_message = e.stderr.decode() if e.stderr else "Unknown FFmpeg error"
            raise RuntimeError(f"Conversion failed for {input_path}: {error_message}")

       
           
