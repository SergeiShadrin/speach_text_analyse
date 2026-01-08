import os
import subprocess
import ffmpeg  # Requires 'pip install ffmpeg-python'
from pathlib import Path
from ..interfaces import MediaConverterInterface
# Ensure this import matches the location of your MediaType Enum
from app.core.entities import MediaType 

class FFmpegMediaConverter(MediaConverterInterface):
    """
    Converter that handles both Video and Audio inputs, detecting their type
    and normalizing them to a standard WAV format.
    """

    def extract_audio(self, input_path: str) -> str:
        """
        Converts any media file (mp4, mkv, mp3, flac, ogg, etc.) to a 
        16kHz, Mono, PCM WAV file suitable for AI Transcription.
        """
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"Input file not found: {input_path}")

        # 1. Determine the output path
        filename = os.path.basename(input_path)
        _name = os.path.splitext(filename)[0]
        
        # SAFETY ADDITION: Ensure the folder exists before writing
        output_dir = "data/input/audio"
        os.makedirs(output_dir, exist_ok=True)
        
        output_path = f"{output_dir}/{_name}.wav"

        # 2. Build the FFmpeg Command
        command = [
            "ffmpeg",
            "-i", input_path,
            "-vn",                  # Disable video recording
            "-acodec", "pcm_s16le", # Codec: PCM 16-bit little endian
            "-ar", "16000",         # Sample Rate: 16kHz
            "-ac", "1",             # Channels: Mono
            output_path,
            "-y",                   # Overwrite output file without asking
            "-loglevel", "error"    # Less verbosity
        ]

        try:
            # 3. Run the Conversion
            subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return output_path

        # 4. Handle Conversion Failures
        except subprocess.CalledProcessError as e:
            error_message = e.stderr.decode() if e.stderr else "Unknown FFmpeg error"
            raise RuntimeError(f"Conversion failed for {input_path}: {error_message}")

    def detect_media_type(self, input_path: str) -> MediaType:
        """
        Scans the file streams using ffprobe to determine if it is Video or Audio.
        Returns the Enum: MediaType.VIDEO or MediaType.AUDIO.
        """
        if not os.path.exists(input_path):
            # Fallback or raise error depending on preference
            raise FileNotFoundError(f"Cannot probe file, path does not exist: {input_path}")

        try:
            # 'probe' reads the file metadata without decoding the whole file (fast)
            probe = ffmpeg.probe(input_path)
            
            # Get streams list
            streams = probe.get('streams', [])

            # Look for a video stream
            for stream in streams:
                if stream.get('codec_type') == 'video':
                    return MediaType.VIDEO
            
            # If no video stream is found, we assume it's Audio
            return MediaType.AUDIO

        except ffmpeg.Error as e:
            print(f"⚠️ Error probing file {input_path}: {e}")
            # If we can't read it, defaulting to AUDIO is usually safer for transcription
            return MediaType.AUDIO