import os
import asyncio
import aiohttp
import xml.etree.ElementTree as ET
from bloom_filter2 import BloomFilter  # pip install bloom-filter2
from urllib.robotparser import RobotFileParser
from urllib.parse import urljoin
from typing import Optional, List

from lxml import html as LH  # pip install lxml

"""
To run in main.py,

import asyncio
from sitemap_scraper_class import SitemapScraper

async def main():
    # You can customize these parameters, or just use the default configurations:
    scraper = SitemapScraper(
        start_sitemap="https://www.toronto.ca/sitemap.xml",
        domain="toronto.ca",
        concurrency=10,
        pdf_concurrency=5,
        user_agent="MyBot/0.1",
        links_file="/scraping/existing_pdf_links.txt",        # make sure this file exists
        keywords=["Climate", "Adaptation", "Mitigation", "Emissions",
            "LENZ", "PollinateTO", "Eco-Roof", "Green",
            "Forestry", "TransformTO", "Waste", "Heat", "Cool",
            "Net Zero", "Net-zero"]
    )
    await scraper.run()

if __name__ == "__main__":
    asyncio.run(main())
"""

class SitemapScraper:
    def __init__(
        self,
        start_sitemap: str = "https://www.toronto.ca/sitemap.xml",
        domain: str = "toronto.ca",
        concurrency: int = 10,
        pdf_concurrency: int = 5,
        user_agent: str = "Sitemap_Scraper/1.2",
        links_file: str = "/scraping/existing_pdf_links.txt",
        keywords: Optional[List[str]] = None,
        bloom_max_elements: int = 200000,
        bloom_error_rate: float = 0.001,
    ):
        self.start_sitemap = start_sitemap
        self.domain = domain
        self.concurrency = concurrency
        self.pdf_concurrency = pdf_concurrency
        self.user_agent = user_agent
        self.links_file = links_file
        self.keywords = keywords or [
            "Climate", "Adaptation", "Mitigation", "Emissions",
            "LENZ", "PollinateTO", "Eco-Roof", "Green",
            "Forestry", "TransformTO", "Waste", "Heat", "Cool",
            "Net Zero", "Net-zero",
        ]

        # robots.txt parser
        self.rp = RobotFileParser()
        robots_url = urljoin(self.start_sitemap, '/robots.txt')
        self.rp.set_url(robots_url)
        self.rp.read()

        # state
        self.visited_pages = BloomFilter(max_elements=bloom_max_elements, error_rate=bloom_error_rate)
        self.found_pdfs = set()
        self.existing_count = 0
        self.session: aiohttp.ClientSession = None  # type: ignore

    def load_existing_links(self) -> None:
        """
        Load previously scraped PDF links from disk.
        """
        if os.path.exists(self.links_file):
            with open(self.links_file, 'r') as lf:
                for line in lf:
                    link = line.strip()
                    if link:
                        self.found_pdfs.add(link)
        self.existing_count = len(self.found_pdfs)

    def is_pdf_url(self, url: str) -> bool:
        return url.lower().endswith('.pdf')

    def is_relevant_url(self, url: str) -> bool:
        low = url.lower()
        return any(kw.lower() in low for kw in self.keywords)

    def is_allowed(self, url: str) -> bool:
        return self.rp.can_fetch(self.user_agent, url)

    async def fetch_xml(self, url: str) -> Optional[ET.Element]:
        if not self.is_allowed(url):
            return None
        try:
            async with self.session.get(url, headers={'User-Agent': self.user_agent}, timeout=15) as resp:
                if resp.status != 200:
                    return None
                text = await resp.text()
                return ET.fromstring(text)
        except Exception:
            return None

    async def collect_sitemap_urls(self, sitemap_url: str) -> List[str]:
        """
        Recursively collect URLs from sitemap index or urlset.
        """
        root = await self.fetch_xml(sitemap_url)
        if root is None:
            return []

        # detect namespace
        ns = {'ns': root.tag.split('}')[0].strip('{')} if '}' in root.tag else {}
        urls: List[str] = []

        # sitemap index
        if root.tag.endswith('sitemapindex'):
            for sitemap in root.findall('ns:sitemap', ns):
                loc = sitemap.find('ns:loc', ns)
                if loc is not None and loc.text:
                    child_url = loc.text.strip()
                    urls.extend(await self.collect_sitemap_urls(child_url))

        # urlset
        elif root.tag.endswith('urlset'):
            for url_el in root.findall('ns:url', ns):
                loc = url_el.find('ns:loc', ns)
                if loc is not None and loc.text:
                    urls.append(loc.text.strip())

        return urls

    async def process_pdf_link(self, url: str) -> None:
        """
        Record a PDF URL if it passes the filters.
        """
        if not self.is_pdf_url(url) or not self.is_relevant_url(url):
            return
        if url in self.found_pdfs:
            return
        self.found_pdfs.add(url)

    async def _process_page(self, page: str, sem_html: asyncio.Semaphore, sem_pdf: asyncio.Semaphore) -> None:
        if not self.is_allowed(page) or page in self.visited_pages:
            return
        self.visited_pages.add(page)

        async with sem_html:
            try:
                async with self.session.get(page, headers={'User-Agent': self.user_agent}, timeout=10) as resp:
                    if resp.status != 200:
                        return
                    content = await resp.text()
            except Exception:
                return

        tree = LH.fromstring(content)
        for a in tree.xpath('//a[@href]'):
            href = a.get('href', '').strip()
            if not href:
                continue
            pdf_url = urljoin(page, href)
            async with sem_pdf:
                await self.process_pdf_link(pdf_url)

    async def write_links(self) -> None:
        os.makedirs(os.path.dirname(self.links_file), exist_ok=True)
        with open(self.links_file, 'w') as lf:
            for url in sorted(self.found_pdfs):
                lf.write(f"{url}\n")

    async def run(self) -> None:
        """
        Execute the full scraping workflow.
        """
        self.load_existing_links()
        async with aiohttp.ClientSession() as session:
            self.session = session
            all_urls = await self.collect_sitemap_urls(self.start_sitemap)
            page_urls = [u for u in all_urls if not self.is_pdf_url(u) and self.is_relevant_url(u)]

            sem_html = asyncio.Semaphore(self.concurrency)
            sem_pdf = asyncio.Semaphore(self.pdf_concurrency)
            tasks = [self._process_page(page, sem_html, sem_pdf) for page in page_urls]
            await asyncio.gather(*tasks)

        await self.write_links()
        new_count = len(self.found_pdfs) - self.existing_count
        print(f"✔️ Total PDF links: {len(self.found_pdfs)}; {new_count} new appended; saved to {self.links_file}")


if __name__ == '__main__':
    scraper = SitemapScraper()
    asyncio.run(scraper.run())
