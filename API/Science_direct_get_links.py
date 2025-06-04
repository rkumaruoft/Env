import requests

API_KEY = '22c00fad5ae3d1d7be9ce917c4c6af6e'
BASE_URL = 'https://api.elsevier.com/content/search/scopus'


def fetch_scopus_results(query: str, api_key: str = API_KEY) -> dict:
    """Fetches raw search results from Scopus API."""
    params = {
        'httpAccept': 'application/json',
        'apiKey': api_key,
        'query': query
    }
    response = requests.get(BASE_URL, params=params)
    response.raise_for_status()
    return response.json()


def extract_top_entries(data: dict, limit: int = 5) -> list:
    """Extracts top N entries from the Scopus API response."""
    entries = data.get('search-results', {}).get('entry', [])
    top_entries = []

    for i, entry in enumerate(entries[:limit], 1):
        title = entry.get('dc:title', 'No title')
        authors = entry.get('dc:creator', 'No author')
        pub_date = entry.get('prism:coverDate', 'No date')
        scopus_link = next((l['@href'] for l in entry.get('link', []) if l['@ref'] == 'scopus'), 'No link')
        doi = entry.get('prism:doi')
        doi_link = f"https://doi.org/{doi}" if doi else "No DOI"

        top_entries.append({
            'title': title,
            'authors': authors,
            'date': pub_date,
            'scopus_link': scopus_link,
            'doi_link': doi_link
        })

    return top_entries


def print_entries(entries: list):
    """Prints entries in a human-readable format."""
    for i, entry in enumerate(entries, 1):
        print(f"\nPaper {i}:")
        print(f"Title: {entry['title']}")
        print(f"Author(s): {entry['authors']}")
        print(f"Date: {entry['date']}")
        print(f"Scopus Link: {entry['scopus_link']}")
        print(f"DOI Link: {entry['doi_link']}")


def extract_doi_list(data: dict) -> list:
    """Extracts all DOIs from the Scopus API response."""
    entries = data.get('search-results', {}).get('entry', [])
    return [f"https://doi.org/{entry['prism:doi']}" for entry in entries if 'prism:doi' in entry]


def print_doi_list(doi_list: list):
    """Prints the list of DOIs."""
    print("\nDOI List:")
    for doi in doi_list:
        print(doi)
    print(f"\nTotal DOIs found: {len(doi_list)}")


# Example usage:
if __name__ == "__main__":
    query = "'Toronto + climate change'"
    data = fetch_scopus_results(query)

    top_entries = extract_top_entries(data)
    print_entries(top_entries)

    doi_list = extract_doi_list(data)
    print_doi_list(doi_list)