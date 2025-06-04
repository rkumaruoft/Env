from google import genai
import chardet
import json
import re
import os


class GeminiMetadataExtractor:
    def __init__(self, api_key_path="google_api_key.txt"):
        self.api_key = self._load_api_key(api_key_path)
        self.client = genai.Client(api_key=self.api_key)

    def _load_api_key(self, path):
        if not os.path.exists(path) or os.stat(path).st_size == 0:
            print("🔐 Google API key not found. Please enter your key:")
            api_key = input("API Key: ").strip()
            with open(path, "w") as f:
                f.write(api_key)
        else:
            with open(path, "r") as file:
                api_key = file.read().strip()
        return api_key

    def get_db_info(self, text):
        """
        Takes the full text of a document and returns a dictionary of metadata fields.
        """
        file_text = str(text)
        context_prompt = (
            "From the given text extract, "
            "1. Title of the text "
            "2. Type of the text (research paper, government article, news article, technical report, or other) "
            "3. Authors of the Text "
            "4. Date - (This could be the date the paper was last updated or its publication date), "
            "return as a datetime object "
            "5. DOI link of the given text if available (NONE if not). "
            "Make sure not to include DOI links from the references. "
            "6. Publishing Organization if available (NONE if not). "
            "I want the output as a JSON object."
        )

        response = self.client.models.generate_content(
            model="gemini-2.0-flash", contents=[file_text, context_prompt]
        )
        return response.text

    def process_directory(self, directory='extracted_text', output_file='db_output.json'):
        db_entries = []
        for entry in os.scandir(directory):
            if entry.is_file():
                print(f"📄 Processing: {entry.path}")
                with open(entry.path, "rb") as this_file:
                    this_file_text = self.read_text_file(this_file)
                    try:
                        response_text = self.get_db_info(this_file_text)
                        db_dict = self.extract_json_dict(response_text)
                        db_entries.append(db_dict)
                    except Exception as e:
                        print(f"❌ Error processing {entry.path}: {e}")

        with open(output_file, "w", encoding="utf-8") as outfile:
            json.dump(db_entries, outfile, indent=4, ensure_ascii=False)

        print(f"\n✅ Saved {len(db_entries)} entries to {output_file}")
        return db_entries

    @staticmethod
    def read_text_file(file):
        raw = file.read()
        detection = chardet.detect(raw)
        encoding = detection["encoding"] or "utf-8"
        return raw.decode(encoding, errors="replace").strip()

    @staticmethod
    def extract_json_dict(text: str):
        """
        Extracts the first JSON object (enclosed in curly braces) from a string
        and returns it as a Python dictionary.

        Args:
            text (str): The input string containing JSON.

        Returns:
            dict: The extracted JSON as a Python dictionary.
        """
        match = re.search(r'\{.*?\}', text, re.DOTALL)
        if not match:
            raise ValueError("No JSON object found in the input string.")

        try:
            return json.loads(match.group())
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON format: {e}")


if __name__ == "__main__":
    extractor = GeminiMetadataExtractor()
    extractor.process_directory()
