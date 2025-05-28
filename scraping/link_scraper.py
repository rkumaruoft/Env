import os
import asyncio
import hashlib
import aiohttp
from lxml import html
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser
from collections import deque

from bloom_filter2 import BloomFilter

try:
    import nest_asyncio
    nest_asyncio.apply()
except ImportError:
    pass

# ─── Configurations ────────────────────────────────────────────────────────────
START_URL       = "https://www.toronto.ca/services-payments/water-environment/"
DOMAIN          = "toronto.ca"
MAX_PAGES       = 300
MAX_DEPTH       = 3
CONCURRENCY     = 10    # number of concurrent fetches for HTML
PDF_CONCURRENCY = 5     # concurrent hash operations for PDFs
UA              = "LinkFetcher/1.1"
TXT_OUTPUT      = "/set/your/output/directory/new_pdf_hashes.txt"  # list of new PDF hashes (and the original links)
HASH_TABLE_FILE = "/set/your/hash/directory/existing_hashes.txt"  # one SHA256 per line, set to an empty .txt for now
KEYWORDS        = ["Climate", "Adaptation", "Mitigation", "Emissions",
                   "LENZ", "PollinateTO", "Eco-Roof", "Green"] # keywords

# ─── Parse robots.txt ─────────────────────────────────────────────────────────
rp = RobotFileParser()
rp.set_url(urljoin(START_URL, "/robots.txt"))
rp.read()

# ─── Crawl state ─────────────────────────────────────────────────────────────
visited               = BloomFilter(max_elements=100000, error_rate=0.001)
queue                 = deque([(START_URL, 0)])
found_pdfs            = set()   # URLs of new relevant PDFs
found_hashes          = set()   # hashes of PDFs discovered this run
pages_visited_count   = 0       # simple counter for pages fetched

# ─── Load pre-existing hashes ─────────────────────────────────────────────────
local_hashes = set()
if os.path.isfile(HASH_TABLE_FILE):
    with open(HASH_TABLE_FILE, 'r') as hf:
        for line in hf:
            h = line.strip()
            if len(h) == 64:
                local_hashes.add(h)

# ─── Utility to detect PDF links and relevance by keywords ────────────────────
def is_pdf_url(url: str) -> bool:
    return url.lower().endswith('.pdf')

def is_relevant_pdf(url: str, text: str) -> bool:
    url_l = url.lower()
    txt_l = (text or '').lower()
    for kw in KEYWORDS:
        kl = kw.lower()
        if kl in url_l or kl in txt_l:
            return True
    return False

# ─── Async fetch & parse HTML pages ───────────────────────────────────────────
async def fetch_html(session: aiohttp.ClientSession, url: str):
    if not rp.can_fetch(UA, url):
        return None
    try:
        async with session.get(url, timeout=10, headers={'User-Agent': UA}) as resp:
            if resp.status != 200 or 'text/html' not in resp.headers.get('Content-Type', ''):
                return None
            text = await resp.text()
            return html.fromstring(text)
    except Exception:
        return None

# ─── Async stream & hash PDF without saving ───────────────────────────────────
async def process_pdf(session: aiohttp.ClientSession, url: str):
    try:
        async with session.get(url, timeout=30, headers={'User-Agent': UA}) as resp:
            if resp.status != 200 or 'application/pdf' not in resp.headers.get('Content-Type', ''):
                return
            hasher = hashlib.sha256()
            async for chunk in resp.content.iter_chunked(8192):
                hasher.update(chunk)
            sha = hasher.hexdigest()
            if sha not in local_hashes and sha not in found_hashes:
                found_hashes.add(sha)
                found_pdfs.add((url, sha))
    except Exception:
        return

# ─── Worker for crawling HTML ──────────────────────────────────────────────────
async def html_worker(html_session: aiohttp.ClientSession, pdf_session: aiohttp.ClientSession):
    global pages_visited_count
    while queue and pages_visited_count < MAX_PAGES:
        url, depth = queue.popleft()
        if url in visited:
            continue
        visited.add(url)
        pages_visited_count += 1

        tree = await fetch_html(html_session, url)
        if tree is None:
            continue

        for a in tree.xpath('//a[@href]'):
            href = a.get('href').strip()
            full = urljoin(START_URL, href)
            p = urlparse(full)
            if DOMAIN not in p.netloc:
                continue
            text = ''.join(a.itertext()).strip()
            if is_pdf_url(full) and is_relevant_pdf(full, text):
                asyncio.create_task(process_pdf(pdf_session, full))
            elif depth < MAX_DEPTH and p.path.lower().endswith(('.html', '/', '')):
                if full not in visited:
                    queue.append((full, depth + 1))

# ─── Main entrypoint ─────────────────────────────────────────────────────────
async def main():
    html_conn = aiohttp.TCPConnector(limit_per_host=CONCURRENCY)
    pdf_conn  = aiohttp.TCPConnector(limit_per_host=PDF_CONCURRENCY)
    async with aiohttp.ClientSession(connector=html_conn) as html_sess, \
               aiohttp.ClientSession(connector=pdf_conn) as pdf_sess:
        workers = [asyncio.create_task(html_worker(html_sess, pdf_sess))
                   for _ in range(CONCURRENCY)]
        await asyncio.gather(*workers)

    with open(TXT_OUTPUT, 'w') as f:
        for url, sha in sorted(found_pdfs):
            f.write(f"{sha}  {url}\n")
    print(f"✔️  Found {len(found_pdfs)} new PDF(s), hashes written to {TXT_OUTPUT}")

if __name__ == '__main__':
    asyncio.run(main())
