import re
import os
import ssl
import certifi
import asyncio
import aiohttp
from typing import List
from urllib.parse import urlparse
from bs4 import BeautifulSoup

from Pipeline.database.DB_funcs import ClimateDB
#from Pipeline.Sources.API_class import fetch_api_results, scopus_config

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
OUTPUT_FILE = "API_PDF_links.txt"

class PDF_through_API:
    def __init__(self, db_path: str = "../database/climate_docs.db"):
        self.db = ClimateDB(db_path)

    async def resolve_doi(self, doi_url: str) -> str:
        try:
            async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=SSL_CONTEXT),
                                             headers={"User-Agent": USER_AGENT}) as session:
                async with session.get(doi_url, allow_redirects=True, timeout=10) as response:
                    return str(response.url)
        except Exception as e:
            print(f"[ERROR] DOI resolution failed: {e}")
            return ""


    async def fetch_html(self, session: aiohttp.ClientSession, url: str) -> str:
        try:
            async with session.get(url, timeout=10) as response:
                if response.status == 200 and "text/html" in response.headers.get("Content-Type", ""):
                    return await response.text()
        except Exception as e:
            print(f"[ERROR] Fetching HTML: {e}")
        return ""

    def extract_pdf_link(self, html: str, base_url: str) -> str:
        soup = BeautifulSoup(html, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if ".pdf" in href.lower():
                if href.startswith("/"):
                    return base_url.split("/")[0] + "//" + urlparse(base_url).hostname + href
                elif href.startswith("http"):
                    return href
        return ""

    async def process_doi(self, doi_url: str) -> str:
        resolved_url = await self.resolve_doi(doi_url)
        if not resolved_url:
            return ""

        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=SSL_CONTEXT),
                                         headers={"User-Agent": USER_AGENT}) as session:
            html = await self.fetch_html(session, resolved_url)
            if not html:
                return ""

            pdf_url = self.extract_pdf_link(html, resolved_url)
            return pdf_url or ""

    def normalize_dois(self, doi_list: List[str]) -> List[str]:
        pattern = re.compile(r'^(https?://doi\.org/)?(.+)$', flags=re.IGNORECASE)
        return [f"https://doi.org/{pattern.match(doi.strip()).group(2)}"
                for doi in doi_list if pattern.match(doi.strip())]

    def filter_new_dois(self, doi_list: List[str]) -> List[str]:
        existing_dois = self.normalize_dois(self.db.get_all_dois())
        return [doi for doi in doi_list if doi not in existing_dois]

    async def fetch_pdfs(self, query: str, max_results: int = 250) -> List[str]:
        print(f"[🔍] Searching for: {query}")
        doi_list = fetch_api_results(query, scopus_config, max_results=max_results)
        doi_list = self.normalize_dois(doi_list)
        new_dois = self.filter_new_dois(doi_list)

        print(f"[🆕] {len(new_dois)} new DOIs found (not in DB).")

        pdf_links = []
        for doi in new_dois:
            pdf = await self.process_doi(doi)
            if pdf:
                print(f"[✔️] PDF found: {pdf}")
                pdf_links.append(pdf)
            else:
                print(f"[❌] No PDF for {doi}")

        with open(OUTPUT_FILE, "w") as f:
            for link in pdf_links:
                f.write(link + "\n")

        print(f"\n[📄] PDF links saved to {OUTPUT_FILE}")
        return pdf_links
'''
import asyncio
from Pipeline.Sources.pdf_through_api import PDF_through_API
'''

if __name__ == "__main__":
    query = input("Enter your search query for Scopus: ").strip()
    pdf_finder = PDF_through_API()
    asyncio.run(pdf_finder.fetch_pdfs(query))
