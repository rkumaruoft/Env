import os
import asyncio
import aiohttp
import xml.etree.ElementTree as ET
from bloom_filter2 import BloomFilter  # pip install bloom-filter2
from urllib.robotparser import RobotFileParser
from urllib.parse import urljoin
from typing import Optional, List

# Patch for nested event loops (Spyder/Jupyter)
try:
    import nest_asyncio  # pip install nest_asyncio

    nest_asyncio.apply()
except ImportError:
    pass

# ─── Configurations ────────────────────────────────────────────────────────────
START_SITEMAP = "https://www.toronto.ca/sitemap.xml"
DOMAIN = "toronto.ca"
CONCURRENCY = 10  # concurrent HTML page fetches
PDF_CONCURRENCY = 5  # concurrent PDF link processing
UA = "Sitemap_Scraper/1.2"
LINKS_FILE = "/scraping/existing_pdf_links.txt"
# Keywords used to filter which page URLs to process for PDF links
KEYWORDS = [
    "Climate", "Adaptation", "Mitigation", "Emissions",
    "LENZ", "PollinateTO", "Eco-Roof", "Green",
    "Forestry", "TransformTO", "Waste", "Heat", "Cool",
    "Net Zero", "Net-zero"
]

# ─── Politeness via robots.txt ──────────────────────────────────────────────────
rp = RobotFileParser()
rp.set_url("https://www.toronto.ca/robots.txt")
rp.read()

# ─── In-memory state ───────────────────────────────────────────────────────────
visited_pages = BloomFilter(max_elements=200000, error_rate=0.001)
found_pdfs = set()

# ─── Load existing links ────────────────────────────────────────────────────────
if os.path.isfile(LINKS_FILE):
    with open(LINKS_FILE, 'r') as lf:
        for line in lf:
            link = line.strip()
            if link:
                found_pdfs.add(link)
existing_count = len(found_pdfs)  # track how many were present before crawling


# ─── Helpers ─────────────────────────────────────────────────────────────────────
def is_pdf_url(url: str) -> bool:
    return url.lower().endswith('.pdf')


def is_relevant_url(url: str) -> bool:
    low = url.lower()
    return any(kw.lower() in low for kw in KEYWORDS)


async def fetch_xml(session: aiohttp.ClientSession, url: str) -> Optional[ET.Element]:
    if not rp.can_fetch(UA, url):
        return None
    try:
        async with session.get(url, headers={'User-Agent': UA}, timeout=15) as resp:
            if resp.status != 200:
                return None
            text = await resp.text()
            return ET.fromstring(text)
    except Exception:
        return None


async def collect_sitemap_urls(session: aiohttp.ClientSession, sitemap_url: str) -> List[str]:
    """
    Recursively fetch all <loc> URLs from sitemap index and urlset.
    """
    root = await fetch_xml(session, sitemap_url)
    if root is None:
        return []
    ns = {'ns': root.tag.split('}')[0].strip('{')}
    urls: List[str] = []
    if root.tag.endswith('sitemapindex'):
        for loc in root.findall('ns:sitemap/ns:loc', ns):
            child = loc.text.strip()
            urls += await collect_sitemap_urls(session, child)
    elif root.tag.endswith('urlset'):
        for loc in root.findall('ns:url/ns:loc', ns):
            urls.append(loc.text.strip())
    return urls


async def process_pdf_link(url: str) -> None:
    """
    Record a PDF URL if it passes relevance checks.
    """
    if not is_pdf_url(url) or not is_relevant_url(url):
        return
    if url in found_pdfs:
        return
    found_pdfs.add(url)


async def main() -> None:
    # 1) collect all URLs from sitemap
    async with aiohttp.ClientSession() as session:
        all_urls = await collect_sitemap_urls(session, START_SITEMAP)

    # 2) filter to relevant page URLs (non-PDF HTML pages)
    page_urls = [u for u in all_urls if not is_pdf_url(u) and is_relevant_url(u)]

    # 3) for each page, fetch HTML and find PDF links
    sem_pdf = asyncio.Semaphore(PDF_CONCURRENCY)
    async with aiohttp.ClientSession() as session:
        from lxml import html as LH
        for page in page_urls:
            if page in visited_pages:
                continue
            visited_pages.add(page)
            try:
                async with session.get(page, headers={'User-Agent': UA}, timeout=10) as resp:
                    if resp.status != 200:
                        continue
                    content = await resp.text()
            except Exception:
                continue
            tree = LH.fromstring(content)
            for a in tree.xpath('//a[@href]'):
                href = a.get('href').strip()
                pdf_url = urljoin(page, href)
                async with sem_pdf:
                    await process_pdf_link(pdf_url)

    # 4) write updated links back to file
    os.makedirs(os.path.dirname(LINKS_FILE), exist_ok=True)
    with open(LINKS_FILE, 'w') as lf:
        for url in sorted(found_pdfs):
            lf.write(f"{url}\n")

    new_count = len(found_pdfs) - existing_count
    print(f"✔️ Total PDF links: {len(found_pdfs)}; {new_count} new appended; saved to {LINKS_FILE}")


if __name__ == '__main__':
    asyncio.run(main())
