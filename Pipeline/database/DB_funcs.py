import sqlite3
import json
from datetime import datetime
import os


class ClimateDB:
    def __init__(self, db_path):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        self.create_table_if_not_exists()

    def create_table_if_not_exists(self):
        """Check if 'documents' table exists and create it if not."""
        self.cursor.execute("""
        SELECT name FROM sqlite_master WHERE type='table' AND name='documents';
        """)
        if self.cursor.fetchone():
            print("ℹ️ Table 'documents' already exists.")
            return

        self.cursor.execute("""
        CREATE TABLE documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            type TEXT,
            authors TEXT,
            date TEXT,
            doi TEXT,
            publishing_organization TEXT,
            full_text TEXT,
            doc_name TEXT
        )
        """)
        self.conn.commit()
        print("Table 'documents' created.")

    @staticmethod
    def normalize_date(date_str):
        """Convert date strings to ISO 8601 format if possible."""
        if not date_str:
            return None

        formats = ["%Y-%m-%d", "%Y/%m/%d", "%Y-%m", "%B %Y", "%b %Y", "%Y"]
        for fmt in formats:
            try:
                dt = datetime.strptime(date_str, fmt)
                return dt.date().isoformat()
            except ValueError:
                continue
        return date_str

    def insert_document(self, doc: dict) -> int:
        """
        Insert a single document into the database.

        Args:
            doc (dict): A dictionary representing a document with the following keys:
                - "title" (str, required): Title of the document.
                - "type" (str, optional): Type of the document (e.g., "research paper").
                - "authors" (str or List[str], optional): Authors of the document.
                - "date" (str, optional): Publication or update date (any common format).
                - "doi" or "doi_link" (str, optional): DOI link (optional fallback supported).
                - "publishing_organization" (str, optional): Organization that published the document.
                - "full_text" (str, optional): Full text of the doc
                - "doc_name" : name of the document in the drive folder

        Returns:
            int: 0 if the document was inserted successfully, -1 if insertion failed.
        """
        try:
            title = doc.get("title", "")
            if not isinstance(title, str) or not title.strip():
                print(title)
                print("Insert Failed: Missing or empty 'title'.")
                return -1

            doc_type = doc.get("type", "")
            if not isinstance(doc_type, str):
                doc_type = str(doc_type)

            authors = doc.get("authors", "")
            if isinstance(authors, list):
                authors = ", ".join(str(author) for author in authors)
            elif not isinstance(authors, str):
                authors = "NONE"

            date = self.normalize_date(doc.get("date", ""))
            doi = doc.get("doi") or doc.get("doi_link") or "NONE"
            publishing_org = doc.get("publishing_organization", "NONE")
            if not isinstance(publishing_org, str):
                publishing_org = str(publishing_org)

            full_text = doc.get("full_text", "")
            if not isinstance(full_text, str):
                full_text = str(full_text)

            self.cursor.execute("""
                INSERT INTO documents (title, type, authors, date, doi, publishing_organization, full_text)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (title.strip(), doc_type, authors, date, doi, publishing_org, full_text))
            self.conn.commit()
            return 0

        except Exception as e:
            print(f"Failed to insert document: {e}")
            return -1

    def title_exists(self, title: str) -> bool:
        """
        Check if a document with the given title already exists (case-insensitive).

        Args:
            title (str): Title to check.

        Returns:
            bool: True if a matching title exists, False otherwise.
        """
        if not title or not isinstance(title, str):
            return False

        self.cursor.execute(
            "SELECT 1 FROM documents WHERE LOWER(title) = ? LIMIT 1",
            (title.strip().lower(),)
        )
        return self.cursor.fetchone() is not None

    def insert_from_json(self, json_path):
        """
        Clear all the documents table and insert fresh data from the provided JSON file.

        Args:
            json_path (str): Path to the JSON file containing document entries.
        """
        # Step 1: Clear the table
        self.cursor.execute("DELETE FROM documents")
        self.conn.commit()
        print("Cleared existing records in 'documents' table.")

        # Step 2: Insert new data
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        inserted = 0
        for doc in data:
            if self.insert_document(doc) == 0:
                inserted += 1

        print(f"Inserted {inserted} documents from {json_path}")

    def get_all_titles(self):
        """Return a list of all document titles in the database."""
        self.cursor.execute("SELECT title FROM documents")
        rows = self.cursor.fetchall()
        return [row[0] for row in rows]

    def get_all_publishers(self) -> list:
        """
        Retrieve a list of all unique publishing organizations in lowercase.

        Returns:
            list: A list of unique, lowercase, non-empty publishing organization names.
        """
        self.cursor.execute("""
            SELECT DISTINCT LOWER(TRIM(publishing_organization))
            FROM documents
            WHERE publishing_organization IS NOT NULL AND TRIM(publishing_organization) != ''
        """)
        rows = self.cursor.fetchall()
        return [row[0] for row in rows if row[0]]

    def get_all_dois(self) -> list:
        """
        Retrieve a list of all unique DOI entries in lowercase.

        Returns:
            list: A list of unique, lowercase, non-empty DOI strings.
        """
        self.cursor.execute("""
            SELECT DISTINCT LOWER(TRIM(doi))
            FROM documents
            WHERE doi IS NOT NULL AND TRIM(doi) != ''
        """)
        rows = self.cursor.fetchall()
        return [row[0] for row in rows if row[0]]

    def get_title_and_text(self):
        self.cursor.execute("SELECT title, full_text FROM documents")
        rows = self.cursor.fetchall()
        return [(title, full_text) for title, full_text in rows if title and full_text]

    def get_jsonl_object(self):
        """Fetches all document records and returns them as a JSONL-style list of dicts."""
        self.cursor.execute("""
            SELECT title, full_text, type, authors, date, doi, publishing_organization FROM documents
        """)
        rows = self.cursor.fetchall()

        jsonl_data = []

        for row in rows:
            title, text, doc_type, authors, date, doi, org = row

            if not text or not title:
                continue  # Skip incomplete records

            record = {
                "title": title.strip(),
                "text": text.strip().lower(),
                "type": doc_type.strip() if doc_type else None,
                "authors": authors.strip() if authors else None,
                "date": date.strip() if date else None,
                "doi": doi.strip() if doi else None,
                "publishing_organization": org.strip() if org else None
            }

            jsonl_data.append(record)

        return jsonl_data

    def close(self):
        """Close the database connection."""
        self.conn.close()
        print("Database connection closed.")
