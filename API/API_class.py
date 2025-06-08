import requests
from typing import Dict, List, Optional


class APIClient:
    def __init__(self, base_url: str, api_key: str = "", headers: Optional[Dict[str, str]] = None):
        """
        Initializes the API client.

        :param base_url: Base API endpoint.
        :param api_key: Optional API key (if required).
        :param headers: Optional headers dictionary.
        """
        self.base_url = base_url
        self.api_key = api_key
        self.headers = headers or {}
        self.response = None

    def fetch_response(self, query_params: Dict[str, str]) -> Dict:
        """
        Sends a GET request to the API with specified query parameters.
        Automatically injects the API key if provided.

        :param query_params: Dictionary of query parameters.
        :return: Parsed JSON response.
        """
        # Add API key if needed
        if self.api_key:
            query_params['apiKey'] = self.api_key

        # Default to JSON
        query_params.setdefault('httpAccept', 'application/json')

        try:
            self.response = requests.get(self.base_url, headers=self.headers, params=query_params)
            self.response.raise_for_status()
            return self.response.json()
        except requests.exceptions.RequestException as e:
            print(f"[ERROR] API request failed: {e}")
            return {}

    def get_entries(self, num_entries: int = 5) -> List[Dict]:
        """
        Extracts and formats top N entries from the last API response.

        :param num_entries: Number of entries to return.
        :return: List of dictionaries with entry details.
        """
        if not self.response:
            print("[WARNING] No response data to parse.")
            return []

        entries = self.response.get('search-results', {}).get('entry', [])
        results = []

        for entry in entries[:num_entries]:
            title = entry.get('dc:title', 'No title')
            authors = entry.get('dc:creator', 'No author')
            pub_date = entry.get('prism:coverDate', 'No date')
            doi = entry.get('prism:doi')
            doi_link = f"https://doi.org/{doi}" if doi else "No DOI"
            scopus_link = next((l['@href'] for l in entry.get('link', []) if l.get('@ref') == 'scopus'), 'No link')

            results.append({
                'title': title,
                'authors': authors,
                'date': pub_date,
                'doi_link': doi_link,
                'scopus_link': scopus_link
            })
        return results
