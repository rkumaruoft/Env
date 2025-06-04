from google import genai
import chardet
import json
import re
import os


def get_google_client():
    with open("google_api_key.txt", "r") as file:
        api_key = file.read().strip()

    return genai.Client(api_key=api_key)


def get_db_info(text, client):
    """
    This function takes a Google client object with the text of the file and returns a dict with all the required
    db fields.
    :param text: Full Text of the document
    :param client: the Google client object to make the api call to
    @:returns An dict of all the required fields for the db for a given
    """
    file_text = str(text)
    context_prompt = (
        "From the provided text, extract the following metadata as a JSON object:\n"
        "1. Title of the document.\n"
        "2. Type of document — choose one of the following: 'research paper', 'government article', 'news article', "
        "'technical report', or 'other'.\n"
        "3. List of authors.\n"
        "4. Date of the document — either the last updated date or the publication date. "
        "Return this as an ISO 8601 datetime string (e.g., '2023-06-01' or '2023').\n"
        "5. DOI link, if available. Return 'NONE' if no DOI is found. Do not include DOIs from the references "
        "section.\n"
        "6. Publishing organization, if available. Return 'NONE' if not present."
    )
    response = client.models.generate_content(
        model="gemini-2.0-flash", contents=[file_text, context_prompt]
    )

    return response.text


def read_text_file(file):
    raw = file.read()
    detection = chardet.detect(raw)
    encoding = detection["encoding"]

    if encoding is None:
        print("⚠️ Encoding not detected, defaulting to 'utf-8'")
        encoding = "utf-8"

    return raw.decode(encoding, errors="replace").strip()


def extract_json_dict(text: str):
    """
    Extracts the first JSON object (enclosed in curly braces) from a string
    and returns it as a Python dictionary.

    Args:
        text (str): The input string containing JSON.

    Returns:
        dict: The extracted JSON as a Python dictionary.
    """
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if not match:
        raise ValueError("No JSON object found in the input string.")

    try:
        return json.loads(match.group())
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON format: {e}")


if __name__ == "__main__":
    client = get_google_client()

    directory = 'extracted_text'
    db_entries = []

    for entry in os.scandir(directory):
        if entry.is_file():
            print(f"Processing: {entry.path}")
            with open(entry.path, "rb") as this_file:
                this_file_text = read_text_file(this_file)
                try:
                    response_text = get_db_info(this_file_text, client)
                    db_dict = extract_json_dict(response_text)
                    db_entries.append(db_dict)
                except Exception as e:
                    print(f"Error processing {entry.path}: {e}")

    # Save to a single JSON file
    with open("db_output.json", "w", encoding="utf-8") as outfile:
        json.dump(db_entries, outfile, indent=4, ensure_ascii=False)

    print(f"\n Saved {len(db_entries)} entries to db_output.json")
