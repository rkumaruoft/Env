import requests
from typing import Callable, Any


class APIConfig:
    def __init__(self, base_url: str, api_key: str, headers: dict, params_builder: Callable[[str, int], dict],
                 entry_parser: Callable[[dict], dict], doi_extractor: Callable[[dict], list]):
        self.base_url = base_url
        self.api_key = api_key
        self.headers = headers
        self.params_builder = params_builder
        self.entry_parser = entry_parser
        self.doi_extractor = doi_extractor


def fetch_api_results(query: str, config: APIConfig, max_results: int = 250, page_size: int = 25) -> list:
    """Paginate through API results until max_results are fetched or no more pages remain."""
    all_dois = []
    start = 0

    while len(all_dois) < max_results:
        params = config.params_builder(query, start)
        response = requests.get(config.base_url, headers=config.headers, params=params)
        response.raise_for_status()
        data = response.json()

        new_dois = config.doi_extractor(data)
        if not new_dois:
            break

        all_dois.extend(new_dois)
        print(f"Fetched {len(new_dois)} DOIs (Total so far: {len(all_dois)})")

        # Stop if we fetched fewer results than the page size (no more pages)
        if len(new_dois) < page_size:
            break

        start += page_size

    return all_dois[:max_results]  # Trim if necessary


def extract_top_entries(data: dict, parser: Callable[[dict], dict], limit: int = 5) -> list:
    entries = data.get('search-results', {}).get('entry', [])
    return [parser(entry) for entry in entries[:limit]]


def print_entries(entries: list):
    for i, entry in enumerate(entries, 1):
        print(f"\nPaper {i}:")
        for key, value in entry.items():
            print(f"{key.capitalize()}: {value}")


def print_doi_list(doi_list: list):
    print("\nDOI List:")
    for doi in doi_list:
        print(doi)
    print(f"\nTotal DOIs found: {len(doi_list)}")


# --- SCOPUS-SPECIFIC CONFIG ---

def scopus_params_builder(query: str, start: int = 0) -> dict:
    return {
        'httpAccept': 'application/json',
        'apiKey': SCOPUS_API_KEY,
        'query': query,
        'start': start,
        'count': 25
    }


def scopus_entry_parser(entry: dict) -> dict:
    title = entry.get('dc:title', 'No title')
    authors = entry.get('dc:creator', 'No author')
    pub_date = entry.get('prism:coverDate', 'No date')
    scopus_link = next((l['@href'] for l in entry.get('link', []) if l['@ref'] == 'scopus'), 'No link')
    doi = entry.get('prism:doi')
    doi_link = f"https://doi.org/{doi}" if doi else "No DOI"
    return {
        'title': title,
        'authors': authors,
        'date': pub_date,
        'scopus_link': scopus_link,
        'doi_link': doi_link
    }


def scopus_doi_extractor(data: dict) -> list:
    entries = data.get('search-results', {}).get('entry', [])
    return [f"https://doi.org/{entry['prism:doi']}" for entry in entries if 'prism:doi' in entry]


SCOPUS_API_KEY = '22c00fad5ae3d1d7be9ce917c4c6af6e'
scopus_config = APIConfig(
    base_url='https://api.elsevier.com/content/search/scopus',
    api_key=SCOPUS_API_KEY,
    headers={},  # or {'X-API-Key': SCOPUS_API_KEY}
    params_builder=scopus_params_builder,
    entry_parser=scopus_entry_parser,
    doi_extractor=scopus_doi_extractor
)

if __name__ == "__main__":
    query = input("Enter your search query for Scopus: ").strip()
    doi_list = fetch_api_results(query, scopus_config, max_results=250)

    if len(doi_list) < 250:
        print(f"\n[⚠️] Only {len(doi_list)} DOIs found (less than 250). No more results available.")

    print_doi_list(doi_list)


