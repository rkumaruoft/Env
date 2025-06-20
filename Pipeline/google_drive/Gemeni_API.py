from google import genai
import chardet
import json
import re
import os
import unicodedata


class GeminiMetadataExtractor:
    def __init__(self, api_key_path='gemini_api_key.txt'):
        self.api_key = self._load_api_key(api_key_path)
        if not self.api_key:
            raise ValueError("API key not found in environment or provided file.")
        self.client = genai.Client(api_key=self.api_key)

    @staticmethod
    def _load_api_key(path):
        """Load API key from env variable or file."""
        if os.getenv("GOOGLE_API_KEY"):
            return os.getenv("GOOGLE_API_KEY")

        if os.path.exists(path) and os.stat(path).st_size > 0:
            with open(path, "r") as f:
                return f.read().strip()

    def get_db_info(self, text):
        """
        Takes the full text of a document and returns a dictionary of metadata fields.
        """
        file_text = str(text)
        context_prompt = (
            "From the given text extract, "
            "1. Title of the text - This is necessory - If title can not be extracted use (TITLE ERROR)"
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
        Takes the full text of a document and returns a dictionary of metadata fields.
        """
        response = self.client.models.generate_content(
            model="gemini-2.0-flash", contents=[data, context_prompt]
        )
        return response.text

    def process_directory(self, directory, output_file='db_output.json'):
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

        with open(output_file, "w", encoding="utf-8") as outfile:
            json.dump(db_entries, outfile, indent=4, ensure_ascii=False)

        print(f"\nSaved {len(db_entries)} entries to {output_file}")

    @staticmethod
    def read_text_file(file):
        raw = file.read()
        detection = chardet.detect(raw)
        encoding = detection["encoding"] or "utf-8"
        return raw.decode(encoding, errors="replace").strip()

    def extract_json_dict(self, text: str):
        """
        Extracts the first JSON object (enclosed in curly braces) from a string
        and returns it as a Python dictionary.

        Args:
            text (str): The input string containing JSON.

        Returns:
            dict: The extracted JSON as a Python dictionary.
        """
        # Extract first JSON-like block
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
        Extremely fast removal of control characters (ASCII 0–31 except \t \n \r) and BOM.
        Operates at byte level for maximum speed.
        """
        # Allowed bytes: printable + \t (9), \n (10), \r (13)
        allowed = set(range(32, 127)) | {9, 10, 13}
        # Remove BOM if present
        s = s.replace('\ufeff', '')
        # Fast byte filtering
        cleaned = ''.join(c for c in s if ord(c) in allowed or ord(c) >= 127)
        return cleaned.strip()

    @staticmethod
    def add_full_text(extracted_metadata, full_text):
        """
        Adds a 'full_text' field to the extracted metadata dictionary.

        Args:
            extracted_metadata (dict): Metadata extracted from the document.
            full_text (str): Full text content of the document.

        Returns:
            dict: Updated metadata dictionary with 'full_text' field added.
        """
        if not isinstance(extracted_metadata, dict):
            raise TypeError("extracted_metadata must be a dictionary")
        extracted_metadata["full_text"] = full_text

    @staticmethod
    def add_filename(extracted_metadata, filename):
        """
        Adds a 'filename' field to the extracted metadata dictionary.

        Args:
            extracted_metadata (dict): Metadata extracted from the document.
            filename (str): Filename of the document.

        Returns:
            dict: Updated metadata dictionary with 'filename' field added.
        """
        if not isinstance(extracted_metadata, dict):
            raise TypeError("extracted_metadata must be a dictionary")
        extracted_metadata["filename"] = filename

    @staticmethod
    def fix_corrupt_temperature_units(text: str) -> str:
        # Replace patterns like '1.5\u0002C' or '2\u0002C' with '1.5°C', '2°C'
        return re.sub(r'(\d+(\.\d+)?)\u0002C', r'\1°C', text)
