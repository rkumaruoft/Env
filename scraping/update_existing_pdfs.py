#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import time
import pandas as pd
import logging
from datetime import datetime
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import sqlite3

db_path = "MySQLDB/climate_docs.db"

'''
This update existing pdfs script pulls pdfs from the database, and then checks for existing versions using Google CSE.
Outputs a log of updated and non-updated pdfs.
Requires: db_path, api keys from google cse. 
'''

# Google CSE credentials
API_KEY = "blerp" # Use your own google CSE API key here
CX = "burp"
if not API_KEY or not CX:
    raise RuntimeError("Environment variables GOOGLE_CSE_API_KEY and GOOGLE_CSE_CX must be set.")

# How many top-results to inspect per query
NUM_RESULTS = 5

# Rate-limit / retry settings
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds
search_cd = 5 #seconds  - to limit rate so google doesn't swat me when using free version

# Where to write the update log (CSV)
UPDATE_LOG_CSV = "update_log2.csv"


# Initialize logging
def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    return logging.getLogger(__name__)


logger = setup_logging()


# ─────────────────────────────────────────────────────────────────────────────
# HELPER FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

def load_config(db_path: str) -> pd.DataFrame:
    """
    Connect to the SQLite database at `db_path` and read the `documents` table.
    Expect columns: title, type, authors, date, doi, publishing_organization.
    Returns a DataFrame with those columns. If any error occurs, returns empty DataFrame.
    """
    if not os.path.exists(db_path):
        logger.error(f"Database file '{db_path}' not found.")
        return pd.DataFrame(columns=["title", "type", "authors", "date", "doi", "publishing_organization"])

    try:
        conn = sqlite3.connect(db_path)
        df = pd.read_sql("SELECT * FROM document LIMIT 20;", con=conn) # currently reads 20
        conn.close()
    except Exception as e:
        logger.error(f"Failed to read from database '{db_path}': {e}")
        return pd.DataFrame(columns=["title", "type", "authors", "date", "doi", "publishing_organization"])

    # Ensure required columns exist
    required_cols = {"title", "date", "publishing_organization"}
    missing = required_cols - set(df.columns)
    if missing:
        logger.error(f"Database is missing required columns: {missing}")
        return pd.DataFrame(columns=["title", "type", "authors", "date", "doi", "publishing_organization"])

    return df


def parse_year_from_date(date_str: str) -> int:
    """
    Given a date string (e.g. '2020-07-15' or '2020'), parse out the year as int.
    If parsing fails or year not in 2000-2099, return None.
    Old function - no longer use this anymore
    """
    try:
        # Try ISO format first
        dt = datetime.fromisoformat(date_str)
        year = dt.year
    except Exception:
        # Fallback: search for 4-digit substring 20xx
        m = re.search(r"(20\d{2})", date_str)
        if m:
            year = int(m.group(1))
        else:
            return None

    if 2000 <= year <= 2099:
        return year
    return None


def build_query(title: str, publisher: str) -> str:
    """
    Build a Google CSE query string using:
      - exact-phrase for title
      - exact-phrase for publishing_organization
      - filetype:pdf
    """
    if not title:
        raise ValueError("Title must be provided.")
    pieces = [f"\"{title}\""]
    if publisher:
        pieces.append(f"\"{publisher}\"")
    pieces.append("filetype:pdf")
    return " ".join(pieces)


def google_search(query: str, num_results: int = NUM_RESULTS) -> list:
    """
    Hit Google Custom Search API, return a list of dicts {link, title, snippet}.
    Retries up to MAX_RETRIES on 429/5xx errors, with exponential backoff.
    """
    try:
        service = build("customsearch", "v1", developerKey=API_KEY)
    except Exception as e:
        logger.error(f"Failed to build Google CSE service: {e}")
        return []

    backoff = RETRY_DELAY
    for attempt in range(MAX_RETRIES):
        try:
            resp = (
                service
                .cse()
                .list(q=query, cx=CX, num=num_results)
                .execute()
            )
            return resp.get("items", [])
        except HttpError as e:
            code = e.resp.status
            if code in (429, 500, 503) and attempt < MAX_RETRIES - 1:
                logger.warning(f"CSE rate limit/server error (status {code}); retrying in {backoff}s...")
                time.sleep(backoff)
                backoff *= 2
                continue
            else:
                logger.error(f"Google search failed (status {code}): {e}")
                return []
        except Exception as e:
            logger.error(f"Unexpected error during Google search: {e}")
            return []
    return []


