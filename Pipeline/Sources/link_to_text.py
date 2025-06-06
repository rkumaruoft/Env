import os
import requests
from pypdf import PdfReader
import io
"""
to use this in another place,
from pdf_link_to_text import get_all_pdf_texts

def main():
    # Use the default path hard‐coded inside pdf_link_to_text.py:
    all_pdfs = get_all_pdf_texts("/scraping/existing_pdf_links.txt")
    # Now `all_pdfs` is a list of [text, url] pairs.
    for idx, (text, url) in enumerate(all_pdfs, start=1):
        print(f"PDF #{idx} ({url}) has {len(text)} characters of extracted text")
"""

# ─── Configuration ─────────────────────────────────────────────────────────────
# Path to the txt file containing one PDF URL per line:
LINKS_FILE = "/scraping/existing_pdf_links.txt"
# (We no longer need OUTPUT_FILE, since we return a Python object)


# ─── Extraction logic ──────────────────────────────────────────────────────────
def extract_text_from_pdf_url(url: str) -> list:
    """
    Fetch the PDF at `url`, extract its text, and return [text, url].
    If anything goes wrong (e.g. network error, parse error), this function
    will raise an exception.
    """
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()  # Raises HTTPError if status != 200
    pdf_stream = io.BytesIO(resp.content)
    reader = PdfReader(pdf_stream)

    text = ""
    for page in reader.pages:
        text += (page.extract_text() or "") + "\n"

    return [text, url]


def get_all_pdf_texts(links_filepath: str) -> list:
    """
    Read every URL from `links_filepath`, call `extract_text_from_pdf_url` on each,
    collect the results into a list of [text, url], and return it.
    Any URL that fails to download or parse will be skipped silently.
    """
    if not os.path.isfile(links_filepath):
        raise FileNotFoundError(f"Links file not found: {links_filepath}")

    with open(links_filepath, "r", encoding="utf-8") as lf:
        urls = [line.strip() for line in lf if line.strip()]

    results = []
    for url in urls:
        try:
            pair = extract_text_from_pdf_url(url)
            results.append(pair)
        except Exception:
            # Silently skip any URL that fails (download or parse)
            continue

    return results