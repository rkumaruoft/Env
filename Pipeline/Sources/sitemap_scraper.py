import os
import asyncio
import aiohttp
import xml.etree.ElementTree as ET
from bloom_filter2 import BloomFilter  # pip install bloom-filter2
from urllib.robotparser import RobotFileParser
from urllib.parse import urljoin
from typing import Optional, List

"""
To run in main

import asyncio
from sitemap_scraper import run_sitemap_scraper
from link_scraper import run_link_scraper

async def main():
    # Run the sitemap‐based extractor (uses the same START_SITEMAP, LINKS_FILE, etc., 
    #    defined in sitemap_scraper.py by default).
    print("Starting sitemap_scraper…")
    await run_sitemap_scraper()
    
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
START_SITEMAP   = "https://www.toronto.ca/sitemap.xml"
DOMAIN          = "toronto.ca"
CONCURRENCY     = 10  # concurrent HTML page fetches
PDF_CONCURRENCY = 5   # concurrent PDF link processing
UA              = "Sitemap_Scraper/1.2"
LINKS_FILE      = "/scraping/existing_pdf_links.txt"

# Keywords used to filter which page URLs to process for PDF links
KEYWORDS = [
    "Climate", "Adaptation", "Mitigation", "Emissions",
    "LENZ", "PollinateTO", "Eco-Roof", "Green",
    "Forestry", "TransformTO", "Waste", "Heat", "Cool",
    "Net Zero", "Net-zero"
]

# ─── In‐memory state ───────────────────────────────────────────────────────────
visited_pages = BloomFilter(max_elements=200000, error_rate=0.001)
found_pdfs     = set()

# ─── HELPERS ────────────────────────────────────────────────────────────────────

def is_pdf_url(url: str) -> bool:
    return url.lower().endswith(".pdf")

def is_relevant_url(url: str) -> bool:
    lower = url.lower()
    # Only process pages that mention one of the KEYWORDS (case‐insensitive)
    if not any(kw.lower() in lower for kw in KEYWORDS):
        return False
    # And skip anything outside our domain or obviously unwanted
    return DOMAIN in url and "mailto:" not in url

async def fetch_xml(session: aiohttp.ClientSession, url: str) -> Optional[ET.Element]:
    try:
        async with session.get(url, timeout=30, headers={"User-Agent": UA}) as resp:
            resp.raise_for_status()
            text = await resp.text()
            return ET.fromstring(text)
    except Exception:
        return None

async def collect_sitemap_urls(session: aiohttp.ClientSession, sitemap_url: str) -> List[str]:
    """
    Recursively fetch <sitemapindex> and <urlset> entries from a given sitemap URL.
    Returns a flat list of all URLs (both sub‐sitemaps and page links).
    """
    root = await fetch_xml(session, sitemap_url)
    if root is None:
        return []

    namespace = {"ns": root.tag.split("}")[0].strip("{")} if "}" in root.tag else {}
    urls: List[str] = []

    # If this is a <sitemapindex> (list of other sitemaps):
    for sitemap in root.findall(".//ns:sitemap", namespaces=namespace):
        loc = sitemap.find("ns:loc", namespaces=namespace)
        if loc is not None and loc.text:
            urls.extend(await collect_sitemap_urls(session, loc.text.strip()))

    # If this is a <urlset> (list of page URLs):
    for url_elem in root.findall(".//ns:url", namespaces=namespace):
        loc = url_elem.find("ns:loc", namespaces=namespace)
        if loc is not None and loc.text:
            urls.append(loc.text.strip())

    return urls

async def process_pdf_link(url: str) -> None:
    """
    Called once per PDF link found. Here you could download or validate it.
    In this example, it simply adds to a global set;
    you could expand it (e.g. check HEAD, verify content‐type, etc.).
    """
    found_pdfs.add(url)

# ─── ASYNC ENTRY POINT ──────────────────────────────────────────────────────────

async def run_sitemap_scraper(
    start_sitemap: str = START_SITEMAP,
    links_file: str    = LINKS_FILE,
    concurrency: int   = CONCURRENCY,
    pdf_concurrency: int = PDF_CONCURRENCY,
) -> None:
    """
    1) Load any existing PDF links from `links_file` into Bloom + found_pdfs.
    2) Recursively crawl `start_sitemap` (and nested sitemaps) to get every page URL.
    3) Filter those URLs by `is_relevant_url` and skip PDFs here.
    4) For each relevant page, fetch HTML, extract <a href="..."> that end in .pdf.
       If not in Bloom, add to Bloom + found_pdfs.
    5) After crawling, overwrite `links_file` with the merged set of all found_pdfs.
    """
    # ─── 1) Load existing links into BloomFilter ────────────────────────────────
    if os.path.isfile(links_file):
        with open(links_file, "r", encoding="utf-8") as lf:
            for line in lf:
                link = line.strip()
                if link:
                    visited_pages.add(link)
                    found_pdfs.add(link)
    existing_count = len(found_pdfs)

    # ─── 2) Recursively collect all URLs from sitemap and its children ───────────
    connector_xml = aiohttp.TCPConnector(limit_per_host=concurrency)
    timeout_xml   = aiohttp.ClientTimeout(total=60)
    async with aiohttp.ClientSession(connector=connector_xml, timeout=timeout_xml) as xml_sess:
        all_urls = await collect_sitemap_urls(xml_sess, start_sitemap)

    # ─── 3) Filter to relevant page URLs (non-PDF HTML pages) ──────────────────
    page_urls = [
        u for u in all_urls
        if (not is_pdf_url(u)) and is_relevant_url(u)
    ]

    # ─── 4) Concurrently fetch each page HTML + extract PDF links ──────────────
    async def html_worker(html_sess: aiohttp.ClientSession):
        while page_urls:
            page_url = page_urls.pop()
            # Respect robots.txt
            rp = RobotFileParser()
            rp.set_url(urljoin(f"https://{DOMAIN}", "/robots.txt"))
            try:
                rp.read()
            except Exception:
                pass
            if not rp.can_fetch("*", page_url):
                continue

            try:
                async with html_sess.get(page_url, timeout=30, headers={"User-Agent": UA}) as resp:
                    resp.raise_for_status()
                    body = await resp.text()
            except Exception:
                continue

            from lxml import html as LH  # ensure HTML parsing
            tree = LH.fromstring(body)
            for anchor in tree.xpath("//a[@href]"):
                href = anchor.get("href").strip()
                full_url = urljoin(page_url, href)
                if is_pdf_url(full_url) and (full_url not in visited_pages):
                    visited_pages.add(full_url)
                    await process_pdf_link(full_url)

    sem_html = asyncio.Semaphore(concurrency)
    conn_html = aiohttp.TCPConnector(limit_per_host=concurrency)
    async with aiohttp.ClientSession(connector=conn_html) as html_sess:
        workers = [
            asyncio.create_task(html_worker(html_sess))
            for _ in range(concurrency)
        ]
        await asyncio.gather(*workers)

    # ─── 5) Write merged set of PDF links back to disk ─────────────────────────
    os.makedirs(os.path.dirname(links_file), exist_ok=True)
    with open(links_file, "w", encoding="utf-8") as lf:
        for url in sorted(found_pdfs):
            lf.write(f"{url}\n")

    new_count = len(found_pdfs) - existing_count
    print(f"✔️ Total PDF links: {len(found_pdfs)}; {new_count} new appended; saved to {links_file}")
