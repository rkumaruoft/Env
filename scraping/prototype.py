import os
import json
import requests
from urllib.parse import urljoin
from bs4 import BeautifulSoup

# This one directly fetches hyperlinked pdfs with the keywords from the specified  web page,

PAGE_URL = "https://www.toronto.ca/services-payments/water-environment/environmentally-friendly-city-initiatives/becoming-a-climate-ready-toronto/"
STATE_FILE = "known_reports.json"
DOWNLOAD_DIR = "climate_reports"

# (optional) only grab PDFs whose link text contains any of these:
KEYWORDS = ["Climate Report", "Future Climate", "Adaptation", "Mitigation"]


# ─── STATE ──────────────────────────────────────────────────────────────────
def load_known():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return set(json.load(f))
    return set()


def save_known(known):
    with open(STATE_FILE, "w") as f:
        json.dump(sorted(known), f, indent=2)


# ─── SCRAPE + DOWNLOAD ──────────────────────────────────────────────────────
def fetch_pdf_links():
    resp = requests.get(PAGE_URL)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    found = set()
    for a in soup.select("a[href$='.pdf']"):
        text = a.get_text(strip=True)
        # filter by anchor‑text if you like
        if KEYWORDS and not any(kw.lower() in text.lower() for kw in KEYWORDS):
            continue
        href = a['href'].strip()
        full = urljoin(PAGE_URL, href)
        found.add(full)
    return found


def download_pdf(url):
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    filename = os.path.join(DOWNLOAD_DIR, url.split("/")[-1])
    if os.path.exists(filename):
        return False
    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        with open(filename, "wb") as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)
    print(f"[+] Downloaded: {filename}")
    return True


def check_for_new_reports():
    known = load_known()
    found = fetch_pdf_links()
    new = sorted(found - known)
    if not new:
        print("No new PDFs found.")
    else:
        print(f"Found {len(new)} new PDF(s):")
        for url in new:
            print("  ", url)
            download_pdf(url)
        save_known(known | set(new))


# ─── ENTRY POINT ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    check_for_new_reports()
