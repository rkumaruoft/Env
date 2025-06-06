import os
import asyncio
import aiohttp
from lxml import html  # ensure HTML parsing is available
import xml.etree.ElementTree as ET
from bloom_filter2 import BloomFilter  # pip install bloom-filter2
from urllib.robotparser import RobotFileParser
from urllib.parse import urljoin, urlparse
from collections import deque
from typing import Optional, List

# Patch for nested event loops (Spyder/Jupyter)
try:
    import nest_asyncio  # pip install nest_asyncio
    nest_asyncio.apply()
except ImportError:
    pass

# ─── Configurations ────────────────────────────────────────────────────────────
START_URL       = "https://www.toronto.ca/services-payments/water-environment/"
DOMAIN          = "toronto.ca"
MAX_PAGES       = 300
MAX_DEPTH       = 3
CONCURRENCY     = 10    # concurrent fetches for HTML pages
PDF_CONCURRENCY = 5     # concurrent PDF link processing
UA              = "LinkFetcher/1.2"
LINKS_FILE      = "/scraping/existing_pdf_links.txt"
# Keywords used to filter which PDF URLs to record
KEYWORDS        = [
    "Climate", "Adaptation", "Mitigation", "Emissions",
    "LENZ", "PollinateTO", "Eco-Roof", "Green",
    "Forestry", "TransformTO", "Waste", "Heat", "Cool",
    "Net Zero", "Net-zero"
]

# ─── Parse robots.txt ─────────────────────────────────────────────────────────
rp = RobotFileParser()
rp.set_url(urljoin(START_URL, "/robots.txt"))
rp.read()

# ─── Crawl state ─────────────────────────────────────────────────────────────
visited_pages = BloomFilter(max_elements=100000, error_rate=0.001)
queue         = deque([(START_URL, 0)])
found_pdfs    = set()

# ─── Load existing links ───────────────────────────────────────────────────────
if os.path.isfile(LINKS_FILE):
    with open(LINKS_FILE, 'r') as lf:
        for line in lf:
            link = line.strip()
            if link:
                found_pdfs.add(link)
existing_count = len(found_pdfs)

# ─── Helpers ─────────────────────────────────────────────────────────────────
def is_pdf_url(url: str) -> bool:
    return url.lower().endswith('.pdf')

def is_relevant_pdf(url: str, text: str) -> bool:
    url_l = url.lower()
    txt_l = (text or '').lower()
    return any(kw.lower() in url_l or kw.lower() in txt_l for kw in KEYWORDS)

async def fetch_html(session: aiohttp.ClientSession, url: str):
    if not rp.can_fetch(UA, url):
        return None
    try:
        async with session.get(url, timeout=10, headers={'User-Agent': UA}) as resp:
            if resp.status != 200:
                return None
            ctype = resp.headers.get('Content-Type', '')
            if 'html' not in ctype.lower():
                return None
            text = await resp.text()
            return html.fromstring(text)
    except Exception:
        return None

async def process_pdf_link(url: str) -> None:
    """
    Record a PDF URL if it passes relevance checks.
    """
    if not is_pdf_url(url):
        return
    if url in found_pdfs:
        return
    found_pdfs.add(url)

async def html_worker(html_session: aiohttp.ClientSession, pdf_session: aiohttp.ClientSession):
    pages_count = 0
    while queue and pages_count < MAX_PAGES:
        url, depth = queue.popleft()
        if url in visited_pages:
            continue
        visited_pages.add(url)
        pages_count += 1

        tree = await fetch_html(html_session, url)
        if tree is None:
            continue

        for a in tree.xpath('//a[@href]'):
            href = a.get('href').strip()
            full = urljoin(START_URL, href)
            p = urlparse(full)
            if DOMAIN not in p.netloc:
                continue

            link_text = ''.join(a.itertext()).strip()
            if is_pdf_url(full) and is_relevant_pdf(full, link_text):
                await process_pdf_link(full)
            elif depth < MAX_DEPTH and p.path.lower().endswith(('.html','/','')):
                if full not in visited_pages:
                    queue.append((full, depth+1))

async def main():
    html_conn = aiohttp.TCPConnector(limit_per_host=CONCURRENCY)
    pdf_conn  = aiohttp.TCPConnector(limit_per_host=PDF_CONCURRENCY)
    async with aiohttp.ClientSession(connector=html_conn) as html_sess, \
               aiohttp.ClientSession(connector=pdf_conn) as pdf_sess:
        workers = [asyncio.create_task(html_worker(html_sess, pdf_sess))
                   for _ in range(CONCURRENCY)]
        await asyncio.gather(*workers)

    os.makedirs(os.path.dirname(LINKS_FILE), exist_ok=True)
    with open(LINKS_FILE, 'w') as lf:
        for url in sorted(found_pdfs):
            lf.write(f"{url}\n")

    new_added = len(found_pdfs) - existing_count
    print(f"✔️ Total PDF links: {len(found_pdfs)}; {new_added} new appended; saved to {LINKS_FILE}")

if __name__ == '__main__':
    asyncio.run(main())
