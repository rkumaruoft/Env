import os
import aiohttp
import asyncio
import ssl
import certifi
from urllib.parse import urlparse
from bs4 import BeautifulSoup

from API_class import (
    fetch_api_results,
    extract_top_entries,
    print_entries,
    print_doi_list,
    scopus_config  # APIConfig instance
)

# Config
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
OUTPUT_FILE = "API_PDF_links.txt"
SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())

async def resolve_doi(doi_url: str) -> str:
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
    try:
        async with session.get(url, timeout=10) as response:
            if response.status == 200 and "text/html" in response.headers.get("Content-Type", ""):
                return await response.text()
    except Exception as e:
        print(f"[ERROR] Fetching HTML: {e}")
    return ""

def extract_pdf_link(html: str, base_url: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if ".pdf" in href.lower():
            if href.startswith("/"):
                return base_url.split("/")[0] + "//" + urlparse(base_url).hostname + href
            elif href.startswith("http"):
                return href
    return ""

async def process_doi(doi_url: str) -> str:
    resolved_url = await resolve_doi(doi_url)
    if not resolved_url:
        return ""

    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=SSL_CONTEXT),
                                     headers={"User-Agent": USER_AGENT}) as session:
        html = await fetch_html(session, resolved_url)
        if not html:
            return ""

        pdf_url = extract_pdf_link(html, resolved_url)
        if pdf_url:
            print(f"[✔️] Found PDF link: {pdf_url}")
        else:
            print("[❌] No PDF link found.")
        return pdf_url

async def main():
    query = input("Enter your search query for Scopus: ").strip()
    doi_list = fetch_api_results(query, scopus_config, max_results=250)

    if len(doi_list) < 250:
        print(f"\n[⚠️] Only {len(doi_list)} DOIs found (less than 250). No more results available.")

    # Process DOIs and collect PDF links
    pdf_links = []
    for i, doi in enumerate(doi_list):
        pdf_url = await process_doi(doi)
        if pdf_url:
            pdf_links.append(pdf_url)


    # Save to file
    with open(OUTPUT_FILE, "w") as f:
        for link in pdf_links:
            f.write(link + "\n")

    print(f"\n[📄] PDF links saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    asyncio.run(main())
