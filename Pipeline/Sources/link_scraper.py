import os
import asyncio
import aiohttp
from lxml import html  # for HTML parsing
import xml.etree.ElementTree as ET
from bloom_filter2 import BloomFilter  # pip install bloom-filter2
from urllib.robotparser import RobotFileParser
from urllib.parse import urljoin, urlparse
from collections import deque
from typing import Optional

"""
To use in main
import asyncio
from link_scraper import run_link_scraper

async def main():

    #Run the in-domain link crawler extractor (uses the same START_URL, LINKS_FILE, etc., 
    #  defined in link_scraper.py by default).
    print("Starting link_scraper…")
    await run_link_scraper()

    print("All scraping tasks finished.")

if __name__ == "__main__":
    asyncio.run(main())
"""
# Patch for nested event loops (Spyder/Jupyter)
try:
    import nest_asyncio  # pip install nest_asyncio
    nest_asyncio.apply()
except ImportError:
    pass

# ─── Configurations ────────────────────────────────────────────────────────────
START_URL       = "https://www.toronto.ca/services-payments/water-environment/"
DOMAIN          = "toronto.ca"
CONCURRENCY     = 10    # concurrent fetches for HTML pages
PDF_CONCURRENCY = 5     # concurrent PDF link processing
UA              = "LinkFetcher/1.2"
LINKS_FILE      = "/scraping/existing_pdf_links.txt"

KEYWORDS = [
    "Climate", "Adaptation", "Mitigation", "Emissions",
    "LENZ", "PollinateTO", "Eco-Roof", "Green",
    "Forestry", "TransformTO", "Waste", "Heat", "Cool",
    "Net Zero", "Net-zero"
]

# ─── In‐memory state ───────────────────────────────────────────────────────────
visited_pages = set()
found_pdfs     = set()


# ─── HELPERS ────────────────────────────────────────────────────────────────────

def is_pdf_url(url: str) -> bool:
    return url.lower().endswith(".pdf")

def is_relevant_pdf(url: str, text: str) -> bool:
    """
    After fetching a PDF link, you could do extra checks here (e.g. Content-Type, headers).
    By default, we accept any PDF that matches KEYWORDS in URL or link text.
    """
    lower_u = url.lower()
    lower_t = text.lower()
    return any(kw.lower() in lower_u or kw.lower() in lower_t for kw in KEYWORDS)

async def fetch_html(session: aiohttp.ClientSession, url: str) -> Optional[str]:
    try:
        async with session.get(url, timeout=10, headers={'User-Agent': UA}) as resp:
            resp.raise_for_status()
            return await resp.text()
    except Exception:
        return None

async def process_pdf_link(url: str, link_text: str) -> None:
    """
    Called once per PDF link discovered.
    Only add to found_pdfs if it passes `is_relevant_pdf`.
    """
    if is_relevant_pdf(url, link_text):
        found_pdfs.add(url)


# ─── ASYNC ENTRY POINT ──────────────────────────────────────────────────────────

async def run_link_scraper(
    start_url: str = START_URL,
    domain: str    = DOMAIN,
    links_file: str = LINKS_FILE,
    concurrency: int = CONCURRENCY,
    pdf_concurrency: int = PDF_CONCURRENCY,
) -> None:
    """
    1) Load any existing PDF links from `links_file` into Bloom + found_pdfs.
    2) Begin crawling from `start_url` (BFS/DFS in‐domain),
       respecting robots.txt, extracting <a href="..."> links.
    3) If a link ends in .pdf and matches KEYWORDS, add to found_pdfs.
    4) After crawling completes, overwrite `links_file` with the merged set.
    """
    # ─── 1) Initialize BloomFilter from existing links ────────────────────────────
    if os.path.isfile(links_file):
        with open(links_file, "r", encoding="utf-8") as lf:
            for line in lf:
                link = line.strip()
                if link:
                    visited_pages.add(link)
                    found_pdfs.add(link)
    existing_count = len(found_pdfs)

    bloom = BloomFilter(max_elements=200000, error_rate=0.001)
    for u in visited_pages:
        bloom.add(u)

    # ─── 2) Initialize BFS queue with start_url ──────────────────────────────────
    queue = deque([(start_url, 0)])  # (url, depth), if you want depth‐limiting later
    visited_pages.add(start_url)

    sem_html = asyncio.Semaphore(concurrency)
    sem_pdf  = asyncio.Semaphore(pdf_concurrency)

    connector_html = aiohttp.TCPConnector(limit_per_host=concurrency)
    timeout_html   = aiohttp.ClientTimeout(total=60)

    async def html_worker(html_sess: aiohttp.ClientSession, pdf_sess: aiohttp.ClientSession):
        while queue:
            page_url, depth = queue.popleft()

            # Respect robots.txt
            rp = RobotFileParser()
            parsed = urlparse(page_url)
            robots_txt = urljoin(f"{parsed.scheme}://{parsed.netloc}", "/robots.txt")
            try:
                rp.set_url(robots_txt)
                rp.read()
            except Exception:
                pass

            if not rp.can_fetch("*", page_url):
                continue

            async with sem_html:
                html_text = await fetch_html(html_sess, page_url)
            if not html_text:
                continue

            tree = html.fromstring(html_text)
            for anchor in tree.xpath("//a[@href]"):
                href = anchor.get("href").strip()
                full_url = urljoin(page_url, href)
                link_text = anchor.text_content().strip()

                #  a) If it’s in‐domain HTML & not visited, enqueue it
                if full_url.startswith(f"https://{domain}") and full_url not in visited_pages:
                    visited_pages.add(full_url)
                    queue.append((full_url, depth + 1))

                #  b) If it’s a PDF & not in Bloom, process it
                if is_pdf_url(full_url) and (full_url not in bloom):
                    bloom.add(full_url)
                    await process_pdf_link(full_url, link_text)

    # ─── Launch worker tasks ───────────────────────────────────────────────────────
    async with aiohttp.ClientSession(connector=connector_html, timeout=timeout_html) as html_sess:
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit_per_host=pdf_concurrency)) as pdf_sess:
            tasks = [
                asyncio.create_task(html_worker(html_sess, pdf_sess))
                for _ in range(concurrency)
            ]
            await asyncio.gather(*tasks)

    # ─── 3) Write merged set of PDF links back to disk ────────────────────────────
    os.makedirs(os.path.dirname(links_file), exist_ok=True)
    with open(links_file, "w", encoding="utf-8") as lf:
        for url in sorted(found_pdfs):
            lf.write(f"{url}\n")

    new_added = len(found_pdfs) - existing_count
    print(f"✔️ Total PDF links: {len(found_pdfs)}; {new_added} new appended; saved to {links_file}")
