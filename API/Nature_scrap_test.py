import os
import aiohttp
import asyncio
from aiohttp import ClientSession
from urllib.parse import urlparse
from bs4 import BeautifulSoup
import ssl
import certifi

# Configuration
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
START_URL = "https://www.nature.com/articles/s41598-025-90169-y"
OUTPUT_DIR = "./scraping/downloaded_pdfs"
EXISTING_LINKS_FILE = "./scraping/existing_pdf_links.txt"
CONCURRENCY = 5
PDF_CONCURRENCY = 2
VALID_EXTENSIONS = (".pdf",)

# Global set of seen links
seen_links = set()

# Ensure output and tracking directories exist
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(os.path.dirname(EXISTING_LINKS_FILE), exist_ok=True)

# Load existing links
if os.path.exists(EXISTING_LINKS_FILE):
    with open(EXISTING_LINKS_FILE, "r") as f:
        seen_links = set(line.strip() for line in f if line.strip())

# SSL context fix using certifi
ssl_context = ssl.create_default_context(cafile=certifi.where())

async def fetch_html(session: ClientSession, url: str) -> str:
    try:
        async with session.get(url, timeout=10) as response:
            if response.status == 200 and 'text/html' in response.headers.get("Content-Type", ""):
                return await response.text()
    except Exception as e:
        print(f"[ERROR] Fetching {url}: {e}")
    return ""

def extract_links(html: str, base_url: str) -> list:
    soup = BeautifulSoup(html, "html.parser")
    links = []

    for tag in soup.find_all("a", href=True):
        href = tag["href"]
        if href.startswith("/"):
            href = urlparse(base_url)._replace(path=href, query="", fragment="").geturl()
        elif not href.startswith("http"):
            continue
        if any(href.lower().endswith(ext) for ext in VALID_EXTENSIONS):
            links.append(href)
    return links

async def download_pdf(session: ClientSession, url: str, output_dir: str) -> bool:
    try:
        filename = os.path.basename(urlparse(url).path)
        output_path = os.path.join(output_dir, filename)

        if os.path.exists(output_path):
            print(f"[SKIP] Already exists: {filename}")
            return False

        async with session.get(url, timeout=15) as response:
            if response.status == 200:
                with open(output_path, "wb") as f:
                    f.write(await response.read())
                print(f"[✔️] Downloaded: {filename}")
                return True
    except Exception as e:
        print(f"[ERROR] Downloading {url}: {e}")
    return False

async def crawl_for_pdfs(start_url: str):
    new_links = set()

    html_conn = aiohttp.TCPConnector(limit_per_host=CONCURRENCY, ssl=ssl_context)
    pdf_conn = aiohttp.TCPConnector(limit_per_host=PDF_CONCURRENCY, ssl=ssl_context)

    async with ClientSession(connector=html_conn, headers={"User-Agent": USER_AGENT}) as html_session:
        html = await fetch_html(html_session, start_url)
        if not html:
            print(f"[❌] Could not fetch HTML from {start_url}")
            return

        links = extract_links(html, base_url=start_url)
        new_links = {link for link in links if link not in seen_links}

    print(f"✔️ Total PDF links: {len(links)}; {len(new_links)} new added; saved to {EXISTING_LINKS_FILE}")

    if new_links:
        async with ClientSession(connector=pdf_conn, headers={"User-Agent": USER_AGENT}) as pdf_session:
            tasks = [download_pdf(pdf_session, url, OUTPUT_DIR) for url in new_links]
            results = await asyncio.gather(*tasks)

        downloaded_links = [link for link, success in zip(new_links, results) if success]
        seen_links.update(downloaded_links)
        with open(EXISTING_LINKS_FILE, "a") as f:
            for link in downloaded_links:
                f.write(link + "\n")

if __name__ == "__main__":
    asyncio.run(crawl_for_pdfs(START_URL))