from abc import ABC, abstractmethod
from os import lstat

class TranscriberInterface(ABC):
    """
    The contract for any class that converts audio to text.
    """

    @abstractmethod
    def transcribe(self, file_path: str, **kwargs) -> str:
        """
        Takes the path to an audio file and returns the transcribed text.
        
        Args:
            file_path (str): The absolute or relative path to the audio file.
            
        Returns:
            str: The full transcription of the audio.
        """
        pass


class MediaConverterInterface(ABC):
    """
    The contract for any class that handles media format conversion
    (e.g., Video to Audio).
    """

    @abstractmethod
    def extract_audio(self, video_path: str, output_path: str) -> str:
        """
        Extracts the audio track from a video file and saves it to the output path.
        
        Args:
            video_path (str): Path to the source video file.
            output_path (str): Path where the audio file should be saved.
            
        Returns:
            str: The path to the generated audio file (usually output_path).
        """
        pass


class FileHandlerInterface(ABC):
    """
    The contract for any class that handles reading/writing result files.
    This ensures our logic is not hard-coded to just .txt files.
    """

    @abstractmethod
    def save_transcription(self, text: str, output_path: str) -> None:
        """
        Saves the transcribed text to a specific path.
        
        Args:
            text (str): The text content to save.
            output_path (str): The destination file path.
        """
        pass


class MediaChunkerInterface(ABC):
    """
    Contract for any class that handles chunking of a file on small parts.
    """

    @abstractmethod
    def split(self, input_path: str, output_dir: str = None, max_size_mb: int = 24) -> list:
        """
        Splits a media file into smaller chunks based on size.

        Args:
            input_path (str): The absolute path to the source file.
            output_dir (str): The folder where chunks should be saved.
            chunk_size_mb (int): The maximum size of each chunk in Megabytes. 
                                 Defaults to 25 (OpenAI limit).

        Returns:
            List[str]: A list of absolute paths to the generated chunk files
                       (e.g., ['/tmp/part1.mp3', '/tmp/part2.mp3']).
        """        
        pass


