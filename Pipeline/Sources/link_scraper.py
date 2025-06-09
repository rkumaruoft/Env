import os
import asyncio
import aiohttp
from lxml import html
from bloom_filter2 import BloomFilter
from urllib.robotparser import RobotFileParser
from urllib.parse import urljoin, urlparse
from collections import deque
from typing import Optional


class LinkScraper:
    def __init__(
            self,
            start_url="https://www.toronto.ca/services-payments/water-environment/",
            domain="toronto.ca",
            concurrency=10,
            pdf_concurrency=5,
            ua="LinkFetcher/1.2",
            links_file="/scraping/existing_pdf_links.txt",
            keywords=None
    ):
        self.sem_html = None
        self.START_URL = start_url
        self.DOMAIN = domain
        self.CONCURRENCY = concurrency
        self.PDF_CONCURRENCY = pdf_concurrency
        self.USER_AGENT = ua
        self.LINKS_FILE = links_file
        self.KEYWORDS = keywords or [
            "Climate", "Adaptation", "Mitigation", "Emissions",
            "LENZ", "PollinateTO", "Eco-Roof", "Green",
            "Forestry", "TransformTO", "Waste", "Heat", "Cool",
            "Net Zero", "Net-zero"
        ]

        self.visited_pages = set()
        self.found_pdfs = set()
        self.bloom = BloomFilter(max_elements=200000, error_rate=0.001)
        self.queue = deque([(self.START_URL, 0)])

    def is_pdf_url(self, url: str) -> bool:
        return url.lower().endswith(".pdf")

    def is_relevant_pdf(self, url: str, text: str) -> bool:
        lower_u = url.lower()
        lower_t = text.lower()
        return any(kw.lower() in lower_u or kw.lower() in lower_t for kw in self.KEYWORDS)

    async def fetch_html(self, session: aiohttp.ClientSession, url: str) -> Optional[str]:
        try:
            async with session.get(url, timeout=10, headers={'User-Agent': self.USER_AGENT}) as resp:
                resp.raise_for_status()
                return await resp.text()
        except Exception:
            return None

    async def process_pdf_link(self, url: str, link_text: str) -> None:
        if self.is_relevant_pdf(url, link_text):
            self.found_pdfs.add(url)

    async def html_worker(self, html_sess: aiohttp.ClientSession):
        while self.queue:
            page_url, depth = self.queue.popleft()

            rp = RobotFileParser()
            parsed = urlparse(page_url)
            robots_txt = urljoin(f"{parsed.scheme}://{parsed.netloc}", "/robots.txt")
            try:
                rp.set_url(robots_txt)
                rp.read()
            except Exception:
                pass

            if not rp.can_fetch("*", page_url):
                continue

            async with self.sem_html:
                html_text = await self.fetch_html(html_sess, page_url)
            if not html_text:
                continue

            tree = html.fromstring(html_text)
            for anchor in tree.xpath("//a[@href]"):
                href = anchor.get("href").strip()
                full_url = urljoin(page_url, href)
                link_text = anchor.text_content().strip()

                if full_url.startswith(f"https://{self.DOMAIN}") and full_url not in self.visited_pages:
                    self.visited_pages.add(full_url)
                    self.queue.append((full_url, depth + 1))

                if self.is_pdf_url(full_url) and full_url not in self.bloom:
                    self.bloom.add(full_url)
                    await self.process_pdf_link(full_url, link_text)

    async def run(self):
        if os.path.isfile(self.LINKS_FILE):
            with open(self.LINKS_FILE, "r", encoding="utf-8") as lf:
                for line in lf:
                    link = line.strip()
                    if link:
                        self.visited_pages.add(link)
                        self.found_pdfs.add(link)
                        self.bloom.add(link)

        existing_count = len(self.found_pdfs)

        self.visited_pages.add(self.START_URL)

        self.sem_html = asyncio.Semaphore(self.CONCURRENCY)

        connector_html = aiohttp.TCPConnector(limit_per_host=self.CONCURRENCY)
        timeout_html = aiohttp.ClientTimeout(total=60)

        async with aiohttp.ClientSession(connector=connector_html, timeout=timeout_html) as html_sess:
            tasks = [
                asyncio.create_task(self.html_worker(html_sess))
                for _ in range(self.CONCURRENCY)
            ]
            await asyncio.gather(*tasks)

        os.makedirs(os.path.dirname(self.LINKS_FILE), exist_ok=True)
        with open(self.LINKS_FILE, "w", encoding="utf-8") as lf:
            for url in sorted(self.found_pdfs):
                lf.write(f"{url}\n")

        new_added = len(self.found_pdfs) - existing_count
        print(
            f"\u2714\ufe0f Total PDF links: {len(self.found_pdfs)}; {new_added} new appended; saved to {self.LINKS_FILE}")
