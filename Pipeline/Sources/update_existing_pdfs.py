import os
import re
import time
import logging
from datetime import datetime
import pandas as pd
import sqlite3
from typing import List, Optional
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


class ClimateDocsUpdater:
    """
    Updates existing PDF documents by searching Google CSE for newer versions
    and logs the results to a CSV. Optionally returns a list of updated PDF URLs.
    """

    def __init__(
        self,
        db_path: str,
        api_key: str,
        cx: str,
        update_log_csv: str = "update_log.csv",
        num_results: int = 5,
        search_delay: int = 5,
        max_retries: int = 3,
        retry_delay: int = 5
    ):
        # Configuration
        self.db_path = db_path
        self.api_key = api_key
        self.cx = cx
        self.update_log_csv = update_log_csv
        self.num_results = num_results
        self.search_delay = search_delay
        self.max_retries = max_retries
        self.retry_delay = retry_delay

        # Setup logger
        self.logger = self._setup_logging()

        # Validate credentials
        if not self.api_key or not self.cx:
            raise RuntimeError("Google CSE API key and CX must be provided.")

    @staticmethod
    def _setup_logging() -> logging.Logger:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        return logging.getLogger(__name__)

    def load_config(self) -> pd.DataFrame:
        """
        Load the `document` table from the SQLite database.
        """
        if not os.path.exists(self.db_path):
            self.logger.error(f"Database file '{self.db_path}' not found.")
            return pd.DataFrame(columns=["title", "type", "authors", "date", "doi", "publishing_organization"])

        try:
            conn = sqlite3.connect(self.db_path)
            df = pd.read_sql("SELECT * FROM document;", con=conn)
            conn.close()
        except Exception as e:
            self.logger.error(f"Failed reading database '{self.db_path}': {e}")
            return pd.DataFrame(columns=["title", "type", "authors", "date", "doi", "publishing_organization"])

        required = {"title", "date", "publishing_organization"}
        if not required.issubset(df.columns):
            missing = required - set(df.columns)
            self.logger.error(f"Missing required columns: {missing}")
            return pd.DataFrame(columns=["title", "type", "authors", "date", "doi", "publishing_organization"])

        return df

    @staticmethod
    def parse_year_from_date(date_str: str) -> Optional[int]:
        """
        Extract a 4-digit year from a date string.
        """
        try:
            year = datetime.fromisoformat(date_str).year
        except Exception:
            m = re.search(r"(20\d{2})", date_str)
            year = int(m.group(1)) if m else None

        return year if year and 2000 <= year <= 2099 else None

    @staticmethod
    def build_query(title: str, publisher: str) -> str:
        """
        Build a Google CSE query for a PDF document.
        """
        if not title:
            raise ValueError("Title must be provided.")
        q = [f'"{title}"']
        if publisher:
            q.append(f'"{publisher}"')
        q.append("filetype:pdf")
        return " ".join(q)

    def google_search(self, query: str) -> list:
        """
        Perform a Google CSE search with retries.
        """
        try:
            service = build("customsearch", "v1", developerKey=self.api_key)
        except Exception as e:
            self.logger.error(f"Failed to build CSE service: {e}")
            return []

        backoff = self.retry_delay
        for attempt in range(self.max_retries):
            try:
                resp = service.cse().list(q=query, cx=self.cx, num=self.num_results).execute()
                return resp.get("items", [])
            except HttpError as e:
                code = e.resp.status
                if code in (429, 500, 503) and attempt < self.max_retries - 1:
                    self.logger.warning(f"Rate/server error {code}, retrying in {backoff}s...")
                    time.sleep(backoff)
                    backoff *= 2
                else:
                    self.logger.error(f"Search failed (status {code}): {e}")
                    return []
            except Exception as e:
                self.logger.error(f"Unexpected search error: {e}")
                return []
        return []

    @staticmethod
    def extract_year_from_result(item: dict) -> Optional[int]:
        """
        Extract a 4-digit year from a search result's link or title.
        """
        text = item.get("link", "") + " " + item.get("title", "")
        m = re.search(r"(20\d{2})", text)
        return int(m.group(1)) if m else None

    def update_pipeline(self, return_links: bool = False) -> Optional[List[str]]:
        """
        Main pipeline to check and log newer PDF versions.
        If `return_links` is True, returns a list of URLs for PDFs found newer than existing.
        """
        df = self.load_config()
        if df.empty:
            self.logger.error("No documents to process.")
            return None

        records = []
        updated_links: List[str] = []
        checked_at = datetime.now().isoformat()

        for _, row in df.iterrows():
            title = row.get("title", "").strip()
            publisher = row.get("publishing_organization", "").strip()
            existing_year = self.parse_year_from_date(row.get("date", ""))

            self.logger.info(f"Processing: {title} (existing year: {existing_year})")
            try:
                query = self.build_query(title, publisher)
            except ValueError as e:
                self.logger.error(e)
                records.append({
                    "checked_at": checked_at,
                    "title": title,
                    "publishing_organization": publisher,
                    "existing_year": existing_year,
                    "found_new_year": None,
                    "used_url": None,
                    "status": f"skipped: {e}"
                })
                continue

            time.sleep(self.search_delay)
            items = self.google_search(query)
            best = None
            best_year = existing_year or 0

            for item in items:
                year = self.extract_year_from_result(item)
                if year and year > best_year:
                    best_year = year
                    best = item

            if best:
                status = "found_newer"
                found_year = best_year
                url = best.get("link")
                updated_links.append(url)
                self.logger.info(f"Found newer ({found_year}) at {url}")
            else:
                status = "no_newer"
                found_year = existing_year
                url = None
                self.logger.info("No newer version found.")

            records.append({
                "checked_at": checked_at,
                "title": title,
                "publishing_organization": publisher,
                "existing_year": existing_year,
                "found_new_year": found_year,
                "used_url": url,
                "status": status
            })

        log_df = pd.DataFrame(records)
        try:
            log_df.to_csv(self.update_log_csv, index=False, encoding="utf-8")
            self.logger.info(f"Log written to {self.update_log_csv}")
        except Exception as e:
            self.logger.error(f"Failed to write log: {e}")

        if return_links:
            return updated_links
        return None


if __name__ == "__main__":
    # Example usage
    updater = ClimateDocsUpdater(
        db_path="Pipeline/database/climate_docs.db",
        api_key=os.getenv("GOOGLE_CSE_API_KEY"),
        cx=os.getenv("GOOGLE_CSE_CX"),
        update_log_csv="update_log2.csv"
    )
    # To get the links of updated PDFs, returns a list of the updated pdfs on top of updating the .csv
    updated = updater.update_pipeline(return_links=True)
    if updated:
        print("Updated PDF URLs:")
        for link in updated:
            print(link)
