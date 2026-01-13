import re
import os
from typing import List, Any
from ..interfaces import TranscriberInterface
from openai import OpenAI
from app.core.config import settings


class OpanAITranscriber(TranscriberInterface):
    """
    A specific implementation of the TranscriberInterface using OpenAI's API.
    Handles transcription, filler word removal, and speaker diarization formatting.
    """
    def __init__(self):
        """
        Initialize the OpenAI client and define filler words to be removed.
        Requires OPENAI_API_KEY to be set in environment variables.
        """
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.FILLERS = [
                r"\buh\b", r"\bum\b", r"\bah\b", r"\bso\b", r"\byou know\b"
                ]

    def clean_text(self, text):
        """
        Sanitizes a text string by removing defined filler words and extra spaces.

        Args:
            text (str): The raw text segment from the transcription.

        Returns:
            str: The cleaned text with fillers removed and whitespace normalized.
        """
        text = text.strip()
        for filler in self.FILLERS:
            text = re.sub(filler, "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s+", " ", text)

        return text.strip()

    def format_diarization(self, segments: List[Any]) -> str:
        """
        Converts a list of segment objects into a readable script format.
        Groups consecutive segments by the same speaker.

        Args:
            segments (List): A list of segment objects returned by the API. 
                             Each object must have .speaker and .text attributes.

        Returns:
            str: A formatted string resembling a script (e.g., "Speaker A: Hello...").
        """
        output = []
        current_speaker = None
        buffer = []

        for segment in segments:
            # Safely access attributes (assuming OpenAI response object structure)
            text = getattr(segment, 'text', '')
            speaker = getattr(segment, 'speaker', 'Unknown')
            
            cleaned_text = self.clean_text(text)
            if not cleaned_text:
                continue

            # If the speaker changes, flush the buffer to the output
            if speaker != current_speaker:
                if buffer:
                    output.append(f"{current_speaker}:\n" + " ".join(buffer) + "\n")
                current_speaker = speaker
                buffer = [cleaned_text]
            else:
                # If same speaker, just add text to the current block
                buffer.append(cleaned_text)

        # Flush the final buffer
        if buffer:
            output.append(f"{current_speaker}:\n" + " ".join(buffer))

        return "\n".join(output)


    def transcribe(self, 
                   input_path: str, 
                   **kwargs) -> str:
        """
        Transcribes an audio file into text using OpenAI models.

        Args:
            input_path (str): Absolute or relative path to the audio file.
            **kwargs: Optional arguments passed directly to the OpenAI API 
                      (e.g., language="fr", prompt="Technical context").

        Returns:
            str: The final transcription. If 'diarized_json' is requested, 
                 returns a formatted script. Otherwise, returns raw text.

        Raises:
            FileNotFoundError: If the input_path does not exist.
        """

        # 0. Verify file_path
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"Input file not found: {input_path}")

        # 1. Set defaults if not provided
        model = kwargs.pop("model", "gpt-4o-transcribe")
        response_format = kwargs.pop("response_format", "text")

        # Remove prompt if format is diarized
        if "diarize" in model or model == "gpt-4o-audio-preview":
            if "prompt" in kwargs:
                print(f"⚠️ Warning: 'prompt' argument ignored for model {model}")
                kwargs.pop("prompt")

            # verify in chunking_strategy was passed in kwargs, if not add it
            if "chunking_strategy" not in kwargs:
                kwargs["chunking_strategy"] = "auto"


        # 2. Open the file for this operation
        with open(input_path, "rb") as audio_file:

            # 3. ONE function call handles all parameter variations
            transcript = self.client.audio.transcriptions.create(
                file = audio_file,
                model = model,
                response_format = response_format,
                **kwargs
            )

        if response_format == "diarized_json":
            # Ensure the response actually has segments
            if hasattr(transcript, 'segments'):
                return self.format_diarization(transcript.segments)
            else:
                # Fallback if API returns simple text despite requesting JSON
                return getattr(transcript, 'text', str(transcript))
        else:
            # Standard return (works for 'json', 'text', 'srt', etc.)
            return getattr(transcript, 'text', str(transcript))










