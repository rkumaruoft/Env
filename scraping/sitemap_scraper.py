import os
import asyncio
import hashlib
import aiohttp
import xml.etree.ElementTree as ET
from bloom_filter2 import BloomFilter  # pip install bloom-filter2
from urllib.robotparser import RobotFileParser
from urllib.parse import urljoin
from typing import Optional, List

try:
    import nest_asyncio  # pip install nest_asyncio
    nest_asyncio.apply()
except ImportError:
    pass

# ─── Configurations ────────────────────────────────────────────────────────────
START_SITEMAP    = "https://www.toronto.ca/sitemap.xml"
DOMAIN           = "toronto.ca"
CONCURRENCY      = 10    # concurrent HTML page fetches
PDF_CONCURRENCY  = 5     # concurrent PDF hash operations
UA               = "LinkFetcher/1.5"
TXT_OUTPUT       = "/your/directory/here/new_pdf_hashes4.txt"
HASH_TABLE_FILE  = "/your/directory/here/existing_hashes.txt"
# Keywords used to filter which page URLs to process for PDF links
KEYWORDS         = [
    "Climate", "Adaptation", "Mitigation", "Emissions",
    "LENZ", "PollinateTO", "Eco-Roof", "Green",
    "Forestry", "TransformTO", "Waste"
]

# ─── Politeness via robots.txt ──────────────────────────────────────────────────
rp = RobotFileParser()
rp.set_url("https://www.toronto.ca/robots.txt")
rp.read()

# ─── In-memory state ───────────────────────────────────────────────────────────
visited_pages = BloomFilter(max_elements=200000, error_rate=0.001)
local_hashes  = set()
found_hashes  = set()
found_pdfs    = []  # list of (url, sha)

# ─── Load existing hashes ───────────────────────────────────────────────────────
if os.path.isfile(HASH_TABLE_FILE):
    with open(HASH_TABLE_FILE, 'r') as hf:
        for line in hf:
            h = line.strip()
            if len(h) == 64:
                local_hashes.add(h)

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

async def hash_pdf(session: aiohttp.ClientSession, url: str) -> None:
    """
    Stream a PDF and compute its SHA256; record if it's new.
    """
    if not is_pdf_url(url) or not is_relevant_url(url):
        return
    if url in (u for u, _ in found_pdfs):
        return
    if not rp.can_fetch(UA, url):
        return
    try:
        async with session.get(url, headers={'User-Agent': UA}, timeout=30) as resp:
            if resp.status != 200:
                return
            ctype = resp.headers.get('Content-Type', '')
            if 'pdf' not in ctype.lower():
                return
            hasher = hashlib.sha256()
            async for chunk in resp.content.iter_chunked(8192):
                hasher.update(chunk)
            sha = hasher.hexdigest()
            if sha not in local_hashes and sha not in found_hashes:
                found_hashes.add(sha)
                found_pdfs.append((url, sha))
    except Exception:
        return

async def main() -> None:
    # 1) collect all URLs from sitemap
    async with aiohttp.ClientSession() as session:
        all_urls = await collect_sitemap_urls(session, START_SITEMAP)

    # 2) filter to relevant page URLs (non-PDF HTML pages)
    page_urls = [u for u in all_urls
                 if not is_pdf_url(u) and is_relevant_url(u)]

    # 3) for each page, fetch HTML and find PDF links
    sem_pdf = asyncio.Semaphore(PDF_CONCURRENCY)
    async with aiohttp.ClientSession() as session:
        tasks = []
        for page in page_urls:
            if page in visited_pages:
                continue
            visited_pages.add(page)
            tasks.append(asyncio.create_task(hash_pdfs_from_page(session, page, sem_pdf)))
        await asyncio.gather(*tasks)

    # 4) write new PDF hashes
    os.makedirs(os.path.dirname(TXT_OUTPUT), exist_ok=True)
    with open(TXT_OUTPUT, 'w') as f:
        for url, sha in sorted(found_pdfs, key=lambda x: x[0]):
            f.write(f"{sha}  {url}\n")
    print(f"✔️ Found {len(found_pdfs)} new PDF(s); hashes in {TXT_OUTPUT}")

async def hash_pdfs_from_page(session: aiohttp.ClientSession, page_url: str, sem_pdf: asyncio.Semaphore) -> None:
    """
    Fetch an HTML page, parse for PDF links, and hash them.
    """
    if not rp.can_fetch(UA, page_url):
        return
    try:
        async with session.get(page_url, headers={'User-Agent': UA}, timeout=10) as resp:
            if resp.status != 200:
                return
            text = await resp.text()
    except Exception:
        return
    from lxml import html as LH
    tree = LH.fromstring(text)
    links = tree.xpath('//a[@href]')
    for a in links:
        href = a.get('href').strip()
        pdf_url = urljoin(page_url, href)
        if is_pdf_url(pdf_url):
            async with sem_pdf:
                await hash_pdf(session, pdf_url)

if __name__ == '__main__':
    asyncio.run(main())
