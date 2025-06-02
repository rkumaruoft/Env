import os
import aiohttp
import asyncio
import ssl
import certifi
from urllib.parse import urlparse
from bs4 import BeautifulSoup
import requests
from Science_direct_get_links import fetch_scopus_results, extract_top_entries, extract_doi_list

# Config
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
OUTPUT_DIR = "./scraping/downloaded_pdfs"
SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())

# Ensure output directory exists
os.makedirs(OUTPUT_DIR, exist_ok=True)

async def resolve_doi(doi_url: str) -> str:
    """Resolve a DOI to its destination publisher URL."""
    try:
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=SSL_CONTEXT),
                                         headers={"User-Agent": USER_AGENT}) as session:
            async with session.get(doi_url, allow_redirects=True, timeout=10) as response:
                final_url = str(response.url)
                print(f"[→] DOI resolved to: {final_url}")
                return final_url
    except Exception as e:
        print(f"[ERROR] DOI resolution failed: {e}")
        return ""

async def fetch_html(session: aiohttp.ClientSession, url: str) -> str:
    """Fetch HTML content from a URL."""
    try:
        async with session.get(url, timeout=10) as response:
            if response.status == 200 and "text/html" in response.headers.get("Content-Type", ""):
                return await response.text()
    except Exception as e:
        print(f"[ERROR] Fetching HTML: {e}")
    return ""

def extract_pdf_link(html: str, base_url: str) -> str:
    """Try to find a PDF link in the HTML."""
    soup = BeautifulSoup(html, "html.parser")
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if ".pdf" in href:
            if href.startswith("/"):
                return base_url.split("/")[0] + "//" + urlparse(base_url).hostname + href
            elif href.startswith("http"):
                return href
    return ""

async def download_pdf(pdf_url: str, output_dir: str) -> bool:
    """Download a PDF file from a URL."""
    try:
        filename = os.path.basename(urlparse(pdf_url).path)
        output_path = os.path.join(output_dir, filename)

        if os.path.exists(output_path):
            print(f"[SKIP] Already exists: {filename}")
            return False

        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=SSL_CONTEXT),
                                         headers={"User-Agent": USER_AGENT}) as session:
            async with session.get(pdf_url, timeout=15) as response:
                if response.status == 200:
                    with open(output_path, "wb") as f:
                        f.write(await response.read())
                    print(f"[✔️] Downloaded: {filename}")
                    return True
                else:
                    print(f"[❌] PDF fetch failed with status {response.status}")
    except Exception as e:
        print(f"[ERROR] Downloading PDF: {e}")
    return False

async def main(doi_link: str):
    resolved_url = await resolve_doi(doi_link)
    if not resolved_url:
        return

    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=SSL_CONTEXT),
                                     headers={"User-Agent": USER_AGENT}) as session:
        html = await fetch_html(session, resolved_url)
        if not html:
            print("[❌] Could not fetch publisher HTML.")
            return

        pdf_url = extract_pdf_link(html, resolved_url)
        if not pdf_url:
            print("[❌] No PDF link found on the page.")
            return

        await download_pdf(pdf_url, OUTPUT_DIR)

if __name__ == "__main__":
    # EXAMPLE DOI — change this to any valid DOI link
    query = "Toronto climate change"
    data = fetch_scopus_results(query)
    top_entries = extract_top_entries(data)
    doi_list = extract_doi_list(data)
    i = 0
    for doi in doi_list:
        asyncio.run(main(doi))
        if i == 5:
            break