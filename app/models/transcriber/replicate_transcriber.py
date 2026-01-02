import os
from typing import Optional, Dict, Any
import replicate

from ..interfaces import TranscriberInterface



class ReplicateTranscriber(TranscriberInterface):
    """
    A specific implementation of the TranscriberInterface using Replicate's API 
    to call WhisperX as a transcription model.
    """
    
    MODEL_VERSION = "victor-upmeet/whisperx:84d2ad2d6194fe98a17d2b60bef1c7f910c46b2f6fd38996ca457afd9c8abfcb"

    def __init__(self):
        """
        Initialize the Replicate client.
        Requires REPLICATE_API_TOKEN to be set in environment variables.
        """
        # The client is implicitly initialized by the replicate module imports
        # assuming the env var is set.
        self.client = replicate

    def _parse_output(self, output: Dict[str, Any], diarization: bool) -> str: 
        """
        Parses the raw JSON output from Replicate into a readable string.
        """
        segments = output.get('segments', [])
        
        # Use a list for string construction (more memory efficient than +=)
        parts = []

        if diarization:
            current_speaker = None
            
            for segment in segments:
                new_speaker = segment.get('speaker', 'Unknown')
                text = segment.get('text', '').strip()

                # If the speaker changes, add a break and the new speaker name
                if current_speaker != new_speaker:
                    if current_speaker is not None:
                        parts.append("\n\n")
                    
                    parts.append(f"**{new_speaker}** : ")
                    current_speaker = new_speaker
                
                parts.append(f"{text} ")
        else:
            for segment in segments:
                text = segment.get('text', '').strip()
                parts.append(f"{text} ")

        return "".join(parts).strip()

    def transcribe(self, input_path: str, **kwargs) -> str:
        """
        Transcribes an audio file into text using Replicate models.

        Args:
            input_path (str): Absolute or relative path to the audio file.
            **kwargs: Optional arguments passed directly to the Replicate API. 
                      Defaults will be used if keys are not provided.

        Returns:
            str: The final transcription.

        Raises:
            FileNotFoundError: If the input_path does not exist.
        """
        hf_token = os.getenv("HUGGINGFACE_API_TOKEN")
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"Input file not found: {input_path}")
        
        # 1. Define Defaults
        input_params = {
            "debug": False,
            "vad_onset": 0.5,
            "batch_size": 64,
            "vad_offset": 0.363,
            "diarization": True,
            "temperature": 0,
            "align_output": False,
            "language": "fr",
            "huggingface_access_token": hf_token
        }
        
        # 2. Merge user kwargs into defaults
        # This ensures defaults exist even if the user only provides one custom arg
        input_params.update(kwargs)

        # 3. Run Inference (using context manager to safely close file)
        with open(input_path, "rb") as audio_file:
            input_params["audio_file"] = audio_file
            
            output = self.client.run(
                self.MODEL_VERSION,
                input=input_params
            )

        # 4. Parse
        is_diarized = input_params.get("diarization", False)
        return self._parse_output(output, diarization=is_diarized)