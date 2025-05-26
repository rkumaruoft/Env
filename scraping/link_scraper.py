import os
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from collections import deque
from urllib.robotparser import RobotFileParser

# ─── Configurations ────────────────────────────────────────────────────────────────
START_URL   = "https://www.toronto.ca/services-payments/water-environment/"
DOMAIN      = "toronto.ca"
KEYWORDS    = ["Climate Report", "Adaptation", "Mitigation", "Emissions"]
MAX_PAGES   = 1000        # total pages to fetch before stopping
MAX_DEPTH   = 6       # how many links‑deep you’ll crawl
DELAY       = 0.1        # seconds between requests
UA          = "LinkFetcher/1.0"
TXT_OUTPUT  = "pdf_links.txt"

# ─── ROBOTS.TXT ────────────────────────────────────────────────────────────
rp = RobotFileParser()
rp.set_url(urljoin(START_URL, "/robots.txt"))
rp.read()

# ─── CRAWL STATE ───────────────────────────────────────────────────────────
visited    = set()
queue      = deque([(START_URL, 0)])  # store (url, depth)
found_pdfs = set()
count      = 0

# ─── HELPERS ─────────────────────────────────────────────────────────────────
def is_pdf_link(href, text):
    href_l = href.lower()
    text_l = (text or "").lower()
    if not href_l.endswith(".pdf"):
        return False
    return any(kw.lower() in href_l or kw.lower() in text_l for kw in KEYWORDS)

# ─── CRAWL LOOP ──────────────────────────────────────────────────────────────
while queue and count < MAX_PAGES:
    url, depth = queue.popleft()
    if url in visited:
        continue
    visited.add(url)
    count += 1

    # respect robots.txt
    if not rp.can_fetch(UA, url):
        continue

    try:
        resp = requests.get(url, timeout=5, headers={"User-Agent": UA})
        resp.raise_for_status()
    except Exception:
        continue

    soup = BeautifulSoup(resp.text, "html.parser")

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        full = urljoin(START_URL, href)
        p    = urlparse(full)

        # only same‑domain
        if DOMAIN not in p.netloc:
            continue

        # PDF? collect it
        if is_pdf_link(full, a.get_text(strip=True)):
            found_pdfs.add(full)

        # HTML? enqueue if we haven’t exceeded depth
        elif depth < MAX_DEPTH and p.path.lower().endswith((".html", "/", "")):
            if full not in visited:
                queue.append((full, depth + 1))

   # time.sleep(DELAY) - uncomment if there is some code after this that needs to be ran and change delay

# ─── OUTPUT ─────────────────────────────────────────────────────────────────
# 1) print to console
for link in sorted(found_pdfs):
    print(link)

# 2) write to a text file
with open(TXT_OUTPUT, "w") as f:
    for link in sorted(found_pdfs):
        f.write(link + "\n")

# test
print(f"\n✔️  Saved {len(found_pdfs)} PDF links to {TXT_OUTPUT}")
