import logging
import os
import re
import time
import textwrap
from pathlib import Path
from typing import List, Optional

from google import genai
from google.genai import types
from ..interfaces import TranscriptionNormaliser

# Configure logging
logger = logging.getLogger(__name__)



class Normaliser(TranscriptionNormaliser):
    """
    Reunites text transcriptions from a single audio/video source into one cohesive text 
    and passes it through an LLM to improve transcription quality.
    """

    def __init__(self, prompt_path: str, model_name: str):
        """
        Initialize the Normaliser with specific configuration.

        Args:
            prompt_path (str): Absolute path to the system prompt text file.
            model_name (str): The specific Gemini model version to use.
        """
        self.api_key = os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable is not set.")
        
        self.client = genai.Client(api_key=self.api_key)
        self.DEFAULT_CHUNK_SIZE = 20000 * 4
        self.model_name = model_name

        # Dynamic Path Loading
        if not os.path.exists(prompt_path):
            raise FileNotFoundError(f"System prompt file not found at: {prompt_path}")

        with open(prompt_path, "r", encoding="utf-8") as f:
            self.system_prompt = f.read()


    def _gemini_api_call(self, input_text: str) -> str:
        """
        Make an API call to Gemini with exponential backoff retry logic.
        """
        max_retries = 3
        backoff_factor = 2.0
        
        # Configure the request
        generate_content_config = types.GenerateContentConfig(
            temperature=0.1,
            system_instruction=[types.Part.from_text(text=self.system_prompt)],
            thinking_config=types.ThinkingConfig(thinking_level="MEDIUM"), 
        )

        content = [
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=input_text)],
            )
        ]

        for attempt in range(1, max_retries + 1):
            try:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=content,
                    config=generate_content_config
                )

                # Validation: Ensure we have a valid response structure
                if not response.candidates:
                    raise RuntimeError(f"API returned no candidates (Attempt {attempt})")
                
                candidate = response.candidates[0]
                if not candidate.content or not candidate.content.parts:
                    raise RuntimeError(f"Candidate content is empty (Attempt {attempt})")

                return candidate.content.parts[0].text

            except Exception as e:
                logger.warning(f"LLM call failed (Attempt {attempt}/{max_retries}): {e}")
                if attempt == max_retries:
                    raise e # Re-raise the last exception if we are out of retries
                
                time.sleep(backoff_factor ** (attempt - 1))

        return "" # Should be unreachable


    def load_and_merge_files(self, input_dir: str) -> str:
        """
        Reads all .txt files from the input directory and merges them into a single string.
        Uses natural sorting to ensure _1, _2, _10 are ordered correctly.
        """
        files = [f for f in os.listdir(input_dir) if f.endswith(".txt")]
        
        # Natural Sort: Handles "test_1" vs "test_10" correctly
        files.sort(key=lambda f: [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', f)])

        merged_parts = []
        for filename in files:
            path = os.path.join(input_dir, filename)
            with open(path, "r", encoding='utf-8') as file:
                content = file.read().strip()
                if content:
                    merged_parts.append(content)

        # Join with a single newline to preserve paragraph structure
        return "\n".join(merged_parts)


    def _create_smart_chunks(self, text: str) -> List[str]:
        """
        Splits text into chunks respecting the MAX_CHUNK_SIZE.
        Prioritizes splitting at double newlines (paragraphs) to avoid cutting sentences.
        """
        chunks = []
        current_chunk = []
        current_length = 0

        # Split by paragraphs first
        paragraphs = text.split("\n\n")

        for paragraph in paragraphs:
            para_len = len(paragraph)

            # Case 1: The paragraph itself is too huge -> Force split
            if para_len > self.DEFAULT_CHUNK_SIZE:
                # Flush current buffer if it exists
                if current_chunk:
                    chunks.append("\n\n".join(current_chunk))
                    current_chunk = []
                    current_length = 0
                
                # Split the massive paragraph
                sub_parts = textwrap.wrap(paragraph, width=self.DEFAULT_CHUNK_SIZE, break_long_words=False)
                chunks.extend(sub_parts)

            # Case 2: Paragraph fits in current chunk -> Add it
            elif current_length + para_len < self.DEFAULT_CHUNK_SIZE:
                current_chunk.append(paragraph)
                current_length += para_len

            # Case 3: Chunk is full -> Save and start new
            else:
                chunks.append("\n\n".join(current_chunk))
                current_chunk = [paragraph]
                current_length = para_len

        # Append any leftovers
        if current_chunk:
            chunks.append("\n\n".join(current_chunk))
            
        return chunks
    

    def post_process(self, row_transcription: str) -> str: 
        """
        Main workflow: Merges files, chunks them, and normalizes via LLM.

        Args:
            input_dir (str): The absolute path to the directory containing chunked text files.
        
        Returns:
            str: The final, normalized transcription text.
        """

        if row_transcription is None:
            raise ValueError(f"Input is empty")
        
        # 2. Preparation
        logger.info(f"Dividing the initial text into chunks.")
        #raw_transcript = self.load_and_merge_files(input_dir) 
        chunks = self._create_smart_chunks(row_transcription)
        
        normalized_parts = []

        # 3. Execution Loop
        logger.info(f"Starting normalization of {len(chunks)} chunks...")
        
        for i, chunk in enumerate(chunks):
            # Log progress clearly
            logger.info(f"Processing chunk {i+1}/{len(chunks)}...")
            try:
                cleaned_text = self._gemini_api_call(chunk)
                normalized_parts.append(cleaned_text)
            except Exception as e:
                logger.error(f"Failed to process chunk {i+1}: {e}")
                # Optional: Append raw text if LLM fails, to avoid data loss
                normalized_parts.append(chunk)

        # 4. Result
        return "\n\n".join(normalized_parts)