from google import genai
import chardet
import json
import re
import os


class GeminiMetadataExtractor:
    """
    GeminiMetadataExtractor uses Google Gemini models to extract structured metadata from text documents.

    This class supports:
    - Extracting metadata from raw text using a structured prompt.
    - Processing .txt files in a directory and returning structured entries.
    - Cleaning and decoding text files with corrupted encodings or special characters.
    - Optionally returning metadata entries as a JSON-like object for database insertion.

    Attributes:
        api_key (str): API key used to authenticate with Gemini.
        client (genai.Client): Google Generative AI client.

    Args:
        api_key_path (str): Path to the file containing the Gemini API key. Defaults to 'gemini_api_key.txt'.
    """

    def __init__(self, api_key_path='gemini_api_key.txt'):
        self.api_key = self._load_api_key(api_key_path)
        if not self.api_key:
            raise ValueError("API key not found in environment or provided file.")
        self.client = genai.Client(api_key=self.api_key)

    @staticmethod
    def _load_api_key(path):
        """
        Load the Gemini API key from an environment variable or file.

        Args:
            path (str): Path to the key file.

        Returns:
            str: API key as string.
        """
        if os.getenv("GOOGLE_API_KEY"):
            return os.getenv("GOOGLE_API_KEY")

        if os.path.exists(path) and os.stat(path).st_size > 0:
            with open(path, "r") as f:
                return f.read().strip()

    def get_db_info(self, text):
        """
        Extract structured metadata from document text using Gemini.

        Args:
            text (str): Full document text.

        Returns:
            str: Response from Gemini model (JSON string).
        """
        file_text = str(text)
        context_prompt = (
            "From the given text extract, "
            "1. Title of the text - This is necessary - If title can not be extracted use (TITLE ERROR)"
            "2. Type of the text - choose one of the 5 following options"
            "(research paper, government article, news article, technical report, or other)"
            "3. Authors of the Text"
            "4. Date - (This could be the date the paper was last updated or its publication date), "
            "return as a datetime object"
            "5. DOI link of the given text if available (NONE if not). "
            "Make sure not to include DOI links from the references. "
            "6. Publishing Organization if available (NONE if not). "
            "I want the output as a JSON object."
        )

        response = self.client.models.generate_content(
            model="gemini-2.0-flash", contents=[file_text, context_prompt]
        )
        return response.text

    def generic_query(self, data, context_prompt):
        """
        Run a custom prompt on text using Gemini.

        Args:
            data (str): Full document text.
            context_prompt (str): Prompt for Gemini.

        Returns:
            str: Gemini model response.
        """
        response = self.client.models.generate_content(
            model="gemini-2.0-flash", contents=[data, context_prompt]
        )
        return response.text

    def process_directory(self, directory):
        """
        Process all txt files in a directory and return extracted metadata as a list of JSON objects.

        Args:
            directory (str): Path to directory containing .txt files.

        Returns:
            list: List of metadata dictionaries.
        """
        db_entries = []
        for entry in os.scandir(directory):
            if entry.is_file():
                print(f"Processing: {entry.path}")
                with open(entry.path, "rb") as this_file:
                    this_file_text = self.read_text_file(this_file)
                    this_file_text = self.fix_corrupt_temperature_units(this_file_text)
                    try:
                        response_text = self.get_db_info(this_file_text)
                        db_dict = self.extract_json_dict(response_text)
                        self.add_full_text(db_dict, this_file_text)
                        self.add_filename(db_dict, entry.name)
                        db_entries.append(db_dict)
                    except Exception as e:
                        print(f"Error processing {entry.path}: {e}")
        return db_entries

    @staticmethod
    def read_text_file(file):
        """
        Decode raw bytes from a file using detected encoding.

        Args:
            file (file-like): Opened file object.

        Returns:
            str: Decoded string content.
        """
        raw = file.read()
        detection = chardet.detect(raw)
        encoding = detection["encoding"] or "utf-8"
        return raw.decode(encoding, errors="replace").strip()

    def extract_json_dict(self, text: str):
        """
        Extract a JSON object from a string and parse it as a Python dictionary.

        Args:
            text (str): Input string.

        Returns:
            dict: Extracted dictionary.
        """
        match = re.search(r'\{.*?\}', text, re.DOTALL)
        if not match:
            raise ValueError("No JSON object found in the input string.")

        json_str = self.clean_for_json(match.group())

        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON format: {e}")

    @staticmethod
    def clean_for_json(s: str) -> str:
        """
        Remove control characters and BOM from a string.

        Args:
            s (str): Input string.

        Returns:
            str: Cleaned string.
        """
        allowed = set(range(32, 127)) | {9, 10, 13}
        s = s.replace('\ufeff', '')
        cleaned = ''.join(c for c in s if ord(c) in allowed or ord(c) >= 127)
        return cleaned.strip()

    @staticmethod
    def add_full_text(extracted_metadata, full_text):
        """
        Add full text content to extracted metadata.

        Args:
            extracted_metadata (dict): Metadata dictionary.
            full_text (str): Document full text.
        """
        if not isinstance(extracted_metadata, dict):
            raise TypeError("extracted_metadata must be a dictionary")
        extracted_metadata["full_text"] = full_text

    @staticmethod
    def add_filename(extracted_metadata, filename):
        """
        Add source filename to extracted metadata.

        Args:
            extracted_metadata (dict): Metadata dictionary.
            filename (str): File name.
        """
        if not isinstance(extracted_metadata, dict):
            raise TypeError("extracted_metadata must be a dictionary")
        extracted_metadata["filename"] = filename

    @staticmethod
    def fix_corrupt_temperature_units(text: str) -> str:
        """
        Replace corrupted temperature units (like 1.5\u0002C) with proper symbols.

        Args:
            text (str): Raw text.

        Returns:
            str: Corrected text.
        """
        return re.sub(r'(\d+(\.\d+)?)\u0002C', r'\1°C', text)
