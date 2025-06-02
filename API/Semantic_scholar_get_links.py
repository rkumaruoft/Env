import requests
# download_from_pdf_url.py
import os
import aiohttp
import asyncio
import ssl
import certifi

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
OUTPUT_DIR = "./scraping/downloaded_pdfs"
SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())

os.makedirs(OUTPUT_DIR, exist_ok=True)

query = "Toronto climate change"
url = f"https://api.semanticscholar.org/graph/v1/paper/search?query={query}&limit=5&fields=title,authors,year,abstract,url,isOpenAccess,openAccessPdf"

response = requests.get(url)
data = response.json()

#The loop will show you all the data in response needed
for i, paper in enumerate(data.get("data", []), 1):
    print(f"\nPaper {i}:")
    print(f"Title: {paper['title']}")
    print(f"Year: {paper['year']}")
    print(f"Authors: {', '.join(a['name'] for a in paper['authors'])}")
    print(f"Abstract: {paper.get('abstract', 'No abstract')}")
    print(f"PDF: {paper.get('openAccessPdf', {}).get('url', 'No PDF available')}")
    print(f"URL: {paper.get('url')}")


async def download_pdf(pdf_url: str):
    """Download a PDF from a direct link."""
    filename = pdf_url.split("/")[-1]
    if not filename.endswith(".pdf"):
        filename += ".pdf"
    filepath = os.path.join(OUTPUT_DIR, filename)

    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=SSL_CONTEXT),
                                     headers={"User-Agent": USER_AGENT}) as session:
        async with session.get(pdf_url) as response:
            if response.status == 200:
                with open(filepath, "wb") as f:
                    f.write(await response.read())
                print(f"[✓] Downloaded to: {filepath}")
            else:
                print(f"[✗] Failed to download: HTTP {response.status}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python download_from_pdf_url.py https://example.com/your-paper.pdf")
    else:
        for i, paper in enumerate(data.get("data", []), 1):

            asyncio.run(download_pdf(sys.argv[1]))