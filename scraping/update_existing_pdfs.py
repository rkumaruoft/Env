#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import time
import yaml
import requests
import pandas as pd
import logging
import tempfile
from datetime import datetime
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from PyPDF2 import PdfReader

# ─────────────────────────────────────────────────────────────────────────────
#  CONFIGURATION SECTION
# ─────────────────────────────────────────────────────────────────────────────

# 1) Path to your local folder of PDFs
LOCAL_PDF_FOLDER = "existing_pdfs/" # Needs a pdf folder to reference to

# 2) API Keys (Google CSE)
API_KEY = "burp" # Put your own one in, it's the free version
CX     = "blerp"

# 3) Path to optional YAML confi
CONFIG_FILE = "config.yaml" # currently points to nothing, actual file name is configuration.yaml (need DB info)

# 4) Where to write the update log (CSV):
UPDATE_LOG_CSV = "update_log.csv"

# 5) How many top-results to inspect per query
NUM_RESULTS = 5

# 6) Rate-limit variables
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds

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

def load_config(path: str) -> dict:
    """
    Load optional YAML config. Returns a dict mapping local_filename → config data.
    Expected YAML structure:
      reports:
        - local_filename: "2019_report.pdf"
          logical_name: "Annual Report"
          publisher: "My Organization"
          site: "example.org"
          query_override: ""  # optional custom query
    """
    if not os.path.exists(path):
        logger.info(f"Config file '{path}' not found; proceeding without overrides.")
        return {}

    try:
        with open(path, 'r') as f:
            raw = yaml.safe_load(f) or {}
    except Exception as e:
        logger.error(f"Failed to read config file: {e}")
        return {}

    result = {}
    for entry in raw.get("reports", []):
        try:
            fname = entry["local_filename"]
            result[fname] = {
                "logical_name": entry.get("logical_name"),
                "publisher": entry.get("publisher"),
                "site": entry.get("site"),
                "query_override": entry.get("query_override")
            }
        except KeyError:
            logger.warning("Skipping config entry missing 'local_filename'.")
    return result

def extract_metadata_from_pdf(path_to_pdf: str) -> str:
    """
    Read the PDF’s metadata (title) if available, else return None.
    If any exception occurs, log a warning and return None.
    """
    try:
        reader = PdfReader(path_to_pdf)
        info = reader.metadata
        if info:
            title = info.title or info.get('/Title')
            return title
        return None
    except Exception as e:
        logger.warning(f"Could not extract metadata from '{path_to_pdf}': {e}")
        return None

def parse_year_from_filename(fname: str) -> int:
    """
    Return the largest 4-digit year (20xx) found in the filename, or None if none.
    """
    candidates = re.findall(r"(20\d{2})", fname)
    if not candidates:
        return None
    years = [int(y) for y in candidates]
    return max(years)

def build_query(logical_name: str, publisher: str, site: str = None, query_override: str = None) -> str:
    """
    Build a Google CSE query string. If query_override is provided, use that verbatim.
    Otherwise:
      • exact‑phrase for logical_name
      • exact‑phrase for publisher
      • optionally “site:…”
      • filetype:pdf
    """
    if query_override:
        return query_override

    if not logical_name:
        raise ValueError("logical_name must be provided if no query_override is set.")

    pieces = [f"\"{logical_name}\""]
    if publisher:
        pieces.append(f"\"{publisher}\"")
    if site:
        pieces.append(f"site:{site}")
    pieces.append("filetype:pdf")
    return " ".join(pieces)

