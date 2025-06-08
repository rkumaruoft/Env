# doi_link_to_text.py

import os
import aiohttp
import asyncio
import ssl
import certifi
from bs4 import BeautifulSoup

from API_class import APIConfig, fetch_api_results, extract_top_entries, scopus_config

USER_AGENT = "Mozilla/5.0"
SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
OUTPUT_DIR = "./scraping/article_texts"
DOI_LOG_PATH = os.path.join(OUTPUT_DIR, "doi_list.txt")

os.makedirs(OUTPUT_DIR, exist_ok=True)

def load_processed_dois() -> set:
    if not os.path.exists(DOI_LOG_PATH):
        return set()
    with open(DOI_LOG_PATH, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())

def log_doi(doi: str):
    with open(DOI_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"{doi}\n")

async def resolve_doi(doi_url: str) -> str:
    try:
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=SSL_CONTEXT),
                                         headers={"User-Agent": USER_AGENT}) as session:
            async with session.get(doi_url, allow_redirects=True, timeout=10) as response:
                return str(response.url)
    except Exception as e:
        print(f"[ERROR] DOI resolution failed: {e}")
        return ""

async def fetch_html(session: aiohttp.ClientSession, url: str) -> str:
    try:
        async with session.get(url, timeout=10) as response:
            if response.status == 200 and "text/html" in response.headers.get("Content-Type", ""):
                return await response.text()
    except Exception as e:
        print(f"[ERROR] HTML fetch failed: {e}")
    return ""

async def extract_and_save_text(doi_link: str, processed_dois: set):
    if doi_link in processed_dois:
        print(f"[SKIP] Already processed: {doi_link}")
        return

    resolved_url = await resolve_doi(doi_link)
    if not resolved_url:
        return

    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=SSL_CONTEXT),
                                     headers={"User-Agent": USER_AGENT}) as session:
        html = await fetch_html(session, resolved_url)
        if not html:
            return

        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(separator="\n", strip=True)

        filename = doi_link.replace("/", "_").replace(":", "_") + ".txt"
        output_path = os.path.join(OUTPUT_DIR, filename)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(text)

        log_doi(doi_link)
        print(f"[OK] Saved: {filename}")

async def main(query: str, config: APIConfig, limit: int = 25):
    data = fetch_api_results(query, config)
    doi_list = config.doi_extractor(data)[:limit]
    processed_dois = load_processed_dois()

    tasks = [extract_and_save_text(doi, processed_dois) for doi in doi_list]
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main("Toronto AND climate change", scopus_config))
