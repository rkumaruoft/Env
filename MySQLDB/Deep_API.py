from google import genai
import chardet


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
    context_prompt = "From the given text extract, " \
                     "1. Title of the text" \
                     "2. Type of the text (research paper, government article, news article, technical report, or other)" \
                     "3. Authors of the Text" \
                     "4. Date (This could be the date the paper was last updated or just the year that the text mentions)" \
                     "I want the output as a json object"

    response = client.models.generate_content(
        model="gemini-2.0-flash", contents=[file_text, context_prompt]
    )

    return response.text


def read_text_file(file):
    raw = file.read()
    encoding = chardet.detect(raw)["encoding"]
    return raw.decode(encoding, errors="replace").strip()


if __name__ == "__main__":
    client = get_google_client()

    # test a file
    file = open("extracted_text/1-s2.0-S2352250X21000415-main.txt", "rb")
    full_text = read_text_file(file)
    print(get_db_info(full_text, client))
