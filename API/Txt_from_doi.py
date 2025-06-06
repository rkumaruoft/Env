import os
import aiohttp
import asyncio
import ssl
import certifi
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from Science_direct_get_links import fetch_scopus_results, extract_top_entries, extract_doi_list

# Config
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
OUTPUT_DIR = "./scraping/article_texts"
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

async def extract_and_save_text(doi_link: str):
    """Resolve a DOI, fetch HTML, extract visible text, and save it to a .txt file."""
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

        print(f"[📝] Text extracted and saved to: {safe_filename}")

async def main():
    # EXAMPLE: Get list of DOIs using your existing methods
    query = "Toronto climate change"
    data = fetch_scopus_results(query)
    doi_list = extract_doi_list(data)

    tasks = []
    for i, doi in enumerate(doi_list):
        if i >= 25:  # Limit for testing — remove or change as needed
            break
        tasks.append(extract_and_save_text(doi))

    await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())
