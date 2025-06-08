import requests
from typing import Callable, Any

class APIConfig:
    def __init__(self, base_url: str, api_key: str, headers: dict, params_builder: Callable[[str], dict],
                 entry_parser: Callable[[dict], dict], doi_extractor: Callable[[dict], list]):
        self.base_url = base_url
        self.api_key = api_key
        self.headers = headers
        self.params_builder = params_builder
        self.entry_parser = entry_parser
        self.doi_extractor = doi_extractor


def fetch_api_results(query: str, config: APIConfig) -> dict:
    """Fetch results from the given API using the config."""
    params = config.params_builder(query)
    response = requests.get(config.base_url, headers=config.headers, params=params)
    response.raise_for_status()
    return response.json()


def extract_top_entries(data: dict, parser: Callable[[dict], dict], limit: int = 5) -> list:
    """Extracts top N entries using the provided parser."""
    entries = data.get('search-results', {}).get('entry', [])  # You could make this more dynamic too
    return [parser(entry) for entry in entries[:limit]]


def print_entries(entries: list):
    """Prints entries in a human-readable format."""
    for i, entry in enumerate(entries, 1):
        print(f"\nPaper {i}:")
        for key, value in entry.items():
            print(f"{key.capitalize()}: {value}")


def print_doi_list(doi_list: list):
    """Prints the list of DOIs."""
    print("\nDOI List:")
    for doi in doi_list:
        print(doi)
    print(f"\nTotal DOIs found: {len(doi_list)}")


# --- SCOPUS SPECIFIC CONFIG ---

def scopus_params_builder(query: str) -> dict:
    return {
        'httpAccept': 'application/json',
        'apiKey': SCOPUS_API_KEY,
        'query': query
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
    headers={},  # or {'X-API-Key': SCOPUS_API_KEY} if needed
    params_builder=scopus_params_builder,
    entry_parser=scopus_entry_parser,
    doi_extractor=scopus_doi_extractor
)


if __name__ == "__main__":
    query = "'Toronto + climate change'"
    data = fetch_api_results(query, scopus_config)

    top_entries = extract_top_entries(data, scopus_config.entry_parser)
    print_entries(top_entries)

    doi_list = scopus_config.doi_extractor(data)
    print_doi_list(doi_list)
