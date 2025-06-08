import os
import aiohttp
import asyncio
import ssl
import certifi
from urllib.parse import urlparse
from bs4 import BeautifulSoup

from Science_direct_get_links import APIConfig, fetch_api_results, extract_top_entries  # You'll create/import this
from Science_direct_get_links import scopus_config  # Scopus-specific config with entry parser and doi_extractor

# Config
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
OUTPUT_DIR = "./scraping/article_texts"
SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())

# Ensure output directory exists
os.makedirs(OUTPUT_DIR, exist_ok=True)

DOI_LOG_PATH = os.path.join(OUTPUT_DIR, "doi_list.txt")

def load_processed_dois() -> set:
    if not os.path.exists(DOI_LOG_PATH):
        return set()
    with open(DOI_LOG_PATH, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())

def log_doi(doi: str):
    with open(DOI_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"{doi}\n")


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


async def extract_and_save_text(doi_link: str, processed_dois: set):
    """Resolve a DOI, fetch HTML, extract visible text, and save it to a .txt file."""
    if doi_link in processed_dois:
        print(f"[⏩] Skipping already processed DOI: {doi_link}")
        return

    resolved_url = await resolve_doi(doi_link)
    if not resolved_url:
        return

    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=SSL_CONTEXT),
                                     headers={"User-Agent": USER_AGENT}) as session:
        html = await fetch_html(session, resolved_url)
        if not html:
            print("[❌] Could not fetch publisher HTML.")
            return

        soup = BeautifulSoup(html, "html.parser")
        visible_text = soup.get_text(separator="\n", strip=True)

        # Make filename safe and unique
        safe_filename = doi_link.replace("/", "_").replace(":", "_") + ".txt"
        output_path = os.path.join(OUTPUT_DIR, safe_filename)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(visible_text)

        log_doi(doi_link)
        print(f"[📝] Text extracted and saved to: {safe_filename}")


async def main():
    query = "Toronto + climate change"
    data = fetch_api_results(query, scopus_config)
    doi_list = scopus_config.doi_extractor(data)

    processed_dois = load_processed_dois()

    tasks = []
    for i, doi in enumerate(doi_list):
        if i >= 25:
            break
        tasks.append(extract_and_save_text(doi, processed_dois))

    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