def google_search(query: str, num_results: int = NUM_RESULTS) -> list:
    """
    Hit Google Custom Search API, return a list of dicts {link, title, snippet} for each item.
    Retries up to MAX_RETRIES on 429/5xx, with exponential backoff.
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
                logger.warning(f"Google CSE rate limit or server error (status {code}). Retrying in {backoff}s...")
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
    Given a Google CSE result “item” (with keys 'link' and 'title'),
    attempt to parse out a 4‑digit year (20xx) from the URL first, then title.
    Return int year or None.
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

def download_pdf(url: str, target_path: str) -> bool:
    """
    Download the PDF at `url` to a temporary file, validate content-type, and
    move it to `target_path` if valid. Return True on success, False otherwise.
    """
    try:
        with requests.get(url, stream=True, timeout=60) as resp:
            resp.raise_for_status()
            content_type = resp.headers.get("Content-Type", "")
            if "pdf" not in content_type.lower():
                logger.error(f"URL did not return a PDF: {url} (Content-Type: {content_type})")
                return False

            # Write to a temp file first
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                for chunk in resp.iter_content(chunk_size=8192):
                    tmp_file.write(chunk)
                temp_path = tmp_file.name

        # Move temp file to final destination
        os.replace(temp_path, target_path)
        return True
    except Exception as e:
        logger.error(f"Failed to download PDF from {url}: {e}")
        # Clean up temp file if it exists
        try:
            if 'temp_path' in locals() and os.path.exists(temp_path):
                os.remove(temp_path)
        except Exception:
            pass
        return False

# ─────────────────────────────────────────────────────────────────────────────
# MAIN PIPELINE
# ─────────────────────────────────────────────────────────────────────────────

def update_reports_pipeline():
    """
    Iterate over PDFs in LOCAL_PDF_FOLDER. For each:
      1. Determine logical_name and existing_year (from filename or config).
      2. Build and run Google CSE query to find potential newer PDF.
      3. If found newer year > existing_year (or existing_year is None), archive old and download new.
      4. Record a log entry (including timestamp).
    """
    if not os.path.isdir(LOCAL_PDF_FOLDER):
        logger.error(f"'{LOCAL_PDF_FOLDER}' is not a directory or does not exist.")
        return

    config_map = load_config(CONFIG_FILE)
    log_records = []
    checked_at = datetime.now().isoformat()

    for fname in os.listdir(LOCAL_PDF_FOLDER):
        if not fname.lower().endswith(".pdf"):
            continue

        local_path = os.path.join(LOCAL_PDF_FOLDER, fname)
        logger.info(f"Checking local file: {fname}")

        existing_year = parse_year_from_filename(fname)
        logical_name = None
        publisher = None
        site = None
        query_override = None

        if fname in config_map:
            logical_name    = config_map[fname]["logical_name"]
            publisher       = config_map[fname]["publisher"]
            site            = config_map[fname]["site"]
            query_override  = config_map[fname]["query_override"]
        else:
            title_meta = extract_metadata_from_pdf(local_path)
            if title_meta:
                logical_name = title_meta
            else:
                logical_name = re.sub(r"^\d{4}_", "", fname).rsplit(".", 1)[0]
            publisher = None
            site = None

        logger.info(f"  • logical_name={logical_name!r}, existing_year={existing_year}")

        try:
            query_str = build_query(logical_name, publisher, site, query_override)
        except ValueError as e:
            logger.error(f"Skipping '{fname}': {e}")
            log_records.append({
                "checked_at": checked_at,
                "local_file": fname,
                "existing_year": existing_year,
                "found_new_year": None,
                "used_url": None,
                "status": f"skipped: {e}"
            })
            continue

        logger.info(f"  • search query → {query_str}")
        items = google_search(query_str)
        if not items:
            logger.info("    → No results returned by Google CSE.")
            log_records.append({
                "checked_at": checked_at,
                "local_file": fname,
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
                is_newer = candidate_year > existing_year and candidate_year > best_year

            if is_newer:
                best_year = candidate_year
                best_candidate = item

        if best_candidate:
            new_url = best_candidate["link"]
            logger.info(f"    → Found newer version: year {best_year} at {new_url}")

            base_name = fname.rsplit('.pdf', 1)[0]
            if existing_year is not None:
                suffix = f"_v{existing_year}"
            else:
                suffix = "_vorig"
            backup_name = f"{base_name}{suffix}.pdf"
            backup_dir  = os.path.join(LOCAL_PDF_FOLDER, "archive")
            os.makedirs(backup_dir, exist_ok=True)
            backup_path = os.path.join(backup_dir, backup_name)

            # Download new PDF to a temp file, then replace
            temp_target = os.path.join(LOCAL_PDF_FOLDER, f"{base_name}.temp.pdf")
            success = download_pdf(new_url, temp_target)
            if success:
                try:
                    os.replace(local_path, backup_path)
                    os.replace(temp_target, local_path)
                    status = "updated"
                    logger.info(f"    → Archived old to {backup_path}, new PDF saved to {local_path}.")
                except Exception as e:
                    status = "move_failed"
                    logger.error(f"Failed to archive/replace for '{fname}': {e}")
                    # Clean up temp file if still present
                    try:
                        if os.path.exists(temp_target):
                            os.remove(temp_target)
                    except Exception:
                        pass
            else:
                status = "download_failed"
                if os.path.exists(temp_target):
                    try:
                        os.remove(temp_target)
                    except Exception:
                        pass

            log_records.append({
                "checked_at": checked_at,
                "local_file": fname,
                "existing_year": existing_year,
                "found_new_year": best_year,
                "used_url": new_url,
                "status": status
            })

        else:
            logger.info("    → No newer version found (year ≤ existing or no valid year parsed).")
            log_records.append({
                "checked_at": checked_at,
                "local_file": fname,
                "existing_year": existing_year,
                "found_new_year": existing_year,
                "used_url": None,
                "status": "unchanged"
            })

    # Write out the log CSV
    try:
        df = pd.DataFrame(log_records)
        df.to_csv(UPDATE_LOG_CSV, index=False, encoding="utf-8")
        logger.info(f"Update log written to {UPDATE_LOG_CSV}")
    except Exception as e:
        logger.error(f"Failed to write update log: {e}")


if __name__ == "__main__":
    update_reports_pipeline()
