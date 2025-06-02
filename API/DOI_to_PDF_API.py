import requests
from bs4 import BeautifulSoup
from Science_direct_get_links import fetch_scopus_results, extract_top_entries, extract_doi_list

API_KEY = '22c00fad5ae3d1d7be9ce917c4c6af6e'
HEADERS = {
    'Accept': 'application/json',
    'X-ELS-APIKey': API_KEY
}


def pdf_exists(doi: str) -> bool:
    url = f"https://api.elsevier.com/content/article/doi/{doi}?view=FULL"
    response = requests.get(url, headers=HEADERS)

    if response.status_code != 200:
        print(f"[!] Error accessing metadata for DOI {doi}: {response.status_code}")
        return False

    data = response.json()
    links = data.get('full-text-retrieval-response', {}).get('coredata', {}).get('link', [])

    for link in links:
        if link.get('@rel') == 'scidir' and 'pdf' in link.get('@href', '').lower():
            return True
    return False


def get_pdf_link_from_doi(doi: str) -> str:
    url = f"https://api.elsevier.com/content/article/doi/{doi}?view=FULL"
    response = requests.get(url, headers=HEADERS)

    if response.status_code != 200:
        print(f"[!] Error retrieving article for DOI {doi}: {response.status_code}")
        return ""

    data = response.json()
    links = data.get('full-text-retrieval-response', {}).get('coredata', {}).get('link', [])

    for link in links:
        if link.get('@rel') == 'scidir' and 'pdf' in link.get('@href', '').lower():
            return link.get('@href', '')
    return ""


def scrape_pdf_link(doi: str) -> str:
    doi_url = f"https://doi.org/{doi}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        r = requests.get(doi_url, headers=headers, timeout=10)
        if r.status_code != 200:
            print(f"[!] DOI page load failed ({doi_url}): {r.status_code}")
            return ""

        soup = BeautifulSoup(r.text, 'html.parser')
        link = soup.find('a', string='Download PDF')
        if link and link.has_attr('href'):
            return requests.compat.urljoin(r.url, link['href'])

    except Exception as e:
        print(f"[!] Exception while scraping PDF for {doi}: {e}")
    return ""


# --- Main execution block ---
query = "'Toronto climate change'"
data = fetch_scopus_results(query)
top_entries = extract_top_entries(data)
doi_list = extract_doi_list(data)

print(f"\n[+] Processing {len(doi_list)} DOIs...\n")

for doi in doi_list:
    print(f"\nDOI: {doi}")

    if pdf_exists(doi):
        pdf_link = get_pdf_link_from_doi(doi)
        print(f"[✔] PDF (via Elsevier API): {pdf_link}")
    else:
        print("[✖] No PDF via Elsevier API. Attempting scrape...")
        scraped_link = scrape_pdf_link(doi)
        if scraped_link:
            print(f"[✔] Scraped PDF link: {scraped_link}")
        else:
            print("[✖] No PDF link found via scraping.")

print("\n[✓] Done.")