def extract_year_from_url_or_title(item: dict) -> int:
    """
    Given a Google CSE result item (keys 'link' and 'title'),
    attempt to parse out a 4-digit year (20xx) from the URL first, then title.
    Return the year as int, or None if not found.
    """
    url = item.get("link", "") or ""
    m = re.search(r"(20\d{2})", url)
    if m:
        return int(m.group(1))
    title = item.get("title", "") or ""
    m2 = re.search(r"(20\d{2})", title)
    if m2:
        return int(m2.group(1))
    return None


# ─────────────────────────────────────────────────────────────────────────────
# MAIN PIPELINE
# ─────────────────────────────────────────────────────────────────────────────

def update_climate_docs_pipeline():
    """
    For each document in the database:
      1. Extract existing_year from its 'date' column.
      2. Build a CSE query using title + publishing_organization.
      3. Check top results for a PDF with year > existing_year.
      4. Record (existing_year, found_new_year, URL, status) into a log.
    """
    df = load_config(db_path)
    if df.empty:
        logger.error("No documents to process. Exiting.")
        return

    log_records = []
    checked_at = datetime.now().isoformat()

    for idx, row in df.iterrows():
        title = row.get("title", "").strip()
        publisher = row.get("publishing_organization", "").strip()
        date_str = row.get("date", "")
        existing_year = parse_year_from_date(date_str)

        logger.info(f"Processing document: title={title!r}, publisher={publisher!r}, existing_year={existing_year}")

        try:
            query_str = build_query(title, publisher)
        except ValueError as e:
            logger.error(f"Skipping record #{idx} due to missing title: {e}")
            log_records.append({
                "checked_at": checked_at,
                "title": title,
                "publishing_organization": publisher,
                "existing_year": existing_year,
                "found_new_year": None,
                "used_url": None,
                "status": f"skipped: {e}"
            })
            continue

        logger.info(f"  • search query → {query_str}")

        time.sleep(search_cd)
        items = google_search(query_str)
        if not items:
            logger.info("    → No results returned by Google CSE.")
            log_records.append({
                "checked_at": checked_at,
                "title": title,
                "publishing_organization": publisher,
                "existing_year": existing_year,
                "found_new_year": None,
                "used_url": None,
                "status": "no_results"
            })
            continue

        best_candidate = None
        best_year = existing_year if existing_year is not None else 0

        for item in items:
            candidate_year = extract_year_from_url_or_title(item)
            if not candidate_year:
                continue

            if existing_year is None:
                is_newer = candidate_year > best_year
            else:
                is_newer = (candidate_year > existing_year and candidate_year > best_year)

            if is_newer:
                best_year = candidate_year
                best_candidate = item

        if best_candidate:
            new_url = best_candidate["link"]
            logger.info(f"    → Found newer version: year {best_year} at {new_url}")
            status = "found_newer"
            found_year = best_year
        else:
            logger.info("    → No newer version found (year ≤ existing or no valid year parsed).")
            status = "no_newer"
            found_year = existing_year

        log_records.append({
            "checked_at": checked_at,
            "title": title,
            "publishing_organization": publisher,
            "existing_year": existing_year,
            "found_new_year": found_year,
            "used_url": best_candidate["link"] if best_candidate else None,
            "status": status
        })

    # Write out the log CSV
    try:
        df_log = pd.DataFrame(log_records)
        df_log.to_csv(UPDATE_LOG_CSV, index=False, encoding="utf-8")
        logger.info(f"Update log written to {UPDATE_LOG_CSV}")
    except Exception as e:
        logger.error(f"Failed to write update log: {e}")


if __name__ == "__main__":
    update_climate_docs_pipeline()
