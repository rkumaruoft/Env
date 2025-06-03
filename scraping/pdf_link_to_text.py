import os
import requests
from pypdf import PdfReader
import io

# This thing is pretty slow

# ─── Configuration ─────────────────────────────────────────────────────────────
# Path to the txt file containing one PDF URL per line:
LINKS_FILE = "/scraping/existing_pdf_links.txt"
# Path for the single txt file:
OUTPUT_FILE = "/scraping/pdf_text_extract.txt"

# ─── Extraction logic ──────────────────────────────────────────────────────────
def extract_text_from_pdf_url(url: str) -> str:
    """Fetch the PDF at `url`, extract and return its full text."""
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()  # Raises HTTPError if status != 200
    pdf_stream = io.BytesIO(resp.content)
    reader = PdfReader(pdf_stream)
    text = ""
    for page in reader.pages:
        text += (page.extract_text() or "") + "\n"
    return text

# ─── Main workflow ────────────────────────────────────────────────────────────
def main():
    # Read URLs from LINKS_FILE
    if not os.path.isfile(LINKS_FILE):
        print(f"Error: Links file not found: {LINKS_FILE}")
        return

    with open(LINKS_FILE, 'r') as lf:
        urls = [line.strip() for line in lf if line.strip()]

    # Ensure output directory exists
    out_dir = os.path.dirname(OUTPUT_FILE)
    if out_dir and not os.path.isdir(out_dir):
        os.makedirs(out_dir, exist_ok=True)

    # Open OUTPUT_FILE once, write only on successful extracts
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as out_f:
        for url in urls:
            try:
                pdf_text = extract_text_from_pdf_url(url)
                # Only if no exception was raised do we write braces + text
                out_f.write("{\n")
                out_f.write(pdf_text)
                out_f.write("}\n\n")
            except Exception as e:
                # Silently skip any URL that fails (download or parse)
                # If you want to see errors on the console, uncomment next line:
                # print(f"Skipping {url} due to error: {e}")
                continue

    print(f"✔️ Extracted text from {len(urls)} PDF(s) (errors were skipped) into '{OUTPUT_FILE}'")

if __name__ == '__main__':
    main()
